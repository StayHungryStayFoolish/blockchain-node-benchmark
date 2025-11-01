"""
Device Manager - Unified device field mapping and configuration management
Supports all field requirements for 32 charts, integrates ACCOUNTS detection logic
"""

import pandas as pd
import re
import os
from typing import Dict, List, Optional, Any

class DeviceManager:
    """Unified device manager - supports field mapping and device detection for 32 charts"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self._device_cache = {}
        self._field_cache = {}
        
        # Field mapping patterns - support all 32 charts' fields
        self.patterns = {
            # EBS DATA fields
            'data_total_iops': r'data_.*_total_iops',
            'data_util': r'data_.*_util',
            'data_avg_await': r'data_.*_avg_await',
            'data_aqu_sz': r'data_.*_aqu_sz',
            'data_aws_standard_iops': r'data_.*_aws_standard_iops',
            'data_aws_standard_throughput_mibs': r'data_.*_aws_standard_throughput_mibs',
            'data_total_throughput_mibs': r'data_.*_total_throughput_mibs',
            'data_r_s': r'data_.*_r_s',
            'data_w_s': r'data_.*_w_s',
            'data_rkb_s': r'data_.*_rkb_s',
            'data_wkb_s': r'data_.*_wkb_s',
            'data_r_await': r'data_.*_r_await',
            'data_w_await': r'data_.*_w_await',
            
            # EBS ACCOUNTS fields
            'accounts_total_iops': r'accounts_.*_total_iops',
            'accounts_util': r'accounts_.*_util',
            'accounts_avg_await': r'accounts_.*_avg_await',
            'accounts_aqu_sz': r'accounts_.*_aqu_sz',
            'accounts_aws_standard_iops': r'accounts_.*_aws_standard_iops',
            'accounts_aws_standard_throughput_mibs': r'accounts_.*_aws_standard_throughput_mibs',
            'accounts_total_throughput_mibs': r'accounts_.*_total_throughput_mibs',
            'accounts_r_s': r'accounts_.*_r_s',
            'accounts_w_s': r'accounts_.*_w_s',
            'accounts_rkb_s': r'accounts_.*_rkb_s',
            'accounts_wkb_s': r'accounts_.*_wkb_s',
            'accounts_r_await': r'accounts_.*_r_await',
            'accounts_w_await': r'accounts_.*_w_await',
            
            # CPU fields
            'cpu_usage': r'cpu_usage',
            'cpu_usr': r'cpu_usr',
            'cpu_sys': r'cpu_sys',
            'cpu_iowait': r'cpu_iowait',
            'cpu_soft': r'cpu_soft',
            'cpu_idle': r'cpu_idle',
            
            # Memory fields
            'mem_used': r'mem_used',
            'mem_total': r'mem_total',
            'mem_usage': r'mem_usage',
            
            # Network fields
            'net_rx_mbps': r'net_rx_mbps',
            'net_tx_mbps': r'net_tx_mbps',
            'net_total_mbps': r'net_total_mbps',
            'net_rx_gbps': r'net_rx_gbps',
            'net_tx_gbps': r'net_tx_gbps',
            'net_total_gbps': r'net_total_gbps',
            'net_rx_pps': r'net_rx_pps',
            'net_tx_pps': r'net_tx_pps',
            'net_total_pps': r'net_total_pps',
            
            # ENA fields
            'bw_in_allowance_exceeded': r'bw_in_allowance_exceeded',
            'bw_out_allowance_exceeded': r'bw_out_allowance_exceeded',
            'pps_allowance_exceeded': r'pps_allowance_exceeded',
            'conntrack_allowance_exceeded': r'conntrack_allowance_exceeded',
            'linklocal_allowance_exceeded': r'linklocal_allowance_exceeded',
            'ena_bw_in_allowance_exceeded': r'ena_bw_in_allowance_exceeded',
            'ena_bw_out_allowance_exceeded': r'ena_bw_out_allowance_exceeded',
            'ena_pps_allowance_exceeded': r'ena_pps_allowance_exceeded',
            'ena_conntrack_allowance_available': r'ena_conntrack_allowance_available',
            'ena_conntrack_allowance_exceeded': r'ena_conntrack_allowance_exceeded',
            
            # Monitoring overhead fields - use correct field names
            'monitoring_cpu_percent': r'monitoring_cpu',  # Actual field name
            'monitoring_mem_percent': r'monitoring_memory_percent',  # Actual field name
            'monitoring_iops_per_sec': r'monitoring_iops.*sec',
            'monitoring_throughput_mibs_per_sec': r'monitoring_throughput.*sec',
            
            # QPS fields
            'qps_actual': r'current_qps',  # Map to actual existing field
            'qps_target': r'current_qps',  # Map to actual existing field
            
            # Blockchain fields
            'block_height': r'local_block_height',  # Map to actual field
            'data_loss_blocks': r'data_loss',  # Fix mapping
            'conntrack_allowance_available': r'conntrack_allowance_available',
            
            # Blockchain fields
            'local_block_height': r'local_block_height',
            'mainnet_block_height': r'mainnet_block_height',
            'block_height_diff': r'block_height_diff',
            'local_health': r'local_health',
            'mainnet_health': r'mainnet_health',
            'data_loss': r'data_loss',
            
            # QPS performance fields
            'current_qps': r'current_qps',
            'rpc_latency_ms': r'rpc_latency_ms',
            'qps_data_available': r'qps_data_available',
            
            # Extended field mapping - solve field requirements for 21 issues
            # Read/write separation fields - solve EBS device info for issues 10,11,12
            'data_read_iops': r'data_.*_r_s',
            'data_write_iops': r'data_.*_w_s', 
            'accounts_read_iops': r'accounts_.*_r_s',
            'accounts_write_iops': r'accounts_.*_w_s',
            
            # Read/write latency fields
            'data_read_latency': r'data_.*_r_await',
            'data_write_latency': r'data_.*_w_await',
            'accounts_read_latency': r'accounts_.*_r_await', 
            'accounts_write_latency': r'accounts_.*_w_await',
            
            # Read/write throughput fields
            'data_read_throughput': r'data_.*_rkb_s',
            'data_write_throughput': r'data_.*_wkb_s',
            'accounts_read_throughput': r'accounts_.*_rkb_s',
            'accounts_write_throughput': r'accounts_.*_wkb_s',
        }
    
    def get_mapped_field(self, field_name):
        """Get mapped field name - use patterns for precise matching"""
        # Use cache for performance
        if field_name in self._field_cache:
            return self._field_cache[field_name]
        
        # Direct field matching
        if field_name in self.df.columns:
            self._field_cache[field_name] = field_name
            return field_name
        
        # Use patterns for regex matching
        if field_name in self.patterns:
            pattern = self.patterns[field_name]
            for col in self.df.columns:
                if re.match(pattern, col):
                    self._field_cache[field_name] = col
                    return col
        
        # Fallback: simple string matching
        for col in self.df.columns:
            if field_name in col or col.endswith(field_name.split('_')[-1]):
                self._field_cache[field_name] = col
                return col
        
        self._field_cache[field_name] = None
        return None
    
    @staticmethod
    def is_accounts_configured(df=None):
        """Unified ACCOUNTS device configuration detection method
        
        Detection logic (configuration-driven first, data validation second):
        1. Primary condition: Check if environment variables are configured (determine if ACCOUNTS device exists)
        2. Secondary condition (optional): If df is provided, additionally validate data columns exist
        
        Args:
            df: Optional DataFrame, if provided will additionally validate data columns
        
        Returns:
            bool: Whether ACCOUNTS device is configured
        """
        # Primary condition: Check environment variables (configuration-driven)
        accounts_device = os.getenv('ACCOUNTS_DEVICE', '').strip()
        accounts_vol_type = os.getenv('ACCOUNTS_VOL_TYPE', '').strip()
        accounts_max_iops = os.getenv('ACCOUNTS_VOL_MAX_IOPS', '').strip()
        
        env_configured = bool(accounts_device and accounts_vol_type and accounts_max_iops)
        
        # If environment variables not configured, return False directly
        if not env_configured:
            # Fallback: If df provided, check data columns (for reading historical data scenario)
            if df is not None:
                accounts_cols = [col for col in df.columns if col.startswith('accounts_')]
                return len(accounts_cols) > 0
            return False
        
        # Environment variables configured, optional: validate data columns
        if df is not None:
            accounts_cols = [col for col in df.columns if col.startswith('accounts_')]
            if len(accounts_cols) == 0:
                # Environment variables configured, but no accounts_ columns in data (abnormal situation)
                return False
        
        return True
    
    def _check_device_data_exists(self, logical_name: str) -> bool:
        """Check if device data columns exist"""
        if self.df is None:
            return False
        
        # Check if device-related columns exist
        device_cols = [col for col in self.df.columns if col.startswith(f'{logical_name}_')]
        has_data = len(device_cols) > 0
        
        if has_data:
            # Further check if there's valid data (not all zeros)
            for col in device_cols[:3]:  # Check first 3 columns is enough
                if col in self.df.columns:
                    non_zero_count = (self.df[col] != 0).sum()
                    if non_zero_count > 0:
                        return True
        
        return False
    
    def get_device_info_text(self):
        """Get device info text - for chart titles and descriptions"""
        accounts_configured = self.is_accounts_configured()
        
        if accounts_configured:
            return {
                'title_suffix': 'DATA & ACCOUNTS Devices',
                'short_info': 'DATA+ACCOUNTS',
                'device_count': 2,
                'devices': ['DATA', 'ACCOUNTS']
            }
        else:
            return {
                'title_suffix': 'DATA Device Only', 
                'short_info': 'DATA',
                'device_count': 1,
                'devices': ['DATA']
            }
    
    def create_chart_title(self, base_title):
        """Create chart title with device info"""
        device_info = self.get_device_info_text()
        return f"{base_title} - {device_info['title_suffix']}"
    
    def get_threshold_values(self):
        """Get threshold configuration from config file"""
        # Base threshold configuration
        base_thresholds = {
            'data_baseline_iops': int(float(os.getenv('DATA_VOL_MAX_IOPS', '20000'))),
            'data_baseline_throughput': int(float(os.getenv('DATA_VOL_MAX_THROUGHPUT', '700'))),
            
            # Bottleneck thresholds
            'cpu_threshold': float(os.getenv('BOTTLENECK_CPU_THRESHOLD', '85')),
            'memory_threshold': float(os.getenv('BOTTLENECK_MEMORY_THRESHOLD', '90')),
            'ebs_util_threshold': float(os.getenv('BOTTLENECK_EBS_UTIL_THRESHOLD', '90')),
            'ebs_latency_threshold': float(os.getenv('BOTTLENECK_EBS_LATENCY_THRESHOLD', '50')),
            'ebs_iops_threshold': float(os.getenv('BOTTLENECK_EBS_IOPS_THRESHOLD', '90')),
            'ebs_throughput_threshold': float(os.getenv('BOTTLENECK_EBS_THROUGHPUT_THRESHOLD', '90')),
            
            # Calculate warning levels (80% and 40% of thresholds)
            'ebs_util_warning': float(os.getenv('BOTTLENECK_EBS_UTIL_THRESHOLD', '90')) * 0.8,  # 72%
            'ebs_latency_warning': float(os.getenv('BOTTLENECK_EBS_LATENCY_THRESHOLD', '50')) * 0.4,  # 20ms
        }
        
        # If ACCOUNTS device configured, add ACCOUNTS baseline values
        if self.is_accounts_configured():
            base_thresholds.update({
                'accounts_baseline_iops': int(float(os.getenv('ACCOUNTS_VOL_MAX_IOPS', '20000'))),
                'accounts_baseline_throughput': int(float(os.getenv('ACCOUNTS_VOL_MAX_THROUGHPUT', '700'))),
            })
        
        return base_thresholds
    
    def get_baseline_values(self):
        """Get baseline configuration - for calculating utilization"""
        thresholds = self.get_threshold_values()
        
        return {
            'data_baseline_iops': thresholds['data_baseline_iops'],
            'data_baseline_throughput': thresholds['data_baseline_throughput'],
            'accounts_baseline_iops': thresholds['accounts_baseline_iops'],
            'accounts_baseline_throughput': thresholds['accounts_baseline_throughput']
        }
    
    def get_qps_display_value(self):
        """Get correct QPS display value"""
        current_qps_field = self.get_mapped_field('current_qps')
        
        if current_qps_field and current_qps_field in self.df.columns:
            # Use actual QPS value, not target value
            actual_qps = self.df[current_qps_field].iloc[-1]  # Last record
            return actual_qps
        
        return None
    
    def get_visualization_thresholds(self):
        """Get visualization threshold configuration - integrated from performance_visualizer.py"""
        # Get base thresholds
        thresholds = self.get_threshold_values()
        
        # Calculate visualization-specific thresholds
        ebs_latency_threshold = int(thresholds['ebs_latency_threshold'])
        ebs_util_threshold = int(thresholds['ebs_util_threshold'])
        
        return {
            'warning': int(thresholds['cpu_threshold']),                     # CPU threshold (%)
            'critical': ebs_util_threshold,                                  # EBS utilization threshold (%)
            'io_warning': int(ebs_latency_threshold * 0.4),                 # I/O latency warning: 50ms * 0.4 = 20ms
            'io_critical': ebs_latency_threshold,                           # I/O latency critical: 50ms
            'memory': int(thresholds['memory_threshold']),                  # Memory threshold (%)
            'network': int(os.getenv('BOTTLENECK_NETWORK_THRESHOLD', '80')) # Network threshold (%)
        }
    
    def format_summary_text(self, device_info, data_stats, accounts_stats=None):
        """Unified text formatting function - integrated from performance_visualizer.py"""
        lines = [f"Analysis Summary ({device_info}):", ""]
        
        # DATA device statistics
        lines.extend([
            "DATA Device:",
            f"  Mean: {data_stats['mean']:.2f}{data_stats['unit']}",
            f"  Max: {data_stats['max']:.2f}{data_stats['unit']}",
            f"  Violations: {data_stats['violations']}",
            ""
        ])
        
        # ACCOUNTS device statistics
        if accounts_stats:
            lines.extend([
                "ACCOUNTS Device:",
                f"  Mean: {accounts_stats['mean']:.2f}{accounts_stats['unit']}",
                f"  Max: {accounts_stats['max']:.2f}{accounts_stats['unit']}",
                f"  Violations: {accounts_stats['violations']}"
            ])
        else:
            lines.append("ACCOUNTS Device: Not Configured")
        
        return "\n".join(lines)
    
    # === Field management methods extracted from EBS Generator ===
    
    def build_field_mapping(self):
        """Build EBS field name mapping - supports ACCOUNTS device optionality"""
        mapping = {}
        
        # Complete field suffix list - based on actual CSV data structure
        all_suffixes = [
            # AWS and base fields
            'aws_standard_iops', 'aws_standard_throughput_mibs', 'util', 'aqu_sz',
            # IOPS-related fields (r_s corresponds to read_iops, w_s corresponds to write_iops)
            'r_s', 'w_s', 'total_iops',
            # Latency-related fields
            'r_await', 'w_await', 'avg_await',
            # Throughput-related fields
            'read_throughput_mibs', 'write_throughput_mibs', 'total_throughput_mibs'
        ]
        
        # Check device availability
        available_devices = []
        
        # DATA device - must exist
        data_fields = [col for col in self.df.columns if col.startswith('data_')]
        if data_fields:
            available_devices.append('data')
        
        # ACCOUNTS device - optional
        accounts_fields = [col for col in self.df.columns if col.startswith('accounts_')]
        if accounts_fields:
            available_devices.append('accounts')
        
        # Build mapping only for available devices
        for device in available_devices:
            for suffix in all_suffixes:
                expected_field = f'{device}_{suffix}'
                actual_field = self.find_field_by_pattern(f'{device}_.*_{suffix}')
                if actual_field:  # Only map actually existing fields
                    mapping[expected_field] = actual_field
        
        # Special mapping: map commonly used simplified field names to actual fields
        if 'data' in available_devices:
            mapping.update({
                'data_read_iops': self.find_field_by_pattern(r'data_.*_r_s'),
                'data_write_iops': self.find_field_by_pattern(r'data_.*_w_s')
            })
        
        if 'accounts' in available_devices:
            mapping.update({
                'accounts_read_iops': self.find_field_by_pattern(r'accounts_.*_r_s'),
                'accounts_write_iops': self.find_field_by_pattern(r'accounts_.*_w_s')
            })
            
        return mapping
    
    def find_field_by_pattern(self, pattern):
        """Find actual field name by pattern"""
        for col in self.df.columns:
            if re.match(pattern, col):
                return col
        return None
    
    def get_field_data(self, field_name):
        """Safely get field data - use mapped field name"""
        mapped_field = self.get_mapped_field(field_name)
        if mapped_field and mapped_field in self.df.columns:
            return self.df[mapped_field]
        return None
    
    def has_field(self, field_name):
        """Check if field exists - use mapped field name"""
        mapped_field = self.get_mapped_field(field_name)
        return mapped_field and mapped_field in self.df.columns
    
    def get_device_label(self, device_name, metric_type):
        """Get device label - solve device info missing for issues 8,10,11,12"""
        device_map = {
            'data': 'DATA Device',
            'accounts': 'ACCOUNTS Device'
        }
        
        metric_map = {
            'aws_standard_iops': 'AWS Standard IOPS',
            'aws_standard_throughput': 'AWS Standard Throughput', 
            'utilization': 'Utilization',
            'latency': 'Average Latency',
            'efficiency': 'Efficiency (MiB/IOPS)'
        }
        
        device_label = device_map.get(device_name.lower(), device_name)
        metric_label = metric_map.get(metric_type, metric_type)
        
        return f"{device_label} {metric_label}"
    
    def get_qps_actual_value(self):
        """Get actual QPS value - solve QPS display error for issue 3"""
        current_qps_field = self.get_mapped_field('current_qps')
        
        if current_qps_field and current_qps_field in self.df.columns:
            # Get QPS value from last valid record
            qps_data = self.df[current_qps_field].dropna()
            if len(qps_data) > 0:
                return qps_data.iloc[-1]  # Last record
        
        return None
    
    def check_data_availability(self, field_list):
        """Check data availability - solve data missing for issues 14,15,16"""
        available_fields = {}
        missing_fields = []
        
        for field in field_list:
            mapped_field = self.get_mapped_field(field)
            if mapped_field and mapped_field in self.df.columns:
                # Check if there's valid data
                data = self.df[mapped_field].dropna()
                if len(data) > 0 and not (data == 0).all():
                    available_fields[field] = mapped_field
                else:
                    missing_fields.append(field)
            else:
                missing_fields.append(field)
        
        return available_fields, missing_fields
    
    def get_memory_fields(self):
        """Get memory-related fields - solve memory data missing for issue 15"""
        memory_fields = ['mem_used', 'mem_total', 'mem_usage']
        return self.check_data_availability(memory_fields)
    
    def get_monitoring_fields(self):
        """Get monitoring overhead fields - solve monitoring data missing for issues 14,15"""
        monitoring_fields = ['monitoring_iops_per_sec', 'monitoring_throughput_mibs_per_sec']
        return self.check_data_availability(monitoring_fields)
    
    def create_device_aware_title(self, base_title):
        """Create device-aware title - unified title format"""
        device_info = self.get_device_info_text()
        return f"{base_title} - {device_info['title_suffix']}"
    
    def get_ebs_device_data(self, device_name, metric_type):
        """Get EBS device data - unified EBS data retrieval"""
        field_name = f"{device_name}_{metric_type}"
        return self.get_field_data(field_name)
    
    def validate_ebs_configuration(self):
        """Validate EBS configuration integrity - solve configuration hardcoding for issue 8"""
        validation_result = {
            'data_configured': False,
            'accounts_configured': False,
            'missing_fields': [],
            'config_issues': []
        }
        
        # Check DATA device
        data_fields = ['data_aws_standard_iops', 'data_util', 'data_avg_await']
        data_available, data_missing = self.check_data_availability(data_fields)
        validation_result['data_configured'] = len(data_available) > 0
        validation_result['missing_fields'].extend(data_missing)
        
        # Check ACCOUNTS device
        if self.is_accounts_configured():
            accounts_fields = ['accounts_aws_standard_iops', 'accounts_util', 'accounts_avg_await']
            accounts_available, accounts_missing = self.check_data_availability(accounts_fields)
            validation_result['accounts_configured'] = len(accounts_available) > 0
            validation_result['missing_fields'].extend(accounts_missing)
        
        # Check configuration consistency
        thresholds = self.get_threshold_values()
        if thresholds['data_baseline_iops'] == 20000:  # Default value, may be hardcoded
            validation_result['config_issues'].append('DATA baseline IOPS may be hardcoded')
        
        return validation_result
