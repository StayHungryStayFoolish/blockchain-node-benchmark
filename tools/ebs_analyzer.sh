#!/bin/bash
# =====================================================================
# EBS Offline Performance Analyzer
# =====================================================================
# Uses unified logger manager
# =====================================================================

# Safely load configuration file, avoid readonly variable conflicts
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "Warning: Configuration file loading failed, using default configuration"
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi
source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh"

# Initialize unified logger manager
init_logger "ebs_analyzer" $LOG_LEVEL "${LOGS_DIR}/ebs_analyzer.log"

# EBS performance analysis function
analyze_ebs_performance() {
    local csv_file="$1"
    
    if [[ ! -f "$csv_file" ]]; then
        log_error "CSV file does not exist: $csv_file"
        return 1
    fi
    
    log_info "Starting EBS performance data analysis: $csv_file"
    log_debug "Analysis parameters: csv_file=$csv_file"
    
    # Read CSV header, dynamically detect field positions
    local header=$(head -1 "$csv_file")
    local field_names=($(echo "$header" | tr ',' ' '))
    
    # Find DATA device fields
    local data_util_idx=-1
    local data_iops_idx=-1
    local data_throughput_idx=-1
    local data_await_idx=-1
    
    for i in "${!field_names[@]}"; do
        local field="${field_names[$i]}"
        case "$field" in
            # Framework standard format: data_{device_name}_{metric}
            data_${LEDGER_DEVICE}_util) data_util_idx=$i ;;
            data_${LEDGER_DEVICE}_total_iops) data_iops_idx=$i ;;
            data_${LEDGER_DEVICE}_total_throughput_mibs) data_throughput_idx=$i ;;
            data_${LEDGER_DEVICE}_avg_await) data_await_idx=$i ;;
        esac
    done
    
    # Find ACCOUNTS device fields
    local accounts_util_idx=-1
    local accounts_iops_idx=-1
    local accounts_throughput_idx=-1
    local accounts_await_idx=-1
    
    # If ACCOUNTS_DEVICE is not configured, skip ACCOUNTS field matching
    if [[ -n "${ACCOUNTS_DEVICE:-}" ]]; then
        for i in "${!field_names[@]}"; do
            local field="${field_names[$i]}"
            case "$field" in
                # Framework standard format: accounts_{device_name}_{metric}
                accounts_${ACCOUNTS_DEVICE}_util) accounts_util_idx=$i ;;
                accounts_${ACCOUNTS_DEVICE}_total_iops) accounts_iops_idx=$i ;;
                accounts_${ACCOUNTS_DEVICE}_total_throughput_mibs) accounts_throughput_idx=$i ;;
                accounts_${ACCOUNTS_DEVICE}_avg_await) accounts_await_idx=$i ;;
            esac
        done
    else
        log_debug "ACCOUNTS_DEVICE not configured, skipping ACCOUNTS field matching"
    fi
    
    # Analyze DATA device
    if [[ $data_util_idx -ge 0 && $data_iops_idx -ge 0 ]]; then
        log_info "Starting DATA device performance analysis"
        analyze_device_performance "$csv_file" "DATA" $((data_util_idx + 1)) $((data_iops_idx + 1)) $((data_throughput_idx + 1)) $((data_await_idx + 1))
    else
        log_warn "DATA device data not found"
    fi
    
    # Analyze ACCOUNTS device
    if [[ $accounts_util_idx -ge 0 && $accounts_iops_idx -ge 0 ]]; then
        log_info "Starting ACCOUNTS device performance analysis"
        analyze_device_performance "$csv_file" "ACCOUNTS" $((accounts_util_idx + 1)) $((accounts_iops_idx + 1)) $((accounts_throughput_idx + 1)) $((accounts_await_idx + 1))
    else
        log_debug "ACCOUNTS device data not found (ACCOUNTS device is optional configuration)"
    fi
    
    log_info "EBS performance analysis completed"
}

# Device performance analysis
analyze_device_performance() {
    local csv_file="$1"
    local device_name="$2"
    local util_field="$3"
    local iops_field="$4"
    local throughput_field="$5"
    local await_field="$6"
    
    log_debug "Analyzing device: $device_name (field positions: util=$util_field, iops=$iops_field)"
    
    # Skip header, analyze data
    tail -n +2 "$csv_file" | while IFS=',' read -r line_data; do
        # Use cut command to safely get field values, consistent with statistical analysis
        local timestamp=$(echo "$line_data" | cut -d',' -f1)
        local util=$(echo "$line_data" | cut -d',' -f"$util_field")
        local iops=$(echo "$line_data" | cut -d',' -f"$iops_field")
        local throughput=$(echo "$line_data" | cut -d',' -f"$throughput_field")
        local await_time=$(echo "$line_data" | cut -d',' -f"$await_field")
        
        # Debug output
        log_debug "Processing data row: util=$util, await_time=$await_time, util_field=$util_field, await_field=$await_field"
        
        # Check high utilization (use 80% of bottleneck threshold as warning level)
        local warning_util_threshold=$(awk "BEGIN {printf \"%.2f\", ${BOTTLENECK_EBS_UTIL_THRESHOLD:-90} * 0.8}")
        if (( $(awk "BEGIN {print ($util > $warning_util_threshold) ? 1 : 0}" 2>/dev/null || echo 0) )); then
            log_warn "$device_name high iostat utilization warning: ${util}% (iostat %util, warning threshold: ${warning_util_threshold}%, data time: $timestamp)"
        fi
        
        # Check high latency (use 40% of bottleneck threshold as warning level, maintain reasonable early warning distance)
        local warning_latency_threshold=$(awk "BEGIN {printf \"%.2f\", ${BOTTLENECK_EBS_LATENCY_THRESHOLD:-50} * 0.4}")
        if (( $(awk "BEGIN {print ($await_time > $warning_latency_threshold) ? 1 : 0}" 2>/dev/null || echo 0) )); then
            log_warn "$device_name high latency warning: ${await_time}ms (warning threshold: ${warning_latency_threshold}ms, data time: $timestamp)"
        fi
    done
    
    # Statistical analysis
    local avg_util=$(tail -n +2 "$csv_file" | cut -d',' -f"$util_field" | awk '{sum+=$1; count++} END {if(count>0) print sum/count; else print 0}')
    local max_util=$(tail -n +2 "$csv_file" | cut -d',' -f"$util_field" | sort -n | tail -1)
    local avg_iops=$(tail -n +2 "$csv_file" | cut -d',' -f"$iops_field" | awk '{sum+=$1; count++} END {if(count>0) print sum/count; else print 0}')
    local max_iops=$(tail -n +2 "$csv_file" | cut -d',' -f"$iops_field" | sort -n | tail -1)
    
    log_performance "${device_name}_avg_iostat_util" "$avg_util" "%"
    log_performance "${device_name}_max_iostat_util" "$max_util" "%"
    log_performance "${device_name}_avg_iops" "$avg_iops" "IOPS"
    log_performance "${device_name}_max_iops" "$max_iops" "IOPS"
}

# Main function
main() {
    log_info "EBS performance analyzer started"
    
    local csv_file="$1"
    
    if [[ -z "$csv_file" ]]; then
        log_error "Missing CSV file parameter"
        echo "Usage: $0 <performance_csv_file>"
        echo ""
        echo "Analyze EBS performance data in CSV file generated by unified monitor"
        echo "Supports parallel analysis of DATA and ACCOUNTS devices"
        echo "Eliminate empirical values, perform precise analysis based on real-time data"
        exit 1
    fi
    
    analyze_ebs_performance "$csv_file"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
