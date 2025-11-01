#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QPS Analyzer - Independent module split from comprehensive_analysis.py + bottleneck mode support
Dedicated to QPS performance analysis, including performance metrics analysis, bottleneck identification, chart generation, etc.
Supports performance cliff analysis and bottleneck detection mode
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
import glob
import os
import sys
import json
import argparse
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

# Add project root directory to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from visualization.chart_style_config import UnifiedChartStyle
from utils.unified_logger import get_logger

# Use unified logger manager
logger = get_logger(__name__)
logger.info("✅ Unified logger manager initialized successfully")

class NodeQPSAnalyzer:
    """Blockchain Node QPS Performance Analyzer + Bottleneck Mode Support - Supports multiple blockchains"""

    def __init__(self, output_dir: Optional[str] = None, benchmark_mode: str = "standard", bottleneck_mode: bool = False):
        """
        Initialize QPS analyzer
        
        Args:
            output_dir: Output directory path (if None, will be obtained from environment variable)
            benchmark_mode: Benchmark mode (quick/standard/intensive)
            bottleneck_mode: Whether to enable bottleneck analysis mode
        """
        # Apply unified style
        UnifiedChartStyle.setup_matplotlib()
        
        if output_dir is None:
            output_dir = os.environ.get('DATA_DIR', os.path.join(os.path.expanduser('~'), 'blockchain-node-benchmark-result'))
        
        self.output_dir = output_dir
        self.benchmark_mode = benchmark_mode
        self.bottleneck_mode = bottleneck_mode
        self.reports_dir = os.getenv('REPORTS_DIR', os.path.join(output_dir, 'current', 'reports'))
        os.makedirs(self.reports_dir, exist_ok=True)
        
        # Bottleneck detection threshold configuration
        self.cpu_threshold = int(os.getenv('BOTTLENECK_CPU_THRESHOLD', 85))
        self.memory_threshold = int(os.getenv('BOTTLENECK_MEMORY_THRESHOLD', 90))
        self.rpc_threshold = int(os.getenv('MAX_LATENCY_THRESHOLD', 1000))
        
        # Initialize CSV file path - fix missing attribute
        self.csv_file = self.get_latest_csv()

        # Using English labels system directly
        
        # Apply unified style configuration
        UnifiedChartStyle.setup_matplotlib()
        
        logger.info(f"🔍 QPS analyzer initialization completed, output directory: {output_dir}, benchmark mode: {benchmark_mode}")
        if bottleneck_mode:
            logger.info("🚨 Bottleneck analysis mode enabled")

    def _get_dynamic_key_metrics(self, df: pd.DataFrame) -> list:
        """Dynamically get key metric fields, replacing hardcoded device names - full version"""
        base_metrics = ['cpu_usage', 'mem_usage']
        
        # Dynamically find EBS utilization field (prioritize DATA device, then ACCOUNTS device)
        ebs_util_field = None
        # First find DATA device field (must exist)
        for col in df.columns:
            if col.startswith('data_') and col.endswith('_util'):
                ebs_util_field = col
                break
        
        # If no DATA device field, find ACCOUNTS device field (optional)
        if not ebs_util_field:
            for col in df.columns:
                if col.startswith('accounts_') and col.endswith('_util'):
                    ebs_util_field = col
                    break
        
        # Dynamically find EBS latency field (prioritize DATA device's r_await)
        ebs_latency_field = None
        # First find DATA device's r_await field
        for col in df.columns:
            if col.startswith('data_') and col.endswith('_r_await'):
                ebs_latency_field = col
                break
        
        # If no DATA device's r_await, find DATA device's avg_await
        if not ebs_latency_field:
            for col in df.columns:
                if col.startswith('data_') and col.endswith('_avg_await'):
                    ebs_latency_field = col
                    break
        
        # If DATA device has none, find ACCOUNTS device latency field (optional)
        if not ebs_latency_field:
            for col in df.columns:
                if col.startswith('accounts_') and col.endswith('_r_await'):
                    ebs_latency_field = col
                    break
        
        if not ebs_latency_field:
            for col in df.columns:
                if col.startswith('accounts_') and col.endswith('_avg_await'):
                    ebs_latency_field = col
                    break
        
        # Dynamically find other important EBS metrics (prioritize DATA device)
        ebs_iops_field = None
        # First find DATA device field
        for col in df.columns:
            if col.startswith('data_') and col.endswith('_total_iops'):
                ebs_iops_field = col
                break
        # If no DATA device field, find ACCOUNTS device field (optional)
        if not ebs_iops_field:
            for col in df.columns:
                if col.startswith('accounts_') and col.endswith('_total_iops'):
                    ebs_iops_field = col
                    break
        
        ebs_throughput_field = None
        # First find DATA device field
        for col in df.columns:
            if col.startswith('data_') and col.endswith('_throughput_mibs'):
                ebs_throughput_field = col
                break
        # If no DATA device field, find ACCOUNTS device field (optional)
        if not ebs_throughput_field:
            for col in df.columns:
                if col.startswith('accounts_') and col.endswith('_throughput_mibs'):
                    ebs_throughput_field = col
                    break
        
        ebs_queue_field = None
        # First find DATA device field
        for col in df.columns:
            if col.startswith('data_') and col.endswith('_aqu_sz'):
                ebs_queue_field = col
                break
        # If no DATA device field, find ACCOUNTS device field (optional)
        if not ebs_queue_field:
            for col in df.columns:
                if col.startswith('accounts_') and col.endswith('_aqu_sz'):
                    ebs_queue_field = col
                    break
        
        # Add discovered fields
        if ebs_util_field:
            base_metrics.append(ebs_util_field)
            logger.info(f"✅ Dynamically discovered EBS utilization field: {ebs_util_field}")
        
        if ebs_latency_field:
            base_metrics.append(ebs_latency_field)
            logger.info(f"✅ Dynamically discovered EBS latency field: {ebs_latency_field}")
        
        if ebs_iops_field:
            base_metrics.append(ebs_iops_field)
            logger.info(f"✅ Dynamically discovered EBS IOPS field: {ebs_iops_field}")
        
        if ebs_throughput_field:
            base_metrics.append(ebs_throughput_field)
            logger.info(f"✅ Dynamically discovered EBS throughput field: {ebs_throughput_field}")
        
        if ebs_queue_field:
            base_metrics.append(ebs_queue_field)
            logger.info(f"✅ Dynamically discovered EBS queue depth field: {ebs_queue_field}")
        
        if not any([ebs_util_field, ebs_latency_field, ebs_iops_field]):
            logger.warning("⚠️ No EBS-related fields discovered, may affect bottleneck analysis accuracy")
        
        logger.info(f"📊 Total dynamic metric fields: {len(base_metrics)}")
        return base_metrics
    


    def analyze_performance_cliff(self, df: pd.DataFrame, max_qps: int, bottleneck_qps: int) -> Dict[str, Any]:
        """Analyze performance cliff - identify points of sharp performance degradation"""
        try:
            cliff_analysis = {
                'max_qps': max_qps,
                'bottleneck_qps': bottleneck_qps,
                'performance_drop_percent': 0.0,  # Use float type for consistency
                'cliff_detected': False,
                'cliff_factors': [],
                'recommendations': []
            }
            
            if max_qps > 0 and bottleneck_qps > 0:
                # Calculate performance drop percentage
                drop_percent = ((bottleneck_qps - max_qps) / max_qps) * 100
                cliff_analysis['performance_drop_percent'] = drop_percent
                
                # Determine if it's a performance cliff (drop exceeds 20%)
                if abs(drop_percent) > 20:
                    cliff_analysis['cliff_detected'] = True
                    
                    # Analyze cliff factors
                    cliff_factors = self._identify_cliff_factors(df, max_qps, bottleneck_qps)
                    cliff_analysis['cliff_factors'] = cliff_factors
                    
                    # Generate recommendations
                    recommendations = self._generate_cliff_recommendations(cliff_factors, drop_percent)
                    cliff_analysis['recommendations'] = recommendations
                    
                    logger.info(f"🚨 Performance cliff detected: {drop_percent:.1f}% performance drop")
                else:
                    logger.info(f"📊 Performance change: {drop_percent:.1f}% (below cliff threshold)")
            
            return cliff_analysis
            
        except Exception as e:
            logger.error(f"❌ Performance cliff analysis failed: {e}")
            return {}

    def _identify_cliff_factors(self, df: pd.DataFrame, max_qps: int, bottleneck_qps: int) -> list:
        """Identify factors causing performance cliff"""
        cliff_factors = []
        
        try:
            # Find QPS column
            qps_column = None
            for col in ['current_qps', 'qps', 'requests_per_second']:
                if col in df.columns:
                    qps_column = col
                    break
            
            if not qps_column:
                return cliff_factors
            
            # Find data points corresponding to max QPS and bottleneck QPS
            max_qps_data = df[df[qps_column] <= max_qps].tail(1)
            bottleneck_qps_data = df[df[qps_column] >= bottleneck_qps].head(1)
            
            if len(max_qps_data) == 0 or len(bottleneck_qps_data) == 0:
                return cliff_factors
            
            # Compare key metrics changes - use dynamic field lookup instead of hardcoding
            key_metrics = self._get_dynamic_key_metrics(df)
            
            for metric in key_metrics:
                if metric in df.columns:
                    try:
                        max_value = max_qps_data[metric].iloc[0]
                        bottleneck_value = bottleneck_qps_data[metric].iloc[0]
                        
                        if pd.notna(max_value) and pd.notna(bottleneck_value) and max_value != 0:
                            change_percent = ((bottleneck_value - max_value) / max_value) * 100
                            
                            # If change exceeds 10%, consider it a cliff factor
                            if abs(change_percent) > 10:
                                cliff_factors.append({
                                    'metric': metric,
                                    'max_qps_value': float(max_value),
                                    'bottleneck_value': float(bottleneck_value),
                                    'change_percent': float(change_percent),
                                    'impact': 'high' if abs(change_percent) > 50 else 'medium'
                                })
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to analyze {metric} cliff factor: {e}")
            
            # Sort by impact level
            cliff_factors.sort(key=lambda x: abs(x['change_percent']), reverse=True)
            
        except Exception as e:
            logger.error(f"❌ Cliff factor identification failed: {e}")
        
        return cliff_factors

    def _generate_cliff_recommendations(self, cliff_factors: list, drop_percent: float) -> list:
        """Generate optimization recommendations based on cliff factors"""
        recommendations = []
        
        try:
            # General recommendations based on performance drop severity
            if abs(drop_percent) > 50:
                recommendations.append("Severe performance cliff: Recommend stopping test immediately and checking system status")
                recommendations.append("Consider reducing test intensity or optimizing system configuration")
            elif abs(drop_percent) > 30:
                recommendations.append("Significant performance drop: Recommend analyzing system bottlenecks and optimizing")
            
            # Recommendations based on specific cliff factors
            for factor in cliff_factors[:3]:  # Only process top 3 most important factors
                metric = factor['metric']
                change = factor['change_percent']
                
                if 'cpu' in metric.lower():
                    if change > 0:
                        recommendations.append(f"CPU usage surged {change:.1f}%: Consider upgrading CPU or optimizing application")
                    else:
                        recommendations.append(f"CPU usage abnormally dropped {abs(change):.1f}%: Check CPU scheduling issues")
                
                elif 'mem' in metric.lower():
                    if change > 0:
                        recommendations.append(f"Memory usage surged {change:.1f}%: Consider increasing memory or optimizing memory usage")
                    else:
                        recommendations.append(f"Memory usage abnormally dropped {abs(change):.1f}%: Check memory management issues")
                
                elif 'util' in metric.lower():
                    if change > 0:
                        recommendations.append(f"Disk utilization surged {change:.1f}%: Consider upgrading storage or optimizing I/O")
                
                elif 'await' in metric.lower():
                    if change > 0:
                        recommendations.append(f"Disk latency surged {change:.1f}%: Check storage performance bottleneck")
            
            # If no obvious cliff factors, provide general recommendations
            if not cliff_factors:
                recommendations.append("No obvious performance cliff factors found, recommend comprehensive system performance analysis")
                recommendations.append("Check network, application logic, and system configuration")
        
        except Exception as e:
            logger.error(f"❌ Failed to generate cliff recommendations: {e}")
        
        return recommendations

    def generate_cliff_analysis_chart(self, df: pd.DataFrame, cliff_analysis: Dict[str, Any]) -> Optional[plt.Figure]:
        """Generate performance cliff analysis chart"""
        try:
            if not cliff_analysis or not cliff_analysis.get('cliff_detected'):
                return None
            
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            # Using English title directly
            fig.suptitle('📉 Performance Cliff Analysis', fontsize=UnifiedChartStyle.FONT_CONFIG["title_size"], fontweight='bold', color=UnifiedChartStyle.COLORS["critical"])
            
            # 1. QPS performance curve
            qps_column = None
            for col in ['current_qps', 'qps', 'requests_per_second']:
                if col in df.columns:
                    qps_column = col
                    break
            
            if qps_column and len(df) > 0:
                axes[0, 0].plot(df.index, df[qps_column], 'b-', alpha=0.7, linewidth=2)
                
                # Mark max QPS and bottleneck QPS
                max_qps = cliff_analysis['max_qps']
                bottleneck_qps = cliff_analysis['bottleneck_qps']
                
                axes[0, 0].axhline(y=max_qps, color=UnifiedChartStyle.COLORS["success"], linestyle='--', linewidth=2,
                                 label=f'Max QPS: {max_qps}')
                axes[0, 0].axhline(y=bottleneck_qps, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', linewidth=2,
                                 label=f'Bottleneck QPS: {bottleneck_qps}')
                
                # Fill cliff area
                axes[0, 0].fill_between(df.index, max_qps, bottleneck_qps, 
                                      alpha=0.3, color=UnifiedChartStyle.COLORS["critical"], label='Performance Cliff')
                
                axes[0, 0].set_title('QPS Performance Cliff')
                axes[0, 0].set_xlabel('Time')
                axes[0, 0].set_ylabel('QPS')
                axes[0, 0].legend()
                axes[0, 0].grid(True, alpha=0.3)
            
            # 2. Cliff factor impact
            cliff_factors = cliff_analysis.get('cliff_factors', [])
            if cliff_factors:
                factor_names = [f['metric'] for f in cliff_factors[:5]]
                factor_changes = [abs(f['change_percent']) for f in cliff_factors[:5]]
                
                colors = ['red' if abs(f['change_percent']) > 50 else 'orange' 
                         for f in cliff_factors[:5]]
                
                axes[0, 1].barh(factor_names, factor_changes, color=colors, alpha=0.7)
                axes[0, 1].set_title('Cliff Factor Impact (%)')
                axes[0, 1].set_xlabel('Change Percentage')
                axes[0, 1].grid(True, alpha=0.3)
            
            # 3. Performance drop visualization
            drop_percent = cliff_analysis.get('performance_drop_percent', 0)
            categories = ['Before Cliff', 'After Cliff']
            values = [100, 100 + drop_percent]  # Relative performance
            colors = ['green', 'red']
            
            bars = axes[1, 0].bar(categories, values, color=colors, alpha=0.7)
            axes[1, 0].set_title(f'Performance Drop: {abs(drop_percent):.1f}%')
            axes[1, 0].set_ylabel('Relative Performance (%)')
            axes[1, 0].axhline(y=100, color='black', linestyle='-', alpha=0.3)
            
            # Add value labels
            for bar, value in zip(bars, values):
                axes[1, 0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                               f'{value:.1f}%', ha='center', va='bottom', fontweight='bold')
            
            # 4. Recommendations summary
            recommendations = cliff_analysis.get('recommendations', [])
            if recommendations:
                axes[1, 1].text(0.05, 0.95, 'Optimization Recommendations:', 
                               transform=axes[1, 1].transAxes, fontsize=UnifiedChartStyle.FONT_CONFIG["subtitle_size"], fontweight='bold',
                               verticalalignment='top')
                
                for i, rec in enumerate(recommendations[:5]):
                    axes[1, 1].text(0.05, 0.85 - i*0.15, f"• {rec}", 
                                   transform=axes[1, 1].transAxes, fontsize=UnifiedChartStyle.FONT_CONFIG["label_size"],
                                   verticalalignment='top', wrap=True)
            
            axes[1, 1].set_xlim(0, 1)
            axes[1, 1].set_ylim(0, 1)
            axes[1, 1].axis('off')
            
            plt.tight_layout()
            
            # Save chart
            chart_path = os.path.join(self.reports_dir, 'performance_cliff_analysis.png')
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            logger.info(f"📊 Performance cliff analysis chart saved: {chart_path}")
            
            return fig
            
        except Exception as e:
            logger.error(f"❌ Performance cliff chart generation failed: {e}")
            return None

    def get_latest_csv(self) -> Optional[str]:
        """CSV file search logic, supports multiple path patterns"""
        # Use LOGS_DIR environment variable, if not exists search by priority
        logs_dir = os.getenv('LOGS_DIR', os.path.join(self.output_dir, 'current', 'logs'))
        csv_patterns = [
            f"{logs_dir}/performance_latest.csv",
            f"{logs_dir}/performance_*.csv",
            f"{self.output_dir}/current/logs/performance_latest.csv",
            f"{self.output_dir}/current/logs/performance_*.csv",
            f"{self.output_dir}/archives/*/logs/performance_latest.csv",
            f"{self.output_dir}/archives/*/logs/performance_*.csv"
        ]
        
        for pattern in csv_patterns:
            csv_files = glob.glob(pattern)
            if csv_files:
                return max(csv_files, key=os.path.getctime)
        return None

    def load_and_clean_data(self) -> pd.DataFrame:
        """Load and clean monitoring data, improved error handling"""
        try:
            if not self.csv_file:
                print("⚠️  No CSV monitoring file found, proceeding with log analysis only")
                return pd.DataFrame()

            print(f"📊 Loading QPS monitoring data from: {os.path.basename(self.csv_file)}")
            
            # Read CSV directly using pandas - field mapper removed
            df = pd.read_csv(self.csv_file)

            print(f"📋 Raw data shape: {df.shape}")

            # Check if QPS-related data exists
            qps_columns = ['current_qps', 'qps', 'target_qps']
            qps_column = None
            for col in qps_columns:
                if col in df.columns:
                    qps_column = col
                    break
            
            if qps_column is None:
                print("⚠️  No QPS data found in CSV, this appears to be system monitoring data only")
                print("📊 Available columns:", ', '.join(df.columns[:10]))
                
                # Add virtual QPS columns for system monitoring data to avoid KeyError
                df['current_qps'] = 0  # Use numeric 0 instead of string '0'
                df['rpc_latency_ms'] = 0.0  # Add virtual RPC latency field
                df['elapsed_time'] = 0.0    # Add virtual time field
                df['remaining_time'] = 0.0  # Add virtual remaining time field
                df['qps_data_available'] = False
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
                return df

            # Process current_qps column
            df['current_qps'] = df[qps_column].astype(str)
            df['qps_data_available'] = True
            numeric_mask = pd.to_numeric(df['current_qps'], errors='coerce').notna()
            numeric_df = df[numeric_mask].copy()

            if len(numeric_df) == 0:
                print("⚠️  No numeric QPS data found")
                df['qps_data_available'] = False
                return df

            # Data type conversion
            numeric_df['current_qps'] = pd.to_numeric(numeric_df['current_qps'])
            numeric_df['timestamp'] = pd.to_datetime(numeric_df['timestamp'], errors='coerce')

            # Filter QPS=0 monitoring data, keep only actual test data
            if 'current_qps' in numeric_df.columns:
                original_count = len(numeric_df)
                numeric_df = numeric_df[numeric_df['current_qps'] > 0].copy()
                filtered_count = len(numeric_df)
                print(f"📊 Filtered QPS data: {filtered_count}/{original_count} active test points (QPS > 0)")

            # Clean numeric columns - use mapped standard field names
            numeric_cols = ['cpu_usage', 'mem_usage', 'rpc_latency_ms', 'elapsed_time', 'remaining_time']
            for col in numeric_cols:
                if col in numeric_df.columns:
                    numeric_df[col] = pd.to_numeric(numeric_df[col], errors='coerce')

            print(f"📊 Processed {len(numeric_df)} QPS monitoring data points")
            return numeric_df
            
        except Exception as e:
            logger.error(f"❌ Data loading and cleaning failed: {e}")
            return pd.DataFrame()

    def analyze_performance_metrics(self, df: pd.DataFrame) -> Tuple[Optional[pd.DataFrame], int]:
        """Analyze key performance metrics"""
        print("\n🎯 QPS Performance Metrics Analysis")
        print("=" * 50)

        if 'current_qps' not in df.columns or len(df) == 0:
            print("❌ No valid QPS data for analysis")
            return None, 0

        max_qps = df['current_qps'].max()
        qps_range = sorted(df['current_qps'].unique())

        print(f"Maximum QPS tested: {max_qps}")
        print(f"QPS range: {min(qps_range)} - {max_qps}")
        print(f"Number of QPS levels: {len(qps_range)}")

        # Group statistics by QPS
        qps_stats_dict = {
            'cpu_usage': ['mean', 'max'],
            'mem_usage': ['mean', 'max']
        }
        
        # Only add rpc_latency_ms field when it exists and has valid data
        if 'rpc_latency_ms' in df.columns and df['rpc_latency_ms'].notna().any():
            qps_stats_dict['rpc_latency_ms'] = ['mean', 'max']
        
        qps_stats = df.groupby('current_qps').agg(qps_stats_dict).round(2)

        print("\nQPS Performance Statistics:")
        print(qps_stats.to_string())

        return qps_stats, max_qps

    def identify_bottlenecks(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Identify performance bottlenecks"""
        print("\n🔍 QPS Performance Bottleneck Analysis")
        print("=" * 50)

        if len(df) == 0:
            print("❌ No data for bottleneck analysis")
            return {}

        bottlenecks = {}

        # CPU bottleneck
        if 'cpu_usage' in df.columns and 'current_qps' in df.columns:
            cpu_bottleneck = df[df['cpu_usage'] > self.cpu_threshold]['current_qps'].min()
            if pd.notna(cpu_bottleneck):
                bottlenecks['CPU'] = cpu_bottleneck

        # Memory bottleneck
        mem_bottleneck = df[df['mem_usage'] > self.memory_threshold]['current_qps'].min()
        if pd.notna(mem_bottleneck):
            bottlenecks['Memory'] = mem_bottleneck

        # RPC latency bottleneck
        if 'rpc_latency_ms' in df.columns and df['rpc_latency_ms'].notna().any():
            rpc_bottleneck = df[df['rpc_latency_ms'] > self.rpc_threshold]['current_qps'].min()
            if pd.notna(rpc_bottleneck):
                bottlenecks['RPC_Latency'] = rpc_bottleneck

        if bottlenecks:
            print("System bottlenecks detected:")
            for bottleneck_type, qps in bottlenecks.items():
                print(f"  {bottleneck_type}: First occurs at QPS {qps:,}" if not pd.isna(qps) else f"  {bottleneck_type}: First occurs at QPS N/A")
        else:
            print("✅ No critical system bottlenecks detected in tested range")

        return bottlenecks

    def generate_performance_charts(self, df: pd.DataFrame) -> Optional[plt.Figure]:
        """Generate performance charts - 2x3 layout"""
        print("\n📈 Generating performance charts...")

        if len(df) == 0:
            print("❌ No QPS data for chart generation")
            return None

        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle('Blockchain Node QPS Performance Analysis Dashboard', fontsize=UnifiedChartStyle.FONT_CONFIG["title_size"], fontweight='bold')

        # Load Vegeta Success Rate data
        success_df = self.load_vegeta_success_rates()
        has_success_data = not success_df.empty
        
        # Add latency numeric column for Vegeta data
        if has_success_data:
            success_df['avg_latency_ms'] = success_df['avg_latency'].apply(self._parse_latency_to_ms)

        # [0,0] CPU Time Series
        ax1 = axes[0, 0]
        qps_levels = sorted(df['current_qps'].unique())
        colors = plt.cm.tab10(np.linspace(0, 1, len(qps_levels)))
        
        for idx, qps in enumerate(qps_levels):
            df_step = df[df['current_qps'] == qps]
            ax1.plot(df_step['timestamp'], df_step['cpu_usage'], 
                    color=colors[idx], label=f'{int(qps)} QPS', linewidth=1.5, alpha=0.7)
        
        ax1.axhline(y=85, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', alpha=0.8, linewidth=2, label='Threshold (85%)')
        ax1.set_title('CPU Usage Time Series', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        ax1.set_xlabel('Time', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax1.set_ylabel('CPU %', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax1.legend(loc='upper left', bbox_to_anchor=(1.02, 1), ncol=1, fontsize=7)
        ax1.grid(True, alpha=0.3)
        UnifiedChartStyle.format_time_axis(ax1, df['timestamp'])

        # [0,1] Memory Time Series
        ax2 = axes[0, 1]
        for idx, qps in enumerate(qps_levels):
            df_step = df[df['current_qps'] == qps]
            ax2.plot(df_step['timestamp'], df_step['mem_usage'], 
                    color=colors[idx], label=f'{int(qps)} QPS', linewidth=1.5, alpha=0.7)
        
        ax2.axhline(y=90, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', alpha=0.8, linewidth=2, label='Threshold (90%)')
        ax2.set_title('Memory Usage Time Series', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        ax2.set_xlabel('Time', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax2.set_ylabel('Memory %', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax2.legend(loc='upper left', bbox_to_anchor=(1.02, 1), ncol=1, fontsize=7)
        ax2.grid(True, alpha=0.3)
        UnifiedChartStyle.format_time_axis(ax2, df['timestamp'])

        # [0,2] Latency Time Series
        ax3 = axes[0, 2]
        df_latency = df[df['rpc_latency_ms'] > 0]
        
        for idx, qps in enumerate(qps_levels):
            df_step = df_latency[df_latency['current_qps'] == qps]
            if len(df_step) > 0:
                ax3.plot(df_step['timestamp'], df_step['rpc_latency_ms'], 
                        color=colors[idx], label=f'{int(qps)} QPS', linewidth=1.5, marker='o', markersize=3, alpha=0.7)
        
        ax3.axhline(y=1000, color=UnifiedChartStyle.COLORS["warning"], linestyle='--', alpha=0.8, linewidth=2, label='Threshold (1s)')
        ax3.set_title('RPC Latency Time Series', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        ax3.set_xlabel('Time', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax3.set_ylabel('Latency (ms)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax3.legend(loc='upper left', bbox_to_anchor=(1.02, 1), ncol=1, fontsize=7)
        ax3.grid(True, alpha=0.3)
        UnifiedChartStyle.format_time_axis(ax3, df_latency['timestamp'])

        # [1,0] Latency & Success Rate vs QPS (dual Y-axis)
        ax4 = axes[1, 0]
        if has_success_data:
            line1 = ax4.plot(success_df['qps'], success_df['avg_latency_ms'], 
                            'ro-', alpha=0.7, markersize=6, linewidth=2, label='Avg Latency')
            ax4.axhline(y=1000, color=UnifiedChartStyle.COLORS["warning"], 
                       linestyle='--', alpha=0.8, linewidth=2, label='Latency Threshold (1s)')
            ax4.set_xlabel('QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax4.set_ylabel('Latency (ms)', color='r', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax4.tick_params(axis='y', labelcolor='r')
            ax4.grid(True, alpha=0.3)
            
            ax4_right = ax4.twinx()
            line2 = ax4_right.plot(success_df['qps'], success_df['success_rate'], 
                                  'g^-', alpha=0.7, markersize=8, linewidth=2, label='Success Rate')
            ax4_right.axhline(y=95, color=UnifiedChartStyle.COLORS["warning"], 
                             linestyle='--', alpha=0.8, linewidth=2, label='Success Threshold (95%)')
            ax4_right.set_ylabel('Success Rate (%)', color='g', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax4_right.set_ylim(0, 105)
            ax4_right.tick_params(axis='y', labelcolor='g')
            
            lines = line1 + line2
            labels = [l.get_label() for l in lines]
            ax4.legend(lines, labels, loc='upper left', fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
        else:
            ax4.plot(df['current_qps'], df['rpc_latency_ms'], 'ro-', alpha=0.7, markersize=4)
            ax4.axhline(y=1000, color=UnifiedChartStyle.COLORS["warning"], 
                       linestyle='--', alpha=0.8, label='High Latency (1s)')
            ax4.set_xlabel('QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax4.set_ylabel('Latency (ms)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax4.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
            ax4.grid(True, alpha=0.3)
        
        ax4.set_title('RPC Latency & Success Rate vs QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        
        # Disable scientific notation on axes
        ax4.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
        ax4.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))

        # [1,1] QPS vs Success Rate Scatter
        ax5 = axes[1, 1]
        if has_success_data:
            # Pure scatter plot (no connecting lines, as there's no intermediate data)
            colors_scatter = []
            for sr in success_df['success_rate']:
                if sr >= 95:
                    colors_scatter.append(UnifiedChartStyle.COLORS["success"])
                elif sr >= 80:
                    colors_scatter.append(UnifiedChartStyle.COLORS["warning"])
                else:
                    colors_scatter.append(UnifiedChartStyle.COLORS["critical"])
            
            # Draw scatter points (reference EBS chart style: small dots, no black border)
            ax5.scatter(success_df['qps'], success_df['success_rate'], 
                       c=colors_scatter, s=60, alpha=0.8, zorder=2)
            
            # Threshold line
            ax5.axhline(y=95, color=UnifiedChartStyle.COLORS["warning"], 
                       linestyle='--', alpha=0.8, linewidth=2, label='Threshold (95%)')
            
            # Annotate low success rate points
            for idx, row in success_df.iterrows():
                if row['success_rate'] < 95:
                    ax5.annotate(f"{int(row['qps'])}\n{row['success_rate']:.1f}%", 
                               xy=(row['qps'], row['success_rate']),
                               xytext=(0, -15), textcoords='offset points',
                               fontsize=8, color='red', ha='center', fontweight='bold')
            
            # Add color legend
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor=UnifiedChartStyle.COLORS["success"], label='Healthy (≥95%)'),
                Patch(facecolor=UnifiedChartStyle.COLORS["warning"], label='Warning (80-95%)'),
                Patch(facecolor=UnifiedChartStyle.COLORS["critical"], label='Critical (<80%)')
            ]
            ax5.legend(handles=legend_elements, loc='lower left', fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
            
            ax5.set_ylim(0, 105)
        
        ax5.set_title('QPS vs Success Rate (Performance Cliff Detection)', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        ax5.set_xlabel('QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax5.set_ylabel('Success Rate (%)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax5.grid(True, alpha=0.3)

        # [1,2] Success Rate Distribution
        ax6 = axes[1, 2]
        if has_success_data:
            ax6.hist(success_df['success_rate'], bins=15, alpha=0.7, color='skyblue', edgecolor='black', linewidth=1.5)
            
            mean_sr = success_df['success_rate'].mean()
            median_sr = success_df['success_rate'].median()
            ax6.axvline(mean_sr, color=UnifiedChartStyle.COLORS["critical"], 
                       linestyle='--', linewidth=2, label=f'Mean: {mean_sr:.1f}%')
            ax6.axvline(median_sr, color=UnifiedChartStyle.COLORS["warning"], 
                       linestyle='--', linewidth=2, label=f'Median: {median_sr:.1f}%')
            ax6.axvline(95, color=UnifiedChartStyle.COLORS["success"], 
                       linestyle='--', linewidth=2, label='Threshold (95%)')
        
        ax6.set_title('Success Rate Distribution', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        ax6.set_xlabel('Success Rate (%)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax6.set_ylabel('Frequency', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax6.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
        ax6.grid(True, alpha=0.3)

        # Apply layout using unified style
        UnifiedChartStyle.apply_layout('auto')
        
        # Save chart
        reports_dir = os.getenv('REPORTS_DIR', os.path.join(self.output_dir, 'current', 'reports'))
        chart_file = os.path.join(reports_dir, 'qps_performance_analysis.png')
        os.makedirs(os.path.dirname(chart_file), exist_ok=True)
        plt.savefig(chart_file, dpi=300, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        print(f"✅ Performance charts saved: {chart_file}")
        plt.close()

        return fig

    def load_vegeta_success_rates(self) -> pd.DataFrame:
        """Extract QPS, Success Rate, Latency from vegeta txt reports"""
        reports_dir = os.getenv('REPORTS_DIR', os.path.join(self.output_dir, 'current', 'reports'))
        vegeta_reports = glob.glob(f"{reports_dir}/vegeta_*qps_*.txt")
        data = []
        
        for report in vegeta_reports:
            try:
                filename = os.path.basename(report)
                qps = int(re.search(r'vegeta_(\d+)qps_', filename).group(1))
                
                with open(report, 'r') as f:
                    content = f.read()
                
                # Extract Success Rate
                success_match = re.search(r'Success\s+\[ratio\]\s+([\d.]+)%', content)
                success_rate = float(success_match.group(1)) if success_match else 0.0
                
                # Extract Latency (mean)
                latency_match = re.search(r'Latencies\s+\[min, mean,.*?\]\s+[\d.µms]+,\s+([\d.µmsh]+),', content)
                avg_latency = latency_match.group(1) if latency_match else 'N/A'
                
                data.append({
                    'qps': qps,
                    'success_rate': success_rate,
                    'avg_latency': avg_latency
                })
            except Exception as e:
                logger.warning(f"⚠️  Failed to parse {filename}: {e}")
        
        if data:
            df = pd.DataFrame(data).sort_values('qps')
            print(f"✅ Loaded success rate data for {len(df)} QPS levels")
            return df
        else:
            print("⚠️  No success rate data found")
            return pd.DataFrame()
    
    def _parse_latency_to_ms(self, latency_str: str) -> float:
        """Convert Vegeta's latency string to milliseconds numeric value"""
        try:
            if 'm' in latency_str and 's' in latency_str:  # e.g. "1m27s"
                parts = latency_str.replace('m', ' ').replace('s', '').split()
                minutes = float(parts[0]) if len(parts) > 0 else 0
                seconds = float(parts[1]) if len(parts) > 1 else 0
                return (minutes * 60 + seconds) * 1000
            elif 's' in latency_str and 'ms' not in latency_str:  # e.g. "31.43s"
                return float(latency_str.replace('s', '')) * 1000
            elif 'ms' in latency_str:  # e.g. "110.256ms"
                return float(latency_str.replace('ms', ''))
            elif 'µs' in latency_str:  # e.g. "76.231µs"
                return float(latency_str.replace('µs', '')) / 1000
            else:
                return 0.0
        except:
            return 0.0

    def analyze_vegeta_reports(self) -> Optional[pd.DataFrame]:
        """Analyze Vegeta test reports"""
        print("\n📋 Vegeta Reports Analysis")
        print("=" * 50)

        reports_dir = os.getenv('REPORTS_DIR', os.path.join(self.output_dir, 'current', 'reports'))
        reports = glob.glob(f"{reports_dir}/vegeta_*.txt")  # Only parse vegeta reports
        if not reports:
            print("No Vegeta reports found")
            return None

        report_data = []
        for report_file in sorted(reports):
            filename = os.path.basename(report_file)  # Initialize outside try block
            try:
                # Fix filename parsing logic: handle vegeta_1000qps_timestamp.txt format
                qps_part = filename.split('_')[1]  # Get "1000qps" part
                qps = int(qps_part.replace('qps', ''))  # Remove "qps" suffix and convert to integer
                with open(report_file, 'r') as f:
                    content = f.read()

                success_rate = 0
                avg_latency = 'N/A'
                p99_latency = 'N/A'

                for line in content.split('\n'):
                    if 'Success' in line and '[ratio]' in line:
                        success_rate = float(line.split()[-1].replace('%', ''))
                    elif 'Latencies' in line and '[min, mean,' in line:
                        parts = line.split()
                        if len(parts) >= 8:
                            avg_latency = parts[6].replace(',', '')
                            p99_latency = parts[8].replace(',', '')

                report_data.append({
                    'QPS': qps,
                    'Success_Rate': success_rate,
                    'Avg_Latency': avg_latency,
                    'P99_Latency': p99_latency
                })
            except Exception as e:
                print(f"Warning: Could not parse {report_file}: {e}")

        if report_data:
            vegeta_df = pd.DataFrame(report_data)
            print(vegeta_df.to_string(index=False))
            return vegeta_df

        return None

    def _evaluate_performance_by_bottleneck_analysis(self, benchmark_mode: str, max_qps: int, 
                                                   bottlenecks: Dict[str, Any], avg_cpu: float, 
                                                   avg_mem: float, avg_rpc: float) -> Dict[str, Any]:
        """
        Scientific performance evaluation based on bottleneck analysis
        Replace hardcoded 60000/40000/20000 logic
        """
        
        # Only intensive benchmark mode can provide accurate performance level evaluation
        if benchmark_mode != "intensive":
            return {
                'performance_level': 'Unable to Evaluate',
                'performance_grade': 'N/A',
                'evaluation_reason': f'{benchmark_mode} benchmark mode cannot accurately evaluate system performance level, intensive mode required for deep analysis',
                'evaluation_basis': 'insufficient_benchmark_depth',
                'max_sustainable_qps': max_qps,
                'recommendations': [
                    f'Current {benchmark_mode} benchmark is only for quick verification',
                    'For accurate performance level evaluation, please use intensive benchmark mode',
                    'Intensive benchmark will trigger system bottlenecks to obtain accurate performance evaluation'
                ]
            }
        
        # Bottleneck analysis evaluation in intensive benchmark mode
        bottleneck_types = bottlenecks.get('detected_bottlenecks', [])
        bottleneck_count = len(bottleneck_types)
        
        # Calculate bottleneck severity score
        bottleneck_score = self._calculate_bottleneck_severity_score(
            bottleneck_types, avg_cpu, avg_mem, avg_rpc
        )
        
        # Scientific level evaluation based on bottleneck score
        if bottleneck_score < 0.2:
            # Low bottleneck score = Excellent performance
            level = "Excellent"
            grade = "A (Excellent)"
            reason = f"System shows no obvious bottlenecks at {max_qps} QPS, excellent performance"
            
        elif bottleneck_score < 0.4:
            # Medium bottleneck score = Good performance
            level = "Good"
            grade = "B (Good)"
            reason = f"System shows minor bottlenecks at {max_qps} QPS: {', '.join(bottleneck_types)}"
            
        elif bottleneck_score < 0.7:
            # Higher bottleneck score = Acceptable performance
            level = "Acceptable"
            grade = "C (Acceptable)"
            reason = f"System shows noticeable bottlenecks at {max_qps} QPS: {', '.join(bottleneck_types)}"
            
        else:
            # High bottleneck score = Needs improvement
            level = "Needs Improvement"
            grade = "D (Needs Improvement)"
            reason = f"System shows serious bottlenecks at {max_qps} QPS: {', '.join(bottleneck_types)}"
        
        return {
            'performance_level': level,
            'performance_grade': grade,
            'evaluation_reason': reason,
            'evaluation_basis': 'intensive_bottleneck_analysis',
            'max_sustainable_qps': max_qps,
            'bottleneck_score': bottleneck_score,
            'bottleneck_types': bottleneck_types,
            'bottleneck_count': bottleneck_count,
            'recommendations': self._generate_bottleneck_based_recommendations(
                bottleneck_types, bottleneck_score, max_qps
            )
        }
    
    def _calculate_bottleneck_severity_score(self, bottleneck_types: list, 
                                           avg_cpu: float, avg_mem: float, avg_rpc: float) -> float:
        """Calculate bottleneck severity score"""
        
        # Bottleneck type weights
        bottleneck_weights = {
            'CPU': 0.2,
            'Memory': 0.25,
            'EBS': 0.3,
            'Network': 0.15,
            'RPC': 0.1
        }
        
        total_score = 0.0
        
        # Calculate score based on detected bottleneck types
        for bottleneck_type in bottleneck_types:
            weight = bottleneck_weights.get(bottleneck_type, 0.1)
            
            # Adjust severity based on specific metrics
            severity_multiplier = 1.0
            if bottleneck_type == 'CPU' and avg_cpu > (self.cpu_threshold + 5):
                severity_multiplier = 1.5
            elif bottleneck_type == 'Memory' and avg_mem > (self.memory_threshold + 5):
                severity_multiplier = 1.5
            elif bottleneck_type == 'RPC' and avg_rpc > (self.rpc_threshold * 2):
                severity_multiplier = 1.5
            
            total_score += weight * severity_multiplier
        
        # Normalize score to 0-1 range
        return min(total_score, 1.0)
    
    def _generate_capacity_assessment(self, performance_evaluation: Dict[str, Any], max_qps: int) -> str:
        """Generate capacity assessment based on performance evaluation"""
        performance_level = performance_evaluation.get('performance_level', 'Unknown')
        bottleneck_score = performance_evaluation.get('bottleneck_score', 0)
        
        if performance_level == "Excellent":
            return f"Current configuration can stably handle high load (tested up to {max_qps:,} QPS, bottleneck score: {bottleneck_score:.3f})" if not pd.isna(max_qps) else f"Current configuration can stably handle high load (insufficient test data, bottleneck score: {bottleneck_score:.3f})"
        elif performance_level == "Good":
            return f"Current configuration can handle medium-high load (tested up to {max_qps:,} QPS, bottleneck score: {bottleneck_score:.3f})" if not pd.isna(max_qps) else f"Current configuration can handle medium-high load (insufficient test data, bottleneck score: {bottleneck_score:.3f})"
        elif performance_level == "Acceptable":
            return f"Current configuration suitable for medium load (tested up to {max_qps:,} QPS, bottleneck score: {bottleneck_score:.3f})" if not pd.isna(max_qps) else f"Current configuration suitable for medium load (insufficient test data, bottleneck score: {bottleneck_score:.3f})"
        elif performance_level == "Needs Improvement":
            return f"Current configuration needs optimization to handle high load (tested up to {max_qps:,} QPS, bottleneck score: {bottleneck_score:.3f})" if not pd.isna(max_qps) else f"Current configuration needs optimization to handle high load (insufficient test data, bottleneck score: {bottleneck_score:.3f})"
        else:
            return f"Intensive benchmark mode required for accurate capacity assessment"

    def _generate_bottleneck_based_recommendations(self, bottleneck_types: list, 
                                                 bottleneck_score: float, max_qps: int) -> list:
        """Generate optimization recommendations based on bottleneck analysis"""
        recommendations = []
        
        if bottleneck_score < 0.2:
            recommendations.extend([
                f"🎉 System performance is excellent, current configuration can stably support {max_qps} QPS",
                "💡 Consider further increasing QPS targets or optimizing cost efficiency",
                "📊 Recommend regular monitoring to maintain current performance level"
            ])
        else:
            # Targeted recommendations based on specific bottleneck types
            if 'CPU' in bottleneck_types:
                recommendations.append("🔧 CPU bottleneck: Consider upgrading CPU or optimizing compute-intensive processes")
            if 'Memory' in bottleneck_types:
                recommendations.append("🔧 Memory bottleneck: Consider increasing memory or optimizing memory usage")
            if 'EBS' in bottleneck_types:
                recommendations.append("🔧 Storage bottleneck: Consider upgrading EBS type or optimizing I/O patterns")
            if 'Network' in bottleneck_types:
                recommendations.append("🔧 Network bottleneck: Consider upgrading network bandwidth or optimizing network configuration")
            if 'RPC' in bottleneck_types:
                recommendations.append("🔧 RPC bottleneck: Consider optimizing RPC configuration or increasing RPC connection pool")
        
        return recommendations

    def generate_performance_report(self, df: pd.DataFrame, max_qps: int, 
                                  bottlenecks: Dict[str, Any], benchmark_mode: str = "standard") -> str:
        """Generate performance report based on bottleneck analysis"""
        print("\n📄 Generating performance report...")

        # Basic performance metrics
        avg_cpu = df['cpu_usage'].mean() if len(df) > 0 and 'cpu_usage' in df.columns else 0
        avg_mem = df['mem_usage'].mean() if len(df) > 0 and 'mem_usage' in df.columns else 0
        avg_rpc = df['rpc_latency_ms'].mean() if len(df) > 0 and 'rpc_latency_ms' in df.columns and df['rpc_latency_ms'].notna().any() else 0

        # Performance evaluation based on benchmark mode and bottleneck analysis
        performance_evaluation = self._evaluate_performance_by_bottleneck_analysis(
            benchmark_mode, max_qps, bottlenecks, avg_cpu, avg_mem, avg_rpc
        )

        # Handle possible NaN values
        max_qps_display = f"{max_qps:,}" if not pd.isna(max_qps) else "N/A"
        
        report = f"""# Blockchain Node QPS Performance Analysis Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
- **Maximum QPS Achieved**: {max_qps_display}
- **Performance Grade**: {performance_evaluation['performance_grade']}
- **Performance Level**: {performance_evaluation['performance_level']}
- **Benchmark Mode**: {benchmark_mode}
- **Test Duration**: {len(df)} monitoring points

## Performance Evaluation
- **Evaluation Basis**: {performance_evaluation['evaluation_basis']}
- **Evaluation Reason**: {performance_evaluation['evaluation_reason']}

## System Performance Metrics
- **Average CPU Usage**: {avg_cpu:.1f}%
- **Average Memory Usage**: {avg_mem:.1f}%
- **Average RPC Latency**: {avg_rpc:.1f}ms
- **CPU Peak**: {(df['cpu_usage'].max() if len(df) > 0 and 'cpu_usage' in df.columns else 0):.1f}%
- **Memory Peak**: {(df['mem_usage'].max() if len(df) > 0 and 'mem_usage' in df.columns else 0):.1f}%
- **RPC Latency Peak**: {(df['rpc_latency_ms'].max() if len(df) > 0 and 'rpc_latency_ms' in df.columns and df['rpc_latency_ms'].notna().any() else 0):.1f}ms

## Performance Bottlenecks Analysis
"""

        if performance_evaluation.get('bottleneck_types'):
            report += f"- **Bottleneck Score**: {performance_evaluation.get('bottleneck_score', 0):.3f}\n"
            report += f"- **Detected Bottlenecks**: {', '.join(performance_evaluation['bottleneck_types'])}\n"
            for bottleneck_type in performance_evaluation['bottleneck_types']:
                qps = bottlenecks.get(bottleneck_type, 'Unknown')
                report += f"  - **{bottleneck_type}**: First detected at {qps} QPS\n" if isinstance(qps, int) else f"  - **{bottleneck_type}**: {qps}\n"
        else:
            report += "- ✅ No critical bottlenecks detected in tested range\n"

        report += f"""
## Optimization Recommendations

### Based on Bottleneck Analysis
"""

        # Use bottleneck-based recommendations
        for recommendation in performance_evaluation.get('recommendations', []):
            report += f"- {recommendation}\n"

        # Calculate recommended production QPS
        recommended_qps_display = f"{int(max_qps * 0.8):,} (80% of maximum tested)" if not pd.isna(max_qps) else "N/A (insufficient test data)"
        
        report += f"""
### Production Deployment Guidelines
- **Recommended Production QPS**: {recommended_qps_display}
- **Monitoring Thresholds**: 
  - Alert if CPU usage > 85%
  - Alert if Memory usage > 90%
  - Alert if RPC latency > 1000ms sustained
- **Capacity Assessment**: {self._generate_capacity_assessment(performance_evaluation, max_qps)}

## Files Generated
- **Performance Charts**: `{self.reports_dir}/qps_performance_analysis.png`
- **Raw QPS Monitoring Data**: `{self.csv_file or 'N/A'}`
- **Vegeta Test Reports**: `{self.reports_dir}/`

---
*Report generated by Blockchain Node QPS Analyzer*
"""

        # Save report
        reports_dir = os.getenv('REPORTS_DIR', os.path.join(self.output_dir, 'current', 'reports'))
        report_file = os.path.join(reports_dir, 'qps_performance_report.md')
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        with open(report_file, 'w') as f:
            f.write(report)

        print(f"✅ Performance report saved: {report_file}")
        return report

    def run_qps_analysis(self) -> Dict[str, Any]:
        """Run complete QPS analysis"""
        print("🚀 Starting Blockchain Node QPS Performance Analysis")
        print("=" * 60)

        # Load QPS monitoring data
        df = self.load_and_clean_data()

        # Execute QPS performance analysis
        qps_stats, max_qps = self.analyze_performance_metrics(df)
        bottlenecks = self.identify_bottlenecks(df)

        # Generate charts and reports
        self.generate_performance_charts(df)
        vegeta_analysis = self.analyze_vegeta_reports()
        report = self.generate_performance_report(df, max_qps, bottlenecks, self.benchmark_mode)

        analysis_results = {
            'dataframe': df,
            'qps_stats': qps_stats,
            'max_qps': max_qps,
            'bottlenecks': bottlenecks,
            'vegeta_analysis': vegeta_analysis,
            'report': report
        }

        print("\n🎉 QPS Analysis Completed Successfully!")
        print("Generated files:")
        print(f"  📊 Charts: {self.reports_dir}/qps_performance_analysis.png")
        print(f"  📄 Report: {self.reports_dir}/qps_performance_report.md")

        return analysis_results


def main():
    """Main execution function - supports bottleneck mode and performance cliff analysis"""
    parser = argparse.ArgumentParser(description='QPS Analyzer - supports bottleneck mode')
    parser.add_argument('csv_file', help='CSV data file path')
    parser.add_argument('--benchmark-mode', default='standard', choices=['quick', 'standard', 'intensive'], 
                       help='Benchmark mode (default: standard)')
    parser.add_argument('--bottleneck-mode', action='store_true', help='Enable bottleneck analysis mode')
    parser.add_argument('--cliff-analysis', action='store_true', help='Enable performance cliff analysis')
    parser.add_argument('--max-qps', type=int, help='Maximum successful QPS')
    parser.add_argument('--bottleneck-qps', type=int, help='Bottleneck trigger QPS')
    parser.add_argument('--output-dir', help='Output directory path')
    
    args = parser.parse_args()
    
    try:
        if not os.path.exists(args.csv_file):
            logger.error(f"❌ CSV file does not exist: {args.csv_file}")
            return 1
        
        # Initialize analyzer
        analyzer = NodeQPSAnalyzer(args.output_dir, args.benchmark_mode, args.bottleneck_mode)
        
        # Read data
        df = pd.read_csv(args.csv_file)
        logger.info(f"📊 Data loaded: {len(df)} records")
        
        # Performance cliff analysis
        if args.cliff_analysis and args.max_qps and args.bottleneck_qps:
            logger.info("📉 Executing performance cliff analysis")
            cliff_analysis = analyzer.analyze_performance_cliff(df, args.max_qps, args.bottleneck_qps)
            
            # Generate cliff analysis chart
            cliff_chart = analyzer.generate_cliff_analysis_chart(df, cliff_analysis)
            
            # Save analysis results
            cliff_result_file = os.path.join(analyzer.reports_dir, 'performance_cliff_analysis.json')
            with open(cliff_result_file, 'w') as f:
                json.dump(cliff_analysis, f, indent=2, default=str)
            logger.info(f"📊 Performance cliff analysis results saved: {cliff_result_file}")
        
        # Execute standard QPS analysis
        result = analyzer.run_qps_analysis()
        
        if result:
            logger.info("✅ QPS analysis completed")
            return 0
        else:
            logger.error("❌ QPS analysis failed")
            return 1
            
    except Exception as e:
        logger.error(f"❌ QPS analysis execution failed: {e}")
        return 1

# Usage example
if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("📋 QPS Analyzer Usage Examples:")
        print("python qps_analyzer.py data.csv")
        print("python qps_analyzer.py data.csv --bottleneck-mode")
        print("python qps_analyzer.py data.csv --cliff-analysis --max-qps 5000 --bottleneck-qps 3000")
    else:
        sys.exit(main())
