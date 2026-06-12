#!/usr/bin/env bash
# Run the monitoring and K8s test group and summarize results
set -uo pipefail
cd "$(dirname "$0")/.."

GREEN=0
RED=0

run_test() {
    local name="$1"
    local cmd="$2"
    echo "=== $name ==="
    if eval "$cmd" > /tmp/test_out.$$ 2>&1; then
        local last=$(tail -3 /tmp/test_out.$$ | tr '\n' ' ')
        echo "  ✓ PASS — $last"
        ((GREEN++))
    else
        echo "  ✗ FAIL"
        tail -20 /tmp/test_out.$$
        ((RED++))
    fi
    rm -f /tmp/test_out.$$
}

run_test "deployment_mode_detector (14 cases)" \
         "bash tests/test_deployment_mode_detector.sh"

run_test "config_loader smoke" \
         "bash tests/smoke_config_loader_deployment_env.sh"

run_test "cgroup_collector (14 cases)" \
         "python3 tests/test_cgroup_collector.py"

run_test "k8s_manifests (19 cases)" \
         "python3 tests/test_k8s_manifests.py"

run_test "K8s API stack (36 cases)" \
         "python3 tests/test_k8s_monitoring_stack.py"

run_test "K8s smoke (import chain)" \
         "python3 tests/smoke_k8s_helpers_import.py"

run_test "monitoring integration import" \
         "python3 tests/test_monitoring_k8s_import_chain.py"

run_test "full-chain integration full chain" \
         "bash tests/integration_k8s_cgroup_config_chain.sh"

echo
echo "═══════════════════════════════════════════"
echo "  Total test files: $((GREEN + RED))  |  PASS: $GREEN  |  FAIL: $RED"
echo "═══════════════════════════════════════════"
exit $RED
