#!/usr/bin/env python
"""
Dynamic Database Provisioner for the Distributed Dairy Supply Chain Tracker.

Replaces static seed.sql by querying live public APIs:
  - Philippine Standard Geographic Code (PSGC) API for real Cotabato municipalities
  - RandomUser.me API for realistic cooperative representative names

Requires: httpx, psycopg2-binary
Usage: python db/dynamic_provisioner.py
"""
import os
import sys
import time
import uuid
import httpx
import psycopg2
import logging

# Ensure project root is in the import path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src.config import DATABASE_URL
except ImportError:
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/dairy_supplychain"
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dynamic_provisioner")

# --- Constants ---

PSGC_API_URL = "https://psgc.gitlab.io/api/provinces/124700000/cities-municipalities.json"
RANDOMUSER_API_URL = "https://randomuser.me/api/"
HTTP_TIMEOUT = 15.0
MAX_RETRIES = 3
RETRY_DELAY = 2

# Deterministic UUID namespace for reproducible cooperative IDs
COOPERATIVE_UUID_NAMESPACE = uuid.UUID("3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df")

# Fixed UUIDs for the multi-generational pedigree tree (must match test expectations)
PEDIGREE_UUIDS = {
    # 5th gen (Great-Great-Great Grandparents)
    "ggg_dam1":  "aa5e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
    "ggg_sire1": "ba5e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
    # 4th gen (Great-Great Grandparents)
    "gg_dam1":   "aa4e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
    "gg_sire1":  "ba4e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
    # 3rd gen (Great Grandparents)
    "g_dam1":    "aa3e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
    "g_sire1":   "ba3e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
    # 2nd gen (Grandparents)
    "gp_dam":    "ca9e88d1-55fc-42b7-a3a8-4e8979148d21",
    "gp_sire":   "fa9e88d1-55fc-42b7-a3a8-4e8979148d22",
    # 1st gen (Parent Dams - full sisters)
    "dam_d1":    "da1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
    "dam_d2":    "da2e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
    # Unrelated Sires
    "sire_a":    "fa9e88d1-55fc-42b7-a3a8-4e8979148d25",
    "sire_b":    "fa9e88d1-55fc-42b7-a3a8-4e8979148d26",
    # Target cousins (used in inbreeding detection tests)
    "cousin_a":  "aa1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
    "cousin_b":  "ba2e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
}

# The primary cooperative UUID (Kabacan / Liton) used by pedigree and tests
PRIMARY_COOP_UUID = "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df"

# Raw milk batch UUIDs for chaos testing
RAW_MILK_UUIDS = [
    "c1a766a7-0cfc-4034-8c63-6b3a0f7c22df",
    "c2a766a7-0cfc-4034-8c63-6b3a0f7c22df",
    "c3a766a7-0cfc-4034-8c63-6b3a0f7c22df",
]


def http_get_with_retry(url: str, params: dict = None) -> dict:
    """Perform an HTTP GET with retry logic."""
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            last_err = e
            logger.warning(f"HTTP GET {url} attempt {attempt+1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    raise RuntimeError(f"HTTP GET {url} failed after {MAX_RETRIES} attempts: {last_err}")


def fetch_psgc_municipalities() -> list:
    """Fetch real municipalities of Cotabato from the Philippine PSGC API."""
    logger.info(f"Querying PSGC API: {PSGC_API_URL}")
    data = http_get_with_retry(PSGC_API_URL)
    municipalities = []
    for entry in data:
        if entry.get("isMunicipality") or entry.get("isCity"):
            municipalities.append({
                "code": entry.get("code", ""),
                "name": entry.get("name", ""),
                "is_city": entry.get("isCity", False),
            })
    logger.info(f"Retrieved {len(municipalities)} municipalities from PSGC API")
    return municipalities


def fetch_random_names(count: int) -> list:
    """Fetch random representative names from randomuser.me API."""
    logger.info(f"Querying RandomUser API for {count} names...")
    data = http_get_with_retry(
        RANDOMUSER_API_URL,
        params={"results": str(count), "inc": "name", "noinfo": ""}
    )
    names = []
    for result in data.get("results", []):
        name = result.get("name", {})
        full_name = f"{name.get('first', 'Juan')} {name.get('last', 'Dela Cruz')}"
        names.append(full_name)
    logger.info(f"Retrieved {len(names)} names from RandomUser API")
    return names


def generate_phone_number(index: int) -> str:
    """Generate a realistic Philippine mobile number."""
    prefix = 917 + (index % 10)
    suffix = 1234567 + index * 111111
    return f"+63 {prefix} {suffix % 10000000:07d}"


def generate_cooperative_uuid(municipality_name: str, index: int) -> str:
    """Generate a deterministic UUID for a cooperative based on municipality name."""
    # The first cooperative (Kabacan) MUST use the primary UUID for test compatibility
    if municipality_name == "Kabacan" and index == 0:
        return PRIMARY_COOP_UUID
    return str(uuid.uuid5(COOPERATIVE_UUID_NAMESPACE, f"{municipality_name}-dairy-coop-{index}"))


def provision_cooperatives(cursor, municipalities: list, names: list):
    """Insert cooperative records using live PSGC municipalities and random names."""
    logger.info("Provisioning cooperatives from live PSGC municipality data...")

    # Ensure Kabacan is first for test compatibility
    kabacan_entry = None
    other_entries = []
    for m in municipalities:
        if m["name"] == "Kabacan":
            kabacan_entry = m
        else:
            other_entries.append(m)

    ordered = []
    if kabacan_entry:
        ordered.append(kabacan_entry)
    ordered.extend(other_entries)

    inserted_count = 0
    for i, muni in enumerate(ordered):
        name_idx = i % len(names) if names else 0
        rep_name = names[name_idx] if names else f"Representative {i+1}"

        # Generate cooperative name from real municipality
        if muni["name"] == "Kabacan":
            coop_name = "Liton Free Farmers Cooperative"
        else:
            coop_name = f"{muni['name']} Dairy Farmers Cooperative"

        coop_uuid = generate_cooperative_uuid(muni["name"], 0)
        phone = generate_phone_number(i)

        try:
            cursor.execute(
                """
                INSERT INTO cooperatives (id, name, municipality, representative_name, contact_number)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (coop_uuid, coop_name, muni["name"], rep_name, phone)
            )
            inserted_count += 1
        except Exception as e:
            logger.warning(f"Skipping cooperative {muni['name']}: {e}")

    logger.info(f"Inserted {inserted_count} cooperatives from {len(ordered)} PSGC municipalities")
    return inserted_count


def provision_pedigree(cursor):
    """
    Insert a deterministic 5-generation pedigree tree using fixed UUIDs.
    The pedigree structure creates first-cousin relationships for inbreeding detection tests.
    """
    logger.info("Provisioning 5-generation pedigree tree...")

    p = PEDIGREE_UUIDS
    coop = PRIMARY_COOP_UUID

    # 5th Generation Ancestors (Great-Great-Great Grandparents)
    cursor.execute(
        """
        INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender,
                             dairy_blood_percentage, dam_id, sire_id, cooperative_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """,
        (p["ggg_dam1"], "TAG-GGG-DAM1", "Liton GGG Dam 1", "2016-01-01", "F",
         1.0, None, None, coop, "Dry")
    )
    cursor.execute(
        """
        INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender,
                             dairy_blood_percentage, dam_id, sire_id, cooperative_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """,
        (p["ggg_sire1"], "TAG-GGG-SIRE1", "Liton GGG Sire 1", "2016-01-01", "M",
         1.0, None, None, coop, "Agistment")
    )

    # 4th Generation (Great-Great Grandparents)
    cursor.execute(
        """
        INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender,
                             dairy_blood_percentage, dam_id, sire_id, cooperative_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """,
        (p["gg_dam1"], "TAG-GG-DAM1", "Liton GG Dam 1", "2018-01-01", "F",
         1.0, p["ggg_dam1"], p["ggg_sire1"], coop, "Dry")
    )
    cursor.execute(
        """
        INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender,
                             dairy_blood_percentage, dam_id, sire_id, cooperative_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """,
        (p["gg_sire1"], "TAG-GG-SIRE1", "Liton GG Sire 1", "2018-01-01", "M",
         1.0, None, None, coop, "Agistment")
    )

    # 3rd Generation (Great Grandparents)
    cursor.execute(
        """
        INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender,
                             dairy_blood_percentage, dam_id, sire_id, cooperative_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """,
        (p["g_dam1"], "TAG-G-DAM1", "Liton G Dam 1", "2020-01-01", "F",
         1.0, p["gg_dam1"], p["gg_sire1"], coop, "Dry")
    )
    cursor.execute(
        """
        INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender,
                             dairy_blood_percentage, dam_id, sire_id, cooperative_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """,
        (p["g_sire1"], "TAG-G-SIRE1", "Liton G Sire 1", "2020-01-01", "M",
         1.0, None, None, coop, "Agistment")
    )

    # 2nd Generation (Grandparents)
    cursor.execute(
        """
        INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender,
                             dairy_blood_percentage, dam_id, sire_id, cooperative_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """,
        (p["gp_dam"], "TAG-GP-DAM", "Liton Grand Dam", "2022-01-01", "F",
         1.0, p["g_dam1"], p["g_sire1"], coop, "Dry")
    )
    cursor.execute(
        """
        INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender,
                             dairy_blood_percentage, dam_id, sire_id, cooperative_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """,
        (p["gp_sire"], "TAG-GP-SIRE", "Liton Grand Sire", "2022-01-01", "M",
         1.0, None, None, coop, "Agistment")
    )

    # Parent Dams (D1 and D2 are full sisters)
    cursor.execute(
        """
        INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender,
                             dairy_blood_percentage, dam_id, sire_id, cooperative_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """,
        (p["dam_d1"], "TAG-DAM-D1", "Liton Dam D1", "2023-11-01", "F",
         1.0, p["gp_dam"], p["gp_sire"], coop, "Dry")
    )
    cursor.execute(
        """
        INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender,
                             dairy_blood_percentage, dam_id, sire_id, cooperative_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """,
        (p["dam_d2"], "TAG-DAM-D2", "Liton Dam D2", "2023-11-15", "F",
         1.0, p["gp_dam"], p["gp_sire"], coop, "Dry")
    )

    # Unrelated Sires
    cursor.execute(
        """
        INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender,
                             dairy_blood_percentage, dam_id, sire_id, cooperative_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """,
        (p["sire_a"], "TAG-SIRE-A", "Unrelated Sire A", "2023-01-01", "M",
         1.0, None, None, coop, "Agistment")
    )
    cursor.execute(
        """
        INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender,
                             dairy_blood_percentage, dam_id, sire_id, cooperative_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """,
        (p["sire_b"], "TAG-SIRE-B", "Unrelated Sire B", "2023-01-01", "M",
         1.0, None, None, coop, "Agistment")
    )

    # First Cousins (Offspring of D1/SireA and D2/SireB)
    cursor.execute(
        """
        INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender,
                             dairy_blood_percentage, dam_id, sire_id, cooperative_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """,
        (p["cousin_a"], "TAG-COUSIN-A", "Cousin A (Offspring of D1)", "2025-01-01", "F",
         1.0, p["dam_d1"], p["sire_a"], coop, "Dry")
    )
    cursor.execute(
        """
        INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender,
                             dairy_blood_percentage, dam_id, sire_id, cooperative_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
        """,
        (p["cousin_b"], "TAG-COUSIN-B", "Cousin B (Offspring of D2)", "2025-01-10", "M",
         1.0, p["dam_d2"], p["sire_b"], coop, "Agistment")
    )

    logger.info("Pedigree tree (14 animals, 5 generations) provisioned successfully")


def provision_raw_milk_batches(cursor):
    """Insert raw milk batch records for transaction and chaos testing."""
    logger.info("Provisioning raw milk batch records...")

    batches = [
        (RAW_MILK_UUIDS[0], 500.00, 4.20, "Midsayap", "In-Storage", "Passed"),
        (RAW_MILK_UUIDS[1], 450.00, 3.90, "Midsayap", "In-Storage", "Passed"),
        (RAW_MILK_UUIDS[2], 300.00, 5.50, "Midsayap", "In-Storage", "Pending"),
    ]
    for batch in batches:
        cursor.execute(
            """
            INSERT INTO raw_milk_batches (id, volume_liters, batch_temperature_celsius,
                                          origin_municipality, inventory_status, processing_suitability)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING;
            """,
            batch
        )
    logger.info(f"Inserted {len(batches)} raw milk batch records")


def run_provisioner():
    """Main entry point: fetch live API data and provision the database."""
    print("=" * 60)
    print("Dynamic PSGC Government API Database Provisioner")
    print("=" * 60)

    # Step 1: Fetch municipalities from PSGC API
    print("\n[1/4] Fetching municipalities from Philippine PSGC API...")
    municipalities = fetch_psgc_municipalities()
    print(f"      Retrieved {len(municipalities)} municipalities:")
    for m in municipalities[:6]:
        print(f"        - {m['name']} (Code: {m['code']})")
    if len(municipalities) > 6:
        print(f"        ... and {len(municipalities) - 6} more")

    # Step 2: Fetch representative names from randomuser.me
    print("\n[2/4] Fetching representative names from RandomUser.me API...")
    name_count = min(len(municipalities), 25)
    names = fetch_random_names(name_count)
    print(f"      Retrieved {len(names)} names:")
    for n in names[:4]:
        print(f"        - {n}")
    if len(names) > 4:
        print(f"        ... and {len(names) - 4} more")

    # Step 3: Connect to database and provision
    print(f"\n[3/4] Connecting to PostgreSQL database...")
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        conn.autocommit = False
        cursor = conn.cursor()
        logger.info("Database connection established")
    except Exception as e:
        logger.critical(f"Database connection failed: {e}")
        print(f"\nFATAL: Could not connect to database: {e}")
        sys.exit(1)

    try:
        # Provision cooperatives from live PSGC data
        coop_count = provision_cooperatives(cursor, municipalities, names)

        # Provision the 5-generation pedigree tree
        provision_pedigree(cursor)

        # Provision raw milk batches
        provision_raw_milk_batches(cursor)

        conn.commit()
        print(f"\n[4/4] Database provisioning complete!")
        print(f"      Cooperatives inserted: {coop_count}")
        print(f"      Animals (pedigree):     14")
        print(f"      Raw milk batches:       3")

        # Verification query
        cursor.execute("SELECT COUNT(*) FROM cooperatives;")
        total_coops = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM animals;")
        total_animals = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM raw_milk_batches;")
        total_batches = cursor.fetchone()[0]

        print(f"\n      Verification totals:")
        print(f"        cooperatives:    {total_coops}")
        print(f"        animals:         {total_animals}")
        print(f"        raw_milk_batches: {total_batches}")

    except Exception as e:
        conn.rollback()
        logger.critical(f"Provisioning failed: {e}")
        print(f"\nFATAL: Provisioning failed, transaction rolled back: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

    print("\n" + "=" * 60)
    print("SUCCESS: Dynamic provisioning completed.")
    print("=" * 60)


if __name__ == "__main__":
    run_provisioner()
