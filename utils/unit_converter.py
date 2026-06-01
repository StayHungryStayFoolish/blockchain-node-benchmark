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
        storage_keys = [k for k in data_dict.keys() if any(term in k.lower() for term in ['throughput', 'iops', 'storage', 'disk'])]
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


# Usage examples
if __name__ == "__main__":
    print("📏 Unified Unit Converter Usage Examples:")
    
    converter = UnitConverter()
    
    # Storage throughput conversion
    print("\nStorage throughput conversion:")
    storage_result = converter.convert_storage_throughput(1024)  # 1024 KiB/s
    for unit, value in storage_result.items():
        print(f"  {unit}: {value:.2f}")
    
    # Formatted display
    print(f"\nFormatted display:")
    print(f"Storage size: {converter.format_storage_size(1073741824)}")  # 1 GiB
    
    # Test sar network data conversion
    print(f"\nsar network data conversion test:")
    sar_result = converter.convert_sar_network_data(125000, 125000)  # 125MB/s each
    print(f"Input: 125000 kB/s RX, 125000 kB/s TX")
    print(f"Output: {sar_result['aws_total_gbps']} Gbps (AWS standard)")
