#!/bin/bash
# Shared utilities for unified monitoring.

# Command availability cache - avoids repeated command -v calls.
declare -A COMMAND_CACHE

is_command_available() {
    local cmd="$1"

    if [[ -z "$cmd" ]]; then
        log_error "is_command_available: Command name cannot be empty"
        return 1
    fi

    if [[ -n "${COMMAND_CACHE[$cmd]:-}" ]]; then
        [[ "${COMMAND_CACHE[$cmd]}" == "1" ]]
        return $?
    fi

    if command -v "$cmd" >/dev/null 2>&1; then
        COMMAND_CACHE[$cmd]="1"
        log_debug "Command available and cached: $cmd"
        return 0
    fi

    COMMAND_CACHE[$cmd]="0"
    log_debug "Command unavailable and cached: $cmd"
    return 1
}

init_command_cache() {
    local commands=(
        "mpstat"
        "free"
        "sar"
        "ethtool"
        "nproc"
        "sysctl"
        "df"
        "top"
        "ps"
        "pgrep"
        "bc"
        "uptime"
    )

    log_info "🔧 Initializing command availability cache (${#commands[@]} commands)..."

    local available_count=0
    for cmd in "${commands[@]}"; do
        if is_command_available "$cmd" >/dev/null; then
            available_count=$((available_count + 1))
        fi
    done

    log_info "✅ Command cache initialization completed: $available_count/${#commands[@]} commands available"
}

validate_numeric_value() {
    local value="$1"
    local default_value="${2:-0}"

    if [[ "$value" =~ ^[0-9]+\.?[0-9]*$ ]] || [[ "$value" =~ ^[0-9]*\.[0-9]+$ ]]; then
        echo "$value"
    else
        log_debug "Numeric validation failed: '$value' -> using default value: $default_value"
        echo "$default_value"
    fi
}

format_percentage() {
    local value="$1"
    local decimal_places="${2:-1}"

    value=$(validate_numeric_value "$value" "0")

    if (( $(awk "BEGIN {print ($value > 100) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        value="100"
    elif (( $(awk "BEGIN {print ($value < 0) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        value="0"
    fi

    printf "%.${decimal_places}f" "$value" 2>/dev/null || echo "$value"
}

sanitize_process_name() {
    local process_name="$1"

    process_name=$(echo "$process_name" | tr -d '",' | tr -s ' ' | head -c 50)

    if [[ -z "$process_name" ]]; then
        process_name="unknown"
    fi

    echo "$process_name"
}

cleanup_monitor_processes() {
    log_info "🧹 Cleaning up monitoring processes and resources..."

    local job_count=$(jobs -p | wc -l)
    if [[ $job_count -gt 0 ]]; then
        log_debug "Terminating $job_count background jobs"
        jobs -p | xargs -r kill 2>/dev/null || true
    fi

    if [[ -n "${UNIFIED_LOG:-}" ]] && [[ -f "$UNIFIED_LOG" ]]; then
        local file_size
        file_size=$(du -h "$UNIFIED_LOG" 2>/dev/null | cut -f1 || echo "unknown")
        log_info "📊 Monitoring data saved: $UNIFIED_LOG (size: $file_size)"
    fi

    if [[ -n "${MEMORY_SHARE_DIR:-}" ]] && [[ -d "$MEMORY_SHARE_DIR" ]]; then
        log_debug "Cleaning up shared memory monitoring files"
        rm -f "${LATEST_METRICS_FILE:-${MEMORY_SHARE_DIR}/latest_metrics.json}" 2>/dev/null || true
        rm -f "${UNIFIED_METRICS_FILE:-${MEMORY_SHARE_DIR}/unified_metrics.json}" 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/sample_count 2>/dev/null || true
    fi

    local cache_hits=0
    for cmd in "${!COMMAND_CACHE[@]}"; do
        [[ "${COMMAND_CACHE[$cmd]}" == "1" ]] && cache_hits=$((cache_hits + 1))
    done
    log_info "📈 Cache statistics: command cache ${cache_hits}/${#COMMAND_CACHE[@]} hits"
}

get_cached_total_memory() {
    if [[ -z "${SYSTEM_TOTAL_MEMORY_MB:-}" ]]; then
        SYSTEM_TOTAL_MEMORY_MB=$(free -m | awk 'NR==2{print $2}' 2>/dev/null || echo "8192")
        export SYSTEM_TOTAL_MEMORY_MB
        log_debug "Cached system total memory: ${SYSTEM_TOTAL_MEMORY_MB}MB"
    fi
    echo "$SYSTEM_TOTAL_MEMORY_MB"
}

calculate_memory_percentage() {
    local memory_usage_mb="$1"
    local total_memory_mb="$2"

    if [[ "$total_memory_mb" -eq 0 ]]; then
        echo "0"
        return
    fi

    awk "BEGIN {printf \"%.2f\", $memory_usage_mb * 100 / $total_memory_mb}" 2>/dev/null || echo "0"
}

basic_config_check() {
    local errors=()

    [[ -z "$LEDGER_DEVICE" ]] && errors+=("LEDGER_DEVICE not configured")
    [[ -z "$DATA_VOL_MAX_IOPS" ]] && errors+=("DATA_VOL_MAX_IOPS not configured")
    [[ -z "$DATA_VOL_MAX_THROUGHPUT" ]] && errors+=("DATA_VOL_MAX_THROUGHPUT not configured")
    [[ -z "$OVERHEAD_CSV_HEADER" ]] && errors+=("OVERHEAD_CSV_HEADER not configured")

    if [[ ${#errors[@]} -gt 0 ]]; then
        echo "❌ Configuration validation failed:" >&2
        printf '  - %s\n' "${errors[@]}" >&2
        return 1
    fi

    echo "✅ Basic configuration validation passed"

    validate_disk_thresholds
}

validate_disk_thresholds() {
    local errors=()

    if [[ -n "${BOTTLENECK_DISK_IOPS_THRESHOLD:-}" ]]; then
        if ! [[ "$BOTTLENECK_DISK_IOPS_THRESHOLD" =~ ^[0-9]+$ ]] || [[ "$BOTTLENECK_DISK_IOPS_THRESHOLD" -lt 50 ]] || [[ "$BOTTLENECK_DISK_IOPS_THRESHOLD" -gt 100 ]]; then
            errors+=("BOTTLENECK_DISK_IOPS_THRESHOLD value invalid: $BOTTLENECK_DISK_IOPS_THRESHOLD (should be 50-100)")
        fi
    fi

    if [[ -n "${BOTTLENECK_DISK_THROUGHPUT_THRESHOLD:-}" ]]; then
        if ! [[ "$BOTTLENECK_DISK_THROUGHPUT_THRESHOLD" =~ ^[0-9]+$ ]] || [[ "$BOTTLENECK_DISK_THROUGHPUT_THRESHOLD" -lt 50 ]] || [[ "$BOTTLENECK_DISK_THROUGHPUT_THRESHOLD" -gt 100 ]]; then
            errors+=("BOTTLENECK_DISK_THROUGHPUT_THRESHOLD value invalid: $BOTTLENECK_DISK_THROUGHPUT_THRESHOLD (should be 50-100)")
        fi
    fi

    if [[ -n "${BOTTLENECK_MEMORY_THRESHOLD:-}" ]]; then
        if ! [[ "$BOTTLENECK_MEMORY_THRESHOLD" =~ ^[0-9]+$ ]] || [[ "$BOTTLENECK_MEMORY_THRESHOLD" -lt 70 ]] || [[ "$BOTTLENECK_MEMORY_THRESHOLD" -gt 95 ]]; then
            errors+=("BOTTLENECK_MEMORY_THRESHOLD value invalid: $BOTTLENECK_MEMORY_THRESHOLD (should be 70-95)")
        fi
    fi

    if [[ ${#errors[@]} -gt 0 ]]; then
        echo "❌ Disk threshold configuration validation failed:" >&2
        printf '  - %s\n' "${errors[@]}" >&2
        return 1
    fi

    echo "✅ Disk threshold configuration validation passed"
    return 0
}

safe_write_csv() {
    local csv_file="$1"
    local csv_data="$2"
    local lock_file="${csv_file}.lock"
    local max_wait=30
    local wait_count=0

    if [[ -z "$csv_file" || -z "$csv_data" ]]; then
        echo "ERROR: safe_write_csv: Missing required parameters" >&2
        return 1
    fi

    while [[ -f "$lock_file" && $wait_count -lt $max_wait ]]; do
        sleep 0.1
        ((wait_count+=1))
    done

    if [[ $wait_count -ge $max_wait ]]; then
        local lock_pid
        lock_pid=$(cat "$lock_file" 2>/dev/null)
        if [[ -n "$lock_pid" ]] && ! kill -0 "$lock_pid" 2>/dev/null; then
            echo "WARNING: Zombie lock file detected, force deleting: $lock_file (PID: $lock_pid)" >&2
            rm -f "$lock_file"
        else
            echo "WARNING: CSV write lock timeout, force deleting lock file: $lock_file" >&2
            rm -f "$lock_file"
        fi
    fi

    echo $$ > "$lock_file"

    {
        echo "$csv_data" >> "$csv_file"
    } 2>/dev/null

    local write_result=$?
    rm -f "$lock_file"

    if [[ $write_result -eq 0 ]]; then
        return 0
    fi

    echo "ERROR: CSV write failed: $csv_file" >&2
    return 1
}
