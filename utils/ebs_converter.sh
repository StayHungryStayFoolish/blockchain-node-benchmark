#!/bin/bash

# AWS EBS IOPS/Throughput 处理脚本
# 用于处理 EBS 性能指标、类型推荐和 io2 吞吐量计算

# AWS EBS 吞吐量基准（用于 throughput 转换，保留兼容性）
AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB=${AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB:-128}

if [[ -z "${IO2_THROUGHPUT_RATIO:-}" ]]; then
    readonly IO2_THROUGHPUT_RATIO=0.256
fi

if [[ -z "${IO2_MAX_THROUGHPUT:-}" ]]; then
    readonly IO2_MAX_THROUGHPUT=4000
fi

# 注意: 所有类型（gp3/io2/instance-store）都使用实际 IOPS 和 throughput
# AWS EBS 按请求次数计数 IOPS，无需基于 I/O 大小进行转换

# 获取 AWS EBS IOPS
# 参数: actual_iops - 实际 IOPS (r/s + w/s)
#       actual_avg_io_size_kib - 平均 I/O 大小（保留参数兼容性，未使用）
# 返回: AWS EBS IOPS（等于实际 IOPS）
# 说明: AWS EBS 按请求次数计数 IOPS，无需转换
# 参考: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html
convert_to_aws_standard_iops() {
    local actual_iops=$1
    local actual_avg_io_size_kib=$2  # 保留参数以保持接口兼容
    
    # AWS EBS IOPS 按请求次数计数，无需转换
    # 参考: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html
    if (( $(awk "BEGIN {print ($actual_iops <= 0) ? 1 : 0}") )); then
        echo "0"
        return
    fi
    
    echo "$actual_iops"
}

# 转换实际throughput为AWS标准throughput
# 参数: actual_throughput_mibs actual_avg_io_size_kib
# 返回: AWS标准throughput (MiB/s)
# Throughput 不需要转换，直接返回实际值
convert_to_aws_standard_throughput() {
    local actual_throughput_mibs="$1"
    local actual_avg_io_size_kib="$2"
    
    # 输入验证
    if [[ -z "$actual_throughput_mibs" ]]; then
        echo "错误: convert_to_aws_standard_throughput需要throughput参数" >&2
        return 1
    fi
    
    # 🔧 Throughput 不需要按 128 KiB 基准转换，直接返回实际值
    # AWS EBS Throughput 配置的就是实际 MiB/s，不需要标准化
    echo "$actual_throughput_mibs"
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
    if (( $(awk "BEGIN {print ($aws_standard_iops <= 80000 && $actual_throughput_mibs <= 2000) ? 1 : 0}") )); then
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
fi