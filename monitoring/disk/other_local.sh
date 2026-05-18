#!/bin/bash
# =====================================================================
# Other / Local-SSD / Bare-metal / Mac Provider (Fallback)
# =====================================================================
# Returns ONLY the 19-field universal set with no provider-specific extras.
# Used for:
#   - Local NVMe (GCP local-ssd / AWS instance-store / on-prem NVMe)
#   - Mac development (no iostat → zero rows)
#   - Any platform not in {aws_ebs, gcp_pd, gcp_hyperdisk}
# Total: 19 fields (smallest set, no provider-specific math)
# =====================================================================

source "$(dirname "${BASH_SOURCE[0]}")/interface.sh"

disk_provider_id() {
    echo "other_local"
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
    disk_provider_universal_header "$prefix"
}

disk_provider_collect() {
    local device="$1"
    local logical_name="$2"
    disk_provider_extract_iostat_base "$device" "$logical_name"
}

export -f disk_provider_id disk_provider_init disk_provider_header disk_provider_collect
