#!/bin/bash
# =====================================================================
# 统一异常事件管理器
# =====================================================================
# 管理所有组件的异常事件，确保时间范围关联分析
# 当任何组件检测到异常时，通知其他组件记录相同时间范围的数据
# =====================================================================

source "$(dirname "${BASH_SOURCE[0]}")/../config/config.sh"

readonly EVENT_LOG="${MEMORY_SHARE_DIR}/unified_events.json"
readonly EVENT_LOCK="${MEMORY_SHARE_DIR}/event_manager.lock"

# 初始化事件管理器
init_event_manager() {
    echo "🎯 初始化统一异常事件管理器..."
    
    # 创建事件日志文件
    echo "[]" > "$EVENT_LOG"
    
    echo "✅ 事件管理器初始化完成"
}

# 记录异常事件开始
record_event_start() {
    local event_type="$1"      # slot_diff, cpu_high, ebs_bottleneck, etc.
    local event_source="$2"    # slot_monitor, unified_monitor, bottleneck_detector
    local event_details="$3"   # 详细信息
    local current_qps="${4:-0}" # 当前QPS (如果适用)
    
    local start_time=$(get_unified_timestamp)
    local start_epoch=$(get_unified_epoch)
    local event_id="${event_type}_${start_epoch}"
    
    # 使用文件锁确保并发安全
    (
        flock -x 200
        
        # 读取现有事件
        local events="[]"
        if [[ -f "$EVENT_LOG" ]]; then
            events=$(cat "$EVENT_LOG")
        fi
        
        # 创建新事件记录
        local new_event="{
            \"event_id\": \"$event_id\",
            \"event_type\": \"$event_type\",
            \"event_source\": \"$event_source\",
            \"event_details\": \"$event_details\",
            \"current_qps\": $current_qps,
            \"start_time\": \"$start_time\",
            \"start_epoch\": $start_epoch,
            \"end_time\": null,
            \"end_epoch\": null,
            \"duration\": null,
            \"status\": \"active\"
        }"
        
        # 添加到事件列表
        echo "$events" | jq ". += [$new_event]" > "$EVENT_LOG"
        
        echo "📢 异常事件开始: $event_type (ID: $event_id)"
        echo "  来源: $event_source"
        echo "  时间: $start_time"
        echo "  详情: $event_details"
        
        # 通知其他组件开始记录详细数据
        notify_components_event_start "$event_id" "$event_type" "$start_time"
        
    ) 200>"$EVENT_LOCK"
    
    echo "$event_id"  # 返回事件ID
}

# 记录异常事件结束
record_event_end() {
    local event_id="$1"
    
    local end_time=$(get_unified_timestamp)
    local end_epoch=$(get_unified_epoch)
    
    # 使用文件锁确保并发安全
    (
        flock -x 200
        
        if [[ -f "$EVENT_LOG" ]]; then
            # 更新事件记录
            local updated_events=$(cat "$EVENT_LOG" | jq "
                map(if .event_id == \"$event_id\" then
                    .end_time = \"$end_time\" |
                    .end_epoch = $end_epoch |
                    .duration = (.end_epoch - .start_epoch) |
                    .status = \"completed\"
                else . end)
            ")
            
            echo "$updated_events" > "$EVENT_LOG"
            
            # 获取事件信息
            local event_info=$(echo "$updated_events" | jq ".[] | select(.event_id == \"$event_id\")")
            local event_type=$(echo "$event_info" | jq -r '.event_type')
            local start_time=$(echo "$event_info" | jq -r '.start_time')
            local duration=$(echo "$event_info" | jq -r '.duration')
            
            echo "✅ 异常事件结束: $event_type (ID: $event_id)"
            echo "  持续时间: ${duration}s"
            echo "  时间范围: $start_time → $end_time"
            
            # 通知其他组件事件结束，开始关联分析
            notify_components_event_end "$event_id" "$event_type" "$start_time" "$end_time"
            
            # 记录时间范围供后续分析使用
            record_time_range "$event_type" "$start_time" "$end_time"
        fi
        
    ) 200>"$EVENT_LOCK"
}

# 通知组件事件开始
notify_components_event_start() {
    local event_id="$1"
    local event_type="$2"
    local start_time="$3"
    
    # 创建通知文件
    local notification="{
        \"action\": \"event_start\",
        \"event_id\": \"$event_id\",
        \"event_type\": \"$event_type\",
        \"start_time\": \"$start_time\",
        \"timestamp\": \"$(get_unified_timestamp)\"
    }"
    
    echo "$notification" > "${MEMORY_SHARE_DIR}/event_notification.json"
    
    # 可以在这里添加更多通知机制，比如信号或消息队列
}

# 通知组件事件结束
notify_components_event_end() {
    local event_id="$1"
    local event_type="$2"
    local start_time="$3"
    local end_time="$4"
    
    # 创建通知文件
    local notification="{
        \"action\": \"event_end\",
        \"event_id\": \"$event_id\",
        \"event_type\": \"$event_type\",
        \"start_time\": \"$start_time\",
        \"end_time\": \"$end_time\",
        \"timestamp\": \"$(get_unified_timestamp)\"
    }"
    
    echo "$notification" > "${MEMORY_SHARE_DIR}/event_notification.json"
    
    echo "🔗 已通知所有组件进行时间范围关联分析"
    echo "  事件类型: $event_type"
    echo "  时间范围: $start_time → $end_time"
}

# 获取活跃事件
get_active_events() {
    if [[ -f "$EVENT_LOG" ]]; then
        cat "$EVENT_LOG" | jq '.[] | select(.status == "active")'
    else
        echo "[]"
    fi
}

# 获取所有事件
get_all_events() {
    if [[ -f "$EVENT_LOG" ]]; then
        cat "$EVENT_LOG"
    else
        echo "[]"
    fi
}

# 获取指定类型的事件
get_events_by_type() {
    local event_type="$1"
    
    if [[ -f "$EVENT_LOG" ]]; then
        cat "$EVENT_LOG" | jq ".[] | select(.event_type == \"$event_type\")"
    else
        echo "[]"
    fi
}

# 清理旧事件
cleanup_old_events() {
    local max_age_hours="${1:-24}"  # 默认保留24小时
    local cutoff_epoch=$(($(get_unified_epoch) - max_age_hours * 3600))
    
    if [[ -f "$EVENT_LOG" ]]; then
        (
            flock -x 200
            
            local filtered_events=$(cat "$EVENT_LOG" | jq "map(select(.start_epoch > $cutoff_epoch))")
            echo "$filtered_events" > "$EVENT_LOG"
            
            echo "🧹 已清理 ${max_age_hours} 小时前的旧事件"
            
        ) 200>"$EVENT_LOCK"
    fi
}

# 主函数
main() {
    case "${1:-help}" in
        init)
            init_event_manager
            ;;
        start)
            record_event_start "$2" "$3" "$4" "$5"
            ;;
        end)
            record_event_end "$2"
            ;;
        active)
            get_active_events
            ;;
        all)
            get_all_events
            ;;
        type)
            get_events_by_type "$2"
            ;;
        cleanup)
            cleanup_old_events "$2"
            ;;
        help|--help|-h)
            echo "Usage: $0 <command> [options]"
            echo ""
            echo "Commands:"
            echo "  init                     初始化事件管理器"
            echo "  start <type> <source> <details> [qps]  记录事件开始"
            echo "  end <event_id>           记录事件结束"
            echo "  active                   显示活跃事件"
            echo "  all                      显示所有事件"
            echo "  type <event_type>        显示指定类型事件"
            echo "  cleanup [hours]          清理旧事件"
            echo "  help                     显示帮助"
            echo ""
            echo "事件类型:"
            echo "  slot_diff                Slot差异异常"
            echo "  cpu_high                 CPU使用率过高"
            echo "  memory_high              内存使用率过高"
            echo "  ebs_bottleneck           EBS性能瓶颈"
            echo "  network_bottleneck       网络瓶颈"
            echo "  qps_failure              QPS测试失败"
            echo ""
            ;;
        *)
            echo "❌ 未知命令: $1"
            echo "使用 '$0 help' 查看帮助"
            exit 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
