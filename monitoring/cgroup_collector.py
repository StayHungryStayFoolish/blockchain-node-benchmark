#!/usr/bin/env python3
"""
cgroup_collector.py — cgroup v1/v2 + 4-mode auto-detect collector
=================================================================

Purpose
-------
Pod-aware IO / Memory / CPU metric collector. Reads cgroup interface files
from HOST_SYS/HOST_PROC, normalizes cgroup v1 vs v2 differences, and emits
a single CSV row (or header) compatible with the framework's
{logical_name}_{device}_{metric} schema.

Why
---
Bare iostat / sar provides host-level metrics, but in K8s / Docker the host
is shared. To attribute IO to the blockchain process, we read cgroup
counters from the process's own slice. This collector covers 4 primary modes:
  Mode A: cgroup v2 unified hierarchy            (modern Linux, K8s, cloudtop)
  Mode B: cgroup v1 split-controller hierarchy   (older RHEL, EKS 1.21-)
  Mode C: cgroup not mounted / unreadable        (fail-soft → NA fields)
  Mode D: target cgroup path not found           (PID unresolvable → NA)

Inputs (env vars from config_loader.sh):
  HOST_PROC        base /proc path           default /proc
  HOST_SYS         base /sys path            default /sys
  CGROUP_VERSION   "v1" | "v2" | "unknown"   set by runtime_paths.sh
  CGROUP_ROOT      base cgroup mount         set by runtime_paths.sh
  CGROUP_V1_BLKIO_PATH    only set for v1
  CGROUP_V1_MEMORY_PATH   only set for v1
  CGROUP_V1_CPU_PATH      only set for v1
  TARGET_PID       optional explicit PID to inspect (default: self)
  TARGET_CGROUP    optional explicit cgroup path (overrides PID lookup)

Outputs (stdout, CSV — one line per invocation):
  --header → CSV header (19 columns)
  --data   → CSV row (default mode)

Schema (19 fields, all numeric except meta_source):
  IO  (6): cgroup_io_rbytes, _wbytes, _rios, _wios, _dbytes, _dios
  MEM (6): cgroup_mem_anon, _file, _kernel, _slab, _sock, _swap
  CPU (6): cgroup_cpu_usage_usec, _user_usec, _system_usec,
           cgroup_cpu_nr_periods, _nr_throttled, _throttled_usec
  META(1): cgroup_meta_source     ∈ {v2,v1,unmounted,unresolved}

Verification (cloudtop, vm_bare + cgroup v2):
  python3 monitoring/cgroup_collector.py --header
  → cgroup_io_rbytes,cgroup_io_wbytes,...,cgroup_meta_source
  python3 monitoring/cgroup_collector.py --data
  → 12345,67890,...,v2

Failure semantics
-----------------
Never raises. Unreadable files → 0 for numeric, "unmounted"/"unresolved"
for meta. The framework's data quality checker treats "0" as zero (not NA)
and meta_source surfaces the actual collection mode for diagnostics.

References
----------
- cgroup v2: kernel.org/doc/Documentation/admin-guide/cgroup-v2.rst
- cgroup v1: kernel.org/doc/Documentation/cgroup-v1/*.txt
- /proc/<pid>/cgroup format: man 7 cgroups
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

IO_FIELDS = (
    "cgroup_io_rbytes",
    "cgroup_io_wbytes",
    "cgroup_io_rios",
    "cgroup_io_wios",
    "cgroup_io_dbytes",  # discard (DAX/trim)
    "cgroup_io_dios",
)

MEM_FIELDS = (
    "cgroup_mem_anon",
    "cgroup_mem_file",
    "cgroup_mem_kernel",
    "cgroup_mem_slab",
    "cgroup_mem_sock",
    "cgroup_mem_swap",
)

CPU_FIELDS = (
    "cgroup_cpu_usage_usec",
    "cgroup_cpu_user_usec",
    "cgroup_cpu_system_usec",
    "cgroup_cpu_nr_periods",
    "cgroup_cpu_nr_throttled",
    "cgroup_cpu_throttled_usec",
)

META_FIELDS = ("cgroup_meta_source",)

ALL_FIELDS = IO_FIELDS + MEM_FIELDS + CPU_FIELDS + META_FIELDS  # 19 cols


# ---------------------------------------------------------------------------
# Env resolution
# ---------------------------------------------------------------------------

def _env(name: str, default: str) -> str:
    """Read env var, fall back to default if unset or empty."""
    v = os.environ.get(name, "")
    return v if v else default


def get_host_paths() -> Dict[str, str]:
    """Resolve HOST_PROC / HOST_SYS / cgroup paths from env (set by runtime_paths.sh)."""
    return {
        "HOST_PROC": _env("HOST_PROC", "/proc"),
        "HOST_SYS": _env("HOST_SYS", "/sys"),
        "CGROUP_VERSION": _env("CGROUP_VERSION", "auto"),
        "CGROUP_ROOT": _env("CGROUP_ROOT", ""),
        "CGROUP_V1_BLKIO_PATH": _env("CGROUP_V1_BLKIO_PATH", ""),
        "CGROUP_V1_MEMORY_PATH": _env("CGROUP_V1_MEMORY_PATH", ""),
        "CGROUP_V1_CPU_PATH": _env("CGROUP_V1_CPU_PATH", ""),
    }


def _detect_cgroup_version_fallback(host_sys: str) -> Tuple[str, str]:
    """Fall-back cgroup version detection when env wasn't set.
    Mirrors logic in runtime_paths.sh._detect_cgroup_version.
    """
    base = f"{host_sys}/fs/cgroup"
    if Path(f"{base}/cgroup.controllers").is_file():
        return "v2", base
    if Path(f"{base}/blkio").is_dir() or Path(f"{base}/memory").is_dir():
        return "v1", base
    return "unknown", ""


# ---------------------------------------------------------------------------
# Target cgroup path resolution
# ---------------------------------------------------------------------------

def resolve_target_cgroup(host_proc: str, target_pid: Optional[str]) -> Optional[str]:
    """Read /proc/<pid>/cgroup and return the cgroup path the process belongs to.

    cgroup v2 format:  0::<path>
    cgroup v1 format:  <hier_id>:<controller_list>:<path>

    For v1 we return the path from the `blkio` (or first non-empty) controller.
    Returns None if /proc/<pid>/cgroup cannot be read.
    """
    pid = target_pid or "self"
    cg_file = Path(f"{host_proc}/{pid}/cgroup")
    if not cg_file.is_file():
        return None
    try:
        content = cg_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    # Prefer v2 line (hier_id=0, empty controller field)
    for line in content.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        hier, ctrls, path = parts
        if hier == "0" and ctrls == "":
            return path or "/"
        # v1: pick blkio line if present
        if "blkio" in ctrls.split(","):
            return path or "/"
    # Fallback: first line's path
    for line in content.splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3:
            return parts[2] or "/"
    return None


# ---------------------------------------------------------------------------
# File parsers — cgroup v2
# ---------------------------------------------------------------------------

def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _parse_kv_lines(text: str) -> Dict[str, int]:
    """Parse "key value" per line files (memory.stat, cpu.stat).

    Values that aren't simple integers are skipped (defensive).
    """
    out: Dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        key = parts[0]
        try:
            out[key] = int(parts[1])
        except ValueError:
            continue
    return out


def _sum_io_stat_v2(text: str) -> Dict[str, int]:
    """Sum io.stat per-device rows into aggregated counters.

    io.stat format (one line per device):
      8:0 rbytes=12345 wbytes=67890 rios=10 wios=20 dbytes=0 dios=0
    """
    totals = {"rbytes": 0, "wbytes": 0, "rios": 0, "wios": 0,
              "dbytes": 0, "dios": 0}
    for line in text.splitlines():
        for tok in line.split()[1:]:  # skip "major:minor"
            if "=" not in tok:
                continue
            k, _, v = tok.partition("=")
            if k in totals:
                try:
                    totals[k] += int(v)
                except ValueError:
                    continue
    return totals


def collect_v2(cgroup_root: str, target_path: str) -> Dict[str, int]:
    """Collect IO/MEM/CPU counters from cgroup v2 unified hierarchy."""
    # Normalize: target_path may start with "/", strip to join cleanly
    rel = target_path.lstrip("/")
    base = Path(cgroup_root) / rel if rel else Path(cgroup_root)

    out: Dict[str, int] = {f: 0 for f in IO_FIELDS + MEM_FIELDS + CPU_FIELDS}

    # IO
    io_text = _safe_read(base / "io.stat")
    io_totals = _sum_io_stat_v2(io_text)
    out["cgroup_io_rbytes"] = io_totals["rbytes"]
    out["cgroup_io_wbytes"] = io_totals["wbytes"]
    out["cgroup_io_rios"] = io_totals["rios"]
    out["cgroup_io_wios"] = io_totals["wios"]
    out["cgroup_io_dbytes"] = io_totals["dbytes"]
    out["cgroup_io_dios"] = io_totals["dios"]

    # MEM
    mem = _parse_kv_lines(_safe_read(base / "memory.stat"))
    out["cgroup_mem_anon"] = mem.get("anon", 0)
    out["cgroup_mem_file"] = mem.get("file", 0)
    out["cgroup_mem_kernel"] = mem.get("kernel", mem.get("kernel_stack", 0))
    out["cgroup_mem_slab"] = mem.get("slab", 0)
    out["cgroup_mem_sock"] = mem.get("sock", 0)
    # NOTE: cgroup v2 memory.stat key is "swap" (current swap in bytes),
    # NOT "swapcached" (which is swap-backed page cache, different metric).
    # See kernel Documentation/admin-guide/cgroup-v2.rst "memory.stat".
    out["cgroup_mem_swap"] = mem.get("swap", 0)

    # CPU
    cpu = _parse_kv_lines(_safe_read(base / "cpu.stat"))
    out["cgroup_cpu_usage_usec"] = cpu.get("usage_usec", 0)
    out["cgroup_cpu_user_usec"] = cpu.get("user_usec", 0)
    out["cgroup_cpu_system_usec"] = cpu.get("system_usec", 0)
    out["cgroup_cpu_nr_periods"] = cpu.get("nr_periods", 0)
    out["cgroup_cpu_nr_throttled"] = cpu.get("nr_throttled", 0)
    out["cgroup_cpu_throttled_usec"] = cpu.get("throttled_usec", 0)

    return out


# ---------------------------------------------------------------------------
# File parsers — cgroup v1
# ---------------------------------------------------------------------------

def _parse_blkio_v1(text: str) -> Dict[str, int]:
    """Parse blkio.throttle.io_service_bytes / blkio.throttle.io_serviced.

    Format (Total line is at the end):
      8:0 Read 12345
      8:0 Write 67890
      ...
      Total 80235
    We sum non-Total lines per op type.
    """
    totals = {"Read": 0, "Write": 0, "Async": 0, "Sync": 0, "Discard": 0}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        _dev, op, val = parts
        if op in totals:
            try:
                totals[op] += int(val)
            except ValueError:
                continue
    return totals


def collect_v1(host_paths: Dict[str, str], target_path: str) -> Dict[str, int]:
    """Collect IO/MEM/CPU from split cgroup v1 controllers."""
    rel = target_path.lstrip("/")
    out: Dict[str, int] = {f: 0 for f in IO_FIELDS + MEM_FIELDS + CPU_FIELDS}

    # IO via blkio controller
    blkio_root = host_paths["CGROUP_V1_BLKIO_PATH"]
    if blkio_root:
        blkio_base = Path(blkio_root) / rel if rel else Path(blkio_root)
        bytes_text = _safe_read(blkio_base / "blkio.throttle.io_service_bytes")
        ios_text = _safe_read(blkio_base / "blkio.throttle.io_serviced")
        b = _parse_blkio_v1(bytes_text)
        i = _parse_blkio_v1(ios_text)
        out["cgroup_io_rbytes"] = b["Read"]
        out["cgroup_io_wbytes"] = b["Write"]
        out["cgroup_io_rios"] = i["Read"]
        out["cgroup_io_wios"] = i["Write"]
        out["cgroup_io_dbytes"] = b["Discard"]
        out["cgroup_io_dios"] = i["Discard"]

    # MEM via memory controller
    mem_root = host_paths["CGROUP_V1_MEMORY_PATH"]
    if mem_root:
        mem_base = Path(mem_root) / rel if rel else Path(mem_root)
        mem = _parse_kv_lines(_safe_read(mem_base / "memory.stat"))
        # v1 keys differ from v2; map best-effort
        out["cgroup_mem_anon"] = mem.get("rss", mem.get("total_rss", 0))
        out["cgroup_mem_file"] = mem.get("cache", mem.get("total_cache", 0))
        out["cgroup_mem_kernel"] = mem.get("kernel_stack",
                                            mem.get("kmem", 0))
        out["cgroup_mem_slab"] = mem.get("slab", 0)
        out["cgroup_mem_sock"] = mem.get("sock", 0)
        out["cgroup_mem_swap"] = mem.get("swap", mem.get("total_swap", 0))

    # CPU via cpuacct + cpu controller
    cpu_root = host_paths["CGROUP_V1_CPU_PATH"]
    if cpu_root:
        cpu_base = Path(cpu_root) / rel if rel else Path(cpu_root)
        # usage_usec: cpuacct.usage is in ns → convert to usec
        usage_ns_text = _safe_read(cpu_base / "cpuacct.usage").strip()
        try:
            out["cgroup_cpu_usage_usec"] = int(usage_ns_text) // 1000
        except ValueError:
            pass
        # cpuacct.usage_user / usage_sys (newer kernels)
        for src, dst in (("cpuacct.usage_user", "cgroup_cpu_user_usec"),
                         ("cpuacct.usage_sys", "cgroup_cpu_system_usec")):
            t = _safe_read(cpu_base / src).strip()
            try:
                out[dst] = int(t) // 1000
            except ValueError:
                pass
        # cpu.stat (throttle data)
        cpu_stat = _parse_kv_lines(_safe_read(cpu_base / "cpu.stat"))
        out["cgroup_cpu_nr_periods"] = cpu_stat.get("nr_periods", 0)
        out["cgroup_cpu_nr_throttled"] = cpu_stat.get("nr_throttled", 0)
        out["cgroup_cpu_throttled_usec"] = cpu_stat.get("throttled_time", 0) // 1000

    return out


# ---------------------------------------------------------------------------
# Top-level collect dispatcher
# ---------------------------------------------------------------------------

def _try_k8s_kubelet_fallback(reason: str) -> Optional[Dict[str, object]]:
    """Mode E: K8s kubelet /stats/summary fallback.

    Only activates when:
      DEPLOYMENT_MODE=k8s              (env, set by deployment_mode_detector.sh)
      AND POD_NAME + POD_NAMESPACE     (env, set by Downward API in daemonset)
      AND NODE_NAME                    (env, set by Downward API)
      AND K8s API reachable            (kubelet_stats_client.fetch_node ok)

    Returns 19-field dict with cgroup_meta_source="k8s_fallback:{reason}" on
    success, or None to let caller emit the original {unmounted,unresolved}
    fallback. Failure is silent (debug log only) — never raises.

    IO fields stay at 0 (kubelet /stats/summary lacks cgroup io_stat).
    MEM + CPU are populated from kubelet rate counters.
    """
    if not os.environ.get("DEPLOYMENT_MODE", "").lower().startswith("k8s"):
        return None
    pod_name = os.environ.get("POD_NAME", "")
    pod_ns = os.environ.get("POD_NAMESPACE", "")
    node_name = os.environ.get("NODE_NAME", "")
    if not (pod_name and pod_ns and node_name):
        return None
    try:
        from kubelet_stats_client import KubeletStatsClient
    except ImportError:
        # Allow run from any cwd: add this script's dir to path
        sys.path.insert(0, str(Path(__file__).parent))
        try:
            from kubelet_stats_client import KubeletStatsClient
        except ImportError:
            return None
    try:
        client = KubeletStatsClient()
        pod = client.pod_on_node(node_name, pod_ns, pod_name)
        if pod is None:
            return None
        out: Dict[str, object] = {f: 0 for f in IO_FIELDS + MEM_FIELDS + CPU_FIELDS}
        # Map kubelet fields → cgroup_mem_*
        out["cgroup_mem_anon"] = int(getattr(pod, "mem_rss_bytes", 0) or 0)
        # working_set = anon + active file pages. We split crudely: file=ws-rss
        ws = int(getattr(pod, "mem_working_set_bytes", 0) or 0)
        rss = int(getattr(pod, "mem_rss_bytes", 0) or 0)
        out["cgroup_mem_file"] = max(0, ws - rss)
        # CPU: kubelet exposes nanocores (current rate) + cumulative core-nanosec
        out["cgroup_cpu_usage_usec"] = int(
            (getattr(pod, "cpu_usage_core_nanosec", 0) or 0) // 1000
        )
        out["cgroup_meta_source"] = f"k8s_fallback:{reason}"
        return out
    except Exception:
        return None


def collect() -> Dict[str, object]:
    """4-mode dispatcher. Always returns a dict with all 19 fields."""
    host_paths = get_host_paths()

    # Resolve cgroup version: prefer env, fall back to fs detection
    cg_ver = host_paths["CGROUP_VERSION"]
    cg_root = host_paths["CGROUP_ROOT"]
    if cg_ver in ("auto", "unknown", ""):
        cg_ver, cg_root = _detect_cgroup_version_fallback(host_paths["HOST_SYS"])
        host_paths["CGROUP_VERSION"] = cg_ver
        host_paths["CGROUP_ROOT"] = cg_root

    # Populate v1 sub-paths if cg_ver=="v1" (regardless of auto-detect or explicit).
    # Previously this block was nested inside the `auto` branch, so a user who
    # explicitly set CGROUP_VERSION=v1 with empty CGROUP_V1_*_PATH got all-zero
    # IO/MEM/CPU output. Now it runs unconditionally for v1.
    if cg_ver == "v1" and cg_root:
        for ctrl, key in (("blkio", "CGROUP_V1_BLKIO_PATH"),
                          ("memory", "CGROUP_V1_MEMORY_PATH")):
            if not host_paths[key]:
                host_paths[key] = f"{cg_root}/{ctrl}"
        if not host_paths["CGROUP_V1_CPU_PATH"]:
            cand1 = Path(f"{cg_root}/cpu,cpuacct")
            cand2 = Path(f"{cg_root}/cpu")
            host_paths["CGROUP_V1_CPU_PATH"] = (
                str(cand1) if cand1.is_dir() else str(cand2)
            )

    # Mode C: unmounted (try K8s Mode E fallback first)
    if cg_ver == "unknown" or not cg_root:
        e_result = _try_k8s_kubelet_fallback("unmounted")
        if e_result is not None:
            return e_result
        out: Dict[str, object] = {f: 0 for f in IO_FIELDS + MEM_FIELDS + CPU_FIELDS}
        out["cgroup_meta_source"] = "unmounted"
        return out

    # Resolve target cgroup path
    target = os.environ.get("TARGET_CGROUP", "")
    if not target:
        target = resolve_target_cgroup(host_paths["HOST_PROC"],
                                        os.environ.get("TARGET_PID"))

    # Mode D: target unresolvable → try Mode E, else 0/0/0 with explicit source
    if target is None:
        e_result = _try_k8s_kubelet_fallback("unresolved")
        if e_result is not None:
            return e_result
        out: Dict[str, object] = {f: 0 for f in IO_FIELDS + MEM_FIELDS + CPU_FIELDS}
        out["cgroup_meta_source"] = "unresolved"
        return out

    # Mode A or B
    if cg_ver == "v2":
        counters = collect_v2(cg_root, target)
        counters_out: Dict[str, object] = dict(counters)
        counters_out["cgroup_meta_source"] = "v2"
        return counters_out
    else:
        counters = collect_v1(host_paths, target)
        counters_out = dict(counters)
        counters_out["cgroup_meta_source"] = "v1"
        return counters_out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_header() -> None:
    print(",".join(ALL_FIELDS))


def print_data() -> None:
    row = collect()
    print(",".join(str(row[f]) for f in ALL_FIELDS))


def main() -> int:
    desc = (__doc__ or "cgroup_collector — collect cgroup v1/v2 metrics").split("\n")[1] if __doc__ else "cgroup_collector"
    ap = argparse.ArgumentParser(description=desc)
    grp = ap.add_mutually_exclusive_group(required=False)
    grp.add_argument("--header", action="store_true",
                     help="print CSV header (19 columns) and exit")
    grp.add_argument("--data", action="store_true",
                     help="print one CSV row of current counters (default)")
    grp.add_argument("--debug", action="store_true",
                     help="print key=value debug dump including resolved paths")
    args = ap.parse_args()

    if args.header:
        print_header()
        return 0
    if args.debug:
        paths = get_host_paths()
        target = os.environ.get("TARGET_CGROUP") or \
            resolve_target_cgroup(paths["HOST_PROC"], os.environ.get("TARGET_PID"))
        for k, v in paths.items():
            print(f"{k}={v}", file=sys.stderr)
        print(f"TARGET_CGROUP_RESOLVED={target}", file=sys.stderr)
        print_data()
        return 0
    # default → --data
    print_data()
    return 0


if __name__ == "__main__":
    sys.exit(main())
