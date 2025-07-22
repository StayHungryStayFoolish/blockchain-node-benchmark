#!/usr/bin/env python3
"""
验证器日志分析器 - 从comprehensive_analysis.py拆分出来的独立模块
专门负责Solana验证器日志的分析，包括RPC性能、错误模式、瓶颈检测等
"""

import sys
import os

# 添加项目根目录到Python路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

import pandas as pd
import numpy as np
import re
import subprocess
from utils.unified_logger import get_logger
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, Any, List, Optional

# 配置日志
logger = get_logger(__name__)


class ValidatorLogAnalyzer:
    """Solana验证器日志分析器"""

    def __init__(self, log_file: Optional[str] = None, 
                 test_start_time: Optional[datetime] = None, 
                 test_end_time: Optional[datetime] = None):
        """
        初始化验证器日志分析器
        
        Args:
            log_file: 验证器日志文件路径（如果为None，将从配置管理器获取）
            test_start_time: 测试开始时间
            test_end_time: 测试结束时间
        """
        # 智能获取日志文件路径
        if log_file is None:
            log_file = os.environ.get('VALIDATOR_LOG_PATH', 
                                    os.path.join(os.environ.get('DATA_DIR', '/tmp'), 'log', 'validator.log'))
        
        self.log_file = log_file
        self.test_start_time = test_start_time
        self.test_end_time = test_end_time
        
        # RPC模式匹配规则
        self.rpc_patterns = {
            'rpc_errors': r'rpc.*(?:error|timeout|failed|rejected)',
            'rpc_busy': r'rpc.*(?:busy|overload|queue.*full)',
            'compute_unit': r'compute.*unit.*(?:limit|exceeded|usage)',
            'memory_pressure': r'(?:memory.*pressure|out.*of.*memory|allocation.*failed)',
            'block_processing': r'processing.*block.*took.*([0-9]+)ms',
            'gossip_issues': r'gossip.*(?:error|timeout|slow|failed)',
            'rpc_methods': r'rpc.*(?:getAccountInfo|getProgramAccounts|sendTransaction|getBalance)',
            'io_issues': r'(?:disk.*slow|io.*timeout|storage.*error)',
            'rpc_latency': r'rpc.*took.*([0-9]+)ms'
        }
        
        logger.info(f"🔍 初始化验证器日志分析器，日志文件: {log_file}")

    def analyze_validator_logs_during_test(self, qps_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        分析测试期间的验证器日志
        
        Args:
            qps_df: QPS测试数据DataFrame
            
        Returns:
            包含分析结果的字典
        """
        print("\n🔍 Validator Log Analysis During QPS Test")
        print("=" * 50)

        if not os.path.exists(self.log_file):
            print(f"❌ Validator log not found: {self.log_file}")
            return {}

        # 确定测试时间范围
        if qps_df is not None and len(qps_df) > 0:
            test_start = qps_df['timestamp'].min()
            test_end = qps_df['timestamp'].max()
            print(f"📅 Test period: {test_start} to {test_end}")
        else:
            # 使用最近2小时的日志窗口
            test_end = datetime.now()
            test_start = test_end - timedelta(hours=2)
            print(f"📅 Using recent 2-hour window: {test_start} to {test_end}")

        # 读取和过滤日志
        log_entries = self.read_log_entries_in_timerange(test_start, test_end)

        if not log_entries:
            print("⚠️  No log entries found in time range")
            return {}

        # 执行各项分析
        analysis_results = {
            'rpc_analysis': self.analyze_rpc_performance(log_entries),
            'bottleneck_analysis': self.detect_bottleneck_patterns(log_entries),
            'error_analysis': self.analyze_error_patterns(log_entries),
            'resource_analysis': self.analyze_resource_issues(log_entries),
            'correlation_analysis': self.correlate_logs_with_qps(log_entries, qps_df),
            'performance_timeline': self.analyze_performance_timeline(log_entries),
            'summary_stats': self.generate_summary_statistics(log_entries)
        }

        return analysis_results

    def read_log_entries_in_timerange(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """读取指定时间范围内的日志条目"""
        log_entries = []

        try:
            # 使用subprocess获取日志以获得更好的性能
            cmd = ["tail", "-10000", self.log_file]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                print(f"⚠️  Warning: Failed to read log file: {result.stderr}")
                return []

            lines = result.stdout.split('\n')

            for line in lines:
                if not line.strip():
                    continue

                # 尝试解析时间戳
                timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
                if timestamp_match:
                    try:
                        log_time = datetime.fromisoformat(timestamp_match.group(1).replace('T', ' '))
                        if start_time <= log_time <= end_time:
                            log_entries.append({
                                'timestamp': log_time,
                                'content': line.strip()
                            })
                    except ValueError:
                        continue

        except subprocess.TimeoutExpired:
            print("⚠️  Timeout reading log file, using fallback method")
            # 备用方法
            try:
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()[-5000:]  # 读取最后5000行

                for line in lines:
                    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
                    if timestamp_match:
                        try:
                            log_time = datetime.fromisoformat(timestamp_match.group(1).replace('T', ' '))
                            if start_time <= log_time <= end_time:
                                log_entries.append({
                                    'timestamp': log_time,
                                    'content': line.strip()
                                })
                        except ValueError:
                            continue
            except Exception as e:
                print(f"⚠️  Error reading log file: {e}")
                return []

        print(f"📋 Analyzed {len(log_entries)} log entries")
        return log_entries

    def analyze_rpc_performance(self, log_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析RPC性能指标"""
        rpc_stats = {
            'total_rpc_requests': 0,
            'rpc_errors': 0,
            'rpc_busy_incidents': 0,
            'method_distribution': Counter(),
            'response_times': [],
            'error_types': Counter(),
            'success_rate': 0.0,  # 使用float类型保持一致性
            'avg_response_time': 0.0,  # 使用float类型保持一致性
            'p95_response_time': 0.0,  # 使用float类型保持一致性
            'p99_response_time': 0.0   # 使用float类型保持一致性
        }

        for entry in log_entries:
            content = entry['content'].lower()

            # RPC请求统计
            if 'rpc' in content:
                rpc_stats['total_rpc_requests'] += 1

                # 错误分类
                if re.search(self.rpc_patterns['rpc_errors'], content):
                    rpc_stats['rpc_errors'] += 1

                    if 'timeout' in content:
                        rpc_stats['error_types']['timeout'] += 1
                    elif 'failed' in content:
                        rpc_stats['error_types']['failed'] += 1
                    elif 'rejected' in content:
                        rpc_stats['error_types']['rejected'] += 1
                    elif 'error' in content:
                        rpc_stats['error_types']['error'] += 1

                # 繁忙状态
                if re.search(self.rpc_patterns['rpc_busy'], content):
                    rpc_stats['rpc_busy_incidents'] += 1

                # RPC方法分布
                for method in ['getaccountinfo', 'getprogramaccounts', 'sendtransaction', 'getbalance', 'getslot']:
                    if method in content:
                        rpc_stats['method_distribution'][method] += 1

                # 响应时间提取
                latency_match = re.search(self.rpc_patterns['rpc_latency'], content)
                if latency_match:
                    response_time = int(latency_match.group(1))
                    rpc_stats['response_times'].append(response_time)

        # 计算统计指标
        if rpc_stats['total_rpc_requests'] > 0:
            rpc_stats['success_rate'] = ((rpc_stats['total_rpc_requests'] - rpc_stats['rpc_errors'])
                                         / rpc_stats['total_rpc_requests'] * 100)

        if rpc_stats['response_times']:
            response_times = np.array(rpc_stats['response_times'])
            rpc_stats['avg_response_time'] = float(np.mean(response_times))
            rpc_stats['p95_response_time'] = float(np.percentile(response_times, 95))
            rpc_stats['p99_response_time'] = float(np.percentile(response_times, 99))

        return rpc_stats

    def detect_bottleneck_patterns(self, log_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """检测瓶颈模式"""
        bottlenecks = {
            'rpc_thread_saturation': 0,
            'compute_unit_limits': 0,
            'memory_pressure': 0,
            'io_bottlenecks': 0,
            'network_issues': 0,
            'critical_events': [],
            'bottleneck_timeline': []
        }

        for entry in log_entries:
            content = entry['content'].lower()
            timestamp = entry['timestamp']

            # RPC线程饱和
            if re.search(self.rpc_patterns['rpc_busy'], content):
                bottlenecks['rpc_thread_saturation'] += 1
                if bottlenecks['rpc_thread_saturation'] % 10 == 0:  # 每10次记录一次
                    bottlenecks['bottleneck_timeline'].append({
                        'timestamp': timestamp,
                        'type': 'RPC_Thread_Saturation',
                        'count': bottlenecks['rpc_thread_saturation']
                    })

            # 计算单元限制
            if re.search(self.rpc_patterns['compute_unit'], content):
                bottlenecks['compute_unit_limits'] += 1

            # 内存压力
            if re.search(self.rpc_patterns['memory_pressure'], content):
                bottlenecks['memory_pressure'] += 1
                bottlenecks['critical_events'].append({
                    'timestamp': timestamp,
                    'type': 'Memory_Pressure',
                    'severity': 'CRITICAL',
                    'content': content[:200]
                })

            # I/O瓶颈
            if re.search(self.rpc_patterns['io_issues'], content):
                bottlenecks['io_bottlenecks'] += 1

            # 网络问题
            if re.search(self.rpc_patterns['gossip_issues'], content):
                bottlenecks['network_issues'] += 1

        return bottlenecks

    def analyze_error_patterns(self, log_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析错误模式"""
        error_patterns = {
            'error_frequency_by_hour': defaultdict(int),
            'error_types': Counter(),
            'error_hotspots': [],
            'recovery_patterns': []
        }

        for entry in log_entries:
            content = entry['content'].lower()
            timestamp = entry['timestamp']
            hour_key = timestamp.strftime('%H:00')

            if any(keyword in content for keyword in ['error', 'failed', 'timeout', 'rejected']):
                error_patterns['error_frequency_by_hour'][hour_key] += 1

                # 错误类型分类
                if 'timeout' in content:
                    error_patterns['error_types']['timeout'] += 1
                elif 'connection' in content and 'failed' in content:
                    error_patterns['error_types']['connection_failed'] += 1
                elif 'memory' in content:
                    error_patterns['error_types']['memory_issue'] += 1
                elif 'rpc' in content:
                    error_patterns['error_types']['rpc_error'] += 1
                else:
                    error_patterns['error_types']['other'] += 1

        return error_patterns

    def analyze_resource_issues(self, log_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析系统资源问题"""
        resource_issues = {
            'memory_events': [],
            'cpu_events': [],
            'io_events': [],
            'resource_timeline': []
        }

        for entry in log_entries:
            content = entry['content'].lower()
            timestamp = entry['timestamp']

            # 内存相关事件
            if re.search(self.rpc_patterns['memory_pressure'], content):
                resource_issues['memory_events'].append({
                    'timestamp': timestamp,
                    'type': 'memory_pressure',
                    'content': content[:150]
                })

            # CPU相关事件
            if re.search(r'cpu.*(high|overload)|thread.*busy', content):
                resource_issues['cpu_events'].append({
                    'timestamp': timestamp,
                    'type': 'cpu_issue',
                    'content': content[:150]
                })

            # I/O相关事件
            if re.search(self.rpc_patterns['io_issues'], content):
                resource_issues['io_events'].append({
                    'timestamp': timestamp,
                    'type': 'io_issue',
                    'content': content[:150]
                })

        return resource_issues

    def correlate_logs_with_qps(self, log_entries: List[Dict[str, Any]], 
                               qps_df: Optional[pd.DataFrame]) -> Dict[str, Any]:
        """将日志事件与QPS数据关联"""
        if qps_df is None or len(qps_df) == 0:
            return {}

        correlation_results = {
            'high_qps_errors': [],
            'performance_degradation_points': [],
            'qps_error_correlation': 0.0,  # 使用float类型保持一致性
            'bottleneck_qps_thresholds': {}
        }

        # 创建时间窗口分析
        window_size = timedelta(minutes=1)  # 1分钟窗口

        for _, qps_row in qps_df.iterrows():
            try:
                qps_time = pd.to_datetime(qps_row['timestamp'])
                current_qps = qps_row['current_qps']

                # 在同一时间窗口内查找日志事件
                window_start = qps_time - window_size
                window_end = qps_time + window_size

                window_errors = 0
                window_rpc_busy = 0

                for entry in log_entries:
                    if window_start <= entry['timestamp'] <= window_end:
                        content = entry['content'].lower()
                        if re.search(self.rpc_patterns['rpc_errors'], content):
                            window_errors += 1
                        if re.search(self.rpc_patterns['rpc_busy'], content):
                            window_rpc_busy += 1

                # 高QPS vs 错误相关性分析
                if window_errors > 2 and current_qps > 50000:
                    correlation_results['high_qps_errors'].append({
                        'qps': current_qps,
                        'errors': window_errors,
                        'rpc_busy': window_rpc_busy,
                        'timestamp': qps_time
                    })

                # 性能降级检测
                if window_rpc_busy > 5:
                    correlation_results['performance_degradation_points'].append({
                        'qps': current_qps,
                        'rpc_busy_events': window_rpc_busy,
                        'timestamp': qps_time
                    })

            except Exception as e:
                continue

        # 计算相关系数
        if len(correlation_results['high_qps_errors']) > 5:
            qps_values = [item['qps'] for item in correlation_results['high_qps_errors']]
            error_values = [item['errors'] for item in correlation_results['high_qps_errors']]
            if len(qps_values) > 1 and len(error_values) > 1:
                correlation_results['qps_error_correlation'] = float(np.corrcoef(qps_values, error_values)[0, 1])

        return correlation_results

    def analyze_performance_timeline(self, log_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析性能时间线"""
        timeline = {
            'rpc_performance_over_time': [],
            'error_rate_over_time': [],
            'bottleneck_events': []
        }

        # 按小时分组分析
        hourly_data = defaultdict(lambda: {'rpc_count': 0, 'error_count': 0, 'busy_count': 0})

        for entry in log_entries:
            content = entry['content'].lower()
            hour_key = entry['timestamp'].strftime('%Y-%m-%d %H:00')

            if 'rpc' in content:
                hourly_data[hour_key]['rpc_count'] += 1

                if re.search(self.rpc_patterns['rpc_errors'], content):
                    hourly_data[hour_key]['error_count'] += 1

                if re.search(self.rpc_patterns['rpc_busy'], content):
                    hourly_data[hour_key]['busy_count'] += 1

        # 转换为时间线数据
        for hour, data in sorted(hourly_data.items()):
            if data['rpc_count'] > 0:
                error_rate = (data['error_count'] / data['rpc_count']) * 100
                busy_rate = (data['busy_count'] / data['rpc_count']) * 100

                timeline['rpc_performance_over_time'].append({
                    'hour': hour,
                    'rpc_count': data['rpc_count'],
                    'error_rate': error_rate,
                    'busy_rate': busy_rate
                })

        return timeline

    def generate_summary_statistics(self, log_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成汇总统计"""
        stats = {
            'total_log_entries': len(log_entries),
            'analysis_period_hours': 0,
            'rpc_requests_per_hour': 0,
            'error_rate_percentage': 0,
            'top_error_types': [],
            'critical_events_count': 0
        }

        if log_entries:
            start_time = min(entry['timestamp'] for entry in log_entries)
            end_time = max(entry['timestamp'] for entry in log_entries)
            stats['analysis_period_hours'] = (end_time - start_time).total_seconds() / 3600

            rpc_count = sum(1 for entry in log_entries if 'rpc' in entry['content'].lower())
            error_count = sum(1 for entry in log_entries
                              if re.search(self.rpc_patterns['rpc_errors'], entry['content'].lower()))

            if stats['analysis_period_hours'] > 0:
                stats['rpc_requests_per_hour'] = rpc_count / stats['analysis_period_hours']

            if rpc_count > 0:
                stats['error_rate_percentage'] = (error_count / rpc_count) * 100

            # 统计关键事件
            stats['critical_events_count'] = sum(1 for entry in log_entries
                                                 if re.search(self.rpc_patterns['memory_pressure'],
                                                              entry['content'].lower()))

        return stats

    def generate_log_analysis_report(self, analysis_results: Dict[str, Any]) -> str:
        """生成日志分析报告"""
        rpc_stats = analysis_results.get('rpc_analysis', {})
        bottlenecks = analysis_results.get('bottleneck_analysis', {})
        error_analysis = analysis_results.get('error_analysis', {})
        summary_stats = analysis_results.get('summary_stats', {})

        report = f"""
## 📋 Validator Log Analysis Results

### 📊 Analysis Summary
- **Total Log Entries Analyzed**: {summary_stats.get('total_log_entries', 0):,}
- **Analysis Period**: {summary_stats.get('analysis_period_hours', 0):.1f} hours
- **RPC Requests per Hour**: {summary_stats.get('rpc_requests_per_hour', 0):.0f}
- **Overall Error Rate**: {summary_stats.get('error_rate_percentage', 0):.2f}%

### 🔍 RPC Performance Analysis
- **Total RPC Requests**: {rpc_stats.get('total_rpc_requests', 0):,}
- **RPC Success Rate**: {rpc_stats.get('success_rate', 0):.2f}%
- **RPC Errors**: {rpc_stats.get('rpc_errors', 0):,}
- **RPC Busy Incidents**: {rpc_stats.get('rpc_busy_incidents', 0):,}
- **Average Response Time**: {rpc_stats.get('avg_response_time', 0):.1f}ms
- **P95 Response Time**: {rpc_stats.get('p95_response_time', 0):.1f}ms
- **P99 Response Time**: {rpc_stats.get('p99_response_time', 0):.1f}ms

### ⚠️ Critical Bottlenecks Detected
- **RPC Thread Saturation**: {bottlenecks.get('rpc_thread_saturation', 0)} incidents
- **Compute Unit Limits**: {bottlenecks.get('compute_unit_limits', 0)} incidents
- **Memory Pressure Events**: {bottlenecks.get('memory_pressure', 0)} incidents
- **I/O Bottlenecks**: {bottlenecks.get('io_bottlenecks', 0)} incidents
- **Network Issues**: {bottlenecks.get('network_issues', 0)} incidents

### 🎯 Most Active RPC Methods
"""

        method_dist = rpc_stats.get('method_distribution', {})
        for method, count in method_dist.most_common(5):
            report += f"- **{method}**: {count:,} requests\n"

        # 错误类型分析
        error_types = rpc_stats.get('error_types', {})
        if error_types:
            report += "\n### 🚨 Error Type Distribution\n"
            for error_type, count in error_types.most_common():
                report += f"- **{error_type}**: {count} occurrences\n"

        # 添加专门的错误分析部分 ✅ 使用 error_analysis 变量
        if error_analysis:
            report += "\n### 🔍 Detailed Error Analysis\n"
            
            # 错误统计
            total_errors = error_analysis.get('total_errors', 0)
            error_rate = error_analysis.get('error_rate', 0)
            report += f"- **Total Errors**: {total_errors:,}\n"
            report += f"- **Error Rate**: {error_rate:.2f}%\n"
            
            # 错误类型分布
            error_types_detailed = error_analysis.get('error_types', [])
            if error_types_detailed:
                report += f"- **Error Types**: {', '.join(error_types_detailed)}\n"
            
            # 错误趋势
            error_trend = error_analysis.get('error_trend', '')
            if error_trend:
                report += f"- **Error Trend**: {error_trend}\n"
            
            # 高频错误模式
            frequent_patterns = error_analysis.get('frequent_patterns', [])
            if frequent_patterns:
                report += "- **Frequent Error Patterns**:\n"
                for pattern in frequent_patterns[:3]:  # 显示前3个
                    report += f"  - {pattern.get('pattern', 'Unknown')}: {pattern.get('count', 0)} times\n"
            
            # 错误影响分析
            impact_analysis = error_analysis.get('impact_analysis', {})
            if impact_analysis:
                report += "- **Error Impact**:\n"
                if impact_analysis.get('performance_degradation'):
                    report += f"  - Performance degradation: {impact_analysis['performance_degradation']}\n"
                if impact_analysis.get('service_availability'):
                    report += f"  - Service availability: {impact_analysis['service_availability']}\n"

        # 关键事件时间线
        critical_events = bottlenecks.get('critical_events', [])
        if critical_events:
            report += "\n### ⏰ Critical Events Timeline (Latest 5)\n"
            for event in critical_events[-5:]:
                report += f"- **{event['type']}** ({event['severity']}): {event['timestamp']}\n"

        return report


# 使用示例
if __name__ == "__main__":
    print("📋 验证器日志分析器使用示例:")
    print("from validator_log_analyzer import ValidatorLogAnalyzer")
    print("analyzer = ValidatorLogAnalyzer('/path/to/validator.log')")
    print("results = analyzer.analyze_validator_logs_during_test(qps_df)")
    print("report = analyzer.generate_log_analysis_report(results)")
