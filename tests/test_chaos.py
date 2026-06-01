import unittest
from unittest.mock import Mock, patch
import time

class DatabaseConnectionError(Exception):
    """Simulated database connection exception."""
    pass

class DatabaseTransactionTimeout(Exception):
    """Simulated database transaction timeout exception."""
    pass

class MockDatabaseSession:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.query_log = []
        self.fail_on_query = None
        self.latency_on_query = 0.0

    def execute(self, query, params=None):
        if self.latency_on_query > 0.0:
            # Simulate network latency
            time.sleep(self.latency_on_query)
            if self.latency_on_query > 1.0: # threshold for mock timeout
                raise DatabaseTransactionTimeout("Transaction timed out due to high latency.")
                
        if self.fail_on_query and self.fail_on_query in query:
            raise DatabaseConnectionError("Lost connection to the database host.")
            
        self.query_log.append((query, params))

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class DairyProcessingCoordinator:
    """Simulates a service class executing db transactions."""
    def __init__(self, db_session):
        self.db = db_session

    def allocate_raw_milk_batch(self, origin_municipality: str, product_type: str, volume: float) -> bool:
        try:
            self.db.execute("BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;")
            
            # Step 1: lock rows
            self.db.execute(
                "SELECT id, volume_liters FROM raw_milk_batches WHERE origin_municipality = %s AND inventory_status = 'In-Storage' FOR UPDATE;",
                (origin_municipality,)
            )
            
            # Step 2: insert pipeline run
            self.db.execute(
                "INSERT INTO processing_pipeline_runs (run_id, product_type, total_volume_liters) VALUES (gen_random_uuid(), %s, %s);",
                (product_type, volume)
            )
            
            # Step 3: update raw milk batch status
            self.db.execute(
                "UPDATE raw_milk_batches SET inventory_status = 'In-Processing' WHERE origin_municipality = %s AND inventory_status = 'In-Storage';",
                (origin_municipality,)
            )
            
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            # Re-raise to allow the test to inspect the error
            raise e


class TestChaosResilience(unittest.TestCase):
    
    def test_successful_transaction_execution(self):
        session = MockDatabaseSession()
        coordinator = DairyProcessingCoordinator(session)
        
        result = coordinator.allocate_raw_milk_batch("Midsayap", "Ice Cream", 450.0)
        
        self.assertTrue(result)
        self.assertTrue(session.committed)
        self.assertFalse(session.rolled_back)
        self.assertEqual(len(session.query_log), 4) # BEGIN + SELECT + INSERT + UPDATE

    def test_database_connection_failure_during_update_triggers_rollback(self):
        session = MockDatabaseSession()
        # Inject connection failure during UPDATE query
        session.fail_on_query = "UPDATE raw_milk_batches"
        coordinator = DairyProcessingCoordinator(session)
        
        with self.assertRaises(DatabaseConnectionError):
            coordinator.allocate_raw_milk_batch("Midsayap", "Ice Cream", 450.0)
            
        # Verify that commit was NOT called, and rollback WAS called
        self.assertFalse(session.committed)
        self.assertTrue(session.rolled_back)

    def test_high_latency_causes_timeout_and_rollback(self):
        session = MockDatabaseSession()
        # Inject high latency (e.g. 1.5 seconds)
        session.latency_on_query = 1.1
        coordinator = DairyProcessingCoordinator(session)
        
        with self.assertRaises(DatabaseTransactionTimeout):
            coordinator.allocate_raw_milk_batch("Midsayap", "Ice Cream", 450.0)
            
        # Verify transaction rolled back cleanly
        self.assertFalse(session.committed)
        self.assertTrue(session.rolled_back)

    def test_failure_on_lock_acquisition_triggers_rollback(self):
        session = MockDatabaseSession()
        # Inject failure on lock select (e.g., deadlock or connection loss)
        session.fail_on_query = "SELECT id, volume_liters"
        coordinator = DairyProcessingCoordinator(session)
        
        with self.assertRaises(DatabaseConnectionError):
            coordinator.allocate_raw_milk_batch("Midsayap", "Ice Cream", 450.0)
            
        # Verify rollback occurred immediately
        self.assertFalse(session.committed)
        self.assertTrue(session.rolled_back)

if __name__ == '__main__':
    unittest.main()
