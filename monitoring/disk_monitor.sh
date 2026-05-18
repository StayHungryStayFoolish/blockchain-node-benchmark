#!/bin/bash
# =====================================================================
# Disk Monitor - Y+ 架构 Disk 监控统一入口
# =====================================================================
# Replaces partially AWS-only iostat_collector.sh with platform-aware
# Y+ architecture. Routes to aws_ebs.sh | gcp_pd.sh | gcp_hyperdisk.sh
# | other_local.sh based on (CLOUD_PROVIDER, disk model) detected at runtime.
#
# This script is invoked by monitoring/monitoring_coordinator.sh task "disk".
# Old iostat_collector.sh continues to coexist (called by unified_monitor.sh)
# for legacy compatibility; disk_monitor.sh is the new parallel entry.
# =====================================================================

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    set -euo pipefail
else
    set -uo pipefail
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! source "${PROJECT_ROOT}/config/config_loader.sh" 2>/dev/null; then
    echo "Warning: Configuration file loading failed, using defaults" >&2
    MONITOR_INTERVAL=${MONITOR_INTERVAL:-10}
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
    SESSION_TIMESTAMP=${SESSION_TIMESTAMP:-$(date +%Y%m%d_%H%M%S)}
fi

if source "${PROJECT_ROOT}/utils/unified_logger.sh" 2>/dev/null; then
    init_logger "disk_monitor" "${LOG_LEVEL:-INFO}" "${LOGS_DIR}/disk_monitor.log" 2>/dev/null || true
else
    log_info()  { echo "[INFO]  $*" >&2; }
    log_warn()  { echo "[WARN]  $*" >&2; }
    log_error() { echo "[ERROR] $*" >&2; }
fi

# Source Y+ unified entry — auto-detects platform/disk model, sources right provider, exposes 4 interface funcs
if ! source "${PROJECT_ROOT}/monitoring/disk_unified_entry.sh"; then
    log_error "Failed to source disk_unified_entry.sh"
    exit 1
fi

# Output CSV path
DISK_CSV="${DISK_CSV:-${LOGS_DIR}/disk_${SESSION_TIMESTAMP}.csv}"
DISK_PID_FILE="${TMP_DIR:-/tmp}/disk_monitor.pid"

mkdir -p "$(dirname "$DISK_CSV")" 2>/dev/null || true

cmd_start() {
    local duration="${1:-0}"
    local interval="${2:-${MONITOR_INTERVAL:-10}}"

    log_info "Starting disk monitor (variant=$(disk_variant), interval=${interval}s, duration=${duration}s)"

    # Write PID + CSV header (timestamp + per-device fields)
    echo $$ > "$DISK_PID_FILE"
    echo "timestamp,$(disk_header)" > "$DISK_CSV"
    log_info "CSV header written to $DISK_CSV (cols=$(head -1 "$DISK_CSV" | awk -F, '{print NF}'))"

    cleanup() {
        log_info "Disk monitor stopping (samples collected: $(wc -l < "$DISK_CSV" 2>/dev/null || echo '?'))"
        rm -f "$DISK_PID_FILE" 2>/dev/null || true
        exit 0
    }
    trap cleanup SIGTERM SIGINT EXIT

    local start_ts
    start_ts=$(date +%s)
    local sample_count=0
    while true; do
        local ts
        ts=$(date "+${TIMESTAMP_FORMAT:-%Y-%m-%d %H:%M:%S}")
        echo "$ts,$(disk_collect)" >> "$DISK_CSV"
        sample_count=$((sample_count + 1))

        if [[ "$duration" -gt 0 ]]; then
            local now
            now=$(date +%s)
            if [[ $((now - start_ts)) -ge "$duration" ]]; then
                log_info "Duration reached, exiting after $sample_count samples"
                break
            fi
        fi
        sleep "$interval"
    done
}

cmd_status() {
    echo "Disk Monitor Status"
    echo "  Variant:         $(disk_variant)"
    echo "  LEDGER_DEVICE:   ${LEDGER_DEVICE:-unknown}"
    echo "  ACCOUNTS_DEVICE: ${ACCOUNTS_DEVICE:-not-set}"
    echo "  CSV:             $DISK_CSV"
    if [[ -f "$DISK_CSV" ]]; then
        echo "  CSV rows:        $(wc -l < "$DISK_CSV")"
        echo "  CSV cols:        $(head -1 "$DISK_CSV" 2>/dev/null | awk -F, '{print NF}')"
    fi
    if [[ -f "$DISK_PID_FILE" ]] && kill -0 "$(cat "$DISK_PID_FILE")" 2>/dev/null; then
        echo "  Process:         running (PID $(cat "$DISK_PID_FILE"))"
    else
        echo "  Process:         not running"
    fi
}

cmd_analyze() {
    local csv="${1:-$DISK_CSV}"
    if [[ ! -f "$csv" ]]; then
        log_error "CSV not found: $csv"
        return 1
    fi
    if ! python3 -c "import pandas" 2>/dev/null; then
        echo "pandas not available, skipping analysis (csv: $csv)"
        return 0
    fi
    python3 - <<PYEOF
import sys
sys.path.insert(0, "${PROJECT_ROOT}")
import pandas as pd
df = pd.read_csv("$csv")
print(f"Rows: {len(df)}")
print(f"Cols: {len(df.columns)}")
print(f"Columns: {list(df.columns)[:5]}...")
print("Summary:")
print(df.describe().T[['mean', 'max']].to_string())
PYEOF
}

cmd_help() {
    cat <<EOF
Disk Monitor — Y+ architecture disk monitor (replaces partially AWS-only iostat_collector.sh)

Usage:
  $0 start [duration_seconds] [interval_seconds]
      duration=0 → run forever (default); interval defaults to \$MONITOR_INTERVAL or 10
  $0 status
  $0 analyze <csv_path>
  $0 help

Detected variant: $(disk_variant)
Output CSV:       $DISK_CSV
EOF
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    cmd="${1:-help}"
    shift || true
    case "$cmd" in
        start)   cmd_start "$@" ;;
        status)  cmd_status ;;
        analyze) cmd_analyze "$@" ;;
        help|-h|--help) cmd_help ;;
        *) cmd_help; exit 1 ;;
    esac
fi
