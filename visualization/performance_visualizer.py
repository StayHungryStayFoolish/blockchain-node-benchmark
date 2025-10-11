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
import seaborn as sns
import numpy as np
from datetime import datetime
from pathlib import Path
from .ebs_chart_generator import EBSChartGenerator
from .device_manager import DeviceManager
from .chart_style_config import UnifiedChartStyle

def get_visualization_thresholds():
    temp_df = pd.DataFrame()
    temp_manager = DeviceManager(temp_df)
    return temp_manager.get_visualization_thresholds()

def read_config_file(config_path):
    """读取配置文件并返回环境变量字典"""
    config_vars = {}
    try:
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # 移除行内注释和引号，处理变量替换
                    value = value.split('#')[0].strip().strip('"\'')
                    
                    # 跳过包含变量替换的行（如$auto_throughput）
                    if '$' in value:
                        continue
                        
                    config_vars[key] = value
    except FileNotFoundError:
        pass
    return config_vars

def load_framework_config():
    """加载框架配置 - 使用动态路径检测"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_dir = os.path.join(current_dir, '..', 'config')
    
    config_files = [
        'user_config.sh',
        'internal_config.sh', 
        'system_config.sh',
        'config_loader.sh'
    ]
    
    config = {}
    for config_file in config_files:
        config_path = os.path.join(config_dir, config_file)
        if os.path.exists(config_path):
            config.update(read_config_file(config_path))
    
    # 更新环境变量
    os.environ.update(config)
    return config

def format_summary_text(device_info, data_stats, accounts_stats=None):
    temp_df = pd.DataFrame()
    temp_manager = DeviceManager(temp_df)
    return temp_manager.format_summary_text(device_info, data_stats, accounts_stats)

def add_text_summary(ax, summary_text, title):
    return UnifiedChartStyle.add_text_summary(ax, summary_text, title)

def create_chart_title(base_title, accounts_configured):
    if accounts_configured:
        return f"{base_title} - DATA & ACCOUNTS Devices"
    else:
        return f"{base_title} - DATA Device Only"

def setup_font():
    return UnifiedChartStyle.setup_matplotlib()

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

# Import unified CSV data processor
current_dir = Path(__file__).parent
utils_dir = current_dir.parent / 'utils'
analysis_dir = current_dir.parent / 'analysis'

# Add paths to sys.path
for path in [str(utils_dir), str(analysis_dir)]:
    if path not in sys.path:
        sys.path.insert(0, path)

def _import_optional_dependencies():
    """优雅导入可选依赖，失败时返回占位符"""
    dependencies = {}
    
    try:
        # Add parent directory to path for utils imports
        parent_dir = os.path.dirname(os.path.dirname(__file__))
        sys.path.insert(0, parent_dir)
        
        from utils.csv_data_processor import CSVDataProcessor
        from analysis.cpu_ebs_correlation_analyzer import CPUEBSCorrelationAnalyzer
        from utils.unit_converter import UnitConverter
        
        # Import advanced_chart_generator from current directory
        current_dir = os.path.dirname(__file__)
        sys.path.insert(0, current_dir)
        from advanced_chart_generator import AdvancedChartGenerator
        
        dependencies.update({
            'CSVDataProcessor': CSVDataProcessor,
            'CPUEBSCorrelationAnalyzer': CPUEBSCorrelationAnalyzer,
            'UnitConverter': UnitConverter,
            'AdvancedChartGenerator': AdvancedChartGenerator,
            'available': True
        })
        print("✅ Advanced analysis tools loaded")
        
    except ImportError as e:
        print(f"⚠️ Advanced analysis tools unavailable: {e}")
        print("📝 Using basic functionality mode")
        
        # 简化的占位符类
        class PlaceholderTool:
            def __init__(self, *args, **kwargs): pass
            def __call__(self, *args, **kwargs): return self
            def __getattr__(self, name): return lambda *args, **kwargs: None
        
        # 特殊的CSVDataProcessor占位符
        class BasicCSVProcessor(PlaceholderTool):
            def __init__(self):
                super().__init__()
                self.df = None
            def load_csv_data(self, file): 
                self.df = pd.read_csv(file)
                return True
            def clean_data(self): return True
            def has_field(self, name): return name in self.df.columns if self.df is not None else False
            def get_device_columns_safe(self, device_prefix: str, metric_suffix: str) -> list:
                if self.df is None: return []
                return [col for col in self.df.columns if col.startswith(f'{device_prefix}_') and metric_suffix in col]
        
        dependencies.update({
            'CSVDataProcessor': BasicCSVProcessor,
            'CPUEBSCorrelationAnalyzer': PlaceholderTool,
            'UnitConverter': PlaceholderTool,
            'AdvancedChartGenerator': PlaceholderTool,
            'available': False
        })
    
    return dependencies

# 导入依赖
_deps = _import_optional_dependencies()
CSVDataProcessor = _deps['CSVDataProcessor']
CPUEBSCorrelationAnalyzer = _deps['CPUEBSCorrelationAnalyzer']
UnitConverter = _deps['UnitConverter']
AdvancedChartGenerator = _deps['AdvancedChartGenerator']
ADVANCED_TOOLS_AVAILABLE = _deps['available']

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
        if ADVANCED_TOOLS_AVAILABLE:
            try:
                self.unit_converter = UnitConverter()
                self.correlation_analyzer = CPUEBSCorrelationAnalyzer(data_file)
                self.chart_generator = AdvancedChartGenerator(data_file, self.output_dir)
            except Exception as e:
                print(f"⚠️ Advanced tools initialization failed: {e}")
                self.unit_converter = None
                self.correlation_analyzer = None
                self.chart_generator = None
        else:
            # 当高级工具不可用时，设置为 None
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
    
    def _is_accounts_configured(self):
        """检查 ACCOUNTS Device是否配置和可用 - 委托给DeviceManager"""
        device_manager = DeviceManager(self.df if hasattr(self, 'df') else pd.DataFrame())
        return device_manager.is_accounts_configured()

    def create_performance_overview_chart(self):
        """✅ System Performance Overview Chart - Systematic Refactor"""
        
        # 加载配置
        load_framework_config()
        
        accounts_configured = self._is_accounts_configured()
        
        fig, axes = plt.subplots(2, 2, figsize=(18, 12))
        fig.suptitle('System Performance Overview', fontsize=16, fontweight='bold')
        
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
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'performance_overview.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"📊 Performance Analysis overview saved: {output_file}")
        return output_file

    def create_correlation_visualization_chart(self):
        """CPU-EBS Performance Correlation Analysis - Dual Device Support"""
        
        # Device configuration detection
        data_configured = len([col for col in self.df.columns if col.startswith('data_')]) > 0
        accounts_configured = len([col for col in self.df.columns if col.startswith('accounts_')]) > 0
        
        if not data_configured:
            print("❌ DATA device data not found")
            return None
        
        # Dynamic title
        title = 'CPU-EBS Performance Correlation Analysis - DATA & ACCOUNTS Devices' if accounts_configured else 'CPU-EBS Performance Correlation Analysis - DATA Device Only'
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(title, fontsize=16, fontweight='bold')
        
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
                             alpha=0.6, s=20, color='blue', label='DATA Device')
            
            # Add ACCOUNTS device if configured
            if accounts_configured and accounts_util_cols:
                accounts_util_col = accounts_util_cols[0]
                axes[0, 0].scatter(self.df[cpu_iowait_col], self.df[accounts_util_col], 
                                 alpha=0.6, s=20, color='orange', label='ACCOUNTS Device')
            
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
            axes[0, 0].set_title('CPU I/O Wait vs Device Utilization')
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
            axes[0, 1].set_title('CPU I/O Wait vs Device Latency')
            axes[0, 1].legend()
            axes[0, 1].grid(True, alpha=0.3)
        
        # 3. Device Utilization vs Queue Depth
        if data_util_cols and data_aqu_cols:
            data_util_col = data_util_cols[0]
            data_aqu_col = data_aqu_cols[0]
            axes[1, 0].scatter(self.df[data_util_col], self.df[data_aqu_col], 
                             alpha=0.6, s=20, color='blue', label='DATA Device')
            
            # Add ACCOUNTS device if configured
            if accounts_configured and accounts_util_cols and accounts_aqu_cols:
                accounts_util_col = accounts_util_cols[0]
                accounts_aqu_col = accounts_aqu_cols[0]
                axes[1, 0].scatter(self.df[accounts_util_col], self.df[accounts_aqu_col], 
                                 alpha=0.6, s=20, color='orange', label='ACCOUNTS Device')
            
            axes[1, 0].set_xlabel('Device Utilization (%)')
            axes[1, 0].set_ylabel('Queue Depth')
            axes[1, 0].set_title('Device Utilization vs Queue Depth')
            axes[1, 0].legend()
            axes[1, 0].grid(True, alpha=0.3)
        
        # 4. Correlation Summary
        axes[1, 1].axis('off')
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
        
        axes[1, 1].text(0.05, 0.95, summary_text, transform=axes[1, 1].transAxes, 
                       fontsize=11, verticalalignment='top', fontfamily='monospace',
                       bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
        axes[1, 1].set_title('Correlation Summary')
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'cpu_ebs_correlation_visualization.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        print(f"✅ CPU-EBS correlation visualization saved: {output_file} ({device_info} devices)")
        
        return output_file

    def create_util_threshold_analysis_chart(self):
        """Device Utilization Threshold Analysis Chart - Systematic Refactor"""
        
        accounts_configured = self._is_accounts_configured()
        title = 'Device Utilization Threshold Analysis - DATA & ACCOUNTS Devices' if accounts_configured else 'Device Utilization Threshold Analysis - DATA Device Only'
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(title, fontsize=16)
        
        thresholds = get_visualization_thresholds()
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        
        if not data_util_cols:
            print("❌ DATA device utilization data not found")
            return None
        
        data_util_col = data_util_cols[0]
        accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')] if accounts_configured else []
        accounts_util_col = accounts_util_cols[0] if accounts_util_cols else None
        
        # 1. Utilization Time Series (Top Left)
        axes[0, 0].plot(self.df['timestamp'], self.df[data_util_col], 
                       label='DATA Device Utilization', linewidth=2, color='blue')
        
        if accounts_configured and accounts_util_cols:
            accounts_util_col = accounts_util_cols[0]
            axes[0, 0].plot(self.df['timestamp'], self.df[accounts_util_col], 
                           label='ACCOUNTS Device Utilization', linewidth=2, color='orange')
        
        axes[0, 0].axhline(y=thresholds['warning'], color='orange', linestyle='--', alpha=0.7, 
                          label=f'Warning: {thresholds["warning"]}%')
        axes[0, 0].axhline(y=thresholds['critical'], color='red', linestyle='--', alpha=0.7, 
                          label=f'Critical: {thresholds["critical"]}%')
        
        axes[0, 0].set_title('Device Utilization vs Thresholds')
        axes[0, 0].set_ylabel('Utilization (%)')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. Utilization Distribution (Top Right)
        axes[0, 1].hist(self.df[data_util_col], bins=15, alpha=0.8, color='blue', 
                       label='DATA Device Distribution')
        
        if accounts_configured and accounts_util_cols:
            axes[0, 1].hist(self.df[accounts_util_col], bins=15, alpha=0.6, color='orange', 
                           label='ACCOUNTS Device Distribution')
        
        axes[0, 1].axvline(x=thresholds['warning'], color='orange', linestyle='--', alpha=0.8, linewidth=2,
                          label=f'Warning: {thresholds["warning"]}%')
        axes[0, 1].axvline(x=thresholds['critical'], color='red', linestyle='--', alpha=0.8, linewidth=2,
                          label=f'Critical: {thresholds["critical"]}%')
        
        axes[0, 1].set_title('Utilization Distribution')
        axes[0, 1].set_xlabel('Utilization (%)')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # 3. Violation Timeline (Bottom Left)
        violation_data = self.df[data_util_col] > thresholds['critical']
        warning_data = (self.df[data_util_col] > thresholds['warning']) & (self.df[data_util_col] <= thresholds['critical'])
        
        axes[1, 0].plot(self.df['timestamp'], violation_data.astype(int), 
                       label='DATA Critical', linewidth=2, color='crimson', marker='o', markersize=2)
        axes[1, 0].plot(self.df['timestamp'], warning_data.astype(int) * 0.5, 
                       label='DATA Warning', linewidth=2, color='gold', marker='s', markersize=2)
        
        if accounts_configured and accounts_util_cols:
            accounts_violation = self.df[accounts_util_col] > thresholds['critical']
            accounts_warning = (self.df[accounts_util_col] > thresholds['warning']) & (self.df[accounts_util_col] <= thresholds['critical'])
            
            axes[1, 0].plot(self.df['timestamp'], accounts_violation.astype(int) + 0.1, 
                           label='ACCOUNTS Critical', linewidth=2, color='darkblue', marker='o', markersize=2)
            axes[1, 0].plot(self.df['timestamp'], accounts_warning.astype(int) * 0.5 + 0.05, 
                           label='ACCOUNTS Warning', linewidth=2, color='forestgreen', marker='s', markersize=2)
        
        axes[1, 0].set_title('Violation Timeline')
        axes[1, 0].set_ylabel('Violation Status')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        axes[1, 0].set_ylim(-0.1, 1.3)
        
        # 4. Statistics Summary (Bottom Right)
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        data_stats = {
            'mean': self.df[data_util_col].mean(),
            'max': self.df[data_util_col].max(),
            'violations': (self.df[data_util_col] > thresholds['critical']).sum(),
            'unit': '%'
        }
        
        accounts_stats = None
        if accounts_configured and accounts_util_cols:
            accounts_stats = {
                'mean': self.df[accounts_util_col].mean(),
                'max': self.df[accounts_util_col].max(),
                'violations': (self.df[accounts_util_col] > thresholds['critical']).sum(),
                'unit': '%'
            }
        
        summary_text = format_summary_text(device_info, data_stats, accounts_stats)
        add_text_summary(axes[1, 1], summary_text, 'Utilization Statistics')
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'util_threshold_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        print(f"✅ Utilization threshold analysis chart saved: {output_file} ({device_info} devices)")
        
        return output_file

    def create_await_threshold_analysis_chart(self):
        """Enhanced I/O Latency Threshold Analysis Chart"""
        
        # 先加载数据，再检查ACCOUNTS配置
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                print("❌ Failed to load data for await threshold analysis")
                return None

        accounts_configured = self._is_accounts_configured()
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
        
        # 智能阈值设置 - 基于实际数据范围
        data_max = self.df[data_await_col].max()
        data_p95 = self.df[data_await_col].quantile(0.95)
        data_p75 = self.df[data_await_col].quantile(0.75)
        data_p50 = self.df[data_await_col].median()
        
        # DATA设备阈值
        data_thresholds = {
            'excellent': data_p50 * 0.6,    # 60% of median
            'good': data_p75,               # P75
            'warning': data_p95,            # P95  
            'poor': data_p95 * 1.05,        # 105% of P95
            'critical': data_max            # Maximum observed
        }
        
        # ACCOUNTS设备独立阈值
        accounts_thresholds = data_thresholds  # 默认使用DATA阈值
        if accounts_configured and accounts_await_col:
            accounts_max = self.df[accounts_await_col].max()
            accounts_p95 = self.df[accounts_await_col].quantile(0.95)
            accounts_p75 = self.df[accounts_await_col].quantile(0.75)
            accounts_p50 = self.df[accounts_await_col].median()
            
            accounts_thresholds = {
                'excellent': accounts_p50 * 0.6,
                'good': accounts_p75,
                'warning': accounts_p95,
                'poor': accounts_p95 * 1.05,
                'critical': accounts_max
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
        axes[0, 0].tick_params(axis='x', rotation=45)
        
        # 2. Enhanced Distribution Analysis
        import numpy as np
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
        axes[1, 0].tick_params(axis='x', rotation=45)
        
        # 4. Enhanced Statistics Summary
        axes[1, 1].axis('off')
        axes[1, 1].set_title('Performance Analysis Summary', 
                            fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=20)
        
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
        
        # 使用UnifiedChartStyle统一的文本样式 (与bottleneck_identification保持一致)
        axes[1, 1].text(0.05, 0.95, summary_text, transform=axes[1, 1].transAxes, 
                       fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'], 
                       verticalalignment='top', 
                       fontfamily=plt.rcParams['font.sans-serif'][0])
        
        plt.tight_layout()
        output_file = os.path.join(self.output_dir, 'await_threshold_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        print(f"✅ I/O latency threshold analysis chart saved: {output_file} ({device_info} devices)")
        
        return output_file

    def create_device_comparison_chart(self):
        """Device Performance Comparison Chart"""
        
        accounts_configured = self._is_accounts_configured()
        
        if not accounts_configured:
            print("⚠️ ACCOUNTS device not configured, creating DATA-only comparison")
        
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                print("❌ Failed to load data for device comparison")
                return None
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        title = 'Device Performance Comparison - DATA & ACCOUNTS' if accounts_configured else 'Device Performance Analysis - DATA Only'
        fig.suptitle(title, fontsize=16)
        
        # Find device columns
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        data_await_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_avg_await')]
        
        accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')] if accounts_configured else []
        accounts_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_avg_await')] if accounts_configured else []
        
        if not data_util_cols or not data_await_cols:
            print("❌ Required DATA device metrics not found")
            return None
        
        data_util_col = data_util_cols[0]
        data_await_col = data_await_cols[0]
        accounts_util_col = accounts_util_cols[0] if accounts_util_cols else None
        accounts_await_col = accounts_await_cols[0] if accounts_await_cols else None
        
        # 1. Utilization Comparison
        axes[0, 0].plot(self.df['timestamp'], self.df[data_util_col], 
                       label='DATA Utilization', linewidth=2, color='blue')
        
        if accounts_configured and accounts_util_col:
            axes[0, 0].plot(self.df['timestamp'], self.df[accounts_util_col], 
                           label='ACCOUNTS Utilization', linewidth=2, color='orange')
        
        axes[0, 0].set_title('Device Utilization Comparison')
        axes[0, 0].set_ylabel('Utilization (%)')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. Latency Comparison
        axes[0, 1].plot(self.df['timestamp'], self.df[data_await_col], 
                       label='DATA Latency', linewidth=2, color='blue')
        
        if accounts_configured and accounts_await_col:
            axes[0, 1].plot(self.df['timestamp'], self.df[accounts_await_col], 
                           label='ACCOUNTS Latency', linewidth=2, color='orange')
        
        axes[0, 1].set_title('Device Latency Comparison')
        axes[0, 1].set_ylabel('Average Latency (ms)')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # 3. Performance Metrics Bar Chart
        metrics = ['Mean Util (%)', 'Max Util (%)', 'Mean Latency (ms)', 'Max Latency (ms)']
        data_values = [
            self.df[data_util_col].mean(),
            self.df[data_util_col].max(),
            self.df[data_await_col].mean(),
            self.df[data_await_col].max()
        ]
        
        x_pos = range(len(metrics))
        bars1 = axes[1, 0].bar([x - 0.2 for x in x_pos], data_values, 0.4, 
                              label='DATA Device', color='blue', alpha=0.7)
        
        # 添加数值标签
        for bar, value in zip(bars1, data_values):
            axes[1, 0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(data_values)*0.01,
                           f'{value:.1f}', ha='center', va='bottom', fontsize=8)
        
        if accounts_configured and accounts_util_col and accounts_await_col:
            accounts_values = [
                self.df[accounts_util_col].mean(),
                self.df[accounts_util_col].max(),
                self.df[accounts_await_col].mean(),
                self.df[accounts_await_col].max()
            ]
            bars2 = axes[1, 0].bar([x + 0.2 for x in x_pos], accounts_values, 0.4, 
                                  label='ACCOUNTS Device', color='orange', alpha=0.7)
            
            # 添加数值标签
            for bar, value in zip(bars2, accounts_values):
                axes[1, 0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(accounts_values)*0.01,
                               f'{value:.1f}', ha='center', va='bottom', fontsize=8)
        
        axes[1, 0].set_title('Performance Metrics Comparison')
        axes[1, 0].set_xticks(x_pos)
        axes[1, 0].set_xticklabels(metrics, rotation=45, ha='right')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # 4. Summary
        axes[1, 1].axis('off')
        
        summary_lines = [
            "Device Comparison Summary:",
            "",
            f"DATA Device:",
            f"  Avg Utilization: {self.df[data_util_col].mean():.1f}%",
            f"  Avg Latency: {self.df[data_await_col].mean():.2f}ms",
        ]
        
        if accounts_configured and accounts_util_col and accounts_await_col:
            summary_lines.extend([
                "",
                f"ACCOUNTS Device:",
                f"  Avg Utilization: {self.df[accounts_util_col].mean():.1f}%",
                f"  Avg Latency: {self.df[accounts_await_col].mean():.2f}ms",
            ])
        else:
            summary_lines.append("\nACCOUNTS Device: Not Configured")
        
        summary_text = "\n".join(summary_lines)
        
        axes[1, 1].text(0.05, 0.95, summary_text, transform=axes[1, 1].transAxes, 
                       fontsize=11, verticalalignment='top', fontfamily='monospace',
                       bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
        
        plt.tight_layout()
        output_file = os.path.join(self.output_dir, 'device_performance_comparison.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
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
                'monitoring_memory': ['monitoring_mem_percent', 'monitoring_memory_percent', 'monitor_memory']
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
            
            # 创建图表
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('Monitoring Overhead Analysis', fontsize=16, fontweight='bold')
            
            # 1. Resource consumption comparison
            ax1 = axes[0, 0]
            ax1.set_title('System Resource Consumption Comparison')
            
            if monitoring_cpu_field and monitoring_mem_field:
                monitor_cpu = overhead_df[monitoring_cpu_field].mean()
                monitor_mem = overhead_df[monitoring_mem_field].mean()
                
                categories = ['CPU Usage (%)', 'Memory Usage (%)']
                monitor_values = [monitor_cpu, monitor_mem]
                
                ax1.bar(categories, monitor_values, alpha=0.8)
                ax1.set_ylabel('Usage Percentage (%)')
                ax1.grid(True, alpha=0.3)
            
            # 2. Monitoring overhead trends
            ax2 = axes[0, 1]
            ax2.set_title('Monitoring Overhead Trends')
            
            if 'timestamp' in overhead_df.columns and monitoring_cpu_field:
                ax2.plot(overhead_df['timestamp'], overhead_df[monitoring_cpu_field], 
                        label='CPU Overhead', linewidth=2)
                if monitoring_mem_field:
                    ax2.plot(overhead_df['timestamp'], overhead_df[monitoring_mem_field], 
                            label='Memory Overhead', linewidth=2)
                ax2.set_ylabel('Overhead (%)')
                ax2.legend()
                ax2.grid(True, alpha=0.3)
            
            # 3. Statistics summary
            ax3 = axes[1, 0]
            ax3.set_title('Overhead Statistics')
            ax3.axis('off')
            
            if monitoring_cpu_field and monitoring_mem_field:
                stats_text = f"""Monitoring Overhead Summary:

CPU Overhead:
  Average: {overhead_df[monitoring_cpu_field].mean():.2f}%
  Maximum: {overhead_df[monitoring_cpu_field].max():.2f}%

Memory Overhead:
  Average: {overhead_df[monitoring_mem_field].mean():.2f}%
  Maximum: {overhead_df[monitoring_mem_field].max():.2f}%

Data Points: {len(overhead_df)}"""
                
                ax3.text(0.1, 0.9, stats_text, transform=ax3.transAxes, fontsize=10,
                        verticalalignment='top', fontfamily='monospace')
            
            # 4. Impact analysis
            ax4 = axes[1, 1]
            ax4.set_title('Impact Analysis')
            
            if monitoring_cpu_field and monitoring_mem_field:
                impact_categories = ['CPU Impact', 'Memory Impact']
                impact_values = [
                    overhead_df[monitoring_cpu_field].mean(),
                    overhead_df[monitoring_mem_field].mean()
                ]
                
                colors = ['red' if x > 10 else 'orange' if x > 5 else 'green' for x in impact_values]
                ax4.bar(impact_categories, impact_values, color=colors, alpha=0.7)
                ax4.set_ylabel('Impact Percentage (%)')
                ax4.grid(True, alpha=0.3)
            
            plt.tight_layout()
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
            if ADVANCED_TOOLS_AVAILABLE and self.chart_generator is not None:
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
        
        try:
            fig, axes = plt.subplots(2, 2, figsize=(18, 12))
            fig.suptitle('Performance Metrics Moving Average Trend Analysis', fontsize=16, fontweight='bold')
            
            # Moving average window size
            window_size = min(10, len(self.df) // 10)  # 自适应窗口大小
            if window_size < 3:
                window_size = 3
            
            # 1. CPU Usage trends
            ax1 = axes[0, 0]
            ax1.plot(self.df['timestamp'], self.df['cpu_usage'], 
                    color='lightblue', linewidth=1, alpha=0.5, label='CPU Usage (Raw)')
            
            cpu_smooth = self.df['cpu_usage'].rolling(window=window_size, center=True).mean()
            ax1.plot(self.df['timestamp'], cpu_smooth, 
                    color='blue', linewidth=2, label=f'CPU Usage({window_size}-point smoothed)')
            
            ax1.set_title('CPU Usage Trends')
            ax1.set_ylabel('Usage (%)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 2. Memory Usage trends
            ax2 = axes[0, 1]
            ax2.plot(self.df['timestamp'], self.df['mem_usage'], 
                    color='lightcoral', linewidth=1, alpha=0.5, label='Memory Usage (Raw)')
            
            mem_smooth = self.df['mem_usage'].rolling(window=window_size, center=True).mean()
            ax2.plot(self.df['timestamp'], mem_smooth, 
                    color='red', linewidth=2, label=f'Memory Usage({window_size}-point smoothed)')
            
            ax2.set_title('Memory Usage Trends')
            ax2.set_ylabel('Usage (%)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            # 3. EBS Latency trends - 支持双设备，移除Raw数据显示
            ax3 = axes[1, 0]
            
            # 查找DATA和ACCOUNTS设备的延迟字段
            data_await_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_avg_await')]
            accounts_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_avg_await')]
            
            if data_await_cols:
                data_await_col = data_await_cols[0]
                # 只显示平滑后的数据，颜色区分度更高
                await_smooth = self.df[data_await_col].rolling(window=window_size, center=True).mean()
                ax3.plot(self.df['timestamp'], await_smooth, 
                        color='blue', linewidth=2, label=f'DATA EBS Latency ({window_size}-point avg)')
                
                # ACCOUNTS设备延迟
                accounts_configured = self._is_accounts_configured()
                if accounts_configured and accounts_await_cols:
                    accounts_await_col = accounts_await_cols[0]
                    accounts_await_smooth = self.df[accounts_await_col].rolling(window=window_size, center=True).mean()
                    ax3.plot(self.df['timestamp'], accounts_await_smooth, 
                            color='orange', linewidth=2, label=f'ACCOUNTS EBS Latency ({window_size}-point avg)')
                
                ax3.set_title('EBS Latency Trends (Smoothed - DATA & ACCOUNTS)')
                ax3.set_ylabel('Latency (ms)')
                ax3.legend(fontsize=9)
                ax3.grid(True, alpha=0.3)
            else:
                axes[1, 0].text(0.5, 0.5, 'EBS Latency data not found', ha='center', va='center', transform=axes[1, 0].transAxes)
                axes[1, 0].set_title('EBS Latency Trends (No Data)')
            
            # 4. Network bandwidth trends
            if 'net_rx_mbps' in self.df.columns:
                ax4 = axes[1, 1]
                ax4.plot(self.df['timestamp'], self.df['net_rx_mbps'], 
                        color='lightcoral', linewidth=1, alpha=0.5, label='Network RX (Raw)')
                
                net_smooth = self.df['net_rx_mbps'].rolling(window=window_size, center=True).mean()
                ax4.plot(self.df['timestamp'], net_smooth, 
                        color='orange', linewidth=2, label=f'Network RX({window_size}-point smoothed)')
                
                ax4.set_title('Network Bandwidth Trends')
                ax4.set_ylabel('Bandwidth (Mbps)')
                ax4.legend()
                ax4.grid(True, alpha=0.3)
            else:
                axes[1, 1].text(0.5, 0.5, 'Network bandwidth data not found', ha='center', va='center', transform=axes[1, 1].transAxes)
                axes[1, 1].set_title('Network Bandwidth Trends (No Data)')
            
            # Format time axis
            for ax in axes.flat:
                ax.tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            
            # Save chart
            output_file = os.path.join(self.output_dir, 'smoothed_trend_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
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
            fig.suptitle('QPS Performance Trend Analysis', fontsize=16, fontweight='bold')
            
            # 查找数值型QPS字段 (排除布尔型字段)
            qps_cols = []
            for col in self.df.columns:
                if 'qps' in col.lower():
                    # 检查是否为数值型字段
                    try:
                        numeric_data = pd.to_numeric(self.df[col], errors='coerce')
                        if not numeric_data.isna().all():  # 如果有有效数值
                            qps_cols.append(col)
                    except (ValueError, TypeError, AttributeError) as e:
                        continue
            
            if not qps_cols:
                print("⚠️  No numeric QPS fields found")
                plt.close()
                return None
            
            # 1. QPS时间序列
            ax1 = axes[0, 0]
            for qps_col in qps_cols[:3]:  # 最多显示3个QPS指标
                qps_data = pd.to_numeric(self.df[qps_col], errors='coerce')
                valid_mask = ~qps_data.isna()
                if valid_mask.any():
                    ax1.plot(self.df.loc[valid_mask, 'timestamp'], 
                            qps_data[valid_mask], 
                            label=qps_col, linewidth=2)
            ax1.set_title('QPS Time Series')
            ax1.set_ylabel('QPS')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 2. QPS分布直方图 (只处理数值数据)
            ax2 = axes[0, 1]
            for qps_col in qps_cols[:2]:
                qps_data = pd.to_numeric(self.df[qps_col], errors='coerce')
                qps_data = qps_data.dropna()  # 移除NaN值
                if len(qps_data) > 0:
                    # 确保数据是数值型
                    qps_data = qps_data.astype(float)
                    ax2.hist(qps_data, alpha=0.7, label=qps_col, bins=20)
            ax2.set_title('QPS Distribution')
            ax2.set_xlabel('QPS')
            ax2.set_ylabel('Frequency')
            ax2.legend()
            
            # 3. QPS与CPU相关性
            ax3 = axes[1, 0]
            if 'cpu_usage' in self.df.columns and qps_cols:
                qps_data = pd.to_numeric(self.df[qps_cols[0]], errors='coerce')
                cpu_data = pd.to_numeric(self.df['cpu_usage'], errors='coerce')
                
                # 只使用有效数据点
                valid_mask = ~(qps_data.isna() | cpu_data.isna())
                if valid_mask.any():
                    ax3.scatter(cpu_data[valid_mask], qps_data[valid_mask], alpha=0.6)
                    ax3.set_title('QPS vs CPU Usage')
                    ax3.set_xlabel('CPU Usage (%)')
                    ax3.set_ylabel('QPS')
                    ax3.grid(True, alpha=0.3)
            
            # 4. QPS统计摘要
            ax4 = axes[1, 1]
            ax4.axis('off')
            stats_text = "QPS Statistics Summary:\n\n"
            for qps_col in qps_cols[:3]:
                qps_data = pd.to_numeric(self.df[qps_col], errors='coerce').dropna()
                if len(qps_data) > 0:
                    stats_text += f"{qps_col}:\n"
                    stats_text += f"  Average: {qps_data.mean():.2f}\n"
                    stats_text += f"  Maximum: {qps_data.max():.2f}\n"
                    stats_text += f"  Minimum: {qps_data.min():.2f}\n"
                    stats_text += f"  Valid samples: {len(qps_data)}\n\n"
            
            # 添加QPS可用性信息
            if 'qps_data_available' in self.df.columns:
                qps_available = self.df['qps_data_available']
                # 正确处理布尔类型数据
                if qps_available.notna().any():
                    # 将数据转换为布尔类型并计算True的数量
                    bool_series = pd.to_numeric(qps_available, errors='coerce').fillna(0).astype(bool)
                    true_count = bool_series.sum()
                else:
                    true_count = 0
                total_count = len(qps_available)
                stats_text += f"QPS Data Availability:\n"
                stats_text += f"  Available: {true_count}/{total_count} ({true_count/total_count*100:.1f}%)\n"
            
            ax4.text(0.1, 0.9, stats_text, transform=ax4.transAxes, fontsize=10, 
                     verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgray', alpha=0.8))
            
            plt.tight_layout()
            
            # Save chart
            output_file = os.path.join(self.output_dir, 'qps_trend_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  ✅ QPS trend analysis chart: {os.path.basename(output_file)}")
            return output_file, {}
            
        except Exception as e:
            print(f"❌ QPS trend analysis chart generation failed: {e}")
            return None

    def create_resource_efficiency_analysis_chart(self):
        """Resource efficiency analysis chart"""
        print("📊 Generating resource efficiency analysis charts...")
        
        # 检查数据是否已加载
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                print("❌ Failed to load data for resource efficiency analysis")
                return None
        
        try:
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('Resource Efficiency Analysis', fontsize=16, fontweight='bold')
            
            # 1. CPU efficiency analysis
            ax1 = axes[0, 0]
            if 'cpu_usage' in self.df.columns:
                cpu_data = self.df['cpu_usage'].dropna()
                thresholds = get_visualization_thresholds()
                efficiency_ranges = ['Low(<30%)', 'Normal(30-60%)', f'High(60-{thresholds["warning"]}%)', f'Overload(>{thresholds["warning"]}%)']
                efficiency_counts = [
                    len(cpu_data[cpu_data < 30]),
                    len(cpu_data[(cpu_data >= 30) & (cpu_data < 60)]),
                    len(cpu_data[(cpu_data >= 60) & (cpu_data < thresholds["warning"])]),
                    len(cpu_data[cpu_data >= thresholds["warning"]])
                ]
                wedges, texts, autotexts = ax1.pie(efficiency_counts, labels=efficiency_ranges,
                                                  autopct='%1.1f%%', startangle=90,
                                                  explode=(0.05, 0.05, 0.05, 0.05),
                                                  textprops={'fontsize': 8})
                # 修复字体重叠问题
                for text in texts:
                    text.set_fontsize(8)
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontweight('bold')
                    autotext.set_fontsize(8)
                ax1.set_title('CPU Efficiency Distribution', fontsize=11, pad=20)
            
            # 2. Memory efficiency analysis
            ax2 = axes[0, 1]
            if 'mem_usage' in self.df.columns:
                mem_data = self.df['mem_usage'].dropna()
                thresholds = get_visualization_thresholds()
                mem_ranges = ['Low(<40%)', 'Normal(40-70%)', f'High(70-{thresholds["memory"]}%)', f'Overload(>{thresholds["memory"]}%)']
                mem_counts = [
                    len(mem_data[mem_data < 40]),
                    len(mem_data[(mem_data >= 40) & (mem_data < 70)]),
                    len(mem_data[(mem_data >= 70) & (mem_data < thresholds["memory"])]),
                    len(mem_data[mem_data >= thresholds["memory"]])
                ]
                wedges, texts, autotexts = ax2.pie(mem_counts, labels=mem_ranges,
                                                  autopct='%1.1f%%', startangle=90,
                                                  explode=(0.05, 0.05, 0.05, 0.05),
                                                  textprops={'fontsize': 8})
                # 修复字体重叠问题
                for text in texts:
                    text.set_fontsize(8)
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontweight('bold')
                    autotext.set_fontsize(8)
                ax2.set_title('Memory Efficiency Distribution', fontsize=11, pad=20)
            
            # 3. I/O efficiency analysis - 支持双设备
            ax3 = axes[1, 0]
            data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
            accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')]
            
            if data_util_cols:
                util_col = data_util_cols[0]
                util_data = self.df[util_col].dropna()
                ax3.hist(util_data, bins=20, alpha=0.7, color='blue', label='DATA Device')
                ax3.axvline(util_data.mean(), color='blue', linestyle='--', 
                           label=f'DATA Avg: {util_data.mean():.1f}%')
                
                # ACCOUNTS设备利用率分布
                if accounts_util_cols:
                    accounts_util_col = accounts_util_cols[0]
                    accounts_util_data = self.df[accounts_util_col].dropna()
                    ax3.hist(accounts_util_data, bins=20, alpha=0.7, color='orange', label='ACCOUNTS Device')
                    ax3.axvline(accounts_util_data.mean(), color='orange', linestyle='--', 
                               label=f'ACCOUNTS Avg: {accounts_util_data.mean():.1f}%')
                
                ax3.set_title('I/O Utilization Distribution (DATA + ACCOUNTS)')
                ax3.set_xlabel('Utilization (%)')
                ax3.set_ylabel('Frequency')
                ax3.legend(fontsize=9)
                ax3.grid(True, alpha=0.3)
            
            # 4. Efficiency statistics summary
            ax4 = axes[1, 1]
            ax4.axis('off')
            stats_text = "Efficiency Statistics Summary:\n\n"
            if 'cpu_usage' in self.df.columns:
                cpu_avg = self.df['cpu_usage'].mean()
                stats_text += f"CPU Average Utilization: {cpu_avg:.1f}%\n"
            if 'mem_usage' in self.df.columns:
                mem_avg = self.df['mem_usage'].mean()
                stats_text += f"Memory Average Utilization: {mem_avg:.1f}%\n"
            if data_util_cols:
                io_avg = self.df[data_util_cols[0]].mean()
                stats_text += f"I/O Average Utilization: {io_avg:.1f}%\n"
            ax4.text(0.1, 0.9, stats_text, transform=ax4.transAxes, fontsize=12, 
                     verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgray', alpha=0.8))
            
            # 调整整体布局，解决饼图重叠问题
            plt.subplots_adjust(hspace=0.35, wspace=0.25)
            
            # 保存图表
            output_file = os.path.join(self.output_dir, 'resource_efficiency_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  ✅ Resource efficiency analysis chart: {os.path.basename(output_file)}")
            return output_file, {}
            
        except Exception as e:
            print(f"❌ Resource efficiency analysis chart generation failed: {e}")
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
        accounts_configured = self._is_accounts_configured()
        
        # Create professional figure layout
        fig, axes = plt.subplots(2, 2, figsize=(18, 14))
        fig.suptitle('System Bottleneck Identification Analysis', 
                    fontsize=UnifiedChartStyle.FONT_CONFIG['title_size'], fontweight='bold')
        
        # Get threshold values
        thresholds = get_visualization_thresholds()
        
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
            data_util_col = data_util_cols[0]
        
        # EBS I/O数据 - ACCOUNTS设备
        accounts_util_col = None
        if accounts_configured:
            accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')]
            if accounts_util_cols:
                system_resources['ACCOUNTS_IO'] = self.df[accounts_util_cols[0]]
                accounts_util_col = accounts_util_cols[0]
        
        # 专业瓶颈阈值定义
        bottleneck_thresholds = {
            'CPU': 85,
            'Memory': 90,
            'DATA_IO': 90,
            'ACCOUNTS_IO': 90
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
                    color=UnifiedChartStyle.COLORS['accounts_primary'], alpha=0.8)
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
                'Memory': UnifiedChartStyle.COLORS['accounts_primary'],
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
                wedges, texts, autotexts = ax2.pie(values, labels=labels, colors=pie_colors,
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
                
                scatter = ax3.scatter(system_resources[resource1], system_resources[resource2], 
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
                
                # 添加图例
                from matplotlib.patches import Patch
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
        ax4.axis('off')
        ax4.set_title('System Bottleneck Diagnostic Report', 
                     fontsize=UnifiedChartStyle.FONT_CONFIG['subtitle_size'], pad=20)
        
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
        
        # 使用UnifiedChartStyle的统一文本样式，无背景框
        ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes,
                fontsize=UnifiedChartStyle.FONT_CONFIG['legend_size'], 
                verticalalignment='top', 
                fontfamily=plt.rcParams['font.sans-serif'][0])
        
        # 应用统一布局
        plt.tight_layout()
        plt.subplots_adjust(top=0.93)  # 为主标题留空间
        
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

        try:
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('System Bottleneck Identification Analysis', fontsize=16, fontweight='bold')
            
            # 1. Bottleneck time series
            ax1 = axes[0, 0]
            bottleneck_data = []
            thresholds = get_visualization_thresholds()
            
            if 'cpu_usage' in self.df.columns:
                cpu_bottleneck = (self.df['cpu_usage'] > thresholds['warning']).astype(int)
                ax1.plot(self.df['timestamp'], cpu_bottleneck, label=f'CPU Bottleneck(>{thresholds["warning"]}%)', linewidth=2)
                bottleneck_data.append(('CPU', cpu_bottleneck.sum()))
            
            if 'mem_usage' in self.df.columns:
                mem_bottleneck = (self.df['mem_usage'] > thresholds['memory']).astype(int)
                ax1.plot(self.df['timestamp'], mem_bottleneck, label=f'Memory Bottleneck(>{thresholds["memory"]}%)', linewidth=2)
                bottleneck_data.append(('Memory', mem_bottleneck.sum()))
            
            data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
            if data_util_cols:
                io_bottleneck = (self.df[data_util_cols[0]] > thresholds['io_warning']).astype(int)
                ax1.plot(self.df['timestamp'], io_bottleneck, label=f'I/O Bottleneck(>{thresholds["io_warning"]}%)', linewidth=2)
                bottleneck_data.append(('I/O', io_bottleneck.sum()))
            
            ax1.set_title('Bottleneck Time Series')
            ax1.set_ylabel('Bottleneck Status')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 2. Bottleneck frequency statistics
            ax2 = axes[0, 1]
            if bottleneck_data:
                resources, counts = zip(*bottleneck_data)
                ax2.bar(resources, counts, color=['red', 'orange', 'yellow'])
                ax2.set_title('Bottleneck Frequency Statistics')
                ax2.set_ylabel('Bottleneck Count')
                for i, count in enumerate(counts):
                    ax2.text(i, count + max(counts) * 0.01, str(count), ha='center')
            
            # 3. Resource utilization heatmap
            ax3 = axes[1, 0]
            resource_cols = []
            if 'cpu_usage' in self.df.columns:
                resource_cols.append('cpu_usage')
            if 'mem_usage' in self.df.columns:
                resource_cols.append('mem_usage')
            if data_util_cols:
                resource_cols.append(data_util_cols[0])
            
            if resource_cols:
                resource_data = self.df[resource_cols].dropna()
                if len(resource_data) > 0:
                    im = ax3.imshow(resource_data.T, aspect='auto', cmap='RdYlBu_r')
                    ax3.set_title('Resource Utilization Heatmap')
                    ax3.set_yticks(range(len(resource_cols)))
                    ax3.set_yticklabels(resource_cols)
                    plt.colorbar(im, ax=ax3)
            
            # 4. Bottleneck analysis summary
            ax4 = axes[1, 1]
            ax4.axis('off')
            summary_text = "Bottleneck Analysis Summary:\n\n"
            total_points = len(self.df)
            
            for resource, count in bottleneck_data:
                percentage = (count / total_points) * 100 if total_points > 0 else 0
                summary_text += f"{resource} Bottleneck:\n"
                summary_text += f"  Occurrences: {count}\n"
                summary_text += f"  Percentage: {percentage:.1f}%\n\n"
            
            ax4.text(0.1, 0.9, summary_text, transform=ax4.transAxes, fontsize=10, 
                     verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgray', alpha=0.8))
            
            plt.tight_layout()
            
            # 保存图表
            output_file = os.path.join(self.output_dir, 'bottleneck_identification.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  ✅ Bottleneck identification analysis chart: {os.path.basename(output_file)}")
            return output_file, {}
            
        except Exception as e:
            print(f"❌ Bottleneck identification analysis chart generation failed: {e}")
            return None

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
            
            # 创建2x2布局
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('Block Height Synchronization Analysis', fontsize=16, fontweight='bold')
            
            # === 子图1: 区块高度对比 (左上) ===
            ax1 = axes[0, 0]
            if local_height is not None and mainnet_height is not None:
                ax1.plot(timestamps, local_height, color='blue', linewidth=2, 
                        label='Local Height', alpha=0.8)
                ax1.plot(timestamps, mainnet_height, color='red', linewidth=2, 
                        label='Mainnet Height', alpha=0.8)
                ax1.set_title('Block Height Comparison')
                ax1.set_ylabel('Block Height')
                ax1.legend()
                # 强制十进制格式显示，用逗号分隔
                ax1.ticklabel_format(style='plain', axis='y', useOffset=False)
                ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
            else:
                ax1.plot(timestamps, height_diff, color='blue', linewidth=2, 
                        label='Height Difference', alpha=0.8)
                ax1.axhline(y=0, color='green', linestyle='-', alpha=0.5, label='Perfect Sync')
                ax1.set_title('Block Height Difference Timeline')
                ax1.set_ylabel('Height Difference')
                ax1.legend()
            
            ax1.grid(True, alpha=0.3)
            ax1.tick_params(axis='x', rotation=45)
            
            # === 子图2: 高度差值详细分析 (右上) ===
            ax2 = axes[0, 1]
            
            ax2.plot(timestamps, height_diff, color='#2E86AB', linewidth=2, 
                    label='Height Difference', alpha=0.8)
            
            # 阈值线 - 使用配置变量
            threshold = int(os.getenv('BLOCK_HEIGHT_DIFF_THRESHOLD', '50'))
            ax2.axhline(y=threshold, color='orange', linestyle='--', 
                       linewidth=2, alpha=0.7, label=f'Warning (+{threshold})')
            ax2.axhline(y=-threshold, color='orange', linestyle='--', 
                       linewidth=2, alpha=0.7, label=f'Warning (-{threshold})')
            ax2.axhline(y=0, color='green', linestyle='-', alpha=0.5, label='Perfect Sync')
            
            # 异常区域标注
            anomaly_mask = data_loss > 0
            if anomaly_mask.any():
                anomaly_periods = self._identify_anomaly_periods(timestamps, anomaly_mask)
                for i, (start_time, end_time) in enumerate(anomaly_periods):
                    ax2.axvspan(start_time, end_time, alpha=0.25, color='red', 
                               label='Data Loss Period' if i == 0 else "")
            
            ax2.set_title('Block Height Difference (Local - Mainnet)')
            ax2.set_ylabel('Height Difference')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            ax2.tick_params(axis='x', rotation=45)
            
            # === 子图3: 同步状态分布 (左下) ===
            ax3 = axes[1, 0]
            
            sync_stats = self._calculate_sync_distribution(height_diff, threshold)
            
            if sync_stats['values']:
                colors = ['#2ECC71', '#F39C12', '#E74C3C']
                wedges, texts, autotexts = ax3.pie(
                    sync_stats['values'], 
                    labels=sync_stats['labels'],
                    colors=colors[:len(sync_stats['values'])],
                    autopct='%1.1f%%',
                    startangle=90,
                    textprops={'fontsize': 10}
                )
                ax3.set_title('Synchronization Status Distribution')
            else:
                ax3.text(0.5, 0.5, 'No Data Available', ha='center', va='center',
                        transform=ax3.transAxes, fontsize=12)
                ax3.set_title('Synchronization Status Distribution (No Data)')
            
            # === 子图4: 分析摘要 (右下) ===
            ax4 = axes[1, 1]
            ax4.axis('off')
            ax4.set_title('Synchronization Analysis Summary')
            
            if local_height is not None and mainnet_height is not None:
                summary_text = self._generate_comprehensive_summary(
                    height_diff, data_loss, sync_stats, timestamps, local_height, mainnet_height
                )
            else:
                summary_text = self._generate_sync_stats_text(height_diff, data_loss)
            
            ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes,
                    verticalalignment='top', fontsize=10, fontfamily='monospace')
            
            # 布局调整
            plt.tight_layout()
            plt.subplots_adjust(top=0.93)
            
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
