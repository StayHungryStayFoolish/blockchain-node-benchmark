"""Synthetic disk visualization regression tests.

These tests simulate iostat-style DATA device columns so disk charts can be
verified even when the test container does not expose the production device
name such as /dev/sda.

Run with:
    python3 tests/test_disk_visualization_synthetic.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)

from visualization.disk_chart_generator import DiskChartGenerator  # noqa: E402
from visualization.performance_visualizer import PerformanceVisualizer  # noqa: E402


def _synthetic_performance_csv(path: Path) -> None:
    rows = []
    base = pd.Timestamp("2026-06-10T12:00:00")

    for i in range(48):
        read_iops = 800 + (i % 12) * 35
        write_iops = 420 + (i % 8) * 28
        read_kbs = read_iops * 12
        write_kbs = write_iops * 16
        total_iops = read_iops + write_iops
        total_mibs = (read_kbs + write_kbs) / 1024

        rows.append(
            {
                "timestamp": (base + pd.Timedelta(seconds=i)).isoformat(),
                "cpu_usage": 35 + (i % 10),
                "cpu_usr": 20 + (i % 5),
                "cpu_sys": 10 + (i % 4),
                "cpu_iowait": 4 + (i % 7) * 0.7,
                "cpu_soft": 1.0,
                "cpu_idle": 60 - (i % 10),
                "mem_used": 12_000,
                "mem_total": 32_000,
                "mem_usage": 37.5,
                "data_nvme0n1_r_s": read_iops,
                "data_nvme0n1_w_s": write_iops,
                "data_nvme0n1_rkb_s": read_kbs,
                "data_nvme0n1_wkb_s": write_kbs,
                "data_nvme0n1_r_await": 2.0 + (i % 6) * 0.2,
                "data_nvme0n1_w_await": 3.5 + (i % 7) * 0.25,
                "data_nvme0n1_avg_await": 2.8 + (i % 8) * 0.22,
                "data_nvme0n1_aqu_sz": 0.4 + (i % 9) * 0.08,
                "data_nvme0n1_util": 28 + (i % 14) * 3,
                "data_nvme0n1_rrqm_s": 0,
                "data_nvme0n1_wrqm_s": 0,
                "data_nvme0n1_rrqm_pct": 0,
                "data_nvme0n1_wrqm_pct": 0,
                "data_nvme0n1_rareq_sz": 12,
                "data_nvme0n1_wareq_sz": 16,
                "data_nvme0n1_total_iops": total_iops,
                "data_nvme0n1_normalized_iops": total_iops,
                "data_nvme0n1_read_throughput_mibs": read_kbs / 1024,
                "data_nvme0n1_write_throughput_mibs": write_kbs / 1024,
                "data_nvme0n1_total_throughput_mibs": total_mibs,
                "data_nvme0n1_normalized_throughput_mibs": total_mibs,
                "net_rx_mbps": 120,
                "net_tx_mbps": 40,
                "net_total_mbps": 160,
                "monitoring_cpu": 1.5,
                "monitoring_memory_percent": 0.8,
                "monitoring_iops_per_sec": 4,
                "monitoring_throughput_mibs_per_sec": 0.1,
                "local_block_height": 1_000_000 + i,
                "mainnet_block_height": 1_000_000 + i,
                "block_height_diff": 0,
                "local_health": 1,
                "mainnet_health": 1,
                "data_loss": 0,
                "sync_mode": "absolute_gap",
                "sync_status": "healthy",
                "lag_value": 0,
                "lag_unit": "block",
                "freshness_gap_seconds": 0,
                "probe_error": "",
                "current_qps": 100,
                "rpc_latency_ms": 12 + (i % 5),
                "qps_data_available": 1,
                "cloud_provider": "other",
            }
        )

    pd.DataFrame(rows).to_csv(path, index=False)


def _minimal_no_disk_csv(path: Path) -> None:
    base = pd.Timestamp("2026-06-10T12:00:00")
    rows = []
    for i in range(3):
        rows.append(
            {
                "timestamp": (base + pd.Timedelta(seconds=i)).isoformat(),
                "cpu_usage": 10 + i,
                "cpu_usr": 5,
                "cpu_sys": 3,
                "cpu_iowait": 0.5,
                "cpu_soft": 0,
                "cpu_idle": 90,
                "mem_used": 1_000,
                "mem_total": 4_000,
                "mem_usage": 25,
                "local_block_height": 1_000 + i,
                "mainnet_block_height": 1_000 + i,
                "block_height_diff": 0,
                "local_health": 1,
                "mainnet_health": 1,
                "data_loss": 0,
                "sync_mode": "absolute_gap",
                "sync_status": "healthy",
                "current_qps": 1,
                "rpc_latency_ms": 3,
                "qps_data_available": 1,
                "cloud_provider": "other",
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


class SyntheticDiskVisualizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.csv_path = self.tmp_path / "performance.csv"
        self.chart_dir = self.tmp_path / "charts"
        self.chart_dir.mkdir()
        _synthetic_performance_csv(self.csv_path)

        self.env = {
            "REPORTS_DIR": str(self.chart_dir),
            "DATA_VOL_MAX_IOPS": "3000",
            "DATA_VOL_MAX_THROUGHPUT": "500",
            "BOTTLENECK_DISK_UTIL_THRESHOLD": "90",
            "BOTTLENECK_DISK_LATENCY_THRESHOLD": "50",
            "BOTTLENECK_DISK_IOPS_THRESHOLD": "90",
            "BOTTLENECK_DISK_THROUGHPUT_THRESHOLD": "90",
        }
        self.old_env = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)

    def tearDown(self) -> None:
        for key, value in self.old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _assert_pngs_exist(self, paths: list[str], expected_names: set[str]) -> None:
        names = {Path(p).name for p in paths}
        self.assertTrue(expected_names.issubset(names), names)
        for path in paths:
            p = Path(path)
            self.assertTrue(p.exists(), f"{p} missing")
            self.assertGreater(p.stat().st_size, 1000, f"{p} unexpectedly small")

    def test_disk_chart_generator_accepts_synthetic_iostat_data(self) -> None:
        generator = DiskChartGenerator(str(self.csv_path), str(self.chart_dir))
        charts = generator.generate_all_disk_charts()

        self._assert_pngs_exist(
            charts,
            {
                "disk_capacity_planning.png",
                "disk_iostat_performance.png",
                "disk_bottleneck_correlation.png",
                "disk_performance_overview.png",
                "disk_bottleneck_analysis.png",
                "disk_normalized_comparison.png",
                "disk_time_series_analysis.png",
            },
        )

    def test_performance_visualizer_disk_entrypoints_accept_synthetic_data(self) -> None:
        visualizer = PerformanceVisualizer(str(self.csv_path))
        self.assertTrue(visualizer.load_data())

        charts = [
            visualizer.create_performance_overview_chart(),
            visualizer.create_correlation_visualization_chart(),
            visualizer.create_await_threshold_analysis_chart()[0],
            visualizer.create_util_threshold_analysis_chart()[0],
        ]

        self._assert_pngs_exist(
            [chart for chart in charts if chart],
            {
                "performance_overview.png",
                "cpu_disk_correlation_visualization.png",
                "await_threshold_analysis.png",
                "util_threshold_analysis.png",
            },
        )

    def test_threshold_charts_skip_cleanly_without_disk_columns(self) -> None:
        no_disk_csv = self.tmp_path / "performance_no_disk.csv"
        _minimal_no_disk_csv(no_disk_csv)

        visualizer = PerformanceVisualizer(str(no_disk_csv))
        self.assertTrue(visualizer.load_data())

        self.assertEqual(visualizer.create_await_threshold_analysis_chart(), (None, {}))
        self.assertEqual(visualizer.create_util_threshold_analysis_chart(), (None, {}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
