#!/usr/bin/env bash
# integration_k8s_cgroup_config_chain.sh
# Simulate the DaemonSet config chain and verify cgroup collector CSV output.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Stage 1: source config chain ==="
# Simulate a Kubernetes DaemonSet environment.
export DEPLOYMENT_MODE=k8s_gke
export DEPLOYMENT_PLATFORM=gcp
# Correct source order: detector must run before runtime_paths because runtime_paths
# depends on DEPLOYMENT_MODE_DETECTED.
source config/deployment_mode_detector.sh
detect_deployment_mode >/dev/null
source config/runtime_paths.sh
resolve_runtime_paths >/dev/null

echo "  DEPLOYMENT_MODE=$DEPLOYMENT_MODE (source=$DEPLOYMENT_MODE_SOURCE)"
echo "  HOST_PROC=$HOST_PROC HOST_SYS=$HOST_SYS"
echo "  CGROUP_VERSION=$CGROUP_VERSION CGROUP_ROOT=$CGROUP_ROOT"

# k8s_gke env override should be detected.
[[ "$DEPLOYMENT_MODE" == "k8s_gke" ]] || { echo "FAIL: mode is not k8s_gke"; exit 1; }
[[ -n "$HOST_PROC" ]] || { echo "FAIL: HOST_PROC is empty"; exit 1; }

echo
echo "=== Stage 2: cgroup collector consumes env ==="
# cgroup_collector should consume the exported environment.
HEADER=$(python3 monitoring/cgroup_collector.py --header)
DATA=$(python3 monitoring/cgroup_collector.py --data)

# Field counts must match.
HEADER_COLS=$(echo "$HEADER" | tr ',' '\n' | wc -l)
DATA_COLS=$(echo "$DATA"   | tr ',' '\n' | wc -l)
echo "  HEADER cols=$HEADER_COLS DATA cols=$DATA_COLS"
[[ $HEADER_COLS -eq 19 ]] || { echo "FAIL: HEADER does not contain 19 fields"; exit 1; }
[[ $DATA_COLS   -eq 19 ]] || { echo "FAIL: DATA does not contain 19 fields"; exit 1; }
[[ $HEADER_COLS -eq $DATA_COLS ]] || { echo "FAIL: header/data field counts do not match"; exit 1; }

# meta_source must be one of the supported states.
META=$(echo "$DATA" | awk -F',' '{print $NF}')
case "$META" in
  v1|v2|unmounted|unresolved) echo "  meta_source=$META ✓" ;;
  *) echo "FAIL: invalid meta_source value '$META'"; exit 1 ;;
esac

echo
echo "=== Stage 3: K8s manifests static cross-ref ==="
# Re-run the K8s manifest test to confirm cross-references are complete.
if python3 -c "import yaml" >/dev/null 2>&1; then
  python3 tests/test_k8s_manifests.py 2>&1 | tail -3
else
  echo "  PyYAML not installed; skipping manifest static cross-ref"
fi

echo
echo "OK: full-chain cross-stage integration smoke passed"
