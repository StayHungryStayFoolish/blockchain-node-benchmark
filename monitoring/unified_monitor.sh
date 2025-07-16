#!/bin/bash
# =====================================================================
# 统一监控器 - 消除重复监控，统一时间管理 (统一日志版本)
# =====================================================================
# 单一监控入口，避免多个脚本重复调用 iostat/mpstat
# 统一时间格式，支持完整的性能指标监控
# 使用统一日志管理器
# =====================================================================

# 严格错误处理 - 但允许在交互式环境中安全使用
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # 脚本直接执行时使用严格模式
    set -euo pipefail
else
    # 被source时使用宽松模式，避免退出shell
    set -uo pipefail
fi

source "$(dirname "${BASH_SOURCE[0]}")/../config/config.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh"

# 初始化统一日志管理器
init_logger "unified_monitor" $LOG_LEVEL "${LOGS_DIR}/unified_monitor.log"

# 错误处理函数
handle_monitor_error() {
    local exit_code=$?
    local line_number=$1
    log_error "监控器错误发生在第 $line_number 行，退出码: $exit_code"
    log_warn "正在停止监控进程..."
    cleanup_monitor_processes
    exit $exit_code
}

# 设置错误陷阱
trap 'handle_monitor_error $LINENO' ERR

# 监控进程清理函数
cleanup_monitor_processes() {
    log_info "清理监控进程..."
    # 停止可能的后台进程
    jobs -p | xargs -r kill 2>/dev/null || true
    # 清理临时文件
    [[ -n "${UNIFIED_LOG:-}" ]] && [[ -f "$UNIFIED_LOG" ]] && {
        log_info "监控数据已保存到: $UNIFIED_LOG"
    }
}

source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh"
source "$(dirname "${BASH_SOURCE[0]}")/iostat_collector.sh"

# 避免重复定义只读变量
if [[ -z "${UNIFIED_LOG:-}" ]]; then
    readonly UNIFIED_LOG="${LOGS_DIR}/performance_$(date +%Y%m%d_%H%M%S).csv"
fi
if [[ -z "${OVERHEAD_LOG:-}" ]]; then
    readonly OVERHEAD_LOG="${LOGS_DIR}/monitoring_overhead_$(date +%Y%m%d_%H%M%S).csv"
fi

MONITOR_PIDS=()
START_TIME=""
END_TIME=""

# 初始化监控环境
init_monitoring() {
    echo "🔧 初始化统一监控环境..."
    
    # 验证配置
    if ! validate_config; then
        return 1
    fi
    
    # 验证设备
    if ! validate_devices; then
        return 1
    fi
    
    # 检查必要命令 - 优雅处理缺失命令
    local missing_commands=()
    local critical_missing=()
    
    # 检查各个命令的可用性
    for cmd in mpstat iostat sar free; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_commands+=("$cmd")
            # iostat是关键命令，其他可以用替代方案
            if [[ "$cmd" == "iostat" ]]; then
                critical_missing+=("$cmd")
            fi
        fi
    done
    
    if [[ ${#missing_commands[@]} -gt 0 ]]; then
        log_warn "缺少部分监控命令: ${missing_commands[*]}"
        echo "⚠️  缺少监控命令: ${missing_commands[*]}"
        echo "💡 建议安装: sudo apt-get install sysstat procps"
        
        # 如果缺少关键命令，则失败
        if [[ ${#critical_missing[@]} -gt 0 ]]; then
            log_error "缺少关键命令: ${critical_missing[*]}，无法继续"
            echo "❌ 缺少关键命令: ${critical_missing[*]}，监控功能无法启动"
            return 1
        else
            echo "🔄 将使用替代方案继续监控..."
        fi
    fi
    
    log_info "统一监控环境初始化完成"
    return 0
}

# CPU 监控 - 统一使用mpstat命令
get_cpu_data() {
    # 统一使用mpstat命令采集CPU指标
    if command -v mpstat >/dev/null 2>&1; then
        local mpstat_output=$(mpstat 1 1 2>/dev/null)
        
        if [[ -n "$mpstat_output" ]]; then
            # mpstat可用，使用原有逻辑
            local avg_line=$(echo "$mpstat_output" | grep "Average.*all" | tail -1)
            if [[ -n "$avg_line" ]]; then
                local fields=($avg_line)
                local start_idx=2
                
                if [[ "${fields[0]}" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2}$ ]]; then
                    start_idx=2
                elif [[ "${fields[0]}" == "Average" ]]; then
                    start_idx=2
                else
                    for i in "${!fields[@]}"; do
                        if [[ "${fields[$i]}" == "all" ]]; then
                            start_idx=$((i + 1))
                            break
                        fi
                    done
                fi
                
                local cpu_usr=${fields[$start_idx]:-0}
                local cpu_sys=${fields[$((start_idx + 2))]:-0}
                local cpu_iowait=${fields[$((start_idx + 3))]:-0}
                local cpu_soft=${fields[$((start_idx + 5))]:-0}
                local cpu_idle=${fields[$((start_idx + 9))]:-0}
                local cpu_usage=$(echo "scale=2; 100 - $cpu_idle" | bc 2>/dev/null || echo "0")
                
                echo "$cpu_usage,$cpu_usr,$cpu_sys,$cpu_iowait,$cpu_soft,$cpu_idle"
                return
            fi
        fi
    fi
    
    # 如果mpstat不可用或失败，返回默认值避免解析错误
    echo "0,0,0,0,0,100"
}

# 内存监控 - 支持free命令和/proc/meminfo替代方案
get_memory_data() {
    # 优先使用free命令
    if command -v free >/dev/null 2>&1; then
        local mem_info=$(free -m 2>/dev/null)
        if [[ -n "$mem_info" ]]; then
            local mem_line=$(echo "$mem_info" | grep "^Mem:")
            local mem_used=$(echo "$mem_line" | awk '{print $3}')
            local mem_total=$(echo "$mem_line" | awk '{print $2}')
            local mem_usage=$(echo "scale=2; $mem_used * 100 / $mem_total" | bc 2>/dev/null || echo "0")
            echo "$mem_used,$mem_total,$mem_usage"
            return
        fi
    fi
    
    # 替代方案：使用/proc/meminfo
    if [[ -r "/proc/meminfo" ]]; then
        local mem_total_kb=$(grep "^MemTotal:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
        local mem_free_kb=$(grep "^MemFree:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
        local mem_available_kb=$(grep "^MemAvailable:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "$mem_free_kb")
        
        if [[ "$mem_total_kb" -gt 0 ]]; then
            # 转换为MB
            local mem_total_mb=$((mem_total_kb / 1024))
            local mem_used_mb=$(((mem_total_kb - mem_available_kb) / 1024))
            local mem_usage=$(echo "scale=2; $mem_used_mb * 100 / $mem_total_mb" | bc 2>/dev/null || echo "0")
            echo "$mem_used_mb,$mem_total_mb,$mem_usage"
            return
        fi
    fi
    
    # 最后的fallback
    echo "0,0,0"
}

# 网络监控 - 支持sar命令和/proc/net/dev替代方案
get_network_data() {
    if [[ -z "$NETWORK_INTERFACE" ]]; then
        echo "unknown,0,0,0,0,0,0,0,0,0"
        return
    fi
    
    # 优先使用 sar 获取网络统计
    if command -v sar >/dev/null 2>&1; then
        local sar_output=$(sar -n DEV 1 1 2>/dev/null | grep "$NETWORK_INTERFACE" | tail -1)
        
        if [[ -n "$sar_output" ]]; then
            local fields=($sar_output)
            
            # 修复：正确处理sar输出格式
            # sar -n DEV输出格式: Time IFACE rxpck/s txpck/s rxkB/s txkB/s rxcmp/s txcmp/s rxmcst/s
            local start_idx=1  # 默认从接口名开始
            
            # 检查第一个字段是否是时间格式
            if [[ "${fields[0]}" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2}$ ]]; then
                start_idx=1  # 接口名在索引1
            else
                # 其他格式，查找接口名的位置
                for i in "${!fields[@]}"; do
                    if [[ "${fields[$i]}" == "$NETWORK_INTERFACE" ]]; then
                        start_idx=$i
                        break
                    fi
                done
            fi
            
            # 确保接口名匹配
            if [[ "${fields[$start_idx]}" != "$NETWORK_INTERFACE" ]]; then
                echo "$NETWORK_INTERFACE,0,0,0,0,0,0,0,0,0"
                return
            fi
            
            # 提取网络统计数据
            local rx_pps=${fields[$((start_idx + 1))]:-0}    # rxpck/s
            local tx_pps=${fields[$((start_idx + 2))]:-0}    # txpck/s  
            local rx_kbs=${fields[$((start_idx + 3))]:-0}    # rxkB/s
            local tx_kbs=${fields[$((start_idx + 4))]:-0}    # txkB/s
            
            # 修复：正确转换为AWS标准的网络带宽单位
            # sar输出的是kB/s (实际是KB/s，十进制)
            # 转换步骤: kB/s -> bytes/s -> bits/s -> Mbps -> Gbps
            local rx_mbps=$(echo "scale=3; $rx_kbs * 8 / 1000" | bc 2>/dev/null || echo "0")
            local tx_mbps=$(echo "scale=3; $tx_kbs * 8 / 1000" | bc 2>/dev/null || echo "0")
            local total_mbps=$(echo "scale=3; $rx_mbps + $tx_mbps" | bc 2>/dev/null || echo "0")
            
            # 转换为Gbps (AWS EC2网络带宽通常以Gbps计量)
            local rx_gbps=$(echo "scale=6; $rx_mbps / 1000" | bc 2>/dev/null || echo "0")
            local tx_gbps=$(echo "scale=6; $tx_mbps / 1000" | bc 2>/dev/null || echo "0")
            local total_gbps=$(echo "scale=6; $total_mbps / 1000" | bc 2>/dev/null || echo "0")
            
            # 计算总PPS
            local total_pps=$(echo "scale=0; $rx_pps + $tx_pps" | bc 2>/dev/null || echo "0")
            
            echo "$NETWORK_INTERFACE,$rx_mbps,$tx_mbps,$total_mbps,$rx_gbps,$tx_gbps,$total_gbps,$rx_pps,$tx_pps,$total_pps"
            return
        fi
    fi
    
    # 替代方案：从/proc/net/dev读取
    if [[ -r "/proc/net/dev" ]]; then
        local net_stats=$(grep "$NETWORK_INTERFACE:" /proc/net/dev 2>/dev/null | head -1)
        if [[ -n "$net_stats" ]]; then
            # 解析/proc/net/dev格式
            # 格式: interface: bytes packets errs drop fifo frame compressed multicast
            local fields=($net_stats)
            local rx_bytes=${fields[1]:-0}
            local rx_packets=${fields[2]:-0}
            local tx_bytes=${fields[9]:-0}
            local tx_packets=${fields[10]:-0}
            
            # 简化计算 - 由于是瞬时读取，无法计算准确的速率
            # 返回基础格式，实际速率为0
            echo "$NETWORK_INTERFACE,0,0,0,0,0,0,0,0,0"
            return
        fi
    fi
    
    # 最后的fallback
    echo "$NETWORK_INTERFACE,0,0,0,0,0,0,0,0,0"
}

get_ena_allowance_data() {
    if [[ "$ENA_MONITOR_ENABLED" != "true" ]]; then
        echo "0,0,0,0,0,0"
        return
    fi
    
    if ! command -v ethtool >/dev/null 2>&1; then
        echo "0,0,0,0,0,0"
        return
    fi
    
    # 检查网络接口是否可用
    if [[ -z "${NETWORK_INTERFACE:-}" ]]; then
        echo "0,0,0,0,0,0"
        return
    fi
    
    local ethtool_output=$(ethtool -S "$NETWORK_INTERFACE" 2>/dev/null || echo "")
    
    # 获取ENA allowance统计
    local bw_in_exceeded=$(echo "$ethtool_output" | grep "bw_in_allowance_exceeded:" | awk '{print $2}' || echo "0")
    local bw_out_exceeded=$(echo "$ethtool_output" | grep "bw_out_allowance_exceeded:" | awk '{print $2}' || echo "0")
    local pps_exceeded=$(echo "$ethtool_output" | grep "pps_allowance_exceeded:" | awk '{print $2}' || echo "0")
    local conntrack_exceeded=$(echo "$ethtool_output" | grep "conntrack_allowance_exceeded:" | awk '{print $2}' || echo "0")
    local linklocal_exceeded=$(echo "$ethtool_output" | grep "linklocal_allowance_exceeded:" | awk '{print $2}' || echo "0")
    local conntrack_available=$(echo "$ethtool_output" | grep "conntrack_allowance_available:" | awk '{print $2}' || echo "0")
    
    echo "$bw_in_exceeded,$bw_out_exceeded,$pps_exceeded,$conntrack_exceeded,$linklocal_exceeded,$conntrack_available"
}

# 加载iostat收集器函数
source "$(dirname "${BASH_SOURCE[0]}")/iostat_collector.sh"
# 加载ENA网络监控器
source "$(dirname "${BASH_SOURCE[0]}")/ena_network_monitor.sh"

# 监控开销统计 (基于真实 /proc/[pid]/io)
get_monitoring_overhead() {
    local total_read_bytes=0
    local total_write_bytes=0
    local total_read_ops=0
    local total_write_ops=0
    
    # 统计所有监控进程的开销
    for pid in "${MONITOR_PIDS[@]}"; do
        if [[ -f "/proc/$pid/io" ]]; then
            local io_stats=$(cat "/proc/$pid/io" 2>/dev/null)
            if [[ -n "$io_stats" ]]; then
                local read_bytes=$(echo "$io_stats" | grep "read_bytes" | awk '{print $2}' || echo "0")
                local write_bytes=$(echo "$io_stats" | grep "write_bytes" | awk '{print $2}' || echo "0")
                local syscr=$(echo "$io_stats" | grep "syscr" | awk '{print $2}' || echo "0")
                local syscw=$(echo "$io_stats" | grep "syscw" | awk '{print $2}' || echo "0")
                
                # 确保变量为数值，如果为空则设为0
                read_bytes=${read_bytes:-0}
                write_bytes=${write_bytes:-0}
                syscr=${syscr:-0}
                syscw=${syscw:-0}

                # 验证是否为数值
                [[ "$read_bytes" =~ ^[0-9]+$ ]] || read_bytes=0
                [[ "$write_bytes" =~ ^[0-9]+$ ]] || write_bytes=0
                [[ "$syscr" =~ ^[0-9]+$ ]] || syscr=0
                [[ "$syscw" =~ ^[0-9]+$ ]] || syscw=0

                total_read_bytes=$((total_read_bytes + read_bytes))
                total_write_bytes=$((total_write_bytes + write_bytes))
                total_read_ops=$((total_read_ops + syscr))
                total_write_ops=$((total_write_ops + syscw))
            fi
        fi
    done
    
    # 计算每秒开销
    local monitoring_iops_per_sec=$(echo "scale=2; ($total_read_ops + $total_write_ops) / $OVERHEAD_STAT_INTERVAL" | bc 2>/dev/null || echo "0")
    local monitoring_throughput_mibs_per_sec=$(echo "scale=6; ($total_read_bytes + $total_write_bytes) / $OVERHEAD_STAT_INTERVAL / 1024 / 1024" | bc 2>/dev/null || echo "0")
    
    echo "$monitoring_iops_per_sec,$monitoring_throughput_mibs_per_sec"
}

# 生成完整 CSV 表头 - 支持条件性ENA字段
generate_csv_header() {
    local basic_header="timestamp,cpu_usage,cpu_usr,cpu_sys,cpu_iowait,cpu_soft,cpu_idle,mem_used,mem_total,mem_usage"
    local device_header=$(generate_all_devices_header)
    local network_header="net_interface,net_rx_mbps,net_tx_mbps,net_total_mbps,net_rx_gbps,net_tx_gbps,net_total_gbps,net_rx_pps,net_tx_pps,net_total_pps"
    local overhead_header="monitoring_iops_per_sec,monitoring_throughput_mibs_per_sec"
    
    # 条件性添加ENA allowance监控字段
    if [[ "$ENA_MONITOR_ENABLED" == "true" ]]; then
        local ena_header="ena_bw_in_exceeded,ena_bw_out_exceeded,ena_pps_exceeded,ena_conntrack_exceeded,ena_linklocal_exceeded,ena_conntrack_available"
        echo "$basic_header,$device_header,$network_header,$ena_header,$overhead_header"
    else
        echo "$basic_header,$device_header,$network_header,$overhead_header"
    fi
}

# 生成JSON格式的监控数据 - 原子写入版本
generate_json_metrics() {
    local timestamp="$1"
    local cpu_data="$2"
    local memory_data="$3"
    local device_data="$4"
    local network_data="$5"
    local ena_data="$6"
    local overhead_data="$7"
    
    # 解析CSV数据为JSON所需的字段
    local cpu_usage=$(echo "$cpu_data" | cut -d',' -f1)
    local mem_usage=$(echo "$memory_data" | cut -d',' -f3)
    
    # 解析网络数据获取总流量
    local net_total_mbps=$(echo "$network_data" | cut -d',' -f4)
    
    # 计算网络利用率
    local network_util=$(echo "scale=2; ($net_total_mbps / $NETWORK_MAX_BANDWIDTH_MBPS) * 100" | bc 2>/dev/null || echo "0")
    # 限制在100%以内
    network_util=$(echo "if ($network_util > 100) 100 else $network_util" | bc 2>/dev/null || echo "0")
    
    # 从设备数据中提取EBS信息 (简化处理，取第一个设备的数据)
    local ebs_util=0
    local ebs_latency=0
    if [[ -n "$device_data" ]]; then
        # 假设设备数据格式为: device1_util,device1_latency,device2_util,device2_latency...
        ebs_util=$(echo "$device_data" | cut -d',' -f2 2>/dev/null || echo "0")
        ebs_latency=$(echo "$device_data" | cut -d',' -f4 2>/dev/null || echo "0")
    fi
    
    # 原子写入latest_metrics.json (核心指标)
    cat > "${MEMORY_SHARE_DIR}/latest_metrics.json.tmp" << EOF
{
    "timestamp": "$timestamp",
    "cpu_usage": $cpu_usage,
    "memory_usage": $mem_usage,
    "ebs_util": $ebs_util,
    "ebs_latency": $ebs_latency,
    "network_util": $network_util,
    "error_rate": 0
}
EOF
    # 原子移动到最终位置
    mv "${MEMORY_SHARE_DIR}/latest_metrics.json.tmp" "${MEMORY_SHARE_DIR}/latest_metrics.json"

    # 原子写入unified_metrics.json (详细指标)
    cat > "${MEMORY_SHARE_DIR}/unified_metrics.json.tmp" << EOF
{
    "timestamp": "$timestamp",
    "cpu_usage": $cpu_usage,
    "memory_usage": $mem_usage,
    "ebs_util": $ebs_util,
    "ebs_latency": $ebs_latency,
    "network_util": $network_util,
    "error_rate": 0,
    "detailed_data": {
        "cpu_data": "$cpu_data",
        "memory_data": "$memory_data",
        "device_data": "$device_data",
        "network_data": "$network_data",
        "ena_data": "$ena_data",
        "overhead_data": "$overhead_data"
    }
}
EOF
    # 原子移动到最终位置
    mv "${MEMORY_SHARE_DIR}/unified_metrics.json.tmp" "${MEMORY_SHARE_DIR}/unified_metrics.json"
}

# 记录性能数据 - 支持条件性ENA数据和JSON生成
log_performance_data() {
    local timestamp=$(get_unified_timestamp)
    local cpu_data=$(get_cpu_data)
    local memory_data=$(get_memory_data)
    local device_data=$(get_all_devices_data)
    local network_data=$(get_network_data)
    local overhead_data=$(get_monitoring_overhead)
    
    # 条件性添加ENA数据
    local ena_data=""
    if [[ "$ENA_MONITOR_ENABLED" == "true" ]]; then
        ena_data=$(get_ena_allowance_data)
        local data_line="$timestamp,$cpu_data,$memory_data,$device_data,$network_data,$ena_data,$overhead_data"
    else
        local data_line="$timestamp,$cpu_data,$memory_data,$device_data,$network_data,$overhead_data"
    fi
    
    # 写入CSV文件
    echo "$data_line" >> "$UNIFIED_LOG"
    
    # 生成JSON文件
    generate_json_metrics "$timestamp" "$cpu_data" "$memory_data" "$device_data" "$network_data" "$ena_data" "$overhead_data"
}

# 启动统一监控 - 修复：支持跟随QPS测试模式
start_unified_monitoring() {
    local duration="$1"
    local interval=${2:-$MONITOR_INTERVAL}
    local follow_qps_test="${3:-false}"
    
    START_TIME=$(get_unified_timestamp)
    
    echo "🚀 启动统一性能监控..."
    echo "  开始时间: $START_TIME"
    echo "  监控间隔: ${interval}秒"
    
    if [[ "$follow_qps_test" == "true" ]]; then
        echo "  模式: 跟随QPS测试 (无时间限制)"
        echo "  控制文件: ${MEMORY_SHARE_DIR}/qps_monitor_control.flag"
    else
        echo "  监控时长: ${duration}秒"
    fi
    
    echo "  数据文件: $UNIFIED_LOG"
    echo ""
    
    # 显示配置状态
    if [[ -n "$LEDGER_DEVICE" ]]; then
        log_info "DATA设备: $LEDGER_DEVICE"
    fi
    
    if [[ -n "$ACCOUNTS_DEVICE" ]]; then
        log_info "ACCOUNTS设备: $ACCOUNTS_DEVICE"
    else
        echo "ℹ️  ACCOUNTS设备未配置"
    fi
    
    if [[ -n "$NETWORK_INTERFACE" ]]; then
        log_info "网络接口: $NETWORK_INTERFACE"
    fi
    
    # 显示ENA监控状态
    if [[ "$ENA_MONITOR_ENABLED" == "true" ]]; then
        log_info "ENA监控: 已启用 (AWS环境)"
    else
        echo "ℹ️  ENA监控: 已禁用 (非AWS环境)"
    fi
    
    # 创建 CSV 表头
    local csv_header=$(generate_csv_header)
    echo "$csv_header" > "$UNIFIED_LOG"
    
    # 创建latest文件软链接，供瓶颈检测使用
    local latest_csv="${LOGS_DIR}/performance_latest.csv"
    ln -sf "$(basename "$UNIFIED_LOG")" "$latest_csv"
    
    log_info "CSV表头已创建 ($(echo "$csv_header" | tr ',' '\n' | wc -l) 个字段)"
    log_info "Latest文件链接已创建: $latest_csv"
    echo ""
    
    # 记录监控进程PID
    MONITOR_PIDS+=($BASHPID)
    
    # 开始监控循环 - 修复：支持跟随QPS测试模式
    local start_time=$(date +%s)
    local sample_count=0
    local last_overhead_time=$start_time
    
    echo "⏰ 开始数据收集..."
    
    if [[ "$follow_qps_test" == "true" ]]; then
        # 跟随QPS测试模式 - 监控直到控制文件状态改变
        while [[ -f "${MEMORY_SHARE_DIR}/qps_monitor_control.flag" ]]; do
            local control_status=$(cat "${MEMORY_SHARE_DIR}/qps_monitor_control.flag" 2>/dev/null || echo "STOPPED")
            
            if [[ "$control_status" != "RUNNING" ]]; then
                echo "📢 收到QPS测试停止信号: $control_status"
                break
            fi
            
            log_performance_data
            sample_count=$((sample_count + 1))
            
            # 进度报告
            if (( sample_count % 12 == 0 )); then
                local current_time=$(date +%s)
                local elapsed=$((current_time - start_time))
                echo "📈 已收集 $sample_count 个样本，已运行 ${elapsed}s (跟随QPS测试中...)"
            fi
            
            sleep "$interval"
        done
    else
        # 固定时长模式
        local end_time=$((start_time + duration))
        
        while [[ $(date +%s) -lt $end_time ]]; do
            log_performance_data
            sample_count=$((sample_count + 1))
            
            # 定期更新监控开销统计
            local current_time=$(date +%s)
            if [[ $((current_time - last_overhead_time)) -ge $OVERHEAD_STAT_INTERVAL ]]; then
                last_overhead_time=$current_time
            fi
            
            # 进度报告
            if (( sample_count % 12 == 0 )); then
                local elapsed=$((current_time - start_time))
                local remaining=$((end_time - current_time))
                echo "📈 已收集 $sample_count 个样本，已运行 ${elapsed}s，剩余 ${remaining}s"
            fi
            
            sleep "$interval"
        done
    fi
    
    END_TIME=$(get_unified_timestamp)
    
    echo ""
    log_info "统一性能监控完成"
    echo "  结束时间: $END_TIME"
    log_info "总样本数: $sample_count"
    echo "📄 数据文件: $UNIFIED_LOG"
    echo "📁 文件大小: $(du -h "$UNIFIED_LOG" | cut -f1)"
}

# 停止监控 - 防止重复调用
STOP_MONITORING_CALLED=false
stop_unified_monitoring() {
    # 防止重复调用
    if [[ "$STOP_MONITORING_CALLED" == "true" ]]; then
        return 0
    fi
    STOP_MONITORING_CALLED=true
    
    echo "🛑 停止统一监控..."
    
    # 终止所有相关进程
    for pid in "${MONITOR_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    
    log_info "统一监控已停止"
}

# 获取监控时间范围 (供其他脚本使用)
get_monitoring_time_range() {
    echo "start_time=$START_TIME"
    echo "end_time=$END_TIME"
}

# 主函数
main() {
    echo "🔧 统一性能监控器"
    echo "=================="
    echo ""
    
    # 初始化
    if ! init_monitoring; then
        exit 1
    fi
    
    # 解析参数 - 修复：添加跟随QPS测试模式
    local duration=$DEFAULT_MONITOR_DURATION
    local interval=$MONITOR_INTERVAL
    local background=false
    local follow_qps_test=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--duration)
                duration="$2"
                shift 2
                ;;
            -i|--interval)
                interval="$2"
                shift 2
                ;;
            -b|--background)
                background=true
                shift
                ;;
            --follow-qps-test)
                follow_qps_test=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [options]"
                echo ""
                echo "Options:"
                echo "  -d, --duration SECONDS    监控时长 (default: $DEFAULT_MONITOR_DURATION)"
                echo "  -i, --interval SECONDS    监控间隔 (default: $MONITOR_INTERVAL)"
                echo "  -b, --background          后台运行"
                echo "  --follow-qps-test         跟随QPS测试模式 (无时间限制)"
                echo "  -h, --help               显示帮助"
                echo ""
                echo "特性:"
                echo "  ✅ 统一监控入口，消除重复监控"
                echo "  ✅ 标准时间格式: $TIMESTAMP_FORMAT"
                echo "  ✅ 完整指标覆盖: CPU, Memory, EBS, Network"
                echo "  ✅ 真实监控开销统计"
                echo "  ✅ 统一字段命名规范"
                echo "  ✅ 跟随QPS测试生命周期"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    if [[ "$background" == "true" ]]; then
        echo "🚀 后台模式启动..."
        if [[ "$follow_qps_test" == "true" ]]; then
            nohup "$0" --follow-qps-test -i "$interval" > "${LOGS_DIR}/unified_monitor.log" 2>&1 &
        else
            nohup "$0" -d "$duration" -i "$interval" > "${LOGS_DIR}/unified_monitor.log" 2>&1 &
        fi
        echo "后台进程PID: $!"
        echo "日志文件: ${LOGS_DIR}/unified_monitor.log"
        echo "数据文件: $UNIFIED_LOG"
    else
        # 设置信号处理
        trap stop_unified_monitoring EXIT INT TERM
        
        start_unified_monitoring "$duration" "$interval" "$follow_qps_test"
    fi
}

# 如果直接执行此脚本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
