#!/usr/bin/env python3
"""
性能可视化器 - 生产级版本 (已修复CSV字段一致性问题)
使用统一的CSV数据处理器，确保字段访问的一致性和可靠性
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

# 配置中文字体支持
def setup_chinese_font():
    """配置matplotlib的中文字体支持"""
    # 尝试常见的中文字体
    chinese_fonts = [
        'Noto Sans CJK SC',      # Linux推荐
        'SimHei',                # Windows
        'Microsoft YaHei',       # Windows
        'PingFang SC',           # macOS
        'STHeiti',               # macOS
        'WenQuanYi Micro Hei',   # Linux
        'DejaVu Sans'            # 后备字体
    ]
    
    # 获取系统可用字体
    available_fonts = [f.name for f in fm.fontManager.ttflist]
    
    # 查找第一个可用的中文字体
    selected_font = None
    for font in chinese_fonts:
        if font in available_fonts:
            selected_font = font
            break
    
    if selected_font:
        plt.rcParams['font.sans-serif'] = [selected_font]
        plt.rcParams['axes.unicode_minus'] = False
        print(f"✅ 使用字体: {selected_font}")
        return True
    else:
        # 如果没有找到中文字体，使用英文标签
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
        print("⚠️  未找到中文字体，将使用英文标签")
        return False

# 初始化字体配置
HAS_CHINESE_FONT = setup_chinese_font()

# 多语言标签配置
def get_labels():
    """获取适合当前字体环境的标签"""
    if HAS_CHINESE_FONT:
        return {
            'performance_analysis': '性能分析',
            'time': '时间',
            'cpu_usage': 'CPU使用率 (%)',
            'memory_usage': '内存使用率 (%)',
            'disk_usage': '磁盘使用率 (%)',
            'network_usage': '网络使用率 (%)',
            'qps': 'QPS',
            'latency': '延迟 (ms)',
            'throughput': '吞吐量',
            'bottleneck_analysis': '瓶颈分析',
            'trend_analysis': '趋势分析',
            'correlation_analysis': '关联分析',
            'performance_summary': '性能摘要'
        }
    else:
        return {
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
            'performance_summary': 'Performance Summary'
        }

# 获取当前环境的标签
LABELS = get_labels()

# 导入统一的CSV数据处理器
current_dir = Path(__file__).parent
utils_dir = current_dir.parent / 'utils'
analysis_dir = current_dir.parent / 'analysis'

# 添加路径到sys.path
for path in [str(utils_dir), str(analysis_dir)]:
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from csv_data_processor import CSVDataProcessor
    from cpu_ebs_correlation_analyzer import CPUEBSCorrelationAnalyzer
    from unit_converter import UnitConverter
    from advanced_chart_generator import AdvancedChartGenerator
    ADVANCED_TOOLS_AVAILABLE = True
    print("✅ 高级分析工具已加载")
except ImportError as e:
    print(f"⚠️  高级分析工具不可用: {e}")
    print("📝 将使用基础功能模式，部分高级功能可能不可用")
    ADVANCED_TOOLS_AVAILABLE = False
    # 设置占位符类以避免运行时错误
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

# 高级工具导入检查
try:
    from advanced_chart_generator import AdvancedChartGenerator
    from cpu_ebs_correlation_analyzer import CPUEBSCorrelationAnalyzer  
    from unit_converter import UnitConverter
    ADVANCED_TOOLS_AVAILABLE = True
    print("✅ 高级分析工具已加载")
except ImportError as e:
    print(f"⚠️  高级分析工具不可用: {e}")
    print("📝 将使用基础功能模式，部分高级功能可能不可用")
    ADVANCED_TOOLS_AVAILABLE = False
    
    # 定义占位符类以避免IDE警告和运行时错误
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
    """性能可视化器 - 基于统一CSV数据处理器"""
    
    def __init__(self, data_file, overhead_file=None):
        super().__init__()  # 初始化CSV数据处理器
        
        self.data_file = data_file
        self.overhead_file = overhead_file
        self.output_dir = os.path.dirname(data_file)
        
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # 使用英文标签系统，移除复杂的字体管理
        self.use_english_labels = True
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
        
        self.util_thresholds = {
            'normal': 70,      # Normal Threshold (%)
            'warning': 85,     # Warning Threshold (%)
            'critical': 95     # Critical Threshold (%)
        }
        
        # 初始化新工具
        if ADVANCED_TOOLS_AVAILABLE:
            try:
                self.unit_converter = UnitConverter()
                self.correlation_analyzer = CPUEBSCorrelationAnalyzer(data_file)
                self.chart_generator = AdvancedChartGenerator(data_file, self.output_dir)
            except Exception as e:
                print(f"⚠️ 高级工具初始化失败: {e}")
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
                        print(f"✅ Time戳字段 'self.df['timestamp']' 转换成功")
                    except Exception as e:
                        print(f"⚠️  Time戳转换失败: {e}")
                        # 创建默认Time戳
                        self.df['timestamp'] = pd.date_range(start='2024-01-01', periods=len(self.df), freq='1min')
                else:
                    print("⚠️  未找到Time戳字段，创建默认Time戳")
                    self.df['timestamp'] = pd.date_range(start='2024-01-01', periods=len(self.df), freq='1min')
                
                print(f"✅ 加载了 {len(self.df)} 条性能数据")
                print(f"📊 CSV列数: {len(self.df.columns)}")
                self.print_field_info()  # 打印字段信息用于调试
                
                # 动态添加ACCOUNTS设备阈值（仅在ACCOUNTS设备配置时）
                self._add_accounts_thresholds_if_configured()
                
            return success
            
        except Exception as e:
            print(f"❌ 数据加载失败: {e}")
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
            print("✅ 已添加ACCOUNTS设备阈值配置")
    
    def _is_accounts_configured(self):
        """检查 ACCOUNTS Device是否配置和可用
        
        根据 config.sh 的逻辑，ACCOUNTS Device是可选的：
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
            print(f"⚠️  ACCOUNTS Device已配置 ({accounts_device}) 但未找到监控数据")
            return False
            
        # 完全未配置，这是正常情况
        return False
    
    def _analyze_threshold_violations(self, data_series, thresholds, metric_name):
        """✅ 改进的阈值违规分析 - 集成自await_util_analyzer"""
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
                'error': '数据为空'
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
                'error': '所有数据都是NaN'
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
        """✅ 改进的性能总览图生成"""
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
            print("❌ 未找到DATA Device数据")
            return None
        
        data_iops_col = data_iops_cols[0]
        data_util_col = data_util_cols[0] if data_util_cols else None
        
        # ✅ CPU性能指标 (改进的字段处理)
        ax1 = axes[0, 0]
        if cpu_usage_col and cpu_iowait_col:
            # 检查数据有效性
            cpu_usage_data = self.df[cpu_usage_col].dropna()
            cpu_iowait_data = self.df[cpu_iowait_col].dropna()
            
            if len(cpu_usage_data) > 0 and len(cpu_iowait_data) > 0:
                # 原始数据
                ax1.plot(self.df['timestamp'], self.df[cpu_usage_col], color='blue', linewidth=1, alpha=0.6, label='CPU Usage(原始)')
                ax1.plot(self.df['timestamp'], self.df[cpu_iowait_col], color='red', linewidth=1, alpha=0.6, label='CPU I/O Wait (Raw)')
                
                # ✅ 安全的移动平均计算
                if len(cpu_usage_data) >= 10:
                    cpu_smooth = self.df[cpu_usage_col].rolling(window=10, center=True, min_periods=1).mean()
                    ax1.plot(self.df['timestamp'], cpu_smooth, color='blue', linewidth=2, label='CPU Usage(平滑)')
                
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
        
        # ✅ DATA DeviceIOPS (改进的数据检查)
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
        
        # ✅ Memory Usage (改进的字段处理)
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
                ax3.text(0.5, 0.5, '内存Data Not Available', ha='center', va='center', transform=ax3.transAxes)
                ax3.set_title('Memory Usage (Data Not Available)')
        else:
            ax3.text(0.5, 0.5, '缺少Memory Usage字段', ha='center', va='center', transform=ax3.transAxes)
            ax3.set_title('Memory Usage (Field Missing)')
        
        # ✅ Device Utilization (改进的数据检查)
        ax4 = axes[1, 1]
        if data_util_col:
            util_data = self.df[data_util_col].dropna()
            if len(util_data) > 0:
                ax4.plot(self.df['timestamp'], self.df[data_util_col], color='orange', linewidth=2, label='DATADevice Utilization')
                ax4.axhline(y=80, color='red', linestyle='--', alpha=0.7, label='80% Warning Line')
                ax4.set_title('Device Utilization')
                ax4.set_ylabel('Utilization (%)')
                ax4.legend()
                ax4.grid(True, alpha=0.3)
            else:
                ax4.text(0.5, 0.5, 'Device UtilizationData Not Available', ha='center', va='center', transform=ax4.transAxes)
                ax4.set_title('Device Utilization (Data Not Available)')
        else:
            ax4.text(0.5, 0.5, '缺少Device Utilization字段', ha='center', va='center', transform=ax4.transAxes)
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
            # 在图表中显示错误信息
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
        
        # ✅ 安全的相关性分析函数
        def safe_correlation_analysis(x_data, y_data, ax, xlabel, ylabel, title_prefix):
            """安全的相关性分析和可视化"""
            try:
                # 数据有效性检查
                if x_data.empty or y_data.empty:
                    ax.text(0.5, 0.5, '数据为空', ha='center', va='center', transform=ax.transAxes)
                    ax.set_title(f'{title_prefix}\nData Not Available')
                    return
                
                # 移除NaN值并对齐数据
                combined_data = pd.concat([x_data, y_data], axis=1).dropna()
                if len(combined_data) < 10:
                    ax.text(0.5, 0.5, f'有效数据点不足\n(仅{len(combined_data)}个点)', 
                           ha='center', va='center', transform=ax.transAxes)
                    ax.set_title(f'{title_prefix}\n数据不足')
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
                    print(f"⚠️  {title_prefix}: 回归线拟合警告 - 数据线性相关性不足")
                except Exception as e:
                    print(f"⚠️  {title_prefix}: 回归线拟合失败: {e}")
                
                # ✅ 安全的相关性计算
                try:
                    corr, p_value = pearsonr(x_clean, y_clean)
                    if np.isnan(corr):
                        corr_text = "相关系数: NaN"
                    else:
                        significance = "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else ""
                        corr_text = f'相关系数: {corr:.3f}{significance}\n(n={len(x_clean)})'
                except Exception as e:
                    corr_text = f"计算失败: {str(e)[:20]}"
                
                ax.set_xlabel(xlabel)
                ax.set_ylabel(ylabel)
                ax.set_title(f'{title_prefix}\n{corr_text}')
                ax.grid(True, alpha=0.3)
                
            except Exception as e:
                ax.text(0.5, 0.5, f'Analysis Failed:\n{str(e)[:50]}', ha='center', va='center', transform=ax.transAxes)
                ax.set_title(f'{title_prefix}\nAnalysis Failed')
        
        # 执行各项相关性分析
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
            'CPU I/O Wait (%)', 'I/O队列长度', 'CPU I/O Wait vs I/O队列长度'
        )
        
        # ✅ Time序列对比 (改进的处理)
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
                ax4.set_title('CPU I/O Wait vs Device UtilizationTime序列')
                ax4.grid(True, alpha=0.3)
            else:
                ax4.text(0.5, 0.5, 'Time序列Data Not Available', ha='center', va='center', transform=ax4.transAxes)
                ax4.set_title('Time序列对比 (Data Not Available)')
        except Exception as e:
            ax4.text(0.5, 0.5, f'Time序列分析失败:\n{str(e)[:50]}', ha='center', va='center', transform=ax4.transAxes)
            ax4.set_title('Time序列对比 (分析失败)')
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'cpu_ebs_correlation_visualization.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 CPU-EBS相关性可视化图已保存: {output_file}")
        
        return output_file
    
    def create_device_comparison_chart(self):
        """创建Device对比图表（DATA vs ACCOUNTS）- 优化版本
        
        根据 ACCOUNTS Device配置状态动态调整图表内容：
        - 如果 ACCOUNTS 未配置：只显示 DATA Device分析
        - 如果 ACCOUNTS 已配置：显示 DATA vs ACCOUNTS 对比
        """
        # 检查 ACCOUNTS Device配置状态
        accounts_configured = self._is_accounts_configured()
        
        fig, axes = plt.subplots(2, 1, figsize=(15, 10))
        
        # 根据配置状态设置标题
        if accounts_configured:
            fig.suptitle('Device性能对比分析 (DATA vs ACCOUNTS)', fontsize=16, fontweight='bold')
        else:
            fig.suptitle('Device性能分析 (DATA)', fontsize=16, fontweight='bold')
        
        # 查找Device列
        data_cols = [col for col in self.df.columns if col.startswith('data_')]
        accounts_cols = [col for col in self.df.columns if col.startswith('accounts_')] if accounts_configured else []
        
        if not data_cols:
            print("❌ 未找到DATA Device数据")
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
        
        ax1.set_title('DeviceIOPS对比' if accounts_configured else 'DATA DeviceIOPS')
        ax1.set_ylabel('IOPS')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 下图：利用率对比
        ax2 = axes[1]
        data_util_col = [col for col in data_cols if col.endswith('_util')]
        if data_util_col:
            ax2.plot(self.df['timestamp'], self.df[data_util_col[0]], 
                    label='DATA 利用率', linewidth=2, color='blue')
        
        # 只有在 ACCOUNTS 配置时才处理 ACCOUNTS 数据
        if accounts_configured and accounts_cols:
            accounts_util_col = [col for col in accounts_cols if col.endswith('_util')]
            if accounts_util_col:
                ax2.plot(self.df['timestamp'], self.df[accounts_util_col[0]], 
                        label='ACCOUNTS 利用率', linewidth=2, color='green')
        
        ax2.axhline(y=80, color='orange', linestyle='--', alpha=0.7, label='80% Warning Line')
        ax2.axhline(y=95, color='red', linestyle='--', alpha=0.7, label='95% Critical Line')
        
        ax2.set_title('Device Utilization对比' if accounts_configured else 'DATADevice Utilization')
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Utilization (%)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'device_performance_comparison.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 Device性能对比图已保存: {output_file}")
        
        return output_file

    def create_await_threshold_analysis_chart(self):
        """创建awaitLatency阈值分析图表 - 优化版本
        
        根据 ACCOUNTS Device配置状态动态调整分析内容：
        - 如果 ACCOUNTS 未配置：只分析 DATA Device
        - 如果 ACCOUNTS 已配置：分析 DATA 和 ACCOUNTS Device
        """
        # 检查 ACCOUNTS Device配置状态
        accounts_configured = self._is_accounts_configured()
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 根据配置状态设置标题
        if accounts_configured:
            fig.suptitle('I/O Latency(await)阈值分析 - DATA & ACCOUNTS', fontsize=16, fontweight='bold')
        else:
            fig.suptitle('I/O Latency(await)阈值分析 - DATA', fontsize=16, fontweight='bold')
        
        # 获取await相关列
        data_await_cols = [col for col in self.df.columns if col.startswith('data_') and 'avg_await' in col]
        accounts_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and 'avg_await' in col] if accounts_configured else []
        
        # 平均等待Time趋势
        ax1 = axes[0, 0]
        ax1.set_title('平均I/O等待Time趋势')
        
        threshold_violations = {}
        
        # 处理dataDevice
        if data_await_cols:
            col = data_await_cols[0]
            ax1.plot(self.df['timestamp'], self.df[col], 
                    label='DATA 平均等待Time', linewidth=2)
            
            # 分析阈值违规
            violations = self._analyze_threshold_violations(
                self.df[col], self.await_thresholds, 'data_avg_await'
            )
            threshold_violations['data_avg_await'] = violations
        
        # 只有在 ACCOUNTS 配置时才处理 ACCOUNTS 数据
        if accounts_configured and accounts_await_cols:
            col = accounts_await_cols[0]
            ax1.plot(self.df['timestamp'], self.df[col], 
                    label='ACCOUNTS 平均等待Time', linewidth=2)
            
            # 分析阈值违规
            violations = self._analyze_threshold_violations(
                self.df[col], self.await_thresholds, 'accounts_avg_await'
            )
            threshold_violations['accounts_avg_await'] = violations
        elif not accounts_configured:
            # 添加说明文本
            ax1.text(0.02, 0.98, 'ACCOUNTS Device未配置', transform=ax1.transAxes, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        ax1.axhline(y=self.await_thresholds['warning'], color='orange', 
                   linestyle='--', alpha=0.7, label='Warning Threshold (20ms)')
        ax1.axhline(y=self.await_thresholds['critical'], color='red', 
                   linestyle='--', alpha=0.7, label='Critical Threshold (50ms)')
        ax1.set_ylabel('等待Time (ms)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 读等待Time
        ax2 = axes[0, 1]
        ax2.set_title('读操作等待Time')
        
        # 获取读等待Time列
        data_r_await_cols = [col for col in self.df.columns if col.startswith('data_') and 'r_await' in col]
        accounts_r_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and 'r_await' in col] if accounts_configured else []
        
        if data_r_await_cols:
            col = data_r_await_cols[0]
            ax2.plot(self.df['timestamp'], self.df[col], 
                    label='DATA 读等待Time', linewidth=2)
        
        if accounts_configured and accounts_r_await_cols:
            col = accounts_r_await_cols[0]
            ax2.plot(self.df['timestamp'], self.df[col], 
                    label='ACCOUNTS 读等待Time', linewidth=2)
        elif not accounts_configured:
            ax2.text(0.02, 0.98, 'ACCOUNTS Device未配置', transform=ax2.transAxes, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        ax2.axhline(y=self.await_thresholds['warning'], color='orange', 
                   linestyle='--', alpha=0.7)
        ax2.axhline(y=self.await_thresholds['critical'], color='red', 
                   linestyle='--', alpha=0.7)
        ax2.set_ylabel('读等待Time (ms)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 写等待Time
        ax3 = axes[1, 0]
        ax3.set_title('写操作等待Time')
        
        # 获取写等待Time列
        data_w_await_cols = [col for col in self.df.columns if col.startswith('data_') and 'w_await' in col]
        accounts_w_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and 'w_await' in col] if accounts_configured else []
        
        if data_w_await_cols:
            col = data_w_await_cols[0]
            ax3.plot(self.df['timestamp'], self.df[col], 
                    label='DATA 写等待Time', linewidth=2)
        
        if accounts_configured and accounts_w_await_cols:
            col = accounts_w_await_cols[0]
            ax3.plot(self.df['timestamp'], self.df[col], 
                    label='ACCOUNTS 写等待Time', linewidth=2)
        elif not accounts_configured:
            ax3.text(0.02, 0.98, 'ACCOUNTS Device未配置', transform=ax3.transAxes, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        ax3.axhline(y=self.await_thresholds['warning'], color='orange', 
                   linestyle='--', alpha=0.7)
        ax3.axhline(y=self.await_thresholds['critical'], color='red', 
                   linestyle='--', alpha=0.7)
        ax3.set_ylabel('写等待Time (ms)')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 阈值违规统计
        ax4 = axes[1, 1]
        ax4.set_title('阈值违规统计')
        
        if threshold_violations:
            devices = list(threshold_violations.keys())
            warning_pcts = [threshold_violations[dev]['warning_percentage'] for dev in devices]
            critical_pcts = [threshold_violations[dev]['critical_percentage'] for dev in devices]
            
            x = np.arange(len(devices))
            width = 0.35
            
            ax4.bar(x - width/2, warning_pcts, width, label='警告违规%', color='orange', alpha=0.7)
            ax4.bar(x + width/2, critical_pcts, width, label='危险违规%', color='red', alpha=0.7)
            
            ax4.set_xlabel('Device')
            ax4.set_ylabel('违规百分比 (%)')
            ax4.set_xticks(x)
            ax4.set_xticklabels([dev.replace('_avg_await', '') for dev in devices])
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        else:
            ax4.text(0.5, 0.5, '无阈值违规数据', ha='center', va='center', transform=ax4.transAxes)
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'await_threshold_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 I/O Latency阈值分析图已保存: {output_file}")
        
        return output_file, threshold_violations

    def create_util_threshold_analysis_chart(self):
        """创建利用率阈值分析图表 - 优化版本
        
        根据 ACCOUNTS Device配置状态动态调整分析内容：
        - 如果 ACCOUNTS 未配置：只分析 DATA Device
        - 如果 ACCOUNTS 已配置：分析 DATA 和 ACCOUNTS Device
        """
        # 检查 ACCOUNTS Device配置状态
        accounts_configured = self._is_accounts_configured()
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 根据配置状态设置标题
        if accounts_configured:
            fig.suptitle('Device Utilization阈值分析 - DATA & ACCOUNTS', fontsize=16, fontweight='bold')
        else:
            fig.suptitle('Device Utilization阈值分析 - DATA', fontsize=16, fontweight='bold')
        
        # 获取利用率相关列
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and '_util' in col]
        accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and '_util' in col] if accounts_configured else []
        
        # 利用率Time序列
        ax1 = axes[0, 0]
        ax1.set_title('Device UtilizationTime序列')
        
        threshold_violations = {}
        
        # 处理dataDevice
        if data_util_cols:
            col = data_util_cols[0]
            ax1.plot(self.df['timestamp'], self.df[col], 
                    label='DATA 利用率', linewidth=2)
            
            # 分析阈值违规
            violations = self._analyze_threshold_violations(
                self.df[col], self.util_thresholds, 'data_util'
            )
            threshold_violations['data_util'] = violations
        
        # 只有在 ACCOUNTS 配置时才处理 ACCOUNTS 数据
        if accounts_configured and accounts_util_cols:
            col = accounts_util_cols[0]
            ax1.plot(self.df['timestamp'], self.df[col], 
                    label='ACCOUNTS 利用率', linewidth=2)
            
            # 分析阈值违规
            violations = self._analyze_threshold_violations(
                self.df[col], self.util_thresholds, 'accounts_util'
            )
            threshold_violations['accounts_util'] = violations
        elif not accounts_configured:
            # 添加说明文本
            ax1.text(0.02, 0.98, 'ACCOUNTS Device未配置', transform=ax1.transAxes, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        ax1.axhline(y=self.util_thresholds['warning'], color='orange', 
                   linestyle='--', alpha=0.7, label='Warning Threshold (85%)')
        ax1.axhline(y=self.util_thresholds['critical'], color='red', 
                   linestyle='--', alpha=0.7, label='Critical Threshold (95%)')
        ax1.set_ylabel('Utilization (%)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 利用率分布
        ax2 = axes[0, 1]
        ax2.set_title('利用率分布')
        
        # 处理dataDevice分布
        if data_util_cols:
            col = data_util_cols[0]
            ax2.hist(self.df[col], bins=30, alpha=0.7, 
                    label='DATA 利用率分布')
        
        # 只有在 ACCOUNTS 配置时才处理 ACCOUNTS 数据
        if accounts_configured and accounts_util_cols:
            col = accounts_util_cols[0]
            ax2.hist(self.df[col], bins=30, alpha=0.7, 
                    label='ACCOUNTS 利用率分布')
        elif not accounts_configured:
            ax2.text(0.02, 0.98, 'ACCOUNTS Device未配置', transform=ax2.transAxes, 
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        ax2.axvline(x=self.util_thresholds['warning'], color='orange', 
                   linestyle='--', alpha=0.7)
        ax2.axvline(x=self.util_thresholds['critical'], color='red', 
                   linestyle='--', alpha=0.7)
        ax2.set_xlabel('Utilization (%)')
        ax2.set_ylabel('频次')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 高利用率Time统计
        ax3 = axes[1, 0]
        ax3.set_title('高利用率Time统计')
        
        if threshold_violations:
            devices = list(threshold_violations.keys())
            warning_times = [threshold_violations[dev]['warning_violations'] for dev in devices]
            critical_times = [threshold_violations[dev]['critical_violations'] for dev in devices]
            
            x = np.arange(len(devices))
            width = 0.35
            
            ax3.bar(x - width/2, warning_times, width, label='警告次数', color='orange', alpha=0.7)
            ax3.bar(x + width/2, critical_times, width, label='危险次数', color='red', alpha=0.7)
            
            ax3.set_xlabel('Device')
            ax3.set_ylabel('违规次数')
            ax3.set_xticks(x)
            ax3.set_xticklabels([dev.replace('_util', '') for dev in devices])
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        else:
            ax3.text(0.5, 0.5, '无高利用率违规', ha='center', va='center', transform=ax3.transAxes)
        
        # 阈值违规百分比
        ax4 = axes[1, 1]
        ax4.set_title('阈值违规百分比')
        
        if threshold_violations:
            devices = list(threshold_violations.keys())
            warning_pcts = [threshold_violations[dev]['warning_percentage'] for dev in devices]
            critical_pcts = [threshold_violations[dev]['critical_percentage'] for dev in devices]
            
            x = np.arange(len(devices))
            width = 0.35
            
            ax4.bar(x - width/2, warning_pcts, width, label='警告违规%', color='orange', alpha=0.7)
            ax4.bar(x + width/2, critical_pcts, width, label='危险违规%', color='red', alpha=0.7)
            
            ax4.set_xlabel('Device')
            ax4.set_ylabel('违规百分比 (%)')
            ax4.set_xticks(x)
            ax4.set_xticklabels([dev.replace('_util', '') for dev in devices])
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        else:
            ax4.text(0.5, 0.5, '无阈值违规数据', ha='center', va='center', transform=ax4.transAxes)
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'util_threshold_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 Device Utilization阈值分析图已保存: {output_file}")
        
        return output_file, threshold_violations
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'util_threshold_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 Device Utilization阈值分析图已保存: {output_file}")
        
        return output_file, threshold_violations

    def create_monitoring_overhead_analysis_chart(self):
        """创建监控开销分析图表"""
        if not self.overhead_file or not os.path.exists(self.overhead_file):
            print("⚠️ 监控开销数据文件不存在，跳过开销分析图表")
            return None, {}
        
        try:
            overhead_df = pd.read_csv(self.overhead_file)
            if 'timestamp' in overhead_df.columns:
                overhead_df['timestamp'] = pd.to_datetime(overhead_df['timestamp'])
        except Exception as e:
            print(f"❌ 监控开销数据加载失败: {e}")
            return None, {}
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('监控开销分析', fontsize=16, fontweight='bold')
        
        # 1. 资源消耗对比 (总资源 vs 节点资源 vs 监控开销)
        ax1 = axes[0, 0]
        ax1.set_title('系统资源消耗对比')
        
        if all(col in self.df.columns for col in ['cpu_usage', 'mem_usage']):
            # 计算平均资源使用
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
                
                ax1.bar(x - width, total_values, width, label='总系统资源', alpha=0.8)
                ax1.bar(x, node_values, width, label='区块链节点', alpha=0.8)
                ax1.bar(x + width, monitor_values, width, label='监控开销', alpha=0.8)
                
                ax1.set_xticks(x)
                ax1.set_xticklabels(categories)
                ax1.legend()
                ax1.grid(True, alpha=0.3)
        
        # 2. 监控开销趋势
        ax2 = axes[0, 1]
        ax2.set_title('监控开销Time趋势')
        
        if 'timestamp' in overhead_df.columns and 'monitoring_cpu_percent' in overhead_df.columns:
            ax2.plot(overhead_df['timestamp'], overhead_df['monitoring_cpu_percent'], 
                    label='CPU开销', linewidth=2)
            if 'monitoring_mem_percent' in overhead_df.columns:
                ax2_mem = ax2.twinx()
                ax2_mem.plot(overhead_df['timestamp'], overhead_df['monitoring_mem_percent'], 
                           'r-', label='内存开销', linewidth=2)
                ax2_mem.set_ylabel('内存开销 (%)', color='r')
                ax2_mem.tick_params(axis='y', labelcolor='r')
            
            ax2.set_ylabel('CPU开销 (%)')
            ax2.legend(loc='upper left')
            ax2.grid(True, alpha=0.3)
        
        # 3. 监控进程资源分布
        ax3 = axes[1, 0]
        ax3.set_title('监控进程资源分布')
        
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
        ax4.set_title('监控开销统计摘要')
        ax4.axis('off')
        
        if all(col in overhead_df.columns for col in ['monitoring_cpu_percent', 'monitoring_mem_percent']):
            stats_text = f"""
监控开销统计:

CPU开销:
  平均: {overhead_df['monitoring_cpu_percent'].mean():.2f}%
  最大: {overhead_df['monitoring_cpu_percent'].max():.2f}%
  最小: {overhead_df['monitoring_cpu_percent'].min():.2f}%

内存开销:
  平均: {overhead_df['monitoring_mem_percent'].mean():.2f}%
  最大: {overhead_df['monitoring_mem_percent'].max():.2f}%
  最小: {overhead_df['monitoring_mem_percent'].min():.2f}%

监控效率:
  数据点数: {len(overhead_df)}
  监控时长: {(overhead_df['timestamp'].max() - overhead_df['timestamp'].min()).total_seconds():.0f}秒
            """
            ax4.text(0.1, 0.9, stats_text, transform=ax4.transAxes, fontsize=10,
                    verticalalignment='top', fontfamily='monospace')
        
        plt.tight_layout()
        
        output_file = os.path.join(self.output_dir, 'monitoring_overhead_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"📊 监控开销分析图已保存: {output_file}")
        
        # 返回开销分析结果
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
        print("🎨 生成性能可视化图表...")
        
        if not self.load_data():
            return []
        
        chart_files = []
        threshold_analysis_results = {}
        
        try:
            # 使用高级图表生成器
            if ADVANCED_TOOLS_AVAILABLE and self.chart_generator is not None:
                print("🎨 使用高级图表生成器...")
                advanced_charts = self.chart_generator.generate_all_charts()
                if advanced_charts:
                    chart_files.extend(advanced_charts)
            
            # 生成传统图表作为补充
            overview_chart = self.create_performance_overview_chart()
            if overview_chart:
                chart_files.append(overview_chart)
                
            correlation_chart = self.create_correlation_visualization_chart()
            if correlation_chart:
                chart_files.append(correlation_chart)
                
            comparison_chart = self.create_device_comparison_chart()
            if comparison_chart:
                chart_files.append(comparison_chart)
            
            # 新增: 移动平均趋势图表
            smoothed_chart = self.create_smoothed_trend_chart()
            if smoothed_chart:
                chart_files.append(smoothed_chart)
            
            # 生成阈值分析图表 - 集成自await_util_analyzer
            print("📊 生成阈值分析图表...")
            
            await_chart, await_violations = self.create_await_threshold_analysis_chart()
            if await_chart:
                chart_files.append(await_chart)
                threshold_analysis_results['await_violations'] = await_violations
            
            # 生成QPS趋势分析图表
            print("📊 生成QPS趋势分析图表...")
            qps_trend_chart = self.create_qps_trend_analysis_chart()
            if qps_trend_chart:
                chart_files.append(qps_trend_chart)
            
            # 生成资源效率分析图表
            print("📊 生成资源效率分析图表...")
            efficiency_chart = self.create_resource_efficiency_analysis_chart()
            if efficiency_chart:
                chart_files.append(efficiency_chart)
            
            # 生成瓶颈识别分析图表
            print("📊 生成瓶颈识别分析图表...")
            bottleneck_chart = self.create_bottleneck_identification_chart()
            if bottleneck_chart:
                chart_files.append(bottleneck_chart)
            
            util_chart, util_violations = self.create_util_threshold_analysis_chart()
            if util_chart:
                chart_files.append(util_chart)
                threshold_analysis_results['util_violations'] = util_violations
            
            # 生成监控开销分析图表
            print("📊 生成监控开销分析图表...")
            
            overhead_chart, overhead_analysis = self.create_monitoring_overhead_analysis_chart()
            if overhead_chart:
                chart_files.append(overhead_chart)
                threshold_analysis_results['overhead_analysis'] = overhead_analysis
            
            # 打印阈值分析摘要
            self._print_threshold_analysis_summary(threshold_analysis_results)
            
            print(f"✅ 生成了 {len(chart_files)} 个图表")
            return chart_files, threshold_analysis_results
            
        except Exception as e:
            print(f"❌ 图表生成失败: {e}")
            import traceback
            traceback.print_exc()
            return [], {}
    
    def _print_threshold_analysis_summary(self, results):
        """打印阈值分析摘要 - 集成自await_util_analyzer"""
        print("\n📊 阈值分析摘要:")
        print("=" * 60)
        
        if 'await_violations' in results:
            print("\n🕐 I/O Latency阈值分析:")
            for device, violations in results['await_violations'].items():
                print(f"  {device}:")
                print(f"    平均值: {violations['avg_value']:.2f}ms")
                print(f"    最大值: {violations['max_value']:.2f}ms")
                print(f"    警告违规: {violations['warning_violations']}/{violations['total_points']} ({violations['warning_percentage']:.1f}%)")
                print(f"    危险违规: {violations['critical_violations']}/{violations['total_points']} ({violations['critical_percentage']:.1f}%)")
        
        if 'util_violations' in results:
            print("\n📈 Device Utilization阈值分析:")
            for device, violations in results['util_violations'].items():
                print(f"  {device}:")
                print(f"    平均值: {violations['avg_value']:.1f}%")
                print(f"    最大值: {violations['max_value']:.1f}%")
                print(f"    警告违规: {violations['warning_violations']}/{violations['total_points']} ({violations['warning_percentage']:.1f}%)")
                print(f"    危险违规: {violations['critical_violations']}/{violations['total_points']} ({violations['critical_percentage']:.1f}%)")
        
        # 新增：详细的监控开销分析摘要
        if 'overhead_analysis' in results:
            print("\n💻 监控开销详细分析:")
            overhead = results['overhead_analysis']
            print(f"  CPU开销:")
            print(f"    平均开销: {overhead.get('avg_cpu_overhead', 0):.2f}%")
            print(f"    峰值开销: {overhead.get('max_cpu_overhead', 0):.2f}%")
            print(f"  内存开销:")
            print(f"    平均开销: {overhead.get('avg_mem_overhead', 0):.2f}%")
            print(f"    峰值开销: {overhead.get('max_mem_overhead', 0):.2f}%")
            print(f"  监控效率:")
            print(f"    数据点数: {overhead.get('total_data_points', 0)}")
            
            # 计算资源效率比
            if self.df is not None and len(self.df) > 0:
                if 'cpu_usage' in self.df.columns:
                    total_cpu = self.df['cpu_usage'].mean()
                    overhead_cpu = overhead.get('avg_cpu_overhead', 0)
                    if total_cpu > 0:
                        cpu_efficiency = (1 - overhead_cpu / total_cpu) * 100
                        print(f"    CPU效率: {cpu_efficiency:.1f}% (节点实际使用)")
                
                if 'mem_usage' in self.df.columns:
                    total_mem = self.df['mem_usage'].mean()
                    overhead_mem = overhead.get('avg_mem_overhead', 0)
                    if total_mem > 0:
                        mem_efficiency = (1 - overhead_mem / total_mem) * 100
                        print(f"    内存效率: {mem_efficiency:.1f}% (节点实际使用)")
        
        print("=" * 60)

    def create_smoothed_trend_chart(self):
        """
        生成移动平均平滑趋势图表
        显示原始数据和平滑后的趋势线对比
        """
        print("📈 生成移动平均趋势图表...")
        
        try:
            fig, axes = plt.subplots(2, 2, figsize=(18, 12))
            fig.suptitle('性能指标移动平均趋势分析', fontsize=16, fontweight='bold')
            
            # 移动平均窗口大小
            window_size = min(10, len(self.df) // 10)  # 自适应窗口大小
            if window_size < 3:
                window_size = 3
            
            # 1. CPU Usage趋势
            ax1 = axes[0, 0]
            ax1.plot(self.df['timestamp'], self.df['cpu_usage'], 
                    color='lightblue', linewidth=1, alpha=0.5, label='CPU Usage(原始)')
            
            cpu_smooth = self.df['cpu_usage'].rolling(window=window_size, center=True).mean()
            ax1.plot(self.df['timestamp'], cpu_smooth, 
                    color='blue', linewidth=2, label=f'CPU Usage({window_size}点平滑)')
            
            ax1.set_title('CPU Usage趋势')
            ax1.set_ylabel('Usage (%)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 2. Memory Usage趋势
            ax2 = axes[0, 1]
            ax2.plot(self.df['timestamp'], self.df['mem_usage'], 
                    color='lightcoral', linewidth=1, alpha=0.5, label='Memory Usage(原始)')
            
            mem_smooth = self.df['mem_usage'].rolling(window=window_size, center=True).mean()
            ax2.plot(self.df['timestamp'], mem_smooth, 
                    color='red', linewidth=2, label=f'Memory Usage({window_size}点平滑)')
            
            ax2.set_title('Memory Usage趋势')
            ax2.set_ylabel('Usage (%)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            # 3. EBSLatency趋势
            data_await_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_avg_await')]
            if data_await_cols:
                ax3 = axes[1, 0]
                await_col = data_await_cols[0]
                
                ax3.plot(self.df['timestamp'], self.df[await_col], 
                        color='lightgreen', linewidth=1, alpha=0.5, label='EBSLatency(原始)')
                
                await_smooth = self.df[await_col].rolling(window=window_size, center=True).mean()
                ax3.plot(self.df['timestamp'], await_smooth, 
                        color='green', linewidth=2, label=f'EBSLatency({window_size}点平滑)')
                
                ax3.set_title('EBSLatency趋势')
                ax3.set_ylabel('Latency (ms)')
                ax3.legend()
                ax3.grid(True, alpha=0.3)
            else:
                axes[1, 0].text(0.5, 0.5, '未找到EBSLatency数据', ha='center', va='center', transform=axes[1, 0].transAxes)
                axes[1, 0].set_title('EBSLatency趋势 (无数据)')
            
            # 4. 网络带宽趋势
            if 'net_rx_mbps' in self.df.columns:
                ax4 = axes[1, 1]
                ax4.plot(self.df['timestamp'], self.df['net_rx_mbps'], 
                        color='lightcoral', linewidth=1, alpha=0.5, label='网络接收(原始)')
                
                net_smooth = self.df['net_rx_mbps'].rolling(window=window_size, center=True).mean()
                ax4.plot(self.df['timestamp'], net_smooth, 
                        color='orange', linewidth=2, label=f'网络接收({window_size}点平滑)')
                
                ax4.set_title('网络带宽趋势')
                ax4.set_ylabel('带宽 (Mbps)')
                ax4.legend()
                ax4.grid(True, alpha=0.3)
            else:
                axes[1, 1].text(0.5, 0.5, '未找到网络带宽数据', ha='center', va='center', transform=axes[1, 1].transAxes)
                axes[1, 1].set_title('网络带宽趋势 (无数据)')
            
            # 格式化Time轴
            for ax in axes.flat:
                ax.tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            
            # 保存图表
            output_file = os.path.join(self.output_dir, 'smoothed_trend_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  ✅ 移动平均趋势图: {os.path.basename(output_file)}")
            return output_file
            
        except Exception as e:
            print(f"❌ 移动平均趋势图生成失败: {e}")
            return None

    def create_qps_trend_analysis_chart(self):
        """QPS趋势分析图"""
        print("📊 生成QPS趋势分析图表...")
        
        try:
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('QPS性能趋势分析', fontsize=16, fontweight='bold')
            
            # 查找QPS相关字段
            qps_cols = [col for col in self.df.columns if 'qps' in col.lower()]
            if not qps_cols:
                print("⚠️  未找到QPS相关字段")
                plt.close()
                return None
            
            # 1. QPSTime序列
            ax1 = axes[0, 0]
            for qps_col in qps_cols[:3]:  # 最多显示3个QPS指标
                ax1.plot(self.df['timestamp'], self.df[qps_col], label=qps_col, linewidth=2)
            ax1.set_title('QPSTime序列')
            ax1.set_ylabel('QPS')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 2. QPS分布直方图
            ax2 = axes[0, 1]
            for qps_col in qps_cols[:2]:
                ax2.hist(self.df[qps_col].dropna(), alpha=0.7, label=qps_col, bins=30)
            ax2.set_title('QPS分布')
            ax2.set_xlabel('QPS')
            ax2.set_ylabel('频次')
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
            stats_text = "QPS统计摘要:\n\n"
            for qps_col in qps_cols[:3]:
                qps_data = self.df[qps_col].dropna()
                if len(qps_data) > 0:
                    stats_text += f"{qps_col}:\n"
                    stats_text += f"  平均: {qps_data.mean():.2f}\n"
                    stats_text += f"  最大: {qps_data.max():.2f}\n"
                    stats_text += f"  最小: {qps_data.min():.2f}\n\n"
            ax4.text(0.1, 0.9, stats_text, transform=ax4.transAxes, fontsize=10, verticalalignment='top')
            
            plt.tight_layout()
            
            # 保存图表
            output_file = os.path.join(self.output_dir, 'qps_trend_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  ✅ QPS趋势分析图: {os.path.basename(output_file)}")
            return output_file
            
        except Exception as e:
            print(f"❌ QPS趋势分析图生成失败: {e}")
            return None

    def create_resource_efficiency_analysis_chart(self):
        """资源效率分析图"""
        print("📊 生成资源效率分析图表...")
        
        try:
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('资源效率分析', fontsize=16, fontweight='bold')
            
            # 1. CPU效率分析
            ax1 = axes[0, 0]
            if 'cpu_usage' in self.df.columns:
                cpu_data = self.df['cpu_usage'].dropna()
                efficiency_ranges = ['低效(<30%)', '一般(30-60%)', '高效(60-85%)', '过载(>85%)']
                efficiency_counts = [
                    len(cpu_data[cpu_data < 30]),
                    len(cpu_data[(cpu_data >= 30) & (cpu_data < 60)]),
                    len(cpu_data[(cpu_data >= 60) & (cpu_data < 85)]),
                    len(cpu_data[cpu_data >= 85])
                ]
                ax1.pie(efficiency_counts, labels=efficiency_ranges, autopct='%1.1f%%')
                ax1.set_title('CPU效率分布')
            
            # 2. 内存效率分析
            ax2 = axes[0, 1]
            if 'mem_usage' in self.df.columns:
                mem_data = self.df['mem_usage'].dropna()
                mem_ranges = ['低效(<40%)', '一般(40-70%)', '高效(70-90%)', '过载(>90%)']
                mem_counts = [
                    len(mem_data[mem_data < 40]),
                    len(mem_data[(mem_data >= 40) & (mem_data < 70)]),
                    len(mem_data[(mem_data >= 70) & (mem_data < 90)]),
                    len(mem_data[mem_data >= 90])
                ]
                ax2.pie(mem_counts, labels=mem_ranges, autopct='%1.1f%%')
                ax2.set_title('内存效率分布')
            
            # 3. I/O效率分析
            ax3 = axes[1, 0]
            data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
            if data_util_cols:
                util_col = data_util_cols[0]
                util_data = self.df[util_col].dropna()
                ax3.hist(util_data, bins=20, alpha=0.7, color='green')
                ax3.axvline(util_data.mean(), color='red', linestyle='--', label=f'平均: {util_data.mean():.1f}%')
                ax3.set_title('I/O利用率分布')
                ax3.set_xlabel('Utilization (%)')
                ax3.set_ylabel('频次')
                ax3.legend()
            
            # 4. 效率统计摘要
            ax4 = axes[1, 1]
            ax4.axis('off')
            stats_text = "效率统计摘要:\n\n"
            if 'cpu_usage' in self.df.columns:
                cpu_avg = self.df['cpu_usage'].mean()
                stats_text += f"CPU平均利用率: {cpu_avg:.1f}%\n"
            if 'mem_usage' in self.df.columns:
                mem_avg = self.df['mem_usage'].mean()
                stats_text += f"内存平均利用率: {mem_avg:.1f}%\n"
            if data_util_cols:
                io_avg = self.df[data_util_cols[0]].mean()
                stats_text += f"I/O平均利用率: {io_avg:.1f}%\n"
            ax4.text(0.1, 0.9, stats_text, transform=ax4.transAxes, fontsize=12, verticalalignment='top')
            
            plt.tight_layout()
            
            # 保存图表
            output_file = os.path.join(self.output_dir, 'resource_efficiency_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  ✅ 资源效率分析图: {os.path.basename(output_file)}")
            return output_file
            
        except Exception as e:
            print(f"❌ 资源效率分析图生成失败: {e}")
            return None

    def create_bottleneck_identification_chart(self):
        """瓶颈识别分析图"""
        print("📊 生成瓶颈识别分析图表...")
        
        try:
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('系统瓶颈识别分析', fontsize=16, fontweight='bold')
            
            # 1. 瓶颈Time序列
            ax1 = axes[0, 0]
            bottleneck_data = []
            
            if 'cpu_usage' in self.df.columns:
                cpu_bottleneck = (self.df['cpu_usage'] > 85).astype(int)
                ax1.plot(self.df['timestamp'], cpu_bottleneck, label='CPU瓶颈(>85%)', linewidth=2)
                bottleneck_data.append(('CPU', cpu_bottleneck.sum()))
            
            if 'mem_usage' in self.df.columns:
                mem_bottleneck = (self.df['mem_usage'] > 90).astype(int)
                ax1.plot(self.df['timestamp'], mem_bottleneck, label='内存瓶颈(>90%)', linewidth=2)
                bottleneck_data.append(('内存', mem_bottleneck.sum()))
            
            data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
            if data_util_cols:
                io_bottleneck = (self.df[data_util_cols[0]] > 80).astype(int)
                ax1.plot(self.df['timestamp'], io_bottleneck, label='I/O瓶颈(>80%)', linewidth=2)
                bottleneck_data.append(('I/O', io_bottleneck.sum()))
            
            ax1.set_title('瓶颈Time序列')
            ax1.set_ylabel('瓶颈状态')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 2. 瓶颈频次统计
            ax2 = axes[0, 1]
            if bottleneck_data:
                resources, counts = zip(*bottleneck_data)
                ax2.bar(resources, counts, color=['red', 'orange', 'yellow'])
                ax2.set_title('瓶颈频次统计')
                ax2.set_ylabel('瓶颈次数')
                for i, count in enumerate(counts):
                    ax2.text(i, count + max(counts) * 0.01, str(count), ha='center')
            
            # 3. 资源使用率热力图
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
                    ax3.set_title('资源使用率热力图')
                    ax3.set_yticks(range(len(resource_cols)))
                    ax3.set_yticklabels(resource_cols)
                    plt.colorbar(im, ax=ax3)
            
            # 4. 瓶颈分析摘要
            ax4 = axes[1, 1]
            ax4.axis('off')
            summary_text = "瓶颈分析摘要:\n\n"
            total_points = len(self.df)
            
            for resource, count in bottleneck_data:
                percentage = (count / total_points) * 100 if total_points > 0 else 0
                summary_text += f"{resource}瓶颈:\n"
                summary_text += f"  发生次数: {count}\n"
                summary_text += f"  占比: {percentage:.1f}%\n\n"
            
            ax4.text(0.1, 0.9, summary_text, transform=ax4.transAxes, fontsize=10, verticalalignment='top')
            
            plt.tight_layout()
            
            # 保存图表
            output_file = os.path.join(self.output_dir, 'bottleneck_identification.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  ✅ 瓶颈识别分析图: {os.path.basename(output_file)}")
            return output_file
            
        except Exception as e:
            print(f"❌ 瓶颈识别分析图生成失败: {e}")
            return None

def main():
    parser = argparse.ArgumentParser(description='性能可视化器')
    parser.add_argument('data_file', help='系统性能监控CSV文件')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.data_file):
        print(f"❌ 数据文件不存在: {args.data_file}")
        return 1
    
    visualizer = PerformanceVisualizer(args.data_file)
    
    result = visualizer.generate_all_charts()
    
    if result:
        print("🎉 性能可视化完成!")
        return 0
    else:
        print("❌ 性能可视化失败")
        return 1

if __name__ == "__main__":
    exit(main())
