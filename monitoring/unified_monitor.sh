#!/bin/bash
# 统一监控脚本 - 简化版本，修复编码和语法问题

set -euo pipefail

# 获取脚本目录
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"

# 加载配置和工具
source "$SCRIPT_DIR/../config/config.sh"
source "$SCRIPT_DIR/../utils/unified_logger.sh"

# 全局变量
START_TIME=""
SAMPLE_COUNT=0

# 初始化监控环境
init_monitoring() {
    echo "[INIT] 初始化统一监控环境..."
    
    # 验证配置
    if [[ -z "${LOGS_DIR:-}" ]]; then
        echo "[ERROR] LOGS_DIR未配置"
        return 1
    fi
    
    # 创建日志目录
    mkdir -p "$LOGS_DIR"
    
    echo "[OK] 监控环境初始化完成"
    return 0
}

# 收集系统数据
collect_system_data() {
    local timestamp="$1"
    
    # 跨平台系统信息收集
    local cpu_usage="0"
    local mem_usage="0"
    
    # 检测操作系统
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        cpu_usage=$(top -l 1 -n 0 | grep "CPU usage" | awk '{print $3}' | sed 's/%//' 2>/dev/null || echo "0")
        mem_usage=$(top -l 1 -n 0 | grep "PhysMem" | awk '{print $2}' | sed 's/M//' 2>/dev/null || echo "0")
    else
        # Linux
        cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2 + $4}' 2>/dev/null || echo "0")
        mem_usage=$(free -m 2>/dev/null | awk '/Mem:/ {print $3}' || echo "0")
    fi
    
    # 输出数据
    echo "$timestamp,$cpu_usage,$mem_usage"
}

# 主监控循环
run_monitoring_loop() {
    local interval="${1:-10}"
    local duration="${2:-0}"
    
    echo "[START] 启动监控循环，间隔: ${interval}s"
    
    local start_time=$(date +%s)
    local sample_count=0
    
    # 创建CSV文件
    local csv_file="$LOGS_DIR/unified_monitor_$(date +%Y%m%d_%H%M%S).csv"
    echo "timestamp,cpu_usage,mem_usage" > "$csv_file"
    
    if [[ "$duration" -eq 0 ]]; then
        # 无限循环模式
        while true; do
            local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
            local data=$(collect_system_data "$timestamp")
            echo "$data" >> "$csv_file"
            
            sample_count=$((sample_count + 1))
            
            # 进度报告
            if (( sample_count % 12 == 0 )); then
                local current_time=$(date +%s)
                local elapsed=$((current_time - start_time))
                echo "[PROGRESS] Collected $sample_count samples, running ${elapsed}s"
            fi
            
            sleep "$interval"
        done
    else
        # 固定时长模式
        local end_time=$((start_time + duration))
        
        while [[ $(date +%s) -lt $end_time ]]; do
            local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
            local data=$(collect_system_data "$timestamp")
            echo "$data" >> "$csv_file"
            
            sample_count=$((sample_count + 1))
            
            # 进度报告
            if (( sample_count % 12 == 0 )); then
                local current_time=$(date +%s)
                local elapsed=$((current_time - start_time))
                local remaining=$((end_time - current_time))
                echo "[PROGRESS] Collected $sample_count samples, running ${elapsed}s, remaining ${remaining}s"
            fi
            
            sleep "$interval"
        done
    fi
    
    echo "[OK] 监控完成，共收集 $sample_count 个样本"
    echo "[INFO] 数据文件: $csv_file"
}

# 显示帮助信息
show_help() {
    cat << EOF
统一性能监控器

用法: $0 [选项]

选项:
  -i, --interval SECONDS    监控间隔 (默认: 10秒)
  -d, --duration SECONDS    运行时长 (默认: 无限)
  -h, --help               显示此帮助信息

示例:
  $0 -i 5                  每5秒采样一次
  $0 -i 10 -d 300          每10秒采样一次，运行5分钟
EOF
}

# 主函数
main() {
    echo "[INIT] 统一性能监控器"
    echo "=================="
    echo ""
    
    local interval=10
    local duration=0
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -i|--interval)
                interval="$2"
                shift 2
                ;;
            -d|--duration)
                duration="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                echo "[ERROR] 未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # 验证参数
    if ! [[ "$interval" =~ ^[0-9]+$ ]] || [[ "$interval" -lt 1 ]]; then
        echo "[ERROR] 无效的监控间隔: $interval"
        exit 1
    fi
    
    if ! [[ "$duration" =~ ^[0-9]+$ ]]; then
        echo "[ERROR] 无效的运行时长: $duration"
        exit 1
    fi
    
    # 初始化监控环境
    if ! init_monitoring; then
        echo "[ERROR] 监控环境初始化失败"
        exit 1
    fi
    
    # 启动监控循环
    run_monitoring_loop "$interval" "$duration"
}

# 信号处理
cleanup() {
    echo ""
    echo "[INFO] 收到退出信号，正在清理..."
    exit 0
}

trap cleanup SIGINT SIGTERM

# 执行主函数
main "$@"