#!/usr/bin/env bash
# tests/test_e2e_smoke_harness.sh — L2 integration test for e2e_smoke.sh
# Tests harness wiring (syntax, deps, --help-equivalent dry-run) without
# running the full 30s smoke loop (that's the actual L3 — see CI/SE script).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
E2E_SCRIPT="${REPO_ROOT}/tools/e2e_smoke.sh"

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
for f in tools/mock_rpc_server.py tools/single_disk_workload_profile.sh monitoring/unified_monitor.sh; do
  if [[ -f "${REPO_ROOT}/${f}" ]]; then
    assert_pass "ref '$f' exists"
  else
    assert_fail "ref '$f' MISSING"
  fi
done

# --- Test 4: smoke runs end-to-end with tiny params ---
echo "Test 4: end-to-end smoke run (10s duration, 4 MiB workload)"
TMP="/tmp/e2e_smoke_test_$$"
mkdir -p "$TMP"
if OUTPUT_DIR="$TMP" DURATION_SEC=5 WORKLOAD_CAP_MIB=4 SKIP_HTML=1 \
     bash "$E2E_SCRIPT" > "$TMP.out" 2>&1; then
  assert_pass "e2e_smoke exited 0"
  if grep -q "e2e_smoke: PASS" "$TMP.out"; then
    assert_pass "PASS summary emitted"
  else
    assert_fail "PASS summary missing"
    tail -30 "$TMP.out"
  fi
  if grep -q "mock RPC ready" "$TMP.out"; then
    assert_pass "mock RPC node started successfully"
  else
    assert_fail "mock RPC did not become ready"
    tail -30 "$TMP.out"
  fi
  if grep -q "workload JSONL produced" "$TMP.out"; then
    assert_pass "workload phase logged JSONL"
  else
    assert_fail "workload JSONL missing"
  fi
else
  rc=$?
  assert_fail "e2e_smoke exited non-zero (rc=$rc)"
  tail -40 "$TMP.out"
fi
rm -rf "$TMP" "$TMP.out"

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
echo "e2e_smoke_harness: $PASS pass, $FAIL fail"
echo "=================================="
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
