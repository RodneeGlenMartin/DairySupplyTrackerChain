import unittest
import psycopg2
import psycopg2.extensions
import psycopg2.errors
import time
from src.config import DATABASE_URL

class DairyProcessingCoordinator:
    """Service class executing real db transactions."""
    def __init__(self, conn):
        self.conn = conn

    def allocate_raw_milk_batch(self, origin_municipality: str, product_type: str, volume: float) -> bool:
        cursor = self.conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;")
            
            # Step 1: lock rows
            cursor.execute(
                "SELECT id, volume_liters FROM raw_milk_batches WHERE origin_municipality = %s AND inventory_status = 'In-Storage' FOR UPDATE;",
                (origin_municipality,)
            )
            
            # Step 2: insert pipeline run
            cursor.execute(
                "INSERT INTO processing_pipeline_runs (run_id, product_type, total_volume_liters) VALUES (gen_random_uuid(), %s, %s);",
                (product_type, volume)
            )
            
            # Step 3: update raw milk batch status
            cursor.execute(
                "UPDATE raw_milk_batches SET inventory_status = 'In-Processing' WHERE origin_municipality = %s AND inventory_status = 'In-Storage';",
                (origin_municipality,)
            )
            
            self.conn.commit()
            return True
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            raise e
        finally:
            cursor.close()

class DairyProcessingCoordinatorWithChaos(DairyProcessingCoordinator):
    def __init__(self, conn, fail_point=None):
        super().__init__(conn)
        self.fail_point = fail_point

    def allocate_raw_milk_batch(self, origin_municipality: str, product_type: str, volume: float) -> bool:
        cursor = self.conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;")
            
            if self.fail_point == "before_lock":
                self.conn.close()
            
            cursor.execute(
                "SELECT id, volume_liters FROM raw_milk_batches WHERE origin_municipality = %s AND inventory_status = 'In-Storage' FOR UPDATE;",
                (origin_municipality,)
            )
            
            cursor.execute(
                "INSERT INTO processing_pipeline_runs (run_id, product_type, total_volume_liters) VALUES (gen_random_uuid(), %s, %s);",
                (product_type, volume)
            )
            
            if self.fail_point == "before_update":
                self.conn.close()
                
            cursor.execute(
                "UPDATE raw_milk_batches SET inventory_status = 'In-Processing' WHERE origin_municipality = %s AND inventory_status = 'In-Storage';",
                (origin_municipality,)
            )
            
            self.conn.commit()
            return True
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            raise e
        finally:
            try:
                cursor.close()
            except Exception:
                pass

class TestChaosResilience(unittest.TestCase):
    
    def setUp(self):
        self.conn = psycopg2.connect(DATABASE_URL)
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM processing_pipeline_runs WHERE product_type = 'Ice Cream';")
        cursor.execute("DELETE FROM raw_milk_batches WHERE origin_municipality = 'ChaosMidsayap';")
        cursor.execute(
            """
            INSERT INTO raw_milk_batches (id, volume_liters, batch_temperature_celsius, origin_municipality, inventory_status, processing_suitability)
            VALUES ('d1a766a7-0cfc-4034-8c63-6b3a0f7c22df', 500.00, 4.20, 'ChaosMidsayap', 'In-Storage', 'Passed');
            """
        )
        self.conn.commit()
        cursor.close()

    def tearDown(self):
        if hasattr(self, 'conn') and self.conn:
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM processing_pipeline_runs WHERE product_type = 'Ice Cream';")
                cursor.execute("DELETE FROM raw_milk_batches WHERE origin_municipality = 'ChaosMidsayap';")
                self.conn.commit()
                cursor.close()
            except Exception:
                pass
            try:
                self.conn.close()
            except Exception:
                pass

    def test_successful_transaction_execution(self):
        coordinator = DairyProcessingCoordinator(self.conn)
        result = coordinator.allocate_raw_milk_batch("ChaosMidsayap", "Ice Cream", 450.0)
        self.assertTrue(result)
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT inventory_status FROM raw_milk_batches WHERE origin_municipality = 'ChaosMidsayap';")
        status = cursor.fetchone()[0]
        self.assertEqual(status, 'In-Processing')
        cursor.close()

    def test_database_connection_failure_during_update_triggers_rollback(self):
        coordinator = DairyProcessingCoordinatorWithChaos(self.conn, fail_point="before_update")
        
        with self.assertRaises((psycopg2.InterfaceError, psycopg2.OperationalError)):
            coordinator.allocate_raw_milk_batch("ChaosMidsayap", "Ice Cream", 450.0)
            
        verify_conn = psycopg2.connect(DATABASE_URL)
        cursor = verify_conn.cursor()
        cursor.execute("SELECT inventory_status FROM raw_milk_batches WHERE origin_municipality = 'ChaosMidsayap';")
        status = cursor.fetchone()[0]
        self.assertEqual(status, 'In-Storage')
        cursor.close()
        verify_conn.close()

    def test_high_latency_causes_timeout_and_rollback(self):
        cursor = self.conn.cursor()
        cursor.execute("SET statement_timeout = 500;")
        self.conn.commit()
        cursor.close()
        
        class TimeoutCoordinator(DairyProcessingCoordinator):
            def allocate_raw_milk_batch(self, origin_municipality: str, product_type: str, volume: float) -> bool:
                cursor = self.conn.cursor()
                try:
                    cursor.execute("BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;")
                    cursor.execute("SELECT pg_sleep(1.0);")
                    cursor.execute(
                        "SELECT id, volume_liters FROM raw_milk_batches WHERE origin_municipality = %s AND inventory_status = 'In-Storage' FOR UPDATE;",
                        (origin_municipality,)
                    )
                    self.conn.commit()
                    return True
                except Exception as e:
                    self.conn.rollback()
                    raise e
                finally:
                    cursor.close()

        coordinator = TimeoutCoordinator(self.conn)
        with self.assertRaises(psycopg2.extensions.QueryCanceledError):
            coordinator.allocate_raw_milk_batch("ChaosMidsayap", "Ice Cream", 450.0)

        cursor = self.conn.cursor()
        cursor.execute("RESET statement_timeout;")
        cursor.execute("SELECT inventory_status FROM raw_milk_batches WHERE origin_municipality = 'ChaosMidsayap';")
        status = cursor.fetchone()[0]
        self.assertEqual(status, 'In-Storage')
        cursor.close()

    def test_failure_on_lock_acquisition_triggers_rollback(self):
        lock_conn = psycopg2.connect(DATABASE_URL)
        lock_cursor = lock_conn.cursor()
        lock_cursor.execute("BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;")
        lock_cursor.execute(
            "SELECT id FROM raw_milk_batches WHERE origin_municipality = %s FOR UPDATE;",
            ("ChaosMidsayap",)
        )

        class NoWaitCoordinator(DairyProcessingCoordinator):
            def allocate_raw_milk_batch(self, origin_municipality: str, product_type: str, volume: float) -> bool:
                cursor = self.conn.cursor()
                try:
                    cursor.execute("BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;")
                    cursor.execute(
                        "SELECT id, volume_liters FROM raw_milk_batches WHERE origin_municipality = %s AND inventory_status = 'In-Storage' FOR UPDATE NOWAIT;",
                        (origin_municipality,)
                    )
                    self.conn.commit()
                    return True
                except Exception as e:
                    self.conn.rollback()
                    raise e
                finally:
                    cursor.close()

        coordinator = NoWaitCoordinator(self.conn)
        with self.assertRaises(psycopg2.errors.LockNotAvailable):
            coordinator.allocate_raw_milk_batch("ChaosMidsayap", "Ice Cream", 450.0)

        lock_conn.rollback()
        lock_cursor.close()
        lock_conn.close()

        cursor = self.conn.cursor()
        cursor.execute("SELECT inventory_status FROM raw_milk_batches WHERE origin_municipality = 'ChaosMidsayap';")
        status = cursor.fetchone()[0]
        self.assertEqual(status, 'In-Storage')
        cursor.close()

if __name__ == '__main__':
    unittest.main()
