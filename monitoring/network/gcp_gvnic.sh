#!/bin/bash
# monitoring/network/gcp_gvnic.sh
# GCP gVNIC 实现 (driver=gve, n2/c2/n4 等现代 GCP 实例)
# 实现 Y+ 接口契约 4 函数

source "$(dirname "${BASH_SOURCE[0]}")/interface.sh"

# gVNIC 字段集 (3 个, 从 ethtool -S)
# 注意: gVNIC 不报 *_allowance_exceeded, 因为根本没这种 counter
readonly GCP_GVNIC_FIELDS=(
    "tx_drops"
    "rx_no_buffer"
    "tx_timeout"
)

init_network_monitoring() {
    [[ -z "$NETWORK_INTERFACE" ]] && return 1
    command -v ethtool >/dev/null 2>&1 || return 1
    local driver
    driver=$(ethtool -i "$NETWORK_INTERFACE" 2>/dev/null | awk '/^driver:/ {print $2}')
    [[ "$driver" == "gve" ]] || return 1
    ethtool -S "$NETWORK_INTERFACE" &>/dev/null || return 1
    return 0
}

generate_network_csv_header() {
    local h="timestamp,interface,rx_bytes,tx_bytes,rx_packets,tx_packets"
    local field
    for field in "${GCP_GVNIC_FIELDS[@]}"; do
        h="${h},gvnic_${field}"
    done
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
    local gvnic_values=""
    local saturation=0
    local field v
    for field in "${GCP_GVNIC_FIELDS[@]}"; do
        v=$(echo "$ethtool_out" | awk -v f="$field" '$1 == f":" {print $2}')
        v=${v:-0}
        gvnic_values="${gvnic_values},${v}"
        # tx_drops > 0 OR rx_no_buffer > 0 触发饱和 (tx_timeout 是 error 不算饱和)
        if [[ "$field" == "tx_drops" || "$field" == "rx_no_buffer" ]] && [[ "$v" -gt 0 ]]; then
            saturation=1
        fi
    done

    echo "${ts},${iface},${base}${gvnic_values},${saturation}"
}

get_network_field_metadata() {
    local base
    base=$(_get_base_field_semantic "$1")
    if [[ -n "$base" ]]; then
        echo "$base"
        return
    fi
    case "$1" in
        gvnic_tx_drops|gvnic_rx_no_buffer) echo "drop_counter" ;;
        gvnic_tx_timeout) echo "error_counter" ;;
        *) echo "unknown" ;;
    esac
}