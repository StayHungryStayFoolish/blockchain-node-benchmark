#!/usr/bin/env python3
"""mini_monitor.py — 1Hz CPU+MEM sampler for proxy + mock_rpc processes.

录-放 PoC 专用简化版 monitor。生产用 monitoring/unified_monitor.sh。
本文件只采 CPU% + RSS,1Hz,写 CSV,不依赖 repo 其它脚本。

设计依据: ADR-0001 (monitor 独立采集) + ADR-0004 (proxy 自报 vs /proc 双采互校)

用法:
    python3 mini_monitor.py \\
        --proxy-pid 12345 \\
        --node-pid 67890 \\
        --out /tmp/monitor.csv \\
        --duration 60

CSV schema:
    ts_unix,proxy_cpu_pct,proxy_rss_kb,node_cpu_pct,node_rss_kb

CPU% = ps -o %cpu (与 top 一致, 1 core = 100%)
"""
import argparse
import csv
import subprocess
import sys
import time


def sample(pid: int) -> tuple[float, int]:
    """Return (cpu_pct, rss_kb) for pid, or (-1, -1) if process gone."""
    try:
        out = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "%cpu=,rss="],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        if not out:
            return -1.0, -1
        parts = out.split()
        return float(parts[0]), int(parts[1])
    except (subprocess.CalledProcessError, ValueError, IndexError):
        return -1.0, -1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy-pid", type=int, required=True)
    ap.add_argument("--node-pid", type=int, required=True, help="mock_rpc pid")
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--duration", type=int, default=60)
    args = ap.parse_args()

    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts_unix", "proxy_cpu_pct", "proxy_rss_kb", "node_cpu_pct", "node_rss_kb"])
        f.flush()

        deadline = time.time() + args.duration
        n = 0
        while time.time() < deadline:
            ts = time.time()
            p_cpu, p_rss = sample(args.proxy_pid)
            n_cpu, n_rss = sample(args.node_pid)
            w.writerow([f"{ts:.3f}", p_cpu, p_rss, n_cpu, n_rss])
            f.flush()
            n += 1
            # Sleep to next 1s boundary
            sleep = 1.0 - (time.time() - ts)
            if sleep > 0:
                time.sleep(sleep)

        print(f"mini_monitor: wrote {n} samples to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
