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
from .chart_style_config import UnifiedChartStyle
from .device_manager import DeviceManager

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
        
        # 加载框架配置
        from .performance_visualizer import load_framework_config
        load_framework_config()
        
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
            # 确保timestamp是datetime类型
            if 'timestamp' in self.df.columns:
                self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        
        # AWS基准值配置 - 使用DeviceManager统一读取（修复问题8）
        temp_device_manager = DeviceManager(self.df) if hasattr(self, 'df') and self.df is not None else None
        if temp_device_manager:
            thresholds = temp_device_manager.get_threshold_values()
            self.data_baseline_iops = thresholds['data_baseline_iops']
            self.data_baseline_throughput = thresholds['data_baseline_throughput']
            
            # 只有在ACCOUNTS配置时才获取ACCOUNTS阈值
            if 'accounts_baseline_iops' in thresholds:
                self.accounts_baseline_iops = thresholds['accounts_baseline_iops']
                self.accounts_baseline_throughput = thresholds['accounts_baseline_throughput']
            else:
                # ACCOUNTS未配置时使用环境变量默认值
                self.accounts_baseline_iops = float(os.getenv('ACCOUNTS_VOL_MAX_IOPS', '20000'))
                self.accounts_baseline_throughput = float(os.getenv('ACCOUNTS_VOL_MAX_THROUGHPUT', '700'))
            
            self.ebs_util_threshold = thresholds['ebs_util_threshold']
            self.ebs_latency_threshold = thresholds['ebs_latency_threshold']
            self.ebs_iops_threshold = thresholds['ebs_iops_threshold']
            self.ebs_throughput_threshold = thresholds['ebs_throughput_threshold']
        else:
            # 回退到环境变量（保持兼容性）
            self.data_baseline_iops = float(os.getenv('DATA_VOL_MAX_IOPS', '20000'))
            self.data_baseline_throughput = float(os.getenv('DATA_VOL_MAX_THROUGHPUT', '700'))
            self.accounts_baseline_iops = float(os.getenv('ACCOUNTS_VOL_MAX_IOPS', '20000'))
            self.accounts_baseline_throughput = float(os.getenv('ACCOUNTS_VOL_MAX_THROUGHPUT', '700'))
            self.ebs_util_threshold = float(os.getenv('BOTTLENECK_EBS_UTIL_THRESHOLD', '90'))
            self.ebs_latency_threshold = float(os.getenv('BOTTLENECK_EBS_LATENCY_THRESHOLD', '50'))
            self.ebs_iops_threshold = float(os.getenv('BOTTLENECK_EBS_IOPS_THRESHOLD', '90'))
            self.ebs_throughput_threshold = float(os.getenv('BOTTLENECK_EBS_THROUGHPUT_THRESHOLD', '90'))
        
        # 添加框架统一方法
        self._init_framework_methods()
        
        # 应用统一样式配置
        try:
            from .chart_style_config import UnifiedChartStyle
            UnifiedChartStyle.setup_matplotlib()
        except ImportError:
            pass
    
    def _init_framework_methods(self):
        """初始化框架统一方法"""
        # 使用DeviceManager统一管理字段映射
        self.device_manager = DeviceManager(self.df)
        self.field_mapping = self.device_manager.build_field_mapping()
    
    def get_mapped_field(self, field_name):
        """获取映射后的实际字段名 - 委托给DeviceManager"""
        return self.device_manager.get_mapped_field(field_name)
    
    def get_field_data(self, field_name):
        """安全获取字段数据 - 委托给DeviceManager"""
        return self.device_manager.get_field_data(field_name)
    
    def has_field(self, field_name):
        """检查字段是否存在 - 委托给DeviceManager"""
        return self.device_manager.has_field(field_name)
    
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
        try:
            # 🎨 重构：应用统一样式配置
            from .chart_style_config import UnifiedChartStyle
            unified_style = UnifiedChartStyle()
            unified_style.setup_matplotlib()
            print("✅ 统一样式已应用到EBS图表")
            
            if not self.validate_data_completeness():
                print("⚠️ EBS data validation failed, skipping EBS charts")
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
        
        except Exception as e:
            print(f"❌ EBS charts generation failed: {e}")
            return []
    
    def _has_ebs_data(self):
        """检查EBS数据可用性 - 使用字段映射"""
        required = ['data_total_iops', 'data_util', 'data_aqu_sz']
        for field in required:
            mapped_field = self.get_mapped_field(field)
            if not mapped_field or mapped_field not in self.df.columns:
                return False
        return True
    
    def _create_aws_capacity_analysis(self):
        """AWS容量规划分析 - 多维度专业分析"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('AWS EBS Capacity Planning Analysis', fontsize=UnifiedChartStyle.FONT_CONFIG["title_size"], fontweight='bold')
        
        # 检查设备配置
        accounts_configured = self.device_manager.is_accounts_configured()
        
        # 1. AWS标准IOPS利用率分析 - 支持双设备
        data_iops_field = self.get_mapped_field('data_aws_standard_iops')
        if data_iops_field and data_iops_field in self.df.columns:
            utilization = (self.df[data_iops_field] / self.data_baseline_iops * 100).clip(0, 100)
            ax1.plot(self.df['timestamp'], utilization, label='DATA IOPS Utilization', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
            
            # ACCOUNTS设备IOPS利用率
            if accounts_configured:
                accounts_iops_field = self.get_mapped_field('accounts_aws_standard_iops')
                if accounts_iops_field and accounts_iops_field in self.df.columns:
                    accounts_utilization = (self.df[accounts_iops_field] / self.accounts_baseline_iops * 100).clip(0, 100)
                    ax1.plot(self.df['timestamp'], accounts_utilization, label='ACCOUNTS IOPS Utilization', linewidth=2, color=UnifiedChartStyle.COLORS["accounts_primary"])
            
            ax1.axhline(y=self.ebs_iops_threshold, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', 
                       label=f'Critical: {self.ebs_iops_threshold}%')
            ax1.axhline(y=70, color=UnifiedChartStyle.COLORS["accounts_primary"], linestyle='--', alpha=0.7, label='Warning: 70%')
            ax1.set_title('AWS Standard IOPS Capacity Utilization')
            ax1.set_ylabel('Utilization (%)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # 2. AWS标准Throughput利用率分析 - 支持双设备
        data_throughput_field = self.get_mapped_field('data_aws_standard_throughput_mibs')
        if data_throughput_field and data_throughput_field in self.df.columns:
            throughput_util = (self.df[data_throughput_field] / self.data_baseline_throughput * 100).clip(0, 100)
            ax2.plot(self.df['timestamp'], throughput_util, label='DATA Throughput Utilization', linewidth=2, color=UnifiedChartStyle.COLORS["success"])
            
            # ACCOUNTS设备Throughput利用率
            if accounts_configured:
                accounts_throughput_field = self.get_mapped_field('accounts_aws_standard_throughput_mibs')
                if accounts_throughput_field and accounts_throughput_field in self.df.columns:
                    accounts_tp_util = (self.df[accounts_throughput_field] / self.accounts_baseline_throughput * 100).clip(0, 100)
                    ax2.plot(self.df['timestamp'], accounts_tp_util, label='ACCOUNTS Throughput Utilization', linewidth=2, color='purple')
            
            ax2.axhline(y=self.ebs_throughput_threshold, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', 
                       label=f'Critical: {self.ebs_throughput_threshold}%')
            ax2.axhline(y=70, color=UnifiedChartStyle.COLORS["accounts_primary"], linestyle='--', alpha=0.7, label='Warning: 70%')
            ax2.set_title('AWS Standard Throughput Capacity Utilization')
            ax2.set_ylabel('Utilization (%)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        
        # 3. 容量规划预测（基于趋势分析）- 支持双设备
        if data_iops_field and len(self.df) > 10:
            # DATA设备IOPS趋势
            iops_values = self.df[data_iops_field].rolling(window=10).mean()
            time_numeric = np.arange(len(iops_values))
            
            # 简单线性回归预测
            valid_mask = ~np.isnan(iops_values)
            if valid_mask.sum() > 5:
                coeffs = np.polyfit(time_numeric[valid_mask], iops_values[valid_mask], 1)
                trend_line = np.polyval(coeffs, time_numeric)
                
                ax3.plot(self.df['timestamp'], iops_values, label='DATA IOPS Trend (10-min avg)', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
                ax3.plot(self.df['timestamp'], trend_line, label='DATA Linear Trend', linewidth=2, linestyle='--', color=UnifiedChartStyle.COLORS["critical"])
                ax3.axhline(y=self.data_baseline_iops, color=UnifiedChartStyle.COLORS["accounts_primary"], linestyle=':', alpha=0.7, 
                           label=f'DATA Baseline: {self.data_baseline_iops}')
                
                # ACCOUNTS设备IOPS趋势
                if accounts_configured:
                    accounts_iops_field = self.get_mapped_field('accounts_aws_standard_iops')
                    if accounts_iops_field and accounts_iops_field in self.df.columns:
                        accounts_iops_values = self.df[accounts_iops_field].rolling(window=10).mean()
                        accounts_valid_mask = ~np.isnan(accounts_iops_values)
                        if accounts_valid_mask.sum() > 5:
                            accounts_coeffs = np.polyfit(time_numeric[accounts_valid_mask], accounts_iops_values[accounts_valid_mask], 1)
                            accounts_trend_line = np.polyval(accounts_coeffs, time_numeric)
                            
                            ax3.plot(self.df['timestamp'], accounts_iops_values, label='ACCOUNTS IOPS Trend (10-min avg)', linewidth=2, color=UnifiedChartStyle.COLORS["success"])
                            ax3.plot(self.df['timestamp'], accounts_trend_line, label='ACCOUNTS Linear Trend', linewidth=2, linestyle='--', color='purple')
                            ax3.axhline(y=self.accounts_baseline_iops, color='cyan', linestyle=':', alpha=0.7, 
                                       label=f'ACCOUNTS Baseline: {self.accounts_baseline_iops}')
                
                ax3.set_title('IOPS Capacity Planning Forecast (DATA + ACCOUNTS)')
                ax3.set_ylabel('AWS Standard IOPS')
                ax3.legend(fontsize=UnifiedChartStyle.FONT_CONFIG["text_size"], ncol=2)
                ax3.grid(True, alpha=0.3)
        
        # 4. 容量利用率分布分析 - 支持双设备
        if data_iops_field:
            data_utilization = (self.df[data_iops_field] / self.data_baseline_iops * 100).clip(0, 100)
            ax4.hist(data_utilization, bins=20, alpha=0.7, color='skyblue', edgecolor='black', label='DATA Device')
            ax4.axvline(x=data_utilization.mean(), color=UnifiedChartStyle.COLORS["data_primary"], linestyle='--', 
                       label=f'DATA Mean: {data_utilization.mean():.1f}%')
            
            # ACCOUNTS设备利用率分布
            if accounts_configured:
                accounts_iops_field = self.get_mapped_field('accounts_aws_standard_iops')
                if accounts_iops_field and accounts_iops_field in self.df.columns:
                    accounts_utilization = (self.df[accounts_iops_field] / self.accounts_baseline_iops * 100).clip(0, 100)
                    ax4.hist(accounts_utilization, bins=20, alpha=0.7, color='lightcoral', edgecolor='black', label='ACCOUNTS Device')
                    ax4.axvline(x=accounts_utilization.mean(), color=UnifiedChartStyle.COLORS["critical"], linestyle='--', 
                               label=f'ACCOUNTS Mean: {accounts_utilization.mean():.1f}%')
            
            ax4.axvline(x=self.ebs_iops_threshold, color=UnifiedChartStyle.COLORS["accounts_primary"], linestyle='--', 
                       label=f'Threshold: {self.ebs_iops_threshold}%')
            ax4.set_title('IOPS Utilization Distribution (DATA + ACCOUNTS)')
            ax4.set_xlabel('Utilization (%)')
            ax4.set_ylabel('Frequency')
            ax4.legend(fontsize=UnifiedChartStyle.FONT_CONFIG["text_size"])
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, self.CHART_FILES['capacity'])
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        return chart_path
    
    def _create_iostat_performance_analysis(self):
        """iostat性能分析 - 多维度专业分析"""
        
        # 检查设备配置
        accounts_configured = self.device_manager.is_accounts_configured()
        
        # 使用框架统一标题函数
        from .performance_visualizer import create_chart_title
        title = create_chart_title('EBS iostat Performance Analysis', accounts_configured)
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(title, fontsize=UnifiedChartStyle.FONT_CONFIG["title_size"], fontweight='bold')
        
        # 1. IOPS性能分析（读写分离）- 支持双设备
        data_read_iops_field = self.get_mapped_field('data_read_iops')
        data_write_iops_field = self.get_mapped_field('data_write_iops')
        if data_read_iops_field and data_write_iops_field and data_read_iops_field in self.df.columns and data_write_iops_field in self.df.columns:
            ax1.plot(self.df['timestamp'], self.df[data_read_iops_field], 
                    label='DATA Read IOPS', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"], alpha=0.8)
            ax1.plot(self.df['timestamp'], self.df[data_write_iops_field], 
                    label='DATA Write IOPS', linewidth=2, color=UnifiedChartStyle.COLORS["critical"], alpha=0.8)
            
            # ACCOUNTS设备IOPS
            if accounts_configured:
                accounts_read_iops_field = self.get_mapped_field('accounts_read_iops')
                accounts_write_iops_field = self.get_mapped_field('accounts_write_iops')
                if accounts_read_iops_field and accounts_write_iops_field and accounts_read_iops_field in self.df.columns and accounts_write_iops_field in self.df.columns:
                    ax1.plot(self.df['timestamp'], self.df[accounts_read_iops_field], 
                            label='ACCOUNTS Read IOPS', linewidth=2, color=UnifiedChartStyle.COLORS["accounts_primary"], alpha=0.8)
                    ax1.plot(self.df['timestamp'], self.df[accounts_write_iops_field], 
                            label='ACCOUNTS Write IOPS', linewidth=2, color='purple', alpha=0.8)
            
            ax1.set_title('IOPS Performance (Read/Write Breakdown)')
            ax1.set_ylabel('IOPS')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        else:
            data_total_iops_field = self.get_mapped_field('data_total_iops')
            if data_total_iops_field and data_total_iops_field in self.df.columns:
                ax1.plot(self.df['timestamp'], self.df[data_total_iops_field], 
                        label='DATA Total IOPS', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
                
                # ACCOUNTS设备总IOPS
                if accounts_configured:
                    accounts_total_iops_field = self.get_mapped_field('accounts_total_iops')
                    if accounts_total_iops_field and accounts_total_iops_field in self.df.columns:
                        ax1.plot(self.df['timestamp'], self.df[accounts_total_iops_field], 
                                label='ACCOUNTS Total IOPS', linewidth=2, color=UnifiedChartStyle.COLORS["accounts_primary"])
            
            ax1.set_title('Total IOPS Performance')
            ax1.set_ylabel('IOPS')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # 2. Throughput性能分析（读写分离）- 支持双设备
        data_read_tp_field = self.get_mapped_field('data_read_throughput_mibs')
        data_write_tp_field = self.get_mapped_field('data_write_throughput_mibs')
        if data_read_tp_field and data_write_tp_field and data_read_tp_field in self.df.columns and data_write_tp_field in self.df.columns:
            ax2.plot(self.df['timestamp'], self.df[data_read_tp_field], 
                    label='DATA Read Throughput', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"], alpha=0.8)
            ax2.plot(self.df['timestamp'], self.df[data_write_tp_field], 
                    label='DATA Write Throughput', linewidth=2, color=UnifiedChartStyle.COLORS["critical"], alpha=0.8)
            
            # ACCOUNTS设备Throughput
            if accounts_configured:
                accounts_read_tp_field = self.get_mapped_field('accounts_read_throughput_mibs')
                accounts_write_tp_field = self.get_mapped_field('accounts_write_throughput_mibs')
                if accounts_read_tp_field and accounts_write_tp_field and accounts_read_tp_field in self.df.columns and accounts_write_tp_field in self.df.columns:
                    ax2.plot(self.df['timestamp'], self.df[accounts_read_tp_field], 
                            label='ACCOUNTS Read Throughput', linewidth=2, color=UnifiedChartStyle.COLORS["accounts_primary"], alpha=0.8)
                    ax2.plot(self.df['timestamp'], self.df[accounts_write_tp_field], 
                            label='ACCOUNTS Write Throughput', linewidth=2, color='purple', alpha=0.8)
            
            ax2.set_title('Throughput Performance (Read/Write Breakdown)')
            ax2.set_ylabel('Throughput (MiB/s)')
            # 修复图例重叠 - 使用更好的位置和较小字体
            ax2.legend(loc='upper left', fontsize=UnifiedChartStyle.FONT_CONFIG["legend_size"], ncol=2)
            ax2.grid(True, alpha=0.3)
        
        # 3. 设备利用率和队列深度分析 - 支持双设备
        data_util_field = self.get_mapped_field('data_util')
        data_aqu_field = self.get_mapped_field('data_aqu_sz')
        if data_util_field and data_aqu_field and data_util_field in self.df.columns and data_aqu_field in self.df.columns:
            ax3_twin = ax3.twinx()
            
            # DATA设备利用率和队列深度
            ax3.plot(self.df['timestamp'], self.df[data_util_field], 
                    label='DATA Device Utilization', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
            ax3_twin.plot(self.df['timestamp'], self.df[data_aqu_field], 
                         label='DATA Queue Depth', linewidth=2, color='lightblue')
            
            # ACCOUNTS设备利用率和队列深度
            if accounts_configured:
                accounts_util_field = self.get_mapped_field('accounts_util')
                accounts_aqu_field = self.get_mapped_field('accounts_aqu_sz')
                if accounts_util_field and accounts_aqu_field and accounts_util_field in self.df.columns and accounts_aqu_field in self.df.columns:
                    ax3.plot(self.df['timestamp'], self.df[accounts_util_field], 
                            label='ACCOUNTS Device Utilization', linewidth=2, color=UnifiedChartStyle.COLORS["accounts_primary"])
                    ax3_twin.plot(self.df['timestamp'], self.df[accounts_aqu_field], 
                                 label='ACCOUNTS Queue Depth', linewidth=2, color='lightsalmon')
            
            ax3.axhline(y=self.ebs_util_threshold, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', alpha=0.7,
                       label=f'Util Threshold: {self.ebs_util_threshold}%')
            ax3.set_ylabel('Utilization (%)', color=UnifiedChartStyle.COLORS["data_primary"])
            ax3.tick_params(axis='y', labelcolor=UnifiedChartStyle.COLORS["data_primary"])
            
            ax3_twin.set_ylabel('Average Queue Size', color='lightblue')
            ax3_twin.tick_params(axis='y', labelcolor='lightblue')
            
            ax3.set_title('Device Utilization vs Queue Depth')
            
            # 合并图例 - 使用紧凑布局
            lines1, labels1 = ax3.get_legend_handles_labels()
            lines2, labels2 = ax3_twin.get_legend_handles_labels()
            ax3.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=UnifiedChartStyle.FONT_CONFIG["text_size"])
            ax3.grid(True, alpha=0.3)
        
        # 4. 延迟分析（读写分离）- 支持双设备
        data_r_await_field = self.get_mapped_field('data_r_await')
        data_w_await_field = self.get_mapped_field('data_w_await')
        if data_r_await_field and data_w_await_field and data_r_await_field in self.df.columns and data_w_await_field in self.df.columns:
            # DATA设备延迟
            ax4.plot(self.df['timestamp'], self.df[data_r_await_field], 
                    label='DATA Read Latency', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"], alpha=0.8)
            ax4.plot(self.df['timestamp'], self.df[data_w_await_field], 
                    label='DATA Write Latency', linewidth=2, color=UnifiedChartStyle.COLORS["critical"], alpha=0.8)
            
            # ACCOUNTS设备延迟
            if accounts_configured:
                accounts_r_await_field = self.get_mapped_field('accounts_r_await')
                accounts_w_await_field = self.get_mapped_field('accounts_w_await')
                if accounts_r_await_field and accounts_w_await_field and accounts_r_await_field in self.df.columns and accounts_w_await_field in self.df.columns:
                    ax4.plot(self.df['timestamp'], self.df[accounts_r_await_field], 
                            label='ACCOUNTS Read Latency', linewidth=2, color=UnifiedChartStyle.COLORS["accounts_primary"], alpha=0.8)
                    ax4.plot(self.df['timestamp'], self.df[accounts_w_await_field], 
                            label='ACCOUNTS Write Latency', linewidth=2, color='purple', alpha=0.8)
            
            # 平均延迟线
            data_avg_await_field = self.get_mapped_field('data_avg_await')
            if data_avg_await_field and data_avg_await_field in self.df.columns:
                ax4.plot(self.df['timestamp'], self.df[data_avg_await_field], 
                        label='DATA Average Latency', linewidth=2, color=UnifiedChartStyle.COLORS["success"], linestyle='--')
            
            if accounts_configured:
                accounts_avg_await_field = self.get_mapped_field('accounts_avg_await')
                if accounts_avg_await_field and accounts_avg_await_field in self.df.columns:
                    ax4.plot(self.df['timestamp'], self.df[accounts_avg_await_field], 
                            label='ACCOUNTS Average Latency', linewidth=2, color='brown', linestyle='--')
            
            ax4.axhline(y=self.ebs_latency_threshold, color=UnifiedChartStyle.COLORS["accounts_primary"], linestyle='--', alpha=0.7,
                       label=f'Latency Threshold: {self.ebs_latency_threshold}ms')
            ax4.set_title('I/O Latency Analysis (Read/Write Breakdown)')
            ax4.set_ylabel('Latency (ms)')
            # 使用紧凑图例布局
            ax4.legend(loc='upper left', fontsize=UnifiedChartStyle.FONT_CONFIG["text_size"], ncol=2)
            ax4.grid(True, alpha=0.3)
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, self.CHART_FILES['performance'])
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        return chart_path
    
    def _create_bottleneck_correlation_analysis(self):
        """瓶颈关联分析 - 多维度专业分析"""
        
        # 检查设备配置
        accounts_configured = self.device_manager.is_accounts_configured()
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('EBS Bottleneck Correlation Analysis', fontsize=UnifiedChartStyle.FONT_CONFIG["title_size"], fontweight='bold')
        
        # 1. AWS标准利用率 vs 设备利用率关联 - 支持双设备
        data_iops_field = self.get_mapped_field('data_aws_standard_iops')
        data_util_field = self.get_mapped_field('data_util')
        if data_iops_field and data_iops_field in self.df.columns and data_util_field and data_util_field in self.df.columns:
            aws_iops_util = (self.df[data_iops_field] / self.data_baseline_iops * 100).clip(0, 100)
            
            # DATA设备散点图
            data_avg_await_field = self.get_mapped_field('data_avg_await')
            if data_avg_await_field and data_avg_await_field in self.df.columns:
                scatter = ax1.scatter(aws_iops_util, self.df[data_util_field], 
                                    c=self.df[data_avg_await_field], cmap='YlOrRd', 
                                    alpha=0.6, s=30, label='DATA Device')
                plt.colorbar(scatter, ax=ax1, label='Avg Latency (ms)')
            else:
                ax1.scatter(aws_iops_util, self.df[data_util_field], alpha=0.6, s=30, label='DATA Device')
            
            # ACCOUNTS设备散点图
            if accounts_configured:
                accounts_iops_field = self.get_mapped_field('accounts_aws_standard_iops')
                accounts_util_field = self.get_mapped_field('accounts_util')
                if accounts_iops_field and accounts_util_field and accounts_iops_field in self.df.columns and accounts_util_field in self.df.columns:
                    accounts_aws_iops_util = (self.df[accounts_iops_field] / self.accounts_baseline_iops * 100).clip(0, 100)
                    ax1.scatter(accounts_aws_iops_util, self.df[accounts_util_field], 
                               alpha=0.6, s=30, marker='^', color=UnifiedChartStyle.COLORS["accounts_primary"], label='ACCOUNTS Device')
            
            ax1.axhline(y=self.ebs_util_threshold, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', 
                       label=f'Device Util Threshold: {self.ebs_util_threshold}%')
            ax1.axvline(x=self.ebs_iops_threshold, color=UnifiedChartStyle.COLORS["accounts_primary"], linestyle='--', 
                       label=f'AWS IOPS Threshold: {self.ebs_iops_threshold}%')
            ax1.set_xlabel('AWS Standard IOPS Utilization (%)', fontsize=UnifiedChartStyle.FONT_CONFIG["label_size"])
            ax1.set_ylabel('Device Utilization (%)', fontsize=UnifiedChartStyle.FONT_CONFIG["label_size"])
            ax1.set_title('AWS IOPS vs Device Utilization', fontsize=UnifiedChartStyle.FONT_CONFIG["subtitle_size"])
            ax1.legend(fontsize=UnifiedChartStyle.FONT_CONFIG["legend_size"])
            ax1.grid(True, alpha=0.3)
        
        # 2. 队列深度 vs 延迟关联分析 - 支持双设备
        data_aqu_field = self.get_mapped_field('data_aqu_sz')
        data_avg_await_field = self.get_mapped_field('data_avg_await')
        if data_aqu_field and data_avg_await_field and data_aqu_field in self.df.columns and data_avg_await_field in self.df.columns:
            # DATA设备队列深度相关性
            if data_util_field and data_util_field in self.df.columns:
                scatter = ax2.scatter(self.df[data_aqu_field], self.df[data_avg_await_field], 
                                    c=self.df[data_util_field], cmap='viridis', 
                                    alpha=0.6, s=30, label='DATA Device')
                plt.colorbar(scatter, ax=ax2, label='Device Util (%)')
            else:
                ax2.scatter(self.df[data_aqu_field], self.df[data_avg_await_field], alpha=0.6, s=30, label='DATA Device')
            
            # ACCOUNTS设备队列深度相关性
            if accounts_configured:
                accounts_aqu_field = self.get_mapped_field('accounts_aqu_sz')
                accounts_avg_await_field = self.get_mapped_field('accounts_avg_await')
                if accounts_aqu_field and accounts_avg_await_field and accounts_aqu_field in self.df.columns and accounts_avg_await_field in self.df.columns:
                    ax2.scatter(self.df[accounts_aqu_field], self.df[accounts_avg_await_field], 
                               alpha=0.6, s=30, marker='^', color=UnifiedChartStyle.COLORS["accounts_primary"], label='ACCOUNTS Device')
            
            ax2.axhline(y=self.ebs_latency_threshold, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', 
                       label=f'Latency Threshold: {self.ebs_latency_threshold}ms')
            ax2.set_xlabel('Average Queue Size', fontsize=UnifiedChartStyle.FONT_CONFIG["label_size"])
            ax2.set_ylabel('Average Latency (ms)', fontsize=UnifiedChartStyle.FONT_CONFIG["label_size"])
            ax2.set_title('Queue Depth vs Latency Correlation', fontsize=UnifiedChartStyle.FONT_CONFIG["subtitle_size"])
            ax2.legend(fontsize=UnifiedChartStyle.FONT_CONFIG["legend_size"])
            ax2.grid(True, alpha=0.3)
        
        # 3. IOPS vs Throughput效率分析 - 支持双设备
        data_total_iops_field = self.get_mapped_field('data_total_iops')
        data_total_throughput_field = self.get_mapped_field('data_total_throughput_mibs')
        if data_total_iops_field and data_total_throughput_field and data_total_iops_field in self.df.columns and data_total_throughput_field in self.df.columns:
            # DATA设备效率分析
            efficiency = np.where(self.df[data_total_iops_field] > 0, 
                                 self.df[data_total_throughput_field] * 1024 / self.df[data_total_iops_field], 
                                 0)
            
            scatter = ax3.scatter(self.df[data_total_iops_field], self.df[data_total_throughput_field], 
                                c=efficiency, cmap='plasma', alpha=0.6, s=30, label='DATA Device')
            plt.colorbar(scatter, ax=ax3, label='KiB per IOPS')
            
            # ACCOUNTS设备效率分析
            if accounts_configured:
                accounts_total_iops_field = self.get_mapped_field('accounts_total_iops')
                accounts_total_throughput_field = self.get_mapped_field('accounts_total_throughput_mibs')
                if accounts_total_iops_field and accounts_total_throughput_field and accounts_total_iops_field in self.df.columns and accounts_total_throughput_field in self.df.columns:
                    ax3.scatter(self.df[accounts_total_iops_field], self.df[accounts_total_throughput_field], 
                               alpha=0.6, s=30, marker='^', color=UnifiedChartStyle.COLORS["accounts_primary"], label='ACCOUNTS Device')
            
            ax3.set_xlabel('Total IOPS', fontsize=UnifiedChartStyle.FONT_CONFIG["label_size"])
            ax3.set_ylabel('Total Throughput (MiB/s)', fontsize=UnifiedChartStyle.FONT_CONFIG["label_size"])
            ax3.set_title('IOPS vs Throughput Efficiency Analysis', fontsize=UnifiedChartStyle.FONT_CONFIG["subtitle_size"])
            ax3.legend(fontsize=UnifiedChartStyle.FONT_CONFIG["legend_size"])
            ax3.grid(True, alpha=0.3)
        
        # 4. 多维度瓶颈热力图
        data_util_field = self.get_mapped_field('data_util')
        data_avg_await_field = self.get_mapped_field('data_avg_await')
        data_aqu_field = self.get_mapped_field('data_aqu_sz')
        
        if (data_util_field and data_avg_await_field and data_aqu_field and 
            all(field in self.df.columns for field in [data_util_field, data_avg_await_field, data_aqu_field])):
            # 创建瓶颈评分矩阵
            util_score = (self.df[data_util_field] / 100).clip(0, 1)
            latency_score = (self.df[data_avg_await_field] / self.ebs_latency_threshold).clip(0, 2)
            queue_score = (self.df[data_aqu_field] / 10).clip(0, 1)  # 假设队列深度10为高值
            
            # 综合瓶颈评分
            bottleneck_score = (util_score + latency_score + queue_score) / 3
            
            # 时间序列热力图
            time_hours = self.df['timestamp'].dt.hour if hasattr(self.df['timestamp'], 'dt') else range(len(self.df))
            
            ax4.scatter(time_hours, bottleneck_score, c=bottleneck_score, 
                       cmap='Reds', alpha=0.7, s=40)
            ax4.axhline(y=1.0, color=UnifiedChartStyle.COLORS["accounts_primary"], linestyle='--', alpha=0.7, label='High Risk')
            ax4.axhline(y=1.5, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', alpha=0.7, label='Critical Risk')
            ax4.set_xlabel('Hour of Day' if hasattr(self.df['timestamp'], 'dt') else 'Time Index', fontsize=UnifiedChartStyle.FONT_CONFIG["label_size"])
            ax4.set_ylabel('Composite Bottleneck Score', fontsize=UnifiedChartStyle.FONT_CONFIG["label_size"])
            ax4.set_title('Multi-dimensional Bottleneck Risk Heatmap', fontsize=UnifiedChartStyle.FONT_CONFIG["subtitle_size"])
            ax4.legend(fontsize=UnifiedChartStyle.FONT_CONFIG["legend_size"])
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, self.CHART_FILES['correlation'])
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        return chart_path
    
    def generate_ebs_performance_overview(self):
        """EBS性能概览图表 - 支持DATA和ACCOUNTS双设备动态显示"""
        
        # 设备配置检测 - 使用统一方法
        data_configured = True
        accounts_configured = self.device_manager.is_accounts_configured()
        
        if not data_configured:
            print("❌ DATA设备数据未找到")
            return None
        
        # 动态标题
        title = 'EBS Performance Overview - DATA & ACCOUNTS Devices' if accounts_configured else 'EBS Performance Overview - DATA Device Only'
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(title, fontsize=UnifiedChartStyle.FONT_CONFIG["title_size"], fontweight='bold')
        
        # 1. AWS标准IOPS vs基准线（带利用率区间）
        data_iops_field = self.get_mapped_field('data_aws_standard_iops')
        if data_iops_field and data_iops_field in self.df.columns:
            ax1.plot(self.df['timestamp'], self.df[data_iops_field], 
                    label='DATA Device AWS Standard IOPS', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
            ax1.axhline(y=self.data_baseline_iops, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', alpha=0.7, 
                       label=f'DATA Baseline: {self.data_baseline_iops}')
            
            # ACCOUNTS设备数据叠加
            if accounts_configured:
                accounts_iops_field = self.get_mapped_field('accounts_aws_standard_iops')
                if accounts_iops_field and accounts_iops_field in self.df.columns:
                    ax1.plot(self.df['timestamp'], self.df[accounts_iops_field], 
                            label='ACCOUNTS Device AWS Standard IOPS', linewidth=2, color=UnifiedChartStyle.COLORS["accounts_primary"])
                    ax1.axhline(y=self.accounts_baseline_iops, color='purple', linestyle='--', alpha=0.7, 
                               label=f'ACCOUNTS Baseline: {self.accounts_baseline_iops}')
            
            ax1.set_title('AWS Standard IOPS Performance Overview')
            ax1.set_ylabel('AWS Standard IOPS')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # 2. AWS标准Throughput vs基准线
        data_throughput_field = self.get_mapped_field('data_aws_standard_throughput_mibs')
        if data_throughput_field and data_throughput_field in self.df.columns:
            ax2.plot(self.df['timestamp'], self.df[data_throughput_field], 
                    label='DATA Device AWS Standard Throughput', linewidth=2, color=UnifiedChartStyle.COLORS["success"])
            ax2.axhline(y=self.data_baseline_throughput, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', alpha=0.7, 
                       label=f'DATA Baseline: {self.data_baseline_throughput} MiB/s')
            
            # ACCOUNTS设备数据叠加
            if accounts_configured:
                accounts_throughput_field = self.get_mapped_field('accounts_aws_standard_throughput_mibs')
                if accounts_throughput_field and accounts_throughput_field in self.df.columns:
                    ax2.plot(self.df['timestamp'], self.df[accounts_throughput_field], 
                            label='ACCOUNTS Device AWS Standard Throughput', linewidth=2, color='purple')
                    ax2.axhline(y=self.accounts_baseline_throughput, color='purple', linestyle='--', alpha=0.7, 
                               label=f'ACCOUNTS Baseline: {self.accounts_baseline_throughput} MiB/s')
            
            ax2.set_title('AWS Standard Throughput Performance Overview')
            ax2.set_ylabel('AWS Standard Throughput (MiB/s)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        
        # 3. 设备利用率对比
        data_util_field = self.get_mapped_field('data_util')
        if data_util_field and data_util_field in self.df.columns:
            ax3.plot(self.df['timestamp'], self.df[data_util_field], 
                    label='DATA Device Utilization', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
            
            if accounts_configured:
                accounts_util_field = self.get_mapped_field('accounts_util')
                if accounts_util_field and accounts_util_field in self.df.columns:
                    ax3.plot(self.df['timestamp'], self.df[accounts_util_field], 
                            label='ACCOUNTS Device Utilization', linewidth=2, color=UnifiedChartStyle.COLORS["accounts_primary"])
            
            ax3.axhline(y=self.ebs_util_threshold, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', 
                       label=f'Critical: {self.ebs_util_threshold}%')
            ax3.set_title('Device Utilization Comparison')
            ax3.set_ylabel('Utilization (%)')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        
        # 4. 性能摘要 - 使用文本换行处理
        ax4.axis('off')
        summary_lines = ["EBS Performance Summary:", ""]
        
        if data_iops_field and data_iops_field in self.df.columns:
            iops_mean = self.df[data_iops_field].mean()
            iops_util = (iops_mean / self.data_baseline_iops * 100)
            summary_lines.extend([
                "DATA Device:",
                f"  Avg IOPS: {iops_mean:.1f}",
                f"  Utilization: {iops_util:.1f}%",
                f"  Baseline: {self.data_baseline_iops}",
                ""
            ])
        
        if accounts_configured:
            accounts_iops_field = self.get_mapped_field('accounts_aws_standard_iops')
            if accounts_iops_field and accounts_iops_field in self.df.columns:
                accounts_iops_mean = self.df[accounts_iops_field].mean()
                accounts_iops_util = (accounts_iops_mean / self.accounts_baseline_iops * 100)
                summary_lines.extend([
                    "ACCOUNTS Device:",
                    f"  Avg IOPS: {accounts_iops_mean:.1f}",
                    f"  Utilization: {accounts_iops_util:.1f}%",
                    f"  Baseline: {self.accounts_baseline_iops}"
                ])
        
        # 使用换行处理避免文本重叠
        summary_text = "\n".join(summary_lines)
        ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes, fontsize=UnifiedChartStyle.FONT_CONFIG["legend_size"], 
                verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.5))
        ax4.set_title('Performance Summary')
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, self.CHART_FILES['overview'])
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        print(f"✅ EBS Performance Overview saved: {os.path.basename(chart_path)} ({device_info} devices)")
        return chart_path
        
    def _is_accounts_configured(self):
        """统一的ACCOUNTS设备检测逻辑"""
        # 检查数据列是否存在（最可靠的方法）
        accounts_cols = [col for col in self.df.columns if col.startswith('accounts_')]
        return len(accounts_cols) > 0
    
    def generate_ebs_bottleneck_analysis(self):
        """EBS Bottleneck Analysis Chart - Dual Device Support"""
        
        # Device configuration detection - 使用统一方法
        data_configured = True
        accounts_configured = self.device_manager.is_accounts_configured()
        
        if not data_configured:
            print("❌ DATA device data not found")
            return None
        
        # Dynamic title
        title = 'EBS Bottleneck Analysis - DATA & ACCOUNTS Devices' if accounts_configured else 'EBS Bottleneck Analysis - DATA Device Only'
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(title, fontsize=UnifiedChartStyle.FONT_CONFIG["title_size"], fontweight='bold')
        
        # 1. IOPS Bottleneck Detection
        data_iops_field = self.get_mapped_field('data_aws_standard_iops')
        if data_iops_field and data_iops_field in self.df.columns:
            threshold_iops = self.data_baseline_iops * (self.ebs_iops_threshold / 100)
            ax1.plot(self.df['timestamp'], self.df[data_iops_field], 
                    label='DATA Device AWS Standard IOPS', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
            ax1.axhline(y=threshold_iops, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', 
                       label=f'DATA Critical: {threshold_iops:.0f}')
            ax1.axhline(y=self.data_baseline_iops * 0.7, color=UnifiedChartStyle.COLORS["accounts_primary"], linestyle='--', alpha=0.7,
                       label=f'DATA Warning: {self.data_baseline_iops * 0.7:.0f}')
            
            # ACCOUNTS device overlay
            if accounts_configured:
                accounts_iops_field = self.get_mapped_field('accounts_aws_standard_iops')
                if accounts_iops_field and accounts_iops_field in self.df.columns:
                    accounts_threshold_iops = self.accounts_baseline_iops * (self.ebs_iops_threshold / 100)
                    ax1.plot(self.df['timestamp'], self.df[accounts_iops_field], 
                            label='ACCOUNTS Device AWS Standard IOPS', linewidth=2, color=UnifiedChartStyle.COLORS["accounts_primary"])
                    ax1.axhline(y=accounts_threshold_iops, color='purple', linestyle='--', 
                               label=f'ACCOUNTS Critical: {accounts_threshold_iops:.0f}')
            
            # Mark bottleneck points
            bottleneck_points = self.df[data_iops_field] > threshold_iops
            if bottleneck_points.any():
                ax1.scatter(self.df.loc[bottleneck_points, 'timestamp'], 
                           self.df.loc[bottleneck_points, data_iops_field], 
                           color=UnifiedChartStyle.COLORS["critical"], s=30, alpha=0.7, label='DATA Bottleneck Points')
            
            ax1.set_title('IOPS Bottleneck Detection')
            ax1.set_ylabel('AWS Standard IOPS')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # 2. Throughput Bottleneck Detection  
        data_throughput_field = self.get_mapped_field('data_aws_standard_throughput_mibs')
        if data_throughput_field and data_throughput_field in self.df.columns:
            threshold_throughput = self.data_baseline_throughput * (self.ebs_throughput_threshold / 100)
            ax2.plot(self.df['timestamp'], self.df[data_throughput_field], 
                    label='DATA Device AWS Standard Throughput', linewidth=2, color=UnifiedChartStyle.COLORS["success"])
            ax2.axhline(y=threshold_throughput, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', 
                       label=f'DATA Critical: {threshold_throughput:.0f} MiB/s')
            
            # ACCOUNTS device overlay
            if accounts_configured:
                accounts_throughput_field = self.get_mapped_field('accounts_aws_standard_throughput_mibs')
                if accounts_throughput_field and accounts_throughput_field in self.df.columns:
                    accounts_threshold_throughput = self.accounts_baseline_throughput * (self.ebs_throughput_threshold / 100)
                    ax2.plot(self.df['timestamp'], self.df[accounts_throughput_field], 
                            label='ACCOUNTS Device AWS Standard Throughput', linewidth=2, color='purple')
                    ax2.axhline(y=accounts_threshold_throughput, color='purple', linestyle='--', 
                               label=f'ACCOUNTS Critical: {accounts_threshold_throughput:.0f} MiB/s')
            
            ax2.set_title('Throughput Bottleneck Detection')
            ax2.set_ylabel('AWS Standard Throughput (MiB/s)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        
        # 3. Utilization Bottleneck Detection
        data_util_field = self.get_mapped_field('data_util')
        if data_util_field and data_util_field in self.df.columns:
            ax3.plot(self.df['timestamp'], self.df[data_util_field], 
                    label='DATA Device Utilization', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
            ax3.axhline(y=self.ebs_util_threshold, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', 
                       label=f'Critical: {self.ebs_util_threshold}%')
            ax3.axhline(y=70, color=UnifiedChartStyle.COLORS["accounts_primary"], linestyle='--', alpha=0.7, label='Warning: 70%')
            
            # ACCOUNTS device overlay
            if accounts_configured:
                accounts_util_field = self.get_mapped_field('accounts_util')
                if accounts_util_field and accounts_util_field in self.df.columns:
                    ax3.plot(self.df['timestamp'], self.df[accounts_util_field], 
                            label='ACCOUNTS Device Utilization', linewidth=2, color=UnifiedChartStyle.COLORS["accounts_primary"])
            
            # Mark high utilization points
            high_util_points = self.df[data_util_field] > self.ebs_util_threshold
            if high_util_points.any():
                ax3.scatter(self.df.loc[high_util_points, 'timestamp'], 
                           self.df.loc[high_util_points, data_util_field], 
                           color=UnifiedChartStyle.COLORS["critical"], s=30, alpha=0.7, label='DATA High Utilization')
            
            ax3.set_title('Utilization Bottleneck Detection')
            ax3.set_ylabel('Utilization (%)')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        
        # 4. Latency Bottleneck Detection
        data_await_field = self.get_mapped_field('data_avg_await')
        if data_await_field and data_await_field in self.df.columns:
            ax4.plot(self.df['timestamp'], self.df[data_await_field], 
                    label='DATA Device Average Latency', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
            ax4.axhline(y=self.ebs_latency_threshold, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', 
                       label=f'Critical: {self.ebs_latency_threshold}ms')
            ax4.axhline(y=20, color=UnifiedChartStyle.COLORS["accounts_primary"], linestyle='--', alpha=0.7, label='Warning: 20ms')
            
            # ACCOUNTS device overlay
            if accounts_configured:
                accounts_await_field = self.get_mapped_field('accounts_avg_await')
                if accounts_await_field and accounts_await_field in self.df.columns:
                    ax4.plot(self.df['timestamp'], self.df[accounts_await_field], 
                            label='ACCOUNTS Device Average Latency', linewidth=2, color=UnifiedChartStyle.COLORS["accounts_primary"])
            
            ax4.set_title('Latency Bottleneck Detection')
            ax4.set_ylabel('Average Latency (ms)')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        
        # Format time axis elegantly - show HH:MM:SS only on all charts
        import matplotlib.dates as mdates
        
        for ax in [ax1, ax2, ax3, ax4]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, self.CHART_FILES['bottleneck'])
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        device_info = "DATA+ACCOUNTS" if accounts_configured else "DATA"
        print(f"✅ EBS Bottleneck Analysis saved: {os.path.basename(chart_path)} ({device_info} devices)")
        return chart_path
    
    def generate_ebs_aws_standard_comparison(self):
        """EBS AWS Standard Comparison Chart - Dual Device Support"""
        
        # Device configuration detection - 使用统一方法
        data_configured = True
        accounts_configured = self.device_manager.is_accounts_configured()
        
        if not data_configured:
            print("❌ DATA device data not found")
            return None
        
        # Dynamic title
        title = 'EBS AWS Standard Comparison - DATA & ACCOUNTS Devices' if accounts_configured else 'EBS AWS Standard Comparison - DATA Device Only'
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(title, fontsize=UnifiedChartStyle.FONT_CONFIG["title_size"], fontweight='bold')
        
        # 1. IOPS对比分析 - 支持双设备
        data_iops_field = self.get_mapped_field('data_aws_standard_iops')
        data_total_iops_field = self.get_mapped_field('data_total_iops')
        if data_iops_field and data_total_iops_field and data_iops_field in self.df.columns and data_total_iops_field in self.df.columns:
            ax1.plot(self.df['timestamp'], self.df[data_total_iops_field], 
                    label='DATA Raw IOPS', linewidth=2, alpha=0.7, color='lightblue')
            ax1.plot(self.df['timestamp'], self.df[data_iops_field], 
                    label='DATA AWS Standard IOPS', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
            
            # ACCOUNTS设备IOPS对比
            if accounts_configured:
                accounts_iops_field = self.get_mapped_field('accounts_aws_standard_iops')
                accounts_total_iops_field = self.get_mapped_field('accounts_total_iops')
                if accounts_iops_field and accounts_total_iops_field and accounts_iops_field in self.df.columns and accounts_total_iops_field in self.df.columns:
                    ax1.plot(self.df['timestamp'], self.df[accounts_total_iops_field], 
                            label='ACCOUNTS Raw IOPS', linewidth=2, alpha=0.7, color='lightsalmon')
                    ax1.plot(self.df['timestamp'], self.df[accounts_iops_field], 
                            label='ACCOUNTS AWS Standard IOPS', linewidth=2, color=UnifiedChartStyle.COLORS["accounts_primary"])
            
            ax1.axhline(y=self.data_baseline_iops, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', alpha=0.7,
                       label=f'DATA Baseline: {self.data_baseline_iops}')
            if accounts_configured:
                ax1.axhline(y=self.accounts_baseline_iops, color='purple', linestyle='--', alpha=0.7,
                           label=f'ACCOUNTS Baseline: {self.accounts_baseline_iops}')
            
            ax1.set_title('IOPS: AWS Standard vs Raw Performance')
            ax1.set_ylabel('IOPS')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # 2. Throughput对比分析 - 支持双设备
        data_throughput_field = self.get_mapped_field('data_aws_standard_throughput_mibs')
        data_total_throughput_field = self.get_mapped_field('data_total_throughput_mibs')
        if data_throughput_field and data_throughput_field in self.df.columns and data_total_throughput_field and data_total_throughput_field in self.df.columns:
            ax2.plot(self.df['timestamp'], self.df[data_total_throughput_field], 
                    label='DATA Raw Throughput', linewidth=2, alpha=0.7, color='lightgreen')
            ax2.plot(self.df['timestamp'], self.df[data_throughput_field], 
                    label='DATA AWS Standard Throughput', linewidth=2, color=UnifiedChartStyle.COLORS["success"])
            
            # ACCOUNTS设备Throughput对比
            if accounts_configured:
                accounts_throughput_field = self.get_mapped_field('accounts_aws_standard_throughput_mibs')
                accounts_total_throughput_field = self.get_mapped_field('accounts_total_throughput_mibs')
                if accounts_throughput_field and accounts_total_throughput_field and accounts_throughput_field in self.df.columns and accounts_total_throughput_field in self.df.columns:
                    ax2.plot(self.df['timestamp'], self.df[accounts_total_throughput_field], 
                            label='ACCOUNTS Raw Throughput', linewidth=2, alpha=0.7, color='lightcoral')
                    ax2.plot(self.df['timestamp'], self.df[accounts_throughput_field], 
                            label='ACCOUNTS AWS Standard Throughput', linewidth=2, color=UnifiedChartStyle.COLORS["critical"])
            
            ax2.axhline(y=self.data_baseline_throughput, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', alpha=0.7,
                       label=f'DATA Baseline: {self.data_baseline_throughput} MiB/s')
            if accounts_configured:
                ax2.axhline(y=self.accounts_baseline_throughput, color='purple', linestyle='--', alpha=0.7,
                           label=f'ACCOUNTS Baseline: {self.accounts_baseline_throughput} MiB/s')
            
            ax2.set_title('Throughput: AWS Standard vs Raw Performance')
            ax2.set_ylabel('Throughput (MiB/s)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        
        # 3. 转换效率分析（AWS标准化的影响）
        if all(col in self.df.columns for col in ['data_aws_standard_iops', 'data_total_iops']):
            # 计算转换比率
            conversion_ratio = np.where(self.df[data_total_iops_field] > 0,
                                      self.df[data_iops_field] / self.df[data_total_iops_field],
                                      1)
            
            ax3.plot(self.df['timestamp'], conversion_ratio, 
                    label='AWS/Raw IOPS Ratio', linewidth=2, color='purple')
            ax3.axhline(y=1.0, color='gray', linestyle='--', alpha=0.7, label='1:1 Ratio')
            ax3.axhline(y=conversion_ratio.mean(), color=UnifiedChartStyle.COLORS["accounts_primary"], linestyle='--', alpha=0.7,
                       label=f'Average: {conversion_ratio.mean():.2f}')
            
            ax3.set_title('AWS Standardization Impact (Conversion Ratio)')
            ax3.set_ylabel('AWS Standard / Raw IOPS')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        
        # 3. Performance Efficiency Analysis (Left Bottom - axes[1,0])
        data_iops_field = self.get_mapped_field('data_aws_standard_iops')
        data_throughput_field = self.get_mapped_field('data_aws_standard_throughput_mibs')
        
        if data_iops_field and data_throughput_field and all(field in self.df.columns for field in [data_iops_field, data_throughput_field]):
            # Calculate efficiency ratio (MiB/s per IOPS)
            efficiency = self.df[data_throughput_field] / (self.df[data_iops_field] + 1)  # +1 to avoid division by zero
            ax3.plot(self.df['timestamp'], efficiency, label='DATA Device Efficiency (MiB/IOPS)', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
            
            # ACCOUNTS device efficiency
            if accounts_configured:
                accounts_iops_field = self.get_mapped_field('accounts_aws_standard_iops')
                accounts_throughput_field = self.get_mapped_field('accounts_aws_standard_throughput_mibs')
                if all(field and field in self.df.columns for field in [accounts_iops_field, accounts_throughput_field]):
                    accounts_efficiency = self.df[accounts_throughput_field] / (self.df[accounts_iops_field] + 1)
                    ax3.plot(self.df['timestamp'], accounts_efficiency, 
                            label='ACCOUNTS Device Efficiency (MiB/IOPS)', linewidth=2, color=UnifiedChartStyle.COLORS["accounts_primary"])
            
            ax3.set_title('Performance Efficiency Analysis', fontsize=UnifiedChartStyle.FONT_CONFIG["subtitle_size"], fontweight='bold', pad=15)
            ax3.set_ylabel('Throughput per IOPS (MiB/IOPS)', fontsize=UnifiedChartStyle.FONT_CONFIG["subtitle_size"], fontweight='bold')
            ax3.set_xlabel('Time', fontsize=UnifiedChartStyle.FONT_CONFIG["subtitle_size"], fontweight='bold')
            ax3.legend(fontsize=UnifiedChartStyle.FONT_CONFIG["label_size"], frameon=True, fancybox=True, shadow=True)
            ax3.grid(True, alpha=0.3)
        
        # 4. Enhanced Capacity Utilization Summary
        ax4.axis('off')
        comparison_text = "AWS Standard vs Raw Comparison:\n\n"
        
        if data_iops_field and data_total_iops_field and all(self.get_mapped_field(f) in self.df.columns for f in ['data_aws_standard_iops', 'data_total_iops']):
            raw_mean = self.df[data_total_iops_field].mean()
            aws_mean = self.df[data_iops_field].mean()
            iops_diff_pct = ((aws_mean - raw_mean) / raw_mean * 100) if raw_mean > 0 else 0
            
            comparison_text += f"IOPS Analysis:\n"
            comparison_text += f"  Raw Average: {raw_mean:.1f}\n"
            comparison_text += f"  AWS Standard Average: {aws_mean:.1f}\n"
            comparison_text += f"  Difference: {iops_diff_pct:+.1f}%\n\n"
        
        if data_throughput_field and data_total_throughput_field and all(self.get_mapped_field(f) in self.df.columns for f in ['data_aws_standard_throughput_mibs', 'data_total_throughput_mibs']):
            raw_tp_mean = self.df[data_total_throughput_field].mean()
            aws_tp_mean = self.df[data_throughput_field].mean()
            tp_diff_pct = ((aws_tp_mean - raw_tp_mean) / raw_tp_mean * 100) if raw_tp_mean > 0 else 0
            
            comparison_text += f"Throughput Analysis:\n"
            comparison_text += f"  Raw Average: {raw_tp_mean:.1f} MiB/s\n"
            comparison_text += f"  AWS Standard Average: {aws_tp_mean:.1f} MiB/s\n"
            comparison_text += f"  Difference: {tp_diff_pct:+.1f}%\n\n"
        
        # 基准线利用率对比
        data_iops_field = self.get_mapped_field('data_aws_standard_iops')
        if data_iops_field and data_iops_field in self.df.columns:
            aws_utilization = (self.df[data_iops_field] / self.data_baseline_iops * 100).mean()
            comparison_text += f"AWS Baseline Utilization:\n"
            comparison_text += f"  Average: {aws_utilization:.1f}%\n"
            
            if aws_utilization > 80:
                comparison_text += f"  Status: [HIGH] High utilization\n"
            elif aws_utilization > 60:
                comparison_text += f"  Status: [MOD] Moderate utilization\n"
            else:
                comparison_text += f"  Status: [LOW] Low utilization\n"
        
        ax4.text(0.05, 0.95, comparison_text, transform=ax4.transAxes, fontsize=UnifiedChartStyle.FONT_CONFIG["label_size"], 
                verticalalignment='top',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue", alpha=0.3))
        
        plt.tight_layout()
        chart_path = os.path.join(self.output_dir, self.CHART_FILES['comparison'])
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        return chart_path
    
    def generate_ebs_time_series(self):
        """EBS Time Series Analysis Chart - Dual Device Support"""
        
        # Device configuration detection - 使用统一方法
        data_configured = True
        accounts_configured = self.device_manager.is_accounts_configured()
        
        if not data_configured:
            print("❌ DATA device data not found")
            return None
        
        # Dynamic title
        title = 'EBS Time Series Analysis - DATA & ACCOUNTS Devices' if accounts_configured else 'EBS Time Series Analysis - DATA Device Only'
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(title, fontsize=UnifiedChartStyle.FONT_CONFIG["title_size"], fontweight='bold')
        
        # 1. 多指标时间序列（标准化显示）
        data_iops_field = self.get_mapped_field('data_aws_standard_iops')
        data_util_field = self.get_mapped_field('data_util')
        data_avg_await_field = self.get_mapped_field('data_avg_await')
        
        if data_iops_field and data_util_field and data_avg_await_field and all(self.get_mapped_field(f) in self.df.columns for f in ['data_aws_standard_iops', 'data_util', 'data_avg_await']):
            # 标准化数据到0-100范围便于比较
            iops_normalized = (self.df[data_iops_field] / self.data_baseline_iops * 100).clip(0, 100)
            util_normalized = self.df[data_util_field]
            latency_normalized = (self.df[data_avg_await_field] / self.ebs_latency_threshold * 100).clip(0, 200)
            
            ax1.plot(self.df['timestamp'], iops_normalized, 
                    label='IOPS Utilization (%)', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
            ax1.plot(self.df['timestamp'], util_normalized, 
                    label='Device Utilization (%)', linewidth=2, color=UnifiedChartStyle.COLORS["success"])
            ax1.plot(self.df['timestamp'], latency_normalized, 
                    label='Latency Score (%)', linewidth=2, color=UnifiedChartStyle.COLORS["critical"])
            
            ax1.axhline(y=100, color='gray', linestyle='--', alpha=0.5, label='100% Reference')
            ax1.set_title('Normalized Performance Metrics Over Time')
            ax1.set_ylabel('Normalized Score (%)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # 2. 滑动平均趋势分析
        data_iops_field = self.get_mapped_field('data_aws_standard_iops')
        if data_iops_field and data_iops_field in self.df.columns:
            window_size = min(20, len(self.df) // 5)  # 动态窗口大小
            if window_size > 1:
                rolling_mean = self.df[data_iops_field].rolling(window=window_size).mean()
                rolling_std = self.df[data_iops_field].rolling(window=window_size).std()
                
                ax2.plot(self.df['timestamp'], self.df[data_iops_field], 
                        label='Raw IOPS', linewidth=1, alpha=0.5, color='lightblue')
                ax2.plot(self.df['timestamp'], rolling_mean, 
                        label=f'{window_size}-point Moving Average', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
                
                # 添加置信区间
                ax2.fill_between(self.df['timestamp'], 
                               rolling_mean - rolling_std, 
                               rolling_mean + rolling_std,
                               alpha=0.2, color=UnifiedChartStyle.COLORS["data_primary"], label='±1 Std Dev')
                
                ax2.axhline(y=self.data_baseline_iops, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', alpha=0.7,
                           label=f'Baseline: {self.data_baseline_iops}')
                ax2.set_title('IOPS Trend Analysis with Moving Average')
                ax2.set_ylabel('AWS Standard IOPS')
                ax2.legend()
                ax2.grid(True, alpha=0.3)
        
        # 3. 性能模式识别（峰值、低谷分析）
        if data_iops_field and len(self.df) > 10:
            # 识别峰值和低谷
            try:
                from scipy.signal import find_peaks
                peaks, _ = find_peaks(self.df[data_iops_field], 
                                    height=self.df[data_iops_field].mean(),
                                    distance=5)
                valleys, _ = find_peaks(-self.df[data_iops_field], 
                                      height=-self.df[data_iops_field].mean(),
                                      distance=5)
                
                ax3.plot(self.df['timestamp'], self.df[data_iops_field], 
                        label='AWS Standard IOPS', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
                
                if len(peaks) > 0:
                    ax3.scatter(self.df.iloc[peaks]['timestamp'], 
                              self.df.iloc[peaks][data_iops_field],
                              color=UnifiedChartStyle.COLORS["critical"], s=50, marker='^', label='Peaks', zorder=5)
                
                if len(valleys) > 0:
                    ax3.scatter(self.df.iloc[valleys]['timestamp'], 
                              self.df.iloc[valleys][data_iops_field],
                              color=UnifiedChartStyle.COLORS["success"], s=50, marker='v', label='Valleys', zorder=5)
                
                ax3.set_title('Performance Pattern Recognition')
                ax3.set_ylabel('AWS Standard IOPS')
                ax3.legend()
                ax3.grid(True, alpha=0.3)
                
            except ImportError:
                # 如果没有scipy，使用简单的峰值检测
                mean_val = self.df[data_iops_field].mean()
                std_val = self.df[data_iops_field].std()
                
                high_points = self.df[data_iops_field] > (mean_val + std_val)
                low_points = self.df[data_iops_field] < (mean_val - std_val)
                
                ax3.plot(self.df['timestamp'], self.df[data_iops_field], 
                        label='AWS Standard IOPS', linewidth=2, color=UnifiedChartStyle.COLORS["data_primary"])
                ax3.axhline(y=mean_val + std_val, color=UnifiedChartStyle.COLORS["critical"], linestyle='--', alpha=0.7,
                           label='High Threshold')
                ax3.axhline(y=mean_val - std_val, color=UnifiedChartStyle.COLORS["success"], linestyle='--', alpha=0.7,
                           label='Low Threshold')
                
                if high_points.any():
                    ax3.scatter(self.df.loc[high_points, 'timestamp'], 
                              self.df.loc[high_points, 'data_aws_standard_iops'],
                              color=UnifiedChartStyle.COLORS["critical"], s=30, alpha=0.7, label='High Points')
                
                if low_points.any():
                    ax3.scatter(self.df.loc[low_points, 'timestamp'], 
                              self.df.loc[low_points, 'data_aws_standard_iops'],
                              color=UnifiedChartStyle.COLORS["success"], s=30, alpha=0.7, label='Low Points')
                
                ax3.set_title('Performance Variation Analysis')
                ax3.set_ylabel('AWS Standard IOPS')
                ax3.legend()
                ax3.grid(True, alpha=0.3)
        
        # 4. 时间序列统计摘要
        ax4.axis('off')
        timeseries_text = "Time Series Analysis Summary:\n\n"
        
        data_iops_field = self.get_mapped_field('data_aws_standard_iops')
        if data_iops_field and data_iops_field in self.df.columns:
            iops_data = self.df[data_iops_field]
            timeseries_text += f"IOPS Statistics:\n"
            timeseries_text += f"  Mean: {iops_data.mean():.1f}\n"
            timeseries_text += f"  Std Dev: {iops_data.std():.1f}\n"
            timeseries_text += f"  Min: {iops_data.min():.1f}\n"
            timeseries_text += f"  Max: {iops_data.max():.1f}\n"
            timeseries_text += f"  Coefficient of Variation: {(iops_data.std()/iops_data.mean()*100):.1f}%\n\n"
        
        data_util_field = self.get_mapped_field('data_util')
        if data_util_field and data_util_field in self.df.columns:
            util_data = self.df[data_util_field]
            timeseries_text += f"Utilization Statistics:\n"
            timeseries_text += f"  Mean: {util_data.mean():.1f}%\n"
            timeseries_text += f"  Peak: {util_data.max():.1f}%\n"
            timeseries_text += f"  >90% Time: {(util_data > 90).sum()/len(util_data)*100:.1f}%\n\n"
        
        data_avg_await_field = self.get_mapped_field('data_avg_await')
        if data_avg_await_field and data_avg_await_field in self.df.columns:
            latency_data = self.df[data_avg_await_field]
            timeseries_text += f"Latency Statistics:\n"
            timeseries_text += f"  Mean: {latency_data.mean():.1f} ms\n"
            timeseries_text += f"  95th Percentile: {latency_data.quantile(0.95):.1f} ms\n"
            timeseries_text += f"  >50ms Time: {(latency_data > 50).sum()/len(latency_data)*100:.1f}%"
        
        ax4.text(0.05, 0.95, timeseries_text, transform=ax4.transAxes, fontsize=UnifiedChartStyle.FONT_CONFIG["label_size"], 
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