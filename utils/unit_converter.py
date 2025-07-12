#!/usr/bin/env python3
"""
统一单位转换器 - 解决单位不统一问题
严格使用二进制单位 (KiB, MiB, GiB) 进行存储相关计算
使用十进制单位 (KB, MB, GB) 进行网络相关计算
"""

from typing import Union, Dict, List
from utils.unified_logger import get_logger

logger = get_logger(__name__)


class UnitConverter:
    """统一单位转换器"""
    
    # 二进制单位 (用于存储)
    BINARY_UNITS = {
        'B': 1,
        'KiB': 1024,
        'MiB': 1024 ** 2,
        'GiB': 1024 ** 3,
        'TiB': 1024 ** 4
    }
    
    # 十进制单位 (用于网络)
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
        将字节转换为二进制单位 (用于存储相关计算)
        
        Args:
            bytes_value: 字节数
            target_unit: 目标单位 (KiB, MiB, GiB, TiB)
            
        Returns:
            转换后的值
        """
        if target_unit not in cls.BINARY_UNITS:
            raise ValueError(f"不支持的二进制单位: {target_unit}")
        
        # ✅ 添加日志记录
        result = bytes_value / cls.BINARY_UNITS[target_unit]
        logger.debug(f"🔄 二进制单位转换: {bytes_value} B → {result:.2f} {target_unit}")
        
        return result
    
    @classmethod
    def binary_unit_to_bytes(cls, value: Union[int, float], source_unit: str) -> int:
        """
        将二进制单位转换为字节
        
        Args:
            value: 数值
            source_unit: 源单位 (KiB, MiB, GiB, TiB)
            
        Returns:
            字节数
        """
        if source_unit not in cls.BINARY_UNITS:
            raise ValueError(f"不支持的二进制单位: {source_unit}")
        
        # ✅ 添加日志记录
        result = int(value * cls.BINARY_UNITS[source_unit])
        logger.debug(f"🔄 二进制单位转换: {value} {source_unit} → {result} B")
        
        return result
    
    @classmethod
    def bytes_to_decimal_unit(cls, bytes_value: Union[int, float], target_unit: str = 'MB') -> float:
        """
        将字节转换为十进制单位 (用于网络相关计算)
        
        Args:
            bytes_value: 字节数
            target_unit: 目标单位 (KB, MB, GB, TB)
            
        Returns:
            转换后的值
        """
        if target_unit not in cls.DECIMAL_UNITS:
            raise ValueError(f"不支持的十进制单位: {target_unit}")
        
        # ✅ 添加日志记录
        result = bytes_value / cls.DECIMAL_UNITS[target_unit]
        logger.debug(f"🔄 十进制单位转换: {bytes_value} B → {result:.2f} {target_unit}")
        
        return result
    
    @classmethod
    def decimal_unit_to_bytes(cls, value: Union[int, float], source_unit: str) -> int:
        """
        将十进制单位转换为字节
        
        Args:
            value: 数值
            source_unit: 源单位 (KB, MB, GB, TB)
            
        Returns:
            字节数
        """
        if source_unit not in cls.DECIMAL_UNITS:
            raise ValueError(f"不支持的十进制单位: {source_unit}")
        
        # ✅ 添加日志记录
        result = int(value * cls.DECIMAL_UNITS[source_unit])
        logger.debug(f"🔄 十进制单位转换: {value} {source_unit} → {result} B")
        
        return result
    
    @classmethod
    def convert_storage_throughput(cls, kb_per_sec: Union[int, float]) -> Dict[str, float]:
        """
        转换存储吞吐量 (iostat输出的kB/s)
        
        Args:
            kb_per_sec: kB/s (iostat输出，实际是KiB/s)
            
        Returns:
            包含各种单位的字典
        """
        # iostat的kB/s实际上是KiB/s (1024字节)
        bytes_per_sec = kb_per_sec * 1024
        
        return {
            'bytes_per_sec': bytes_per_sec,
            'kib_per_sec': kb_per_sec,  # 原值就是KiB/s
            'mib_per_sec': cls.bytes_to_binary_unit(bytes_per_sec, 'MiB'),
            'gib_per_sec': cls.bytes_to_binary_unit(bytes_per_sec, 'GiB'),
            # 也提供十进制单位用于对比
            'kb_per_sec_decimal': cls.bytes_to_decimal_unit(bytes_per_sec, 'KB'),
            'mb_per_sec_decimal': cls.bytes_to_decimal_unit(bytes_per_sec, 'MB')
        }
    
    @classmethod
    def convert_network_throughput(cls, bytes_per_sec: Union[int, float]) -> Dict[str, float]:
        """
        转换网络吞吐量 (符合AWS标准，使用Gbps)
        
        Args:
            bytes_per_sec: 字节/秒
            
        Returns:
            包含各种单位的字典，重点是AWS标准的Gbps
        """
        # 转换为比特/秒 (网络的基础单位)
        bits_per_sec = bytes_per_sec * 8
        
        return {
            'bytes_per_sec': bytes_per_sec,
            'kb_per_sec': cls.bytes_to_decimal_unit(bytes_per_sec, 'KB'),
            'mb_per_sec': cls.bytes_to_decimal_unit(bytes_per_sec, 'MB'),
            'gb_per_sec': cls.bytes_to_decimal_unit(bytes_per_sec, 'GB'),
            # 网络比特率 (AWS标准)
            'bps': bits_per_sec,
            'kbps': bits_per_sec / 1000,
            'mbps': bits_per_sec / 1000000,
            'gbps': bits_per_sec / 1000000000,  # AWS标准单位
            # 格式化显示
            'aws_standard_gbps': round(bits_per_sec / 1000000000, 6),
            'aws_display_mbps': round(bits_per_sec / 1000000, 3)
        }
    
    @classmethod
    def convert_sar_network_data(cls, rx_kbs: Union[int, float], tx_kbs: Union[int, float]) -> Dict[str, float]:
        """
        转换sar网络数据为AWS标准格式
        
        Args:
            rx_kbs: 接收速率 (kB/s，sar输出)
            tx_kbs: 发送速率 (kB/s，sar输出)
            
        Returns:
            AWS标准的网络指标
        """
        # sar的kB/s是十进制KB/s
        rx_bytes_per_sec = rx_kbs * 1000
        tx_bytes_per_sec = tx_kbs * 1000
        total_bytes_per_sec = rx_bytes_per_sec + tx_bytes_per_sec
        
        # 转换为比特率
        rx_bits_per_sec = rx_bytes_per_sec * 8
        tx_bits_per_sec = tx_bytes_per_sec * 8
        total_bits_per_sec = rx_bits_per_sec + tx_bits_per_sec
        
        return {
            # 字节率
            'rx_bytes_per_sec': rx_bytes_per_sec,
            'tx_bytes_per_sec': tx_bytes_per_sec,
            'total_bytes_per_sec': total_bytes_per_sec,
            
            # 比特率 (网络标准)
            'rx_bps': rx_bits_per_sec,
            'tx_bps': tx_bits_per_sec,
            'total_bps': total_bits_per_sec,
            
            # Mbps
            'rx_mbps': round(rx_bits_per_sec / 1000000, 3),
            'tx_mbps': round(tx_bits_per_sec / 1000000, 3),
            'total_mbps': round(total_bits_per_sec / 1000000, 3),
            
            # Gbps (AWS标准)
            'rx_gbps': round(rx_bits_per_sec / 1000000000, 6),
            'tx_gbps': round(tx_bits_per_sec / 1000000000, 6),
            'total_gbps': round(total_bits_per_sec / 1000000000, 6),
            
            # AWS标准显示格式
            'aws_rx_gbps': f"{rx_bits_per_sec / 1000000000:.6f}",
            'aws_tx_gbps': f"{tx_bits_per_sec / 1000000000:.6f}",
            'aws_total_gbps': f"{total_bits_per_sec / 1000000000:.6f}"
        }
    
    @classmethod
    def convert_aws_ebs_metrics(cls, iostat_data: Dict) -> Dict[str, float]:
        """
        转换AWS EBS指标 (严格按照AWS文档)
        
        Args:
            iostat_data: iostat数据字典，包含r/s, w/s, rkB/s, wkB/s等
            
        Returns:
            AWS EBS标准指标
        """
        # 计算总IOPS
        total_iops = iostat_data.get('r_s', 0) + iostat_data.get('w_s', 0)
        
        # 计算总吞吐量 (iostat的kB/s实际是KiB/s)
        read_kib_s = iostat_data.get('rkB_s', 0)
        write_kib_s = iostat_data.get('wkB_s', 0)
        total_kib_s = read_kib_s + write_kib_s
        
        # 转换为各种单位
        throughput_conversions = cls.convert_storage_throughput(total_kib_s)
        
        # 计算平均I/O大小
        avg_io_size_kib = total_kib_s / total_iops if total_iops > 0 else 0
        
        # AWS EBS标准IOPS (16 KiB基准)
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
        格式化存储大小显示 (自动选择合适的二进制单位)
        
        Args:
            bytes_value: 字节数
            precision: 小数位数
            
        Returns:
            格式化的字符串
        """
        for unit in ['TiB', 'GiB', 'MiB', 'KiB']:
            if bytes_value >= cls.BINARY_UNITS[unit]:
                value = cls.bytes_to_binary_unit(bytes_value, unit)
                return f"{value:.{precision}f} {unit}"
        
        return f"{bytes_value:.0f} B"
    
    @classmethod
    def format_network_speed_aws_standard(cls, bits_per_sec: Union[int, float], precision: int = 3) -> str:
        """
        按AWS标准格式化网络速度显示 (优先使用Gbps)
        
        Args:
            bits_per_sec: 比特/秒
            precision: 小数位数
            
        Returns:
            AWS标准格式的字符串
        """
        # AWS网络带宽标准：优先使用Gbps
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
        验证数据中的单位一致性
        
        Args:
            data_dict: 包含各种指标的数据字典
            
        Returns:
            验证结果和建议
        """
        issues = []
        recommendations = []
        
        # 检查存储相关指标是否使用二进制单位
        storage_keys = [k for k in data_dict.keys() if any(term in k.lower() for term in ['throughput', 'iops', 'storage', 'disk', 'ebs'])]
        for key in storage_keys:
            if any(unit in str(data_dict[key]) for unit in ['KB', 'MB', 'GB']):
                issues.append(f"存储指标 {key} 使用了十进制单位")
                recommendations.append(f"建议 {key} 使用二进制单位 (KiB, MiB, GiB)")
        
        # 检查网络相关指标是否使用十进制单位
        network_keys = [k for k in data_dict.keys() if any(term in k.lower() for term in ['network', 'bandwidth', 'speed', 'bps'])]
        for key in network_keys:
            if any(unit in str(data_dict[key]) for unit in ['KiB', 'MiB', 'GiB']):
                issues.append(f"网络指标 {key} 使用了二进制单位")
                recommendations.append(f"建议 {key} 使用十进制单位 (KB, MB, GB)")
        
        return {
            'issues': issues,
            'recommendations': recommendations,
            'is_consistent': len(issues) == 0
        }


# 便捷函数
def convert_iostat_to_standard_units(iostat_row: Dict) -> Dict[str, Union[float, str]]:
    """
    将iostat输出转换为标准单位
    
    Args:
        iostat_row: iostat的一行数据
        
    Returns:
        标准化的数据
    """
    converter = UnitConverter()
    
    # 转换AWS EBS指标
    aws_metrics = converter.convert_aws_ebs_metrics(iostat_row)
    
    # 创建包含格式化显示的结果字典
    result: Dict[str, Union[float, str]] = dict(aws_metrics)
    result['formatted_throughput'] = converter.format_storage_size(
        aws_metrics['total_throughput_kib_s'] * 1024
    ) + '/s'
    
    return result


def format_performance_metrics(metrics: Dict) -> Dict[str, str]:
    """
    格式化性能指标用于显示
    
    Args:
        metrics: 性能指标字典
        
    Returns:
        格式化后的指标
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


# 使用示例
if __name__ == "__main__":
    print("📏 统一单位转换器使用示例:")
    
    converter = UnitConverter()
    
    # 存储吞吐量转换
    print("\n存储吞吐量转换:")
    storage_result = converter.convert_storage_throughput(1024)  # 1024 KiB/s
    for unit, value in storage_result.items():
        print(f"  {unit}: {value:.2f}")
    
    # 网络吞吐量转换
    print("\n网络吞吐量转换:")
    network_result = converter.convert_network_throughput(1048576)  # 1 MB/s
    for unit, value in network_result.items():
        print(f"  {unit}: {value:.2f}")
    
    # AWS EBS指标转换
    print("\nAWS EBS指标转换:")
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
    
    # 格式化显示
    print(f"\n格式化显示:")
    print(f"存储大小: {converter.format_storage_size(1073741824)}")  # 1 GiB
    print(f"网络速度: {converter.format_network_speed_aws_standard(1000000000)}")   # 1 Gbps
    
    # 测试sar网络数据转换
    print(f"\nsar网络数据转换测试:")
    sar_result = converter.convert_sar_network_data(125000, 125000)  # 125MB/s each
    print(f"输入: 125000 kB/s RX, 125000 kB/s TX")
    print(f"输出: {sar_result['aws_total_gbps']} Gbps (AWS标准)")
