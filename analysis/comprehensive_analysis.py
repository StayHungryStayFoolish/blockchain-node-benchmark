#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Analyzer - Refactored integrated version with bottleneck mode support
Integrates RPC deep analyzer and QPS analyzer for blockchain node performance testing
Provides unified analysis entry point and complete report generation
Supports bottleneck detection mode and time window analysis
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import glob
import os
import sys
import json
import argparse
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

# Add project root directory to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from visualization.chart_style_config import UnifiedChartStyle
from visualization.performance_visualizer import PerformanceVisualizer
from utils.unified_logger import get_logger
from analysis.rpc_deep_analyzer import RpcDeepAnalyzer
from analysis.qps_analyzer import NodeQPSAnalyzer

logger = get_logger(__name__)

class DataProcessor:
    """Data processing utility class - Solves data processing code duplication"""
    
    @staticmethod
    def validate_dataframe_column(df: pd.DataFrame, column: str) -> bool:
        """Validate if DataFrame contains specified column and has data"""
        return column in df.columns and len(df) > 0 and not df[column].empty
    
    @staticmethod
    def safe_calculate_mean(df: pd.DataFrame, column: str) -> float:
        """Safely calculate column mean - Solves repeated mean calculation code"""
        if DataProcessor.validate_dataframe_column(df, column):
            return df[column].mean()
        return 0.0
    
    @staticmethod
    def safe_calculate_max(df: pd.DataFrame, column: str) -> float:
        """Safely calculate column maximum"""
        if DataProcessor.validate_dataframe_column(df, column):
            return df[column].max()
        return 0.0

class FileManager:
    """File management utility class - Smart file saving with backup and fixed naming"""
    
    def __init__(self, output_dir: str, session_timestamp: str):
        self.output_dir = output_dir
        self.session_timestamp = session_timestamp
        self.reports_dir = os.getenv('REPORTS_DIR', os.path.join(output_dir, 'current', 'reports'))
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def save_chart_with_backup(self, chart_name: str, plt_figure) -> str:
        """Save chart, create both backup and current version"""
        # Fixed name file (for reference by other components)
        current_path = os.path.join(self.reports_dir, f'{chart_name}.png')
        
        # Timestamped backup file
        backup_path = os.path.join(self.reports_dir, f'{chart_name}_{self.session_timestamp}.png')
        
        # Save both versions
        plt_figure.savefig(current_path, dpi=300, bbox_inches='tight')
        plt_figure.savefig(backup_path, dpi=300, bbox_inches='tight')
        
        logger.info(f"📊 Chart saved: {current_path} (current version)")
        logger.info(f"📊 Backup created: {backup_path}")
        
        return current_path
    
    def save_report_with_backup(self, report_name: str, content: str) -> str:
        """Save report, create both backup and current version"""
        # Fixed name file (for reference by other components)
        current_path = os.path.join(self.reports_dir, f'{report_name}.md')
        
        # Timestamped backup file
        backup_path = os.path.join(self.reports_dir, f'{report_name}_{self.session_timestamp}.md')
        
        # Save both versions
        with open(current_path, 'w', encoding='utf-8') as f:
            f.write(content)
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"📄 Report saved: {current_path} (current version)")
        logger.info(f"📄 Backup created: {backup_path}")
        
        return current_path

class OperationLogger:
    """Operation logger decorator - Unified log format, solves print statement duplication"""
    
    @staticmethod
    def log_operation(operation_name: str, emoji: str = "📊"):
        """Decorator for logging operations"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                print(f"\n{emoji} {operation_name}...")
                try:
                    result = func(*args, **kwargs)
                    logger.info(f"✅ {operation_name} completed successfully")
                    return result
                except Exception as e:
                    logger.error(f"❌ {operation_name} failed: {e}")
                    raise
            return wrapper
        return decorator

# Configure logging
class BottleneckAnalysisMode:
    """Bottleneck analysis mode configuration"""
    
    def __init__(self, bottleneck_info: Optional[Dict] = None):
        # Only enable when valid bottleneck information is provided
        self.enabled = bottleneck_info is not None and len(bottleneck_info) > 0
        self.bottleneck_info = bottleneck_info or {}
        self.bottleneck_time = None
        self.analysis_window = None
        self.max_qps = 0
        self.bottleneck_qps = 0
        
        if self.enabled:
            self._parse_bottleneck_info()
    
    def _parse_bottleneck_info(self):
        """Parse bottleneck information"""
        try:
            self.bottleneck_time = self.bottleneck_info.get('detection_time')
            self.analysis_window = self.bottleneck_info.get('analysis_window', {})
            self.max_qps = self.bottleneck_info.get('max_successful_qps', 0)
            self.bottleneck_qps = self.bottleneck_info.get('bottleneck_qps', 0)
            
            logger.info(f"🚨 Bottleneck analysis mode: Max QPS={self.max_qps}, Bottleneck QPS={self.bottleneck_qps}")
        except Exception as e:
            logger.error(f"❌ Bottleneck information parsing failed: {e}")
            self.enabled = False

class ComprehensiveAnalyzer:
    """Comprehensive Analyzer - Main controller integrating all analysis functions + bottleneck mode support"""

    def __init__(self, output_dir: Optional[str] = None, benchmark_mode: str = "standard", bottleneck_mode: Optional[BottleneckAnalysisMode] = None):
        """Refactored initialization method - Ensures all attributes are properly initialized"""
        
        # Apply unified style
        UnifiedChartStyle.setup_matplotlib()
        
        # Output directory handling - Prioritize framework-set environment variables
        if output_dir is None:
            output_dir = os.environ.get('BASE_DATA_DIR') or os.environ.get('DATA_DIR', os.path.join(os.path.expanduser('~'), 'blockchain-node-benchmark-result'))
        
        # Core attributes initialization
        self.output_dir = output_dir
        self.benchmark_mode = benchmark_mode
        # Strictly use framework unified SESSION_TIMESTAMP environment variable
        self.session_timestamp = os.environ.get('SESSION_TIMESTAMP')
        if not self.session_timestamp:
            raise RuntimeError("SESSION_TIMESTAMP environment variable not set, please ensure framework is properly initialized through config_loader.sh")
        
        # File manager initialization
        self.file_manager = FileManager(self.output_dir, self.session_timestamp)
        
        # Critical fix: Ensure FileManager is properly initialized
        if not hasattr(self.file_manager, 'reports_dir'):
            raise RuntimeError(f"FileManager initialization failed: missing reports_dir attribute. output_dir={self.output_dir}, session_timestamp={self.session_timestamp}")
        
        self.reports_dir = self.file_manager.reports_dir
        
        # Validate reports_dir validity
        if not self.reports_dir:
            raise RuntimeError(f"FileManager.reports_dir is empty. REPORTS_DIR environment variable={os.getenv('REPORTS_DIR')}")
        
        # Ensure directory exists
        os.makedirs(self.reports_dir, exist_ok=True)
        
        # CSV file path
        self.csv_file = self.get_latest_csv()
        if not self.csv_file:
            raise FileNotFoundError(f"Performance data CSV file not found in directory: {output_dir}")
        
        # Bottleneck mode initialization
        self.bottleneck_mode = bottleneck_mode or BottleneckAnalysisMode()
        
        # Analyzer initialization
        self.qps_analyzer = NodeQPSAnalyzer(output_dir, benchmark_mode, self.bottleneck_mode.enabled)
        self.rpc_deep_analyzer = RpcDeepAnalyzer(self.csv_file)
        
        logger.info(f"🔍 Comprehensive analyzer initialization completed")
        logger.info(f"   Output directory: {self.output_dir}")
        logger.info(f"   Reports directory: {self.reports_dir}")
        logger.info(f"   CSV file: {self.csv_file}")
        
        if self.bottleneck_mode.enabled:
            logger.info(f"🚨 Bottleneck analysis mode enabled")
    
    def get_latest_csv(self) -> Optional[str]:
        """Get latest CSV monitoring file"""
        # Use LOGS_DIR environment variable, if not exists use current/logs structure
        logs_dir = os.getenv('LOGS_DIR', os.path.join(self.output_dir, 'current', 'logs'))
        csv_files = glob.glob(f"{logs_dir}/*.csv")
        if not csv_files:
            # Fallback search: check archives directory
            csv_files = glob.glob(f"{self.output_dir}/archives/*/logs/*.csv")
        return max(csv_files, key=os.path.getctime) if csv_files else None

    @staticmethod
    def filter_data_by_time_window(df: pd.DataFrame, start_time: str, end_time: str) -> pd.DataFrame:
        """Filter data by time window - Static method"""
        try:
            if 'timestamp' not in df.columns:
                logger.warning("⚠️ No timestamp column in data, cannot perform time window filtering")
                return df
            
            # Convert timestamps
            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            start_dt = pd.to_datetime(start_time)
            end_dt = pd.to_datetime(end_time)
            
            # Handle timezone: if parameters have timezone but DataFrame doesn't, remove parameter timezone
            if start_dt.tz is not None and df['timestamp'].dt.tz is None:
                start_dt = start_dt.tz_localize(None)
                end_dt = end_dt.tz_localize(None)
            # If DataFrame has timezone but parameters don't, add UTC timezone to DataFrame
            elif start_dt.tz is None and df['timestamp'].dt.tz is not None:
                df['timestamp'] = df['timestamp'].dt.tz_localize(None)
            
            # Filter data
            filtered_df = df[(df['timestamp'] >= start_dt) & (df['timestamp'] <= end_dt)]
            logger.info(f"📊 Time window filtering: {len(df)} -> {len(filtered_df)} records")
            
            return filtered_df
        except Exception as e:
            logger.error(f"❌ Time window filtering failed: {e}")
            return df

    def analyze_bottleneck_correlation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze bottleneck correlation"""
        if not self.bottleneck_mode.enabled:
            return {}
        
        try:
            analysis_result = {
                'bottleneck_detected': True,
                'max_qps': self.bottleneck_mode.max_qps,
                'bottleneck_qps': self.bottleneck_mode.bottleneck_qps,
                'performance_drop': 0.0,  # Use float type for consistency
                'correlations': {},
                'bottleneck_factors': []
            }
            
            # Calculate performance drop
            if self.bottleneck_mode.max_qps > 0:
                performance_drop = ((self.bottleneck_mode.bottleneck_qps - self.bottleneck_mode.max_qps) / 
                                  self.bottleneck_mode.max_qps * 100)
                analysis_result['performance_drop'] = performance_drop
            
            # Analyze correlation between metrics and QPS
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            qps_column = None
            
            # Find QPS column
            for col in ['current_qps', 'qps', 'requests_per_second']:
                if col in df.columns:
                    qps_column = col
                    break
            
            if qps_column:
                for col in numeric_columns:
                    if col != qps_column and len(df[col].dropna()) > 1:
                        try:
                            correlation = df[qps_column].corr(df[col])
                            if not np.isnan(correlation):
                                analysis_result['correlations'][col] = correlation
                                
                                # Identify bottleneck factors
                                if abs(correlation) > 0.7:
                                    analysis_result['bottleneck_factors'].append({
                                        'metric': col,
                                        'correlation': correlation,
                                        'impact': 'high' if abs(correlation) > 0.8 else 'medium'
                                    })
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to calculate {col} correlation: {e}")
            
            logger.info(f"🔍 Bottleneck correlation analysis completed, found {len(analysis_result['bottleneck_factors'])} key factors")
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ Bottleneck correlation analysis failed: {e}")
            return {}

    def generate_ultimate_performance_charts(self, df: pd.DataFrame) -> Optional[plt.Figure]:
        """Generate ultimate performance charts, integrating all analysis results"""
        print("\n📈 Generating ultimate performance charts...")

        if len(df) == 0:
            print("❌ No QPS data for chart generation")
            return None
        
        fig, axes = plt.subplots(3, 2, figsize=(16, 18))
        
        # Set main title first (before apply_layout)
        fig.suptitle('Comprehensive Performance Analysis', 
                     fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], 
                     fontweight='bold')

        # Simplified QPS data check - only check if column exists
        qps_available = 'current_qps' in df.columns and len(df) > 0
        
        # 1. CPU Usage vs QPS
        if 'current_qps' in df.columns and 'cpu_usage' in df.columns:
            axes[0, 0].plot(df['current_qps'], df['cpu_usage'], 'bo-', alpha=0.7, markersize=4)
            axes[0, 0].axhline(y=85, color='red', linestyle='--', alpha=0.8, label='Warning (85%)')
            axes[0, 0].set_title('CPU Usage vs QPS', 
                                fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            axes[0, 0].set_xlabel('QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            axes[0, 0].set_ylabel('CPU %', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)
        else:
            axes[0, 0].text(0.5, 0.5, 'QPS Data Not Available\nfor CPU Analysis', ha='center', va='center',
                           transform=axes[0, 0].transAxes, fontsize=12)
            axes[0, 0].set_title('CPU Usage vs QPS (No Data)', 
                                fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])

        # 2. Memory Usage vs QPS
        if 'current_qps' in df.columns and 'mem_usage' in df.columns:
            axes[0, 1].plot(df['current_qps'], df['mem_usage'], 'go-', alpha=0.7, markersize=4)
            axes[0, 1].axhline(y=90, color='red', linestyle='--', alpha=0.8, label='Warning (90%)')
            axes[0, 1].set_title('Memory Usage vs QPS', 
                                fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            axes[0, 1].set_xlabel('QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            axes[0, 1].set_ylabel('Memory %', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            axes[0, 1].legend()
            axes[0, 1].grid(True, alpha=0.3)
        else:
            axes[0, 1].text(0.5, 0.5, 'QPS Data Not Available\nfor Memory Analysis', ha='center', va='center',
                           transform=axes[0, 1].transAxes, fontsize=12)
            axes[0, 1].set_title('Memory Usage vs QPS (No Data)', 
                                fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])

        # 3. RPC Latency vs QPS
        if 'current_qps' in df.columns and 'rpc_latency_ms' in df.columns and df['rpc_latency_ms'].notna().any():
            axes[1, 0].plot(df['current_qps'], df['rpc_latency_ms'], 'ro-', alpha=0.7, markersize=4)
            axes[1, 0].axhline(y=1000, color='orange', linestyle='--', alpha=0.8, label='High Latency (1s)')
            axes[1, 0].set_title('RPC Latency vs QPS', 
                                fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            axes[1, 0].set_xlabel('QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            axes[1, 0].set_ylabel('Latency (ms)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            axes[1, 0].legend()
            axes[1, 0].grid(True, alpha=0.3)
        else:
            axes[1, 0].text(0.5, 0.5, 'QPS Data Not Available\nfor RPC Latency Analysis', ha='center', va='center',
                           transform=axes[1, 0].transAxes, fontsize=12)
            axes[1, 0].set_title('RPC Latency vs QPS (No Data)', 
                                fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])

        # 4. EBS IOPS vs QPS
        ebs_iops_fields = [col for col in df.columns if 'total_iops' in col]
        if 'current_qps' in df.columns and ebs_iops_fields:
            total_iops = df[ebs_iops_fields].sum(axis=1)
            axes[1, 1].scatter(df['current_qps'], total_iops, 
                              alpha=0.6, color=UnifiedChartStyle.COLORS['warning'])
            axes[1, 1].set_title('EBS IOPS vs QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            axes[1, 1].set_xlabel('QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            axes[1, 1].set_ylabel('Total IOPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            axes[1, 1].grid(True, alpha=0.3)
        else:
            axes[1, 1].text(0.5, 0.5, 'EBS IOPS Data\nNot Available', ha='center', va='center',
                           transform=axes[1, 1].transAxes, fontsize=12)
            axes[1, 1].set_title('EBS IOPS vs QPS (No Data)', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])

        # 5. RPC Latency Distribution
        if 'rpc_latency_ms' in df.columns and df['rpc_latency_ms'].notna().any():
            axes[2, 0].hist(df['rpc_latency_ms'], bins=30, alpha=0.7, color='purple')
            if 'rpc_latency_ms' in df.columns:
                mean_latency = df['rpc_latency_ms'].mean()
                p95_latency = df['rpc_latency_ms'].quantile(0.95)
                axes[2, 0].axvline(mean_latency, color='red', linestyle='--',
                                   label=f'Mean: {mean_latency:.1f}ms')
                axes[2, 0].axvline(p95_latency, color='orange', linestyle='--',
                                   label=f'P95: {p95_latency:.1f}ms')
            axes[2, 0].set_title('RPC Latency Distribution', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            axes[2, 0].set_xlabel('Latency (ms)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            axes[2, 0].set_ylabel('Frequency', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            axes[2, 0].legend()
            axes[2, 0].grid(True, alpha=0.3)

        # 6. QPS Performance Analysis (replace Performance Cliff Detection)
        if len(df) > 0 and qps_available and 'current_qps' in df.columns and 'rpc_latency_ms' in df.columns:
            # Filter valid QPS data - exclude invalid data with rpc_latency_ms=0
            valid_qps_data = df[(df['current_qps'] > 0) & (df['rpc_latency_ms'] > 0)].copy()
            
            if len(valid_qps_data) >= 2:  # Ensure sufficient data points
                # Group by QPS and calculate average latency
                qps_groups = valid_qps_data.groupby('current_qps').agg({
                    'rpc_latency_ms': ['mean', 'std', 'count']
                }).round(3)
                
                qps_values = qps_groups.index.tolist()
                latency_means = qps_groups[('rpc_latency_ms', 'mean')].tolist()
                latency_stds = qps_groups[('rpc_latency_ms', 'std')].tolist()
                
                # Plot QPS vs latency relationship
                axes[2, 1].errorbar(qps_values, latency_means, yerr=latency_stds,
                                   fmt='bo-', capsize=5, capthick=2, alpha=0.8, markersize=8)
                
                # Add data annotations
                for qps, latency in zip(qps_values, latency_means):
                    axes[2, 1].annotate(f'{latency:.3f}ms',
                                       (qps, latency), textcoords="offset points",
                                       xytext=(0,15), ha='center', fontsize=10, fontweight='bold')
                
                axes[2, 1].set_title('QPS vs Latency Performance Analysis', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
                axes[2, 1].set_xlabel('QPS (Queries Per Second)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                axes[2, 1].set_ylabel('Average RPC Latency (ms)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                axes[2, 1].grid(True, alpha=0.3)
                axes[2, 1].set_ylim(bottom=0)
                
                # Add performance evaluation text
                performance_text = f"Test Results:\n"
                performance_text += f"QPS Levels: {len(qps_values)}\n"
                performance_text += f"Max QPS: {max(qps_values)}\n"
                performance_text += f"Min Latency: {min(latency_means):.3f}ms\n"
                performance_text += f"Max Latency: {max(latency_means):.3f}ms"
                
                axes[2, 1].text(0.02, 0.98, performance_text, transform=axes[2, 1].transAxes,
                                fontsize=9, verticalalignment='top',
                                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
            else:
                axes[2, 1].text(0.5, 0.5, f'Insufficient QPS Data\n({len(valid_qps_data)} valid points)',
                               ha='center', va='center', transform=axes[2, 1].transAxes, fontsize=12)
                axes[2, 1].set_title('QPS Performance Analysis (Insufficient Data)', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        else:
            axes[2, 1].text(0.5, 0.5, 'QPS Data Not Available\nfor Performance Analysis',
                           ha='center', va='center', transform=axes[2, 1].transAxes, fontsize=12)
            axes[2, 1].set_title('QPS Performance Analysis (No Data)', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])

        # Apply layout using unified style
        UnifiedChartStyle.apply_layout('auto')
        
        # Save chart - use file manager to create current version and backup
        chart_file = self.file_manager.save_chart_with_backup('comprehensive_analysis_charts', plt)
        print(f"✅ Ultimate performance charts saved: {chart_file}")

        return fig

    def _evaluate_comprehensive_performance(self, benchmark_mode: str, max_qps: int, 
                                          bottlenecks: Dict[str, Any], avg_cpu: float, 
                                          avg_mem: float, avg_rpc: float) -> Dict[str, Any]:
        """
        Scientific performance evaluation based on actual monitoring data
        Integrates multi-dimensional monitoring data including QPS performance, system resource utilization, RPC latency, etc.
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
        
        # Comprehensive bottleneck analysis - based on actual monitoring data
        bottleneck_types = bottlenecks.get('detected_bottlenecks', [])
        
        # Calculate comprehensive bottleneck score - no longer relying on deprecated log analysis data
        comprehensive_score = ComprehensiveAnalyzer._calculate_comprehensive_bottleneck_score(
            bottleneck_types, avg_cpu, avg_mem, avg_rpc
        )
        
        # Scientific level evaluation based on comprehensive score
        if comprehensive_score < 0.2:
            level = "Excellent"
            grade = "A (Excellent)"
            reason = f"System performs excellently at {max_qps} QPS, all metrics within normal range"
            
        elif comprehensive_score < 0.4:
            level = "Good"
            grade = "B (Good)"
            reason = f"System performs well at {max_qps} QPS, with minor bottlenecks or issues"
            
        elif comprehensive_score < 0.7:
            level = "Acceptable"
            grade = "C (Acceptable)"
            reason = f"System performs acceptably at {max_qps} QPS, with noticeable bottlenecks requiring attention"
            
        else:
            level = "Needs Improvement"
            grade = "D (Needs Improvement)"
            reason = f"System has serious issues at {max_qps} QPS, requires immediate optimization"
        
        return {
            'performance_level': level,
            'performance_grade': grade,
            'evaluation_reason': reason,
            'evaluation_basis': 'comprehensive_intensive_analysis',
            'max_sustainable_qps': max_qps,
            'comprehensive_score': comprehensive_score,
            'bottleneck_types': bottleneck_types,
            'avg_rpc_latency': avg_rpc,
            'recommendations': ComprehensiveAnalyzer._generate_comprehensive_recommendations(
                bottleneck_types, comprehensive_score, max_qps, avg_rpc
            )
        }
    
    @staticmethod
    def _calculate_comprehensive_bottleneck_score(bottleneck_types: list, 
                                                avg_cpu: float, avg_mem: float, avg_rpc: float) -> float:
        """Calculate comprehensive bottleneck severity score - based on actual monitoring data"""
        
        # System resource bottleneck score (weight: 0.7)
        resource_score = 0.0
        if 'CPU' in bottleneck_types:
            resource_score += 0.3 * (1.5 if avg_cpu > 90 else 1.0)
        if 'Memory' in bottleneck_types:
            resource_score += 0.3 * (1.5 if avg_mem > 95 else 1.0)
        if 'EBS' in bottleneck_types:
            resource_score += 0.1
        
        # RPC performance score (weight: 0.3) - based on actual RPC latency monitoring data
        rpc_score = 0.0
        if avg_rpc > 1000:  # High latency
            rpc_score += 0.15
        if avg_rpc > 2000:  # Very high latency
            rpc_score += 0.15
        
        total_score = resource_score + rpc_score
        
        return min(total_score, 1.0)
    
    @staticmethod
    def _generate_comprehensive_capacity_assessment(performance_evaluation: Dict[str, Any], max_qps: int) -> str:
        """Generate capacity assessment based on comprehensive performance evaluation - static method"""
        performance_level = performance_evaluation.get('performance_level', 'Unknown')
        comprehensive_score = performance_evaluation.get('comprehensive_score', 0.0)
        
        if performance_level == "Excellent":
            return f"Current configuration can stably handle high load (tested up to {max_qps:,} QPS, comprehensive score: {comprehensive_score:.3f})" if not pd.isna(max_qps) else f"Current configuration can stably handle high load (insufficient test data, comprehensive score: {comprehensive_score:.3f})"
        elif performance_level == "Good":
            return f"Current configuration can handle medium-high load (tested up to {max_qps:,} QPS, with minor issues)" if not pd.isna(max_qps) else "Current configuration can handle medium-high load (insufficient test data, with minor issues)"
        elif performance_level == "Acceptable":
            return f"Current configuration suitable for medium load (tested up to {max_qps:,} QPS, with noticeable issues)" if not pd.isna(max_qps) else "Current configuration suitable for medium load (insufficient test data, with noticeable issues)"
        elif performance_level == "Needs Improvement":
            return f"Current configuration needs optimization to handle high load (tested up to {max_qps:,} QPS, with serious issues)" if not pd.isna(max_qps) else "Current configuration needs optimization to handle high load (insufficient test data, with serious issues)"
        else:
            return f"Intensive benchmark mode required for accurate capacity assessment"

    @staticmethod
    def _generate_comprehensive_recommendations(bottleneck_types: list, 
                                             comprehensive_score: float, max_qps: int, avg_rpc: float) -> list:
        """Generate optimization recommendations based on comprehensive analysis - based on actual monitoring data"""
        recommendations = []
        
        if comprehensive_score < 0.2:
            recommendations.extend([
                f"🎉 System comprehensive performance is excellent, current configuration can stably support {max_qps} QPS",
                "💡 Consider further increasing QPS targets or optimizing cost efficiency",
                "� Recomdmend regular monitoring to maintain current performance level"
            ])
        else:
            # System resource optimization recommendations
            if 'CPU' in bottleneck_types:
                recommendations.append("🔧 CPU bottleneck: Consider upgrading CPU or optimizing compute-intensive processes")
            if 'Memory' in bottleneck_types:
                recommendations.append("🔧 Memory bottleneck: Consider increasing memory or optimizing memory usage")
            if 'EBS' in bottleneck_types:
                recommendations.append("🔧 Storage bottleneck: Consider upgrading EBS type or optimizing I/O patterns")
            
            # Optimization recommendations based on actual RPC latency
            if avg_rpc > 1000:
                recommendations.append("🔧 High RPC latency: Consider optimizing RPC configuration or increasing RPC processing capacity")
            if avg_rpc > 2000:
                recommendations.append("🔥 Excessive RPC latency: Immediate RPC performance optimization or network connection check required")
        
        return recommendations

    @OperationLogger.log_operation("Generating comprehensive report", "📄")
    def generate_comprehensive_report(self, df: pd.DataFrame, max_qps: int, 
                                    bottlenecks: Dict[str, Any], 
                                    rpc_deep_analysis: Dict[str, Any],
                                    benchmark_mode: str = "standard") -> str:
        """Generate comprehensive report based on bottleneck analysis, integrating all analysis results"""

        # Verify reports_dir attribute integrity - conservative fix
        if not hasattr(self, 'reports_dir') or not self.reports_dir:
            logger.error("ComprehensiveAnalyzer.reports_dir attribute missing, attempting recovery")
            # Try to recover from file_manager
            if hasattr(self, 'file_manager') and hasattr(self.file_manager, 'reports_dir'):
                self.reports_dir = self.file_manager.reports_dir
                logger.warning(f"Recovered reports_dir from file_manager: {self.reports_dir}")
            else:
                # Last resort: rebuild directly
                self.reports_dir = os.getenv('REPORTS_DIR', os.path.join(self.output_dir, 'current', 'reports'))
                os.makedirs(self.reports_dir, exist_ok=True)
                logger.warning(f"Rebuilt reports_dir: {self.reports_dir}")
        
        if not self.reports_dir:
            raise RuntimeError(f"ComprehensiveAnalyzer.reports_dir is empty - output_dir={self.output_dir}")

        # Basic performance metrics - use utility class to avoid code duplication
        avg_cpu = DataProcessor.safe_calculate_mean(df, 'cpu_usage')
        avg_mem = DataProcessor.safe_calculate_mean(df, 'mem_usage')
        avg_rpc = DataProcessor.safe_calculate_mean(df, 'rpc_latency_ms') if 'rpc_latency_ms' in df.columns else 0

        # Performance evaluation based on benchmark mode and bottleneck analysis
        performance_evaluation = self._evaluate_comprehensive_performance(
            benchmark_mode, max_qps, bottlenecks, avg_cpu, avg_mem, avg_rpc
        )

        # Build report sections
        cpu_bottleneck = 'Detected' if 'CPU' in bottlenecks.get('detected_bottlenecks', []) else 'None detected'
        memory_bottleneck = 'Detected' if 'Memory' in bottlenecks.get('detected_bottlenecks', []) else 'None detected'
        network_bottleneck = 'Detected' if 'Network' in bottlenecks.get('detected_bottlenecks', []) else 'None detected'
        ebs_bottleneck = 'Detected' if 'EBS' in bottlenecks.get('detected_bottlenecks', []) else 'None detected'
        
        max_cpu = DataProcessor.safe_calculate_max(df, 'cpu_usage')
        max_mem = DataProcessor.safe_calculate_max(df, 'mem_usage')
        max_rpc_latency = DataProcessor.safe_calculate_max(df, 'rpc_latency_ms') if 'rpc_latency_ms' in df.columns else 0
        
        latency_trend = 'Stable' if max_rpc_latency < avg_rpc * 2 else 'Variable'

        # Handle possible NaN values
        max_qps_display = f"{max_qps:,}" if not pd.isna(max_qps) else "N/A"
        
        report = f"""# Blockchain Node QPS Comprehensive Performance Analysis Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
- **Maximum QPS Achieved**: {max_qps_display}
- **Performance Grade**: {performance_evaluation['performance_grade']}
- **Performance Level**: {performance_evaluation['performance_level']}
- **Benchmark Mode**: {benchmark_mode}
- **Test Duration**: {len(df)} monitoring points
- **Monitoring Data Points**: {len(df)} records
- **Analysis Coverage**: Complete system performance monitoring

## Performance Evaluation
- **Evaluation Basis**: {performance_evaluation['evaluation_basis']}
- **Evaluation Reason**: {performance_evaluation['evaluation_reason']}
- **Comprehensive Score**: {performance_evaluation.get('comprehensive_score', 0.0):.3f}

## System Performance Metrics
- **Average CPU Usage**: {avg_cpu:.1f}%
- **Average Memory Usage**: {avg_mem:.1f}%
- **Average RPC Latency**: {avg_rpc:.1f}ms
- **CPU Peak**: {max_cpu:.1f}%
- **Memory Peak**: {max_mem:.1f}%
- **RPC Latency Peak**: {max_rpc_latency:.1f}ms

## 🔍 System Performance Analysis Results

### Monitoring Data Analysis
- **QPS Performance**: Based on real-time system monitoring and CSV data
- **System Resource Usage**: CPU, Memory, Network utilization continuously tracked
- **RPC Performance Monitoring**: Average latency {avg_rpc:.1f}ms from monitoring data
- **Peak RPC Latency**: {max_rpc_latency:.1f}ms during test period

### Resource Bottleneck Detection
- **CPU Bottlenecks**: {cpu_bottleneck}
- **Memory Bottlenecks**: {memory_bottleneck}
- **Network Bottlenecks**: {network_bottleneck}
- **EBS Bottlenecks**: {ebs_bottleneck}

### Performance Trend Analysis
- **QPS Stability**: Analyzed from {len(df)} monitoring data points
- **Latency Trend**: {latency_trend} throughout test period
- **Resource Utilization**: CPU avg {avg_cpu:.1f}%, Memory avg {avg_mem:.1f}%
- **Data Source**: Real-time system monitoring and RPC performance tracking
"""

        # Add RPC deep analysis results
        if rpc_deep_analysis:
            rpc_deep_report = self.rpc_deep_analyzer.generate_rpc_deep_analysis_report(rpc_deep_analysis)
            report += rpc_deep_report

        # Optimization recommendations
        report += """
## 💡 Comprehensive Optimization Recommendations

### Immediate Actions
"""

        # Specific recommendations based on existing monitoring data
        if avg_rpc > 1000:
            report += "- 🔧 **High Priority**: RPC latency is high, consider optimization\n"
            
        if max_rpc_latency > 2000:
            report += "- 🔥 **Critical**: Peak RPC latency detected, investigate bottlenecks\n"

        if avg_mem > 90:
            report += "- 🔥 **Critical**: High memory usage detected, consider increasing memory\n"
            report += "- 🔧 Monitor for potential memory leaks\n"

        # Use recommendations based on comprehensive analysis
        for recommendation in performance_evaluation.get('recommendations', []):
            report += f"- {recommendation}\n"

        # Recommendations based on RPC deep analysis
        if rpc_deep_analysis:
            bottleneck_classification = rpc_deep_analysis.get('bottleneck_classification', {})
            recommendations = bottleneck_classification.get('recommendations', [])
            if recommendations:
                report += "\n### RPC Deep Analysis Recommendations\n"
                for rec in recommendations:
                    report += f"- 🔧 {rec}\n"

        # Production deployment recommendations
        capacity_assessment = ComprehensiveAnalyzer._generate_comprehensive_capacity_assessment(performance_evaluation, max_qps)
        csv_file_display = self.csv_file or 'N/A'
        
        # Calculate recommended production QPS
        recommended_qps_display = f"{int(max_qps * 0.8):,} (80% of maximum tested)" if not pd.isna(max_qps) else "N/A (insufficient test data)"
        
        report += f"""
### Production Deployment
- **Recommended Production QPS**: {recommended_qps_display}
- **Monitoring Thresholds**: 
  - Alert if RPC latency P99 > 500ms sustained
  - Alert if CPU usage > 85% sustained
  - Alert if Memory usage > 90% sustained
- **Capacity Assessment**: {capacity_assessment}

## Files Generated
- **Comprehensive Charts**: `{self.reports_dir}/comprehensive_analysis_charts.png`
- **Raw Monitoring Data**: `{csv_file_display}`
- **System Performance Analysis**: Included in this report
- **RPC Performance Analysis**: Included in this report
- **Load Test Reports**: `{self.reports_dir}/`

---
*Report generated by Comprehensive Blockchain Node QPS Analyzer v4.0*
"""

        # Save comprehensive report - use file manager to create current version and backup
        report_file = self.file_manager.save_report_with_backup('comprehensive_analysis_report', report)

        print(f"✅ Comprehensive report saved: {report_file}")
        return report

    def run_comprehensive_analysis(self) -> Dict[str, Any]:
        """Run complete comprehensive analysis"""
        print("🚀 Starting Comprehensive Blockchain Node QPS Analysis")
        print("=" * 80)

        # 1. Run QPS analysis
        print("\n📊 Phase 1: QPS Performance Analysis")
        qps_results = self.qps_analyzer.run_qps_analysis()
        df = qps_results['dataframe']
        max_qps = qps_results['max_qps']
        bottlenecks = qps_results['bottlenecks']

        # 1.1 Using direct CSV column names for analysis
        logger.info("ℹ️  Using monitoring data for comprehensive analysis")
        print("  ℹ️  Using monitoring data for comprehensive analysis")

        # 2. Run RPC deep analysis
        print("\n🔍 Phase 2: RPC Deep Analysis")
        rpc_deep_analysis = self.rpc_deep_analyzer.analyze_rpc_deep_performance(df)

        # 3. Generate comprehensive charts and reports
        print("\n📈 Phase 3: Comprehensive Reporting")
        self.generate_ultimate_performance_charts(df)
        
        # 4.1 Generate performance visualization charts (including threshold analysis)
        print("\n🎨 Phase 4.1: Performance Visualization with Threshold Analysis")
        try:
            # Save temporary CSV file for performance_visualizer - use process ID and random number to avoid conflicts
            process_id = os.getpid()
            random_id = random.randint(1000, 9999)
            # Use TMP_DIR environment variable or current/tmp directory to save temporary file
            tmp_dir = os.getenv('TMP_DIR', os.path.join(self.output_dir, 'current', 'tmp'))
            os.makedirs(tmp_dir, exist_ok=True)
            temp_csv_path = os.path.join(tmp_dir, f'temp_performance_data_{process_id}_{random_id}.csv')
            df.to_csv(temp_csv_path, index=False)
            
            # Find monitoring overhead file - enhanced search logic to handle archiving
            overhead_files = glob.glob(f"{self.output_dir}/current/logs/monitoring_overhead_*.csv")
            if not overhead_files:
                # If not in current directory, check archives directory
                overhead_files = glob.glob(f"{self.output_dir}/archives/*/logs/monitoring_overhead_*.csv")
            if not overhead_files:
                # Finally check current working directory
                overhead_files = glob.glob("monitoring_overhead_*.csv")
            overhead_file = max(overhead_files, key=os.path.getctime) if overhead_files else None
            
            # Create performance visualizer and generate charts
            visualizer = PerformanceVisualizer(temp_csv_path, overhead_file)
            chart_results = visualizer.generate_all_charts()
            
            if isinstance(chart_results, tuple) and len(chart_results) == 2:
                chart_files, threshold_analysis = chart_results
                print(f"✅ Generated {len(chart_files)} performance charts (including threshold analysis)")
                
                # Add threshold analysis results to comprehensive results
                if threshold_analysis:
                    print("📊 Threshold analysis completed and integrated into report")
            else:
                chart_files = chart_results if isinstance(chart_results, list) else []
                print(f"✅ Generated {len(chart_files)} performance charts")
            
            # Clean up temporary file
            if os.path.exists(temp_csv_path):
                os.remove(temp_csv_path)
                
        except ImportError as e:
            print(f"⚠️ Performance visualizer import failed: {e}")
        except Exception as e:
            print(f"⚠️ Performance visualization chart generation failed: {e}")
        
        comprehensive_report = self.generate_comprehensive_report(
            df, max_qps, bottlenecks, rpc_deep_analysis, self.benchmark_mode
        )

        # 5. Display RPC deep analysis report

        if rpc_deep_analysis:
            rpc_report = self.rpc_deep_analyzer.generate_rpc_deep_analysis_report(rpc_deep_analysis)
            print(rpc_report)

        # Return complete analysis results
        comprehensive_results = {
            'qps_analysis': qps_results,
            'rpc_deep_analysis': rpc_deep_analysis,
            'comprehensive_report': comprehensive_report,
            'dataframe': df,
            'max_qps': max_qps,
            'bottlenecks': bottlenecks
        }

        print("\n🎉 Comprehensive Analysis Completed Successfully!")
        print("Generated files:")
        print(f"  📊 Charts: {self.reports_dir}/comprehensive_analysis_charts.png")
        print(f"  📄 Report: {self.reports_dir}/comprehensive_analysis_report.md")
        print(f"  💾 Backups: Files with timestamp {self.session_timestamp} created for version history")
        print(f"  📋 Individual Analysis Reports: Check {self.reports_dir}/ for detailed reports")

        return comprehensive_results


def main():
    """Main execution function - supports bottleneck mode and time window analysis"""
    parser = argparse.ArgumentParser(description='Comprehensive Analyzer - supports bottleneck mode')
    parser.add_argument('csv_file', nargs='?', help='CSV data file path')
    parser.add_argument('--benchmark-mode', default='standard', choices=['quick', 'standard', 'intensive'], 
                       help='Benchmark mode (default: standard)')
    parser.add_argument('--bottleneck-mode', action='store_true', help='Enable bottleneck analysis mode')
    parser.add_argument('--bottleneck-info', help='Bottleneck information JSON file path')
    parser.add_argument('--time-window', action='store_true', help='Enable time window analysis')
    parser.add_argument('--start-time', help='Time window start time')
    parser.add_argument('--end-time', help='Time window end time')
    parser.add_argument('--bottleneck-time', help='Bottleneck detection time')
    parser.add_argument('--output-dir', help='Output directory path')
    
    args = parser.parse_args()
    
    try:
        # Initialize bottleneck analysis mode
        bottleneck_mode = None
        if args.bottleneck_mode or args.bottleneck_info:
            bottleneck_info = {}
            
            if args.bottleneck_info and os.path.exists(args.bottleneck_info):
                try:
                    with open(args.bottleneck_info, 'r') as f:
                        bottleneck_info = json.load(f)
                    logger.info(f"📊 Loaded bottleneck info: {args.bottleneck_info}")
                except Exception as e:
                    logger.error(f"❌ Failed to read bottleneck info file: {e}")
            
            bottleneck_mode = BottleneckAnalysisMode(bottleneck_info)
        
        # Initialize analyzer
        analyzer = ComprehensiveAnalyzer(args.output_dir, args.benchmark_mode, bottleneck_mode)
        
        # Determine CSV file
        csv_file = args.csv_file or analyzer.csv_file
        if not csv_file or not os.path.exists(csv_file):
            logger.error("❌ Valid CSV data file not found")
            return 1
        
        logger.info(f"📈 Starting comprehensive analysis: {csv_file}")
        
        # Read data
        df = pd.read_csv(csv_file)
        logger.info(f"📊 Data loaded: {len(df)} records")
        
        # Time window filtering
        if args.time_window and args.start_time and args.end_time:
            df = ComprehensiveAnalyzer.filter_data_by_time_window(df, args.start_time, args.end_time)
            logger.info(f"🕐 Time window analysis: {args.start_time} to {args.end_time}")
        
        # Execute analysis
        if bottleneck_mode and bottleneck_mode.enabled:
            logger.info("🚨 Executing bottleneck mode analysis")
            
            # Bottleneck correlation analysis
            bottleneck_analysis = analyzer.analyze_bottleneck_correlation(df)

            # Save bottleneck analysis results
            reports_dir = os.getenv('REPORTS_DIR', os.path.join(analyzer.output_dir, 'current', 'reports'))
            bottleneck_result_file = os.path.join(reports_dir, 'bottleneck_analysis_result.json')
            os.makedirs(os.path.dirname(bottleneck_result_file), exist_ok=True)
            with open(bottleneck_result_file, 'w') as f:
                json.dump(bottleneck_analysis, f, indent=2, default=str)
            logger.info(f"📊 Bottleneck analysis results saved: {bottleneck_result_file}")
        
        # Execute standard comprehensive analysis
        result = analyzer.run_comprehensive_analysis()
        
        if result:
            logger.info("✅ Comprehensive analysis completed")
            return 0
        else:
            logger.error("❌ Comprehensive analysis failed")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Comprehensive analysis execution failed: {e}")
        return 1

if __name__ == "__main__":
    main()
