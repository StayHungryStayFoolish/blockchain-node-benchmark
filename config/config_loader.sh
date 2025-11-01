#!/bin/bash
# =====================================================================
# Blockchain Node Benchmark Framework - Unified Configuration Loader
# =====================================================================
# Function: Load all configuration layers in order and perform dynamic configuration detection
# =====================================================================

# =====================================================================
# User Configuration Variables - Users only need to configure these variables
# =====================================================================

# ----- Basic Configuration -----
# Blockchain Node Local RPC Endpoint
LOCAL_RPC_URL="${LOCAL_RPC_URL:-http://localhost:8899}"

# ----- Blockchain Node Configuration -----
BLOCKCHAIN_NODE="${BLOCKCHAIN_NODE:-solana}"

# Force ensure BLOCKCHAIN_NODE is lowercase
BLOCKCHAIN_NODE=$(echo "$BLOCKCHAIN_NODE" | tr '[:upper:]' '[:lower:]')

# Blockchain node running process names
BLOCKCHAIN_PROCESS_NAMES=(
    "blockchain"
    "validator"
    "agave-validator"
    "node.service"
)

# Account and target file configuration
ACCOUNT_COUNT=1000                                                    # Default account count

# ----- Account Fetching Tool Configuration -----
# Detailed configuration parameters for account fetching tool
ACCOUNT_MAX_SIGNATURES=50000                                          # Maximum signature count
ACCOUNT_TX_BATCH_SIZE=100                                             # Transaction batch size
ACCOUNT_SEMAPHORE_LIMIT=10                                            # Concurrency limit

# ----- RPC Mode Configuration -----
RPC_MODE="${RPC_MODE:-single}"      # RPC mode: single/mixed (default single)

# =====================================================================
# User Configuration Variables - Users only need to configure the above variables
# =====================================================================


# =====================================================================
# High-Performance Configuration Caching Mechanism - Prevent repeated loading and JSON parsing
# =====================================================================
# Load configuration directly
echo "🔧 Starting configuration loading..." >&2

# Check if configuration is already loaded, avoid duplicate output
if [[ "${CONFIG_ALREADY_LOADED:-}" == "true" && "${FORCE_CONFIG_RELOAD:-}" != "true" ]]; then
    return 0
fi

# Get configuration directory
CONFIG_DIR="$(dirname "${BASH_SOURCE[0]}")"

# Load configuration layers in order
echo "🔧 Loading layered configuration..." >&2

# 1. Load user configuration layer
if [[ -f "${CONFIG_DIR}/user_config.sh" ]]; then
    source "${CONFIG_DIR}/user_config.sh"
    echo "✅ User configuration layer loaded" >&2
else
    echo "❌ User configuration layer file does not exist: ${CONFIG_DIR}/user_config.sh" >&2
    exit 1
fi

# 2. Load system configuration layer
if [[ -f "${CONFIG_DIR}/system_config.sh" ]]; then
    source "${CONFIG_DIR}/system_config.sh"
    echo "✅ System configuration layer loaded" >&2
else
    echo "❌ System configuration layer file does not exist: ${CONFIG_DIR}/system_config.sh" >&2
    exit 1
fi

# 3. Load internal configuration layer
if [[ -f "${CONFIG_DIR}/internal_config.sh" ]]; then
    source "${CONFIG_DIR}/internal_config.sh"
    echo "✅ Internal configuration layer loaded" >&2
else
    echo "❌ Internal configuration layer file does not exist: ${CONFIG_DIR}/internal_config.sh" >&2
    exit 1
fi

# =====================================================================
# Dynamic Configuration Detection and Calculation
# =====================================================================

# ----- Automatically Calculated Network Configuration -----
# Automatically convert to Mbps (for internal calculation, users do not need to modify)
NETWORK_MAX_BANDWIDTH_MBPS=$((NETWORK_MAX_BANDWIDTH_GBPS * 1000))

# ----- Deployment Platform Detection Function -----
# Automatically detect deployment platform and adjust ENA monitoring configuration
detect_deployment_platform() {
    if [[ "$DEPLOYMENT_PLATFORM" == "auto" ]]; then
        echo "🔍 Auto-detecting deployment platform..." >&2
        
        # Check if in AWS environment (via AWS metadata service)
        if curl -s --max-time 3 --connect-timeout 2 "${AWS_METADATA_ENDPOINT}/${AWS_METADATA_API_VERSION}/meta-data/instance-id" >/dev/null 2>&1; then
            DEPLOYMENT_PLATFORM="aws"
            ENA_MONITOR_ENABLED=true
            echo "✅ AWS environment detected, ENA monitoring enabled" >&2
        else
            DEPLOYMENT_PLATFORM="other"
            ENA_MONITOR_ENABLED=false
            echo "ℹ️  Non-AWS environment detected (IDC/other cloud), ENA monitoring disabled" >&2
        fi
    else
        echo "🔧 Using manually configured deployment platform: $DEPLOYMENT_PLATFORM" >&2
        case "$DEPLOYMENT_PLATFORM" in
            "aws")
                ENA_MONITOR_ENABLED=true
                echo "✅ AWS environment, ENA monitoring enabled" >&2
                ;;
            "other"|"idc")
                ENA_MONITOR_ENABLED=false
                echo "ℹ️  Non-AWS environment, ENA monitoring disabled" >&2
                ;;
            *)
                echo "⚠️  Unknown deployment platform: $DEPLOYMENT_PLATFORM, ENA monitoring disabled" >&2
                ENA_MONITOR_ENABLED=false
                ;;
        esac
    fi
    
    # Output final configuration
    echo "📊 Deployment platform configuration:" >&2
    echo "   Platform type: $DEPLOYMENT_PLATFORM" >&2
    echo "   ENA monitoring: $ENA_MONITOR_ENABLED" >&2
    
    # Mark platform detection as completed and export to subprocesses
    DEPLOYMENT_PLATFORM_DETECTED=true
}

# ----- Network Interface Detection Function -----
# Automatically detect ENA network interface
detect_network_interface() {
    # Prioritize detecting ENA interfaces
    local ena_interfaces
    if command -v ip >/dev/null 2>&1; then
        ena_interfaces=($(ip link show 2>/dev/null | grep -E "^[0-9]+: (eth|ens|enp)" | grep "state UP" | cut -d: -f2 | tr -d ' '))
    else
        ena_interfaces=()
    fi
    
    # If ENA interface found, prioritize using the first one
    if [[ ${#ena_interfaces[@]} -gt 0 ]]; then
        NETWORK_INTERFACE="${ena_interfaces[0]}"
        return 0
    fi
    
    # If no ENA interface found, use traditional detection method
    local interface=""
    if command -v ip >/dev/null 2>&1; then
        interface=$(ip route 2>/dev/null | grep default | awk '{print $5}' | head -1)
    elif command -v route >/dev/null 2>&1; then
        interface=$(route get default 2>/dev/null | grep interface | awk '{print $2}')
    elif command -v netstat >/dev/null 2>&1; then
        interface=$(netstat -rn 2>/dev/null | grep default | awk '{print $6}' | head -1)
    fi
    
    # If still not found, use system default
    if [[ -z "$interface" ]]; then
        interface="eth0"  # Linux default
    fi
    
    NETWORK_INTERFACE="$interface"
}

# ----- Path Detection and Configuration Function -----
ACCOUNT_OUTPUT_FILE="active_accounts.txt"                             # Output filename

# Detect deployment environment and set paths
detect_deployment_paths() {
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local framework_dir="$(dirname "$script_dir")"
    local deployment_dir="$(dirname "$framework_dir")"
    
    echo "   Framework directory: $framework_dir" >&2
    echo "   Deployment directory: $deployment_dir" >&2
    
    # Set memory sharing directory (independent of data directory, maintain system-level path)
    # Linux production environment - use system tmpfs
    BASE_MEMORY_DIR="/dev/shm/blockchain-node-benchmark"
    echo "🐧 Linux production environment" >&2
    
    # Standardized path configuration
    BASE_FRAMEWORK_DIR="$framework_dir"
    BASE_DATA_DIR="${BLOCKCHAIN_BENCHMARK_DATA_DIR:-${deployment_dir}/blockchain-node-benchmark-result}"
    
    # Validate and fix path settings
    if [[ -z "$BASE_DATA_DIR" || "$BASE_DATA_DIR" == "/blockchain-node-benchmark-result" ]]; then
        echo "⚠️ Data directory path abnormal, using default path" >&2
        BASE_DATA_DIR="${HOME}/blockchain-node-benchmark-result"
    fi

    echo "   Data directory: $BASE_DATA_DIR" >&2
    
    # Support environment variable override
    if [[ -n "${BLOCKCHAIN_BENCHMARK_DATA_DIR:-}" ]]; then
        echo "   (Using environment variable: BLOCKCHAIN_BENCHMARK_DATA_DIR)" >&2
    fi
    
    # Set directory structure - based on new standardized paths
    # Main data directory (QPS test exclusive)
    DATA_DIR="${BASE_DATA_DIR}"
    # Current test data directory
    CURRENT_TEST_DIR="${DATA_DIR}/current"
    # Log directory (performance monitoring data)
    LOGS_DIR="${CURRENT_TEST_DIR}/logs"
    # Report directory (analysis reports and charts)
    REPORTS_DIR="${CURRENT_TEST_DIR}/reports"
    # Vegeta results directory (stress test raw data)
    VEGETA_RESULTS_DIR="${CURRENT_TEST_DIR}/vegeta_results"
    # Temporary file directory (runtime temporary data)
    TMP_DIR="${CURRENT_TEST_DIR}/tmp"
    # Archive directory (historical test data)
    ARCHIVES_DIR="${DATA_DIR}/archives"
    # Error handling and log directories
    ERROR_LOG_DIR="${CURRENT_TEST_DIR}/${ERROR_LOG_SUBDIR}"
    PYTHON_ERROR_LOG_DIR="${CURRENT_TEST_DIR}/${PYTHON_ERROR_LOG_SUBDIR}"
    
    # Memory sharing directory (independent of data directory, use system-level path)
    MEMORY_SHARE_DIR="${BASE_MEMORY_DIR}"
    
    # Generate unified session timestamp (ensure all processes use the same timestamp)
    if [[ -z "${SESSION_TIMESTAMP:-}" ]]; then
        SESSION_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        export SESSION_TIMESTAMP
    fi
    
    # Set dynamic path variables (using unified session timestamp)
    BLOCK_HEIGHT_CACHE_FILE="${MEMORY_SHARE_DIR}/block_height_monitor_cache.json"
    BLOCK_HEIGHT_DATA_FILE="${LOGS_DIR}/block_height_monitor_${SESSION_TIMESTAMP}.csv"
    ACCOUNTS_OUTPUT_FILE="${TMP_DIR}/${ACCOUNT_OUTPUT_FILE}"
    SINGLE_METHOD_TARGETS_FILE="${TMP_DIR}/targets_single.json"
    MIXED_METHOD_TARGETS_FILE="${TMP_DIR}/targets_mixed.json"
    QPS_STATUS_FILE="${MEMORY_SHARE_DIR}/qps_status.json"
    TEST_SESSION_DIR="${TMP_DIR}/session_${SESSION_TIMESTAMP}"
    
    # Set monitoring overhead optimization related log file paths (using unified timestamp)
    MONITORING_OVERHEAD_LOG="${LOGS_DIR}/monitoring_overhead_${SESSION_TIMESTAMP}.csv"
    PERFORMANCE_LOG="${LOGS_DIR}/monitoring_performance_${SESSION_TIMESTAMP}.log"
    ERROR_LOG="${LOGS_DIR}/monitoring_errors_${SESSION_TIMESTAMP}.log"
    
    # Temporary file pattern (for cleanup)
    TEMP_FILE_PATTERN="${TMP_DIR}/${TEMP_FILE_PREFIX}-*"
    
    # Output final configuration
    echo "📋 Path configuration completed:" >&2
    echo "   Framework directory: $BASE_FRAMEWORK_DIR" >&2
    echo "   Data directory: $BASE_DATA_DIR" >&2
    echo "   Memory sharing: $MEMORY_SHARE_DIR" >&2
    
    # Mark path detection as completed and export to subprocesses
    DEPLOYMENT_PATHS_DETECTED=true
    export DEPLOYMENT_PATHS_DETECTED
}

# ----- Directory Creation Function -----
# Safely create directories function
create_directories_safely() {
    local dirs=("$@")
    local created_dirs=()
    local failed_dirs=()
    
    echo "🔧 Creating necessary directories..." >&2
    
    for dir in "${dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            if mkdir -p "$dir" 2>/dev/null; then
                echo "✅ Created directory: $dir" >&2
                created_dirs+=("$dir")
                chmod 755 "$dir" 2>/dev/null || true
            else
                echo "❌ Unable to create directory: $dir" >&2
                failed_dirs+=("$dir")
            fi
        else
            echo "✅ Directory already exists: $dir" >&2
        fi
    done
    
    # Mark directory creation as completed and export to subprocesses
    DIRECTORIES_CREATED=true
    export DIRECTORIES_CREATED
    
    # Return result summary
    if [[ ${#failed_dirs[@]} -gt 0 ]]; then
        echo "⚠️  Some directories failed to create: ${failed_dirs[*]}" >&2
        return 1
    else
        echo "✅ All directories created successfully" >&2
        return 0
    fi
}

# =====================================================================
# Execute Dynamic Configuration Detection
# =====================================================================

# Execute deployment platform detection
detect_deployment_platform

# Execute network interface detection
detect_network_interface

# Execute path detection and configuration
detect_deployment_paths

# Create necessary directories
create_directories_safely "$DATA_DIR" "$CURRENT_TEST_DIR" "$LOGS_DIR" "$REPORTS_DIR" "$VEGETA_RESULTS_DIR" "$TMP_DIR" "$ARCHIVES_DIR" "$ERROR_LOG_DIR" "$PYTHON_ERROR_LOG_DIR" "$MEMORY_SHARE_DIR"

# =====================================================================
# Configure Blockchain Node & On-chain Active Addresses
# =====================================================================
# User configuration variables have been moved to the beginning of the file

# =====================================================================
# Unified Blockchain Configuration - Integrate complete configuration for all 8 blockchains
# =====================================================================
# ----- Multi-chain Mainnet Endpoint Dynamic Configuration -----
# Dynamically set MAINNET_RPC_URL based on BLOCKCHAIN_NODE
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
        echo "⚠️ Warning: Unknown blockchain type '${BLOCKCHAIN_NODE}', using default Solana endpoint" >&2
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
# Automatic Configuration Generation Functions
# =====================================================================

# Validate BLOCKCHAIN_NODE value validity
validate_blockchain_node() {
    local blockchain_node="$1"
    local blockchain_node_lower
    blockchain_node_lower=$(echo "$blockchain_node" | tr '[:upper:]' '[:lower:]')
    # Supported blockchain list
    local supported_blockchains=("solana" "ethereum" "bsc" "base" "scroll" "polygon" "starknet" "sui")
    # Check if in supported list
    for supported in "${supported_blockchains[@]}"; do
        if [[ "$blockchain_node_lower" == "$supported" ]]; then
            return 0  # Valid
        fi
    done
    # Invalid blockchain type
    echo "❌ Error: Unsupported blockchain type '$blockchain_node'" >&2
    echo "📋 Supported blockchain types:" >&2
    printf "   - %s\n" "${supported_blockchains[@]}" >&2
    echo "💡 Tip: Please check the value of BLOCKCHAIN_NODE environment variable" >&2
    return 1  # Invalid
}

# Configuration consistency validation function
validate_config_consistency() {
    local blockchain_node_lower
    blockchain_node_lower=$(echo "${BLOCKCHAIN_NODE:-solana}" | tr '[:upper:]' '[:lower:]')
    local rpc_mode_lower
    rpc_mode_lower=$(echo "${RPC_MODE:-single}" | tr '[:upper:]' '[:lower:]')

    # Validate consistency between CHAIN_CONFIG and CURRENT_RPC_METHODS_STRING
    if [[ -n "$CHAIN_CONFIG" && "$CHAIN_CONFIG" != "null" ]]; then
        local expected_method
        expected_method=$(echo "$CHAIN_CONFIG" | jq -r ".rpc_methods.\"$rpc_mode_lower\"")

        if [[ -n "$expected_method" && "$expected_method" != "null" ]]; then
            if [[ "$CURRENT_RPC_METHODS_STRING" != "$expected_method" ]]; then
                echo "⚠️ Configuration inconsistency detected: Expected '$expected_method', Actual '$CURRENT_RPC_METHODS_STRING'" >&2
                echo "🔧 Auto-fixing configuration inconsistency..." >&2
                CURRENT_RPC_METHODS_STRING="$expected_method"

                # Update cache
                local rpc_cache_var_name="CACHED_RPC_METHODS_${blockchain_node_lower}_${rpc_mode_lower}"
                export "$rpc_cache_var_name"="$CURRENT_RPC_METHODS_STRING"

                echo "✅ Configuration consistency fixed" >&2
            fi
        fi
    fi
}

# Automatically generate configuration based on BLOCKCHAIN_NODE
generate_auto_config() {
    # Clear all configuration cache, ensure clean environment, avoid conflicts between different blockchain configurations
    clear_config_cache
    
    local blockchain_node="${BLOCKCHAIN_NODE:-solana}"
    local blockchain_node_lower
    # Validate BLOCKCHAIN_NODE value
    if ! validate_blockchain_node "$blockchain_node"; then
        # Configuration error, exit directly
        exit 1
    fi
    blockchain_node_lower=$(echo "$blockchain_node" | tr '[:upper:]' '[:lower:]')
    echo "🎯 Starting automatic configuration generation..." >&2
    echo "   BLOCKCHAIN_NODE original value: ${BLOCKCHAIN_NODE}" >&2
    echo "   Target blockchain: $blockchain_node_lower" >&2
    
    # Performance optimization: Use cached JSON parsing results
    local cache_var_name="CACHED_CHAIN_CONFIG_${blockchain_node_lower}"
    local cached_config="${!cache_var_name:-}"
    
    if [[ -n "$cached_config" ]]; then
        # Use cached configuration
        CHAIN_CONFIG="$cached_config"

    else
        local jq_query=".blockchains.\"$blockchain_node_lower\""
        CHAIN_CONFIG=$(echo "$UNIFIED_BLOCKCHAIN_CONFIG" | jq -c "$jq_query")
        # Cache parsing result
        if [[ "$CHAIN_CONFIG" != "null" && -n "$CHAIN_CONFIG" ]]; then
            export "$cache_var_name"="$CHAIN_CONFIG"
        fi
    fi
    
    # Validate if configuration loaded correctly
    if [[ "$CHAIN_CONFIG" == "null" || -z "$CHAIN_CONFIG" ]]; then
        echo "❌ Error: Unable to load configuration for $blockchain_node_lower" >&2
        echo "   This indicates missing configuration for this blockchain in UNIFIED_BLOCKCHAIN_CONFIG" >&2
        echo "   Please check configuration file integrity" >&2
        exit 1
    fi
    
    # Get RPC methods from CHAIN_CONFIG - Fix caching logic
    local rpc_mode_lower
    rpc_mode_lower=$(echo "${RPC_MODE:-single}" | tr '[:upper:]' '[:lower:]')
    
    # Performance optimization: Use cached RPC method parsing results
    local rpc_cache_var_name="CACHED_RPC_METHODS_${blockchain_node_lower}_${rpc_mode_lower}"
    local cached_rpc_methods="${!rpc_cache_var_name:-}"
    
    if [[ -n "$cached_rpc_methods" ]]; then
        # Use cached RPC methods
        CURRENT_RPC_METHODS_STRING="$cached_rpc_methods"
    else
        # Recalculate and cache
        CURRENT_RPC_METHODS_STRING=$(echo "$CHAIN_CONFIG" | jq -r ".rpc_methods.\"$rpc_mode_lower\"")
        # Cache RPC method parsing result
        if [[ "$CURRENT_RPC_METHODS_STRING" != "null" && -n "$CURRENT_RPC_METHODS_STRING" ]]; then
            export "$rpc_cache_var_name"="$CURRENT_RPC_METHODS_STRING"
        fi
    fi
    # Use configuration directly, framework configuration is complete
    # No need for validation and fallback mechanism
    # Framework configuration is complete, use directly
    
    # Convert to array
    IFS=',' read -ra CURRENT_RPC_METHODS_ARRAY <<< "$CURRENT_RPC_METHODS_STRING"
    
    # Configuration consistency validation (safety check for hybrid solution)
    validate_config_consistency
    
    echo "🎯 Automatic configuration completed:" >&2
    echo "   Blockchain: $blockchain_node_lower" >&2
    echo "   RPC methods: $CURRENT_RPC_METHODS_STRING" >&2
    echo "   Method count: ${#CURRENT_RPC_METHODS_ARRAY[@]}" >&2
}

# Clear expired cache function
clear_config_cache() {
    local cache_pattern="${1:-CACHED_}"
    
    # Clear cache variables
    for var in $(compgen -v | grep "^${cache_pattern}" 2>/dev/null || true); do
        unset "$var" 2>/dev/null || true
    done
    
    # Clear deployment path detection variables
    unset DEPLOYMENT_PATHS_DETECTED 2>/dev/null || true
    
    echo "🧹 Configuration cache cleared" >&2
}

# =====================================================================
# Automatic Configuration Generation Functions
# =====================================================================

# Redesigned RPC method retrieval function
get_current_rpc_methods() {
    local rpc_mode_lower
    rpc_mode_lower=$(echo "${RPC_MODE}" | tr '[:upper:]' '[:lower:]')
    
    # Get corresponding mode methods from CHAIN_CONFIG's rpc_methods field
    local methods_string
    methods_string=$(echo "$CHAIN_CONFIG" | jq -r ".rpc_methods.\"$rpc_mode_lower\"")
    
    # Use configuration directly, framework configuration is complete
    
    # Framework configuration is complete, use directly
    
    echo "$methods_string"
}

get_param_format_from_json() {
    local method="$1"
    local format
    
    # Performance optimization: Use cached parameter format
    local param_cache_var_name="CACHED_PARAM_FORMAT_${method}"
    local cached_format="${!param_cache_var_name:-}"
    
    if [[ -n "$cached_format" ]]; then
        echo "$cached_format"
        return 0
    fi
    
    format=$(echo "$CHAIN_CONFIG" | jq -r ".param_formats.\"$method\"")
    
    if [[ "$format" == "null" || -z "$format" ]]; then
        format="single_address"  # Default format
    fi
    
    export "$param_cache_var_name"="$format"
    echo "$format"
}

# Validate if key variables are correctly set
if [[ -z "$ACCOUNTS_OUTPUT_FILE" ]]; then
    echo "⚠️ Warning: ACCOUNTS_OUTPUT_FILE not correctly set" >&2
fi
if [[ -z "$LOCAL_RPC_URL" ]]; then
    echo "⚠️ Warning: LOCAL_RPC_URL not correctly set" >&2
fi

# Execute automatic configuration generation
echo "Before calling generate_auto_config: BLOCKCHAIN_NODE=$BLOCKCHAIN_NODE" >&2
generate_auto_config

export -f get_current_rpc_methods get_param_format_from_json clear_config_cache generate_auto_config validate_config_consistency
export LAST_BLOCKCHAIN_NODE="${BLOCKCHAIN_NODE:-solana}"
export ACCOUNTS_OUTPUT_FILE SINGLE_METHOD_TARGETS_FILE MIXED_METHOD_TARGETS_FILE
export LOCAL_RPC_URL MAINNET_RPC_URL BLOCKCHAIN_NODE BLOCKCHAIN_PROCESS_NAMES RPC_MODE
export ACCOUNT_COUNT ACCOUNT_OUTPUT_FILE ACCOUNT_MAX_SIGNATURES ACCOUNT_TX_BATCH_SIZE ACCOUNT_SEMAPHORE_LIMIT
export CHAIN_CONFIG DEPLOYMENT_PLATFORM_DETECTED
export CURRENT_RPC_METHODS_STRING

export DATA_DIR CURRENT_TEST_DIR LOGS_DIR REPORTS_DIR VEGETA_RESULTS_DIR TMP_DIR ARCHIVES_DIR
export ERROR_LOG_DIR PYTHON_ERROR_LOG_DIR MEMORY_SHARE_DIR
export BLOCK_HEIGHT_CACHE_FILE BLOCK_HEIGHT_DATA_FILE QPS_STATUS_FILE TEST_SESSION_DIR
export MONITORING_OVERHEAD_LOG PERFORMANCE_LOG ERROR_LOG TEMP_FILE_PATTERN SESSION_TIMESTAMP

export NETWORK_MAX_BANDWIDTH_MBPS DEPLOYMENT_PLATFORM ENA_MONITOR_ENABLED
export NETWORK_INTERFACE BASE_MEMORY_DIR
export BASE_FRAMEWORK_DIR BASE_DATA_DIR
export BLOCKCHAIN_PROCESS_NAMES_STR="${BLOCKCHAIN_PROCESS_NAMES[*]}"

# ENA field configuration - Support development environment testing
export ENA_ALLOWANCE_FIELDS=${ENA_ALLOWANCE_FIELDS:-"bw_in_allowance_exceeded,bw_out_allowance_exceeded,pps_allowance_exceeded,conntrack_allowance_exceeded,linklocal_allowance_exceeded,conntrack_allowance_available"}

export CONFIG_ALREADY_LOADED="true"

echo "🔧 RPC method configuration completed:" >&2
echo "   Blockchain type: $BLOCKCHAIN_NODE" >&2
echo "   RPC mode: $RPC_MODE" >&2
echo "   Current methods: $CURRENT_RPC_METHODS_STRING" >&2
echo "🎉 Layered configuration loading completed!" >&2