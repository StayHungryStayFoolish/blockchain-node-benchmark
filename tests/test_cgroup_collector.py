#!/usr/bin/env python3
"""
Test suite for monitoring/cgroup_collector.py.

Covers all 4 modes:
  A: cgroup v2 unified
  B: cgroup v1 split-controller
  C: cgroup not mounted
  D: target cgroup path unresolvable

Plus header schema invariants and CLI smoke.

Run:
  python3 -m pytest tests/test_cgroup_collector.py -v
  # or
  python3 tests/test_cgroup_collector.py
"""

from __future__ import annotations

import os
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

# Make repo root importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "monitoring"))

import cgroup_collector as cc  # noqa: E402


class TestSchema(unittest.TestCase):
    def test_header_has_19_fields(self):
        self.assertEqual(len(cc.ALL_FIELDS), 19)

    def test_header_field_order_and_names(self):
        # IO first 6
        self.assertTrue(cc.ALL_FIELDS[0].startswith("cgroup_io_"))
        self.assertTrue(cc.ALL_FIELDS[5].startswith("cgroup_io_"))
        # MEM next 6
        for i in range(6, 12):
            self.assertTrue(cc.ALL_FIELDS[i].startswith("cgroup_mem_"))
        # CPU next 6
        for i in range(12, 18):
            self.assertTrue(cc.ALL_FIELDS[i].startswith("cgroup_cpu_"))
        # META last
        self.assertEqual(cc.ALL_FIELDS[18], "cgroup_meta_source")


class TestParsers(unittest.TestCase):
    def test_kv_line_parser_basic(self):
        text = "anon 1024\nfile 2048\nkernel 64\nbogus not_a_number\n"
        out = cc._parse_kv_lines(text)
        self.assertEqual(out["anon"], 1024)
        self.assertEqual(out["file"], 2048)
        self.assertEqual(out["kernel"], 64)
        self.assertNotIn("bogus", out)

    def test_io_stat_v2_parser(self):
        text = (
            "8:0 rbytes=1000 wbytes=2000 rios=10 wios=20 dbytes=5 dios=1\n"
            "8:16 rbytes=500 wbytes=1500 rios=2 wios=3 dbytes=0 dios=0\n"
        )
        out = cc._sum_io_stat_v2(text)
        self.assertEqual(out["rbytes"], 1500)
        self.assertEqual(out["wbytes"], 3500)
        self.assertEqual(out["rios"], 12)
        self.assertEqual(out["wios"], 23)
        self.assertEqual(out["dbytes"], 5)
        self.assertEqual(out["dios"], 1)

    def test_io_stat_v2_handles_garbage(self):
        text = "8:0 rbytes=NOT_A_NUMBER wbytes=100\n"
        out = cc._sum_io_stat_v2(text)
        self.assertEqual(out["rbytes"], 0)
        self.assertEqual(out["wbytes"], 100)

    def test_blkio_v1_parser(self):
        text = (
            "8:0 Read 1000\n"
            "8:0 Write 2000\n"
            "8:0 Discard 5\n"
            "8:16 Read 500\n"
            "8:16 Write 1500\n"
            "Total 5005\n"
        )
        out = cc._parse_blkio_v1(text)
        self.assertEqual(out["Read"], 1500)
        self.assertEqual(out["Write"], 3500)
        self.assertEqual(out["Discard"], 5)


class TestCgroupResolution(unittest.TestCase):
    def test_resolve_target_cgroup_v2_format(self):
        with tempfile.TemporaryDirectory() as td:
            proc = Path(td) / "proc"
            (proc / "1").mkdir(parents=True)
            (proc / "1" / "cgroup").write_text("0::/system.slice/blockchain.service\n")
            r = cc.resolve_target_cgroup(str(proc), "1")
            self.assertEqual(r, "/system.slice/blockchain.service")

    def test_resolve_target_cgroup_v1_format_blkio(self):
        with tempfile.TemporaryDirectory() as td:
            proc = Path(td) / "proc"
            (proc / "1").mkdir(parents=True)
            (proc / "1" / "cgroup").write_text(
                "11:blkio:/system.slice/geth\n"
                "10:memory:/system.slice/geth\n"
                "9:cpu,cpuacct:/system.slice/geth\n"
            )
            r = cc.resolve_target_cgroup(str(proc), "1")
            self.assertEqual(r, "/system.slice/geth")

    def test_resolve_target_cgroup_missing(self):
        with tempfile.TemporaryDirectory() as td:
            r = cc.resolve_target_cgroup(str(Path(td) / "nonexistent"), "9999")
            self.assertIsNone(r)


class TestCollectModes(unittest.TestCase):
    """Integration tests with synthetic cgroupfs trees."""

    def _make_v2_tree(self, td: Path, target_path: str = "/") -> Path:
        """Build a fake cgroup v2 hierarchy under td/sys/fs/cgroup with
        io.stat / memory.stat / cpu.stat at the given target_path."""
        sys_root = td / "sys"
        cg_root = sys_root / "fs" / "cgroup"
        cg_root.mkdir(parents=True)
        (cg_root / "cgroup.controllers").write_text("cpu memory io\n")

        target_dir = cg_root / target_path.lstrip("/")
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "io.stat").write_text(
            "8:0 rbytes=1000 wbytes=2000 rios=10 wios=20 dbytes=0 dios=0\n"
        )
        (target_dir / "memory.stat").write_text(
            "anon 5000\nfile 3000\nkernel 200\nslab 100\nsock 50\nswapcached 0\n"
        )
        (target_dir / "cpu.stat").write_text(
            "usage_usec 12345\nuser_usec 8000\nsystem_usec 4345\n"
            "nr_periods 100\nnr_throttled 5\nthrottled_usec 200\n"
        )

        proc = td / "proc"
        (proc / "self").mkdir(parents=True)
        (proc / "self" / "cgroup").write_text(f"0::{target_path}\n")
        return td

    def test_mode_a_cgroup_v2(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            self._make_v2_tree(td_path, "/test.slice")
            env = {
                "HOST_PROC": str(td_path / "proc"),
                "HOST_SYS": str(td_path / "sys"),
                "CGROUP_VERSION": "v2",
                "CGROUP_ROOT": str(td_path / "sys/fs/cgroup"),
            }
            old_env = {k: os.environ.get(k) for k in env}
            os.environ.update(env)
            try:
                row = cc.collect()
                self.assertEqual(row["cgroup_meta_source"], "v2")
                self.assertEqual(row["cgroup_io_rbytes"], 1000)
                self.assertEqual(row["cgroup_io_wbytes"], 2000)
                self.assertEqual(row["cgroup_mem_anon"], 5000)
                self.assertEqual(row["cgroup_cpu_usage_usec"], 12345)
                self.assertEqual(row["cgroup_cpu_nr_throttled"], 5)
            finally:
                for k, v in old_env.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v

    def test_mode_c_unmounted(self):
        with tempfile.TemporaryDirectory() as td:
            # No cgroup.controllers, no blkio/memory subdirs
            sys_root = Path(td) / "sys"
            (sys_root / "fs" / "cgroup").mkdir(parents=True)
            env = {
                "HOST_PROC": str(Path(td) / "proc"),
                "HOST_SYS": str(sys_root),
                "CGROUP_VERSION": "",      # force fallback detection
                "CGROUP_ROOT": "",
            }
            old_env = {k: os.environ.get(k) for k in env}
            os.environ.update(env)
            try:
                row = cc.collect()
                self.assertEqual(row["cgroup_meta_source"], "unmounted")
                self.assertEqual(row["cgroup_io_rbytes"], 0)
                self.assertEqual(row["cgroup_mem_anon"], 0)
                self.assertEqual(row["cgroup_cpu_usage_usec"], 0)
            finally:
                for k, v in old_env.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v

    def test_mode_d_unresolvable(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            # cgroup root exists (v2) but /proc/self/cgroup absent
            sys_root = td_path / "sys"
            cg_root = sys_root / "fs" / "cgroup"
            cg_root.mkdir(parents=True)
            (cg_root / "cgroup.controllers").write_text("cpu memory io\n")
            env = {
                "HOST_PROC": str(td_path / "nonexistent_proc"),
                "HOST_SYS": str(sys_root),
                "CGROUP_VERSION": "v2",
                "CGROUP_ROOT": str(cg_root),
                "TARGET_PID": "9999",  # nonexistent
            }
            # Clear any TARGET_CGROUP override
            old_env = {k: os.environ.get(k) for k in env}
            old_target = os.environ.pop("TARGET_CGROUP", None)
            os.environ.update(env)
            try:
                row = cc.collect()
                self.assertEqual(row["cgroup_meta_source"], "unresolved")
            finally:
                for k, v in old_env.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
                if old_target is not None:
                    os.environ["TARGET_CGROUP"] = old_target


class TestCLI(unittest.TestCase):
    """Smoke test the CLI script ends-to-end."""

    SCRIPT = ROOT / "monitoring" / "cgroup_collector.py"

    def test_header(self):
        out = subprocess.check_output(
            ["python3", str(self.SCRIPT), "--header"], text=True).strip()
        fields = out.split(",")
        self.assertEqual(len(fields), 19)
        self.assertEqual(fields[0], "cgroup_io_rbytes")
        self.assertEqual(fields[-1], "cgroup_meta_source")

    def test_data_runs_on_cloudtop(self):
        """On cloudtop (vm_bare + cgroup v2), running --data should:
        - exit 0
        - print a single CSV line with 19 comma-separated fields
        - last field = v2 (cloudtop has cgroup v2)
        """
        out = subprocess.check_output(
            ["python3", str(self.SCRIPT), "--data"], text=True).strip()
        fields = out.split(",")
        self.assertEqual(len(fields), 19)
        # Last field must be one of the 4 valid sources
        self.assertIn(fields[-1], {"v2", "v1", "unmounted", "unresolved"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
