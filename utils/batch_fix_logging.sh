#!/bin/bash
# =====================================================================
# 批量修复日志配置工具
# =====================================================================
# 基于分析报告，批量修复项目中的日志配置不统一问题
# =====================================================================

source "$(dirname "${BASH_SOURCE[0]}")/../config/config.sh"
source "$(dirname "${BASH_SOURCE[0]}")/unified_logger.sh"

init_logger "batch_fix_logging" $LOG_LEVEL_INFO "${LOGS_DIR}/batch_fix_logging.log"

readonly BACKUP_DIR="${LOGS_DIR}/logging_fix_backups_$(date +%Y%m%d_%H%M%S)"
readonly FIX_REPORT="${LOGS_DIR}/logging_fix_report_$(date +%Y%m%d_%H%M%S).md"

# 需要修复的Shell脚本列表
SHELL_FILES_TO_FIX=(
    "tools/ebs_bottleneck_detector.sh"
    "core/master_qps_executor.sh"
    "analysis/analyze_validator_logs.sh"
    "utils/error_handler.sh"
    "monitoring/bottleneck_detector.sh"
    "monitoring/unified_monitor.sh"
)

# 需要修复的Python脚本列表
PYTHON_FILES_TO_FIX=(
    "visualization/advanced_chart_generator.py"
    "analysis/validator_log_analyzer.py"
    "analysis/comprehensive_analysis.py"
    "analysis/rpc_deep_analyzer.py"
    "analysis/cpu_ebs_correlation_analyzer.py"
    "utils/anomaly_detector.py"
    "utils/unit_converter.py"
    "utils/csv_data_processor.py"
    "utils/python_error_handler.py"
    "comprehensive_analysis_refactor_plan.py"
)

# 创建备份目录
create_backup_dir() {
    mkdir -p "$BACKUP_DIR"
    log_info "创建备份目录: $BACKUP_DIR"
}

# 备份文件
backup_file() {
    local file="$1"
    local backup_file="${BACKUP_DIR}/$(basename "$file").backup"
    
    if [[ -f "$file" ]]; then
        cp "$file" "$backup_file"
        log_debug "备份文件: $file -> $backup_file"
        return 0
    else
        log_warn "文件不存在，跳过备份: $file"
        return 1
    fi
}

# 修复Shell脚本
fix_shell_script() {
    local file="$1"
    
    log_info "修复Shell脚本: $file"
    
    # 备份原文件
    if ! backup_file "$file"; then
        return 1
    fi
    
    # 获取组件名称
    local component_name=$(basename "$file" .sh)
    
    # 创建临时文件
    local temp_file="${file}.tmp"
    
    # 检查是否已经使用统一日志
    if grep -q "unified_logger.sh" "$file" 2>/dev/null; then
        log_debug "文件已使用统一日志，跳过: $file"
        return 0
    fi
    
    # 处理文件内容
    {
        # 保留shebang和初始注释
        head -20 "$file" | while IFS= read -r line; do
            echo "$line"
            # 在source config.sh后添加统一日志
            if [[ "$line" =~ source.*config\.sh ]]; then
                echo 'source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh"'
                echo ""
                echo "# 初始化统一日志管理器"
                echo "init_logger \"$component_name\" \$LOG_LEVEL \"\${LOGS_DIR}/${component_name}.log\""
                echo ""
            fi
        done
        
        # 处理剩余内容，替换日志调用
        tail -n +21 "$file" | sed \
            -e 's/echo "\([^"]*\)" | tee -a "\$[^"]*"/log_info "\1"/g' \
            -e 's/echo "✅ \([^"]*\)" | tee -a "\$[^"]*"/log_info "\1"/g' \
            -e 's/echo "⚠️ \([^"]*\)" | tee -a "\$[^"]*"/log_warn "\1"/g' \
            -e 's/echo "❌ \([^"]*\)" | tee -a "\$[^"]*"/log_error "\1"/g' \
            -e 's/echo "🔍 \([^"]*\)" | tee -a "\$[^"]*"/log_info "\1"/g' \
            -e 's/echo "\([^"]*\)" >> "\$[^"]*"/log_info "\1"/g' \
            -e 's/printf "\([^"]*\)" | tee -a "\$[^"]*"/log_info "\1"/g'
    } > "$temp_file"
    
    # 替换原文件
    mv "$temp_file" "$file"
    
    log_info "Shell脚本修复完成: $file"
}

# 修复Python脚本
fix_python_script() {
    local file="$1"
    
    log_info "修复Python脚本: $file"
    
    # 备份原文件
    if ! backup_file "$file"; then
        return 1
    fi
    
    # 检查是否已经使用统一日志
    if grep -q "from.*unified_logger import\|unified_logger" "$file" 2>/dev/null; then
        log_debug "文件已使用统一日志，跳过: $file"
        return 0
    fi
    
    # 创建临时文件
    local temp_file="${file}.tmp"
    
    # 处理文件内容
    python3 << EOF
import re

with open('$file', 'r', encoding='utf-8') as f:
    content = f.read()

# 替换logging导入
content = re.sub(r'^import logging$', 'from utils.unified_logger import get_logger', content, flags=re.MULTILINE)

# 替换logger初始化
content = re.sub(r'logger = logging\.getLogger\(__name__\)', 'logger = get_logger(__name__)', content)

# 替换basicConfig调用
content = re.sub(r'logging\.basicConfig\([^)]*\)', '# logging.basicConfig - replaced with unified logger', content)

# 添加统一日志导入（如果还没有）
if 'from utils.unified_logger import get_logger' not in content and 'import logging' in content:
    content = content.replace('import logging', 'from utils.unified_logger import get_logger')

with open('$temp_file', 'w', encoding='utf-8') as f:
    f.write(content)
EOF
    
    # 替换原文件
    mv "$temp_file" "$file"
    
    log_info "Python脚本修复完成: $file"
}

# 生成修复报告
generate_fix_report() {
    log_info "生成修复报告: $FIX_REPORT"
    
    cat > "$FIX_REPORT" << EOF
# 日志配置批量修复报告
生成时间: $(date)

## 修复概览

### 修复的Shell脚本
$(printf "- %s\n" "${SHELL_FILES_TO_FIX[@]}")

### 修复的Python脚本
$(printf "- %s\n" "${PYTHON_FILES_TO_FIX[@]}")

## 修复内容

### Shell脚本修复
1. 添加统一日志管理器引入
2. 初始化日志器配置
3. 替换旧的日志输出方式：
   - \`echo "信息" | tee -a "\$LOG_FILE"\` → \`log_info "信息"\`
   - \`echo "⚠️ 警告" | tee -a "\$LOG_FILE"\` → \`log_warn "警告"\`
   - \`echo "❌ 错误" | tee -a "\$LOG_FILE"\` → \`log_error "错误"\`

### Python脚本修复
1. 替换logging导入：
   - \`import logging\` → \`from utils.unified_logger import get_logger\`
2. 替换logger初始化：
   - \`logger = logging.getLogger(__name__)\` → \`logger = get_logger(__name__)\`
3. 注释掉basicConfig调用

## 备份信息
- 备份目录: $BACKUP_DIR
- 所有原文件已备份，可以随时回滚

## 验证建议
1. 运行各个组件确保功能正常
2. 检查日志输出格式是否统一
3. 验证日志文件是否正确生成

## 回滚方法
如需回滚，执行以下命令：
\`\`\`bash
# 恢复所有文件
for backup in $BACKUP_DIR/*.backup; do
    original=\$(basename "\$backup" .backup)
    cp "\$backup" "\$original"
done
\`\`\`
EOF
}

# 主修复流程
main() {
    log_info "开始批量修复日志配置..."
    
    create_backup_dir
    
    local fixed_shell=0
    local fixed_python=0
    local failed_files=()
    
    # 修复Shell脚本
    log_info "修复Shell脚本..."
    for file in "${SHELL_FILES_TO_FIX[@]}"; do
        if fix_shell_script "$file"; then
            ((fixed_shell++))
        else
            failed_files+=("$file")
        fi
    done
    
    # 修复Python脚本
    log_info "修复Python脚本..."
    for file in "${PYTHON_FILES_TO_FIX[@]}"; do
        if fix_python_script "$file"; then
            ((fixed_python++))
        else
            failed_files+=("$file")
        fi
    done
    
    # 生成报告
    generate_fix_report
    
    # 输出结果
    log_info "批量修复完成！"
    log_info "修复的Shell脚本: $fixed_shell 个"
    log_info "修复的Python脚本: $fixed_python 个"
    
    if [[ ${#failed_files[@]} -gt 0 ]]; then
        log_warn "修复失败的文件:"
        for file in "${failed_files[@]}"; do
            log_warn "  - $file"
        done
    fi
    
    log_info "备份目录: $BACKUP_DIR"
    log_info "修复报告: $FIX_REPORT"
    
    echo ""
    echo "🎉 日志配置批量修复完成！"
    echo "📋 修复报告: $FIX_REPORT"
    echo "💾 备份目录: $BACKUP_DIR"
    echo ""
    echo "建议接下来："
    echo "1. 测试各个组件功能"
    echo "2. 验证日志输出格式"
    echo "3. 检查日志文件生成"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
