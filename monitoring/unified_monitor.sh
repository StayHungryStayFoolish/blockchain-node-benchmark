#!/bin/bash
# =====================================================================
# Unified Monitor - Unified Time Management (Unified Logger Version)
# =====================================================================
# Single monitoring entry point, avoid multiple scripts calling iostat/mpstat repeatedly
# Unified time format, support complete performance metrics monitoring
# Use unified logger
# =====================================================================

# Strict error handling - but allow safe use in interactive environments
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Use strict mode when script is executed directly
    set -euo pipefail
else
    # Use relaxed mode when sourced to avoid exiting shell
    set -uo pipefail
fi

source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../utils/ebs_converter.sh"

# Initialize unified logger
init_logger "unified_monitor" $LOG_LEVEL "${LOGS_DIR}/unified_monitor.log"

# Error handling function
handle_monitor_error() {
    local exit_code=$?
    local line_number=$1
    log_error "Monitor error occurred at line $line_number , exit code: $exit_code"
    log_warn "Stopping monitoring processes..."
    cleanup_monitor_processes
    exit $exit_code
}

# Set error trap - only enable when script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    trap 'handle_monitor_error $LINENO' ERR
fi

# =====================================================================
# Performance Optimization Module - Cache System
# =====================================================================
# Avoid repeated system calls, improve monitoring performance

# Command availability cache - performance optimization: avoid repeated command -v calls
declare -A COMMAND_CACHE

# Check if command is available (with cache)
# Parameters: $1 - command name
# Returns: 0=available, 1=unavailable
# Note: Result is cached after first check, subsequent calls return cached result directly
is_command_available() {
    local cmd="$1"
    
    # Parameter validation
    if [[ -z "$cmd" ]]; then
        log_error "is_command_available: Command name cannot be empty"
        return 1
    fi
    
    # Check cache - avoid repeated command -v calls
    if [[ -n "${COMMAND_CACHE[$cmd]:-}" ]]; then
        [[ "${COMMAND_CACHE[$cmd]}" == "1" ]]
        return $?
    fi
    
    # Execute check and cache result
    if command -v "$cmd" >/dev/null 2>&1; then
        COMMAND_CACHE[$cmd]="1"
        log_debug "Command available and cached: $cmd"
        return 0
    else
        COMMAND_CACHE[$cmd]="0"
        log_debug "Command unavailable and cached: $cmd"
        return 1
    fi
}

# Initialize command cache
# Note: Pre-check all required commands at monitoring startup, avoid repeated checks at runtime
# Performance impact: one-time overhead at startup, zero overhead at runtime
init_command_cache() {
    # Define all possible system commands
    local commands=(
        "mpstat"    # CPU statistics
        "free"      # Memory statistics  
        "sar"       # Network statistics
        "ethtool"   # Network interface statistics
        "nproc"     # CPU core count
        "sysctl"    # System parameters
        "df"        # Disk usage
        "top"       # Process statistics
        "ps"        # Process information
        "pgrep"     # Process search
        "bc"        # Mathematical calculation
        "uptime"    # System load
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

# =====================================================================
# Data Validation and Utility Functions Module
# =====================================================================

# Validate if numeric value is valid
# Parameters: $1 - value to validate, $2 - default value (optional)
# Returns: valid value or default value
validate_numeric_value() {
    local value="$1"
    local default_value="${2:-0}"
    
    # Check if valid number (supports integers and decimals)
    if [[ "$value" =~ ^[0-9]+\.?[0-9]*$ ]] || [[ "$value" =~ ^[0-9]*\.[0-9]+$ ]]; then
        echo "$value"
    else
        log_debug "Numeric validation failed: '$value' -> using default value: $default_value"
        echo "$default_value"
    fi
}

# Format percentage value
# Parameters: $1 - raw value, $2 - decimal places (default 1)
# Returns: formatted percentage value
format_percentage() {
    local value="$1"
    local decimal_places="${2:-1}"
    
    # Validate input
    value=$(validate_numeric_value "$value" "0")
    
    # Ensure percentage is within 0-100 range
    if (( $(awk "BEGIN {print ($value > 100) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        value="100"
    elif (( $(awk "BEGIN {print ($value < 0) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        value="0"
    fi
    
    # Format output
    printf "%.${decimal_places}f" "$value" 2>/dev/null || echo "$value"
}

# Safe process name sanitization
# Parameters: $1 - raw process name
# Returns: sanitized process name (remove special characters, prevent CSV injection)
sanitize_process_name() {
    local process_name="$1"
    
    # Remove characters that may cause CSV parsing issues
    process_name=$(echo "$process_name" | tr -d '",' | tr -s ' ' | head -c 50)
    
    # If empty, use default value
    if [[ -z "$process_name" ]]; then
        process_name="unknown"
    fi
    
    echo "$process_name"
}

# Monitor process cleanup function
cleanup_monitor_processes() {
    log_info "🧹 Cleaning up monitoring processes and resources..."
    
    # Stop possible background processes
    local job_count=$(jobs -p | wc -l)
    if [[ $job_count -gt 0 ]]; then
        log_debug "Terminating $job_count background jobs"
        jobs -p | xargs -r kill 2>/dev/null || true
    fi
    
    # Clean up temporary files and report save location
    if [[ -n "${UNIFIED_LOG:-}" ]] && [[ -f "$UNIFIED_LOG" ]]; then
        local file_size=$(du -h "$UNIFIED_LOG" 2>/dev/null | cut -f1 || echo "unknown")
        log_info "📊 Monitoring data saved: $UNIFIED_LOG (size: $file_size)"
    fi
    
    # Clean up monitoring files in shared memory
    if [[ -n "${MEMORY_SHARE_DIR:-}" ]] && [[ -d "$MEMORY_SHARE_DIR" ]]; then
        log_debug "Cleaning up shared memory monitoring files"
        rm -f "$MEMORY_SHARE_DIR"/latest_metrics.json 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/unified_metrics.json 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/sample_count 2>/dev/null || true
    fi
    
    # Display cache statistics
    local cache_hits=0
    for cmd in "${!COMMAND_CACHE[@]}"; do
        [[ "${COMMAND_CACHE[$cmd]}" == "1" ]] && cache_hits=$((cache_hits + 1))
    done
    log_info "📈 Cache statistics: command cache ${cache_hits}/${#COMMAND_CACHE[@]} hits"
}

source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh"
source "$(dirname "${BASH_SOURCE[0]}")/iostat_collector.sh"

# Avoid redefining readonly variables - use definitions from config_loader.sh
if [[ -z "${UNIFIED_LOG:-}" ]]; then
    UNIFIED_LOG="${LOGS_DIR}/performance_${SESSION_TIMESTAMP}.csv"
fi

# MONITORING_OVERHEAD_LOG is set in detect_deployment_paths() function in config_loader.sh

# Monitoring overhead CSV header definition - loaded from config_loader.sh
# OVERHEAD_CSV_HEADER is defined in config_loader.sh

MONITOR_PIDS=()
START_TIME=""
END_TIME=""

# I/O status management - for real I/O monitoring
declare -A LAST_IO_STATS

# Clean up I/O status data for exited processes
cleanup_dead_process_io_stats() {
    local cleaned_count=0
    
    for key in "${!LAST_IO_STATS[@]}"; do
        local pid=$(echo "$key" | cut -d'_' -f1)
        if ! kill -0 "$pid" 2>/dev/null; then
            unset LAST_IO_STATS["$key"]
            ((cleaned_count++))
        fi
    done
    
    [[ $cleaned_count -gt 0 ]] && log_debug "Cleaned up $cleaned_count dead process I/O states"
}

# Initialize monitoring environment
init_monitoring() {
    echo "🔧 Initializing unified monitoring environment..."

    # Basic configuration validation
    if ! basic_config_check; then
        echo "❌ Monitoring system startup failed: configuration validation failed" >&2
        return 1
    fi

    # Validate devices
    if ! validate_devices; then
        return 1
    fi

    # Check required commands - gracefully handle missing commands
    local missing_commands=()
    local critical_missing=()

    # Check availability of each command
    for cmd in mpstat iostat sar free; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_commands+=("$cmd")
            # All monitoring commands are critical, missing any will affect functionality
            critical_missing+=("$cmd")
        fi
    done

    if [[ ${#missing_commands[@]} -gt 0 ]]; then
        log_warn "Missing some monitoring commands: ${missing_commands[*]}"
        echo "⚠️  Missing monitoring commands: ${missing_commands[*]}"
        echo "💡 Recommended installation: sudo apt-get install sysstat procps"

        # Fail if critical commands are missing
        if [[ ${#critical_missing[@]} -gt 0 ]]; then
            log_error "Missing critical commands: ${critical_missing[*]}, cannot continue"
            echo "❌ Missing critical commands: ${critical_missing[*]}, monitoring functionality cannot start"
            return 1
        fi
    fi

    log_info "Unified monitoring environment initialization completed"
    return 0
}

# CPU Monitoring - Unified use of mpstat command
# =====================================================================
# Core Data Collection Functions Module
# =====================================================================

# CPU data collector
# Returns: "cpu_usage,cpu_usr,cpu_sys,cpu_iowait,cpu_soft,cpu_idle" format string
# Note: Prefer mpstat for detailed CPU statistics, fallback to /proc/stat
get_cpu_data() {
    log_debug "🔍 Collecting CPU performance data..."
    
    # Prefer mpstat command for CPU metrics - provides most detailed CPU statistics
    if is_command_available "mpstat"; then
        local mpstat_output=$(mpstat 1 1 2>/dev/null)

        if [[ -n "$mpstat_output" ]]; then
            log_debug "✅ mpstat command executed successfully, parsing CPU data"
            
            # Find line containing CPU statistics
            local avg_line=$(echo "$mpstat_output" | grep "Average.*all" | tail -1)
            if [[ -n "$avg_line" ]]; then
                local fields=($avg_line)
                local start_idx=2

                # Intelligently detect field start position - adapt to different mpstat versions
                if [[ "${fields[0]}" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2}$ ]]; then
                    start_idx=2  # Format with timestamp
                    log_debug "Detected timestamp format mpstat output"
                elif [[ "${fields[0]}" == "Average" ]]; then
                    start_idx=2  # Format starting with Average
                    log_debug "Detected Average format mpstat output"
                else
                    # Find "all" field to determine start position
                    for i in "${!fields[@]}"; do
                        if [[ "${fields[$i]}" == "all" ]]; then
                            start_idx=$((i + 1))
                            log_debug "Found 'all' field at position $i, start index set to $start_idx"
                            break
                        fi
                    done
                fi

                # Extract and validate CPU metric data
                local cpu_usr=$(validate_numeric_value "${fields[$start_idx]:-0}")
                local cpu_sys=$(validate_numeric_value "${fields[$((start_idx + 2))]:-0}")
                local cpu_iowait=$(validate_numeric_value "${fields[$((start_idx + 3))]:-0}")
                local cpu_soft=$(validate_numeric_value "${fields[$((start_idx + 5))]:-0}")
                local cpu_idle=$(validate_numeric_value "${fields[$((start_idx + 9))]:-0}")
                
                # Calculate total CPU usage and validate
                local cpu_usage=$(awk "BEGIN {printf \"%.2f\", 100 - $cpu_idle}" 2>/dev/null || echo "0")
                cpu_usage=$(validate_numeric_value "$cpu_usage")

                log_debug "📊 CPU metrics parsed successfully: usage=${cpu_usage}%, user=${cpu_usr}%, system=${cpu_sys}%, IO wait=${cpu_iowait}%, soft IRQ=${cpu_soft}%, idle=${cpu_idle}%"
                echo "$cpu_usage,$cpu_usr,$cpu_sys,$cpu_iowait,$cpu_soft,$cpu_idle"
                return
            else
                log_warn "⚠️ CPU statistics line not found in mpstat output"
            fi
        else
            log_warn "⚠️ mpstat command execution failed or no output"
        fi
    fi

    # Fallback: if mpstat unavailable or failed, return safe default values
    log_warn "🔄 CPU data acquisition failed, using default values"
    echo "0,0,0,0,0,100"
}

# Memory data collector
# Returns: "mem_used_mb,mem_total_mb,mem_usage_percent" format string
# Note: Prefer free command, fallback to /proc/meminfo
get_memory_data() {
    log_debug "🔍 Collecting memory usage data..."
    
    # Prefer free command - most direct memory statistics method
    if is_command_available "free"; then
        local mem_info=$(free -m 2>/dev/null)
        if [[ -n "$mem_info" ]]; then
            log_debug "✅ free command executed successfully, parsing memory data"
            
            local mem_line=$(echo "$mem_info" | grep "^Mem:")
            if [[ -n "$mem_line" ]]; then
                # Extract and validate memory data
                local mem_used=$(echo "$mem_line" | awk '{print $3}' 2>/dev/null || echo "0")
                local mem_total=$(echo "$mem_line" | awk '{print $2}' 2>/dev/null || echo "1")
                
                mem_used=$(validate_numeric_value "$mem_used")
                mem_total=$(validate_numeric_value "$mem_total" "1")  # Avoid division by zero
                
                # Calculate memory usage
                local mem_usage="0"
                if [[ "$mem_total" != "0" ]]; then
                    mem_usage=$(awk "BEGIN {printf \"%.2f\", $mem_used * 100 / $mem_total}" 2>/dev/null || echo "0")
                    mem_usage=$(format_percentage "$mem_usage" 2)
                fi
                
                log_debug "📊 Memory data: used=${mem_used}MB, total=${mem_total}MB, usage=${mem_usage}%"
                echo "$mem_used,$mem_total,$mem_usage"
                return
            else
                log_warn "⚠️ free command output format abnormal"
            fi
        else
            log_warn "⚠️ free command execution failed"
        fi
    fi

    # Use /proc/meminfo
    if [[ -r "/proc/meminfo" ]]; then
        local mem_total_kb=$(grep "^MemTotal:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "1")
        local mem_free_kb=$(grep "^MemFree:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
        local mem_available_kb=$(grep "^MemAvailable:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "$mem_free_kb")

        if [[ "$mem_total_kb" -gt 0 ]]; then
            # Convert to MB
            local mem_total_mb=$((mem_total_kb / 1024))
            local mem_used_mb=$(((mem_total_kb - mem_available_kb) / 1024))
            local mem_usage=$(awk "BEGIN {printf \"%.2f\", $mem_used_mb * 100 / $mem_total_mb}" 2>/dev/null || echo "0")
            echo "$mem_used_mb,$mem_total_mb,$mem_usage"
            return
        fi
    fi

    # Final fallback
    echo "0,0,0"
}

# Network monitoring - support sar command and /proc/net/dev alternative
get_network_data() {
    if [[ -z "$NETWORK_INTERFACE" ]]; then
        echo "unknown,0,0,0,0,0,0,0,0,0"
        return
    fi

    # Prefer sar for network statistics
    if is_command_available "sar"; then
        local sar_output=$(sar -n DEV 1 1 2>/dev/null | grep "$NETWORK_INTERFACE" | tail -1)

        if [[ -n "$sar_output" ]]; then
            local fields=($sar_output)

            # Correctly handle sar output format
            # sar -n DEV output format: Time IFACE rxpck/s txpck/s rxkB/s txkB/s rxcmp/s txcmp/s rxmcst/s
            local start_idx=1  # Default start from interface name

            # Check if first field is time format
            if [[ "${fields[0]}" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2}$ ]]; then
                start_idx=1  # Interface name at index 1
            else
                # Other formats, find interface name position
                for i in "${!fields[@]}"; do
                    if [[ "${fields[$i]}" == "$NETWORK_INTERFACE" ]]; then
                        start_idx=$i
                        break
                    fi
                done
            fi

            # Ensure interface name matches
            if [[ "${fields[$start_idx]}" != "$NETWORK_INTERFACE" ]]; then
                echo "$NETWORK_INTERFACE,0,0,0,0,0,0,0,0,0"
                return
            fi

            # Extract network statistics data
            local rx_pps=${fields[$((start_idx + 1))]:-0}    # rxpck/s
            local tx_pps=${fields[$((start_idx + 2))]:-0}    # txpck/s
            local rx_kbs=${fields[$((start_idx + 3))]:-0}    # rxkB/s
            local tx_kbs=${fields[$((start_idx + 4))]:-0}    # txkB/s

            # Correctly convert to AWS standard network bandwidth units
            # sar outputs kB/s (actually is KB/s, decimal)
            # Conversion steps: kB/s -> bytes/s -> bits/s -> Mbps -> Gbps
            local rx_mbps=$(awk "BEGIN {printf \"%.3f\", $rx_kbs * 8 / 1000}" 2>/dev/null || echo "0")
            local tx_mbps=$(awk "BEGIN {printf \"%.3f\", $tx_kbs * 8 / 1000}" 2>/dev/null || echo "0")
            local total_mbps=$(awk "BEGIN {printf \"%.3f\", $rx_mbps + $tx_mbps}" 2>/dev/null || echo "0")

            # Convert to Gbps (AWS EC2 network bandwidth usually measured in Gbps)
            local rx_gbps=$(awk "BEGIN {printf \"%.6f\", $rx_mbps / 1000}" 2>/dev/null || echo "0")
            local tx_gbps=$(awk "BEGIN {printf \"%.6f\", $tx_mbps / 1000}" 2>/dev/null || echo "0")
            local total_gbps=$(awk "BEGIN {printf \"%.6f\", $total_mbps / 1000}" 2>/dev/null || echo "0")

            # Calculate total PPS
            local total_pps=$(awk "BEGIN {printf \"%.0f\", $rx_pps + $tx_pps}" 2>/dev/null || echo "0")

            echo "$NETWORK_INTERFACE,$rx_mbps,$tx_mbps,$total_mbps,$rx_gbps,$tx_gbps,$total_gbps,$rx_pps,$tx_pps,$total_pps"
            return
        fi
    fi

    # Alternative: read from /proc/net/dev
    if [[ -r "/proc/net/dev" ]]; then
        local net_stats=$(grep "$NETWORK_INTERFACE:" /proc/net/dev 2>/dev/null | head -1)
        if [[ -n "$net_stats" ]]; then
            # Parse /proc/net/dev format
            # Format: interface: bytes packets errs drop fifo frame compressed multicast
            local fields=($net_stats)
            local rx_bytes=${fields[1]:-0}
            local rx_packets=${fields[2]:-0}
            local tx_bytes=${fields[9]:-0}
            local tx_packets=${fields[10]:-0}

            # Simplified calculation - cannot calculate accurate rate due to instantaneous read
            # Return basic format, actual rate is 0
            echo "$NETWORK_INTERFACE,0,0,0,0,0,0,0,0,0"
            return
        fi
    fi

    # Final fallback
    echo "$NETWORK_INTERFACE,0,0,0,0,0,0,0,0,0"
}

get_ena_allowance_data() {
    if [[ "$ENA_MONITOR_ENABLED" != "true" ]]; then
        # Generate default values matching configured field count - use standardized array access
        local default_values=""
        ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
        for field in "${ena_fields[@]}"; do
            if [[ -n "$default_values" ]]; then
                default_values="$default_values,0"
            else
                default_values="0"
            fi
        done
        echo "$default_values"
        return
    fi

    if ! is_command_available "ethtool"; then
        # Generate default values matching configured field count - use standardized array access
        local default_values=""
        ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
        for field in "${ena_fields[@]}"; do
            if [[ -n "$default_values" ]]; then
                default_values="$default_values,0"
            else
                default_values="0"
            fi
        done
        echo "$default_values"
        return
    fi

    local ethtool_output=$(ethtool -S "$NETWORK_INTERFACE" 2>/dev/null || echo "")

    # Configuration-driven ENA allowance statistics acquisition - use standardized array access
    local ena_values=""
    ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
    for field in "${ena_fields[@]}"; do
        local value=$(echo "$ethtool_output" | grep "$field:" | awk '{print $2}' || echo "0")
        # Add data validation to ensure value is valid number
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

# Configuration-based process discovery engine (with performance monitoring)
discover_monitoring_processes() {
    local start_time=$(date +%s%3N 2>/dev/null || date +%s)
    local pattern=""

    # Build process name pattern string - use standardized array access
    monitoring_processes=($MONITORING_PROCESS_NAMES_STR)
    pattern=$(IFS='|'; echo "${monitoring_processes[*]}")
    log_debug "Using configured monitoring process name pattern: $pattern"

    # Get monitoring process list, exclude current script to avoid self-reference
    local monitoring_pids=$(pgrep -f "$pattern" 2>/dev/null | grep -v "^$$\$" | tr '\n' ' ')

    if [[ -n "$monitoring_pids" ]]; then
        log_debug "Found monitoring processes: $monitoring_pids"
    else
        log_debug "No monitoring processes found"
    fi

    # Performance monitoring
    local end_time=$(date +%s%3N 2>/dev/null || date +%s)
    local current_resources=$(get_current_process_resources)
    local current_cpu=$(echo "$current_resources" | cut -d',' -f1)
    local current_memory=$(echo "$current_resources" | cut -d',' -f2)
    monitor_performance_impact "discover_monitoring_processes" "$start_time" "$end_time" "$current_cpu" "$current_memory"

    echo "$monitoring_pids"
}

# System static resource collector - direct acquisition
get_system_static_resources() {
    # Direct acquisition of CPU core count
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
    
    # Direct acquisition of memory size
    local memory_gb="0.00"
    if command -v free >/dev/null 2>&1; then
        local memory_kb=$(free | awk '/^Mem:/{print $2}' 2>/dev/null)
        if [[ "$memory_kb" =~ ^[0-9]+$ ]] && [[ "$memory_kb" -gt 0 ]]; then
            memory_gb=$(awk "BEGIN {printf \"%.2f\", $memory_kb/1024/1024}")
        fi
    fi
    
    # Direct acquisition of disk size
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

# System dynamic resource collector
get_system_dynamic_resources() {
    log_debug "Collecting system dynamic resource usage"

    # Get system CPU usage
    local cpu_usage=0
    if is_command_available "mpstat"; then
        # Use mpstat to get CPU usage (1 second sampling)
        cpu_usage=$(mpstat 1 1 2>/dev/null | awk '/Average:/ && /all/ {print 100-$NF}' | head -1)
        # Verify result is numeric
        if ! [[ "$cpu_usage" =~ ^[0-9]+\.?[0-9]*$ ]]; then
            cpu_usage=0
        fi
    elif [[ -r "/proc/stat" ]]; then
        # Linux fallback: use /proc/stat
        local cpu_line1=$(grep "^cpu " /proc/stat)
        sleep 1
        local cpu_line2=$(grep "^cpu " /proc/stat)

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
        # Generic fallback
        cpu_usage=$(top -l 2 -n 0 2>/dev/null | grep "CPU usage" | tail -1 | awk '{print $3}' | sed 's/%//' || echo "0.0")
    fi

    # Get system memory usage and detailed information
    local memory_usage=0
    local cached_gb=0
    local buffers_gb=0
    local anon_pages_gb=0
    local mapped_gb=0
    local shmem_gb=0
    
    if is_command_available "free"; then
        # Linux
        memory_usage=$(free 2>/dev/null | awk '/^Mem:/{printf "%.1f", $3/$2*100}' || echo "0.0")
    fi
    
    # Read detailed memory information from /proc/meminfo
    if [[ -r "/proc/meminfo" ]]; then
        # Linux fallback
        local mem_total_kb=$(grep "^MemTotal:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "1")
        local mem_available_kb=$(grep "^MemAvailable:" /proc/meminfo | awk '{print $2}' 2>/dev/null)
        local cached_kb=$(grep "^Cached:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
        local buffers_kb=$(grep "^Buffers:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
        local anon_pages_kb=$(grep "^AnonPages:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
        local mapped_kb=$(grep "^Mapped:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
        local shmem_kb=$(grep "^Shmem:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
        
        # Convert to GB
        cached_gb=$(awk "BEGIN {printf \"%.2f\", ${cached_kb}/1024/1024}" 2>/dev/null || echo "0.00")
        buffers_gb=$(awk "BEGIN {printf \"%.2f\", ${buffers_kb}/1024/1024}" 2>/dev/null || echo "0.00")
        anon_pages_gb=$(awk "BEGIN {printf \"%.2f\", ${anon_pages_kb}/1024/1024}" 2>/dev/null || echo "0.00")
        mapped_gb=$(awk "BEGIN {printf \"%.2f\", ${mapped_kb}/1024/1024}" 2>/dev/null || echo "0.00")
        shmem_gb=$(awk "BEGIN {printf \"%.2f\", ${shmem_kb}/1024/1024}" 2>/dev/null || echo "0.00")
        
        if [[ -z "$mem_available_kb" ]]; then
            local mem_free_kb=$(grep "^MemFree:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
            local mem_buffers_kb=$(grep "^Buffers:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
            local mem_cached_kb=$(grep "^Cached:" /proc/meminfo | awk '{print $2}' 2>/dev/null || echo "0")
            mem_available_kb=$((mem_free_kb + mem_buffers_kb + mem_cached_kb))
        fi
    fi

    # Get disk usage (root partition)
    local disk_usage=0
    if is_command_available "df"; then
        disk_usage=$(df / 2>/dev/null | awk 'NR==2{print $5}' | sed 's/%//' || echo "0")
    fi

    # Validate all numeric values
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

# Discover blockchain node processes
discover_blockchain_processes() {
    local pattern=""

    # Build blockchain process name pattern string - use standardized array access
    blockchain_processes=($BLOCKCHAIN_PROCESS_NAMES_STR)
    pattern=$(IFS='|'; echo "${blockchain_processes[*]}")
    log_debug "Using configured blockchain process name pattern: $pattern"

    # Get blockchain process list
    local blockchain_pids=$(pgrep -f "$pattern" 2>/dev/null | tr '\n' ' ')

    if [[ -n "$blockchain_pids" ]]; then
        log_debug "Discovered blockchain processes: $blockchain_pids"
    else
        log_debug "No blockchain processes found"
    fi

    echo "$blockchain_pids"
}

# Batch process resource calculator (with performance monitoring)
calculate_process_resources() {
    local start_time=$(date +%s%3N 2>/dev/null || date +%s)
    local pids="$1"
    local process_type="${2:-unknown}"

    if [[ -z "$pids" ]]; then
        log_debug "No ${process_type} processes to count"
        echo "0,0,0,0"
        return
    fi

    # Clean PID string, convert to comma-separated format
    pids=$(echo "$pids" | tr -s ' ' | sed 's/^ *//;s/ *$//' | tr ' ' ',')

    # Use single ps command to batch query all processes (cross-platform compatible)
    local proc_stats=""
    if is_command_available "ps"; then
        # Detect operating system type
        if [[ "$(uname -s)" == "Linux" ]]; then
            # Linux format
            proc_stats=$(ps -p $pids -o %cpu,%mem,rss --no-headers 2>/dev/null)
        else
            # BSD format
            proc_stats=$(ps -p $pids -o pcpu,pmem,rss 2>/dev/null | tail -n +2)
        fi

        # If first format fails, try another format
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
        # Skip empty lines
        [[ -n "$cpu" ]] || continue

        # Numeric validation and accumulation - use awk for cross-platform compatibility
        if [[ "$cpu" =~ ^[0-9]+\.?[0-9]*$ ]]; then
            total_cpu=$(awk "BEGIN {printf \"%.2f\", $total_cpu + $cpu}" 2>/dev/null || echo "$total_cpu")
        fi

        if [[ "$mem" =~ ^[0-9]+\.?[0-9]*$ ]]; then
            total_memory=$(awk "BEGIN {printf \"%.2f\", $total_memory + $mem}" 2>/dev/null || echo "$total_memory")
        fi

        if [[ "$rss" =~ ^[0-9]+$ ]]; then
            local rss_mb=$(awk "BEGIN {printf \"%.2f\", $rss / 1024}" 2>/dev/null || echo "0.00")
            total_memory_mb=$(awk "BEGIN {printf \"%.2f\", $total_memory_mb + $rss_mb}" 2>/dev/null || echo "$total_memory_mb")
        fi

        count=$((count + 1))
    done <<< "$proc_stats"

    log_debug "${process_type} process resource statistics: CPU=${total_cpu}%, Memory=${total_memory}%, MemoryMB=${total_memory_mb}, ProcessCount=${count}"

    # Performance monitoring
    local end_time=$(date +%s%3N 2>/dev/null || date +%s)
    local current_resources=$(get_current_process_resources)
    local current_cpu=$(echo "$current_resources" | cut -d',' -f1)
    local current_memory=$(echo "$current_resources" | cut -d',' -f2)
    monitor_performance_impact "calculate_process_resources_${process_type}" "$start_time" "$end_time" "$current_cpu" "$current_memory"

    echo "$total_cpu,$total_memory,$total_memory_mb,$count"
}

# Monitoring overhead statistics
get_monitoring_overhead() {
    # Simple recursion detection
    if [[ "${MONITORING_SELF:-false}" == "true" ]]; then
        echo "0,0"
        return 0
    fi
    
    # Set recursion flag
    export MONITORING_SELF=true
    
    # Execute actual monitoring logic - call monitoring overhead calculation
    local result=$(get_monitoring_overhead_legacy)
    
    # Clear recursion flag
    unset MONITORING_SELF
    
    echo "$result"
}

get_monitoring_overhead_legacy() {
    # I/O state cleanup counter
    call_count=${call_count:-0}
    ((call_count++))
    if (( call_count % 50 == 0 )); then
        cleanup_dead_process_io_stats
    fi
    
    # Use new process discovery engine
    local monitoring_pids=$(discover_monitoring_processes)

    if [[ -z "$monitoring_pids" ]]; then
        log_debug "No monitoring processes found, returning zero overhead"
        echo "0,0"
        return
    fi

    # Calculate monitoring process resource usage
    local monitoring_resources=$(calculate_process_resources "$monitoring_pids" "monitoring")

    # Parse resource statistics result
    local monitoring_cpu=$(echo "$monitoring_resources" | cut -d',' -f1)
    local monitoring_memory_percent=$(echo "$monitoring_resources" | cut -d',' -f2)
    local monitoring_memory_mb=$(echo "$monitoring_resources" | cut -d',' -f3)
    local process_count=$(echo "$monitoring_resources" | cut -d',' -f4)

    # Real I/O measurement - based on /proc/pid/io data
    local total_read_bytes_diff=0
    local total_write_bytes_diff=0
    local total_read_ops_diff=0
    local total_write_ops_diff=0

    for pid in $monitoring_pids; do
        if [[ -f "/proc/$pid/io" ]]; then
            local io_stats=$(cat "/proc/$pid/io" 2>/dev/null)
            if [[ -n "$io_stats" ]]; then
                local current_read_bytes=$(echo "$io_stats" | grep "^read_bytes:" | awk '{print $2}' | tr -d '\n\r\t ' 2>/dev/null)
                local current_write_bytes=$(echo "$io_stats" | grep "^write_bytes:" | awk '{print $2}' | tr -d '\n\r\t ' 2>/dev/null)
                local current_syscr=$(echo "$io_stats" | grep "^syscr:" | awk '{print $2}' | tr -d '\n\r\t ' 2>/dev/null)
                local current_syscw=$(echo "$io_stats" | grep "^syscw:" | awk '{print $2}' | tr -d '\n\r\t ' 2>/dev/null)

                # Add numeric validation
                [[ "$current_read_bytes" =~ ^[0-9]+$ ]] || current_read_bytes=0
                [[ "$current_write_bytes" =~ ^[0-9]+$ ]] || current_write_bytes=0
                [[ "$current_syscr" =~ ^[0-9]+$ ]] || current_syscr=0
                [[ "$current_syscw" =~ ^[0-9]+$ ]] || current_syscw=0

                # Get last recorded values
                local last_read_bytes=${LAST_IO_STATS["${pid}_read_bytes"]:-$current_read_bytes}
                local last_write_bytes=${LAST_IO_STATS["${pid}_write_bytes"]:-$current_write_bytes}
                local last_syscr=${LAST_IO_STATS["${pid}_syscr"]:-$current_syscr}
                local last_syscw=${LAST_IO_STATS["${pid}_syscw"]:-$current_syscw}

                # Calculate difference (increment for this monitoring cycle)
                local read_bytes_diff=$((current_read_bytes - last_read_bytes))
                local write_bytes_diff=$((current_write_bytes - last_write_bytes))
                local syscr_diff=$((current_syscr - last_syscr))
                local syscw_diff=$((current_syscw - last_syscw))

                # Ensure difference is positive (handle process restart scenarios)
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

                # Update state
                LAST_IO_STATS["${pid}_read_bytes"]=$current_read_bytes
                LAST_IO_STATS["${pid}_write_bytes"]=$current_write_bytes
                LAST_IO_STATS["${pid}_syscr"]=$current_syscr
                LAST_IO_STATS["${pid}_syscw"]=$current_syscw

                # Accumulate differences
                total_read_bytes_diff=$((total_read_bytes_diff + read_bytes_diff))
                total_write_bytes_diff=$((total_write_bytes_diff + write_bytes_diff))
                total_read_ops_diff=$((total_read_ops_diff + syscr_diff))
                total_write_ops_diff=$((total_write_ops_diff + syscw_diff))
            fi
        fi
    done

    # Calculate real per-second rate (improve precision to capture minimal values)
    local real_iops=$(awk "BEGIN {printf \"%.4f\", ($total_read_ops_diff + $total_write_ops_diff) / $MONITOR_INTERVAL}" 2>/dev/null || echo "0.0000")
    local real_throughput=$(awk "BEGIN {printf \"%.8f\", ($total_read_bytes_diff + $total_write_bytes_diff) / $MONITOR_INTERVAL / 1024 / 1024}" 2>/dev/null || echo "0.00000000")

    # Ensure numeric format is correct
    real_iops=$(printf "%.4f" "$real_iops" 2>/dev/null || echo "0.0000")
    real_throughput=$(printf "%.8f" "$real_throughput" 2>/dev/null || echo "0.00000000")

    log_debug "Monitoring overhead statistics: ProcessCount=${process_count}, CPU=${monitoring_cpu}%, Memory=${monitoring_memory_percent}%(${monitoring_memory_mb}MB), RealIOPS=${real_iops}, RealThroughput=${real_throughput}MiB/s"

    # Keep original return format (IOPS, Throughput)
    echo "$real_iops,$real_throughput"
}

# Blockchain node resource statistics
get_blockchain_node_resources() {
    # Use new process discovery engine to get blockchain processes
    local blockchain_pids=$(discover_blockchain_processes)

    if [[ -z "$blockchain_pids" ]]; then
        log_debug "No blockchain processes found, returning zero resource usage"
        echo "0,0,0,0"
        return
    fi

    # Calculate blockchain process resource usage
    local blockchain_resources=$(calculate_process_resources "$blockchain_pids" "blockchain")

    # Parse resource statistics result
    local blockchain_cpu=$(echo "$blockchain_resources" | cut -d',' -f1)
    local blockchain_memory_percent=$(echo "$blockchain_resources" | cut -d',' -f2)
    local blockchain_memory_mb=$(echo "$blockchain_resources" | cut -d',' -f3)
    local process_count=$(echo "$blockchain_resources" | cut -d',' -f4)

    log_debug "Blockchain node resources: ProcessCount=${process_count}, CPU=${blockchain_cpu}%, Memory=${blockchain_memory_percent}%(${blockchain_memory_mb}MB)"

    echo "$blockchain_cpu,$blockchain_memory_percent,$blockchain_memory_mb,$process_count"
}

# Performance impact monitoring configuration - use layered configuration to avoid duplicate definitions
# PERFORMANCE_MONITORING_ENABLED, MAX_COLLECTION_TIME_MS already defined in internal_config.sh
# Bottleneck detection thresholds BOTTLENECK_CPU_THRESHOLD, BOTTLENECK_MEMORY_THRESHOLD already defined in internal_config.sh
# PERFORMANCE_LOG will be set in detect_deployment_paths() function in config_loader.sh

# Performance impact monitoring function
monitor_performance_impact() {
    local function_name="$1"
    local start_time="$2"
    local end_time="$3"
    local cpu_usage="$4"
    local memory_usage="$5"

    if [[ "$PERFORMANCE_MONITORING_ENABLED" != "true" ]]; then
        return 0
    fi

    # Calculate execution time (milliseconds)
    local execution_time_ms=$(( (end_time - start_time) ))

    # Check performance thresholds
    local warnings=()

    # Check execution time
    if (( execution_time_ms > MAX_COLLECTION_TIME_MS )); then
        warnings+=("Execution time exceeded: ${execution_time_ms}ms > ${MAX_COLLECTION_TIME_MS}ms")
    fi

    # Check CPU usage
    if (( $(awk "BEGIN {print ($cpu_usage > $BOTTLENECK_CPU_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        warnings+=("CPU usage exceeded: ${cpu_usage}% > ${BOTTLENECK_CPU_THRESHOLD}%")
    fi

    # Check memory usage
    local total_memory_mb=$(get_cached_total_memory)
    local memory_usage_percent=$(calculate_memory_percentage "$memory_usage" "$total_memory_mb")
    
    if (( $(awk "BEGIN {print ($memory_usage_percent > $BOTTLENECK_MEMORY_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        warnings+=("Memory usage exceeded: ${memory_usage}MB (${memory_usage_percent}%) > ${BOTTLENECK_MEMORY_THRESHOLD}%")
    fi

    # Record performance data
    local timestamp=$(get_unified_timestamp)
    local performance_entry="${timestamp},${function_name},${execution_time_ms},${cpu_usage},${memory_usage}"

    # Write to performance log
    if [[ ! -f "$PERFORMANCE_LOG" ]]; then
        echo "timestamp,function_name,execution_time_ms,cpu_percent,memory_mb" > "$PERFORMANCE_LOG"
    fi
    
    # Write directly to performance log to avoid recursion risk
    local temp_file="${PERFORMANCE_LOG}.tmp.$$"
    if echo "$performance_entry" >> "$temp_file" && mv "$temp_file" "$PERFORMANCE_LOG"; then
        : # Success, no output needed
    else
        rm -f "$temp_file"
        echo "ERROR: Performance log write failed: $PERFORMANCE_LOG" >&2
    fi

    # If there are warnings, write directly to unified_monitor log file
    if [[ ${#warnings[@]} -gt 0 ]]; then
        # Hardcode component name to completely avoid environment variable pollution
        local component="unified_monitor"
        local component_log="${LOGS_DIR}/unified_monitor.log"
        
        if [[ -n "$component_log" ]]; then
            local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
            echo "[$timestamp] [WARN] [$component] Monitoring performance warning - Function: $function_name" >> "$component_log"
            for warning in "${warnings[@]}"; do
                echo "[$timestamp] [WARN] [$component]   - $warning" >> "$component_log"
            done
            
            # Generate optimization suggestions
            echo "[$timestamp] [INFO] [$component] 🔧 Performance optimization suggestions - $function_name:" >> "$component_log"
            echo "[$timestamp] [INFO] [$component]   💡 Suggestion: Consider increasing MONITOR_INTERVAL or optimizing data collection logic" >> "$component_log"
            echo "[$timestamp] [INFO] [$component]   📊 View detailed performance data: $PERFORMANCE_LOG" >> "$component_log"
        fi
    fi

    log_debug "Performance monitoring: $function_name execution_time=${execution_time_ms}ms CPU=${cpu_usage}% Memory=${memory_usage}MB"
}

# Generate performance optimization suggestions
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

# Generate performance impact report
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

        # Calculate overall performance statistics
        echo "## Overall Performance Statistics"
        local total_records=$(tail -n +2 "$PERFORMANCE_LOG" | wc -l)
        echo "Total records: $total_records"

        if [[ $total_records -gt 0 ]]; then
            # Average execution time
            local avg_time=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f3 | awk '{sum+=$1} END {print sum/NR}')
            echo "Average execution time: ${avg_time:-0} ms"

            # Maximum execution time
            local max_time=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f3 | sort -n | tail -1)
            echo "Maximum execution time: ${max_time:-0} ms"

            # Average CPU usage
            local avg_cpu=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f4 | awk '{sum+=$1} END {print sum/NR}')
            echo "Average CPU usage: ${avg_cpu:-0}%"

            # Average memory usage
            local avg_memory=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f5 | awk '{sum+=$1} END {print sum/NR}')
            echo "Average memory usage: ${avg_memory:-0} MB"
        fi

        echo ""

        # Statistics grouped by function
        echo "## Statistics Grouped by Function"
        tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f2 | sort | uniq | while read -r func_name; do
            echo "### $func_name"
            local func_data=$(tail -n +2 "$PERFORMANCE_LOG" | grep ",$func_name,")
            local func_count=$(echo "$func_data" | wc -l)
            local func_avg_time=$(echo "$func_data" | cut -d',' -f3 | awk '{sum+=$1} END {print sum/NR}')
            local func_max_time=$(echo "$func_data" | cut -d',' -f3 | sort -n | tail -1)
            local func_avg_cpu=$(echo "$func_data" | cut -d',' -f4 | awk '{sum+=$1} END {print sum/NR}')
            local func_avg_memory=$(echo "$func_data" | cut -d',' -f5 | awk '{sum+=$1} END {print sum/NR}')

            echo "- Call count: $func_count"
            echo "- Average execution time: ${func_avg_time:-0} ms"
            echo "- Maximum execution time: ${func_max_time:-0} ms"
            echo "- Average CPU usage: ${func_avg_cpu:-0}%"
            echo "- Average memory usage: ${func_avg_memory:-0} MB"
            echo ""
        done

        # Performance warning analysis
        echo "## Performance Warning Analysis"
        local total_memory_mb=$(get_cached_total_memory)
        local memory_threshold_mb=$(awk "BEGIN {printf \"%.0f\", $total_memory_mb * $BOTTLENECK_MEMORY_THRESHOLD / 100}")
        
        local warning_count=$(tail -n +2 "$PERFORMANCE_LOG" | awk -F',' -v max_time="$MAX_COLLECTION_TIME_MS" -v max_cpu="$BOTTLENECK_CPU_THRESHOLD" -v max_mem="$memory_threshold_mb" '
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
            local warning_ratio=$(awk "BEGIN {printf \"%.2f\", $warning_count * 100 / $total_records}")
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

# Automatic performance optimization advisor system
auto_performance_optimization_advisor() {
    if [[ ! -f "$PERFORMANCE_LOG" ]]; then
        return 0
    fi

    local total_records=$(tail -n +2 "$PERFORMANCE_LOG" | wc -l)

    # Need at least 10 records for analysis
    if [[ $total_records -lt 10 ]]; then
        return 0
    fi

    log_info "🤖 Automatic performance optimization analysis (based on $total_records records)"

    # Analyze execution time trend
    local avg_time=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f3 | awk '{sum+=$1} END {print sum/NR}')
    local max_time=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f3 | sort -n | tail -1)

    if (( $(awk "BEGIN {print ($avg_time > $MAX_COLLECTION_TIME_MS * 0.8) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        log_warn "⚠️  Average execution time approaching threshold (${avg_time}ms vs ${MAX_COLLECTION_TIME_MS}ms)"
        log_info "💡 Suggestion: Consider increasing MONITOR_INTERVAL from ${MONITOR_INTERVAL}s to $((MONITOR_INTERVAL * 2))s"
    fi

    # Analyze CPU usage trend
    local avg_cpu=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f4 | awk '{sum+=$1} END {print sum/NR}')

    if (( $(awk "BEGIN {print ($avg_cpu > $BOTTLENECK_CPU_THRESHOLD * 0.8) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        log_warn "⚠️  Average CPU usage approaching threshold (${avg_cpu}% vs ${BOTTLENECK_CPU_THRESHOLD}%)"
        log_info "💡 Suggestion: Reduce number of monitoring processes or optimize process discovery algorithm"
    fi

    # Analyze memory usage trend
    local avg_memory=$(tail -n +2 "$PERFORMANCE_LOG" | cut -d',' -f5 | awk '{sum+=$1} END {print sum/NR}')

    # Convert MB to percentage for comparison
    local total_memory_mb=$(get_cached_total_memory)
    local avg_memory_percent=$(calculate_memory_percentage "$avg_memory" "$total_memory_mb")
    
    if (( $(awk "BEGIN {print ($avg_memory_percent > $BOTTLENECK_MEMORY_THRESHOLD * 0.8) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        log_warn "⚠️  Average memory usage approaching threshold (${avg_memory}MB, ${avg_memory_percent}% vs ${BOTTLENECK_MEMORY_THRESHOLD}%)"
        log_info "💡 Suggestion: Optimize data structures or add memory cleanup logic"
    fi

    # Analyze slowest function
    local slowest_func=$(tail -n +2 "$PERFORMANCE_LOG" | sort -t',' -k3 -n | tail -1 | cut -d',' -f2)
    local slowest_time=$(tail -n +2 "$PERFORMANCE_LOG" | sort -t',' -k3 -n | tail -1 | cut -d',' -f3)

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

# Current dynamic monitoring interval (global variable) - use general monitoring interval, EBS-specific monitoring uses EBS_MONITOR_RATE through iostat background high-frequency collection
CURRENT_MONITOR_INTERVAL=${MONITOR_INTERVAL}

# System load assessment function
assess_system_load() {
    local cpu_usage=0
    local memory_usage=0
    local load_average=0

    # Get CPU usage
    if is_command_available "mpstat"; then
        cpu_usage=$(mpstat 1 1 | awk '/Average/ && /all/ {print 100-$NF}' 2>/dev/null || echo "0.0")
    elif is_command_available "top"; then
        # Use top command to get CPU usage
        cpu_usage=$(top -l 1 -n 0 | grep "CPU usage" | awk '{print $3}' | sed 's/%//' 2>/dev/null || echo "0.0")
    fi

    # Get memory usage
    if is_command_available "free"; then
        memory_usage=$(free | awk '/^Mem:/ {printf "%.1f", $3/$2 * 100}' 2>/dev/null || echo "0.0")
    elif [[ -f /proc/meminfo ]]; then
        local mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        local mem_available=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
        if [[ -n "$mem_total" && -n "$mem_available" ]]; then
            memory_usage=$(awk "BEGIN {printf \"%.1f\", ($mem_total - $mem_available) * 100 / $mem_total}" 2>/dev/null || echo "0.0")
        fi

    fi

    # Get system load average
    if [[ -f /proc/loadavg ]]; then
        load_average=$(cut -d' ' -f1 /proc/loadavg 2>/dev/null || echo "0.0")
    elif is_command_available "uptime"; then
        load_average=$(uptime | awk -F'load average:' '{print $2}' | awk -F',' '{print $1}' | tr -d ' ' 2>/dev/null || echo "0.0")
    fi

    # Calculate comprehensive load score (0-100)
    local cpu_score=$(awk "BEGIN {printf \"%.0f\", $cpu_usage}" 2>/dev/null || echo "0")
    local memory_score=$(awk "BEGIN {printf \"%.0f\", $memory_usage}" 2>/dev/null || echo "0")

    # Convert load average to score (assume 4-core system, load 4.0 = 100%)
    local cpu_cores=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "4")
    local load_score=$(awk "BEGIN {printf \"%.0f\", $load_average * 100 / $cpu_cores}" 2>/dev/null || echo "0")

    # Take highest score as system load
    local system_load=$cpu_score
    if (( $(awk "BEGIN {print ($memory_score > $system_load) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        system_load=$memory_score
    fi
    if (( $(awk "BEGIN {print ($load_score > $system_load) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        system_load=$load_score
    fi

    # Ensure load value is within reasonable range
    if (( $(awk "BEGIN {print ($system_load < 0) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        system_load=0
    elif (( $(awk "BEGIN {print ($system_load > 100) ? 1 : 0}" 2>/dev/null || echo "0") )); then
        system_load=100
    fi

    log_debug "System load assessment: CPU=${cpu_usage}% Memory=${memory_usage}% Load=${load_average} Comprehensive=${system_load}%"
    echo "$system_load"
}

# Error handling and recovery mechanism configuration - use configuration from system_config.sh to avoid duplicate definitions
# ERROR_RECOVERY_ENABLED, MAX_CONSECUTIVE_ERRORS, ERROR_RECOVERY_DELAY already defined in system_config.sh
# ERROR_LOG will be set in detect_deployment_paths() function in config_loader.sh

# Error counters (global variables)
declare -A ERROR_COUNTERS
declare -A LAST_ERROR_TIME
declare -A RECOVERY_ATTEMPTS

# Error handling wrapper
handle_function_error() {
    local function_name="$1"
    local error_code="$2"
    local error_message="$3"
    local timestamp=$(get_unified_timestamp)

    # Increment error count
    ERROR_COUNTERS["$function_name"]=$((${ERROR_COUNTERS["$function_name"]:-0} + 1))
    LAST_ERROR_TIME["$function_name"]=$(date +%s)

    # Log error to file
    log_error_to_file "$function_name" "$error_code" "$error_message" "$timestamp"

    # Check if error recovery is needed
    if [[ ${ERROR_COUNTERS["$function_name"]} -ge $MAX_CONSECUTIVE_ERRORS ]]; then
        log_error "🔴 Function $function_name consecutive errors ${ERROR_COUNTERS["$function_name"]} times, initiating error recovery"
        initiate_error_recovery "$function_name"
    else
        log_warn "⚠️  Function $function_name error occurred (${ERROR_COUNTERS["$function_name"]}/$MAX_CONSECUTIVE_ERRORS): $error_message"
    fi
}

# Log error to file
log_error_to_file() {
    local function_name="$1"
    local error_code="$2"
    local error_message="$3"
    local timestamp="$4"

    # Create error log file
    if [[ ! -f "$ERROR_LOG" ]]; then
        echo "timestamp,function_name,error_code,error_message,consecutive_count" > "$ERROR_LOG"
    fi

    safe_write_csv "$ERROR_LOG" "$timestamp,$function_name,$error_code,\"$error_message\",${ERROR_COUNTERS["$function_name"]}"
}

# Initiate error recovery
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

    # Wait for recovery delay
    log_info "⏳ Error recovery delay ${ERROR_RECOVERY_DELAY}s..."
    sleep "$ERROR_RECOVERY_DELAY"

    # Reset error counter
    ERROR_COUNTERS["$function_name"]=0
    log_info "✅ Error recovery completed: $function_name"
}

# Process discovery error recovery
recover_process_discovery() {
    log_info "🔧 Recovering process discovery function..."

    # Check process name configuration - use standardized array access
    if [[ -z "$MONITORING_PROCESS_NAMES_STR" ]]; then
        log_warn "Monitoring process name configuration is empty, using default configuration"
        export MONITORING_PROCESS_NAMES_STR="iostat mpstat sar vmstat netstat unified_monitor bottleneck_detector ena_network_monitor block_height_monitor performance_visualizer overhead_monitor adaptive_frequency error_recovery report_generator"
    fi

    # Check if pgrep command is available
    if ! is_command_available "pgrep"; then
        log_error "pgrep command not available, trying to use ps command as alternative"
        # Can implement ps command alternative here
    fi

    # Clean up possible zombie processes
    log_info "Cleaning up zombie processes..."
    pkill -f "defunct" 2>/dev/null || true
}

# Resource calculation error recovery
recover_resource_calculation() {
    log_info "🔧 Recovering resource calculation function..."

    # Check if ps command is available
    if ! is_command_available "ps"; then
        log_error "ps command not available, this is a serious issue"
        return 1
    fi

    # Clean up possible temporary files
    rm -f /tmp/ps_output_* 2>/dev/null || true
}

# Monitoring overhead collection error recovery
recover_overhead_collection() {
    log_info "🔧 Recovering monitoring overhead collection function..."

    # Check log directory permissions
    if [[ ! -w "$LOGS_DIR" ]]; then
        log_error "Log directory not writable: $LOGS_DIR"
        mkdir -p "$LOGS_DIR" 2>/dev/null || true
        chmod 755 "$LOGS_DIR" 2>/dev/null || true
    fi

    # Check monitoring overhead log file
    if [[ -f "$MONITORING_OVERHEAD_LOG" ]] && [[ ! -w "$MONITORING_OVERHEAD_LOG" ]]; then
        log_warn "Monitoring overhead log file not writable, trying to fix permissions"
        chmod 644 "$MONITORING_OVERHEAD_LOG" 2>/dev/null || true
    fi

    # Reinitialize related components
    log_info "Reinitializing monitoring overhead collection components..."
}

# System load assessment error recovery
recover_system_load_assessment() {
    log_info "🔧 Recovering system load assessment function..."

    # Check system monitoring command availability
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
    else
        log_info "Available system monitoring commands: ${available_commands[*]}"
    fi
}

# Generic error recovery
generic_error_recovery() {
    local function_name="$1"

    log_info "🔧 Executing generic error recovery: $function_name"

    # Clean up temporary files
    find /tmp -name "*monitoring*" -mtime +1 -delete 2>/dev/null || true

    # Check system resources
    local available_memory=$(free -m 2>/dev/null | awk '/^Mem:/ {print $7}' || echo "unknown")
    local disk_space=$(df "$LOGS_DIR" 2>/dev/null | awk 'NR==2 {print $4}' || echo "unknown")

    log_info "System status check: available_memory=${available_memory}MB, disk_space=${disk_space}KB"

    # If disk space is insufficient, clean up old logs
    if [[ "$disk_space" != "unknown" ]] && [[ $disk_space -lt 1048576 ]]; then  # Less than 1GB
        log_warn "Insufficient disk space, cleaning up old log files..."
        find "$LOGS_DIR" -name "*.log" -mtime +7 -delete 2>/dev/null || true
        find "$LOGS_DIR" -name "*.csv" -mtime +3 -delete 2>/dev/null || true
    fi
}

# Error recovery suggestion system
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

# Safe function execution wrapper
safe_execute() {
    local function_name="$1"
    shift
    local function_args=("$@")

    # Check if function exists
    if ! declare -f "$function_name" >/dev/null 2>&1; then
        handle_function_error "$function_name" "FUNCTION_NOT_FOUND" "Function does not exist"
        return 1
    fi

    # Execute function and capture errors
    local result
    local error_code=0

    if result=$("$function_name" "${function_args[@]}" 2>&1); then
        # Successfully executed, reset error counter
        if [[ ${ERROR_COUNTERS["$function_name"]:-0} -gt 0 ]]; then
            log_info "✅ Function $function_name recovered to normal"
            ERROR_COUNTERS["$function_name"]=0
        fi
        echo "$result"
        return 0
    else
        error_code=$?
        handle_function_error "$function_name" "$error_code" "$result"
        return $error_code
    fi
}

# Get current process resource usage (for performance monitoring)
get_current_process_resources() {
    local pid=${1:-$$}

    # Get CPU and memory usage
    local process_info=$(ps -p "$pid" -o %cpu,%mem,rss --no-headers 2>/dev/null || echo "0.0 0.0 0")
    local cpu_percent=$(echo "$process_info" | awk '{print $1}')
    local memory_percent=$(echo "$process_info" | awk '{print $2}')
    local memory_kb=$(echo "$process_info" | awk '{print $3}')
    local memory_mb=$(awk "BEGIN {printf \"%.2f\", $memory_kb/1024}" 2>/dev/null || echo "0")

    echo "$cpu_percent,$memory_mb"
}

# Data quality check function
validate_data_quality() {
    local data_line="$1"
    local expected_fields=$(echo "$OVERHEAD_CSV_HEADER" | tr ',' '\n' | wc -l)
    local actual_fields=$(echo "$data_line" | tr ',' '\n' | wc -l)
    
    # Field count check
    if [[ "$actual_fields" -ne "$expected_fields" ]]; then
        log_error "Data quality check failed: field count mismatch"
        return 1
    fi
    
    # Abnormal format check - only check real problem formats
    if echo "$data_line" | grep -q ",,$\|^,$\|^,\|,$"; then
        log_error "Data quality check failed: empty fields or format errors detected"
        log_debug "Problem data line: $data_line"
        return 1
    fi
    
    return 0
}

# Data cleaning and formatting function
clean_and_format_number() {
    local value="$1"
    local format="$2"  # "int" or "float"
    local original_value="$value"
    
    # Remove all non-numeric and decimal point characters
    value=$(echo "$value" | tr -cd '0-9.')
    
    # Handle multiple decimal points: only keep first decimal point and content before it
    if [[ "$value" == *.*.* ]]; then
        # Find position of first decimal point, only keep up to first decimal point and following digits
        value=$(echo "$value" | sed 's/\([0-9]*\.[0-9]*\)\..*/\1/')
    fi
    
    # Handle edge cases
    if [[ -z "$value" ]] || [[ "$value" == "." ]] || [[ "$value" == ".." ]]; then
        value="0"
    fi
    
    # Remove leading decimal point
    if [[ "$value" == .* ]]; then
        value="0$value"
    fi
    
    # Remove trailing decimal point
    if [[ "$value" == *. ]]; then
        value="${value%.*}"
    fi
    
    # Final validation
    if ! [[ "$value" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        value="0"
    fi
    
    # Format output
    local result
    if [[ "$format" == "int" ]]; then
        result=$(printf "%.0f" "$value" 2>/dev/null || echo "0")
    else
        result=$(printf "%.2f" "$value" 2>/dev/null || echo "0.00")
    fi
    
    # Debug: if input or output is abnormal, log detailed information
    if [[ "$original_value" == *"."*"."* ]] || [[ "$result" == *"."*"."* ]] || [[ "$original_value" == "00" ]]; then
        log_debug "Data cleaning anomaly: input='$original_value' -> output='$result' (format:$format)"
    fi
    
    echo "$result"
}

# Monitoring overhead data collection main function (enhanced - with performance monitoring)
collect_monitoring_overhead_data() {
    local start_time=$(date +%s%3N 2>/dev/null || date +%s)
    local timestamp=$(get_unified_timestamp)

    # Collect monitoring process resource usage
    local monitoring_pids=$(discover_monitoring_processes)
    local monitoring_resources=$(calculate_process_resources "$monitoring_pids" "monitoring")

    local monitoring_cpu=$(echo "$monitoring_resources" | cut -d',' -f1)
    local monitoring_memory_percent=$(echo "$monitoring_resources" | cut -d',' -f2)
    local monitoring_memory_mb=$(echo "$monitoring_resources" | cut -d',' -f3)
    local monitoring_process_count=$(echo "$monitoring_resources" | cut -d',' -f4)

    # Collect blockchain node resource usage
    local blockchain_resources=$(get_blockchain_node_resources)

    local blockchain_cpu=$(echo "$blockchain_resources" | cut -d',' -f1)
    local blockchain_memory_percent=$(echo "$blockchain_resources" | cut -d',' -f2)
    local blockchain_memory_mb=$(echo "$blockchain_resources" | cut -d',' -f3)
    local blockchain_process_count=$(echo "$blockchain_resources" | cut -d',' -f4)

    # Collect system static resources
    local system_static=$(get_system_static_resources)
    local system_cpu_cores=$(echo "$system_static" | cut -d',' -f1)
    local system_memory_gb=$(echo "$system_static" | cut -d',' -f2)
    local system_disk_gb=$(echo "$system_static" | cut -d',' -f3)

    # Collect system dynamic resources
    local system_dynamic=$(get_system_dynamic_resources)
    local system_cpu_usage=$(echo "$system_dynamic" | cut -d',' -f1)
    local system_memory_usage=$(echo "$system_dynamic" | cut -d',' -f2)
    local system_disk_usage=$(echo "$system_dynamic" | cut -d',' -f3)
    local system_cached_gb=$(echo "$system_dynamic" | cut -d',' -f4)
    local system_buffers_gb=$(echo "$system_dynamic" | cut -d',' -f5)
    local system_anon_pages_gb=$(echo "$system_dynamic" | cut -d',' -f6)
    local system_mapped_gb=$(echo "$system_dynamic" | cut -d',' -f7)
    local system_shmem_gb=$(echo "$system_dynamic" | cut -d',' -f8)

    # Refactor all formatting calls - enhance data source validation
    monitoring_cpu=$(clean_and_format_number "$monitoring_cpu" "float")
    monitoring_memory_percent=$(clean_and_format_number "$monitoring_memory_percent" "float")
    monitoring_memory_mb=$(clean_and_format_number "$monitoring_memory_mb" "float")
    monitoring_process_count=$(clean_and_format_number "$monitoring_process_count" "int")

    blockchain_cpu=$(clean_and_format_number "$blockchain_cpu" "float")
    blockchain_memory_percent=$(clean_and_format_number "$blockchain_memory_percent" "float")
    blockchain_memory_mb=$(clean_and_format_number "$blockchain_memory_mb" "float")
    blockchain_process_count=$(clean_and_format_number "$blockchain_process_count" "int")

    # Debug: log system info raw values
    log_debug "System info raw values: CPU='$system_cpu_cores' Memory='$system_memory_gb' Disk='$system_disk_gb'"
    
    system_cpu_cores=$(clean_and_format_number "$system_cpu_cores" "int")
    system_memory_gb=$(clean_and_format_number "$system_memory_gb" "float")
    system_disk_gb=$(clean_and_format_number "$system_disk_gb" "float")
    
    # Debug: log cleaned values
    log_debug "System info after cleaning: CPU='$system_cpu_cores' Memory='$system_memory_gb' Disk='$system_disk_gb'"
    system_cpu_usage=$(clean_and_format_number "$system_cpu_usage" "float")
    system_memory_usage=$(clean_and_format_number "$system_memory_usage" "float")
    system_disk_usage=$(clean_and_format_number "$system_disk_usage" "int")
    system_cached_gb=$(clean_and_format_number "$system_cached_gb" "float")
    system_buffers_gb=$(clean_and_format_number "$system_buffers_gb" "float")
    system_anon_pages_gb=$(clean_and_format_number "$system_anon_pages_gb" "float")
    system_mapped_gb=$(clean_and_format_number "$system_mapped_gb" "float")
    system_shmem_gb=$(clean_and_format_number "$system_shmem_gb" "float")

    # Generate complete data line - ensure all variables have valid values
    local overhead_data_line="${timestamp},${monitoring_cpu},${monitoring_memory_percent},${monitoring_memory_mb},${monitoring_process_count},${blockchain_cpu},${blockchain_memory_percent},${blockchain_memory_mb},${blockchain_process_count},${system_cpu_cores},${system_memory_gb},${system_disk_gb},${system_cpu_usage},${system_memory_usage},${system_disk_usage},${system_cached_gb},${system_buffers_gb},${system_anon_pages_gb},${system_mapped_gb},${system_shmem_gb}"
    
    # Debug: log final data line format
    log_debug "Final data line: $(echo "$overhead_data_line" | cut -c1-150)..."
    
    # Final data integrity validation - only check empty fields
    if [[ "$overhead_data_line" == *",,"* ]]; then
        log_error "Monitoring overhead data format anomaly detected (empty fields): $overhead_data_line"
        return 1
    fi

    log_debug "Monitoring overhead data collection completed: monitoring_processes=${monitoring_process_count}, blockchain_processes=${blockchain_process_count}, system_cpu=${system_cpu_cores}cores"

    # Performance monitoring - measure execution time and resource usage
    local end_time=$(date +%s%3N 2>/dev/null || date +%s)
    local current_resources=$(get_current_process_resources)
    local current_cpu=$(echo "$current_resources" | cut -d',' -f1)
    local current_memory=$(echo "$current_resources" | cut -d',' -f2)

    # Call performance monitoring
    monitor_performance_impact "collect_monitoring_overhead_data" "$start_time" "$end_time" "$current_cpu" "$current_memory"

    # Generate complete data line - ensure all variables have valid values
    local safe_timestamp="${timestamp:-$(date '+%Y-%m-%d %H:%M:%S')}"
    local safe_monitoring_cpu="${monitoring_cpu:-0.00}"
    local safe_monitoring_memory_percent="${monitoring_memory_percent:-0.00}"
    local safe_monitoring_memory_mb="${monitoring_memory_mb:-0.00}"
    local safe_monitoring_process_count="${monitoring_process_count:-0}"
    local safe_blockchain_cpu="${blockchain_cpu:-0.00}"
    local safe_blockchain_memory_percent="${blockchain_memory_percent:-0.00}"
    local safe_blockchain_memory_mb="${blockchain_memory_mb:-0.00}"
    local safe_blockchain_process_count="${blockchain_process_count:-0}"
    local safe_system_cpu_cores="${system_cpu_cores:-0}"
    local safe_system_memory_gb="${system_memory_gb:-0.00}"
    local safe_system_disk_gb="${system_disk_gb:-0.00}"
    local safe_system_cpu_usage="${system_cpu_usage:-0.00}"
    local safe_system_memory_usage="${system_memory_usage:-0.00}"
    local safe_system_disk_usage="${system_disk_usage:-0.00}"
    local safe_system_cached_gb="${system_cached_gb:-0.00}"
    local safe_system_buffers_gb="${system_buffers_gb:-0.00}"
    local safe_system_anon_pages_gb="${system_anon_pages_gb:-0.00}"
    local safe_system_mapped_gb="${system_mapped_gb:-0.00}"
    local safe_system_shmem_gb="${system_shmem_gb:-0.00}"
    
    echo "$safe_timestamp,$safe_monitoring_cpu,$safe_monitoring_memory_percent,$safe_monitoring_memory_mb,$safe_monitoring_process_count,$safe_blockchain_cpu,$safe_blockchain_memory_percent,$safe_blockchain_memory_mb,$safe_blockchain_process_count,$safe_system_cpu_cores,$safe_system_memory_gb,$safe_system_disk_gb,$safe_system_cpu_usage,$safe_system_memory_usage,$safe_system_disk_usage,$safe_system_cached_gb,$safe_system_buffers_gb,$safe_system_anon_pages_gb,$safe_system_mapped_gb,$safe_system_shmem_gb"
}

# Write monitoring overhead log
write_monitoring_overhead_log() {
    # Ensure directory exists
    local log_dir=$(dirname "$MONITORING_OVERHEAD_LOG")
    mkdir -p "$log_dir"
    
    # Atomic file operation
    local temp_file="${MONITORING_OVERHEAD_LOG}.tmp.$$"
    local lock_file="${MONITORING_OVERHEAD_LOG}.lock"
    
    # Acquire file lock
    if ! (set -C; echo $$ > "$lock_file") 2>/dev/null; then
        log_warn "Monitoring overhead log file is locked, skipping this write"
        return 1
    fi
    
    # Check and write header
    if [[ ! -f "$MONITORING_OVERHEAD_LOG" ]] || [[ ! -s "$MONITORING_OVERHEAD_LOG" ]]; then
        if [[ -n "$OVERHEAD_CSV_HEADER" ]]; then
            echo "$OVERHEAD_CSV_HEADER" > "$temp_file"
            log_debug "Creating monitoring overhead log header: $OVERHEAD_CSV_HEADER"
        else
            log_error "OVERHEAD_CSV_HEADER variable not defined, cannot create header"
            return 1
        fi
    else
        # Copy existing content
        cp "$MONITORING_OVERHEAD_LOG" "$temp_file"
    fi
    
    # Collect and validate data
    local overhead_data_line
    if [[ "$ERROR_RECOVERY_ENABLED" == "true" ]]; then
        overhead_data_line=$(enhanced_collect_monitoring_overhead_data)
    else
        overhead_data_line=$(collect_monitoring_overhead_data)
    fi
    
    if [[ -n "$overhead_data_line" ]]; then
        # Data quality check
        if ! validate_data_quality "$overhead_data_line"; then
            log_error "Data quality check failed, skipping this write"
            rm -f "$temp_file"
            rm -f "$lock_file"
            return 1
        fi
        
        # Validate data format (field count)
        local expected_fields=$(echo "$OVERHEAD_CSV_HEADER" | tr ',' '\n' | wc -l)
        local actual_fields=$(echo "$overhead_data_line" | tr ',' '\n' | wc -l)
        
        if [[ "$actual_fields" -eq "$expected_fields" ]]; then
            echo "$overhead_data_line" >> "$temp_file"
            # Atomic replacement
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
    
    # Release file lock
    rm -f "$lock_file"
}

# Configuration validation and health check
validate_monitoring_overhead_config() {
    local validation_errors=()
    local validation_warnings=()

    # Check necessary configuration variables - use standardized array access
    if [[ -z "$MONITORING_PROCESS_NAMES_STR" ]]; then
        validation_errors+=("MONITORING_PROCESS_NAMES_STR not defined or empty")
    fi

    if [[ -z "$BLOCKCHAIN_PROCESS_NAMES_STR" ]]; then
        validation_errors+=("BLOCKCHAIN_PROCESS_NAMES_STR not defined or empty")
    fi

    if [[ -z "$MONITORING_OVERHEAD_LOG" ]]; then
        validation_errors+=("MONITORING_OVERHEAD_LOG variable not defined")
    fi

    if [[ -z "$OVERHEAD_CSV_HEADER" ]]; then
        validation_errors+=("OVERHEAD_CSV_HEADER variable not defined")
    fi

    # Check EBS baseline configuration
    if [[ -z "$DATA_VOL_MAX_IOPS" || -z "$DATA_VOL_MAX_THROUGHPUT" ]]; then
        validation_warnings+=("DATA device baseline not fully configured")
    fi

    if is_accounts_configured; then
        if [[ -z "$ACCOUNTS_VOL_MAX_THROUGHPUT" ]]; then
            validation_warnings+=("ACCOUNTS device configured but baseline missing")
        fi
    fi

    # Check availability of necessary commands
    local required_commands=("pgrep" "ps" "bc" "cut" "grep" "awk")
    for cmd in "${required_commands[@]}"; do
        if ! is_command_available "$cmd"; then
            validation_errors+=("Required command not available: $cmd")
        fi
    done

    # Check log directory writability
    local log_dir=$(dirname "$MONITORING_OVERHEAD_LOG")
    if [[ ! -d "$log_dir" ]]; then
        validation_warnings+=("Monitoring overhead log directory does not exist: $log_dir")
    elif [[ ! -w "$log_dir" ]]; then
        validation_errors+=("Monitoring overhead log directory not writable: $log_dir")
    fi

    # Output validation results
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

# Dynamically generate ENA header - based on ENA_ALLOWANCE_FIELDS configuration
build_ena_header() {
    local header=""
    # Directly use field names from configuration, don't hardcode - use standardized array access
    ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
    for field in "${ena_fields[@]}"; do
        if [[ -n "$header" ]]; then
            header="$header,$field"
        else
            header="$field"
        fi
    done
    echo "$header"
}

# Generate complete CSV header - support conditional ENA fields
generate_csv_header() {
    local basic_header="timestamp,cpu_usage,cpu_usr,cpu_sys,cpu_iowait,cpu_soft,cpu_idle,mem_used,mem_total,mem_usage"
    local device_header=$(generate_all_devices_header)
    local network_header="net_interface,net_rx_mbps,net_tx_mbps,net_total_mbps,net_rx_gbps,net_tx_gbps,net_total_gbps,net_rx_pps,net_tx_pps,net_total_pps"
    local overhead_header="monitoring_iops_per_sec,monitoring_throughput_mibs_per_sec"
    local block_height_header="local_block_height,mainnet_block_height,block_height_diff,local_health,mainnet_health,data_loss"
    local qps_header="current_qps,rpc_latency_ms,qps_data_available"

    # Configuration-driven ENA header generation
    if [[ "$ENA_MONITOR_ENABLED" == "true" ]]; then
        local ena_header=$(build_ena_header)
        echo "$basic_header,$device_header,$network_header,$ena_header,$overhead_header,$block_height_header,$qps_header"
    else
        echo "$basic_header,$device_header,$network_header,$overhead_header,$block_height_header,$qps_header"
    fi
}

# Generate JSON format monitoring data - atomic write version
generate_json_metrics() {
    local timestamp="$1"
    local cpu_data="$2"
    local memory_data="$3"
    local device_data="$4"
    local network_data="$5"
    local ena_data="$6"
    local overhead_data="$7"

    # Parse CSV data into fields needed for JSON
    local cpu_usage=$(echo "$cpu_data" | cut -d',' -f1)
    local mem_usage=$(echo "$memory_data" | cut -d',' -f3)

    # Parse network data to get total traffic
    local net_total_mbps=$(echo "$network_data" | cut -d',' -f4)

    # Calculate network utilization
    local network_util=$(awk "BEGIN {printf \"%.2f\", ($net_total_mbps / $NETWORK_MAX_BANDWIDTH_MBPS) * 100}" 2>/dev/null || echo "0")
    # Limit to within 100%
    network_util=$(awk "BEGIN {printf \"%.2f\", ($network_util > 100) ? 100 : $network_util}" 2>/dev/null || echo "0")

    # Extract EBS info from device data (simplified processing, take first device data)
    local ebs_util=0
    local ebs_latency=0
    if [[ -n "$device_data" ]]; then
        # Device data format (21 fields): r_s,w_s,rkb_s,wkb_s,r_await,w_await,avg_await,aqu_sz,util...
        ebs_util=$(echo "$device_data" | cut -d',' -f9 2>/dev/null || echo "0")      # f9=util
        ebs_latency=$(echo "$device_data" | cut -d',' -f7 2>/dev/null || echo "0")   # f7=avg_await
    fi

    # Atomic write latest_metrics.json (core metrics)
    cat > "${MEMORY_SHARE_DIR}/latest_metrics.json.tmp" << EOF
{
    "timestamp": "$timestamp",
    "cpu_usage": $cpu_usage,
    "memory_usage": $mem_usage,
    "ebs_util": $ebs_util,
    "ebs_latency": $ebs_latency,
    "network_util": $network_util,
    "error_rate": 0
}
EOF
    # Atomic move to final location
    mv "${MEMORY_SHARE_DIR}/latest_metrics.json.tmp" "${MEMORY_SHARE_DIR}/latest_metrics.json"

    # Atomic write unified_metrics.json (detailed metrics)
    cat > "${MEMORY_SHARE_DIR}/unified_metrics.json.tmp" << EOF
{
    "timestamp": "$timestamp",
    "cpu_usage": $cpu_usage,
    "memory_usage": $mem_usage,
    "ebs_util": $ebs_util,
    "ebs_latency": $ebs_latency,
    "network_util": $network_util,
    "error_rate": 0,
    "detailed_data": {
        "cpu_data": "$cpu_data",
        "memory_data": "$memory_data",
        "device_data": "$device_data",
        "network_data": "$network_data",
        "ena_data": "$ena_data",
        "overhead_data": "$overhead_data"
    }
}
EOF
    # Atomic move to final location
    mv "${MEMORY_SHARE_DIR}/unified_metrics.json.tmp" "${MEMORY_SHARE_DIR}/unified_metrics.json"
}

# Log performance data - support conditional ENA data and JSON generation
log_performance_data() {
    local timestamp=$(get_unified_timestamp)
    local cpu_data=$(get_cpu_data)
    local memory_data=$(get_memory_data)
    local device_data=$(get_all_devices_data)
    local network_data=$(get_network_data)
    local overhead_data=$(get_monitoring_overhead)

    # Collect current QPS test data
    local current_qps=0
    local rpc_latency_ms=0.0
    local qps_data_available=false
    
    # Check if there is an active QPS test
    if [[ -f "$TMP_DIR/qps_test_status" ]]; then
        local qps_status_content=$(cat "$TMP_DIR/qps_test_status" 2>/dev/null || echo "")
        if [[ -n "$qps_status_content" ]]; then
            # Extract current QPS value from status file
            current_qps=$(echo "$qps_status_content" | grep -o "qps:[0-9]*" | cut -d: -f2 || echo "0")
            qps_data_available=true
            
            # Try to get latency data from latest vegeta result file
            local latest_vegeta_file=$(ls -t "${VEGETA_RESULTS_DIR}"/vegeta_*qps_*.json 2>/dev/null | head -1)
            if [[ -f "$latest_vegeta_file" ]]; then
                # Check if file is complete (avoid reading file being written)
                if [[ -s "$latest_vegeta_file" ]] && grep -q "}" "$latest_vegeta_file" 2>/dev/null; then
                    rpc_latency_ms=$(python3 -c "
import json, sys
try:
    with open('$latest_vegeta_file', 'r') as f:
        data = json.load(f)
    latency_ns = data.get('latencies', {}).get('mean', 0)
    print(latency_ns / 1000000)  # Convert to milliseconds
except:
    print(0.0)
" 2>/dev/null | tr -d '\n\r' || echo "0.0")
                fi
            fi
        fi
    fi

    # Get block height data (if block_height monitoring is enabled)
    local block_height_data=""
    if [[ -n "$BLOCK_HEIGHT_DATA_FILE" && -f "$BLOCK_HEIGHT_DATA_FILE" ]]; then
        # Read latest block_height data
        local latest_block_data=$(tail -1 "$BLOCK_HEIGHT_DATA_FILE" 2>/dev/null)
        if [[ -n "$latest_block_data" && "$latest_block_data" != *"timestamp"* ]]; then
            # Extract block_height related fields (skip timestamp) - data is already in numeric format
            block_height_data=$(echo "$latest_block_data" | cut -d',' -f2-7)
        else
            block_height_data="0,0,0,1,1,0"  # Default values: all numeric, health status is 1
        fi
    else
        block_height_data="0,0,0,1,1,0"  # Default values: all numeric, health status is 1
    fi

    # Conditionally add ENA data
    local ena_data=""
    if [[ "$ENA_MONITOR_ENABLED" == "true" ]]; then
        ena_data=$(get_ena_allowance_data)
        
        # Add ENA data validation and debugging
        log_debug "ENA data debug: '$ena_data'"
        log_debug "ENA data length: ${#ena_data}"
        
        # Validate ENA data format (only contains numbers and commas)
        if [[ ! "$ena_data" =~ ^[0-9,]+$ ]]; then
            log_error "ENA data format anomaly: '$ena_data'"
            log_error "First 100 chars: '$(echo "$ena_data" | cut -c1-100)'"
            
            # Replace abnormal data with default values
            local field_count=$(echo "$ENA_ALLOWANCE_FIELDS_STR" | wc -w)
            ena_data=$(printf "0,%.0s" $(seq 1 $field_count) | sed 's/,$//')
            log_error "Using default ENA data: '$ena_data'"
        fi
        
        # Clean newlines and special characters from all variables
        current_qps=$(echo "$current_qps" | tr -d '\n\r' | head -c 20)
        rpc_latency_ms=$(echo "$rpc_latency_ms" | tr -d '\n\r' | head -c 20)
        qps_data_available=$(echo "$qps_data_available" | tr -d '\n\r' | head -c 10)
        
        local data_line="$timestamp,$cpu_data,$memory_data,$device_data,$network_data,$ena_data,$overhead_data,$block_height_data,$current_qps,$rpc_latency_ms,$qps_data_available"
    else
        # Clean newlines and special characters from all variables
        current_qps=$(echo "$current_qps" | tr -d '\n\r' | head -c 20)
        rpc_latency_ms=$(echo "$rpc_latency_ms" | tr -d '\n\r' | head -c 20)
        qps_data_available=$(echo "$qps_data_available" | tr -d '\n\r' | head -c 10)
        
        local data_line="$timestamp,$cpu_data,$memory_data,$device_data,$network_data,$overhead_data,$block_height_data,$current_qps,$rpc_latency_ms,$qps_data_available"
    fi
    
    # Final data line validation
    log_debug "Final data line length: ${#data_line}"
    if [[ ${#data_line} -gt 10000 ]]; then
        log_error "Data line abnormally long: ${#data_line} characters"
        log_error "First 200 chars of data line: '$(echo "$data_line" | cut -c1-200)'"
    fi

    # If CSV file doesn't exist or is empty, write header first
    if [[ ! -f "$UNIFIED_LOG" ]] || [[ ! -s "$UNIFIED_LOG" ]]; then
        local csv_header=$(generate_csv_header)
        echo "$csv_header" > "$UNIFIED_LOG"
    fi

    # Use concurrent-safe CSV writing
    if safe_write_csv "$UNIFIED_LOG" "$data_line"; then
        log_debug "CSV data safely written: $UNIFIED_LOG"
    else
        echo "ERROR: CSV data write failed: $UNIFIED_LOG" >&2
        return 1
    fi

    # Write separate monitoring overhead log
    write_monitoring_overhead_log

    # Periodic performance analysis (analyze once every 100 records)
    local sample_count_file="${MEMORY_SHARE_DIR}/sample_count"
    local current_count=1

    if [[ -f "$sample_count_file" ]]; then
        current_count=$(cat "$sample_count_file" 2>/dev/null || echo "1")
        current_count=$((current_count + 1))
    fi

    echo "$current_count" > "$sample_count_file"

    # Perform performance analysis every 100 samples
    if (( current_count % 100 == 0 )); then
        log_info "🔍 Executing periodic performance analysis - sample $current_count"
        auto_performance_optimization_advisor
    fi

    # Generate complete report every 1000 samples
    if (( current_count % 1000 == 0 )); then
        log_info "📊 Generating performance impact report - sample $current_count"
        generate_performance_impact_report
    fi

    # Generate JSON file
    generate_json_metrics "$timestamp" "$cpu_data" "$memory_data" "$device_data" "$network_data" "$ena_data" "$overhead_data"
}

# Start unified monitoring - support follow QPS test mode
start_unified_monitoring() {
    local duration="$1"
    local interval=${2:-$MONITOR_INTERVAL}

    # =====================================================================
    # Monitoring system initialization phase
    # =====================================================================
    
    log_info "🚀 Starting unified performance monitoring system..."
    
    # Step 1: Initialize command cache - key performance optimization step
    log_info "📋 Step 1: Initialize system command cache"
    init_command_cache

    # Step 2: Initialize error handling system
    log_info "🛡️ Step 2: Initialize error handling system"
    initialize_error_handling_system

    START_TIME=$(get_unified_timestamp)

    # =====================================================================
    # Monitoring configuration information display
    # =====================================================================
    
    echo ""
    echo "🎯 ===== Unified Performance Monitoring System ====="
    echo "📅 Start time: $START_TIME"
    echo "⏱️  Monitoring interval: ${interval} seconds"

    if [[ "$duration" -eq 0 ]]; then
        echo "🔄 Run mode: Follow framework lifecycle (no time limit)"
        echo "🎛️  Control file: $TMP_DIR/qps_test_status"
    else
        echo "⏰ Run mode: Timed monitoring (${duration} seconds)"
    fi

    echo "📊 Data file: $UNIFIED_LOG"
    
    # Display system capability detection results
    echo ""
    echo "🔧 ===== System Capability Detection ====="

    # Display configuration status
    log_info "DATA device: $LEDGER_DEVICE"

    if is_accounts_configured; then
        log_info "ACCOUNTS device: $ACCOUNTS_DEVICE Volume type: $ACCOUNTS_VOL_TYPE"
    else
        echo "ℹ️  ACCOUNTS device not configured"
    fi

    if [[ -n "$NETWORK_INTERFACE" ]]; then
        log_info "Network interface: $NETWORK_INTERFACE"
    fi

    # Display ENA monitoring status
    if [[ "$ENA_MONITOR_ENABLED" == "true" ]]; then
        log_info "ENA monitoring: Enabled - AWS environment"
    else
        echo "ℹ️  ENA monitoring: Disabled - Non-AWS environment"
    fi

    # Create CSV header
    local csv_header=$(generate_csv_header)
    echo "$csv_header" > "$UNIFIED_LOG"

    # Create latest file symlink for bottleneck detection use
    local latest_csv="${LOGS_DIR}/performance_latest.csv"
    ln -sf "$(basename "$UNIFIED_LOG")" "$latest_csv"

    log_info "CSV header created - $(echo "$csv_header" | tr ',' '\n' | wc -l) fields"
    log_info "Latest file link created: $latest_csv"
    echo ""

    # Record monitoring process PID
    MONITOR_PIDS+=($BASHPID)

    # =====================================================================
    # Main monitoring loop
    # =====================================================================
    
    echo ""
    echo "🔄 ===== Starting Monitoring Loop ====="
    
    local start_time=$(date +%s)
    local sample_count=0
    local last_status_time=0
    local status_interval=30  # Display status every 30 seconds

    echo "⏰ Starting data collection..."

    # Unified monitoring loop logic - choose control method based on duration parameter
    if [[ "$duration" -eq 0 ]]; then
        # duration=0 means follow framework lifecycle - check status file
        while [[ -f "$TMP_DIR/qps_test_status" ]]; do
            # Collect unified monitoring data
            log_debug "📊 Data collection #${sample_count} starting..."
            local current_system_load=$(assess_system_load)

            log_performance_data
            sample_count=$((sample_count + 1))
            
            # Periodically display monitoring status
            local current_time=$(date +%s)
            if [[ $((current_time - last_status_time)) -ge $status_interval ]]; then
                local elapsed=$((current_time - start_time))
                echo "📈 Monitoring status: Collected $sample_count data points, runtime ${elapsed}s (following framework lifecycle)"
                last_status_time=$current_time
            fi

            # Progress report
            if (( sample_count % 12 == 0 )); then
                local current_time=$(date +%s)
                local elapsed=$((current_time - start_time))
                local avg_interval=$(awk -v e="$elapsed" -v s="$sample_count" 'BEGIN {printf "%.2f", (s > 0) ? e / s : 0}' 2>/dev/null || echo "N/A")
                echo "📈 Monitoring status: Collected $sample_count samples, runtime ${elapsed}s, average interval ${avg_interval}s (following framework lifecycle)"
            fi

            # Wait until next scheduled time
            local now=$(date +%s)
            local next_run=$((start_time + sample_count * CURRENT_MONITOR_INTERVAL))
            if (( now < next_run )); then
                sleep $((next_run - now))
            fi
        done
    else
            # Fixed duration logic
            local end_time=$((start_time + duration))

            while [[ $(date +%s) -lt $end_time ]]; do
            # Collect unified monitoring data
            log_debug "📊 Data collection #${sample_count} starting..."
            local current_system_load=$(assess_system_load)

            log_performance_data
            sample_count=$((sample_count + 1))
            
            # Periodically display monitoring status
            local current_time=$(date +%s)
            if [[ $((current_time - last_status_time)) -ge $status_interval ]]; then
                local elapsed=$((current_time - start_time))
                local remaining=$((end_time - current_time))
                local progress_percent=$(awk "BEGIN {printf "%.1f", $elapsed * 100 / $duration}" 2>/dev/null || echo "N/A")
                echo "📈 Monitoring status: Collected $sample_count data points, progress ${progress_percent}%, runtime ${elapsed}s, remaining ${remaining}s"
                last_status_time=$current_time
            fi

            # Progress report
            if (( sample_count % 12 == 0 )); then
                local current_time=$(date +%s)
                local elapsed=$((current_time - start_time))
                local remaining=$((end_time - current_time))
                local avg_interval=$(awk -v e="$elapsed" -v s="$sample_count" 'BEGIN {printf "%.2f", (s > 0) ? e / s : 0}' 2>/dev/null || echo "N/A")
                local progress_percent=$(awk -v e="$elapsed" -v d="$duration" 'BEGIN {printf "%.1f", (d > 0) ? e * 100 / d : 0}' 2>/dev/null || echo "N/A")
                echo "📈 Monitoring status: Collected $sample_count samples, progress ${progress_percent}%, runtime ${elapsed}s, remaining ${remaining}s, average interval ${avg_interval}s"
            fi

            # Wait until next scheduled time
            local now=$(date +%s)
            local next_run=$((start_time + sample_count * CURRENT_MONITOR_INTERVAL))
            if (( now < next_run )); then
                sleep $((next_run - now))
            fi
        done
    fi

    END_TIME=$(get_unified_timestamp)

    # =====================================================================
    # Monitoring completion statistics report
    # =====================================================================
    
    local final_time=$(date +%s)
    local total_elapsed=$((final_time - start_time))
    local avg_sample_interval=$(awk -v t="$total_elapsed" -v s="$sample_count" 'BEGIN {printf "%.2f", (s > 0) ? t / s : 0}' 2>/dev/null || echo "N/A")
    local file_size=$(du -h "$UNIFIED_LOG" 2>/dev/null | cut -f1 || echo "unknown")
    local line_count=$(wc -l < "$UNIFIED_LOG" 2>/dev/null || echo "unknown")
    
    echo ""
    echo "✅ ===== Unified Performance Monitoring Completed ====="
    echo "📅 Start time: $START_TIME"
    echo "📅 End time: $END_TIME"
    echo "⏱️  Total runtime: ${total_elapsed} seconds"
    echo "📊 Total samples: $sample_count times"
    echo "📈 Average sampling interval: ${avg_sample_interval} seconds"
    echo "📄 Data file: $UNIFIED_LOG"
    echo "📋 Data statistics: $line_count lines, file size $file_size"
    
    # Performance efficiency assessment
    if [[ "$sample_count" -gt 0 ]] && [[ "$total_elapsed" -gt 0 ]]; then
        local efficiency=$(awk -v s="$sample_count" -v t="$total_elapsed" 'BEGIN {printf "%.1f", (t > 0) ? s * 100 / t : 0}' 2>/dev/null || echo "N/A")
        echo "⚡ Monitoring efficiency: ${efficiency} samples/second"
    fi
    
    # Data quality assessment
    if [[ "$line_count" != "unknown" ]] && [[ "$sample_count" -gt 0 ]]; then
        local data_integrity=$(awk -v l="$line_count" -v s="$sample_count" 'BEGIN {printf "%.1f", (s > 0) ? (l - 1) * 100 / s : 0}' 2>/dev/null || echo "N/A")
        echo "📊 Data integrity: ${data_integrity}% (${line_count} data lines/${sample_count} samples)"
    fi
    
    echo ""
    echo "🧹 ===== Cleaning System Resources ====="
}

# Stop monitoring - prevent duplicate calls
STOP_MONITORING_CALLED=false
stop_unified_monitoring() {
    # Prevent duplicate calls
    if [[ "$STOP_MONITORING_CALLED" == "true" ]]; then
        return 0
    fi
    STOP_MONITORING_CALLED=true

    echo "🛑 Stopping unified monitoring..."
    
    local cleanup_count=0
    local cleanup_errors=0

    # Terminate all related processes
    echo "🔄 Cleaning up monitoring processes..."
    for pid in "${MONITOR_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            if kill "$pid" 2>/dev/null; then
                cleanup_count=$((cleanup_count + 1))
                log_debug "✅ Terminated process PID: $pid"
            else
                cleanup_errors=$((cleanup_errors + 1))
                log_debug "❌ Unable to terminate process PID: $pid"
            fi
        fi
    done

    # Generate error recovery report
    if [[ "$ERROR_RECOVERY_ENABLED" == "true" ]]; then
        echo "📋 Generating error recovery report..."
        generate_error_recovery_report
    fi

    # Cleanup completion summary
    echo "✅ Resource cleanup completed: Terminated $cleanup_count processes"
    if [[ "$cleanup_errors" -gt 0 ]]; then
        echo "⚠️  Cleanup warning: $cleanup_errors processes could not be terminated normally"
    fi
    
    log_info "Unified monitoring stopped"
}

# Get monitoring time range (for use by other scripts)
get_monitoring_time_range() {
    echo "start_time=$START_TIME"
    echo "end_time=$END_TIME"
}

# Main function
main() {
    echo "🔧 Unified Performance Monitor"
    echo "=================="
    echo ""

    # Initialize
    if ! init_monitoring; then
        exit 1
    fi

    # Parse parameters - add follow QPS test mode
    local duration=0  # 0 means run indefinitely, stopped by external control
    local interval=$MONITOR_INTERVAL
    local background=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--duration)
                duration="$2"
                shift 2
                ;;
            -i|--interval)
                interval="$2"
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
                echo "  -d, --duration SECONDS    Monitor duration, 0=follow framework lifecycle, default: 0"
                echo "  -i, --interval SECONDS    Monitor interval, default: $MONITOR_INTERVAL"
                echo "  -b, --background          Run in background"
                echo "  -h, --help               Show help"
                echo ""
                echo "Features:"
                echo "  ✅ Unified monitoring entry, eliminate duplicate monitoring"
                echo "  ✅ Standard time format: $TIMESTAMP_FORMAT"
                echo "  ✅ Complete metric coverage: CPU, Memory, EBS, Network"
                echo "  ✅ Real monitoring overhead statistics"
                echo "  ✅ Unified field naming convention"
                echo "  ✅ Follow QPS test lifecycle"
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
        # Background call logic, uniformly use duration=0 follow framework lifecycle mode
        nohup "$0" -i "$interval" > "${LOGS_DIR}/unified_monitor.log" 2>&1 &
        echo "Background process PID: $!"
        echo "Log file: ${LOGS_DIR}/unified_monitor.log"
        echo "Data file: $UNIFIED_LOG"
    else
        # Set signal handling
        trap stop_unified_monitoring EXIT INT TERM

        start_unified_monitoring "$duration" "$interval"
    fi
}

# Memory calculation helper function
get_cached_total_memory() {
    if [[ -z "${SYSTEM_TOTAL_MEMORY_MB:-}" ]]; then
        SYSTEM_TOTAL_MEMORY_MB=$(free -m | awk 'NR==2{print $2}' 2>/dev/null || echo "8192")
        export SYSTEM_TOTAL_MEMORY_MB
        log_debug "Cached system total memory: ${SYSTEM_TOTAL_MEMORY_MB}MB"
    fi
    echo "$SYSTEM_TOTAL_MEMORY_MB"
}

# Memory percentage calculation function
calculate_memory_percentage() {
    local memory_usage_mb="$1"
    local total_memory_mb="$2"
    
    if [[ "$total_memory_mb" -eq 0 ]]; then
        echo "0"
        return
    fi
    
    local memory_percent=$(awk "BEGIN {printf \"%.2f\", $memory_usage_mb * 100 / $total_memory_mb}" 2>/dev/null || echo "0")
    echo "$memory_percent"
}

# Basic configuration validation mechanism
basic_config_check() {
    local errors=()
    
    # Check critical configuration variables
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
    
    # Execute EBS threshold validation
    if ! validate_ebs_thresholds; then
        return 1
    fi
    
    return 0
}

# EBS configuration validation
validate_ebs_thresholds() {
    local errors=()
    
    # Validate EBS threshold configuration
    if [[ -n "${BOTTLENECK_EBS_IOPS_THRESHOLD:-}" ]]; then
        if ! [[ "$BOTTLENECK_EBS_IOPS_THRESHOLD" =~ ^[0-9]+$ ]] || [[ "$BOTTLENECK_EBS_IOPS_THRESHOLD" -lt 50 ]] || [[ "$BOTTLENECK_EBS_IOPS_THRESHOLD" -gt 100 ]]; then
            errors+=("BOTTLENECK_EBS_IOPS_THRESHOLD value invalid: $BOTTLENECK_EBS_IOPS_THRESHOLD (should be 50-100)")
        fi
    fi
    
    if [[ -n "${BOTTLENECK_EBS_THROUGHPUT_THRESHOLD:-}" ]]; then
        if ! [[ "$BOTTLENECK_EBS_THROUGHPUT_THRESHOLD" =~ ^[0-9]+$ ]] || [[ "$BOTTLENECK_EBS_THROUGHPUT_THRESHOLD" -lt 50 ]] || [[ "$BOTTLENECK_EBS_THROUGHPUT_THRESHOLD" -gt 100 ]]; then
            errors+=("BOTTLENECK_EBS_THROUGHPUT_THRESHOLD value invalid: $BOTTLENECK_EBS_THROUGHPUT_THRESHOLD (should be 50-100)")
        fi
    fi
    
    if [[ -n "${BOTTLENECK_MEMORY_THRESHOLD:-}" ]]; then
        if ! [[ "$BOTTLENECK_MEMORY_THRESHOLD" =~ ^[0-9]+$ ]] || [[ "$BOTTLENECK_MEMORY_THRESHOLD" -lt 70 ]] || [[ "$BOTTLENECK_MEMORY_THRESHOLD" -gt 95 ]]; then
            errors+=("BOTTLENECK_MEMORY_THRESHOLD value invalid: $BOTTLENECK_MEMORY_THRESHOLD (should be 70-95)")
        fi
    fi
    
    if [[ ${#errors[@]} -gt 0 ]]; then
        echo "❌ EBS threshold configuration validation failed:" >&2
        printf '  - %s\n' "${errors[@]}" >&2
        return 1
    fi
    
    echo "✅ EBS threshold configuration validation passed"
    return 0
}

# Concurrent-safe CSV write function
safe_write_csv() {
    local csv_file="$1"
    local csv_data="$2"
    local lock_file="${csv_file}.lock"
    local max_wait=30
    local wait_count=0
    
    # Check parameters
    if [[ -z "$csv_file" || -z "$csv_data" ]]; then
        echo "ERROR: safe_write_csv: Missing required parameters" >&2
        return 1
    fi
    
    # Wait for lock release
    while [[ -f "$lock_file" && $wait_count -lt $max_wait ]]; do
        sleep 0.1
        ((wait_count++))
    done
    
    # If wait timeout, detect zombie lock and force delete
    if [[ $wait_count -ge $max_wait ]]; then
        local lock_pid=$(cat "$lock_file" 2>/dev/null)
        if [[ -n "$lock_pid" ]] && ! kill -0 "$lock_pid" 2>/dev/null; then
            echo "WARNING: Zombie lock file detected, force deleting: $lock_file (PID: $lock_pid)" >&2
            rm -f "$lock_file"
        else
            echo "WARNING: CSV write lock timeout, force deleting lock file: $lock_file" >&2
            rm -f "$lock_file"
        fi
    fi
    
    # Create lock file
    echo $$ > "$lock_file"
    
    # Atomic write CSV data
    {
        echo "$csv_data" >> "$csv_file"
    } 2>/dev/null
    
    local write_result=$?
    
    # Delete lock file
    rm -f "$lock_file"
    
    if [[ $write_result -eq 0 ]]; then
        return 0
    else
        echo "ERROR: CSV write failed: $csv_file" >&2
        return 1
    fi
}

enhanced_collect_monitoring_overhead_data() {
    if [[ "$ERROR_RECOVERY_ENABLED" == "true" ]]; then
        safe_execute "collect_monitoring_overhead_data" "$@"
    else
        collect_monitoring_overhead_data "$@"
    fi
}

# Error recovery status report
generate_error_recovery_report() {
    local report_file="${LOGS_DIR}/error_recovery_report_${SESSION_TIMESTAMP}.txt"

    log_info "Generating error recovery report: $report_file"

    {
        echo "# Monitoring System Error Recovery Report"
        echo "Generated: $(date)"
        echo "Error log: $ERROR_LOG"
        echo ""

        echo "## Error Statistics"
        if [[ ${#ERROR_COUNTERS[@]} -gt 0 ]]; then
            for func_name in "${!ERROR_COUNTERS[@]}"; do
                echo "- $func_name: ${ERROR_COUNTERS[$func_name]} errors"
            done
        else
            echo "- No error records"
        fi

        echo ""
        echo "## Recovery Attempt Statistics"
        if [[ ${#RECOVERY_ATTEMPTS[@]} -gt 0 ]]; then
            for func_name in "${!RECOVERY_ATTEMPTS[@]}"; do
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

# Monitoring system integrity check
monitoring_system_integrity_check() {
    log_info "🔍 Executing monitoring system integrity check..."

    local integrity_issues=()

    # Check critical files
    local critical_files=("$UNIFIED_LOG" "$MONITORING_OVERHEAD_LOG")
    for file in "${critical_files[@]}"; do
        if [[ -n "$file" ]] && [[ -f "$file" ]]; then
            if [[ ! -r "$file" ]]; then
                integrity_issues+=("File not readable: $file")
            fi
            if [[ ! -w "$file" ]]; then
                integrity_issues+=("File not writable: $file")
            fi
        fi
    done

    # Check configuration integrity
    local required_vars=("LOGS_DIR" "MONITOR_INTERVAL" "LEDGER_DEVICE")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            integrity_issues+=("Required configuration variable not set: $var")
        fi
    done

    # Check process configuration - use standardized array access
    if [[ -z "$MONITORING_PROCESS_NAMES_STR" ]]; then
        integrity_issues+=("Monitoring process name configuration is empty")
    fi

    # Check permissions
    if [[ ! -w "$LOGS_DIR" ]]; then
        integrity_issues+=("Insufficient log directory permissions: $LOGS_DIR")
    fi

    # Report integrity status
    if [[ ${#integrity_issues[@]} -eq 0 ]]; then
        log_info "✅ Monitoring system integrity check passed"
        return 0
    else
        log_warn "⚠️  Found ${#integrity_issues[@]} integrity issues:"
        for issue in "${integrity_issues[@]}"; do
            log_warn "  - $issue"
        done
        return 1
    fi
}

# Auto-fix functionality
auto_fix_common_issues() {
    log_info "🔧 Attempting to auto-fix common issues..."

    local fixes_applied=0

    # Fix log directory permissions
    if [[ ! -w "$LOGS_DIR" ]]; then
        log_info "Fixing log directory permissions..."
        if mkdir -p "$LOGS_DIR" 2>/dev/null && chmod 755 "$LOGS_DIR" 2>/dev/null; then
            log_info "✅ Log directory permissions fixed"
            fixes_applied=$((fixes_applied + 1))
        else
            log_warn "❌ Unable to fix log directory permissions"
        fi
    fi

    # Fix log file permissions
    for log_file in "$UNIFIED_LOG" "$MONITORING_OVERHEAD_LOG" "$PERFORMANCE_LOG" "$ERROR_LOG"; do
        if [[ -n "$log_file" ]] && [[ -f "$log_file" ]] && [[ ! -w "$log_file" ]]; then
            log_info "Fixing log file permissions: $log_file"
            if chmod 644 "$log_file" 2>/dev/null; then
                log_info "✅ Log file permissions fixed: $log_file"
                fixes_applied=$((fixes_applied + 1))
            else
                log_warn "❌ Unable to fix log file permissions: $log_file"
            fi
        fi
    done

    # Clean disk space
    local disk_usage=$(df "$LOGS_DIR" 2>/dev/null | awk 'NR==2 {print $5}' | sed 's/%//' || echo "0")
    if [[ $disk_usage -gt 90 ]]; then
        log_info "Cleaning disk space..."
        local cleaned_files=0

        # Clean log files older than 7 days
        if find "$LOGS_DIR" -name "*.log" -mtime +7 -delete 2>/dev/null; then
            cleaned_files=$((cleaned_files + 1))
        fi

        # Clean CSV files older than 3 days
        if find "$LOGS_DIR" -name "*.csv" -mtime +3 -delete 2>/dev/null; then
            cleaned_files=$((cleaned_files + 1))
        fi

        if [[ $cleaned_files -gt 0 ]]; then
            log_info "✅ Old log files cleaned"
            fixes_applied=$((fixes_applied + 1))
        fi
    fi

    log_info "Auto-fix completed, applied $fixes_applied fixes"
    return $fixes_applied
}

# Error handling system initialization
initialize_error_handling_system() {
    if [[ "$ERROR_RECOVERY_ENABLED" != "true" ]]; then
        log_info "Error recovery system disabled"
        return 0
    fi

    log_info "🚀 Initializing error handling system..."

    # Create error log file
    if [[ ! -f "$ERROR_LOG" ]]; then
        echo "timestamp,function_name,error_code,error_message,consecutive_count" > "$ERROR_LOG"
        log_info "Error log file created: $ERROR_LOG"
    fi

    # System health check removed - conflicts with extreme testing philosophy

    # Execute integrity check
    monitoring_system_integrity_check

    # Attempt auto-fix
    auto_fix_common_issues

    log_info "✅ Error handling system initialization completed"
}

# Script entry point - only call main function when executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
