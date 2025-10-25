#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Visualizer - Production Version (CSV Field Consistency Fixed)
Uses unified CSV data processor to ensure field access consistency and reliability
"""

import argparse
import os
import sys
import glob
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.dates as mdates
import seaborn as sns
import numpy as np
import traceback
from datetime import datetime
from pathlib import Path
from matplotlib.patches import Patch

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from visualization.ebs_chart_generator import EBSChartGenerator
from visualization.device_manager import DeviceManager
from visualization.chart_style_config import UnifiedChartStyle, load_framework_config, create_chart_title
from visualization.advanced_chart_generator import AdvancedChartGenerator
from utils.csv_data_processor import CSVDataProcessor
from utils.unit_converter import UnitConverter
from analysis.cpu_ebs_correlation_analyzer import CPUEBSCorrelationAnalyzer

def get_visualization_thresholds():
    temp_df = pd.DataFrame()
    temp_manager = DeviceManager(temp_df)
    return temp_manager.get_visualization_thresholds()

def format_summary_text(device_info, data_stats, accounts_stats=None):
    temp_df = pd.DataFrame()
    temp_manager = DeviceManager(temp_df)
    return temp_manager.format_summary_text(device_info, data_stats, accounts_stats)

def add_text_summary(ax, summary_text, title):
    """辅助函数：统一文本摘要样式"""
    ax.axis('off')
    ax.text(0.05, 0.95, summary_text, transform=ax.transAxes, 
           fontsize=11, verticalalignment='top', fontfamily='monospace',
           bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
    ax.set_title(title)

def setup_font():
    return UnifiedChartStyle.setup_matplotlib()

def format_time_axis(ax, df_timestamp):
    """
    格式化时间轴显示 - 根据时间跨度自动选择格式
    
    Args:
        ax: matplotlib axis对象
        df_timestamp: pandas datetime series
    """
    if len(df_timestamp) == 0:
        return
    
    time_span = (df_timestamp.iloc[-1] - df_timestamp.iloc[0]).total_seconds()
    
    if time_span < 300:  # 小于5分钟，显示 时:分:秒
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    elif time_span < 3600:  # 小于1小时，显示 时:分
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    elif time_span < 86400:  # 小于1天，显示 月-日 时:分
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    else:  # 大于1天，显示 月-日
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    
    ax.tick_params(axis='x', rotation=45)
    plt.setp(ax.xaxis.get_majorticklabels(), ha='right')

LABELS = {
    'performance_analysis': 'Performance Analysis',
    'time': 'Time',
    'cpu_usage': 'CPU Usage (%)',
    'memory_usage': 'Memory Usage (%)',
    'disk_usage': 'Disk Usage (%)',
    'network_usage': 'Network Usage (%)',
    'qps': 'QPS',
    'latency': 'Latency (ms)',
    'throughput': 'Throughput',
    'bottleneck_analysis': 'Bottleneck Analysis',
    'trend_analysis': 'Trend Analysis',
    'correlation_analysis': 'Correlation Analysis',
    'performance_summary': 'Performance Summary',
    'device_performance': 'Device Performance',
    'io_latency': 'I/O Latency',
    'utilization': 'Utilization',
    'threshold_analysis': 'Threshold Analysis'
}

class PerformanceVisualizer(CSVDataProcessor):
    """Performance Visualizer - Based on unified CSV data processor"""
    
    def __init__(self, data_file, overhead_file=None):
        super().__init__()  # 初始化CSV数据处理器
        
        self.data_file = data_file
        self.overhead_file = overhead_file or self._find_monitoring_overhead_file() or os.getenv('MONITORING_OVERHEAD_LOG')
        self.output_dir = os.getenv('REPORTS_DIR', os.path.dirname(data_file))
        
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # Using English labels system directly
        self.font_manager = None
        
        self._accounts_thresholds_added = False
        
        # 从环境变量读取阈值配置 - 使用统一框架
        temp_manager = DeviceManager(pd.DataFrame())  # 临时实例获取配置
        thresholds = temp_manager.get_visualization_thresholds()
        self.util_thresholds = {
            'normal': 70,      # Normal Threshold (%)
            'warning': thresholds['warning'],     # Warning Threshold (%)
            'critical': thresholds['critical']    # Critical Threshold (%)
        }
        
        # 初始化新工具
        try:
            self.unit_converter = UnitConverter()
            self.correlation_analyzer = CPUEBSCorrelationAnalyzer(data_file)
            self.chart_generator = AdvancedChartGenerator(data_file, self.output_dir)
        except Exception as e:
            print(f"⚠️ Advanced tools initialization failed: {e}")
            self.unit_converter = None
            self.correlation_analyzer = None
            self.chart_generator = None
    
    def _find_monitoring_overhead_file(self):
        """智能查找监控开销文件 - 与report_generator.py保持一致"""
        try:
            # 多路径搜索策略
            search_dirs = [
                os.path.dirname(self.data_file),  # 与performance CSV同目录
                os.path.join(os.path.dirname(self.data_file), 'logs'),  # logs子目录
                os.getenv('LOGS_DIR', os.path.join(os.path.dirname(self.data_file), 'current', 'logs')),  # 环境变量指定
            ]
            
            for logs_dir in search_dirs:
                if os.path.exists(logs_dir):
                    pattern = os.path.join(logs_dir, 'monitoring_overhead_*.csv')
                    files = glob.glob(pattern)
                    if files:
                        # 返回最新的文件
                        latest_file = max(files, key=os.path.getctime)
                        print(f"✅ Found monitoring overhead file: {os.path.basename(latest_file)}")
                        return latest_file
            
            return None
        except Exception as e:
            print(f"Warning: Failed to find monitoring overhead file: {e}")
            return None

    def load_data(self):
        """加载数据"""
        try:
            success = self.load_csv_data(self.data_file)
            if success:
                self.clean_data()  # 清洗数据
                
                # 安全的Time戳处理
                if 'timestamp' in self.df.columns:
                    try:
                        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
                        print(f"✅ Timestamp field 'self.df['timestamp']' conversion successful")
                    except Exception as e:
                        print(f"⚠️  Timestamp conversion failed: {e}")
                        # 创建默认Time戳
                        self.df['timestamp'] = pd.date_range(start='2024-01-01', periods=len(self.df), freq='1min')
                else:
                    print("⚠️  Timestamp field not found, creating default timestamp")
                    self.df['timestamp'] = pd.date_range(start='2024-01-01', periods=len(self.df), freq='1min')
                
                print(f"✅ Loaded {len(self.df)} performance data records")
                print(f"📊 CSV columns: {len(self.df.columns)}")

            return success
            
        except Exception as e:
            print(f"❌ Data loading failed: {e}")
            return False
    
    def _analyze_threshold_violations(self, data_series, thresholds, metric_name):
        """Threshold violation analysis"""
        if data_series.empty:
            return {
                'total_points': 0,
                'warning_violations': 0,
                'critical_violations': 0,
                'warning_percentage': 0.0,
                'critical_percentage': 0.0,
                'max_value': 0.0,
                'avg_value': 0.0,
                'metric_name': metric_name,
                'error': 'Data is empty'
            }
        
        valid_data = data_series.dropna()
        if len(valid_data) == 0:
            return {
                'total_points': len(data_series),
                'warning_violations': 0,
                'critical_violations': 0,
                'warning_percentage': 0.0,
                'critical_percentage': 0.0,
                'max_value': 0.0,
                'avg_value': 0.0,
                'metric_name': metric_name,
                'error': 'All data is NaN'
            }
        
        total_points = len(valid_data)
        violations = {
            'warning': len(valid_data[valid_data > thresholds['warning']]),
            'critical': len(valid_data[valid_data > thresholds['critical']])
        }
        
        return {
            'total_points': total_points,
            'warning_violations': violations['warning'],
            'critical_violations': violations['critical'],
            'warning_percentage': (violations['warning'] / total_points * 100) if total_points > 0 else 0,
            'critical_percentage': (violations['critical'] / total_points * 100) if total_points > 0 else 0,
            'max_value': valid_data.max(),
            'avg_value': valid_data.mean(),
            'metric_name': metric_name,
            'valid_data_ratio': len(valid_data) / len(data_series) * 100
        }
    
    def create_performance_overview_chart(self):
        """✅ System Performance Overview Chart - Systematic Refactor"""
        
        # 数据检查 - 确保数据已加载
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                return None
        
        # 加载配置
        load_framework_config()
        
        accounts_configured = DeviceManager.is_accounts_configured(self.df)
        
        fig, axes = plt.subplots(2, 2, figsize=(18, 12))
        fig.suptitle('System Performance Overview', fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], fontweight='bold')
        
        # ✅ 修复字段名映射
        cpu_usage_col = 'cpu_usage' if 'cpu_usage' in self.df.columns else None
        cpu_iowait_col = 'cpu_iowait' if 'cpu_iowait' in self.df.columns else None
        mem_usage_col = 'mem_usage' if 'mem_usage' in self.df.columns else None  # 修复字段名
        
        # 查找设备列
        data_iops_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_total_iops')]
        data_throughput_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_total_throughput_mibs')]
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        
        accounts_iops_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_total_iops')] if accounts_configured else []
        accounts_throughput_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_total_throughput_mibs')] if accounts_configured else []
        accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')] if accounts_configured else []
        
        # 1. CPU Performance (Top Left)
        ax1 = axes[0, 0]
        if cpu_usage_col and cpu_iowait_col:
            cpu_usage_data = self.df[cpu_usage_col].dropna()
            cpu_iowait_data = self.df[cpu_iowait_col].dropna()
            
            if len(cpu_usage_data) > 0 and len(cpu_iowait_data) > 0:
                # 先绘制网格线（底层）
                ax1.grid(True, alpha=0.3, zorder=0)
                # 再绘制数据线（上层）
                ax1.plot(self.df['timestamp'], cpu_usage_data, label='CPU Usage', linewidth=2, color='blue', zorder=2)
                ax1.plot(self.df['timestamp'], cpu_iowait_data, label='CPU I/O Wait', linewidth=2, color='red', zorder=2)
                ax1.set_title('CPU Performance')
                ax1.set_ylabel('Usage (%)')
                ax1.legend()
            else:
                ax1.text(0.5, 0.5, 'CPU data not available', ha='center', va='center', transform=ax1.transAxes)
                ax1.set_title('CPU Performance (No Data)')
        else:
            ax1.text(0.5, 0.5, 'CPU data not found', ha='center', va='center', transform=ax1.transAxes)
            ax1.set_title('CPU Performance (No Data)')
        
        # 2. Memory Usage (Top Right)
        ax2 = axes[0, 1]
        if mem_usage_col:
            mem_data = self.df[mem_usage_col].dropna()
            if len(mem_data) > 0:
                ax2.plot(self.df['timestamp'], mem_data, label='Memory Usage', linewidth=2, color='green')
                ax2.set_title('Memory Usage')
                ax2.set_ylabel('Usage (%)')
                ax2.legend()
                ax2.grid(True, alpha=0.3)
            else:
                ax2.text(0.5, 0.5, 'Memory data not available', ha='center', va='center', transform=ax2.transAxes)
                ax2.set_title('Memory Usage (No Data)')
        else:
            ax2.text(0.5, 0.5, 'Memory data not found', ha='center', va='center', transform=ax2.transAxes)
            ax2.set_title('Memory Usage (No Data)')
        
        # 3. EBS IOPS + Throughput (Bottom Left) - iostat原始数据
        ax3 = axes[1, 0]
        if data_iops_cols and data_throughput_cols:
            # 双Y轴显示IOPS和throughput
            ax3_twin = ax3.twinx()
            
            # DATA设备
            ax3.plot(self.df['timestamp'], self.df[data_iops_cols[0]], 
                    label='DATA IOPS (iostat)', linewidth=2, color='blue')
            ax3_twin.plot(self.df['timestamp'], self.df[data_throughput_cols[0]], 
                         label='DATA Throughput (iostat)', linewidth=2, color='lightblue', linestyle='--')
            
            # ACCOUNTS设备
            if accounts_configured and accounts_iops_cols and accounts_throughput_cols:
                ax3.plot(self.df['timestamp'], self.df[accounts_iops_cols[0]], 
                        label='ACCOUNTS IOPS (iostat)', linewidth=2, color='orange')
                ax3_twin.plot(self.df['timestamp'], self.df[accounts_throughput_cols[0]], 
                             label='ACCOUNTS Throughput (iostat)', linewidth=2, color='lightsalmon', linestyle='--')
            
            ax3.set_title('EBS IOPS & Throughput (iostat data)')
            ax3.set_ylabel('IOPS')
            ax3_twin.set_ylabel('Throughput (MiB/s)')
            ax3.legend(loc='upper left')
            ax3_twin.legend(loc='upper right')
            ax3.grid(True, alpha=0.3)
        else:
            ax3.text(0.5, 0.5, 'EBS IOPS/Throughput data not found', ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('EBS IOPS & Throughput (No Data)')
        
        # 4. EBS Utilization (Bottom Right) - iostat原始数据
        ax4 = axes[1, 1]
        if data_util_cols:
            ax4.plot(self.df['timestamp'], self.df[data_util_cols[0]], 
                    label='DATA Utilization (iostat)', linewidth=2, color='blue')
            
            if accounts_configured and accounts_util_cols:
                ax4.plot(self.df['timestamp'], self.df[accounts_util_cols[0]], 
                        label='ACCOUNTS Utilization (iostat)', linewidth=2, color='orange')
            
            ax4.set_title('EBS Utilization (iostat data)')
            ax4.set_ylabel('Utilization (%)')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        else:
            ax4.text(0.5, 0.5, 'EBS Utilization data not found', ha='center', va='center', transform=ax4.transAxes)
            ax4.set_title('EBS Utilization (No Data)')
        
        # Format time axis
        for ax in axes.flat:
            ax.tick_params(axis='x', rotation=45)
        
        UnifiedChartStyle.apply_layout('auto')
        
        output_file = os.path.join(self.output_dir, 'performance_overview.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"📊 Performance Analysis overview saved: {output_file}")
        return output_file

    def create_correlation_visualization_chart(self):
        """CPU-EBS Performance Correlation Analysis - Dual Device Support"""
        
        # Check data availability (与其他方法保持一致)
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                print("❌ Failed to load data for correlation analysis")
                return None
        
        # Device configuration detection
        data_configured = len([col for col in self.df.columns if col.startswith('data_')]) > 0
        accounts_configured = DeviceManager.is_accounts_configured(self.df)
        
        if not data_configured:
            print("❌ DATA device data not found")
            return None
        
        # Dynamic title
        title = 'CPU-EBS Performance Correlation Analysis - DATA & ACCOUNTS Devices' if accounts_configured else 'CPU-EBS Performance Correlation Analysis - DATA Device Only'
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(title, fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], fontweight='bold')
        
        # Get CPU and device fields
        cpu_iowait_col = 'cpu_iowait' if 'cpu_iowait' in self.df.columns else None
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        data_await_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_avg_await')]
        data_aqu_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_aqu_sz')]
        
        # ACCOUNTS device fields
        accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')] if accounts_configured else []
        accounts_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_avg_await')] if accounts_configured else []
        accounts_aqu_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_aqu_sz')] if accounts_configured else []
        
        accounts_util_col = accounts_util_cols[0] if accounts_util_cols else None
        accounts_await_col = accounts_await_cols[0] if accounts_await_cols else None

        # Check field availability
        missing_fields = []
        if not cpu_iowait_col:
            missing_fields.append('cpu_iowait')
        if not data_util_cols:
            missing_fields.append('data_util')
        
        if missing_fields:
            print(f"⚠️  Missing fields for correlation analysis: {', '.join(missing_fields)}")
            # Display error information in chart
            for i, ax in enumerate(axes.flat):
                ax.text(0.5, 0.5, f'Missing required fields:\n{chr(10).join(missing_fields)}', 
                       ha='center', va='center', transform=ax.transAxes, fontsize=12)
                ax.set_title(f'Correlation Analysis {i+1} - Data Unavailable')
            
            output_file = os.path.join(self.output_dir, 'cpu_ebs_correlation_visualization.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            return output_file
        
        # 1. CPU I/O Wait vs DATA Device Utilization
        if cpu_iowait_col and data_util_cols:
            data_util_col = data_util_cols[0]
            axes[0, 0].scatter(self.df[cpu_iowait_col], self.df[data_util_col], 
                             alpha=0.6, s=20, color=UnifiedChartStyle.COLORS['data_primary'], label='DATA Device')
            
            # Add ACCOUNTS device if configured
            if accounts_configured and accounts_util_cols:
                accounts_util_col = accounts_util_cols[0]
                axes[0, 0].scatter(self.df[cpu_iowait_col], self.df[accounts_util_col], 
                                 alpha=0.6, s=20, color=UnifiedChartStyle.COLORS['accounts_primary'], label='ACCOUNTS Device')
            
            # Calculate and display correlation
            data_corr = self.df[cpu_iowait_col].corr(self.df[data_util_col])
            corr_text = f'DATA Correlation: {data_corr:.3f}'
            
            if accounts_configured and accounts_util_cols:
                accounts_corr = self.df[cpu_iowait_col].corr(self.df[accounts_util_col])
                corr_text += f'\nACCOUNTS Correlation: {accounts_corr:.3f}'
            
            axes[0, 0].text(0.05, 0.95, corr_text, transform=axes[0, 0].transAxes, 
                           bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            axes[0, 0].set_xlabel('CPU I/O Wait (%)')
            axes[0, 0].set_ylabel('Device Utilization (%)')
            axes[0, 0].set_title('CPU I/O Wait vs Device Utilization', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)
        
        # 2. CPU I/O Wait vs Device Latency
        if cpu_iowait_col and data_await_cols:
            data_await_col = data_await_cols[0]
            axes[0, 1].scatter(self.df[cpu_iowait_col], self.df[data_await_col], 
                             alpha=0.6, s=20, color='green', label='DATA Device')
            
            # Add ACCOUNTS device if configured
            if accounts_configured and accounts_await_col:
                axes[0, 1].scatter(self.df[cpu_iowait_col], self.df[accounts_await_col], 
                                 alpha=0.6, s=20, color='purple', label='ACCOUNTS Device')
            
            # Calculate correlation
            data_corr = self.df[cpu_iowait_col].corr(self.df[data_await_col])
            corr_text = f'DATA Correlation: {data_corr:.3f}'
            
            if accounts_configured and accounts_await_col:
                accounts_corr = self.df[cpu_iowait_col].corr(self.df[accounts_await_col])
                corr_text += f'\nACCOUNTS Correlation: {accounts_corr:.3f}'
            
            axes[0, 1].text(0.05, 0.95, corr_text, transform=axes[0, 1].transAxes,
                           bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            axes[0, 1].set_xlabel('CPU I/O Wait (%)')
            axes[0, 1].set_ylabel('Average Latency (ms)')
            axes[0, 1].set_title('CPU I/O Wait vs Device Latency', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            axes[0, 1].legend()
            axes[0, 1].grid(True, alpha=0.3)
        
        # 3. Device Utilization vs Queue Depth
        if data_util_cols and data_aqu_cols:
            data_util_col = data_util_cols[0]
            data_aqu_col = data_aqu_cols[0]
            axes[1, 0].scatter(self.df[data_util_col], self.df[data_aqu_col], 
                             alpha=0.6, s=20, color=UnifiedChartStyle.COLORS['data_primary'], label='DATA Device')
            
            # Add ACCOUNTS device if configured
            if accounts_configured and accounts_util_cols and accounts_aqu_cols:
                accounts_util_col = accounts_util_cols[0]
                accounts_aqu_col = accounts_aqu_cols[0]
                axes[1, 0].scatter(self.df[accounts_util_col], self.df[accounts_aqu_col], 
                                 alpha=0.6, s=20, color=UnifiedChartStyle.COLORS['accounts_primary'], label='ACCOUNTS Device')
            
            axes[1, 0].set_xlabel('Device Utilization (%)')
            axes[1, 0].set_ylabel('Queue Depth')
            axes[1, 0].set_title('Device Utilization vs Queue Depth', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            axes[1, 0].legend()
            axes[1, 0].grid(True, alpha=0.3)
        
        # 4. Correlation Summary
        summary_text = "CPU-EBS Correlation Summary:\n\n"
        
        if cpu_iowait_col and data_util_cols:
            data_corr = self.df[cpu_iowait_col].corr(self.df[data_util_cols[0]])
            summary_text += f"DATA Device:\n"
            summary_text += f"  CPU I/O Wait vs Utilization: {data_corr:.3f}\n"
            
            if data_await_cols:
                data_await_corr = self.df[cpu_iowait_col].corr(self.df[data_await_cols[0]])
                summary_text += f"  CPU I/O Wait vs Latency: {data_await_corr:.3f}\n\n"
        
        if accounts_configured and cpu_iowait_col and accounts_util_cols:
            accounts_corr = self.df[cpu_iowait_col].corr(self.df[accounts_util_cols[0]])
            summary_text += f"ACCOUNTS Device:\n"
            summary_text += f"  CPU I/O Wait vs Utilization: {accounts_corr:.3f}\n"
            
            if accounts_await_cols:
                accounts_await_corr = self.df[cpu_iowait_col].corr(self.df[accounts_await_cols[0]])
                summary_text += f"  CPU I/O Wait vs Latency: {accounts_await_corr:.3f}"
        elif not accounts_configured:
            summary_text += "ACCOUNTS Device: Not Configured\n"
            summary_text += "Configure ACCOUNTS_DEVICE for dual-device analysis"
        
        UnifiedChartStyle.add_text_summary(axes[1, 1], summary_text, 'Correlation Summary')
        
        UnifiedChartStyle.apply_layout('auto')
        
        output_file = os.path.join(self.output_dir, 'cpu_ebs_correlation_visualization.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        print(f"✅ CPU-EBS correlation visualization saved: {output_file} ({device_info} devices)")
        
        return output_file

    def create_util_threshold_analysis_chart(self):
        """Device Utilization Threshold Analysis Chart - Systematic Refactor"""
        
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                print("❌ Failed to load data")
                return None, {}
        
        accounts_configured = DeviceManager.is_accounts_configured(self.df)
        title = 'Device Utilization Threshold Analysis - DATA & ACCOUNTS Devices' if accounts_configured else 'Device Utilization Threshold Analysis - DATA Device Only'
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(title, fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], fontweight='bold')
        
        thresholds = get_visualization_thresholds()
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        
        if not data_util_cols:
            print("❌ DATA device utilization data not found")
            return None
        
        data_util_col = data_util_cols[0]
        accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')] if accounts_configured else []
        accounts_util_col = accounts_util_cols[0] if accounts_util_cols else None
        
        # 1. Utilization Time Series
        axes[0, 0].plot(self.df['timestamp'], self.df[data_util_col], 
                       label='DATA Device Utilization', linewidth=2, color=UnifiedChartStyle.COLORS['data_primary'])
        
        if accounts_configured and accounts_util_cols:
            accounts_util_col = accounts_util_cols[0]
            axes[0, 0].plot(self.df['timestamp'], self.df[accounts_util_col], 
                           label='ACCOUNTS Device Utilization', linewidth=2, color=UnifiedChartStyle.COLORS['accounts_primary'])
        
        axes[0, 0].axhline(y=thresholds['warning'], color=UnifiedChartStyle.COLORS['warning'], linestyle='--', alpha=0.7, 
                          label=f'Warning: {thresholds["warning"]}%')
        axes[0, 0].axhline(y=thresholds['critical'], color=UnifiedChartStyle.COLORS['critical'], linestyle='--', alpha=0.7, 
                          label=f'Critical: {thresholds["critical"]}%')
        
        axes[0, 0].set_title('Device Utilization vs Thresholds', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        axes[0, 0].set_ylabel('Utilization (%)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        axes[0, 0].legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
        axes[0, 0].grid(True, alpha=0.3)
        UnifiedChartStyle.format_time_axis(axes[0, 0], self.df['timestamp'])
        
        # 2. Utilization Distribution
        axes[0, 1].hist(self.df[data_util_col], bins=15, alpha=0.8, color=UnifiedChartStyle.COLORS['data_primary'], 
                       label='DATA Device Distribution')
        
        if accounts_configured and accounts_util_cols:
            axes[0, 1].hist(self.df[accounts_util_col], bins=15, alpha=0.6, color=UnifiedChartStyle.COLORS['accounts_primary'], 
                           label='ACCOUNTS Device Distribution')
        
        axes[0, 1].axvline(x=thresholds['warning'], color=UnifiedChartStyle.COLORS['warning'], linestyle='--', alpha=0.8, linewidth=2,
                          label=f'Warning: {thresholds["warning"]}%')
        axes[0, 1].axvline(x=thresholds['critical'], color=UnifiedChartStyle.COLORS['critical'], linestyle='--', alpha=0.8, linewidth=2,
                          label=f'Critical: {thresholds["critical"]}%')
        
        axes[0, 1].set_title('Utilization Distribution', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        axes[0, 1].set_xlabel('Utilization (%)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        axes[0, 1].set_ylabel('Frequency', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        axes[0, 1].legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
        axes[0, 1].grid(True, alpha=0.3)
        
        # 3. Violation Timeline
        violation_data = self.df[data_util_col] > thresholds['critical']
        warning_data = (self.df[data_util_col] > thresholds['warning']) & (self.df[data_util_col] <= thresholds['critical'])
        
        axes[1, 0].plot(self.df['timestamp'], violation_data.astype(int), 
                       label='DATA Critical', linewidth=2, color=UnifiedChartStyle.COLORS['critical'], marker='o', markersize=2)
        axes[1, 0].plot(self.df['timestamp'], warning_data.astype(int) * 0.5, 
                       label='DATA Warning', linewidth=2, color=UnifiedChartStyle.COLORS['warning'], marker='s', markersize=2)
        
        if accounts_configured and accounts_util_cols:
            accounts_violation = self.df[accounts_util_col] > thresholds['critical']
            accounts_warning = (self.df[accounts_util_col] > thresholds['warning']) & (self.df[accounts_util_col] <= thresholds['critical'])
            
            axes[1, 0].plot(self.df['timestamp'], accounts_violation.astype(int) + 0.1, 
                           label='ACCOUNTS Critical', linewidth=2, color=UnifiedChartStyle.COLORS['data_primary'], marker='o', markersize=2)
            axes[1, 0].plot(self.df['timestamp'], accounts_warning.astype(int) * 0.5 + 0.05, 
                           label='ACCOUNTS Warning', linewidth=2, color=UnifiedChartStyle.COLORS['success'], marker='s', markersize=2)
        
        axes[1, 0].set_title('Violation Timeline', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        axes[1, 0].set_ylabel('Violation Status', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        axes[1, 0].legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
        axes[1, 0].grid(True, alpha=0.3)
        axes[1, 0].set_ylim(-0.1, 1.3)
        UnifiedChartStyle.format_time_axis(axes[1, 0], self.df['timestamp'])
        
        # 4. Statistics Summary
        summary_lines = ["Utilization Statistics:", ""]
        summary_lines.extend([
            f"DATA Device:",
            f"  Mean: {self.df[data_util_col].mean():.2f}%",
            f"  Max: {self.df[data_util_col].max():.2f}%",
            f"  Violations: {(self.df[data_util_col] > thresholds['critical']).sum()}",
            ""
        ])
        
        if accounts_configured and accounts_util_cols:
            summary_lines.extend([
                f"ACCOUNTS Device:",
                f"  Mean: {self.df[accounts_util_col].mean():.2f}%",
                f"  Max: {self.df[accounts_util_col].max():.2f}%",
                f"  Violations: {(self.df[accounts_util_col] > thresholds['critical']).sum()}"
            ])
        
        UnifiedChartStyle.add_text_summary(axes[1, 1], "\n".join(summary_lines), "Statistics Summary")
        
        plt.tight_layout()
        
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        output_file = os.path.join(self.output_dir, 'util_threshold_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
        plt.close()
        print(f"✅ Utilization threshold analysis chart saved: {output_file} ({device_info} devices)")
        
        threshold_violations = {}
        if data_util_col:
            threshold_violations['data_util'] = self._analyze_threshold_violations(
                self.df[data_util_col], self.util_thresholds, 'data_util'
            )
        if accounts_configured and accounts_util_col:
            threshold_violations['accounts_util'] = self._analyze_threshold_violations(
                self.df[accounts_util_col], self.util_thresholds, 'accounts_util'
            )
        
        return output_file, threshold_violations

    def create_await_threshold_analysis_chart(self):
        """Enhanced I/O Latency Threshold Analysis Chart"""
        
        # 先加载数据，再检查ACCOUNTS配置
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                print("❌ Failed to load data for await threshold analysis")
                return None

        accounts_configured = DeviceManager.is_accounts_configured(self.df)
        title = 'Enhanced I/O Await Threshold Analysis - DATA & ACCOUNTS Devices' if accounts_configured else 'Enhanced I/O Await Threshold Analysis - DATA Device Only'
        
        fig, axes = plt.subplots(2, 2, figsize=(18, 14))
        fig.suptitle(title, fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], fontweight='bold')
        
        data_await_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_avg_await')]
        
        if not data_await_cols:
            print("❌ DATA device latency data not found")
            return None
        
        data_await_col = data_await_cols[0]
        accounts_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_avg_await')] if accounts_configured else []
        accounts_await_col = accounts_await_cols[0] if accounts_await_cols else None
        
        # 智能阈值设置 - 使用配置变量和统一计算规则
        base_latency_threshold = int(os.getenv('BOTTLENECK_EBS_LATENCY_THRESHOLD', '50'))
        
        # DATA设备阈值 - 使用统一计算规则
        data_thresholds = {
            'excellent': base_latency_threshold * 0.4,    # 40% of base threshold
            'good': base_latency_threshold * 0.6,         # 60% of base threshold
            'warning': base_latency_threshold * 0.8,      # 80% of base threshold (统一规则)
            'poor': base_latency_threshold * 1.0,         # 100% of base threshold
            'critical': base_latency_threshold * 1.2      # 120% of base threshold
        }
        
        # ACCOUNTS设备独立阈值 - 使用相同的配置规则
        accounts_thresholds = data_thresholds  # 默认使用DATA阈值
        if accounts_configured and accounts_await_col:
            # ACCOUNTS设备使用相同的配置阈值规则
            accounts_thresholds = {
                'excellent': base_latency_threshold * 0.4,
                'good': base_latency_threshold * 0.6,
                'warning': base_latency_threshold * 0.8,
                'poor': base_latency_threshold * 1.0,
                'critical': base_latency_threshold * 1.2
            }
        
        # 用于显示的统一阈值（取两者最大值）
        enhanced_thresholds = data_thresholds
        if accounts_configured and accounts_await_col:
            enhanced_thresholds = {
                'excellent': max(data_thresholds['excellent'], accounts_thresholds['excellent']),
                'good': max(data_thresholds['good'], accounts_thresholds['good']),
                'warning': max(data_thresholds['warning'], accounts_thresholds['warning']),
                'poor': max(data_thresholds['poor'], accounts_thresholds['poor']),
                'critical': max(data_thresholds['critical'], accounts_thresholds['critical'])
            }

        # 1. Enhanced Time Series with Multiple Thresholds
        axes[0, 0].plot(self.df['timestamp'], self.df[data_await_col], 
                       label='DATA Device Latency', linewidth=2.5, color=UnifiedChartStyle.COLORS['data_primary'])
        
        if accounts_configured and accounts_await_col:
            axes[0, 0].plot(self.df['timestamp'], self.df[accounts_await_col], 
                           label='ACCOUNTS Device Latency', linewidth=2.5, color=UnifiedChartStyle.COLORS['accounts_primary'])
        
        # Multiple threshold lines with better colors
        axes[0, 0].axhline(y=enhanced_thresholds['excellent'], color=UnifiedChartStyle.COLORS['success'], 
                          linestyle='-', alpha=0.8, linewidth=1, label=f'Excellent (<{enhanced_thresholds["excellent"]:.2f}ms)')
        axes[0, 0].axhline(y=enhanced_thresholds['good'], color='limegreen', 
                          linestyle='--', alpha=0.8, linewidth=1.5, label=f'Good (<{enhanced_thresholds["good"]:.2f}ms)')
        axes[0, 0].axhline(y=enhanced_thresholds['warning'], color=UnifiedChartStyle.COLORS['warning'], 
                          linestyle='--', alpha=0.8, linewidth=2, label=f'Warning (<{enhanced_thresholds["warning"]:.2f}ms)')
        axes[0, 0].axhline(y=enhanced_thresholds['critical'], color=UnifiedChartStyle.COLORS['critical'], 
                          linestyle='--', alpha=0.8, linewidth=2, label=f'Critical (<{enhanced_thresholds["critical"]:.2f}ms)')
        
        axes[0, 0].set_title('I/O Latency Timeline with Performance Thresholds', 
                            fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        axes[0, 0].set_ylabel('Average Latency (ms)')
        axes[0, 0].legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'], loc='upper left')
        axes[0, 0].grid(True, alpha=0.3)
        format_time_axis(axes[0, 0], self.df['timestamp'])
        
        # 2. Enhanced Distribution Analysis
        bins = np.linspace(0, max(enhanced_thresholds['critical'] * 1.2, self.df[data_await_col].max() * 1.1), 25)
        axes[0, 1].hist(self.df[data_await_col], bins=bins, alpha=0.7, color=UnifiedChartStyle.COLORS['data_primary'], 
                       edgecolor='black', linewidth=0.5, label='DATA Distribution')
        
        if accounts_configured and accounts_await_col:
            axes[0, 1].hist(self.df[accounts_await_col], bins=bins, alpha=0.6, color=UnifiedChartStyle.COLORS['accounts_primary'], 
                           edgecolor='black', linewidth=0.5, label='ACCOUNTS Distribution')
        
        # Add threshold lines to histogram with labels
        axes[0, 1].axvline(x=enhanced_thresholds['excellent'], color=UnifiedChartStyle.COLORS['success'], 
                          linestyle='-', alpha=0.8, linewidth=1.5, label=f'Excellent ({enhanced_thresholds["excellent"]:.2f}ms)')
        axes[0, 1].axvline(x=enhanced_thresholds['good'], color='limegreen', 
                          linestyle='--', alpha=0.8, linewidth=1.5, label=f'Good ({enhanced_thresholds["good"]:.2f}ms)')
        axes[0, 1].axvline(x=enhanced_thresholds['warning'], color=UnifiedChartStyle.COLORS['warning'], 
                          linestyle='--', alpha=0.8, linewidth=1.5, label=f'Warning ({enhanced_thresholds["warning"]:.2f}ms)')
        axes[0, 1].axvline(x=enhanced_thresholds['critical'], color=UnifiedChartStyle.COLORS['critical'], 
                          linestyle='--', alpha=0.8, linewidth=1.5, label=f'Critical ({enhanced_thresholds["critical"]:.2f}ms)')
        
        # Add statistics
        data_mean = self.df[data_await_col].mean()
        axes[0, 1].axvline(x=data_mean, color=UnifiedChartStyle.COLORS['data_primary'], 
                          linestyle='-', alpha=0.9, linewidth=2, label=f'DATA Mean: {data_mean:.2f}ms')
        
        if accounts_configured and accounts_await_col:
            accounts_mean = self.df[accounts_await_col].mean()
            axes[0, 1].axvline(x=accounts_mean, color=UnifiedChartStyle.COLORS['accounts_primary'], 
                              linestyle='-', alpha=0.9, linewidth=2, label=f'ACCOUNTS Mean: {accounts_mean:.2f}ms')
        
        axes[0, 1].set_title('Latency Distribution with Performance Bands', 
                            fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        axes[0, 1].set_xlabel('Average Latency (ms)')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
        axes[0, 1].grid(True, alpha=0.3)
        
        # 3. Enhanced Violation Timeline - 使用各自的阈值
        data_violations = {
            'critical': self.df[data_await_col] > data_thresholds['critical'],
            'poor': (self.df[data_await_col] > data_thresholds['poor']) & (self.df[data_await_col] <= data_thresholds['critical']),
            'warning': (self.df[data_await_col] > data_thresholds['warning']) & (self.df[data_await_col] <= data_thresholds['poor'])
        }
        
        # Plot violation timelines with clearly different colors
        axes[1, 0].plot(self.df['timestamp'], data_violations['critical'].astype(int) * 3, 
                       label='DATA Critical', linewidth=3, color=UnifiedChartStyle.COLORS['critical'], marker='o', markersize=4)
        axes[1, 0].plot(self.df['timestamp'], data_violations['poor'].astype(int) * 2, 
                       label='DATA Poor', linewidth=2.5, color='darkorange', marker='s', markersize=3)
        axes[1, 0].plot(self.df['timestamp'], data_violations['warning'].astype(int) * 1, 
                       label='DATA Warning', linewidth=2, color=UnifiedChartStyle.COLORS['warning'], marker='^', markersize=3)
        
        if accounts_configured and accounts_await_col:
            # ACCOUNTS使用自己的阈值
            accounts_violations = {
                'critical': self.df[accounts_await_col] > accounts_thresholds['critical'],
                'poor': (self.df[accounts_await_col] > accounts_thresholds['poor']) & (self.df[accounts_await_col] <= accounts_thresholds['critical']),
                'warning': (self.df[accounts_await_col] > accounts_thresholds['warning']) & (self.df[accounts_await_col] <= accounts_thresholds['poor'])
            }
            
            # ACCOUNTS violations with clearly different colors (紫色系)
            axes[1, 0].plot(self.df['timestamp'], accounts_violations['critical'].astype(int) * 3 + 0.1, 
                           label='ACCOUNTS Critical', linewidth=3, color='purple', marker='o', markersize=4, alpha=0.8)
            axes[1, 0].plot(self.df['timestamp'], accounts_violations['poor'].astype(int) * 2 + 0.1, 
                           label='ACCOUNTS Poor', linewidth=2.5, color='mediumorchid', marker='s', markersize=3, alpha=0.8)
            axes[1, 0].plot(self.df['timestamp'], accounts_violations['warning'].astype(int) * 1 + 0.1, 
                           label='ACCOUNTS Warning', linewidth=2, color='plum', marker='^', markersize=3, alpha=0.8)
        
        axes[1, 0].set_title('Threshold Violation Timeline Analysis', 
                            fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        axes[1, 0].set_xlabel('Time')
        axes[1, 0].set_ylabel('Violation Severity Level')
        axes[1, 0].set_ylim(-0.5, 4)
        axes[1, 0].legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'], ncol=2)
        axes[1, 0].grid(True, alpha=0.3)
        format_time_axis(axes[1, 0], self.df['timestamp'])
        
        # 4. Enhanced Statistics Summary
        # Calculate detailed statistics
        data_stats = {
            'mean': self.df[data_await_col].mean(),
            'p50': self.df[data_await_col].median(),
            'p95': self.df[data_await_col].quantile(0.95),
            'p99': self.df[data_await_col].quantile(0.99),
            'max': self.df[data_await_col].max()
        }
        
        # Calculate violation percentages - 使用DATA自己的阈值
        total_points = len(self.df)
        data_violations_pct = {
            'excellent': (self.df[data_await_col] < data_thresholds['excellent']).sum() / total_points * 100,
            'good': ((self.df[data_await_col] >= data_thresholds['excellent']) & 
                     (self.df[data_await_col] < data_thresholds['good'])).sum() / total_points * 100,
            'warning': ((self.df[data_await_col] >= data_thresholds['good']) & 
                        (self.df[data_await_col] < data_thresholds['warning'])).sum() / total_points * 100,
            'poor': ((self.df[data_await_col] >= data_thresholds['warning']) & 
                     (self.df[data_await_col] < data_thresholds['poor'])).sum() / total_points * 100,
            'critical': (self.df[data_await_col] >= data_thresholds['poor']).sum() / total_points * 100
        }
        
        accounts_violations_pct = {}
        
        summary_text = f"""DATA Device Performance:
  Mean: {data_stats['mean']:.2f}ms  |  P50: {data_stats['p50']:.2f}ms
  P95: {data_stats['p95']:.2f}ms   |  P99: {data_stats['p99']:.2f}ms
  Max: {data_stats['max']:.2f}ms

Performance Distribution (DATA):
  Excellent (<{data_thresholds['excellent']:.2f}ms): {data_violations_pct['excellent']:.1f}%
  Good ({data_thresholds['excellent']:.2f}-{data_thresholds['good']:.2f}ms): {data_violations_pct['good']:.1f}%
  Warning ({data_thresholds['good']:.2f}-{data_thresholds['warning']:.2f}ms): {data_violations_pct['warning']:.1f}%
  Poor ({data_thresholds['warning']:.2f}-{data_thresholds['poor']:.2f}ms): {data_violations_pct['poor']:.1f}%
  Critical (>{data_thresholds['poor']:.2f}ms): {data_violations_pct['critical']:.1f}%"""
        
        if accounts_configured and accounts_await_col:
            accounts_stats = {
                'mean': self.df[accounts_await_col].mean(),
                'p50': self.df[accounts_await_col].median(),
                'p95': self.df[accounts_await_col].quantile(0.95),
                'p99': self.df[accounts_await_col].quantile(0.99),
                'max': self.df[accounts_await_col].max()
            }
            
            # Calculate ACCOUNTS violation percentages - 使用ACCOUNTS自己的阈值
            accounts_violations_pct = {
                'excellent': (self.df[accounts_await_col] < accounts_thresholds['excellent']).sum() / total_points * 100,
                'good': ((self.df[accounts_await_col] >= accounts_thresholds['excellent']) & 
                         (self.df[accounts_await_col] < accounts_thresholds['good'])).sum() / total_points * 100,
                'warning': ((self.df[accounts_await_col] >= accounts_thresholds['good']) & 
                            (self.df[accounts_await_col] < accounts_thresholds['warning'])).sum() / total_points * 100,
                'poor': ((self.df[accounts_await_col] >= accounts_thresholds['warning']) & 
                         (self.df[accounts_await_col] < accounts_thresholds['poor'])).sum() / total_points * 100,
                'critical': (self.df[accounts_await_col] >= accounts_thresholds['poor']).sum() / total_points * 100
            }
            
            summary_text += f"""

ACCOUNTS Device Performance:
  Mean: {accounts_stats['mean']:.2f}ms  |  P50: {accounts_stats['p50']:.2f}ms
  P95: {accounts_stats['p95']:.2f}ms   |  P99: {accounts_stats['p99']:.2f}ms
  Max: {accounts_stats['max']:.2f}ms

Performance Distribution (ACCOUNTS):
  Excellent (<{accounts_thresholds['excellent']:.2f}ms): {accounts_violations_pct['excellent']:.1f}%
  Good ({accounts_thresholds['excellent']:.2f}-{accounts_thresholds['good']:.2f}ms): {accounts_violations_pct['good']:.1f}%
  Warning ({accounts_thresholds['good']:.2f}-{accounts_thresholds['warning']:.2f}ms): {accounts_violations_pct['warning']:.1f}%
  Poor ({accounts_thresholds['warning']:.2f}-{accounts_thresholds['poor']:.2f}ms): {accounts_violations_pct['poor']:.1f}%
  Critical (>{accounts_thresholds['poor']:.2f}ms): {accounts_violations_pct['critical']:.1f}%"""

        summary_text += f"""

Recommendations:
  • Target: Keep 95% of requests under P95 latency
  • Monitor: P99 latency trends for early warning
  • Alert: When performance degrades significantly"""
        
        UnifiedChartStyle.add_text_summary(axes[1, 1], summary_text, 'Performance Analysis Summary')
        
        UnifiedChartStyle.apply_layout('auto')
        output_file = os.path.join(self.output_dir, 'await_threshold_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        print(f"✅ I/O latency threshold analysis chart saved: {output_file} ({device_info} devices)")
        
        threshold_violations = {}
        if data_await_col:
            threshold_violations['data_avg_await'] = self._analyze_threshold_violations(
                self.df[data_await_col], self.await_thresholds, 'data_avg_await'
            )
        if accounts_configured and accounts_await_col:
            threshold_violations['accounts_avg_await'] = self._analyze_threshold_violations(
                self.df[accounts_await_col], self.await_thresholds, 'accounts_avg_await'
            )
        
        return output_file, threshold_violations

    def create_device_comparison_chart(self):
        """Device Performance Comparison Chart - 3x2 Layout"""
        
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                print("❌ Failed to load data for device comparison")
                return None
        
        accounts_configured = DeviceManager.is_accounts_configured(self.df)
        
        if not accounts_configured:
            print("⚠️ ACCOUNTS device not configured, creating DATA-only comparison")
        
        fig, axes = plt.subplots(3, 2, figsize=(16, 18))
        title = 'Device Performance Comparison - DATA & ACCOUNTS' if accounts_configured else 'Device Performance Analysis - DATA Only'
        fig.suptitle(title, fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], 
                    fontweight='bold')
        
        # 动态查找字段
        data_iops_cols = [col for col in self.df.columns if col.startswith('data_') and 'total_iops' in col and 'aws' not in col]
        data_tp_cols = [col for col in self.df.columns if col.startswith('data_') and 'total_throughput_mibs' in col and 'aws' not in col]
        data_aqu_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_aqu_sz')]
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        data_await_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_avg_await')]
        data_r_s_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_r_s')]
        data_w_s_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_w_s')]
        
        accounts_iops_cols = [col for col in self.df.columns if col.startswith('accounts_') and 'total_iops' in col and 'aws' not in col] if accounts_configured else []
        accounts_tp_cols = [col for col in self.df.columns if col.startswith('accounts_') and 'total_throughput_mibs' in col and 'aws' not in col] if accounts_configured else []
        accounts_aqu_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_aqu_sz')] if accounts_configured else []
        accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')] if accounts_configured else []
        accounts_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_avg_await')] if accounts_configured else []
        accounts_r_s_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_r_s')] if accounts_configured else []
        accounts_w_s_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_w_s')] if accounts_configured else []
        
        # 子图1: IOPS & Throughput (双Y轴)
        ax1 = axes[0, 0]
        ax1_twin = ax1.twinx()
        
        if data_iops_cols:
            ax1.plot(self.df['timestamp'], self.df[data_iops_cols[0]], 
                    label='DATA IOPS', linewidth=2, color=UnifiedChartStyle.COLORS['data_primary'])
            if accounts_configured and accounts_iops_cols:
                ax1.plot(self.df['timestamp'], self.df[accounts_iops_cols[0]], 
                        label='ACCOUNTS IOPS', linewidth=2, color=UnifiedChartStyle.COLORS['accounts_primary'])
        
        if data_tp_cols:
            ax1_twin.plot(self.df['timestamp'], self.df[data_tp_cols[0]], 
                         label='DATA Throughput', linewidth=2, linestyle='--', color=UnifiedChartStyle.COLORS['success'])
            if accounts_configured and accounts_tp_cols:
                ax1_twin.plot(self.df['timestamp'], self.df[accounts_tp_cols[0]], 
                             label='ACCOUNTS Throughput', linewidth=2, linestyle='--', color=UnifiedChartStyle.COLORS['critical'])
        
        ax1.set_title('IOPS & Throughput Comparison', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        ax1.set_ylabel('IOPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax1_twin.set_ylabel('Throughput (MiB/s)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax1.legend(loc='upper left', fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
        ax1_twin.legend(loc='upper right', fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
        ax1.grid(True, alpha=0.3)
        format_time_axis(ax1, self.df['timestamp'])
        
        # 子图2: Queue Depth
        ax2 = axes[0, 1]
        if data_aqu_cols:
            ax2.plot(self.df['timestamp'], self.df[data_aqu_cols[0]], 
                    label='DATA Queue Depth', linewidth=2, color=UnifiedChartStyle.COLORS['data_primary'])
            if accounts_configured and accounts_aqu_cols:
                ax2.plot(self.df['timestamp'], self.df[accounts_aqu_cols[0]], 
                        label='ACCOUNTS Queue Depth', linewidth=2, color=UnifiedChartStyle.COLORS['accounts_primary'])
            ax2.axhline(y=2.0, color=UnifiedChartStyle.COLORS['warning'], linestyle='--', alpha=0.7, label='Warning (2.0)')
        
        ax2.set_title('Queue Depth Comparison', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        ax2.set_ylabel('Queue Depth', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax2.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
        ax2.grid(True, alpha=0.3)
        format_time_axis(ax2, self.df['timestamp'])
        
        # 子图3: Utilization
        ax3 = axes[1, 0]
        if data_util_cols:
            ax3.plot(self.df['timestamp'], self.df[data_util_cols[0]], 
                    label='DATA Utilization', linewidth=2, color=UnifiedChartStyle.COLORS['data_primary'])
            if accounts_configured and accounts_util_cols:
                ax3.plot(self.df['timestamp'], self.df[accounts_util_cols[0]], 
                        label='ACCOUNTS Utilization', linewidth=2, color=UnifiedChartStyle.COLORS['accounts_primary'])
            ax3.axhline(y=80, color=UnifiedChartStyle.COLORS['warning'], linestyle='--', alpha=0.7, label='Warning (80%)')
        
        ax3.set_title('Utilization Comparison', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        ax3.set_ylabel('Utilization (%)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax3.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
        ax3.grid(True, alpha=0.3)
        format_time_axis(ax3, self.df['timestamp'])
        
        # 子图4: Latency
        ax4 = axes[1, 1]
        if data_await_cols:
            ax4.plot(self.df['timestamp'], self.df[data_await_cols[0]], 
                    label='DATA Latency', linewidth=2, color=UnifiedChartStyle.COLORS['data_primary'])
            if accounts_configured and accounts_await_cols:
                ax4.plot(self.df['timestamp'], self.df[accounts_await_cols[0]], 
                        label='ACCOUNTS Latency', linewidth=2, color=UnifiedChartStyle.COLORS['accounts_primary'])
            ax4.axhline(y=10, color=UnifiedChartStyle.COLORS['warning'], linestyle='--', alpha=0.7, label='Warning (10ms)')
        
        ax4.set_title('Latency Comparison', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        ax4.set_ylabel('Latency (ms)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax4.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
        ax4.grid(True, alpha=0.3)
        format_time_axis(ax4, self.df['timestamp'])
        
        # 子图5: Read/Write IOPS
        ax5 = axes[2, 0]
        if data_r_s_cols and data_w_s_cols:
            ax5.plot(self.df['timestamp'], self.df[data_r_s_cols[0]], 
                    label='DATA Read', linewidth=2, color=UnifiedChartStyle.COLORS['data_primary'], alpha=0.7)
            ax5.plot(self.df['timestamp'], self.df[data_w_s_cols[0]], 
                    label='DATA Write', linewidth=2, color=UnifiedChartStyle.COLORS['critical'], alpha=0.7)
            if accounts_configured and accounts_r_s_cols and accounts_w_s_cols:
                ax5.plot(self.df['timestamp'], self.df[accounts_r_s_cols[0]], 
                        label='ACCOUNTS Read', linewidth=2, color=UnifiedChartStyle.COLORS['accounts_primary'], alpha=0.7)
                ax5.plot(self.df['timestamp'], self.df[accounts_w_s_cols[0]], 
                        label='ACCOUNTS Write', linewidth=2, color='purple', alpha=0.7)
        
        ax5.set_title('Read/Write IOPS Breakdown', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        ax5.set_ylabel('IOPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
        ax5.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
        ax5.grid(True, alpha=0.3)
        format_time_axis(ax5, self.df['timestamp'])
        
        # 子图6: Summary
        summary_lines = [
            "Device Performance Summary:",
            "(Based on iostat raw data)",
            ""
        ]
        
        if data_iops_cols:
            data_iops_mean = self.df[data_iops_cols[0]].mean()
            summary_lines.append(f"DATA Device:")
            summary_lines.append(f"  Avg IOPS: {data_iops_mean:.0f}")
            if data_util_cols:
                summary_lines.append(f"  Avg Utilization: {self.df[data_util_cols[0]].mean():.1f}%")
            if data_await_cols:
                summary_lines.append(f"  Avg Latency: {self.df[data_await_cols[0]].mean():.2f}ms")
            if data_r_s_cols and data_w_s_cols:
                r_mean = self.df[data_r_s_cols[0]].mean()
                w_mean = self.df[data_w_s_cols[0]].mean()
                ratio = r_mean / w_mean if w_mean > 0 else float('inf')
                summary_lines.append(f"  Read/Write: {ratio:.2f}:1 ({'Read' if ratio > 1 else 'Write'} intensive)")
        
        if accounts_configured and accounts_iops_cols:
            accounts_iops_mean = self.df[accounts_iops_cols[0]].mean()
            summary_lines.extend(["", "ACCOUNTS Device:"])
            summary_lines.append(f"  Avg IOPS: {accounts_iops_mean:.0f}")
            if accounts_util_cols:
                summary_lines.append(f"  Avg Utilization: {self.df[accounts_util_cols[0]].mean():.1f}%")
            if accounts_await_cols:
                summary_lines.append(f"  Avg Latency: {self.df[accounts_await_cols[0]].mean():.2f}ms")
            if accounts_r_s_cols and accounts_w_s_cols:
                r_mean = self.df[accounts_r_s_cols[0]].mean()
                w_mean = self.df[accounts_w_s_cols[0]].mean()
                ratio = r_mean / w_mean if w_mean > 0 else float('inf')
                summary_lines.append(f"  Read/Write: {ratio:.2f}:1 ({'Read' if ratio > 1 else 'Write'} intensive)")
            
            if data_iops_cols:
                data_iops_mean = self.df[data_iops_cols[0]].mean()
                iops_ratio = data_iops_mean / accounts_iops_mean if accounts_iops_mean > 0 else 0
                summary_lines.extend(["", f"IOPS Ratio: {iops_ratio:.1f}:1 (DATA:ACCOUNTS)"])
                summary_lines.append(f"Primary Workload: {'DATA' if iops_ratio > 2 else 'Balanced'}")
        else:
            summary_lines.append("\nACCOUNTS Device: Not Configured")
        
        summary_text = "\n".join(summary_lines)
        UnifiedChartStyle.add_text_summary(axes[2, 1], summary_text, 'Performance Summary')
        
        UnifiedChartStyle.apply_layout('auto')
        
        output_file = os.path.join(self.output_dir, 'device_performance_comparison.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
        plt.close()
        
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        print(f"✅ Device performance comparison chart saved: {output_file} ({device_info} devices)")
        
        return output_file
    def create_monitoring_overhead_analysis_chart(self):
        """Create monitoring overhead analysis chart"""
        if not self.overhead_file or not os.path.exists(self.overhead_file):
            print("⚠️ Monitoring overhead data file does not exist, skipping overhead analysis chart")
            return None, {}
        
        try:
            # Load overhead data
            overhead_df = pd.read_csv(self.overhead_file)
            if 'timestamp' in overhead_df.columns:
                overhead_df['timestamp'] = pd.to_datetime(overhead_df['timestamp'])
            
            # 智能字段映射配置
            field_mapping = {
                'monitoring_cpu': ['monitoring_cpu_percent', 'monitoring_cpu', 'monitor_cpu'],
                'monitoring_memory': ['monitoring_memory_mb', 'monitoring_mem_mb', 'monitor_memory_mb']
            }
            
            # 查找实际字段
            monitoring_cpu_field = None
            monitoring_mem_field = None
            
            for field in field_mapping['monitoring_cpu']:
                if field in overhead_df.columns:
                    monitoring_cpu_field = field
                    break
                    
            for field in field_mapping['monitoring_memory']:
                if field in overhead_df.columns:
                    monitoring_mem_field = field
                    break
            
            # 创建图表 - 使用统一样式
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('Monitoring Overhead Analysis', 
                        fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], fontweight='bold')
            
            # 1. Resource consumption comparison
            ax1 = axes[0, 0]
            ax1.set_title('System Resource Consumption Comparison',
                         fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            
            if monitoring_cpu_field and monitoring_mem_field:
                monitor_cpu = overhead_df[monitoring_cpu_field].mean()
                monitor_mem_raw = overhead_df[monitoring_mem_field].mean()
                
                # 如果是MB单位，转换为百分比
                if 'mb' in monitoring_mem_field.lower():
                    system_memory_gb = overhead_df['system_memory_gb'].mean() if 'system_memory_gb' in overhead_df.columns else 739.70
                    monitor_mem = (monitor_mem_raw / 1024 / system_memory_gb * 100)
                else:
                    monitor_mem = monitor_mem_raw
                
                # 检测 memory 数据是否有效
                mem_data_valid = monitor_mem > 0.001
                
                if mem_data_valid:
                    categories = ['CPU Usage (%)', 'Memory Usage (%)']
                    monitor_values = [monitor_cpu, monitor_mem]
                else:
                    categories = ['CPU Usage (%)']
                    monitor_values = [monitor_cpu]
                    ax1.text(0.7, 0.5, 'Memory data\nunavailable\n(all zeros)', 
                            transform=ax1.transAxes, ha='center', va='center',
                            fontsize=UnifiedChartStyle.FONT_CONFIG['text_size'],
                            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.5))
                
                ax1.bar(categories, monitor_values, alpha=0.8, 
                       color=[UnifiedChartStyle.COLORS['warning'], UnifiedChartStyle.COLORS['info']])
                ax1.set_ylabel('Usage Percentage (%)', 
                              fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax1.tick_params(axis='both', labelsize=UnifiedChartStyle.FONT_CONFIG['text_size'])
                ax1.grid(True, alpha=0.3)
            
            # 2. Monitoring overhead trends
            ax2 = axes[0, 1]
            ax2.set_title('Monitoring Overhead Trends',
                         fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            
            if 'timestamp' in overhead_df.columns and monitoring_cpu_field:
                ax2.plot(overhead_df['timestamp'], overhead_df[monitoring_cpu_field], 
                        label='CPU Overhead', linewidth=2, color=UnifiedChartStyle.COLORS['critical'])
                if monitoring_mem_field and overhead_df[monitoring_mem_field].mean() > 0:
                    ax2.plot(overhead_df['timestamp'], overhead_df[monitoring_mem_field], 
                            label='Memory Overhead', linewidth=2, color=UnifiedChartStyle.COLORS['warning'])
                else:
                    ax2.text(0.7, 0.9, 'Memory: N/A', transform=ax2.transAxes,
                            fontsize=UnifiedChartStyle.FONT_CONFIG['text_size'],
                            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.5))
                ax2.set_ylabel('Overhead (%)', 
                              fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax2.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
                ax2.tick_params(axis='both', labelsize=UnifiedChartStyle.FONT_CONFIG['text_size'])
                ax2.grid(True, alpha=0.3)
            
            # 3. Impact analysis - 移到左下角
            ax3 = axes[1, 0]
            ax3.set_title('Impact Analysis',
                         fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            
            if monitoring_cpu_field and monitoring_mem_field:
                cpu_impact = overhead_df[monitoring_cpu_field].mean()
                mem_impact = overhead_df[monitoring_mem_field].mean()
                
                if mem_impact > 0:
                    impact_categories = ['CPU Impact', 'Memory Impact']
                    impact_values = [cpu_impact, mem_impact]
                else:
                    impact_categories = ['CPU Impact']
                    impact_values = [cpu_impact]
                    ax3.text(0.7, 0.5, 'Memory\nN/A', transform=ax3.transAxes,
                            ha='center', va='center',
                            fontsize=UnifiedChartStyle.FONT_CONFIG['text_size'],
                            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.5))
                
                colors = [UnifiedChartStyle.COLORS['critical'] if x > 10 else UnifiedChartStyle.COLORS['warning'] if x > 5 else UnifiedChartStyle.COLORS['success'] for x in impact_values]
                ax3.bar(impact_categories, impact_values, color=colors, alpha=0.7)
                ax3.set_ylabel('Impact Percentage (%)', 
                              fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax3.tick_params(axis='both', labelsize=UnifiedChartStyle.FONT_CONFIG['text_size'])
                ax3.grid(True, alpha=0.3)
            
            # 4. Statistics summary - 修复：移到右下角，使用统一样式
            if monitoring_cpu_field and monitoring_mem_field:
                summary_text = f"""Monitoring Overhead Summary:

• CPU Overhead:
  - Average: {overhead_df[monitoring_cpu_field].mean():.2f}%
  - Maximum: {overhead_df[monitoring_cpu_field].max():.2f}%

• Memory Overhead:
  - Average: {overhead_df[monitoring_mem_field].mean():.2f}%
  - Maximum: {overhead_df[monitoring_mem_field].max():.2f}%

Data Points: {len(overhead_df)}"""
                
                UnifiedChartStyle.add_text_summary(axes[1, 1], summary_text, 'Overhead Analysis Summary')
            
            UnifiedChartStyle.apply_layout('auto')
            output_file = os.path.join(self.output_dir, 'monitoring_overhead_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"📊 Monitoring overhead analysis chart saved: {output_file}")
            
            # Return analysis results
            overhead_analysis = {}
            if monitoring_cpu_field and monitoring_mem_field:
                overhead_analysis = {
                    'avg_cpu_overhead': overhead_df[monitoring_cpu_field].mean(),
                    'max_cpu_overhead': overhead_df[monitoring_cpu_field].max(),
                    'avg_mem_overhead': overhead_df[monitoring_mem_field].mean(),
                    'max_mem_overhead': overhead_df[monitoring_mem_field].max(),
                    'total_data_points': len(overhead_df)
                }
            
            return output_file, overhead_analysis
            
        except Exception as e:
            print(f"❌ Monitoring overhead chart generation failed: {e}")
            return None, {}

    def generate_all_charts(self):
        print("🎨 Generating performance visualization charts...")
        
        # 设置全局图表样式
        plt.rcParams.update({
            'font.size': 10,
            'axes.titlesize': 12,
            'axes.labelsize': 10,
            'xtick.labelsize': 9,
            'ytick.labelsize': 9,
            'legend.fontsize': 9,
            'figure.titlesize': 14,
            'font.family': 'DejaVu Sans'  # 确保跨平台字体兼容性
        })
        
        if not self.load_data():
            return []
        
        chart_files = []
        threshold_analysis_results = {}
        
        try:
            # Use advanced chart generator
            if self.chart_generator is not None:
                print("🎨 Using advanced chart generator...")
                advanced_charts = self.chart_generator.generate_all_charts()
                if advanced_charts:
                    chart_files.extend(advanced_charts)
            
            # Generate EBS professional analysis charts (high priority)
            print("📊 Generating EBS professional analysis charts...")
            ebs_charts = self.generate_all_ebs_charts()
            if ebs_charts:
                chart_files.extend(ebs_charts)
                print(f"✅ Generated {len(ebs_charts)} EBS professional charts")
            
            # Generate blockchain node analysis charts
            print("Generating blockchain node analysis charts...")
            block_sync_chart = self.create_block_height_sync_chart()
            if block_sync_chart:
                chart_files.append(block_sync_chart)
                print("✅ Block height sync chart generated")
            
            # Generate traditional charts as supplement
            overview_chart = self.create_performance_overview_chart()
            if overview_chart:
                chart_files.append(overview_chart)
                
            correlation_chart = self.create_correlation_visualization_chart()
            if correlation_chart:
                chart_files.append(correlation_chart)
                
            comparison_chart = self.create_device_comparison_chart()
            if comparison_chart:
                chart_files.append(comparison_chart)
            
            # New: Moving average trend charts
            smoothed_chart = self.create_smoothed_trend_chart()
            if smoothed_chart:
                chart_files.append(smoothed_chart)
            
            # Generate threshold analysis charts - integrated from await_util_analyzer
            print("📊 Generating threshold analysis charts...")
            
            await_chart, await_violations = self.create_await_threshold_analysis_chart()
            if await_chart:
                chart_files.append(await_chart)
                threshold_analysis_results['await_violations'] = await_violations
            
            # Generate QPS trend analysis charts
            print("📊 Generating QPS trend analysis charts...")
            qps_trend_chart = self.create_qps_trend_analysis_chart()
            if qps_trend_chart:
                chart_files.append(qps_trend_chart)
            
            # Generate resource efficiency analysis charts
            print("📊 Generating resource efficiency analysis charts...")
            efficiency_chart = self.create_resource_efficiency_analysis_chart()
            if efficiency_chart:
                chart_files.append(efficiency_chart)
            
            # Generate bottleneck identification analysis charts
            print("📊 Generating bottleneck identification analysis charts...")
            bottleneck_chart = self.create_bottleneck_identification_chart()
            if bottleneck_chart:
                chart_files.append(bottleneck_chart)
            
            util_chart, util_violations = self.create_util_threshold_analysis_chart()
            if util_chart:
                chart_files.append(util_chart)
                threshold_analysis_results['util_violations'] = util_violations
            
            # Generate monitoring overhead analysis charts
            print("📊 Generating monitoring overhead analysis charts...")
            
            overhead_chart, overhead_analysis = self.create_monitoring_overhead_analysis_chart()
            if overhead_chart:
                chart_files.append(overhead_chart)
                threshold_analysis_results['overhead_analysis'] = overhead_analysis
            
            # Print threshold analysis summary
            self._print_threshold_analysis_summary(threshold_analysis_results)
            
            print(f"✅ Generated {len(chart_files)} charts")
            return chart_files, threshold_analysis_results
            
        except Exception as e:
            print(f"❌ Chart generation failed: {e}")
            import traceback
            traceback.print_exc()
            return [], {}
    
    def _print_threshold_analysis_summary(self, results):
        """Print threshold analysis summary - integrated from await_util_analyzer"""
        print("\n📊 Threshold Analysis Summary:")
        print("=" * 60)
        
        if 'await_violations' in results:
            print("\n🕐 I/O Latency Threshold Analysis:")
            for device, violations in results['await_violations'].items():
                print(f"  {device}:")
                print(f"    Average: {violations['avg_value']:.2f}ms")
                print(f"    Maximum: {violations['max_value']:.2f}ms")
                print(f"    Warning violations: {violations['warning_violations']}/{violations['total_points']} ({violations['warning_percentage']:.1f}%)")
                print(f"    Critical violations: {violations['critical_violations']}/{violations['total_points']} ({violations['critical_percentage']:.1f}%)")
        
        if 'util_violations' in results:
            print("\n📈 Device iostat %util Threshold Analysis:")
            for device, violations in results['util_violations'].items():
                print(f"  {device} (iostat %util):")
                print(f"    Average: {violations['avg_value']:.1f}%")
                print(f"    Maximum: {violations['max_value']:.1f}%")
                print(f"    Warning violations: {violations['warning_violations']}/{violations['total_points']} ({violations['warning_percentage']:.1f}%)")
                print(f"    Critical violations: {violations['critical_violations']}/{violations['total_points']} ({violations['critical_percentage']:.1f}%)")
        
        # New: Detailed monitoring overhead analysis summary
        if 'overhead_analysis' in results:
            print("\n💻 Monitoring Overhead Detailed Analysis:")
            overhead = results['overhead_analysis']
            print(f"  CPU Overhead:")
            print(f"    Average Overhead: {overhead.get('avg_cpu_overhead', 0):.2f}%")
            print(f"    Peak Overhead: {overhead.get('max_cpu_overhead', 0):.2f}%")
            print(f"  Memory Overhead:")
            print(f"    Average Overhead: {overhead.get('avg_mem_overhead', 0):.2f}%")
            print(f"    Peak Overhead: {overhead.get('max_mem_overhead', 0):.2f}%")
            print(f"  Monitoring efficiency:")
            print(f"    Data Points: {overhead.get('total_data_points', 0)}")
            
            # Calculate resource efficiency ratio
            if self.df is not None and len(self.df) > 0:
                if 'cpu_usage' in self.df.columns:
                    total_cpu = self.df['cpu_usage'].mean()
                    overhead_cpu = overhead.get('avg_cpu_overhead', 0)
                    if total_cpu > 0:
                        cpu_efficiency = (1 - overhead_cpu / total_cpu) * 100
                        print(f"    CPU efficiency: {cpu_efficiency:.1f}% (actual node usage)")
                
                if 'mem_usage' in self.df.columns:
                    total_mem = self.df['mem_usage'].mean()
                    overhead_mem = overhead.get('avg_mem_overhead', 0)
                    if total_mem > 0:
                        mem_efficiency = (1 - overhead_mem / total_mem) * 100
                        print(f"    Memory efficiency: {mem_efficiency:.1f}% (actual node usage)")
        
        print("=" * 60)

    def create_smoothed_trend_chart(self):
        """
        Generate moving average smoothed trend charts
        Display comparison between original data and smoothed trend lines
        """
        print("📈 Generating moving average trend charts...")
        
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                print("❌ Failed to load data")
                return None
        
        try:
            fig, axes = plt.subplots(2, 2, figsize=(18, 12))
            fig.suptitle('Performance Metrics Moving Average Trend Analysis', fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], fontweight='bold')
            
            # Moving average window size
            window_size = min(10, len(self.df) // 10)
            if window_size < 3:
                window_size = 3
            
            # 1. CPU Usage trends
            ax1 = axes[0, 0]
            ax1.plot(self.df['timestamp'], self.df['cpu_usage'], 
                    color=UnifiedChartStyle.COLORS['data_primary'], linewidth=1, alpha=0.3, label='CPU Usage (Raw)')
            
            cpu_smooth = self.df['cpu_usage'].rolling(window=window_size, center=True).mean()
            ax1.plot(self.df['timestamp'], cpu_smooth, 
                    color=UnifiedChartStyle.COLORS['data_primary'], linewidth=2, label=f'CPU Usage({window_size}-point smoothed)')
            
            ax1.set_title('CPU Usage Trends', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            ax1.set_ylabel('Usage (%)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax1.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
            ax1.grid(True, alpha=0.3)
            UnifiedChartStyle.format_time_axis(ax1, self.df['timestamp'])
            
            # 2. Memory Usage trends
            ax2 = axes[0, 1]
            ax2.plot(self.df['timestamp'], self.df['mem_usage'], 
                    color=UnifiedChartStyle.COLORS['critical'], linewidth=1, alpha=0.3, label='Memory Usage (Raw)')
            
            mem_smooth = self.df['mem_usage'].rolling(window=window_size, center=True).mean()
            ax2.plot(self.df['timestamp'], mem_smooth, 
                    color=UnifiedChartStyle.COLORS['critical'], linewidth=2, label=f'Memory Usage({window_size}-point smoothed)')
            
            ax2.set_title('Memory Usage Trends', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            ax2.set_ylabel('Usage (%)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax2.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
            ax2.grid(True, alpha=0.3)
            UnifiedChartStyle.format_time_axis(ax2, self.df['timestamp'])
            
            # 3. EBS Latency trends
            ax3 = axes[1, 0]
            
            data_await_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_avg_await')]
            accounts_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_avg_await')]
            
            if data_await_cols:
                data_await_col = data_await_cols[0]
                await_smooth = self.df[data_await_col].rolling(window=window_size, center=True).mean()
                ax3.plot(self.df['timestamp'], await_smooth, 
                        color=UnifiedChartStyle.COLORS['data_primary'], linewidth=2, label=f'DATA EBS Latency ({window_size}-point avg)')
                
                accounts_configured = DeviceManager.is_accounts_configured(self.df)
                if accounts_configured and accounts_await_cols:
                    accounts_await_col = accounts_await_cols[0]
                    accounts_await_smooth = self.df[accounts_await_col].rolling(window=window_size, center=True).mean()
                    ax3.plot(self.df['timestamp'], accounts_await_smooth,
                            color=UnifiedChartStyle.COLORS['accounts_primary'], linewidth=2, label=f'ACCOUNTS EBS Latency ({window_size}-point avg)')
                
                ax3.set_title('EBS Latency Trends (Smoothed)', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
                ax3.set_ylabel('Latency (ms)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax3.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
                ax3.grid(True, alpha=0.3)
                UnifiedChartStyle.format_time_axis(ax3, self.df['timestamp'])
            else:
                ax3.text(0.5, 0.5, 'EBS Latency data not found', ha='center', va='center', transform=ax3.transAxes,
                        fontsize=UnifiedChartStyle.FONT_CONFIG['text_size'])
                ax3.set_title('EBS Latency Trends (No Data)', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            
            # 4. Network bandwidth trends
            if 'net_rx_mbps' in self.df.columns:
                ax4 = axes[1, 1]
                ax4.plot(self.df['timestamp'], self.df['net_rx_mbps'], 
                        color=UnifiedChartStyle.COLORS['warning'], linewidth=1, alpha=0.3, label='Network RX (Raw)')
                
                net_smooth = self.df['net_rx_mbps'].rolling(window=window_size, center=True).mean()
                ax4.plot(self.df['timestamp'], net_smooth, 
                        color=UnifiedChartStyle.COLORS['warning'], linewidth=2, label=f'Network RX({window_size}-point smoothed)')
                
                ax4.set_title('Network Bandwidth Trends', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
                ax4.set_ylabel('Bandwidth (Mbps)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax4.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
                ax4.grid(True, alpha=0.3)
                UnifiedChartStyle.format_time_axis(ax4, self.df['timestamp'])
            else:
                axes[1, 1].text(0.5, 0.5, 'Network bandwidth data not found', ha='center', va='center', transform=axes[1, 1].transAxes,
                               fontsize=UnifiedChartStyle.FONT_CONFIG['text_size'])
                axes[1, 1].set_title('Network Bandwidth Trends (No Data)', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            
            plt.tight_layout()
            
            # Save chart
            output_file = os.path.join(self.output_dir, 'smoothed_trend_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
            plt.close()
            
            print(f"  ✅ Moving average trend chart: {os.path.basename(output_file)}")
            return output_file
            
        except Exception as e:
            print(f"❌ Moving average trend chart generation failed: {e}")
            return None

    def create_qps_trend_analysis_chart(self):
        """QPS trend analysis chart"""
        print("📊 Generating QPS trend analysis charts...")
        
        # 检查数据是否已加载
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                print("❌ Failed to load data for QPS analysis")
                return None
        
        try:
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('QPS Performance Trend Analysis', fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], fontweight='bold')
            
            # 查找数值型QPS字段
            qps_cols = []
            for col in self.df.columns:
                if 'qps' in col.lower():
                    try:
                        numeric_data = pd.to_numeric(self.df[col], errors='coerce')
                        if not numeric_data.isna().all():
                            qps_cols.append(col)
                    except (ValueError, TypeError, AttributeError):
                        continue
            
            if not qps_cols:
                print("⚠️  No numeric QPS fields found")
                plt.close()
                return None
            
            # 1. QPS时间序列
            ax1 = axes[0, 0]
            for qps_col in qps_cols[:3]:
                qps_data = pd.to_numeric(self.df[qps_col], errors='coerce')
                valid_mask = ~qps_data.isna()
                if valid_mask.any():
                    ax1.plot(self.df.loc[valid_mask, 'timestamp'], 
                            qps_data[valid_mask], 
                            label=qps_col, linewidth=2)
            ax1.set_title('QPS Time Series', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            ax1.set_ylabel('QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax1.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
            ax1.grid(True, alpha=0.3)
            
            # 2. QPS分布直方图
            ax2 = axes[0, 1]
            for qps_col in qps_cols[:2]:
                qps_data = pd.to_numeric(self.df[qps_col], errors='coerce')
                qps_data = qps_data.dropna()
                if len(qps_data) > 0:
                    qps_data = qps_data.astype(float)
                    ax2.hist(qps_data, alpha=0.7, label=qps_col, bins=20)
            ax2.set_title('QPS Distribution', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            ax2.set_xlabel('QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax2.set_ylabel('Frequency', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax2.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
            
            # 3. QPS与CPU相关性
            ax3 = axes[1, 0]
            if 'cpu_usage' in self.df.columns and qps_cols:
                qps_data = pd.to_numeric(self.df[qps_cols[0]], errors='coerce')
                cpu_data = pd.to_numeric(self.df['cpu_usage'], errors='coerce')
                
                valid_mask = ~(qps_data.isna() | cpu_data.isna())
                if valid_mask.any():
                    ax3.scatter(cpu_data[valid_mask], qps_data[valid_mask], alpha=0.6, color=UnifiedChartStyle.COLORS['data_primary'])
                    ax3.set_title('QPS vs CPU Usage', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
                    ax3.set_xlabel('CPU Usage (%)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                    ax3.set_ylabel('QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                    ax3.grid(True, alpha=0.3)
            
            # 4. QPS统计摘要
            ax4 = axes[1, 1]
            stats_lines = ["QPS Statistics Summary:", ""]
            for qps_col in qps_cols[:3]:
                qps_data = pd.to_numeric(self.df[qps_col], errors='coerce').dropna()
                if len(qps_data) > 0:
                    stats_lines.extend([
                        f"{qps_col}:",
                        f"  Average: {qps_data.mean():.2f}",
                        f"  Maximum: {qps_data.max():.2f}",
                        f"  Minimum: {qps_data.min():.2f}",
                        f"  Valid samples: {len(qps_data)}",
                        ""
                    ])
            
            if 'qps_data_available' in self.df.columns:
                qps_available = self.df['qps_data_available']
                if qps_available.notna().any():
                    bool_series = pd.to_numeric(qps_available, errors='coerce').fillna(0).astype(bool)
                    true_count = bool_series.sum()
                else:
                    true_count = 0
                total_count = len(qps_available)
                stats_lines.extend([
                    "QPS Data Availability:",
                    f"  Available: {true_count}/{total_count} ({true_count/total_count*100:.1f}%)"
                ])
            
            UnifiedChartStyle.add_text_summary(ax4, "\n".join(stats_lines), "QPS Summary")
            
            plt.tight_layout()
            
            # Save chart
            output_file = os.path.join(self.output_dir, 'qps_trend_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
            plt.close()
            
            print(f"  ✅ QPS trend analysis chart: {os.path.basename(output_file)}")
            return output_file, {}
            
        except Exception as e:
            print(f"❌ QPS trend analysis chart generation failed: {e}")
            return None

    def create_resource_efficiency_analysis_chart(self):
        """Resource efficiency analysis chart - 参考重构框架实现"""
        print("📊 Generating resource efficiency analysis charts...")
        
        # 检查数据是否已加载
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                print("❌ Failed to load data for resource efficiency analysis")
                return None
        
        try:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('Resource Efficiency Analysis', fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], fontweight='bold')
            
            # 1. CPU Efficiency (QPS per CPU%)
            if 'current_qps' in self.df.columns and 'cpu_usage' in self.df.columns:
                cpu_efficiency = self.df['current_qps'] / (self.df['cpu_usage'] + 0.1)  # 避免除零
                ax1.plot(self.df['timestamp'], cpu_efficiency, color=UnifiedChartStyle.COLORS['data_primary'], linewidth=2)
                ax1.set_title('CPU Efficiency (QPS per CPU%)', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
                ax1.set_ylabel('QPS/CPU%', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax1.grid(True, alpha=0.3)
                UnifiedChartStyle.format_time_axis(ax1, self.df['timestamp'])
            
            # 2. Memory Efficiency (QPS per Memory%)
            if 'current_qps' in self.df.columns and 'mem_usage' in self.df.columns:
                mem_efficiency = self.df['current_qps'] / (self.df['mem_usage'] + 0.1)
                ax2.plot(self.df['timestamp'], mem_efficiency, color=UnifiedChartStyle.COLORS['success'], linewidth=2)
                ax2.set_title('Memory Efficiency (QPS per Memory%)', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
                ax2.set_ylabel('QPS/Memory%', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax2.grid(True, alpha=0.3)
                UnifiedChartStyle.format_time_axis(ax2, self.df['timestamp'])
            
            # 3. IOPS & Throughput Efficiency - 区分 DATA 和 ACCOUNTS 设备
            if 'current_qps' in self.df.columns:
                accounts_configured = DeviceManager.is_accounts_configured(self.df)
                
                # DATA 设备 IOPS
                data_iops_cols = [col for col in self.df.columns if col.startswith('data_') and 'total_iops' in col]
                if data_iops_cols:
                    data_iops = self.df[data_iops_cols[0]]
                    data_iops_efficiency = self.df['current_qps'] / (data_iops + 1)
                    ax3.plot(self.df['timestamp'], data_iops_efficiency, 
                            color=UnifiedChartStyle.COLORS['data_primary'], linewidth=2, label='DATA IOPS Efficiency')
                
                # ACCOUNTS 设备 IOPS
                if accounts_configured:
                    accounts_iops_cols = [col for col in self.df.columns if col.startswith('accounts_') and 'total_iops' in col]
                    if accounts_iops_cols:
                        accounts_iops = self.df[accounts_iops_cols[0]]
                        accounts_iops_efficiency = self.df['current_qps'] / (accounts_iops + 1)
                        ax3.plot(self.df['timestamp'], accounts_iops_efficiency, 
                                color=UnifiedChartStyle.COLORS['accounts_primary'], linewidth=2, label='ACCOUNTS IOPS Efficiency')
                
                ax3.set_title('IOPS & Throughput Efficiency (QPS per IOPS/Throughput)', 
                             fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
                ax3.set_xlabel('Time', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax3.set_ylabel('QPS/IOPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax3.legend(loc='upper left', fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
                ax3.grid(True, alpha=0.3)
                UnifiedChartStyle.format_time_axis(ax3, self.df['timestamp'])
                
                # 添加右侧 Y 轴显示 Throughput Efficiency
                ax3_right = ax3.twinx()
                
                # DATA 设备 Throughput
                data_throughput_cols = [col for col in self.df.columns if col.startswith('data_') and 'total_throughput' in col]
                if data_throughput_cols:
                    data_throughput = self.df[data_throughput_cols[0]]
                    data_throughput_efficiency = self.df['current_qps'] / (data_throughput + 0.1)
                    ax3_right.plot(self.df['timestamp'], data_throughput_efficiency, 
                                  color=UnifiedChartStyle.COLORS['data_primary'], linewidth=2, 
                                  linestyle='--', alpha=0.7, label='DATA Throughput Eff')
                
                # ACCOUNTS 设备 Throughput
                if accounts_configured:
                    accounts_throughput_cols = [col for col in self.df.columns if col.startswith('accounts_') and 'total_throughput' in col]
                    if accounts_throughput_cols:
                        accounts_throughput = self.df[accounts_throughput_cols[0]]
                        accounts_throughput_efficiency = self.df['current_qps'] / (accounts_throughput + 0.1)
                        ax3_right.plot(self.df['timestamp'], accounts_throughput_efficiency, 
                                      color=UnifiedChartStyle.COLORS['accounts_primary'], linewidth=2, 
                                      linestyle='--', alpha=0.7, label='ACCOUNTS Throughput Eff')
                
                ax3_right.set_ylabel('QPS/Throughput(MiB/s)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax3_right.legend(loc='upper right', fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
            
            # 4. Efficiency Summary
            summary_lines = ["Resource Efficiency Analysis:", ""]
            
            if 'current_qps' in self.df.columns and 'cpu_usage' in self.df.columns:
                cpu_eff = (self.df['current_qps'] / (self.df['cpu_usage'] + 0.1)).mean()
                summary_lines.append(f"CPU Efficiency:")
                summary_lines.append(f"  Avg: {cpu_eff:.1f} QPS/CPU%")
                summary_lines.append("")
            
            if 'current_qps' in self.df.columns and 'mem_usage' in self.df.columns:
                mem_eff = (self.df['current_qps'] / (self.df['mem_usage'] + 0.1)).mean()
                summary_lines.append(f"Memory Efficiency:")
                summary_lines.append(f"  Avg: {mem_eff:.1f} QPS/Memory%")
                summary_lines.append("")
            
            if 'current_qps' in self.df.columns:
                accounts_configured = DeviceManager.is_accounts_configured(self.df)
                
                # DATA 设备效率
                data_iops_cols = [col for col in self.df.columns if col.startswith('data_') and 'total_iops' in col]
                if data_iops_cols:
                    data_iops = self.df[data_iops_cols[0]]
                    data_iops_eff = (self.df['current_qps'] / (data_iops + 1)).mean()
                    summary_lines.append(f"DATA IOPS Efficiency:")
                    summary_lines.append(f"  Avg: {data_iops_eff:.3f} QPS/IOPS")
                
                data_throughput_cols = [col for col in self.df.columns if col.startswith('data_') and 'total_throughput' in col]
                if data_throughput_cols:
                    data_throughput = self.df[data_throughput_cols[0]]
                    data_throughput_eff = (self.df['current_qps'] / (data_throughput + 0.1)).mean()
                    summary_lines.append(f"  Throughput: {data_throughput_eff:.3f} QPS/MiB/s")
                    summary_lines.append("")
                
                # ACCOUNTS 设备效率
                if accounts_configured:
                    accounts_iops_cols = [col for col in self.df.columns if col.startswith('accounts_') and 'total_iops' in col]
                    if accounts_iops_cols:
                        accounts_iops = self.df[accounts_iops_cols[0]]
                        accounts_iops_eff = (self.df['current_qps'] / (accounts_iops + 1)).mean()
                        summary_lines.append(f"ACCOUNTS IOPS Efficiency:")
                        summary_lines.append(f"  Avg: {accounts_iops_eff:.3f} QPS/IOPS")
                    
                    accounts_throughput_cols = [col for col in self.df.columns if col.startswith('accounts_') and 'total_throughput' in col]
                    if accounts_throughput_cols:
                        accounts_throughput = self.df[accounts_throughput_cols[0]]
                        accounts_throughput_eff = (self.df['current_qps'] / (accounts_throughput + 0.1)).mean()
                        summary_lines.append(f"  Throughput: {accounts_throughput_eff:.3f} QPS/MiB/s")
                        summary_lines.append("")
            
            summary_lines.append("Efficiency Assessment:")
            if 'current_qps' in self.df.columns and 'cpu_usage' in self.df.columns:
                avg_qps = self.df['current_qps'].mean()
                avg_cpu = self.df['cpu_usage'].mean()
                if avg_cpu > 0:
                    overall_eff = avg_qps / avg_cpu
                    if overall_eff > 100:
                        summary_lines.append("HIGH: Excellent efficiency")
                    elif overall_eff > 50:
                        summary_lines.append("GOOD: Good efficiency")
                    elif overall_eff > 20:
                        summary_lines.append("MODERATE: Average efficiency")
                    else:
                        summary_lines.append("LOW: Poor efficiency")
            
            summary_lines.append("")
            summary_lines.append("Note on IOPS/Throughput Efficiency:")
            summary_lines.append("- Higher = More QPS per IOPS/MiB/s")
            summary_lines.append("- Spikes = Low IOPS/Throughput usage")
            summary_lines.append("- See EBS charts for detailed analysis")
            
            UnifiedChartStyle.add_text_summary(ax4, "\n".join(summary_lines), "Efficiency Summary")
            
            plt.tight_layout()
            output_file = os.path.join(self.output_dir, 'resource_efficiency_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
            plt.close()
            
            print(f"  ✅ Resource efficiency analysis chart: {os.path.basename(output_file)}")
            return output_file
            
        except Exception as e:
            print(f"❌ Resource efficiency analysis chart generation failed: {e}")
            return None
    
    def create_performance_cliff_analysis_chart(self):
        """Performance Cliff Analysis Chart"""
        print("📊 Generating performance cliff analysis chart...")
        
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                print("❌ Failed to load data for cliff analysis")
                return None
        
        try:
            if 'current_qps' not in self.df.columns or 'rpc_latency_ms' not in self.df.columns:
                print("⚠️ QPS or latency data not found")
                return None
            
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('Performance Cliff Analysis', fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], fontweight='bold')
            
            qps_data = self.df['current_qps']
            latency_data = self.df['rpc_latency_ms']
            
            # 1. QPS vs Latency scatter plot
            ax1.scatter(qps_data, latency_data, alpha=0.6, color=UnifiedChartStyle.COLORS['data_primary'])
            ax1.set_title('QPS vs Latency - Cliff Detection', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            ax1.set_xlabel('QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax1.set_ylabel('Latency (ms)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax1.grid(True, alpha=0.3)
            
            # 2. CPU Usage vs QPS
            if 'cpu_usage' in self.df.columns:
                cpu_data = self.df['cpu_usage']
                thresholds = get_visualization_thresholds()
                ax2.plot(qps_data, cpu_data, 'o-', alpha=0.7, color=UnifiedChartStyle.COLORS['success'])
                ax2.axhline(y=thresholds['warning'], color=UnifiedChartStyle.COLORS['critical'], linestyle='--', alpha=0.7, 
                           label=f'Warning ({thresholds["warning"]}%)')
                ax2.set_title('CPU Usage vs QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
                ax2.set_xlabel('QPS', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax2.set_ylabel('CPU Usage (%)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
                ax2.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
                ax2.grid(True, alpha=0.3)
            
            # 3. Performance Timeline
            ax3.plot(self.df['timestamp'], latency_data, color=UnifiedChartStyle.COLORS['data_primary'], linewidth=2, label='Latency')
            ax3.set_title('Performance Timeline', fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            ax3.set_xlabel('Time', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax3.set_ylabel('Latency (ms)', fontsize=UnifiedChartStyle.FONT_CONFIG['label_size'])
            ax3.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
            ax3.grid(True, alpha=0.3)
            UnifiedChartStyle.format_time_axis(ax3, self.df['timestamp'])
            
            # 4. Analysis Summary
            summary_lines = [
                "Performance Analysis:",
                "",
                f"Max QPS: {qps_data.max():,.0f}",
                f"Max Latency: {latency_data.max():.1f}ms",
                f"Avg Latency: {latency_data.mean():.1f}ms",
                "",
                f"Data Points: {len(self.df)}"
            ]
            
            UnifiedChartStyle.add_text_summary(ax4, "\n".join(summary_lines), "Analysis Summary")
            
            plt.tight_layout()
            output_file = os.path.join(self.output_dir, 'performance_cliff_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
            plt.close()
            
            print(f"  ✅ Performance cliff analysis chart: {os.path.basename(output_file)}")
            return output_file
            
        except Exception as e:
            print(f"❌ Performance cliff analysis failed: {e}")
            return None

    def create_bottleneck_identification_chart(self):
        """System Bottleneck Identification Analysis - 专业化系统瓶颈识别分析"""
        print("📊 Generating System Bottleneck Identification Analysis...")

        # Check data availability
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                print("❌ Failed to load data for system bottleneck analysis")
                return None
        
        # Device configuration detection
        accounts_configured = DeviceManager.is_accounts_configured(self.df)
        
        # Create professional figure layout
        fig, axes = plt.subplots(2, 2, figsize=(18, 14))
        fig.suptitle('System Bottleneck Identification Analysis',
                    fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], fontweight='bold')
        
        # === 系统资源数据收集 ===
        system_resources = {}
        
        # CPU数据
        if 'cpu_usage' in self.df.columns:
            system_resources['CPU'] = self.df['cpu_usage']
        
        # Memory数据
        if 'mem_usage' in self.df.columns:
            system_resources['Memory'] = self.df['mem_usage']
        
        # EBS I/O数据 - DATA设备
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        if data_util_cols:
            system_resources['DATA_IO'] = self.df[data_util_cols[0]]
        
        # EBS I/O数据 - ACCOUNTS设备
        if accounts_configured:
            accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')]
            if accounts_util_cols:
                system_resources['ACCOUNTS_IO'] = self.df[accounts_util_cols[0]]
        
        # 专业瓶颈阈值定义 - 使用配置变量
        bottleneck_thresholds = {
            'CPU': int(os.getenv('BOTTLENECK_CPU_THRESHOLD', '85')),
            'Memory': int(os.getenv('BOTTLENECK_MEMORY_THRESHOLD', '90')),
            'DATA_IO': int(os.getenv('BOTTLENECK_EBS_UTIL_THRESHOLD', '90')),
            'ACCOUNTS_IO': int(os.getenv('BOTTLENECK_EBS_UTIL_THRESHOLD', '90'))
        }
        
        # 系统瓶颈检测函数
        def detect_system_bottlenecks(row_idx):
            bottlenecks = {}
            for resource, threshold in bottleneck_thresholds.items():
                if resource in system_resources:
                    value = system_resources[resource].iloc[row_idx] if row_idx < len(system_resources[resource]) else 0
                    bottlenecks[resource] = value > threshold
            return bottlenecks
        
        # === 1. 系统资源瓶颈时间线 (左上) ===
        ax1 = axes[0, 0]
        
        # 绘制各系统资源利用率
        if 'CPU' in system_resources:
            ax1.plot(self.df['timestamp'], system_resources['CPU'], 
                    label='CPU Usage', linewidth=2.5, 
                    color=UnifiedChartStyle.COLORS['data_primary'], alpha=0.8)
            ax1.axhline(y=bottleneck_thresholds['CPU'], color=UnifiedChartStyle.COLORS['critical'], 
                       linestyle='--', alpha=0.8, linewidth=2, label=f'CPU Bottleneck ({bottleneck_thresholds["CPU"]}%)')
        
        if 'Memory' in system_resources:
            ax1.plot(self.df['timestamp'], system_resources['Memory'], 
                    label='Memory Usage', linewidth=2.5, 
                    color=UnifiedChartStyle.COLORS['purple'], alpha=0.8)
            ax1.axhline(y=bottleneck_thresholds['Memory'], color=UnifiedChartStyle.COLORS['warning'], 
                       linestyle='--', alpha=0.8, linewidth=2, label=f'Memory Bottleneck ({bottleneck_thresholds["Memory"]}%)')
        
        if 'DATA_IO' in system_resources:
            ax1.plot(self.df['timestamp'], system_resources['DATA_IO'], 
                    label='DATA I/O Utilization', linewidth=2.5, 
                    color='#2E86AB', alpha=0.8)
            ax1.axhline(y=bottleneck_thresholds['DATA_IO'], color='#E74C3C', 
                       linestyle=':', alpha=0.8, linewidth=2, label=f'DATA I/O Bottleneck ({bottleneck_thresholds["DATA_IO"]}%)')
        
        if 'ACCOUNTS_IO' in system_resources:
            ax1.plot(self.df['timestamp'], system_resources['ACCOUNTS_IO'], 
                    label='ACCOUNTS I/O Utilization', linewidth=2.5, 
                    color='#F39C12', alpha=0.8)
            ax1.axhline(y=bottleneck_thresholds['ACCOUNTS_IO'], color='#8B4513', 
                       linestyle=':', alpha=0.8, linewidth=2, label=f'ACCOUNTS I/O Bottleneck ({bottleneck_thresholds["ACCOUNTS_IO"]}%)')
        
        # 计算综合瓶颈评分
        bottleneck_scores = []
        for i in range(len(self.df)):
            bottlenecks = detect_system_bottlenecks(i)
            score = sum(bottlenecks.values()) * 25  # 每个瓶颈25分，最高100分
            bottleneck_scores.append(score)
        
        # 绘制综合瓶颈评分（右Y轴）
        ax1_twin = ax1.twinx()
        ax1_twin.fill_between(self.df['timestamp'], bottleneck_scores, alpha=0.3, 
                             color='red', label='Bottleneck Score')
        ax1_twin.set_ylabel('Bottleneck Score', color='red')
        ax1_twin.set_ylim(0, 100)
        
        ax1.set_title('System Resource Bottleneck Timeline', 
                     fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        ax1.set_ylabel('Resource Utilization (%)')
        ax1.legend(fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'], loc='upper left')
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='x', rotation=45)
        
        # === 2. 瓶颈类型分布与严重程度 (右上) ===
        ax2 = axes[0, 1]
        
        # 统计各类型瓶颈事件
        bottleneck_stats = {}
        for resource in system_resources.keys():
            if resource in bottleneck_thresholds:
                threshold = bottleneck_thresholds[resource]
                bottleneck_count = (system_resources[resource] > threshold).sum()
                bottleneck_stats[resource] = bottleneck_count
        
        # 计算复合瓶颈（多个资源同时瓶颈）
        compound_bottlenecks = 0
        for i in range(len(self.df)):
            bottlenecks = detect_system_bottlenecks(i)
            if sum(bottlenecks.values()) > 1:
                compound_bottlenecks += 1
        
        if compound_bottlenecks > 0:
            bottleneck_stats['Compound'] = compound_bottlenecks
        
        # 绘制瓶颈类型分布饼图
        if bottleneck_stats and sum(bottleneck_stats.values()) > 0:
            # 定义专业颜色
            colors = {
                'CPU': UnifiedChartStyle.COLORS['data_primary'],
                'Memory': UnifiedChartStyle.COLORS['purple'],
                'DATA_IO': '#2E86AB',
                'ACCOUNTS_IO': '#F39C12',
                'Compound': UnifiedChartStyle.COLORS['critical']
            }
            
            labels = []
            values = []
            pie_colors = []
            
            for resource, count in bottleneck_stats.items():
                if count > 0:
                    labels.append(f'{resource}\n({count} events)')
                    values.append(count)
                    pie_colors.append(colors.get(resource, 'gray'))
            
            if values:
                ax2.pie(values, labels=labels, colors=pie_colors,
                       autopct='%1.1f%%', startangle=90,
                       textprops={'fontsize': UnifiedChartStyle.FONT_CONFIG['legend_size']})
                
                ax2.set_title('Bottleneck Type Distribution', 
                             fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
            else:
                ax2.text(0.5, 0.5, 'No Bottlenecks\nDetected', ha='center', va='center',
                        transform=ax2.transAxes, 
                        fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'],
                        color=UnifiedChartStyle.COLORS['success'])
                ax2.set_title('System Status: Healthy', 
                             fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        else:
            ax2.text(0.5, 0.5, 'System Running\nOptimally', ha='center', va='center',
                    transform=ax2.transAxes, 
                    fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'],
                    color=UnifiedChartStyle.COLORS['success'])
            ax2.set_title('System Status: Optimal', 
                         fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        
        # === 3. 系统资源利用率关联分析 (左下) ===
        ax3 = axes[1, 0]
        
        # 创建资源关联散点图
        available_resources = list(system_resources.keys())
        
        if len(available_resources) >= 2:
            # 选择最重要的两个资源进行关联分析
            primary_resources = []
            if 'CPU' in available_resources:
                primary_resources.append('CPU')
            if 'Memory' in available_resources:
                primary_resources.append('Memory')
            if 'DATA_IO' in available_resources and len(primary_resources) < 2:
                primary_resources.append('DATA_IO')
            if 'ACCOUNTS_IO' in available_resources and len(primary_resources) < 2:
                primary_resources.append('ACCOUNTS_IO')
            
            if len(primary_resources) >= 2:
                resource1, resource2 = primary_resources[0], primary_resources[1]
                
                # 创建散点图，颜色表示瓶颈状态
                colors = []
                for i in range(len(self.df)):
                    bottlenecks = detect_system_bottlenecks(i)
                    if bottlenecks.get(resource1, False) and bottlenecks.get(resource2, False):
                        colors.append(UnifiedChartStyle.COLORS['critical'])  # 双重瓶颈
                    elif bottlenecks.get(resource1, False) or bottlenecks.get(resource2, False):
                        colors.append(UnifiedChartStyle.COLORS['warning'])   # 单一瓶颈
                    else:
                        colors.append(UnifiedChartStyle.COLORS['success'])   # 正常
                
                ax3.scatter(system_resources[resource1], system_resources[resource2], 
                           c=colors, alpha=0.6, s=30)
                
                # 添加瓶颈阈值线
                ax3.axvline(x=bottleneck_thresholds[resource1], color=UnifiedChartStyle.COLORS['critical'], 
                           linestyle='--', alpha=0.7, linewidth=2)
                ax3.axhline(y=bottleneck_thresholds[resource2], color=UnifiedChartStyle.COLORS['critical'], 
                           linestyle='--', alpha=0.7, linewidth=2)
                
                # 标注瓶颈区域
                ax3.axvspan(bottleneck_thresholds[resource1], 100, alpha=0.1, color='red')
                ax3.axhspan(bottleneck_thresholds[resource2], 100, alpha=0.1, color='red')
                
                ax3.set_xlabel(f'{resource1} Utilization (%)')
                ax3.set_ylabel(f'{resource2} Utilization (%)')
                ax3.set_title(f'{resource1} vs {resource2} Correlation Analysis', 
                             fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
                
                legend_elements = [
                    Patch(facecolor=UnifiedChartStyle.COLORS['success'], label='Normal'),
                    Patch(facecolor=UnifiedChartStyle.COLORS['warning'], label='Single Bottleneck'),
                    Patch(facecolor=UnifiedChartStyle.COLORS['critical'], label='Compound Bottleneck')
                ]
                ax3.legend(handles=legend_elements, fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'])
                ax3.grid(True, alpha=0.3)
            else:
                ax3.text(0.5, 0.5, 'Insufficient Resources\nfor Correlation Analysis', 
                        ha='center', va='center', transform=ax3.transAxes, 
                        fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        else:
            ax3.text(0.5, 0.5, 'Insufficient Data\nfor Resource Analysis', 
                    ha='center', va='center', transform=ax3.transAxes, 
                    fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'])
        
        # === 4. 系统瓶颈诊断报告 (右下) ===
        ax4 = axes[1, 1]
        
        # 计算系统整体统计
        total_samples = len(self.df)
        total_bottleneck_events = sum(bottleneck_stats.values()) if bottleneck_stats else 0
        
        # 识别主要瓶颈资源
        primary_bottleneck = 'None'
        if bottleneck_stats:
            primary_bottleneck = max(bottleneck_stats, key=bottleneck_stats.get) if bottleneck_stats else 'None'
        
        # 计算系统健康评级
        overall_bottleneck_rate = (total_bottleneck_events / total_samples * 100) if total_samples > 0 else 0
        
        if overall_bottleneck_rate == 0:
            health_status = "[EXCELLENT]"
            health_desc = "No bottlenecks detected"
            recommendations = ["System running optimally", "Continue monitoring"]
        elif overall_bottleneck_rate < 5:
            health_status = "[GOOD]"
            health_desc = "Rare bottlenecks"
            recommendations = ["Monitor peak usage periods", "Consider capacity planning"]
        elif overall_bottleneck_rate < 15:
            health_status = "[FAIR]"
            health_desc = "Occasional bottlenecks"
            recommendations = [f"Optimize {primary_bottleneck} usage", "Review workload distribution"]
        elif overall_bottleneck_rate < 30:
            health_status = "[POOR]"
            health_desc = "Frequent bottlenecks"
            recommendations = [f"Urgent: Scale {primary_bottleneck} resources", "Implement load balancing"]
        else:
            health_status = "[CRITICAL]"
            health_desc = "Persistent bottlenecks"
            recommendations = [f"Critical: Immediate {primary_bottleneck} scaling", "Emergency capacity increase"]
        
        # 生成专业诊断报告
        summary_lines = [
            f"System Bottleneck Diagnostic Report:",
            "",
            f"Overall Health: {health_status}",
            f"Status: {health_desc}",
            f"Analysis Period: {total_samples} samples",
            "",
            "Resource Analysis:"
        ]
        
        # 各资源详细分析
        for resource in system_resources.keys():
            if resource in bottleneck_thresholds:
                max_util = system_resources[resource].max()
                avg_util = system_resources[resource].mean()
                bottleneck_count = bottleneck_stats.get(resource, 0)
                bottleneck_rate = (bottleneck_count / total_samples * 100) if total_samples > 0 else 0
                
                status_icon = "[HIGH]" if bottleneck_rate > 10 else "[MED]" if bottleneck_rate > 5 else "[LOW]"
                
                summary_lines.extend([
                    f"  {status_icon} {resource}:",
                    f"    Max: {max_util:.1f}% | Avg: {avg_util:.1f}%",
                    f"    Bottlenecks: {bottleneck_count} ({bottleneck_rate:.1f}%)"
                ])
        
        # 添加优化建议
        summary_lines.extend([
            "",
            "Optimization Recommendations:"
        ])
        
        for i, rec in enumerate(recommendations, 1):
            summary_lines.append(f"  {i}. {rec}")
        
        # 添加复合瓶颈警告
        if compound_bottlenecks > 0:
            compound_rate = (compound_bottlenecks / total_samples * 100)
            summary_lines.extend([
                "",
                f"WARNING: Compound Bottlenecks: {compound_bottlenecks} ({compound_rate:.1f}%)",
                "   Multiple resources bottlenecked simultaneously"
            ])
        
        summary_text = "\n".join(summary_lines)
        
        # 使用统一样式
        UnifiedChartStyle.add_text_summary(ax4, summary_text, 'System Bottleneck Diagnostic Report')
        
        # 应用统一布局
        UnifiedChartStyle.apply_layout('auto')
        
        # 保存文件
        output_file = os.path.join(self.output_dir, 'bottleneck_identification.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        plt.close()
        
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        print(f"✅ System Bottleneck Identification Analysis saved: {output_file}")
        print(f"   Device configuration: {device_info}")
        print(f"   System health: {health_status} - {health_desc}")
        print(f"   Primary bottleneck: {primary_bottleneck}")
        
        return output_file

    # EBS委托方法 - 委托给EBS专用模块
    def generate_ebs_bottleneck_analysis(self):
        """委托给EBS专用模块"""
        try:
            ebs_generator = EBSChartGenerator(self.df, self.output_dir)
            return ebs_generator.generate_ebs_bottleneck_analysis()
        except Exception as e:
            print(f"⚠️ EBS瓶颈分析失败: {e}")
            return None
    
    def generate_ebs_time_series(self):
        """委托给EBS专用模块"""
        try:
            ebs_generator = EBSChartGenerator(self.df, self.output_dir)
            return ebs_generator.generate_ebs_time_series()
        except Exception as e:
            print(f"⚠️ EBS时间序列分析失败: {e}")
            return None
    
    def create_block_height_sync_chart(self):
        """生成区块高度同步状态综合分析图表 - 增强版4子图布局"""
        print("📊 Generating enhanced block height synchronization analysis...")
        
        if not self.load_data():
            return None
        
        try:
            # 检查必需字段
            required_fields = ['timestamp', 'block_height_diff', 'data_loss']
            if not all(field in self.df.columns for field in required_fields):
                print("⚠️ Block height fields not found, skipping chart generation")
                return None
            
            # 数据预处理
            df_clean = self.df.dropna(subset=required_fields)
            if df_clean.empty:
                print("⚠️ No valid block height data found")
                return None
                
            timestamps = pd.to_datetime(df_clean['timestamp'])
            height_diff = pd.to_numeric(df_clean['block_height_diff'], errors='coerce')
            data_loss = pd.to_numeric(df_clean['data_loss'], errors='coerce')
            
            # 检查可选字段
            local_height = None
            mainnet_height = None
            optional_fields = ['local_block_height', 'mainnet_block_height']
            if all(field in df_clean.columns for field in optional_fields):
                local_height = pd.to_numeric(df_clean['local_block_height'], errors='coerce')
                mainnet_height = pd.to_numeric(df_clean['mainnet_block_height'], errors='coerce')
            
            # 创建2x2布局 - 使用统一样式
            fig, axes, layout = UnifiedChartStyle.setup_subplot_layout('2x2')
            fig.suptitle('Block Height Synchronization Analysis', 
                        fontsize=layout['title_fontsize'], fontweight='bold')
            
            # === 子图1: 区块高度对比 (左上) ===
            ax1 = axes[0, 0]
            if local_height is not None and mainnet_height is not None:
                ax1.plot(timestamps, local_height, color=UnifiedChartStyle.COLORS['data_primary'], linewidth=2, 
                        label='Local Height', alpha=0.8)
                ax1.plot(timestamps, mainnet_height, color=UnifiedChartStyle.COLORS['critical'], linewidth=2, 
                        label='Mainnet Height', alpha=0.8)
                ax1.set_title('Block Height Comparison', fontsize=layout['subtitle_fontsize'])
                ax1.set_ylabel('Block Height')
                ax1.legend()
                # 强制十进制格式显示，用逗号分隔
                ax1.ticklabel_format(style='plain', axis='y', useOffset=False)
                ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
            else:
                ax1.plot(timestamps, height_diff, color=UnifiedChartStyle.COLORS['data_primary'], linewidth=2, 
                        label='Height Difference', alpha=0.8)
                ax1.axhline(y=0, color=UnifiedChartStyle.COLORS['success'], linestyle='-', alpha=0.5, label='Perfect Sync')
                ax1.set_title('Block Height Difference Timeline', fontsize=layout['subtitle_fontsize'])
                ax1.set_ylabel('Height Difference')
                ax1.legend()
            
            ax1.grid(True, alpha=0.3)
            ax1.tick_params(axis='x', rotation=45)
            
            # === 子图2: 高度差值详细分析 (右上) ===
            ax2 = axes[0, 1]
            
            ax2.plot(timestamps, height_diff, color=UnifiedChartStyle.COLORS['data_primary'], linewidth=2, 
                    label='Height Difference', alpha=0.8)
            
            # 阈值线 - 使用配置变量
            threshold = int(os.getenv('BLOCK_HEIGHT_DIFF_THRESHOLD', '50'))
            ax2.axhline(y=threshold, color=UnifiedChartStyle.COLORS['warning'], linestyle='--', 
                       linewidth=2, alpha=0.7, label=f'Warning (+{threshold})')
            ax2.axhline(y=-threshold, color=UnifiedChartStyle.COLORS['warning'], linestyle='--', 
                       linewidth=2, alpha=0.7, label=f'Warning (-{threshold})')
            ax2.axhline(y=0, color=UnifiedChartStyle.COLORS['success'], linestyle='-', alpha=0.5, label='Perfect Sync')
            
            # 异常区域标注
            anomaly_mask = data_loss > 0
            if anomaly_mask.any():
                anomaly_periods = self._identify_anomaly_periods(timestamps, anomaly_mask)
                for i, (start_time, end_time) in enumerate(anomaly_periods):
                    ax2.axvspan(start_time, end_time, alpha=0.25, color=UnifiedChartStyle.COLORS['critical'], 
                               label='Data Loss Period' if i == 0 else "")
            
            ax2.set_title('Block Height Difference (Local - Mainnet)', fontsize=layout['subtitle_fontsize'])
            ax2.set_ylabel('Height Difference')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            ax2.tick_params(axis='x', rotation=45)
            
            # === 子图3: 同步状态分布 (左下) ===
            ax3 = axes[1, 0]
            
            sync_stats = self._calculate_sync_distribution(height_diff, threshold)
            
            if sync_stats['values']:
                colors = [UnifiedChartStyle.COLORS['success'], UnifiedChartStyle.COLORS['warning'], UnifiedChartStyle.COLORS['critical']]
                ax3.pie(
                    sync_stats['values'], 
                    labels=sync_stats['labels'],
                    colors=colors[:len(sync_stats['values'])],
                    autopct='%1.1f%%',
                    startangle=90,
                    textprops={'fontsize': 10}
                )
                ax3.set_title('Synchronization Status Distribution', fontsize=layout['subtitle_fontsize'])
            else:
                ax3.text(0.5, 0.5, 'No Data Available', ha='center', va='center',
                        transform=ax3.transAxes, fontsize=12)
                ax3.set_title('Synchronization Status Distribution (No Data)', fontsize=layout['subtitle_fontsize'])
            
            # === 子图4: 分析摘要 (右下) ===
            if local_height is not None and mainnet_height is not None:
                summary_text = self._generate_comprehensive_summary(
                    height_diff, data_loss, sync_stats, timestamps, local_height, mainnet_height
                )
            else:
                summary_text = self._generate_sync_stats_text(height_diff, data_loss)
            
            UnifiedChartStyle.add_text_summary(axes[1, 1], summary_text, 'Synchronization Analysis Summary')
            
            # 布局调整
            UnifiedChartStyle.apply_layout('auto')
            
            # 保存文件
            output_file = os.path.join(self.output_dir, 'block_height_sync_chart.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            plt.close()
            
            print(f"✅ Enhanced block height sync chart saved: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"❌ Error generating block height sync chart: {e}")
            return None

    def _identify_anomaly_periods(self, timestamps, data_loss):
        """识别数据丢失时间段"""
        periods = []
        start_time = None
        
        for i, (ts, loss) in enumerate(zip(timestamps, data_loss)):
            if loss == 1 and start_time is None:
                start_time = ts
            elif loss == 0 and start_time is not None:
                periods.append((start_time, ts))
                start_time = None
        
        # 处理结尾的异常
        if start_time is not None and len(timestamps) > 0:
            periods.append((start_time, timestamps.iloc[-1]))
        
        return periods

    def _generate_sync_stats_text(self, height_diff, data_loss):
        """生成同步统计文本"""
        total_samples = len(height_diff)
        anomaly_samples = int(data_loss.sum())
        avg_diff = height_diff.mean()
        max_diff = height_diff.max()
        min_diff = height_diff.min()
        
        return f"""Sync Statistics:
• Total Samples: {total_samples}
• Anomaly Samples: {anomaly_samples} ({anomaly_samples/total_samples*100:.1f}%)
• Avg Difference: {avg_diff:.1f} blocks
• Max Difference: {max_diff:.0f} blocks
• Min Difference: {min_diff:.0f} blocks"""

    def _calculate_sync_distribution(self, height_diff, threshold):
        """计算同步状态分布"""
        perfect_sync = (height_diff == 0).sum()
        good_sync = ((height_diff.abs() > 0) & (height_diff.abs() <= threshold)).sum()
        poor_sync = (height_diff.abs() > threshold).sum()
        
        total = len(height_diff)
        
        labels = []
        values = []
        
        if perfect_sync > 0:
            labels.append('Perfect Sync')
            values.append(perfect_sync)
        
        if good_sync > 0:
            labels.append('Good Sync')
            values.append(good_sync)
        
        if poor_sync > 0:
            labels.append('Poor Sync')
            values.append(poor_sync)
        
        return {
            'labels': labels,
            'values': values,
            'perfect_sync_pct': (perfect_sync / total) * 100,
            'good_sync_pct': (good_sync / total) * 100,
            'poor_sync_pct': (poor_sync / total) * 100
        }

    def _generate_comprehensive_summary(self, height_diff, data_loss, sync_stats, 
                                      timestamps, local_height, mainnet_height):
        """生成综合分析摘要"""
        max_diff = height_diff.abs().max()
        avg_diff = height_diff.abs().mean()
        data_loss_events = (data_loss > 0).sum()
        total_data_loss = data_loss.sum()
        
        duration = timestamps.iloc[-1] - timestamps.iloc[0]
        duration_minutes = duration.total_seconds() / 60
        
        summary_lines = [
            "Block Height Sync Analysis:",
            "",
            "Block Heights:",
            f"  Local Start: {local_height.iloc[0]:,}",
            f"  Local End: {local_height.iloc[-1]:,}",
            f"  Mainnet End: {mainnet_height.iloc[-1]:,}",
            f"  Max Diff: {max_diff}",
            f"  Avg Diff: {avg_diff:.1f}",
            "",
            "Synchronization Stats:",
            f"  Perfect Sync: {sync_stats['perfect_sync_pct']:.1f}%",
            f"  Good Sync: {sync_stats['good_sync_pct']:.1f}%",
            f"  Poor Sync: {sync_stats['poor_sync_pct']:.1f}%",
            "",
            "Data Loss:",
            f"  Events: {data_loss_events}",
            f"  Total: {total_data_loss}",
            "",
            "Sync Quality:",
            f"  Duration: {duration_minutes:.1f}min",
        ]
        
        if sync_stats['perfect_sync_pct'] > 90:
            quality = "EXCELLENT"
        elif sync_stats['perfect_sync_pct'] > 70:
            quality = "GOOD"
        elif sync_stats['perfect_sync_pct'] > 50:
            quality = "FAIR"
        else:
            quality = "POOR"
        
        summary_lines.extend([
            f"  Overall: {quality}",
            "",
            f"✓ Node well synchronized" if sync_stats['perfect_sync_pct'] > 50 else "⚠ Sync issues detected"
        ])
        
        return "\n".join(summary_lines)

    def generate_all_ebs_charts(self):
        """生成所有EBS图表"""
        try:
            ebs_generator = EBSChartGenerator(self.df, self.output_dir)
            return ebs_generator.generate_all_ebs_charts()
        except Exception as e:
            print(f"⚠️ EBS图表生成失败: {e}")
            return []

def main():
    parser = argparse.ArgumentParser(description='Performance Visualizer')
    parser.add_argument('data_file', help='System performance monitoring CSV file')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.data_file):
        print(f"❌ Data file does not exist: {args.data_file}")
        return 1
    
    visualizer = PerformanceVisualizer(args.data_file)
    
    result = visualizer.generate_all_charts()
    
    if result:
        print("🎉 Performance visualization completed!")
        return 0
    else:
        print("❌ Performance visualization failed")
        return 1
    
if __name__ == "__main__":
    exit(main())
