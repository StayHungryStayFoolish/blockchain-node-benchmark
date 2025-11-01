#!/bin/bash
# =====================================================================
# Unified Logger Manager - Unified Logger
# =====================================================================
# Provides unified logging configuration, formatting, rotation, and management functionality
# Solves inconsistent logging configuration issues in the project
# =====================================================================

# Prevent duplicate loading - but function definitions need to be reloaded in subprocesses
if [[ "${UNIFIED_LOGGER_LOADED:-false}" == "true" ]] && [[ "$(type -t init_logger)" == "function" ]]; then
    return 0
fi

# Import configuration
source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh"

# =====================================================================
# Logging configuration constants
# =====================================================================

# Log level definitions
readonly LOG_LEVEL_DEBUG=0
readonly LOG_LEVEL_INFO=1
readonly LOG_LEVEL_WARN=2
readonly LOG_LEVEL_ERROR=3
readonly LOG_LEVEL_FATAL=4

# Log level name mapping
LOG_LEVEL_NAMES_0="DEBUG"
LOG_LEVEL_NAMES_1="INFO"
LOG_LEVEL_NAMES_2="WARN"
LOG_LEVEL_NAMES_3="ERROR"
LOG_LEVEL_NAMES_4="FATAL"

# Color definitions
readonly COLOR_RESET='\033[0m'
readonly COLOR_RED='\033[0;31m'
readonly COLOR_GREEN='\033[0;32m'
readonly COLOR_YELLOW='\033[0;33m'
readonly COLOR_BLUE='\033[0;34m'
readonly COLOR_PURPLE='\033[0;35m'
readonly COLOR_CYAN='\033[0;36m'
readonly COLOR_WHITE='\033[0;37m'

# Log level color mapping
LOG_LEVEL_COLORS_0="\033[0;36m"    # Cyan - DEBUG
LOG_LEVEL_COLORS_1="\033[0;32m"    # Green - INFO
LOG_LEVEL_COLORS_2="\033[0;33m"    # Yellow - WARN
LOG_LEVEL_COLORS_3="\033[0;31m"    # Red - ERROR
LOG_LEVEL_COLORS_4="\033[0;35m"    # Purple - FATAL

# Default configuration
DEFAULT_LOG_LEVEL=${LOG_LEVEL:-$LOG_LEVEL_INFO}
DEFAULT_LOG_FORMAT="${LOG_FORMAT:-"[%timestamp%] [%level%] [%component%] %message%"}"
DEFAULT_MAX_LOG_SIZE="${MAX_LOG_SIZE:-10M}"
DEFAULT_MAX_LOG_FILES="${MAX_LOG_FILES:-5}"

# =====================================================================
# Logger manager class
# =====================================================================

# Component log file mapping table (replaces global LOGGER_FILE)
declare -A COMPONENT_LOG_FILES

# Initialize logger manager
init_logger() {
    local component="$1"
    local log_level="${2:-$DEFAULT_LOG_LEVEL}"
    local log_file="${3:-}"
    
    # Use component-level mapping, completely remove global variables
    if [[ -n "$log_file" ]]; then
        COMPONENT_LOG_FILES["$component"]="$log_file"
        # Ensure log directory exists
        mkdir -p "$(dirname "$log_file")" 2>/dev/null
    fi
    
    # Set component-specific environment variables (process internal only)
    export LOGGER_COMPONENT="$component"
    export LOGGER_LEVEL="$log_level"
    export LOGGER_INITIALIZED="true"
    
    # Output initialization information
    local level_name=$(get_log_level_name "$log_level")
    echo "Logger initialized for component: $component (level: $level_name)"
}

# Generate standardized log file path
get_log_file_path() {
    local component="$1"
    local log_type="${2:-general}"
    local timestamp="${3:-$(date +%Y%m%d)}"
    
    echo "${LOGS_DIR}/${component}_${log_type}_${timestamp}.log"
}

# Get log level name
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

# Get log level color (compatibility function)
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

# Format log message
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

# Write log
write_log() {
    local level="$1"
    local message="$2"
    local component="${LOGGER_COMPONENT:-unknown}"
    local current_level="${LOGGER_LEVEL:-$DEFAULT_LOG_LEVEL}"
    
    # Check log level
    if [[ $level -lt $current_level ]]; then
        return 0
    fi
    
    # Format message
    local formatted_message=$(format_log_message "$level" "$component" "$message")
    
    # Console output (with color) - redirect to stderr to avoid polluting stdout
    local color=$(get_log_level_color "$level")
    echo -e "${color}${formatted_message}${COLOR_RESET}" >&2
    
    # File output (no color)
    local component="${LOGGER_COMPONENT:-unknown}"
    local log_file="${COMPONENT_LOG_FILES[$component]:-}"
    
    if [[ -n "$log_file" ]]; then
        echo "$formatted_message" >> "$log_file"
        
        # Check log rotation
        check_log_rotation "$log_file"
    fi
}

# =====================================================================
# Log level functions
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
# Special log functions
# =====================================================================

# Performance log
log_performance() {
    local metric="$1"
    local value="$2"
    local unit="${3:-}"
    
    local perf_message="PERF: $metric=$value"
    [[ -n "$unit" ]] && perf_message="$perf_message $unit"
    
    log_info "$perf_message"
}

# Bottleneck log
log_bottleneck() {
    local bottleneck_type="$1"
    local severity="$2"
    local details="$3"
    
    log_warn "BOTTLENECK: $bottleneck_type (severity: $severity) - $details"
}

# Error trace log
log_error_trace() {
    local error_message="$1"
    local function_name="${2:-unknown}"
    local line_number="${3:-unknown}"
    
    log_error "ERROR_TRACE: $error_message (function: $function_name, line: $line_number)"
}

# =====================================================================
# Log rotation management
# =====================================================================

# Check and execute log rotation
check_log_rotation() {
    local log_file="$1"
    
    if [[ ! -f "$log_file" ]]; then
        return 0
    fi
    
    # Check file size
    local file_size=$(stat -c%s "$log_file" 2>/dev/null || echo "0")
    local max_size_bytes=$(convert_size_to_bytes "$DEFAULT_MAX_LOG_SIZE")
    
    if [[ $file_size -gt $max_size_bytes ]]; then
        rotate_log_file "$log_file"
    fi
}

# Convert size unit to bytes
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

# Execute log rotation
rotate_log_file() {
    local log_file="$1"
    local base_name="${log_file%.*}"
    local extension="${log_file##*.}"
    
    # Rotate existing files
    for ((i=$DEFAULT_MAX_LOG_FILES; i>1; i--)); do
        local old_file="${base_name}.${i}.${extension}"
        local new_file="${base_name}.$((i+1)).${extension}"
        [[ -f "$old_file" ]] && mv "$old_file" "$new_file"
    done
    
    # Move current file
    mv "$log_file" "${base_name}.1.${extension}"
    
    log_info "Log rotated: $log_file"
}

# =====================================================================
# Log query and analysis
# =====================================================================

# Query logs
query_logs() {
    local component="$1"
    local level="${2:-}"
    local start_time="${3:-}"
    local end_time="${4:-}"
    local pattern="${5:-}"
    
    local log_pattern="${LOGS_DIR}/${component}_*.log"
    
    # Build grep command
    local grep_cmd="grep"
    [[ -n "$level" ]] && grep_cmd="$grep_cmd -E '\\[$level\\]'"
    [[ -n "$pattern" ]] && grep_cmd="$grep_cmd -E '$pattern'"
    
    # Execute query
    find "${LOGS_DIR}" -name "${component}_*.log" -exec $grep_cmd {} \; 2>/dev/null | sort
}

# Generate log statistics
generate_log_stats() {
    local component="$1"
    local log_file="${2:-$(get_log_file_path "$component")}"
    
    if [[ ! -f "$log_file" ]]; then
        echo "Log file does not exist: $log_file"
        return 1
    fi
    
    echo "📊 Log Statistics Report: $component"
    echo "================================"
    echo "File: $log_file"
    echo "Total lines: $(wc -l < "$log_file")"
    echo ""
    echo "Statistics by level:"
    for level in 0 1 2 3 4; do
        local level_name=$(get_log_level_name "$level")
        local count=$(grep -c "\\[$level_name\\]" "$log_file" 2>/dev/null || echo "0")
        echo "  $level_name: $count"
    done
    echo ""
    echo "Last 10 log entries:"
    tail -10 "$log_file"
}

# =====================================================================
# Utility functions
# =====================================================================

# Show usage help
show_logger_help() {
    cat << EOF
📋 Unified Logger Manager Usage Guide
============================

Initialize logger:
  init_logger <component> [log_level] [log_file]

Log level functions:
  log_debug <message>     - Debug information
  log_info <message>      - General information  
  log_warn <message>      - Warning information
  log_error <message>     - Error information
  log_fatal <message>     - Fatal error

Special log functions:
  log_performance <metric> <value> [unit]
  log_bottleneck <type> <severity> <details>
  log_error_trace <message> [function] [line]

Log query:
  query_logs <component> [level] [start_time] [end_time] [pattern]
  generate_log_stats <component> [log_file]

Configuration environment variables:
  LOG_LEVEL=<0-4>         - Set log level
  LOG_FORMAT=<format>     - Set log format
  MAX_LOG_SIZE=<size>     - Set maximum log file size
  MAX_LOG_FILES=<count>   - Set number of log files to keep

Example:
  source utils/unified_logger.sh
  init_logger "qps_analyzer" \$LOG_LEVEL_INFO "\${LOGS_DIR}/qps_analyzer.log"
  log_info "QPS analysis started"
  log_performance "max_qps" "1500" "req/s"
  log_warn "Performance bottleneck detected"
EOF
}

# =====================================================================
# Main function - for testing
# =====================================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-help}" in
        "test")
            echo "🧪 Testing unified logger manager..."
            init_logger "test_component" $LOG_LEVEL_DEBUG "/tmp/test_logger.log"
            log_debug "This is debug information"
            log_info "This is general information"
            log_warn "This is warning information"
            log_error "This is error information"
            log_performance "test_metric" "100" "ms"
            log_bottleneck "CPU" "HIGH" "CPU usage exceeds 90%"
            echo "✅ Testing completed, check log file: /tmp/test_logger.log"
            ;;
        "help"|*)
            show_logger_help
            ;;
    esac
fi

# Mark as loaded to prevent duplicate loading
UNIFIED_LOGGER_LOADED=true
export UNIFIED_LOGGER_LOADED
