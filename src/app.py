from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
import asyncio
import uuid
import logging
import os
import json
import httpx

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

def get_db_connection():
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=1)
        return conn
    except Exception as e:
        logger.critical(f"Database connection failed: {e}")
        raise RuntimeError(f"Database connection failed: {e}") from e

# --- Dynamic Public API Caches & Helpers ---

MUNICIPALITIES_GEO = [
    {"name": "Kabacan", "lat": 7.118, "lon": 124.843, "texture": "Clay Loam", "clay_pct": 28.0},
    {"name": "Midsayap", "lat": 7.192, "lon": 124.530, "texture": "Clay Loam", "clay_pct": 30.0},
    {"name": "Carmen", "lat": 7.198, "lon": 124.795, "texture": "Clay Loam", "clay_pct": 32.0},
    {"name": "Matalam", "lat": 7.070, "lon": 124.970, "texture": "Sandy Clay Loam", "clay_pct": 22.0},
    {"name": "Aleosan", "lat": 7.210, "lon": 124.620, "texture": "Clay", "clay_pct": 45.0},
    {"name": "Libungan", "lat": 7.240, "lon": 124.520, "texture": "Sandy Loam", "clay_pct": 15.0}
]

async def fetch_open_meteo_weather(latitude: float, longitude: float) -> List[float]:
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&hourly=temperature_2m&past_days=1&forecast_days=1"
    last_err = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                temps = data.get("hourly", {}).get("temperature_2m", [])
                if not temps or len(temps) < 24:
                    raise RuntimeError("Invalid or incomplete weather data from Open-Meteo API")
                return [float(t) for t in temps[-24:]]
        except Exception as e:
            last_err = e
            logger.warning(f"fetch_open_meteo_weather attempt {attempt+1}/3 failed: {e}")
            if attempt < 2:
                await asyncio.sleep(1)
    raise RuntimeError(f"fetch_open_meteo_weather failed after 3 attempts: {last_err}")

def evaluate_forage_suitability(temp: float, moisture: float, texture: str, clay_pct: float) -> Dict[str, Any]:
    # Napier grass evaluation
    napier_score = 0
    if 20.0 <= temp <= 35.0:
        napier_score += 2
    elif 15.0 <= temp <= 40.0:
        napier_score += 1
        
    if 0.18 <= moisture <= 0.38:
        napier_score += 2
    elif 0.12 <= moisture <= 0.45:
        napier_score += 1
        
    if texture in ["Clay Loam", "Sandy Clay Loam"]:
        napier_score += 2
    elif texture in ["Clay", "Sandy Loam"]:
        napier_score += 1
        
    if 20.0 <= clay_pct <= 35.0:
        napier_score += 2
    elif 15.0 <= clay_pct <= 45.0:
        napier_score += 1
        
    napier_suitability = "Low"
    if napier_score >= 7:
        napier_suitability = "High"
    elif napier_score >= 4:
        napier_suitability = "Moderate"
        
    # Guinea grass evaluation
    guinea_score = 0
    if 18.0 <= temp <= 38.0:
        guinea_score += 2
    elif 15.0 <= temp <= 42.0:
        guinea_score += 1
        
    if 0.10 <= moisture <= 0.30:
        guinea_score += 2
    elif 0.08 <= moisture <= 0.38:
        guinea_score += 1
        
    if texture in ["Sandy Loam", "Sandy Clay Loam"]:
        guinea_score += 2
    elif texture in ["Clay Loam"]:
        guinea_score += 1
        
    if 10.0 <= clay_pct <= 25.0:
        guinea_score += 2
    elif 5.0 <= clay_pct <= 35.0:
        guinea_score += 1
        
    guinea_suitability = "Low"
    if guinea_score >= 7:
        guinea_suitability = "High"
    elif guinea_score >= 4:
        guinea_suitability = "Moderate"
        
    return {
        "napier": napier_suitability,
        "guinea": guinea_suitability
    }

async def fetch_soil_suitability(latitude: float, longitude: float) -> Dict[str, Any]:
    nearest = MUNICIPALITIES_GEO[0]
    min_dist = float('inf')
    for m in MUNICIPALITIES_GEO:
        dist = (latitude - m["lat"])**2 + (longitude - m["lon"])**2
        if dist < min_dist:
            min_dist = dist
            nearest = m
            
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&hourly=soil_temperature_0_to_7cm,soil_moisture_0_to_7cm&forecast_days=1"
    last_err = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                temps = data.get("hourly", {}).get("soil_temperature_0_to_7cm", [])
                moistures = data.get("hourly", {}).get("soil_moisture_0_to_7cm", [])
                if not temps or not moistures:
                    raise RuntimeError("Invalid or incomplete soil suitability data from Open-Meteo API")
                soil_temp = float(sum(temps[:24]) / len(temps[:24]))
                soil_moisture = float(sum(moistures[:24]) / len(moistures[:24]))
                
                evaluation = evaluate_forage_suitability(soil_temp, soil_moisture, nearest["texture"], nearest["clay_pct"])
                
                return {
                    "latitude": latitude,
                    "longitude": longitude,
                    "nearest_municipality": nearest["name"],
                    "soil_texture": nearest["texture"],
                    "clay_percentage": nearest["clay_pct"],
                    "soil_temperature_celsius": round(soil_temp, 2),
                    "soil_moisture_m3_m3": round(soil_moisture, 3),
                    "forage_suitability": {
                        "napier_grass": evaluation["napier"],
                        "guinea_grass": evaluation["guinea"]
                    }
                }
        except Exception as e:
            last_err = e
            logger.warning(f"fetch_soil_suitability attempt {attempt+1}/3 failed: {e}")
            if attempt < 2:
                await asyncio.sleep(1)
    raise RuntimeError(f"fetch_soil_suitability failed after 3 attempts: {last_err}")

def get_canister_status_details(final_cfu: float):
    if final_cfu > 1.0e5:
        return "error", "highrisk", "High Risk Warning"
    elif final_cfu > 1.0e4:
        return "warning", "elevated", "Isolate for Validation"
    else:
        return "success", "normal", "Clear for Processing"

def build_bars_and_rows(temps: List[float], times: List[datetime]):
    n = len(temps)
    cfu_vals = []
    intervals = [max(1, n // 4), max(1, n // 2), max(1, (3 * n) // 4), n]
    for step in intervals:
        sub_temps = temps[:step]
        sub_times = times[:step]
        try:
            val = evaluate_batch_spoilage_risk(sub_temps, sub_times)[0]
        except Exception:
            val = 1000.0
        cfu_vals.append(val)
        
    bars_html = ""
    for val in cfu_vals:
        pct = max(10, min(100, int((val / 1.0e5) * 100)))
        bar_class = ""
        if val > 1.0e5:
            bar_class = " red"
        elif val > 1.0e4:
            bar_class = " yellow"
        bars_html += f'<div class="curve-bar{bar_class}" style="height: {pct}%;"></div>\n'
        
    rows_html = ""
    step_rows = max(1, n // 12)
    for i in range(0, n, step_rows):
        if i < len(times):
            time_str = times[i].strftime("%H:%M")
            temp_val = temps[i]
            rows_html += f"<tr><td>{time_str}</td><td>{temp_val:.1f}</td></tr>\n"
        
    return bars_html, rows_html

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
    temp_log: Optional[List[float]] = None
    time_log: Optional[List[datetime]] = None
    initial_cfu: float = 1000.0
    latitude: Optional[float] = None
    longitude: Optional[float] = None

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

    try:
        import psycopg2.extras
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Fetch dam percent
        if animal.dam_id:
            cursor.execute("SELECT dairy_blood_percentage FROM animals WHERE id = %s", (animal.dam_id,))
            res = cursor.fetchone()
            if res:
                dam_percentage = float(res["dairy_blood_percentage"])
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Dam animal with id {animal.dam_id} not found."
                )
        # Fetch sire percent
        if animal.sire_id:
            cursor.execute("SELECT dairy_blood_percentage FROM animals WHERE id = %s", (animal.sire_id,))
            res = cursor.fetchone()
            if res:
                sire_percentage = float(res["dairy_blood_percentage"])
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sire animal with id {animal.sire_id} not found."
                )
                
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
    except HTTPException:
        if conn:
            conn.close()
        raise
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        logger.error(f"Postgres error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database insertion failed: {e}"
        )

@app.post("/breeding", status_code=status.HTTP_201_CREATED)
def log_breeding(breeding: BreedingCreate):
    """
    Logs breeding attempts. Integrates coefficient of relationship R validation.
    Blocks the attempt with HTTP 400 if R >= 0.0625.
    """
    conn = get_db_connection()
    pedigree = {}
    
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
        if conn:
            conn.close()
        logger.error(f"Postgres pedigree fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database pedigree fetch failed: {e}"
        )

    # Execute R relationship check
    try:
        calculate_relationship_coefficient(breeding.animal_id, breeding.semen_sire_id, pedigree)
    except ValueError as val_err:
        if conn:
            conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )

    expected_calving = breeding.insemination_date + timedelta(days=310)
    new_id = str(uuid.uuid4())

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database breeding insertion failed: {e}"
        )

@app.post("/telemetry")
async def process_telemetry(payload: TelemetryPayload):
    """
    Receives JSON telemetry logs (temperatures, datetimes) or coordinates and predicts spoilage risk.
    """
    try:
        temp_log = payload.temp_log
        time_log = payload.time_log
        
        if payload.latitude is not None and payload.longitude is not None:
            temp_log = await fetch_open_meteo_weather(payload.latitude, payload.longitude)
            time_log = [datetime.utcnow() - timedelta(hours=len(temp_log) - 1 - i) for i in range(len(temp_log))]
            
        if not temp_log or not time_log:
            raise ValueError("Either temp_log/time_log or latitude/longitude coordinates must be provided.")
            
        final_cfu, status_flag = evaluate_batch_spoilage_risk(
            temp_log,
            time_log,
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

    try:
        import psycopg2.extras
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if not prev_hash:
            # Retrieve latest signature to chain
            cursor.execute("SELECT cryptographic_signature FROM product_batches ORDER BY manufacture_date DESC, id DESC LIMIT 1;")
            res = cursor.fetchone()
            if res:
                prev_hash = res["cryptographic_signature"]
    except Exception as e:
        if conn:
            conn.close()
        logger.error(f"Postgres latest signature fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database latest signature fetch failed: {e}"
        )

    if not prev_hash:
        prev_hash = "0" * 64

    # Calculate cryptographic signature
    timestamp_str = batch.manufacture_date.strftime("%Y-%m-%d")
    signature = generate_batch_hash(
        previous_hash=prev_hash,
        batch_identifier=batch.batch_identifier,
        volume=float(batch.quantity_units_produced),
        pasteur_temp=batch.pasteurization_temp_celsius,
        coliform_status=batch.coliform_test_status,
        timestamp=timestamp_str
    )

    new_id = str(uuid.uuid4())
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database batch insertion failed: {e}"
        )

# --- HCI HTML Templates ---

FIELD_PORTAL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Field Technician Portal</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #121212;
            --card-bg: #1E1E1E;
            --text-color: #F5F5F5;
            --text-muted: #A3A3A3;
            --primary: #0D9488;
            --primary-hover: #0F766E;
            --border: #374151;
            --border-high: #E5E7EB;
            --error: #EF4444;
            --success: #10B981;
            --warning: #F59E0B;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            padding: 16px;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        
        .container {
            width: 100%;
            max-width: 500px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 0;
            border-bottom: 2px solid var(--border);
        }
        
        h1 {
            font-family: 'Outfit', sans-serif;
            font-size: 24px;
            font-weight: 700;
        }
        
        .i18n-select {
            background-color: var(--card-bg);
            color: var(--text-color);
            border: 2px solid var(--border-high);
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 16px;
            height: 48px;
            cursor: pointer;
        }
        
        .sync-bar {
            padding: 12px 16px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
            font-weight: 600;
            font-size: 16px;
        }
        .sync-bar.synced {
            background-color: rgba(16, 185, 129, 0.15);
            border: 2px solid var(--success);
            color: var(--success);
        }
        .sync-bar.pending {
            background-color: rgba(245, 158, 11, 0.15);
            border: 2px solid var(--warning);
            color: var(--warning);
        }
        .sync-bar.offline {
            background-color: rgba(239, 68, 68, 0.15);
            border: 2px solid var(--error);
            color: var(--error);
        }
        
        .indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
        }
        .indicator.synced { background-color: var(--success); }
        .indicator.pending { background-color: var(--warning); }
        .indicator.offline { background-color: var(--error); }
        
        .tabs {
            display: flex;
            border-bottom: 2px solid var(--border);
            gap: 8px;
        }
        
        .tab-btn {
            flex: 1;
            background: none;
            border: none;
            color: var(--text-muted);
            padding: 16px 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            text-align: center;
            border-bottom: 4px solid transparent;
            height: 52px;
        }
        .tab-btn.active {
            color: var(--text-color);
            border-bottom-color: var(--primary);
        }
        
        .card {
            background-color: var(--card-bg);
            border-radius: 12px;
            padding: 24px;
            border: 2px solid var(--border);
        }
        
        .form-group {
            margin-bottom: 20px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        label {
            font-weight: 600;
            font-size: 16px;
        }
        
        input, select {
            width: 100%;
            background-color: #121212;
            color: var(--text-color);
            border: 2px solid var(--border-high);
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 16px;
            height: 52px;
            outline: none;
        }
        
        input:focus, select:focus {
            border-color: var(--primary);
        }
        
        .submit-btn {
            width: 100%;
            background-color: var(--primary);
            color: #FFFFFF;
            border: none;
            padding: 16px;
            font-size: 18px;
            font-weight: 700;
            border-radius: 8px;
            cursor: pointer;
            height: 54px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background-color 0.2s;
        }
        
        .submit-btn:hover {
            background-color: var(--primary-hover);
        }
        
        .toast {
            position: fixed;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 16px;
            z-index: 1000;
            display: none;
            text-align: center;
            width: calc(100% - 32px);
            max-width: 400px;
            border: 2px solid transparent;
        }
        .toast.success {
            background-color: #064E3B;
            color: #A7F3D0;
            border-color: var(--success);
        }
        .toast.error {
            background-color: #7F1D1D;
            color: #FCA5A5;
            border-color: var(--error);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1 id="ui-title">Field Technician Portal</h1>
            <select class="i18n-select" id="lang-select" onchange="changeLanguage(this.value)">
                <option value="en">English</option>
                <option value="ceb">Cebuano</option>
                <option value="hil">Hiligaynon</option>
                <option value="tl">Tagalog</option>
            </select>
        </header>
        
        <div class="sync-bar synced" id="sync-indicator">
            <span class="indicator synced"></span> <span id="ui-syncStatus">Synced</span>
        </div>
        
        <div class="tabs">
            <button class="tab-btn active" id="tab-animal" onclick="switchTab('animal')">Register Animal</button>
            <button class="tab-btn" id="tab-breeding" onclick="switchTab('breeding')">Log Breeding</button>
            <button class="tab-btn" id="tab-soil" onclick="switchTab('soil')">Soil & Forage</button>
        </div>
        
        <div class="card" id="animal-panel">
            <form id="animal-form" onsubmit="handleAnimalSubmit(event)">
                <div class="form-group">
                    <label for="animal-tag" id="lbl-earTag">Ear Tag Number</label>
                    <input type="text" id="animal-tag" required placeholder="e.g. TAG-1234">
                </div>
                <div class="form-group">
                    <label for="animal-name" id="lbl-regName">Registration Name</label>
                    <input type="text" id="animal-name" placeholder="e.g. Liton Heifer A">
                </div>
                <div class="form-group">
                    <label for="animal-dob" id="lbl-dob">Birth Date</label>
                    <input type="date" id="animal-dob" required>
                </div>
                <div class="form-group">
                    <label for="animal-gender" id="lbl-gender">Gender</label>
                    <select id="animal-gender" required>
                        <option value="F" id="opt-female">Female</option>
                        <option value="M" id="opt-male">Male</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="animal-dam" id="lbl-damId">Dam ID (Optional)</label>
                    <input type="text" id="animal-dam" placeholder="UUID of Dam">
                </div>
                <div class="form-group">
                    <label for="animal-sire" id="lbl-sireId">Sire ID (Optional)</label>
                    <input type="text" id="animal-sire" placeholder="UUID of Sire">
                </div>
                <div class="form-group">
                    <label for="animal-coop" id="lbl-coopId">Cooperative ID (Optional)</label>
                    <input type="text" id="animal-coop" placeholder="UUID of Cooperative">
                </div>
                <div class="form-group">
                    <label for="animal-status" id="lbl-status">Status</label>
                    <select id="animal-status" required>
                        <option value="Dry">Dry</option>
                        <option value="Gestating">Gestating</option>
                        <option value="Lactating">Lactating</option>
                        <option value="Pre-Weaning Heifer">Pre-Weaning Heifer</option>
                        <option value="Post-Weaning Heifer">Post-Weaning Heifer</option>
                        <option value="Agistment">Agistment</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="animal-manure" id="lbl-manure">Manure Yield (kg, Optional)</label>
                    <input type="number" step="0.01" id="animal-manure" value="0.00">
                </div>
                <button type="submit" class="submit-btn" id="btn-submit-animal">Register Animal</button>
            </form>
        </div>
        
        <div class="card" id="breeding-panel" style="display: none;">
            <form id="breeding-form" onsubmit="handleBreedingSubmit(event)">
                <div class="form-group">
                    <label for="breed-animal-id" id="lbl-breedAnimal">Animal ID (Dam)</label>
                    <input type="text" id="breed-animal-id" required placeholder="UUID of Dam">
                </div>
                <div class="form-group">
                    <label for="breed-type" id="lbl-breedingType">Breeding Type</label>
                    <select id="breed-type" required>
                        <option value="AI">AI (Artificial Insemination)</option>
                        <option value="Natural Bull Service">Natural Bull Service</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="breed-semen-code" id="lbl-semenCode">Semen Batch Code (Optional)</label>
                    <input type="text" id="breed-semen-code" placeholder="e.g. SEM-9921">
                </div>
                <div class="form-group">
                    <label for="breed-date" id="lbl-insemDate">Insemination Date</label>
                    <input type="date" id="breed-date" required>
                </div>
                <div class="form-group">
                    <label for="breed-sire-id" id="lbl-semenSire">Semen Sire ID</label>
                    <input type="text" id="breed-sire-id" required placeholder="UUID of Sire">
                </div>
                <button type="submit" class="submit-btn" id="btn-submit-breeding">Log Breeding</button>
            </form>
        </div>
        
        <div class="card" id="soil-panel" style="display: none;">
            <form id="soil-form" onsubmit="handleSoilSubmit(event)">
                <div class="form-group">
                    <label for="soil-lat" id="lbl-soilLat">Latitude</label>
                    <input type="number" step="0.0001" id="soil-lat" required placeholder="e.g. 7.1180" value="7.1180">
                </div>
                <div class="form-group">
                    <label for="soil-lon" id="lbl-soilLon">Longitude</label>
                    <input type="number" step="0.0001" id="soil-lon" required placeholder="e.g. 124.8430" value="124.8430">
                </div>
                <button type="submit" class="submit-btn" id="btn-submit-soil">Check Forage Suitability</button>
            </form>
            <div id="soil-results" style="margin-top: 24px; display: none; border-top: 2px solid var(--border); padding-top: 16px;">
                <h3 style="margin-bottom: 12px;" id="lbl-suitabilityResult">Results</h3>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <div style="display: flex; justify-content: space-between;"><span style="color: var(--text-muted);">Closest Town:</span><span id="res-town" style="font-weight:600;">-</span></div>
                    <div style="display: flex; justify-content: space-between;"><span style="color: var(--text-muted);">Texture:</span><span id="res-texture" style="font-weight:600;">-</span></div>
                    <div style="display: flex; justify-content: space-between;"><span style="color: var(--text-muted);">Clay Pct:</span><span id="res-clay" style="font-weight:600;">-</span></div>
                    <div style="display: flex; justify-content: space-between;"><span style="color: var(--text-muted);">Soil Temp:</span><span id="res-temp" style="font-weight:600;">-</span></div>
                    <div style="display: flex; justify-content: space-between;"><span style="color: var(--text-muted);">Soil Moisture:</span><span id="res-moisture" style="font-weight:600;">-</span></div>
                    <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 12px; border-top: 2px dashed var(--border); padding-top: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; height: 48px;"><span style="font-weight:600;">Napier Grass:</span><span id="res-napier" class="status-badge" style="padding: 6px 12px; border-radius: 4px; font-weight:700;">-</span></div>
                        <div style="display: flex; justify-content: space-between; align-items: center; height: 48px;"><span style="font-weight:600;">Guinea Grass:</span><span id="res-guinea" class="status-badge" style="padding: 6px 12px; border-radius: 4px; font-weight:700;">-</span></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="toast" id="toast-el"></div>
    
    <script>
        const i18n = {
            en: {
                title: "Field Technician Portal",
                registerAnimal: "Register Animal",
                logBreeding: "Log Breeding",
                earTag: "Ear Tag Number",
                regName: "Registration Name",
                dob: "Birth Date",
                gender: "Gender",
                male: "Male",
                female: "Female",
                damId: "Dam ID (Optional)",
                sireId: "Sire ID (Optional)",
                coopId: "Cooperative ID (Optional)",
                status: "Status",
                manure: "Manure Yield (kg, Optional)",
                breedAnimal: "Animal ID (Dam)",
                breedingType: "Breeding Type",
                semenCode: "Semen Batch Code (Optional)",
                insemDate: "Insemination Date",
                semenSire: "Semen Sire ID",
                syncStatusSynced: "Synced",
                syncStatusPending: "Pending Offline ({count} items)",
                syncStatusOffline: "Offline Mode ({count} items)",
                soilSuitability: "Soil & Forage",
                latitude: "Latitude",
                longitude: "Longitude",
                checkSuitability: "Check Forage Suitability",
                results: "Suitability Results"
            }
        };
        
        let currentLang = 'en';
        let offlineQueue = JSON.parse(localStorage.getItem('offlineQueue') || '[]');
        let dictCache = {};

        async function translateText(text, targetLang) {
            if (targetLang === 'en') return text;
            const cacheKey = `translation_${targetLang}_${text}`;
            let cached = sessionStorage.getItem(cacheKey);
            if (cached) return cached;

            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 3000);
                const url = `https://api.mymemory.translated.net/get?q=${encodeURIComponent(text)}&langpair=en|${targetLang}`;
                const response = await fetch(url, { signal: controller.signal });
                clearTimeout(timeoutId);
                
                if (response.ok) {
                    const data = await response.json();
                    if (data && data.responseData && data.responseData.translatedText) {
                        const translated = data.responseData.translatedText;
                        sessionStorage.setItem(cacheKey, translated);
                        return translated;
                    }
                }
            } catch (e) {
                console.warn(`Translation error: ${e}`);
            }
            return null;
        }

        async function changeLanguage(lang) {
            currentLang = lang;
            
            if (dictCache[lang]) {
                applyLanguageDict(dictCache[lang]);
                return;
            }
            
            const dict = {};
            const keys = Object.keys(i18n.en);
            
            for (let key of keys) {
                const text = i18n.en[key];
                if (lang === 'en') {
                    dict[key] = text;
                } else {
                    let cleanText = text;
                    let hasCount = text.includes('{count}');
                    if (hasCount) {
                        cleanText = text.replace('{count}', 'COUNT_VAR');
                    }
                    
                    let translated = await translateText(cleanText, lang);
                    if (!translated) {
                        translated = text;
                    } else if (hasCount) {
                        translated = translated.replace('COUNT_VAR', '{count}').replace('count_var', '{count}');
                    }
                    dict[key] = translated;
                }
            }
            
            dictCache[lang] = dict;
            applyLanguageDict(dict);
        }

        function applyLanguageDict(dict) {
            document.getElementById('ui-title').innerText = dict.title;
            document.getElementById('tab-animal').innerText = dict.registerAnimal;
            document.getElementById('tab-breeding').innerText = dict.logBreeding;
            document.getElementById('tab-soil').innerText = dict.soilSuitability;
            document.getElementById('btn-submit-animal').innerText = dict.registerAnimal;
            document.getElementById('btn-submit-breeding').innerText = dict.logBreeding;
            document.getElementById('btn-submit-soil').innerText = dict.checkSuitability;
            
            document.getElementById('lbl-earTag').innerText = dict.earTag;
            document.getElementById('lbl-regName').innerText = dict.regName;
            document.getElementById('lbl-dob').innerText = dict.dob;
            document.getElementById('lbl-gender').innerText = dict.gender;
            document.getElementById('lbl-damId').innerText = dict.damId;
            document.getElementById('lbl-sireId').innerText = dict.sireId;
            document.getElementById('lbl-coopId').innerText = dict.coopId;
            document.getElementById('lbl-status').innerText = dict.status;
            document.getElementById('lbl-manure').innerText = dict.manure;
            
            document.getElementById('lbl-breedAnimal').innerText = dict.breedAnimal;
            document.getElementById('lbl-breedingType').innerText = dict.breedingType;
            document.getElementById('lbl-semenCode').innerText = dict.semenCode;
            document.getElementById('lbl-insemDate').innerText = dict.insemDate;
            document.getElementById('lbl-semenSire').innerText = dict.semenSire;
            
            document.getElementById('lbl-soilLat').innerText = dict.latitude;
            document.getElementById('lbl-soilLon').innerText = dict.longitude;
            document.getElementById('lbl-suitabilityResult').innerText = dict.results;
            
            document.getElementById('opt-female').innerText = dict.female;
            document.getElementById('opt-male').innerText = dict.male;
            
            updateSyncIndicator();
        }
        
        function switchTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('animal-panel').style.display = 'none';
            document.getElementById('breeding-panel').style.display = 'none';
            document.getElementById('soil-panel').style.display = 'none';
            
            if (tab === 'animal') {
                document.getElementById('tab-animal').classList.add('active');
                document.getElementById('animal-panel').style.display = 'block';
            } else if (tab === 'breeding') {
                document.getElementById('tab-breeding').classList.add('active');
                document.getElementById('breeding-panel').style.display = 'block';
            } else if (tab === 'soil') {
                document.getElementById('tab-soil').classList.add('active');
                document.getElementById('soil-panel').style.display = 'block';
            }
        }
        
        function updateSyncIndicator() {
            const syncEl = document.getElementById('sync-indicator');
            const dict = dictCache[currentLang] || i18n.en;
            const count = offlineQueue.length;
            
            if (!navigator.onLine) {
                syncEl.innerHTML = `<span class="indicator offline"></span> ` + dict.syncStatusOffline.replace('{count}', count);
                syncEl.className = "sync-bar offline";
            } else if (count > 0) {
                syncEl.innerHTML = `<span class="indicator pending"></span> ` + dict.syncStatusPending.replace('{count}', count);
                syncEl.className = "sync-bar pending";
            } else {
                syncEl.innerHTML = `<span class="indicator synced"></span> ` + dict.syncStatusSynced;
                syncEl.className = "sync-bar synced";
            }
        }
        
        function playBeep(type) {
            try {
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                if (type === 'success') {
                    const osc = audioCtx.createOscillator();
                    const gain = audioCtx.createGain();
                    osc.type = 'sine';
                    osc.frequency.setValueAtTime(1000, audioCtx.currentTime);
                    gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.15);
                    osc.connect(gain);
                    gain.connect(audioCtx.destination);
                    osc.start();
                    osc.stop(audioCtx.currentTime + 0.15);
                    
                    if (navigator.vibrate) {
                        navigator.vibrate(100);
                    }
                } else if (type === 'error') {
                    const osc = audioCtx.createOscillator();
                    const gain = audioCtx.createGain();
                    osc.type = 'sawtooth';
                    osc.frequency.setValueAtTime(150, audioCtx.currentTime);
                    gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
                    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5);
                    osc.connect(gain);
                    gain.connect(audioCtx.destination);
                    osc.start();
                    osc.stop(audioCtx.currentTime + 0.5);
                    
                    if (navigator.vibrate) {
                        navigator.vibrate([400, 100, 400]);
                    }
                }
            } catch (e) {
                console.error("Audio Context or Vibration API blocked/unsupported:", e);
            }
        }
        
        function showToast(message, type) {
            const toast = document.getElementById('toast-el');
            toast.innerText = message;
            toast.className = `toast ${type}`;
            toast.style.display = 'block';
            setTimeout(() => {
                toast.style.display = 'none';
            }, 5000);
        }
        
        async function handleAnimalSubmit(e) {
            e.preventDefault();
            const payload = {
                ear_tag_number: document.getElementById('animal-tag').value,
                registration_name: document.getElementById('animal-name').value || null,
                birth_date: document.getElementById('animal-dob').value,
                gender: document.getElementById('animal-gender').value,
                dam_id: document.getElementById('animal-dam').value || null,
                sire_id: document.getElementById('animal-sire').value || null,
                cooperative_id: document.getElementById('animal-coop').value || null,
                status: document.getElementById('animal-status').value,
                vermicomposting_manure_yield_kg: parseFloat(document.getElementById('animal-manure').value || '0')
            };
            
            if (!navigator.onLine) {
                offlineQueue.push({ type: 'animal', payload });
                localStorage.setItem('offlineQueue', JSON.stringify(offlineQueue));
                updateSyncIndicator();
                playBeep('success');
                showToast('Animal registration saved offline.', 'success');
                document.getElementById('animal-form').reset();
                return;
            }
            
            try {
                const res = await fetch('/animals', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.status === 201) {
                    playBeep('success');
                    showToast('Animal registered successfully!', 'success');
                    document.getElementById('animal-form').reset();
                } else {
                    const err = await res.json();
                    playBeep('error');
                    showToast('Error: ' + (err.detail || 'Failed registration'), 'error');
                }
            } catch (err) {
                offlineQueue.push({ type: 'animal', payload });
                localStorage.setItem('offlineQueue', JSON.stringify(offlineQueue));
                updateSyncIndicator();
                playBeep('success');
                showToast('Network error. Saved offline.', 'success');
                document.getElementById('animal-form').reset();
            }
        }
        
        async function handleBreedingSubmit(e) {
            e.preventDefault();
            const payload = {
                animal_id: document.getElementById('breed-animal-id').value,
                breeding_type: document.getElementById('breed-type').value,
                semen_batch_code: document.getElementById('breed-semen-code').value || null,
                insemination_date: document.getElementById('breed-date').value,
                semen_sire_id: document.getElementById('breed-sire-id').value
            };
            
            if (!navigator.onLine) {
                offlineQueue.push({ type: 'breeding', payload });
                localStorage.setItem('offlineQueue', JSON.stringify(offlineQueue));
                updateSyncIndicator();
                playBeep('success');
                showToast('Breeding record saved offline.', 'success');
                document.getElementById('breeding-form').reset();
                return;
            }
            
            try {
                const res = await fetch('/breeding', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.status === 201) {
                    playBeep('success');
                    showToast('Breeding logged successfully!', 'success');
                    document.getElementById('breeding-form').reset();
                } else {
                    const err = await res.json();
                    playBeep('error');
                    showToast('Blocked: ' + (err.detail || 'Failed logging'), 'error');
                }
            } catch (err) {
                offlineQueue.push({ type: 'breeding', payload });
                localStorage.setItem('offlineQueue', JSON.stringify(offlineQueue));
                updateSyncIndicator();
                playBeep('success');
                showToast('Network error. Saved offline.', 'success');
                document.getElementById('breeding-form').reset();
            }
        }
        
        async function syncOfflineQueue() {
            if (!navigator.onLine || offlineQueue.length === 0) return;
            
            const item = offlineQueue[0];
            const url = item.type === 'animal' ? '/animals' : '/breeding';
            
            try {
                const res = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(item.payload)
                });
                if (res.status === 201 || res.status === 400) {
                    offlineQueue.shift();
                    localStorage.setItem('offlineQueue', JSON.stringify(offlineQueue));
                    updateSyncIndicator();
                    if (res.status === 400) {
                        const err = await res.json();
                        showToast('Sync item failed: ' + err.detail, 'error');
                    } else {
                        showToast('Offline item successfully synced!', 'success');
                    }
                    syncOfflineQueue();
                }
            } catch (err) {
                console.error("Failed to sync offline item:", err);
            }
        }
        
        async function handleSoilSubmit(event) {
            event.preventDefault();
            const lat = document.getElementById('soil-lat').value;
            const lon = document.getElementById('soil-lon').value;
            const btn = document.getElementById('btn-submit-soil');
            
            btn.disabled = true;
            btn.innerText = "Querying...";
            
            try {
                const response = await fetch(`/api/soil-suitability?latitude=${lat}&longitude=${lon}`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                
                document.getElementById('res-town').innerText = data.nearest_municipality;
                document.getElementById('res-texture').innerText = data.soil_texture;
                document.getElementById('res-clay').innerText = data.clay_percentage + '%';
                document.getElementById('res-temp').innerText = data.soil_temperature_celsius + '°C';
                document.getElementById('res-moisture').innerText = data.soil_moisture_m3_m3 + ' m³/m³';
                
                const napierEl = document.getElementById('res-napier');
                const guineaEl = document.getElementById('res-guinea');
                
                napierEl.innerText = data.forage_suitability.napier_grass;
                guineaEl.innerText = data.forage_suitability.guinea_grass;
                
                const setSuitabilityStyle = (el, val) => {
                    el.className = "status-badge";
                    if (val === "High") {
                        el.style.backgroundColor = "rgba(16, 185, 129, 0.2)";
                        el.style.color = "#34D399";
                        el.style.border = "1px solid #34D399";
                    } else if (val === "Moderate") {
                        el.style.backgroundColor = "rgba(245, 158, 11, 0.2)";
                        el.style.color = "#FBBF24";
                        el.style.border = "1px solid #FBBF24";
                    } else {
                        el.style.backgroundColor = "rgba(239, 68, 68, 0.2)";
                        el.style.color = "#FCA5A5";
                        el.style.border = "1px solid #FCA5A5";
                    }
                };
                
                setSuitabilityStyle(napierEl, data.forage_suitability.napier_grass);
                setSuitabilityStyle(guineaEl, data.forage_suitability.guinea_grass);
                
                document.getElementById('soil-results').style.display = 'block';
                showToast("Soil suitability fetched successfully!", "success");
                playBeep("success");
            } catch (err) {
                console.error(err);
                showToast("Error querying soil suitability. Using cached/offline fallback.", "error");
                playBeep("error");
                
                document.getElementById('res-town').innerText = "Region 12 Cotabato (Fallback)";
                document.getElementById('res-texture').innerText = "Clay Loam";
                document.getElementById('res-clay').innerText = "28%";
                document.getElementById('res-temp').innerText = "26.5°C";
                document.getElementById('res-moisture').innerText = "0.22 m³/m³";
                
                const napierEl = document.getElementById('res-napier');
                const guineaEl = document.getElementById('res-guinea');
                
                napierEl.innerText = "Moderate";
                guineaEl.innerText = "Moderate";
                
                const setFallbackStyle = (el) => {
                    el.style.backgroundColor = "rgba(245, 158, 11, 0.2)";
                    el.style.color = "#FBBF24";
                    el.style.border = "1px solid #FBBF24";
                };
                setFallbackStyle(napierEl);
                setFallbackStyle(guineaEl);
                
                document.getElementById('soil-results').style.display = 'block';
            } finally {
                btn.disabled = false;
                btn.innerText = dictCache[currentLang]?.checkSuitability || "Check Forage Suitability";
            }
        }
        
        window.addEventListener('online', () => {
            updateSyncIndicator();
            syncOfflineQueue();
        });
        window.addEventListener('offline', updateSyncIndicator);
        
        // Initial setup
        changeLanguage('en');
    </script>
</body>
</html>
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Plant Operator Telemetry Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #121212;
            --card-bg: #1E1E1E;
            --text-color: #F5F5F5;
            --text-muted: #A3A3A3;
            --border: #374151;
            --success: #10B981;
            --warning: #F59E0B;
            --error: #EF4444;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            padding: 24px;
            min-height: 100vh;
        }
        
        header {
            margin-bottom: 32px;
        }
        
        h1 {
            font-family: 'Outfit', sans-serif;
            font-size: 28px;
            font-weight: 800;
        }
        
        p.subtitle {
            color: var(--text-muted);
            margin-top: 4px;
            font-size: 16px;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 24px;
        }
        
        .canister-card {
            background-color: var(--card-bg);
            border-radius: 12px;
            border: 2px solid var(--border);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .canister-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 10px 15px -3px rgba(0,0,0,0.5);
        }
        
        .card-header {
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
        }
        
        .canister-name {
            font-family: 'Outfit', sans-serif;
            font-size: 20px;
            font-weight: 700;
        }
        
        .status-badge {
            padding: 6px 12px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
        }
        
        .status-badge.normal {
            background-color: rgba(16, 185, 129, 0.2);
            color: #34D399;
            border: 1px solid #34D399;
        }
        .status-badge.elevated {
            background-color: rgba(245, 158, 11, 0.2);
            color: #FBBF24;
            border: 1px solid #FBBF24;
        }
        .status-badge.highrisk {
            background-color: rgba(239, 68, 68, 0.2);
            color: #FCA5A5;
            border: 1px solid #FCA5A5;
            animation: flash-animation 1.5s infinite;
        }
        
        @keyframes flash-animation {
            0% { opacity: 0.5; }
            50% { opacity: 1; }
            100% { opacity: 0.5; }
        }
        
        .card-body {
            padding: 20px;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .metric {
            display: flex;
            justify-content: space-between;
            font-size: 15px;
        }
        
        .metric-label { color: var(--text-muted); }
        .metric-val { font-weight: 600; }
        
        .disclosure-trigger {
            background: none;
            border: none;
            color: #0D9488;
            font-size: 16px;
            font-weight: 600;
            padding: 16px 20px;
            width: 100%;
            text-align: left;
            cursor: pointer;
            border-top: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            height: 48px;
        }
        
        .details-panel {
            display: none;
            padding: 20px;
            background-color: #161616;
            border-top: 1px solid var(--border);
            font-size: 14px;
        }
        
        .details-panel table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
        }
        
        .details-panel th, .details-panel td {
            text-align: left;
            padding: 8px;
            border-bottom: 1px solid var(--border);
        }
        .details-panel th { color: var(--text-muted); }
        
        .growth-curve {
            margin-top: 16px;
            height: 100px;
            background-color: #121212;
            border-radius: 6px;
            border: 1px solid var(--border);
            display: flex;
            align-items: flex-end;
            padding: 12px;
            gap: 8px;
            justify-content: space-around;
        }
        
        .curve-bar {
            width: 16px;
            background-color: #0D9488;
            border-radius: 3px 3px 0 0;
            transition: height 0.5s;
        }
        .curve-bar.yellow { background-color: var(--warning); }
        .curve-bar.red { background-color: var(--error); }
    </style>
</head>
<body>
    <header>
        <h1>Plant Operator Telemetry Dashboard</h1>
        <p class="subtitle">Real-time Arrhenius Spoilage Kinetic Models & Canister Health</p>
    </header>
    
    <div class="grid">
        <!-- Canister 1: Normal -->
        <div class="canister-card" style="border-top: 4px solid var(--__CAN1_STATUS_COLOR__);">
            <div class="card-header">
                <span class="canister-name">Canister CAN-001 (Kabacan)</span>
                <span class="status-badge __CAN1_BADGE_CLASS__">__CAN1_STATUS_TEXT__</span>
            </div>
            <div class="card-body">
                <div class="metric">
                    <span class="metric-label">Predicted Load (N_t)</span>
                    <span class="metric-val">__CAN1_LOAD__ CFU/ml</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Last Recorded Temp</span>
                    <span class="metric-val">__CAN1_LAST_TEMP__°C</span>
                </div>
            </div>
            <button class="disclosure-trigger" onclick="toggleDetails(this)">
                <span>View Raw Log & Growth Curve</span>
                <span>▼</span>
            </button>
            <div class="details-panel">
                <h4>Dynamic Growth Curve</h4>
                <div class="growth-curve">
                    __CAN1_BARS__
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Temp (°C)</th>
                        </tr>
                    </thead>
                    <tbody>
                        __CAN1_TABLE_ROWS__
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Canister 2: Elevated -->
        <div class="canister-card" style="border-top: 4px solid var(--__CAN2_STATUS_COLOR__);">
            <div class="card-header">
                <span class="canister-name">Canister CAN-002 (Midsayap)</span>
                <span class="status-badge __CAN2_BADGE_CLASS__">__CAN2_STATUS_TEXT__</span>
            </div>
            <div class="card-body">
                <div class="metric">
                    <span class="metric-label">Predicted Load (N_t)</span>
                    <span class="metric-val">__CAN2_LOAD__ CFU/ml</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Last Recorded Temp</span>
                    <span class="metric-val">__CAN2_LAST_TEMP__°C</span>
                </div>
            </div>
            <button class="disclosure-trigger" onclick="toggleDetails(this)">
                <span>View Raw Log & Growth Curve</span>
                <span>▼</span>
            </button>
            <div class="details-panel">
                <h4>Dynamic Growth Curve</h4>
                <div class="growth-curve">
                    __CAN2_BARS__
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Temp (°C)</th>
                        </tr>
                    </thead>
                    <tbody>
                        __CAN2_TABLE_ROWS__
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Canister 3: High Risk -->
        <div class="canister-card" style="border-top: 4px solid var(--__CAN3_STATUS_COLOR__);">
            <div class="card-header">
                <span class="canister-name">Canister CAN-003 (Carmen)</span>
                <span class="status-badge __CAN3_BADGE_CLASS__">__CAN3_STATUS_TEXT__</span>
            </div>
            <div class="card-body">
                <div class="metric">
                    <span class="metric-label">Predicted Load (N_t)</span>
                    <span class="metric-val">__CAN3_LOAD__ CFU/ml</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Last Recorded Temp</span>
                    <span class="metric-val">__CAN3_LAST_TEMP__°C</span>
                </div>
            </div>
            <button class="disclosure-trigger" onclick="toggleDetails(this)">
                <span>View Raw Log & Growth Curve</span>
                <span>▼</span>
            </button>
            <div class="details-panel">
                <h4>Dynamic Growth Curve</h4>
                <div class="growth-curve">
                    __CAN3_BARS__
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Temp (°C)</th>
                        </tr>
                    </thead>
                    <tbody>
                        __CAN3_TABLE_ROWS__
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <script>
        function toggleDetails(btn) {
            const panel = btn.nextElementSibling;
            const arrow = btn.querySelector('span:last-child');
            const isExpanded = btn.getAttribute('aria-expanded') === 'true';
            
            if (isExpanded) {
                panel.style.display = 'none';
                arrow.innerText = '▼';
                btn.setAttribute('aria-expanded', 'false');
            } else {
                panel.style.display = 'block';
                arrow.innerText = '▲';
                btn.setAttribute('aria-expanded', 'true');
            }
        }
    </script>
</body>
</html>
"""

PASSPORT_FOUND_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dairy Safety Traceability Passport</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #121212;
            --card-bg: #1E1E1E;
            --text-color: #F5F5F5;
            --text-muted: #A3A3A3;
            --border: #374151;
            --success: #10B981;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            padding: 24px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        
        .card {
            background-color: var(--card-bg);
            border-radius: 16px;
            border: 2px solid var(--border);
            padding: 32px;
            width: 100%;
            max-width: 500px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
            display: flex;
            flex-direction: column;
            gap: 24px;
        }
        
        .badge-header {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        
        .check-circle {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background-color: rgba(16, 185, 129, 0.2);
            border: 2px solid var(--success);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--success);
            font-size: 24px;
            font-weight: bold;
        }
        
        .header-text h1 {
            font-family: 'Outfit', sans-serif;
            font-size: 22px;
            font-weight: 800;
        }
        .header-text p {
            color: var(--text-muted);
            font-size: 14px;
            margin-top: 2px;
        }
        
        .passport-desc {
            font-size: 16px;
            line-height: 1.6;
            background-color: #121212;
            padding: 16px;
            border-radius: 8px;
            border: 1px solid var(--border);
        }
        
        .details-group {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .detail-row {
            display: flex;
            justify-content: space-between;
            font-size: 15px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
        }
        .detail-lbl { color: var(--text-muted); }
        .detail-val { font-weight: 600; }
        
        details {
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px;
            background-color: #161616;
        }
        
        summary {
            font-weight: 600;
            cursor: pointer;
            outline: none;
            padding: 4px;
        }
        
        .crypto-data {
            margin-top: 12px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            font-family: monospace;
            font-size: 12px;
            word-break: break-all;
            background-color: #121212;
            padding: 8px;
            border-radius: 4px;
        }
        
        .crypto-lbl {
            color: var(--text-muted);
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="badge-header">
            <div class="check-circle">✓</div>
            <div class="header-text">
                <h1>Dairy Safety Passport</h1>
                <p>Digital Batch Authentication</p>
            </div>
        </div>
        
        <p class="passport-desc">
            This batch of <strong>__PRODUCT_TYPE__</strong> was pasteurized at <strong>__PASTEUR_TEMP__°C</strong> on <strong>__MANUFACTURE_DATE__</strong>. Safety tests: <strong>__COLIFORM_STATUS__</strong>.
        </p>
        
        <div class="details-group">
            <div class="detail-row">
                <span class="detail-lbl">Batch Identifier</span>
                <span class="detail-val">__BATCH_IDENTIFIER__</span>
            </div>
            <div class="detail-row">
                <span class="detail-lbl">Units Produced</span>
                <span class="detail-val">__UNITS_PRODUCED__</span>
            </div>
            <div class="detail-row">
                <span class="detail-lbl">Expiry Date</span>
                <span class="detail-val">__EXPIRY_DATE__</span>
            </div>
        </div>
        
        <details>
            <summary>Audit Cryptographic Signatures</summary>
            <div class="crypto-data">
                <div>
                    <span class="crypto-lbl">Current Batch Signature:</span><br>
                    <span>__SIGNATURE__</span>
                </div>
                <div style="margin-top: 8px;">
                    <span class="crypto-lbl">Previous Link Hash:</span><br>
                    <span>__PREVIOUS_HASH__</span>
                </div>
            </div>
        </details>
    </div>
</body>
</html>
"""

PASSPORT_NOT_FOUND_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dairy Safety Traceability Passport - Not Found</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #121212;
            --card-bg: #1E1E1E;
            --text-color: #F5F5F5;
            --text-muted: #A3A3A3;
            --border: #374151;
            --error: #EF4444;
        }
        
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            padding: 24px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        
        .card {
            background-color: var(--card-bg);
            border-radius: 16px;
            border: 2px solid var(--border);
            padding: 32px;
            width: 100%;
            max-width: 500px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 20px;
            text-align: center;
        }
        
        .warning-circle {
            width: 64px;
            height: 64px;
            border-radius: 50%;
            background-color: rgba(239, 68, 68, 0.2);
            border: 2px solid var(--error);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--error);
            font-size: 32px;
            font-weight: bold;
        }
        
        h1 {
            font-family: 'Outfit', sans-serif;
            font-size: 24px;
            font-weight: 800;
        }
        
        p {
            color: var(--text-muted);
            line-height: 1.6;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="warning-circle">!</div>
        <h1>Safety Passport Not Found</h1>
        <p>
            The batch identifier <strong>__BATCH_ID__</strong> could not be located in our physical database. Please check spelling or verify registration status.
        </p>
    </div>
</body>
</html>
"""

# --- HCI HTML Endpoints ---

@app.get("/api/soil-suitability")
async def get_soil_suitability(latitude: float, longitude: float):
    try:
        return await fetch_soil_suitability(latitude, longitude)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Soil suitability query failure: {e}"
        )

@app.get("/", response_class=HTMLResponse)
@app.get("/field", response_class=HTMLResponse)
def get_field_portal():
    """Serves the Field Technician Mobile Portal."""
    return FIELD_PORTAL_HTML

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard_portal():
    """Serves the Plant Operator Telemetry Dashboard with dynamic live weather feeds."""
    canisters = [
        {"id": 1, "name": "Canister CAN-001 (Kabacan)", "lat": 7.118, "lon": 124.843},
        {"id": 2, "name": "Canister CAN-002 (Midsayap)", "lat": 7.192, "lon": 124.530},
        {"id": 3, "name": "Canister CAN-003 (Carmen)", "lat": 7.198, "lon": 124.795}
    ]
    
    replacements = {}
    for can in canisters:
        cid = can["id"]
        temps = await fetch_open_meteo_weather(can["lat"], can["lon"])
        times = [datetime.utcnow() - timedelta(hours=len(temps) - 1 - i) for i in range(len(temps))]
        
        try:
            final_cfu, _ = evaluate_batch_spoilage_risk(temps, times)
        except Exception:
            final_cfu = 1000.0
            
        color, badge_class, status_text = get_canister_status_details(final_cfu)
        bars, rows = build_bars_and_rows(temps, times)
        
        replacements[f"__CAN{cid}_STATUS_COLOR__"] = color
        replacements[f"__CAN{cid}_BADGE_CLASS__"] = badge_class
        replacements[f"__CAN{cid}_STATUS_TEXT__"] = status_text
        replacements[f"__CAN{cid}_LOAD__"] = f"{final_cfu:.2e}"
        replacements[f"__CAN{cid}_LAST_TEMP__"] = f"{temps[-1]:.1f}"
        replacements[f"__CAN{cid}_BARS__"] = bars
        replacements[f"__CAN{cid}_TABLE_ROWS__"] = rows
        
    html = DASHBOARD_HTML
    for key, val in replacements.items():
        html = html.replace(key, str(val))
        
    return HTMLResponse(content=html)

@app.get("/passport/{batch_id}", response_class=HTMLResponse)
def get_passport_portal(batch_id: str):
    """Serves the Inspector Traceability Passport."""
    conn = get_db_connection()
    try:
        import psycopg2.extras
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT * FROM product_batches WHERE batch_identifier = %s OR id::text = %s LIMIT 1;",
            (batch_id, batch_id)
        )
        batch = cursor.fetchone()
        conn.close()
    except Exception as e:
        logger.error(f"Postgres passport error: {e}")
        if conn:
            conn.close()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed: {e}"
        )
            
    if not batch:
        html = PASSPORT_NOT_FOUND_HTML.replace("__BATCH_ID__", batch_id)
        return HTMLResponse(content=html, status_code=404)
        
    html = PASSPORT_FOUND_HTML
    html = html.replace("__PRODUCT_TYPE__", str(batch["product_type"]))
    html = html.replace("__PASTEUR_TEMP__", str(float(batch["pasteurization_temp_celsius"])))
    html = html.replace("__MANUFACTURE_DATE__", str(batch["manufacture_date"]))
    html = html.replace("__COLIFORM_STATUS__", str(batch["coliform_test_status"]))
    html = html.replace("__BATCH_IDENTIFIER__", str(batch["batch_identifier"]))
    html = html.replace("__UNITS_PRODUCED__", str(batch["quantity_units_produced"]))
    html = html.replace("__EXPIRY_DATE__", str(batch["expiry_date"]))
    html = html.replace("__SIGNATURE__", str(batch["cryptographic_signature"]))
    html = html.replace("__PREVIOUS_HASH__", str(batch["previous_batch_hash"]))
    return HTMLResponse(content=html)

