#!/bin/bash
# monitoring/network/gcp_virtio.sh
# GCP virtio_net 实现 (cloudtop / e2 系列 / 老 GCP 实例, driver=virtio_net)
# 实测来源: cloudtop ens4 (driver=virtio_net, version=1.0.0)
# 实现 Y+ 接口契约 4 函数

source "$(dirname "${BASH_SOURCE[0]}")/interface.sh"

# 顶级 counter 4 个 (ethtool 真实字段名按实测保留, 双 tx 不是 typo)
readonly GCP_VIRTIO_FIELDS=(
    "rx_drops"          # 顶级 rx 丢包
    "tx_tx_timeouts"    # 顶级 tx 超时 (ethtool 里名字真就是 tx_tx_timeouts, 双 tx)
    "rx_xdp_drops"      # XDP 路径 rx 丢包
    "tx_xdp_tx_drops"   # XDP 路径 tx 丢包
)

# 按 queue 的 rx{N}_drops 用正则聚合 (N=0..6+, 数量随 vCPU 变)
readonly GCP_VIRTIO_PER_QUEUE_PATTERN="rx[0-9]+_drops"

init_network_monitoring() {
    [[ -z "$NETWORK_INTERFACE" ]] && return 1
    command -v ethtool >/dev/null 2>&1 || return 1
    local driver
    driver=$(ethtool -i "$NETWORK_INTERFACE" 2>/dev/null | awk '/^driver:/ {print $2}')
    [[ "$driver" == "virtio_net" ]] || return 1
    return 0
}

generate_network_csv_header() {
    local h="timestamp,interface,rx_bytes,tx_bytes,rx_packets,tx_packets"
    local field
    for field in "${GCP_VIRTIO_FIELDS[@]}"; do
        h="${h},virtio_${field}"
    done
    h="${h},virtio_per_queue_rx_drops_sum"   # 聚合的 per-queue drops
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
    local virtio_values=""
    local saturation=0
    local field v
    for field in "${GCP_VIRTIO_FIELDS[@]}"; do
        v=$(echo "$ethtool_out" | awk -v f="$field" '$1 == f":" {print $2}')
        v=${v:-0}
        virtio_values="${virtio_values},${v}"
        [[ "$v" -gt 0 ]] && saturation=1
    done

    # per-queue drops 聚合: 求和所有 rx{N}_drops
    local per_queue_drops
    per_queue_drops=$(echo "$ethtool_out" | awk '/^[[:space:]]*rx[0-9]+_drops:/ {sum+=$2} END {print sum+0}')
    [[ "$per_queue_drops" -gt 0 ]] && saturation=1

    echo "${ts},${iface},${base}${virtio_values},${per_queue_drops},${saturation}"
}

get_network_field_metadata() {
    local base
    base=$(_get_base_field_semantic "$1")
    if [[ -n "$base" ]]; then
        echo "$base"
        return
    fi
    case "$1" in
        virtio_rx_drops|virtio_rx_xdp_drops|virtio_tx_xdp_tx_drops|virtio_per_queue_rx_drops_sum) echo "drop_counter" ;;
        virtio_tx_tx_timeouts) echo "error_counter" ;;
        *) echo "unknown" ;;
    esac
}