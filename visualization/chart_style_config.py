#!/usr/bin/env python3
"""
Unified Chart Style Configuration System
Solves fundamental issues of inconsistent fonts, colors, and layouts
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.dates as mdates
import os
import subprocess
import sys

# =====================================================================
# Framework configuration utility functions
# =====================================================================

# Configuration cache - avoid repeated Shell script execution
_config_cache = None
_config_loaded = False

def load_framework_config(force_reload=False):
    """
    Load framework configuration - obtain complete configuration via Shell source
    
    This is the only correct approach because:
    1. Configuration files contain complex Shell syntax (functions, arrays, arithmetic operations)
    2. Requires dynamic calculations (io2 throughput, AWS environment detection, etc.)
    3. Ensures complete consistency with production environment (Shell calling Python)
    
    Intelligent detection:
    - If environment variables already loaded by Shell (production), use directly
    - If environment variables not loaded (test environment), execute Shell script
    
    Parameters:
        force_reload: Force reload configuration (default False, use cache)
    
    Returns:
        dict: Configuration dictionary
    """
    global _config_cache, _config_loaded
    
    # Use cache (unless forced reload)
    if _config_loaded and not force_reload:
        return _config_cache or {}
    
    # Detect if key environment variables already loaded (pre-loaded by Shell)
    # If these variables exist, Shell has already sourced config_loader.sh
    key_vars = [
        'DATA_VOL_MAX_IOPS',
        'BOTTLENECK_CPU_THRESHOLD',
        'BASE_DATA_DIR',
        'CONFIG_ALREADY_LOADED'  # Marker set by Shell script
    ]
    
    already_loaded = any(os.getenv(var) for var in key_vars)
    
    if already_loaded and not force_reload:
        # Environment variables already loaded by Shell, use directly
        config = {k: v for k, v in os.environ.items()}
        _config_cache = config
        _config_loaded = True
        return config
    
    # Environment variables not loaded, need to execute Shell script
    try:
        # Get configuration file path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(current_dir, '..', 'config')
        config_loader = os.path.join(config_dir, 'config_loader.sh')
        
        if not os.path.exists(config_loader):
            print(f"⚠️  Configuration file does not exist: {config_loader}", file=sys.stderr)
            _config_loaded = True
            _config_cache = {}
            return {}
        
        # Load configuration via Shell source and export environment variables
        # Use env command to get all environment variables
        script = f'source "{config_loader}" 2>/dev/null && env'
        
        result = subprocess.run(
            ['bash', '-c', script],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(config_loader)
        )
        
        if result.returncode != 0:
            print(f"⚠️  Configuration loading failed: {result.stderr}", file=sys.stderr)
            _config_loaded = True
            _config_cache = {}
            return {}
        
        # Parse environment variables
        config = {}
        for line in result.stdout.splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                config[key] = value
                os.environ[key] = value
        
        # Cache configuration
        _config_cache = config
        _config_loaded = True
        
        return config
        
    except Exception as e:
        print(f"⚠️  Configuration loading exception: {e}", file=sys.stderr)
        _config_loaded = True
        _config_cache = {}
        return {}

def create_chart_title(base_title, accounts_configured):
    """Create unified chart title"""
    if accounts_configured:
        return f"{base_title} - DATA & ACCOUNTS Devices"
    else:
        return f"{base_title} - DATA Device Only"

class UnifiedChartStyle:
    """Unified chart style configuration"""
    
    # Unified font configuration
    FONT_CONFIG = {
        'title_size': 16,
        'subtitle_size': 12, 
        'label_size': 10,
        'legend_size': 9,
        'text_size': 10  # Summary text font size
    }
    
    # Unified color configuration - extended support for 32 charts
    COLORS = {
        # Device primary colors
        'data_primary': '#1f77b4',      # Blue - DATA device primary color
        'accounts_primary': '#ff9500',   # Deep orange - ACCOUNTS device primary color (distinct from warning color)
        
        # Status colors
        'warning': '#ff7f0e',           # Orange - warning
        'critical': '#d62728',          # Red - critical
        'success': '#2ca02c',           # Green - normal
        'info': '#17becf',              # Cyan - info
        
        # Chart element colors
        'grid': '#cccccc',              # Light gray - grid
        'text_bg': 'lightgray',         # Light gray - text background
        'threshold': '#d62728',         # Red - threshold line
        'baseline': '#2ca02c',          # Green - baseline
        
        # Extended color palette - support multi-device/multi-metric charts
        'purple': '#9467bd',            # Purple
        'brown': '#8c564b',             # Brown
        'pink': '#e377c2',              # Pink
        'gray': '#7f7f7f',              # Gray
        'olive': '#bcbd22',             # Olive
        'cyan': '#17becf',              # Cyan
        
        # Gradient color mapping - heatmaps and scatter plots
        'heatmap_low': '#ffffcc',       # Light yellow
        'heatmap_mid': '#fd8d3c',       # Orange
        'heatmap_high': '#800026',      # Dark red
    }
    
    # Chart type specific configuration
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
            'explode': (0.05, 0.05, 0.05, 0.05),  # Pie chart separation
            'autopct': '%1.1f%%',
            'startangle': 90,
            'text_overlap_fix': True,  # Enable text overlap fix
            'pctdistance': 0.85,       # Percentage text distance
            'labeldistance': 1.1,      # Label distance
            'dual_pie_spacing': 0.4    # Dual pie chart spacing
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
    
    # High contrast color sequence - ensure 6+ colors are clearly distinguishable
    COLOR_PALETTE = [
        '#1f77b4',  # Blue - primary data
        '#ff7f0e',  # Orange - secondary data  
        '#2ca02c',  # Green - normal status
        '#d62728',  # Red - warning/error
        '#9467bd',  # Purple - special data
        '#8c564b',  # Brown - auxiliary data
        '#e377c2',  # Pink - supplementary data
        '#7f7f7f',  # Gray - background data
        '#bcbd22',  # Yellow-green - neutral data
        '#17becf',  # Cyan - network data
        '#ff1493',  # Deep pink - high contrast
        '#00ced1',  # Dark cyan - high contrast
        '#ffd700',  # Gold - high contrast
        '#32cd32',  # Lime green - high contrast
        '#ff6347',  # Tomato red - high contrast
        '#4169e1',  # Royal blue - high contrast
        '#da70d6',  # Orchid purple - high contrast
        '#20b2aa',  # Light sea green - high contrast
        '#f0e68c'   # Khaki - high contrast
    ]
    
    # Subplot layout configuration - support all layouts for 32 charts
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
        'dual_pie': {  # Dual pie chart special layout
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
    
    # Text position configuration - unified text box style
    TEXT_POSITIONS = {
        'right_bottom': {
            'x': 0.98, 'y': 0.02,
            'ha': 'right', 'va': 'bottom',
            'transform': 'axes',  # Relative to subplot coordinates
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
        'center_bottom': {  # Pie chart center text
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
    
    # Colormap configuration - covers all actually used colormaps
    COLORMAPS = {
        'correlation': 'RdBu_r',        # Correlation analysis
        'performance': 'viridis',       # Performance analysis  
        'bottleneck': 'Reds',           # Bottleneck analysis
        'efficiency': 'plasma',         # Efficiency analysis
        'trend': 'coolwarm',            # Trend analysis
        'latency': 'YlOrRd',            # Latency analysis - used by EBS charts
        'utilization': 'viridis',       # Utilization analysis - used by EBS charts
        'heatmap': 'RdYlBu_r',          # Heatmap - used by advanced analysis
    }
    
    # Scatter plot marker style configuration
    MARKERS = {
        'data_device': 'o',             # DATA device - circle
        'accounts_device': '^',         # ACCOUNTS device - triangle
        'critical_point': 'x',          # Critical point - X shape
        'warning_point': 'o',           # Warning point - circle
        'normal_point': '.',            # Normal point - dot
    }
    
    # Unified text background style
    TEXT_BG_STYLE = {
        'boxstyle': "round,pad=0.3",
        'facecolor': 'lightgray',
        'alpha': 0.8
    }
    
    # Unified drawing layer order
    Z_ORDER = {
        'grid': 1,          # Grid lines - bottom layer
        'threshold': 2,     # Threshold lines - middle layer  
        'data': 3,          # Data lines - upper layer
        'annotation': 4     # Annotations - top layer
    }
    
    # Layout configuration for 32 charts
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
        """Configure matplotlib global style"""
        # Apply seaborn style to get unified light background
        try:
            plt.style.use('seaborn-v0_8')
        except:
            pass  # If style not available, continue with default style
        
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
        """Apply unified axis style"""
        if title:
            ax.set_title(title, fontsize=cls.FONT_CONFIG['subtitle_size'])
        ax.grid(True, alpha=0.3, zorder=cls.Z_ORDER['grid'])
        ax.tick_params(axis='both', labelsize=cls.FONT_CONFIG['text_size'])
        
    @classmethod
    def add_text_with_bg(cls, ax, x, y, text, **kwargs):
        """Add text with unified background"""
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
        """Unified text summary addition function - concise style"""
        ax.axis('off')
        ax.text(0.05, 0.95, summary_text, transform=ax.transAxes, 
               fontsize=cls.FONT_CONFIG['text_size'], verticalalignment='top', 
               fontfamily='monospace')
        ax.set_title(title, fontsize=cls.FONT_CONFIG['subtitle_size'])
        
    @classmethod
    def get_device_colors(cls, device_name):
        """Get device-specific color"""
        if device_name.lower() == 'data':
            return cls.COLORS['data_primary']
        elif device_name.lower() == 'accounts':
            return cls.COLORS['accounts_primary']
        else:
            return cls.COLORS['data_primary']
    
    @classmethod
    def get_chart_config(cls, chart_type):
        """Get chart type specific configuration"""
        return cls.CHART_CONFIGS.get(chart_type, {})
    
    @classmethod
    def get_colormap(cls, analysis_type):
        """Get colormap corresponding to analysis type"""
        return cls.COLORMAPS.get(analysis_type, 'viridis')
    
    @classmethod
    def get_marker(cls, marker_type):
        """Get marker style corresponding to marker type"""
        return cls.MARKERS.get(marker_type, 'o')
    
    @classmethod
    def get_subplot_layout(cls, layout_type):
        """Get subplot layout configuration"""
        return cls.SUBPLOT_LAYOUTS.get(layout_type, cls.SUBPLOT_LAYOUTS['2x2'])
    
    @classmethod
    def get_text_position(cls, position_type):
        """Get text position configuration"""
        return cls.TEXT_POSITIONS.get(position_type, cls.TEXT_POSITIONS['right_bottom'])
    
    @classmethod
    def apply_text_style(cls, ax, text, position='right_bottom', **kwargs):
        """Apply unified text style"""
        pos_config = cls.get_text_position(position)
        
        # Merge configuration and custom parameters
        text_kwargs = pos_config.copy()
        text_kwargs.update(kwargs)
        
        # Handle transform parameter
        if text_kwargs.get('transform') == 'axes':
            text_kwargs['transform'] = ax.transAxes
        
        # Filter out non-matplotlib parameters
        matplotlib_params = ['x', 'y', 'fontsize', 'ha', 'va', 'bbox', 'transform', 'color', 'weight']
        filtered_kwargs = {k: v for k, v in text_kwargs.items() if k in matplotlib_params and k not in ['x', 'y']}
        
        return ax.text(text_kwargs['x'], text_kwargs['y'], text, **filtered_kwargs)
    
    @classmethod
    def setup_subplot_layout(cls, layout_type, **kwargs):
        """Set up subplot layout"""
        layout_config = cls.get_subplot_layout(layout_type)
        
        # Merge configuration and custom parameters
        subplot_kwargs = layout_config.copy()
        subplot_kwargs.update(kwargs)
        
        # Extract matplotlib parameters
        figsize = subplot_kwargs.pop('figsize', (16, 12))
        nrows = subplot_kwargs.pop('nrows', 2)
        ncols = subplot_kwargs.pop('ncols', 2)
        
        fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
        
        # Apply tight_layout first for automatic optimization
        plt.tight_layout()
        
        # Only adjust necessary parameters
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
        Unified layout application - avoid repeatedly calling tight_layout or subplots_adjust in each chart
        
        Args:
            layout_type: Layout type
                - 'auto': Use tight_layout for automatic optimization (recommended, suitable for most charts)
                - '2x2', '2x3', '3x2', etc.: Use predefined subplots_adjust parameters (for special cases)
            fig: matplotlib figure object (optional)
        
        Usage examples:
            # Method 1: Automatic layout (recommended)
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('Chart Title', fontsize=16, fontweight='bold')
            # ... draw charts ...
            UnifiedChartStyle.apply_layout('auto')  # Replace plt.tight_layout()
            plt.savefig('chart.png')
            
            # Method 2: Use predefined layout (special cases)
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            # ... draw charts ...
            UnifiedChartStyle.apply_layout('2x2', fig)  # Use predefined spacing parameters
            plt.savefig('chart.png')
        """
        if layout_type == 'auto':
            # Use tight_layout for automatic optimization, reserve space for suptitle
            # rect=[left, bottom, right, top] - top < 1.0 reserves space for main title
            plt.tight_layout(rect=[0, 0, 1, 0.98])
        elif layout_type in cls.SUBPLOT_LAYOUTS:
            # Use predefined layout parameters
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
            # Default use tight_layout
            plt.tight_layout()
    
    @classmethod
    def apply_standard_plot_order(cls, ax, data_func, threshold_func=None, title=None):
        """Apply standard drawing order - solve grid line overlay issue"""
        # 1. Set grid first (bottom layer)
        ax.grid(True, alpha=0.3, zorder=cls.Z_ORDER['grid'])
        
        # 2. Draw threshold lines (middle layer)
        if threshold_func:
            threshold_func(ax, zorder=cls.Z_ORDER['threshold'])
        
        # 3. Draw data (upper layer)
        data_func(ax, zorder=cls.Z_ORDER['data'])
        
        # 4. Apply unified style
        if title:
            cls.apply_axis_style(ax, title)
    
    @classmethod
    def format_time_axis_unified(cls, axes_list, df_timestamp=None):
        """
        Unified time axis formatting - intelligent format selection
        
        Args:
            axes_list: matplotlib axes list
            df_timestamp: pandas datetime series (optional, for intelligent format selection)
        """
        if df_timestamp is not None and len(df_timestamp) > 0:
            # Intelligent format: automatically select based on time span
            time_span = (df_timestamp.iloc[-1] - df_timestamp.iloc[0]).total_seconds()
            
            if time_span < 300:  # Less than 5 minutes
                date_format = '%H:%M:%S'
            elif time_span < 3600:  # Less than 1 hour
                date_format = '%H:%M'
            elif time_span < 86400:  # Less than 1 day
                date_format = '%m-%d %H:%M'
            else:  # Greater than 1 day
                date_format = '%m-%d'
        else:
            # Default format
            date_format = '%H:%M:%S'
        
        for ax in axes_list:
            ax.xaxis.set_major_formatter(mdates.DateFormatter(date_format))
            ax.tick_params(axis='x', rotation=45, labelsize=cls.FONT_CONFIG['text_size'])
            plt.setp(ax.xaxis.get_majorticklabels(), ha='right')
    
    @classmethod
    def format_time_axis(cls, ax, timestamps):
        """
        Single ax time axis formatting - intelligent format selection
        
        Args:
            ax: matplotlib axes object
            timestamps: pandas datetime series
        """
        if len(timestamps) == 0:
            return
        time_range = (timestamps.max() - timestamps.min()).total_seconds()
        if time_range < 300:  # < 5 minutes
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        elif time_range < 3600:  # < 1 hour
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        elif time_range < 86400:  # < 1 day
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        else:  # > 1 day
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    @classmethod
    def apply_unified_text_layout(cls, ax, text_content, position='right_bottom'):
        """Unified text layout application - solve issue 21 style inconsistency"""
        return cls.apply_text_style(ax, text_content, position)
    
    @classmethod
    def fix_subplot_text_consistency(cls, axes_list, texts_list, position='right_bottom'):
        """Fix subplot text consistency - solve issues 4,5,6 layout inconsistency"""
        for ax, text in zip(axes_list, texts_list):
            cls.apply_text_style(ax, text, position)
    
    @classmethod
    def create_device_aware_layout(cls, layout_type, accounts_configured=False):
        """Create device-aware layout - solve EBS device information missing issue"""
        fig, axes, config = cls.setup_subplot_layout(layout_type)
        
        # Adjust title based on device configuration
        if accounts_configured:
            device_suffix = "DATA & ACCOUNTS Devices"
        else:
            device_suffix = "DATA Device Only"
        
        return fig, axes, config, device_suffix
    
    @classmethod
    def get_device_color_scheme(cls, device_name, element_type='primary'):
        """Get device color scheme - solve color conflict issue"""
        device_colors = {
            'data': {
                'primary': cls.COLORS['data_primary'],      # Blue
                'warning': '#87CEEB',                       # Light blue - avoid conflict with orange
                'critical': cls.COLORS['critical'],         # Red
                'marker': cls.MARKERS['data_device']        # Circle
            },
            'accounts': {
                'primary': cls.COLORS['accounts_primary'],  # Orange
                'warning': '#FFA07A',                       # Light orange - avoid conflict
                'critical': '#9467bd',                      # Purple
                'marker': cls.MARKERS['accounts_device']    # Triangle
            }
        }
        
        return device_colors.get(device_name.lower(), device_colors['data']).get(element_type, cls.COLORS['data_primary'])
    
    @classmethod
    def apply_qps_chart_style(cls, ax, qps_value, target_value=None):
        """QPS chart specific style - solve issues 3,18 QPS display"""
        if target_value:
            title = f"QPS Performance (Actual: {qps_value}, Target: {target_value})"
        else:
            title = f"QPS Performance (Current: {qps_value})"
        
        cls.apply_axis_style(ax, title)
        return title

# Initialize global style
UnifiedChartStyle.setup_matplotlib()
print("✅ SUCCESS: Unified Chart Style initialized")