#!/bin/bash
# monitoring/network/other_none.sh
# Fallback implementation for local, bare-metal, or unknown environments.
# Collects common counters only; saturation_signal is always 0 because no
# cloud-level saturation counter is available.
# Implements the provider network interface functions

source "$(dirname "${BASH_SOURCE[0]}")/interface.sh"

init_network_monitoring() {
    [[ -z "$NETWORK_INTERFACE" ]] && return 1
    # A NIC statistics directory is enough; this fallback does not need ethtool.
    [[ -d "${NET_SYS_CLASS_DIR:-/sys/class/net}/$NETWORK_INTERFACE" ]] || return 1
    return 0
}

generate_network_csv_header() {
    echo "timestamp,interface,rx_bytes,tx_bytes,rx_packets,tx_packets,network_saturation_signal"
}

collect_network_metrics() {
    local ts
    ts=$(date +"%Y-%m-%d %H:%M:%S")
    local iface="$NETWORK_INTERFACE"
    local base
    base=$(_collect_base_network_counters "$iface")
    # No provider-specific counter is available, so never mark saturation.
    local saturation=0
    echo "${ts},${iface},${base},${saturation}"
}

get_network_field_metadata() {
    local base
    base=$(_get_base_field_semantic "$1")
    if [[ -n "$base" ]]; then
        echo "$base"
        return
    fi
    echo "unknown"
}
