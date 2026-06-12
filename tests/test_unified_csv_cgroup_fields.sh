#!/usr/bin/env bash
# tests/test_unified_csv_cgroup_fields.sh
# Proves cgroup_collector.py is wired into unified_monitor.sh main pipeline.
# This test verifies cgroup_collector is part of the active monitoring pipeline.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
UNIFIED="${REPO_ROOT}/monitoring/unified_monitor.sh"
COLLECTOR="${REPO_ROOT}/monitoring/cgroup_collector.py"

PASS=0
FAIL=0
assert_pass() { PASS=$((PASS+1)); echo "  ✓ $1"; }
assert_fail() { FAIL=$((FAIL+1)); echo "  ✗ $1"; }

# --- Test 1: source files exist ---
echo "Test 1: source files exist"
for f in "$UNIFIED" "$COLLECTOR"; do
  [[ -f "$f" ]] && assert_pass "exists: ${f##*/}" || assert_fail "missing: $f"
done

# --- Test 2: get_cgroup_header / get_cgroup_data functions defined ---
echo "Test 2: helper functions defined in unified_monitor.sh"
for fn in get_cgroup_header get_cgroup_data; do
  if grep -qE "^${fn}\(\)" "$UNIFIED"; then
    assert_pass "function $fn defined"
  else
    assert_fail "function $fn NOT defined (regression!)"
  fi
done

# --- Test 3: generate_csv_header calls get_cgroup_header ---
echo "Test 3: generate_csv_header wires cgroup_header"
if grep -A 20 'generate_csv_header()' "$UNIFIED" | grep -q 'cgroup_header=$(get_cgroup_header)'; then
  assert_pass "generate_csv_header calls get_cgroup_header"
else
  assert_fail "generate_csv_header does NOT call get_cgroup_header"
fi

# --- Test 4: data_line includes cgroup_data ---
echo "Test 4: log_performance_data wires cgroup_data into data_line"
ena_branch=$(grep -A 100 'log_performance_data()' "$UNIFIED" | grep -c '$cgroup_data' || true)
if [[ "$ena_branch" -ge 2 ]]; then
  assert_pass "data_line includes \$cgroup_data in both ENA + non-ENA branches"
else
  assert_fail "data_line missing \$cgroup_data (found $ena_branch refs, need ≥2)"
fi

# --- Test 5: collector --header/--data produce 19 fields ---
echo "Test 5: cgroup_collector.py contract (19 fields)"
header_n=$(python3 "$COLLECTOR" --header 2>/dev/null | tr ',' '\n' | wc -l)
if [[ "$header_n" -eq 19 ]]; then
  assert_pass "--header → 19 fields"
else
  assert_fail "--header → $header_n fields (expected 19)"
fi
data_n=$(python3 "$COLLECTOR" --data 2>/dev/null | tr ',' '\n' | wc -l)
if [[ "$data_n" -eq 19 ]]; then
  assert_pass "--data → 19 fields"
else
  assert_fail "--data → $data_n fields (expected 19)"
fi

# --- Test 6: disabled flag honored ---
echo "Test 6: CGROUP_COLLECTOR_ENABLED=false produces 19 placeholder fields"
# Source unified_monitor in a subshell to grab the function only
disabled_out=$(bash -c "
  CGROUP_COLLECTOR_ENABLED=false
  source <(sed -n '/^get_cgroup_data()/,/^}/p' '$UNIFIED')
  get_cgroup_data
")
fields_n=$(echo "$disabled_out" | tr ',' '\n' | wc -l)
if [[ "$fields_n" -eq 19 ]]; then
  assert_pass "disabled mode emits 19 placeholder fields"
else
  assert_fail "disabled mode emitted $fields_n fields"
fi
if echo "$disabled_out" | grep -q "disabled"; then
  assert_pass "disabled mode meta_source='disabled' sentinel"
else
  assert_fail "disabled mode missing 'disabled' sentinel"
fi

# --- Test 7: missing-collector fallback ---
echo "Test 7: missing collector path produces 19 placeholder fields"
# Move collector aside, source function, run, restore
TMP_COLL="${COLLECTOR}.tmp.$$"
mv "$COLLECTOR" "$TMP_COLL"
trap "mv '$TMP_COLL' '$COLLECTOR'" EXIT
missing_out=$(bash -c "
  source <(sed -n '/^get_cgroup_data()/,/^}/p' '$UNIFIED')
  get_cgroup_data
" 2>/dev/null || echo "")
mv "$TMP_COLL" "$COLLECTOR"
trap - EXIT
fields_n=$(echo "$missing_out" | tr ',' '\n' | wc -l)
if [[ "$fields_n" -eq 19 ]]; then
  assert_pass "missing collector → 19 placeholder fields (fail-soft)"
else
  assert_fail "missing collector emitted $fields_n fields"
fi
if echo "$missing_out" | grep -q "unavailable"; then
  assert_pass "missing collector meta_source='unavailable' sentinel"
else
  assert_fail "missing collector missing 'unavailable' sentinel"
fi

# --- Summary ---
echo ""
echo "=================================="
echo "cgroup_in_unified_csv: $PASS pass, $FAIL fail"
echo "=================================="
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
