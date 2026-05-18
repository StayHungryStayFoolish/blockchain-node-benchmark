"""NetworkFieldRegistry - 字段语义类型注册表 (Y+ 架构 Python 侧)

与 bash get_network_field_metadata 1:1 对称, 但用静态查表避免每次调用 fork bash.

Usage:
    from utils.network_field_registry import NetworkFieldRegistry
    semantic = NetworkFieldRegistry.get_semantic_type('virtio_rx_drops')
    # -> 'drop_counter'

    fields_by_type = NetworkFieldRegistry.group_by_semantic(df.columns)
    # -> {'throughput': ['rx_bytes', 'tx_bytes'], 'drop_counter': ['virtio_rx_drops', ...], ...}
"""
from typing import Dict, List, Iterable, Any
import re


class NetworkFieldRegistry:
    # 静态映射 - 与 bash get_network_field_metadata 完全对称
    # 顺序: 精确匹配优先, 通配次之
    _SEMANTIC_MAP: Dict[str, str] = {
        # 跨平台统一字段
        'rx_bytes': 'throughput',
        'tx_bytes': 'throughput',
        'rx_packets': 'packet_count',
        'tx_packets': 'packet_count',
        'network_saturation_signal': 'saturation_signal',

        # AWS ENA 字段 (saturation_counter × 5 + gauge × 1)
        'ena_bw_in_exceeded': 'saturation_counter',
        'ena_bw_out_exceeded': 'saturation_counter',
        'ena_pps_exceeded': 'saturation_counter',
        'ena_conntrack_exceeded': 'saturation_counter',
        'ena_linklocal_exceeded': 'saturation_counter',
        'ena_conntrack_available': 'gauge',

        # GCP gVNIC 字段 (drop_counter × 2 + error_counter × 1)
        'gvnic_tx_drops': 'drop_counter',
        'gvnic_rx_no_buffer': 'drop_counter',
        'gvnic_tx_timeout': 'error_counter',

        # GCP virtio 字段 (drop_counter × 4 + error_counter × 1)
        'virtio_rx_drops': 'drop_counter',
        'virtio_rx_xdp_drops': 'drop_counter',
        'virtio_tx_xdp_tx_drops': 'drop_counter',
        'virtio_per_queue_rx_drops_sum': 'drop_counter',
        'virtio_tx_tx_timeouts': 'error_counter',
    }

    VALID_SEMANTIC_TYPES = {
        'throughput', 'packet_count', 'saturation_counter',
        'drop_counter', 'error_counter', 'saturation_signal',
        'gauge', 'unknown'
    }

    @classmethod
    def get_semantic_type(cls, field_name: str) -> str:
        """查询字段的 semantic_type. 未注册字段返回 'unknown'."""
        return cls._SEMANTIC_MAP.get(field_name, 'unknown')

    @classmethod
    def group_by_semantic(cls, fields: Iterable[str]) -> Dict[str, List[str]]:
        """把字段列表按 semantic_type 分组."""
        groups: Dict[str, List[str]] = {}
        for f in fields:
            semantic = cls.get_semantic_type(f)
            groups.setdefault(semantic, []).append(f)
        return groups

    @classmethod
    def is_platform_specific(cls, field_name: str) -> bool:
        """判断字段是否平台特异 (有 ena_/gvnic_/virtio_ 前缀)."""
        return bool(re.match(r'^(ena|gvnic|virtio)_', field_name))

    @classmethod
    def get_platform_prefix(cls, field_name: str) -> str:
        """提取平台前缀. 无前缀返回 'common'."""
        m = re.match(r'^(ena|gvnic|virtio)_', field_name)
        return m.group(1) if m else 'common'

    @classmethod
    def validate_csv_columns(cls, columns: List[str]) -> Dict[str, Any]:
        """验证 CSV 列符合 Y+ 不变量:
           - 必含 5 列 (rx_bytes/tx_bytes/rx_packets/tx_packets/network_saturation_signal)
           - 末列是 network_saturation_signal
           - 平台前缀一致 (不能 ena_* 和 gvnic_* 共存于同一 CSV)
        """
        required = {'rx_bytes', 'tx_bytes', 'rx_packets', 'tx_packets', 'network_saturation_signal'}
        missing = required - set(columns)

        prefixes = set()
        for c in columns:
            p = cls.get_platform_prefix(c)
            if p != 'common':
                prefixes.add(p)

        last_col_is_saturation = bool(columns) and columns[-1] == 'network_saturation_signal'

        return {
            'valid': len(missing) == 0 and len(prefixes) <= 1 and last_col_is_saturation,
            'missing_required': sorted(missing),
            'platform_prefixes': sorted(prefixes),
            'last_col_is_saturation': last_col_is_saturation,
        }
