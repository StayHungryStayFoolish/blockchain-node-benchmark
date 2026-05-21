#!/usr/bin/env python3
"""Unit test guards for cgroup_collector v1.4.4 bug fixes.

Bug #1 (v2 swap key): collect_v2() previously read mem.get("swapcached", 0)
  but cgroup v2 memory.stat key is "swap" (current swap in bytes).
  "swapcached" is swap-backed page cache — a different metric.

Bug #2 (explicit v1 sub-path population): collect() top-level dispatcher
  nested the v1 sub-path population (BLKIO/MEMORY/CPU) inside the `if cg_ver
  in ("auto",...)` branch. When a user explicitly set CGROUP_VERSION=v1 with
  empty CGROUP_V1_*_PATH, the population block was skipped and IO/MEM/CPU
  all returned 0.

Run: python3 tests/test_cgroup_collector_v144_fixes.py
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from monitoring import cgroup_collector  # noqa: E402


class TestV2SwapKey(unittest.TestCase):
    """Bug #1: cgroup v2 swap accounting must read `swap`, not `swapcached`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_memory_stat(self, content):
        (self.root / "memory.stat").write_text(content)
        # Required files for collect_v2 — empty is fine
        (self.root / "io.stat").write_text("")
        (self.root / "cpu.stat").write_text("")

    def test_v2_reads_swap_not_swapcached(self):
        """When memory.stat has both `swap` and `swapcached`, prefer `swap`."""
        self._write_memory_stat(
            "anon 1000\n"
            "file 2000\n"
            "swap 5555\n"          # this is what we want
            "swapcached 99999\n"   # this is a red herring
        )
        out = cgroup_collector.collect_v2(str(self.root), "")
        self.assertEqual(out["cgroup_mem_swap"], 5555,
                         "Must read `swap` key, not `swapcached`")
        self.assertNotEqual(out["cgroup_mem_swap"], 99999)

    def test_v2_swap_missing_returns_zero(self):
        """When memory.stat has no `swap` key, default to 0."""
        self._write_memory_stat("anon 1000\nfile 2000\n")
        out = cgroup_collector.collect_v2(str(self.root), "")
        self.assertEqual(out["cgroup_mem_swap"], 0)

    def test_v2_swap_only_swapcached_returns_zero(self):
        """When memory.stat has ONLY `swapcached`, must NOT fall back to it."""
        self._write_memory_stat(
            "anon 1000\nswapcached 12345\n"
        )
        out = cgroup_collector.collect_v2(str(self.root), "")
        self.assertEqual(out["cgroup_mem_swap"], 0,
                         "swapcached must NOT be used as swap fallback")


class TestExplicitV1SubPathPopulation(unittest.TestCase):
    """Bug #2: when user explicitly sets CGROUP_VERSION=v1 with empty
    CGROUP_V1_*_PATH, the top-level collect() must still populate them.
    """

    def setUp(self):
        # Save env
        self._env_bak = {}
        for k in (
            "CGROUP_VERSION", "CGROUP_ROOT",
            "CGROUP_V1_BLKIO_PATH", "CGROUP_V1_MEMORY_PATH",
            "CGROUP_V1_CPU_PATH", "HOST_SYS", "HOST_PROC",
            "TARGET_CGROUP",
        ):
            self._env_bak[k] = os.environ.pop(k, None)

        self.tmp = tempfile.TemporaryDirectory()
        self.cg_root = Path(self.tmp.name) / "cgroup"
        # Build a fake v1 hierarchy
        for ctrl in ("blkio", "memory", "cpu,cpuacct"):
            (self.cg_root / ctrl).mkdir(parents=True)
            # Empty stat files — content not relevant, only path resolution is
            for f in ("blkio.throttle.io_service_bytes",
                      "blkio.throttle.io_serviced",
                      "memory.stat", "cpu.stat",
                      "cpuacct.usage"):
                (self.cg_root / ctrl / f).write_text("")

    def tearDown(self):
        for k, v in self._env_bak.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def test_explicit_v1_populates_subpaths(self):
        """Explicit CGROUP_VERSION=v1 + empty sub-paths → must auto-populate."""
        os.environ["CGROUP_VERSION"] = "v1"
        os.environ["CGROUP_ROOT"] = str(self.cg_root)
        # Sub-paths intentionally empty — this is the bug condition
        os.environ["CGROUP_V1_BLKIO_PATH"] = ""
        os.environ["CGROUP_V1_MEMORY_PATH"] = ""
        os.environ["CGROUP_V1_CPU_PATH"] = ""
        os.environ["TARGET_CGROUP"] = ""

        # Patch get_host_paths to inject our test env (it normally reads
        # from env, but also includes other keys we don't want to mock)
        out = cgroup_collector.collect()

        # If sub-paths were populated, collect_v1 was called against real
        # (empty but existing) files → returns 0s WITHOUT meta_source=unmounted.
        # If sub-paths were NOT populated (the bug), collect_v1 reads from
        # empty paths and also returns 0s — distinguishable only by meta_source.
        self.assertEqual(out.get("cgroup_meta_source"), "v1",
                         f"Expected meta_source=v1, got {out!r}. "
                         f"This means the v1 sub-path population block was "
                         f"skipped for explicit CGROUP_VERSION=v1.")

    def test_auto_v1_still_populates_subpaths(self):
        """Regression: auto-detect path should still work (existing behavior)."""
        os.environ["CGROUP_VERSION"] = "auto"
        os.environ["CGROUP_ROOT"] = str(self.cg_root)
        # Force auto-detect to land on v1 by creating cgroup.subtree_control
        # absent (heuristic varies by impl — we just verify no crash on auto)
        os.environ["TARGET_CGROUP"] = ""

        # Just verify it doesn't crash
        out = cgroup_collector.collect()
        self.assertIn("cgroup_meta_source", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
