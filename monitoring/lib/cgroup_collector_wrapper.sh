#!/usr/bin/env bash
# =====================================================================
# cgroup Collector Wrapper for Unified Monitor
# =====================================================================
# Provides stable 19-field cgroup CSV header/data rows. The Python collector
# is optional at runtime; this wrapper keeps the unified CSV schema stable
# when cgroup collection is disabled or unavailable.
# =====================================================================

CGROUP_PLACEHOLDER_HEADER="cgroup_io_rbytes,cgroup_io_wbytes,cgroup_io_rios,cgroup_io_wios,cgroup_io_dbytes,cgroup_io_dios,cgroup_mem_anon,cgroup_mem_file,cgroup_mem_kernel,cgroup_mem_slab,cgroup_mem_sock,cgroup_mem_swap,cgroup_cpu_usage_usec,cgroup_cpu_user_usec,cgroup_cpu_system_usec,cgroup_cpu_nr_periods,cgroup_cpu_nr_throttled,cgroup_cpu_throttled_usec,cgroup_meta_source"

resolve_cgroup_collector_path() {
    if [[ -n "${CGROUP_COLLECTOR_PATH:-}" ]]; then
        echo "$CGROUP_COLLECTOR_PATH"
        return 0
    fi

    local module_dir
    module_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    echo "${module_dir}/cgroup_collector.py"
}

get_cgroup_header() {
    if [[ "${CGROUP_COLLECTOR_ENABLED:-true}" != "true" ]]; then
        echo "$CGROUP_PLACEHOLDER_HEADER"
        return 0
    fi

    local collector
    collector="$(resolve_cgroup_collector_path)"
    if [[ ! -f "$collector" ]]; then
        log_warn "cgroup_collector.py not found at $collector — emitting placeholder header"
        echo "$CGROUP_PLACEHOLDER_HEADER"
        return 0
    fi

    python3 "$collector" --header 2>/dev/null || echo "$CGROUP_PLACEHOLDER_HEADER"
}

get_cgroup_data() {
    if [[ "${CGROUP_COLLECTOR_ENABLED:-true}" != "true" ]]; then
        echo "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,disabled"
        return 0
    fi

    local collector
    collector="$(resolve_cgroup_collector_path)"
    if [[ ! -f "$collector" ]]; then
        echo "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,unavailable"
        return 0
    fi

    python3 "$collector" --data 2>/dev/null || echo "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,error"
}
