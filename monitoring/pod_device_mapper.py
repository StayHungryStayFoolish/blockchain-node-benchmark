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

Supported volume sources
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
    # Disk NVMe naming: nvme-Amazon_Elastic_Block_Store_vol<hexid>
    # (NVMe instances strip the dash from vol-xxx → volxxx)
    by_id = (Path(host_root) / "dev/disk/by-id"
             / f"nvme-Amazon_Elastic_Block_Store_{handle.replace('-', '')}")
    if by_id.exists():
        return _resolve_by_id(by_id), "csi"
    # Fall back: xen-virtualized older instances expose /dev/xvd*; udev does
    # not create a stable by-id link, so we just return the volumeHandle so
    # caller can try a downstream lookup against EC2 BlockDeviceMappings.
    return f"{handle}@xen", "csi"


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
    """Fallback for unrecognized CSI drivers.

    Returns ("?", "csi") with the volumeHandle preserved separately by the
    caller. We do NOT return the raw volumeHandle as `device` — that would
    pollute downstream iostat lookups, which expect bare device names like
    "sda" or "nvme0n1". Caller surfaces the handle via VolumeMapping for
    diagnostics; an unresolved generic CSI driver must be handled by adding
    a new entry to _CSI_EXTRACTORS.
    """
    return "?", "csi"


def _strip_partition_suffix(name: str) -> str:
    """Strip trailing partition number from a device name.

      sda1     → sda
      sda10    → sda
      nvme0n1p1 → nvme0n1   (NVMe uses 'p<N>' partition suffix)
      nvme0n1p15 → nvme0n1
      xvda1    → xvda
      vda1     → vda

    The "name" we care about is the WHOLE-disk device that iostat reports
    against (cgroup io.stat also reports against the whole disk). Returning
    a partition name (e.g. 'sda1') causes 0-byte counters because iostat
    never accumulates against the partition.
    """
    if not name:
        return name
    # NVMe: nvme<ctrl>n<ns>p<part> → keep up to nsX
    # Match e.g. 'nvme0n1p1' → split on 'p' before digits at end
    import re
    nvme_m = re.match(r"^(nvme\d+n\d+)p\d+$", name)
    if nvme_m:
        return nvme_m.group(1)
    # SCSI/SATA/virtio: trailing digits are partition
    scsi_m = re.match(r"^([a-z]+)\d+$", name)
    if scsi_m:
        return scsi_m.group(1)
    return name


def _resolve_by_id(by_id_path: Path) -> str:
    """Resolve /dev/disk/by-id/... symlink to a device name (e.g. 'sda').

    Strips trailing partition suffix so the result aligns with what iostat
    and cgroup io.stat report against (whole-disk device, not partition).

    Returns "?" if the link doesn't exist or can't be resolved.
    """
    if not by_id_path.exists():
        return "?"
    try:
        target = by_id_path.resolve(strict=False)
        name = target.name
        if not name:
            return "?"
        return _strip_partition_suffix(name)
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

    # Legacy AWS EBS (pre-CSI in-tree provisioner)
    # awsElasticBlockStore.volumeID format: aws://AZ/vol-xxxx or just vol-xxxx
    if "awsElasticBlockStore" in spec:
        vol_id_raw = spec["awsElasticBlockStore"].get("volumeID", "")
        # Strip aws://az/ prefix if present
        vol_id = vol_id_raw.rsplit("/", 1)[-1] if vol_id_raw else ""
        if vol_id and vol_id.startswith("vol-"):
            # Same NVMe by-id convention as ebs.csi.aws.com
            by_id = (Path(host_root) / "dev/disk/by-id"
                     / f"nvme-Amazon_Elastic_Block_Store_{vol_id.replace('-', '')}")
            if by_id.exists():
                return _resolve_by_id(by_id), "awsElasticBlockStore", vol_id_raw, ""
            # Xen-virtualized fall-through (no stable by-id link)
            return f"{vol_id}@xen", "awsElasticBlockStore", vol_id_raw, ""
        return "?", "awsElasticBlockStore", vol_id_raw, ""

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
# Kubelet mount fallback — last-resort device resolution
# ---------------------------------------------------------------------


def _resolve_via_kubelet_mounts(
    pv_name: str,
    pod_uid: str,
    host_root: str,
) -> Optional[str]:
    """Last-resort: scan /proc/mounts for the kubelet PV mount line.

    When CSI extraction fails (unknown driver, missing by-id link, xen
    instance), the volume is still mounted somewhere — kubelet mounts
    every PV under:

      <host_root>/var/lib/kubelet/pods/<pod_uid>/volumes/<plugin>/<pv_name>/mount

    or for CSI plugins:

      <host_root>/var/lib/kubelet/pods/<pod_uid>/volumes/kubernetes.io~csi/<pv_name>/mount

    /proc/mounts shows the source device for each mountpoint. We grep for
    the pv_name (or pod_uid) and extract the device.

    Returns the whole-disk device name (e.g. "nvme0n1") or None if no
    mount line is found.
    """
    if not pv_name and not pod_uid:
        return None
    mounts_path = Path(host_root) / "proc/mounts"
    if not mounts_path.is_file():
        # Try without host_root prefix (we may already be inside the host PID ns)
        mounts_path = Path("/proc/mounts")
        if not mounts_path.is_file():
            return None
    try:
        text = mounts_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    # Look for a mount line whose mountpoint contains both pod_uid and pv_name
    # (more specific than just pv_name, which could match across pods after
    # a Pod restart that re-binds the same PVC).
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        source, mountpoint, _fstype = parts[0], parts[1], parts[2]
        # Must be a /dev/ block device source — skip tmpfs, overlay, nfs etc.
        if not source.startswith("/dev/"):
            continue
        # Match by pv_name (kubelet path convention) — robust across plugins
        if pv_name and pv_name in mountpoint:
            dev_name = source.rsplit("/", 1)[-1]
            return _strip_partition_suffix(dev_name)
        if pod_uid and pod_uid in mountpoint and "/volumes/" in mountpoint:
            dev_name = source.rsplit("/", 1)[-1]
            return _strip_partition_suffix(dev_name)
    return None


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
    meta = pod.get("metadata", {})
    node = spec.get("nodeName", "?")
    pod_uid = meta.get("uid", "")
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
                # Fallback: if CSI/legacy extraction gave us "?" or a tagged
                # placeholder like "vol-xxx@xen", try /proc/mounts via pv_name
                # + pod uid. This rescues unknown CSI drivers and xen Disk.
                if device == "?" or "@" in device:
                    fallback = _resolve_via_kubelet_mounts(
                        pv_name, pod_uid, host_root,
                    )
                    if fallback:
                        device = fallback
                        if kind == "csi":
                            kind = "csi+mount-fallback"
                        else:
                            kind = f"{kind}+mount-fallback"
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
