-- PostgreSQL Database Schema for Distributed Dairy Supply Chain and Logistics Tracker

-- Enable UUID extension if not enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table: cooperatives
CREATE TABLE cooperatives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    municipality VARCHAR(100) NOT NULL,
    representative_name VARCHAR(100),
    contact_number VARCHAR(50)
);

-- Table: animals
CREATE TABLE animals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ear_tag_number VARCHAR(50) UNIQUE NOT NULL,
    registration_name VARCHAR(100),
    birth_date DATE NOT NULL,
    gender CHAR(1) CHECK (gender IN ('M', 'F')),
    dairy_blood_percentage NUMERIC(5, 4) NOT NULL CHECK (dairy_blood_percentage BETWEEN 0.0000 AND 1.0000),
    dam_id UUID REFERENCES animals(id),
    sire_id UUID REFERENCES animals(id),
    cooperative_id UUID REFERENCES cooperatives(id),
    status VARCHAR(50) CHECK (status IN ('Gestating', 'Lactating', 'Dry', 'Pre-Weaning Heifer', 'Post-Weaning Heifer', 'Agistment')),
    vermicomposting_manure_yield_kg NUMERIC(6, 2) DEFAULT 0.00
);

-- Table: breeding_records
CREATE TABLE breeding_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    animal_id UUID REFERENCES animals(id) ON DELETE CASCADE,
    breeding_type VARCHAR(20) CHECK (breeding_type IN ('AI', 'Natural Bull Service')),
    semen_batch_code VARCHAR(100),
    insemination_date DATE NOT NULL,
    expected_calving_date DATE GENERATED ALWAYS AS (insemination_date + INTERVAL '310 days') STORED,
    actual_calving_date DATE,
    calving_outcome_gender CHAR(1) CHECK (calving_outcome_gender IN ('M', 'F')),
    repayment_due_date DATE GENERATED ALWAYS AS (actual_calving_date + INTERVAL '540 days') STORED,
    repayment_status VARCHAR(50) DEFAULT 'Pending' CHECK (repayment_status IN ('Pending', 'Returned', 'Waived', 'Delayed'))
);

-- Table: raw_milk_batches
CREATE TABLE raw_milk_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    volume_liters NUMERIC(8, 2) NOT NULL,
    batch_temperature_celsius NUMERIC(5, 2) NOT NULL,
    origin_municipality VARCHAR(100) NOT NULL,
    inventory_status VARCHAR(50) NOT NULL DEFAULT 'In-Storage' CHECK (inventory_status IN ('In-Storage', 'In-Processing', 'Processed')),
    processing_suitability VARCHAR(20) NOT NULL DEFAULT 'Pending' CHECK (processing_suitability IN ('Passed', 'Failed', 'Pending'))
);

-- Table: processing_pipeline_runs
CREATE TABLE processing_pipeline_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_type VARCHAR(50) NOT NULL CHECK (product_type IN ('Pasteurized Milk', 'Yogurt', 'Ice Cream')),
    total_volume_liters NUMERIC(8, 2) NOT NULL,
    start_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table: product_batches
CREATE TABLE product_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_identifier VARCHAR(100) UNIQUE NOT NULL,
    product_type VARCHAR(50) CHECK (product_type IN ('Pasteurized Milk', 'Yogurt', 'Ice Cream')),
    quantity_units_produced INT NOT NULL,
    manufacture_date DATE NOT NULL,
    shelf_life_days INT NOT NULL,
    expiry_date DATE GENERATED ALWAYS AS (manufacture_date + shelf_life_days * INTERVAL '1 day') STORED,
    coliform_test_status VARCHAR(20) CHECK (coliform_test_status IN ('Passed', 'Failed')),
    pasteurization_temp_celsius NUMERIC(5,2),
    previous_batch_hash VARCHAR(64) NOT NULL,
    cryptographic_signature VARCHAR(64) UNIQUE NOT NULL
);

-- Table: feeding_allocations
CREATE TABLE feeding_allocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_agency VARCHAR(10) CHECK (recipient_agency IN ('DepEd', 'DSWD')),
    school_or_center_name VARCHAR(255) NOT NULL,
    target_municipality VARCHAR(100) NOT NULL,
    allocation_date TIMESTAMP WITH TIME ZONE NOT NULL,
    delivery_status VARCHAR(50) DEFAULT 'Pending' CHECK (delivery_status IN ('Pending', 'In-Transit', 'Delivered', 'Rejected'))
);

-- Table: batch_allocation_mapping
CREATE TABLE batch_allocation_mapping (
    batch_id UUID REFERENCES product_batches(id),
    allocation_id UUID REFERENCES feeding_allocations(id),
    units_delivered INT NOT NULL,
    PRIMARY KEY (batch_id, allocation_id)
);

-- Table: database_quality_metrics
CREATE TABLE database_quality_metrics (
    id SERIAL PRIMARY KEY,
    log_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    active_connections INT NOT NULL,
    transaction_rollback_count INT NOT NULL,
    deadlock_events_count INT NOT NULL,
    average_query_execution_time_ms NUMERIC(8,2) NOT NULL
);
