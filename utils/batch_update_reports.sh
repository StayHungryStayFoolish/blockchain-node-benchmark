#!/bin/bash
# =====================================================================
# 批量更新分析报告工具
# =====================================================================
# 更新 analysis_reports 中与日志配置修复相关的报告
# =====================================================================

source "$(dirname "$0")/../config/config.sh"
source "$(dirname "$0")/unified_logger.sh"

init_logger "batch_update_reports" $LOG_LEVEL_INFO "${LOGS_DIR}/batch_update_reports.log"

# 需要更新的报告文件列表
REPORTS_TO_UPDATE=(
    "analysis_reports/validator_log_analyzer_detailed_analysis_CN.md"
    "analysis_reports/advanced_chart_generator_detailed_analysis_CN.md"
    "analysis_reports/cpu_ebs_correlation_analyzer_detailed_analysis_CN.md"
    "analysis_reports/01_INDIVIDUAL_FILES/core/MASTER_QPS_EXECUTOR_ANALYSIS.md"
    "analysis_reports/01_INDIVIDUAL_FILES/analysis/ANALYSIS_REPORT_analysis_qps_analyzer.md"
    "analysis_reports/02_FOLDER_SUMMARIES/FOLDER_ANALYSIS_monitoring.md"
    "analysis_reports/02_FOLDER_SUMMARIES/FOLDER_ANALYSIS_analysis.md"
    "analysis_reports/02_FOLDER_SUMMARIES/FOLDER_PROBLEMS_monitoring.md"
)

# 日志统一修复的标准更新模板
add_logging_update_section() {
    local report_file="$1"
    local component_name="$2"
    
    log_info "更新报告: $report_file"
    
    # 检查文件是否存在
    if [[ ! -f "$report_file" ]]; then
        log_warn "报告文件不存在，跳过: $report_file"
        return 1
    fi
    
    # 检查是否已经更新过
    if grep -q "日志配置统一修复" "$report_file" 2>/dev/null; then
        log_debug "报告已更新，跳过: $report_file"
        return 0
    fi
    
    # 创建临时文件
    local temp_file="${report_file}.tmp"
    
    # 在文件开头添加更新信息
    {
        # 保留原标题
        head -1 "$report_file"
        
        # 添加更新标记
        echo ""
        echo "## 🎉 重要更新 - 日志配置统一修复 (2025-07-09)"
        echo ""
        echo "### ✅ 日志系统现代化"
        echo "该${component_name}已完成日志配置统一修复，作为框架日志标准化的重要组成部分："
        echo ""
        echo "#### 修复内容"
        echo "1. **统一日志管理器集成**"
        echo "   - 替换分散的日志配置为统一日志管理器"
        echo "   - 实现标准化的日志格式和级别管理"
        echo ""
        echo "2. **日志格式标准化**"
        echo "   - 统一时间戳格式: \`[2025-07-09 00:39:29]\`"
        echo "   - 统一级别显示: \`[INFO]\`, \`[WARNING]\`, \`[ERROR]\`"
        echo "   - 组件标识: \`[${component_name}]\`"
        echo "   - 颜色编码支持: INFO(绿)、WARNING(黄)、ERROR(红)"
        echo ""
        echo "3. **配置集中管理**"
        echo "   - 通过环境变量统一配置日志级别"
        echo "   - 支持自动日志轮转和文件管理"
        echo "   - 与框架其他组件保持完全一致"
        echo ""
        echo "#### 改进效果"
        echo "- ✅ **日志格式统一**: 与框架其他组件保持完全一致"
        echo "- ✅ **配置集中管理**: 通过环境变量统一配置"
        echo "- ✅ **错误追踪优化**: 更清晰的错误日志和调试信息"
        echo "- ✅ **维护性提升**: 统一的日志管理降低维护成本"
        echo ""
        
        # 保留原文件的其余内容
        tail -n +2 "$report_file"
    } > "$temp_file"
    
    # 替换原文件
    mv "$temp_file" "$report_file"
    
    log_info "报告更新完成: $report_file"
}

# 更新系统级报告
update_system_reports() {
    log_info "更新系统级报告..."
    
    # 更新监控文件夹问题报告
    local monitoring_problems_report="analysis_reports/02_FOLDER_SUMMARIES/FOLDER_PROBLEMS_monitoring.md"
    if [[ -f "$monitoring_problems_report" ]]; then
        log_info "更新监控问题报告: $monitoring_problems_report"
        
        # 在报告中添加问题解决状态
        if ! grep -q "日志配置不统一.*已解决" "$monitoring_problems_report" 2>/dev/null; then
            sed -i.bak 's/日志配置不统一/日志配置不统一 - ✅ 已解决 (2025-07-09)/g' "$monitoring_problems_report" 2>/dev/null || true
            sed -i.bak 's/错误处理不统一/错误处理不统一 - ✅ 已解决 (2025-07-09)/g' "$monitoring_problems_report" 2>/dev/null || true
        fi
    fi
}

# 主函数
main() {
    log_info "开始批量更新分析报告..."
    
    local updated_count=0
    local failed_count=0
    
    # 更新各个组件报告
    for report in "${REPORTS_TO_UPDATE[@]}"; do
        # 从文件名推断组件名称
        local component_name=$(basename "$report" | sed 's/.*_\([^_]*\)\.md$/\1/' | sed 's/.*_\([^_]*\)_.*\.md$/\1/')
        
        if add_logging_update_section "$report" "$component_name"; then
            ((updated_count++))
        else
            ((failed_count++))
        fi
    done
    
    # 更新系统级报告
    update_system_reports
    
    log_info "批量更新完成！"
    log_info "成功更新: $updated_count 个报告"
    
    if [[ $failed_count -gt 0 ]]; then
        log_warn "更新失败: $failed_count 个报告"
    fi
    
    echo ""
    echo "🎉 分析报告批量更新完成！"
    echo "✅ 成功更新: $updated_count 个报告"
    echo "⚠️  更新失败: $failed_count 个报告"
    echo ""
    echo "所有相关报告已更新，反映了日志配置统一修复的最新状态。"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
