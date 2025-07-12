#!/bin/bash

# =====================================================================
# Solana QPS 测试框架共享函数库
# 包含多个脚本共用的函数
# =====================================================================

# 检查 Slot 差异
check_slot_diff() {
    local slot_cache_file="$1"
    local slot_diff_threshold="$2"
    local slot_time_threshold="$3"
    local slot_diff_start_time="$4"
    
    echo "Checking Slot difference..."
    
    # 检查缓存文件是否存在
    if [[ ! -f "$slot_cache_file" ]]; then
        echo "Warning: Slot monitor cache file not found"
        return 0
    fi
    
    # 读取缓存数据
    local cache_data=$(cat "$slot_cache_file")
    local slot_diff=$(echo "$cache_data" | jq -r '.slot_diff')
    local timestamp=$(echo "$cache_data" | jq -r '.timestamp')
    
    # 检查 Slot 差异是否超过阈值
    if [[ "$slot_diff" != "null" && $slot_diff -gt $slot_diff_threshold ]]; then
        if [[ -z "$slot_diff_start_time" ]]; then
            # 记录开始时间
            slot_diff_start_time=$(date +"%Y-%m-%d %H:%M:%S")
            echo "⚠️ WARNING: Slot difference ($slot_diff) exceeds threshold, starting timer at $slot_diff_start_time"
            echo "$slot_diff_start_time"  # 返回开始时间
            return 0
        else
            # 计算持续时间
            local start_seconds=$(date -d "$slot_diff_start_time" +%s)
            local current_seconds=$(date +%s)
            local duration=$((current_seconds - start_seconds))
            
            if [[ $duration -gt $slot_time_threshold ]]; then
                echo "🚨 CRITICAL: Slot difference ($slot_diff) has exceeded threshold for ${duration}s (> ${slot_time_threshold}s)"
                echo "🚨 CRITICAL: Pausing QPS test until Slot difference is resolved"
                return 1
            else
                echo "⚠️ WARNING: Slot difference ($slot_diff) exceeds threshold, but duration (${duration}s) is still within time threshold"
                echo "$slot_diff_start_time"  # 返回开始时间
                return 0
            fi
        fi
    else
        # 重置开始时间
        echo ""  # 返回空字符串，表示重置开始时间
        return 0
    fi
}

# 等待 Slot 恢复
wait_for_slot_recovery() {
    local slot_cache_file="$1"
    local slot_diff_threshold="$2"
    
    echo "Waiting for Slot difference to recover..."
    
    while true; do
        if check_slot_recovery "$slot_cache_file" "$slot_diff_threshold"; then
            echo "Slot difference recovered, resuming test"
            return 0
        fi
        
        echo "Still waiting for Slot recovery..."
        sleep 30
    done
}

# 检查 Slot 是否恢复
check_slot_recovery() {
    local slot_cache_file="$1"
    local slot_diff_threshold="$2"
    
    # 读取缓存数据
    if [[ ! -f "$slot_cache_file" ]]; then
        echo "Warning: Slot monitor cache file not found"
        return 1
    fi
    
    local cache_data=$(cat "$slot_cache_file")
    local slot_diff=$(echo "$cache_data" | jq -r '.slot_diff')
    
    if [[ "$slot_diff" != "null" && $slot_diff -le $slot_diff_threshold ]]; then
        return 0
    else
        return 1
    fi
}

# 更新 QPS 测试状态
update_qps_status() {
    local status_file="$1"
    local status="$2"
    local current_qps="$3"
    local message="$4"
    
    # 创建状态 JSON
    local status_json="{\"status\":\"$status\",\"current_qps\":$current_qps,\"message\":\"$message\",\"timestamp\":\"$(get_unified_timestamp)\"}"
    
    # 写入状态文件
    echo "$status_json" > "$status_file"
}

# 检查测试状态
check_qps_status() {
    local status_file="$1"
    
    if [[ ! -f "$status_file" ]]; then
        echo "No QPS test status found"
        return 1
    fi
    
    cat "$status_file"
    return 0
}

# 缓冲数据写入（增强版，带错误处理）
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

# 刷新缓冲（增强版）
flush_buffer() {
    local file="$1"
    local buffer_file="${file}.buffer"
    
    # 检查文件是否存在
    if [[ ! -f "$file" ]]; then
        echo "Warning: File $file does not exist, cannot flush buffer" >&2
        return 1
    fi
    
    # 刷新文件
    sync "$file" 2>/dev/null || true
    
    # 重置缓冲计数
    if [[ -f "$buffer_file" ]]; then
        echo "0" > "$buffer_file" 2>/dev/null || true
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
    local timestamp_ms=$(get_unified_timestamp_ms)
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
