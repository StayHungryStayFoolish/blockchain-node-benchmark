#!/usr/bin/env bash
# Test monitoring_coordinator.sh s5_diag subcommand
# L2: 真调 monitoring_coordinator.sh s5_diag,验输出契约。
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO/monitoring/monitoring_coordinator.sh"

PASS=0
FAIL=0
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }
pass() { echo "  ✓ $1"; PASS=$((PASS+1)); }

echo "=== test_s5_diag.sh ==="

# 1. 子命令存在 (show_usage 列出)
if grep -q '"s5_diag"' "$SCRIPT" && grep -q 's5_diag.*S5 cgroup' "$SCRIPT"; then
    pass "s5_diag dispatch case + show_usage 条目都在"
else
    fail "s5_diag 缺失"
fi

# 2. 三件套都被调
for tool in cgroup_collector pod_device_mapper kubelet_stats_client; do
    if grep -q "$tool" "$SCRIPT"; then
        pass "调到 $tool"
    else
        fail "未调 $tool"
    fi
done

# 3. 真跑 (本机非 k8s,应正常退出 + 三段输出齐)
OUT="$(bash "$SCRIPT" s5_diag 2>&1)"
RC=$?
if [[ $RC -eq 0 ]]; then
    pass "退出码 0"
else
    fail "退出码 $RC"
fi

for marker in "[1/3] cgroup_collector" "[2/3] pod_device_mapper" "[3/3] kubelet_stats_client" "诊断完成"; do
    if echo "$OUT" | grep -qF "$marker"; then
        pass "输出含: $marker"
    else
        fail "输出缺: $marker"
    fi
done

# 4. cgroup 19 字段契约 (header/data 各 19)
if echo "$OUT" | grep -qE 'header  \(19 fields\)'; then
    pass "cgroup header 19 fields"
else
    fail "cgroup header 字段数不对"
fi
if echo "$OUT" | grep -qE 'data    \(19 fields\)'; then
    pass "cgroup data 19 fields"
else
    fail "cgroup data 字段数不对"
fi

# 5. 非 k8s 环境正确跳过 K8s 两段
if echo "$OUT" | grep -q "跳过 (DEPLOYMENT_MODE != k8s)"; then
    pass "pod_device_mapper 在非 k8s 正确跳过"
else
    fail "pod_device_mapper 未跳过"
fi
if echo "$OUT" | grep -q "跳过 (需 DEPLOYMENT_MODE=k8s"; then
    pass "kubelet_stats_client 在非 k8s 正确跳过"
else
    fail "kubelet_stats_client 未跳过"
fi

# 6. meta_source 在合法值集
if echo "$OUT" | grep -qE 'meta_source = (v2|v1|unmounted|unresolved|disabled|error|k8s_fallback)'; then
    pass "meta_source 在合法值集"
else
    fail "meta_source 不在合法值集"
fi

echo ""
echo "PASS: $PASS  FAIL: $FAIL"
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
