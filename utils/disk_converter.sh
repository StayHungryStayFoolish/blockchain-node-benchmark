#!/bin/bash

# AWS EBS IOPS/Throughput Processing Script
# Used for processing Disk performance metrics, type recommendations, and io2 throughput calculation

# AWS EBS throughput baseline (for throughput conversion, maintain compatibility)
AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB=${AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB:-128}

if [[ -z "${IO2_THROUGHPUT_RATIO:-}" ]]; then
    readonly IO2_THROUGHPUT_RATIO=0.256
fi

if [[ -z "${IO2_MAX_THROUGHPUT:-}" ]]; then
    readonly IO2_MAX_THROUGHPUT=4000
fi

# Note: IOPS conversion is provider-aware via get_iops_conversion_func (CP-1 双云对等).
#   AWS EBS: I/O size capped at 256 KiB (SSD) / 1024 KiB (HDD) — count splits by ceil(io_size/cap).
#            官方实证: analysis-notes/aws-gcp-io-counting-rules-verified.md (AWS EBS docs:
#            "I/O size is capped at 256 KiB for SSD volumes and 1,024 KiB for HDD volumes")
#   GCP PD/Hyperdisk + other: passthrough (不按 I/O size 拆分,直接用 r/s+w/s).
# 分流键来自 config/providers/{aws,gcp,other}_provider.sh 的 get_iops_conversion_func.

# 磁盘类型 → IOPS 拆分上限 io_cap (KiB). B 核心: 计算规则按磁盘类型定, 不只按 provider.
# 依据 analysis-notes/aws-gcp-io-counting-rules-verified.md (4 云厂商官方文档实证 2026-05-19):
#   AWS EBS SSD (gp3/io2)   → 256 KiB  (官方: "I/O size capped at 256 KiB for SSD")
#   AWS EBS HDD (st1/sc1)   → 1024 KiB (官方: "1,024 KiB for HDD volumes"; st1/sc1 IOPS 按 1MiB 算)
#   GCP 全盘型 (pd-*/hyperdisk-*) / other / instance-store → 不拆分 (passthrough, 返 0 表示 N/A)
# 返回: io_cap KiB (256/1024) 供 AWS 拆分; 0 = 不拆分(passthrough 盘型)。
disk_iops_io_cap_kib() {
    local vol_type="${1:-}"
    case "$vol_type" in
        gp3|io2)        echo "256" ;;    # AWS EBS SSD
        st1|sc1)        echo "1024" ;;   # AWS EBS HDD
        *)              echo "0" ;;      # GCP 盘型/instance-store/other/未配 → 不拆分
    esac
}

# Convert actual IOPS to provider-standard IOPS
# Parameters: actual_iops              - Actual IOPS (r/s + w/s)
#             actual_avg_io_size_kib   - Average I/O size in KiB (used for AWS split)
#             io_cap_kib (optional)    - I/O size cap: 256 (SSD, default) | 1024 (HDD)
#                                        由 caller 经 disk_iops_io_cap_kib "$DATA_VOL_TYPE" 求得
# Returns: provider-standard IOPS
#   AWS:        actual_iops * ceil(avg_io_size_kib / cap)   (保守上界,见官方 merge/split 语义)
#   GCP/other:  actual_iops (passthrough)
# 命名: 函数本就是 provider-aware(按 get_iops_conversion_func 分流), 故主名中立.
convert_to_standard_iops() {
    local actual_iops=$1
    local actual_avg_io_size_kib=${2:-0}
    local io_cap_kib=${3:-256}   # SSD 默认 256 KiB; HDD caller 传 1024

    # 非正 IOPS 直接 0
    if (( $(awk "BEGIN {print ($actual_iops <= 0) ? 1 : 0}") )); then
        echo "0"
        return
    fi

    # provider 分流: getter 不可用时(未 source provider)默认 passthrough,保守不夸大
    local conv_func="passthrough"
    if declare -F get_iops_conversion_func >/dev/null 2>&1; then
        conv_func=$(get_iops_conversion_func)
    fi

    # B 核心: 磁盘类型优先. io_cap_kib=0 表示该盘型不按 io_size 拆分
    # (GCP pd-*/hyperdisk-* / instance-store / other), 直接 passthrough —
    # 即使 provider=aws 也不拆 (盘型决定规则, 不是 provider 一刀切).
    if [[ "$io_cap_kib" == "0" ]]; then
        echo "$actual_iops"
        return
    fi

    case "$conv_func" in
        aws_ssd_ceil_256|aws_*|*ceil*)
            # AWS: 按 I/O size 拆分. io_size<=cap 时 multiplier=1 (无放大).
            # multiplier = ceil(avg_io_size_kib / cap), 最小为 1.
            if (( $(awk "BEGIN {print ($actual_avg_io_size_kib <= 0) ? 1 : 0}") )); then
                # 无 io_size 信息 → 退化为 passthrough(不凭空放大),避免假告警
                echo "$actual_iops"
                return
            fi
            local multiplier
            multiplier=$(awk "BEGIN { m = ($actual_avg_io_size_kib / $io_cap_kib); c = (m == int(m)) ? m : int(m)+1; if (c < 1) c = 1; printf \"%d\", c }")
            awk "BEGIN {printf \"%.2f\", $actual_iops * $multiplier}"
            ;;
        *)
            # GCP / other / passthrough: 不拆分
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
export -f disk_iops_io_cap_kib
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