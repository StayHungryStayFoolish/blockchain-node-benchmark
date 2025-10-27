#!/usr/bin/env python3
"""
Report Generator - Enhanced Version with Bottleneck Mode Support
Integrates monitoring overhead analysis, configuration status check, and specific analysis features
Supports bottleneck detection results display and specialized analysis reports
"""

import pandas as pd
import json
import subprocess
import os
import sys
import argparse
import glob
import traceback
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from datetime import datetime
from scipy.stats import pearsonr
from typing import Dict, Union

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from visualization.chart_style_config import UnifiedChartStyle
from visualization.device_manager import DeviceManager
from visualization.performance_visualizer import format_time_axis
from utils.ena_field_accessor import ENAFieldAccessor

# Bilingual translation dictionary
TRANSLATIONS = {
    'en': {
        # EBS Analysis Section
        'ebs_performance_analysis': 'EBS Performance Analysis Results',
        'performance_warnings': 'Performance Warnings',
        'no_performance_anomaly': 'No performance anomaly detected',
        'occurred_at': 'Occurred at',
        'aws_ebs_baseline_stats': 'AWS EBS Baseline Performance Statistics',
        'device': 'Device',
        'metric': 'Metric',
        'baseline_config': 'Baseline (Config)',
        'min': 'Min',
        'avg': 'Avg',
        'max': 'Max',
        'data_device': 'DATA Device',
        'accounts_device': 'ACCOUNTS Device',
        'iops': 'IOPS',
        'throughput_mibs': 'Throughput (MiB/s)',
        'iostat_sampling_stats': 'iostat Raw Sampling Data Statistics',
        'utilization_pct': 'Utilization (%)',
        'latency_ms': 'Latency (ms)',
        'no_aws_ebs_data': 'No AWS EBS baseline data available',
        'no_iostat_data': 'No iostat sampling data available',
        # Configuration Section
        'config_status_check': 'Configuration Status Check',
        'config_item': 'Configuration Item',
        'status': 'Status',
        'value': 'Value',
        'blockchain_node_type': 'Blockchain Node Type',
        'configured': 'Configured',
        'not_configured': 'Not Configured',
        'data_volume_type': 'DATA Volume Type',
        'accounts_volume_type': 'ACCOUNTS Volume Type',
        'note': 'Note',
        'accounts_not_configured_note': 'ACCOUNTS Device not configured, only monitoring DATA Device performance. Recommend configuring ACCOUNTS_DEVICE for complete storage performance analysis.',
        # Monitoring Overhead Section
        'monitoring_overhead_comprehensive_analysis': 'Monitoring Overhead Comprehensive Analysis',
        'system_resource_overview': 'System Resource Overview',
        'metric_label': 'Metric',
        'value_label': 'Value',
        'cpu_cores': 'CPU Cores',
        'total_memory': 'Total Memory',
        'avg_cpu_usage': 'Average CPU Usage',
        'avg_memory_usage': 'Average Memory Usage',
        'resource_usage_comparison': 'Resource Usage Comparison Analysis',
        'resource_type': 'Resource Type',
        'monitoring_system': 'Monitoring System',
        'blockchain_node': 'Blockchain Node',
        'other_processes': 'Other Processes',
        'cpu_usage_rate': 'CPU Usage',
        'memory_usage_rate': 'Memory Usage',
        'memory_usage_amount': 'Memory Usage Amount',
        'process_count': 'Process Count',
        'percentage_note': 'Percentages in parentheses represent the proportion of total system resources',
        'monitoring_io_overhead': 'Monitoring System I/O Overhead',
        'average': 'Average',
        'maximum': 'Maximum',
        'monitoring_overhead_conclusion': 'Monitoring Overhead Conclusion',
        'monitoring_resource_analysis': 'Monitoring system resource consumption analysis:',
        'cpu_overhead': 'CPU overhead',
        'memory_overhead': 'Memory overhead',
        'io_overhead': 'I/O overhead',
        'blockchain_resource_analysis': 'Blockchain node resource consumption analysis:',
        'cpu_usage': 'CPU usage',
        'memory_usage': 'Memory usage',
        'monitoring_impact': 'Monitoring system impact on test results:',
        'significant': 'Significant',
        'minor': 'Minor',
        'monitoring_cpu_exceeds_5': 'monitoring CPU overhead exceeds 5%',
        'monitoring_cpu_below_5': 'monitoring CPU overhead below 5%',
        'monitoring_data_unavailable': 'Monitoring Overhead Data Not Available',
        'monitoring_data_not_found': 'Monitoring overhead data file not found or empty. Please ensure monitoring overhead statistics are enabled during performance testing.',
        'expected_file': 'Expected file',
        'how_to_enable': 'How to Enable Monitoring Overhead Statistics',
        'monitoring_integrated': 'Monitoring overhead statistics feature is integrated into the unified monitoring system and enabled by default.',
        'check_config': 'If monitoring overhead data is not generated, please check the following configuration:',
        'ensure_variable_set': 'Ensure the MONITORING_OVERHEAD_LOG variable in config_loader.sh is correctly set',
        'ensure_function_calls': 'Ensure log_performance_data function calls write_monitoring_overhead_log',
        'check_permissions': 'Check if log directory permissions are correct',
        'detailed_analysis': 'Monitoring Overhead Detailed Analysis',
        'resource_usage_trends': 'Resource Usage Trends',
        'resource_proportion_analysis': 'Resource Proportion Analysis',
        'monitoring_performance_relationship': 'Monitoring Overhead and Performance Relationship',
        # Monitoring Overhead Charts Section
        'resource_proportion_chart': 'Resource Proportion Analysis',
        'resource_distribution_image': 'Resource Distribution Chart',
        'chart_shows_component_resources': 'This chart shows the proportion of system resources occupied by different components:',
        'all_monitoring_processes': 'All monitoring processes resource proportion',
        'blockchain_related_processes': 'Blockchain-related processes resource proportion',
        'other_system_processes': 'Other system processes resource proportion',
        'monitoring_performance_chart': 'Monitoring Overhead and Performance Relationship',
        'monitoring_impact_image': 'Monitoring Impact Analysis',
        'chart_analyzes_correlation': 'This chart analyzes the correlation between monitoring overhead and system performance metrics:',
        'monitoring_cpu_vs_qps': 'Monitoring CPU Overhead vs QPS',
        'monitoring_io_vs_ebs': 'Monitoring I/O Overhead vs EBS Performance',
        'monitoring_cpu_qps_relationship': 'Relationship between monitoring CPU usage and system throughput',
        'monitoring_io_ebs_relationship': 'Relationship between monitoring I/O and storage performance',
        'monitoring_overhead_label': 'Monitoring Overhead',
        'iops_margin': 'IOPS margin',
        'monitoring_overhead_detailed': 'Monitoring Overhead Detailed Analysis',
        'monitoring_detailed_unavailable': 'Monitoring Overhead Detailed Data Unavailable',
        'monitoring_file_not_found': 'Monitoring overhead data file not found or chart generation failed. Please ensure:',
        'overhead_csv_generated': 'Monitoring overhead CSV file has been correctly generated',
        'chart_script_executed': 'Chart generation script has been correctly executed',
        'output_dir_permissions': 'Output directory has correct write permissions',
        'how_to_generate_charts': 'How to Generate Monitoring Overhead Charts',
        'use_command_to_generate': 'You can use the following command to generate monitoring overhead analysis charts:',
        'generate_resource_distribution': 'Generate resource distribution chart',
        'resource_distribution_failed': 'Resource distribution chart generation failed',
        'generate_monitoring_impact': 'Generate monitoring impact analysis chart',
        'read_memory_data_failed': 'Failed to read memory data',
        'read_network_data_failed': 'Failed to read network data',
        # Monitoring Impact Chart Section
        'get_io_data_from_perf': 'Get I/O data and basic memory data from performance CSV',
        'use_basic_memory_data': 'Use basic memory data from performance CSV (unit: MB, needs conversion to GB)',
        'convert_to_gb': 'Convert to GB',
        'convert_to_cores_gb': 'Convert to cores and GB',
        'calculate_proportions': 'Calculate proportions',
        'create_3x2_layout': 'Create 3x2 layout',
        'subplot_cpu_core_usage': 'Subplot 1: CPU Core Usage',
        'subplot_memory_usage': 'Subplot 2: Memory Usage',
        'subplot_monitoring_io': 'Subplot 3: Monitoring I/O Impact',
        'calculate_io_overhead_pct': 'Calculate I/O overhead percentage',
        'subplot_system_memory': 'Subplot 4: System Memory Overview',
        'subplot_cpu_overhead_trend': 'Subplot 5: CPU Overhead Trend',
        'subplot_monitoring_efficiency': 'Subplot 6: Monitoring Efficiency Summary',
        'generation_complete_monitoring': 'Generation complete: monitoring_impact_chart.png',
        'monitoring_impact_failed': 'Monitoring impact analysis chart generation failed',
        # EBS Bottleneck Section
        'generate_ebs_bottleneck_section': 'Generate EBS bottleneck analysis section',
        'device_type_list': 'Device type list',
        'device_bottleneck': 'Device Bottleneck',
        'device_label': 'Device',
        # EBS Bottleneck Analysis Section
        'no_bottleneck_detected': 'No Bottleneck Detected',
        'device_performance_good': 'Device performance is good, no bottleneck found.',
        'ebs_bottleneck_analysis': 'EBS Bottleneck Analysis',
        'ebs_analysis_based_on': 'EBS bottleneck analysis is based on AWS recommended performance metrics, including utilization, latency, AWS standard IOPS and throughput.',
        'root_cause_based_on': 'Root cause analysis is based on correlation analysis between monitoring overhead and EBS performance metrics.',
        'no_ebs_bottleneck_detected': 'No EBS Bottleneck Detected',
        'no_ebs_bottleneck_found': 'No EBS performance bottleneck found during testing. Storage performance is good and will not limit overall system performance.',
        'generate_root_cause_html': 'Generate bottleneck root cause analysis HTML',
        'cannot_perform_root_cause': 'Cannot Perform Root Cause Analysis',
        'missing_overhead_data': 'Missing monitoring overhead data, cannot determine if bottleneck is caused by monitoring system.',
        'get_overhead_data': 'Get monitoring overhead data',
        'estimate_monitoring_impact': 'Estimate monitoring overhead impact on EBS',
        'root_cause_significant_impact': 'Root Cause Analysis: Significant Monitoring System Impact',
        'monitoring_impact_level': 'Monitoring system impact on EBS performance',
        'monitoring_avg_iops': 'Monitoring system average IOPS',
        'monitoring_avg_throughput': 'Monitoring system average throughput',
        'recommendation': 'Recommendation',
        'reduce_monitoring_frequency': 'Consider reducing monitoring frequency or optimizing monitoring system I/O operations to reduce impact on',
        'root_cause_moderate_impact': 'Root Cause Analysis: Moderate Monitoring System Impact',
        'monitoring_has_some_impact': 'Monitoring system has some impact on device, but is not the main bottleneck source. Should optimize both business logic and monitoring system.',
        'root_cause_minor_impact': 'Root Cause Analysis: Minor Monitoring System Impact',
        'bottleneck_from_workload': 'Device bottleneck is mainly caused by business workload, monitoring system impact is negligible. Should optimize business logic or upgrade EBS configuration.',
        'overhead_detailed_data': 'Monitoring Overhead Detailed Data',
        'monitoring_overhead_breakdown': 'Monitoring Overhead Component Breakdown',
        'data_shows_component_consumption': 'The following data shows the resource consumption of each monitoring component during testing, helping to evaluate real resource requirements in production environment.',
        'monitoring_component_label': 'Monitoring Component',
        'avg_cpu_usage_label': 'Average CPU Usage',
        'peak_cpu_usage_label': 'Peak CPU Usage',
        'avg_memory_usage_label': 'Average Memory Usage',
        'peak_memory_usage_label': 'Peak Memory Usage',
        'avg_iops_label': 'Average IOPS',
        'peak_iops_label': 'Peak IOPS',
        'avg_throughput_label': 'Average Throughput',
        'data_completeness_label': 'Data Completeness',
        'iostat_monitoring': 'iostat Monitoring',
        'sar_monitoring': 'sar Monitoring',
        # Overhead Data Table Section
        'none_label': 'None',
        'storage_io_label': 'Storage I/O',
        'vmstat_monitoring': 'vmstat Monitoring',
        'data_collection_script': 'Data Collection Script',
        'total_monitoring_overhead': 'Total Monitoring Overhead',
        'overhead_analysis_notes': 'Monitoring Overhead Analysis Notes',
        'memory_usage_label': 'Memory Usage',
        'overhead_data_not_available': 'Monitoring Overhead Data Not Available',
        'overhead_file_not_found': 'Monitoring overhead data file not found or empty. Please ensure monitoring overhead statistics are enabled during performance testing.',
        'expected_file_label': 'Expected file',
        'description_label': 'Description',
        'overhead_auto_generated': 'Monitoring overhead data is automatically generated by unified_monitor.sh, no need to manually run additional tools.',
        'total_overhead_usually': 'Total monitoring overhead usually accounts for 1-3% of system resources and can be ignored.',
        'iops_throughput_zero_reason': 'Reasons for IOPS/Throughput Being 0',
        'monitoring_reads_proc': 'Monitoring system mainly reads <code>/proc</code> virtual filesystem, kernel does not count physical I/O statistics',
        'actual_io_overhead': 'Actual I/O overhead < 0.00005 IOPS/s, even with 4 decimal precision (%.4f) still shows as 0.0000',
        'proves_efficient_design': 'This proves the monitoring system is efficiently designed with almost no impact on production environment',
        'to_view_tiny_values': 'To view tiny values, increase precision to %.6f or higher in source code',
        'overhead_table_generation_failed': 'Monitoring overhead table generation failed',
        'error_message_label': 'Error message',
        'check_data_format': 'Please check the format and completeness of monitoring overhead data.',
        'generate_independent_tools': 'Generate independent analysis tools results display',
        'ebs_bottleneck_detection': 'EBS Bottleneck Detection Results',
        'report_file_label': 'Report file',
        'analyze_ebs_under_qps': 'Analyze EBS storage performance bottlenecks under different QPS loads',
        'ebs_iops_conversion': 'EBS IOPS Conversion Analysis',
        'convert_iostat_to_aws': 'Convert iostat metrics to AWS EBS standard IOPS and Throughput metrics',
        'ebs_comprehensive_analysis': 'EBS Comprehensive Analysis',
        'ebs_performance_report': 'EBS storage performance comprehensive analysis report',
        'monitoring_overhead_calculation': 'Monitoring Overhead Calculation',
        'data_file_label': 'Data file',
        'detailed_overhead_data': 'Detailed monitoring system resource consumption data',
        'about': 'about',
        # EBS Baseline Analysis Section
        'component_breakdown': 'Resource consumption breakdown of each system monitoring tool (estimated based on overall monitoring data)',
        'cpu_percentage_used': 'CPU percentage used by monitoring tools',
        'memory_size_used': 'Memory size used by monitoring tools (MB)',
        'disk_io_operations': 'Disk I/O operations generated by monitoring tools (tiny values shown as < 0.0001)',
        'disk_throughput_generated': 'Disk Throughput generated by monitoring tools (MiB/s)',
        'data_completeness_percentage': 'Data completeness percentage of monitoring data',
        'improved_ebs_baseline': 'Improved EBS baseline analysis section',
        'safe_get_env_float': 'Safely get environment variable and convert to float',
        'safe_utilization_calc': 'Safe utilization calculation function',
        'baseline_not_configured': 'Baseline not configured',
        'utilization_calc_failed': 'Utilization calculation failed',
        'calculation_error': 'Calculation error',
        'safe_field_search': 'Safe field search and data extraction',
        'safe_get_metric_avg': 'Safely get metric average',
        'field_not_found': 'Related field not found',
        'data_empty': 'Data is empty',
        'data_extraction_failed': 'Data extraction failed',
        'calculate_data_device': 'Calculate DATA Device metrics',
        'calculate_accounts_device': 'Calculate ACCOUNTS Device metrics',
        'calculate_utilization': 'Calculate utilization',
        'smart_warning_check': 'Smart warning check',
        'check_utilization_warning': 'Check if utilization needs warning',
        'device_iops_high': 'Device IOPS utilization too high',
        'device_throughput_high': 'Device Throughput utilization too high',
        'generate_html_report': 'Generate HTML report',
        'high_utilization_warning': 'High Utilization Warning',
        'recommendation_label': 'Recommendation',
        'consider_upgrade_ebs': 'Consider upgrading EBS configuration or optimizing I/O patterns',
        'preprocess_display_values': 'Preprocess display values to avoid formatting errors',
        'data_not_available': 'Data Not Available',
        'ebs_aws_baseline_analysis': 'EBS AWS Baseline Analysis',
        'device_name': 'Device',
        'metric_type': 'Metric Type',
        'baseline_value': 'Baseline Value',
        'actual_value': 'Actual Value',
        'utilization_label': 'Utilization',
        'status_label': 'Status',
        'ledger_storage': 'LEDGER Storage',
        'warning_label': 'Warning',
        'normal_label': 'Normal',
        'accounts_storage': 'Accounts Storage',
        'ebs_baseline_notes': 'EBS Baseline Analysis Notes',
        'baseline_configured_via_env': 'EBS performance baseline configured via environment variables',
        'avg_performance_during_test': 'Average performance during testing',
        'actual_vs_baseline_percentage': 'Percentage of actual performance vs baseline performance',
        'warning_threshold_label': 'Warning threshold',
        'utilization_exceeds_warning': 'Warning displayed when utilization exceeds',
        'configuration_method': 'Configuration Method',
        'set_env_variables': 'Set environment variables',
        'ebs_baseline_generation_failed': 'EBS baseline analysis generation failed',
        'baseline_analysis_failed': 'Baseline Analysis Failed',
        'please_check_label': 'Please check:',
        'env_config_correct': 'Environment variable configuration is correct',
        'csv_contains_fields': 'CSV data contains necessary fields',
        'data_format_correct': 'Data format is correct',
        'generate_ena_warnings': 'Generate ENA network warning section',
        'check_ena_availability': 'Check ENA data availability',
        'analyze_ena_limitations': 'Analyze ENA limitation data',
        'ena_network_normal': 'ENA Network Status Normal',
        'no_ena_limitations': 'No ENA network limitations detected during monitoring. All network metrics are within normal range.',
        'ena_limitation_detected': 'ENA Network Limitation Detection Results',
        'detected_ena_limitations': 'Detected the following ENA network limitation situations, recommend focusing on network performance optimization:',
        'duration_time': 'Duration',
        'to': 'to',
        # ENA Warnings Section
        'occurrence_count': 'Occurrence count',
        'times': 'times',
        'max_value_label': 'Max value',
        'cumulative_impact': 'Cumulative impact',
        'consider_optimize_network': 'Consider optimizing network configuration, upgrading hardware resources, or adjusting application load patterns.',
        'ena_warning_generation_failed': 'ENA warning generation failed',
        'analyze_ena_limitations_func': 'Analyze ENA limitation occurrences',
        'analyze_exceeded_fields': 'Analyze exceeded type fields',
        'get_field_analysis': 'Get field analysis information',
        'filter_limited_records': 'Filter records with limitations (value > 0)',
        'special_handling_connection': 'Special handling: Connection capacity insufficient warning',
        'find_available_fields': 'Find available type fields',
        'use_dynamic_threshold': 'Use dynamic threshold',
        'warning_when_below': 'Warning when available capacity is below',
        'connection_capacity_warning': 'Connection Capacity Insufficient Warning',
        'minimum_remaining': 'Minimum remaining',
        'connections': 'connections',
        'average_remaining': 'Average remaining',
        'generate_ena_data_table': 'Generate ENA data statistics table',
        'generate_statistics': 'Generate statistics',
        'use_accessor_for_description': 'Use ENAFieldAccessor to get field descriptions',
        'generate_html_table': 'Generate HTML table',
        'set_format_for_field_types': 'Set different formats for different field types',
        'status_indicator': 'Status indicator',
        'use_threshold_for_connection': 'Use dynamic threshold to determine connection capacity status',
        'ena_network_statistics': 'ENA Network Statistics',
        'ena_metric': 'ENA Metric',
        'current_value': 'Current Value',
        'max_value': 'Max Value',
        'avg_value': 'Average Value',
        'note_label': 'Note',
        'exceeded_fields_show_drops': 'Exceeded fields show cumulative packet drops, larger values indicate more severe network limitations',
        'available_connections_show_capacity': 'Available connections show remaining connection capacity, smaller values indicate greater connection pressure',
        'ena_table_generation_failed': 'ENA data table generation failed',
        'improved_cpu_ebs_correlation': 'Improved CPU and EBS correlation analysis table generation',
        'cpu_iowait_vs_util': 'CPU I/O Wait vs Device Utilization',
        'cpu_iowait_vs_queue': 'CPU I/O Wait vs I/O Queue Length',
        'cpu_iowait_vs_read_latency': 'CPU I/O Wait vs Read Latency',
        'cpu_iowait_vs_write_latency': 'CPU I/O Wait vs Write Latency',
        'user_cpu_vs_read_requests': 'User Mode CPU vs Read Requests',
        'system_cpu_vs_write_requests': 'System Mode CPU vs Write Requests',
        # CPU-EBS Correlation Section
        'use_max_or_default': 'Use max value or default value',
        'safe_correlation_func': 'Safe correlation analysis function',
        'safe_correlation_analysis': 'Safe correlation analysis',
        'missing_cpu_field': 'Missing CPU field',
        'missing_ebs_field': 'Missing EBS field',
        'data_validity_check': 'Data validity check',
        'data_is_empty': 'Data is empty',
        'insufficient_data_points': 'Insufficient valid data points',
        'correlation_result_nan': 'Correlation calculation result is NaN',
        'improved_correlation_strength': 'Improved correlation strength classification',
        'very_strong_correlation': 'Very Strong Correlation',
        'strong_correlation': 'Strong Correlation',
        'moderate_correlation': 'Moderate Correlation',
        'weak_correlation': 'Weak Correlation',
        'very_weak_correlation': 'Very Weak Correlation',
        'improved_significance': 'Improved statistical significance determination',
        'highly_significant_3': 'Highly Significant (***)',
        'highly_significant_2': 'Highly Significant (**)',
        'significant_1': 'Significant (*)',
        'not_significant': 'Not Significant',
        'device_type': 'Device Type',
        'analysis_item': 'Analysis Item',
        'cpu_metric': 'CPU Metric',
        'ebs_metric': 'EBS Metric',
        'correlation_coefficient': 'Correlation Coefficient',
        'p_value': 'P Value',
        'statistical_significance': 'Statistical Significance',
        'correlation_strength': 'Correlation Strength',
        'valid_sample_count': 'Valid Sample Count',
        'data_integrity': 'Data Integrity',
        'analysis_failed': 'Analysis failed',
        'precise_field_matching': 'Precise field matching',
        'exact_match': 'Exact match',
        'fuzzy_match_strict': 'Fuzzy match (stricter)',
        'analyze_data_device': 'Analyze DATA Device',
        'analyze_accounts_device': 'Analyze ACCOUNTS Device',
        'correlation_data_unavailable': 'Correlation Analysis Data Not Available',
        'possible_reasons': 'Possible reasons:',
        'missing_cpu_ebs_fields': 'Missing necessary CPU or EBS performance fields',
        'data_quality_issues': 'Data quality issues (too many NaN values)',
        'insufficient_data_less_10': 'Insufficient valid data points (less than 10)',
        'generate_improved_table': 'Generate improved HTML table',
        'set_row_color_by_strength': 'Set row color based on correlation strength',
        'correlation_analysis_notes': 'Correlation Analysis Notes',
        'correlation_range': 'Correlation coefficient range',
        'larger_abs_stronger': '-1.0 to 1.0, larger absolute value indicates stronger correlation',
        'significance_levels': '*** p<0.001, ** p<0.01, * p<0.05',
        'strength_classification': 'Correlation strength classification: |r|≥0.8 very strong, |r|≥0.6 strong, |r|≥0.4 moderate, |r|≥0.2 weak',
        'data_integrity_percentage': 'Data integrity: Percentage of valid data points out of total data points',
        'format_block_height_readable': 'Convert block_height related field values to human-readable format',
        'enhanced_block_height_analysis': 'Enhanced block height performance analysis',
        'use_comparison_table': 'Use comparison table display',
        'block_height_monitoring': 'Block Height Monitoring',
        'no_block_height_data': 'No block height data available',
        'add_time_series_chart': 'Add time series chart display',
        'add_data_loss_stats': 'Add data_loss_stats.json file display',
        'collect_block_height_data': 'Collect block height data',
        'only': 'only',
        'items': 'items',
        'high_latency': 'High Latency',
        'no_aws_ebs_baseline': 'No AWS EBS baseline data available',
        'iostat_raw_sampling_stats': 'iostat Raw Sampling Data Statistics',
        'device_impact_suffix': 'device impact',
        'block_height_data_comparison': 'Block Height Data Comparison',
        'blockchain_node_sync_analysis': 'Blockchain Node Sync Analysis',
        'block_height_analysis_failed': 'Block height analysis failed',
        'block_height_sync_time_series': 'Block Height Sync Time Series',
        'block_height_sync_status': 'Block Height Sync Status',
        'chart_shows_block_height_diff': 'This chart shows the block height difference between local node and mainnet during testing',
        'blue_curve': 'Blue Curve',
        'block_height_diff_mainnet_minus_local': 'Block height difference (Mainnet - Local)',
        'red_dashed_line': 'Red Dashed Line',
        'anomaly_threshold_50_blocks': 'Anomaly threshold (±50 blocks)',
        'red_area': 'Red Area',
        'data_loss_detected_periods': 'Time periods with detected data loss',
        'statistics_info': 'Statistics Info',
        'sync_quality_stats_top_left': 'Sync quality statistics displayed in top left corner',
        'block_height_chart_not_generated': 'Block height sync chart not generated',
        'possible_reason_node_data_unavailable': 'Possible reason: Blockchain node data unavailable or monitoring not enabled',
        'data_loss_stats_summary': 'Data Loss Statistics Summary',
        'anomaly_sample_count': 'Anomaly Sample Count',
        'anomaly_event_count': 'Anomaly Event Count',
        'total_anomaly_duration': 'Total Anomaly Duration',
        'avg_event_duration': 'Avg Event Duration',
        'stats_file_location': 'Stats File Location',
        'last_updated': 'Last Updated',
        'data_loss_statistics': 'Data Loss Statistics',
        'stats_file_read_failed': 'Stats file read failed',
        'file_location': 'File Location',
        'data_loss_stats_file_not_found': 'data_loss_stats.json file not found. Possible reasons',
        'no_data_loss_detected_during_test': 'No data loss events detected during testing',
        'stats_file_not_archived': 'Stats file not properly archived',
        'block_height_monitor_not_running': 'block_height_monitor.sh not running properly',
        'generated_time': 'Generated Time',
        'unified_field_naming': 'Unified Field Naming',
        'complete_device_support': 'Complete Device Support',
        'monitoring_overhead_analysis': 'Monitoring Overhead Analysis',
        'blockchain_node_specific_analysis': 'Blockchain Node Specific Analysis',
        'bottleneck_detection_analysis': 'Bottleneck Detection Analysis',
        'system_bottleneck_analysis': 'System-Level Bottleneck Analysis',
        'system_bottleneck_detected': 'System-Level Performance Bottleneck Detected',
        'no_system_bottleneck_detected': 'No System-Level Performance Bottleneck Detected',
        'bottleneck_criteria_title': 'System-Level Bottleneck Criteria',
        'bottleneck_criteria_note': 'All three conditions must be met simultaneously:',
        'bottleneck_condition_1': 'Resource Limit: CPU>85% OR Memory>90% OR EBS IOPS/Throughput>90% OR Network>80% OR Error Rate>5%',
        'bottleneck_condition_2': 'Persistence: 3 consecutive detections of above resource limits',
        'bottleneck_condition_3': 'Node Unhealthy: Block height diff>50 AND duration>300s, OR RPC call failure',
        'bottleneck_current_status': 'Current Status',
        'bottleneck_status_normal': 'No system-level bottleneck stop condition was triggered during testing. Although intermittent performance events may exist (see "Performance Warnings" below), the system is running normally and the node is syncing healthily.',
        'consecutive_detections': 'Consecutive Detections',
        'html_content_generation_failed': 'HTML content generation failed',
        'performance_analysis_charts': 'Performance Analysis Charts',
        'charts_provide_comprehensive_visualization': 'The following charts provide comprehensive visualization analysis of system performance, including performance trends, correlation analysis, bottleneck identification, etc.',
        'chart_statistics': 'Chart Statistics',
        'available_charts': 'Available Charts',
        'pending_charts': 'Pending Charts',
        'chart_coverage': 'Chart Coverage',
        'chart_generation_notice': 'Chart Generation Notice',
        'no_chart_files_found': 'No chart files found. Charts will be generated in the following cases',
        'run_performance_visualizer': 'Run performance_visualizer.py to generate performance analysis charts',
        'run_advanced_chart_generator': 'Run advanced_chart_generator.py to generate advanced analysis charts',
        'run_comprehensive_analysis': 'Run comprehensive_analysis.py to generate comprehensive analysis charts',
        'ensure_run_chart_scripts_before_report': 'Please ensure to run the corresponding chart generation scripts before generating the report',
        'following_charts_not_generated': 'The following charts have not been generated yet and will be displayed automatically after running the corresponding scripts',
        'and': 'and',
        'more_charts': 'more charts',
        'warning_statistics': 'Warning Statistics',
        'type': 'Type',
        'count': 'Count',
        'max_value': 'Max Value',
        'time_range': 'Time Range',
        'detailed_warnings': 'Detailed Warnings',
        'time': 'Time',
        'more_warnings': 'more warnings',
        'check_full_log': 'Check full log for details',
        'advanced_analysis_charts': 'Advanced Analysis Charts',
        'ebs_professional_charts': 'EBS Professional Charts',
        'core_performance_charts': 'Core Performance Charts',
        'monitoring_overhead_charts': 'Monitoring & Overhead Charts',
        'network_ena_charts': 'Network & ENA Charts',
        'additional_charts': 'Additional Charts',
        'chart_display_error': 'Chart Display Error',
        'chart_section_generation_failed': 'Chart section generation failed',
        'unknown': 'Unknown',
        'performance_bottleneck_detection_result': 'Performance Bottleneck Detection Result',
        'max_successful_qps': 'Max Successful QPS',
        'bottleneck_trigger_qps': 'Bottleneck Trigger QPS',
        'performance_drop': 'Performance Drop',
        'bottleneck_details': 'Bottleneck Details',
        'detection_time': 'Detection Time',
        'severity_level': 'Severity Level',
        'bottleneck_reason': 'Bottleneck Reason',
        'optimization_recommendations': 'Optimization Recommendations',
        'suggested_next_actions': 'Suggested Next Actions',
        'view_detailed_bottleneck_charts': 'View detailed bottleneck analysis charts to understand root causes',
        'adjust_system_config_per_recommendations': 'Adjust system configuration according to optimization recommendations',
        'consider_hardware_upgrade_or_app_optimization': 'Consider upgrading hardware resources or optimizing application',
        'rerun_test_to_verify_improvements': 'Rerun test to verify improvement effects',
        'bottleneck_info_display_error': 'Bottleneck Info Display Error',
        'bottleneck_info_processing_failed': 'Bottleneck info processing failed',
        'performance_summary': 'Performance Summary',
        'peak_cpu_usage': 'Peak CPU Usage',
        'data_device_avg_iops': 'DATA Device Avg IOPS',
        'accounts_device_avg_iops': 'ACCOUNTS Device Avg IOPS',
        'monitoring_data_points': 'Monitoring Data Points',
        'performance_summary_generation_failed': 'Performance summary generation failed',
        # Chart Titles and Descriptions
        'chart_performance_overview': 'Performance Overview',
        'chart_performance_overview_desc': 'System overall performance overview, including time series display of key metrics such as CPU, Memory, EBS',
        'chart_cpu_ebs_correlation': 'CPU-EBS Correlation Visualization',
        'chart_cpu_ebs_correlation_desc': 'Correlation analysis between CPU Usage and EBS performance metrics to help identify I/O bottlenecks',
        'chart_cpu_ebs_correlation_visualization': 'CPU-EBS Correlation Visualization',
        'chart_cpu_ebs_correlation_visualization_desc': 'Correlation analysis between CPU Usage and EBS performance metrics to help identify I/O bottlenecks',
        'chart_device_performance_comparison': 'Device Performance Comparison',
        'chart_device_performance_comparison_desc': 'Performance comparison analysis between DATA Device and ACCOUNTS Device',
        'chart_await_threshold_analysis': 'Await Time Threshold Analysis',
        'chart_await_threshold_analysis_desc': 'I/O wait time threshold analysis to identify storage performance bottlenecks',
        'chart_util_threshold_analysis': 'Utilization Threshold Analysis',
        'chart_util_threshold_analysis_desc': 'Device Utilization threshold analysis to evaluate resource usage efficiency',
        'chart_monitoring_overhead_analysis': 'Monitoring Overhead Analysis',
        'chart_monitoring_overhead_analysis_desc': 'Resource consumption analysis of the monitoring system itself to evaluate monitoring impact on system performance',
        'chart_smoothed_trend_analysis': 'Smoothed Trend Analysis',
        'chart_smoothed_trend_analysis_desc': 'Smoothed trend analysis of performance metrics showing performance change trends after noise elimination',
        'chart_qps_trend_analysis': 'QPS Trend Analysis',
        'chart_qps_trend_analysis_desc': 'Detailed QPS performance trend analysis showing QPS changes during testing',
        'chart_resource_efficiency_analysis': 'Resource Efficiency Analysis',
        'chart_resource_efficiency_analysis_desc': 'Efficiency analysis of QPS vs resource consumption to evaluate resource cost per QPS',
        'chart_bottleneck_identification': 'Bottleneck Identification',
        'chart_bottleneck_identification_desc': 'Automatic bottleneck identification results marking performance bottleneck points and influencing factors',
        'chart_pearson_correlation_analysis': 'Pearson Correlation Analysis',
        'chart_pearson_correlation_analysis_desc': 'Pearson correlation analysis between CPU and EBS metrics quantifying linear relationships between metrics',
        'chart_linear_regression_analysis': 'Linear Regression Analysis',
        'chart_linear_regression_analysis_desc': 'Linear regression analysis of key metrics to predict performance trends and relationships',
        'chart_negative_correlation_analysis': 'Negative Correlation Analysis',
        'chart_negative_correlation_analysis_desc': 'Negative correlation metric analysis to identify performance trade-off relationships',
        'chart_comprehensive_correlation_matrix': 'Comprehensive Correlation Matrix',
        'chart_comprehensive_correlation_matrix_desc': 'Comprehensive correlation matrix heatmap of all monitoring metrics',
        'chart_performance_trend_analysis': 'Performance Trend Analysis',
        'chart_performance_trend_analysis_desc': 'Long-term performance trend analysis to identify performance change patterns',
        'chart_ena_limitation_trends': 'ENA Network Limitation Trends',
        'chart_ena_limitation_trends_desc': 'AWS ENA network limitation trend analysis showing time changes of PPS, bandwidth, connection tracking limits',
        'chart_ena_connection_capacity': 'ENA Connection Capacity Monitoring',
        'chart_ena_connection_capacity_desc': 'ENA connection capacity real-time monitoring showing available connection changes and capacity warnings',
        'chart_ena_comprehensive_status': 'ENA Comprehensive Status Analysis',
        'chart_ena_comprehensive_status_desc': 'ENA network comprehensive status analysis including limitation distribution, capacity status and severity assessment',
        'chart_performance_correlation_heatmap': 'Performance Correlation Heatmap',
        'chart_performance_correlation_heatmap_desc': 'Heatmap display of performance metric correlations intuitively showing relationship strength between metrics',
        'chart_performance_cliff_analysis': 'Performance Cliff Analysis',
        'chart_performance_cliff_analysis_desc': 'Performance cliff detection and analysis identifying causes of sharp performance drops',
        'chart_comprehensive_analysis_charts': 'Comprehensive Analysis Charts',
        'chart_comprehensive_analysis_charts_desc': 'Comprehensive performance analysis chart collection fully displaying system performance status',
        'chart_qps_performance_analysis': 'QPS Performance Analysis',
        'chart_qps_performance_analysis_desc': 'Specialized QPS performance analysis charts deeply analyzing QPS performance characteristics',
        'chart_ebs_aws_capacity_planning': 'EBS AWS Capacity Planning Analysis',
        'chart_ebs_aws_capacity_planning_desc': 'AWS EBS capacity planning analysis including IOPS and throughput utilization prediction supporting capacity planning decisions',
        'chart_ebs_iostat_performance': 'EBS iostat Performance Analysis',
        'chart_ebs_iostat_performance_desc': 'EBS device iostat performance analysis including read/write separation, latency analysis and queue depth monitoring',
        'chart_ebs_bottleneck_correlation': 'EBS Bottleneck Correlation Analysis',
        'chart_ebs_bottleneck_correlation_desc': 'EBS bottleneck correlation analysis showing relationships between AWS standard perspective and iostat perspective',
        'chart_ebs_performance_overview': 'EBS Performance Overview',
        'chart_ebs_performance_overview_desc': 'EBS comprehensive performance overview including AWS standard IOPS, throughput vs baseline comparison',
        'chart_ebs_bottleneck_analysis': 'EBS Bottleneck Detection Analysis',
        'chart_ebs_bottleneck_analysis_desc': 'EBS bottleneck detection analysis automatically identifying IOPS, throughput and latency bottleneck points',
        'chart_ebs_aws_standard_comparison': 'EBS AWS Standard Comparison',
        'chart_ebs_aws_standard_comparison_desc': 'AWS standard values vs raw iostat data comparison analysis evaluating performance standardization level',
        'chart_ebs_time_series_analysis': 'EBS Time Series Analysis',
        'chart_ebs_time_series_analysis_desc': 'EBS performance time series analysis showing multi-metric time dimension change trends',
        'chart_block_height_sync_chart': 'Blockchain Node Sync Status',
        'chart_block_height_sync_chart_desc': 'Local node vs mainnet block height sync status time series showing sync difference changes and anomaly period annotations',
        'chart_resource_distribution_chart': 'Resource Distribution Analysis',
        'chart_resource_distribution_chart_desc': 'System resource distribution showing the proportion of resources occupied by monitoring system, blockchain node, and other processes',
        'chart_monitoring_impact_chart': 'Monitoring Impact Analysis',
        'chart_monitoring_impact_chart_desc': 'Correlation analysis between monitoring overhead and system performance metrics to evaluate monitoring system impact',
        # Additional UI Text
        'report_title': 'Blockchain Node QPS Benchmark Report: Performance Analysis and Bottlenecks',
        'performance_charts': 'Performance Charts',
        'no_charts_found': 'No charts found.',
        'performance_chart_gallery': 'Performance Chart Gallery',
        'total_charts_generated': 'Total Charts Generated',
        'chart_shows_resource_usage_trend': 'This chart shows the trend of system resource usage during testing, including',
        'monitoring_system_resource_usage': 'Monitoring system resource usage',
        'blockchain_node_resource_usage': 'Blockchain node resource usage',
        'total_system_resource_usage': 'Total system resource usage',
        'cpu_memory_io_overhead_changes': 'CPU, memory, I/O overhead changes over time',
        'cpu_memory_usage_trends': 'CPU and memory usage trends of blockchain process',
        'cpu_memory_usage_entire_system': 'CPU and memory usage of the entire system',
        'cpu': 'CPU',
        'ebs_iops': 'EBS IOPS',
        'local_block_height': 'Local Block Height',
        'mainnet_block_height': 'Mainnet Block Height',
        'block_height_diff': 'Block Height Diff',
    },
    'zh': {
        # EBS Analysis Section
        'ebs_performance_analysis': 'EBS性能分析结果',
        'performance_warnings': '性能警告',
        'no_performance_anomaly': '未发现性能异常',
        'occurred_at': '发生时间',
        'aws_ebs_baseline_stats': 'AWS EBS 基准性能统计',
        'device': '设备',
        'metric': '指标',
        'baseline_config': '配置基准',
        'min': '最小值',
        'avg': '平均值',
        'max': '最大值',
        'data_device': 'DATA设备',
        'accounts_device': 'ACCOUNTS设备',
        'iops': 'IOPS',
        'throughput_mibs': '吞吐量 (MiB/s)',
        'iostat_sampling_stats': 'iostat 原生采样数据统计',
        'utilization_pct': '利用率 (%)',
        'latency_ms': '延迟 (ms)',
        'no_aws_ebs_data': '暂无AWS EBS基准数据',
        'no_iostat_data': '暂无iostat采样数据',
        # Configuration Section
        'config_status_check': '配置状态检查',
        'config_item': '配置项',
        'status': '状态',
        'value': '值',
        'blockchain_node_type': '区块链节点类型',
        'configured': '已配置',
        'not_configured': '未配置',
        'data_volume_type': 'DATA卷类型',
        'accounts_volume_type': 'ACCOUNTS卷类型',
        'note': '提示',
        'accounts_not_configured_note': 'ACCOUNTS Device未配置，仅监控DATA Device性能。建议配置ACCOUNTS_DEVICE以获得完整的存储性能分析。',
        # Monitoring Overhead Section
        'monitoring_overhead_comprehensive_analysis': '监控开销综合分析',
        'system_resource_overview': '系统资源概览',
        'metric_label': '指标',
        'value_label': '值',
        'cpu_cores': 'CPU核数',
        'total_memory': '内存总量',
        'resource_usage_comparison': '资源使用对比分析',
        'resource_type': '资源类型',
        'monitoring_system': '监控系统',
        'blockchain_node': '区块链节点',
        'other_processes': '其他进程',
        'cpu_usage_rate': 'CPU使用率',
        'memory_usage_rate': '内存使用率',
        'memory_usage_amount': '内存使用量',
        'process_count': '进程数量',
        'percentage_note': '括号内百分比表示占系统总资源的比例',
        'monitoring_io_overhead': '监控系统I/O开销',
        'average': '平均值',
        'maximum': '最大值',
        'monitoring_overhead_conclusion': '监控开销结论',
        'monitoring_resource_analysis': '监控系统资源消耗分析:',
        'cpu_overhead': 'CPU开销',
        'memory_overhead': '内存开销',
        'io_overhead': 'I/O开销',
        'blockchain_resource_analysis': '区块链节点资源消耗分析:',
        'cpu_usage': 'CPU使用',
        'memory_usage': '内存使用',
        'monitoring_impact': '监控系统对测试结果的影响:',
        'significant': '显著',
        'minor': '较小',
        'monitoring_cpu_exceeds_5': '监控CPU开销超过5%',
        'monitoring_cpu_below_5': '监控CPU开销低于5%',
        'monitoring_data_unavailable': '监控开销数据不可用',
        'monitoring_data_not_found': '监控开销数据文件未找到或为空。请确保在性能测试期间启用了监控开销统计。',
        'expected_file': '预期文件',
        'how_to_enable': '如何启用监控开销统计',
        'monitoring_integrated': '监控开销统计功能已集成到统一监控系统中，默认启用。',
        'check_config': '如果未生成监控开销数据，请检查以下配置:',
        'ensure_variable_set': '确保 config_loader.sh 中的 MONITORING_OVERHEAD_LOG 变量已正确设置',
        'ensure_function_calls': '确保 log_performance_data 函数中调用了 write_monitoring_overhead_log',
        'check_permissions': '检查日志目录权限是否正确',
        'detailed_analysis': '监控开销详细分析',
        'resource_usage_trends': '资源使用趋势',
        'resource_proportion_analysis': '资源占比分析',
        'monitoring_performance_relationship': '监控开销与性能关系',
        # Monitoring Overhead Charts Section
        'resource_proportion_chart': '资源占比分析',
        'resource_distribution_image': '资源分布图',
        'chart_shows_component_resources': '此图表展示了不同组件对系统资源的占用比例:',
        'all_monitoring_processes': '所有监控进程的资源占比',
        'blockchain_related_processes': '区块链相关进程的资源占比',
        'other_system_processes': '系统中其他进程的资源占比',
        'monitoring_performance_chart': '监控开销与性能关系',
        'monitoring_impact_image': '监控影响分析',
        'chart_analyzes_correlation': '此图表分析了监控开销与系统性能指标之间的相关性:',
        'monitoring_cpu_vs_qps': '监控CPU开销 vs QPS',
        'monitoring_io_vs_ebs': '监控I/O开销 vs EBS性能',
        'monitoring_cpu_qps_relationship': '监控CPU使用与系统吞吐量的关系',
        'monitoring_io_ebs_relationship': '监控I/O与存储性能的关系',
        'monitoring_overhead_label': '监控开销',
        'iops_margin': 'IOPS 余量',
        'monitoring_overhead_detailed': '监控开销详细分析',
        'monitoring_detailed_unavailable': '监控开销详细数据不可用',
        'monitoring_file_not_found': '监控开销数据文件未找到或图表生成失败。请确保:',
        'overhead_csv_generated': '监控开销CSV文件已正确生成',
        'chart_script_executed': '图表生成脚本已正确执行',
        'output_dir_permissions': '输出目录有正确的写入权限',
        'how_to_generate_charts': '如何生成监控开销图表',
        'use_command_to_generate': '可以使用以下命令生成监控开销分析图表:',
        'generate_resource_distribution': '生成资源分布图表',
        'resource_distribution_failed': '资源分布图表生成失败',
        'generate_monitoring_impact': '生成监控影响分析图',
        'read_memory_data_failed': '读取内存数据失败',
        'read_network_data_failed': '读取网络数据失败',
        # Monitoring Impact Chart Section
        'get_io_data_from_perf': '从 performance CSV 获取I/O数据和基础内存数据',
        'use_basic_memory_data': '使用 performance CSV 中的基础内存数据（单位：MB，需转换为GB）',
        'convert_to_gb': '转换为GB',
        'convert_to_cores_gb': '转换为核心数和GB',
        'calculate_proportions': '计算占比',
        'create_3x2_layout': '创建3x2布局',
        'subplot_cpu_core_usage': '子图1: CPU Core Usage',
        'subplot_memory_usage': '子图2: Memory Usage',
        'subplot_monitoring_io': '子图3: Monitoring I/O Impact',
        'calculate_io_overhead_pct': '计算 I/O 开销百分比',
        'subplot_system_memory': '子图4: System Memory Overview',
        'subplot_cpu_overhead_trend': '子图5: CPU Overhead Trend',
        'subplot_monitoring_efficiency': '子图6: Monitoring Efficiency Summary',
        'generation_complete_monitoring': '生成完成: monitoring_impact_chart.png',
        'monitoring_impact_failed': '监控影响分析图表生成失败',
        # EBS Bottleneck Section
        'generate_ebs_bottleneck_section': '生成EBS瓶颈分析部分',
        'device_type_list': '设备类型列表',
        'device_bottleneck': '设备瓶颈',
        'device_label': '设备',
        # EBS Bottleneck Analysis Section
        'no_bottleneck_detected': '未检测到瓶颈',
        'device_performance_good': '设备性能良好，未发现瓶颈。',
        'ebs_bottleneck_analysis': 'EBS瓶颈分析',
        'ebs_analysis_based_on': 'EBS瓶颈分析基于AWS推荐的性能指标，包括利用率、延迟、AWS标准IOPS和吞吐量。',
        'root_cause_based_on': '根因分析基于监控开销与EBS性能指标的相关性分析。',
        'no_ebs_bottleneck_detected': '未检测到EBS瓶颈',
        'no_ebs_bottleneck_found': '在测试期间未发现EBS性能瓶颈。存储性能良好，不会限制系统整体性能。',
        'generate_root_cause_html': '生成瓶颈根因分析HTML',
        'cannot_perform_root_cause': '无法进行根因分析',
        'missing_overhead_data': '缺少监控开销数据，无法确定瓶颈是否由监控系统引起。',
        'get_overhead_data': '获取监控开销数据',
        'estimate_monitoring_impact': '估算监控开销对EBS的影响',
        'root_cause_significant_impact': '根因分析: 监控系统影响显著',
        'monitoring_impact_level': '监控系统对EBS性能的影响程度',
        'monitoring_avg_iops': '监控系统平均IOPS',
        'monitoring_avg_throughput': '监控系统平均吞吐量',
        'recommendation': '建议',
        'reduce_monitoring_frequency': '考虑减少监控频率或优化监控系统I/O操作，以降低对',
        'root_cause_moderate_impact': '根因分析: 监控系统有一定影响',
        'monitoring_has_some_impact': '监控系统对设备有一定影响，但不是主要瓶颈来源。应同时优化业务逻辑和监控系统。',
        'root_cause_minor_impact': '根因分析: 监控系统影响较小',
        'bottleneck_from_workload': '设备瓶颈主要由业务负载引起，监控系统影响可忽略。应优化业务逻辑或提升EBS配置。',
        'overhead_detailed_data': '监控开销详细数据',
        'monitoring_overhead_breakdown': '监控开销组件分解',
        'data_shows_component_consumption': '以下数据显示了测试期间各监控组件的资源消耗情况，帮助评估生产环境的真实资源需求。',
        'monitoring_component_label': '监控组件',
        'avg_cpu_usage_label': '平均CPU Usage',
        'peak_cpu_usage_label': '峰值CPU Usage',
        'avg_memory_usage_label': '平均内存使用',
        'peak_memory_usage_label': '峰值内存使用',
        'avg_iops_label': '平均IOPS',
        'peak_iops_label': '峰值IOPS',
        'avg_throughput_label': '平均Throughput',
        'data_completeness_label': '数据完整性',
        'iostat_monitoring': 'iostat监控',
        'sar_monitoring': 'sar监控',
        # Overhead Data Table Section
        'none_label': '无',
        'storage_io_label': '存储I/O',
        'vmstat_monitoring': 'vmstat监控',
        'data_collection_script': '数据收集脚本',
        'total_monitoring_overhead': '总监控开销',
        'overhead_analysis_notes': '监控开销分析说明',
        'memory_usage_label': '内存使用',
        'total_overhead_usually': '总监控开销通常占系统资源的1-3%，可以忽略不计。',
        'iops_throughput_zero_reason': 'IOPS/Throughput 为 0 的原因',
        'monitoring_reads_proc': '监控系统主要读取 <code>/proc</code> 虚拟文件系统，内核不计入物理 I/O 统计',
        'actual_io_overhead': '实际 I/O 开销 < 0.00005 IOPS/s，即使使用 4 位小数精度（%.4f）仍显示为 0.0000',
        'proves_efficient_design': '这证明监控系统设计高效，对生产环境几乎无影响',
        'to_view_tiny_values': '如需查看极小值，可在源码中将精度提升至 %.6f 或更高',
        'overhead_table_generation_failed': '监控开销表格生成失败',
        'error_message_label': '错误信息',
        'check_data_format': '请检查监控开销数据的格式和完整性。',
        'generate_independent_tools': '生成独立分析工具结果展示',
        'ebs_bottleneck_detection': 'EBS瓶颈检测结果',
        'report_file_label': '报告文件',
        'analyze_ebs_under_qps': '分析EBS存储在不同QPS负载下的性能瓶颈情况',
        'ebs_iops_conversion': 'EBS IOPS转换分析',
        'convert_iostat_to_aws': '将iostat指标转换为AWS EBS标准IOPS和Throughput指标',
        'ebs_comprehensive_analysis': 'EBS综合分析',
        'ebs_performance_report': 'EBS存储性能的综合分析报告',
        'monitoring_overhead_calculation': '监控开销计算',
        'data_file_label': '数据文件',
        'detailed_overhead_data': '详细的监控系统资源消耗数据',
        'about': '约',
        # EBS Baseline Analysis Section
        'component_breakdown': '各个系统监控工具的资源消耗分解（基于总体监控数据估算）',
        'cpu_percentage_used': '监控工具占用的CPU百分比',
        'memory_size_used': '监控工具占用的内存大小(MB)',
        'disk_io_operations': '监控工具产生的磁盘I/O操作数（极小值显示为 < 0.0001）',
        'disk_throughput_generated': '监控工具产生的磁盘Throughput(MiB/s)',
        'data_completeness_percentage': '监控数据的完整性百分比',
        'improved_ebs_baseline': '改进的EBS基准分析部分',
        'safe_get_env_float': '安全获取环境变量并转换为浮点数',
        'safe_utilization_calc': '安全的利用率计算函数',
        'baseline_not_configured': '基准未配置',
        'utilization_calc_failed': '利用率计算失败',
        'calculation_error': '计算错误',
        'safe_field_search': '安全的字段查找和数据提取',
        'safe_get_metric_avg': '安全获取指标平均值',
        'field_not_found': '未找到相关字段',
        'data_empty': '数据为空',
        'data_extraction_failed': '数据提取失败',
        'calculate_data_device': '计算DATA Device指标',
        'calculate_accounts_device': '计算ACCOUNTS Device指标',
        'calculate_utilization': '计算利用率',
        'smart_warning_check': '智能警告判断',
        'check_utilization_warning': '检查利用率是否需要警告',
        'device_iops_high': 'DeviceIOPS利用率过高',
        'device_throughput_high': 'DeviceThroughput利用率过高',
        'generate_html_report': '生成HTML报告',
        'high_utilization_warning': '高利用率警告',
        'recommendation_label': '建议',
        'consider_upgrade_ebs': '考虑升级EBS配置或优化I/O模式',
        'preprocess_display_values': '预处理显示值以避免格式化错误',
        'data_not_available': 'Data Not Available',
        'ebs_aws_baseline_analysis': 'EBS AWS基准分析',
        'device_name': '设备',
        'metric_type': '指标类型',
        'baseline_value': '基准值',
        'actual_value': '实际值',
        'utilization_label': '利用率',
        'status_label': '状态',
        'ledger_storage': 'LEDGER存储',
        'warning_label': '警告',
        'normal_label': '正常',
        'accounts_storage': '账户存储',
        'ebs_baseline_notes': 'EBS基准分析说明',
        'baseline_configured_via_env': '通过环境变量配置的EBS性能基准',
        'avg_performance_during_test': '测试期间的平均性能表现',
        'actual_vs_baseline_percentage': '实际性能占基准性能的百分比',
        'warning_threshold_label': '警告阈值',
        'utilization_exceeds_warning': '利用率超过时显示警告',
        'configuration_method': '配置方法',
        'set_env_variables': '设置环境变量',
        'ebs_baseline_generation_failed': 'EBS基准分析生成失败',
        'baseline_analysis_failed': '基准分析失败',
        'please_check_label': '请检查：',
        'env_config_correct': '环境变量配置是否正确',
        'csv_contains_fields': 'CSV数据是否包含必要字段',
        'data_format_correct': '数据格式是否正确',
        'generate_ena_warnings': '生成ENA网络警告section',
        'check_ena_availability': '检查ENA数据可用性',
        'analyze_ena_limitations': '分析ENA限制数据',
        'ena_network_normal': 'ENA网络状态正常',
        'no_ena_limitations': '监控期间未检测到任何ENA网络限制。所有网络指标均在正常范围内。',
        'ena_limitation_detected': 'ENA网络限制检测结果',
        'detected_ena_limitations': '检测到以下ENA网络限制情况，建议关注网络性能优化：',
        'duration_time': '持续Time',
        'to': '至',
        # ENA Warnings Section
        'occurrence_count': '发生次数',
        'times': '次',
        'max_value_label': '最大值',
        'cumulative_impact': '累计影响',
        'consider_optimize_network': '考虑优化网络配置、升级硬件资源或调整应用负载模式。',
        'ena_warning_generation_failed': 'ENA警告生成失败',
        'analyze_ena_limitations_func': '分析ENA限制发生情况',
        'analyze_exceeded_fields': '分析 exceeded 类型字段',
        'get_field_analysis': '获取字段分析信息',
        'filter_limited_records': '筛选限制发生的记录 (值 > 0)',
        'special_handling_connection': '特殊处理: 连接容量不足预警',
        'find_available_fields': '查找 available 类型字段',
        'use_dynamic_threshold': '使用动态阈值',
        'warning_when_below': '当可用量低于最大值的时预警',
        'connection_capacity_warning': '连接容量不足预警',
        'minimum_remaining': '最少剩余',
        'connections': '个连接',
        'average_remaining': '平均剩余',
        'generate_ena_data_table': '生成ENA数据统计表格',
        'generate_statistics': '生成统计数据',
        'use_accessor_for_description': '使用 ENAFieldAccessor 获取字段描述',
        'generate_html_table': '生成HTML表格',
        'set_format_for_field_types': '为不同类型的字段设置不同的格式',
        'status_indicator': '状态指示',
        'use_threshold_for_connection': '使用动态阈值判断连接容量状态',
        'ena_network_statistics': 'ENA网络统计',
        'ena_metric': 'ENA指标',
        'current_value': '当前值',
        'max_value': '最大值',
        'avg_value': '平均值',
        'note_label': '说明',
        'exceeded_fields_show_drops': '超限字段显示累计丢包数量，值越大表示网络限制越严重',
        'available_connections_show_capacity': '可用连接数显示剩余连接容量，值越小表示连接压力越大',
        'ena_table_generation_failed': 'ENA数据表格生成失败',
        'improved_cpu_ebs_correlation': '改进的CPU与EBS关联分析表格生成',
        'cpu_iowait_vs_util': 'CPU I/O Wait vs Device Utilization',
        'cpu_iowait_vs_queue': 'CPU I/O Wait vs I/O队列长度',
        'cpu_iowait_vs_read_latency': 'CPU I/O Wait vs 读Latency',
        'cpu_iowait_vs_write_latency': 'CPU I/O Wait vs 写Latency',
        'user_cpu_vs_read_requests': '用户态CPU vs 读请求数',
        'system_cpu_vs_write_requests': '系统态CPU vs 写请求数',
        # CPU-EBS Correlation Section
        'use_max_or_default': '使用最大值或默认值',
        'safe_correlation_func': '安全的相关性分析函数',
        'safe_correlation_analysis': '安全的相关性分析',
        'missing_cpu_field': '缺少CPU字段',
        'missing_ebs_field': '缺少EBS字段',
        'data_validity_check': '数据有效性检查',
        'data_is_empty': '数据为空',
        'insufficient_data_points': '有效数据点不足',
        'correlation_result_nan': '相关性计算结果为NaN',
        'improved_correlation_strength': '改进的相关性强度分类',
        'very_strong_correlation': '极强相关',
        'strong_correlation': '强相关',
        'moderate_correlation': '中等相关',
        'weak_correlation': '弱相关',
        'very_weak_correlation': '极弱相关',
        'improved_significance': '改进的统计显著性判断',
        'highly_significant_3': '极显著 (***)',
        'highly_significant_2': '高度显著 (**)',
        'significant_1': '显著 (*)',
        'not_significant': '不显著',
        'device_type': 'Device类型',
        'analysis_item': '分析项目',
        'cpu_metric': 'CPU指标',
        'ebs_metric': 'EBS指标',
        'correlation_coefficient': '相关系数',
        'p_value': 'P值',
        'statistical_significance': '统计显著性',
        'correlation_strength': '相关强度',
        'valid_sample_count': '有效样本数',
        'data_integrity': '数据完整性',
        'analysis_failed': '分析失败',
        'precise_field_matching': '精确的字段匹配',
        'exact_match': '精确匹配',
        'fuzzy_match_strict': '模糊匹配（更严格）',
        'analyze_data_device': '分析DATA Device',
        'analyze_accounts_device': '分析ACCOUNTS Device',
        'correlation_data_unavailable': '相关性分析Data Not Available',
        'possible_reasons': '可能的原因：',
        'missing_cpu_ebs_fields': '缺少必要的CPU或EBS性能字段',
        'data_quality_issues': '数据质量问题（过多NaN值）',
        'insufficient_data_less_10': '有效数据点不足（少于10个）',
        'generate_improved_table': '生成改进的HTML表格',
        'set_row_color_by_strength': '根据相关性强度设置行颜色',
        'correlation_analysis_notes': '相关性分析说明',
        'correlation_range': '相关系数范围',
        'larger_abs_stronger': '-1.0 到 1.0，绝对值越大相关性越强',
        'significance_levels': '*** p<0.001, ** p<0.01, * p<0.05',
        'strength_classification': '相关强度分类: |r|≥0.8极强, |r|≥0.6强, |r|≥0.4中等, |r|≥0.2弱',
        'data_integrity_percentage': '数据完整性: 有效数据点占总数据点的百分比',
        'format_block_height_readable': '将block_height相关字段的数值转换为人类可读格式',
        'enhanced_block_height_analysis': '增强的区块高度性能分析',
        'use_comparison_table': '使用对比表格展示',
        'block_height_monitoring': '区块高度监控',
        'no_block_height_data': '暂无区块高度数据',
        'add_time_series_chart': '添加时序图表展示',
        'add_data_loss_stats': '添加data_loss_stats.json文件展示',
        'collect_block_height_data': '收集区块高度数据',
        'only': '仅',
        'items': '个',
        'high_latency': '高延迟',
        'no_aws_ebs_baseline': '暂无AWS EBS基准数据',
        'iostat_raw_sampling_stats': 'iostat 原生采样数据统计',
        'device_impact_suffix': '设备的影响',
        'block_height_data_comparison': '区块高度数据对比',
        'blockchain_node_sync_analysis': '区块链节点同步分析',
        'block_height_analysis_failed': '区块高度分析失败',
        'block_height_sync_time_series': '区块高度同步时序图',
        'block_height_sync_status': '区块高度同步状态',
        'chart_shows_block_height_diff': '此图表展示了测试期间本地节点与主网的区块高度差值变化',
        'blue_curve': '蓝色曲线',
        'block_height_diff_mainnet_minus_local': '区块高度差值 (主网 - 本地)',
        'red_dashed_line': '红色虚线',
        'anomaly_threshold_50_blocks': '异常阈值 (±50个区块)',
        'red_area': '红色区域',
        'data_loss_detected_periods': '检测到数据丢失的时间段',
        'statistics_info': '统计信息',
        'sync_quality_stats_top_left': '左上角显示同步质量统计',
        'block_height_chart_not_generated': '区块高度同步图表未生成',
        'possible_reason_node_data_unavailable': '可能原因：区块链节点数据不可用或监控未启用',
        'data_loss_stats_summary': '数据丢失统计摘要',
        'anomaly_sample_count': '异常采样数',
        'anomaly_event_count': '异常事件数',
        'total_anomaly_duration': '总异常时长',
        'avg_event_duration': '平均事件时长',
        'stats_file_location': '统计文件位置',
        'last_updated': '最后更新',
        'data_loss_statistics': '数据丢失统计',
        'stats_file_read_failed': '统计文件读取失败',
        'file_location': '文件位置',
        'data_loss_stats_file_not_found': '未找到data_loss_stats.json文件。可能的原因',
        'no_data_loss_detected_during_test': '测试期间未检测到数据丢失事件',
        'stats_file_not_archived': '统计文件未正确归档',
        'block_height_monitor_not_running': 'block_height_monitor.sh未正常运行',
        'generated_time': '生成时间',
        'unified_field_naming': '统一字段命名',
        'complete_device_support': '完整Device支持',
        'monitoring_overhead_analysis': '监控开销分析',
        'blockchain_node_specific_analysis': 'Blockchain Node 特定分析',
        'bottleneck_detection_analysis': '瓶颈检测分析',
        'system_bottleneck_analysis': '系统级瓶颈分析',
        'system_bottleneck_detected': '检测到系统级性能瓶颈',
        'no_system_bottleneck_detected': '未检测到系统级性能瓶颈',
        'bottleneck_criteria_title': '系统级瓶颈判定条件',
        'bottleneck_criteria_note': '需同时满足以下三个条件：',
        'bottleneck_condition_1': '资源超限：CPU>85% 或 内存>90% 或 EBS IOPS/Throughput>90% 或 网络>80% 或 错误率>5%',
        'bottleneck_condition_2': '持续性：连续3次检测到上述资源超限',
        'bottleneck_condition_3': '节点不健康：区块高度差异>50且持续时间>300秒，或 RPC调用失败',
        'bottleneck_current_status': '当前状态',
        'bottleneck_status_normal': '测试过程中未触发系统级瓶颈停止条件。虽然可能存在间歇性性能事件（见下方"性能警告"），但系统整体运行正常，节点同步健康。',
        'consecutive_detections': '连续检测次数',
        'html_content_generation_failed': 'HTML内容生成失败',
        'performance_analysis_charts': '性能分析图表',
        'charts_provide_comprehensive_visualization': '以下图表提供了系统性能的全方位可视化分析，包括性能趋势、关联性分析、瓶颈识别等',
        'chart_statistics': '图表统计',
        'available_charts': '可用图表',
        'pending_charts': '待生成图表',
        'chart_coverage': '图表覆盖率',
        'chart_generation_notice': '图表生成提示',
        'no_chart_files_found': '当前没有找到生成的图表文件。图表将在以下情况下生成',
        'run_performance_visualizer': '运行 performance_visualizer.py 生成性能分析图表',
        'run_advanced_chart_generator': '运行 advanced_chart_generator.py 生成高级分析图表',
        'run_comprehensive_analysis': '运行 comprehensive_analysis.py 生成综合分析图表',
        'ensure_run_chart_scripts_before_report': '请确保在生成报告前先运行相应的图表生成脚本',
        'following_charts_not_generated': '以下图表尚未生成，运行相应脚本后将自动显示',
        'and': '还有',
        'more_charts': '个图表',
        'warning_statistics': '警告统计',
        'type': '类型',
        'count': '数量',
        'max_value': '最大值',
        'time_range': '时间范围',
        'detailed_warnings': '详细警告',
        'time': '时间',
        'more_warnings': '条警告',
        'check_full_log': '查看完整日志以获取详细信息',
        'advanced_analysis_charts': '高级分析图表',
        'ebs_professional_charts': 'EBS 专业图表',
        'core_performance_charts': '核心性能图表',
        'monitoring_overhead_charts': '监控与开销图表',
        'network_ena_charts': '网络与 ENA 图表',
        'additional_charts': '附加图表',
        'chart_display_error': '图表展示错误',
        'chart_section_generation_failed': '图表部分生成失败',
        'unknown': '未知',
        'performance_bottleneck_detection_result': '性能瓶颈检测结果',
        'max_successful_qps': '最大成功QPS',
        'bottleneck_trigger_qps': '瓶颈触发QPS',
        'performance_drop': '性能下降',
        'bottleneck_details': '瓶颈详情',
        'detection_time': '检测时间',
        'severity_level': '严重程度',
        'bottleneck_reason': '瓶颈原因',
        'optimization_recommendations': '优化建议',
        'suggested_next_actions': '建议的下一步行动',
        'view_detailed_bottleneck_charts': '查看详细的瓶颈分析图表了解根本原因',
        'adjust_system_config_per_recommendations': '根据优化建议调整系统配置',
        'consider_hardware_upgrade_or_app_optimization': '考虑升级硬件资源或优化应用程序',
        'rerun_test_to_verify_improvements': '重新运行测试验证改进效果',
        'bottleneck_info_display_error': '瓶颈信息显示错误',
        'bottleneck_info_processing_failed': '瓶颈信息处理失败',
        'performance_summary': '性能摘要',
        'avg_cpu_usage': '平均CPU使用率',
        'peak_cpu_usage': '峰值CPU使用率',
        'avg_memory_usage': '平均内存使用率',
        'data_device_avg_iops': 'DATA Device平均IOPS',
        'accounts_device_avg_iops': 'ACCOUNTS Device平均IOPS',
        'monitoring_data_points': '监控数据点',
        'performance_summary_generation_failed': '性能摘要生成失败',
        # Chart Titles and Descriptions
        'chart_performance_overview': '性能概览图表',
        'chart_performance_overview_desc': '系统整体性能概览，包括CPU、内存、EBS等关键指标的时间序列展示',
        'chart_cpu_ebs_correlation': 'CPU-EBS关联可视化',
        'chart_cpu_ebs_correlation_desc': 'CPU使用率与EBS性能指标的关联性分析，帮助识别I/O瓶颈',
        'chart_cpu_ebs_correlation_visualization': 'CPU-EBS关联可视化',
        'chart_cpu_ebs_correlation_visualization_desc': 'CPU使用率与EBS性能指标的关联性分析，帮助识别I/O瓶颈',
        'chart_device_performance_comparison': 'Device性能对比',
        'chart_device_performance_comparison_desc': 'DATA Device和ACCOUNTS Device的性能对比分析',
        'chart_await_threshold_analysis': '等待时间阈值分析',
        'chart_await_threshold_analysis_desc': 'I/O等待时间的阈值分析，识别存储性能瓶颈',
        'chart_util_threshold_analysis': '利用率阈值分析',
        'chart_util_threshold_analysis_desc': 'Device利用率的阈值分析，评估资源使用效率',
        'chart_monitoring_overhead_analysis': '监控开销分析',
        'chart_monitoring_overhead_analysis_desc': '监控系统本身的资源消耗分析，评估监控对系统性能的影响',
        'chart_smoothed_trend_analysis': '平滑趋势分析',
        'chart_smoothed_trend_analysis_desc': '性能指标的平滑趋势分析，消除噪声后的性能变化趋势',
        'chart_qps_trend_analysis': 'QPS趋势分析',
        'chart_qps_trend_analysis_desc': 'QPS性能的详细趋势分析，展示测试过程中的QPS变化',
        'chart_resource_efficiency_analysis': '资源效率分析',
        'chart_resource_efficiency_analysis_desc': 'QPS与资源消耗的效率分析，评估每QPS的资源成本',
        'chart_bottleneck_identification': '瓶颈识别图',
        'chart_bottleneck_identification_desc': '自动瓶颈识别结果，标注性能瓶颈点和影响因素',
        'chart_pearson_correlation_analysis': 'Pearson相关性分析',
        'chart_pearson_correlation_analysis_desc': 'CPU与EBS指标的Pearson相关性分析，量化指标间的线性关系',
        'chart_linear_regression_analysis': '线性回归分析',
        'chart_linear_regression_analysis_desc': '关键指标的线性回归分析，预测性能趋势和关系',
        'chart_negative_correlation_analysis': '负相关分析',
        'chart_negative_correlation_analysis_desc': '负相关指标分析，识别性能权衡关系',
        'chart_comprehensive_correlation_matrix': '综合相关性矩阵',
        'chart_comprehensive_correlation_matrix_desc': '所有监控指标的综合相关性矩阵热力图',
        'chart_performance_trend_analysis': '性能趋势分析',
        'chart_performance_trend_analysis_desc': '长期性能趋势分析，识别性能变化模式',
        'chart_ena_limitation_trends': 'ENA网络限制趋势',
        'chart_ena_limitation_trends_desc': 'AWS ENA网络限制趋势分析，显示PPS、带宽、连接跟踪等限制的时间变化',
        'chart_ena_connection_capacity': 'ENA连接容量监控',
        'chart_ena_connection_capacity_desc': 'ENA连接容量实时监控，显示可用连接数变化和容量预警',
        'chart_ena_comprehensive_status': 'ENA综合状态分析',
        'chart_ena_comprehensive_status_desc': 'ENA网络综合状态分析，包括限制分布、容量状态和严重程度评估',
        'chart_performance_correlation_heatmap': '性能相关性热力图',
        'chart_performance_correlation_heatmap_desc': '性能指标相关性的热力图展示，直观显示指标间关系强度',
        'chart_performance_cliff_analysis': '性能悬崖分析',
        'chart_performance_cliff_analysis_desc': '性能悬崖检测和分析，识别性能急剧下降的原因',
        'chart_comprehensive_analysis_charts': '综合分析图表',
        'chart_comprehensive_analysis_charts_desc': '综合性能分析图表集合，全面展示系统性能状况',
        'chart_qps_performance_analysis': 'QPS性能分析',
        'chart_qps_performance_analysis_desc': 'QPS性能的专项分析图表，深入分析QPS性能特征',
        'chart_ebs_aws_capacity_planning': 'EBS AWS容量规划分析',
        'chart_ebs_aws_capacity_planning_desc': 'AWS EBS容量规划分析，包括IOPS和吞吐量利用率预测，支持容量规划决策',
        'chart_ebs_iostat_performance': 'EBS iostat性能分析',
        'chart_ebs_iostat_performance_desc': 'EBS设备的iostat性能分析，包括读写分离、延迟分析和队列深度监控',
        'chart_ebs_bottleneck_correlation': 'EBS瓶颈关联分析',
        'chart_ebs_bottleneck_correlation_desc': 'EBS瓶颈关联分析，展示AWS标准视角与iostat视角的关联关系',
        'chart_ebs_performance_overview': 'EBS性能概览',
        'chart_ebs_performance_overview_desc': 'EBS综合性能概览，包括AWS标准IOPS、吞吐量与基准线对比',
        'chart_ebs_bottleneck_analysis': 'EBS瓶颈检测分析',
        'chart_ebs_bottleneck_analysis_desc': 'EBS瓶颈检测分析，自动识别IOPS、吞吐量和延迟瓶颈点',
        'chart_ebs_aws_standard_comparison': 'EBS AWS标准对比',
        'chart_ebs_aws_standard_comparison_desc': 'AWS标准值与原始iostat数据对比分析，评估性能标准化程度',
        'chart_ebs_time_series_analysis': 'EBS时间序列分析',
        'chart_ebs_time_series_analysis_desc': 'EBS性能时间序列分析，展示多指标时间维度变化趋势',
        'chart_block_height_sync_chart': '区块链节点同步状态',
        'chart_block_height_sync_chart_desc': '本地节点与主网区块高度同步状态时序图，展示同步差值变化和异常时间段标注',
        'chart_resource_distribution_chart': '资源分布分析',
        'chart_resource_distribution_chart_desc': '系统资源分布情况，展示监控系统、区块链节点和其他进程占用的资源比例',
        'chart_monitoring_impact_chart': '监控影响分析',
        'chart_monitoring_impact_chart_desc': '监控开销与系统性能指标的关联性分析，评估监控系统的影响程度',
        # Additional UI Text
        'report_title': '区块链节点QPS基准测试报告：性能分析与瓶颈',
        'performance_charts': '性能图表',
        'no_charts_found': '未找到图表。',
        'performance_chart_gallery': '性能图表画廊',
        'total_charts_generated': '生成的图表总数',
        'chart_shows_resource_usage_trend': '此图表展示了测试期间系统资源使用趋势，包括',
        'monitoring_system_resource_usage': '监控系统资源使用',
        'blockchain_node_resource_usage': '区块链节点资源使用',
        'total_system_resource_usage': '系统总资源使用',
        'cpu_memory_io_overhead_changes': 'CPU、内存、I/O开销随时间的变化',
        'cpu_memory_usage_trends': '区块链进程的CPU和内存使用趋势',
        'cpu_memory_usage_entire_system': '整个系统的CPU和内存使用情况',
        'cpu': 'CPU',
        'ebs_iops': 'EBS IOPS',
        'local_block_height': '本地区块高度',
        'mainnet_block_height': '主网区块高度',
        'block_height_diff': '区块高度差值',
    }
}

def safe_get_env_int(env_name, default_value=0):
    """Safely get environment variable and convert to integer"""
    try:
        value = os.getenv(env_name)
        if value and value != 'N/A' and value.strip():
            return int(value)
        return default_value
    except (ValueError, TypeError):
        print(f"⚠️ Environment variable {env_name} format error")
        return default_value

def get_visualization_thresholds():
    """Get visualization threshold configuration - using safe environment variable access"""
    return {
        'warning': safe_get_env_int('BOTTLENECK_CPU_THRESHOLD', 85),
        'critical': safe_get_env_int('SUCCESS_RATE_THRESHOLD', 95),
        'io_warning': safe_get_env_int('BOTTLENECK_NETWORK_THRESHOLD', 80),
        'memory': safe_get_env_int('BOTTLENECK_MEMORY_THRESHOLD', 90)
    }

class ReportGenerator:
    def __init__(self, performance_csv, config_file='config_loader.sh', overhead_csv=None, bottleneck_info=None, language='en'):
        self.performance_csv = performance_csv
        self.config_file = config_file
        self.overhead_csv = overhead_csv
        self.bottleneck_info = bottleneck_info
        self.language = language
        self.t = TRANSLATIONS.get(language, TRANSLATIONS['en'])
        self.output_dir = os.getenv('REPORTS_DIR', os.path.dirname(performance_csv))
        self.ebs_log_path = os.path.join(os.getenv('LOGS_DIR', '/tmp/blockchain-node-benchmark/logs'), 'ebs_bottleneck_detector.log')
        self.config = self._load_config()
        self.overhead_data = self._load_overhead_data()
        self.bottleneck_data = self._load_bottleneck_data()
        
        # Execute data integrity validation
        self.validation_results = self.validate_data_integrity()
        
    def _load_config(self):
        config = {}
        # Read configuration from environment variables
        config_keys = [
            'BLOCKCHAIN_NODE', 'DATA_VOL_TYPE', 'ACCOUNTS_VOL_TYPE',
            'NETWORK_MAX_BANDWIDTH_GBPS', 'ENA_MONITOR_ENABLED',
            'LEDGER_DEVICE', 'ACCOUNTS_DEVICE',
            'DATA_VOL_MAX_IOPS', 'DATA_VOL_MAX_THROUGHPUT',
            'ACCOUNTS_VOL_MAX_IOPS', 'ACCOUNTS_VOL_MAX_THROUGHPUT'
        ]
        for key in config_keys:
            value = os.getenv(key)
            if value:
                config[key] = value
        return config
    
    def _load_bottleneck_data(self):
        """Load bottleneck detection data - enhanced fault tolerance"""
        # Default bottleneck data structure
        default_data = {
            "timestamp": datetime.now().isoformat(),
            "status": "no_bottleneck_detected",
            "bottleneck_detected": False,
            "bottlenecks": [],
            "bottleneck_types": [],
            "bottleneck_values": [],
            "bottleneck_summary": "No bottleneck detected",
            "detection_time": "",
            "current_qps": 0,
            "last_check": datetime.now().isoformat(),
            "version": "1.0"
        }
        
        # Try loading bottleneck data from multiple possible locations
        bottleneck_files = []
        if self.bottleneck_info:
            bottleneck_files.append(self.bottleneck_info)
        
        # Add default locations
        memory_share_dir = os.getenv('MEMORY_SHARE_DIR', '/tmp/blockchain_monitoring')
        bottleneck_files.extend([
            os.path.join(memory_share_dir, "bottleneck_status.json"),
            os.path.join(self.output_dir, "bottleneck_status.json"),
            "logs/bottleneck_status.json"
        ])
        
        for bottleneck_file in bottleneck_files:
            try:
                if os.path.exists(bottleneck_file):
                    with open(bottleneck_file, 'r') as f:
                        data = json.load(f)
                        # Validate data structure
                        if isinstance(data, dict) and 'bottleneck_detected' in data:
                            print(f"✅ Successfully loaded bottleneck data: {bottleneck_file}")
                            return data
                        else:
                            print(f"⚠️ Invalid bottleneck data format: {bottleneck_file}")
                            
            except (json.JSONDecodeError, IOError) as e:
                print(f"⚠️ Failed to load bottleneck data {bottleneck_file}: {e}")
                continue
        
        print(f"ℹ️ No valid bottleneck data file found, using default data")
        return default_data

    def _load_overhead_data(self):
        """Load monitoring overhead data - supports auto-discovery"""
        try:
            # Method 1: Auto-discover monitoring overhead file
            auto_discovered_file = self._find_latest_monitoring_overhead_file()
            if auto_discovered_file:
                self.overhead_csv = auto_discovered_file
                print(f"✅ Auto-discovered monitoring overhead file: {os.path.basename(auto_discovered_file)}")
                return self._load_from_overhead_csv()
            
            # Method 2: Fallback, extract IOPS data from performance_csv
            if hasattr(self, 'performance_csv') and os.path.exists(self.performance_csv):
                return self._extract_iops_from_performance_csv()
            
            # Method 3: Last resort, return empty data
            return None
        except Exception as e:
            print(f"Error loading overhead data: {e}")
            return None

    def _load_from_overhead_csv(self):
        """Load data from dedicated overhead CSV"""
        try:
            df = pd.read_csv(self.overhead_csv)
            if df.empty:
                return None
            
            # Record sample count
            sample_count = len(df)
                
            # Define required fields and their possible variants
            field_mappings = {
                # Monitoring process resources
                'monitoring_cpu_percent': ['monitoring_cpu_percent', 'monitoring_cpu', 'monitor_cpu', 'overhead_cpu'],
                'monitoring_memory_percent': ['monitoring_memory_percent', 'monitor_memory_percent'],
                'monitoring_memory_mb': ['monitoring_memory_mb', 'monitor_memory', 'overhead_memory'],
                'monitoring_process_count': ['monitoring_process_count', 'process_count', 'monitor_processes'],
                
                # Blockchain node resources
                'blockchain_cpu_sum': ['blockchain_cpu'],  # Multi-process CPU sum (can be >100%)
                'blockchain_cpu_percent': ['blockchain_cpu_percent'],  # System-wide CPU percentage
                'blockchain_memory_percent': ['blockchain_memory_percent'],
                'blockchain_memory_mb': ['blockchain_memory_mb', 'blockchain_memory'],
                'blockchain_process_count': ['blockchain_process_count'],
                
                # System static resources
                'system_cpu_cores': ['system_cpu_cores', 'cpu_cores'],
                'system_memory_gb': ['system_memory_gb', 'memory_gb'],
                'system_disk_gb': ['system_disk_gb', 'disk_gb'],
                
                # System dynamic resources
                'system_cpu_usage': ['system_cpu_usage', 'cpu_usage'],
                'system_memory_usage': ['system_memory_usage', 'memory_usage'],
                'system_disk_usage': ['system_disk_usage', 'disk_usage'],
                
                'monitoring_iops': ['monitoring_iops', 'monitor_iops', 'overhead_iops'],
                'monitoring_throughput_mibs': ['monitoring_throughput_mibs', 'monitor_throughput', 'overhead_throughput']
            }
            
            # Try to find matching fields
            data: Dict[str, Union[int, float]] = {'sample_count': sample_count}
            for target_field, possible_fields in field_mappings.items():
                for field in possible_fields:
                    if field in df.columns:
                        # Calculate average and max values
                        data[f'{target_field}_avg'] = df[field].mean()
                        data[f'{target_field}_max'] = df[field].max()
                        # For percentage fields, calculate ratio
                        if 'percent' in target_field or 'usage' in target_field:
                            data[f'{target_field}_p90'] = df[field].quantile(0.9)
                        break
            
            # Convert blockchain_cpu_sum to system-wide percentage if needed
            if 'blockchain_cpu_sum_avg' in data and 'system_cpu_cores_avg' in data and data['system_cpu_cores_avg'] > 0:
                # blockchain_cpu_sum is multi-process CPU sum (can be >100%)
                # Convert to system-wide percentage: (sum / cores) = percentage
                data['blockchain_cpu_percent_avg'] = data['blockchain_cpu_sum_avg'] / data['system_cpu_cores_avg']
                data['blockchain_cpu_percent_max'] = data.get('blockchain_cpu_sum_max', 0) / data['system_cpu_cores_avg']
            
            # Calculate monitoring overhead ratio
            if 'monitoring_cpu_percent_avg' in data and 'system_cpu_usage_avg' in data and data['system_cpu_usage_avg'] > 0:
                data['monitoring_cpu_ratio'] = data['monitoring_cpu_percent_avg'] / data['system_cpu_usage_avg']
            
            if 'monitoring_memory_percent_avg' in data and 'system_memory_usage_avg' in data and data['system_memory_usage_avg'] > 0:
                data['monitoring_memory_ratio'] = data['monitoring_memory_percent_avg'] / data['system_memory_usage_avg']
            
            # Calculate blockchain node ratio
            if 'blockchain_cpu_percent_avg' in data and 'system_cpu_usage_avg' in data and data['system_cpu_usage_avg'] > 0:
                data['blockchain_cpu_ratio'] = data['blockchain_cpu_percent_avg'] / data['system_cpu_usage_avg']
            
            if 'blockchain_memory_percent_avg' in data and 'system_memory_usage_avg' in data and data['system_memory_usage_avg'] > 0:
                data['blockchain_memory_ratio'] = data['blockchain_memory_percent_avg'] / data['system_memory_usage_avg']
                        
            return data
        except Exception as e:
            print(f"Error loading from overhead CSV: {e}")
            return None

    def _find_latest_monitoring_overhead_file(self):
        """Auto-discover the latest monitoring overhead file"""
        try:
            
            # Get logs directory path - use environment variable or current/logs structure
            logs_dir = os.getenv('LOGS_DIR', os.path.join(self.output_dir, 'current', 'logs'))
            
            # Search for monitoring overhead files
            pattern = os.path.join(logs_dir, 'monitoring_overhead_*.csv')
            files = glob.glob(pattern)
            
            if not files:
                return None
            
            # Return the latest file (sorted by creation time, consistent with comprehensive_analysis.py)
            latest_file = max(files, key=os.path.getctime)
            return latest_file
            
        except Exception as e:
            print(f"Warning: Failed to find monitoring overhead file: {e}")
            return None

    def _extract_iops_from_performance_csv(self):
        """Extract IOPS and throughput data from performance CSV"""
        try:
            df = pd.read_csv(self.performance_csv)
            data = {}
            
            # Extract IOPS data
            if 'monitoring_iops_per_sec' in df.columns:
                iops_data = pd.to_numeric(df['monitoring_iops_per_sec'], errors='coerce').dropna()
                if not iops_data.empty:
                    data['monitoring_iops_avg'] = iops_data.mean()
                    data['monitoring_iops_max'] = iops_data.max()
            
            # Extract throughput data
            if 'monitoring_throughput_mibs_per_sec' in df.columns:
                throughput_data = pd.to_numeric(df['monitoring_throughput_mibs_per_sec'], errors='coerce').dropna()
                if not throughput_data.empty:
                    data['monitoring_throughput_mibs_avg'] = throughput_data.mean()
                    data['monitoring_throughput_mibs_max'] = throughput_data.max()
            
            return data if data else None
            
        except Exception as e:
            # Log error but don't affect main functionality
            print(f"Warning: Failed to extract IOPS data from performance CSV: {e}")
            return None
    
    def _validate_overhead_csv_format(self):
        """Validate monitoring overhead CSV format"""
        if not self.overhead_csv:
            print("⚠️ Monitoring overhead CSV file not specified")
            return False
            
        if not os.path.exists(self.overhead_csv):
            print(f"⚠️ Monitoring overhead CSV file does not exist: {self.overhead_csv}")
            return False
        
        try:
            with open(self.overhead_csv, 'r') as f:
                header = f.readline().strip()
                if not header:
                    print("⚠️ Monitoring overhead CSV file missing header")
                    return False
                
                field_count = len(header.split(','))
                expected_fields = 20  # Based on configured field count
                
                if field_count < 10:  # Should have at least 10 basic fields
                    print(f"⚠️ Monitoring overhead CSV has too few fields, expected at least 10, got {field_count}")
                    return False
                elif field_count != expected_fields:
                    print(f"ℹ️ Monitoring overhead CSV field count: {field_count} (expected {expected_fields})")
                
                # Check if there are data rows
                data_line = f.readline().strip()
                if not data_line:
                    print("⚠️ Monitoring overhead CSV file has no data rows")
                    return False
                    
                print(f"✅ Monitoring overhead CSV format validation passed: {field_count} fields")
                return True
                
        except Exception as e:
            print(f"❌ CSV format validation failed: {e}")
            return False
    
    def validate_data_integrity(self):
        """Validate data integrity"""
        validation_results = {
            'performance_csv': False,
            'overhead_csv': False,
            'bottleneck_data': False,
            'config': False
        }
        
        # Validate performance CSV
        if os.path.exists(self.performance_csv):
            try:
                df = pd.read_csv(self.performance_csv)
                if not df.empty:
                    validation_results['performance_csv'] = True
                    print(f"✅ Performance CSV validation passed: {len(df)} rows of data")
                else:
                    print("⚠️ Performance CSV file is empty")
            except Exception as e:
                print(f"❌ Performance CSV validation failed: {e}")
        else:
            print(f"❌ Performance CSV file does not exist: {self.performance_csv}")
        
        # Validate overhead CSV
        validation_results['overhead_csv'] = self._validate_overhead_csv_format()
        
        # Validate bottleneck data
        if self.bottleneck_data and isinstance(self.bottleneck_data, dict):
            # Support both new format (bottleneck_detected) and old format (bottlenecks)
            if 'bottleneck_detected' in self.bottleneck_data or 'bottlenecks' in self.bottleneck_data:
                validation_results['bottleneck_data'] = True
                print("✅ Bottleneck data validation passed")
            else:
                print("⚠️ Bottleneck data format incomplete")
        else:
            print("ℹ️ Using default bottleneck data")
            validation_results['bottleneck_data'] = True  # Default data also counts as passed
        
        # Validate configuration
        if self.config and isinstance(self.config, dict) and len(self.config) > 0:
            validation_results['config'] = True
            print("✅ Configuration data validation passed")
        else:
            validation_results['config'] = False
            print("ℹ️ Configuration data incomplete (does not affect core functionality)")
        
        # Output validation summary
        passed = sum(validation_results.values())
        total = len(validation_results)
        print(f"\n📊 Data integrity validation results: {passed}/{total} items passed")
        
        return validation_results
    
    def parse_ebs_analyzer_log(self):
        """Parse EBS bottleneck detector log file"""
        warnings = []
        performance_metrics = {}
        
        if not os.path.exists(self.ebs_log_path):
            return warnings, performance_metrics
        
        try:
            with open(self.ebs_log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    
                    # Parse bottleneck warning: ⚠️  [时间] EBS BOTTLENECK DETECTED: 设备 - 类型, (Severity: 级别)
                    if '⚠️' in line and 'EBS BOTTLENECK DETECTED' in line:
                        try:
                            # Extract timestamp
                            timestamp = line.split('[')[1].split(']')[0] if '[' in line and ']' in line else ''
                            
                            # Extract device and type: "nvme2n1 - IOPS"
                            main_part = line.split('EBS BOTTLENECK DETECTED:')[1].split('(Severity:')[0].strip()
                            device = main_part.split('-')[0].strip()
                            bottleneck_type = main_part.split('-')[1].strip().rstrip(',')
                            
                            # Extract severity
                            severity = line.split('Severity:')[1].split(')')[0].strip()
                            
                            # Read next line for detailed metrics
                            if i + 1 < len(lines):
                                detail_line = lines[i + 1].strip()
                                iops_value = ''
                                throughput_value = ''
                                
                                # Extract IOPS: "IOPS: 29788.00/30000 (99%)"
                                if 'IOPS:' in detail_line:
                                    iops_part = detail_line.split('IOPS:')[1].split(',')[0].strip()
                                    iops_value = iops_part.split('/')[0].strip()
                                
                                # Extract Throughput: "Throughput: 2779.61/4000.00 MiB/s (69%)"
                                if 'Throughput:' in detail_line:
                                    throughput_part = detail_line.split('Throughput:')[1].strip()
                                    throughput_value = throughput_part.split('/')[0].strip()
                                
                                # Determine value based on bottleneck type
                                if bottleneck_type == 'IOPS':
                                    value = iops_value
                                    type_label = 'High IOPS'
                                elif bottleneck_type == 'THROUGHPUT':
                                    value = throughput_value
                                    type_label = 'High Throughput'
                                else:
                                    value = iops_value
                                    type_label = 'High Utilization'
                                
                                warnings.append({
                                    'type': type_label,
                                    'device': device,
                                    'value': value,
                                    'timestamp': timestamp,
                                    'data_time': timestamp,
                                    'severity': severity,
                                    'bottleneck_type': bottleneck_type
                                })
                        except (IndexError, ValueError) as e:
                            pass
                    
                    i += 1
        
        except Exception as e:
            print(f"⚠️ Error parsing EBS log: {e}")
        
        return warnings, performance_metrics
    
    def _calculate_data_completeness(self):
        """Calculate monitoring data completeness - file exists, has data, fields complete = 100%"""
        try:
            # Check performance CSV file
            if not os.path.exists(self.performance_csv):
                return 0.0
            
            perf_df = pd.read_csv(self.performance_csv)
            
            # Check if there are data rows
            if len(perf_df) == 0:
                return 0.0
            
            # Check if key fields exist (field completeness)
            required_fields = ['timestamp', 'cpu_usage', 'mem_usage']
            missing_fields = [f for f in required_fields if f not in perf_df.columns]
            
            if missing_fields:
                # Has missing fields, calculate partial completeness
                return (len(required_fields) - len(missing_fields)) / len(required_fields) * 100
            
            # File exists + has data + fields complete = 100%
            return 100.0
            
        except Exception as e:
            print(f"⚠️ Error calculating data completeness: {e}")
            return 0.0
    
    def _format_monitoring_io(self, value, metric_type='iops'):
        """Format monitoring IO value, display tiny values"""
        if value == 0:
            return "< 0.0001"
        elif value < 0.01:
            return f"{value:.4f}"
        elif metric_type == 'iops':
            return f"{value:.2f}"
        else:
            return f"{value:.4f}"
    
    def _format_stat_value(self, value, decimal=0):
        """Format statistical value"""
        if isinstance(value, (int, float)):
            if decimal == 0:
                return f"{value:.0f}"
            else:
                return f"{value:.{decimal}f}"
        return 'N/A'
    
    def generate_ebs_analysis_section(self, warnings, performance_metrics):
        """Generate EBS analysis report HTML section - enhanced version with dual-layer statistics"""
        if not warnings and not performance_metrics:
            return ""
        
        # Read CSV data to calculate statistics
        try:
            df = pd.read_csv(self.performance_csv)
        except:
            df = None
        
        html = f"""
        <div class="section">
            <h2>&#128202; {self.t['ebs_performance_analysis']}</h2>
            
            <div class="subsection">
                <h3>&#9888; {self.t['performance_warnings']}</h3>
        """
        
        if warnings:
            # Generate statistics summary
            summary = {}
            for w in warnings:
                key = (w['device'], w['type'])
                if key not in summary:
                    summary[key] = {
                        'count': 0,
                        'max_value': 0,
                        'first_time': w['timestamp'],
                        'last_time': w['timestamp']
                    }
                summary[key]['count'] += 1
                try:
                    summary[key]['max_value'] = max(summary[key]['max_value'], float(w['value']))
                except:
                    pass
                summary[key]['last_time'] = w['timestamp']
            
            # Display summary table
            html += f'''
            <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 4px; padding: 15px; margin: 15px 0;">
                <h4 style="margin-top: 0; color: #856404;">&#128202; {self.t.get('warning_statistics', 'Warning Statistics')}</h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #ffc107;">
                            <th style="padding: 8px; border: 1px solid #ddd;">{self.t.get('device', 'Device')}</th>
                            <th style="padding: 8px; border: 1px solid #ddd;">{self.t.get('type', 'Type')}</th>
                            <th style="padding: 8px; border: 1px solid #ddd;">{self.t.get('count', 'Count')}</th>
                            <th style="padding: 8px; border: 1px solid #ddd;">{self.t.get('max_value', 'Max Value')}</th>
                            <th style="padding: 8px; border: 1px solid #ddd;">{self.t.get('time_range', 'Time Range')}</th>
                        </tr>
                    </thead>
                    <tbody>
            '''
            
            for (device, type_label), stats in summary.items():
                html += f'''
                        <tr>
                            <td style="padding: 8px; border: 1px solid #ddd;"><strong>{device}</strong></td>
                            <td style="padding: 8px; border: 1px solid #ddd;">{type_label}</td>
                            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;"><strong style="color: #dc3545;">{stats['count']}</strong></td>
                            <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">{stats['max_value']:.2f}</td>
                            <td style="padding: 8px; border: 1px solid #ddd; font-size: 0.9em;">{stats['first_time']} - {stats['last_time']}</td>
                        </tr>
                '''
            
            html += '''
                    </tbody>
                </table>
                <p style="margin: 10px 0 0 0; font-size: 0.9em; color: #856404;">
                    &#128202; {tip_text}
                </p>
            </div>
            '''.format(tip_text=self.t.get('refer_to_ebs_charts_hint', 
                '💡 提示：警告的时间分布可在下方"EBS 专业图表"部分查看 → 点击"EBS 瓶颈分析"和"EBS 时间序列分析"图表' if self.language == 'zh' 
                else '💡 Tip: View warning time distribution in "EBS Professional Charts" section below → Click "EBS Bottleneck Analysis" and "EBS Time Series Analysis" charts'))
            
            # Display detailed list (Top 20) as table
            display_warnings = warnings[:20]
            html += f'<h4>{self.t.get("detailed_warnings", "Detailed Warnings")} ({"Top 20" if len(warnings) > 20 else "All"} / {len(warnings)})</h4>'
            html += '''
            <table style="width: 100%; border-collapse: collapse; margin: 15px 0; background: white;">
                <thead>
                    <tr style="background: #f8f9fa;">
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">#</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">{device}</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">{type}</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">{value}</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: center;">{time}</th>
                    </tr>
                </thead>
                <tbody>
            '''.format(
                device=self.t.get('device', 'Device'),
                type=self.t.get('type', 'Type'),
                value=self.t.get('value', 'Value'),
                time=self.t.get('time', 'Time')
            )
            
            for idx, warning in enumerate(display_warnings, 1):
                color = "#dc3545" if warning['type'] == 'High Utilization' else "#fd7e14"
                unit = "%" if warning['type'] == 'High Utilization' else ""
                html += f'''
                <tr style="border-bottom: 1px solid #eee;">
                    <td style="padding: 8px; border: 1px solid #ddd; color: #999;">{idx}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>{warning['device']}</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd; color: {color};">{warning['type']}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;"><strong>{warning['value']}{unit}</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center; font-size: 0.9em;">{warning.get('data_time', warning['timestamp'])}</td>
                </tr>
                '''
            
            html += '</tbody></table>'
            
            if len(warnings) > 20:
                html += f'<p style="color: #6c757d; font-style: italic; margin-top: 10px;">... {self.t.get("and", "and")} {len(warnings) - 20} {self.t.get("more_warnings", "more warnings")}. {self.t.get("check_full_log", "Check full log for details")}: <code>{self.ebs_log_path}</code></p>'
        else:
            html += f'<p style="color: #28a745; font-weight: bold;">&#9989; {self.t["no_performance_anomaly"]}</p>'
        
        html += '</div>'
        
        # Layer 1: AWS EBS baseline data statistics
        html += f'''
            <div class="subsection">
                <h3>&#128200; {self.t['aws_ebs_baseline_stats']}</h3>
        '''
        
        if df is not None and not df.empty:
            # Get configured baseline values
            data_max_iops = self.config.get('DATA_VOL_MAX_IOPS', 'N/A')
            data_max_throughput = self.config.get('DATA_VOL_MAX_THROUGHPUT', 'N/A')
            accounts_max_iops = self.config.get('ACCOUNTS_VOL_MAX_IOPS', 'N/A')
            accounts_max_throughput = self.config.get('ACCOUNTS_VOL_MAX_THROUGHPUT', 'N/A')
            
            # Calculate actual usage statistics
            stats_data = {}
            
            # DATA Device AWS standard fields
            data_iops_col = [col for col in df.columns if col.startswith('data_') and col.endswith('_aws_standard_iops')]
            data_throughput_col = [col for col in df.columns if col.startswith('data_') and col.endswith('_aws_standard_throughput_mibs')]
            
            if data_iops_col:
                # Filter out noise values (< 10 IOPS) for Min calculation
                meaningful_data = df[df[data_iops_col[0]] >= 10][data_iops_col[0]]
                stats_data['DATA_IOPS_Min'] = meaningful_data.min() if len(meaningful_data) > 0 else 0
                stats_data['DATA_IOPS_Max'] = df[data_iops_col[0]].max()
                stats_data['DATA_IOPS_Avg'] = df[data_iops_col[0]].mean()
            
            if data_throughput_col:
                # Filter out noise values (< 1.0 MiB/s) for Min calculation
                meaningful_data = df[df[data_throughput_col[0]] >= 1.0][data_throughput_col[0]]
                stats_data['DATA_Throughput_Min'] = meaningful_data.min() if len(meaningful_data) > 0 else 0
                stats_data['DATA_Throughput_Max'] = df[data_throughput_col[0]].max()
                stats_data['DATA_Throughput_Avg'] = df[data_throughput_col[0]].mean()
            
            # ACCOUNTS Device AWS standard fields
            accounts_iops_col = [col for col in df.columns if col.startswith('accounts_') and col.endswith('_aws_standard_iops')]
            accounts_throughput_col = [col for col in df.columns if col.startswith('accounts_') and col.endswith('_aws_standard_throughput_mibs')]
            
            if accounts_iops_col:
                # Filter out noise values (< 10 IOPS) for Min calculation
                meaningful_data = df[df[accounts_iops_col[0]] >= 10][accounts_iops_col[0]]
                stats_data['ACCOUNTS_IOPS_Min'] = meaningful_data.min() if len(meaningful_data) > 0 else 0
                stats_data['ACCOUNTS_IOPS_Max'] = df[accounts_iops_col[0]].max()
                stats_data['ACCOUNTS_IOPS_Avg'] = df[accounts_iops_col[0]].mean()
            
            if accounts_throughput_col:
                # Filter out noise values (< 1.0 MiB/s) for Min calculation
                meaningful_data = df[df[accounts_throughput_col[0]] >= 1.0][accounts_throughput_col[0]]
                stats_data['ACCOUNTS_Throughput_Min'] = meaningful_data.min() if len(meaningful_data) > 0 else 0
                stats_data['ACCOUNTS_Throughput_Max'] = df[accounts_throughput_col[0]].max()
                stats_data['ACCOUNTS_Throughput_Avg'] = df[accounts_throughput_col[0]].mean()
            
            # Format values
            data_iops_min = self._format_stat_value(stats_data.get('DATA_IOPS_Min'), 0)
            data_iops_avg = self._format_stat_value(stats_data.get('DATA_IOPS_Avg'), 0)
            data_iops_max = self._format_stat_value(stats_data.get('DATA_IOPS_Max'), 0)
            data_tp_min = self._format_stat_value(stats_data.get('DATA_Throughput_Min'), 1)
            data_tp_avg = self._format_stat_value(stats_data.get('DATA_Throughput_Avg'), 1)
            data_tp_max = self._format_stat_value(stats_data.get('DATA_Throughput_Max'), 1)
            
            html += f'''
                <table style="width: 100%; border-collapse: collapse; margin-top: 15px; background: white;">
                    <thead>
                        <tr>
                            <th style="background: #E67E22; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['device']}</th>
                            <th style="background: #E67E22; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['metric']}</th>
                            <th style="background: #E67E22; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['baseline_config']}</th>
                            <th style="background: #E67E22; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['min']}</th>
                            <th style="background: #E67E22; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['avg']}</th>
                            <th style="background: #E67E22; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['max']}</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td rowspan="2" style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{self.t['data_device']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{self.t['iops']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{data_max_iops}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{data_iops_min}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{data_iops_avg}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{data_iops_max}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd;">{self.t['throughput_mibs']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{data_max_throughput}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{data_tp_min}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{data_tp_avg}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{data_tp_max}</td>
                        </tr>
            '''
            
            # If ACCOUNTS device data exists, add ACCOUNTS rows
            if accounts_iops_col or accounts_throughput_col:
                acc_iops_min = self._format_stat_value(stats_data.get('ACCOUNTS_IOPS_Min'), 0)
                acc_iops_avg = self._format_stat_value(stats_data.get('ACCOUNTS_IOPS_Avg'), 0)
                acc_iops_max = self._format_stat_value(stats_data.get('ACCOUNTS_IOPS_Max'), 0)
                acc_tp_min = self._format_stat_value(stats_data.get('ACCOUNTS_Throughput_Min'), 1)
                acc_tp_avg = self._format_stat_value(stats_data.get('ACCOUNTS_Throughput_Avg'), 1)
                acc_tp_max = self._format_stat_value(stats_data.get('ACCOUNTS_Throughput_Max'), 1)
                
                html += f'''
                        <tr>
                            <td rowspan="2" style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{self.t['accounts_device']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{self.t['iops']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{accounts_max_iops}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{acc_iops_min}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{acc_iops_avg}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{acc_iops_max}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd;">{self.t['throughput_mibs']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{accounts_max_throughput}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{acc_tp_min}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{acc_tp_avg}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{acc_tp_max}</td>
                        </tr>
                '''
            
            html += '''
                    </tbody>
                </table>
            '''
        else:
            html += f'<p style="color: #6c757d;">{self.t["no_aws_ebs_baseline"]}</p>'
        
        html += '</div>'
        
        # Second layer: iostat raw sampling data statistics
        html += f'''
            <div class="subsection">
                <h3>&#128200; {self.t["iostat_raw_sampling_stats"]}</h3>
        '''
        
        if df is not None and not df.empty:
            iostat_stats = {}
            
            # DATA Device iostat fields
            for metric in ['total_iops', 'total_throughput_mibs', 'util', 'avg_await']:
                data_col = [col for col in df.columns if col.startswith('data_') and col.endswith(f'_{metric}')]
                if data_col:
                    # Filter out noise values for Min calculation
                    if metric == 'total_iops':
                        meaningful_data = df[df[data_col[0]] >= 10][data_col[0]]  # >= 10 IOPS
                    elif metric == 'total_throughput_mibs':
                        meaningful_data = df[df[data_col[0]] >= 1.0][data_col[0]]  # >= 1.0 MiB/s
                    elif metric == 'util':
                        meaningful_data = df[df[data_col[0]] >= 1.0][data_col[0]]  # >= 1.0%
                    elif metric == 'avg_await':
                        meaningful_data = df[df[data_col[0]] >= 0.1][data_col[0]]  # >= 0.1 ms
                    else:
                        meaningful_data = df[df[data_col[0]] > 0][data_col[0]]
                    
                    iostat_stats[f'DATA_{metric}_Min'] = meaningful_data.min() if len(meaningful_data) > 0 else 0
                    iostat_stats[f'DATA_{metric}_Max'] = df[data_col[0]].max()
                    iostat_stats[f'DATA_{metric}_Avg'] = df[data_col[0]].mean()
            
            # ACCOUNTS Device iostat fields
            for metric in ['total_iops', 'total_throughput_mibs', 'util', 'avg_await']:
                accounts_col = [col for col in df.columns if col.startswith('accounts_') and col.endswith(f'_{metric}')]
                if accounts_col:
                    # Filter out noise values for Min calculation
                    if metric == 'total_iops':
                        meaningful_data = df[df[accounts_col[0]] >= 10][accounts_col[0]]  # >= 10 IOPS
                    elif metric == 'total_throughput_mibs':
                        meaningful_data = df[df[accounts_col[0]] >= 1.0][accounts_col[0]]  # >= 1.0 MiB/s
                    elif metric == 'util':
                        meaningful_data = df[df[accounts_col[0]] >= 1.0][accounts_col[0]]  # >= 1.0%
                    elif metric == 'avg_await':
                        meaningful_data = df[df[accounts_col[0]] >= 0.1][accounts_col[0]]  # >= 0.1 ms
                    else:
                        meaningful_data = df[df[accounts_col[0]] > 0][accounts_col[0]]
                    
                    iostat_stats[f'ACCOUNTS_{metric}_Min'] = meaningful_data.min() if len(meaningful_data) > 0 else 0
                    iostat_stats[f'ACCOUNTS_{metric}_Max'] = df[accounts_col[0]].max()
                    iostat_stats[f'ACCOUNTS_{metric}_Avg'] = df[accounts_col[0]].mean()
            
            html += f'''
                <table style="width: 100%; border-collapse: collapse; margin-top: 15px; background: white;">
                    <thead>
                        <tr>
                            <th style="background: #D35400; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['device']}</th>
                            <th style="background: #D35400; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['metric']}</th>
                            <th style="background: #D35400; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['min']}</th>
                            <th style="background: #D35400; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['avg']}</th>
                            <th style="background: #D35400; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['max']}</th>
                        </tr>
                    </thead>
                    <tbody>
            '''
            
            # DATA Device data
            if any(k.startswith('DATA_') for k in iostat_stats.keys()):
                d_iops_min = self._format_stat_value(iostat_stats.get('DATA_total_iops_Min'), 0)
                d_iops_avg = self._format_stat_value(iostat_stats.get('DATA_total_iops_Avg'), 0)
                d_iops_max = self._format_stat_value(iostat_stats.get('DATA_total_iops_Max'), 0)
                d_tp_min = self._format_stat_value(iostat_stats.get('DATA_total_throughput_mibs_Min'), 1)
                d_tp_avg = self._format_stat_value(iostat_stats.get('DATA_total_throughput_mibs_Avg'), 1)
                d_tp_max = self._format_stat_value(iostat_stats.get('DATA_total_throughput_mibs_Max'), 1)
                d_util_min = self._format_stat_value(iostat_stats.get('DATA_util_Min'), 1)
                d_util_avg = self._format_stat_value(iostat_stats.get('DATA_util_Avg'), 1)
                d_util_max = self._format_stat_value(iostat_stats.get('DATA_util_Max'), 1)
                d_lat_min = self._format_stat_value(iostat_stats.get('DATA_avg_await_Min'), 2)
                d_lat_avg = self._format_stat_value(iostat_stats.get('DATA_avg_await_Avg'), 2)
                d_lat_max = self._format_stat_value(iostat_stats.get('DATA_avg_await_Max'), 2)
                
                html += f'''
                        <tr>
                            <td rowspan="4" style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{self.t['data_device']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{self.t['iops']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{d_iops_min}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{d_iops_avg}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{d_iops_max}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd;">{self.t['throughput_mibs']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{d_tp_min}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{d_tp_avg}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{d_tp_max}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd;">{self.t['utilization_pct']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{d_util_min}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{d_util_avg}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{d_util_max}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd;">{self.t['latency_ms']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{d_lat_min}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{d_lat_avg}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{d_lat_max}</td>
                        </tr>
                '''
            
            # ACCOUNTS Device data
            if any(k.startswith('ACCOUNTS_') for k in iostat_stats.keys()):
                a_iops_min = self._format_stat_value(iostat_stats.get('ACCOUNTS_total_iops_Min'), 0)
                a_iops_avg = self._format_stat_value(iostat_stats.get('ACCOUNTS_total_iops_Avg'), 0)
                a_iops_max = self._format_stat_value(iostat_stats.get('ACCOUNTS_total_iops_Max'), 0)
                a_tp_min = self._format_stat_value(iostat_stats.get('ACCOUNTS_total_throughput_mibs_Min'), 1)
                a_tp_avg = self._format_stat_value(iostat_stats.get('ACCOUNTS_total_throughput_mibs_Avg'), 1)
                a_tp_max = self._format_stat_value(iostat_stats.get('ACCOUNTS_total_throughput_mibs_Max'), 1)
                a_util_min = self._format_stat_value(iostat_stats.get('ACCOUNTS_util_Min'), 1)
                a_util_avg = self._format_stat_value(iostat_stats.get('ACCOUNTS_util_Avg'), 1)
                a_util_max = self._format_stat_value(iostat_stats.get('ACCOUNTS_util_Max'), 1)
                a_lat_min = self._format_stat_value(iostat_stats.get('ACCOUNTS_avg_await_Min'), 2)
                a_lat_avg = self._format_stat_value(iostat_stats.get('ACCOUNTS_avg_await_Avg'), 2)
                a_lat_max = self._format_stat_value(iostat_stats.get('ACCOUNTS_avg_await_Max'), 2)
                
                html += f'''
                        <tr>
                            <td rowspan="4" style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{self.t['accounts_device']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{self.t['iops']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{a_iops_min}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{a_iops_avg}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{a_iops_max}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd;">{self.t['throughput_mibs']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{a_tp_min}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{a_tp_avg}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{a_tp_max}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd;">{self.t['utilization_pct']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{a_util_min}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{a_util_avg}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{a_util_max}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd;">{self.t['latency_ms']}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{a_lat_min}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{a_lat_avg}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{a_lat_max}</td>
                        </tr>
                '''
            
            html += '''
                    </tbody>
                </table>
            '''
        else:
            html += f'<p style="color: #6c757d;">{self.t["no_iostat_data"]}</p>'
        
        html += '</div>'
        
        html += '''
        </div>
        '''
        
        return html
    def generate_html_report(self):
        """Generate HTML report - using safe field access"""
        try:
            df = pd.read_csv(self.performance_csv)
            
            html_content = self._generate_html_content(df)
            
            output_file = os.path.join(self.output_dir, f'performance_report_{self.language}_{os.environ.get("SESSION_TIMESTAMP")}.html')
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"✅ Enhanced HTML report generated: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"❌ HTML report generation failed: {e}")
            return None

    def _generate_config_status_section(self):
        """Generate configuration status check section"""
        ledger_status = f"✅ {self.t['configured']}" if self.config.get('LEDGER_DEVICE') else f"❌ {self.t['not_configured']}"
        accounts_status = f"✅ {self.t['configured']}" if DeviceManager.is_accounts_configured() else f"⚠️ {self.t['not_configured']}"
        blockchain_node = self.config.get('BLOCKCHAIN_NODE', 'General')
        
        accounts_note = ""
        if not DeviceManager.is_accounts_configured():
            accounts_note = f'<div class="warning"><strong>{self.t["note"]}:</strong> {self.t["accounts_not_configured_note"]}</div>'
        
        return f"""
        <div class="section">
            <h2>&#9881; {self.t['config_status_check']}</h2>
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px; background: white;">
                <thead>
                    <tr>
                        <th style="background: #34495E; color: white; padding: 12px;">{self.t['config_item']}</th>
                        <th style="background: #34495E; color: white; padding: 12px;">{self.t['status']}</th>
                        <th style="background: #34495E; color: white; padding: 12px;">{self.t['value']}</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td style="padding: 10px; border: 1px solid #ddd;">{self.t['blockchain_node_type']}</td><td style="padding: 10px; border: 1px solid #ddd;">&#9989; {self.t['configured']}</td><td style="padding: 10px; border: 1px solid #ddd;">{blockchain_node}</td></tr>
                    <tr><td style="padding: 10px; border: 1px solid #ddd;">{self.t['data_device']}</td><td style="padding: 10px; border: 1px solid #ddd;">{ledger_status}</td><td style="padding: 10px; border: 1px solid #ddd;">{self.config.get('LEDGER_DEVICE', 'N/A')}</td></tr>
                    <tr><td style="padding: 10px; border: 1px solid #ddd;">{self.t['accounts_device']}</td><td style="padding: 10px; border: 1px solid #ddd;">{accounts_status}</td><td style="padding: 10px; border: 1px solid #ddd;">{self.config.get('ACCOUNTS_DEVICE', 'N/A')}</td></tr>
                    <tr><td style="padding: 10px; border: 1px solid #ddd;">{self.t['data_volume_type']}</td><td style="padding: 10px; border: 1px solid #ddd;">{'&#9989; ' + self.t['configured'] if self.config.get('DATA_VOL_TYPE') else '&#9888; ' + self.t['not_configured']}</td><td style="padding: 10px; border: 1px solid #ddd;">{self.config.get('DATA_VOL_TYPE', 'N/A')}</td></tr>
                    <tr><td style="padding: 10px; border: 1px solid #ddd;">{self.t['accounts_volume_type']}</td><td style="padding: 10px; border: 1px solid #ddd;">{'&#9989; ' + self.t['configured'] if self.config.get('ACCOUNTS_VOL_TYPE') else '&#9888; ' + self.t['not_configured']}</td><td style="padding: 10px; border: 1px solid #ddd;">{self.config.get('ACCOUNTS_VOL_TYPE', 'N/A')}</td></tr>
                </tbody>
            </table>
            {accounts_note}
        </div>
        """
    
    def _generate_monitoring_overhead_section(self):
        """Generate monitoring overhead section - enhanced with full resource analysis"""
        overhead_data = self.overhead_data  # Use cached data instead of reloading
        
        if overhead_data:
            # Monitoring process resources
            monitoring_cpu_avg = overhead_data.get('monitoring_cpu_percent_avg', 0)
            monitoring_memory_percent_avg = overhead_data.get('monitoring_memory_percent_avg', 0)
            monitoring_memory_mb_avg = overhead_data.get('monitoring_memory_mb_avg', 0)
            monitoring_process_count = overhead_data.get('monitoring_process_count_avg', 0)
            
            # Blockchain node resources
            blockchain_cpu_avg = overhead_data.get('blockchain_cpu_percent_avg', 0)
            blockchain_memory_percent_avg = overhead_data.get('blockchain_memory_percent_avg', 0)
            blockchain_memory_mb_avg = overhead_data.get('blockchain_memory_mb_avg', 0)
            blockchain_process_count = overhead_data.get('blockchain_process_count_avg', 0)
            
            # System resources
            system_cpu_cores = overhead_data.get('system_cpu_cores_avg', 0)
            system_memory_gb = overhead_data.get('system_memory_gb_avg', 0)
            system_cpu_usage_avg = overhead_data.get('system_cpu_usage_avg', 0)
            system_memory_usage_avg = overhead_data.get('system_memory_usage_avg', 0)
            
            # Resource ratio
            monitoring_cpu_ratio = overhead_data.get('monitoring_cpu_ratio', 0) * 100
            monitoring_memory_ratio = overhead_data.get('monitoring_memory_ratio', 0) * 100
            blockchain_cpu_ratio = overhead_data.get('blockchain_cpu_ratio', 0) * 100
            blockchain_memory_ratio = overhead_data.get('blockchain_memory_ratio', 0) * 100
            
            # Currently used I/O monitoring fields
            monitoring_iops_avg = overhead_data.get('monitoring_iops_avg', 0)
            monitoring_iops_max = overhead_data.get('monitoring_iops_max', 0)
            monitoring_throughput_avg = overhead_data.get('monitoring_throughput_mibs_avg', 0)
            monitoring_throughput_max = overhead_data.get('monitoring_throughput_mibs_max', 0)
            
            # Format to two decimal places
            format_num = lambda x: f"{x:.2f}"
            
            section_html = f"""
            <div class="section">
                <h2>&#128202; {self.t['monitoring_overhead_comprehensive_analysis']}</h2>
                
                <div class="info-card">
                    <h3>{self.t['system_resource_overview']}</h3>
                    <table class="data-table">
                        <tr>
                            <th>{self.t['metric_label']}</th>
                            <th>{self.t['value_label']}</th>
                        </tr>
                        <tr>
                            <td>{self.t['cpu_cores']}</td>
                            <td>{int(system_cpu_cores)}</td>
                        </tr>
                        <tr>
                            <td>{self.t['total_memory']}</td>
                            <td>{format_num(system_memory_gb)} GB</td>
                        </tr>
                        <tr>
                            <td>{self.t['avg_cpu_usage']}</td>
                            <td>{format_num(system_cpu_usage_avg)}%</td>
                        </tr>
                        <tr>
                            <td>{self.t['avg_memory_usage']}</td>
                            <td>{format_num(system_memory_usage_avg)}%</td>
                        </tr>
                    </table>
                </div>
                
                <div class="info-card">
                    <h3>{self.t['resource_usage_comparison']}</h3>
                    <table class="data-table">
                        <tr>
                            <th>{self.t['resource_type']}</th>
                            <th>{self.t['monitoring_system']}</th>
                            <th>{self.t['blockchain_node']}</th>
                            <th>{self.t['other_processes']}</th>
                        </tr>
                        <tr>
                            <td>{self.t['cpu_usage_rate']}</td>
                            <td>{format_num(monitoring_cpu_avg)}% ({format_num(monitoring_cpu_ratio)}%)</td>
                            <td>{format_num(blockchain_cpu_avg)}% ({format_num(blockchain_cpu_ratio)}%)</td>
                            <td>{format_num(max(0, system_cpu_usage_avg - monitoring_cpu_avg - blockchain_cpu_avg))}%</td>
                        </tr>
                        <tr>
                            <td>{self.t['memory_usage_rate']}</td>
                            <td>{format_num(monitoring_memory_percent_avg)}%</td>
                            <td>{format_num(blockchain_memory_percent_avg)}%</td>
                            <td>{format_num(max(0, system_memory_usage_avg - monitoring_memory_percent_avg - blockchain_memory_percent_avg))}%</td>
                        </tr>
                        <tr>
                            <td>{self.t['memory_usage_amount']}</td>
                            <td>{format_num(monitoring_memory_mb_avg)} MB</td>
                            <td>{format_num(blockchain_memory_mb_avg/1024)} GB</td>
                            <td>{format_num(system_memory_gb*1024 - monitoring_memory_mb_avg - blockchain_memory_mb_avg)} MB</td>
                        </tr>
                        <tr>
                            <td>{self.t['process_count']}</td>
                            <td>{int(monitoring_process_count)}</td>
                            <td>{int(blockchain_process_count)}</td>
                            <td>N/A</td>
                        </tr>
                    </table>
                    <p class="note">{self.t['percentage_note']}</p>
                </div>
                
                <div class="info-card">
                    <h3>{self.t['monitoring_io_overhead']}</h3>
                    <table class="data-table">
                        <tr>
                            <th>{self.t['metric_label']}</th>
                            <th>{self.t['average']}</th>
                            <th>{self.t['maximum']}</th>
                        </tr>
                        <tr>
                            <td>{self.t['iops']}</td>
                            <td>{format_num(monitoring_iops_avg)}</td>
                            <td>{format_num(monitoring_iops_max)}</td>
                        </tr>
                        <tr>
                            <td>{self.t['throughput_mibs']}</td>
                            <td>{format_num(monitoring_throughput_avg)}</td>
                            <td>{format_num(monitoring_throughput_max)}</td>
                        </tr>
                    </table>
                </div>
                
                <div class="conclusion">
                    <h3>&#128221; {self.t['monitoring_overhead_conclusion']}</h3>
                    <p>{self.t['monitoring_resource_analysis']}</p>
                    <ul>
                        <li>{self.t['cpu_overhead']}: {format_num(monitoring_cpu_ratio)}%</li>
                        <li>{self.t['memory_overhead']}: {format_num(monitoring_memory_percent_avg)}% ({format_num(monitoring_memory_mb_avg)} MB)</li>
                        <li>{self.t['io_overhead']}: {format_num(monitoring_iops_avg)} {self.t['iops']}</li>
                    </ul>
                    
                    <p>{self.t['blockchain_resource_analysis']}</p>
                    <ul>
                        <li>{self.t['cpu_usage']}: {format_num(blockchain_cpu_ratio)}%</li>
                        <li>{self.t['memory_usage']}: {format_num(blockchain_memory_percent_avg)}% ({format_num(blockchain_memory_mb_avg/1024)} GB)</li>
                    </ul>
                    
                    <p class="{'warning' if monitoring_cpu_avg > 5 else 'success'}">
                        {self.t['monitoring_impact']} 
                        {'<strong>' + self.t['significant'] + '</strong> (' + self.t['monitoring_cpu_exceeds_5'] + ')' if monitoring_cpu_avg > 5 else '<strong>' + self.t['minor'] + '</strong> (' + self.t['monitoring_cpu_below_5'] + ')'}
                    </p>
                </div>
            </div>
            """
        else:
            section_html = f"""
            <div class="section">
                <h2>&#128202; {self.t['monitoring_overhead_comprehensive_analysis']}</h2>
                <div class="warning">
                    <h4>&#9888; {self.t['monitoring_data_unavailable']}</h4>
                    <p>{self.t['monitoring_data_not_found']}</p>
                    <p><strong>{self.t['expected_file']}</strong>: <code>logs/monitoring_overhead_YYYYMMDD_HHMMSS.csv</code></p>
                </div>
                <div class="info">
                    <h4>&#128161; {self.t['how_to_enable']}</h4>
                    <p>{self.t['monitoring_integrated']}</p>
                    <p>{self.t['check_config']}</p>
                    <ul>
                        <li>{self.t['ensure_variable_set']}</li>
                        <li>{self.t['ensure_function_calls']}</li>
                        <li>{self.t['check_permissions']}</li>
                    </ul>
                </div>
            </div>
            """
            
        return section_html

    def _generate_monitoring_overhead_detailed_section(self):
        """Generate detailed monitoring overhead analysis section"""
        overhead_data = self.overhead_data  # Use cached data instead of reloading
        
        if overhead_data and os.path.exists(os.path.join(self.output_dir, "monitoring_overhead_analysis.png")):
            # Generate resource usage trend charts
            self._generate_resource_usage_charts()
            
            section_html = f"""
            <div class="section">
                <h2>&#128200; {self.t['monitoring_overhead_detailed']}</h2>
                
                <div class="info-card">
                    <h3>&#128202; {self.t['resource_usage_trends']}</h3>
                    <div class="chart-container">
                        <img src="monitoring_overhead_analysis.png" alt="{self.t['monitoring_overhead_analysis']}" class="chart">
                    </div>
                    <div class="chart-info">
                        <p>{self.t['chart_shows_resource_usage_trend']}:</p>
                        <ul>
                            <li><strong>{self.t['monitoring_system_resource_usage']}</strong>: {self.t['cpu_memory_io_overhead_changes']}</li>
                            <li><strong>{self.t['blockchain_node_resource_usage']}</strong>: {self.t['cpu_memory_usage_trends']}</li>
                            <li><strong>{self.t['total_system_resource_usage']}</strong>: {self.t['cpu_memory_usage_entire_system']}</li>
                        </ul>
                    </div>
                </div>
                
                <div class="info-card">
                    <h3>&#128202; {self.t['resource_proportion_chart']}</h3>
                    <div class="chart-container">
                        <img src="resource_distribution_chart.png" alt="{self.t['resource_distribution_image']}" class="chart">
                    </div>
                    <div class="chart-info">
                        <p>{self.t['chart_shows_component_resources']}</p>
                        <ul>
                            <li><strong>{self.t['monitoring_system']}</strong>: {self.t['all_monitoring_processes']}</li>
                            <li><strong>{self.t['blockchain_node']}</strong>: {self.t['blockchain_related_processes']}</li>
                            <li><strong>{self.t['other_processes']}</strong>: {self.t['other_system_processes']}</li>
                        </ul>
                    </div>
                </div>
                
                <div class="info-card">
                    <h3>&#128202; {self.t['monitoring_performance_chart']}</h3>
                    <div class="chart-container">
                        <img src="monitoring_impact_chart.png" alt="{self.t['monitoring_impact_image']}" class="chart">
                    </div>
                    <div class="chart-info">
                        <p>{self.t['chart_analyzes_correlation']}</p>
                        <ul>
                            <li><strong>{self.t['monitoring_cpu_vs_qps']}</strong>: {self.t['monitoring_cpu_qps_relationship']}</li>
                            <li><strong>{self.t['monitoring_io_vs_ebs']}</strong>: {self.t['monitoring_io_ebs_relationship']}</li>
                        </ul>
                    </div>
                </div>
            </div>
            """
        else:
            section_html = f"""
            <div class="section">
                <h2>&#128200; {self.t['monitoring_overhead_detailed']}</h2>
                <div class="warning">
                    <h4>&#9888; {self.t['monitoring_detailed_unavailable']}</h4>
                    <p>{self.t['monitoring_file_not_found']}</p>
                    <ul>
                        <li>{self.t['overhead_csv_generated']}</li>
                        <li>{self.t['chart_script_executed']}</li>
                        <li>{self.t['output_dir_permissions']}</li>
                    </ul>
                </div>
                <div class="info">
                    <h4>&#128161; {self.t['how_to_generate_charts']}</h4>
                    <p>{self.t['use_command_to_generate']}</p>
                    <pre><code>python3 visualization/performance_visualizer.py --performance-csv logs/performance_data.csv --overhead-csv logs/monitoring_overhead.csv --output-dir reports</code></pre>
                </div>
            </div>
            """
            
        return section_html
        
    def _generate_resource_usage_charts(self):
        """Generate resource usage trend charts"""
        try:
            if not self.overhead_csv or not os.path.exists(self.overhead_csv):
                return
                
            df = pd.read_csv(self.overhead_csv)
            if df.empty:
                return
                
            # Resource distribution pie chart
            self._generate_resource_distribution_chart(df)
            
            # Monitoring impact analysis chart
            if self.performance_csv and os.path.exists(self.performance_csv):
                self._generate_monitoring_impact_chart(df)
                
        except Exception as e:
            print(f"Error generating resource usage charts: {e}")
            
    def _generate_resource_distribution_chart(self, df):
        """Generate resource distribution chart - 3x2 layout (using actual available data)"""
        try:
            
            UnifiedChartStyle.setup_matplotlib()
            
            # Read CPU data
            blockchain_cpu = df['blockchain_cpu'].mean() if 'blockchain_cpu' in df.columns else 0
            monitoring_cpu = df['monitoring_cpu'].mean() if 'monitoring_cpu' in df.columns else 0
            system_cpu_cores = df['system_cpu_cores'].mean() if 'system_cpu_cores' in df.columns else 96
            
            # Read Memory data - using basic fields
            blockchain_memory_mb = df['blockchain_memory_mb'].mean() if 'blockchain_memory_mb' in df.columns else 0
            monitoring_memory_mb = df['monitoring_memory_mb'].mean() if 'monitoring_memory_mb' in df.columns else 0
            system_memory_gb = df['system_memory_gb'].mean() if 'system_memory_gb' in df.columns else 739.70
            
            # Read basic memory data from performance CSV (unit: MB, needs conversion to GB)
            mem_used_mb = 0
            mem_total_mb = system_memory_gb * 1024
            if self.performance_csv and os.path.exists(self.performance_csv):
                try:
                    perf_df = pd.read_csv(self.performance_csv, usecols=['mem_used', 'mem_total'])
                    mem_used_mb = perf_df['mem_used'].mean() if 'mem_used' in perf_df.columns else 0
                    mem_total_mb = perf_df['mem_total'].mean() if 'mem_total' in perf_df.columns else system_memory_gb * 1024
                except Exception as e:
                    print(f"⚠️ {self.t['read_memory_data_failed']}: {e}")
            
            # Convert to GB
            mem_used_gb = mem_used_mb / 1024
            mem_total_gb = mem_total_mb / 1024
            
            # Read Network data
            net_total_gbps = 0
            network_max_gbps = 25
            if self.performance_csv and os.path.exists(self.performance_csv):
                try:
                    perf_df = pd.read_csv(self.performance_csv, usecols=['net_total_gbps'])
                    net_total_gbps = perf_df['net_total_gbps'].mean() if 'net_total_gbps' in perf_df.columns else 0
                    network_max_gbps = float(os.getenv('NETWORK_MAX_BANDWIDTH_GBPS', '25'))
                except Exception as e:
                    print(f"⚠️ {self.t['read_network_data_failed']}: {e}")
            
            # Calculate derived metrics
            blockchain_cores = blockchain_cpu / 100 if blockchain_cpu > 0 else 0
            monitoring_cores = monitoring_cpu / 100 if monitoring_cpu > 0 else 0
            idle_cores = max(0, system_cpu_cores - blockchain_cores - monitoring_cores)
            
            blockchain_memory_gb = blockchain_memory_mb / 1024
            monitoring_memory_gb = monitoring_memory_mb / 1024
            mem_free_gb = max(0, mem_total_gb - mem_used_gb)
            
            network_used_gbps = net_total_gbps
            network_available_gbps = max(0, network_max_gbps - net_total_gbps)
            network_utilization = (net_total_gbps / network_max_gbps * 100) if network_max_gbps > 0 else 0
            
            # Create 3x2 layout
            fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6)) = plt.subplots(3, 2, figsize=(16, 18))
            fig.suptitle('System Resource Distribution Analysis', 
                        fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], fontweight='bold', y=0.995)
            
            # Subplot 1: CPU Core Usage
            cpu_sizes = [blockchain_cores, monitoring_cores, idle_cores]
            cpu_labels = [f'Blockchain\n{blockchain_cores:.2f} cores',
                         f'Monitoring\n{monitoring_cores:.2f} cores',
                         f'Idle\n{idle_cores:.2f} cores']
            cpu_colors = [UnifiedChartStyle.COLORS['data_primary'], UnifiedChartStyle.COLORS['warning'],
                         UnifiedChartStyle.COLORS['success']]
            wedges1, texts1, autotexts1 = ax1.pie(cpu_sizes, labels=cpu_labels, colors=cpu_colors,
                                                   autopct='%1.1f%%', startangle=45, labeldistance=1.15,
                                                   textprops={'fontsize': UnifiedChartStyle.FONT_CONFIG['legend_size']})
            ax1.set_title(f'CPU Core Usage (Total: {system_cpu_cores:.0f} cores)', 
                         fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=15)
            for autotext in autotexts1:
                autotext.set_fontsize(UnifiedChartStyle.FONT_CONFIG['text_size'])
                autotext.set_color('white')
                autotext.set_weight('bold')
            
            # Subplot 2: Memory Usage Distribution
            mem_sizes = [blockchain_memory_gb, monitoring_memory_gb, mem_free_gb]
            mem_labels = [f'Blockchain\n{blockchain_memory_gb:.2f} GB',
                         f'Monitoring\n{monitoring_memory_gb:.2f} GB',
                         f'Free\n{mem_free_gb:.2f} GB']
            mem_colors = [UnifiedChartStyle.COLORS['data_primary'], UnifiedChartStyle.COLORS['warning'],
                         UnifiedChartStyle.COLORS['success']]
            wedges2, texts2, autotexts2 = ax2.pie(mem_sizes, labels=mem_labels, colors=mem_colors,
                                                   autopct='%1.1f%%', startangle=45, labeldistance=1.15,
                                                   textprops={'fontsize': UnifiedChartStyle.FONT_CONFIG['legend_size']})
            ax2.set_title(f'Memory Usage Distribution (Total: {mem_total_gb:.0f} GB)', 
                         fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=15)
            for autotext in autotexts2:
                autotext.set_fontsize(UnifiedChartStyle.FONT_CONFIG['text_size'])
                autotext.set_color('white')
                autotext.set_weight('bold')
            
            # Subplot 3: Memory Usage Comparison
            mem_categories = ['Blockchain', 'Monitoring', 'Free']
            mem_values = [blockchain_memory_gb, monitoring_memory_gb, mem_free_gb]
            mem_bar_colors = [UnifiedChartStyle.COLORS['data_primary'], UnifiedChartStyle.COLORS['warning'],
                             UnifiedChartStyle.COLORS['success']]
            bars3 = ax3.bar(mem_categories, mem_values, color=mem_bar_colors, alpha=0.7)
            ax3.set_ylabel('Memory (GB)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax3.set_title('Memory Usage Comparison', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=15)
            ax3.grid(True, alpha=0.3, axis='y')
            for bar, val in zip(bars3, mem_values):
                pct = (val / mem_total_gb * 100) if mem_total_gb > 0 else 0
                ax3.text(bar.get_x() + bar.get_width()/2, val + max(mem_values)*0.02, 
                        f'{val:.1f} GB\n({pct:.1f}%)', ha='center', fontsize=UnifiedChartStyle.FONT_CONFIG['text_size'])
            
            # Subplot 4: CPU Usage Comparison
            cpu_categories = ['Blockchain', 'Monitoring']
            cpu_values = [blockchain_cpu, monitoring_cpu]
            cpu_bar_colors = [UnifiedChartStyle.COLORS['data_primary'], UnifiedChartStyle.COLORS['warning']]
            bars4 = ax4.bar(cpu_categories, cpu_values, color=cpu_bar_colors, alpha=0.7)
            ax4.set_ylabel('CPU Usage (%)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax4.set_title('CPU Usage Comparison', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=15)
            ax4.grid(True, alpha=0.3, axis='y')
            for bar, val in zip(bars4, cpu_values):
                ax4.text(bar.get_x() + bar.get_width()/2, val + max(cpu_values)*0.02, 
                        f'{val:.2f}%', ha='center', fontsize=UnifiedChartStyle.FONT_CONFIG['text_size'])
            
            # Subplot 5: Network Bandwidth
            if net_total_gbps > 0:
                net_sizes = [network_used_gbps, network_available_gbps]
                net_labels = [f'Used\n{network_used_gbps:.2f} Gbps',
                             f'Available\n{network_available_gbps:.2f} Gbps']
                net_colors = [UnifiedChartStyle.COLORS['critical'], UnifiedChartStyle.COLORS['success']]
                wedges5, texts5, autotexts5 = ax5.pie(net_sizes, labels=net_labels, colors=net_colors,
                                                      autopct='%1.1f%%', startangle=45, labeldistance=1.15,
                                                      textprops={'fontsize': UnifiedChartStyle.FONT_CONFIG['legend_size']})
                ax5.set_title(f'Network Bandwidth (Max: {network_max_gbps:.0f} Gbps, Util: {network_utilization:.2f}%)', 
                             fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=15)
                for autotext in autotexts5:
                    autotext.set_fontsize(UnifiedChartStyle.FONT_CONFIG['text_size'])
                    autotext.set_color('white')
                    autotext.set_weight('bold')
            else:
                ax5.text(0.5, 0.5, 'Network Data\nUnavailable',
                        ha='center', va='center', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'],
                        bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.5))
                ax5.set_title('Network Bandwidth', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=15)
                ax5.axis('off')
            
            # Subplot 6: Resource Overhead Summary
            overhead_categories = ['CPU\nOverhead', 'Memory\nOverhead']
            total_cpu = blockchain_cpu + monitoring_cpu
            total_mem = blockchain_memory_gb + monitoring_memory_gb
            cpu_overhead_pct = (monitoring_cpu / total_cpu * 100) if total_cpu > 0 else 0
            mem_overhead_pct = (monitoring_memory_gb / total_mem * 100) if total_mem > 0 else 0
            overhead_values = [cpu_overhead_pct, mem_overhead_pct]
            overhead_colors = [UnifiedChartStyle.COLORS['warning'], UnifiedChartStyle.COLORS['info']]
            bars6 = ax6.bar(overhead_categories, overhead_values, color=overhead_colors, alpha=0.7)
            ax6.set_ylabel('Overhead (%)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax6.set_title('Monitoring Overhead Comparison', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=15)
            ax6.grid(True, alpha=0.3, axis='y')
            for bar, val in zip(bars6, overhead_values):
                ax6.text(bar.get_x() + bar.get_width()/2, val + max(overhead_values)*0.02, f'{val:.2f}%',
                        ha='center', fontsize=UnifiedChartStyle.FONT_CONFIG['text_size'])
            
            UnifiedChartStyle.apply_layout('auto')
            reports_dir = self.output_dir
            plt.savefig(os.path.join(reports_dir, 'resource_distribution_chart.png'), dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"✅ Generation complete: resource_distribution_chart.png")
            
        except Exception as e:
            print(f"❌ {self.t['resource_distribution_failed']}: {e}")
            import traceback
            traceback.print_exc()
    
    def _generate_monitoring_impact_chart(self, overhead_df):
        """Generate monitoring impact analysis chart - 3x2 layout (using actual available data)"""
        try:
            
            UnifiedChartStyle.setup_matplotlib()
            
            # Read performance data
            perf_df = pd.read_csv(self.performance_csv) if self.performance_csv and os.path.exists(self.performance_csv) else pd.DataFrame()
            
            # Calculate averages - from overhead CSV
            blockchain_cpu = overhead_df['blockchain_cpu'].mean() if 'blockchain_cpu' in overhead_df.columns else 0
            monitoring_cpu = overhead_df['monitoring_cpu'].mean() if 'monitoring_cpu' in overhead_df.columns else 0
            blockchain_memory_mb = overhead_df['blockchain_memory_mb'].mean() if 'blockchain_memory_mb' in overhead_df.columns else 0
            monitoring_memory_mb = overhead_df['monitoring_memory_mb'].mean() if 'monitoring_memory_mb' in overhead_df.columns else 0
            system_cpu_cores = overhead_df['system_cpu_cores'].mean() if 'system_cpu_cores' in overhead_df.columns else 96
            system_memory_gb = overhead_df['system_memory_gb'].mean() if 'system_memory_gb' in overhead_df.columns else 739.70
            
            # Get I/O data and basic memory data from performance CSV
            monitoring_iops = perf_df['monitoring_iops_per_sec'].mean() if not perf_df.empty and 'monitoring_iops_per_sec' in perf_df.columns else 0
            monitoring_throughput = perf_df['monitoring_throughput_mibs_per_sec'].mean() if not perf_df.empty and 'monitoring_throughput_mibs_per_sec' in perf_df.columns else 0
            
            # Use basic memory data from performance CSV (unit: MB, needs conversion to GB)
            mem_used_mb = perf_df['mem_used'].mean() if not perf_df.empty and 'mem_used' in perf_df.columns else 0
            mem_total_mb = perf_df['mem_total'].mean() if not perf_df.empty and 'mem_total' in perf_df.columns else system_memory_gb * 1024
            mem_usage_pct = perf_df['mem_usage'].mean() if not perf_df.empty and 'mem_usage' in perf_df.columns else 0
            
            # Convert to GB
            mem_used = mem_used_mb / 1024
            mem_total = mem_total_mb / 1024
            
            # Convert to cores and GB
            blockchain_cores = blockchain_cpu / 100
            monitoring_cores = monitoring_cpu / 100
            blockchain_memory_gb = blockchain_memory_mb / 1024
            monitoring_memory_gb = monitoring_memory_mb / 1024
            
            # Calculate proportions
            total_cpu = blockchain_cpu + monitoring_cpu
            cpu_overhead_pct = (monitoring_cpu / total_cpu * 100) if total_cpu > 0 else 0
            total_memory = blockchain_memory_gb + monitoring_memory_gb
            memory_overhead_pct = (monitoring_memory_gb / total_memory * 100) if total_memory > 0 else 0
            
            # Create 3x2 layout
            fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6)) = plt.subplots(3, 2, figsize=(16, 18))
            fig.suptitle('Monitoring Overhead Impact Analysis', 
                        fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], fontweight='bold', y=0.995)
            
            # Subplot 1: CPU Core Usage
            cpu_categories = ['Blockchain', 'Monitoring']
            cpu_values = [blockchain_cores, monitoring_cores]
            cpu_colors = [UnifiedChartStyle.COLORS['data_primary'], UnifiedChartStyle.COLORS['warning']]
            bars1 = ax1.bar(cpu_categories, cpu_values, color=cpu_colors, alpha=0.7)
            ax1.set_ylabel('CPU Cores', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax1.set_title(f'CPU Core Usage (Total: {system_cpu_cores:.0f} cores)', 
                         fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=15)
            ax1.grid(True, alpha=0.3, axis='y')
            for bar, val in zip(bars1, cpu_values):
                pct = (val / system_cpu_cores * 100) if system_cpu_cores > 0 else 0
                ax1.text(bar.get_x() + bar.get_width()/2, val + max(cpu_values)*0.02, 
                        f'{val:.2f}\n({pct:.1f}%)', ha='center', fontsize=UnifiedChartStyle.FONT_CONFIG['text_size'])
            
            # Subplot 2: Memory Usage
            mem_categories = ['Blockchain', 'Monitoring']
            mem_values = [blockchain_memory_gb, monitoring_memory_gb]
            mem_colors = [UnifiedChartStyle.COLORS['data_primary'], UnifiedChartStyle.COLORS['warning']]
            bars2 = ax2.bar(mem_categories, mem_values, color=mem_colors, alpha=0.7)
            ax2.set_ylabel('Memory (GB)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax2.set_title(f'Memory Usage (Total: {system_memory_gb:.1f} GB)', 
                         fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=15)
            ax2.grid(True, alpha=0.3, axis='y')
            for bar, val in zip(bars2, mem_values):
                pct = (val / system_memory_gb * 100) if system_memory_gb > 0 else 0
                ax2.text(bar.get_x() + bar.get_width()/2, val + max(mem_values)*0.02, 
                        f'{val:.2f}\n({pct:.1f}%)', ha='center', fontsize=UnifiedChartStyle.FONT_CONFIG['text_size'])
            
            # Subplot 3: Monitoring I/O Impact
            # Calculate I/O overhead percentage - use DeviceManager to dynamically get fields
            device_manager = DeviceManager(perf_df) if not perf_df.empty else None
            data_total_iops = 0
            accounts_total_iops = 0
            
            if device_manager:
                data_iops_field = device_manager.get_mapped_field('data_total_iops')
                if data_iops_field and data_iops_field in perf_df.columns:
                    data_total_iops = perf_df[data_iops_field].mean()
                
                if device_manager.is_accounts_configured():
                    accounts_iops_field = device_manager.get_mapped_field('accounts_total_iops')
                    if accounts_iops_field and accounts_iops_field in perf_df.columns:
                        accounts_total_iops = perf_df[accounts_iops_field].mean()
            
            total_system_iops = data_total_iops + accounts_total_iops
            io_overhead_pct = (monitoring_iops / total_system_iops * 100) if total_system_iops > 0 else 0
            
            if monitoring_iops > 0.01 or monitoring_throughput > 0.01:
                io_categories = ['IOPS/sec', 'Throughput\n(MiB/s)']
                io_values = [monitoring_iops, monitoring_throughput]
                io_colors = [UnifiedChartStyle.COLORS['data_primary'], UnifiedChartStyle.COLORS['success']]
                bars3 = ax3.bar(io_categories, io_values, color=io_colors, alpha=0.7)
                ax3.set_ylabel('Monitoring I/O', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax3.set_title('Monitoring I/O Operations', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=15)
                ax3.grid(True, alpha=0.3, axis='y')
                for bar, val in zip(bars3, io_values):
                    if max(io_values) > 0:
                        ax3.text(bar.get_x() + bar.get_width()/2, val + max(io_values)*0.02, 
                                f'{val:.3f}', ha='center', fontsize=UnifiedChartStyle.FONT_CONFIG['text_size'])
            else:
                ax3.text(0.5, 0.5, 'Monitoring I/O Data Unavailable\n(All values are 0)', 
                        ha='center', va='center', transform=ax3.transAxes,
                        fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'],
                        bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.3))
                ax3.set_title('Monitoring I/O Operations', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=15)
                ax3.set_xlabel('I/O Type', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax3.set_ylabel('Monitoring I/O', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax3.grid(True, alpha=0.3)
            
            # Subplot 4: System Memory Overview (using basic memory data)
            if mem_used > 0 and mem_total > 0:
                mem_free = mem_total - mem_used
                mem_overview_labels = ['Used', 'Free']
                mem_overview_values = [mem_used, mem_free]
                mem_overview_colors = [UnifiedChartStyle.COLORS['warning'], UnifiedChartStyle.COLORS['success']]
                bars4 = ax4.bar(mem_overview_labels, mem_overview_values, color=mem_overview_colors, alpha=0.7)
                ax4.set_ylabel('Memory (GB)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax4.set_title(f'System Memory Overview (Usage: {mem_usage_pct:.1f}%)', 
                             fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=15)
                ax4.grid(True, alpha=0.3, axis='y')
                for bar, val in zip(bars4, mem_overview_values):
                    pct = (val / mem_total * 100) if mem_total > 0 else 0
                    ax4.text(bar.get_x() + bar.get_width()/2, val + max(mem_overview_values)*0.02, 
                            f'{val:.1f} GB\n({pct:.1f}%)', ha='center', fontsize=UnifiedChartStyle.FONT_CONFIG['text_size'])
            else:
                ax4.text(0.5, 0.5, 'Memory Data\nNot Available', ha='center', va='center',
                        fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
                ax4.set_title('System Memory Overview', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=15)
                ax4.axis('off')
            
            # Subplot 5: CPU Overhead Trend
            if 'timestamp' in overhead_df.columns and 'monitoring_cpu' in overhead_df.columns and 'blockchain_cpu' in overhead_df.columns:
                if not pd.api.types.is_datetime64_any_dtype(overhead_df['timestamp']):
                    overhead_df['timestamp'] = pd.to_datetime(overhead_df['timestamp'])
                
                overhead_df['cpu_overhead_pct'] = (overhead_df['monitoring_cpu'] / 
                                                   (overhead_df['blockchain_cpu'] + overhead_df['monitoring_cpu']) * 100)
                ax5.plot(overhead_df['timestamp'], overhead_df['cpu_overhead_pct'], 
                        linewidth=2, color=UnifiedChartStyle.COLORS['warning'], alpha=0.7)
                ax5.axhline(y=overhead_df['cpu_overhead_pct'].mean(), color=UnifiedChartStyle.COLORS['critical'], 
                           linestyle='--', alpha=0.7, label=f'Average: {overhead_df["cpu_overhead_pct"].mean():.2f}%')
                ax5.set_ylabel('Overhead (%)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax5.set_title('CPU Overhead Trend Over Time', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=15)
                ax5.legend()
                ax5.grid(True, alpha=0.3)
                format_time_axis(ax5, overhead_df['timestamp'])
            else:
                ax5.text(0.5, 0.5, 'No Time Series Data', ha='center', va='center', 
                        fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
                ax5.axis('off')
            
            # Subplot 6: Monitoring Efficiency Summary
            summary_lines = [
                "Monitoring Overhead Summary:",
                "",
                f"CPU Overhead:     {cpu_overhead_pct:.2f}%",
                f"Memory Overhead:  {memory_overhead_pct:.2f}%",
                f"I/O Overhead:     {io_overhead_pct:.2f}%",
                "",
                "Absolute Values:",
                f"  CPU:        {monitoring_cores:.2f} cores",
                f"  Memory:     {monitoring_memory_gb:.2f} GB",
                f"  IOPS:       {monitoring_iops:.0f}",
                f"  Throughput: {monitoring_throughput:.2f} MiB/s",
                "",
                f"Efficiency Rating: {'Excellent' if cpu_overhead_pct < 1 else 'Good' if cpu_overhead_pct < 3 else 'Needs Optimization'}"
            ]
            summary_text = "\n".join(summary_lines)
            UnifiedChartStyle.add_text_summary(ax6, summary_text, 'Monitoring Efficiency Summary')
            
            UnifiedChartStyle.apply_layout('auto')
            reports_dir = self.output_dir
            plt.savefig(os.path.join(reports_dir, 'monitoring_impact_chart.png'), dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"✅ {self.t['generation_complete_monitoring']}")
            
        except Exception as e:
            print(f"❌ {self.t['monitoring_impact_failed']}: {e}")
            import traceback
            traceback.print_exc()
    
    def _generate_ebs_bottleneck_section(self):
        """Generate EBS bottleneck analysis section - enhanced version with multi-device and root cause analysis"""
        bottleneck_info = self._load_bottleneck_info()
        overhead_data = self.overhead_data  # Use cached data instead of reloading
        
        # Device type list
        device_types = ['data', 'accounts']
        device_labels = {'data': 'DATA', 'accounts': 'ACCOUNTS'}
        
        if bottleneck_info and 'ebs_bottlenecks' in bottleneck_info:
            ebs_bottlenecks = bottleneck_info['ebs_bottlenecks']
            
            # Group bottlenecks by device type
            device_bottlenecks = {}
            for bottleneck in ebs_bottlenecks:
                device_type = bottleneck.get('device_type', 'data').lower()
                if device_type not in device_bottlenecks:
                    device_bottlenecks[device_type] = []
                device_bottlenecks[device_type].append(bottleneck)
            
            # Generate device bottleneck HTML
            devices_html = ""
            for device_type in device_types:
                if device_type in device_bottlenecks and device_bottlenecks[device_type]:
                    # This device has bottlenecks
                    bottlenecks = device_bottlenecks[device_type]
                    
                    # Format bottleneck information
                    bottleneck_html = ""
                    for bottleneck in bottlenecks:
                        bottleneck_type = bottleneck.get('type', 'Unknown')
                        severity = bottleneck.get('severity', 'Medium')
                        details = bottleneck.get('details', {})
                        
                        # Format details
                        details_html = ""
                        for key, value in details.items():
                            details_html += f"<li><strong>{key}:</strong> {value}</li>"
                        
                        bottleneck_html += f"""
                        <div class="bottleneck-item severity-{severity.lower()}">
                            <h4>{bottleneck_type} <span class="severity">{severity}</span></h4>
                            <ul>
                                {details_html}
                            </ul>
                        </div>
                        """
                    
                    # Get monitoring overhead data for root cause analysis
                    root_cause_html = self._generate_bottleneck_root_cause_analysis(device_type, overhead_data)
                    
                    devices_html += f"""
                    <div class="device-bottleneck">
                        <h3>&#128192; {device_labels[device_type]}{self.t['device_bottleneck']}</h3>
                        <div class="bottleneck-container">
                            {bottleneck_html}
                        </div>
                        {root_cause_html}
                    </div>
                    """
                elif device_type == 'data':
                    # DATA device must be displayed even if no bottleneck
                    devices_html += f"""
                    <div class="device-bottleneck">
                        <h3>&#128192; {device_labels[device_type]}{self.t['device_label']}</h3>
                        <div class="success">
                            <h4>&#9989; {self.t['no_bottleneck_detected']}</h4>
                            <p>{device_labels[device_type]}{self.t['device_performance_good']}</p>
                        </div>
                    </div>
                    """
            
            section_html = f"""
            <div class="section">
                <h2>&#128192; {self.t['ebs_bottleneck_analysis']}</h2>
                {devices_html}
                <div class="note">
                    <p>{self.t['ebs_analysis_based_on']}</p>
                    <p>{self.t['root_cause_based_on']}</p>
                </div>
            </div>
            """
        else:
            section_html = f"""
            <div class="section">
                <h2>&#128192; {self.t['ebs_bottleneck_analysis']}</h2>
                <div class="success">
                    <h4>&#9989; {self.t['no_ebs_bottleneck_detected']}</h4>
                    <p>{self.t['no_ebs_bottleneck_found']}</p>
                </div>
            </div>
            """
            
        return section_html
        
    def _generate_bottleneck_root_cause_analysis(self, device_type, overhead_data):
        """Generate bottleneck root cause analysis HTML"""
        if not overhead_data:
            return f"""
            <div class="warning">
                <h4>&#9888; {self.t['cannot_perform_root_cause']}</h4>
                <p>{self.t['missing_overhead_data']}</p>
            </div>
            """
        
        # Get monitoring overhead data
        monitoring_iops_avg = overhead_data.get('monitoring_iops_avg', 0)
        monitoring_throughput_avg = overhead_data.get('monitoring_throughput_mibs_avg', 0)
        
        # Estimate monitoring overhead impact on EBS
        # Note: Monitoring system reads /proc virtual filesystem, IOPS usually < 0.01
        if monitoring_iops_avg > 1.0:  # Very high (abnormal)
            impact_level = self.t['high_label']
            impact_percent = min(90, monitoring_iops_avg * 50)  # 1 IOPS = 50%
        elif monitoring_iops_avg > 0.1:  # High
            impact_level = self.t['medium_label']
            impact_percent = min(50, monitoring_iops_avg * 100)  # 0.1 IOPS = 10%
        else:  # Normal (< 0.1 IOPS)
            impact_level = self.t['low_label']
            impact_percent = min(20, monitoring_iops_avg * 200)  # 0.01 IOPS = 2%
        
        # Generate different HTML based on impact level
        if impact_level == self.t['high_label']:
            return f"""
            <div class="root-cause-analysis warning">
                <h4>&#128269; {self.t['root_cause_significant_impact']}</h4>
                <p>{self.t['monitoring_impact_level']}: <strong>{impact_level} ({self.t['about']}{impact_percent:.1f}%)</strong></p>
                <ul>
                    <li>{self.t['monitoring_avg_iops']}: <strong>{monitoring_iops_avg:.2f}</strong></li>
                    <li>{self.t['monitoring_avg_throughput']}: <strong>{monitoring_throughput_avg:.2f} MiB/s</strong></li>
                </ul>
                <p class="recommendation">{self.t['recommendation']}: {self.t['reduce_monitoring_frequency']}{device_type.upper()}{self.t['device_impact_suffix']}</p>
            </div>
            """
        elif impact_level == self.t['medium_label']:
            return f"""
            <div class="root-cause-analysis info">
                <h4>&#128269; {self.t['root_cause_moderate_impact']}</h4>
                <p>{self.t['monitoring_impact_level']}: <strong>{impact_level} ({self.t['about']}{impact_percent:.1f}%)</strong></p>
                <ul>
                    <li>{self.t['monitoring_avg_iops']}: <strong>{monitoring_iops_avg:.2f}</strong></li>
                    <li>{self.t['monitoring_avg_throughput']}: <strong>{monitoring_throughput_avg:.2f} MiB/s</strong></li>
                </ul>
                <p class="recommendation">{self.t['recommendation']}: {self.t['monitoring_has_some_impact']}</p>
            </div>
            """
        else:
            return f"""
            <div class="root-cause-analysis success">
                <h4>&#128269; {self.t['root_cause_minor_impact']}</h4>
                <p>{self.t['monitoring_impact_level']}: <strong>{impact_level} ({self.t['about']}{impact_percent:.1f}%)</strong></p>
                <ul>
                    <li>{self.t['monitoring_avg_iops']}: <strong>{monitoring_iops_avg:.2f}</strong></li>
                    <li>{self.t['monitoring_avg_throughput']}: <strong>{monitoring_throughput_avg:.2f} MiB/s</strong></li>
                </ul>
                <p class="recommendation">{self.t['recommendation']}: {device_type.upper()}{self.t['bottleneck_from_workload']}</p>
            </div>
            """
    


    def _generate_overhead_data_table(self):
        """Generate complete monitoring overhead data table"""
        if not self.overhead_data:
            return f"""
            <h2>&#128202; {self.t['monitoring_overhead_breakdown']}</h2>
            <div class="warning">
                <h4>&#9888; {self.t['overhead_data_not_available']}</h4>
                <p>{self.t['overhead_file_not_found']}</p>
                <p><strong>{self.t['expected_file_label']}</strong>: <code>logs/monitoring_overhead_YYYYMMDD_HHMMSS.csv</code></p>
                <p><strong>{self.t['description_label']}</strong>: {self.t['overhead_auto_generated']}</p>
            </div>
            """
        
        try:
            # Generate detailed monitoring overhead table
            table_html = f"""
            <h2>&#128202; {self.t['monitoring_overhead_breakdown']}</h2>
            <div class="info">
                <h4>&#128202; {self.t['overhead_detailed_data']}</h4>
                <p>{self.t['data_shows_component_consumption']}</p>
            </div>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px; background: white;">
                <thead>
                    <tr>
                        <th style="background: #8E44AD; color: white; padding: 12px;">{self.t['monitoring_component_label']}</th>
                        <th style="background: #8E44AD; color: white; padding: 12px;">{self.t['avg_cpu_usage_label']}</th>
                        <th style="background: #8E44AD; color: white; padding: 12px;">{self.t['peak_cpu_usage_label']}</th>
                        <th style="background: #8E44AD; color: white; padding: 12px;">{self.t['avg_memory_usage_label']}</th>
                        <th style="background: #8E44AD; color: white; padding: 12px;">{self.t['peak_memory_usage_label']}</th>
                        <th style="background: #8E44AD; color: white; padding: 12px;">{self.t['avg_iops_label']}</th>
                        <th style="background: #8E44AD; color: white; padding: 12px;">{self.t['peak_iops_label']}</th>
                        <th style="background: #8E44AD; color: white; padding: 12px;">{self.t['avg_throughput_label']}</th>
                        <th style="background: #8E44AD; color: white; padding: 12px;">{self.t['data_completeness_label']}</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            # Monitoring component data (estimated based on overall monitoring data)
            # Calculate unified completeness
            data_completeness = self._calculate_data_completeness()
            
            monitoring_components = [
                {
                    'name': self.t['iostat_monitoring'],
                    'cpu_avg': self.overhead_data.get('monitoring_cpu_percent_avg', 0) * 0.3,
                    'cpu_max': self.overhead_data.get('monitoring_cpu_percent_max', 0) * 0.4,
                    'mem_avg': self.overhead_data.get('monitoring_memory_mb_avg', 0) * 0.2,
                    'mem_max': self.overhead_data.get('monitoring_memory_mb_max', 0) * 0.3,
                    'iops_avg': self.overhead_data.get('monitoring_iops_avg', 0) * 0.4,
                    'iops_max': self.overhead_data.get('monitoring_iops_max', 0) * 0.5,
                    'throughput_avg': self.overhead_data.get('monitoring_throughput_mibs_avg', 0) * 0.3,
                    'completeness': data_completeness
                },
                {
                    'name': self.t['sar_monitoring'],
                    'cpu_avg': self.overhead_data.get('monitoring_cpu_percent_avg', 0) * 0.2,
                    'cpu_max': self.overhead_data.get('monitoring_cpu_percent_max', 0) * 0.3,
                    'mem_avg': self.overhead_data.get('monitoring_memory_mb_avg', 0) * 0.15,
                    'mem_max': self.overhead_data.get('monitoring_memory_mb_max', 0) * 0.2,
                    'iops_avg': self.overhead_data.get('monitoring_iops_avg', 0) * 0.2,
                    'iops_max': self.overhead_data.get('monitoring_iops_max', 0) * 0.3,
                    'throughput_avg': self.overhead_data.get('monitoring_throughput_mibs_avg', 0) * 0.2,
                    'completeness': data_completeness
                },
                {
                    'name': self.t['vmstat_monitoring'],
                    'cpu_avg': self.overhead_data.get('monitoring_cpu_percent_avg', 0) * 0.1,
                    'cpu_max': self.overhead_data.get('monitoring_cpu_percent_max', 0) * 0.15,
                    'mem_avg': self.overhead_data.get('monitoring_memory_mb_avg', 0) * 0.1,
                    'mem_max': self.overhead_data.get('monitoring_memory_mb_max', 0) * 0.15,
                    'iops_avg': self.overhead_data.get('monitoring_iops_avg', 0) * 0.1,
                    'iops_max': self.overhead_data.get('monitoring_iops_max', 0) * 0.15,
                    'throughput_avg': self.overhead_data.get('monitoring_throughput_mibs_avg', 0) * 0.1,
                    'completeness': data_completeness
                },
                {
                    'name': self.t['data_collection_script'],
                    'cpu_avg': self.overhead_data.get('monitoring_cpu_percent_avg', 0) * 0.3,
                    'cpu_max': self.overhead_data.get('monitoring_cpu_percent_max', 0) * 0.4,
                    'mem_avg': self.overhead_data.get('monitoring_memory_mb_avg', 0) * 0.4,
                    'mem_max': self.overhead_data.get('monitoring_memory_mb_max', 0) * 0.5,
                    'iops_avg': self.overhead_data.get('monitoring_iops_avg', 0) * 0.2,
                    'iops_max': self.overhead_data.get('monitoring_iops_max', 0) * 0.3,
                    'throughput_avg': self.overhead_data.get('monitoring_throughput_mibs_avg', 0) * 0.3,
                    'completeness': data_completeness
                },
                {
                    'name': self.t['total_monitoring_overhead'],
                    'cpu_avg': self.overhead_data.get('monitoring_cpu_percent_avg', 0),
                    'cpu_max': self.overhead_data.get('monitoring_cpu_percent_max', 0),
                    'mem_avg': self.overhead_data.get('monitoring_memory_mb_avg', 0),
                    'mem_max': self.overhead_data.get('monitoring_memory_mb_max', 0),
                    'iops_avg': self.overhead_data.get('monitoring_iops_avg', 0),
                    'iops_max': self.overhead_data.get('monitoring_iops_max', 0),
                    'throughput_avg': self.overhead_data.get('monitoring_throughput_mibs_avg', 0),
                    'completeness': data_completeness
                }
            ]
            
            for i, component in enumerate(monitoring_components):
                # Set style based on whether it's a total row
                if component['name'] == self.t['total_monitoring_overhead']:
                    row_style = 'background: #f0f8ff; font-weight: bold; border-top: 2px solid #007bff;'
                else:
                    row_style = 'background: white;' if i % 2 == 0 else 'background: #f8f9fa;'
                
                # Data completeness color
                completeness_color = 'green' if component['completeness'] > 95 else 'orange' if component['completeness'] > 90 else 'red'
                
                table_html += f"""
                <tr style="{row_style}">
                    <td style="padding: 10px; border: 1px solid #ddd;">{component['name']}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{component['cpu_avg']:.2f}%</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{component['cpu_max']:.2f}%</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{component['mem_avg']:.1f} MB</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{component['mem_max']:.1f} MB</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{self._format_monitoring_io(component['iops_avg'], 'iops')}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{self._format_monitoring_io(component['iops_max'], 'iops')}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{self._format_monitoring_io(component['throughput_avg'], 'throughput')} MiB/s</td>
                    <td style="padding: 10px; border: 1px solid #ddd; color: {completeness_color};">{component['completeness']:.1f}%</td>
                </tr>
                """
            
            table_html += f"""
                </tbody>
            </table>
            
            <div class="info" style="margin-top: 15px;">
                <h4>&#128202; {self.t['overhead_analysis_notes']}</h4>
                <ul>
                    <li><strong>{self.t['monitoring_component_label']}</strong>: {self.t['component_breakdown']}</li>
                    <li><strong>CPU Usage</strong>: {self.t['cpu_percentage_used']}</li>
                    <li><strong>{self.t['memory_usage_label']}</strong>: {self.t['memory_size_used']}</li>
                    <li><strong>IOPS</strong>: {self.t['disk_io_operations']}</li>
                    <li><strong>Throughput</strong>: {self.t['disk_throughput_generated']}</li>
                    <li><strong>{self.t['data_completeness_label']}</strong>: {self.t['data_completeness_percentage']}</li>
                </ul>
                <p>{self.t['total_overhead_usually']}</p>
                <p><strong>{self.t['iops_throughput_zero_reason']}</strong>:</p>
                <ul style="margin-top: 5px;">
                    <li>{self.t['monitoring_reads_proc']}</li>
                    <li>{self.t['actual_io_overhead']}</li>
                    <li>{self.t['proves_efficient_design']}</li>
                    <li>{self.t['to_view_tiny_values']}</li>
                </ul>
            </div>
            """
            
            return table_html
            
        except Exception as e:
            print(f"❌ {self.t['overhead_table_generation_failed']}: {e}")
            return f"""
            <div class="warning">
                <h4>❌ {self.t['overhead_table_generation_failed']}</h4>
                <p>{self.t['error_message_label']}: {str(e)[:100]}</p>
                <p>{self.t['check_data_format']}</p>
            </div>
            """
    

    
    def _generate_independent_tools_results(self):
        """Generate independent analysis tools results display"""
        return f"""
        <div class="info-grid">
            <div class="info-card">
                <h4>&#128269; {self.t['ebs_bottleneck_detection']}</h4>
                <p><strong>{self.t['report_file_label']}</strong>: ebs_bottleneck_analysis.txt</p>
                <p>{self.t['analyze_ebs_under_qps']}</p>
            </div>
            <div class="info-card">
                <h4>&#128260; {self.t['ebs_iops_conversion']}</h4>
                <p><strong>{self.t['report_file_label']}</strong>: ebs_iops_conversion.json</p>
                <p>{self.t['convert_iostat_to_aws']}</p>
            </div>
            <div class="info-card">
                <h4>&#128202; {self.t['ebs_comprehensive_analysis']}</h4>
                <p><strong>{self.t['report_file_label']}</strong>: ebs_analysis.txt</p>
                <p>{self.t['ebs_performance_report']}</p>
            </div>
            <div class="info-card">
                <h4>&#128187; {self.t['monitoring_overhead_calculation']}</h4>
                <p><strong>{self.t['data_file_label']}</strong>: monitoring_overhead_YYYYMMDD_HHMMSS.csv</p>
                <p>{self.t['detailed_overhead_data']}</p>
            </div>
        </div>
        """

    def _generate_ena_warnings_section(self, df):
        """Generate ENA network warning section - using ENAFieldAccessor"""
        try:
            # Check ENA data availability - using configuration-driven approach
            ena_columns = ENAFieldAccessor.get_available_ena_fields(df)
            if not ena_columns:
                return ""
            
            # Analyze ENA limitation data
            limitations = self._analyze_ena_limitations(df)
            
            if not limitations:
                return f"""
                <div class="info" style="background-color: #E8F8F5; padding: 15px; border-radius: 6px; margin: 15px 0; border-left: 4px solid #27AE60;">
                    <h4>&#9989; {self.t['ena_network_normal']}</h4>
                    <p>{self.t['no_ena_limitations']}</p>
                </div>
                """
            
            # Generate warning HTML
            html = f"""
            <div class="warning">
                <h4>&#128680; {self.t['ena_limitation_detected']}</h4>
                <p>{self.t['detected_ena_limitations']}</p>
                <ul>
            """
            
            for limit in limitations:
                duration = ""
                if limit['first_time'] != limit['last_time']:
                    duration = f" ({self.t['duration_time']}: {limit['first_time']} {self.t['to']} {limit['last_time']})"
                
                html += f"""
                <li>
                    <strong>{limit['type']}</strong>{duration}
                    <ul>
                        <li>{self.t['occurrence_count']}: {limit['occurrences']}{self.t['times']}</li>
                        <li>{self.t['max_value_label']}: {limit['max_value']}</li>
                        <li>{self.t['cumulative_impact']}: {limit['total_affected']}</li>
                    </ul>
                </li>
                """
            
            html += f"""
                </ul>
                <p><strong>{self.t['recommendation_label']}</strong>: {self.t['consider_optimize_network']}</p>
            </div>
            """
            
            return html
            
        except Exception as e:
            return f'<div class="error">{self.t["ena_warning_generation_failed"]}: {str(e)}</div>'

    def _analyze_ena_limitations(self, df):
        """Analyze ENA limitation occurrences - using ENAFieldAccessor"""
        limitations = []
        available_fields = ENAFieldAccessor.get_available_ena_fields(df)
        
        # Analyze exceeded type fields
        for field in available_fields:
            if 'exceeded' in field and field in df.columns:
                # Get field analysis information
                field_analysis = ENAFieldAccessor.analyze_ena_field(df, field)
                if field_analysis:
                    # Filter records with limitations (value > 0)
                    limited_records = df[df[field] > 0]
                    
                    if not limited_records.empty:
                        limitations.append({
                            'type': field_analysis['description'],
                            'field': field,
                            'first_time': limited_records['timestamp'].min(),
                            'last_time': limited_records['timestamp'].max(),
                            'occurrences': len(limited_records),
                            'max_value': limited_records[field].max(),
                            'total_affected': limited_records[field].sum()
                        })
        
        # Special handling: Connection capacity insufficient warning - find available type fields
        available_field = None
        for field in available_fields:
            if 'available' in field and 'conntrack' in field:
                available_field = field
                break
        
        if available_field and available_field in df.columns:
            # Use dynamic threshold: calculate based on network threshold and data max value
            thresholds = get_visualization_thresholds()
            max_available = df[available_field].max() if not df[available_field].empty else 50000
            # Warning when available capacity is below (100-network threshold)% of max value
            low_connection_threshold = int(max_available * (100 - thresholds['io_warning']) / 100)
            low_connection_records = df[df[available_field] < low_connection_threshold]
            if not low_connection_records.empty:
                limitations.append({
                    'type': self.t['connection_capacity_warning'],
                    'field': available_field,
                    'first_time': low_connection_records['timestamp'].min(),
                    'last_time': low_connection_records['timestamp'].max(),
                    'occurrences': len(low_connection_records),
                    'max_value': f"{self.t['minimum_remaining']} {low_connection_records[available_field].min()} {self.t['connections']}",
                    'total_affected': f"{self.t['average_remaining']} {low_connection_records[available_field].mean():.0f} {self.t['connections']}" if available_field in low_connection_records.columns else self.t['data_not_available']
                })
        
        return limitations

    def _generate_ena_data_table(self, df):
        """Generate ENA data statistics table - using ENAFieldAccessor"""
        try:
            ena_columns = ENAFieldAccessor.get_available_ena_fields(df)
            if not ena_columns:
                return ""
            
            # Generate statistics - use ENAFieldAccessor to get field descriptions
            ena_stats = {}
            
            for col in ena_columns:
                field_analysis = ENAFieldAccessor.analyze_ena_field(df, col)
                if field_analysis:
                    # Select description based on language
                    description = field_analysis.get('aws_description', field_analysis['description']) if self.language == 'en' else field_analysis['description']
                    ena_stats[col] = {
                        'description': description,
                        'max': df[col].max(),
                        'mean': df[col].mean(),
                        'current': df[col].iloc[-1] if len(df) > 0 else 0
                    }
            
            # Generate HTML table
            table_rows = ""
            for field, stats in ena_stats.items():
                field_analysis = ENAFieldAccessor.analyze_ena_field(df, field)
                
                # Set different formats for different field types
                if field_analysis and field_analysis['type'] == 'gauge':  # available type fields
                    current_val = f"{stats['current']:,.0f}"
                    max_val = f"{stats['max']:,.0f}"
                    mean_val = f"{stats['mean']:,.0f}"
                else:  # counter type fields (exceeded)
                    current_val = f"{stats['current']}"
                    max_val = f"{stats['max']}"
                    mean_val = f"{stats['mean']:.1f}"
                
                # Status indicator
                status_class = "normal"
                if field_analysis and field_analysis['type'] == 'counter' and stats['current'] > 0:
                    status_class = "warning"
                elif field_analysis and field_analysis['type'] == 'gauge':
                    # Use dynamic threshold to determine connection capacity status
                    thresholds = get_visualization_thresholds()
                    max_available = max(stats['max'], 50000)  # Use max value or default value
                    warning_threshold = int(max_available * (100 - thresholds['io_warning']) / 100)
                    if stats['current'] < warning_threshold:
                        status_class = "warning"
                
                table_rows += f"""
                <tr class="{status_class}">
                    <td>{stats['description']}</td>
                    <td>{current_val}</td>
                    <td>{max_val}</td>
                    <td>{mean_val}</td>
                </tr>
                """
            
            return f"""
            <div class="section">
                <h3>&#127760; {self.t['ena_network_statistics']}</h3>
                <table class="performance-table">
                    <thead>
                        <tr>
                            <th>{self.t['ena_metric']}</th>
                            <th>{self.t['current_value']}</th>
                            <th>{self.t['max_value']}</th>
                            <th>{self.t['avg_value']}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
                <p class="table-note">
                    <strong>{self.t['note_label']}</strong>: 
                    • {self.t['exceeded_fields_show_drops']}
                    • {self.t['available_connections_show_capacity']}
                </p>
            </div>
            """
            
        except Exception as e:
            return f'<div class="error">{self.t["ena_table_generation_failed"]}: {str(e)}</div>'

    def _generate_cpu_ebs_correlation_table(self, df):
        """Improved CPU and EBS correlation analysis table generation"""
        key_correlations = [
            ('cpu_iowait', 'util', self.t['cpu_iowait_vs_util']),
            ('cpu_iowait', 'aqu_sz', self.t['cpu_iowait_vs_queue']),
            ('cpu_iowait', 'r_await', self.t['cpu_iowait_vs_read_latency']),
            ('cpu_iowait', 'w_await', self.t['cpu_iowait_vs_write_latency']),
            ('cpu_usr', 'r_s', self.t['user_cpu_vs_read_requests']),
            ('cpu_sys', 'w_s', self.t['system_cpu_vs_write_requests']),
        ]
        
        correlation_data = []
        data_cols = [col for col in df.columns if col.startswith('data_')]
        accounts_cols = [col for col in df.columns if col.startswith('accounts_')]
        
        # Safe correlation analysis function
        def safe_correlation_analysis(cpu_col, iostat_col, description, device_type):
            """Safe correlation analysis"""
            try:
                if cpu_col not in df.columns:
                    return None, f"{self.t['missing_cpu_field']}: {cpu_col}"
                
                if iostat_col not in df.columns:
                    return None, f"{self.t['missing_ebs_field']}: {iostat_col}"
                
                # Data validity check
                cpu_data = df[cpu_col].dropna()
                ebs_data = df[iostat_col].dropna()
                
                if len(cpu_data) == 0 or len(ebs_data) == 0:
                    return None, self.t['data_is_empty']
                
                # Align data and remove NaN
                combined_data = pd.concat([df[cpu_col], df[iostat_col]], axis=1).dropna()
                if len(combined_data) < 10:
                    return None, f"{self.t['insufficient_data_points']} ({self.t['only']}{len(combined_data)}{self.t['items']})"
                
                x_clean = combined_data.iloc[:, 0]
                y_clean = combined_data.iloc[:, 1]
                
                # Calculate correlation
                corr, p_value = pearsonr(x_clean, y_clean)
                
                # Check result validity
                if np.isnan(corr) or np.isnan(p_value):
                    return None, self.t['correlation_result_nan']
                
                # Improved correlation strength classification
                abs_corr = abs(corr)
                if abs_corr >= 0.8:
                    strength = self.t['very_strong_correlation']
                elif abs_corr >= 0.6:
                    strength = self.t['strong_correlation']
                elif abs_corr >= 0.4:
                    strength = self.t['moderate_correlation']
                elif abs_corr >= 0.2:
                    strength = self.t['weak_correlation']
                else:
                    strength = self.t['very_weak_correlation']
                
                # Improved statistical significance determination
                if p_value < 0.001:
                    significant = self.t['highly_significant_3']
                elif p_value < 0.01:
                    significant = self.t['highly_significant_2']
                elif p_value < 0.05:
                    significant = self.t['significant_1']
                else:
                    significant = self.t['not_significant']
                
                return {
                    self.t['device_type']: device_type,
                    self.t['analysis_item']: description,
                    self.t['cpu_metric']: cpu_col,
                    self.t['ebs_metric']: iostat_col,
                    self.t['correlation_coefficient']: f"{corr:.4f}",
                    self.t['p_value']: f"{p_value:.4f}",
                    self.t['statistical_significance']: significant,
                    self.t['correlation_strength']: strength,
                    self.t['valid_sample_count']: len(combined_data),
                    self.t['data_integrity']: f"{len(combined_data)/len(df)*100:.1f}%"
                }, None
                
            except Exception as e:
                return None, f"{self.t['analysis_failed']}: {str(e)[:50]}"
        
        def find_matching_column(target_field, column_list):
            """Precise field matching"""
            # Exact match
            exact_matches = [col for col in column_list if col.endswith(f'_{target_field}')]
            if exact_matches:
                return exact_matches[0]
            
            # Fuzzy matching (stricter)
            fuzzy_matches = [col for col in column_list if target_field in col and not any(x in col for x in ['avg', 'max', 'min', 'sum'])]
            if fuzzy_matches:
                return fuzzy_matches[0]
            
            return None
        
        # Analyze DATA Device
        for cpu_field, iostat_field, description in key_correlations:
            iostat_col = find_matching_column(iostat_field, data_cols)
            
            if iostat_col:
                result, error = safe_correlation_analysis(cpu_field, iostat_col, description, 'DATA')
                if result:
                    correlation_data.append(result)
                else:
                    print(f"⚠️ DATA Device {description}: {error}")
        
        # Analyze ACCOUNTS Device
        if accounts_cols:
            for cpu_field, iostat_field, description in key_correlations:
                iostat_col = find_matching_column(iostat_field, accounts_cols)
                
                if iostat_col:
                    result, error = safe_correlation_analysis(cpu_field, iostat_col, description.replace('Device', 'ACCOUNTS Device'), 'ACCOUNTS')
                    if result:
                        correlation_data.append(result)
                    else:
                        print(f"⚠️ ACCOUNTS Device {description}: {error}")
        
        if not correlation_data:
            return f"""
            <div class="warning">
                <h4>&#9888; {self.t['correlation_data_unavailable']}</h4>
                <p>{self.t['possible_reasons']}</p>
                <ul>
                    <li>{self.t['missing_cpu_ebs_fields']}</li>
                    <li>{self.t['data_quality_issues']}</li>
                    <li>{self.t['insufficient_data_less_10']}</li>
                </ul>
            </div>
            """
        
        # Generate improved HTML table
        table_html = f"""
        <table style="width: 100%; border-collapse: collapse; margin-top: 15px; background: white;">
            <thead>
                <tr>
                    <th style="background: #C0392B; color: white; padding: 12px;">{self.t['device_type']}</th>
                    <th style="background: #C0392B; color: white; padding: 12px;">{self.t['analysis_item']}</th>
                    <th style="background: #C0392B; color: white; padding: 12px;">{self.t['correlation_coefficient']}</th>
                    <th style="background: #C0392B; color: white; padding: 12px;">{self.t['p_value']}</th>
                    <th style="background: #C0392B; color: white; padding: 12px;">{self.t['statistical_significance']}</th>
                    <th style="background: #C0392B; color: white; padding: 12px;">{self.t['correlation_strength']}</th>
                    <th style="background: #C0392B; color: white; padding: 12px;">{self.t['valid_sample_count']}</th>
                    <th style="background: #C0392B; color: white; padding: 12px;">{self.t['data_integrity']}</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for i, data in enumerate(correlation_data):
            # Set row color based on correlation strength
            strength_val = data[self.t['correlation_strength']]
            if self.t['very_strong_correlation'] in strength_val:
                row_color = "#e8f5e8"
            elif self.t['strong_correlation'] in strength_val:
                row_color = "#f0f8f0"
            elif self.t['moderate_correlation'] in strength_val:
                row_color = "#fff8e1"
            else:
                row_color = "#f8f9fa"
            
            table_html += f"""
                <tr style="background: {row_color};">
                    <td style="padding: 10px; border: 1px solid #ddd;">{data[self.t['device_type']]}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{data[self.t['analysis_item']]}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{data[self.t['correlation_coefficient']]}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{data[self.t['p_value']]}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{data[self.t['statistical_significance']]}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{data[self.t['correlation_strength']]}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{data[self.t['valid_sample_count']]}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{data[self.t['data_integrity']]}</td>
                </tr>
            """
        
        table_html += f"""
            </tbody>
        </table>
        <div class="info" style="margin-top: 15px;">
            <h4>&#128202; {self.t['correlation_analysis_notes']}</h4>
            <ul>
                <li><strong>{self.t['correlation_range']}</strong>: {self.t['larger_abs_stronger']}</li>
                <li><strong>{self.t['statistical_significance']}</strong>: {self.t['significance_levels']}</li>
                <li><strong>{self.t['strength_classification']}</strong></li>
                <li><strong>{self.t['data_integrity']}</strong>: {self.t['data_integrity_percentage']}</li>
            </ul>
        </div>
        """
        
        return table_html

    def _format_block_height_value(self, field_name, value):
        """Convert block_height related field values to human-readable format"""
        if 'health' in field_name.lower():
            return 'Healthy' if value == 1 else 'Unhealthy'
        elif 'data_loss' in field_name.lower():
            return 'No Data Loss' if value == 0 else 'Data Loss Detected'
        else:
            # For numeric fields (like block_height, block_height_diff), keep as is
            return f"{value:.0f}" if isinstance(value, (int, float)) else str(value)

    def _analyze_block_height_performance(self, df, block_height_fields):
        """Enhanced block height performance analysis - using comparison table display"""
        if not block_height_fields or df.empty:
            return f"<div class='info-card'><h4>{self.t['block_height_monitoring']}</h4><p>{self.t['no_block_height_data']}</p></div>"
        
        try:
            # Add time series chart display
            sync_chart_html = self._generate_block_height_chart_section()
            
            # Add data_loss_stats.json file display
            stats_file_html = self._generate_data_loss_stats_section()
            
            # Collect block height data
            block_height_data = {}
            for field in block_height_fields:
                if field in df.columns:
                    numeric_data = pd.to_numeric(df[field], errors='coerce').dropna()
                    if not numeric_data.empty:
                        block_height_data[field] = {
                            'current': numeric_data.iloc[-1] if len(numeric_data) > 0 else 0,
                            'average': numeric_data.mean(),
                            'min': numeric_data.min(),
                            'max': numeric_data.max(),
                            'data': numeric_data
                        }
            
            # Generate comparison table
            comparison_table = f"""
            <div style="margin: 20px 0;">
                <h3>📊 {self.t['block_height_data_comparison']}</h3>
                <table style="width: 100%; border-collapse: collapse; margin-top: 15px; background: white;">
                    <thead>
                        <tr>
                            <th style="background: #16A085; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['metric']}</th>
                            <th style="background: #16A085; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['local_block_height']}</th>
                            <th style="background: #16A085; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['mainnet_block_height']}</th>
                            <th style="background: #16A085; color: white; padding: 12px; border: 1px solid #ddd;">{self.t['block_height_diff']}</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            # Add data rows
            metrics = [
                ('Current', 'current'),
                ('Average', 'average'),
                ('Min', 'min'),
                ('Max', 'max')
            ]
            
            for metric_name, metric_key in metrics:
                local_val = block_height_data.get('local_block_height', {}).get(metric_key, 'N/A')
                mainnet_val = block_height_data.get('mainnet_block_height', {}).get(metric_key, 'N/A')
                diff_val = block_height_data.get('block_height_diff', {}).get(metric_key, 'N/A')
                
                # Format numeric values
                local_str = f"{local_val:.0f}" if isinstance(local_val, (int, float)) else str(local_val)
                mainnet_str = f"{mainnet_val:.0f}" if isinstance(mainnet_val, (int, float)) else str(mainnet_val)
                diff_str = f"{diff_val:.0f}" if isinstance(diff_val, (int, float)) else str(diff_val)
                
                comparison_table += f"""
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{metric_name}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{local_str}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{mainnet_str}</td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{diff_str}</td>
                        </tr>
                """
            
            comparison_table += """
                    </tbody>
                </table>
            </div>
            """
            
            # Combine all parts
            complete_html = f"""
            <div class="section">
                <h2>🔗 {self.t['blockchain_node_sync_analysis']}</h2>
                {sync_chart_html}
                {comparison_table}
                {stats_file_html}
            </div>
            """
            
            return complete_html
                
        except Exception as e:
            return f"<div class='error'>{self.t['block_height_analysis_failed']}: {str(e)}</div>"

    def _generate_block_height_chart_section(self):
        """Generate block height chart display section"""
        # Check multiple possible chart locations
        possible_paths = [
            os.path.join(self.output_dir, 'block_height_sync_chart.png'),
            os.path.join(os.path.dirname(self.output_dir), 'reports', 'block_height_sync_chart.png'),
            os.path.join(self.output_dir, 'current', 'reports', 'block_height_sync_chart.png')
        ]
        
        chart_src = None
        for path in possible_paths:
            if os.path.exists(path):
                # Calculate relative path
                chart_src = os.path.relpath(path, self.output_dir)
                break
        
        if chart_src:
            return f"""
            <div class="info-card">
                <h3>📊 {self.t['block_height_sync_time_series']}</h3>
                <div class="chart-container">
                    <img src="{chart_src}" alt="{self.t['block_height_sync_status']}" class="chart-image">
                </div>
                <div class="chart-info">
                    <p>{self.t['chart_shows_block_height_diff']}:</p>
                    <ul>
                        <li><strong>{self.t['blue_curve']}</strong>: {self.t['block_height_diff_mainnet_minus_local']}</li>
                        <li><strong>{self.t['red_dashed_line']}</strong>: {self.t['anomaly_threshold_50_blocks']}</li>
                        <li><strong>{self.t['red_area']}</strong>: {self.t['data_loss_detected_periods']}</li>
                        <li><strong>{self.t['statistics_info']}</strong>: {self.t['sync_quality_stats_top_left']}</li>
                    </ul>
                </div>
            </div>
            """
        else:
            return f"""
            <div class="info-card">
                <h3>📊 {self.t['block_height_sync_time_series']}</h3>
                <div class="warning">
                    <p>⚠️ {self.t['block_height_chart_not_generated']}</p>
                    <p>{self.t['possible_reason_node_data_unavailable']}</p>
                </div>
            </div>
            """

    def _generate_data_loss_stats_section(self):
        """Generate data_loss_stats.json file display section"""
        
        # Check stats file in archive
        stats_file = None
        possible_paths = [
            os.path.join(self.output_dir, 'stats', 'data_loss_stats.json'),
            os.path.join(self.output_dir, 'data_loss_stats.json'),
            os.path.join(os.path.dirname(self.output_dir), 'stats', 'data_loss_stats.json')
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                stats_file = path
                break
        
        if stats_file:
            try:
                with open(stats_file, 'r') as f:
                    stats_data = json.load(f)
                
                # Calculate derived metrics
                avg_duration = (stats_data['total_duration'] / stats_data['data_loss_periods']) if stats_data['data_loss_periods'] > 0 else 0
                
                return f"""
                <div class="info-card">
                    <h3>📋 {self.t['data_loss_stats_summary']}</h3>
                    <div class="stats-grid">
                        <div class="stat-item">
                            <div class="stat-value">{stats_data['data_loss_count']}</div>
                            <div class="stat-label">{self.t['anomaly_sample_count']}</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">{stats_data['data_loss_periods']}</div>
                            <div class="stat-label">{self.t['anomaly_event_count']}</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">{stats_data['total_duration']}s</div>
                            <div class="stat-label">{self.t['total_anomaly_duration']}</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">{avg_duration:.1f}s</div>
                            <div class="stat-label">{self.t['avg_event_duration']}</div>
                        </div>
                    </div>
                    <div class="file-info">
                        <p><strong>📁 {self.t['stats_file_location']}:</strong> <code>{os.path.relpath(stats_file, self.output_dir)}</code></p>
                        <p><strong>🕐 {self.t['last_updated']}:</strong> {stats_data.get('last_updated', 'Unknown')}</p>
                    </div>
                </div>
                """
            except Exception as e:
                return f"""
                <div class="warning">
                    <h3>⚠️ {self.t['data_loss_statistics']}</h3>
                    <p>{self.t['stats_file_read_failed']}: {str(e)}</p>
                    <p><strong>{self.t['file_location']}:</strong> <code>{os.path.relpath(stats_file, self.output_dir)}</code></p>
                </div>
                """
        else:
            return f"""
            <div class="warning">
                <h3>⚠️ {self.t['data_loss_statistics']}</h3>
                <p>{self.t['data_loss_stats_file_not_found']}:</p>
                <ul>
                    <li>{self.t['no_data_loss_detected_during_test']}</li>
                    <li>{self.t['stats_file_not_archived']}</li>
                    <li>{self.t['block_height_monitor_not_running']}</li>
                </ul>
            </div>
            """

    def _discover_chart_files(self):
        """Dynamically discover all generated chart files - scan multiple directories, support archive paths"""
        chart_patterns = ["*.png", "*.jpg", "*.svg"]
        chart_files = []
        
        # Scan directory list - support archived path structure
        scan_dirs = [
            self.output_dir,  # Main output directory (may be archive directory)
            os.path.join(self.output_dir, 'current', 'reports'),  # Advanced charts directory
            os.path.join(self.output_dir, 'reports'),  # Backup reports directory
            os.path.join(self.output_dir, 'logs'),  # Archived logs directory
        ]
        
        # If output_dir looks like archive directory, add special scan paths
        if 'archives' in self.output_dir or 'run_' in os.path.basename(self.output_dir):
            # This is archive directory, scan its subdirectories directly
            scan_dirs.extend([
                os.path.join(self.output_dir, 'logs'),
                os.path.join(self.output_dir, 'reports'),
                os.path.join(self.output_dir, 'current', 'reports'),
            ])
        
        # Add sibling reports directory scan (critical fix)
        parent_dir = os.path.dirname(self.output_dir)
        sibling_reports = os.path.join(parent_dir, 'reports')
        if os.path.exists(sibling_reports):
            scan_dirs.append(sibling_reports)
        
        for scan_dir in scan_dirs:
            if os.path.exists(scan_dir):
                for pattern in chart_patterns:
                    chart_files.extend(glob.glob(os.path.join(scan_dir, pattern)))
        
        # Deduplicate and sort
        unique_charts = list(set(chart_files))
        
        # Filter out timestamped duplicates (e.g., keep xxx.png, remove xxx_20251024_104814.png)
        import re
        timestamp_pattern = re.compile(r'_\d{8}_\d{6}\.png$')
        filtered_charts = []
        base_names = {}
        
        for chart in unique_charts:
            basename = os.path.basename(chart)
            # Check if this is a timestamped version
            if timestamp_pattern.search(basename):
                # Extract base name without timestamp
                base_name = re.sub(r'_\d{8}_\d{6}', '', basename)
                base_names[base_name] = base_names.get(base_name, []) + [chart]
            else:
                # Non-timestamped version, always keep
                filtered_charts.append(chart)
        
        # For timestamped files, only add if no non-timestamped version exists
        for base_name, charts in base_names.items():
            if base_name not in [os.path.basename(f) for f in filtered_charts]:
                # No non-timestamped version, keep the timestamped one
                filtered_charts.extend(charts)
        
        return sorted([f for f in filtered_charts if os.path.exists(f)])

    def _categorize_charts(self, chart_files):
        """Organize charts by category - based on filename patterns, exclude duplicate displayed charts"""
        # Exclude charts already displayed in fixed sections
        excluded_charts = {
            'block_height_sync_chart.png',  # Already displayed in block height analysis section
            'monitoring_overhead_analysis.png',  # Already displayed in monitoring overhead detailed analysis section
            'monitoring_impact_chart.png',  # Already displayed in monitoring overhead and performance relationship section
            'resource_distribution_chart.png'  # Already displayed in resource proportion analysis section
        }
        
        categories = {
            'advanced': {'title': self.t.get('advanced_analysis_charts', 'Advanced Analysis Charts'), 'charts': []},
            'ebs': {'title': self.t.get('ebs_professional_charts', 'EBS Professional Charts'), 'charts': []},
            'performance': {'title': self.t.get('core_performance_charts', 'Core Performance Charts'), 'charts': []},
            'monitoring': {'title': self.t.get('monitoring_overhead_charts', 'Monitoring & Overhead Charts'), 'charts': []},
            'network': {'title': self.t.get('network_ena_charts', 'Network & ENA Charts'), 'charts': []},
            'other': {'title': self.t.get('additional_charts', 'Additional Charts'), 'charts': []}
        }
        
        for chart_file in chart_files:
            filename = os.path.basename(chart_file)
            filename_lower = filename.lower()
            
            # Skip excluded charts
            if filename in excluded_charts:
                continue
            
            # Advanced analysis charts
            if any(keyword in filename_lower for keyword in ['pearson', 'correlation', 'regression', 'heatmap', 'matrix']):
                categories['advanced']['charts'].append(chart_file)
            # EBS charts
            elif any(keyword in filename_lower for keyword in ['ebs', 'aws', 'iostat', 'bottleneck']):
                categories['ebs']['charts'].append(chart_file)
            # Network/ENA charts
            elif any(keyword in filename_lower for keyword in ['ena', 'network', 'allowance']):
                categories['network']['charts'].append(chart_file)
            # Monitoring charts (exclude already displayed)
            elif any(keyword in filename_lower for keyword in ['monitoring', 'overhead']) and filename not in excluded_charts:
                categories['monitoring']['charts'].append(chart_file)
            # Performance charts
            elif any(keyword in filename_lower for keyword in ['performance', 'qps', 'trend', 'efficiency', 'threshold', 'util', 'await']):
                categories['performance']['charts'].append(chart_file)
            else:
                categories['other']['charts'].append(chart_file)
        
        return categories

    def _generate_chart_gallery_section(self):
        """Generate dynamic chart display area"""
        chart_files = self._discover_chart_files()
        if not chart_files:
            return f'<div class="section"><h2>📊 {self.t["performance_charts"]}</h2><p>{self.t["no_charts_found"]}</p></div>'
        
        categories = self._categorize_charts(chart_files)
        total_charts = len(chart_files)
        
        html = f'''
        <div class="section">
            <h2>📊 {self.t["performance_chart_gallery"]}</h2>
            <div class="chart-summary">
                <p><strong>{self.t["total_charts_generated"]}:</strong> {total_charts}</p>
            </div>
        '''
        
        for category_key, category_data in categories.items():
            if category_data['charts']:
                html += f'''
                <div class="chart-category">
                    <h3 style="color: #2C3E50;">📈 {category_data['title']} ({len(category_data['charts'])} charts)</h3>
                    <div class="chart-grid">
                '''
                
                for chart_file in category_data['charts']:
                    chart_name = os.path.basename(chart_file)
                    chart_key = chart_name.replace('.png', '')
                    
                    # Get localized title and description
                    title_key = f'chart_{chart_key}'
                    desc_key = f'chart_{chart_key}_desc'
                    chart_title = self.t.get(title_key, chart_name.replace('_', ' ').replace('.png', '').title())
                    chart_desc = self.t.get(desc_key, '')
                    
                    # Fix capitalization if using fallback title
                    if title_key not in self.t:
                        chart_title = chart_title.replace('Cpu', 'CPU').replace('Ebs', 'EBS').replace('Aws', 'AWS').replace('Qps', 'QPS').replace('Ena', 'ENA')
                    
                    # Calculate relative path
                    rel_path = os.path.relpath(chart_file, self.output_dir)
                    
                    html += f'''
                    <div class="chart-item">
                        <h4>{chart_title}</h4>
                        {f'<p style="color: #666; font-size: 0.9em; margin: 8px 0;">{chart_desc}</p>' if chart_desc else ''}
                        <div class="chart-container">
                            <img src="{rel_path}" alt="{chart_title}" class="chart">
                        </div>
                    </div>
                    '''
                
                html += '''
                    </div>
                </div>
                '''
        
        html += '</div>'
        return html

    def _generate_html_content(self, df):
        """Generate HTML content + bottleneck information display + image references"""
        try:
            # Identify block_height related fields
            block_height_fields = [col for col in df.columns if 'block_height' in col.lower() or 'height' in col.lower()]
            
            # Generate each section - using actually existing methods
            monitoring_overhead_analysis = self._generate_monitoring_overhead_section()
            monitoring_overhead_detailed = self._generate_monitoring_overhead_detailed_section()
            ena_warnings = self._generate_ena_warnings_section(df)
            ena_data_table = self._generate_ena_data_table(df)
            
            config_status_section = self._generate_config_status_section()
            block_height_analysis = self._analyze_block_height_performance(df, block_height_fields)

            correlation_table = self._generate_cpu_ebs_correlation_table(df)
            overhead_table = self._generate_overhead_data_table()
            
            # Generate performance summary
            performance_summary = self._generate_performance_summary(df)
            
            # Generate bottleneck information display (if available)
            bottleneck_section = self._generate_bottleneck_section()
            
            # Generate dynamic chart display section
            charts_section = self._generate_chart_gallery_section()
            
            # Generate EBS analysis results
            ebs_warnings, ebs_metrics = self.parse_ebs_analyzer_log()
            ebs_analysis_section = self.generate_ebs_analysis_section(ebs_warnings, ebs_metrics)
            
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>&#128640; {self.t['report_title']}</title>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    {self._get_css_styles()}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>{self.t['report_title']}</h1>
                    <p>{self.t['generated_time']}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>{self.t['unified_field_naming']} | {self.t['complete_device_support']} | {self.t['monitoring_overhead_analysis']} | {self.t['blockchain_node_specific_analysis']} | {self.t['bottleneck_detection_analysis']}</p>
                    
                    {bottleneck_section}
                    {performance_summary}
                    {config_status_section}
                    {block_height_analysis}
                    {ebs_analysis_section}
                    {charts_section}
                    {monitoring_overhead_analysis}
                    {monitoring_overhead_detailed}
                    {overhead_table}
                    {ena_warnings}
                    {ena_data_table}

                    {correlation_table}
                </div>
            </body>
            </html>
            """
        except Exception as e:
            return f"<div class='error'>{self.t['html_content_generation_failed']}: {str(e)}</div>"

    def _generate_charts_section(self):
        """Generate chart display section"""
        try:
            # Define all possible generated charts and their descriptions
            chart_definitions = [
                # Charts generated by performance_visualizer.py
                {
                    'filename': 'performance_overview.png',
                    'title': f'&#128200; {self.t["chart_performance_overview"]}',
                    'description': self.t['chart_performance_overview_desc']
                },
                {
                    'filename': 'cpu_ebs_correlation_visualization.png',
                    'title': f'&#128279; {self.t["chart_cpu_ebs_correlation"]}',
                    'description': self.t['chart_cpu_ebs_correlation_desc']
                },
                {
                    'filename': 'device_performance_comparison.png',
                    'title': f'&#128190; {self.t["chart_device_performance_comparison"]}',
                    'description': self.t['chart_device_performance_comparison_desc']
                },
                {
                    'filename': 'await_threshold_analysis.png',
                    'title': f'&#9202; {self.t["chart_await_threshold_analysis"]}',
                    'description': self.t['chart_await_threshold_analysis_desc']
                },
                {
                    'filename': 'util_threshold_analysis.png',
                    'title': f'&#128202; {self.t["chart_util_threshold_analysis"]}',
                    'description': self.t['chart_util_threshold_analysis_desc']
                },
                {
                    'filename': 'monitoring_overhead_analysis.png',
                    'title': f'&#128203; {self.t["chart_monitoring_overhead_analysis"]}',
                    'description': self.t['chart_monitoring_overhead_analysis_desc']
                },
                {
                    'filename': 'smoothed_trend_analysis.png',
                    'title': f'&#128200; {self.t["chart_smoothed_trend_analysis"]}',
                    'description': self.t['chart_smoothed_trend_analysis_desc']
                },
                {
                    'filename': 'qps_trend_analysis.png',
                    'title': f'&#128640; {self.t["chart_qps_trend_analysis"]}',
                    'description': self.t['chart_qps_trend_analysis_desc']
                },
                {
                    'filename': 'resource_efficiency_analysis.png',
                    'title': f'&#9889; {self.t["chart_resource_efficiency_analysis"]}',
                    'description': self.t['chart_resource_efficiency_analysis_desc']
                },
                {
                    'filename': 'bottleneck_identification.png',
                    'title': f'&#128680; {self.t["chart_bottleneck_identification"]}',
                    'description': self.t['chart_bottleneck_identification_desc']
                },
                
                # Charts generated by advanced_chart_generator.py
                {
                    'filename': 'pearson_correlation_analysis.png',
                    'title': f'&#128202; {self.t["chart_pearson_correlation_analysis"]}',
                    'description': self.t['chart_pearson_correlation_analysis_desc']
                },
                {
                    'filename': 'linear_regression_analysis.png',
                    'title': f'&#128200; {self.t["chart_linear_regression_analysis"]}',
                    'description': self.t['chart_linear_regression_analysis_desc']
                },
                {
                    'filename': 'negative_correlation_analysis.png',
                    'title': f'&#128201; {self.t["chart_negative_correlation_analysis"]}',
                    'description': self.t['chart_negative_correlation_analysis_desc']
                },
                {
                    'filename': 'comprehensive_correlation_matrix.png',
                    'title': f'&#128269; {self.t["chart_comprehensive_correlation_matrix"]}',
                    'description': self.t['chart_comprehensive_correlation_matrix_desc']
                },
                {
                    'filename': 'performance_trend_analysis.png',
                    'title': f'&#128202; {self.t["chart_performance_trend_analysis"]}',
                    'description': self.t['chart_performance_trend_analysis_desc']
                },
                {
                    'filename': 'ena_limitation_trends.png',
                    'title': f'&#128680; {self.t["chart_ena_limitation_trends"]}',
                    'description': self.t['chart_ena_limitation_trends_desc']
                },
                {
                    'filename': 'ena_connection_capacity.png',
                    'title': f'&#128279; {self.t["chart_ena_connection_capacity"]}',
                    'description': self.t['chart_ena_connection_capacity_desc']
                },
                {
                    'filename': 'ena_comprehensive_status.png',
                    'title': f'&#127760; {self.t["chart_ena_comprehensive_status"]}',
                    'description': self.t['chart_ena_comprehensive_status_desc']
                },
                {
                    'filename': 'performance_correlation_heatmap.png',
                    'title': f'&#128293; {self.t["chart_performance_correlation_heatmap"]}',
                    'description': self.t['chart_performance_correlation_heatmap_desc']
                },
                
                {
                    'filename': 'performance_cliff_analysis.png',
                    'title': f'&#128201; {self.t["chart_performance_cliff_analysis"]}',
                    'description': self.t['chart_performance_cliff_analysis_desc']
                },
                {
                    'filename': 'comprehensive_analysis_charts.png',
                    'title': f'&#128202; {self.t["chart_comprehensive_analysis_charts"]}',
                    'description': self.t['chart_comprehensive_analysis_charts_desc']
                },
                {
                    'filename': 'qps_performance_analysis.png',
                    'title': f'&#127919; {self.t["chart_qps_performance_analysis"]}',
                    'description': self.t['chart_qps_performance_analysis_desc']
                },
                
                # EBS professional analysis chart group
                {
                    'filename': 'ebs_aws_capacity_planning.png',
                    'title': f'&#128202; {self.t["chart_ebs_aws_capacity_planning"]}',
                    'description': self.t['chart_ebs_aws_capacity_planning_desc']
                },
                {
                    'filename': 'ebs_iostat_performance.png',
                    'title': f'&#128190; {self.t["chart_ebs_iostat_performance"]}',
                    'description': self.t['chart_ebs_iostat_performance_desc']
                },
                {
                    'filename': 'ebs_bottleneck_correlation.png',
                    'title': f'&#128279; {self.t["chart_ebs_bottleneck_correlation"]}',
                    'description': self.t['chart_ebs_bottleneck_correlation_desc']
                },
                {
                    'filename': 'ebs_performance_overview.png',
                    'title': f'&#128200; {self.t["chart_ebs_performance_overview"]}',
                    'description': self.t['chart_ebs_performance_overview_desc']
                },
                {
                    'filename': 'ebs_bottleneck_analysis.png',
                    'title': f'&#128680; {self.t["chart_ebs_bottleneck_analysis"]}',
                    'description': self.t['chart_ebs_bottleneck_analysis_desc']
                },
                {
                    'filename': 'ebs_aws_standard_comparison.png',
                    'title': f'&#9878;️ {self.t["chart_ebs_aws_standard_comparison"]}',
                    'description': self.t['chart_ebs_aws_standard_comparison_desc']
                },
                {
                    'filename': 'ebs_time_series_analysis.png',
                    'title': f'&#128202; {self.t["chart_ebs_time_series_analysis"]}',
                    'description': self.t['chart_ebs_time_series_analysis_desc']
                },
                {
                    'filename': 'block_height_sync_chart.png',
                    'title': f'🔗 {self.t["chart_block_height_sync_chart"]}',
                    'description': self.t['chart_block_height_sync_chart_desc']
                }
            ]
            
            # Check chart file existence and generate HTML
            charts_html = f"""
            <div class="section">
                <h2>&#128202; {self.t['performance_analysis_charts']}</h2>
                <div class="info">
                    <p>{self.t['charts_provide_comprehensive_visualization']}</p>
                </div>
            """
            
            # Get report output directory - use environment variable or current/reports structure
            reports_dir = os.getenv('REPORTS_DIR', os.path.join(self.output_dir, 'current', 'reports'))
            if not os.path.exists(reports_dir):
                reports_dir = self.output_dir
            
            available_charts = []
            missing_charts = []
            
            for chart in chart_definitions:
                chart_path = os.path.join(reports_dir, chart['filename'])
                # Also check charts directly in output_dir
                alt_chart_path = os.path.join(self.output_dir, os.path.basename(chart['filename']))
                
                if os.path.exists(chart_path):
                    available_charts.append((chart, chart['filename']))
                elif os.path.exists(alt_chart_path):
                    available_charts.append((chart, os.path.basename(chart['filename'])))
                else:
                    missing_charts.append(chart)
            
            # Generate HTML for available charts
            if available_charts:
                charts_html += """
                <div class="charts-grid">
                """
                
                for chart, relative_path in available_charts:
                    charts_html += f"""
                    <div class="chart-item">
                        <h3>{chart['title']}</h3>
                        <div class="chart-description">
                            <p>{chart['description']}</p>
                        </div>
                        <div class="chart-container">
                            <img src="{relative_path}" alt="{chart['title']}" class="chart-image">
                        </div>
                    </div>
                    """
                
                charts_html += """
                </div>
                """
                
                # Add chart statistics
                charts_html += f"""
                <div class="charts-summary">
                    <h3>&#128200; {self.t['chart_statistics']}</h3>
                    <ul>
                        <li>&#9989; {self.t['available_charts']}: {len(available_charts)} {self.t['items']}</li>
                        <li>&#8987; {self.t['pending_charts']}: {len(missing_charts)} {self.t['items']}</li>
                        <li>&#128202; {self.t['chart_coverage']}: {len(available_charts)/(len(available_charts)+len(missing_charts))*100:.1f}%</li>
                    </ul>
                </div>
                """
            else:
                charts_html += f"""
                <div class="warning">
                    <h3>&#9888; {self.t['chart_generation_notice']}</h3>
                    <p>{self.t['no_chart_files_found']}:</p>
                    <ul>
                        <li>{self.t['run_performance_visualizer']}</li>
                        <li>{self.t['run_advanced_chart_generator']}</li>
                        <li>{self.t['run_comprehensive_analysis']}</li>
                    </ul>
                    <p>{self.t['ensure_run_chart_scripts_before_report']}</p>
                </div>
                """
            
            # If there are missing charts, show notice
            if missing_charts:
                charts_html += f"""
                <div class="missing-charts">
                    <h3>&#128203; {self.t['pending_charts']}</h3>
                    <p>{self.t['following_charts_not_generated']}:</p>
                    <ul>
                """
                for chart in missing_charts[:5]:  # Show only first 5
                    charts_html += f"<li>{chart['title']} - {chart['description']}</li>"
                
                if len(missing_charts) > 5:
                    charts_html += f"<li>... {self.t['and']} {len(missing_charts) - 5} {self.t['more_charts']}</li>"
                
                charts_html += """
                    </ul>
                </div>
                """
            
            charts_html += """
            </div>
            """
            
            return charts_html
            
        except Exception as e:
            return f"""
            <div class="section error">
                <h2>&#9888; {self.t['chart_display_error']}</h2>
                <p>{self.t['chart_section_generation_failed']}: {str(e)}</p>
            </div>
            """

    def _generate_bottleneck_section(self):
        """Generate system-level bottleneck analysis section - always display"""
        try:
            bottleneck_detected = False
            if self.bottleneck_data:
                bottleneck_detected = self.bottleneck_data.get('bottleneck_detected', False)
            
            if bottleneck_detected:
                # 有瓶颈：显示详细信息
                max_qps = self.bottleneck_data.get('max_successful_qps', 0)
                bottleneck_qps = self.bottleneck_data.get('bottleneck_qps', 0)
                reasons = self.bottleneck_data.get('bottleneck_reasons', self.t['unknown'])
                severity = self.bottleneck_data.get('severity', 'medium')
                detection_time = self.bottleneck_data.get('detection_time', self.t['unknown'])
                consecutive_detections = self.bottleneck_data.get('consecutive_detections', 0)
                
                performance_drop = 0.0
                if max_qps > 0:
                    performance_drop = ((bottleneck_qps - max_qps) / max_qps) * 100
                
                severity_color = {
                    'low': '#28a745',
                    'medium': '#ffc107', 
                    'high': '#dc3545'
                }.get(severity.lower(), '#ffc107')
                
                return f"""
                <div class="section" style="border-left: 5px solid {severity_color}; background-color: #FEF5E7;">
                    <h2 style="color: {severity_color};">&#128680; {self.t['system_bottleneck_analysis']}</h2>
                    
                    <div style="background: #fff3cd; border: 1px solid {severity_color}; padding: 15px; border-radius: 4px; margin: 15px 0;">
                        <h3 style="color: {severity_color}; margin-top: 0;">&#9888; {self.t['system_bottleneck_detected']}</h3>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0;">
                        <div style="background: white; padding: 15px; border-radius: 4px; border: 1px solid #ddd;">
                            <h4 style="margin: 0 0 10px 0; color: #666;">&#127942; {self.t['max_successful_qps']}</h4>
                            <div style="color: #28a745; font-size: 2em; font-weight: bold;">{max_qps}</div>
                        </div>
                        <div style="background: white; padding: 15px; border-radius: 4px; border: 1px solid #ddd;">
                            <h4 style="margin: 0 0 10px 0; color: #666;">&#128680; {self.t['bottleneck_trigger_qps']}</h4>
                            <div style="color: #dc3545; font-size: 2em; font-weight: bold;">{bottleneck_qps}</div>
                        </div>
                        <div style="background: white; padding: 15px; border-radius: 4px; border: 1px solid #ddd;">
                            <h4 style="margin: 0 0 10px 0; color: #666;">&#128201; {self.t['performance_drop']}</h4>
                            <div style="color: #dc3545; font-size: 2em; font-weight: bold;">{performance_drop:.1f}%</div>
                        </div>
                    </div>
                    
                    <div style="background: white; padding: 15px; border-radius: 4px; margin: 15px 0;">
                        <h3>&#128269; {self.t['bottleneck_details']}</h3>
                        <p><strong>{self.t['detection_time']}:</strong> {detection_time}</p>
                        <p><strong>{self.t['severity_level']}:</strong> <span style="color: {severity_color}; font-weight: bold;">{severity.upper()}</span></p>
                        <p><strong>{self.t['bottleneck_reason']}:</strong> {reasons}</p>
                        <p><strong>{self.t['consecutive_detections']}:</strong> {consecutive_detections}</p>
                    </div>
                    
                    <div style="background: #e7f3ff; border: 1px solid #b3d9ff; padding: 15px; border-radius: 4px; margin: 15px 0;">
                        <h3 style="margin-top: 0;">&#128203; {self.t['bottleneck_criteria_title']}</h3>
                        <p><strong>{self.t['bottleneck_criteria_note']}</strong></p>
                        <ol style="margin: 10px 0; padding-left: 20px;">
                            <li>{self.t['bottleneck_condition_1']}</li>
                            <li>{self.t['bottleneck_condition_2']}</li>
                            <li>{self.t['bottleneck_condition_3']}</li>
                        </ol>
                    </div>
                </div>
                """
            else:
                # 无瓶颈：显示判定条件
                return f"""
                <div class="section">
                    <h2>&#9989; {self.t['system_bottleneck_analysis']}</h2>
                    
                    <div style="background: #d4edda; border: 1px solid #c3e6cb; padding: 15px; border-radius: 4px; margin: 15px 0;">
                        <h3 style="color: #155724; margin-top: 0;">&#9989; {self.t['no_system_bottleneck_detected']}</h3>
                    </div>
                    
                    <div style="background: #e7f3ff; border: 1px solid #b3d9ff; padding: 15px; border-radius: 4px; margin: 15px 0;">
                        <h3 style="margin-top: 0;">&#128203; {self.t['bottleneck_criteria_title']}</h3>
                        <p><strong>{self.t['bottleneck_criteria_note']}</strong></p>
                        <ol style="margin: 10px 0; padding-left: 20px;">
                            <li>{self.t['bottleneck_condition_1']}</li>
                            <li>{self.t['bottleneck_condition_2']}</li>
                            <li>{self.t['bottleneck_condition_3']}</li>
                        </ol>
                    </div>
                    
                    <div style="background: #f8f9fa; border: 1px solid #dee2e6; padding: 15px; border-radius: 4px; margin: 15px 0;">
                        <h3 style="margin-top: 0;">&#128202; {self.t['bottleneck_current_status']}</h3>
                        <p>{self.t['bottleneck_status_normal']}</p>
                    </div>
                </div>
                """
                
        except Exception as e:
            return f"""
            <div class="section error">
                <h2>&#9888; {self.t['bottleneck_info_display_error']}</h2>
                <p>{self.t['bottleneck_info_processing_failed']}: {str(e)}</p>
            </div>
            """

    def _get_css_styles(self):
        """Get CSS styles - enhanced version with chart display support"""
        return """
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background-color: #f5f7fa; 
            line-height: 1.6;
        }
        .container { 
            width: 95%;
            margin: 0 auto; 
            background-color: white; 
            padding: 30px; 
            border-radius: 12px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.1); 
        }
        .section { 
            margin: 30px 0; 
            padding: 20px; 
            border: 1px solid #e1e8ed; 
            border-radius: 8px; 
            background-color: #fafbfc;
        }
        .info { 
            background-color: #EBF5FB; 
            padding: 15px; 
            border-radius: 6px; 
            margin: 15px 0; 
            border-left: 4px solid #3498DB;
        }
        .success {
            background-color: #E8F8F5;
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
            border-left: 4px solid #27AE60;
        }
        .warning { 
            background-color: #FEF5E7; 
            padding: 15px; 
            border-radius: 6px; 
            margin: 15px 0; 
            border-left: 4px solid #F39C12; 
        }
        .warning tr.warning {
            background-color: #FEF5E7 !important;
        }
        .table-note {
            font-size: 0.9em;
            color: #666;
            margin-top: 10px;
            font-style: italic;
        }
        .error { 
            background-color: #FADBD8; 
            padding: 15px; 
            border-radius: 6px; 
            margin: 15px 0; 
            border-left: 4px solid #E74C3C; 
        }
        .bottleneck-alert { 
            background-color: #FEF5E7 !important; 
            border-left: 5px solid #E74C3C !important; 
        }
        .bottleneck-summary { 
            margin: 20px 0; 
        }
        .bottleneck-stats { 
            display: flex; 
            justify-content: space-around; 
            margin: 25px 0; 
            flex-wrap: wrap;
        }
        .stat-item { 
            text-align: center; 
            padding: 20px; 
            background-color: #f8f9fa; 
            border-radius: 10px; 
            min-width: 180px; 
            margin: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .stat-value { 
            margin-top: 10px; 
            font-weight: bold;
        }
        .bottleneck-details, .bottleneck-recommendations, .bottleneck-actions { 
            margin: 25px 0; 
        }
        
        /* Chart display styles */
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
            margin: 25px 0;
        }
        .chart-item {
            background-color: white;
            border: 1px solid #e1e8ed;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .chart-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.12);
        }
        .chart-item h3 {
            color: #2c3e50;
            margin-top: 0;
            margin-bottom: 15px;
            font-size: 1.2em;
            border-bottom: 2px solid #3498db;
            padding-bottom: 8px;
        }
        .chart-description {
            margin-bottom: 20px;
        }
        .chart-description p {
            color: #5a6c7d;
            font-size: 0.95em;
            margin: 0;
            line-height: 1.5;
        }
        .chart-container {
            text-align: center;
            background-color: #fafbfc;
            border-radius: 8px;
            padding: 15px;
            border: 1px solid #e9ecef;
        }
        .chart-image {
            max-width: 100%;
            height: auto;
            border-radius: 6px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s ease;
        }
        .chart-image:hover {
            transform: scale(1.02);
        }
        .charts-summary {
            background-color: #e8f5e8;
            padding: 20px;
            border-radius: 8px;
            margin: 25px 0;
            border-left: 4px solid #27AE60;
        }
        .charts-summary h3 {
            color: #155724;
            margin-top: 0;
        }
        .charts-summary ul {
            margin: 10px 0;
            padding-left: 20px;
        }
        .charts-summary li {
            margin: 8px 0;
            color: #155724;
        }
        .missing-charts {
            background-color: #FEF5E7;
            padding: 20px;
            border-radius: 8px;
            margin: 25px 0;
            border-left: 4px solid #ffc107;
        }
        .missing-charts h3 {
            color: #856404;
            margin-top: 0;
        }
        .missing-charts ul {
            margin: 10px 0;
            padding-left: 20px;
        }
        .missing-charts li {
            margin: 8px 0;
            color: #856404;
        }
        
        /* Block height statistics styles */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .stat-item {
            text-align: center;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #e9ecef;
        }
        .stat-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
        }
        .stat-label {
            font-size: 0.9em;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .file-info {
            margin-top: 20px;
            padding: 15px;
            background-color: #e8f4fd;
            border-radius: 6px;
            border-left: 4px solid #007bff;
        }
        .file-info code {
            background-color: #f1f3f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        
        /* Table styles */
        table { 
            width: 100%; 
            border-collapse: collapse; 
            margin: 15px 0; 
            background-color: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        th, td { 
            border: 1px solid #dee2e6; 
            padding: 12px 15px; 
            text-align: left; 
        }
        th { 
            background-color: #f8f9fa; 
            font-weight: 600;
            color: #495057;
        }
        tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        tr:hover {
            background-color: #e9ecef;
        }
        
        /* Heading styles */
        h1 { 
            color: #2c3e50; 
            text-align: center; 
            margin-bottom: 10px;
            font-size: 2.2em;
        }
        h2 { 
            color: #34495e; 
            border-bottom: 3px solid #2C3E50; 
            padding-bottom: 8px; 
            margin-top: 30px;
        }
        h3 { 
            color: #5a6c7d; 
            margin-top: 20px;
        }
        
        /* Responsive design */
        @media (max-width: 1200px) {
            .container {
                width: 98%;
                padding: 20px;
            }
            table {
                font-size: 0.9em;
            }
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 15px;
                margin: 10px;
                width: 98%;
            }
            .charts-grid {
                grid-template-columns: 1fr;
            }
            .chart-grid {
                grid-template-columns: 1fr;
            }
            .bottleneck-stats {
                flex-direction: column;
                align-items: center;
            }
            .stat-item {
                min-width: 250px;
            }
            table {
                font-size: 0.85em;
                display: block;
                overflow-x: auto;
                white-space: nowrap;
            }
            h1 {
                font-size: 1.5em;
            }
            h2 {
                font-size: 1.3em;
            }
        }
        
        /* Print styles */
        @media print {
            .container {
                box-shadow: none;
                border: 1px solid #ccc;
            }
            .chart-item:hover {
                transform: none;
                box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            }
            .chart-image:hover {
                transform: none;
            }
        }
        
        /* Chart Gallery Styles */
        .chart-summary {
            background-color: #e3f2fd;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #2196f3;
        }
        .chart-category {
            margin-bottom: 30px;
            background-color: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }
        .chart-category h3 {
            color: #1976d2;
            border-bottom: 2px solid #e3f2fd;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .chart-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-top: 15px;
        }
        .chart-item {
            background-color: #fafafa;
            border-radius: 8px;
            padding: 15px;
            border: 1px solid #e0e0e0;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .chart-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(0,0,0,0.12);
        }
        .chart-item h4 {
            color: #424242;
            margin-bottom: 10px;
            font-size: 1.1em;
        }
        .chart-container {
            text-align: center;
            background-color: white;
            border-radius: 6px;
            padding: 10px;
            border: 1px solid #e8e8e8;
        }
        .chart {
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            transition: transform 0.2s ease;
        }
        .chart:hover {
            transform: scale(1.02);
        }
        """

    def _generate_performance_summary(self, df):
        """Generate performance summary section"""
        try:
            # Calculate basic statistics
            cpu_avg = df['cpu_usage'].mean() if 'cpu_usage' in df.columns and len(df) > 0 else 0
            cpu_max = df['cpu_usage'].max() if 'cpu_usage' in df.columns and len(df) > 0 else 0
            mem_avg = df['mem_usage'].mean() if 'mem_usage' in df.columns and len(df) > 0 else 0
            
            # DATA Device statistics - using unified field format matching
            data_iops_cols = [col for col in df.columns if col.startswith('data_') and col.endswith('_total_iops')]
            data_iops_avg = df[data_iops_cols[0]].mean() if data_iops_cols and len(df) > 0 else 0
            
            # ACCOUNTS Device statistics - using unified field format matching
            accounts_iops_cols = [col for col in df.columns if col.startswith('accounts_') and col.endswith('_total_iops')]
            accounts_iops_avg = df[accounts_iops_cols[0]].mean() if accounts_iops_cols and len(df) > 0 else 0
            
            return f"""
            <div class="section">
                <h2>&#128202; {self.t['performance_summary']}</h2>
                <table style="width: 100%; border-collapse: collapse; margin-top: 15px; background: white;">
                    <thead>
                        <tr>
                            <th style="background: #2C3E50; color: white; padding: 12px; text-align: left;">{self.t['metric']}</th>
                            <th style="background: #2C3E50; color: white; padding: 12px; text-align: right;">{self.t['value']}</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td style="padding: 10px; border: 1px solid #ddd;">{self.t['avg_cpu_usage']}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: right; font-weight: bold;">{cpu_avg:.1f}%</td></tr>
                        <tr><td style="padding: 10px; border: 1px solid #ddd;">{self.t['peak_cpu_usage']}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: right; font-weight: bold;">{cpu_max:.1f}%</td></tr>
                        <tr><td style="padding: 10px; border: 1px solid #ddd;">{self.t['avg_memory_usage']}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: right; font-weight: bold;">{mem_avg:.1f}%</td></tr>
                        <tr><td style="padding: 10px; border: 1px solid #ddd;">{self.t['data_device_avg_iops']}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: right; font-weight: bold;">{data_iops_avg:.0f}</td></tr>
                        <tr><td style="padding: 10px; border: 1px solid #ddd;">{self.t['accounts_device_avg_iops']}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: right; font-weight: bold;">{accounts_iops_avg:.0f}</td></tr>
                        <tr><td style="padding: 10px; border: 1px solid #ddd;">{self.t['monitoring_data_points']}</td><td style="padding: 10px; border: 1px solid #ddd; text-align: right; font-weight: bold;">{len(df):,}</td></tr>
                    </tbody>
                </table>
            </div>
            """
        except Exception as e:
            return f"<div class='error'>{self.t['performance_summary_generation_failed']}: {str(e)}</div>"

def main():
    parser = argparse.ArgumentParser(description='Report Generator - Enhanced version + bottleneck mode support')
    parser.add_argument('performance_csv', help='System performance monitoring CSV file')
    parser.add_argument('-c', '--config', help='Configuration file', default='config_loader.sh')
    parser.add_argument('-o', '--overhead-csv', help='Monitoring overhead CSV file')
    parser.add_argument('--bottleneck-mode', action='store_true', help='Enable bottleneck analysis mode')
    parser.add_argument('--bottleneck-info', help='Bottleneck information JSON file path')
    parser.add_argument('--language', choices=['en', 'zh'], default='en', help='Report language (en or zh)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.performance_csv):
        print(f"❌ File does not exist: {args.performance_csv}")
        return 1
    
    # Check bottleneck information file
    bottleneck_info_file = None
    if args.bottleneck_mode or args.bottleneck_info:
        if args.bottleneck_info and os.path.exists(args.bottleneck_info):
            bottleneck_info_file = args.bottleneck_info
            print(f"📊 Using bottleneck information file: {bottleneck_info_file}")
        else:
            print("⚠️ Bottleneck mode enabled but bottleneck information file not found, will generate standard report")
    
    # Create generator with specified language
    generator = ReportGenerator(args.performance_csv, args.config, args.overhead_csv, bottleneck_info_file, args.language)
    
    result = generator.generate_html_report()
    
    if result:
        if bottleneck_info_file:
            print("🎉 Bottleneck mode HTML report generated successfully!")
        else:
            print("🎉 Enhanced HTML report generated successfully!")
        return 0
    else:
        print("❌ HTML report generation failed")
        return 1

if __name__ == "__main__":
    exit(main())
