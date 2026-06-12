#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT

LOGS_DIR="$TMP_ROOT/logs"
REPORTS_DIR="$TMP_ROOT/reports"
MEMORY_DIR="$TMP_ROOT/memory"
mkdir -p "$LOGS_DIR" "$REPORTS_DIR" "$MEMORY_DIR"

source "$ROOT/config/csv_schema_registry.sh"

SAMPLE_TIMESTAMP="2026-06-11 12:00:00"
SAMPLE_TIMESTAMP_MS="$(python3 - "$SAMPLE_TIMESTAMP" <<'PY'
from datetime import datetime
import sys

dt = datetime.strptime(sys.argv[1], "%Y-%m-%d %H:%M:%S")
print(int(dt.timestamp() * 1000))
PY
)"

basic_header="timestamp,cpu_usage,cpu_user,cpu_system,cpu_iowait,cpu_softirq,cpu_idle,mem_usage,mem_used_mb,mem_available_mb"
disk_header="$(csv_registry_disk_header "data_sda" "aws"),$(csv_registry_disk_header "accounts_sdb" "aws")"
network_header="network_rx_mbps,network_tx_mbps,network_total_mbps,network_util,network_rx_pps,network_tx_pps,network_connections,network_errors,network_drops,network_retransmits"
ena_header="ena_bw_in_allowance_exceeded,ena_bw_out_allowance_exceeded,ena_pps_allowance_exceeded,ena_conntrack_allowance_exceeded,ena_linklocal_allowance_exceeded,ena_conntrack_allowance_available"
overhead_header="monitoring_iops_per_sec,monitoring_throughput_mibs_per_sec"
block_header="$(csv_registry_block_header)"
qps_header="current_qps,rpc_latency_ms,qps_data_available"
cgroup_header="cgroup_cpu_usage_percent,cgroup_memory_usage_mb,cgroup_memory_limit_mb,cgroup_blkio_read_iops,cgroup_blkio_write_iops,cgroup_blkio_read_mbps,cgroup_blkio_write_mbps"

header="$basic_header,$disk_header,$network_header,$ena_header,$overhead_header,$block_header,$qps_header,$cgroup_header,cloud_provider"

value_for_field() {
    local field="$1"
    case "$field" in
        timestamp) echo "$SAMPLE_TIMESTAMP" ;;
        sync_mode) echo "absolute_gap" ;;
        sync_status) echo "healthy" ;;
        lag_unit) echo "block" ;;
        probe_error) echo "null" ;;
        cloud_provider) echo "aws" ;;
        qps_data_available|local_health|mainnet_health) echo "1" ;;
        data_loss) echo "0" ;;
        *) echo "1" ;;
    esac
}

row=""
IFS=',' read -ra fields <<< "$header"
for field in "${fields[@]}"; do
    value="$(value_for_field "$field")"
    if [[ -z "$row" ]]; then
        row="$value"
    else
        row="$row,$value"
    fi
done

perf_file="$LOGS_DIR/performance_20260611_120000.csv"
{
    echo "$header"
    echo "$row"
} > "$perf_file"
ln -s "$(basename "$perf_file")" "$LOGS_DIR/performance_latest.csv"

block_csv_header="$(csv_registry_block_csv_header)"
{
    echo "$block_csv_header"
    echo "$SAMPLE_TIMESTAMP,100,101,1,1,1,0,absolute_gap,healthy,1,block,0,null"
} > "$LOGS_DIR/block_height_monitor_20260611_120000.csv"

cat > "$MEMORY_DIR/latest_metrics.json" <<'JSON'
{
  "timestamp": "2026-06-11 12:00:00",
  "cpu_usage": 10,
  "memory_usage": 20,
  "disk_util": 30,
  "disk_latency": 1,
  "network_util": 5,
  "error_rate": 0
}
JSON

cat > "$MEMORY_DIR/unified_metrics.json" <<'JSON'
{
  "timestamp": "2026-06-11 12:00:00",
  "cpu_usage": 10,
  "memory_usage": 20,
  "disk_util": 30,
  "disk_latency": 1,
  "network_util": 5,
  "error_rate": 0,
  "detailed_data": {
    "cpu_data": "10,1,1,1,1,86",
    "memory_data": "20,1024,4096"
  }
}
JSON

cat > "$MEMORY_DIR/block_height_monitor_cache.json" <<'JSON'
{
  "timestamp_ms": __SAMPLE_TIMESTAMP_MS__,
  "timestamp": "2026-06-11 12:00:00",
  "local_block_height": 100,
  "mainnet_block_height": 101,
  "block_height_diff": 1,
  "local_health": "1",
  "mainnet_health": "1",
  "data_loss": "0",
  "sync_mode": "absolute_gap",
  "sync_status": "healthy",
  "lag_value": 1,
  "lag_unit": "block",
  "freshness_gap_seconds": 0,
  "probe_error": null
}
JSON
perl -pi -e "s/__SAMPLE_TIMESTAMP_MS__/$SAMPLE_TIMESTAMP_MS/" "$MEMORY_DIR/block_height_monitor_cache.json"

echo "1" > "$MEMORY_DIR/sample_count"

cat > "$LOGS_DIR/proxy_method.csv" <<'CSV'
timestamp_ns,timestamp,method_name,status_code,latency_ms,request_bytes,response_bytes,error,batch_idx
1781150400000000000,2026-06-11T12:00:00Z,getBalance,200,2,100,200,,0
CSV

cat > "$REPORTS_DIR/performance_report_en_20260611_120000.html" <<'HTML'
<!doctype html>
<html><body><h1>Report</h1><section>Data Quality Summary</section></body></html>
HTML

bash "$ROOT/tools/audit_monitoring_runtime.sh" \
    --logs-dir "$LOGS_DIR" \
    --reports-dir "$REPORTS_DIR" \
    --memory-dir "$MEMORY_DIR" \
    --skip-freshness \
    --require-report

bad_logs="$TMP_ROOT/bad_logs"
mkdir -p "$bad_logs"
cp "$perf_file" "$bad_logs/performance_latest.csv"
echo "bad,row" >> "$bad_logs/performance_latest.csv"
cp "$LOGS_DIR/block_height_monitor_20260611_120000.csv" "$bad_logs/"

if bash "$ROOT/tools/audit_monitoring_runtime.sh" \
    --logs-dir "$bad_logs" \
    --memory-dir "$MEMORY_DIR" \
    --skip-freshness >/tmp/monitoring_contract_bad.out 2>&1; then
    echo "expected audit failure for malformed CSV row" >&2
    cat /tmp/monitoring_contract_bad.out >&2
    exit 1
fi

bad_memory="$TMP_ROOT/bad_memory"
mkdir -p "$bad_memory"
cp "$MEMORY_DIR/latest_metrics.json" "$bad_memory/latest_metrics.json"
cp "$MEMORY_DIR/unified_metrics.json" "$bad_memory/unified_metrics.json"
cp "$MEMORY_DIR/block_height_monitor_cache.json" "$bad_memory/block_height_monitor_cache.json"
jq '.timestamp = "2026-06-11 12:00:01"' "$MEMORY_DIR/latest_metrics.json" > "$bad_memory/latest_metrics.json"

if bash "$ROOT/tools/audit_monitoring_runtime.sh" \
    --logs-dir "$LOGS_DIR" \
    --memory-dir "$bad_memory" \
    --skip-freshness >/tmp/monitoring_contract_bad_json.out 2>&1; then
    echo "expected audit failure for JSON/CSV timestamp mismatch" >&2
    cat /tmp/monitoring_contract_bad_json.out >&2
    exit 1
fi

bad_pointer_logs="$TMP_ROOT/bad_pointer_logs"
mkdir -p "$bad_pointer_logs"
cp "$perf_file" "$bad_pointer_logs/performance_20260611_120000.csv"
cp "$perf_file" "$bad_pointer_logs/performance_20260611_120001.csv"
touch -t 202606111200.00 "$bad_pointer_logs/performance_20260611_120000.csv"
touch -t 202606111200.01 "$bad_pointer_logs/performance_20260611_120001.csv"
ln -s "performance_20260611_120000.csv" "$bad_pointer_logs/performance_latest.csv"
cp "$LOGS_DIR/block_height_monitor_20260611_120000.csv" "$bad_pointer_logs/"

if bash "$ROOT/tools/audit_monitoring_runtime.sh" \
    --logs-dir "$bad_pointer_logs" \
    --memory-dir "$MEMORY_DIR" \
    --skip-freshness >/tmp/monitoring_contract_bad_pointer.out 2>&1; then
    echo "expected audit failure for stale performance_latest.csv pointer" >&2
    cat /tmp/monitoring_contract_bad_pointer.out >&2
    exit 1
fi

bad_count_memory="$TMP_ROOT/bad_count_memory"
mkdir -p "$bad_count_memory"
cp "$MEMORY_DIR/latest_metrics.json" "$bad_count_memory/latest_metrics.json"
cp "$MEMORY_DIR/unified_metrics.json" "$bad_count_memory/unified_metrics.json"
cp "$MEMORY_DIR/block_height_monitor_cache.json" "$bad_count_memory/block_height_monitor_cache.json"
echo "2" > "$bad_count_memory/sample_count"

if bash "$ROOT/tools/audit_monitoring_runtime.sh" \
    --logs-dir "$LOGS_DIR" \
    --memory-dir "$bad_count_memory" \
    --skip-freshness >/tmp/monitoring_contract_bad_count.out 2>&1; then
    echo "expected audit failure for sample_count/performance row mismatch" >&2
    cat /tmp/monitoring_contract_bad_count.out >&2
    exit 1
fi

echo "PASS: monitoring runtime contract audit"
