#!/bin/bash
# =====================================================================
# Intelligent Bottleneck Detector - For Intensive Testing
# =====================================================================
# Real-time monitoring of system metrics, automatic bottleneck detection
# Used for automatic stop condition determination in intensive test mode
# Uses unified logger
# =====================================================================

# Strict error handling - but allow safe use in interactive environments
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Use strict mode when script is executed directly
    set -euo pipefail
else
    # Use relaxed mode when sourced to avoid exiting shell
    set -uo pipefail
fi

# Safely load configuration file to avoid readonly variable conflicts
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "Warning: Configuration file loading failed, using default configuration"
    MONITOR_INTERVAL=${MONITOR_INTERVAL:-10}
    LOGS_DIR=${LOGS_DIR:-"/tmp/blockchain-node-benchmark/logs"}
fi
source "$(dirname "${BASH_SOURCE[0]}")/../utils/unified_logger.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../utils/ebs_converter.sh"
source "$(dirname "${BASH_SOURCE[0]}")/../core/common_functions.sh"

# Initialize unified logger
init_logger "bottleneck_detector" $LOG_LEVEL "${LOGS_DIR}/bottleneck_detector.log"

# Define bottleneck detection log file variable (for tee output)
BOTTLENECK_LOG="${LOGS_DIR}/bottleneck_detector.log"
# Dynamically build device field matching patterns - fix hardcoded device name issue
build_device_field_patterns() {
    local field_type="$1"  # util, r_await, avg_await, aws_standard_iops, throughput_mibs
    local patterns=()
    
    # DATA device pattern (required)
    patterns+=("data_${LEDGER_DEVICE}_${field_type}")
    
    # ACCOUNTS device pattern (optional)
    if is_accounts_configured; then
        patterns+=("accounts_${ACCOUNTS_DEVICE}_${field_type}")
    fi

    # Return pattern string separated by |
    local IFS='|'
    echo "${patterns[*]}"
}

# Build all required field patterns
EBS_UTIL_PATTERNS=$(build_device_field_patterns "util")
EBS_R_AWAIT_PATTERNS=$(build_device_field_patterns "r_await")
EBS_AVG_AWAIT_PATTERNS=$(build_device_field_patterns "avg_await")
EBS_AWS_IOPS_PATTERNS=$(build_device_field_patterns "aws_standard_iops")
EBS_THROUGHPUT_PATTERNS=$(build_device_field_patterns "throughput_mibs")

log_info "🔧 Dynamic field pattern construction completed:"
log_info "   EBS utilization pattern: $EBS_UTIL_PATTERNS"
log_info "   EBS latency pattern: $EBS_R_AWAIT_PATTERNS"

# Error handling function
handle_detector_error() {
    local exit_code=$?
    local line_number=$1
    log_error "Bottleneck detector error occurred at line $line_number, exit code: $exit_code"
    log_warn "Bottleneck detector exited abnormally, but does not affect main test process"
    # Bottleneck detector errors should not interrupt main test, return safe exit code
    exit 0
}

# Set error trap
trap 'handle_detector_error $LINENO' ERR

readonly BOTTLENECK_STATUS_FILE="${MEMORY_SHARE_DIR}/bottleneck_status.json"
readonly BOTTLENECK_COUNTERS_FILE="${MEMORY_SHARE_DIR}/bottleneck_counters.json"

# Create performance metrics JSON string
create_performance_metrics_json() {
    local cpu_usage="$1"
    local memory_usage="$2"
    local ebs_util="$3"
    local ebs_latency="$4"
    local ebs_aws_iops="$5"
    local ebs_throughput="$6"
    local network_util="$7"
    local error_rate="$8"
    
    cat << EOF
{
    "cpu_usage": ${cpu_usage:-null},
    "memory_usage": ${memory_usage:-null},
    "ebs_util": ${ebs_util:-null},
    "ebs_latency": ${ebs_latency:-null},
    "ebs_aws_iops": ${ebs_aws_iops:-null},
    "ebs_throughput": ${ebs_throughput:-null},
    "network_util": ${network_util:-null},
    "error_rate": ${error_rate:-null}
}
EOF
}

# Unified bottleneck status JSON generation function
generate_bottleneck_status_json() {
    local status="$1"
    local detected="$2"
    local types_csv="$3"
    local values_csv="$4"
    local current_qps="$5"
    local metrics_json="$6"
    
    # Extract values from JSON
    local cpu_usage=$(echo "$metrics_json" | jq -r '.cpu_usage // null' 2>/dev/null || echo "null")
    local memory_usage=$(echo "$metrics_json" | jq -r '.memory_usage // null' 2>/dev/null || echo "null")
    local ebs_util=$(echo "$metrics_json" | jq -r '.ebs_util // null' 2>/dev/null || echo "null")
    local ebs_latency=$(echo "$metrics_json" | jq -r '.ebs_latency // null' 2>/dev/null || echo "null")
    local ebs_aws_iops=$(echo "$metrics_json" | jq -r '.ebs_aws_iops // null' 2>/dev/null || echo "null")
    local ebs_throughput=$(echo "$metrics_json" | jq -r '.ebs_throughput // null' 2>/dev/null || echo "null")
    local network_util=$(echo "$metrics_json" | jq -r '.network_util // null' 2>/dev/null || echo "null")
    local error_rate=$(echo "$metrics_json" | jq -r '.error_rate // null' 2>/dev/null || echo "null")
    
    # Build JSON arrays
    local types_array="[]"
    local values_array="[]"
    local summary=""
    
    if [[ -n "$types_csv" ]]; then
        types_array="[\"$(echo "$types_csv" | sed 's/,/","/g')\"]"
        values_array="[\"$(echo "$values_csv" | sed 's/,/","/g')\"]"
        summary="$types_csv"
    fi
    
    # Generate unified JSON structure
    cat > "$BOTTLENECK_STATUS_FILE" << EOF
{
    "status": "$status",
    "bottleneck_detected": $detected,
    "bottleneck_types": $types_array,
    "bottleneck_values": $values_array,
    "bottleneck_summary": "$summary",
    "detection_time": $(if [[ "$detected" == "true" ]]; then echo "\"$(get_unified_timestamp)\""; else echo "null"; fi),
    "current_qps": $current_qps,
    "performance_metrics": {
        "cpu_usage": $cpu_usage,
        "memory_usage": $memory_usage,
        "ebs_util": $ebs_util,
        "ebs_latency": $ebs_latency,
        "ebs_aws_iops": $ebs_aws_iops,
        "ebs_throughput": $ebs_throughput,
        "network_util": $network_util,
        "error_rate": $error_rate
    },
    "ebs_baselines": {
        "data_baseline_iops": ${DATA_VOL_MAX_IOPS:-0},
        "data_baseline_throughput": ${DATA_VOL_MAX_THROUGHPUT:-0},
        "accounts_baseline_iops": ${ACCOUNTS_VOL_MAX_IOPS:-0},
        "accounts_baseline_throughput": ${ACCOUNTS_VOL_MAX_THROUGHPUT:-0}
    },
    "counters": {
        "cpu": ${BOTTLENECK_COUNTERS["cpu"]:-0},
        "memory": ${BOTTLENECK_COUNTERS["memory"]:-0},
        "ebs_util": ${BOTTLENECK_COUNTERS["ebs_util"]:-0},
        "ebs_latency": ${BOTTLENECK_COUNTERS["ebs_latency"]:-0},
        "ebs_aws_iops": ${BOTTLENECK_COUNTERS["ebs_aws_iops"]:-0},
        "ebs_aws_throughput": ${BOTTLENECK_COUNTERS["ebs_aws_throughput"]:-0},
        "network": ${BOTTLENECK_COUNTERS["network"]:-0},
        "ena_limit": ${BOTTLENECK_COUNTERS["ena_limit"]:-0},
        "error_rate": ${BOTTLENECK_COUNTERS["error_rate"]:-0},
        "rpc_latency": ${BOTTLENECK_COUNTERS["rpc_latency"]:-0}
    }
}
EOF
}

# Bottleneck detection counters - must be declared before use
declare -A BOTTLENECK_COUNTERS

# Save counters to shared memory file
save_bottleneck_counters() {
    local json_content="{"
    local first=true
    
    # Temporarily disable set -u to check array length (empty array triggers unbound variable)
    set +u
    local array_size=${#BOTTLENECK_COUNTERS[@]}
    set -u
    
    if [[ $array_size -gt 0 ]]; then
        for key in "${!BOTTLENECK_COUNTERS[@]}"; do
            if [[ "$first" == "true" ]]; then
                first=false
            else
                json_content+=","
            fi
            json_content+="\"$key\":${BOTTLENECK_COUNTERS[$key]}"
        done
    fi
    
    json_content+="}"
    echo "$json_content" > "$BOTTLENECK_COUNTERS_FILE"
}

# Load counters from shared memory file
load_bottleneck_counters() {
    if [[ -f "$BOTTLENECK_COUNTERS_FILE" ]]; then
        # Use jq to parse JSON and populate array
        local keys=$(jq -r 'keys[]' "$BOTTLENECK_COUNTERS_FILE" 2>/dev/null)
        if [[ -n "$keys" ]]; then
            while IFS= read -r key; do
                local value=$(jq -r ".\"$key\"" "$BOTTLENECK_COUNTERS_FILE" 2>/dev/null)
                BOTTLENECK_COUNTERS["$key"]=$value
            done <<< "$keys"
            return 0
        fi
    fi
    return 1
}

# Initialize bottleneck detection counters
initialize_bottleneck_counters() {
    # Basic counters
    BOTTLENECK_COUNTERS["cpu"]=0
    BOTTLENECK_COUNTERS["memory"]=0
    BOTTLENECK_COUNTERS["network"]=0
    BOTTLENECK_COUNTERS["error_rate"]=0
    BOTTLENECK_COUNTERS["rpc_latency"]=0
    BOTTLENECK_COUNTERS["rpc_success_rate"]=0
    BOTTLENECK_COUNTERS["rpc_connection"]=0
    BOTTLENECK_COUNTERS["ena_limit"]=0
    
    # DATA device counters
    BOTTLENECK_COUNTERS["ebs_util"]=0
    BOTTLENECK_COUNTERS["ebs_latency"]=0
    BOTTLENECK_COUNTERS["ebs_aws_iops"]=0
    BOTTLENECK_COUNTERS["ebs_aws_throughput"]=0
    
    # ACCOUNTS device counters (if ACCOUNTS device is configured)
    if is_accounts_configured; then
        BOTTLENECK_COUNTERS["accounts_ebs_util"]=0
        BOTTLENECK_COUNTERS["accounts_ebs_latency"]=0
        BOTTLENECK_COUNTERS["accounts_ebs_aws_iops"]=0
        BOTTLENECK_COUNTERS["accounts_ebs_aws_throughput"]=0
        log_debug "ACCOUNTS device bottleneck counters initialized"
    fi
    
    # Persist to shared memory file
    save_bottleneck_counters
    
    log_debug "Bottleneck detection counters initialization completed"
}

# Reset resource bottleneck counters (preserve RPC counters)
reset_resource_bottleneck_counters() {
    # Only reset resource-related counters
    BOTTLENECK_COUNTERS["cpu"]=0
    BOTTLENECK_COUNTERS["memory"]=0
    BOTTLENECK_COUNTERS["network"]=0
    BOTTLENECK_COUNTERS["ena_limit"]=0
    
    # DATA device counters
    BOTTLENECK_COUNTERS["ebs_util"]=0
    BOTTLENECK_COUNTERS["ebs_latency"]=0
    BOTTLENECK_COUNTERS["ebs_aws_iops"]=0
    BOTTLENECK_COUNTERS["ebs_aws_throughput"]=0
    
    # ACCOUNTS device counters
    if is_accounts_configured; then
        BOTTLENECK_COUNTERS["accounts_ebs_util"]=0
        BOTTLENECK_COUNTERS["accounts_ebs_latency"]=0
        BOTTLENECK_COUNTERS["accounts_ebs_aws_iops"]=0
        BOTTLENECK_COUNTERS["accounts_ebs_aws_throughput"]=0
    fi
    
    # Preserve RPC counters:
    # - rpc_success_rate
    # - rpc_latency
    # - rpc_connection
    # - error_rate
    
    log_debug "Resource bottleneck counters reset, RPC counters preserved"
}

# Initialize bottleneck detection
init_bottleneck_detection() {
    echo "🔍 Initializing intelligent bottleneck detector..." | tee -a "$BOTTLENECK_LOG"
    
    # Ensure status file directory exists
    mkdir -p "$(dirname "$BOTTLENECK_STATUS_FILE")"
    log_info "Status file directory created: $(dirname "$BOTTLENECK_STATUS_FILE")"
    
    # Initialize counters
    initialize_bottleneck_counters
    
    echo "📊 Bottleneck detection thresholds:" | tee -a "$BOTTLENECK_LOG"
    echo "  CPU usage: ${BOTTLENECK_CPU_THRESHOLD}%" | tee -a "$BOTTLENECK_LOG"
    echo "  Memory usage: ${BOTTLENECK_MEMORY_THRESHOLD}%" | tee -a "$BOTTLENECK_LOG"
    echo "  EBS utilization: ${BOTTLENECK_EBS_UTIL_THRESHOLD}%" | tee -a "$BOTTLENECK_LOG"
    echo "  EBS latency: ${BOTTLENECK_EBS_LATENCY_THRESHOLD}ms" | tee -a "$BOTTLENECK_LOG"
    echo "  Network utilization: ${BOTTLENECK_NETWORK_THRESHOLD}%" | tee -a "$BOTTLENECK_LOG"
    echo "  Error rate: ${BOTTLENECK_ERROR_RATE_THRESHOLD}%" | tee -a "$BOTTLENECK_LOG"
    
    # Display EBS baseline configuration
    if [[ -n "$DATA_VOL_MAX_IOPS" ]]; then
        echo "📋 EBS performance baselines:" | tee -a "$BOTTLENECK_LOG"
        echo "  DATA device baseline: ${DATA_VOL_MAX_IOPS} IOPS, ${DATA_VOL_MAX_THROUGHPUT} MiB/s" | tee -a "$BOTTLENECK_LOG"
        
        # Fix: Use complete ACCOUNTS check logic, consistent with other places
        if is_accounts_configured && [[ -n "$ACCOUNTS_VOL_MAX_THROUGHPUT" ]]; then
            echo "  ACCOUNTS device baseline: ${ACCOUNTS_VOL_MAX_IOPS} IOPS, ${ACCOUNTS_VOL_MAX_THROUGHPUT} MiB/s" | tee -a "$BOTTLENECK_LOG"
        fi
    fi
    echo "  Consecutive detection count: ${BOTTLENECK_CONSECUTIVE_COUNT}" | tee -a "$BOTTLENECK_LOG"
    echo ""
    
    # Initialize status file
    local empty_metrics=$(create_performance_metrics_json "null" "null" "null" "null" "null" "null" "null" "null")
    generate_bottleneck_status_json "initialized" "false" "" "" "null" "$empty_metrics"
    
    echo "✅ Bottleneck detector initialization completed"
    echo "📄 Status file: $BOTTLENECK_STATUS_FILE"
    
    # Verify status file creation
    if [[ -f "$BOTTLENECK_STATUS_FILE" ]]; then
        log_info "Bottleneck status file created successfully: $BOTTLENECK_STATUS_FILE"
        echo "📊 Initial status file content:"
        cat "$BOTTLENECK_STATUS_FILE" | jq . 2>/dev/null || cat "$BOTTLENECK_STATUS_FILE"
    else
        log_error "Bottleneck status file creation failed: $BOTTLENECK_STATUS_FILE"
    fi
}

# Detect CPU bottleneck
check_cpu_bottleneck() {
    local cpu_usage="$1"
    
    if (( $(awk "BEGIN {print ($cpu_usage > $BOTTLENECK_CPU_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo 0) )); then
        BOTTLENECK_COUNTERS["cpu"]=$((${BOTTLENECK_COUNTERS["cpu"]:-0} + 1))
        echo "⚠️  CPU bottleneck detection: ${cpu_usage}% > ${BOTTLENECK_CPU_THRESHOLD}% (${BOTTLENECK_COUNTERS["cpu"]:-0}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["cpu"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            return 0  # Bottleneck detected
        fi
    else
        BOTTLENECK_COUNTERS["cpu"]=0  # Reset counter
    fi
    
    return 1  # No bottleneck detected
}

# Detect memory bottleneck
check_memory_bottleneck() {
    local memory_usage="$1"
    
    if (( $(awk "BEGIN {print ($memory_usage > $BOTTLENECK_MEMORY_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo 0) )); then
        BOTTLENECK_COUNTERS["memory"]=$((${BOTTLENECK_COUNTERS["memory"]:-0} + 1))
        echo "⚠️  Memory bottleneck detection: ${memory_usage}% > ${BOTTLENECK_MEMORY_THRESHOLD}% (${BOTTLENECK_COUNTERS["memory"]:-0}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["memory"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            return 0  # Bottleneck detected
        fi
    else
        BOTTLENECK_COUNTERS["memory"]=0  # Reset counter
    fi
    
    return 1  # No bottleneck detected
}

check_ebs_bottleneck() {
    local ebs_aws_iops="$1"
    local ebs_throughput="$2"
    local device_type="${3:-data}" # Device type: "data" or "accounts", default is "data"
    
    local bottleneck_detected=false
    
    # Select correct baseline values and counter prefix based on device type
    local baseline_iops="$DATA_VOL_MAX_IOPS"
    local baseline_throughput="$DATA_VOL_MAX_THROUGHPUT"
    local counter_prefix="ebs"
    
    if [[ "$device_type" == "accounts" ]]; then
        # Check if ACCOUNTS device baseline values are configured
        if [[ -n "$ACCOUNTS_VOL_MAX_IOPS" && -n "$ACCOUNTS_VOL_MAX_THROUGHPUT" ]]; then
            baseline_iops="$ACCOUNTS_VOL_MAX_IOPS"
            baseline_throughput="$ACCOUNTS_VOL_MAX_THROUGHPUT"
            counter_prefix="accounts_ebs"
            log_debug "Using ACCOUNTS device baseline: IOPS=$baseline_iops, Throughput=$baseline_throughput"
        else
            log_debug "ACCOUNTS device baseline values not configured, using DATA device baseline values"
        fi
    else
        log_debug "Using DATA device baseline: IOPS=$baseline_iops, Throughput=$baseline_throughput"
    fi
    
    # Validate baseline values
    if [[ -z "$baseline_iops" || -z "$baseline_throughput" ]]; then
        log_debug "Invalid baseline values, skipping AWS baseline bottleneck detection"
        baseline_iops=""
        baseline_throughput=""
    fi
    
    # AWS baseline IOPS bottleneck detection (using device-specific baseline values)
    if [[ -n "$ebs_aws_iops" && -n "$baseline_iops" ]]; then
        local aws_iops_utilization=$(awk "BEGIN {printf \"%.4f\", $ebs_aws_iops / $baseline_iops}" 2>/dev/null || echo "0")
        local aws_iops_threshold=$(awk "BEGIN {printf \"%.2f\", ${BOTTLENECK_EBS_IOPS_THRESHOLD:-90} / 100}")
        log_debug "EBS IOPS bottleneck detection threshold: ${BOTTLENECK_EBS_IOPS_THRESHOLD:-90}% (${aws_iops_threshold})"
        
        if (( $(awk "BEGIN {print ($aws_iops_utilization > $aws_iops_threshold) ? 1 : 0}" 2>/dev/null || echo 0) )); then
            BOTTLENECK_COUNTERS["${counter_prefix}_aws_iops"]=$((${BOTTLENECK_COUNTERS["${counter_prefix}_aws_iops"]:-0} + 1))
            echo "⚠️  EBS AWS baseline IOPS bottleneck (${device_type}): ${ebs_aws_iops}/${baseline_iops} (${aws_iops_utilization%.*}%) > ${aws_iops_threshold%.*}% (${BOTTLENECK_COUNTERS["${counter_prefix}_aws_iops"]:-0}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
            
            if [[ ${BOTTLENECK_COUNTERS["${counter_prefix}_aws_iops"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
                bottleneck_detected=true
            fi
        else
            BOTTLENECK_COUNTERS["${counter_prefix}_aws_iops"]=0
        fi
    fi
    
    # AWS baseline throughput bottleneck detection (using device-specific baseline values)
    if [[ -n "$ebs_throughput" && -n "$baseline_throughput" ]]; then
        local aws_throughput_utilization=$(awk "BEGIN {printf \"%.4f\", $ebs_throughput / $baseline_throughput}" 2>/dev/null || echo "0")
        local aws_throughput_threshold=$(awk "BEGIN {printf \"%.2f\", ${BOTTLENECK_EBS_THROUGHPUT_THRESHOLD:-90} / 100}")
        log_debug "EBS Throughput bottleneck detection threshold: ${BOTTLENECK_EBS_THROUGHPUT_THRESHOLD:-90}% (${aws_throughput_threshold})"
        
        if (( $(awk "BEGIN {print ($aws_throughput_utilization > $aws_throughput_threshold) ? 1 : 0}" 2>/dev/null || echo 0) )); then
            BOTTLENECK_COUNTERS["${counter_prefix}_aws_throughput"]=$((${BOTTLENECK_COUNTERS["${counter_prefix}_aws_throughput"]:-0} + 1))
            echo "⚠️  EBS AWS baseline throughput bottleneck (${device_type}): ${ebs_throughput}/${baseline_throughput} MiB/s (${aws_throughput_utilization%.*}%) > ${aws_throughput_threshold%.*}% (${BOTTLENECK_COUNTERS["${counter_prefix}_aws_throughput"]:-0}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
            
            if [[ ${BOTTLENECK_COUNTERS["${counter_prefix}_aws_throughput"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
                bottleneck_detected=true
            fi
        else
            BOTTLENECK_COUNTERS["${counter_prefix}_aws_throughput"]=0
        fi
    fi
    
    if [[ "$bottleneck_detected" == "true" ]]; then
        return 0
    else
        return 1
    fi
}

# Detect ENA network limit bottleneck
check_ena_network_bottleneck() {
    local performance_csv="$1"
    
    # Check if ENA monitoring is enabled
    if [[ "$ENA_MONITOR_ENABLED" != "true" ]]; then
        return 1
    fi
    
    if [[ ! -f "$performance_csv" ]] || [[ ! -s "$performance_csv" ]]; then
        return 1
    fi
    
    # Get latest ENA data
    local latest_data=$(tail -1 "$performance_csv" 2>/dev/null)
    if [[ -z "$latest_data" ]]; then
        return 1
    fi
    
    local header=$(head -1 "$performance_csv")
    
    # Configuration-driven: dynamically find all ENA field indices
    declare -A ena_field_indices
    declare -A ena_field_values
    
    # Iterate through configured fields, no hardcoding - use standardized array access
    ena_fields=($ENA_ALLOWANCE_FIELDS_STR)
    
    # Parse data line (use IFS to avoid space splitting issues)
    local fields
    IFS=',' read -ra fields <<< "$latest_data"
    
    for field in "${ena_fields[@]}"; do
        local field_idx=$(echo "$header" | tr ',' '\n' | grep -n "^$field$" | cut -d: -f1)
        if [[ -n "$field_idx" ]]; then
            ena_field_indices["$field"]=$field_idx
            ena_field_values["$field"]="${fields[$((field_idx - 1))]:-0}"
        fi
    done
    
    # Check if any ENA fields were found
    if [[ ${#ena_field_values[@]} -eq 0 ]]; then
        return 1  # No ENA data found
    fi
    
    # ENA baseline value management (lazy loading)
    local ena_baseline_file="${MEMORY_SHARE_DIR}/ena_baseline.json"
    declare -A ena_baseline_values
    
    if [[ ! -f "$ena_baseline_file" ]]; then
        # First call: read CSV second line as baseline values
        local baseline_data=$(sed -n '2p' "$performance_csv" 2>/dev/null)
        if [[ -n "$baseline_data" ]]; then
            local baseline_fields
            IFS=',' read -ra baseline_fields <<< "$baseline_data"
            
            # Save baseline values to file
            local baseline_json="{"
            local first=true
            for field in "${!ena_field_indices[@]}"; do
                local idx="${ena_field_indices[$field]}"
                local baseline_val="${baseline_fields[$((idx - 1))]:-0}"
                ena_baseline_values["$field"]=$baseline_val
                
                if [[ "$first" == "true" ]]; then
                    first=false
                else
                    baseline_json+=","
                fi
                baseline_json+="\"$field\":$baseline_val"
            done
            baseline_json+="}"
            echo "$baseline_json" > "$ena_baseline_file"
            log_debug "ENA baseline values saved: $ena_baseline_file"
        else
            # CSV only has header, no data, skip detection
            return 1
        fi
    else
        # Load existing baseline values
        for field in "${!ena_field_indices[@]}"; do
            local baseline_val=$(jq -r ".\"$field\" // 0" "$ena_baseline_file" 2>/dev/null || echo "0")
            ena_baseline_values["$field"]=$baseline_val
        done
    fi
    
    # Calculate delta values
    declare -A ena_delta_values
    for field in "${!ena_field_values[@]}"; do
        local current_val="${ena_field_values[$field]}"
        local baseline_val="${ena_baseline_values[$field]:-0}"
        local delta=$((current_val - baseline_val))
        # Delta cannot be negative
        if [[ $delta -lt 0 ]]; then
            delta=0
        fi
        ena_delta_values["$field"]=$delta
    done
    
    # Detect exceeded type fields (using delta values)
    local exceeded_detected=false
    local exceeded_summary=""
    local exceeded_count=0
    
    for field in "${!ena_delta_values[@]}"; do
        if [[ "$field" == *"exceeded"* ]] && [[ "${ena_delta_values[$field]}" -gt 0 ]]; then
            exceeded_detected=true
            ((exceeded_count++))
            if [[ -n "$exceeded_summary" ]]; then
                exceeded_summary="$exceeded_summary, $field=${ena_delta_values[$field]}"
            else
                exceeded_summary="$field=${ena_delta_values[$field]}"
            fi
        fi
    done
    
    # Detect abnormally low values for available type fields (optional additional detection)
    for field in "${!ena_field_values[@]}"; do
        if [[ "$field" == *"available"* ]]; then
            local available_value="${ena_field_values[$field]}"
            # If available value is 0, may also indicate resource exhaustion
            if [[ "$available_value" -eq 0 ]]; then
                if [[ -n "$exceeded_summary" ]]; then
                    exceeded_summary="$exceeded_summary, $field=0(exhausted)"
                else
                    exceeded_summary="$field=0(exhausted)"
                fi
                exceeded_detected=true
            fi
        fi
    done
    
    if [[ "$exceeded_detected" == "true" ]]; then
        BOTTLENECK_COUNTERS["ena_limit"]=$((${BOTTLENECK_COUNTERS["ena_limit"]:-0} + 1))
        echo "⚠️  ENA network limit detection: $exceeded_summary (${BOTTLENECK_COUNTERS["ena_limit"]:-0}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["ena_limit"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            return 0  # ENA bottleneck detected
        fi
    else
        BOTTLENECK_COUNTERS["ena_limit"]=0  # Reset counter
    fi

    # No ENA bottleneck detected
    return 1
}

# Detect general network bottleneck (based on network utilization threshold)
check_network_bottleneck() {
    local network_util="$1"
    
    if (( $(awk "BEGIN {print ($network_util > $BOTTLENECK_NETWORK_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo 0) )); then
        BOTTLENECK_COUNTERS["network"]=$((${BOTTLENECK_COUNTERS["network"]:-0} + 1))
        echo "⚠️  Network bottleneck detection: ${network_util}% > ${BOTTLENECK_NETWORK_THRESHOLD}% (${BOTTLENECK_COUNTERS["network"]:-0}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["network"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            return 0  # Bottleneck detected
        fi
    else
        BOTTLENECK_COUNTERS["network"]=0  # Reset counter
    fi
    
    return 1  # No bottleneck detected
}

# Get latest QPS error rate
get_latest_qps_error_rate() {
    # Find latest QPS test report file
    local latest_report=$(find "${REPORTS_DIR}" -name "qps_*_report.txt" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
    
    if [[ -z "$latest_report" || ! -f "$latest_report" ]]; then
        echo "0"
        return
    fi
    
    # Extract success rate from report, calculate error rate
    local success_rate=$(grep "Success" "$latest_report" | awk '{print $NF}' | sed 's/%//' 2>/dev/null)
    
    if [[ -n "$success_rate" && "$success_rate" =~ ^[0-9]+\.?[0-9]*$ ]]; then
        local error_rate=$(awk "BEGIN {printf \"%.2f\", 100 - $success_rate}" 2>/dev/null || echo "0")
        echo "$error_rate"
    else
        echo "0"
    fi
}

# Detect QPS bottleneck (error rate and RPC latency)
check_qps_bottleneck() {
    local current_qps="$1"
    local error_rate="$2"
    
    # Get latest QPS test latency
    local latest_report=$(find "${REPORTS_DIR}" -name "qps_*_report.txt" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
    local rpc_latency=0
    
    if [[ -n "$latest_report" && -f "$latest_report" ]]; then
        # Extract P99 latency
        rpc_latency=$(grep "Latencies" "$latest_report" | awk -F',' '{print $(NF-1)}' | sed 's/[^0-9.]//g' 2>/dev/null || echo "0")
    fi
    
    local qps_bottleneck_detected=false
    
    # Detect error rate bottleneck
    if (( $(awk "BEGIN {print ($error_rate > $BOTTLENECK_ERROR_RATE_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo 0) )); then
        BOTTLENECK_COUNTERS["error_rate"]=$((${BOTTLENECK_COUNTERS["error_rate"]:-0} + 1))
        echo "⚠️  QPS error rate bottleneck detection: ${error_rate}% > ${BOTTLENECK_ERROR_RATE_THRESHOLD}% (${BOTTLENECK_COUNTERS["error_rate"]:-0}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["error_rate"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            qps_bottleneck_detected=true
        fi
    else
        BOTTLENECK_COUNTERS["error_rate"]=0
    fi
    
    # Detect RPC latency bottleneck (P99 latency exceeding 1000ms considered bottleneck)
    local rpc_latency_threshold=1000
    if (( $(awk "BEGIN {print ($rpc_latency > $rpc_latency_threshold) ? 1 : 0}" 2>/dev/null || echo 0) )); then
        BOTTLENECK_COUNTERS["rpc_latency"]=$((${BOTTLENECK_COUNTERS["rpc_latency"]:-0} + 1))
        echo "⚠️  RPC latency bottleneck detection: ${rpc_latency}ms > ${rpc_latency_threshold}ms (${BOTTLENECK_COUNTERS["rpc_latency"]:-0}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["rpc_latency"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            qps_bottleneck_detected=true
        fi
    else
        BOTTLENECK_COUNTERS["rpc_latency"]=0
    fi
    
    if [[ "$qps_bottleneck_detected" == "true" ]]; then
        return 0  # QPS bottleneck detected
    else
        return 1  # No QPS bottleneck detected
    fi
}

# Detect RPC connection failure
check_rpc_connection_bottleneck() {
    local timeout=2
    
    # Don't use cache, test connection directly (avoid cache masking failures)
    local result=$(timeout $timeout curl -s -X POST -H "Content-Type: application/json" \
        --data '{"jsonrpc":"2.0","id":1,"method":"getBlockHeight","params":[]}' \
        "$LOCAL_RPC_URL" 2>&1)
    
    local exit_code=$?
    
    if [[ $exit_code -ne 0 ]]; then
        # Connection failed
        BOTTLENECK_COUNTERS["rpc_connection"]=$((${BOTTLENECK_COUNTERS["rpc_connection"]:-0} + 1))
        echo "⚠️  RPC connection failed: exit_code=$exit_code (${BOTTLENECK_COUNTERS["rpc_connection"]:-0}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["rpc_connection"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            return 0  # Connection bottleneck detected
        fi
    else
        BOTTLENECK_COUNTERS["rpc_connection"]=0
    fi
    
    return 1
}

# Detect RPC performance bottleneck (success rate and latency)
check_rpc_performance_bottleneck() {
    local vegeta_result="$1"
    
    if [[ -z "$vegeta_result" || ! -f "$vegeta_result" ]]; then
        log_debug "Vegeta result file does not exist, skipping RPC performance detection: $vegeta_result"
        return 1
    fi
    
    local rpc_bottleneck_detected=false
    
    local total_requests=$(jq -r '.requests // 1' "$vegeta_result" 2>/dev/null || echo "1")
    local success_requests=$(jq -r '.status_codes."200" // 0' "$vegeta_result" 2>/dev/null || echo "0")
    local success_rate=$(awk "BEGIN {printf \"%.0f\", $success_requests * 100 / $total_requests}" 2>/dev/null || echo "0")
    
    local avg_latency_ns=$(jq -r '.latencies.mean // 0' "$vegeta_result" 2>/dev/null || echo "0")
    local avg_latency=$(awk "BEGIN {printf \"%.2f\", $avg_latency_ns / 1000000}" 2>/dev/null || echo "0")
    
    if (( $(awk "BEGIN {print ($success_rate < $SUCCESS_RATE_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo 0) )); then
        BOTTLENECK_COUNTERS["rpc_success_rate"]=$((${BOTTLENECK_COUNTERS["rpc_success_rate"]:-0} + 1))
        echo "⚠️  RPC success rate bottleneck: ${success_rate}% < ${SUCCESS_RATE_THRESHOLD}% (${BOTTLENECK_COUNTERS["rpc_success_rate"]:-0}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["rpc_success_rate"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            rpc_bottleneck_detected=true
        fi
    else
        BOTTLENECK_COUNTERS["rpc_success_rate"]=0
    fi
    
    if (( $(awk "BEGIN {print ($avg_latency > $MAX_LATENCY_THRESHOLD) ? 1 : 0}" 2>/dev/null || echo 0) )); then
        BOTTLENECK_COUNTERS["rpc_latency"]=$((${BOTTLENECK_COUNTERS["rpc_latency"]:-0} + 1))
        echo "⚠️  RPC latency bottleneck: ${avg_latency}ms > ${MAX_LATENCY_THRESHOLD}ms (${BOTTLENECK_COUNTERS["rpc_latency"]:-0}/${BOTTLENECK_CONSECUTIVE_COUNT})" | tee -a "$BOTTLENECK_LOG"
        
        if [[ ${BOTTLENECK_COUNTERS["rpc_latency"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            rpc_bottleneck_detected=true
        fi
    else
        BOTTLENECK_COUNTERS["rpc_latency"]=0
    fi
    
    if [[ "$rpc_bottleneck_detected" == "true" ]]; then
        return 0
    else
        return 1
    fi
}

# Extract metrics from performance data
extract_performance_metrics() {
    local performance_csv="$1"
    
    if [[ ! -f "$performance_csv" ]]; then
        echo "0,0,0,0,0,0"  # cpu,memory,ebs_util,ebs_latency,network,error_rate
        return
    fi
    
    # Get latest performance data (last line)
    local latest_data=$(tail -1 "$performance_csv" 2>/dev/null)
    
    if [[ -z "$latest_data" ]]; then
        echo "0,0,0,0,0,0,0,0"  # cpu,memory,ebs_util,ebs_latency,ebs_aws_iops,ebs_throughput,network,error_rate
        return
    fi
    
    # Use CSV field mapper to dynamically parse field positions
    local header=$(head -1 "$performance_csv")
    IFS=',' read -ra field_names <<< "$header"
    IFS=',' read -ra data_values <<< "$latest_data"
    
    # Dynamically find field positions
    local cpu_usage=0
    local memory_usage=0
    local ebs_util=0
    local ebs_latency=0
    local ebs_aws_iops=0
    local ebs_throughput=0
    local network_util=0
    local error_rate=0
    
    # Use dynamic field matching instead of hardcoding
    for i in "${!field_names[@]}"; do
        local field_name="${field_names[i]}"
        
        case "$field_name" in
            # CPU and memory fields (unchanged)
            "cpu_usage"|"cpu_percent"|"cpu_total")
                cpu_usage=${data_values[i]:-0}
                ;;
            "mem_usage"|"memory_usage"|"mem_percent")
                memory_usage=${data_values[i]:-0}
                ;;
            # Network total traffic fields (unchanged)
            "net_total_mbps"|"network_total_mbps"|"total_mbps")
                local current_mbps=${data_values[i]:-0}
                network_util=$(awk "BEGIN {printf \"%.2f\", ($current_mbps / $NETWORK_MAX_BANDWIDTH_MBPS) * 100}" 2>/dev/null || echo "0")
                network_util=$(awk "BEGIN {printf \"%.2f\", ($network_util > 100) ? 100 : $network_util}" 2>/dev/null || echo "0")
                ;;
        esac
        
        # Use dynamic pattern matching for EBS fields
        if [[ "$EBS_UTIL_PATTERNS" == *"$field_name"* ]]; then
            ebs_util=${data_values[i]:-0}
            log_debug "Matched EBS utilization field: $field_name = $ebs_util"
        fi
        
        if [[ "$EBS_R_AWAIT_PATTERNS" == *"$field_name"* ]]; then
            ebs_latency=${data_values[i]:-0}
            log_debug "Matched EBS read latency field: $field_name = $ebs_latency"
        elif [[ "$EBS_AVG_AWAIT_PATTERNS" == *"$field_name"* ]] && [[ "$ebs_latency" == "0" ]]; then
            # If latency value not set yet, use average latency
            ebs_latency=${data_values[i]:-0}
            log_debug "Matched EBS average latency field: $field_name = $ebs_latency"
        fi
        
        if [[ "$EBS_AWS_IOPS_PATTERNS" == *"$field_name"* ]]; then
            ebs_aws_iops=${data_values[i]:-0}
            log_debug "Matched EBS AWS IOPS field: $field_name = $ebs_aws_iops"
        fi
        
        if [[ "$EBS_THROUGHPUT_PATTERNS" == *"$field_name"* ]]; then
            ebs_throughput=${data_values[i]:-0}
            log_debug "Matched EBS throughput field: $field_name = $ebs_throughput"
        fi
    done
    
    # This requires reading the latest QPS test report file
    error_rate=$(get_latest_qps_error_rate)
    
    echo "$cpu_usage,$memory_usage,$ebs_util,$ebs_latency,$ebs_aws_iops,$ebs_throughput,$network_util,$error_rate"
}

# Multi-device EBS bottleneck detection coordinator
detect_all_ebs_bottlenecks() {
    local performance_csv="$1"
    local bottleneck_detected=false
    local bottleneck_info=()
    
    # Read CSV data
    if [[ ! -f "$performance_csv" ]]; then
        log_debug "Performance data file does not exist: $performance_csv"
        return 1
    fi
    
    local latest_line=$(tail -n 1 "$performance_csv")
    if [[ -z "$latest_line" ]]; then
        log_debug "Performance data file is empty"
        return 1
    fi
    
    # Parse CSV header and data
    local header_line=$(head -n 1 "$performance_csv")
    IFS=',' read -ra field_names <<< "$header_line"
    IFS=',' read -ra data_values <<< "$latest_line"
    
    # Detect DATA device
    local data_util=0 data_latency=0 data_aws_iops=0 data_throughput=0
    
    for i in "${!field_names[@]}"; do
        local field_name="${field_names[i]}"
        
        # DATA device field matching
        if [[ "$field_name" == data_${LEDGER_DEVICE}_util ]]; then
            data_util=${data_values[i]:-0}
        elif [[ "$field_name" == data_${LEDGER_DEVICE}_r_await ]]; then
            data_latency=${data_values[i]:-0}
        elif [[ "$field_name" == data_${LEDGER_DEVICE}_avg_await ]] && [[ "$data_latency" == "0" ]]; then
            data_latency=${data_values[i]:-0}
        elif [[ "$field_name" == data_${LEDGER_DEVICE}_aws_standard_iops ]]; then
            data_aws_iops=${data_values[i]:-0}
        elif [[ "$field_name" == data_${LEDGER_DEVICE}_aws_standard_throughput_mibs ]]; then
            data_throughput=${data_values[i]:-0}
        fi
    done
    
    # Detect DATA device bottleneck
    if check_ebs_bottleneck "$data_aws_iops" "$data_throughput" "data"; then
        bottleneck_detected=true
        bottleneck_info+=("DATA device bottleneck: AWS_IOPS=${data_aws_iops}, Throughput=${data_throughput}MiB/s")
    fi
    
    # Detect ACCOUNTS device (if configured)
    if is_accounts_configured; then
        local accounts_util=0 accounts_latency=0 accounts_aws_iops=0 accounts_throughput=0
        
        for i in "${!field_names[@]}"; do
            local field_name="${field_names[i]}"
            
            # ACCOUNTS device field matching
            if [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_util ]]; then
                accounts_util=${data_values[i]:-0}
            elif [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_r_await ]]; then
                accounts_latency=${data_values[i]:-0}
            elif [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_avg_await ]] && [[ "$accounts_latency" == "0" ]]; then
                accounts_latency=${data_values[i]:-0}
            elif [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_aws_standard_iops ]]; then
                accounts_aws_iops=${data_values[i]:-0}
            elif [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_aws_standard_throughput_mibs ]]; then
                accounts_throughput=${data_values[i]:-0}
            fi
        done
        
        # Detect ACCOUNTS device bottleneck
        if check_ebs_bottleneck "$accounts_aws_iops" "$accounts_throughput" "accounts"; then
            bottleneck_detected=true
            bottleneck_info+=("ACCOUNTS device bottleneck: AWS_IOPS=${accounts_aws_iops}, Throughput=${accounts_throughput}MiB/s")
        fi
    fi
    
    # Output detection results
    if [[ "$bottleneck_detected" == "true" ]]; then
        echo "🚨 EBS bottleneck detected:" | tee -a "$BOTTLENECK_LOG"
        for info in "${bottleneck_info[@]}"; do
            echo "   - $info" | tee -a "$BOTTLENECK_LOG"
        done
        return 0
    else
        log_debug "No EBS bottleneck detected"
        return 1
    fi
}

# Comprehensive bottleneck detection
detect_bottleneck() {
    local current_qps="$1"
    local performance_csv="$2"
    local vegeta_result="${3:-}"
    
    # Extract performance metrics
    local metrics=$(extract_performance_metrics "$performance_csv")
    local cpu_usage=$(echo "$metrics" | cut -d',' -f1)
    local memory_usage=$(echo "$metrics" | cut -d',' -f2)
    local ebs_util=$(echo "$metrics" | cut -d',' -f3)
    local ebs_latency=$(echo "$metrics" | cut -d',' -f4)
    local ebs_aws_iops=$(echo "$metrics" | cut -d',' -f5)
    local ebs_throughput=$(echo "$metrics" | cut -d',' -f6)
    local network_util=$(echo "$metrics" | cut -d',' -f7)
    local error_rate=$(echo "$metrics" | cut -d',' -f8)
    
    echo "📊 Current QPS: $current_qps, Performance metrics: CPU=${cpu_usage}%, MEM=${memory_usage}%, EBS=${ebs_util}%/${ebs_latency}ms, AWS_IOPS=${ebs_aws_iops}, THROUGHPUT=${ebs_throughput}MiB/s, NET=${network_util}%, ERR=${error_rate}%" | tee -a "$BOTTLENECK_LOG"
    
    # Create performance metrics JSON
    local metrics_json=$(create_performance_metrics_json "$cpu_usage" "$memory_usage" "$ebs_util" "$ebs_latency" "$ebs_aws_iops" "$ebs_throughput" "$network_util" "$error_rate")
    
    # Detect various bottlenecks
    local bottleneck_detected=false
    local bottleneck_types=()
    local bottleneck_values=()
    local rpc_bottleneck=false
    
    if check_cpu_bottleneck "$cpu_usage"; then
        bottleneck_detected=true
        bottleneck_types+=("CPU")
        bottleneck_values+=("${cpu_usage}%")
    fi
    
    if check_memory_bottleneck "$memory_usage"; then
        bottleneck_detected=true
        bottleneck_types+=("Memory")
        bottleneck_values+=("${memory_usage}%")
    fi
    
    # Detect DATA device EBS bottleneck
    if check_ebs_bottleneck "$ebs_aws_iops" "$ebs_throughput" "data"; then
        bottleneck_detected=true
        if [[ ${BOTTLENECK_COUNTERS["ebs_aws_iops"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            bottleneck_types+=("EBS_AWS_IOPS")
            bottleneck_values+=("${ebs_aws_iops}/${DATA_VOL_MAX_IOPS}")
        fi
        if [[ ${BOTTLENECK_COUNTERS["ebs_aws_throughput"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
            bottleneck_types+=("EBS_AWS_Throughput")
            bottleneck_values+=("${ebs_throughput}/${DATA_VOL_MAX_THROUGHPUT}MiB/s")
        fi
    fi
    
    # Detect ACCOUNTS device EBS bottleneck (if configured)
    if is_accounts_configured; then
        # Get ACCOUNTS device performance metrics
        local accounts_util=0
        local accounts_latency=0
        local accounts_aws_iops=0
        local accounts_throughput=0
        
        # Extract ACCOUNTS device metrics from CSV data
        for i in "${!field_names[@]}"; do
            local field_name="${field_names[i]}"
            
            # Match ACCOUNTS device fields
            if [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_util ]]; then
                accounts_util=${data_values[i]:-0}
            fi
            
            if [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_r_await ]]; then
                accounts_latency=${data_values[i]:-0}
            elif [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_avg_await ]] && [[ "$accounts_latency" == "0" ]]; then
                accounts_latency=${data_values[i]:-0}
            fi
            
            if [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_aws_standard_iops ]]; then
                accounts_aws_iops=${data_values[i]:-0}
            fi
            
            if [[ "$field_name" == accounts_${ACCOUNTS_DEVICE}_aws_standard_throughput_mibs ]]; then
                accounts_throughput=${data_values[i]:-0}
            fi
        done
        
        log_debug "ACCOUNTS device metrics: AWS_IOPS=${accounts_aws_iops}, Throughput=${accounts_throughput}MiB/s"
        
        if check_ebs_bottleneck "$accounts_aws_iops" "$accounts_throughput" "accounts"; then
            bottleneck_detected=true
            if [[ ${BOTTLENECK_COUNTERS["accounts_ebs_aws_iops"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
                bottleneck_types+=("ACCOUNTS_EBS_AWS_IOPS")
                bottleneck_values+=("${accounts_aws_iops}/${ACCOUNTS_VOL_MAX_IOPS}")
            fi
            if [[ ${BOTTLENECK_COUNTERS["accounts_ebs_aws_throughput"]:-0} -ge $BOTTLENECK_CONSECUTIVE_COUNT ]]; then
                bottleneck_types+=("ACCOUNTS_EBS_AWS_Throughput")
                bottleneck_values+=("${accounts_throughput}/${ACCOUNTS_VOL_MAX_THROUGHPUT}MiB/s")
            fi
        fi
    fi
    
    if check_network_bottleneck "$network_util"; then
        bottleneck_detected=true
        bottleneck_types+=("Network")
        bottleneck_values+=("${network_util}%")
    fi
    
    # Detect ENA network limit bottleneck
    if check_ena_network_bottleneck "$performance_csv"; then
        bottleneck_detected=true
        bottleneck_types+=("ENA_Network_Limit")
        bottleneck_values+=("AWS network limit")
    fi
    
    if check_qps_bottleneck "$current_qps" "$error_rate"; then
        bottleneck_detected=true
        bottleneck_types+=("QPS")
        bottleneck_values+=("${error_rate}% error rate")
    fi
    
    # Detect RPC connection failure
    if check_rpc_connection_bottleneck; then
        bottleneck_detected=true
        bottleneck_types+=("RPC_Connection")
        bottleneck_values+=("Connection failed")
    fi
    
    # Detect RPC performance bottleneck
    if [[ -n "$vegeta_result" ]] && check_rpc_performance_bottleneck "$vegeta_result"; then
        bottleneck_detected=true
        rpc_bottleneck=true
        
        local total_requests=$(jq -r '.requests // 1' "$vegeta_result" 2>/dev/null || echo "1")
        local success_requests=$(jq -r '.status_codes."200" // 0' "$vegeta_result" 2>/dev/null || echo "0")
        local success_rate=$(awk "BEGIN {printf \"%.0f\", $success_requests * 100 / $total_requests}" 2>/dev/null || echo "0")
        local avg_latency_ns=$(jq -r '.latencies.mean // 0' "$vegeta_result" 2>/dev/null || echo "0")
        local avg_latency=$(awk "BEGIN {printf \"%.2f\", $avg_latency_ns / 1000000}" 2>/dev/null || echo "0")
        
        if (( $(awk "BEGIN {print ($success_rate < $SUCCESS_RATE_THRESHOLD) ? 1 : 0}") )); then
            bottleneck_types+=("RPC_Success_Rate")
            bottleneck_values+=("${success_rate}%")
        fi
        if (( $(awk "BEGIN {print ($avg_latency > $MAX_LATENCY_THRESHOLD) ? 1 : 0}") )); then
            bottleneck_types+=("RPC_Latency")
            bottleneck_values+=("${avg_latency}ms")
        fi
    fi
    
    # ========== P0: Node Health Check Integration ==========
    # Get node persistent unhealthy flag (written by block_height_monitor.sh)
    local node_unhealthy_flag="${MEMORY_SHARE_DIR}/block_height_time_exceeded.flag"
    local is_node_critically_unhealthy=false
    
    # Check if node is persistently unhealthy (persistent > BLOCK_HEIGHT_TIME_THRESHOLD seconds)
    if [[ -f "$node_unhealthy_flag" ]]; then
        local flag_value=$(cat "$node_unhealthy_flag" 2>/dev/null || echo "0")
        if [[ "$flag_value" == "1" ]]; then
            is_node_critically_unhealthy=true
            echo "🚨 Node persistently unhealthy exceeding ${BLOCK_HEIGHT_TIME_THRESHOLD}s" | tee -a "$BOTTLENECK_LOG"
        fi
    fi
    
    # Scenario A: Bottleneck + Node Healthy → Need to distinguish resource bottleneck and RPC performance bottleneck
    if [[ "$bottleneck_detected" == "true" && "$is_node_critically_unhealthy" == "false" ]]; then
        if [[ "$rpc_bottleneck" == "true" ]]; then
            # Scenario A-RPC: RPC performance bottleneck + Node healthy → True bottleneck (necessary condition)
            local bottleneck_list=$(IFS=,; echo "${bottleneck_types[*]}")
            local value_list=$(IFS=,; echo "${bottleneck_values[*]}")
            echo "🚨 RPC performance bottleneck (necessary condition), confirmed as true bottleneck" | tee -a "$BOTTLENECK_LOG"
            echo "   Bottleneck types: $bottleneck_list (QPS: $current_qps)" | tee -a "$BOTTLENECK_LOG"
            echo "   Bottleneck values: $value_list" | tee -a "$BOTTLENECK_LOG"
            generate_bottleneck_status_json "bottleneck_detected" "true" "$bottleneck_list" "$value_list" "$current_qps" "$metrics_json"
            save_bottleneck_counters
            return 0
        else
            # Scenario A-Resource: Resource bottleneck + Node healthy → Possible false positive, reset resource counters (preserve RPC counters)
            echo "✅ Resource bottleneck but node healthy, judged as false positive, reset resource counters (preserve RPC counters)" | tee -a "$BOTTLENECK_LOG"
            reset_resource_bottleneck_counters
            generate_bottleneck_status_json "monitoring" "false" "" "" "$current_qps" "$metrics_json"
            save_bottleneck_counters
            return 1
        fi
    fi
    
    # Scenario B: Resource bottleneck + Node persistently unhealthy → True system-level bottleneck
    if [[ "$bottleneck_detected" == "true" && "$is_node_critically_unhealthy" == "true" ]]; then
        local bottleneck_list=$(IFS=,; echo "${bottleneck_types[*]}")
        local value_list=$(IFS=,; echo "${bottleneck_values[*]}")
        echo "🚨 Confirmed system-level bottleneck: Resource bottleneck + Node unhealthy" | tee -a "$BOTTLENECK_LOG"
        echo "   Bottleneck types: $bottleneck_list (QPS: $current_qps)" | tee -a "$BOTTLENECK_LOG"
        echo "   Bottleneck values: $value_list" | tee -a "$BOTTLENECK_LOG"
        generate_bottleneck_status_json "bottleneck_detected" "true" "$bottleneck_list" "$value_list" "$current_qps" "$metrics_json"
        save_bottleneck_counters
        return 0
    fi
    
    # Scenario C: Node persistently unhealthy (no resource bottleneck) → Node failure
    if [[ "$is_node_critically_unhealthy" == "true" ]]; then
        echo "🚨 Detected node persistently unhealthy (persistent > ${BLOCK_HEIGHT_TIME_THRESHOLD}s)" | tee -a "$BOTTLENECK_LOG"
        echo "   Even if resource metrics are normal, node is unavailable" | tee -a "$BOTTLENECK_LOG"
        
        # Add node unhealthy to bottleneck types
        bottleneck_types+=("Node_Unhealthy")
        bottleneck_values+=("Persistent>${BLOCK_HEIGHT_TIME_THRESHOLD}s")
        
        local bottleneck_list=$(IFS=,; echo "${bottleneck_types[*]}")
        local value_list=$(IFS=,; echo "${bottleneck_values[*]}")
        
        generate_bottleneck_status_json "bottleneck_detected" "true" "$bottleneck_list" "$value_list" "$current_qps" "$metrics_json"
        save_bottleneck_counters
        return 0
    fi
    
    # Scenario D: No bottleneck + Node healthy → Normal operation
    generate_bottleneck_status_json "monitoring" "false" "" "" "$current_qps" "$metrics_json"
    save_bottleneck_counters
    return 1
}

# Check if bottleneck detected
is_bottleneck_detected() {
    if [[ -f "$BOTTLENECK_STATUS_FILE" ]]; then
        local status=$(jq -r '.bottleneck_detected' "$BOTTLENECK_STATUS_FILE" 2>/dev/null)
        [[ "$status" == "true" ]]
    else
        return 1
    fi
}

# Get bottleneck information
get_bottleneck_info() {
    if [[ -f "$BOTTLENECK_STATUS_FILE" ]]; then
        cat "$BOTTLENECK_STATUS_FILE" | jq .
    else
        echo '{"status": "not_initialized"}'
    fi
}

# Main function
main() {
    case "${1:-help}" in
        init)
            init_bottleneck_detection
            ;;
        detect)
            local current_qps="$2"
            local performance_csv="$3"
            local vegeta_result="${4:-}"
            
            # Load counters from shared memory file (persist across subprocesses)
            if ! load_bottleneck_counters; then
                # File does not exist, initialize counters
                initialize_bottleneck_counters
            fi
            
            detect_bottleneck "$current_qps" "$performance_csv" "$vegeta_result"
            ;;
        status)
            get_bottleneck_info
            ;;
        is-detected)
            if is_bottleneck_detected; then
                echo "true"
                exit 0
            else
                echo "false"
                exit 1
            fi
            ;;
        help|--help|-h)
            echo "Usage: $0 <command> [options]"
            echo ""
            echo "Commands:"
            echo "  init                     Initialize bottleneck detector"
            echo "  detect <qps> <csv>       Detect bottleneck at current QPS"
            echo "  status                   Display bottleneck detection status"
            echo "  is-detected              Check if bottleneck detected"
            echo "  help                     Display help"
            echo ""
            echo "Bottleneck detection types:"
            echo "  CPU usage > ${BOTTLENECK_CPU_THRESHOLD}%"
            echo "  Memory usage > ${BOTTLENECK_MEMORY_THRESHOLD}%"
            echo "  EBS utilization > ${BOTTLENECK_EBS_UTIL_THRESHOLD}%"
            echo "  EBS latency > ${BOTTLENECK_EBS_LATENCY_THRESHOLD}ms"
            echo "  Network utilization > ${BOTTLENECK_NETWORK_THRESHOLD}%"
            echo "  Error rate > ${BOTTLENECK_ERROR_RATE_THRESHOLD}%"
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
