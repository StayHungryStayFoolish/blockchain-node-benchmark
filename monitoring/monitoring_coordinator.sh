#!/bin/bash
# =====================================================================
# 监控协调器 - 消除监控脚本重复，统一管理所有监控任务
# =====================================================================
# 这个脚本整合了所有监控功能，避免重复启动监控进程
# 提供统一的监控启动、停止和状态管理
# =====================================================================

# 加载错误处理和配置
source "$(dirname "${BASH_SOURCE[0]}")/../utils/error_handler.sh"
# 安全加载配置文件，避免readonly变量冲突
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "警告: 配置文件加载失败，使用默认配置"
    MONITOR_INTERVAL=${MONITOR_INTERVAL:-5}
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi

setup_error_handling "$(basename "$0")" "监控协调器"
log_script_start "$(basename "$0")"

# 监控状态文件 - 优先使用环境变量，否则使用默认值
if [[ -z "${MONITOR_STATUS_FILE:-}" ]]; then
    readonly MONITOR_STATUS_FILE="${TMP_DIR}/monitoring_status.json"
fi
if [[ -z "${MONITOR_PIDS_FILE:-}" ]]; then
    readonly MONITOR_PIDS_FILE="${TMP_DIR}/monitor_pids.txt"
fi

# 监控任务定义 - 包含所有必要的监控脚本
# 注意：iostat功能由unified_monitor.sh统一管理，避免重复启动和进程冲突
# 用户仍可通过 'start iostat' 命令启动，但会自动重定向到unified_monitor.sh
declare -A MONITOR_TASKS=(
    ["unified"]="unified_monitor.sh"
    ["block_height"]="block_height_monitor.sh"
    ["ena_network"]="ena_network_monitor.sh"
    ["ebs_bottleneck"]="ebs_bottleneck_detector.sh"
    ["iostat"]="iostat_collector.sh"  # 通过unified_monitor.sh管理
)

# 初始化监控协调器
init_coordinator() {
    echo "🔧 初始化监控协调器..."
    
    # 创建必要的目录
    mkdir -p "${TMP_DIR}" "${LOGS_DIR}"
    
    # 初始化状态文件
    cat > "$MONITOR_STATUS_FILE" << EOF
{
    "coordinator_start_time": "$(date -Iseconds)",
    "active_monitors": {},
    "total_monitors_started": 0,
    "total_monitors_stopped": 0
}
EOF
    
    # 清空PID文件
    > "$MONITOR_PIDS_FILE"
    
    echo "✅ 监控协调器初始化完成"
}

# 检查监控任务是否已运行
is_monitor_running() {
    local monitor_name="$1"
    local script_name="${MONITOR_TASKS[$monitor_name]:-}"
    
    if [[ -z "$script_name" ]]; then
        echo "❌ 未知的监控任务: $monitor_name"
        return 1
    fi
    
    # 检查进程是否存在
    if pgrep -f "$script_name" >/dev/null; then
        return 0
    else
        return 1
    fi
}

# 启动单个监控任务
start_monitor() {
    local monitor_name="$1"
    local script_name="${MONITOR_TASKS[$monitor_name]:-}"
    
    if [[ -z "$script_name" ]]; then
        echo "❌ 未知的监控任务: $monitor_name"
        return 1
    fi
    
    if is_monitor_running "$monitor_name"; then
        echo "⚠️  监控任务 $monitor_name 已在运行"
        return 0
    fi
    
    echo "🚀 启动监控任务: $monitor_name ($script_name)"
    
    # 获取当前脚本所在目录
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # 启动监控脚本
    case "$monitor_name" in
        "unified")
            # QPS测试模式：不传递duration，无限运行
            # 清理日志相关环境变量，确保进程隔离
            (
                unset LOGGER_COMPONENT  # 防止日志组件标识污染
                cd "${script_dir}" && ./"${script_name}" -i "$MONITOR_INTERVAL"
            ) &
            ;;
        "block_height")
            # QPS测试模式：不传递duration，无限运行
            # 设置正确的工作目录和环境变量，确保子进程能正确加载依赖
            (
                unset LOGGER_COMPONENT
                cd "${script_dir}" && ./"${script_name}" -b
            ) &
            ;;
        "iostat")
            # iostat功能由unified_monitor.sh统一管理，避免重复启动
            echo "🔗 iostat功能由unified_monitor.sh统一管理"
            if is_monitor_running "unified"; then
                echo "✅ iostat功能已通过unified_monitor.sh启动"
                # 验证iostat进程是否真正运行
                if pgrep -f "iostat -dx [0-9]+" >/dev/null 2>&1; then
                    echo "✅ iostat进程确认运行中"
                else
                    echo "⚠️  unified_monitor运行中但iostat进程未检测到，可能正在启动"
                fi
                return 0
            else
                echo "⚠️  需要先启动unified监控器以启用iostat功能"
                echo "🚀 自动启动unified监控器..."
                start_monitor "unified"
                return $?
            fi
            ;;
        "ena_network")
            # ENA网络监控器
            if [[ "$ENA_MONITOR_ENABLED" == "true" ]]; then
                # 使用正确的参数格式：start [duration] [interval]
                # duration=0 表示持续运行
                (
                    unset LOGGER_COMPONENT
                    cd "${script_dir}" && ./"${script_name}" start 0 "$MONITOR_INTERVAL"
                ) &
            else
                echo "⚠️  ENA监控已禁用，跳过ena_network任务"
                return 0
            fi
            ;;
        "ebs_bottleneck")
            # QPS测试模式：不传递duration，无限运行
            # 设置正确的工作目录和环境变量，确保子进程能正确加载依赖
            (
                unset LOGGER_COMPONENT
                cd "${script_dir}/../tools" && ./"${script_name}" -b
            ) &
            ;;
        *)
            echo "❌ 不支持的监控任务: $monitor_name"
            return 1
            ;;
    esac
    
    local pid=$!
    echo "$monitor_name:$pid" >> "$MONITOR_PIDS_FILE"
    
    # 更新状态文件
    update_monitor_status "$monitor_name" "started" "$pid"
    
    echo "✅ 监控任务 $monitor_name 已启动 (PID: $pid)"
    return 0
}

# 停止单个监控任务
stop_monitor() {
    local monitor_name="$1"
    
    echo "🛑 停止监控任务: $monitor_name"
    
    # 从PID文件中查找PID
    local pid=$(grep "^$monitor_name:" "$MONITOR_PIDS_FILE" 2>/dev/null | cut -d: -f2)
    
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        echo "正在停止进程 $pid..."
        kill "$pid" 2>/dev/null
        sleep 3
        
        # 如果还在运行，强制终止
        if kill -0 "$pid" 2>/dev/null; then
            echo "强制终止进程 $pid..."
            kill -9 "$pid" 2>/dev/null
        fi
        
        # 从PID文件中移除
        grep -v "^$monitor_name:" "$MONITOR_PIDS_FILE" > "${MONITOR_PIDS_FILE}.tmp" 2>/dev/null || true
        mv "${MONITOR_PIDS_FILE}.tmp" "$MONITOR_PIDS_FILE" 2>/dev/null || true
    fi
    
    # 使用脚本名称查找并停止进程
    local script_name="${MONITOR_TASKS[$monitor_name]:-}"
    if [[ -n "$script_name" ]]; then
        pkill -f "$script_name" 2>/dev/null || true
    fi
    
    # 更新状态文件
    update_monitor_status "$monitor_name" "stopped" ""
    
    echo "✅ 监控任务 $monitor_name 已停止"
}

# 启动所有监控任务
start_all_monitors() {
    echo "🚀 启动所有监控任务 (监控间隔: ${MONITOR_INTERVAL}秒)"
    
    # 按优先级启动监控任务 - 启动所有必要的监控脚本
    local monitors_to_start=("unified" "ena_network" "block_height" "ebs_bottleneck")
    
    for monitor in "${monitors_to_start[@]}"; do
        start_monitor "$monitor"
        sleep 1  # 避免同时启动造成资源竞争
    done
    
    echo "✅ 所有监控任务启动完成"
    show_monitor_status
}

# 停止所有监控任务
stop_all_monitors() {
    echo "🛑 停止所有监控任务..."
    
    # 停止所有已知的监控任务
    for monitor in "${!MONITOR_TASKS[@]}"; do
        stop_monitor "$monitor"
    done
    
    # 额外清理：强制终止所有相关进程
    # 检查是否有进程需要清理
    local processes_to_clean=""
    for script in "${MONITOR_TASKS[@]}"; do
        local pids=$(pgrep -f "$script" 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            processes_to_clean="$processes_to_clean $script"
        fi
    done
    
    # 只有在有进程需要清理时才输出日志和执行清理
    if [[ -n "$processes_to_clean" ]]; then
        echo "🧹 清理残留的监控进程..."
        for script in "${MONITOR_TASKS[@]}"; do
            pkill -f "$script" 2>/dev/null || true
        done
        echo "✅ 清理了监控进程:$processes_to_clean"
    else
        echo "ℹ️  没有发现需要清理的监控进程"
    fi
    
    # 停止iostat持续采样进程（由unified_monitor.sh启动）
    local iostat_pids=$(pgrep -f "iostat -dx [0-9]+" 2>/dev/null || true)
    if [[ -n "$iostat_pids" ]]; then
        echo "🧹 清理iostat进程..."
        pkill -f "iostat -dx [0-9]+" 2>/dev/null || true
        # 清理iostat相关的临时文件
        rm -f /tmp/iostat_*.pid /tmp/iostat_*.data 2>/dev/null || true
        echo "✅ iostat进程已清理"
    else
        echo "ℹ️  没有发现需要清理的iostat进程"
    fi
    
    # 清理PID文件
    > "$MONITOR_PIDS_FILE"
    
    echo "✅ 所有监控任务已停止"
}

# 显示监控状态
show_monitor_status() {
    echo ""
    echo "📊 监控任务状态:"
    echo "================================"
    
    for monitor in "${!MONITOR_TASKS[@]}"; do
        local script_name="${MONITOR_TASKS[$monitor]:-}"
        
        # iostat任务特殊处理：显示其通过unified_monitor.sh的管理状态
        if [[ "$monitor" == "iostat" ]]; then
            show_iostat_status
        else
            # 其他任务的标准处理
            if is_monitor_running "$monitor"; then
                local pid=$(pgrep -f "$script_name" | head -1)
                echo "✅ $monitor ($script_name) - 运行中 (PID: $pid)"
            else
                echo "❌ $monitor ($script_name) - 已停止"
            fi
        fi
    done
    
    echo ""
    echo "📁 监控文件:"
    echo "  状态文件: $MONITOR_STATUS_FILE"
    echo "  PID文件: $MONITOR_PIDS_FILE"
    echo "  日志目录: $LOGS_DIR"
}

# 显示iostat详细状态
show_iostat_status() {
    echo "📊 iostat (iostat_collector.sh) - 通过unified_monitor.sh管理"
    
    if is_monitor_running "unified"; then
        echo "  └─ unified_monitor: ✅ 运行中"
        
        # 检查真正的iostat进程（Linux环境）
        if pgrep -f "iostat -dx [0-9]+" >/dev/null 2>&1; then
            local iostat_pid=$(pgrep -f "iostat -dx [0-9]+" | head -1)
            echo "  └─ iostat进程: ✅ 运行中 (PID: $iostat_pid)"
        else
            echo "  └─ iostat进程: ⚠️  未检测到 (可能在非Linux环境或未配置EBS设备)"
        fi
        
        # 检查iostat数据文件
        if ls /tmp/iostat_*.data >/dev/null 2>&1; then
            local data_files=$(ls /tmp/iostat_*.data 2>/dev/null | wc -l)
            echo "  └─ 数据文件: ✅ $data_files 个设备数据文件"
        else
            echo "  └─ 数据文件: ❌ 未找到数据文件"
        fi
    else
        echo "  └─ unified_monitor: ❌ 未运行"
        echo "  └─ iostat进程: ❌ 未运行"
    fi
}

# 更新监控状态
update_monitor_status() {
    local monitor_name="$1"
    local status="$2"
    local pid="$3"
    
    # 使用jq更新JSON状态文件（如果可用且文件存在）
    if command -v jq >/dev/null 2>&1 && [[ -f "$MONITOR_STATUS_FILE" ]]; then
        local temp_file="${MONITOR_STATUS_FILE}.tmp"
        if jq --arg name "$monitor_name" --arg status "$status" --arg pid "$pid" --arg time "$(date -Iseconds)" \
           '.active_monitors[$name] = {status: $status, pid: $pid, timestamp: $time}' \
           "$MONITOR_STATUS_FILE" > "$temp_file" 2>/dev/null; then
            mv "$temp_file" "$MONITOR_STATUS_FILE"
        else
            # 如果jq操作失败，清理临时文件
            rm -f "$temp_file" 2>/dev/null
        fi
    fi
}

# 健康检查
health_check() {
    echo "🏥 监控协调器健康检查"
    echo "================================"
    
    local healthy=true
    local total_monitors=0
    local running_monitors=0
    
    for monitor in "${!MONITOR_TASKS[@]}"; do
        total_monitors=$((total_monitors + 1))
        if is_monitor_running "$monitor"; then
            running_monitors=$((running_monitors + 1))
            echo "✅ $monitor - 健康"
        else
            echo "❌ $monitor - 未运行"
            healthy=false
        fi
    done
    
    echo ""
    echo "📊 健康状态摘要:"
    echo "  总监控任务: $total_monitors"
    echo "  运行中: $running_monitors"
    echo "  健康度: $((running_monitors * 100 / total_monitors))%"
    
    if $healthy; then
        echo "🎉 所有监控任务运行正常"
        return 0
    else
        echo "⚠️  部分监控任务未运行"
        return 1
    fi
}

# 清理状态标记
CLEANUP_COMPLETED=false

# 清理函数
cleanup_coordinator() {
    # 防止重复清理
    if [[ "$CLEANUP_COMPLETED" == "true" ]]; then
        echo "ℹ️  监控协调器已清理，跳过重复清理"
        return 0
    fi
    
    echo "🧹 清理监控协调器..."
    stop_all_monitors
    
    # 增强清理：确保所有相关进程被清理
    echo "🔍 清理可能的孤儿进程..."
    pkill -f "ebs_bottleneck_detector" 2>/dev/null || true
    pkill -f "ena_network_monitor" 2>/dev/null || true
    pkill -f "block_height_monitor" 2>/dev/null || true
    pkill -f "tail.*performance_latest.csv" 2>/dev/null || true

    # 清理共享内存文件
    if [[ -n "${MEMORY_SHARE_DIR:-}" ]] && [[ -d "$MEMORY_SHARE_DIR" ]]; then
        echo "🧹 清理共享内存文件..."
        
        # 清理所有监控相关文件
        rm -f "$MEMORY_SHARE_DIR"/*.json 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/sample_count 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/*cache* 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/*.lock 2>/dev/null || true
        
        # 统一的清理结果反馈
        if [[ -z "$(ls -A "$MEMORY_SHARE_DIR" 2>/dev/null)" ]]; then
            rmdir "$MEMORY_SHARE_DIR" 2>/dev/null || true
            echo "✅ 共享内存目录已完全清理"
        else
            echo "✅ 共享内存监控文件已清理"
        fi
    fi

    # 保留状态文件用于调试
    if [[ -f "$MONITOR_STATUS_FILE" ]]; then
        echo "📊 监控状态文件保留: $MONITOR_STATUS_FILE"
    fi
    
    # 标记清理完成
    CLEANUP_COMPLETED=true
    echo "✅ 监控协调器清理完成"
}

# 信号处理
trap cleanup_coordinator EXIT INT TERM

# 使用说明
show_usage() {
    echo "监控协调器 - 统一管理所有监控任务"
    echo ""
    echo "用法: $0 [选项] [命令]"
    echo ""
    echo "命令:"
    echo "  start                启动所有监控任务"
    echo "  stop                 停止所有监控任务"
    echo "  status               显示监控状态"
    echo "  health               执行健康检查"
    echo "  start-monitor <name> 启动指定监控任务"
    echo "  stop-monitor <name>  停止指定监控任务"
    echo ""
    echo "可用的监控任务:"
    for monitor in "${!MONITOR_TASKS[@]}"; do
        echo "  $monitor - ${MONITOR_TASKS[$monitor]:-}"
    done
    echo ""
    echo "选项:"
    echo "  -h, --help          显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 start 1800       启动所有监控任务，持续30分钟"
    echo "  $0 start-monitor unified  只启动统一监控器"
    echo "  $0 status           查看监控状态"
    echo "  $0 health           执行健康检查"
}

# 主函数
main() {
    local command="${1:-status}"
    
    case "$command" in
        "start")
            init_coordinator
            start_all_monitors
            # 保持监控协调器运行，监控子进程状态
            echo "🔄 监控协调器保持运行，监控子进程状态..."
            
            # 记录启动时间
            local start_time=$(date +%s)
            
            # 检查QPS测试是否还在运行的函数
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
                echo "❌ 请指定监控任务名称"
                show_usage
                exit 1
            fi
            init_coordinator
            start_monitor "$2"
            ;;
        "stop-monitor")
            if [[ -z "$2" ]]; then
                echo "❌ 请指定监控任务名称"
                show_usage
                exit 1
            fi
            stop_monitor "$2"
            ;;
        "-h"|"--help"|"help")
            show_usage
            ;;
        *)
            echo "❌ 未知命令: $command"
            show_usage
            exit 1
            ;;
    esac
}

# 如果直接执行此脚本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

log_script_success "$(basename "$0")"
