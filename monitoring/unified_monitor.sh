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

# 设置错误陷阱 - 只在脚本直接执行时启用
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    trap 'handle_monitor_error $LINENO' ERR
fi

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
if [[ -z "${MONITORING_OVERHEAD_LOG:-}" ]]; then
    readonly MONITORING_OVERHEAD_LOG="${LOGS_DIR}/monitoring_overhead_$(date +%Y%m%d_%H%M%S).csv"
fi

# 监控开销CSV表头定义
readonly OVERHEAD_CSV_HEADER="timestamp,monitoring_cpu_percent,monitoring_memory_percent,monitoring_memory_mb,monitoring_process_count,blockchain_cpu_percent,blockchain_memory_percent,blockchain_memory_mb,blockchain_process_count,system_cpu_cores,system_memory_gb,system_disk_gb,system_cpu_usage,system_memory_usage,system_disk_usage"

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

# 配置化进程发现引擎（带性能监控）
discover_monitoring_processes() {
    local start_time=$(date +%s%3N 2>/dev/null || date +%s)
    local pattern=""
    
    # 构建进程名模式字符串
    if [[ -n "${MONITORING_PROCESS_NAMES[@]}" ]]; then
        pattern=$(IFS='|'; echo "${MONITORING_PROCESS_NAMES[*]}")
        log_debug "使用配置的监控进程名模式: $pattern"
    else
        # 使用默认值作为fallback
        pattern="iostat|mpstat|sar|vmstat|unified_monitor|bottleneck_detector"
        log_debug "使用默认监控进程名模式: $pattern"
    fi
    
    # 获取监控进程列表，排除当前脚本避免自引用
    local monitoring_pids=$(pgrep -f "$pattern" 2>/dev/null | grep -v "^$$\$" | tr '\n' ' ')
    
    if [[ -n "$monitoring_pids" ]]; then
        log_debug "发现监控进程: $monitoring_pids"
    else
        log_debug "未发现监控进程"
    fi
    
    # 性能监控
    local end_time=$(date +%s%3N 2>/dev/null || date +%s)
    local current_resources=$(get_current_process_resources)
    local current_cpu=$(echo "$current_resources" | cut -d',' -f1)
    local current_memory=$(echo "$current_resources" | cut -d',' -f2)
    monitor_performance_impact "discover_monitoring_processes" "$start_time" "$end_time" "$current_cpu" "$current_memory"
    
    echo "$monitoring_pids"
}

# 系统静态资源收集器
get_system_static_resources() {
    # 缓存文件路径
    local cache_file="${MEMORY_SHARE_DIR}/system_static_resources.cache"
    local cache_ttl=3600  # 1小时缓存
    
    # 检查缓存是否存在且未过期
    if [[ -f "$cache_file" ]]; then
        local cache_time=$(stat -c %Y "$cache_file" 2>/dev/null || stat -f %m "$cache_file" 2>/dev/null || echo 0)
        local current_time=$(date +%s)
        local cache_age=$((current_time - cache_time))
        
        if [[ $cache_age -lt $cache_ttl ]]; then
            log_debug "使用缓存的系统静态资源信息"
            cat "$cache_file"
            return
        fi
    fi
    
    log_debug "收集系统静态资源信息"
    
    # 获取CPU核数
    local cpu_cores=1
    if command -v nproc >/dev/null 2>&1; then
        cpu_cores=$(nproc 2>/dev/null || echo 1)
    elif [[ -r "/proc/cpuinfo" ]]; then
        cpu_cores=$(grep -c "^processor" /proc/cpuinfo 2>/dev/null || echo 1)
    elif command -v sysctl >/dev/null 2>&1; then
        # macOS fallback
        cpu_cores=$(sysctl -n hw.ncpu 2>/dev/null || echo 1)
    fi
    
    # 获取总内存 (GB)
    local memory_gb=0
    if command -v free >/dev/null 2>&1; then
        # Linux
        local memory_kb=$(free | awk '/^Mem:/{print $2}' 2>/dev/null || echo 0)
        memory_gb=$(echo "scale=2; $memory_kb / 1024 / 1024" | bc 2>/dev/null || echo 0)
    elif [[ -r "/proc/meminfo" ]]; then
        # Linux fallback
        local memory_kb=$(grep "^MemTotal:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo 0)
        memory_gb=$(echo "scale=2; $memory_kb / 1024" | bc 2>/dev/null || echo 0)
    elif command -v sysctl >/dev/null 2>&1; then
        # macOS
        local memory_bytes=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
        memory_gb=$(echo "scale=2; $memory_bytes / 1024 / 1024 / 1024" | bc 2>/dev/null || echo 0)
    fi
    
    # 获取根分区总磁盘空间 (GB)
    local disk_gb=0
    if command -v df >/dev/null 2>&1; then
        # 获取根分区大小，转换为GB
        disk_gb=$(df / 2>/dev/null | awk 'NR==2{printf "%.2f", $2/1024/1024}' || echo 0)
    fi
    
    # 格式化结果
    local result="${cpu_cores},${memory_gb},${disk_gb}"
    
    # 缓存结果
    if [[ -n "$MEMORY_SHARE_DIR" ]]; then
        mkdir -p "$MEMORY_SHARE_DIR" 2>/dev/null
        echo "$result" > "$cache_file" 2>/dev/null
        log_debug "系统静态资源已缓存: CPU=${cpu_cores}核, 内存=${memory_gb}GB, 磁盘=${disk_gb}GB"
    fi
    
    echo "$result"
}

# 系统动态资源收集器
get_system_dynamic_resources() {
    log_debug "收集系统动态资源使用率"
    
    # 获取系统CPU使用率
    local cpu_usage=0
    if command -v mpstat >/dev/null 2>&1; then
        # 使用mpstat获取CPU使用率 (1秒采样)
        cpu_usage=$(mpstat 1 1 2>/dev/null | awk '/Average:/ && /all/ {print 100-$NF}' | head -1)
        # 验证结果是否为数字
        if ! [[ "$cpu_usage" =~ ^[0-9]+\.?[0-9]*$ ]]; then
            cpu_usage=0
        fi
    elif [[ -r "/proc/stat" ]]; then
        # Linux fallback: 使用/proc/stat
        local cpu_line1=$(grep "^cpu " /proc/stat)
        sleep 1
        local cpu_line2=$(grep "^cpu " /proc/stat)
        
        if [[ -n "$cpu_line1" && -n "$cpu_line2" ]]; then
            local cpu1=($cpu_line1)
            local cpu2=($cpu_line2)
            
            local idle1=${cpu1[4]}
            local idle2=${cpu2[4]}
            local total1=0
            local total2=0
            
            for i in {1..7}; do
                total1=$((total1 + ${cpu1[i]:-0}))
                total2=$((total2 + ${cpu2[i]:-0}))
            done
            
            local idle_diff=$((idle2 - idle1))
            local total_diff=$((total2 - total1))
            
            if [[ $total_diff -gt 0 ]]; then
                cpu_usage=$(echo "scale=1; 100 - ($idle_diff * 100 / $total_diff)" | bc 2>/dev/null || echo 0)
            fi
        fi
    elif command -v top >/dev/null 2>&1; then
        # macOS/通用fallback
        cpu_usage=$(top -l 2 -n 0 2>/dev/null | grep "CPU usage" | tail -1 | awk '{print $3}' | sed 's/%//' || echo 0)
    fi
    
    # 获取系统内存使用率
    local memory_usage=0
    if command -v free >/dev/null 2>&1; then
        # Linux
        memory_usage=$(free 2>/dev/null | awk '/^Mem:/{printf "%.1f", $3/$2*100}' || echo 0)
    elif [[ -r "/proc/meminfo" ]]; then
        # Linux fallback
        local mem_total_kb=$(grep "^MemTotal:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo 1)
        local mem_available_kb=$(grep "^MemAvailable:" /proc/meminfo | awk '{print $2}' 2>/dev/null)
        if [[ -z "$mem_available_kb" ]]; then
            local mem_free_kb=$(grep "^MemFree:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo 0)
            local mem_buffers_kb=$(grep "^Buffers:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo 0)
            local mem_cached_kb=$(grep "^Cached:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo 0)
            mem_available_kb=$((mem_free_kb + mem_buffers_kb + mem_cached_kb))
        fi
        local mem_used_kb=$((mem_total_kb - mem_available_kb))
        memory_usage=$(echo "scale=1; $mem_used_kb * 100 / $mem_total_kb" | bc 2>/dev/null || echo 0)
    elif command -v vm_stat >/dev/null 2>&1; then
        # macOS
        local vm_stat_output=$(vm_stat 2>/dev/null)
        if [[ -n "$vm_stat_output" ]]; then
            local page_size=4096
            local pages_free=$(echo "$vm_stat_output" | grep "Pages free" | awk '{print $3}' | sed 's/\.//')
            local pages_active=$(echo "$vm_stat_output" | grep "Pages active" | awk '{print $3}' | sed 's/\.//')
            local pages_inactive=$(echo "$vm_stat_output" | grep "Pages inactive" | awk '{print $3}' | sed 's/\.//')
            local pages_speculative=$(echo "$vm_stat_output" | grep "Pages speculative" | awk '{print $3}' | sed 's/\.//')
            local pages_wired=$(echo "$vm_stat_output" | grep "Pages wired down" | awk '{print $4}' | sed 's/\.//')
            
            local total_pages=$((pages_free + pages_active + pages_inactive + pages_speculative + pages_wired))
            local used_pages=$((pages_active + pages_inactive + pages_speculative + pages_wired))
            
            if [[ $total_pages -gt 0 ]]; then
                memory_usage=$(echo "scale=1; $used_pages * 100 / $total_pages" | bc 2>/dev/null || echo 0)
            fi
        fi
    fi
    
    # 获取磁盘使用率 (根分区)
    local disk_usage=0
    if command -v df >/dev/null 2>&1; then
        disk_usage=$(df / 2>/dev/null | awk 'NR==2{print $5}' | sed 's/%//' || echo 0)
    fi
    
    # 验证所有数值
    [[ "$cpu_usage" =~ ^[0-9]+\.?[0-9]*$ ]] || cpu_usage=0
    [[ "$memory_usage" =~ ^[0-9]+\.?[0-9]*$ ]] || memory_usage=0
    [[ "$disk_usage" =~ ^[0-9]+$ ]] || disk_usage=0
    
    log_debug "系统动态资源: CPU=${cpu_usage}%, 内存=${memory_usage}%, 磁盘=${disk_usage}%"
    
    echo "${cpu_usage},${memory_usage},${disk_usage}"
}

# 发现区块链节点进程
discover_blockchain_processes() {
    local pattern=""
    
    # 构建区块链进程名模式字符串
    if [[ -n "${BLOCKCHAIN_PROCESS_NAMES[@]}" ]]; then
        pattern=$(IFS='|'; echo "${BLOCKCHAIN_PROCESS_NAMES[*]}")
        log_debug "使用配置的区块链进程名模式: $pattern"
    else
        # 使用默认值作为fallback
        pattern="solana-validator|solana|blockchain"
        log_debug "使用默认区块链进程名模式: $pattern"
    fi
    
    # 获取区块链进程列表
    local blockchain_pids=$(pgrep -f "$pattern" 2>/dev/null | tr '\n' ' ')
    
    if [[ -n "$blockchain_pids" ]]; then
        log_debug "发现区块链进程: $blockchain_pids"
    else
        log_debug "未发现区块链进程"
    fi
    
    echo "$blockchain_pids"
}

# 批量进程资源计算器（带性能监控）
calculate_process_resources() {
    local start_time=$(date +%s%3N 2>/dev/null || date +%s)
    local pids="$1"
    local process_type="${2:-unknown}"
    
    if [[ -z "$pids" ]]; then
        log_debug "没有${process_type}进程需要统计"
        echo "0,0,0,0"
        return
    fi
    
    # 清理PID字符串，转换为逗号分隔格式
    pids=$(echo "$pids" | tr -s ' ' | sed 's/^ *//;s/ *$//' | tr ' ' ',')
    
    # 使用单次ps命令批量查询所有进程 (跨平台兼容)
    local proc_stats=""
    if command -v ps >/dev/null 2>&1; then
        # 检测操作系统类型
        if [[ "$(uname -s)" == "Linux" ]]; then
            # Linux格式
            proc_stats=$(ps -p $pids -o %cpu,%mem,rss --no-headers 2>/dev/null)
        else
            # macOS/BSD格式
            proc_stats=$(ps -p $pids -o pcpu,pmem,rss 2>/dev/null | tail -n +2)
        fi
        
        # 如果第一种格式失败，尝试另一种格式
        if [[ -z "$proc_stats" ]]; then
            if [[ "$(uname -s)" == "Linux" ]]; then
                proc_stats=$(ps -p $pids -o pcpu,pmem,rss 2>/dev/null | tail -n +2)
            else
                proc_stats=$(ps -p $pids -o %cpu,%mem,rss --no-headers 2>/dev/null)
            fi
        fi
    fi
    
    if [[ -z "$proc_stats" ]]; then
        log_debug "${process_type}进程资源查询失败，PID: $pids"
        echo "0,0,0,0"
        return
    fi
    
    local total_cpu=0 total_memory=0 total_memory_mb=0 count=0
    
    while read -r cpu mem rss; do
        # 跳过空行
        [[ -n "$cpu" ]] || continue
        
        # 数值验证和累加
        if [[ "$cpu" =~ ^[0-9]+\.?[0-9]*$ ]]; then
            total_cpu=$(echo "$total_cpu + $cpu" | bc -l 2>/dev/null || echo $total_cpu)
        fi
        
        if [[ "$mem" =~ ^[0-9]+\.?[0-9]*$ ]]; then
            total_memory=$(echo "$total_memory + $mem" | bc -l 2>/dev/null || echo $total_memory)
        fi
        
        if [[ "$rss" =~ ^[0-9]+$ ]]; then
            local rss_mb=$(echo "scale=2; $rss / 1024" | bc -l 2>/dev/null || echo 0)
            total_memory_mb=$(echo "$total_memory_mb + $rss_mb" | bc -l 2>/dev/null || echo $total_memory_mb)
        fi
        
        count=$((count + 1))
    done <<< "$proc_stats"
    
    log_debug "${process_type}进程资源统计: CPU=${total_cpu}%, 内存=${total_memory}%, 内存MB=${total_memory_mb}, 进程数=${count}"
    
    # 性能监控
    local end_time=$(date +%s%3N 2>/dev/null || date +%s)
    local current_resources=$(get_current_process_resources)
    local current_cpu=$(echo "$current_resources" | cut -d',' -f1)
    local current_memory=$(echo "$current_resources" | cut -d',' -f2)
    monitor_performance_impact "calculate_process_resources_${process_type}" "$start_time" "$end_time" "$current_cpu" "$current_memory"
    
    echo "$total_cpu,$total_memory,$total_memory_mb,$count"
}

# 监控开销统计 (重写版 - 使用配置化进程发现)
get_monitoring_overhead() {
    # 使用新的进程发现引擎
    local monitoring_pids=$(discover_monitoring_processes)
    
    if [[ -z "$monitoring_pids" ]]; then
        log_debug "未发现监控进程，返回零开销"
        echo "0,0"
        return
    fi
    
    # 计算监控进程资源使用
    local monitoring_resources=$(calculate_process_resources "$monitoring_pids" "监控")
    
    # 解析资源统计结果
    local monitoring_cpu=$(echo "$monitoring_resources" | cut -d',' -f1)
    local monitoring_memory_percent=$(echo "$monitoring_resources" | cut -d',' -f2)
    local monitoring_memory_mb=$(echo "$monitoring_resources" | cut -d',' -f3)
    local process_count=$(echo "$monitoring_resources" | cut -d',' -f4)
    
    # 改进的I/O估算 - 基于实际进程数量和类型
    # 不同类型的监控进程有不同的I/O特征
    local base_iops_per_process=0.2  # 每个监控进程的基础IOPS
    local base_throughput_per_process=0.0005  # 每个监控进程的基础吞吐量(MiB/s)
    
    # 根据进程数量计算I/O开销
    local estimated_iops=$(echo "scale=2; $process_count * $base_iops_per_process" | bc 2>/dev/null || echo "0.00")
    local estimated_throughput=$(echo "scale=6; $process_count * $base_throughput_per_process" | bc 2>/dev/null || echo "0.000000")
    
    # 如果CPU使用率较高，增加I/O估算
    if (( $(echo "$monitoring_cpu > 5.0" | bc -l 2>/dev/null || echo 0) )); then
        estimated_iops=$(echo "scale=2; $estimated_iops * 1.5" | bc 2>/dev/null || echo "$estimated_iops")
        estimated_throughput=$(echo "scale=6; $estimated_throughput * 1.5" | bc 2>/dev/null || echo "$estimated_throughput")
    fi
    
    # 确保数值格式正确
    estimated_iops=$(printf "%.2f" "$estimated_iops" 2>/dev/null || echo "0.00")
    estimated_throughput=$(printf "%.6f" "$estimated_throughput" 2>/dev/null || echo "0.000000")
    
    log_debug "监控开销统计: 进程数=${process_count}, CPU=${monitoring_cpu}%, 内存=${monitoring_memory_percent}%(${monitoring_memory_mb}MB), 估算IOPS=${estimated_iops}, 估算吞吐量=${estimated_throughput}MiB/s"
    
    # 保持原有返回格式 (IOPS, 吞吐量)
    echo "$estimated_iops,$estimated_throughput"
}

# 系统静态资源收集器
get_system_static_resources() {
    # 获取系统静态资源信息（不经常变化的信息）
    local cpu_cores=$(nproc 2>/dev/null || echo 1)
    
    # 获取内存总量
    local memory_gb=0
    if command -v free >/dev/null 2>&1; then
        # Linux
        local memory_kb=$(free -k 2>/dev/null | awk '/^Mem:/{print $2}')
        if [[ -n "$memory_kb" && "$memory_kb" -gt 0 ]]; then
            memory_gb=$(echo "scale=2; $memory_kb / 1024 / 1024" | bc 2>/dev/null || echo 0)
        fi
    elif [[ -r "/proc/meminfo" ]]; then
        # Linux fallback
        local memory_kb=$(grep "^MemTotal:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo 0)
        if [[ "$memory_kb" -gt 0 ]]; then
            memory_gb=$(echo "scale=2; $memory_kb / 1024 / 1024" | bc 2>/dev/null || echo 0)
        fi
    elif command -v system_profiler >/dev/null 2>&1; then
        # macOS
        local memory_bytes=$(system_profiler SPHardwareDataType 2>/dev/null | grep "Memory:" | awk '{print $2}' | sed 's/GB//')
        if [[ -n "$memory_bytes" ]]; then
            memory_gb="$memory_bytes"
        fi
    fi
    
    # 获取根分区总空间
    local disk_gb=0
    if command -v df >/dev/null 2>&1; then
        local disk_kb=$(df / 2>/dev/null | awk 'NR==2{print $2}')
        if [[ -n "$disk_kb" && "$disk_kb" -gt 0 ]]; then
            disk_gb=$(echo "scale=2; $disk_kb / 1024 / 1024" | bc 2>/dev/null || echo 0)
        fi
    fi
    
    log_debug "系统静态资源: CPU=${cpu_cores}核, 内存=${memory_gb}GB, 磁盘=${disk_gb}GB"
    
    echo "$cpu_cores,$memory_gb,$disk_gb"
}

# 系统动态资源收集器
get_system_dynamic_resources() {
    # 获取系统当前资源使用率
    local cpu_usage=0
    local memory_usage=0
    local disk_usage=0
    
    # 获取CPU使用率
    if command -v mpstat >/dev/null 2>&1; then
        cpu_usage=$(mpstat 1 1 2>/dev/null | awk '/Average:/ && /all/ {print 100-$NF}' | head -1)
        if [[ -z "$cpu_usage" ]]; then
            cpu_usage=0
        fi
    elif command -v top >/dev/null 2>&1; then
        # 使用top作为fallback (macOS/Linux兼容)
        cpu_usage=$(top -l 1 -n 0 2>/dev/null | grep "CPU usage" | awk '{print $3}' | sed 's/%//' || echo 0)
        if [[ -z "$cpu_usage" ]]; then
            cpu_usage=0
        fi
    fi
    
    # 获取内存使用率
    if command -v free >/dev/null 2>&1; then
        memory_usage=$(free 2>/dev/null | awk '/^Mem:/{printf "%.1f", $3/$2*100}' || echo 0)
    elif [[ -r "/proc/meminfo" ]]; then
        local mem_total_kb=$(grep "^MemTotal:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo 1)
        local mem_available_kb=$(grep "^MemAvailable:" /proc/meminfo | awk '{print $2}' 2>/dev/null)
        if [[ -z "$mem_available_kb" ]]; then
            local mem_free_kb=$(grep "^MemFree:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo 0)
            mem_available_kb="$mem_free_kb"
        fi
        local mem_used_kb=$((mem_total_kb - mem_available_kb))
        memory_usage=$(echo "scale=1; $mem_used_kb * 100 / $mem_total_kb" | bc 2>/dev/null || echo 0)
    fi
    
    # 获取磁盘使用率
    if command -v df >/dev/null 2>&1; then
        disk_usage=$(df / 2>/dev/null | awk 'NR==2{print $5}' | sed 's/%//' || echo 0)
    fi
    
    log_debug "系统动态资源: CPU=${cpu_usage}%, 内存=${memory_usage}%, 磁盘=${disk_usage}%"
    
    echo "$cpu_usage,$memory_usage,$disk_usage"
}

# 区块链节点资源统计
get_blockchain_node_resources() {
    # 使用新的进程发现引擎获取区块链进程
    local blockchain_pids=$(discover_blockchain_processes)
    
    if [[ -z "$blockchain_pids" ]]; then
        log_debug "未发现区块链进程，返回零资源使用"
        echo "0,0,0,0"
        return
    fi
    
    # 计算区块链进程资源使用
    local blockchain_resources=$(calculate_process_resources "$blockchain_pids" "区块链")
    
    # 解析资源统计结果
    local blockchain_cpu=$(echo "$blockchain_resources" | cut -d',' -f1)
    local blockchain_memory_percent=$(echo "$blockchain_resources" | cut -d',' -f2)
    local blockchain_memory_mb=$(echo "$blockchain_resources" | cut -d',' -f3)
    local process_count=$(echo "$blockchain_resources" | cut -d',' -f4)
    
    log_debug "区块链节点资源: 进程数=${process_count}, CPU=${blockchain_cpu}%, 内存=${blockchain_memory_percent}%(${blockchain_memory_mb}MB)"
    
    echo "$blockchain_cpu,$blockchain_memory_percent,$blockchain_memory_mb,$process_count"
}

# 性能影响监控配置
readonly PERFORMANCE_MONITORING_ENABLED=${PERFORMANCE_MONITORING_ENABLED:-true}
readonly MAX_COLLECTION_TIME_MS=${MAX_COLLECTION_TIME_MS:-1000}  # 最大收集时间1秒
readonly CPU_THRESHOLD_PERCENT=${CPU_THRESHOLD_PERCENT:-5.0}     # CPU使用率阈值5%
readonly MEMORY_THRESHOLD_MB=${MEMORY_THRESHOLD_MB:-100}         # 内存使用阈值100MB
readonly PERFORMANCE_LOG="${LOGS_DIR}/monitoring_performance_$(date +%Y%m%d_%H%M%S).log"

# 性能影响监控函数
monitor_performance_impact() {
    local function_name="$1"
    local start_time="$2"
    local end_time="$3"
    local cpu_usage="$4"
    local memory_usage="$5"
    
    if [[ "$PERFORMANCE_MONITORING_ENABLED" != "true" ]]; then
        return 0
    fi
    
    # 计算执行时间（毫秒）
    local execution_time_ms=$(( (end_time - start_time) ))
    
    # 检查性能阈值
    local warnings=()
    
    # 检查执行时间
    if (( execution_time_ms > MAX_COLLECTION_TIME_MS )); then
        warnings+=("执行时间超标: ${execution_time_ms}ms > ${MAX_COLLECTION_TIME_MS}ms")
    fi
    
    # 检查CPU使用率
    if (( $(echo "$cpu_usage > $CPU_THRESHOLD_PERCENT" | bc -l 2>/dev/null || echo 0) )); then
        warnings+=("CPU使用率超标: ${cpu_usage}% > ${CPU_THRESHOLD_PERCENT}%")
    fi
    
    # 检查内存使用
    if (( $(echo "$memory_usage > $MEMORY_THRESHOLD_MB" | bc -l 2>/dev/null || echo 0) )); then
        warnings+=("内存使用超标: ${memory_usage}MB > ${MEMORY_THRESHOLD_MB}MB")
    fi
    
    # 记录性能数据
    local timestamp=$(get_unified_timestamp)
    local performance_entry="${timestamp},${function_name},${execution_time_ms},${cpu_usage},${memory_usage}"
    
    # 写入性能日志
    if [[ ! -f "$PERFORMANCE_LOG" ]]; then
        echo "timestamp,function_name,execution_time_ms,cpu_percent,memory_mb" > "$PERFORMANCE_LOG"
    fi
    echo "$performance_entry" >> "$PERFORMANCE_LOG"
    
    # 如果有警告，记录到主日志
    if [[ ${#warnings[@]} -gt 0 ]]; then
        log_warn "监控性能警告 - 函数: $function_name"
        for warning in "${warnings[@]}"; do
            log_warn "  - $warning"
        done
        
        # 生成优化建议
        generate_performance_optimization_suggestions "$function_name" "${warnings[@]}"
    fi
    
    log_debug "性能监控: $function_name 执行时间=${execution_time_ms}ms CPU=${cpu_usage}% 内存=${memory_usage}MB"
}

# 生成性能优化建议
generate_performance_optimization_suggestions() {
    local function_name="$1"
    shift
    local warnings=("$@")
    
    log_info "🔧 性能优化建议 - $function_name:"
    
    for warning in "${warnings[@]}"; do
        if [[ "$warning" == *"执行时间超标"* ]]; then
            log_info "  💡 建议: 考虑增加MONITOR_INTERVAL间隔或优化数据收集逻辑"
        elif [[ "$warning" == *"CPU使用率超标"* ]]; then
            log_info "  💡 建议: 减少监控进程数量或降低监控频率"
        elif [[ "$warning" == *"内存使用超标"* ]]; then
            log_info "  💡 建议: 优化数据结构或增加内存清理逻辑"
        fi
    done
    
    log_info "  📊 查看详细性能数据: $PERFORMANCE_LOG"
}

# 生成性能影响报告
generate_performance_impact_report() {
    local report_file="${LOGS_DIR}/monitoring_performance_report_$(date +%Y%m%d_%H%M%S).txt"
    
    if [[ ! -f "$PERFORMANCE_LOG" ]]; then
        log_warn "性能日志文件不存在，无法生成报告: $PERFORMANCE_LOG"
        return 1
    fi
    
    log_info "生成性能影响报告: $report_file"
    
    {
        echo "# 监控系统性能影响报告"
        echo "生成时间: $(date)"
        echo "数据来源: $PERFORMANCE_LOG"
        echo ""
        
        # 统计总体性能数据
        echo "## 总体性能统计"
        local total_records=$(tail -n +2 "$PERFORMANCE_LOG" | wc -l)
        echo "总记录数: $total_records"
        
        if [[ $total_records -gt 0 ]]; then
            # 平均执行时间
            local avg_time=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f3 | awk '{sum+=$1} END {print sum/NR}')
            echo "平均执行时间: ${avg_time:-0} ms"
            
            # 最大执行时间
            local max_time=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f3 | sort -n | tail -1)
            echo "最大执行时间: ${max_time:-0} ms"
            
            # 平均CPU使用率
            local avg_cpu=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f4 | awk '{sum+=$1} END {print sum/NR}')
            echo "平均CPU使用率: ${avg_cpu:-0}%"
            
            # 平均内存使用
            local avg_memory=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f5 | awk '{sum+=$1} END {print sum/NR}')
            echo "平均内存使用: ${avg_memory:-0} MB"
        fi
        
        echo ""
        
        # 按函数分组统计
        echo "## 按函数分组统计"
        tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f2 | sort | uniq | while read -r func_name; do
            echo "### $func_name"
            local func_data=$(tail -n +2 "$PERFORMANCE_LOG" | grep ",$func_name,")
            local func_count=$(echo "$func_data" | wc -l)
            local func_avg_time=$(echo "$func_data" | cut -d',' -f3 | awk '{sum+=$1} END {print sum/NR}')
            local func_max_time=$(echo "$func_data" | cut -d',' -f3 | sort -n | tail -1)
            local func_avg_cpu=$(echo "$func_data" | cut -d',' -f4 | awk '{sum+=$1} END {print sum/NR}')
            local func_avg_memory=$(echo "$func_data" | cut -d',' -f5 | awk '{sum+=$1} END {print sum/NR}')
            
            echo "- 调用次数: $func_count"
            echo "- 平均执行时间: ${func_avg_time:-0} ms"
            echo "- 最大执行时间: ${func_max_time:-0} ms"
            echo "- 平均CPU使用率: ${func_avg_cpu:-0}%"
            echo "- 平均内存使用: ${func_avg_memory:-0} MB"
            echo ""
        done
        
        # 性能警告统计
        echo "## 性能警告分析"
        local warning_count=$(tail -n +2 "$PERFORMANCE_LOG" | awk -F',' -v max_time="$MAX_COLLECTION_TIME_MS" -v max_cpu="$CPU_THRESHOLD_PERCENT" -v max_mem="$MEMORY_THRESHOLD_MB" '
            $3 > max_time || $4 > max_cpu || $5 > max_mem {count++} 
            END {print count+0}')
        
        echo "超标记录数: $warning_count / $total_records"
        
        if [[ $warning_count -gt 0 ]]; then
            echo ""
            echo "### 超标记录详情"
            tail -n +2 "$PERFORMANCE_LOG" | awk -F',' -v max_time="$MAX_COLLECTION_TIME_MS" -v max_cpu="$CPU_THRESHOLD_PERCENT" -v max_mem="$MEMORY_THRESHOLD_MB" '
                $3 > max_time || $4 > max_cpu || $5 > max_mem {
                    printf "- %s %s: 执行时间=%sms CPU=%s%% 内存=%sMB\n", $1, $2, $3, $4, $5
                }'
        fi
        
        echo ""
        echo "## 优化建议"
        
        if [[ $warning_count -gt 0 ]]; then
            local warning_ratio=$(echo "scale=2; $warning_count * 100 / $total_records" | bc -l)
            echo "- 警告比例: ${warning_ratio}%"
            
            if (( $(echo "$warning_ratio > 10" | bc -l) )); then
                echo "- 🔴 高风险: 超过10%的监控操作存在性能问题"
                echo "  建议: 立即优化监控频率或算法"
            elif (( $(echo "$warning_ratio > 5" | bc -l) )); then
                echo "- 🟡 中风险: 5-10%的监控操作存在性能问题"
                echo "  建议: 考虑优化监控配置"
            else
                echo "- 🟢 低风险: 少于5%的监控操作存在性能问题"
                echo "  建议: 继续监控，定期检查"
            fi
        else
            echo "- 🟢 优秀: 所有监控操作都在性能阈值内"
            echo "  建议: 保持当前配置"
        fi
        
    } > "$report_file"
    
    log_info "性能影响报告已生成: $report_file"
    return 0
}

# 自动性能优化建议系统
auto_performance_optimization_advisor() {
    if [[ ! -f "$PERFORMANCE_LOG" ]]; then
        return 0
    fi
    
    local total_records=$(tail -n +2 "$PERFORMANCE_LOG" | wc -l)
    
    # 需要至少10条记录才能进行分析
    if [[ $total_records -lt 10 ]]; then
        return 0
    fi
    
    log_info "🤖 自动性能优化分析 (基于 $total_records 条记录)"
    
    # 分析执行时间趋势
    local avg_time=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f3 | awk '{sum+=$1} END {print sum/NR}')
    local max_time=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f3 | sort -n | tail -1)
    
    if (( $(echo "$avg_time > $MAX_COLLECTION_TIME_MS * 0.8" | bc -l 2>/dev/null || echo 0) )); then
        log_warn "⚠️  平均执行时间接近阈值 (${avg_time}ms vs ${MAX_COLLECTION_TIME_MS}ms)"
        log_info "💡 建议: 考虑将MONITOR_INTERVAL从${MONITOR_INTERVAL}s增加到$((MONITOR_INTERVAL * 2))s"
    fi
    
    # 分析CPU使用趋势
    local avg_cpu=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f4 | awk '{sum+=$1} END {print sum/NR}')
    
    if (( $(echo "$avg_cpu > $CPU_THRESHOLD_PERCENT * 0.8" | bc -l 2>/dev/null || echo 0) )); then
        log_warn "⚠️  平均CPU使用率接近阈值 (${avg_cpu}% vs ${CPU_THRESHOLD_PERCENT}%)"
        log_info "💡 建议: 减少监控进程数量或优化进程发现算法"
    fi
    
    # 分析内存使用趋势
    local avg_memory=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f5 | awk '{sum+=$1} END {print sum/NR}')
    
    if (( $(echo "$avg_memory > $MEMORY_THRESHOLD_MB * 0.8" | bc -l 2>/dev/null || echo 0) )); then
        log_warn "⚠️  平均内存使用接近阈值 (${avg_memory}MB vs ${MEMORY_THRESHOLD_MB}MB)"
        log_info "💡 建议: 优化数据结构或增加内存清理逻辑"
    fi
    
    # 分析最慢的函数
    local slowest_func=$(tail -n +2 "$PERFORMANCE_LOG" | sort -t',' -k3 -n | tail -1 | cut -d',' -f2)
    local slowest_time=$(tail -n +2 "$PERFORMANCE_LOG" | sort -t',' -k3 -n | tail -1 | cut -d',' -f3)
    
    if [[ -n "$slowest_func" ]] && (( $(echo "$slowest_time > $MAX_COLLECTION_TIME_MS" | bc -l 2>/dev/null || echo 0) )); then
        log_warn "🐌 最慢函数: $slowest_func (${slowest_time}ms)"
        
        case "$slowest_func" in
            *"discover_monitoring_processes"*)
                log_info "💡 建议: 优化进程发现算法，考虑缓存进程列表"
                ;;
            *"calculate_process_resources"*)
                log_info "💡 建议: 减少ps命令调用频率或优化资源计算逻辑"
                ;;
            *"collect_monitoring_overhead_data"*)
                log_info "💡 建议: 分解数据收集步骤，考虑异步处理"
                ;;
            *)
                log_info "💡 建议: 分析 $slowest_func 函数的具体实现"
                ;;
        esac
    fi
    
    # 生成配置优化建议
    log_info "📋 当前配置优化建议:"
    log_info "  - MONITOR_INTERVAL: ${MONITOR_INTERVAL}s (当前) -> 建议范围: 5-30s"
    log_info "  - MAX_COLLECTION_TIME_MS: ${MAX_COLLECTION_TIME_MS}ms (当前) -> 建议范围: 500-2000ms"
    log_info "  - CPU_THRESHOLD_PERCENT: ${CPU_THRESHOLD_PERCENT}% (当前) -> 建议范围: 3-10%"
    log_info "  - MEMORY_THRESHOLD_MB: ${MEMORY_THRESHOLD_MB}MB (当前) -> 建议范围: 50-200MB"
}

# 自适应频率调整配置
readonly ADAPTIVE_FREQUENCY_ENABLED=${ADAPTIVE_FREQUENCY_ENABLED:-true}
readonly MIN_MONITOR_INTERVAL=${MIN_MONITOR_INTERVAL:-2}      # 最小监控间隔2秒
readonly MAX_MONITOR_INTERVAL=${MAX_MONITOR_INTERVAL:-30}     # 最大监控间隔30秒
readonly SYSTEM_LOAD_THRESHOLD=${SYSTEM_LOAD_THRESHOLD:-80}  # 系统负载阈值80%
readonly FREQUENCY_ADJUSTMENT_LOG="${LOGS_DIR}/frequency_adjustment_$(date +%Y%m%d_%H%M%S).log"

# 当前动态监控间隔（全局变量）
CURRENT_MONITOR_INTERVAL=${MONITOR_INTERVAL}

# 系统负载评估函数
assess_system_load() {
    local cpu_usage=0
    local memory_usage=0
    local load_average=0
    
    # 获取CPU使用率
    if command -v mpstat >/dev/null 2>&1; then
        cpu_usage=$(mpstat 1 1 | awk '/Average/ && /all/ {print 100-$NF}' 2>/dev/null || echo 0)
    elif command -v top >/dev/null 2>&1; then
        # 使用top命令获取CPU使用率
        cpu_usage=$(top -l 1 -n 0 | grep "CPU usage" | awk '{print $3}' | sed 's/%//' 2>/dev/null || echo 0)
    fi
    
    # 获取内存使用率
    if command -v free >/dev/null 2>&1; then
        memory_usage=$(free | awk '/^Mem:/ {printf "%.1f", $3/$2 * 100}' 2>/dev/null || echo 0)
    elif [[ -f /proc/meminfo ]]; then
        local mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        local mem_available=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
        if [[ -n "$mem_total" && -n "$mem_available" ]]; then
            memory_usage=$(echo "scale=1; ($mem_total - $mem_available) * 100 / $mem_total" | bc -l 2>/dev/null || echo 0)
        fi
    elif command -v vm_stat >/dev/null 2>&1; then
        # macOS系统
        local vm_stat_output=$(vm_stat)
        local pages_free=$(echo "$vm_stat_output" | grep "Pages free" | awk '{print $3}' | sed 's/\.//')
        local pages_active=$(echo "$vm_stat_output" | grep "Pages active" | awk '{print $3}' | sed 's/\.//')
        local pages_inactive=$(echo "$vm_stat_output" | grep "Pages inactive" | awk '{print $3}' | sed 's/\.//')
        local pages_wired=$(echo "$vm_stat_output" | grep "Pages wired down" | awk '{print $4}' | sed 's/\.//')
        
        if [[ -n "$pages_free" && -n "$pages_active" && -n "$pages_inactive" && -n "$pages_wired" ]]; then
            local total_pages=$((pages_free + pages_active + pages_inactive + pages_wired))
            local used_pages=$((pages_active + pages_inactive + pages_wired))
            memory_usage=$(echo "scale=1; $used_pages * 100 / $total_pages" | bc -l 2>/dev/null || echo 0)
        fi
    fi
    
    # 获取系统负载平均值
    if [[ -f /proc/loadavg ]]; then
        load_average=$(cut -d' ' -f1 /proc/loadavg 2>/dev/null || echo 0)
    elif command -v uptime >/dev/null 2>&1; then
        load_average=$(uptime | awk -F'load average:' '{print $2}' | awk -F',' '{print $1}' | tr -d ' ' 2>/dev/null || echo 0)
    fi
    
    # 计算综合负载分数 (0-100)
    local cpu_score=$(echo "scale=0; $cpu_usage" | bc -l 2>/dev/null || echo 0)
    local memory_score=$(echo "scale=0; $memory_usage" | bc -l 2>/dev/null || echo 0)
    
    # 负载平均值转换为分数 (假设4核系统，负载4.0为100%)
    local cpu_cores=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
    local load_score=$(echo "scale=0; $load_average * 100 / $cpu_cores" | bc -l 2>/dev/null || echo 0)
    
    # 取最高分数作为系统负载
    local system_load=$cpu_score
    if (( $(echo "$memory_score > $system_load" | bc -l 2>/dev/null || echo 0) )); then
        system_load=$memory_score
    fi
    if (( $(echo "$load_score > $system_load" | bc -l 2>/dev/null || echo 0) )); then
        system_load=$load_score
    fi
    
    # 确保负载值在合理范围内
    if (( $(echo "$system_load < 0" | bc -l 2>/dev/null || echo 0) )); then
        system_load=0
    elif (( $(echo "$system_load > 100" | bc -l 2>/dev/null || echo 0) )); then
        system_load=100
    fi
    
    log_debug "系统负载评估: CPU=${cpu_usage}% 内存=${memory_usage}% 负载=${load_average} 综合=${system_load}%"
    echo "$system_load"
}

# 自适应频率调整函数
adaptive_frequency_adjustment() {
    if [[ "$ADAPTIVE_FREQUENCY_ENABLED" != "true" ]]; then
        return 0
    fi
    
    local system_load=$(assess_system_load)
    local old_interval=$CURRENT_MONITOR_INTERVAL
    local new_interval=$CURRENT_MONITOR_INTERVAL
    local adjustment_reason=""
    
    # 根据系统负载调整监控频率
    if (( $(echo "$system_load > $SYSTEM_LOAD_THRESHOLD" | bc -l 2>/dev/null || echo 0) )); then
        # 高负载：降低监控频率（增加间隔）
        new_interval=$(echo "scale=0; $CURRENT_MONITOR_INTERVAL * 1.5" | bc -l 2>/dev/null || echo $CURRENT_MONITOR_INTERVAL)
        adjustment_reason="高系统负载 (${system_load}%)"
    elif (( $(echo "$system_load < 50" | bc -l 2>/dev/null || echo 0) )); then
        # 低负载：可以提高监控频率（减少间隔）
        new_interval=$(echo "scale=0; $CURRENT_MONITOR_INTERVAL * 0.8" | bc -l 2>/dev/null || echo $CURRENT_MONITOR_INTERVAL)
        adjustment_reason="低系统负载 (${system_load}%)"
    fi
    
    # 检查性能历史，如果监控本身性能有问题，也要降低频率
    if [[ -f "$PERFORMANCE_LOG" ]]; then
        local recent_avg_time=$(tail -20 "$PERFORMANCE_LOG" 2>/dev/null | tail -n +2 | cut -d',' -f3 | awk '{sum+=$1} END {print sum/NR}' 2>/dev/null || echo 0)
        
        if (( $(echo "$recent_avg_time > $MAX_COLLECTION_TIME_MS * 0.8" | bc -l 2>/dev/null || echo 0) )); then
            new_interval=$(echo "scale=0; $CURRENT_MONITOR_INTERVAL * 1.3" | bc -l 2>/dev/null || echo $CURRENT_MONITOR_INTERVAL)
            adjustment_reason="监控性能下降 (${recent_avg_time}ms)"
        fi
    fi
    
    # 限制调整范围
    if (( $(echo "$new_interval < $MIN_MONITOR_INTERVAL" | bc -l 2>/dev/null || echo 0) )); then
        new_interval=$MIN_MONITOR_INTERVAL
    elif (( $(echo "$new_interval > $MAX_MONITOR_INTERVAL" | bc -l 2>/dev/null || echo 0) )); then
        new_interval=$MAX_MONITOR_INTERVAL
    fi
    
    # 只有变化超过1秒才进行调整
    local interval_diff=$(echo "scale=0; $new_interval - $old_interval" | bc -l 2>/dev/null || echo 0)
    if (( $(echo "$interval_diff > 1 || $interval_diff < -1" | bc -l 2>/dev/null || echo 0) )); then
        CURRENT_MONITOR_INTERVAL=$(printf "%.0f" "$new_interval")
        
        # 记录频率调整
        log_frequency_adjustment "$old_interval" "$CURRENT_MONITOR_INTERVAL" "$system_load" "$adjustment_reason"
        
        log_info "🔄 自适应频率调整: ${old_interval}s -> ${CURRENT_MONITOR_INTERVAL}s (原因: $adjustment_reason)"
    fi
    
    echo "$CURRENT_MONITOR_INTERVAL"
}

# 记录频率调整日志
log_frequency_adjustment() {
    local old_interval="$1"
    local new_interval="$2"
    local system_load="$3"
    local reason="$4"
    local timestamp=$(get_unified_timestamp)
    
    # 创建频率调整日志文件
    if [[ ! -f "$FREQUENCY_ADJUSTMENT_LOG" ]]; then
        echo "timestamp,old_interval,new_interval,system_load,reason" > "$FREQUENCY_ADJUSTMENT_LOG"
    fi
    
    echo "$timestamp,$old_interval,$new_interval,$system_load,$reason" >> "$FREQUENCY_ADJUSTMENT_LOG"
}

# 优雅降级机制
graceful_degradation() {
    local current_load="$1"
    local degradation_level=0
    
    # 根据系统负载确定降级级别
    if (( $(echo "$current_load > 95" | bc -l 2>/dev/null || echo 0) )); then
        degradation_level=3  # 严重降级
    elif (( $(echo "$current_load > 85" | bc -l 2>/dev/null || echo 0) )); then
        degradation_level=2  # 中度降级
    elif (( $(echo "$current_load > 75" | bc -l 2>/dev/null || echo 0) )); then
        degradation_level=1  # 轻度降级
    fi
    
    case $degradation_level in
        3)
            log_warn "🔴 系统负载严重 (${current_load}%) - 启动严重降级模式"
            # 禁用非关键监控功能
            export ENA_MONITOR_ENABLED=false
            export PERFORMANCE_MONITORING_ENABLED=false
            CURRENT_MONITOR_INTERVAL=$MAX_MONITOR_INTERVAL
            log_warn "  - 已禁用ENA监控"
            log_warn "  - 已禁用性能监控"
            log_warn "  - 监控间隔调整为最大值: ${MAX_MONITOR_INTERVAL}s"
            ;;
        2)
            log_warn "🟡 系统负载较高 (${current_load}%) - 启动中度降级模式"
            # 减少监控频率
            CURRENT_MONITOR_INTERVAL=$(echo "scale=0; $MAX_MONITOR_INTERVAL * 0.8" | bc -l 2>/dev/null || echo $MAX_MONITOR_INTERVAL)
            log_warn "  - 监控间隔调整为: ${CURRENT_MONITOR_INTERVAL}s"
            ;;
        1)
            log_info "🟠 系统负载偏高 (${current_load}%) - 启动轻度降级模式"
            # 轻微减少监控频率
            CURRENT_MONITOR_INTERVAL=$(echo "scale=0; $MONITOR_INTERVAL * 1.5" | bc -l 2>/dev/null || echo $MONITOR_INTERVAL)
            log_info "  - 监控间隔调整为: ${CURRENT_MONITOR_INTERVAL}s"
            ;;
        0)
            # 正常模式，恢复默认设置
            if [[ "$ENA_MONITOR_ENABLED" == "false" ]]; then
                export ENA_MONITOR_ENABLED=true
                log_info "🟢 系统负载正常 (${current_load}%) - 恢复ENA监控"
            fi
            if [[ "$PERFORMANCE_MONITORING_ENABLED" == "false" ]]; then
                export PERFORMANCE_MONITORING_ENABLED=true
                log_info "🟢 系统负载正常 (${current_load}%) - 恢复性能监控"
            fi
            ;;
    esac
    
    return $degradation_level
}

# 错误处理和恢复机制配置
readonly ERROR_RECOVERY_ENABLED=${ERROR_RECOVERY_ENABLED:-true}
readonly MAX_CONSECUTIVE_ERRORS=${MAX_CONSECUTIVE_ERRORS:-5}
readonly ERROR_RECOVERY_DELAY=${ERROR_RECOVERY_DELAY:-10}  # 错误恢复延迟10秒
readonly ERROR_LOG="${LOGS_DIR}/monitoring_errors_$(date +%Y%m%d_%H%M%S).log"

# 错误计数器（全局变量）
declare -A ERROR_COUNTERS
declare -A LAST_ERROR_TIME
declare -A RECOVERY_ATTEMPTS

# 错误处理包装器
handle_function_error() {
    local function_name="$1"
    local error_code="$2"
    local error_message="$3"
    local timestamp=$(get_unified_timestamp)
    
    # 增加错误计数
    ERROR_COUNTERS["$function_name"]=$((${ERROR_COUNTERS["$function_name"]:-0} + 1))
    LAST_ERROR_TIME["$function_name"]=$(date +%s)
    
    # 记录错误日志
    log_error_to_file "$function_name" "$error_code" "$error_message" "$timestamp"
    
    # 检查是否需要错误恢复
    if [[ ${ERROR_COUNTERS["$function_name"]} -ge $MAX_CONSECUTIVE_ERRORS ]]; then
        log_error "🔴 函数 $function_name 连续错误 ${ERROR_COUNTERS["$function_name"]} 次，启动错误恢复"
        initiate_error_recovery "$function_name"
    else
        log_warn "⚠️  函数 $function_name 发生错误 (${ERROR_COUNTERS["$function_name"]}/$MAX_CONSECUTIVE_ERRORS): $error_message"
    fi
}

# 记录错误到文件
log_error_to_file() {
    local function_name="$1"
    local error_code="$2"
    local error_message="$3"
    local timestamp="$4"
    
    # 创建错误日志文件
    if [[ ! -f "$ERROR_LOG" ]]; then
        echo "timestamp,function_name,error_code,error_message,consecutive_count" > "$ERROR_LOG"
    fi
    
    echo "$timestamp,$function_name,$error_code,\"$error_message\",${ERROR_COUNTERS["$function_name"]}" >> "$ERROR_LOG"
}

# 启动错误恢复
initiate_error_recovery() {
    local function_name="$1"
    
    RECOVERY_ATTEMPTS["$function_name"]=$((${RECOVERY_ATTEMPTS["$function_name"]:-0} + 1))
    
    log_error "🔧 开始错误恢复: $function_name (第 ${RECOVERY_ATTEMPTS["$function_name"]} 次尝试)"
    
    case "$function_name" in
        "discover_monitoring_processes")
            recover_process_discovery
            ;;
        "calculate_process_resources"*)
            recover_resource_calculation
            ;;
        "collect_monitoring_overhead_data")
            recover_overhead_collection
            ;;
        "assess_system_load")
            recover_system_load_assessment
            ;;
        *)
            generic_error_recovery "$function_name"
            ;;
    esac
    
    # 等待恢复延迟
    log_info "⏳ 错误恢复延迟 ${ERROR_RECOVERY_DELAY}s..."
    sleep "$ERROR_RECOVERY_DELAY"
    
    # 重置错误计数器
    ERROR_COUNTERS["$function_name"]=0
    log_info "✅ 错误恢复完成: $function_name"
}

# 进程发现错误恢复
recover_process_discovery() {
    log_info "🔧 恢复进程发现功能..."
    
    # 检查进程名配置
    if [[ -z "${MONITORING_PROCESS_NAMES[@]}" ]]; then
        log_warn "监控进程名配置为空，使用默认配置"
        MONITORING_PROCESS_NAMES=("iostat" "mpstat" "sar" "vmstat" "unified_monitor")
    fi
    
    # 检查pgrep命令是否可用
    if ! command -v pgrep >/dev/null 2>&1; then
        log_error "pgrep命令不可用，尝试使用ps命令替代"
        # 可以在这里实现ps命令的替代方案
    fi
    
    # 清理可能的僵尸进程
    log_info "清理僵尸进程..."
    pkill -f "defunct" 2>/dev/null || true
}

# 资源计算错误恢复
recover_resource_calculation() {
    log_info "🔧 恢复资源计算功能..."
    
    # 检查ps命令是否可用
    if ! command -v ps >/dev/null 2>&1; then
        log_error "ps命令不可用，这是严重问题"
        return 1
    fi
    
    # 检查bc命令是否可用
    if ! command -v bc >/dev/null 2>&1; then
        log_warn "bc命令不可用，将使用简化的数学计算"
        # 可以实现不依赖bc的计算方法
    fi
    
    # 清理可能的临时文件
    rm -f /tmp/ps_output_* 2>/dev/null || true
}

# 监控开销收集错误恢复
recover_overhead_collection() {
    log_info "🔧 恢复监控开销收集功能..."
    
    # 检查日志目录权限
    if [[ ! -w "$LOGS_DIR" ]]; then
        log_error "日志目录不可写: $LOGS_DIR"
        mkdir -p "$LOGS_DIR" 2>/dev/null || true
        chmod 755 "$LOGS_DIR" 2>/dev/null || true
    fi
    
    # 检查监控开销日志文件
    if [[ -f "$MONITORING_OVERHEAD_LOG" ]] && [[ ! -w "$MONITORING_OVERHEAD_LOG" ]]; then
        log_warn "监控开销日志文件不可写，尝试修复权限"
        chmod 644 "$MONITORING_OVERHEAD_LOG" 2>/dev/null || true
    fi
    
    # 重新初始化相关组件
    log_info "重新初始化监控开销收集组件..."
}

# 系统负载评估错误恢复
recover_system_load_assessment() {
    log_info "🔧 恢复系统负载评估功能..."
    
    # 检查系统监控命令可用性
    local available_commands=()
    
    if command -v mpstat >/dev/null 2>&1; then
        available_commands+=("mpstat")
    fi
    
    if command -v top >/dev/null 2>&1; then
        available_commands+=("top")
    fi
    
    if command -v free >/dev/null 2>&1; then
        available_commands+=("free")
    fi
    
    if command -v vm_stat >/dev/null 2>&1; then
        available_commands+=("vm_stat")
    fi
    
    if [[ ${#available_commands[@]} -eq 0 ]]; then
        log_error "没有可用的系统监控命令，系统负载评估将使用默认值"
        return 1
    else
        log_info "可用的系统监控命令: ${available_commands[*]}"
    fi
}

# 通用错误恢复
generic_error_recovery() {
    local function_name="$1"
    
    log_info "🔧 执行通用错误恢复: $function_name"
    
    # 清理临时文件
    find /tmp -name "*monitoring*" -mtime +1 -delete 2>/dev/null || true
    
    # 检查系统资源
    local available_memory=$(free -m 2>/dev/null | awk '/^Mem:/ {print $7}' || echo "unknown")
    local disk_space=$(df "$LOGS_DIR" 2>/dev/null | awk 'NR==2 {print $4}' || echo "unknown")
    
    log_info "系统状态检查: 可用内存=${available_memory}MB, 磁盘空间=${disk_space}KB"
    
    # 如果磁盘空间不足，清理旧日志
    if [[ "$disk_space" != "unknown" ]] && [[ $disk_space -lt 1048576 ]]; then  # 小于1GB
        log_warn "磁盘空间不足，清理旧日志文件..."
        find "$LOGS_DIR" -name "*.log" -mtime +7 -delete 2>/dev/null || true
        find "$LOGS_DIR" -name "*.csv" -mtime +3 -delete 2>/dev/null || true
    fi
}

# 错误恢复建议系统
generate_error_recovery_suggestions() {
    local function_name="$1"
    local error_count="${ERROR_COUNTERS["$function_name"]:-0}"
    local recovery_count="${RECOVERY_ATTEMPTS["$function_name"]:-0}"
    
    log_info "📋 错误恢复建议 - $function_name:"
    log_info "  错误次数: $error_count"
    log_info "  恢复尝试: $recovery_count"
    
    if [[ $recovery_count -gt 3 ]]; then
        log_warn "🔴 多次恢复失败，建议采取以下措施:"
        log_warn "  1. 检查系统资源是否充足"
        log_warn "  2. 验证相关命令和工具是否正常"
        log_warn "  3. 考虑重启监控系统"
        log_warn "  4. 联系系统管理员进行深入诊断"
    elif [[ $error_count -gt 10 ]]; then
        log_warn "🟡 频繁错误，建议:"
        log_warn "  1. 检查配置参数是否合理"
        log_warn "  2. 调整监控频率"
        log_warn "  3. 查看详细错误日志: $ERROR_LOG"
    else
        log_info "🟢 错误情况在可控范围内"
        log_info "  建议: 继续监控，定期检查错误日志"
    fi
}

# 安全函数执行包装器
safe_execute() {
    local function_name="$1"
    shift
    local function_args=("$@")
    
    # 检查函数是否存在
    if ! declare -f "$function_name" >/dev/null 2>&1; then
        handle_function_error "$function_name" "FUNCTION_NOT_FOUND" "函数不存在"
        return 1
    fi
    
    # 执行函数并捕获错误
    local result
    local error_code=0
    
    if result=$("$function_name" "${function_args[@]}" 2>&1); then
        # 成功执行，重置错误计数器
        if [[ ${ERROR_COUNTERS["$function_name"]:-0} -gt 0 ]]; then
            log_info "✅ 函数 $function_name 恢复正常"
            ERROR_COUNTERS["$function_name"]=0
        fi
        echo "$result"
        return 0
    else
        error_code=$?
        handle_function_error "$function_name" "$error_code" "$result"
        return $error_code
    fi
}

# 监控系统健康检查
monitoring_system_health_check() {
    log_info "🏥 执行监控系统健康检查..."
    
    local health_issues=()
    
    # 检查关键命令可用性
    local critical_commands=("ps" "date" "sleep")
    for cmd in "${critical_commands[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            health_issues+=("关键命令不可用: $cmd")
        fi
    done
    
    # 检查日志目录
    if [[ ! -d "$LOGS_DIR" ]]; then
        health_issues+=("日志目录不存在: $LOGS_DIR")
    elif [[ ! -w "$LOGS_DIR" ]]; then
        health_issues+=("日志目录不可写: $LOGS_DIR")
    fi
    
    # 检查磁盘空间
    local disk_usage=$(df "$LOGS_DIR" 2>/dev/null | awk 'NR==2 {print $5}' | sed 's/%//' || echo "100")
    if [[ $disk_usage -gt 90 ]]; then
        health_issues+=("磁盘空间不足: ${disk_usage}%")
    fi
    
    # 检查内存使用
    local memory_usage=$(free 2>/dev/null | awk '/^Mem:/ {printf "%.0f", $3/$2 * 100}' || echo "0")
    if [[ $memory_usage -gt 90 ]]; then
        health_issues+=("内存使用率过高: ${memory_usage}%")
    fi
    
    # 检查错误日志
    if [[ -f "$ERROR_LOG" ]]; then
        local recent_errors=$(tail -100 "$ERROR_LOG" 2>/dev/null | wc -l)
        if [[ $recent_errors -gt 50 ]]; then
            health_issues+=("最近错误过多: $recent_errors 条")
        fi
    fi
    
    # 报告健康状态
    if [[ ${#health_issues[@]} -eq 0 ]]; then
        log_info "✅ 监控系统健康状态良好"
        return 0
    else
        log_warn "⚠️  发现 ${#health_issues[@]} 个健康问题:"
        for issue in "${health_issues[@]}"; do
            log_warn "  - $issue"
        done
        
        # 生成修复建议
        generate_health_fix_suggestions "${health_issues[@]}"
        return 1
    fi
}

# 生成健康修复建议
generate_health_fix_suggestions() {
    local issues=("$@")
    
    log_info "🔧 健康修复建议:"
    
    for issue in "${issues[@]}"; do
        case "$issue" in
            *"关键命令不可用"*)
                log_info "  - 安装缺失的系统工具包"
                ;;
            *"日志目录不存在"*)
                log_info "  - 创建日志目录: mkdir -p $LOGS_DIR"
                ;;
            *"日志目录不可写"*)
                log_info "  - 修复目录权限: chmod 755 $LOGS_DIR"
                ;;
            *"磁盘空间不足"*)
                log_info "  - 清理旧日志文件或扩展磁盘空间"
                ;;
            *"内存使用率过高"*)
                log_info "  - 检查内存泄漏

# 获取当前进程资源使用（用于性能监控）
get_current_process_resources() {
    local pid=${1:-$$}  # 默认使用当前进程PID
    
    # 获取CPU和内存使用率
    local process_info=$(ps -p "$pid" -o %cpu,%mem,rss --no-headers 2>/dev/null || echo "0.0 0.0 0")
    local cpu_percent=$(echo "$process_info" | awk '{print $1}')
    local memory_percent=$(echo "$process_info" | awk '{print $2}')
    local memory_kb=$(echo "$process_info" | awk '{print $3}')
    local memory_mb=$(echo "scale=2; $memory_kb / 1024" | bc -l 2>/dev/null || echo "0")
    
    echo "$cpu_percent,$memory_mb"
}

# 监控开销数据收集主函数（增强版 - 带性能监控）
collect_monitoring_overhead_data() {
    local start_time=$(date +%s%3N 2>/dev/null || date +%s)
    local timestamp=$(get_unified_timestamp)
    
    # 收集监控进程资源使用
    local monitoring_pids=$(discover_monitoring_processes)
    local monitoring_resources=$(calculate_process_resources "$monitoring_pids" "监控")
    
    local monitoring_cpu=$(echo "$monitoring_resources" | cut -d',' -f1)
    local monitoring_memory_percent=$(echo "$monitoring_resources" | cut -d',' -f2)
    local monitoring_memory_mb=$(echo "$monitoring_resources" | cut -d',' -f3)
    local monitoring_process_count=$(echo "$monitoring_resources" | cut -d',' -f4)
    
    # 收集区块链节点资源使用
    local blockchain_resources=$(get_blockchain_node_resources)
    
    local blockchain_cpu=$(echo "$blockchain_resources" | cut -d',' -f1)
    local blockchain_memory_percent=$(echo "$blockchain_resources" | cut -d',' -f2)
    local blockchain_memory_mb=$(echo "$blockchain_resources" | cut -d',' -f3)
    local blockchain_process_count=$(echo "$blockchain_resources" | cut -d',' -f4)
    
    # 收集系统静态资源
    local system_static=$(get_system_static_resources)
    local system_cpu_cores=$(echo "$system_static" | cut -d',' -f1)
    local system_memory_gb=$(echo "$system_static" | cut -d',' -f2)
    local system_disk_gb=$(echo "$system_static" | cut -d',' -f3)
    
    # 收集系统动态资源
    local system_dynamic=$(get_system_dynamic_resources)
    local system_cpu_usage=$(echo "$system_dynamic" | cut -d',' -f1)
    local system_memory_usage=$(echo "$system_dynamic" | cut -d',' -f2)
    local system_disk_usage=$(echo "$system_dynamic" | cut -d',' -f3)
    
    # 数据验证和格式化
    monitoring_cpu=$(printf "%.2f" "$monitoring_cpu" 2>/dev/null || echo "0.00")
    monitoring_memory_percent=$(printf "%.2f" "$monitoring_memory_percent" 2>/dev/null || echo "0.00")
    monitoring_memory_mb=$(printf "%.2f" "$monitoring_memory_mb" 2>/dev/null || echo "0.00")
    monitoring_process_count=$(printf "%.0f" "$monitoring_process_count" 2>/dev/null || echo "0")
    
    blockchain_cpu=$(printf "%.2f" "$blockchain_cpu" 2>/dev/null || echo "0.00")
    blockchain_memory_percent=$(printf "%.2f" "$blockchain_memory_percent" 2>/dev/null || echo "0.00")
    blockchain_memory_mb=$(printf "%.2f" "$blockchain_memory_mb" 2>/dev/null || echo "0.00")
    blockchain_process_count=$(printf "%.0f" "$blockchain_process_count" 2>/dev/null || echo "0")
    
    system_cpu_cores=$(printf "%.0f" "$system_cpu_cores" 2>/dev/null || echo "0")
    system_memory_gb=$(printf "%.2f" "$system_memory_gb" 2>/dev/null || echo "0.00")
    system_disk_gb=$(printf "%.2f" "$system_disk_gb" 2>/dev/null || echo "0.00")
    system_cpu_usage=$(printf "%.2f" "$system_cpu_usage" 2>/dev/null || echo "0.00")
    system_memory_usage=$(printf "%.2f" "$system_memory_usage" 2>/dev/null || echo "0.00")
    system_disk_usage=$(printf "%.0f" "$system_disk_usage" 2>/dev/null || echo "0")
    
    log_debug "监控开销数据收集完成: 监控进程=${monitoring_process_count}, 区块链进程=${blockchain_process_count}, 系统CPU=${system_cpu_cores}核"
    
    # 性能监控 - 测量执行时间和资源使用
    local end_time=$(date +%s%3N 2>/dev/null || date +%s)
    local current_resources=$(get_current_process_resources)
    local current_cpu=$(echo "$current_resources" | cut -d',' -f1)
    local current_memory=$(echo "$current_resources" | cut -d',' -f2)
    
    # 调用性能监控
    monitor_performance_impact "collect_monitoring_overhead_data" "$start_time" "$end_time" "$current_cpu" "$current_memory"
    
    # 生成完整的数据行
    echo "$timestamp,$monitoring_cpu,$monitoring_memory_percent,$monitoring_memory_mb,$monitoring_process_count,$blockchain_cpu,$blockchain_memory_percent,$blockchain_memory_mb,$blockchain_process_count,$system_cpu_cores,$system_memory_gb,$system_disk_gb,$system_cpu_usage,$system_memory_usage,$system_disk_usage"
}

# 写入监控开销日志
write_monitoring_overhead_log() {
    # 检查是否需要创建日志文件和写入表头
    if [[ ! -f "$MONITORING_OVERHEAD_LOG" ]] || [[ ! -s "$MONITORING_OVERHEAD_LOG" ]]; then
        echo "$OVERHEAD_CSV_HEADER" > "$MONITORING_OVERHEAD_LOG"
        log_debug "创建监控开销日志文件: $MONITORING_OVERHEAD_LOG"
    fi
    
    # 收集监控开销数据（使用增强的错误处理）
    local overhead_data_line
    if [[ "$ERROR_RECOVERY_ENABLED" == "true" ]]; then
        overhead_data_line=$(enhanced_collect_monitoring_overhead_data)
    else
        overhead_data_line=$(collect_monitoring_overhead_data)
    fi
    
    # 写入数据行
    if [[ -n "$overhead_data_line" ]]; then
        echo "$overhead_data_line" >> "$MONITORING_OVERHEAD_LOG"
        log_debug "写入监控开销数据: $(echo "$overhead_data_line" | cut -d',' -f1-5)..."
    else
        log_debug "监控开销数据收集失败，跳过写入"
    fi
}

# 配置验证和健康检查
validate_monitoring_overhead_config() {
    local validation_errors=()
    local validation_warnings=()
    
    # 检查必要的配置变量
    if [[ -z "${MONITORING_PROCESS_NAMES[@]}" ]]; then
        validation_errors+=("MONITORING_PROCESS_NAMES数组未定义或为空")
    fi
    
    if [[ -z "${BLOCKCHAIN_PROCESS_NAMES[@]}" ]]; then
        validation_errors+=("BLOCKCHAIN_PROCESS_NAMES数组未定义或为空")
    fi
    
    if [[ -z "$MONITORING_OVERHEAD_LOG" ]]; then
        validation_errors+=("MONITORING_OVERHEAD_LOG变量未定义")
    fi
    
    if [[ -z "$OVERHEAD_CSV_HEADER" ]]; then
        validation_errors+=("OVERHEAD_CSV_HEADER变量未定义")
    fi
    
    # 检查EBS基准值配置
    if [[ -z "$DATA_BASELINE_IOPS" || -z "$DATA_BASELINE_THROUGHPUT" ]]; then
        validation_warnings+=("DATA设备基准值未完全配置")
    fi
    
    if [[ -n "${ACCOUNTS_DEVICE:-}" && -n "${ACCOUNTS_VOL_TYPE:-}" ]]; then
        if [[ -z "$ACCOUNTS_BASELINE_IOPS" || -z "$ACCOUNTS_BASELINE_THROUGHPUT" ]]; then
            validation_warnings+=("ACCOUNTS设备已配置但基准值缺失")
        fi
    fi
    
    # 检查必要命令的可用性
    local required_commands=("pgrep" "ps" "bc" "cut" "grep" "awk")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            validation_errors+=("必要命令不可用: $cmd")
        fi
    done
    
    # 检查日志目录的可写性
    local log_dir=$(dirname "$MONITORING_OVERHEAD_LOG")
    if [[ ! -d "$log_dir" ]]; then
        validation_warnings+=("监控开销日志目录不存在: $log_dir")
    elif [[ ! -w "$log_dir" ]]; then
        validation_errors+=("监控开销日志目录不可写: $log_dir")
    fi
    
    # 输出验证结果
    if [[ ${#validation_errors[@]} -gt 0 ]]; then
        echo "❌ 配置验证失败:" >&2
        for error in "${validation_errors[@]}"; do
            echo "   - $error" >&2
        done
        return 1
    fi
    
    if [[ ${#validation_warnings[@]} -gt 0 ]]; then
        echo "⚠️  配置验证警告:" >&2
        for warning in "${validation_warnings[@]}"; do
            echo "   - $warning" >&2
        done
    fi
    
    log_debug "监控开销配置验证通过"
    return 0
}

# 监控开销系统健康检查
monitoring_overhead_health_check() {
    local health_issues=()
    
    # 检查进程发现功能
    local monitoring_pids=$(discover_monitoring_processes 2>/dev/null)
    if [[ -z "$monitoring_pids" ]]; then
        health_issues+=("未发现监控进程")
    else
        local pid_count=$(echo "$monitoring_pids" | wc -w)
        log_debug "健康检查: 发现${pid_count}个监控进程"
    fi
    
    # 检查区块链进程发现功能
    local blockchain_pids=$(discover_blockchain_processes 2>/dev/null)
    if [[ -z "$blockchain_pids" ]]; then
        log_debug "健康检查: 未发现区块链进程 可能正常"
    else
        local pid_count=$(echo "$blockchain_pids" | wc -w)
        log_debug "健康检查: 发现${pid_count}个区块链进程"
    fi
    
    # 检查资源计算功能
    local test_resources=$(calculate_process_resources "$$" "测试" 2>/dev/null)
    if [[ "$test_resources" == "0,0,0,0" ]]; then
        health_issues+=("进程资源计算功能异常")
    fi
    
    # 检查系统资源收集功能
    local static_resources=$(get_system_static_resources 2>/dev/null)
    if [[ -z "$static_resources" ]]; then
        health_issues+=("系统静态资源收集功能异常")
    fi
    
    local dynamic_resources=$(get_system_dynamic_resources 2>/dev/null)
    if [[ -z "$dynamic_resources" ]]; then
        health_issues+=("系统动态资源收集功能异常")
    fi
    
    # 检查日志文件状态
    if [[ -f "$MONITORING_OVERHEAD_LOG" ]]; then
        local log_size=$(wc -l < "$MONITORING_OVERHEAD_LOG" 2>/dev/null || echo 0)
        log_debug "健康检查: 监控开销日志包含${log_size}行数据"
        
        if [[ $log_size -gt 10000 ]]; then
            health_issues+=("监控开销日志文件过大 ${log_size}行")
        fi
    fi
    
    # 输出健康检查结果
    if [[ ${#health_issues[@]} -gt 0 ]]; then
        echo "⚠️  健康检查发现问题:" >&2
        for issue in "${health_issues[@]}"; do
            echo "   - $issue" >&2
        done
        return 1
    fi
    
    log_debug "监控开销系统健康检查通过"
    return 0
}

# 兼容性函数 - 保持原有的基于MONITOR_PIDS的逻辑作为备用
get_monitoring_overhead_legacy() {
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
    
    # 如果CSV文件不存在或为空，先写入头部
    if [[ ! -f "$UNIFIED_LOG" ]] || [[ ! -s "$UNIFIED_LOG" ]]; then
        local csv_header=$(generate_csv_header)
        echo "$csv_header" > "$UNIFIED_LOG"
    fi
    
    # 写入CSV文件
    echo "$data_line" >> "$UNIFIED_LOG"
    
    # 写入独立的监控开销日志
    write_monitoring_overhead_log
    
    # 定期性能分析 (每100次记录分析一次)
    local sample_count_file="${MEMORY_SHARE_DIR}/sample_count"
    local current_count=1
    
    if [[ -f "$sample_count_file" ]]; then
        current_count=$(cat "$sample_count_file" 2>/dev/null || echo 1)
        current_count=$((current_count + 1))
    fi
    
    echo "$current_count" > "$sample_count_file"
    
    # 每100次采样进行一次性能分析
    if (( current_count % 100 == 0 )); then
        log_info "🔍 执行定期性能分析 第 $current_count 次采样"
        auto_performance_optimization_advisor
    fi
    
    # 每1000次采样生成一次完整报告
    if (( current_count % 1000 == 0 )); then
        log_info "📊 生成性能影响报告 第 $current_count 次采样"
        generate_performance_impact_report
    fi
    
    # 生成JSON文件
    generate_json_metrics "$timestamp" "$cpu_data" "$memory_data" "$device_data" "$network_data" "$ena_data" "$overhead_data"
}

# 启动统一监控 - 修复：支持跟随QPS测试模式
start_unified_monitoring() {
    local duration="$1"
    local interval=${2:-$MONITOR_INTERVAL}
    local follow_qps_test="${3:-false}"
    
    # 初始化错误处理系统
    initialize_error_handling_system
    
    START_TIME=$(get_unified_timestamp)
    
    echo "🚀 启动统一性能监控..."
    echo "  开始时间: $START_TIME"
    echo "  监控间隔: ${interval}秒"
    
    if [[ "$follow_qps_test" == "true" ]]; then
        echo "  模式: 跟随QPS测试 无时间限制"
        echo "  控制文件: ${MEMORY_SHARE_DIR}/qps_monitor_control.flag"
    else
        echo "  监控时长: ${duration}秒"
    fi
    
    echo "  数据文件: $UNIFIED_LOG"
    echo ""
    
    # 显示配置状态
    log_info "DATA设备: $LEDGER_DEVICE"
    
    if [[ -n "$ACCOUNTS_DEVICE" && -n "$ACCOUNTS_VOL_TYPE" ]]; then
        log_info "ACCOUNTS设备: $ACCOUNTS_DEVICE 卷类型: $ACCOUNTS_VOL_TYPE"
    else
        echo "ℹ️  ACCOUNTS设备未配置"
    fi
    
    if [[ -n "$NETWORK_INTERFACE" ]]; then
        log_info "网络接口: $NETWORK_INTERFACE"
    fi
    
    # 显示ENA监控状态
    if [[ "$ENA_MONITOR_ENABLED" == "true" ]]; then
        log_info "ENA监控: 已启用 AWS环境"
    else
        echo "ℹ️  ENA监控: 已禁用 非AWS环境"
    fi
    
    # 创建 CSV 表头
    local csv_header=$(generate_csv_header)
    echo "$csv_header" > "$UNIFIED_LOG"
    
    # 创建latest文件软链接，供瓶颈检测使用
    local latest_csv="${LOGS_DIR}/performance_latest.csv"
    ln -sf "$(basename "$UNIFIED_LOG")" "$latest_csv"
    
    log_info "CSV表头已创建 $(echo "$csv_header" | tr ',' '\n' | wc -l) 个字段"
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
            
            # 自适应频率调整
            local current_system_load=$(assess_system_load)
            graceful_degradation "$current_system_load"
            local adjusted_interval=$(adaptive_frequency_adjustment)
            
            log_performance_data
            sample_count=$((sample_count + 1))
            
            # 进度报告
            if (( sample_count % 12 == 0 )); then
                local current_time=$(date +%s)
                local elapsed=$((current_time - start_time))
                echo "📈 已收集 $sample_count 个样本，已运行 ${elapsed}s 跟随QPS测试中"
                echo "   当前监控间隔: ${adjusted_interval}s (系统负载: ${current_system_load}%)"
            fi
            
            sleep "$adjusted_interval"
        done
    else
        # 固定时长模式
        local end_time=$((start_time + duration))
        
        while [[ $(date +%s) -lt $end_time ]]; do
            # 自适应频率调整
            local current_system_load=$(assess_system_load)
            graceful_degradation "$current_system_load"
            local adjusted_interval=$(adaptive_frequency_adjustment)
            
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
                echo "   当前监控间隔: ${adjusted_interval}s (系统负载: ${current_system_load}%)"
            fi
            
            sleep "$adjusted_interval"
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
    
    # 生成错误恢复报告
    if [[ "$ERROR_RECOVERY_ENABLED" == "true" ]]; then
        generate_error_recovery_report
    fi
    
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
# 生成健康修复建议
generate_health_fix_suggestions() {
    local issues=("$@")
    
    log_info "🔧 健康修复建议:"
    
    for issue in "${issues[@]}"; do
        case "$issue" in
            *"关键命令不可用"*)
                log_info "  - 安装缺失的系统工具包"
                ;;
            *"日志目录不存在"*)
                log_info "  - 创建日志目录: mkdir -p $LOGS_DIR"
                ;;
            *"日志目录不可写"*)
                log_info "  - 修复目录权限: chmod 755 $LOGS_DIR"
                ;;
            *"磁盘空间不足"*)
                log_info "  - 清理旧日志文件或扩展磁盘空间"
                ;;
            *"内存使用率过高"*)
                log_info "  - 检查内存泄漏或重启相关进程"
                ;;
            *"最近错误过多"*)
                log_info "  - 分析错误日志: $ERROR_LOG"
                log_info "  - 考虑调整监控配置参数"
                ;;
        esac
    done
}

# 增强的函数包装器 - 为关键函数添加错误处理
enhanced_discover_monitoring_processes() {
    if [[ "$ERROR_RECOVERY_ENABLED" == "true" ]]; then
        safe_execute "discover_monitoring_processes" "$@"
    else
        discover_monitoring_processes "$@"
    fi
}

enhanced_calculate_process_resources() {
    if [[ "$ERROR_RECOVERY_ENABLED" == "true" ]]; then
        safe_execute "calculate_process_resources" "$@"
    else
        calculate_process_resources "$@"
    fi
}

enhanced_collect_monitoring_overhead_data() {
    if [[ "$ERROR_RECOVERY_ENABLED" == "true" ]]; then
        safe_execute "collect_monitoring_overhead_data" "$@"
    else
        collect_monitoring_overhead_data "$@"
    fi
}

enhanced_assess_system_load() {
    if [[ "$ERROR_RECOVERY_ENABLED" == "true" ]]; then
        safe_execute "assess_system_load" "$@"
    else
        assess_system_load "$@"
    fi
}

# 错误恢复状态报告
generate_error_recovery_report() {
    local report_file="${LOGS_DIR}/error_recovery_report_$(date +%Y%m%d_%H%M%S).txt"
    
    log_info "生成错误恢复报告: $report_file"
    
    {
        echo "# 监控系统错误恢复报告"
        echo "生成时间: $(date)"
        echo "错误日志: $ERROR_LOG"
        echo ""
        
        echo "## 错误统计"
        if [[ ${#ERROR_COUNTERS[@]} -gt 0 ]]; then
            for func_name in "${!ERROR_COUNTERS[@]}"; do
                echo "- $func_name: ${ERROR_COUNTERS[$func_name]} 次错误"
            done
        else
            echo "- 无错误记录"
        fi
        
        echo ""
        echo "## 恢复尝试统计"
        if [[ ${#RECOVERY_ATTEMPTS[@]} -gt 0 ]]; then
            for func_name in "${!RECOVERY_ATTEMPTS[@]}"; do
                echo "- $func_name: ${RECOVERY_ATTEMPTS[$func_name]} 次恢复尝试"
            done
        else
            echo "- 无恢复尝试记录"
        fi
        
        echo ""
        echo "## 系统健康状态"
        monitoring_system_health_check >/dev/null 2>&1
        local health_status=$?
        if [[ $health_status -eq 0 ]]; then
            echo "- 状态: 健康"
        else
            echo "- 状态: 存在问题"
            echo "- 建议: 查看上述健康检查输出"
        fi
        
        echo ""
        echo "## 配置参数"
        echo "- ERROR_RECOVERY_ENABLED: $ERROR_RECOVERY_ENABLED"
        echo "- MAX_CONSECUTIVE_ERRORS: $MAX_CONSECUTIVE_ERRORS"
        echo "- ERROR_RECOVERY_DELAY: ${ERROR_RECOVERY_DELAY}s"
        echo "- ADAPTIVE_FREQUENCY_ENABLED: $ADAPTIVE_FREQUENCY_ENABLED"
        echo "- PERFORMANCE_MONITORING_ENABLED: $PERFORMANCE_MONITORING_ENABLED"
        
    } > "$report_file"
    
    log_info "错误恢复报告已生成: $report_file"
}

# 监控系统完整性检查
monitoring_system_integrity_check() {
    log_info "🔍 执行监控系统完整性检查..."
    
    local integrity_issues=()
    
    # 检查关键文件
    local critical_files=("$UNIFIED_LOG" "$MONITORING_OVERHEAD_LOG")
    for file in "${critical_files[@]}"; do
        if [[ -n "$file" ]] && [[ -f "$file" ]]; then
            if [[ ! -r "$file" ]]; then
                integrity_issues+=("文件不可读: $file")
            fi
            if [[ ! -w "$file" ]]; then
                integrity_issues+=("文件不可写: $file")
            fi
        fi
    done
    
    # 检查配置完整性
    local required_vars=("LOGS_DIR" "MONITOR_INTERVAL" "LEDGER_DEVICE")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            integrity_issues+=("必需配置变量未设置: $var")
        fi
    done
    
    # 检查进程配置
    if [[ -z "${MONITORING_PROCESS_NAMES[@]}" ]]; then
        integrity_issues+=("监控进程名配置为空")
    fi
    
    # 检查权限
    if [[ ! -w "$LOGS_DIR" ]]; then
        integrity_issues+=("日志目录权限不足: $LOGS_DIR")
    fi
    
    # 报告完整性状态
    if [[ ${#integrity_issues[@]} -eq 0 ]]; then
        log_info "✅ 监控系统完整性检查通过"
        return 0
    else
        log_warn "⚠️  发现 ${#integrity_issues[@]} 个完整性问题:"
        for issue in "${integrity_issues[@]}"; do
            log_warn "  - $issue"
        done
        return 1
    fi
}

# 自动修复功能
auto_fix_common_issues() {
    log_info "🔧 尝试自动修复常见问题..."
    
    local fixes_applied=0
    
    # 修复日志目录权限
    if [[ ! -w "$LOGS_DIR" ]]; then
        log_info "修复日志目录权限..."
        if mkdir -p "$LOGS_DIR" 2>/dev/null && chmod 755 "$LOGS_DIR" 2>/dev/null; then
            log_info "✅ 日志目录权限已修复"
            fixes_applied=$((fixes_applied + 1))
        else
            log_warn "❌ 无法修复日志目录权限"
        fi
    fi
    
    # 修复日志文件权限
    for log_file in "$UNIFIED_LOG" "$MONITORING_OVERHEAD_LOG" "$PERFORMANCE_LOG" "$ERROR_LOG"; do
        if [[ -n "$log_file" ]] && [[ -f "$log_file" ]] && [[ ! -w "$log_file" ]]; then
            log_info "修复日志文件权限: $log_file"
            if chmod 644 "$log_file" 2>/dev/null; then
                log_info "✅ 日志文件权限已修复: $log_file"
                fixes_applied=$((fixes_applied + 1))
            else
                log_warn "❌ 无法修复日志文件权限: $log_file"
            fi
        fi
    done
    
    # 清理磁盘空间
    local disk_usage=$(df "$LOGS_DIR" 2>/dev/null | awk 'NR==2 {print $5}' | sed 's/%//' || echo "0")
    if [[ $disk_usage -gt 90 ]]; then
        log_info "清理磁盘空间..."
        local cleaned_files=0
        
        # 清理7天前的日志文件
        if find "$LOGS_DIR" -name "*.log" -mtime +7 -delete 2>/dev/null; then
            cleaned_files=$((cleaned_files + 1))
        fi
        
        # 清理3天前的CSV文件
        if find "$LOGS_DIR" -name "*.csv" -mtime +3 -delete 2>/dev/null; then
            cleaned_files=$((cleaned_files + 1))
        fi
        
        if [[ $cleaned_files -gt 0 ]]; then
            log_info "✅ 已清理旧日志文件"
            fixes_applied=$((fixes_applied + 1))
        fi
    fi
    
    log_info "自动修复完成，应用了 $fixes_applied 个修复"
    return $fixes_applied
}

# 错误处理系统初始化
initialize_error_handling_system() {
    if [[ "$ERROR_RECOVERY_ENABLED" != "true" ]]; then
        log_info "错误恢复系统已禁用"
        return 0
    fi
    
    log_info "🚀 初始化错误处理系统..."
    
    # 创建错误日志文件
    if [[ ! -f "$ERROR_LOG" ]]; then
        echo "timestamp,function_name,error_code,error_message,consecutive_count" > "$ERROR_LOG"
        log_info "错误日志文件已创建: $ERROR_LOG"
    fi
    
    # 执行系统健康检查
    monitoring_system_health_check
    
    # 执行完整性检查
    monitoring_system_integrity_check
    
    # 尝试自动修复
    auto_fix_common_issues
    
    log_info "✅ 错误处理系统初始化完成"
}