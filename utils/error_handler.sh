#!/bin/bash
# =====================================================================
# Unified Error Handling Tool - Provides standardized error handling for all scripts
# =====================================================================
# This is a new tool that does not replace any existing functionality
# Provides unified error handling, logging, and cleanup mechanisms for the framework
# =====================================================================

# Strict error handling
set -euo pipefail

# Get current script directory (use local variable to avoid polluting global SCRIPT_DIR)
LOCAL_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load unified logging tool
source "${LOCAL_SCRIPT_DIR}/unified_logger.sh"

# Global error handling configuration - use unified configuration from config_loader.sh
if [[ -z "${ERROR_LOG_DIR:-}" ]]; then
    readonly ERROR_LOG_DIR="${LOGS_DIR:-/tmp}/error_logs"
fi
if [[ -z "${ERROR_LOG_FILE:-}" ]]; then
    readonly ERROR_LOG_FILE="${ERROR_LOG_DIR}/framework_errors_$(date +%Y%m%d).log"
fi

# Ensure error log directory exists
mkdir -p "$ERROR_LOG_DIR" 2>/dev/null || {
    # If unable to create configured directory, use system temp directory as fallback
    if [[ -z "${FALLBACK_ERROR_LOG_DIR:-}" ]]; then
        readonly FALLBACK_ERROR_LOG_DIR="/tmp/blockchain-node-qps-errors"
    fi
    mkdir -p "$FALLBACK_ERROR_LOG_DIR"
    if [[ "$ERROR_LOG_DIR" != "$FALLBACK_ERROR_LOG_DIR" ]]; then
        ERROR_LOG_DIR="$FALLBACK_ERROR_LOG_DIR"
        ERROR_LOG_FILE="${ERROR_LOG_DIR}/framework_errors_$(date +%Y%m%d).log"
    fi
    echo "⚠️ Using fallback error log directory: $ERROR_LOG_DIR" >&2
}

# Generic error handling function
handle_framework_error() {
    local exit_code=$?
    local line_number=$1
    local script_name="${2:-$(basename "$0")}"
    local error_context="${3:-Unknown error}"
    
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local error_msg="[$timestamp] ❌ $script_name:$line_number - $error_context (Exit code: $exit_code)"
    
    # Log to error log
    log_info "$error_msg"
    
    # Output to stderr
    echo "$error_msg" >&2
    echo "🔧 Error details logged to: $ERROR_LOG_FILE" >&2
    
    # Call cleanup function (if exists)
    if declare -f cleanup_on_error >/dev/null; then
        echo "🧹 Executing cleanup operations..." >&2
        cleanup_on_error || true
    fi
    
    return $exit_code
}

# Function to set up generic error trap
setup_error_handling() {
    local script_name="${1:-$(basename "$0")}"
    local context="${2:-Script execution}"
    
    trap "handle_framework_error \$LINENO '$script_name' '$context'" ERR
    
    echo "✅ Error handling set up for $script_name" >&2
}

# Log script start execution
log_script_start() {
    local script_name="${1:-$(basename "$0")}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    log_info "[$timestamp] 🚀 Starting execution: $script_name"
}

# Log script successful completion
log_script_success() {
    local script_name="${1:-$(basename "$0")}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    log_info "[$timestamp] ✅ Successfully completed: $script_name"
}

# Check if dependency tools exist
check_dependencies() {
    local missing_deps=()
    
    for cmd in "$@"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing_deps+=("$cmd")
        fi
    done
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        echo "❌ Missing required dependency tools: ${missing_deps[*]}" >&2
        echo "Please install missing tools and retry" >&2
        return 1
    fi
    
    return 0
}

# Safely execute command (with retry mechanism)
safe_execute() {
    local max_retries=${1:-3}
    local retry_delay=${2:-1}
    shift 2
    local cmd=("$@")
    
    local attempt=1
    while [[ $attempt -le $max_retries ]]; do
        if "${cmd[@]}"; then
            return 0
        else
            local exit_code=$?
            echo "⚠️  Command execution failed (attempt $attempt/$max_retries): ${cmd[*]}" >&2
            
            if [[ $attempt -lt $max_retries ]]; then
                echo "🔄 Waiting ${retry_delay}s before retry..." >&2
                sleep "$retry_delay"
                ((attempt++))
            else
                echo "❌ Command execution finally failed: ${cmd[*]}" >&2
                return $exit_code
            fi
        fi
    done
}

# Generic function to clean up temporary files
cleanup_temp_files() {
    # Use temp file pattern configured in user_config.sh, or use default pattern if unavailable
    local temp_pattern="${1:-${TEMP_FILE_PATTERN:-/tmp/blockchain-node-qps-*}}"
    
    echo "🧹 Cleaning temporary files: $temp_pattern" >&2
    find /tmp -name "$(basename "$temp_pattern")" -type f -mtime +1 -delete 2>/dev/null || true
}

# Check disk space
check_disk_space() {
    local required_space_mb=${1:-1000}  # Default requires 1GB space
    local target_dir="${2:-${DATA_DIR:-/tmp}}"
    
    if [[ ! -d "$target_dir" ]]; then
        echo "⚠️  Directory does not exist: $target_dir" >&2
        return 1
    fi
    
    local available_space=$(df "$target_dir" | awk 'NR==2 {print int($4/1024)}')
    
    if [[ $available_space -lt $required_space_mb ]]; then
        echo "❌ Insufficient disk space: requires ${required_space_mb}MB, available ${available_space}MB" >&2
        return 1
    fi
    
    echo "✅ Sufficient disk space: available ${available_space}MB" >&2
    return 0
}

# Validate configuration file
validate_config() {
    local config_file="${1:-config_loader.sh}"
    
    if [[ ! -f "$config_file" ]]; then
        echo "❌ Configuration file does not exist: $config_file" >&2
        return 1
    fi
    
    # Check configuration file syntax
    if ! bash -n "$config_file"; then
        echo "❌ Configuration file syntax error: $config_file" >&2
        return 1
    fi
    
    echo "✅ Configuration file validation passed: $config_file" >&2
    return 0
}

# If script is executed directly, display usage instructions
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "📋 Unified Error Handling Tool Usage Instructions:"
    echo ""
    echo "Use in other scripts:"
    echo "  source \"\$(dirname \"\$0\")/../utils/error_handler.sh\""
    echo "  setup_error_handling \"\$(basename \"\$0\")\" \"Script description\""
    echo "  log_script_start"
    echo ""
    echo "Available functions:"
    echo "  - setup_error_handling: Set up error handling"
    echo "  - log_script_start/success: Log script status"
    echo "  - check_dependencies: Check dependency tools"
    echo "  - safe_execute: Safely execute command (with retry)"
    echo "  - cleanup_temp_files: Clean up temporary files"
    echo "  - check_disk_space: Check disk space"
    echo "  - validate_config: Validate configuration file"
    echo ""
    echo "Error log location: $ERROR_LOG_FILE"
fi
