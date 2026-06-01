#!/usr/bin/env python3
"""Degraded-mode HTML report generator.

Used when performance.csv is missing or empty so that the framework can still
emit a minimal-but-useful HTML report from vegeta JSON results + block-height
CSV data (if present).

Pure stdlib (json, csv, os, sys, glob, datetime, xml.etree.ElementTree, html).
No third-party dependencies (matplotlib / jinja2 / pandas all forbidden).

Usage:
    python3 degraded_report.py <vegeta_results_dir> <logs_dir> <reports_dir>
"""
from __future__ import annotations

import csv
import glob
import html as html_escape
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Vegeta JSON parsing
# ---------------------------------------------------------------------------

QPS_RE = re.compile(r"vegeta_(\d+)qps_")


def _ns_to_ms(value: Any) -> float:
    try:
        return float(value) / 1_000_000.0
    except (TypeError, ValueError):
        return 0.0


def parse_vegeta_file(path: str) -> dict:
    """Parse a single vegeta JSON file (either summary blob or stream of attacks).

    Vegeta supports two encodings; we try summary first (vegeta report -type=json)
    and fall back to streaming attack records.
    """
    qps_match = QPS_RE.search(os.path.basename(path))
    qps = int(qps_match.group(1)) if qps_match else 0

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read().strip()

    if not text:
        return _empty_record(qps, path)

    # Try summary JSON first.
    try:
        blob = json.loads(text)
        if isinstance(blob, dict) and "latencies" in blob:
            lat = blob.get("latencies", {}) or {}
            return {
                "qps": qps,
                "file": os.path.basename(path),
                "requests": int(blob.get("requests", 0) or 0),
                "success_rate": float(blob.get("success", 0.0) or 0.0) * 100.0,
                "mean_ms": _ns_to_ms(lat.get("mean")),
                "p50_ms": _ns_to_ms(lat.get("50th")),
                "p99_ms": _ns_to_ms(lat.get("99th")),
                "max_ms": _ns_to_ms(lat.get("max")),
                "status_codes": dict(blob.get("status_codes", {}) or {}),
            }
    except json.JSONDecodeError:
        pass

    # Fall back to streamed attack records (one JSON per line).
    latencies_ns: list[int] = []
    status_counts: dict[str, int] = {}
    total = 0
    success = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        code = str(rec.get("code", "0"))
        status_counts[code] = status_counts.get(code, 0) + 1
        if 200 <= int(code or 0) < 400:
            success += 1
        lat = rec.get("latency")
        if isinstance(lat, (int, float)):
            latencies_ns.append(int(lat))

    if total == 0:
        return _empty_record(qps, path)

    latencies_ns.sort()
    return {
        "qps": qps,
        "file": os.path.basename(path),
        "requests": total,
        "success_rate": (success / total) * 100.0,
        "mean_ms": _ns_to_ms(sum(latencies_ns) / len(latencies_ns)) if latencies_ns else 0.0,
        "p50_ms": _ns_to_ms(_pct(latencies_ns, 50)),
        "p99_ms": _ns_to_ms(_pct(latencies_ns, 99)),
        "max_ms": _ns_to_ms(latencies_ns[-1]) if latencies_ns else 0.0,
        "status_codes": status_counts,
    }


def _pct(sorted_values: list[int], p: float) -> int:
    if not sorted_values:
        return 0
    idx = int(round((p / 100.0) * (len(sorted_values) - 1)))
    return sorted_values[idx]


def _empty_record(qps: int, path: str) -> dict:
    return {
        "qps": qps,
        "file": os.path.basename(path),
        "requests": 0,
        "success_rate": 0.0,
        "mean_ms": 0.0,
        "p50_ms": 0.0,
        "p99_ms": 0.0,
        "max_ms": 0.0,
        "status_codes": {},
    }


def collect_vegeta(results_dir: str) -> list[dict]:
    if not results_dir or not os.path.isdir(results_dir):
        return []
    files = sorted(glob.glob(os.path.join(results_dir, "vegeta_*qps_*.json")))
    rows = [parse_vegeta_file(p) for p in files]
    rows.sort(key=lambda r: r["qps"])
    return rows


# ---------------------------------------------------------------------------
# Block height parsing
# ---------------------------------------------------------------------------

def collect_block_heights(logs_dir: str) -> list[tuple[str, float]]:
    """Return [(timestamp, local_block_height), ...] from any source we can find."""
    points: list[tuple[str, float]] = []
    if not logs_dir or not os.path.isdir(logs_dir):
        return points

    # Pattern 1: dedicated block_height_*.csv
    candidates = sorted(glob.glob(os.path.join(logs_dir, "block_height_*.csv")))
    # Pattern 2: as a fallback, try performance_latest.csv even if it's tiny;
    # it may still have a couple of block_height_diff rows.
    perf = os.path.join(logs_dir, "performance_latest.csv")
    if os.path.isfile(perf):
        candidates.append(perf)

    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    continue
                ts_field = _first_present(reader.fieldnames, ["timestamp", "time", "ts"])
                height_field = _first_present(
                    reader.fieldnames,
                    ["local_block_height", "block_height", "height"],
                )
                if not ts_field or not height_field:
                    continue
                for row in reader:
                    try:
                        h = float(row.get(height_field) or 0)
                    except ValueError:
                        continue
                    if h <= 0:
                        continue
                    points.append((row.get(ts_field, ""), h))
        except OSError:
            continue

    return points


def _first_present(fields, wanted) -> str | None:
    lower_map = {f.lower(): f for f in fields}
    for w in wanted:
        if w in lower_map:
            return lower_map[w]
    return None


# ---------------------------------------------------------------------------
# Inline SVG line chart (stdlib only via ElementTree)
# ---------------------------------------------------------------------------

def render_block_height_svg(points: list[tuple[str, float]],
                            width: int = 720, height: int = 240) -> str:
    svg = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "viewBox": f"0 0 {width} {height}",
        "width": str(width),
        "height": str(height),
        "style": "background:#fafafa;border:1px solid #ddd;",
    })

    margin = 40
    if len(points) < 2:
        text = ET.SubElement(svg, "text", {
            "x": str(width // 2), "y": str(height // 2),
            "text-anchor": "middle", "fill": "#888", "font-size": "14",
        })
        text.text = "Block-height data unavailable"
        return ET.tostring(svg, encoding="unicode")

    ys = [p[1] for p in points]
    y_min, y_max = min(ys), max(ys)
    if y_max == y_min:
        y_max = y_min + 1
    n = len(points)
    inner_w = width - 2 * margin
    inner_h = height - 2 * margin

    coords = []
    for i, (_ts, y) in enumerate(points):
        x = margin + (inner_w * i / (n - 1))
        y_pix = margin + inner_h - (inner_h * (y - y_min) / (y_max - y_min))
        coords.append(f"{x:.1f},{y_pix:.1f}")

    # Axes.
    ET.SubElement(svg, "line", {
        "x1": str(margin), "y1": str(margin),
        "x2": str(margin), "y2": str(height - margin),
        "stroke": "#666", "stroke-width": "1",
    })
    ET.SubElement(svg, "line", {
        "x1": str(margin), "y1": str(height - margin),
        "x2": str(width - margin), "y2": str(height - margin),
        "stroke": "#666", "stroke-width": "1",
    })
    # Polyline.
    ET.SubElement(svg, "polyline", {
        "fill": "none", "stroke": "#1976d2",
        "stroke-width": "2", "points": " ".join(coords),
    })
    # Y labels.
    for tag, val in (("y_max", y_max), ("y_min", y_min)):
        y_pos = margin if tag == "y_max" else height - margin
        t = ET.SubElement(svg, "text", {
            "x": "4", "y": str(int(y_pos) + 4),
            "fill": "#444", "font-size": "11",
        })
        t.text = f"{val:.0f}"
    # Title.
    title = ET.SubElement(svg, "text", {
        "x": str(width // 2), "y": "16",
        "text-anchor": "middle", "fill": "#333", "font-size": "13",
    })
    title.text = f"Local block height ({n} samples)"

    return ET.tostring(svg, encoding="unicode")


# ---------------------------------------------------------------------------
# HTML assembly
# ---------------------------------------------------------------------------

MISSING_CAPABILITIES = [
    "Disk I/O analysis (iostat-derived metrics)",
    "System resource trends (CPU / memory / network from sar/mpstat)",
    "Per-method system-resource attribution charts",
    "Disk bottleneck detector correlation",
    "Bottleneck root-cause ML analysis",
]


def _fmt(v: float) -> str:
    return f"{v:.2f}" if isinstance(v, (int, float)) else html_escape.escape(str(v))


def build_html(vegeta_rows: list[dict], height_points: list[tuple[str, float]]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # QPS table.
    if vegeta_rows:
        rows_html = []
        for r in vegeta_rows:
            codes = ", ".join(f"{html_escape.escape(k)}:{v}"
                              for k, v in sorted(r["status_codes"].items()))
            rows_html.append(
                "<tr>"
                f"<td>{r['qps']}</td>"
                f"<td>{r['requests']}</td>"
                f"<td>{_fmt(r['success_rate'])}%</td>"
                f"<td>{_fmt(r['mean_ms'])}</td>"
                f"<td>{_fmt(r['p50_ms'])}</td>"
                f"<td>{_fmt(r['p99_ms'])}</td>"
                f"<td>{_fmt(r['max_ms'])}</td>"
                f"<td>{codes or '-'}</td>"
                "</tr>"
            )
        qps_table = (
            "<table class='qps'><thead><tr>"
            "<th>QPS</th><th>Requests</th><th>Success</th>"
            "<th>Mean (ms)</th><th>p50 (ms)</th><th>p99 (ms)</th>"
            "<th>Max (ms)</th><th>Status codes</th>"
            "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table>"
        )
    else:
        qps_table = "<p class='warn'>No vegeta JSON results found.</p>"

    svg = render_block_height_svg(height_points)
    missing = "".join(f"<li>{html_escape.escape(c)}</li>" for c in MISSING_CAPABILITIES)

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Blockchain Node Benchmark — DEGRADED MODE Report</title>
<style>
body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif;
        margin: 24px; color: #222; }}
.banner {{ background:#fff4e5; border:2px solid #ff9800; padding:16px 20px;
          border-radius:6px; margin-bottom:20px; font-size:16px; }}
.banner h1 {{ margin:0 0 6px; color:#b25600; font-size:20px; }}
h2 {{ border-bottom:1px solid #ddd; padding-bottom:4px; }}
table.qps {{ border-collapse:collapse; width:100%; font-size:13px; }}
table.qps th, table.qps td {{ border:1px solid #ccc; padding:6px 8px;
                              text-align:right; }}
table.qps th {{ background:#f0f0f0; }}
table.qps td:last-child, table.qps th:last-child {{ text-align:left; }}
.warn {{ color:#b25600; font-style:italic; }}
ul.missing li {{ margin:4px 0; }}
footer {{ margin-top:30px; color:#888; font-size:12px; }}
</style></head><body>

<div class="banner">
<h1>⚠️ DEGRADED MODE: performance.csv unavailable, full system resource analysis skipped</h1>
<div>This is a minimal fallback report generated from vegeta JSON output and
block-height monitor data only. System metrics (disk I/O, CPU, memory,
network, per-method attribution) were not analysed because the
<code>performance.csv</code> file was missing or empty.</div>
</div>

<h2>QPS Sweep Summary</h2>
{qps_table}

<h2>Block Height Trend</h2>
{svg}

<h2>Capabilities skipped in degraded mode</h2>
<ul class="missing">{missing}</ul>

<footer>Generated {html_escape.escape(now)} by analysis/degraded_report.py</footer>
</body></html>
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate(vegeta_dir: str, logs_dir: str, reports_dir: str) -> str:
    os.makedirs(reports_dir, exist_ok=True)
    vegeta_rows = collect_vegeta(vegeta_dir)
    height_points = collect_block_heights(logs_dir)
    html_doc = build_html(vegeta_rows, height_points)
    out_path = os.path.join(reports_dir, "degraded_report.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    return out_path


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        sys.stderr.write(
            "usage: degraded_report.py <vegeta_results_dir> "
            "<logs_dir> <reports_dir>\n"
        )
        return 2
    out = generate(argv[1], argv[2], argv[3])
    print(f"[degraded-report] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
