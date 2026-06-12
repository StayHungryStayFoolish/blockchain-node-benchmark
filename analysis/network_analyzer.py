"""NetworkAnalyzer - provider-aware NIC data reader

No platform branches are needed here. The analyzer groups fields by
NetworkFieldRegistry.get_semantic_type and downstream code should avoid
hardcoded literal matching for 'ena_*', 'gvnic_*', or 'virtio_*' names.

Usage:
    import pandas as pd
    from analysis.network_analyzer import NetworkAnalyzer

    df = pd.read_csv('network_metrics.csv')
    results = NetworkAnalyzer.analyze(df)
    # -> {'throughput': {...}, 'saturation': {...}, 'drops': {...}, ...}
"""
from typing import Dict, Any, List
import pandas as pd

from utils.network_field_registry import NetworkFieldRegistry


class NetworkAnalyzer:

    @classmethod
    def analyze(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze columns grouped by semantic_type."""
        validation = NetworkFieldRegistry.validate_csv_columns(list(df.columns))

        groups = NetworkFieldRegistry.group_by_semantic(df.columns)

        results: Dict[str, Any] = {
            'csv_validation': validation,
            'platform_detected': cls._detect_platform_from_columns(df.columns),
            'sample_count': len(df),
        }

        # Throughput fields.
        if 'throughput' in groups:
            results['throughput'] = cls._analyze_throughput(df, groups['throughput'])

        # Packet-count fields.
        if 'packet_count' in groups:
            results['packet_count'] = cls._analyze_packet_count(df, groups['packet_count'])

        # saturation_counter (AWS ENA limit counters)
        if 'saturation_counter' in groups:
            results['saturation_counters'] = cls._analyze_saturation_counters(df, groups['saturation_counter'])

        # drop_counter (GCP gVNIC/virtio drop counters)
        if 'drop_counter' in groups:
            results['drop_counters'] = cls._analyze_drop_counters(df, groups['drop_counter'])

        # error_counter
        if 'error_counter' in groups:
            results['error_counters'] = cls._analyze_error_counters(df, groups['error_counter'])

        # saturation_signal - cross-provider aligned core metric.
        if 'saturation_signal' in groups:
            results['saturation_ratio'] = cls._analyze_saturation_signal(df, groups['saturation_signal'])

        return results

    @classmethod
    def _detect_platform_from_columns(cls, columns: List[str]) -> str:
        """Infer platform variant from field prefixes."""
        prefixes = {NetworkFieldRegistry.get_platform_prefix(c) for c in columns} - {'common'}
        if not prefixes:
            return 'other_none'
        prefix = next(iter(prefixes))
        mapping = {'ena': 'aws_ena', 'gvnic': 'gcp_gvnic', 'virtio': 'gcp_virtio'}
        return mapping.get(prefix, 'unknown_{}'.format(prefix))

    @staticmethod
    def _analyze_throughput(df: pd.DataFrame, fields: List[str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in fields:
            series = pd.to_numeric(df[f], errors='coerce').dropna()
            if len(series) < 2:
                continue
            # Throughput fields are cumulative byte counters; diff gives rate.
            rate = series.diff().dropna()
            out[f] = {
                'total_bytes': int(series.iloc[-1] - series.iloc[0]),
                'mean_rate_bps': float(rate.mean()),
                'p50_rate_bps': float(rate.quantile(0.50)),
                'p99_rate_bps': float(rate.quantile(0.99)),
                'max_rate_bps': float(rate.max()),
            }
        return out

    @staticmethod
    def _analyze_packet_count(df: pd.DataFrame, fields: List[str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in fields:
            series = pd.to_numeric(df[f], errors='coerce').dropna()
            if len(series) < 2:
                continue
            rate = series.diff().dropna()
            out[f] = {
                'total_packets': int(series.iloc[-1] - series.iloc[0]),
                'mean_pps': float(rate.mean()),
                'p99_pps': float(rate.quantile(0.99)),
            }
        return out

    @staticmethod
    def _analyze_saturation_counters(df: pd.DataFrame, fields: List[str]) -> Dict[str, Any]:
        """AWS ENA saturation counters: count positive deltas as events."""
        out: Dict[str, Any] = {}
        for f in fields:
            series = pd.to_numeric(df[f], errors='coerce').dropna()
            if len(series) < 2:
                continue
            delta = series.diff().dropna()
            out[f] = {
                'total_increment': int(series.iloc[-1] - series.iloc[0]),
                'saturation_events': int((delta > 0).sum()),
                'max_per_sample_delta': int(delta.max()),
            }
        return out

    @staticmethod
    def _analyze_drop_counters(df: pd.DataFrame, fields: List[str]) -> Dict[str, Any]:
        """GCP gVNIC/virtio drop counters: count positive deltas as events."""
        out: Dict[str, Any] = {}
        for f in fields:
            series = pd.to_numeric(df[f], errors='coerce').dropna()
            if len(series) < 2:
                continue
            delta = series.diff().dropna()
            out[f] = {
                'total_drops': int(series.iloc[-1] - series.iloc[0]),
                'drop_events': int((delta > 0).sum()),
                'max_per_sample_delta': int(delta.max()),
            }
        return out

    @staticmethod
    def _analyze_error_counters(df: pd.DataFrame, fields: List[str]) -> Dict[str, Any]:
        """timeout/error counter"""
        out: Dict[str, Any] = {}
        for f in fields:
            series = pd.to_numeric(df[f], errors='coerce').dropna()
            if len(series) < 2:
                continue
            delta = series.diff().dropna()
            out[f] = {
                'total_errors': int(series.iloc[-1] - series.iloc[0]),
                'error_events': int((delta > 0).sum()),
            }
        return out

    @staticmethod
    def _analyze_saturation_signal(df: pd.DataFrame, fields: List[str]) -> Dict[str, Any]:
        """Core cross-provider metric: mean of network_saturation_signal (0/1)."""
        # fields should contain only network_saturation_signal.
        f = fields[0]
        series = pd.to_numeric(df[f], errors='coerce').dropna()
        return {
            'field': f,
            'saturated_samples': int((series == 1).sum()),
            'total_samples': len(series),
            'saturated_ratio': float((series == 1).mean()) if len(series) > 0 else 0.0,
        }
