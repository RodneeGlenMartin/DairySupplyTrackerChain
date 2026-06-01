#!/usr/bin/env bash

# verify_stack.sh
# End-to-end verification script for the Distributed Dairy Supply Chain and Logistics Tracker

# Color outputs
RED='\033[0;31%'
GREEN='\033[0;32%'
YELLOW='\033[0;33%'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Starting E2E Stack Verification ===${NC}"

# Exit immediately if a command exits with a non-zero status
set -e

# Check if Docker daemon is running
DOCKER_AVAILABLE=true
if ! docker info >/dev/null 2>&1; then
  DOCKER_AVAILABLE=false
  echo -e "${YELLOW}[Warning] Docker daemon is not running or not accessible.${NC}"
  echo -e "${YELLOW}Falling back to local host-based uvicorn verification...${NC}"
fi

# 1. Clean Environment
echo -e "${YELLOW}1. Cleaning up previous environments...${NC}"
set +e
if [ "$DOCKER_AVAILABLE" = true ]; then
  docker stop dairy_tracker_api dairy_postgres_db 2>/dev/null || true
  docker rm dairy_tracker_api dairy_postgres_db 2>/dev/null || true
  docker network rm dairy-network 2>/dev/null || true
else
  # Kill any stale uvicorn process running on port 8000
  pkill -f "uvicorn src.app:app" 2>/dev/null || true
fi
set -e

# 2. Build and Launch Stack
if [ "$DOCKER_AVAILABLE" = true ]; then
  echo -e "${YELLOW}2a. Creating custom docker network 'dairy-network'...${NC}"
  docker network create dairy-network

  echo -e "${YELLOW}2b. Building the multi-stage Python API image...${NC}"
  docker build -t pcc-usm-registry.edu.ph/dairy/coldchain-tracker:v2.1.0 .

  echo -e "${YELLOW}2c. Running the PostgreSQL container...${NC}"
  docker run -d \
    --name dairy_postgres_db \
    --network dairy-network \
    -e POSTGRES_DB=dairy_supplychain \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=postgres \
    -p 5432:5432 \
    postgres:15-alpine

  echo -e "${YELLOW}2d. Waiting for database to be ready and loading seeds...${NC}"
  set +e
  TIMEOUT_DB=15
  ELAPSED_DB=0
  DB_READY=false
  while [ $ELAPSED_DB -lt $TIMEOUT_DB ]; do
    if docker exec dairy_postgres_db pg_isready -U postgres -d dairy_supplychain >/dev/null 2>&1; then
      DB_READY=true
      break
    fi
    echo -e "Waiting for Postgres to start... (${ELAPSED_DB}s elapsed)"
    sleep 2
    ELAPSED_DB=$((ELAPSED_DB + 2))
  done

  if [ "$DB_READY" = false ]; then
    echo -e "${RED}PostgreSQL did not start in time. Exiting...${NC}"
    docker stop dairy_postgres_db || true
    docker rm dairy_postgres_db || true
    docker network rm dairy-network || true
    exit 1
  fi
  set -e

  echo -e "${GREEN}Database is ready! Loading schema.sql and seed.sql...${NC}"
  docker exec -i dairy_postgres_db psql -U postgres -d dairy_supplychain < db/schema.sql
  docker exec -i dairy_postgres_db psql -U postgres -d dairy_supplychain < db/seed.sql

  echo -e "${YELLOW}2e. Launching the Python REST API container...${NC}"
  docker run -d \
    --name dairy_tracker_api \
    --network dairy-network \
    -e DATABASE_URL=postgresql://postgres:postgres@dairy_postgres_db:5432/dairy_supplychain \
    -e KINETIC_MODEL_ACTIVATION_ENERGY=64000 \
    -p 8000:8000 \
    pcc-usm-registry.edu.ph/dairy/coldchain-tracker:v2.1.0
else
  # Local host execution
  echo -e "${YELLOW}2. Starting local uvicorn API gateway server in the background...${NC}"
  uvicorn src.app:app --host 127.0.0.1 --port 8000 > uvicorn.log 2>&1 &
  UVICORN_PID=$!
fi

# 3. Health Monitoring
echo -e "${YELLOW}3. Monitoring health on /healthz...${NC}"
TIMEOUT=45
ELAPSED=0
HEALTHY=false

# Disable exit on error for curl checks
set +e

while [ $ELAPSED -lt $TIMEOUT ]; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/healthz || true)
  if [ "$HTTP_CODE" = "200" ]; then
    HEALTHY=true
    break
  fi
  echo -e "${YELLOW}Waiting for API to be healthy... (HTTP $HTTP_CODE, ${ELAPSED}s elapsed)${NC}"
  sleep 2
  ELAPSED=$((ELAPSED + 2))
done

if [ "$HEALTHY" = false ]; then
  echo -e "${RED}API did not become healthy within $TIMEOUT seconds. Exiting...${NC}"
  if [ "$DOCKER_AVAILABLE" = true ]; then
    docker logs dairy_tracker_api
    docker stop dairy_tracker_api dairy_postgres_db || true
    docker rm dairy_tracker_api dairy_postgres_db || true
    docker network rm dairy-network || true
  else
    kill $UVICORN_PID || true
    cat uvicorn.log
    rm -f uvicorn.log
  fi
  exit 1
fi

echo -e "${GREEN}API is healthy (HTTP 200 OK)! Starting verification requests...${NC}"
set -e

# 4. End-to-End Test Requests

# Test 1 (Genetics Blocker): Inbreeding block check between cousins (aa1e2f3a and ba2e2f3a)
echo -e "${YELLOW}Executing Test 1 (Genetics Blocker): Breeding cousins...${NC}"
BREEDING_PAYLOAD='{
  "animal_id": "aa1e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
  "breeding_type": "AI",
  "semen_batch_code": "SEM-COUSIN-99",
  "insemination_date": "2026-06-01",
  "semen_sire_id": "ba2e2f3a-4a5b-6c7d-8e9f-0a1b2c3d4e5f"
}'

RESPONSE_1=$(curl -s -w "\n%{http_code}" -X POST -H "Content-Type: application/json" -d "$BREEDING_PAYLOAD" http://localhost:8000/breeding)
STATUS_1=$(echo "$RESPONSE_1" | tail -n 1)
BODY_1=$(echo "$RESPONSE_1" | sed '$d')

if [ "$STATUS_1" = "400" ]; then
  echo -e "${GREEN}Test 1 Passed: Breeding blocked successfully with HTTP 400 Bad Request!${NC}"
  echo -e "${GREEN}Response detail: $BODY_1${NC}"
else
  echo -e "${RED}Test 1 Failed: Expected HTTP 400 but got HTTP $STATUS_1${NC}"
  echo -e "${RED}Response: $BODY_1${NC}"
  if [ "$DOCKER_AVAILABLE" = true ]; then
    docker stop dairy_tracker_api dairy_postgres_db || true
    docker rm dairy_tracker_api dairy_postgres_db || true
    docker network rm dairy-network || true
  else
    kill $UVICORN_PID || true
    rm -f uvicorn.log
  fi
  exit 1
fi

# Test 2 (Cold-Chain Arrhenius): Temperature spike telemetry
echo -e "${YELLOW}Executing Test 2 (Cold-Chain Arrhenius): Telemetry spoilage spike...${NC}"
TELEMETRY_PAYLOAD='{
  "temp_log": [4.0, 15.0, 25.0, 35.0, 35.0, 35.0, 35.0, 35.0, 35.0, 35.0],
  "time_log": [
    "2026-06-01T08:00:00Z",
    "2026-06-01T09:00:00Z",
    "2026-06-01T10:00:00Z",
    "2026-06-01T11:00:00Z",
    "2026-06-01T12:00:00Z",
    "2026-06-01T13:00:00Z",
    "2026-06-01T14:00:00Z",
    "2026-06-01T15:00:00Z",
    "2026-06-01T16:00:00Z",
    "2026-06-01T17:00:00Z"
  ],
  "initial_cfu": 1000.0
}'

RESPONSE_2=$(curl -s -w "\n%{http_code}" -X POST -H "Content-Type: application/json" -d "$TELEMETRY_PAYLOAD" http://localhost:8000/telemetry)
STATUS_2=$(echo "$RESPONSE_2" | tail -n 1)
BODY_2=$(echo "$RESPONSE_2" | sed '$d')

if [ "$STATUS_2" = "200" ]; then
  echo -e "${GREEN}Test 2 Passed: Spoilage checked with HTTP 200 OK!${NC}"
  echo -e "${GREEN}Response result: $BODY_2${NC}"
else
  echo -e "${RED}Test 2 Failed: Expected HTTP 200 but got HTTP $STATUS_2${NC}"
  echo -e "${RED}Response: $BODY_2${NC}"
  if [ "$DOCKER_AVAILABLE" = true ]; then
    docker stop dairy_tracker_api dairy_postgres_db || true
    docker rm dairy_tracker_api dairy_postgres_db || true
    docker network rm dairy-network || true
  else
    kill $UVICORN_PID || true
    rm -f uvicorn.log
  fi
  exit 1
fi

# Test 3 (Cryptographic Chain): Finished product batch creation
echo -e "${YELLOW}Executing Test 3 (Cryptographic Chain): Finished product batch creation...${NC}"
BATCH_PAYLOAD='{
  "batch_identifier": "E2E-BATCH-100",
  "product_type": "Ice Cream",
  "quantity_units_produced": 500,
  "manufacture_date": "2026-06-01",
  "shelf_life_days": 180,
  "coliform_test_status": "Passed",
  "pasteurization_temp_celsius": 72.5
}'

RESPONSE_3=$(curl -s -w "\n%{http_code}" -X POST -H "Content-Type: application/json" -d "$BATCH_PAYLOAD" http://localhost:8000/batches)
STATUS_3=$(echo "$RESPONSE_3" | tail -n 1)
BODY_3=$(echo "$RESPONSE_3" | sed '$d')

if [ "$STATUS_3" = "201" ]; then
  echo -e "${GREEN}Test 3 Passed: Batch created with HTTP 201 Created!${NC}"
  echo -e "${GREEN}Response result: $BODY_3${NC}"
else
  echo -e "${RED}Test 3 Failed: Expected HTTP 201 but got HTTP $STATUS_3${NC}"
  echo -e "${RED}Response: $BODY_3${NC}"
  if [ "$DOCKER_AVAILABLE" = true ]; then
    docker stop dairy_tracker_api dairy_postgres_db || true
    docker rm dairy_tracker_api dairy_postgres_db || true
    docker network rm dairy-network || true
  else
    kill $UVICORN_PID || true
    rm -f uvicorn.log
  fi
  exit 1
fi

echo -e "${GREEN}All E2E Verification Requests Passed successfully!${NC}"

# 5. Graceful Cleanup
echo -e "${YELLOW}5. Cleaning up...${NC}"
if [ "$DOCKER_AVAILABLE" = true ]; then
  docker stop dairy_tracker_api dairy_postgres_db || true
  docker rm dairy_tracker_api dairy_postgres_db || true
  docker network rm dairy-network || true
else
  kill $UVICORN_PID || true
  rm -f uvicorn.log
fi

echo -e "${GREEN}=== E2E Stack Verification Complete! ===${NC}"
