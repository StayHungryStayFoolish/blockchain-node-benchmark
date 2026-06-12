#!/bin/bash

# Provider-aware IOPS/throughput processing helpers.
# Includes AWS EBS split accounting and GCP/other passthrough accounting.

if [[ -z "${IO2_THROUGHPUT_RATIO:-}" ]]; then
    readonly IO2_THROUGHPUT_RATIO=0.256
fi

if [[ -z "${IO2_MAX_THROUGHPUT:-}" ]]; then
    readonly IO2_MAX_THROUGHPUT=4000
fi

# Note: IOPS conversion is provider-aware via get_iops_conversion_func.
#   AWS EBS: I/O size capped at 256 KiB (SSD) / 1024 KiB (HDD) — count splits by ceil(io_size/cap).
#   GCP PD/Hyperdisk + other: passthrough without I/O-size split accounting.
# The routing key comes from get_iops_conversion_func in config/providers/.

# Convert actual IOPS to provider-standard IOPS
# Parameters: actual_iops              - Actual IOPS (r/s + w/s)
#             actual_avg_io_size_kib   - Average I/O size in KiB (used for AWS split)
#             io_cap_kib (optional)    - I/O size cap: 256 (SSD, default) | 1024 (HDD)
# Returns: provider-standard IOPS
#   AWS:        actual_iops * ceil(avg_io_size_kib / cap)
#   GCP/other:  actual_iops (passthrough)
convert_to_standard_iops() {
    local actual_iops=$1
    local actual_avg_io_size_kib=${2:-0}
    local io_cap_kib=${3:-256}   # SSD default 256 KiB; HDD callers pass 1024.

    # Non-positive IOPS maps to 0.
    if (( $(awk "BEGIN {print ($actual_iops <= 0) ? 1 : 0}") )); then
        echo "0"
        return
    fi

    # Provider routing: if the provider getter is unavailable, default to
    # passthrough so we do not inflate values accidentally.
    local conv_func="passthrough"
    if declare -F get_iops_conversion_func >/dev/null 2>&1; then
        conv_func=$(get_iops_conversion_func)
    fi

    case "$conv_func" in
        aws_ssd_ceil_256|aws_*|*ceil*)
            # AWS: split by I/O size. If io_size<=cap, multiplier=1.
            # multiplier = ceil(avg_io_size_kib / cap), minimum 1.
            if (( $(awk "BEGIN {print ($actual_avg_io_size_kib <= 0) ? 1 : 0}") )); then
                # No I/O-size signal: degrade to passthrough to avoid false alerts.
                echo "$actual_iops"
                return
            fi
            local multiplier
            multiplier=$(awk "BEGIN { m = ($actual_avg_io_size_kib / $io_cap_kib); c = (m == int(m)) ? m : int(m)+1; if (c < 1) c = 1; printf \"%d\", c }")
            awk "BEGIN {printf \"%.2f\", $actual_iops * $multiplier}"
            ;;
        *)
            # GCP / other / passthrough: no split accounting.
            echo "$actual_iops"
            ;;
    esac
}

# Convert actual throughput to provider-standard throughput
# Parameters: actual_throughput_mibs actual_avg_io_size_kib
# Returns: provider-standard throughput (MiB/s)
# Throughput does not need conversion, return actual value directly
convert_to_standard_throughput() {
    local actual_throughput_mibs="$1"
    local actual_avg_io_size_kib="$2"
    
    # Input validation
    if [[ -z "$actual_throughput_mibs" ]]; then
        echo "Error: convert_to_standard_throughput requires throughput parameter" >&2
        return 1
    fi
    
    # Throughput does not need 128 KiB baseline conversion; return the actual value.
    # AWS EBS Throughput configuration is actual MiB/s, no standardization needed
    echo "$actual_throughput_mibs"
}

# Calculate io2 Block Express automatic throughput
# Parameters: iops
# Returns: Automatically calculated throughput (MiB/s)
calculate_io2_throughput() {
    local iops=$1
    local calculated_throughput=$(awk "BEGIN {printf \"%.2f\", $iops * $IO2_THROUGHPUT_RATIO}")
    local actual_throughput=$(awk "BEGIN {printf \"%.2f\", ($calculated_throughput > $IO2_MAX_THROUGHPUT) ? $IO2_MAX_THROUGHPUT : $calculated_throughput}")
    echo "$actual_throughput"
}

# instance-store performance analysis (no AWS standard conversion)
# Parameters: actual_iops actual_throughput_mibs configured_iops configured_throughput
# Returns: Performance analysis result
analyze_instance_store_performance() {
    local actual_iops=$1
    local actual_throughput_mibs=$2
    local configured_iops=$3
    local configured_throughput=$4
    
    echo "Instance Store Performance (No AWS conversion needed):"
    echo "  Actual IOPS: $actual_iops"
    echo "  Actual Throughput: $actual_throughput_mibs MiB/s"
    echo "  Configured IOPS: $configured_iops"
    echo "  Configured Throughput: $configured_throughput MiB/s"
    echo "  Reference: https://docs.aws.amazon.com/ec2/latest/instancetypes/so.html"
}

# Recommend Disk type (only supports gp3, io2, instance-store)
# Parameters: normalized_iops actual_throughput_mibs
# Returns: Recommended Disk type
recommend_ebs_type() {
    local normalized_iops=$1
    local actual_throughput_mibs=$2
    
    # Check if gp3 can satisfy
    if (( $(awk "BEGIN {print ($normalized_iops <= 80000 && $actual_throughput_mibs <= 2000) ? 1 : 0}") )); then
        echo "gp3"
        return
    fi
    
    # Check if io2 can satisfy
    local io2_throughput=$(calculate_io2_throughput "$normalized_iops")
    if (( $(awk "BEGIN {print ($normalized_iops <= 256000 && $io2_throughput >= $actual_throughput_mibs) ? 1 : 0}") )); then
        echo "io2"
        return
    fi
    
    # If Disk cannot satisfy, recommend instance-store
    echo "instance-store"
}

# Calculate average I/O size (from iostat data)
# Parameters: r_s w_s rkb_s wkb_s
# Returns: Weighted average I/O size (KiB)
calculate_weighted_avg_io_size() {
    local r_s=$1
    local w_s=$2
    local rkb_s=$3
    local wkb_s=$4
    
    local total_iops=$(awk "BEGIN {printf \"%.2f\", $r_s + $w_s}")
    local total_throughput_kbs=$(awk "BEGIN {printf \"%.2f\", $rkb_s + $wkb_s}")
    
    if (( $(awk "BEGIN {print ($total_iops <= 0) ? 1 : 0}") )); then
        echo "0"
        return
    fi
    
    local avg_io_kib=$(awk "BEGIN {printf \"%.2f\", $total_throughput_kbs / $total_iops}")
    echo "$avg_io_kib"
}

# Check if ACCOUNTS device is configured
# Criteria: All 3 key environment variables must be configured
# Returns: 0=configured, 1=not configured
is_accounts_configured() {
    [[ -n "${ACCOUNTS_DEVICE:-}" && -n "${ACCOUNTS_VOL_TYPE:-}" && -n "${ACCOUNTS_VOL_MAX_IOPS:-}" ]]
}
# Export functions
export -f convert_to_standard_iops
export -f convert_to_standard_throughput
export -f calculate_io2_throughput
export -f recommend_ebs_type
export -f calculate_weighted_avg_io_size
export -f analyze_instance_store_performance
export -f is_accounts_configured

# If script is executed directly, display help information
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "AWS EBS IOPS/Throughput Standard Conversion Script"
    echo "Usage examples:"
    echo "  source disk_converter.sh"
    echo "  convert_to_standard_iops 1000 32"
    echo "  convert_to_standard_throughput 100 64"
    echo "  calculate_io2_throughput 20000"
fi
