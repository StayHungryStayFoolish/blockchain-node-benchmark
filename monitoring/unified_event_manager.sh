#!/bin/bash
# =====================================================================
# Unified Exception Event Manager
# =====================================================================
# Manage exception events from all components, ensure time range correlation analysis
# When any component detects an exception, notify other components to record data for the same time range
# =====================================================================

# Safely load configuration file to avoid readonly variable conflicts
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "Warning: Configuration file loading failed, using default configuration"
    MONITOR_INTERVAL=${MONITOR_INTERVAL:-10}
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi

# Avoid redefining readonly variables
if [[ -z "${EVENT_LOG:-}" ]]; then
    readonly EVENT_LOG="${MEMORY_SHARE_DIR}/unified_events.json"
fi
if [[ -z "${EVENT_LOCK:-}" ]]; then
    readonly EVENT_LOCK="${MEMORY_SHARE_DIR}/event_manager.lock"
fi

# Initialize event manager
init_event_manager() {
    echo "🎯 Initializing unified exception event manager..."
    
    # Create event log file
    echo "[]" > "$EVENT_LOG"
    
    echo "✅ Event manager initialization completed"
}

# Record exception event start
record_event_start() {
    local event_type="$1"      # block_height_diff, cpu_high, ebs_bottleneck, etc.
    local event_source="$2"    # block_height_monitor, unified_monitor, bottleneck_detector
    local event_details="$3"   # Detailed information
    local current_qps="${4:-0}" # Current QPS (if applicable)
    
    local start_time=$(get_unified_timestamp)
    local start_epoch=$(get_unified_epoch)
    local event_id="${event_type}_${start_epoch}"
    
    # Use file lock to ensure concurrency safety
    (
        flock -x 200
        
        # Read existing events
        local events="[]"
        if [[ -f "$EVENT_LOG" ]]; then
            events=$(cat "$EVENT_LOG")
        fi
        
        # Create new event record
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
        
        # Add to event list
        echo "$events" | jq ". += [$new_event]" > "$EVENT_LOG"
        
        echo "📢 Exception event started: $event_type (ID: $event_id)"
        echo "  Source: $event_source"
        echo "  Time: $start_time"
        echo "  Details: $event_details"
        
        # Notify other components to start recording detailed data
        notify_components_event_start "$event_id" "$event_type" "$start_time"
        
    ) 200>"$EVENT_LOCK"
    
    echo "$event_id"  # Return event ID
}

# Record exception event end
record_event_end() {
    local event_id="$1"
    
    local end_time=$(get_unified_timestamp)
    local end_epoch=$(get_unified_epoch)
    
    # Use file lock to ensure concurrency safety
    (
        flock -x 200
        
        if [[ -f "$EVENT_LOG" ]]; then
            # Update event record
            local updated_events=$(cat "$EVENT_LOG" | jq "
                map(if .event_id == \"$event_id\" then
                    .end_time = \"$end_time\" |
                    .end_epoch = $end_epoch |
                    .duration = (.end_epoch - .start_epoch) |
                    .status = \"completed\"
                else . end)
            ")
            
            echo "$updated_events" > "$EVENT_LOG"
            
            # Get event information
            local event_info=$(echo "$updated_events" | jq ".[] | select(.event_id == \"$event_id\")")
            local event_type=$(echo "$event_info" | jq -r '.event_type')
            local start_time=$(echo "$event_info" | jq -r '.start_time')
            local duration=$(echo "$event_info" | jq -r '.duration')
            
            echo "✅ Exception event ended: $event_type (ID: $event_id)"
            echo "  Duration: ${duration}s"
            echo "  Time range: $start_time → $end_time"
            
            # Notify other components event ended, start correlation analysis
            notify_components_event_end "$event_id" "$event_type" "$start_time" "$end_time"
            
            # Record time range for subsequent analysis
            record_time_range "$event_type" "$start_time" "$end_time"
        fi
        
    ) 200>"$EVENT_LOCK"
}

# Notify components of event start
notify_components_event_start() {
    local event_id="$1"
    local event_type="$2"
    local start_time="$3"
    
    # Create notification file
    local notification="{
        \"action\": \"event_start\",
        \"event_id\": \"$event_id\",
        \"event_type\": \"$event_type\",
        \"start_time\": \"$start_time\",
        \"timestamp\": \"$(get_unified_timestamp)\"
    }"
    
    echo "$notification" > "${MEMORY_SHARE_DIR}/event_notification.json"
    
    # Can add more notification mechanisms here, such as signals or message queues
}

# Notify components of event end
notify_components_event_end() {
    local event_id="$1"
    local event_type="$2"
    local start_time="$3"
    local end_time="$4"
    
    # Create notification file
    local notification="{
        \"action\": \"event_end\",
        \"event_id\": \"$event_id\",
        \"event_type\": \"$event_type\",
        \"start_time\": \"$start_time\",
        \"end_time\": \"$end_time\",
        \"timestamp\": \"$(get_unified_timestamp)\"
    }"
    
    echo "$notification" > "${MEMORY_SHARE_DIR}/event_notification.json"
    
    echo "🔗 Notified all components for time range correlation analysis"
    echo "  Event type: $event_type"
    echo "  Time range: $start_time → $end_time"
}

# Get active events
get_active_events() {
    if [[ -f "$EVENT_LOG" ]]; then
        cat "$EVENT_LOG" | jq '.[] | select(.status == "active")'
    else
        echo "[]"
    fi
}

# Get all events
get_all_events() {
    if [[ -f "$EVENT_LOG" ]]; then
        cat "$EVENT_LOG"
    else
        echo "[]"
    fi
}

# Get events by type
get_events_by_type() {
    local event_type="$1"
    
    if [[ -f "$EVENT_LOG" ]]; then
        cat "$EVENT_LOG" | jq ".[] | select(.event_type == \"$event_type\")"
    else
        echo "[]"
    fi
}

# Clean up old events
cleanup_old_events() {
    local max_age_hours="${1:-24}"  # Default keep 24 hours
    local cutoff_epoch=$(($(get_unified_epoch) - max_age_hours * 3600))
    
    if [[ -f "$EVENT_LOG" ]]; then
        (
            flock -x 200
            
            local filtered_events=$(cat "$EVENT_LOG" | jq "map(select(.start_epoch > $cutoff_epoch))")
            echo "$filtered_events" > "$EVENT_LOG"
            
            echo "🧹 Cleaned up old events from ${max_age_hours} hours ago"
            
        ) 200>"$EVENT_LOCK"
    fi
}

# Main function
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
            echo "  init                     Initialize event manager"
            echo "  start <type> <source> <details> [qps]  Record event start"
            echo "  end <event_id>           Record event end"
            echo "  active                   Show active events"
            echo "  all                      Show all events"
            echo "  type <event_type>        Show events of specified type"
            echo "  cleanup [hours]          Clean up old events"
            echo "  help                     Show help"
            echo ""
            echo "Event types:"
            echo "  block_height_diff        Block height difference exception"
            echo "  cpu_high                 High CPU usage"
            echo "  memory_high              High memory usage"
            echo "  ebs_bottleneck           EBS performance bottleneck"
            echo "  network_bottleneck       Network bottleneck"
            echo "  qps_failure              QPS test failure"
            echo ""
            ;;
        *)
            echo "❌ Unknown command: $1"
            echo "Use '$0 help' to view help"
            exit 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
