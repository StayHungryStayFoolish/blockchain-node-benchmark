#!/bin/bash
# =====================================================================
# GCP Hyperdisk Provider (hyperdisk-extreme / hyperdisk-balanced)
# =====================================================================
# Hyperdisk has DIFFERENT IOPS/throughput characteristics from PD:
#   - Per-disk provisioned IOPS up to 350K (vs PD's 100K)
#   - Per-disk provisioned throughput up to 5 GiB/s (vs PD's 1.2 GiB/s)
#   - Decoupled IOPS/throughput billing (vs PD's coupled tier)
#
# Adds 3 Hyperdisk-specific fields:
#   gcp_hyperdisk_iops_provisioned       — Provisioned IOPS (from env or 0)
#   gcp_hyperdisk_throughput_provisioned — Provisioned MiB/s (from env or 0)
#   gcp_hyperdisk_type                   — "extreme" / "balanced" / "ml" / "unknown"
# Total: 22 fields (1 more than aws_ebs / gcp_pd due to disk-type tag)
# =====================================================================

source "$(dirname "${BASH_SOURCE[0]}")/interface.sh"

disk_provider_id() {
    echo "gcp_hyperdisk"
}

declare -gA _HYPERDISK_TYPE_CACHE

_hyperdisk_get_type() {
    local device="$1"
    if [[ -n "${_HYPERDISK_TYPE_CACHE[$device]:-}" ]]; then
        echo "${_HYPERDISK_TYPE_CACHE[$device]}"
        return
    fi
    # Type passed in via env: GCP_HYPERDISK_TYPE_SDA=extreme
    local env_var="GCP_HYPERDISK_TYPE_${device^^}"
    local t="${!env_var:-unknown}"
    _HYPERDISK_TYPE_CACHE[$device]="$t"
    echo "$t"
}

disk_provider_init() {
    return 0
}

disk_provider_header() {
    local device="$1"
    local logical_name="$2"
    local prefix
    case "$logical_name" in
        "data") prefix="data_${device}" ;;
        "accounts") prefix="accounts_${device}" ;;
        *) prefix="${logical_name}_${device}" ;;
    esac
    local universal
    universal=$(disk_provider_universal_header "$prefix")
    echo "${universal},${prefix}_gcp_hyperdisk_iops_provisioned,${prefix}_gcp_hyperdisk_throughput_provisioned_mibs,${prefix}_gcp_hyperdisk_type"
}

disk_provider_collect() {
    local device="$1"
    local logical_name="$2"
    local universal
    universal=$(disk_provider_extract_iostat_base "$device" "$logical_name")
    local iops_env="GCP_HYPERDISK_IOPS_${device^^}"
    local tput_env="GCP_HYPERDISK_TPUT_${device^^}"
    local iops_prov="${!iops_env:-0}"
    local tput_prov="${!tput_env:-0}"
    local hd_type
    hd_type=$(_hyperdisk_get_type "$device")
    echo "${universal},${iops_prov},${tput_prov},${hd_type}"
}

export -f disk_provider_id disk_provider_init disk_provider_header disk_provider_collect _hyperdisk_get_type
