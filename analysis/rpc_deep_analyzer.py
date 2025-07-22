#!/usr/bin/env python3
"""
RPC深度分析器 - 从comprehensive_analysis.py拆分出来的独立模块
专门负责RPC性能的深度分析，包括延迟趋势、异常检测、性能悬崖检测等
"""

import sys
import os

# 添加项目根目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

import pandas as pd
import numpy as np
from utils.unified_logger import get_logger
import traceback
from typing import Dict, Any, Optional

# 配置日志
logger = get_logger(__name__)


class RpcAnalysisConfig:
    """RPC分析配置类 - 集中管理所有阈值和参数"""
    
    # 异常检测配置
    IQR_MULTIPLIER = 1.5  # IQR异常检测倍数
    MIN_LATENCY_THRESHOLD = 30  # 最小延迟阈值(ms)
    SIGMA_MULTIPLIER = 2  # 标准差倍数
    
    # 同步分析配置
    SLOT_SYNC_THRESHOLD = 20  # Slot同步偏移阈值
    
    # 性能悬崖检测配置
    CLIFF_THRESHOLD_ABSOLUTE = 10  # 绝对延迟增长阈值(ms)
    CLIFF_THRESHOLD_PERCENTAGE = 50  # 相对延迟增长阈值(%)
    
    # 瓶颈分类配置
    HIGH_CPU_THRESHOLD = 85  # 高CPU使用率阈值(%)
    HIGH_MEMORY_THRESHOLD = 90  # 高内存使用率阈值(%)
    LOW_CPU_THRESHOLD = 30  # 低CPU使用率阈值(%)
    HIGH_LATENCY_THRESHOLD = 50  # 高延迟阈值(ms)
    VERY_HIGH_LATENCY_THRESHOLD = 100  # 极高延迟阈值(ms)
    SPECIAL_QPS_ANALYSIS = 75000  # 特殊QPS分析点
    
    # 相关性分析配置
    STRONG_CORRELATION_THRESHOLD = 0.7  # 强相关性阈值
    MODERATE_CORRELATION_THRESHOLD = 0.5  # 中等相关性阈值
    WEAK_CORRELATION_THRESHOLD = 0.3  # 弱相关性阈值
    MIN_SAMPLES_FOR_SIGNIFICANCE = 30  # 统计显著性最小样本数
    
    # 高QPS分析配置
    HIGH_QPS_QUANTILE = 0.8  # 高QPS分位数(前20%)

# 错误处理装饰器
def handle_errors(func):
    """错误处理装饰器，保证程序不会因为单个功能失败而完全崩溃"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"函数 {func.__name__} 执行失败: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            # 返回安全的默认值而不是崩溃
            if 'analyze' in func.__name__:
                return {}  # 分析函数返回空字典
            elif 'generate' in func.__name__:
                return ""  # 生成函数返回空字符串
            else:
                return None
    return wrapper


class RpcDeepAnalyzer:
    """RPC深度分析器 - 基于CSV监控数据进行RPC性能深度分析"""

    def __init__(self, csv_file: Optional[str] = None, config: Optional[RpcAnalysisConfig] = None):
        """
        初始化RPC深度分析器
        
        Args:
            csv_file: CSV文件路径（可选）
            config: 分析配置对象（可选，默认使用RpcAnalysisConfig）
        """
        self.csv_file = csv_file
        self.config = config or RpcAnalysisConfig()
        logger.info(f"🔍 初始化RPC深度分析器，CSV文件: {csv_file}")

    @handle_errors
    def analyze_rpc_deep_performance(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        执行RPC深度性能分析
        
        Args:
            df: 包含监控数据的DataFrame
            
        Returns:
            包含分析结果的字典
        """
        logger.info("🔍 开始RPC深度性能分析")
        print("\n🔍 RPC Deep Performance Analysis")
        print("=" * 50)

        if df is None or len(df) == 0:
            logger.warning("❌ RPC深度分析无可用数据")
            print("❌ No data available for RPC deep analysis")
            return {}

        # 准备数值数据
        numeric_df = self._prepare_numeric_data(df)
        if len(numeric_df) == 0:
            print("❌ No valid numeric QPS data found")
            return {}

        # 执行各项分析
        analysis_results = {
            'latency_trend': self._analyze_latency_trends(numeric_df),
            'anomaly_detection': self._detect_latency_anomalies(numeric_df),
            'slot_sync_analysis': self._analyze_slot_synchronization(numeric_df),
            'correlation_analysis': self._analyze_qps_latency_correlation(numeric_df),
            'performance_cliff': self._detect_performance_cliff(numeric_df),
            'bottleneck_classification': self._classify_bottleneck_type(numeric_df)
        }

        return analysis_results

    def _prepare_numeric_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """准备数值数据，处理混合类型问题"""
        print(f"📋 Processing {len(df)} raw data points...")

        # 处理混合类型的current_qps列
        df_copy = df.copy()
        df_copy['current_qps_str'] = df_copy['current_qps'].astype(str)
        numeric_mask = df_copy['current_qps_str'].str.isdigit()
        numeric_df = df_copy[numeric_mask].copy()

        if len(numeric_df) > 0:
            numeric_df['current_qps'] = pd.to_numeric(numeric_df['current_qps_str'])

            # 确保其他数值列也是数值类型
            numeric_cols = ['rpc_latency_ms', 'cpu_usage', 'mem_usage']
            for col in numeric_cols:
                if col in numeric_df.columns:
                    numeric_df[col] = pd.to_numeric(numeric_df[col], errors='coerce')

        print(f"📊 Valid numeric data points: {len(numeric_df)}")
        return numeric_df

    def _analyze_latency_trends(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析延迟趋势"""
        latency_stats = df.groupby('current_qps')['rpc_latency_ms'].agg([
            'mean', 'max', 'std', 'count', 'median'
        ]).round(2)

        return {
            'latency_by_qps': latency_stats,
            'overall_avg_latency': df['rpc_latency_ms'].mean(),
            'overall_max_latency': df['rpc_latency_ms'].max(),
            'latency_std': df['rpc_latency_ms'].std()
        }

    def _detect_latency_anomalies(self, df: pd.DataFrame) -> Dict[str, Any]:
        """检测延迟异常 - 使用IQR方法替代2σ规则"""
        # IQR异常检测方法 (更鲁棒，适合非正态分布)
        Q1 = df['rpc_latency_ms'].quantile(0.25)
        Q3 = df['rpc_latency_ms'].quantile(0.75)
        IQR = Q3 - Q1
        
        # IQR异常检测阈值
        lower_bound = Q1 - self.config.IQR_MULTIPLIER * IQR
        upper_bound = Q3 + self.config.IQR_MULTIPLIER * IQR
        
        # 确保下界不为负，上界至少为配置的最小阈值
        lower_bound = max(0, lower_bound)
        upper_bound = max(self.config.MIN_LATENCY_THRESHOLD, upper_bound)
        
        # 检测异常 (只关注高延迟异常)
        high_latency = df[df['rpc_latency_ms'] > upper_bound]
        
        # 同时保留2σ方法作为对比
        avg_latency = df['rpc_latency_ms'].mean()
        std_latency = df['rpc_latency_ms'].std()
        sigma2_threshold = max(self.config.MIN_LATENCY_THRESHOLD, 
                              avg_latency + self.config.SIGMA_MULTIPLIER * std_latency)
        sigma2_anomalies = df[df['rpc_latency_ms'] > sigma2_threshold]

        anomaly_analysis = {
            'method': 'IQR',
            'iqr_threshold': upper_bound,
            'iqr_anomaly_count': len(high_latency),
            'iqr_anomaly_percentage': (len(high_latency) / len(df)) * 100 if len(df) > 0 else 0,
            
            # 对比2σ方法
            'sigma2_threshold': sigma2_threshold,
            'sigma2_anomaly_count': len(sigma2_anomalies),
            'sigma2_anomaly_percentage': (len(sigma2_anomalies) / len(df)) * 100 if len(df) > 0 else 0,
            
            # 统计信息
            'Q1': Q1,
            'Q3': Q3,
            'IQR': IQR,
            'median': df['rpc_latency_ms'].median(),
            'mean': avg_latency,
            'std': std_latency,
            
            'anomaly_samples': [],
            'system_state_during_anomalies': {}
        }

        if len(high_latency) > 0:
            # 记录异常样本 (使用IQR检测结果)
            anomaly_analysis['anomaly_samples'] = high_latency[
                ['current_qps', 'rpc_latency_ms', 'cpu_usage', 'mem_usage', 'timestamp']
            ].to_dict('records')

            # 分析异常期间的系统状态
            anomaly_analysis['system_state_during_anomalies'] = {
                'avg_cpu': float(high_latency['cpu_usage'].mean()) if 'cpu_usage' in high_latency.columns else 0.0,
                'avg_memory': float(high_latency['mem_usage'].mean()) if 'mem_usage' in high_latency.columns else 0.0,
                'avg_qps': float(high_latency['current_qps'].mean()) if 'current_qps' in high_latency.columns else 0.0,
                'most_affected_qps_ranges': high_latency['current_qps'].value_counts().head(3).to_dict()
            }

            print(f"⚠️  Anomaly latency detection (>{upper_bound:.1f}ms):")
            print(f"Found {len(high_latency)} high latency samples")
            print(f"Average system state during high latency periods:")
            print(f"CPU usage: {anomaly_analysis.get('system_state_during_anomalies', {}).get('avg_cpu', 0):.1f}%")
            print(f"Memory usage: {anomaly_analysis.get('system_state_during_anomalies', {}).get('avg_memory', 0):.1f}%")

        return anomaly_analysis

    def _analyze_slot_synchronization(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析Slot同步状态"""
        slot_analysis = {
            'sync_data_available': False,
            'sync_issues_count': 0,
            'avg_slot_offset': 0,
            'max_slot_offset': 0,
            'sync_issues_samples': []
        }

        # 处理slot_diff数据
        if 'slot_diff' in df.columns:
            slot_data = df[df['slot_diff'] != 'N/A'].copy()

            if len(slot_data) > 0:
                slot_data['slot_diff_numeric'] = pd.to_numeric(slot_data['slot_diff'], errors='coerce')
                slot_data = slot_data.dropna(subset=['slot_diff_numeric'])

                if len(slot_data) > 0:
                    slot_analysis['sync_data_available'] = True
                    slot_analysis['avg_slot_offset'] = slot_data['slot_diff_numeric'].mean()
                    slot_analysis['max_slot_offset'] = slot_data['slot_diff_numeric'].max()

                    # 检查同步问题（偏移 > 配置阈值）
                    sync_issues = slot_data[slot_data['slot_diff_numeric'] > self.config.SLOT_SYNC_THRESHOLD]
                    slot_analysis['sync_issues_count'] = len(sync_issues)

                    if len(sync_issues) > 0:
                        slot_analysis['sync_issues_samples'] = sync_issues[
                            ['current_qps', 'slot_diff_numeric', 'rpc_latency_ms']
                        ].to_dict('records')
                        print(f"\n⚠️  Found {len(sync_issues)} sync delay samples (Slot offset >{self.config.SLOT_SYNC_THRESHOLD}):")

        return slot_analysis

    def _analyze_qps_latency_correlation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析QPS与延迟的相关性"""
        correlation = df['current_qps'].corr(df['rpc_latency_ms'])

        correlation_analysis = {
            'correlation_coefficient': correlation,
            'correlation_strength': 'weak',
            'correlation_direction': 'none',
            'interpretation': '',
            'statistical_significance': False
        }

        # 确定相关性强度
        abs_correlation = abs(correlation)
        if abs_correlation > self.config.STRONG_CORRELATION_THRESHOLD:
            correlation_analysis['correlation_strength'] = 'strong'
        elif abs_correlation > self.config.MODERATE_CORRELATION_THRESHOLD:
            correlation_analysis['correlation_strength'] = 'moderate'
        elif abs_correlation > self.config.WEAK_CORRELATION_THRESHOLD:
            correlation_analysis['correlation_strength'] = 'weak'
        else:
            correlation_analysis['correlation_strength'] = 'very_weak'

        # 确定方向和解释
        if correlation > self.config.MODERATE_CORRELATION_THRESHOLD:
            correlation_analysis['correlation_direction'] = 'positive'
            correlation_analysis['interpretation'] = '🔍 Strong positive correlation found: latency increases significantly with QPS'
        elif correlation < -self.config.MODERATE_CORRELATION_THRESHOLD:
            correlation_analysis['correlation_direction'] = 'negative'
            correlation_analysis['interpretation'] = '🔍 Strong negative correlation found: latency decreases significantly with QPS (unusual phenomenon)'
        elif abs(correlation) > self.config.WEAK_CORRELATION_THRESHOLD:
            correlation_analysis['interpretation'] = '🔍 Moderate correlation: some relationship exists between latency and QPS'
        else:
            correlation_analysis['interpretation'] = '🔍 Weak correlation: latency may be influenced by other factors'

        # 统计显著性
        if len(df) > self.config.MIN_SAMPLES_FOR_SIGNIFICANCE and abs_correlation > self.config.WEAK_CORRELATION_THRESHOLD:
            correlation_analysis['statistical_significance'] = True

        print(f"\n📈 QPS-Latency correlation analysis:")
        print(f"QPS vs RPC latency correlation coefficient: {correlation:.3f}")
        print(correlation_analysis['interpretation'])

        return correlation_analysis

    def _detect_performance_cliff(self, df: pd.DataFrame) -> Dict[str, Any]:
        """检测性能悬崖"""
        qps_latency_summary = df.groupby('current_qps')['rpc_latency_ms'].agg([
            'mean', 'max', 'count'
        ]).reset_index()
        qps_latency_summary = qps_latency_summary.sort_values('current_qps')

        # 计算延迟增长
        qps_latency_summary['latency_increase'] = qps_latency_summary['mean'].diff()
        qps_latency_summary['latency_increase_percentage'] = (
                qps_latency_summary['latency_increase'] / qps_latency_summary['mean'].shift(1) * 100
        )

        # 检测悬崖点（延迟增长 > 配置阈值）
        cliff_points = qps_latency_summary[
            (qps_latency_summary['latency_increase'] > self.config.CLIFF_THRESHOLD_ABSOLUTE) |
            (qps_latency_summary['latency_increase_percentage'] > self.config.CLIFF_THRESHOLD_PERCENTAGE)
        ]

        cliff_analysis = {
            'cliff_points_detected': len(cliff_points),
            'cliff_details': [],
            'performance_degradation_qps': []
        }

        if len(cliff_points) > 0:
            cliff_analysis['cliff_details'] = cliff_points[
                ['current_qps', 'mean', 'latency_increase', 'latency_increase_percentage']
            ].to_dict('records')

            cliff_analysis['performance_degradation_qps'] = cliff_points['current_qps'].tolist()

            print(f"\n📊 Performance cliff detection:")
            print("⚠️  Performance cliff points detected:")
            for _, row in cliff_points.iterrows():
                print(f"QPS {row['current_qps']:,.0f}: latency spike +{row['latency_increase']:.1f}ms")
        else:
            print(f"\n📊 Performance cliff detection:")
            print("✅ No significant performance cliff detected")

        return cliff_analysis

    def _classify_bottleneck_type(self, df: pd.DataFrame) -> Dict[str, Any]:
        """瓶颈类型分类"""
        bottleneck_classification = {
            'primary_bottleneck': 'unknown',
            'bottleneck_confidence': 0.0,  # 使用 float 类型保持一致性
            'evidence': [],
            'recommendations': []
        }

        # 分析高QPS阶段的系统状态
        high_qps_threshold = df['current_qps'].quantile(self.config.HIGH_QPS_QUANTILE)  # 配置的高QPS分位数
        high_qps_data = df[df['current_qps'] >= high_qps_threshold]

        if len(high_qps_data) > 0:
            avg_cpu = high_qps_data['cpu_usage'].mean() if 'cpu_usage' in high_qps_data.columns else 0.0
            avg_latency = high_qps_data['rpc_latency_ms'].mean() if 'rpc_latency_ms' in high_qps_data.columns else 0.0
            avg_memory = high_qps_data['mem_usage'].mean() if 'mem_usage' in high_qps_data.columns else 0.0

            print(f"\n🎯 Bottleneck type classification:")

            # 特殊分析配置的QPS阶段（如果存在）
            qps_special = df[df['current_qps'] == self.config.SPECIAL_QPS_ANALYSIS] if 'current_qps' in df.columns else pd.DataFrame()
            if len(qps_special) > 0:
                avg_cpu_special = qps_special['cpu_usage'].mean() if 'cpu_usage' in qps_special.columns else 0.0
                avg_latency_special = qps_special['rpc_latency_ms'].mean() if 'rpc_latency_ms' in qps_special.columns else 0.0
                print(f"{self.config.SPECIAL_QPS_ANALYSIS} QPS phase analysis:")
                print(f"  Average CPU: {avg_cpu_special:.1f}%")
                print(f"  Average latency: {avg_latency_special:.1f}ms")

                if avg_latency_special > 20 and avg_cpu_special < self.config.LOW_CPU_THRESHOLD:
                    bottleneck_classification['primary_bottleneck'] = 'rpc_processing'
                    bottleneck_classification['bottleneck_confidence'] = 0.8
                    bottleneck_classification['evidence'].append(
                        f"High latency ({avg_latency_special:.1f}ms) at {self.config.SPECIAL_QPS_ANALYSIS} QPS with low CPU ({avg_cpu_special:.1f}%)")
                    print("🔍 Bottleneck type: RPC processing capacity limitation (non-CPU bottleneck)")
                    print("💡 Optimization suggestions:")
                    print("  - Increase RPC thread count")
                    print("  - Optimize network configuration")
                    print("  - Check RPC connection pool settings")

            # 通用瓶颈分类逻辑
            if avg_cpu > self.config.HIGH_CPU_THRESHOLD:
                bottleneck_classification['primary_bottleneck'] = 'cpu'
                bottleneck_classification['bottleneck_confidence'] = 0.8
                bottleneck_classification['evidence'].append(f"High CPU usage: {avg_cpu:.1f}%")
                bottleneck_classification['recommendations'].extend([
                    "Upgrade CPU or optimize CPU-intensive operations",
                    "Consider horizontal scaling"
                ])

            elif avg_memory > self.config.HIGH_MEMORY_THRESHOLD:
                bottleneck_classification['primary_bottleneck'] = 'memory'
                bottleneck_classification['bottleneck_confidence'] = 0.8
                bottleneck_classification['evidence'].append(f"High memory usage: {avg_memory:.1f}%")
                bottleneck_classification['recommendations'].extend([
                    "Increase system memory",
                    "Optimize memory usage patterns"
                ])

            elif avg_latency > self.config.HIGH_LATENCY_THRESHOLD and avg_cpu < self.config.LOW_CPU_THRESHOLD:
                if bottleneck_classification['primary_bottleneck'] == 'unknown':
                    bottleneck_classification['primary_bottleneck'] = 'rpc_processing'
                    bottleneck_classification['bottleneck_confidence'] = 0.7
                bottleneck_classification['evidence'].extend([
                    f"High RPC latency: {avg_latency:.1f}ms",
                    f"Low CPU usage: {avg_cpu:.1f}%"
                ])
                bottleneck_classification['recommendations'].extend([
                    "Increase RPC thread pool size",
                    "Optimize network configuration",
                    "Check RPC connection pool settings"
                ])

            elif avg_latency > self.config.VERY_HIGH_LATENCY_THRESHOLD:
                bottleneck_classification['primary_bottleneck'] = 'network_io'
                bottleneck_classification['bottleneck_confidence'] = 0.6
                bottleneck_classification['evidence'].append(f"Very high latency: {avg_latency:.1f}ms")
                bottleneck_classification['recommendations'].extend([
                    "Check network configuration",
                    "Optimize storage I/O",
                    "Review validator configuration"
                ])
            else:
                bottleneck_classification['primary_bottleneck'] = 'balanced'
                bottleneck_classification['bottleneck_confidence'] = 0.5
                bottleneck_classification['evidence'].append("No clear bottleneck detected")
                bottleneck_classification['recommendations'].append("System appears well-balanced")

        return bottleneck_classification

    def generate_rpc_deep_analysis_report(self, analysis_results: Dict[str, Any]) -> str:
        """生成RPC深度分析报告"""
        report = "\n## 🔍 RPC Deep Performance Analysis Report\n"
        report += "=" * 60 + "\n"

        # 延迟趋势
        latency_trend = analysis_results.get('latency_trend', {})
        if latency_trend:
            report += f"""
### 📊 Latency Trend Analysis
- **Overall Average Latency**: {latency_trend.get('overall_avg_latency', 0):.1f}ms
- **Maximum Latency**: {latency_trend.get('overall_max_latency', 0):.1f}ms
- **Latency Standard Deviation**: {latency_trend.get('latency_std', 0):.1f}ms

#### Latency by QPS Levels:
"""
            latency_by_qps = latency_trend.get('latency_by_qps')
            if latency_by_qps is not None and len(latency_by_qps) > 0:
                for qps, stats in latency_by_qps.head(10).iterrows():
                    report += f"- **{qps:,} QPS**: Avg {stats['mean']:.1f}ms, Max {stats['max']:.1f}ms, Samples {stats['count']}\n"

        # 异常检测
        anomaly = analysis_results.get('anomaly_detection', {})
        if anomaly:
            report += f"""
### ⚠️ Latency Anomaly Detection
- **Detection Method**: {anomaly.get('method', 'Unknown')}
- **IQR Threshold**: {anomaly.get('iqr_threshold', 0):.1f}ms
- **2σ Threshold**: {anomaly.get('sigma2_threshold', 0):.1f}ms
- **IQR Anomalies Detected**: {anomaly.get('iqr_anomaly_count', 0)} ({anomaly.get('iqr_anomaly_percentage', 0):.1f}% of samples)
- **2σ Anomalies Detected**: {anomaly.get('sigma2_anomaly_count', 0)} ({anomaly.get('sigma2_anomaly_percentage', 0):.1f}% of samples)
"""
            if anomaly.get('iqr_anomaly_count', 0) > 0:
                system_state = anomaly.get('system_state_during_anomalies', {})
                report += f"""
#### System State During Anomalies:
- **Average CPU**: {system_state.get('avg_cpu', 0):.1f}%
- **Average Memory**: {system_state.get('avg_memory', 0):.1f}%
- **Average QPS**: {system_state.get('avg_qps', 0):,.0f}
"""

        # 相关性分析
        correlation = analysis_results.get('correlation_analysis', {})
        if correlation:
            report += f"""
### 📈 QPS-Latency Correlation Analysis
- **Correlation Coefficient**: {correlation.get('correlation_coefficient', 0):.3f}
- **Correlation Strength**: {correlation.get('correlation_strength', 'unknown').title()}
- **Interpretation**: {correlation.get('interpretation', 'No analysis available')}
- **Statistical Significance**: {'Yes' if correlation.get('statistical_significance') else 'No'}
"""

        # 性能悬崖
        cliff = analysis_results.get('performance_cliff', {})
        if cliff and cliff.get('cliff_points_detected', 0) > 0:
            report += f"""
### 📉 Performance Cliff Detection
- **Cliff Points Detected**: {cliff.get('cliff_points_detected', 0)}

#### Critical QPS Thresholds:
"""
            for cliff_point in cliff.get('cliff_details', []):
                report += f"- **{cliff_point['current_qps']:,} QPS**: Latency spike +{cliff_point['latency_increase']:.1f}ms ({cliff_point.get('latency_increase_percentage', 0):.1f}%)\n"

        # 瓶颈分类
        bottleneck = analysis_results.get('bottleneck_classification', {})
        if bottleneck:
            report += f"""
### 🎯 Bottleneck Classification
- **Primary Bottleneck**: {bottleneck.get('primary_bottleneck', 'unknown').replace('_', ' ').title()}
- **Confidence Level**: {bottleneck.get('bottleneck_confidence', 0) * 100:.0f}%

#### Evidence:
"""
            for evidence in bottleneck.get('evidence', []):
                report += f"- {evidence}\n"

            report += "\n#### Recommendations:\n"
            for rec in bottleneck.get('recommendations', []):
                report += f"- {rec}\n"

        return report


# 使用示例
if __name__ == "__main__":
    print("📋 RPC深度分析器使用示例:")
    print("from rpc_deep_analyzer import RpcDeepAnalyzer")
    print("analyzer = RpcDeepAnalyzer('data.csv')")
    print("results = analyzer.analyze_rpc_deep_performance(df)")
    print("report = analyzer.generate_rpc_deep_analysis_report(results)")
