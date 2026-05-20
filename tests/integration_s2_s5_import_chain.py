"""S2-S5 闭环检查：所有新模块互相 import 链不断"""
import sys
sys.path.insert(0, "monitoring")

# S3 modules — real exports
from cgroup_collector import (
    ALL_FIELDS, IO_FIELDS, MEM_FIELDS, CPU_FIELDS, META_FIELDS,
    collect, collect_v1, collect_v2,
    _sum_io_stat_v2, _parse_blkio_v1, _parse_kv_lines,
    resolve_target_cgroup, get_host_paths,
)

# S5 modules
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

print("=== S2-S5 模块 import 闭环 ===")
print(f"S3 cgroup_collector  ALL_FIELDS count    = {len(ALL_FIELDS)}")
print(f"S3 cgroup_collector  IO+MEM+CPU+META     = "
      f"{len(IO_FIELDS)}+{len(MEM_FIELDS)}+{len(CPU_FIELDS)}+{len(META_FIELDS)}")
assert len(ALL_FIELDS) == 19, f"ALL_FIELDS 应为 19，实际 {len(ALL_FIELDS)}"
assert len(ALL_FIELDS) == len(IO_FIELDS) + len(MEM_FIELDS) + len(CPU_FIELDS) + len(META_FIELDS)
print(f"S3 schema 一致性                          ✓ ALL_FIELDS == sum(sub-groups)")

print(f"S5 K8sApiClient      default API server  = {K8sApiClient().api_server}")
print(f"S5 CSI extractors    registered count    = {len(_CSI_EXTRACTORS)}")
print(f"S5 CSI extractors    drivers             = {list(_CSI_EXTRACTORS.keys())}")
print(f"S5 PodStats fields   count               = {len(POD_STATS_FIELDS)}")
print(f"S5 pod_stats_header start                = {pod_stats_header()[:50]}...")

# 跨模块兼容性：pod_device_mapper 和 kubelet_stats_client 都用同一 K8sApiClient
api = K8sApiClient(api_server="http://localhost:0", token="dummy")
client = KubeletStatsClient(api)
assert client.api is api, "KubeletStatsClient 必须复用传入的 api 实例"
print(f"S5 客户端复用            KubeletStatsClient ↔ K8sApiClient 共享实例 ✓")

# 跨模块兼容性：cgroup_collector 和 K8s API 客户端可在同一 DaemonSet 进程共存
host_paths = get_host_paths()
print(f"S3 host_paths            HOST_PROC={host_paths.get('HOST_PROC')}")
assert host_paths.get('HOST_PROC'), "HOST_PROC 默认值缺失"

print("\nOK: 所有 S2-S5 模块互相 import 通畅，schema 一致，无断链")
