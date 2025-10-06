"""
设备管理器 - 统一的设备字段映射和配置管理
支持32张图表的所有字段需求，整合ACCOUNTS判断逻辑
"""

import pandas as pd
import re
import os
from typing import Dict, List, Optional, Any

class DeviceManager:
    """统一设备管理器 - 支持32张图表的字段映射和设备检测"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self._device_cache = {}
        self._field_cache = {}
        
        # 字段映射模式 - 支持所有32张图表的字段
        self.patterns = {
            # EBS DATA字段
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
            
            # EBS ACCOUNTS字段
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
            
            # CPU字段
            'cpu_usage': r'cpu_usage',
            'cpu_usr': r'cpu_usr',
            'cpu_sys': r'cpu_sys',
            'cpu_iowait': r'cpu_iowait',
            'cpu_soft': r'cpu_soft',
            'cpu_idle': r'cpu_idle',
            
            # 内存字段
            'mem_used': r'mem_used',
            'mem_total': r'mem_total',
            'mem_usage': r'mem_usage',
            
            # 网络字段
            'net_rx_mbps': r'net_rx_mbps',
            'net_tx_mbps': r'net_tx_mbps',
            'net_total_mbps': r'net_total_mbps',
            'net_rx_gbps': r'net_rx_gbps',
            'net_tx_gbps': r'net_tx_gbps',
            'net_total_gbps': r'net_total_gbps',
            'net_rx_pps': r'net_rx_pps',
            'net_tx_pps': r'net_tx_pps',
            'net_total_pps': r'net_total_pps',
            
            # ENA字段
            'bw_in_allowance_exceeded': r'bw_in_allowance_exceeded',
            'bw_out_allowance_exceeded': r'bw_out_allowance_exceeded',
            'pps_allowance_exceeded': r'pps_allowance_exceeded',
            'conntrack_allowance_exceeded': r'conntrack_allowance_exceeded',
            'linklocal_allowance_exceeded': r'linklocal_allowance_exceeded',
            'conntrack_allowance_available': r'conntrack_allowance_available',
            
            # 监控开销字段
            'monitoring_iops_per_sec': r'monitoring_iops_per_sec',
            'monitoring_throughput_mibs_per_sec': r'monitoring_throughput_mibs_per_sec',
            
            # 区块链字段
            'local_block_height': r'local_block_height',
            'mainnet_block_height': r'mainnet_block_height',
            'block_height_diff': r'block_height_diff',
            'local_health': r'local_health',
            'mainnet_health': r'mainnet_health',
            'data_loss': r'data_loss',
            
            # QPS性能字段
            'current_qps': r'current_qps',
            'rpc_latency_ms': r'rpc_latency_ms',
            'qps_data_available': r'qps_data_available',
        }
    
    def get_mapped_field(self, field_name):
        """获取映射后的字段名 - 使用patterns进行精确匹配"""
        # 使用缓存提高性能
        if field_name in self._field_cache:
            return self._field_cache[field_name]
        
        # 直接字段匹配
        if field_name in self.df.columns:
            self._field_cache[field_name] = field_name
            return field_name
        
        # 使用patterns进行正则匹配
        if field_name in self.patterns:
            pattern = self.patterns[field_name]
            for col in self.df.columns:
                if re.match(pattern, col):
                    self._field_cache[field_name] = col
                    return col
        
        # 兜底：简单字符串匹配
        for col in self.df.columns:
            if field_name in col or col.endswith(field_name.split('_')[-1]):
                self._field_cache[field_name] = col
                return col
        
        self._field_cache[field_name] = None
        return None
    
    def is_accounts_configured(self):
        """统一的ACCOUNTS设备配置检测方法
        
        整合框架中的两套判断逻辑：
        1. 环境变量检查 (performance_visualizer.py逻辑)
        2. 数据列存在性检查 (ebs_chart_generator.py逻辑)
        """
        # 方法1: 检查环境变量配置
        accounts_device = os.getenv('ACCOUNTS_DEVICE', '')
        if not accounts_device:
            # 如果环境变量未设置，直接检查数据列
            return self._check_device_data_exists('accounts')
        
        # 方法2: 检查数据列是否存在
        return self._check_device_data_exists('accounts')
    
    def _check_device_data_exists(self, logical_name: str) -> bool:
        """检查设备数据列是否存在"""
        if self.df is None:
            return False
        
        # 检查设备相关列是否存在
        device_cols = [col for col in self.df.columns if col.startswith(f'{logical_name}_')]
        has_data = len(device_cols) > 0
        
        if has_data:
            # 进一步检查是否有有效数据（非全零）
            for col in device_cols[:3]:  # 检查前3列即可
                if col in self.df.columns:
                    non_zero_count = (self.df[col] != 0).sum()
                    if non_zero_count > 0:
                        return True
        
        return False
    
    def get_device_info_text(self):
        """获取设备信息文本 - 用于图表标题和说明"""
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
        """创建包含设备信息的图表标题"""
        device_info = self.get_device_info_text()
        return f"{base_title} - {device_info['title_suffix']}"
    
    def get_threshold_values(self):
        """从配置文件获取阈值配置"""
        # 基础阈值配置
        base_thresholds = {
            'data_baseline_iops': int(os.getenv('DATA_VOL_MAX_IOPS', '20000')),
            'data_baseline_throughput': int(os.getenv('DATA_VOL_MAX_THROUGHPUT', '700')),
            
            # 瓶颈阈值
            'cpu_threshold': float(os.getenv('BOTTLENECK_CPU_THRESHOLD', '85')),
            'memory_threshold': float(os.getenv('BOTTLENECK_MEMORY_THRESHOLD', '90')),
            'ebs_util_threshold': float(os.getenv('BOTTLENECK_EBS_UTIL_THRESHOLD', '90')),
            'ebs_latency_threshold': float(os.getenv('BOTTLENECK_EBS_LATENCY_THRESHOLD', '50')),
            'ebs_iops_threshold': float(os.getenv('BOTTLENECK_EBS_IOPS_THRESHOLD', '90')),
            'ebs_throughput_threshold': float(os.getenv('BOTTLENECK_EBS_THROUGHPUT_THRESHOLD', '90')),
            
            # 计算警告级别 (阈值的80%和40%)
            'ebs_util_warning': float(os.getenv('BOTTLENECK_EBS_UTIL_THRESHOLD', '90')) * 0.8,  # 72%
            'ebs_latency_warning': float(os.getenv('BOTTLENECK_EBS_LATENCY_THRESHOLD', '50')) * 0.4,  # 20ms
        }
        
        # 如果ACCOUNTS设备配置了，添加ACCOUNTS基准值
        if self.is_accounts_configured():
            base_thresholds.update({
                'accounts_baseline_iops': int(os.getenv('ACCOUNTS_VOL_MAX_IOPS', '20000')),
                'accounts_baseline_throughput': int(os.getenv('ACCOUNTS_VOL_MAX_THROUGHPUT', '700')),
            })
        
        return base_thresholds
    
    def get_baseline_values(self):
        """获取基准值配置 - 用于计算利用率"""
        thresholds = self.get_threshold_values()
        
        return {
            'data_baseline_iops': thresholds['data_baseline_iops'],
            'data_baseline_throughput': thresholds['data_baseline_throughput'],
            'accounts_baseline_iops': thresholds['accounts_baseline_iops'],
            'accounts_baseline_throughput': thresholds['accounts_baseline_throughput']
        }
    
    def get_qps_display_value(self):
        """获取正确的QPS显示值"""
        current_qps_field = self.get_mapped_field('current_qps')
        
        if current_qps_field and current_qps_field in self.df.columns:
            # 使用实际QPS值，不是目标值
            actual_qps = self.df[current_qps_field].iloc[-1]  # 最后一次记录
            return actual_qps
        
        return None
    
    def get_visualization_thresholds(self):
        """获取可视化阈值配置 - 整合自performance_visualizer.py"""
        # 获取基础阈值
        thresholds = self.get_threshold_values()
        
        # 计算可视化专用阈值
        ebs_latency_threshold = int(thresholds['ebs_latency_threshold'])
        ebs_util_threshold = int(thresholds['ebs_util_threshold'])
        
        return {
            'warning': int(thresholds['cpu_threshold']),                     # CPU阈值 (%)
            'critical': ebs_util_threshold,                                  # EBS利用率阈值 (%)
            'io_warning': int(ebs_latency_threshold * 0.4),                 # I/O延迟警告: 50ms * 0.4 = 20ms
            'io_critical': ebs_latency_threshold,                           # I/O延迟临界: 50ms
            'memory': int(thresholds['memory_threshold']),                  # 内存阈值 (%)
            'network': int(os.getenv('BOTTLENECK_NETWORK_THRESHOLD', '80')) # 网络阈值 (%)
        }
    
    def format_summary_text(self, device_info, data_stats, accounts_stats=None):
        """统一的文本格式化函数 - 整合自performance_visualizer.py"""
        lines = [f"Analysis Summary ({device_info}):", ""]
        
        # DATA设备统计
        lines.extend([
            "DATA Device:",
            f"  Mean: {data_stats['mean']:.2f}{data_stats['unit']}",
            f"  Max: {data_stats['max']:.2f}{data_stats['unit']}",
            f"  Violations: {data_stats['violations']}",
            ""
        ])
        
        # ACCOUNTS设备统计
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
    
    # === 从EBS Generator提取的字段管理方法 ===
    
    def build_field_mapping(self):
        """构建EBS字段名称映射 - 支持ACCOUNTS设备可选性"""
        mapping = {}
        
        # 完整的字段后缀列表 - 基于实际CSV数据结构
        all_suffixes = [
            # AWS和基础字段
            'aws_standard_iops', 'aws_standard_throughput_mibs', 'util', 'aqu_sz',
            # IOPS相关字段 (r_s对应read_iops, w_s对应write_iops)
            'r_s', 'w_s', 'total_iops',
            # 延迟相关字段
            'r_await', 'w_await', 'avg_await',
            # 吞吐量相关字段
            'read_throughput_mibs', 'write_throughput_mibs', 'total_throughput_mibs'
        ]
        
        # 检查设备可用性
        available_devices = []
        
        # DATA设备 - 必须存在
        data_fields = [col for col in self.df.columns if col.startswith('data_')]
        if data_fields:
            available_devices.append('data')
        
        # ACCOUNTS设备 - 可选存在
        accounts_fields = [col for col in self.df.columns if col.startswith('accounts_')]
        if accounts_fields:
            available_devices.append('accounts')
        
        # 只为可用设备构建映射
        for device in available_devices:
            for suffix in all_suffixes:
                expected_field = f'{device}_{suffix}'
                actual_field = self.find_field_by_pattern(f'{device}_.*_{suffix}')
                if actual_field:  # 只映射实际存在的字段
                    mapping[expected_field] = actual_field
        
        # 特殊映射：将常用的简化字段名映射到实际字段
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
        """根据模式查找实际字段名"""
        import re
        for col in self.df.columns:
            if re.match(pattern, col):
                return col
        return None
    
    def get_field_data(self, field_name):
        """安全获取字段数据 - 使用映射后的字段名"""
        mapped_field = self.get_mapped_field(field_name)
        if mapped_field and mapped_field in self.df.columns:
            return self.df[mapped_field]
        return None
    
    def has_field(self, field_name):
        """检查字段是否存在 - 使用映射后的字段名"""
        mapped_field = self.get_mapped_field(field_name)
        return mapped_field and mapped_field in self.df.columns
