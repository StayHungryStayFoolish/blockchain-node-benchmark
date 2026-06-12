"""Monitoring and K8s module import-chain regression check"""
import sys
sys.path.insert(0, "monitoring")

# cgroup collector module exports
from cgroup_collector import (
    ALL_FIELDS, IO_FIELDS, MEM_FIELDS, CPU_FIELDS, META_FIELDS,
    collect, collect_v1, collect_v2,
    _sum_io_stat_v2, _parse_blkio_v1, _parse_kv_lines,
    resolve_target_cgroup, get_host_paths,
)

# K8s helper module exports
from k8s_api_client import K8sApiClient, K8sApiError
from pod_device_mapper import (
    map_pod_volumes, map_namespace_pods,
    _CSI_EXTRACTORS, _resolve_pv_device,
    PodMapping, VolumeMapping,
)
from kubelet_stats_client import (
    KubeletStatsClient, PodStats, VolumeStats,
    pod_stats_header, pod_stats_row, POD_STATS_FIELDS,
    _parse_pod, _parse_volume,
)

print("=== Monitoring module import chain ===")
print(f"cgroup_collector  ALL_FIELDS count    = {len(ALL_FIELDS)}")
print(f"cgroup_collector  IO+MEM+CPU+META     = "
      f"{len(IO_FIELDS)}+{len(MEM_FIELDS)}+{len(CPU_FIELDS)}+{len(META_FIELDS)}")
assert len(ALL_FIELDS) == 19, f"ALL_FIELDS expected 19, got {len(ALL_FIELDS)}"
assert len(ALL_FIELDS) == len(IO_FIELDS) + len(MEM_FIELDS) + len(CPU_FIELDS) + len(META_FIELDS)
print(f"schema consistency                          ✓ ALL_FIELDS == sum(sub-groups)")

print(f"K8sApiClient      default API server  = {K8sApiClient().api_server}")
print(f"CSI extractors    registered count    = {len(_CSI_EXTRACTORS)}")
print(f"CSI extractors    drivers             = {list(_CSI_EXTRACTORS.keys())}")
print(f"PodStats fields   count               = {len(POD_STATS_FIELDS)}")
print(f"pod_stats_header start                = {pod_stats_header()[:50]}...")

# Cross-module compatibility: pod_device_mapper and kubelet_stats_client share one K8sApiClient
api = K8sApiClient(api_server="http://localhost:0", token="dummy")
client = KubeletStatsClient(api)
assert client.api is api, "KubeletStatsClient must reuse the supplied API instance"
print(f"K8s client reuse            KubeletStatsClient ↔ K8sApiClient shared instance ✓")

# Cross-module compatibility: cgroup_collector and K8s API client can coexist in one DaemonSet process
host_paths = get_host_paths()
print(f"host_paths            HOST_PROC={host_paths.get('HOST_PROC')}")
assert host_paths.get('HOST_PROC'), "HOST_PROC default value missing"

print("\nOK: monitoring modules import cleanly and schemas are consistent")
