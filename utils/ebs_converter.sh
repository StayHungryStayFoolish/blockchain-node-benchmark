#!/bin/bash

# AWS EBS IOPS/Throughput Processing Script
# Used for processing EBS performance metrics, type recommendations, and io2 throughput calculation

# AWS EBS throughput baseline (for throughput conversion, maintain compatibility)
AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB=${AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB:-128}

if [[ -z "${IO2_THROUGHPUT_RATIO:-}" ]]; then
    readonly IO2_THROUGHPUT_RATIO=0.256
fi

if [[ -z "${IO2_MAX_THROUGHPUT:-}" ]]; then
    readonly IO2_MAX_THROUGHPUT=4000
fi

# Note: All types (gp3/io2/instance-store) use actual IOPS and throughput
# AWS EBS counts IOPS by request count, no conversion based on I/O size needed

# Get AWS EBS IOPS
# Parameters: actual_iops - Actual IOPS (r/s + w/s)
#             actual_avg_io_size_kib - Average I/O size (parameter kept for compatibility, unused)
# Returns: AWS EBS IOPS (equals actual IOPS)
# Description: AWS EBS counts IOPS by request count, no conversion needed
# Reference: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html
convert_to_aws_standard_iops() {
    local actual_iops=$1
    local actual_avg_io_size_kib=$2  # Keep parameter to maintain interface compatibility
    
    # AWS EBS IOPS counts by request count, no conversion needed
    # Reference: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html
    if (( $(awk "BEGIN {print ($actual_iops <= 0) ? 1 : 0}") )); then
        echo "0"
        return
    fi
    
    echo "$actual_iops"
}

# Convert actual throughput to AWS standard throughput
# Parameters: actual_throughput_mibs actual_avg_io_size_kib
# Returns: AWS standard throughput (MiB/s)
# Throughput does not need conversion, return actual value directly
convert_to_aws_standard_throughput() {
    local actual_throughput_mibs="$1"
    local actual_avg_io_size_kib="$2"
    
    # Input validation
    if [[ -z "$actual_throughput_mibs" ]]; then
        echo "Error: convert_to_aws_standard_throughput requires throughput parameter" >&2
        return 1
    fi
    
    # 🔧 Throughput does not need conversion by 128 KiB baseline, return actual value directly
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

# Recommend EBS type (only supports gp3, io2, instance-store)
# Parameters: aws_standard_iops actual_throughput_mibs
# Returns: Recommended EBS type
recommend_ebs_type() {
    local aws_standard_iops=$1
    local actual_throughput_mibs=$2
    
    # Check if gp3 can satisfy
    if (( $(awk "BEGIN {print ($aws_standard_iops <= 80000 && $actual_throughput_mibs <= 2000) ? 1 : 0}") )); then
        echo "gp3"
        return
    fi
    
    # Check if io2 can satisfy
    local io2_throughput=$(calculate_io2_throughput "$aws_standard_iops")
    if (( $(awk "BEGIN {print ($aws_standard_iops <= 256000 && $io2_throughput >= $actual_throughput_mibs) ? 1 : 0}") )); then
        echo "io2"
        return
    fi
    
    # If EBS cannot satisfy, recommend instance-store
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
export -f convert_to_aws_standard_iops
export -f convert_to_aws_standard_throughput
export -f calculate_io2_throughput
export -f recommend_ebs_type
export -f calculate_weighted_avg_io_size
export -f analyze_instance_store_performance
export -f is_accounts_configured

# If script is executed directly, display help information
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "AWS EBS IOPS/Throughput Standard Conversion Script"
    echo "Usage examples:"
    echo "  source ebs_converter.sh"
    echo "  convert_to_aws_standard_iops 1000 32"
    echo "  convert_to_aws_standard_throughput 100 64"
    echo "  calculate_io2_throughput 20000"
fi