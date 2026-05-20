"""S5 smoke: verify all 3 modules import correctly."""
import sys
sys.path.insert(0, "monitoring")
from k8s_api_client import K8sApiClient, K8sApiError
from pod_device_mapper import map_pod_volumes, map_namespace_pods
from kubelet_stats_client import KubeletStatsClient, pod_stats_header
print("OK: all 3 modules importable")
print(f"  K8sApiClient default API: {K8sApiClient().api_server}")
print(f"  pod_stats CSV header: {pod_stats_header()[:60]}...")
