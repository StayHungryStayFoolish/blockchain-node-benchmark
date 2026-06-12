#!/usr/bin/env bash
# =====================================================================
# Process Collectors for Unified Monitor
# =====================================================================
# Process discovery and resource aggregation helpers. The functions keep the
# original unified_monitor.sh contracts and only print comma-separated values.
# =====================================================================

discover_monitoring_processes() {
    local start_time
    local pattern=""
    local monitoring_pids
    local end_time
    local current_resources
    local current_cpu
    local current_memory

    start_time=$(date +%s%3N 2>/dev/null || date +%s)
    monitoring_processes=($MONITORING_PROCESS_NAMES_STR)
    pattern=$(IFS='|'; echo "${monitoring_processes[*]}")
    log_debug "Using configured monitoring process name pattern: $pattern"

    monitoring_pids=$(pgrep -f "$pattern" 2>/dev/null | grep -v "^$$\$" | tr '\n' ' ')

    if [[ -n "$monitoring_pids" ]]; then
        log_debug "Found monitoring processes: $monitoring_pids"
    else
        log_debug "No monitoring processes found"
    fi

    end_time=$(date +%s%3N 2>/dev/null || date +%s)
    current_resources=$(get_current_process_resources)
    current_cpu=$(echo "$current_resources" | cut -d',' -f1)
    current_memory=$(echo "$current_resources" | cut -d',' -f2)
    monitor_performance_impact "discover_monitoring_processes" "$start_time" "$end_time" "$current_cpu" "$current_memory"

    echo "$monitoring_pids"
}

discover_blockchain_processes() {
    local pattern=""
    local blockchain_pids

    blockchain_processes=($BLOCKCHAIN_PROCESS_NAMES_STR)
    pattern=$(IFS='|'; echo "${blockchain_processes[*]}")
    log_debug "Using configured blockchain process name pattern: $pattern"

    blockchain_pids=$(pgrep -f "$pattern" 2>/dev/null | tr '\n' ' ')

    if [[ -n "$blockchain_pids" ]]; then
        log_debug "Discovered blockchain processes: $blockchain_pids"
    else
        log_debug "No blockchain processes found"
    fi

    echo "$blockchain_pids"
}

calculate_process_resources() {
    local start_time
    local pids="$1"
    local process_type="${2:-unknown}"
    local proc_stats=""

    start_time=$(date +%s%3N 2>/dev/null || date +%s)

    if [[ -z "$pids" ]]; then
        log_debug "No ${process_type} processes to count"
        echo "0,0,0,0"
        return
    fi

    pids=$(echo "$pids" | tr -s ' ' | sed 's/^ *//;s/ *$//' | tr ' ' ',')

    if is_command_available "ps"; then
        if [[ "$(uname -s)" == "Linux" ]]; then
            proc_stats=$(ps -p $pids -o %cpu,%mem,rss --no-headers 2>/dev/null)
        else
            proc_stats=$(ps -p $pids -o pcpu,pmem,rss 2>/dev/null | tail -n +2)
        fi

        if [[ -z "$proc_stats" ]]; then
            if [[ "$(uname -s)" == "Linux" ]]; then
                proc_stats=$(ps -p $pids -o pcpu,pmem,rss 2>/dev/null | tail -n +2)
            else
                proc_stats=$(ps -p $pids -o %cpu,%mem,rss --no-headers 2>/dev/null)
            fi
        fi
    fi

    if [[ -z "$proc_stats" ]]; then
        log_debug "${process_type} process resource query failed, PID: $pids"
        echo "0,0,0,0"
        return
    fi

    local total_cpu=0 total_memory=0 total_memory_mb=0 count=0

    while read -r cpu mem rss; do
        [[ -n "$cpu" ]] || continue

        if [[ "$cpu" =~ ^[0-9]+\.?[0-9]*$ ]]; then
            total_cpu=$(awk "BEGIN {printf \"%.2f\", $total_cpu + $cpu}" 2>/dev/null || echo "$total_cpu")
        fi

        if [[ "$mem" =~ ^[0-9]+\.?[0-9]*$ ]]; then
            total_memory=$(awk "BEGIN {printf \"%.2f\", $total_memory + $mem}" 2>/dev/null || echo "$total_memory")
        fi

        if [[ "$rss" =~ ^[0-9]+$ ]]; then
            local rss_mb
            rss_mb=$(awk "BEGIN {printf \"%.2f\", $rss / 1024}" 2>/dev/null || echo "0.00")
            total_memory_mb=$(awk "BEGIN {printf \"%.2f\", $total_memory_mb + $rss_mb}" 2>/dev/null || echo "$total_memory_mb")
        fi

        count=$((count + 1))
    done <<< "$proc_stats"

    log_debug "${process_type} process resource statistics: CPU=${total_cpu}%, Memory=${total_memory}%, MemoryMB=${total_memory_mb}, ProcessCount=${count}"

    local end_time
    local current_resources
    local current_cpu
    local current_memory
    end_time=$(date +%s%3N 2>/dev/null || date +%s)
    current_resources=$(get_current_process_resources)
    current_cpu=$(echo "$current_resources" | cut -d',' -f1)
    current_memory=$(echo "$current_resources" | cut -d',' -f2)
    monitor_performance_impact "calculate_process_resources_${process_type}" "$start_time" "$end_time" "$current_cpu" "$current_memory"

    echo "$total_cpu,$total_memory,$total_memory_mb,$count"
}

get_blockchain_node_resources() {
    local blockchain_pids
    local blockchain_resources
    local blockchain_cpu
    local blockchain_memory_percent
    local blockchain_memory_mb
    local process_count

    blockchain_pids=$(discover_blockchain_processes)

    if [[ -z "$blockchain_pids" ]]; then
        log_debug "No blockchain processes found, returning zero resource usage"
        echo "0,0,0,0"
        return
    fi

    blockchain_resources=$(calculate_process_resources "$blockchain_pids" "blockchain")
    blockchain_cpu=$(echo "$blockchain_resources" | cut -d',' -f1)
    blockchain_memory_percent=$(echo "$blockchain_resources" | cut -d',' -f2)
    blockchain_memory_mb=$(echo "$blockchain_resources" | cut -d',' -f3)
    process_count=$(echo "$blockchain_resources" | cut -d',' -f4)

    log_debug "Blockchain node resources: ProcessCount=${process_count}, CPU=${blockchain_cpu}%, Memory=${blockchain_memory_percent}%(${blockchain_memory_mb}MB)"
    echo "$blockchain_cpu,$blockchain_memory_percent,$blockchain_memory_mb,$process_count"
}

get_current_process_resources() {
    local pid=${1:-$$}
    local process_info
    local cpu_percent
    local memory_kb
    local memory_mb

    process_info=$(ps -p "$pid" -o %cpu,%mem,rss --no-headers 2>/dev/null || echo "0.0 0.0 0")
    cpu_percent=$(echo "$process_info" | awk '{print $1}')
    memory_kb=$(echo "$process_info" | awk '{print $3}')
    memory_mb=$(awk "BEGIN {printf \"%.2f\", $memory_kb/1024}" 2>/dev/null || echo "0")

    echo "$cpu_percent,$memory_mb"
}
