#!/bin/bash
# monitoring/network_unified_entry.sh
# Y+ 架构: NIC 监控统一入口 (业务代码不直接 source provider 文件, 通过此入口)
#
# Source 后 4 个接口函数立即可用 (来自 ${CLOUD_PROVIDER_VARIANT}.sh):
#   init_network_monitoring
#   generate_network_csv_header
#   collect_network_metrics
#   get_network_field_metadata
#
# Usage:
#   source monitoring/network_unified_entry.sh
#   if init_network_monitoring; then
#       generate_network_csv_header > "$NETWORK_CSV"
#       while running; do collect_network_metrics >> "$NETWORK_CSV"; done
#   fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 1. 探测 platform + driver (导出 CLOUD_PROVIDER_VARIANT)
# shellcheck disable=SC1091
source "${PROJECT_ROOT}/config/cloud_provider.sh"

# 2. 根据 variant source 对应 provider 实现
PROVIDER_FILE="${SCRIPT_DIR}/network/${CLOUD_PROVIDER_VARIANT}.sh"
if [[ ! -f "$PROVIDER_FILE" ]]; then
    echo "WARN: provider file not found: $PROVIDER_FILE, falling back to other_none" >&2
    PROVIDER_FILE="${SCRIPT_DIR}/network/other_none.sh"
fi

if [[ ! -f "$PROVIDER_FILE" ]]; then
    echo "ERROR: even other_none.sh missing at $PROVIDER_FILE" >&2
    return 1 2>/dev/null || exit 1
fi

# shellcheck disable=SC1090
source "$PROVIDER_FILE"

# 3. 验证 4 接口都已定义
for fn in init_network_monitoring generate_network_csv_header collect_network_metrics get_network_field_metadata; do
    if ! declare -F "$fn" > /dev/null; then
        echo "ERROR: provider $PROVIDER_FILE missing function: $fn" >&2
        return 1 2>/dev/null || exit 1
    fi
done

# 暴露元数据
export NETWORK_PROVIDER_FILE="$PROVIDER_FILE"
export NETWORK_PROVIDER_VARIANT="$CLOUD_PROVIDER_VARIANT"
