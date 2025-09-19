#!/bin/bash
# =====================================================================
# Blockchain Node Benchmark Framework - 统一配置加载器
# =====================================================================
# 功能: 按顺序加载所有配置层并执行动态配置检测
# =====================================================================

# =====================================================================
# 用户配置变量 - 用户只需要配置这些变量
# =====================================================================

# ----- 基础配置 -----
# Blockchain Node Local RPC Endpoint
LOCAL_RPC_URL="${LOCAL_RPC_URL:-http://localhost:8899}"

# ----- 区块链节点配置 -----
BLOCKCHAIN_NODE="${BLOCKCHAIN_NODE:-solana}"

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
ACCOUNT_MAX_SIGNATURES=50000                                          # 最大签名数量
ACCOUNT_TX_BATCH_SIZE=100                                             # 交易批处理大小
ACCOUNT_SEMAPHORE_LIMIT=10                                            # 并发限制

# ----- RPC模式配置 -----
RPC_MODE="${RPC_MODE:-single}"      # RPC模式: single/mixed (默认single)

# =====================================================================
# 用户配置变量 - 用户只需要配置以上这些变量
# =====================================================================


# =====================================================================
# 高性能配置缓存机制 - 防止重复加载和JSON解析
# =====================================================================
CONFIG_CACHE_KEY="${BLOCKCHAIN_NODE}_${RPC_MODE}"

# 检查是否需要重新加载配置
NEED_RELOAD="false"
if [[ "${CONFIG_LOADED:-}" != "true" ]]; then
    NEED_RELOAD="true"
elif [[ "${LAST_CONFIG_CACHE_KEY:-}" != "$CONFIG_CACHE_KEY" ]]; then
    NEED_RELOAD="true"
fi
if [[ "$NEED_RELOAD" == "false" ]]; then
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
        interface="eth0"  # Linux默认
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
    # Linux 生产环境 - 使用系统 tmpfs
    BASE_MEMORY_DIR="/dev/shm/blockchain-node-benchmark"
    DEPLOYMENT_ENV="production"
    echo "🐧 Linux生产环境" >&2
    
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
    BLOCK_HEIGHT_CACHE_FILE="${MEMORY_SHARE_DIR}/block_height_monitor_cache.json"
    BLOCK_HEIGHT_DATA_FILE="${LOGS_DIR}/block_height_monitor_$(date +%Y%m%d_%H%M%S).csv"
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
# 用户配置变量已移动到文件开头

# =====================================================================
# 统一区块链配置 - 集成所有8个区块链的完整配置
# =====================================================================
# ----- 多链主网端点动态配置 -----
# 根据BLOCKCHAIN_NODE动态设置MAINNET_RPC_URL
case "${BLOCKCHAIN_NODE,,}" in
    solana)
        MAINNET_RPC_URL="https://api.mainnet-beta.solana.com"
        ;;
    ethereum)
        MAINNET_RPC_URL="https://eth.llamarpc.com"
        ;;
    bsc)
        MAINNET_RPC_URL="https://bsc-dataseed.bnbchain.org"
        ;;
    base)
        MAINNET_RPC_URL="https://mainnet.base.org"
        ;;
    polygon)
        MAINNET_RPC_URL="https://polygon-rpc.com"
        ;;
    scroll)
        MAINNET_RPC_URL="https://rpc.scroll.io"
        ;;
    starknet)
        MAINNET_RPC_URL="https://starknet-mainnet.public.blastapi.io"
        ;;
    sui)
        MAINNET_RPC_URL="https://fullnode.mainnet.sui.io:443"
        ;;
    *)
        echo "⚠️ 警告: 未知的区块链类型 '${BLOCKCHAIN_NODE}'，使用默认Solana端点" >&2
        MAINNET_RPC_URL="https://api.mainnet-beta.solana.com"
        ;;
esac

UNIFIED_BLOCKCHAIN_CONFIG=$(cat <<'EOF'
{
  "blockchains": {
    "solana": {
      "chain_type": "solana",
      "rpc_url": "LOCAL_RPC_URL",
      "params": {
        "account_count": "ACCOUNT_COUNT",
        "output_file": "ACCOUNTS_OUTPUT_FILE",
        "target_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
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
      ],
      "rpc_methods": {
        "single": "getAccountInfo",
        "mixed": "getAccountInfo,getBalance,getTokenAccountBalance,getRecentBlockhash,getBlockHeight"
      },
      "param_formats": {
        "getAccountInfo": "single_address",
        "getBalance": "single_address",
        "getTokenAccountBalance": "single_address",
        "getRecentBlockhash": "no_params",
        "getBlockHeight": "no_params"
      }
    },
    "ethereum": {
      "chain_type": "ethereum",
      "rpc_url": "LOCAL_RPC_URL",
      "params": {
        "account_count": "ACCOUNT_COUNT",
        "output_file": "ACCOUNTS_OUTPUT_FILE",
        "target_address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "max_signatures": "ACCOUNT_MAX_SIGNATURES",
        "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
        "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
      },
      "methods": {
        "get_logs": "eth_getLogs",
        "get_transaction": "eth_getTransactionByHash"
      },
      "system_addresses": [
        "0x0000000000000000000000000000000000000000",
        "0x000000000000000000000000000000000000dead"
      ],
      "rpc_methods": {
        "single": "eth_getBalance",
        "mixed": "eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"
      },
      "param_formats": {
        "eth_getBalance": "address_latest",
        "eth_getTransactionCount": "address_latest",
        "eth_blockNumber": "no_params",
        "eth_gasPrice": "no_params"
      }
    },
    "bsc": {
      "chain_type": "bsc",
      "rpc_url": "LOCAL_RPC_URL",
      "params": {
        "account_count": "ACCOUNT_COUNT",
        "output_file": "ACCOUNTS_OUTPUT_FILE",
        "target_address": "0x250632378E573c6Be1AC2f97Fcdf00515d0Aa91B",
        "max_signatures": "ACCOUNT_MAX_SIGNATURES",
        "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
        "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
      },
      "methods": {
        "get_logs": "eth_getLogs",
        "get_transaction": "eth_getTransactionByHash"
      },
      "system_addresses": [
        "0x0000000000000000000000000000000000000000",
        "0x000000000000000000000000000000000000dead"
      ],
      "rpc_methods": {
        "single": "eth_getBalance",
        "mixed": "eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"
      },
      "param_formats": {
        "eth_getBalance": "address_latest",
        "eth_getTransactionCount": "address_latest",
        "eth_blockNumber": "no_params",
        "eth_gasPrice": "no_params"
      }
    },
    "base": {
      "chain_type": "base",
      "rpc_url": "LOCAL_RPC_URL",
      "params": {
        "account_count": "ACCOUNT_COUNT",
        "output_file": "ACCOUNTS_OUTPUT_FILE",
        "target_address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "max_signatures": "ACCOUNT_MAX_SIGNATURES",
        "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
        "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
      },
      "methods": {
        "get_logs": "eth_getLogs",
        "get_transaction": "eth_getTransactionByHash"
      },
      "system_addresses": [
        "0x0000000000000000000000000000000000000000",
        "0x000000000000000000000000000000000000dead"
      ],
      "rpc_methods": {
        "single": "eth_getBalance",
        "mixed": "eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"
      },
      "param_formats": {
        "eth_getBalance": "address_latest",
        "eth_getTransactionCount": "address_latest",
        "eth_blockNumber": "no_params",
        "eth_gasPrice": "no_params"
      }
    },
    "scroll": {
      "chain_type": "scroll",
      "rpc_url": "LOCAL_RPC_URL",
      "params": {
        "account_count": "ACCOUNT_COUNT",
        "output_file": "ACCOUNTS_OUTPUT_FILE",
        "target_address": "0x06eFdBFf2a14a7c8E15944D1F4A48F9F95F663A4",
        "max_signatures": "ACCOUNT_MAX_SIGNATURES",
        "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
        "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
      },
      "methods": {
        "get_logs": "eth_getLogs",
        "get_transaction": "eth_getTransactionByHash"
      },
      "system_addresses": [
        "0x0000000000000000000000000000000000000000",
        "0x000000000000000000000000000000000000dead"
      ],
      "rpc_methods": {
        "single": "eth_getBalance",
        "mixed": "eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"
      },
      "param_formats": {
        "eth_getBalance": "address_latest",
        "eth_getTransactionCount": "address_latest",
        "eth_blockNumber": "no_params",
        "eth_gasPrice": "no_params"
      }
    },
    "polygon": {
      "chain_type": "polygon",
      "rpc_url": "LOCAL_RPC_URL",
      "params": {
        "account_count": "ACCOUNT_COUNT",
        "output_file": "ACCOUNTS_OUTPUT_FILE",
        "target_address": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        "max_signatures": "ACCOUNT_MAX_SIGNATURES",
        "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
        "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
      },
      "methods": {
        "get_logs": "eth_getLogs",
        "get_transaction": "eth_getTransactionByHash"
      },
      "system_addresses": [
        "0x0000000000000000000000000000000000000000",
        "0x000000000000000000000000000000000000dead"
      ],
      "rpc_methods": {
        "single": "eth_getBalance",
        "mixed": "eth_getBalance,eth_getTransactionCount,eth_blockNumber,eth_gasPrice"
      },
      "param_formats": {
        "eth_getBalance": "address_latest",
        "eth_getTransactionCount": "address_latest",
        "eth_blockNumber": "no_params",
        "eth_gasPrice": "no_params"
      }
    },
    "starknet": {
      "chain_type": "starknet",
      "rpc_url": "LOCAL_RPC_URL",
      "params": {
        "account_count": "ACCOUNT_COUNT",
        "output_file": "ACCOUNTS_OUTPUT_FILE",
        "target_address": "0x068f5c6a61780768455de69077e07e89787839bf8166decfbf92b645209c0fb8",
        "max_signatures": "ACCOUNT_MAX_SIGNATURES",
        "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
        "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
      },
      "methods": {
        "get_events_native": "starknet_getEvents",
        "get_transaction": "starknet_getTransactionByHash"
      },
      "system_addresses": [],
      "rpc_methods": {
        "single": "starknet_getClassAt",
        "mixed": "starknet_getClassAt,starknet_getNonce,starknet_getStorageAt,starknet_blockNumber"
      },
      "param_formats": {
        "starknet_getClassAt": "latest_address",
        "starknet_getNonce": "latest_address",
        "starknet_getStorageAt": "address_key_latest",
        "starknet_blockNumber": "no_params"
      }
    },
    "sui": {
      "chain_type": "sui",
      "rpc_url": "LOCAL_RPC_URL",
      "params": {
        "account_count": "ACCOUNT_COUNT",
        "output_file": "ACCOUNTS_OUTPUT_FILE",
        "target_address": "0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC",
        "max_signatures": "ACCOUNT_MAX_SIGNATURES",
        "tx_batch_size": "ACCOUNT_TX_BATCH_SIZE",
        "semaphore_limit": "ACCOUNT_SEMAPHORE_LIMIT"
      },
      "methods": {
        "get_owned_objects": "suix_getOwnedObjects",
        "get_transaction": "sui_getTransactionBlock",
        "get_transactions": "suix_queryTransactionBlocks"
      },
      "system_addresses": ["0x1", "0x2", "0x3"],
      "rpc_methods": {
        "single": "sui_getObject",
        "mixed": "sui_getObject,sui_getObjectsOwnedByAddress,sui_getTotalTransactionBlocks,sui_getLatestCheckpointSequenceNumber"
      },
      "param_formats": {
        "sui_getObject": "address_with_options",
        "sui_getObjectsOwnedByAddress": "single_address",
        "sui_getTotalTransactionBlocks": "no_params",
        "sui_getLatestCheckpointSequenceNumber": "no_params"
      }
    }
  }
}
EOF
)

# =====================================================================
# 自动配置生成函数
# =====================================================================

# 验证BLOCKCHAIN_NODE值的有效性
validate_blockchain_node() {
    local blockchain_node="$1"
    local blockchain_node_lower
    blockchain_node_lower=$(echo "$blockchain_node" | tr '[:upper:]' '[:lower:]')
    # 支持的区块链列表
    local supported_blockchains=("solana" "ethereum" "bsc" "base" "scroll" "polygon" "starknet" "sui")
    # 检查是否在支持列表中
    for supported in "${supported_blockchains[@]}"; do
        if [[ "$blockchain_node_lower" == "$supported" ]]; then
            return 0  # 有效
        fi
    done
    # 无效的区块链类型
    echo "❌ 错误: 不支持的区块链类型 '$blockchain_node'" >&2
    echo "📋 支持的区块链类型:" >&2
    printf "   - %s\n" "${supported_blockchains[@]}" >&2
    echo "💡 提示: 请检查BLOCKCHAIN_NODE环境变量的值" >&2
    return 1  # 无效
}



# 基于BLOCKCHAIN_NODE自动生成配置
generate_auto_config() {
    local blockchain_node="${BLOCKCHAIN_NODE:-solana}"
    local blockchain_node_lower
    # 验证BLOCKCHAIN_NODE值
    if ! validate_blockchain_node "$blockchain_node"; then
        # 配置错误，直接退出
        exit 1
    fi
    blockchain_node_lower=$(echo "$blockchain_node" | tr '[:upper:]' '[:lower:]')
    echo "🎯 开始自动配置生成..." >&2
    echo "   BLOCKCHAIN_NODE原值: ${BLOCKCHAIN_NODE}" >&2
    echo "   目标区块链: $blockchain_node_lower" >&2
    
    # 性能优化：使用缓存的JSON解析结果
    local cache_var_name="CACHED_CHAIN_CONFIG_${blockchain_node_lower}"
    local cached_config="${!cache_var_name}"
    
    if [[ -n "$cached_config" ]]; then
        # 使用缓存的配置
        CHAIN_CONFIG="$cached_config"

    else
        local jq_query=".blockchains.\"$blockchain_node_lower\""
        CHAIN_CONFIG=$(echo "$UNIFIED_BLOCKCHAIN_CONFIG" | jq -c "$jq_query")
        # 缓存解析结果
        if [[ "$CHAIN_CONFIG" != "null" && -n "$CHAIN_CONFIG" ]]; then
            export "$cache_var_name"="$CHAIN_CONFIG"
        fi
    fi
    
    # 验证配置是否正确加载
    if [[ "$CHAIN_CONFIG" == "null" || -z "$CHAIN_CONFIG" ]]; then
        echo "❌ 错误: 无法加载 $blockchain_node_lower 的配置" >&2
        echo "   这表示UNIFIED_BLOCKCHAIN_CONFIG中缺少该区块链的配置" >&2
        echo "   请检查配置文件的完整性" >&2
        exit 1
    fi
    
    # 从CHAIN_CONFIG中获取RPC方法 - 修复缓存逻辑
    local rpc_mode_lower
    rpc_mode_lower=$(echo "${RPC_MODE:-single}" | tr '[:upper:]' '[:lower:]')
    
    # 性能优化：使用缓存的RPC方法解析结果
    local rpc_cache_var_name="CACHED_RPC_METHODS_${blockchain_node_lower}_${rpc_mode_lower}"
    local cached_rpc_methods="${!rpc_cache_var_name}"
    
    if [[ -n "$cached_rpc_methods" ]]; then
        # 使用缓存的RPC方法
        CURRENT_RPC_METHODS_STRING="$cached_rpc_methods"
    else
        # 重新计算并缓存
        CURRENT_RPC_METHODS_STRING=$(echo "$CHAIN_CONFIG" | jq -r ".rpc_methods.\"$rpc_mode_lower\"")
        # 缓存RPC方法解析结果
        if [[ "$CURRENT_RPC_METHODS_STRING" != "null" && -n "$CURRENT_RPC_METHODS_STRING" ]]; then
            export "$rpc_cache_var_name"="$CURRENT_RPC_METHODS_STRING"
        fi
    fi
    # 直接使用配置，框架配置是完整的
    # 无需验证和回退机制
    # 框架配置是完整的，直接使用
    
    # 转换为数组
    IFS=',' read -ra CURRENT_RPC_METHODS_ARRAY <<< "$CURRENT_RPC_METHODS_STRING"
    
    # 配置一致性验证（混合方案的安全检查）
    validate_config_consistency
    
    echo "🎯 自动配置完成:" >&2
    echo "   区块链: $blockchain_node_lower" >&2
    echo "   RPC方法: $CURRENT_RPC_METHODS_STRING" >&2
    echo "   方法数量: ${#CURRENT_RPC_METHODS_ARRAY[@]}" >&2
}

# 配置一致性验证函数（混合方案的核心安全机制）
validate_config_consistency() {
    local blockchain_node_lower
    blockchain_node_lower=$(echo "${BLOCKCHAIN_NODE:-solana}" | tr '[:upper:]' '[:lower:]')
    local rpc_mode_lower
    rpc_mode_lower=$(echo "${RPC_MODE:-single}" | tr '[:upper:]' '[:lower:]')
    
    # 验证CHAIN_CONFIG和CURRENT_RPC_METHODS_STRING的一致性
    if [[ -n "$CHAIN_CONFIG" && "$CHAIN_CONFIG" != "null" ]]; then
        local expected_method
        expected_method=$(echo "$CHAIN_CONFIG" | jq -r ".rpc_methods.\"$rpc_mode_lower\"")
        
        if [[ -n "$expected_method" && "$expected_method" != "null" ]]; then
            if [[ "$CURRENT_RPC_METHODS_STRING" != "$expected_method" ]]; then
                echo "⚠️ 配置不一致检测: 期望 '$expected_method', 实际 '$CURRENT_RPC_METHODS_STRING'" >&2
                echo "🔧 自动修复配置不一致..." >&2
                CURRENT_RPC_METHODS_STRING="$expected_method"
                
                # 更新缓存
                local rpc_cache_var_name="CACHED_RPC_METHODS_${blockchain_node_lower}_${rpc_mode_lower}"
                export "$rpc_cache_var_name"="$CURRENT_RPC_METHODS_STRING"
                
                echo "✅ 配置一致性已修复" >&2
            fi
        fi
    fi
}

# 清理过期缓存函数
clear_stale_cache() {
    local current_blockchain="${BLOCKCHAIN_NODE:-solana}"
    local current_rpc_mode="${RPC_MODE:-single}"
    
    # 清理不匹配当前配置的缓存
    for var in $(env | grep "^CACHED_RPC_METHODS_" | cut -d= -f1); do
        if [[ "$var" != "CACHED_RPC_METHODS_${current_blockchain}_${current_rpc_mode}" ]]; then
            unset "$var"
        fi
    done
}

# =====================================================================
# 自动配置生成函数
# =====================================================================

# 重新设计的RPC方法获取函数
get_current_rpc_methods() {
    local rpc_mode_lower
    rpc_mode_lower=$(echo "${RPC_MODE}" | tr '[:upper:]' '[:lower:]')
    
    # 从CHAIN_CONFIG的rpc_methods字段中获取对应模式的方法
    local methods_string
    methods_string=$(echo "$CHAIN_CONFIG" | jq -r ".rpc_methods.\"$rpc_mode_lower\"")
    
    # 直接使用配置，框架配置是完整的
    
    # 框架配置是完整的，直接使用
    
    echo "$methods_string"
}

get_param_format_from_json() {
    local method="$1"
    local format
    
    # 性能优化：使用缓存的参数格式
    local param_cache_var_name="CACHED_PARAM_FORMAT_${method}"
    local cached_format="${!param_cache_var_name}"
    
    if [[ -n "$cached_format" ]]; then
        echo "$cached_format"
        return 0
    fi
    
    format=$(echo "$CHAIN_CONFIG" | jq -r ".param_formats.\"$method\"")
    
    if [[ "$format" == "null" || -z "$format" ]]; then
        format="single_address"  # 默认格式
    fi
    
    export "$param_cache_var_name"="$format"
    echo "$format"
}

# 验证关键变量是否正确设置
if [[ -z "$ACCOUNTS_OUTPUT_FILE" ]]; then
    echo "⚠️ 警告: ACCOUNTS_OUTPUT_FILE 未正确设置" >&2
fi
if [[ -z "$LOCAL_RPC_URL" ]]; then
    echo "⚠️ 警告: LOCAL_RPC_URL 未正确设置" >&2
fi

# 执行自动配置生成
echo "调用generate_auto_config前: BLOCKCHAIN_NODE=$BLOCKCHAIN_NODE" >&2
generate_auto_config

clear_config_cache() {
    local cache_pattern="$1"
    if [[ -z "$cache_pattern" ]]; then
        cache_pattern="CACHED_"
    fi
    # 清理匹配模式的缓存变量
    for var in $(compgen -v | grep "^${cache_pattern}"); do
        unset "$var"
    done
}

export -f get_current_rpc_methods get_param_format_from_json clear_config_cache generate_auto_config validate_config_consistency clear_stale_cache
export CONFIG_LOADED="true"
export LAST_BLOCKCHAIN_NODE="${BLOCKCHAIN_NODE:-solana}"
export LAST_CONFIG_CACHE_KEY="$CONFIG_CACHE_KEY"
export ACCOUNTS_OUTPUT_FILE SINGLE_METHOD_TARGETS_FILE MIXED_METHOD_TARGETS_FILE
export LOCAL_RPC_URL MAINNET_RPC_URL BLOCKCHAIN_NODE BLOCKCHAIN_PROCESS_NAMES RPC_MODE
export ACCOUNT_COUNT ACCOUNT_OUTPUT_FILE ACCOUNT_MAX_SIGNATURES ACCOUNT_TX_BATCH_SIZE ACCOUNT_SEMAPHORE_LIMIT
export CHAIN_CONFIG
export CURRENT_RPC_METHODS_STRING

export DATA_DIR CURRENT_TEST_DIR LOGS_DIR REPORTS_DIR VEGETA_RESULTS_DIR TMP_DIR ARCHIVES_DIR
export ERROR_LOG_DIR PYTHON_ERROR_LOG_DIR MEMORY_SHARE_DIR
export BLOCK_HEIGHT_CACHE_FILE BLOCK_HEIGHT_DATA_FILE QPS_STATUS_FILE TEST_SESSION_DIR
export MONITORING_OVERHEAD_LOG PERFORMANCE_LOG ERROR_LOG TEMP_FILE_PATTERN

export NETWORK_MAX_BANDWIDTH_MBPS DEPLOYMENT_PLATFORM ENA_MONITOR_ENABLED
export NETWORK_INTERFACE BASE_MEMORY_DIR DEPLOYMENT_ENV
export BASE_FRAMEWORK_DIR BASE_DATA_DIR DEPLOYMENT_STRUCTURE
export BLOCKCHAIN_PROCESS_NAMES_STR="${BLOCKCHAIN_PROCESS_NAMES[*]}"

echo "🔧 RPC方法配置完成:" >&2
echo "   区块链类型: $BLOCKCHAIN_NODE" >&2
echo "   RPC模式: $RPC_MODE" >&2
echo "   当前方法: $CURRENT_RPC_METHODS_STRING" >&2
echo "🎉 分层配置加载完成！" >&2