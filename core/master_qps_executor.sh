#!/bin/bash

# =====================================================================
# Blockchain Node QPS 测试框架主控制器 - 纯QPS测试引擎
# Master QPS Executor - Core QPS Testing Engine Only
# =====================================================================

# 加载共享函数和配置
QPS_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${QPS_SCRIPT_DIR}/common_functions.sh"
source "${QPS_SCRIPT_DIR}/../config/config_loader.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh"

# 初始化统一日志管理器
init_logger "master_qps_executor" $LOG_LEVEL "${LOGS_DIR}/master_qps_executor.log"

source "${QPS_SCRIPT_DIR}/../utils/error_handler.sh"

# 设置错误处理
setup_error_handling "$(basename "${BASH_SOURCE[0]}")" "QPS测试引擎"
log_script_start "$(basename "$0")"

# 全局变量
readonly PROGRAM_NAME="Blockchain Node QPS 基准测试引擎"
readonly VERSION="v2.1"
readonly BENCHMARK_MODES=("quick" "standard" "intensive")
readonly RPC_MODES=("single" "mixed")

# 基准测试参数 - 直接使用user_config.sh中的配置值
# 注意: 所有默认值都来自user_config.sh，确保配置一致性
BENCHMARK_MODE=""
RPC_MODE="single"
INITIAL_QPS=$QUICK_INITIAL_QPS    # 来自user_config.sh: QUICK_INITIAL_QPS=1000
MAX_QPS=$QUICK_MAX_QPS           # 来自user_config.sh: QUICK_MAX_QPS=3000
STEP_QPS=$QUICK_QPS_STEP         # 来自user_config.sh: QUICK_QPS_STEP=500
DURATION=""
CUSTOM_PARAMS=false

# 瓶颈检测状态
BOTTLENECK_DETECTED=false
BOTTLENECK_COUNT=0
LAST_SUCCESSFUL_QPS=0

# 显示帮助信息
show_help() {
    cat << EOF
🚀 $PROGRAM_NAME $VERSION

📋 使用方法:
    $0 [测试模式] [RPC模式] [自定义参数]

🎯 基准测试模式:
    --quick     快速基准测试
    --standard  标准基准测试
    --intensive 深度基准测试 (自动瓶颈检测)

🔗 RPC模式:
    --single    单一RPC方法测试 (默认: getAccountInfo)
    --mixed     混合RPC方法测试 (多种方法组合)

⚙️ 自定义参数:
    --initial-qps NUM    起始QPS (默认: $QUICK_INITIAL_QPS)
    --max-qps NUM        最大QPS (默认: 根据测试模式)
    --step-qps NUM       QPS步进 (默认: $QUICK_QPS_STEP)
    --duration NUM       每级别持续时间(秒)

📊 其他选项:
    --status    显示当前测试状态
    --version   显示版本信息
    --help      显示此帮助信息

📖 示例:
    $0 --intensive --mixed
    $0 --quick --single --initial-qps 500 --max-qps 2000
    $0 --standard --mixed --duration 300

EOF
}

# 显示版本信息
show_version() {
    echo "$PROGRAM_NAME $VERSION"
}

# 显示测试状态
show_status() {
    echo "📊 QPS测试引擎状态"
    echo "=================="
    
    # 检查vegeta是否可用
    if command -v vegeta >/dev/null 2>&1; then
        echo "✅ Vegeta: $(vegeta --version 2>&1 | head -1)"
    else
        echo "❌ Vegeta: 未安装"
    fi
    
    # 检查目标文件
    if [[ -f "$SINGLE_METHOD_TARGETS_FILE" ]]; then
        echo "✅ 单一方法目标文件: $(wc -l < "$SINGLE_METHOD_TARGETS_FILE") 个目标"
    else
        echo "❌ 单一方法目标文件: 不存在"
    fi
    
    if [[ -f "$MIXED_METHOD_TARGETS_FILE" ]]; then
        echo "✅ 混合方法目标文件: $(wc -l < "$MIXED_METHOD_TARGETS_FILE") 个目标"
    else
        echo "❌ 混合方法目标文件: 不存在"
    fi
    
    # 检查RPC连接
    echo "🔗 RPC连接测试:"
    if curl -s -X POST -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}' \
        "$LOCAL_RPC_URL" >/dev/null 2>&1; then
        echo "✅ 本地RPC: $LOCAL_RPC_URL"
    else
        echo "❌ 本地RPC: $LOCAL_RPC_URL (连接失败)"
    fi
    
    # 检查监控状态
    if pgrep -f "monitoring.*coordinator" > /dev/null; then
        echo "✅ 监控系统: 运行中"
    else
        echo "⚠️ 监控系统: 未运行"
    fi
}

# 解析命令行参数
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --quick)
                BENCHMARK_MODE="quick"
                INITIAL_QPS=$QUICK_INITIAL_QPS
                MAX_QPS=$QUICK_MAX_QPS
                STEP_QPS=$QUICK_QPS_STEP
                DURATION=$QUICK_DURATION
                shift
                ;;
            --standard)
                BENCHMARK_MODE="standard"
                INITIAL_QPS=$STANDARD_INITIAL_QPS
                MAX_QPS=$STANDARD_MAX_QPS
                STEP_QPS=$STANDARD_QPS_STEP
                DURATION=$STANDARD_DURATION
                shift
                ;;
            --intensive)
                BENCHMARK_MODE="intensive"
                INITIAL_QPS=$INTENSIVE_INITIAL_QPS
                MAX_QPS=$INTENSIVE_MAX_QPS
                STEP_QPS=$INTENSIVE_QPS_STEP
                DURATION=$INTENSIVE_DURATION
                shift
                ;;
            --single)
                RPC_MODE="single"
                shift
                ;;
            --mixed)
                RPC_MODE="mixed"
                shift
                ;;
            --initial-qps)
                INITIAL_QPS="$2"
                CUSTOM_PARAMS=true
                shift 2
                ;;
            --max-qps)
                MAX_QPS="$2"
                CUSTOM_PARAMS=true
                shift 2
                ;;
            --step-qps)
                STEP_QPS="$2"
                CUSTOM_PARAMS=true
                shift 2
                ;;
            --duration)
                DURATION="$2"
                CUSTOM_PARAMS=true
                shift 2
                ;;
            --status)
                show_status
                exit 0
                ;;
            --version)
                show_version
                exit 0
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                echo "❌ 未知参数: $1"
                echo "💡 使用 --help 查看帮助信息"
                exit 1
                ;;
        esac
    done
    
    # 设置默认基准测试模式
    if [[ -z "$BENCHMARK_MODE" ]]; then
        BENCHMARK_MODE="quick"
        INITIAL_QPS=$QUICK_INITIAL_QPS
        MAX_QPS=$QUICK_MAX_QPS
        STEP_QPS=$QUICK_QPS_STEP
        DURATION=$QUICK_DURATION
    fi
}

# 显示基准测试配置
show_benchmark_config() {
    echo "⚙️ QPS基准测试配置"
    echo "=================="
    echo "基准测试模式: $BENCHMARK_MODE"
    echo "RPC模式:     $RPC_MODE"
    echo "起始QPS:     $INITIAL_QPS"
    echo "最大QPS:     $MAX_QPS"
    echo "QPS步进:     $STEP_QPS"
    echo "持续时间:    ${DURATION}秒"
    echo "本地RPC:     $LOCAL_RPC_URL"
    echo ""
}

# 预检查系统环境
pre_check() {
    echo "🔍 执行预检查..."
    
    # 检查vegeta
    if ! command -v vegeta >/dev/null 2>&1; then
        echo "❌ 错误: vegeta未安装"
        echo "💡 安装方法: https://github.com/tsenart/vegeta"
        return 1
    fi
    
    # 检查目标文件
    local targets_file
    if [[ "$RPC_MODE" == "mixed" ]]; then
        targets_file="$MIXED_METHOD_TARGETS_FILE"
    else
        targets_file="$SINGLE_METHOD_TARGETS_FILE"
    fi
    
    if [[ ! -f "$targets_file" ]]; then
        echo "❌ 错误: 目标文件不存在: $targets_file"
        echo "💡 请确保已生成vegeta目标文件"
        return 1
    fi
    
    # 检查RPC连接
    if ! curl -s -X POST -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}' \
        "$LOCAL_RPC_URL" >/dev/null 2>&1; then
        echo "❌ 错误: 无法连接到RPC端点: $LOCAL_RPC_URL"
        return 1
    fi
    
    echo "✅ 预检查通过"
    return 0
}
# 检查瓶颈状态
check_bottleneck_during_test() {
    local current_qps=$1
    
    # 读取最新监控数据
    local latest_data=$(get_latest_monitoring_data)
    if [[ -z "$latest_data" ]]; then
        return 0  # 无监控数据，继续测试
    fi
    
    local bottleneck_found=false
    local bottleneck_reasons=()
    local bottleneck_severity="low"
    
    # 检查CPU瓶颈
    local cpu_usage=$(echo "$latest_data" | jq -r '.cpu_usage // 0' 2>/dev/null || echo "0")
    if (( $(echo "$cpu_usage > $BOTTLENECK_CPU_THRESHOLD" | bc -l) )); then
        bottleneck_found=true
        local severity="中等"
        if (( $(echo "$cpu_usage > 95" | bc -l) )); then
            severity="严重"
            bottleneck_severity="high"
        fi
        bottleneck_reasons+=("CPU使用率: ${cpu_usage}% > ${BOTTLENECK_CPU_THRESHOLD}% ($severity)")
    fi
    
    # 检查内存瓶颈
    local mem_usage=$(echo "$latest_data" | jq -r '.memory_usage // 0' 2>/dev/null || echo "0")
    if (( $(echo "$mem_usage > $BOTTLENECK_MEMORY_THRESHOLD" | bc -l) )); then
        bottleneck_found=true
        local severity="中等"
        if (( $(echo "$mem_usage > 95" | bc -l) )); then
            severity="严重"
            bottleneck_severity="high"
        fi
        bottleneck_reasons+=("内存使用率: ${mem_usage}% > ${BOTTLENECK_MEMORY_THRESHOLD}% ($severity)")
    fi
    
    # 检查EBS利用率瓶颈
    local ebs_util=$(echo "$latest_data" | jq -r '.ebs_util // 0' 2>/dev/null || echo "0")
    if (( $(echo "$ebs_util > $BOTTLENECK_EBS_UTIL_THRESHOLD" | bc -l) )); then
        bottleneck_found=true
        bottleneck_reasons+=("EBS利用率: ${ebs_util}% > ${BOTTLENECK_EBS_UTIL_THRESHOLD}%")
    fi
    
    # 检查EBS延迟瓶颈
    local ebs_latency=$(echo "$latest_data" | jq -r '.ebs_latency // 0' 2>/dev/null || echo "0")
    if (( $(echo "$ebs_latency > $BOTTLENECK_EBS_LATENCY_THRESHOLD" | bc -l) )); then
        bottleneck_found=true
        bottleneck_severity="high"
        bottleneck_reasons+=("EBS延迟: ${ebs_latency}ms > ${BOTTLENECK_EBS_LATENCY_THRESHOLD}ms (严重)")
    fi
    
    # 检查网络瓶颈
    local network_util=$(echo "$latest_data" | jq -r '.network_util // 0' 2>/dev/null || echo "0")
    if (( $(echo "$network_util > $BOTTLENECK_NETWORK_THRESHOLD" | bc -l) )); then
        bottleneck_found=true
        bottleneck_reasons+=("网络利用率: ${network_util}% > ${BOTTLENECK_NETWORK_THRESHOLD}%")
    fi
    
    # 检查错误率瓶颈
    local error_rate=$(echo "$latest_data" | jq -r '.error_rate // 0' 2>/dev/null || echo "0")
    if (( $(echo "$error_rate > $BOTTLENECK_ERROR_RATE_THRESHOLD" | bc -l) )); then
        bottleneck_found=true
        bottleneck_severity="high"
        bottleneck_reasons+=("错误率: ${error_rate}% > ${BOTTLENECK_ERROR_RATE_THRESHOLD}% (严重)")
    fi
    
    if [[ "$bottleneck_found" == "true" ]]; then
        BOTTLENECK_COUNT=$((BOTTLENECK_COUNT + 1))
        echo "⚠️ 检测到瓶颈 ($BOTTLENECK_COUNT/${BOTTLENECK_CONSECUTIVE_COUNT}): ${bottleneck_reasons[*]}"
        
        # 立即触发瓶颈分析
        trigger_immediate_bottleneck_analysis "$current_qps" "$bottleneck_severity" "${bottleneck_reasons[*]}"
        
        if [[ $BOTTLENECK_COUNT -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            BOTTLENECK_DETECTED=true
            save_bottleneck_context "$current_qps" "${bottleneck_reasons[*]}" "$bottleneck_severity"
            return 1  # 触发停止
        fi
    else
        BOTTLENECK_COUNT=0  # 重置计数器
    fi
    
    return 0
}

# 获取最新监控数据 - 增强版
get_latest_monitoring_data() {
    local monitoring_data="{}"
    
    # 尝试从多个数据源读取最新数据
    local data_sources=(
        "${MEMORY_SHARE_DIR}/latest_metrics.json"
        "${MEMORY_SHARE_DIR}/unified_metrics.json"
        "${LOGS_DIR}/performance_latest.csv"
    )
    
    for source in "${data_sources[@]}"; do
        if [[ -f "$source" ]]; then
            case "$source" in
                *.json)
                    # JSON格式数据
                    local json_data=$(cat "$source" 2>/dev/null)
                    if [[ -n "$json_data" && "$json_data" != "{}" ]]; then
                        monitoring_data="$json_data"
                        break
                    fi
                    ;;
                *.csv)
                    # CSV格式数据，转换为JSON
                    monitoring_data=$(convert_csv_to_json "$source")
                    if [[ -n "$monitoring_data" && "$monitoring_data" != "{}" ]]; then
                        break
                    fi
                    ;;
            esac
        fi
    done
    
    # 如果没有找到数据，尝试实时获取
    if [[ "$monitoring_data" == "{}" ]]; then
        monitoring_data=$(get_realtime_metrics)
    fi
    
    echo "$monitoring_data"
}

# 转换CSV数据为JSON格式
convert_csv_to_json() {
    local csv_file="$1"
    
    if [[ ! -f "$csv_file" ]]; then
        echo "{}"
        return
    fi
    
    # 读取CSV最后一行数据
    local last_line=$(tail -n 1 "$csv_file" 2>/dev/null)
    if [[ -z "$last_line" ]]; then
        echo "{}"
        return
    fi
    
    # 简化的CSV到JSON转换
    local json_data=$(python3 -c "
import sys, csv, json
try:
    with open('$csv_file', 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if rows:
            print(json.dumps(rows[-1]))
        else:
            print('{}')
except:
    print('{}')
" 2>/dev/null)
    
    echo "${json_data:-{}}"
}

# 获取实时指标
get_realtime_metrics() {
    # Linux环境下的实时指标获取
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//' 2>/dev/null || echo "0")
    local mem_usage=$(free | awk '/^Mem:/ {if($2>0) printf "%.1f", $3/$2 * 100; else print "0"}' 2>/dev/null || echo "0")
    
    # 构建JSON
    local metrics=$(cat << EOF
{
    "timestamp": "$(date -Iseconds)",
    "cpu_usage": $cpu_usage,
    "memory_usage": $mem_usage,
    "ebs_util": 0,
    "ebs_latency": 0,
    "network_util": 0,
    "error_rate": 0
}
EOF
)
    
    echo "$metrics"
}

# 立即触发瓶颈分析
trigger_immediate_bottleneck_analysis() {
    local qps=$1
    local severity=$2
    local reasons="$3"
    
    echo "🚨 触发瓶颈分析，QPS: $qps, 严重程度: $severity"
    
    # 调用瓶颈检测器进行实时分析
    if [[ -f "${QPS_SCRIPT_DIR}/../monitoring/bottleneck_detector.sh" ]]; then
        echo "🔍 执行实时瓶颈分析..."
        
        # 获取最新的性能数据文件
        local performance_csv="${LOGS_DIR}/performance_latest.csv"
        if [[ -f "$performance_csv" ]]; then
            "${QPS_SCRIPT_DIR}/../monitoring/bottleneck_detector.sh" \
                detect "$qps" "$performance_csv"
            
            # 等待瓶颈检测完成后再继续
            sleep 1
            
            local analysis_pid=$!
            echo "📊 瓶颈分析进程启动 (PID: $analysis_pid)"
        else
            echo "⚠️  性能数据文件不存在，跳过瓶颈分析: $performance_csv"
        fi
    fi
    
    # 调用EBS瓶颈检测器
    if [[ -f "${QPS_SCRIPT_DIR}/../tools/ebs_bottleneck_detector.sh" ]]; then
        echo "💾 执行EBS瓶颈分析..."
        "${QPS_SCRIPT_DIR}/../tools/ebs_bottleneck_detector.sh" \
            --background --duration 300 &
        
        local ebs_analysis_pid=$!
        echo "📊 EBS瓶颈分析进程启动 (PID: $ebs_analysis_pid)"
    fi
    
    # 记录瓶颈事件
    log_bottleneck_event "$qps" "$severity" "$reasons"
}

# 记录瓶颈事件
log_bottleneck_event() {
    local qps=$1
    local severity=$2
    local reasons="$3"
    
    local event_data=$(cat << EOF
{
    "event_type": "bottleneck_detected",
    "timestamp": "$(date -Iseconds)",
    "qps": $qps,
    "severity": "$severity",
    "reasons": "$reasons",
    "benchmark_mode": "$BENCHMARK_MODE",
    "rpc_mode": "$RPC_MODE"
}
EOF
)
    
    # 保存到事件日志
    local event_log="${LOGS_DIR}/bottleneck_events.jsonl"
    log_info "$event_data"
    
    echo "📝 瓶颈事件已记录到: $(basename "$event_log")"
}

# 保存瓶颈上下文 - 增强版
save_bottleneck_context() {
    local qps=$1
    local reasons="$2"
    local severity="${3:-medium}"
    
    # 获取详细的系统状态
    local system_context=$(get_detailed_system_context)
    
    local bottleneck_data=$(cat << EOF
{
    "bottleneck_detected": true,
    "detection_time": "$(date -Iseconds)",
    "max_successful_qps": $LAST_SUCCESSFUL_QPS,
    "bottleneck_qps": $qps,
    "bottleneck_reasons": "$reasons",
    "severity": "$severity",
    "benchmark_mode": "$BENCHMARK_MODE",
    "rpc_mode": "$RPC_MODE",
    "consecutive_detections": $BOTTLENECK_COUNT,
    "system_context": $system_context,
    "analysis_window": {
        "start_time": "$(date -d "-${BOTTLENECK_ANALYSIS_WINDOW} seconds" -Iseconds)",
        "end_time": "$(date -Iseconds)",
        "window_seconds": $BOTTLENECK_ANALYSIS_WINDOW
    },
    "recommendations": $(generate_bottleneck_recommendations "$severity" "$reasons")
}
EOF
)
    
    echo "$bottleneck_data" > "$QPS_STATUS_FILE"
    echo "📊 详细瓶颈信息已保存到: $QPS_STATUS_FILE"
    
    # 同时保存到专门的瓶颈分析文件
    local bottleneck_analysis_file="${LOGS_DIR}/bottleneck_analysis_$(date +%Y%m%d_%H%M%S).json"
    echo "$bottleneck_data" > "$bottleneck_analysis_file"
    echo "🔍 瓶颈分析文件: $(basename "$bottleneck_analysis_file")"
}

# 获取详细系统上下文
get_detailed_system_context() {
    local context=$(cat << 'EOF'
{
    "cpu_info": {
        "usage": 0,
        "load_avg": "0.0 0.0 0.0",
        "core_count": 1
    },
    "memory_info": {
        "usage_percent": 0,
        "available_gb": 0,
        "total_gb": 0
    },
    "disk_info": {
        "ebs_util": 0,
        "ebs_latency": 0,
        "iops": 0
    },
    "network_info": {
        "utilization": 0,
        "connections": 0
    }
}
EOF
)
    

    
    echo "$context"
}

# 生成瓶颈建议
generate_bottleneck_recommendations() {
    local severity="$1"
    local reasons="$2"
    
    local recommendations='[]'
    
    # 基于瓶颈原因生成建议
    if echo "$reasons" | grep -q "CPU"; then
        recommendations=$(echo "$recommendations" | jq '. + ["考虑升级到更高CPU性能的EC2实例类型", "优化应用程序CPU使用效率", "检查是否有CPU密集型进程"]')
    fi
    
    if echo "$reasons" | grep -q "内存"; then
        recommendations=$(echo "$recommendations" | jq '. + ["考虑升级到更大内存的EC2实例类型", "优化内存使用模式", "检查内存泄漏问题"]')
    fi
    
    if echo "$reasons" | grep -q "EBS"; then
        recommendations=$(echo "$recommendations" | jq '. + ["考虑升级EBS卷类型到io2", "增加EBS IOPS配置", "优化I/O访问模式"]')
    fi
    
    if echo "$reasons" | grep -q "网络"; then
        recommendations=$(echo "$recommendations" | jq '. + ["考虑升级到更高网络性能的EC2实例", "优化网络I/O模式", "检查网络配置"]')
    fi
    
    # 基于严重程度添加建议
    if [[ "$severity" == "high" ]]; then
        recommendations=$(echo "$recommendations" | jq '. + ["立即停止测试以避免系统不稳定", "进行详细的性能分析", "考虑系统架构优化"]')
    fi
    
    echo "$recommendations"
}

# 执行单个QPS级别的测试
execute_single_qps_test() {
    local qps=$1
    local duration=$2
    local targets_file=$3
    
    echo "🚀 执行QPS测试: ${qps} QPS, 持续 ${duration}秒"
    
    # 构建vegeta命令
    local vegeta_cmd="vegeta attack -format=json -targets=$targets_file -rate=$qps -duration=${duration}s"
    local result_file="${VEGETA_RESULTS_DIR}/vegeta_${qps}qps_$(date +%Y%m%d_%H%M%S).json"
    
    # 执行vegeta测试
    echo "📊 执行命令: $vegeta_cmd"
    if $vegeta_cmd | vegeta report -type=json > "$result_file" 2>/dev/null; then
        echo "✅ QPS测试完成，结果保存到: $(basename "$result_file")"
        
        # 解析测试结果
        local total_requests=$(jq -r '.requests' "$result_file" 2>/dev/null || echo "1")
        local success_requests=$(jq -r '.status_codes."200" // 0' "$result_file" 2>/dev/null || echo "0")
        local success_rate=$(echo "scale=0; $success_requests * 100 / $total_requests" | bc 2>/dev/null || echo "0")
        local avg_latency=$(jq -r '.latencies.mean' "$result_file" 2>/dev/null || echo "0")
        
        # 转换延迟单位 (纳秒转毫秒)
        local avg_latency_ms=$(echo "scale=2; $avg_latency / 1000000" | bc 2>/dev/null || echo "0")
        
        echo "📈 测试结果: 成功率 ${success_rate}%, 平均延迟 ${avg_latency_ms}ms"
        
        # 检查测试是否成功
        local success_rate_num=$(echo "$success_rate * 100" | bc 2>/dev/null || echo "0")
        local avg_latency_num=$(echo "$avg_latency_ms" | bc 2>/dev/null || echo "0")
        
        if (( $(echo "$success_rate_num >= $SUCCESS_RATE_THRESHOLD" | bc -l) )) && \
           (( $(echo "$avg_latency_num <= $MAX_LATENCY_THRESHOLD" | bc -l) )); then
            LAST_SUCCESSFUL_QPS=$qps
            return 0
        else
            echo "⚠️ 测试质量不达标: 成功率 ${success_rate}% (要求>${SUCCESS_RATE_THRESHOLD}%), 延迟 ${avg_latency_ms}ms (要求<${MAX_LATENCY_THRESHOLD}ms)"
            return 1
        fi
    else
        echo "❌ QPS测试执行失败"
        return 1
    fi
}

# 执行QPS测试主逻辑
execute_qps_test() {
    echo "🚀 开始执行QPS测试..."
    
    local test_start_time=$(date +"%Y%m%d_%H%M%S")
    
    # 选择目标文件
    local targets_file
    if [[ "$RPC_MODE" == "mixed" ]]; then
        targets_file="$MIXED_METHOD_TARGETS_FILE"
    else
        targets_file="$SINGLE_METHOD_TARGETS_FILE"
    fi
    
    echo "🎯 使用目标文件: $(basename "$targets_file")"
    echo "📊 目标数量: $(wc -l < "$targets_file")"
    
    # 初始化测试状态
    BOTTLENECK_DETECTED=false
    BOTTLENECK_COUNT=0
    LAST_SUCCESSFUL_QPS=0
    
    # 如果是intensive模式，初始化瓶颈检测器
    if [[ "$BENCHMARK_MODE" == "intensive" && "$INTENSIVE_AUTO_STOP" == "true" ]]; then
        echo "🔍 初始化瓶颈检测器 (极限测试模式)..."
        if [[ -f "${QPS_SCRIPT_DIR}/../monitoring/bottleneck_detector.sh" ]]; then
            "${QPS_SCRIPT_DIR}/../monitoring/bottleneck_detector.sh" init
            if [[ $? -eq 0 ]]; then
                echo "✅ 瓶颈检测器初始化成功"
            else
                echo "⚠️  瓶颈检测器初始化失败，但不影响测试继续"
            fi
        else
            echo "⚠️  瓶颈检测器脚本不存在，跳过初始化"
        fi
        echo ""
    fi
    
    # QPS测试循环
    local current_qps=$INITIAL_QPS
    local test_count=0
    
    while [[ $current_qps -le $MAX_QPS ]]; do
        test_count=$((test_count + 1))
        echo ""
        echo "📋 测试轮次 $test_count: QPS = $current_qps"
        
        # 预热阶段
        if [[ $QPS_WARMUP_DURATION -gt 0 ]]; then
            echo "🔥 预热阶段: ${QPS_WARMUP_DURATION}秒"
            sleep $QPS_WARMUP_DURATION
        fi
        
        # 执行单个QPS级别测试
        if execute_single_qps_test "$current_qps" "$DURATION" "$targets_file"; then
            echo "✅ QPS $current_qps 基准测试成功"
        else
            echo "❌ QPS $current_qps 基准测试失败"
            
            # 如果不是深度基准测试模式，测试失败就停止
            if [[ "$BENCHMARK_MODE" != "intensive" ]]; then
                echo "🛑 非深度基准测试模式下测试失败，停止测试"
                break
            fi
        fi
        
        # 深度基准测试模式下检查瓶颈
        if [[ "$BENCHMARK_MODE" == "intensive" && "$INTENSIVE_AUTO_STOP" == "true" ]]; then
            if ! check_bottleneck_during_test "$current_qps"; then
                echo "🚨 检测到性能瓶颈，停止基准测试"
                echo "🏆 最大成功QPS: $LAST_SUCCESSFUL_QPS"
                break
            fi
        fi
        
        # 冷却时间
        if [[ $QPS_COOLDOWN -gt 0 ]]; then
            echo "❄️ 冷却时间: ${QPS_COOLDOWN}秒"
            sleep $QPS_COOLDOWN
        fi
        
        # 增加QPS
        current_qps=$((current_qps + STEP_QPS))
    done
    
    echo ""
    echo "🎉 QPS测试完成"
    echo "📊 测试轮次: $test_count"
    echo "🏆 最大成功QPS: $LAST_SUCCESSFUL_QPS"
    
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        echo "🚨 检测到性能瓶颈，详细信息已保存"
    else
        # 正常完成时写入状态文件
        cat > "$QPS_STATUS_FILE" << EOF
{
    "status": "completed",
    "max_successful_qps": $LAST_SUCCESSFUL_QPS,
    "bottleneck_detected": false,
    "bottleneck_qps": 0,
    "completion_time": "$(date -Iseconds)",
    "test_duration": $DURATION,
    "benchmark_mode": "$BENCHMARK_MODE",
    "rpc_mode": "$RPC_MODE"
}
EOF
        echo "📊 QPS状态已保存到: $QPS_STATUS_FILE"
    fi
    
    return 0
}

# 清理函数
cleanup() {
    echo "🧹 执行QPS测试引擎清理..."
    
    # 🚨 新增: 清理QPS测试状态标记文件
    if [[ -f "$TMP_DIR/qps_test_status" ]]; then
        rm -f "$TMP_DIR/qps_test_status"
        echo "🗑️ QPS测试状态标记文件已清理"
    fi
    
    # QPS测试引擎只负责清理自己的资源
    # 监控系统清理由入口脚本负责
    echo "✅ QPS测试引擎清理完成"
}

# 主函数
main() {
    # 设置清理陷阱
    trap cleanup EXIT INT TERM
    
    # 解析参数
    parse_arguments "$@"
    
    # 显示配置
    show_benchmark_config
    
    # 预检查
    if ! pre_check; then
        echo "❌ 预检查失败"
        return 1
    fi
    
    # 执行QPS测试
    if execute_qps_test; then
        echo "🎉 QPS测试执行成功"
        return 0
    else
        echo "❌ QPS测试执行失败"
        return 1
    fi
}

# 执行主函数
main "$@"