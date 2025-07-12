#!/bin/bash

# =====================================================================
# Solana 验证节点日志分析脚本
# 用于分析 Solana 验证节点日志，识别性能问题和异常
# =====================================================================

# 加载配置文件
source "$(dirname "${BASH_SOURCE[0]}")/../config/config.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh"

# 初始化统一日志管理器
init_logger "analyze_validator_logs" $LOG_LEVEL "${LOGS_DIR}/analyze_validator_logs.log"


# 初始化变量
INPUT_LOG=""
OUTPUT_FILE=""
TIMEFRAME=24  # 默认分析最近 24 小时的日志
VERBOSE=false

# 帮助信息
show_help() {
    echo "Solana Validator Log Analyzer"
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help                 Show this help message"
    echo "  -i, --input FILE           Input log file (default: ${VALIDATOR_LOG_PATH})"
    echo "  -o, --output FILE          Output analysis file (default: ${LOG_ANALYSIS_OUTPUT})"
    echo "  -t, --timeframe HOURS      Analyze logs from the last N hours (default: ${TIMEFRAME})"
    echo "  -v, --verbose              Enable verbose output"
    echo ""
    echo "Example:"
    echo "  $0 -i \${VALIDATOR_LOG_PATH:-/var/log/solana/validator.log} -o \${REPORTS_DIR}/validator_analysis.txt -t 12"
    echo ""
}

# 参数解析
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0  # --help 应该直接退出整个脚本
                ;;
            -i|--input)
                INPUT_LOG="$2"
                shift 2
                ;;
            -o|--output)
                OUTPUT_FILE="$2"
                shift 2
                ;;
            -t|--timeframe)
                TIMEFRAME="$2"
                shift 2
                ;;
            --bottleneck-time)
                BOTTLENECK_TIME="$2"
                shift 2
                ;;
            --window-seconds)
                WINDOW_SECONDS="$2"
                shift 2
                ;;
            --bottleneck-types)
                BOTTLENECK_TYPES="$2"
                shift 2
                ;;
            --focus-errors)
                FOCUS_ERRORS=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                return 1
                ;;
        esac
    done
    
    # 设置默认值
    INPUT_LOG=${INPUT_LOG:-"$VALIDATOR_LOG_PATH"}
    OUTPUT_FILE=${OUTPUT_FILE:-"$LOG_ANALYSIS_OUTPUT"}
    WINDOW_SECONDS=${WINDOW_SECONDS:-30}
    FOCUS_ERRORS=${FOCUS_ERRORS:-false}
}

# 检查依赖
check_dependencies() {
    if ! command -v grep &> /dev/null || ! command -v awk &> /dev/null || ! command -v sort &> /dev/null; then
        echo "Error: Required tools (grep, awk, sort) are not installed"
        return 1
    fi
}

# 检查输入文件
check_input_file() {
    if [[ ! -f "$INPUT_LOG" ]]; then
        echo "Error: Input log file not found: $INPUT_LOG"
        return 1
    fi
    
    # 检查文件是否为空
    if [[ ! -s "$INPUT_LOG" ]]; then
        echo "Error: Input log file is empty: $INPUT_LOG"
        return 1
    fi
}

# 获取日志时间范围
get_log_timeframe() {
    local current_time=$(date +%s)
    local timeframe_seconds=$((TIMEFRAME * 3600))
    local start_time=$((current_time - timeframe_seconds))
    
    # 转换为日期格式，用于过滤日志
    local start_date=$(date -d "@$start_time" "+%Y-%m-%d %H:%M:%S")
    
    echo "$start_date"
}

# 解析Solana时间戳格式
parse_solana_timestamp() {
    local log_line="$1"
    # 提取时间戳：[2025-06-16T18:36:55.458394519Z INFO ...]
    echo "$log_line" | grep -o '\[20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9]*Z' | sed 's/\[//g'
}

# 过滤瓶颈时间窗口内的日志
filter_logs_by_bottleneck_time() {
    local bottleneck_time="$1"
    local window_seconds="$2"
    local input_file="$3"
    local output_file="$4"
    
    if [[ -z "$bottleneck_time" ]]; then
        echo "Error: Bottleneck time not specified"
        return 1
    fi
    
    # 计算时间窗口
    local bottleneck_epoch=$(date -d "$bottleneck_time" +%s 2>/dev/null)
    if [[ $? -ne 0 ]]; then
        echo "Error: Invalid bottleneck time format: $bottleneck_time"
        return 1
    fi
    
    local start_epoch=$((bottleneck_epoch - window_seconds))
    local end_epoch=$((bottleneck_epoch + window_seconds))
    
    local start_iso=$(date -d "@$start_epoch" -Iseconds | sed 's/+00:00/Z/')
    local end_iso=$(date -d "@$end_epoch" -Iseconds | sed 's/+00:00/Z/')
    
    if [[ "$VERBOSE" == "true" ]]; then
        echo "Filtering logs around bottleneck time: $bottleneck_time"
        echo "Time window: $start_iso to $end_iso (±${window_seconds}s)"
    fi
    
    # 使用awk过滤时间范围内的日志
    awk -v start_time="$start_iso" -v end_time="$end_iso" '
    {
        # 提取时间戳 [2025-06-23T02:50:26.696435462Z ...]
        if (match($0, /\[20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9]*Z/)) {
            timestamp = substr($0, RSTART+1, RLENGTH-1)
            # 简化时间戳比较 (去掉纳秒部分)
            simple_timestamp = substr(timestamp, 1, 19) "Z"
            if (simple_timestamp >= start_time && simple_timestamp <= end_time) {
                print $0
            }
        }
    }' "$input_file" > "$output_file"
    
    local filtered_count=$(wc -l < "$output_file")
    if [[ "$VERBOSE" == "true" ]]; then
        echo "Filtered $filtered_count log entries in time window"
    fi
    
    return 0
}

# 过滤指定时间范围内的日志
filter_logs_by_time() {
    local start_time=$1
    local input_file="$2"
    local output_file="$3"
    
    # 计算开始时间的ISO格式
    local start_iso=$(date -d "@$start_time" -Iseconds | sed 's/+00:00/Z/')
    local start_date_only=$(echo "$start_iso" | cut -d'T' -f1)
    
    if [[ "$VERBOSE" == "true" ]]; then
        echo "Filtering logs since: $start_iso"
        echo "Date filter: $start_date_only"
    fi
    
    # 使用awk来过滤时间范围内的日志
    awk -v start_date="$start_date_only" '
    {
        # 提取时间戳
        if (match($0, /\[20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9]*Z/)) {
            timestamp = substr($0, RSTART+1, RLENGTH-1)
            log_date = substr(timestamp, 1, 10)
            if (log_date >= start_date) {
                print $0
            }
        }
    }' "$input_file" > "$output_file"
}

# 分析Solana数据点指标
analyze_datapoints() {
    local filtered_log="$1"
    local tmp_file="${TMP_DIR}/validator_datapoints_$(date +%Y%m%d_%H%M%S).txt"
    
    echo "Analyzing Solana datapoint metrics..."
    
    # 提取所有datapoint行
    grep "datapoint:" "$filtered_log" > "$tmp_file"
    
    # 分析cost_tracker_stats
    local cost_tracker_count=$(grep "cost_tracker_stats" "$tmp_file" | wc -l)
    if [[ $cost_tracker_count -gt 0 ]]; then
        echo ""
        echo "Cost Tracker Analysis ($cost_tracker_count entries):"
        
        # 提取关键指标的平均值
        local avg_block_cost=$(grep "cost_tracker_stats" "$tmp_file" | grep -o "block_cost=[0-9]*i" | cut -d'=' -f2 | sed 's/i$//' | awk '{sum+=$1; count++} END {if(count>0) print int(sum/count); else print 0}')
        local avg_tx_count=$(grep "cost_tracker_stats" "$tmp_file" | grep -o " transaction_count=[0-9]*i" | cut -d'=' -f2 | sed 's/i$//' | awk '{sum+=$1; count++} END {if(count>0) print int(sum/count); else print 0}')
        local avg_account_count=$(grep "cost_tracker_stats" "$tmp_file" | grep -o "number_of_accounts=[0-9]*i" | cut -d'=' -f2 | sed 's/i$//' | awk '{sum+=$1; count++} END {if(count>0) print int(sum/count); else print 0}')
        
        echo "- Average block cost: $avg_block_cost"
        echo "- Average transaction count: $avg_tx_count"
        echo "- Average account count: $avg_account_count"
        
        # 找出最昂贵的账户
        echo "- Most expensive accounts:"
        grep "cost_tracker_stats" "$tmp_file" | grep -o 'costliest_account="[^"]*"' | sort | uniq -c | sort -nr | head -5
    fi
    
    # 分析compute_bank_stats
    local compute_bank_count=$(grep "compute_bank_stats" "$tmp_file" | wc -l)
    if [[ $compute_bank_count -gt 0 ]]; then
        echo ""
        echo "Compute Bank Analysis ($compute_bank_count entries):"
        
        # 提取计算时间统计
        local avg_elapsed=$(grep "compute_bank_stats" "$tmp_file" | grep -o "elapsed=[0-9]*i" | cut -d'=' -f2 | sed 's/i$//' | awk '{sum+=$1; count++} END {if(count>0) print int(sum/count); else print 0}')
        echo "- Average compute time: ${avg_elapsed}ms"
        
        # 分析slot处理
        echo "- Recent slot processing:"
        grep "compute_bank_stats" "$tmp_file" | tail -5 | while read line; do
            local slot=$(echo "$line" | grep -o "computed_slot=[0-9]*i" | cut -d'=' -f2 | sed 's/i$//')
            local elapsed=$(echo "$line" | grep -o "elapsed=[0-9]*i" | cut -d'=' -f2 | sed 's/i$//')
            echo "  Slot $slot: ${elapsed}ms"
        done
    fi
    
    # 清理临时文件
    if [[ "$VERBOSE" != "true" ]]; then
        rm -f "$tmp_file"
    else
        echo "Temporary datapoints file saved to: $tmp_file"
    fi
}

# 分析瓶颈时间窗口内的关键事件
analyze_bottleneck_events() {
    local filtered_log="$1"
    local bottleneck_types="$2"
    
    echo ""
    echo "========================================="
    echo "瓶颈时间窗口关键事件分析"
    echo "========================================="
    echo "瓶颈类型: $bottleneck_types"
    echo ""
    
    # 1. 分析ERROR和error事件
    echo "🚨 错误事件分析:"
    local error_count=$(grep -i "error" "$filtered_log" | wc -l)
    echo "- 错误事件总数: $error_count"
    
    if [[ $error_count -gt 0 ]]; then
        echo "- 错误事件详情:"
        grep -i "error" "$filtered_log" | head -10 | while read line; do
            local timestamp=$(echo "$line" | grep -o '\[20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9]*Z' | sed 's/\[//g')
            local error_msg=$(echo "$line" | sed 's/.*ERROR[[:space:]]*//' | cut -c1-100)
            echo "  [$timestamp] $error_msg"
        done
    fi
    
    # 2. 分析solana_core事件
    echo ""
    echo "🔧 Solana Core事件分析:"
    local core_count=$(grep "solana_core" "$filtered_log" | wc -l)
    echo "- Core事件总数: $core_count"
    
    if [[ $core_count -gt 0 ]]; then
        echo "- 关键Core事件:"
        grep "solana_core" "$filtered_log" | grep -E "(replay_stage|banking_stage|poh_recorder)" | head -5 | while read line; do
            local timestamp=$(echo "$line" | grep -o '\[20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9]*Z' | sed 's/\[//g')
            local component=$(echo "$line" | grep -o "solana_core::[^]]*" | head -1)
            echo "  [$timestamp] $component"
        done
    fi
    
    # 3. 分析solana_metrics事件
    echo ""
    echo "📊 Solana Metrics事件分析:"
    local metrics_count=$(grep "solana_metrics" "$filtered_log" | wc -l)
    echo "- Metrics事件总数: $metrics_count"
    
    if [[ $metrics_count -gt 0 ]]; then
        echo "- 性能指标事件:"
        grep "solana_metrics" "$filtered_log" | head -5 | while read line; do
            local timestamp=$(echo "$line" | grep -o '\[20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9]*Z' | sed 's/\[//g')
            local metric_info=$(echo "$line" | sed 's/.*solana_metrics[[:space:]]*//' | cut -c1-80)
            echo "  [$timestamp] $metric_info"
        done
    fi
    
    # 4. 根据瓶颈类型进行专门分析
    echo ""
    echo "🎯 瓶颈类型专门分析:"
    case "$bottleneck_types" in
        *CPU*)
            echo "- CPU瓶颈相关事件:"
            grep -E "(compute_bank|cost_tracker|banking_stage)" "$filtered_log" | head -3 | while read line; do
                local timestamp=$(echo "$line" | grep -o '\[20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9]*Z' | sed 's/\[//g')
                echo "  [$timestamp] CPU相关: $(echo "$line" | cut -c1-100)"
            done
            ;;
        *EBS*)
            echo "- 存储瓶颈相关事件:"
            grep -E "(accounts_db|ledger|snapshot)" "$filtered_log" | head -3 | while read line; do
                local timestamp=$(echo "$line" | grep -o '\[20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9]*Z' | sed 's/\[//g')
                echo "  [$timestamp] 存储相关: $(echo "$line" | cut -c1-100)"
            done
            ;;
        *ENA*)
            echo "- 网络瓶颈相关事件:"
            grep -E "(streamer|gossip|repair)" "$filtered_log" | head -3 | while read line; do
                local timestamp=$(echo "$line" | grep -o '\[20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9]*Z' | sed 's/\[//g')
                echo "  [$timestamp] 网络相关: $(echo "$line" | cut -c1-100)"
            done
            ;;
        *)
            echo "- 通用关键事件:"
            grep -E "(WARN|WARNING)" "$filtered_log" | head -3 | while read line; do
                local timestamp=$(echo "$line" | grep -o '\[20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]\.[0-9]*Z' | sed 's/\[//g')
                echo "  [$timestamp] 警告: $(echo "$line" | cut -c1-100)"
            done
            ;;
    esac
    
    echo ""
    echo "========================================="
}

# 分析错误和警告
analyze_errors_warnings() {
    local start_date=$1
    local tmp_file="${TMP_DIR}/validator_errors_$(date +%Y%m%d_%H%M%S).txt"
    
    echo "Analyzing errors and warnings since $start_date..."
    
    # 检查输入日志文件大小，如果太大则限制处理
    local log_size=$(stat -f%z "$INPUT_LOG" 2>/dev/null || stat -c%s "$INPUT_LOG" 2>/dev/null || echo "0")
    local max_size=$((1024 * 1024 * 1024))  # 1GB limit
    
    if [ "$log_size" -gt "$max_size" ]; then
        echo "Warning: Log file is very large ($(($log_size / 1024 / 1024))MB). Processing last 100MB only..."
        # 只处理最后100MB的日志
        tail -c 100M "$INPUT_LOG" | grep -i -E "error|warn|exception|fail|timeout|panic" > "$tmp_file"
    else
        # 提取错误和警告
        grep -i -E "error|warn|exception|fail|timeout|panic" "$INPUT_LOG" > "$tmp_file"
    fi
    
    # 检查临时文件大小，如果太大则截断
    local tmp_size=$(stat -f%z "$tmp_file" 2>/dev/null || stat -c%s "$tmp_file" 2>/dev/null || echo "0")
    local max_tmp_size=$((100 * 1024 * 1024))  # 100MB limit for temp file
    
    if [ "$tmp_size" -gt "$max_tmp_size" ]; then
        echo "Warning: Error extraction is very large ($(($tmp_size / 1024 / 1024))MB). Truncating to 100MB..."
        head -c 100M "$tmp_file" > "${tmp_file}.truncated"
        mv "${tmp_file}.truncated" "$tmp_file"
    fi
    
    # 统计错误类型
    local error_count=$(grep -i "error" "$tmp_file" | wc -l)
    local warning_count=$(grep -i "warn" "$tmp_file" | wc -l)
    local exception_count=$(grep -i "exception" "$tmp_file" | wc -l)
    local failure_count=$(grep -i "fail" "$tmp_file" | wc -l)
    local timeout_count=$(grep -i "timeout" "$tmp_file" | wc -l)
    local panic_count=$(grep -i "panic" "$tmp_file" | wc -l)
    
    echo "Error and Warning Analysis:"
    echo "- Total errors: $error_count"
    echo "- Total warnings: $warning_count"
    echo "- Total exceptions: $exception_count"
    echo "- Total failures: $failure_count"
    echo "- Total timeouts: $timeout_count"
    echo "- Total panics: $panic_count"
    
    # 分析最常见的错误模式
    echo ""
    echo "Top 10 most common error patterns:"
    grep -i "error" "$tmp_file" | awk -F': ' '{print $NF}' | sort | uniq -c | sort -nr | head -10
    
    echo ""
    echo "Top 10 most common warning patterns:"
    grep -i "warn" "$tmp_file" | awk -F': ' '{print $NF}' | sort | uniq -c | sort -nr | head -10
    
    # 清理临时文件
    if [[ "$VERBOSE" != "true" ]]; then
        rm -f "$tmp_file"
    else
        echo "Temporary error file saved to: $tmp_file"
    fi
}

# 分析性能指标
analyze_performance_metrics() {
    local start_date=$1
    local tmp_file="${TMP_DIR}/validator_perf_$(date +%Y%m%d_%H%M%S).txt"
    
    echo "Analyzing performance metrics since $start_date..."
    
    # 提取性能相关日志
    grep -i -E "performance|throughput|latency|qps|tps|block|slot|transaction" "$INPUT_LOG" > "$tmp_file"
    
    # 分析 Slot 处理
    local slot_processed=$(grep -i "slot" "$tmp_file" | grep -i "processed" | wc -l)
    local slot_skipped=$(grep -i "slot" "$tmp_file" | grep -i "skipped" | wc -l)
    local slot_confirmed=$(grep -i "slot" "$tmp_file" | grep -i "confirmed" | wc -l)
    
    echo "Slot Processing Analysis:"
    echo "- Slots processed: $slot_processed"
    echo "- Slots skipped: $slot_skipped"
    echo "- Slots confirmed: $slot_confirmed"
    
    # 分析交易处理
    local tx_processed=$(grep -i "transaction" "$tmp_file" | grep -i "processed" | wc -l)
    local tx_failed=$(grep -i "transaction" "$tmp_file" | grep -i "failed" | wc -l)
    
    echo ""
    echo "Transaction Processing Analysis:"
    echo "- Transactions processed: $tx_processed"
    echo "- Transactions failed: $tx_failed"
    
    # 分析性能指标
    echo ""
    echo "Performance Metrics:"
    grep -i "performance" "$tmp_file" | tail -10
    
    # 清理临时文件
    if [[ "$VERBOSE" != "true" ]]; then
        rm -f "$tmp_file"
    else
        echo "Temporary performance file saved to: $tmp_file"
    fi
}

# 分析网络连接
analyze_network_connections() {
    local start_date=$1
    local tmp_file="${TMP_DIR}/validator_network_$(date +%Y%m%d_%H%M%S).txt"
    
    echo "Analyzing network connections since $start_date..."
    
    # 提取网络相关日志
    grep -i -E "connection|peer|gossip|network|socket|bind|rpc" "$INPUT_LOG" > "$tmp_file"
    
    # 分析连接统计
    local connection_established=$(grep -i "connection" "$tmp_file" | grep -i "established" | wc -l)
    local connection_closed=$(grep -i "connection" "$tmp_file" | grep -i "closed" | wc -l)
    local connection_failed=$(grep -i "connection" "$tmp_file" | grep -i "failed" | wc -l)
    
    echo "Network Connection Analysis:"
    echo "- Connections established: $connection_established"
    echo "- Connections closed: $connection_closed"
    echo "- Connection failures: $connection_failed"
    
    # 分析 RPC 请求
    local rpc_requests=$(grep -i "rpc" "$tmp_file" | grep -i "request" | wc -l)
    local rpc_errors=$(grep -i "rpc" "$tmp_file" | grep -i "error" | wc -l)
    
    echo ""
    echo "RPC Request Analysis:"
    echo "- Total RPC requests: $rpc_requests"
    echo "- RPC errors: $rpc_errors"
    
    # 分析 Gossip 网络
    echo ""
    echo "Gossip Network Analysis:"
    grep -i "gossip" "$tmp_file" | grep -i -E "error|warn|fail" | tail -10
    
    # 清理临时文件
    if [[ "$VERBOSE" != "true" ]]; then
        rm -f "$tmp_file"
    else
        echo "Temporary network file saved to: $tmp_file"
    fi
}

# 分析资源使用
analyze_resource_usage() {
    local start_date=$1
    local tmp_file="${TMP_DIR}/validator_resource_$(date +%Y%m%d_%H%M%S).txt"
    
    echo "Analyzing resource usage since $start_date..."
    
    # 提取资源相关日志
    grep -i -E "cpu|memory|disk|io|bandwidth|resource|usage|limit" "$INPUT_LOG" > "$tmp_file"
    
    # 分析 CPU 使用
    echo "CPU Usage Analysis:"
    grep -i "cpu" "$tmp_file" | grep -i "usage" | tail -5
    
    # 分析内存使用
    echo ""
    echo "Memory Usage Analysis:"
    grep -i "memory" "$tmp_file" | grep -i "usage" | tail -5
    
    # 分析磁盘使用
    echo ""
    echo "Disk Usage Analysis:"
    grep -i -E "disk|io" "$tmp_file" | grep -i "usage" | tail -5
    
    # 分析资源限制
    echo ""
    echo "Resource Limit Analysis:"
    grep -i "limit" "$tmp_file" | grep -i -E "reached|exceeded" | tail -5
    
    # 清理临时文件
    if [[ "$VERBOSE" != "true" ]]; then
        rm -f "$tmp_file"
    else
        echo "Temporary resource file saved to: $tmp_file"
    fi
}

# 分析验证节点日志
analyze_validator_log() {
    echo "Analyzing Solana validator log: $INPUT_LOG"
    echo "Timeframe: Last $TIMEFRAME hours"
    echo "Output file: $OUTPUT_FILE"
    
    # 创建输出目录
    mkdir -p "$(dirname "$OUTPUT_FILE")"
    
    # 获取日志时间范围
    local start_date=$(get_log_timeframe)
    
    # 生成分析报告
    {
        echo "========================================"
        echo "Solana Validator Log Analysis Report"
        echo "========================================"
        echo "Generated: $(date)"
        echo "Input Log: $INPUT_LOG"
        echo "Timeframe: Last $TIMEFRAME hours (since $start_date)"
        echo "========================================"
        echo ""
        
        echo "========================================"
        echo "Error and Warning Analysis"
        echo "========================================"
        analyze_errors_warnings "$start_date"
        echo ""
        
        echo "========================================"
        echo "Performance Metrics Analysis"
        echo "========================================"
        analyze_performance_metrics "$start_date"
        echo ""
        
        echo "========================================"
        echo "Network Connection Analysis"
        echo "========================================"
        analyze_network_connections "$start_date"
        echo ""
        
        echo "========================================"
        echo "Resource Usage Analysis"
        echo "========================================"
        analyze_resource_usage "$start_date"
        echo ""
        
        echo "========================================"
        echo "Recommendations"
        echo "========================================"
        echo "Based on the log analysis:"
        echo "1. Monitor error patterns and address recurring issues"
        echo "2. Check for resource constraints if performance degradation is observed"
        echo "3. Verify network connectivity if connection failures are frequent"
        echo "4. Consider optimizing RPC configuration if RPC errors are high"
        echo ""
        
        echo "========================================"
        echo "End of Report"
        echo "========================================"
    } > "$OUTPUT_FILE"
    
    echo "Validator log analysis completed: $OUTPUT_FILE"
    
    # 如果启用了详细输出，显示报告内容
    if [[ "$VERBOSE" == "true" ]]; then
        echo ""
        echo "Report content:"
        echo "----------------------------------------"
        cat "$OUTPUT_FILE"
        echo "----------------------------------------"
    fi
}

# 主函数
main() {
    # 解析参数
    parse_args "$@"
    
    # 检查依赖
    if ! check_dependencies; then
        exit 1
    fi
    
    # 检查输入文件
    if ! check_input_file; then
        exit 1
    fi
    
    # 判断是否为瓶颈时间关联分析
    if [[ -n "$BOTTLENECK_TIME" ]]; then
        echo "🔍 执行瓶颈时间关联分析模式"
        analyze_bottleneck_correlation
    else
        echo "📊 执行标准验证器日志分析模式"
        # 分析验证节点日志
        analyze_validator_log
    fi
}

# 瓶颈时间关联分析主函数
analyze_bottleneck_correlation() {
    echo "========================================="
    echo "Solana Validator Log - 瓶颈关联分析"
    echo "========================================="
    echo "生成时间: $(date)"
    echo "输入日志: $INPUT_LOG"
    echo "瓶颈时间: $BOTTLENECK_TIME"
    echo "分析窗口: ±${WINDOW_SECONDS}秒"
    echo "瓶颈类型: ${BOTTLENECK_TYPES:-未指定}"
    echo "========================================="
    
    # 创建输出目录
    mkdir -p "$(dirname "$OUTPUT_FILE")"
    
    # 创建临时过滤文件
    local filtered_log="${TMP_DIR}/bottleneck_filtered_$(date +%Y%m%d_%H%M%S).log"
    
    # 过滤瓶颈时间窗口内的日志
    if filter_logs_by_bottleneck_time "$BOTTLENECK_TIME" "$WINDOW_SECONDS" "$INPUT_LOG" "$filtered_log"; then
        echo "✅ 日志时间窗口过滤完成"
        
        # 生成分析报告
        {
            echo "========================================="
            echo "Solana Validator Log - 瓶颈关联分析报告"
            echo "========================================="
            echo "生成时间: $(date)"
            echo "输入日志: $INPUT_LOG"
            echo "瓶颈时间: $BOTTLENECK_TIME"
            echo "分析窗口: ±${WINDOW_SECONDS}秒"
            echo "瓶颈类型: ${BOTTLENECK_TYPES:-未指定}"
            echo "过滤日志行数: $(wc -l < "$filtered_log")"
            echo ""
            
            # 执行瓶颈事件分析
            analyze_bottleneck_events "$filtered_log" "$BOTTLENECK_TYPES"
            
            # 如果启用了错误聚焦，进行详细错误分析
            if [[ "$FOCUS_ERRORS" == "true" ]]; then
                echo ""
                echo "========================================="
                echo "详细错误分析 (错误聚焦模式)"
                echo "========================================="
                analyze_errors_warnings_filtered "$filtered_log"
            fi
            
            # 分析slot处理情况
            echo ""
            echo "========================================="
            echo "Slot处理分析"
            echo "========================================="
            analyze_slot_processing "$filtered_log"
            
            # 分析网络连接情况
            echo ""
            echo "========================================="
            echo "网络连接分析"
            echo "========================================="
            analyze_network_connections_filtered "$filtered_log"
            
            echo ""
            echo "========================================="
            echo "分析完成时间: $(date)"
            echo "========================================="
            
        } > "$OUTPUT_FILE"
        
        echo "✅ 瓶颈关联分析完成"
        echo "📄 分析报告: $OUTPUT_FILE"
        
        # 清理临时文件
        if [[ "$VERBOSE" != "true" ]]; then
            rm -f "$filtered_log"
        else
            echo "🔧 临时过滤文件保留: $filtered_log"
        fi
        
    else
        echo "❌ 日志时间窗口过滤失败"
        return 1
    fi
}

# 分析过滤后日志的错误和警告
analyze_errors_warnings_filtered() {
    local filtered_log="$1"
    local tmp_file="${TMP_DIR}/validator_errors_filtered_$(date +%Y%m%d_%H%M%S).txt"
    
    # 提取错误和警告
    grep -i -E "ERROR|WARN|exception|fail|timeout|panic" "$filtered_log" > "$tmp_file"
    
    # 统计错误类型
    local error_count=$(grep -i "ERROR" "$tmp_file" | wc -l)
    local warning_count=$(grep -i "WARN" "$tmp_file" | wc -l)
    local exception_count=$(grep -i "exception" "$tmp_file" | wc -l)
    local failure_count=$(grep -i "fail" "$tmp_file" | wc -l)
    local timeout_count=$(grep -i "timeout" "$tmp_file" | wc -l)
    local panic_count=$(grep -i "panic" "$tmp_file" | wc -l)
    
    echo "Error and Warning Summary:"
    echo "- Total errors: $error_count"
    echo "- Total warnings: $warning_count"
    echo "- Total exceptions: $exception_count"
    echo "- Total failures: $failure_count"
    echo "- Total timeouts: $timeout_count"
    echo "- Total panics: $panic_count"
    
    if [[ $error_count -gt 0 ]]; then
        echo ""
        echo "Recent errors (last 5):"
        grep -i "ERROR" "$tmp_file" | tail -5
    fi
    
    if [[ $warning_count -gt 0 ]]; then
        echo ""
        echo "Recent warnings (last 5):"
        grep -i "WARN" "$tmp_file" | tail -5
    fi
    
    # 清理临时文件
    if [[ "$VERBOSE" != "true" ]]; then
        rm -f "$tmp_file"
    fi
}

# 分析过滤后日志的性能指标
analyze_performance_metrics_filtered() {
    local filtered_log="$1"
    
    # 分析slot处理性能
    local slot_lines=$(grep -i "slot" "$filtered_log" | wc -l)
    echo "Slot-related log entries: $slot_lines"
    
    # 分析交易处理
    local tx_lines=$(grep -i "transaction" "$filtered_log" | wc -l)
    echo "Transaction-related log entries: $tx_lines"
    
    # 分析RPC性能
    local rpc_lines=$(grep -i "rpc" "$filtered_log" | wc -l)
    echo "RPC-related log entries: $rpc_lines"
    
    # 显示最近的性能相关日志
    echo ""
    echo "Recent performance-related entries:"
    grep -i -E "performance|latency|throughput" "$filtered_log" | tail -3
}

# 分析slot处理
analyze_slot_processing() {
    local filtered_log="$1"
    
    # 分析fork choice和voting
    local voting_lines=$(grep "voting:" "$filtered_log" | wc -l)
    local fork_lines=$(grep "fork" "$filtered_log" | wc -l)
    
    echo "Slot Processing Summary:"
    echo "- Voting entries: $voting_lines"
    echo "- Fork-related entries: $fork_lines"
    
    # 显示最近的slot处理信息
    echo ""
    echo "Recent slot processing (last 5):"
    grep -E "voting:|fork|slot_weight" "$filtered_log" | tail -5
    
    # 分析slot确认时间
    echo ""
    echo "Recent slot confirmations:"
    grep "confirmed" "$filtered_log" | grep -o "[0-9]*ms" | tail -5 | while read time; do
        echo "- Confirmation time: $time"
    done
}

# 分析过滤后日志的网络连接
analyze_network_connections_filtered() {
    local filtered_log="$1"
    
    # 分析网络相关日志
    local network_lines=$(grep -i -E "connection|peer|gossip|network" "$filtered_log" | wc -l)
    echo "Network-related log entries: $network_lines"
    
    # 分析RPC连接
    local rpc_lines=$(grep -i "rpc" "$filtered_log" | wc -l)
    echo "RPC-related log entries: $rpc_lines"
    
    if [[ $network_lines -gt 0 ]]; then
        echo ""
        echo "Recent network activity (last 3):"
        grep -i -E "connection|peer|gossip" "$filtered_log" | tail -3
    fi
}

# 执行主函数
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
