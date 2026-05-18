"""NetworkAnalyzer - Y+ 架构 NIC 数据单 reader

零 platform 分支, 完全通过 NetworkFieldRegistry.get_semantic_type 分组分析.
下游禁止 hardcode 'ena_*' / 'gvnic_*' / 'virtio_*' 字面量字符串匹配.

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
        """主入口 - 按 semantic_type 分组分析."""
        validation = NetworkFieldRegistry.validate_csv_columns(list(df.columns))

        groups = NetworkFieldRegistry.group_by_semantic(df.columns)

        results: Dict[str, Any] = {
            'csv_validation': validation,
            'platform_detected': cls._detect_platform_from_columns(df.columns),
            'sample_count': len(df),
        }

        # throughput 字段分析
        if 'throughput' in groups:
            results['throughput'] = cls._analyze_throughput(df, groups['throughput'])

        # packet_count 字段分析
        if 'packet_count' in groups:
            results['packet_count'] = cls._analyze_packet_count(df, groups['packet_count'])

        # saturation_counter (AWS ENA 限速触发计数)
        if 'saturation_counter' in groups:
            results['saturation_counters'] = cls._analyze_saturation_counters(df, groups['saturation_counter'])

        # drop_counter (GCP gVNIC/virtio 丢包计数)
        if 'drop_counter' in groups:
            results['drop_counters'] = cls._analyze_drop_counters(df, groups['drop_counter'])

        # error_counter
        if 'error_counter' in groups:
            results['error_counters'] = cls._analyze_error_counters(df, groups['error_counter'])

        # saturation_signal - 跨平台对齐的核心指标
        if 'saturation_signal' in groups:
            results['saturation_ratio'] = cls._analyze_saturation_signal(df, groups['saturation_signal'])

        return results

    @classmethod
    def _detect_platform_from_columns(cls, columns: List[str]) -> str:
        """从字段前缀推断 platform variant (aws_ena / gcp_gvnic / gcp_virtio / other_none)."""
        prefixes = {NetworkFieldRegistry.get_platform_prefix(c) for c in columns} - {'common'}
        if not prefixes:
            return 'other_none'
        prefix = next(iter(prefixes))  # 应该只有 1 个
        mapping = {'ena': 'aws_ena', 'gvnic': 'gcp_gvnic', 'virtio': 'gcp_virtio'}
        return mapping.get(prefix, 'unknown_{}'.format(prefix))

    @staticmethod
    def _analyze_throughput(df: pd.DataFrame, fields: List[str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in fields:
            series = pd.to_numeric(df[f], errors='coerce').dropna()
            if len(series) < 2:
                continue
            # throughput 字段是累计 byte counter, 取差分得速率
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
        """AWS ENA saturation counter - 取增量, 非零次数即饱和发生次数."""
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
        """GCP gVNIC/virtio drop counter - 同样取增量."""
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
        """跨平台对齐核心: network_saturation_signal 列 (0/1), 直接 .mean() 得饱和占比."""
        # fields 应该只有 1 个: network_saturation_signal
        f = fields[0]
        series = pd.to_numeric(df[f], errors='coerce').dropna()
        return {
            'field': f,
            'saturated_samples': int((series == 1).sum()),
            'total_samples': len(series),
            'saturated_ratio': float((series == 1).mean()) if len(series) > 0 else 0.0,
        }
