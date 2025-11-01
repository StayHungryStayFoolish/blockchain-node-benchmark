#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPC Deep Analyzer - Independent module split from comprehensive_analysis.py
Specialized in deep analysis of RPC performance, including latency trends, anomaly detection, performance cliff detection, etc.
"""

import sys
import os

# Add project root directory to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

import pandas as pd
import numpy as np
from utils.unified_logger import get_logger
import traceback
from typing import Dict, Any, Optional

# Configure logging
logger = get_logger(__name__)


class RpcAnalysisConfig:
    """RPC Analysis Configuration Class - Centralized management of all thresholds and parameters"""
    
    # Anomaly detection configuration
    IQR_MULTIPLIER = 1.5  # IQR anomaly detection multiplier
    MIN_LATENCY_THRESHOLD = 30  # Minimum latency threshold (ms)
    SIGMA_MULTIPLIER = 2  # Standard deviation multiplier
    
    # Sync analysis configuration
    BLOCK_HEIGHT_SYNC_THRESHOLD = 20  # Block height sync offset threshold
    
    # Performance cliff detection configuration
    CLIFF_THRESHOLD_ABSOLUTE = 10  # Absolute latency increase threshold (ms)
    CLIFF_THRESHOLD_PERCENTAGE = 50  # Relative latency increase threshold (%)
    
    # Bottleneck classification configuration
    HIGH_CPU_THRESHOLD = int(os.getenv('BOTTLENECK_CPU_THRESHOLD', 85))     # High CPU usage threshold (%)
    HIGH_MEMORY_THRESHOLD = int(os.getenv('BOTTLENECK_MEMORY_THRESHOLD', 90))       # High memory usage threshold (%)
    LOW_CPU_THRESHOLD = 30  # Low CPU usage threshold (%)
    RPC_WARNING_LATENCY_THRESHOLD = 20  # RPC latency warning threshold (ms)
    HIGH_LATENCY_THRESHOLD = 50  # High latency threshold (ms)
    VERY_HIGH_LATENCY_THRESHOLD = 100  # Very high latency threshold (ms)
    SPECIAL_QPS_ANALYSIS_RATIO = 0.75  # Special QPS analysis point ratio (75% of max QPS)
    
    # Correlation analysis configuration
    STRONG_CORRELATION_THRESHOLD = 0.7  # Strong correlation threshold
    MODERATE_CORRELATION_THRESHOLD = 0.5  # Moderate correlation threshold
    WEAK_CORRELATION_THRESHOLD = 0.3  # Weak correlation threshold
    MIN_SAMPLES_FOR_SIGNIFICANCE = 30  # Minimum samples for statistical significance
    
    # High QPS analysis configuration
    HIGH_QPS_QUANTILE = 0.8  # High QPS quantile (top 20%)

# Error handling decorator
def handle_errors(func):
    """Error handling decorator to prevent program crash due to single function failure"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Function {func.__name__} execution failed: {str(e)}")
            logger.error(f"Error details: {traceback.format_exc()}")
            # Return safe default value instead of crashing
            if 'analyze' in func.__name__:
                return {}  # Analysis functions return empty dict
            elif 'generate' in func.__name__:
                return ""  # Generation functions return empty string
            else:
                return None
    return wrapper


class RpcDeepAnalyzer:
    """RPC Deep Analyzer - Deep analysis of RPC performance based on CSV monitoring data"""

    def __init__(self, csv_file: Optional[str] = None, config: Optional[RpcAnalysisConfig] = None):
        """
        Initialize RPC Deep Analyzer
        
        Args:
            csv_file: CSV file path (optional)
            config: Analysis configuration object (optional, defaults to RpcAnalysisConfig)
        """
        self.csv_file = csv_file
        self.config = config or RpcAnalysisConfig()
        logger.info(f"🔍 Initializing RPC Deep Analyzer, CSV file: {csv_file}")

    @handle_errors
    def analyze_rpc_deep_performance(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Execute RPC deep performance analysis
        
        Args:
            df: DataFrame containing monitoring data
            
        Returns:
            Dictionary containing analysis results
        """
        logger.info("🔍 Starting RPC deep performance analysis")
        print("\n🔍 RPC Deep Performance Analysis")
        print("=" * 50)

        if df is None or len(df) == 0:
            logger.warning("❌ No data available for RPC deep analysis")
            print("❌ No data available for RPC deep analysis")
            return {}

        # Prepare numeric data
        numeric_df = self._prepare_numeric_data(df)
        if len(numeric_df) == 0:
            print("❌ No valid numeric QPS data found")
            return {}

        # Execute various analyses
        analysis_results = {
            'latency_trend': self._analyze_latency_trends(numeric_df),
            'anomaly_detection': self._detect_latency_anomalies(numeric_df),
            'block_height_sync_analysis': self._analyze_block_height_synchronization(numeric_df),
            'correlation_analysis': self._analyze_qps_latency_correlation(numeric_df),
            'performance_cliff': self._detect_performance_cliff(numeric_df),
            'bottleneck_classification': self._classify_bottleneck_type(numeric_df)
        }

        return analysis_results

    def _prepare_numeric_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare numeric data, handle mixed type issues"""
        print(f"📋 Processing {len(df)} raw data points...")

        # Handle mixed type current_qps column
        df_copy = df.copy()
        df_copy['current_qps_str'] = df_copy['current_qps'].astype(str)
        numeric_mask = pd.to_numeric(df_copy['current_qps_str'], errors='coerce').notna()
        numeric_df = df_copy[numeric_mask].copy()

        if len(numeric_df) > 0:
            numeric_df['current_qps'] = pd.to_numeric(numeric_df['current_qps_str'])

            # Ensure other numeric columns are also numeric type
            numeric_cols = ['rpc_latency_ms', 'cpu_usage', 'mem_usage']
            for col in numeric_cols:
                if col in numeric_df.columns:
                    numeric_df[col] = pd.to_numeric(numeric_df[col], errors='coerce')

        print(f"📊 Valid numeric data points: {len(numeric_df)}")
        return numeric_df

    def _analyze_latency_trends(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze latency trends"""
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
        """Detect latency anomalies - Use IQR method instead of 2σ rule"""
        # IQR anomaly detection method (more robust, suitable for non-normal distribution)
        Q1 = df['rpc_latency_ms'].quantile(0.25)
        Q3 = df['rpc_latency_ms'].quantile(0.75)
        IQR = Q3 - Q1
        
        # IQR anomaly detection threshold
        lower_bound = Q1 - self.config.IQR_MULTIPLIER * IQR
        upper_bound = Q3 + self.config.IQR_MULTIPLIER * IQR
        
        # Ensure lower bound is not negative, upper bound is at least the configured minimum threshold
        lower_bound = max(0, lower_bound)
        upper_bound = max(self.config.MIN_LATENCY_THRESHOLD, upper_bound)
        
        # Detect anomalies (only focus on high latency anomalies)
        high_latency = df[df['rpc_latency_ms'] > upper_bound]
        
        # Also keep 2σ method for comparison
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
            
            # Comparison with 2σ method
            'sigma2_threshold': sigma2_threshold,
            'sigma2_anomaly_count': len(sigma2_anomalies),
            'sigma2_anomaly_percentage': (len(sigma2_anomalies) / len(df)) * 100 if len(df) > 0 else 0,
            
            # Statistical information
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
            # Record anomaly samples (using IQR detection results)
            anomaly_analysis['anomaly_samples'] = high_latency[
                ['current_qps', 'rpc_latency_ms', 'cpu_usage', 'mem_usage', 'timestamp']
            ].to_dict('records')

            # Analyze system state during anomalies
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

    def _analyze_block_height_synchronization(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze block height synchronization status"""
        block_height_analysis = {
            'sync_data_available': False,
            'sync_issues_count': 0,
            'avg_block_height_offset': 0,
            'max_block_height_offset': 0,
            'sync_issues_samples': []
        }

        # Process block_height_diff data
        if 'block_height_diff' in df.columns:
            # Convert to numeric and filter invalid data (now all data is numeric, no more 'N/A' strings)
            block_height_data = df.copy()
            block_height_data['block_height_diff_numeric'] = pd.to_numeric(df['block_height_diff'], errors='coerce')
            block_height_data = block_height_data.dropna(subset=['block_height_diff_numeric'])

            if len(block_height_data) > 0:
                    block_height_analysis['sync_data_available'] = True
                    block_height_analysis['avg_block_height_offset'] = block_height_data['block_height_diff_numeric'].mean()
                    block_height_analysis['max_block_height_offset'] = block_height_data['block_height_diff_numeric'].max()

                    # Check sync issues (offset > configured threshold)
                    sync_issues = block_height_data[block_height_data['block_height_diff_numeric'] > self.config.BLOCK_HEIGHT_SYNC_THRESHOLD]
                    block_height_analysis['sync_issues_count'] = len(sync_issues)

                    if len(sync_issues) > 0:
                        block_height_analysis['sync_issues_samples'] = sync_issues[
                            ['current_qps', 'block_height_diff_numeric', 'rpc_latency_ms']
                        ].to_dict('records')
                        print(f"\n⚠️  Found {len(sync_issues)} sync delay samples (Block height offset >{self.config.BLOCK_HEIGHT_SYNC_THRESHOLD}):")

        return block_height_analysis

    def _analyze_qps_latency_correlation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze correlation between QPS and latency"""
        correlation = df['current_qps'].corr(df['rpc_latency_ms'])

        correlation_analysis = {
            'correlation_coefficient': correlation,
            'correlation_strength': 'weak',
            'correlation_direction': 'none',
            'interpretation': '',
            'statistical_significance': False
        }

        # Determine correlation strength
        abs_correlation = abs(correlation)
        if abs_correlation > self.config.STRONG_CORRELATION_THRESHOLD:
            correlation_analysis['correlation_strength'] = 'strong'
        elif abs_correlation > self.config.MODERATE_CORRELATION_THRESHOLD:
            correlation_analysis['correlation_strength'] = 'moderate'
        elif abs_correlation > self.config.WEAK_CORRELATION_THRESHOLD:
            correlation_analysis['correlation_strength'] = 'weak'
        else:
            correlation_analysis['correlation_strength'] = 'very_weak'

        # Determine direction and interpretation
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

        # Statistical significance
        if len(df) > self.config.MIN_SAMPLES_FOR_SIGNIFICANCE and abs_correlation > self.config.WEAK_CORRELATION_THRESHOLD:
            correlation_analysis['statistical_significance'] = True

        print(f"\n📈 QPS-Latency correlation analysis:")
        print(f"QPS vs RPC latency correlation coefficient: {correlation:.3f}")
        print(correlation_analysis['interpretation'])

        return correlation_analysis

    def _detect_performance_cliff(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Detect performance cliff"""
        qps_latency_summary = df.groupby('current_qps')['rpc_latency_ms'].agg([
            'mean', 'max', 'count'
        ]).reset_index()
        qps_latency_summary = qps_latency_summary.sort_values('current_qps')

        # Calculate latency increase
        qps_latency_summary['latency_increase'] = qps_latency_summary['mean'].diff()
        qps_latency_summary['latency_increase_percentage'] = (
                qps_latency_summary['latency_increase'] / qps_latency_summary['mean'].shift(1) * 100
        )

        # Detect cliff points (latency increase > configured threshold)
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
                qps_display = f"{row['current_qps']:,.0f}" if not pd.isna(row['current_qps']) else "N/A"
                print(f"QPS {qps_display}: latency spike +{row['latency_increase']:.1f}ms")
        else:
            print(f"\n📊 Performance cliff detection:")
            print("✅ No significant performance cliff detected")

        return cliff_analysis

    def _classify_bottleneck_type(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Bottleneck type classification"""
        bottleneck_classification = {
            'primary_bottleneck': 'unknown',
            'bottleneck_confidence': 0.0,  # Use float type for consistency
            'evidence': [],
            'recommendations': []
        }

        # Analyze system state during high QPS phase
        high_qps_threshold = df['current_qps'].quantile(self.config.HIGH_QPS_QUANTILE)  # Configured high QPS quantile
        high_qps_data = df[df['current_qps'] >= high_qps_threshold]

        if len(high_qps_data) > 0:
            avg_cpu = high_qps_data['cpu_usage'].mean() if 'cpu_usage' in high_qps_data.columns else 0.0
            avg_latency = high_qps_data['rpc_latency_ms'].mean() if 'rpc_latency_ms' in high_qps_data.columns else 0.0
            avg_memory = high_qps_data['mem_usage'].mean() if 'mem_usage' in high_qps_data.columns else 0.0

            print(f"\n🎯 Bottleneck type classification:")

            # Dynamically calculate special analysis QPS point (75% of max QPS)
            qps_special = pd.DataFrame()
            closest_qps = 0
            max_qps = 0
            
            if 'current_qps' in df.columns and len(df[df['current_qps'] > 0]) > 0:
                max_qps = df['current_qps'].max()
                target_qps = int(max_qps * self.config.SPECIAL_QPS_ANALYSIS_RATIO)
                # Find the actual test point closest to target QPS
                closest_qps = df.loc[(df['current_qps'] - target_qps).abs().idxmin(), 'current_qps']
                qps_special = df[df['current_qps'] == closest_qps]
            
            if len(qps_special) > 0:
                avg_cpu_special = qps_special['cpu_usage'].mean() if 'cpu_usage' in qps_special.columns else 0.0
                avg_latency_special = qps_special['rpc_latency_ms'].mean() if 'rpc_latency_ms' in qps_special.columns else 0.0
                print(f"{int(closest_qps)} QPS phase analysis (75% of max {int(max_qps)} QPS):")
                print(f"  🖥️ Average CPU: {avg_cpu_special:.1f}%")
                print(f"  ⏱️ Average latency: {avg_latency_special:.1f}ms")

                if avg_latency_special > self.config.RPC_WARNING_LATENCY_THRESHOLD and avg_cpu_special < self.config.LOW_CPU_THRESHOLD:
                    bottleneck_classification['primary_bottleneck'] = 'rpc_processing'
                    bottleneck_classification['bottleneck_confidence'] = 0.8
                    bottleneck_classification['evidence'].append(
                        f"High latency ({avg_latency_special:.1f}ms) at {int(closest_qps)} QPS with low CPU ({avg_cpu_special:.1f}%)")
                    print("🔍 Bottleneck type: RPC processing capacity limitation (non-CPU bottleneck)")
                    print("💡 Optimization suggestions:")
                    print("  🔧 - Increase RPC thread count")
                    print("  🌐 - Optimize network configuration")
                    print("  ⚙️ - Check RPC connection pool settings")

            # General bottleneck classification logic
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
        """Generate RPC deep analysis report"""
        report = "\n## 🔍 RPC Deep Performance Analysis Report\n"
        report += "=" * 60 + "\n"

        # Latency trend
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
                    report += f"- **{qps:,} QPS**: Avg {stats['mean']:.1f}ms, Max {stats['max']:.1f}ms, Samples {stats['count']}\n" if not pd.isna(qps) else f"- **N/A QPS**: Avg {stats['mean']:.1f}ms, Max {stats['max']:.1f}ms, Samples {stats['count']}\n"

        # Anomaly detection
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
                avg_qps_display = f"{system_state.get('avg_qps', 0):,.0f}" if not pd.isna(system_state.get('avg_qps', 0)) else "N/A"
                report += f"""
#### System State During Anomalies:
- **Average CPU**: {system_state.get('avg_cpu', 0):.1f}%
- **Average Memory**: {system_state.get('avg_memory', 0):.1f}%
- **Average QPS**: {avg_qps_display}
"""

        # Correlation analysis
        correlation = analysis_results.get('correlation_analysis', {})
        if correlation:
            report += f"""
### 📈 QPS-Latency Correlation Analysis
- **Correlation Coefficient**: {correlation.get('correlation_coefficient', 0):.3f}
- **Correlation Strength**: {correlation.get('correlation_strength', 'unknown').title()}
- **Interpretation**: {correlation.get('interpretation', 'No analysis available')}
- **Statistical Significance**: {'Yes' if correlation.get('statistical_significance') else 'No'}
"""

        # Performance cliff
        cliff = analysis_results.get('performance_cliff', {})
        if cliff and cliff.get('cliff_points_detected', 0) > 0:
            report += f"""
### 📉 Performance Cliff Detection
- **Cliff Points Detected**: {cliff.get('cliff_points_detected', 0)}

#### Critical QPS Thresholds:
"""
            for cliff_point in cliff.get('cliff_details', []):
                report += f"- **{cliff_point['current_qps']:,} QPS**: Latency spike +{cliff_point['latency_increase']:.1f}ms ({cliff_point.get('latency_increase_percentage', 0):.1f}%)\n" if not pd.isna(cliff_point['current_qps']) else f"- **N/A QPS**: Latency spike +{cliff_point['latency_increase']:.1f}ms ({cliff_point.get('latency_increase_percentage', 0):.1f}%)\n"

        # Bottleneck classification
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


# Usage example
if __name__ == "__main__":
    print("📋 RPC Deep Analyzer usage example:")
    print("from rpc_deep_analyzer import RpcDeepAnalyzer")
    print("analyzer = RpcDeepAnalyzer('data.csv')")
    print("results = analyzer.analyze_rpc_deep_performance(df)")
    print("report = analyzer.generate_rpc_deep_analysis_report(results)")
