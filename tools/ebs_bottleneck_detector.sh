#!/bin/bash
# EBS 实时瓶颈检测，控制台输出
# 高频监控EBS性能，实时检测IOPS和Throughput瓶颈

# 引入依赖
# 安全加载配置文件，避免readonly变量冲突
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "警告: 配置文件加载失败，使用默认配置"
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi
source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh"

# 初始化统一日志管理器
init_logger "ebs_bottleneck_detector" $LOG_LEVEL "${LOGS_DIR}/ebs_bottleneck_detector.log"

source "$(dirname "${BASH_SOURCE[0]}")/../utils/ebs_converter.sh"

# 瓶颈检测配置
# 使用统一的监控间隔，从config.sh加载
# 阈值配置 (可通过环境变量覆盖)
BOTTLENECK_EBS_IOPS_THRESHOLD=${BOTTLENECK_EBS_IOPS_THRESHOLD:-90}      # IOPS利用率阈值 (%)
BOTTLENECK_EBS_THROUGHPUT_THRESHOLD=${BOTTLENECK_EBS_THROUGHPUT_THRESHOLD:-90}  # 吞吐量利用率阈值 (%)

# 阈值配置
readonly BOTTLENECK_IOPS_THRESHOLD=$(echo "scale=4; ${BOTTLENECK_EBS_IOPS_THRESHOLD:-90} / 100" | bc)
readonly BOTTLENECK_THROUGHPUT_THRESHOLD=$(echo "scale=4; ${BOTTLENECK_EBS_THROUGHPUT_THRESHOLD:-90} / 100" | bc)

# 全局变量
declare -A DEVICE_LIMITS
declare -gA CSV_FIELD_MAP  # CSV字段映射：字段名 -> 列索引

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
                DEVICE_LIMITS["${LEDGER_DEVICE}_max_throughput"]="$DATA_VOL_MAX_THROUGHPUT"
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
                DEVICE_LIMITS["${ACCOUNTS_DEVICE}_max_throughput"]="$ACCOUNTS_VOL_MAX_THROUGHPUT"
                ;;
            "instance-store")
                DEVICE_LIMITS["${ACCOUNTS_DEVICE}_max_iops"]="$ACCOUNTS_VOL_MAX_IOPS"
                DEVICE_LIMITS["${ACCOUNTS_DEVICE}_max_throughput"]="$ACCOUNTS_VOL_MAX_THROUGHPUT"
                ;;
        esac
        echo "  ACCOUNTS Volume (${ACCOUNTS_DEVICE}): ${DEVICE_LIMITS["${ACCOUNTS_DEVICE}_max_iops"]} IOPS, ${DEVICE_LIMITS["${ACCOUNTS_DEVICE}_max_throughput"]} MiB/s"
    fi
}

# CSV字段映射初始化
init_csv_field_mapping() {
    local csv_file="$1"
    
    if [[ ! -f "$csv_file" ]]; then
        log_error "CSV文件不存在: $csv_file"
        return 1
    fi
    
    local header_line=$(head -n 1 "$csv_file" 2>/dev/null)
    if [[ -z "$header_line" ]]; then
        log_error "无法读取CSV文件头部: $csv_file"
        return 1
    fi
    
    # 清空现有映射
    declare -gA CSV_FIELD_MAP
    
    # 建立字段名到索引的映射
    local index=0
    IFS=',' read -ra header_fields <<< "$header_line"
    for field in "${header_fields[@]}"; do
        # 去除字段名的空白字符
        field=$(echo "$field" | tr -d ' \t\r\n')
        CSV_FIELD_MAP["$field"]=$index
        ((index++))
    done
    
    log_info "✅ CSV字段映射初始化完成，共映射 $index 个字段"
    return 0
}

# 从CSV行提取EBS数据
get_ebs_data_from_csv() {
    local device="$1"
    local csv_line="$2"
    
    if [[ -z "$device" || -z "$csv_line" ]]; then
        echo "0,0,0,0,0,0,0"
        return
    fi
    
    # 解析CSV行
    IFS="," read -ra fields <<< "$csv_line"
    
    # 根据设备类型确定字段前缀
    local prefix=""
    if [[ "$device" == "$LEDGER_DEVICE" ]]; then
        prefix="data_${device}"
    elif [[ -n "$ACCOUNTS_DEVICE" && "$device" == "$ACCOUNTS_DEVICE" ]]; then
        prefix="accounts_${device}"
    else
        log_warn "未知设备: $device，返回默认值"
        echo "0,0,0,0,0,0,0"
        return
    fi
    
    # 使用CSV_FIELD_MAP提取字段值
    local util_index="${CSV_FIELD_MAP["${prefix}_util"]:-}"
    local total_iops_index="${CSV_FIELD_MAP["${prefix}_total_iops"]:-}"
    local aws_standard_iops_index="${CSV_FIELD_MAP["${prefix}_aws_standard_iops"]:-}"
    local aws_standard_throughput_index="${CSV_FIELD_MAP["${prefix}_aws_standard_throughput_mibs"]:-}"
    local r_await_index="${CSV_FIELD_MAP["${prefix}_r_await"]:-}"
    local w_await_index="${CSV_FIELD_MAP["${prefix}_w_await"]:-}"
    
    # 安全提取字段值，使用默认值0
    local util="${fields[$util_index]:-0}"
    local total_iops="${fields[$total_iops_index]:-0}"
    local aws_standard_iops="${fields[$aws_standard_iops_index]:-0}"
    local aws_standard_throughput="${fields[$aws_standard_throughput_index]:-0}"
    local r_await="${fields[$r_await_index]:-0}"
    local w_await="${fields[$w_await_index]:-0}"
    
    # 数值验证：确保所有值都是有效的数字
    if ! [[ "$util" =~ ^[0-9]*\.?[0-9]+$ ]]; then util="0"; fi
    if ! [[ "$total_iops" =~ ^[0-9]*\.?[0-9]+$ ]]; then total_iops="0"; fi
    if ! [[ "$aws_standard_iops" =~ ^[0-9]*\.?[0-9]+$ ]]; then aws_standard_iops="0"; fi
    if ! [[ "$aws_standard_throughput" =~ ^[0-9]*\.?[0-9]+$ ]]; then aws_standard_throughput="0"; fi
    if ! [[ "$r_await" =~ ^[0-9]*\.?[0-9]+$ ]]; then r_await="0"; fi
    if ! [[ "$w_await" =~ ^[0-9]*\.?[0-9]+$ ]]; then w_await="0"; fi
    
    # 返回标准化格式：util,total_iops,aws_standard_iops,aws_standard_throughput,r_await,w_await,avg_io_kib
    echo "$util,$total_iops,$aws_standard_iops,$aws_standard_throughput,$r_await,$w_await,0"
}

# 验证必需的CSV字段是否存在
validate_required_csv_fields() {
    local required_fields=()
    
    # 为LEDGER_DEVICE添加必需字段
    if [[ -n "$LEDGER_DEVICE" ]]; then
        required_fields+=("data_${LEDGER_DEVICE}_util")
        required_fields+=("data_${LEDGER_DEVICE}_total_iops")
        required_fields+=("data_${LEDGER_DEVICE}_aws_standard_iops")
        required_fields+=("data_${LEDGER_DEVICE}_aws_standard_throughput_mibs")
        required_fields+=("data_${LEDGER_DEVICE}_r_await")
        required_fields+=("data_${LEDGER_DEVICE}_w_await")
    fi
    
    # 为ACCOUNTS_DEVICE添加必需字段（如果配置了）
    if [[ -n "$ACCOUNTS_DEVICE" ]]; then
        required_fields+=("accounts_${ACCOUNTS_DEVICE}_util")
        required_fields+=("accounts_${ACCOUNTS_DEVICE}_total_iops")
        required_fields+=("accounts_${ACCOUNTS_DEVICE}_aws_standard_iops")
        required_fields+=("accounts_${ACCOUNTS_DEVICE}_aws_standard_throughput_mibs")
        required_fields+=("accounts_${ACCOUNTS_DEVICE}_r_await")
        required_fields+=("accounts_${ACCOUNTS_DEVICE}_w_await")
    fi
    
    # 验证每个必需字段是否存在于CSV_FIELD_MAP中
    for field in "${required_fields[@]}"; do
        if [[ -z "${CSV_FIELD_MAP[$field]:-}" ]]; then
            log_error "❌ 关键字段缺失: $field"
            log_error "❌ CSV格式可能不兼容或设备配置错误"
            log_error "❌ 当前配置: LEDGER_DEVICE=$LEDGER_DEVICE, ACCOUNTS_DEVICE=$ACCOUNTS_DEVICE"
            return 1
        fi
    done
    
    log_info "✅ 所有关键字段验证通过，共验证 ${#required_fields[@]} 个字段"
    return 0
}

# CSV事件驱动监控
start_csv_monitoring() {
    local duration="$1"
    local csv_file="${LOGS_DIR}/performance_latest.csv"
    
    log_info "🚀 启动CSV事件驱动监控模式"
    log_info "📊 数据源: $csv_file"
    log_info "⏱️  监控时长: ${duration}s"
    
    # 初始化CSV字段映射
    if ! init_csv_field_mapping "$csv_file"; then
        log_error "❌ CSV字段映射初始化失败"
        return 1
    fi
    
    # 验证必需字段
    if ! validate_required_csv_fields; then
        log_error "❌ 必需字段验证失败"
        return 1
    fi
    
    log_info "📊 事件驱动模式: 监听CSV文件变化"
    
    # 使用tail -F跟踪文件名，处理文件轮转
    timeout "$duration" tail -F "$csv_file" 2>/dev/null | while IFS= read -r line; do
        # 跳过表头和空行
        [[ "$line" =~ ^timestamp ]] && continue
        [[ -z "$line" ]] && continue
        
        # 检测文件轮转：如果时间戳格式异常，重新初始化字段映射
        local timestamp=$(echo "$line" | cut -d',' -f1)
        if [[ ! "$timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2} ]]; then
            log_warn "⚠️  检测到CSV格式变化，重新初始化字段映射"
            init_csv_field_mapping "$csv_file"
            continue
        fi
        
        # 监控每个配置的设备
        for device in "$LEDGER_DEVICE" "$ACCOUNTS_DEVICE"; do
            [[ -z "$device" ]] && continue
            
            # 从CSV提取EBS数据
            local metrics=$(get_ebs_data_from_csv "$device" "$line")
            
            if [[ -n "$metrics" && "$metrics" != "0,0,0,0,0,0,0" ]]; then
                IFS=',' read -r util total_iops aws_standard_iops aws_standard_throughput r_await w_await _ <<< "$metrics"
                
                # 计算平均延迟
                local avg_latency=$(echo "scale=2; ($r_await + $w_await) / 2" | bc 2>/dev/null || echo "0")
                
                # 执行瓶颈检测 (使用正确的AWS标准化参数)
                detect_ebs_bottleneck "$device" "$total_iops" "$aws_standard_iops" "$aws_standard_throughput" "$avg_latency" "$timestamp"
                
                local bottleneck_detected=$?
                log_info "$timestamp,$device,$total_iops,$aws_standard_throughput,$avg_latency,$bottleneck_detected"
            fi
        done
    done
    
    # 处理tail -F异常退出
    local exit_code=$?
    if [[ $exit_code -ne 0 && $exit_code -ne 124 ]]; then  # 124是timeout正常退出
        log_error "⚠️  CSV监听异常退出 (exit code: $exit_code)"
        return $exit_code
    fi
    
    log_info "✅ CSV事件驱动监控完成"
    return 0
}

# 等待CSV文件准备就绪
wait_for_csv_ready() {
    local csv_file="${LOGS_DIR}/performance_latest.csv"
    local max_wait=60  # 60秒超时
    local wait_count=0
    
    log_info "⏳ 等待CSV文件准备就绪: $csv_file"
    
    while [[ $wait_count -lt $max_wait ]]; do
        # 检查软链接是否存在
        if [[ -L "$csv_file" ]]; then
            local target=$(readlink "$csv_file")
            local target_file="${LOGS_DIR}/$target"
            
            # 检查目标文件是否存在且有内容
            if [[ -f "$target_file" && -s "$target_file" ]]; then
                # 检查文件是否有数据行（不只是表头）
                local line_count=$(wc -l < "$target_file" 2>/dev/null || echo 0)
                if [[ $line_count -gt 1 ]]; then
                    # 验证表头格式
                    local header_line=$(head -n 1 "$target_file" 2>/dev/null)
                    if [[ -n "$header_line" && "$header_line" =~ ^timestamp ]]; then
                        log_info "✅ CSV文件准备就绪: $csv_file -> $target_file"
                        return 0
                    fi
                fi
            fi
        fi
        
        echo "   等待CSV数据生成... ($((wait_count + 1))/$max_wait)"
        sleep 1
        ((wait_count++))
    done
    
    log_error "❌ 超时: CSV文件未在${max_wait}秒内准备就绪"
    log_error "❌ 请确保unified_monitor.sh正在运行并生成CSV数据"
    return 1
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
    if (( $(echo "$iops_utilization > $BOTTLENECK_IOPS_THRESHOLD" | bc -l) )); then
        bottleneck_detected=true
        bottleneck_type="${bottleneck_type}IOPS,"
        
        # 使用可配置的阈值而不是硬编码值
        local critical_threshold=$(echo "scale=2; (${BOTTLENECK_EBS_IOPS_THRESHOLD:-90} + 5) / 100" | bc)
        local high_threshold=$(echo "scale=2; ${BOTTLENECK_EBS_IOPS_THRESHOLD:-90} / 100" | bc)
        
        if (( $(echo "$iops_utilization > $critical_threshold" | bc -l) )); then
            severity="CRITICAL"
        elif (( $(echo "$iops_utilization > $high_threshold" | bc -l) )); then
            severity="HIGH"
        else
            severity="MEDIUM"
        fi
    fi
    
    # Throughput瓶颈检测
    local throughput_utilization=$(echo "scale=4; $current_throughput / $max_throughput" | bc)
    if (( $(echo "$throughput_utilization > $BOTTLENECK_THROUGHPUT_THRESHOLD" | bc -l) )); then
        bottleneck_detected=true
        bottleneck_type="${bottleneck_type}THROUGHPUT,"
        
        # 使用可配置的阈值而不是硬编码值
        local critical_threshold=$(echo "scale=2; (${BOTTLENECK_EBS_THROUGHPUT_THRESHOLD:-90} + 5) / 100" | bc)
        local high_threshold=$(echo "scale=2; ${BOTTLENECK_EBS_THROUGHPUT_THRESHOLD:-90} / 100" | bc)
        
        if (( $(echo "$throughput_utilization > $critical_threshold" | bc -l) )); then
            severity="CRITICAL"
        elif (( $(echo "$throughput_utilization > $high_threshold" | bc -l) )); then
            severity="HIGH"
        else
            severity="MEDIUM"
        fi
    fi
    
    # 延迟瓶颈检测
    local latency_threshold=${BOTTLENECK_EBS_LATENCY_THRESHOLD:-50}
    if (( $(echo "$current_latency > $latency_threshold" | bc -l) )); then
        bottleneck_detected=true
        bottleneck_type="${bottleneck_type}LATENCY,"
        
        # 延迟严重程度分级
        local critical_latency_threshold=$(echo "scale=2; $latency_threshold * 2" | bc)
        if (( $(echo "$current_latency > $critical_latency_threshold" | bc -l) )); then
            severity="CRITICAL"
        else
            severity="HIGH"
        fi
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

# 启动高频监控
start_high_freq_monitoring() {
    local duration="$1"
    local qps_test_mode="${2:-false}"  # 是否为QPS测试模式
    
    # 添加持续运行模式支持
    if [[ "$duration" -eq 0 ]]; then
        log_info "🔄 持续运行模式 (跟随框架生命周期)"
        duration=2147483647  # 使用最大整数值实现持续运行
    fi
    
    # 如果没有指定时长，根据模式决定默认值
    if [[ -z "$duration" ]]; then
        if [[ "$qps_test_mode" == "true" ]]; then
            duration="$QPS_TEST_DURATION"  # 使用QPS测试时长
            log_info "🔗 EBS监控与QPS测试同步，时长: ${duration}s"
        else
            duration=300  # 独立运行时使用默认时长(5分钟)
            log_info "🔧 EBS独立监控模式，时长: ${duration}s"
        fi
    fi
    
    log_info "🚀 启动EBS瓶颈检测 (生产者-消费者模式)"
    log_info "   Duration: ${duration}s"
    log_info "   Data Source: iostat_collector.sh → unified_monitor.sh → performance_latest.csv"
    log_info "   Consumer Mode: Event-driven with dynamic field mapping"
    
    # 初始化EBS限制配置
    init_ebs_limits
    

    # 尝试CSV事件驱动模式
    if wait_for_csv_ready; then
        log_info "✅ 使用CSV事件驱动模式"
        start_csv_monitoring "$duration"
        local csv_result=$?
        
        if [[ $csv_result -eq 0 ]]; then
            log_info "✅ CSV事件驱动监控成功完成"
            return 0
        else
            log_error "❌ CSV事件驱动监控失败 (exit code: $csv_result)"
            return $csv_result
        fi
    else
        log_error "❌ CSV数据源不可用，退出并报告依赖失败"
        log_error "❌ 请确保unified_monitor.sh正在运行并生成CSV数据"
        log_error "❌ 检查监控协调器是否正确启动了依赖服务"
        exit 1
    fi
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

# QPS测试期间启动EBS监控
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
    pkill -f "iostat.*${MONITOR_INTERVAL}" 2>/dev/null || true
    
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
        echo "🔄 Framework lifecycle integration mode"
        echo "📝 Logging to: ${LOGS_DIR}/ebs_bottleneck_detector.log"
        # 直接调用监控函数，不重新启动进程
        # duration=0 表示持续运行，跟随框架生命周期
        # 重定向输出到日志文件
        exec > "${LOGS_DIR}/ebs_bottleneck_detector.log" 2>&1
        start_high_freq_monitoring 0
    else
        start_high_freq_monitoring "$duration"
    fi
}

# 如果直接执行此脚本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
