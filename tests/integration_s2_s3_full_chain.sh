#!/usr/bin/env bash
# integration_s2_s3_full_chain.sh
# 完整模拟 DaemonSet 启动流程：source 配置链 → 用 env 跑 cgroup collector → 验证 CSV 输出
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Stage 1: source config chain ==="
# 模拟 DaemonSet 里 K8S 环境
export DEPLOYMENT_MODE=k8s_gke
export DEPLOYMENT_PLATFORM=gcp
# 正确顺序：detector 必须在 k8s_paths 之前（k8s_paths 依赖 DEPLOYMENT_MODE_DETECTED）
source config/deployment_mode_detector.sh
detect_deployment_mode >/dev/null
source config/k8s_paths.sh
resolve_k8s_paths >/dev/null

echo "  DEPLOYMENT_MODE=$DEPLOYMENT_MODE (source=$DEPLOYMENT_MODE_SOURCE)"
echo "  HOST_PROC=$HOST_PROC HOST_SYS=$HOST_SYS"
echo "  CGROUP_VERSION=$CGROUP_VERSION CGROUP_ROOT=$CGROUP_ROOT"

# k8s_gke env override 应被识别
[[ "$DEPLOYMENT_MODE" == "k8s_gke" ]] || { echo "FAIL: mode 不是 k8s_gke"; exit 1; }
[[ -n "$HOST_PROC" ]] || { echo "FAIL: HOST_PROC 空"; exit 1; }

echo
echo "=== Stage 2: cgroup collector consumes env ==="
# cgroup_collector 应读取上一步 export 的 env
HEADER=$(python3 monitoring/cgroup_collector.py --header)
DATA=$(python3 monitoring/cgroup_collector.py --data)

# 字段数对齐
HEADER_COLS=$(echo "$HEADER" | tr ',' '\n' | wc -l)
DATA_COLS=$(echo "$DATA"   | tr ',' '\n' | wc -l)
echo "  HEADER cols=$HEADER_COLS DATA cols=$DATA_COLS"
[[ $HEADER_COLS -eq 19 ]] || { echo "FAIL: HEADER 不是 19 字段"; exit 1; }
[[ $DATA_COLS   -eq 19 ]] || { echo "FAIL: DATA 不是 19 字段"; exit 1; }
[[ $HEADER_COLS -eq $DATA_COLS ]] || { echo "FAIL: header/data 字段数不齐"; exit 1; }

# meta source 末列应为 v1/v2/unmounted/unresolved 之一
META=$(echo "$DATA" | awk -F',' '{print $NF}')
case "$META" in
  v1|v2|unmounted|unresolved) echo "  meta_source=$META ✓" ;;
  *) echo "FAIL: meta_source 非法值 '$META'"; exit 1 ;;
esac

echo
echo "=== Stage 3: K8s manifests static cross-ref ==="
# 重跑 K8s manifest 测试确认 cross-ref 完整
python3 tests/test_k8s_manifests.py 2>&1 | tail -3

echo
echo "OK: S2→S3→S4 跨阶段集成 smoke 通过"
