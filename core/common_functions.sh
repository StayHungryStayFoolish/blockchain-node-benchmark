#!/bin/bash

# =====================================================================
# Solana QPS 测试框架共享函数库
# 包含多个脚本共用的函数
# =====================================================================

# 检查 Slot 差异
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

# 获取带缓存的 Slot 数据
get_cached_slot_data() {
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
    local local_slot=$(get_slot "$local_rpc_url")
    local mainnet_slot=$(get_slot "$mainnet_rpc_url")
    local local_health=$(check_node_health "$local_rpc_url")
    local mainnet_health=$(check_node_health "$mainnet_rpc_url")
    
    # 计算 Slot 差异
    local slot_diff="N/A"
    if [[ "$local_slot" != "N/A" && "$mainnet_slot" != "N/A" ]]; then
        slot_diff=$((mainnet_slot - local_slot))
    fi
    
    # 检测数据丢失 - 改进的逻辑
    local data_loss="false"
    
    # 更严格的数据丢失检测条件
    # 1. 只有当slot数据完全无法获取时才标记为数据丢失
    # 2. 或者当slot差异超过严重阈值时（如 > 1000）
    if [[ "$local_slot" == "N/A" && "$mainnet_slot" == "N/A" ]]; then
        # 两个节点都无法获取slot数据
        data_loss="true"
    elif [[ "$local_slot" != "N/A" && "$mainnet_slot" != "N/A" ]]; then
        # 如果能获取到slot数据，检查差异是否过大
        local abs_slot_diff
        if [[ $slot_diff -lt 0 ]]; then
            abs_slot_diff=$((-slot_diff))
        else
            abs_slot_diff=$slot_diff
        fi
        
        # 只有当slot差异超过1000时才认为是严重的数据丢失
        if [[ $abs_slot_diff -gt 1000 ]]; then
            data_loss="true"
        fi
    elif [[ "$local_slot" == "N/A" || "$mainnet_slot" == "N/A" ]]; then
        # 只有一个节点无法获取数据，检查是否持续
        # 这里可以添加更复杂的逻辑，比如检查历史数据
        # 暂时不标记为数据丢失，除非健康状态也异常
        if [[ "$local_health" == "unhealthy" && "$mainnet_health" == "unhealthy" ]]; then
            data_loss="true"
        fi
    fi
    
    # 创建新的缓存数据（带毫秒时间戳）
    local timestamp_ms=$(date +%s)000
    local new_data="{\"timestamp_ms\":$timestamp_ms,\"timestamp\":\"$(get_unified_timestamp)\",\"local_slot\":$local_slot,\"mainnet_slot\":$mainnet_slot,\"slot_diff\":$slot_diff,\"local_health\":\"$local_health\",\"mainnet_health\":\"$mainnet_health\",\"data_loss\":\"$data_loss\"}"
    
    # 更新缓存
    echo "$new_data" > "$cache_file"
    
    # 返回新数据
    echo "$new_data"
    return 0
}

# 清理旧的缓存数据（保留最近 5 分钟）
cleanup_slot_cache() {
    local cache_dir="$1"
    local max_age_minutes="${2:-5}"  # 默认 5 分钟
    
    # 查找并删除旧的缓存文件
    find "$cache_dir" -name "slot_*.json" -type f -mmin +$max_age_minutes -delete
}

# 获取 Solana 节点 Slot
get_slot() {
    local rpc_url=$1
    local result
    
    # 尝试获取 Slot 信息，最多重试 3 次
    for i in {1..3}; do
        result=$(curl -s -X POST -H "Content-Type: application/json" \
            -d '{"jsonrpc":"2.0","id":1,"method":"getSlot"}' \
            "$rpc_url")
        
        # 检查是否成功获取 Slot
        if [[ $(echo "$result" | jq -r '.result') != "null" ]]; then
            echo $(echo "$result" | jq -r '.result')
            return 0
        fi
        
        sleep 1
    done
    
    echo "N/A"
    return 1
}

# 检查节点健康状态
check_node_health() {
    local rpc_url=$1
    local result
    
    # 尝试获取健康状态，最多重试 3 次
    for i in {1..3}; do
        result=$(curl -s -X POST -H "Content-Type: application/json" \
            -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}' \
            "$rpc_url")
        
        # 检查是否成功获取健康状态
        if [[ $(echo "$result" | jq -r '.result') != "null" ]]; then
            echo $(echo "$result" | jq -r '.result')
            return 0
        fi
        
        sleep 1
    done
    
    echo "unhealthy"
    return 1
}
