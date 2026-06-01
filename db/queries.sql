-- Concurrency Control and Transaction Isolation Queries

-- Transaction to allocate raw milk batches to the processing line
-- This uses SERIALIZABLE transaction isolation and row-level locking (FOR UPDATE)
-- to prevent race conditions during concurrent morning collections.

BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;

-- 1. Query and lock specific raw milk inventory records for processing
SELECT id, volume_liters, batch_temperature_celsius, inventory_status
FROM raw_milk_batches
WHERE origin_municipality = 'Midsayap' 
  AND inventory_status = 'In-Storage'
  AND processing_suitability = 'Passed'
FOR UPDATE;

-- 2. Record the pipeline run run parameters and allocation details
INSERT INTO processing_pipeline_runs (run_id, product_type, total_volume_liters, start_timestamp)
VALUES (gen_random_uuid(), 'Ice Cream', 450.0, CURRENT_TIMESTAMP);

-- 3. Update the matching raw milk batches inventory status to reflect their allocation
UPDATE raw_milk_batches
SET inventory_status = 'In-Processing'
WHERE origin_municipality = 'Midsayap' 
  AND inventory_status = 'In-Storage'
  AND processing_suitability = 'Passed';

COMMIT;
