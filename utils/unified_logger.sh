#!/bin/bash
# =====================================================================
# 统一日志管理器 - Unified Logger
# =====================================================================
# 提供统一的日志配置、格式化、轮转和管理功能
# 解决项目中日志配置不统一的问题
# =====================================================================

# 防止重复加载 - 但在子进程中需要重新加载函数定义
if [[ "${UNIFIED_LOGGER_LOADED:-false}" == "true" ]] && [[ "$(type -t init_logger)" == "function" ]]; then
    return 0
fi

# 引入配置
source "$(dirname "${BASH_SOURCE[0]}")/../config/config.sh"

# =====================================================================
# 日志配置常量
# =====================================================================

# 日志级别定义
readonly LOG_LEVEL_DEBUG=0
readonly LOG_LEVEL_INFO=1
readonly LOG_LEVEL_WARN=2
readonly LOG_LEVEL_ERROR=3
readonly LOG_LEVEL_FATAL=4

# 日志级别名称映射 (兼容macOS)
LOG_LEVEL_NAMES_0="DEBUG"
LOG_LEVEL_NAMES_1="INFO"
LOG_LEVEL_NAMES_2="WARN"
LOG_LEVEL_NAMES_3="ERROR"
LOG_LEVEL_NAMES_4="FATAL"

# 颜色定义
readonly COLOR_RESET='\033[0m'
readonly COLOR_RED='\033[0;31m'
readonly COLOR_GREEN='\033[0;32m'
readonly COLOR_YELLOW='\033[0;33m'
readonly COLOR_BLUE='\033[0;34m'
readonly COLOR_PURPLE='\033[0;35m'
readonly COLOR_CYAN='\033[0;36m'
readonly COLOR_WHITE='\033[0;37m'

# 日志级别颜色映射 (兼容macOS)
LOG_LEVEL_COLORS_0="\033[0;36m"    # 青色 - DEBUG
LOG_LEVEL_COLORS_1="\033[0;32m"    # 绿色 - INFO
LOG_LEVEL_COLORS_2="\033[0;33m"    # 黄色 - WARN
LOG_LEVEL_COLORS_3="\033[0;31m"    # 红色 - ERROR
LOG_LEVEL_COLORS_4="\033[0;35m"    # 紫色 - FATAL

# 默认配置
DEFAULT_LOG_LEVEL=${LOG_LEVEL:-$LOG_LEVEL_INFO}
DEFAULT_LOG_FORMAT="${LOG_FORMAT:-"[%timestamp%] [%level%] [%component%] %message%"}"
DEFAULT_MAX_LOG_SIZE="${MAX_LOG_SIZE:-10M}"
DEFAULT_MAX_LOG_FILES="${MAX_LOG_FILES:-5}"

# =====================================================================
# 日志管理器类
# =====================================================================

# 初始化日志管理器
init_logger() {
    local component="$1"
    local log_level="${2:-$DEFAULT_LOG_LEVEL}"
    local log_file="${3:-}"
    
    # 设置组件特定的环境变量
    export LOGGER_COMPONENT="$component"
    export LOGGER_LEVEL="$log_level"
    export LOGGER_INITIALIZED="true"
    
    # 如果指定了日志文件，设置文件路径
    if [[ -n "$log_file" ]]; then
        export LOGGER_FILE="$log_file"
        # 确保日志目录存在
        mkdir -p "$(dirname "$log_file")" 2>/dev/null
    fi
    
    # 输出初始化信息
    local level_name=$(get_log_level_name "$log_level")
    log_info "Logger initialized for component: $component (level: $level_name)"
}

# 生成标准化日志文件路径
get_log_file_path() {
    local component="$1"
    local log_type="${2:-general}"
    local timestamp="${3:-$(date +%Y%m%d)}"
    
    echo "${LOGS_DIR}/${component}_${log_type}_${timestamp}.log"
}

# 获取日志级别名称 (兼容函数)
get_log_level_name() {
    local level="$1"
    case "$level" in
        0) echo "$LOG_LEVEL_NAMES_0" ;;
        1) echo "$LOG_LEVEL_NAMES_1" ;;
        2) echo "$LOG_LEVEL_NAMES_2" ;;
        3) echo "$LOG_LEVEL_NAMES_3" ;;
        4) echo "$LOG_LEVEL_NAMES_4" ;;
        *) echo "UNKNOWN" ;;
    esac
}

# 获取日志级别颜色 (兼容函数)
get_log_level_color() {
    local level="$1"
    case "$level" in
        0) echo "$LOG_LEVEL_COLORS_0" ;;
        1) echo "$LOG_LEVEL_COLORS_1" ;;
        2) echo "$LOG_LEVEL_COLORS_2" ;;
        3) echo "$LOG_LEVEL_COLORS_3" ;;
        4) echo "$LOG_LEVEL_COLORS_4" ;;
        *) echo "" ;;
    esac
}

# 格式化日志消息
format_log_message() {
    local level="$1"
    local component="$2"
    local message="$3"
    local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    
    local level_name=$(get_log_level_name "$level")
    
    local formatted_message="$DEFAULT_LOG_FORMAT"
    formatted_message="${formatted_message//%timestamp%/$timestamp}"
    formatted_message="${formatted_message//%level%/$level_name}"
    formatted_message="${formatted_message//%component%/$component}"
    formatted_message="${formatted_message//%message%/$message}"
    
    echo "$formatted_message"
}

# 写入日志
write_log() {
    local level="$1"
    local message="$2"
    local component="${LOGGER_COMPONENT:-unknown}"
    local current_level="${LOGGER_LEVEL:-$DEFAULT_LOG_LEVEL}"
    
    # 检查日志级别
    if [[ $level -lt $current_level ]]; then
        return 0
    fi
    
    # 格式化消息
    local formatted_message=$(format_log_message "$level" "$component" "$message")
    
    # 控制台输出（带颜色）
    local color=$(get_log_level_color "$level")
    echo -e "${color}${formatted_message}${COLOR_RESET}"
    
    # 文件输出（无颜色）
    if [[ -n "${LOGGER_FILE:-}" ]]; then
        echo "$formatted_message" >> "$LOGGER_FILE"
        
        # 检查日志轮转
        check_log_rotation "$LOGGER_FILE"
    fi
}

# =====================================================================
# 日志级别函数
# =====================================================================

log_debug() {
    write_log $LOG_LEVEL_DEBUG "$1"
}

log_info() {
    write_log $LOG_LEVEL_INFO "$1"
}

log_warn() {
    write_log $LOG_LEVEL_WARN "$1"
}

log_error() {
    write_log $LOG_LEVEL_ERROR "$1"
}

log_fatal() {
    write_log $LOG_LEVEL_FATAL "$1"
}

# =====================================================================
# 特殊日志函数
# =====================================================================

# 性能日志
log_performance() {
    local metric="$1"
    local value="$2"
    local unit="${3:-}"
    
    local perf_message="PERF: $metric=$value"
    [[ -n "$unit" ]] && perf_message="$perf_message $unit"
    
    log_info "$perf_message"
}

# 瓶颈日志
log_bottleneck() {
    local bottleneck_type="$1"
    local severity="$2"
    local details="$3"
    
    log_warn "BOTTLENECK: $bottleneck_type (severity: $severity) - $details"
}

# 错误追踪日志
log_error_trace() {
    local error_message="$1"
    local function_name="${2:-unknown}"
    local line_number="${3:-unknown}"
    
    log_error "ERROR_TRACE: $error_message (function: $function_name, line: $line_number)"
}

# =====================================================================
# 日志轮转管理
# =====================================================================

# 检查并执行日志轮转
check_log_rotation() {
    local log_file="$1"
    
    if [[ ! -f "$log_file" ]]; then
        return 0
    fi
    
    # 检查文件大小
    local file_size=$(stat -f%z "$log_file" 2>/dev/null || stat -c%s "$log_file" 2>/dev/null || echo "0")
    local max_size_bytes=$(convert_size_to_bytes "$DEFAULT_MAX_LOG_SIZE")
    
    if [[ $file_size -gt $max_size_bytes ]]; then
        rotate_log_file "$log_file"
    fi
}

# 转换大小单位到字节
convert_size_to_bytes() {
    local size_str="$1"
    local size_num=$(echo "$size_str" | sed 's/[^0-9]//g')
    local size_unit=$(echo "$size_str" | sed 's/[0-9]//g' | tr '[:lower:]' '[:upper:]')
    
    case "$size_unit" in
        "K"|"KB") echo $((size_num * 1024)) ;;
        "M"|"MB") echo $((size_num * 1024 * 1024)) ;;
        "G"|"GB") echo $((size_num * 1024 * 1024 * 1024)) ;;
        *) echo "$size_num" ;;
    esac
}

# 执行日志轮转
rotate_log_file() {
    local log_file="$1"
    local base_name="${log_file%.*}"
    local extension="${log_file##*.}"
    
    # 轮转现有文件
    for ((i=$DEFAULT_MAX_LOG_FILES; i>1; i--)); do
        local old_file="${base_name}.${i}.${extension}"
        local new_file="${base_name}.$((i+1)).${extension}"
        [[ -f "$old_file" ]] && mv "$old_file" "$new_file"
    done
    
    # 移动当前文件
    mv "$log_file" "${base_name}.1.${extension}"
    
    log_info "Log rotated: $log_file"
}

# =====================================================================
# 日志查询和分析
# =====================================================================

# 查询日志
query_logs() {
    local component="$1"
    local level="${2:-}"
    local start_time="${3:-}"
    local end_time="${4:-}"
    local pattern="${5:-}"
    
    local log_pattern="${LOGS_DIR}/${component}_*.log"
    
    # 构建grep命令
    local grep_cmd="grep"
    [[ -n "$level" ]] && grep_cmd="$grep_cmd -E '\\[$level\\]'"
    [[ -n "$pattern" ]] && grep_cmd="$grep_cmd -E '$pattern'"
    
    # 执行查询
    find "${LOGS_DIR}" -name "${component}_*.log" -exec $grep_cmd {} \; 2>/dev/null | sort
}

# 生成日志统计
generate_log_stats() {
    local component="$1"
    local log_file="${2:-$(get_log_file_path "$component")}"
    
    if [[ ! -f "$log_file" ]]; then
        echo "日志文件不存在: $log_file"
        return 1
    fi
    
    echo "📊 日志统计报告: $component"
    echo "================================"
    echo "文件: $log_file"
    echo "总行数: $(wc -l < "$log_file")"
    echo ""
    echo "按级别统计:"
    for level in 0 1 2 3 4; do
        local level_name=$(get_log_level_name "$level")
        local count=$(grep -c "\\[$level_name\\]" "$log_file" 2>/dev/null || echo "0")
        echo "  $level_name: $count"
    done
    echo ""
    echo "最近10条日志:"
    tail -10 "$log_file"
}

# =====================================================================
# 工具函数
# =====================================================================

# 显示使用帮助
show_logger_help() {
    cat << EOF
📋 统一日志管理器使用说明
============================

初始化日志器:
  init_logger <component> [log_level] [log_file]

日志级别函数:
  log_debug <message>     - 调试信息
  log_info <message>      - 一般信息  
  log_warn <message>      - 警告信息
  log_error <message>     - 错误信息
  log_fatal <message>     - 致命错误

特殊日志函数:
  log_performance <metric> <value> [unit]
  log_bottleneck <type> <severity> <details>
  log_error_trace <message> [function] [line]

日志查询:
  query_logs <component> [level] [start_time] [end_time] [pattern]
  generate_log_stats <component> [log_file]

配置环境变量:
  LOG_LEVEL=<0-4>         - 设置日志级别
  LOG_FORMAT=<format>     - 设置日志格式
  MAX_LOG_SIZE=<size>     - 设置最大日志文件大小
  MAX_LOG_FILES=<count>   - 设置保留的日志文件数量

示例:
  source utils/unified_logger.sh
  init_logger "qps_analyzer" $LOG_LEVEL_INFO "\${LOGS_DIR}/qps_analyzer.log"
  log_info "QPS分析开始"
  log_performance "max_qps" "1500" "req/s"
  log_warn "检测到性能瓶颈"
EOF
}

# =====================================================================
# 主函数 - 用于测试
# =====================================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-help}" in
        "test")
            echo "🧪 测试统一日志管理器..."
            init_logger "test_component" $LOG_LEVEL_DEBUG "/tmp/test_logger.log"
            log_debug "这是调试信息"
            log_info "这是一般信息"
            log_warn "这是警告信息"
            log_error "这是错误信息"
            log_performance "test_metric" "100" "ms"
            log_bottleneck "CPU" "HIGH" "CPU使用率超过90%"
            echo "✅ 测试完成，查看日志文件: /tmp/test_logger.log"
            ;;
        "help"|*)
            show_logger_help
            ;;
    esac
fi

# 标记已加载，防止重复加载
UNIFIED_LOGGER_LOADED=true
export UNIFIED_LOGGER_LOADED
