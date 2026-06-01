#!/usr/bin/env bash
# ci/check_csv_registry_bypass.sh
# CI 门 — 守护 proposal §5 风险1/4 (防 reader 绕过 registry 写裸 provider_aware 物理名).
#
# 机制 (仿 ci/check_parallel_entry.sh v1.4.5 的"已迁移文件清单"模式):
#   - provider_aware 物理名 (normalized_iops / normalized_throughput_mibs / baseline_iops / ...)
#     一旦某文件被迁移到 registry, 就加入 MIGRATED 清单
#   - MIGRATED 清单里的文件若再出现裸 provider_aware 物理名 -> CI 失败 (回归门)
#   - 未迁移文件暂不强制 (S0 基线; 随 S1~S6 推进逐个移入 MIGRATED)
#
# S0 状态: MIGRATED 为空 (还没迁移任何 reader). 此门此刻只建立基线 + 框架.
# S1 起: 每迁移完一个 reader, 把它加进 MIGRATED_FILES, 该文件从此被门守护.

set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# provider_aware 物理名的"裸字符串"正则.
#   - normalized_* 形态: 三云统一折算值物理前缀 (registry: aws/gcp/other -> normalized).
#     但 normalized 是高频同名异义词 (sklearn/statsmodels 等第三方: is_normalized /
#     normalized_cov_params / coef_normalized ...). 故 NOT 裸抓 normalized_iops;
#     只把"真·CSV 物理列名形态" (data|accounts)_<device>_normalized_(iops|throughput)
#     (三段, 中间 device 段) 判为违规 — 与 baseline 形态同款防误报策略.
#   - baseline_* 形态: 与 Disk 配置阈值键/变量同名异义 (DATA_VOL_MAX_IOPS 派生).
#     CSV 物理列名 = (data|accounts)_<device>_baseline_*  (三段, 中间 device 段);
#     配置项 = data_baseline_* (两段) 或裸变量 baseline_* . 故只把"带 device 段"的 baseline 形态判为违规.
# VIOLATION_PATTERN = reader 不得裸写的真·CSV 物理列名形态.
VIOLATION_PATTERN='(data|accounts)_[a-z0-9]+_normalized_(iops|throughput)|(data|accounts)_[a-z0-9]+_baseline_(iops|throughput)'
# 兼容旧变量名 (S0 注释/历史引用)
BARE_PATTERN="$VIOLATION_PATTERN"

# 已迁移文件清单 (随 S1~S6 推进追加; S0 为空)
MIGRATED_FILES=(
    # S1 disk reader 迁移后逐个加入:
    tools/disk_bottleneck_detector.sh
    monitoring/bottleneck_detector.sh
)

# 允许保留裸名的文件 (registry 自身 + writer 模板 + 对称测试 + 本门 + provider 定义)
# 这些是"物理名的合法定义处", 不算绕过
ALLOWLIST_REGEX='^(config/csv_schema_registry\.sh|utils/csv_schema_registry\.py|config/providers/|tests/test_csv_registry_symmetry|ci/check_csv_registry_bypass|monitoring/iostat_collector\.sh)'

FAIL=0
echo "=== CSV registry bypass 门 (MIGRATED: ${#MIGRATED_FILES[@]} 文件) ==="

if [[ ${#MIGRATED_FILES[@]} -eq 0 ]]; then
    echo "  ℹ️  S0 基线: 尚无已迁移文件, 门处于待命状态 (框架就绪)"
    echo "  ℹ️  当前全仓裸 provider_aware 物理名分布 (供 S1 迁移参考):"
    grep -rlE "$BARE_PATTERN" --include='*.py' --include='*.sh' . 2>/dev/null \
        | grep -vE "$ALLOWLIST_REGEX" | sed 's/^/      /' || echo "      (无)"
    echo "✅ S0 grep gate 框架就绪"
    exit 0
fi

# S1+ : 检查每个已迁移文件是否还有裸名
for f in "${MIGRATED_FILES[@]}"; do
    if [[ ! -f "$f" ]]; then
        echo "  ⚠️  MIGRATED 清单文件不存在: $f (清单过期?)"
        continue
    fi
    # 用 VIOLATION_PATTERN 直接匹配真·CSV 物理列名 (已通过结构区分排除同名异义配置项)
    hits="$(grep -nE "$VIOLATION_PATTERN" "$f" 2>/dev/null || true)"
    if [[ -n "$hits" ]]; then
        echo "  ❌ 已迁移文件仍有裸 provider_aware 物理名: $f"
        echo "$hits" | sed 's/^/        /'
        FAIL=$((FAIL+1))
    else
        echo "  ✅ $f 无裸名 (已正确经 registry)"
    fi
done

if [[ $FAIL -ne 0 ]]; then
    echo "❌ registry bypass 门失败 ($FAIL 文件) — 迁移后的 reader 不得裸写 provider_aware 物理名"
    exit 1
fi
echo "✅ registry bypass 门通过"
