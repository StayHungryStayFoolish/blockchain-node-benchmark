#!/usr/bin/env python3
"""
Unified Unit Converter - Solves unit inconsistency issues
Strictly uses binary units (KiB, MiB, GiB) for storage-related calculations
Uses decimal units (KB, MB, GB) for network-related calculations
"""

import sys
import os
from typing import Union, Dict, List

# Add project root directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.unified_logger import get_logger

logger = get_logger(__name__)


class UnitConverter:
    """Unified unit converter"""
    
    # Binary units (for storage)
    BINARY_UNITS = {
        'B': 1,
        'KiB': 1024,
        'MiB': 1024 ** 2,
        'GiB': 1024 ** 3,
        'TiB': 1024 ** 4
    }
    
    # Decimal units (for network)
    DECIMAL_UNITS = {
        'B': 1,
        'KB': 1000,
        'MB': 1000 ** 2,
        'GB': 1000 ** 3,
        'TB': 1000 ** 4
    }
    
    @classmethod
    def bytes_to_binary_unit(cls, bytes_value: Union[int, float], target_unit: str = 'MiB') -> float:
        """
        Convert bytes to binary unit (for storage-related calculations)
        
        Args:
            bytes_value: Number of bytes
            target_unit: Target unit (KiB, MiB, GiB, TiB)
            
        Returns:
            Converted value
        """
        if target_unit not in cls.BINARY_UNITS:
            raise ValueError(f"Unsupported binary unit: {target_unit}")
        
        # ✅ Add logging
        result = bytes_value / cls.BINARY_UNITS[target_unit]
        logger.debug(f"🔄 Binary unit conversion: {bytes_value} B → {result:.2f} {target_unit}")
        
        return result
    
    @classmethod
    def binary_unit_to_bytes(cls, value: Union[int, float], source_unit: str) -> int:
        """
        Convert binary unit to bytes
        
        Args:
            value: Numeric value
            source_unit: Source unit (KiB, MiB, GiB, TiB)
            
        Returns:
            Number of bytes
        """
        if source_unit not in cls.BINARY_UNITS:
            raise ValueError(f"Unsupported binary unit: {source_unit}")
        
        # ✅ Add logging
        result = int(value * cls.BINARY_UNITS[source_unit])
        logger.debug(f"🔄 Binary unit conversion: {value} {source_unit} → {result} B")
        
        return result
    
    @classmethod
    def bytes_to_decimal_unit(cls, bytes_value: Union[int, float], target_unit: str = 'MB') -> float:
        """
        Convert bytes to decimal unit (for network-related calculations)
        
        Args:
            bytes_value: Number of bytes
            target_unit: Target unit (KB, MB, GB, TB)
            
        Returns:
            Converted value
        """
        if target_unit not in cls.DECIMAL_UNITS:
            raise ValueError(f"Unsupported decimal unit: {target_unit}")
        
        # ✅ Add logging
        result = bytes_value / cls.DECIMAL_UNITS[target_unit]
        logger.debug(f"🔄 Decimal unit conversion: {bytes_value} B → {result:.2f} {target_unit}")
        
        return result
    
    @classmethod
    def decimal_unit_to_bytes(cls, value: Union[int, float], source_unit: str) -> int:
        """
        Convert decimal unit to bytes
        
        Args:
            value: Numeric value
            source_unit: Source unit (KB, MB, GB, TB)
            
        Returns:
            Number of bytes
        """
        if source_unit not in cls.DECIMAL_UNITS:
            raise ValueError(f"Unsupported decimal unit: {source_unit}")
        
        # ✅ Add logging
        result = int(value * cls.DECIMAL_UNITS[source_unit])
        logger.debug(f"🔄 Decimal unit conversion: {value} {source_unit} → {result} B")
        
        return result
    
    @classmethod
    def convert_storage_throughput(cls, kb_per_sec: Union[int, float]) -> Dict[str, float]:
        """
        Convert storage throughput (iostat output kB/s)
        
        Args:
            kb_per_sec: kB/s (iostat output, actually KiB/s)
            
        Returns:
            Dictionary containing various units
        """
        # iostat's kB/s is actually KiB/s (1024 bytes)
        bytes_per_sec = kb_per_sec * 1024
        
        return {
            'bytes_per_sec': bytes_per_sec,
            'kib_per_sec': kb_per_sec,  # Original value is KiB/s
            'mib_per_sec': cls.bytes_to_binary_unit(bytes_per_sec, 'MiB'),
            'gib_per_sec': cls.bytes_to_binary_unit(bytes_per_sec, 'GiB'),
            # Also provide decimal units for comparison
            'kb_per_sec_decimal': cls.bytes_to_decimal_unit(bytes_per_sec, 'KB'),
            'mb_per_sec_decimal': cls.bytes_to_decimal_unit(bytes_per_sec, 'MB')
        }
    
    @classmethod
    def convert_network_throughput(cls, bytes_per_sec: Union[int, float]) -> Dict[str, float]:
        """
        Convert network throughput (AWS standard, using Gbps)
        
        Args:
            bytes_per_sec: Bytes per second
            
        Returns:
            Dictionary containing various units, focusing on AWS standard Gbps
        """
        # Convert to bits per second (network base unit)
        bits_per_sec = bytes_per_sec * 8
        
        return {
            'bytes_per_sec': bytes_per_sec,
            'kb_per_sec': cls.bytes_to_decimal_unit(bytes_per_sec, 'KB'),
            'mb_per_sec': cls.bytes_to_decimal_unit(bytes_per_sec, 'MB'),
            'gb_per_sec': cls.bytes_to_decimal_unit(bytes_per_sec, 'GB'),
            # Network bit rate (AWS standard)
            'bps': bits_per_sec,
            'kbps': bits_per_sec / 1000,
            'mbps': bits_per_sec / 1000000,
            'gbps': bits_per_sec / 1000000000,  # AWS standard unit
            # Formatted display
            'aws_standard_gbps': round(bits_per_sec / 1000000000, 6),
            'aws_display_mbps': round(bits_per_sec / 1000000, 3)
        }
    
    @classmethod
    def convert_sar_network_data(cls, rx_kbs: Union[int, float], tx_kbs: Union[int, float]) -> Dict[str, float]:
        """
        Convert sar network data to AWS standard format
        
        Args:
            rx_kbs: Receive rate (kB/s, sar output)
            tx_kbs: Transmit rate (kB/s, sar output)
            
        Returns:
            AWS standard network metrics
        """
        # sar's kB/s is decimal KB/s
        rx_bytes_per_sec = rx_kbs * 1000
        tx_bytes_per_sec = tx_kbs * 1000
        total_bytes_per_sec = rx_bytes_per_sec + tx_bytes_per_sec
        
        # Convert to bit rate
        rx_bits_per_sec = rx_bytes_per_sec * 8
        tx_bits_per_sec = tx_bytes_per_sec * 8
        total_bits_per_sec = rx_bits_per_sec + tx_bits_per_sec
        
        return {
            # Byte rate
            'rx_bytes_per_sec': rx_bytes_per_sec,
            'tx_bytes_per_sec': tx_bytes_per_sec,
            'total_bytes_per_sec': total_bytes_per_sec,
            
            # Bit rate (network standard)
            'rx_bps': rx_bits_per_sec,
            'tx_bps': tx_bits_per_sec,
            'total_bps': total_bits_per_sec,
            
            # Mbps
            'rx_mbps': round(rx_bits_per_sec / 1000000, 3),
            'tx_mbps': round(tx_bits_per_sec / 1000000, 3),
            'total_mbps': round(total_bits_per_sec / 1000000, 3),
            
            # Gbps (AWS standard)
            'rx_gbps': round(rx_bits_per_sec / 1000000000, 6),
            'tx_gbps': round(tx_bits_per_sec / 1000000000, 6),
            'total_gbps': round(total_bits_per_sec / 1000000000, 6),
            
            # AWS standard display format
            'aws_rx_gbps': f"{rx_bits_per_sec / 1000000000:.6f}",
            'aws_tx_gbps': f"{tx_bits_per_sec / 1000000000:.6f}",
            'aws_total_gbps': f"{total_bits_per_sec / 1000000000:.6f}"
        }
    
    @classmethod
    def convert_aws_ebs_metrics(cls, iostat_data: Dict) -> Dict[str, float]:
        """
        Convert AWS EBS metrics (strictly following AWS documentation)
        
        Args:
            iostat_data: iostat data dictionary containing r/s, w/s, rkB/s, wkB/s, etc.
            
        Returns:
            AWS EBS standard metrics
        """
        # Calculate total IOPS
        total_iops = iostat_data.get('r_s', 0) + iostat_data.get('w_s', 0)
        
        # Calculate total throughput (iostat's kB/s is actually KiB/s)
        read_kib_s = iostat_data.get('rkB_s', 0)
        write_kib_s = iostat_data.get('wkB_s', 0)
        total_kib_s = read_kib_s + write_kib_s
        
        # Convert to various units
        throughput_conversions = cls.convert_storage_throughput(total_kib_s)
        
        # Calculate average I/O size
        avg_io_size_kib = total_kib_s / total_iops if total_iops > 0 else 0
        
        # AWS EBS standard IOPS (16 KiB baseline)
        aws_standard_iops = total_iops * (avg_io_size_kib / 16) if avg_io_size_kib > 0 else total_iops
        
        return {
            'total_iops': total_iops,
            'read_iops': iostat_data.get('r_s', 0),
            'write_iops': iostat_data.get('w_s', 0),
            'total_throughput_kib_s': total_kib_s,
            'total_throughput_mib_s': throughput_conversions['mib_per_sec'],
            'total_throughput_mb_s': throughput_conversions['mb_per_sec_decimal'],
            'avg_io_size_kib': avg_io_size_kib,
            'aws_standard_iops': aws_standard_iops,
            'read_latency_ms': iostat_data.get('r_await', 0),
            'write_latency_ms': iostat_data.get('w_await', 0),
            'avg_latency_ms': iostat_data.get('avg_await', 0),
            'queue_depth': iostat_data.get('aqu_sz', 0),
            'utilization_percent': iostat_data.get('util', 0)
        }
    
    @classmethod
    def format_storage_size(cls, bytes_value: Union[int, float], precision: int = 2) -> str:
        """
        Format storage size display (automatically select appropriate binary unit)
        
        Args:
            bytes_value: Number of bytes
            precision: Decimal places
            
        Returns:
            Formatted string
        """
        for unit in ['TiB', 'GiB', 'MiB', 'KiB']:
            if bytes_value >= cls.BINARY_UNITS[unit]:
                value = cls.bytes_to_binary_unit(bytes_value, unit)
                return f"{value:.{precision}f} {unit}"
        
        return f"{bytes_value:.0f} B"
    
    @classmethod
    def format_network_speed_aws_standard(cls, bits_per_sec: Union[int, float], precision: int = 3) -> str:
        """
        Format network speed display in AWS standard (prioritize Gbps)
        
        Args:
            bits_per_sec: Bits per second
            precision: Decimal places
            
        Returns:
            AWS standard format string
        """
        # AWS network bandwidth standard: prioritize Gbps
        gbps = bits_per_sec / 1000000000
        if gbps >= 1.0:
            return f"{gbps:.{precision}f} Gbps"
        
        mbps = bits_per_sec / 1000000
        if mbps >= 1.0:
            return f"{mbps:.{precision}f} Mbps"
        
        kbps = bits_per_sec / 1000
        if kbps >= 1.0:
            return f"{kbps:.{precision}f} Kbps"
        
        return f"{bits_per_sec:.0f} bps"
    
    @classmethod
    def validate_unit_consistency(cls, data_dict: Dict) -> Dict[str, Union[List[str], bool]]:
        """
        Validate unit consistency in data
        
        Args:
            data_dict: Data dictionary containing various metrics
            
        Returns:
            Validation results and recommendations
        """
        issues = []
        recommendations = []
        
        # Check if storage-related metrics use binary units
        storage_keys = [k for k in data_dict.keys() if any(term in k.lower() for term in ['throughput', 'iops', 'storage', 'disk', 'ebs'])]
        for key in storage_keys:
            if any(unit in str(data_dict[key]) for unit in ['KB', 'MB', 'GB']):
                issues.append(f"Storage metric {key} uses decimal units")
                recommendations.append(f"Recommend {key} to use binary units (KiB, MiB, GiB)")
        
        # Check if network-related metrics use decimal units
        network_keys = [k for k in data_dict.keys() if any(term in k.lower() for term in ['network', 'bandwidth', 'speed', 'bps'])]
        for key in network_keys:
            if any(unit in str(data_dict[key]) for unit in ['KiB', 'MiB', 'GiB']):
                issues.append(f"Network metric {key} uses binary units")
                recommendations.append(f"Recommend {key} to use decimal units (KB, MB, GB)")
        
        return {
            'issues': issues,
            'recommendations': recommendations,
            'is_consistent': len(issues) == 0
        }


# Convenience functions
def convert_iostat_to_standard_units(iostat_row: Dict) -> Dict[str, Union[float, str]]:
    """
    Convert iostat output to standard units
    
    Args:
        iostat_row: One row of iostat data
        
    Returns:
        Standardized data
    """
    converter = UnitConverter()
    
    # Convert AWS EBS metrics
    aws_metrics = converter.convert_aws_ebs_metrics(iostat_row)
    
    # Create result dictionary with formatted display
    result: Dict[str, Union[float, str]] = dict(aws_metrics)
    result['formatted_throughput'] = converter.format_storage_size(
        aws_metrics['total_throughput_kib_s'] * 1024
    ) + '/s'
    
    return result


def format_performance_metrics(metrics: Dict) -> Dict[str, str]:
    """
    Format performance metrics for display
    
    Args:
        metrics: Performance metrics dictionary
        
    Returns:
        Formatted metrics
    """
    converter = UnitConverter()
    formatted = {}
    
    for key, value in metrics.items():
        if 'throughput' in key.lower() and 'bytes' in key.lower():
            formatted[key] = converter.format_storage_size(value) + '/s'
        elif 'speed' in key.lower() or 'bandwidth' in key.lower():
            formatted[key] = converter.format_network_speed_aws_standard(value)
        elif isinstance(value, float):
            formatted[key] = f"{value:.2f}"
        else:
            formatted[key] = str(value)
    
    return formatted


# Usage examples
if __name__ == "__main__":
    print("📏 Unified Unit Converter Usage Examples:")
    
    converter = UnitConverter()
    
    # Storage throughput conversion
    print("\nStorage throughput conversion:")
    storage_result = converter.convert_storage_throughput(1024)  # 1024 KiB/s
    for unit, value in storage_result.items():
        print(f"  {unit}: {value:.2f}")
    
    # Network throughput conversion
    print("\nNetwork throughput conversion:")
    network_result = converter.convert_network_throughput(1048576)  # 1 MB/s
    for unit, value in network_result.items():
        print(f"  {unit}: {value:.2f}")
    
    # AWS EBS metrics conversion
    print("\nAWS EBS metrics conversion:")
    iostat_data = {
        'r_s': 100,
        'w_s': 50,
        'rkB_s': 1024,
        'wkB_s': 512,
        'r_await': 5.0,
        'w_await': 3.0,
        'avg_await': 4.0,
        'aqu_sz': 2.5,
        'util': 75.0
    }
    aws_result = converter.convert_aws_ebs_metrics(iostat_data)
    for metric, value in aws_result.items():
        print(f"  {metric}: {value:.2f}")
    
    # Formatted display
    print(f"\nFormatted display:")
    print(f"Storage size: {converter.format_storage_size(1073741824)}")  # 1 GiB
    print(f"Network speed: {converter.format_network_speed_aws_standard(1000000000)}")   # 1 Gbps
    
    # Test sar network data conversion
    print(f"\nsar network data conversion test:")
    sar_result = converter.convert_sar_network_data(125000, 125000)  # 125MB/s each
    print(f"Input: 125000 kB/s RX, 125000 kB/s TX")
    print(f"Output: {sar_result['aws_total_gbps']} Gbps (AWS standard)")
