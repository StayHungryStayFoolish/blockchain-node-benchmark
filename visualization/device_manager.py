"""
Device Manager - Unified device field mapping and configuration management
Supports all field requirements for 32 charts, integrates ACCOUNTS detection logic
"""

import pandas as pd
import re
import os
from typing import Dict, List, Optional, Any

from utils.csv_schema_registry import CSVSchemaRegistry

class DeviceManager:
    """Unified device manager - supports field mapping and device detection for 32 charts"""

    # provider_aware disk 逻辑名 (物理列名随 cloud_provider 变, reader 只认逻辑名).
    # 经 CSVSchemaRegistry 解析为物理列后缀, 不在本文件硬编码任何 aws_standard 字面量.
    _DISK_IOPS_LOGICAL = 'disk_iops_provider_adjusted'
    _DISK_THROUGHPUT_LOGICAL = 'disk_throughput_provider_adjusted'

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self._device_cache = {}
        self._field_cache = {}

        # 铁律: provider 从 CSV cloud_provider 列取 (不猜不硬编码、不读环境变量).
        # 用于经 CSVSchemaRegistry 解析 provider_aware disk 物理列后缀.
        self.cloud_provider = self._read_cloud_provider_from_csv()

        # 经 registry 解析出的 provider_aware disk 物理列后缀 (如 '_standard_iops').
        # 注意: 这是 CSV 字段名 (物理列), 区别于 get_threshold_values() 里的
        #       *_provisioned_iops / *_provisioned_throughput —— 那些是业务配置变量 (磁盘额定能力上限,
        #       来自卷规格环境变量 DATA_VOL_MAX_*, 利用率公式分母; ADR-0002 层3 定名 provisioned),
        #       不是 CSV 列名, 不经 registry 解析.
        self._disk_iops_suffix = self._resolve_disk_suffix(self._DISK_IOPS_LOGICAL)
        self._disk_throughput_suffix = self._resolve_disk_suffix(self._DISK_THROUGHPUT_LOGICAL)

        # Field mapping patterns - support all 32 charts' fields
        self.patterns = {
            # Disk DATA fields
            'data_total_iops': r'data_.*_total_iops',
            'data_util': r'data_.*_util',
            'data_avg_await': r'data_.*_avg_await',
            'data_aqu_sz': r'data_.*_aqu_sz',
            # provider_aware disk 列: 物理后缀由 CSVSchemaRegistry 解析 (随 cloud_provider 变),
            # 逻辑键名用三云中立 *_normalized_* (调用方按此名取数), 不再硬编码物理后缀, 不带厂商烙印.
            'data_normalized_iops': rf'data_.*{re.escape(self._disk_iops_suffix)}',
            'data_normalized_throughput_mibs': rf'data_.*{re.escape(self._disk_throughput_suffix)}',
            'data_total_throughput_mibs': r'data_.*_total_throughput_mibs',
            'data_r_s': r'data_.*_r_s',
            'data_w_s': r'data_.*_w_s',
            'data_rkb_s': r'data_.*_rkb_s',
            'data_wkb_s': r'data_.*_wkb_s',
            'data_r_await': r'data_.*_r_await',
            'data_w_await': r'data_.*_w_await',
            
            # Disk ACCOUNTS fields
            'accounts_total_iops': r'accounts_.*_total_iops',
            'accounts_util': r'accounts_.*_util',
            'accounts_avg_await': r'accounts_.*_avg_await',
            'accounts_aqu_sz': r'accounts_.*_aqu_sz',
            # provider_aware disk 列 (ACCOUNTS): 物理后缀由 CSVSchemaRegistry 解析.
            'accounts_normalized_iops': rf'accounts_.*{re.escape(self._disk_iops_suffix)}',
            'accounts_normalized_throughput_mibs': rf'accounts_.*{re.escape(self._disk_throughput_suffix)}',
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
            # Read/write separation fields - solve Disk device info for issues 10,11,12
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
    
    def _read_cloud_provider_from_csv(self):
        """从 CSV cloud_provider 列读取 provider (aws|gcp|other).

        铁律: provider 来源是 CSV 数据本身, 不运行时探测、不读环境变量.
        缺列或空值时回退 'other' (中立兜底, registry 三云同名, 不影响物理列名).
        """
        if self.df is not None and 'cloud_provider' in self.df.columns:
            series = self.df['cloud_provider'].dropna()
            if len(series) > 0:
                val = str(series.iloc[-1]).strip().lower()
                if val:
                    return val
        return 'other'

    def _resolve_disk_suffix(self, logical_name):
        """经 CSV Schema Registry 解析 provider_aware disk 逻辑名 -> 物理列后缀.

        registry.resolve(logical_name, provider, '') 把模板 {prefix} 替换为空,
        产出形如 '_standard_iops' / '_standard_throughput_mibs' 的物理后缀
        (随 cloud_provider 变). 真实 CSV 列名含运行时设备名
        (如 'data_nvme1n1_standard_iops'), 故只取后缀供正则匹配, 不保留任何裸字面量.
        """
        return CSVSchemaRegistry.resolve(logical_name, self.cloud_provider, '')

    def _resolve_disk_field(self, logical_name, device_prefix):
        """经 CSV Schema Registry 解析 provider_aware disk 字段 -> 实际 CSV 列名.

        logical_name: 'disk_iops_provider_adjusted' 或 'disk_throughput_provider_adjusted'.
        device_prefix: 逻辑设备前缀 'data' 或 'accounts'.
        返回匹配的真实列名 (含运行时设备名); 无匹配返回 None.
        """
        if self.df is None:
            return None
        suffix = self._resolve_disk_suffix(logical_name)
        physical = f'{device_prefix}{suffix}'  # 无运行时设备名拆分时的直接命中
        if physical in self.df.columns:
            return physical
        pattern = re.compile(rf'^{re.escape(device_prefix)}_.*{re.escape(suffix)}$')
        for col in self.df.columns:
            if pattern.match(col):
                return col
        return None

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
        # 注意 (区分业务变量与字段名):
        #   *_provisioned_iops / *_provisioned_throughput 是【业务配置变量】(磁盘额定能力上限),
        #   来自卷规格环境变量 (DATA_VOL_MAX_IOPS 等), 利用率公式的分母 (ADR-0002 层3 定名 provisioned).
        #   它们与 CSV 物理列 *_<dfp>_iops (provider_aware, 经 CSVSchemaRegistry 解析) 是
        #   两类不同概念, 不是 CSV 字段名, 故不经 registry.
        base_thresholds = {
            'data_provisioned_iops': int(float(os.getenv('DATA_VOL_MAX_IOPS', '20000'))),
            'data_provisioned_throughput': int(float(os.getenv('DATA_VOL_MAX_THROUGHPUT', '700'))),
            
            # Bottleneck thresholds
            'cpu_threshold': float(os.getenv('BOTTLENECK_CPU_THRESHOLD', '85')),
            'memory_threshold': float(os.getenv('BOTTLENECK_MEMORY_THRESHOLD', '90')),
            'disk_util_threshold': float(os.getenv('BOTTLENECK_DISK_UTIL_THRESHOLD', '90')),
            'disk_latency_threshold': float(os.getenv('BOTTLENECK_DISK_LATENCY_THRESHOLD', '50')),
            'disk_iops_threshold': float(os.getenv('BOTTLENECK_DISK_IOPS_THRESHOLD', '90')),
            'disk_throughput_threshold': float(os.getenv('BOTTLENECK_DISK_THROUGHPUT_THRESHOLD', '90')),
            
            # Calculate warning levels (80% and 40% of thresholds)
            'disk_util_warning': float(os.getenv('BOTTLENECK_DISK_UTIL_THRESHOLD', '90')) * 0.8,  # 72%
            'disk_latency_warning': float(os.getenv('BOTTLENECK_DISK_LATENCY_THRESHOLD', '50')) * 0.4,  # 20ms
        }
        
        # If ACCOUNTS device configured, add ACCOUNTS provisioned-ceiling values
        if self.is_accounts_configured():
            base_thresholds.update({
                'accounts_provisioned_iops': int(float(os.getenv('ACCOUNTS_VOL_MAX_IOPS', '20000'))),
                'accounts_provisioned_throughput': int(float(os.getenv('ACCOUNTS_VOL_MAX_THROUGHPUT', '700'))),
            })
        
        return base_thresholds
    
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
        disk_latency_threshold = int(thresholds['disk_latency_threshold'])
        disk_util_threshold = int(thresholds['disk_util_threshold'])
        
        return {
            'warning': int(thresholds['cpu_threshold']),                     # CPU threshold (%)
            'critical': disk_util_threshold,                                  # Disk utilization threshold (%)
            'io_warning': int(disk_latency_threshold * 0.4),                 # I/O latency warning: 50ms * 0.4 = 20ms
            'io_critical': disk_latency_threshold,                           # I/O latency critical: 50ms
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
    
    # === Field management methods extracted from Disk Generator ===
    
    def build_field_mapping(self):
        """Build Disk field name mapping - supports ACCOUNTS device optionality"""
        mapping = {}
        
        # Complete field suffix list - based on actual CSV data structure.
        # 注意: provider_aware 的 IOPS/吞吐物理后缀不在此硬编码 (随云变),
        #       由下方 _provider_aware_suffix_map 经 CSVSchemaRegistry 解析后单独并入.
        all_suffixes = [
            # base fields
            'util', 'aqu_sz',
            # IOPS-related fields (r_s corresponds to read_iops, w_s corresponds to write_iops)
            'r_s', 'w_s', 'total_iops',
            # Latency-related fields
            'r_await', 'w_await', 'avg_await',
            # Throughput-related fields
            'read_throughput_mibs', 'write_throughput_mibs', 'total_throughput_mibs'
        ]

        # provider_aware disk 字段: 业务别名(逻辑键) -> 物理后缀(经 registry 解析, 随云变).
        # 区分: 左侧是业务变量名(调用方按此名取数), 右侧是 registry 给出的 CSV 物理列后缀.
        provider_aware_suffix_map = {
            'normalized_iops': self._disk_iops_suffix.lstrip('_'),
            'normalized_throughput_mibs': self._disk_throughput_suffix.lstrip('_'),
        }

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
            # provider_aware 字段: 业务别名键固定, 物理后缀经 registry 解析后匹配真实列名
            for alias, phys_suffix in provider_aware_suffix_map.items():
                expected_field = f'{device}_{alias}'
                actual_field = self.find_field_by_pattern(f'{device}_.*_{phys_suffix}')
                if actual_field:
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
        
        # 业务层 metric_type -> 显示标签 (非 CSV 字段名). 这里的键是图表语义维度,
        # 不参与 CSV 列解析, 故保持原样, 不经 CSVSchemaRegistry.
        metric_map = {
            'normalized_iops': 'Normalized IOPS',
            'normalized_throughput': 'Normalized Throughput', 
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
    
    def get_disk_device_data(self, device_name, metric_type):
        """Get Disk device data - unified Disk data retrieval"""
        field_name = f"{device_name}_{metric_type}"
        return self.get_field_data(field_name)
    
    def validate_disk_configuration(self):
        """Validate Disk configuration integrity - solve configuration hardcoding for issue 8"""
        validation_result = {
            'data_configured': False,
            'accounts_configured': False,
            'missing_fields': [],
            'config_issues': []
        }
        
        # Check DATA device
        # 这些是业务逻辑别名 (经 get_mapped_field -> patterns -> CSVSchemaRegistry 解析为物理列),
        # 不是裸 CSV 字段名; provider_aware 的 *_normalized_iops 物理后缀已随云解析.
        data_fields = ['data_normalized_iops', 'data_util', 'data_avg_await']
        data_available, data_missing = self.check_data_availability(data_fields)
        validation_result['data_configured'] = len(data_available) > 0
        validation_result['missing_fields'].extend(data_missing)
        
        # Check ACCOUNTS device
        if self.is_accounts_configured():
            # 同上: 业务别名, 经 registry 解析为物理列名.
            accounts_fields = ['accounts_normalized_iops', 'accounts_util', 'accounts_avg_await']
            accounts_available, accounts_missing = self.check_data_availability(accounts_fields)
            validation_result['accounts_configured'] = len(accounts_available) > 0
            validation_result['missing_fields'].extend(accounts_missing)
        
        # Check configuration consistency
        thresholds = self.get_threshold_values()
        if thresholds['data_provisioned_iops'] == 20000:  # Default value, may be hardcoded
            validation_result['config_issues'].append('DATA provisioned IOPS may be hardcoded')
        
        return validation_result
