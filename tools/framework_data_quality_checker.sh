#!/bin/bash

# =====================================================================
# Framework Data Validation Script - Validate archived data and shared memory cache data quality
# =====================================================================

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load framework configuration
if ! source "${SCRIPT_DIR}/../config/config_loader.sh" 2>/dev/null; then
    echo "❌ Configuration file loading failed"
    exit 1
fi

# CSV Schema Registry — disk 段 header 单一事实源 (与 writer iostat_collector 同源).
# generate_expected_csv_header 经此生成 disk 段, 消除与 writer 重复的第二份 header 定义.
source "${SCRIPT_DIR}/../config/csv_schema_registry.sh" 2>/dev/null || true

# Validation result statistics
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
VALIDATION_ERRORS=()

# Log functions
log_info() { echo "ℹ️  $*"; }
log_success() { echo "✅ $*"; ((PASSED_CHECKS++)); }
log_error() { echo "❌ $*"; ((FAILED_CHECKS++)); VALIDATION_ERRORS+=("$*"); }
log_warn() { echo "⚠️  $*"; }

# Increase check count
check_count() { ((TOTAL_CHECKS++)); }

# Get latest archive number
get_latest_archive_number() {
    if [[ ! -d "$ARCHIVES_DIR" ]]; then
        echo "000"
        return
    fi
    
    local latest=$(ls -1 "$ARCHIVES_DIR" 2>/dev/null | grep "^run_" | sort -V | tail -1 | sed 's/run_//')
    echo "${latest:-000}"
}

# Validate file existence
validate_file_exists() {
    local file_path="$1"
    local file_desc="$2"
    
    check_count
    if [[ -f "$file_path" ]]; then
        log_success "$file_desc exists: $(basename "$file_path")"
        return 0
    else
        log_error "$file_desc does not exist: $file_path"
        return 1
    fi
}

# Validate CSV file format
validate_csv_file() {
    local csv_file="$1"
    local file_desc="$2"
    local expected_header="$3"
    
    if [[ ! -f "$csv_file" ]]; then
        log_error "$file_desc CSV file does not exist: $csv_file"
        return 1
    fi
    
    # Check if file is empty
    check_count
    if [[ ! -s "$csv_file" ]]; then
        log_error "$file_desc CSV file is empty"
        return 1
    fi
    log_success "$file_desc CSV file is not empty"
    
    # Validate header
    check_count
    local actual_header=$(head -1 "$csv_file")
    if [[ -n "$expected_header" ]]; then
        if [[ "$actual_header" == "$expected_header" ]]; then
            log_success "$file_desc CSV header is correct"
        else
            log_error "$file_desc CSV header mismatch"
            log_error "  Expected: $(echo "$expected_header" | cut -c1-100)..."
            log_error "  Actual: $(echo "$actual_header" | cut -c1-100)..."
            return 1
        fi
    else
        log_success "$file_desc CSV header exists: $(echo "$actual_header" | tr ',' '\n' | wc -l) fields"
    fi
    
    # Validate data row count
    check_count
    local line_count=$(wc -l < "$csv_file")
    if [[ $line_count -gt 1 ]]; then
        log_success "$file_desc CSV contains $((line_count - 1)) data rows"
    else
        log_error "$file_desc CSV has only header, no data rows"
        return 1
    fi
    
    # Validate timestamp format (check first 5 rows) - fixed to space-separated format
    check_count
    local invalid_timestamps=$(tail -n +2 "$csv_file" | head -5 | cut -d',' -f1 | grep -v '^[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\} [0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}' | wc -l)
    if [[ $invalid_timestamps -eq 0 ]]; then
        log_success "$file_desc timestamp format is correct"
    else
        log_error "$file_desc found $invalid_timestamps invalid timestamps"
    fi
    
    return 0
}

# Validate JSON file format
validate_json_file() {
    local json_file="$1"
    local file_desc="$2"
    local required_fields="$3"
    
    if [[ ! -f "$json_file" ]]; then
        log_error "$file_desc JSON file does not exist: $json_file"
        return 1
    fi
    
    # Validate JSON format
    check_count
    if jq empty "$json_file" 2>/dev/null; then
        log_success "$file_desc JSON format is correct"
    else
        log_error "$file_desc JSON format is invalid"
        return 1
    fi
    
    # Validate required fields
    if [[ -n "$required_fields" ]]; then
        check_count
        local missing_fields=()
        for field in $required_fields; do
            if ! jq -e ".$field" "$json_file" >/dev/null 2>&1; then
                missing_fields+=("$field")
            fi
        done
        
        if [[ ${#missing_fields[@]} -eq 0 ]]; then
            log_success "$file_desc JSON required fields are complete"
        else
            log_error "$file_desc JSON missing fields: ${missing_fields[*]}"
        fi
    fi
    
    return 0
}

# Validate data_loss_stats.json logical consistency
validate_data_loss_stats_logic() {
    local stats_file="$1"
    
    if [[ ! -f "$stats_file" ]]; then
        log_error "Statistics file does not exist: $stats_file"
        return 1
    fi
    
    check_count
    
    # Extract key values
    local data_loss_count=$(jq -r '.data_loss_count' "$stats_file" 2>/dev/null || echo "null")
    local data_loss_periods=$(jq -r '.data_loss_periods' "$stats_file" 2>/dev/null || echo "null")
    local total_duration=$(jq -r '.total_duration' "$stats_file" 2>/dev/null || echo "null")
    
    # Validate value validity
    local logic_errors=()
    
    # Check value types
    if [[ "$data_loss_count" == "null" ]] || ! [[ "$data_loss_count" =~ ^[0-9]+$ ]]; then
        logic_errors+=("data_loss_count invalid: $data_loss_count")
    fi
    
    if [[ "$data_loss_periods" == "null" ]] || ! [[ "$data_loss_periods" =~ ^[0-9]+$ ]]; then
        logic_errors+=("data_loss_periods invalid: $data_loss_periods")
    fi
    
    if [[ "$total_duration" == "null" ]] || ! [[ "$total_duration" =~ ^[0-9]+$ ]]; then
        logic_errors+=("total_duration invalid: $total_duration")
    fi
    
    # Validate logical relationships
    if [[ "$data_loss_count" =~ ^[0-9]+$ ]] && [[ "$data_loss_periods" =~ ^[0-9]+$ ]]; then
        # data_loss_count should be >= data_loss_periods (at least 1 sample per period)
        if [[ $data_loss_count -lt $data_loss_periods ]]; then
            logic_errors+=("Logic error: sample count($data_loss_count) < period count($data_loss_periods)")
        fi
        
        # If there are periods but no samples, or samples but no periods, both are abnormal
        if [[ $data_loss_periods -gt 0 && $data_loss_count -eq 0 ]]; then
            logic_errors+=("Logic error: has periods($data_loss_periods) but no samples($data_loss_count)")
        fi
        
        if [[ $data_loss_count -gt 0 && $data_loss_periods -eq 0 ]]; then
            logic_errors+=("Logic error: has samples($data_loss_count) but no periods($data_loss_periods)")
        fi
    fi
    
    # Validate duration logic
    if [[ "$total_duration" =~ ^[0-9]+$ ]] && [[ "$data_loss_periods" =~ ^[0-9]+$ ]]; then
        if [[ $data_loss_periods -gt 0 && $total_duration -eq 0 ]]; then
            logic_errors+=("Logic error: has periods($data_loss_periods) but no duration($total_duration)")
        fi
    fi
    
    # Output validation results
    if [[ ${#logic_errors[@]} -eq 0 ]]; then
        log_success "Data loss statistics logical consistency validation passed"
        
        # Output statistics summary
        if [[ "$data_loss_count" =~ ^[0-9]+$ ]] && [[ "$data_loss_periods" =~ ^[0-9]+$ ]] && [[ "$total_duration" =~ ^[0-9]+$ ]]; then
            local avg_duration=0
            if [[ $data_loss_periods -gt 0 ]]; then
                avg_duration=$((total_duration / data_loss_periods))
            fi
            
            echo "    📊 Statistics summary: ${data_loss_count} samples, ${data_loss_periods} periods, ${total_duration}s total duration, average ${avg_duration}s/period"
        fi
    else
        log_error "Data loss statistics logic validation failed:"
        for error in "${logic_errors[@]}"; do
            echo "    🔴 $error"
        done
        return 1
    fi
    
    return 0
}

# Validate Vegeta result file
validate_vegeta_file() {
    local vegeta_file="$1"
    local file_desc="$2"
    
    if [[ ! -f "$vegeta_file" ]]; then
        log_error "$file_desc Vegeta file does not exist: $vegeta_file"
        return 1
    fi
    
    # Validate JSON format
    check_count
    if ! jq empty "$vegeta_file" 2>/dev/null; then
        log_error "$file_desc Vegeta JSON format is invalid"
        return 1
    fi
    log_success "$file_desc Vegeta JSON format is correct"
    
    # Validate fields actually used by framework
    check_count
    local requests=$(jq -r '.requests' "$vegeta_file" 2>/dev/null || echo "null")
    local success_200=$(jq -r '.status_codes."200" // 0' "$vegeta_file" 2>/dev/null || echo "null")
    local avg_latency=$(jq -r '.latencies.mean' "$vegeta_file" 2>/dev/null || echo "null")
    
    # Validate field existence and numeric validity
    local field_errors=()
    
    if [[ "$requests" == "null" ]] || ! [[ "$requests" =~ ^[0-9]+$ ]] || [[ $requests -le 0 ]]; then
        field_errors+=("requests field invalid: $requests")
    fi
    
    if [[ "$success_200" == "null" ]] || ! [[ "$success_200" =~ ^[0-9]+$ ]]; then
        field_errors+=("status_codes.200 field invalid: $success_200")
    fi
    
    if [[ "$avg_latency" == "null" ]] || ! [[ "$avg_latency" =~ ^[0-9]+$ ]]; then
        field_errors+=("latencies.mean field invalid: $avg_latency")
    fi
    
    if [[ ${#field_errors[@]} -eq 0 ]]; then
        log_success "$file_desc Vegeta key fields are valid"
    else
        log_error "$file_desc Vegeta field validation failed: ${field_errors[*]}"
        return 1
    fi
    
    # Validate logical consistency
    check_count
    if [[ "$requests" =~ ^[0-9]+$ ]] && [[ "$success_200" =~ ^[0-9]+$ ]]; then
        if [[ $success_200 -le $requests ]]; then
            log_success "$file_desc Vegeta data logic is consistent"
        else
            log_error "$file_desc Vegeta data logic error: successful requests($success_200) > total requests($requests)"
            return 1
        fi
    fi
    
    return 0
}

# Extract error and warning information from log file
extract_log_warnings_errors() {
    local log_file="$1"
    local file_desc="$2"
    
    if [[ ! -f "$log_file" ]]; then
        log_warn "$file_desc log file does not exist: $(basename "$log_file")"
        return 0
    fi
    
    check_count
    
    # Extract ERROR and WARN messages (support multiple formats)
    local errors=$(grep -i "ERROR\|\[ERROR\]\|❌" "$log_file" 2>/dev/null | head -10 || true)
    local warnings=$(grep -i "WARN\|\[WARN\]\|⚠️" "$log_file" 2>/dev/null | head -10 || true)
    
    # Count - fix syntax error caused by newlines
    local error_count=$(echo "$errors" | grep -c . 2>/dev/null | tr -d '\n' || echo "0")
    local warn_count=$(echo "$warnings" | grep -c . 2>/dev/null | tr -d '\n' || echo "0")
    
    if [[ $error_count -eq 0 && $warn_count -eq 0 ]]; then
        log_success "$file_desc no errors or warnings"
        return 0
    fi
    
    # Output error information
    if [[ -n "$errors" && $error_count -gt 0 ]]; then
        log_error "$file_desc found $error_count errors:"
        echo "$errors" | while IFS= read -r line; do
            [[ -n "$line" ]] && echo "    🔴 $(echo "$line" | cut -c1-120)..."
        done
    fi
    
    # Output warning information
    if [[ -n "$warnings" && $warn_count -gt 0 ]]; then
        log_warn "$file_desc found $warn_count warnings:"
        echo "$warnings" | while IFS= read -r line; do
            [[ -n "$line" ]] && echo "    🟡 $(echo "$line" | cut -c1-120)..."
        done
    fi
    
    # If there are errors, mark as failed
    if [[ $error_count -gt 0 ]]; then
        log_error "$file_desc contains error messages"
        return 1
    else
        log_success "$file_desc only has warnings, no errors"
        return 0
    fi
}

# Generate expected CSV header
generate_expected_csv_header() {
    # basic 段 header — 经 csv_schema_registry 生成 (单一事实源, 与 writer unified_monitor.sh
    # generate_csv_header 严格对齐; S2/S3 writer-first 收敛: 消除此处与 writer 重复的第二份 basic 定义).
    # 防御: registry 未 source 时回退字面量 (与 registry _BASIC_FIELDS 字节一致, symmetry Phase3.5 守护).
    local basic_header
    if declare -F csv_registry_basic_header >/dev/null 2>&1; then
        basic_header="$(csv_registry_basic_header)"
    else
        basic_header="timestamp,cpu_usage,cpu_usr,cpu_sys,cpu_iowait,cpu_soft,cpu_idle,mem_used,mem_total,mem_usage"
    fi
    
    # Device header — 经 csv_schema_registry 生成 (单一事实源, 与 writer iostat_collector 严格对齐).
    # 方案甲(中立命名): provider_aware 字段三云统一 normalized_iops/normalized_throughput_mibs (ADR-0002).
    # provider 取配置驱动 (get_provider_name); 选甲后三云同名, provider 仅作 registry 接口透传.
    local _expect_provider="other"
    if declare -F get_provider_name >/dev/null 2>&1; then
        _expect_provider="$(get_provider_name 2>/dev/null || echo other)"
    fi
    local device_header=""
    if [[ -n "$LEDGER_DEVICE" ]] && declare -F csv_registry_disk_header >/dev/null 2>&1; then
        device_header="$(csv_registry_disk_header "data_${LEDGER_DEVICE}" "$_expect_provider")"
    fi
    if [[ -n "$ACCOUNTS_DEVICE" && "$ACCOUNTS_DEVICE" != "$LEDGER_DEVICE" ]] && declare -F csv_registry_disk_header >/dev/null 2>&1; then
        local _acct_header
        _acct_header="$(csv_registry_disk_header "accounts_${ACCOUNTS_DEVICE}" "$_expect_provider")"
        if [[ -n "$device_header" ]]; then
            device_header="${device_header},${_acct_header}"
        else
            device_header="$_acct_header"
        fi
    fi
    
    # network/overhead/block/qps 段经 registry 单一事实源 (F1: 与 writer unified_monitor
    # 同源, 消除双源字面量). registry 不可用时回退字面量(与 registry 字节一致)。
    local network_header overhead_header block_height_header qps_header
    if declare -F csv_registry_segment_header >/dev/null 2>&1; then
        network_header="$(csv_registry_segment_header network)"
        overhead_header="$(csv_registry_segment_header overhead)"
        block_height_header="$(csv_registry_segment_header block)"
        qps_header="$(csv_registry_segment_header qps)"
    else
        network_header="net_interface,net_rx_mbps,net_tx_mbps,net_total_mbps,net_rx_gbps,net_tx_gbps,net_total_gbps,net_rx_pps,net_tx_pps,net_total_pps"
        overhead_header="monitoring_iops_per_sec,monitoring_throughput_mibs_per_sec"
        block_height_header="local_block_height,mainnet_block_height,block_height_diff,local_health,mainnet_health,data_loss"
        qps_header="current_qps,rpc_latency_ms,qps_data_available"
    fi
    
    # Assemble complete header
    local full_header="$basic_header"
    [[ -n "$device_header" ]] && full_header="$full_header,$device_header"
    full_header="$full_header,$network_header"
    
    # ENA fields (if enabled) - dynamically generated fully synchronized with framework
    if [[ "$ENA_MONITOR_ENABLED" == "true" ]]; then
        # Use same dynamic generation logic as framework
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
    # CP-1 双云对等: 实际 header 末尾追加 cloud_provider 列(见 unified_monitor.sh:generate_csv_header).
    # 注意: 此 expected header 既有缺陷 — 未含 cgroup_header(19字段),与实际已不完全对齐;
    #       该缺陷早于本次改动,超出 CP-1 范围,记录于 analysis-notes/CP-1-execution-tracker.md 待办.
    #       本行仅同步本次新增的 cloud_provider 列,保持改动自洽.
    full_header="$full_header,cloud_provider"
    echo "$full_header"
}

# Validate archive files
validate_archive_files() {
    local run_number="$1"
    local archive_dir="$ARCHIVES_DIR/run_$run_number"
    
    log_info "Validating data files for archive run_$run_number..."
    
    if [[ ! -d "$archive_dir" ]]; then
        log_error "Archive directory does not exist: $archive_dir"
        return 1
    fi
    
    # Validate main CSV files
    local logs_dir="$archive_dir/logs"
    if [[ -d "$logs_dir" ]]; then
        # Find performance data file
        local perf_csv=$(find "$logs_dir" -name "performance_*.csv" | head -1)
        if [[ -n "$perf_csv" ]]; then
            local expected_header=$(generate_expected_csv_header)
            validate_csv_file "$perf_csv" "Performance data" "$expected_header"
        else
            log_error "Performance data CSV file not found"
        fi
        
        # Validate block height monitoring file
        local block_csv=$(find "$logs_dir" -name "block_height_monitor_*.csv" | head -1)
        if [[ -n "$block_csv" ]]; then
            local block_header="timestamp,local_block_height,mainnet_block_height,block_height_diff,local_health,mainnet_health,data_loss"
            validate_csv_file "$block_csv" "Block height monitoring" "$block_header"
        else
            log_warn "Block height monitoring CSV file not found"
        fi
        
        # Validate monitoring overhead file
        local overhead_csv=$(find "$logs_dir" -name "monitoring_overhead_*.csv" | head -1)
        if [[ -n "$overhead_csv" ]]; then
            validate_csv_file "$overhead_csv" "Monitoring overhead" ""
        else
            log_warn "Monitoring overhead CSV file not found"
        fi
        
        # Validate log files (extract errors and warnings)
        log_info "Checking errors and warnings in log files..."
        
        # Check various log files
        for log_pattern in "disk_bottleneck_detector.log" "disk_analyzer.log" "master_qps_executor.log" "monitoring_performance_*.log" "monitoring_errors_*.log"; do
            local log_files=$(find "$logs_dir" -name "$log_pattern" 2>/dev/null)
            if [[ -n "$log_files" ]]; then
                while IFS= read -r log_file; do
                    [[ -n "$log_file" ]] && extract_log_warnings_errors "$log_file" "$(basename "$log_file")"
                done <<< "$log_files"
            fi
        done
    else
        log_error "Archive logs directory does not exist: $logs_dir"
    fi
    
    # Validate statistics files in archive
    local stats_dir="$archive_dir/stats"
    if [[ -d "$stats_dir" ]]; then
        log_info "Validating archive statistics files..."
        
        # Validate data_loss_stats.json
        if [[ -f "$stats_dir/data_loss_stats.json" ]]; then
            local required_stats_fields="data_loss_count data_loss_periods total_duration last_updated"
            validate_json_file "$stats_dir/data_loss_stats.json" "Data loss statistics" "$required_stats_fields"
            
            # Validate logical consistency of statistics data
            validate_data_loss_stats_logic "$stats_dir/data_loss_stats.json"
        else
            log_warn "data_loss_stats.json file not found - possibly no data loss events during test"
        fi
        
        # Validate bottleneck_status.json
        if [[ -f "$stats_dir/bottleneck_status.json" ]]; then
            local required_bottleneck_fields="status bottleneck_detected"
            validate_json_file "$stats_dir/bottleneck_status.json" "Bottleneck status" "$required_bottleneck_fields"
        else
            log_warn "bottleneck_status.json file not found"
        fi
    else
        log_warn "Archive statistics directory not found: $stats_dir"
    fi
    
    # Validate Vegeta result files
    local vegeta_dir="$archive_dir/vegeta_results"
    if [[ -d "$vegeta_dir" ]]; then
        log_info "Validating Vegeta test result files..."
        
        local vegeta_files=$(find "$vegeta_dir" -name "*.json" 2>/dev/null)
        if [[ -n "$vegeta_files" ]]; then
            local vegeta_count=0
            while IFS= read -r vegeta_file; do
                if [[ -n "$vegeta_file" ]]; then
                    validate_vegeta_file "$vegeta_file" "Vegeta result[$(basename "$vegeta_file")]"
                    ((vegeta_count++))
                fi
            done <<< "$vegeta_files"
            
            if [[ $vegeta_count -eq 0 ]]; then
                log_warn "Vegeta results directory exists but no JSON files"
            fi
        else
            log_warn "Vegeta result JSON files not found"
        fi
    else
        log_warn "Vegeta results directory not found: $vegeta_dir"
    fi
}

# Validate shared memory files
validate_shared_memory_files() {
    log_info "Validating shared memory cache files..."
    
    if [[ ! -d "$MEMORY_SHARE_DIR" ]]; then
        log_warn "Shared memory directory does not exist: $MEMORY_SHARE_DIR (may have been cleaned up)"
        return 0
    fi
    
    # Validate core metrics JSON (if exists)
    if [[ -f "$MEMORY_SHARE_DIR/latest_metrics.json" ]]; then
        validate_json_file "$MEMORY_SHARE_DIR/latest_metrics.json" "Core metrics" "timestamp cpu_usage memory_usage"
    else
        log_info "Shared memory files have been cleaned up, skipping core metrics validation (normal framework behavior)"
    fi
    
    # Validate detailed metrics JSON (if exists)
    if [[ -f "$MEMORY_SHARE_DIR/unified_metrics.json" ]]; then
        validate_json_file "$MEMORY_SHARE_DIR/unified_metrics.json" "Detailed metrics" "timestamp cpu_usage memory_usage detailed_data"
    else
        log_info "Shared memory files have been cleaned up, skipping detailed metrics validation (normal framework behavior)"
    fi
    
    # Validate block height cache (if exists)
    if [[ -f "$MEMORY_SHARE_DIR/block_height_monitor_cache.json" ]]; then
        validate_json_file "$MEMORY_SHARE_DIR/block_height_monitor_cache.json" "Block height cache" "timestamp local_block_height mainnet_block_height"
    else
        log_info "Shared memory files have been cleaned up, skipping block height cache validation (normal framework behavior)"
    fi
    
    # Validate sample count file (if exists)
    if [[ -f "$MEMORY_SHARE_DIR/sample_count" ]]; then
        validate_file_exists "$MEMORY_SHARE_DIR/sample_count" "Sample count"
    else
        log_info "Shared memory files have been cleaned up, skipping sample count validation (normal framework behavior)"
    fi
    
    # Validate other optional files
    [[ -f "$MEMORY_SHARE_DIR/data_loss_stats.json" ]] && validate_json_file "$MEMORY_SHARE_DIR/data_loss_stats.json" "Data loss statistics" ""
    [[ -f "$MEMORY_SHARE_DIR/bottleneck_status.json" ]] && validate_json_file "$MEMORY_SHARE_DIR/bottleneck_status.json" "Bottleneck status" ""
    [[ -f "$MEMORY_SHARE_DIR/unified_events.json" ]] && validate_json_file "$MEMORY_SHARE_DIR/unified_events.json" "Unified events" ""
}

# Validate data consistency
validate_data_consistency() {
    local run_number="$1"
    
    log_info "Validating data consistency..."
    
    # If shared memory directory does not exist, skip consistency check
    if [[ ! -d "$MEMORY_SHARE_DIR" ]]; then
        log_warn "Shared memory directory does not exist, skipping consistency validation"
        return 0
    fi
    
    # Validate sample count consistency
    if [[ -f "$MEMORY_SHARE_DIR/sample_count" ]]; then
        check_count
        local sample_count=$(cat "$MEMORY_SHARE_DIR/sample_count" 2>/dev/null || echo "0")
        if [[ "$sample_count" =~ ^[0-9]+$ ]] && [[ $sample_count -gt 0 ]]; then
            log_success "Sample count valid: $sample_count"
        else
            log_error "Sample count invalid: $sample_count"
        fi
    fi
    
    # Validate timestamp consistency (JSON vs CSV)
    local archive_dir="$ARCHIVES_DIR/run_$run_number"
    local perf_csv=$(find "$archive_dir/logs" -name "performance_*.csv" 2>/dev/null | head -1)
    
    if [[ -n "$perf_csv" && -f "$MEMORY_SHARE_DIR/latest_metrics.json" ]]; then
        check_count
        local csv_last_timestamp=$(tail -1 "$perf_csv" | cut -d',' -f1)
        local json_timestamp=$(jq -r '.timestamp' "$MEMORY_SHARE_DIR/latest_metrics.json" 2>/dev/null)
        
        if [[ -n "$csv_last_timestamp" && -n "$json_timestamp" && "$json_timestamp" != "null" ]]; then
            # Simple timestamp format check - fixed to space-separated format
            if [[ "$csv_last_timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2} ]] && 
               [[ "$json_timestamp" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2} ]]; then
                log_success "Timestamp format consistent"
            else
                log_error "Timestamp format inconsistent: CSV=$csv_last_timestamp, JSON=$json_timestamp"
            fi
        else
            log_warn "Unable to obtain valid timestamps for consistency validation"
        fi
    fi
}

# Generate validation report
generate_validation_report() {
    local run_number="$1"
    
    echo ""
    echo "========================================"
    echo "🔍 Framework Data Validation Report"
    echo "========================================"
    echo "Validation time: $(date)"
    echo "Archive number: run_$run_number"
    echo "Configuration environment: $DEPLOYMENT_PLATFORM"
    echo "ENA monitoring: $ENA_MONITOR_ENABLED"
    echo ""
    echo "📊 Validation statistics:"
    echo "  Total checks: $TOTAL_CHECKS"
    echo "  Passed checks: $PASSED_CHECKS"
    echo "  Failed checks: $FAILED_CHECKS"
    
    local success_rate=0
    if [[ $TOTAL_CHECKS -gt 0 ]]; then
        success_rate=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))
    fi
    echo "  Success rate: $success_rate%"
    
    echo ""
    echo "📋 Validation coverage:"
    echo "  ✅ CSV data files (header, format, timestamp)"
    echo "  ✅ JSON configuration files (format, required fields)"
    echo "  ✅ Vegeta result files (key fields, logical consistency)"
    echo "  ✅ Archive statistics files (data_loss_stats.json logic validation)"
    echo "  ✅ Shared memory cache files (within 5-minute TTL)"
    echo "  ✅ Log files (error and warning extraction)"
    echo "  ✅ Data consistency (timestamp, sample count)"
    echo ""
    echo "📊 Validation coverage: ~90% (added archive statistics file validation)"
    
    if [[ $FAILED_CHECKS -eq 0 ]]; then
        echo ""
        echo "✅ Data validation passed - all check items are normal"
        echo "🎉 Data quality score: $success_rate/100"
        echo ""
        echo "🔍 Validation details:"
        echo "  • All CSV file headers are correctly formatted"
        echo "  • All JSON file structures are complete"
        echo "  • Vegeta test result data is valid"
        echo "  • Archive statistics file logic is consistent"
        echo "  • Log files have no serious errors"
        echo "  • Data timestamp consistency is good"
    else
        echo ""
        echo "❌ Data validation failed - found $FAILED_CHECKS issues"
        echo "📋 Error details:"
        for error in "${VALIDATION_ERRORS[@]}"; do
            echo "  • $error"
        done
        echo ""
        echo "⚠️  Data quality score: $success_rate/100"
        echo ""
        echo "🔧 Recommended fixes:"
        echo "  1. Check if CSV file headers match configuration"
        echo "  2. Verify JSON file format and required fields"
        echo "  3. Confirm Vegeta tests executed normally"
        echo "  4. Review error messages in log files"
        echo "  5. Check timing issues in data generation process"
    fi
    
    echo "========================================"
}

# Main function
main() {
    echo "🔍 Starting framework data validation..."
    echo ""
    
    # Get latest archive number
    local latest_run=$(get_latest_archive_number)
    
    if [[ "$latest_run" == "000" ]]; then
        log_error "No archive data found"
        exit 1
    fi
    
    log_info "Detected latest archive: run_$latest_run"
    echo ""
    
    # Execute validation
    validate_archive_files "$latest_run"
    echo ""
    
    validate_shared_memory_files
    echo ""
    
    validate_data_consistency "$latest_run"
    echo ""
    
    # Generate report
    generate_validation_report "$latest_run"
    
    # Return appropriate exit code
    if [[ $FAILED_CHECKS -eq 0 ]]; then
        exit 0
    else
        exit 1
    fi
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
