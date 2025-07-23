#!/bin/bash

# =====================================================================
# Solana 区块链节点性能基准测试框架启动脚本
# Blockchain Node Performance Benchmark Framework Entry Point
# =====================================================================

# 部署环境检查
check_deployment() {
    local current_path="$(pwd)"
    local script_path="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    echo "🔍 验证部署环境..." >&2
    echo "   当前位置: $script_path" >&2
    
    # 基本权限检查
    if [[ ! -r "$script_path" ]]; then
        echo "❌ 错误: 无法读取框架目录" >&2
        echo "💡 解决方案: 检查目录权限" >&2
        return 1
    fi
    
    echo "✅ 部署环境验证通过" >&2
}

# 显示框架信息
show_framework_info() {
    echo "🚀 Blockchain Node Performance Benchmark Framework"
    echo ""
    echo "📊 支持的测试模式:"
    echo "   • 快速验证测试 (7分钟)   - 基础性能验证"
    echo "   • 标准性能测试 (15分钟)  - 全面性能评估"
    echo "   • 极限压力测试 (2小时)   - 智能瓶颈检测"
    echo ""
    echo "🔍 监控能力:"
    echo "   • 49-67个性能指标实时监控"
    echo "   • CPU、内存、EBS存储、网络、ENA限制"
    echo "   • 智能瓶颈检测和根因分析"
    echo "   • 瓶颈-日志时间关联分析"
    echo ""
    echo "📈 分析功能:"
    echo "   • 机器学习异常检测"
    echo "   • 多维度性能关联分析"
    echo "   • HTML报告和PNG图表生成"
    echo "   • 历史测试对比和趋势分析"
    echo ""
}

# 执行部署检查
if ! check_deployment; then
    exit 1
fi

# 如果没有参数，显示框架信息
if [[ $# -eq 0 ]]; then
    show_framework_info
    echo "💡 使用 ./blockchain_node_benchmark.sh --help 查看详细使用说明"
    echo ""
    exit 0
fi

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 加载配置和共享函数
source "${SCRIPT_DIR}/config/config.sh"
source "${SCRIPT_DIR}/core/common_functions.sh"
source "${SCRIPT_DIR}/utils/error_handler.sh"

# 设置错误处理
setup_error_handling "$(basename "$0")" "区块链节点基准测试框架"
log_script_start "$(basename "$0")"

# 全局变量
MONITORING_PIDS=()
TEST_SESSION_ID="session_$(date +%Y%m%d_%H%M%S)"
BOTTLENECK_DETECTED=false
BOTTLENECK_INFO=""

# 清理函数
cleanup_framework() {
    echo "🧹 执行框架清理..."
    
    # 停止监控系统
    stop_monitoring_system
    
    # 清理临时文件
    cleanup_temp_files
    
    echo "✅ 框架清理完成"
}

# 设置清理陷阱
trap cleanup_framework EXIT INT TERM

# 准备测试数据
prepare_test_data() {
    echo "📊 准备测试数据..."
    
    # 检查账户文件是否存在
    if [[ ! -f "$ACCOUNTS_OUTPUT_FILE" ]]; then
        echo "🔍 获取活跃账户..."
        if [[ -f "${SCRIPT_DIR}/tools/fetch_active_accounts.py" ]]; then
            python3 "${SCRIPT_DIR}/tools/fetch_active_accounts.py" \
                --rpc-url "$LOCAL_RPC_URL" \
                --output "$ACCOUNTS_OUTPUT_FILE" \
                --count "$ACCOUNT_COUNT"
            
            if [[ $? -eq 0 && -f "$ACCOUNTS_OUTPUT_FILE" ]]; then
                echo "✅ 账户获取成功: $(wc -l < "$ACCOUNTS_OUTPUT_FILE") 个账户"
            else
                echo "❌ 账户获取失败"
                return 1
            fi
        else
            echo "❌ 账户获取脚本不存在: ${SCRIPT_DIR}/tools/fetch_active_accounts.py"
            echo "   请检查文件是否存在和路径是否正确"
            return 1
        fi
    else
        echo "✅ 账户文件已存在: $(wc -l < "$ACCOUNTS_OUTPUT_FILE") 个账户"
    fi
    
    # 生成vegeta目标文件
    echo "🎯 生成Vegeta目标文件 (RPC模式: $RPC_MODE)..."
    if [[ -f "${SCRIPT_DIR}/tools/target_generator.sh" ]]; then
        "${SCRIPT_DIR}/tools/target_generator.sh" \
            --accounts-file "$ACCOUNTS_OUTPUT_FILE" \
            --rpc-url "$LOCAL_RPC_URL" \
            --rpc-mode "$RPC_MODE" \
            --output-single "$SINGLE_METHOD_TARGETS_FILE" \
            --output-mixed "$MIXED_METHOD_TARGETS_FILE"
        
        if [[ $? -eq 0 ]]; then
            echo "✅ Vegeta目标文件生成成功 (RPC模式: $RPC_MODE)"
            if [[ "$RPC_MODE" == "mixed" ]]; then
                echo "   混合方法目标: $MIXED_METHOD_TARGETS_FILE"
            else
                echo "   单一方法目标: $SINGLE_METHOD_TARGETS_FILE"
            fi
        else
            echo "❌ Vegeta目标文件生成失败"
            return 1
        fi
    else
        echo "❌ 目标生成脚本不存在: tools/target_generator.sh"
        return 1
    fi
    
    return 0
}

# 启动监控系统
start_monitoring_system() {
    echo "📊 启动监控系统..."
    
    # 启动监控协调器
    if [[ -f "${SCRIPT_DIR}/monitoring/monitoring_coordinator.sh" ]]; then
        echo "🚀 启动监控协调器..."
        "${SCRIPT_DIR}/monitoring/monitoring_coordinator.sh" start &
        local coordinator_pid=$!
        MONITORING_PIDS+=($coordinator_pid)
        echo "✅ 监控协调器已启动 (PID: $coordinator_pid)"
        
        # 等待监控系统初始化
        sleep 5
        
        # 验证监控系统状态
        if kill -0 $coordinator_pid 2>/dev/null; then
            echo "✅ 监控系统运行正常"
            return 0
        else
            echo "❌ 监控系统启动失败"
            return 1
        fi
    else
        echo "❌ 监控协调器不存在: monitoring/monitoring_coordinator.sh"
        return 1
    fi
}

# 停止监控系统
stop_monitoring_system() {
    echo "🛑 停止监控系统..."
    
    # 检查是否有监控进程需要停止
    if [[ ${#MONITORING_PIDS[@]} -eq 0 ]]; then
        echo "ℹ️  没有监控进程需要停止"
        return 0
    fi
    
    # 停止监控协调器
    if [[ -f "${SCRIPT_DIR}/monitoring/monitoring_coordinator.sh" ]]; then
        "${SCRIPT_DIR}/monitoring/monitoring_coordinator.sh" stop
    fi
    
    # 停止所有监控进程
    for pid in "${MONITORING_PIDS[@]}"; do
        if kill -0 $pid 2>/dev/null; then
            echo "🛑 停止监控进程 PID: $pid"
            kill -TERM $pid 2>/dev/null
            sleep 2
            if kill -0 $pid 2>/dev/null; then
                kill -KILL $pid 2>/dev/null
            fi
        fi
    done
    
    MONITORING_PIDS=()
    echo "✅ 监控系统已停止"
}

# 执行核心QPS测试
execute_core_qps_test() {
    echo "[START] Executing core QPS test (RPC mode: $RPC_MODE)..."
    
    # Create QPS test status marker file - using atomic operation for reliability
    echo "running" > "$TMP_DIR/qps_test_status.tmp"
    mv "$TMP_DIR/qps_test_status.tmp" "$TMP_DIR/qps_test_status"
    echo "[STATUS] QPS test status marker created: $TMP_DIR/qps_test_status"
    
    # 构建参数数组，过滤掉RPC模式参数，因为我们会单独添加
    local executor_args=()
    
    # 添加非RPC模式的参数
    for arg in "$@"; do
        case $arg in
            --single|--mixed)
                # RPC模式参数跳过，我们会根据RPC_MODE变量添加
                ;;
            *)
                executor_args+=("$arg")
                ;;
        esac
    done
    
    # 根据RPC_MODE变量添加正确的RPC模式参数
    executor_args+=("--$RPC_MODE")
    
    # 调用master_qps_executor.sh
    "${SCRIPT_DIR}/core/master_qps_executor.sh" "${executor_args[@]}"
    local test_result=$?
    
    # Delete QPS test status marker file - safe deletion
    if [[ -f "$TMP_DIR/qps_test_status" ]]; then
        rm -f "$TMP_DIR/qps_test_status"
        echo "[STATUS] QPS test status marker deleted"
    else
        echo "[WARN] QPS test status marker file does not exist, may have been deleted"
    fi
    
    # 检查是否检测到瓶颈
    if [[ -f "${MEMORY_SHARE_DIR}/bottleneck_status.json" ]]; then
        local status_data=$(cat "${MEMORY_SHARE_DIR}/bottleneck_status.json" 2>/dev/null)
        if echo "$status_data" | grep -q "bottleneck_detected.*true"; then
            BOTTLENECK_DETECTED=true
            # 从瓶颈状态文件获取瓶颈摘要
            BOTTLENECK_INFO=$(echo "$status_data" | jq -r '.bottleneck_summary // "Unknown bottleneck"' 2>/dev/null || echo "Unknown bottleneck")
            echo "🚨 检测到性能瓶颈: $BOTTLENECK_INFO"
        fi
    fi
    
    return $test_result
}

# 处理测试结果
process_test_results() {
    echo "🔄 处理测试结果..."
    
    # AWS基准转换
    echo "📊 执行AWS基准转换..."
    if [[ -f "${SCRIPT_DIR}/utils/ebs_converter.sh" ]]; then
        "${SCRIPT_DIR}/utils/ebs_converter.sh" --auto-convert
        echo "✅ EBS基准转换完成"
    else
        echo "⚠️ EBS转换脚本不存在，跳过转换"
    fi
    
    # 单位转换
    if [[ -f "${SCRIPT_DIR}/utils/unit_converter.py" ]]; then
        python3 "${SCRIPT_DIR}/utils/unit_converter.py" --auto-process
        echo "✅ 单位转换完成"
    else
        echo "⚠️ 单位转换脚本不存在，跳过转换"
    fi
    
    # 归档测试结果
    echo "📦 归档测试结果..."
    if [[ -f "${SCRIPT_DIR}/tools/benchmark_archiver.sh" ]]; then
        # 确定基准测试模式
        local benchmark_mode="standard"  # 默认值
        for arg in "$@"; do
            case $arg in
                --quick) benchmark_mode="quick" ;;
                --standard) benchmark_mode="standard" ;;
                --intensive) benchmark_mode="intensive" ;;
            esac
        done
        
        # 获取最大QPS (从QPS状态文件或跳过归档)
        local max_qps=""
        if [[ -f "${QPS_STATUS_FILE}" ]]; then
            max_qps=$(jq -r '.max_successful_qps // empty' "${QPS_STATUS_FILE}" 2>/dev/null || echo "")
        fi
        
        # 如果无法获取有效的QPS值，跳过归档
        if [[ -z "$max_qps" ]] || [[ "$max_qps" == "0" ]] || [[ "$max_qps" == "null" ]]; then
            echo "⚠️ 无法获取有效的最大QPS值，跳过测试结果归档"
            echo "💡 QPS状态文件: ${QPS_STATUS_FILE}"
            return 0
        fi
        
        # 调用归档工具 (瓶颈信息将自动检测)
        "${SCRIPT_DIR}/tools/benchmark_archiver.sh" --archive \
            --benchmark-mode "$benchmark_mode" \
            --max-qps "$max_qps"
        
        if [[ $? -eq 0 ]]; then
            echo "✅ 测试结果归档完成"
        else
            echo "⚠️ 测试结果归档失败"
        fi
    else
        echo "⚠️ 归档脚本不存在，跳过归档"
    fi
    
    return 0
}

# 执行数据分析 - 增强版
execute_data_analysis() {
    echo "🔍 执行数据分析..."
    
    # 查找最新的性能数据文件 - 修复文件名模式 (跨平台兼容)
    local latest_csv
    if [[ "$(uname -s)" == "Darwin" ]]; then
        # macOS版本 - 使用stat命令
        latest_csv=$(find "$LOGS_DIR" -name "unified_monitor_*.csv" -type f -exec stat -f "%m %N" {} \; 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
    else
        # Linux版本 - 使用printf
        latest_csv=$(find "$LOGS_DIR" -name "unified_monitor_*.csv" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
    fi
    
    if [[ -z "$latest_csv" ]]; then
        echo "[ERROR] No unified_monitor CSV file found in $LOGS_DIR"
        echo "[DEBUG] Available CSV files:"
        ls -la "$LOGS_DIR"/*.csv 2>/dev/null || echo "  No CSV files found"
        echo "[DEBUG] LOGS_DIR = $LOGS_DIR"
        return 1
    fi
    
    echo "[INFO] Using monitoring data file: $(basename "$latest_csv")"
    echo "[INFO] File size: $(wc -l < "$latest_csv") lines"
    
    # 如果检测到瓶颈，执行瓶颈专项分析
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        echo "🚨 执行瓶颈专项分析..."
        
        # 读取瓶颈详细信息
        local bottleneck_details=""
        if [[ -f "$QPS_STATUS_FILE" ]]; then
            bottleneck_details=$(cat "$QPS_STATUS_FILE")
            local bottleneck_qps=$(echo "$bottleneck_details" | jq -r '.bottleneck_qps // 0')
            local max_qps=$(echo "$bottleneck_details" | jq -r '.max_qps_achieved // 0')
            local severity=$(echo "$bottleneck_details" | jq -r '.severity // "medium"')
            
            echo "📊 瓶颈详情: QPS=$bottleneck_qps, 最大成功QPS=$max_qps, 严重程度=$severity"
        fi
        
        # 瓶颈检测器深度分析
        if [[ -f "${SCRIPT_DIR}/monitoring/bottleneck_detector.sh" ]]; then
            echo "🔍 执行瓶颈检测器深度分析..."
            "${SCRIPT_DIR}/monitoring/bottleneck_detector.sh" \
                --analyze \
                --csv-file "$latest_csv" \
                --bottleneck-info "$bottleneck_details"
        fi
        
        # EBS瓶颈专项分析
        if [[ -f "${SCRIPT_DIR}/tools/ebs_bottleneck_detector.sh" ]]; then
            echo "💾 执行EBS瓶颈专项分析..."
            "${SCRIPT_DIR}/tools/ebs_bottleneck_detector.sh" \
                --post-analysis \
                --csv-file "$latest_csv" \
                --bottleneck-mode
        fi
        
        # 瓶颈时间窗口分析
        execute_bottleneck_window_analysis "$latest_csv" "$bottleneck_details"
        
        # 性能悬崖分析
        execute_performance_cliff_analysis "$latest_csv" "$bottleneck_details"
    fi
    
    # 执行所有标准分析脚本
    local analysis_scripts=(
        "analysis/comprehensive_analysis.py"
        "analysis/cpu_ebs_correlation_analyzer.py"
        "analysis/qps_analyzer.py"
        "analysis/rpc_deep_analyzer.py"
        "analysis/validator_log_analyzer.py"
    )
    
    for script in "${analysis_scripts[@]}"; do
        if [[ -f "${SCRIPT_DIR}/$script" ]]; then
            echo "🔍 执行分析: $(basename "$script")"
            
            # 如果检测到瓶颈，传递瓶颈模式参数
            if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
                python3 "${SCRIPT_DIR}/$script" "$latest_csv" --bottleneck-mode
            else
                python3 "${SCRIPT_DIR}/$script" "$latest_csv"
            fi
        else
            echo "⚠️ 分析脚本不存在: $script"
        fi
    done
    
    echo "✅ 数据分析完成"
    return 0
}

# 执行瓶颈时间窗口分析
execute_bottleneck_window_analysis() {
    local csv_file="$1"
    local bottleneck_info="$2"
    
    echo "🕐 执行瓶颈时间窗口分析..."
    
    if [[ -z "$bottleneck_info" ]]; then
        echo "⚠️ 无瓶颈信息，跳过时间窗口分析"
        return
    fi
    
    # 提取瓶颈时间信息
    local bottleneck_time=$(echo "$bottleneck_info" | jq -r '.detection_time // ""')
    local window_start=$(echo "$bottleneck_info" | jq -r '.analysis_window.start_time // ""')
    local window_end=$(echo "$bottleneck_info" | jq -r '.analysis_window.end_time // ""')
    
    if [[ -n "$bottleneck_time" ]]; then
        echo "📊 瓶颈时间窗口: $window_start 到 $window_end"
        
        # 调用时间窗口分析工具
        if [[ -f "${SCRIPT_DIR}/analysis/comprehensive_analysis.py" ]]; then
            python3 "${SCRIPT_DIR}/analysis/comprehensive_analysis.py" \
                "$csv_file" \
                --benchmark-mode "$BENCHMARK_MODE" \
                --time-window \
                --start-time "$window_start" \
                --end-time "$window_end" \
                --bottleneck-time "$bottleneck_time"
        fi
    fi
}

# 执行性能悬崖分析
execute_performance_cliff_analysis() {
    local csv_file="$1"
    local bottleneck_info="$2"
    
    echo "📉 执行性能悬崖分析..."
    
    if [[ -z "$bottleneck_info" ]]; then
        echo "⚠️ 无瓶颈信息，跳过性能悬崖分析"
        return
    fi
    
    local max_qps=$(echo "$bottleneck_info" | jq -r '.max_qps_achieved // 0')
    local bottleneck_qps=$(echo "$bottleneck_info" | jq -r '.bottleneck_qps // 0')
    
    if [[ $max_qps -gt 0 && $bottleneck_qps -gt 0 ]]; then
        local performance_drop=$(echo "scale=2; ($bottleneck_qps - $max_qps) * 100 / $max_qps" | bc)
        echo "📊 性能悬崖: 从 ${max_qps} QPS 到 ${bottleneck_qps} QPS (${performance_drop}%)"
        
        # 调用性能悬崖分析工具
        if [[ -f "${SCRIPT_DIR}/analysis/qps_analyzer.py" ]]; then
            python3 "${SCRIPT_DIR}/analysis/qps_analyzer.py" \
                "$csv_file" \
                --benchmark-mode "$BENCHMARK_MODE" \
                --cliff-analysis \
                --max-qps "$max_qps" \
                --bottleneck-qps "$bottleneck_qps"
        fi
    fi
}

# 生成最终报告 - 增强版
generate_final_reports() {
    echo "📊 生成最终报告..."
    
    # 查找最新的性能数据文件
    local latest_csv=$(find "$LOGS_DIR" -name "performance_*.csv" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
    
    if [[ -z "$latest_csv" ]]; then
        echo "⚠️ 警告: 没有找到性能数据文件"
        return 1
    fi
    
    # 准备报告生成参数
    local report_params=("$latest_csv")
    
    # 如果检测到瓶颈，添加瓶颈模式参数
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        report_params+=("--bottleneck-mode")
        
        # 添加瓶颈信息文件
        if [[ -f "$QPS_STATUS_FILE" ]]; then
            report_params+=("--bottleneck-info" "$QPS_STATUS_FILE")
        fi
        
        echo "🚨 瓶颈模式报告生成"
    fi
    
    # 生成HTML报告
    if [[ -f "${SCRIPT_DIR}/visualization/report_generator.py" ]]; then
        echo "📄 生成HTML报告..."
        python3 "${SCRIPT_DIR}/visualization/report_generator.py" "${report_params[@]}"
        echo "✅ HTML报告已生成"
    else
        echo "⚠️ HTML报告生成器不存在"
    fi
    
    # 生成性能图表
    if [[ -f "${SCRIPT_DIR}/visualization/performance_visualizer.py" ]]; then
        echo "📈 生成性能图表..."
        python3 "${SCRIPT_DIR}/visualization/performance_visualizer.py" "${report_params[@]}"
        echo "✅ 性能图表已生成"
    else
        echo "⚠️ 性能图表生成器不存在"
    fi
    
    # 生成高级图表
    if [[ -f "${SCRIPT_DIR}/visualization/advanced_chart_generator.py" ]]; then
        echo "📊 生成高级图表..."
        python3 "${SCRIPT_DIR}/visualization/advanced_chart_generator.py" "${report_params[@]}"
        echo "✅ 高级图表已生成"
    else
        echo "⚠️ 高级图表生成器不存在"
    fi
    
    # 生成瓶颈专项报告
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        generate_bottleneck_summary_report
    fi
    
    # 显示报告位置和摘要
    display_final_report_summary
    
    return 0
}

# 生成瓶颈摘要报告
generate_bottleneck_summary_report() {
    echo "🚨 生成瓶颈摘要报告..."
    
    local bottleneck_summary_file="${REPORTS_DIR}/bottleneck_summary_$(date +%Y%m%d_%H%M%S).md"
    
    # 读取瓶颈信息
    local bottleneck_info=""
    if [[ -f "$QPS_STATUS_FILE" ]]; then
        bottleneck_info=$(cat "$QPS_STATUS_FILE")
    fi
    
    # 生成Markdown格式的瓶颈摘要
    cat > "$bottleneck_summary_file" << EOF
# 🚨 性能瓶颈检测报告

## 📊 测试摘要

- **测试时间**: $(date)
- **测试会话**: $TEST_SESSION_ID
- **瓶颈状态**: ✅ 检测到性能瓶颈

## 🎯 瓶颈详情

EOF
    
    if [[ -n "$bottleneck_info" ]]; then
        local max_qps=$(echo "$bottleneck_info" | jq -r '.max_qps_achieved // 0')
        local bottleneck_qps=$(echo "$bottleneck_info" | jq -r '.bottleneck_qps // 0')
        local severity=$(echo "$bottleneck_info" | jq -r '.severity // "unknown"')
        local reasons=$(echo "$bottleneck_info" | jq -r '.bottleneck_reasons // "未知"')
        local detection_time=$(echo "$bottleneck_info" | jq -r '.detection_time // "未知"')
        
        cat >> "$bottleneck_summary_file" << EOF
- **最大成功QPS**: $max_qps
- **瓶颈触发QPS**: $bottleneck_qps
- **严重程度**: $severity
- **检测时间**: $detection_time
- **瓶颈原因**: $reasons

## 🔍 系统建议

EOF
        
        # 添加建议
        local recommendations=$(echo "$bottleneck_info" | jq -r '.recommendations[]?' 2>/dev/null)
        if [[ -n "$recommendations" ]]; then
            echo "$recommendations" | while read -r recommendation; do
                echo "- $recommendation" >> "$bottleneck_summary_file"
            done
        else
            echo "- 请查看详细分析报告获取优化建议" >> "$bottleneck_summary_file"
        fi
    fi
    
    cat >> "$bottleneck_summary_file" << EOF

## 📋 相关文件

- **详细瓶颈分析**: $QPS_STATUS_FILE
- **瓶颈事件日志**: ${LOGS_DIR}/bottleneck_events.jsonl
- **性能数据**: $(find "$LOGS_DIR" -name "performance_*.csv" | head -1)

## 🎯 下一步行动

1. 查看HTML报告了解详细性能分析
2. 检查瓶颈分析文件了解根本原因
3. 根据建议优化系统配置
4. 重新运行测试验证改进效果

---
*报告生成时间: $(date)*
EOF
    
    echo "📄 瓶颈摘要报告: $(basename "$bottleneck_summary_file")"
}

# 显示最终报告摘要
display_final_report_summary() {
    echo ""
    echo "🎉 测试完成！报告摘要："
    echo "================================"
    echo "📁 报告目录: $REPORTS_DIR"
    
    # HTML报告
    local html_report=$(find "$REPORTS_DIR" -name "*.html" -type f | head -1)
    if [[ -n "$html_report" ]]; then
        echo "📄 HTML报告: $(basename "$html_report")"
    fi
    
    # 图表文件
    local chart_count=$(find "$REPORTS_DIR" -name "*.png" -type f | wc -l)
    echo "📊 图表文件: $chart_count 个PNG文件"
    
    # 瓶颈相关报告
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        echo ""
        echo "🚨 瓶颈检测结果："
        
        if [[ -f "$QPS_STATUS_FILE" ]]; then
            local max_qps=$(jq -r '.max_qps_achieved // 0' "$QPS_STATUS_FILE" 2>/dev/null)
            local bottleneck_qps=$(jq -r '.bottleneck_qps // 0' "$QPS_STATUS_FILE" 2>/dev/null)
            echo "🏆 最大成功QPS: $max_qps"
            echo "🚨 瓶颈触发QPS: $bottleneck_qps"
        fi
        
        local bottleneck_summary=$(find "$REPORTS_DIR" -name "bottleneck_summary_*.md" -type f | head -1)
        if [[ -n "$bottleneck_summary" ]]; then
            echo "📋 瓶颈摘要: $(basename "$bottleneck_summary")"
        fi
    fi
    
    echo ""
    echo "🎯 建议的下一步："
    echo "1. 打开HTML报告查看详细分析"
    echo "2. 检查PNG图表了解性能趋势"
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        echo "3. 查看瓶颈摘要报告了解优化建议"
        echo "4. 根据建议优化系统后重新测试"
    else
        echo "3. 考虑运行极限测试模式找出性能上限"
    fi
}

# 清理临时文件
cleanup_temp_files() {
    echo "🧹 清理临时文件..."
    
    # 清理会话临时目录
    if [[ -d "$TEST_SESSION_DIR" ]]; then
        rm -rf "$TEST_SESSION_DIR"
    fi
    
    # 清理状态文件
    if [[ -f "$QPS_STATUS_FILE" ]]; then
        rm -f "$QPS_STATUS_FILE"
    fi
}

# 解析RPC模式参数
parse_rpc_mode_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --single)
                RPC_MODE="single"
                shift
                ;;
            --mixed)
                RPC_MODE="mixed"
                shift
                ;;
            *)
                # 其他参数继续传递
                shift
                ;;
        esac
    done
}

# 主执行函数
main() {
    # 保存原始参数用于后续传递
    local original_args=("$@")
    
    # 解析RPC模式参数
    parse_rpc_mode_args "$@"
    
    echo "🚀 启动区块链节点性能基准测试框架"
    echo "   RPC模式: $RPC_MODE"
    echo "   测试会话ID: $TEST_SESSION_ID"
    echo ""
    
    # 显示框架信息
    show_framework_info
    
    # 检查部署环境
    if ! check_deployment; then
        exit 1
    fi
    
    # 注意：目录初始化已在config.sh中完成，无需重复执行
    
    # 阶段1: 准备测试数据
    echo "📋 阶段1: 准备测试数据"
    if ! prepare_test_data; then
        echo "❌ 测试数据准备失败"
        exit 1
    fi
    
    # 阶段2: 启动监控系统
    echo "📋 阶段2: 启动监控系统"
    if ! start_monitoring_system; then
        echo "❌ 监控系统启动失败"
        exit 1
    fi
    
    # 阶段3: 执行核心QPS测试
    echo "📋 阶段3: 执行核心QPS测试"
    if ! execute_core_qps_test "${original_args[@]}"; then
        echo "❌ QPS测试执行失败"
        exit 1
    fi
    
    # 阶段4: 停止监控系统
    echo "📋 阶段4: 停止监控系统"
    stop_monitoring_system
    
    # 阶段5: 处理测试结果
    echo "📋 阶段5: 处理测试结果"
    process_test_results "${original_args[@]}"
    
    # 阶段6: 执行数据分析
    echo "📋 阶段6: 执行数据分析"
    execute_data_analysis
    
    # 阶段7: 生成最终报告
    echo "📋 阶段7: 生成最终报告"
    generate_final_reports
    
    echo ""
    echo "🎉 区块链节点性能基准测试完成！"
    
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        echo "🚨 检测到性能瓶颈: $BOTTLENECK_INFO"
        echo "📊 已生成瓶颈专项分析报告"
    fi
    
    return 0
}

# 执行主函数
main "$@"
