#!/bin/bash
# =====================================================================
# Monitoring Runtime Contract Audit
# =====================================================================
# Read-only audit for monitoring runtime artifacts. This script is designed
# to catch silent monitor regressions before refactoring unified_monitor.sh.
# =====================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

LOGS_DIR_ARG=""
REPORTS_DIR_ARG=""
MEMORY_DIR_ARG=""
ARCHIVE_DIR_ARG=""
MONITOR_INTERVAL_ARG="${MONITOR_INTERVAL:-5}"
BLOCK_HEIGHT_RATE_ARG="${BLOCK_HEIGHT_MONITOR_RATE:-1}"
SKIP_FRESHNESS=false
REQUIRE_REPORT=false
REQUIRE_ARCHIVE=false

failures=0
warnings=0

usage() {
    cat <<EOF
Usage: $0 [options]

Options:
  --logs-dir DIR                 Runtime logs directory
  --reports-dir DIR              Runtime reports directory
  --memory-dir DIR               Runtime memory-share directory
  --archive-dir DIR              Archived run directory
  --monitor-interval SECONDS     Unified monitor interval, default: ${MONITOR_INTERVAL_ARG}
  --block-height-rate RATE       Block-height monitor rate per second, default: ${BLOCK_HEIGHT_RATE_ARG}
  --skip-freshness               Skip mtime freshness checks for archived/synthetic fixtures
  --require-report               Require an HTML report in reports-dir
  --require-archive              Require archive subdirectories logs/reports/vegeta_results/stats
  -h, --help                     Show this help
EOF
}

log_ok() { echo "✅ $*"; }
log_warn() { warnings=$((warnings + 1)); echo "⚠️  $*" >&2; }
log_fail() { failures=$((failures + 1)); echo "❌ $*" >&2; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --logs-dir) LOGS_DIR_ARG="$2"; shift 2 ;;
        --reports-dir) REPORTS_DIR_ARG="$2"; shift 2 ;;
        --memory-dir) MEMORY_DIR_ARG="$2"; shift 2 ;;
        --archive-dir) ARCHIVE_DIR_ARG="$2"; shift 2 ;;
        --monitor-interval) MONITOR_INTERVAL_ARG="$2"; shift 2 ;;
        --block-height-rate) BLOCK_HEIGHT_RATE_ARG="$2"; shift 2 ;;
        --skip-freshness) SKIP_FRESHNESS=true; shift ;;
        --require-report) REQUIRE_REPORT=true; shift ;;
        --require-archive) REQUIRE_ARCHIVE=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
    esac
done

if [[ -n "$ARCHIVE_DIR_ARG" ]]; then
    LOGS_DIR_ARG="${LOGS_DIR_ARG:-${ARCHIVE_DIR_ARG}/logs}"
    REPORTS_DIR_ARG="${REPORTS_DIR_ARG:-${ARCHIVE_DIR_ARG}/reports}"
    MEMORY_DIR_ARG="${MEMORY_DIR_ARG:-${ARCHIVE_DIR_ARG}/stats}"
fi

if [[ -z "$LOGS_DIR_ARG" || -z "$MEMORY_DIR_ARG" ]]; then
    echo "Missing required --logs-dir and/or --memory-dir" >&2
    usage
    exit 2
fi

is_number() {
    [[ "${1:-}" =~ ^[0-9]+([.][0-9]+)?$ ]]
}

mtime_age_seconds() {
    local path="$1"
    python3 - "$path" <<'PY'
import os, sys, time
path = sys.argv[1]
print(max(0, int(time.time() - os.path.getmtime(path))))
PY
}

mtime_epoch_seconds() {
    local path="$1"
    python3 - "$path" <<'PY'
import os, sys
print(int(os.path.getmtime(sys.argv[1])))
PY
}

real_path() {
    local path="$1"
    python3 - "$path" <<'PY'
import os, sys
print(os.path.realpath(sys.argv[1]))
PY
}

timestamp_epoch_seconds() {
    local timestamp="$1"
    python3 - "$timestamp" <<'PY'
from datetime import datetime, timezone
import sys

raw = sys.argv[1].strip()
if not raw or raw == "null":
    sys.exit(1)

formats = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
)

for fmt in formats:
    try:
        dt = datetime.strptime(raw, fmt)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        print(int(dt.timestamp()))
        sys.exit(0)
    except ValueError:
        pass

sys.exit(1)
PY
}

json_field() {
    local json_file="$1"
    local field="$2"
    jq -r --arg field "$field" '.[$field] // empty' "$json_file" 2>/dev/null || true
}

check_fresh() {
    local path="$1"
    local source_name="$2"
    local threshold="$3"

    if [[ "$SKIP_FRESHNESS" == "true" ]]; then
        return 0
    fi
    if [[ ! -e "$path" ]]; then
        log_fail "$source_name missing: $path"
        return 1
    fi
    if ! is_number "$threshold"; then
        threshold=15
    fi

    local age
    age=$(mtime_age_seconds "$path")
    if awk "BEGIN {exit !($age <= $threshold)}"; then
        log_ok "$source_name fresh (${age}s <= ${threshold}s)"
    else
        log_fail "$source_name stale (${age}s > ${threshold}s): $path"
    fi
}

csv_field_index() {
    local csv_file="$1"
    local field="$2"
    awk -v target="$field" -F, 'NR==1 {for (i=1; i<=NF; i++) if ($i == target) {print i; exit}}' "$csv_file"
}

csv_has_field() {
    [[ -n "$(csv_field_index "$1" "$2")" ]]
}

csv_data_row_count() {
    local csv_file="$1"
    awk 'END {print (NR > 0 ? NR - 1 : 0)}' "$csv_file"
}

csv_last_field_value() {
    local csv_file="$1"
    local field="$2"
    local idx
    idx="$(csv_field_index "$csv_file" "$field")"
    if [[ -z "$idx" ]]; then
        return 1
    fi
    awk -F, -v idx="$idx" 'NF {value=$idx} END {print value}' "$csv_file"
}

newest_performance_csv() {
    find "$LOGS_DIR_ARG" -maxdepth 1 -type f -name 'performance_*.csv' ! -name 'performance_latest.csv' -print0 2>/dev/null \
        | xargs -0 ls -t 2>/dev/null \
        | head -1 || true
}

check_csv_widths() {
    local csv_file="$1"
    local label="$2"
    if [[ ! -s "$csv_file" ]]; then
        log_fail "$label missing or empty: $csv_file"
        return
    fi

    local expected
    expected=$(awk -F, 'NR==1 {print NF}' "$csv_file")
    if [[ -z "$expected" || "$expected" -lt 1 ]]; then
        log_fail "$label header has invalid width: $csv_file"
        return
    fi

    local bad
    bad=$(awk -F, -v expected="$expected" 'NR>1 && NF != expected {print NR ":" NF; exit}' "$csv_file")
    if [[ -n "$bad" ]]; then
        log_fail "$label row width mismatch at ${bad}, expected ${expected}: $csv_file"
    else
        log_ok "$label row widths match header (${expected} fields)"
    fi
}

check_json_fields() {
    local json_file="$1"
    local label="$2"
    shift 2

    if [[ ! -s "$json_file" ]]; then
        log_fail "$label missing or empty: $json_file"
        return
    fi
    if ! jq empty "$json_file" >/dev/null 2>&1; then
        log_fail "$label malformed JSON: $json_file"
        return
    fi

    local field missing=false
    for field in "$@"; do
        if ! jq -e --arg field "$field" 'has($field)' "$json_file" >/dev/null 2>&1; then
            log_fail "$label missing field: $field"
            missing=true
        fi
    done
    [[ "$missing" == "false" ]] && log_ok "$label JSON fields present"
}

check_performance_csv() {
    local perf_csv="${LOGS_DIR_ARG}/performance_latest.csv"
    local latest_csv="$perf_csv"
    [[ -f "$perf_csv" ]] || perf_csv="$(ls -t "${LOGS_DIR_ARG}"/performance_*.csv 2>/dev/null | head -1 || true)"

    if [[ -z "$perf_csv" || ! -f "$perf_csv" ]]; then
        log_fail "performance CSV not found in $LOGS_DIR_ARG"
        return
    fi

    check_csv_widths "$perf_csv" "performance CSV"

    local required_fields=(
        timestamp
        cpu_usage
        mem_usage
        local_block_height
        mainnet_block_height
        block_height_diff
        local_health
        mainnet_health
        data_loss
        sync_mode
        sync_status
        lag_value
        lag_unit
        freshness_gap_seconds
        probe_error
        current_qps
        rpc_latency_ms
        qps_data_available
        cloud_provider
    )

    local field
    for field in "${required_fields[@]}"; do
        if csv_has_field "$perf_csv" "$field"; then
            log_ok "performance CSV contains field: $field"
        else
            log_fail "performance CSV missing field: $field"
        fi
    done

    local last_field
    last_field=$(awk -F, 'NR==1 {print $NF}' "$perf_csv")
    if [[ "$last_field" == "cloud_provider" ]]; then
        log_ok "performance CSV cloud_provider is final column"
    else
        log_fail "performance CSV final column is '$last_field', expected cloud_provider"
    fi

    local threshold
    threshold=$(awk -v interval="$MONITOR_INTERVAL_ARG" 'BEGIN {printf "%.0f", (2 * interval) + 5}')
    check_fresh "$perf_csv" "performance CSV" "$threshold"

    if [[ -e "$latest_csv" ]]; then
        local newest
        newest="$(newest_performance_csv)"
        if [[ -n "$newest" && -f "$newest" ]]; then
            local latest_mtime newest_mtime
            latest_mtime="$(mtime_epoch_seconds "$latest_csv")"
            newest_mtime="$(mtime_epoch_seconds "$newest")"

            if [[ -L "$latest_csv" ]]; then
                local latest_target newest_target
                latest_target="$(real_path "$latest_csv")"
                newest_target="$(real_path "$newest")"
                if [[ "$latest_target" == "$newest_target" ]]; then
                    log_ok "performance_latest.csv points to newest performance CSV"
                else
                    log_fail "performance_latest.csv points to $latest_target, expected newest $newest_target"
                fi
            elif awk "BEGIN {exit !(($latest_mtime + 1) >= $newest_mtime)}"; then
                log_ok "performance_latest.csv is at least as fresh as newest performance CSV"
            else
                log_fail "performance_latest.csv is older than newest performance CSV: $latest_csv"
            fi
        fi
    fi
}

check_block_height_csv() {
    local block_csv
    block_csv="$(ls -t "${LOGS_DIR_ARG}"/block_height_monitor_*.csv 2>/dev/null | head -1 || true)"
    if [[ -z "$block_csv" || ! -f "$block_csv" ]]; then
        log_fail "block height CSV not found in $LOGS_DIR_ARG"
        return
    fi

    check_csv_widths "$block_csv" "block height CSV"

    local expected
    if source "${PROJECT_ROOT}/config/csv_schema_registry.sh" >/dev/null 2>&1 && declare -F csv_registry_block_csv_header >/dev/null 2>&1; then
        expected="$(csv_registry_block_csv_header)"
    else
        expected="timestamp,local_block_height,mainnet_block_height,block_height_diff,local_health,mainnet_health,data_loss,sync_mode,sync_status,lag_value,lag_unit,freshness_gap_seconds,probe_error"
    fi
    local actual
    actual="$(head -1 "$block_csv")"
    if [[ "$actual" == "$expected" ]]; then
        log_ok "block height CSV header matches registry"
    else
        log_fail "block height CSV header mismatch"
        echo "expected: $expected" >&2
        echo "actual:   $actual" >&2
    fi

    local threshold
    threshold=$(awk -v rate="$BLOCK_HEIGHT_RATE_ARG" 'BEGIN {if (rate <= 0) rate=1; printf "%.0f", (2 / rate) + 5}')
    check_fresh "$block_csv" "block height CSV" "$threshold"
}

check_memory_json() {
    local latest="${MEMORY_DIR_ARG}/latest_metrics.json"
    local unified="${MEMORY_DIR_ARG}/unified_metrics.json"
    local sync_cache="${MEMORY_DIR_ARG}/block_height_monitor_cache.json"
    local sample_count_file="${MEMORY_DIR_ARG}/sample_count"

    check_json_fields "$latest" "latest_metrics" timestamp cpu_usage memory_usage
    check_json_fields "$unified" "unified_metrics" timestamp cpu_usage memory_usage detailed_data
    check_json_fields "$sync_cache" "block_height_monitor_cache" timestamp timestamp_ms sync_mode sync_status local_health data_loss

    local perf_threshold
    perf_threshold=$(awk -v interval="$MONITOR_INTERVAL_ARG" 'BEGIN {printf "%.0f", (2 * interval) + 5}')
    check_fresh "$latest" "latest_metrics" "$perf_threshold"
    check_fresh "$unified" "unified_metrics" "$perf_threshold"

    local sync_threshold
    sync_threshold=$(awk -v rate="$BLOCK_HEIGHT_RATE_ARG" 'BEGIN {if (rate <= 0) rate=1; printf "%.0f", (2 / rate) + 5}')
    check_fresh "$sync_cache" "block_height_monitor_cache" "$sync_threshold"

    local perf_csv="${LOGS_DIR_ARG}/performance_latest.csv"
    [[ -f "$perf_csv" ]] || perf_csv="$(newest_performance_csv)"
    if [[ -n "$perf_csv" && -f "$perf_csv" && -s "$latest" && -s "$unified" ]]; then
        local csv_timestamp latest_timestamp unified_timestamp
        csv_timestamp="$(csv_last_field_value "$perf_csv" "timestamp" || true)"
        latest_timestamp="$(json_field "$latest" "timestamp")"
        unified_timestamp="$(json_field "$unified" "timestamp")"

        if [[ -n "$csv_timestamp" && "$latest_timestamp" == "$csv_timestamp" ]]; then
            log_ok "latest_metrics timestamp matches performance CSV latest row"
        else
            log_fail "latest_metrics timestamp mismatch: json='${latest_timestamp:-<empty>}' csv='${csv_timestamp:-<empty>}'"
        fi

        if [[ -n "$csv_timestamp" && "$unified_timestamp" == "$csv_timestamp" ]]; then
            log_ok "unified_metrics timestamp matches performance CSV latest row"
        else
            log_fail "unified_metrics timestamp mismatch: json='${unified_timestamp:-<empty>}' csv='${csv_timestamp:-<empty>}'"
        fi
    fi

    if [[ -s "$sync_cache" ]]; then
        local cache_timestamp cache_timestamp_ms parsed_epoch expected_ms delta_ms
        cache_timestamp="$(json_field "$sync_cache" "timestamp")"
        cache_timestamp_ms="$(json_field "$sync_cache" "timestamp_ms")"
        if [[ "$cache_timestamp_ms" =~ ^[0-9]+$ ]]; then
            log_ok "block_height_monitor_cache timestamp_ms is numeric"
        else
            log_fail "block_height_monitor_cache timestamp_ms invalid: ${cache_timestamp_ms:-<empty>}"
        fi

        if parsed_epoch="$(timestamp_epoch_seconds "$cache_timestamp" 2>/dev/null)" && [[ "$cache_timestamp_ms" =~ ^[0-9]+$ ]]; then
            expected_ms=$((parsed_epoch * 1000))
            delta_ms=$((cache_timestamp_ms - expected_ms))
            [[ "$delta_ms" -lt 0 ]] && delta_ms=$((0 - delta_ms))
            if [[ "$delta_ms" -le 2000 ]]; then
                log_ok "block_height_monitor_cache timestamp and timestamp_ms are coherent"
            else
                log_fail "block_height_monitor_cache timestamp_ms differs from timestamp by ${delta_ms}ms"
            fi
        else
            log_fail "block_height_monitor_cache timestamp is not parseable: ${cache_timestamp:-<empty>}"
        fi
    fi

    if [[ -f "$sample_count_file" ]]; then
        local sample_count
        sample_count="$(cat "$sample_count_file" 2>/dev/null || true)"
        if [[ "$sample_count" =~ ^[0-9]+$ && "$sample_count" -gt 0 ]]; then
            log_ok "sample_count is numeric and positive"
        else
            log_fail "sample_count invalid: ${sample_count:-<empty>}"
        fi

        local perf_csv="${LOGS_DIR_ARG}/performance_latest.csv"
        [[ -f "$perf_csv" ]] || perf_csv="$(newest_performance_csv)"
        if [[ -n "$perf_csv" && -f "$perf_csv" && "$sample_count" =~ ^[0-9]+$ ]]; then
            local row_count
            row_count="$(csv_data_row_count "$perf_csv")"
            if [[ "$sample_count" -eq "$row_count" ]]; then
                log_ok "sample_count matches performance CSV data row count"
            else
                log_fail "sample_count mismatch: sample_count=$sample_count performance_rows=$row_count"
            fi
        fi
    else
        log_warn "sample_count not found; cannot verify monitor loop row counter"
    fi
}

check_proxy_csv() {
    local proxy_csv="${LOGS_DIR_ARG}/proxy_method.csv"
    if [[ ! -f "$proxy_csv" ]]; then
        log_warn "proxy_method.csv not found; per-method attribution unavailable for this run"
        return
    fi
    check_csv_widths "$proxy_csv" "proxy_method CSV"
    if [[ "$(wc -l < "$proxy_csv")" -gt 1 ]]; then
        log_ok "proxy_method CSV contains request rows"
    else
        log_warn "proxy_method CSV has header only"
    fi
}

check_reports() {
    [[ "$REQUIRE_REPORT" == "true" ]] || return 0
    if [[ -z "$REPORTS_DIR_ARG" || ! -d "$REPORTS_DIR_ARG" ]]; then
        log_fail "reports directory missing: ${REPORTS_DIR_ARG:-<unset>}"
        return
    fi
    local html_file
    html_file="$(ls -t "${REPORTS_DIR_ARG}"/*.html 2>/dev/null | head -1 || true)"
    if [[ -z "$html_file" ]]; then
        log_fail "HTML report not found in $REPORTS_DIR_ARG"
        return
    fi
    log_ok "HTML report found: $html_file"
    if grep -qE "Data Quality|Data Not Available|No Data" "$html_file"; then
        log_ok "HTML report contains data-quality/degraded wording"
    else
        log_warn "HTML report does not contain obvious data-quality/degraded wording"
    fi
}

check_archive() {
    [[ "$REQUIRE_ARCHIVE" == "true" ]] || return 0
    if [[ -z "$ARCHIVE_DIR_ARG" || ! -d "$ARCHIVE_DIR_ARG" ]]; then
        log_fail "archive directory missing: ${ARCHIVE_DIR_ARG:-<unset>}"
        return
    fi
    local dir
    for dir in logs reports vegeta_results stats; do
        if [[ -d "${ARCHIVE_DIR_ARG}/${dir}" ]]; then
            log_ok "archive contains $dir/"
        else
            log_fail "archive missing $dir/"
        fi
    done
    if [[ -f "${ARCHIVE_DIR_ARG}/test_summary.json" ]]; then
        log_ok "archive contains test_summary.json"
    else
        log_fail "archive missing test_summary.json"
    fi
}

echo "🔎 Monitoring runtime contract audit"
echo "   logs:    $LOGS_DIR_ARG"
echo "   reports: ${REPORTS_DIR_ARG:-<not checked>}"
echo "   memory:  $MEMORY_DIR_ARG"

check_performance_csv
check_block_height_csv
check_memory_json
check_proxy_csv
check_reports
check_archive

echo ""
echo "Audit summary: failures=$failures warnings=$warnings"
if [[ "$failures" -gt 0 ]]; then
    exit 1
fi
exit 0
