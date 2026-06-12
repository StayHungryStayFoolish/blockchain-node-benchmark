#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

export MEMORY_SHARE_DIR="$TEST_ROOT/memory"
export LATEST_METRICS_FILE="$MEMORY_SHARE_DIR/latest_metrics.json"
export UNIFIED_METRICS_FILE="$MEMORY_SHARE_DIR/unified_metrics.json"
export NETWORK_MAX_BANDWIDTH_MBPS=1000

# shellcheck source=/dev/null
source monitoring/lib/metrics_json_writer.sh

generate_json_metrics \
    "2026-06-11 12:00:00" \
    "12.5,0,0,0" \
    "1000,450,45.0,550,55.0" \
    "1,2,3,4,5,6,4.5,8,70.2,10" \
    "eth0,10,90,100,0.01,0.09,0.10,100,200,300" \
    "0,0,0" \
    "0,0"

[[ -f "$LATEST_METRICS_FILE" ]] || { echo "latest_metrics.json not written"; exit 1; }
[[ -f "$UNIFIED_METRICS_FILE" ]] || { echo "unified_metrics.json not written"; exit 1; }

jq -e '
  .timestamp == "2026-06-11 12:00:00" and
  .cpu_usage == 12.5 and
  .memory_usage == 45.0 and
  .disk_latency == 4.5 and
  .disk_util == 70.2 and
  .network_util == 10.00 and
  .error_rate == 0
' "$LATEST_METRICS_FILE" >/dev/null

jq -e '
  .detailed_data.cpu_data == "12.5,0,0,0" and
  .detailed_data.memory_data == "1000,450,45.0,550,55.0" and
  .detailed_data.network_data == "eth0,10,90,100,0.01,0.09,0.10,100,200,300"
' "$UNIFIED_METRICS_FILE" >/dev/null

echo "✅ metrics_json_writer writes expected JSON metrics"
