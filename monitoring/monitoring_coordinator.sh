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

# 监控状态文件 - 防止重复定义
if [[ -z "${MONITOR_STATUS_FILE:-}" ]]; then
    readonly MONITOR_STATUS_FILE="${TMP_DIR}/monitoring_status.json"
    readonly MONITOR_PIDS_FILE="${TMP_DIR}/monitor_pids.txt"
fi

# 监控任务定义 - 包含所有必要的监控脚本
declare -A MONITOR_TASKS=(
    ["unified"]="unified_monitor.sh"
    ["slot"]="slot_monitor.sh"
    ["iostat"]="iostat_collector.sh"
    ["ena_network"]="ena_network_monitor.sh"
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
            # 设置正确的工作目录和环境变量，确保子进程能正确加载依赖
            (cd "${script_dir}" && ./"${script_name}" -i "$MONITOR_INTERVAL") &
            ;;
        "slot")
            # QPS测试模式：不传递duration，无限运行
            # 设置正确的工作目录和环境变量，确保子进程能正确加载依赖
            (cd "${script_dir}" && ./"${script_name}" -b) &
            ;;
        "iostat")
            # iostat收集器 - 独立运行模式，生成自己的CSV文件
            # 注意：这个脚本目前只有测试模式，需要添加持续监控模式
            echo "⚠️  iostat_collector.sh 需要持续监控模式支持"
            return 1
            ;;
        "ena_network")
            # ENA网络监控器 - 独立运行模式
            if [[ "$ENA_MONITOR_ENABLED" == "true" ]]; then
                (cd "${script_dir}" && ./"${script_name}" start -i "$MONITOR_INTERVAL") &
            else
                echo "⚠️  ENA监控已禁用，跳过ena_network任务"
                return 0
            fi
            ;;
        "ebs_bottleneck")
            # QPS测试模式：不传递duration，无限运行
            # 设置正确的工作目录和环境变量，确保子进程能正确加载依赖
            (cd "${script_dir}/../tools" && ./"${script_name}" -b) &
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
    echo "🚀 启动所有监控任务 (监控间隔: ${MONITOR_INTERVAL}秒)"
    
    # 按优先级启动监控任务 - 启动所有必要的监控脚本
    local monitors_to_start=("unified" "iostat" "ena_network" "slot" "ebs_bottleneck")
    
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
    echo "  start                启动所有监控任务"
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
            start_all_monitors
            # 保持监控协调器运行，监控子进程状态
            echo "🔄 监控协调器保持运行，监控子进程状态..."
            
            # 记录启动时间
            local start_time=$(date +%s)
            
            # 检查QPS测试是否还在运行的函数
            is_qps_test_running() {
                # 检查QPS测试状态标记文件
                if [[ -f "$TMP_DIR/qps_test_status" ]]; then
                    return 0  # QPS测试还在运行
                fi
                
                # 检查master_qps_executor进程
                if pgrep -f "master_qps_executor" >/dev/null 2>&1; then
                    return 0  # QPS测试还在运行
                fi
                
                # 检查vegeta进程
                if pgrep -f "vegeta" >/dev/null 2>&1; then
                    return 0  # QPS测试还在运行
                fi
                
                return 1  # QPS测试已结束
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
            start_monitor "slot" "${2:-follow_qps_test}"
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
