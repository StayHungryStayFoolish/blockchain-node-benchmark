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

# 4. Load deployment-mode detector (v1.3 plan §S2)
# Detects runtime environment (VM / Docker / K8s), orthogonal to
# DEPLOYMENT_PLATFORM (cloud provider). Together they form (platform, mode)
# matrix used by cloud_variants/ and k8s_paths.sh.
if [[ -f "${CONFIG_DIR}/deployment_mode_detector.sh" ]]; then
    source "${CONFIG_DIR}/deployment_mode_detector.sh"
    echo "✅ Deployment mode detector loaded" >&2
else
    echo "⚠️  Deployment mode detector not found: ${CONFIG_DIR}/deployment_mode_detector.sh — falling back to vm_bare assumption" >&2
    DEPLOYMENT_MODE="vm_bare"
    DEPLOYMENT_MODE_DETECTED=true
    DEPLOYMENT_MODE_SOURCE="missing_detector_fallback"
    export DEPLOYMENT_MODE DEPLOYMENT_MODE_DETECTED DEPLOYMENT_MODE_SOURCE
fi

# 5. Load K8s/container path templates (HOST_PROC / HOST_SYS / cgroup paths)
# Depends on DEPLOYMENT_MODE being set (above).
if [[ -f "${CONFIG_DIR}/k8s_paths.sh" ]]; then
    source "${CONFIG_DIR}/k8s_paths.sh"
    echo "✅ K8s paths template loaded" >&2
else
    echo "⚠️  K8s paths template not found: ${CONFIG_DIR}/k8s_paths.sh — using local /proc /sys" >&2
    HOST_PROC="${HOST_PROC:-/proc}"
    HOST_SYS="${HOST_SYS:-/sys}"
    HOST_ROOT="${HOST_ROOT:-/}"
    export HOST_PROC HOST_SYS HOST_ROOT
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
    # ── Provider 解析统一入口 (single source of truth = config/cloud_provider.sh) ──
    # 修复 (2026-06-01): 旧实现把 cloud_provider.sh 的 source + provider getter 加载
    # 只挂在 DEPLOYMENT_PLATFORM=="auto" 分支, 导致用户【手动指定】(CLOUD_PROVIDER=aws
    # 或 DEPLOYMENT_PLATFORM=aws) 时 getter 不加载 → convert_to_standard_iops 退化
    # passthrough → AWS IOPS 公式静默失效 (回退 7 个月前 bug)。现统一为:
    #   ① 用户显式 CLOUD_PROVIDER=aws/gcp/other → 尊重 (不 unset, cloud_provider.sh
    #      内 ${CLOUD_PROVIDER:-} 短路保留用户值)
    #   ② CLOUD_PROVIDER 为空/auto → 强制重探测 (cloudtop 沙盒可能继承脏值, 82c2722 诉求)
    #   ③ 无论哪条路, 函数末尾都确保 provider getter 已加载 (覆盖 auto + 手动 + 子进程继承缺失)
    # 决策: "auto/空 = 重探测" vs "显式值 = 尊重用户" (用户 2026-06-01 拍板)。
    local _cp_sh="${CONFIG_DIR}/cloud_provider.sh"
    # 用户显式意图判定: CLOUD_PROVIDER 或 DEPLOYMENT_PLATFORM 被设为非 auto 的具体云值
    local _user_pinned=""
    case "${CLOUD_PROVIDER:-}" in aws|gcp|other) _user_pinned="$CLOUD_PROVIDER" ;; esac
    if [[ -z "$_user_pinned" ]]; then
        case "${DEPLOYMENT_PLATFORM:-}" in aws|gcp|other) _user_pinned="$DEPLOYMENT_PLATFORM" ;; esac
    fi

    if [[ -n "$_user_pinned" ]]; then
        echo "🔧 Using pinned cloud provider: $_user_pinned (探测跳过, 尊重用户显式配置)" >&2
        export CLOUD_PROVIDER="$_user_pinned"
        if [[ -f "$_cp_sh" ]]; then
            # source 后 cloud_provider.sh 的 ${CLOUD_PROVIDER:-} 短路保留 $_user_pinned,
            # 仅补探测 NIC/interface, 并经 _load_provider_getters 加载对应 provider getter。
            # shellcheck source=/dev/null
            source "$_cp_sh"
        fi
        DEPLOYMENT_PLATFORM="${CLOUD_PROVIDER:-$_user_pinned}"
    elif [[ "$DEPLOYMENT_PLATFORM" == "auto" ]]; then
        echo "🔍 Auto-detecting deployment platform..." >&2

        # Delegate to config/cloud_provider.sh (single source of truth for aws/gcp/other).
        # 关键 bug 修复: 之前这里只用裸 IMDSv1 探测,无 GCP 分支,且 169.254 在
        # GCP/cloudtop 沙盒下被代理拦截返回 HTML → curl exit 0 → 误判 AWS。
        # 现在统一走 cloud_provider.sh 的 detect_platform(),它做内容校验且 GCP 优先。
        if [[ -f "$_cp_sh" ]]; then
            # 强制重探测: 清空 CLOUD_PROVIDER 避免 cloud_provider.sh 里 :- 短路
            unset CLOUD_PROVIDER NIC_DRIVER CLOUD_PROVIDER_VARIANT
            # shellcheck source=/dev/null
            source "$_cp_sh"
            DEPLOYMENT_PLATFORM="${CLOUD_PROVIDER:-other}"
        else
            echo "⚠️  cloud_provider.sh not found at $_cp_sh, falling back to legacy IMDSv1 probe" >&2
            # Legacy fallback: 不要再误打 AWS,无法判定即 other。
            DEPLOYMENT_PLATFORM="other"
        fi

        case "$DEPLOYMENT_PLATFORM" in
            aws)
                ENA_MONITOR_ENABLED=true
                echo "✅ AWS environment detected, ENA monitoring enabled" >&2
                ;;
            gcp)
                ENA_MONITOR_ENABLED=false
                echo "✅ GCP environment detected, ENA monitoring disabled (use gvnic monitor instead)" >&2
                ;;
            *)
                DEPLOYMENT_PLATFORM="other"
                ENA_MONITOR_ENABLED=false
                echo "ℹ️  Non-AWS/GCP environment detected (IDC/other cloud), ENA monitoring disabled" >&2
                ;;
        esac
    else
        echo "🔧 Using manually configured deployment platform: $DEPLOYMENT_PLATFORM" >&2
        case "$DEPLOYMENT_PLATFORM" in
            "aws")
                ENA_MONITOR_ENABLED=true
                echo "✅ AWS environment, ENA monitoring enabled" >&2
                ;;
            "gcp")
                ENA_MONITOR_ENABLED=false
                echo "✅ GCP environment, ENA monitoring disabled (use gvnic monitor instead)" >&2
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
    
    # ── ③ 无条件兜底: 确保 provider getter 已加载 (修复核心) ──
    # 防御所有路径 (auto / 显式 pinned / cloud_provider.sh 缺失 / 子进程未继承 export -f):
    # 若 get_iops_conversion_func 此刻仍未定义, 说明上面没成功 source cloud_provider.sh
    # (例如 DEPLOYMENT_PLATFORM=aws 老式手动指定但 CLOUD_PROVIDER 未同步), 这里按最终
    # DEPLOYMENT_PLATFORM 同步 CLOUD_PROVIDER 后补加载, 避免 convert_to_standard_iops
    # 静默退化 passthrough (AWS IOPS 公式失效)。幂等: getter 已在则跳过。
    if ! declare -F get_iops_conversion_func >/dev/null 2>&1; then
        local _cp_sh2="${CONFIG_DIR}/cloud_provider.sh"
        if [[ -f "$_cp_sh2" ]]; then
            case "$DEPLOYMENT_PLATFORM" in
                aws|gcp|other) export CLOUD_PROVIDER="$DEPLOYMENT_PLATFORM" ;;
            esac
            # shellcheck source=/dev/null
            source "$_cp_sh2"
            declare -F get_iops_conversion_func >/dev/null 2>&1 \
                && echo "   provider getter loaded (fallback): conv_func=$(get_iops_conversion_func)" >&2 \
                || echo "⚠️  provider getter still unavailable after fallback source" >&2
        fi
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

# Execute deployment platform detection (cloud provider: aws / gcp / other)
detect_deployment_platform

# Execute deployment mode detection (runtime: VM / Docker / K8s) — v1.3 §S2
# Orthogonal axis to deployment_platform; together → (platform, mode) matrix.
if declare -F detect_deployment_mode >/dev/null 2>&1; then
    detect_deployment_mode
fi

# Resolve K8s/container paths (HOST_PROC / HOST_SYS / cgroup paths) — v1.3 §S2
# Must run after detect_deployment_mode (depends on DEPLOYMENT_MODE).
if declare -F resolve_k8s_paths >/dev/null 2>&1; then
    resolve_k8s_paths
fi

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
        # 2026-05-23: 原 https://polygon-rpc.com 已停服(返 "API key disabled, tenant disabled" HTTP 401)
        # 改用 publicnode 公开 endpoint(与 ethereum 同 provider,实测 eth_blockNumber+eth_getBalance PASS)
        MAINNET_RPC_URL="https://polygon-bor-rpc.publicnode.com"
        ;;
    scroll)
        MAINNET_RPC_URL="https://rpc.scroll.io"
        ;;
    starknet)
        # 2026-05-23: 原 https://starknet-mainnet.public.blastapi.io 已停服
        # (返 "Blast API is no longer available. Please update your integration to use Alchemy's API instead" HTTP 403)
        # 改用 Lava Network 公开 endpoint(实测 blockNumber/getClassAt/getNonce/getStorageAt/getEvents 全 PASS,spec 0.8.1)
        MAINNET_RPC_URL="https://rpc.starknet.lava.build"
        ;;
    sui)
        MAINNET_RPC_URL="https://fullnode.mainnet.sui.io:443"
        ;;
    *)
        echo "⚠️ Warning: Unknown blockchain type '${BLOCKCHAIN_NODE}', using default Solana endpoint" >&2
        MAINNET_RPC_URL="https://api.mainnet-beta.solana.com"
        ;;
esac


# =====================================================================
# Automatic Configuration Generation Functions
# =====================================================================

# Validate BLOCKCHAIN_NODE value validity
validate_blockchain_node() {
    local blockchain_node="$1"
    local blockchain_node_lower
    blockchain_node_lower=$(echo "$blockchain_node" | tr '[:upper:]' '[:lower:]')

    # S1.1 (5bd01a6+): supported chains discovered from config/chains/*.json
    # instead of hardcoded list. Source of truth = one chain template JSON per
    # chain. No parallel-entry-trap: there is no second authority list.
    local chains_dir="${CONFIG_LOADER_DIR:-$(dirname "${BASH_SOURCE[0]}")}/chains"
    if [[ ! -d "$chains_dir" ]]; then
        echo "❌ Error: chain template directory not found: $chains_dir" >&2
        return 1
    fi

    local target_file="$chains_dir/${blockchain_node_lower}.json"
    if [[ -f "$target_file" ]]; then
        return 0  # Valid
    fi

    # Invalid blockchain type — discover known chains for diagnostic output
    local known_chains=()
    while IFS= read -r f; do
        known_chains+=("$(basename "$f" .json)")
    done < <(find "$chains_dir" -maxdepth 1 -name '*.json' -type f | sort)

    echo "❌ Error: Unsupported blockchain type '$blockchain_node'" >&2
    echo "   No template at $target_file" >&2
    echo "📋 Supported blockchain types (${#known_chains[@]} discovered):" >&2
    printf "   - %s\n" "${known_chains[@]}" >&2
    echo "💡 Tip: Please check the value of BLOCKCHAIN_NODE environment variable" >&2
    echo "💡 Tip: To add a new chain, create config/chains/<name>.json" >&2
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
                local rpc_cache_var_name="CACHED_RPC_METHODS_${blockchain_node_lower//-/_}_${rpc_mode_lower}"
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
    # NOTE (S0.7-norm): bash variable names disallow '-', so chain names like
    # avalanche-c / cosmos-hub / zksync-era must have '-' normalized to '_'
    # for the cache var name only. The on-disk file name stays as-is.
    local blockchain_node_var_safe="${blockchain_node_lower//-/_}"
    local cache_var_name="CACHED_CHAIN_CONFIG_${blockchain_node_var_safe}"
    local cached_config="${!cache_var_name:-}"
    
    if [[ -n "$cached_config" ]]; then
        # Use cached configuration
        CHAIN_CONFIG="$cached_config"

    else
        # S1.1 (5bd01a6+): read chain template from config/chains/<name>.json
        # instead of the legacy UNIFIED_BLOCKCHAIN_CONFIG heredoc. The .json
        # file is the single source of truth; _meta field is stripped by jq
        # so downstream consumers see the same shape as before.
        local chains_dir="${CONFIG_LOADER_DIR:-$(dirname "${BASH_SOURCE[0]}")}/chains"
        local chain_file="$chains_dir/${blockchain_node_lower}.json"
        if [[ ! -f "$chain_file" ]]; then
            CHAIN_CONFIG=""
        else
            CHAIN_CONFIG=$(jq -c 'del(._meta)' "$chain_file")
        fi
        # Cache parsing result
        if [[ "$CHAIN_CONFIG" != "null" && -n "$CHAIN_CONFIG" ]]; then
            export "$cache_var_name"="$CHAIN_CONFIG"
        fi
    fi
    
    # Validate if configuration loaded correctly
    if [[ "$CHAIN_CONFIG" == "null" || -z "$CHAIN_CONFIG" ]]; then
        echo "❌ Error: Unable to load configuration for $blockchain_node_lower" >&2
        echo "   Expected file: config/chains/${blockchain_node_lower}.json" >&2
        echo "   This indicates missing or malformed chain template" >&2
        exit 1
    fi
    
    # Get RPC methods from CHAIN_CONFIG - Fix caching logic
    local rpc_mode_lower
    rpc_mode_lower=$(echo "${RPC_MODE:-single}" | tr '[:upper:]' '[:lower:]')
    
    # Performance optimization: Use cached RPC method parsing results
    local rpc_cache_var_name="CACHED_RPC_METHODS_${blockchain_node_lower//-/_}_${rpc_mode_lower}"
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
# v1.3 §S2: deployment mode + K8s/container paths (export for child monitor processes)
export DEPLOYMENT_MODE DEPLOYMENT_MODE_DETECTED DEPLOYMENT_MODE_SOURCE
export HOST_PROC HOST_SYS HOST_ROOT CGROUP_VERSION CGROUP_ROOT
# CGROUP_V1_* only set when cgroup v1, but export unconditionally — harmless if empty
export CGROUP_V1_BLKIO_PATH CGROUP_V1_MEMORY_PATH CGROUP_V1_CPU_PATH
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