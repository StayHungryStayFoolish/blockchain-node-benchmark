#!/bin/bash
# =====================================================================
# Solana QPS 测试框架 - 统一配置加载器
# =====================================================================
# 版本: 3.0 - 分层配置架构
# 功能: 按顺序加载所有配置层并执行动态配置检测
# =====================================================================

# 防止重复加载配置文件
if [[ "${CONFIG_LOADED:-}" == "true" ]]; then
    return 0
fi

# 获取配置目录
CONFIG_DIR="$(dirname "${BASH_SOURCE[0]}")"

# 按顺序加载配置层
echo "🔧 加载分层配置..." >&2

# 1. 加载用户配置层
if [[ -f "${CONFIG_DIR}/user_config.sh" ]]; then
    source "${CONFIG_DIR}/user_config.sh"
    echo "✅ 用户配置层加载完成" >&2
else
    echo "❌ 用户配置层文件不存在: ${CONFIG_DIR}/user_config.sh" >&2
    exit 1
fi

# 2. 加载系统配置层
if [[ -f "${CONFIG_DIR}/system_config.sh" ]]; then
    source "${CONFIG_DIR}/system_config.sh"
    echo "✅ 系统配置层加载完成" >&2
else
    echo "❌ 系统配置层文件不存在: ${CONFIG_DIR}/system_config.sh" >&2
    exit 1
fi

# 3. 加载内部配置层
if [[ -f "${CONFIG_DIR}/internal_config.sh" ]]; then
    source "${CONFIG_DIR}/internal_config.sh"
    echo "✅ 内部配置层加载完成" >&2
else
    echo "❌ 内部配置层文件不存在: ${CONFIG_DIR}/internal_config.sh" >&2
    exit 1
fi

# =====================================================================
# 动态配置检测和计算
# =====================================================================

# ----- 自动计算的网络配置 -----
# 自动转换为Mbps (用于内部计算，用户无需修改)
NETWORK_MAX_BANDWIDTH_MBPS=$((NETWORK_MAX_BANDWIDTH_GBPS * 1000))

# ----- 部署平台检测函数 -----
# 自动检测部署平台并调整ENA监控配置
detect_deployment_platform() {
    if [[ "$DEPLOYMENT_PLATFORM" == "auto" ]]; then
        echo "🔍 自动检测部署平台..." >&2
        
        # 检测是否在AWS环境 (通过AWS元数据服务)
        if curl -s --max-time 3 --connect-timeout 2 "${AWS_METADATA_ENDPOINT}/${AWS_METADATA_API_VERSION}/meta-data/instance-id" >/dev/null 2>&1; then
            DEPLOYMENT_PLATFORM="aws"
            ENA_MONITOR_ENABLED=true
            echo "✅ 检测到AWS环境，启用ENA监控" >&2
        else
            DEPLOYMENT_PLATFORM="other"
            ENA_MONITOR_ENABLED=false
            echo "ℹ️  检测到非AWS环境 (IDC/其他云)，禁用ENA监控" >&2
        fi
    else
        echo "🔧 使用手动配置的部署平台: $DEPLOYMENT_PLATFORM" >&2
        case "$DEPLOYMENT_PLATFORM" in
            "aws")
                ENA_MONITOR_ENABLED=true
                echo "✅ AWS环境，启用ENA监控" >&2
                ;;
            "other"|"idc")
                ENA_MONITOR_ENABLED=false
                echo "ℹ️  非AWS环境，禁用ENA监控" >&2
                ;;
            *)
                echo "⚠️  未知部署平台: $DEPLOYMENT_PLATFORM，禁用ENA监控" >&2
                ENA_MONITOR_ENABLED=false
                ;;
        esac
    fi
    
    # 输出最终配置
    echo "📊 部署平台配置:" >&2
    echo "   平台类型: $DEPLOYMENT_PLATFORM" >&2
    echo "   ENA监控: $ENA_MONITOR_ENABLED" >&2
    
    # 标记平台检测已完成并导出到子进程
    DEPLOYMENT_PLATFORM_DETECTED=true
    export DEPLOYMENT_PLATFORM_DETECTED
}

# ----- 网络接口检测函数 -----
# 自动检测ENA网络接口
detect_network_interface() {
    # 优先检测ENA接口
    local ena_interfaces
    if command -v ip >/dev/null 2>&1; then
        ena_interfaces=($(ip link show 2>/dev/null | grep -E "^[0-9]+: (eth|ens|enp)" | grep "state UP" | cut -d: -f2 | tr -d ' '))
    else
        ena_interfaces=()
    fi
    
    # 如果找到ENA接口，优先使用第一个
    if [[ ${#ena_interfaces[@]} -gt 0 ]]; then
        NETWORK_INTERFACE="${ena_interfaces[0]}"
        return 0
    fi
    
    # 如果没有找到ENA接口，使用传统方法检测
    local interface=""
    if command -v ip >/dev/null 2>&1; then
        interface=$(ip route 2>/dev/null | grep default | awk '{print $5}' | head -1)
    elif command -v route >/dev/null 2>&1; then
        interface=$(route get default 2>/dev/null | grep interface | awk '{print $2}')
    elif command -v netstat >/dev/null 2>&1; then
        interface=$(netstat -rn 2>/dev/null | grep default | awk '{print $6}' | head -1)
    fi
    
    # 如果仍然没有找到，使用系统默认
    if [[ -z "$interface" ]]; then
        case "$(uname -s)" in
            "Darwin") interface="en0" ;;  # macOS默认
            "Linux") interface="eth0" ;;   # Linux默认
            *) interface="eth0" ;;         # 其他系统默认
        esac
    fi
    
    NETWORK_INTERFACE="$interface"
}

# ----- 路径检测和配置函数 -----
ACCOUNT_OUTPUT_FILE="active_accounts.txt"                             # 输出文件名

# 检测部署环境并设置路径
detect_deployment_paths() {
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local framework_dir="$(dirname "$script_dir")"
    local deployment_dir="$(dirname "$framework_dir")"
    
    echo "🔍 检测部署结构..." >&2
    echo "   框架目录: $framework_dir" >&2
    echo "   部署目录: $deployment_dir" >&2
    
    # 设置内存共享目录 (独立于数据目录，保持系统级路径)
    if [[ "$(uname -s)" == "Darwin" ]]; then
        # macOS 开发环境
        BASE_MEMORY_DIR="${TMPDIR:-/tmp}/blockchain-node-benchmark"
        DEPLOYMENT_ENV="development"
        echo "🔧 检测到开发环境 (macOS)" >&2
    else
        # Linux 生产环境 - 使用系统 tmpfs
        BASE_MEMORY_DIR="/dev/shm/blockchain-node-benchmark"
        DEPLOYMENT_ENV="production"
        echo "🐧 检测到Linux生产环境" >&2
    fi
    
    # 标准化路径配置
    BASE_FRAMEWORK_DIR="$framework_dir"
    BASE_DATA_DIR="${BLOCKCHAIN_BENCHMARK_DATA_DIR:-${deployment_dir}/blockchain-node-benchmark-result}"
    
    # 验证和修复路径设置
    if [[ -z "$BASE_DATA_DIR" || "$BASE_DATA_DIR" == "/blockchain-node-benchmark-result" ]]; then
        echo "⚠️ 数据目录路径异常，使用默认路径" >&2
        BASE_DATA_DIR="${HOME}/blockchain-node-benchmark-result"
    fi
    
    DEPLOYMENT_STRUCTURE="standard"
    
    echo "🚀 使用标准部署结构" >&2
    echo "   数据目录: $BASE_DATA_DIR" >&2
    
    # 支持环境变量覆盖
    if [[ -n "${BLOCKCHAIN_BENCHMARK_DATA_DIR:-}" ]]; then
        echo "   (使用环境变量: BLOCKCHAIN_BENCHMARK_DATA_DIR)" >&2
    fi
    
    # 设置目录结构 - 基于新的标准化路径
    # 主数据目录 (QPS测试专属)
    DATA_DIR="${BASE_DATA_DIR}"
    # 当前测试数据目录
    CURRENT_TEST_DIR="${DATA_DIR}/current"
    # 日志目录 (性能监控数据)
    LOGS_DIR="${CURRENT_TEST_DIR}/logs"
    # 报告目录 (分析报告和图表)
    REPORTS_DIR="${CURRENT_TEST_DIR}/reports"
    # Vegeta 结果目录 (压测原始数据)
    VEGETA_RESULTS_DIR="${CURRENT_TEST_DIR}/vegeta_results"
    # 临时文件目录 (运行时临时数据)
    TMP_DIR="${CURRENT_TEST_DIR}/tmp"
    # 归档目录 (历史测试数据)
    ARCHIVES_DIR="${DATA_DIR}/archives"
    # 错误处理和日志目录
    ERROR_LOG_DIR="${CURRENT_TEST_DIR}/${ERROR_LOG_SUBDIR}"
    PYTHON_ERROR_LOG_DIR="${CURRENT_TEST_DIR}/${PYTHON_ERROR_LOG_SUBDIR}"
    
    # 内存共享目录 (独立于数据目录，使用系统级路径)
    MEMORY_SHARE_DIR="${BASE_MEMORY_DIR}"
    
    # 设置动态路径变量
    SLOT_CACHE_FILE="${MEMORY_SHARE_DIR}/slot_monitor_cache.json"
    SLOT_DATA_FILE="${LOGS_DIR}/slot_monitor_$(date +%Y%m%d_%H%M%S).csv"
    ACCOUNTS_OUTPUT_FILE="${TMP_DIR}/${ACCOUNT_OUTPUT_FILE}"
    SINGLE_METHOD_TARGETS_FILE="${TMP_DIR}/targets_single.json"
    MIXED_METHOD_TARGETS_FILE="${TMP_DIR}/targets_mixed.json"
    QPS_STATUS_FILE="${MEMORY_SHARE_DIR}/qps_status.json"
    TEST_SESSION_DIR="${TMP_DIR}/session_$(date +%Y%m%d_%H%M%S)"
    
    # 设置监控开销优化相关的日志文件路径
    MONITORING_OVERHEAD_LOG="${LOGS_DIR}/monitoring_overhead_$(date +%Y%m%d_%H%M%S).csv"
    PERFORMANCE_LOG="${LOGS_DIR}/monitoring_performance_$(date +%Y%m%d_%H%M%S).log"
    ERROR_LOG="${LOGS_DIR}/monitoring_errors_$(date +%Y%m%d_%H%M%S).log"
    
    # 临时文件模式 (用于清理)
    TEMP_FILE_PATTERN="${TMP_DIR}/${TEMP_FILE_PREFIX}-*"
    
    # 输出最终配置
    echo "📋 路径配置完成:" >&2
    echo "   部署结构: $DEPLOYMENT_STRUCTURE" >&2
    echo "   框架目录: $BASE_FRAMEWORK_DIR" >&2
    echo "   数据目录: $BASE_DATA_DIR" >&2
    echo "   内存共享: $MEMORY_SHARE_DIR" >&2
    
    # 标记路径检测已完成并导出到子进程
    DEPLOYMENT_PATHS_DETECTED=true
    export DEPLOYMENT_PATHS_DETECTED
}

# ----- 目录创建函数 -----
# 安全创建目录函数
create_directories_safely() {
    local dirs=("$@")
    local created_dirs=()
    local failed_dirs=()
    
    echo "🔧 正在创建必要的目录..." >&2
    
    for dir in "${dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            if mkdir -p "$dir" 2>/dev/null; then
                echo "✅ 创建目录: $dir" >&2
                created_dirs+=("$dir")
                chmod 755 "$dir" 2>/dev/null || true
            else
                echo "❌ 无法创建目录: $dir" >&2
                failed_dirs+=("$dir")
            fi
        else
            echo "✅ 目录已存在: $dir" >&2
        fi
    done
    
    # 标记目录创建已完成并导出到子进程
    DIRECTORIES_CREATED=true
    export DIRECTORIES_CREATED
    
    # 返回结果摘要
    if [[ ${#failed_dirs[@]} -gt 0 ]]; then
        echo "⚠️  部分目录创建失败: ${failed_dirs[*]}" >&2
        return 1
    else
        echo "✅ 所有目录创建成功" >&2
        return 0
    fi
}

# =====================================================================
# 执行动态配置检测
# =====================================================================

# 执行部署平台检测
detect_deployment_platform

# 执行网络接口检测
detect_network_interface

# 执行路径检测和配置
detect_deployment_paths

# 创建必要的目录
create_directories_safely "$DATA_DIR" "$CURRENT_TEST_DIR" "$LOGS_DIR" "$REPORTS_DIR" "$VEGETA_RESULTS_DIR" "$TMP_DIR" "$ARCHIVES_DIR" "$ERROR_LOG_DIR" "$PYTHON_ERROR_LOG_DIR" "$MEMORY_SHARE_DIR"



# =====================================================================
# 配置 Blockchain Node & On-chain Active Addresses
# =====================================================================

# ----- 基础配置 -----
# Blockchain Node Local RPC Endpoint
LOCAL_RPC_URL="${LOCAL_RPC_URL:-http://localhost:8899}"
# Mainnet RPC Endpoint
MAINNET_RPC_URL="https://api.mainnet-beta.solana.com"

# ----- 区块链节点配置 -----
BLOCKCHAIN_NODE="Solana"

# 强制确保 BLOCKCHAIN_NODE 是小写
BLOCKCHAIN_NODE=$(echo "$BLOCKCHAIN_NODE" | tr '[:upper:]' '[:lower:]')

# 区块链节点运行进程名称
BLOCKCHAIN_PROCESS_NAMES=(
    "blockchain"
    "validator"
    "node"
)

# 账户和目标文件配置
ACCOUNT_COUNT=1000                                                    # 默认账户数量

# ----- 账户获取工具配置 -----
# 账户获取工具的详细配置参数
ACCOUNT_TARGET_ADDRESS="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v" # 示例目标地址
ACCOUNT_MAX_SIGNATURES=50000                                          # 最大签名数量
ACCOUNT_TX_BATCH_SIZE=100                                             # 交易批处理大小
ACCOUNT_SEMAPHORE_LIMIT=10                                            # 并发限制

# ----- RPC模式配置 -----
RPC_MODE="${RPC_MODE:-single}"      # RPC模式: single/mixed (默认single)

CHAIN_CONFIG=$(cat <<EOF
{
  "chain_type": "BLOCKCHAIN_NODE",
  "rpc_url": "LOCAL_RPC_URL",
  "params": {
    "account_count": "ACCOUNT_COUNT",
    "output_file": "ACCOUNTS_OUTPUT_FILE",
    "target_address": "ACCOUNT_TARGET_ADDRESS",
    "max_signatures": "ACCOUNT_MAX_SIGNATURES",
    "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
    "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
  },
  "methods": {
    "get_signatures": "getSignaturesForAddress",
    "get_transaction": "getTransaction"
  },
  "system_addresses": [
    "11111111111111111111111111111111",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s",
    "SysvarRent111111111111111111111111111111111",
    "ComputeBudget111111111111111111111111111111"
  ]
}
EOF
)

# =====================================================================
# 多区块链 RPC 方法配置 - 基于 JSON-RPC-API-List.md
# =====================================================================

# 多区块链 RPC 方法配置 - 基于 API 功能对应关系总结表
declare -A BLOCKCHAIN_RPC_METHODS=(
    # Solana RPC 方法配置
    ["solana_single"]="getAccountInfo"
    ["solana_mixed"]="getAccountInfo,getBalance,getTokenAccountBalance,getRecentBlockhash,getBlockHeight"

    # EVM兼容链 RPC 方法配置 (Ethereum, BSC, Base, Polygon, Scroll)
    ["ethereum_single"]="eth_getBalance"
    ["ethereum_mixed"]="eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"

    ["bsc_single"]="eth_getBalance"
    ["bsc_mixed"]="eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"

    ["base_single"]="eth_getBalance"
    ["base_mixed"]="eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"

    ["polygon_single"]="eth_getBalance"
    ["polygon_mixed"]="eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"

    ["scroll_single"]="eth_getBalance"
    ["scroll_mixed"]="eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"

    # StarkNet RPC 方法配置
    ["starknet_single"]="starknet_getClassAt"
    ["starknet_mixed"]="starknet_getClassAt,starknet_getNonce,starknet_getStorageAt,starknet_blockNumber"

    # Sui RPC 方法配置
    ["sui_single"]="sui_getObject"
    ["sui_mixed"]="sui_getObject,sui_getObjectsOwnedByAddress,sui_getTotalTransactionBlocks,sui_getLatestCheckpointSequenceNumber"
)


# 精确的参数格式配置 - 基于实际API文档
declare -A RPC_METHOD_PARAM_FORMATS=(
    # Solana 方法参数格式
    ["getAccountInfo"]="single_address"           # ["address"]
    ["getBalance"]="single_address"               # ["address"]
    ["getTokenAccountBalance"]="single_address"   # ["address"]
    ["getRecentBlockhash"]="no_params"           # []
    ["getBlockHeight"]="no_params"               # []

    # EVM兼容链方法参数格式
    ["eth_getBalance"]="address_latest"          # ["address", "latest"]
    ["eth_getTransactionCount"]="address_latest" # ["address", "latest"]
    ["eth_blockNumber"]="no_params"              # []
    ["eth_gasPrice"]="no_params"                 # []

    # StarkNet 方法参数格式
    ["starknet_getClassAt"]="latest_address"     # ["latest", "address"]
    ["starknet_getNonce"]="latest_address"       # ["latest", "address"]
    ["starknet_getStorageAt"]="address_key_latest" # ["address", "0x1", "latest"]
    ["starknet_blockNumber"]="no_params"         # []

    # Sui 方法参数格式
    ["sui_getObject"]="address_with_options"     # ["address", {"showType": true, "showContent": true, "showDisplay": false}]
    ["sui_getObjectsOwnedByAddress"]="single_address" # ["address"]
    ["sui_getTotalTransactionBlocks"]="no_params"     # []
    ["sui_getLatestCheckpointSequenceNumber"]="no_params" # []
)

# 获取当前区块链的RPC方法列表
get_current_rpc_methods() {
    local chain_type=$(echo "${BLOCKCHAIN_NODE}" | tr '[:upper:]' '[:lower:]')
    local rpc_mode=$(echo "${RPC_MODE}" | tr '[:upper:]' '[:lower:]')
    local config_key="${chain_type}_${rpc_mode}"

    local methods_string="${BLOCKCHAIN_RPC_METHODS[$config_key]}"

    if [[ -z "$methods_string" ]]; then
        echo "⚠️ 警告: 未找到 $config_key 的RPC方法配置，使用默认Solana配置" >&2
        methods_string="${BLOCKCHAIN_RPC_METHODS["solana_${rpc_mode}"]}"
    fi

    echo "$methods_string"
}


# 验证关键变量是否正确设置
if [[ -z "$ACCOUNTS_OUTPUT_FILE" ]]; then
    echo "⚠️ 警告: ACCOUNTS_OUTPUT_FILE 未正确设置" >&2
fi
if [[ -z "$LOCAL_RPC_URL" ]]; then
    echo "⚠️ 警告: LOCAL_RPC_URL 未正确设置" >&2
fi

# 标记配置已加载
# 导出函数到子进程
export -f get_current_rpc_methods
CURRENT_RPC_METHODS_STRING=$(get_current_rpc_methods)
IFS=',' read -ra CURRENT_RPC_METHODS_ARRAY <<< "$CURRENT_RPC_METHODS_STRING"
export CONFIG_LOADED="true"
export ACCOUNTS_OUTPUT_FILE SINGLE_METHOD_TARGETS_FILE MIXED_METHOD_TARGETS_FILE
export LOCAL_RPC_URL MAINNET_RPC_URL BLOCKCHAIN_NODE BLOCKCHAIN_PROCESS_NAMES RPC_MODE
export ACCOUNT_COUNT ACCOUNT_OUTPUT_FILE ACCOUNT_TARGET_ADDRESS ACCOUNT_MAX_SIGNATURES ACCOUNT_TX_BATCH_SIZE ACCOUNT_SEMAPHORE_LIMIT
export CHAIN_CONFIG
export BLOCKCHAIN_RPC_METHODS RPC_METHOD_PARAM_FORMATS
export CURRENT_RPC_METHODS_STRING CURRENT_RPC_METHODS_ARRAY

export DATA_DIR CURRENT_TEST_DIR LOGS_DIR REPORTS_DIR VEGETA_RESULTS_DIR TMP_DIR ARCHIVES_DIR
export ERROR_LOG_DIR PYTHON_ERROR_LOG_DIR MEMORY_SHARE_DIR
export SLOT_CACHE_FILE SLOT_DATA_FILE QPS_STATUS_FILE TEST_SESSION_DIR
export MONITORING_OVERHEAD_LOG PERFORMANCE_LOG ERROR_LOG TEMP_FILE_PATTERN

export NETWORK_MAX_BANDWIDTH_MBPS DEPLOYMENT_PLATFORM ENA_MONITOR_ENABLED
export NETWORK_INTERFACE BASE_MEMORY_DIR DEPLOYMENT_ENV
export BASE_FRAMEWORK_DIR BASE_DATA_DIR DEPLOYMENT_STRUCTURE



echo "🔧 RPC方法配置完成:" >&2
echo "   区块链类型: $BLOCKCHAIN_NODE" >&2
echo "   RPC模式: $RPC_MODE" >&2
echo "   当前方法: $CURRENT_RPC_METHODS_STRING" >&2
echo "🎉 分层配置加载完成！" >&2


## =====================================================================
## Other Blockchain Configuration
## =====================================================================
##
## Solana USDC Address
#ACCOUNT_TARGET_ADDRESS="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
## Solana Json
#CHAIN_CONFIG=$(cat <<EOF
#{
#  "chain_type": "BLOCKCHAIN_NODE",
#  "rpc_url": "LOCAL_RPC_URL",
#  "params": {
#    "account_count": "ACCOUNT_COUNT",
#    "output_file": "ACCOUNTS_OUTPUT_FILE",
#    "target_address": "ACCOUNT_TARGET_ADDRESS",
#    "max_signatures": "ACCOUNT_MAX_SIGNATURES",
#    "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
#    "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
#  },
#  "methods": {
#    "get_signatures": "getSignaturesForAddress",
#    "get_transaction": "getTransaction"
#  },
#  "system_addresses": [
#    "11111111111111111111111111111111",
#    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
#    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
#    "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s",
#    "SysvarRent111111111111111111111111111111111",
#    "ComputeBudget111111111111111111111111111111"
#  ]
#}
#EOF
#)
#
## =====================================================================
## Ethereum USDT Address
#ACCOUNT_TARGET_ADDRESS="0xdAC17F958D2ee523a2206206994597C13D831ec7"
## Ethereum Json
#CHAIN_CONFIG=$(cat <<EOF
#{
#  "chain_type": "ethereum",
#  "rpc_url": "LOCAL_RPC_URL",
#  "params": {
#    "account_count": "ACCOUNT_COUNT",
#    "output_file": "ACCOUNTS_OUTPUT_FILE",
#    "target_address": "ACCOUNT_TARGET_ADDRESS",
#    "max_signatures": "ACCOUNT_MAX_SIGNATURES",
#    "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
#    "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
#  },
#  "methods": {
#    "get_logs": "eth_getLogs",
#    "get_transaction": "eth_getTransactionByHash"
#  },
#  "system_addresses": [
#    "0x0000000000000000000000000000000000000000",
#    "0x000000000000000000000000000000000000dead"
#  ]
#}
#EOF
#)
#
## =====================================================================
#
## BSC USDS Address
#ACCOUNT_TARGET_ADDRESS="0x250632378E573c6Be1AC2f97Fcdf00515d0Aa91B"
## BSC Json
#CHAIN_CONFIG=$(cat <<EOF
#{
#  "chain_type": "bsc",
#  "rpc_url": "LOCAL_RPC_URL",
#  "params": {
#    "account_count": "ACCOUNT_COUNT",
#    "output_file": "ACCOUNTS_OUTPUT_FILE",
#    "target_address": "ACCOUNT_TARGET_ADDRESS",
#    "max_signatures": "ACCOUNT_MAX_SIGNATURES",
#    "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
#    "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
#  },
#  "methods": {
#    "get_logs": "eth_getLogs",
#    "get_transaction": "eth_getTransactionByHash"
#  },
#  "system_addresses": [
#    "0x0000000000000000000000000000000000000000",
#    "0x000000000000000000000000000000000000dead"
#  ]
#}
#EOF
#)
#
## =====================================================================
#
## Base USDC Address
#ACCOUNT_TARGET_ADDRESS="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # USDC on Base
## Base Json
#CHAIN_CONFIG=$(cat <<EOF
#{
#  "chain_type": "base",
#  "rpc_url": "LOCAL_RPC_URL",
#  "params": {
#    "account_count": "ACCOUNT_COUNT",
#    "output_file": "ACCOUNTS_OUTPUT_FILE",
#    "target_address": "ACCOUNT_TARGET_ADDRESS",
#    "max_signatures": "ACCOUNT_MAX_SIGNATURES",
#    "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
#    "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
#  },
#  "methods": {
#    "get_logs": "eth_getLogs",
#    "get_transaction": "eth_getTransactionByHash"
#  },
#  "system_addresses": [
#    "0x0000000000000000000000000000000000000000",
#    "0x000000000000000000000000000000000000dead"
#  ]
#}
#EOF
#)
#
## =====================================================================
## Scroll USDC Address
#ACCOUNT_TARGET_ADDRESS="0x06eFdBFf2a14a7c8E15944D1F4A48F9F95F663A4"
## Scroll Json
#CHAIN_CONFIG=$(cat <<EOF
#{
#  "chain_type": "scroll",
#  "rpc_url": "LOCAL_RPC_URL",
#  "params": {
#    "account_count": "ACCOUNT_COUNT",
#    "output_file": "ACCOUNTS_OUTPUT_FILE",
#    "target_address": "ACCOUNT_TARGET_ADDRESS",
#    "max_signatures": "ACCOUNT_MAX_SIGNATURES",
#    "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
#    "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
#  },
#  "methods": {
#    "get_logs": "eth_getLogs",
#    "get_transaction": "eth_getTransactionByHash"
#  },
#  "system_addresses": [
#    "0x0000000000000000000000000000000000000000",
#    "0x000000000000000000000000000000000000dead"
#  ]
#}
#EOF
#)
#
## =====================================================================
## Polygon USDT Address
#ACCOUNT_TARGET_ADDRESS="0xc2132D05D31c914a87C6611C10748AEb04B58e8F"  # USDT on Polygon
## Polygon Jason
#CHAIN_CONFIG=$(cat <<EOF
#{
#  "chain_type": "polygon",
#  "rpc_url": "LOCAL_RPC_URL",
#  "params": {
#    "account_count": "ACCOUNT_COUNT",
#    "output_file": "ACCOUNTS_OUTPUT_FILE",
#    "target_address": "ACCOUNT_TARGET_ADDRESS",
#    "max_signatures": "ACCOUNT_MAX_SIGNATURES",
#    "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
#    "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
#  },
#  "methods": {
#    "get_logs": "eth_getLogs",
#    "get_transaction": "eth_getTransactionByHash"
#  },
#  "system_addresses": [
#    "0x0000000000000000000000000000000000000000",
#    "0x000000000000000000000000000000000000dead"
#  ]
#}
#EOF
#)
#
## =====================================================================
## Starknet USDC Address
#ACCOUNT_TARGET_ADDRESS="0x068f5c6a61780768455de69077e07e89787839bf8166decfbf92b645209c0fb8"  # Starknet USDC
## Starknet Json
#CHAIN_CONFIG=$(cat <<EOF
#{
#  "chain_type": "starknet",
#  "rpc_url": "LOCAL_RPC_URL",
#  "params": {
#    "account_count": "ACCOUNT_COUNT",
#    "output_file": "ACCOUNTS_OUTPUT_FILE",
#    "target_address": "ACCOUNT_TARGET_ADDRESS",
#    "max_signatures": "ACCOUNT_MAX_SIGNATURES",
#    "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
#    "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
#  },
#  "methods": {
#    "get_events_native": "starknet_getEvents",
#    "get_transaction": "starknet_getTransactionByHash"
#  },
#  "system_addresses": []
#}
#EOF
#)
#
## =====================================================================
#
## Sui USDC Address
#ACCOUNT_TARGET_ADDRESS="0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC"
## Sui Json
#CHAIN_CONFIG=$(cat <<EOF
#{
#  "chain_type": "sui",
#  "rpc_url": "LOCAL_RPC_URL",
#  "params": {
#    "account_count": "ACCOUNT_COUNT",
#    "output_file": "ACCOUNTS_OUTPUT_FILE",
#    "target_address": "ACCOUNT_TARGET_ADDRESS",
#    "max_signatures": "ACCOUNT_MAX_SIGNATURES",
#    "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
#    "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
#  },
#  "methods": {
#    "get_owned_objects": "suix_getOwnedObjects",
#    "get_transaction": "sui_getTransactionBlock",
#    "get_transactions": "suix_queryTransactionBlocks"
#  },
#  "system_addresses": ["0x1", "0x2", "0x3"]
#}
#EOF
#)
#
## =====================================================================