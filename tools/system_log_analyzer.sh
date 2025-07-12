#!/bin/bash

# =====================================================================
# 系统日志分析器 - 分析QPS测试期间的系统事件
# =====================================================================

source "$(dirname "${BASH_SOURCE[0]}")/../config/config.sh"

# 系统日志路径
SYSTEM_LOG_PATH="/var/log/syslog"

# 分析QPS测试期间的系统日志
analyze_system_log() {
    local start_time="$1"
    local end_time="$2"
    local output_file="$3"
    
    echo "🔍 分析系统日志: $SYSTEM_LOG_PATH"
    echo "📅 时间范围: $start_time 到 $end_time"
    echo "📄 输出文件: $output_file"
    
    if [[ ! -f "$SYSTEM_LOG_PATH" ]]; then
        echo "❌ 系统日志文件不存在: $SYSTEM_LOG_PATH"
        return 1
    fi
    
    # 提取时间范围内的日志
    awk -v start="$start_time" -v end="$end_time" '
    {
        # 提取日志时间戳并与指定范围比较
        if ($0 ~ /^[A-Z][a-z]{2} [0-9 ][0-9] [0-9]{2}:[0-9]{2}:[0-9]{2}/) {
            if ($0 >= start && $0 <= end) {
                print $0
            }
        }
    }' "$SYSTEM_LOG_PATH" > "$output_file"
    
    echo "✅ 系统日志分析完成"
}

# 如果直接执行此脚本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ $# -lt 3 ]]; then
        echo "用法: $0 <开始时间> <结束时间> <输出文件>"
        echo "示例: $0 '2024-06-22 10:00:00' '2024-06-22 12:00:00' system_analysis.txt"
        exit 1
    fi
    
    analyze_system_log "$1" "$2" "$3"
fi
