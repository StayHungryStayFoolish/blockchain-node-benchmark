"""Unit tests for analysis/degraded_report.py.

Pure stdlib; runnable as `python3 -m unittest tests/test_degraded_report.py`.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest

# Make repo root importable so we can `import analysis.degraded_report`.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from analysis import degraded_report  # noqa: E402


def _make_vegeta_summary(path: str, qps: int) -> None:
    blob = {
        "latencies": {
            "mean": 12_000_000,    # 12 ms in ns
            "50th": 10_000_000,
            "99th": 45_000_000,
            "max": 80_000_000,
        },
        "requests": 600,
        "success": 0.985,
        "status_codes": {"200": 591, "500": 9},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(blob, f)


def _make_vegeta_stream(path: str) -> None:
    """Stream-of-records flavour of vegeta JSON output."""
    with open(path, "w", encoding="utf-8") as f:
        for i in range(50):
            rec = {"code": 200 if i % 10 else 503,
                   "latency": (5 + i) * 1_000_000}
            f.write(json.dumps(rec) + "\n")


def _make_block_height_csv(path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "local_block_height", "mainnet_block_height"])
        for i in range(8):
            w.writerow([f"2026-05-28T13:30:{i:02d}", 1000 + i * 2, 1010 + i * 2])


class DegradedReportTests(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vegeta_dir = os.path.join(self.tmp.name, "vegeta")
        self.logs_dir = os.path.join(self.tmp.name, "logs")
        self.reports_dir = os.path.join(self.tmp.name, "reports")
        for d in (self.vegeta_dir, self.logs_dir, self.reports_dir):
            os.makedirs(d, exist_ok=True)

        _make_vegeta_summary(
            os.path.join(self.vegeta_dir, "vegeta_500qps_20260528_133000.json"), 500)
        _make_vegeta_summary(
            os.path.join(self.vegeta_dir, "vegeta_1000qps_20260528_133100.json"), 1000)
        _make_vegeta_stream(
            os.path.join(self.vegeta_dir, "vegeta_1500qps_20260528_133200.json"))
        _make_block_height_csv(
            os.path.join(self.logs_dir, "block_height_20260528_133000.csv"))

    def _run(self) -> str:
        return degraded_report.generate(self.vegeta_dir, self.logs_dir,
                                        self.reports_dir)

    def test_html_is_produced(self) -> None:
        out = self._run()
        self.assertTrue(os.path.isfile(out),
                        f"HTML report missing at {out}")
        self.assertEqual(os.path.basename(out), "degraded_report.html")
        self.assertGreater(os.path.getsize(out), 500)

    def test_html_contains_degraded_banner(self) -> None:
        out = self._run()
        with open(out, "r", encoding="utf-8") as f:
            html_doc = f.read()
        self.assertIn("DEGRADED MODE", html_doc)
        self.assertIn("performance.csv unavailable", html_doc)

    def test_html_contains_qps_table_rows(self) -> None:
        out = self._run()
        with open(out, "r", encoding="utf-8") as f:
            html_doc = f.read()
        # Summary rows for 500 / 1000 / 1500 QPS should all appear.
        self.assertIn("<table", html_doc)
        for qps in ("500", "1000", "1500"):
            self.assertIn(f">{qps}<", html_doc,
                          f"QPS row {qps} missing from table")
        # Latency columns rendered.
        self.assertIn("Mean (ms)", html_doc)
        self.assertIn("p99 (ms)", html_doc)

    def test_html_embeds_svg(self) -> None:
        out = self._run()
        with open(out, "r", encoding="utf-8") as f:
            html_doc = f.read()
        self.assertIn("<svg", html_doc)
        self.assertIn("polyline", html_doc,
                      "SVG line chart polyline element missing")

    def test_lists_missing_capabilities(self) -> None:
        out = self._run()
        with open(out, "r", encoding="utf-8") as f:
            html_doc = f.read()
        self.assertIn("Disk I/O", html_doc)
        self.assertIn("Per-method", html_doc)

    def test_handles_missing_data_directories(self) -> None:
        """Should still produce HTML even with no inputs at all."""
        empty_root = tempfile.mkdtemp(dir=self.tmp.name)
        v = os.path.join(empty_root, "vegeta")
        l_ = os.path.join(empty_root, "logs")
        r = os.path.join(empty_root, "reports")
        os.makedirs(v); os.makedirs(l_)
        out = degraded_report.generate(v, l_, r)
        self.assertTrue(os.path.isfile(out))
        with open(out, "r", encoding="utf-8") as f:
            html_doc = f.read()
        self.assertIn("DEGRADED MODE", html_doc)
        self.assertIn("No vegeta JSON results found", html_doc)
        self.assertIn("Block-height data unavailable", html_doc)


if __name__ == "__main__":
    unittest.main()
