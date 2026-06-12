#!/usr/bin/env bash
# tests/test_ci_check_parallel_entry.sh
# L2: verify ci/check_parallel_entry.sh positive and negative paths.
# Verifies that removing a required caller reference causes the guard to fail.

set -u
cd "$(dirname "$0")/.."

pass=0
fail=0

check() {
    local name="$1"
    local expected="$2"
    local actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        echo "PASS: $name (exit=$actual)"
        pass=$((pass + 1))
    else
        echo "FAIL: $name (expected exit=$expected got=$actual)"
        fail=$((fail + 1))
    fi
}

# T1: positive path.
bash ci/check_parallel_entry.sh >/dev/null 2>&1
check "T1 baseline POS" 0 $?

# T2: removing cgroup_collector.py should fail.
mv monitoring/cgroup_collector.py monitoring/cgroup_collector.py.tmp
bash ci/check_parallel_entry.sh >/dev/null 2>&1
rc=$?
mv monitoring/cgroup_collector.py.tmp monitoring/cgroup_collector.py
check "T2 missing file NEG" 1 $rc

# T3: breaking unified_monitor.sh's wrapper source should fail.
cp monitoring/unified_monitor.sh /tmp/u_test.bak
perl -0pi -e 's/cgroup_collector_wrapper/XXX_cgroup_collector_wrapper_XXX/g' monitoring/unified_monitor.sh
bash ci/check_parallel_entry.sh >/dev/null 2>&1
rc=$?
cp /tmp/u_test.bak monitoring/unified_monitor.sh
rm -f /tmp/u_test.bak
check "T3 broken caller NEG (word boundary)" 1 $rc

# T4: comment-only references should fail.
cp monitoring/unified_monitor.sh /tmp/u_test.bak
perl -0pi -e 's/^([^#\n]*cgroup_collector_wrapper[^\n]*)/# $1/m' monitoring/unified_monitor.sh
bash ci/check_parallel_entry.sh >/dev/null 2>&1
rc=$?
cp /tmp/u_test.bak monitoring/unified_monitor.sh
rm -f /tmp/u_test.bak
check "T4 comment-only NEG" 1 $rc

# T5: positive path after restoration.
bash ci/check_parallel_entry.sh >/dev/null 2>&1
check "T5 restore-check POS" 0 $?

# T6: syntax check
bash -n ci/check_parallel_entry.sh
check "T6 syntax check" 0 $?

echo "==="
echo "Results: $pass passed, $fail failed"
[[ $fail -eq 0 ]] && exit 0 || exit 1
