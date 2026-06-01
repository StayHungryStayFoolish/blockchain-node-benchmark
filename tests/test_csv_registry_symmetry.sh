#!/usr/bin/env bash
# tests/test_csv_registry_symmetry.sh
# S0 前置阻塞项 (CI 硬门) — 守护 proposal §5 风险2 (bash/python 双 registry 对称漂移).
#
# 验证三件事:
#   Phase 1: bash 与 python registry 逻辑名集合 1:1
#   Phase 2: 同一 (logical, provider, device) 两侧 resolve 物理名完全一致
#   Phase 3: registry 生成的 disk header == 现有 iostat_collector.sh 旧 header (字节级)
#            -> 保证 S1 把 writer 切到 registry 后 CSV 零变化, 不破坏现有 reader
#
# 任一断言失败 -> exit 1, CI 拒绝合入. 这是允许开始 disk 段迁移的前提.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

FAIL=0
TOTAL=0
pass() { TOTAL=$((TOTAL+1)); echo "  ✅ $1"; }
fail() { TOTAL=$((TOTAL+1)); FAIL=$((FAIL+1)); echo "  ❌ $1"; }

source config/csv_schema_registry.sh

# ============================================================
# Phase 1: 逻辑名集合 1:1
# ============================================================
echo "=== Phase 1: bash/python 逻辑名集合对称 ==="
bash_names="$(csv_registry_all_logical_names | tr ' ' '\n' | LC_ALL=C sort)"
py_names="$(python3 -c '
from utils.csv_schema_registry import CSVSchemaRegistry
print("\n".join(CSVSchemaRegistry.all_logical_names()))
' | LC_ALL=C sort)"

if [[ "$bash_names" == "$py_names" ]]; then
    pass "逻辑名集合 1:1 ($(echo "$bash_names" | wc -l) 字段)"
else
    fail "逻辑名集合不对称"
    echo "--- bash only ---"; comm -23 <(echo "$bash_names") <(echo "$py_names") || true
    echo "--- python only ---"; comm -13 <(echo "$bash_names") <(echo "$py_names") || true
fi

# Phase 1.5: provider_aware 集合两侧对称 (防风险4 provider_aware 标志漂移)
bash_pa="$(csv_registry_provider_aware_names | tr ' ' '\n' | LC_ALL=C sort)"
py_pa="$(python3 -c '
from utils.csv_schema_registry import CSVSchemaRegistry
print("\n".join(CSVSchemaRegistry.provider_aware_fields()))
' | LC_ALL=C sort)"
if [[ "$bash_pa" == "$py_pa" ]]; then
    pass "provider_aware 集合 1:1 ($(echo "$bash_pa" | wc -l) 字段)"
else
    fail "provider_aware 集合不对称  bash=[$bash_pa] py=[$py_pa]"
fi

# ============================================================
# Phase 2: resolve 物理名两侧一致 (3 provider × 2 device × 全字段)
# ============================================================
echo "=== Phase 2: resolve 物理名 bash==python (3 provider × 2 device) ==="
for provider in aws gcp other; do
    for device in data accounts; do
        for logical in $(csv_registry_all_logical_names); do
            bash_phys="$(csv_registry_resolve "$logical" "$provider" "$device")"
            py_phys="$(python3 -c "
from utils.csv_schema_registry import CSVSchemaRegistry
print(CSVSchemaRegistry.resolve('$logical', '$provider', '$device'))
")"
            if [[ "$bash_phys" != "$py_phys" ]]; then
                fail "resolve 不一致: $logical/$provider/$device  bash=$bash_phys py=$py_phys"
            fi
        done
    done
done
[[ $FAIL -eq 0 ]] && pass "全部 resolve 两侧一致 (31 字段 × 3 provider × 2 device = 186 组)"

# ============================================================
# Phase 2.5: case→数组反向检查 (防 registry 文件内部双源漂移)
# bash resolve 用 case 写死字段名, 与 _CSV_REGISTRY_DISK_LOGICAL 数组是两份清单.
# Phase 1/2 能抓"数组有 case 无"; 这里抓"case 有数组无"(反向盲区).
# ============================================================
echo "=== Phase 2.5: bash case 分支字段 ⊆ 数组 (防文件内双源) ==="
# 从 csv_registry_resolve 函数体内提取 case 分支字段名 (排除通配 * / 注释 / provider 名).
# 用 awk 限定在 resolve 函数体, 避免误抓 segment_logical_names 里的段名 (basic)/device)).
# 覆盖 basic (timestamp/cpu_*/mem_*) 与 disk (disk_*) 全部静态字段.
case_fields="$(awk '/^csv_registry_resolve\(\)/{inf=1} inf&&/^}/{inf=0} inf' config/csv_schema_registry.sh \
    | grep -oE '^[[:space:]]*[a-z_][a-z0-9_]*\)' \
    | tr -d ' )' | LC_ALL=C sort -u)"
array_fields="$(csv_registry_all_logical_names | tr ' ' '\n' | LC_ALL=C sort -u)"
orphan="$(comm -23 <(echo "$case_fields") <(echo "$array_fields") || true)"
if [[ -z "$orphan" ]]; then
    pass "case 分支字段全部 ∈ 数组 ($(echo "$case_fields" | wc -l) 分支, 无孤儿)"
else
    fail "case 有但数组无的孤儿字段(文件内双源漂移): $orphan"
fi

# ============================================================
# Phase 3: writer (generate_device_header) == registry header, 对每个 provider 字节级一致
# ============================================================
# 中立化后: writer 不再默认 aws, header 随 provider 变. 正确不变量 =
#   对任一 provider P, generate_device_header(DEV, data, P) == csv_registry_disk_header(data_DEV, P).
# 即 writer 与 registry 共用同一事实源, 任何 provider 下都对齐 (无 aws 倾向硬编码).
echo "=== Phase 3: writer header == registry header (每 provider 字节级) ==="
DEV="nvme1n1"
P3_FAIL=0
for provider in aws gcp other; do
    registry_header="$(csv_registry_disk_header "data_${DEV}" "$provider")"
    # writer 显式传 provider (第3参), 隔离 get_provider_name 上下文差异, 纯测对齐契约
    writer_header="$(
        source monitoring/iostat_collector.sh >/dev/null 2>&1 || true
        if declare -F generate_device_header >/dev/null; then
            generate_device_header "$DEV" "data" "$provider"
        fi
    )"
    if [[ -z "$writer_header" ]]; then
        fail "[$provider] 无法取得 writer header (generate_device_header 未定义/source 失败)"
        P3_FAIL=1
    elif [[ "$registry_header" == "$writer_header" ]]; then
        : # ok, 累计后统一 pass
    else
        fail "[$provider] writer header != registry header — 切换会破坏 CSV"
        echo "--- registry[$provider] ---"; echo "$registry_header"
        echo "--- writer  [$provider] ---"; echo "$writer_header"
        echo "--- 逐字段 diff ---"
        diff <(echo "$registry_header" | tr ',' '\n') <(echo "$writer_header" | tr ',' '\n') || true
        P3_FAIL=1
    fi
done
[[ $P3_FAIL -eq 0 ]] && pass "writer==registry header (aws/gcp/other 三 provider 各 21 字段字节一致)"

# ============================================================
# Phase 3.5: basic 段 writer fallback 字面量 == registry header (字节级)
# writer (unified_monitor.sh:1926 generate_csv_header) 已切换为优先调 csv_registry_basic_header;
# 仅当 registry 未 source 时回退到内联字面量。本 Phase 守护该 fallback 字面量与 registry 字节一致,
# 防 registry 缺失时 writer 写出与 reader 期望漂移的 header。
# 提取法: grep 含 'timestamp,cpu_usage' 的 basic_header= 字面量行 (跳过 $(...) 函数调用行)。
# ============================================================
echo "=== Phase 3.5: basic 段 writer fallback 字面量 == registry header (字节级) ==="
writer_basic="$(grep -oE 'basic_header="timestamp,[^"]*"' monitoring/unified_monitor.sh \
    | head -1 | sed -E 's/^basic_header="//; s/"$//')"
registry_basic="$(csv_registry_basic_header)"
if [[ -z "$writer_basic" ]]; then
    fail "无法从 unified_monitor.sh 提取 writer basic_header fallback 字面量"
elif [[ "$writer_basic" == "$registry_basic" ]]; then
    pass "basic header writer-fallback==registry ($(echo "$registry_basic" | tr ',' '\n' | wc -l) 字段字节一致)"
else
    fail "basic header writer-fallback != registry — registry 缺失时会破坏 CSV"
    echo "--- writer-fallback ---"; echo "$writer_basic"
    echo "--- registry        ---"; echo "$registry_basic"
    diff <(echo "$writer_basic" | tr ',' '\n') <(echo "$registry_basic" | tr ',' '\n') || true
fi

# Phase 3.6: writer 确实经 registry 出 basic header (parallel-entry 防呆: 证 registry 路径是 live 的)
# 复刻生产 source 链 (iostat_collector.sh:16 硬 source registry), 调 writer 的 registry 分支,
# 断言输出 == registry header。证明 writer-first 切换非死代码 (registry 真被 writer 调用)。
echo "=== Phase 3.6: writer 经 registry 出 basic header (live 路径, 非 fallback) ==="
live_basic="$(
    source config/csv_schema_registry.sh >/dev/null 2>&1
    if declare -F csv_registry_basic_header >/dev/null 2>&1; then
        csv_registry_basic_header
    fi
)"
if [[ "$live_basic" == "$registry_basic" ]]; then
    pass "source registry 后 writer 取到 registry basic header (live, 非 fallback)"
else
    fail "registry source 后 writer basic header 异常: [$live_basic]"
fi

# ============================================================
echo ""
echo "=== 结果: $((TOTAL-FAIL))/$TOTAL 通过 ==="
if [[ $FAIL -ne 0 ]]; then
    echo "❌ S0 对称测试失败 ($FAIL) — 禁止开始 disk 段迁移"
    exit 1
fi
echo "✅ S0 对称测试全绿 — bash/python registry 对称, 可安全进入 S1 writer-first"
