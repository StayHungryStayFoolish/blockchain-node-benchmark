#!/usr/bin/env bash
# =====================================================================
# Monitoring Overhead CSV Writer for Unified Monitor
# =====================================================================
# Owns the monitoring_overhead_<session>.csv row collection, validation, and
# atomic write path. Function names preserve the original unified_monitor API.
# =====================================================================

validate_data_quality() {
    local data_line="$1"
    local expected_fields
    local actual_fields
    expected_fields=$(echo "$OVERHEAD_CSV_HEADER" | tr ',' '\n' | wc -l)
    actual_fields=$(echo "$data_line" | tr ',' '\n' | wc -l)

    if [[ "$actual_fields" -ne "$expected_fields" ]]; then
        log_error "Data quality check failed: field count mismatch"
        return 1
    fi

    if echo "$data_line" | grep -q ",,$\|^,$\|^,\|,$"; then
        log_error "Data quality check failed: empty fields or format errors detected"
        log_debug "Problem data line: $data_line"
        return 1
    fi

    return 0
}

clean_and_format_number() {
    local value="$1"
    local format="$2"
    local original_value="$value"
    local result

    value=$(echo "$value" | tr -cd '0-9.')
    if [[ "$value" == *.*.* ]]; then
        value=$(echo "$value" | sed 's/\([0-9]*\.[0-9]*\)\..*/\1/')
    fi
    if [[ -z "$value" ]] || [[ "$value" == "." ]] || [[ "$value" == ".." ]]; then
        value="0"
    fi
    if [[ "$value" == .* ]]; then
        value="0$value"
    fi
    if [[ "$value" == *. ]]; then
        value="${value%.*}"
    fi
    if ! [[ "$value" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        value="0"
    fi

    if [[ "$format" == "int" ]]; then
        result=$(printf "%.0f" "$value" 2>/dev/null || echo "0")
    else
        result=$(printf "%.2f" "$value" 2>/dev/null || echo "0.00")
    fi

    if [[ "$original_value" == *"."*"."* ]] || [[ "$result" == *"."*"."* ]] || [[ "$original_value" == "00" ]]; then
        log_debug "Data cleaning anomaly: input='$original_value' -> output='$result' (format:$format)"
    fi

    echo "$result"
}

collect_monitoring_overhead_data() {
    local start_time
    local timestamp
    start_time=$(date +%s%3N 2>/dev/null || date +%s)
    timestamp=$(get_unified_timestamp)

    local monitoring_pids
    local monitoring_resources
    local monitoring_cpu
    local monitoring_memory_percent
    local monitoring_memory_mb
    local monitoring_process_count
    monitoring_pids=$(discover_monitoring_processes)
    monitoring_resources=$(calculate_process_resources "$monitoring_pids" "monitoring")
    monitoring_cpu=$(echo "$monitoring_resources" | cut -d',' -f1)
    monitoring_memory_percent=$(echo "$monitoring_resources" | cut -d',' -f2)
    monitoring_memory_mb=$(echo "$monitoring_resources" | cut -d',' -f3)
    monitoring_process_count=$(echo "$monitoring_resources" | cut -d',' -f4)

    local blockchain_resources
    local blockchain_cpu
    local blockchain_memory_percent
    local blockchain_memory_mb
    local blockchain_process_count
    blockchain_resources=$(get_blockchain_node_resources)
    blockchain_cpu=$(echo "$blockchain_resources" | cut -d',' -f1)
    blockchain_memory_percent=$(echo "$blockchain_resources" | cut -d',' -f2)
    blockchain_memory_mb=$(echo "$blockchain_resources" | cut -d',' -f3)
    blockchain_process_count=$(echo "$blockchain_resources" | cut -d',' -f4)

    local system_static
    local system_cpu_cores
    local system_memory_gb
    local system_disk_gb
    system_static=$(get_system_static_resources)
    system_cpu_cores=$(echo "$system_static" | cut -d',' -f1)
    system_memory_gb=$(echo "$system_static" | cut -d',' -f2)
    system_disk_gb=$(echo "$system_static" | cut -d',' -f3)

    local system_dynamic
    local system_cpu_usage
    local system_memory_usage
    local system_disk_usage
    local system_cached_gb
    local system_buffers_gb
    local system_anon_pages_gb
    local system_mapped_gb
    local system_shmem_gb
    system_dynamic=$(get_system_dynamic_resources)
    system_cpu_usage=$(echo "$system_dynamic" | cut -d',' -f1)
    system_memory_usage=$(echo "$system_dynamic" | cut -d',' -f2)
    system_disk_usage=$(echo "$system_dynamic" | cut -d',' -f3)
    system_cached_gb=$(echo "$system_dynamic" | cut -d',' -f4)
    system_buffers_gb=$(echo "$system_dynamic" | cut -d',' -f5)
    system_anon_pages_gb=$(echo "$system_dynamic" | cut -d',' -f6)
    system_mapped_gb=$(echo "$system_dynamic" | cut -d',' -f7)
    system_shmem_gb=$(echo "$system_dynamic" | cut -d',' -f8)

    monitoring_cpu=$(clean_and_format_number "$monitoring_cpu" "float")
    monitoring_memory_percent=$(clean_and_format_number "$monitoring_memory_percent" "float")
    monitoring_memory_mb=$(clean_and_format_number "$monitoring_memory_mb" "float")
    monitoring_process_count=$(clean_and_format_number "$monitoring_process_count" "int")
    blockchain_cpu=$(clean_and_format_number "$blockchain_cpu" "float")
    blockchain_memory_percent=$(clean_and_format_number "$blockchain_memory_percent" "float")
    blockchain_memory_mb=$(clean_and_format_number "$blockchain_memory_mb" "float")
    blockchain_process_count=$(clean_and_format_number "$blockchain_process_count" "int")

    log_debug "System info raw values: CPU='$system_cpu_cores' Memory='$system_memory_gb' Disk='$system_disk_gb'"
    system_cpu_cores=$(clean_and_format_number "$system_cpu_cores" "int")
    system_memory_gb=$(clean_and_format_number "$system_memory_gb" "float")
    system_disk_gb=$(clean_and_format_number "$system_disk_gb" "float")
    log_debug "System info after cleaning: CPU='$system_cpu_cores' Memory='$system_memory_gb' Disk='$system_disk_gb'"

    system_cpu_usage=$(clean_and_format_number "$system_cpu_usage" "float")
    system_memory_usage=$(clean_and_format_number "$system_memory_usage" "float")
    system_disk_usage=$(clean_and_format_number "$system_disk_usage" "int")
    system_cached_gb=$(clean_and_format_number "$system_cached_gb" "float")
    system_buffers_gb=$(clean_and_format_number "$system_buffers_gb" "float")
    system_anon_pages_gb=$(clean_and_format_number "$system_anon_pages_gb" "float")
    system_mapped_gb=$(clean_and_format_number "$system_mapped_gb" "float")
    system_shmem_gb=$(clean_and_format_number "$system_shmem_gb" "float")

    local overhead_data_line="${timestamp},${monitoring_cpu},${monitoring_memory_percent},${monitoring_memory_mb},${monitoring_process_count},${blockchain_cpu},${blockchain_memory_percent},${blockchain_memory_mb},${blockchain_process_count},${system_cpu_cores},${system_memory_gb},${system_disk_gb},${system_cpu_usage},${system_memory_usage},${system_disk_usage},${system_cached_gb},${system_buffers_gb},${system_anon_pages_gb},${system_mapped_gb},${system_shmem_gb}"
    log_debug "Final data line: $(echo "$overhead_data_line" | cut -c1-150)..."

    if [[ "$overhead_data_line" == *",,"* ]]; then
        log_error "Monitoring overhead data format anomaly detected (empty fields): $overhead_data_line"
        return 1
    fi

    log_debug "Monitoring overhead data collection completed: monitoring_processes=${monitoring_process_count}, blockchain_processes=${blockchain_process_count}, system_cpu=${system_cpu_cores}cores"

    local end_time
    local current_resources
    local current_cpu
    local current_memory
    end_time=$(date +%s%3N 2>/dev/null || date +%s)
    current_resources=$(get_current_process_resources)
    current_cpu=$(echo "$current_resources" | cut -d',' -f1)
    current_memory=$(echo "$current_resources" | cut -d',' -f2)
    monitor_performance_impact "collect_monitoring_overhead_data" "$start_time" "$end_time" "$current_cpu" "$current_memory"

    local safe_timestamp="${timestamp:-$(date '+%Y-%m-%d %H:%M:%S')}"
    echo "$safe_timestamp,${monitoring_cpu:-0.00},${monitoring_memory_percent:-0.00},${monitoring_memory_mb:-0.00},${monitoring_process_count:-0},${blockchain_cpu:-0.00},${blockchain_memory_percent:-0.00},${blockchain_memory_mb:-0.00},${blockchain_process_count:-0},${system_cpu_cores:-0},${system_memory_gb:-0.00},${system_disk_gb:-0.00},${system_cpu_usage:-0.00},${system_memory_usage:-0.00},${system_disk_usage:-0.00},${system_cached_gb:-0.00},${system_buffers_gb:-0.00},${system_anon_pages_gb:-0.00},${system_mapped_gb:-0.00},${system_shmem_gb:-0.00}"
}

write_monitoring_overhead_log() {
    local log_dir
    local temp_file
    local lock_file

    log_dir=$(dirname "$MONITORING_OVERHEAD_LOG")
    mkdir -p "$log_dir"
    temp_file="${MONITORING_OVERHEAD_LOG}.tmp.$$"
    lock_file="${MONITORING_OVERHEAD_LOG}.lock"

    if ! (set -C; echo $$ > "$lock_file") 2>/dev/null; then
        log_warn "Monitoring overhead log file is locked, skipping this write"
        return 1
    fi

    if [[ ! -f "$MONITORING_OVERHEAD_LOG" ]] || [[ ! -s "$MONITORING_OVERHEAD_LOG" ]]; then
        if [[ -n "$OVERHEAD_CSV_HEADER" ]]; then
            echo "$OVERHEAD_CSV_HEADER" > "$temp_file"
            log_debug "Creating monitoring overhead log header: $OVERHEAD_CSV_HEADER"
        else
            log_error "OVERHEAD_CSV_HEADER variable not defined, cannot create header"
            rm -f "$lock_file"
            return 1
        fi
    else
        cp "$MONITORING_OVERHEAD_LOG" "$temp_file"
    fi

    local overhead_data_line
    if [[ "${ERROR_RECOVERY_ENABLED:-false}" == "true" ]]; then
        overhead_data_line=$(enhanced_collect_monitoring_overhead_data)
    else
        overhead_data_line=$(collect_monitoring_overhead_data)
    fi

    if [[ -n "$overhead_data_line" ]]; then
        if ! validate_data_quality "$overhead_data_line"; then
            log_error "Data quality check failed, skipping this write"
            rm -f "$temp_file" "$lock_file"
            return 1
        fi

        local expected_fields
        local actual_fields
        expected_fields=$(echo "$OVERHEAD_CSV_HEADER" | tr ',' '\n' | wc -l)
        actual_fields=$(echo "$overhead_data_line" | tr ',' '\n' | wc -l)
        if [[ "$actual_fields" -eq "$expected_fields" ]]; then
            echo "$overhead_data_line" >> "$temp_file"
            mv "$temp_file" "$MONITORING_OVERHEAD_LOG"
            log_debug "Monitoring overhead data written: $MONITORING_OVERHEAD_LOG"
        else
            log_error "Data format error: expected ${expected_fields} fields, actual ${actual_fields} fields"
            rm -f "$temp_file"
        fi
    else
        log_error "Monitoring overhead data collection failed"
        rm -f "$temp_file"
    fi

    rm -f "$lock_file"
}

validate_monitoring_overhead_config() {
    local validation_errors=()
    local validation_warnings=()

    if [[ -z "${MONITORING_PROCESS_NAMES_STR:-}" ]]; then
        validation_errors+=("MONITORING_PROCESS_NAMES_STR not defined or empty")
    fi
    if [[ -z "${BLOCKCHAIN_PROCESS_NAMES_STR:-}" ]]; then
        validation_errors+=("BLOCKCHAIN_PROCESS_NAMES_STR not defined or empty")
    fi
    if [[ -z "${MONITORING_OVERHEAD_LOG:-}" ]]; then
        validation_errors+=("MONITORING_OVERHEAD_LOG variable not defined")
    fi
    if [[ -z "${OVERHEAD_CSV_HEADER:-}" ]]; then
        validation_errors+=("OVERHEAD_CSV_HEADER variable not defined")
    fi

    if [[ -z "${DATA_VOL_MAX_IOPS:-}" || -z "${DATA_VOL_MAX_THROUGHPUT:-}" ]]; then
        validation_warnings+=("DATA device baseline not fully configured")
    fi
    if is_accounts_configured; then
        if [[ -z "${ACCOUNTS_VOL_MAX_THROUGHPUT:-}" ]]; then
            validation_warnings+=("ACCOUNTS device configured but baseline missing")
        fi
    fi

    local required_commands=("pgrep" "ps" "bc" "cut" "grep" "awk")
    for cmd in "${required_commands[@]}"; do
        if ! is_command_available "$cmd"; then
            validation_errors+=("Required command not available: $cmd")
        fi
    done

    local log_dir
    log_dir=$(dirname "$MONITORING_OVERHEAD_LOG")
    if [[ ! -d "$log_dir" ]]; then
        validation_warnings+=("Monitoring overhead log directory does not exist: $log_dir")
    elif [[ ! -w "$log_dir" ]]; then
        validation_errors+=("Monitoring overhead log directory not writable: $log_dir")
    fi

    if [[ ${#validation_errors[@]} -gt 0 ]]; then
        echo "❌ Configuration validation failed:" >&2
        for error in "${validation_errors[@]}"; do
            echo "   - $error" >&2
        done
        return 1
    fi

    if [[ ${#validation_warnings[@]} -gt 0 ]]; then
        echo "⚠️  Configuration validation warnings:" >&2
        for warning in "${validation_warnings[@]}"; do
            echo "   - $warning" >&2
        done
    fi

    log_debug "Monitoring overhead configuration validation passed"
    return 0
}

enhanced_collect_monitoring_overhead_data() {
    if [[ "${ERROR_RECOVERY_ENABLED:-false}" == "true" ]]; then
        safe_execute "collect_monitoring_overhead_data" "$@"
    else
        collect_monitoring_overhead_data "$@"
    fi
}
