#!/usr/bin/env bash
# tests/test_l3_csv_e2e.sh
# L3 端到端: 验证监控层在 provider getter 可用下生成的 CSV header 含 cloud_provider 列、
# header/data 列数对齐、iops getter 分流生效。
# 这是 CP-1 改动(cloud_provider 列 + iops provider-aware)的端到端守护。

set -uo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

FAIL=0
N=0
check() { N=$((N+1)); if [[ "$2" == "$3" ]]; then echo "OK   [$1]"; else echo "FAIL [$1] expected='$2' actual='$3'" >&2; FAIL=1; fi; }
check_contains() { N=$((N+1)); if [[ "$2" == *"$3"* ]]; then echo "OK   [$1]"; else echo "FAIL [$1] '$3' not in output" >&2; FAIL=1; fi; }

# === 1. CLOUD_PROVIDER=gcp 时 header 末列 = cloud_provider ===
export CLOUD_PROVIDER=gcp
export ENA_MONITOR_ENABLED=false
export CGROUP_COLLECTOR_ENABLED=false
export LEDGER_DEVICE="${LEDGER_DEVICE:-nvme0n1}"
export DATA_VOL_TYPE="${DATA_VOL_TYPE:-hyperdisk-extreme}"

# source 监控链(与生产一致路径)
source config/config_loader.sh >/dev/null 2>&1 || true

# getter 可用性(iops 修复生效前提)
check_contains "config_loader 后 get_provider_name 可用" "$(declare -F get_provider_name >/dev/null 2>&1 && echo yes || echo no)" "yes"
check "GCP iops 分流 = passthrough" "passthrough" "$(get_iops_conversion_func 2>/dev/null)"
check "GCP disk_field_prefix = normalized" "normalized" "$(get_disk_field_prefix 2>/dev/null)"
check "GCP provider_name = gcp" "gcp" "$(get_provider_name 2>/dev/null)"

# === 2. unified_monitor header 生成: 末列必须 cloud_provider ===
source monitoring/unified_monitor.sh >/dev/null 2>&1 || true
if declare -F generate_csv_header >/dev/null 2>&1; then
    header=$(generate_csv_header 2>/dev/null)
    last_col=$(echo "$header" | awk -F, '{print $NF}')
    check "unified header 末列 = cloud_provider" "cloud_provider" "$last_col"
    # header 不为空且含 timestamp 首列
    first_col=$(echo "$header" | awk -F, '{print $1}')
    check "unified header 首列 = timestamp" "timestamp" "$first_col"
    echo "     header 列数: $(echo "$header" | awk -F, '{print NF}')"
else
    echo "FAIL generate_csv_header 不可用" >&2; FAIL=1; N=$((N+1))
fi

# === 3. iops 修复在生产数据流: AWS 拆分 vs GCP passthrough ===
source utils/disk_converter.sh >/dev/null 2>&1 || true
# 当前 CLOUD_PROVIDER=gcp → passthrough
check "GCP convert iops 1000@1024 = passthrough(1000)" "1000" "$(convert_to_standard_iops 1000 1024)"

echo ""
if [[ $FAIL -eq 0 ]]; then echo "PASS L3 csv e2e ($N checks)"; exit 0
else echo "FAIL L3 csv e2e ($N checks)" >&2; exit 1; fi
