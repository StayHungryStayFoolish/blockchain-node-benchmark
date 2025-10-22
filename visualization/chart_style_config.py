#!/usr/bin/env python3
"""
统一图表样式配置系统
解决字体、颜色、布局不一致的根本问题
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.dates as mdates
import os
import subprocess
import sys

# =====================================================================
# 框架配置工具函数
# =====================================================================

# 配置缓存 - 避免重复执行 Shell 脚本
_config_cache = None
_config_loaded = False

def load_framework_config(force_reload=False):
    """
    加载框架配置 - 通过 Shell source 获取完整配置
    
    这是唯一正确的方式，因为：
    1. 配置文件包含 Shell 函数、数组、算术运算等复杂语法
    2. 需要执行动态计算（io2 吞吐量、AWS 环境检测等）
    3. 保证与生产环境（Shell 调用 Python）的行为完全一致
    
    智能检测：
    - 如果环境变量已由 Shell 加载（生产环境），直接使用
    - 如果环境变量未加载（测试环境），执行 Shell 脚本
    
    参数:
        force_reload: 强制重新加载配置（默认 False，使用缓存）
    
    返回:
        dict: 配置字典
    """
    global _config_cache, _config_loaded
    
    # 使用缓存（除非强制重新加载）
    if _config_loaded and not force_reload:
        return _config_cache or {}
    
    # 检测关键环境变量是否已加载（由 Shell 预先加载）
    # 如果这些变量存在，说明 Shell 已经 source 了 config_loader.sh
    key_vars = [
        'DATA_VOL_MAX_IOPS',
        'BOTTLENECK_CPU_THRESHOLD',
        'BASE_DATA_DIR',
        'CONFIG_ALREADY_LOADED'  # Shell 脚本设置的标记
    ]
    
    already_loaded = any(os.getenv(var) for var in key_vars)
    
    if already_loaded and not force_reload:
        # 环境变量已由 Shell 加载，直接使用
        config = {k: v for k, v in os.environ.items()}
        _config_cache = config
        _config_loaded = True
        return config
    
    # 环境变量未加载，需要执行 Shell 脚本
    try:
        # 获取配置文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(current_dir, '..', 'config')
        config_loader = os.path.join(config_dir, 'config_loader.sh')
        
        if not os.path.exists(config_loader):
            print(f"⚠️  配置文件不存在: {config_loader}", file=sys.stderr)
            _config_loaded = True
            _config_cache = {}
            return {}
        
        # 通过 Shell source 加载配置并导出环境变量
        # 使用 env 命令获取所有环境变量
        script = f'source "{config_loader}" 2>/dev/null && env'
        
        result = subprocess.run(
            ['bash', '-c', script],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(config_loader)
        )
        
        if result.returncode != 0:
            print(f"⚠️  配置加载失败: {result.stderr}", file=sys.stderr)
            _config_loaded = True
            _config_cache = {}
            return {}
        
        # 解析环境变量
        config = {}
        for line in result.stdout.splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                config[key] = value
                os.environ[key] = value
        
        # 缓存配置
        _config_cache = config
        _config_loaded = True
        
        return config
        
    except Exception as e:
        print(f"⚠️  配置加载异常: {e}", file=sys.stderr)
        _config_loaded = True
        _config_cache = {}
        return {}

def create_chart_title(base_title, accounts_configured):
    """创建统一的图表标题"""
    if accounts_configured:
        return f"{base_title} - DATA & ACCOUNTS Devices"
    else:
        return f"{base_title} - DATA Device Only"

class UnifiedChartStyle:
    """统一图表样式配置"""
    
    # 统一字体配置
    FONT_CONFIG = {
        'title_size': 16,
        'subtitle_size': 12, 
        'label_size': 10,
        'legend_size': 9,
        'text_size': 10  # Summary文本字体大小
    }
    
    # 统一颜色配置 - 扩展支持32张图表
    COLORS = {
        # 设备主色
        'data_primary': '#1f77b4',      # 蓝色 - DATA设备主色
        'accounts_primary': '#ff9500',   # 深橙色 - ACCOUNTS设备主色 (区别于警告色)
        
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
            'startangle': 90,
            'text_overlap_fix': True,  # 启用文本重叠修复
            'pctdistance': 0.85,       # 百分比文本距离
            'labeldistance': 1.1,      # 标签距离
            'dual_pie_spacing': 0.4    # 双饼图间距
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
    
    # 高对比度颜色序列 - 确保6+颜色清晰区分
    COLOR_PALETTE = [
        '#1f77b4',  # 蓝色 - 主要数据
        '#ff7f0e',  # 橙色 - 次要数据  
        '#2ca02c',  # 绿色 - 正常状态
        '#d62728',  # 红色 - 警告/错误
        '#9467bd',  # 紫色 - 特殊数据
        '#8c564b',  # 棕色 - 辅助数据
        '#e377c2',  # 粉色 - 补充数据
        '#7f7f7f',  # 灰色 - 背景数据
        '#bcbd22',  # 黄绿 - 中性数据
        '#17becf',  # 青色 - 网络数据
        '#ff1493',  # 深粉 - 高对比度
        '#00ced1',  # 深青 - 高对比度
        '#ffd700',  # 金色 - 高对比度
        '#32cd32',  # 酸橙绿 - 高对比度
        '#ff6347',  # 番茄红 - 高对比度
        '#4169e1',  # 皇家蓝 - 高对比度
        '#da70d6',  # 兰花紫 - 高对比度
        '#20b2aa',  # 浅海绿 - 高对比度
        '#f0e68c'   # 卡其色 - 高对比度
    ]
    
    # 子图布局配置 - 支持32张图表的所有布局
    SUBPLOT_LAYOUTS = {
        '2x2': {
            'figsize': (16, 12),
            'nrows': 2, 'ncols': 2,
            'hspace': 0.35,
            'wspace': 0.25,
            'title_fontsize': 16,
            'subtitle_fontsize': 12
        },
        '2x3': {
            'figsize': (18, 12), 
            'nrows': 2, 'ncols': 3,
            'top': 0.93,
            'bottom': 0.08,
            'left': 0.08,
            'right': 0.95,
            'hspace': 0.35,
            'wspace': 0.3,
            'title_fontsize': 16,
            'subtitle_fontsize': 11
        },
        '3x2': {
            'figsize': (16, 15),
            'nrows': 3, 'ncols': 2,
            'top': 0.94,
            'bottom': 0.06,
            'left': 0.08,
            'right': 0.95,
            'hspace': 0.4,
            'wspace': 0.25,
            'title_fontsize': 16,
            'subtitle_fontsize': 11
        },
        '1x2': {
            'figsize': (16, 8),
            'nrows': 1, 'ncols': 2,
            'top': 0.85,
            'bottom': 0.12,
            'left': 0.08,
            'right': 0.95,
            'hspace': 0.20,
            'wspace': 0.25,
            'title_fontsize': 16,
            'subtitle_fontsize': 12
        },
        '2x1': {
            'figsize': (12, 10),
            'nrows': 2, 'ncols': 1,
            'top': 0.93,
            'bottom': 0.08,
            'left': 0.10,
            'right': 0.92,
            'hspace': 0.3,
            'wspace': 0.2,
            'title_fontsize': 16,
            'subtitle_fontsize': 12
        },
        'dual_pie': {  # 双饼图特殊布局
            'figsize': (16, 8),
            'nrows': 1, 'ncols': 2,
            'top': 0.85,
            'bottom': 0.12,
            'left': 0.08,
            'right': 0.95,
            'hspace': 0.2,
            'wspace': 0.4,
            'title_fontsize': 14,
            'subtitle_fontsize': 10,
            'pie_text_distance': 1.2
        }
    }
    
    # 文本位置配置 - 统一文本框样式
    TEXT_POSITIONS = {
        'right_bottom': {
            'x': 0.98, 'y': 0.02,
            'ha': 'right', 'va': 'bottom',
            'transform': 'axes',  # 相对于子图坐标
            'bbox': {
                'boxstyle': 'round,pad=0.3',
                'facecolor': 'lightgray',
                'alpha': 0.8,
                'edgecolor': 'gray'
            },
            'fontsize': 9,
            'fontweight': 'normal'
        },
        'left_bottom': {
            'x': 0.02, 'y': 0.02,
            'ha': 'left', 'va': 'bottom', 
            'transform': 'axes',
            'bbox': {
                'boxstyle': 'round,pad=0.3',
                'facecolor': 'lightgray',
                'alpha': 0.8,
                'edgecolor': 'gray'
            },
            'fontsize': 9,
            'fontweight': 'normal'
        },
        'right_top': {
            'x': 0.98, 'y': 0.98,
            'ha': 'right', 'va': 'top',
            'transform': 'axes',
            'bbox': {
                'boxstyle': 'round,pad=0.3',
                'facecolor': 'lightgray', 
                'alpha': 0.8,
                'edgecolor': 'gray'
            },
            'fontsize': 9,
            'fontweight': 'normal'
        },
        'center_bottom': {  # 饼图中心文本
            'x': 0.5, 'y': 0.02,
            'ha': 'center', 'va': 'bottom',
            'transform': 'axes',
            'bbox': {
                'boxstyle': 'round,pad=0.3',
                'facecolor': 'white',
                'alpha': 0.9,
                'edgecolor': 'gray'
            },
            'fontsize': 10,
            'fontweight': 'bold'
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
    
    # 32个图表的布局配置
    LAYOUT_CONFIGS = {
        'performance_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
        'ebs_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
        'correlation_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
        'trend_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
        'comprehensive_3x2': {'figsize': (18, 15), 'layout': (3, 2)},
        'single_chart': {'figsize': (14, 8), 'layout': (1, 1)},
        'comparison_2x1': {'figsize': (16, 8), 'layout': (2, 1)},
        'threshold_3x1': {'figsize': (18, 6), 'layout': (3, 1)},
        'overhead_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
        'qps_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
        'efficiency_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
        'bottleneck_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
        'distribution_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
        'impact_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
        'cliff_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
        'qps_analysis_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
        'regression_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
        'capacity_2x2': {'figsize': (16, 12), 'layout': (2, 2)},
        'matrix_single': {'figsize': (12, 10), 'layout': (1, 1)},
        'heatmap_single': {'figsize': (12, 10), 'layout': (1, 1)}
    }
    
    @classmethod
    def setup_matplotlib(cls):
        """配置matplotlib全局样式"""
        # 应用 seaborn 样式以获得统一的浅色背景
        try:
            plt.style.use('seaborn-v0_8')
        except:
            pass  # 如果样式不可用，继续使用默认样式
        
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['font.size'] = cls.FONT_CONFIG['label_size']
        plt.rcParams['axes.titlesize'] = cls.FONT_CONFIG['subtitle_size']
        plt.rcParams['axes.labelsize'] = cls.FONT_CONFIG['label_size']
        plt.rcParams['legend.fontsize'] = cls.FONT_CONFIG['legend_size']
        plt.rcParams['xtick.labelsize'] = cls.FONT_CONFIG['text_size']
        plt.rcParams['ytick.labelsize'] = cls.FONT_CONFIG['text_size']
        print("✅ SUCCESS: Unified Chart Style initialized")
        return True
        
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
    def add_text_summary(cls, ax, summary_text, title):
        """统一的文本摘要添加函数 - 简洁样式"""
        ax.axis('off')
        ax.text(0.05, 0.95, summary_text, transform=ax.transAxes, 
               fontsize=cls.FONT_CONFIG['text_size'], verticalalignment='top', 
               fontfamily='monospace')
        ax.set_title(title, fontsize=cls.FONT_CONFIG['subtitle_size'])
        
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
    def get_subplot_layout(cls, layout_type):
        """获取子图布局配置"""
        return cls.SUBPLOT_LAYOUTS.get(layout_type, cls.SUBPLOT_LAYOUTS['2x2'])
    
    @classmethod
    def get_text_position(cls, position_type):
        """获取文本位置配置"""
        return cls.TEXT_POSITIONS.get(position_type, cls.TEXT_POSITIONS['right_bottom'])
    
    @classmethod
    def apply_text_style(cls, ax, text, position='right_bottom', **kwargs):
        """应用统一文本样式"""
        pos_config = cls.get_text_position(position)
        
        # 合并配置和自定义参数
        text_kwargs = pos_config.copy()
        text_kwargs.update(kwargs)
        
        # 处理transform参数
        if text_kwargs.get('transform') == 'axes':
            text_kwargs['transform'] = ax.transAxes
        
        # 过滤掉非matplotlib参数
        matplotlib_params = ['x', 'y', 'fontsize', 'ha', 'va', 'bbox', 'transform', 'color', 'weight']
        filtered_kwargs = {k: v for k, v in text_kwargs.items() if k in matplotlib_params and k not in ['x', 'y']}
        
        return ax.text(text_kwargs['x'], text_kwargs['y'], text, **filtered_kwargs)
    
    @classmethod
    def setup_subplot_layout(cls, layout_type, **kwargs):
        """设置子图布局"""
        layout_config = cls.get_subplot_layout(layout_type)
        
        # 合并配置和自定义参数
        subplot_kwargs = layout_config.copy()
        subplot_kwargs.update(kwargs)
        
        # 提取matplotlib参数
        figsize = subplot_kwargs.pop('figsize', (16, 12))
        nrows = subplot_kwargs.pop('nrows', 2)
        ncols = subplot_kwargs.pop('ncols', 2)
        
        fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
        
        # 先应用tight_layout自动优化
        plt.tight_layout()
        
        # 只调整必要的参数
        adjust_params = {}
        for param in ['top', 'bottom', 'left', 'right', 'hspace', 'wspace']:
            if param in subplot_kwargs:
                adjust_params[param] = subplot_kwargs[param]
            
        if adjust_params:
            plt.subplots_adjust(**adjust_params)
        
        return fig, axes, subplot_kwargs
    
    @classmethod
    def apply_layout(cls, layout_type: str = 'auto', fig=None):
        """
        统一应用布局 - 避免在每个图表中重复调用 tight_layout 或 subplots_adjust
        
        Args:
            layout_type: 布局类型
                - 'auto': 使用 tight_layout 自动优化（推荐，适用于大多数图表）
                - '2x2', '2x3', '3x2' 等: 使用预定义的 subplots_adjust 参数（用于特殊情况）
            fig: matplotlib figure对象（可选）
        
        使用示例:
            # 方式1: 自动布局（推荐）
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('Chart Title', fontsize=16, fontweight='bold')
            # ... 绘制图表 ...
            UnifiedChartStyle.apply_layout('auto')  # 替代 plt.tight_layout()
            plt.savefig('chart.png')
            
            # 方式2: 使用预定义布局（特殊情况）
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            # ... 绘制图表 ...
            UnifiedChartStyle.apply_layout('2x2', fig)  # 使用预定义的间距参数
            plt.savefig('chart.png')
        """
        if layout_type == 'auto':
            # 使用 tight_layout 自动优化，并为 suptitle 预留空间
            # rect=[left, bottom, right, top] - top < 1.0 为主标题预留空间
            plt.tight_layout(rect=[0, 0, 1, 0.98])
        elif layout_type in cls.SUBPLOT_LAYOUTS:
            # 使用预定义的布局参数
            layout = cls.SUBPLOT_LAYOUTS[layout_type]
            adjust_params = {}
            for param in ['top', 'bottom', 'left', 'right', 'hspace', 'wspace']:
                if param in layout:
                    adjust_params[param] = layout[param]
            
            if adjust_params:
                if fig:
                    fig.subplots_adjust(**adjust_params)
                else:
                    plt.subplots_adjust(**adjust_params)
        else:
            # 默认使用 tight_layout
            plt.tight_layout()
    
    @classmethod
    def fix_pie_text_overlap(cls, ax, labels, autopct_texts=None):
        """修复饼图文本重叠问题"""
        pie_config = cls.CHART_CONFIGS['pie']
        
        if pie_config.get('text_overlap_fix', False):
            # 调整标签距离
            if hasattr(ax, 'texts'):
                for text in ax.texts:
                    text.set_fontsize(pie_config.get('label_fontsize', 10))
            
            # 调整百分比文本
            if autopct_texts:
                for text in autopct_texts:
                    text.set_fontsize(pie_config.get('pct_fontsize', 9))
                    text.set_weight('bold')
        
        return ax
    
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
    
    @classmethod
    def format_time_axis_unified(cls, axes_list, df_timestamp=None):
        """
        统一时间轴格式化 - 智能选择格式
        
        Args:
            axes_list: matplotlib axes列表
            df_timestamp: pandas datetime series (可选，用于智能格式选择)
        """
        if df_timestamp is not None and len(df_timestamp) > 0:
            # 智能格式：根据时间跨度自动选择
            time_span = (df_timestamp.iloc[-1] - df_timestamp.iloc[0]).total_seconds()
            
            if time_span < 300:  # 小于5分钟
                date_format = '%H:%M:%S'
            elif time_span < 3600:  # 小于1小时
                date_format = '%H:%M'
            elif time_span < 86400:  # 小于1天
                date_format = '%m-%d %H:%M'
            else:  # 大于1天
                date_format = '%m-%d'
        else:
            # 默认格式
            date_format = '%H:%M:%S'
        
        for ax in axes_list:
            ax.xaxis.set_major_formatter(mdates.DateFormatter(date_format))
            ax.tick_params(axis='x', rotation=45, labelsize=cls.FONT_CONFIG['text_size'])
            plt.setp(ax.xaxis.get_majorticklabels(), ha='right')
    
    @classmethod
    def apply_unified_text_layout(cls, ax, text_content, position='right_bottom'):
        """统一文本布局应用 - 解决问题21的样式不统一"""
        return cls.apply_text_style(ax, text_content, position)
    
    @classmethod
    def fix_subplot_text_consistency(cls, axes_list, texts_list, position='right_bottom'):
        """修复子图文本一致性 - 解决问题4,5,6的布局不一致"""
        for ax, text in zip(axes_list, texts_list):
            cls.apply_text_style(ax, text, position)
    
    @classmethod
    def create_device_aware_layout(cls, layout_type, accounts_configured=False):
        """创建设备感知的布局 - 解决EBS设备信息缺失问题"""
        fig, axes, config = cls.setup_subplot_layout(layout_type)
        
        # 根据设备配置调整标题
        if accounts_configured:
            device_suffix = "DATA & ACCOUNTS Devices"
        else:
            device_suffix = "DATA Device Only"
        
        return fig, axes, config, device_suffix
    
    @classmethod
    def get_device_color_scheme(cls, device_name, element_type='primary'):
        """获取设备颜色方案 - 解决颜色冲突问题"""
        device_colors = {
            'data': {
                'primary': cls.COLORS['data_primary'],      # 蓝色
                'warning': '#87CEEB',                       # 浅蓝色 - 避免与orange冲突
                'critical': cls.COLORS['critical'],         # 红色
                'marker': cls.MARKERS['data_device']        # 圆形
            },
            'accounts': {
                'primary': cls.COLORS['accounts_primary'],  # 橙色
                'warning': '#FFA07A',                       # 浅橙色 - 避免冲突
                'critical': '#9467bd',                      # 紫色
                'marker': cls.MARKERS['accounts_device']    # 三角形
            }
        }
        
        return device_colors.get(device_name.lower(), device_colors['data']).get(element_type, cls.COLORS['data_primary'])
    
    @classmethod
    def apply_qps_chart_style(cls, ax, qps_value, target_value=None):
        """QPS图表专用样式 - 解决问题3,18的QPS显示"""
        if target_value:
            title = f"QPS Performance (Actual: {qps_value}, Target: {target_value})"
        else:
            title = f"QPS Performance (Current: {qps_value})"
        
        cls.apply_axis_style(ax, title)
        return title

# 初始化全局样式
UnifiedChartStyle.setup_matplotlib()
print("✅ SUCCESS: Unified Chart Style initialized")