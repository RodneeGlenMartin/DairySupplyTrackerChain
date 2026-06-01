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
import asyncio

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

PSGC_API_URL = "https://psgc.cloud/api/provinces/cotabato/cities-municipalities"
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


async def fetch_psgc_municipalities() -> list:
    """Fetch real municipalities of Cotabato from the Philippine PSGC API."""
    logger.info(f"Querying PSGC API: {PSGC_API_URL}")
    last_err = None
    data = None
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(PSGC_API_URL)
                response.raise_for_status()
                data = response.json()
                break
        except Exception as e:
            last_err = e
            logger.warning(f"PSGC API query attempt {attempt+1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
    else:
        raise RuntimeError(f"PSGC API query failed after {MAX_RETRIES} attempts: {last_err}")

    municipalities = []
    for entry in data:
        name = entry.get("name", "").strip()
        code = entry.get("code", "")
        muni_type = entry.get("type", "")
        if name and muni_type in ("City", "Mun"):
            municipalities.append({
                "code": code,
                "name": name,
                "is_city": muni_type == "City",
            })
    logger.info(f"Retrieved {len(municipalities)} municipalities from PSGC API")
    return municipalities


async def fetch_random_names(count: int) -> list:
    """Fetch random representative names from randomuser.me API."""
    logger.info(f"Querying RandomUser API for {count} names...")
    last_err = None
    data = None
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(
                    RANDOMUSER_API_URL,
                    params={"results": str(count), "inc": "name", "noinfo": ""}
                )
                response.raise_for_status()
                data = response.json()
                break
        except Exception as e:
            last_err = e
            logger.warning(f"RandomUser API query attempt {attempt+1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
    else:
        raise RuntimeError(f"RandomUser API query failed after {MAX_RETRIES} attempts: {last_err}")

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


SCHOOL_UUID_NAMESPACE = uuid.UUID("4b4f66a7-0cfc-4034-8c63-6b3a0f7c22df")

def generate_cooperative_uuid(coop_name: str) -> str:
    """Generate a deterministic UUID for a cooperative based on cooperative name."""
    if "Liton Free Farmers Cooperative" in coop_name or coop_name == "Liton Free Farmers Cooperative":
        return PRIMARY_COOP_UUID
    return str(uuid.uuid5(COOPERATIVE_UUID_NAMESPACE, coop_name))


def generate_school_uuid(school_name: str) -> str:
    """Generate a deterministic UUID for a school allocation based on school name."""
    return str(uuid.uuid5(SCHOOL_UUID_NAMESPACE, school_name))


async def fetch_real_schools() -> list:
    """Query real DepEd schools via data.gov.ph CKAN API with a resilient fallback."""
    url = "https://data.gov.ph/api/action/datastore_search"
    params = {"q": "Cotabato", "limit": "50"}
    logger.info(f"Querying data.gov.ph CKAN API: {url} with params {params}")
    
    fallback_schools = [
        "Kabacan National High School",
        "University of Southern Mindanao",
        "Matalam National High School",
        "Carmen National High School",
        "Midsayap National High School",
        "President Roxas National High School",
        "Tulunan National High School",
        "Antipas National High School",
        "Aleosan National High School",
        "Kidapawan City National High School",
        "Libungan National High School",
        "Magpet National High School",
        "Arakan National High School"
    ]
    
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            schools = []
            records = data.get("result", {}).get("records", [])
            for rec in records:
                school_name = rec.get("school_name") or rec.get("name") or rec.get("facility_name") or rec.get("school")
                if school_name:
                    schools.append(school_name.strip())
            
            if schools:
                logger.info(f"Successfully retrieved {len(schools)} schools from CKAN API")
                return list(set(schools))
    except Exception as e:
        logger.warning(f"Failed to fetch schools from data.gov.ph: {e}. Using resilient official fallback schools.")
        
    return fallback_schools


async def fetch_cda_cooperatives(municipalities_list) -> list:
    """Scrape accredited cooperatives from the CDA Region XII portal."""
    portal_url = "https://cda.gov.ph/region-12/list-of-cda-accredited-cooperatives-in-region-xii-as-of-march-31-2025/"
    logger.info(f"Scraping CDA Region XII Portal: {portal_url}")
    
    fallback_coops = [
        {"name": "Cuyapon Farmers Agri Marketing Cooperative", "municipality": "Kabacan"},
        {"name": "CARD Multipurpose Cooperative", "municipality": "Carmen"},
        {"name": "Liton Free Farmers Cooperative", "municipality": "Kabacan"},
        {"name": "Arakan Farmers Agrarian Reform", "municipality": "Arakan"},
        {"name": "Badtasan Farmers Agriculture Cooperative", "municipality": "Badtasan"},
        {"name": "Makilala Multipurpose Cooperative", "municipality": "Makilala"},
        {"name": "Tulunan Farmers Multi-Purpose Cooperative", "municipality": "Tulunan"}
    ]
    
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(portal_url)
            response.raise_for_status()
            
            import re
            from urllib.parse import urljoin
            pdf_links = re.findall(r'href=["\']([^"\']+\.pdf)', response.text, re.IGNORECASE)
            if not pdf_links:
                logger.warning("No PDF links found on CDA Portal Page.")
                return fallback_coops
            
            pdf_url = None
            for link in pdf_links:
                abs_link = urljoin(portal_url, link)
                if "ACCREDITED" in abs_link.upper():
                    pdf_url = abs_link
                    break
            if not pdf_url:
                pdf_url = urljoin(portal_url, pdf_links[0])
                
            logger.info(f"Downloading CDA Accredited list PDF: {pdf_url}")
            pdf_response = await client.get(pdf_url)
            pdf_response.raise_for_status()
            
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(pdf_response.content))
            
            coops = []
            muni_names = [m["name"] for m in municipalities_list]
            
            for page in reader.pages:
                text = page.extract_text()
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                for i, line in enumerate(lines):
                    if any(term in line for term in ["Cooperative", "COOP", "Association"]):
                        coop_name = line
                        coop_muni = None
                        
                        for offset in range(1, 3):
                            if i + offset < len(lines):
                                next_line = lines[i + offset]
                                for m_name in muni_names:
                                    if m_name.lower() in next_line.lower():
                                        coop_muni = m_name
                                        break
                                if coop_muni:
                                    break
                                    
                        if not coop_muni:
                            for m_name in muni_names:
                                if m_name.lower() in coop_name.lower():
                                    coop_muni = m_name
                                    break
                                    
                        if not coop_muni:
                            is_cotabato = False
                            for offset in range(-1, 3):
                                if 0 <= i + offset < len(lines):
                                    if "cotabato" in lines[i+offset].lower() or "kidapawan" in lines[i+offset].lower():
                                        is_cotabato = True
                                        break
                            if is_cotabato:
                                coop_muni = "Kabacan"
                                
                        if coop_muni:
                            coops.append({
                                "name": coop_name,
                                "municipality": coop_muni
                            })
            
            if coops:
                logger.info(f"Successfully scraped {len(coops)} cooperatives from CDA PDF")
                has_cuyapon = any("Cuyapon" in c["name"] for c in coops)
                has_card = any("CARD" in c["name"] for c in coops)
                has_liton = any("Liton" in c["name"] for c in coops)
                if not has_cuyapon:
                    coops.append({"name": "Cuyapon Farmers Agri Marketing Cooperative", "municipality": "Kabacan"})
                if not has_card:
                    coops.append({"name": "CARD Multipurpose Cooperative", "municipality": "Carmen"})
                if not has_liton:
                    coops.append({"name": "Liton Free Farmers Cooperative", "municipality": "Kabacan"})
                return coops
                
    except Exception as e:
        logger.warning(f"Failed to scrape cooperatives from CDA portal: {e}. Using resilient accredited cooperatives fallback.")
        
    return fallback_coops


def provision_cooperatives(cursor, coops: list, names: list):
    """Insert cooperative records using live CDA accredited cooperatives."""
    logger.info("Provisioning cooperatives from live CDA accredited cooperatives...")
    inserted_count = 0
    for i, coop in enumerate(coops):
        coop_name = coop["name"]
        muni_name = coop["municipality"]
        
        name_idx = i % len(names) if names else 0
        rep_name = names[name_idx] if names else f"Representative {i+1}"
        
        coop_uuid = generate_cooperative_uuid(coop_name)
        phone = generate_phone_number(i)
        
        try:
            cursor.execute(
                """
                INSERT INTO cooperatives (id, name, municipality, representative_name, contact_number)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (coop_uuid, coop_name, muni_name, rep_name, phone)
            )
            inserted_count += 1
        except Exception as e:
            logger.warning(f"Skipping cooperative {coop_name}: {e}")
            
    logger.info(f"Inserted {inserted_count} cooperatives from CDA scraper list")
    return inserted_count


def provision_feeding_allocations(cursor, schools: list, municipalities: list):
    """Insert feeding allocations based on real schools fetched from data.gov.ph."""
    logger.info("Provisioning feeding allocations from live school data...")
    muni_names = [m["name"] for m in municipalities]
    inserted_count = 0
    import datetime
    
    for i, school in enumerate(schools):
        alloc_uuid = generate_school_uuid(school)
        agency = "DepEd" if i % 2 == 0 else "DSWD"
        muni = muni_names[i % len(muni_names)] if muni_names else "Kabacan"
        alloc_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=i)
        
        try:
            cursor.execute(
                """
                INSERT INTO feeding_allocations (id, recipient_agency, school_or_center_name, target_municipality, allocation_date, delivery_status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
                """,
                (alloc_uuid, agency, school, muni, alloc_date, "Pending")
            )
            inserted_count += 1
        except Exception as e:
            logger.warning(f"Skipping school allocation for {school}: {e}")
            
    logger.info(f"Inserted {inserted_count} feeding allocations")
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


def safe_print(msg: str):
    """Print message safely, handling encoding errors on Windows."""
    try:
        enc = sys.stdout.encoding or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc))
    except Exception:
        print(msg.encode("ascii", errors="ignore").decode("ascii"))


async def run_provisioner_async():
    """Main entry point helper: fetch live API data and provision the database."""
    safe_print("=" * 60)
    safe_print("Dynamic PSGC Government API Database Provisioner")
    safe_print("=" * 60)

    # Step 1: Fetch municipalities from PSGC API
    safe_print("\n[1/5] Fetching municipalities from Philippine PSGC API...")
    municipalities = await fetch_psgc_municipalities()
    safe_print(f"      Retrieved {len(municipalities)} municipalities:")
    for m in municipalities[:6]:
        safe_print(f"        - {m['name']} (Code: {m['code']})")
    if len(municipalities) > 6:
        safe_print(f"        ... and {len(municipalities) - 6} more")

    # Step 2: Fetch real schools from data.gov.ph API
    safe_print("\n[2/5] Fetching real schools from data.gov.ph CKAN API...")
    schools = await fetch_real_schools()
    safe_print(f"      Retrieved {len(schools)} schools:")
    for s in schools[:6]:
        safe_print(f"        - {s}")
    if len(schools) > 6:
        safe_print(f"        ... and {len(schools) - 6} more")

    # Step 3: Fetch accredited cooperatives from CDA portal
    safe_print("\n[3/5] Fetching accredited cooperatives from CDA Region XII Portal...")
    coops = await fetch_cda_cooperatives(municipalities)
    safe_print(f"      Retrieved {len(coops)} cooperatives:")
    for c in coops[:6]:
        safe_print(f"        - {c['name']} ({c['municipality']})")
    if len(coops) > 6:
        safe_print(f"        ... and {len(coops) - 6} more")

    # Step 4: Fetch representative names from randomuser.me
    safe_print("\n[4/5] Fetching representative names from RandomUser.me API...")
    name_count = min(len(coops), 25) if coops else 25
    names = await fetch_random_names(name_count)
    safe_print(f"      Retrieved {len(names)} names:")
    for n in names[:4]:
        safe_print(f"        - {n}")
    if len(names) > 4:
        safe_print(f"        ... and {len(names) - 4} more")

    # Step 5: Connect to database and provision
    safe_print(f"\n[5/5] Connecting to PostgreSQL database...")
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
        # Provision cooperatives using live CDA data
        coop_count = provision_cooperatives(cursor, coops, names)

        # Provision feeding allocations using live school data
        school_count = provision_feeding_allocations(cursor, schools, municipalities)

        # Provision the 5-generation pedigree tree
        provision_pedigree(cursor)

        # Provision raw milk batches
        provision_raw_milk_batches(cursor)

        conn.commit()
        safe_print(f"\nDatabase provisioning complete!")
        safe_print(f"      Cooperatives inserted: {coop_count}")
        safe_print(f"      Schools/Feeding allocs: {school_count}")
        safe_print(f"      Animals (pedigree):     14")
        safe_print(f"      Raw milk batches:       3")

        # Verification query
        cursor.execute("SELECT COUNT(*) FROM cooperatives;")
        total_coops = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM animals;")
        total_animals = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM raw_milk_batches;")
        total_batches = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM feeding_allocations;")
        total_schools = cursor.fetchone()[0]

        safe_print(f"\n      Verification totals:")
        safe_print(f"        cooperatives:    {total_coops}")
        safe_print(f"        feeding_allocs:  {total_schools}")
        safe_print(f"        animals:         {total_animals}")
        safe_print(f"        raw_milk_batches: {total_batches}")

    except Exception as e:
        conn.rollback()
        logger.critical(f"Provisioning failed: {e}")
        safe_print(f"\nFATAL: Provisioning failed, transaction rolled back: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

    safe_print("\n" + "=" * 60)
    safe_print("SUCCESS: Dynamic provisioning completed.")
    safe_print("=" * 60)


def run_provisioner():
    """Main entry point: run async provisioner loop."""
    asyncio.run(run_provisioner_async())


if __name__ == "__main__":
    run_provisioner()
