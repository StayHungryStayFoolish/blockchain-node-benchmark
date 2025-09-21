#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EBS专用图表生成器 - 完全独立的EBS性能分析模块
基于单一职责原则和模块化设计
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import os
from datetime import datetime

# Configure font support for cross-platform compatibility
def setup_font():
    """Configure matplotlib font for cross-platform compatibility"""
    # Use standard fonts that work across all platforms
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False
    print("✅ SUCCESS: EBS Charts using font: DejaVu Sans")
    return True

# Initialize font configuration
setup_font()

class EBSChartGenerator:
    # 统一的EBS图表文件命名规范
    CHART_FILES = {
        'capacity': 'ebs_aws_capacity_planning.png',
        'performance': 'ebs_iostat_performance.png',
        'correlation': 'ebs_bottleneck_correlation.png',
        'overview': 'ebs_performance_overview.png',
        'bottleneck': 'ebs_bottleneck_analysis.png',
        'comparison': 'ebs_aws_standard_comparison.png',
        'timeseries': 'ebs_time_series_analysis.png'
    }
    
    def __init__(self, data_source, output_dir=None):
        """智能构造函数 - 支持DataFrame和CSV路径"""
        if output_dir is None:
            output_dir = os.getenv('REPORTS_DIR', 'charts')
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # 智能识别输入类型
        if isinstance(data_source, str):
            # CSV文件路径 - 兼容performance_visualizer.py调用
            self.df = pd.read_csv(data_source)
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        else:
            # DataFrame对象 - 兼容report_generator.py调用
            self.df = data_source
        
        # AWS基准值配置 - 直接使用现有变量，避免框架膨胀
        self.data_baseline_iops = float(os.getenv('DATA_VOL_MAX_IOPS', '3000'))
        self.data_baseline_throughput = float(os.getenv('DATA_VOL_MAX_THROUGHPUT', '125'))
        
        # EBS瓶颈检测阈值配置（来自internal_config.sh）
        self.ebs_util_threshold = float(os.getenv('BOTTLENECK_EBS_UTIL_THRESHOLD', '90'))
        self.ebs_latency_threshold = float(os.getenv('BOTTLENECK_EBS_LATENCY_THRESHOLD', '50'))
        self.ebs_iops_threshold = float(os.getenv('BOTTLENECK_EBS_IOPS_THRESHOLD', '90'))
        self.ebs_throughput_threshold = float(os.getenv('BOTTLENECK_EBS_THROUGHPUT_THRESHOLD', '90'))
        
        # 添加EBS字段名称动态映射
        self.field_mapping = self._build_field_mapping()
    
    def _build_field_mapping(self):
        """构建EBS字段名称映射"""
        mapping = {}
        
        # 查找data设备字段
        for suffix in ['aws_standard_iops', 'aws_standard_throughput_mibs', 'util', 'aqu_sz']:
            expected_field = f'data_{suffix}'
            actual_field = self._find_field_by_pattern(f'data_.*_{suffix}')
            mapping[expected_field] = actual_field
        
        # 查找accounts设备字段
        for suffix in ['aws_standard_iops', 'aws_standard_throughput_mibs', 'util', 'aqu_sz']:
            expected_field = f'accounts_{suffix}'
            actual_field = self._find_field_by_pattern(f'accounts_.*_{suffix}')
            mapping[expected_field] = actual_field
            
        return mapping
    
    def _find_field_by_pattern(self, pattern):
        """根据模式查找实际字段名"""
        import re
        for col in self.df.columns:
            if re.match(pattern, col):
                return col
        return None
    
    def get_mapped_field(self, field_name):
        """获取映射后的实际字段名"""
        return self.field_mapping.get(field_name, field_name)
    
    def validate_data_completeness(self):
        """EBS数据完整性验证"""
        required_columns = [
            'data_aws_standard_iops', 'data_aws_standard_throughput_mibs',
            'data_util', 'data_aqu_sz'
        ]
        missing_columns = [col for col in required_columns if self.get_mapped_field(col) not in self.df.columns]
        if missing_columns:
            print(f"⚠️ WARNING: 缺失EBS数据列: {missing_columns}")
            return False
        return True
    
    def generate_all_ebs_charts(self):
        """生成所有EBS图表 - 统一入口"""
        if not self.validate_data_completeness():
            return []
            
        charts = []
        if self._has_ebs_data():
            charts.append(self._create_aws_capacity_analysis())
            charts.append(self._create_iostat_performance_analysis())
            charts.append(self._create_bottleneck_correlation_analysis())
            charts.append(self.generate_ebs_performance_overview())
            charts.append(self.generate_ebs_bottleneck_analysis())
            charts.append(self.generate_ebs_aws_standard_comparison())
            charts.append(self.generate_ebs_time_series())
        
        return [chart for chart in charts if chart]
    
    def _has_ebs_data(self):
        """检查EBS数据可用性"""
        required = ['data_total_iops', 'data_util', 'data_aqu_sz']
        return all(col in self.df.columns for col in required)
    
    def _create_aws_capacity_analysis(self):
        """AWS容量规划分析 - 多维度专业分析"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('AWS EBS Capacity Planning Analysis', fontsize=16, fontweight='bold')
        
        # 1. AWS标准IOPS利用率分析
        if 'data_aws_standard_iops' in self.df.columns:
            utilization = (self.df['data_aws_standard_iops'] / self.data_baseline_iops * 100).clip(0, 100)
            ax1.plot(self.df['timestamp'], utilization, label='IOPS Utilization', linewidth=2, color='blue')
            ax1.axhline(y=self.ebs_iops_threshold, color='red', linestyle='--', 
                       label=f'Critical: {self.ebs_iops_threshold}%')
            ax1.axhline(y=70, color='orange', linestyle='--', alpha=0.7, label='Warning: 70%')
            ax1.set_title('AWS Standard IOPS Capacity Utilization')
            ax1.set_ylabel('Utilization (%)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # 2. AWS标准Throughput利用率分析
        if 'data_aws_standard_throughput_mibs' in self.df.columns:
            throughput_util = (self.df['data_aws_standard_throughput_mibs'] / self.data_baseline_throughput * 100).clip(0, 100)
            ax2.plot(self.df['timestamp'], throughput_util, label='Throughput Utilization', linewidth=2, color='green')
            ax2.axhline(y=self.ebs_throughput_threshold, color='red', linestyle='--', 
                       label=f'Critical: {self.ebs_throughput_threshold}%')
            ax2.axhline(y=70, color='orange', linestyle='--', alpha=0.7, label='Warning: 70%')
            ax2.set_title('AWS Standard Throughput Capacity Utilization')
            ax2.set_ylabel('Utilization (%)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        
        # 3. 容量规划预测（基于趋势分析）
        if 'data_aws_standard_iops' in self.df.columns and len(self.df) > 10:
            # 计算IOPS增长趋势
            iops_values = self.df['data_aws_standard_iops'].rolling(window=10).mean()
            time_numeric = np.arange(len(iops_values))
            
            # 简单线性回归预测
            valid_mask = ~np.isnan(iops_values)
            if valid_mask.sum() > 5:
                coeffs = np.polyfit(time_numeric[valid_mask], iops_values[valid_mask], 1)
                trend_line = np.polyval(coeffs, time_numeric)
                
                ax3.plot(self.df['timestamp'], iops_values, label='IOPS Trend (10-min avg)', linewidth=2, color='blue')
                ax3.plot(self.df['timestamp'], trend_line, label='Linear Trend', linewidth=2, linestyle='--', color='red')
                ax3.axhline(y=self.data_baseline_iops, color='orange', linestyle=':', alpha=0.7, 
                           label=f'Baseline: {self.data_baseline_iops}')
                ax3.set_title('IOPS Capacity Planning Forecast')
                ax3.set_ylabel('AWS Standard IOPS')
                ax3.legend()
                ax3.grid(True, alpha=0.3)
        
        # 4. 容量利用率分布分析
        if 'data_aws_standard_iops' in self.df.columns:
            utilization_data = (self.df['data_aws_standard_iops'] / self.data_baseline_iops * 100).clip(0, 100)
            ax4.hist(utilization_data, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
            ax4.axvline(x=utilization_data.mean(), color='red', linestyle='--', 
                       label=f'Mean: {utilization_data.mean():.1f}%')
            ax4.axvline(x=self.ebs_iops_threshold, color='orange', linestyle='--', 
                       label=f'Threshold: {self.ebs_iops_threshold}%')
            ax4.set_title('IOPS Utilization Distribution')
            ax4.set_xlabel('Utilization (%)')
            ax4.set_ylabel('Frequency')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, self.CHART_FILES['capacity'])
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        return chart_path
    
    def _create_iostat_performance_analysis(self):
        """iostat性能分析 - 多维度专业分析"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('EBS iostat Performance Analysis', fontsize=16, fontweight='bold')
        
        # 1. IOPS性能分析（读写分离）
        if 'data_read_iops' in self.df.columns and 'data_write_iops' in self.df.columns:
            ax1.plot(self.df['timestamp'], self.df['data_read_iops'], 
                    label='Read IOPS', linewidth=2, color='blue', alpha=0.8)
            ax1.plot(self.df['timestamp'], self.df['data_write_iops'], 
                    label='Write IOPS', linewidth=2, color='red', alpha=0.8)
            if 'data_total_iops' in self.df.columns:
                ax1.plot(self.df['timestamp'], self.df['data_total_iops'], 
                        label='Total IOPS', linewidth=2, color='green', linestyle='--')
            ax1.set_title('IOPS Performance (Read/Write Breakdown)')
            ax1.set_ylabel('IOPS')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        elif 'data_total_iops' in self.df.columns:
            ax1.plot(self.df['timestamp'], self.df['data_total_iops'], 
                    label='Total IOPS', linewidth=2, color='blue')
            ax1.set_title('Total IOPS Performance')
            ax1.set_ylabel('IOPS')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # 2. Throughput性能分析（读写分离）
        if 'data_read_throughput_mibs' in self.df.columns and 'data_write_throughput_mibs' in self.df.columns:
            ax2.plot(self.df['timestamp'], self.df['data_read_throughput_mibs'], 
                    label='Read Throughput', linewidth=2, color='blue', alpha=0.8)
            ax2.plot(self.df['timestamp'], self.df['data_write_throughput_mibs'], 
                    label='Write Throughput', linewidth=2, color='red', alpha=0.8)
            if 'data_total_throughput_mibs' in self.df.columns:
                ax2.plot(self.df['timestamp'], self.df['data_total_throughput_mibs'], 
                        label='Total Throughput', linewidth=2, color='green', linestyle='--')
            ax2.set_title('Throughput Performance (Read/Write Breakdown)')
            ax2.set_ylabel('Throughput (MiB/s)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        
        # 3. 设备利用率和队列深度分析
        if 'data_util' in self.df.columns and 'data_aqu_sz' in self.df.columns:
            ax3_twin = ax3.twinx()
            
            ax3.plot(self.df['timestamp'], self.df['data_util'], 
                    label='Device Utilization', linewidth=2, color='blue')
            ax3.axhline(y=self.ebs_util_threshold, color='red', linestyle='--', alpha=0.7,
                       label=f'Util Threshold: {self.ebs_util_threshold}%')
            ax3.set_ylabel('Utilization (%)', color='blue')
            ax3.tick_params(axis='y', labelcolor='blue')
            
            ax3_twin.plot(self.df['timestamp'], self.df['data_aqu_sz'], 
                         label='Queue Depth', linewidth=2, color='red')
            ax3_twin.set_ylabel('Average Queue Size', color='red')
            ax3_twin.tick_params(axis='y', labelcolor='red')
            
            ax3.set_title('Device Utilization vs Queue Depth')
            
            # 合并图例
            lines1, labels1 = ax3.get_legend_handles_labels()
            lines2, labels2 = ax3_twin.get_legend_handles_labels()
            ax3.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
            ax3.grid(True, alpha=0.3)
        
        # 4. 延迟分析（读写分离）
        if 'data_r_await' in self.df.columns and 'data_w_await' in self.df.columns:
            ax4.plot(self.df['timestamp'], self.df['data_r_await'], 
                    label='Read Latency', linewidth=2, color='blue', alpha=0.8)
            ax4.plot(self.df['timestamp'], self.df['data_w_await'], 
                    label='Write Latency', linewidth=2, color='red', alpha=0.8)
            if 'data_avg_await' in self.df.columns:
                ax4.plot(self.df['timestamp'], self.df['data_avg_await'], 
                        label='Average Latency', linewidth=2, color='green', linestyle='--')
            
            ax4.axhline(y=self.ebs_latency_threshold, color='orange', linestyle='--', alpha=0.7,
                       label=f'Latency Threshold: {self.ebs_latency_threshold}ms')
            ax4.set_title('I/O Latency Analysis (Read/Write Breakdown)')
            ax4.set_ylabel('Latency (ms)')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, self.CHART_FILES['performance'])
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        return chart_path
    
    def _create_bottleneck_correlation_analysis(self):
        """瓶颈关联分析 - 多维度专业分析"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('EBS Bottleneck Correlation Analysis', fontsize=16, fontweight='bold')
        
        # 1. AWS标准利用率 vs 设备利用率关联
        if 'data_aws_standard_iops' in self.df.columns and 'data_util' in self.df.columns:
            aws_iops_util = (self.df['data_aws_standard_iops'] / self.data_baseline_iops * 100).clip(0, 100)
            
            # 颜色编码：根据延迟水平着色
            if 'data_avg_await' in self.df.columns:
                scatter = ax1.scatter(aws_iops_util, self.df['data_util'], 
                                    c=self.df['data_avg_await'], cmap='YlOrRd', 
                                    alpha=0.6, s=30)
                plt.colorbar(scatter, ax=ax1, label='Avg Latency (ms)')
            else:
                ax1.scatter(aws_iops_util, self.df['data_util'], alpha=0.6, s=30)
            
            ax1.axhline(y=self.ebs_util_threshold, color='red', linestyle='--', 
                       label=f'Device Util Threshold: {self.ebs_util_threshold}%')
            ax1.axvline(x=self.ebs_iops_threshold, color='orange', linestyle='--', 
                       label=f'AWS IOPS Threshold: {self.ebs_iops_threshold}%')
            ax1.set_xlabel('AWS Standard IOPS Utilization (%)')
            ax1.set_ylabel('Device Utilization (%)')
            ax1.set_title('AWS IOPS vs Device Utilization (colored by latency)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # 2. 队列深度 vs 延迟关联分析
        if 'data_aqu_sz' in self.df.columns and 'data_avg_await' in self.df.columns:
            # 颜色编码：根据设备利用率着色
            if 'data_util' in self.df.columns:
                scatter = ax2.scatter(self.df['data_aqu_sz'], self.df['data_avg_await'], 
                                    c=self.df['data_util'], cmap='viridis', 
                                    alpha=0.6, s=30)
                plt.colorbar(scatter, ax=ax2, label='Device Util (%)')
            else:
                ax2.scatter(self.df['data_aqu_sz'], self.df['data_avg_await'], alpha=0.6, s=30)
            
            ax2.axhline(y=self.ebs_latency_threshold, color='red', linestyle='--', 
                       label=f'Latency Threshold: {self.ebs_latency_threshold}ms')
            ax2.set_xlabel('Average Queue Size')
            ax2.set_ylabel('Average Latency (ms)')
            ax2.set_title('Queue Depth vs Latency Correlation (colored by utilization)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        
        # 3. IOPS vs Throughput效率分析
        if 'data_total_iops' in self.df.columns and 'data_total_throughput_mibs' in self.df.columns:
            # 计算每IOPS的平均数据量（效率指标）
            efficiency = np.where(self.df['data_total_iops'] > 0, 
                                 self.df['data_total_throughput_mibs'] * 1024 / self.df['data_total_iops'], 
                                 0)  # KiB per IOPS
            
            scatter = ax3.scatter(self.df['data_total_iops'], self.df['data_total_throughput_mibs'], 
                                c=efficiency, cmap='plasma', alpha=0.6, s=30)
            plt.colorbar(scatter, ax=ax3, label='KiB per IOPS')
            
            ax3.set_xlabel('Total IOPS')
            ax3.set_ylabel('Total Throughput (MiB/s)')
            ax3.set_title('IOPS vs Throughput Efficiency (colored by KiB/IOPS)')
            ax3.grid(True, alpha=0.3)
        
        # 4. 多维度瓶颈热力图
        if all(col in self.df.columns for col in ['data_util', 'data_avg_await', 'data_aqu_sz']):
            # 创建瓶颈评分矩阵
            util_score = (self.df['data_util'] / 100).clip(0, 1)
            latency_score = (self.df['data_avg_await'] / self.ebs_latency_threshold).clip(0, 2)
            queue_score = (self.df['data_aqu_sz'] / 10).clip(0, 1)  # 假设队列深度10为高值
            
            # 综合瓶颈评分
            bottleneck_score = (util_score + latency_score + queue_score) / 3
            
            # 时间序列热力图
            time_hours = self.df['timestamp'].dt.hour if hasattr(self.df['timestamp'], 'dt') else range(len(self.df))
            
            ax4.scatter(time_hours, bottleneck_score, c=bottleneck_score, 
                       cmap='Reds', alpha=0.7, s=40)
            ax4.axhline(y=1.0, color='orange', linestyle='--', alpha=0.7, label='High Risk')
            ax4.axhline(y=1.5, color='red', linestyle='--', alpha=0.7, label='Critical Risk')
            ax4.set_xlabel('Hour of Day' if hasattr(self.df['timestamp'], 'dt') else 'Time Index')
            ax4.set_ylabel('Composite Bottleneck Score')
            ax4.set_title('Multi-dimensional Bottleneck Risk Heatmap')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, self.CHART_FILES['correlation'])
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        return chart_path
    
    def generate_ebs_performance_overview(self):
        """EBS性能概览图表 - 多维度专业分析"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('EBS Performance Overview Dashboard', fontsize=16, fontweight='bold')
        
        # 1. AWS标准IOPS vs基准线（带利用率区间）
        if 'data_aws_standard_iops' in self.df.columns:
            ax1.plot(self.df['timestamp'], self.df['data_aws_standard_iops'], 
                    label='AWS Standard IOPS', linewidth=2, color='blue')
            ax1.axhline(y=self.data_baseline_iops, color='red', linestyle='--', alpha=0.7, 
                       label=f'Baseline: {self.data_baseline_iops}')
            
            # 添加利用率区间
            ax1.axhspan(0, self.data_baseline_iops * 0.7, alpha=0.1, color='green', label='Safe Zone')
            ax1.axhspan(self.data_baseline_iops * 0.7, self.data_baseline_iops * 0.9, 
                       alpha=0.1, color='yellow', label='Warning Zone')
            ax1.axhspan(self.data_baseline_iops * 0.9, self.data_baseline_iops * 1.2, 
                       alpha=0.1, color='red', label='Critical Zone')
            
            ax1.set_title('AWS Standard IOPS Performance Overview')
            ax1.set_ylabel('AWS Standard IOPS')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # 2. AWS标准Throughput vs基准线
        if 'data_aws_standard_throughput_mibs' in self.df.columns:
            ax2.plot(self.df['timestamp'], self.df['data_aws_standard_throughput_mibs'], 
                    label='AWS Standard Throughput', linewidth=2, color='green')
            ax2.axhline(y=self.data_baseline_throughput, color='red', linestyle='--', alpha=0.7, 
                       label=f'Baseline: {self.data_baseline_throughput} MiB/s')
            
            # 添加利用率区间
            ax2.axhspan(0, self.data_baseline_throughput * 0.7, alpha=0.1, color='green')
            ax2.axhspan(self.data_baseline_throughput * 0.7, self.data_baseline_throughput * 0.9, 
                       alpha=0.1, color='yellow')
            ax2.axhspan(self.data_baseline_throughput * 0.9, self.data_baseline_throughput * 1.2, 
                       alpha=0.1, color='red')
            
            ax2.set_title('AWS Standard Throughput Performance Overview')
            ax2.set_ylabel('AWS Standard Throughput (MiB/s)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        
        # 3. 综合性能指标仪表盘
        if all(col in self.df.columns for col in ['data_aws_standard_iops', 'data_util', 'data_avg_await']):
            # 计算综合性能评分
            iops_score = (self.df['data_aws_standard_iops'] / self.data_baseline_iops).clip(0, 1)
            util_score = (100 - self.df['data_util']) / 100  # 利用率越低越好
            latency_score = np.where(self.df['data_avg_await'] > 0, 
                                   (self.ebs_latency_threshold - self.df['data_avg_await']) / self.ebs_latency_threshold, 
                                   1).clip(0, 1)  # 延迟越低越好
            
            performance_score = (iops_score + util_score + latency_score) / 3 * 100
            
            ax3.plot(self.df['timestamp'], performance_score, 
                    label='Performance Score', linewidth=2, color='purple')
            ax3.axhline(y=80, color='green', linestyle='--', alpha=0.7, label='Excellent: 80+')
            ax3.axhline(y=60, color='orange', linestyle='--', alpha=0.7, label='Good: 60+')
            ax3.axhline(y=40, color='red', linestyle='--', alpha=0.7, label='Poor: <40')
            
            ax3.set_title('Composite Performance Score')
            ax3.set_ylabel('Performance Score (0-100)')
            ax3.set_ylim(0, 100)
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        
        # 4. 关键指标统计摘要
        ax4.axis('off')
        summary_text = "EBS Performance Summary:\n\n"
        
        if 'data_aws_standard_iops' in self.df.columns:
            iops_mean = self.df['data_aws_standard_iops'].mean()
            iops_max = self.df['data_aws_standard_iops'].max()
            iops_util = (iops_mean / self.data_baseline_iops * 100)
            summary_text += f"AWS Standard IOPS:\n"
            summary_text += f"  Average: {iops_mean:.1f} ({iops_util:.1f}% of baseline)\n"
            summary_text += f"  Peak: {iops_max:.1f}\n\n"
        
        if 'data_aws_standard_throughput_mibs' in self.df.columns:
            tp_mean = self.df['data_aws_standard_throughput_mibs'].mean()
            tp_max = self.df['data_aws_standard_throughput_mibs'].max()
            tp_util = (tp_mean / self.data_baseline_throughput * 100)
            summary_text += f"AWS Standard Throughput:\n"
            summary_text += f"  Average: {tp_mean:.1f} MiB/s ({tp_util:.1f}% of baseline)\n"
            summary_text += f"  Peak: {tp_max:.1f} MiB/s\n\n"
        
        if 'data_util' in self.df.columns:
            util_mean = self.df['data_util'].mean()
            util_max = self.df['data_util'].max()
            summary_text += f"Device Utilization:\n"
            summary_text += f"  Average: {util_mean:.1f}%\n"
            summary_text += f"  Peak: {util_max:.1f}%\n\n"
        
        if 'data_avg_await' in self.df.columns:
            latency_mean = self.df['data_avg_await'].mean()
            latency_max = self.df['data_avg_await'].max()
            summary_text += f"Average Latency:\n"
            summary_text += f"  Average: {latency_mean:.1f} ms\n"
            summary_text += f"  Peak: {latency_max:.1f} ms"
        
        ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes, fontsize=10, 
                verticalalignment='top',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.5))
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, self.CHART_FILES['overview'])
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        return chart_path
    
    def generate_ebs_bottleneck_analysis(self):
        """EBS瓶颈分析图表 - 多维度专业分析"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('EBS Bottleneck Analysis Dashboard', fontsize=16, fontweight='bold')
        
        # 1. IOPS瓶颈检测
        if 'data_aws_standard_iops' in self.df.columns:
            threshold_iops = self.data_baseline_iops * (self.ebs_iops_threshold / 100)
            ax1.plot(self.df['timestamp'], self.df['data_aws_standard_iops'], 
                    label='AWS Standard IOPS', linewidth=2, color='blue')
            ax1.axhline(y=threshold_iops, color='red', linestyle='--', 
                       label=f'Critical: {threshold_iops:.0f}')
            ax1.axhline(y=self.data_baseline_iops * 0.7, color='orange', linestyle='--', alpha=0.7,
                       label=f'Warning: {self.data_baseline_iops * 0.7:.0f}')
            
            # 标记瓶颈点
            bottleneck_points = self.df['data_aws_standard_iops'] > threshold_iops
            warning_points = (self.df['data_aws_standard_iops'] > self.data_baseline_iops * 0.7) & ~bottleneck_points
            
            if bottleneck_points.any():
                ax1.scatter(self.df.loc[bottleneck_points, 'timestamp'], 
                          self.df.loc[bottleneck_points, 'data_aws_standard_iops'],
                          color='red', s=50, marker='x', label='Critical Points', zorder=5)
            if warning_points.any():
                ax1.scatter(self.df.loc[warning_points, 'timestamp'], 
                          self.df.loc[warning_points, 'data_aws_standard_iops'],
                          color='orange', s=30, marker='o', alpha=0.7, label='Warning Points', zorder=4)
            
            ax1.set_title('IOPS Bottleneck Detection')
            ax1.set_ylabel('AWS Standard IOPS')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # 2. Throughput瓶颈检测
        if 'data_aws_standard_throughput_mibs' in self.df.columns:
            threshold_tp = self.data_baseline_throughput * (self.ebs_throughput_threshold / 100)
            ax2.plot(self.df['timestamp'], self.df['data_aws_standard_throughput_mibs'], 
                    label='AWS Standard Throughput', linewidth=2, color='green')
            ax2.axhline(y=threshold_tp, color='red', linestyle='--', 
                       label=f'Critical: {threshold_tp:.0f} MiB/s')
            ax2.axhline(y=self.data_baseline_throughput * 0.7, color='orange', linestyle='--', alpha=0.7,
                       label=f'Warning: {self.data_baseline_throughput * 0.7:.0f} MiB/s')
            
            # 标记瓶颈点
            tp_bottleneck = self.df['data_aws_standard_throughput_mibs'] > threshold_tp
            tp_warning = (self.df['data_aws_standard_throughput_mibs'] > self.data_baseline_throughput * 0.7) & ~tp_bottleneck
            
            if tp_bottleneck.any():
                ax2.scatter(self.df.loc[tp_bottleneck, 'timestamp'], 
                          self.df.loc[tp_bottleneck, 'data_aws_standard_throughput_mibs'],
                          color='red', s=50, marker='x', label='Critical Points', zorder=5)
            if tp_warning.any():
                ax2.scatter(self.df.loc[tp_warning, 'timestamp'], 
                          self.df.loc[tp_warning, 'data_aws_standard_throughput_mibs'],
                          color='orange', s=30, marker='o', alpha=0.7, label='Warning Points', zorder=4)
            
            ax2.set_title('Throughput Bottleneck Detection')
            ax2.set_ylabel('AWS Standard Throughput (MiB/s)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        
        # 3. 延迟瓶颈检测
        if 'data_avg_await' in self.df.columns:
            ax3.plot(self.df['timestamp'], self.df['data_avg_await'], 
                    label='Average Latency', linewidth=2, color='purple')
            ax3.axhline(y=self.ebs_latency_threshold, color='red', linestyle='--', 
                       label=f'Critical: {self.ebs_latency_threshold} ms')
            ax3.axhline(y=self.ebs_latency_threshold * 0.7, color='orange', linestyle='--', alpha=0.7,
                       label=f'Warning: {self.ebs_latency_threshold * 0.7:.0f} ms')
            
            # 标记延迟瓶颈点
            latency_bottleneck = self.df['data_avg_await'] > self.ebs_latency_threshold
            latency_warning = (self.df['data_avg_await'] > self.ebs_latency_threshold * 0.7) & ~latency_bottleneck
            
            if latency_bottleneck.any():
                ax3.scatter(self.df.loc[latency_bottleneck, 'timestamp'], 
                          self.df.loc[latency_bottleneck, 'data_avg_await'],
                          color='red', s=50, marker='x', label='Critical Points', zorder=5)
            if latency_warning.any():
                ax3.scatter(self.df.loc[latency_warning, 'timestamp'], 
                          self.df.loc[latency_warning, 'data_avg_await'],
                          color='orange', s=30, marker='o', alpha=0.7, label='Warning Points', zorder=4)
            
            ax3.set_title('Latency Bottleneck Detection')
            ax3.set_ylabel('Average Latency (ms)')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        
        # 4. 瓶颈统计摘要
        ax4.axis('off')
        summary_text = "Bottleneck Analysis Summary:\n\n"
        
        total_points = len(self.df)
        
        if 'data_aws_standard_iops' in self.df.columns:
            threshold_iops = self.data_baseline_iops * (self.ebs_iops_threshold / 100)
            iops_bottlenecks = (self.df['data_aws_standard_iops'] > threshold_iops).sum()
            iops_warnings = ((self.df['data_aws_standard_iops'] > self.data_baseline_iops * 0.7) & 
                           (self.df['data_aws_standard_iops'] <= threshold_iops)).sum()
            
            summary_text += f"IOPS Bottlenecks:\n"
            summary_text += f"  Critical: {iops_bottlenecks} ({iops_bottlenecks/total_points*100:.1f}%)\n"
            summary_text += f"  Warning: {iops_warnings} ({iops_warnings/total_points*100:.1f}%)\n\n"
        
        if 'data_aws_standard_throughput_mibs' in self.df.columns:
            threshold_tp = self.data_baseline_throughput * (self.ebs_throughput_threshold / 100)
            tp_bottlenecks = (self.df['data_aws_standard_throughput_mibs'] > threshold_tp).sum()
            tp_warnings = ((self.df['data_aws_standard_throughput_mibs'] > self.data_baseline_throughput * 0.7) & 
                         (self.df['data_aws_standard_throughput_mibs'] <= threshold_tp)).sum()
            
            summary_text += f"Throughput Bottlenecks:\n"
            summary_text += f"  Critical: {tp_bottlenecks} ({tp_bottlenecks/total_points*100:.1f}%)\n"
            summary_text += f"  Warning: {tp_warnings} ({tp_warnings/total_points*100:.1f}%)\n\n"
        
        if 'data_avg_await' in self.df.columns:
            latency_bottlenecks = (self.df['data_avg_await'] > self.ebs_latency_threshold).sum()
            latency_warnings = ((self.df['data_avg_await'] > self.ebs_latency_threshold * 0.7) & 
                              (self.df['data_avg_await'] <= self.ebs_latency_threshold)).sum()
            
            summary_text += f"Latency Bottlenecks:\n"
            summary_text += f"  Critical: {latency_bottlenecks} ({latency_bottlenecks/total_points*100:.1f}%)\n"
            summary_text += f"  Warning: {latency_warnings} ({latency_warnings/total_points*100:.1f}%)\n\n"
        
        # 综合瓶颈评估
        if all(col in self.df.columns for col in ['data_aws_standard_iops', 'data_avg_await']):
            combined_bottlenecks = ((self.df['data_aws_standard_iops'] > self.data_baseline_iops * 0.9) | 
                                  (self.df['data_avg_await'] > self.ebs_latency_threshold)).sum()
            summary_text += f"Combined Bottlenecks:\n"
            summary_text += f"  Any Critical: {combined_bottlenecks} ({combined_bottlenecks/total_points*100:.1f}%)"
        
        ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes, fontsize=10, 
                verticalalignment='top',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightcoral", alpha=0.3))
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, self.CHART_FILES['bottleneck'])
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        return chart_path
    
    def generate_ebs_aws_standard_comparison(self):
        """AWS标准对比图表 - 多维度专业分析"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('AWS Standard vs Raw EBS Performance Comparison', fontsize=16, fontweight='bold')
        
        # 1. IOPS对比分析
        if 'data_aws_standard_iops' in self.df.columns and 'data_total_iops' in self.df.columns:
            ax1.plot(self.df['timestamp'], self.df['data_total_iops'], 
                    label='Raw IOPS', linewidth=2, alpha=0.7, color='lightblue')
            ax1.plot(self.df['timestamp'], self.df['data_aws_standard_iops'], 
                    label='AWS Standard IOPS', linewidth=2, color='blue')
            ax1.axhline(y=self.data_baseline_iops, color='red', linestyle='--', alpha=0.7,
                       label=f'AWS Baseline: {self.data_baseline_iops}')
            ax1.set_title('IOPS: AWS Standard vs Raw Performance')
            ax1.set_ylabel('IOPS')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # 2. Throughput对比分析
        if 'data_aws_standard_throughput_mibs' in self.df.columns and 'data_total_throughput_mibs' in self.df.columns:
            ax2.plot(self.df['timestamp'], self.df['data_total_throughput_mibs'], 
                    label='Raw Throughput', linewidth=2, alpha=0.7, color='lightgreen')
            ax2.plot(self.df['timestamp'], self.df['data_aws_standard_throughput_mibs'], 
                    label='AWS Standard Throughput', linewidth=2, color='green')
            ax2.axhline(y=self.data_baseline_throughput, color='red', linestyle='--', alpha=0.7,
                       label=f'AWS Baseline: {self.data_baseline_throughput} MiB/s')
            ax2.set_title('Throughput: AWS Standard vs Raw Performance')
            ax2.set_ylabel('Throughput (MiB/s)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        
        # 3. 转换效率分析（AWS标准化的影响）
        if all(col in self.df.columns for col in ['data_aws_standard_iops', 'data_total_iops']):
            # 计算转换比率
            conversion_ratio = np.where(self.df['data_total_iops'] > 0,
                                      self.df['data_aws_standard_iops'] / self.df['data_total_iops'],
                                      1)
            
            ax3.plot(self.df['timestamp'], conversion_ratio, 
                    label='AWS/Raw IOPS Ratio', linewidth=2, color='purple')
            ax3.axhline(y=1.0, color='gray', linestyle='--', alpha=0.7, label='1:1 Ratio')
            ax3.axhline(y=conversion_ratio.mean(), color='orange', linestyle='--', alpha=0.7,
                       label=f'Average: {conversion_ratio.mean():.2f}')
            
            ax3.set_title('AWS Standardization Impact (Conversion Ratio)')
            ax3.set_ylabel('AWS Standard / Raw IOPS')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        
        # 4. 性能差异统计分析
        ax4.axis('off')
        comparison_text = "AWS Standard vs Raw Comparison:\n\n"
        
        if all(col in self.df.columns for col in ['data_aws_standard_iops', 'data_total_iops']):
            raw_mean = self.df['data_total_iops'].mean()
            aws_mean = self.df['data_aws_standard_iops'].mean()
            iops_diff_pct = ((aws_mean - raw_mean) / raw_mean * 100) if raw_mean > 0 else 0
            
            comparison_text += f"IOPS Analysis:\n"
            comparison_text += f"  Raw Average: {raw_mean:.1f}\n"
            comparison_text += f"  AWS Standard Average: {aws_mean:.1f}\n"
            comparison_text += f"  Difference: {iops_diff_pct:+.1f}%\n\n"
        
        if all(col in self.df.columns for col in ['data_aws_standard_throughput_mibs', 'data_total_throughput_mibs']):
            raw_tp_mean = self.df['data_total_throughput_mibs'].mean()
            aws_tp_mean = self.df['data_aws_standard_throughput_mibs'].mean()
            tp_diff_pct = ((aws_tp_mean - raw_tp_mean) / raw_tp_mean * 100) if raw_tp_mean > 0 else 0
            
            comparison_text += f"Throughput Analysis:\n"
            comparison_text += f"  Raw Average: {raw_tp_mean:.1f} MiB/s\n"
            comparison_text += f"  AWS Standard Average: {aws_tp_mean:.1f} MiB/s\n"
            comparison_text += f"  Difference: {tp_diff_pct:+.1f}%\n\n"
        
        # 基准线利用率对比
        if 'data_aws_standard_iops' in self.df.columns:
            aws_utilization = (self.df['data_aws_standard_iops'] / self.data_baseline_iops * 100).mean()
            comparison_text += f"AWS Baseline Utilization:\n"
            comparison_text += f"  Average: {aws_utilization:.1f}%\n"
            
            if aws_utilization > 80:
                comparison_text += f"  Status: [HIGH] High utilization\n"
            elif aws_utilization > 60:
                comparison_text += f"  Status: [MOD] Moderate utilization\n"
            else:
                comparison_text += f"  Status: [LOW] Low utilization\n"
        
        ax4.text(0.05, 0.95, comparison_text, transform=ax4.transAxes, fontsize=10, 
                verticalalignment='top',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.3))
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, self.CHART_FILES['comparison'])
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        return chart_path
    
    def generate_ebs_time_series(self):
        """EBS时间序列图表 - 多维度专业分析"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('EBS Performance Time Series Analysis', fontsize=16, fontweight='bold')
        
        # 1. 多指标时间序列（标准化显示）
        if all(col in self.df.columns for col in ['data_aws_standard_iops', 'data_util', 'data_avg_await']):
            # 标准化数据到0-100范围便于比较
            iops_normalized = (self.df['data_aws_standard_iops'] / self.data_baseline_iops * 100).clip(0, 100)
            util_normalized = self.df['data_util']
            latency_normalized = (self.df['data_avg_await'] / self.ebs_latency_threshold * 100).clip(0, 200)
            
            ax1.plot(self.df['timestamp'], iops_normalized, 
                    label='IOPS Utilization (%)', linewidth=2, color='blue')
            ax1.plot(self.df['timestamp'], util_normalized, 
                    label='Device Utilization (%)', linewidth=2, color='green')
            ax1.plot(self.df['timestamp'], latency_normalized, 
                    label='Latency Score (%)', linewidth=2, color='red')
            
            ax1.axhline(y=100, color='gray', linestyle='--', alpha=0.5, label='100% Reference')
            ax1.set_title('Normalized Performance Metrics Over Time')
            ax1.set_ylabel('Normalized Score (%)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # 2. 滑动平均趋势分析
        if 'data_aws_standard_iops' in self.df.columns:
            window_size = min(20, len(self.df) // 5)  # 动态窗口大小
            if window_size > 1:
                rolling_mean = self.df['data_aws_standard_iops'].rolling(window=window_size).mean()
                rolling_std = self.df['data_aws_standard_iops'].rolling(window=window_size).std()
                
                ax2.plot(self.df['timestamp'], self.df['data_aws_standard_iops'], 
                        label='Raw IOPS', linewidth=1, alpha=0.5, color='lightblue')
                ax2.plot(self.df['timestamp'], rolling_mean, 
                        label=f'{window_size}-point Moving Average', linewidth=2, color='blue')
                
                # 添加置信区间
                ax2.fill_between(self.df['timestamp'], 
                               rolling_mean - rolling_std, 
                               rolling_mean + rolling_std,
                               alpha=0.2, color='blue', label='±1 Std Dev')
                
                ax2.axhline(y=self.data_baseline_iops, color='red', linestyle='--', alpha=0.7,
                           label=f'Baseline: {self.data_baseline_iops}')
                ax2.set_title('IOPS Trend Analysis with Moving Average')
                ax2.set_ylabel('AWS Standard IOPS')
                ax2.legend()
                ax2.grid(True, alpha=0.3)
        
        # 3. 性能模式识别（峰值、低谷分析）
        if 'data_aws_standard_iops' in self.df.columns and len(self.df) > 10:
            # 识别峰值和低谷
            try:
                from scipy.signal import find_peaks
                peaks, _ = find_peaks(self.df['data_aws_standard_iops'], 
                                    height=self.df['data_aws_standard_iops'].mean(),
                                    distance=5)
                valleys, _ = find_peaks(-self.df['data_aws_standard_iops'], 
                                      height=-self.df['data_aws_standard_iops'].mean(),
                                      distance=5)
                
                ax3.plot(self.df['timestamp'], self.df['data_aws_standard_iops'], 
                        label='AWS Standard IOPS', linewidth=2, color='blue')
                
                if len(peaks) > 0:
                    ax3.scatter(self.df.iloc[peaks]['timestamp'], 
                              self.df.iloc[peaks]['data_aws_standard_iops'],
                              color='red', s=50, marker='^', label='Peaks', zorder=5)
                
                if len(valleys) > 0:
                    ax3.scatter(self.df.iloc[valleys]['timestamp'], 
                              self.df.iloc[valleys]['data_aws_standard_iops'],
                              color='green', s=50, marker='v', label='Valleys', zorder=5)
                
                ax3.set_title('Performance Pattern Recognition')
                ax3.set_ylabel('AWS Standard IOPS')
                ax3.legend()
                ax3.grid(True, alpha=0.3)
                
            except ImportError:
                # 如果没有scipy，使用简单的峰值检测
                mean_val = self.df['data_aws_standard_iops'].mean()
                std_val = self.df['data_aws_standard_iops'].std()
                
                high_points = self.df['data_aws_standard_iops'] > (mean_val + std_val)
                low_points = self.df['data_aws_standard_iops'] < (mean_val - std_val)
                
                ax3.plot(self.df['timestamp'], self.df['data_aws_standard_iops'], 
                        label='AWS Standard IOPS', linewidth=2, color='blue')
                ax3.axhline(y=mean_val + std_val, color='red', linestyle='--', alpha=0.7,
                           label='High Threshold')
                ax3.axhline(y=mean_val - std_val, color='green', linestyle='--', alpha=0.7,
                           label='Low Threshold')
                
                if high_points.sum() > 0:
                    ax3.scatter(self.df.loc[high_points, 'timestamp'], 
                              self.df.loc[high_points, 'data_aws_standard_iops'],
                              color='red', s=30, alpha=0.7, label='High Points')
                
                if low_points.sum() > 0:
                    ax3.scatter(self.df.loc[low_points, 'timestamp'], 
                              self.df.loc[low_points, 'data_aws_standard_iops'],
                              color='green', s=30, alpha=0.7, label='Low Points')
                
                ax3.set_title('Performance Variation Analysis')
                ax3.set_ylabel('AWS Standard IOPS')
                ax3.legend()
                ax3.grid(True, alpha=0.3)
        
        # 4. 时间序列统计摘要
        ax4.axis('off')
        timeseries_text = "Time Series Analysis Summary:\n\n"
        
        if 'data_aws_standard_iops' in self.df.columns:
            iops_data = self.df['data_aws_standard_iops']
            timeseries_text += f"IOPS Statistics:\n"
            timeseries_text += f"  Mean: {iops_data.mean():.1f}\n"
            timeseries_text += f"  Std Dev: {iops_data.std():.1f}\n"
            timeseries_text += f"  Min: {iops_data.min():.1f}\n"
            timeseries_text += f"  Max: {iops_data.max():.1f}\n"
            timeseries_text += f"  Coefficient of Variation: {(iops_data.std()/iops_data.mean()*100):.1f}%\n\n"
        
        if 'data_util' in self.df.columns:
            util_data = self.df['data_util']
            timeseries_text += f"Utilization Statistics:\n"
            timeseries_text += f"  Mean: {util_data.mean():.1f}%\n"
            timeseries_text += f"  Peak: {util_data.max():.1f}%\n"
            timeseries_text += f"  >90% Time: {(util_data > 90).sum()/len(util_data)*100:.1f}%\n\n"
        
        if 'data_avg_await' in self.df.columns:
            latency_data = self.df['data_avg_await']
            timeseries_text += f"Latency Statistics:\n"
            timeseries_text += f"  Mean: {latency_data.mean():.1f} ms\n"
            timeseries_text += f"  95th Percentile: {latency_data.quantile(0.95):.1f} ms\n"
            timeseries_text += f"  >50ms Time: {(latency_data > 50).sum()/len(latency_data)*100:.1f}%"
        
        ax4.text(0.05, 0.95, timeseries_text, transform=ax4.transAxes, fontsize=10, 
                verticalalignment='top',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.5))
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, self.CHART_FILES['timeseries'])
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        return chart_path
    
    def validate_ebs_integration(self):
        """验证EBS功能完全分离后的集成正确性"""
        validation_results = {
            'data_completeness': self.validate_data_completeness(),
            'chart_files_defined': len(self.CHART_FILES) == 7,
            'output_dir_exists': os.path.exists(self.output_dir)
        }
        return all(validation_results.values())