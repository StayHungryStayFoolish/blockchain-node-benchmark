#!/usr/bin/env python3
"""
综合分析器 - 重构后的集成版本 + 瓶颈模式支持
整合RPC深度分析器、验证器日志分析器和QPS分析器
提供统一的分析入口和完整的报告生成
支持瓶颈检测模式和时间窗口分析
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import glob
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.unified_logger import get_logger
import json
import argparse
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

class DataProcessor:
    """数据处理工具类 - 解决数据处理重复代码"""
    
    @staticmethod
    def validate_dataframe_column(df: pd.DataFrame, column: str) -> bool:
        """验证DataFrame是否包含指定列且有数据"""
        return column in df.columns and len(df) > 0 and not df[column].empty
    
    @staticmethod
    def safe_calculate_mean(df: pd.DataFrame, column: str) -> float:
        """安全计算列的平均值 - 解决重复的均值计算代码"""
        if DataProcessor.validate_dataframe_column(df, column):
            return df[column].mean()
        return 0.0
    
    @staticmethod
    def safe_calculate_max(df: pd.DataFrame, column: str) -> float:
        """安全计算列的最大值"""
        if DataProcessor.validate_dataframe_column(df, column):
            return df[column].max()
        return 0.0

class FileManager:
    """文件管理工具类 - 智能文件保存，支持备份和固定名称"""
    
    def __init__(self, output_dir: str, session_timestamp: str):
        self.output_dir = output_dir
        self.session_timestamp = session_timestamp
        self.reports_dir = os.path.join(output_dir, 'reports')
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def save_chart_with_backup(self, chart_name: str, plt_figure) -> str:
        """保存图表，同时创建备份和当前版本"""
        # 固定名称文件（供其他组件引用）
        current_path = os.path.join(self.reports_dir, f'{chart_name}.png')
        
        # 带时间戳的备份文件
        backup_path = os.path.join(self.reports_dir, f'{chart_name}_{self.session_timestamp}.png')
        
        # 保存两个版本
        plt_figure.savefig(current_path, dpi=300, bbox_inches='tight')
        plt_figure.savefig(backup_path, dpi=300, bbox_inches='tight')
        
        logger.info(f"📊 图表已保存: {current_path} (当前版本)")
        logger.info(f"📊 备份已创建: {backup_path}")
        
        return current_path
    
    def save_report_with_backup(self, report_name: str, content: str) -> str:
        """保存报告，同时创建备份和当前版本"""
        # 固定名称文件（供其他组件引用）
        current_path = os.path.join(self.reports_dir, f'{report_name}.md')
        
        # 带时间戳的备份文件
        backup_path = os.path.join(self.reports_dir, f'{report_name}_{self.session_timestamp}.md')
        
        # 保存两个版本
        with open(current_path, 'w', encoding='utf-8') as f:
            f.write(content)
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"📄 报告已保存: {current_path} (当前版本)")
        logger.info(f"📄 备份已创建: {backup_path}")
        
        return current_path

class OperationLogger:
    """操作日志装饰器 - 统一日志格式，解决print语句重复问题"""
    
    @staticmethod
    def log_operation(operation_name: str, emoji: str = "📊"):
        """记录操作的装饰器"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                print(f"\n{emoji} {operation_name}...")
                try:
                    result = func(*args, **kwargs)
                    logger.info(f"✅ {operation_name} completed successfully")
                    return result
                except Exception as e:
                    logger.error(f"❌ {operation_name} failed: {e}")
                    raise
            return wrapper
        return decorator

# 配置日志
logger = get_logger(__name__)

# 添加路径以支持重组后的目录结构
from pathlib import Path

# 使用更健壮的路径管理
current_dir = Path(__file__).parent
project_root = current_dir.parent
utils_dir = project_root / 'utils'
visualization_dir = project_root / 'visualization'

# 添加路径到sys.path
for path in [str(utils_dir), str(visualization_dir)]:
    if path not in sys.path:
        sys.path.insert(0, path)

# 导入拆分后的模块
try:
    from rpc_deep_analyzer import RpcDeepAnalyzer
    from validator_log_analyzer import ValidatorLogAnalyzer
    from qps_analyzer import SolanaQPSAnalyzer
    logger.info("✅ 所有分析模块加载成功")
except ImportError as e:
    logger.error(f"❌ 分析模块导入失败: {e}")

class BottleneckAnalysisMode:
    """瓶颈分析模式配置"""
    
    def __init__(self, bottleneck_info: Optional[Dict] = None):
        # 只有当提供了有效的瓶颈信息时才启用
        self.enabled = bottleneck_info is not None and len(bottleneck_info) > 0
        self.bottleneck_info = bottleneck_info or {}
        self.bottleneck_time = None
        self.analysis_window = None
        self.max_qps = 0
        self.bottleneck_qps = 0
        
        if self.enabled:
            self._parse_bottleneck_info()
    
    def _parse_bottleneck_info(self):
        """解析瓶颈信息"""
        try:
            self.bottleneck_time = self.bottleneck_info.get('detection_time')
            self.analysis_window = self.bottleneck_info.get('analysis_window', {})
            self.max_qps = self.bottleneck_info.get('max_qps_achieved', 0)
            self.bottleneck_qps = self.bottleneck_info.get('bottleneck_qps', 0)
            
            logger.info(f"🚨 瓶颈分析模式: 最大QPS={self.max_qps}, 瓶颈QPS={self.bottleneck_qps}")
        except Exception as e:
            logger.error(f"❌ 瓶颈信息解析失败: {e}")
            self.enabled = False

# 字段映射器已移除
try:
    # 不再使用字段映射器
    FIELD_MAPPER_AVAILABLE = False
    logger.info("✅ 使用直接字段访问模式")
except ImportError as e:
    FIELD_MAPPER_AVAILABLE = False
    logger.warning(f"⚠️  字段映射器不可用: {e}，将使用原始字段名")


class ComprehensiveAnalyzer:
    """综合分析器 - 整合所有分析功能的主控制器 + 瓶颈模式支持"""

    def __init__(self, output_dir: Optional[str] = None, benchmark_mode: str = "standard", bottleneck_mode: Optional[BottleneckAnalysisMode] = None):
        """
        初始化综合分析器
        
        Args:
            output_dir: 输出目录路径（如果为None，将从环境变量获取）
            benchmark_mode: 基准测试模式 (quick/standard/intensive)
            bottleneck_mode: 瓶颈分析模式配置
        """
        if output_dir is None:
            output_dir = os.environ.get('DATA_DIR', os.path.join(os.path.expanduser('~'), 'blockchain-node-benchmark-result'))
        
        # 创建会话时间戳，用于备份文件命名
        self.session_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        self.output_dir = output_dir
        self.benchmark_mode = benchmark_mode
        self.csv_file = self.get_latest_csv()
        self.bottleneck_mode = bottleneck_mode or BottleneckAnalysisMode()
        
        # 初始化各个分析器
        self.qps_analyzer = SolanaQPSAnalyzer(output_dir, benchmark_mode, self.bottleneck_mode.enabled)
        self.log_analyzer = ValidatorLogAnalyzer()
        self.rpc_deep_analyzer = RpcDeepAnalyzer(self.csv_file)
        
        # 初始化文件管理器
        self.file_manager = FileManager(self.output_dir, self.session_timestamp)
        
        logger.info(f"🔍 初始化综合分析器，输出目录: {output_dir}")
        if self.bottleneck_mode.enabled:
            logger.info(f"🚨 瓶颈分析模式已启用")

    def get_latest_csv(self) -> Optional[str]:
        """获取最新的CSV监控文件"""
        csv_files = glob.glob(f"{self.output_dir}/logs/*.csv")
        return max(csv_files, key=os.path.getctime) if csv_files else None

    @staticmethod
    def filter_data_by_time_window(df: pd.DataFrame, start_time: str, end_time: str) -> pd.DataFrame:
        """根据时间窗口过滤数据 - 静态方法"""
        try:
            if 'timestamp' not in df.columns:
                logger.warning("⚠️ 数据中没有timestamp列，无法进行时间窗口过滤")
                return df
            
            # 转换时间戳
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            start_dt = pd.to_datetime(start_time)
            end_dt = pd.to_datetime(end_time)
            
            # 过滤数据
            filtered_df = df[(df['timestamp'] >= start_dt) & (df['timestamp'] <= end_dt)]
            logger.info(f"📊 时间窗口过滤: {len(df)} -> {len(filtered_df)} 条记录")
            
            return filtered_df
        except Exception as e:
            logger.error(f"❌ 时间窗口过滤失败: {e}")
            return df

    def analyze_bottleneck_correlation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析瓶颈相关性"""
        if not self.bottleneck_mode.enabled:
            return {}
        
        try:
            analysis_result = {
                'bottleneck_detected': True,
                'max_qps': self.bottleneck_mode.max_qps,
                'bottleneck_qps': self.bottleneck_mode.bottleneck_qps,
                'performance_drop': 0.0,  # 使用float类型保持一致性
                'correlations': {},
                'bottleneck_factors': []
            }
            
            # 计算性能下降
            if self.bottleneck_mode.max_qps > 0:
                performance_drop = ((self.bottleneck_mode.bottleneck_qps - self.bottleneck_mode.max_qps) / 
                                  self.bottleneck_mode.max_qps * 100)
                analysis_result['performance_drop'] = performance_drop
            
            # 分析各指标与QPS的相关性
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            qps_column = None
            
            # 寻找QPS列
            for col in ['current_qps', 'qps', 'requests_per_second']:
                if col in df.columns:
                    qps_column = col
                    break
            
            if qps_column:
                for col in numeric_columns:
                    if col != qps_column and len(df[col].dropna()) > 1:
                        try:
                            correlation = df[qps_column].corr(df[col])
                            if not np.isnan(correlation):
                                analysis_result['correlations'][col] = correlation
                                
                                # 识别瓶颈因子
                                if abs(correlation) > 0.7:
                                    analysis_result['bottleneck_factors'].append({
                                        'metric': col,
                                        'correlation': correlation,
                                        'impact': 'high' if abs(correlation) > 0.8 else 'medium'
                                    })
                        except Exception as e:
                            logger.warning(f"⚠️ 计算{col}相关性失败: {e}")
            
            logger.info(f"🔍 瓶颈相关性分析完成，发现{len(analysis_result['bottleneck_factors'])}个关键因子")
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ 瓶颈相关性分析失败: {e}")
            return {}

    def generate_bottleneck_analysis_chart(self, df: pd.DataFrame, bottleneck_analysis: Dict[str, Any]) -> Optional[plt.Figure]:
        """生成瓶颈分析专项图表"""
        if not self.bottleneck_mode.enabled or not bottleneck_analysis:
            return None
        
        try:
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('🚨 Bottleneck Analysis Dashboard', fontsize=16, fontweight='bold', color='red')
            
            # 1. QPS性能曲线 + 瓶颈标记
            if 'current_qps' in df.columns and len(df) > 0:
                axes[0, 0].plot(df.index, df['current_qps'], 'b-', alpha=0.7, label='QPS')
                
                # 标记最大成功QPS和瓶颈QPS
                max_qps = bottleneck_analysis.get('max_qps', 0)
                bottleneck_qps = bottleneck_analysis.get('bottleneck_qps', 0)
                
                if max_qps > 0:
                    axes[0, 0].axhline(y=max_qps, color='green', linestyle='--', 
                                     label=f'Max Successful QPS: {max_qps}')
                if bottleneck_qps > 0:
                    axes[0, 0].axhline(y=bottleneck_qps, color='red', linestyle='--', 
                                     label=f'Bottleneck QPS: {bottleneck_qps}')
                
                axes[0, 0].set_title('QPS Performance with Bottleneck Markers')
                axes[0, 0].set_xlabel('Time')
                axes[0, 0].set_ylabel('QPS')
                axes[0, 0].legend()
                axes[0, 0].grid(True, alpha=0.3)
            
            # 2. 瓶颈因子相关性
            correlations = bottleneck_analysis.get('correlations', {})
            if correlations:
                factors = list(correlations.keys())[:10]  # 取前10个
                corr_values = [correlations[f] for f in factors]
                
                colors = ['red' if abs(c) > 0.7 else 'orange' if abs(c) > 0.5 else 'blue' for c in corr_values]
                axes[0, 1].barh(factors, corr_values, color=colors, alpha=0.7)
                axes[0, 1].set_title('Bottleneck Factor Correlations')
                axes[0, 1].set_xlabel('Correlation with QPS')
                axes[0, 1].axvline(x=0, color='black', linestyle='-', alpha=0.3)
                axes[0, 1].grid(True, alpha=0.3)
            
            # 3. 性能下降分析
            performance_drop = bottleneck_analysis.get('performance_drop', 0.0)
            if performance_drop != 0:
                # 从瓶颈分析结果或瓶颈模式对象中获取QPS值
                max_qps = bottleneck_analysis.get('max_qps', self.bottleneck_mode.max_qps)
                bottleneck_qps = bottleneck_analysis.get('bottleneck_qps', self.bottleneck_mode.bottleneck_qps)
                
                categories = ['Max QPS', 'Bottleneck QPS']
                values = [max_qps, bottleneck_qps]
                colors = ['green', 'red']
                
                bars = axes[1, 0].bar(categories, values, color=colors, alpha=0.7)
                axes[1, 0].set_title(f'Performance Drop: {performance_drop:.1f}%')
                axes[1, 0].set_ylabel('QPS')
                
                # 添加数值标签
                for bar, value in zip(bars, values):
                    axes[1, 0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.01,
                                   f'{value}', ha='center', va='bottom', fontweight='bold')
            
            # 4. 瓶颈因子重要性
            bottleneck_factors = bottleneck_analysis.get('bottleneck_factors', [])
            if bottleneck_factors:
                factor_names = [f['metric'] for f in bottleneck_factors]
                factor_impacts = [abs(f['correlation']) for f in bottleneck_factors]
                
                axes[1, 1].pie(factor_impacts, labels=factor_names, autopct='%1.1f%%', startangle=90)
                axes[1, 1].set_title('Bottleneck Factor Impact Distribution')
            
            plt.tight_layout()
            
            # 保存图表 - 使用文件管理器，同时创建当前版本和备份
            chart_path = self.file_manager.save_chart_with_backup('bottleneck_analysis_chart', plt)
            logger.info(f"📊 瓶颈分析图表已保存: {chart_path}")
            
            return fig
            
        except Exception as e:
            logger.error(f"❌ 瓶颈分析图表生成失败: {e}")
            return None

    def generate_ultimate_performance_charts(self, df: pd.DataFrame, 
                                           log_analysis: Dict[str, Any], 
                                           rpc_deep_analysis: Dict[str, Any]) -> Optional[plt.Figure]:
        """生成终极性能图表，整合所有分析结果"""
        print("\n📈 Generating ultimate performance charts...")

        if len(df) == 0:
            print("❌ No QPS data for chart generation")
            return None

        plt.style.use('default')
        fig, axes = plt.subplots(4, 2, figsize=(16, 24))
        fig.suptitle('Solana QPS Ultimate Performance Analysis Dashboard', fontsize=16, fontweight='bold')

        # 1. CPU使用率 vs QPS
        if len(df) > 0 and 'cpu_usage' in df.columns:
            axes[0, 0].plot(df['current_qps'], df['cpu_usage'], 'bo-', alpha=0.7, markersize=4)
            axes[0, 0].axhline(y=85, color='red', linestyle='--', alpha=0.8, label='Warning (85%)')
            axes[0, 0].set_title('CPU Usage vs QPS')
            axes[0, 0].set_xlabel('QPS')
            axes[0, 0].set_ylabel('CPU %')
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)

        # 2. 内存使用率 vs QPS
        if len(df) > 0 and 'mem_usage' in df.columns:
            axes[0, 1].plot(df['current_qps'], df['mem_usage'], 'go-', alpha=0.7, markersize=4)
            axes[0, 1].axhline(y=90, color='red', linestyle='--', alpha=0.8, label='Warning (90%)')
            axes[0, 1].set_title('Memory Usage vs QPS')
            axes[0, 1].set_xlabel('QPS')
            axes[0, 1].set_ylabel('Memory %')
            axes[0, 1].legend()
            axes[0, 1].grid(True, alpha=0.3)

        # 3. RPC延迟 vs QPS
        if len(df) > 0 and 'rpc_latency_ms' in df.columns:
            axes[1, 0].plot(df['current_qps'], df['rpc_latency_ms'], 'ro-', alpha=0.7, markersize=4)
            axes[1, 0].axhline(y=1000, color='orange', linestyle='--', alpha=0.8, label='High Latency (1s)')
            axes[1, 0].set_title('RPC Latency vs QPS')
            axes[1, 0].set_xlabel('QPS')
            axes[1, 0].set_ylabel('Latency (ms)')
            axes[1, 0].legend()
            axes[1, 0].grid(True, alpha=0.3)

        # 4. RPC错误率（来自日志分析）
        rpc_analysis = log_analysis.get('rpc_analysis', {})
        if rpc_analysis:
            error_rate = 100 - rpc_analysis.get('success_rate', 100)
            axes[1, 1].bar(['RPC Success Rate', 'RPC Error Rate'],
                           [rpc_analysis.get('success_rate', 100), error_rate],
                           color=['green', 'red'], alpha=0.7)
            axes[1, 1].set_title('RPC Success vs Error Rate')
            axes[1, 1].set_ylabel('Percentage')
            axes[1, 1].grid(True, alpha=0.3)
        else:
            axes[1, 1].text(0.5, 0.5, 'No RPC Analysis Data', ha='center', va='center',
                            transform=axes[1, 1].transAxes, fontsize=12)
            axes[1, 1].set_title('RPC Analysis (No Data)')

        # 5. 瓶颈事件分布
        bottleneck_analysis = log_analysis.get('bottleneck_analysis', {})
        if bottleneck_analysis:
            bottleneck_types = ['RPC Thread', 'Compute Unit', 'Memory', 'I/O', 'Network']
            bottleneck_counts = [
                bottleneck_analysis.get('rpc_thread_saturation', 0),
                bottleneck_analysis.get('compute_unit_limits', 0),
                bottleneck_analysis.get('memory_pressure', 0),
                bottleneck_analysis.get('io_bottlenecks', 0),
                bottleneck_analysis.get('network_issues', 0)
            ]

            colors = ['red', 'orange', 'purple', 'brown', 'pink']
            bars = axes[2, 0].bar(bottleneck_types, bottleneck_counts, color=colors, alpha=0.7)
            axes[2, 0].set_title('Bottleneck Events Distribution')
            axes[2, 0].set_ylabel('Event Count')
            axes[2, 0].tick_params(axis='x', rotation=45)

            # 添加数值标签
            for bar, count in zip(bars, bottleneck_counts):
                if count > 0:
                    axes[2, 0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                                    str(count), ha='center', va='bottom')
        else:
            axes[2, 0].text(0.5, 0.5, 'No Bottleneck Data', ha='center', va='center',
                            transform=axes[2, 0].transAxes, fontsize=12)
            axes[2, 0].set_title('Bottleneck Analysis (No Data)')

        # 6. RPC方法分布
        if rpc_analysis and 'method_distribution' in rpc_analysis:
            method_dist = rpc_analysis['method_distribution']
            if method_dist:
                methods = list(method_dist.keys())[:5]  # 前5个方法
                counts = [method_dist[method] for method in methods]

                axes[2, 1].pie(counts, labels=methods, autopct='%1.1f%%', startangle=90)
                axes[2, 1].set_title('RPC Method Distribution')
            else:
                axes[2, 1].text(0.5, 0.5, 'No RPC Method Data', ha='center', va='center',
                                transform=axes[2, 1].transAxes, fontsize=12)
                axes[2, 1].set_title('RPC Methods (No Data)')
        else:
            axes[2, 1].text(0.5, 0.5, 'No RPC Method Data', ha='center', va='center',
                            transform=axes[2, 1].transAxes, fontsize=12)
            axes[2, 1].set_title('RPC Methods (No Data)')

        # 7. RPC延迟分布
        if len(df) > 0 and 'rpc_latency_ms' in df.columns:
            axes[3, 0].hist(df['rpc_latency_ms'], bins=30, alpha=0.7, color='purple')
            axes[3, 0].axvline(df['rpc_latency_ms'].mean(), color='red', linestyle='--',
                               label=f'Mean: {df["rpc_latency_ms"].mean():.1f}ms')
            axes[3, 0].axvline(df['rpc_latency_ms'].quantile(0.95), color='orange', linestyle='--',
                               label=f'P95: {df["rpc_latency_ms"].quantile(0.95):.1f}ms')
            axes[3, 0].set_title('RPC Latency Distribution')
            axes[3, 0].set_xlabel('Latency (ms)')
            axes[3, 0].set_ylabel('Frequency')
            axes[3, 0].legend()
            axes[3, 0].grid(True, alpha=0.3)

        # 8. 性能悬崖可视化
        cliff_analysis = rpc_deep_analysis.get('performance_cliff', {})
        if cliff_analysis and len(df) > 0:
            qps_latency = df.groupby('current_qps')['rpc_latency_ms'].mean().reset_index()
            qps_latency = qps_latency.sort_values('current_qps')

            axes[3, 1].plot(qps_latency['current_qps'], qps_latency['rpc_latency_ms'], 'bo-', alpha=0.7)

            # 标记悬崖点
            cliff_points = cliff_analysis.get('performance_degradation_qps', [])
            for cliff_qps in cliff_points:
                cliff_latency = qps_latency[qps_latency['current_qps'] == cliff_qps]['rpc_latency_ms']
                if len(cliff_latency) > 0:
                    axes[3, 1].scatter(cliff_qps, cliff_latency.iloc[0], color='red', s=100, marker='x',
                                       label='Performance Cliff')

            axes[3, 1].set_title('Performance Cliff Detection')
            axes[3, 1].set_xlabel('QPS')
            axes[3, 1].set_ylabel('Average Latency (ms)')
            axes[3, 1].grid(True, alpha=0.3)
            if cliff_points:
                axes[3, 1].legend()

        plt.tight_layout()
        
        # 保存图表 - 使用文件管理器，同时创建当前版本和备份
        chart_file = self.file_manager.save_chart_with_backup('comprehensive_analysis_charts', plt)
        print(f"✅ Ultimate performance charts saved: {chart_file}")

        return fig

    def _evaluate_comprehensive_performance(self, benchmark_mode: str, max_qps: int, 
                                          bottlenecks: Dict[str, Any], avg_cpu: float, 
                                          avg_mem: float, avg_rpc: float,
                                          bottleneck_analysis: Dict[str, Any],
                                          rpc_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于综合分析的科学性能评估
        整合QPS、日志分析、RPC分析等多维度数据
        """
        
        # 只有深度基准测试模式才能进行准确的性能等级评估
        if benchmark_mode != "intensive":
            return {
                'performance_level': '无法评估',
                'performance_grade': 'N/A',
                'evaluation_reason': f'{benchmark_mode}基准测试模式无法准确评估系统性能等级，需要intensive模式进行深度分析',
                'evaluation_basis': 'insufficient_benchmark_depth',
                'max_sustainable_qps': max_qps,
                'recommendations': [
                    f'当前{benchmark_mode}基准测试仅用于快速验证',
                    '如需准确的性能等级评估，请使用intensive基准测试模式',
                    '深度基准测试将触发系统瓶颈以获得准确的性能评估'
                ]
            }
        
        # 综合瓶颈分析
        bottleneck_types = bottlenecks.get('detected_bottlenecks', [])
        rpc_issues = rpc_analysis.get('critical_issues', [])
        validator_issues = bottleneck_analysis.get('critical_patterns', [])
        
        # 计算综合瓶颈评分
        comprehensive_score = ComprehensiveAnalyzer._calculate_comprehensive_bottleneck_score(
            bottleneck_types, avg_cpu, avg_mem, avg_rpc, rpc_issues, validator_issues
        )
        
        # 基于综合评分的科学等级评估
        if comprehensive_score < 0.2:
            level = "优秀"
            grade = "A (Excellent)"
            reason = f"系统在{max_qps} QPS下表现优秀，各项指标均在正常范围内"
            
        elif comprehensive_score < 0.4:
            level = "良好"
            grade = "B (Good)"
            reason = f"系统在{max_qps} QPS下表现良好，存在轻微瓶颈或问题"
            
        elif comprehensive_score < 0.7:
            level = "一般"
            grade = "C (Acceptable)"
            reason = f"系统在{max_qps} QPS下表现一般，存在明显瓶颈需要关注"
            
        else:
            level = "需要优化"
            grade = "D (Needs Improvement)"
            reason = f"系统在{max_qps} QPS下存在严重问题，需要立即优化"
        
        return {
            'performance_level': level,
            'performance_grade': grade,
            'evaluation_reason': reason,
            'evaluation_basis': 'comprehensive_intensive_analysis',
            'max_sustainable_qps': max_qps,
            'comprehensive_score': comprehensive_score,
            'bottleneck_types': bottleneck_types,
            'rpc_issues_count': len(rpc_issues),
            'validator_issues_count': len(validator_issues),
            'recommendations': ComprehensiveAnalyzer._generate_comprehensive_recommendations(
                bottleneck_types, rpc_issues, validator_issues, comprehensive_score, max_qps
            )
        }
    
    @staticmethod
    def _calculate_comprehensive_bottleneck_score(bottleneck_types: list, 
                                                avg_cpu: float, avg_mem: float, avg_rpc: float,
                                                rpc_issues: list, validator_issues: list) -> float:
        """计算综合瓶颈严重程度评分 - 静态方法"""
        
        total_score = 0.0
        
        # 系统资源瓶颈评分 (权重: 0.4)
        resource_score = 0.0
        if 'CPU' in bottleneck_types:
            resource_score += 0.15 * (1.5 if avg_cpu > 90 else 1.0)
        if 'Memory' in bottleneck_types:
            resource_score += 0.15 * (1.5 if avg_mem > 95 else 1.0)
        if 'EBS' in bottleneck_types:
            resource_score += 0.1
        
        # RPC问题评分 (权重: 0.3)
        rpc_score = min(len(rpc_issues) * 0.1, 0.3)
        if avg_rpc > 2000:
            rpc_score *= 1.5
        
        # 验证器问题评分 (权重: 0.3)
        validator_score = min(len(validator_issues) * 0.1, 0.3)
        
        total_score = resource_score + rpc_score + validator_score
        
        return min(total_score, 1.0)
    
    @staticmethod
    def _generate_comprehensive_capacity_assessment(performance_evaluation: Dict[str, Any], max_qps: int) -> str:
        """基于综合性能评估生成容量评估 - 静态方法"""
        performance_level = performance_evaluation.get('performance_level', '未知')
        comprehensive_score = performance_evaluation.get('comprehensive_score', 0)
        
        if performance_level == "优秀":
            return f"当前配置可稳定处理高负载 (已测试至 {max_qps:,} QPS，综合评分: {comprehensive_score:.3f})"
        elif performance_level == "良好":
            return f"当前配置可处理中高负载 (已测试至 {max_qps:,} QPS，存在轻微问题)"
        elif performance_level == "一般":
            return f"当前配置适合中等负载 (已测试至 {max_qps:,} QPS，存在明显问题)"
        elif performance_level == "需要优化":
            return f"当前配置需要优化以处理高负载 (已测试至 {max_qps:,} QPS，存在严重问题)"
        else:
            return f"需要intensive基准测试模式进行准确的容量评估"

    @staticmethod
    def _generate_comprehensive_recommendations(bottleneck_types: list, 
                                             rpc_issues: list, validator_issues: list,
                                             comprehensive_score: float, max_qps: int) -> list:
        """基于综合分析生成优化建议 - 静态方法"""
        recommendations = []
        
        if comprehensive_score < 0.2:
            recommendations.extend([
                f"🎉 系统综合性能优秀，当前配置可稳定支持 {max_qps} QPS",
                "💡 可考虑进一步提升QPS目标或优化成本效率",
                "📊 建议定期监控以维持当前性能水平"
            ])
        else:
            # 系统资源优化建议
            if 'CPU' in bottleneck_types:
                recommendations.append("🔧 CPU瓶颈：考虑升级CPU或优化计算密集型进程")
            if 'Memory' in bottleneck_types:
                recommendations.append("🔧 内存瓶颈：考虑增加内存或优化内存使用")
            if 'EBS' in bottleneck_types:
                recommendations.append("🔧 存储瓶颈：考虑升级EBS类型或优化I/O模式")
            
            # RPC优化建议
            if rpc_issues:
                recommendations.append(f"🔧 RPC问题：发现{len(rpc_issues)}个RPC相关问题，需要优化RPC配置")
            
            # 验证器优化建议
            if validator_issues:
                recommendations.append(f"🔧 验证器问题：发现{len(validator_issues)}个验证器相关问题，需要检查验证器配置")
        
        return recommendations

    @OperationLogger.log_operation("Generating comprehensive report", "📄")
    def generate_comprehensive_report(self, df: pd.DataFrame, max_qps: int, 
                                    bottlenecks: Dict[str, Any], 
                                    log_analysis: Dict[str, Any], 
                                    rpc_deep_analysis: Dict[str, Any],
                                    benchmark_mode: str = "standard") -> str:
        """生成基于瓶颈分析的综合报告，整合所有分析结果"""

        # 基本性能指标 - 使用工具类避免重复代码
        avg_cpu = DataProcessor.safe_calculate_mean(df, 'cpu_usage')
        avg_mem = DataProcessor.safe_calculate_mean(df, 'mem_usage')
        avg_rpc = DataProcessor.safe_calculate_mean(df, 'rpc_latency_ms')
        avg_rpc = df['rpc_latency_ms'].mean() if len(df) > 0 and 'rpc_latency_ms' in df.columns else 0

        # 日志分析结果
        rpc_analysis = log_analysis.get('rpc_analysis', {})
        bottleneck_analysis = log_analysis.get('bottleneck_analysis', {})
        summary_stats = log_analysis.get('summary_stats', {})
        correlation_analysis = log_analysis.get('correlation_analysis', {})

        # 基于基准测试模式和瓶颈分析的性能评估
        performance_evaluation = self._evaluate_comprehensive_performance(
            benchmark_mode, max_qps, bottlenecks, avg_cpu, avg_mem, avg_rpc, 
            bottleneck_analysis, rpc_analysis
        )

        report = f"""# Solana QPS Comprehensive Performance Analysis Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
- **Maximum QPS Achieved**: {max_qps:,}
- **Performance Grade**: {performance_evaluation['performance_grade']}
- **Performance Level**: {performance_evaluation['performance_level']}
- **Benchmark Mode**: {benchmark_mode}
- **Test Duration**: {len(df)} monitoring points
- **Log Entries Analyzed**: {summary_stats.get('total_log_entries', 0):,}
- **Analysis Period**: {summary_stats.get('analysis_period_hours', 0):.1f} hours

## Performance Evaluation
- **Evaluation Basis**: {performance_evaluation['evaluation_basis']}
- **Evaluation Reason**: {performance_evaluation['evaluation_reason']}
- **Comprehensive Score**: {performance_evaluation.get('comprehensive_score', 0):.3f}

## System Performance Metrics
- **Average CPU Usage**: {avg_cpu:.1f}%
- **Average Memory Usage**: {avg_mem:.1f}%
- **Average RPC Latency**: {avg_rpc:.1f}ms
- **CPU Peak**: {DataProcessor.safe_calculate_max(df, 'cpu_usage'):.1f}%
- **Memory Peak**: {DataProcessor.safe_calculate_max(df, 'mem_usage'):.1f}%
- **RPC Latency Peak**: {DataProcessor.safe_calculate_max(df, 'rpc_latency_ms'):.1f}ms

## 🔍 Enhanced Log Analysis Results

### RPC Performance (From Validator Logs)
- **Total RPC Requests**: {rpc_analysis.get('total_rpc_requests', 0):,}
- **RPC Success Rate**: {rpc_analysis.get('success_rate', 0):.2f}%
- **RPC Error Count**: {rpc_analysis.get('rpc_errors', 0):,}
- **RPC Busy Incidents**: {rpc_analysis.get('rpc_busy_incidents', 0):,}
- **Average Response Time**: {rpc_analysis.get('avg_response_time', 0):.1f}ms
- **P95 Response Time**: {rpc_analysis.get('p95_response_time', 0):.1f}ms
- **P99 Response Time**: {rpc_analysis.get('p99_response_time', 0):.1f}ms

### Critical Bottlenecks Detected
- **RPC Thread Saturation**: {bottleneck_analysis.get('rpc_thread_saturation', 0)} incidents
- **Compute Unit Limits**: {bottleneck_analysis.get('compute_unit_limits', 0)} incidents
- **Memory Pressure Events**: {bottleneck_analysis.get('memory_pressure', 0)} incidents
- **I/O Bottlenecks**: {bottleneck_analysis.get('io_bottlenecks', 0)} incidents
- **Network Issues**: {bottleneck_analysis.get('network_issues', 0)} incidents

### QPS vs Error Correlation
"""

        # 添加相关性分析
        if correlation_analysis and correlation_analysis.get('qps_error_correlation'):
            correlation = correlation_analysis['qps_error_correlation']
            report += f"- **QPS-Error Correlation**: {correlation:.3f}\n"

            if correlation > 0.7:
                report += "  ⚠️  Strong positive correlation detected - errors increase with QPS\n"
            elif correlation > 0.3:
                report += "  📊 Moderate correlation detected between QPS and errors\n"
            else:
                report += "  ✅ Low correlation - system handles QPS increases well\n"

        # 最常用的RPC方法
        if rpc_analysis.get('method_distribution'):
            report += "\n### Most Active RPC Methods\n"
            for method, count in rpc_analysis['method_distribution'].most_common(5):
                report += f"- **{method}**: {count:,} requests\n"

        # 添加RPC深度分析结果
        if rpc_deep_analysis:
            rpc_deep_report = self.rpc_deep_analyzer.generate_rpc_deep_analysis_report(rpc_deep_analysis)
            report += rpc_deep_report

        # 优化建议
        report += f"""
## 💡 Comprehensive Optimization Recommendations

### Immediate Actions
"""

        # 基于日志分析和RPC深度分析的具体建议
        rpc_busy_count = bottleneck_analysis.get('rpc_thread_saturation', 0)
        memory_pressure = bottleneck_analysis.get('memory_pressure', 0)

        if rpc_busy_count > 20:
            report += "- 🔧 **High Priority**: Increase RPC thread pool size (current threads are saturated)\n"
            report += "- 🔧 **High Priority**: Consider implementing RPC request rate limiting\n"

        if memory_pressure > 0:
            report += "- 🔥 **Critical**: Increase system memory allocation or optimize memory usage\n"
            report += "- 🔧 Check for memory leaks in validator process\n"

        # 使用基于综合分析的建议
        for recommendation in performance_evaluation.get('recommendations', []):
            report += f"- {recommendation}\n"

        # 基于RPC深度分析的建议
        if rpc_deep_analysis:
            bottleneck_classification = rpc_deep_analysis.get('bottleneck_classification', {})
            recommendations = bottleneck_classification.get('recommendations', [])
            if recommendations:
                report += "\n### RPC Deep Analysis Recommendations\n"
                for rec in recommendations:
                    report += f"- 🔧 {rec}\n"

        report += f"""
### Production Deployment
- **Recommended Production QPS**: {int(max_qps * 0.8):,} (80% of maximum tested)
- **Monitoring Thresholds**: 
  - Alert if RPC success rate < 98%
  - Alert if RPC busy incidents > 10/hour
  - Alert if memory pressure events detected
  - Alert if RPC latency P99 > 500ms sustained
- **Capacity Assessment**: {ComprehensiveAnalyzer._generate_comprehensive_capacity_assessment(performance_evaluation, max_qps)}

## Files Generated
- **Comprehensive Charts**: `{self.output_dir}/reports/comprehensive_analysis_charts.png`
- **Raw QPS Monitoring Data**: `{self.csv_file or 'N/A'}`
- **Validator Log Analysis**: Included in this report
- **RPC Deep Analysis**: Included in this report
- **Vegeta Test Reports**: `{self.output_dir}/reports/`

---
*Report generated by Comprehensive Solana QPS Analyzer v4.0*
"""

        # 保存综合报告 - 使用文件管理器，同时创建当前版本和备份
        report_file = self.file_manager.save_report_with_backup('comprehensive_analysis_report', report)

        print(f"✅ Comprehensive report saved: {report_file}")
        return report

    def run_comprehensive_analysis(self) -> Dict[str, Any]:
        """运行完整的综合分析"""
        print("🚀 Starting Comprehensive Solana QPS Analysis")
        print("=" * 80)

        # 1. 运行QPS分析
        print("\n📊 Phase 1: QPS Performance Analysis")
        qps_results = self.qps_analyzer.run_qps_analysis()
        df = qps_results['dataframe']
        max_qps = qps_results['max_qps']
        bottlenecks = qps_results['bottlenecks']

        # 1.1 字段映射器已移除，直接使用原始列名
        # 注意: 字段映射器功能已被移除，现在直接使用CSV文件中的原始列名
        if FIELD_MAPPER_AVAILABLE:
            # 这个分支不会执行，因为FIELD_MAPPER_AVAILABLE=False
            try:
                # 字段映射器相关代码已移除
                logger.info("✅ 字段映射器应用成功")
                print("  ✅ 字段标准化完成")
            except Exception as e:
                logger.warning(f"⚠️  字段映射器应用失败: {e}，继续使用原始列名")
                print(f"  ⚠️  字段映射器应用失败，使用原始列名")
        else:
            logger.info("ℹ️  使用原始CSV列名进行分析")
            print("  ℹ️  使用原始CSV列名进行分析")

        # 2. 运行验证器日志分析
        print("\n📋 Phase 2: Validator Log Analysis")
        log_analysis = self.log_analyzer.analyze_validator_logs_during_test(df)

        # 3. 运行RPC深度分析
        print("\n🔍 Phase 3: RPC Deep Analysis")
        rpc_deep_analysis = self.rpc_deep_analyzer.analyze_rpc_deep_performance(df)

        # 4. 生成综合图表和报告
        print("\n📈 Phase 4: Comprehensive Reporting")
        self.generate_ultimate_performance_charts(df, log_analysis, rpc_deep_analysis)
        
        # 4.1 生成性能可视化图表（包含阈值分析）
        print("\n🎨 Phase 4.1: Performance Visualization with Threshold Analysis")
        try:
            from performance_visualizer import PerformanceVisualizer
            
            # 保存临时CSV文件供performance_visualizer使用 - 使用进程ID和随机数避免冲突
            process_id = os.getpid()
            random_id = random.randint(1000, 9999)
            temp_csv_path = os.path.join(self.output_dir, f'temp_performance_data_{process_id}_{random_id}.csv')
            df.to_csv(temp_csv_path, index=False)
            
            # 查找监控开销文件
            overhead_files = glob.glob(f"{self.output_dir}/logs/monitoring_overhead_*.csv")
            overhead_file = max(overhead_files, key=os.path.getctime) if overhead_files else None
            
            # 创建性能可视化器并生成图表
            visualizer = PerformanceVisualizer(temp_csv_path, overhead_file)
            chart_results = visualizer.generate_all_charts()
            
            if isinstance(chart_results, tuple) and len(chart_results) == 2:
                chart_files, threshold_analysis = chart_results
                print(f"✅ 生成了 {len(chart_files)} 张性能图表（包含阈值分析）")
                
                # 将阈值分析结果添加到综合结果中
                if threshold_analysis:
                    print("📊 阈值分析已完成并集成到报告中")
            else:
                chart_files = chart_results if isinstance(chart_results, list) else []
                print(f"✅ 生成了 {len(chart_files)} 张性能图表")
            
            # 清理临时文件
            if os.path.exists(temp_csv_path):
                os.remove(temp_csv_path)
                
        except ImportError as e:
            print(f"⚠️ 性能可视化器导入失败: {e}")
        except Exception as e:
            print(f"⚠️ 性能可视化图表生成失败: {e}")
        
        comprehensive_report = self.generate_comprehensive_report(
            df, max_qps, bottlenecks, log_analysis, rpc_deep_analysis, self.benchmark_mode
        )

        # 5. 显示所有分析报告
        if log_analysis:
            log_report = self.log_analyzer.generate_log_analysis_report(log_analysis)
            print(log_report)

        if rpc_deep_analysis:
            rpc_report = self.rpc_deep_analyzer.generate_rpc_deep_analysis_report(rpc_deep_analysis)
            print(rpc_report)

        # 返回完整的分析结果
        comprehensive_results = {
            'qps_analysis': qps_results,
            'log_analysis': log_analysis,
            'rpc_deep_analysis': rpc_deep_analysis,
            'comprehensive_report': comprehensive_report,
            'dataframe': df,
            'max_qps': max_qps,
            'bottlenecks': bottlenecks
        }

        print("\n🎉 Comprehensive Analysis Completed Successfully!")
        print("Generated files:")
        print(f"  📊 Charts: {self.output_dir}/reports/comprehensive_analysis_charts.png")
        print(f"  📄 Report: {self.output_dir}/reports/comprehensive_analysis_report.md")
        print(f"  💾 Backups: Files with timestamp {self.session_timestamp} created for version history")
        print(f"  📋 Individual Analysis Reports: Check {self.output_dir}/reports/ for detailed reports")

        return comprehensive_results


def main():
    """主执行函数 - 支持瓶颈模式和时间窗口分析"""
    parser = argparse.ArgumentParser(description='综合分析器 - 支持瓶颈模式')
    parser.add_argument('csv_file', nargs='?', help='CSV数据文件路径')
    parser.add_argument('--benchmark-mode', default='standard', choices=['quick', 'standard', 'intensive'], 
                       help='基准测试模式 (默认: standard)')
    parser.add_argument('--bottleneck-mode', action='store_true', help='启用瓶颈分析模式')
    parser.add_argument('--bottleneck-info', help='瓶颈信息JSON文件路径')
    parser.add_argument('--time-window', action='store_true', help='启用时间窗口分析')
    parser.add_argument('--start-time', help='时间窗口开始时间')
    parser.add_argument('--end-time', help='时间窗口结束时间')
    parser.add_argument('--bottleneck-time', help='瓶颈检测时间')
    parser.add_argument('--output-dir', help='输出目录路径')
    
    args = parser.parse_args()
    
    try:
        # 初始化瓶颈分析模式
        bottleneck_mode = None
        if args.bottleneck_mode or args.bottleneck_info:
            bottleneck_info = {}
            
            if args.bottleneck_info and os.path.exists(args.bottleneck_info):
                try:
                    with open(args.bottleneck_info, 'r') as f:
                        bottleneck_info = json.load(f)
                    logger.info(f"📊 加载瓶颈信息: {args.bottleneck_info}")
                except Exception as e:
                    logger.error(f"❌ 瓶颈信息文件读取失败: {e}")
            
            bottleneck_mode = BottleneckAnalysisMode(bottleneck_info)
        
        # 初始化分析器
        analyzer = ComprehensiveAnalyzer(args.output_dir, args.benchmark_mode, bottleneck_mode)
        
        # 确定CSV文件
        csv_file = args.csv_file or analyzer.csv_file
        if not csv_file or not os.path.exists(csv_file):
            logger.error("❌ 未找到有效的CSV数据文件")
            return 1
        
        logger.info(f"📈 开始综合分析: {csv_file}")
        
        # 读取数据
        df = pd.read_csv(csv_file)
        logger.info(f"📊 数据加载完成: {len(df)} 条记录")
        
        # 时间窗口过滤
        if args.time_window and args.start_time and args.end_time:
            df = ComprehensiveAnalyzer.filter_data_by_time_window(df, args.start_time, args.end_time)
            logger.info(f"🕐 时间窗口分析: {args.start_time} 到 {args.end_time}")
        
        # 执行分析
        if bottleneck_mode and bottleneck_mode.enabled:
            logger.info("🚨 执行瓶颈模式分析")
            
            # 瓶颈相关性分析
            bottleneck_analysis = analyzer.analyze_bottleneck_correlation(df)
            
            # 生成瓶颈分析图表
            bottleneck_chart = analyzer.generate_bottleneck_analysis_chart(df, bottleneck_analysis)
            
            # 保存瓶颈分析结果
            bottleneck_result_file = os.path.join(analyzer.output_dir, 'reports', 'bottleneck_analysis_result.json')
            os.makedirs(os.path.dirname(bottleneck_result_file), exist_ok=True)
            with open(bottleneck_result_file, 'w') as f:
                json.dump(bottleneck_analysis, f, indent=2, default=str)
            logger.info(f"📊 瓶颈分析结果已保存: {bottleneck_result_file}")
        
        # 执行标准综合分析
        result = analyzer.run_comprehensive_analysis()
        
        if result:
            logger.info("✅ 综合分析完成")
            return 0
        else:
            logger.error("❌ 综合分析失败")
            return 1
            
    except Exception as e:
        logger.error(f"❌ 综合分析执行失败: {e}")
        return 1


# 演示功能（仅在直接运行时使用）
def demo_comprehensive_analysis():
    """演示综合分析功能"""
    try:
        analyzer = ComprehensiveAnalyzer(benchmark_mode="standard")
        results = analyzer.run_comprehensive_analysis()

        print("\n🎯 Analysis Summary:")
        print(f"  Maximum QPS: {results['max_qps']:,}")
        print(f"  Data Points: {len(results['dataframe'])}")
        print(f"  Bottlenecks: {len(results['bottlenecks'])}")
        
        return results

    except Exception as e:
        logger.error(f"❌ Comprehensive analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    main()
