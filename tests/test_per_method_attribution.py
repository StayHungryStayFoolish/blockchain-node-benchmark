"""单测: per-method 归因算法 (S4.2 W3.2).

测试覆盖:
- read_proxy_csv: 跳过 __unmatched__, ns 时间解析
- read_monitor_csv: 时间戳格式自适应 (s/ms/ns)
- _percentile: 边界 (空/单元素/p50/p99)
- compute_per_method_qps: 秒级 bucket + error 计数 + p50/p99
- compute_per_method_resource: weight = count/total + 缺监控秒跳过
- write_qps_csv / write_resource_csv: 列名 + 排序 + 浮点格式

跑法: python3 tests/test_per_method_attribution.py
"""

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 项目根
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.per_method_attribution import (  # noqa: E402
    MonitorRecord,
    PerMethodQpsRow,
    PerMethodResourceRow,
    ProxyRecord,
    _percentile,
    compute_per_method_qps,
    compute_per_method_resource,
    read_monitor_csv,
    read_proxy_csv,
    write_qps_csv,
    write_resource_csv,
)


def _ns(sec: int, ms: int = 0) -> int:
    return sec * 1_000_000_000 + ms * 1_000_000


class TestPercentile(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(_percentile([], 0.5), 0.0)

    def test_single(self):
        self.assertEqual(_percentile([42.0], 0.99), 42.0)

    def test_p50_even(self):
        # [1,2,3,4] — p50 idx = 0.5*3 = 1.5 → 2 + 0.5*(3-2) = 2.5
        self.assertAlmostEqual(_percentile([1, 2, 3, 4], 0.5), 2.5)

    def test_p99_large(self):
        vs = list(range(1, 101))  # 1..100
        # idx = 0.99 * 99 = 98.01 → 99 + 0.01*(100-99) = 99.01
        self.assertAlmostEqual(_percentile(vs, 0.99), 99.01)


class TestReadProxyCsv(unittest.TestCase):
    def _write_csv(self, rows: list[dict]) -> str:
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(path, "w", newline="") as f:
            if not rows:
                return path
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        return path

    def test_skips_unmatched(self):
        path = self._write_csv([
            {"timestamp_ns": _ns(100), "method_name": "getSlot", "protocol": "json_rpc",
             "request_id": "1", "batch_idx": "0", "status_code": "200",
             "latency_ms": "5", "upstream": "u1", "client_addr": "c1"},
            {"timestamp_ns": _ns(101), "method_name": "__unmatched__", "protocol": "json_rpc",
             "request_id": "2", "batch_idx": "0", "status_code": "200",
             "latency_ms": "3", "upstream": "u1", "client_addr": "c1"},
        ])
        try:
            recs = list(read_proxy_csv(path))
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0].method_name, "getSlot")
            self.assertEqual(recs[0].timestamp_ns, _ns(100))
        finally:
            os.unlink(path)

    def test_empty_batch_idx_defaults_zero(self):
        path = self._write_csv([
            {"timestamp_ns": _ns(100), "method_name": "getSlot", "protocol": "json_rpc",
             "request_id": "1", "batch_idx": "", "status_code": "200",
             "latency_ms": "5", "upstream": "", "client_addr": ""},
        ])
        try:
            recs = list(read_proxy_csv(path))
            self.assertEqual(recs[0].batch_idx, 0)
        finally:
            os.unlink(path)


class TestReadMonitorCsv(unittest.TestCase):
    def _write(self, rows: list[dict]) -> str:
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        return path

    def test_epoch_seconds(self):
        path = self._write([
            {"timestamp": "1700000000", "cpu_usage": "42.5", "mem_used_mb": "1024"},
        ])
        try:
            recs = list(read_monitor_csv(path))
            self.assertEqual(recs[0].timestamp_s, 1700000000)
            self.assertAlmostEqual(recs[0].cpu_pct, 42.5)
            self.assertAlmostEqual(recs[0].mem_mb, 1024.0)
        finally:
            os.unlink(path)

    def test_epoch_milliseconds(self):
        path = self._write([
            {"timestamp": "1700000000123", "cpu_usage": "10", "mem_used_mb": "512"},
        ])
        try:
            recs = list(read_monitor_csv(path))
            self.assertEqual(recs[0].timestamp_s, 1700000000)
        finally:
            os.unlink(path)

    def test_epoch_nanoseconds(self):
        path = self._write([
            {"timestamp": str(_ns(1700000000)), "cpu_usage": "10", "mem_used_mb": "512"},
        ])
        try:
            recs = list(read_monitor_csv(path))
            self.assertEqual(recs[0].timestamp_s, 1700000000)
        finally:
            os.unlink(path)


def _make_proxy(ts_s: int, method: str, latency_ms: int = 5,
                status: int = 200) -> ProxyRecord:
    return ProxyRecord(
        timestamp_ns=_ns(ts_s),
        method_name=method,
        protocol="json_rpc",
        request_id="r",
        batch_idx=0,
        status_code=status,
        latency_ms=latency_ms,
        upstream="u",
        client_addr="c",
    )


class TestComputePerMethodQps(unittest.TestCase):
    def test_basic_bucket(self):
        recs = [
            _make_proxy(100, "getSlot", latency_ms=2),
            _make_proxy(100, "getSlot", latency_ms=4),
            _make_proxy(100, "getBlock", latency_ms=10),
            _make_proxy(101, "getSlot", latency_ms=3),
        ]
        rows = compute_per_method_qps(recs)
        # 排序后: (100,getBlock), (100,getSlot), (101,getSlot)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].timestamp_s, 100)
        self.assertEqual(rows[0].method_name, "getBlock")
        self.assertEqual(rows[0].qps, 1)
        self.assertEqual(rows[1].method_name, "getSlot")
        self.assertEqual(rows[1].qps, 2)
        self.assertAlmostEqual(rows[1].p50_ms, 3.0)  # [2,4] p50 = 3
        self.assertEqual(rows[2].qps, 1)

    def test_error_count(self):
        recs = [
            _make_proxy(100, "getSlot", status=200),
            _make_proxy(100, "getSlot", status=500),
            _make_proxy(100, "getSlot", status=429),
            _make_proxy(100, "getSlot", status=399),  # 不算 error
        ]
        rows = compute_per_method_qps(recs)
        self.assertEqual(rows[0].error_count, 2)
        self.assertEqual(rows[0].qps, 4)


class TestComputePerMethodResource(unittest.TestCase):
    def test_weight_attribution(self):
        # 100 秒: getSlot×3, getBlock×1 → getSlot weight 0.75 / getBlock 0.25
        # monitor: cpu=80% mem=1000MB
        proxy = [
            _make_proxy(100, "getSlot"),
            _make_proxy(100, "getSlot"),
            _make_proxy(100, "getSlot"),
            _make_proxy(100, "getBlock"),
        ]
        monitor = [MonitorRecord(timestamp_s=100, cpu_pct=80.0, mem_mb=1000.0)]
        rows = compute_per_method_resource(proxy, monitor)
        self.assertEqual(len(rows), 2)
        # 排序: getBlock 在前
        self.assertEqual(rows[0].method_name, "getBlock")
        self.assertAlmostEqual(rows[0].weight, 0.25)
        self.assertAlmostEqual(rows[0].cpu_pct, 20.0)
        self.assertAlmostEqual(rows[0].mem_mb, 250.0)
        self.assertEqual(rows[1].method_name, "getSlot")
        self.assertAlmostEqual(rows[1].weight, 0.75)
        self.assertAlmostEqual(rows[1].cpu_pct, 60.0)
        self.assertAlmostEqual(rows[1].mem_mb, 750.0)

    def test_skip_missing_monitor_second(self):
        # proxy 在 100/101 都有, monitor 只有 100
        proxy = [_make_proxy(100, "m"), _make_proxy(101, "m")]
        monitor = [MonitorRecord(timestamp_s=100, cpu_pct=50, mem_mb=500)]
        rows = compute_per_method_resource(proxy, monitor)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].timestamp_s, 100)

    def test_weights_sum_to_one_per_second(self):
        proxy = [_make_proxy(100, "a"), _make_proxy(100, "b"), _make_proxy(100, "c")]
        monitor = [MonitorRecord(timestamp_s=100, cpu_pct=99, mem_mb=999)]
        rows = compute_per_method_resource(proxy, monitor)
        total_weight = sum(r.weight for r in rows)
        self.assertAlmostEqual(total_weight, 1.0)
        total_cpu = sum(r.cpu_pct for r in rows)
        self.assertAlmostEqual(total_cpu, 99.0)


class TestWriteCsv(unittest.TestCase):
    def test_qps_csv_header_and_rows(self):
        rows = [PerMethodQpsRow(100, "getSlot", 5, 1, 2.5, 9.9)]
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            write_qps_csv(rows, path)
            with open(path) as f:
                content = f.read()
            self.assertIn("timestamp_s,method_name,qps,error_count,p50_ms,p99_ms", content)
            self.assertIn("100,getSlot,5,1,2.500,9.900", content)
        finally:
            os.unlink(path)

    def test_resource_csv_header_and_rows(self):
        rows = [PerMethodResourceRow(100, "getSlot", 0.75, 60.0, 750.0)]
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            write_resource_csv(rows, path)
            with open(path) as f:
                content = f.read()
            self.assertIn("timestamp_s,method_name,weight,cpu_pct,mem_mb", content)
            self.assertIn("100,getSlot,0.750000,60.000,750.000", content)
        finally:
            os.unlink(path)


class TestE2eFixture(unittest.TestCase):
    """W3.6 验收: 从 fixture CSV 完整跑通归因 → 输出 2 个 CSV."""

    def test_e2e_pipeline(self):
        # 1. 写 proxy fixture (3 秒, 3 method 混合)
        tmpdir = tempfile.mkdtemp()
        try:
            proxy_path = Path(tmpdir) / "proxy.csv"
            monitor_path = Path(tmpdir) / "monitor.csv"
            with open(proxy_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["timestamp_ns", "method_name", "protocol", "request_id",
                           "batch_idx", "status_code", "latency_ms", "upstream", "client_addr"])
                # T=100: getSlot×5, getBlock×3
                for i in range(5):
                    w.writerow([_ns(100, i * 100), "getSlot", "json_rpc", str(i), "0",
                               "200", str(5 + i), "u", "c"])
                for i in range(3):
                    w.writerow([_ns(100, 500 + i * 100), "getBlock", "json_rpc",
                               str(100 + i), "0", "200", str(20 + i), "u", "c"])
                # T=101: getSlot×2, 1 error
                w.writerow([_ns(101, 0), "getSlot", "json_rpc", "200", "0", "200", "7", "u", "c"])
                w.writerow([_ns(101, 200), "getSlot", "json_rpc", "201", "0", "500", "100", "u", "c"])
                # T=102: 全 __unmatched__ (应被丢)
                w.writerow([_ns(102, 0), "__unmatched__", "json_rpc", "300", "0", "200", "3", "u", "c"])

            with open(monitor_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["timestamp", "cpu_usage", "mem_used_mb"])
                w.writerow(["100", "40.0", "2000"])
                w.writerow(["101", "60.0", "2200"])
                # T=102 故意不写, 验"缺监控秒跳过"

            # 2. 跑归因
            proxy_recs = list(read_proxy_csv(proxy_path))
            self.assertEqual(len(proxy_recs), 10)  # __unmatched__ 已跳

            qps_rows = compute_per_method_qps(proxy_recs)
            # T=100: getBlock(3), getSlot(5);  T=101: getSlot(2)
            self.assertEqual(len(qps_rows), 3)

            monitor_recs = list(read_monitor_csv(monitor_path))
            resource_rows = compute_per_method_resource(
                list(read_proxy_csv(proxy_path)), monitor_recs
            )
            # T=100: getBlock(weight=3/8=0.375), getSlot(weight=5/8=0.625)
            # T=101: getSlot(weight=1.0)
            self.assertEqual(len(resource_rows), 3)
            t100_block = [r for r in resource_rows if r.timestamp_s == 100 and r.method_name == "getBlock"][0]
            self.assertAlmostEqual(t100_block.weight, 0.375)
            self.assertAlmostEqual(t100_block.cpu_pct, 40.0 * 0.375)
            self.assertAlmostEqual(t100_block.mem_mb, 2000 * 0.375)

            t101_slot = [r for r in resource_rows if r.timestamp_s == 101][0]
            self.assertEqual(t101_slot.method_name, "getSlot")
            self.assertAlmostEqual(t101_slot.weight, 1.0)
            self.assertAlmostEqual(t101_slot.cpu_pct, 60.0)

            # 3. 写入 CSV 也成
            out_qps = Path(tmpdir) / "out_qps.csv"
            out_res = Path(tmpdir) / "out_res.csv"
            write_qps_csv(qps_rows, out_qps)
            write_resource_csv(resource_rows, out_res)
            self.assertTrue(out_qps.exists())
            self.assertTrue(out_res.exists())
        finally:
            import shutil
            shutil.rmtree(tmpdir)


if __name__ == "__main__":
    unittest.main(verbosity=2)
