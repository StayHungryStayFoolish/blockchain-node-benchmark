#!/usr/bin/env python3
"""
test_s5_k8s_stack.py — unit tests for S5 K8s client stack
==========================================================

Covers (no real cluster, no PyPI deps):
  - k8s_api_client.K8sApiClient: token reading, TLS context, HTTP GET,
    error mapping, all object accessors
  - pod_device_mapper: 3-hop Pod→PVC→PV→device, 4 CSI drivers
    (GCE/Disk/Azure/generic), legacy GCE/Disk, hostPath, local,
    unbound PVC, missing PV
  - kubelet_stats_client: stats summary parsing, defensive accessors,
    CSV header + row stability

All tests use a stdlib http.server fake apiserver — zero PyPI deps,
zero kind/docker requirement (matches §S5 acceptance: cloudtop-runnable).

Run: python3 tests/test_s5_k8s_stack.py
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Make the monitoring/ modules importable
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "monitoring"))

from k8s_api_client import K8sApiClient, K8sApiError  # noqa: E402
from pod_device_mapper import (  # noqa: E402
    PodMapping, VolumeMapping, map_pod_volumes, map_namespace_pods,
    _extract_gce_csi, _extract_ebs_csi, _extract_azure_csi,
    _extract_generic_csi, _resolve_pv_device,
)
from kubelet_stats_client import (  # noqa: E402
    KubeletStatsClient, PodStats, VolumeStats,
    pod_stats_header, pod_stats_row, POD_STATS_FIELDS,
    _int_or_zero, _str_or_empty, _parse_pod, _parse_volume,
)


# =====================================================================
# Fake apiserver — programmable per-path JSON responses
# =====================================================================

class _FakeApiserverHandler(BaseHTTPRequestHandler):
    """Serves preset responses from server.routes dict."""

    def log_message(self, format, *args):  # silence
        pass

    def do_GET(self):
        routes = getattr(self.server, "routes", {})
        if self.path not in routes:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"kind":"Status","status":"Failure","code":404}')
            return
        status, body = routes[self.path]
        if isinstance(body, dict):
            body_bytes = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body_bytes = body.encode("utf-8")
        else:
            body_bytes = body
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)


def _start_fake_server(routes: dict) -> tuple:
    """Start the fake apiserver on a random port. Returns (server, thread, url)."""
    # Bind to localhost, port 0 → kernel picks free port
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    server = HTTPServer(("127.0.0.1", port), _FakeApiserverHandler)
    server.routes = routes
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{port}"


# =====================================================================
# K8sApiClient tests
# =====================================================================

class TestK8sApiClient(unittest.TestCase):

    def setUp(self):
        self.routes = {}
        self.server, self.thread, self.url = _start_fake_server(self.routes)
        self.client = K8sApiClient(
            api_server=self.url,
            token="test-token-abc",
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    # ---- happy path ----

    def test_list_namespaced_pods_returns_items(self):
        self.routes["/api/v1/namespaces/default/pods"] = (200, {
            "items": [{"metadata": {"name": "pod-a"}}]
        })
        result = self.client.list_namespaced_pods("default")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["metadata"]["name"], "pod-a")

    def test_get_pod_single_object(self):
        self.routes["/api/v1/namespaces/ns1/pods/p1"] = (200, {
            "metadata": {"name": "p1"}, "spec": {"nodeName": "n1"}
        })
        pod = self.client.get_pod("ns1", "p1")
        self.assertEqual(pod["spec"]["nodeName"], "n1")

    def test_get_pvc(self):
        self.routes["/api/v1/namespaces/ns1/persistentvolumeclaims/pvc1"] = (200, {
            "spec": {"volumeName": "pv-xyz"}
        })
        pvc = self.client.get_pvc("ns1", "pvc1")
        self.assertEqual(pvc["spec"]["volumeName"], "pv-xyz")

    def test_get_pv(self):
        self.routes["/api/v1/persistentvolumes/pv-xyz"] = (200, {
            "spec": {"csi": {"driver": "pd.csi.storage.gke.io"}}
        })
        pv = self.client.get_pv("pv-xyz")
        self.assertEqual(pv["spec"]["csi"]["driver"], "pd.csi.storage.gke.io")

    def test_kubelet_stats_summary_routes_through_proxy(self):
        self.routes["/api/v1/nodes/gke-1/proxy/stats/summary"] = (200, {
            "node": {"nodeName": "gke-1"}, "pods": []
        })
        s = self.client.kubelet_stats_summary("gke-1")
        self.assertEqual(s["node"]["nodeName"], "gke-1")

    # ---- error paths ----

    def test_404_raises_k8s_api_error(self):
        with self.assertRaises(K8sApiError) as ctx:
            self.client.get_pod("ns", "missing")
        self.assertEqual(ctx.exception.status, 404)

    def test_connection_refused_raises_network_error(self):
        # Bogus port, nothing listening
        bad_client = K8sApiClient(api_server="http://127.0.0.1:1", token="x")
        with self.assertRaises(K8sApiError) as ctx:
            bad_client.get_pod("ns", "p")
        self.assertEqual(ctx.exception.status, 0)  # network error

    # ---- auth + config ----

    def test_token_from_env(self):
        os.environ["K8S_TOKEN"] = "env-token-zzz"
        try:
            c = K8sApiClient(api_server=self.url)
            # v1.4.4: token storage refactored to lazy reread (rotation-safe).
            # Public accessor is _current_token().
            self.assertEqual(c._current_token(), "env-token-zzz")
        finally:
            del os.environ["K8S_TOKEN"]

    def test_token_from_file(self, tmp=None):
        import tempfile
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("file-token-yyy\n")
            path = f.name
        try:
            c = K8sApiClient(api_server=self.url, token_file=path)
            self.assertEqual(c._current_token(), "file-token-yyy")
        finally:
            os.unlink(path)

    def test_missing_token_file_returns_empty(self):
        c = K8sApiClient(api_server=self.url, token_file="/nonexistent/file")
        self.assertEqual(c._current_token(), "")


# =====================================================================
# pod_device_mapper tests
# =====================================================================

class TestCSIExtractors(unittest.TestCase):
    """Pure-function extractors — no HTTP needed."""

    def test_gce_csi_volume_handle_parsed(self):
        spec = {"csi": {
            "driver": "pd.csi.storage.gke.io",
            "volumeHandle": "projects/p/zones/us-central1-a/disks/my-disk",
        }}
        # by-id path won't exist on test host → "?" but kind=csi
        dev, kind = _extract_gce_csi(spec, "/nonexistent-host-root")
        self.assertEqual(kind, "csi")
        self.assertEqual(dev, "?")  # missing on test box

    def test_ebs_csi_handle_extracted(self):
        spec = {"csi": {
            "driver": "ebs.csi.aws.com",
            "volumeHandle": "vol-0abc123def456",
        }}
        dev, kind = _extract_ebs_csi(spec, "/nonexistent")
        self.assertEqual(kind, "csi")

    def test_azure_csi_handle_extracted(self):
        spec = {"csi": {
            "driver": "disk.csi.azure.com",
            "volumeHandle": "/subscriptions/SID/.../disks/my-azure-disk",
        }}
        dev, kind = _extract_azure_csi(spec, "/nonexistent")
        self.assertEqual(kind, "csi")

    def test_generic_csi_falls_back_to_volume_handle(self):
        """v1.4.4 behavior change: generic CSI returns "?" (not raw handle).

        Old behavior leaked the volumeHandle as `device`, which polluted
        downstream iostat lookups (handles like "vol-xxx" or
        "projects/.../disks/X" are NOT block-device names). The volumeHandle
        is preserved separately on the VolumeMapping for diagnostics; an
        unrecognized CSI driver must be added to _CSI_EXTRACTORS to actually
        resolve it. See pod_device_mapper.py docstring on _extract_generic_csi.
        """
        spec = {"csi": {
            "driver": "unknown.csi.example.com",
            "volumeHandle": "opaque-handle-string",
        }}
        dev, kind = _extract_generic_csi(spec, "/nonexistent")
        self.assertEqual(dev, "?")
        self.assertEqual(kind, "csi")

    def test_generic_csi_empty_handle_returns_question(self):
        dev, kind = _extract_generic_csi({"csi": {}}, "/nonexistent")
        self.assertEqual(dev, "?")

    def test_resolve_pv_device_dispatches_on_source(self):
        # hostPath
        pv = {"spec": {"hostPath": {"path": "/var/lib/data"}}}
        dev, kind, handle, driver = _resolve_pv_device(pv, "/nonexistent")
        self.assertEqual(dev, "/var/lib/data")
        self.assertEqual(kind, "hostPath")

        # local
        pv = {"spec": {"local": {"path": "/mnt/local-ssd"}}}
        dev, kind, _, _ = _resolve_pv_device(pv, "/nonexistent")
        self.assertEqual(dev, "/mnt/local-ssd")
        self.assertEqual(kind, "local")

        # legacy GCE
        pv = {"spec": {"gcePersistentDisk": {"pdName": "legacy-disk"}}}
        _, kind, handle, _ = _resolve_pv_device(pv, "/nonexistent")
        self.assertEqual(kind, "gcePersistentDisk")
        self.assertEqual(handle, "legacy-disk")

        # legacy Disk
        pv = {"spec": {"awsElasticBlockStore": {"volumeID": "vol-xxx"}}}
        _, kind, handle, _ = _resolve_pv_device(pv, "/nonexistent")
        self.assertEqual(kind, "awsElasticBlockStore")
        self.assertEqual(handle, "vol-xxx")

        # unknown
        pv = {"spec": {"weirdVolume": {}}}
        dev, kind, _, _ = _resolve_pv_device(pv, "/nonexistent")
        self.assertEqual(kind, "unknown")


class TestPodVolumeMapping(unittest.TestCase):
    """Full 3-hop chain via fake apiserver."""

    def setUp(self):
        self.routes = {}
        self.server, self.thread, self.url = _start_fake_server(self.routes)
        self.client = K8sApiClient(api_server=self.url, token="tok")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_pvc_backed_pod_full_chain(self):
        # Pod with one PVC volume
        self.routes["/api/v1/namespaces/bench/pods/geth-0"] = (200, {
            "metadata": {"name": "geth-0"},
            "spec": {
                "nodeName": "node-a",
                "volumes": [
                    {"name": "data", "persistentVolumeClaim": {"claimName": "geth-data"}}
                ],
            },
        })
        self.routes["/api/v1/namespaces/bench/persistentvolumeclaims/geth-data"] = (200, {
            "spec": {"volumeName": "pv-geth-data"}
        })
        self.routes["/api/v1/persistentvolumes/pv-geth-data"] = (200, {
            "spec": {"csi": {
                "driver": "pd.csi.storage.gke.io",
                "volumeHandle": "projects/p/zones/z/disks/d-1",
            }}
        })

        m = map_pod_volumes(self.client, "bench", "geth-0", host_root="/nonexistent")
        self.assertEqual(m.namespace, "bench")
        self.assertEqual(m.pod_name, "geth-0")
        self.assertEqual(m.node_name, "node-a")
        self.assertEqual(len(m.volumes), 1)
        v = m.volumes[0]
        self.assertEqual(v.logical_name, "data")
        self.assertEqual(v.pvc_name, "geth-data")
        self.assertEqual(v.pv_name, "pv-geth-data")
        self.assertEqual(v.csi_driver, "pd.csi.storage.gke.io")
        self.assertEqual(v.source_kind, "csi")
        # device "?" because by-id path doesn't exist on test box — that's correct
        self.assertEqual(v.device, "?")

    def test_unbound_pvc_recorded_with_warning(self):
        self.routes["/api/v1/namespaces/bench/pods/p1"] = (200, {
            "spec": {"nodeName": "n", "volumes": [
                {"name": "d", "persistentVolumeClaim": {"claimName": "unbound"}}
            ]},
        })
        # PVC exists but has no volumeName (unbound)
        self.routes["/api/v1/namespaces/bench/persistentvolumeclaims/unbound"] = (200, {
            "spec": {}
        })
        m = map_pod_volumes(self.client, "bench", "p1")
        self.assertEqual(len(m.volumes), 1)
        self.assertEqual(m.volumes[0].source_kind, "pvc_unbound")
        self.assertTrue(any("not yet bound" in w for w in m.warnings))

    def test_missing_pvc_recorded_with_warning(self):
        self.routes["/api/v1/namespaces/bench/pods/p1"] = (200, {
            "spec": {"nodeName": "n", "volumes": [
                {"name": "d", "persistentVolumeClaim": {"claimName": "gone"}}
            ]},
        })
        # PVC route NOT registered → 404 → caught as warning
        m = map_pod_volumes(self.client, "bench", "p1")
        self.assertEqual(len(m.volumes), 1)
        self.assertEqual(m.volumes[0].source_kind, "error")
        self.assertTrue(any("PVC/PV resolution failed" in w for w in m.warnings))

    def test_hostpath_inline_volume(self):
        self.routes["/api/v1/namespaces/sys/pods/agent"] = (200, {
            "spec": {"nodeName": "n", "volumes": [
                {"name": "proc", "hostPath": {"path": "/proc"}},
                {"name": "logs", "emptyDir": {}},
                {"name": "cfg",  "configMap": {"name": "c"}},
            ]},
        })
        m = map_pod_volumes(self.client, "sys", "agent")
        self.assertEqual(len(m.volumes), 3)
        kinds = {v.source_kind for v in m.volumes}
        self.assertIn("hostPath", kinds)
        self.assertIn("emptyDir", kinds)
        self.assertIn("configMap", kinds)

    def test_pod_without_volumes_returns_empty_list(self):
        self.routes["/api/v1/namespaces/ns/pods/bare"] = (200, {
            "spec": {"nodeName": "n"}
        })
        m = map_pod_volumes(self.client, "ns", "bare")
        self.assertEqual(m.volumes, [])
        self.assertEqual(m.warnings, [])

    def test_pod_fetch_failure_returns_mapping_with_warning(self):
        # No route → 404
        m = map_pod_volumes(self.client, "ns", "missing")
        self.assertEqual(m.node_name, "?")
        self.assertTrue(any("failed to fetch Pod" in w for w in m.warnings))

    def test_namespace_walk_iterates_all_pods(self):
        self.routes["/api/v1/namespaces/bench/pods"] = (200, {
            "items": [
                {"metadata": {"name": "p1"}, "spec": {"nodeName": "n1", "volumes": []}},
                {"metadata": {"name": "p2"}, "spec": {"nodeName": "n2", "volumes": []}},
            ]
        })
        # Pre-register get_pod for each
        self.routes["/api/v1/namespaces/bench/pods/p1"] = (200, {
            "spec": {"nodeName": "n1", "volumes": []}
        })
        self.routes["/api/v1/namespaces/bench/pods/p2"] = (200, {
            "spec": {"nodeName": "n2", "volumes": []}
        })
        ms = map_namespace_pods(self.client, "bench")
        self.assertEqual(len(ms), 2)
        names = {m.pod_name for m in ms}
        self.assertEqual(names, {"p1", "p2"})


# =====================================================================
# kubelet_stats_client tests
# =====================================================================

class TestDefensiveAccessors(unittest.TestCase):

    def test_int_or_zero_handles_none(self):
        self.assertEqual(_int_or_zero(None, "x"), 0)
        self.assertEqual(_int_or_zero({}, "x"), 0)
        self.assertEqual(_int_or_zero({"x": None}, "x"), 0)
        self.assertEqual(_int_or_zero({"x": "abc"}, "x"), 0)
        self.assertEqual(_int_or_zero({"x": 42}, "x"), 42)
        self.assertEqual(_int_or_zero({"x": "42"}, "x"), 42)

    def test_str_or_empty_handles_none(self):
        self.assertEqual(_str_or_empty(None, "x"), "")
        self.assertEqual(_str_or_empty({}, "x"), "")
        self.assertEqual(_str_or_empty({"x": None}, "x"), "")
        self.assertEqual(_str_or_empty({"x": "v"}, "x"), "v")
        self.assertEqual(_str_or_empty({"x": 7}, "x"), "7")

    def test_parse_volume_with_pvc_ref(self):
        v = _parse_volume({
            "name": "data",
            "pvcRef": {"name": "geth-data", "namespace": "bench"},
            "usedBytes": 12345,
            "capacityBytes": 99999,
            "availableBytes": 87654,
            "inodesUsed": 100,
            "inodesFree": 9900,
        })
        self.assertEqual(v.name, "data")
        self.assertEqual(v.pvc_name, "geth-data")
        self.assertEqual(v.used_bytes, 12345)
        self.assertEqual(v.capacity_bytes, 99999)

    def test_parse_volume_without_pvc_ref(self):
        v = _parse_volume({"name": "logs", "usedBytes": 1000})
        self.assertEqual(v.name, "logs")
        self.assertEqual(v.pvc_name, "")
        self.assertEqual(v.used_bytes, 1000)

    def test_parse_pod_full_fields(self):
        p = _parse_pod({
            "podRef": {"name": "geth-0", "namespace": "bench"},
            "cpu": {"time": "2026-05-20T10:30:00Z",
                    "usageNanoCores": 12345678,
                    "usageCoreNanoSeconds": 987654321},
            "memory": {"workingSetBytes": 1234567890,
                       "rssBytes": 1000000000,
                       "pageFaults": 12345,
                       "majorPageFaults": 1},
            "network": {"rxBytes": 1111, "txBytes": 2222,
                        "rxErrors": 0, "txErrors": 0},
            "ephemeral-storage": {"usedBytes": 98765, "capacityBytes": 1073741824},
            "volume": [
                {"name": "data", "pvcRef": {"name": "geth-data"},
                 "usedBytes": 500, "capacityBytes": 1000},
            ],
        }, node_name="gke-1")
        self.assertEqual(p.pod_name, "geth-0")
        self.assertEqual(p.namespace, "bench")
        self.assertEqual(p.node_name, "gke-1")
        self.assertEqual(p.cpu_nanocores, 12345678)
        self.assertEqual(p.mem_working_set_bytes, 1234567890)
        self.assertEqual(p.net_rx_bytes, 1111)
        self.assertEqual(p.ephemeral_storage_used_bytes, 98765)
        self.assertEqual(p.volume_count, 1)
        self.assertEqual(p.volumes[0].pvc_name, "geth-data")

    def test_parse_pod_with_missing_subobjects_defaults_zero(self):
        # No cpu/memory/network sections at all — must not crash
        p = _parse_pod({
            "podRef": {"name": "x", "namespace": "y"},
        }, node_name="n")
        self.assertEqual(p.cpu_nanocores, 0)
        self.assertEqual(p.mem_working_set_bytes, 0)
        self.assertEqual(p.net_rx_bytes, 0)
        self.assertEqual(p.volume_count, 0)


class TestKubeletStatsClient(unittest.TestCase):

    def setUp(self):
        self.routes = {}
        self.server, self.thread, self.url = _start_fake_server(self.routes)
        self.api = K8sApiClient(api_server=self.url, token="tok")
        self.client = KubeletStatsClient(self.api)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_pods_on_node_parses_full_summary(self):
        self.routes["/api/v1/nodes/gke-1/proxy/stats/summary"] = (200, {
            "pods": [
                {"podRef": {"name": "p1", "namespace": "ns"},
                 "cpu": {"usageNanoCores": 100},
                 "memory": {"workingSetBytes": 200}},
                {"podRef": {"name": "p2", "namespace": "ns"},
                 "cpu": {"usageNanoCores": 300}},
            ]
        })
        pods = self.client.pods_on_node("gke-1")
        self.assertEqual(len(pods), 2)
        self.assertEqual(pods[0].pod_name, "p1")
        self.assertEqual(pods[0].cpu_nanocores, 100)
        self.assertEqual(pods[1].cpu_nanocores, 300)

    def test_pod_on_node_filters_correctly(self):
        self.routes["/api/v1/nodes/n/proxy/stats/summary"] = (200, {
            "pods": [
                {"podRef": {"name": "a", "namespace": "ns"}},
                {"podRef": {"name": "b", "namespace": "ns"}},
            ]
        })
        result = self.client.pod_on_node("n", "ns", "b")
        self.assertIsNotNone(result)
        self.assertEqual(result.pod_name, "b")

        missing = self.client.pod_on_node("n", "ns", "nonexistent")
        self.assertIsNone(missing)

    def test_empty_summary_returns_empty_list(self):
        self.routes["/api/v1/nodes/n/proxy/stats/summary"] = (200, {"pods": []})
        self.assertEqual(self.client.pods_on_node("n"), [])

    def test_summary_without_pods_key(self):
        # kubelet has been known to return summary without 'pods' on cold start
        self.routes["/api/v1/nodes/n/proxy/stats/summary"] = (200, {"node": {}})
        self.assertEqual(self.client.pods_on_node("n"), [])


class TestCsvSchema(unittest.TestCase):
    """Schema stability — these are downstream contract tests."""

    def test_header_field_count_matches_dataclass(self):
        # All POD_STATS_FIELDS must be attributes of PodStats
        p = PodStats()
        for f in POD_STATS_FIELDS:
            self.assertTrue(hasattr(p, f), f"missing attr {f} on PodStats")

    def test_header_is_stable_csv(self):
        h = pod_stats_header()
        self.assertEqual(h.count(","), len(POD_STATS_FIELDS) - 1)
        self.assertTrue(h.startswith("timestamp,namespace,pod_name"))
        self.assertTrue(h.endswith("volume_count"))

    def test_row_matches_header_columns(self):
        p = PodStats(timestamp="2026-05-20T10:30:00Z",
                     namespace="bench", pod_name="geth-0", node_name="n1",
                     cpu_nanocores=1, mem_working_set_bytes=2)
        row = pod_stats_row(p)
        self.assertEqual(row.count(","), len(POD_STATS_FIELDS) - 1)
        self.assertTrue(row.startswith("2026-05-20T10:30:00Z,bench,geth-0,n1,1"))


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
