#!/usr/bin/env bash
# tests/test_single_disk_workload.sh — L1 unit tests for workload generator
# Run: bash tests/test_single_disk_workload.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKLOAD_SCRIPT="${REPO_ROOT}/tools/single_disk_workload_profile.sh"

PASS=0
FAIL=0

assert_pass() { PASS=$((PASS+1)); echo "  ✓ $1"; }
assert_fail() { FAIL=$((FAIL+1)); echo "  ✗ $1"; }

# --- Test 1: syntax check ---
echo "Test 1: bash -n syntax check"
if bash -n "$WORKLOAD_SCRIPT"; then
  assert_pass "syntax valid"
else
  assert_fail "syntax error"
fi

# --- Test 2: --help / no-arg behavior is sane ---
echo "Test 2: default invocation with tiny cap produces JSONL output"
TMP="/tmp/test_workload_$$"
mkdir -p "$TMP"
if WORKDIR="$TMP" TOTAL_WRITE_CAP_MIB=4 PHASES=write \
     bash "$WORKLOAD_SCRIPT" > "$TMP/out.jsonl" 2>"$TMP/err.log"; then
  if grep -q '"phase":"write"' "$TMP/out.jsonl"; then
    assert_pass "write phase JSONL emitted"
  else
    assert_fail "write phase JSONL missing"
    cat "$TMP/out.jsonl"
  fi
else
  assert_fail "workload exited non-zero"
  cat "$TMP/err.log"
fi
rm -rf "$TMP"

# --- Test 3: all 3 phases ---
echo "Test 3: write+read+mixed all run"
TMP="/tmp/test_workload_$$"
mkdir -p "$TMP"
if WORKDIR="$TMP" TOTAL_WRITE_CAP_MIB=4 PHASES=write,read,mixed \
     bash "$WORKLOAD_SCRIPT" > "$TMP/out.jsonl" 2>"$TMP/err.log"; then
  lines=$(wc -l < "$TMP/out.jsonl")
  if [[ "$lines" -eq 3 ]]; then
    assert_pass "3 phases produced 3 JSONL lines"
  else
    assert_fail "expected 3 lines, got $lines"
  fi
  for p in write read mixed; do
    if grep -q "\"phase\":\"$p\"" "$TMP/out.jsonl"; then
      assert_pass "phase '$p' present"
    else
      assert_fail "phase '$p' missing"
    fi
  done
else
  assert_fail "3-phase workload failed"
  cat "$TMP/err.log"
fi
rm -rf "$TMP"

# --- Test 4: G1 hard limit (>10240 MiB) refused ---
echo "Test 4: G1 hard limit (TOTAL_WRITE_CAP_MIB=99999) rejected"
TMP="/tmp/test_workload_$$"
mkdir -p "$TMP"
if WORKDIR="$TMP" TOTAL_WRITE_CAP_MIB=99999 PHASES=write \
     bash "$WORKLOAD_SCRIPT" > "$TMP/out.jsonl" 2>"$TMP/err.log"; then
  assert_fail "G1 hard limit NOT enforced (should have failed)"
else
  if grep -q "G1 violated" "$TMP/err.log"; then
    assert_pass "G1 hard limit enforced"
  else
    assert_fail "G1 failed but wrong error message"
    cat "$TMP/err.log"
  fi
fi
rm -rf "$TMP"

# --- Test 5: G2 concurrency cap ---
echo "Test 5: G2 hard limit (MAX_CONCURRENT_DD=99) rejected"
TMP="/tmp/test_workload_$$"
mkdir -p "$TMP"
if WORKDIR="$TMP" TOTAL_WRITE_CAP_MIB=4 MAX_CONCURRENT_DD=99 PHASES=write \
     bash "$WORKLOAD_SCRIPT" > "$TMP/out.jsonl" 2>"$TMP/err.log"; then
  assert_fail "G2 hard limit NOT enforced"
else
  if grep -q "G2 violated" "$TMP/err.log"; then
    assert_pass "G2 hard limit enforced"
  else
    assert_fail "G2 failed but wrong error"
    cat "$TMP/err.log"
  fi
fi
rm -rf "$TMP"

# --- Test 6: unknown phase rejected ---
echo "Test 6: unknown phase rejected"
TMP="/tmp/test_workload_$$"
mkdir -p "$TMP"
if WORKDIR="$TMP" TOTAL_WRITE_CAP_MIB=4 PHASES=write,bogus \
     bash "$WORKLOAD_SCRIPT" > "$TMP/out.jsonl" 2>"$TMP/err.log"; then
  assert_fail "unknown phase NOT rejected"
else
  if grep -q "unknown phase" "$TMP/err.log"; then
    assert_pass "unknown phase rejected with clear error"
  else
    assert_fail "wrong error for unknown phase"
    cat "$TMP/err.log"
  fi
fi
rm -rf "$TMP"

# --- Summary ---
echo ""
echo "=================================="
echo "single_disk_workload: $PASS pass, $FAIL fail"
echo "=================================="
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
