-- SQL Script to Seed the Dairy Supply Chain Database

-- 1. Seed Cooperatives across Cotabato and Region 12
INSERT INTO cooperatives (id, name, municipality, representative_name, contact_number) VALUES
('3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Liton Free Farmers Cooperative', 'Kabacan', 'Roberto Alvarez', '+63 917 123 4567'),
('4b4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'President Roxas Dairy Cooperative', 'President Roxas', 'Maria Santos', '+63 918 234 5678'),
('5c4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Tupi Dairy Box Cooperative', 'Tupi', 'Juan Dela Cruz', '+63 919 345 6789'),
('6d4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Surallah Dairy Farmers Association', 'Surallah', 'Elena Torralba', '+63 920 456 7890'),
('7e4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Maitum Sarangani Dairy Association', 'Maitum', 'Pedro Penduko', '+63 921 567 8901'),
('8f4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Midsayap Dairy Farmers Cooperative', 'Midsayap', 'Grace Ramos', '+63 922 678 9012'),
('9a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Matalam Livestock Cooperative', 'Matalam', 'Carlos Tech', '+63 923 789 0123'),
('0b4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Aleosan Forage Association', 'Aleosan', 'Dante Aligieri', '+63 924 890 1234'),
('1c4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Libungan Agricultural Cooperative', 'Libungan', 'Sylvia Plath', '+63 925 901 2345');

-- 2. Seed a Multi-generational Pedigree structure for inbreeding checks
-- Legend:
-- GGG_GP (Great-Great-Great Grandparents)
-- GG_GP (Great-Great Grandparents)
-- G_GP (Great Grandparents)
-- GP (Grandparents)
-- Parent (Dams & Sires)
-- Target A & B (Cousins)

-- 5th Generation Ancestors (Great-Great-Great Grandparents)
INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender, dairy_blood_percentage, dam_id, sire_id, cooperative_id, status) VALUES
('aa5e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'TAG-GGG-DAM1', 'Liton GGG Dam 1', '2016-01-01', 'F', 1.0000, NULL, NULL, '3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Dry'),
('ba5e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'TAG-GGG-SIRE1', 'Liton GGG Sire 1', '2016-01-01', 'M', 1.0000, NULL, NULL, '3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Agistment');

-- 4th Generation Ancestors (Great-Great Grandparents)
INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender, dairy_blood_percentage, dam_id, sire_id, cooperative_id, status) VALUES
('aa4e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'TAG-GG-DAM1', 'Liton GG Dam 1', '2018-01-01', 'F', 1.0000, 'aa5e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'ba5e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', '3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Dry'),
('ba4e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'TAG-GG-SIRE1', 'Liton GG Sire 1', '2018-01-01', 'M', 1.0000, NULL, NULL, '3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Agistment');

-- 3rd Generation Ancestors (Great Grandparents)
INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender, dairy_blood_percentage, dam_id, sire_id, cooperative_id, status) VALUES
('aa3e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'TAG-G-DAM1', 'Liton G Dam 1', '2020-01-01', 'F', 1.0000, 'aa4e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'ba4e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', '3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Dry'),
('ba3e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'TAG-G-SIRE1', 'Liton G Sire 1', '2020-01-01', 'M', 1.0000, NULL, NULL, '3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Agistment');

-- 2nd Generation Ancestors (Grandparents GP_D and GP_S)
INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender, dairy_blood_percentage, dam_id, sire_id, cooperative_id, status) VALUES
('ca9e88d1-55fc-42b7-a3a8-4e8979148d21', 'TAG-GP-DAM', 'Liton Grand Dam', '2022-01-01', 'F', 1.0000, 'aa3e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'ba3e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', '3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Dry'),
('fa9e88d1-55fc-42b7-a3a8-4e8979148d22', 'TAG-GP-SIRE', 'Liton Grand Sire', '2022-01-01', 'M', 1.0000, NULL, NULL, '3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Agistment');

-- Dams D1 and D2 (Full sisters, parents are Grandparents GP_D and GP_S)
INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender, dairy_blood_percentage, dam_id, sire_id, cooperative_id, status) VALUES
('da1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'TAG-DAM-D1', 'Liton Dam D1', '2023-11-01', 'F', 1.0000, 'ca9e88d1-55fc-42b7-a3a8-4e8979148d21', 'fa9e88d1-55fc-42b7-a3a8-4e8979148d22', '3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Dry'),
('da2e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'TAG-DAM-D2', 'Liton Dam D2', '2023-11-15', 'F', 1.0000, 'ca9e88d1-55fc-42b7-a3a8-4e8979148d21', 'fa9e88d1-55fc-42b7-a3a8-4e8979148d22', '3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Dry');

-- Unrelated Sires
INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender, dairy_blood_percentage, dam_id, sire_id, cooperative_id, status) VALUES
('fa9e88d1-55fc-42b7-a3a8-4e8979148d25', 'TAG-SIRE-A', 'Unrelated Sire A', '2023-01-01', 'M', 1.0000, NULL, NULL, '3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Agistment'),
('fa9e88d1-55fc-42b7-a3a8-4e8979148d26', 'TAG-SIRE-B', 'Unrelated Sire B', '2023-01-01', 'M', 1.0000, NULL, NULL, '3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Agistment');

-- Offsprings A and B (First cousins)
-- A's parents: dam D1, sire Sire A.
-- B's parents: dam D2, sire Sire B.
INSERT INTO animals (id, ear_tag_number, registration_name, birth_date, gender, dairy_blood_percentage, dam_id, sire_id, cooperative_id, status) VALUES
('aa1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'TAG-COUSIN-A', 'Cousin A (Offspring of D1)', '2025-01-01', 'F', 1.0000, 'da1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'fa9e88d1-55fc-42b7-a3a8-4e8979148d25', '3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Dry'),
('ba2e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'TAG-COUSIN-B', 'Cousin B (Offspring of D2)', '2025-01-10', 'M', 1.0000, 'da2e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f', 'fa9e88d1-55fc-42b7-a3a8-4e8979148d26', '3a4f66a7-0cfc-4034-8c63-6b3a0f7c22df', 'Agistment');

-- 3. Seed some initial raw milk batches for transaction testing
INSERT INTO raw_milk_batches (id, volume_liters, batch_temperature_celsius, origin_municipality, inventory_status, processing_suitability) VALUES
('c1a766a7-0cfc-4034-8c63-6b3a0f7c22df', 500.00, 4.20, 'Midsayap', 'In-Storage', 'Passed'),
('c2a766a7-0cfc-4034-8c63-6b3a0f7c22df', 450.00, 3.90, 'Midsayap', 'In-Storage', 'Passed'),
('c3a766a7-0cfc-4034-8c63-6b3a0f7c22df', 300.00, 5.50, 'Midsayap', 'In-Storage', 'Pending');
