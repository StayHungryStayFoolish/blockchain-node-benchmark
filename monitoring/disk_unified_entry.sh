#!/bin/bash
# =====================================================================
# Disk Unified Entry — Y+ Architecture
# =====================================================================
# Single source of truth for disk monitoring across AWS/GCP/Other.
# Source this file; it auto-detects disk variant and exports 4 functions:
#   disk_init       — provider init
#   disk_header     — full CSV header (all configured devices)
#   disk_collect    — single CSV row (all configured devices, current sample)
#   disk_variant    — string id of active provider
#
# Detection order:
#   1. Env override DISK_PROVIDER_VARIANT (aws_ebs / gcp_pd / gcp_hyperdisk / other_local)
#   2. Auto-detect via CLOUD_PROVIDER + LSBLK model string
#      - AWS + (nvme*) → aws_ebs
#      - GCP + (Hyperdisk*) → gcp_hyperdisk
#      - GCP + (PersistentDisk) → gcp_pd
#      - GCP + (other) → gcp_pd (default GCP fallback)
#      - other → other_local
#
# Companion file: monitoring/disk/interface.sh + 4 providers in same dir.
# Requires LEDGER_DEVICE (required) and ACCOUNTS_DEVICE (optional) env vars.
# =====================================================================

# Ensure cloud_provider detection has run
if [[ -z "${CLOUD_PROVIDER:-}" ]]; then
    if [[ -f "$(dirname "${BASH_SOURCE[0]}")/../config/cloud_provider.sh" ]]; then
        source "$(dirname "${BASH_SOURCE[0]}")/../config/cloud_provider.sh"
    else
        export CLOUD_PROVIDER="other"
    fi
fi

# Detect disk variant
detect_disk_variant() {
    # Env override takes priority
    if [[ -n "${DISK_PROVIDER_VARIANT:-}" ]]; then
        echo "$DISK_PROVIDER_VARIANT"
        return
    fi

    # Probe primary device model via lsblk
    local primary_dev="${LEDGER_DEVICE:-sda}"
    local model=""
    if command -v lsblk >/dev/null 2>&1; then
        model=$(lsblk -d -no MODEL "/dev/${primary_dev}" 2>/dev/null | tr -s ' ' | head -1)
    fi
    # Lower-case for matching
    local model_lc
    model_lc=$(echo "$model" | tr '[:upper:]' '[:lower:]')

    case "$CLOUD_PROVIDER" in
        aws)
            # AWS EBS shows as "Amazon Elastic Block Store" or nvme* device
            echo "aws_ebs"
            ;;
        gcp)
            if echo "$model_lc" | grep -q "hyperdisk"; then
                echo "gcp_hyperdisk"
            elif echo "$model_lc" | grep -qE "persistentdisk|persistent disk"; then
                echo "gcp_pd"
            else
                # Default GCP fallback to pd (most common)
                echo "gcp_pd"
            fi
            ;;
        *)
            echo "other_local"
            ;;
    esac
}

# Load the active provider
_load_disk_provider() {
    local variant="$1"
    local provider_file="$(dirname "${BASH_SOURCE[0]}")/disk/${variant}.sh"
    if [[ ! -f "$provider_file" ]]; then
        echo "ERROR: disk provider file not found: $provider_file, falling back to other_local" >&2
        provider_file="$(dirname "${BASH_SOURCE[0]}")/disk/other_local.sh"
    fi
    source "$provider_file"
}

# Public API: disk_init
disk_init() {
    disk_provider_init
}

# Public API: disk_header  (concatenates header for all configured devices)
disk_header() {
    local headers=()
    if [[ -n "${LEDGER_DEVICE:-}" ]]; then
        headers+=("$(disk_provider_header "$LEDGER_DEVICE" "data")")
    else
        echo "ERROR: LEDGER_DEVICE not set" >&2
        return 1
    fi
    if [[ -n "${ACCOUNTS_DEVICE:-}" ]]; then
        headers+=("$(disk_provider_header "$ACCOUNTS_DEVICE" "accounts")")
    fi
    local IFS=,
    echo "${headers[*]}"
}

# Public API: disk_collect (concatenates collect for all configured devices)
disk_collect() {
    local rows=()
    if [[ -n "${LEDGER_DEVICE:-}" ]]; then
        rows+=("$(disk_provider_collect "$LEDGER_DEVICE" "data")")
    else
        echo "ERROR: LEDGER_DEVICE not set" >&2
        return 1
    fi
    if [[ -n "${ACCOUNTS_DEVICE:-}" ]]; then
        rows+=("$(disk_provider_collect "$ACCOUNTS_DEVICE" "accounts")")
    fi
    local IFS=,
    echo "${rows[*]}"
}

disk_variant() {
    disk_provider_id
}

# Auto-execute on source
DISK_VARIANT="${DISK_VARIANT:-$(detect_disk_variant)}"
export DISK_VARIANT
_load_disk_provider "$DISK_VARIANT"
disk_init

export -f detect_disk_variant disk_init disk_header disk_collect disk_variant _load_disk_provider
