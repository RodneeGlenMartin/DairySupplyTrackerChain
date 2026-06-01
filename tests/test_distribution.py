import unittest
from src.distribution import generate_batch_hash, verify_batch_chain

class TestDistribution(unittest.TestCase):
    
    def setUp(self):
        # Setup mock data for a sequence of 3 batches
        self.batch1 = {
            "previous_hash": "0" * 64,
            "batch_identifier": "BATCH-20260601-001",
            "volume": 250.50,
            "pasteur_temp": 72.50,
            "coliform_status": "Passed",
            "timestamp": "2026-06-01T08:00:00Z"
        }
        self.batch1["cryptographic_signature"] = generate_batch_hash(
            previous_hash=self.batch1["previous_hash"],
            batch_identifier=self.batch1["batch_identifier"],
            volume=self.batch1["volume"],
            pasteur_temp=self.batch1["pasteur_temp"],
            coliform_status=self.batch1["coliform_status"],
            timestamp=self.batch1["timestamp"]
        )

        self.batch2 = {
            "previous_hash": self.batch1["cryptographic_signature"],
            "batch_identifier": "BATCH-20260601-002",
            "volume": 300.00,
            "pasteur_temp": 73.00,
            "coliform_status": "Passed",
            "timestamp": "2026-06-01T09:00:00Z"
        }
        self.batch2["cryptographic_signature"] = generate_batch_hash(
            previous_hash=self.batch2["previous_hash"],
            batch_identifier=self.batch2["batch_identifier"],
            volume=self.batch2["volume"],
            pasteur_temp=self.batch2["pasteur_temp"],
            coliform_status=self.batch2["coliform_status"],
            timestamp=self.batch2["timestamp"]
        )

        self.batch3 = {
            "previous_hash": self.batch2["cryptographic_signature"],
            "batch_identifier": "BATCH-20260601-003",
            "volume": 180.25,
            "pasteur_temp": 72.00,
            "coliform_status": "Passed",
            "timestamp": "2026-06-01T10:00:00Z"
        }
        self.batch3["cryptographic_signature"] = generate_batch_hash(
            previous_hash=self.batch3["previous_hash"],
            batch_identifier=self.batch3["batch_identifier"],
            volume=self.batch3["volume"],
            pasteur_temp=self.batch3["pasteur_temp"],
            coliform_status=self.batch3["coliform_status"],
            timestamp=self.batch3["timestamp"]
        )
        
        self.chain = [self.batch1, self.batch2, self.batch3]

    def test_valid_chain_verification(self):
        # Verify that a clean chain passes verification
        self.assertTrue(verify_batch_chain(self.chain))

    def test_tampered_volume_fails(self):
        # Tamper with the volume of batch 2
        tampered_chain = [self.batch1.copy(), self.batch2.copy(), self.batch3.copy()]
        tampered_chain[1]["volume"] = 300.01 # subtle change
        self.assertFalse(verify_batch_chain(tampered_chain))

    def test_tampered_coliform_status_fails(self):
        # Tamper with the coliform status of batch 1
        tampered_chain = [self.batch1.copy(), self.batch2.copy(), self.batch3.copy()]
        tampered_chain[0]["coliform_status"] = "Failed"
        self.assertFalse(verify_batch_chain(tampered_chain))

    def test_broken_link_fails(self):
        # Tamper with the linkage (change previous_hash of batch 3)
        tampered_chain = [self.batch1.copy(), self.batch2.copy(), self.batch3.copy()]
        tampered_chain[2]["previous_hash"] = "a" * 64
        # Since previous_hash changed, recalculate the signature or test directly
        # The chain integrity check verifies signature matches and link matches.
        # If we change previous_hash but don't change signature, signature verification itself will fail.
        # If we change previous_hash and also change the signature to match the new previous_hash:
        # the previous_hash won't match batch 2's signature, failing the link check.
        self.assertFalse(verify_batch_chain(tampered_chain))
        
        # Test recalculating the signature for the tampered link (the link check must fail)
        tampered_chain[2]["cryptographic_signature"] = generate_batch_hash(
            previous_hash=tampered_chain[2]["previous_hash"],
            batch_identifier=tampered_chain[2]["batch_identifier"],
            volume=tampered_chain[2]["volume"],
            pasteur_temp=tampered_chain[2]["pasteur_temp"],
            coliform_status=tampered_chain[2]["coliform_status"],
            timestamp=tampered_chain[2]["timestamp"]
        )
        self.assertFalse(verify_batch_chain(tampered_chain))

if __name__ == '__main__':
    unittest.main()
