import unittest
from datetime import datetime, date
from src.genetics import (
    calculate_genetic_blood_fraction,
    calculate_relationship_coefficient,
    calculate_repayment_due_date
)

class TestGenetics(unittest.TestCase):
    
    def test_genetic_backcrossing_calculation(self):
        # Base case: purebred sire (1.0) and dam with 50% dairy blood (0.5)
        # Expected: (1.0 + 0.5) / 2 = 0.75
        self.assertEqual(calculate_genetic_blood_fraction(1.0, 0.5), 0.75)
        
        # S_n = 1.0 (purebred) and D_n-1 = 0.75
        # Expected: (1.0 + 0.75) / 2 = 0.8750
        self.assertEqual(calculate_genetic_blood_fraction(1.0, 0.75), 0.875)

        # Border conditions
        self.assertEqual(calculate_genetic_blood_fraction(0.0, 0.0), 0.0)
        self.assertEqual(calculate_genetic_blood_fraction(1.0, 1.0), 1.0)

        # Invalid bounds checks
        with self.assertRaises(ValueError):
            calculate_genetic_blood_fraction(-0.1, 0.5)
        with self.assertRaises(ValueError):
            calculate_genetic_blood_fraction(1.0, 1.5)

    def test_repayment_date_calculation(self):
        # 18 months repayment window corresponds to exactly 540 days post actual calving date
        calving_date = date(2026, 1, 26)
        expected_repayment = date(2027, 7, 20)
        self.assertEqual(calculate_repayment_due_date(calving_date), expected_repayment)
        
        # Test datetime object
        calving_datetime = datetime(2026, 1, 26, 12, 0, 0)
        self.assertEqual(calculate_repayment_due_date(calving_datetime).date(), expected_repayment)

        # Test string parsing
        self.assertEqual(calculate_repayment_due_date("2026-01-26"), expected_repayment)
        self.assertEqual(calculate_repayment_due_date("2026-01-26 12:00:00"), expected_repayment)

    def test_relationship_coefficient_scenarios(self):
        # We construct a pedigree dictionary mapping animal_id to {'dam_id': ..., 'sire_id': ...}
        # Unrelated case
        pedigree_unrelated = {
            "A": {"dam_id": "D1", "sire_id": "S1"},
            "B": {"dam_id": "D2", "sire_id": "S2"}
        }
        R_unrelated = calculate_relationship_coefficient("A", "B", pedigree_unrelated)
        self.assertEqual(R_unrelated, 0.0)

        # Full Siblings: share same Sire (S) and Dam (D)
        # R should be: (0.5)^(1+1) + (0.5)^(1+1) = 0.25 + 0.25 = 0.5
        pedigree_siblings = {
            "A": {"dam_id": "D", "sire_id": "S"},
            "B": {"dam_id": "D", "sire_id": "S"}
        }
        with self.assertRaises(ValueError):
            calculate_relationship_coefficient("A", "B", pedigree_siblings)

        # Half Siblings: share same Sire (S), different Dams (D1 and D2)
        # R should be: (0.5)^(1+1) = 0.25
        pedigree_half_siblings = {
            "A": {"dam_id": "D1", "sire_id": "S"},
            "B": {"dam_id": "D2", "sire_id": "S"}
        }
        with self.assertRaises(ValueError):
            calculate_relationship_coefficient("A", "B", pedigree_half_siblings)

        # First Cousins: A's parents are D1 and S1, B's parents are D2 and S2.
        # D1 and D2 are full sisters sharing GP_D and GP_S.
        # Sire S1 and Sire S2 are unrelated.
        # R should be: through GP_D: (0.5)^(2+2) = 0.0625. Through GP_S: (0.5)^(2+2) = 0.0625.
        # Total R = 0.125
        pedigree_cousins = {
            "A": {"dam_id": "D1", "sire_id": "S1"},
            "B": {"dam_id": "D2", "sire_id": "S2"},
            "D1": {"dam_id": "GP_D", "sire_id": "GP_S"},
            "D2": {"dam_id": "GP_D", "sire_id": "GP_S"}
        }
        with self.assertRaises(ValueError):
            calculate_relationship_coefficient("A", "B", pedigree_cousins)

        # Half Cousins: A and B share exactly one grandparent (GP)
        # R should be: (0.5)^(2+2) = 0.0625 (exactly the threshold)
        pedigree_half_cousins = {
            "A": {"dam_id": "D1", "sire_id": "S1"},
            "B": {"dam_id": "D2", "sire_id": "S2"},
            "D1": {"dam_id": "GP", "sire_id": "S_unrelated_1"},
            "D2": {"dam_id": "GP", "sire_id": "S_unrelated_2"}
        }
        with self.assertRaises(ValueError):
            # Half-cousin breeding is exactly 0.0625, raising error to prevent inbreeding
            calculate_relationship_coefficient("A", "B", pedigree_half_cousins)

        # Second Cousins: share great-grandparents GGP_D and GGP_S
        # Distance from A to GGP is 3 generations (A -> D1 -> GD1 -> GGP)
        # Distance from B to GGP is 3 generations (B -> D2 -> GD2 -> GGP)
        # Contribution per GGP: (0.5)^(3+3) = 0.015625
        # For two GGPs: 2 * 0.015625 = 0.03125
        # Since R = 0.03125 is < 0.0625, this should be allowed
        pedigree_second_cousins = {
            "A": {"dam_id": "D1", "sire_id": "S1"},
            "B": {"dam_id": "D2", "sire_id": "S2"},
            "D1": {"dam_id": "GD1", "sire_id": "GS1"},
            "D2": {"dam_id": "GD2", "sire_id": "GS2"},
            "GD1": {"dam_id": "GGP_D", "sire_id": "GGP_S"},
            "GD2": {"dam_id": "GGP_D", "sire_id": "GGP_S"}
        }
        R_second_cousins = calculate_relationship_coefficient("A", "B", pedigree_second_cousins)
        self.assertEqual(R_second_cousins, 0.03125)

if __name__ == '__main__':
    unittest.main()
