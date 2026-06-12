#!/bin/bash
# =====================================================================
# Network Monitor - provider-aware NIC monitoring entrypoint
# =====================================================================
# Replaces the retired AWS-only ENA monitor with provider-aware NIC monitoring.
# Routes to aws_ena.sh | gcp_gvnic.sh | gcp_virtio.sh | other_none.sh
# based on (CLOUD_PROVIDER, NIC_DRIVER) detected at runtime.
#
# This script is invoked by monitoring/monitoring_coordinator.sh task "network".
# =====================================================================

# Strict error handling - allow safe sourcing
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    set -euo pipefail
else
    set -uo pipefail
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load config (failure-tolerant)
if ! source "${PROJECT_ROOT}/config/config_loader.sh" 2>/dev/null; then
    echo "Warning: Configuration file loading failed, using defaults" >&2
    MONITOR_INTERVAL=${MONITOR_INTERVAL:-10}
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
    SESSION_TIMESTAMP=${SESSION_TIMESTAMP:-$(date +%Y%m%d_%H%M%S)}
fi

# Logger (failure-tolerant)
if source "${PROJECT_ROOT}/utils/unified_logger.sh" 2>/dev/null; then
    init_logger "network_monitor" "${LOG_LEVEL:-INFO}" "${LOGS_DIR}/network_monitor.log" 2>/dev/null || true
else
    # Stub loggers when utils/unified_logger.sh unavailable
    log_info()  { echo "[INFO]  $*" >&2; }
    log_warn()  { echo "[WARN]  $*" >&2; }
    log_error() { echo "[ERROR] $*" >&2; }
fi

# Source provider-aware entrypoint; it detects platform/driver and exposes interface functions
if ! source "${PROJECT_ROOT}/monitoring/network_unified_entry.sh"; then
    log_error "Failed to source network_unified_entry.sh"
    exit 1
fi

# Output CSV path — uses "network_" prefix (not "ena_network_") to distinguish from legacy
NETWORK_CSV="${NETWORK_CSV:-${LOGS_DIR}/network_${SESSION_TIMESTAMP}.csv}"
NETWORK_PID_FILE="${NETWORK_PID_FILE:-${TMP_DIR:-/tmp}/network_monitor.pid}"

mkdir -p "$(dirname "$NETWORK_CSV")" 2>/dev/null || true

# === Commands ===

cmd_start() {
    local duration="${1:-0}"          # 0 = run forever until SIGTERM
    local interval="${2:-${MONITOR_INTERVAL:-10}}"

    log_info "Starting network monitor (variant=$NETWORK_PROVIDER_VARIANT, interface=${NETWORK_INTERFACE:-?}, interval=${interval}s, duration=${duration}s)"

    # Verify provider readiness
    if ! init_network_monitoring; then
        log_error "init_network_monitoring failed for variant=$NETWORK_PROVIDER_VARIANT (interface=${NETWORK_INTERFACE:-?}); falling back to other_none"
        # Re-source other_none as last-resort fallback
        source "${PROJECT_ROOT}/monitoring/network/other_none.sh"
        if ! init_network_monitoring; then
            log_error "Even other_none.sh init failed; aborting"
            return 1
        fi
    fi

    # Write PID + CSV header
    echo $$ > "$NETWORK_PID_FILE"
    generate_network_csv_header > "$NETWORK_CSV"
    log_info "CSV header written to $NETWORK_CSV (cols=$(head -1 "$NETWORK_CSV" | awk -F, '{print NF}'))"

    # Graceful shutdown
    cleanup() {
        log_info "Network monitor stopping (samples collected: $(wc -l < "$NETWORK_CSV" 2>/dev/null || echo '?'))"
        rm -f "$NETWORK_PID_FILE" 2>/dev/null || true
        exit 0
    }
    trap cleanup SIGTERM SIGINT EXIT

    # Collection loop
    local start_ts=$(date +%s)
    local sample_count=0
    while true; do
        collect_network_metrics >> "$NETWORK_CSV"
        sample_count=$((sample_count + 1))

        if [[ "$duration" -gt 0 ]]; then
            local now=$(date +%s)
            if [[ $((now - start_ts)) -ge "$duration" ]]; then
                log_info "Duration reached, exiting after $sample_count samples"
                break
            fi
        fi
        sleep "$interval"
    done
}

cmd_status() {
    echo "Network Monitor Status"
    echo "  Variant:         ${NETWORK_PROVIDER_VARIANT:-unknown}"
    echo "  Provider file:   ${NETWORK_PROVIDER_FILE:-unknown}"
    echo "  Interface:       ${NETWORK_INTERFACE:-unknown}"
    echo "  CSV:             $NETWORK_CSV"
    if [[ -f "$NETWORK_CSV" ]]; then
        echo "  CSV rows:        $(wc -l < "$NETWORK_CSV")"
        echo "  CSV cols:        $(head -1 "$NETWORK_CSV" 2>/dev/null | awk -F, '{print NF}')"
    fi
    if [[ -f "$NETWORK_PID_FILE" ]] && kill -0 "$(cat "$NETWORK_PID_FILE")" 2>/dev/null; then
        echo "  Process:         running (PID $(cat "$NETWORK_PID_FILE"))"
    else
        echo "  Process:         not running"
    fi
}

cmd_analyze() {
    local csv="${1:-$NETWORK_CSV}"
    if [[ ! -f "$csv" ]]; then
        log_error "CSV not found: $csv"
        return 1
    fi
    # Graceful degradation: pandas may not be installed (cloudtop case)
    if ! python3 -c "import pandas" 2>/dev/null; then
        echo "pandas not available, skipping analysis (csv: $csv)"
        return 0
    fi
    python3 - <<PYEOF
import sys, json
sys.path.insert(0, "${PROJECT_ROOT}")
import pandas as pd
from analysis.network_analyzer import NetworkAnalyzer
df = pd.read_csv("$csv")
print(json.dumps(NetworkAnalyzer.analyze(df), indent=2, default=str))
PYEOF
}

cmd_help() {
    cat <<EOF
Network Monitor - provider-aware NIC monitor

Usage:
  $0 start [duration_seconds] [interval_seconds]
      duration=0 → run forever (default); interval defaults to \$MONITOR_INTERVAL or 10
  $0 status
  $0 analyze <csv_path>
  $0 help

Detected platform: ${NETWORK_PROVIDER_VARIANT:-unknown}
Output CSV:       $NETWORK_CSV
EOF
}

# === Entry ===
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
