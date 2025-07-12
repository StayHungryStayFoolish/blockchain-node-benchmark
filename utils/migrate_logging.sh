#!/bin/bash
# =====================================================================
# 日志配置迁移工具
# =====================================================================
# 自动将现有文件的日志配置迁移到统一日志管理器
# 分析现有日志模式并生成迁移建议
# =====================================================================

source "$(dirname "$0")/unified_logger.sh"

# 初始化迁移日志器
init_logger "log_migrator" $LOG_LEVEL_INFO "${LOGS_DIR}/log_migration.log"

# =====================================================================
# 迁移配置
# =====================================================================

readonly MIGRATION_REPORT="${LOGS_DIR}/log_migration_report_$(date +%Y%m%d_%H%M%S).md"
readonly BACKUP_DIR="${LOGS_DIR}/migration_backups_$(date +%Y%m%d_%H%M%S)"

# 需要迁移的文件模式
declare -a SHELL_FILES=(
    "tools/*.sh"
    "analysis/*.sh"
    "monitoring/*.sh"
    "core/*.sh"
)

declare -a PYTHON_FILES=(
    "analysis/*.py"
    "visualization/*.py"
    "utils/*.py"
)

# =====================================================================
# 分析现有日志模式
# =====================================================================

analyze_current_logging() {
    log_info "开始分析现有日志配置..."
    
    echo "# 日志配置迁移分析报告" > "$MIGRATION_REPORT"
    echo "生成时间: $(date)" >> "$MIGRATION_REPORT"
    echo "" >> "$MIGRATION_REPORT"
    
    # 分析Shell脚本日志模式
    analyze_shell_logging
    
    # 分析Python脚本日志模式
    analyze_python_logging
    
    # 生成迁移建议
    generate_migration_recommendations
    
    log_info "分析完成，报告保存至: $MIGRATION_REPORT"
}

analyze_shell_logging() {
    log_info "分析Shell脚本日志模式..."
    
    echo "## Shell脚本日志模式分析" >> "$MIGRATION_REPORT"
    echo "" >> "$MIGRATION_REPORT"
    
    local shell_log_patterns=()
    
    for pattern in "${SHELL_FILES[@]}"; do
        for file in $pattern; do
            [[ -f "$file" ]] || continue
            
            log_debug "分析文件: $file"
            
            # 检查日志文件定义
            local log_file_defs=$(grep -n "LOG.*FILE\|log.*file" "$file" 2>/dev/null || true)
            if [[ -n "$log_file_defs" ]]; then
                echo "### $file" >> "$MIGRATION_REPORT"
                echo "**日志文件定义:**" >> "$MIGRATION_REPORT"
                echo '```bash' >> "$MIGRATION_REPORT"
                echo "$log_file_defs" >> "$MIGRATION_REPORT"
                echo '```' >> "$MIGRATION_REPORT"
                echo "" >> "$MIGRATION_REPORT"
            fi
            
            # 检查日志输出模式
            local log_outputs=$(grep -n "echo.*tee\|printf.*tee\|>>.*log\|>.*log" "$file" 2>/dev/null | head -5 || true)
            if [[ -n "$log_outputs" ]]; then
                echo "**日志输出模式:**" >> "$MIGRATION_REPORT"
                echo '```bash' >> "$MIGRATION_REPORT"
                echo "$log_outputs" >> "$MIGRATION_REPORT"
                echo '```' >> "$MIGRATION_REPORT"
                echo "" >> "$MIGRATION_REPORT"
            fi
        done
    done
}

analyze_python_logging() {
    log_info "分析Python脚本日志模式..."
    
    echo "## Python脚本日志模式分析" >> "$MIGRATION_REPORT"
    echo "" >> "$MIGRATION_REPORT"
    
    for pattern in "${PYTHON_FILES[@]}"; do
        for file in $pattern; do
            [[ -f "$file" ]] || continue
            
            log_debug "分析文件: $file"
            
            # 检查logging导入
            local logging_imports=$(grep -n "import logging\|from logging" "$file" 2>/dev/null || true)
            if [[ -n "$logging_imports" ]]; then
                echo "### $file" >> "$MIGRATION_REPORT"
                echo "**Logging导入:**" >> "$MIGRATION_REPORT"
                echo '```python' >> "$MIGRATION_REPORT"
                echo "$logging_imports" >> "$MIGRATION_REPORT"
                echo '```' >> "$MIGRATION_REPORT"
                echo "" >> "$MIGRATION_REPORT"
            fi
            
            # 检查logger配置
            local logger_configs=$(grep -n "getLogger\|basicConfig\|StreamHandler\|FileHandler" "$file" 2>/dev/null || true)
            if [[ -n "$logger_configs" ]]; then
                echo "**Logger配置:**" >> "$MIGRATION_REPORT"
                echo '```python' >> "$MIGRATION_REPORT"
                echo "$logger_configs" >> "$MIGRATION_REPORT"
                echo '```' >> "$MIGRATION_REPORT"
                echo "" >> "$MIGRATION_REPORT"
            fi
        done
    done
}

generate_migration_recommendations() {
    log_info "生成迁移建议..."
    
    cat >> "$MIGRATION_REPORT" << 'EOF'

## 迁移建议

### Shell脚本迁移步骤

1. **引入统一日志管理器**
```bash
# 在脚本开头添加
source "$(dirname "$0")/../utils/unified_logger.sh"

# 初始化日志器
init_logger "component_name" $LOG_LEVEL_INFO "${LOGS_DIR}/component_name.log"
```

2. **替换现有日志输出**
```bash
# 替换前
echo "信息消息" | tee -a "$LOG_FILE"
echo "⚠️ 警告消息" | tee -a "$LOG_FILE"
echo "❌ 错误消息" | tee -a "$LOG_FILE"

# 替换后
log_info "信息消息"
log_warn "警告消息"
log_error "错误消息"
```

3. **性能和瓶颈日志**
```bash
# 性能日志
log_performance "max_qps" "1500" "req/s"

# 瓶颈日志
log_bottleneck "CPU" "HIGH" "CPU使用率超过90%"
```

### Python脚本迁移步骤

1. **引入统一日志管理器**
```python
# 替换现有导入
# import logging
# logger = logging.getLogger(__name__)

# 使用统一日志管理器
from utils.unified_logger import get_logger

logger = get_logger(__name__)
```

2. **替换日志调用**
```python
# 基本日志
logger.info("分析开始")
logger.warning("检测到异常")
logger.error("处理失败")

# 特殊日志
logger.performance("processing_time", 1.5, "seconds")
logger.bottleneck("memory", "HIGH", "内存使用率超过85%")
logger.analysis_result("qps_analysis", {"max_qps": 1500})
```

### 环境变量配置

```bash
# 在config.sh中添加
export LOG_LEVEL="INFO"
export LOG_FORMAT="[%timestamp%] [%level%] [%component%] %message%"
export MAX_LOG_SIZE="10M"
export MAX_LOG_FILES="5"
```

EOF
}

# =====================================================================
# 执行迁移
# =====================================================================

migrate_shell_file() {
    local file="$1"
    local backup_file="${BACKUP_DIR}/$(basename "$file").backup"
    
    log_info "迁移Shell文件: $file"
    
    # 创建备份
    mkdir -p "$BACKUP_DIR"
    cp "$file" "$backup_file"
    
    # 创建临时文件
    local temp_file="${file}.tmp"
    
    # 处理文件内容
    {
        # 添加统一日志管理器引入
        echo '# 引入统一日志管理器'
        echo 'source "$(dirname "$0")/../utils/unified_logger.sh"'
        echo ''
        
        # 添加日志器初始化
        local component_name=$(basename "$file" .sh)
        echo "# 初始化日志器"
        echo "init_logger \"$component_name\" \$LOG_LEVEL_INFO \"\${LOGS_DIR}/${component_name}.log\""
        echo ''
        
        # 处理原文件内容
        sed -e 's/echo "\([^"]*\)" | tee -a "\$[^"]*"/log_info "\1"/g' \
            -e 's/echo "⚠️ \([^"]*\)" | tee -a "\$[^"]*"/log_warn "\1"/g' \
            -e 's/echo "❌ \([^"]*\)" | tee -a "\$[^"]*"/log_error "\1"/g' \
            "$file"
    } > "$temp_file"
    
    # 替换原文件
    mv "$temp_file" "$file"
    
    log_info "Shell文件迁移完成: $file (备份: $backup_file)"
}

migrate_python_file() {
    local file="$1"
    local backup_file="${BACKUP_DIR}/$(basename "$file").backup"
    
    log_info "迁移Python文件: $file"
    
    # 创建备份
    mkdir -p "$BACKUP_DIR"
    cp "$file" "$backup_file"
    
    # 创建临时文件
    local temp_file="${file}.tmp"
    
    # 处理文件内容
    sed -e 's/import logging/from utils.unified_logger import get_logger/g' \
        -e 's/logger = logging.getLogger(__name__)/logger = get_logger(__name__)/g' \
        -e 's/logging.basicConfig/#logging.basicConfig/g' \
        "$file" > "$temp_file"
    
    # 替换原文件
    mv "$temp_file" "$file"
    
    log_info "Python文件迁移完成: $file (备份: $backup_file)"
}

# =====================================================================
# 主函数
# =====================================================================

main() {
    local action="${1:-analyze}"
    
    case "$action" in
        "analyze")
            log_info "开始日志配置分析..."
            analyze_current_logging
            ;;
        "migrate")
            log_info "开始执行日志配置迁移..."
            
            # 先分析
            analyze_current_logging
            
            # 询问确认
            echo "是否继续执行迁移? (y/N)"
            read -r confirm
            if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
                log_info "迁移已取消"
                exit 0
            fi
            
            # 执行迁移
            log_info "开始迁移Shell脚本..."
            for pattern in "${SHELL_FILES[@]}"; do
                for file in $pattern; do
                    [[ -f "$file" ]] && migrate_shell_file "$file"
                done
            done
            
            log_info "开始迁移Python脚本..."
            for pattern in "${PYTHON_FILES[@]}"; do
                for file in $pattern; do
                    [[ -f "$file" ]] && migrate_python_file "$file"
                done
            done
            
            log_info "迁移完成！备份目录: $BACKUP_DIR"
            ;;
        "help"|*)
            cat << EOF
📋 日志配置迁移工具使用说明
============================

用法: $0 [action]

Actions:
  analyze  - 分析现有日志配置模式 (默认)
  migrate  - 执行日志配置迁移
  help     - 显示此帮助信息

示例:
  $0 analyze   # 分析现有日志配置
  $0 migrate   # 执行迁移（会先分析再询问确认）

注意:
  - 迁移前会自动创建备份
  - 建议先运行analyze查看分析报告
  - 迁移后需要测试各个组件功能
EOF
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
