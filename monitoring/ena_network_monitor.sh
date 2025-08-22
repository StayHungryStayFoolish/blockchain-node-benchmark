#!/bin/bash
# =====================================================================
# ENA网络监控器 - 基于AWS ENA文档的网络限制监控
# =====================================================================
# 监控ENA网络接口的allowance exceeded指标
# 替代假设的PPS阈值，使用实际的AWS网络限制数据
# 使用统一日志管理器
# =====================================================================

# 严格错误处理 - 但允许在交互式环境中安全使用
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    set -euo pipefail
else
    set -uo pipefail
fi

# 安全加载配置文件，避免readonly变量冲突
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "警告: 配置文件加载失败，使用默认配置"
    MONITOR_INTERVAL=${MONITOR_INTERVAL:-10}
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi
source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh"

# 初始化统一日志管理器
init_logger "ena_network_monitor" $LOG_LEVEL "${LOGS_DIR}/ena_network_monitor.log"

# ENA监控日志文件 - 避免重复定义只读变量
if [[ -z "${ENA_LOG:-}" ]]; then
    readonly ENA_LOG="${LOGS_DIR}/ena_network_$(date +%Y%m%d_%H%M%S).csv"
fi

# 初始化ENA监控
init_ena_monitoring() {
    log_info "初始化ENA网络监控..."
    
    # 检查ENA监控是否启用
    if [[ "$ENA_MONITOR_ENABLED" != "true" ]]; then
        log_warn "ENA监控已禁用，跳过ENA网络监控"
        return 1
    fi
    
    # 检查网络接口
    if [[ -z "$NETWORK_INTERFACE" ]]; then
        log_error "无法检测到网络接口"
        return 1
    fi
    
    # 检查ethtool是否可用
    if ! command -v ethtool >/dev/null 2>&1; then
        log_error "ethtool命令不可用，无法监控ENA统计信息"
        return 1
    fi
    
    # 检查接口是否支持ENA统计
    if ! ethtool -S "$NETWORK_INTERFACE" &>/dev/null; then
        log_warn "接口 $NETWORK_INTERFACE 不支持ethtool统计"
        return 1
    fi
    
    # 检查是否有ENA allowance字段 - 使用标准化数组访问方式
    local ena_fields_found=0
    ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
    for field in "${ena_fields[@]}"; do
        if ethtool -S "$NETWORK_INTERFACE" 2>/dev/null | grep -q "$field"; then
            ((ena_fields_found++))
        fi
    done
    
    if [[ $ena_fields_found -eq 0 ]]; then
        log_warn "接口 $NETWORK_INTERFACE 不支持ENA allowance监控"
        return 1
    fi
    
    log_info "ENA监控初始化成功"
    echo "   接口: $NETWORK_INTERFACE"
    echo "   支持的ENA字段: $ena_fields_found/${#ena_fields[@]}"
    
    # 创建CSV表头
    generate_ena_csv_header > "$ENA_LOG"
    
    return 0
}

# 生成ENA CSV表头
generate_ena_csv_header() {
    local header="timestamp"
    
    # 添加基础网络统计
    header="$header,interface,rx_bytes,tx_bytes,rx_packets,tx_packets"
    
    ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
    for field in "${ena_fields[@]}"; do
        header="$header,$field"
    done
    
    # 添加计算字段
    header="$header,network_limited,pps_limited,bandwidth_limited"
    
    echo "$header"
}

# 获取ENA网络统计
get_ena_network_stats() {
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    local interface="$NETWORK_INTERFACE"
    
    # 获取基础网络统计
    local rx_bytes=$(cat "/sys/class/net/$interface/statistics/rx_bytes" 2>/dev/null || echo "0")
    local tx_bytes=$(cat "/sys/class/net/$interface/statistics/tx_bytes" 2>/dev/null || echo "0")
    local rx_packets=$(cat "/sys/class/net/$interface/statistics/rx_packets" 2>/dev/null || echo "0")
    local tx_packets=$(cat "/sys/class/net/$interface/statistics/tx_packets" 2>/dev/null || echo "0")
    
    # 获取ENA allowance统计
    local ena_stats=""
    local ethtool_output=$(ethtool -S "$interface" 2>/dev/null || echo "")
    
    ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
    for field in "${ena_fields[@]}"; do
        local value=$(echo "$ethtool_output" | grep "$field:" | awk '{print $2}' || echo "0")
        ena_stats="$ena_stats,$value"
    done
    
    # 计算网络限制状态
    local network_limited="false"
    local pps_limited="false"
    local bandwidth_limited="false"
    
    # 检查PPS限制
    local pps_exceeded=$(echo "$ethtool_output" | grep "pps_allowance_exceeded:" | awk '{print $2}' || echo "0")
    if [[ "$pps_exceeded" -gt 0 ]]; then
        pps_limited="true"
        network_limited="true"
    fi
    
    # 检查带宽限制
    local bw_in_exceeded=$(echo "$ethtool_output" | grep "bw_in_allowance_exceeded:" | awk '{print $2}' || echo "0")
    local bw_out_exceeded=$(echo "$ethtool_output" | grep "bw_out_allowance_exceeded:" | awk '{print $2}' || echo "0")
    if [[ "$bw_in_exceeded" -gt 0 || "$bw_out_exceeded" -gt 0 ]]; then
        bandwidth_limited="true"
        network_limited="true"
    fi
    
    # 输出CSV行
    echo "$timestamp,$interface,$rx_bytes,$tx_bytes,$rx_packets,$tx_packets$ena_stats,$network_limited,$pps_limited,$bandwidth_limited"
}

# 启动ENA监控
start_ena_monitoring() {
    local duration=${1:-3600}
    local interval=${2:-5}
    
    echo "🚀 启动ENA网络监控..."
    echo "   持续时间: ${duration}秒"
    echo "   监控间隔: ${interval}秒"
    echo "   日志文件: $ENA_LOG"
    
    if ! init_ena_monitoring; then
        log_error "ENA监控初始化失败"
        return 1
    fi
    
    local start_time=$(date +%s)
    local end_time=$((start_time + duration))
    
    while [[ $(date +%s) -lt $end_time ]]; do
        get_ena_network_stats >> "$ENA_LOG"
        sleep "$interval"
    done
    
    log_info "ENA网络监控完成"
    echo "   数据已保存到: $ENA_LOG"
}

# 分析ENA网络限制
analyze_ena_limits() {
    local ena_csv="$1"
    
    if [[ ! -f "$ena_csv" ]]; then
        log_error "ENA日志文件不存在: $ena_csv"
        return 1
    fi
    
    echo "📊 分析ENA网络限制..."
    
    # 统计网络限制事件
    local total_samples=$(tail -n +2 "$ena_csv" | wc -l)
    local network_limited_count=$(tail -n +2 "$ena_csv" | awk -F',' '$NF=="true"' | wc -l)
    local pps_limited_count=$(tail -n +2 "$ena_csv" | awk -F',' '$(NF-1)=="true"' | wc -l)
    local bandwidth_limited_count=$(tail -n +2 "$ena_csv" | awk -F',' '$(NF-2)=="true"' | wc -l)
    
    echo "ENA网络限制分析结果:"
    echo "  总样本数: $total_samples"
    echo "  网络受限样本: $network_limited_count ($(echo "scale=2; $network_limited_count * 100 / $total_samples" | bc 2>/dev/null || echo "0")%)"
    echo "  PPS受限样本: $pps_limited_count ($(echo "scale=2; $pps_limited_count * 100 / $total_samples" | bc 2>/dev/null || echo "0")%)"
    echo "  带宽受限样本: $bandwidth_limited_count ($(echo "scale=2; $bandwidth_limited_count * 100 / $total_samples" | bc 2>/dev/null || echo "0")%)"
    
    # 检查最大allowance exceeded值
    echo ""
    echo "最大allowance exceeded值:"
    ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
    for field in "${ena_fields[@]}"; do
        local field_index=$(head -1 "$ena_csv" | tr ',' '\n' | grep -n "^$field$" | cut -d: -f1)
        if [[ -n "$field_index" ]]; then
            local max_value=$(tail -n +2 "$ena_csv" | cut -d',' -f"$field_index" | sort -n | tail -1)
            echo "  $field: $max_value"
        fi
    done
}

# 主函数
main() {
    case "${1:-}" in
        "start")
            start_ena_monitoring "${2:-3600}" "${3:-5}"
            ;;
        "analyze")
            analyze_ena_limits "${2:-$ENA_LOG}"
            ;;
        "test")
            echo "🧪 测试ENA监控功能..."
            if init_ena_monitoring; then
                log_info "ENA监控功能正常"
                get_ena_network_stats
            else
                log_error "ENA监控功能异常"
                exit 1
            fi
            ;;
        *)
            echo "Usage: $0 {start|analyze|test} [duration] [interval]"
            echo ""
            echo "Commands:"
            echo "  start [duration] [interval]  - 启动ENA监控"
            echo "  analyze [csv_file]           - 分析ENA限制"
            echo "  test                         - 测试ENA监控功能"
            echo ""
            echo "Examples:"
            echo "  $0 start 3600 5             - 监控1小时，每5秒采样"
            echo "  $0 analyze ena_network_*.csv - 分析ENA日志"
            echo "  $0 test                      - 测试功能"
            exit 1
            ;;
    esac
}

# 如果直接执行此脚本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
