#!/usr/bin/env python3
"""
高级图表生成器 - 严格按照文档要求生成CPU-EBS相关性图表
实现统计分析方法的可视化，包括相关性热力图
已修复CSV字段一致性问题，使用统一的字段访问接口
"""

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
import seaborn as sns
import numpy as np
from scipy import stats
from sklearn.linear_model import LinearRegression
import statsmodels.api as sm
from typing import Dict, List, Tuple, Optional
import os
from utils.unified_logger import get_logger
import sys
from pathlib import Path

# 导入统一的CSV数据处理器
current_dir = Path(__file__).parent
utils_dir = current_dir.parent / 'utils'
sys.path.insert(0, str(utils_dir))

try:
    from csv_data_processor import CSVDataProcessor
    from unit_converter import UnitConverter
except ImportError as e:
    logging.warning(f"导入模块失败: {e}")
    # 创建占位符类
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
        def get_device_columns_safe(self, device_prefix: str, metric_suffix: str) -> List[str]:
            if self.df is None:
                return []
            matching_cols = []
            for col in self.df.columns:
                if col.startswith(f'{device_prefix}_') and metric_suffix in col:
                    matching_cols.append(col)
            return matching_cols
    
    class UnitConverter:
        pass

logger = get_logger(__name__)


class AdvancedChartGenerator(CSVDataProcessor):
    """高级图表生成器 - 基于统一CSV数据处理器"""
    
    def __init__(self, data_file: str, output_dir: str = None):
        """
        初始化图表生成器
        
        Args:
            data_file: 数据文件路径
            output_dir: 输出目录
        """
        super().__init__()  # 初始化CSV数据处理器
        
        self.data_file = data_file
        self.output_dir = output_dir or os.path.dirname(data_file)
        
        try:
            self.unit_converter = UnitConverter()
        except:
            self.unit_converter = None
        
        # 设置图表样式
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
    def _check_device_configured(self, logical_name: str) -> bool:
        """检查设备是否配置并且有数据"""
        if self.df is None:
            return False
        
        # 通过列名前缀检查设备是否存在
        device_cols = [col for col in self.df.columns if col.startswith(f'{logical_name}_')]
        return len(device_cols) > 0
    
    def _get_device_columns_safe(self, logical_name: str, metric_suffix: str) -> List[str]:
        """安全获取设备列，只返回存在的列"""
        if not self._check_device_configured(logical_name):
            return []
        
        return self.get_device_columns_safe(logical_name, metric_suffix)
    
    def _get_configured_devices(self) -> List[str]:
        """获取已配置的设备列表"""
        devices = []
        if self._check_device_configured('data'):
            devices.append('data')
        if self._check_device_configured('accounts'):
            devices.append('accounts')
        return devices
        
    def load_data(self) -> bool:
        """加载数据"""
        try:
            success = self.load_csv_data(self.data_file)
            if success:
                self.clean_data()  # 清洗数据
                logger.info(f"✅ 加载数据成功: {len(self.df)} 行")
                self.print_field_info()  # 打印字段信息用于调试
            return success
        except Exception as e:
            logger.error(f"❌ 数据加载失败: {e}")
            return False
    
    def print_field_info(self):
        """打印字段信息用于调试"""
        if self.df is not None:
            logger.info(f"📊 数据字段信息: {list(self.df.columns)}")
            logger.info(f"📊 数据形状: {self.df.shape}")
        else:
            logger.warning("⚠️ 数据未加载")
    
    def get_field_name_safe(self, field_name: str) -> Optional[str]:
        """安全获取字段名称"""
        if self.df is None:
            return None
        
        # 直接匹配
        if field_name in self.df.columns:
            return field_name
        
        # 模糊匹配
        for col in self.df.columns:
            if field_name.lower() in col.lower():
                return col
        
        return None
    
    def generate_pearson_correlation_charts(self) -> List[str]:
        """生成Pearson相关性图表"""
        if not self.load_data():
            return []
        
        print("📊 生成Pearson相关性图表...")
        chart_files = []
        
        # 检查设备配置
        data_configured = self._check_device_configured('data')
        accounts_configured = self._check_device_configured('accounts')
        
        # 使用安全的字段获取方法
        cpu_iowait_field = self.get_field_name_safe('cpu_iowait')
        if not cpu_iowait_field:
            print("⚠️ 未找到CPU I/O等待字段，跳过相关性分析")
            return []
        
        # 获取设备字段
        device_util_cols = []
        device_aqu_cols = []
        device_await_cols = []
        
        if data_configured:
            device_util_cols.extend(self._get_device_columns_safe('data', 'util'))
            device_aqu_cols.extend(self._get_device_columns_safe('data', 'aqu_sz'))
            device_await_cols.extend(self._get_device_columns_safe('data', 'avg_await'))
        
        if accounts_configured:
            device_util_cols.extend(self._get_device_columns_safe('accounts', 'util'))
            device_aqu_cols.extend(self._get_device_columns_safe('accounts', 'aqu_sz'))
            device_await_cols.extend(self._get_device_columns_safe('accounts', 'avg_await'))
        
        # 构建绘图配置
        plot_configs = []
        
        for util_col in device_util_cols:
            device_name = util_col.split('_')[0].upper()
            plot_configs.append((cpu_iowait_field, util_col, f'CPU I/O等待 vs {device_name}设备利用率'))
        
        for aqu_col in device_aqu_cols:
            device_name = aqu_col.split('_')[0].upper()
            plot_configs.append((cpu_iowait_field, aqu_col, f'CPU I/O等待 vs {device_name}设备队列长度'))
        
        for await_col in device_await_cols:
            device_name = await_col.split('_')[0].upper()
            plot_configs.append((cpu_iowait_field, await_col, f'CPU I/O等待 vs {device_name}设备延迟'))
        
        if not plot_configs:
            print("  ⚠️ 没有配置的设备，跳过Pearson相关性图表生成")
            return []
        
        # 动态创建子图布局
        total_plots = len(plot_configs)
        if total_plots <= 3:
            rows, cols = 1, total_plots
        elif total_plots <= 6:
            rows, cols = 2, 3
        else:
            rows, cols = 2, 4
        
        fig, axes = plt.subplots(rows, cols, figsize=(5*cols, 5*rows))
        
        # 确保axes始终是二维数组，便于统一处理
        if total_plots == 1:
            axes = np.array([[axes]])
        elif rows == 1:
            axes = axes.reshape(1, -1)
        elif cols == 1:
            axes = axes.reshape(-1, 1)
        
        fig.suptitle('CPU-EBS Pearson相关性分析', fontsize=16, fontweight='bold')
        
        # 生成每个子图
        plot_idx = 0
        for i in range(rows):
            for j in range(cols):
                if plot_idx < len(plot_configs):
                    cpu_col, ebs_col, title = plot_configs[plot_idx]
                    ax: Axes = axes[i, j]  # 类型注解：明确指定为 matplotlib Axes 对象
                    
                    try:
                        # 安全获取数据
                        cpu_data = self.df.get('cpu_iowait', pd.Series(dtype=float))
                        ebs_data = self.df[ebs_col] if ebs_col in self.df.columns else pd.Series(dtype=float)
                        
                        if len(cpu_data) > 0 and len(ebs_data) > 0:
                            # 计算相关性
                            corr, p_value = stats.pearsonr(cpu_data, ebs_data)
                            
                            # 绘制散点图
                            ax.scatter(cpu_data, ebs_data, alpha=0.6, s=20)
                            
                            # 添加趋势线
                            z = np.polyfit(cpu_data, ebs_data, 1)
                            p = np.poly1d(z)
                            ax.plot(cpu_data, p(cpu_data), "r--", alpha=0.8)
                            
                            ax.set_xlabel('CPU I/O等待 (%)')
                            ax.set_ylabel(ebs_col.replace('_', ' ').title())
                            ax.set_title(f'{title}\nr={corr:.3f}, p={p_value:.3f}')
                            ax.grid(True, alpha=0.3)
                        else:
                            ax.text(0.5, 0.5, '数据不足', ha='center', va='center', transform=ax.transAxes)
                            ax.set_title(title)
                    
                    except Exception as e:
                        print(f"⚠️ 生成子图失败: {e}")
                        ax.text(0.5, 0.5, f'生成失败\n{str(e)}', ha='center', va='center', transform=ax.transAxes)
                        ax.set_title(title)
                    
                    plot_idx += 1
                else:
                    # 隐藏多余的子图
                    axes[i, j].set_visible(False)
        
        plt.tight_layout()
        
        # 保存图表
        output_file = os.path.join(self.output_dir, 'pearson_correlation_analysis.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        chart_files.append(output_file)
        print(f"✅ Pearson相关性图表已保存: {output_file}")
        
        return chart_files
        
    def generate_regression_analysis_charts(self) -> List[str]:
        """生成回归分析图表"""
        if not self.load_data():
            return []
        
        print("📈 生成回归分析图表...")
        chart_files = []
        
        # 检查设备配置
        data_configured = self._check_device_configured('data')
        accounts_configured = self._check_device_configured('accounts')
        
        # 使用安全的列获取方法
        data_r_cols = self._get_device_columns_safe('data', '_r_s')
        data_w_cols = self._get_device_columns_safe('data', '_w_s')
        accounts_r_cols = self._get_device_columns_safe('accounts', '_r_s')
        accounts_w_cols = self._get_device_columns_safe('accounts', '_w_s')
        
        # 构建回归配置
        regression_configs = []
        if data_configured and data_r_cols:
            regression_configs.append(('cpu_usr', data_r_cols[0], 'User CPU vs DATA读请求'))
        if data_configured and data_w_cols:
            regression_configs.append(('cpu_sys', data_w_cols[0], 'System CPU vs DATA写请求'))
        if accounts_configured and accounts_r_cols:
            regression_configs.append(('cpu_usr', accounts_r_cols[0], 'User CPU vs ACCOUNTS读请求'))
        if accounts_configured and accounts_w_cols:
            regression_configs.append(('cpu_sys', accounts_w_cols[0], 'System CPU vs ACCOUNTS写请求'))
        
        if not regression_configs:
            print("  ⚠️ 没有配置的设备，跳过回归分析图表生成")
            return []
        
        # 动态创建子图布局
        total_plots = len(regression_configs)
        if total_plots <= 2:
            rows, cols = 1, total_plots
        else:
            rows, cols = 2, 2
        
        fig, axes = plt.subplots(rows, cols, figsize=(8*cols, 6*rows))
        
        # 确保axes始终是二维数组，便于统一处理
        if total_plots == 1:
            axes = np.array([[axes]])
        elif rows == 1:
            axes = axes.reshape(1, -1)
        elif cols == 1:
            axes = axes.reshape(-1, 1)
        
        fig.suptitle('线性回归分析', fontsize=16, fontweight='bold')
        
        for idx, (x_col, y_col, title) in enumerate(regression_configs):
            row, col = divmod(idx, cols)
            ax: Axes = axes[row, col]  # 类型注解：明确指定为 matplotlib Axes 对象
            
            if x_col in self.df.columns and y_col and y_col in self.df.columns:
                # 准备数据
                X = self.df[[x_col]].values
                y = self.df[y_col].values
                
                # 线性回归
                model = LinearRegression()
                model.fit(X, y)
                y_pred = model.predict(X)
                
                # 计算R²
                r2 = model.score(X, y)
                
                # 绘制散点图和回归线
                ax.scatter(self.df[x_col], self.df[y_col], alpha=0.6, s=20)
                ax.plot(self.df[x_col], y_pred, 'r-', linewidth=2)
                
                # 设置标题和标签
                ax.set_title(f'{title}\nR²={r2:.3f}, 系数={model.coef_[0]:.3f}', fontsize=12)
                ax.set_xlabel(x_col.replace('_', ' ').title())
                ax.set_ylabel(y_col.replace('_', ' ').title())
                ax.grid(True, alpha=0.3)
                
                # 添加回归方程
                equation = f'y = {model.coef_[0]:.3f}x + {model.intercept_:.3f}'
                ax.text(0.05, 0.95, equation, transform=ax.transAxes,
                       bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.7))
            else:
                ax.text(0.5, 0.5, '数据不可用', ha='center', va='center', transform=ax.transAxes)
                ax.set_title(title, fontsize=12)
        
        plt.tight_layout()
        chart_file = os.path.join(self.output_dir, 'linear_regression_analysis.png')
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        chart_files.append(chart_file)
        print(f"  ✅ 线性回归图表: {os.path.basename(chart_file)}")
        
        return chart_files
    
    def generate_negative_correlation_charts(self) -> List[str]:
        """生成负相关分析图表"""
        if not self.load_data():
            return []
        
        print("📉 生成负相关分析图表...")
        chart_files = []
        
        # 检查设备配置
        data_configured = self._check_device_configured('data')
        accounts_configured = self._check_device_configured('accounts')
        
        # 使用安全的列获取方法
        data_aqu_cols = self._get_device_columns_safe('data', 'aqu_sz')
        accounts_aqu_cols = self._get_device_columns_safe('accounts', 'aqu_sz')
        
        # 构建负相关配置
        negative_configs = []
        if data_configured and data_aqu_cols:
            negative_configs.append(('cpu_idle', data_aqu_cols[0], 'CPU空闲 vs DATA队列长度'))
        if accounts_configured and accounts_aqu_cols:
            negative_configs.append(('cpu_idle', accounts_aqu_cols[0], 'CPU空闲 vs ACCOUNTS队列长度'))
        
        if not negative_configs:
            print("  ⚠️ 没有配置的设备，跳过负相关分析图表生成")
            return []
        
        # 动态创建子图布局
        total_plots = len(negative_configs)
        fig, axes = plt.subplots(1, total_plots, figsize=(8*total_plots, 6))
        
        # 确保axes始终是数组
        if total_plots == 1:
            axes = [axes]
        
        fig.suptitle('负相关分析', fontsize=16, fontweight='bold')
        
        for idx, (x_col, y_col, title) in enumerate(negative_configs):
            ax: Axes = axes[idx]  # 类型注解：明确指定为 matplotlib Axes 对象
            
            if x_col in self.df.columns and y_col and y_col in self.df.columns:
                # 计算相关性
                corr, p_value = stats.pearsonr(self.df[x_col], self.df[y_col])
                
                # 绘制散点图
                ax.scatter(self.df[x_col], self.df[y_col], alpha=0.6, s=20)
                
                # 添加回归线
                z = np.polyfit(self.df[x_col], self.df[y_col], 1)
                p = np.poly1d(z)
                ax.plot(self.df[x_col], p(self.df[x_col]), "r--", alpha=0.8)
                
                # 设置标题和标签
                correlation_type = "负相关" if corr < 0 else "正相关"
                ax.set_title(f'{title}\nr={corr:.3f} ({correlation_type})', fontsize=12)
                ax.set_xlabel(x_col.replace('_', ' ').title())
                ax.set_ylabel(y_col.replace('_', ' ').title())
                ax.grid(True, alpha=0.3)
                
                # 高亮负相关
                if corr < 0:
                    ax.text(0.05, 0.95, '✓ 负相关关系', transform=ax.transAxes,
                           bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.7))
                else:
                    ax.text(0.05, 0.95, '⚠ 非负相关', transform=ax.transAxes,
                           bbox=dict(boxstyle="round,pad=0.3", facecolor="orange", alpha=0.7))
            else:
                ax.text(0.5, 0.5, '数据不可用', ha='center', va='center', transform=ax.transAxes)
                ax.set_title(title, fontsize=12)
        
        plt.tight_layout()
        chart_file = os.path.join(self.output_dir, 'negative_correlation_analysis.png')
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        chart_files.append(chart_file)
        print(f"  ✅ 负相关分析图表: {os.path.basename(chart_file)}")
        
        return chart_files
    
    def generate_comprehensive_correlation_matrix(self) -> List[str]:
        """生成综合相关性矩阵热力图"""
        if not self.load_data():
            return []
        
        print("🔥 生成综合相关性矩阵...")
        chart_files = []
        
        # 选择关键列进行相关性分析
        key_columns = []
        
        # CPU相关列
        cpu_cols = ['cpu_usr', 'cpu_sys', 'cpu_iowait', 'cpu_idle', 'cpu_soft']
        for col in cpu_cols:
            if col in self.df.columns:
                key_columns.append(col)
        
        # EBS相关列
        ebs_patterns = ['util', 'aqu_sz', 'avg_await', 'r_s', 'w_s', 'total_iops', 'throughput_mibs']
        for pattern in ebs_patterns:
            matching_cols = [col for col in self.df.columns if pattern in col]
            key_columns.extend(matching_cols[:2])  # 最多取2个相关列
        
        # 移除重复并确保列存在
        key_columns = list(set(key_columns))
        key_columns = [col for col in key_columns if col in self.df.columns]
        
        if len(key_columns) < 4:
            print("  ⚠️ 可用列数不足，跳过相关性矩阵生成")
            return []
        
        # 计算相关性矩阵
        correlation_matrix = self.df[key_columns].corr()
        
        # 创建热力图
        plt.figure(figsize=(14, 12))
        
        # 使用自定义颜色映射
        mask = np.triu(np.ones_like(correlation_matrix, dtype=bool))
        
        sns.heatmap(correlation_matrix, 
                   mask=mask,
                   annot=True, 
                   cmap='RdBu_r', 
                   vmin=-1, 
                   vmax=1,
                   center=0,
                   square=True,
                   fmt='.3f',
                   cbar_kws={"shrink": .8})
        
        plt.title('CPU-EBS性能指标相关性矩阵', fontsize=16, fontweight='bold', pad=20)
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        
        plt.tight_layout()
        chart_file = os.path.join(self.output_dir, 'comprehensive_correlation_matrix.png')
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        chart_files.append(chart_file)
        print(f"  ✅ 综合相关性矩阵: {os.path.basename(chart_file)}")
        
        return chart_files
    
    def generate_performance_trend_analysis(self) -> List[str]:
        """生成性能趋势分析图表"""
        if not self.load_data():
            return []
        
        print("📈 生成性能趋势分析...")
        chart_files = []
        
        # 确保有时间戳列
        if 'timestamp' not in self.df.columns:
            print("  ⚠️ 缺少时间戳列，跳过趋势分析")
            return []
        
        # 转换时间戳
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        
        fig, axes = plt.subplots(3, 2, figsize=(18, 15))
        fig.suptitle('CPU-EBS性能趋势分析', fontsize=16, fontweight='bold')
        
        # CPU使用率趋势
        if 'cpu_iowait' in self.df.columns:
            axes[0, 0].plot(self.df['timestamp'], self.df['cpu_iowait'], 'b-', alpha=0.7)
            axes[0, 0].set_title('CPU I/O等待时间趋势')
            axes[0, 0].set_ylabel('I/O Wait (%)')
            axes[0, 0].grid(True, alpha=0.3)
        
        # EBS利用率趋势 - 使用统一的字段格式匹配
        util_cols = [col for col in self.df.columns if 
                    (col.startswith('data_') and col.endswith('_util')) or 
                    (col.startswith('accounts_') and col.endswith('_util'))]
        if util_cols:
            axes[0, 1].plot(self.df['timestamp'], self.df[util_cols[0]], 'r-', alpha=0.7)
            axes[0, 1].set_title('EBS设备利用率趋势')
            axes[0, 1].set_ylabel('Utilization (%)')
            axes[0, 1].grid(True, alpha=0.3)
        
        # IOPS趋势
        iops_cols = [col for col in self.df.columns if 'total_iops' in col]
        if iops_cols:
            axes[1, 0].plot(self.df['timestamp'], self.df[iops_cols[0]], 'g-', alpha=0.7)
            axes[1, 0].set_title('IOPS趋势')
            axes[1, 0].set_ylabel('IOPS')
            axes[1, 0].grid(True, alpha=0.3)
        
        # 吞吐量趋势
        throughput_cols = [col for col in self.df.columns if 'throughput' in col and 'mibs' in col]
        if throughput_cols:
            axes[1, 1].plot(self.df['timestamp'], self.df[throughput_cols[0]], 'm-', alpha=0.7)
            axes[1, 1].set_title('吞吐量趋势')
            axes[1, 1].set_ylabel('Throughput (MiB/s)')
            axes[1, 1].grid(True, alpha=0.3)
        
        # 延迟趋势
        await_cols = [col for col in self.df.columns if 'avg_await' in col]
        if await_cols:
            axes[2, 0].plot(self.df['timestamp'], self.df[await_cols[0]], 'orange', alpha=0.7)
            axes[2, 0].set_title('I/O延迟趋势')
            axes[2, 0].set_ylabel('Latency (ms)')
            axes[2, 0].grid(True, alpha=0.3)
        
        # 队列深度趋势
        queue_cols = [col for col in self.df.columns if 'aqu_sz' in col]
        if queue_cols:
            axes[2, 1].plot(self.df['timestamp'], self.df[queue_cols[0]], 'purple', alpha=0.7)
            axes[2, 1].set_title('I/O队列深度趋势')
            axes[2, 1].set_ylabel('Queue Depth')
            axes[2, 1].grid(True, alpha=0.3)
        
        # 格式化x轴
        for ax in axes.flat:
            ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        chart_file = os.path.join(self.output_dir, 'performance_trend_analysis.png')
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        chart_files.append(chart_file)
        print(f"  ✅ 性能趋势分析: {os.path.basename(chart_file)}")
        
        return chart_files
    
    def _get_correlation_strength(self, corr: float) -> str:
        """获取相关性强度描述"""
        abs_corr = abs(corr)
        if abs_corr >= 0.8:
            return "很强"
        elif abs_corr >= 0.6:
            return "强"
        elif abs_corr >= 0.4:
            return "中等"
        elif abs_corr >= 0.2:
            return "弱"
        else:
            return "很弱"
    
    def generate_ena_network_analysis_charts(self) -> List[str]:
        """生成ENA网络限制分析图表"""
        if not self.load_data():
            return []
        
        print("🌐 生成ENA网络限制分析图表...")
        chart_files = []
        
        # 检查是否有ENA数据
        ena_columns = [col for col in self.df.columns if col.startswith('ena_')]
        if not ena_columns:
            print("  ⚠️ 没有ENA网络数据，跳过ENA分析图表")
            return []
        
        # 检查时间戳列
        if 'timestamp' not in self.df.columns:
            print("  ⚠️ 缺少时间戳列，跳过ENA趋势分析")
            return []
        
        # 转换时间戳
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        
        # 生成ENA限制趋势图
        trend_chart = self._generate_ena_limitation_trends_chart()
        if trend_chart:
            chart_files.append(trend_chart)
        
        # 生成ENA连接容量图
        capacity_chart = self._generate_ena_connection_capacity_chart()
        if capacity_chart:
            chart_files.append(capacity_chart)
        
        # 生成ENA综合状态图
        comprehensive_chart = self._generate_ena_comprehensive_status_chart()
        if comprehensive_chart:
            chart_files.append(comprehensive_chart)
        
        return chart_files

    def _generate_ena_limitation_trends_chart(self):
        """生成ENA限制趋势图表"""
        try:
            # 定义ENA限制字段 (exceeded类型)
            limitation_fields = {
                'ena_pps_exceeded': {'label': 'PPS超限', 'color': 'red'},
                'ena_bw_in_exceeded': {'label': '入站带宽超限', 'color': 'orange'}, 
                'ena_bw_out_exceeded': {'label': '出站带宽超限', 'color': 'blue'},
                'ena_conntrack_exceeded': {'label': '连接跟踪超限', 'color': 'purple'},
                'ena_linklocal_exceeded': {'label': '本地代理超限', 'color': 'green'}
            }
            
            # 检查是否有任何限制数据
            has_limitation_data = False
            for field in limitation_fields.keys():
                if field in self.df.columns and self.df[field].max() > 0:
                    has_limitation_data = True
                    break
            
            if not has_limitation_data:
                print("  ℹ️ 未检测到ENA限制，跳过限制趋势图")
                return None
            
            # 创建图表
            fig, ax = plt.subplots(1, 1, figsize=(16, 8))
            
            # 绘制每个ENA限制指标的趋势线
            lines_plotted = 0
            for field, config in limitation_fields.items():
                if field in self.df.columns:
                    # 只显示有数据的字段 (最大值 > 0)
                    if self.df[field].max() > 0:
                        ax.plot(self.df['timestamp'], self.df[field], 
                               label=config['label'], 
                               color=config['color'],
                               linewidth=2,
                               marker='o',
                               markersize=3,
                               alpha=0.8)
                        lines_plotted += 1
            
            if lines_plotted == 0:
                plt.close()
                return None
            
            # 图表美化
            ax.set_title('🚨 ENA网络限制趋势分析', fontsize=16, fontweight='bold')
            ax.set_xlabel('时间', fontsize=12)
            ax.set_ylabel('限制触发次数 (累计)', fontsize=12)
            ax.legend(loc='upper left')
            ax.grid(True, alpha=0.3)
            
            # 时间轴格式化
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # 保存图表
            chart_file = os.path.join(self.output_dir, 'ena_limitation_trends.png')
            plt.savefig(chart_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  ✅ ENA限制趋势图已生成: {os.path.basename(chart_file)}")
            return chart_file
            
        except Exception as e:
            print(f"  ❌ ENA限制趋势图生成失败: {str(e)}")
            return None

    def _generate_ena_connection_capacity_chart(self):
        """生成ENA连接容量图表"""
        try:
            if 'ena_conntrack_available' not in self.df.columns:
                return None
            
            # 检查是否有连接容量数据
            if self.df['ena_conntrack_available'].max() == 0:
                print("  ℹ️ 无ENA连接容量数据，跳过连接容量图")
                return None
            
            # 创建图表
            fig, ax = plt.subplots(1, 1, figsize=(16, 6))
            
            # 绘制连接容量趋势
            ax.plot(self.df['timestamp'], self.df['ena_conntrack_available'], 
                   color='green', linewidth=2, marker='o', markersize=2, alpha=0.8)
            
            # 添加警告线 (连接容量不足阈值)
            warning_threshold = 10000
            ax.axhline(y=warning_threshold, color='red', linestyle='--', alpha=0.7, 
                      label=f'警告阈值 ({warning_threshold:,})')
            
            # 图表美化
            ax.set_title('🔗 ENA连接容量监控', fontsize=16, fontweight='bold')
            ax.set_xlabel('时间', fontsize=12)
            ax.set_ylabel('可用连接数', fontsize=12)
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            # 格式化Y轴数值
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:,.0f}'))
            
            # 时间轴格式化
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # 保存图表
            chart_file = os.path.join(self.output_dir, 'ena_connection_capacity.png')
            plt.savefig(chart_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  ✅ ENA连接容量图已生成: {os.path.basename(chart_file)}")
            return chart_file
            
        except Exception as e:
            print(f"  ❌ ENA连接容量图生成失败: {str(e)}")
            return None

    def _generate_ena_comprehensive_status_chart(self):
        """生成ENA综合状态图表"""
        try:
            # 检查是否有足够的ENA数据
            ena_fields = ['ena_pps_exceeded', 'ena_bw_in_exceeded', 'ena_bw_out_exceeded', 
                         'ena_conntrack_exceeded', 'ena_linklocal_exceeded', 'ena_conntrack_available']
            
            available_fields = [field for field in ena_fields if field in self.df.columns]
            if len(available_fields) < 3:
                return None
            
            # 创建2x2子图布局
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('🌐 ENA网络综合分析', fontsize=16, fontweight='bold')
            
            # 1. 限制类型分布 (左上)
            ax1 = axes[0, 0]
            limitation_counts = {}
            field_labels = {
                'ena_pps_exceeded': 'PPS超限',
                'ena_bw_in_exceeded': '入站带宽超限',
                'ena_bw_out_exceeded': '出站带宽超限',
                'ena_conntrack_exceeded': '连接跟踪超限',
                'ena_linklocal_exceeded': '本地代理超限'
            }
            
            for field, label in field_labels.items():
                if field in self.df.columns:
                    count = (self.df[field] > 0).sum()
                    if count > 0:
                        limitation_counts[label] = count
            
            if limitation_counts:
                ax1.pie(limitation_counts.values(), labels=limitation_counts.keys(), 
                       autopct='%1.1f%%', startangle=90)
                ax1.set_title('限制类型分布')
            else:
                ax1.text(0.5, 0.5, '未检测到网络限制', ha='center', va='center', 
                        transform=ax1.transAxes, fontsize=12)
                ax1.set_title('限制类型分布')
            
            # 2. 连接容量状态 (右上)
            ax2 = axes[0, 1]
            if 'ena_conntrack_available' in self.df.columns:
                capacity_data = self.df['ena_conntrack_available']
                ax2.hist(capacity_data, bins=20, alpha=0.7, color='green', edgecolor='black')
                ax2.axvline(capacity_data.mean(), color='red', linestyle='--', 
                           label=f'平均值: {capacity_data.mean():,.0f}')
                ax2.set_title('连接容量分布')
                ax2.set_xlabel('可用连接数')
                ax2.set_ylabel('频次')
                ax2.legend()
            else:
                ax2.text(0.5, 0.5, '无连接容量数据', ha='center', va='center', 
                        transform=ax2.transAxes, fontsize=12)
                ax2.set_title('连接容量分布')
            
            # 3. 限制严重程度时间线 (左下)
            ax3 = axes[1, 0]
            # 计算每个时间点的总限制严重程度
            severity_fields = ['ena_pps_exceeded', 'ena_bw_in_exceeded', 'ena_bw_out_exceeded', 
                              'ena_conntrack_exceeded', 'ena_linklocal_exceeded']
            
            severity_score = pd.Series(0, index=self.df.index)
            for field in severity_fields:
                if field in self.df.columns:
                    severity_score += (self.df[field] > 0).astype(int)
            
            if severity_score.max() > 0:
                ax3.plot(self.df['timestamp'], severity_score, color='red', linewidth=2)
                ax3.fill_between(self.df['timestamp'], severity_score, alpha=0.3, color='red')
                ax3.set_title('网络限制严重程度')
                ax3.set_xlabel('时间')
                ax3.set_ylabel('同时限制类型数')
                plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)
            else:
                ax3.text(0.5, 0.5, '无网络限制记录', ha='center', va='center', 
                        transform=ax3.transAxes, fontsize=12)
                ax3.set_title('网络限制严重程度')
            
            # 4. ENA状态汇总 (右下)
            ax4 = axes[1, 1]
            # 创建状态汇总表格
            summary_data = []
            for field in ena_fields:
                if field in self.df.columns:
                    if field == 'ena_conntrack_available':
                        summary_data.append([field_labels.get(field, field), 
                                           f'{self.df[field].mean():,.0f}', 
                                           f'{self.df[field].min():,.0f}'])
                    else:
                        max_val = self.df[field].max()
                        total_events = (self.df[field] > 0).sum()
                        summary_data.append([field_labels.get(field, field), 
                                           f'{max_val}', 
                                           f'{total_events}次'])
            
            if summary_data:
                table = ax4.table(cellText=summary_data,
                                colLabels=['指标', '最大值/平均值', '事件次数/最小值'],
                                cellLoc='center',
                                loc='center')
                table.auto_set_font_size(False)
                table.set_fontsize(9)
                table.scale(1.2, 1.5)
                ax4.axis('off')
                ax4.set_title('ENA状态汇总')
            else:
                ax4.text(0.5, 0.5, '无ENA数据', ha='center', va='center', 
                        transform=ax4.transAxes, fontsize=12)
                ax4.set_title('ENA状态汇总')
            
            plt.tight_layout()
            
            # 保存图表
            chart_file = os.path.join(self.output_dir, 'ena_comprehensive_status.png')
            plt.savefig(chart_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  ✅ ENA综合状态图已生成: {os.path.basename(chart_file)}")
            return chart_file
            
        except Exception as e:
            print(f"  ❌ ENA综合状态图生成失败: {str(e)}")
            return None
        
        return chart_files

    def generate_all_charts(self) -> List[str]:
        """生成所有图表"""
        print("🎨 开始生成完整的CPU-EBS相关性分析图表...")
        
        all_charts = []
        
        # 1. Pearson相关性图表 (6-8种，根据配置设备动态调整)
        all_charts.extend(self.generate_pearson_correlation_charts())
        
        # 2. 回归分析图表 (4种，根据配置设备动态调整)
        all_charts.extend(self.generate_regression_analysis_charts())
        
        # 3. 负相关分析图表 (2种，根据配置设备动态调整)
        all_charts.extend(self.generate_negative_correlation_charts())
        
        # 4. ENA网络限制分析图表 (新增)
        all_charts.extend(self.generate_ena_network_analysis_charts())
        
        # 5. 综合相关性矩阵
        all_charts.extend(self.generate_comprehensive_correlation_matrix())
        
        # 6. 性能趋势分析
        all_charts.extend(self.generate_performance_trend_analysis())
        
        # 新增: 相关性热力图
        all_charts.extend(self.generate_correlation_heatmap())
        
        print(f"\n🎉 图表生成完成！共生成 {len(all_charts)} 个图表文件:")
        for chart in all_charts:
            print(f"  📊 {os.path.basename(chart)}")
        
        return all_charts

    def generate_correlation_heatmap(self) -> List[str]:
        """
        生成性能指标相关性热力图
        基于现有的71个CSV字段映射生成全面的相关性分析
        """
        print("\n📊 生成相关性热力图...")
        
        try:
            # 选择数值型字段进行相关性分析
            numeric_cols = self.df.select_dtypes(include=[np.number]).columns.tolist()
            
            # 排除时间戳和一些不适合相关性分析的字段
            exclude_cols = ['timestamp', 'current_qps', 'test_duration']
            numeric_cols = [col for col in numeric_cols if col not in exclude_cols]
            
            if len(numeric_cols) < 2:
                print("⚠️  可用于相关性分析的数值字段不足")
                return []
            
            # 计算相关性矩阵
            correlation_data = self.df[numeric_cols].dropna()
            correlation_matrix = correlation_data.corr(method='pearson')
            
            # 创建热力图
            plt.figure(figsize=(16, 14))
            
            # 创建遮罩，只显示下三角
            mask = np.triu(np.ones_like(correlation_matrix, dtype=bool))
            
            # 生成热力图
            sns.heatmap(
                correlation_matrix, 
                mask=mask,
                annot=True, 
                fmt='.2f',
                cmap='RdYlBu_r', 
                center=0,
                square=True,
                cbar_kws={"shrink": .8},
                annot_kws={'size': 8}
            )
            
            plt.title('性能指标相关性热力图\nPerformance Metrics Correlation Heatmap', 
                     fontsize=16, fontweight='bold', pad=20)
            plt.xlabel('性能指标 Performance Metrics', fontsize=12)
            plt.ylabel('性能指标 Performance Metrics', fontsize=12)
            
            # 旋转标签以提高可读性
            plt.xticks(rotation=45, ha='right')
            plt.yticks(rotation=0)
            
            plt.tight_layout()
            
            # 保存图表
            chart_file = os.path.join(self.output_dir, 'performance_correlation_heatmap.png')
            plt.savefig(chart_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"  ✅ 相关性热力图: {os.path.basename(chart_file)}")
            
            # 生成强相关性分析报告
            self._generate_correlation_insights(correlation_matrix, chart_file)
            
            return [chart_file]
            
        except Exception as e:
            print(f"❌ 相关性热力图生成失败: {e}")
            return []

    def _generate_correlation_insights(self, correlation_matrix: pd.DataFrame, chart_file: str):
        """
        生成相关性洞察分析
        识别强相关和负相关的指标对
        """
        try:
            # 找出强相关性 (|r| > 0.7)
            strong_correlations = []
            
            for i in range(len(correlation_matrix.columns)):
                for j in range(i+1, len(correlation_matrix.columns)):
                    corr_value = correlation_matrix.iloc[i, j]
                    if abs(corr_value) > 0.7:
                        strong_correlations.append({
                            'metric1': correlation_matrix.columns[i],
                            'metric2': correlation_matrix.columns[j],
                            'correlation': corr_value,
                            'strength': 'Strong Positive' if corr_value > 0 else 'Strong Negative'
                        })
            
            # 按相关性强度排序
            strong_correlations.sort(key=lambda x: abs(x['correlation']), reverse=True)
            
            # 生成洞察报告
            insights_file = chart_file.replace('.png', '_insights.txt')
            with open(insights_file, 'w', encoding='utf-8') as f:
                f.write("性能指标相关性分析洞察报告\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"分析时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"分析指标数量: {len(correlation_matrix.columns)}\n")
                f.write(f"强相关性对数: {len(strong_correlations)}\n\n")
                
                if strong_correlations:
                    f.write("🔍 强相关性指标对 (|r| > 0.7):\n")
                    f.write("-" * 40 + "\n")
                    for i, corr in enumerate(strong_correlations[:10], 1):  # 只显示前10个
                        f.write(f"{i:2d}. {corr['metric1']} ↔ {corr['metric2']}\n")
                        f.write(f"    相关系数: {corr['correlation']:.3f} ({corr['strength']})\n\n")
                else:
                    f.write("未发现强相关性指标对 (|r| > 0.7)\n")
            
            print(f"  📋 相关性洞察: {os.path.basename(insights_file)}")
            
        except Exception as e:
            print(f"⚠️  相关性洞察生成失败: {e}")


# 使用示例
if __name__ == "__main__":
    print("🎨 高级图表生成器使用示例:")
    print("generator = AdvancedChartGenerator('performance_data.csv')")
    print("charts = generator.generate_all_charts()")
    print("# 生成包括相关性热力图在内的统计分析可视化图表")
