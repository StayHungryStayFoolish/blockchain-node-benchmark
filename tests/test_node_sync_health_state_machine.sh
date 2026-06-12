#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

source core/common_functions.sh

export BLOCK_HEIGHT_DIFF_THRESHOLD=50
export BLOCK_HEIGHT_TIME_THRESHOLD=300
export MEMORY_SHARE_DIR="${MEMORY_SHARE_DIR:-/tmp}"

MODE="absolute_gap"
UNIT="block"
LOCAL_HEIGHT="100"
MAIN_HEIGHT="120"
LOCAL_HEALTH="1"
MAIN_HEALTH="1"

get_chain_sync_health_field() {
    case "$1" in
        mode) echo "$MODE" ;;
        threshold_unit) echo "$UNIT" ;;
        *) echo "$2" ;;
    esac
}

get_block_height() {
    if [[ "$1" == "local" ]]; then
        echo "$LOCAL_HEIGHT"
    else
        echo "$MAIN_HEIGHT"
    fi
}

check_node_health() {
    if [[ "$1" == "local" ]]; then
        echo "$LOCAL_HEALTH"
    else
        echo "$MAIN_HEALTH"
    fi
}

assert_jq() {
    local json="$1"
    local expr="$2"
    echo "$json" | jq -e "$expr" >/dev/null
}

out="$(get_node_sync_health local mainnet /tmp/no-cache.json)"
assert_jq "$out" '.sync_mode == "absolute_gap" and .sync_status == "healthy" and .block_height_diff == 20 and .lag_value == 20'

MAIN_HEIGHT="180"
out="$(get_node_sync_health local mainnet /tmp/no-cache.json)"
assert_jq "$out" '.sync_status == "behind" and .block_height_diff == 80 and .data_loss == "0"'

MAIN_HEIGHT="N/A"
out="$(get_node_sync_health local mainnet /tmp/no-cache.json)"
assert_jq "$out" '.sync_status == "unknown" and .probe_error == "mainnet_height_unavailable" and .data_loss == "0"'

MODE="conditional_gap"
LOCAL_HEIGHT="35"
MAIN_HEIGHT="N/A"
out="$(get_node_sync_health local mainnet /tmp/no-cache.json)"
assert_jq "$out" '.sync_mode == "conditional_gap" and .sync_status == "healthy" and .block_height_diff == 35 and .lag_value == 35 and .mainnet_block_height == null'

LOCAL_HEIGHT="75"
out="$(get_node_sync_health local mainnet /tmp/no-cache.json)"
assert_jq "$out" '.sync_mode == "conditional_gap" and .sync_status == "behind" and .block_height_diff == 75 and .lag_value == 75'

MODE="reported_lag"
UNIT="slot"
LOCAL_HEIGHT="75"
out="$(get_node_sync_health local mainnet /tmp/no-cache.json)"
assert_jq "$out" '.sync_mode == "reported_lag" and .sync_status == "behind" and .lag_unit == "slot" and .lag_value == 75'

MODE="freshness_only"
UNIT="timestamp_seconds"
LOCAL_HEIGHT="1000"
LOCAL_HEALTH="1"
cache="$(mktemp)"
old_ts=$(( $(current_epoch_ms) - 301000 ))
jq -n --argjson ts "$old_ts" '{timestamp_ms:$ts,local_block_height:1000}' > "$cache"
out="$(get_node_sync_health local mainnet "$cache")"
rm -f "$cache"
assert_jq "$out" '.sync_mode == "freshness_only" and .sync_status == "stale" and .freshness_gap_seconds >= 300'

LOCAL_HEIGHT="N/A"
out="$(get_node_sync_health local mainnet /tmp/no-cache.json)"
assert_jq "$out" '.sync_status == "unhealthy" and .data_loss == "1" and .probe_error == "local_freshness_unavailable"'

echo "PASS: get_node_sync_health state machine"
