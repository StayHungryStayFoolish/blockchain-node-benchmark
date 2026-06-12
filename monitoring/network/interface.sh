#!/bin/bash
# monitoring/network/interface.sh
# Provider-aware NIC monitoring interface
# Provider implementations must expose these functions; driver detection lives in config.

# === Interface contract ===
# init_network_monitoring() -> 0 (ready) | 1 (unavailable)
#   Responsibility: detect NIC availability and verify the provider driver type.
#   Failure reasons: empty NETWORK_INTERFACE, missing ethtool, or driver mismatch.
# generate_network_csv_header() -> stdout (CSV header)
#   Invariant: first column must be timestamp, last column must be network_saturation_signal.
#   Required common fields: timestamp,interface,rx_bytes,tx_bytes,rx_packets,tx_packets,network_saturation_signal.
# collect_network_metrics() -> stdout (CSV row)
#   Invariant: field count equals generate_network_csv_header() output.
# get_network_field_metadata(field_name) -> stdout (semantic_type)
#   Return value is one of throughput, packet_count, saturation_counter,
#   drop_counter, error_counter, saturation_signal, gauge, unknown.

# === Common counter collection from /sys/class/net ===
_collect_base_network_counters() {
    local iface="$1"
    local sys_class_net="${NET_SYS_CLASS_DIR:-/sys/class/net}"
    local rx_bytes=$(cat "$sys_class_net/$iface/statistics/rx_bytes" 2>/dev/null || echo 0)
    local tx_bytes=$(cat "$sys_class_net/$iface/statistics/tx_bytes" 2>/dev/null || echo 0)
    local rx_pkts=$(cat "$sys_class_net/$iface/statistics/rx_packets" 2>/dev/null || echo 0)
    local tx_pkts=$(cat "$sys_class_net/$iface/statistics/tx_packets" 2>/dev/null || echo 0)
    echo "${rx_bytes},${tx_bytes},${rx_pkts},${tx_pkts}"
}

# === Common metadata used by provider get_network_field_metadata implementations ===
_get_base_field_semantic() {
    case "$1" in
        rx_bytes|tx_bytes) echo "throughput" ;;
        rx_packets|tx_packets) echo "packet_count" ;;
        network_saturation_signal) echo "saturation_signal" ;;
        *) echo "" ;;  # Empty means it is not a base field; provider modules decide.
    esac
}
