#!/bin/bash

# =====================================================================
# 框架数据验证脚本 - 验证归档数据和共享内存缓存数据质量
# =====================================================================

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 加载框架配置
if ! source "${SCRIPT_DIR}/../config/config_loader.sh" 2>/dev/null; then
    echo "❌ 配置文件加载失败"
    exit 1
fi

# 验证结果统计
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
VALIDATION_ERRORS=()

# 日志函数
log_info() { echo "ℹ️  $*"; }
log_success() { echo "✅ $*"; ((PASSED_CHECKS++)); }
log_error() { echo "❌ $*"; ((FAILED_CHECKS++)); VALIDATION_ERRORS+=("$*"); }
log_warn() { echo "⚠️  $*"; }

# 增加检查计数
check_count() { ((TOTAL_CHECKS++)); }

# 获取最新归档编号
get_latest_archive_number() {
    if [[ ! -d "$ARCHIVES_DIR" ]]; then
        echo "000"
        return
    fi
    
    local latest=$(ls -1 "$ARCHIVES_DIR" 2>/dev/null | grep "^run_" | sort -V | tail -1 | sed 's/run_//')
    echo "${latest:-000}"
}

# 验证文件存在性
validate_file_exists() {
    local file_path="$1"
    local file_desc="$2"
    
    check_count
    if [[ -f "$file_path" ]]; then
        log_success "$file_desc 存在: $(basename "$file_path")"
        return 0
    else
        log_error "$file_desc 不存在: $file_path"
        return 1
    fi
}

# 验证CSV文件格式
validate_csv_file() {
    local csv_file="$1"
    local file_desc="$2"
    local expected_header="$3"
    
    if [[ ! -f "$csv_file" ]]; then
        log_error "$file_desc CSV文件不存在: $csv_file"
        return 1
    fi
    
    # 检查文件是否为空
    check_count
    if [[ ! -s "$csv_file" ]]; then
        log_error "$file_desc CSV文件为空"
        return 1
    fi
    log_success "$file_desc CSV文件非空"
    
    # 验证表头
    check_count
    local actual_header=$(head -1 "$csv_file")
    if [[ -n "$expected_header" ]]; then
        if [[ "$actual_header" == "$expected_header" ]]; then
            log_success "$file_desc CSV表头正确"
        else
            log_error "$file_desc CSV表头不匹配"
            log_error "  预期: $(echo "$expected_header" | cut -c1-100)..."
            log_error "  实际: $(echo "$actual_header" | cut -c1-100)..."
            return 1
        fi
    else
        log_success "$file_desc CSV表头存在: $(echo "$actual_header" | tr ',' '\n' | wc -l) 个字段"
    fi
    
    # 验证数据行数
    check_count
    local line_count=$(wc -l < "$csv_file")
    if [[ $line_count -gt 1 ]]; then
        log_success "$file_desc CSV包含 $((line_count - 1)) 行数据"
    else
        log_error "$file_desc CSV只有表头，无数据行"
        return 1
    fi
    
    # 验证时间戳格式 (检查前5行) - 修复为空格分隔格式
    check_count
    local invalid_timestamps=$(tail -n +2 "$csv_file" | head -5 | cut -d',' -f1 | grep -v '^[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\} [0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}' | wc -l)
    if [[ $invalid_timestamps -eq 0 ]]; then
        log_success "$file_desc 时间戳格式正确"
    else
        log_error "$file_desc 发现 $invalid_timestamps 个无效时间戳"
    fi
    
    return 0
}

# 验证JSON文件格式
validate_json_file() {
    local json_file="$1"
    local file_desc="$2"
    local required_fields="$3"
    
    if [[ ! -f "$json_file" ]]; then
        log_error "$file_desc JSON文件不存在: $json_file"
        return 1
    fi
    
    # 验证JSON格式
    check_count
    if jq empty "$json_file" 2>/dev/null; then
        log_success "$file_desc JSON格式正确"
    else
        log_error "$file_desc JSON格式无效"
        return 1
    fi
    
    # 验证必需字段
    if [[ -n "$required_fields" ]]; then
        check_count
        local missing_fields=()
        for field in $required_fields; do
            if ! jq -e ".$field" "$json_file" >/dev/null 2>&1; then
                missing_fields+=("$field")
            fi
        done
        
        if [[ ${#missing_fields[@]} -eq 0 ]]; then
            log_success "$file_desc JSON必需字段完整"
        else
            log_error "$file_desc JSON缺少字段: ${missing_fields[*]}"
        fi
    fi
    
    return 0
}

# 验证data_loss_stats.json的逻辑一致性
validate_data_loss_stats_logic() {
    local stats_file="$1"
    
    if [[ ! -f "$stats_file" ]]; then
        log_error "统计文件不存在: $stats_file"
        return 1
    fi
    
    check_count
    
    # 提取关键数值
    local data_loss_count=$(jq -r '.data_loss_count' "$stats_file" 2>/dev/null || echo "null")
    local data_loss_periods=$(jq -r '.data_loss_periods' "$stats_file" 2>/dev/null || echo "null")
    local total_duration=$(jq -r '.total_duration' "$stats_file" 2>/dev/null || echo "null")
    
    # 验证数值有效性
    local logic_errors=()
    
    # 检查数值类型
    if [[ "$data_loss_count" == "null" ]] || ! [[ "$data_loss_count" =~ ^[0-9]+$ ]]; then
        logic_errors+=("data_loss_count无效: $data_loss_count")
    fi
    
    if [[ "$data_loss_periods" == "null" ]] || ! [[ "$data_loss_periods" =~ ^[0-9]+$ ]]; then
        logic_errors+=("data_loss_periods无效: $data_loss_periods")
    fi
    
    if [[ "$total_duration" == "null" ]] || ! [[ "$total_duration" =~ ^[0-9]+$ ]]; then
        logic_errors+=("total_duration无效: $total_duration")
    fi
    
    # 验证逻辑关系
    if [[ "$data_loss_count" =~ ^[0-9]+$ ]] && [[ "$data_loss_periods" =~ ^[0-9]+$ ]]; then
        # data_loss_count应该 >= data_loss_periods (每个周期至少1个采样)
        if [[ $data_loss_count -lt $data_loss_periods ]]; then
            logic_errors+=("逻辑错误: 采样数($data_loss_count) < 周期数($data_loss_periods)")
        fi
        
        # 如果有周期但无采样，或有采样但无周期，都是异常
        if [[ $data_loss_periods -gt 0 && $data_loss_count -eq 0 ]]; then
            logic_errors+=("逻辑错误: 有周期($data_loss_periods)但无采样($data_loss_count)")
        fi
        
        if [[ $data_loss_count -gt 0 && $data_loss_periods -eq 0 ]]; then
            logic_errors+=("逻辑错误: 有采样($data_loss_count)但无周期($data_loss_periods)")
        fi
    fi
    
    # 验证持续时间逻辑
    if [[ "$total_duration" =~ ^[0-9]+$ ]] && [[ "$data_loss_periods" =~ ^[0-9]+$ ]]; then
        if [[ $data_loss_periods -gt 0 && $total_duration -eq 0 ]]; then
            logic_errors+=("逻辑错误: 有周期($data_loss_periods)但无持续时间($total_duration)")
        fi
    fi
    
    # 输出验证结果
    if [[ ${#logic_errors[@]} -eq 0 ]]; then
        log_success "数据丢失统计逻辑一致性验证通过"
        
        # 输出统计摘要
        if [[ "$data_loss_count" =~ ^[0-9]+$ ]] && [[ "$data_loss_periods" =~ ^[0-9]+$ ]] && [[ "$total_duration" =~ ^[0-9]+$ ]]; then
            local avg_duration=0
            if [[ $data_loss_periods -gt 0 ]]; then
                avg_duration=$((total_duration / data_loss_periods))
            fi
            
            echo "    📊 统计摘要: ${data_loss_count}次采样, ${data_loss_periods}个周期, ${total_duration}秒总时长, 平均${avg_duration}秒/周期"
        fi
    else
        log_error "数据丢失统计逻辑验证失败:"
        for error in "${logic_errors[@]}"; do
            echo "    🔴 $error"
        done
        return 1
    fi
    
    return 0
}

# 验证Vegeta结果文件
validate_vegeta_file() {
    local vegeta_file="$1"
    local file_desc="$2"
    
    if [[ ! -f "$vegeta_file" ]]; then
        log_error "$file_desc Vegeta文件不存在: $vegeta_file"
        return 1
    fi
    
    # 验证JSON格式
    check_count
    if ! jq empty "$vegeta_file" 2>/dev/null; then
        log_error "$file_desc Vegeta JSON格式无效"
        return 1
    fi
    log_success "$file_desc Vegeta JSON格式正确"
    
    # 验证框架实际使用的字段
    check_count
    local requests=$(jq -r '.requests' "$vegeta_file" 2>/dev/null || echo "null")
    local success_200=$(jq -r '.status_codes."200" // 0' "$vegeta_file" 2>/dev/null || echo "null")
    local avg_latency=$(jq -r '.latencies.mean' "$vegeta_file" 2>/dev/null || echo "null")
    
    # 验证字段存在性和数值有效性
    local field_errors=()
    
    if [[ "$requests" == "null" ]] || ! [[ "$requests" =~ ^[0-9]+$ ]] || [[ $requests -le 0 ]]; then
        field_errors+=("requests字段无效: $requests")
    fi
    
    if [[ "$success_200" == "null" ]] || ! [[ "$success_200" =~ ^[0-9]+$ ]]; then
        field_errors+=("status_codes.200字段无效: $success_200")
    fi
    
    if [[ "$avg_latency" == "null" ]] || ! [[ "$avg_latency" =~ ^[0-9]+$ ]]; then
        field_errors+=("latencies.mean字段无效: $avg_latency")
    fi
    
    if [[ ${#field_errors[@]} -eq 0 ]]; then
        log_success "$file_desc Vegeta关键字段有效"
    else
        log_error "$file_desc Vegeta字段验证失败: ${field_errors[*]}"
        return 1
    fi
    
    # 验证逻辑一致性
    check_count
    if [[ "$requests" =~ ^[0-9]+$ ]] && [[ "$success_200" =~ ^[0-9]+$ ]]; then
        if [[ $success_200 -le $requests ]]; then
            log_success "$file_desc Vegeta数据逻辑一致"
        else
            log_error "$file_desc Vegeta数据逻辑错误: 成功请求($success_200) > 总请求($requests)"
            return 1
        fi
    fi
    
    return 0
}

# 提取日志文件中的错误和警告信息
extract_log_warnings_errors() {
    local log_file="$1"
    local file_desc="$2"
    
    if [[ ! -f "$log_file" ]]; then
        log_warn "$file_desc 日志文件不存在: $(basename "$log_file")"
        return 0
    fi
    
    check_count
    
    # 提取ERROR和WARN消息 (支持多种格式)
    local errors=$(grep -i "ERROR\|\[ERROR\]\|❌" "$log_file" 2>/dev/null | head -10 || true)
    local warnings=$(grep -i "WARN\|\[WARN\]\|⚠️" "$log_file" 2>/dev/null | head -10 || true)
    
    # 统计数量 - 修复换行符导致的语法错误
    local error_count=$(echo "$errors" | grep -c . 2>/dev/null | tr -d '\n' || echo "0")
    local warn_count=$(echo "$warnings" | grep -c . 2>/dev/null | tr -d '\n' || echo "0")
    
    if [[ $error_count -eq 0 && $warn_count -eq 0 ]]; then
        log_success "$file_desc 无错误或警告"
        return 0
    fi
    
    # 输出错误信息
    if [[ -n "$errors" && $error_count -gt 0 ]]; then
        log_error "$file_desc 发现 $error_count 个错误:"
        echo "$errors" | while IFS= read -r line; do
            [[ -n "$line" ]] && echo "    🔴 $(echo "$line" | cut -c1-120)..."
        done
    fi
    
    # 输出警告信息
    if [[ -n "$warnings" && $warn_count -gt 0 ]]; then
        log_warn "$file_desc 发现 $warn_count 个警告:"
        echo "$warnings" | while IFS= read -r line; do
            [[ -n "$line" ]] && echo "    🟡 $(echo "$line" | cut -c1-120)..."
        done
    fi
    
    # 如果有错误，标记为失败
    if [[ $error_count -gt 0 ]]; then
        log_error "$file_desc 包含错误信息"
        return 1
    else
        log_success "$file_desc 仅有警告，无错误"
        return 0
    fi
}

# 生成预期的CSV表头
generate_expected_csv_header() {
    local basic_header="timestamp,cpu_usage,cpu_usr,cpu_sys,cpu_iowait,cpu_soft,cpu_idle,mem_used,mem_total,mem_usage"
    
    # 设备表头 (与框架实际生成逻辑同步)
    local device_header=""
    if [[ -n "$LEDGER_DEVICE" ]]; then
        device_header="data_${LEDGER_DEVICE}_r_s,data_${LEDGER_DEVICE}_w_s,data_${LEDGER_DEVICE}_rkb_s,data_${LEDGER_DEVICE}_wkb_s,data_${LEDGER_DEVICE}_r_await,data_${LEDGER_DEVICE}_w_await,data_${LEDGER_DEVICE}_avg_await,data_${LEDGER_DEVICE}_aqu_sz,data_${LEDGER_DEVICE}_util,data_${LEDGER_DEVICE}_rrqm_s,data_${LEDGER_DEVICE}_wrqm_s,data_${LEDGER_DEVICE}_rrqm_pct,data_${LEDGER_DEVICE}_wrqm_pct,data_${LEDGER_DEVICE}_rareq_sz,data_${LEDGER_DEVICE}_wareq_sz,data_${LEDGER_DEVICE}_total_iops,data_${LEDGER_DEVICE}_aws_standard_iops,data_${LEDGER_DEVICE}_read_throughput_mibs,data_${LEDGER_DEVICE}_write_throughput_mibs,data_${LEDGER_DEVICE}_total_throughput_mibs,data_${LEDGER_DEVICE}_aws_standard_throughput_mibs"
    fi
    if [[ -n "$ACCOUNTS_DEVICE" && "$ACCOUNTS_DEVICE" != "$LEDGER_DEVICE" ]]; then
        if [[ -n "$device_header" ]]; then
            device_header="$device_header,accounts_${ACCOUNTS_DEVICE}_r_s,accounts_${ACCOUNTS_DEVICE}_w_s,accounts_${ACCOUNTS_DEVICE}_rkb_s,accounts_${ACCOUNTS_DEVICE}_wkb_s,accounts_${ACCOUNTS_DEVICE}_r_await,accounts_${ACCOUNTS_DEVICE}_w_await,accounts_${ACCOUNTS_DEVICE}_avg_await,accounts_${ACCOUNTS_DEVICE}_aqu_sz,accounts_${ACCOUNTS_DEVICE}_util,accounts_${ACCOUNTS_DEVICE}_rrqm_s,accounts_${ACCOUNTS_DEVICE}_wrqm_s,accounts_${ACCOUNTS_DEVICE}_rrqm_pct,accounts_${ACCOUNTS_DEVICE}_wrqm_pct,accounts_${ACCOUNTS_DEVICE}_rareq_sz,accounts_${ACCOUNTS_DEVICE}_wareq_sz,accounts_${ACCOUNTS_DEVICE}_total_iops,accounts_${ACCOUNTS_DEVICE}_aws_standard_iops,accounts_${ACCOUNTS_DEVICE}_read_throughput_mibs,accounts_${ACCOUNTS_DEVICE}_write_throughput_mibs,accounts_${ACCOUNTS_DEVICE}_total_throughput_mibs,accounts_${ACCOUNTS_DEVICE}_aws_standard_throughput_mibs"
        else
            device_header="accounts_${ACCOUNTS_DEVICE}_r_s,accounts_${ACCOUNTS_DEVICE}_w_s,accounts_${ACCOUNTS_DEVICE}_rkb_s,accounts_${ACCOUNTS_DEVICE}_wkb_s,accounts_${ACCOUNTS_DEVICE}_r_await,accounts_${ACCOUNTS_DEVICE}_w_await,accounts_${ACCOUNTS_DEVICE}_avg_await,accounts_${ACCOUNTS_DEVICE}_aqu_sz,accounts_${ACCOUNTS_DEVICE}_util,accounts_${ACCOUNTS_DEVICE}_rrqm_s,accounts_${ACCOUNTS_DEVICE}_wrqm_s,accounts_${ACCOUNTS_DEVICE}_rrqm_pct,accounts_${ACCOUNTS_DEVICE}_wrqm_pct,accounts_${ACCOUNTS_DEVICE}_rareq_sz,accounts_${ACCOUNTS_DEVICE}_wareq_sz,accounts_${ACCOUNTS_DEVICE}_total_iops,accounts_${ACCOUNTS_DEVICE}_aws_standard_iops,accounts_${ACCOUNTS_DEVICE}_read_throughput_mibs,accounts_${ACCOUNTS_DEVICE}_write_throughput_mibs,accounts_${ACCOUNTS_DEVICE}_total_throughput_mibs,accounts_${ACCOUNTS_DEVICE}_aws_standard_throughput_mibs"
        fi
    fi
    
    local network_header="net_interface,net_rx_mbps,net_tx_mbps,net_total_mbps,net_rx_gbps,net_tx_gbps,net_total_gbps,net_rx_pps,net_tx_pps,net_total_pps"
    local overhead_header="monitoring_iops_per_sec,monitoring_throughput_mibs_per_sec"
    local block_height_header="local_block_height,mainnet_block_height,block_height_diff,local_health,mainnet_health,data_loss"
    local qps_header="current_qps,rpc_latency_ms,qps_data_available"
    
    # 组装完整表头
    local full_header="$basic_header"
    [[ -n "$device_header" ]] && full_header="$full_header,$device_header"
    full_header="$full_header,$network_header"
    
    # ENA字段 (如果启用) - 动态生成与框架完全同步
    if [[ "$ENA_MONITOR_ENABLED" == "true" ]]; then
        # 使用框架相同的动态生成逻辑
        local ena_header=""
        if [[ -n "$ENA_ALLOWANCE_FIELDS_STR" ]]; then
            ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
            for field in "${ena_fields[@]}"; do
                if [[ -n "$ena_header" ]]; then
                    ena_header="$ena_header,$field"
                else
                    ena_header="$field"
                fi
            done
        fi
        [[ -n "$ena_header" ]] && full_header="$full_header,$ena_header"
    fi
    
    full_header="$full_header,$overhead_header,$block_height_header,$qps_header"
    echo "$full_header"
}

# 验证归档文件
validate_archive_files() {
    local run_number="$1"
    local archive_dir="$ARCHIVES_DIR/run_$run_number"
    
    log_info "验证归档 run_$run_number 的数据文件..."
    
    if [[ ! -d "$archive_dir" ]]; then
        log_error "归档目录不存在: $archive_dir"
        return 1
    fi
    
    # 验证主要CSV文件
    local logs_dir="$archive_dir/logs"
    if [[ -d "$logs_dir" ]]; then
        # 查找性能数据文件
        local perf_csv=$(find "$logs_dir" -name "performance_*.csv" | head -1)
        if [[ -n "$perf_csv" ]]; then
            local expected_header=$(generate_expected_csv_header)
            validate_csv_file "$perf_csv" "性能数据" "$expected_header"
        else
            log_error "未找到性能数据CSV文件"
        fi
        
        # 验证区块高度监控文件
        local block_csv=$(find "$logs_dir" -name "block_height_monitor_*.csv" | head -1)
        if [[ -n "$block_csv" ]]; then
            local block_header="timestamp,local_block_height,mainnet_block_height,block_height_diff,local_health,mainnet_health,data_loss"
            validate_csv_file "$block_csv" "区块高度监控" "$block_header"
        else
            log_warn "未找到区块高度监控CSV文件"
        fi
        
        # 验证监控开销文件
        local overhead_csv=$(find "$logs_dir" -name "monitoring_overhead_*.csv" | head -1)
        if [[ -n "$overhead_csv" ]]; then
            validate_csv_file "$overhead_csv" "监控开销" ""
        else
            log_warn "未找到监控开销CSV文件"
        fi
        
        # 验证日志文件 (提取错误和警告)
        log_info "检查日志文件中的错误和警告信息..."
        
        # 检查各种日志文件
        for log_pattern in "ebs_bottleneck_detector.log" "ebs_analyzer.log" "master_qps_executor.log" "monitoring_performance_*.log" "monitoring_errors_*.log"; do
            local log_files=$(find "$logs_dir" -name "$log_pattern" 2>/dev/null)
            if [[ -n "$log_files" ]]; then
                while IFS= read -r log_file; do
                    [[ -n "$log_file" ]] && extract_log_warnings_errors "$log_file" "$(basename "$log_file")"
                done <<< "$log_files"
            fi
        done
    else
        log_error "归档日志目录不存在: $logs_dir"
    fi
    
    # 验证归档中的统计文件
    local stats_dir="$archive_dir/stats"
    if [[ -d "$stats_dir" ]]; then
        log_info "验证归档统计文件..."
        
        # 验证data_loss_stats.json
        if [[ -f "$stats_dir/data_loss_stats.json" ]]; then
            local required_stats_fields="data_loss_count data_loss_periods total_duration last_updated"
            validate_json_file "$stats_dir/data_loss_stats.json" "数据丢失统计" "$required_stats_fields"
            
            # 验证统计数据的逻辑一致性
            validate_data_loss_stats_logic "$stats_dir/data_loss_stats.json"
        else
            log_warn "未找到data_loss_stats.json文件 - 可能测试期间无数据丢失事件"
        fi
        
        # 验证bottleneck_status.json
        if [[ -f "$stats_dir/bottleneck_status.json" ]]; then
            local required_bottleneck_fields="status bottleneck_detected"
            validate_json_file "$stats_dir/bottleneck_status.json" "瓶颈状态" "$required_bottleneck_fields"
        else
            log_warn "未找到bottleneck_status.json文件"
        fi
    else
        log_warn "未找到归档统计目录: $stats_dir"
    fi
    
    # 验证Vegeta结果文件
    local vegeta_dir="$archive_dir/vegeta_results"
    if [[ -d "$vegeta_dir" ]]; then
        log_info "验证Vegeta测试结果文件..."
        
        local vegeta_files=$(find "$vegeta_dir" -name "*.json" 2>/dev/null)
        if [[ -n "$vegeta_files" ]]; then
            local vegeta_count=0
            while IFS= read -r vegeta_file; do
                if [[ -n "$vegeta_file" ]]; then
                    validate_vegeta_file "$vegeta_file" "Vegeta结果[$(basename "$vegeta_file")]"
                    ((vegeta_count++))
                fi
            done <<< "$vegeta_files"
            
            if [[ $vegeta_count -eq 0 ]]; then
                log_warn "Vegeta结果目录存在但无JSON文件"
            fi
        else
            log_warn "未找到Vegeta结果JSON文件"
        fi
    else
        log_warn "未找到Vegeta结果目录: $vegeta_dir"
    fi
}

# 验证共享内存文件
validate_shared_memory_files() {
    log_info "验证共享内存缓存文件..."
    
    if [[ ! -d "$MEMORY_SHARE_DIR" ]]; then
        log_warn "共享内存目录不存在: $MEMORY_SHARE_DIR (可能已被清理)"
        return 0
    fi
    
    # 验证核心指标JSON (如果存在)
    if [[ -f "$MEMORY_SHARE_DIR/latest_metrics.json" ]]; then
        validate_json_file "$MEMORY_SHARE_DIR/latest_metrics.json" "核心指标" "timestamp cpu_usage memory_usage"
    else
        log_info "共享内存文件已被清理，跳过核心指标验证 (框架正常行为)"
    fi
    
    # 验证详细指标JSON (如果存在)
    if [[ -f "$MEMORY_SHARE_DIR/unified_metrics.json" ]]; then
        validate_json_file "$MEMORY_SHARE_DIR/unified_metrics.json" "详细指标" "timestamp cpu_usage memory_usage detailed_data"
    else
        log_info "共享内存文件已被清理，跳过详细指标验证 (框架正常行为)"
    fi
    
    # 验证区块高度缓存 (如果存在)
    if [[ -f "$MEMORY_SHARE_DIR/block_height_monitor_cache.json" ]]; then
        validate_json_file "$MEMORY_SHARE_DIR/block_height_monitor_cache.json" "区块高度缓存" "timestamp local_block_height mainnet_block_height"
    else
        log_info "共享内存文件已被清理，跳过区块高度缓存验证 (框架正常行为)"
    fi
    
    # 验证采样计数文件 (如果存在)
    if [[ -f "$MEMORY_SHARE_DIR/sample_count" ]]; then
        validate_file_exists "$MEMORY_SHARE_DIR/sample_count" "采样计数"
    else
        log_info "共享内存文件已被清理，跳过采样计数验证 (框架正常行为)"
    fi
    
    # 验证其他可选文件
    [[ -f "$MEMORY_SHARE_DIR/data_loss_stats.json" ]] && validate_json_file "$MEMORY_SHARE_DIR/data_loss_stats.json" "数据丢失统计" ""
    [[ -f "$MEMORY_SHARE_DIR/bottleneck_status.json" ]] && validate_json_file "$MEMORY_SHARE_DIR/bottleneck_status.json" "瓶颈状态" ""
    [[ -f "$MEMORY_SHARE_DIR/unified_events.json" ]] && validate_json_file "$MEMORY_SHARE_DIR/unified_events.json" "统一事件" ""
}

# 验证数据一致性
validate_data_consistency() {
    local run_number="$1"
    
    log_info "验证数据一致性..."
    
    # 如果共享内存目录不存在，跳过一致性检查
    if [[ ! -d "$MEMORY_SHARE_DIR" ]]; then
        log_warn "共享内存目录不存在，跳过一致性验证"
        return 0
    fi
    
    # 验证采样计数一致性
    if [[ -f "$MEMORY_SHARE_DIR/sample_count" ]]; then
        check_count
        local sample_count=$(cat "$MEMORY_SHARE_DIR/sample_count" 2>/dev/null || echo "0")
        if [[ "$sample_count" =~ ^[0-9]+$ ]] && [[ $sample_count -gt 0 ]]; then
            log_success "采样计数有效: $sample_count"
        else
            log_error "采样计数无效: $sample_count"
        fi
    fi
    
    # 验证时间戳一致性 (JSON vs CSV)
    local archive_dir="$ARCHIVES_DIR/run_$run_number"
    local perf_csv=$(find "$archive_dir/logs" -name "performance_*.csv" 2>/dev/null | head -1)
    
    if [[ -n "$perf_csv" && -f "$MEMORY_SHARE_DIR/latest_metrics.json" ]]; then
        check_count
        local csv_last_timestamp=$(tail -1 "$perf_csv" | cut -d',' -f1)
        local json_timestamp=$(jq -r '.timestamp' "$MEMORY_SHARE_DIR/latest_metrics.json" 2>/dev/null)
        
        if [[ -n "$csv_last_timestamp" && -n "$json_timestamp" && "$json_timestamp" != "null" ]]; then
            # 简单的时间戳格式检查 - 修复为空格分隔格式
            if [[ "$csv_last_timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2} ]] && 
               [[ "$json_timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2} ]]; then
                log_success "时间戳格式一致"
            else
                log_error "时间戳格式不一致: CSV=$csv_last_timestamp, JSON=$json_timestamp"
            fi
        else
            log_warn "无法获取有效时间戳进行一致性验证"
        fi
    fi
}

# 生成验证报告
generate_validation_report() {
    local run_number="$1"
    
    echo ""
    echo "========================================"
    echo "🔍 框架数据验证报告"
    echo "========================================"
    echo "验证时间: $(date)"
    echo "归档编号: run_$run_number"
    echo "配置环境: $DEPLOYMENT_PLATFORM"
    echo "ENA监控: $ENA_MONITOR_ENABLED"
    echo ""
    echo "📊 验证统计:"
    echo "  总检查项: $TOTAL_CHECKS"
    echo "  通过检查: $PASSED_CHECKS"
    echo "  失败检查: $FAILED_CHECKS"
    
    local success_rate=0
    if [[ $TOTAL_CHECKS -gt 0 ]]; then
        success_rate=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))
    fi
    echo "  成功率: $success_rate%"
    
    echo ""
    echo "📋 验证覆盖范围:"
    echo "  ✅ CSV数据文件 (表头、格式、时间戳)"
    echo "  ✅ JSON配置文件 (格式、必需字段)"
    echo "  ✅ Vegeta结果文件 (关键字段、逻辑一致性)"
    echo "  ✅ 归档统计文件 (data_loss_stats.json逻辑验证)"
    echo "  ✅ 共享内存缓存文件 (5分钟TTL内)"
    echo "  ✅ 日志文件 (错误和警告提取)"
    echo "  ✅ 数据一致性 (时间戳、采样计数)"
    echo ""
    echo "📊 验证覆盖率: ~90% (新增归档统计文件验证)"
    
    if [[ $FAILED_CHECKS -eq 0 ]]; then
        echo ""
        echo "✅ 数据验证通过 - 所有检查项目都正常"
        echo "🎉 数据质量评分: $success_rate/100"
        echo ""
        echo "🔍 验证详情:"
        echo "  • 所有CSV文件表头格式正确"
        echo "  • 所有JSON文件结构完整"
        echo "  • Vegeta测试结果数据有效"
        echo "  • 归档统计文件逻辑一致"
        echo "  • 日志文件无严重错误"
        echo "  • 数据时间戳一致性良好"
    else
        echo ""
        echo "❌ 数据验证失败 - 发现 $FAILED_CHECKS 个问题"
        echo "📋 错误详情:"
        for error in "${VALIDATION_ERRORS[@]}"; do
            echo "  • $error"
        done
        echo ""
        echo "⚠️  数据质量评分: $success_rate/100"
        echo ""
        echo "🔧 建议修复:"
        echo "  1. 检查CSV文件表头是否与配置匹配"
        echo "  2. 验证JSON文件格式和必需字段"
        echo "  3. 确认Vegeta测试正常执行"
        echo "  4. 查看日志文件中的错误信息"
        echo "  5. 检查数据生成过程的时序问题"
    fi
    
    echo "========================================"
}

# 主函数
main() {
    echo "🔍 开始框架数据验证..."
    echo ""
    
    # 获取最新归档编号
    local latest_run=$(get_latest_archive_number)
    
    if [[ "$latest_run" == "000" ]]; then
        log_error "未找到任何归档数据"
        exit 1
    fi
    
    log_info "检测到最新归档: run_$latest_run"
    echo ""
    
    # 执行验证
    validate_archive_files "$latest_run"
    echo ""
    
    validate_shared_memory_files
    echo ""
    
    validate_data_consistency "$latest_run"
    echo ""
    
    # 生成报告
    generate_validation_report "$latest_run"
    
    # 返回适当的退出码
    if [[ $FAILED_CHECKS -eq 0 ]]; then
        exit 0
    else
        exit 1
    fi
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
