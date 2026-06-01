Architecture III: Distributed Dairy Supply Chain and Logistics TrackerContext, Macroeconomic Drivers, and the Localized EcosystemThe modernization of the Philippine dairy sector requires a strategic alignment between physical infrastructure and specialized enterprise software. The establishment of the ₱3.4 million Dairy Box facility at the Kabacan Terminal Complex in Barangay Kayaga, Kabacan, Cotabato, is a key localized intervention under the Accelerating Livelihood and Assets Buildup (ALAB-Karbawan) project. Funded through the Senate Committee on Agriculture, Food, and Agrarian Reform, chaired by Senator Cynthia A. Villar, and executed by the Department of Agriculture - Philippine Carabao Center (DA-PCC) at the University of Southern Mindanao (USM), this facility is scheduled for operational completion in May 2026.Once completed, the Kabacan Dairy Box will be handed over to the Liton Free Farmers' Cooperative to serve as a processing and marketing hub. It joins a network of facilities in Region 12, complementing existing Dairy Boxes in President Roxas (constructed in 2020), Tupi, Surallah, and Maitum, while mirroring the cooperative-led model deployed in the Davao region across Matanao, Montevista, Mati, Cateel, and Sta. Maria.                     +---------------------------------------+
                     |       REGION 12 DAIRY BOX NETWORK     |
                     +---------------------------------------+
                                         |
       +------------------+--------------+--------------+------------------+
       |                  |                             |                  |
       v                  v                             v                  v
+--------------+   +--------------+              +--------------+   +--------------+
| Kabacan (2026|   | Pres. Roxas  |              |    Tupi &    |   |    Maitum    |
| Kayaga Node) |   | (Est. 2020)  |              |   Surallah   |   | (Sarangani)  |
+--------------+   +--------------+              +--------------+   +--------------+
Historically, the national government has made significant investments to address the supply-demand deficit in local dairy. Between 2013 and 2018, the state allocated at least ₱2.85 billion to the National Dairy Authority (NDA) and the PCC to expand the national dairy herd from 39,069 animals. Despite these investments, local milk demand continues to outpace domestic production.The DA-PCC is executing a target trajectory to reverse the downward trend in the national carabao population starting in 2025. While live-weight carabao production for meat has experienced a 1% average annual decline, the live-weight farmgate price rose to ₱149.41 per kilogram in 2023—a 13.5% increase over five years. This economic shift makes dairying increasingly profitable for smallholders. To capitalize on this, the PCC has issued a national directive to increase local milk production from 1% to 10%. The Carabao Herd Build-Up (CHB) program supports this directive by distributing pregnant dairy buffaloes to farmers.To support these operations, the DA-PCC at USM operates under the leadership of Center Director Dr. Geoffray R. Atok and in close collaboration with USM President Dr. Jonald L. Pimentel. Under their partnership, a ₱400 million research budget starting in 2026 funds interdisciplinary scientific initiatives. These initiatives bring together USM's College of Agriculture (CA), College of Science and Mathematics - Biology Department, and College of Veterinary Medicine (CVM).This research-driven approach is supported by academic studies. For example, at the 44th Year-end In-House Review conducted by the USM Office of the Vice President for Research Development and Extension (VPRDE), the paper "PCC's Dairy Box and Family Module: Success Stories, Challenges and Ways Forward" was awarded Best Paper in the Social Research Category.To translate these research insights into field operations, the distributed supply chain requires specialized software. This system acts as a localized Enterprise Resource Planning (ERP) tool, tracking genetic lineage, feed bases, cold-chain logistics, and institutional distribution.Herd Genetics and Breeding Ledger ModuleThe Herd Genetics and Breeding Ledger manages livestock assets and genetic improvement at the cooperative level. On September 1, 2025, DA-PCC at USM formally signed a Memorandum of Agreement (MOA) with the USM Academic Support Staff Association, Inc. (USMASSAI) in Kabacan, Cotabato. This agreement established a partnership under the Carabao Enterprise Development Program. Under the MOA, DA-PCC provides genetically improved dairy buffaloes, technical training, and veterinary support, while USMASSAI manages the dispersed animals and ensures compliance with breeding protocols.On January 26, 2026, during the 31st Founding Anniversary of DA-PCC at USM, both USMASSAI and the Tambad Farmers Agriculture Association (TFAA) of Carmen, Cotabato, received five gestating dairy buffaloes under the CHB project. Sourced from PCC nucleus and agistment farms, these animals represent a high-value public investment.Biological and Reproductive Lineage FormulationTo organicially boost milk production, the system monitors reproductive efficiency and genetic heritage. It enforces a directed backcrossing protocol designed to raise the dairy blood composition of subsequent generations to at least 75%. Let $G_n$ denote the genetic percentage of dairy blood in an offspring of generation $n$. Let $S_n$ represent the dairy purity of the sire (with purebred imported dairy sires fixed at $S_n = 1.0$), and let $D_{n-1}$ represent the dairy blood fraction of the dam. The ledger calculates genetic inheritance using the following formula:$$G_n = \frac{S_n + D_{n-1}}{2}$$To prevent inbreeding depression, the breeding engine monitors the coefficient of relationship ($R$) between a candidate sire and dam by parsing ancestral paths up to five generations. Let $A$ represent a common ancestor, and let $p$ and $q$ represent the number of generations from the sire and dam to that ancestor, respectively. The system calculates the coefficient as:$$R = \sum \left( \frac{1}{2} \right)^{p + q}$$If $R \ge 0.0625$ (the equivalent of a cousin mating), the system flags the transaction and blocks the allocation of that semen batch.                          Sire (S) ---- (p generations) ----+
                                                            |
                                                            v
                                                   Common Ancestor (A)
                                                            ^
                                                            |
                          Dam (D)  ---- (q generations) ----+
Statutory Compliance and Biological WorkflowsThe breeding ledger enforces the biological workflows mandated by the General Appropriations Act (GAA) of 2024 for the PCC Herd Build-Up Program. These mandates require tracking across six operational categories:Sourcing and procurement of dairy stock.Multiplying local stock through nucleus and agistment farms.Providing breeding services to Farmers Cooperatives and Associations (FCAs).Providing veterinary health services.Providing nutritional services, including forage and silage production.Enhancing dairy farm facilities.Additionally, the ledger tracks climate change adaptation metrics, specifically monitoring the conversion of dairy animal manure into organic fertilizer through vermicomposting. Under the GAA, the PCC must submit quarterly financial and physical accomplishments via the Unified Reporting System (URS) within 30 days of the end of each quarter. The breeding ledger automates this reporting by aggregating herd numbers, pregnancies, and health profiles.The system also tracks the 18-month heifer repayment model. Under this protocol, which is used to sustain local dairy programs, a beneficiary receives a pregnant buffalo at no initial cost. In return, they must return an 18-month-old female offspring to the cooperative for redistribution to other members. The ledger manages this lifecycle through the relational database schema structured below.SQLCREATE TABLE cooperatives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    municipality VARCHAR(100) NOT NULL,
    representative_name VARCHAR(100),
    contact_number VARCHAR(50)
);

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
Cold-Chain Yield and Processing Tracker ModuleThe cold chain begins with the daily extraction of raw milk across Midsayap, Aleosan, Libungan, Carmen, and Matalam, followed by its transport to the central Kabacan Dairy Box. Because raw carabao milk is highly perishable, maintaining precise temperature control is critical to prevent spoilage and ensure the quality of value-added products like ice cream and yogurt.Soil and Forage Nutritional Suitability CoregistrationThe quality of raw milk begins with herd nutrition and forage quality. To support this, the tracking system integrates regional soil and land suitability data. Using GIS mapping coordinates from PhilGIS, the ledger evaluates the local soil suitability of each municipality.For example, in Matalam, Cotabato, approximately 37% (12,528 hectares) of the land is moderately suitable for agricultural production due to moderately shallow soils. This soil profile affects the growth rate and mineral content of forage grasses like Napier and Guinea grass. The tracker records these municipal soil profiles to help cooperatives optimize their silage production and manage nutritional variables.MunicipalitySoil Suitability ProfileKey Forage & Silage VarietiesPrimary Transport Challenge to KabacanKabacanDeep alluvial, highly fertile Napier, Centrosema Minimal; immediate local intake CarmenClay loam, moderately deep Corn Silage, Guinea Grass Intermittent road construction delaysMatalam37% moderately shallow soils Napier Grass, Legumes High-elevation transport vibrationsAleosanRolling hills, moderate erosionPara Grass, Silage Prolonged transit times in midday heatLibunganSandy loam, highly permeableNapier, Trichanthera Distance; requires active coolingMidsayapClay loam, flood-proneMixed Forage, Silage River crossing logistics; high humidityReal-Time Kinetic Spoilage ModelingTo monitor milk safety during transit, the platform ingests real-time temperature data from IoT-enabled storage canisters. It uses a kinetic model based on the Arrhenius equation to calculate bacterial growth and predict shelf-life degradation in real time.Let $C(t)$ represent the concentration of spoilage microorganisms (such as Pseudomonas or lactic acid bacteria) at transit time $t$. The growth rate is defined as:$$\frac{dC}{dt} = \mu(T) \cdot C(t)$$$$\ln\left(\frac{C(t)}{C_0}\right) = \int_{0}^{t} \mu(T(\tau)) \, d\tau$$The temperature-dependent specific growth rate $\mu(T)$ (where $T$ is in Kelvin) is calculated using the Arrhenius relationship:$$\mu(T) = \mu_{ref} \cdot \exp\left( -\frac{E_a}{R} \cdot \left \right)$$Where $E_a$ is the activation energy ($J \cdot \text{mol}^{-1}$), $R$ is the ideal gas constant ($8.314 \text{ J} \cdot \text{mol}^{-1} \cdot \text{K}^{-1}$), $T$ is the raw milk temperature, and $T_{ref}$ is a reference temperature (typically $277.15\text{ K}$ or $4^\circ\text{C}$).Pythonimport numpy as np
from datetime import datetime

def predict_microbial_growth(temp_log, time_log, initial_cfu=1000.0):
    """
    Computes predicted microbial load (CFU/ml) based on temperature logs.
    temp_log: List of float values representing temperature readings in Celsius.
    time_log: List of datetime objects representing the time of each reading.
    """
    R = 8.314                   # Ideal gas constant
    E_a = 64000.0               # Activation energy (J/mol) for milk psychrotrophic bacteria
    T_ref = 277.15              # Reference temperature in Kelvin (4 C)
    mu_ref = 0.05               # Specific growth rate at reference temperature (hours^-1)
    
    log_ratio = 0.0
    for i in range(1, len(temp_log)):
        # Calculate time difference in hours
        dt = (time_log[i] - time_log[i-1]).total_seconds() / 3600.0
        
        # Calculate average temperature during the interval in Kelvin
        temp_k_prev = temp_log[i-1] + 273.15
        temp_k_curr = temp_log[i] + 273.15
        T_avg = (temp_k_prev + temp_k_curr) / 2.0
        
        # Apply the Arrhenius model
        mu = mu_ref * np.exp(-(E_a / R) * ((1.0 / T_avg) - (1.0 / T_ref)))
        log_ratio += mu * dt
        
    final_cfu = initial_cfu * np.exp(log_ratio)
    return final_cfu
If the predicted microbial count ($C(t)$) exceeds a threshold of $1.0 \times 10^5 \text{ CFU/ml}$ during transit, the platform automatically flags the batch as "High Risk." Upon arrival at the Kabacan facility, the receiving team is notified to run immediate acidity and quality validation tests before processing.Concurrent Access and Transaction IsolationDuring morning collection hours, multiple cooperative agents write yield and temperature records to the database simultaneously. To prevent race conditions, lost updates, or duplicate allocation of raw milk batches to the processing pipeline, the system uses an explicit concurrency control strategy. Transactions that modify inventory state are executed using SERIALIZABLE transaction isolation or explicit row-level locking:SQL-- Transaction to allocate raw milk batches to the ice cream processing line
BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;

-- Query and lock specific inventory records
SELECT id, volume_liters, batch_temperature_celsius, inventory_status
FROM raw_milk_batches
WHERE origin_municipality = 'Midsayap' 
  AND inventory_status = 'In-Storage'
  AND processing_suitability = 'Passed'
FOR UPDATE;

-- Record allocation to the processing line
INSERT INTO processing_pipeline_runs (run_id, product_type, total_volume_liters, start_timestamp)
VALUES (gen_random_uuid(), 'Ice Cream', 450.0, CURRENT_TIMESTAMP);

-- Update raw milk inventory status
UPDATE raw_milk_batches
SET inventory_status = 'In-Processing'
WHERE origin_municipality = 'Midsayap' 
  AND inventory_status = 'In-Storage'
  AND processing_suitability = 'Passed';

COMMIT;
Quality Assurance and Institutional Distribution ModuleOnce raw milk is processed into pasteurized milk, ice cream, or yogurt, the distribution ledger manages downstream supply chain security. The finished goods are integrated directly into the national feeding and nutrition programs run by the Department of Education (DepEd) and the Department of Social Welfare and Development (DSWD). This distribution network is supported by Cotabato Governor Emmylou Mendoza, who emphasizes its role in improving childhood nutrition across the province.                 +----------------------------------------+
                 |       FINISHED GOOD BATCH CREATION     |
                 |  - Unique Batch Number (SHA-256)       |
                 |  - Processing Variables Recorded       |
                 +-------------------+--------------------+
                                     |
                                     v
                 +----------------------------------------+
                 |      QA VALIDATION & LAB CLEARANCE     |
                 |  - Bacterial & pH Testing              |
                 |  - Cryptographic Verification Hash     |
                 +-------------------+--------------------+
                                     |
                                     v
                 +----------------------------------------+
                 |       INSTITUTIONAL DISTRIBUTION       |
                 |  - DepEd & DSWD Allocation             |
                 |  - Dispatch Tracking (Real-Time Temp)  |
                 +-------------------+--------------------+
                                     |
         +---------------------------+---------------------------+
         |                                                       |
         v                                                       v
+-------------------------------+                       +-------------------------------+
|     DepEd Feeding Program     |                       |     DSWD Feeding Program      |
|  - Schools in Region 12       |                       |  - Community Daycare Centers  |
+-------------------------------+                       +-------------------------------+
Cryptographic Traceability and Food Safety ComplianceTo ensure food safety and regulatory compliance, the distribution ledger uses a cryptographic chaining model. This model links each finished product batch to its raw milk inputs, processing records, and quality testing history.Let $B_i$ denote the unique identifier of a finished product batch. The cryptographic signature of the batch, $H(B_i)$, is calculated as:$$H(B_i) = \text{SHA256}\left( H(B_{i-1}) \parallel B_i \parallel V_{batch} \parallel T_{pasteur} \parallel P_{coliform} \parallel t_{stamp} \right)$$Where:$H(B_{i-1})$ is the hash of the preceding batch, maintaining a tamper-evident audit trail.$V_{batch}$ is the physical volume of the batch.$T_{pasteur}$ represents the pasteurization temperature logs.$P_{coliform}$ is the coliform test result.$t_{stamp}$ is the processing timestamp.If an audit is triggered by a feeding site, inspectors can parse the chain to verify that the batch’s processing history has not been altered.SQLCREATE TABLE product_batches (
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

CREATE TABLE feeding_allocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_agency VARCHAR(10) CHECK (recipient_agency IN ('DepEd', 'DSWD')),
    school_or_center_name VARCHAR(255) NOT NULL,
    target_municipality VARCHAR(100) NOT NULL,
    allocation_date TIMESTAMP WITH TIME ZONE NOT NULL,
    delivery_status VARCHAR(50) DEFAULT 'Pending' CHECK (delivery_status IN ('Pending', 'In-Transit', 'Delivered', 'Rejected'))
);

CREATE TABLE batch_allocation_mapping (
    batch_id UUID REFERENCES product_batches(id),
    allocation_id UUID REFERENCES feeding_allocations(id),
    units_delivered INT NOT NULL,
    PRIMARY KEY (batch_id, allocation_id)
);
Pedagogical Alignment and Software Quality FrameworkIntegrating this logistics system into university computing curricula provides students with practical experience in managing complex system states and concurrency. This hands-on application aligns directly with the Software Engineering Body of Knowledge (SWEBOK) standards. Specifically, it maps to Software Testing (KA 5) and Software Quality (KA 12).SWEBOK KA 5: Software Testing IntegrationThe software testing lifecycle is designed around reliability-oriented verification. This is critical because system failures or delayed reports can lead to the spoilage of expensive raw milk or inaccurate payments to smallholder dairy farmers. Testing is structured across three SWEBOK levels: Unit, Integration, and System Testing.1. Unit Testing and Mocking Telemetry InputsUnit tests verify the correctness of isolated mathematical functions, such as the Arrhenius spoilage calculator or the genetic percentage calculation. To test these functions, the testing pipeline mocks input data, simulating edge cases and extreme environmental conditions.Pythonimport unittest
from datetime import datetime, timedelta

class TestDairyLogisticsAlgorithms(unittest.TestCase):
    
    def test_genetic_backcrossing_calculation(self):
        # Base case: purebred sire (100% dairy) mated to local dam with 50% dairy blood
        # Expected offspring: (1.0 + 0.5) / 2 = 0.75 (75%)
        sire_percentage = 1.0000
        dam_percentage = 0.5000
        offspring_percentage = (sire_percentage + dam_percentage) / 2.0
        self.assertEqual(offspring_percentage, 0.7500)
        
    def test_repayment_date_calculation(self):
        # Test that the system correctly projects the 18-month heifer repayment window
        calving_date = datetime.strptime("2026-01-26", "%Y-%m-%d")
        # 18 months corresponds to exactly 540 days in system intervals
        expected_repayment = calving_date + timedelta(days=540)
        self.assertEqual(expected_repayment.strftime("%Y-%m-%d"), "2027-07-20")

if __name__ == '__main__':
    unittest.main()
2. Integration TestingIntegration testing verifies that separate system modules communicate correctly. In this architecture, integration tests validate the flow of data between the IoT telemetry receiver and the relational database, ensuring that sensor data is written to the database without causing locks or database drift.3. System Testing and Chaos InjectionSystem testing evaluates the application’s resilience in an integrated environment. To simulate network dropouts and hardware failures in rural Cotabato, the testing pipeline uses automated chaos injection:Network Latency Simulation: Artificially limits bandwidth on mobile-client connections to verify that offline database syncing works correctly when connectivity is restored.Node Failures: Terminates container pods during active data transfers to verify that the system recovers without losing transaction state.Data Recovery Verification: Simulates database connection losses during transaction sequences to confirm that transactions rollback properly, preventing partial writes.SWEBOK KA 12: Software Quality IntegrationThe platform manages software quality using both static and dynamic verification techniques, as defined in SWEBOK Chapter 12.Static Quality ManagementStatic verification evaluates the codebase without executing the program :Static Analysis: Linters and static type checkers (such as MyPy and SonarQube) analyze code structure to identify vulnerabilities, syntax issues, or potential type errors before deployment.Database Schema Validation: Schema migrations are parsed by automated tools to verify that database indices, constraints, and relational structures are properly aligned.Dynamic Quality ManagementDynamic verification evaluates the system during active execution :Performance Profiling: Automated performance tests run continuously to monitor system latency, memory usage, and execution speeds during simulated peak loads.Quality Metrics Dashboard: A monitoring system tracks key database and API performance indicators, helping administrators identify bottlenecks.SQLCREATE TABLE database_quality_metrics (
    id SERIAL PRIMARY KEY,
    log_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    active_connections INT NOT NULL,
    transaction_rollback_count INT NOT NULL,
    deadlock_events_count INT NOT NULL,
    average_query_execution_time_ms NUMERIC(8,2) NOT NULL
);
Virtualization and Deployment InfrastructureThe deployment architecture uses container virtualization to maintain high availability and resource efficiency. Docker containers package each microservice with its required dependencies, ensuring consistent runtime environments across development, testing, and production.                                  +-----------------------+
                                  |     INGRESS GATEWAY   |
                                  |   (Reverse Proxy /    |
                                  |    Load Balancer)     |
                                  +-----------+-----------+
                                              |
             +--------------------------------+--------------------------------+
             |                                |                                |
             v                                v                                v
+------------------------+       +------------------------+       +------------------------+
|      BREEDING LEDGER   |       |     COLD-CHAIN FLOW    |       |   DISTRIBUTION LEDGER  |
|      MICROSERVICE      |       |      MICROSERVICE      |       |      MICROSERVICE      |
|  - Replica Pod 1       |       |  - Replica Pod 1       |       |  - Replica Pod 1       |
|  - Replica Pod 2       |       |  - Replica Pod 2       |       |  - Replica Pod 2       |
+-----------+------------+       +-----------+------------+       +-----------+------------+
            |                                |                                |
            +--------------------------------+--------------------------------+
                                             |
                                             v
                                  +-----------------------+
                                  |     DATABASE CLUSTER  |
                                  |  - PostgreSQL Master  |
                                  |  - Timescale Replica  |
                                  +-----------------------+
Production Deployment ConfigurationFor production environments, a Kubernetes cluster orchestrates container lifecycles, resource scaling, and network routing. The configuration below defines the deployment for the core cold-chain service:YAMLapiVersion: apps/v1
kind: Deployment
metadata:
  name: coldchain-tracker-deployment
  namespace: dairy-supplychain
  labels:
    app: coldchain-tracker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: coldchain-tracker
  template:
    metadata:
      labels:
        app: coldchain-tracker
    spec:
      containers:
      - name: tracker-service
        image: pcc-usm-registry.edu.ph/dairy/coldchain-tracker:v2.1.0
        ports:
        - containerPort: 8000
        resources:
          limits:
            cpu: "1.0"
            memory: "1024Mi"
          requests:
            cpu: "0.5"
            memory: "512Mi"
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-credentials
              key: connection-string
        - name: KINETIC_MODEL_ACTIVATION_ENERGY
          value: "64000"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: coldchain-tracker-service
  namespace: dairy-supplychain
spec:
  selector:
    app: coldchain-tracker
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: ClusterIP
Deploying this architecture in a virtualized Kubernetes environment provides students with practical experience in managing scalable cloud infrastructure. It teaches them to configure health probes, establish secure database connections, and run multi-node container networks. This real-world application of SWEBOK principles ensures that computing graduates gain experience with industry-standard deployment practices while supporting the operational goals of the DA-PCC herd build-up program.