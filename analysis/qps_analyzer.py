#!/usr/bin/env python3
"""
QPS分析器 - 从comprehensive_analysis.py拆分出来的独立模块 + 瓶颈模式支持
专门负责QPS性能分析，包括性能指标分析、瓶颈识别、图表生成等
支持性能悬崖分析和瓶颈检测模式
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import os
import json
import argparse
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

# 使用统一日志管理器
import sys

# 使用更健壮的路径管理
current_dir = Path(__file__).parent
utils_dir = current_dir.parent / 'utils'
if str(utils_dir) not in sys.path:
    sys.path.insert(0, str(utils_dir))

try:
    from unified_logger import get_logger
    logger = get_logger(__name__)
    logger.info("✅ 统一日志管理器初始化成功")
except ImportError as e:
    # 降级到标准logging
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ 统一日志管理器不可用，使用标准logging: {e}")

class NodeQPSAnalyzer:
    """区块链节点 QPS性能分析器 + 瓶颈模式支持 - 支持多种区块链"""

    def __init__(self, output_dir: Optional[str] = None, benchmark_mode: str = "standard", bottleneck_mode: bool = False):
        """
        初始化QPS分析器
        
        Args:
            output_dir: 输出目录路径（如果为None，将从环境变量获取）
            benchmark_mode: 基准测试模式 (quick/standard/intensive)
            bottleneck_mode: 是否启用瓶颈分析模式
        """
        if output_dir is None:
            output_dir = os.environ.get('DATA_DIR', os.path.join(os.path.expanduser('~'), 'blockchain-node-benchmark-result'))
        
        self.output_dir = output_dir
        self.benchmark_mode = benchmark_mode
        self.bottleneck_mode = bottleneck_mode
        self.reports_dir = os.path.join(output_dir, 'reports')
        os.makedirs(self.reports_dir, exist_ok=True)
        
        # 瓶颈检测阈值配置
        self.cpu_threshold = int(os.getenv('BOTTLENECK_CPU_THRESHOLD', 85))
        self.memory_threshold = int(os.getenv('BOTTLENECK_MEMORY_THRESHOLD', 90))
        self.rpc_threshold = int(os.getenv('MAX_LATENCY_THRESHOLD', 1000))
        
        # 初始化CSV文件路径 - 修复缺失的属性
        self.csv_file = self.get_latest_csv()

        # Using English labels system directly
        
        logger.info(f"🔍 QPS分析器初始化完成，输出目录: {output_dir}, 基准测试模式: {benchmark_mode}")
        if bottleneck_mode:
            logger.info("🚨 瓶颈分析模式已启用")

    def _get_dynamic_key_metrics(self, df: pd.DataFrame) -> list:
        """动态获取关键指标字段，替代硬编码设备名 - 完整版本"""
        base_metrics = ['cpu_usage', 'mem_usage']
        
        # 动态查找EBS利用率字段（优先DATA设备，然后ACCOUNTS设备）
        ebs_util_field = None
        # 首先查找DATA设备字段（必须存在）
        for col in df.columns:
            if col.startswith('data_') and col.endswith('_util'):
                ebs_util_field = col
                break
        
        # 如果没有DATA设备字段，查找ACCOUNTS设备字段（可选）
        if not ebs_util_field:
            for col in df.columns:
                if col.startswith('accounts_') and col.endswith('_util'):
                    ebs_util_field = col
                    break
        
        # 动态查找EBS延迟字段（优先DATA设备的r_await）
        ebs_latency_field = None
        # 首先查找DATA设备的r_await字段
        for col in df.columns:
            if col.startswith('data_') and col.endswith('_r_await'):
                ebs_latency_field = col
                break
        
        # 如果没有DATA设备的r_await，查找DATA设备的avg_await
        if not ebs_latency_field:
            for col in df.columns:
                if col.startswith('data_') and col.endswith('_avg_await'):
                    ebs_latency_field = col
                    break
        
        # 如果DATA设备都没有，查找ACCOUNTS设备的延迟字段（可选）
        if not ebs_latency_field:
            for col in df.columns:
                if col.startswith('accounts_') and col.endswith('_r_await'):
                    ebs_latency_field = col
                    break
        
        if not ebs_latency_field:
            for col in df.columns:
                if col.startswith('accounts_') and col.endswith('_avg_await'):
                    ebs_latency_field = col
                    break
        
        # 动态查找其他重要EBS指标（优先DATA设备）
        ebs_iops_field = None
        # 首先查找DATA设备字段
        for col in df.columns:
            if col.startswith('data_') and col.endswith('_total_iops'):
                ebs_iops_field = col
                break
        # 如果没有DATA设备字段，查找ACCOUNTS设备字段（可选）
        if not ebs_iops_field:
            for col in df.columns:
                if col.startswith('accounts_') and col.endswith('_total_iops'):
                    ebs_iops_field = col
                    break
        
        ebs_throughput_field = None
        # 首先查找DATA设备字段
        for col in df.columns:
            if col.startswith('data_') and col.endswith('_throughput_mibs'):
                ebs_throughput_field = col
                break
        # 如果没有DATA设备字段，查找ACCOUNTS设备字段（可选）
        if not ebs_throughput_field:
            for col in df.columns:
                if col.startswith('accounts_') and col.endswith('_throughput_mibs'):
                    ebs_throughput_field = col
                    break
        
        ebs_queue_field = None
        # 首先查找DATA设备字段
        for col in df.columns:
            if col.startswith('data_') and col.endswith('_aqu_sz'):
                ebs_queue_field = col
                break
        # 如果没有DATA设备字段，查找ACCOUNTS设备字段（可选）
        if not ebs_queue_field:
            for col in df.columns:
                if col.startswith('accounts_') and col.endswith('_aqu_sz'):
                    ebs_queue_field = col
                    break
        
        # 添加找到的字段
        if ebs_util_field:
            base_metrics.append(ebs_util_field)
            logger.info(f"✅ 动态发现EBS利用率字段: {ebs_util_field}")
        
        if ebs_latency_field:
            base_metrics.append(ebs_latency_field)
            logger.info(f"✅ 动态发现EBS延迟字段: {ebs_latency_field}")
        
        if ebs_iops_field:
            base_metrics.append(ebs_iops_field)
            logger.info(f"✅ 动态发现EBS IOPS字段: {ebs_iops_field}")
        
        if ebs_throughput_field:
            base_metrics.append(ebs_throughput_field)
            logger.info(f"✅ 动态发现EBS吞吐量字段: {ebs_throughput_field}")
        
        if ebs_queue_field:
            base_metrics.append(ebs_queue_field)
            logger.info(f"✅ 动态发现EBS队列深度字段: {ebs_queue_field}")
        
        if not any([ebs_util_field, ebs_latency_field, ebs_iops_field]):
            logger.warning("⚠️ 未发现EBS相关字段，可能影响瓶颈分析准确性")
        
        logger.info(f"📊 动态指标字段总数: {len(base_metrics)}")
        return base_metrics
    


    def analyze_performance_cliff(self, df: pd.DataFrame, max_qps: int, bottleneck_qps: int) -> Dict[str, Any]:
        """分析性能悬崖 - 识别性能急剧下降的点"""
        try:
            cliff_analysis = {
                'max_qps': max_qps,
                'bottleneck_qps': bottleneck_qps,
                'performance_drop_percent': 0.0,  # 使用float类型保持一致性
                'cliff_detected': False,
                'cliff_factors': [],
                'recommendations': []
            }
            
            if max_qps > 0 and bottleneck_qps > 0:
                # 计算性能下降百分比
                drop_percent = ((bottleneck_qps - max_qps) / max_qps) * 100
                cliff_analysis['performance_drop_percent'] = drop_percent
                
                # 判断是否为性能悬崖（下降超过20%）
                if abs(drop_percent) > 20:
                    cliff_analysis['cliff_detected'] = True
                    
                    # 分析悬崖因子
                    cliff_factors = self._identify_cliff_factors(df, max_qps, bottleneck_qps)
                    cliff_analysis['cliff_factors'] = cliff_factors
                    
                    # 生成建议
                    recommendations = self._generate_cliff_recommendations(cliff_factors, drop_percent)
                    cliff_analysis['recommendations'] = recommendations
                    
                    logger.info(f"🚨 检测到性能悬崖: {drop_percent:.1f}% 性能下降")
                else:
                    logger.info(f"📊 性能变化: {drop_percent:.1f}% (未达到悬崖阈值)")
            
            return cliff_analysis
            
        except Exception as e:
            logger.error(f"❌ 性能悬崖分析失败: {e}")
            return {}

    def _identify_cliff_factors(self, df: pd.DataFrame, max_qps: int, bottleneck_qps: int) -> list:
        """识别导致性能悬崖的因子"""
        cliff_factors = []
        
        try:
            # 寻找QPS列
            qps_column = None
            for col in ['current_qps', 'qps', 'requests_per_second']:
                if col in df.columns:
                    qps_column = col
                    break
            
            if not qps_column:
                return cliff_factors
            
            # 找到最大QPS和瓶颈QPS对应的数据点
            max_qps_data = df[df[qps_column] <= max_qps].tail(1)
            bottleneck_qps_data = df[df[qps_column] >= bottleneck_qps].head(1)
            
            if len(max_qps_data) == 0 or len(bottleneck_qps_data) == 0:
                return cliff_factors
            
            # 比较关键指标的变化 - 使用动态字段查找替代硬编码
            key_metrics = self._get_dynamic_key_metrics(df)
            
            for metric in key_metrics:
                if metric in df.columns:
                    try:
                        max_value = max_qps_data[metric].iloc[0]
                        bottleneck_value = bottleneck_qps_data[metric].iloc[0]
                        
                        if pd.notna(max_value) and pd.notna(bottleneck_value) and max_value != 0:
                            change_percent = ((bottleneck_value - max_value) / max_value) * 100
                            
                            # 如果变化超过10%，认为是悬崖因子
                            if abs(change_percent) > 10:
                                cliff_factors.append({
                                    'metric': metric,
                                    'max_qps_value': float(max_value),
                                    'bottleneck_value': float(bottleneck_value),
                                    'change_percent': float(change_percent),
                                    'impact': 'high' if abs(change_percent) > 50 else 'medium'
                                })
                    except Exception as e:
                        logger.warning(f"⚠️ 分析{metric}悬崖因子失败: {e}")
            
            # 按影响程度排序
            cliff_factors.sort(key=lambda x: abs(x['change_percent']), reverse=True)
            
        except Exception as e:
            logger.error(f"❌ 悬崖因子识别失败: {e}")
        
        return cliff_factors

    def _generate_cliff_recommendations(self, cliff_factors: list, drop_percent: float) -> list:
        """基于悬崖因子生成优化建议"""
        recommendations = []
        
        try:
            # 基于性能下降程度的通用建议
            if abs(drop_percent) > 50:
                recommendations.append("严重性能悬崖：建议立即停止测试并检查系统状态")
                recommendations.append("考虑降低测试强度或优化系统配置")
            elif abs(drop_percent) > 30:
                recommendations.append("显著性能下降：建议分析系统瓶颈并进行优化")
            
            # 基于具体悬崖因子的建议
            for factor in cliff_factors[:3]:  # 只处理前3个最重要的因子
                metric = factor['metric']
                change = factor['change_percent']
                
                if 'cpu' in metric.lower():
                    if change > 0:
                        recommendations.append(f"CPU使用率急剧上升{change:.1f}%：考虑升级CPU或优化应用")
                    else:
                        recommendations.append(f"CPU使用率异常下降{abs(change):.1f}%：检查CPU调度问题")
                
                elif 'mem' in metric.lower():
                    if change > 0:
                        recommendations.append(f"内存使用率急剧上升{change:.1f}%：考虑增加内存或优化内存使用")
                    else:
                        recommendations.append(f"内存使用率异常下降{abs(change):.1f}%：检查内存管理问题")
                
                elif 'util' in metric.lower():
                    if change > 0:
                        recommendations.append(f"磁盘利用率急剧上升{change:.1f}%：考虑升级存储或优化I/O")
                
                elif 'await' in metric.lower():
                    if change > 0:
                        recommendations.append(f"磁盘延迟急剧上升{change:.1f}%：检查存储性能瓶颈")
            
            # 如果没有明显的悬崖因子，提供通用建议
            if not cliff_factors:
                recommendations.append("未发现明显的性能悬崖因子，建议进行全面的系统性能分析")
                recommendations.append("检查网络、应用逻辑和系统配置")
        
        except Exception as e:
            logger.error(f"❌ 生成悬崖建议失败: {e}")
        
        return recommendations

    def generate_cliff_analysis_chart(self, df: pd.DataFrame, cliff_analysis: Dict[str, Any]) -> Optional[plt.Figure]:
        """生成性能悬崖分析图表"""
        try:
            if not cliff_analysis or not cliff_analysis.get('cliff_detected'):
                return None
            
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            # Using English title directly
            fig.suptitle('📉 Performance Cliff Analysis', fontsize=16, fontweight='bold', color='red')
            
            # 1. QPS性能曲线
            qps_column = None
            for col in ['current_qps', 'qps', 'requests_per_second']:
                if col in df.columns:
                    qps_column = col
                    break
            
            if qps_column and len(df) > 0:
                axes[0, 0].plot(df.index, df[qps_column], 'b-', alpha=0.7, linewidth=2)
                
                # 标记最大QPS和瓶颈QPS
                max_qps = cliff_analysis['max_qps']
                bottleneck_qps = cliff_analysis['bottleneck_qps']
                
                axes[0, 0].axhline(y=max_qps, color='green', linestyle='--', linewidth=2,
                                 label=f'Max QPS: {max_qps}')
                axes[0, 0].axhline(y=bottleneck_qps, color='red', linestyle='--', linewidth=2,
                                 label=f'Bottleneck QPS: {bottleneck_qps}')
                
                # 填充悬崖区域
                axes[0, 0].fill_between(df.index, max_qps, bottleneck_qps, 
                                      alpha=0.3, color='red', label='Performance Cliff')
                
                axes[0, 0].set_title('QPS Performance Cliff')
                axes[0, 0].set_xlabel('Time')
                axes[0, 0].set_ylabel('QPS')
                axes[0, 0].legend()
                axes[0, 0].grid(True, alpha=0.3)
            
            # 2. 悬崖因子影响
            cliff_factors = cliff_analysis.get('cliff_factors', [])
            if cliff_factors:
                factor_names = [f['metric'] for f in cliff_factors[:5]]
                factor_changes = [abs(f['change_percent']) for f in cliff_factors[:5]]
                
                colors = ['red' if abs(f['change_percent']) > 50 else 'orange' 
                         for f in cliff_factors[:5]]
                
                axes[0, 1].barh(factor_names, factor_changes, color=colors, alpha=0.7)
                axes[0, 1].set_title('Cliff Factor Impact (%)')
                axes[0, 1].set_xlabel('Change Percentage')
                axes[0, 1].grid(True, alpha=0.3)
            
            # 3. 性能下降可视化
            drop_percent = cliff_analysis.get('performance_drop_percent', 0)
            categories = ['Before Cliff', 'After Cliff']
            values = [100, 100 + drop_percent]  # 相对性能
            colors = ['green', 'red']
            
            bars = axes[1, 0].bar(categories, values, color=colors, alpha=0.7)
            axes[1, 0].set_title(f'Performance Drop: {abs(drop_percent):.1f}%')
            axes[1, 0].set_ylabel('Relative Performance (%)')
            axes[1, 0].axhline(y=100, color='black', linestyle='-', alpha=0.3)
            
            # 添加数值标签
            for bar, value in zip(bars, values):
                axes[1, 0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                               f'{value:.1f}%', ha='center', va='bottom', fontweight='bold')
            
            # 4. 建议摘要
            recommendations = cliff_analysis.get('recommendations', [])
            if recommendations:
                axes[1, 1].text(0.05, 0.95, 'Optimization Recommendations:', 
                               transform=axes[1, 1].transAxes, fontsize=12, fontweight='bold',
                               verticalalignment='top')
                
                for i, rec in enumerate(recommendations[:5]):
                    axes[1, 1].text(0.05, 0.85 - i*0.15, f"• {rec}", 
                                   transform=axes[1, 1].transAxes, fontsize=10,
                                   verticalalignment='top', wrap=True)
                
                axes[1, 1].set_xlim(0, 1)
                axes[1, 1].set_ylim(0, 1)
                axes[1, 1].axis('off')
            
            plt.tight_layout()
            
            # 保存图表
            chart_path = os.path.join(self.reports_dir, 'performance_cliff_analysis.png')
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            logger.info(f"📊 性能悬崖分析图表已保存: {chart_path}")
            
            return fig
            
        except Exception as e:
            logger.error(f"❌ 性能悬崖图表生成失败: {e}")
            return None

    def get_latest_csv(self) -> Optional[str]:
        """改进的CSV文件查找逻辑，支持多种路径模式"""
        csv_patterns = [
            f"{self.output_dir}/logs/performance_latest.csv",
            f"{self.output_dir}/logs/performance_*.csv",
            f"{self.output_dir}/current/logs/performance_latest.csv",
            f"{self.output_dir}/current/logs/performance_*.csv"
        ]
        
        for pattern in csv_patterns:
            csv_files = glob.glob(pattern)
            if csv_files:
                return max(csv_files, key=os.path.getctime)
        return None

    def load_and_clean_data(self) -> pd.DataFrame:
        """加载和清理监控数据，改进错误处理"""
        try:
            if not self.csv_file:
                print("⚠️  No CSV monitoring file found, proceeding with log analysis only")
                return pd.DataFrame()

            print(f"📊 Loading QPS monitoring data from: {os.path.basename(self.csv_file)}")
            
            # 直接使用pandas读取CSV - 字段映射器已移除
            df = pd.read_csv(self.csv_file)

            print(f"📋 Raw data shape: {df.shape}")

            # 检查是否有QPS相关数据
            qps_columns = ['current_qps', 'qps', 'target_qps']
            qps_column = None
            for col in qps_columns:
                if col in df.columns:
                    qps_column = col
                    break
            
            if qps_column is None:
                print("⚠️  No QPS data found in CSV, this appears to be system monitoring data only")
                print("📊 Available columns:", ', '.join(df.columns[:10]))
                # 仍然返回数据，用于系统性能分析
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
                return df

            # 处理current_qps列
            df['current_qps'] = df[qps_column].astype(str)
            numeric_mask = df['current_qps'].str.isdigit()
            numeric_df = df[numeric_mask].copy()

            if len(numeric_df) == 0:
                print("⚠️  No numeric QPS data found")
                return df

            # 数据类型转换
            numeric_df['current_qps'] = pd.to_numeric(numeric_df['current_qps'])
            numeric_df['timestamp'] = pd.to_datetime(numeric_df['timestamp'], errors='coerce')

            # 清理数值列 - 使用映射后的标准字段名
            numeric_cols = ['cpu_usage', 'mem_usage', 'rpc_latency_ms', 'elapsed_time', 'remaining_time']
            for col in numeric_cols:
                if col in numeric_df.columns:
                    numeric_df[col] = pd.to_numeric(numeric_df[col], errors='coerce')

            print(f"📊 Processed {len(numeric_df)} QPS monitoring data points")
            return numeric_df
            
        except Exception as e:
            logger.error(f"❌ Data loading and cleaning failed: {e}")
            return pd.DataFrame()

    def analyze_performance_metrics(self, df: pd.DataFrame) -> Tuple[Optional[pd.DataFrame], int]:
        """分析关键性能指标"""
        print("\n🎯 QPS Performance Metrics Analysis")
        print("=" * 50)

        if 'current_qps' not in df.columns or len(df) == 0:
            print("❌ No valid QPS data for analysis")
            return None, 0

        max_qps = df['current_qps'].max()
        qps_range = sorted(df['current_qps'].unique())

        print(f"Maximum QPS tested: {max_qps:,}")
        print(f"QPS range: {min(qps_range):,} - {max_qps:,}")
        print(f"Number of QPS levels: {len(qps_range)}")

        # 按QPS分组统计
        qps_stats = df.groupby('current_qps').agg({
            'cpu_usage': ['mean', 'max'],
            'mem_usage': ['mean', 'max'],
            'rpc_latency_ms': ['mean', 'max']
        }).round(2)

        print("\nQPS Performance Statistics:")
        print(qps_stats.to_string())

        return qps_stats, max_qps

    def identify_bottlenecks(self, df: pd.DataFrame) -> Dict[str, Any]:
        """识别性能瓶颈"""
        print("\n🔍 QPS Performance Bottleneck Analysis")
        print("=" * 50)

        if len(df) == 0:
            print("❌ No data for bottleneck analysis")
            return {}

        bottlenecks = {}

        # CPU瓶颈
        if 'cpu_usage' in df.columns and 'current_qps' in df.columns:
            cpu_bottleneck = df[df['cpu_usage'] > self.cpu_threshold]['current_qps'].min()
            if pd.notna(cpu_bottleneck):
                bottlenecks['CPU'] = cpu_bottleneck

        # 内存瓶颈
        mem_bottleneck = df[df['mem_usage'] > self.memory_threshold]['current_qps'].min()
        if pd.notna(mem_bottleneck):
            bottlenecks['Memory'] = mem_bottleneck

        # RPC延迟瓶颈
        rpc_bottleneck = df[df['rpc_latency_ms'] > self.rpc_threshold]['current_qps'].min()
        if pd.notna(rpc_bottleneck):
            bottlenecks['RPC_Latency'] = rpc_bottleneck

        if bottlenecks:
            print("System bottlenecks detected:")
            for bottleneck_type, qps in bottlenecks.items():
                print(f"  {bottleneck_type}: First occurs at QPS {qps:,}")
        else:
            print("✅ No critical system bottlenecks detected in tested range")

        return bottlenecks

    def generate_performance_charts(self, df: pd.DataFrame) -> Optional[plt.Figure]:
        """生成性能图表"""
        print("\n📈 Generating performance charts...")

        if len(df) == 0:
            print("❌ No QPS data for chart generation")
            return None

        plt.style.use('default')
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        # Using English title directly
        fig.suptitle('Solana QPS Performance Analysis Dashboard', fontsize=16, fontweight='bold')

        # 1. CPU使用率 vs QPS
        if len(df) > 0:
            axes[0, 0].plot(df['current_qps'], df['cpu_usage'], 'bo-', alpha=0.7, markersize=4)
            axes[0, 0].axhline(y=85, color='red', linestyle='--', alpha=0.8, label='Warning (85%)')
            axes[0, 0].set_title('CPU Usage vs QPS')
            axes[0, 0].set_xlabel('QPS')
            axes[0, 0].set_ylabel('CPU %')
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)

        # 2. 内存使用率 vs QPS
        if len(df) > 0:
            axes[0, 1].plot(df['current_qps'], df['mem_usage'], 'go-', alpha=0.7, markersize=4)
            axes[0, 1].axhline(y=90, color='red', linestyle='--', alpha=0.8, label='Warning (90%)')
            axes[0, 1].set_title('Memory Usage vs QPS')
            axes[0, 1].set_xlabel('QPS')
            axes[0, 1].set_ylabel('Memory %')
            axes[0, 1].legend()
            axes[0, 1].grid(True, alpha=0.3)

        # 3. RPC延迟 vs QPS
        if len(df) > 0:
            axes[1, 0].plot(df['current_qps'], df['rpc_latency_ms'], 'ro-', alpha=0.7, markersize=4)
            axes[1, 0].axhline(y=1000, color='orange', linestyle='--', alpha=0.8, label='High Latency (1s)')
            axes[1, 0].set_title('RPC Latency vs QPS')
            axes[1, 0].set_xlabel('QPS')
            axes[1, 0].set_ylabel('Latency (ms)')
            axes[1, 0].legend()
            axes[1, 0].grid(True, alpha=0.3)

        # 4. RPC延迟分布
        if len(df) > 0 and 'rpc_latency_ms' in df.columns:
            axes[1, 1].hist(df['rpc_latency_ms'], bins=30, alpha=0.7, color='purple')
            if 'rpc_latency_ms' in df.columns:
                mean_latency = df['rpc_latency_ms'].mean()
                p95_latency = df['rpc_latency_ms'].quantile(0.95)
                axes[1, 1].axvline(mean_latency, color='red', linestyle='--',
                                   label=f'Mean: {mean_latency:.1f}ms')
                axes[1, 1].axvline(p95_latency, color='orange', linestyle='--',
                                   label=f'P95: {p95_latency:.1f}ms')
            axes[1, 1].set_title('RPC Latency Distribution')
            axes[1, 1].set_xlabel('Latency (ms)')
            axes[1, 1].set_ylabel('Frequency')
            axes[1, 1].legend()
            axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()
        
        # 保存图表
        chart_file = os.path.join(self.output_dir, 'reports', 'qps_performance_analysis.png')
        os.makedirs(os.path.dirname(chart_file), exist_ok=True)
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        print(f"✅ Performance charts saved: {chart_file}")

        return fig

    def analyze_vegeta_reports(self) -> Optional[pd.DataFrame]:
        """分析Vegeta测试报告"""
        print("\n📋 Vegeta Reports Analysis")
        print("=" * 50)

        reports = glob.glob(f"{self.output_dir}/reports/*.txt")
        if not reports:
            print("No Vegeta reports found")
            return None

        report_data = []
        for report_file in sorted(reports):
            try:
                qps = int(os.path.basename(report_file).split('_')[1])
                with open(report_file, 'r') as f:
                    content = f.read()

                success_rate = 0
                avg_latency = 'N/A'
                p99_latency = 'N/A'

                for line in content.split('\n'):
                    if 'Success' in line and '[ratio]' in line:
                        success_rate = float(line.split()[-1].replace('%', ''))
                    elif 'Latencies' in line and '[min, mean,' in line:
                        parts = line.split()
                        if len(parts) >= 8:
                            avg_latency = parts[6].replace(',', '')
                            p99_latency = parts[8].replace(',', '')

                report_data.append({
                    'QPS': qps,
                    'Success_Rate': success_rate,
                    'Avg_Latency': avg_latency,
                    'P99_Latency': p99_latency
                })
            except Exception as e:
                print(f"Warning: Could not parse {report_file}: {e}")

        if report_data:
            vegeta_df = pd.DataFrame(report_data)
            print(vegeta_df.to_string(index=False))
            return vegeta_df

        return None

    def _evaluate_performance_by_bottleneck_analysis(self, benchmark_mode: str, max_qps: int, 
                                                   bottlenecks: Dict[str, Any], avg_cpu: float, 
                                                   avg_mem: float, avg_rpc: float) -> Dict[str, Any]:
        """
        基于瓶颈分析的科学性能评估
        替代硬编码的60000/40000/20000逻辑
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
        
        # 深度基准测试模式下的瓶颈分析评估
        bottleneck_types = bottlenecks.get('detected_bottlenecks', [])
        bottleneck_count = len(bottleneck_types)
        
        # 计算瓶颈严重程度评分
        bottleneck_score = self._calculate_bottleneck_severity_score(
            bottleneck_types, avg_cpu, avg_mem, avg_rpc
        )
        
        # 基于瓶颈评分的科学等级评估
        if bottleneck_score < 0.2:
            # 低瓶颈评分 = 优秀性能
            level = "优秀"
            grade = "A (Excellent)"
            reason = f"系统在{max_qps} QPS下未出现明显瓶颈，性能表现优秀"
            
        elif bottleneck_score < 0.4:
            # 中等瓶颈评分 = 良好性能
            level = "良好"
            grade = "B (Good)"
            reason = f"系统在{max_qps} QPS下出现轻微瓶颈: {', '.join(bottleneck_types)}"
            
        elif bottleneck_score < 0.7:
            # 较高瓶颈评分 = 一般性能
            level = "一般"
            grade = "C (Acceptable)"
            reason = f"系统在{max_qps} QPS下出现明显瓶颈: {', '.join(bottleneck_types)}"
            
        else:
            # 高瓶颈评分 = 需要优化
            level = "需要优化"
            grade = "D (Needs Improvement)"
            reason = f"系统在{max_qps} QPS下出现严重瓶颈: {', '.join(bottleneck_types)}"
        
        return {
            'performance_level': level,
            'performance_grade': grade,
            'evaluation_reason': reason,
            'evaluation_basis': 'intensive_bottleneck_analysis',
            'max_sustainable_qps': max_qps,
            'bottleneck_score': bottleneck_score,
            'bottleneck_types': bottleneck_types,
            'bottleneck_count': bottleneck_count,
            'recommendations': self._generate_bottleneck_based_recommendations(
                bottleneck_types, bottleneck_score, max_qps
            )
        }
    
    def _calculate_bottleneck_severity_score(self, bottleneck_types: list, 
                                           avg_cpu: float, avg_mem: float, avg_rpc: float) -> float:
        """计算瓶颈严重程度评分"""
        
        # 瓶颈类型权重
        bottleneck_weights = {
            'CPU': 0.2,
            'Memory': 0.25,
            'EBS': 0.3,
            'Network': 0.15,
            'RPC': 0.1
        }
        
        total_score = 0.0
        
        # 基于检测到的瓶颈类型计算评分
        for bottleneck_type in bottleneck_types:
            weight = bottleneck_weights.get(bottleneck_type, 0.1)
            
            # 根据具体指标调整严重程度
            severity_multiplier = 1.0
            if bottleneck_type == 'CPU' and avg_cpu > (self.cpu_threshold + 5):
                severity_multiplier = 1.5
            elif bottleneck_type == 'Memory' and avg_mem > (self.memory_threshold + 5):
                severity_multiplier = 1.5
            elif bottleneck_type == 'RPC' and avg_rpc > (self.rpc_threshold * 2):
                severity_multiplier = 1.5
            
            total_score += weight * severity_multiplier
        
        # 归一化评分到0-1范围
        return min(total_score, 1.0)
    
    def _generate_capacity_assessment(self, performance_evaluation: Dict[str, Any], max_qps: int) -> str:
        """基于性能评估生成容量评估"""
        performance_level = performance_evaluation.get('performance_level', '未知')
        bottleneck_score = performance_evaluation.get('bottleneck_score', 0)
        
        if performance_level == "优秀":
            return f"当前配置可稳定处理高负载 (已测试至 {max_qps:,} QPS，无明显瓶颈)"
        elif performance_level == "良好":
            return f"当前配置可处理中高负载 (已测试至 {max_qps:,} QPS，轻微瓶颈)"
        elif performance_level == "一般":
            return f"当前配置适合中等负载 (已测试至 {max_qps:,} QPS，存在瓶颈)"
        elif performance_level == "需要优化":
            return f"当前配置需要优化以处理高负载 (已测试至 {max_qps:,} QPS，严重瓶颈)"
        else:
            return f"需要intensive基准测试模式进行准确的容量评估"

    def _generate_bottleneck_based_recommendations(self, bottleneck_types: list, 
                                                 bottleneck_score: float, max_qps: int) -> list:
        """基于瓶颈分析生成优化建议"""
        recommendations = []
        
        if bottleneck_score < 0.2:
            recommendations.extend([
                f"🎉 系统性能优秀，当前配置可稳定支持 {max_qps} QPS",
                "💡 可考虑进一步提升QPS目标或优化成本效率",
                "📊 建议定期监控以维持当前性能水平"
            ])
        else:
            # 基于具体瓶颈类型的针对性建议
            if 'CPU' in bottleneck_types:
                recommendations.append("🔧 CPU瓶颈：考虑升级CPU或优化计算密集型进程")
            if 'Memory' in bottleneck_types:
                recommendations.append("🔧 内存瓶颈：考虑增加内存或优化内存使用")
            if 'EBS' in bottleneck_types:
                recommendations.append("🔧 存储瓶颈：考虑升级EBS类型或优化I/O模式")
            if 'Network' in bottleneck_types:
                recommendations.append("🔧 网络瓶颈：考虑升级网络带宽或优化网络配置")
            if 'RPC' in bottleneck_types:
                recommendations.append("🔧 RPC瓶颈：考虑优化RPC配置或增加RPC连接池")
        
        return recommendations

    def generate_performance_report(self, df: pd.DataFrame, max_qps: int, 
                                  bottlenecks: Dict[str, Any], benchmark_mode: str = "standard") -> str:
        """生成基于瓶颈分析的性能报告"""
        print("\n📄 Generating performance report...")

        # 基本性能指标
        avg_cpu = df['cpu_usage'].mean() if len(df) > 0 and 'cpu_usage' in df.columns else 0
        avg_mem = df['mem_usage'].mean() if len(df) > 0 and 'mem_usage' in df.columns else 0
        avg_rpc = df['rpc_latency_ms'].mean() if len(df) > 0 and 'rpc_latency_ms' in df.columns else 0

        # 基于基准测试模式和瓶颈分析的性能评估
        performance_evaluation = self._evaluate_performance_by_bottleneck_analysis(
            benchmark_mode, max_qps, bottlenecks, avg_cpu, avg_mem, avg_rpc
        )

        report = f"""# Solana QPS Performance Analysis Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
- **Maximum QPS Achieved**: {max_qps:,}
- **Performance Grade**: {performance_evaluation['performance_grade']}
- **Performance Level**: {performance_evaluation['performance_level']}
- **Benchmark Mode**: {benchmark_mode}
- **Test Duration**: {len(df)} monitoring points

## Performance Evaluation
- **Evaluation Basis**: {performance_evaluation['evaluation_basis']}
- **Evaluation Reason**: {performance_evaluation['evaluation_reason']}

## System Performance Metrics
- **Average CPU Usage**: {avg_cpu:.1f}%
- **Average Memory Usage**: {avg_mem:.1f}%
- **Average RPC Latency**: {avg_rpc:.1f}ms
- **CPU Peak**: {(df['cpu_usage'].max() if len(df) > 0 and 'cpu_usage' in df.columns else 0):.1f}%
- **Memory Peak**: {(df['mem_usage'].max() if len(df) > 0 and 'mem_usage' in df.columns else 0):.1f}%
- **RPC Latency Peak**: {(df['rpc_latency_ms'].max() if len(df) > 0 and 'rpc_latency_ms' in df.columns else 0):.1f}ms

## Performance Bottlenecks Analysis
"""

        if performance_evaluation.get('bottleneck_types'):
            report += f"- **Bottleneck Score**: {performance_evaluation.get('bottleneck_score', 0):.3f}\n"
            report += f"- **Detected Bottlenecks**: {', '.join(performance_evaluation['bottleneck_types'])}\n"
            for bottleneck_type in performance_evaluation['bottleneck_types']:
                qps = bottlenecks.get(bottleneck_type, 'Unknown')
                report += f"  - **{bottleneck_type}**: First detected at {qps:,} QPS\n" if isinstance(qps, int) else f"  - **{bottleneck_type}**: {qps}\n"
        else:
            report += "- ✅ No critical bottlenecks detected in tested range\n"

        report += f"""
## Optimization Recommendations

### Based on Bottleneck Analysis
"""

        # 使用基于瓶颈分析的建议
        for recommendation in performance_evaluation.get('recommendations', []):
            report += f"- {recommendation}\n"

        report += f"""
### Production Deployment Guidelines
- **Recommended Production QPS**: {int(max_qps * 0.8):,} (80% of maximum tested)
- **Monitoring Thresholds**: 
  - Alert if CPU usage > 85%
  - Alert if Memory usage > 90%
  - Alert if RPC latency > 1000ms sustained
- **Capacity Assessment**: {self._generate_capacity_assessment(performance_evaluation, max_qps)}

## Files Generated
- **Performance Charts**: `{self.output_dir}/reports/qps_performance_analysis.png`
- **Raw QPS Monitoring Data**: `{self.csv_file or 'N/A'}`
- **Vegeta Test Reports**: `{self.output_dir}/reports/`

---
*Report generated by Solana QPS Analyzer*
"""

        # 保存报告
        report_file = os.path.join(self.output_dir, 'reports', 'qps_performance_report.md')
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        with open(report_file, 'w') as f:
            f.write(report)

        print(f"✅ Performance report saved: {report_file}")
        return report

    def run_qps_analysis(self) -> Dict[str, Any]:
        """运行完整的QPS分析"""
        print("🚀 Starting Solana QPS Performance Analysis")
        print("=" * 60)

        # 加载QPS监控数据
        df = self.load_and_clean_data()

        # 执行QPS性能分析
        qps_stats, max_qps = self.analyze_performance_metrics(df)
        bottlenecks = self.identify_bottlenecks(df)

        # 生成图表和报告
        self.generate_performance_charts(df)
        vegeta_analysis = self.analyze_vegeta_reports()
        report = self.generate_performance_report(df, max_qps, bottlenecks, self.benchmark_mode)

        analysis_results = {
            'dataframe': df,
            'qps_stats': qps_stats,
            'max_qps': max_qps,
            'bottlenecks': bottlenecks,
            'vegeta_analysis': vegeta_analysis,
            'report': report
        }

        print("\n🎉 QPS Analysis Completed Successfully!")
        print("Generated files:")
        print(f"  📊 Charts: {self.output_dir}/reports/qps_performance_analysis.png")
        print(f"  📄 Report: {self.output_dir}/reports/qps_performance_report.md")

        return analysis_results


def main():
    """主执行函数 - 支持瓶颈模式和性能悬崖分析"""
    parser = argparse.ArgumentParser(description='QPS分析器 - 支持瓶颈模式')
    parser.add_argument('csv_file', help='CSV数据文件路径')
    parser.add_argument('--benchmark-mode', default='standard', choices=['quick', 'standard', 'intensive'], 
                       help='基准测试模式 (默认: standard)')
    parser.add_argument('--bottleneck-mode', action='store_true', help='启用瓶颈分析模式')
    parser.add_argument('--cliff-analysis', action='store_true', help='启用性能悬崖分析')
    parser.add_argument('--max-qps', type=int, help='最大成功QPS')
    parser.add_argument('--bottleneck-qps', type=int, help='瓶颈触发QPS')
    parser.add_argument('--output-dir', help='输出目录路径')
    
    args = parser.parse_args()
    
    try:
        if not os.path.exists(args.csv_file):
            logger.error(f"❌ CSV文件不存在: {args.csv_file}")
            return 1
        
        # 初始化分析器
        analyzer = NodeQPSAnalyzer(args.output_dir, args.benchmark_mode, args.bottleneck_mode)
        
        # 读取数据
        df = pd.read_csv(args.csv_file)
        logger.info(f"📊 数据加载完成: {len(df)} 条记录")
        
        # 性能悬崖分析
        if args.cliff_analysis and args.max_qps and args.bottleneck_qps:
            logger.info("📉 执行性能悬崖分析")
            cliff_analysis = analyzer.analyze_performance_cliff(df, args.max_qps, args.bottleneck_qps)
            
            # 生成悬崖分析图表
            cliff_chart = analyzer.generate_cliff_analysis_chart(df, cliff_analysis)
            
            # 保存分析结果
            cliff_result_file = os.path.join(analyzer.reports_dir, 'performance_cliff_analysis.json')
            with open(cliff_result_file, 'w') as f:
                json.dump(cliff_analysis, f, indent=2, default=str)
            logger.info(f"📊 性能悬崖分析结果已保存: {cliff_result_file}")
        
        # 执行标准QPS分析
        result = analyzer.run_qps_analysis()
        
        if result:
            logger.info("✅ QPS分析完成")
            return 0
        else:
            logger.error("❌ QPS分析失败")
            return 1
            
    except Exception as e:
        logger.error(f"❌ QPS分析执行失败: {e}")
        return 1

# 使用示例
if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("📋 QPS分析器使用示例:")
        print("python qps_analyzer.py data.csv")
        print("python qps_analyzer.py data.csv --bottleneck-mode")
        print("python qps_analyzer.py data.csv --cliff-analysis --max-qps 5000 --bottleneck-qps 3000")
    else:
        sys.exit(main())
    print("analyzer = NodeQPSAnalyzer('/path/to/output/dir', 'standard', False)")
    print("results = analyzer.run_qps_analysis()")
    
    # 演示功能
    try:
        analyzer = NodeQPSAnalyzer(benchmark_mode="standard", bottleneck_mode=False)
        results = analyzer.run_qps_analysis()
        if results:
            print("🎯 QPS分析器演示完成")
            print(f"📊 生成了 {len(results)} 个分析组件")
            print(f"📈 最大QPS: {results.get('max_qps', 'N/A')}")
        else:
            print("⚠️ 分析未产生结果")
    except Exception as e:
        print(f"⚠️  演示运行失败: {e}")
        print("这是正常的，因为可能没有实际的测试数据")
