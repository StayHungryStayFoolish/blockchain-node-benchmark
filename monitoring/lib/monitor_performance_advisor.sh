#!/bin/bash
# Monitoring performance impact and advisor helpers.

monitor_performance_impact() {
    local function_name="$1"
    local start_time="$2"
    local end_time="$3"
    local cpu_usage="$4"
    local memory_usage="$5"

    if [[ "$PERFORMANCE_MONITORING_ENABLED" != "true" ]]; then
        return 0
    fi

    local execution_time_ms=$(( (end_time - start_time) ))
    local warnings=()

    if (( execution_time_ms > MAX_COLLECTION_TIME_MS )); then
        warnings+=("Execution time exceeded: ${execution_time_ms}ms > ${MAX_COLLECTION_TIME_MS}ms")
    fi

    if (( $(awk "BEGIN {print ($cpu_usage > $BOTTLENECK_CPU_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        warnings+=("CPU usage exceeded: ${cpu_usage}% > ${BOTTLENECK_CPU_THRESHOLD}%")
    fi

    local total_memory_mb
    local memory_usage_percent
    total_memory_mb=$(get_cached_total_memory)
    memory_usage_percent=$(calculate_memory_percentage "$memory_usage" "$total_memory_mb")

    if (( $(awk "BEGIN {print ($memory_usage_percent > $BOTTLENECK_MEMORY_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        warnings+=("Memory usage exceeded: ${memory_usage}MB (${memory_usage_percent}%) > ${BOTTLENECK_MEMORY_THRESHOLD}%")
    fi

    local timestamp
    local performance_entry
    timestamp=$(get_unified_timestamp)
    performance_entry="${timestamp},${function_name},${execution_time_ms},${cpu_usage},${memory_usage}"

    if [[ ! -s "$PERFORMANCE_LOG" ]]; then
        echo "timestamp,function_name,execution_time_ms,cpu_percent,memory_mb" > "$PERFORMANCE_LOG"
    fi

    if echo "$performance_entry" >> "$PERFORMANCE_LOG"; then
        :
    else
        echo "ERROR: Performance log write failed: $PERFORMANCE_LOG" >&2
    fi

    if [[ ${#warnings[@]} -gt 0 ]]; then
        local component="unified_monitor"
        local component_log="${LOGS_DIR}/unified_monitor.log"

        if [[ -n "$component_log" ]]; then
            timestamp=$(date '+%Y-%m-%d %H:%M:%S')
            echo "[$timestamp] [WARN] [$component] Monitoring performance warning - Function: $function_name" >> "$component_log"
            for warning in "${warnings[@]}"; do
                echo "[$timestamp] [WARN] [$component]   - $warning" >> "$component_log"
            done

            echo "[$timestamp] [INFO] [$component] 🔧 Performance optimization suggestions - $function_name:" >> "$component_log"
            echo "[$timestamp] [INFO] [$component]   💡 Suggestion: Consider increasing MONITOR_INTERVAL or optimizing data collection logic" >> "$component_log"
            echo "[$timestamp] [INFO] [$component]   📊 View detailed performance data: $PERFORMANCE_LOG" >> "$component_log"
        fi
    fi

    log_debug "Performance monitoring: $function_name execution_time=${execution_time_ms}ms CPU=${cpu_usage}% Memory=${memory_usage}MB"
}

generate_performance_optimization_suggestions() {
    local function_name="$1"
    shift
    local warnings=("$@")

    log_info "🔧 Performance optimization suggestions - $function_name:"

    for warning in "${warnings[@]}"; do
        if [[ "$warning" == *"Execution time exceeded"* ]]; then
            log_info "  💡 Suggestion: Consider increasing MONITOR_INTERVAL or optimizing data collection logic"
        elif [[ "$warning" == *"CPU usage exceeded"* ]]; then
            log_info "  💡 Suggestion: Reduce number of monitoring processes or lower monitoring frequency"
        elif [[ "$warning" == *"Memory usage exceeded"* ]]; then
            log_info "  💡 Suggestion: Optimize data structures or add memory cleanup logic"
        fi
    done

    log_info "  📊 View detailed performance data: $PERFORMANCE_LOG"
}

generate_performance_impact_report() {
    local report_file="${LOGS_DIR}/monitoring_performance_report_${SESSION_TIMESTAMP}.txt"

    if [[ ! -f "$PERFORMANCE_LOG" ]]; then
        log_warn "Performance log file does not exist, cannot generate report: $PERFORMANCE_LOG"
        return 1
    fi

    log_info "Generating performance impact report: $report_file"

    {
        echo "# Monitoring System Performance Impact Report"
        echo "Generated: $(date)"
        echo "Data source: $PERFORMANCE_LOG"
        echo ""

        echo "## Overall Performance Statistics"
        local total_records
        total_records=$(tail -n +2 "$PERFORMANCE_LOG" | wc -l)
        echo "Total records: $total_records"

        if [[ $total_records -gt 0 ]]; then
            local avg_time
            local max_time
            local avg_cpu
            local avg_memory
            avg_time=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f3 | awk '{sum+=$1} END {print sum/NR}')
            max_time=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f3 | sort -n | tail -1)
            avg_cpu=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f4 | awk '{sum+=$1} END {print sum/NR}')
            avg_memory=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f5 | awk '{sum+=$1} END {print sum/NR}')

            echo "Average execution time: ${avg_time:-0} ms"
            echo "Maximum execution time: ${max_time:-0} ms"
            echo "Average CPU usage: ${avg_cpu:-0}%"
            echo "Average memory usage: ${avg_memory:-0} MB"
        fi

        echo ""
        echo "## Statistics Grouped by Function"
        tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f2 | sort | uniq | while read -r func_name; do
            echo "### $func_name"
            local func_data
            local func_count
            local func_avg_time
            local func_max_time
            local func_avg_cpu
            local func_avg_memory
            func_data=$(tail -n +2 "$PERFORMANCE_LOG" | grep ",$func_name,")
            func_count=$(echo "$func_data" | wc -l)
            func_avg_time=$(echo "$func_data" | cut -d',' -f3 | awk '{sum+=$1} END {print sum/NR}')
            func_max_time=$(echo "$func_data" | cut -d',' -f3 | sort -n | tail -1)
            func_avg_cpu=$(echo "$func_data" | cut -d',' -f4 | awk '{sum+=$1} END {print sum/NR}')
            func_avg_memory=$(echo "$func_data" | cut -d',' -f5 | awk '{sum+=$1} END {print sum/NR}')

            echo "- Call count: $func_count"
            echo "- Average execution time: ${func_avg_time:-0} ms"
            echo "- Maximum execution time: ${func_max_time:-0} ms"
            echo "- Average CPU usage: ${func_avg_cpu:-0}%"
            echo "- Average memory usage: ${func_avg_memory:-0} MB"
            echo ""
        done

        echo "## Performance Warning Analysis"
        local total_memory_mb
        local memory_threshold_mb
        local warning_count
        total_memory_mb=$(get_cached_total_memory)
        memory_threshold_mb=$(awk "BEGIN {printf \"%.0f\", $total_memory_mb * $BOTTLENECK_MEMORY_THRESHOLD / 100}")

        warning_count=$(tail -n +2 "$PERFORMANCE_LOG" | awk -F',' -v max_time="$MAX_COLLECTION_TIME_MS" -v max_cpu="$BOTTLENECK_CPU_THRESHOLD" -v max_mem="$memory_threshold_mb" '
            $3 > max_time || $4 > max_cpu || $5 > max_mem {count++}
            END {print count+0}')

        echo "Exceeded records: $warning_count / $total_records"
        echo "Memory threshold: ${BOTTLENECK_MEMORY_THRESHOLD}% (${memory_threshold_mb}MB / ${total_memory_mb}MB)"

        if [[ $warning_count -gt 0 ]]; then
            echo ""
            echo "### Exceeded Record Details"
            tail -n +2 "$PERFORMANCE_LOG" | awk -F',' -v max_time="$MAX_COLLECTION_TIME_MS" -v max_cpu="$BOTTLENECK_CPU_THRESHOLD" -v max_mem="$memory_threshold_mb" -v total_mem="$total_memory_mb" '
                $3 > max_time || $4 > max_cpu || $5 > max_mem {
                    mem_percent = ($5 * 100 / total_mem)
                    printf "- %s %s: execution_time=%sms CPU=%s%% memory=%sMB(%.1f%%)\n", $1, $2, $3, $4, $5, mem_percent
                }'
        fi

        echo ""
        echo "## Optimization Suggestions"

        if [[ $warning_count -gt 0 ]]; then
            local warning_ratio
            warning_ratio=$(awk "BEGIN {printf \"%.2f\", $warning_count * 100 / $total_records}")
            echo "- Warning ratio: ${warning_ratio}%"

            if (( $(awk "BEGIN {print ($warning_ratio > 10) ? 1 : 0}") )); then
                echo "- 🔴 High risk: Over 10% of monitoring operations have performance issues"
                echo "  Suggestion: Immediately optimize monitoring frequency or algorithms"
            elif (( $(awk "BEGIN {print ($warning_ratio > 5) ? 1 : 0}") )); then
                echo "- 🟡 Medium risk: 5-10% of monitoring operations have performance issues"
                echo "  Suggestion: Consider optimizing monitoring configuration"
            else
                echo "- 🟢 Low risk: Less than 5% of monitoring operations have performance issues"
                echo "  Suggestion: Continue monitoring, check periodically"
            fi
        else
            echo "- 🟢 Excellent: All monitoring operations are within performance thresholds"
            echo "  Suggestion: Maintain current configuration"
        fi

    } > "$report_file"

    log_info "Performance impact report generated: $report_file"
    return 0
}

auto_performance_optimization_advisor() {
    if [[ ! -f "$PERFORMANCE_LOG" ]]; then
        return 0
    fi

    local total_records
    total_records=$(tail -n +2 "$PERFORMANCE_LOG" | wc -l)

    if [[ $total_records -lt 10 ]]; then
        return 0
    fi

    log_info "🤖 Automatic performance optimization analysis (based on $total_records records)"

    local avg_time
    local max_time
    avg_time=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f3 | awk '{sum+=$1} END {print sum/NR}')
    max_time=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f3 | sort -n | tail -1)

    if (( $(awk "BEGIN {print ($avg_time > $MAX_COLLECTION_TIME_MS * 0.8) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        log_warn "⚠️  Average execution time approaching threshold (${avg_time}ms vs ${MAX_COLLECTION_TIME_MS}ms)"
        log_info "💡 Suggestion: Consider increasing MONITOR_INTERVAL from ${MONITOR_INTERVAL}s to $((MONITOR_INTERVAL * 2))s"
    fi

    local avg_cpu
    avg_cpu=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f4 | awk '{sum+=$1} END {print sum/NR}')

    if (( $(awk "BEGIN {print ($avg_cpu > $BOTTLENECK_CPU_THRESHOLD * 0.8) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        log_warn "⚠️  Average CPU usage approaching threshold (${avg_cpu}% vs ${BOTTLENECK_CPU_THRESHOLD}%)"
        log_info "💡 Suggestion: Reduce number of monitoring processes or optimize process discovery algorithm"
    fi

    local avg_memory
    local total_memory_mb
    local avg_memory_percent
    avg_memory=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f5 | awk '{sum+=$1} END {print sum/NR}')
    total_memory_mb=$(get_cached_total_memory)
    avg_memory_percent=$(calculate_memory_percentage "$avg_memory" "$total_memory_mb")

    if (( $(awk "BEGIN {print ($avg_memory_percent > $BOTTLENECK_MEMORY_THRESHOLD * 0.8) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        log_warn "⚠️  Average memory usage approaching threshold (${avg_memory}MB, ${avg_memory_percent}% vs ${BOTTLENECK_MEMORY_THRESHOLD}%)"
        log_info "💡 Suggestion: Optimize data structures or add memory cleanup logic"
    fi

    local slowest_func
    local slowest_time
    slowest_func=$(tail -n +2 "$PERFORMANCE_LOG" | sort -t',' -k3 -n | tail -1 | cut -d',' -f2)
    slowest_time=$(tail -n +2 "$PERFORMANCE_LOG" | sort -t',' -k3 -n | tail -1 | cut -d',' -f3)

    if [[ -n "$slowest_func" ]] && (( $(awk "BEGIN {print ($slowest_time > $MAX_COLLECTION_TIME_MS) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        log_warn "🐌 Slowest function: $slowest_func (${slowest_time}ms)"

        case "$slowest_func" in
            *"discover_monitoring_processes"*)
                log_info "💡 Suggestion: Optimize process discovery algorithm, consider caching process list"
                ;;
            *"calculate_process_resources"*)
                log_info "💡 Suggestion: Reduce ps command call frequency or optimize resource calculation logic"
                ;;
            *"collect_monitoring_overhead_data"*)
                log_info "💡 Suggestion: Break down data collection steps, consider asynchronous processing"
                ;;
            *)
                log_info "💡 Suggestion: Analyze specific implementation of $slowest_func function"
                ;;
        esac
    fi
}

CURRENT_MONITOR_INTERVAL=${MONITOR_INTERVAL}

assess_system_load() {
    local cpu_usage=0
    local memory_usage=0
    local load_average=0

    if is_command_available "mpstat"; then
        cpu_usage=$(mpstat 1 1 | awk '/Average/ && /all/ {print 100-$NF}' 2>/dev/null || echo "0.0")
    elif is_command_available "top"; then
        cpu_usage=$(top -l 1 -n 0 | grep "CPU usage" | awk '{print $3}' | sed 's/%//' 2>/dev/null || echo "0.0")
    fi

    if is_command_available "free"; then
        memory_usage=$(free | awk '/^Mem:/ {printf "%.1f", $3/$2 * 100}' 2>/dev/null || echo "0.0")
    elif [[ -f /proc/meminfo ]]; then
        local mem_total
        local mem_available
        mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        mem_available=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
        if [[ -n "$mem_total" && -n "$mem_available" ]]; then
            memory_usage=$(awk "BEGIN {printf \"%.1f\", ($mem_total - $mem_available) * 100 / $mem_total}" 2>/dev/null || echo "0.0")
        fi
    fi

    if [[ -f /proc/loadavg ]]; then
        load_average=$(cut -d' ' -f1 /proc/loadavg 2>/dev/null || echo "0.0")
    elif is_command_available "uptime"; then
        load_average=$(uptime | awk -F'load average:' '{print $2}' | awk -F',' '{print $1}' | tr -d ' ' 2>/dev/null || echo "0.0")
    fi

    local cpu_score
    local memory_score
    local cpu_cores
    local load_score
    local system_load
    cpu_score=$(awk "BEGIN {printf \"%.0f\", $cpu_usage}" 2>/dev/null || echo "0")
    memory_score=$(awk "BEGIN {printf \"%.0f\", $memory_usage}" 2>/dev/null || echo "0")
    cpu_cores=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "4")
    load_score=$(awk "BEGIN {printf \"%.0f\", $load_average * 100 / $cpu_cores}" 2>/dev/null || echo "0")

    system_load=$cpu_score
    if (( $(awk "BEGIN {print ($memory_score > $system_load) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        system_load=$memory_score
    fi
    if (( $(awk "BEGIN {print ($load_score > $system_load) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        system_load=$load_score
    fi

    if (( $(awk "BEGIN {print ($system_load < 0) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        system_load=0
    elif (( $(awk "BEGIN {print ($system_load > 100) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        system_load=100
    fi

    log_debug "System load assessment: CPU=${cpu_usage}% Memory=${memory_usage}% Load=${load_average} Comprehensive=${system_load}%"
    echo "$system_load"
}
