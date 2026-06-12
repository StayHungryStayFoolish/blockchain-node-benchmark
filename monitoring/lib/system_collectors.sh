#!/usr/bin/env bash
# =====================================================================
# System Collectors for Unified Monitor
# =====================================================================
# CPU, memory, network, ENA allowance, and coarse system resource collectors.
# These functions intentionally keep the original unified_monitor.sh contracts:
# each function prints a comma-separated field group and fails soft with zeros.
# =====================================================================

get_cpu_data() {
    log_debug "🔍 Collecting CPU performance data..."

    if is_command_available "mpstat"; then
        local mpstat_output
        mpstat_output=$(mpstat 1 1 2>/dev/null)

        if [[ -n "$mpstat_output" ]]; then
            log_debug "✅ mpstat command executed successfully, parsing CPU data"
            local avg_line
            avg_line=$(echo "$mpstat_output" | grep "Average.*all" | tail -1)
            if [[ -n "$avg_line" ]]; then
                local fields=($avg_line)
                local start_idx=2

                if [[ "${fields[0]}" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2}$ ]]; then
                    start_idx=2
                    log_debug "Detected timestamp format mpstat output"
                elif [[ "${fields[0]}" == "Average" ]]; then
                    start_idx=2
                    log_debug "Detected Average format mpstat output"
                else
                    for i in "${!fields[@]}"; do
                        if [[ "${fields[$i]}" == "all" ]]; then
                            start_idx=$((i + 1))
                            log_debug "Found 'all' field at position $i, start index set to $start_idx"
                            break
                        fi
                    done
                fi

                local cpu_usr
                local cpu_sys
                local cpu_iowait
                local cpu_soft
                local cpu_idle
                local cpu_usage

                cpu_usr=$(validate_numeric_value "${fields[$start_idx]:-0}")
                cpu_sys=$(validate_numeric_value "${fields[$((start_idx + 2))]:-0}")
                cpu_iowait=$(validate_numeric_value "${fields[$((start_idx + 3))]:-0}")
                cpu_soft=$(validate_numeric_value "${fields[$((start_idx + 5))]:-0}")
                cpu_idle=$(validate_numeric_value "${fields[$((start_idx + 9))]:-0}")
                cpu_usage=$(awk "BEGIN {printf \"%.2f\", 100 - $cpu_idle}" 2>/dev/null || echo "0")
                cpu_usage=$(validate_numeric_value "$cpu_usage")

                log_debug "📊 CPU metrics parsed successfully: usage=${cpu_usage}%, user=${cpu_usr}%, system=${cpu_sys}%, IO wait=${cpu_iowait}%, soft IRQ=${cpu_soft}%, idle=${cpu_idle}%"
                echo "$cpu_usage,$cpu_usr,$cpu_sys,$cpu_iowait,$cpu_soft,$cpu_idle"
                return
            fi
            log_warn "⚠️ CPU statistics line not found in mpstat output"
        else
            log_warn "⚠️ mpstat command execution failed or no output"
        fi
    fi

    log_warn "🔄 CPU data acquisition failed, using default values"
    echo "0,0,0,0,0,100"
}

get_memory_data() {
    log_debug "🔍 Collecting memory usage data..."

    if is_command_available "free"; then
        local mem_info
        mem_info=$(free -m 2>/dev/null)
        if [[ -n "$mem_info" ]]; then
            log_debug "✅ free command executed successfully, parsing memory data"
            local mem_line
            mem_line=$(echo "$mem_info" | grep "^Mem:")
            if [[ -n "$mem_line" ]]; then
                local mem_used
                local mem_total
                local mem_usage="0"

                mem_used=$(echo "$mem_line" | awk '{print $3}' 2>/dev/null || echo "0")
                mem_total=$(echo "$mem_line" | awk '{print $2}' 2>/dev/null || echo "1")
                mem_used=$(validate_numeric_value "$mem_used")
                mem_total=$(validate_numeric_value "$mem_total" "1")

                if [[ "$mem_total" != "0" ]]; then
                    mem_usage=$(awk "BEGIN {printf \"%.2f\", $mem_used * 100 / $mem_total}" 2>/dev/null || echo "0")
                    mem_usage=$(format_percentage "$mem_usage" 2)
                fi

                log_debug "📊 Memory data: used=${mem_used}MB, total=${mem_total}MB, usage=${mem_usage}%"
                echo "$mem_used,$mem_total,$mem_usage"
                return
            fi
            log_warn "⚠️ free command output format abnormal"
        else
            log_warn "⚠️ free command execution failed"
        fi
    fi

    if [[ -r "/proc/meminfo" ]]; then
        local mem_total_kb
        local mem_free_kb
        local mem_available_kb
        mem_total_kb=$(grep "^MemTotal:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "1")
        mem_free_kb=$(grep "^MemFree:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
        mem_available_kb=$(grep "^MemAvailable:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "$mem_free_kb")

        if [[ "$mem_total_kb" -gt 0 ]]; then
            local mem_total_mb=$((mem_total_kb / 1024))
            local mem_used_mb=$(((mem_total_kb - mem_available_kb) / 1024))
            local mem_usage
            mem_usage=$(awk "BEGIN {printf \"%.2f\", $mem_used_mb * 100 / $mem_total_mb}" 2>/dev/null || echo "0")
            echo "$mem_used_mb,$mem_total_mb,$mem_usage"
            return
        fi
    fi

    echo "0,0,0"
}

get_network_data() {
    if [[ -z "$NETWORK_INTERFACE" ]]; then
        echo "unknown,0,0,0,0,0,0,0,0,0"
        return
    fi

    if is_command_available "sar"; then
        local sar_output
        sar_output=$(sar -n DEV 1 1 2>/dev/null | grep "$NETWORK_INTERFACE" | tail -1)

        if [[ -n "$sar_output" ]]; then
            local fields=($sar_output)
            local start_idx=1

            if [[ "${fields[0]}" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2}$ ]]; then
                start_idx=1
            else
                for i in "${!fields[@]}"; do
                    if [[ "${fields[$i]}" == "$NETWORK_INTERFACE" ]]; then
                        start_idx=$i
                        break
                    fi
                done
            fi

            if [[ "${fields[$start_idx]}" != "$NETWORK_INTERFACE" ]]; then
                echo "$NETWORK_INTERFACE,0,0,0,0,0,0,0,0,0"
                return
            fi

            local rx_pps=${fields[$((start_idx + 1))]:-0}
            local tx_pps=${fields[$((start_idx + 2))]:-0}
            local rx_kbs=${fields[$((start_idx + 3))]:-0}
            local tx_kbs=${fields[$((start_idx + 4))]:-0}
            local rx_mbps
            local tx_mbps
            local total_mbps
            local rx_gbps
            local tx_gbps
            local total_gbps
            local total_pps

            rx_mbps=$(awk "BEGIN {printf \"%.3f\", $rx_kbs * 8 / 1000}" 2>/dev/null || echo "0")
            tx_mbps=$(awk "BEGIN {printf \"%.3f\", $tx_kbs * 8 / 1000}" 2>/dev/null || echo "0")
            total_mbps=$(awk "BEGIN {printf \"%.3f\", $rx_mbps + $tx_mbps}" 2>/dev/null || echo "0")
            rx_gbps=$(awk "BEGIN {printf \"%.6f\", $rx_mbps / 1000}" 2>/dev/null || echo "0")
            tx_gbps=$(awk "BEGIN {printf \"%.6f\", $tx_mbps / 1000}" 2>/dev/null || echo "0")
            total_gbps=$(awk "BEGIN {printf \"%.6f\", $total_mbps / 1000}" 2>/dev/null || echo "0")
            total_pps=$(awk "BEGIN {printf \"%.0f\", $rx_pps + $tx_pps}" 2>/dev/null || echo "0")

            echo "$NETWORK_INTERFACE,$rx_mbps,$tx_mbps,$total_mbps,$rx_gbps,$tx_gbps,$total_gbps,$rx_pps,$tx_pps,$total_pps"
            return
        fi
    fi

    if [[ -r "/proc/net/dev" ]]; then
        local net_stats
        net_stats=$(grep "$NETWORK_INTERFACE:" /proc/net/dev 2>/dev/null | head -1)
        if [[ -n "$net_stats" ]]; then
            echo "$NETWORK_INTERFACE,0,0,0,0,0,0,0,0,0"
            return
        fi
    fi

    echo "$NETWORK_INTERFACE,0,0,0,0,0,0,0,0,0"
}

get_ena_allowance_data() {
    local field_count
    field_count=$(echo "${ENA_ALLOWANCE_FIELDS_STR:-}" | wc -w | tr -d ' ')

    if [[ "${ENA_MONITOR_ENABLED:-false}" != "true" ]]; then
        build_zero_csv_fields "$field_count"
        return
    fi

    if ! is_command_available "ethtool"; then
        build_zero_csv_fields "$field_count"
        return
    fi

    local ethtool_output
    local ena_values=""
    local ena_fields
    ethtool_output=$(ethtool -S "$NETWORK_INTERFACE" 2>/dev/null || echo "")
    ena_fields=($ENA_ALLOWANCE_FIELDS_STR)

    for field in "${ena_fields[@]}"; do
        local value
        value=$(echo "$ethtool_output" | grep "$field:" | awk '{print $2}' || echo "0")
        if [[ ! "$value" =~ ^[0-9]+$ ]]; then
            log_debug "ENA field $field data abnormal: '$value', using default value 0"
            value="0"
        fi
        if [[ -n "$ena_values" ]]; then
            ena_values="$ena_values,$value"
        else
            ena_values="$value"
        fi
    done

    echo "$ena_values"
}

get_system_static_resources() {
    local cpu_cores
    if command -v nproc >/dev/null 2>&1; then
        cpu_cores=$(nproc 2>/dev/null)
    elif [[ -r "/proc/cpuinfo" ]]; then
        cpu_cores=$(grep -c "^processor" /proc/cpuinfo 2>/dev/null)
    else
        cpu_cores="1"
    fi
    cpu_cores=$(echo "$cpu_cores" | grep -o '^[0-9]\+' | head -c 10)
    cpu_cores="${cpu_cores:-1}"

    local memory_gb="0.00"
    if command -v free >/dev/null 2>&1; then
        local memory_kb
        memory_kb=$(free | awk '/^Mem:/{print $2}' 2>/dev/null)
        if [[ "$memory_kb" =~ ^[0-9]+$ ]] && [[ "$memory_kb" -gt 0 ]]; then
            memory_gb=$(awk "BEGIN {printf \"%.2f\", $memory_kb/1024/1024}")
        fi
    fi

    local disk_gb="0.00"
    if command -v df >/dev/null 2>&1; then
        disk_gb=$(df / 2>/dev/null | awk 'NR==2{printf "%.2f", $2/1024/1024}')
        if [[ ! "$disk_gb" =~ ^[0-9]+\.[0-9]+$ ]]; then
            disk_gb="0.00"
        fi
    fi

    log_debug "System static resources: CPU=${cpu_cores} cores, Memory=${memory_gb}GB, Disk=${disk_gb}GB (direct acquisition)"
    echo "${cpu_cores},${memory_gb},${disk_gb}"
}

get_system_dynamic_resources() {
    log_debug "Collecting system dynamic resource usage"

    local cpu_usage=0
    if is_command_available "mpstat"; then
        cpu_usage=$(mpstat 1 1 2>/dev/null | awk '/Average:/ && /all/ {print 100-$NF}' | head -1)
        [[ "$cpu_usage" =~ ^[0-9]+\.?[0-9]*$ ]] || cpu_usage=0
    elif [[ -r "/proc/stat" ]]; then
        local cpu_line1
        local cpu_line2
        cpu_line1=$(grep "^cpu " /proc/stat)
        sleep 1
        cpu_line2=$(grep "^cpu " /proc/stat)

        if [[ -n "$cpu_line1" && -n "$cpu_line2" ]]; then
            local cpu1=($cpu_line1)
            local cpu2=($cpu_line2)
            local idle1=${cpu1[4]}
            local idle2=${cpu2[4]}
            local total1=0
            local total2=0

            for i in {1..7}; do
                total1=$((total1 + ${cpu1[i]:-0}))
                total2=$((total2 + ${cpu2[i]:-0}))
            done

            local idle_diff=$((idle2 - idle1))
            local total_diff=$((total2 - total1))

            if [[ $total_diff -gt 0 ]]; then
                cpu_usage=$(awk "BEGIN {printf \"%.1f\", 100 - ($idle_diff * 100 / $total_diff)}" 2>/dev/null || echo "0.0")
            fi
        fi
    elif is_command_available "top"; then
        cpu_usage=$(top -l 2 -n 0 2>/dev/null | grep "CPU usage" | tail -1 | awk '{print $3}' | sed 's/%//' || echo "0.0")
    fi

    local memory_usage=0
    local cached_gb=0
    local buffers_gb=0
    local anon_pages_gb=0
    local mapped_gb=0
    local shmem_gb=0

    if is_command_available "free"; then
        memory_usage=$(free 2>/dev/null | awk '/^Mem:/{printf "%.1f", $3/$2*100}' || echo "0.0")
    fi

    if [[ -r "/proc/meminfo" ]]; then
        local mem_available_kb
        local cached_kb
        local buffers_kb
        local anon_pages_kb
        local mapped_kb
        local shmem_kb
        mem_available_kb=$(grep "^MemAvailable:" /proc/meminfo | awk '{print $2}' 2>/dev/null)
        cached_kb=$(grep "^Cached:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
        buffers_kb=$(grep "^Buffers:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
        anon_pages_kb=$(grep "^AnonPages:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
        mapped_kb=$(grep "^Mapped:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
        shmem_kb=$(grep "^Shmem:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")

        cached_gb=$(awk "BEGIN {printf \"%.2f\", ${cached_kb}/1024/1024}" 2>/dev/null || echo "0.00")
        buffers_gb=$(awk "BEGIN {printf \"%.2f\", ${buffers_kb}/1024/1024}" 2>/dev/null || echo "0.00")
        anon_pages_gb=$(awk "BEGIN {printf \"%.2f\", ${anon_pages_kb}/1024/1024}" 2>/dev/null || echo "0.00")
        mapped_gb=$(awk "BEGIN {printf \"%.2f\", ${mapped_kb}/1024/1024}" 2>/dev/null || echo "0.00")
        shmem_gb=$(awk "BEGIN {printf \"%.2f\", ${shmem_kb}/1024/1024}" 2>/dev/null || echo "0.00")

        if [[ -z "$mem_available_kb" ]]; then
            local mem_free_kb
            local mem_buffers_kb
            local mem_cached_kb
            mem_free_kb=$(grep "^MemFree:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
            mem_buffers_kb=$(grep "^Buffers:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
            mem_cached_kb=$(grep "^Cached:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
            mem_available_kb=$((mem_free_kb + mem_buffers_kb + mem_cached_kb))
        fi
    fi

    local disk_usage=0
    if is_command_available "df"; then
        disk_usage=$(df / 2>/dev/null | awk 'NR==2{print $5}' | sed 's/%//' || echo "0")
    fi

    [[ "$cpu_usage" =~ ^[0-9]+\.?[0-9]*$ ]] || cpu_usage=0
    [[ "$memory_usage" =~ ^[0-9]+\.?[0-9]*$ ]] || memory_usage=0
    [[ "$disk_usage" =~ ^[0-9]+$ ]] || disk_usage=0
    [[ "$cached_gb" =~ ^[0-9]+\.?[0-9]*$ ]] || cached_gb=0
    [[ "$buffers_gb" =~ ^[0-9]+\.?[0-9]*$ ]] || buffers_gb=0
    [[ "$anon_pages_gb" =~ ^[0-9]+\.?[0-9]*$ ]] || anon_pages_gb=0
    [[ "$mapped_gb" =~ ^[0-9]+\.?[0-9]*$ ]] || mapped_gb=0
    [[ "$shmem_gb" =~ ^[0-9]+\.?[0-9]*$ ]] || shmem_gb=0

    log_debug "System dynamic resources: CPU=${cpu_usage}%, Memory=${memory_usage}%, Disk=${disk_usage}%, Cache=${cached_gb}GB, AnonPages=${anon_pages_gb}GB"
    echo "${cpu_usage},${memory_usage},${disk_usage},${cached_gb},${buffers_gb},${anon_pages_gb},${mapped_gb},${shmem_gb}"
}
