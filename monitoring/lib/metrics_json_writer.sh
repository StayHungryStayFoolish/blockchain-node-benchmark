#!/usr/bin/env bash
# =====================================================================
# Monitoring JSON Metrics Writer
# =====================================================================
# Writes the memory-share JSON files consumed by QPS and bottleneck logic.
# Contract:
#   - LATEST_METRICS_FILE defaults to $MEMORY_SHARE_DIR/latest_metrics.json
#   - UNIFIED_METRICS_FILE defaults to $MEMORY_SHARE_DIR/unified_metrics.json
# =====================================================================

generate_json_metrics() {
    local timestamp="$1"
    local cpu_data="$2"
    local memory_data="$3"
    local device_data="$4"
    local network_data="$5"
    local ena_data="$6"
    local overhead_data="$7"

    local cpu_usage
    local mem_usage
    local net_total_mbps
    cpu_usage=$(echo "$cpu_data" | cut -d',' -f1)
    mem_usage=$(echo "$memory_data" | cut -d',' -f3)
    net_total_mbps=$(echo "$network_data" | cut -d',' -f4)

    local network_max="${NETWORK_MAX_BANDWIDTH_MBPS:-0}"
    local network_util="0"
    if awk "BEGIN {exit !($network_max > 0)}" 2>/dev/null; then
        network_util=$(awk "BEGIN {printf \"%.2f\", ($net_total_mbps / $network_max) * 100}" 2>/dev/null || echo "0")
        network_util=$(awk "BEGIN {printf \"%.2f\", ($network_util > 100) ? 100 : $network_util}" 2>/dev/null || echo "0")
    fi

    local disk_util=0
    local disk_latency=0
    if [[ -n "$device_data" ]]; then
        # Device data format: r_s,w_s,rkb_s,wkb_s,r_await,w_await,avg_await,aqu_sz,util...
        disk_util=$(echo "$device_data" | cut -d',' -f9 2>/dev/null || echo "0")
        disk_latency=$(echo "$device_data" | cut -d',' -f7 2>/dev/null || echo "0")
    fi

    local latest_metrics_file="${LATEST_METRICS_FILE:-${MEMORY_SHARE_DIR}/latest_metrics.json}"
    local unified_metrics_file="${UNIFIED_METRICS_FILE:-${MEMORY_SHARE_DIR}/unified_metrics.json}"
    mkdir -p "$(dirname "$latest_metrics_file")" "$(dirname "$unified_metrics_file")"

    cat > "${latest_metrics_file}.tmp" << EOF
{
    "timestamp": "$timestamp",
    "cpu_usage": $cpu_usage,
    "memory_usage": $mem_usage,
    "disk_util": $disk_util,
    "disk_latency": $disk_latency,
    "network_util": $network_util,
    "error_rate": 0
}
EOF
    mv "${latest_metrics_file}.tmp" "$latest_metrics_file"

    cat > "${unified_metrics_file}.tmp" << EOF
{
    "timestamp": "$timestamp",
    "cpu_usage": $cpu_usage,
    "memory_usage": $mem_usage,
    "disk_util": $disk_util,
    "disk_latency": $disk_latency,
    "network_util": $network_util,
    "error_rate": 0,
    "detailed_data": {
        "cpu_data": "$cpu_data",
        "memory_data": "$memory_data",
        "device_data": "$device_data",
        "network_data": "$network_data",
        "ena_data": "$ena_data",
        "overhead_data": "$overhead_data"
    }
}
EOF
    mv "${unified_metrics_file}.tmp" "$unified_metrics_file"
}
