#!/bin/bash

# =====================================================================
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
    echo "   • 快速验证测试 - 基础性能验证"
    echo "   • 标准性能测试 - 全面性能评估"
    echo "   • 极限压力测试 - 智能瓶颈检测"
    echo ""
    echo "🔍 监控能力:"
    echo "   • 73 - 79 个性能指标实时监控"
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
source "${SCRIPT_DIR}/config/config_loader.sh"
source "${SCRIPT_DIR}/utils/error_handler.sh"
source "${SCRIPT_DIR}/core/common_functions.sh"

# 清理或创建内存共享目录
if [[ -d "$MEMORY_SHARE_DIR" ]]; then
    echo "🧹 清理内存共享目录中的旧缓存数据..." >&2
    # 清理所有可能的残留文件
    rm -f "$MEMORY_SHARE_DIR"/*.json 2>/dev/null || true
    rm -f "$MEMORY_SHARE_DIR"/sample_count 2>/dev/null || true
    rm -f "$MEMORY_SHARE_DIR"/*cache* 2>/dev/null || true
    rm -f "$MEMORY_SHARE_DIR"/*.pid 2>/dev/null || true
    rm -f "$MEMORY_SHARE_DIR"/*.lock 2>/dev/null || true
else
    echo "📁 创建内存共享目录..." >&2
    mkdir -p "$MEMORY_SHARE_DIR" 2>/dev/null || true
    chmod 755 "$MEMORY_SHARE_DIR" 2>/dev/null || true
fi

echo "✅ 内存共享目录准备完成" >&2

# 设置错误处理
setup_error_handling "$(basename "$0")" "区块链节点基准测试框架"
log_script_start "$(basename "$0")"

# 全局变量
MONITORING_PIDS=()
TEST_SESSION_ID="session_${SESSION_TIMESTAMP}"
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

# 准备 Benchmark 数据
prepare_benchmark_data() {
    echo "📊 准备 Benchmark 数据..."
    
    # 检查账户文件是否存在
    if [[ ! -f "$ACCOUNTS_OUTPUT_FILE" ]]; then
        echo "🔍 获取活跃账户..."
        if [[ -f "${SCRIPT_DIR}/tools/fetch_active_accounts.py" ]]; then
            python3 "${SCRIPT_DIR}/tools/fetch_active_accounts.py" \
                --output "$ACCOUNTS_OUTPUT_FILE" \
                --count "$ACCOUNT_COUNT" \
                --verbose

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
    
    # 在启动监控前创建框架运行状态文件
    echo "running" > "$TMP_DIR/qps_test_status.tmp"
    mv "$TMP_DIR/qps_test_status.tmp" "$TMP_DIR/qps_test_status"
    echo "[STATUS] Framework lifecycle marker created: $TMP_DIR/qps_test_status"
    
    # 导出监控PID文件路径供子进程使用
    export MONITOR_PIDS_FILE="${TMP_DIR}/monitor_pids.txt"
    export MONITOR_STATUS_FILE="${TMP_DIR}/monitoring_status.json"
    
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
    
    # 🔧 验证框架状态文件存在（已在监控启动时创建）
    if [[ ! -f "$TMP_DIR/qps_test_status" ]]; then
        echo "[ERROR] Framework status file not found. Monitoring system may not be running."
        return 1
    fi
    echo "[STATUS] Framework lifecycle marker verified: $TMP_DIR/qps_test_status"
    
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
    
    # 等待监控系统收集最后的数据，确保数据完整性
    echo "[STATUS] QPS test completed, waiting for monitoring data collection..."
    sleep 3
    
    # Delete QPS test status marker file - safe deletion
    if [[ -f "$TMP_DIR/qps_test_status" ]]; then
        rm -f "$TMP_DIR/qps_test_status"
        echo "[STATUS] QPS test status marker deleted"
    else
        echo "[WARN] QPS test status marker file does not exist, may have been deleted"
    fi
    
    # 检查是否检测到瓶颈 - 智能合并多个瓶颈数据源
    local bottleneck_sources=(
        "${QPS_STATUS_FILE}"                              # 优先QPS测试期间的瓶颈
        "${MEMORY_SHARE_DIR}/bottleneck_status.json"      # 然后是监控期间的瓶颈
    )
    
    local bottleneck_found=false
    local all_bottleneck_info=""
    
    for bottleneck_file in "${bottleneck_sources[@]}"; do
        if [[ -f "$bottleneck_file" ]]; then
            local status_data=$(cat "$bottleneck_file" 2>/dev/null)
            if [[ -n "$status_data" ]] && echo "$status_data" | grep -q "bottleneck_detected.*true"; then
                local source_info=$(echo "$status_data" | jq -r '.bottleneck_summary // "Unknown bottleneck"' 2>/dev/null || echo "Unknown bottleneck")
                local source_name=$(basename "$bottleneck_file")
                
                if [[ "$bottleneck_found" == "false" ]]; then
                    BOTTLENECK_DETECTED=true
                    BOTTLENECK_INFO="$source_info"
                    all_bottleneck_info="$source_name: $source_info"
                    bottleneck_found=true
                else
                    all_bottleneck_info="$all_bottleneck_info; $source_name: $source_info"
                fi
                
                echo "🚨 检测到性能瓶颈: $source_info (来源: $source_name)"
            fi
        fi
    done
    
    # 如果发现多个瓶颈源，记录完整信息
    if [[ "$bottleneck_found" == "true" ]]; then
        echo "[INFO] 完整瓶颈信息: $all_bottleneck_info"
    fi
    
    return $test_result
}

# 处理测试结果
process_test_results() {
    echo "🔄 处理测试结果..."
    
    # AWS基准转换
    echo "📊 执行AWS基准转换..."
    if [[ -f "${SCRIPT_DIR}/utils/ebs_converter.sh" ]]; then
        # 注意: ebs_converter.sh是函数库，不支持直接执行参数
        # 实际的EBS转换在iostat_collector.sh中通过source调用实现
        echo "✅ EBS转换库已加载，转换在数据收集时自动执行"
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
    
    return 0
}

# 执行数据分析
execute_data_analysis() {
    echo "🔍 执行数据分析..."
    
    # 解析benchmark_mode参数
    local benchmark_mode=""
    for arg in "$@"; do
        case $arg in
            --quick) benchmark_mode="quick" ;;
            --standard) benchmark_mode="standard" ;;
            --intensive) benchmark_mode="intensive" ;;
        esac
    done
    
    if [[ -z "$benchmark_mode" ]]; then
        benchmark_mode="quick"
    fi
    
    # 使用软链接获取最新的性能数据文件
    local latest_csv="${LOGS_DIR}/performance_latest.csv"
    
    if [[ ! -f "$latest_csv" ]]; then
        echo "[ERROR] Performance data file not found: $latest_csv"
        echo "[DEBUG] Available CSV files:"
        ls -la "$LOGS_DIR"/*.csv 2>/dev/null || echo "  No CSV files found"
        echo "[DEBUG] LOGS_DIR = $LOGS_DIR"
        return 1
    fi
    
    # 验证文件完整性和软链接目标
    if [[ -L "$latest_csv" ]]; then
        local target_file=$(readlink "$latest_csv")
        local full_target="${LOGS_DIR}/$target_file"
        if [[ ! -f "$full_target" ]]; then
            echo "[ERROR] Symlink target does not exist: $full_target"
            return 1
        fi
        echo "[INFO] Using symlinked file: $target_file"
    fi
    
    local line_count=$(wc -l < "$latest_csv")
    if [[ $line_count -lt 2 ]]; then
        echo "[ERROR] Performance data file is empty or only contains header: $line_count lines"
        return 1
    fi
    
    # 验证CSV表头完整性和必需字段
    local header=$(head -1 "$latest_csv")
    local field_count=$(echo "$header" | tr ',' '\n' | wc -l)
    if [[ $field_count -lt 10 ]]; then
        echo "[ERROR] CSV header appears incomplete: only $field_count fields"
        return 1
    fi
    
    # 验证关键字段存在
    local required_fields=("timestamp" "cpu_usage" "mem_usage")
    local missing_fields=()
    
    for field in "${required_fields[@]}"; do
        if ! echo "$header" | grep -q "$field"; then
            missing_fields+=("$field")
        fi
    done
    
    if [[ ${#missing_fields[@]} -gt 0 ]]; then
        echo "[ERROR] Required fields missing from CSV: ${missing_fields[*]}"
        echo "[DEBUG] Available fields: $header"
        return 1
    fi
    
    # 检查设备相关字段的存在性（用于分析脚本兼容性）
    local has_data_device=false
    local has_accounts_device=false
    local has_ena_fields=false
    
    if echo "$header" | grep -q "data_.*_util"; then
        has_data_device=true
        echo "[INFO] DATA device fields detected"
    fi
    
    if echo "$header" | grep -q "accounts_.*_util"; then
        has_accounts_device=true
        echo "[INFO] ACCOUNTS device fields detected"
    fi
    
    if echo "$header" | grep -q "ena_"; then
        has_ena_fields=true
        echo "[INFO] ENA fields detected (AWS environment)"
    fi
    
    # 警告：如果没有设备字段，某些分析可能受限
    if [[ "$has_data_device" == "false" && "$has_accounts_device" == "false" ]]; then
        echo "[WARN] No EBS device fields detected - storage analysis may be limited"
    fi
    
    echo "[INFO] Using monitoring data file: $(basename "$latest_csv")"
    echo "[INFO] File size: $line_count lines, $field_count fields"
    echo "[INFO] Required fields verified: ${required_fields[*]}"
    
    # 如果检测到瓶颈，执行瓶颈专项分析
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        echo "🚨 执行瓶颈专项分析..."
        
        # 读取瓶颈详细信息
        local bottleneck_details=""
        if [[ -f "$QPS_STATUS_FILE" ]]; then
            bottleneck_details=$(cat "$QPS_STATUS_FILE")
            local bottleneck_qps=$(echo "$bottleneck_details" | jq -r '.bottleneck_qps // 0')
            local max_qps=$(echo "$bottleneck_details" | jq -r '.max_successful_qps // 0')
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
        
        # EBS瓶颈专项分析已通过实时监控完成
        # ebs_bottleneck_detector.sh在测试期间通过monitoring_coordinator.sh实时运行
        # 瓶颈检测结果已记录在ebs_analyzer.log中，无需重复调用
        echo "💾 EBS瓶颈检测已通过实时监控完成"
        
        # 瓶颈时间窗口分析
        execute_bottleneck_window_analysis "$latest_csv" "$bottleneck_details"
        
        # 性能悬崖分析
        execute_performance_cliff_analysis "$latest_csv" "$bottleneck_details"
    fi
    
    # 执行EBS性能分析 (生成ebs_analyzer.log)
    if [[ -f "${SCRIPT_DIR}/tools/ebs_analyzer.sh" ]]; then
        echo "🔍 执行EBS性能分析: ebs_analyzer.sh"
        if ! bash "${SCRIPT_DIR}/tools/ebs_analyzer.sh" "$latest_csv"; then
            echo "⚠️ EBS分析执行失败，HTML报告中可能缺少EBS分析部分"
        fi
    else
        echo "⚠️ EBS分析脚本不存在: tools/ebs_analyzer.sh"
    fi
    
    # 执行所有标准分析脚本
    local analysis_scripts=(
        "analysis/comprehensive_analysis.py"
        "analysis/cpu_ebs_correlation_analyzer.py"
        "analysis/qps_analyzer.py"
        "analysis/rpc_deep_analyzer.py"
    )
    
    for script in "${analysis_scripts[@]}"; do
        if [[ -f "${SCRIPT_DIR}/$script" ]]; then
            echo "🔍 执行分析: $(basename "$script")"
            
            # 如果检测到瓶颈，传递瓶颈模式参数
            if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
                if ! python3 "${SCRIPT_DIR}/$script" "$latest_csv" --benchmark-mode "$benchmark_mode" --bottleneck-mode --output-dir "$BASE_DATA_DIR"; then
                    echo "⚠️ 分析脚本执行失败: $(basename "$script")"
                fi
            else
                # 即使没有瓶颈也执行基础分析，确保图表生成
                if ! python3 "${SCRIPT_DIR}/$script" "$latest_csv" --benchmark-mode "$benchmark_mode" --output-dir "$BASE_DATA_DIR"; then
                    echo "⚠️ 分析脚本执行失败: $(basename "$script")"
                fi
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
                --benchmark-mode "$benchmark_mode" \
                --output-dir "$BASE_DATA_DIR" \
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
    
    # 调用性能悬崖分析工具 - 即使没有瓶颈信息也执行基础分析
    if [[ -f "${SCRIPT_DIR}/analysis/qps_analyzer.py" ]]; then
        if [[ -n "$bottleneck_info" ]]; then
            # 有瓶颈信息时的完整分析
            local max_qps=$(echo "$bottleneck_info" | jq -r '.max_successful_qps // 0')
            local bottleneck_qps=$(echo "$bottleneck_info" | jq -r '.bottleneck_qps // 0')
            
            if [[ $max_qps -gt 0 && $bottleneck_qps -gt 0 ]]; then
                local performance_drop=$(awk "BEGIN {printf \"%.2f\", ($bottleneck_qps - $max_qps) * 100 / $max_qps}")
                echo "📊 性能悬崖: 从 ${max_qps} QPS 到 ${bottleneck_qps} QPS (${performance_drop}%)"
                
                python3 "${SCRIPT_DIR}/analysis/qps_analyzer.py" \
                    "$csv_file" \
                    --benchmark-mode "$benchmark_mode" \
                    --cliff-analysis \
                    --max-qps "$max_qps" \
                    --bottleneck-qps "$bottleneck_qps" \
                    --output-dir "$BASE_DATA_DIR"
            else
                echo "📊 执行基础性能分析（瓶颈数据不完整）"
                python3 "${SCRIPT_DIR}/analysis/qps_analyzer.py" \
                    "$csv_file" \
                    --benchmark-mode "$benchmark_mode" \
                    --output-dir "$BASE_DATA_DIR"
            fi
        else
            echo "📊 执行基础性能分析（无瓶颈信息）"
            python3 "${SCRIPT_DIR}/analysis/qps_analyzer.py" \
                "$csv_file" \
                --benchmark-mode "$benchmark_mode" \
                --output-dir "$BASE_DATA_DIR"
        fi
    fi
}

# 归档测试结果
archive_test_results() {
    echo "📦 归档测试结果..."
    
    # 确定基准测试模式 - 从传入的参数中解析
    local benchmark_mode=""
    for arg in "$@"; do
        case $arg in
            --quick) benchmark_mode="quick" ;;
            --standard) benchmark_mode="standard" ;;
            --intensive) benchmark_mode="intensive" ;;
        esac
    done
    
    # 如果没有找到模式参数，使用默认值
    if [[ -z "$benchmark_mode" ]]; then
        benchmark_mode="quick"  # 默认模式，与master_qps_executor.sh保持一致
        echo "⚠️ 未检测到基准测试模式参数，使用默认模式: $benchmark_mode"
    fi
    
    echo "🔍 检测到基准测试模式: $benchmark_mode"
    
    # 从QPS状态文件读取最大QPS
    local max_qps=0
    if [[ -f "$QPS_STATUS_FILE" ]]; then
        max_qps=$(jq -r '.max_successful_qps // 0' "$QPS_STATUS_FILE" 2>/dev/null)
    fi
    
    # 调用专业的归档工具
    if [[ -f "${SCRIPT_DIR}/tools/benchmark_archiver.sh" ]]; then
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
}

# 生成最终报告
generate_final_reports() {
    echo "📊 生成最终报告..."
    
    # 使用软链接获取最新的性能数据文件
    local latest_csv="${LOGS_DIR}/performance_latest.csv"
    
    if [[ ! -f "$latest_csv" ]]; then
        echo "⚠️ 警告: 没有找到性能数据文件: $latest_csv"
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
    
    # 生成HTML报告（双语：英文和中文）
    if [[ -f "${SCRIPT_DIR}/visualization/report_generator.py" ]]; then
        echo "📄 生成HTML报告（双语）..."
        
        # 生成英文报告
        echo "  📝 生成英文报告..."
        if ! python3 "${SCRIPT_DIR}/visualization/report_generator.py" "${report_params[@]}" --language en; then
            echo "  ❌ 英文报告生成失败"
            return 1
        fi
        echo "  ✅ 英文报告已生成"
        
        # 生成中文报告
        echo "  📝 生成中文报告..."
        if ! python3 "${SCRIPT_DIR}/visualization/report_generator.py" "${report_params[@]}" --language zh; then
            echo "  ❌ 中文报告生成失败"
            return 1
        fi
        echo "  ✅ 中文报告已生成"
        
        echo "✅ 双语HTML报告已生成"
    else
        echo "⚠️ HTML报告生成器不存在"
    fi

    # 生成高级图表
    if [[ -f "${SCRIPT_DIR}/visualization/advanced_chart_generator.py" ]]; then
        echo "📊 生成高级图表..."
        if ! python3 "${SCRIPT_DIR}/visualization/advanced_chart_generator.py" "${report_params[@]}"; then
            echo "⚠️ 高级图表生成失败"
        else
            echo "✅ 高级图表已生成"
        fi
    else
        echo "⚠️ 高级图表生成器不存在"
    fi
    
    # 生成瓶颈专项报告
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        generate_bottleneck_summary_report
    fi
    
    # 显示报告位置和摘要
    display_final_report_summary
    
    # 归档测试结果 - 在所有分析和报告生成完成后执行
    archive_test_results "$@"
    
    return 0
}

# 生成瓶颈摘要报告
generate_bottleneck_summary_report() {
    echo "🚨 生成瓶颈摘要报告..."
    
    local bottleneck_summary_file="${REPORTS_DIR}/bottleneck_summary_${SESSION_TIMESTAMP}.md"
    
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
        local max_qps=$(echo "$bottleneck_info" | jq -r '.max_successful_qps // 0')
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
- **性能数据**: ${LOGS_DIR}/performance_latest.csv

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
            local max_qps=$(jq -r '.max_successful_qps // 0' "$QPS_STATUS_FILE" 2>/dev/null)
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
    
    # 阶段1: 准备 Benchmark 数据
    echo "📋 阶段1: 准备 Benchmark 数据"
    if ! prepare_benchmark_data; then
        echo "❌ Benchmark 数据准备失败"
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
    if ! execute_data_analysis "${original_args[@]}"; then
        echo "❌ 数据分析失败，测试终止"
        exit 1
    fi
    
    # 阶段7: 生成最终报告
    echo "📋 阶段7: 生成最终报告"
    if ! generate_final_reports "${original_args[@]}"; then
        echo "❌ 报告生成失败，测试终止"
        exit 1
    fi
    
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
