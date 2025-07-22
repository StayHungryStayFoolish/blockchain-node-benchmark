#!/bin/bash

# =====================================================================
# Solana Slot 监控模块
# 用于监控本地 Solana 节点与主网之间的 Slot 差异
# =====================================================================

# 加载配置文件
# 安全加载配置文件，避免readonly变量冲突
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config.sh" 2>/dev/null; then
    echo "警告: 配置文件加载失败，使用默认配置"
    MONITOR_INTERVAL=${MONITOR_INTERVAL:-10}
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi

# 初始化变量
MONITOR_PID=""
SLOT_DIFF_ALERT=false
SLOT_DIFF_START_TIME=""
SLOT_DIFF_END_TIME=""
SLOT_DIFF_EVENT_ID=""
SLOT_DIFF_EVENTS=()
DATA_LOSS_ALERT=false
DATA_LOSS_START_TIME=""
DATA_LOSS_END_TIME=""
DATA_LOSS_EVENTS=()

# 清理和退出函数
cleanup_and_exit() {
    echo "Received termination signal, cleaning up slot monitor..."
    
    # 刷新所有缓冲
    if [[ -n "$SLOT_DATA_FILE" && -f "$SLOT_DATA_FILE" ]]; then
        sync "$SLOT_DATA_FILE" 2>/dev/null || true
        rm -f "${SLOT_DATA_FILE}.buffer" 2>/dev/null || true
    fi
    
    # 删除PID文件
    rm -f "${TMP_DIR}/slot_monitor.pid" 2>/dev/null || true
    
    # 清理共享内存缓存
    rm -rf /dev/shm/solana-qps-test/ 2>/dev/null || true
    
    echo "Slot monitor cleanup completed"
    exit 0
}

# 注意：信号处理将在后台监控模式下设置，而不是全局设置
DATA_LOSS_COUNT=0
DATA_LOSS_PERIODS=0
DATA_LOSS_TOTAL_DURATION=0
BACKGROUND=false
VERBOSE=false

# 帮助信息
show_help() {
    echo "Solana Slot Monitor"
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help                 Show this help message"
    echo "  -i, --interval SECONDS     Set monitoring interval (default: ${SLOT_MONITOR_INTERVAL}s)"
    echo "  -d, --duration SECONDS     Set monitoring duration (for standalone use)"
    echo "  --diff SLOTS               Set slot difference threshold (default: ${SLOT_DIFF_THRESHOLD})"
    echo "  -t, --time SECONDS         Set time difference threshold (default: ${SLOT_TIME_THRESHOLD}s)"
    echo "  -o, --output FILE          Set output file (default: ${SLOT_DATA_FILE})"
    echo "  -v, --verbose              Enable verbose output"
    echo "  -b, --background           Run in background mode"
    echo "  status                     Show current slot status"
    echo "  stop                       Stop background monitor"
    echo ""
}

# 参数解析
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -i|--interval)
                SLOT_MONITOR_INTERVAL="$2"
                shift 2
                ;;
            -d|--duration)
                SLOT_MONITOR_DURATION="$2"
                shift 2
                ;;
            --diff)
                SLOT_DIFF_THRESHOLD="$2"
                shift 2
                ;;
            -t|--time)
                SLOT_TIME_THRESHOLD="$2"
                shift 2
                ;;
            -o|--output)
                SLOT_DATA_FILE="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -b|--background)
                BACKGROUND=true
                shift
                ;;
            status)
                show_status
                exit 0
                ;;
            stop)
                stop_monitor
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# 检查依赖
check_dependencies() {
    if ! command -v curl &> /dev/null; then
        echo "Error: curl is not installed"
        exit 1
    fi
    if ! command -v jq &> /dev/null; then
        echo "Error: jq is not installed"
        exit 1
    fi
}

# 获取本地节点 Slot
get_local_slot() {
    # 使用共享函数库中的函数获取 Slot
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && get_slot "$LOCAL_RPC_URL"
}

# 获取主网 Slot
get_mainnet_slot() {
    # 使用共享函数库中的函数获取 Slot
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && get_slot "$MAINNET_RPC_URL"
}

# 检查节点健康状态
check_node_health() {
    local rpc_url=$1
    # 使用共享函数库中的函数检查健康状态
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && check_node_health "$rpc_url"
}

# 监控 Slot 差异
monitor_slot_diff() {
    local timestamp=$(get_unified_timestamp)
    
    # 使用共享函数库中的函数获取 Slot 数据
    local slot_data=$(source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && get_cached_slot_data "$SLOT_CACHE_FILE" 3 "$LOCAL_RPC_URL" "$MAINNET_RPC_URL")
    
    # 解析数据
    local local_slot=$(echo "$slot_data" | jq -r '.local_slot')
    local mainnet_slot=$(echo "$slot_data" | jq -r '.mainnet_slot')
    local slot_diff=$(echo "$slot_data" | jq -r '.slot_diff')
    local local_health=$(echo "$slot_data" | jq -r '.local_health')
    local mainnet_health=$(echo "$slot_data" | jq -r '.mainnet_health')
    local data_loss=$(echo "$slot_data" | jq -r '.data_loss')
    
    # 使用缓冲写入减少磁盘 I/O
    local data_line="$timestamp,$local_slot,$mainnet_slot,$slot_diff,$local_health,$mainnet_health,$data_loss"
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && buffered_write "$SLOT_DATA_FILE" "$data_line" 10
    
    # 检查 Slot 差异是否超过阈值
    if [[ "$slot_diff" != "null" && "$slot_diff" != "N/A" && $slot_diff -gt $SLOT_DIFF_THRESHOLD ]]; then
        if [[ "$SLOT_DIFF_ALERT" == "false" ]]; then
            SLOT_DIFF_ALERT=true
            SLOT_DIFF_START_TIME=$(get_unified_timestamp)
            echo "⚠️ ALERT: Slot difference ($slot_diff) exceeds threshold ($SLOT_DIFF_THRESHOLD) at $SLOT_DIFF_START_TIME"
            
            # 记录异常事件开始
            SLOT_DIFF_EVENT_ID=$(./unified_event_manager.sh start "slot_diff" "slot_monitor" "Slot difference $slot_diff exceeds threshold $SLOT_DIFF_THRESHOLD")
        fi
        
        # 检查持续时间是否超过阈值
        if [[ -n "$SLOT_DIFF_START_TIME" ]]; then
            local start_seconds=$(date -d "$SLOT_DIFF_START_TIME" +%s)
            local current_seconds=$(date +%s)
            local duration=$((current_seconds - start_seconds))
            
            if [[ $duration -gt $SLOT_TIME_THRESHOLD ]]; then
                echo "🚨 CRITICAL: Slot difference has exceeded threshold for ${duration}s (> ${SLOT_TIME_THRESHOLD}s)"
                echo "🚨 CRITICAL: Local node may be considered unavailable for service"
                
                # 记录事件
                SLOT_DIFF_EVENTS+=("CRITICAL: Slot diff $slot_diff for ${duration}s at $(get_unified_timestamp)")
            fi
        fi
    elif [[ "$SLOT_DIFF_ALERT" == "true" ]]; then
        SLOT_DIFF_ALERT=false
        SLOT_DIFF_END_TIME=$(get_unified_timestamp)
        
        # 计算持续时间
        local start_seconds=$(date -d "$SLOT_DIFF_START_TIME" +%s)
        local end_seconds=$(date -d "$SLOT_DIFF_END_TIME" +%s)
        local duration=$((end_seconds - start_seconds))
        
        echo "✅ RESOLVED: Slot difference is now below threshold at $SLOT_DIFF_END_TIME (lasted ${duration}s)"
        
        # 记录事件结束
        if [[ -n "$SLOT_DIFF_EVENT_ID" ]]; then
            ./unified_event_manager.sh end "$SLOT_DIFF_EVENT_ID"
        fi
        
        # 记录事件
        SLOT_DIFF_EVENTS+=("RESOLVED: Slot diff normalized after ${duration}s at $SLOT_DIFF_END_TIME")
        
        # 重置开始时间
        SLOT_DIFF_START_TIME=""
        SLOT_DIFF_EVENT_ID=""
    fi
    
    # 检查数据丢失
    if [[ "$data_loss" == "true" ]]; then
        DATA_LOSS_COUNT=$((DATA_LOSS_COUNT + 1))
        
        if [[ "$DATA_LOSS_ALERT" == "false" ]]; then
            DATA_LOSS_ALERT=true
            DATA_LOSS_START_TIME=$(get_unified_timestamp)
            DATA_LOSS_PERIODS=$((DATA_LOSS_PERIODS + 1))
            echo "⚠️ ALERT: Data loss or node health issue detected at $DATA_LOSS_START_TIME"
            echo "    Local health: $local_health, Mainnet health: $mainnet_health"
            echo "    Local slot: $local_slot, Mainnet slot: $mainnet_slot"
            
            # 记录数据丢失统计到共享文件
            update_data_loss_stats
        fi
    elif [[ "$DATA_LOSS_ALERT" == "true" ]]; then
        DATA_LOSS_ALERT=false
        DATA_LOSS_END_TIME=$(get_unified_timestamp)
        
        # 计算持续时间
        local start_seconds=$(date -d "$DATA_LOSS_START_TIME" +%s)
        local end_seconds=$(date -d "$DATA_LOSS_END_TIME" +%s)
        local duration=$((end_seconds - start_seconds))
        
        DATA_LOSS_TOTAL_DURATION=$((DATA_LOSS_TOTAL_DURATION + duration))
        
        echo "✅ RESOLVED: Data loss or node health issue resolved at $DATA_LOSS_END_TIME (lasted ${duration}s)"
        
        # 记录事件
        DATA_LOSS_EVENTS+=("Data loss or node health issue for ${duration}s from $DATA_LOSS_START_TIME to $DATA_LOSS_END_TIME")
        
        # 更新统计
        update_data_loss_stats
        
        # 重置开始时间
        DATA_LOSS_START_TIME=""
    fi
    
    # 详细输出
    if [[ "$VERBOSE" == "true" ]]; then
        echo "[$timestamp] Local: $local_slot, Mainnet: $mainnet_slot, Diff: $slot_diff, Local Health: $local_health, Mainnet Health: $mainnet_health, Data Loss: $data_loss"
    fi
    
    # 清理旧的缓存数据
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && cleanup_slot_cache "$MEMORY_SHARE_DIR" 5
}

# 显示当前状态
show_status() {
    echo "Slot Monitor Status"
    echo "===================="
    
    # 获取最新的 Slot 数据
    local slot_data=$(source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && get_cached_slot_data "$SLOT_CACHE_FILE" "$CACHE_MAX_AGE" "$LOCAL_RPC_URL" "$MAINNET_RPC_URL")
    
    # 解析数据
    local timestamp=$(echo "$slot_data" | jq -r '.timestamp')
    local local_slot=$(echo "$slot_data" | jq -r '.local_slot')
    local mainnet_slot=$(echo "$slot_data" | jq -r '.mainnet_slot')
    local slot_diff=$(echo "$slot_data" | jq -r '.slot_diff')
    local local_health=$(echo "$slot_data" | jq -r '.local_health')
    local mainnet_health=$(echo "$slot_data" | jq -r '.mainnet_health')
    local data_loss=$(echo "$slot_data" | jq -r '.data_loss')
    
    echo "Last update: $timestamp"
    echo "Local slot: $local_slot"
    echo "Mainnet slot: $mainnet_slot"
    echo "Slot difference: $slot_diff"
    echo "Local health: $local_health"
    echo "Mainnet health: $mainnet_health"
    echo "Data loss: $data_loss"
    
    # 检查是否超过阈值
    if [[ "$slot_diff" != "null" && $slot_diff -gt $SLOT_DIFF_THRESHOLD ]]; then
        echo "⚠️ WARNING: Slot difference exceeds threshold ($SLOT_DIFF_THRESHOLD)"
    else
        echo "✅ OK: Slot difference is within threshold"
    fi
    
    # 检查是否有进程在运行
    if [[ -f "${TMP_DIR}/slot_monitor.pid" ]]; then
        local pid=$(cat "${TMP_DIR}/slot_monitor.pid")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Monitor is running with PID: $pid"
        else
            echo "Monitor is not running (stale PID file)"
        fi
    else
        echo "Monitor is not running"
    fi
}

# 停止监控
stop_monitor() {
    echo "Stopping slot monitor..."
    
    if [[ -f "${TMP_DIR}/slot_monitor.pid" ]]; then
        local pid=$(cat "${TMP_DIR}/slot_monitor.pid" 2>/dev/null)
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            echo "Stopping Slot monitor (PID: $pid)..."
            kill "$pid" 2>/dev/null
            sleep 2
            
            # 检查进程是否还在运行
            if kill -0 "$pid" 2>/dev/null; then
                echo "Force killing Slot monitor (PID: $pid)..."
                kill -9 "$pid" 2>/dev/null
            fi
            
            echo "Slot monitor stopped successfully"
        else
            echo "Slot monitor is not running"
        fi
        rm -f "${TMP_DIR}/slot_monitor.pid"
    else
        echo "Slot monitor PID file not found"
        # 尝试通过进程名终止
        pkill -f "slot_monitor.sh" 2>/dev/null || true
    fi
    
    # 清理缓冲文件
    if [[ -n "$SLOT_DATA_FILE" ]]; then
        rm -f "${SLOT_DATA_FILE}.buffer" 2>/dev/null || true
    fi
    
    # 清理共享内存
    rm -rf /dev/shm/solana-qps-test/ 2>/dev/null || true
    
    echo "Slot monitor cleanup completed"
}

# 启动监控
start_monitoring() {
    echo "Starting Slot monitor..."
    echo "Monitoring interval: ${SLOT_MONITOR_INTERVAL}s"
    echo "Slot difference threshold: ${SLOT_DIFF_THRESHOLD}"
    echo "Slot time difference threshold: ${SLOT_TIME_THRESHOLD}s"
    echo "Output file: $SLOT_DATA_FILE"
    
    # 创建输出目录
    mkdir -p "$(dirname "$SLOT_DATA_FILE")"
    
    # 创建缓存目录
    if [[ "$USE_MEMORY_CACHE" == "true" ]]; then
        mkdir -p "$(dirname "$SLOT_CACHE_FILE")"
    fi
    
    # 写入 CSV 头
    echo "timestamp,local_slot,mainnet_slot,slot_diff,local_health,mainnet_health,data_loss" > "$SLOT_DATA_FILE"
    
    # 如果是后台模式，启动后台进程
    if [[ "$BACKGROUND" == "true" ]]; then
        (
            # 在后台进程中设置信号处理
            trap 'cleanup_and_exit' SIGTERM SIGINT SIGQUIT EXIT
            
            # 检查是否有duration参数（单独运行模式）
            if [[ -n "$SLOT_MONITOR_DURATION" ]]; then
                local start_time=$(date +%s)
                local end_time=$((start_time + SLOT_MONITOR_DURATION))
                
                while [[ $(date +%s) -lt $end_time ]]; do
                    monitor_slot_diff
                    sleep "$SLOT_MONITOR_INTERVAL"
                done
            else
                # QPS测试模式：无限运行
                while true; do
                    monitor_slot_diff
                    sleep "$SLOT_MONITOR_INTERVAL"
                done
            fi
        ) &
        MONITOR_PID=$!
        echo "Monitor started in background with PID: $MONITOR_PID"
        echo "$MONITOR_PID" > "${TMP_DIR}/slot_monitor.pid"
    else
        # 前台模式 - 设置信号处理
        trap 'cleanup_and_exit' SIGTERM SIGINT SIGQUIT
        
        # 检查是否有duration参数（单独运行模式）
        if [[ -n "$SLOT_MONITOR_DURATION" ]]; then
            local start_time=$(date +%s)
            local end_time=$((start_time + SLOT_MONITOR_DURATION))
            
            while [[ $(date +%s) -lt $end_time ]]; do
                monitor_slot_diff
                sleep "$SLOT_MONITOR_INTERVAL"
            done
        else
            # QPS测试模式：无限运行
            while true; do
                monitor_slot_diff
                sleep "$SLOT_MONITOR_INTERVAL"
            done
        fi
    fi
}

# 主函数
main() {
    # 检查依赖
    check_dependencies
    
    # 解析参数
    parse_args "$@"
    
    # 启动监控
    start_monitoring
}

# 执行主函数
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
# 更新数据丢失统计
update_data_loss_stats() {
    # 创建统一的数据丢失统计JSON
    local stats_json="{
        \"data_loss_count\": $DATA_LOSS_COUNT,
        \"data_loss_periods\": $DATA_LOSS_PERIODS,
        \"total_duration\": $DATA_LOSS_TOTAL_DURATION,
        \"last_updated\": \"$(date +"%Y-%m-%d %H:%M:%S")\"
    }"
    
    # 写入共享文件
    echo "$stats_json" > "${MEMORY_SHARE_DIR}/data_loss_stats.json"
}
