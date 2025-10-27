#!/bin/bash

# =====================================================================
# 多链区块高度监控模块
# 用于监控本地区块链节点与主网之间的区块高度差异
# =====================================================================

# 加载配置文件
# 安全加载配置文件，避免readonly变量冲突
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "警告: 配置文件加载失败，使用默认配置"
    BLOCK_HEIGHT_MONITOR_RATE=${BLOCK_HEIGHT_MONITOR_RATE:-1}
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi

# 初始化变量
MONITOR_PID=""
BLOCK_HEIGHT_DIFF_ALERT=false
BLOCK_HEIGHT_DIFF_START_TIME=""
BLOCK_HEIGHT_DIFF_END_TIME=""
BLOCK_HEIGHT_DIFF_EVENT_ID=""
BLOCK_HEIGHT_DIFF_EVENTS=()
DATA_LOSS_ALERT=false
DATA_LOSS_START_TIME=""
DATA_LOSS_END_TIME=""
DATA_LOSS_EVENTS=()

# 清理和退出函数
cleanup_and_exit() {
    echo "Received termination signal, cleaning up block height monitor..."
    
    # 刷新所有缓冲
    if [[ -n "$BLOCK_HEIGHT_DATA_FILE" && -f "$BLOCK_HEIGHT_DATA_FILE" ]]; then
        sync "$BLOCK_HEIGHT_DATA_FILE" 2>/dev/null || true
        rm -f "${BLOCK_HEIGHT_DATA_FILE}.buffer" 2>/dev/null || true
    fi
    
    # 删除PID文件
    rm -f "${TMP_DIR}/block_height_monitor.pid" 2>/dev/null || true
    
    # 清理共享内存缓存 - 只清理block_height相关文件，保留QPS状态文件
    if [[ -n "$BASE_MEMORY_DIR" ]]; then
        # 只清理block_height相关的缓存文件，保留其他进程的状态文件
        rm -f "$MEMORY_SHARE_DIR"/block_height_monitor_cache.json 2>/dev/null || true
        rm -f "$BASE_MEMORY_DIR"/node_health_*.cache 2>/dev/null || true
    fi
    
    echo "Block height monitor cleanup completed"
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
    echo "Multi-Chain Block Height Monitor"
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help                 Show this help message"
    echo "  -r, --rate RATE            Set monitoring rate (times per second, default: ${BLOCK_HEIGHT_MONITOR_RATE})"
    echo "  --diff BLOCKS              Set block height difference threshold (default: ${BLOCK_HEIGHT_DIFF_THRESHOLD})"
    echo "  -t, --time SECONDS         Set time difference threshold (default: ${BLOCK_HEIGHT_TIME_THRESHOLD}s)"
    echo "  -o, --output FILE          Set output file (default: ${BLOCK_HEIGHT_DATA_FILE})"
    echo "  -v, --verbose              Enable verbose output"
    echo "  -b, --background           Run in background mode"
    echo "  status                     Show current block height status"
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
            -r|--rate)
                BLOCK_HEIGHT_MONITOR_RATE="$2"
                shift 2
                ;;
            --diff)
                BLOCK_HEIGHT_DIFF_THRESHOLD="$2"
                shift 2
                ;;
            -t|--time)
                BLOCK_HEIGHT_TIME_THRESHOLD="$2"
                shift 2
                ;;
            -o|--output)
                BLOCK_HEIGHT_DATA_FILE="$2"
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

# 获取本地节点区块高度
get_local_block_height() {
    # 使用共享函数库中的函数获取区块高度
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && get_block_height "$LOCAL_RPC_URL"
}

# 获取主网区块高度
get_mainnet_block_height() {
    # 使用共享函数库中的函数获取区块高度
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && get_block_height "$MAINNET_RPC_URL"
}

# 检查节点健康状态
check_node_health() {
    local rpc_url=$1
    # 使用共享函数库中的函数检查健康状态
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && check_node_health "$rpc_url"
}

# 监控区块高度差异
monitor_block_height_diff() {
    local timestamp=$(get_unified_timestamp)
    
    # 使用共享函数库中的函数获取区块高度数据
    local block_height_data=$(source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && get_cached_block_height_data "$BLOCK_HEIGHT_CACHE_FILE" 3 "$LOCAL_RPC_URL" "$MAINNET_RPC_URL")
    
    # 解析数据
    local local_block_height=$(echo "$block_height_data" | jq -r '.local_block_height')
    local mainnet_block_height=$(echo "$block_height_data" | jq -r '.mainnet_block_height')
    local block_height_diff=$(echo "$block_height_data" | jq -r '.block_height_diff')
    local local_health=$(echo "$block_height_data" | jq -r '.local_health')
    local mainnet_health=$(echo "$block_height_data" | jq -r '.mainnet_health')
    local data_loss=$(echo "$block_height_data" | jq -r '.data_loss')
    
    # 使用缓冲写入减少磁盘 I/O
    local data_line="$timestamp,$local_block_height,$mainnet_block_height,$block_height_diff,$local_health,$mainnet_health,$data_loss"
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && buffered_write "$BLOCK_HEIGHT_DATA_FILE" "$data_line" 10
    
    # 检查区块高度差异是否超过阈值
    if [[ "$block_height_diff" != "null" && "$block_height_diff" != "N/A" && $block_height_diff -gt $BLOCK_HEIGHT_DIFF_THRESHOLD ]]; then
        if [[ "$BLOCK_HEIGHT_DIFF_ALERT" == "false" ]]; then
            BLOCK_HEIGHT_DIFF_ALERT=true
            BLOCK_HEIGHT_DIFF_START_TIME=$(get_unified_timestamp)
            echo "⚠️ ALERT: Block height difference ($block_height_diff) exceeds threshold ($BLOCK_HEIGHT_DIFF_THRESHOLD) at $BLOCK_HEIGHT_DIFF_START_TIME"
            
            # 记录异常事件开始
            BLOCK_HEIGHT_DIFF_EVENT_ID=$(./unified_event_manager.sh start "block_height_diff" "block_height_monitor" "Block height difference $block_height_diff exceeds threshold $BLOCK_HEIGHT_DIFF_THRESHOLD")
        fi
        
        # 检查持续时间是否超过阈值
        if [[ -n "$BLOCK_HEIGHT_DIFF_START_TIME" ]]; then
            local start_seconds=$(date -d "$BLOCK_HEIGHT_DIFF_START_TIME" +%s)
            local current_seconds=$(date +%s)
            local duration=$((current_seconds - start_seconds))
            
            if [[ $duration -gt $BLOCK_HEIGHT_TIME_THRESHOLD ]]; then
                echo "🚨 CRITICAL: Block height difference has exceeded threshold for ${duration}s (> ${BLOCK_HEIGHT_TIME_THRESHOLD}s)"
                echo "🚨 CRITICAL: Local node may be considered unavailable for service"
                
                # 设置持续超限标志文件（用于系统级瓶颈判断）
                echo "1" > "${MEMORY_SHARE_DIR}/block_height_time_exceeded.flag"
                
                # 记录事件
                BLOCK_HEIGHT_DIFF_EVENTS+=("CRITICAL: Block height diff $block_height_diff for ${duration}s at $(get_unified_timestamp)")
            fi
        fi
    elif [[ "$BLOCK_HEIGHT_DIFF_ALERT" == "true" ]]; then
        BLOCK_HEIGHT_DIFF_ALERT=false
        BLOCK_HEIGHT_DIFF_END_TIME=$(get_unified_timestamp)
        
        # 计算持续时间
        local start_seconds=$(date -d "$BLOCK_HEIGHT_DIFF_START_TIME" +%s)
        local end_seconds=$(date -d "$BLOCK_HEIGHT_DIFF_END_TIME" +%s)
        local duration=$((end_seconds - start_seconds))
        
        echo "✅ RESOLVED: Block height difference is now below threshold at $BLOCK_HEIGHT_DIFF_END_TIME (lasted ${duration}s)"
        
        # 记录事件结束
        if [[ -n "$BLOCK_HEIGHT_DIFF_EVENT_ID" ]]; then
            ./unified_event_manager.sh end "$BLOCK_HEIGHT_DIFF_EVENT_ID"
        fi
        
        # 记录事件
        BLOCK_HEIGHT_DIFF_EVENTS+=("RESOLVED: Block height diff normalized after ${duration}s at $BLOCK_HEIGHT_DIFF_END_TIME")
        
        # 重置开始时间
        BLOCK_HEIGHT_DIFF_START_TIME=""
        BLOCK_HEIGHT_DIFF_EVENT_ID=""
    fi
    
    # 检查数据丢失
    if [[ "$data_loss" == "1" ]]; then
        DATA_LOSS_COUNT=$((DATA_LOSS_COUNT + 1))
        
        if [[ "$DATA_LOSS_ALERT" == "false" ]]; then
            DATA_LOSS_ALERT=true
            DATA_LOSS_START_TIME=$(get_unified_timestamp)
            DATA_LOSS_PERIODS=$((DATA_LOSS_PERIODS + 1))
            # 转换数值为人类可读格式
            local local_health_display=$([ "$local_health" = "1" ] && echo "healthy" || echo "unhealthy")
            local mainnet_health_display=$([ "$mainnet_health" = "1" ] && echo "healthy" || echo "unhealthy")
            
            echo "⚠️ ALERT: Data loss or node health issue detected at $DATA_LOSS_START_TIME"
            echo "    Local health: $local_health_display, Mainnet health: $mainnet_health_display"
            echo "    Local block height: $local_block_height, Mainnet block height: $mainnet_block_height"
            
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
        # 转换数值为人类可读格式
        local local_health_display=$([ "$local_health" = "1" ] && echo "healthy" || echo "unhealthy")
        local mainnet_health_display=$([ "$mainnet_health" = "1" ] && echo "healthy" || echo "unhealthy")
        local data_loss_display=$([ "$data_loss" = "1" ] && echo "detected" || echo "none")
        echo "[$timestamp] Local: $local_block_height, Mainnet: $mainnet_block_height, Diff: $block_height_diff, Local Health: $local_health_display, Mainnet Health: $mainnet_health_display, Data Loss: $data_loss_display"
    fi
    
    # 清理旧的缓存数据
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && cleanup_block_height_cache "$MEMORY_SHARE_DIR" 5
}

# 显示当前状态
show_status() {
    echo "Block Height Monitor Status"
    echo "===================="
    
    # 获取最新的区块高度数据
    local block_height_data=$(source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && get_cached_block_height_data "$BLOCK_HEIGHT_CACHE_FILE" "$CACHE_MAX_AGE" "$LOCAL_RPC_URL" "$MAINNET_RPC_URL")
    
    # 解析数据
    local timestamp=$(echo "$block_height_data" | jq -r '.timestamp')
    local local_block_height=$(echo "$block_height_data" | jq -r '.local_block_height')
    local mainnet_block_height=$(echo "$block_height_data" | jq -r '.mainnet_block_height')
    local block_height_diff=$(echo "$block_height_data" | jq -r '.block_height_diff')
    local local_health=$(echo "$block_height_data" | jq -r '.local_health')
    local mainnet_health=$(echo "$block_height_data" | jq -r '.mainnet_health')
    local data_loss=$(echo "$block_height_data" | jq -r '.data_loss')
    
    # 转换数值为人类可读格式
    local local_health_display=$([ "$local_health" = "1" ] && echo "healthy" || echo "unhealthy")
    local mainnet_health_display=$([ "$mainnet_health" = "1" ] && echo "healthy" || echo "unhealthy")
    local data_loss_display=$([ "$data_loss" = "1" ] && echo "detected" || echo "none")
    
    echo "Last update: $timestamp"
    echo "Local block height: $local_block_height"
    echo "Mainnet block height: $mainnet_block_height"
    echo "Block height difference: $block_height_diff"
    echo "Local health: $local_health_display"
    echo "Mainnet health: $mainnet_health_display"
    echo "Data loss: $data_loss_display"
    
    # 检查是否超过阈值
    if [[ "$block_height_diff" != "null" && $block_height_diff -gt $BLOCK_HEIGHT_DIFF_THRESHOLD ]]; then
        echo "⚠️ WARNING: Block height difference exceeds threshold ($BLOCK_HEIGHT_DIFF_THRESHOLD)"
    else
        echo "✅ OK: Block height difference is within threshold"
    fi
    
    # 检查是否有进程在运行
    if [[ -f "${TMP_DIR}/block_height_monitor.pid" ]]; then
        local pid=$(cat "${TMP_DIR}/block_height_monitor.pid")
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
    echo "Stopping block height monitor..."
    
    if [[ -f "${TMP_DIR}/block_height_monitor.pid" ]]; then
        local pid=$(cat "${TMP_DIR}/block_height_monitor.pid" 2>/dev/null)
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            echo "Stopping Block height monitor (PID: $pid)..."
            kill "$pid" 2>/dev/null
            sleep 2
            
            # 检查进程是否还在运行
            if kill -0 "$pid" 2>/dev/null; then
                echo "Force killing Block height monitor (PID: $pid)..."
                kill -9 "$pid" 2>/dev/null
            fi
            
            echo "Block height monitor stopped successfully"
        else
            echo "Block height monitor is not running"
        fi
        rm -f "${TMP_DIR}/block_height_monitor.pid"
    else
        echo "Block height monitor PID file not found"
        # 尝试通过进程名终止
        pkill -f "block_height_monitor.sh" 2>/dev/null || true
    fi
    
    # 清理缓冲文件
    if [[ -n "$BLOCK_HEIGHT_DATA_FILE" ]]; then
        rm -f "${BLOCK_HEIGHT_DATA_FILE}.buffer" 2>/dev/null || true
    fi
    
    # 清理共享内存
    rm -rf /dev/shm/blockchain-node-qps-test/ 2>/dev/null || true
    
    echo "Block height monitor cleanup completed"
}

# 启动监控
start_monitoring() {
    echo "Starting Block Height monitor..."
    echo "Monitoring rate: ${BLOCK_HEIGHT_MONITOR_RATE}/s"
    echo "Block height difference threshold: ${BLOCK_HEIGHT_DIFF_THRESHOLD}"
    echo "Block height time difference threshold: ${BLOCK_HEIGHT_TIME_THRESHOLD}s"
    echo "Output file: $BLOCK_HEIGHT_DATA_FILE"
    
    # 创建输出目录
    mkdir -p "$(dirname "$BLOCK_HEIGHT_DATA_FILE")"
    
    # 创建缓存目录
    if [[ "$USE_MEMORY_CACHE" == "true" ]]; then
        mkdir -p "$(dirname "$BLOCK_HEIGHT_CACHE_FILE")"
    fi
    
    # 写入 CSV 头
    echo "timestamp,local_block_height,mainnet_block_height,block_height_diff,local_health,mainnet_health,data_loss" > "$BLOCK_HEIGHT_DATA_FILE"
    
    # 统一的监控循环 - 跟随框架生命周期
    if [[ "$BACKGROUND" == "true" ]]; then
        (
            # 在后台进程中设置信号处理
            trap 'cleanup_and_exit' SIGTERM SIGINT SIGQUIT EXIT
            
            # 频率转换：计算sleep间隔
            local sleep_interval=$(awk "BEGIN {printf \"%.3f\", 1/$BLOCK_HEIGHT_MONITOR_RATE}" 2>/dev/null || echo "1")
            
            # 跟随框架生命周期
            while [[ -f "$TMP_DIR/qps_test_status" ]]; do
                monitor_block_height_diff
                sleep "$sleep_interval"
            done
        ) &
        MONITOR_PID=$!
        echo "Monitor started in background with PID: $MONITOR_PID"
        echo "$MONITOR_PID" > "${TMP_DIR}/block_height_monitor.pid"
    else
        # 前台模式（保留用于调试）
        trap 'cleanup_and_exit' SIGTERM SIGINT SIGQUIT
        
        # 频率转换：计算sleep间隔
        local sleep_interval=$(awk "BEGIN {printf \"%.3f\", 1/$BLOCK_HEIGHT_MONITOR_RATE}" 2>/dev/null || echo "1")
        
        # 跟随框架生命周期
        while [[ -f "$TMP_DIR/qps_test_status" ]]; do
            monitor_block_height_diff
            sleep "$sleep_interval"
        done
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
