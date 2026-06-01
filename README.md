# Distributed Dairy Supply Chain and Logistics Tracker

An enterprise-grade, hardware-integrated backend, concurrency-safe query ledger, and REST API platform designed to track, calculate, and secure dairy logistics pipelines. This project aligns with the **ALAB-Karbawan** modernization project of the **Department of Agriculture - Philippine Carabao Center (DA-PCC)** at the **University of Southern Mindanao (USM)** in Cotabato, Philippines, serving the **Liton Free Farmers' Cooperative** and regional stakeholders.

---

## 1. System Architecture & Core Mathematical Engines

The platform is structured into specialized modules that manage herd genetics, thermodynamic cold-chain kinetics, and supply chain authenticity:

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

## 2. Dynamic, Seed-Free Database Provisioning

The database setup runs completely mock-free with **zero local seed SQL files or static mock tables** in the repository. Instead, initial seeding and geographic records are constructed dynamically over the internet by `db/dynamic_provisioner.py`:

- **Philippine Geographic Data Ingestion:**
  The script performs active, real-time HTTP requests to the **official Philippine Standard Geographic Code (PSGC) Cloud API** (`psgc.cloud`) to fetch current geographical municipalities of Cotabato over the internet.
- **Dynamic Representative Profiles:**
  Queries the open `randomuser.me` API dynamically to retrieve realistic names and contact details to generate cooperative representative profiles on the fly.
- **Cryptographic Determinism:**
  To maintain test compatibility without relying on static local mock tables, the system uses deterministic UUID mapping via `uuid.uuid5(namespace, name)` to bind live-ingested municipalities to identical, repeatable UUID keys. This guarantees that test suite assertions referencing specific cooperatives and animal pedigree IDs remain perfectly valid and aligned across runs.
- **Pedigree Reconstruction:**
  Generates a 5-generation animal pedigree tree dynamically (complete with Great-Great-Great Grandparents to target Cousin A and Cousin B) to serve as a baseline for the Wright's coefficient relationship checks.

---

## 3. Live Climate-Driven Spoilage Telemetry

The thermodynamic cold-chain predictor (`src/coldchain.py`) is fully integrated with environmental conditions:
- **Open-Meteo Integration:**
  On batch submission or telemetry checks, the system fetches the actual, live ambient temperature log for the past 24 hours directly from the **Open-Meteo API** based on canister coordinates (e.g. Kabacan: Lat 7.118, Lon 124.843, or Midsayap: Lat 7.192, Lon 124.530).
- **Arrhenius Integration:**
  These 24 real-time temperature telemetry data points are fed into the Arrhenius decay calculation, replacing static mock temperature profiles with live climate measurements.

---

## 4. Accessible UI & Dynamic Translations

The Field Portal and Operator Dashboard provide a mobile-first, accessible, and multi-lingual interface layer:
- **Acoustic & Haptic Feedback Mappings:**
  To assist field technicians working with gloves in high-glare outdoor environments, the Web UI maps key transactions to haptic vibrations and synthesized audio beeps:
  - **Success Indicator:** Generates a 1000 Hz sine wave beep for 0.15 seconds, accompanied by a 100ms haptic vibration pulse on the device.
  - **Error / Blocker Warning:** Generates a low-frequency 150 Hz sawtooth wave warning tone for 0.5 seconds, accompanied by a double-pulse vibration pattern `[400ms on, 100ms off, 400ms on]` to signal validation failures (such as inbreeding blocks).
- **Dynamic Multilingual Translations:**
  The portal includes a translation toggle supporting English, Cebuano, Hiligaynon, and Tagalog. Switching languages triggers on-the-fly requests to the public **MyMemory Translation API** (`https://api.mymemory.translated.net/get`).
- **Session Cache:**
  To optimize network calls and minimize latency, translated labels are saved in the client's local `sessionStorage` cache.

---

## 5. Outage and Failover Handling

To protect request latency and maintain operational resilience during connectivity loss:
- **Connection Timeouts:**
  All `httpx.AsyncClient` network calls enforce strict connection timeout boundaries (defaulting to a strict `3.0 seconds` configuration, optimized up to `10.0 seconds` for high-latency test runners).
- **Transient Outage Resilience:**
  The system utilizes a 3-attempt retry loop with exponential/linear backoffs for Open-Meteo and MyMemory requests.
- **Client Offline Synchronization Queue:**
  If the network is completely down, the Field Portal caches submitted animal registrations and breeding logs locally using the browser's `localStorage` and client queue retry loops, automatically synchronization once connection is restored.

---

## 6. Technology Stack

- **Core Runtime:** Python 3.11
- **Database Engine:** PostgreSQL 15 (utilizing `SERIALIZABLE` transaction isolation and row-level locking for batch allocations)
- **API Gateway:** FastAPI & Uvicorn (REST API routing, Pydantic data validation schemas)
- **Virtualization & Orchestration:** Docker, Docker Compose, Kubernetes (Deployment and Service configs)
- **Verification Engine:** pytest (SWEBOK-aligned unit, integration, database durability, and chaos tests)

---

## 7. Getting Started & Verification Commands

### Prerequisite Setup
Clone the repository and install requirements in your environment:
```bash
pip install -r requirements.txt
```

### Running the Dynamic Provisioner
Initialize the database structure and dynamically seed the cooperative registries, pedigree records, and test logs over live web APIs:
```bash
python db/dynamic_provisioner.py
```

### Running the Test Suite
The SWEBOK-aligned test suite (`pytest -v`) now executes all 27 integration tests completely mock-free over active internet connections:
```bash
pytest -v
```

### Deploying via Docker Compose
To build the multi-stage production Docker image and start the application container stack:
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
