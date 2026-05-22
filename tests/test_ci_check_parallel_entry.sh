#!/usr/bin/env bash
# tests/test_ci_check_parallel_entry.sh
# L2: 验 ci/check_parallel_entry.sh 自身正/反向都对
# Round-05 v1.4.5 Step 6 自审收尾:必须验"删 caller 引用真触发 FAIL"

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

# T1: 正向 — 当前 HEAD 应 PASS
bash ci/check_parallel_entry.sh >/dev/null 2>&1
check "T1 baseline POS" 0 $?

# T2: 删 cgroup_collector.py — 应 FAIL (file missing)
mv monitoring/cgroup_collector.py monitoring/cgroup_collector.py.tmp
bash ci/check_parallel_entry.sh >/dev/null 2>&1
rc=$?
mv monitoring/cgroup_collector.py.tmp monitoring/cgroup_collector.py
check "T2 missing file NEG" 1 $rc

# T3: 破坏 unified_monitor.sh 里的 cgroup_collector 引用 — 应 FAIL (no live reference)
cp monitoring/unified_monitor.sh /tmp/u_test.bak
sed -i 's/cgroup_collector/XXX_cgroup_collector_XXX/g' monitoring/unified_monitor.sh
bash ci/check_parallel_entry.sh >/dev/null 2>&1
rc=$?
cp /tmp/u_test.bak monitoring/unified_monitor.sh
rm -f /tmp/u_test.bak
check "T3 broken caller NEG (word boundary)" 1 $rc

# T4: 仅在注释里引用 — 应 FAIL (comment filter)
cp monitoring/unified_monitor.sh /tmp/u_test.bak
sed -i 's/^[^#]*cgroup_collector/# &/' monitoring/unified_monitor.sh
bash ci/check_parallel_entry.sh >/dev/null 2>&1
rc=$?
cp /tmp/u_test.bak monitoring/unified_monitor.sh
rm -f /tmp/u_test.bak
check "T4 comment-only NEG" 1 $rc

# T5: 还原后再跑一次 — 应 PASS (确认 T2-T4 restore 干净)
bash ci/check_parallel_entry.sh >/dev/null 2>&1
check "T5 restore-check POS" 0 $?

# T6: syntax check
bash -n ci/check_parallel_entry.sh
check "T6 syntax check" 0 $?

echo "==="
echo "Results: $pass passed, $fail failed"
[[ $fail -eq 0 ]] && exit 0 || exit 1
