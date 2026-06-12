#!/usr/bin/env bash
# tests/test_provider_contract.sh
# Provider contract test: aws/gcp/other implement the required getters.
# Ensures AWS and GCP provider contracts do not collapse into identical behavior.
# Any assertion failure exits non-zero.
#
# get_iops_conversion_func selects provider-specific IOPS conversion.

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
# Step 1: all providers implement required getters
# aws/gcp must return non-empty values except known exceptions; other may be empty fallback.
# ============================================================
echo "=== Step 1: completeness check (3 providers x ${#REQUIRED_GETTERS[@]} getters) ==="
for provider in aws gcp other; do
    output=$(CLOUD_PROVIDER=$provider bash -c "
        unset CLOUD_PROVIDER_DETECTED 2>/dev/null || true
        source config/cloud_provider.sh >/dev/null 2>&1
        for getter in ${REQUIRED_GETTERS[*]}; do
            declare -F \$getter >/dev/null || { echo \"FAIL: \$getter missing in $provider\" >&2; exit 1; }
            val=\$(\$getter 2>/dev/null || true)
            if [[ \"$provider\" != \"other\" && -z \"\$val\" ]]; then
                # Known exception: GCP gVNIC does not expose allowance counters.
                if [[ \"$provider\" == \"gcp\" && \"\$getter\" == \"get_nic_allowance_fields\" ]]; then :;
                else echo \"FAIL: \$getter returned empty in $provider\" >&2; exit 1; fi
            fi
        done
        echo \"$provider: OK (${#REQUIRED_GETTERS[@]}/${#REQUIRED_GETTERS[@]} getters)\"
    " 2>&1) || { echo "$output"; FAIL=1; TOTAL_CHECKS=$((TOTAL_CHECKS+${#REQUIRED_GETTERS[@]})); continue; }
    echo "$output"
    TOTAL_CHECKS=$((TOTAL_CHECKS+${#REQUIRED_GETTERS[@]}))
done

# ============================================================
# Step 2: AWS and GCP must differ on key getters
# Includes get_iops_conversion_func because IOPS conversion differs by provider.
# ============================================================
echo ""
echo "=== Step 2: AWS != GCP assertions ==="
ANTI_PLAGIARISM_GETTERS=(
    get_metadata_endpoint
    get_metadata_header
    get_iops_conversion_func
    get_nic_driver
    get_archive_dir_prefix
    get_bottleneck_label
    get_platform_display_name
)
for getter in "${ANTI_PLAGIARISM_GETTERS[@]}"; do
    aws_val=$(CLOUD_PROVIDER=aws bash -c "unset CLOUD_PROVIDER_DETECTED 2>/dev/null||true; source config/cloud_provider.sh >/dev/null 2>&1; $getter")
    gcp_val=$(CLOUD_PROVIDER=gcp bash -c "unset CLOUD_PROVIDER_DETECTED 2>/dev/null||true; source config/cloud_provider.sh >/dev/null 2>&1; $getter")
    if [[ "$aws_val" == "$gcp_val" ]]; then
        echo "FAIL: $getter returned identical value in AWS and GCP ('$aws_val')" >&2
        FAIL=1
    else
        echo "OK   $getter: aws='$aws_val' != gcp='$gcp_val'"
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS+1))
done

# ============================================================
# Step 3: IOPS conversion semantic assertions
# AWS must split IOPS accounting; GCP/other must use passthrough.
# ============================================================
echo ""
echo "=== Step 3: IOPS conversion semantics ==="
aws_iops=$(CLOUD_PROVIDER=aws bash -c "unset CLOUD_PROVIDER_DETECTED 2>/dev/null||true; source config/cloud_provider.sh >/dev/null 2>&1; get_iops_conversion_func")
gcp_iops=$(CLOUD_PROVIDER=gcp bash -c "unset CLOUD_PROVIDER_DETECTED 2>/dev/null||true; source config/cloud_provider.sh >/dev/null 2>&1; get_iops_conversion_func")
other_iops=$(CLOUD_PROVIDER=other bash -c "unset CLOUD_PROVIDER_DETECTED 2>/dev/null||true; source config/cloud_provider.sh >/dev/null 2>&1; get_iops_conversion_func")
if [[ "$aws_iops" == "passthrough" ]]; then
    echo "FAIL: AWS get_iops_conversion_func must NOT be passthrough (SSD ceil256/HDD ceil1024)" >&2; FAIL=1
else echo "OK   AWS iops conversion = '$aws_iops'"; fi
if [[ "$gcp_iops" != "passthrough" ]]; then
    echo "FAIL: GCP get_iops_conversion_func must be passthrough (PD/Hyperdisk no split)" >&2; FAIL=1
else echo "OK   GCP iops conversion = passthrough"; fi
if [[ "$other_iops" != "passthrough" ]]; then
    echo "FAIL: other get_iops_conversion_func must be passthrough" >&2; FAIL=1
else echo "OK   other iops conversion = passthrough"; fi
TOTAL_CHECKS=$((TOTAL_CHECKS+3))

# ============================================================
# Step 4: NIC monitor entrypoint cleanup
# AWS/GCP expose different NIC drivers and fields, but both must route through
# the provider-aware network_monitor entrypoint.
# ============================================================
echo ""
echo "=== Step 4: NIC monitor entrypoint ==="
aws_nic_monitor=$(CLOUD_PROVIDER=aws bash -c "unset CLOUD_PROVIDER_DETECTED 2>/dev/null||true; source config/cloud_provider.sh >/dev/null 2>&1; get_nic_monitor_process_name")
gcp_nic_monitor=$(CLOUD_PROVIDER=gcp bash -c "unset CLOUD_PROVIDER_DETECTED 2>/dev/null||true; source config/cloud_provider.sh >/dev/null 2>&1; get_nic_monitor_process_name")
if [[ "$aws_nic_monitor" != "network_monitor" ]]; then
    echo "FAIL: AWS NIC monitor must route through network_monitor (got '$aws_nic_monitor')" >&2
    FAIL=1
else
    echo "OK   AWS NIC monitor = network_monitor"
fi
if [[ "$gcp_nic_monitor" != "network_monitor" ]]; then
    echo "FAIL: GCP NIC monitor must route through network_monitor (got '$gcp_nic_monitor')" >&2
    FAIL=1
else
    echo "OK   GCP NIC monitor = network_monitor"
fi
TOTAL_CHECKS=$((TOTAL_CHECKS+2))

# ============================================================
# Summary
# ============================================================
echo ""
if [[ $FAIL -eq 0 ]]; then
    echo "PASS Contract test ($TOTAL_CHECKS checks)"
    exit 0
else
    echo "FAIL Contract test ($TOTAL_CHECKS checks attempted)" >&2
    exit 1
fi
