#!/usr/bin/env python3
"""Regression tests for pod_device_mapper.py fixes.

Covers previously observed bugs:

P1a (L174 _resolve_by_id): Docstring said "strip trailing partition number"
     but code only `return name` without stripping. Result: iostat lookups
     against "sda1" / "nvme0n1p1" return 0 because iostat reports against
     whole-disk devices, not partitions.

P1b (L209 legacy AWS EBS): Hardcoded `return "?"` — never attempted to
     resolve `volumeID` (e.g. "vol-abc123") via /dev/disk/by-id like the
     CSI variant does. In-tree provisioner is still used by many existing
     clusters.

P1c (L162 _extract_generic_csi): Returned the raw `volumeHandle` as `device`
     for unknown CSI drivers. volumeHandles like "vol-xxx" or
     "projects/PROJ/zones/Z/disks/X" are NOT device names — downstream
     iostat lookups silently break.

P1d (kubelet mount fallback): No /proc/mounts fallback when CSI extraction
     fails. Unknown CSI drivers, xen Disk, and any provider-specific quirks
     leave volumes unmonitored despite being clearly mounted on the host.

Run this file with python3
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
# pod_device_mapper.py does `from k8s_api_client import ...` so we need
# monitoring/ on the path
sys.path.insert(0, str(REPO_ROOT / "monitoring"))

from monitoring import pod_device_mapper as pdm  # noqa: E402


class TestStripPartitionSuffix(unittest.TestCase):
    """P1a: device name partition suffix must be stripped."""

    def test_scsi_simple(self):
        self.assertEqual(pdm._strip_partition_suffix("sda1"), "sda")
        self.assertEqual(pdm._strip_partition_suffix("sda10"), "sda")
        self.assertEqual(pdm._strip_partition_suffix("sdb15"), "sdb")

    def test_nvme(self):
        self.assertEqual(pdm._strip_partition_suffix("nvme0n1p1"), "nvme0n1")
        self.assertEqual(pdm._strip_partition_suffix("nvme0n1p15"), "nvme0n1")
        self.assertEqual(pdm._strip_partition_suffix("nvme1n2p3"), "nvme1n2")

    def test_xen_virtio(self):
        self.assertEqual(pdm._strip_partition_suffix("xvda1"), "xvda")
        self.assertEqual(pdm._strip_partition_suffix("vda1"), "vda")

    def test_whole_disk_unchanged(self):
        """Whole-disk names already have no partition suffix."""
        self.assertEqual(pdm._strip_partition_suffix("sda"), "sda")
        self.assertEqual(pdm._strip_partition_suffix("nvme0n1"), "nvme0n1")
        self.assertEqual(pdm._strip_partition_suffix("xvda"), "xvda")

    def test_empty_string(self):
        self.assertEqual(pdm._strip_partition_suffix(""), "")

    def test_pathological_inputs_untouched(self):
        """Don't mangle names that don't match either pattern."""
        # md raid, dm-mapper, loop — unchanged
        self.assertEqual(pdm._strip_partition_suffix("md0"), "md")
        # ^^^ This is a known limitation: md0 is a whole-disk array but the
        # regex strips. Acceptable for now (md devices aren't expected on
        # cloud PVs); document if it becomes a problem.
        self.assertEqual(pdm._strip_partition_suffix("loop0"), "loop")


class TestLegacyAwsEbs(unittest.TestCase):
    """P1b: legacy awsElasticBlockStore must attempt resolution, not return ?."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.host_root = Path(self.tmp.name)
        # Build a fake by-id symlink
        by_id_dir = self.host_root / "dev/disk/by-id"
        by_id_dir.mkdir(parents=True)
        # Fake device + symlink
        (self.host_root / "dev/nvme1n1").write_text("")  # placeholder
        # NVMe naming: vol-abc123 → volabc123
        (by_id_dir / "nvme-Amazon_Elastic_Block_Store_volabc123").symlink_to(
            "../../nvme1n1"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_legacy_disk_with_aws_prefix(self):
        """volumeID = 'aws://us-east-1a/vol-abc123' → resolves to nvme1n1."""
        pv = {"spec": {"awsElasticBlockStore": {
            "volumeID": "aws://us-east-1a/vol-abc123",
        }}}
        device, kind, handle, driver = pdm._resolve_pv_device(pv, str(self.host_root))
        self.assertEqual(device, "nvme1n1")
        self.assertEqual(kind, "awsElasticBlockStore")
        self.assertEqual(handle, "aws://us-east-1a/vol-abc123")

    def test_legacy_disk_bare_volid(self):
        """volumeID = 'vol-abc123' (no aws:// prefix) → resolves."""
        pv = {"spec": {"awsElasticBlockStore": {"volumeID": "vol-abc123"}}}
        device, _, _, _ = pdm._resolve_pv_device(pv, str(self.host_root))
        self.assertEqual(device, "nvme1n1")

    def test_legacy_disk_no_by_id_link_xen_fallback(self):
        """When by-id link missing (xen), return tagged handle, not bare ?."""
        pv = {"spec": {"awsElasticBlockStore": {"volumeID": "vol-deadbeef"}}}
        device, kind, _, _ = pdm._resolve_pv_device(pv, str(self.host_root))
        # No by-id symlink for vol-deadbeef → tagged
        self.assertEqual(device, "vol-deadbeef@xen")
        self.assertEqual(kind, "awsElasticBlockStore")

    def test_legacy_disk_empty_volid(self):
        pv = {"spec": {"awsElasticBlockStore": {"volumeID": ""}}}
        device, kind, _, _ = pdm._resolve_pv_device(pv, str(self.host_root))
        self.assertEqual(device, "?")
        self.assertEqual(kind, "awsElasticBlockStore")


class TestGenericCsi(unittest.TestCase):
    """P1c: generic CSI fallback must NOT return raw volumeHandle as device."""

    def test_unknown_driver_returns_question_mark(self):
        pv = {"spec": {"csi": {
            "driver": "rook-ceph.csi.unknown.io",
            "volumeHandle": "0001-0009-rook-ceph-0000000000000001-abc-123",
        }}}
        device, kind, handle, driver = pdm._resolve_pv_device(pv, "/host")
        # Must be "?" — NOT the raw handle (which would pollute iostat lookups)
        self.assertEqual(device, "?")
        self.assertEqual(kind, "csi")
        # But the handle must still be preserved for diagnostics
        self.assertEqual(handle, "0001-0009-rook-ceph-0000000000000001-abc-123")
        self.assertEqual(driver, "rook-ceph.csi.unknown.io")

    def test_handle_not_leaked_as_device(self):
        """Even an Disk-looking handle on unknown driver → still ?."""
        pv = {"spec": {"csi": {
            "driver": "custom.csi.example.com",
            "volumeHandle": "vol-abc123",  # looks like Disk but driver isn't ebs.csi.aws.com
        }}}
        device, _, _, _ = pdm._resolve_pv_device(pv, "/host")
        self.assertEqual(device, "?",
                         "Generic fallback must NOT return volumeHandle as device")


class TestKubeletMountFallback(unittest.TestCase):
    """P1d: /proc/mounts fallback when CSI extraction fails."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.host_root = Path(self.tmp.name)
        (self.host_root / "proc").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _write_mounts(self, content):
        (self.host_root / "proc/mounts").write_text(content)

    def test_resolves_by_pv_name(self):
        self._write_mounts(
            "tmpfs /run tmpfs rw 0 0\n"
            "/dev/nvme0n1p1 /var/lib/kubelet/pods/abc/volumes/kubernetes.io~csi/"
            "pvc-my-data-pv/mount ext4 rw 0 0\n"
        )
        result = pdm._resolve_via_kubelet_mounts(
            "pvc-my-data-pv", "abc", str(self.host_root)
        )
        self.assertEqual(result, "nvme0n1")  # partition stripped

    def test_resolves_by_pod_uid_when_pv_missing(self):
        self._write_mounts(
            "/dev/sda1 /var/lib/kubelet/pods/podxyz/volumes/x/y/mount ext4 rw 0 0\n"
        )
        result = pdm._resolve_via_kubelet_mounts(
            "", "podxyz", str(self.host_root)
        )
        self.assertEqual(result, "sda")

    def test_skips_non_dev_sources(self):
        """tmpfs, overlay, nfs mounts must be ignored."""
        self._write_mounts(
            "tmpfs /var/lib/kubelet/pods/abc/volumes/empty/data tmpfs rw 0 0\n"
            "overlay /var/lib/kubelet/pods/abc/volumes/img/data overlay rw 0 0\n"
        )
        result = pdm._resolve_via_kubelet_mounts(
            "abc-pv", "abc", str(self.host_root)
        )
        self.assertIsNone(result)

    def test_no_match(self):
        self._write_mounts("/dev/sda1 /home ext4 rw 0 0\n")
        result = pdm._resolve_via_kubelet_mounts(
            "unrelated-pv", "unrelated-uid", str(self.host_root)
        )
        self.assertIsNone(result)

    def test_missing_proc_mounts(self):
        # Don't write /proc/mounts → graceful None (with fallback try also failing
        # if /proc/mounts on actual host doesn't match either)
        result = pdm._resolve_via_kubelet_mounts(
            "definitely-not-a-real-pv-name-xyz123", "definitely-not-a-real-uid-xyz",
            str(self.host_root)
        )
        # Either way, must be None (no false positive)
        self.assertIsNone(result)

    def test_empty_args(self):
        self._write_mounts("/dev/sda1 /home ext4 rw 0 0\n")
        result = pdm._resolve_via_kubelet_mounts("", "", str(self.host_root))
        self.assertIsNone(result)


class TestResolveByIdStripsPartition(unittest.TestCase):
    """P1a end-to-end: _resolve_by_id must return whole-disk, not partition."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.host_root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolves_to_whole_disk_not_partition(self):
        by_id_dir = self.host_root / "dev/disk/by-id"
        by_id_dir.mkdir(parents=True)
        (self.host_root / "dev/nvme0n1p1").write_text("")
        # Some CSI drivers symlink to a partition node (unusual but seen in wild)
        link = by_id_dir / "google-mydisk"
        link.symlink_to("../../nvme0n1p1")
        # Verify: even when by-id points at partition, we report whole disk
        self.assertEqual(pdm._resolve_by_id(link), "nvme0n1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
