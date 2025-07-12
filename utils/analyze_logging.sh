#!/bin/bash
# =====================================================================
# 日志配置分析工具 - 简化版
# =====================================================================
# 分析项目中的日志配置现状，生成待修复清单
# 适用于开发阶段的代码审查和标准化
# =====================================================================

source "$(dirname "$0")/../config/config.sh"
source "$(dirname "$0")/unified_logger.sh"

init_logger "log_analyzer" $LOG_LEVEL_INFO "${LOGS_DIR}/log_analysis.log"

readonly ANALYSIS_REPORT="${LOGS_DIR}/logging_analysis_$(date +%Y%m%d_%H%M%S).md"

# 分析日志配置现状
analyze_logging_status() {
    log_info "开始分析项目日志配置现状..."
    
    echo "# 项目日志配置分析报告" > "$ANALYSIS_REPORT"
    echo "生成时间: $(date)" >> "$ANALYSIS_REPORT"
    echo "" >> "$ANALYSIS_REPORT"
    
    # 统计信息
    local total_shell_files=0
    local total_python_files=0
    local shell_with_logging=0
    local python_with_logging=0
    
    echo "## 📊 统计概览" >> "$ANALYSIS_REPORT"
    echo "" >> "$ANALYSIS_REPORT"
    
    # 分析Shell脚本
    echo "### Shell脚本分析" >> "$ANALYSIS_REPORT"
    echo "" >> "$ANALYSIS_REPORT"
    echo "| 文件 | 日志方式 | 状态 | 建议 |" >> "$ANALYSIS_REPORT"
    echo "|------|----------|------|------|" >> "$ANALYSIS_REPORT"
    
    for file in $(find . -name "*.sh" -not -path "./backups/*" -not -path "./utils/migrate_logging.sh"); do
        [[ -f "$file" ]] || continue
        ((total_shell_files++))
        
        local status="❌ 未统一"
        local suggestion="需要集成统一日志"
        
        if grep -q "unified_logger.sh" "$file" 2>/dev/null; then
            status="✅ 已统一"
            suggestion="无需修改"
        elif grep -q "tee.*log\|echo.*log\|printf.*log" "$file" 2>/dev/null; then
            ((shell_with_logging++))
            status="⚠️ 旧格式"
            suggestion="替换为统一日志"
        fi
        
        echo "| $file | $(grep -c "tee\|echo.*log" "$file" 2>/dev/null || echo "0") 处 | $status | $suggestion |" >> "$ANALYSIS_REPORT"
    done
    
    echo "" >> "$ANALYSIS_REPORT"
    
    # 分析Python脚本
    echo "### Python脚本分析" >> "$ANALYSIS_REPORT"
    echo "" >> "$ANALYSIS_REPORT"
    echo "| 文件 | 日志方式 | 状态 | 建议 |" >> "$ANALYSIS_REPORT"
    echo "|------|----------|------|------|" >> "$ANALYSIS_REPORT"
    
    for file in $(find . -name "*.py" -not -path "./backups/*"); do
        [[ -f "$file" ]] || continue
        ((total_python_files++))
        
        local status="❌ 未统一"
        local suggestion="需要集成统一日志"
        
        if grep -q "from.*unified_logger import\|unified_logger" "$file" 2>/dev/null; then
            status="✅ 已统一"
            suggestion="无需修改"
        elif grep -q "import logging\|getLogger" "$file" 2>/dev/null; then
            ((python_with_logging++))
            status="⚠️ 标准logging"
            suggestion="替换为统一日志"
        fi
        
        echo "| $file | $(grep -c "logging\|getLogger" "$file" 2>/dev/null || echo "0") 处 | $status | $suggestion |" >> "$ANALYSIS_REPORT"
    done
    
    echo "" >> "$ANALYSIS_REPORT"
    
    # 生成统计摘要
    echo "## 📈 统计摘要" >> "$ANALYSIS_REPORT"
    echo "" >> "$ANALYSIS_REPORT"
    echo "- **Shell脚本总数**: $total_shell_files" >> "$ANALYSIS_REPORT"
    echo "- **Python脚本总数**: $total_python_files" >> "$ANALYSIS_REPORT"
    echo "- **Shell脚本需要修复**: $shell_with_logging" >> "$ANALYSIS_REPORT"
    echo "- **Python脚本需要修复**: $python_with_logging" >> "$ANALYSIS_REPORT"
    echo "" >> "$ANALYSIS_REPORT"
    
    # 生成修复建议
    echo "## 🔧 修复建议" >> "$ANALYSIS_REPORT"
    echo "" >> "$ANALYSIS_REPORT"
    echo "### Shell脚本标准模板" >> "$ANALYSIS_REPORT"
    echo '```bash' >> "$ANALYSIS_REPORT"
    echo '# 在脚本开头添加' >> "$ANALYSIS_REPORT"
    echo 'source "$(dirname "$0")/../utils/unified_logger.sh"' >> "$ANALYSIS_REPORT"
    echo 'init_logger "component_name" $LOG_LEVEL_INFO "${LOGS_DIR}/component_name.log"' >> "$ANALYSIS_REPORT"
    echo '' >> "$ANALYSIS_REPORT"
    echo '# 替换日志调用' >> "$ANALYSIS_REPORT"
    echo '# echo "信息" | tee -a "$LOG_FILE"  →  log_info "信息"' >> "$ANALYSIS_REPORT"
    echo '# echo "⚠️ 警告" | tee -a "$LOG_FILE"  →  log_warn "警告"' >> "$ANALYSIS_REPORT"
    echo '```' >> "$ANALYSIS_REPORT"
    echo "" >> "$ANALYSIS_REPORT"
    
    echo "### Python脚本标准模板" >> "$ANALYSIS_REPORT"
    echo '```python' >> "$ANALYSIS_REPORT"
    echo '# 替换导入' >> "$ANALYSIS_REPORT"
    echo '# import logging' >> "$ANALYSIS_REPORT"
    echo '# logger = logging.getLogger(__name__)' >> "$ANALYSIS_REPORT"
    echo '' >> "$ANALYSIS_REPORT"
    echo '# 使用统一日志管理器' >> "$ANALYSIS_REPORT"
    echo 'from utils.unified_logger import get_logger' >> "$ANALYSIS_REPORT"
    echo 'logger = get_logger(__name__)' >> "$ANALYSIS_REPORT"
    echo '```' >> "$ANALYSIS_REPORT"
    
    log_info "分析完成，报告保存至: $ANALYSIS_REPORT"
    echo "📋 分析报告: $ANALYSIS_REPORT"
}

# 主函数
main() {
    case "${1:-analyze}" in
        "analyze")
            analyze_logging_status
            ;;
        "help"|*)
            echo "📋 日志配置分析工具"
            echo "==================="
            echo ""
            echo "用法: $0 [analyze]"
            echo ""
            echo "功能:"
            echo "  analyze  - 分析项目中的日志配置现状"
            echo "  help     - 显示此帮助信息"
            echo ""
            echo "输出:"
            echo "  - 生成详细的分析报告(Markdown格式)"
            echo "  - 提供具体的修复建议和模板"
            echo "  - 统计需要修复的文件数量"
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
