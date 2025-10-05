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
    # 获取EBS延迟阈值 (正确的I/O延迟基准)
    ebs_latency_threshold = int(os.getenv('BOTTLENECK_EBS_LATENCY_THRESHOLD', 50))
    ebs_util_threshold = int(os.getenv('BOTTLENECK_EBS_UTIL_THRESHOLD', 90))
    
    return {
        'warning': int(os.getenv('BOTTLENECK_CPU_THRESHOLD', 85)),           # CPU阈值 (%)
        'critical': ebs_util_threshold,                                      # EBS利用率阈值 (%)
        'io_warning': int(ebs_latency_threshold * 0.4),                     # I/O延迟警告: 50ms * 0.4 = 20ms
        'io_critical': ebs_latency_threshold,                               # I/O延迟临界: 50ms
        'memory': int(os.getenv('BOTTLENECK_MEMORY_THRESHOLD', 90)),        # 内存阈值 (%)
        'network': int(os.getenv('BOTTLENECK_NETWORK_THRESHOLD', 80))       # 网络阈值 (%)
    }

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
    import os
    
    # 动态检测配置路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_dir = os.path.join(current_dir, '..', 'config')
    
    # 配置文件列表 - 加载所有4个配置文件
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
    """统一的文本格式化函数"""
    lines = [f"Analysis Summary ({device_info}):", ""]
    
    # DATA设备统计
    lines.extend([
        "DATA Device:",
        f"  Mean: {data_stats['mean']:.2f}{data_stats['unit']}",
        f"  Max: {data_stats['max']:.2f}{data_stats['unit']}",
        f"  Violations: {data_stats['violations']}",
        ""
    ])
    
    # ACCOUNTS设备统计
    if accounts_stats:
        lines.extend([
            "ACCOUNTS Device:",
            f"  Mean: {accounts_stats['mean']:.2f}{accounts_stats['unit']}",
            f"  Max: {accounts_stats['max']:.2f}{accounts_stats['unit']}",
            f"  Violations: {accounts_stats['violations']}"
        ])
    else:
        lines.append("ACCOUNTS Device: Not Configured")
    
    return "\n".join(lines)

def add_text_summary(ax, summary_text, title):
    """统一的文本摘要添加函数"""
    ax.axis('off')
    ax.text(0.05, 0.95, summary_text, transform=ax.transAxes, 
           fontsize=11, verticalalignment='top', fontfamily='monospace',
           bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
    ax.set_title(title)

def create_chart_title(base_title, accounts_configured):
    """统一的图表标题创建函数"""
    if accounts_configured:
        return f"{base_title} - DATA & ACCOUNTS Devices"
    else:
        return f"{base_title} - DATA Device Only"

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
        self.overhead_file = overhead_file or self._find_monitoring_overhead_file() or os.getenv('MONITORING_OVERHEAD_LOG')
        self.output_dir = os.getenv('REPORTS_DIR', os.path.dirname(data_file))
        
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # Using English labels system directly
        self.font_manager = None
    
    def _find_monitoring_overhead_file(self):
        """智能查找监控开销文件 - 与report_generator.py保持一致"""
        try:
            import glob
            
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
            if accounts_configured and accounts_await_cols:
                accounts_await_col = accounts_await_cols[0]
                axes[0, 1].scatter(self.df[cpu_iowait_col], self.df[accounts_await_col], 
                                 alpha=0.6, s=20, color='purple', label='ACCOUNTS Device')
            
            # Calculate correlation
            data_corr = self.df[cpu_iowait_col].corr(self.df[data_await_col])
            corr_text = f'DATA Correlation: {data_corr:.3f}'
            
            if accounts_configured and accounts_await_cols:
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
        """Device Performance Comparison Chart - Enhanced Dual Device Support"""
        
        # Device configuration detection
        accounts_configured = self._is_accounts_configured()
        
        fig, axes = plt.subplots(2, 1, figsize=(15, 10))
        
        # Enhanced dynamic title
        if accounts_configured:
            fig.suptitle('Device Performance Comparison Analysis (DATA vs ACCOUNTS)', fontsize=16, fontweight='bold')
        else:
            fig.suptitle('Device Performance Analysis (DATA Device Only)', fontsize=16, fontweight='bold')
        
        # Find device columns with correct field names
        data_iops_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_total_iops')]
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        
        accounts_iops_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_total_iops')] if accounts_configured else []
        accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')] if accounts_configured else []
        
        if not data_iops_cols and not data_util_cols:
            print("❌ DATA Device data not found")
            return None
        
        # Upper chart: IOPS comparison with enhanced font labels
        ax1 = axes[0]
        if data_iops_cols:
            ax1.plot(self.df['timestamp'], self.df[data_iops_cols[0]], 
                    label='DATA Device Total IOPS', linewidth=2, color='blue')
        
        if accounts_configured and accounts_iops_cols:
            ax1.plot(self.df['timestamp'], self.df[accounts_iops_cols[0]], 
                    label='ACCOUNTS Device Total IOPS', linewidth=2, color='orange')
        
        ax1.set_title('Device IOPS Performance Comparison' if accounts_configured else 'DATA Device IOPS Performance')
        ax1.set_ylabel('Total IOPS')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Lower chart: Utilization comparison with enhanced font labels
        ax2 = axes[1]
        if data_util_cols:
            ax2.plot(self.df['timestamp'], self.df[data_util_cols[0]], 
                    label='DATA Device Utilization', linewidth=2, color='blue')
        
        if accounts_configured and accounts_util_cols:
            ax2.plot(self.df['timestamp'], self.df[accounts_util_cols[0]], 
                    label='ACCOUNTS Device Utilization', linewidth=2, color='orange')
        
        # Enhanced threshold lines with clear labels
        thresholds = get_visualization_thresholds()
        ax2.axhline(y=thresholds['warning'], color='orange', linestyle='--', alpha=0.7, 
                   label=f'Warning Threshold: {thresholds["warning"]}%')
        ax2.axhline(y=thresholds['critical'], color='red', linestyle='--', alpha=0.7, 
                   label=f'Critical Threshold: {thresholds["critical"]}%')
        
        ax2.set_title('Device Utilization Performance Comparison' if accounts_configured else 'DATA Device Utilization Performance')
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Utilization (%)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Adjust layout with proper spacing
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        
        output_file = os.path.join(self.output_dir, 'device_performance_comparison.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        print(f"✅ Device performance comparison chart saved: {output_file} ({device_info} devices)")
        
        return output_file

    def create_await_threshold_analysis_chart(self):
        """I/O Latency Threshold Analysis Chart - Dual Device Support"""
        
        # Device configuration detection
        accounts_configured = self._is_accounts_configured()
        
        # Dynamic title
        title = 'I/O Latency Threshold Analysis - DATA & ACCOUNTS Devices' if accounts_configured else 'I/O Latency Threshold Analysis - DATA Device Only'
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        fig.suptitle(title, fontsize=16, fontweight='bold')
        
        # Get threshold values
        thresholds = get_visualization_thresholds()
        
        # Find DATA device await columns
        data_await_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_avg_await')]
        
        if not data_await_cols:
            print("❌ DATA device latency data not found")
            return None
        
        data_await_col = data_await_cols[0]
        
        # Find ACCOUNTS device await columns
        accounts_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_avg_await')] if accounts_configured else []
        
        # 1. Latency Time Series with Thresholds
        axes[0, 0].plot(self.df['timestamp'], self.df[data_await_col], 
                       label='DATA Device Average Latency', linewidth=2, color='blue')
        
        # ACCOUNTS device overlay
        if accounts_configured and accounts_await_cols:
            accounts_await_col = accounts_await_cols[0]
            axes[0, 0].plot(self.df['timestamp'], self.df[accounts_await_col], 
                           label='ACCOUNTS Device Average Latency', linewidth=2, color='orange')
        
        # Threshold lines
        axes[0, 0].axhline(y=thresholds['io_warning'], color='orange', linestyle='--', alpha=0.7, 
                          label=f'Warning: {thresholds["io_warning"]}ms')
        axes[0, 0].axhline(y=thresholds['io_critical'], color='red', linestyle='--', alpha=0.7, 
                          label=f'Critical: {thresholds["io_critical"]}ms')
        
        axes[0, 0].set_title('I/O Latency vs Thresholds')
        axes[0, 0].set_ylabel('Average Latency (ms)')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 1.5. Latency Distribution Chart (Left Bottom - axes[1,0])
        axes[1, 0].hist(self.df[data_await_col], bins=10, alpha=0.8, color='blue', 
                       label='DATA Device Latency Distribution')
        
        if accounts_configured and accounts_await_cols:
            accounts_await_col = accounts_await_cols[0]
            axes[1, 0].hist(self.df[accounts_await_col], bins=10, alpha=0.6, color='orange', 
                           label='ACCOUNTS Device Latency Distribution')
        
        axes[1, 0].axvline(x=thresholds['io_warning'], color='orange', linestyle='--', alpha=0.8, linewidth=3,
                          label=f'Warning: {thresholds["io_warning"]}ms')
        axes[1, 0].axvline(x=thresholds['io_critical'], color='red', linestyle='--', alpha=0.8, linewidth=3,
                          label=f'Critical: {thresholds["io_critical"]}ms')
        
        axes[1, 0].set_title('Latency Distribution Analysis')
        axes[1, 0].set_xlabel('Average Latency (ms)')
        axes[1, 0].set_ylabel('Frequency')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # 2. Latency Violation Timeline (Right Top - axes[0,1]) - Optimized Colors
        violation_data = self.df[data_await_col] > thresholds['io_critical']
        warning_data = (self.df[data_await_col] > thresholds['io_warning']) & (self.df[data_await_col] <= thresholds['io_critical'])
        
        axes[0, 1].plot(self.df['timestamp'], violation_data.astype(int), 
                       label='DATA Critical Violations', linewidth=2, color='crimson', marker='o', markersize=3)
        axes[0, 1].plot(self.df['timestamp'], warning_data.astype(int) * 0.5, 
                       label='DATA Warning Violations', linewidth=2, color='gold', marker='s', markersize=3)
        
        if accounts_configured and accounts_await_cols:
            accounts_violation = self.df[accounts_await_col] > thresholds['io_critical']
            accounts_warning = (self.df[accounts_await_col] > thresholds['io_warning']) & (self.df[accounts_await_col] <= thresholds['io_critical'])
            
            axes[0, 1].plot(self.df['timestamp'], accounts_violation.astype(int) + 0.1, 
                           label='ACCOUNTS Critical Violations', linewidth=2, color='darkblue', marker='o', markersize=3)
            axes[0, 1].plot(self.df['timestamp'], accounts_warning.astype(int) * 0.5 + 0.05, 
                           label='ACCOUNTS Warning Violations', linewidth=2, color='forestgreen', marker='s', markersize=3)
        
        axes[0, 1].set_title('Latency Threshold Violations Timeline')
        axes[0, 1].set_ylabel('Violation Status (0=Normal, 1=Violation)')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        axes[0, 1].set_ylim(-0.1, 1.3)
        
        
        # 4. Summary Statistics (Right Bottom - axes[1,1])
        axes[1, 1].axis('off')
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        summary_text = f"I/O Latency Analysis Summary ({device_info}):\n\n"
        
        # DATA device statistics
        if data_await_cols:
            data_mean = self.df[data_await_col].mean()
            data_max = self.df[data_await_col].max()
            data_violations = (self.df[data_await_col] > thresholds['io_critical']).sum()
            
            summary_text += f"DATA Device:\n"
            summary_text += f"  Mean Latency: {data_mean:.2f}ms\n"
            summary_text += f"  Max Latency: {data_max:.2f}ms\n"
            summary_text += f"  Critical Violations: {data_violations}\n\n"
        
        # ACCOUNTS device statistics
        if accounts_configured and accounts_await_cols:
            accounts_mean = self.df[accounts_await_col].mean()
            accounts_max = self.df[accounts_await_col].max()
            accounts_violations = (self.df[accounts_await_col] > thresholds['io_critical']).sum()
            
            summary_text += f"ACCOUNTS Device:\n"
            summary_text += f"  Mean Latency: {accounts_mean:.2f}ms\n"
            summary_text += f"  Max Latency: {accounts_max:.2f}ms\n"
            summary_text += f"  Critical Violations: {accounts_violations}"
        else:
            summary_text += "ACCOUNTS Device: Not Configured"
        
        axes[1, 1].text(0.05, 0.95, summary_text, transform=axes[1, 1].transAxes, 
                       fontsize=11, verticalalignment='top', fontfamily='monospace',
                       bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
        axes[1, 1].set_title('Latency Statistics Summary')
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'await_threshold_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ I/O latency threshold analysis chart saved: {output_file} ({device_info} devices)")
        return output_file, {}
        
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
        
        return output_file, {}
        """Utilization Threshold Analysis Chart - Dual Device Support"""
        
        # Device configuration detection
        accounts_configured = self._is_accounts_configured()
        
        # Dynamic title
        title = 'Utilization Threshold Analysis - DATA & ACCOUNTS Devices' if accounts_configured else 'Utilization Threshold Analysis - DATA Device Only'
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        fig.suptitle(title, fontsize=16, fontweight='bold')
        
        # Get threshold values
        thresholds = get_visualization_thresholds()
        
        # Find DATA device util columns
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        
        if not data_util_cols:
            print("❌ DATA device utilization data not found")
            return None
        
        data_util_col = data_util_cols[0]
        
        # Find ACCOUNTS device util columns
        accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')] if accounts_configured else []
        
        # 1. Utilization Time Series with Thresholds
        axes[0, 0].plot(self.df['timestamp'], self.df[data_util_col], 
                       label='DATA Device Utilization', linewidth=2, color='blue')
        
        # ACCOUNTS device overlay
        if accounts_configured and accounts_util_cols:
            accounts_util_col = accounts_util_cols[0]
            axes[0, 0].plot(self.df['timestamp'], self.df[accounts_util_col], 
                           label='ACCOUNTS Device Utilization', linewidth=2, color='orange')
        
        # Threshold lines
        axes[0, 0].axhline(y=thresholds['io_warning'], color='orange', linestyle='--', alpha=0.7, 
                          label=f'Warning: {thresholds["io_warning"]}%')
        axes[0, 0].axhline(y=thresholds['critical'], color='red', linestyle='--', alpha=0.7, 
                          label=f'Critical: {thresholds["critical"]}%')
        
        axes[0, 0].set_title('Device Utilization vs Thresholds')
        axes[0, 0].set_ylabel('Utilization (%)')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. Utilization Distribution Chart (Left Bottom - axes[1,0])
        axes[1, 0].hist(self.df[data_util_col], bins=20, alpha=0.7, color='blue', 
                       label='DATA Device Utilization Distribution', edgecolor='black')
        
        if accounts_configured and accounts_util_cols:
            accounts_util_col = accounts_util_cols[0]
            axes[1, 0].hist(self.df[accounts_util_col], bins=20, alpha=0.7, color='orange', 
                           label='ACCOUNTS Device Utilization Distribution', edgecolor='black')
        
        axes[1, 0].axvline(x=thresholds['io_warning'], color='orange', linestyle='--', alpha=0.8, linewidth=2,
                          label=f'Warning: {thresholds["io_warning"]}%')
        axes[1, 0].axvline(x=thresholds['critical'], color='red', linestyle='--', alpha=0.8, linewidth=2,
                          label=f'Critical: {thresholds["critical"]}%')
        
        axes[1, 0].set_title('Utilization Distribution Analysis')
        axes[1, 0].set_xlabel('Utilization (%)')
        axes[1, 0].set_ylabel('Frequency')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # 2. Summary Statistics
        axes[0, 1].axis('off')
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        summary_text = f"Utilization Analysis Summary ({device_info}):\n\n"
        
        # DATA device statistics
        data_mean = self.df[data_util_col].mean()
        data_max = self.df[data_util_col].max()
        data_violations = (self.df[data_util_col] > thresholds['critical']).sum()
        
        summary_text += f"DATA Device:\n"
        summary_text += f"  Mean Utilization: {data_mean:.1f}%\n"
        summary_text += f"  Max Utilization: {data_max:.1f}%\n"
        summary_text += f"  Critical Violations: {data_violations}\n\n"
        
        # ACCOUNTS device statistics
        if accounts_configured and accounts_util_cols:
            accounts_mean = self.df[accounts_util_col].mean()
            accounts_max = self.df[accounts_util_col].max()
            accounts_violations = (self.df[accounts_util_col] > thresholds['critical']).sum()
            
            summary_text += f"ACCOUNTS Device:\n"
            summary_text += f"  Mean Utilization: {accounts_mean:.1f}%\n"
            summary_text += f"  Max Utilization: {accounts_max:.1f}%\n"
            summary_text += f"  Critical Violations: {accounts_violations}"
        else:
            summary_text += "ACCOUNTS Device: Not Configured"
        
        axes[0, 1].text(0.05, 0.95, summary_text, transform=axes[0, 1].transAxes, 
                       fontsize=11, verticalalignment='top', fontfamily='monospace',
                       bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
        
        # 4. Summary Statistics (Right Bottom - axes[1,1])
        axes[1, 1].axis('off')
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        summary_text = f"Utilization Analysis Summary ({device_info}):\\n\\n"
        
        # DATA device statistics
        if data_util_cols:
            data_mean = self.df[data_util_col].mean()
            data_max = self.df[data_util_col].max()
            data_violations = (self.df[data_util_col] > thresholds['critical']).sum()
            
            summary_text += f"DATA Device:\\n"
            summary_text += f"  Mean Utilization: {data_mean:.1f}%\\n"
            summary_text += f"  Max Utilization: {data_max:.1f}%\\n"
            summary_text += f"  Critical Violations: {data_violations}\\n\\n"
        
        # ACCOUNTS device statistics
        if accounts_configured and accounts_util_cols:
            accounts_util_col = accounts_util_cols[0]
            accounts_mean = self.df[accounts_util_col].mean()
            accounts_max = self.df[accounts_util_col].max()
            accounts_violations = (self.df[accounts_util_col] > thresholds['critical']).sum()
            
            summary_text += f"ACCOUNTS Device:\\n"
            summary_text += f"  Mean Utilization: {accounts_mean:.1f}%\\n"
            summary_text += f"  Max Utilization: {accounts_max:.1f}%\\n"
            summary_text += f"  Critical Violations: {accounts_violations}"
        else:
            summary_text += "ACCOUNTS Device: Not Configured"
        
        axes[1, 1].text(0.05, 0.95, summary_text, transform=axes[1, 1].transAxes, 
                       fontsize=11, verticalalignment='top', fontfamily='monospace',
                       bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
        axes[1, 1].set_title('Utilization Statistics Summary')
        
        plt.tight_layout()
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'util_threshold_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ Utilization threshold analysis chart saved: {output_file} ({device_info} devices)")
        return output_file, {}
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
        """Create monitoring overhead analysis chart - 增强稳定性"""
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
            
            # 3. EBS Latency trends
            data_await_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_avg_await')]
            if data_await_cols:
                ax3 = axes[1, 0]
                await_col = data_await_cols[0]
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
                    except:
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
        """Bottleneck Identification Chart - Systematic Refactor"""
        
        accounts_configured = self._is_accounts_configured()
        title = 'Bottleneck Identification Analysis - DATA & ACCOUNTS Devices' if accounts_configured else 'Bottleneck Identification Analysis - DATA Device Only'
        
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                print("❌ Failed to load data for bottleneck identification analysis")
                return None
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(title, fontsize=16)
        
        thresholds = get_visualization_thresholds()
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        
        if not data_util_cols:
            print("❌ DATA device data not found")
            return None
        
        data_util_col = data_util_cols[0]
        accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')] if accounts_configured else []
        
        # 1. Utilization Time Series (Top Left)
        axes[0, 0].plot(self.df['timestamp'], self.df[data_util_col], 
                       label='DATA Device Utilization', linewidth=2, color='blue')
        
        if accounts_configured and accounts_util_cols:
            accounts_util_col = accounts_util_cols[0]
            axes[0, 0].plot(self.df['timestamp'], self.df[accounts_util_col], 
                           label='ACCOUNTS Device Utilization', linewidth=2, color='orange')
        
        axes[0, 0].axhline(y=thresholds['critical'], color='red', linestyle='--', alpha=0.7, 
                          label=f'Bottleneck Threshold: {thresholds["critical"]}%')
        
        axes[0, 0].set_title('Device Utilization vs Bottleneck Threshold')
        axes[0, 0].set_ylabel('Utilization (%)')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. Bottleneck Timeline (Top Right)
        bottleneck_timeline = self.df[data_util_col] > thresholds['critical']
        
        axes[0, 1].plot(self.df['timestamp'], bottleneck_timeline.astype(int), 
                       label='DATA Bottleneck Events', linewidth=2, color='red', marker='o', markersize=2)
        
        if accounts_configured and accounts_util_cols:
            accounts_bottleneck_timeline = self.df[accounts_util_col] > thresholds['critical']
            axes[0, 1].plot(self.df['timestamp'], accounts_bottleneck_timeline.astype(int) + 0.1, 
                           label='ACCOUNTS Bottleneck Events', linewidth=2, color='darkred', marker='s', markersize=2)
        
        axes[0, 1].set_title('Bottleneck Event Timeline')
        axes[0, 1].set_ylabel('Bottleneck Status')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        axes[0, 1].set_ylim(-0.1, 1.3)
        
        # 3. Bottleneck Distribution (Bottom Left)
        normal_data = self.df[data_util_col][self.df[data_util_col] <= thresholds['critical']]
        bottleneck_data = self.df[data_util_col][self.df[data_util_col] > thresholds['critical']]
        
        if len(normal_data) > 0:
            axes[1, 0].hist(normal_data, bins=15, alpha=0.7, color='green', label='Normal Operation')
        if len(bottleneck_data) > 0:
            axes[1, 0].hist(bottleneck_data, bins=15, alpha=0.7, color='red', label='Bottleneck Events')
        
        axes[1, 0].axvline(x=thresholds['critical'], color='red', linestyle='--', alpha=0.8, linewidth=2,
                          label=f'Threshold: {thresholds["critical"]}%')
        
        axes[1, 0].set_title('Utilization Distribution')
        axes[1, 0].set_xlabel('Utilization (%)')
        axes[1, 0].set_ylabel('Frequency')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # 4. Statistics Summary (Bottom Right)
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        data_normal = (self.df[data_util_col] <= thresholds['critical']).sum()
        data_bottleneck = (self.df[data_util_col] > thresholds['critical']).sum()
        data_percentage = (data_bottleneck / len(self.df) * 100) if len(self.df) > 0 else 0
        
        data_stats = {
            'mean': self.df[data_util_col].mean(),
            'max': self.df[data_util_col].max(),
            'violations': data_bottleneck,
            'unit': '%'
        }
        
        accounts_stats = None
        if accounts_configured and accounts_util_cols:
            accounts_normal = (self.df[accounts_util_col] <= thresholds['critical']).sum()
            accounts_bottleneck = (self.df[accounts_util_col] > thresholds['critical']).sum()
            
            accounts_stats = {
                'mean': self.df[accounts_util_col].mean(),
                'max': self.df[accounts_util_col].max(),
                'violations': accounts_bottleneck,
                'unit': '%'
            }
        
        summary_text = format_summary_text(device_info, data_stats, accounts_stats)
        add_text_summary(axes[1, 1], summary_text, 'Bottleneck Statistics')
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'bottleneck_identification.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        print(f"✅ Bottleneck identification chart saved: {output_file} ({device_info} devices)")
        
        return output_file
        """Bottleneck Identification Chart - Dual Device Support"""
        
        # Device configuration detection
        accounts_configured = self._is_accounts_configured()
        
        # Dynamic title
        title = 'Bottleneck Identification Analysis - DATA & ACCOUNTS Devices' if accounts_configured else 'Bottleneck Identification Analysis - DATA Device Only'
        
        # Check data availability
        if not hasattr(self, 'df') or self.df is None:
            if not self.load_data():
                print("❌ Failed to load data for bottleneck identification analysis")
                return None
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(title, fontsize=16, fontweight='bold')
        
        # Get threshold values
        thresholds = get_visualization_thresholds()
        
        # Find device columns
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        
        if not data_util_cols:
            print("❌ DATA device data not found")
            return None
        
        data_util_col = data_util_cols[0]
        
        # ACCOUNTS device columns
        accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')] if accounts_configured else []
        
        # 1. Device Utilization Bottleneck Detection
        axes[0, 0].plot(self.df['timestamp'], self.df[data_util_col], 
                       label='DATA Device Utilization', linewidth=2, color='blue')
        
        # ACCOUNTS device overlay
        if accounts_configured and accounts_util_cols:
            accounts_util_col = accounts_util_cols[0]
            axes[0, 0].plot(self.df['timestamp'], self.df[accounts_util_col], 
                           label='ACCOUNTS Device Utilization', linewidth=2, color='orange')
        
        # Bottleneck threshold lines
        axes[0, 0].axhline(y=thresholds['critical'], color='red', linestyle='--', alpha=0.7, 
                          label=f'Bottleneck Threshold: {thresholds["critical"]}%')
        
        axes[0, 0].set_title('Utilization Bottleneck Detection')
        axes[0, 0].set_ylabel('Utilization (%)')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. Bottleneck Timeline Chart (Right Top - axes[0,1])
        bottleneck_timeline = self.df[data_util_col] > thresholds['critical']
        axes[0, 1].plot(self.df['timestamp'], bottleneck_timeline.astype(int), 
                       label='DATA Device Bottleneck Events', linewidth=2, color='red', marker='o', markersize=4)
        
        if accounts_configured and accounts_util_cols:
            accounts_util_col = accounts_util_cols[0]
            accounts_bottleneck_timeline = self.df[accounts_util_col] > thresholds['critical']
            axes[0, 1].plot(self.df['timestamp'], accounts_bottleneck_timeline.astype(int) + 0.1, 
                           label='ACCOUNTS Device Bottleneck Events', linewidth=2, color='orange', marker='s', markersize=4)
        
        axes[0, 1].set_title('Bottleneck Timeline Analysis')
        axes[0, 1].set_ylabel('Bottleneck Status (0=Normal, 1=Bottleneck)')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        axes[0, 1].set_ylim(-0.1, 1.3)
        
        # 3. Bottleneck Statistics Chart (Left Bottom - axes[1,0])
        bottleneck_counts = ['Normal', 'Bottleneck']
        data_normal = (self.df[data_util_col] <= thresholds['critical']).sum()
        data_bottleneck = (self.df[data_util_col] > thresholds['critical']).sum()
        data_counts = [data_normal, data_bottleneck]
        
        if accounts_configured and accounts_util_cols:
            accounts_util_col = accounts_util_cols[0]
            accounts_normal = (self.df[accounts_util_col] <= thresholds['critical']).sum()
            accounts_bottleneck = (self.df[accounts_util_col] > thresholds['critical']).sum()
            accounts_counts = [accounts_normal, accounts_bottleneck]
            
            x_pos = range(len(bottleneck_counts))
            width = 0.35
            axes[1, 0].bar([x - width/2 for x in x_pos], data_counts, width, 
                          label='DATA Device', color=['green', 'red'], alpha=0.7)
            axes[1, 0].bar([x + width/2 for x in x_pos], accounts_counts, width, 
                          label='ACCOUNTS Device', color=['lightgreen', 'lightcoral'], alpha=0.7)
            axes[1, 0].set_xticks(x_pos)
            axes[1, 0].set_xticklabels(bottleneck_counts)
            axes[1, 0].legend()
        else:
            axes[1, 0].bar(bottleneck_counts, data_counts, color=['green', 'red'], alpha=0.7)
        
        axes[1, 0].set_title('Bottleneck Statistics')
        axes[1, 0].set_ylabel('Number of Samples')
        axes[1, 0].grid(True, alpha=0.3)
        
        # 4. Enhanced Summary Statistics (Right Bottom - axes[1,1])
        axes[1, 1].axis('off')
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        summary_text = f"Bottleneck Analysis Summary ({device_info}):\\n\\n"
        
        # DATA device statistics
        data_normal = (self.df[data_util_col] <= thresholds['critical']).sum()
        data_bottleneck = (self.df[data_util_col] > thresholds['critical']).sum()
        data_percentage = (data_bottleneck / len(self.df) * 100) if len(self.df) > 0 else 0
        
        summary_text += f"DATA Device:\\n"
        summary_text += f"  Normal Samples: {data_normal}\\n"
        summary_text += f"  Bottleneck Samples: {data_bottleneck}\\n"
        summary_text += f"  Bottleneck Rate: {data_percentage:.1f}%\\n\\n"
        
        # ACCOUNTS device statistics
        if accounts_configured and accounts_util_cols:
            accounts_util_col = accounts_util_cols[0]
            accounts_normal = (self.df[accounts_util_col] <= thresholds['critical']).sum()
            accounts_bottleneck = (self.df[accounts_util_col] > thresholds['critical']).sum()
            accounts_percentage = (accounts_bottleneck / len(self.df) * 100) if len(self.df) > 0 else 0
            
            summary_text += f"ACCOUNTS Device:\\n"
            summary_text += f"  Normal Samples: {accounts_normal}\\n"
            summary_text += f"  Bottleneck Samples: {accounts_bottleneck}\\n"
            summary_text += f"  Bottleneck Rate: {accounts_percentage:.1f}%"
        else:
            summary_text += "ACCOUNTS Device: Not Configured"
        
        axes[1, 1].text(0.05, 0.95, summary_text, transform=axes[1, 1].transAxes, 
                       fontsize=10, verticalalignment='top', fontfamily='monospace',
                       bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
        axes[1, 1].set_title('Bottleneck Statistics Summary')
        axes[0, 1].axis('off')
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        summary_text = f"Bottleneck Analysis Summary ({device_info}):\n\n"
        
        # DATA device bottleneck analysis
        data_bottlenecks = self.df[data_util_col] > thresholds['critical']
        data_bottleneck_count = data_bottlenecks.sum()
        data_bottleneck_pct = (data_bottleneck_count / len(self.df) * 100)
        
        summary_text += f"DATA Device:\n"
        summary_text += f"  Bottlenecks: {data_bottleneck_count} ({data_bottleneck_pct:.1f}%)\n"
        summary_text += f"  Max Utilization: {self.df[data_util_col].max():.1f}%\n\n"
        
        # ACCOUNTS device bottleneck analysis
        if accounts_configured and accounts_util_cols:
            accounts_bottlenecks = self.df[accounts_util_col] > thresholds['critical']
            accounts_bottleneck_count = accounts_bottlenecks.sum()
            accounts_bottleneck_pct = (accounts_bottleneck_count / len(self.df) * 100)
            
            summary_text += f"ACCOUNTS Device:\n"
            summary_text += f"  Bottlenecks: {accounts_bottleneck_count} ({accounts_bottleneck_pct:.1f}%)\n"
            summary_text += f"  Max Utilization: {self.df[accounts_util_col].max():.1f}%"
        else:
            summary_text += "ACCOUNTS Device: Not Configured"
        
        axes[0, 1].text(0.05, 0.95, summary_text, transform=axes[0, 1].transAxes, 
                       fontsize=11, verticalalignment='top', fontfamily='monospace',
                       bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'bottleneck_identification.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ Bottleneck identification chart saved: {output_file} ({device_info} devices)")
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
            
            # 阈值线 - 使用配置变量
            threshold = int(os.getenv('BLOCK_HEIGHT_DIFF_THRESHOLD', 50))
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
            ax.set_title('Blockchain Node Synchronization Status', 
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
