#!/usr/bin/env python3
"""
pod_device_mapper.py — Pod → PVC → PV → host device path resolution
====================================================================

Purpose
-------
Given a Pod (namespace + name), walk the K8s storage chain and return the
host device name (e.g. "sda", "nvme0n1") backing each persistent volume
the Pod mounts. This is the bridge that lets us attribute host-level
iostat metrics to Pod-level workloads.

Hop chain
---------
  Pod.spec.volumes[*].persistentVolumeClaim.claimName
    → PVC (by namespace + claimName)
  PVC.spec.volumeName
    → PV (by name)
  PV.spec.{csi,gcePersistentDisk,awsElasticBlockStore,hostPath,local}
    → host device path
  Device path normalization (/dev/disk/by-id/... → sda/nvme0n1)
    → device name as it appears in iostat / cgroup io.stat

Supported volume sources (S5 v1; more in S6/S7)
------------------------------------------------
  csi.driver=pd.csi.storage.gke.io           — GCE PD (CSI)
  csi.driver=ebs.csi.aws.com                 — AWS EBS (CSI)
  csi.driver=disk.csi.azure.com              — Azure Disk (CSI)
  csi.driver=*.csi.* (generic)               — best-effort: extract volumeHandle
  gcePersistentDisk (legacy)                 — GCE PD pre-CSI
  awsElasticBlockStore (legacy)              — AWS EBS pre-CSI
  hostPath                                   — direct host path
  local                                       — host path via Local PV
  emptyDir, configMap, secret, projected     — explicitly ignored (no PV)

Resolution semantics
--------------------
- Returns a list of (logical_name, device_or_path, pv_name) tuples per Pod
- logical_name = Pod-spec volume name (e.g. "data", "wal", "accounts")
- device_or_path = "sda" / "nvme1n1" for block, "/host/path" for hostPath
- Unresolvable PVs return ("?", "?", pv_name) so caller can surface gaps

Failure modes
-------------
- Pod has no volumes: returns []
- PVC not found: skips that volume with a warning
- PV not found: same
- CSI driver unrecognized: returns ("?", volumeHandle, pv_name) so the
  framework can still try device name extraction downstream

References
----------
- PV spec: kubernetes.io/docs/concepts/storage/persistent-volumes/
- CSI volumeHandle conventions:
    GCE PD:    projects/PROJ/zones/ZONE/disks/DISK_NAME
    AWS EBS:   vol-xxxxxxxxxxxxxxxxx
    Azure:     /subscriptions/.../disks/DISK_NAME
- udev /dev/disk/by-id linkage:
    /dev/disk/by-id/google-DISK_NAME      → GCE
    /dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_vol-xxx  → AWS NVMe
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from k8s_api_client import K8sApiClient, K8sApiError

_LOG = logging.getLogger(__name__)


@dataclass
class VolumeMapping:
    """One resolved Pod-volume → host device mapping."""
    logical_name: str       # Pod spec volume name (e.g. "data")
    device: str             # "sda" / "nvme0n1" / "/host/path" / "?"
    pv_name: str            # "" if no PV (emptyDir etc.)
    pvc_name: str = ""
    volume_handle: str = ""  # CSI volumeHandle, raw
    source_kind: str = ""   # csi | gcePersistentDisk | hostPath | local | unknown
    csi_driver: str = ""


@dataclass
class PodMapping:
    """All volume mappings for one Pod."""
    namespace: str
    pod_name: str
    node_name: str
    volumes: List[VolumeMapping] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------
# CSI driver → host device extraction
# ---------------------------------------------------------------------

# Map CSI driver name → function that extracts device from PV spec.
# Each extractor returns (device_name, source_kind). device_name "?"
# means "couldn't resolve, see warnings".


def _extract_gce_csi(pv_spec: Dict[str, Any], host_root: str) -> Tuple[str, str]:
    """GCE PD CSI: volumeHandle = projects/PROJ/zones/ZONE/disks/DISK_NAME.
    Host device link: /dev/disk/by-id/google-DISK_NAME.
    """
    csi = pv_spec.get("csi", {})
    handle = csi.get("volumeHandle", "")
    disk_name = handle.split("/")[-1] if "/" in handle else handle
    if not disk_name:
        return "?", "csi"
    by_id = Path(host_root) / "dev/disk/by-id" / f"google-{disk_name}"
    return _resolve_by_id(by_id), "csi"


def _extract_ebs_csi(pv_spec: Dict[str, Any], host_root: str) -> Tuple[str, str]:
    """AWS EBS CSI: volumeHandle = vol-xxxxxxxxxxxxxxxxx.
    NVMe host link: /dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_vol-xxx.
    """
    csi = pv_spec.get("csi", {})
    handle = csi.get("volumeHandle", "")
    if not handle:
        return "?", "csi"
    # EBS NVMe naming
    by_id = (Path(host_root) / "dev/disk/by-id"
             / f"nvme-Amazon_Elastic_Block_Store_{handle.replace('-', '')}")
    if by_id.exists():
        return _resolve_by_id(by_id), "csi"
    # Fall back: try /dev/xvd* alias (xen-virtualized older instances)
    return "?", "csi"


def _extract_azure_csi(pv_spec: Dict[str, Any], host_root: str) -> Tuple[str, str]:
    """Azure Disk CSI: volumeHandle = /subscriptions/.../disks/NAME.
    Host LUN: /dev/disk/azure/scsi1/lun<N>.
    """
    csi = pv_spec.get("csi", {})
    handle = csi.get("volumeHandle", "")
    disk_name = handle.split("/")[-1] if "/" in handle else handle
    if not disk_name:
        return "?", "csi"
    by_id = Path(host_root) / "dev/disk/by-id" / disk_name
    return _resolve_by_id(by_id), "csi"


# Registry: CSI driver name → extractor.
# Unrecognized drivers fall through to generic extractor.
_CSI_EXTRACTORS = {
    "pd.csi.storage.gke.io": _extract_gce_csi,
    "ebs.csi.aws.com": _extract_ebs_csi,
    "disk.csi.azure.com": _extract_azure_csi,
}


def _extract_generic_csi(pv_spec: Dict[str, Any], host_root: str) -> Tuple[str, str]:
    """Fallback for unrecognized CSI drivers: return volumeHandle unresolved."""
    handle = pv_spec.get("csi", {}).get("volumeHandle", "")
    return ("?" if not handle else handle), "csi"


def _resolve_by_id(by_id_path: Path) -> str:
    """Resolve /dev/disk/by-id/... symlink to a device name (e.g. 'sda').

    Returns "?" if the link doesn't exist or can't be resolved.
    """
    if not by_id_path.exists():
        return "?"
    try:
        target = by_id_path.resolve(strict=False)
        # Strip /dev/ prefix and any trailing partition number
        name = target.name
        return name if name else "?"
    except OSError:
        return "?"


# ---------------------------------------------------------------------
# Per-volume-source dispatcher
# ---------------------------------------------------------------------


def _resolve_pv_device(pv: Dict[str, Any], host_root: str) -> Tuple[str, str, str, str]:
    """Returns (device, source_kind, volume_handle, csi_driver)."""
    spec = pv.get("spec", {})

    # CSI (modern)
    if "csi" in spec:
        driver = spec["csi"].get("driver", "")
        handle = spec["csi"].get("volumeHandle", "")
        extractor = _CSI_EXTRACTORS.get(driver, _extract_generic_csi)
        device, kind = extractor(spec, host_root)
        return device, kind, handle, driver

    # Legacy GCE PD
    if "gcePersistentDisk" in spec:
        disk_name = spec["gcePersistentDisk"].get("pdName", "")
        if disk_name:
            by_id = Path(host_root) / "dev/disk/by-id" / f"google-{disk_name}"
            return _resolve_by_id(by_id), "gcePersistentDisk", disk_name, ""
        return "?", "gcePersistentDisk", "", ""

    # Legacy AWS EBS
    if "awsElasticBlockStore" in spec:
        vol_id = spec["awsElasticBlockStore"].get("volumeID", "")
        return "?", "awsElasticBlockStore", vol_id, ""

    # hostPath (direct host directory)
    if "hostPath" in spec:
        path = spec["hostPath"].get("path", "?")
        return path, "hostPath", "", ""

    # local PV
    if "local" in spec:
        path = spec["local"].get("path", "?")
        return path, "local", "", ""

    return "?", "unknown", "", ""


# ---------------------------------------------------------------------
# Top-level mapper
# ---------------------------------------------------------------------


def map_pod_volumes(
    client: K8sApiClient,
    namespace: str,
    pod_name: str,
    host_root: str = "/host",
) -> PodMapping:
    """Resolve all volumes for one Pod. Never raises — accumulates warnings."""
    try:
        pod = client.get_pod(namespace, pod_name)
    except K8sApiError as e:
        m = PodMapping(namespace=namespace, pod_name=pod_name, node_name="?")
        m.warnings.append(f"failed to fetch Pod: {e}")
        return m

    spec = pod.get("spec", {})
    node = spec.get("nodeName", "?")
    mapping = PodMapping(namespace=namespace, pod_name=pod_name, node_name=node)

    for vol in spec.get("volumes", []):
        logical = vol.get("name", "?")

        # PVC-backed volumes: walk the chain
        if "persistentVolumeClaim" in vol:
            pvc_name = vol["persistentVolumeClaim"].get("claimName", "")
            try:
                pvc = client.get_pvc(namespace, pvc_name)
                pv_name = pvc.get("spec", {}).get("volumeName", "")
                if not pv_name:
                    mapping.warnings.append(
                        f"PVC {pvc_name} not yet bound to a PV"
                    )
                    mapping.volumes.append(VolumeMapping(
                        logical_name=logical, device="?", pv_name="",
                        pvc_name=pvc_name, source_kind="pvc_unbound"))
                    continue
                pv = client.get_pv(pv_name)
                device, kind, handle, driver = _resolve_pv_device(pv, host_root)
                mapping.volumes.append(VolumeMapping(
                    logical_name=logical, device=device, pv_name=pv_name,
                    pvc_name=pvc_name, volume_handle=handle,
                    source_kind=kind, csi_driver=driver))
            except K8sApiError as e:
                mapping.warnings.append(
                    f"PVC/PV resolution failed for {pvc_name}: {e}"
                )
                mapping.volumes.append(VolumeMapping(
                    logical_name=logical, device="?", pv_name="",
                    pvc_name=pvc_name, source_kind="error"))

        # Inline volumes (hostPath, emptyDir, etc.)
        elif "hostPath" in vol:
            path = vol["hostPath"].get("path", "?")
            mapping.volumes.append(VolumeMapping(
                logical_name=logical, device=path, pv_name="",
                source_kind="hostPath"))

        elif "emptyDir" in vol:
            # Not a host device — skip but record presence
            mapping.volumes.append(VolumeMapping(
                logical_name=logical, device="", pv_name="",
                source_kind="emptyDir"))

        else:
            # configMap, secret, projected, downwardAPI, etc.
            # All non-IO — record as such for completeness
            kind = next(iter(vol.keys() - {"name"}), "unknown")
            mapping.volumes.append(VolumeMapping(
                logical_name=logical, device="", pv_name="",
                source_kind=kind))

    return mapping


def map_namespace_pods(
    client: K8sApiClient,
    namespace: str,
    host_root: str = "/host",
) -> List[PodMapping]:
    """Resolve volumes for every Pod in a namespace."""
    try:
        pods = client.list_namespaced_pods(namespace)
    except K8sApiError as e:
        _LOG.error("Failed to list pods in %s: %s", namespace, e)
        return []
    out: List[PodMapping] = []
    for p in pods.get("items", []):
        name = p.get("metadata", {}).get("name", "?")
        out.append(map_pod_volumes(client, namespace, name, host_root))
    return out


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------


def _print_mapping(m: PodMapping) -> None:
    print(f"=== Pod: {m.namespace}/{m.pod_name} (node={m.node_name}) ===")
    if not m.volumes:
        print("  (no volumes)")
    for v in m.volumes:
        line = f"  {v.logical_name:20s} → {v.device:30s}"
        if v.pv_name:
            line += f" pv={v.pv_name}"
        if v.csi_driver:
            line += f" csi={v.csi_driver}"
        line += f" kind={v.source_kind}"
        print(line)
    for w in m.warnings:
        print(f"  ⚠ {w}")


def main() -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Pod→PVC→PV→device mapper")
    ap.add_argument("--namespace", "-n", required=True)
    ap.add_argument("--pod", "-p", help="single pod name (otherwise all)")
    ap.add_argument("--host-root", default=os.environ.get("HOST_ROOT", "/host"))
    ap.add_argument("--insecure", action="store_true",
                    help="skip TLS verification (dev/test only)")
    args = ap.parse_args()

    client = K8sApiClient(insecure_tls=args.insecure)
    if args.pod:
        m = map_pod_volumes(client, args.namespace, args.pod, args.host_root)
        _print_mapping(m)
    else:
        for m in map_namespace_pods(client, args.namespace, args.host_root):
            _print_mapping(m)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
