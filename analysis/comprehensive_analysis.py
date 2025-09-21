#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Analyzer - Refactored integrated version with bottleneck mode support
Integrates RPC deep analyzer and QPS analyzer for blockchain node performance testing
Provides unified analysis entry point and complete report generation
Supports bottleneck detection mode and time window analysis
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import glob
import os
import sys

# Configure font support for cross-platform compatibility
def setup_font():
    """Configure matplotlib font for cross-platform compatibility"""
    # Use standard fonts that work across all platforms
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False
    print("✅ SUCCESS: Comprehensive Analysis using font: DejaVu Sans")
    return True

# Initialize font configuration
setup_font()

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
        self.reports_dir = os.getenv('REPORTS_DIR', os.path.join(output_dir, 'current', 'reports'))
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
analysis_dir = current_dir  # 添加当前analysis目录

# 添加路径到sys.path
for path in [str(utils_dir), str(visualization_dir), str(analysis_dir)]:
    if path not in sys.path:
        sys.path.insert(0, path)

# 导入拆分后的模块
try:
    # 尝试相对导入（当作为模块导入时）
    from .rpc_deep_analyzer import RpcDeepAnalyzer
    from .qps_analyzer import NodeQPSAnalyzer
    logger.info("✅ 所有分析模块加载成功")
except ImportError:
    try:
        # 尝试直接导入（当直接运行脚本时）
        from rpc_deep_analyzer import RpcDeepAnalyzer
        from qps_analyzer import NodeQPSAnalyzer
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
            self.max_qps = self.bottleneck_info.get('max_successful_qps', 0)
            self.bottleneck_qps = self.bottleneck_info.get('bottleneck_qps', 0)
            
            logger.info(f"🚨 瓶颈分析模式: 最大QPS={self.max_qps}, 瓶颈QPS={self.bottleneck_qps}")
        except Exception as e:
            logger.error(f"❌ 瓶颈信息解析失败: {e}")
            self.enabled = False

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
        self.qps_analyzer = NodeQPSAnalyzer(output_dir, benchmark_mode, self.bottleneck_mode.enabled)
        self.rpc_deep_analyzer = RpcDeepAnalyzer(self.csv_file)
        
        # 初始化文件管理器
        self.file_manager = FileManager(self.output_dir, self.session_timestamp)
        
        # Using English labels system directly
        
        logger.info(f"🔍 初始化综合分析器，输出目录: {output_dir}")
        if self.bottleneck_mode.enabled:
            logger.info(f"🚨 瓶颈分析模式已启用")
    
    def get_latest_csv(self) -> Optional[str]:
        """获取最新的CSV监控文件"""
        # 使用环境变量LOGS_DIR，如果不存在则使用current/logs结构
        logs_dir = os.getenv('LOGS_DIR', os.path.join(self.output_dir, 'current', 'logs'))
        csv_files = glob.glob(f"{logs_dir}/*.csv")
        if not csv_files:
            # 备用查找：检查archives目录
            csv_files = glob.glob(f"{self.output_dir}/archives/*/logs/*.csv")
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

    def generate_ultimate_performance_charts(self, df: pd.DataFrame, 
                                           rpc_deep_analysis: Dict[str, Any]) -> Optional[plt.Figure]:
        """生成终极性能图表，整合所有分析结果"""
        print("\n📈 Generating ultimate performance charts...")

        if len(df) == 0:
            print("❌ No QPS data for chart generation")
            return None

        plt.style.use('default')
        fig, axes = plt.subplots(3, 2, figsize=(16, 18))
        # Using English title directly
        fig.suptitle('Blockchain Node QPS Ultimate Performance Analysis Dashboard', fontsize=16, fontweight='bold')

        # 检查QPS数据可用性
        qps_available = 'qps_data_available' in df.columns and df['qps_data_available'].iloc[0] if len(df) > 0 else False
        
        # 1. CPU使用率 vs QPS
        if len(df) > 0 and 'cpu_usage' in df.columns and qps_available and 'current_qps' in df.columns:
            axes[0, 0].plot(df['current_qps'], df['cpu_usage'], 'bo-', alpha=0.7, markersize=4)
            axes[0, 0].axhline(y=85, color='red', linestyle='--', alpha=0.8, label='Warning (85%)')
            axes[0, 0].set_title('CPU Usage vs QPS')
            axes[0, 0].set_xlabel('QPS')
            axes[0, 0].set_ylabel('CPU %')
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)
        else:
            axes[0, 0].text(0.5, 0.5, 'QPS Data Not Available\nfor CPU Analysis', ha='center', va='center',
                           transform=axes[0, 0].transAxes, fontsize=12)
            axes[0, 0].set_title('CPU Usage vs QPS (No Data)')

        # 2. 内存使用率 vs QPS
        if len(df) > 0 and 'mem_usage' in df.columns and qps_available and 'current_qps' in df.columns:
            axes[0, 1].plot(df['current_qps'], df['mem_usage'], 'go-', alpha=0.7, markersize=4)
            axes[0, 1].axhline(y=90, color='red', linestyle='--', alpha=0.8, label='Warning (90%)')
            axes[0, 1].set_title('Memory Usage vs QPS')
            axes[0, 1].set_xlabel('QPS')
            axes[0, 1].set_ylabel('Memory %')
            axes[0, 1].legend()
            axes[0, 1].grid(True, alpha=0.3)
        else:
            axes[0, 1].text(0.5, 0.5, 'QPS Data Not Available\nfor Memory Analysis', ha='center', va='center',
                           transform=axes[0, 1].transAxes, fontsize=12)
            axes[0, 1].set_title('Memory Usage vs QPS (No Data)')

        # 3. RPC延迟 vs QPS
        if len(df) > 0 and 'rpc_latency_ms' in df.columns and qps_available and 'current_qps' in df.columns and df['rpc_latency_ms'].notna().any():
            axes[1, 0].plot(df['current_qps'], df['rpc_latency_ms'], 'ro-', alpha=0.7, markersize=4)
            axes[1, 0].axhline(y=1000, color='orange', linestyle='--', alpha=0.8, label='High Latency (1s)')
            axes[1, 0].set_title('RPC Latency vs QPS')
            axes[1, 0].set_xlabel('QPS')
            axes[1, 0].set_ylabel('Latency (ms)')
            axes[1, 0].legend()
            axes[1, 0].grid(True, alpha=0.3)
        else:
            axes[1, 0].text(0.5, 0.5, 'QPS Data Not Available\nfor RPC Latency Analysis', ha='center', va='center',
                           transform=axes[1, 0].transAxes, fontsize=12)
            axes[1, 0].set_title('RPC Latency vs QPS (No Data)')

        # 4. RPC延迟分布（移动到第2行第0列）
        if len(df) > 0 and 'rpc_latency_ms' in df.columns and df['rpc_latency_ms'].notna().any():
            axes[2, 0].hist(df['rpc_latency_ms'], bins=30, alpha=0.7, color='purple')
            if 'rpc_latency_ms' in df.columns:
                mean_latency = df['rpc_latency_ms'].mean()
                p95_latency = df['rpc_latency_ms'].quantile(0.95)
                axes[2, 0].axvline(mean_latency, color='red', linestyle='--',
                                   label=f'Mean: {mean_latency:.1f}ms')
                axes[2, 0].axvline(p95_latency, color='orange', linestyle='--',
                                   label=f'P95: {p95_latency:.1f}ms')
            axes[2, 0].set_title('RPC Latency Distribution')
            axes[2, 0].set_xlabel('Latency (ms)')
            axes[2, 0].set_ylabel('Frequency')
            axes[2, 0].legend()
            axes[2, 0].grid(True, alpha=0.3)

        # 5. 性能悬崖可视化
        cliff_analysis = rpc_deep_analysis.get('performance_cliff', {})
        if cliff_analysis and len(df) > 0 and qps_available and 'current_qps' in df.columns and 'rpc_latency_ms' in df.columns and df['rpc_latency_ms'].notna().any():
            try:
                qps_latency = df.groupby('current_qps')['rpc_latency_ms'].mean().reset_index()
                qps_latency = qps_latency.sort_values('current_qps')

                axes[2, 1].plot(qps_latency['current_qps'], qps_latency['rpc_latency_ms'], 'bo-', alpha=0.7)

                # 标记悬崖点
                cliff_points = cliff_analysis.get('performance_degradation_qps', [])
                for cliff_qps in cliff_points:
                    cliff_latency = qps_latency[qps_latency['current_qps'] == cliff_qps]['rpc_latency_ms']
                    if len(cliff_latency) > 0:
                        axes[2, 1].scatter(cliff_qps, cliff_latency.iloc[0], color='red', s=100, marker='x',
                                           label='Performance Cliff')

                axes[2, 1].set_title('Performance Cliff Detection')
                axes[2, 1].set_xlabel('QPS')
                axes[2, 1].set_ylabel('Average Latency (ms)')
                axes[2, 1].grid(True, alpha=0.3)
                if cliff_points:
                    axes[2, 1].legend()
            except Exception as e:
                logger.warning(f"⚠️ Performance cliff visualization failed: {e}")
                axes[2, 1].text(0.5, 0.5, 'Performance Cliff Analysis\nData Processing Error', ha='center', va='center',
                               transform=axes[2, 1].transAxes, fontsize=12)
                axes[2, 1].set_title('Performance Cliff Detection (Error)')
        else:
            axes[2, 1].text(0.5, 0.5, 'QPS Data Not Available\nfor Cliff Analysis', ha='center', va='center',
                           transform=axes[2, 1].transAxes, fontsize=12)
            axes[2, 1].set_title('Performance Cliff Detection (No Data)')

        plt.tight_layout()
        
        # 保存图表 - 使用文件管理器，同时创建当前版本和备份
        chart_file = self.file_manager.save_chart_with_backup('comprehensive_analysis_charts', plt)
        print(f"✅ Ultimate performance charts saved: {chart_file}")

        return fig

    def _evaluate_comprehensive_performance(self, benchmark_mode: str, max_qps: int, 
                                          bottlenecks: Dict[str, Any], avg_cpu: float, 
                                          avg_mem: float, avg_rpc: float) -> Dict[str, Any]:
        """
        基于实际监控数据的科学性能评估
        整合QPS性能、系统资源使用率、RPC延迟等多维度监控数据
        """
        
        # 只有深度基准测试模式才能进行准确的性能等级评估
        if benchmark_mode != "intensive":
            return {
                'performance_level': 'Unable to Evaluate',
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
        
        # 综合瓶颈分析 - 基于实际监控数据
        bottleneck_types = bottlenecks.get('detected_bottlenecks', [])
        
        # 计算综合瓶颈评分 - 不再依赖废弃的日志分析数据
        comprehensive_score = ComprehensiveAnalyzer._calculate_comprehensive_bottleneck_score(
            bottleneck_types, avg_cpu, avg_mem, avg_rpc
        )
        
        # 基于综合评分的科学等级评估
        if comprehensive_score < 0.2:
            level = "Excellent"
            grade = "A (Excellent)"
            reason = f"System performs excellently at {max_qps} QPS, all metrics within normal range"
            
        elif comprehensive_score < 0.4:
            level = "Good"
            grade = "B (Good)"
            reason = f"System performs well at {max_qps} QPS, with minor bottlenecks or issues"
            
        elif comprehensive_score < 0.7:
            level = "Acceptable"
            grade = "C (Acceptable)"
            reason = f"System performs acceptably at {max_qps} QPS, with noticeable bottlenecks requiring attention"
            
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
            'avg_rpc_latency': avg_rpc,
            'recommendations': ComprehensiveAnalyzer._generate_comprehensive_recommendations(
                bottleneck_types, comprehensive_score, max_qps, avg_rpc
            )
        }
    
    @staticmethod
    def _calculate_comprehensive_bottleneck_score(bottleneck_types: list, 
                                                avg_cpu: float, avg_mem: float, avg_rpc: float) -> float:
        """计算综合瓶颈严重程度评分 - 基于实际监控数据"""
        
        total_score = 0.0
        
        # 系统资源瓶颈评分 (权重: 0.7)
        resource_score = 0.0
        if 'CPU' in bottleneck_types:
            resource_score += 0.3 * (1.5 if avg_cpu > 90 else 1.0)
        if 'Memory' in bottleneck_types:
            resource_score += 0.3 * (1.5 if avg_mem > 95 else 1.0)
        if 'EBS' in bottleneck_types:
            resource_score += 0.1
        
        # RPC性能评分 (权重: 0.3) - 基于实际RPC延迟监控数据
        rpc_score = 0.0
        if avg_rpc > 1000:  # 高延迟
            rpc_score += 0.15
        if avg_rpc > 2000:  # 极高延迟
            rpc_score += 0.15
        
        total_score = resource_score + rpc_score
        
        return min(total_score, 1.0)
    
    @staticmethod
    def _generate_comprehensive_capacity_assessment(performance_evaluation: Dict[str, Any], max_qps: int) -> str:
        """基于综合性能评估生成容量评估 - 静态方法"""
        performance_level = performance_evaluation.get('performance_level', '未知')
        comprehensive_score = performance_evaluation.get('comprehensive_score', 0.0)
        
        if performance_level == "Excellent":
            return f"Current configuration can stably handle high load (tested up to {max_qps:,} QPS, comprehensive score: {comprehensive_score:.3f})" if not pd.isna(max_qps) else f"Current configuration can stably handle high load (insufficient test data, comprehensive score: {comprehensive_score:.3f})"
        elif performance_level == "Good":
            return f"Current configuration can handle medium-high load (tested up to {max_qps:,} QPS, with minor issues)" if not pd.isna(max_qps) else "Current configuration can handle medium-high load (insufficient test data, with minor issues)"
        elif performance_level == "Acceptable":
            return f"Current configuration suitable for medium load (tested up to {max_qps:,} QPS, with noticeable issues)" if not pd.isna(max_qps) else "Current configuration suitable for medium load (insufficient test data, with noticeable issues)"
        elif performance_level == "需要优化":
            return f"当前配置需要优化以处理高负载 (已测试至 {max_qps:,} QPS，存在严重问题)" if not pd.isna(max_qps) else "当前配置需要优化以处理高负载 (测试数据不足，存在严重问题)"
        else:
            return f"需要intensive基准测试模式进行准确的容量评估"

    @staticmethod
    def _generate_comprehensive_recommendations(bottleneck_types: list, 
                                             comprehensive_score: float, max_qps: int, avg_rpc: float) -> list:
        """基于综合分析生成优化建议 - 基于实际监控数据"""
        recommendations = []
        
        if comprehensive_score < 0.2:
            recommendations.extend([
                f"🎉 System comprehensive performance is excellent, current configuration can stably support {max_qps} QPS",
                "💡 Consider further increasing QPS targets or optimizing cost efficiency",
                "� Recomdmend regular monitoring to maintain current performance level"
            ])
        else:
            # 系统资源优化建议
            if 'CPU' in bottleneck_types:
                recommendations.append("🔧 CPU瓶颈：考虑升级CPU或优化计算密集型进程")
            if 'Memory' in bottleneck_types:
                recommendations.append("🔧 内存瓶颈：考虑增加内存或优化内存使用")
            if 'EBS' in bottleneck_types:
                recommendations.append("🔧 存储瓶颈：考虑升级EBS类型或优化I/O模式")
            
            # 基于实际RPC延迟的优化建议
            if avg_rpc > 1000:
                recommendations.append("🔧 RPC延迟较高：考虑优化RPC配置或增加RPC处理能力")
            if avg_rpc > 2000:
                recommendations.append("🔥 RPC延迟过高：需要立即优化RPC性能或检查网络连接")
        
        return recommendations

    @OperationLogger.log_operation("Generating comprehensive report", "📄")
    def generate_comprehensive_report(self, df: pd.DataFrame, max_qps: int, 
                                    bottlenecks: Dict[str, Any], 
                                    rpc_deep_analysis: Dict[str, Any],
                                    benchmark_mode: str = "standard") -> str:
        """生成基于瓶颈分析的综合报告，整合所有分析结果"""

        # 基本性能指标 - 使用工具类避免重复代码
        avg_cpu = DataProcessor.safe_calculate_mean(df, 'cpu_usage')
        avg_mem = DataProcessor.safe_calculate_mean(df, 'mem_usage')
        avg_rpc = DataProcessor.safe_calculate_mean(df, 'rpc_latency_ms') if 'rpc_latency_ms' in df.columns else 0

        # 注意：当前框架只使用实时监控数据，不再依赖区块链节点日志分析
        # RPC分析基于监控数据中的延迟指标，不是日志解析结果
        
        # 基于基准测试模式和瓶颈分析的性能评估
        # 不再使用废弃的日志分析数据，直接基于监控数据进行评估
        performance_evaluation = self._evaluate_comprehensive_performance(
            benchmark_mode, max_qps, bottlenecks, avg_cpu, avg_mem, avg_rpc
        )

        # 构建报告的各个部分
        cpu_bottleneck = 'Detected' if 'CPU' in bottlenecks.get('detected_bottlenecks', []) else 'None detected'
        memory_bottleneck = 'Detected' if 'Memory' in bottlenecks.get('detected_bottlenecks', []) else 'None detected'
        network_bottleneck = 'Detected' if 'Network' in bottlenecks.get('detected_bottlenecks', []) else 'None detected'
        ebs_bottleneck = 'Detected' if 'EBS' in bottlenecks.get('detected_bottlenecks', []) else 'None detected'
        
        max_cpu = DataProcessor.safe_calculate_max(df, 'cpu_usage')
        max_mem = DataProcessor.safe_calculate_max(df, 'mem_usage')
        max_rpc_latency = DataProcessor.safe_calculate_max(df, 'rpc_latency_ms') if 'rpc_latency_ms' in df.columns else 0
        
        latency_trend = 'Stable' if max_rpc_latency < avg_rpc * 2 else 'Variable'

        # 处理可能的NaN值
        max_qps_display = f"{max_qps:,}" if not pd.isna(max_qps) else "N/A"
        
        report = f"""# Blockchain Node QPS Comprehensive Performance Analysis Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
- **Maximum QPS Achieved**: {max_qps_display}
- **Performance Grade**: {performance_evaluation['performance_grade']}
- **Performance Level**: {performance_evaluation['performance_level']}
- **Benchmark Mode**: {benchmark_mode}
- **Test Duration**: {len(df)} monitoring points
- **Monitoring Data Points**: {len(df)} records
- **Analysis Coverage**: Complete system performance monitoring

## Performance Evaluation
- **Evaluation Basis**: {performance_evaluation['evaluation_basis']}
- **Evaluation Reason**: {performance_evaluation['evaluation_reason']}
- **Comprehensive Score**: {performance_evaluation.get('comprehensive_score', 0.0):.3f}

## System Performance Metrics
- **Average CPU Usage**: {avg_cpu:.1f}%
- **Average Memory Usage**: {avg_mem:.1f}%
- **Average RPC Latency**: {avg_rpc:.1f}ms
- **CPU Peak**: {max_cpu:.1f}%
- **Memory Peak**: {max_mem:.1f}%
- **RPC Latency Peak**: {max_rpc_latency:.1f}ms

## 🔍 System Performance Analysis Results

### Monitoring Data Analysis
- **QPS Performance**: Based on real-time system monitoring and CSV data
- **System Resource Usage**: CPU, Memory, Network utilization continuously tracked
- **RPC Performance Monitoring**: Average latency {avg_rpc:.1f}ms from monitoring data
- **Peak RPC Latency**: {max_rpc_latency:.1f}ms during test period

### Resource Bottleneck Detection
- **CPU Bottlenecks**: {cpu_bottleneck}
- **Memory Bottlenecks**: {memory_bottleneck}
- **Network Bottlenecks**: {network_bottleneck}
- **EBS Bottlenecks**: {ebs_bottleneck}

### Performance Trend Analysis
- **QPS Stability**: Analyzed from {len(df)} monitoring data points
- **Latency Trend**: {latency_trend} throughout test period
- **Resource Utilization**: CPU avg {avg_cpu:.1f}%, Memory avg {avg_mem:.1f}%
- **Data Source**: Real-time system monitoring and RPC performance tracking
"""

        # 添加RPC深度分析结果
        if rpc_deep_analysis:
            rpc_deep_report = self.rpc_deep_analyzer.generate_rpc_deep_analysis_report(rpc_deep_analysis)
            report += rpc_deep_report

        # 优化建议
        report += """
## 💡 Comprehensive Optimization Recommendations

### Immediate Actions
"""

        # 基于现有监控数据的具体建议
        if avg_rpc > 1000:
            report += "- 🔧 **High Priority**: RPC latency is high, consider optimization\n"
            
        if max_rpc_latency > 2000:
            report += "- 🔥 **Critical**: Peak RPC latency detected, investigate bottlenecks\n"

        if avg_mem > 90:
            report += "- 🔥 **Critical**: High memory usage detected, consider increasing memory\n"
            report += "- 🔧 Monitor for potential memory leaks\n"

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

        # 生产部署建议
        capacity_assessment = ComprehensiveAnalyzer._generate_comprehensive_capacity_assessment(performance_evaluation, max_qps)
        csv_file_display = self.csv_file or 'N/A'
        
        # 计算推荐生产QPS
        recommended_qps_display = f"{int(max_qps * 0.8):,} (80% of maximum tested)" if not pd.isna(max_qps) else "N/A (insufficient test data)"
        
        report += f"""
### Production Deployment
- **Recommended Production QPS**: {recommended_qps_display}
- **Monitoring Thresholds**: 
  - Alert if RPC latency P99 > 500ms sustained
  - Alert if CPU usage > 85% sustained
  - Alert if Memory usage > 90% sustained
- **Capacity Assessment**: {capacity_assessment}

## Files Generated
- **Comprehensive Charts**: `{self.reports_dir}/comprehensive_analysis_charts.png`
- **Raw Monitoring Data**: `{csv_file_display}`
- **System Performance Analysis**: Included in this report
- **RPC Performance Analysis**: Included in this report
- **Load Test Reports**: `{self.reports_dir}/`

---
*Report generated by Comprehensive Blockchain Node QPS Analyzer v4.0*
"""

        # 保存综合报告 - 使用文件管理器，同时创建当前版本和备份
        report_file = self.file_manager.save_report_with_backup('comprehensive_analysis_report', report)

        print(f"✅ Comprehensive report saved: {report_file}")
        return report

    def run_comprehensive_analysis(self) -> Dict[str, Any]:
        """运行完整的综合分析"""
        print("🚀 Starting Comprehensive Blockchain Node QPS Analysis")
        print("=" * 80)

        # 1. 运行QPS分析
        print("\n📊 Phase 1: QPS Performance Analysis")
        qps_results = self.qps_analyzer.run_qps_analysis()
        df = qps_results['dataframe']
        max_qps = qps_results['max_qps']
        bottlenecks = qps_results['bottlenecks']

        # 1.1 Using direct CSV column names for analysis
        logger.info("ℹ️  Using monitoring data for comprehensive analysis")
        print("  ℹ️  Using monitoring data for comprehensive analysis")

        # 2. 运行RPC深度分析
        print("\n🔍 Phase 2: RPC Deep Analysis")
        rpc_deep_analysis = self.rpc_deep_analyzer.analyze_rpc_deep_performance(df)

        # 3. 生成综合图表和报告
        print("\n📈 Phase 3: Comprehensive Reporting")
        self.generate_ultimate_performance_charts(df, rpc_deep_analysis)
        
        # 4.1 生成性能可视化图表（包含阈值分析）
        print("\n🎨 Phase 4.1: Performance Visualization with Threshold Analysis")
        try:
            from performance_visualizer import PerformanceVisualizer
            
            # 保存临时CSV文件供performance_visualizer使用 - 使用进程ID和随机数避免冲突
            process_id = os.getpid()
            random_id = random.randint(1000, 9999)
            # 使用TMP_DIR环境变量或current/tmp目录保存临时文件
            tmp_dir = os.getenv('TMP_DIR', os.path.join(self.output_dir, 'current', 'tmp'))
            os.makedirs(tmp_dir, exist_ok=True)
            temp_csv_path = os.path.join(tmp_dir, f'temp_performance_data_{process_id}_{random_id}.csv')
            df.to_csv(temp_csv_path, index=False)
            
            # 查找监控开销文件 - 增强查找逻辑以处理归档情况
            overhead_files = glob.glob(f"{self.output_dir}/current/logs/monitoring_overhead_*.csv")
            if not overhead_files:
                # 如果current目录没有，检查archives目录
                overhead_files = glob.glob(f"{self.output_dir}/archives/*/logs/monitoring_overhead_*.csv")
            if not overhead_files:
                # 最后检查当前工作目录
                overhead_files = glob.glob("monitoring_overhead_*.csv")
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
            df, max_qps, bottlenecks, rpc_deep_analysis, self.benchmark_mode
        )

        # 5. 显示RPC深度分析报告

        if rpc_deep_analysis:
            rpc_report = self.rpc_deep_analyzer.generate_rpc_deep_analysis_report(rpc_deep_analysis)
            print(rpc_report)

        # 返回完整的分析结果
        comprehensive_results = {
            'qps_analysis': qps_results,
            'rpc_deep_analysis': rpc_deep_analysis,
            'comprehensive_report': comprehensive_report,
            'dataframe': df,
            'max_qps': max_qps,
            'bottlenecks': bottlenecks
        }

        print("\n🎉 Comprehensive Analysis Completed Successfully!")
        print("Generated files:")
        print(f"  📊 Charts: {self.reports_dir}/comprehensive_analysis_charts.png")
        print(f"  📄 Report: {self.reports_dir}/comprehensive_analysis_report.md")
        print(f"  💾 Backups: Files with timestamp {self.session_timestamp} created for version history")
        print(f"  📋 Individual Analysis Reports: Check {self.reports_dir}/ for detailed reports")

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

            # 保存瓶颈分析结果
            reports_dir = os.getenv('REPORTS_DIR', os.path.join(analyzer.output_dir, 'current', 'reports'))
            bottleneck_result_file = os.path.join(reports_dir, 'bottleneck_analysis_result.json')
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
        print(f"  Maximum QPS: {results['max_qps']:,}" if not pd.isna(results['max_qps']) else "  Maximum QPS: N/A")
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
