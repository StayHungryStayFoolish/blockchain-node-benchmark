#!/bin/bash

# =====================================================================
# Blockchain Node Benchmark QPS Shared Function Library
# Contains functions shared across multiple scripts
# =====================================================================

# Load system configuration to get timestamp function
LOCAL_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${LOCAL_SCRIPT_DIR}/../config/system_config.sh" 2>/dev/null || {
    # If system config cannot be loaded, provide fallback timestamp function
    get_unified_timestamp() {
        date +"%Y-%m-%d %H:%M:%S"
    }
}

# Check Block Height difference
# Buffered data write
buffered_write() {
    local file="$1"
    local data="$2"
    local buffer_file="${file}.buffer"
    local buffer_size="${3:-10}"
    local buffer_count=0
    
    # Check if directory exists
    local dir=$(dirname "$file")
    if [[ ! -d "$dir" ]]; then
        echo "Warning: Directory $dir does not exist, skipping write" >&2
        return 1
    fi
    
    # Safely handle buffer file
    if [[ ! -f "$buffer_file" ]]; then
        if ! echo "0" > "$buffer_file" 2>/dev/null; then
            echo "Warning: Cannot create buffer file $buffer_file, using direct write" >&2
            # Direct write without buffering
            echo "$data" >> "$file" 2>/dev/null || return 1
            return 0
        fi
    fi
    
    # Safely read buffer count
    if ! buffer_count=$(cat "$buffer_file" 2>/dev/null); then
        echo "Warning: Cannot read buffer file $buffer_file, resetting to 0" >&2
        buffer_count=0
    fi
    
    # Verify buffer count is numeric
    if ! [[ "$buffer_count" =~ ^[0-9]+$ ]]; then
        buffer_count=0
    fi
    
    # Safely write data
    if ! echo "$data" >> "$file" 2>/dev/null; then
        echo "Warning: Cannot write to file $file" >&2
        return 1
    fi
    
    # Update buffer count
    buffer_count=$((buffer_count + 1))
    
    # Flush buffer
    if [[ $buffer_count -ge $buffer_size ]]; then
        sync "$file" 2>/dev/null || true
        buffer_count=0
    fi
    
    # Safely update buffer count
    if ! echo "$buffer_count" > "$buffer_file" 2>/dev/null; then
        echo "Warning: Cannot update buffer count for $buffer_file" >&2
    fi
    
    return 0
}

# Get cached Block Height data
get_cached_block_height_data() {
    local cache_file="$1"
    local max_age_seconds="${2:-1}"  # Default 1 second (adjusted from 3 seconds)
    local local_rpc_url="$3"
    local mainnet_rpc_url="$4"
    
    # Check if cache file exists
    if [[ -f "$cache_file" ]]; then
        # Read cache data
        local cache_data=$(cat "$cache_file")
        local timestamp=$(echo "$cache_data" | jq -r '.timestamp_ms')
        
        # Verify timestamp is valid
        if [[ -n "$timestamp" && "$timestamp" != "null" && "$timestamp" != "N/A" ]]; then
            # Check if cache is expired
            local current_time=$(date +%s.%N)
            local age=$(awk "BEGIN {printf \"%.6f\", $current_time - $timestamp}")
            
            if (( $(awk "BEGIN {print ($age < $max_age_seconds) ? 1 : 0}") )); then
                # Cache not expired, return cached data
                echo "$cache_data"
                return 0
            fi
        fi
    fi
    
    # Cache doesn't exist or expired, fetch new data
    local local_block_height=$(get_block_height "$local_rpc_url")
    local mainnet_block_height=$(get_block_height "$mainnet_rpc_url")
    local local_health=$(check_node_health "$local_rpc_url")
    local mainnet_health=$(check_node_health "$mainnet_rpc_url")
    
    # Calculate block height difference
    local block_height_diff="N/A"
    if [[ "$local_block_height" != "N/A" && "$mainnet_block_height" != "N/A" ]]; then
        block_height_diff=$((mainnet_block_height - local_block_height))
    fi
    
    # Detect data loss - improved logic
    local data_loss="0"  # Use numeric: 0=false, 1=true
    
    # Stricter data loss detection conditions
    # 1. Only mark as data loss when block height data is completely unavailable
    # 2. Or when block height difference exceeds configured threshold (BLOCK_HEIGHT_DIFF_THRESHOLD)
    if [[ "$local_block_height" == "N/A" && "$mainnet_block_height" == "N/A" ]]; then
        # Both nodes cannot retrieve block height data
        data_loss="1"  # Numeric: 1=true
    elif [[ "$local_block_height" != "N/A" && "$mainnet_block_height" != "N/A" ]]; then
        # Can retrieve block height data, data_loss remains 0
        # Block height difference judgment is handled by block_height_monitor.sh (requires duration check)
        data_loss="0"
    elif [[ "$local_block_height" == "N/A" || "$mainnet_block_height" == "N/A" ]]; then
        # Only one node cannot retrieve data, check if persistent
        # More complex logic can be added here, such as checking historical data
        # Don't mark as data loss for now unless health status is also abnormal
        if [[ "$local_health" == "0" && "$mainnet_health" == "0" ]]; then  # 0=unhealthy
            data_loss="1"  # Numeric: 1=true
        fi
    fi
    
    # Create new cache data (with millisecond timestamp)
    local timestamp_ms=$(date +%s%3N)
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    local new_data
    new_data=$(jq -n \
        --arg timestamp_ms "$timestamp_ms" \
        --arg timestamp "$timestamp" \
        --arg local_block_height "$local_block_height" \
        --arg mainnet_block_height "$mainnet_block_height" \
        --arg block_height_diff "$block_height_diff" \
        --arg local_health "$local_health" \
        --arg mainnet_health "$mainnet_health" \
        --arg data_loss "$data_loss" \
        '{
            timestamp_ms: ($timestamp_ms | tonumber),
            timestamp: $timestamp,
            local_block_height: (if $local_block_height == "N/A" then null else ($local_block_height | tonumber) end),
            mainnet_block_height: (if $mainnet_block_height == "N/A" then null else ($mainnet_block_height | tonumber) end),
            block_height_diff: (if $block_height_diff == "N/A" then null else ($block_height_diff | tonumber) end),
            local_health: $local_health,
            mainnet_health: $mainnet_health,
            data_loss: $data_loss
        }')
    
    # Update cache
    echo "$new_data" > "$cache_file"
    
    # Return new data
    echo "$new_data"
    return 0
}

# Clean up old cache data (keep last 5 minutes)
cleanup_block_height_cache() {
    local cache_dir="$1"
    local max_age_minutes="${2:-5}"  # Default 5 minutes
    
    # Find and delete old cache files
    find "$cache_dir" -name "block_height_*.json" -type f -mmin +$max_age_minutes -delete
}

# Multi-chain block height retrieval function (based on actual test verification)
get_block_height() {
    local rpc_url="$1"
    local blockchain_type="${BLOCKCHAIN_NODE,,}"
    local url_hash=$(echo "$rpc_url" | md5sum | cut -d' ' -f1)
    local health_cache_file="${MEMORY_SHARE_DIR:-/tmp}/node_health_${url_hash}.cache"
    local result
    
    # Validate input parameters
    if [[ -z "$rpc_url" ]]; then
        echo "0" > "$health_cache_file"  # Cache numeric: 0=unhealthy
        echo "N/A"
        return 1
    fi
    
    case "$blockchain_type" in
        solana)
            # Solana: Use getBlockHeight (verified returns: 337632288)
            for i in {1..3}; do
                result=$(curl -s -X POST -H "Content-Type: application/json" \
                    --data '{"jsonrpc":"2.0","id":1,"method":"getBlockHeight","params":[]}' \
                    "$rpc_url" 2>/dev/null)
                
                if [[ -n "$result" ]] && echo "$result" | jq -e '.result' >/dev/null 2>&1; then
                    local height=$(echo "$result" | jq -r '.result')
                    if [[ "$height" =~ ^[0-9]+$ ]]; then
                        echo "1" > "$health_cache_file"  # Cache numeric: 1=healthy
                        echo "$height"
                        return 0
                    fi
                fi
                sleep 1
            done
            ;;
        ethereum|bsc|base|polygon|scroll)
            # EVM chains: Use eth_blockNumber (verified returns hexadecimal format)
            for i in {1..3}; do
                result=$(curl -s -X POST -H "Content-Type: application/json" \
                    --data '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}' \
                    "$rpc_url" 2>/dev/null)
                
                if [[ -n "$result" ]] && echo "$result" | jq -e '.result' >/dev/null 2>&1; then
                    local block_hex=$(echo "$result" | jq -r '.result')
                    if [[ "$block_hex" =~ ^0x[0-9a-fA-F]+$ ]]; then
                        # Convert hexadecimal to decimal (e.g.: 0x160cda4 → 23256484)
                        local block_num="${block_hex#0x}"
                        local decimal_height=$(printf "%d" "$((16#$block_num))")
                        echo "1" > "$health_cache_file"  # Cache numeric: 1=healthy
                        echo "$decimal_height"
                        return 0
                    fi
                fi
                sleep 1
            done
            ;;
        starknet)
            # StarkNet: Use starknet_blockNumber (verified returns: 1717483)
            for i in {1..3}; do
                result=$(curl -s -X POST -H "Content-Type: application/json" \
                    --data '{"jsonrpc":"2.0","id":1,"method":"starknet_blockNumber","params":[]}' \
                    "$rpc_url" 2>/dev/null)
                
                if [[ -n "$result" ]] && echo "$result" | jq -e '.result' >/dev/null 2>&1; then
                    local height=$(echo "$result" | jq -r '.result')
                    if [[ "$height" =~ ^[0-9]+$ ]]; then
                        echo "1" > "$health_cache_file"  # Cache numeric: 1=healthy
                        echo "$height"
                        return 0
                    fi
                fi
                sleep 1
            done
            ;;
        sui)
            # Sui: Use sui_getTotalTransactionBlocks (verified returns: 3953306852)
            for i in {1..3}; do
                result=$(curl -s -X POST -H "Content-Type: application/json" \
                    --data '{"jsonrpc":"2.0","id":1,"method":"sui_getTotalTransactionBlocks","params":[]}' \
                    "$rpc_url" 2>/dev/null)
                
                if [[ -n "$result" ]] && echo "$result" | jq -e '.result' >/dev/null 2>&1; then
                    local height=$(echo "$result" | jq -r '.result')
                    if [[ "$height" =~ ^[0-9]+$ ]]; then
                        echo "1" > "$health_cache_file"  # Cache numeric: 1=healthy
                        echo "$height"
                        return 0
                    fi
                fi
                sleep 1
            done
            ;;
        *)
            echo "❌ Unsupported blockchain type: $blockchain_type" >&2
            echo "0" > "$health_cache_file"  # Cache numeric: 0=unhealthy
            echo "N/A"
            return 1
            ;;
    esac
    
    echo "0" > "$health_cache_file"  # Cache numeric: 0=unhealthy
    echo "N/A"
    return 1
}

# Check node health status - cache-based health check
check_node_health() {
    local rpc_url="$1"
    local url_hash=$(echo "$rpc_url" | md5sum | cut -d' ' -f1)
    local health_cache_file="${MEMORY_SHARE_DIR:-/tmp}/node_health_${url_hash}.cache"
    
    # Validate input parameters
    if [[ -z "$rpc_url" ]]; then
        echo "0"  # Return numeric: 0=unhealthy
        return 1
    fi
    
    # Check if cache file exists and is recent (within 60 seconds)
    if [[ -f "$health_cache_file" ]]; then
        local cache_age=$(($(date +%s) - $(stat -c %Y "$health_cache_file" 2>/dev/null || echo 0)))
        if [[ $cache_age -lt 60 ]]; then
            # Use cached health status
            cat "$health_cache_file" 2>/dev/null || echo "0"
            return 0
        fi
    fi
    
    # Cache expired or doesn't exist, test connectivity via get_block_height
    local block_height=$(get_block_height "$rpc_url")
    
    if [[ "$block_height" != "N/A" && "$block_height" =~ ^[0-9]+$ ]]; then
        echo "1" > "$health_cache_file"  # Cache numeric: 1=healthy
        echo "1"  # Return numeric: 1=healthy
        return 0
    else
        echo "0" > "$health_cache_file"  # Cache numeric: 0=unhealthy
        echo "0"  # Return numeric: 0=unhealthy
        return 1
    fi
}
