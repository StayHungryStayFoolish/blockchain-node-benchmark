#!/bin/bash

# AWS EBS IOPS/Throughput标准转换脚本
# 用于将实际的IOPS和I/O大小转换为AWS EBS标准基准

# AWS标准基准常量
# AWS EBS基准配置 - 使用system_config.sh中的配置，如果不可用则使用默认值
# 注意：优先使用配置文件中的值，避免readonly冲突
AWS_EBS_BASELINE_IO_SIZE_KIB=${AWS_EBS_BASELINE_IO_SIZE_KIB:-16}

AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB=${AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB:-128}

if [[ -z "${IO2_THROUGHPUT_RATIO:-}" ]]; then
    readonly IO2_THROUGHPUT_RATIO=0.256
fi

if [[ -z "${IO2_MAX_THROUGHPUT:-}" ]]; then
    readonly IO2_MAX_THROUGHPUT=4000
fi

# 注意: instance-store类型不使用AWS EBS标准转换
# instance-store使用实际IOPS和throughput，不需要16KiB基准转换

# 转换实际IOPS为AWS标准IOPS
# 参数: actual_iops actual_avg_io_size_kib
# 返回: AWS标准IOPS (基于16 KiB)
convert_to_aws_standard_iops() {
    local actual_iops=$1
    local actual_avg_io_size_kib=$2
    
    if (( $(awk "BEGIN {print ($actual_iops <= 0) ? 1 : 0}") )); then
        echo "0"
        return
    fi
    
    if (( $(awk "BEGIN {print ($actual_avg_io_size_kib <= 0) ? 1 : 0}") )); then
        echo "0"
        return
    fi
    
    local aws_standard_iops=$(awk "BEGIN {printf \"%.2f\", $actual_iops * ($actual_avg_io_size_kib / $AWS_EBS_BASELINE_IO_SIZE_KIB)}")
    echo "$aws_standard_iops"
}

# 转换实际throughput为AWS标准throughput
# 参数: actual_throughput_mibs actual_avg_io_size_kib
# 返回: AWS标准throughput (基于128 KiB)
convert_to_aws_standard_throughput() {
    local actual_throughput_mibs="$1"
    local actual_avg_io_size_kib="$2"
    
    # 输入验证
    if [[ -z "$actual_throughput_mibs" || -z "$actual_avg_io_size_kib" ]]; then
        echo "错误: convert_to_aws_standard_throughput需要2个参数" >&2
        return 1
    fi
    
    # 避免除零错误
    if [[ $(awk "BEGIN {print ($actual_avg_io_size_kib == 0) ? 1 : 0}") -eq 1 ]]; then
        echo "$actual_throughput_mibs"  # IO大小为0时，返回原始值
        return 0
    fi
    
    # 使用system_config.sh中定义的AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB变量
    local aws_standard_throughput=$(awk "BEGIN {printf \"%.2f\", $actual_throughput_mibs * ($actual_avg_io_size_kib / $AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB)}")
    
    echo "$aws_standard_throughput"
}

# 计算io2 Block Express自动吞吐量
# 参数: iops
# 返回: 自动计算的吞吐量 (MiB/s)
calculate_io2_throughput() {
    local iops=$1
    local calculated_throughput=$(awk "BEGIN {printf \"%.2f\", $iops * $IO2_THROUGHPUT_RATIO}")
    local actual_throughput=$(awk "BEGIN {printf \"%.2f\", ($calculated_throughput > $IO2_MAX_THROUGHPUT) ? $IO2_MAX_THROUGHPUT : $calculated_throughput}")
    echo "$actual_throughput"
}

# instance-store性能分析 (不进行AWS标准转换)
# 参数: actual_iops actual_throughput_mibs configured_iops configured_throughput
# 返回: 性能分析结果
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

# 推荐EBS类型 (仅支持gp3, io2, instance-store)
# 参数: aws_standard_iops actual_throughput_mibs
# 返回: 推荐的EBS类型
recommend_ebs_type() {
    local aws_standard_iops=$1
    local actual_throughput_mibs=$2
    
    # 检查gp3是否可满足
    if (( $(awk "BEGIN {print ($aws_standard_iops <= 16000 && $actual_throughput_mibs <= 1000) ? 1 : 0}") )); then
        echo "gp3"
        return
    fi
    
    # 检查io2是否可满足
    local io2_throughput=$(calculate_io2_throughput "$aws_standard_iops")
    if (( $(awk "BEGIN {print ($aws_standard_iops <= 256000 && $io2_throughput >= $actual_throughput_mibs) ? 1 : 0}") )); then
        echo "io2"
        return
    fi
    
    # 如果EBS无法满足，推荐instance-store
    echo "instance-store"
}

# 计算平均I/O大小 (从iostat数据)
# 参数: r_s w_s rkb_s wkb_s
# 返回: 加权平均I/O大小 (KiB)
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

# 从扇区转换为KiB
# 参数: sectors
# 返回: KiB
sectors_to_kib() {
    local sectors=$1
    awk "BEGIN {printf \"%.2f\", $sectors * 0.5}"
}

# 主函数：完整的EBS性能转换
# 参数: device_name r_s w_s rkb_s wkb_s rareq_sz wareq_sz
# 返回: JSON格式的转换结果
convert_ebs_performance() {
    local device_name=$1
    local r_s=$2
    local w_s=$3
    local rkb_s=$4
    local wkb_s=$5
    local rareq_sz=$6
    local wareq_sz=$7
    
    # 计算基础指标
    local total_iops=$(awk "BEGIN {printf \"%.2f\", $r_s + $w_s}")
    local total_throughput_kbs=$(awk "BEGIN {printf \"%.2f\", $rkb_s + $wkb_s}")
    local total_throughput_mibs=$(awk "BEGIN {printf \"%.2f\", $total_throughput_kbs / 1024}")
    
    # 计算平均I/O大小
    local avg_read_io_kib=$(sectors_to_kib "$rareq_sz")
    local avg_write_io_kib=$(sectors_to_kib "$wareq_sz")
    local weighted_avg_io_kib=$(calculate_weighted_avg_io_size "$r_s" "$w_s" "$rkb_s" "$wkb_s")
    
    # 转换为AWS标准
    local aws_standard_iops=$(convert_to_aws_standard_iops "$total_iops" "$weighted_avg_io_kib")
    
    # 推荐EBS类型
    local recommended_type=$(recommend_ebs_type "$aws_standard_iops" "$total_throughput_mibs")
    
    # 输出JSON格式结果
    cat << EOF
{
    "device": "$device_name",
    "actual_performance": {
        "total_iops": $total_iops,
        "read_iops": $r_s,
        "write_iops": $w_s,
        "total_throughput_mibs": $total_throughput_mibs,
        "avg_read_io_kib": $avg_read_io_kib,
        "avg_write_io_kib": $avg_write_io_kib,
        "weighted_avg_io_kib": $weighted_avg_io_kib
    },
    "aws_standard": {
        "aws_standard_iops": $aws_standard_iops,
        "conversion_formula": "实际IOPS × (实际平均I/O大小KiB ÷ 16)",
        "calculation": "$total_iops × ($weighted_avg_io_kib ÷ 16) = $aws_standard_iops",
        "note": "仅适用于EBS卷，instance-store使用实际IOPS"
    },
    "recommendation": {
        "ebs_type": "$recommended_type",
        "io2_auto_throughput": $(calculate_io2_throughput "$aws_standard_iops"),
        "gp3_max_iops": 16000,
        "gp3_max_throughput": 1000,
        "io2_max_iops": 256000,
        "io2_max_throughput": 4000
    }
}
EOF
}

# 检查 ACCOUNTS 设备是否配置
# 判断标准：3个关键环境变量都必须配置
# 返回: 0=已配置, 1=未配置
is_accounts_configured() {
    [[ -n "${ACCOUNTS_DEVICE:-}" && -n "${ACCOUNTS_VOL_TYPE:-}" && -n "${ACCOUNTS_VOL_MAX_IOPS:-}" ]]
}

# 导出函数
export -f convert_to_aws_standard_iops
export -f convert_to_aws_standard_throughput
export -f calculate_io2_throughput
export -f recommend_ebs_type
export -f calculate_weighted_avg_io_size
export -f sectors_to_kib
export -f convert_ebs_performance
export -f analyze_instance_store_performance
export -f is_accounts_configured

# 如果直接执行此脚本，显示帮助信息
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "AWS EBS IOPS/Throughput标准转换脚本"
    echo "用法示例:"
    echo "  source ebs_converter.sh"
    echo "  convert_to_aws_standard_iops 1000 32"
    echo "  convert_to_aws_standard_throughput 100 64"
    echo "  calculate_io2_throughput 20000"
    echo "  convert_ebs_performance nvme1n1 6687.17 7657.43 43668.93 282862.29 6.53 36.94"
fi