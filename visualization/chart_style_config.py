#!/usr/bin/env python3
"""
统一图表样式配置系统
解决字体、颜色、布局不一致的根本问题
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os

class UnifiedChartStyle:
    """统一图表样式配置"""
    
    # 统一字体配置
    FONT_CONFIG = {
        'title_size': 16,
        'subtitle_size': 12, 
        'label_size': 10,
        'legend_size': 9,
        'text_size': 8
    }
    
    # 统一颜色配置 - 扩展支持32张图表
    COLORS = {
        # 设备主色
        'data_primary': '#1f77b4',      # 蓝色 - DATA设备主色
        'accounts_primary': '#ff7f0e',   # 橙色 - ACCOUNTS设备主色
        
        # 状态颜色
        'warning': '#ff7f0e',           # 橙色 - 警告
        'critical': '#d62728',          # 红色 - 危险
        'success': '#2ca02c',           # 绿色 - 正常
        'info': '#17becf',              # 青色 - 信息
        
        # 图表元素颜色
        'grid': '#cccccc',              # 浅灰 - 网格
        'text_bg': 'lightgray',         # 浅灰 - 文本背景
        'threshold': '#d62728',         # 红色 - 阈值线
        'baseline': '#2ca02c',          # 绿色 - 基准线
        
        # 扩展调色板 - 支持多设备/多指标图表
        'purple': '#9467bd',            # 紫色
        'brown': '#8c564b',             # 棕色
        'pink': '#e377c2',              # 粉色
        'gray': '#7f7f7f',              # 灰色
        'olive': '#bcbd22',             # 橄榄色
        'cyan': '#17becf',              # 青色
        
        # 渐变色映射 - 热力图和散点图
        'heatmap_low': '#ffffcc',       # 浅黄
        'heatmap_mid': '#fd8d3c',       # 橙色
        'heatmap_high': '#800026',      # 深红
    }
    
    # 图表类型特定配置
    CHART_CONFIGS = {
        'scatter': {
            'alpha': 0.6,
            'size': 30,
            'marker': 'o'
        },
        'line': {
            'linewidth': 2,
            'alpha': 0.8
        },
        'pie': {
            'explode': (0.05, 0.05, 0.05, 0.05),  # 饼图分离度
            'autopct': '%1.1f%%',
            'startangle': 90
        },
        'histogram': {
            'bins': 20,
            'alpha': 0.7,
            'edgecolor': 'black'
        },
        'heatmap': {
            'cmap': 'RdYlBu_r',
            'annot': True,
            'fmt': '.2f'
        }
    }
    
    # colormap配置 - 覆盖实际使用的所有colormap
    COLORMAPS = {
        'correlation': 'RdBu_r',        # 相关性分析
        'performance': 'viridis',       # 性能分析  
        'bottleneck': 'Reds',           # 瓶颈分析
        'efficiency': 'plasma',         # 效率分析
        'trend': 'coolwarm',            # 趋势分析
        'latency': 'YlOrRd',            # 延迟分析 - EBS图表使用
        'utilization': 'viridis',       # 利用率分析 - EBS图表使用
        'heatmap': 'RdYlBu_r',          # 热力图 - 高级分析使用
    }
    
    # 散点图marker样式配置
    MARKERS = {
        'data_device': 'o',             # DATA设备 - 圆形
        'accounts_device': '^',         # ACCOUNTS设备 - 三角形
        'critical_point': 'x',          # 关键点 - X形
        'warning_point': 'o',           # 警告点 - 圆形
        'normal_point': '.',            # 正常点 - 点形
    }
    
    # 统一文本背景样式
    TEXT_BG_STYLE = {
        'boxstyle': "round,pad=0.3",
        'facecolor': 'lightgray',
        'alpha': 0.8
    }
    
    # 统一绘制层级
    Z_ORDER = {
        'grid': 1,          # 网格线 - 底层
        'threshold': 2,     # 阈值线 - 中层  
        'data': 3,          # 数据线 - 上层
        'annotation': 4     # 注释 - 顶层
    }
    
    @classmethod
    def setup_matplotlib(cls):
        """配置matplotlib全局样式"""
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['font.size'] = cls.FONT_CONFIG['label_size']
        plt.rcParams['axes.titlesize'] = cls.FONT_CONFIG['subtitle_size']
        plt.rcParams['axes.labelsize'] = cls.FONT_CONFIG['label_size']
        plt.rcParams['legend.fontsize'] = cls.FONT_CONFIG['legend_size']
        plt.rcParams['xtick.labelsize'] = cls.FONT_CONFIG['text_size']
        plt.rcParams['ytick.labelsize'] = cls.FONT_CONFIG['text_size']
        
    @classmethod
    def apply_axis_style(cls, ax, title=None):
        """应用统一的轴样式"""
        if title:
            ax.set_title(title, fontsize=cls.FONT_CONFIG['subtitle_size'])
        ax.grid(True, alpha=0.3, zorder=cls.Z_ORDER['grid'])
        ax.tick_params(axis='both', labelsize=cls.FONT_CONFIG['text_size'])
        
    @classmethod
    def add_text_with_bg(cls, ax, x, y, text, **kwargs):
        """添加带统一背景的文本"""
        default_kwargs = {
            'transform': ax.transAxes,
            'verticalalignment': 'top',
            'fontsize': cls.FONT_CONFIG['text_size'],
            'bbox': cls.TEXT_BG_STYLE
        }
        default_kwargs.update(kwargs)
        return ax.text(x, y, text, **default_kwargs)
        
    @classmethod
    def get_device_colors(cls, device_name):
        """获取设备专用颜色"""
        if device_name.lower() == 'data':
            return cls.COLORS['data_primary']
        elif device_name.lower() == 'accounts':
            return cls.COLORS['accounts_primary']
        else:
            return cls.COLORS['data_primary']
    
    @classmethod
    def get_chart_config(cls, chart_type):
        """获取图表类型特定配置"""
        return cls.CHART_CONFIGS.get(chart_type, {})
    
    @classmethod
    def get_colormap(cls, analysis_type):
        """获取分析类型对应的colormap"""
        return cls.COLORMAPS.get(analysis_type, 'viridis')
    
    @classmethod
    def get_marker(cls, marker_type):
        """获取标记类型对应的marker样式"""
        return cls.MARKERS.get(marker_type, 'o')
    
    @classmethod
    def get_scatter_config(cls, device_type='data', point_type='normal'):
        """获取散点图完整配置"""
        config = cls.CHART_CONFIGS['scatter'].copy()
        
        # 设备特定的marker
        if device_type == 'accounts':
            config['marker'] = cls.MARKERS['accounts_device']
        else:
            config['marker'] = cls.MARKERS['data_device']
            
        # 点类型特定的marker
        if point_type == 'critical':
            config['marker'] = cls.MARKERS['critical_point']
            config['size'] = 50
        elif point_type == 'warning':
            config['marker'] = cls.MARKERS['warning_point']
            config['size'] = 30
            
        return config
    
    @classmethod
    def apply_standard_plot_order(cls, ax, data_func, threshold_func=None, title=None):
        """应用标准绘制顺序 - 解决网格线覆盖问题"""
        # 1. 先设置网格（底层）
        ax.grid(True, alpha=0.3, zorder=cls.Z_ORDER['grid'])
        
        # 2. 绘制阈值线（中层）
        if threshold_func:
            threshold_func(ax, zorder=cls.Z_ORDER['threshold'])
        
        # 3. 绘制数据（上层）
        data_func(ax, zorder=cls.Z_ORDER['data'])
        
        # 4. 应用统一样式
        if title:
            cls.apply_axis_style(ax, title)

# 初始化全局样式
UnifiedChartStyle.setup_matplotlib()
print("✅ SUCCESS: Unified Chart Style initialized")