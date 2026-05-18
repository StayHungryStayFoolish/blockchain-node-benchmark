#!/bin/bash
# monitoring/network/other_none.sh
# Other (Mac / IDC / 未知环境) 兜底实现
# 只采基础 4 列 + saturation_signal 永远 0 (无法判断 cloud-level 饱和)
# 实现 Y+ 接口契约 4 函数

source "$(dirname "${BASH_SOURCE[0]}")/interface.sh"

init_network_monitoring() {
    [[ -z "$NETWORK_INTERFACE" ]] && return 1
    # 只要 /sys/class/net/$NETWORK_INTERFACE 存在就 OK (不依赖 ethtool)
    [[ -d "/sys/class/net/$NETWORK_INTERFACE" ]] || return 1
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
    # other_none 永远不判定饱和 (没有 platform-specific counter)
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