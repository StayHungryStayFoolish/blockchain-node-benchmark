#!/bin/bash
# monitoring/network/aws_ena.sh
# AWS ENA implementation (driver=ena).
# Implements the provider network interface functions: init_network_monitoring / generate_network_csv_header /
#                          collect_network_metrics / get_network_field_metadata

source "$(dirname "${BASH_SOURCE[0]}")/interface.sh"

# AWS ENA fields. Older ENA versions may expose only 3 counters; newer versions expose all 6.
readonly AWS_ENA_FIELDS=(
    "bw_in_allowance_exceeded"
    "bw_out_allowance_exceeded"
    "pps_allowance_exceeded"
    "conntrack_allowance_exceeded"
    "linklocal_allowance_exceeded"
    "conntrack_allowance_available"
)

init_network_monitoring() {
    [[ -z "$NETWORK_INTERFACE" ]] && return 1
    command -v ethtool >/dev/null 2>&1 || return 1
    ethtool -S "$NETWORK_INTERFACE" &>/dev/null || return 1
    # Verify the driver is ENA-family (ena / efa).
    local driver
    driver=$(ethtool -i "$NETWORK_INTERFACE" 2>/dev/null | awk '/^driver:/ {print $2}')
    [[ "$driver" == "ena" || "$driver" == "efa" ]] || return 1
    # Detect which ENA counters are visible on this instance.
    local found=0
    local field
    for field in "${AWS_ENA_FIELDS[@]}"; do
        ethtool -S "$NETWORK_INTERFACE" 2>/dev/null | grep -q "$field" && ((found+=1))
    done
    [[ $found -gt 0 ]] || return 1
    return 0
}

generate_network_csv_header() {
    local h="timestamp,interface,rx_bytes,tx_bytes,rx_packets,tx_packets"
    local field
    for field in "${AWS_ENA_FIELDS[@]}"; do
        # bw_in_allowance_exceeded -> ena_bw_in_exceeded ; conntrack_allowance_available -> ena_conntrack_available
        h="${h},ena_${field/_allowance/}"
    done
    h="${h},ena_pps_limited,ena_bandwidth_limited"
    h="${h},network_saturation_signal"
    echo "$h"
}

collect_network_metrics() {
    local ts
    ts=$(date +"%Y-%m-%d %H:%M:%S")
    local iface="$NETWORK_INTERFACE"
    local base
    base=$(_collect_base_network_counters "$iface")

    local ethtool_out
    ethtool_out=$(ethtool -S "$iface" 2>/dev/null)
    local ena_values=""
    local saturation=0
    local pps_limited=0
    local bandwidth_limited=0
    local field v
    for field in "${AWS_ENA_FIELDS[@]}"; do
        v=$(echo "$ethtool_out" | grep "$field:" | awk '{print $2}')
        v=${v:-0}
        ena_values="${ena_values},${v}"
        # Any ena_*_exceeded counter greater than 0 triggers the saturation signal.
        if [[ "$field" =~ exceeded ]] && [[ "$v" -gt 0 ]]; then
            saturation=1
        fi
        if [[ "$field" == "pps_allowance_exceeded" && "$v" -gt 0 ]]; then
            pps_limited=1
        fi
        if [[ "$field" == "bw_in_allowance_exceeded" || "$field" == "bw_out_allowance_exceeded" ]] && [[ "$v" -gt 0 ]]; then
            bandwidth_limited=1
        fi
    done

    echo "${ts},${iface},${base}${ena_values},${pps_limited},${bandwidth_limited},${saturation}"
}

get_network_field_metadata() {
    local base
    base=$(_get_base_field_semantic "$1")
    if [[ -n "$base" ]]; then
        echo "$base"
        return
    fi
    case "$1" in
        ena_*_exceeded) echo "saturation_counter" ;;
        ena_conntrack_available) echo "gauge" ;;
        ena_pps_limited|ena_bandwidth_limited) echo "saturation_signal" ;;
        *) echo "unknown" ;;
    esac
}
