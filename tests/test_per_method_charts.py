"""Unit tests for per-method chart generation.

These tests avoid pixel-level assertions. They verify:
- generated SVG files exist and are non-empty
- SVG start/end tags are valid
- expected method names and polyline/polygon tags are present
- empty and boundary inputs do not crash

Run: python3 tests/test_per_method_charts.py
"""

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.per_method_attribution import PerMethodQpsRow, PerMethodResourceRow  # noqa: E402
from visualization.per_method_charts import (  # noqa: E402
    _PALETTE,
    _top_n_methods_by_qps,
    _assign_colors,
    _scale,
    generate_all_charts,
    plot_success_failure_totals,
    plot_error_rate,
    plot_latency_p99,
    plot_qps,
    plot_resource_stacked,
)


class TestHelpers(unittest.TestCase):
    def test_top_n_by_qps(self):
        rows = [
            PerMethodQpsRow(100, "a", 5, 0, 1.0, 2.0),
            PerMethodQpsRow(101, "a", 3, 0, 1.0, 2.0),
            PerMethodQpsRow(100, "b", 10, 0, 1.0, 2.0),
            PerMethodQpsRow(100, "c", 1, 0, 1.0, 2.0),
        ]
        top = _top_n_methods_by_qps(rows, n=2)
        self.assertEqual(top, ["b", "a"])  # b=10, a=8

    def test_assign_colors(self):
        cs = _assign_colors(["x", "y", "z"])
        self.assertEqual(cs["x"], _PALETTE[0])
        self.assertEqual(cs["y"], _PALETTE[1])
        self.assertEqual(cs["z"], _PALETTE[2])

    def test_scale(self):
        self.assertAlmostEqual(_scale(50, 0, 100, 0, 1000), 500)
        self.assertAlmostEqual(_scale(0, 0, 100, 100, 200), 100)
        # Degenerate range: vmax == vmin.
        self.assertAlmostEqual(_scale(5, 5, 5, 0, 100), 50)


def _make_fixture():
    qps_rows = [
        PerMethodQpsRow(100, "getSlot", 5, 1, 2.5, 9.9),
        PerMethodQpsRow(100, "getBlock", 3, 0, 10.0, 20.0),
        PerMethodQpsRow(101, "getSlot", 6, 0, 3.0, 11.0),
        PerMethodQpsRow(102, "getSlot", 4, 2, 5.0, 15.0),
        PerMethodQpsRow(102, "getBlock", 2, 0, 8.0, 18.0),
    ]
    resource_rows = [
        PerMethodResourceRow(100, "getSlot", 0.625, 50.0, 500.0),
        PerMethodResourceRow(100, "getBlock", 0.375, 30.0, 300.0),
        PerMethodResourceRow(101, "getSlot", 1.0, 70.0, 700.0),
        PerMethodResourceRow(102, "getSlot", 0.667, 60.0, 600.0),
        PerMethodResourceRow(102, "getBlock", 0.333, 30.0, 300.0),
    ]
    return qps_rows, resource_rows


class TestPlots(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.qps_rows, self.res_rows = _make_fixture()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def _assert_valid_svg(self, path: Path, expect_methods: list[str]):
        self.assertTrue(path.exists(), f"{path} missing")
        content = path.read_text()
        self.assertGreater(len(content), 200, "SVG too small")
        self.assertTrue(content.startswith("<svg"), "missing <svg")
        self.assertTrue(content.rstrip().endswith("</svg>"), "missing </svg>")
        # Legend includes method names.
        for m in expect_methods:
            self.assertIn(m, content, f"method {m} missing from {path.name}")

    def test_plot_qps(self):
        out = plot_qps(self.qps_rows, Path(self.tmp) / "qps.svg")
        self._assert_valid_svg(out, ["getSlot", "getBlock"])
        self.assertIn("polyline", out.read_text())

    def test_plot_latency(self):
        out = plot_latency_p99(self.qps_rows, Path(self.tmp) / "p99.svg")
        self._assert_valid_svg(out, ["getSlot", "getBlock"])

    def test_plot_error_rate(self):
        out = plot_error_rate(self.qps_rows, Path(self.tmp) / "err.svg")
        self._assert_valid_svg(out, ["getSlot", "getBlock"])
        # Error rate is a percentage; this only verifies the plot does not crash.

    def test_plot_success_failure_totals(self):
        out = plot_success_failure_totals(self.qps_rows, Path(self.tmp) / "sf.svg")
        self._assert_valid_svg(out, ["getSlot", "getBlock"])
        content = out.read_text()
        self.assertIn("success", content)
        self.assertIn("failure", content)

    def test_plot_resource_stacked(self):
        out = plot_resource_stacked(
            self.qps_rows, self.res_rows, Path(self.tmp) / "res.svg"
        )
        self._assert_valid_svg(out, ["getSlot", "getBlock"])
        self.assertIn("polygon", out.read_text())

    def test_generate_all_charts(self):
        paths = generate_all_charts(
            self.qps_rows, self.res_rows, self.tmp, chain_name="solana",
        )
        self.assertEqual(set(paths.keys()), {"qps", "latency", "error_rate", "success_failure", "resource"})
        for kind, p in paths.items():
            self.assertTrue(p.exists(), f"{kind} → {p} missing")
            self.assertIn(f"_solana.svg", p.name)
            self._assert_valid_svg(p, ["getSlot"])

    def test_i18n_titles(self):
        paths = generate_all_charts(
            self.qps_rows, self.res_rows, self.tmp, chain_name="solana",
            titles={
                "qps": "\u6bcf\u65b9\u6cd5 QPS",
                "latency": "\u6bcf\u65b9\u6cd5 p99 \u5ef6\u8fdf",
                "error_rate": "\u6bcf\u65b9\u6cd5\u9519\u8bef\u7387",
                "resource": "\u6bcf\u65b9\u6cd5 CPU \u5f52\u56e0",
            },
        )
        self.assertIn("\u6bcf\u65b9\u6cd5 QPS", paths["qps"].read_text())
        self.assertIn("\u6bcf\u65b9\u6cd5 p99 \u5ef6\u8fdf", paths["latency"].read_text())
        self.assertIn("\u6bcf\u65b9\u6cd5 CPU \u5f52\u56e0", paths["resource"].read_text())


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def test_empty_qps_rows_does_not_crash(self):
        out = plot_qps([], Path(self.tmp) / "empty.svg")
        self.assertTrue(out.exists())

    def test_empty_resource_rows(self):
        out = plot_resource_stacked([], [], Path(self.tmp) / "empty.svg")
        self.assertTrue(out.exists())

    def test_single_data_point(self):
        rows = [PerMethodQpsRow(100, "m", 1, 0, 1.0, 1.0)]
        out = plot_qps(rows, Path(self.tmp) / "single.svg")
        self.assertTrue(out.exists())

    def test_top_n_limits(self):
        # 25 methods -> only top 10 are included.
        rows = [PerMethodQpsRow(100, f"m{i}", 100 - i, 0, 1.0, 1.0) for i in range(25)]
        out = plot_qps(rows, Path(self.tmp) / "top.svg", top_n=10)
        content = out.read_text()
        # m0..m9 appear in the legend; m10+ do not.
        for i in range(10):
            self.assertIn(f"m{i}", content)
        self.assertNotIn("m20", content)

    def test_html_escape_method_name(self):
        # Method names containing < > & must not break SVG markup.
        rows = [PerMethodQpsRow(100, "m<x>&y", 1, 0, 1.0, 1.0)]
        out = plot_qps(rows, Path(self.tmp) / "esc.svg")
        content = out.read_text()
        # The string should be escaped, not rendered as a raw <x> tag.
        self.assertNotIn("<x>", content)
        self.assertIn("m&lt;x&gt;", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
