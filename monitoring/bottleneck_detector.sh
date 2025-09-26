#!/bin/bash
# =====================================================================
# 智能瓶颈检测器 - 极限测试专用
# =====================================================================
# 实时监控系统各项指标，自动检测性能瓶颈
# 用于极限测试模式的自动停止条件判断
# 使用统一日志管理器
# =====================================================================

# 严格错误处理 - 但允许在交互式环境中安全使用
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # 脚本直接执行时使用严格模式
    set -euo pipefail
else
    # 被source时使用宽松模式，避免退出shell
    set -uo pipefail
fi

# 安全加载配置文件，避免readonly变量冲突
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "警告: 配置文件加载失败，使用默认配置"
    MONITOR_INTERVAL=${MONITOR_INTERVAL:-10}
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi
source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh"

# 初始化统一日志管理器
init_logger "bottleneck_detector" $LOG_LEVEL "${LOGS_DIR}/bottleneck_detector.log"

# 动态构建设备字段匹配模式 - 修复硬编码设备名问题
build_device_field_patterns() {
    local field_type="$1"  # util, r_await, avg_await, aws_standard_iops, throughput_mibs
    local patterns=()
    
    # DATA设备模式（必须存在）
    patterns+=("data_${LEDGER_DEVICE}_${field_type}")
    
    # ACCOUNTS设备模式（可选）
    if [[ -n "${ACCOUNTS_DEVICE:-}" && -n "${ACCOUNTS_VOL_TYPE:-}" ]]; then
        patterns+=("accounts_${ACCOUNTS_DEVICE}_${field_type}")
    fi

    # 返回用|分隔的模式字符串
    local IFS='|'
    echo "${patterns[*]}"
}

# 构建所有需要的字段模式
EBS_UTIL_PATTERNS=$(build_device_field_patterns "util")
EBS_R_AWAIT_PATTERNS=$(build_device_field_patterns "r_await")
EBS_AVG_AWAIT_PATTERNS=$(build_device_field_patterns "avg_await")
EBS_AWS_IOPS_PATTERNS=$(build_device_field_patterns "aws_standard_iops")
EBS_THROUGHPUT_PATTERNS=$(build_device_field_patterns "throughput_mibs")

log_info "🔧 动态字段模式构建完成:"
log_info "   EBS利用率模式: $EBS_UTIL_PATTERNS"
log_info "   EBS延迟模式: $EBS_R_AWAIT_PATTERNS"

# 错误处理函数
handle_detector_error() {
    local exit_code=$?
    local line_number=$1
    log_error "瓶颈检测器错误发生在第 $line_number 行，退出码: $exit_code"
    log_warn "瓶颈检测器异常退出，但不影响主测试流程"
    # 瓶颈检测器错误不应该中断主测试，返回安全的退出码
    exit 0
}

# 设置错误陷阱
trap 'handle_detector_error $LINENO' ERR

readonly BOTTLENECK_STATUS_FILE="${MEMORY_SHARE_DIR}/bottleneck_status.json"

# 创建性能指标的JSON字符串
create_performance_metrics_json() {
    local cpu_usage="$1"
    local memory_usage="$2"
    local ebs_util="$3"
    local ebs_latency="$4"
    local ebs_aws_iops="$5"
    local ebs_throughput="$6"
    local network_util="$7"
    local error_rate="$8"
    
    cat << EOF
{
    "cpu_usage": ${cpu_usage:-null},
    "memory_usage": ${memory_usage:-null},
    "ebs_util": ${ebs_util:-null},
    "ebs_latency": ${ebs_latency:-null},
    "ebs_aws_iops": ${ebs_aws_iops:-null},
    "ebs_throughput": ${ebs_throughput:-null},
    "network_util": ${network_util:-null},
    "error_rate": ${error_rate:-null}
}
EOF
}

# 统一的瓶颈状态JSON生成函数
generate_bottleneck_status_json() {
    local status="$1"
    local detected="$2"
    local types_csv="$3"
    local values_csv="$4"
    local current_qps="$5"
    local metrics_json="$6"
    
    # 从JSON中提取值
    local cpu_usage=$(echo "$metrics_json" | jq -r '.cpu_usage // null' 2>/dev/null || echo "null")
    local memory_usage=$(echo "$metrics_json" | jq -r '.memory_usage // null' 2>/dev/null || echo "null")
    local ebs_util=$(echo "$metrics_json" | jq -r '.ebs_util // null' 2>/dev/null || echo "null")
    local ebs_latency=$(echo "$metrics_json" | jq -r '.ebs_latency // null' 2>/dev/null || echo "null")
    local ebs_aws_iops=$(echo "$metrics_json" | jq -r '.ebs_aws_iops // null' 2>/dev/null || echo "null")
    local ebs_throughput=$(echo "$metrics_json" | jq -r '.ebs_throughput // null' 2>/dev/null || echo "null")
    local network_util=$(echo "$metrics_json" | jq -r '.network_util // null' 2>/dev/null || echo "null")
    local error_rate=$(echo "$metrics_json" | jq -r '.error_rate // null' 2>/dev/null || echo "null")
    
    # 构建JSON数组
    local types_array="[]"
    local values_array="[]"
    local summary=""
    
    if [[ -n "$types_csv" ]]; then
        types_array="[\"$(echo "$types_csv" | sed 's/,/","/g')\"]"
        values_array="[\"$(echo "$values_csv" | sed 's/,/","/g')\"]"
        summary="$types_csv"
    fi
    
    # 生成统一的JSON结构
    cat > "$BOTTLENECK_STATUS_FILE" << EOF
{
    "status": "$status",
    "bottleneck_detected": $detected,
    "bottleneck_types": $types_array,
    "bottleneck_values": $values_array,
    "bottleneck_summary": "$summary",
    "detection_time": $(if [[ "$detected" == "true" ]]; then echo "\"$(get_unified_timestamp)\""; else echo "null"; fi),
    "current_qps": $current_qps,
    "performance_metrics": {
        "cpu_usage": $cpu_usage,
        "memory_usage": $memory_usage,
        "ebs_util": $ebs_util,
        "ebs_latency": $ebs_latency,
        "ebs_aws_iops": $ebs_aws_iops,
        "ebs_throughput": $ebs_throughput,
        "network_util": $network_util,
        "error_rate": $error_rate
    },
    "ebs_baselines": {
        "data_baseline_iops": ${DATA_VOL_MAX_IOPS:-0},
        "data_baseline_throughput": ${DATA_VOL_MAX_THROUGHPUT:-0},
        "accounts_baseline_iops": ${ACCOUNTS_VOL_MAX_IOPS:-0},
        "accounts_baseline_throughput": ${ACCOUNTS_VOL_MAX_THROUGHPUT:-0}
    },
    "counters": {
        "cpu": ${BOTTLENECK_COUNTERS["cpu"]:-0},
        "memory": ${BOTTLENECK_COUNTERS["memory"]:-0},
        "ebs_util": ${BOTTLENECK_COUNTERS["ebs_util"]:-0},
        "ebs_latency": ${BOTTLENECK_COUNTERS["ebs_latency"]:-0},
        "ebs_aws_iops": ${BOTTLENECK_COUNTERS["ebs_aws_iops"]:-0},
        "ebs_aws_throughput": ${BOTTLENECK_COUNTERS["ebs_aws_throughput"]:-0},
        "network": ${BOTTLENECK_COUNTERS["network"]:-0},
        "ena_limit": ${BOTTLENECK_COUNTERS["ena_limit"]:-0},
        "error_rate": ${BOTTLENECK_COUNTERS["error_rate"]:-0},
        "rpc_latency": ${BOTTLENECK_COUNTERS["rpc_latency"]:-0}
    }
}
EOF
}

# 瓶颈检测计数器 (动态初始化)
declare -A BOTTLENECK_COUNTERS

# 初始化瓶颈检测计数器
initialize_bottleneck_counters() {
    # 基础计数器
    BOTTLENECK_COUNTERS["cpu"]=0
    BOTTLENECK_COUNTERS["memory"]=0
    BOTTLENECK_COUNTERS["network"]=0
    BOTTLENECK_COUNTERS["error_rate"]=0
    BOTTLENECK_COUNTERS["rpc_latency"]=0
    BOTTLENECK_COUNTERS["ena_limit"]=0
    
    # DATA设备计数器
    BOTTLENECK_COUNTERS["ebs_util"]=0
    BOTTLENECK_COUNTERS["ebs_latency"]=0
    BOTTLENECK_COUNTERS["ebs_aws_iops"]=0
    BOTTLENECK_COUNTERS["ebs_aws_throughput"]=0
    
    # ACCOUNTS设备计数器 (如果配置了ACCOUNTS设备)
    if [[ -n "${ACCOUNTS_DEVICE:-}" && -n "${ACCOUNTS_VOL_TYPE:-}" ]]; then
        BOTTLENECK_COUNTERS["accounts_ebs_util"]=0
        BOTTLENECK_COUNTERS["accounts_ebs_latency"]=0
        BOTTLENECK_COUNTERS["accounts_ebs_aws_iops"]=0
        BOTTLENECK_COUNTERS["accounts_ebs_aws_throughput"]=0
        log_debug "已初始化ACCOUNTS设备瓶颈计数器"
    fi
    
    log_debug "瓶颈检测计数器初始化完成"
}

# 初始化瓶颈检测
init_bottleneck_detection() {
    echo "🔍 初始化智能瓶颈检测器..." | tee -a "$BOTTLENECK_LOG"
    
    # 确保状态文件目录存在
    mkdir -p "$(dirname "$BOTTLENECK_STATUS_FILE")"
    log_info "状态文件目录已创建: $(dirname "$BOTTLENECK_STATUS_FILE")"
    
    # 初始化计数器
    initialize_bottleneck_counters
    
    echo "📊 瓶颈检测阈值:" | tee -a "$BOTTLENECK_LOG"
    echo "  CPU使用率: ${BOTTLENECK_CPU_THRESHOLD}%" | tee -a "$BOTTLENECK_LOG"
    echo "  内存使用率: ${BOTTLENECK_MEMORY_THRESHOLD}%" | tee -a "$BOTTLENECK_LOG"
    echo "  EBS利用率: ${BOTTLENECK_EBS_UTIL_THRESHOLD}%" | tee -a "$BOTTLENECK_LOG"
    echo "  EBS延迟: ${BOTTLENECK_EBS_LATENCY_THRESHOLD}ms" | tee -a "$BOTTLENECK_LOG"
    echo "  网络利用率: ${BOTTLENECK_NETWORK_THRESHOLD}%" | tee -a "$BOTTLENECK_LOG"
    echo "  错误率: ${BOTTLENECK_ERROR_RATE_THRESHOLD}%" | tee -a "$BOTTLENECK_LOG"
    
    # 显示EBS基准配置
    if [[ -n "$DATA_VOL_MAX_IOPS" ]]; then
        echo "📋 EBS性能基准:" | tee -a "$BOTTLENECK_LOG"
        echo "  DATA设备基准: ${DATA_VOL_MAX_IOPS} IOPS, ${DATA_VOL_MAX_THROUGHPUT} MiB/s" | tee -a "$BOTTLENECK_LOG"
        
        # 修正：使用完整的ACCOUNTS检查逻辑，与其他地方保持一致
        if [[ -n "${ACCOUNTS_DEVICE:-}" && -n "${ACCOUNTS_VOL_TYPE:-}" && -n "$ACCOUNTS_VOL_MAX_IOPS" && -n "$ACCOUNTS_VOL_MAX_THROUGHPUT" ]]; then
            echo "  ACCOUNTS设备基准: ${ACCOUNTS_VOL_MAX_IOPS} IOPS, ${ACCOUNTS_VOL_MAX_THROUGHPUT} MiB/s" | tee -a "$BOTTLENECK_LOG"
        fi
    fi
    echo "  连续检测次数: ${BOTTLENECK_CONSECUTIVE_COUNT}" | tee -a "$BOTTLENECK_LOG"
    echo ""
    
    # 初始化状态文件
    local empty_metrics=$(create_performance_metrics_json "null" "null" "null" "null" "null" "null" "null" "null")
    generate_bottleneck_status_json "initialized" "false" "" "" "null" "$empty_metrics"
    
    echo "✅ 瓶颈检测器初始化完成"
    echo "📄 状态文件: $BOTTLENECK_STATUS_FILE"
    
    # 验证状态文件是否创建成功
    if [[ -f "$BOTTLENECK_STATUS_FILE" ]]; then
        log_info "瓶颈状态文件已成功创建: $BOTTLENECK_STATUS_FILE"
        echo "📊 初始状态文件内容:"
        cat "$BOTTLENECK_STATUS_FILE" | jq . 2>/dev/null || cat "$BOTTLENECK_STATUS_FILE"
    else
        log_error "瓶颈状态文件创建失败: $BOTTLENECK_STATUS_FILE"
    fi
}

# 检测CPU瓶颈
check_cpu_bottleneck() {
    local cpu_usage="$1"
    
    if (( $(awk "BEGIN {print ($cpu_usage > $BOTTLENECK_CPU_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo 0) )); then
        BOTTLENECK_COUNTERS["cpu"]=$((${BOTTLENECK_COUNTERS["cpu"]} + 1))
        echo "⚠️  CPU瓶颈检测: ${cpu_usage}% > ${BOTTLENECK_CPU_THRESHOLD}% (${BOTTLENECK_COUNTERS["cpu"]}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["cpu"]} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            return 0  # 检测到瓶颈
        fi
    else
        BOTTLENECK_COUNTERS["cpu"]=0  # 重置计数器
    fi
    
    return 1  # 未检测到瓶颈
}

# 检测内存瓶颈
check_memory_bottleneck() {
    local memory_usage="$1"
    
    if (( $(awk "BEGIN {print ($memory_usage > $BOTTLENECK_MEMORY_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo 0) )); then
        BOTTLENECK_COUNTERS["memory"]=$((${BOTTLENECK_COUNTERS["memory"]} + 1))
        echo "⚠️  内存瓶颈检测: ${memory_usage}% > ${BOTTLENECK_MEMORY_THRESHOLD}% (${BOTTLENECK_COUNTERS["memory"]}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["memory"]} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            return 0  # 检测到瓶颈
        fi
    else
        BOTTLENECK_COUNTERS["memory"]=0  # 重置计数器
    fi
    
    return 1  # 未检测到瓶颈
}

check_ebs_bottleneck() {
    local ebs_util="$1"
    local ebs_latency="$2"
    local ebs_aws_iops="$3"
    local ebs_throughput="$4"
    local device_type="${5:-data}" # 设备类型: "data" 或 "accounts"，默认为 "data"
    
    local bottleneck_detected=false
    
    # 根据设备类型选择正确的基准值和计数器前缀
    local baseline_iops="$DATA_VOL_MAX_IOPS"
    local baseline_throughput="$DATA_VOL_MAX_THROUGHPUT"
    local counter_prefix="ebs"
    
    if [[ "$device_type" == "accounts" ]]; then
        # 检查ACCOUNTS设备的基准值是否已配置
        if [[ -n "$ACCOUNTS_VOL_MAX_IOPS" && -n "$ACCOUNTS_VOL_MAX_THROUGHPUT" ]]; then
            baseline_iops="$ACCOUNTS_VOL_MAX_IOPS"
            baseline_throughput="$ACCOUNTS_VOL_MAX_THROUGHPUT"
            counter_prefix="accounts_ebs"
            log_debug "使用ACCOUNTS设备基准: IOPS=$baseline_iops, 吞吐量=$baseline_throughput"
        else
            log_debug "ACCOUNTS设备基准值未配置，使用DATA设备基准值"
        fi
    else
        log_debug "使用DATA设备基准: IOPS=$baseline_iops, 吞吐量=$baseline_throughput"
    fi
    
    # 验证基准值有效性
    if [[ -z "$baseline_iops" || -z "$baseline_throughput" ]]; then
        log_debug "基准值无效，跳过AWS基准瓶颈检测"
        baseline_iops=""
        baseline_throughput=""
    fi
    
    # 检测EBS利用率瓶颈
    if (( $(awk "BEGIN {print ($ebs_util > $BOTTLENECK_EBS_UTIL_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo 0) )); then
        BOTTLENECK_COUNTERS["${counter_prefix}_util"]=$((${BOTTLENECK_COUNTERS["${counter_prefix}_util"]:-0} + 1))
        echo "⚠️  EBS利用率瓶颈检测 (${device_type}): ${ebs_util}% > ${BOTTLENECK_EBS_UTIL_THRESHOLD}% (${BOTTLENECK_COUNTERS["${counter_prefix}_util"]}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["${counter_prefix}_util"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            bottleneck_detected=true
        fi
    else
        BOTTLENECK_COUNTERS["${counter_prefix}_util"]=0
    fi
    
    # 检测EBS延迟瓶颈
    if (( $(awk "BEGIN {print ($ebs_latency > $BOTTLENECK_EBS_LATENCY_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo 0) )); then
        BOTTLENECK_COUNTERS["${counter_prefix}_latency"]=$((${BOTTLENECK_COUNTERS["${counter_prefix}_latency"]:-0} + 1))
        echo "⚠️  EBS延迟瓶颈检测 (${device_type}): ${ebs_latency}ms > ${BOTTLENECK_EBS_LATENCY_THRESHOLD}ms (${BOTTLENECK_COUNTERS["${counter_prefix}_latency"]}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["${counter_prefix}_latency"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            bottleneck_detected=true
        fi
    else
        BOTTLENECK_COUNTERS["${counter_prefix}_latency"]=0
    fi
    
    # AWS基准IOPS瓶颈检测 (使用设备特定的基准值)
    if [[ -n "$ebs_aws_iops" && -n "$baseline_iops" ]]; then
        local aws_iops_utilization=$(awk "BEGIN {printf \"%.4f\", $ebs_aws_iops / $baseline_iops}" 2>/dev/null || echo "0")
        local aws_iops_threshold=$(awk "BEGIN {printf \"%.2f\", ${BOTTLENECK_EBS_IOPS_THRESHOLD:-90} / 100}")
        log_debug "EBS IOPS瓶颈检测阈值: ${BOTTLENECK_EBS_IOPS_THRESHOLD:-90}% (${aws_iops_threshold})"
        
        if (( $(awk "BEGIN {print ($aws_iops_utilization > $aws_iops_threshold) ? 1 : 0}" 2>/dev/null || echo 0) )); then
            BOTTLENECK_COUNTERS["${counter_prefix}_aws_iops"]=$((${BOTTLENECK_COUNTERS["${counter_prefix}_aws_iops"]:-0} + 1))
            echo "⚠️  EBS AWS基准IOPS瓶颈 (${device_type}): ${ebs_aws_iops}/${baseline_iops} (${aws_iops_utilization%.*}%) > ${aws_iops_threshold%.*}% (${BOTTLENECK_COUNTERS["${counter_prefix}_aws_iops"]}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
            
            if [[ ${BOTTLENECK_COUNTERS["${counter_prefix}_aws_iops"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
                bottleneck_detected=true
            fi
        else
            BOTTLENECK_COUNTERS["${counter_prefix}_aws_iops"]=0
        fi
    fi
    
    # AWS基准吞吐量瓶颈检测 (使用设备特定的基准值)
    if [[ -n "$ebs_throughput" && -n "$baseline_throughput" ]]; then
        local aws_throughput_utilization=$(awk "BEGIN {printf \"%.4f\", $ebs_throughput / $baseline_throughput}" 2>/dev/null || echo "0")
        local aws_throughput_threshold=$(awk "BEGIN {printf \"%.2f\", ${BOTTLENECK_EBS_THROUGHPUT_THRESHOLD:-90} / 100}")
        log_debug "EBS Throughput瓶颈检测阈值: ${BOTTLENECK_EBS_THROUGHPUT_THRESHOLD:-90}% (${aws_throughput_threshold})"
        
        if (( $(awk "BEGIN {print ($aws_throughput_utilization > $aws_throughput_threshold) ? 1 : 0}" 2>/dev/null || echo 0) )); then
            BOTTLENECK_COUNTERS["${counter_prefix}_aws_throughput"]=$((${BOTTLENECK_COUNTERS["${counter_prefix}_aws_throughput"]:-0} + 1))
            echo "⚠️  EBS AWS基准吞吐量瓶颈 (${device_type}): ${ebs_throughput}/${baseline_throughput} MiB/s (${aws_throughput_utilization%.*}%) > ${aws_throughput_threshold%.*}% (${BOTTLENECK_COUNTERS["${counter_prefix}_aws_throughput"]}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
            
            if [[ ${BOTTLENECK_COUNTERS["${counter_prefix}_aws_throughput"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
                bottleneck_detected=true
            fi
        else
            BOTTLENECK_COUNTERS["${counter_prefix}_aws_throughput"]=0
        fi
    fi
    
    if [[ "$bottleneck_detected" == "true" ]]; then
        return 0
    else
        return 1
    fi
}

# 检测ENA网络限制瓶颈
check_ena_network_bottleneck() {
    local performance_csv="$1"
    
    # 检查是否启用ENA监控
    if [[ "$ENA_MONITOR_ENABLED" != "true" ]]; then
        return 1
    fi
    
    if [[ ! -f "$performance_csv" ]] || [[ ! -s "$performance_csv" ]]; then
        return 1
    fi
    
    # 获取最新的ENA数据
    local latest_data=$(tail -1 "$performance_csv" 2>/dev/null)
    if [[ -z "$latest_data" ]]; then
        return 1
    fi
    
    local header=$(head -1 "$performance_csv")
    
    # 配置驱动：动态查找所有ENA字段索引
    declare -A ena_field_indices
    declare -A ena_field_values
    
    # 遍历配置中的字段，不硬编码 - 使用标准化数组访问方式
    ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
    for field in "${ena_fields[@]}"; do
        local field_idx=$(echo "$header" | tr ',' '\n' | grep -n "^$field$" | cut -d: -f1)
        if [[ -n "$field_idx" ]]; then
            ena_field_indices["$field"]=$field_idx
            local fields=($(echo "$latest_data" | tr ',' ' '))
            ena_field_values["$field"]="${fields[$((field_idx - 1))]:-0}"
        fi
    done
    
    # 检查是否找到任何ENA字段
    if [[ ${#ena_field_values[@]} -eq 0 ]]; then
        return 1  # 没有找到ENA数据
    fi
    
    # 检测exceeded类型的字段 (基于字段名模式，不硬编码字段列表)
    local exceeded_detected=false
    local exceeded_summary=""
    local exceeded_count=0
    
    for field in "${!ena_field_values[@]}"; do
        if [[ "$field" == *"exceeded"* ]] && [[ "${ena_field_values[$field]}" -gt 0 ]]; then
            exceeded_detected=true
            ((exceeded_count++))
            if [[ -n "$exceeded_summary" ]]; then
                exceeded_summary="$exceeded_summary, $field=${ena_field_values[$field]}"
            else
                exceeded_summary="$field=${ena_field_values[$field]}"
            fi
        fi
    done
    
    # 检测available类型字段的异常低值 (可选的额外检测)
    for field in "${!ena_field_values[@]}"; do
        if [[ "$field" == *"available"* ]]; then
            local available_value="${ena_field_values[$field]}"
            # 如果available值为0，也可能表示资源耗尽
            if [[ "$available_value" -eq 0 ]]; then
                if [[ -n "$exceeded_summary" ]]; then
                    exceeded_summary="$exceeded_summary, $field=0(耗尽)"
                else
                    exceeded_summary="$field=0(耗尽)"
                fi
                exceeded_detected=true
            fi
        fi
    done
    
    if [[ "$exceeded_detected" == "true" ]]; then
        BOTTLENECK_COUNTERS["ena_limit"]=$((${BOTTLENECK_COUNTERS["ena_limit"]} + 1))
        echo "⚠️  ENA网络限制检测: $exceeded_summary (${BOTTLENECK_COUNTERS["ena_limit"]}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["ena_limit"]} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            return 0  # 检测到ENA瓶颈
        fi
    else
        BOTTLENECK_COUNTERS["ena_limit"]=0  # 重置计数器
    fi

    # 未检测到ENA瓶颈
    return 1
}

# 检测通用网络瓶颈 (基于网络利用率阈值)
check_network_bottleneck() {
    local network_util="$1"
    
    if (( $(awk "BEGIN {print ($network_util > $BOTTLENECK_NETWORK_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo 0) )); then
        BOTTLENECK_COUNTERS["network"]=$((${BOTTLENECK_COUNTERS["network"]} + 1))
        echo "⚠️  网络瓶颈检测: ${network_util}% > ${BOTTLENECK_NETWORK_THRESHOLD}% (${BOTTLENECK_COUNTERS["network"]}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["network"]} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            return 0  # 检测到瓶颈
        fi
    else
        BOTTLENECK_COUNTERS["network"]=0  # 重置计数器
    fi
    
    return 1  # 未检测到瓶颈
}

# 获取最新的QPS错误率
get_latest_qps_error_rate() {
    # 查找最新的QPS测试报告文件
    local latest_report=$(find "${REPORTS_DIR}" -name "qps_*_report.txt" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
    
    if [[ -z "$latest_report" || ! -f "$latest_report" ]]; then
        echo "0"
        return
    fi
    
    # 从报告中提取成功率，计算错误率
    local success_rate=$(grep "Success" "$latest_report" | awk '{print $NF}' | sed 's/%//' 2>/dev/null)
    
    if [[ -n "$success_rate" && "$success_rate" =~ ^[0-9]+\.?[0-9]*$ ]]; then
        local error_rate=$(awk "BEGIN {printf \"%.2f\", 100 - $success_rate}" 2>/dev/null || echo "0")
        echo "$error_rate"
    else
        echo "0"
    fi
}

# 检测QPS瓶颈 (错误率和RPC延迟)
check_qps_bottleneck() {
    local current_qps="$1"
    local error_rate="$2"
    
    # 获取最新的QPS测试延迟
    local latest_report=$(find "${REPORTS_DIR}" -name "qps_*_report.txt" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
    local rpc_latency=0
    
    if [[ -n "$latest_report" && -f "$latest_report" ]]; then
        # 提取P99延迟
        rpc_latency=$(grep "Latencies" "$latest_report" | awk -F',' '{print $(NF-1)}' | sed 's/[^0-9.]//g' 2>/dev/null || echo "0")
    fi
    
    local qps_bottleneck_detected=false
    
    # 检测错误率瓶颈
    if (( $(awk "BEGIN {print ($error_rate > $BOTTLENECK_ERROR_RATE_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo 0) )); then
        BOTTLENECK_COUNTERS["error_rate"]=$((${BOTTLENECK_COUNTERS["error_rate"]} + 1))
        echo "⚠️  QPS错误率瓶颈检测: ${error_rate}% > ${BOTTLENECK_ERROR_RATE_THRESHOLD}% (${BOTTLENECK_COUNTERS["error_rate"]}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["error_rate"]} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            qps_bottleneck_detected=true
        fi
    else
        BOTTLENECK_COUNTERS["error_rate"]=0
    fi
    
    # 检测RPC延迟瓶颈 (P99延迟超过1000ms视为瓶颈)
    local rpc_latency_threshold=1000
    if (( $(awk "BEGIN {print ($rpc_latency > $rpc_latency_threshold) ? 1 : 0}" 2>/dev/null || echo 0) )); then
        BOTTLENECK_COUNTERS["rpc_latency"]=$((${BOTTLENECK_COUNTERS["rpc_latency"]} + 1))
        echo "⚠️  RPC延迟瓶颈检测: ${rpc_latency}ms > ${rpc_latency_threshold}ms (${BOTTLENECK_COUNTERS["rpc_latency"]}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["rpc_latency"]} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            qps_bottleneck_detected=true
        fi
    else
        BOTTLENECK_COUNTERS["rpc_latency"]=0
    fi
    
    if [[ "$qps_bottleneck_detected" == "true" ]]; then
        return 0  # 检测到QPS瓶颈
    else
        return 1  # 未检测到QPS瓶颈
    fi
}

# 从性能数据中提取指标
extract_performance_metrics() {
    local performance_csv="$1"
    
    if [[ ! -f "$performance_csv" ]]; then
        echo "0,0,0,0,0,0"  # cpu,memory,ebs_util,ebs_latency,network,error_rate
        return
    fi
    
    # 获取最新的性能数据 (最后一行)
    local latest_data=$(tail -1 "$performance_csv" 2>/dev/null)
    
    if [[ -z "$latest_data" ]]; then
        echo "0,0,0,0,0,0,0,0"  # cpu,memory,ebs_util,ebs_latency,ebs_aws_iops,ebs_throughput,network,error_rate
        return
    fi
    
    # 使用CSV字段映射器动态解析字段位置
    local header=$(head -1 "$performance_csv")
    local field_names=($(echo "$header" | tr ',' ' '))
    local data_values=($(echo "$latest_data" | tr ',' ' '))
    
    # 动态查找字段位置
    local cpu_usage=0
    local memory_usage=0
    local ebs_util=0
    local ebs_latency=0
    local ebs_aws_iops=0
    local ebs_throughput=0
    local network_util=0
    local error_rate=0
    
    # 使用动态字段匹配替代硬编码
    for i in "${!field_names[@]}"; do
        local field_name="${field_names[i]}"
        
        case "$field_name" in
            # CPU和内存字段（保持不变）
            "cpu_usage"|"cpu_percent"|"cpu_total")
                cpu_usage=${data_values[i]:-0}
                ;;
            "mem_usage"|"memory_usage"|"mem_percent")
                memory_usage=${data_values[i]:-0}
                ;;
            # 网络总流量字段（保持不变）
            "net_total_mbps"|"network_total_mbps"|"total_mbps")
                local current_mbps=${data_values[i]:-0}
                network_util=$(awk "BEGIN {printf \"%.2f\", ($current_mbps / $NETWORK_MAX_BANDWIDTH_MBPS) * 100}" 2>/dev/null || echo "0")
                network_util=$(awk "BEGIN {printf \"%.2f\", ($network_util > 100) ? 100 : $network_util}" 2>/dev/null || echo "0")
                ;;
        esac
        
        # 使用动态模式匹配EBS字段
        if [[ "$EBS_UTIL_PATTERNS" == *"$field_name"* ]]; then
            ebs_util=${data_values[i]:-0}
            log_debug "匹配到EBS利用率字段: $field_name = $ebs_util"
        fi
        
        if [[ "$EBS_R_AWAIT_PATTERNS" == *"$field_name"* ]]; then
            ebs_latency=${data_values[i]:-0}
            log_debug "匹配到EBS读延迟字段: $field_name = $ebs_latency"
        elif [[ "$EBS_AVG_AWAIT_PATTERNS" == *"$field_name"* ]] && [[ "$ebs_latency" == "0" ]]; then
            # 如果还没有设置延迟值，使用平均延迟
            ebs_latency=${data_values[i]:-0}
            log_debug "匹配到EBS平均延迟字段: $field_name = $ebs_latency"
        fi
        
        if [[ "$EBS_AWS_IOPS_PATTERNS" == *"$field_name"* ]]; then
            ebs_aws_iops=${data_values[i]:-0}
            log_debug "匹配到EBS AWS IOPS字段: $field_name = $ebs_aws_iops"
        fi
        
        if [[ "$EBS_THROUGHPUT_PATTERNS" == *"$field_name"* ]]; then
            ebs_throughput=${data_values[i]:-0}
            log_debug "匹配到EBS吞吐量字段: $field_name = $ebs_throughput"
        fi
    done
    
    # 这需要读取最新的QPS测试报告文件
    error_rate=$(get_latest_qps_error_rate)
    
    echo "$cpu_usage,$memory_usage,$ebs_util,$ebs_latency,$ebs_aws_iops,$ebs_throughput,$network_util,$error_rate"
}

# 多设备EBS瓶颈检测协调器
detect_all_ebs_bottlenecks() {
    local performance_csv="$1"
    local bottleneck_detected=false
    local bottleneck_info=()
    
    # 读取CSV数据
    if [[ ! -f "$performance_csv" ]]; then
        log_debug "性能数据文件不存在: $performance_csv"
        return 1
    fi
    
    local latest_line=$(tail -n 1 "$performance_csv")
    if [[ -z "$latest_line" ]]; then
        log_debug "性能数据文件为空"
        return 1
    fi
    
    # 解析CSV表头和数据
    local header_line=$(head -n 1 "$performance_csv")
    IFS=',' read -ra field_names <<< "$header_line"
    IFS=',' read -ra data_values <<< "$latest_line"
    
    # 检测DATA设备
    local data_util=0 data_latency=0 data_aws_iops=0 data_throughput=0
    
    for i in "${!field_names[@]}"; do
        local field_name="${field_names[i]}"
        
        # DATA设备字段匹配
        if [[ "$field_name" == data_${LEDGER_DEVICE}_util ]]; then
            data_util=${data_values[i]:-0}
        elif [[ "$field_name" == data_${LEDGER_DEVICE}_r_await ]]; then
            data_latency=${data_values[i]:-0}
        elif [[ "$field_name" == data_${LEDGER_DEVICE}_avg_await ]] && [[ "$data_latency" == "0" ]]; then
            data_latency=${data_values[i]:-0}
        elif [[ "$field_name" == data_${LEDGER_DEVICE}_aws_standard_iops ]]; then
            data_aws_iops=${data_values[i]:-0}
        elif [[ "$field_name" == data_${LEDGER_DEVICE}_throughput_mibs ]]; then
            data_throughput=${data_values[i]:-0}
        fi
    done
    
    # 检测DATA设备瓶颈
    if check_ebs_bottleneck "$data_util" "$data_latency" "$data_aws_iops" "$data_throughput" "data"; then
        bottleneck_detected=true
        bottleneck_info+=("DATA设备瓶颈: 利用率=${data_util}%, 延迟=${data_latency}ms, AWS_IOPS=${data_aws_iops}, 吞吐量=${data_throughput}MiB/s")
    fi
    
    # 检测ACCOUNTS设备 (如果配置了)
    if [[ -n "${ACCOUNTS_DEVICE:-}" && -n "${ACCOUNTS_VOL_TYPE:-}" ]]; then
        local accounts_util=0 accounts_latency=0 accounts_aws_iops=0 accounts_throughput=0
        
        for i in "${!field_names[@]}"; do
            local field_name="${field_names[i]}"
            
            # ACCOUNTS设备字段匹配
            if [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_util ]]; then
                accounts_util=${data_values[i]:-0}
            elif [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_r_await ]]; then
                accounts_latency=${data_values[i]:-0}
            elif [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_avg_await ]] && [[ "$accounts_latency" == "0" ]]; then
                accounts_latency=${data_values[i]:-0}
            elif [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_aws_standard_iops ]]; then
                accounts_aws_iops=${data_values[i]:-0}
            elif [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_throughput_mibs ]]; then
                accounts_throughput=${data_values[i]:-0}
            fi
        done
        
        # 检测ACCOUNTS设备瓶颈
        if check_ebs_bottleneck "$accounts_util" "$accounts_latency" "$accounts_aws_iops" "$accounts_throughput" "accounts"; then
            bottleneck_detected=true
            bottleneck_info+=("ACCOUNTS设备瓶颈: 利用率=${accounts_util}%, 延迟=${accounts_latency}ms, AWS_IOPS=${accounts_aws_iops}, 吞吐量=${accounts_throughput}MiB/s")
        fi
    fi
    
    # 输出检测结果
    if [[ "$bottleneck_detected" == "true" ]]; then
        echo "🚨 检测到EBS瓶颈:" | tee -a "$BOTTLENECK_LOG"
        for info in "${bottleneck_info[@]}"; do
            echo "   - $info" | tee -a "$BOTTLENECK_LOG"
        done
        return 0
    else
        log_debug "未检测到EBS瓶颈"
        return 1
    fi
}

# 综合瓶颈检测
detect_bottleneck() {
    local current_qps="$1"
    local performance_csv="$2"
    
    # 提取性能指标
    local metrics=$(extract_performance_metrics "$performance_csv")
    local cpu_usage=$(echo "$metrics" | cut -d',' -f1)
    local memory_usage=$(echo "$metrics" | cut -d',' -f2)
    local ebs_util=$(echo "$metrics" | cut -d',' -f3)
    local ebs_latency=$(echo "$metrics" | cut -d',' -f4)
    local ebs_aws_iops=$(echo "$metrics" | cut -d',' -f5)
    local ebs_throughput=$(echo "$metrics" | cut -d',' -f6)
    local network_util=$(echo "$metrics" | cut -d',' -f7)
    local error_rate=$(echo "$metrics" | cut -d',' -f8)
    
    echo "📊 当前QPS: $current_qps, 性能指标: CPU=${cpu_usage}%, MEM=${memory_usage}%, EBS=${ebs_util}%/${ebs_latency}ms, AWS_IOPS=${ebs_aws_iops}, THROUGHPUT=${ebs_throughput}MiB/s, NET=${network_util}%, ERR=${error_rate}%" | tee -a "$BOTTLENECK_LOG"
    
    # 创建性能指标JSON
    local metrics_json=$(create_performance_metrics_json "$cpu_usage" "$memory_usage" "$ebs_util" "$ebs_latency" "$ebs_aws_iops" "$ebs_throughput" "$network_util" "$error_rate")
    
    # 检测各种瓶颈
    local bottleneck_detected=false
    local bottleneck_types=()
    local bottleneck_values=()
    
    if check_cpu_bottleneck "$cpu_usage"; then
        bottleneck_detected=true
        bottleneck_types+=("CPU")
        bottleneck_values+=("${cpu_usage}%")
    fi
    
    if check_memory_bottleneck "$memory_usage"; then
        bottleneck_detected=true
        bottleneck_types+=("Memory")
        bottleneck_values+=("${memory_usage}%")
    fi
    
    # 检测DATA设备EBS瓶颈
    if check_ebs_bottleneck "$ebs_util" "$ebs_latency" "$ebs_aws_iops" "$ebs_throughput" "data"; then
        bottleneck_detected=true
        if [[ ${BOTTLENECK_COUNTERS["ebs_util"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            bottleneck_types+=("DATA_EBS_Utilization")
            bottleneck_values+=("${ebs_util}%")
        fi
        if [[ ${BOTTLENECK_COUNTERS["ebs_latency"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            bottleneck_types+=("DATA_EBS_Latency")
            bottleneck_values+=("${ebs_latency}ms")
        fi
        if [[ ${BOTTLENECK_COUNTERS["ebs_aws_iops"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            bottleneck_types+=("EBS_AWS_IOPS")
            bottleneck_values+=("${ebs_aws_iops}/${DATA_VOL_MAX_IOPS}")
        fi
        if [[ ${BOTTLENECK_COUNTERS["ebs_aws_throughput"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            bottleneck_types+=("EBS_AWS_Throughput")
            bottleneck_values+=("${ebs_throughput}/${DATA_VOL_MAX_THROUGHPUT}MiB/s")
        fi
    fi
    
    # 检测ACCOUNTS设备EBS瓶颈 (如果配置)
    if [[ -n "${ACCOUNTS_DEVICE:-}" && -n "${ACCOUNTS_VOL_TYPE:-}" ]]; then
        # 获取ACCOUNTS设备的性能指标
        local accounts_util=0
        local accounts_latency=0
        local accounts_aws_iops=0
        local accounts_throughput=0
        
        # 从CSV数据中提取ACCOUNTS设备指标
        for i in "${!field_names[@]}"; do
            local field_name="${field_names[i]}"
            
            # 匹配ACCOUNTS设备字段
            if [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_util ]]; then
                accounts_util=${data_values[i]:-0}
            fi
            
            if [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_r_await ]]; then
                accounts_latency=${data_values[i]:-0}
            elif [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_avg_await ]] && [[ "$accounts_latency" == "0" ]]; then
                accounts_latency=${data_values[i]:-0}
            fi
            
            if [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_aws_standard_iops ]]; then
                accounts_aws_iops=${data_values[i]:-0}
            fi
            
            if [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_throughput_mibs ]]; then
                accounts_throughput=${data_values[i]:-0}
            fi
        done
        
        log_debug "ACCOUNTS设备指标: 利用率=${accounts_util}%, 延迟=${accounts_latency}ms, AWS_IOPS=${accounts_aws_iops}, 吞吐量=${accounts_throughput}MiB/s"
        
        if check_ebs_bottleneck "$accounts_util" "$accounts_latency" "$accounts_aws_iops" "$accounts_throughput" "accounts"; then
            bottleneck_detected=true
            if [[ ${BOTTLENECK_COUNTERS["accounts_ebs_util"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
                bottleneck_types+=("ACCOUNTS_EBS_Utilization")
                bottleneck_values+=("${accounts_util}%")
            fi
            if [[ ${BOTTLENECK_COUNTERS["accounts_ebs_latency"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
                bottleneck_types+=("ACCOUNTS_EBS_Latency")
                bottleneck_values+=("${accounts_latency}ms")
            fi
            if [[ ${BOTTLENECK_COUNTERS["accounts_ebs_aws_iops"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
                bottleneck_types+=("ACCOUNTS_EBS_AWS_IOPS")
                bottleneck_values+=("${accounts_aws_iops}/${ACCOUNTS_VOL_MAX_IOPS}")
            fi
            if [[ ${BOTTLENECK_COUNTERS["accounts_ebs_aws_throughput"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
                bottleneck_types+=("ACCOUNTS_EBS_AWS_Throughput")
                bottleneck_values+=("${accounts_throughput}/${ACCOUNTS_VOL_MAX_THROUGHPUT}MiB/s")
            fi
        fi
    fi
    
    if check_network_bottleneck "$network_util"; then
        bottleneck_detected=true
        bottleneck_types+=("Network")
        bottleneck_values+=("${network_util}%")
    fi
    
    # 检测ENA网络限制瓶颈
    if check_ena_network_bottleneck "$performance_csv"; then
        bottleneck_detected=true
        bottleneck_types+=("ENA_Network_Limit")
        bottleneck_values+=("AWS网络限制")
    fi
    
    if check_qps_bottleneck "$current_qps" "$error_rate"; then
        bottleneck_detected=true
        bottleneck_types+=("QPS")
        bottleneck_values+=("${error_rate}% error rate")
    fi
    
    # 更新状态文件
    if [[ "$bottleneck_detected" == "true" ]]; then
        local bottleneck_list=$(IFS=,; echo "${bottleneck_types[*]}")
        local value_list=$(IFS=,; echo "${bottleneck_values[*]}")
        
        echo "🚨 检测到系统瓶颈: $bottleneck_list (QPS: $current_qps)" | tee -a "$BOTTLENECK_LOG"
        echo "   瓶颈值: $value_list" | tee -a "$BOTTLENECK_LOG"
        
        generate_bottleneck_status_json "bottleneck_detected" "true" "$bottleneck_list" "$value_list" "$current_qps" "$metrics_json"
        return 0  # 检测到瓶颈
    else
        # 更新计数器状态 - 保持格式一致性
        generate_bottleneck_status_json "monitoring" "false" "" "" "$current_qps" "$metrics_json"
        return 1  # 未检测到瓶颈
    fi
}

# 检查是否检测到瓶颈
is_bottleneck_detected() {
    if [[ -f "$BOTTLENECK_STATUS_FILE" ]]; then
        local status=$(jq -r '.bottleneck_detected' "$BOTTLENECK_STATUS_FILE" 2>/dev/null)
        [[ "$status" == "true" ]]
    else
        return 1
    fi
}

# 获取瓶颈信息
get_bottleneck_info() {
    if [[ -f "$BOTTLENECK_STATUS_FILE" ]]; then
        cat "$BOTTLENECK_STATUS_FILE" | jq .
    else
        echo '{"status": "not_initialized"}'
    fi
}

# 主函数
main() {
    case "${1:-help}" in
        init)
            init_bottleneck_detection
            ;;
        detect)
            local current_qps="$2"
            local performance_csv="$3"
            detect_bottleneck "$current_qps" "$performance_csv"
            ;;
        status)
            get_bottleneck_info
            ;;
        is-detected)
            if is_bottleneck_detected; then
                echo "true"
                exit 0
            else
                echo "false"
                exit 1
            fi
            ;;
        help|--help|-h)
            echo "Usage: $0 <command> [options]"
            echo ""
            echo "Commands:"
            echo "  init                     初始化瓶颈检测器"
            echo "  detect <qps> <csv>       检测当前QPS下的瓶颈"
            echo "  status                   显示瓶颈检测状态"
            echo "  is-detected              检查是否检测到瓶颈"
            echo "  help                     显示帮助"
            echo ""
            echo "瓶颈检测类型:"
            echo "  CPU使用率 > ${BOTTLENECK_CPU_THRESHOLD}%"
            echo "  内存使用率 > ${BOTTLENECK_MEMORY_THRESHOLD}%"
            echo "  EBS利用率 > ${BOTTLENECK_EBS_UTIL_THRESHOLD}%"
            echo "  EBS延迟 > ${BOTTLENECK_EBS_LATENCY_THRESHOLD}ms"
            echo "  网络利用率 > ${BOTTLENECK_NETWORK_THRESHOLD}%"
            echo "  错误率 > ${BOTTLENECK_ERROR_RATE_THRESHOLD}%"
            ;;
        *)
            echo "❌ 未知命令: $1"
            echo "使用 '$0 help' 查看帮助"
            exit 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
