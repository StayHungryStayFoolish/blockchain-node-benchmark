#!/usr/bin/env bash
# =====================================================================
# Monitoring Overhead Collector for Unified Monitor
# =====================================================================
# Calculates the monitoring subsystem I/O overhead fields used in the unified
# performance CSV: "overhead_iops,overhead_throughput".
# =====================================================================

declare -A LAST_IO_STATS

cleanup_dead_process_io_stats() {
    local cleaned_count=0

    for key in "${!LAST_IO_STATS[@]}"; do
        local pid
        pid=$(echo "$key" | cut -d'_' -f1)
        if ! kill -0 "$pid" 2>/dev/null; then
            unset LAST_IO_STATS["$key"]
            ((cleaned_count+=1))
        fi
    done

    [[ $cleaned_count -gt 0 ]] && log_debug "Cleaned up $cleaned_count dead process I/O states"
}

get_monitoring_overhead() {
    if [[ "${MONITORING_SELF:-false}" == "true" ]]; then
        echo "0,0"
        return 0
    fi

    export MONITORING_SELF=true
    local result
    result=$(get_monitoring_overhead_legacy)
    unset MONITORING_SELF

    echo "$result"
}

get_monitoring_overhead_legacy() {
    call_count=${call_count:-0}
    ((call_count+=1))
    if (( call_count % 50 == 0 )); then
        cleanup_dead_process_io_stats
    fi

    local monitoring_pids
    monitoring_pids=$(discover_monitoring_processes)

    if [[ -z "$monitoring_pids" ]]; then
        log_debug "No monitoring processes found, returning zero overhead"
        echo "0,0"
        return
    fi

    local monitoring_resources
    local monitoring_cpu
    local monitoring_memory_percent
    local monitoring_memory_mb
    local process_count
    monitoring_resources=$(calculate_process_resources "$monitoring_pids" "monitoring")
    monitoring_cpu=$(echo "$monitoring_resources" | cut -d',' -f1)
    monitoring_memory_percent=$(echo "$monitoring_resources" | cut -d',' -f2)
    monitoring_memory_mb=$(echo "$monitoring_resources" | cut -d',' -f3)
    process_count=$(echo "$monitoring_resources" | cut -d',' -f4)

    local total_read_bytes_diff=0
    local total_write_bytes_diff=0
    local total_read_ops_diff=0
    local total_write_ops_diff=0

    for pid in $monitoring_pids; do
        if [[ -f "/proc/$pid/io" ]]; then
            local io_stats
            io_stats=$(cat "/proc/$pid/io" 2>/dev/null)
            if [[ -n "$io_stats" ]]; then
                local current_read_bytes
                local current_write_bytes
                local current_syscr
                local current_syscw
                current_read_bytes=$(echo "$io_stats" | grep "^read_bytes:" | awk '{print $2}' | tr -d '\n\r\t ' 2>/dev/null)
                current_write_bytes=$(echo "$io_stats" | grep "^write_bytes:" | awk '{print $2}' | tr -d '\n\r\t ' 2>/dev/null)
                current_syscr=$(echo "$io_stats" | grep "^syscr:" | awk '{print $2}' | tr -d '\n\r\t ' 2>/dev/null)
                current_syscw=$(echo "$io_stats" | grep "^syscw:" | awk '{print $2}' | tr -d '\n\r\t ' 2>/dev/null)

                [[ "$current_read_bytes" =~ ^[0-9]+$ ]] || current_read_bytes=0
                [[ "$current_write_bytes" =~ ^[0-9]+$ ]] || current_write_bytes=0
                [[ "$current_syscr" =~ ^[0-9]+$ ]] || current_syscr=0
                [[ "$current_syscw" =~ ^[0-9]+$ ]] || current_syscw=0

                local last_read_bytes=${LAST_IO_STATS["${pid}_read_bytes"]:-$current_read_bytes}
                local last_write_bytes=${LAST_IO_STATS["${pid}_write_bytes"]:-$current_write_bytes}
                local last_syscr=${LAST_IO_STATS["${pid}_syscr"]:-$current_syscr}
                local last_syscw=${LAST_IO_STATS["${pid}_syscw"]:-$current_syscw}

                local read_bytes_diff=$((current_read_bytes - last_read_bytes))
                local write_bytes_diff=$((current_write_bytes - last_write_bytes))
                local syscr_diff=$((current_syscr - last_syscr))
                local syscw_diff=$((current_syscw - last_syscw))

                if [[ $read_bytes_diff -lt 0 ]]; then
                    log_debug "Process $pid read_bytes reset ($last_read_bytes -> $current_read_bytes), possible restart"
                    read_bytes_diff=0
                fi
                if [[ $write_bytes_diff -lt 0 ]]; then
                    log_debug "Process $pid write_bytes reset ($last_write_bytes -> $current_write_bytes), possible restart"
                    write_bytes_diff=0
                fi
                if [[ $syscr_diff -lt 0 ]]; then
                    log_debug "Process $pid syscr reset ($last_syscr -> $current_syscr), possible restart"
                    syscr_diff=0
                fi
                if [[ $syscw_diff -lt 0 ]]; then
                    log_debug "Process $pid syscw reset ($last_syscw -> $current_syscw), possible restart"
                    syscw_diff=0
                fi

                LAST_IO_STATS["${pid}_read_bytes"]=$current_read_bytes
                LAST_IO_STATS["${pid}_write_bytes"]=$current_write_bytes
                LAST_IO_STATS["${pid}_syscr"]=$current_syscr
                LAST_IO_STATS["${pid}_syscw"]=$current_syscw

                total_read_bytes_diff=$((total_read_bytes_diff + read_bytes_diff))
                total_write_bytes_diff=$((total_write_bytes_diff + write_bytes_diff))
                total_read_ops_diff=$((total_read_ops_diff + syscr_diff))
                total_write_ops_diff=$((total_write_ops_diff + syscw_diff))
            fi
        fi
    done

    local real_iops
    local real_throughput
    real_iops=$(awk "BEGIN {printf \"%.4f\", ($total_read_ops_diff + $total_write_ops_diff) / $MONITOR_INTERVAL}" 2>/dev/null || echo "0.0000")
    real_throughput=$(awk "BEGIN {printf \"%.8f\", ($total_read_bytes_diff + $total_write_bytes_diff) / $MONITOR_INTERVAL / 1024 / 1024}" 2>/dev/null || echo "0.00000000")
    real_iops=$(printf "%.4f" "$real_iops" 2>/dev/null || echo "0.0000")
    real_throughput=$(printf "%.8f" "$real_throughput" 2>/dev/null || echo "0.00000000")

    log_debug "Monitoring overhead statistics: ProcessCount=${process_count}, CPU=${monitoring_cpu}%, Memory=${monitoring_memory_percent}%(${monitoring_memory_mb}MB), RealIOPS=${real_iops}, RealThroughput=${real_throughput}MiB/s"
    echo "$real_iops,$real_throughput"
}
