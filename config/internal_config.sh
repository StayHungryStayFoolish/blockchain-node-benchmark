#!/bin/bash
# =====================================================================
# Blockchain Node Benchmark Framework - Internal Configuration Layer
# =====================================================================
# Target users: Framework developers
# Configuration content: Internal implementation details, dynamic detection results, performance parameters
# Modification frequency: Rarely modified
# =====================================================================

# ----- Internal State Management -----

# ----- Bottleneck Detection Configuration -----
# Bottleneck detection thresholds (for extreme testing)
BOTTLENECK_CPU_THRESHOLD=85               # CPU usage exceeding 85% is considered a bottleneck
BOTTLENECK_MEMORY_THRESHOLD=90            # Memory usage exceeding 90% is considered a bottleneck
# EBS bottleneck detection thresholds (for bottleneck detection system)
BOTTLENECK_EBS_UTIL_THRESHOLD=90          # EBS utilization exceeding 90% is considered a bottleneck
BOTTLENECK_EBS_LATENCY_THRESHOLD=50       # EBS latency exceeding 50ms is considered a bottleneck
BOTTLENECK_NETWORK_THRESHOLD=80           # Network utilization exceeding 80% is considered a bottleneck
BOTTLENECK_ERROR_RATE_THRESHOLD=5         # Error rate exceeding 5% is considered a bottleneck
BOTTLENECK_EBS_IOPS_THRESHOLD=90          # EBS IOPS utilization exceeding 90% is considered a bottleneck
BOTTLENECK_EBS_THROUGHPUT_THRESHOLD=90    # EBS Throughput utilization exceeding 90% is considered a bottleneck

# Multi-level monitoring threshold explanation:
# - ebs_bottleneck_detector.sh (real-time bottleneck detection):
#   * HIGH level: Uses above baseline thresholds (90%, 50ms)
#   * CRITICAL level: Baseline threshold + 5% (95%) or Baseline threshold * 2 (100ms)
# - ebs_analyzer.sh (offline performance analysis):
#   * WARNING level: Utilization = BOTTLENECK_EBS_UTIL_THRESHOLD * 0.8 (72%)
#   * WARNING level: Latency = BOTTLENECK_EBS_LATENCY_THRESHOLD * 0.4 (20ms)
# 
# Note: EBS performance analyzer (ebs_analyzer.sh) uses calculation method to avoid variable bloat:
# Utilization warning level = BOTTLENECK_EBS_UTIL_THRESHOLD * 0.8 (90% * 0.8 = 72%)
# Latency warning level = BOTTLENECK_EBS_LATENCY_THRESHOLD * 0.4 (50ms * 0.4 = 20ms)


# Bottleneck detection consecutive count (avoid sporadic fluctuations)
BOTTLENECK_CONSECUTIVE_COUNT=3      # Stop only after detecting bottleneck 3 consecutive times

# Bottleneck analysis time window configuration
BOTTLENECK_ANALYSIS_WINDOW=30       # Analysis window before and after bottleneck time point (seconds)

# ----- Performance Monitoring Configuration -----
# Performance monitoring switch (true/false) - When enabled, monitors the performance impact of the monitoring system itself
PERFORMANCE_MONITORING_ENABLED=${PERFORMANCE_MONITORING_ENABLED:-true}

# Performance threshold configuration
MAX_COLLECTION_TIME_MS=${MAX_COLLECTION_TIME_MS:-1000}     # Maximum data collection time (milliseconds)

# Error handling threshold
MAX_CONSECUTIVE_ERRORS=${MAX_CONSECUTIVE_ERRORS:-5}        # Maximum consecutive error count

# QPS test success rate and latency thresholds
SUCCESS_RATE_THRESHOLD=95    # Success rate threshold (%)
MAX_LATENCY_THRESHOLD=1000   # Maximum latency threshold (ms)

# ----- Block Node Height Monitoring Configuration -----
# Block height difference threshold, triggers warning
BLOCK_HEIGHT_DIFF_THRESHOLD=50
# Block height time threshold (seconds), triggers warning
BLOCK_HEIGHT_TIME_THRESHOLD=300
# Block height monitoring frequency (monitoring times per second)
BLOCK_HEIGHT_MONITOR_RATE=1

# ----- Log Output Configuration -----
LOG_CONSOLE=${LOG_CONSOLE:-true}       # Console output
LOG_FILE=${LOG_FILE:-true}             # File output

# Export internal configuration variables
export BOTTLENECK_CPU_THRESHOLD BOTTLENECK_MEMORY_THRESHOLD BOTTLENECK_EBS_UTIL_THRESHOLD
export BOTTLENECK_EBS_LATENCY_THRESHOLD BOTTLENECK_NETWORK_THRESHOLD BOTTLENECK_ERROR_RATE_THRESHOLD BOTTLENECK_EBS_IOPS_THRESHOLD BOTTLENECK_EBS_THROUGHPUT_THRESHOLD
export BOTTLENECK_CONSECUTIVE_COUNT BOTTLENECK_ANALYSIS_WINDOW
export PERFORMANCE_MONITORING_ENABLED MAX_COLLECTION_TIME_MS MAX_CONSECUTIVE_ERRORS
export SUCCESS_RATE_THRESHOLD MAX_LATENCY_THRESHOLD
export BLOCK_HEIGHT_DIFF_THRESHOLD BLOCK_HEIGHT_TIME_THRESHOLD BLOCK_HEIGHT_MONITOR_RATE
export LOG_CONSOLE LOG_FILE