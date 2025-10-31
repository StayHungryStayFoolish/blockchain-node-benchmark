#!/bin/bash
# =====================================================================
# ENA Network Monitor - Network Limit Monitoring Based on AWS ENA Documentation
# =====================================================================
# Monitor ENA network interface allowance exceeded metrics
# Replace assumed PPS thresholds with actual AWS network limit data
# Use unified logger
# =====================================================================

# Strict error handling - but allow safe use in interactive environments
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    set -euo pipefail
else
    set -uo pipefail
fi

# Safely load configuration file to avoid readonly variable conflicts
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "Warning: Configuration file loading failed, using default configuration"
    MONITOR_INTERVAL=${MONITOR_INTERVAL:-10}
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi
source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh"

# Initialize unified logger
init_logger "ena_network_monitor" $LOG_LEVEL "${LOGS_DIR}/ena_network_monitor.log"

# ENA monitoring log file - avoid redefining readonly variables
if [[ -z "${ENA_LOG:-}" ]]; then
    readonly ENA_LOG="${LOGS_DIR}/ena_network_${SESSION_TIMESTAMP}.csv"
fi

# Initialize ENA monitoring
init_ena_monitoring() {
    log_info "Initializing ENA network monitoring..."
    
    # Check if ENA monitoring is enabled
    if [[ "$ENA_MONITOR_ENABLED" != "true" ]]; then
        log_warn "ENA monitoring is disabled, skipping ENA network monitoring"
        return 1
    fi
    
    # Check network interface
    if [[ -z "$NETWORK_INTERFACE" ]]; then
        log_error "Cannot detect network interface"
        return 1
    fi
    
    # Check if ethtool is available
    if ! command -v ethtool >/dev/null 2>&1; then
        log_error "ethtool command unavailable, cannot monitor ENA statistics"
        return 1
    fi
    
    # Check if interface supports ENA statistics
    if ! ethtool -S "$NETWORK_INTERFACE" &>/dev/null; then
        log_warn "Interface $NETWORK_INTERFACE does not support ethtool statistics"
        return 1
    fi
    
    # Check for ENA allowance fields - use standardized array access
    local ena_fields_found=0
    ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
    for field in "${ena_fields[@]}"; do
        if ethtool -S "$NETWORK_INTERFACE" 2>/dev/null | grep -q "$field"; then
            ((ena_fields_found++))
        fi
    done
    
    if [[ $ena_fields_found -eq 0 ]]; then
        log_warn "Interface $NETWORK_INTERFACE does not support ENA allowance monitoring"
        return 1
    fi
    
    log_info "ENA monitoring initialized successfully"
    echo "   Interface: $NETWORK_INTERFACE"
    echo "   Supported ENA fields: $ena_fields_found/${#ena_fields[@]}"
    
    # Create CSV header
    generate_ena_csv_header > "$ENA_LOG"
    
    return 0
}

# Generate ENA CSV header
generate_ena_csv_header() {
    local header="timestamp"
    
    # Add basic network statistics
    header="$header,interface,rx_bytes,tx_bytes,rx_packets,tx_packets"
    
    ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
    for field in "${ena_fields[@]}"; do
        header="$header,$field"
    done
    
    # Add calculated fields
    header="$header,network_limited,pps_limited,bandwidth_limited"
    
    echo "$header"
}

# Get ENA network statistics
get_ena_network_stats() {
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    local interface="$NETWORK_INTERFACE"
    
    # Get basic network statistics
    local rx_bytes=$(cat "/sys/class/net/$interface/statistics/rx_bytes" 2>/dev/null || echo "0")
    local tx_bytes=$(cat "/sys/class/net/$interface/statistics/tx_bytes" 2>/dev/null || echo "0")
    local rx_packets=$(cat "/sys/class/net/$interface/statistics/rx_packets" 2>/dev/null || echo "0")
    local tx_packets=$(cat "/sys/class/net/$interface/statistics/tx_packets" 2>/dev/null || echo "0")
    
    # Get ENA allowance statistics
    local ena_stats=""
    local ethtool_output=$(ethtool -S "$interface" 2>/dev/null || echo "")
    
    ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
    for field in "${ena_fields[@]}"; do
        local value=$(echo "$ethtool_output" | grep "$field:" | awk '{print $2}' || echo "0")
        ena_stats="$ena_stats,$value"
    done
    
    # Calculate network limit status
    local network_limited="false"
    local pps_limited="false"
    local bandwidth_limited="false"
    
    # Check PPS limit
    local pps_exceeded=$(echo "$ethtool_output" | grep "pps_allowance_exceeded:" | awk '{print $2}' || echo "0")
    if [[ "$pps_exceeded" -gt 0 ]]; then
        pps_limited="true"
        network_limited="true"
    fi
    
    # Check bandwidth limit
    local bw_in_exceeded=$(echo "$ethtool_output" | grep "bw_in_allowance_exceeded:" | awk '{print $2}' || echo "0")
    local bw_out_exceeded=$(echo "$ethtool_output" | grep "bw_out_allowance_exceeded:" | awk '{print $2}' || echo "0")
    if [[ "$bw_in_exceeded" -gt 0 || "$bw_out_exceeded" -gt 0 ]]; then
        bandwidth_limited="true"
        network_limited="true"
    fi
    
    # Output CSV row
    echo "$timestamp,$interface,$rx_bytes,$tx_bytes,$rx_packets,$tx_packets$ena_stats,$network_limited,$pps_limited,$bandwidth_limited"
}

# Start ENA monitoring
start_ena_monitoring() {
    local duration=${1:-3600}
    local interval=${2:-${MONITOR_INTERVAL:-5}}
    
    echo "🚀 Starting ENA network monitoring..."
    echo "   Log file: $ENA_LOG"
    
    if ! init_ena_monitoring; then
        log_error "ENA monitoring initialization failed"
        return 1
    fi
    
    # Support continuous running mode
    if [[ "$duration" == "0" ]]; then
        echo "   Running mode: Continuous monitoring (suitable for framework integration)"
        echo "   Monitoring interval: ${interval} seconds"
        log_info "ENA continuous monitoring mode started, interval: ${interval}s"
        
        # Continuous running mode - follow framework lifecycle
        while [[ -f "$TMP_DIR/qps_test_status" ]]; do
            get_ena_network_stats >> "$ENA_LOG"
            sleep "$interval"
        done
    else
        echo "   Duration: ${duration} seconds"
        echo "   Monitoring interval: ${interval} seconds"
        log_info "ENA timed monitoring mode started, duration: ${duration}s, interval: ${interval}s"
        
        # Fixed duration mode
        local start_time=$(date +%s)
        local end_time=$((start_time + duration))
        
        while [[ $(date +%s) -lt $end_time ]]; do
            get_ena_network_stats >> "$ENA_LOG"
            sleep "$interval"
        done
        
        log_info "ENA network monitoring completed"
        echo "   Data saved to: $ENA_LOG"
    fi
}

# Analyze ENA network limits
analyze_ena_limits() {
    local ena_csv="$1"
    
    if [[ ! -f "$ena_csv" ]]; then
        log_error "ENA log file does not exist: $ena_csv"
        return 1
    fi
    
    echo "📊 Analyzing ENA network limits..."
    
    # Count network limit events
    local total_samples=$(tail -n +2 "$ena_csv" | wc -l)
    local network_limited_count=$(tail -n +2 "$ena_csv" | awk -F',' '$NF=="true"' | wc -l)
    local pps_limited_count=$(tail -n +2 "$ena_csv" | awk -F',' '$(NF-1)=="true"' | wc -l)
    local bandwidth_limited_count=$(tail -n +2 "$ena_csv" | awk -F',' '$(NF-2)=="true"' | wc -l)
    
    echo "ENA Network Limit Analysis Results:"
    echo "  Total samples: $total_samples"
    echo "  Network limited samples: $network_limited_count ($(awk "BEGIN {printf \"%.2f\", $network_limited_count * 100 / $total_samples}" 2>/dev/null || echo "0")%)"
    echo "  PPS limited samples: $pps_limited_count ($(awk "BEGIN {printf \"%.2f\", $pps_limited_count * 100 / $total_samples}" 2>/dev/null || echo "0")%)"
    echo "  Bandwidth limited samples: $bandwidth_limited_count ($(awk "BEGIN {printf \"%.2f\", $bandwidth_limited_count * 100 / $total_samples}" 2>/dev/null || echo "0")%)"
    
    # Check maximum allowance exceeded values
    echo ""
    echo "Maximum allowance exceeded values:"
    ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
    for field in "${ena_fields[@]}"; do
        local field_index=$(head -1 "$ena_csv" | tr ',' '\n' | grep -n "^$field$" | cut -d: -f1)
        if [[ -n "$field_index" ]]; then
            local max_value=$(tail -n +2 "$ena_csv" | cut -d',' -f"$field_index" | sort -n | tail -1)
            echo "  $field: $max_value"
        fi
    done
}

# Main function
main() {
    case "${1:-}" in
        "start")
            start_ena_monitoring "${2:-3600}" "${3:-5}"
            ;;
        "analyze")
            analyze_ena_limits "${2:-$ENA_LOG}"
            ;;
        "test")
            echo "🧪 Testing ENA monitoring functionality..."
            if init_ena_monitoring; then
                log_info "ENA monitoring functionality normal"
                get_ena_network_stats
            else
                log_error "ENA monitoring functionality abnormal"
                exit 1
            fi
            ;;
        *)
            echo "Usage: $0 {start|analyze|test} [duration] [interval]"
            echo ""
            echo "Commands:"
            echo "  start [duration] [interval]  - Start ENA monitoring"
            echo "  analyze [csv_file]           - Analyze ENA limits"
            echo "  test                         - Test ENA monitoring functionality"
            echo ""
            echo "Examples:"
            echo "  $0 start 3600 5             - Monitor for 1 hour, sample every 5 seconds"
            echo "  $0 analyze ena_network_*.csv - Analyze ENA log"
            echo "  $0 test                      - Test functionality"
            exit 1
            ;;
    esac
}

# If this script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
