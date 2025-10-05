#!/usr/bin/env python3
"""
统一设备管理系统
解决设备检测、标识、字段映射重复实现的问题
"""

import pandas as pd
import re
import os
from typing import Dict, List, Optional, Tuple

class DeviceManager:
    """统一设备管理器"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self._device_cache = {}
        self._field_cache = {}
        
    def get_device_name(self, logical_name: str) -> str:
        """提取设备的实际名称"""
        if logical_name in self._device_cache:
            return self._device_cache[logical_name]
            
        for col in self.df.columns:
            if col.startswith(f'{logical_name}_'):
                parts = col.split('_')
                if len(parts) >= 3:
                    device_name = parts[1]
                    self._device_cache[logical_name] = device_name
                    return device_name
        
        self._device_cache[logical_name] = 'unknown'
        return 'unknown'
    
    def is_device_configured(self, device_name: str) -> bool:
        """检查设备是否配置"""
        device_cols = [col for col in self.df.columns if col.startswith(f'{device_name}_')]
        return len(device_cols) > 0
    
    def get_configured_devices(self) -> List[str]:
        """获取所有已配置的设备"""
        devices = set()
        for col in self.df.columns:
            if '_' in col:
                device = col.split('_')[0]
                if device in ['data', 'accounts']:
                    devices.add(device)
        return list(devices)
    
    def get_mapped_field(self, field_name: str) -> Optional[str]:
        """智能字段映射"""
        if field_name in self._field_cache:
            return self._field_cache[field_name]
            
        # 直接匹配
        if field_name in self.df.columns:
            self._field_cache[field_name] = field_name
            return field_name
            
        # 模式匹配 - 扩展支持所有32张图表的字段
        patterns = {
            # EBS相关字段
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
            
            # ACCOUNTS设备字段
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
            
            # CPU字段 - 核心性能图表需要
            'cpu_usage': r'cpu_usage',
            'cpu_usr': r'cpu_usr', 
            'cpu_sys': r'cpu_sys',
            'cpu_iowait': r'cpu_iowait',
            'cpu_soft': r'cpu_soft',
            'cpu_idle': r'cpu_idle',
            
            # 内存字段
            'mem_usage': r'mem_usage',
            'mem_used': r'mem_used',
            'mem_total': r'mem_total',
            
            # 网络字段 - ENA分析需要
            'net_rx_mbps': r'net_rx_mbps',
            'net_tx_mbps': r'net_tx_mbps',
            'net_total_mbps': r'net_total_mbps',
            'net_rx_gbps': r'net_rx_gbps',
            'net_tx_gbps': r'net_tx_gbps',
            'net_total_gbps': r'net_total_gbps',
            'net_rx_pps': r'net_rx_pps',
            'net_tx_pps': r'net_tx_pps',
            'net_total_pps': r'net_total_pps',
            
            # ENA限制字段
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
        
        if field_name in patterns:
            pattern = patterns[field_name]
            for col in self.df.columns:
                if re.match(pattern, col):
                    self._field_cache[field_name] = col
                    return col
        
        self._field_cache[field_name] = None
        return None
    
    def create_chart_title(self, base_title: str) -> str:
        """创建包含设备信息的图表标题"""
        devices = self.get_configured_devices()
        
        if len(devices) == 0:
            return f"{base_title} (No Devices Configured)"
        elif len(devices) == 1:
            device_name = self.get_device_name(devices[0])
            return f"{base_title} - {devices[0].upper()} Device ({device_name})"
        else:
            device_info = []
            for device in sorted(devices):
                device_name = self.get_device_name(device)
                device_info.append(f"{device.upper()} ({device_name})")
            return f"{base_title} - {' & '.join(device_info)}"
    
    def get_device_fields(self, device: str, field_type: str) -> List[str]:
        """获取指定设备的特定类型字段"""
        pattern = f"{device}_.*_{field_type}"
        return [col for col in self.df.columns if re.match(pattern, col)]
    
    def get_baseline_values(self) -> Dict[str, Dict[str, float]]:
        """获取设备基准值"""
        return {
            'data': {
                'iops': float(os.getenv('DATA_VOL_MAX_IOPS', '3000')),
                'throughput': float(os.getenv('DATA_VOL_MAX_THROUGHPUT', '125'))
            },
            'accounts': {
                'iops': float(os.getenv('ACCOUNTS_VOL_MAX_IOPS', '3000')),
                'throughput': float(os.getenv('ACCOUNTS_VOL_MAX_THROUGHPUT', '125'))
            }
        }
    
    def get_threshold_values(self) -> Dict[str, float]:
        """获取阈值配置"""
        return {
            'ebs_util': float(os.getenv('BOTTLENECK_EBS_UTIL_THRESHOLD', '90')),
            'ebs_latency': float(os.getenv('BOTTLENECK_EBS_LATENCY_THRESHOLD', '50')),
            'ebs_iops': float(os.getenv('BOTTLENECK_EBS_IOPS_THRESHOLD', '90')),
            'ebs_throughput': float(os.getenv('BOTTLENECK_EBS_THROUGHPUT_THRESHOLD', '90'))
        }