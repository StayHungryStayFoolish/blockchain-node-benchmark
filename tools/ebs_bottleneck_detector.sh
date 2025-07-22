#!/bin/bash
# EBS瓶颈检测器
# 高频监控EBS性能，检测IOPS和Throughput瓶颈

# 引入依赖
source "$(dirname "${BASH_SOURCE[0]}")/../config/config.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh"

# 初始化统一日志管理器
init_logger "ebs_bottleneck_detector" $LOG_LEVEL "${LOGS_DIR}/ebs_bottleneck_detector.log"

source "$(dirname "${BASH_SOURCE[0]}")/../utils/ebs_converter.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../monitoring/ec2_info_collector.sh"

# 瓶颈检测配置
readonly HIGH_FREQ_INTERVAL=1        # 高频监控间隔(秒)
readonly BOTTLENECK_THRESHOLD=0.85   # 瓶颈阈值(85%)
readonly PEAK_DETECTION_WINDOW=10    # 峰值检测窗口(秒)
readonly BOTTLENECK_LOG_FILE="${LOGS_DIR}/ebs_bottleneck_$(date +%Y%m%d_%H%M%S).csv"

# 全局变量
declare -A DEVICE_LIMITS
declare -A BOTTLENECK_COUNTERS
declare -A PEAK_VALUES

# 初始化EBS限制配置
init_ebs_limits() {
    echo "🔧 Initializing EBS limits configuration..."
    
    # DATA卷限制（必须存在）
    if [[ -n "$DATA_VOL_MAX_IOPS" ]]; then
        case "$DATA_VOL_TYPE" in
            "gp3")
                DEVICE_LIMITS["${LEDGER_DEVICE}_max_iops"]="$DATA_VOL_MAX_IOPS"
                DEVICE_LIMITS["${LEDGER_DEVICE}_max_throughput"]="${DATA_VOL_MAX_THROUGHPUT:-1000}"
                ;;
            "io2")
                DEVICE_LIMITS["${LEDGER_DEVICE}_max_iops"]="$DATA_VOL_MAX_IOPS"
                local auto_throughput=$(calculate_io2_throughput "$DATA_VOL_MAX_IOPS")
                DEVICE_LIMITS["${LEDGER_DEVICE}_max_throughput"]="$auto_throughput"
                ;;
            "instance-store")
                DEVICE_LIMITS["${LEDGER_DEVICE}_max_iops"]="$DATA_VOL_MAX_IOPS"
                DEVICE_LIMITS["${LEDGER_DEVICE}_max_throughput"]="$DATA_VOL_MAX_THROUGHPUT"
                ;;
        esac
        echo "  DATA Volume (${LEDGER_DEVICE}): ${DEVICE_LIMITS["${LEDGER_DEVICE}_max_iops"]} IOPS, ${DEVICE_LIMITS["${LEDGER_DEVICE}_max_throughput"]} MiB/s"
    fi
    
    # ACCOUNTS卷限制
    if [[ -n "$ACCOUNTS_VOL_TYPE" && -n "$ACCOUNTS_VOL_MAX_IOPS" && -n "$ACCOUNTS_DEVICE" ]]; then
        case "$ACCOUNTS_VOL_TYPE" in
            "gp3")
                DEVICE_LIMITS["${ACCOUNTS_DEVICE}_max_iops"]="$ACCOUNTS_VOL_MAX_IOPS"
                DEVICE_LIMITS["${ACCOUNTS_DEVICE}_max_throughput"]="${ACCOUNTS_VOL_MAX_THROUGHPUT:-1000}"
                ;;
            "io2")
                DEVICE_LIMITS["${ACCOUNTS_DEVICE}_max_iops"]="$ACCOUNTS_VOL_MAX_IOPS"
                local auto_throughput=$(calculate_io2_throughput "$ACCOUNTS_VOL_MAX_IOPS")
                DEVICE_LIMITS["${ACCOUNTS_DEVICE}_max_throughput"]="$auto_throughput"
                ;;
            "instance-store")
                DEVICE_LIMITS["${ACCOUNTS_DEVICE}_max_iops"]="$ACCOUNTS_VOL_MAX_IOPS"
                DEVICE_LIMITS["${ACCOUNTS_DEVICE}_max_throughput"]="$ACCOUNTS_VOL_MAX_THROUGHPUT"
                ;;
        esac
        echo "  ACCOUNTS Volume (${ACCOUNTS_DEVICE}): ${DEVICE_LIMITS["${ACCOUNTS_DEVICE}_max_iops"]} IOPS, ${DEVICE_LIMITS["${ACCOUNTS_DEVICE}_max_throughput"]} MiB/s"
    fi
    
    # 初始化计数器
    for device in "$LEDGER_DEVICE" "$ACCOUNTS_DEVICE"; do
        if [[ -n "$device" ]]; then
            BOTTLENECK_COUNTERS["${device}_iops_exceeded"]=0
            BOTTLENECK_COUNTERS["${device}_throughput_exceeded"]=0
            PEAK_VALUES["${device}_max_iops"]=0
            PEAK_VALUES["${device}_max_throughput"]=0
        fi
    done
}

# 高频率iostat数据采集
get_high_freq_iostat() {
    local device=$1
    
    # 使用更短的间隔获取瞬时数据
    local iostat_data=$(timeout 3 iostat -x 1 1 2>/dev/null)
    
    if [[ -z "$iostat_data" ]]; then
        echo "0,0,0,0,0,0,0"
        return
    fi
    
    local device_stats=$(echo "$iostat_data" | awk "/^${device}[[:space:]]/ {print; exit}")
    
    if [[ -z "$device_stats" ]]; then
        echo "0,0,0,0,0,0,0"
        return
    fi
    
    # 提取关键字段
    local r_s=$(echo "$device_stats" | awk '{printf "%.2f", $2}')
    local w_s=$(echo "$device_stats" | awk '{printf "%.2f", $8}')
    local rkb_s=$(echo "$device_stats" | awk '{printf "%.2f", $3}')
    local wkb_s=$(echo "$device_stats" | awk '{printf "%.2f", $9}')
    local r_await=$(echo "$device_stats" | awk '{printf "%.2f", $6}')
    local w_await=$(echo "$device_stats" | awk '{printf "%.2f", $12}')
    local util=$(echo "$device_stats" | awk '{printf "%.2f", $23}')
    
    # 计算总体指标
    local total_iops=$(echo "scale=2; $r_s + $w_s" | bc)
    local total_throughput_kbs=$(echo "scale=2; $rkb_s + $wkb_s" | bc)
    local total_throughput_mibs=$(echo "scale=2; $total_throughput_kbs / 1024" | bc)
    
    # 计算AWS标准IOPS (基于实时数据，消除经验值)
    local avg_io_kib
    if [[ $(echo "$total_iops > 0" | bc 2>/dev/null || echo 0) -eq 1 ]]; then
        avg_io_kib=$(echo "scale=2; $total_throughput_kbs / $total_iops" | bc 2>/dev/null || echo "0")
    else
        avg_io_kib="0"
    fi
    local aws_standard_iops=$(convert_to_aws_standard_iops "$total_iops" "$avg_io_kib")
    
    echo "$total_iops,$aws_standard_iops,$total_throughput_mibs,$r_await,$w_await,$util,$avg_io_kib"
}

# 检测EBS瓶颈
detect_ebs_bottleneck() {
    local device=$1
    local current_iops=$2
    local current_aws_iops=$3
    local current_throughput=$4
    local current_latency=$5
    local timestamp=$6
    
    local bottleneck_detected=false
    local bottleneck_type=""
    local severity=""
    
    # 获取设备限制
    local max_iops=${DEVICE_LIMITS["${device}_max_iops"]}
    local max_throughput=${DEVICE_LIMITS["${device}_max_throughput"]}
    
    if [[ -z "$max_iops" || -z "$max_throughput" ]]; then
        return 0
    fi
    
    # IOPS瓶颈检测
    local iops_utilization=$(echo "scale=4; $current_aws_iops / $max_iops" | bc)
    if (( $(echo "$iops_utilization > $BOTTLENECK_THRESHOLD" | bc -l) )); then
        bottleneck_detected=true
        bottleneck_type="${bottleneck_type}IOPS,"
        BOTTLENECK_COUNTERS["${device}_iops_exceeded"]=$((BOTTLENECK_COUNTERS["${device}_iops_exceeded"] + 1))
        
        if (( $(echo "$iops_utilization > 0.95" | bc -l) )); then
            severity="CRITICAL"
        elif (( $(echo "$iops_utilization > 0.90" | bc -l) )); then
            severity="HIGH"
        else
            severity="MEDIUM"
        fi
    fi
    
    # Throughput瓶颈检测
    local throughput_utilization=$(echo "scale=4; $current_throughput / $max_throughput" | bc)
    if (( $(echo "$throughput_utilization > $BOTTLENECK_THRESHOLD" | bc -l) )); then
        bottleneck_detected=true
        bottleneck_type="${bottleneck_type}THROUGHPUT,"
        BOTTLENECK_COUNTERS["${device}_throughput_exceeded"]=$((BOTTLENECK_COUNTERS["${device}_throughput_exceeded"] + 1))
        
        if (( $(echo "$throughput_utilization > 0.95" | bc -l) )); then
            severity="CRITICAL"
        elif (( $(echo "$throughput_utilization > 0.90" | bc -l) )); then
            severity="HIGH"
        else
            severity="MEDIUM"
        fi
    fi
    
    # 延迟瓶颈检测
    if (( $(echo "$current_latency > 50" | bc -l) )); then
        bottleneck_detected=true
        bottleneck_type="${bottleneck_type}LATENCY,"
        severity="HIGH"
    fi
    
    # 更新峰值
    if (( $(echo "$current_aws_iops > ${PEAK_VALUES["${device}_max_iops"]}" | bc -l) )); then
        PEAK_VALUES["${device}_max_iops"]="$current_aws_iops"
    fi
    
    if (( $(echo "$current_throughput > ${PEAK_VALUES["${device}_max_throughput"]}" | bc -l) )); then
        PEAK_VALUES["${device}_max_throughput"]="$current_throughput"
    fi
    
    # 记录瓶颈事件
    if [[ "$bottleneck_detected" == "true" ]]; then
        local bottleneck_record="$timestamp,$device,$bottleneck_type,$severity,$current_aws_iops,$max_iops,$iops_utilization,$current_throughput,$max_throughput,$throughput_utilization,$current_latency"
        log_info "$bottleneck_record"
        
        # 实时警告
        echo "⚠️  [$(date '+%H:%M:%S')] EBS BOTTLENECK DETECTED: $device - $bottleneck_type (Severity: $severity)"
        echo "   IOPS: $current_aws_iops/$max_iops (${iops_utilization%.*}%), Throughput: $current_throughput/$max_throughput MiB/s (${throughput_utilization%.*}%)"
        
        return 1
    fi
    
    return 0
}

# 启动高频监控 - 修复：支持QPS测试时长同步
start_high_freq_monitoring() {
    local duration="$1"
    local qps_test_mode="${2:-false}"  # 是否为QPS测试模式
    
    # 如果没有指定时长，根据模式决定默认值
    if [[ -z "$duration" ]]; then
        if [[ "$qps_test_mode" == "true" ]]; then
            duration="$QPS_TEST_DURATION"  # 使用QPS测试时长
            echo "🔗 EBS监控与QPS测试同步，时长: ${duration}s"
        else
            duration="$DEFAULT_MONITOR_DURATION"  # 独立运行时使用默认时长
            echo "🔧 EBS独立监控模式，时长: ${duration}s"
        fi
    fi
    
    local output_file="${LOGS_DIR}/ebs_high_freq_$(date +%Y%m%d_%H%M%S).csv"
    
    echo "🚀 Starting high-frequency EBS monitoring..."
    echo "   Duration: ${duration}s"
    echo "   Interval: ${HIGH_FREQ_INTERVAL}s"
    echo "   Output: $output_file"
    echo "   Bottleneck Log: $BOTTLENECK_LOG_FILE"
    echo "   QPS Test Mode: $qps_test_mode"
    echo ""
    
    # 创建CSV表头
    echo "timestamp,device,total_iops,aws_standard_iops,throughput_mibs,r_await,w_await,util,avg_io_kib,iops_utilization,throughput_utilization,bottleneck_detected" > "$output_file"
    echo "timestamp,device,bottleneck_type,severity,current_aws_iops,max_iops,iops_utilization,current_throughput,max_throughput,throughput_utilization,latency" > "$BOTTLENECK_LOG_FILE"
    
    local start_time=$(date +%s)
    local end_time=$((start_time + duration))
    local sample_count=0
    
    while [[ $(date +%s) -lt $end_time ]]; do
        local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        sample_count=$((sample_count + 1))
        
        # 监控每个配置的设备
        for device in "$LEDGER_DEVICE" "$ACCOUNTS_DEVICE"; do
            if [[ -n "$device" && -n "${DEVICE_LIMITS["${device}_max_iops"]}" ]]; then
                # 获取高频数据
                local metrics=$(get_high_freq_iostat "$device")
                IFS=',' read -r total_iops aws_standard_iops throughput_mibs r_await w_await util avg_io_kib <<< "$metrics"
                
                # 计算利用率
                local max_iops=${DEVICE_LIMITS["${device}_max_iops"]}
                local max_throughput=${DEVICE_LIMITS["${device}_max_throughput"]}
                local iops_utilization=$(echo "scale=4; $aws_standard_iops / $max_iops" | bc 2>/dev/null || echo "0")
                local throughput_utilization=$(echo "scale=4; $throughput_mibs / $max_throughput" | bc 2>/dev/null || echo "0")
                
                # 检测瓶颈
                local avg_latency=$(echo "scale=2; ($r_await + $w_await) / 2" | bc)
                detect_ebs_bottleneck "$device" "$total_iops" "$aws_standard_iops" "$throughput_mibs" "$avg_latency" "$timestamp"
                local bottleneck_detected=$?
                
                # 记录数据
                log_info "$timestamp,$device,$total_iops,$aws_standard_iops,$throughput_mibs,$r_await,$w_await,$util,$avg_io_kib,$iops_utilization,$throughput_utilization,$bottleneck_detected"
                
                # 实时显示 (每10秒显示一次)
                if (( sample_count % 10 == 0 )); then
                    printf "📊 [%s] %s: IOPS=%s/%s (%.1f%%), Throughput=%.1f/%.1f MiB/s (%.1f%%), Latency=%.1fms\n" \
                        "$(date '+%H:%M:%S')" "$device" "$aws_standard_iops" "$max_iops" \
                        "$(echo "$iops_utilization * 100" | bc)" "$throughput_mibs" "$max_throughput" \
                        "$(echo "$throughput_utilization * 100" | bc)" "$avg_latency"
                fi
            fi
        done
        
        sleep "$HIGH_FREQ_INTERVAL"
    done
    
    echo ""
    echo "✅ High-frequency monitoring completed"
    echo "📄 Data file: $output_file"
    echo "⚠️  Bottleneck log: $BOTTLENECK_LOG_FILE"
    
    # 生成监控摘要
    generate_monitoring_summary "$output_file"
}

# 生成监控摘要
generate_monitoring_summary() {
    local data_file=$1
    local summary_file="${data_file%.*}_summary.txt"
    
    echo "📊 Generating monitoring summary..."
    
    {
        echo "==============================================="
        echo "EBS High-Frequency Monitoring Summary"
        echo "==============================================="
        echo "Generated: $(date)"
        echo "Data File: $data_file"
        echo "Bottleneck Log: $BOTTLENECK_LOG_FILE"
        echo ""
        
        echo "=== EBS Configuration ==="
        for device in "$LEDGER_DEVICE" "$ACCOUNTS_DEVICE"; do
            if [[ -n "$device" && -n "${DEVICE_LIMITS["${device}_max_iops"]}" ]]; then
                echo "$device:"
                echo "  Max IOPS: ${DEVICE_LIMITS["${device}_max_iops"]}"
                echo "  Max Throughput: ${DEVICE_LIMITS["${device}_max_throughput"]} MiB/s"
                echo "  Peak IOPS Observed: ${PEAK_VALUES["${device}_max_iops"]}"
                echo "  Peak Throughput Observed: ${PEAK_VALUES["${device}_max_throughput"]} MiB/s"
                echo "  IOPS Bottleneck Events: ${BOTTLENECK_COUNTERS["${device}_iops_exceeded"]}"
                echo "  Throughput Bottleneck Events: ${BOTTLENECK_COUNTERS["${device}_throughput_exceeded"]}"
                echo ""
            fi
        done
        
        echo "=== Bottleneck Analysis ==="
        if [[ -f "$BOTTLENECK_LOG_FILE" ]]; then
            local total_bottlenecks=$(tail -n +2 "$BOTTLENECK_LOG_FILE" | wc -l)
            echo "Total Bottleneck Events: $total_bottlenecks"
            
            if [[ $total_bottlenecks -gt 0 ]]; then
                echo ""
                echo "Bottleneck Event Details:"
                echo "------------------------"
                tail -n +2 "$BOTTLENECK_LOG_FILE" | while IFS=',' read -r timestamp device bottleneck_type severity current_aws_iops max_iops iops_util current_throughput max_throughput throughput_util latency; do
                    echo "[$timestamp] $device: $bottleneck_type (Severity: $severity)"
                    echo "  IOPS: $current_aws_iops/$max_iops ($(echo "$iops_util * 100" | bc | cut -d'.' -f1)%)"
                    echo "  Throughput: $current_throughput/$max_throughput MiB/s ($(echo "$throughput_util * 100" | bc | cut -d'.' -f1)%)"
                    echo ""
                done
            fi
        else
            echo "No bottleneck events detected ✅"
        fi
        
        echo "==============================================="
        
    } > "$summary_file"
    
    echo "📄 Summary saved to: $summary_file"
    
    # 显示关键信息
    echo ""
    echo "🎯 Key Findings:"
    for device in "$LEDGER_DEVICE" "$ACCOUNTS_DEVICE"; do
        if [[ -n "$device" && -n "${DEVICE_LIMITS["${device}_max_iops"]}" ]]; then
            local peak_iops=${PEAK_VALUES["${device}_max_iops"]}
            local max_iops=${DEVICE_LIMITS["${device}_max_iops"]}
            local peak_utilization=$(echo "scale=1; $peak_iops / $max_iops * 100" | bc)
            
            echo "  $device: Peak utilization ${peak_utilization}% (${peak_iops}/${max_iops} IOPS)"
            
            if (( $(echo "$peak_utilization > 85" | bc -l) )); then
                echo "    ⚠️  HIGH UTILIZATION - Consider upgrading EBS configuration"
            elif (( $(echo "$peak_utilization > 70" | bc -l) )); then
                echo "    ⚠️  MODERATE UTILIZATION - Monitor closely"
            else
                echo "    ✅ NORMAL UTILIZATION"
            fi
        fi
    done
}

# QPS测试期间启动EBS监控 - 新增函数
start_ebs_monitoring_for_qps_test() {
    local qps_duration="$1"
    local qps_start_time="$2"
    
    if [[ -z "$qps_duration" ]]; then
        echo "❌ QPS测试时长未指定"
        return 1
    fi
    
    echo "🔗 启动EBS瓶颈监控 (QPS测试模式)"
    echo "   QPS测试时长: ${qps_duration}s"
    echo "   QPS开始时间: ${qps_start_time:-$(date +'%Y-%m-%d %H:%M:%S')}"
    echo "   EBS监控将与QPS测试同步运行"
    echo ""
    
    # 记录QPS测试时间范围
    export QPS_TEST_START_TIME="${qps_start_time:-$(date +'%Y-%m-%d %H:%M:%S')}"
    export QPS_TEST_DURATION="$qps_duration"
    
    # 启动与QPS测试同步的EBS监控
    start_high_freq_monitoring "$qps_duration" "true"
}

# 停止EBS监控 - 新增函数
stop_ebs_monitoring() {
    echo "🛑 停止EBS瓶颈监控..."
    
    # 终止所有相关的监控进程
    pkill -f "ebs_bottleneck_detector" 2>/dev/null || true
    pkill -f "iostat.*${HIGH_FREQ_INTERVAL}" 2>/dev/null || true
    
    echo "✅ EBS监控已停止"
    
    # 生成监控摘要
    if [[ -f "$BOTTLENECK_LOG_FILE" ]]; then
        local bottleneck_count=$(wc -l < "$BOTTLENECK_LOG_FILE" 2>/dev/null || echo "0")
        echo "📊 监控期间检测到 $bottleneck_count 个EBS瓶颈事件"
        
        if [[ $bottleneck_count -gt 0 ]]; then
            echo "⚠️  EBS瓶颈详情请查看: $BOTTLENECK_LOG_FILE"
        fi
    fi
}

# 主函数
main() {
    echo "🔧 EBS Bottleneck Detector"
    echo "=========================="
    echo ""
    
    # 初始化
    init_ebs_limits
    echo ""
    
    # 解析参数
    local duration=300
    local background=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--duration)
                duration="$2"
                shift 2
                ;;
            -b|--background)
                background=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [options]"
                echo ""
                echo "Options:"
                echo "  -d, --duration SECONDS    Monitoring duration (default: 300)"
                echo "  -b, --background          Run in background"
                echo "  -h, --help               Show this help"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    if [[ "$background" == "true" ]]; then
        echo "🚀 Starting in background mode..."
        nohup "$0" -d "$duration" > "${LOGS_DIR}/ebs_bottleneck_detector.log" 2>&1 &
        echo "Background PID: $!"
        echo "Log file: ${LOGS_DIR}/ebs_bottleneck_detector.log"
    else
        start_high_freq_monitoring "$duration"
    fi
}

# 如果直接执行此脚本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
