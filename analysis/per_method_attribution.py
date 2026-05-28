"""
Per-method 资源归因模块 (S4.2 W3.1).

输入:
- proxy sink CSV (W2 输出, 9 列: timestamp_ns, method_name, protocol,
  request_id, batch_idx, status_code, latency_ms, upstream, client_addr)
- unified monitor CSV (现有, 每秒 1 行)

输出:
- per_method_qps_<chain>.csv          每秒每 method 的 QPS / 错误率 / p50/p99 延迟
- per_method_resource_<chain>.csv     每秒每 method 的归因 CPU%/MEM% (按 method count 权重)

归因公式 (Q4-7 已锁):
    method_weight(method, t)  = count(method in [t, t+1)) / total_count(in [t, t+1))
    method_cpu(method, t)     = total_cpu(t) * method_weight(method, t)
    method_mem(method, t)     = total_mem_mb(t) * method_weight(method, t)

时间窗对齐 (W3-1 自决): 左闭右开 [t, t+1) — 与 monitor.csv 每秒采样自然对齐。
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence


@dataclass
class ProxyRecord:
    """一条 proxy sink 记录 (对应 W2 sink.Record)."""
    timestamp_ns: int
    method_name: str
    protocol: str
    request_id: str
    batch_idx: int
    status_code: int
    latency_ms: int
    upstream: str
    client_addr: str


@dataclass
class MonitorRecord:
    """一条 monitor CSV 记录 — 只取归因需要的字段."""
    timestamp_s: int        # epoch seconds
    cpu_pct: float          # 系统 CPU% 0-100
    mem_mb: float           # 已用内存 MB


@dataclass
class PerMethodQpsRow:
    timestamp_s: int
    method_name: str
    qps: int                # 该秒该 method 的请求数 (= QPS, 因窗 1s)
    error_count: int        # status >= 400 的数量
    p50_ms: float
    p99_ms: float


@dataclass
class PerMethodResourceRow:
    timestamp_s: int
    method_name: str
    weight: float           # 0-1
    cpu_pct: float          # 归因 CPU% = total_cpu * weight
    mem_mb: float           # 归因 mem MB = total_mem * weight


def read_proxy_csv(path: str | Path) -> Iterator[ProxyRecord]:
    """流式读 W2 sink CSV.

    跳过 method_name == '__unmatched__' 的记录 (extractor 没匹配上, 不应归因到任何 method).
    """
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("method_name") == "__unmatched__":
                continue
            yield ProxyRecord(
                timestamp_ns=int(row["timestamp_ns"]),
                method_name=row["method_name"],
                protocol=row.get("protocol", ""),
                request_id=row.get("request_id", ""),
                batch_idx=int(row.get("batch_idx", "0") or "0"),
                status_code=int(row["status_code"]),
                latency_ms=int(row["latency_ms"]),
                upstream=row.get("upstream", ""),
                client_addr=row.get("client_addr", ""),
            )


def read_monitor_csv(
    path: str | Path,
    timestamp_col: str = "timestamp",
    cpu_col: str = "cpu_usage",
    mem_col: str = "mem_used_mb",
) -> Iterator[MonitorRecord]:
    """读 unified monitor CSV.

    列名可配 (项目内不同 collector 列名各异). 默认按 cgroup_collector 输出.
    timestamp 列接受: epoch int/float, 或 ISO 字符串 (留 future, 当前只支持 epoch).
    """
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_raw = row[timestamp_col]
            # epoch seconds or nanoseconds — 长度判断
            ts_int = int(float(ts_raw))
            # 长度判断 epoch 单位:
            # seconds  ~1e9 (10 digits, year 2001-2286)
            # millis   ~1e12 (13 digits)
            # micros   ~1e15 (16 digits)
            # nanos    ~1e18 (19 digits)
            if ts_int > 10**17:    # ns
                ts_s = ts_int // 1_000_000_000
            elif ts_int > 10**14:  # us
                ts_s = ts_int // 1_000_000
            elif ts_int > 10**11:  # ms
                ts_s = ts_int // 1000
            else:                  # seconds
                ts_s = ts_int
            yield MonitorRecord(
                timestamp_s=ts_s,
                cpu_pct=float(row.get(cpu_col, 0) or 0),
                mem_mb=float(row.get(mem_col, 0) or 0),
            )


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    """从已排序列表算 percentile (线性插值)."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = pct * (len(sorted_values) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = idx - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def compute_per_method_qps(
    proxy_records: Iterable[ProxyRecord],
) -> list[PerMethodQpsRow]:
    """秒级 group_by (method, timestamp_s) 算 QPS + 错误率 + p50/p99 延迟.

    返回按 (timestamp_s, method_name) 字典序排序的列表.
    """
    # bucket: (ts_s, method) -> list[latency_ms]
    latencies: dict[tuple[int, str], list[int]] = defaultdict(list)
    errors: dict[tuple[int, str], int] = defaultdict(int)

    for r in proxy_records:
        ts_s = r.timestamp_ns // 1_000_000_000
        key = (ts_s, r.method_name)
        latencies[key].append(r.latency_ms)
        if r.status_code >= 400:
            errors[key] += 1

    rows: list[PerMethodQpsRow] = []
    for key, lats in latencies.items():
        ts_s, method = key
        lats_sorted = sorted(lats)
        rows.append(PerMethodQpsRow(
            timestamp_s=ts_s,
            method_name=method,
            qps=len(lats),
            error_count=errors.get(key, 0),
            p50_ms=_percentile(lats_sorted, 0.5),
            p99_ms=_percentile(lats_sorted, 0.99),
        ))
    rows.sort(key=lambda x: (x.timestamp_s, x.method_name))
    return rows


def compute_per_method_resource(
    proxy_records: Iterable[ProxyRecord],
    monitor_records: Iterable[MonitorRecord],
) -> list[PerMethodResourceRow]:
    """按秒级 weight = method_count / total_count 归因 CPU%/MEM 到 method.

    proxy_records 和 monitor_records 都被消费一次 (Iterator 不可重用).
    缺失监控数据的秒不出归因行 (避免误把 0 当真实零负载).
    """
    # 第 1 步: 秒级 method count
    method_count: dict[tuple[int, str], int] = defaultdict(int)
    total_count: dict[int, int] = defaultdict(int)
    for r in proxy_records:
        ts_s = r.timestamp_ns // 1_000_000_000
        method_count[(ts_s, r.method_name)] += 1
        total_count[ts_s] += 1

    # 第 2 步: 秒级 monitor lookup
    monitor_by_ts: dict[int, MonitorRecord] = {m.timestamp_s: m for m in monitor_records}

    # 第 3 步: 归因
    rows: list[PerMethodResourceRow] = []
    for (ts_s, method), cnt in method_count.items():
        m = monitor_by_ts.get(ts_s)
        if m is None:
            continue  # 该秒无监控数据, 跳过
        total = total_count[ts_s]
        if total == 0:
            continue
        weight = cnt / total
        rows.append(PerMethodResourceRow(
            timestamp_s=ts_s,
            method_name=method,
            weight=weight,
            cpu_pct=m.cpu_pct * weight,
            mem_mb=m.mem_mb * weight,
        ))
    rows.sort(key=lambda x: (x.timestamp_s, x.method_name))
    return rows


def write_qps_csv(rows: list[PerMethodQpsRow], path: str | Path) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_s", "method_name", "qps", "error_count", "p50_ms", "p99_ms"])
        for r in rows:
            w.writerow([r.timestamp_s, r.method_name, r.qps, r.error_count,
                       f"{r.p50_ms:.3f}", f"{r.p99_ms:.3f}"])


def write_resource_csv(rows: list[PerMethodResourceRow], path: str | Path) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_s", "method_name", "weight", "cpu_pct", "mem_mb"])
        for r in rows:
            w.writerow([r.timestamp_s, r.method_name, f"{r.weight:.6f}",
                       f"{r.cpu_pct:.3f}", f"{r.mem_mb:.3f}"])
