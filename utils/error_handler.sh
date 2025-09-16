#!/bin/bash
# =====================================================================
# 统一错误处理工具 - 为所有脚本提供标准化错误处理
# =====================================================================
# 这是一个新增的工具，不替代任何现有功能
# 为框架提供统一的错误处理、日志记录和清理机制
# =====================================================================

# 严格错误处理
set -euo pipefail

# 获取当前脚本目录（使用局部变量避免污染全局SCRIPT_DIR）
LOCAL_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 加载统一日志工具
source "${LOCAL_SCRIPT_DIR}/unified_logger.sh"

# 全局错误处理配置 - 使用config_loader.sh中的统一配置
if [[ -z "${ERROR_LOG_DIR:-}" ]]; then
    readonly ERROR_LOG_DIR="${LOGS_DIR:-/tmp}/error_logs"
fi
if [[ -z "${ERROR_LOG_FILE:-}" ]]; then
    readonly ERROR_LOG_FILE="${ERROR_LOG_DIR}/framework_errors_$(date +%Y%m%d).log"
fi

# 确保错误日志目录存在
mkdir -p "$ERROR_LOG_DIR" 2>/dev/null || {
    # 如果无法创建配置的目录，使用系统临时目录作为后备
    if [[ -z "${FALLBACK_ERROR_LOG_DIR:-}" ]]; then
        readonly FALLBACK_ERROR_LOG_DIR="/tmp/solana-qps-errors"
    fi
    mkdir -p "$FALLBACK_ERROR_LOG_DIR"
    if [[ "$ERROR_LOG_DIR" != "$FALLBACK_ERROR_LOG_DIR" ]]; then
        ERROR_LOG_DIR="$FALLBACK_ERROR_LOG_DIR"
        ERROR_LOG_FILE="${ERROR_LOG_DIR}/framework_errors_$(date +%Y%m%d).log"
    fi
    echo "⚠️ 使用后备错误日志目录: $ERROR_LOG_DIR" >&2
}

# 通用错误处理函数
handle_framework_error() {
    local exit_code=$?
    local line_number=$1
    local script_name="${2:-$(basename "$0")}"
    local error_context="${3:-未知错误}"
    
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local error_msg="[$timestamp] ❌ $script_name:$line_number - $error_context (退出码: $exit_code)"
    
    # 记录到错误日志
    log_info "$error_msg"
    
    # 输出到stderr
    echo "$error_msg" >&2
    echo "🔧 错误详情已记录到: $ERROR_LOG_FILE" >&2
    
    # 调用清理函数（如果存在）
    if declare -f cleanup_on_error >/dev/null; then
        echo "🧹 执行清理操作..." >&2
        cleanup_on_error || true
    fi
    
    return $exit_code
}

# 设置通用错误陷阱的函数
setup_error_handling() {
    local script_name="${1:-$(basename "$0")}"
    local context="${2:-脚本执行}"
    
    trap "handle_framework_error \$LINENO '$script_name' '$context'" ERR
    
    echo "✅ 已为 $script_name 设置错误处理" >&2
}

# 记录脚本开始执行
log_script_start() {
    local script_name="${1:-$(basename "$0")}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    log_info "[$timestamp] 🚀 开始执行: $script_name"
}

# 记录脚本成功完成
log_script_success() {
    local script_name="${1:-$(basename "$0")}"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    log_info "[$timestamp] ✅ 成功完成: $script_name"
}

# 检查依赖工具是否存在
check_dependencies() {
    local missing_deps=()
    
    for cmd in "$@"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing_deps+=("$cmd")
        fi
    done
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        echo "❌ 缺少必要的依赖工具: ${missing_deps[*]}" >&2
        echo "请安装缺少的工具后重试" >&2
        return 1
    fi
    
    return 0
}

# 安全执行命令（带重试机制）
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
            echo "⚠️  命令执行失败 (尝试 $attempt/$max_retries): ${cmd[*]}" >&2
            
            if [[ $attempt -lt $max_retries ]]; then
                echo "🔄 等待 ${retry_delay}s 后重试..." >&2
                sleep "$retry_delay"
                ((attempt++))
            else
                echo "❌ 命令执行最终失败: ${cmd[*]}" >&2
                return $exit_code
            fi
        fi
    done
}

# 清理临时文件的通用函数
cleanup_temp_files() {
    # 使用user_config.sh中配置的临时文件模式，如果不可用则使用默认模式
    local temp_pattern="${1:-${TEMP_FILE_PATTERN:-/tmp/solana-qps-*}}"
    
    echo "🧹 清理临时文件: $temp_pattern" >&2
    find /tmp -name "$(basename "$temp_pattern")" -type f -mtime +1 -delete 2>/dev/null || true
}

# 检查磁盘空间
check_disk_space() {
    local required_space_mb=${1:-1000}  # 默认需要1GB空间
    local target_dir="${2:-${DATA_DIR:-/tmp}}"
    
    if [[ ! -d "$target_dir" ]]; then
        echo "⚠️  目录不存在: $target_dir" >&2
        return 1
    fi
    
    local available_space=$(df "$target_dir" | awk 'NR==2 {print int($4/1024)}')
    
    if [[ $available_space -lt $required_space_mb ]]; then
        echo "❌ 磁盘空间不足: 需要 ${required_space_mb}MB，可用 ${available_space}MB" >&2
        return 1
    fi
    
    echo "✅ 磁盘空间充足: 可用 ${available_space}MB" >&2
    return 0
}

# 验证配置文件
validate_config() {
    local config_file="${1:-config_loader.sh}"
    
    if [[ ! -f "$config_file" ]]; then
        echo "❌ 配置文件不存在: $config_file" >&2
        return 1
    fi
    
    # 检查配置文件语法
    if ! bash -n "$config_file"; then
        echo "❌ 配置文件语法错误: $config_file" >&2
        return 1
    fi
    
    echo "✅ 配置文件验证通过: $config_file" >&2
    return 0
}

# 如果直接执行此脚本，显示使用说明
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "📋 统一错误处理工具使用说明:"
    echo ""
    echo "在其他脚本中使用:"
    echo "  source \"\$(dirname \"\$0\")/../utils/error_handler.sh\""
    echo "  setup_error_handling \"\$(basename \"\$0\")\" \"脚本描述\""
    echo "  log_script_start"
    echo ""
    echo "可用函数:"
    echo "  - setup_error_handling: 设置错误处理"
    echo "  - log_script_start/success: 记录脚本状态"
    echo "  - check_dependencies: 检查依赖工具"
    echo "  - safe_execute: 安全执行命令（带重试）"
    echo "  - cleanup_temp_files: 清理临时文件"
    echo "  - check_disk_space: 检查磁盘空间"
    echo "  - validate_config: 验证配置文件"
    echo ""
    echo "错误日志位置: $ERROR_LOG_FILE"
fi
