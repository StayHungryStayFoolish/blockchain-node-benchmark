#!/bin/bash
# AWS EBS IOPS/Throughput标准转换脚本
# 用于将实际的IOPS和I/O大小转换为AWS EBS标准基准

# AWS标准基准常量
# AWS EBS基准配置 - 使用config.sh中的配置，如果不可用则使用默认值
# 注意：如果变量已经定义（如从config.sh加载），则不重新定义
if [[ -z "${AWS_EBS_BASELINE_IO_SIZE_KIB:-}" ]]; then
    readonly AWS_EBS_BASELINE_IO_SIZE_KIB=16
fi
readonly IO2_THROUGHPUT_RATIO=0.256
readonly IO2_MAX_THROUGHPUT=4000

# 注意: instance-store类型不使用AWS EBS标准转换
# instance-store使用实际IOPS和throughput，不需要16KiB基准转换

# 转换实际IOPS为AWS标准IOPS
# 参数: actual_iops actual_avg_io_size_kib
# 返回: AWS标准IOPS (基于16 KiB)
convert_to_aws_standard_iops() {
    local actual_iops=$1
    local actual_avg_io_size_kib=$2
    
    if (( $(echo "$actual_iops <= 0" | bc -l) )); then
        echo "0"
        return
    fi
    
    if (( $(echo "$actual_avg_io_size_kib <= 0" | bc -l) )); then
        echo "0"
        return
    fi
    
    local aws_standard_iops=$(echo "scale=2; $actual_iops * ($actual_avg_io_size_kib / $AWS_EBS_BASELINE_IO_SIZE_KIB)" | bc)
    echo "$aws_standard_iops"
}

# 计算io2 Block Express自动吞吐量
# 参数: iops
# 返回: 自动计算的吞吐量 (MiB/s)
calculate_io2_throughput() {
    local iops=$1
    
    local calculated_throughput=$(echo "scale=2; $iops * $IO2_THROUGHPUT_RATIO" | bc)
    local actual_throughput=$(echo "if ($calculated_throughput > $IO2_MAX_THROUGHPUT) $IO2_MAX_THROUGHPUT else $calculated_throughput" | bc)
    
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
    if (( $(echo "$aws_standard_iops <= 16000 && $actual_throughput_mibs <= 1000" | bc -l) )); then
        echo "gp3"
        return
    fi
    
    # 检查io2是否可满足
    local io2_throughput=$(calculate_io2_throughput "$aws_standard_iops")
    if (( $(echo "$aws_standard_iops <= 256000 && $io2_throughput >= $actual_throughput_mibs" | bc -l) )); then
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
    
    local total_iops=$(echo "scale=2; $r_s + $w_s" | bc)
    local total_throughput_kbs=$(echo "scale=2; $rkb_s + $wkb_s" | bc)
    
    if (( $(echo "$total_iops <= 0" | bc -l) )); then
        echo "0"
        return
    fi
    
    local avg_io_kib=$(echo "scale=2; $total_throughput_kbs / $total_iops" | bc)
    echo "$avg_io_kib"
}

# 从扇区转换为KiB
# 参数: sectors
# 返回: KiB
sectors_to_kib() {
    local sectors=$1
    echo "scale=2; $sectors * 0.5" | bc
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
    local total_iops=$(echo "scale=2; $r_s + $w_s" | bc)
    local total_throughput_kbs=$(echo "scale=2; $rkb_s + $wkb_s" | bc)
    local total_throughput_mibs=$(echo "scale=2; $total_throughput_kbs / 1024" | bc)
    
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

# 如果直接执行此脚本，显示帮助信息
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "AWS EBS IOPS/Throughput标准转换脚本"
    echo "用法示例:"
    echo "  source ebs_converter.sh"
    echo "  convert_to_aws_standard_iops 1000 32"
    echo "  calculate_io2_throughput 20000"
    echo "  convert_ebs_performance nvme1n1 6687.17 7657.43 43668.93 282862.29 6.53 36.94"
fi
