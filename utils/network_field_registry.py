"""NetworkFieldRegistry - network field semantic registry

Python-side mirror of the bash get_network_field_metadata behavior. Uses a
static lookup table so callers do not need to fork bash on every lookup.

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
    # Static mapping aligned with bash get_network_field_metadata.
    # Exact matches come first, wildcard-style handling can be added later.
    _SEMANTIC_MAP: Dict[str, str] = {
        # Cross-provider fields.
        'rx_bytes': 'throughput',
        'tx_bytes': 'throughput',
        'rx_packets': 'packet_count',
        'tx_packets': 'packet_count',
        'network_saturation_signal': 'saturation_signal',

        # AWS ENA fields (five saturation counters and one gauge).
        'ena_bw_in_exceeded': 'saturation_counter',
        'ena_bw_out_exceeded': 'saturation_counter',
        'ena_pps_exceeded': 'saturation_counter',
        'ena_conntrack_exceeded': 'saturation_counter',
        'ena_linklocal_exceeded': 'saturation_counter',
        'ena_conntrack_available': 'gauge',

        # GCP gVNIC fields (two drop counters and one error counter).
        'gvnic_tx_drops': 'drop_counter',
        'gvnic_rx_no_buffer': 'drop_counter',
        'gvnic_tx_timeout': 'error_counter',

        # GCP virtio fields (four drop counters and one error counter).
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
        """Return a field's semantic_type; unknown fields return 'unknown'."""
        return cls._SEMANTIC_MAP.get(field_name, 'unknown')

    @classmethod
    def group_by_semantic(cls, fields: Iterable[str]) -> Dict[str, List[str]]:
        """Group field names by semantic_type."""
        groups: Dict[str, List[str]] = {}
        for f in fields:
            semantic = cls.get_semantic_type(f)
            groups.setdefault(semantic, []).append(f)
        return groups

    @classmethod
    def is_platform_specific(cls, field_name: str) -> bool:
        """Return whether a field has an ena_/gvnic_/virtio_ provider prefix."""
        return bool(re.match(r'^(ena|gvnic|virtio)_', field_name))

    @classmethod
    def get_platform_prefix(cls, field_name: str) -> str:
        """Extract the provider prefix; fields without a prefix return 'common'."""
        m = re.match(r'^(ena|gvnic|virtio)_', field_name)
        return m.group(1) if m else 'common'

    @classmethod
    def validate_csv_columns(cls, columns: List[str]) -> Dict[str, Any]:
        """Validate CSV columns against provider-aware invariants:
           - required common fields are present
           - the last column is network_saturation_signal
           - provider prefixes are consistent within one CSV
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
