#!/bin/bash
# =====================================================================
# GCP Persistent Disk Provider (pd-standard / pd-ssd / pd-balanced / pd-extreme)
# =====================================================================
# Adds 2 GCP-specific fields on top of the 19-field universal set:
#   gcp_pd_iops_limit          — Configured PD IOPS limit (from metadata,
#                                fallback to 0 if not detectable)
#   gcp_pd_throughput_limit    — Configured PD throughput limit (MiB/s)
# Total: 21 fields (parity with aws_ebs.sh, distinct semantics)
#
# GCP PD IOPS/throughput is NOT block-size normalized like AWS — GCP enforces
# raw IOPS/throughput at the configured limit. Limits are queryable via:
#   curl -sH 'Metadata-Flavor: Google' \
#     http://metadata.google.internal/computeMetadata/v1/instance/disks/<idx>/
# But that requires disk index mapping — we make best-effort detection and
# fall back to 0 (analyst can see device util% to interpret).
# =====================================================================

source "$(dirname "${BASH_SOURCE[0]}")/interface.sh"

disk_provider_id() {
    echo "gcp_pd"
}

# Cache disk limits per device to avoid hammering metadata server
declare -gA _GCP_PD_IOPS_LIMIT_CACHE
declare -gA _GCP_PD_TPUT_LIMIT_CACHE

_gcp_pd_get_limit() {
    local device="$1"
    local kind="$2"  # "iops" or "throughput"
    # Use cache
    if [[ "$kind" == "iops" && -n "${_GCP_PD_IOPS_LIMIT_CACHE[$device]:-}" ]]; then
        echo "${_GCP_PD_IOPS_LIMIT_CACHE[$device]}"
        return
    fi
    if [[ "$kind" == "throughput" && -n "${_GCP_PD_TPUT_LIMIT_CACHE[$device]:-}" ]]; then
        echo "${_GCP_PD_TPUT_LIMIT_CACHE[$device]}"
        return
    fi

    # Try metadata server (only on actual GCE VMs, not always available)
    local value="0"
    # On real GCE, /sys/block/<dev>/queue/nr_requests can hint at IO queue depth
    # but doesn't give the configured PD limit. Defer to 0 unless explicitly set
    # in env vars GCP_PD_IOPS_LIMIT_<DEV> or GCP_PD_TPUT_LIMIT_<DEV>.
    local env_var
    if [[ "$kind" == "iops" ]]; then
        env_var="GCP_PD_IOPS_LIMIT_${device^^}"
    else
        env_var="GCP_PD_TPUT_LIMIT_${device^^}"
    fi
    value="${!env_var:-0}"

    if [[ "$kind" == "iops" ]]; then
        _GCP_PD_IOPS_LIMIT_CACHE[$device]="$value"
    else
        _GCP_PD_TPUT_LIMIT_CACHE[$device]="$value"
    fi
    echo "$value"
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
    echo "${universal},${prefix}_gcp_pd_iops_limit,${prefix}_gcp_pd_throughput_limit_mibs"
}

disk_provider_collect() {
    local device="$1"
    local logical_name="$2"
    local universal
    universal=$(disk_provider_extract_iostat_base "$device" "$logical_name")
    local iops_limit tput_limit
    iops_limit=$(_gcp_pd_get_limit "$device" "iops")
    tput_limit=$(_gcp_pd_get_limit "$device" "throughput")
    echo "${universal},${iops_limit},${tput_limit}"
}

export -f disk_provider_id disk_provider_init disk_provider_header disk_provider_collect _gcp_pd_get_limit
