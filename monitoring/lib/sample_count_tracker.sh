#!/usr/bin/env bash
# =====================================================================
# Sample Count Tracker for Unified Monitor
# =====================================================================
# Owns the small runtime counter used by unified_monitor.sh to decide when
# periodic analysis/report hooks should fire.
# =====================================================================

next_sample_count() {
    local sample_count_file="$1"
    local current_count=0

    if [[ -f "$sample_count_file" ]]; then
        current_count=$(cat "$sample_count_file" 2>/dev/null || echo "0")
        if [[ ! "$current_count" =~ ^[0-9]+$ ]]; then
            current_count=0
        fi
    fi

    current_count=$((current_count + 1))

    mkdir -p "$(dirname "$sample_count_file")" 2>/dev/null || true
    echo "$current_count" > "$sample_count_file"
    echo "$current_count"
}
