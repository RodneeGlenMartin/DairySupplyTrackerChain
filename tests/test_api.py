import unittest
import psycopg2
from fastapi.testclient import TestClient
from datetime import datetime, date, timedelta
from src.app import app
from src.config import DATABASE_URL

client = TestClient(app)

class TestDairyTrackerAPI(unittest.TestCase):

    def setUp(self):
        self.conn = psycopg2.connect(DATABASE_URL)
        cursor = self.conn.cursor()
        # Clean up existing test records to avoid duplicate errors
        cursor.execute("DELETE FROM product_batches WHERE batch_identifier IN ('API-BATCH-001', 'API-BATCH-002', 'TEST-BATCH-PASSPORT');")
        cursor.execute("DELETE FROM breeding_records WHERE semen_batch_code IN ('SEM-COUSIN-99', 'SEM-OK-12');")
        cursor.execute("DELETE FROM animals WHERE ear_tag_number IN ('TAG-TEST-DAM-1', 'TAG-TEST-OFFSPRING-1');")
        self.conn.commit()
        cursor.close()

    def tearDown(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM product_batches WHERE batch_identifier IN ('API-BATCH-001', 'API-BATCH-002', 'TEST-BATCH-PASSPORT');")
        cursor.execute("DELETE FROM breeding_records WHERE semen_batch_code IN ('SEM-COUSIN-99', 'SEM-OK-12');")
        cursor.execute("DELETE FROM animals WHERE ear_tag_number IN ('TAG-TEST-DAM-1', 'TAG-TEST-OFFSPRING-1');")
        self.conn.commit()
        cursor.close()
        self.conn.close()

    def test_healthz_endpoint(self):
        response = client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertIn("timestamp", response.json())

    def test_register_animal_without_parents(self):
        payload = {
            "ear_tag_number": "TAG-TEST-DAM-1",
            "registration_name": "Test Dam 1",
            "birth_date": "2024-01-01",
            "gender": "F",
            "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
            "status": "Dry"
        }
        response = client.post("/animals", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["ear_tag_number"], "TAG-TEST-DAM-1")
        self.assertEqual(data["dairy_blood_percentage"], 0.5000)

    def test_register_animal_with_seeded_parents(self):
        payload = {
            "ear_tag_number": "TAG-TEST-OFFSPRING-1",
            "registration_name": "Test Offspring 1",
            "birth_date": "2026-06-01",
            "gender": "F",
            "dam_id": "ca9e88d1-55fc-42b7-a3a8-4e8979148d21",
            "sire_id": "fa9e88d1-55fc-42b7-a3a8-4e8979148d22",
            "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
            "status": "Pre-Weaning Heifer"
        }
        response = client.post("/animals", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["dairy_blood_percentage"], 1.0000)

    def test_breeding_first_cousins_blocked(self):
        payload = {
            "animal_id": "aa1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
            "breeding_type": "AI",
            "semen_batch_code": "SEM-COUSIN-99",
            "insemination_date": "2026-06-01",
            "semen_sire_id": "ba2e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f"
        }
        response = client.post("/breeding", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Inbreeding risk", response.json()["detail"])

    def test_breeding_unrelated_animals_passed(self):
        payload = {
            "animal_id": "aa1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
            "breeding_type": "Natural Bull Service",
            "semen_batch_code": "SEM-OK-12",
            "insemination_date": "2026-06-01",
            "semen_sire_id": "fa9e88d1-55fc-42b7-a3a8-4e8979148d26"
        }
        response = client.post("/breeding", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["expected_calving_date"], "2027-04-07")

    def test_telemetry_growth_spoilage_low_temperature(self):
        payload = {
            "temp_log": [4.0, 4.0, 4.0],
            "time_log": [
                "2026-06-01T08:00:00Z",
                "2026-06-01T12:00:00Z",
                "2026-06-01T16:00:00Z"
            ],
            "initial_cfu": 1000.0
        }
        response = client.post("/telemetry", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "Normal")
        self.assertLess(data["final_cfu"], 2000.0)

    def test_telemetry_growth_spoilage_spike_temperature(self):
        payload = {
            "temp_log": [4.0, 15.0, 25.0, 35.0, 35.0, 35.0, 35.0, 35.0, 35.0, 35.0],
            "time_log": [
                "2026-06-01T08:00:00Z",
                "2026-06-01T09:00:00Z",
                "2026-06-01T10:00:00Z",
                "2026-06-01T11:00:00Z",
                "2026-06-01T12:00:00Z",
                "2026-06-01T13:00:00Z",
                "2026-06-01T14:00:00Z",
                "2026-06-01T15:00:00Z",
                "2026-06-01T16:00:00Z",
                "2026-06-01T17:00:00Z"
            ],
            "initial_cfu": 1000.0
        }
        response = client.post("/telemetry", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "High Risk")
        self.assertGreater(data["final_cfu"], 1.0e5)

    def test_create_and_chain_product_batches(self):
        batch1_payload = {
            "batch_identifier": "API-BATCH-001",
            "product_type": "Ice Cream",
            "quantity_units_produced": 500,
            "manufacture_date": "2026-06-01",
            "shelf_life_days": 180,
            "coliform_test_status": "Passed",
            "pasteurization_temp_celsius": 72.5
        }
        response = client.post("/batches", json=batch1_payload)
        self.assertEqual(response.status_code, 201)
        data1 = response.json()
        self.assertIn("cryptographic_signature", data1)
        self.assertEqual(data1["previous_batch_hash"], "0" * 64)

        batch2_payload = {
            "batch_identifier": "API-BATCH-002",
            "product_type": "Yogurt",
            "quantity_units_produced": 300,
            "manufacture_date": "2026-06-02",
            "shelf_life_days": 30,
            "coliform_test_status": "Passed",
            "pasteurization_temp_celsius": 73.0
        }
        response = client.post("/batches", json=batch2_payload)
        self.assertEqual(response.status_code, 201)
        data2 = response.json()
        self.assertIn("cryptographic_signature", data2)
        self.assertEqual(data2["previous_batch_hash"], data1["cryptographic_signature"])

    def test_field_portal_accessible_elements(self):
        for path in ("/", "/field"):
            response = client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/html", response.headers["content-type"])
            html_content = response.text
            self.assertIn("Field Technician Portal", html_content)
            self.assertIn("lang-select", html_content)
            self.assertIn("sync-indicator", html_content)
            self.assertIn("animal-form", html_content)
            self.assertIn("breeding-form", html_content)
            self.assertIn("playBeep", html_content)

    def test_dashboard_telemetry_elements(self):
        response = client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        html_content = response.text
        self.assertIn("Plant Operator Telemetry Dashboard", html_content)
        self.assertIn("canister-card", html_content)
        self.assertIn("disclosure-trigger", html_content)
        self.assertIn("details-panel", html_content)
        self.assertIn("growth-curve", html_content)

    def test_passport_validation_endpoints(self):
        response = client.get("/passport/INVALID-BATCH-ID")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Safety Passport Not Found", response.text)

        batch_payload = {
            "batch_identifier": "TEST-BATCH-PASSPORT",
            "product_type": "Yogurt",
            "quantity_units_produced": 250,
            "manufacture_date": "2026-06-01",
            "shelf_life_days": 14,
            "coliform_test_status": "Passed",
            "pasteurization_temp_celsius": 72.5
        }
        response = client.post("/batches", json=batch_payload)
        self.assertEqual(response.status_code, 201)

        response = client.get("/passport/TEST-BATCH-PASSPORT")
        self.assertEqual(response.status_code, 200)
        html_content = response.text
        self.assertIn("Dairy Safety Passport", html_content)
        self.assertIn("Yogurt", html_content)
        self.assertIn("72.5", html_content)
        self.assertIn("Passed", html_content)
        self.assertIn("Audit Cryptographic Signatures", html_content)

    def test_weather_telemetry_integration_live(self):
        payload = {
            "initial_cfu": 1000.0,
            "latitude": 7.118,
            "longitude": 124.843
        }
        response = client.post("/telemetry", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("final_cfu", data)
        self.assertIn("status", data)

        response_dash = client.get("/dashboard")
        self.assertEqual(response_dash.status_code, 200)
        self.assertIn("Plant Operator Telemetry Dashboard", response_dash.text)
        self.assertIn("Canister CAN-001 (Kabacan)", response_dash.text)

    def test_soil_suitability_integration_live(self):
        response = client.get("/api/soil-suitability?latitude=7.118&longitude=124.843")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["nearest_municipality"], "Kabacan")
        self.assertEqual(data["soil_texture"], "Clay Loam")
        self.assertIn("napier_grass", data["forage_suitability"])

if __name__ == '__main__':
    unittest.main()
