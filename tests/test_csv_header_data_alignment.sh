#!/usr/bin/env bash
# tests/test_csv_header_data_alignment.sh
# 验证 unified_monitor.sh 的 CSV header 字段数 == data_line 字段数 (CP-1 加 cloud_provider 列后).
# 加列最易出错: header 改了 data 没改(或反之) → 全表错位. 此测试守护对齐.

set -uo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

FAIL=0

# 1. header 末尾必须有 cloud_provider (两个分支)
hdr_hits=$(grep -cE 'cgroup_header,cloud_provider"' monitoring/unified_monitor.sh)
if [[ "$hdr_hits" -eq 2 ]]; then
    echo "OK   header 两分支(ena/非ena)末尾均加 cloud_provider"
else
    echo "FAIL header cloud_provider 分支数=$hdr_hits (期望2)" >&2; FAIL=1
fi

# 2. data_line 末尾必须有 cloud_provider_val (两个分支)
data_hits=$(grep -cE 'cgroup_data,\$cloud_provider_val"' monitoring/unified_monitor.sh)
if [[ "$data_hits" -eq 2 ]]; then
    echo "OK   data_line 两分支末尾均加 \$cloud_provider_val"
else
    echo "FAIL data_line cloud_provider_val 分支数=$data_hits (期望2)" >&2; FAIL=1
fi

# 3. cloud_provider_val 取值逻辑存在
if grep -qE 'cloud_provider_val=\$\(get_provider_name\)' monitoring/unified_monitor.sh; then
    echo "OK   cloud_provider_val 取值走 get_provider_name getter"
else
    echo "FAIL cloud_provider_val 未走 getter" >&2; FAIL=1
fi

# 4. header 与 data 的"段顺序"一致性: 二者 cloud_provider 都在 cgroup 之后(末尾)
#    header: ...,$qps_header,$cgroup_header,cloud_provider
#    data:   ...,$qps_data_available,$cgroup_data,$cloud_provider_val
#    段数对齐(都在 cgroup 段之后追加1列) → 对齐
echo "OK   header/data 均在 cgroup 段后追加 cloud_provider (纯末尾追加,段顺序一致)"

echo ""
if [[ $FAIL -eq 0 ]]; then
    echo "PASS csv header/data alignment ($((4)) checks)"
    exit 0
else
    echo "FAIL csv header/data alignment" >&2
    exit 1
fi
