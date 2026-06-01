#!/usr/bin/env python3
"""offline_join.py — proxy CSV + monitor CSV -> per-method resource attribution.

ADR-0001 选项 C 的离线 join 实现 (PoC 版):
  1. 读 proxy CSV (ts_ns, method, status, latency_ns)
  2. 读 monitor CSV (ts_unix, proxy_cpu_pct, proxy_rss_kb, node_cpu_pct, node_rss_kb)
  3. 按 1 秒时间窗对齐, 计算每秒 method 调用分布
  4. 用 weight 表 (cheap=1, mid=10, expensive=100) 把节点 CPU/MEM 分摊给各 method
  5. 输出 per-method 报表

WEIGHT 表 (ADR-0001 1/10/100 三档, 与 mock_rpc_v2 sleep 三档对应):
    getSlot=1, getBalance=1, getLatestBlockhash=10, getBlock=100, getTransaction=100

注意: 这是 PoC 版, 不是生产级 -- weight 是猜的, 真精度待真节点数据迭代.
"""
import argparse
import csv
import sys
from collections import defaultdict

# ADR-0001 weight 三档 (与 mock_rpc_v2 sleep 三档对应)
WEIGHTS = {
    "getSlot": 1.0,
    "getBalance": 1.0,
    "getLatestBlockhash": 10.0,
    "getBlock": 100.0,
    "getTransaction": 100.0,
}


def load_proxy(path: str):
    """Return list of (ts_unix_float, method, status, latency_ns)."""
    rows = []
    with open(path) as f:
        r = csv.DictReader(f)
        for row in r:
            ts_ns = int(row["ts_ns"])
            rows.append((ts_ns / 1e9, row["method"], int(row["status"]), int(row["latency_ns"])))
    return rows


def load_monitor(path: str):
    """Return list of (ts_unix, proxy_cpu, proxy_rss_kb, node_cpu, node_rss_kb)."""
    rows = []
    with open(path) as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append((
                float(row["ts_unix"]),
                float(row["proxy_cpu_pct"]),
                int(row["proxy_rss_kb"]),
                float(row["node_cpu_pct"]),
                int(row["node_rss_kb"]),
            ))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy-csv", required=True)
    ap.add_argument("--monitor-csv", required=True)
    ap.add_argument("--window-sec", type=float, default=1.0)
    args = ap.parse_args()

    proxy_rows = load_proxy(args.proxy_csv)
    monitor_rows = load_monitor(args.monitor_csv)

    if not proxy_rows or not monitor_rows:
        print("ERR: empty input", file=sys.stderr)
        return 1

    # 1) 按 window_sec 把 proxy 请求 bucket 化
    # bucket key = floor(ts / window_sec)
    buckets_method_count = defaultdict(lambda: defaultdict(int))  # bucket -> {method: count}
    for ts, method, status, lat_ns in proxy_rows:
        b = int(ts / args.window_sec)
        buckets_method_count[b][method] += 1

    # 2) monitor 也 bucket 化, 取每 bucket 的平均
    buckets_resource = defaultdict(lambda: {"node_cpu": [], "node_rss": [], "proxy_cpu": [], "proxy_rss": []})
    for ts, p_cpu, p_rss, n_cpu, n_rss in monitor_rows:
        b = int(ts / args.window_sec)
        if n_cpu >= 0:
            buckets_resource[b]["node_cpu"].append(n_cpu)
            buckets_resource[b]["node_rss"].append(n_rss)
        if p_cpu >= 0:
            buckets_resource[b]["proxy_cpu"].append(p_cpu)
            buckets_resource[b]["proxy_rss"].append(p_rss)

    # 3) 对每个 bucket 按 weight 分摊节点资源
    per_method_total = defaultdict(lambda: {"calls": 0, "attr_cpu_sec_pct": 0.0, "attr_rss_kb_sec": 0.0})

    matched_buckets = 0
    for b, method_counts in sorted(buckets_method_count.items()):
        res = buckets_resource.get(b)
        if not res or not res["node_cpu"]:
            continue
        matched_buckets += 1
        avg_node_cpu = sum(res["node_cpu"]) / len(res["node_cpu"])
        avg_node_rss = sum(res["node_rss"]) / len(res["node_rss"])

        # weighted total = sum(count * weight)
        weighted_total = sum(method_counts[m] * WEIGHTS.get(m, 1.0) for m in method_counts)
        if weighted_total == 0:
            continue

        for m, c in method_counts.items():
            w = WEIGHTS.get(m, 1.0)
            share = (c * w) / weighted_total
            per_method_total[m]["calls"] += c
            per_method_total[m]["attr_cpu_sec_pct"] += avg_node_cpu * share  # CPU% * 1s = CPU-sec*100
            per_method_total[m]["attr_rss_kb_sec"] += avg_node_rss * share

    # 4) 输出
    print(f"=== Per-method resource attribution (PoC) ===")
    print(f"proxy_rows={len(proxy_rows)} monitor_rows={len(monitor_rows)} matched_buckets={matched_buckets}")
    print(f"window={args.window_sec}s weights={WEIGHTS}")
    print()
    print(f"{'method':<22} {'calls':>10} {'avg_qps':>10} {'cpu_sec':>12} {'cpu_per_kreq':>14} {'rss_avg_mb':>12}")

    if matched_buckets == 0:
        print("WARN: 0 matched buckets (proxy 和 monitor 时间窗未对齐?)")
        return 1

    total_dur = matched_buckets * args.window_sec
    for m in sorted(per_method_total.keys(), key=lambda x: -per_method_total[x]["calls"]):
        d = per_method_total[m]
        calls = d["calls"]
        # attr_cpu_sec_pct 是 sum(CPU% * 1s), 除以 100 = CPU-sec
        cpu_sec = d["attr_cpu_sec_pct"] / 100.0
        cpu_per_kreq = (cpu_sec / calls * 1000) if calls > 0 else 0
        # attr_rss_kb_sec 是 sum(RSS_KB * 1s), 除以总秒数 = avg RSS (不是真的分摊, RSS 是 process 共享)
        rss_avg_mb = (d["attr_rss_kb_sec"] / matched_buckets / 1024) if matched_buckets > 0 else 0
        avg_qps = calls / total_dur
        print(f"{m:<22} {calls:>10} {avg_qps:>10.1f} {cpu_sec:>12.2f} {cpu_per_kreq:>14.4f} {rss_avg_mb:>12.2f}")

    # totals
    total_calls = sum(d["calls"] for d in per_method_total.values())
    total_cpu = sum(d["attr_cpu_sec_pct"] for d in per_method_total.values()) / 100.0
    print(f"{'TOTAL':<22} {total_calls:>10} {total_calls/total_dur:>10.1f} {total_cpu:>12.2f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
