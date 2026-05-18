#!/bin/bash
# =====================================================================
# Disk Monitoring Provider Interface (Y+ Architecture, CP-3)
# =====================================================================
# Contract that every disk-storage provider (aws_ebs / gcp_pd /
# gcp_hyperdisk / other_local) must implement.
#
# Each provider must export 4 functions:
#   disk_provider_id        — string id (e.g. "aws_ebs", "gcp_pd")
#   disk_provider_init      — one-time init (e.g. probe iostat, no-op OK)
#   disk_provider_header    — CSV header for ONE device (called per device)
#   disk_provider_collect   — CSV row for ONE device (called per device)
#
# Sister architecture to monitoring/network/interface.sh (CP-2.5).
# Reference docs:
#   - analysis-notes/CORRECTED_PLAN.md  CP-3 / CP-2.5
#   - utils/network_field_registry.py   (sister registry for network)
# =====================================================================

# Each provider must override these. Default implementations raise.
disk_provider_id() {
    echo "abstract_disk_provider"
    return 1
}

disk_provider_init() {
    # Optional. Default no-op.
    return 0
}

# Args: $1=device (e.g. "sda"), $2=logical_name ("data" / "accounts")
# Stdout: comma-separated CSV header WITHOUT trailing newline
disk_provider_header() {
    echo "abstract_disk_header_must_be_overridden"
    return 1
}

# Args: $1=device (e.g. "sda"), $2=logical_name ("data" / "accounts")
# Stdout: comma-separated CSV row matching disk_provider_header
disk_provider_collect() {
    echo "abstract_disk_collect_must_be_overridden"
    return 1
}

# ─────────────────────────────────────────────────────────────────────
# Shared iostat-extraction helper (used by aws_ebs / gcp_pd / gcp_hyperdisk).
# Returns 14 raw iostat fields (the universal set, no AWS-specific math).
# Output: r_s,w_s,rkb_s,wkb_s,r_await,w_await,avg_await,aqu_sz,util,rrqm_s,wrqm_s,rrqm_pct,wrqm_pct,total_iops,total_throughput_mibs,read_throughput_mibs,write_throughput_mibs,rareq_sz,wareq_sz
# Field count: 19 (the universal subset every provider returns; provider can add more)
# ─────────────────────────────────────────────────────────────────────
disk_provider_extract_iostat_base() {
    local device="$1"
    local logical_name="$2"
    local monitor_rate="${EBS_MONITOR_RATE:-1}"
    local iostat_pid_file="/tmp/iostat_${device}_${logical_name}.pid"
    local iostat_data_file="/tmp/iostat_${device}_${logical_name}.data"

    # Start continuous iostat sampler if not running
    if [[ ! -f "$iostat_pid_file" ]] || ! kill -0 "$(cat "$iostat_pid_file" 2>/dev/null)" 2>/dev/null; then
        if [[ "$(uname -s)" == "Linux" ]] && command -v iostat >/dev/null 2>&1; then
            iostat -dx "$monitor_rate" > "$iostat_data_file" 2>/dev/null &
            local iostat_pid=$!
            echo "$iostat_pid" > "$iostat_pid_file"
            sleep 0.5  # let iostat write first sample
        fi
    fi

    local device_stats
    device_stats=$(tail -n 20 "$iostat_data_file" 2>/dev/null | awk "/^${device}[[:space:]]/ {latest=\$0} END {print latest}")

    if [[ -z "$device_stats" ]]; then
        # 19 zero-fields
        echo "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"
        return
    fi

    local fields=($device_stats)
    local r_s=${fields[1]:-0}
    local rkb_s=${fields[2]:-0}
    local rrqm_s=${fields[3]:-0}
    local rrqm_pct=${fields[4]:-0}
    local r_await=${fields[5]:-0}
    local rareq_sz=${fields[6]:-0}
    local w_s=${fields[7]:-0}
    local wkb_s=${fields[8]:-0}
    local wrqm_s=${fields[9]:-0}
    local wrqm_pct=${fields[10]:-0}
    local w_await=${fields[11]:-0}
    local wareq_sz=${fields[12]:-0}
    local aqu_sz=${fields[21]:-0}
    local util=${fields[22]:-0}

    local total_iops total_throughput_kbs total_throughput_mibs read_throughput_mibs write_throughput_mibs avg_await
    total_iops=$(awk "BEGIN {printf \"%.2f\", $r_s + $w_s}" 2>/dev/null || echo "0")
    total_throughput_kbs=$(awk "BEGIN {printf \"%.2f\", $rkb_s + $wkb_s}" 2>/dev/null || echo "0")
    total_throughput_mibs=$(awk "BEGIN {printf \"%.2f\", $total_throughput_kbs / 1024}" 2>/dev/null || echo "0")
    read_throughput_mibs=$(awk "BEGIN {printf \"%.2f\", $rkb_s / 1024}" 2>/dev/null || echo "0")
    write_throughput_mibs=$(awk "BEGIN {printf \"%.2f\", $wkb_s / 1024}" 2>/dev/null || echo "0")
    avg_await=$(awk "BEGIN {printf \"%.2f\", ($r_await + $w_await) / 2}" 2>/dev/null || echo "0")

    # 19-field universal set
    echo "$r_s,$w_s,$rkb_s,$wkb_s,$r_await,$w_await,$avg_await,$aqu_sz,$util,$rrqm_s,$wrqm_s,$rrqm_pct,$wrqm_pct,$total_iops,$total_throughput_mibs,$read_throughput_mibs,$write_throughput_mibs,$rareq_sz,$wareq_sz"
}

# Universal CSV header for the 19 fields above (caller prefixes with logical_name_device_).
# Args: $1=prefix (e.g. "data_sda")
disk_provider_universal_header() {
    local prefix="$1"
    echo "${prefix}_r_s,${prefix}_w_s,${prefix}_rkb_s,${prefix}_wkb_s,${prefix}_r_await,${prefix}_w_await,${prefix}_avg_await,${prefix}_aqu_sz,${prefix}_util,${prefix}_rrqm_s,${prefix}_wrqm_s,${prefix}_rrqm_pct,${prefix}_wrqm_pct,${prefix}_total_iops,${prefix}_total_throughput_mibs,${prefix}_read_throughput_mibs,${prefix}_write_throughput_mibs,${prefix}_rareq_sz,${prefix}_wareq_sz"
}

export -f disk_provider_id disk_provider_init disk_provider_header disk_provider_collect disk_provider_extract_iostat_base disk_provider_universal_header
