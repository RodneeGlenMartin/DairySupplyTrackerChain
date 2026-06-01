import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from datetime import datetime, date, timedelta
from src.app import app

client = TestClient(app)

class TestDairyTrackerAPI(unittest.TestCase):

    def test_healthz_endpoint(self):
        response = client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertIn("timestamp", response.json())

    def test_register_animal_without_parents(self):
        # Register a base dam with 80% blood
        payload = {
            "ear_tag_number": "TAG-TEST-DAM-1",
            "registration_name": "Test Dam 1",
            "birth_date": "2024-01-01",
            "gender": "F",
            "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
            "status": "Dry"
        }
        # In-memory default for sire (1.0) and dam (0.0) since dam_id/sire_id are None
        response = client.post("/animals", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["ear_tag_number"], "TAG-TEST-DAM-1")
        # Default backcrossing fraction when parent IDs are omitted
        self.assertEqual(data["dairy_blood_percentage"], 0.5000)

    def test_register_animal_with_seeded_parents(self):
        # GP_DAM is ca9e88d1-55fc-42b7-a3a8-4e8979148d21 (100% dairy)
        # GP_SIRE is fa9e88d1-55fc-42b7-a3a8-4e8979148d22 (100% dairy)
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
        # Cousin A: aa1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f
        # Cousin B: ba2e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f
        # Relationship R is 0.125 >= 0.0625, should raise 400 Bad Request
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
        # Cousin A: aa1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f
        # Sire TAG-SIRE-A: fa9e88d1-55fc-42b7-a3a8-4e8979148d25 (is A's sire, R=0.5 -> blocked)
        # Sire TAG-SIRE-B: fa9e88d1-55fc-42b7-a3a8-4e8979148d26 (unrelated to Cousin A, R=0.0 -> passed)
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
        self.assertEqual(data["expected_calving_date"], "2027-04-07") # 2026-06-01 + 310 days

    def test_telemetry_growth_spoilage_low_temperature(self):
        # Spoilage check at 4C constant (Normal)
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
        # Spoilage check with a heat exposure spike to 35C (High Risk)
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
        # Create Batch 1 (Genesis)
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

        # Create Batch 2 (Chained to Batch 1)
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
        # Should link back to Batch 1 signature
        self.assertEqual(data2["previous_batch_hash"], data1["cryptographic_signature"])

    @patch("src.app.DISABLE_IN_MEMORY_FALLBACK", True)
    @patch("src.app.DATABASE_URL", "postgresql://invalid_host:5432/invalid_db")
    def test_disable_in_memory_fallback_enforcement(self):
        # When fallback is disabled and database connection fails,
        # calls should fail and raise RuntimeError
        payload = {
            "ear_tag_number": "TAG-TEST-FAILBACK-1",
            "registration_name": "Test Failback 1",
            "birth_date": "2026-06-01",
            "gender": "F",
            "cooperative_id": "3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df",
            "status": "Dry"
        }
        with self.assertRaises(RuntimeError):
            client.post("/animals", json=payload)

    def test_field_portal_accessible_elements(self):
        # Verify /field endpoint returns HTML and accessibility hooks
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
        # Verify /dashboard endpoint returns telemetry dashboard elements
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
        # Verify passport 404 for missing batches
        response = client.get("/passport/INVALID-BATCH-ID")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Safety Passport Not Found", response.text)

        # Seed a dummy batch in IN_MEMORY_PRODUCT_BATCHES to verify 200 OK rendering
        from src.app import IN_MEMORY_PRODUCT_BATCHES
        mock_batch = {
            "id": "test-uuid-9999",
            "batch_identifier": "TEST-BATCH-PASSPORT",
            "product_type": "Yogurt",
            "quantity_units_produced": 250,
            "manufacture_date": date(2026, 6, 1),
            "shelf_life_days": 14,
            "expiry_date": date(2026, 6, 15),
            "coliform_test_status": "Passed",
            "pasteurization_temp_celsius": 72.5,
            "previous_batch_hash": "0" * 64,
            "cryptographic_signature": "a" * 64
        }
        IN_MEMORY_PRODUCT_BATCHES.append(mock_batch)

        # Retrieve and verify passport
        response = client.get("/passport/TEST-BATCH-PASSPORT")
        self.assertEqual(response.status_code, 200)
        html_content = response.text
        self.assertIn("Dairy Safety Passport", html_content)
        self.assertIn("Yogurt", html_content)
        self.assertIn("72.5", html_content)
        self.assertIn("Passed", html_content)
        self.assertIn("Audit Cryptographic Signatures", html_content)

    @patch("httpx.AsyncClient.get", new_callable=unittest.mock.AsyncMock)
    def test_weather_telemetry_integration_mocked(self, mock_get):
        class MockResponse:
            def __init__(self, json_data, status_code):
                self.json_data = json_data
                self.status_code = status_code
            def json(self):
                return self.json_data
        
        mock_weather_data = {
            "hourly": {
                "time": [f"2026-06-01T{i:02d}:00" for i in range(48)],
                "temperature_2m": [4.0 + (i % 2) for i in range(48)]
            }
        }
        mock_get.return_value = MockResponse(mock_weather_data, 200)

        # Call process_telemetry endpoint with coordinates
        payload = {
            "initial_cfu": 1000.0,
            "latitude": 7.118,
            "longitude": 124.843
        }
        response = client.post("/telemetry", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("final_cfu", data)
        self.assertEqual(data["status"], "Normal")

        # Call get_dashboard_portal and verify it renders
        response_dash = client.get("/dashboard")
        self.assertEqual(response_dash.status_code, 200)
        self.assertIn("Plant Operator Telemetry Dashboard", response_dash.text)
        self.assertIn("Canister CAN-001 (Kabacan)", response_dash.text)

    @patch("httpx.AsyncClient.get", new_callable=unittest.mock.AsyncMock)
    def test_soil_suitability_integration_mocked(self, mock_get):
        class MockResponse:
            def __init__(self, json_data, status_code):
                self.json_data = json_data
                self.status_code = status_code
            def json(self):
                return self.json_data

        mock_soil_data = {
            "hourly": {
                "soil_temperature_0_to_7cm": [27.0] * 24,
                "soil_moisture_0_to_7cm": [0.25] * 24
            }
        }
        mock_get.return_value = MockResponse(mock_soil_data, 200)

        # Call get_soil_suitability
        response = client.get("/api/soil-suitability?latitude=7.118&longitude=124.843")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["nearest_municipality"], "Kabacan")
        self.assertEqual(data["soil_texture"], "Clay Loam")
        self.assertEqual(data["forage_suitability"]["napier_grass"], "High")

    @patch("httpx.AsyncClient.get", new_callable=unittest.mock.AsyncMock)
    def test_external_api_network_timeout_fallback(self, mock_get):
        import httpx
        mock_get.side_effect = httpx.ConnectTimeout("Connection timed out")

        # 1. Test soil suitability fallback
        response = client.get("/api/soil-suitability?latitude=7.118&longitude=124.843")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["soil_temperature_celsius"], 26.5)
        self.assertEqual(data["soil_moisture_m3_m3"], 0.220)

        # 2. Test dashboard weather fallback
        response_dash = client.get("/dashboard")
        self.assertEqual(response_dash.status_code, 200)
        self.assertIn("Plant Operator Telemetry Dashboard", response_dash.text)

if __name__ == '__main__':
    import unittest.mock
    unittest.main()

