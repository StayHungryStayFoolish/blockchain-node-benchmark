#!/bin/bash

# =====================================================================
# QPS测试归档工具 - 按执行次数归档测试数据
# =====================================================================

# 安全加载配置文件，避免readonly变量冲突
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "警告: 配置文件加载失败，使用默认配置"
    DATA_DIR=${DATA_DIR:-"/tmp/blockchain-node-benchmark"}
fi

# 全局变量
ARCHIVES_DIR="${DATA_DIR}/archives"
CURRENT_TEST_DIR="${DATA_DIR}/current"
TEST_HISTORY_FILE="${DATA_DIR}/test_history.json"

# 获取下一个运行编号
get_next_run_number() {
    if [[ -f "$TEST_HISTORY_FILE" ]]; then
        local total_tests=$(jq -r '.total_tests // 0' "$TEST_HISTORY_FILE")
        echo $(printf "%03d" $((total_tests + 1)))
    else
        echo "001"
    fi
}

# 自动检测瓶颈信息 (开发环境优化版)
auto_detect_bottlenecks() {
    local bottleneck_file="${MEMORY_SHARE_DIR}/bottleneck_status.json"
    
    if [[ -f "$bottleneck_file" ]]; then
        # 验证JSON格式
        if ! jq empty "$bottleneck_file" 2>/dev/null; then
            echo "none|none|false"
            return
        fi
        
        local detected=$(jq -r '.bottleneck_detected' "$bottleneck_file" 2>/dev/null || echo "false")
        if [[ "$detected" == "true" ]]; then
            # 直接使用新格式 (无需向后兼容)
            local types_array=$(jq -r '.bottleneck_types[]?' "$bottleneck_file" 2>/dev/null)
            local values_array=$(jq -r '.bottleneck_values[]?' "$bottleneck_file" 2>/dev/null)
            
            if [[ -n "$types_array" ]]; then
                local types_csv=$(echo "$types_array" | tr '\n' ',' | sed 's/,$//')
                local values_csv=$(echo "$values_array" | tr '\n' ',' | sed 's/,$//')
                echo "$types_csv|$values_csv|true"
            else
                echo "none|none|false"
            fi
        else
            echo "none|none|false"
        fi
    else
        echo "none|none|false"
    fi
}

# 生成测试摘要
generate_test_summary() {
    local run_id="$1"
    local benchmark_mode="$2"
    local max_qps="$3"
    local start_time="$4"
    local end_time="$5"
    
    # 自动检测瓶颈信息
    local bottleneck_info=$(auto_detect_bottlenecks)
    local bottleneck_types=$(echo "$bottleneck_info" | cut -d'|' -f1)
    local bottleneck_values=$(echo "$bottleneck_info" | cut -d'|' -f2)
    local bottleneck_detected=$(echo "$bottleneck_info" | cut -d'|' -f3)
    
    local archive_path="${ARCHIVES_DIR}/${run_id}"
    local summary_file="${archive_path}/test_summary.json"
    
    # 计算测试时长
    local duration_minutes=0
    if [[ -n "$start_time" && -n "$end_time" ]]; then
        local start_epoch=$(date -d "$start_time" +%s 2>/dev/null || echo 0)
        local end_epoch=$(date -d "$end_time" +%s 2>/dev/null || echo 0)
        if [[ $start_epoch -gt 0 && $end_epoch -gt 0 ]]; then
            duration_minutes=$(( (end_epoch - start_epoch) / 60 ))
        fi
    fi
    
    # 计算数据大小
    local logs_mb=$(du -sm "${archive_path}/logs" 2>/dev/null | cut -f1 || echo 0)
    local reports_mb=$(du -sm "${archive_path}/reports" 2>/dev/null | cut -f1 || echo 0)
    local vegeta_mb=$(du -sm "${archive_path}/vegeta_results" 2>/dev/null | cut -f1 || echo 0)
    local total_mb=$((logs_mb + reports_mb + vegeta_mb))
    
    # 生成优化的JSON摘要 (开发环境版)
    local bottleneck_types_json=""
    local bottleneck_values_json=""
    
    if [[ "$bottleneck_detected" == "true" && "$bottleneck_types" != "none" ]]; then
        # 转换为JSON数组格式
        bottleneck_types_json=$(echo "[$bottleneck_types]" | sed 's/,/","/g' | sed 's/\[/["/' | sed 's/\]/"]/')
        bottleneck_values_json=$(echo "[$bottleneck_values]" | sed 's/,/","/g' | sed 's/\[/["/' | sed 's/\]/"]/')
    else
        bottleneck_types_json="[]"
        bottleneck_values_json="[]"
    fi
    
    cat > "$summary_file" << EOF
{
  "run_id": "$run_id",
  "benchmark_mode": "$benchmark_mode",
  "start_time": "$start_time",
  "end_time": "$end_time",
  "duration_minutes": $duration_minutes,
  "max_successful_qps": $max_qps,
  "bottleneck_detected": $bottleneck_detected,
  "bottleneck_types": $bottleneck_types_json,
  "bottleneck_values": $bottleneck_values_json,
  "bottleneck_summary": "$bottleneck_types",
  "test_parameters": {
    "initial_qps": ${FULL_INITIAL_QPS:-1000},
    "max_qps": ${FULL_MAX_QPS:-5000},
    "qps_step": ${FULL_QPS_STEP:-500},
    "duration_per_level": ${FULL_DURATION:-600}
  },
  "data_size": {
    "logs_mb": $logs_mb,
    "reports_mb": $reports_mb,
    "vegeta_results_mb": $vegeta_mb,
    "total_mb": $total_mb
  },
  "archived_at": "$(date '+%Y-%m-%d %H:%M:%S')"
}
EOF
    
    echo "✅ 测试摘要已生成: $summary_file"
}

# 更新测试历史索引
update_test_history() {
    local run_id="$1"
    local benchmark_mode="$2"
    local max_qps="$3"
    local status="$4"
    
    # 如果历史文件不存在，创建初始结构
    if [[ ! -f "$TEST_HISTORY_FILE" ]]; then
        cat > "$TEST_HISTORY_FILE" << EOF
{
  "total_tests": 0,
  "latest_run": "",
  "tests": []
}
EOF
    fi
    
    # 添加新测试记录
    local temp_file=$(mktemp)
    jq --arg run_id "$run_id" \
       --arg benchmark_mode "$benchmark_mode" \
       --argjson max_qps "$max_qps" \
       --arg status "$status" \
       '.total_tests += 1 | 
        .latest_run = $run_id | 
        .tests += [{
          "run_id": $run_id,
          "benchmark_mode": $benchmark_mode,
          "max_qps": $max_qps,
          "status": $status,
          "archived_at": now | strftime("%Y-%m-%d %H:%M:%S")
        }]' "$TEST_HISTORY_FILE" > "$temp_file" && mv "$temp_file" "$TEST_HISTORY_FILE"
    
    echo "✅ 测试历史已更新: $TEST_HISTORY_FILE"
}

# 自动归档当前测试
archive_current_test() {
    local benchmark_mode="$1"
    local max_qps="$2"
    local start_time="$3"
    local end_time="$4"
    
    echo "🗂️  开始归档当前测试数据..."
    
    # 检查当前测试目录是否存在数据
    if [[ ! -d "$CURRENT_TEST_DIR" ]] || [[ -z "$(ls -A "$CURRENT_TEST_DIR" 2>/dev/null)" ]]; then
        echo "⚠️  当前测试目录为空，无需归档"
        return 1
    fi
    
    # 生成运行ID
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local run_number=$(get_next_run_number)
    local run_id="run_${run_number}_${timestamp}"
    
    # 自动检测瓶颈信息用于显示
    local bottleneck_info=$(auto_detect_bottlenecks)
    local bottleneck_types=$(echo "$bottleneck_info" | cut -d'|' -f1)
    local bottleneck_detected=$(echo "$bottleneck_info" | cut -d'|' -f3)
    
    echo "📋 归档信息:"
    echo "   运行ID: $run_id"
    echo "   基准测试模式: $benchmark_mode"
    echo "   最大QPS: $max_qps"
    echo "   瓶颈检测: $bottleneck_detected"
    if [[ "$bottleneck_detected" == "true" ]]; then
        echo "   瓶颈类型: $bottleneck_types"
    fi
    
    # 创建归档目录
    local archive_path="${ARCHIVES_DIR}/${run_id}"
    mkdir -p "$archive_path"
    
    # 移动当前测试数据到归档
    if mv "$CURRENT_TEST_DIR"/* "$archive_path/" 2>/dev/null; then
        echo "✅ 测试数据已移动到归档目录"
    else
        echo "❌ 移动测试数据失败"
        return 1
    fi
    
    # 生成测试摘要
    generate_test_summary "$run_id" "$benchmark_mode" "$max_qps" "$start_time" "$end_time"
    
    # 确定测试状态
    local status="completed_successfully"
    if [[ "$bottleneck_detected" == "true" ]]; then
        status="completed_with_bottleneck"
    fi
    
    # 更新测试历史索引
    update_test_history "$run_id" "$benchmark_mode" "$max_qps" "$status"
    
    echo "🎉 测试归档完成: $run_id"
    echo "📊 数据大小: $(du -sh "$archive_path" | cut -f1)"
    
    return 0
}

# 列出历史测试
list_test_history() {
    echo "📊 QPS测试历史记录"
    echo "=================="
    
    if [[ -f "$TEST_HISTORY_FILE" ]]; then
        local total_tests=$(jq -r '.total_tests' "$TEST_HISTORY_FILE")
        local latest_run=$(jq -r '.latest_run' "$TEST_HISTORY_FILE")
        
        echo "总测试次数: $total_tests"
        echo "最新测试: $latest_run"
        echo ""
        echo "历史测试列表:"
        
        jq -r '.tests[] | "🔹 \(.run_id) | 模式: \(.benchmark_mode) | 最大QPS: \(.max_qps) | 状态: \(.status) | 时间: \(.archived_at)"' "$TEST_HISTORY_FILE"
    else
        echo "暂无测试历史记录"
    fi
}

# 比较测试结果
compare_tests() {
    local run1="$1"
    local run2="$2"
    
    if [[ -z "$run1" || -z "$run2" ]]; then
        echo "❌ 错误: 请提供两个测试ID进行比较"
        echo "💡 用法: $0 --compare <run_id_1> <run_id_2>"
        echo "🔍 使用 --list 查看可用的测试ID"
        return 1
    fi
    
    echo "📈 测试对比: $run1 vs $run2"
    echo "=========================="
    
    local summary1="${ARCHIVES_DIR}/${run1}/test_summary.json"
    local summary2="${ARCHIVES_DIR}/${run2}/test_summary.json"
    
    if [[ ! -f "$summary1" ]]; then
        echo "❌ 错误: 测试 '$run1' 的摘要文件不存在"
        echo "💡 文件路径: $summary1"
        echo "🔍 使用 --list 查看可用的测试ID"
        return 1
    fi
    
    if [[ ! -f "$summary2" ]]; then
        echo "❌ 错误: 测试 '$run2' 的摘要文件不存在"
        echo "💡 文件路径: $summary2"
        echo "🔍 使用 --list 查看可用的测试ID"
        return 1
    fi
    
    # 验证JSON文件格式
    if ! jq empty "$summary1" 2>/dev/null; then
        echo "❌ 错误: 测试 '$run1' 的摘要文件格式无效"
        echo "💡 文件可能已损坏，请检查: $summary1"
        return 1
    fi
    
    if ! jq empty "$summary2" 2>/dev/null; then
        echo "❌ 错误: 测试 '$run2' 的摘要文件格式无效"
        echo "💡 文件可能已损坏，请检查: $summary2"
        return 1
    fi
    
    echo "📊 性能对比:"
    printf "%-30s %-15s %-15s\n" "指标" "$run1" "$run2"
    echo "------------------------------------------------------------"
    printf "%-30s %-15s %-15s\n" "最大QPS" \
        "$(jq -r '.max_successful_qps' "$summary1")" \
        "$(jq -r '.max_successful_qps' "$summary2")"
    printf "%-30s %-15s %-15s\n" "测试时长(分钟)" \
        "$(jq -r '.duration_minutes' "$summary1")" \
        "$(jq -r '.duration_minutes' "$summary2")"
    printf "%-30s %-15s %-15s\n" "瓶颈类型" \
        "$(jq -r '.bottleneck_summary // "none"' "$summary1")" \
        "$(jq -r '.bottleneck_summary // "none"' "$summary2")"
    printf "%-30s %-15s %-15s\n" "数据大小(MB)" \
        "$(jq -r '.data_size.total_mb' "$summary1")" \
        "$(jq -r '.data_size.total_mb' "$summary2")"
    
    echo ""
    echo "📅 时间对比:"
    echo "  $run1: $(jq -r '.start_time' "$summary1") - $(jq -r '.end_time' "$summary1")"
    echo "  $run2: $(jq -r '.start_time' "$summary2") - $(jq -r '.end_time' "$summary2")"
}

# 清理旧测试数据
cleanup_old_tests() {
    local keep_count=${1:-10}
    
    # 验证保留数量参数
    if ! [[ "$keep_count" =~ ^[0-9]+$ ]] || [[ "$keep_count" -eq 0 ]]; then
        echo "❌ 错误: 保留数量必须是正整数，当前值: '$keep_count'"
        echo "💡 示例: cleanup_old_tests 5"
        return 1
    fi
    
    echo "🗑️  清理旧测试数据，保留最近 $keep_count 次测试"
    
    if [[ ! -d "$ARCHIVES_DIR" ]]; then
        echo "ℹ️  归档目录不存在，无需清理"
        echo "💡 目录路径: $ARCHIVES_DIR"
        return 0
    fi
    
    # 检查目录权限
    if [[ ! -w "$ARCHIVES_DIR" ]]; then
        echo "❌ 错误: 没有归档目录的写权限"
        echo "💡 目录路径: $ARCHIVES_DIR"
        echo "🔧 请检查目录权限或以适当用户身份运行"
        return 1
    fi
    
    # 获取所有测试目录，按时间排序
    local test_dirs=($(ls -1t "$ARCHIVES_DIR" | grep "^run_"))
    local total_tests=${#test_dirs[@]}
    
    if [[ $total_tests -le $keep_count ]]; then
        echo "当前测试数量($total_tests)不超过保留数量($keep_count)，无需清理"
        return 0
    fi
    
    echo "发现 $total_tests 个测试，将删除最旧的 $((total_tests - keep_count)) 个"
    
    # 删除超出保留数量的旧测试
    for ((i=$keep_count; i<$total_tests; i++)); do
        local old_test="${test_dirs[$i]}"
        local old_path="${ARCHIVES_DIR}/${old_test}"
        local size=$(du -sh "$old_path" | cut -f1)
        
        echo "删除: $old_test (大小: $size)"
        rm -rf "$old_path"
    done
    
    # 重建测试历史索引
    rebuild_test_history
    
    echo "✅ 清理完成"
}

# 重建测试历史索引
rebuild_test_history() {
    echo "🔄 重建测试历史索引..."
    
    # 创建新的历史文件
    cat > "$TEST_HISTORY_FILE" << EOF
{
  "total_tests": 0,
  "latest_run": "",
  "tests": []
}
EOF
    
    # 扫描归档目录中的所有测试
    if [[ -d "$ARCHIVES_DIR" ]]; then
        local test_dirs=($(ls -1t "$ARCHIVES_DIR" | grep "^run_"))
        
        for test_dir in "${test_dirs[@]}"; do
            local summary_file="${ARCHIVES_DIR}/${test_dir}/test_summary.json"
            
            if [[ -f "$summary_file" ]]; then
                local benchmark_mode=$(jq -r '.benchmark_mode' "$summary_file")
                local max_qps=$(jq -r '.max_successful_qps' "$summary_file")
                local bottleneck=$(jq -r '.bottleneck_detected' "$summary_file")
                local status="completed_successfully"
                
                if [[ "$bottleneck" == "true" ]]; then
                    status="completed_with_bottleneck"
                fi
                
                update_test_history "$test_dir" "$benchmark_mode" "$max_qps" "$status"
            fi
        done
    fi
    
    echo "✅ 测试历史索引重建完成"
}

# 显示帮助信息
show_help() {
    cat << 'EOF'
📦 基准测试归档工具 - 开发环境优化版

用法:
  $0 <操作> [选项]

操作:
  --archive                    归档当前测试数据
    --benchmark-mode <mode>    基准测试模式 (必需)
                              支持: quick, standard, intensive
    --max-qps <qps>           最大成功QPS (必需，正整数)
    --start-time <time>       测试开始时间 (可选)
                              格式: 'YYYY-MM-DD HH:MM:SS'
    --end-time <time>         测试结束时间 (可选)
                              格式: 'YYYY-MM-DD HH:MM:SS'
    注: 瓶颈信息将自动从系统检测结果中提取

  --list                       列出测试历史记录
  
  --compare <run1> <run2>      比较两次测试结果
                              run1, run2: 测试运行ID
                              使用 --list 查看可用的测试ID
  
  --cleanup [--keep <count>]   清理旧测试数据
                              count: 保留的测试数量 (默认: 10)
                              必须是正整数
  
  --rebuild-history           重建测试历史索引
  
  --help                      显示此帮助信息

示例:
  # 归档测试 (基本用法)
  $0 --archive --benchmark-mode standard --max-qps 2500
  
  # 归档测试 (完整信息)
  $0 --archive --benchmark-mode intensive --max-qps 3500 \
     --start-time "2025-01-01 10:00:00" --end-time "2025-01-01 12:00:00"
  
  # 列出历史测试
  $0 --list
  
  # 比较两次测试
  $0 --compare run_001_20250101_100000 run_002_20250101_110000
  
  # 清理旧测试，保留最近5次
  $0 --cleanup --keep 5

注意事项:
  • 所有时间格式使用: 'YYYY-MM-DD HH:MM:SS'
  • QPS值必须是正整数
  • 瓶颈信息自动检测，无需手动指定
  • 在开发环境中，错误处理更加严格和友好

错误处理:
  • 参数验证: 严格验证所有参数的格式和有效性
  • 友好提示: 提供具体的错误信息和使用建议
  • 快速帮助: 错误时显示相关的使用提示
EOF
}

# 主函数
main() {
    case "$1" in
        --archive)
            shift
            local mode="full"
            local max_qps="0"
            local start_time=""
            local end_time=""
            
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --benchmark-mode) 
                        if [[ -z "$2" ]]; then
                            echo "❌ 错误: --benchmark-mode 参数值不能为空"
                            echo "💡 支持的模式: quick, standard, intensive"
                            exit 1
                        fi
                        if [[ "$2" != "quick" && "$2" != "standard" && "$2" != "intensive" ]]; then
                            echo "❌ 错误: 无效的基准测试模式 '$2'"
                            echo "💡 支持的模式: quick, standard, intensive"
                            exit 1
                        fi
                        mode="$2"; shift 2 ;;
                    --max-qps) 
                        if [[ -z "$2" ]]; then
                            echo "❌ 错误: --max-qps 参数值不能为空"
                            echo "💡 示例: --max-qps 2500"
                            exit 1
                        fi
                        if ! [[ "$2" =~ ^[0-9]+$ ]] || [[ "$2" -eq 0 ]]; then
                            echo "❌ 错误: --max-qps 必须是正整数，当前值: '$2'"
                            echo "💡 示例: --max-qps 2500"
                            exit 1
                        fi
                        max_qps="$2"; shift 2 ;;
                    --start-time) 
                        if [[ -z "$2" ]]; then
                            echo "❌ 错误: --start-time 参数值不能为空"
                            echo "💡 格式: 'YYYY-MM-DD HH:MM:SS'"
                            exit 1
                        fi
                        start_time="$2"; shift 2 ;;
                    --end-time) 
                        if [[ -z "$2" ]]; then
                            echo "❌ 错误: --end-time 参数值不能为空"
                            echo "💡 格式: 'YYYY-MM-DD HH:MM:SS'"
                            exit 1
                        fi
                        end_time="$2"; shift 2 ;;
                    --help)
                        show_help
                        exit 0 ;;
                    -*) 
                        echo "❌ 错误: 未知参数 '$1'"
                        echo ""
                        echo "💡 支持的参数:"
                        echo "   --benchmark-mode <mode>  基准测试模式 (quick/standard/intensive)"
                        echo "   --max-qps <qps>         最大成功QPS (正整数)"
                        echo "   --start-time <time>     测试开始时间"
                        echo "   --end-time <time>       测试结束时间"
                        echo "   --help                  显示完整帮助信息"
                        echo ""
                        echo "🔍 使用 --help 查看完整使用说明"
                        exit 1 ;;
                    *) 
                        echo "❌ 错误: 无效参数 '$1'"
                        echo "💡 提示: 参数必须以 -- 开头"
                        echo "🔍 使用 --help 查看支持的参数"
                        exit 1 ;;
                esac
            done
            
            # 验证必需参数
            if [[ -z "$mode" ]]; then
                echo "❌ 错误: 缺少必需参数 --benchmark-mode"
                echo "💡 示例: --benchmark-mode standard"
                exit 1
            fi
            
            if [[ -z "$max_qps" ]]; then
                echo "❌ 错误: 缺少必需参数 --max-qps"
                echo "💡 示例: --max-qps 2500"
                exit 1
            fi
            
            archive_current_test "$mode" "$max_qps" "$start_time" "$end_time"
            ;;
        --list)
            list_test_history
            ;;
        --compare)
            if [[ $# -lt 3 ]]; then
                echo "❌ 错误: --compare 需要两个测试ID参数"
                echo "💡 用法: --compare <run_id1> <run_id2>"
                echo "🔍 使用 --list 查看可用的测试ID"
                exit 1
            fi
            local run1="$2"
            local run2="$3"
            if [[ -z "$run1" || -z "$run2" ]]; then
                echo "❌ 错误: 测试ID不能为空"
                echo "💡 用法: --compare run_001_20250101_120000 run_002_20250101_130000"
                exit 1
            fi
            compare_tests "$run1" "$run2"
            ;;
        --cleanup)
            local keep_count=10  # 默认保留10次
            if [[ -n "$2" && "$2" == "--keep" ]]; then
                if [[ -z "$3" ]]; then
                    echo "❌ 错误: --keep 参数需要指定保留数量"
                    echo "💡 用法: --cleanup --keep 5"
                    exit 1
                fi
                if ! [[ "$3" =~ ^[0-9]+$ ]] || [[ "$3" -eq 0 ]]; then
                    echo "❌ 错误: 保留数量必须是正整数，当前值: '$3'"
                    echo "💡 用法: --cleanup --keep 5"
                    exit 1
                fi
                keep_count="$3"
            elif [[ -n "$2" ]]; then
                echo "❌ 错误: --cleanup 的无效参数 '$2'"
                echo "💡 用法: --cleanup [--keep <count>]"
                exit 1
            fi
            cleanup_old_tests "$keep_count"
            ;;
        --rebuild-history)
            rebuild_test_history
            ;;
        --help)
            show_help
            ;;
        "")
            echo "❌ 错误: 缺少操作参数"
            echo ""
            echo "💡 可用操作:"
            echo "   --archive                    归档当前测试"
            echo "   --list                       列出测试历史"
            echo "   --compare <run1> <run2>      比较两次测试"
            echo "   --cleanup [--keep <count>]   清理旧测试"
            echo "   --rebuild-history            重建测试历史"
            echo "   --help                       显示帮助"
            echo ""
            echo "🔍 使用 --help 查看详细说明"
            exit 1
            ;;
        *)
            echo "❌ 错误: 未知操作 '$1'"
            echo ""
            echo "💡 可用操作:"
            echo "   --archive                    归档当前测试"
            echo "   --list                       列出测试历史"
            echo "   --compare <run1> <run2>      比较两次测试"
            echo "   --cleanup [--keep <count>]   清理旧测试"
            echo "   --rebuild-history            重建测试历史"
            echo "   --help                       显示帮助"
            echo ""
            echo "🔍 使用 --help 查看详细说明"
            exit 1
            ;;
    esac
}

# 如果直接执行此脚本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
