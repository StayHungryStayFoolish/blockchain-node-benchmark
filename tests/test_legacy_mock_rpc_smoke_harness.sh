#!/usr/bin/env bash
# tests/test_legacy_mock_rpc_smoke_harness.sh
# Tests legacy harness wiring without running the full smoke loop. The complete
# benchmark lifecycle is covered by the fake-node entrypoint smoke.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
E2E_SCRIPT="${REPO_ROOT}/tools/legacy_mock_rpc_e2e_smoke.sh"

PASS=0
FAIL=0

assert_pass() { PASS=$((PASS+1)); echo "  ✓ $1"; }
assert_fail() { FAIL=$((FAIL+1)); echo "  ✗ $1"; }

# --- Test 1: syntax check ---
echo "Test 1: bash -n syntax check"
if bash -n "$E2E_SCRIPT"; then
  assert_pass "syntax valid"
else
  assert_fail "syntax error"
fi

# --- Test 2: required deps present ---
echo "Test 2: required dependencies installed"
for cmd in bash python3 curl dd awk grep; do
  if command -v "$cmd" >/dev/null 2>&1; then
    assert_pass "dep '$cmd' present"
  else
    assert_fail "dep '$cmd' missing"
  fi
done

# --- Test 3: referenced files exist ---
echo "Test 3: referenced sub-scripts exist"
for f in tools/legacy_mock_rpc_server.py tools/single_disk_workload_profile.sh monitoring/unified_monitor.sh; do
  if [[ -f "${REPO_ROOT}/${f}" ]]; then
    assert_pass "ref '$f' exists"
  else
    assert_fail "ref '$f' MISSING"
  fi
done

# --- Test 4: script wiring references the legacy mock RPC server ---
echo "Test 4: script wiring"
if grep -q "tools/legacy_mock_rpc_server.py" "$E2E_SCRIPT"; then
  assert_pass "legacy mock RPC server referenced"
else
  assert_fail "legacy mock RPC server reference missing"
fi

if grep -q "tools/single_disk_workload_profile.sh" "$E2E_SCRIPT"; then
  assert_pass "single disk workload referenced"
else
  assert_fail "single disk workload reference missing"
fi

if grep -q "legacy_mock_rpc_e2e_smoke: PASS" "$E2E_SCRIPT"; then
  assert_pass "PASS summary string present"
else
  assert_fail "PASS summary string missing"
fi

# --- Test 5: cleanup happens on early exit ---
echo "Test 5: trap cleanup is wired"
if grep -q "trap cleanup EXIT" "$E2E_SCRIPT"; then
  assert_pass "EXIT trap present"
else
  assert_fail "EXIT trap missing — leaks subprocesses on error"
fi

# --- Summary ---
echo ""
echo "=================================="
echo "legacy_mock_rpc_smoke_harness: $PASS pass, $FAIL fail"
echo "=================================="
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
