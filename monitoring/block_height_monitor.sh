#!/bin/bash

# =====================================================================
# Multi-Chain Block Height Monitor Module
# Monitor block height difference between local blockchain node and mainnet
# =====================================================================

# Load configuration file
# Safely load configuration file to avoid readonly variable conflicts
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "Warning: Configuration file loading failed, using default configuration"
    BLOCK_HEIGHT_MONITOR_RATE=${BLOCK_HEIGHT_MONITOR_RATE:-1}
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi

# Initialize variables
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

# Cleanup and exit function
cleanup_and_exit() {
    echo "Received termination signal, cleaning up block height monitor..."
    
    # Flush all buffers
    if [[ -n "$BLOCK_HEIGHT_DATA_FILE" && -f "$BLOCK_HEIGHT_DATA_FILE" ]]; then
        sync "$BLOCK_HEIGHT_DATA_FILE" 2>/dev/null || true
        rm -f "${BLOCK_HEIGHT_DATA_FILE}.buffer" 2>/dev/null || true
    fi
    
    # Delete PID file
    rm -f "${TMP_DIR}/block_height_monitor.pid" 2>/dev/null || true
    
    # Clean shared memory cache - only clean block_height related files, keep QPS status file
    if [[ -n "$BASE_MEMORY_DIR" ]]; then
        # Only clean block_height related cache files, keep other process status files
        rm -f "$MEMORY_SHARE_DIR"/block_height_monitor_cache.json 2>/dev/null || true
        rm -f "$BASE_MEMORY_DIR"/node_health_*.cache 2>/dev/null || true
    fi
    
    echo "Block height monitor cleanup completed"
    exit 0
}

# Note: Signal handling will be set in background monitoring mode, not globally
DATA_LOSS_COUNT=0
DATA_LOSS_PERIODS=0
DATA_LOSS_TOTAL_DURATION=0
BACKGROUND=false
VERBOSE=false

# Help information
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

# Parse arguments
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

# Check dependencies
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

# Get local node block height
get_local_block_height() {
    # Use function from shared function library to get block height
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && get_block_height "$LOCAL_RPC_URL"
}

# Get mainnet block height
get_mainnet_block_height() {
    # Use function from shared function library to get block height
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && get_block_height "$MAINNET_RPC_URL"
}

# Check node health status
check_node_health() {
    local rpc_url=$1
    # Use function from shared function library to check health status
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && check_node_health "$rpc_url"
}

# Monitor block height difference
monitor_block_height_diff() {
    local timestamp=$(get_unified_timestamp)
    
    # Use function from shared function library to get block height data
    local block_height_data=$(source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && get_cached_block_height_data "$BLOCK_HEIGHT_CACHE_FILE" 3 "$LOCAL_RPC_URL" "$MAINNET_RPC_URL")
    
    # Parse data
    local local_block_height=$(echo "$block_height_data" | jq -r '.local_block_height')
    local mainnet_block_height=$(echo "$block_height_data" | jq -r '.mainnet_block_height')
    local block_height_diff=$(echo "$block_height_data" | jq -r '.block_height_diff')
    local local_health=$(echo "$block_height_data" | jq -r '.local_health')
    local mainnet_health=$(echo "$block_height_data" | jq -r '.mainnet_health')
    local data_loss=$(echo "$block_height_data" | jq -r '.data_loss')
    
    # Use buffered write to reduce disk I/O
    local data_line="$timestamp,$local_block_height,$mainnet_block_height,$block_height_diff,$local_health,$mainnet_health,$data_loss"
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && buffered_write "$BLOCK_HEIGHT_DATA_FILE" "$data_line" 10
    
    # Check if block height difference exceeds threshold
    if [[ "$block_height_diff" != "null" && "$block_height_diff" != "N/A" && $block_height_diff -gt $BLOCK_HEIGHT_DIFF_THRESHOLD ]]; then
        if [[ "$BLOCK_HEIGHT_DIFF_ALERT" == "false" ]]; then
            BLOCK_HEIGHT_DIFF_ALERT=true
            BLOCK_HEIGHT_DIFF_START_TIME=$(get_unified_timestamp)
            echo "⚠️ ALERT: Block height difference ($block_height_diff) exceeds threshold ($BLOCK_HEIGHT_DIFF_THRESHOLD) at $BLOCK_HEIGHT_DIFF_START_TIME"
            
            # Record exception event start
            BLOCK_HEIGHT_DIFF_EVENT_ID=$(./unified_event_manager.sh start "block_height_diff" "block_height_monitor" "Block height difference $block_height_diff exceeds threshold $BLOCK_HEIGHT_DIFF_THRESHOLD")
        fi
        
        # Check if duration exceeds threshold
        if [[ -n "$BLOCK_HEIGHT_DIFF_START_TIME" ]]; then
            local start_seconds=$(date -d "$BLOCK_HEIGHT_DIFF_START_TIME" +%s)
            local current_seconds=$(date +%s)
            local duration=$((current_seconds - start_seconds))
            
            if [[ $duration -gt $BLOCK_HEIGHT_TIME_THRESHOLD ]]; then
                echo "🚨 CRITICAL: Block height difference has exceeded threshold for ${duration}s (> ${BLOCK_HEIGHT_TIME_THRESHOLD}s)"
                echo "🚨 CRITICAL: Local node may be considered unavailable for service"
                
                # Set persistent exceeded flag file (for system-level bottleneck judgment)
                echo "1" > "${MEMORY_SHARE_DIR}/block_height_time_exceeded.flag"
                
                # Record event
                BLOCK_HEIGHT_DIFF_EVENTS+=("CRITICAL: Block height diff $block_height_diff for ${duration}s at $(get_unified_timestamp)")
            fi
        fi
    elif [[ "$BLOCK_HEIGHT_DIFF_ALERT" == "true" ]]; then
        BLOCK_HEIGHT_DIFF_ALERT=false
        BLOCK_HEIGHT_DIFF_END_TIME=$(get_unified_timestamp)
        
        # Calculate duration
        local start_seconds=$(date -d "$BLOCK_HEIGHT_DIFF_START_TIME" +%s)
        local end_seconds=$(date -d "$BLOCK_HEIGHT_DIFF_END_TIME" +%s)
        local duration=$((end_seconds - start_seconds))
        
        echo "✅ RESOLVED: Block height difference is now below threshold at $BLOCK_HEIGHT_DIFF_END_TIME (lasted ${duration}s)"
        
        # Record event end
        if [[ -n "$BLOCK_HEIGHT_DIFF_EVENT_ID" ]]; then
            ./unified_event_manager.sh end "$BLOCK_HEIGHT_DIFF_EVENT_ID"
        fi
        
        # Record event
        BLOCK_HEIGHT_DIFF_EVENTS+=("RESOLVED: Block height diff normalized after ${duration}s at $BLOCK_HEIGHT_DIFF_END_TIME")
        
        # Reset start time
        BLOCK_HEIGHT_DIFF_START_TIME=""
        BLOCK_HEIGHT_DIFF_EVENT_ID=""
    fi
    
    # Check data loss
    if [[ "$data_loss" == "1" ]]; then
        DATA_LOSS_COUNT=$((DATA_LOSS_COUNT + 1))
        
        if [[ "$DATA_LOSS_ALERT" == "false" ]]; then
            DATA_LOSS_ALERT=true
            DATA_LOSS_START_TIME=$(get_unified_timestamp)
            DATA_LOSS_PERIODS=$((DATA_LOSS_PERIODS + 1))
            # Convert numeric values to human-readable format
            local local_health_display=$([ "$local_health" = "1" ] && echo "healthy" || echo "unhealthy")
            local mainnet_health_display=$([ "$mainnet_health" = "1" ] && echo "healthy" || echo "unhealthy")
            
            echo "⚠️ ALERT: Data loss or node health issue detected at $DATA_LOSS_START_TIME"
            echo "    Local health: $local_health_display, Mainnet health: $mainnet_health_display"
            echo "    Local block height: $local_block_height, Mainnet block height: $mainnet_block_height"
            
            # Record data loss statistics to shared file
            update_data_loss_stats
        fi
    elif [[ "$DATA_LOSS_ALERT" == "true" ]]; then
        DATA_LOSS_ALERT=false
        DATA_LOSS_END_TIME=$(get_unified_timestamp)
        
        # Calculate duration
        local start_seconds=$(date -d "$DATA_LOSS_START_TIME" +%s)
        local end_seconds=$(date -d "$DATA_LOSS_END_TIME" +%s)
        local duration=$((end_seconds - start_seconds))
        
        DATA_LOSS_TOTAL_DURATION=$((DATA_LOSS_TOTAL_DURATION + duration))
        
        echo "✅ RESOLVED: Data loss or node health issue resolved at $DATA_LOSS_END_TIME (lasted ${duration}s)"
        
        # Record event
        DATA_LOSS_EVENTS+=("Data loss or node health issue for ${duration}s from $DATA_LOSS_START_TIME to $DATA_LOSS_END_TIME")
        
        # Update statistics
        update_data_loss_stats
        
        # Reset start time
        DATA_LOSS_START_TIME=""
    fi
    
    # Verbose output
    if [[ "$VERBOSE" == "true" ]]; then
        # Convert numeric values to human-readable format
        local local_health_display=$([ "$local_health" = "1" ] && echo "healthy" || echo "unhealthy")
        local mainnet_health_display=$([ "$mainnet_health" = "1" ] && echo "healthy" || echo "unhealthy")
        local data_loss_display=$([ "$data_loss" = "1" ] && echo "detected" || echo "none")
        echo "[$timestamp] Local: $local_block_height, Mainnet: $mainnet_block_height, Diff: $block_height_diff, Local Health: $local_health_display, Mainnet Health: $mainnet_health_display, Data Loss: $data_loss_display"
    fi
    
    # Clean up old cache data
    source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && cleanup_block_height_cache "$MEMORY_SHARE_DIR" 5
}

# Display current status
show_status() {
    echo "Block Height Monitor Status"
    echo "===================="
    
    # Get latest block height data
    local block_height_data=$(source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh" && get_cached_block_height_data "$BLOCK_HEIGHT_CACHE_FILE" "$CACHE_MAX_AGE" "$LOCAL_RPC_URL" "$MAINNET_RPC_URL")
    
    # Parse data
    local timestamp=$(echo "$block_height_data" | jq -r '.timestamp')
    local local_block_height=$(echo "$block_height_data" | jq -r '.local_block_height')
    local mainnet_block_height=$(echo "$block_height_data" | jq -r '.mainnet_block_height')
    local block_height_diff=$(echo "$block_height_data" | jq -r '.block_height_diff')
    local local_health=$(echo "$block_height_data" | jq -r '.local_health')
    local mainnet_health=$(echo "$block_height_data" | jq -r '.mainnet_health')
    local data_loss=$(echo "$block_height_data" | jq -r '.data_loss')
    
    # Convert numeric values to human-readable format
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
    
    # Check if threshold exceeded
    if [[ "$block_height_diff" != "null" && $block_height_diff -gt $BLOCK_HEIGHT_DIFF_THRESHOLD ]]; then
        echo "⚠️ WARNING: Block height difference exceeds threshold ($BLOCK_HEIGHT_DIFF_THRESHOLD)"
    else
        echo "✅ OK: Block height difference is within threshold"
    fi
    
    # Check if process is running
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

# Stop monitoring
stop_monitor() {
    echo "Stopping block height monitor..."
    
    if [[ -f "${TMP_DIR}/block_height_monitor.pid" ]]; then
        local pid=$(cat "${TMP_DIR}/block_height_monitor.pid" 2>/dev/null)
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            echo "Stopping Block height monitor (PID: $pid)..."
            kill "$pid" 2>/dev/null
            sleep 2
            
            # Check if process is still running
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
        # Try to terminate by process name
        pkill -f "block_height_monitor.sh" 2>/dev/null || true
    fi
    
    # Clean up buffer files
    if [[ -n "$BLOCK_HEIGHT_DATA_FILE" ]]; then
        rm -f "${BLOCK_HEIGHT_DATA_FILE}.buffer" 2>/dev/null || true
    fi
    
    # Clean up shared memory
    rm -rf /dev/shm/blockchain-node-qps-test/ 2>/dev/null || true
    
    echo "Block height monitor cleanup completed"
}

# Start monitoring
start_monitoring() {
    echo "Starting Block Height monitor..."
    echo "Monitoring rate: ${BLOCK_HEIGHT_MONITOR_RATE}/s"
    echo "Block height difference threshold: ${BLOCK_HEIGHT_DIFF_THRESHOLD}"
    echo "Block height time difference threshold: ${BLOCK_HEIGHT_TIME_THRESHOLD}s"
    echo "Output file: $BLOCK_HEIGHT_DATA_FILE"
    
    # Create output directory
    mkdir -p "$(dirname "$BLOCK_HEIGHT_DATA_FILE")"
    
    # Create cache directory
    if [[ "$USE_MEMORY_CACHE" == "true" ]]; then
        mkdir -p "$(dirname "$BLOCK_HEIGHT_CACHE_FILE")"
    fi
    
    # Write CSV header
    echo "timestamp,local_block_height,mainnet_block_height,block_height_diff,local_health,mainnet_health,data_loss" > "$BLOCK_HEIGHT_DATA_FILE"
    
    # Unified monitoring loop - follow framework lifecycle
    if [[ "$BACKGROUND" == "true" ]]; then
        (
            # Set signal handling in background process
            trap 'cleanup_and_exit' SIGTERM SIGINT SIGQUIT EXIT
            
            # Frequency conversion: calculate sleep interval
            local sleep_interval=$(awk "BEGIN {printf \"%.3f\", 1/$BLOCK_HEIGHT_MONITOR_RATE}" 2>/dev/null || echo "1")
            
            # Follow framework lifecycle
            while [[ -f "$TMP_DIR/qps_test_status" ]]; do
                monitor_block_height_diff
                sleep "$sleep_interval"
            done
        ) &
        MONITOR_PID=$!
        echo "Monitor started in background with PID: $MONITOR_PID"
        echo "$MONITOR_PID" > "${TMP_DIR}/block_height_monitor.pid"
    else
        # Foreground mode (kept for debugging)
        trap 'cleanup_and_exit' SIGTERM SIGINT SIGQUIT
        
        # Frequency conversion: calculate sleep interval
        local sleep_interval=$(awk "BEGIN {printf \"%.3f\", 1/$BLOCK_HEIGHT_MONITOR_RATE}" 2>/dev/null || echo "1")
        
        # Follow framework lifecycle
        while [[ -f "$TMP_DIR/qps_test_status" ]]; do
            monitor_block_height_diff
            sleep "$sleep_interval"
        done
    fi
}

# Main function
main() {
    # Check dependencies
    check_dependencies
    
    # Parse arguments
    parse_args "$@"
    
    # Start monitoring
    start_monitoring
}

# Execute main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
# Update data loss statistics
update_data_loss_stats() {
    # Create unified data loss statistics JSON
    local stats_json="{
        \"data_loss_count\": $DATA_LOSS_COUNT,
        \"data_loss_periods\": $DATA_LOSS_PERIODS,
        \"total_duration\": $DATA_LOSS_TOTAL_DURATION,
        \"last_updated\": \"$(date +"%Y-%m-%d %H:%M:%S")\"
    }"
    
    # Write to shared file
    echo "$stats_json" > "${MEMORY_SHARE_DIR}/data_loss_stats.json"
}
