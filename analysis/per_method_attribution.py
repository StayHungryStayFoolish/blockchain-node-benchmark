"""
Per-method resource attribution module.

Inputs:
- proxy sink CSV. Current schema:
  timestamp_ns, method_name, protocol, request_id, batch_idx, status_code,
  transport_success, rpc_success, rpc_error_code, rpc_error_message,
  latency_ms, upstream, client_addr
  Legacy 9-column proxy CSVs are still accepted.
- unified monitor CSV (existing per-second rows)

Outputs:
- per_method_qps_<chain>.csv          per-method per-second QPS, error rate, and p50/p90/p99 latency
- per_method_resource_<chain>.csv     per-method per-second attributed CPU%/MEM% weighted by method counts

Attribution formula:
    method_weight(method, t)  = count(method in [t, t+1)) / total_count(in [t, t+1))
    method_cpu(method, t)     = total_cpu(t) * method_weight(method, t)
    method_mem(method, t)     = total_mem_mb(t) * method_weight(method, t)

Time-window alignment: left-closed, right-open [t, t+1), matching per-second monitor samples.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence


@dataclass
class ProxyRecord:
    """One proxy sink record."""
    timestamp_ns: int
    method_name: str
    protocol: str
    request_id: str
    batch_idx: int
    status_code: int
    latency_ms: int
    upstream: str
    client_addr: str
    transport_success: bool = True
    rpc_success: bool = True
    rpc_error_code: str = ""
    rpc_error_message: str = ""


@dataclass
class MonitorRecord:
    """One monitor CSV record with only fields needed for attribution."""
    timestamp_s: int        # epoch seconds
    cpu_pct: float          # system CPU% 0-100
    mem_mb: float           # used memory MB


@dataclass
class PerMethodQpsRow:
    timestamp_s: int
    method_name: str
    qps: int                # request count for this method in this second (= QPS for a 1s window)
    error_count: int        # rpc_success=false count
    p50_ms: float
    p90_ms: float
    p99_ms: float


@dataclass
class PerMethodResourceRow:
    timestamp_s: int
    method_name: str
    weight: float           # 0-1
    cpu_pct: float          # attributed CPU% = total_cpu * weight
    mem_mb: float           # attributed memory MB = total_mem * weight


def read_proxy_csv(path: str | Path) -> Iterator[ProxyRecord]:
    """Stream-read proxy sink CSV.

    Skip method_name == '__unmatched__'. Extractor misses should not be
    attributed to any workload method.
    """
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("method_name") == "__unmatched__":
                continue
            status_code = int(row["status_code"])
            transport_success = _parse_bool(
                row.get("transport_success"),
                default=(200 <= status_code < 400),
            )
            rpc_success = _parse_bool(
                row.get("rpc_success"),
                default=transport_success,
            )
            yield ProxyRecord(
                timestamp_ns=int(row["timestamp_ns"]),
                method_name=row["method_name"],
                protocol=row.get("protocol", ""),
                request_id=row.get("request_id", ""),
                batch_idx=int(row.get("batch_idx", "0") or "0"),
                status_code=status_code,
                transport_success=transport_success,
                rpc_success=rpc_success,
                rpc_error_code=row.get("rpc_error_code", ""),
                rpc_error_message=row.get("rpc_error_message", ""),
                latency_ms=int(row["latency_ms"]),
                upstream=row.get("upstream", ""),
                client_addr=row.get("client_addr", ""),
            )


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def read_monitor_csv(
    path: str | Path,
    timestamp_col: str = "timestamp",
    cpu_col: str = "cpu_usage",
    mem_col: str = "mem_used_mb",
) -> Iterator[MonitorRecord]:
    """Read unified monitor CSV.

    Column names are configurable because collectors use different schemas.
    The timestamp column accepts two auto-detected formats:
      1. epoch int/float, with unit inferred from magnitude (s/ms/us/ns)
      2. ISO/datetime strings, such as '2026-05-31 19:19:50' or ISO8601.
         unified_monitor.sh emits local timestamp strings, which are parsed as
         local-time epoch seconds to align with the proxy sink from the same run.
    """
    import datetime as _dt

    def _parse_ts_to_epoch_s(ts_raw: str) -> int:
        ts_raw = (ts_raw or "").strip()
        # Prefer numeric epoch values and infer seconds/ms/us/ns by magnitude.
        try:
            ts_int = int(float(ts_raw))
        except (ValueError, TypeError):
            ts_int = None
        if ts_int is not None:
            if ts_int > 10**17:    # ns
                return ts_int // 1_000_000_000
            elif ts_int > 10**14:  # us
                return ts_int // 1_000_000
            elif ts_int > 10**11:  # ms
                return ts_int // 1000
            else:                  # seconds
                return ts_int
        # String datetime: unified_monitor uses '%Y-%m-%d %H:%M:%S';
        # also accept ISO8601 strings with a 'T' separator.
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = _dt.datetime.strptime(ts_raw, fmt)
                return int(dt.timestamp())  # local timezone -> epoch seconds
            except ValueError:
                continue
        # Finally try fromisoformat for fractional seconds or timezone offsets.
        try:
            dt = _dt.datetime.fromisoformat(ts_raw)
            return int(dt.timestamp())
        except ValueError:
            raise ValueError(
                f"read_monitor_csv: unable to parse timestamp {ts_raw!r}; "
                f"expected numeric epoch or a supported datetime string"
            )

    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_s = _parse_ts_to_epoch_s(row[timestamp_col])
            yield MonitorRecord(
                timestamp_s=ts_s,
                cpu_pct=float(row.get(cpu_col, 0) or 0),
                mem_mb=float(row.get(mem_col, 0) or 0),
            )


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    """Compute percentile from a sorted list with linear interpolation."""
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
    """Group by (method, timestamp_s) and compute QPS, error rate, p50, p90, and p99.

    Returns rows sorted by (timestamp_s, method_name).
    """
    # bucket: (ts_s, method) -> list[latency_ms]
    latencies: dict[tuple[int, str], list[int]] = defaultdict(list)
    errors: dict[tuple[int, str], int] = defaultdict(int)

    for r in proxy_records:
        ts_s = r.timestamp_ns // 1_000_000_000
        key = (ts_s, r.method_name)
        latencies[key].append(r.latency_ms)
        if not r.rpc_success:
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
            p90_ms=_percentile(lats_sorted, 0.9),
            p99_ms=_percentile(lats_sorted, 0.99),
        ))
    rows.sort(key=lambda x: (x.timestamp_s, x.method_name))
    return rows


def filter_proxy_records_by_methods(
    proxy_records: Iterable[ProxyRecord],
    allowed_methods: Iterable[str] | None,
) -> list[ProxyRecord]:
    """Keep only workload methods declared by the chain template.

    Proxy CSV also contains framework probes, such as block-height/sync-health
    RPCs. Per-method attribution is intended for the user-selected single or
    mixed workload, so monitor probes must not be charged to business methods.
    If allowed_methods is None/empty, return all records to preserve legacy
    behavior for old reports that lack chain template context.
    """
    allowed = {m for m in (allowed_methods or []) if m}
    records = list(proxy_records)
    if not allowed:
        return records
    return [r for r in records if r.method_name in allowed]


def compute_per_method_resource(
    proxy_records: Iterable[ProxyRecord],
    monitor_records: Iterable[MonitorRecord],
) -> list[PerMethodResourceRow]:
    """Attribute CPU%/memory by per-second method_count / total_count weight.

    proxy_records and monitor_records are consumed once. Seconds without monitor
    data are skipped to avoid treating missing data as real zero load.
    """
    # Step 1: per-second method counts.
    method_count: dict[tuple[int, str], int] = defaultdict(int)
    total_count: dict[int, int] = defaultdict(int)
    for r in proxy_records:
        ts_s = r.timestamp_ns // 1_000_000_000
        method_count[(ts_s, r.method_name)] += 1
        total_count[ts_s] += 1

    # Step 2: per-second monitor lookup.
    monitor_by_ts: dict[int, MonitorRecord] = {m.timestamp_s: m for m in monitor_records}

    # Step 3: attribution.
    rows: list[PerMethodResourceRow] = []
    for (ts_s, method), cnt in method_count.items():
        m = monitor_by_ts.get(ts_s)
        if m is None:
            continue  # no monitor data for this second
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
        w.writerow(["timestamp_s", "method_name", "qps", "error_count", "p50_ms", "p90_ms", "p99_ms"])
        for r in rows:
            w.writerow([r.timestamp_s, r.method_name, r.qps, r.error_count,
                       f"{r.p50_ms:.3f}", f"{r.p90_ms:.3f}", f"{r.p99_ms:.3f}"])


def write_resource_csv(rows: list[PerMethodResourceRow], path: str | Path) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_s", "method_name", "weight", "cpu_pct", "mem_mb"])
        for r in rows:
            w.writerow([r.timestamp_s, r.method_name, f"{r.weight:.6f}",
                       f"{r.cpu_pct:.3f}", f"{r.mem_mb:.3f}"])
