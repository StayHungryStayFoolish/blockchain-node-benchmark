#!/bin/bash

# =====================================================================
# Blockchain Node Performance Benchmark Framework Entry Point
# =====================================================================

# Deployment environment check
check_deployment() {
    local current_path="$(pwd)"
    local script_path="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    echo "🔍 Verifying deployment environment..." >&2
    echo "   Current location: $script_path" >&2
    
    # Basic permission check
    if [[ ! -r "$script_path" ]]; then
        echo "❌ Error: Cannot read framework directory" >&2
        echo "💡 Solution: Check directory permissions" >&2
        return 1
    fi
    
    echo "✅ Deployment environment verification passed" >&2
}

# Display framework information
show_framework_info() {
    echo "🚀 Blockchain Node Performance Benchmark Framework"
    echo ""
    echo "📊 Supported test modes:"
    echo "   • Quick verification test - Basic performance verification"
    echo "   • Standard performance test - Comprehensive performance evaluation"
    echo "   • Intensive stress test - Intelligent bottleneck detection"
    echo ""
    echo "🔍 Monitoring capabilities:"
    echo "   • 73 - 79 performance metrics real-time monitoring"
    echo "   • CPU, Memory, EBS storage, Network, ENA limitations"
    echo "   • Intelligent bottleneck detection and root cause analysis"
    echo "   • Bottleneck-log time correlation analysis"
    echo ""
    echo "📈 Analysis features:"
    echo "   • Machine learning anomaly detection"
    echo "   • Multi-dimensional performance correlation analysis"
    echo "   • HTML report and PNG chart generation"
    echo "   • Historical test comparison and trend analysis"
    echo ""
}

# Execute deployment check
if ! check_deployment; then
    exit 1
fi

# If no parameters, display framework information
if [[ $# -eq 0 ]]; then
    show_framework_info
    echo "💡 Use ./blockchain_node_benchmark.sh --help to view detailed usage instructions"
    echo ""
    exit 0
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load configuration and shared functions
source "${SCRIPT_DIR}/config/config_loader.sh"
source "${SCRIPT_DIR}/utils/error_handler.sh"
source "${SCRIPT_DIR}/core/common_functions.sh"

# Clean or create memory sharing directory
if [[ -d "$MEMORY_SHARE_DIR" ]]; then
    echo "🧹 Cleaning old cached data in memory sharing directory..." >&2
    # Clean all possible residual files
    rm -f "$MEMORY_SHARE_DIR"/*.json 2>/dev/null || true
    rm -f "$MEMORY_SHARE_DIR"/sample_count 2>/dev/null || true
    rm -f "$MEMORY_SHARE_DIR"/*cache* 2>/dev/null || true
    rm -f "$MEMORY_SHARE_DIR"/*.pid 2>/dev/null || true
    rm -f "$MEMORY_SHARE_DIR"/*.lock 2>/dev/null || true
else
    echo "📁 Creating memory sharing directory..." >&2
    mkdir -p "$MEMORY_SHARE_DIR" 2>/dev/null || true
    chmod 755 "$MEMORY_SHARE_DIR" 2>/dev/null || true
fi

echo "✅ Memory sharing directory prepared" >&2

# Set up error handling
setup_error_handling "$(basename "$0")" "Blockchain Node Benchmark Framework"
log_script_start "$(basename "$0")"

# Global variables
MONITORING_PIDS=()
TEST_SESSION_ID="session_${SESSION_TIMESTAMP}"
BOTTLENECK_DETECTED=false
BOTTLENECK_INFO=""

# Cleanup function
cleanup_framework() {
    echo "🧹 Executing framework cleanup..."
    
    # Stop monitoring system
    stop_monitoring_system
    
    # Clean up temporary files
    cleanup_temp_files
    
    echo "✅ Framework cleanup completed"
}

# Set cleanup trap
trap cleanup_framework EXIT INT TERM

# Prepare Benchmark data
prepare_benchmark_data() {
    echo "📊 Preparing Benchmark data..."
    
    # Check if account file exists
    if [[ ! -f "$ACCOUNTS_OUTPUT_FILE" ]]; then
        echo "🔍 Fetching active accounts..."
        if [[ -f "${SCRIPT_DIR}/tools/fetch_active_accounts.py" ]]; then
            python3 "${SCRIPT_DIR}/tools/fetch_active_accounts.py" \
                --output "$ACCOUNTS_OUTPUT_FILE" \
                --count "$ACCOUNT_COUNT" \
                --verbose

            if [[ $? -eq 0 && -f "$ACCOUNTS_OUTPUT_FILE" ]]; then
                echo "✅ Account fetching successful: $(wc -l < "$ACCOUNTS_OUTPUT_FILE") accounts"
            else
                echo "❌ Account fetching failed"
                return 1
            fi
        else
            echo "❌ Account fetching script does not exist: ${SCRIPT_DIR}/tools/fetch_active_accounts.py"
            echo "   Please check if file exists and path is correct"
            return 1
        fi
    else
        echo "✅ Account file already exists: $(wc -l < "$ACCOUNTS_OUTPUT_FILE") accounts"
    fi
    
    # Generate vegeta target files
    echo "🎯 Generating Vegeta target files (RPC mode: $RPC_MODE)..."
    if [[ -f "${SCRIPT_DIR}/tools/target_generator.sh" ]]; then
        "${SCRIPT_DIR}/tools/target_generator.sh" \
            --accounts-file "$ACCOUNTS_OUTPUT_FILE" \
            --rpc-url "$LOCAL_RPC_URL" \
            --rpc-mode "$RPC_MODE" \
            --output-single "$SINGLE_METHOD_TARGETS_FILE" \
            --output-mixed "$MIXED_METHOD_TARGETS_FILE"
        
        if [[ $? -eq 0 ]]; then
            echo "✅ Vegeta target file generation successful (RPC mode: $RPC_MODE)"
            if [[ "$RPC_MODE" == "mixed" ]]; then
                echo "   Mixed method target: $MIXED_METHOD_TARGETS_FILE"
            else
                echo "   Single method target: $SINGLE_METHOD_TARGETS_FILE"
            fi
        else
            echo "❌ Vegeta target file generation failed"
            return 1
        fi
    else
        echo "❌ Target generation script does not exist: tools/target_generator.sh"
        return 1
    fi
    
    return 0
}

# Start monitoring system
start_monitoring_system() {
    echo "📊 Starting monitoring system..."
    
    # Clean up block height continuous exceeded flag file from last test
    rm -f "${MEMORY_SHARE_DIR}/block_height_time_exceeded.flag" 2>/dev/null || true
    
    # Create framework running status file before starting monitoring
    echo "running" > "$TMP_DIR/qps_test_status.tmp"
    mv "$TMP_DIR/qps_test_status.tmp" "$TMP_DIR/qps_test_status"
    echo "[STATUS] Framework lifecycle marker created: $TMP_DIR/qps_test_status"
    
    # Export monitoring PID file path for subprocess use
    export MONITOR_PIDS_FILE="${TMP_DIR}/monitor_pids.txt"
    export MONITOR_STATUS_FILE="${TMP_DIR}/monitoring_status.json"
    
    # Start monitoring coordinator
    if [[ -f "${SCRIPT_DIR}/monitoring/monitoring_coordinator.sh" ]]; then
        echo "🚀 Starting monitoring coordinator..."
        "${SCRIPT_DIR}/monitoring/monitoring_coordinator.sh" start &
        local coordinator_pid=$!
        MONITORING_PIDS+=($coordinator_pid)
        echo "✅ Monitoring coordinator started (PID: $coordinator_pid)"
        
        # Wait for monitoring system initialization
        sleep 5
        
        # Verify monitoring system status
        if kill -0 $coordinator_pid 2>/dev/null; then
            echo "✅ Monitoring system running normally"
            return 0
        else
            echo "❌ Monitoring system startup failed"
            return 1
        fi
    else
        echo "❌ Monitoring coordinator does not exist: monitoring/monitoring_coordinator.sh"
        return 1
    fi
}

# Stop monitoring system
stop_monitoring_system() {
    echo "🛑 Stopping monitoring system..."
    
    # Check if there are monitoring processes to stop
    if [[ ${#MONITORING_PIDS[@]} -eq 0 ]]; then
        echo "ℹ️  No monitoring processes to stop"
        return 0
    fi
    
    # Stop monitoring coordinator
    if [[ -f "${SCRIPT_DIR}/monitoring/monitoring_coordinator.sh" ]]; then
        "${SCRIPT_DIR}/monitoring/monitoring_coordinator.sh" stop
    fi
    
    # Stop all monitoring processes
    for pid in "${MONITORING_PIDS[@]}"; do
        if kill -0 $pid 2>/dev/null; then
            echo "🛑 Stopping monitoring process PID: $pid"
            kill -TERM $pid 2>/dev/null
            sleep 2
            if kill -0 $pid 2>/dev/null; then
                kill -KILL $pid 2>/dev/null
            fi
        fi
    done
    
    MONITORING_PIDS=()
    echo "✅ Monitoring system stopped"
}

# Execute core QPS test
execute_core_qps_test() {
    echo "[START] Executing core QPS test (RPC mode: $RPC_MODE)..."
    
    # 🔧 Verify framework status file exists (created when monitoring started)
    if [[ ! -f "$TMP_DIR/qps_test_status" ]]; then
        echo "[ERROR] Framework status file not found. Monitoring system may not be running."
        return 1
    fi
    echo "[STATUS] Framework lifecycle marker verified: $TMP_DIR/qps_test_status"
    
    # Build parameter array, filter out RPC mode parameters as we will add them separately
    local executor_args=()
    
    # Add non-RPC mode parameters
    for arg in "$@"; do
        case $arg in
            --single|--mixed)
                # Skip RPC mode parameters, we will add based on RPC_MODE variable
                ;;
            *)
                executor_args+=("$arg")
                ;;
        esac
    done
    
    # Add correct RPC mode parameter based on RPC_MODE variable
    executor_args+=("--$RPC_MODE")
    
    # Call master_qps_executor.sh
    "${SCRIPT_DIR}/core/master_qps_executor.sh" "${executor_args[@]}"
    local test_result=$?
    
    # Wait for monitoring system to collect final data, ensure data integrity
    echo "[STATUS] QPS test completed, waiting for monitoring data collection..."
    sleep 3
    
    # Delete QPS test status marker file - safe deletion
    if [[ -f "$TMP_DIR/qps_test_status" ]]; then
        rm -f "$TMP_DIR/qps_test_status"
        echo "[STATUS] QPS test status marker deleted"
    else
        echo "[WARN] QPS test status marker file does not exist, may have been deleted"
    fi
    
    # Check if bottleneck detected - intelligently merge multiple bottleneck data sources
    local bottleneck_sources=(
        "${QPS_STATUS_FILE}"                              # Prioritize bottlenecks during QPS test
        "${MEMORY_SHARE_DIR}/bottleneck_status.json"      # Then bottlenecks during monitoring
    )
    
    local bottleneck_found=false
    local all_bottleneck_info=""
    
    for bottleneck_file in "${bottleneck_sources[@]}"; do
        if [[ -f "$bottleneck_file" ]]; then
            local status_data=$(cat "$bottleneck_file" 2>/dev/null)
            if [[ -n "$status_data" ]] && echo "$status_data" | grep -q "bottleneck_detected.*true"; then
                local source_info=$(echo "$status_data" | jq -r '.bottleneck_summary // "Unknown bottleneck"' 2>/dev/null || echo "Unknown bottleneck")
                local source_name=$(basename "$bottleneck_file")
                
                if [[ "$bottleneck_found" == "false" ]]; then
                    BOTTLENECK_DETECTED=true
                    BOTTLENECK_INFO="$source_info"
                    all_bottleneck_info="$source_name: $source_info"
                    bottleneck_found=true
                else
                    all_bottleneck_info="$all_bottleneck_info; $source_name: $source_info"
                fi
                
                echo "🚨 Performance bottleneck detected: $source_info (source: $source_name)"
            fi
        fi
    done
    
    # If multiple bottleneck sources found, record complete information
    if [[ "$bottleneck_found" == "true" ]]; then
        echo "[INFO] Complete bottleneck information: $all_bottleneck_info"
    fi
    
    return $test_result
}

# Process test results
process_test_results() {
    echo "🔄 Processing test results..."
    
    # AWS baseline conversion
    echo "📊 Executing AWS baseline conversion..."
    if [[ -f "${SCRIPT_DIR}/utils/ebs_converter.sh" ]]; then
        # Note: ebs_converter.sh is a function library, does not support direct parameter execution
        # Actual EBS conversion is implemented through source call in iostat_collector.sh
        echo "✅ EBS conversion library loaded, conversion executed automatically during data collection"
    else
        echo "⚠️ EBS conversion script does not exist, skipping conversion"
    fi
    
    # Unit conversion
    if [[ -f "${SCRIPT_DIR}/utils/unit_converter.py" ]]; then
        python3 "${SCRIPT_DIR}/utils/unit_converter.py" --auto-process
        echo "✅ Unit conversion completed"
    else
        echo "⚠️ Unit conversion script does not exist, skipping conversion"
    fi
    
    return 0
}

# Execute data analysis
execute_data_analysis() {
    echo "🔍 Executing data analysis..."
    
    # Parse benchmark_mode parameter
    local benchmark_mode=""
    for arg in "$@"; do
        case $arg in
            --quick) benchmark_mode="quick" ;;
            --standard) benchmark_mode="standard" ;;
            --intensive) benchmark_mode="intensive" ;;
        esac
    done
    
    if [[ -z "$benchmark_mode" ]]; then
        benchmark_mode="quick"
    fi
    
    # Use symlink to get latest performance data file
    local latest_csv="${LOGS_DIR}/performance_latest.csv"
    
    if [[ ! -f "$latest_csv" ]]; then
        echo "[ERROR] Performance data file not found: $latest_csv"
        echo "[DEBUG] Available CSV files:"
        ls -la "$LOGS_DIR"/*.csv 2>/dev/null || echo "  No CSV files found"
        echo "[DEBUG] LOGS_DIR = $LOGS_DIR"
        return 1
    fi
    
    # Verify file integrity and symlink target
    if [[ -L "$latest_csv" ]]; then
        local target_file=$(readlink "$latest_csv")
        local full_target="${LOGS_DIR}/$target_file"
        if [[ ! -f "$full_target" ]]; then
            echo "[ERROR] Symlink target does not exist: $full_target"
            return 1
        fi
        echo "[INFO] Using symlinked file: $target_file"
    fi
    
    local line_count=$(wc -l < "$latest_csv")
    if [[ $line_count -lt 2 ]]; then
        echo "[ERROR] Performance data file is empty or only contains header: $line_count lines"
        return 1
    fi
    
    # Verify CSV header integrity and required fields
    local header=$(head -1 "$latest_csv")
    local field_count=$(echo "$header" | tr ',' '\n' | wc -l)
    if [[ $field_count -lt 10 ]]; then
        echo "[ERROR] CSV header appears incomplete: only $field_count fields"
        return 1
    fi
    
    # Verify critical fields exist
    local required_fields=("timestamp" "cpu_usage" "mem_usage")
    local missing_fields=()
    
    for field in "${required_fields[@]}"; do
        if ! echo "$header" | grep -q "$field"; then
            missing_fields+=("$field")
        fi
    done
    
    if [[ ${#missing_fields[@]} -gt 0 ]]; then
        echo "[ERROR] Required fields missing from CSV: ${missing_fields[*]}"
        echo "[DEBUG] Available fields: $header"
        return 1
    fi
    
    # Check existence of device-related fields (for analysis script compatibility)
    local has_data_device=false
    local has_accounts_device=false
    local has_ena_fields=false
    
    if echo "$header" | grep -q "data_.*_util"; then
        has_data_device=true
        echo "[INFO] DATA device fields detected"
    fi
    
    if echo "$header" | grep -q "accounts_.*_util"; then
        has_accounts_device=true
        echo "[INFO] ACCOUNTS device fields detected"
    fi
    
    if echo "$header" | grep -q "ena_"; then
        has_ena_fields=true
        echo "[INFO] ENA fields detected (AWS environment)"
    fi
    
    # Warning: If no device fields, some analysis may be limited
    if [[ "$has_data_device" == "false" && "$has_accounts_device" == "false" ]]; then
        echo "[WARN] No EBS device fields detected - storage analysis may be limited"
    fi
    
    echo "[INFO] Using monitoring data file: $(basename "$latest_csv")"
    echo "[INFO] File size: $line_count lines, $field_count fields"
    echo "[INFO] Required fields verified: ${required_fields[*]}"
    
    # If bottleneck detected, execute bottleneck-specific analysis
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        echo "🚨 Executing bottleneck-specific analysis..."
        
        # Read bottleneck detailed information
        local bottleneck_details=""
        if [[ -f "$QPS_STATUS_FILE" ]]; then
            bottleneck_details=$(cat "$QPS_STATUS_FILE")
            local bottleneck_qps=$(echo "$bottleneck_details" | jq -r '.bottleneck_qps // 0')
            local max_qps=$(echo "$bottleneck_details" | jq -r '.max_successful_qps // 0')
            local severity=$(echo "$bottleneck_details" | jq -r '.severity // "medium"')
            
            echo "📊 Bottleneck details: QPS=$bottleneck_qps, Max successful QPS=$max_qps, Severity=$severity"
        fi
        
        # EBS bottleneck-specific analysis completed through real-time monitoring
        # ebs_bottleneck_detector.sh runs in real-time through monitoring_coordinator.sh during testing
        # Bottleneck detection results recorded in ebs_analyzer.log, no need to call again
        echo "💾 EBS bottleneck detection completed through real-time monitoring"
        
        # Bottleneck time window analysis
        execute_bottleneck_window_analysis "$latest_csv" "$bottleneck_details"
        
        # Performance cliff analysis
        execute_performance_cliff_analysis "$latest_csv" "$bottleneck_details"
    fi
    
    # Execute EBS performance analysis (generate ebs_analyzer.log)
    if [[ -f "${SCRIPT_DIR}/tools/ebs_analyzer.sh" ]]; then
        echo "🔍 Executing EBS performance analysis: ebs_analyzer.sh"
        if ! bash "${SCRIPT_DIR}/tools/ebs_analyzer.sh" "$latest_csv"; then
            echo "⚠️ EBS analysis execution failed, HTML report may be missing EBS analysis section"
        fi
    else
        echo "⚠️ EBS analysis script does not exist: tools/ebs_analyzer.sh"
    fi
    
    # Execute all standard analysis scripts
    local analysis_scripts=(
        "analysis/comprehensive_analysis.py"
        "analysis/cpu_ebs_correlation_analyzer.py"
        "analysis/qps_analyzer.py"
        "analysis/rpc_deep_analyzer.py"
    )
    
    for script in "${analysis_scripts[@]}"; do
        if [[ -f "${SCRIPT_DIR}/$script" ]]; then
            local script_name=$(basename "$script")
            
            # If bottleneck detected, some scripts already handled by specific analysis, skip to avoid duplication
            if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
                case "$script_name" in
                    "comprehensive_analysis.py")
                        echo "⏭️  Skipping $script_name (already handled by bottleneck time window analysis)"
                        continue
                        ;;
                    "qps_analyzer.py")
                        echo "⏭️  Skipping $script_name (already handled by performance cliff analysis)"
                        continue
                        ;;
                esac
            fi
            
            echo "🔍 Executing analysis: $script_name"
            
            # If bottleneck detected, pass bottleneck mode parameter
            if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
                if ! python3 "${SCRIPT_DIR}/$script" "$latest_csv" --benchmark-mode "$benchmark_mode" --bottleneck-mode --output-dir "$BASE_DATA_DIR"; then
                    echo "⚠️ Analysis script execution failed: $script_name"
                fi
            else
                # Execute basic analysis even without bottleneck, ensure chart generation
                if ! python3 "${SCRIPT_DIR}/$script" "$latest_csv" --benchmark-mode "$benchmark_mode" --output-dir "$BASE_DATA_DIR"; then
                    echo "⚠️ Analysis script execution failed: $script_name"
                fi
            fi
        else
            echo "⚠️ Analysis script does not exist: $script"
        fi
    done
    
    echo "✅ Data analysis completed"
    return 0
}

# Execute bottleneck time window analysis
execute_bottleneck_window_analysis() {
    local csv_file="$1"
    local bottleneck_info="$2"
    
    echo "🕐 Executing bottleneck time window analysis..."
    
    if [[ -z "$bottleneck_info" ]]; then
        echo "⚠️ No bottleneck information, skipping time window analysis"
        return
    fi
    
    # Extract bottleneck time information
    local bottleneck_time=$(echo "$bottleneck_info" | jq -r '.detection_time // ""')
    local window_start=$(echo "$bottleneck_info" | jq -r '.analysis_window.start_time // ""')
    local window_end=$(echo "$bottleneck_info" | jq -r '.analysis_window.end_time // ""')
    
    if [[ -n "$bottleneck_time" ]]; then
        echo "📊 Bottleneck time window: $window_start to $window_end"
        
        # Call time window analysis tool
        if [[ -f "${SCRIPT_DIR}/analysis/comprehensive_analysis.py" ]]; then
            python3 "${SCRIPT_DIR}/analysis/comprehensive_analysis.py" \
                "$csv_file" \
                --benchmark-mode "$benchmark_mode" \
                --output-dir "$BASE_DATA_DIR" \
                --time-window \
                --start-time "$window_start" \
                --end-time "$window_end" \
                --bottleneck-time "$bottleneck_time"
        fi
    fi
}

# Execute performance cliff analysis
execute_performance_cliff_analysis() {
    local csv_file="$1"
    local bottleneck_info="$2"
    
    echo "📉 Executing performance cliff analysis..."
    
    # Call performance cliff analysis tool - execute basic analysis even without bottleneck information
    if [[ -f "${SCRIPT_DIR}/analysis/qps_analyzer.py" ]]; then
        if [[ -n "$bottleneck_info" ]]; then
            # Complete analysis when bottleneck information available
            local max_qps=$(echo "$bottleneck_info" | jq -r '.max_successful_qps // 0')
            local bottleneck_qps=$(echo "$bottleneck_info" | jq -r '.bottleneck_qps // 0')
            
            if [[ $max_qps -gt 0 && $bottleneck_qps -gt 0 ]]; then
                local performance_drop=$(awk "BEGIN {printf \"%.2f\", ($bottleneck_qps - $max_qps) * 100 / $max_qps}")
                echo "📊 Performance cliff: from ${max_qps} QPS to ${bottleneck_qps} QPS (${performance_drop}%)"
                
                python3 "${SCRIPT_DIR}/analysis/qps_analyzer.py" \
                    "$csv_file" \
                    --benchmark-mode "$benchmark_mode" \
                    --cliff-analysis \
                    --max-qps "$max_qps" \
                    --bottleneck-qps "$bottleneck_qps" \
                    --output-dir "$BASE_DATA_DIR"
            else
                echo "📊 Executing basic performance analysis (incomplete bottleneck data)"
                python3 "${SCRIPT_DIR}/analysis/qps_analyzer.py" \
                    "$csv_file" \
                    --benchmark-mode "$benchmark_mode" \
                    --output-dir "$BASE_DATA_DIR"
            fi
        else
            echo "📊 Executing basic performance analysis (no bottleneck information)"
            python3 "${SCRIPT_DIR}/analysis/qps_analyzer.py" \
                "$csv_file" \
                --benchmark-mode "$benchmark_mode" \
                --output-dir "$BASE_DATA_DIR"
        fi
    fi
}

# Archive test results
archive_test_results() {
    echo "📦 Archiving test results..."
    
    # Determine benchmark mode - parse from passed parameters
    local benchmark_mode=""
    for arg in "$@"; do
        case $arg in
            --quick) benchmark_mode="quick" ;;
            --standard) benchmark_mode="standard" ;;
            --intensive) benchmark_mode="intensive" ;;
        esac
    done
    
    # If no mode parameter found, use default value
    if [[ -z "$benchmark_mode" ]]; then
        benchmark_mode="quick"  # Default mode, consistent with master_qps_executor.sh
        echo "⚠️ Benchmark mode parameter not detected, using default mode: $benchmark_mode"
    fi
    
    echo "🔍 Detected benchmark mode: $benchmark_mode"
    
    # Read maximum QPS from QPS status file
    local max_qps=0
    if [[ -f "$QPS_STATUS_FILE" ]]; then
        max_qps=$(jq -r '.max_successful_qps // 0' "$QPS_STATUS_FILE" 2>/dev/null)
    fi
    
    # Call professional archiving tool
    if [[ -f "${SCRIPT_DIR}/tools/benchmark_archiver.sh" ]]; then
        "${SCRIPT_DIR}/tools/benchmark_archiver.sh" --archive \
            --benchmark-mode "$benchmark_mode" \
            --max-qps "$max_qps"
        
        if [[ $? -eq 0 ]]; then
            echo "✅ Test results archiving completed"
        else
            echo "⚠️ Test results archiving failed"
        fi
    else
        echo "⚠️ Archiving script does not exist, skipping archiving"
    fi
}

# Generate final reports
generate_final_reports() {
    echo "📊 Generating final reports..."
    
    # Use symlink to get latest performance data file
    local latest_csv="${LOGS_DIR}/performance_latest.csv"
    
    if [[ ! -f "$latest_csv" ]]; then
        echo "⚠️ Warning: Performance data file not found: $latest_csv"
        return 1
    fi
    
    # Prepare report generation parameters
    local report_params=("$latest_csv")
    
    # If bottleneck detected, add bottleneck mode parameter
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        report_params+=("--bottleneck-mode")
        
        # Add bottleneck information file
        if [[ -f "$QPS_STATUS_FILE" ]]; then
            report_params+=("--bottleneck-info" "$QPS_STATUS_FILE")
        fi
        
        echo "🚨 Bottleneck mode report generation"
    fi
    
    # Generate HTML report (bilingual: English and Chinese)
    if [[ -f "${SCRIPT_DIR}/visualization/report_generator.py" ]]; then
        echo "📄 Generating HTML report (bilingual)..."
        
        # Generate English report
        echo "  📝 Generating English report..."
        if ! python3 "${SCRIPT_DIR}/visualization/report_generator.py" "${report_params[@]}" --language en; then
            echo "  ❌ English report generation failed"
            return 1
        fi
        echo "  ✅ English report generated"
        
        # Generate Chinese report
        echo "  📝 Generating Chinese report..."
        if ! python3 "${SCRIPT_DIR}/visualization/report_generator.py" "${report_params[@]}" --language zh; then
            echo "  ❌ Chinese report generation failed"
            return 1
        fi
        echo "  ✅ Chinese report generated"
        
        echo "✅ Bilingual HTML report generated"
    else
        echo "⚠️ HTML report generator does not exist"
    fi

    # Generate advanced charts
    if [[ -f "${SCRIPT_DIR}/visualization/advanced_chart_generator.py" ]]; then
        echo "📊 Generating advanced charts..."
        if ! python3 "${SCRIPT_DIR}/visualization/advanced_chart_generator.py" "${report_params[@]}"; then
            echo "⚠️ Advanced chart generation failed"
        else
            echo "✅ Advanced charts generated"
        fi
    else
        echo "⚠️ Advanced chart generator does not exist"
    fi
    
    # Generate bottleneck-specific report
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        generate_bottleneck_summary_report
    fi
    
    # Display report location and summary
    display_final_report_summary
    
    # Archive test results - execute after all analysis and report generation completed
    archive_test_results "$@"
    
    return 0
}

# Generate bottleneck summary report
generate_bottleneck_summary_report() {
    echo "🚨 Generating bottleneck summary report..."
    
    local bottleneck_summary_file="${REPORTS_DIR}/bottleneck_summary_${SESSION_TIMESTAMP}.md"
    
    # Read bottleneck information
    local bottleneck_info=""
    if [[ -f "$QPS_STATUS_FILE" ]]; then
        bottleneck_info=$(cat "$QPS_STATUS_FILE")
    fi
    
    # Generate Markdown format bottleneck summary
    cat > "$bottleneck_summary_file" << EOF
# 🚨 Performance Bottleneck Detection Report

## 📊 Test Summary

- **Test time**: $(date)
- **Test session**: $TEST_SESSION_ID
- **Bottleneck status**: ✅ Performance bottleneck detected

## 🎯 Bottleneck Details

EOF
    
    if [[ -n "$bottleneck_info" ]]; then
        local max_qps=$(echo "$bottleneck_info" | jq -r '.max_successful_qps // 0')
        local bottleneck_qps=$(echo "$bottleneck_info" | jq -r '.bottleneck_qps // 0')
        local severity=$(echo "$bottleneck_info" | jq -r '.severity // "unknown"')
        local reasons=$(echo "$bottleneck_info" | jq -r '.bottleneck_reasons // "Unknown"')
        local detection_time=$(echo "$bottleneck_info" | jq -r '.detection_time // "Unknown"')
        
        cat >> "$bottleneck_summary_file" << EOF
- **Maximum successful QPS**: $max_qps
- **Bottleneck trigger QPS**: $bottleneck_qps
- **Severity**: $severity
- **Detection time**: $detection_time
- **Bottleneck reasons**: $reasons

## 🔍 System Recommendations

EOF
        
        # Add recommendations
        local recommendations=$(echo "$bottleneck_info" | jq -r '.recommendations[]?' 2>/dev/null)
        if [[ -n "$recommendations" ]]; then
            echo "$recommendations" | while read -r recommendation; do
                echo "- $recommendation" >> "$bottleneck_summary_file"
            done
        else
            echo "- Please refer to detailed analysis report for optimization recommendations" >> "$bottleneck_summary_file"
        fi
    fi
    
    cat >> "$bottleneck_summary_file" << EOF

## 📋 Related Files

- **Detailed bottleneck analysis**: $QPS_STATUS_FILE
- **Bottleneck event log**: ${LOGS_DIR}/bottleneck_events.jsonl
- **Performance data**: ${LOGS_DIR}/performance_latest.csv

## 🎯 Next Steps

1. View HTML report for detailed performance analysis
2. Check bottleneck analysis file to understand root cause
3. Optimize system configuration based on recommendations
4. Re-run test to verify improvement effects

---
*Report generation time: $(date)*
EOF
    
    echo "📄 Bottleneck summary report: $(basename "$bottleneck_summary_file")"
}

# Display final report summary
display_final_report_summary() {
    echo ""
    echo "🎉 Test completed! Report summary:"
    echo "================================"
    echo "📁 Report directory: $REPORTS_DIR"
    
    # HTML report
    local html_report=$(find "$REPORTS_DIR" -name "*.html" -type f | head -1)
    if [[ -n "$html_report" ]]; then
        echo "📄 HTML report: $(basename "$html_report")"
    fi
    
    # Chart files
    local chart_count=$(find "$REPORTS_DIR" -name "*.png" -type f | wc -l)
    echo "📊 Chart files: $chart_count PNG files"
    
    # Bottleneck-related reports
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        echo ""
        echo "🚨 Bottleneck detection results:"
        
        if [[ -f "$QPS_STATUS_FILE" ]]; then
            local max_qps=$(jq -r '.max_successful_qps // 0' "$QPS_STATUS_FILE" 2>/dev/null)
            local bottleneck_qps=$(jq -r '.bottleneck_qps // 0' "$QPS_STATUS_FILE" 2>/dev/null)
            echo "🏆 Maximum successful QPS: $max_qps"
            echo "🚨 Bottleneck trigger QPS: $bottleneck_qps"
        fi
        
        local bottleneck_summary=$(find "$REPORTS_DIR" -name "bottleneck_summary_*.md" -type f | head -1)
        if [[ -n "$bottleneck_summary" ]]; then
            echo "📋 Bottleneck summary: $(basename "$bottleneck_summary")"
        fi
    fi
    
    echo ""
    echo "🎯 Recommended next steps:"
    echo "1. Open HTML report to view detailed analysis"
    echo "2. Check PNG charts to understand performance trends"
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        echo "3. View bottleneck summary report for optimization recommendations"
        echo "4. Re-test after optimizing system based on recommendations"
    else
        echo "3. Consider running intensive test mode to find performance limits"
    fi
}

# Clean up temporary files
cleanup_temp_files() {
    echo "🧹 Cleaning up temporary files..."
    
    # Clean up session temporary directory
    if [[ -d "$TEST_SESSION_DIR" ]]; then
        rm -rf "$TEST_SESSION_DIR"
    fi
    
    # Clean up temporary files in memory sharing directory
    if [[ -d "$MEMORY_SHARE_DIR" ]]; then
        rm -f "$MEMORY_SHARE_DIR"/*.json 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/sample_count 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/*cache* 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/*.pid 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/*.lock 2>/dev/null || true
        rm -f "$MEMORY_SHARE_DIR"/*.flag 2>/dev/null || true
    fi
    
    # Do not delete qps_status.json, keep for archiving
    # if [[ -f "$QPS_STATUS_FILE" ]]; then
    #     rm -f "$QPS_STATUS_FILE"
    # fi
}

# Parse RPC mode parameters
parse_rpc_mode_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --single)
                RPC_MODE="single"
                shift
                ;;
            --mixed)
                RPC_MODE="mixed"
                shift
                ;;
            *)
                # Other parameters continue to pass
                shift
                ;;
        esac
    done
}

# Main execution function
main() {
    # Save original parameters for subsequent passing
    local original_args=("$@")
    
    # Parse RPC mode parameters
    parse_rpc_mode_args "$@"
    
    echo "🚀 Starting Blockchain Node Performance Benchmark Framework"
    echo "   RPC mode: $RPC_MODE"
    echo "   Test session ID: $TEST_SESSION_ID"
    echo ""
    
    # Display framework information
    show_framework_info
    
    # Check deployment environment
    if ! check_deployment; then
        exit 1
    fi
    
    # Note: Directory initialization completed in config.sh, no need to repeat
    
    # Phase 1: Prepare Benchmark data
    echo "📋 Phase 1: Prepare Benchmark data"
    if ! prepare_benchmark_data; then
        echo "❌ Benchmark data preparation failed"
        exit 1
    fi
    
    # Phase 2: Start monitoring system
    echo "📋 Phase 2: Start monitoring system"
    if ! start_monitoring_system; then
        echo "❌ Monitoring system startup failed"
        exit 1
    fi
    
    # Phase 3: Execute core QPS test
    echo "📋 Phase 3: Execute core QPS test"
    if ! execute_core_qps_test "${original_args[@]}"; then
        echo "❌ QPS test execution failed"
        exit 1
    fi
    
    # Phase 4: Stop monitoring system
    echo "📋 Phase 4: Stop monitoring system"
    stop_monitoring_system
    
    # Phase 5: Process test results
    echo "📋 Phase 5: Process test results"
    process_test_results "${original_args[@]}"
    
    # Phase 6: Execute data analysis
    echo "📋 Phase 6: Execute data analysis"
    if ! execute_data_analysis "${original_args[@]}"; then
        echo "❌ Data analysis failed, test terminated"
        exit 1
    fi
    
    # Phase 7: Generate final reports
    echo "📋 Phase 7: Generate final reports"
    if ! generate_final_reports "${original_args[@]}"; then
        echo "❌ Report generation failed, test terminated"
        exit 1
    fi
    
    echo ""
    echo "🎉 Blockchain Node Performance Benchmark completed!"
    
    if [[ "$BOTTLENECK_DETECTED" == "true" ]]; then
        echo "🚨 Performance bottleneck detected: $BOTTLENECK_INFO"
        echo "📊 Bottleneck-specific analysis report generated"
    fi
    
    return 0
}

# Execute main function
main "$@"
