#!/usr/bin/env python3
"""
kubelet_stats_client.py — kubelet /stats/summary fetch + parse
================================================================

Purpose
-------
Fetch the kubelet `/stats/summary` JSON for a node (via apiserver proxy,
so we only need nodes/proxy RBAC, not direct :10250 access) and flatten
it into per-Pod resource snapshots that align with our CSV schema.

Why apiserver proxy (not direct :10250)
---------------------------------------
- Direct :10250 needs node IP discovery + kubelet serving cert trust +
  per-node auth tokens. That's 3 extra failure modes.
- Apiserver proxy needs only the existing ServiceAccount token + RBAC
  verb `get` on `nodes/proxy`. One credential, one TLS context.
- Trade-off: ~5-10 ms extra latency per call. Negligible for our 1s
  collection interval.

Output schema
-------------
Per-Pod snapshot dict (one per Pod present in /stats/summary):
    {
      "timestamp":     "2026-05-20T10:30:00Z",   # from /stats/summary
      "namespace":     "blockchain-bench",
      "pod_name":      "geth-node-0",
      "node_name":     "gke-node-1",
      "cpu_nanocores":            12345678,       # current rate (nanocores)
      "cpu_usage_core_nanosec":   987654321,      # cumulative
      "mem_working_set_bytes":    1234567890,     # used (excl. cached)
      "mem_rss_bytes":            1000000000,
      "mem_page_faults":          12345,
      "mem_major_page_faults":    1,
      "net_rx_bytes":             1234567,        # aggregated across veth
      "net_tx_bytes":             7654321,
      "net_rx_errors":            0,
      "net_tx_errors":            0,
      "ephemeral_storage_used_bytes":  98765,
      "ephemeral_storage_capacity_bytes": 1073741824,
      "volume_count":             3,              # PVCs reported by kubelet
      "volumes":                  [...]           # list of per-volume dicts
    }

Reference shape (truncated):
https://github.com/kubernetes/kubernetes/blob/master/pkg/kubelet/apis/stats/v1alpha1/types.go

Failure modes
-------------
- Node not found / not authorized: raises K8sApiError (caller catches)
- Stats summary fetch ok but Pod has incomplete data: missing fields
  default to 0 (kubelet returns sparse JSON for some Pods)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from k8s_api_client import K8sApiClient, K8sApiError

_LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Defensive accessors
# ---------------------------------------------------------------------

def _int_or_zero(d: Optional[Dict[str, Any]], key: str) -> int:
    """Return d[key] as int if present and non-None, else 0."""
    if not d:
        return 0
    v = d.get(key)
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _str_or_empty(d: Optional[Dict[str, Any]], key: str) -> str:
    if not d:
        return ""
    v = d.get(key)
    return str(v) if v is not None else ""


# ---------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------

@dataclass
class VolumeStats:
    name: str = ""
    pvc_name: str = ""
    used_bytes: int = 0
    capacity_bytes: int = 0
    available_bytes: int = 0
    inodes_used: int = 0
    inodes_free: int = 0


@dataclass
class PodStats:
    timestamp: str = ""
    namespace: str = ""
    pod_name: str = ""
    node_name: str = ""
    cpu_nanocores: int = 0
    cpu_usage_core_nanosec: int = 0
    mem_working_set_bytes: int = 0
    mem_rss_bytes: int = 0
    mem_page_faults: int = 0
    mem_major_page_faults: int = 0
    net_rx_bytes: int = 0
    net_tx_bytes: int = 0
    net_rx_errors: int = 0
    net_tx_errors: int = 0
    ephemeral_storage_used_bytes: int = 0
    ephemeral_storage_capacity_bytes: int = 0
    volume_count: int = 0
    volumes: List[VolumeStats] = field(default_factory=list)


def _parse_volume(v: Dict[str, Any]) -> VolumeStats:
    pvc_ref = v.get("pvcRef") or {}
    return VolumeStats(
        name=_str_or_empty(v, "name"),
        pvc_name=_str_or_empty(pvc_ref, "name"),
        used_bytes=_int_or_zero(v, "usedBytes"),
        capacity_bytes=_int_or_zero(v, "capacityBytes"),
        available_bytes=_int_or_zero(v, "availableBytes"),
        inodes_used=_int_or_zero(v, "inodesUsed"),
        inodes_free=_int_or_zero(v, "inodesFree"),
    )


def _parse_pod(pod_json: Dict[str, Any], node_name: str) -> PodStats:
    """Convert one entry of summary['pods'][i] to a PodStats."""
    pod_ref = pod_json.get("podRef") or {}
    cpu = pod_json.get("cpu") or {}
    mem = pod_json.get("memory") or {}
    net = pod_json.get("network") or {}
    eph = pod_json.get("ephemeral-storage") or {}
    volumes_json = pod_json.get("volume") or []

    return PodStats(
        timestamp=_str_or_empty(cpu, "time") or _str_or_empty(mem, "time"),
        namespace=_str_or_empty(pod_ref, "namespace"),
        pod_name=_str_or_empty(pod_ref, "name"),
        node_name=node_name,
        cpu_nanocores=_int_or_zero(cpu, "usageNanoCores"),
        cpu_usage_core_nanosec=_int_or_zero(cpu, "usageCoreNanoSeconds"),
        mem_working_set_bytes=_int_or_zero(mem, "workingSetBytes"),
        mem_rss_bytes=_int_or_zero(mem, "rssBytes"),
        mem_page_faults=_int_or_zero(mem, "pageFaults"),
        mem_major_page_faults=_int_or_zero(mem, "majorPageFaults"),
        net_rx_bytes=_int_or_zero(net, "rxBytes"),
        net_tx_bytes=_int_or_zero(net, "txBytes"),
        net_rx_errors=_int_or_zero(net, "rxErrors"),
        net_tx_errors=_int_or_zero(net, "txErrors"),
        ephemeral_storage_used_bytes=_int_or_zero(eph, "usedBytes"),
        ephemeral_storage_capacity_bytes=_int_or_zero(eph, "capacityBytes"),
        volume_count=len(volumes_json),
        volumes=[_parse_volume(v) for v in volumes_json],
    )


# ---------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------

class KubeletStatsClient:
    """Wraps a K8sApiClient with stats-summary parsing helpers."""

    def __init__(self, api: Optional[K8sApiClient] = None):
        self.api = api or K8sApiClient()

    def fetch_node(self, node_name: str) -> Dict[str, Any]:
        """Raw /stats/summary JSON for a node (for debugging/inspection)."""
        return self.api.kubelet_stats_summary(node_name)

    def pods_on_node(self, node_name: str) -> List[PodStats]:
        """Return flattened PodStats list for all Pods on the node."""
        try:
            summary = self.api.kubelet_stats_summary(node_name)
        except K8sApiError as e:
            _LOG.error("kubelet stats summary fetch failed: %s", e)
            raise
        pods = summary.get("pods") or []
        return [_parse_pod(p, node_name) for p in pods]

    def pod_on_node(
        self,
        node_name: str,
        namespace: str,
        pod_name: str,
    ) -> Optional[PodStats]:
        """Find one specific Pod's stats on a node. Returns None if absent."""
        for p in self.pods_on_node(node_name):
            if p.namespace == namespace and p.pod_name == pod_name:
                return p
        return None


# ---------------------------------------------------------------------
# CSV-friendly flattening (matches baseline iostat_collector style)
# ---------------------------------------------------------------------

# Stable field order for CSV/header output.
POD_STATS_FIELDS = (
    "timestamp", "namespace", "pod_name", "node_name",
    "cpu_nanocores", "cpu_usage_core_nanosec",
    "mem_working_set_bytes", "mem_rss_bytes",
    "mem_page_faults", "mem_major_page_faults",
    "net_rx_bytes", "net_tx_bytes", "net_rx_errors", "net_tx_errors",
    "ephemeral_storage_used_bytes", "ephemeral_storage_capacity_bytes",
    "volume_count",
)


def pod_stats_header() -> str:
    return ",".join(POD_STATS_FIELDS)


def pod_stats_row(p: PodStats) -> str:
    return ",".join(str(getattr(p, k)) for k in POD_STATS_FIELDS)


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def main() -> int:
    import argparse
    import json as _json
    import sys

    ap = argparse.ArgumentParser(description="Kubelet /stats/summary client")
    ap.add_argument("--node", "-N", required=True)
    ap.add_argument("--namespace", "-n", help="filter by namespace")
    ap.add_argument("--format", choices=["text", "csv", "json"], default="text")
    ap.add_argument("--insecure", action="store_true")
    args = ap.parse_args()

    client = KubeletStatsClient(K8sApiClient(insecure_tls=args.insecure))
    try:
        pods = client.pods_on_node(args.node)
    except K8sApiError as e:
        print(f"❌ failed: {e}", file=sys.stderr)
        return 1

    if args.namespace:
        pods = [p for p in pods if p.namespace == args.namespace]

    if args.format == "json":
        print(_json.dumps([p.__dict__ for p in pods], default=lambda x: x.__dict__, indent=2))
    elif args.format == "csv":
        print(pod_stats_header())
        for p in pods:
            print(pod_stats_row(p))
    else:
        print(f"Pods on node {args.node}: {len(pods)}")
        for p in pods:
            print(f"  {p.namespace}/{p.pod_name:30s}  "
                  f"cpu={p.cpu_nanocores:>12}n  "
                  f"mem={p.mem_working_set_bytes:>12}B  "
                  f"net={p.net_rx_bytes:>10}/{p.net_tx_bytes:<10}B  "
                  f"vols={p.volume_count}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
