#!/bin/bash
# config/cloud_provider.sh
# Y+ 架构: cloud_provider 探测 + nic_driver 探测 + CLOUD_PROVIDER_VARIANT 输出
# Source 后导出 4 个变量:
#   CLOUD_PROVIDER         - aws | gcp | other
#   NIC_DRIVER             - ena | gvnic | virtio | none
#   CLOUD_PROVIDER_VARIANT - ${CLOUD_PROVIDER}_${NIC_DRIVER}
#   NETWORK_INTERFACE      - 主网卡名 (eth0/ens4/...)

# === detect_platform: 通过 metadata 探测 ===
# 注意: 用内容校验而不是 curl exit code, 防止沙盒/代理在 169.254/metadata.google.internal
#       上返回 HTTP 200 + HTML 错误页 → curl 退出 0 → 误判。
detect_platform() {
    local body

    # --- 1. GCP metadata (3s timeout) ---
    # GCP instance id 是纯数字 (>= 1 位)。Metadata-Flavor 头是 GCP 元数据契约的强制要求,
    # 任何非 GCP 端点不会返回符合此格式的响应。
    body=$(curl -s -m 3 -H 'Metadata-Flavor: Google' \
        http://metadata.google.internal/computeMetadata/v1/instance/id 2>/dev/null)
    if [[ "$body" =~ ^[0-9]+$ ]]; then
        echo "gcp"; return
    fi

    # --- 2. AWS IMDSv2 (3s timeout) ---
    # EC2 instance id 形如 i-0123456789abcdef0,有严格前缀。
    local token
    token=$(curl -s -m 3 -X PUT 'http://169.254.169.254/latest/api/token' \
        -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' 2>/dev/null)
    if [[ -n "$token" ]]; then
        body=$(curl -s -m 3 -H "X-aws-ec2-metadata-token: $token" \
            http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null)
        if [[ "$body" =~ ^i-[0-9a-f]+$ ]]; then
            echo "aws"; return
        fi
    fi

    echo "other"
}

# === detect_network_interface: 通过默认路由出口 ===
detect_network_interface() {
    local iface
    iface=$(ip route 2>/dev/null | awk '/^default/ {print $5; exit}')
    [[ -n "$iface" ]] && echo "$iface" || echo ""
}

# === detect_nic_driver: 通过 ethtool -i 探测驱动 ===
detect_nic_driver() {
    local iface="${1:-$(detect_network_interface)}"
    [[ -z "$iface" ]] && { echo "none"; return; }
    command -v ethtool >/dev/null 2>&1 || { echo "none"; return; }

    local driver
    driver=$(ethtool -i "$iface" 2>/dev/null | awk '/^driver:/ {print $2}')
    case "$driver" in
        ena|efa) echo "ena" ;;
        gve) echo "gvnic" ;;
        virtio_net) echo "virtio" ;;
        *) echo "none" ;;
    esac
}

# === detect_cloud_provider: 主入口, 设置所有变量 ===
detect_cloud_provider() {
    export NETWORK_INTERFACE="${NETWORK_INTERFACE:-$(detect_network_interface)}"
    export CLOUD_PROVIDER="${CLOUD_PROVIDER:-$(detect_platform)}"
    export NIC_DRIVER="${NIC_DRIVER:-$(detect_nic_driver "$NETWORK_INTERFACE")}"
    export CLOUD_PROVIDER_VARIANT="${CLOUD_PROVIDER}_${NIC_DRIVER}"

    # 已知合法 variants (其他视为 unknown_variant 兜底到 other_none)
    case "$CLOUD_PROVIDER_VARIANT" in
        aws_ena|gcp_gvnic|gcp_virtio|other_none)
            : # 合法
            ;;
        gcp_none|aws_none|other_ena|other_gvnic|other_virtio)
            # 边缘情况: 平台对了但 driver 不匹配 (例如 GCP VM 但 ethtool 探测失败)
            # 兜底到 other_none, 但日志要告警
            echo "WARN: unusual variant '$CLOUD_PROVIDER_VARIANT', falling back to other_none" >&2
            export CLOUD_PROVIDER_VARIANT="other_none"
            ;;
        *)
            echo "WARN: unknown variant '$CLOUD_PROVIDER_VARIANT', falling back to other_none" >&2
            export CLOUD_PROVIDER_VARIANT="other_none"
            ;;
    esac
}

# === 自动执行 (source 时立即探测) ===
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    # 被 source
    detect_cloud_provider
fi
