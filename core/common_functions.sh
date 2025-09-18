#!/bin/bash

# =====================================================================
# Blockchain Node Benchmark QPS 共享函数库
# 包含多个脚本共用的函数
# =====================================================================

# 加载系统配置以获取时间戳函数
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../config/system_config.sh" 2>/dev/null || {
    # 如果无法加载系统配置，提供备用时间戳函数
    get_unified_timestamp() {
        date +"%Y-%m-%d %H:%M:%S"
    }
}

# 检查 Block Height 差异
# 缓冲数据写入
buffered_write() {
    local file="$1"
    local data="$2"
    local buffer_file="${file}.buffer"
    local buffer_size="${3:-10}"
    local buffer_count=0
    
    # 检查目录是否存在
    local dir=$(dirname "$file")
    if [[ ! -d "$dir" ]]; then
        echo "Warning: Directory $dir does not exist, skipping write" >&2
        return 1
    fi
    
    # 安全地处理缓冲文件
    if [[ ! -f "$buffer_file" ]]; then
        if ! echo "0" > "$buffer_file" 2>/dev/null; then
            echo "Warning: Cannot create buffer file $buffer_file, using direct write" >&2
            # 直接写入，不使用缓冲
            echo "$data" >> "$file" 2>/dev/null || return 1
            return 0
        fi
    fi
    
    # 安全地读取缓冲计数
    if ! buffer_count=$(cat "$buffer_file" 2>/dev/null); then
        echo "Warning: Cannot read buffer file $buffer_file, resetting to 0" >&2
        buffer_count=0
    fi
    
    # 验证缓冲计数是数字
    if ! [[ "$buffer_count" =~ ^[0-9]+$ ]]; then
        buffer_count=0
    fi
    
    # 安全地写入数据
    if ! echo "$data" >> "$file" 2>/dev/null; then
        echo "Warning: Cannot write to file $file" >&2
        return 1
    fi
    
    # 更新缓冲计数
    buffer_count=$((buffer_count + 1))
    
    # 刷新缓冲
    if [[ $buffer_count -ge $buffer_size ]]; then
        sync "$file" 2>/dev/null || true
        buffer_count=0
    fi
    
    # 安全地更新缓冲计数
    if ! echo "$buffer_count" > "$buffer_file" 2>/dev/null; then
        echo "Warning: Cannot update buffer count for $buffer_file" >&2
    fi
    
    return 0
}

# 获取带缓存的 Block Height 数据
get_cached_block_height_data() {
    local cache_file="$1"
    local max_age_seconds="${2:-3}"  # 默认 3 秒
    local local_rpc_url="$3"
    local mainnet_rpc_url="$4"
    
    # 检查缓存文件是否存在
    if [[ -f "$cache_file" ]]; then
        # 读取缓存数据
        local cache_data=$(cat "$cache_file")
        local timestamp=$(echo "$cache_data" | jq -r '.timestamp_ms')
        
        # 检查缓存是否过期
        local current_time=$(date +%s.%N)
        local age=$(echo "$current_time - $timestamp" | bc)
        
        if (( $(echo "$age < $max_age_seconds" | bc -l) )); then
            # 缓存未过期，返回缓存数据
            echo "$cache_data"
            return 0
        fi
    fi
    
    # 缓存不存在或已过期，获取新数据
    local local_block_height=$(get_block_height "$local_rpc_url")
    local mainnet_block_height=$(get_block_height "$mainnet_rpc_url")
    local local_health=$(check_node_health "$local_rpc_url")
    local mainnet_health=$(check_node_health "$mainnet_rpc_url")
    
    # 计算区块高度差异
    local block_height_diff="N/A"
    if [[ "$local_block_height" != "N/A" && "$mainnet_block_height" != "N/A" ]]; then
        block_height_diff=$((mainnet_block_height - local_block_height))
    fi
    
    # 检测数据丢失 - 改进的逻辑
    local data_loss="false"
    
    # 更严格的数据丢失检测条件
    # 1. 只有当区块高度数据完全无法获取时才标记为数据丢失
    # 2. 或者当区块高度差异超过严重阈值时（如 > 1000）
    if [[ "$local_block_height" == "N/A" && "$mainnet_block_height" == "N/A" ]]; then
        # 两个节点都无法获取区块高度数据
        data_loss="true"
    elif [[ "$local_block_height" != "N/A" && "$mainnet_block_height" != "N/A" ]]; then
        # 如果能获取到区块高度数据，检查差异是否过大
        local abs_block_height_diff
        if [[ $block_height_diff -lt 0 ]]; then
            abs_block_height_diff=$((-block_height_diff))
        else
            abs_block_height_diff=$block_height_diff
        fi
        
        # 只有当区块高度差异超过1000时才认为是严重的数据丢失
        if [[ $abs_block_height_diff -gt 1000 ]]; then
            data_loss="true"
        fi
    elif [[ "$local_block_height" == "N/A" || "$mainnet_block_height" == "N/A" ]]; then
        # 只有一个节点无法获取数据，检查是否持续
        # 这里可以添加更复杂的逻辑，比如检查历史数据
        # 暂时不标记为数据丢失，除非健康状态也异常
        if [[ "$local_health" == "unhealthy" && "$mainnet_health" == "unhealthy" ]]; then
            data_loss="true"
        fi
    fi
    
    # 创建新的缓存数据（带毫秒时间戳）
    local timestamp_ms=$(date +%s)000
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
            local_block_height: ($local_block_height | tonumber),
            mainnet_block_height: ($mainnet_block_height | tonumber),
            block_height_diff: ($block_height_diff | tonumber),
            local_health: $local_health,
            mainnet_health: $mainnet_health,
            data_loss: $data_loss
        }')
    
    # 更新缓存
    echo "$new_data" > "$cache_file"
    
    # 返回新数据
    echo "$new_data"
    return 0
}

# 清理旧的缓存数据（保留最近 5 分钟）
cleanup_block_height_cache() {
    local cache_dir="$1"
    local max_age_minutes="${2:-5}"  # 默认 5 分钟
    
    # 查找并删除旧的缓存文件
    find "$cache_dir" -name "block_height_*.json" -type f -mmin +$max_age_minutes -delete
}

# 多链区块高度获取函数 (基于实际测试验证)
get_block_height() {
    local rpc_url="$1"
    local blockchain_type="${BLOCKCHAIN_NODE,,}"
    local url_hash=$(echo "$rpc_url" | md5sum | cut -d' ' -f1)
    local health_cache_file="${MEMORY_SHARE_DIR:-/tmp}/node_health_${url_hash}.cache"
    local result
    
    # 验证输入参数
    if [[ -z "$rpc_url" ]]; then
        echo "unhealthy" > "$health_cache_file"
        echo "N/A"
        return 1
    fi
    
    case "$blockchain_type" in
        solana)
            # Solana: 使用getBlockHeight (已验证返回: 337632288)
            for i in {1..3}; do
                result=$(curl -s -X POST -H "Content-Type: application/json" \
                    --data '{"jsonrpc":"2.0","id":1,"method":"getBlockHeight","params":[]}' \
                    "$rpc_url" 2>/dev/null)
                
                if [[ -n "$result" ]] && echo "$result" | jq -e '.result' >/dev/null 2>&1; then
                    local height=$(echo "$result" | jq -r '.result')
                    if [[ "$height" =~ ^[0-9]+$ ]]; then
                        echo "healthy" > "$health_cache_file"
                        echo "$height"
                        return 0
                    fi
                fi
                sleep 1
            done
            ;;
        ethereum|bsc|base|polygon|scroll)
            # EVM链: 使用eth_blockNumber (已验证返回十六进制格式)
            for i in {1..3}; do
                result=$(curl -s -X POST -H "Content-Type: application/json" \
                    --data '{"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}' \
                    "$rpc_url" 2>/dev/null)
                
                if [[ -n "$result" ]] && echo "$result" | jq -e '.result' >/dev/null 2>&1; then
                    local block_hex=$(echo "$result" | jq -r '.result')
                    if [[ "$block_hex" =~ ^0x[0-9a-fA-F]+$ ]]; then
                        # 转换十六进制为十进制 (如: 0x160cda4 → 23256484)
                        local block_num="${block_hex#0x}"
                        local decimal_height=$(printf "%d" "$((16#$block_num))")
                        echo "healthy" > "$health_cache_file"
                        echo "$decimal_height"
                        return 0
                    fi
                fi
                sleep 1
            done
            ;;
        starknet)
            # StarkNet: 使用starknet_blockNumber (已验证返回: 1717483)
            for i in {1..3}; do
                result=$(curl -s -X POST -H "Content-Type: application/json" \
                    --data '{"jsonrpc":"2.0","id":1,"method":"starknet_blockNumber","params":[]}' \
                    "$rpc_url" 2>/dev/null)
                
                if [[ -n "$result" ]] && echo "$result" | jq -e '.result' >/dev/null 2>&1; then
                    local height=$(echo "$result" | jq -r '.result')
                    if [[ "$height" =~ ^[0-9]+$ ]]; then
                        echo "healthy" > "$health_cache_file"
                        echo "$height"
                        return 0
                    fi
                fi
                sleep 1
            done
            ;;
        sui)
            # Sui: 使用sui_getTotalTransactionBlocks (已验证返回: 3953306852)
            for i in {1..3}; do
                result=$(curl -s -X POST -H "Content-Type: application/json" \
                    --data '{"jsonrpc":"2.0","id":1,"method":"sui_getTotalTransactionBlocks","params":[]}' \
                    "$rpc_url" 2>/dev/null)
                
                if [[ -n "$result" ]] && echo "$result" | jq -e '.result' >/dev/null 2>&1; then
                    local height=$(echo "$result" | jq -r '.result')
                    if [[ "$height" =~ ^[0-9]+$ ]]; then
                        echo "healthy" > "$health_cache_file"
                        echo "$height"
                        return 0
                    fi
                fi
                sleep 1
            done
            ;;
        *)
            echo "❌ 不支持的区块链类型: $blockchain_type" >&2
            echo "unhealthy" > "$health_cache_file"
            echo "N/A"
            return 1
            ;;
    esac
    
    echo "unhealthy" > "$health_cache_file"
    echo "N/A"
    return 1
}

# 检查节点健康状态
# 检查节点健康状态 - 基于缓存的健康状态检查
check_node_health() {
    local rpc_url="$1"
    local url_hash=$(echo "$rpc_url" | md5sum | cut -d' ' -f1)
    local health_cache_file="${MEMORY_SHARE_DIR:-/tmp}/node_health_${url_hash}.cache"
    
    # 验证输入参数
    if [[ -z "$rpc_url" ]]; then
        echo "unhealthy"
        return 1
    fi
    
    # 检查缓存文件是否存在且是最近的（60秒内）
    if [[ -f "$health_cache_file" ]]; then
        local cache_age=$(($(date +%s) - $(stat -f %m "$health_cache_file" 2>/dev/null || echo 0)))
        if [[ $cache_age -lt 60 ]]; then
            # 使用缓存的健康状态
            cat "$health_cache_file" 2>/dev/null || echo "unhealthy"
            return 0
        fi
    fi
    
    # 缓存过期或不存在，通过get_block_height测试连接性
    local block_height=$(get_block_height "$rpc_url")
    
    if [[ "$block_height" != "N/A" && "$block_height" =~ ^[0-9]+$ ]]; then
        echo "healthy" > "$health_cache_file"
        echo "healthy"
        return 0
    else
        echo "unhealthy" > "$health_cache_file"
        echo "unhealthy"
        return 1
    fi
}
