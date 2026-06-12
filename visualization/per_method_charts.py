"""Per-method chart generator.

Generates SVG chart types using only Python stdlib:
1. per_method_qps_<chain>.svg         - per-second per-method QPS line chart
2. per_method_latency_<chain>.svg     - per-second per-method p99 latency line chart
3. per_method_latency_percentiles_<chain>.svg - per-method P50/P90/P99 latency bars
4. per_method_error_rate_<chain>.svg  - per-second per-method error-rate line chart
5. per_method_resource_<chain>.svg    - per-second attributed-resource stacked area chart
6. per_method_success_failure_<chain>.svg - per-method success/failure totals

Design principles:
- no matplotlib/numpy/pandas dependency for this path
- SVG can be embedded in HTML or opened standalone
- top_n_methods=10 keeps dense mixed workloads readable
- Input rows come from per-method attribution output

Layout: 900x420 px viewBox with fixed padding for axis labels and legend.
"""

from __future__ import annotations

import html
import math
from collections import defaultdict
from pathlib import Path
from typing import Sequence

from analysis.per_method_attribution import PerMethodQpsRow, PerMethodResourceRow


# tab20-style palette with 20 distinguishable colors.
_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
    "#c49c94", "#f7b6d2", "#c7c7c7", "#dbdb8d", "#9edae5",
]

# Canvas dimensions.
_W, _H = 900, 420
_PAD_L, _PAD_R, _PAD_T, _PAD_B = 70, 200, 40, 50  # right padding reserves legend space
_PLOT_W = _W - _PAD_L - _PAD_R
_PLOT_H = _H - _PAD_T - _PAD_B


def _top_n_methods_by_qps(rows: Sequence[PerMethodQpsRow], n: int = 10) -> list[str]:
    totals: dict[str, int] = defaultdict(int)
    for r in rows:
        totals[r.method_name] += r.qps
    sorted_methods = sorted(totals.items(), key=lambda x: -x[1])
    return [m for m, _ in sorted_methods[:n]]


def _assign_colors(methods: list[str]) -> dict[str, str]:
    return {m: _PALETTE[i % len(_PALETTE)] for i, m in enumerate(methods)}


def _scale(value: float, vmin: float, vmax: float, out_min: float, out_max: float) -> float:
    if vmax == vmin:
        return out_min + (out_max - out_min) / 2
    return out_min + (value - vmin) / (vmax - vmin) * (out_max - out_min)


def _svg_header(title: str) -> str:
    safe = html.escape(title)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_W} {_H}" font-family="Arial, sans-serif" font-size="11">
<title>{safe}</title>
<style>
  .axis {{ stroke: #888; stroke-width: 1; }}
  .gridline {{ stroke: #ddd; stroke-width: 0.5; }}
  .label {{ fill: #333; }}
  .title {{ font-size: 14px; font-weight: bold; fill: #222; }}
</style>
<text class="title" x="{_W/2}" y="22" text-anchor="middle">{safe}</text>
<rect x="{_PAD_L}" y="{_PAD_T}" width="{_PLOT_W}" height="{_PLOT_H}" fill="#fafafa" stroke="#ccc"/>
'''


def _svg_axes(x_min: float, x_max: float, y_min: float, y_max: float,
              x_label: str, y_label: str) -> str:
    out = []
    # X-axis ticks.
    for i in range(6):
        x_px = _PAD_L + i * _PLOT_W / 5
        x_val = x_min + i * (x_max - x_min) / 5
        out.append(f'<line class="gridline" x1="{x_px}" y1="{_PAD_T}" x2="{x_px}" y2="{_PAD_T + _PLOT_H}"/>')
        out.append(f'<text class="label" x="{x_px}" y="{_PAD_T + _PLOT_H + 14}" text-anchor="middle">{int(x_val)}</text>')
    # Y-axis ticks.
    for i in range(6):
        y_px = _PAD_T + _PLOT_H - i * _PLOT_H / 5
        y_val = y_min + i * (y_max - y_min) / 5
        out.append(f'<line class="gridline" x1="{_PAD_L}" y1="{y_px}" x2="{_PAD_L + _PLOT_W}" y2="{y_px}"/>')
        out.append(f'<text class="label" x="{_PAD_L - 5}" y="{y_px + 3}" text-anchor="end">{y_val:.1f}</text>')
    # Axis labels.
    out.append(f'<text class="label" x="{_PAD_L + _PLOT_W/2}" y="{_H - 10}" text-anchor="middle">{html.escape(x_label)}</text>')
    out.append(f'<text class="label" x="15" y="{_PAD_T + _PLOT_H/2}" text-anchor="middle" transform="rotate(-90 15 {_PAD_T + _PLOT_H/2})">{html.escape(y_label)}</text>')
    return "\n".join(out) + "\n"


def _svg_legend(methods: list[str], colors: dict[str, str]) -> str:
    out = []
    x0 = _PAD_L + _PLOT_W + 12
    for i, m in enumerate(methods):
        y = _PAD_T + 10 + i * 18
        c = colors[m]
        out.append(f'<rect x="{x0}" y="{y - 8}" width="12" height="12" fill="{c}"/>')
        out.append(f'<text class="label" x="{x0 + 16}" y="{y + 2}">{html.escape(m)}</text>')
    return "\n".join(out) + "\n"


def _svg_line(points: list[tuple[float, float]], color: str, width: float = 1.5) -> str:
    if not points:
        return ""
    # Skip NaN by splitting polyline segments.
    segments: list[list[tuple[float, float]]] = [[]]
    for x, y in points:
        if math.isnan(y):
            if segments[-1]:
                segments.append([])
        else:
            segments[-1].append((x, y))
    out = []
    for seg in segments:
        if len(seg) < 2:
            continue
        pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in seg)
        out.append(f'<polyline fill="none" stroke="{color}" stroke-width="{width}" points="{pts}"/>')
    return "\n".join(out)


def _svg_stacked_area(
    x_values: list[float], series_by_method: list[tuple[str, list[float]]],
    colors: dict[str, str], x_min: float, x_max: float, y_max: float,
) -> str:
    """Stacked area chart. series_by_method order determines stack order."""
    n = len(x_values)
    if n == 0:
        return ""
    cum = [0.0] * n
    out = []
    for method, values in series_by_method:
        new_cum = [c + v for c, v in zip(cum, values)]
        # Polygon points: top edge plus reversed bottom edge.
        pts_top = [(
            _scale(x_values[i], x_min, x_max, _PAD_L, _PAD_L + _PLOT_W),
            _scale(new_cum[i], 0, y_max, _PAD_T + _PLOT_H, _PAD_T),
        ) for i in range(n)]
        pts_bot = [(
            _scale(x_values[i], x_min, x_max, _PAD_L, _PAD_L + _PLOT_W),
            _scale(cum[i], 0, y_max, _PAD_T + _PLOT_H, _PAD_T),
        ) for i in range(n - 1, -1, -1)]
        all_pts = pts_top + pts_bot
        pts_str = " ".join(f"{x:.2f},{y:.2f}" for x, y in all_pts)
        out.append(f'<polygon fill="{colors[method]}" fill-opacity="0.85" stroke="{colors[method]}" stroke-width="0.5" points="{pts_str}"/>')
        cum = new_cum
    return "\n".join(out)


def _write_svg(content: str, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content + "\n</svg>\n", encoding="utf-8")
    return out


# ---------- chart entry points ----------

def _build_qps_chart(rows: Sequence[PerMethodQpsRow], top_n: int, title: str,
                     y_label: str, value_picker) -> str:
    """Generic line chart for QPS/p99/error_rate, value_picker(row) -> float."""
    if not rows:
        return _svg_header(title) + _svg_axes(0, 1, 0, 1, "time", y_label) + ""
    methods = _top_n_methods_by_qps(rows, top_n)
    colors = _assign_colors(methods)
    all_ts = sorted({r.timestamp_s for r in rows})
    idx: dict[tuple[int, str], PerMethodQpsRow] = {(r.timestamp_s, r.method_name): r for r in rows}

    series: dict[str, list[float]] = {m: [] for m in methods}
    for ts in all_ts:
        for m in methods:
            r = idx.get((ts, m))
            series[m].append(float("nan") if r is None else value_picker(r))

    y_vals = [v for vs in series.values() for v in vs if not math.isnan(v)]
    y_max = max(y_vals) * 1.1 if y_vals else 1.0
    y_min = 0.0
    x_min = all_ts[0] if all_ts else 0
    x_max = all_ts[-1] if all_ts else 1
    if x_max == x_min:
        x_max = x_min + 1

    parts = [_svg_header(title), _svg_axes(x_min, x_max, y_min, y_max, "time (epoch s)", y_label)]
    for m in methods:
        pts = [
            (_scale(all_ts[i], x_min, x_max, _PAD_L, _PAD_L + _PLOT_W),
             _scale(series[m][i], y_min, y_max, _PAD_T + _PLOT_H, _PAD_T))
            for i in range(len(all_ts))
        ]
        parts.append(_svg_line(pts, colors[m]))
    parts.append(_svg_legend(methods, colors))
    return "\n".join(parts)


def plot_qps(rows: Sequence[PerMethodQpsRow], output: str | Path,
             top_n: int = 10, title: str = "Per-Method QPS") -> Path:
    svg = _build_qps_chart(rows, top_n, title, "QPS", lambda r: float(r.qps))
    return _write_svg(svg, output)


def plot_latency_p99(rows: Sequence[PerMethodQpsRow], output: str | Path,
                     top_n: int = 10, title: str = "Per-Method p99 Latency") -> Path:
    svg = _build_qps_chart(rows, top_n, title, "p99 latency (ms)", lambda r: r.p99_ms)
    return _write_svg(svg, output)


def plot_latency_percentiles(
    rows: Sequence[PerMethodQpsRow],
    output: str | Path,
    top_n: int = 10,
    title: str = "Per-Method Latency Percentiles",
) -> Path:
    """Grouped bar chart of average per-second P50/P90/P99 latency by method."""
    methods = _top_n_methods_by_qps(rows, top_n)
    if not methods:
        svg = _svg_header(title) + _svg_axes(0, 1, 0, 1, "method", "latency (ms)")
        return _write_svg(svg, output)

    by_method: dict[str, list[PerMethodQpsRow]] = defaultdict(list)
    for r in rows:
        if r.method_name in methods:
            by_method[r.method_name].append(r)

    percentiles: dict[str, tuple[float, float, float]] = {}
    for method in methods:
        method_rows = by_method.get(method, [])
        if not method_rows:
            percentiles[method] = (0.0, 0.0, 0.0)
            continue
        n = len(method_rows)
        percentiles[method] = (
            sum(r.p50_ms for r in method_rows) / n,
            sum(r.p90_ms for r in method_rows) / n,
            sum(r.p99_ms for r in method_rows) / n,
        )

    y_max = max(max(values) for values in percentiles.values()) * 1.15
    if y_max <= 0:
        y_max = 1.0

    colors = {"P50": "#2ca02c", "P90": "#ff7f0e", "P99": "#d62728"}
    group_w = _PLOT_W / max(len(methods), 1)
    bar_w = min(22, group_w / 5)
    parts = [_svg_header(title)]

    for i in range(6):
        y = _PAD_T + _PLOT_H - i * _PLOT_H / 5
        val = y_max * i / 5
        parts.append(f'<line class="gridline" x1="{_PAD_L}" y1="{y}" x2="{_PAD_L + _PLOT_W}" y2="{y}"/>')
        parts.append(f'<text class="label" x="{_PAD_L - 5}" y="{y + 3}" text-anchor="end">{val:.1f}</text>')

    for idx, method in enumerate(methods):
        center = _PAD_L + group_w * idx + group_w / 2
        values = percentiles[method]
        labels = ("P50", "P90", "P99")
        for j, label in enumerate(labels):
            value = values[j]
            height = _scale(value, 0, y_max, 0, _PLOT_H)
            x = center + (j - 1) * (bar_w + 3) - bar_w / 2
            y = _PAD_T + _PLOT_H - height
            parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{height:.2f}" fill="{colors[label]}" opacity="0.9"/>')
        safe_method = html.escape(method)
        parts.append(
            f'<text class="label" x="{center:.2f}" y="{_PAD_T + _PLOT_H + 16}" '
            f'text-anchor="end" transform="rotate(-25 {center:.2f} {_PAD_T + _PLOT_H + 16})">{safe_method}</text>'
        )

    parts.append(f'<text class="label" x="15" y="{_PAD_T + _PLOT_H/2}" text-anchor="middle" transform="rotate(-90 15 {_PAD_T + _PLOT_H/2})">latency (ms)</text>')
    legend_x = _PAD_L + _PLOT_W + 12
    for i, label in enumerate(("P50", "P90", "P99")):
        y = _PAD_T + 10 + i * 20
        parts.append(f'<rect x="{legend_x}" y="{y - 8}" width="12" height="12" fill="{colors[label]}"/>')
        parts.append(f'<text class="label" x="{legend_x + 16}" y="{y + 2}">{label}</text>')

    return _write_svg("\n".join(parts), output)


def plot_error_rate(rows: Sequence[PerMethodQpsRow], output: str | Path,
                    top_n: int = 10, title: str = "Per-Method Error Rate") -> Path:
    svg = _build_qps_chart(rows, top_n, title, "error rate (%)",
                           lambda r: (r.error_count / r.qps * 100) if r.qps > 0 else 0.0)
    return _write_svg(svg, output)


def plot_success_failure_totals(
    rows: Sequence[PerMethodQpsRow],
    output: str | Path,
    top_n: int = 10,
    title: str = "Per-Method Success vs Failure",
) -> Path:
    methods = _top_n_methods_by_qps(rows, top_n)
    totals: dict[str, int] = defaultdict(int)
    failures: dict[str, int] = defaultdict(int)
    for r in rows:
        if r.method_name in methods:
            totals[r.method_name] += r.qps
            failures[r.method_name] += r.error_count

    if not methods:
        svg = _svg_header(title) + _svg_axes(0, 1, 0, 1, "requests", "method")
        return _write_svg(svg, output)

    max_total = max(totals.values()) if totals else 1
    if max_total <= 0:
        max_total = 1

    chart_w = _PLOT_W
    row_h = min(28, max(16, int(_PLOT_H / max(len(methods), 1)) - 4))
    y0 = _PAD_T + 12
    success_color = "#2ca02c"
    failure_color = "#d62728"
    parts = [
        _svg_header(title),
        f'<text class="label" x="{_PAD_L}" y="{_H - 12}">requests</text>',
    ]

    for i in range(6):
        x = _PAD_L + i * chart_w / 5
        val = max_total * i / 5
        parts.append(f'<line class="gridline" x1="{x}" y1="{_PAD_T}" x2="{x}" y2="{_PAD_T + _PLOT_H}"/>')
        parts.append(f'<text class="label" x="{x}" y="{_PAD_T + _PLOT_H + 14}" text-anchor="middle">{int(val)}</text>')

    for idx, method in enumerate(methods):
        y = y0 + idx * (row_h + 7)
        total = totals[method]
        fail = failures[method]
        success = max(total - fail, 0)
        success_w = chart_w * success / max_total
        fail_w = chart_w * fail / max_total
        parts.append(f'<text class="label" x="{_PAD_L - 8}" y="{y + row_h * 0.68}" text-anchor="end">{html.escape(method)}</text>')
        parts.append(f'<rect x="{_PAD_L}" y="{y}" width="{success_w:.2f}" height="{row_h}" fill="{success_color}" opacity="0.9"/>')
        parts.append(f'<rect x="{_PAD_L + success_w:.2f}" y="{y}" width="{fail_w:.2f}" height="{row_h}" fill="{failure_color}" opacity="0.9"/>')
        parts.append(f'<text class="label" x="{_PAD_L + chart_w + 8}" y="{y + row_h * 0.68}">{success}/{fail}</text>')

    legend_x = _PAD_L + _PLOT_W + 70
    parts.append(f'<rect x="{legend_x}" y="{_PAD_T}" width="12" height="12" fill="{success_color}"/>')
    parts.append(f'<text class="label" x="{legend_x + 16}" y="{_PAD_T + 10}">success</text>')
    parts.append(f'<rect x="{legend_x}" y="{_PAD_T + 20}" width="12" height="12" fill="{failure_color}"/>')
    parts.append(f'<text class="label" x="{legend_x + 16}" y="{_PAD_T + 30}">failure</text>')
    return _write_svg("\n".join(parts), output)


def plot_resource_stacked(
    qps_rows: Sequence[PerMethodQpsRow],
    resource_rows: Sequence[PerMethodResourceRow],
    output: str | Path,
    top_n: int = 10,
    title: str = "Per-Method CPU Attribution (stacked)",
) -> Path:
    methods = _top_n_methods_by_qps(qps_rows, top_n)
    colors = _assign_colors(methods)
    all_ts = sorted({r.timestamp_s for r in resource_rows})
    if not all_ts:
        svg = _svg_header(title) + _svg_axes(0, 1, 0, 1, "time", "cpu%")
        return _write_svg(svg, output)
    idx: dict[tuple[int, str], PerMethodResourceRow] = {(r.timestamp_s, r.method_name): r for r in resource_rows}
    series: list[tuple[str, list[float]]] = []
    for m in methods:
        vs: list[float] = []
        for ts in all_ts:
            r = idx.get((ts, m))
            vs.append(r.cpu_pct if r is not None else 0.0)
        series.append((m, vs))
    # y_max = max stacked sum
    stacked_max = max(sum(s[1][i] for s in series) for i in range(len(all_ts)))
    y_max = stacked_max * 1.1 if stacked_max > 0 else 1.0
    x_min = float(all_ts[0]); x_max = float(all_ts[-1])
    if x_max == x_min:
        x_max = x_min + 1
    x_floats = [float(t) for t in all_ts]
    parts = [
        _svg_header(title),
        _svg_axes(x_min, x_max, 0, y_max, "time (epoch s)", "CPU% (attributed)"),
        _svg_stacked_area(x_floats, series, colors, x_min, x_max, y_max),
        _svg_legend(methods, colors),
    ]
    return _write_svg("\n".join(parts), output)


def generate_all_charts(
    qps_rows: Sequence[PerMethodQpsRow],
    resource_rows: Sequence[PerMethodResourceRow],
    output_dir: str | Path,
    chain_name: str = "chain",
    top_n: int = 10,
    titles: dict[str, str] | None = None,
) -> dict[str, Path]:
    titles = titles or {}
    out_dir = Path(output_dir); out_dir.mkdir(parents=True, exist_ok=True)
    return {
        "qps": plot_qps(qps_rows, out_dir / f"per_method_qps_{chain_name}.svg",
                        top_n=top_n,
                        title=titles.get("qps", f"Per-Method QPS — {chain_name}")),
        "latency": plot_latency_p99(qps_rows, out_dir / f"per_method_latency_{chain_name}.svg",
                                    top_n=top_n,
                                    title=titles.get("latency", f"Per-Method p99 Latency — {chain_name}")),
        "latency_percentiles": plot_latency_percentiles(
            qps_rows, out_dir / f"per_method_latency_percentiles_{chain_name}.svg",
            top_n=top_n,
            title=titles.get("latency_percentiles", f"Per-Method Latency Percentiles — {chain_name}")),
        "error_rate": plot_error_rate(qps_rows, out_dir / f"per_method_error_rate_{chain_name}.svg",
                                      top_n=top_n,
                                      title=titles.get("error_rate", f"Per-Method Error Rate — {chain_name}")),
        "success_failure": plot_success_failure_totals(
            qps_rows, out_dir / f"per_method_success_failure_{chain_name}.svg",
            top_n=top_n,
            title=titles.get("success_failure", f"Per-Method Success vs Failure — {chain_name}")),
        "resource": plot_resource_stacked(
            qps_rows, resource_rows, out_dir / f"per_method_resource_{chain_name}.svg",
            top_n=top_n,
            title=titles.get("resource", f"Per-Method CPU Attribution — {chain_name}")),
    }
