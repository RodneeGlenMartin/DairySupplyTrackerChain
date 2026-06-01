import unittest
from datetime import datetime, timedelta
import math
from src.coldchain import predict_microbial_growth, evaluate_batch_spoilage_risk

class TestColdChain(unittest.TestCase):
    
    def test_constant_reference_temperature_growth(self):
        # At 4°C (277.15 Kelvin), growth rate should be exactly mu_ref = 0.05 hours^-1
        # If we run for 24 hours, cumulative exponent log_ratio = 0.05 * 24 = 1.20
        # Expected final CFU = 1000 * exp(1.2) = 1000 * 3.3201169 = 3320.1169...
        
        initial_cfu = 1000.0
        start_time = datetime(2026, 6, 1, 0, 0, 0)
        time_log = [start_time + timedelta(hours=i) for i in range(25)] # 24 hourly intervals
        temp_log = [4.0] * 25 # constant 4.0 Celsius
        
        predicted_cfu = predict_microbial_growth(temp_log, time_log, initial_cfu)
        expected_cfu = initial_cfu * math.exp(0.05 * 24.0)
        
        self.assertAlmostEqual(predicted_cfu, expected_cfu, places=3)
        
        # Verify status is Normal since it is below 1.0e5 threshold
        cfu, status = evaluate_batch_spoilage_risk(temp_log, time_log, initial_cfu)
        self.assertEqual(status, "Normal")
        self.assertEqual(cfu, predicted_cfu)

    def test_temperature_spike_high_risk_flagging(self):
        # Scenario where milk canister is left in the Cotabato sun, spiking to 35°C
        initial_cfu = 1000.0
        start_time = datetime(2026, 6, 1, 10, 0, 0)
        
        # Spiking profile over 9 hours: 4C, 15C, 25C, 35C, 35C, 35C, 35C, 35C, 35C, 35C
        temp_log = [4.0, 15.0, 25.0, 35.0, 35.0, 35.0, 35.0, 35.0, 35.0, 35.0]
        time_log = [start_time + timedelta(hours=i) for i in range(10)]
        
        predicted_cfu, status = evaluate_batch_spoilage_risk(temp_log, time_log, initial_cfu)
        
        # Verify bacterial load has spiked and is marked High Risk (should easily exceed 1.0e5 CFU/ml)
        self.assertGreater(predicted_cfu, 1.0e5)
        self.assertEqual(status, "High Risk")

    def test_invalid_log_lengths(self):
        with self.assertRaises(ValueError):
            predict_microbial_growth([4.0, 5.0], [datetime.now()])

if __name__ == '__main__':
    unittest.main()
