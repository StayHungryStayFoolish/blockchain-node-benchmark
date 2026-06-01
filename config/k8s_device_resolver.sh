#!/usr/bin/env bash
# config/k8s_device_resolver.sh
# =====================================================================
# K8s 模式磁盘设备解析: 把本 Pod 的 PVC 卷解析成 node 上的真实块设备名,
# 填充 LEDGER_DEVICE / ACCOUNTS_DEVICE, 让下游 iostat 采集链(get_iostat_data /
# get_all_devices_data / sizing / 图表)零改动复用 VM 路径。
#
# 设计依据: analysis-notes/EXEC-TRACKER.md §18 (真机验证: data→sdb / accounts→sdc)
# 真机硬证(GKE bench-k8s-test, 2026-06-01): pod_device_mapper 正确区分 data/accounts
#   两卷映射到 sdb/sdc; node 级 iostat 对各盘采到 util/IOPS/throughput。
#
# 调用时机: config_loader.sh 在 detect_deployment_mode + resolve_k8s_paths 之后调用。
#   仅 DEPLOYMENT_MODE=k8s* 时生效; 非 k8s 模式整段跳过 → VM 路径零影响(回归保护)。
#
# 依赖(Pod 内由 Downward API 注入, 见 deploy/k8s/04-daemonset.yaml):
#   POD_NAME / POD_NAMESPACE   - 定位本 Pod
#   HOST_ROOT (默认 /host)     - pod_device_mapper 解析 by-id 设备链接的宿主根
# Pod ServiceAccount 需有 get pods/pvc/pv 权限(deploy/k8s/02-serviceaccount-rbac.yaml 已配)。
#
# 解析失败处理(分级 fallback, 不静默断链):
#   - DEPLOYMENT_MODE 非 k8s         → 跳过, 保留 user_config 配置值
#   - pod_device_mapper 不可用/报错  → WARN, 保留 user_config 配置值(可能是用户手配 hostPath)
#   - 某卷解析出 "?" / 空            → 该卷 WARN, 不覆盖对应变量(保留原值)
# =====================================================================

# 仅 k8s 模式生效; 其余形态直接返回(VM/docker 路径完全不走此逻辑)
resolve_k8s_disk_devices() {
    case "${DEPLOYMENT_MODE:-}" in
        k8s_eks|k8s_gke|k8s_other) : ;;   # 继续
        *) return 0 ;;                     # 非 k8s: 跳过, 保留 user_config 值
    esac

    local pod_ns="${POD_NAMESPACE:-}"
    local pod_name="${POD_NAME:-}"
    local host_root="${HOST_ROOT:-/host}"

    if [[ -z "$pod_ns" || -z "$pod_name" ]]; then
        echo "⚠️  k8s_device_resolver: POD_NAMESPACE/POD_NAME 未注入(需 Downward API), 保留 user_config 磁盘配置" >&2
        return 0
    fi

    local mapper="$(dirname "${BASH_SOURCE[0]}")/../monitoring/pod_device_mapper.py"
    if [[ ! -f "$mapper" ]]; then
        echo "⚠️  k8s_device_resolver: pod_device_mapper.py 不存在($mapper), 保留 user_config 磁盘配置" >&2
        return 0
    fi

    # pod_device_mapper 输出格式(每卷一行): "  <logical_name>  → <device>  pv=... csi=... kind=..."
    # 解析本 Pod 各卷; 失败(无 python3 / API 不可达 / 权限不足)整体降级保留配置值。
    local mapper_out
    mapper_out="$(POD_NAMESPACE="$pod_ns" POD_NAME="$pod_name" \
        python3 "$mapper" -n "$pod_ns" -p "$pod_name" --host-root "$host_root" 2>/dev/null)"
    if [[ -z "$mapper_out" ]]; then
        echo "⚠️  k8s_device_resolver: pod_device_mapper 无输出(API 不可达/权限不足?), 保留 user_config 磁盘配置" >&2
        return 0
    fi

    # 按 logical_name 提取 data / accounts 卷对应的 node 块设备名。
    # 约定: Pod spec 的卷名 = "data"(LEDGER) / "accounts"(ACCOUNTS), 与 VM 逻辑名一致。
    local data_dev accounts_dev
    data_dev="$(echo "$mapper_out"     | awk '$1=="data"     {print $3; exit}')"
    accounts_dev="$(echo "$mapper_out" | awk '$1=="accounts" {print $3; exit}')"

    # 仅在解析出有效设备名(非空、非占位符 "?")时覆盖, 否则保留 user_config 原值
    if [[ -n "$data_dev" && "$data_dev" != "?" ]]; then
        export LEDGER_DEVICE="$data_dev"
        echo "✅ k8s_device_resolver: LEDGER_DEVICE=$data_dev (Pod 卷 data → node 块设备)" >&2
    else
        echo "⚠️  k8s_device_resolver: Pod 卷 'data' 未解析到 node 设备(得 '${data_dev:-空}'), 保留 LEDGER_DEVICE=${LEDGER_DEVICE:-未设}" >&2
    fi

    if [[ -n "$accounts_dev" && "$accounts_dev" != "?" ]]; then
        export ACCOUNTS_DEVICE="$accounts_dev"
        echo "✅ k8s_device_resolver: ACCOUNTS_DEVICE=$accounts_dev (Pod 卷 accounts → node 块设备)" >&2
    else
        # accounts 是可选盘(单盘部署无此卷), 解析不到属正常, 仅 debug 级提示
        echo "ℹ️  k8s_device_resolver: Pod 卷 'accounts' 未解析到 node 设备(可选盘, 单盘部署正常), 保留 ACCOUNTS_DEVICE=${ACCOUNTS_DEVICE:-未设}" >&2
    fi
}
