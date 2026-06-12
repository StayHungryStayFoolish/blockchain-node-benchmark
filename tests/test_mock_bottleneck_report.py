#!/usr/bin/env python3
"""Synthetic bottleneck report regression test.

This is not a real node capacity benchmark. It injects high-load monitoring
signals and bottleneck status files so the report path can prove that mocked
extreme-pressure evidence is consumed end to end.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(REPO_ROOT))

from visualization.performance_visualizer import PerformanceVisualizer  # noqa: E402
from visualization.report_generator import ReportGenerator  # noqa: E402


def _ns(epoch_s: int) -> int:
    return epoch_s * 1_000_000_000


def _write_performance_csv(path: Path) -> None:
    rows = []
    base = pd.Timestamp("2026-06-12T12:00:00")
    for i in range(72):
        # First half is healthy warm-up, second half injects persistent pressure.
        pressured = i >= 30
        qps = 500 + i * 50
        cpu = 55 + (i % 5) if not pressured else 91 + (i % 5)
        mem = 52 + (i % 3) if not pressured else 92 + (i % 4)
        disk_util = 45 + (i % 10) if not pressured else 94 + (i % 5)
        avg_await = 6 + (i % 4) if not pressured else 58 + (i % 8)
        read_iops = 900 + i * 20 if not pressured else 2700 + i * 25
        write_iops = 600 + i * 15 if not pressured else 2100 + i * 20
        read_mibs = read_iops * 12 / 1024
        write_mibs = write_iops * 16 / 1024
        height_diff = 3 if not pressured else 188

        epoch_s = 1_781_265_600 + i
        rows.append(
            {
                "timestamp": epoch_s,
                "cpu_usage": cpu,
                "cpu_usr": max(cpu - 20, 0),
                "cpu_sys": 16 if pressured else 8,
                "cpu_iowait": 18 if pressured else 2,
                "cpu_soft": 2,
                "cpu_idle": max(100 - cpu, 0),
                "mem_used": 12000 + i * 20,
                "mem_total": 32000,
                "mem_usage": mem,
                "data_nvme0n1_r_s": read_iops,
                "data_nvme0n1_w_s": write_iops,
                "data_nvme0n1_rkb_s": read_iops * 12,
                "data_nvme0n1_wkb_s": write_iops * 16,
                "data_nvme0n1_r_await": avg_await * 0.8,
                "data_nvme0n1_w_await": avg_await * 1.2,
                "data_nvme0n1_avg_await": avg_await,
                "data_nvme0n1_aqu_sz": 0.5 if not pressured else 4.5,
                "data_nvme0n1_util": disk_util,
                "data_nvme0n1_total_iops": read_iops + write_iops,
                "data_nvme0n1_normalized_iops": read_iops + write_iops,
                "data_nvme0n1_read_throughput_mibs": read_mibs,
                "data_nvme0n1_write_throughput_mibs": write_mibs,
                "data_nvme0n1_total_throughput_mibs": read_mibs + write_mibs,
                "data_nvme0n1_normalized_throughput_mibs": read_mibs + write_mibs,
                "net_rx_mbps": 1200 if pressured else 220,
                "net_tx_mbps": 900 if pressured else 110,
                "net_total_mbps": 2100 if pressured else 330,
                "monitoring_cpu": 1.9,
                "monitoring_memory_percent": 0.9,
                "monitoring_iops_per_sec": 5,
                "monitoring_throughput_mibs_per_sec": 0.2,
                "local_block_height": 1000000 + i,
                "mainnet_block_height": 1000000 + i + height_diff,
                "block_height_diff": height_diff,
                "local_health": 0 if pressured else 1,
                "mainnet_health": 1,
                "data_loss": 0,
                "sync_mode": "absolute_gap",
                "sync_status": "behind" if pressured else "healthy",
                "lag_value": height_diff,
                "lag_unit": "slot",
                "freshness_gap_seconds": 0,
                "probe_error": "",
                "current_qps": qps,
                "rpc_latency_ms": 1450 if pressured else 80,
                "qps_data_available": 1,
                "cloud_provider": "gcp",
            }
        )

    pd.DataFrame(rows).to_csv(path, index=False)


def _write_proxy_csv(path: Path) -> None:
    methods = ["getAccountInfo", "getBalance", "getTokenAccountBalance"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp_ns",
                "method_name",
                "protocol",
                "request_id",
                "batch_idx",
                "status_code",
                "transport_success",
                "rpc_success",
                "rpc_error_code",
                "rpc_error_message",
                "latency_ms",
                "upstream",
                "client_addr",
            ]
        )
        # Align with the numeric epoch timestamps in the performance CSV.
        for second in range(1_781_265_600, 1_781_265_630):
            for idx, method in enumerate(methods):
                ok = not (second >= 1_781_265_620 and method == "getTokenAccountBalance")
                writer.writerow(
                    [
                        _ns(second) + idx,
                        method,
                        "json_rpc",
                        f"req-{second}-{idx}",
                        0,
                        200 if ok else 500,
                        "true" if ok else "false",
                        "true" if ok else "false",
                        "" if ok else "-32005",
                        "" if ok else "mock injected overload",
                        85 if ok else 1800,
                        "http://127.0.0.1:8899",
                        "127.0.0.1:50000",
                    ]
                )
            # Sync-health probes should be excluded from per-method attribution.
            writer.writerow(
                [
                    _ns(second) + 99,
                    "getHealth",
                    "json_rpc",
                    f"probe-{second}",
                    0,
                    200,
                    "true",
                    "true",
                    "",
                    "",
                    3,
                    "http://127.0.0.1:8899",
                    "127.0.0.1:50000",
                ]
            )


def _write_block_height_csv(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp",
                "local_block_height",
                "mainnet_block_height",
                "block_height_diff",
                "local_health",
                "mainnet_health",
                "data_loss",
                "sync_mode",
                "sync_status",
                "lag_value",
                "lag_unit",
                "freshness_gap_seconds",
                "probe_error",
            ]
        )
        for i in range(72):
            pressured = i >= 30
            writer.writerow(
                [
                    f"2026-06-12 12:{i // 60:02d}:{i % 60:02d}",
                    1000000 + i,
                    1000000 + i + (188 if pressured else 3),
                    188 if pressured else 3,
                    0 if pressured else 1,
                    1,
                    0,
                    "absolute_gap",
                    "behind" if pressured else "healthy",
                    188 if pressured else 3,
                    "slot",
                    0,
                    "",
                ]
            )


class MockBottleneckReportTest(unittest.TestCase):
    def test_mocked_extreme_pressure_signals_render_in_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs_dir = root / "logs"
            reports_dir = root / "reports"
            memory_dir = root / "memory"
            logs_dir.mkdir()
            reports_dir.mkdir()
            memory_dir.mkdir()

            session = "20260612_120000"
            perf_csv = logs_dir / f"performance_{session}.csv"
            latest_csv = logs_dir / "performance_latest.csv"
            proxy_csv = logs_dir / "proxy_method.csv"
            bottleneck_json = memory_dir / "bottleneck_status.json"

            _write_performance_csv(perf_csv)
            latest_csv.write_text(perf_csv.read_text(encoding="utf-8"), encoding="utf-8")
            _write_proxy_csv(proxy_csv)
            _write_block_height_csv(logs_dir / f"block_height_monitor_{session}.csv")

            bottleneck_json.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-06-12T12:00:42Z",
                        "status": "bottleneck_detected",
                        "bottleneck_detected": True,
                        "bottleneck_types": ["CPU", "DATA_IO", "RPC_LATENCY", "SYNC_HEALTH"],
                        "bottleneck_reasons": "Mock injected CPU, disk, RPC latency, and sync-health pressure",
                        "max_successful_qps": 1800,
                        "bottleneck_qps": 2400,
                        "current_qps": 2400,
                        "severity": "high",
                        "detection_time": "2026-06-12 12:00:42",
                        "consecutive_detections": 3,
                    }
                ),
                encoding="utf-8",
            )

            old_env = dict(os.environ)
            try:
                os.environ.update(
                    {
                        "LOGS_DIR": str(logs_dir),
                        "REPORTS_DIR": str(reports_dir),
                        "MEMORY_SHARE_DIR": str(memory_dir),
                        "BOTTLENECK_STATUS_FILE": str(bottleneck_json),
                        "PROXY_METHOD_CSV": str(proxy_csv),
                        "UNIFIED_MONITOR_CSV": str(perf_csv),
                        "SESSION_TIMESTAMP": session,
                        "BLOCKCHAIN_NODE": "solana",
                        "RPC_MODE": "mixed",
                        "CLOUD_PROVIDER": "gcp",
                        "CLOUD_REGION": "asia-east1",
                        "MACHINE_TYPE": "c3-standard-8",
                        "LEDGER_DEVICE": "nvme0n1",
                        "DATA_VOL_TYPE": "hyperdisk-extreme",
                        "DATA_VOL_MAX_IOPS": "3000",
                        "DATA_VOL_MAX_THROUGHPUT": "500",
                        "BOTTLENECK_CPU_THRESHOLD": "85",
                        "BOTTLENECK_MEMORY_THRESHOLD": "90",
                        "BOTTLENECK_DISK_UTIL_THRESHOLD": "90",
                        "BOTTLENECK_DISK_LATENCY_THRESHOLD": "50",
                    }
                )
                visualizer = PerformanceVisualizer(str(perf_csv))
                chart_paths = visualizer.generate_all_charts()
                self.assertTrue(chart_paths, "performance visualizer generated no charts")

                generator = ReportGenerator(
                    str(perf_csv),
                    bottleneck_info=str(bottleneck_json),
                    language="en",
                )
                report_path = generator.generate_html_report()
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            self.assertIsNotNone(report_path)
            report = Path(report_path)
            self.assertTrue(report.exists())
            html = report.read_text(encoding="utf-8")

            self.assertIn("System-Level Performance Bottleneck Detected", html)
            self.assertIn("Mock injected CPU, disk, RPC latency, and sync-health pressure", html)
            self.assertIn("2400", html)
            self.assertIn("Per-Method Performance Attribution", html)
            self.assertIn("getAccountInfo", html)
            self.assertIn("getTokenAccountBalance", html)
            self.assertNotIn(">getHealth<", html)
            self.assertIn("Data Quality Summary", html)
            self.assertIn("Valid Disk Samples", html)

            expected_pngs = [
                "performance_overview.png",
                "bottleneck_identification.png",
                "block_height_sync_chart.png",
                "disk_bottleneck_analysis.png",
                "disk_bottleneck_correlation.png",
            ]
            for name in expected_pngs:
                png = reports_dir / name
                self.assertTrue(png.exists(), f"missing {png}")
                self.assertGreater(png.stat().st_size, 1000, f"small chart {png}")

            per_method_dir = reports_dir / "per_method_charts"
            self.assertTrue(per_method_dir.exists())
            expected_per_method_charts = {
                "per_method_qps_solana.svg",
                "per_method_latency_solana.svg",
                "per_method_latency_percentiles_solana.svg",
                "per_method_error_rate_solana.svg",
                "per_method_resource_solana.svg",
                "per_method_success_failure_solana.svg",
            }
            actual_per_method_charts = {path.name for path in per_method_dir.glob("*.svg")}
            self.assertTrue(
                expected_per_method_charts.issubset(actual_per_method_charts),
                actual_per_method_charts,
            )
            for chart_name in expected_per_method_charts:
                self.assertGreater((per_method_dir / chart_name).stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
