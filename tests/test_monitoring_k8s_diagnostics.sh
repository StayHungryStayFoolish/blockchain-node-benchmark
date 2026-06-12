#!/usr/bin/env bash
# Test monitoring_coordinator.sh s5_diag subcommand
# Integration test for monitoring_coordinator.sh s5_diag output contract.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO/monitoring/monitoring_coordinator.sh"

PASS=0
FAIL=0
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }
pass() { echo "  ✓ $1"; PASS=$((PASS+1)); }

echo "=== test_monitoring_k8s_diagnostics.sh ==="

# 1. Subcommand exists and is listed by show_usage.
if grep -q '"s5_diag"' "$SCRIPT" && grep -q 's5_diag.*cgroup' "$SCRIPT"; then
    pass "s5_diag dispatch case and show_usage entry exist"
else
    fail "s5_diag is missing"
fi

# 2. All three diagnostic helpers are referenced.
for tool in cgroup_collector pod_device_mapper kubelet_stats_client; do
    if grep -q "$tool" "$SCRIPT"; then
        pass "called $tool"
    else
        fail "did not call $tool"
    fi
done

# 3. Real run on a non-K8s host should exit cleanly and print all three sections.
OUT="$(bash "$SCRIPT" s5_diag 2>&1)"
RC=$?
if [[ $RC -eq 0 ]]; then
    pass "exit code 0"
else
    fail "exit code $RC"
fi

for marker in "[1/3] cgroup_collector" "[2/3] pod_device_mapper" "[3/3] kubelet_stats_client" "Diagnostics complete"; do
    if echo "$OUT" | grep -qF "$marker"; then
        pass "output contains: $marker"
    else
        fail "output missing: $marker"
    fi
done

# 4. cgroup 19-field contract (header/data each 19 fields)
if echo "$OUT" | grep -qE 'header  \(19 fields\)'; then
    pass "cgroup header 19 fields"
else
        fail "cgroup header field count is incorrect"
fi
if echo "$OUT" | grep -qE 'data    \(19 fields\)'; then
    pass "cgroup data 19 fields"
else
        fail "cgroup data field count is incorrect"
fi

# 5. Non-Kubernetes environments skip the Kubernetes sections correctly.
if echo "$OUT" | grep -q "Skip (DEPLOYMENT_MODE != k8s"; then
    pass "pod_device_mapper skipped correctly on non-K8s"
else
    fail "pod_device_mapper did not skip"
fi
if echo "$OUT" | grep -q "Skipped (requires DEPLOYMENT_MODE=k8s"; then
    pass "kubelet_stats_client skipped correctly on non-K8s"
else
    fail "kubelet_stats_client did not skip"
fi

# 6. meta_source is in the valid value set.
if echo "$OUT" | grep -qE 'meta_source = (v2|v1|unmounted|unresolved|disabled|error|k8s_fallback)'; then
    pass "meta_source is in the valid value set"
else
    fail "meta_source is not in the valid value set"
fi

echo ""
echo "PASS: $PASS  FAIL: $FAIL"
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
