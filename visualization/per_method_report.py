"""Per-method HTML report-section generator.

Output: an HTML <div class="section"> fragment that can be concatenated into
report_generator's main HTML.

Bilingual output: switch with language='en'/'zh', aligned with report_generator.TRANSLATIONS.
PER_METHOD_TRANSLATIONS stays local to avoid mutating global TRANSLATIONS.

Integration: report_generator.py calls this while building the main HTML:
    from visualization.per_method_report import render_per_method_section
    html += render_per_method_section(language, chain_name, chart_paths, summary)
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Sequence, Mapping

from analysis.per_method_attribution import PerMethodQpsRow, PerMethodResourceRow


# ---------- i18n ----------

PER_METHOD_TRANSLATIONS = {
    "en": {
        "section_title": "Per-Method Performance Attribution",
        "section_intro": (
            "Resource and latency metrics attributed per RPC method, based on proxy-level "
            "extraction. Top {top_n} methods by total QPS shown. Methods not matched by "
            "DSL extractors are excluded."
        ),
        "summary_title": "Summary",
        "method_col": "Method",
        "total_qps_col": "Total Requests",
        "avg_p99_col": "Avg p99 (ms)",
        "max_p99_col": "Max p99 (ms)",
        "error_count_col": "Errors",
        "success_count_col": "Successes",
        "error_rate_col": "Error Rate",
        "cpu_share_col": "CPU% Share (peak)",
        "chart_qps_title": "Per-Method QPS",
        "chart_qps_desc": (
            "Requests per second per method over the benchmark window. Useful for spotting "
            "method-level traffic spikes and skew."
        ),
        "chart_latency_title": "Per-Method p99 Latency",
        "chart_latency_desc": (
            "p99 latency per method per second. Identifies which methods drive tail latency "
            "and when degradation begins."
        ),
        "chart_error_title": "Per-Method Error Rate",
        "chart_error_desc": (
            "Per-second RPC failure rate per method. Localizes transport failures and "
            "JSON-RPC error responses to "
            "specific RPC calls during the run."
        ),
        "chart_success_failure_title": "Per-Method Success vs Failure",
        "chart_success_failure_desc": (
            "Total successful and failed requests per method across the benchmark "
            "window. This verifies whether configured single/mixed workload methods "
            "were actually accepted by the node."
        ),
        "chart_resource_title": "Per-Method CPU Attribution",
        "chart_resource_desc": (
            "CPU% attributed to each method per second using weight = method_count / "
            "total_count. Stacked area shows method-level resource contribution."
        ),
        "no_data": "No per-method data available — proxy sink CSV was empty or all requests were unmatched.",
    },
    "zh": {
        "section_title": "Per-Method 性能归因",
        "section_intro": (
            "基于 proxy 层提取的每 RPC method 资源与延迟指标。展示 QPS 总量排名前 {top_n} 的 "
            "method。未被 DSL extractor 匹配的请求已剔除。"
        ),
        "summary_title": "摘要",
        "method_col": "方法",
        "total_qps_col": "请求总数",
        "avg_p99_col": "平均 p99 (ms)",
        "max_p99_col": "最大 p99 (ms)",
        "error_count_col": "错误数",
        "success_count_col": "成功数",
        "error_rate_col": "错误率",
        "cpu_share_col": "CPU% 占比 (峰值)",
        "chart_qps_title": "每方法 QPS",
        "chart_qps_desc": (
            "压测窗口内每秒每 method 请求数。用于识别 method 级流量尖峰与不均衡。"
        ),
        "chart_latency_title": "每方法 p99 延迟",
        "chart_latency_desc": (
            "每秒每 method 的 p99 延迟。识别哪些 method 主导尾延迟以及何时开始劣化。"
        ),
        "chart_error_title": "每方法错误率",
        "chart_error_desc": (
            "每秒每 method 的 RPC 失败率。将传输失败和 JSON-RPC error 响应定位到具体 RPC 调用。"
        ),
        "chart_success_failure_title": "每方法成功/失败请求数",
        "chart_success_failure_desc": (
            "压测窗口内每个 method 的成功与失败请求总量。用于确认 single/mixed workload "
            "中配置的 RPC method 是否真的被节点接受。"
        ),
        "chart_resource_title": "每方法 CPU 归因",
        "chart_resource_desc": (
            "按 weight = method_count / total_count 把 CPU% 归因到每 method 每秒。"
            "堆叠面积图展示 method 级资源贡献。"
        ),
        "no_data": "无 per-method 数据 — proxy sink CSV 为空, 或所有请求均未匹配 DSL extractor。",
    },
}


def _t(language: str, key: str) -> str:
    """Look up i18n text, falling back to en and then [key]."""
    lang_dict = PER_METHOD_TRANSLATIONS.get(language, PER_METHOD_TRANSLATIONS["en"])
    if key in lang_dict:
        return lang_dict[key]
    return PER_METHOD_TRANSLATIONS["en"].get(key, f"[{key}]")


# ---------- summary ----------

def compute_summary(
    qps_rows: Sequence[PerMethodQpsRow],
    resource_rows: Sequence[PerMethodResourceRow],
    top_n: int = 10,
) -> list[dict]:
    """Aggregate method-level summary rows for the table.

    One row per method: total_requests, avg_p99, max_p99, errors,
    error_rate, peak_cpu_share.
    """
    by_method_qps: dict[str, list[PerMethodQpsRow]] = {}
    for r in qps_rows:
        by_method_qps.setdefault(r.method_name, []).append(r)
    by_method_res: dict[str, list[PerMethodResourceRow]] = {}
    for r in resource_rows:
        by_method_res.setdefault(r.method_name, []).append(r)

    summary = []
    for method, qrs in by_method_qps.items():
        total = sum(r.qps for r in qrs)
        errors = sum(r.error_count for r in qrs)
        successes = max(total - errors, 0)
        avg_p99 = sum(r.p99_ms for r in qrs) / len(qrs) if qrs else 0
        max_p99 = max((r.p99_ms for r in qrs), default=0)
        rrs = by_method_res.get(method, [])
        peak_cpu_share = max((r.weight for r in rrs), default=0) * 100
        summary.append({
            "method": method,
            "total_requests": total,
            "success_count": successes,
            "avg_p99_ms": avg_p99,
            "max_p99_ms": max_p99,
            "error_count": errors,
            "error_rate": errors / total if total > 0 else 0,
            "peak_cpu_share_pct": peak_cpu_share,
        })
    # top-N by total requests
    summary.sort(key=lambda s: -s["total_requests"])
    return summary[:top_n]


# ---------- HTML render ----------

def _esc(s: str) -> str:
    return html.escape(str(s))


def _render_summary_table(summary: list[dict], language: str) -> str:
    cols = [
        ("method_col", "method", str),
        ("total_qps_col", "total_requests", lambda v: f"{v:,}"),
        ("success_count_col", "success_count", lambda v: f"{v:,}"),
        ("error_count_col", "error_count", lambda v: f"{v:,}"),
        ("error_rate_col", "error_rate", lambda v: f"{v*100:.2f}%"),
        ("avg_p99_col", "avg_p99_ms", lambda v: f"{v:.2f}"),
        ("max_p99_col", "max_p99_ms", lambda v: f"{v:.2f}"),
        ("cpu_share_col", "peak_cpu_share_pct", lambda v: f"{v:.1f}%"),
    ]
    head = "".join(
        f'<th style="padding:6px 10px;border:1px solid #ccc;background:#f0f0f0;">'
        f'{_esc(_t(language, key))}</th>'
        for key, _, _ in cols
    )
    body_rows = []
    for s in summary:
        cells = "".join(
            f'<td style="padding:5px 10px;border:1px solid #ddd;">{_esc(fmt(s[field]))}</td>'
            for _, field, fmt in cols
        )
        body_rows.append(f'<tr>{cells}</tr>')
    if not body_rows:
        body_rows.append(
            f'<tr><td colspan="{len(cols)}" '
            f'style="padding:10px;text-align:center;color:#888;font-style:italic;">'
            f'{_esc(_t(language, "no_data"))}</td></tr>'
        )
    return (
        '<table style="border-collapse:collapse;margin:10px 0;font-size:13px;">'
        f'<thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody>'
        '</table>'
    )


def _render_chart_block(title_key: str, desc_key: str, img_path: str, language: str) -> str:
    return (
        f'<div class="subsection" style="margin:20px 0;">'
        f'<h3 style="color:#333;">{_esc(_t(language, title_key))}</h3>'
        f'<p style="color:#555;margin:5px 0 10px 0;">{_esc(_t(language, desc_key))}</p>'
        f'<img src="{_esc(img_path)}" alt="{_esc(_t(language, title_key))}" '
        f'style="max-width:100%;border:1px solid #ddd;background:#fff;"/>'
        f'</div>'
    )


def render_per_method_section(
    language: str,
    chain_name: str,
    chart_paths: Mapping[str, str | Path],
    summary: list[dict],
    top_n: int = 10,
) -> str:
    """Render the complete per-method HTML section.

    Args:
        language: 'en' | 'zh'
        chain_name: display chain name
        chart_paths: {'qps', 'latency', 'error_rate', 'resource'} -> chart paths
        summary: output from compute_summary()
        top_n: number of top methods displayed
    """
    title = _t(language, "section_title")
    intro = _t(language, "section_intro").format(top_n=top_n)
    summary_title = _t(language, "summary_title")

    parts = [
        '<div class="section" id="per-method-attribution" '
        'style="margin:30px 0;padding:20px;border:1px solid #ccc;background:#fafafa;">',
        f'<h2 style="color:#222;">📊 {_esc(title)} — {_esc(chain_name)}</h2>',
        f'<p style="color:#555;">{_esc(intro)}</p>',
        f'<h3 style="color:#333;margin-top:20px;">{_esc(summary_title)}</h3>',
        _render_summary_table(summary, language),
        _render_chart_block("chart_qps_title", "chart_qps_desc",
                            str(chart_paths.get("qps", "")), language),
        _render_chart_block("chart_latency_title", "chart_latency_desc",
                            str(chart_paths.get("latency", "")), language),
        _render_chart_block("chart_error_title", "chart_error_desc",
                            str(chart_paths.get("error_rate", "")), language),
        _render_chart_block("chart_success_failure_title", "chart_success_failure_desc",
                            str(chart_paths.get("success_failure", "")), language),
        _render_chart_block("chart_resource_title", "chart_resource_desc",
                            str(chart_paths.get("resource", "")), language),
        '</div>',
    ]
    return "\n".join(parts)


def get_chart_titles_for_language(language: str) -> dict[str, str]:
    """Return chart titles for per_method_charts.generate_all_charts(titles=...)."""
    return {
        "qps": _t(language, "chart_qps_title"),
        "latency": _t(language, "chart_latency_title"),
        "error_rate": _t(language, "chart_error_title"),
        "success_failure": _t(language, "chart_success_failure_title"),
        "resource": _t(language, "chart_resource_title"),
    }
