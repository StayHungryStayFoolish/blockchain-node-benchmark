#!/usr/bin/env bash
# tests/test_iops_conversion.sh
# 验证 convert_to_standard_iops 的 provider-aware 拆分逻辑 (CP-1 §0 裁决1)
# 依据官方实证: analysis-notes/aws-gcp-io-counting-rules-verified.md
#   AWS EBS 官方示例: 1 x 1024 KiB I/O = 4 IOPS (1024/256=4)

set -uo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
source utils/disk_converter.sh

FAIL=0
N=0
check() {
    local desc="$1" expected="$2" actual="$3"
    N=$((N+1))
    if [[ "$actual" == "$expected" ]]; then
        echo "OK   [$desc] = $actual"
    else
        echo "FAIL [$desc] expected=$expected actual=$actual" >&2
        FAIL=1
    fi
}

echo "=== AWS provider: 按 256 KiB(SSD) 拆分 ==="
CLOUD_PROVIDER=aws source config/cloud_provider.sh >/dev/null 2>&1
# 官方示例: 1000 IOPS @ 1024 KiB avg → multiplier=ceil(1024/256)=4 → 4000
check "AWS 1000iops@1024KiB SSD" "4000.00" "$(convert_to_standard_iops 1000 1024)"
# 官方示例核心: 1 IOPS @ 1024 KiB = 4
check "AWS 1iops@1024KiB SSD" "4.00" "$(convert_to_standard_iops 1 1024)"
# io_size <= cap → multiplier=1 (无放大)
check "AWS 500iops@32KiB SSD(<=256)" "500.00" "$(convert_to_standard_iops 500 32)"
check "AWS 500iops@256KiB SSD(=cap)" "500.00" "$(convert_to_standard_iops 500 256)"
# 257 KiB → ceil(257/256)=2 → 1000
check "AWS 500iops@257KiB SSD" "1000.00" "$(convert_to_standard_iops 500 257)"
# HDD cap=1024: 500 @ 2048 → ceil(2048/1024)=2 → 1000
check "AWS 500iops@2048KiB HDD(cap1024)" "1000.00" "$(convert_to_standard_iops 500 2048 1024)"
# 无 io_size 信息 → 退化 passthrough (不凭空放大)
check "AWS 777iops@0(no iosize)" "777" "$(convert_to_standard_iops 777 0)"
# 非正 → 0
check "AWS 0iops" "0" "$(convert_to_standard_iops 0 512)"

echo ""
echo "=== GCP provider: passthrough(不拆分) ==="
CLOUD_PROVIDER=gcp source config/cloud_provider.sh >/dev/null 2>&1
# GCP 即使 io_size 大也不拆分
check "GCP 1000iops@1024KiB" "1000" "$(convert_to_standard_iops 1000 1024)"
check "GCP 500iops@4096KiB" "500" "$(convert_to_standard_iops 500 4096)"
check "GCP 0iops" "0" "$(convert_to_standard_iops 0 512)"

echo ""
echo "=== other provider: passthrough ==="
CLOUD_PROVIDER=other source config/cloud_provider.sh >/dev/null 2>&1
check "other 1000iops@1024KiB" "1000" "$(convert_to_standard_iops 1000 1024)"

echo ""
echo "=== 中立别名 convert_to_standard_iops 等价 ==="
CLOUD_PROVIDER=aws source config/cloud_provider.sh >/dev/null 2>&1
check "alias AWS 1000@1024" "4000.00" "$(convert_to_standard_iops 1000 1024)"

echo ""
if [[ $FAIL -eq 0 ]]; then
    echo "PASS iops conversion test ($N checks)"
    exit 0
else
    echo "FAIL iops conversion test ($N checks)" >&2
    exit 1
fi
