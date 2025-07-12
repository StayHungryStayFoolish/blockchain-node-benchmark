#!/bin/bash
# EC2实例信息收集脚本
# 用于收集EC2实例的基本信息，使用IMDSv2标准

# AWS元数据服务配置 - 使用config.sh中的配置，如果不可用则使用默认值
readonly AWS_METADATA_ENDPOINT="${AWS_METADATA_ENDPOINT:-http://169.254.169.254}"
readonly AWS_METADATA_TOKEN_TTL="${AWS_METADATA_TOKEN_TTL:-21600}"
readonly AWS_METADATA_API_VERSION="${AWS_METADATA_API_VERSION:-latest}"

# 获取IMDSv2 token
get_imds_token() {
    local token=$(curl -X PUT "${AWS_METADATA_ENDPOINT}/${AWS_METADATA_API_VERSION}/api/token" \
        -H "X-aws-ec2-metadata-token-ttl-seconds: ${AWS_METADATA_TOKEN_TTL}" \
        -s --max-time 5 2>/dev/null)
    echo "$token"
}

# 使用token获取元数据
get_metadata_with_token() {
    local token=$1
    local path=$2
    
    if [[ -n "$token" ]]; then
        curl -H "X-aws-ec2-metadata-token: $token" \
            -s --max-time 5 "${AWS_METADATA_ENDPOINT}/${AWS_METADATA_API_VERSION}/meta-data/$path" 2>/dev/null
    else
        echo ""
    fi
}

# 获取EC2实例类型
get_ec2_instance_type() {
    # 如果config.sh中设置了EC2_INSTANCE_TYPE，优先使用
    if [[ -n "$EC2_INSTANCE_TYPE" ]]; then
        echo "$EC2_INSTANCE_TYPE"
        return
    fi
    
    # 使用IMDSv2获取实例类型
    local token=$(get_imds_token)
    local instance_type=$(get_metadata_with_token "$token" "instance-type")
    
    if [[ -n "$instance_type" ]]; then
        echo "$instance_type"
    else
        echo "Unknown"
    fi
}

# 获取vCPU数量
get_vcpu_count() {
    local vcpu_count=$(nproc 2>/dev/null)
    if [[ -n "$vcpu_count" ]]; then
        echo "$vcpu_count"
    else
        echo "Unknown"
    fi
}

# 获取内存大小 (优先使用AWS官方规格，默认单位GiB)
get_memory_size() {
    # 如果config.sh中设置了EC2_OFFICIAL_MEMORY，优先使用
    if [[ -n "$EC2_OFFICIAL_MEMORY" ]]; then
        # 简化配置：只需要数字，默认单位为GiB
        if [[ "$EC2_OFFICIAL_MEMORY" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
            echo "$EC2_OFFICIAL_MEMORY GiB"
        else
            # 如果不是纯数字，直接使用（兼容旧格式）
            echo "$EC2_OFFICIAL_MEMORY"
        fi
        return
    fi
    
    # 否则使用系统检测值
    local memory_size=$(free -h 2>/dev/null | grep Mem | awk '{print $2}')
    if [[ -n "$memory_size" ]]; then
        echo "$memory_size"
    else
        echo "Unknown"
    fi
}

# 获取内存大小（以MB为单位的数值）
get_memory_size_mb() {
    # 如果设置了官方内存规格，尝试解析
    if [[ -n "$EC2_OFFICIAL_MEMORY" ]]; then
        local memory_value
        local memory_unit
        
        # 简化配置：如果是纯数字，默认为GiB
        if [[ "$EC2_OFFICIAL_MEMORY" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
            memory_value="$EC2_OFFICIAL_MEMORY"
            memory_unit="GiB"
        else
            # 兼容旧格式 "数字 单位"
            memory_value=$(echo "$EC2_OFFICIAL_MEMORY" | awk '{print $1}')
            memory_unit=$(echo "$EC2_OFFICIAL_MEMORY" | awk '{print $2}')
        fi
        
        # 验证数值是否为有效数字（包括小数）
        if [[ "$memory_value" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
            case "$memory_unit" in
                "GiB"|"GB"|"")  # 空单位默认为GiB
                    local result=$(echo "scale=0; $memory_value * 1024" | bc 2>/dev/null)
                    echo "${result:-0}"
                    ;;
                "TiB"|"TB")
                    local result=$(echo "scale=0; $memory_value * 1024 * 1024" | bc 2>/dev/null)
                    echo "${result:-0}"
                    ;;
                *)
                    # 如果单位无效，回退到系统检测
                    local memory_mb=$(free -m 2>/dev/null | grep Mem | awk '{print $2}')
                    echo "${memory_mb:-0}"
                    ;;
            esac
        else
            # 如果数值无效，回退到系统检测
            local memory_mb=$(free -m 2>/dev/null | grep Mem | awk '{print $2}')
            echo "${memory_mb:-0}"
        fi
    else
        # 使用系统检测值
        local memory_mb=$(free -m 2>/dev/null | grep Mem | awk '{print $2}')
        echo "${memory_mb:-0}"
    fi
}

# 获取EC2可用区
get_ec2_availability_zone() {
    local token=$(get_imds_token)
    local az=$(get_metadata_with_token "$token" "placement/availability-zone")
    
    if [[ -n "$az" ]]; then
        echo "$az"
    else
        echo "Unknown"
    fi
}

# 获取EC2区域
get_ec2_region() {
    local token=$(get_imds_token)
    local region=$(get_metadata_with_token "$token" "placement/region")
    
    if [[ -n "$region" ]]; then
        echo "$region"
    else
        echo "Unknown"
    fi
}

# 获取实例ID
get_ec2_instance_id() {
    local token=$(get_imds_token)
    local instance_id=$(get_metadata_with_token "$token" "instance-id")
    
    if [[ -n "$instance_id" ]]; then
        echo "$instance_id"
    else
        echo "Unknown"
    fi
}

# 获取完整的EC2信息（JSON格式）
get_ec2_info_json() {
    local instance_type=$(get_ec2_instance_type)
    local vcpu_count=$(get_vcpu_count)
    local memory_size=$(get_memory_size)
    local memory_mb=$(get_memory_size_mb)
    local availability_zone=$(get_ec2_availability_zone)
    local region=$(get_ec2_region)
    local instance_id=$(get_ec2_instance_id)
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    # 确保memory_mb是有效数字
    if ! [[ "$memory_mb" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        memory_mb="0"
    fi
    
    # 确定内存来源
    local memory_source
    local note
    if [[ -n "$EC2_OFFICIAL_MEMORY" ]]; then
        memory_source="AWS_Official_Config"
        note="Using AWS official memory specification from config."
    else
        memory_source="System_Detection"
        note="Memory from system detection may differ from AWS specs. Set EC2_OFFICIAL_MEMORY in config.sh for accurate values."
    fi
    
    cat << EOF
{
    "instance_type": "$instance_type",
    "vcpu_count": "$vcpu_count",
    "memory_size": "$memory_size",
    "memory_mb": $memory_mb,
    "availability_zone": "$availability_zone",
    "region": "$region",
    "instance_id": "$instance_id",
    "timestamp": "$timestamp",
    "memory_source": "$memory_source",
    "note": "$note"
}
EOF
}

# 获取简化的EC2信息（用于CSV或日志）
get_ec2_info_csv() {
    local instance_type=$(get_ec2_instance_type)
    local vcpu_count=$(get_vcpu_count)
    local memory_size=$(get_memory_size)
    
    echo "$instance_type,$vcpu_count,$memory_size"
}

# 显示EC2信息（人类可读格式）
show_ec2_info() {
    echo "=== EC2 Instance Information ==="
    echo "Instance Type: $(get_ec2_instance_type)"
    echo "vCPU Count: $(get_vcpu_count)"
    echo "Memory Size: $(get_memory_size)"
    if [[ -n "$EC2_OFFICIAL_MEMORY" ]]; then
        echo "Memory Source: AWS Official Configuration"
    else
        echo "Memory Source: System Detection (may differ from AWS specs)"
        echo "  Tip: Set EC2_OFFICIAL_MEMORY in config.sh for accurate AWS specs"
    fi
    echo "Availability Zone: $(get_ec2_availability_zone)"
    echo "Region: $(get_ec2_region)"
    echo "Instance ID: $(get_ec2_instance_id)"
    echo "Collected at: $(date)"
    echo ""
}

# 验证是否在EC2环境中运行 (使用IMDSv2)
is_running_on_ec2() {
    local token=$(get_imds_token)
    if [[ -n "$token" ]]; then
        local test_result=$(curl -s --max-time 3 \
            -H "X-aws-ec2-metadata-token: $token" \
            ${AWS_METADATA_ENDPOINT}/${AWS_METADATA_API_VERSION}/meta-data/ 2>/dev/null)
        if [[ -n "$test_result" ]]; then
            return 0  # 在EC2中运行
        fi
    fi
    return 1  # 不在EC2中运行
}

# 如果直接执行此脚本，显示EC2信息
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # 尝试加载config.sh
    if [[ -f "$(dirname "$0")/config.sh" ]]; then
        source "$(dirname "$0")/../config/config.sh"
    fi
    
    if is_running_on_ec2; then
        show_ec2_info
        echo "JSON格式:"
        get_ec2_info_json
    else
        echo "警告: 此脚本不在EC2环境中运行，某些信息可能不可用"
        show_ec2_info
    fi
fi
