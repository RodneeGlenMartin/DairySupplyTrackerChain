# Distributed Dairy Supply Chain and Logistics Tracker

An enterprise-grade, hardware-integrated backend, concurrency-safe query ledger, and REST API platform designed to track, calculate, and secure dairy logistics pipelines. This project aligns with the **ALAB-Karbawan** modernization project of the **Department of Agriculture - Philippine Carabao Center (DA-PCC)** at the **University of Southern Mindanao (USM)** in Cotabato, Philippines, serving the **Liton Free Farmers' Cooperative** and regional stakeholders.

---

## 1. System Architecture & Core Mathematical Engines

The platform is structured into three specialized modules that manage herd genetics, thermodynamic cold-chain kinetics, and supply chain authenticity:

### A. Herd Genetics & Breeding Ledger (`src/genetics.py`)
Provides pedigree auditing and inbreeding prevention algorithms to maintain herd health:
1. **Backcrossing Genetic Calculation:** 
   Calculates the dairy blood percentage ($G_n$) for newborn calves based on their sire ($S_n$) and dam ($D_{n-1}$) lineage. Assuming purebred sires ($S_n = 1.0$):
   $$G_n = \frac{S_n + D_{n-1}}{2}$$
2. **Inbreeding Block (Wright's Coefficient of Relationship):**
   Calculates the coefficient of relationship $R$ between a breeding dam and sire using a 5-generation pedigree tree:
   $$R_{XY} = \sum \left( \frac{1}{2} \right)^{n_1 + n_2}$$
   Where $n_1$ and $n_2$ represent the generational path lengths from dam $X$ and sire $Y$ to their common ancestors. Breeding attempts are blocked with `400 Bad Request` if $R \ge 0.0625$ (cousin/half-cousin boundary or closer).
3. **Heifer Repayment Tracking:**
   Enforces the cooperative's heifer repayment policy where members return the first-born heifer calf to the pool within 18 months (540 days) of actual calving:
   $$D_{\text{repayment}} = D_{\text{calving}} + 540 \text{ days}$$

### B. Cold-Chain Spoilage Predictor (`src/coldchain.py`)
Processes real-time IoT temperature telemetry logs to predict raw milk degradation using Arrhenius microbial growth kinetics:
1. **Arrhenius Microbial Growth Model:**
   Integrates temperature history logs to compute the temperature-dependent specific growth rate $k(T)$:
   $$\ln(k) = \ln(k_{\text{ref}}) - \frac{E_a}{R_g} \left( \frac{1}{T} - \frac{1}{T_{\text{ref}}} \right)$$
   Where:
   - $E_a = 64,000 \text{ J/mol}$ (Activation Energy)
   - $R_g = 8.314 \text{ J/(mol}\cdot\text{K)}$ (Universal Gas Constant)
   - $T_{\text{ref}} = 277.15 \text{ K}$ (4 °C Reference Temperature)
   - $k_{\text{ref}} = 0.05 \text{ h}^{-1}$ (Reference growth rate)
2. **Telemetry Integration & Quality Control:**
   Integrates growth rate across discrete time steps $dt$ to predict the final microbial load $N_t$ from initial count $N_0$:
   $$N_t = N_0 \cdot e^{\sum k(T_i) \Delta t_i}$$
   If $N_t \ge 1.0 \times 10^5 \text{ CFU/ml}$, the batch is flagged as **High Risk** (unsuitable for pasteurization), otherwise **Normal**.

### C. Cryptographic Distribution Ledger (`src/distribution.py`)
Ensures tamper-evident tracking of processed milk batches distributed through Department of Education (DepEd) and Department of Social Welfare and Development (DSWD) school-milk feeding programs:
- **Tamper-Evident SHA-256 Batch Chaining:**
  Creates a sequential, cryptographically linked chain of batch records where the signature of batch $B_i$ depends on the signature of the predecessor $B_{i-1}$:
  $$H_i = \text{SHA256}(H_{i-1} \parallel \text{BatchID}_i \parallel \text{Volume}_i \parallel \text{Temp}_i \parallel \text{Coliform}_i \parallel \text{Date}_i)$$
  Any attempt to alter historical records breaks the cryptographic signature chain, immediately invalidating downstream distribution receipts.

---

## 2. Technology Stack

- **Core Runtime:** Python 3.11
- **Database Engine:** PostgreSQL 15 (utilizing `SERIALIZABLE` transaction isolation and row-level locking for batch allocations)
- **API Gateway:** FastAPI & Uvicorn (REST API routing, Pydantic data validation schemas)
- **Virtualization & Orchestration:** Docker, Docker Compose, Kubernetes (Deployment and Service configs)
- **Verification Engine:** pytest (23 SWEBOK-aligned unit, integration, database durability, and chaos tests)

---

## 3. Getting Started & Verification Commands

### Prerequisite Setup
Clone the repository and install requirements in your environment:
```bash
pip install -r requirements.txt
```

### Running the Test Suite
Run the 23 SWEBOK-aligned tests locally:
```bash
pytest -v
```

### Deploying via Docker Compose
To build the multi-stage production Docker image and start the application container stack along with the PostgreSQL database:
```bash
docker compose up --build -d
```

### Running End-to-End Shell Verification
To execute the live verification suite (polls healthcheck, checks genetic blocks, cold-chain analysis, and cryptographic signatures):
```bash
chmod +x verify_stack.sh
./verify_stack.sh
```

### Validating Kubernetes Configuration
Execute the validator script to verify k8s resource configurations, namespace, probes, and secrets definitions:
```bash
chmod +x k8s/validate_k8s.sh
./k8s/validate_k8s.sh
```

---

## 4. Production Schema Migration

To apply DDL schema migrations against a target remote production database without seeding development test data:
```bash
# Set your production database URL connection string
export DATABASE_URL="postgresql://db_user:secure_prod_password@prod-db-host.internal:5432/dairy_supplychain_prod"

# Execute standalone migrator (validates schema via catalog checks)
python db/prod_migration.py
```
