#!/usr/bin/env python3
"""tests/test_cgroup_kubelet_stats_fallback.py

Proves cgroup_collector.py picks up kubelet_stats_client
when DEPLOYMENT_MODE=k8s and local cgroup fs is unavailable.

Mocks the K8sApiClient HTTP call with a stub /stats/summary JSON, no real
apiserver required.
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

# Add monitoring/ to sys.path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "monitoring"))


# Minimal kubelet /stats/summary stub
STUB_STATS_SUMMARY = {
    "node": {"nodeName": "gke-test-node-1"},
    "pods": [
        {
            "podRef": {
                "name": "geth-bench-0",
                "namespace": "blockchain-bench",
                "uid": "abc-123",
            },
            "cpu": {
                "time": "2026-05-21T19:00:00Z",
                "usageNanoCores": 12345678,
                "usageCoreNanoSeconds": 987654321,
            },
            "memory": {
                "time": "2026-05-21T19:00:00Z",
                "workingSetBytes": 1234567890,
                "rssBytes": 1000000000,
                "pageFaults": 12345,
                "majorPageFaults": 1,
            },
            "network": {
                "time": "2026-05-21T19:00:00Z",
                "rxBytes": 1234567,
                "txBytes": 7654321,
                "rxErrors": 0,
                "txErrors": 0,
            },
            "volume": [],
        }
    ],
}


class CgroupModeETestCase(unittest.TestCase):

    def setUp(self):
        # Import fresh each test to pick up env changes
        if "cgroup_collector" in sys.modules:
            del sys.modules["cgroup_collector"]
        if "kubelet_stats_client" in sys.modules:
            del sys.modules["kubelet_stats_client"]
        if "k8s_api_client" in sys.modules:
            del sys.modules["k8s_api_client"]

    def test_mode_e_skipped_when_not_k8s(self):
        """No DEPLOYMENT_MODE → Mode E returns None."""
        from cgroup_collector import _try_k8s_kubelet_fallback
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEPLOYMENT_MODE", None)
            self.assertIsNone(_try_k8s_kubelet_fallback("unmounted"))

    def test_mode_e_skipped_when_no_pod_env(self):
        """DEPLOYMENT_MODE=k8s but no POD_NAME → Mode E returns None."""
        from cgroup_collector import _try_k8s_kubelet_fallback
        env = {"DEPLOYMENT_MODE": "k8s"}
        with mock.patch.dict(os.environ, env, clear=False):
            for k in ("POD_NAME", "POD_NAMESPACE", "NODE_NAME"):
                os.environ.pop(k, None)
            self.assertIsNone(_try_k8s_kubelet_fallback("unmounted"))

    def test_mode_e_returns_19_fields_when_k8s_ready(self):
        """Mocked kubelet returns stats → Mode E produces 19-field dict."""
        from cgroup_collector import (
            _try_k8s_kubelet_fallback,
            IO_FIELDS,
            MEM_FIELDS,
            CPU_FIELDS,
        )
        import kubelet_stats_client

        env = {
            "DEPLOYMENT_MODE": "k8s",
            "POD_NAME": "geth-bench-0",
            "POD_NAMESPACE": "blockchain-bench",
            "NODE_NAME": "gke-test-node-1",
        }
        # Patch KubeletStatsClient.pod_on_node to return our stub-parsed Pod
        stub_pod = kubelet_stats_client._parse_pod(
            STUB_STATS_SUMMARY["pods"][0], "gke-test-node-1"
        )
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(
                 kubelet_stats_client.KubeletStatsClient,
                 "pod_on_node",
                 return_value=stub_pod,
             ):
            result = _try_k8s_kubelet_fallback("unmounted")

        self.assertIsNotNone(result, "Mode E should activate")
        # 19 fields
        expected_n = len(IO_FIELDS) + len(MEM_FIELDS) + len(CPU_FIELDS) + 1
        self.assertEqual(len(result), expected_n,
                         f"Expected {expected_n} fields, got {len(result)}")
        # meta_source explicit
        self.assertEqual(result["cgroup_meta_source"], "k8s_fallback:unmounted")
        # Mem populated from kubelet
        self.assertEqual(result["cgroup_mem_anon"], 1000000000)
        # file = workingSet - rss
        self.assertEqual(result["cgroup_mem_file"], 234567890)
        # CPU converted nanosec → usec
        self.assertEqual(result["cgroup_cpu_usage_usec"], 987654)
        # IO stays 0 (kubelet stats summary doesn't expose cgroup io_stat)
        for f in IO_FIELDS:
            self.assertEqual(result[f], 0, f"{f} should be 0 in K8s fallback")

    def test_mode_e_silent_on_kubelet_error(self):
        """Kubelet call raises → Mode E returns None (does not crash)."""
        from cgroup_collector import _try_k8s_kubelet_fallback
        import kubelet_stats_client

        env = {
            "DEPLOYMENT_MODE": "k8s",
            "POD_NAME": "geth-bench-0",
            "POD_NAMESPACE": "blockchain-bench",
            "NODE_NAME": "gke-test-node-1",
        }
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(
                 kubelet_stats_client.KubeletStatsClient,
                 "pod_on_node",
                 side_effect=RuntimeError("apiserver down"),
             ):
            self.assertIsNone(_try_k8s_kubelet_fallback("unresolved"))

    def test_mode_e_silent_on_no_such_pod(self):
        """pod_on_node returns None → Mode E returns None."""
        from cgroup_collector import _try_k8s_kubelet_fallback
        import kubelet_stats_client

        env = {
            "DEPLOYMENT_MODE": "k8s",
            "POD_NAME": "missing",
            "POD_NAMESPACE": "blockchain-bench",
            "NODE_NAME": "gke-test-node-1",
        }
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(
                 kubelet_stats_client.KubeletStatsClient,
                 "pod_on_node",
                 return_value=None,
             ):
            self.assertIsNone(_try_k8s_kubelet_fallback("unmounted"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
