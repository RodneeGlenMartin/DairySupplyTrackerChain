from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
import uuid
import logging

from src.config import DATABASE_URL, DISABLE_IN_MEMORY_FALLBACK
from src.genetics import (
    calculate_genetic_blood_fraction,
    calculate_relationship_coefficient,
    calculate_repayment_due_date
)
from src.coldchain import evaluate_batch_spoilage_risk
from src.distribution import generate_batch_hash

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dairy_tracker_api")

app = FastAPI(
    title="Distributed Dairy Supply Chain and Logistics Tracker API",
    description="REST API for herd genetics, cold-chain kinetics, and batch traceability.",
    version="1.0.0"
)

# --- In-Memory Fallback Database ---
# Seed data matching db/seed.sql
IN_MEMORY_COOPERATIVES = {
    "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df": {
        "id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "name": "Liton Free Farmers Cooperative",
        "municipality": "Kabacan"
    }
}

IN_MEMORY_ANIMALS = {
    # 5th Gen
    "aa5e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f": {
        "id": "aa5e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "ear_tag_number": "TAG-GGG-DAM1",
        "registration_name": "Liton GGG Dam 1",
        "birth_date": "2016-01-01",
        "gender": "F",
        "dairy_blood_percentage": 1.0,
        "dam_id": None,
        "sire_id": None,
        "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "status": "Dry"
    },
    "ba5e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f": {
        "id": "ba5e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "ear_tag_number": "TAG-GGG-SIRE1",
        "registration_name": "Liton GGG Sire 1",
        "birth_date": "2016-01-01",
        "gender": "M",
        "dairy_blood_percentage": 1.0,
        "dam_id": None,
        "sire_id": None,
        "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "status": "Agistment"
    },
    # 4th Gen
    "aa4e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f": {
        "id": "aa4e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "ear_tag_number": "TAG-GG-DAM1",
        "registration_name": "Liton GG Dam 1",
        "birth_date": "2018-01-01",
        "gender": "F",
        "dairy_blood_percentage": 1.0,
        "dam_id": "aa5e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "sire_id": "ba5e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "status": "Dry"
    },
    "ba4e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f": {
        "id": "ba4e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "ear_tag_number": "TAG-GG-SIRE1",
        "registration_name": "Liton GG Sire 1",
        "birth_date": "2018-01-01",
        "gender": "M",
        "dairy_blood_percentage": 1.0,
        "dam_id": None,
        "sire_id": None,
        "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "status": "Agistment"
    },
    # 3rd Gen
    "aa3e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f": {
        "id": "aa3e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "ear_tag_number": "TAG-G-DAM1",
        "registration_name": "Liton G Dam 1",
        "birth_date": "2020-01-01",
        "gender": "F",
        "dairy_blood_percentage": 1.0,
        "dam_id": "aa4e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "sire_id": "ba4e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "status": "Dry"
    },
    "ba3e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f": {
        "id": "ba3e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "ear_tag_number": "TAG-G-SIRE1",
        "registration_name": "Liton G Sire 1",
        "birth_date": "2020-01-01",
        "gender": "M",
        "dairy_blood_percentage": 1.0,
        "dam_id": None,
        "sire_id": None,
        "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "status": "Agistment"
    },
    # 2nd Gen
    "ca9e88d1-55fc-42b7-a3a8-4e8979148d21": {
        "id": "ca9e88d1-55fc-42b7-a3a8-4e8979148d21",
        "ear_tag_number": "TAG-GP-DAM",
        "registration_name": "Liton Grand Dam",
        "birth_date": "2022-01-01",
        "gender": "F",
        "dairy_blood_percentage": 1.0,
        "dam_id": "aa3e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "sire_id": "ba3e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "status": "Dry"
    },
    "fa9e88d1-55fc-42b7-a3a8-4e8979148d22": {
        "id": "fa9e88d1-55fc-42b7-a3a8-4e8979148d22",
        "ear_tag_number": "TAG-GP-SIRE",
        "registration_name": "Liton Grand Sire",
        "birth_date": "2022-01-01",
        "gender": "M",
        "dairy_blood_percentage": 1.0,
        "dam_id": None,
        "sire_id": None,
        "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "status": "Agistment"
    },
    # Dams D1 and D2 (sisters)
    "da1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f": {
        "id": "da1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "ear_tag_number": "TAG-DAM-D1",
        "registration_name": "Liton Dam D1",
        "birth_date": "2023-11-01",
        "gender": "F",
        "dairy_blood_percentage": 1.0,
        "dam_id": "ca9e88d1-55fc-42b7-a3a8-4e8979148d21",
        "sire_id": "fa9e88d1-55fc-42b7-a3a8-4e8979148d22",
        "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "status": "Dry"
    },
    "da2e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f": {
        "id": "da2e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "ear_tag_number": "TAG-DAM-D2",
        "registration_name": "Liton Dam D2",
        "birth_date": "2023-11-15",
        "gender": "F",
        "dairy_blood_percentage": 1.0,
        "dam_id": "ca9e88d1-55fc-42b7-a3a8-4e8979148d21",
        "sire_id": "fa9e88d1-55fc-42b7-a3a8-4e8979148d22",
        "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "status": "Dry"
    },
    # Sires
    "fa9e88d1-55fc-42b7-a3a8-4e8979148d25": {
        "id": "fa9e88d1-55fc-42b7-a3a8-4e8979148d25",
        "ear_tag_number": "TAG-SIRE-A",
        "registration_name": "Unrelated Sire A",
        "birth_date": "2023-01-01",
        "gender": "M",
        "dairy_blood_percentage": 1.0,
        "dam_id": None,
        "sire_id": None,
        "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "status": "Agistment"
    },
    "fa9e88d1-55fc-42b7-a3a8-4e8979148d26": {
        "id": "fa9e88d1-55fc-42b7-a3a8-4e8979148d26",
        "ear_tag_number": "TAG-SIRE-B",
        "registration_name": "Unrelated Sire B",
        "birth_date": "2023-01-01",
        "gender": "M",
        "dairy_blood_percentage": 1.0,
        "dam_id": None,
        "sire_id": None,
        "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "status": "Agistment"
    },
    # Cousin A & B
    "aa1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f": {
        "id": "aa1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "ear_tag_number": "TAG-COUSIN-A",
        "registration_name": "Cousin A",
        "birth_date": "2025-01-01",
        "gender": "F",
        "dairy_blood_percentage": 1.0,
        "dam_id": "da1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "sire_id": "fa9e88d1-55fc-42b7-a3a8-4e8979148d25",
        "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "status": "Dry"
    },
    "ba2e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f": {
        "id": "ba2e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "ear_tag_number": "TAG-COUSIN-B",
        "registration_name": "Cousin B",
        "birth_date": "2025-01-10",
        "gender": "M",
        "dairy_blood_percentage": 1.0,
        "dam_id": "da2e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "sire_id": "fa9e88d1-55fc-42b7-a3a8-4e8979148d26",
        "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
        "status": "Agistment"
    }
}

IN_MEMORY_BREEDING_RECORDS = {}
IN_MEMORY_PRODUCT_BATCHES = []

def get_db_connection():
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=1)
        return conn
    except Exception as e:
        if DISABLE_IN_MEMORY_FALLBACK:
            logger.critical("Database connection failed and DISABLE_IN_MEMORY_FALLBACK is true.")
            raise RuntimeError(f"Database connection failed: {e}") from e
        # Silently fall back to in-memory mode
        return None

# --- API Models ---
class AnimalCreate(BaseModel):
    ear_tag_number: str
    registration_name: Optional[str] = None
    birth_date: date
    gender: str = Field(..., pattern="^[MF]$")
    dam_id: Optional[str] = None
    sire_id: Optional[str] = None
    cooperative_id: Optional[str] = None
    status: Optional[str] = None
    vermicomposting_manure_yield_kg: float = 0.0

class BreedingCreate(BaseModel):
    animal_id: str
    breeding_type: str = Field(..., pattern="^(AI|Natural Bull Service)$")
    semen_batch_code: Optional[str] = None
    insemination_date: date
    semen_sire_id: str

class TelemetryPayload(BaseModel):
    temp_log: List[float]
    time_log: List[datetime]
    initial_cfu: float = 1000.0

class BatchCreate(BaseModel):
    batch_identifier: str
    product_type: str = Field(..., pattern="^(Pasteurized Milk|Yogurt|Ice Cream)$")
    quantity_units_produced: int
    manufacture_date: date
    shelf_life_days: int
    coliform_test_status: str = Field(..., pattern="^(Passed|Failed)$")
    pasteurization_temp_celsius: float
    previous_batch_hash: Optional[str] = None

# --- API Endpoints ---

@app.get("/healthz")
def healthz():
    """Liveness probe indicator."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/animals", status_code=status.HTTP_201_CREATED)
def register_animal(animal: AnimalCreate):
    """
    Registers a new animal, calculates genetic blood composition backcrossing fraction:
    G_n = (S_n + D_{n-1}) / 2
    """
    conn = get_db_connection()
    dam_percentage = 0.0
    sire_percentage = 1.0 # Purebred sire default

    if conn:
        try:
            import psycopg2.extras
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Fetch dam percent
            if animal.dam_id:
                cursor.execute("SELECT dairy_blood_percentage FROM animals WHERE id = %s", (animal.dam_id,))
                res = cursor.fetchone()
                if res:
                    dam_percentage = float(res["dairy_blood_percentage"])
            # Fetch sire percent
            if animal.sire_id:
                cursor.execute("SELECT dairy_blood_percentage FROM animals WHERE id = %s", (animal.sire_id,))
                res = cursor.fetchone()
                if res:
                    sire_percentage = float(res["dairy_blood_percentage"])
                    
            calculated_blood = calculate_genetic_blood_fraction(sire_percentage, dam_percentage)
            
            new_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender, 
                                     dairy_blood_percentage, dam_id, sire_id, cooperative_id, status, vermicomposting_manure_yield_kg)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (new_id, animal.ear_tag_number, animal.registration_name, animal.birth_date, animal.gender,
                 calculated_blood, animal.dam_id, animal.sire_id, animal.cooperative_id, animal.status, animal.vermicomposting_manure_yield_kg)
            )
            result = cursor.fetchone()
            conn.commit()
            conn.close()
            # Convert date objects to string for JSON serialization
            result["birth_date"] = str(result["birth_date"])
            result["dairy_blood_percentage"] = float(result["dairy_blood_percentage"])
            return result
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            logger.error(f"Postgres error: {e}")
            if DISABLE_IN_MEMORY_FALLBACK:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database insertion failed: {e}"
                )
            # Failover to in-memory on DB insertion failure
            conn = None

    if not conn:
        # In-Memory execution
        if animal.dam_id in IN_MEMORY_ANIMALS:
            dam_percentage = IN_MEMORY_ANIMALS[animal.dam_id]["dairy_blood_percentage"]
        if animal.sire_id in IN_MEMORY_ANIMALS:
            sire_percentage = IN_MEMORY_ANIMALS[animal.sire_id]["dairy_blood_percentage"]
            
        calculated_blood = calculate_genetic_blood_fraction(sire_percentage, dam_percentage)
        
        new_id = str(uuid.uuid4())
        record = {
            "id": new_id,
            "ear_tag_number": animal.ear_tag_number,
            "registration_name": animal.registration_name,
            "birth_date": str(animal.birth_date),
            "gender": animal.gender,
            "dairy_blood_percentage": calculated_blood,
            "dam_id": animal.dam_id,
            "sire_id": animal.sire_id,
            "cooperative_id": animal.cooperative_id,
            "status": animal.status,
            "vermicomposting_manure_yield_kg": animal.vermicomposting_manure_yield_kg
        }
        IN_MEMORY_ANIMALS[new_id] = record
        return record

@app.post("/breeding", status_code=status.HTTP_201_CREATED)
def log_breeding(breeding: BreedingCreate):
    """
    Logs breeding attempts. Integrates coefficient of relationship R validation.
    Blocks the attempt with HTTP 400 if R >= 0.0625.
    """
    conn = get_db_connection()
    pedigree = {}
    
    if conn:
        try:
            import psycopg2.extras
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT id, dam_id, sire_id FROM animals;")
            rows = cursor.fetchall()
            for r in rows:
                pedigree[str(r["id"])] = {
                    "dam_id": str(r["dam_id"]) if r["dam_id"] else None,
                    "sire_id": str(r["sire_id"]) if r["sire_id"] else None
                }
        except Exception as e:
            logger.error(f"Postgres pedigree fetch error: {e}")
            if DISABLE_IN_MEMORY_FALLBACK:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database pedigree fetch failed: {e}"
                )
            conn = None

    if not conn:
        # Build pedigree from in-memory fallback
        for anim_id, details in IN_MEMORY_ANIMALS.items():
            pedigree[anim_id] = {
                "dam_id": details.get("dam_id"),
                "sire_id": details.get("sire_id")
            }

    # Execute R relationship check
    try:
        calculate_relationship_coefficient(breeding.animal_id, breeding.semen_sire_id, pedigree)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )

    expected_calving = breeding.insemination_date + timedelta(days=310)
    new_id = str(uuid.uuid4())

    if conn:
        try:
            cursor.execute(
                """
                INSERT INTO breeding_records (id, animal_id, breeding_type, semen_batch_code, insemination_date, repayment_status)
                VALUES (%s, %s, %s, %s, %s, 'Pending')
                RETURNING *;
                """,
                (new_id, breeding.animal_id, breeding.breeding_type, breeding.semen_batch_code, breeding.insemination_date)
            )
            result = cursor.fetchone()
            conn.commit()
            conn.close()
            result["insemination_date"] = str(result["insemination_date"])
            result["expected_calving_date"] = str(result["expected_calving_date"])
            return result
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            logger.error(f"Postgres breeding insertion error: {e}")
            if DISABLE_IN_MEMORY_FALLBACK:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database breeding insertion failed: {e}"
                )
            conn = None

    if not conn:
        record = {
            "id": new_id,
            "animal_id": breeding.animal_id,
            "breeding_type": breeding.breeding_type,
            "semen_batch_code": breeding.semen_batch_code,
            "insemination_date": str(breeding.insemination_date),
            "expected_calving_date": str(expected_calving),
            "actual_calving_date": None,
            "calving_outcome_gender": None,
            "repayment_due_date": None,
            "repayment_status": "Pending"
        }
        IN_MEMORY_BREEDING_RECORDS[new_id] = record
        return record

@app.post("/telemetry")
def process_telemetry(payload: TelemetryPayload):
    """
    Receives JSON telemetry logs (temperatures, datetimes) and predicts spoilage risk.
    """
    try:
        final_cfu, status_flag = evaluate_batch_spoilage_risk(
            payload.temp_log,
            payload.time_log,
            payload.initial_cfu
        )
        return {
            "final_cfu": final_cfu,
            "status": status_flag
        }
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Telemetry computation failure: {err}"
        )

@app.post("/batches", status_code=status.HTTP_201_CREATED)
def create_finished_batch(batch: BatchCreate):
    """
    Creates a finished product batch and returns its updated SHA-256 cryptographic chain receipt.
    """
    conn = get_db_connection()
    prev_hash = batch.previous_batch_hash

    if not prev_hash:
        # Retrieve latest signature to chain
        if conn:
            try:
                import psycopg2.extras
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute("SELECT cryptographic_signature FROM product_batches ORDER BY manufacture_date DESC, id DESC LIMIT 1;")
                res = cursor.fetchone()
                if res:
                    prev_hash = res["cryptographic_signature"]
            except Exception as e:
                logger.error(f"Postgres latest signature fetch error: {e}")
                if DISABLE_IN_MEMORY_FALLBACK:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Database latest signature fetch failed: {e}"
                    )
                conn = None
        
        if not conn and IN_MEMORY_PRODUCT_BATCHES:
            prev_hash = IN_MEMORY_PRODUCT_BATCHES[-1]["cryptographic_signature"]

    if not prev_hash:
        prev_hash = "0" * 64

    # Calculate cryptographic signature
    timestamp_str = batch.manufacture_date.strftime("%Y-%m-%d")
    signature = generate_batch_hash(
        previous_hash=prev_hash,
        batch_identifier=batch.batch_identifier,
        volume=float(batch.quantity_units_produced), # treating unit volume mapping
        pasteur_temp=batch.pasteurization_temp_celsius,
        coliform_status=batch.coliform_test_status,
        timestamp=timestamp_str
    )

    new_id = str(uuid.uuid4())
    if conn:
        try:
            cursor.execute(
                """
                INSERT INTO product_batches (id, batch_identifier, product_type, quantity_units_produced,
                                             manufacture_date, shelf_life_days, coliform_test_status,
                                             pasteurization_temp_celsius, previous_batch_hash, cryptographic_signature)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (new_id, batch.batch_identifier, batch.product_type, batch.quantity_units_produced,
                 batch.manufacture_date, batch.shelf_life_days, batch.coliform_test_status,
                 batch.pasteurization_temp_celsius, prev_hash, signature)
            )
            result = cursor.fetchone()
            conn.commit()
            conn.close()
            result["manufacture_date"] = str(result["manufacture_date"])
            result["expiry_date"] = str(result["expiry_date"])
            return result
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            logger.error(f"Postgres batch insertion error: {e}")
            if DISABLE_IN_MEMORY_FALLBACK:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database batch insertion failed: {e}"
                )
            conn = None

    if not conn:
        expiry_date = batch.manufacture_date + timedelta(days=batch.shelf_life_days)
        record = {
            "id": new_id,
            "batch_identifier": batch.batch_identifier,
            "product_type": batch.product_type,
            "quantity_units_produced": batch.quantity_units_produced,
            "manufacture_date": str(batch.manufacture_date),
            "shelf_life_days": batch.shelf_life_days,
            "expiry_date": str(expiry_date),
            "coliform_test_status": batch.coliform_test_status,
            "pasteurization_temp_celsius": batch.pasteurization_temp_celsius,
            "previous_batch_hash": prev_hash,
            "cryptographic_signature": signature
        }
        IN_MEMORY_PRODUCT_BATCHES.append(record)
        return record
