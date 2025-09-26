#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Visualizer - Production Version (CSV Field Consistency Fixed)
Uses unified CSV data processor to ensure field access consistency and reliability
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
import numpy as np
from datetime import datetime
import argparse
import os
import sys
from pathlib import Path

def get_visualization_thresholds():
    """获取可视化阈值配置"""
    return {
        'warning': int(os.getenv('BOTTLENECK_CPU_THRESHOLD', 85)),
        'critical': int(os.getenv('SUCCESS_RATE_THRESHOLD', 95)),
        'io_warning': int(os.getenv('BOTTLENECK_NETWORK_THRESHOLD', 80)),
        'memory': int(os.getenv('BOTTLENECK_MEMORY_THRESHOLD', 90))
    }

# Configure font support for cross-platform compatibility
def setup_font():
    """Configure matplotlib font for cross-platform compatibility"""
    # Use standard fonts that work across all platforms
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False
    print("✅ Using font: DejaVu Sans")
    return True

# Initialize font configuration
setup_font()

# English labels for universal compatibility
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

try:
    # Add parent directory to path for utils imports
    import sys
    import os
    parent_dir = os.path.dirname(os.path.dirname(__file__))
    sys.path.insert(0, parent_dir)
    
    from utils.csv_data_processor import CSVDataProcessor
    from analysis.cpu_ebs_correlation_analyzer import CPUEBSCorrelationAnalyzer
    from utils.unit_converter import UnitConverter
    # Import advanced_chart_generator from current directory
    current_dir = os.path.dirname(__file__)
    sys.path.insert(0, current_dir)
    from advanced_chart_generator import AdvancedChartGenerator
    ADVANCED_TOOLS_AVAILABLE = True
    print("✅ Advanced analysis tools loaded")
except ImportError as e:
    print(f"⚠️  Advanced analysis tools unavailable: {e}")
    print("📝 Using basic functionality mode, some advanced features may be unavailable")
    ADVANCED_TOOLS_AVAILABLE = False
    # Set placeholder classes to avoid runtime errors
    class CSVDataProcessor:
        def __init__(self):
            self.df = None
        def load_csv_data(self, file): 
            self.df = pd.read_csv(file)
            return True
        def clean_data(self):
            return True
        def has_field(self, name):
            return name in self.df.columns if self.df is not None else False
        def get_device_columns_safe(self, device_prefix: str, metric_suffix: str) -> list:
            if self.df is None:
                return []
            matching_cols = []
            for col in self.df.columns:
                if col.startswith(f'{device_prefix}_') and metric_suffix in col:
                    matching_cols.append(col)
            return matching_cols

    # Define placeholder classes to avoid IDE warnings and runtime errors
    class DummyTool:
        def __init__(self, *args, **kwargs):
            pass
        def __call__(self, *args, **kwargs):
            return self
    
    # 使用可调用的占位符类
    CPUEBSCorrelationAnalyzer = DummyTool
    UnitConverter = DummyTool
    AdvancedChartGenerator = DummyTool

class PerformanceVisualizer(CSVDataProcessor):
    """Performance Visualizer - Based on unified CSV data processor"""
    
    def __init__(self, data_file, overhead_file=None):
        super().__init__()  # 初始化CSV数据处理器
        
        self.data_file = data_file
        self.overhead_file = overhead_file
        self.output_dir = os.getenv('REPORTS_DIR', os.path.dirname(data_file))
        
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # Using English labels system directly
        self.font_manager = None
            
        # 阈值配置 - 集成自await_util_analyzer
        self.await_thresholds = {
            'data_avg_await': 5.0,  # 默认I/O等待阈值 (ms)
            'data_r_await': 5.0,  # 默认读Latency阈值 (ms)
            'data_w_await': 10.0,  # 默认写Latency阈值 (ms)
            'normal': 10,      # Normal Threshold (ms)
            'warning': 20,     # Warning Threshold (ms)
            'critical': 50     # Critical Threshold (ms)
        }
        
        # ACCOUNTS设备阈值将在数据加载后动态添加
        self._accounts_thresholds_added = False
        
        # 从环境变量读取阈值配置
        thresholds = get_visualization_thresholds()
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
                self.print_field_info()  # Print field info for debugging
                
                # 动态添加ACCOUNTS设备阈值（仅在ACCOUNTS设备配置时）
                self._add_accounts_thresholds_if_configured()
                
            return success
            
        except Exception as e:
            print(f"❌ Data loading failed: {e}")
            return False
    
    def print_field_info(self):
        """打印字段信息用于调试"""
        pass
    
    def _add_accounts_thresholds_if_configured(self):
        """动态添加ACCOUNTS设备阈值（仅在ACCOUNTS设备配置时）"""
        if not self._accounts_thresholds_added and self._is_accounts_configured():
            self.await_thresholds.update({
                'accounts_avg_await': 5.0,  # ACCOUNTS I/O等待阈值 (ms)
                'accounts_r_await': 5.0,    # ACCOUNTS 读Latency阈值 (ms)
                'accounts_w_await': 10.0,   # ACCOUNTS 写Latency阈值 (ms)
            })
            self._accounts_thresholds_added = True
            print("✅ ACCOUNTS device threshold configuration added")
    
    def _is_accounts_configured(self):
        """检查 ACCOUNTS Device是否配置和可用
        
        根据 user_config.sh 的逻辑，ACCOUNTS Device是可选的：
        1. 检查环境变量配置
        2. 检查实际数据列是否存在
        3. 返回配置状态
        """
        # 方法1: 检查环境变量配置
        accounts_device = os.environ.get('ACCOUNTS_DEVICE')
        accounts_vol_type = os.environ.get('ACCOUNTS_VOL_TYPE')
        
        # 方法2: 检查数据列是否存在（更可靠的方法）
        accounts_cols = [col for col in self.df.columns if col.startswith('accounts_')]
        
        # 如果有数据列，说明 ACCOUNTS Device已配置且正在监控
        if accounts_cols:
            return True
            
        # 如果环境变量配置了但没有数据列，说明配置有问题
        if accounts_device and accounts_vol_type:
            print(f"⚠️  ACCOUNTS Device configured ({accounts_device}) but monitoring data not found")
            return False
            
        # 完全未配置，这是正常情况
        return False
    
    def _analyze_threshold_violations(self, data_series, thresholds, metric_name):
        """✅ Improved threshold violation analysis - integrated from await_util_analyzer"""
        # 数据有效性检查
        if data_series.empty:
            return {
                'total_points': 0,
                'warning_violations': 0,
                'critical_violations': 0,
                'warning_percentage': 0.0,  # 使用float类型保持一致性
                'critical_percentage': 0.0,  # 使用float类型保持一致性
                'max_value': 0.0,  # 使用float类型保持一致性
                'avg_value': 0.0,  # 使用float类型保持一致性
                'metric_name': metric_name,
                'error': 'Data is empty'
            }
        
        # ✅ 过滤NaN值
        valid_data = data_series.dropna()
        if len(valid_data) == 0:
            return {
                'total_points': len(data_series),
                'warning_violations': 0,
                'critical_violations': 0,
                'warning_percentage': 0.0,  # 使用float类型保持一致性
                'critical_percentage': 0.0,  # 使用float类型保持一致性
                'max_value': 0.0,  # 使用float类型保持一致性
                'avg_value': 0.0,  # 使用float类型保持一致性
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
        """✅ Improved performance overview chart generation"""
        fig, axes = plt.subplots(2, 2, figsize=(18, 12))
        fig.suptitle('System Performance Overview', fontsize=16, fontweight='bold')
        
        # ✅ 安全获取字段名 - 直接访问
        cpu_usage_col = 'cpu_usage' if 'cpu_usage' in self.df.columns else None
        cpu_iowait_col = 'cpu_iowait' if 'cpu_iowait' in self.df.columns else None
        mem_usage_col = 'memory_usage' if 'memory_usage' in self.df.columns else None
        
        # 查找DATA Device列
        data_iops_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_total_iops')]
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        
        if not data_iops_cols:
            print("❌ DATA Device data not found")
            return None
        
        data_iops_col = data_iops_cols[0]
        data_util_col = data_util_cols[0] if data_util_cols else None
        
        # ✅ CPU performance metrics (improved field handling)
        ax1 = axes[0, 0]
        if cpu_usage_col and cpu_iowait_col:
            # 检查数据有效性
            cpu_usage_data = self.df[cpu_usage_col].dropna()
            cpu_iowait_data = self.df[cpu_iowait_col].dropna()
            
            if len(cpu_usage_data) > 0 and len(cpu_iowait_data) > 0:
                # 原始数据
                ax1.plot(self.df['timestamp'], self.df[cpu_usage_col], color='blue', linewidth=1, alpha=0.6, label='CPU Usage (Raw)')
                ax1.plot(self.df['timestamp'], self.df[cpu_iowait_col], color='red', linewidth=1, alpha=0.6, label='CPU I/O Wait (Raw)')
                
                # ✅ 安全的移动平均计算
                if len(cpu_usage_data) >= 10:
                    cpu_smooth = self.df[cpu_usage_col].rolling(window=10, center=True, min_periods=1).mean()
                    ax1.plot(self.df['timestamp'], cpu_smooth, color='blue', linewidth=2, label='CPU Usage (Smoothed)')
                
                if len(cpu_iowait_data) >= 10:
                    iowait_smooth = self.df[cpu_iowait_col].rolling(window=10, center=True, min_periods=1).mean()
                    ax1.plot(self.df['timestamp'], iowait_smooth, color='red', linewidth=2, label='CPU I/O Wait (Smoothed)')
                
                ax1.set_title(f'{LABELS["cpu_usage"]} (with Moving Average)')
                ax1.set_ylabel('Usage (%)')
                ax1.legend()
                ax1.grid(True, alpha=0.3)
            else:
                ax1.text(0.5, 0.5, 'CPUData Not Available', ha='center', va='center', transform=ax1.transAxes)
                ax1.set_title(f'{LABELS["cpu_usage"]} (Data Not Available)')
        else:
            missing_fields = []
            if not cpu_usage_col:
                missing_fields.append('cpu_usage')
            if not cpu_iowait_col:
                missing_fields.append('cpu_iowait')
            ax1.text(0.5, 0.5, f'Missing Fields: {", ".join(missing_fields)}', ha='center', va='center', transform=ax1.transAxes)
            ax1.set_title(f'{LABELS["cpu_usage"]} (Field Missing)')
        
        # ✅ DATA DeviceIOPS
        ax2 = axes[0, 1]
        iops_data = self.df[data_iops_col].dropna()
        if len(iops_data) > 0:
            ax2.plot(self.df['timestamp'], self.df[data_iops_col], color='green', linewidth=2, label='DATA IOPS')
            ax2.set_title('DATA DeviceIOPS')
            ax2.set_ylabel('IOPS')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        else:
            ax2.text(0.5, 0.5, 'DATA IOPSData Not Available', ha='center', va='center', transform=ax2.transAxes)
            ax2.set_title('DATA DeviceIOPS (Data Not Available)')
        
        # ✅ Memory Usage
        ax3 = axes[1, 0]
        if mem_usage_col:
            mem_data = self.df[mem_usage_col].dropna()
            if len(mem_data) > 0:
                ax3.plot(self.df['timestamp'], self.df[mem_usage_col], color='purple', linewidth=2, label='Memory Usage')
                ax3.set_title('Memory Usage')
                ax3.set_ylabel('Usage (%)')
                ax3.legend()
                ax3.grid(True, alpha=0.3)
            else:
                ax3.text(0.5, 0.5, 'Memory Data Not Available', ha='center', va='center', transform=ax3.transAxes)
                ax3.set_title('Memory Usage (Data Not Available)')
        else:
            ax3.text(0.5, 0.5, 'Memory Usage Field Missing', ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('Memory Usage (Field Missing)')
        
        # ✅ Device Utilization
        ax4 = axes[1, 1]
        if data_util_col:
            util_data = self.df[data_util_col].dropna()
            if len(util_data) > 0:
                ax4.plot(self.df['timestamp'], self.df[data_util_col], color='orange', linewidth=2, label='DATA Device iostat %util')
                thresholds = get_visualization_thresholds()
                ax4.axhline(y=thresholds['io_warning'], color='red', linestyle='--', alpha=0.7, label=f'{thresholds["io_warning"]}% Warning Line')
                ax4.set_title('Device iostat %util')
                ax4.set_ylabel('iostat %util (%)')
                ax4.legend()
                ax4.grid(True, alpha=0.3)
            else:
                ax4.text(0.5, 0.5, 'Device iostat %util Data Not Available', ha='center', va='center', transform=ax4.transAxes)
                ax4.set_title('Device iostat %util (Data Not Available)')
        else:
            ax4.text(0.5, 0.5, 'Device Utilization Field Missing', ha='center', va='center', transform=ax4.transAxes)
            ax4.set_title('Device Utilization (Field Missing)')
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'performance_overview.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 {LABELS['performance_analysis']} overview saved: {output_file}")
        
        return output_file
    
    def create_correlation_visualization_chart(self):
        """✅ 改进的CPU-EBS Performance Correlation Analysis"""
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('CPU-EBS Performance Correlation Analysis', fontsize=16, fontweight='bold')
        
        # ✅ 安全获取相关字段
        cpu_iowait_col = 'cpu_iowait' if 'cpu_iowait' in self.df.columns else None
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        data_await_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_avg_await')]
        data_aqu_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_aqu_sz')]
        
        # ✅ 改进的字段存在性检查
        missing_fields = []
        if not cpu_iowait_col:
            missing_fields.append('cpu_iowait')
        if not data_util_cols:
            missing_fields.append('data_util')
        if not data_await_cols:
            missing_fields.append('data_avg_await')
        if not data_aqu_cols:
            missing_fields.append('data_aqu_sz')
        
        if missing_fields:
            print(f"⚠️  Missing fields for correlation analysis: {', '.join(missing_fields)}")
            # Display error information in chart
            for i, ax in enumerate(axes.flat):
                ax.text(0.5, 0.5, f'Missing Fields:\n{chr(10).join(missing_fields)}', 
                       ha='center', va='center', transform=ax.transAxes, fontsize=12)
                ax.set_title(f'{LABELS["correlation_analysis"]} {i+1} (Field Missing)')
            plt.tight_layout()
            output_file = os.path.join(self.output_dir, 'cpu_ebs_correlation_visualization.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            return output_file
        
        data_util_col = data_util_cols[0]
        data_await_col = data_await_cols[0]
        data_aqu_col = data_aqu_cols[0]
        
        from scipy.stats import pearsonr
        
        # ✅ Safe correlation analysis function
        def safe_correlation_analysis(x_data, y_data, ax, xlabel, ylabel, title_prefix):
            """Safe correlation analysis and visualization"""
            try:
                # 数据有效性检查
                if x_data.empty or y_data.empty:
                    ax.text(0.5, 0.5, 'Data is empty', ha='center', va='center', transform=ax.transAxes)
                    ax.set_title(f'{title_prefix}\nData Not Available')
                    return
                
                # 移除NaN值并对齐数据
                combined_data = pd.concat([x_data, y_data], axis=1).dropna()
                if len(combined_data) < 10:
                    ax.text(0.5, 0.5, f'Insufficient valid data points\n(only {len(combined_data)} points)', 
                           ha='center', va='center', transform=ax.transAxes)
                    ax.set_title(f'{title_prefix}\nInsufficient Data')
                    return
                
                x_clean = combined_data.iloc[:, 0]
                y_clean = combined_data.iloc[:, 1]
                
                # 绘制散点图
                ax.scatter(x_clean, y_clean, alpha=0.6, s=30)
                
                # ✅ 安全的回归线拟合
                try:
                    z = np.polyfit(x_clean, y_clean, 1)
                    p = np.poly1d(z)
                    ax.plot(x_clean, p(x_clean), "r--", alpha=0.8, linewidth=2)
                except np.linalg.LinAlgError:
                    print(f"⚠️  {title_prefix}: Regression line fitting warning - insufficient data linear correlation")
                except Exception as e:
                    print(f"⚠️  {title_prefix}: Regression line fitting failed: {e}")
                
                # ✅ 安全的相关性计算
                try:
                    corr, p_value = pearsonr(x_clean, y_clean)
                    if np.isnan(corr):
                        corr_text = "Correlation: NaN"
                    else:
                        significance = "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else ""
                        corr_text = f'Correlation: {corr:.3f}{significance}\n(n={len(x_clean)})'
                except Exception as e:
                    corr_text = f"Calculation failed: {str(e)[:20]}"
                
                ax.set_xlabel(xlabel)
                ax.set_ylabel(ylabel)
                ax.set_title(f'{title_prefix}\n{corr_text}')
                ax.grid(True, alpha=0.3)
                
            except Exception as e:
                ax.text(0.5, 0.5, f'Analysis Failed:\n{str(e)[:50]}', ha='center', va='center', transform=ax.transAxes)
                ax.set_title(f'{title_prefix}\nAnalysis Failed')
        
        # Execute various correlation analyses
        safe_correlation_analysis(
            self.df[cpu_iowait_col], self.df[data_util_col], axes[0, 0],
            'CPU I/O Wait (%)', 'Device Utilization (%)', 'CPU I/O Wait vs Device Utilization'
        )
        
        safe_correlation_analysis(
            self.df[cpu_iowait_col], self.df[data_await_col], axes[0, 1],
            'CPU I/O Wait (%)', 'I/O Latency (ms)', 'CPU I/O Wait vs I/O Latency'
        )
        
        safe_correlation_analysis(
            self.df[cpu_iowait_col], self.df[data_aqu_col], axes[1, 0],
            'CPU I/O Wait (%)', 'I/O Queue Length', 'CPU I/O Wait vs I/O Queue Length'
        )
        
        # ✅ Time序列对比
        ax4 = axes[1, 1]
        try:
            cpu_data = self.df[cpu_iowait_col].dropna()
            util_data = self.df[data_util_col].dropna()
            
            if len(cpu_data) > 0 and len(util_data) > 0:
                ax4_twin = ax4.twinx()
                
                ax4.plot(self.df['timestamp'], self.df[cpu_iowait_col], color='blue', linewidth=2, label='CPU I/O Wait')
                ax4_twin.plot(self.df['timestamp'], self.df[data_util_col], color='red', linewidth=2, linestyle='--', alpha=0.7, label='Device Utilization')
                
                ax4.set_xlabel('Time')
                ax4.set_ylabel('CPU I/O Wait (%)', color='blue')
                ax4_twin.set_ylabel('Device Utilization (%)', color='red')
                ax4.set_title('CPU I/O Wait vs Device Utilization Time Series')
                ax4.grid(True, alpha=0.3)
            else:
                ax4.text(0.5, 0.5, 'Time Series Data Not Available', ha='center', va='center', transform=ax4.transAxes)
                ax4.set_title('Time Series Comparison (Data Not Available)')
        except Exception as e:
            ax4.text(0.5, 0.5, f'Time series analysis failed:\n{str(e)[:50]}', ha='center', va='center', transform=ax4.transAxes)
            ax4.set_title('Time Series Comparison (Analysis Failed)')
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'cpu_ebs_correlation_visualization.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 CPU-EBS correlation visualization saved: {output_file}")
        
        return output_file
    
    def create_device_comparison_chart(self):
        """Create Device comparison chart (DATA vs ACCOUNTS) - optimized version
        
        Dynamically adjust chart content based on ACCOUNTS Device configuration status:
        - If ACCOUNTS not configured: only show DATA Device analysis
        - If ACCOUNTS configured: show DATA vs ACCOUNTS comparison
        """
        # 检查 ACCOUNTS Device配置状态
        accounts_configured = self._is_accounts_configured()
        
        fig, axes = plt.subplots(2, 1, figsize=(15, 10))
        
        # 根据配置状态设置标题
        if accounts_configured:
            fig.suptitle('Device Performance Comparison Analysis (DATA vs ACCOUNTS)', fontsize=16, fontweight='bold')
        else:
            fig.suptitle('Device Performance Analysis (DATA)', fontsize=16, fontweight='bold')
        
        # 查找Device列
        data_cols = [col for col in self.df.columns if col.startswith('data_')]
        accounts_cols = [col for col in self.df.columns if col.startswith('accounts_')] if accounts_configured else []
        
        if not data_cols:
            print("❌ DATA Device data not found")
            return None
        
        # 上图：IOPS对比
        ax1 = axes[0]
        data_iops_col = [col for col in data_cols if col.endswith('_total_iops')]
        if data_iops_col:
            ax1.plot(self.df['timestamp'], self.df[data_iops_col[0]], 
                    label='DATA IOPS', linewidth=2, color='blue')
        
        # 只有在 ACCOUNTS 配置时才处理 ACCOUNTS 数据
        if accounts_configured and accounts_cols:
            accounts_iops_col = [col for col in accounts_cols if col.endswith('_total_iops')]
            if accounts_iops_col:
                ax1.plot(self.df['timestamp'], self.df[accounts_iops_col[0]], 
                        label='ACCOUNTS IOPS', linewidth=2, color='green')
        
        ax1.set_title('Device IOPS Comparison' if accounts_configured else 'DATA Device IOPS')
        ax1.set_ylabel('IOPS')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 下图：利用率对比
        ax2 = axes[1]
        data_util_col = [col for col in data_cols if col.endswith('_util')]
        if data_util_col:
            ax2.plot(self.df['timestamp'], self.df[data_util_col[0]], 
                    label='DATA Utilization', linewidth=2, color='blue')
        
        # 只有在 ACCOUNTS 配置时才处理 ACCOUNTS 数据
        if accounts_configured and accounts_cols:
            accounts_util_col = [col for col in accounts_cols if col.endswith('_util')]
            if accounts_util_col:
                ax2.plot(self.df['timestamp'], self.df[accounts_util_col[0]], 
                        label='ACCOUNTS Utilization', linewidth=2, color='green')
        
        thresholds = get_visualization_thresholds()
        ax2.axhline(y=thresholds['io_warning'], color='orange', linestyle='--', alpha=0.7, label=f'{thresholds["io_warning"]}% Warning Line')
        ax2.axhline(y=thresholds['critical'], color='red', linestyle='--', alpha=0.7, label=f'{thresholds["critical"]}% Critical Line')
        
        ax2.set_title('Device Utilization Comparison' if accounts_configured else 'DATA Device Utilization')
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Utilization (%)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'device_performance_comparison.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 Device performance comparison chart saved: {output_file}")
        
        return output_file

    def create_await_threshold_analysis_chart(self):
        """Create await latency threshold analysis chart - optimized version
        
        Dynamically adjust analysis content based on ACCOUNTS Device configuration status:
        - If ACCOUNTS not configured: only analyze DATA Device
        - If ACCOUNTS configured: analyze DATA and ACCOUNTS Device
        """
        # 检查 ACCOUNTS Device配置状态
        accounts_configured = self._is_accounts_configured()
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 根据配置状态设置标题
        if accounts_configured:
            fig.suptitle('I/O Latency (await) Threshold Analysis - DATA & ACCOUNTS', fontsize=16, fontweight='bold')
        else:
            fig.suptitle('I/O Latency (await) Threshold Analysis - DATA', fontsize=16, fontweight='bold')
        
        # 获取await相关列
        data_await_cols = [col for col in self.df.columns if col.startswith('data_') and 'avg_await' in col]
        accounts_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and 'avg_await' in col] if accounts_configured else []
        
        # Average wait time trends
        ax1 = axes[0, 0]
        ax1.set_title('Average I/O Wait Time Trends')
        
        threshold_violations = {}
        
        # 处理dataDevice
        if data_await_cols:
            col = data_await_cols[0]
            ax1.plot(self.df['timestamp'], self.df[col], 
                    label='DATA Average Wait Time', linewidth=2)
            
            # Analyze threshold violations
            violations = self._analyze_threshold_violations(
                self.df[col], self.await_thresholds, 'data_avg_await'
            )
            threshold_violations['data_avg_await'] = violations
        
        # 只有在 ACCOUNTS 配置时才处理 ACCOUNTS 数据
        if accounts_configured and accounts_await_cols:
            col = accounts_await_cols[0]
            ax1.plot(self.df['timestamp'], self.df[col], 
                    label='ACCOUNTS Average Wait Time', linewidth=2)
            
            # Analyze threshold violations
            violations = self._analyze_threshold_violations(
                self.df[col], self.await_thresholds, 'accounts_avg_await'
            )
            threshold_violations['accounts_avg_await'] = violations
        elif not accounts_configured:
            # 添加说明文本
            ax1.text(0.02, 0.98, 'ACCOUNTS Device Not Configured', transform=ax1.transAxes, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        ax1.axhline(y=self.await_thresholds['warning'], color='orange', 
                   linestyle='--', alpha=0.7, label='Warning Threshold (20ms)')
        ax1.axhline(y=self.await_thresholds['critical'], color='red', 
                   linestyle='--', alpha=0.7, label='Critical Threshold (50ms)')
        ax1.set_ylabel('Wait Time (ms)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 读等待Time
        ax2 = axes[0, 1]
        ax2.set_title('Read Operation Wait Time')
        
        # 获取读等待Time列
        data_r_await_cols = [col for col in self.df.columns if col.startswith('data_') and 'r_await' in col]
        accounts_r_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and 'r_await' in col] if accounts_configured else []
        
        if data_r_await_cols:
            col = data_r_await_cols[0]
            ax2.plot(self.df['timestamp'], self.df[col], 
                    label='DATA Read Wait Time', linewidth=2)
        
        if accounts_configured and accounts_r_await_cols:
            col = accounts_r_await_cols[0]
            ax2.plot(self.df['timestamp'], self.df[col], 
                    label='ACCOUNTS Read Wait Time', linewidth=2)
        elif not accounts_configured:
            ax2.text(0.02, 0.98, 'ACCOUNTS Device Not Configured', transform=ax2.transAxes, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        ax2.axhline(y=self.await_thresholds['warning'], color='orange', 
                   linestyle='--', alpha=0.7)
        ax2.axhline(y=self.await_thresholds['critical'], color='red', 
                   linestyle='--', alpha=0.7)
        ax2.set_ylabel('Read Wait Time (ms)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 写等待Time
        ax3 = axes[1, 0]
        ax3.set_title('Write Operation Wait Time')
        
        # 获取写等待Time列
        data_w_await_cols = [col for col in self.df.columns if col.startswith('data_') and 'w_await' in col]
        accounts_w_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and 'w_await' in col] if accounts_configured else []
        
        if data_w_await_cols:
            col = data_w_await_cols[0]
            ax3.plot(self.df['timestamp'], self.df[col], 
                    label='DATA Write Wait Time', linewidth=2)
        
        if accounts_configured and accounts_w_await_cols:
            col = accounts_w_await_cols[0]
            ax3.plot(self.df['timestamp'], self.df[col], 
                    label='ACCOUNTS Write Wait Time', linewidth=2)
        elif not accounts_configured:
            ax3.text(0.02, 0.98, 'ACCOUNTS Device Not Configured', transform=ax3.transAxes, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        ax3.axhline(y=self.await_thresholds['warning'], color='orange', 
                   linestyle='--', alpha=0.7)
        ax3.axhline(y=self.await_thresholds['critical'], color='red', 
                   linestyle='--', alpha=0.7)
        ax3.set_ylabel('Write Wait Time (ms)')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 阈值违规统计
        ax4 = axes[1, 1]
        ax4.set_title('Threshold Violation Statistics')
        
        if threshold_violations:
            devices = list(threshold_violations.keys())
            warning_pcts = [threshold_violations[dev]['warning_percentage'] for dev in devices]
            critical_pcts = [threshold_violations[dev]['critical_percentage'] for dev in devices]
            
            x = np.arange(len(devices))
            width = 0.35
            
            ax4.bar(x - width/2, warning_pcts, width, label='Warning Violations %', color='orange', alpha=0.7)
            ax4.bar(x + width/2, critical_pcts, width, label='Critical Violations %', color='red', alpha=0.7)
            
            ax4.set_xlabel('Device')
            ax4.set_ylabel('Violation Percentage (%)')
            ax4.set_xticks(x)
            ax4.set_xticklabels([dev.replace('_avg_await', '') for dev in devices])
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        else:
            ax4.text(0.5, 0.5, 'No Threshold Violation Data', ha='center', va='center', transform=ax4.transAxes)
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'await_threshold_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 I/O Latency threshold analysis chart saved: {output_file}")
        
        return output_file, threshold_violations

    def create_util_threshold_analysis_chart(self):
        """Create utilization threshold analysis chart - optimized version
        
        Dynamically adjust analysis content based on ACCOUNTS Device configuration status:
        - If ACCOUNTS not configured: only analyze DATA Device
        - If ACCOUNTS configured: analyze DATA and ACCOUNTS Device
        """
        # 检查 ACCOUNTS Device配置状态
        accounts_configured = self._is_accounts_configured()
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 根据配置状态设置标题
        if accounts_configured:
            fig.suptitle('Device Utilization Threshold Analysis - DATA & ACCOUNTS', fontsize=16, fontweight='bold')
        else:
            fig.suptitle('Device Utilization Threshold Analysis - DATA', fontsize=16, fontweight='bold')
        
        # 获取利用率相关列
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and '_util' in col]
        accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and '_util' in col] if accounts_configured else []
        
        # 利用率Time序列
        ax1 = axes[0, 0]
        ax1.set_title('Device Utilization Time Series')
        
        threshold_violations = {}
        
        # 处理dataDevice
        if data_util_cols:
            col = data_util_cols[0]
            ax1.plot(self.df['timestamp'], self.df[col], 
                    label='DATA Utilization', linewidth=2)
            
            # Analyze threshold violations
            violations = self._analyze_threshold_violations(
                self.df[col], self.util_thresholds, 'data_util'
            )
            threshold_violations['data_util'] = violations
        
        # 只有在 ACCOUNTS 配置时才处理 ACCOUNTS 数据
        if accounts_configured and accounts_util_cols:
            col = accounts_util_cols[0]
            ax1.plot(self.df['timestamp'], self.df[col], 
                    label='ACCOUNTS Utilization', linewidth=2)
            
            # Analyze threshold violations
            violations = self._analyze_threshold_violations(
                self.df[col], self.util_thresholds, 'accounts_util'
            )
            threshold_violations['accounts_util'] = violations
        elif not accounts_configured:
            # 添加说明文本
            ax1.text(0.02, 0.98, 'ACCOUNTS Device Not Configured', transform=ax1.transAxes, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        ax1.axhline(y=self.util_thresholds['warning'], color='orange', 
                   linestyle='--', alpha=0.7, label=f'Warning Threshold ({self.util_thresholds["warning"]}%)')
        ax1.axhline(y=self.util_thresholds['critical'], color='red', 
                   linestyle='--', alpha=0.7, label=f'Critical Threshold ({self.util_thresholds["critical"]}%)')
        ax1.set_ylabel('Utilization (%)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 利用率分布
        ax2 = axes[0, 1]
        ax2.set_title('Utilization Distribution')
        
        # 处理dataDevice分布
        if data_util_cols:
            col = data_util_cols[0]
            ax2.hist(self.df[col], bins=30, alpha=0.7, 
                    label='DATA Utilization Distribution')
        
        # 只有在 ACCOUNTS 配置时才处理 ACCOUNTS 数据
        if accounts_configured and accounts_util_cols:
            col = accounts_util_cols[0]
            ax2.hist(self.df[col], bins=30, alpha=0.7, 
                    label='ACCOUNTS Utilization Distribution')
        elif not accounts_configured:
            ax2.text(0.02, 0.98, 'ACCOUNTS Device Not Configured', transform=ax2.transAxes, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        ax2.axvline(x=self.util_thresholds['warning'], color='orange', 
                   linestyle='--', alpha=0.7)
        ax2.axvline(x=self.util_thresholds['critical'], color='red', 
                   linestyle='--', alpha=0.7)
        ax2.set_xlabel('Utilization (%)')
        ax2.set_ylabel('Frequency')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 高利用率Time统计
        ax3 = axes[1, 0]
        ax3.set_title('High Utilization Time Statistics')
        
        if threshold_violations:
            devices = list(threshold_violations.keys())
            warning_times = [threshold_violations[dev]['warning_violations'] for dev in devices]
            critical_times = [threshold_violations[dev]['critical_violations'] for dev in devices]
            
            x = np.arange(len(devices))
            width = 0.35
            
            ax3.bar(x - width/2, warning_times, width, label='Warning Count', color='orange', alpha=0.7)
            ax3.bar(x + width/2, critical_times, width, label='Critical Count', color='red', alpha=0.7)
            
            ax3.set_xlabel('Device')
            ax3.set_ylabel('Violation Count')
            ax3.set_xticks(x)
            ax3.set_xticklabels([dev.replace('_util', '') for dev in devices])
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        else:
            ax3.text(0.5, 0.5, 'No High Utilization Violations', ha='center', va='center', transform=ax3.transAxes)
        
        # 阈值违规百分比
        ax4 = axes[1, 1]
        ax4.set_title('Threshold Violation Percentage')
        
        if threshold_violations:
            devices = list(threshold_violations.keys())
            warning_pcts = [threshold_violations[dev]['warning_percentage'] for dev in devices]
            critical_pcts = [threshold_violations[dev]['critical_percentage'] for dev in devices]
            
            x = np.arange(len(devices))
            width = 0.35
            
            ax4.bar(x - width/2, warning_pcts, width, label='Warning Violations %', color='orange', alpha=0.7)
            ax4.bar(x + width/2, critical_pcts, width, label='Critical Violations %', color='red', alpha=0.7)
            
            ax4.set_xlabel('Device')
            ax4.set_ylabel('Violation Percentage (%)')
            ax4.set_xticks(x)
            ax4.set_xticklabels([dev.replace('_util', '') for dev in devices])
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        else:
            ax4.text(0.5, 0.5, 'No Threshold Violation Data', ha='center', va='center', transform=ax4.transAxes)
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'util_threshold_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 Device Utilization threshold analysis chart saved: {output_file}")
        
        return output_file, threshold_violations

    def create_monitoring_overhead_analysis_chart(self):
        """Create monitoring overhead analysis chart"""
        if not self.overhead_file or not os.path.exists(self.overhead_file):
            print("⚠️ Monitoring overhead data file does not exist, skipping overhead analysis chart")
            return None, {}
        
        try:
            overhead_df = pd.read_csv(self.overhead_file)
            if 'timestamp' in overhead_df.columns:
                overhead_df['timestamp'] = pd.to_datetime(overhead_df['timestamp'])
        except Exception as e:
            print(f"❌ Monitoring overhead data loading failed: {e}")
            return None, {}
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Monitoring Overhead Analysis', fontsize=16, fontweight='bold')
        
        # 1. Resource consumption comparison (total resources vs node resources vs monitoring overhead)
        ax1 = axes[0, 0]
        ax1.set_title('System Resource Consumption Comparison')
        
        if all(col in self.df.columns for col in ['cpu_usage', 'mem_usage']):
            # Calculate average resource usage
            total_cpu = self.df['cpu_usage'].mean()
            total_mem = self.df['mem_usage'].mean()
            
            if all(col in overhead_df.columns for col in ['monitoring_cpu_percent', 'monitoring_mem_percent']):
                monitor_cpu = overhead_df['monitoring_cpu_percent'].mean()
                monitor_mem = overhead_df['monitoring_mem_percent'].mean()
                
                node_cpu = max(0, total_cpu - monitor_cpu)
                node_mem = max(0, total_mem - monitor_mem)
                
                categories = ['CPU Usage (%)', 'Memory Usage (%)']
                total_values = [total_cpu, total_mem]
                node_values = [node_cpu, node_mem]
                monitor_values = [monitor_cpu, monitor_mem]
                
                x = np.arange(len(categories))
                width = 0.25
                
                ax1.bar(x - width, total_values, width, label='Total System Resources', alpha=0.8)
                ax1.bar(x, node_values, width, label='Blockchain Node', alpha=0.8)
                ax1.bar(x + width, monitor_values, width, label='Monitoring Overhead', alpha=0.8)
                
                ax1.set_xticks(x)
                ax1.set_xticklabels(categories)
                ax1.legend()
                ax1.grid(True, alpha=0.3)
        
        # 2. Monitoring overhead trends
        ax2 = axes[0, 1]
        ax2.set_title('Monitoring Overhead Time Trends')
        
        if 'timestamp' in overhead_df.columns and 'monitoring_cpu_percent' in overhead_df.columns:
            ax2.plot(overhead_df['timestamp'], overhead_df['monitoring_cpu_percent'], 
                    label='CPU Overhead', linewidth=2)
            if 'monitoring_mem_percent' in overhead_df.columns:
                ax2_mem = ax2.twinx()
                ax2_mem.plot(overhead_df['timestamp'], overhead_df['monitoring_mem_percent'], 
                           'r-', label='Memory Overhead', linewidth=2)
                ax2_mem.set_ylabel('Memory Overhead (%)', color='r')
                ax2_mem.tick_params(axis='y', labelcolor='r')
            
            ax2.set_ylabel('CPU Overhead (%)')
            ax2.legend(loc='upper left')
            ax2.grid(True, alpha=0.3)
        
        # 3. Monitoring process resource distribution
        ax3 = axes[1, 0]
        ax3.set_title('Monitoring Process Resource Distribution')
        
        # 如果有进程级别的数据
        process_cols = [col for col in overhead_df.columns if col.startswith('process_')]
        if process_cols:
            process_data = []
            process_names = []
            for col in process_cols[:5]:  # 显示前5个进程
                if overhead_df[col].sum() > 0:
                    process_data.append(overhead_df[col].mean())
                    process_names.append(col.replace('process_', '').replace('_cpu', ''))
            
            if process_data:
                ax3.pie(process_data, labels=process_names, autopct='%1.1f%%')
        
        # 4. 监控开销统计摘要
        ax4 = axes[1, 1]
        ax4.set_title('Monitoring Overhead Statistics Summary')
        ax4.axis('off')
        
        if all(col in overhead_df.columns for col in ['monitoring_cpu_percent', 'monitoring_mem_percent']):
            stats_text = f"""
Monitoring Overhead Statistics:

CPU Overhead:
  Average: {overhead_df['monitoring_cpu_percent'].mean():.2f}%
  Maximum: {overhead_df['monitoring_cpu_percent'].max():.2f}%
  Minimum: {overhead_df['monitoring_cpu_percent'].min():.2f}%

Memory Overhead:
  Average: {overhead_df['monitoring_mem_percent'].mean():.2f}%
  Maximum: {overhead_df['monitoring_mem_percent'].max():.2f}%
  Minimum: {overhead_df['monitoring_mem_percent'].min():.2f}%

Monitoring Efficiency:
  Data points: {len(overhead_df)}
  Monitoring duration: {(overhead_df['timestamp'].max() - overhead_df['timestamp'].min()).total_seconds():.0f}s
            """
            ax4.text(0.1, 0.9, stats_text, transform=ax4.transAxes, fontsize=10,
                    verticalalignment='top', fontfamily='monospace')
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'monitoring_overhead_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 Monitoring overhead analysis chart saved: {output_file}")
        
        # Return overhead analysis results
        overhead_analysis = {}
        if all(col in overhead_df.columns for col in ['monitoring_cpu_percent', 'monitoring_mem_percent']):
            overhead_analysis = {
                'avg_cpu_overhead': overhead_df['monitoring_cpu_percent'].mean(),
                'max_cpu_overhead': overhead_df['monitoring_cpu_percent'].max(),
                'avg_mem_overhead': overhead_df['monitoring_mem_percent'].mean(),
                'max_mem_overhead': overhead_df['monitoring_mem_percent'].max(),
                'total_data_points': len(overhead_df)
            }
        
        return output_file, overhead_analysis

    def generate_all_charts(self):
        print("🎨 Generating performance visualization charts...")
        
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
            print("🔗 Generating blockchain node analysis charts...")
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
            
            # Generate EBS professional analysis charts
            print("📊 Generating EBS professional analysis charts...")
            ebs_charts = self.generate_all_ebs_charts()
            if ebs_charts:
                chart_files.extend(ebs_charts)
                print(f"✅ Generated {len(ebs_charts)} EBS professional charts")
            
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
            
            # 3. EBS Latency trends
            data_await_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_avg_await')]
            if data_await_cols:
                ax3 = axes[1, 0]
                await_col = data_await_cols[0]
                
                ax3.plot(self.df['timestamp'], self.df[await_col], 
                        color='lightgreen', linewidth=1, alpha=0.5, label='EBS Latency (Raw)')
                
                await_smooth = self.df[await_col].rolling(window=window_size, center=True).mean()
                ax3.plot(self.df['timestamp'], await_smooth, 
                        color='green', linewidth=2, label=f'EBS Latency({window_size}-point smoothed)')
                
                ax3.set_title('EBS Latency Trends')
                ax3.set_ylabel('Latency (ms)')
                ax3.legend()
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
        
        try:
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('QPS Performance Trend Analysis', fontsize=16, fontweight='bold')
            
            # 查找QPS相关字段
            qps_cols = [col for col in self.df.columns if 'qps' in col.lower()]
            if not qps_cols:
                print("⚠️  QPS related fields not found")
                plt.close()
                return None
            
            # 1. QPSTime序列
            ax1 = axes[0, 0]
            for qps_col in qps_cols[:3]:  # 最多显示3个QPS指标
                ax1.plot(self.df['timestamp'], self.df[qps_col], label=qps_col, linewidth=2)
            ax1.set_title('QPS Time Series')
            ax1.set_ylabel('QPS')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 2. QPS分布直方图
            ax2 = axes[0, 1]
            for qps_col in qps_cols[:2]:
                qps_data = pd.to_numeric(self.df[qps_col].dropna(), errors='coerce')
                qps_data = qps_data.dropna()  # Remove any NaN values after conversion
                if len(qps_data) > 0:
                    ax2.hist(qps_data, alpha=0.7, label=qps_col, bins=30)
            ax2.set_title('QPS Distribution')
            ax2.set_xlabel('QPS')
            ax2.set_ylabel('Frequency')
            ax2.legend()
            
            # 3. QPS与CPU相关性
            ax3 = axes[1, 0]
            if 'cpu_usage' in self.df.columns and qps_cols:
                ax3.scatter(self.df['cpu_usage'], self.df[qps_cols[0]], alpha=0.6)
                ax3.set_title('QPS vs CPU Usage')
                ax3.set_xlabel('CPU Usage (%)')
                ax3.set_ylabel('QPS')
                ax3.grid(True, alpha=0.3)
            
            # 4. QPS统计摘要
            ax4 = axes[1, 1]
            ax4.axis('off')
            stats_text = "QPS Statistics Summary:\n\n"
            for qps_col in qps_cols[:3]:
                qps_data = self.df[qps_col].dropna()
                if len(qps_data) > 0:
                    stats_text += f"{qps_col}:\n"
                    stats_text += f"  Average: {qps_data.mean():.2f}\n"
                    stats_text += f"  Maximum: {qps_data.max():.2f}\n"
                    stats_text += f"  Minimum: {qps_data.min():.2f}\n\n"
            ax4.text(0.1, 0.9, stats_text, transform=ax4.transAxes, fontsize=10, verticalalignment='top')
            
            plt.tight_layout()
            
            # Save chart
            output_file = os.path.join(self.output_dir, 'qps_trend_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  ✅ QPS trend analysis chart: {os.path.basename(output_file)}")
            return output_file
            
        except Exception as e:
            print(f"❌ QPS trend analysis chart generation failed: {e}")
            return None

    def create_resource_efficiency_analysis_chart(self):
        """Resource efficiency analysis chart"""
        print("📊 Generating resource efficiency analysis charts...")
        
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
                ax1.pie(efficiency_counts, labels=efficiency_ranges, autopct='%1.1f%%')
                ax1.set_title('CPU Efficiency Distribution')
            
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
                ax2.pie(mem_counts, labels=mem_ranges, autopct='%1.1f%%')
                ax2.set_title('Memory Efficiency Distribution')
            
            # 3. I/O efficiency analysis
            ax3 = axes[1, 0]
            data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
            if data_util_cols:
                util_col = data_util_cols[0]
                util_data = self.df[util_col].dropna()
                ax3.hist(util_data, bins=20, alpha=0.7, color='green')
                ax3.axvline(util_data.mean(), color='red', linestyle='--', label=f'Average: {util_data.mean():.1f}%')
                ax3.set_title('I/O Utilization Distribution')
                ax3.set_xlabel('Utilization (%)')
                ax3.set_ylabel('Frequency')
                ax3.legend()
            
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
            ax4.text(0.1, 0.9, stats_text, transform=ax4.transAxes, fontsize=12, verticalalignment='top')
            
            plt.tight_layout()
            
            # 保存图表
            output_file = os.path.join(self.output_dir, 'resource_efficiency_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  ✅ Resource efficiency analysis chart: {os.path.basename(output_file)}")
            return output_file
            
        except Exception as e:
            print(f"❌ Resource efficiency analysis chart generation failed: {e}")
            return None

    def create_bottleneck_identification_chart(self):
        """Bottleneck identification analysis chart"""
        print("📊 Generating bottleneck identification analysis charts...")
        
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
            
            ax4.text(0.1, 0.9, summary_text, transform=ax4.transAxes, fontsize=10, verticalalignment='top')
            
            plt.tight_layout()
            
            # 保存图表
            output_file = os.path.join(self.output_dir, 'bottleneck_identification.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  ✅ Bottleneck identification analysis chart: {os.path.basename(output_file)}")
            return output_file
            
        except Exception as e:
            print(f"❌ Bottleneck identification analysis chart generation failed: {e}")
            return None

    # EBS委托方法 - 委托给EBS专用模块
    def generate_ebs_bottleneck_analysis(self):
        """委托给EBS专用模块"""
        try:
            from .ebs_chart_generator import EBSChartGenerator
        except ImportError:
            # 回退到绝对导入
            import sys
            import os
            sys.path.insert(0, os.path.dirname(__file__))
            from ebs_chart_generator import EBSChartGenerator
        
        try:
            ebs_generator = EBSChartGenerator(self.df, self.output_dir)
            return ebs_generator.generate_ebs_bottleneck_analysis()
        except Exception as e:
            print(f"⚠️ EBS瓶颈分析失败: {e}")
            return None
    
    def generate_ebs_time_series(self):
        """委托给EBS专用模块"""
        try:
            from .ebs_chart_generator import EBSChartGenerator
        except ImportError:
            # 回退到绝对导入
            import sys
            import os
            sys.path.insert(0, os.path.dirname(__file__))
            from ebs_chart_generator import EBSChartGenerator
        
        try:
            ebs_generator = EBSChartGenerator(self.df, self.output_dir)
            return ebs_generator.generate_ebs_time_series()
        except Exception as e:
            print(f"⚠️ EBS时间序列分析失败: {e}")
            return None
    
    def create_block_height_sync_chart(self):
        """生成区块高度同步状态时序图表"""
        print("📊 Generating block height synchronization chart...")
        
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
            
            # 创建图表
            fig, ax = plt.subplots(figsize=(14, 8))
            
            # 主曲线：区块高度差值
            ax.plot(timestamps, height_diff, 
                    color='#2E86AB', linewidth=2, 
                    label='Block Height Difference (Mainnet - Local)', alpha=0.8)
            
            # 阈值线
            threshold = 50  # BLOCK_HEIGHT_DIFF_THRESHOLD
            ax.axhline(y=threshold, color='#E74C3C', linestyle='--', 
                      linewidth=2, alpha=0.7, label=f'Threshold (+{threshold})')
            ax.axhline(y=-threshold, color='#E74C3C', linestyle='--', 
                      linewidth=2, alpha=0.7, label=f'Threshold (-{threshold})')
            
            # 异常区域标注
            anomaly_periods = self._identify_anomaly_periods(timestamps, data_loss)
            for i, (start_time, end_time) in enumerate(anomaly_periods):
                ax.axvspan(start_time, end_time, alpha=0.25, color='#E74C3C', 
                          label='Data Loss Period' if i == 0 else "")
            
            # 图表美化
            ax.set_title('🔗 Blockchain Node Synchronization Status', 
                        fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Time', fontsize=12)
            ax.set_ylabel('Block Height Difference', fontsize=12)
            ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
            ax.legend(loc='upper right', framealpha=0.9)
            
            # 时间轴格式化
            if len(timestamps) > 0:
                ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%H:%M:%S'))
                plt.xticks(rotation=45)
            
            # 添加统计信息文本框
            stats_text = self._generate_sync_stats_text(height_diff, data_loss)
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                   verticalalignment='top', bbox=dict(boxstyle='round', 
                   facecolor='wheat', alpha=0.8), fontsize=10)
            
            plt.tight_layout()
            
            # 保存文件
            output_file = os.path.join(self.output_dir, 'block_height_sync_chart.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            plt.close()
            
            print(f"✅ Block height sync chart saved: {output_file}")
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

    def generate_all_ebs_charts(self):
        """生成所有EBS图表"""
        try:
            from .ebs_chart_generator import EBSChartGenerator
        except ImportError:
            # 回退到绝对导入
            import sys
            import os
            sys.path.insert(0, os.path.dirname(__file__))
            from ebs_chart_generator import EBSChartGenerator
        
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
