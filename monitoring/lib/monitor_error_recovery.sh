#!/usr/bin/env bash
# =====================================================================
# Monitor Error Recovery for Unified Monitor
# =====================================================================
# Error counters, recovery handlers, safe execution wrapper, and recovery report.
# =====================================================================

declare -A ERROR_COUNTERS
declare -A LAST_ERROR_TIME
declare -A RECOVERY_ATTEMPTS

handle_function_error() {
    local function_name="$1"
    local error_code="$2"
    local error_message="$3"
    local timestamp
    timestamp=$(get_unified_timestamp)

    ERROR_COUNTERS["$function_name"]=$((${ERROR_COUNTERS["$function_name"]:-0} + 1))
    LAST_ERROR_TIME["$function_name"]=$(date +%s)
    log_error_to_file "$function_name" "$error_code" "$error_message" "$timestamp"

    if [[ ${ERROR_COUNTERS["$function_name"]} -ge $MAX_CONSECUTIVE_ERRORS ]]; then
        log_error "🔴 Function $function_name consecutive errors ${ERROR_COUNTERS["$function_name"]} times, initiating error recovery"
        initiate_error_recovery "$function_name"
    else
        log_warn "⚠️  Function $function_name error occurred (${ERROR_COUNTERS["$function_name"]}/$MAX_CONSECUTIVE_ERRORS): $error_message"
    fi
}

log_error_to_file() {
    local function_name="$1"
    local error_code="$2"
    local error_message="$3"
    local timestamp="$4"

    if [[ ! -f "$ERROR_LOG" ]]; then
        echo "timestamp,function_name,error_code,error_message,consecutive_count" > "$ERROR_LOG"
    fi

    safe_write_csv "$ERROR_LOG" "$timestamp,$function_name,$error_code,\"$error_message\",${ERROR_COUNTERS["$function_name"]}"
}

initiate_error_recovery() {
    local function_name="$1"

    RECOVERY_ATTEMPTS["$function_name"]=$((${RECOVERY_ATTEMPTS["$function_name"]:-0} + 1))
    log_error "🔧 Starting error recovery: $function_name (attempt ${RECOVERY_ATTEMPTS["$function_name"]})"

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

    log_info "⏳ Error recovery delay ${ERROR_RECOVERY_DELAY}s..."
    sleep "$ERROR_RECOVERY_DELAY"
    ERROR_COUNTERS["$function_name"]=0
    log_info "✅ Error recovery completed: $function_name"
}

recover_process_discovery() {
    log_info "🔧 Recovering process discovery function..."

    if [[ -z "${MONITORING_PROCESS_NAMES_STR:-}" ]]; then
        log_warn "Monitoring process name configuration is empty, using default configuration"
        export MONITORING_PROCESS_NAMES_STR="iostat mpstat sar vmstat netstat unified_monitor bottleneck_detector network_monitor block_height_monitor performance_visualizer overhead_monitor adaptive_frequency error_recovery report_generator"
    fi

    if ! is_command_available "pgrep"; then
        log_error "pgrep command not available, trying to use ps command as alternative"
    fi

    log_info "Cleaning up zombie processes..."
    pkill -f "defunct" 2>/dev/null || true
}

recover_resource_calculation() {
    log_info "🔧 Recovering resource calculation function..."

    if ! is_command_available "ps"; then
        log_error "ps command not available, this is a serious issue"
        return 1
    fi

    rm -f "${TMP_DIR:-/tmp}"/ps_output_* 2>/dev/null || true
}

recover_overhead_collection() {
    log_info "🔧 Recovering monitoring overhead collection function..."

    if [[ ! -w "$LOGS_DIR" ]]; then
        log_error "Log directory not writable: $LOGS_DIR"
        mkdir -p "$LOGS_DIR" 2>/dev/null || true
        chmod 755 "$LOGS_DIR" 2>/dev/null || true
    fi

    if [[ -f "$MONITORING_OVERHEAD_LOG" ]] && [[ ! -w "$MONITORING_OVERHEAD_LOG" ]]; then
        log_warn "Monitoring overhead log file not writable, trying to fix permissions"
        chmod 644 "$MONITORING_OVERHEAD_LOG" 2>/dev/null || true
    fi

    log_info "Reinitializing monitoring overhead collection components..."
}

recover_system_load_assessment() {
    log_info "🔧 Recovering system load assessment function..."

    local available_commands=()
    if is_command_available "mpstat"; then
        available_commands+=("mpstat")
    fi
    if is_command_available "top"; then
        available_commands+=("top")
    fi
    if is_command_available "free"; then
        available_commands+=("free")
    fi

    if [[ ${#available_commands[@]} -eq 0 ]]; then
        log_error "No available system monitoring commands, system load assessment will use default values"
        return 1
    fi

    log_info "Available system monitoring commands: ${available_commands[*]}"
}

generic_error_recovery() {
    local function_name="$1"

    log_info "🔧 Executing generic error recovery: $function_name"
    find "${TMP_DIR:-/tmp}" -name "*monitoring*" -mtime +1 -delete 2>/dev/null || true

    local available_memory
    local disk_space
    available_memory=$(free -m 2>/dev/null | awk '/^Mem:/ {print $7}' || echo "unknown")
    disk_space=$(df "$LOGS_DIR" 2>/dev/null | awk 'NR==2 {print $4}' || echo "unknown")

    log_info "System status check: available_memory=${available_memory}MB, disk_space=${disk_space}KB"

    if [[ "$disk_space" != "unknown" ]] && [[ $disk_space -lt 1048576 ]]; then
        log_warn "Insufficient disk space, cleaning up old log files..."
        find "$LOGS_DIR" -name "*.log" -mtime +7 -delete 2>/dev/null || true
        find "$LOGS_DIR" -name "*.csv" -mtime +3 -delete 2>/dev/null || true
    fi
}

generate_error_recovery_suggestions() {
    local function_name="$1"
    local error_count="${ERROR_COUNTERS["$function_name"]:-0}"
    local recovery_count="${RECOVERY_ATTEMPTS["$function_name"]:-0}"

    log_info "📋 Error recovery suggestions - $function_name:"
    log_info "  Error count: $error_count"
    log_info "  Recovery attempts: $recovery_count"

    if [[ $recovery_count -gt 3 ]]; then
        log_warn "🔴 Multiple recovery failures, recommend taking following actions:"
        log_warn "  1. Check if system resources are sufficient"
        log_warn "  2. Verify related commands and tools are working properly"
        log_warn "  3. Consider restarting monitoring system"
        log_warn "  4. Contact system administrator for in-depth diagnosis"
    elif [[ $error_count -gt 10 ]]; then
        log_warn "🟡 Frequent errors, recommend:"
        log_warn "  1. Check if configuration parameters are reasonable"
        log_warn "  2. Adjust monitoring frequency"
        log_warn "  3. View detailed error log: $ERROR_LOG"
    else
        log_info "🟢 Error situation is within controllable range"
        log_info "  Suggestion: Continue monitoring, check error log periodically"
    fi
}

safe_execute() {
    local function_name="$1"
    shift
    local function_args=("$@")
    local result
    local error_code=0

    if ! declare -f "$function_name" >/dev/null 2>&1; then
        handle_function_error "$function_name" "FUNCTION_NOT_FOUND" "Function does not exist"
        return 1
    fi

    if result=$("$function_name" "${function_args[@]}" 2>&1); then
        if [[ ${ERROR_COUNTERS["$function_name"]:-0} -gt 0 ]]; then
            log_info "✅ Function $function_name recovered to normal"
            ERROR_COUNTERS["$function_name"]=0
        fi
        echo "$result"
        return 0
    else
        error_code=$?
        handle_function_error "$function_name" "$error_code" "$result"
        return "$error_code"
    fi
}

generate_error_recovery_report() {
    local report_file="${LOGS_DIR}/error_recovery_report_${SESSION_TIMESTAMP}.txt"
    local nounset_was_enabled=false
    local error_counter_keys=()
    local recovery_attempt_keys=()

    if [[ "$-" == *u* ]]; then
        nounset_was_enabled=true
        set +u
    fi
    error_counter_keys=("${!ERROR_COUNTERS[@]}")
    recovery_attempt_keys=("${!RECOVERY_ATTEMPTS[@]}")
    if [[ "$nounset_was_enabled" == "true" ]]; then
        set -u
    fi

    log_info "Generating error recovery report: $report_file"

    {
        echo "# Monitoring System Error Recovery Report"
        echo "Generated: $(date)"
        echo "Error log: $ERROR_LOG"
        echo ""
        echo "## Error Statistics"
        if [[ ${#error_counter_keys[@]} -gt 0 ]]; then
            for func_name in "${error_counter_keys[@]}"; do
                echo "- $func_name: ${ERROR_COUNTERS[$func_name]} errors"
            done
        else
            echo "- No error records"
        fi
        echo ""
        echo "## Recovery Attempt Statistics"
        if [[ ${#recovery_attempt_keys[@]} -gt 0 ]]; then
            for func_name in "${recovery_attempt_keys[@]}"; do
                echo "- $func_name: ${RECOVERY_ATTEMPTS[$func_name]} recovery attempts"
            done
        else
            echo "- No recovery attempt records"
        fi
        echo ""
        echo "## System Status"
        echo "- Status: Extreme test mode, health check disabled"
        echo "- Note: High resource usage is normal during extreme testing"
        echo ""
        echo "## Configuration Parameters"
        echo "- ERROR_RECOVERY_ENABLED: $ERROR_RECOVERY_ENABLED"
        echo "- MAX_CONSECUTIVE_ERRORS: $MAX_CONSECUTIVE_ERRORS"
        echo "- ERROR_RECOVERY_DELAY: ${ERROR_RECOVERY_DELAY}s"
        echo "- PERFORMANCE_MONITORING_ENABLED: $PERFORMANCE_MONITORING_ENABLED"
    } > "$report_file"

    log_info "Error recovery report generated: $report_file"
}
