#!/bin/bash
# monitoring/network/interface.sh
# Y+ 架构: NIC 监控接口契约 (5 个核心函数)
# 任何 provider 实现必须实现这 4 个函数 (detect_nic_driver 在 config 层, 不在 provider 实现层)

# === 接口契约 ===
# init_network_monitoring() -> 0 (就绪) | 1 (不可用)
#   职责: 探测网卡可用性 + 验证 driver 类型匹配本 provider
#   失败原因: NETWORK_INTERFACE 空 / ethtool 缺 / driver 类型不匹配
# generate_network_csv_header() -> stdout (CSV header)
#   不变量: 首列必须 timestamp, 末列必须 network_saturation_signal
#   跨 provider 必含列: timestamp,interface,rx_bytes,tx_bytes,rx_packets,tx_packets,network_saturation_signal (7 列)
# collect_network_metrics() -> stdout (CSV row)
#   不变量: 列数 = generate_network_csv_header() 输出的列数
# get_network_field_metadata(field_name) -> stdout (semantic_type)
#   返回值 ∈ {throughput, packet_count, saturation_counter, drop_counter, error_counter, saturation_signal, gauge, unknown}

# === 基础 counter 采集 (跨 provider 共享, 从 /sys/class/net) ===
_collect_base_network_counters() {
    local iface="$1"
    local rx_bytes=$(cat "/sys/class/net/$iface/statistics/rx_bytes" 2>/dev/null || echo 0)
    local tx_bytes=$(cat "/sys/class/net/$iface/statistics/tx_bytes" 2>/dev/null || echo 0)
    local rx_pkts=$(cat "/sys/class/net/$iface/statistics/rx_packets" 2>/dev/null || echo 0)
    local tx_pkts=$(cat "/sys/class/net/$iface/statistics/tx_packets" 2>/dev/null || echo 0)
    echo "${rx_bytes},${tx_bytes},${rx_pkts},${tx_pkts}"
}

# === 通用元数据 (provider 实现的 get_network_field_metadata 应先调这个) ===
_get_base_field_semantic() {
    case "$1" in
        rx_bytes|tx_bytes) echo "throughput" ;;
        rx_packets|tx_packets) echo "packet_count" ;;
        network_saturation_signal) echo "saturation_signal" ;;
        *) echo "" ;;  # 空 = 不是基础字段, 让 provider 自己判断
    esac
}