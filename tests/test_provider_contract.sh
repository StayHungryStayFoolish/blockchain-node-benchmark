#!/usr/bin/env bash
# tests/test_provider_contract.sh
# E1+ Provider Contract Test — 验证 aws/gcp/other 三 provider 都实现了 16 个 getter
# 且 AWS≠GCP 防抄断言（性能对比公平性）。
# 任一断言失败 → exit 1，CI gate 拒绝合入。
#
# 依据: analysis-notes/CORRECTED_PLAN.md §CP-0.5 + analysis-notes/CP-1-execution-tracker.md §1
#       新增 get_iops_conversion_func（双云 IOPS 计量分流核心，本任务 §0 裁决1）

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

REQUIRED_GETTERS=(
    get_provider_name get_platform_display_name
    get_metadata_endpoint get_metadata_header get_metadata_api_path
    get_iops_conversion_func get_baseline_io_kib get_baseline_throughput_kib
    get_default_disk_type get_disk_type_options
    get_nic_driver get_nic_allowance_fields get_nic_monitor_process_name
    get_disk_field_prefix get_archive_dir_prefix get_bottleneck_label
    get_doc_url
)

FAIL=0
TOTAL_CHECKS=0

# ============================================================
# Phase 1: 三 provider 都实现全部 getter
# aws/gcp 必须返回非空（已知特例除外）；other 允许返空（中立 fallback）
# ============================================================
echo "=== Phase 1: 完整性检查 (3 providers × ${#REQUIRED_GETTERS[@]} getters) ==="
for provider in aws gcp other; do
    output=$(CLOUD_PROVIDER=$provider bash -c "
        unset CLOUD_PROVIDER_DETECTED 2>/dev/null || true
        source config/cloud_provider.sh >/dev/null 2>&1
        for getter in ${REQUIRED_GETTERS[*]}; do
            declare -F \$getter >/dev/null || { echo \"FAIL: \$getter missing in $provider\" >&2; exit 1; }
            val=\$(\$getter 2>/dev/null || true)
            if [[ \"$provider\" != \"other\" && -z \"\$val\" ]]; then
                # 已知特例：AWS get_metadata_header 故意空（IMDSv2 token 走 -H）；
                # GCP get_nic_allowance_fields 故意空（gVNIC 无 allowance）
                if [[ \"$provider\" == \"aws\" && \"\$getter\" == \"get_metadata_header\" ]]; then :; 
                elif [[ \"$provider\" == \"gcp\" && \"\$getter\" == \"get_nic_allowance_fields\" ]]; then :; 
                else echo \"FAIL: \$getter returned empty in $provider\" >&2; exit 1; fi
            fi
        done
        echo \"$provider: OK (${#REQUIRED_GETTERS[@]}/${#REQUIRED_GETTERS[@]} getters)\"
    " 2>&1) || { echo "$output"; FAIL=1; TOTAL_CHECKS=$((TOTAL_CHECKS+${#REQUIRED_GETTERS[@]})); continue; }
    echo "$output"
    TOTAL_CHECKS=$((TOTAL_CHECKS+${#REQUIRED_GETTERS[@]}))
done

# ============================================================
# Phase 2: AWS ≠ GCP 防抄断言（8 个关键 getter）
# 含 get_iops_conversion_func — 双云 IOPS 计量必须不同
# ============================================================
echo ""
echo "=== Phase 2: AWS≠GCP 防抄断言 ==="
ANTI_PLAGIARISM_GETTERS=(
    get_metadata_endpoint
    get_metadata_header
    get_iops_conversion_func
    get_disk_field_prefix
    get_nic_driver
    get_archive_dir_prefix
    get_bottleneck_label
    get_platform_display_name
)
for getter in "${ANTI_PLAGIARISM_GETTERS[@]}"; do
    aws_val=$(CLOUD_PROVIDER=aws bash -c "unset CLOUD_PROVIDER_DETECTED 2>/dev/null||true; source config/cloud_provider.sh >/dev/null 2>&1; $getter")
    gcp_val=$(CLOUD_PROVIDER=gcp bash -c "unset CLOUD_PROVIDER_DETECTED 2>/dev/null||true; source config/cloud_provider.sh >/dev/null 2>&1; $getter")
    if [[ "$aws_val" == "$gcp_val" ]]; then
        echo "FAIL: $getter returned identical value in AWS and GCP ('$aws_val') — provider 抄袭嫌疑" >&2
        FAIL=1
    else
        echo "OK   $getter: aws='$aws_val' != gcp='$gcp_val'"
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS+1))
done

# ============================================================
# Phase 3: IOPS 计量语义断言（§0 裁决1 — 官方实证）
# AWS 必须拆分(非 passthrough)，GCP/other 必须 passthrough
# ============================================================
echo ""
echo "=== Phase 3: IOPS 计量语义 ==="
aws_iops=$(CLOUD_PROVIDER=aws bash -c "unset CLOUD_PROVIDER_DETECTED 2>/dev/null||true; source config/cloud_provider.sh >/dev/null 2>&1; get_iops_conversion_func")
gcp_iops=$(CLOUD_PROVIDER=gcp bash -c "unset CLOUD_PROVIDER_DETECTED 2>/dev/null||true; source config/cloud_provider.sh >/dev/null 2>&1; get_iops_conversion_func")
other_iops=$(CLOUD_PROVIDER=other bash -c "unset CLOUD_PROVIDER_DETECTED 2>/dev/null||true; source config/cloud_provider.sh >/dev/null 2>&1; get_iops_conversion_func")
if [[ "$aws_iops" == "passthrough" ]]; then
    echo "FAIL: AWS get_iops_conversion_func must NOT be passthrough (官方实证: SSD ceil256/HDD ceil1024)" >&2; FAIL=1
else echo "OK   AWS iops conversion = '$aws_iops' (非 passthrough)"; fi
if [[ "$gcp_iops" != "passthrough" ]]; then
    echo "FAIL: GCP get_iops_conversion_func must be passthrough (官方实证: PD/Hyperdisk 不拆分)" >&2; FAIL=1
else echo "OK   GCP iops conversion = passthrough"; fi
if [[ "$other_iops" != "passthrough" ]]; then
    echo "FAIL: other get_iops_conversion_func must be passthrough" >&2; FAIL=1
else echo "OK   other iops conversion = passthrough"; fi
TOTAL_CHECKS=$((TOTAL_CHECKS+3))

# ============================================================
# 汇总
# ============================================================
echo ""
if [[ $FAIL -eq 0 ]]; then
    echo "PASS Contract test ($TOTAL_CHECKS checks)"
    exit 0
else
    echo "FAIL Contract test ($TOTAL_CHECKS checks attempted)" >&2
    exit 1
fi
