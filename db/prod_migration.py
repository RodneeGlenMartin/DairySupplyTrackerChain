#!/usr/bin/env python
import os
import sys
import psycopg2

# Ensure project root is in the import path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src.config import DATABASE_URL
except ImportError:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/dairy_supplychain")

def run_migrations():
    schema_path = os.path.join(script_dir, "schema.sql")
    
    print("==================================================")
    print("Starting Production Database Schema Migration...")
    print(f"Schema file: {schema_path}")
    
    # Hide password in connection string when printing for security
    from urllib.parse import urlparse
    try:
        parsed = urlparse(DATABASE_URL)
        connection_print = f"postgresql://{parsed.username}:****@{parsed.hostname}:{parsed.port}/{parsed.path.lstrip('/')}"
    except Exception:
        connection_print = "postgresql://****:****@****/****"
    print(f"Target Database: {connection_print}")
    print("==================================================")
    
    if not os.path.exists(schema_path):
        print(f"ERROR: Schema file not found at {schema_path}")
        sys.exit(1)
        
    try:
        print("Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
        conn.autocommit = False # Use explicit transactions
        cursor = conn.cursor()
        
        print("Reading schema definition...")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_ddl = f.read()
            
        print("Executing DDL updates...")
        cursor.execute(schema_ddl)
        
        # Verify created tables
        print("Verifying applied database schema tables...")
        cursor.execute(
            """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND table_type = 'BASE TABLE'
            ORDER BY table_name;
            """
        )
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = {
            "cooperatives", "animals", "breeding_records", "raw_milk_batches",
            "processing_pipeline_runs", "product_batches", "feeding_allocations",
            "batch_allocation_mapping", "database_quality_metrics"
        }
        
        print("\nVerified Tables in 'public' schema:")
        for t in tables:
            status = " [OK]" if t in expected_tables else ""
            print(f"  - {t}{status}")
            
        # Check if all expected tables exist
        missing_tables = expected_tables - set(tables)
        if missing_tables:
            print(f"\nWARNING: Some expected tables were not found: {missing_tables}")
            print("Rolling back DDL changes.")
            conn.rollback()
            sys.exit(1)
        else:
            print("\nAll expected schema tables successfully created.")
            conn.commit()
            print("DDL Migration completed and transaction committed successfully.")
            
        cursor.close()
        conn.close()
        
    except psycopg2.OperationalError as op_err:
        print(f"\nCONNECTION ERROR: Could not connect to database: {op_err}")
        print("Please ensure your DATABASE_URL environment variable is correct and the server is running.")
        sys.exit(1)
    except Exception as err:
        print(f"\nMIGRATION ERROR: Schema application failed: {err}")
        sys.exit(1)

if __name__ == "__main__":
    run_migrations()
