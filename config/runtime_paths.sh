#!/bin/bash
# =====================================================================
# Blockchain Node Benchmark Framework - Runtime Host Path Resolver
# =====================================================================
# Purpose: Resolve /proc, /sys, and cgroup paths in a deployment-mode-aware
#          way. When running inside a K8s DaemonSet pod, the host's /proc
#          must be mounted at /host/proc (convention), and our monitors
#          must read from there instead of the container's own /proc.
#
# Dependency: deployment_mode_detector.sh must run first
#             (DEPLOYMENT_MODE must be set).
#
# Outputs (exported env vars):
#   HOST_PROC      base path for /proc reads      (e.g. /proc, /host/proc)
#   HOST_SYS       base path for /sys reads       (e.g. /sys, /host/sys)
#   HOST_ROOT      base path for /  reads         (e.g. /,    /host)
#   CGROUP_VERSION "v1" | "v2"
#   CGROUP_ROOT    base path for cgroup reads
#                  v2: /sys/fs/cgroup or /host/sys/fs/cgroup
#                  v1: per-controller subdir; use CGROUP_V1_*_PATH below
#   CGROUP_V1_BLKIO_PATH    only for v1
#   CGROUP_V1_MEMORY_PATH   only for v1
#   CGROUP_V1_CPU_PATH      only for v1
#
# Override conventions:
#   - User can set HOST_PROC/HOST_SYS/HOST_ROOT before sourcing to override
#     auto-resolution (useful for tests + non-standard mount points).
#   - K8s DaemonSet manifest (deploy/k8s/04-daemonset.yaml) mounts:
#         /proc → /host/proc
#         /sys  → /host/sys
#         /     → /host  (read-only)
#     and sets HOST_PROC=/host/proc etc. as env, so this file's auto-resolve
#     is a fallback when the env wasn't pre-set by the manifest.
#
# References:
#   - node_exporter --path.procfs / --path.sysfs convention
#   - cAdvisor host-mount convention (/rootfs)
#   - cgroup v2 unified hierarchy: kernel.org/doc/Documentation/cgroup-v2.txt
# =====================================================================

# Ensure deployment mode was detected
if [[ -z "${DEPLOYMENT_MODE_DETECTED:-}" ]]; then
    echo "⚠️  runtime_paths.sh sourced before deployment_mode_detector.sh — " \
         "DEPLOYMENT_MODE not set. Assuming vm_bare." >&2
    DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-vm_bare}"
fi

# Step 1: Resolve HOST_PROC / HOST_SYS / HOST_ROOT
# When running inside a K8s pod or Docker, prefer /host/* if mounted; else
# fall back to local /proc /sys.
_resolve_host_paths() {
    case "$DEPLOYMENT_MODE" in
        k8s_eks|k8s_gke|k8s_other|docker)
            # Container modes: prefer /host/* mount (DaemonSet convention)
            HOST_PROC="${HOST_PROC:-$(_pick_path /host/proc /proc)}"
            HOST_SYS="${HOST_SYS:-$(_pick_path /host/sys /sys)}"
            HOST_ROOT="${HOST_ROOT:-$(_pick_path /host /)}"
            ;;
        vm_bare|vm_systemd|*)
            # VM modes: always use local paths
            HOST_PROC="${HOST_PROC:-/proc}"
            HOST_SYS="${HOST_SYS:-/sys}"
            HOST_ROOT="${HOST_ROOT:-/}"
            ;;
    esac
}

# Pick first existing readable directory from arguments
_pick_path() {
    local p
    for p in "$@"; do
        if [[ -d "$p" && -r "$p" ]]; then
            echo "$p"
            return 0
        fi
    done
    # Last resort: echo the last argument (so we still get a valid string)
    echo "${@: -1}"
}

# Step 2: Detect cgroup version
# v2 marker: /sys/fs/cgroup/cgroup.controllers exists (unified hierarchy)
# v1 marker: /sys/fs/cgroup is a tmpfs containing controller subdirs
#            (blkio, memory, cpu, ...)
_detect_cgroup_version() {
    local cg_base="${HOST_SYS}/fs/cgroup"

    if [[ -f "${cg_base}/cgroup.controllers" ]]; then
        CGROUP_VERSION="v2"
        CGROUP_ROOT="${cg_base}"
    elif [[ -d "${cg_base}/blkio" ]] || [[ -d "${cg_base}/memory" ]]; then
        CGROUP_VERSION="v1"
        CGROUP_ROOT="${cg_base}"
        CGROUP_V1_BLKIO_PATH="${cg_base}/blkio"
        CGROUP_V1_MEMORY_PATH="${cg_base}/memory"
        CGROUP_V1_CPU_PATH="${cg_base}/cpu,cpuacct"
        # Some systems put cpu and cpuacct under separate dirs (older Debian)
        if [[ ! -d "$CGROUP_V1_CPU_PATH" ]]; then
            CGROUP_V1_CPU_PATH="${cg_base}/cpu"
        fi
    else
        # Edge case: cgroup not mounted (or only partially). Mark as unknown
        # so downstream collectors can fail-soft.
        CGROUP_VERSION="unknown"
        CGROUP_ROOT=""
        echo "⚠️  cgroup not detected at ${cg_base} — collectors will fail-soft" >&2
    fi
}

# Step 3: Print resolved state
_print_path_state() {
    echo "📂 Host paths resolved:" >&2
    echo "   HOST_PROC=${HOST_PROC}" >&2
    echo "   HOST_SYS=${HOST_SYS}" >&2
    echo "   HOST_ROOT=${HOST_ROOT}" >&2
    echo "   CGROUP_VERSION=${CGROUP_VERSION}" >&2
    echo "   CGROUP_ROOT=${CGROUP_ROOT}" >&2
    if [[ "$CGROUP_VERSION" == "v1" ]]; then
        echo "   CGROUP_V1_BLKIO_PATH=${CGROUP_V1_BLKIO_PATH}" >&2
        echo "   CGROUP_V1_MEMORY_PATH=${CGROUP_V1_MEMORY_PATH}" >&2
        echo "   CGROUP_V1_CPU_PATH=${CGROUP_V1_CPU_PATH}" >&2
    fi
}

# Main entry — called by config_loader.sh after detect_deployment_mode
resolve_runtime_paths() {
    _resolve_host_paths
    _detect_cgroup_version
    _print_path_state

    export HOST_PROC HOST_SYS HOST_ROOT
    export CGROUP_VERSION CGROUP_ROOT
    if [[ "$CGROUP_VERSION" == "v1" ]]; then
        export CGROUP_V1_BLKIO_PATH CGROUP_V1_MEMORY_PATH CGROUP_V1_CPU_PATH
    fi
}

# When sourced via config_loader.sh: do NOT auto-execute. The loader calls
# resolve_runtime_paths explicitly. When executed directly: run + print state.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Standalone mode: assume vm_bare if no DEPLOYMENT_MODE
    DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-vm_bare}"
    DEPLOYMENT_MODE_DETECTED="${DEPLOYMENT_MODE_DETECTED:-true}"
    resolve_runtime_paths
fi
