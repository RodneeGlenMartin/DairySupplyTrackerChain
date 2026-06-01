#!/bin/bash
# k8s/validate_k8s.sh - Kubernetes Configuration Validation Script
set -euo pipefail

YAML_FILE="k8s/deployment.yaml"

echo "=================================================="
echo "Starting Kubernetes Configuration Validation..."
echo "Target File: $YAML_FILE"
echo "=================================================="

# Check if file exists
if [ ! -f "$YAML_FILE" ]; then
    echo "ERROR: File $YAML_FILE not found!"
    exit 1
fi

errors=0

# Helper function to check patterns
check_pattern() {
    local pattern="$1"
    local description="$2"
    if grep -q "$pattern" "$YAML_FILE"; then
        echo "  [PASS] $description"
    else
        echo "  [FAIL] $description (Missing pattern: $pattern)"
        errors=$((errors + 1))
    fi
}

echo "1. Checking Namespace definitions..."
check_pattern "namespace: dairy-supplychain" "Namespace 'dairy-supplychain' configured"

echo "2. Checking Resource Limits and Requests..."
check_pattern "cpu: \"1.0\"" "CPU limit is set to 1.0"
check_pattern "memory: \"1024Mi\"" "Memory limit is set to 1024Mi"
check_pattern "cpu: \"0.5\"" "CPU request is set to 0.5"
check_pattern "memory: \"512Mi\"" "Memory request is set to 512Mi"

echo "3. Checking Readiness & Liveness Probes..."
check_pattern "path: /healthz" "Liveness probe endpoint is set to /healthz"
check_pattern "path: /ready" "Readiness probe endpoint is set to /ready"
check_pattern "port: 8000" "Probe port is configured to 8000"

echo "4. Checking Secrets and Environment Config..."
check_pattern "name: database-credentials" "Environment references database-credentials secret"
check_pattern "key: connection-string" "Environment references connection-string key"

echo "5. Checking Service Definition..."
check_pattern "kind: Service" "Service definition is present"
check_pattern "targetPort: 8000" "Service targetPort is 8000"

echo "6. Running dry-run validation if kubectl is present..."
if command -v kubectl &> /dev/null; then
    echo "kubectl detected. Executing client dry-run validation..."
    if kubectl apply --dry-run=client -f "$YAML_FILE" &> /dev/null; then
        echo "  [PASS] kubectl dry-run client validation succeeded"
    else
        echo "  [FAIL] kubectl dry-run client validation failed"
        errors=$((errors + 1))
    fi
else
    echo "  [INFO] kubectl not found on this host. Skipping dry-run validation."
fi

echo "=================================================="
if [ $errors -eq 0 ]; then
    echo "SUCCESS: Kubernetes configurations are valid and conform to spec."
    exit 0
else
    echo "FAILURE: Detected $errors validation error(s)."
    exit 1
fi
