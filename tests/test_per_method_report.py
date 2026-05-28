"""单测: per-method HTML 报告章节 + 双语 (S4.2 W3.4 + W3.5).

加 W3.6 e2e mock 跑通完整 pipeline:
fixture CSV → 归因 → 图表 → HTML 章节 → 落盘可在浏览器查看.

跑法: python3 tests/test_per_method_report.py
"""

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.per_method_attribution import (  # noqa: E402
    PerMethodQpsRow,
    PerMethodResourceRow,
    compute_per_method_qps,
    compute_per_method_resource,
    read_monitor_csv,
    read_proxy_csv,
)
from visualization.per_method_charts import generate_all_charts  # noqa: E402
from visualization.per_method_report import (  # noqa: E402
    PER_METHOD_TRANSLATIONS,
    _t,
    compute_summary,
    get_chart_titles_for_language,
    render_per_method_section,
)


class TestI18n(unittest.TestCase):
    def test_en_zh_both_have_all_keys(self):
        en_keys = set(PER_METHOD_TRANSLATIONS["en"].keys())
        zh_keys = set(PER_METHOD_TRANSLATIONS["zh"].keys())
        self.assertEqual(en_keys, zh_keys,
                         f"i18n key mismatch: en-zh={en_keys-zh_keys}, zh-en={zh_keys-en_keys}")

    def test_t_fallback_en(self):
        self.assertEqual(_t("ja", "section_title"),
                         PER_METHOD_TRANSLATIONS["en"]["section_title"])

    def test_t_missing_key(self):
        self.assertEqual(_t("en", "nonexistent_key_xyz"), "[nonexistent_key_xyz]")

    def test_zh_section_title(self):
        self.assertIn("Per-Method", _t("zh", "section_title"))


class TestComputeSummary(unittest.TestCase):
    def test_basic_summary(self):
        qps_rows = [
            PerMethodQpsRow(100, "a", 5, 1, 2.0, 8.0),
            PerMethodQpsRow(100, "a", 3, 0, 3.0, 9.0),  # 同 method 不同秒
            PerMethodQpsRow(100, "b", 1, 0, 5.0, 5.0),
        ]
        res_rows = [
            PerMethodResourceRow(100, "a", 0.8, 80, 800),
            PerMethodResourceRow(101, "a", 0.6, 60, 600),
            PerMethodResourceRow(100, "b", 0.2, 20, 200),
        ]
        summary = compute_summary(qps_rows, res_rows)
        # a 总请求 8, b 总请求 1
        self.assertEqual(summary[0]["method"], "a")
        self.assertEqual(summary[0]["total_requests"], 8)
        self.assertEqual(summary[0]["error_count"], 1)
        self.assertAlmostEqual(summary[0]["error_rate"], 1/8)
        self.assertAlmostEqual(summary[0]["avg_p99_ms"], 8.5)  # (8+9)/2
        self.assertAlmostEqual(summary[0]["max_p99_ms"], 9.0)
        self.assertAlmostEqual(summary[0]["peak_cpu_share_pct"], 80.0)  # max weight a 0.8

    def test_top_n_truncates(self):
        qps_rows = [PerMethodQpsRow(100, f"m{i}", 100 - i, 0, 1, 1) for i in range(20)]
        summary = compute_summary(qps_rows, [], top_n=5)
        self.assertEqual(len(summary), 5)
        self.assertEqual([s["method"] for s in summary], ["m0", "m1", "m2", "m3", "m4"])


class TestRenderHtml(unittest.TestCase):
    def _fixture(self):
        qps_rows = [
            PerMethodQpsRow(100, "getSlot", 5, 0, 2.0, 8.0),
            PerMethodQpsRow(100, "getBlock", 3, 1, 10.0, 20.0),
        ]
        res_rows = [
            PerMethodResourceRow(100, "getSlot", 0.625, 50, 500),
            PerMethodResourceRow(100, "getBlock", 0.375, 30, 300),
        ]
        return qps_rows, res_rows

    def test_render_en(self):
        qps_rows, res_rows = self._fixture()
        summary = compute_summary(qps_rows, res_rows)
        html = render_per_method_section(
            "en", "solana",
            {"qps": "a.svg", "latency": "b.svg", "error_rate": "c.svg", "resource": "d.svg"},
            summary,
        )
        self.assertIn('<div class="section"', html)
        self.assertIn("Per-Method Performance Attribution", html)
        self.assertIn("solana", html)
        self.assertIn("getSlot", html)
        self.assertIn("getBlock", html)
        self.assertIn('<img src="a.svg"', html)
        self.assertIn('<img src="d.svg"', html)
        # 包含 4 张图 (qps/latency/error_rate/resource)
        self.assertEqual(html.count("<img"), 4)

    def test_render_zh(self):
        qps_rows, res_rows = self._fixture()
        summary = compute_summary(qps_rows, res_rows)
        html = render_per_method_section(
            "zh", "solana",
            {"qps": "a.svg", "latency": "b.svg", "error_rate": "c.svg", "resource": "d.svg"},
            summary,
        )
        self.assertIn("Per-Method 性能归因", html)
        self.assertIn("每方法 QPS", html)
        self.assertIn("方法", html)  # 表头

    def test_empty_summary_shows_no_data(self):
        html = render_per_method_section(
            "en", "chain",
            {"qps": "", "latency": "", "error_rate": "", "resource": ""},
            [],
        )
        self.assertIn("No per-method data", html)

    def test_html_escape_chain_name(self):
        # chain_name 注入 <script> 不该执行
        summary = []
        html = render_per_method_section(
            "en", "<script>alert(1)</script>",
            {"qps": "", "latency": "", "error_rate": "", "resource": ""},
            summary,
        )
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_get_chart_titles_for_language(self):
        en = get_chart_titles_for_language("en")
        zh = get_chart_titles_for_language("zh")
        self.assertEqual(set(en.keys()), {"qps", "latency", "error_rate", "resource"})
        self.assertNotEqual(en["qps"], zh["qps"])


def _ns(s, ms=0):
    return s * 1_000_000_000 + ms * 1_000_000


class TestW36E2E(unittest.TestCase):
    """W3.6 验收: fixture CSV → 归因 → 图 → HTML, 浏览器可看."""

    def test_e2e_full_pipeline_en(self):
        self._run_lang("en")

    def test_e2e_full_pipeline_zh(self):
        self._run_lang("zh")

    def _run_lang(self, language: str):
        tmpdir = tempfile.mkdtemp()
        try:
            proxy_path = Path(tmpdir) / "proxy.csv"
            monitor_path = Path(tmpdir) / "monitor.csv"

            # 写 fixture: 60 秒, 3 method 混合 + 1 个 error spike
            with open(proxy_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["timestamp_ns", "method_name", "protocol", "request_id",
                           "batch_idx", "status_code", "latency_ms", "upstream", "client_addr"])
                for t in range(60):
                    # getSlot 100 req/s
                    for i in range(100):
                        status = 500 if (t == 30 and i < 20) else 200  # t=30 spike
                        w.writerow([_ns(1700000000 + t, i * 10), "getSlot", "json_rpc",
                                   f"r{t}_{i}", "0", str(status), str(2 + i % 5), "u", "c"])
                    # getBlock 20 req/s
                    for i in range(20):
                        w.writerow([_ns(1700000000 + t, 500 + i * 25), "getBlock", "json_rpc",
                                   f"b{t}_{i}", "0", "200", str(15 + i), "u", "c"])

            with open(monitor_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["timestamp", "cpu_usage", "mem_used_mb"])
                for t in range(60):
                    cpu = 40 + (20 if t == 30 else 0)  # t=30 spike to 60
                    w.writerow([str(1700000000 + t), str(cpu), "4096"])

            # 跑 pipeline
            proxy_recs = list(read_proxy_csv(proxy_path))
            qps_rows = compute_per_method_qps(proxy_recs)
            monitor_recs = list(read_monitor_csv(monitor_path))
            res_rows = compute_per_method_resource(
                list(read_proxy_csv(proxy_path)), monitor_recs
            )

            # 60s × 2 method = 120 row
            self.assertEqual(len(qps_rows), 120)
            self.assertEqual(len(res_rows), 120)

            # 图
            chart_dir = Path(tmpdir) / "charts"
            titles = get_chart_titles_for_language(language)
            paths = generate_all_charts(
                qps_rows, res_rows, chart_dir, chain_name="solana", titles=titles,
            )
            for p in paths.values():
                self.assertTrue(p.exists())
                self.assertGreater(p.stat().st_size, 500)

            # HTML 章节
            summary = compute_summary(qps_rows, res_rows)
            section_html = render_per_method_section(
                language, "solana",
                {k: p.name for k, p in paths.items()},  # 用相对路径方便浏览器
                summary,
            )

            # 嵌入完整 HTML 页面写盘 — 用户/CI 可手动打开浏览器看
            full_html = f'''<!DOCTYPE html>
<html lang="{language}">
<head><meta charset="UTF-8"><title>per-method test ({language})</title></head>
<body style="font-family:Arial;max-width:1200px;margin:auto;padding:20px;">
{section_html}
</body></html>'''
            out_html = chart_dir / f"report_{language}.html"
            out_html.write_text(full_html, encoding="utf-8")

            # 验报告内容
            content = out_html.read_text()
            self.assertIn("getSlot", content)
            self.assertIn("getBlock", content)
            self.assertEqual(content.count("<img"), 4)
            # 错误率非 0 (t=30 spike)
            self.assertGreater(summary[0]["error_count"], 0)

            print(f"\n  [e2e-{language}] report written: {out_html}")
        finally:
            import shutil
            shutil.rmtree(tmpdir)


if __name__ == "__main__":
    unittest.main(verbosity=2)
