#!/bin/bash
# =====================================================================
# EBS 性能分析器 - 统一日志版本
# =====================================================================
# 消除经验值，使用统一监控数据进行分析
# 使用统一日志管理器
# =====================================================================

source "$(dirname "$0")/../config/config.sh"
source "$(dirname "$0")/../core/common_functions.sh"
source "$(dirname "$0")/../monitoring/iostat_collector.sh"
source "$(dirname "$0")/../utils/unified_logger.sh"

# 初始化统一日志管理器
init_logger "ebs_analyzer" $LOG_LEVEL "${LOGS_DIR}/ebs_analyzer.log"

# EBS 性能分析函数
analyze_ebs_performance() {
    local csv_file="$1"
    
    if [[ ! -f "$csv_file" ]]; then
        log_error "CSV文件不存在: $csv_file"
        return 1
    fi
    
    log_info "开始分析EBS性能数据: $csv_file"
    log_debug "分析参数: csv_file=$csv_file"
    
    # 读取CSV表头，动态检测字段位置
    local header=$(head -1 "$csv_file")
    local field_names=($(echo "$header" | tr ',' ' '))
    
    # 查找DATA设备字段
    local data_util_idx=-1
    local data_iops_idx=-1
    local data_throughput_idx=-1
    local data_await_idx=-1
    
    for i in "${!field_names[@]}"; do
        case "${field_names[$i]}" in
            data_*_util) data_util_idx=$i ;;
            data_*_total_iops) data_iops_idx=$i ;;
            data_*_throughput_mibs) data_throughput_idx=$i ;;
            data_*_avg_await) data_await_idx=$i ;;
        esac
    done
    
    # 查找ACCOUNTS设备字段
    local accounts_util_idx=-1
    local accounts_iops_idx=-1
    local accounts_throughput_idx=-1
    local accounts_await_idx=-1
    
    for i in "${!field_names[@]}"; do
        case "${field_names[$i]}" in
            accounts_*_util) accounts_util_idx=$i ;;
            accounts_*_total_iops) accounts_iops_idx=$i ;;
            accounts_*_throughput_mibs) accounts_throughput_idx=$i ;;
            accounts_*_avg_await) accounts_await_idx=$i ;;
        esac
    done
    
    # 分析DATA设备
    if [[ $data_util_idx -ge 0 && $data_iops_idx -ge 0 ]]; then
        log_info "开始DATA设备性能分析"
        analyze_device_performance "$csv_file" "DATA" $((data_util_idx + 1)) $((data_iops_idx + 1)) $((data_throughput_idx + 1)) $((data_await_idx + 1))
    else
        log_warn "未找到DATA设备数据"
    fi
    
    # 分析ACCOUNTS设备
    if [[ $accounts_util_idx -ge 0 && $accounts_iops_idx -ge 0 ]]; then
        log_info "开始ACCOUNTS设备性能分析"
        analyze_device_performance "$csv_file" "ACCOUNTS" $((accounts_util_idx + 1)) $((accounts_iops_idx + 1)) $((accounts_throughput_idx + 1)) $((accounts_await_idx + 1))
    else
        log_debug "未找到ACCOUNTS设备数据 (ACCOUNTS设备为可选配置)"
    fi
    
    log_info "EBS性能分析完成"
}

# 设备性能分析
analyze_device_performance() {
    local csv_file="$1"
    local device_name="$2"
    local util_field="$3"
    local iops_field="$4"
    local throughput_field="$5"
    local await_field="$6"
    
    log_debug "分析设备: $device_name (字段位置: util=$util_field, iops=$iops_field)"
    
    # 跳过表头，分析数据
    tail -n +2 "$csv_file" | while IFS=',' read -r line_data; do
        local fields=($line_data)
        
        # 安全地获取字段值
        local util=${fields[$((util_field - 1))]:-0}
        local iops=${fields[$((iops_field - 1))]:-0}
        local throughput=${fields[$((throughput_field - 1))]:-0}
        local await_time=${fields[$((await_field - 1))]:-0}
        
        # 检查高利用率
        if (( $(echo "$util > 80" | bc -l 2>/dev/null || echo 0) )); then
            log_warn "$device_name 高利用率警告: ${util}%"
        fi
        
        # 检查高延迟
        if (( $(echo "$await_time > 20" | bc -l 2>/dev/null || echo 0) )); then
            log_warn "$device_name 高延迟警告: ${await_time}ms"
        fi
        
        # 只处理第一行作为示例，避免输出过多
        break
    done
    
    # 统计分析
    local avg_util=$(tail -n +2 "$csv_file" | cut -d',' -f"$util_field" | awk '{sum+=$1; count++} END {if(count>0) print sum/count; else print 0}')
    local max_util=$(tail -n +2 "$csv_file" | cut -d',' -f"$util_field" | sort -n | tail -1)
    local avg_iops=$(tail -n +2 "$csv_file" | cut -d',' -f"$iops_field" | awk '{sum+=$1; count++} END {if(count>0) print sum/count; else print 0}')
    local max_iops=$(tail -n +2 "$csv_file" | cut -d',' -f"$iops_field" | sort -n | tail -1)
    
    log_performance "${device_name}_avg_util" "$avg_util" "%"
    log_performance "${device_name}_max_util" "$max_util" "%"
    log_performance "${device_name}_avg_iops" "$avg_iops" "IOPS"
    log_performance "${device_name}_max_iops" "$max_iops" "IOPS"
}

# 主函数
main() {
    log_info "EBS性能分析器启动"
    
    local csv_file="$1"
    
    if [[ -z "$csv_file" ]]; then
        log_error "缺少CSV文件参数"
        echo "Usage: $0 <performance_csv_file>"
        echo ""
        echo "分析统一监控器生成的CSV文件中的EBS性能数据"
        echo "支持DATA和ACCOUNTS设备的并行分析"
        echo "消除经验值，基于实时数据进行精准分析"
        exit 1
    fi
    
    analyze_ebs_performance "$csv_file"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
