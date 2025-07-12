#!/bin/bash
# =====================================================================
# 监控协调器 - 消除监控脚本重复，统一管理所有监控任务
# =====================================================================
# 这个脚本整合了所有监控功能，避免重复启动监控进程
# 提供统一的监控启动、停止和状态管理
# =====================================================================

# 加载错误处理和配置
source "$(dirname "$0")/../utils/error_handler.sh"
source "$(dirname "$0")/../config/config.sh"

setup_error_handling "$(basename "$0")" "监控协调器"
log_script_start "$(basename "$0")"

# 监控状态文件
readonly MONITOR_STATUS_FILE="${TMP_DIR}/monitoring_status.json"
readonly MONITOR_PIDS_FILE="${TMP_DIR}/monitor_pids.txt"

# 监控任务定义
declare -A MONITOR_TASKS=(
    ["unified"]="unified_monitor.sh"
    ["slot"]="slot_monitor.sh"
    ["bottleneck"]="bottleneck_detector.sh"
    ["ebs_bottleneck"]="ebs_bottleneck_detector.sh"
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
    local script_name="${MONITOR_TASKS[$monitor_name]}"
    
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
    local script_name="${MONITOR_TASKS[$monitor_name]}"
    local duration="${2:-$DEFAULT_MONITOR_DURATION}"
    
    if [[ -z "$script_name" ]]; then
        echo "❌ 未知的监控任务: $monitor_name"
        return 1
    fi
    
    if is_monitor_running "$monitor_name"; then
        echo "⚠️  监控任务 $monitor_name 已在运行"
        return 0
    fi
    
    echo "🚀 启动监控任务: $monitor_name ($script_name)"
    
    # 启动监控脚本
    case "$monitor_name" in
        "unified")
            ./"$script_name" -d "$duration" -i "$MONITOR_INTERVAL" &
            ;;
        "slot")
            ./"$script_name" -d "$duration" &
            ;;
        "bottleneck")
            ./"$script_name" -d "$duration" &
            ;;
        "ebs_bottleneck")
            ./"$script_name" -d "$duration" &
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
        sleep 2
        
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
    local script_name="${MONITOR_TASKS[$monitor_name]}"
    if [[ -n "$script_name" ]]; then
        pkill -f "$script_name" 2>/dev/null || true
    fi
    
    # 更新状态文件
    update_monitor_status "$monitor_name" "stopped" ""
    
    echo "✅ 监控任务 $monitor_name 已停止"
}

# 启动所有监控任务
start_all_monitors() {
    local duration="${1:-$DEFAULT_MONITOR_DURATION}"
    
    echo "🚀 启动所有监控任务 (持续时间: ${duration}秒)"
    
    # 按优先级启动监控任务
    local monitors_to_start=("unified" "slot" "bottleneck" "ebs_bottleneck")
    
    for monitor in "${monitors_to_start[@]}"; do
        start_monitor "$monitor" "$duration"
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
    echo "🧹 清理残留的监控进程..."
    for script in "${MONITOR_TASKS[@]}"; do
        pkill -f "$script" 2>/dev/null || true
    done
    
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
        local script_name="${MONITOR_TASKS[$monitor]}"
        if is_monitor_running "$monitor"; then
            local pid=$(pgrep -f "$script_name" | head -1)
            echo "✅ $monitor ($script_name) - 运行中 (PID: $pid)"
        else
            echo "❌ $monitor ($script_name) - 已停止"
        fi
    done
    
    echo ""
    echo "📁 监控文件:"
    echo "  状态文件: $MONITOR_STATUS_FILE"
    echo "  PID文件: $MONITOR_PIDS_FILE"
    echo "  日志目录: $LOGS_DIR"
}

# 更新监控状态
update_monitor_status() {
    local monitor_name="$1"
    local status="$2"
    local pid="$3"
    
    # 使用jq更新JSON状态文件（如果可用）
    if command -v jq >/dev/null 2>&1; then
        local temp_file="${MONITOR_STATUS_FILE}.tmp"
        jq --arg name "$monitor_name" --arg status "$status" --arg pid "$pid" --arg time "$(date -Iseconds)" \
           '.active_monitors[$name] = {status: $status, pid: $pid, timestamp: $time}' \
           "$MONITOR_STATUS_FILE" > "$temp_file" && mv "$temp_file" "$MONITOR_STATUS_FILE"
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

# 清理函数
cleanup_coordinator() {
    echo "🧹 清理监控协调器..."
    stop_all_monitors
    
    # 保留状态文件用于调试
    if [[ -f "$MONITOR_STATUS_FILE" ]]; then
        echo "📊 监控状态文件保留: $MONITOR_STATUS_FILE"
    fi
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
    echo "  start [duration]     启动所有监控任务"
    echo "  stop                 停止所有监控任务"
    echo "  status               显示监控状态"
    echo "  health               执行健康检查"
    echo "  start-monitor <name> 启动指定监控任务"
    echo "  stop-monitor <name>  停止指定监控任务"
    echo ""
    echo "可用的监控任务:"
    for monitor in "${!MONITOR_TASKS[@]}"; do
        echo "  $monitor - ${MONITOR_TASKS[$monitor]}"
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
            start_all_monitors "${2:-$DEFAULT_MONITOR_DURATION}"
            ;;
        "start_all")
            # 新增：为QPS测试框架提供的统一启动入口
            init_coordinator
            echo "🚀 启动所有监控任务 (QPS测试模式)"
            start_monitor "unified" "${2:-follow_qps_test}"
            start_monitor "slot" "${2:-follow_qps_test}"
            start_monitor "bottleneck" "${2:-follow_qps_test}"
            echo "✅ 所有监控任务已启动"
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
            start_monitor "$2" "${3:-$DEFAULT_MONITOR_DURATION}"
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
