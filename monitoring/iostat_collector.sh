#!/bin/bash
# =====================================================================
# iostat Data Collector
# =====================================================================
# Unified iostat data collection and processing logic
# Eliminate empirical values, calculate precisely based on real-time data
# =====================================================================

# Safely load configuration file to avoid readonly variable conflicts
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "Warning: Configuration file loading failed, using default configuration"
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi
source "$(dirname "${BASH_SOURCE[0]}")/../utils/ebs_converter.sh"

# Load logging functions
source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh" 2>/dev/null || {
    # Provide simple alternatives if logging functions are unavailable
    log_warn() { echo "⚠️ $*" >&2; }
    log_debug() { echo "🔍 $*" >&2; }
}

# Get complete iostat data
get_iostat_data() {
    local device="$1"
    local logical_name="$2"  # data or accounts
    
    if [[ -z "$device" || -z "$logical_name" ]]; then
        echo "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"
        return
    fi
    
    # Implement true iostat continuous sampling
    local monitor_rate=${EBS_MONITOR_RATE:-1}
    local iostat_pid_file="/tmp/iostat_${device}_${logical_name}.pid"
    local iostat_data_file="/tmp/iostat_${device}_${logical_name}.data"
    
    # Check if continuous sampling process already exists
    if [[ ! -f "$iostat_pid_file" ]] || ! kill -0 "$(cat "$iostat_pid_file" 2>/dev/null)" 2>/dev/null; then
        # Start continuous sampling process
        if [[ "$(uname -s)" == "Linux" ]]; then
            iostat -dx "$monitor_rate" > "$iostat_data_file" &
            local iostat_pid=$!
            echo "$iostat_pid" > "$iostat_pid_file"
            log_debug "Started iostat continuous sampling: $device, PID: $iostat_pid, Rate: ${monitor_rate}s, Data file: $iostat_data_file"
        else
            log_warn "iostat functionality only available in Linux environment, current system: $(uname -s)"
            return 1
        fi
    fi
    
    # Get latest device data line
    local device_stats=$(tail -n 20 "$iostat_data_file" 2>/dev/null | awk "/^${device}[[:space:]]/ {latest=\$0} END {print latest}")
    
    if [[ -z "$device_stats" ]]; then
        echo "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"
        return
    fi
    
    local fields=($device_stats)
    
    # Extract iostat fields (eliminate hardcoded indices)
    local r_s=${fields[1]:-0}
    local rkb_s=${fields[2]:-0}
    local rrqm_s=${fields[3]:-0}
    local rrqm_pct=${fields[4]:-0}
    local r_await=${fields[5]:-0}
    local rareq_sz=${fields[6]:-0}
    local w_s=${fields[7]:-0}
    local wkb_s=${fields[8]:-0}
    local wrqm_s=${fields[9]:-0}
    local wrqm_pct=${fields[10]:-0}
    local w_await=${fields[11]:-0}
    local wareq_sz=${fields[12]:-0}
    local aqu_sz=${fields[21]:-0}
    local util=${fields[22]:-0}
    
    # Calculate derived metrics (based on real-time data, no empirical values)
    local total_iops=$(awk "BEGIN {printf \"%.2f\", $r_s + $w_s}" 2>/dev/null || echo "0")
    local total_throughput_kbs=$(awk "BEGIN {printf \"%.2f\", $rkb_s + $wkb_s}" 2>/dev/null || echo "0")
    local total_throughput_mibs=$(awk "BEGIN {printf \"%.2f\", $total_throughput_kbs / 1024}" 2>/dev/null || echo "0")
    
    # Calculate separate read/write throughput (KB/s → MiB/s)
    local read_throughput_mibs=$(awk "BEGIN {printf \"%.2f\", $rkb_s / 1024}" 2>/dev/null || echo "0")
    local write_throughput_mibs=$(awk "BEGIN {printf \"%.2f\", $wkb_s / 1024}" 2>/dev/null || echo "0")
    
    # Calculate AWS standard throughput
    local aws_standard_throughput_mibs="0"
    if command -v convert_to_aws_standard_throughput >/dev/null 2>&1; then
        # Calculate weighted average IO size
        local weighted_avg_io_kib
        if [[ $(awk "BEGIN {print ($total_iops > 0) ? 1 : 0}") -eq 1 ]]; then
            weighted_avg_io_kib=$(awk "BEGIN {printf \"%.2f\", $total_throughput_kbs / $total_iops}" 2>/dev/null || echo "0")
        else
            weighted_avg_io_kib="0"
        fi
        
        if [[ "$weighted_avg_io_kib" != "0" ]]; then
            aws_standard_throughput_mibs=$(convert_to_aws_standard_throughput "$total_throughput_mibs" "$weighted_avg_io_kib")
        else
            aws_standard_throughput_mibs="$total_throughput_mibs"  # Use raw value if average IO size cannot be calculated
        fi
    else
        log_debug "convert_to_aws_standard_throughput function unavailable, using raw throughput value"
        aws_standard_throughput_mibs="$total_throughput_mibs"
    fi
    
    local avg_await=$(awk "BEGIN {printf \"%.2f\", ($r_await + $w_await) / 2}" 2>/dev/null || echo "0")
    
    # Calculate average I/O size (based on real-time data)
    local avg_io_kib
    if [[ $(awk "BEGIN {print ($total_iops > 0) ? 1 : 0}") -eq 1 ]]; then
        avg_io_kib=$(awk "BEGIN {printf \"%.2f\", $total_throughput_kbs / $total_iops}" 2>/dev/null || echo "0")
    else
        avg_io_kib="0"
    fi
    
    # Calculate AWS standard IOPS (based on real-time data)
    local aws_standard_iops
    if [[ $(awk "BEGIN {print ($avg_io_kib > 0) ? 1 : 0}") -eq 1 ]]; then
        aws_standard_iops=$(convert_to_aws_standard_iops "$total_iops" "$avg_io_kib")
    else
        aws_standard_iops="$total_iops"
    fi
    
    # Return complete data (21 fields)
    echo "$r_s,$w_s,$rkb_s,$wkb_s,$r_await,$w_await,$avg_await,$aqu_sz,$util,$rrqm_s,$wrqm_s,$rrqm_pct,$wrqm_pct,$rareq_sz,$wareq_sz,$total_iops,$aws_standard_iops,$read_throughput_mibs,$write_throughput_mibs,$total_throughput_mibs,$aws_standard_throughput_mibs"
}

# Generate CSV header for device
generate_device_header() {
    local device="$1"
    local logical_name="$2"
    
    # Use unified naming convention {logical_name}_{device_name}_{metric}
    # DATA device uses data prefix, ACCOUNTS device uses accounts prefix
    local prefix
    case "$logical_name" in
        "data") prefix="data_${device}" ;;
        "accounts") prefix="accounts_${device}" ;;
        *) prefix="${logical_name}_${device}" ;;
    esac
    
    echo "${prefix}_r_s,${prefix}_w_s,${prefix}_rkb_s,${prefix}_wkb_s,${prefix}_r_await,${prefix}_w_await,${prefix}_avg_await,${prefix}_aqu_sz,${prefix}_util,${prefix}_rrqm_s,${prefix}_wrqm_s,${prefix}_rrqm_pct,${prefix}_wrqm_pct,${prefix}_rareq_sz,${prefix}_wareq_sz,${prefix}_total_iops,${prefix}_aws_standard_iops,${prefix}_read_throughput_mibs,${prefix}_write_throughput_mibs,${prefix}_total_throughput_mibs,${prefix}_aws_standard_throughput_mibs"
}

# Get data for all configured devices
get_all_devices_data() {
    local device_data=""
    
    # DATA device - use data as logical name prefix (required)
    if [[ -n "$DATA_VOL_TYPE" ]]; then
        local data_stats=$(get_iostat_data "$LEDGER_DEVICE" "data")
        device_data="$data_stats"
    else
        log_error "DATA_VOL_TYPE not configured - this is required"
        return 1
    fi
    
    # ACCOUNTS device - use accounts as logical name prefix
    if is_accounts_configured; then
        local accounts_stats=$(get_iostat_data "$ACCOUNTS_DEVICE" "accounts")
        if [[ -n "$device_data" ]]; then
            device_data="${device_data},$accounts_stats"
        else
            device_data="$accounts_stats"
        fi
    fi
    
    echo "$device_data"
}

# Generate CSV header for all devices
generate_all_devices_header() {
    local device_header=""
    
    # DATA device header - use data as logical name prefix (required)
    if [[ -n "$DATA_VOL_TYPE" ]]; then
        device_header=$(generate_device_header "$LEDGER_DEVICE" "data")
    else
        log_error "DATA_VOL_TYPE not configured - this is required"
        return 1
    fi
    
    # ACCOUNTS device header - use accounts as logical name prefix
    if is_accounts_configured; then
        local accounts_header=$(generate_device_header "$ACCOUNTS_DEVICE" "accounts")
        if [[ -n "$device_header" ]]; then
            device_header="${device_header},$accounts_header"
        else
            device_header="$accounts_header"
        fi
    fi
    
    echo "$device_header"
}

# Validate device availability
validate_devices() {
    local errors=()
    
    # DATA device validation (required)
    if [[ -z "$LEDGER_DEVICE" ]]; then
        errors+=("LEDGER_DEVICE is required but not configured")
    elif [[ ! -b "/dev/$LEDGER_DEVICE" ]]; then
        errors+=("LEDGER_DEVICE /dev/$LEDGER_DEVICE does not exist")
    fi
    
    if [[ -n "$ACCOUNTS_DEVICE" && ! -b "/dev/$ACCOUNTS_DEVICE" ]]; then
        errors+=("ACCOUNTS_DEVICE /dev/$ACCOUNTS_DEVICE does not exist")
    fi
    
    if [[ ${#errors[@]} -gt 0 ]]; then
        printf "❌ Device validation failed:\n"
        printf "  - %s\n" "${errors[@]}"
        return 1
    fi
    
    return 0
}

# If this script is executed directly, run test
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "🔧 iostat Data Collector Test"
    echo "========================="
    
    if validate_devices; then
        echo "✅ Device validation passed"
        echo ""
        echo "📊 CSV Header:"
        echo "timestamp,$(generate_all_devices_header)"
        echo ""
        echo "📊 Current Data:"
        echo "$(date +"$TIMESTAMP_FORMAT"),$(get_all_devices_data)"
    else
        echo "❌ Device validation failed"
        exit 1
    fi
fi
