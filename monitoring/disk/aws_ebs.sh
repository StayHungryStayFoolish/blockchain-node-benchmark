#!/bin/bash
# =====================================================================
# AWS EBS Disk Provider (gp3 / io2 / etc.) — Y+ Architecture
# =====================================================================
# Adds 2 AWS-specific fields on top of the 19-field universal set:
#   aws_standard_iops          — IOPS normalized to AWS 16KB-block standard
#   aws_standard_throughput    — Throughput normalized to AWS standard
# Total: 21 fields (matches legacy iostat_collector.sh exactly)
#
# AWS standardization uses utils/ebs_converter.sh's convert_to_aws_standard_*
# functions (block-size weighted).
# =====================================================================

source "$(dirname "${BASH_SOURCE[0]}")/interface.sh"

disk_provider_id() {
    echo "aws_ebs"
}

disk_provider_init() {
    # Ensure ebs_converter.sh is loaded for AWS standardization functions
    if ! command -v convert_to_aws_standard_iops >/dev/null 2>&1; then
        source "$(dirname "${BASH_SOURCE[0]}")/../../utils/ebs_converter.sh" 2>/dev/null || true
    fi
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
    # Append 2 AWS-specific fields
    echo "${universal},${prefix}_aws_standard_iops,${prefix}_aws_standard_throughput_mibs"
}

disk_provider_collect() {
    local device="$1"
    local logical_name="$2"
    local universal
    universal=$(disk_provider_extract_iostat_base "$device" "$logical_name")

    # Parse total_iops and total_throughput_mibs (positions 14 and 15 in the 19-field set, 1-indexed)
    IFS=',' read -ra arr <<<"$universal"
    local total_iops="${arr[13]:-0}"
    local total_throughput_mibs="${arr[14]:-0}"
    local rkb_s="${arr[2]:-0}"
    local wkb_s="${arr[3]:-0}"
    local total_kbs
    total_kbs=$(awk "BEGIN {printf \"%.2f\", $rkb_s + $wkb_s}")

    # AWS-standard normalization
    local aws_standard_iops aws_standard_throughput
    local avg_io_kib="0"
    if awk "BEGIN {exit !($total_iops > 0)}" 2>/dev/null; then
        avg_io_kib=$(awk "BEGIN {printf \"%.2f\", $total_kbs / $total_iops}")
    fi

    if command -v convert_to_aws_standard_iops >/dev/null 2>&1 && awk "BEGIN {exit !($avg_io_kib > 0)}" 2>/dev/null; then
        aws_standard_iops=$(convert_to_aws_standard_iops "$total_iops" "$avg_io_kib")
        aws_standard_throughput=$(convert_to_aws_standard_throughput "$total_throughput_mibs" "$avg_io_kib")
    else
        aws_standard_iops="$total_iops"
        aws_standard_throughput="$total_throughput_mibs"
    fi

    echo "${universal},${aws_standard_iops},${aws_standard_throughput}"
}

export -f disk_provider_id disk_provider_init disk_provider_header disk_provider_collect
