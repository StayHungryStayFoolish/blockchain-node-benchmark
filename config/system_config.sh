#!/bin/bash
# =====================================================================
# Blockchain Node Benchmark Framework - System Configuration Layer
# =====================================================================
# Target users: System administrators and advanced users
# Configuration content: AWS parameters, log configuration, advanced bottleneck detection thresholds
# Modification frequency: Occasionally modified
# =====================================================================

# ----- Deployment Platform Detection Configuration -----
# Deployment platform type (auto: auto-detect, aws: AWS environment, other: other environments)
DEPLOYMENT_PLATFORM=${DEPLOYMENT_PLATFORM:-"auto"}

# ENA network limitation monitoring configuration - Based on AWS ENA documentation (will be automatically adjusted according to deployment platform)
ENA_ALLOWANCE_FIELDS=(
    "bw_in_allowance_exceeded"
    "bw_out_allowance_exceeded"
    "pps_allowance_exceeded"
    "conntrack_allowance_exceeded"
    "linklocal_allowance_exceeded"
    "conntrack_allowance_available"
)

# ----- Unified Log Management Configuration -----
# Log level configuration (0=DEBUG, 1=INFO, 2=WARN, 3=ERROR, 4=FATAL)
LOG_LEVEL=${LOG_LEVEL:-1}  # Default INFO level

# Log format configuration
LOG_FORMAT=${LOG_FORMAT:-"[%timestamp%] [%level%] [%component%] %message%"}

# Log rotation configuration
MAX_LOG_SIZE=${MAX_LOG_SIZE:-"10M"}    # Maximum log file size
MAX_LOG_FILES=${MAX_LOG_FILES:-5}      # Number of log files to keep

# Log output configuration
LOG_JSON=${LOG_JSON:-false}            # JSON format output

# ----- Error Handling and Recovery Configuration -----
# Error recovery switch (true/false) - Disabled in benchmark framework to ensure test accuracy
ERROR_RECOVERY_ENABLED=${ERROR_RECOVERY_ENABLED:-false}

# Error handling threshold
ERROR_RECOVERY_DELAY=${ERROR_RECOVERY_DELAY:-10}          # Error recovery delay (seconds)

# ----- Error Handling and Log Configuration -----
# Error handling directory based on unified path structure (full path will be set in detect_deployment_paths)
ERROR_LOG_SUBDIR="error_logs"                                  # Error log subdirectory name
PYTHON_ERROR_LOG_SUBDIR="python_logs"                         # Python error log subdirectory name
TEMP_FILE_PREFIX="blockchain-node-qps"                                 # Temporary file prefix

# ----- AWS Related Configuration -----
# AWS EBS baseline configuration
AWS_EBS_BASELINE_IO_SIZE_KIB=16                               # AWS EBS baseline IO size (KiB)
AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB=128                      # AWS EBS baseline Throughput size (KiB)

# AWS metadata service endpoint configuration
AWS_METADATA_ENDPOINT="http://169.254.169.254"                # AWS instance metadata endpoint
AWS_METADATA_TOKEN_TTL=21600                                  # Metadata token TTL (6 hours)
AWS_METADATA_API_VERSION="latest"                             # API version

# ----- Monitoring Process Configuration -----
# Monitoring process name configuration (for monitoring overhead calculation)
MONITORING_PROCESS_NAMES=(
    "iostat"
    "mpstat"
    "sar"
    "vmstat"
    "netstat"
    "unified_monitor"
    "bottleneck_detector"
    "ena_network_monitor"
    "block_height_monitor"
    "performance_visualizer"
    "report_generator"
)

# Time format standard
TIMESTAMP_FORMAT="%Y-%m-%d %H:%M:%S"

get_unified_timestamp() {
    date +"$TIMESTAMP_FORMAT"
}

get_unified_epoch() {
    date +%s
}

# Silent mode configuration
SILENT_MODE=${SILENT_MODE:-false}

# Monitoring overhead CSV header definition - 20 fields (matches actual output from unified_monitor.sh)
OVERHEAD_CSV_HEADER="timestamp,monitoring_cpu,monitoring_memory_percent,monitoring_memory_mb,monitoring_process_count,blockchain_cpu,blockchain_memory_percent,blockchain_memory_mb,blockchain_process_count,system_cpu_cores,system_memory_gb,system_disk_gb,system_cpu_usage,system_memory_usage,system_disk_usage,system_cached_gb,system_buffers_gb,system_anon_pages_gb,system_mapped_gb,system_shmem_gb"

# Add configuration validation function
validate_overhead_csv_header() {
    if [[ -z "$OVERHEAD_CSV_HEADER" ]]; then
        echo "Error: OVERHEAD_CSV_HEADER variable is not defined" >&2
        return 1
    fi
    
    local field_count=$(echo "$OVERHEAD_CSV_HEADER" | tr ',' '\n' | wc -l)
    if [[ $field_count -ne 20 ]]; then
        echo "Warning: OVERHEAD_CSV_HEADER field count is incorrect, expected 20, actual ${field_count}" >&2
    fi
}

# Export system configuration variables
export -f get_unified_timestamp get_unified_epoch
export ENA_ALLOWANCE_FIELDS_STR="${ENA_ALLOWANCE_FIELDS[*]}"
export MONITORING_PROCESS_NAMES_STR="${MONITORING_PROCESS_NAMES[*]}"
export ENA_ALLOWANCE_FIELDS MONITORING_PROCESS_NAMES DEPLOYMENT_PLATFORM
export LOG_LEVEL LOG_FORMAT MAX_LOG_SIZE MAX_LOG_FILES LOG_JSON
export ERROR_RECOVERY_ENABLED ERROR_RECOVERY_DELAY
export ERROR_LOG_SUBDIR PYTHON_ERROR_LOG_SUBDIR TEMP_FILE_PREFIX
export AWS_EBS_BASELINE_IO_SIZE_KIB AWS_EBS_BASELINE_THROUGHPUT_SIZE_KIB AWS_METADATA_ENDPOINT AWS_METADATA_TOKEN_TTL AWS_METADATA_API_VERSION
export TIMESTAMP_FORMAT SILENT_MODE OVERHEAD_CSV_HEADER