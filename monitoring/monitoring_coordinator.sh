#!/bin/bash
# =====================================================================
# Monitoring Coordinator - Eliminate monitoring script duplication, unified management of all monitoring tasks
# =====================================================================
# This script integrates all monitoring functions to avoid duplicate monitoring processes
# Provides unified monitoring start, stop and status management
# =====================================================================

# Load error handling and configuration
source "$(dirname "${BASH_SOURCE[0]}")/../utils/error_handler.sh"
# Safely load configuration file to avoid readonly variable conflicts
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "Warning: Configuration file loading failed, using default configuration"
    MONITOR_INTERVAL=${MONITOR_INTERVAL:-5}
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi

setup_error_handling "$(basename "$0")" "Monitoring Coordinator"
log_script_start "$(basename "$0")"

# Monitoring status file - prioritize environment variables, otherwise use default values
if [[ -z "${MONITOR_STATUS_FILE:-}" ]]; then
    readonly MONITOR_STATUS_FILE="${TMP_DIR}/monitoring_status.json"
fi
if [[ -z "${MONITOR_PIDS_FILE:-}" ]]; then
    readonly MONITOR_PIDS_FILE="${TMP_DIR}/monitor_pids.txt"
fi

# Monitoring task definitions - includes all necessary monitoring scripts
# Note: iostat functionality is managed by unified_monitor.sh to avoid duplicate startup and process conflicts
# Users can still start via 'start iostat' command, but will be automatically redirected to unified_monitor.sh
declare -A MONITOR_TASKS=(
    ["unified"]="unified_monitor.sh"
    ["block_height"]="block_height_monitor.sh"
    ["ena_network"]="ena_network_monitor.sh"
    ["ebs_bottleneck"]="ebs_bottleneck_detector.sh"
    ["iostat"]="iostat_collector.sh"  # Managed by unified_monitor.sh
)

# Initialize monitoring coordinator
init_coordinator() {
    echo "🔧 Initializing monitoring coordinator..."
    
    # Create necessary directories
    mkdir -p "${TMP_DIR}" "${LOGS_DIR}"
    
    # Initialize status file
    cat > "$MONITOR_STATUS_FILE" << EOF
{
    "coordinator_start_time": "$(date -Iseconds)",
    "active_monitors": {},
    "total_monitors_started": 0,
    "total_monitors_stopped": 0
}
EOF
    
    # Clear PID file
    > "$MONITOR_PIDS_FILE"
    
    echo "✅ Monitoring coordinator initialization completed"
}

# Check if monitoring task is already running
is_monitor_running() {
    local monitor_name="$1"
    local script_name="${MONITOR_TASKS[$monitor_name]:-}"
    
    if [[ -z "$script_name" ]]; then
        echo "❌ Unknown monitoring task: $monitor_name"
        return 1
    fi
    
    # Check if process exists
    if pgrep -f "$script_name" >/dev/null; then
        return 0
    else
        return 1
    fi
}

# Start single monitoring task
start_monitor() {
    local monitor_name="$1"
    local script_name="${MONITOR_TASKS[$monitor_name]:-}"
    
    if [[ -z "$script_name" ]]; then
        echo "❌ Unknown monitoring task: $monitor_name"
        return 1
    fi
    
    if is_monitor_running "$monitor_name"; then
        echo "⚠️  Monitoring task $monitor_name is already running"
        return 0
    fi
    
    echo "🚀 Starting monitoring task: $monitor_name ($script_name)"
    
    # Get current script directory
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Start monitoring script
    case "$monitor_name" in
        "unified")
            # QPS test mode: no duration passed, run indefinitely
            # Clean log-related environment variables to ensure process isolation
            (
                unset LOGGER_COMPONENT  # Prevent log component identifier pollution
                cd "${script_dir}" && ./"${script_name}" -i "$MONITOR_INTERVAL"
            ) &
            ;;
        "block_height")
            # QPS test mode: no duration passed, run indefinitely
            # Set correct working directory and environment variables to ensure subprocess can load dependencies correctly
            (
                unset LOGGER_COMPONENT
                cd "${script_dir}" && ./"${script_name}" -b
            ) &
            ;;
        "iostat")
            # iostat functionality is managed by unified_monitor.sh to avoid duplicate startup
            echo "🔗 iostat functionality is managed by unified_monitor.sh"
            if is_monitor_running "unified"; then
                echo "✅ iostat functionality already started via unified_monitor.sh"
                # Verify iostat process is actually running
                if pgrep -f "iostat -dx [0-9]+" >/dev/null 2>&1; then
                    echo "✅ iostat process confirmed running"
                else
                    echo "⚠️  unified_monitor running but iostat process not detected, may be starting"
                fi
                return 0
            else
                echo "⚠️  Need to start unified monitor first to enable iostat functionality"
                echo "🚀 Auto-starting unified monitor..."
                start_monitor "unified"
                return $?
            fi
            ;;
        "ena_network")
            # ENA network monitor
            if [[ "$ENA_MONITOR_ENABLED" == "true" ]]; then
                # Use correct parameter format: start [duration] [interval]
                # duration=0 means continuous running
                (
                    unset LOGGER_COMPONENT
                    cd "${script_dir}" && ./"${script_name}" start 0 "$MONITOR_INTERVAL"
                ) &
            else
                echo "⚠️  ENA monitoring is disabled, skipping ena_network task"
                return 0
            fi
            ;;
        "ebs_bottleneck")
            # QPS test mode: no duration passed, run indefinitely
            # Set correct working directory and environment variables to ensure subprocess can load dependencies correctly
            (
                unset LOGGER_COMPONENT
                cd "${script_dir}/../tools" && ./"${script_name}" -b
            ) &
            ;;
        *)
            echo "❌ Unsupported monitoring task: $monitor_name"
            return 1
            ;;
    esac
    
    local pid=$!
    echo "$monitor_name:$pid" >> "$MONITOR_PIDS_FILE"
    
    # Update status file
    update_monitor_status "$monitor_name" "started" "$pid"
    
    echo "✅ Monitoring task $monitor_name started (PID: $pid)"
    return 0
}

# Stop single monitoring task
stop_monitor() {
    local monitor_name="$1"
    
    echo "🛑 Stopping monitoring task: $monitor_name"
    
    # Find PID from PID file
    local pid=$(grep "^$monitor_name:" "$MONITOR_PIDS_FILE" 2>/dev/null | cut -d: -f2)
    
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        echo "Stopping process $pid..."
        kill "$pid" 2>/dev/null
        sleep 3
        
        # Force terminate if still running
        if kill -0 "$pid" 2>/dev/null; then
            echo "Force terminating process $pid..."
            kill -9 "$pid" 2>/dev/null
        fi
        
        # Remove from PID file
        grep -v "^$monitor_name:" "$MONITOR_PIDS_FILE" > "${MONITOR_PIDS_FILE}.tmp" 2>/dev/null || true
        mv "${MONITOR_PIDS_FILE}.tmp" "$MONITOR_PIDS_FILE" 2>/dev/null || true
    fi
    
    # Find and stop process using script name
    local script_name="${MONITOR_TASKS[$monitor_name]:-}"
    if [[ -n "$script_name" ]]; then
        pkill -f "$script_name" 2>/dev/null || true
    fi
    
    # Update status file
    update_monitor_status "$monitor_name" "stopped" ""
    
    echo "✅ Monitoring task $monitor_name stopped"
}

# Start all monitoring tasks
start_all_monitors() {
    echo "🚀 Starting all monitoring tasks (monitoring interval: ${MONITOR_INTERVAL} seconds)"
    
    # Start monitoring tasks by priority - start all necessary monitoring scripts
    local monitors_to_start=("unified" "ena_network" "block_height" "ebs_bottleneck")
    
    for monitor in "${monitors_to_start[@]}"; do
        start_monitor "$monitor"
        sleep 1  # Avoid resource competition from simultaneous startup
    done
    
    echo "✅ All monitoring tasks startup completed"
    show_monitor_status
}

# Stop all monitoring tasks
stop_all_monitors() {
    echo "🛑 Stopping all monitoring tasks..."
    
    # Stop all known monitoring tasks
    for monitor in "${!MONITOR_TASKS[@]}"; do
        stop_monitor "$monitor"
    done
    
    # Additional cleanup: force terminate all related processes
    # Check if there are processes that need cleanup
    local processes_to_clean=""
    for script in "${MONITOR_TASKS[@]}"; do
        local pids=$(pgrep -f "$script" 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            processes_to_clean="$processes_to_clean $script"
        fi
    done
    
    # Only output logs and perform cleanup when there are processes to clean
    if [[ -n "$processes_to_clean" ]]; then
        echo "🧹 Cleaning up residual monitoring processes..."
        for script in "${MONITOR_TASKS[@]}"; do
            pkill -f "$script" 2>/dev/null || true
        done
        echo "✅ Cleaned up monitoring processes:$processes_to_clean"
    else
        echo "ℹ️  No monitoring processes found that need cleanup"
    fi
    
    # Stop iostat continuous sampling process (started by unified_monitor.sh)
    local iostat_pids=$(pgrep -f "iostat -dx [0-9]+" 2>/dev/null || true)
    if [[ -n "$iostat_pids" ]]; then
        echo "🧹 Cleaning up iostat processes..."
        pkill -f "iostat -dx [0-9]+" 2>/dev/null || true
        # Clean up iostat related temporary files
        rm -f /tmp/iostat_*.pid /tmp/iostat_*.data 2>/dev/null || true
        echo "✅ iostat processes cleaned up"
    else
        echo "ℹ️  No iostat processes found that need cleanup"
    fi
    
    # Clean up PID file
    > "$MONITOR_PIDS_FILE"
    
    echo "✅ All monitoring tasks stopped"
}

# Display monitoring status
show_monitor_status() {
    echo ""
    echo "📊 Monitoring Task Status:"
    echo "================================"
    
    for monitor in "${!MONITOR_TASKS[@]}"; do
        local script_name="${MONITOR_TASKS[$monitor]:-}"
        
        # Special handling for iostat task: show its management status via unified_monitor.sh
        if [[ "$monitor" == "iostat" ]]; then
            show_iostat_status
        else
            # Standard handling for other tasks
            if is_monitor_running "$monitor"; then
                local pid=$(pgrep -f "$script_name" | head -1)
                echo "✅ $monitor ($script_name) - Running (PID: $pid)"
            else
                echo "❌ $monitor ($script_name) - Stopped"
            fi
        fi
    done
    
    echo ""
    echo "📁 Monitoring Files:"
    echo "  Status file: $MONITOR_STATUS_FILE"
    echo "  PID file: $MONITOR_PIDS_FILE"
    echo "  Log directory: $LOGS_DIR"
}

# Display iostat detailed status
show_iostat_status() {
    echo "📊 iostat (iostat_collector.sh) - Managed by unified_monitor.sh"
    
    if is_monitor_running "unified"; then
        echo "  └─ unified_monitor: ✅ Running"
        
        # Check actual iostat process (Linux environment)
        if pgrep -f "iostat -dx [0-9]+" >/dev/null 2>&1; then
            local iostat_pid=$(pgrep -f "iostat -dx [0-9]+" | head -1)
            echo "  └─ iostat process: ✅ Running (PID: $iostat_pid)"
        else
            echo "  └─ iostat process: ⚠️  Not detected (may be in non-Linux environment or EBS device not configured)"
        fi
        
        # Check iostat data files
        if ls /tmp/iostat_*.data >/dev/null 2>&1; then
            local data_files=$(ls /tmp/iostat_*.data 2>/dev/null | wc -l)
            echo "  └─ Data files: ✅ $data_files device data files"
        else
            echo "  └─ Data files: ❌ Data files not found"
        fi
    else
        echo "  └─ unified_monitor: ❌ Not running"
        echo "  └─ iostat process: ❌ Not running"
    fi
}

# Update monitoring status
update_monitor_status() {
    local monitor_name="$1"
    local status="$2"
    local pid="$3"
    
    # Use jq to update JSON status file (if available and file exists)
    if command -v jq >/dev/null 2>&1 && [[ -f "$MONITOR_STATUS_FILE" ]]; then
        local temp_file="${MONITOR_STATUS_FILE}.tmp"
        if jq --arg name "$monitor_name" --arg status "$status" --arg pid "$pid" --arg time "$(date -Iseconds)" \
           '.active_monitors[$name] = {status: $status, pid: $pid, timestamp: $time}' \
           "$MONITOR_STATUS_FILE" > "$temp_file" 2>/dev/null; then
            mv "$temp_file" "$MONITOR_STATUS_FILE"
        else
            # If jq operation fails, clean up temporary file
            rm -f "$temp_file" 2>/dev/null
        fi
    fi
}

# Health check
health_check() {
    echo "🏥 Monitoring Coordinator Health Check"
    echo "================================"
    
    local healthy=true
    local total_monitors=0
    local running_monitors=0
    
    for monitor in "${!MONITOR_TASKS[@]}"; do
        total_monitors=$((total_monitors + 1))
        if is_monitor_running "$monitor"; then
            running_monitors=$((running_monitors + 1))
            echo "✅ $monitor - Healthy"
        else
            echo "❌ $monitor - Not running"
            healthy=false
        fi
    done
    
    echo ""
    echo "📊 Health Status Summary:"
    echo "  Total monitoring tasks: $total_monitors"
    echo "  Running: $running_monitors"
    echo "  Health score: $((running_monitors * 100 / total_monitors))%"
    
    if $healthy; then
        echo "🎉 All monitoring tasks running normally"
        return 0
    else
        echo "⚠️  Some monitoring tasks not running"
        return 1
    fi
}

# Cleanup status flag
CLEANUP_COMPLETED=false

# Cleanup function
cleanup_coordinator() {
    # Prevent duplicate cleanup
    if [[ "$CLEANUP_COMPLETED" == "true" ]]; then
        echo "ℹ️  Monitoring coordinator already cleaned up, skipping duplicate cleanup"
        return 0
    fi
    
    echo "🧹 Cleaning up monitoring coordinator..."
    stop_all_monitors
    
    # Enhanced cleanup: ensure all related processes are cleaned
    echo "🔍 Cleaning up possible orphan processes..."
    pkill -f "ebs_bottleneck_detector" 2>/dev/null || true
    pkill -f "ena_network_monitor" 2>/dev/null || true
    pkill -f "block_height_monitor" 2>/dev/null || true
    pkill -f "tail.*performance_latest.csv" 2>/dev/null || true

    # Clean up shared memory files
    if [[ -n "${MEMORY_SHARE_DIR:-}" ]] && [[ -d "$MEMORY_SHARE_DIR" ]]; then
        echo "🧹 Cleaning up shared memory files..."
        
        # Clean up monitoring related files
        rm -f "$MEMORY_SHARE_DIR"/latest_metrics.json 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/unified_metrics.json 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/block_height_monitor_cache.json 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/sample_count 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/*cache* 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/*.lock 2>/dev/null || true
        # Keep qps_status.json until framework final cleanup
        
        # Unified cleanup result feedback
        if [[ -z "$(ls -A "$MEMORY_SHARE_DIR" 2>/dev/null)" ]]; then
            rmdir "$MEMORY_SHARE_DIR" 2>/dev/null || true
            echo "✅ Shared memory directory completely cleaned up"
        else
            echo "✅ Shared memory monitoring files cleaned up"
        fi
    fi

    # Keep status file for debugging
    if [[ -f "$MONITOR_STATUS_FILE" ]]; then
        echo "📊 Monitoring status file retained: $MONITOR_STATUS_FILE"
    fi
    
    # Mark cleanup completed
    CLEANUP_COMPLETED=true
    echo "✅ Monitoring coordinator cleanup completed"
}

# Signal handling
trap cleanup_coordinator EXIT INT TERM

# Usage instructions
show_usage() {
    echo "Monitoring Coordinator - Unified Management of All Monitoring Tasks"
    echo ""
    echo "Usage: $0 [options] [command]"
    echo ""
    echo "Commands:"
    echo "  start                Start all monitoring tasks"
    echo "  stop                 Stop all monitoring tasks"
    echo "  status               Display monitoring status"
    echo "  health               Perform health check"
    echo "  start-monitor <name> Start specified monitoring task"
    echo "  stop-monitor <name>  Stop specified monitoring task"
    echo ""
    echo "Available monitoring tasks:"
    for monitor in "${!MONITOR_TASKS[@]}"; do
        echo "  $monitor - ${MONITOR_TASKS[$monitor]:-}"
    done
    echo ""
    echo "Options:"
    echo "  -h, --help          Display this help information"
    echo ""
    echo "Examples:"
    echo "  $0 start 1800       Start all monitoring tasks, duration 30 minutes"
    echo "  $0 start-monitor unified  Start unified monitor only"
    echo "  $0 status           View monitoring status"
    echo "  $0 health           Perform health check"
}

# Main function
main() {
    local command="${1:-status}"
    
    case "$command" in
        "start")
            init_coordinator
            start_all_monitors
            # Keep monitoring coordinator running, monitor subprocess status
            echo "🔄 Monitoring coordinator keeps running, monitoring subprocess status..."
            
            # Record start time
            local start_time=$(date +%s)
            
            # Function to check if QPS test is still running
            is_qps_test_running() {
                [[ -f "$TMP_DIR/qps_test_status" ]]
            }
            
            while true; do
                sleep 10
                local current_time=$(date +%s)
                local runtime=$((current_time - start_time))
                
                # 1. Priority check QPS test status
                if is_qps_test_running; then
                    echo "[ACTIVE] QPS test in progress, monitoring system continues running (runtime: ${runtime}s)"
                    continue  # QPS test still running, continue regardless of monitoring task status
                fi
                
                # 2. QPS test completed, check monitoring task status
                echo "[INFO] QPS test completed, checking monitoring task status..."
                
                # Check if there are any monitoring tasks running
                if [[ ! -f "$MONITOR_PIDS_FILE" ]] || [[ ! -s "$MONITOR_PIDS_FILE" ]]; then
                    echo "[INFO] No active monitoring tasks, monitoring coordinator exiting"
                    break
                fi
                
                # Check monitoring task status - enhanced robustness check
                local active_count=0
                echo "[CHECK] Checking monitoring task status (runtime: ${runtime}s):"
                
                # File existence and readability check
                if [[ ! -f "$MONITOR_PIDS_FILE" ]]; then
                    echo "  [WARN] PID file does not exist: $MONITOR_PIDS_FILE"
                    active_count=0
                elif [[ ! -r "$MONITOR_PIDS_FILE" ]]; then
                    echo "  [WARN] PID file is not readable: $MONITOR_PIDS_FILE"
                    active_count=0
                elif [[ ! -s "$MONITOR_PIDS_FILE" ]]; then
                    echo "  [WARN] PID file is empty: $MONITOR_PIDS_FILE"
                    active_count=0
                else
                    # Safe reading and format validation
                    while IFS=':' read -r monitor_name pid; do
                        if [[ -n "$monitor_name" && -n "$pid" && "$pid" =~ ^[0-9]+$ ]]; then
                            if kill -0 "$pid" 2>/dev/null; then
                                echo "  [OK] $monitor_name (PID: $pid) - running"
                                ((active_count++))
                            else
                                echo "  [STOP] $monitor_name (PID: $pid) - stopped"
                            fi
                        else
                            echo "  [WARN] Invalid PID file format: '$monitor_name:$pid'"
                        fi
                    done < "$MONITOR_PIDS_FILE"
                fi
                
                echo "  [STAT] Active task count: $active_count"
                
                if [[ $active_count -eq 0 ]]; then
                    echo "[INFO] All monitoring tasks stopped, waiting for graceful cleanup..."
                    sleep 3
                    echo "[INFO] QPS test completed and all monitoring tasks finished, monitoring coordinator exiting"
                    break
                fi
            done
            ;;
        "start_all")
            # New: Unified startup entry for QPS test framework
            init_coordinator
            echo "[START] Starting all monitoring tasks (QPS test mode)"
            start_monitor "unified" "${2:-follow_qps_test}"
            start_monitor "block_height" "${2:-follow_qps_test}"
            start_monitor "bottleneck" "${2:-follow_qps_test}"
            echo "[OK] All monitoring tasks started"
            ;;
        "stop")
            stop_all_monitors
            ;;
        "status")
            show_monitor_status
            ;;
        "health")
            health_check
            ;;
        "start-monitor")
            if [[ -z "$2" ]]; then
                echo "❌ Please specify monitoring task name"
                show_usage
                exit 1
            fi
            init_coordinator
            start_monitor "$2"
            ;;
        "stop-monitor")
            if [[ -z "$2" ]]; then
                echo "❌ Please specify monitoring task name"
                show_usage
                exit 1
            fi
            stop_monitor "$2"
            ;;
        "-h"|"--help"|"help")
            show_usage
            ;;
        *)
            echo "❌ Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# If this script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

log_script_success "$(basename "$0")"
