#!/usr/bin/env bash
# 全部 S2-S5 测试一次跑完，汇总成绩
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

run_test "S2 deployment_mode_detector (14 cases)" \
         "bash tests/test_deployment_mode_detector.sh"

run_test "S2 smoke config_loader" \
         "bash tests/smoke_config_loader_s2.sh"

run_test "S3 cgroup_collector (14 cases)" \
         "python3 tests/test_cgroup_collector.py"

run_test "S4 k8s_manifests (19 cases)" \
         "python3 tests/test_k8s_manifests.py"

run_test "S5 K8s API stack (36 cases)" \
         "python3 tests/test_s5_k8s_stack.py"

run_test "S5 smoke (import chain)" \
         "python3 tests/smoke_s5.py"

run_test "S2-S5 integration import" \
         "python3 tests/integration_s2_s5_import_chain.py"

run_test "S2-S3-S4 integration full chain" \
         "bash tests/integration_s2_s3_full_chain.sh"

echo
echo "═══════════════════════════════════════════"
echo "  Total test files: $((GREEN + RED))  |  PASS: $GREEN  |  FAIL: $RED"
echo "═══════════════════════════════════════════"
exit $RED
