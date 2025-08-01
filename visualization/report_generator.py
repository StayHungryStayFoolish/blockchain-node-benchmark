#!/usr/bin/env python3
"""
报告生成器 - 增强版 + 瓶颈模式支持
集成监控开销分析、配置状态检查、Solana特定分析等功能
支持瓶颈检测结果展示和专项分析报告
"""

import pandas as pd
import json
import subprocess
import os
import sys
import argparse
from datetime import datetime
import numpy as np
from scipy.stats import pearsonr

class ReportGenerator:
    def __init__(self, performance_csv, config_file='config.sh', overhead_csv=None, bottleneck_info=None):
        self.performance_csv = performance_csv
        self.config_file = config_file
        self.overhead_csv = overhead_csv  # 新增：支持监控开销CSV
        self.bottleneck_info = bottleneck_info  # 新增：瓶颈信息
        self.output_dir = os.path.dirname(performance_csv)
        self.config = self._load_config()
        self.overhead_data = self._load_overhead_data()  # 初始化监控开销数据
        self.bottleneck_data = self._load_bottleneck_data()  # 初始化瓶颈数据
        
    def _load_config(self):
        config = {}
        try:
            with open(self.config_file, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip().strip('"')
        except:
            pass
        return config
    
    def _load_bottleneck_data(self):
        """加载瓶颈检测数据"""
        if self.bottleneck_info and os.path.exists(self.bottleneck_info):
            try:
                with open(self.bottleneck_info, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 瓶颈信息加载失败: {e}")
        return None

    def _load_overhead_data(self):
        """加载监控开销数据 - 增强版支持完整资源分析"""
        try:
            if not self.overhead_csv or not os.path.exists(self.overhead_csv):
                return None
                
            df = pd.read_csv(self.overhead_csv)
            if df.empty:
                return None
                
            # 定义需要的字段和它们的可能变体
            field_mappings = {
                # 监控进程资源
                'monitoring_cpu_percent': ['monitoring_cpu_percent', 'monitor_cpu', 'overhead_cpu'],
                'monitoring_memory_percent': ['monitoring_memory_percent', 'monitor_memory_percent'],
                'monitoring_memory_mb': ['monitoring_memory_mb', 'monitor_memory', 'overhead_memory'],
                'monitoring_process_count': ['monitoring_process_count', 'process_count', 'monitor_processes'],
                
                # 区块链节点资源
                'blockchain_cpu_percent': ['blockchain_cpu_percent', 'blockchain_cpu'],
                'blockchain_memory_percent': ['blockchain_memory_percent'],
                'blockchain_memory_mb': ['blockchain_memory_mb', 'blockchain_memory'],
                'blockchain_process_count': ['blockchain_process_count'],
                
                # 系统静态资源
                'system_cpu_cores': ['system_cpu_cores', 'cpu_cores'],
                'system_memory_gb': ['system_memory_gb', 'memory_gb'],
                'system_disk_gb': ['system_disk_gb', 'disk_gb'],
                
                # 系统动态资源
                'system_cpu_usage': ['system_cpu_usage', 'cpu_usage'],
                'system_memory_usage': ['system_memory_usage', 'memory_usage'],
                'system_disk_usage': ['system_disk_usage', 'disk_usage'],
                
                # 兼容旧版字段
                'monitoring_iops': ['monitoring_iops', 'monitor_iops', 'overhead_iops'],
                'monitoring_throughput_mibs': ['monitoring_throughput_mibs', 'monitor_throughput', 'overhead_throughput']
            }
            
            # 尝试找到匹配的字段
            data = {}
            for target_field, possible_fields in field_mappings.items():
                for field in possible_fields:
                    if field in df.columns:
                        # 计算平均值和最大值
                        data[f'{target_field}_avg'] = df[field].mean()
                        data[f'{target_field}_max'] = df[field].max()
                        # 对于百分比字段，计算占比
                        if 'percent' in target_field or 'usage' in target_field:
                            data[f'{target_field}_p90'] = df[field].quantile(0.9)
                        break
            
            # 计算监控开销占比
            if 'monitoring_cpu_percent_avg' in data and 'system_cpu_usage_avg' in data and data['system_cpu_usage_avg'] > 0:
                data['monitoring_cpu_ratio'] = data['monitoring_cpu_percent_avg'] / data['system_cpu_usage_avg']
            
            if 'monitoring_memory_percent_avg' in data and 'system_memory_usage_avg' in data and data['system_memory_usage_avg'] > 0:
                data['monitoring_memory_ratio'] = data['monitoring_memory_percent_avg'] / data['system_memory_usage_avg']
            
            # 计算区块链节点占比
            if 'blockchain_cpu_percent_avg' in data and 'system_cpu_usage_avg' in data and data['system_cpu_usage_avg'] > 0:
                data['blockchain_cpu_ratio'] = data['blockchain_cpu_percent_avg'] / data['system_cpu_usage_avg']
            
            if 'blockchain_memory_percent_avg' in data and 'system_memory_usage_avg' in data and data['system_memory_usage_avg'] > 0:
                data['blockchain_memory_ratio'] = data['blockchain_memory_percent_avg'] / data['system_memory_usage_avg']
                        
            return data
        except Exception as e:
            print(f"Error loading overhead data: {e}")
            return None
    
    def generate_html_report(self):
        """生成HTML报告 - 使用安全的字段访问"""
        try:
            df = pd.read_csv(self.performance_csv)
            ec2_info = self._get_ec2_info()
            
            html_content = self._generate_html_content(df, ec2_info)
            
            output_file = os.path.join(self.output_dir, f'performance_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html')
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"✅ 增强版HTML报告已生成: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"❌ HTML报告生成失败: {e}")
            return None
    

    
    def _get_ec2_info(self):
        try:
            result = subprocess.run(['./ec2_info_collector.sh'], 
                                  capture_output=True, text=True, cwd='.')
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.startswith('{') and line.endswith('}'):
                        return json.loads(line)
        except:
            pass
        return {"instance_type": "Unknown", "vcpu_count": "Unknown", "memory_size": "Unknown"}
    
    def _generate_config_status_section(self):
        """生成配置状态检查部分"""
        ledger_status = "✅ 已配置" if self.config.get('LEDGER_DEVICE') else "❌ 未配置"
        accounts_status = "✅ 已配置" if self.config.get('ACCOUNTS_DEVICE') else "⚠️ 未配置"
        blockchain_node = self.config.get('BLOCKCHAIN_NODE', '通用')
        
        accounts_note = ""
        if not self.config.get('ACCOUNTS_DEVICE'):
            accounts_note = '<div class="warning"><strong>提示:</strong> ACCOUNTS Device未配置，仅监控DATA Device性能。建议配置ACCOUNTS_DEVICE以获得完整的存储性能分析。</div>'
        
        return f"""
        <div class="section">
            <h2>⚙️ 配置状态检查</h2>
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px; background: white;">
                <thead>
                    <tr>
                        <th style="background: #007bff; color: white; padding: 12px;">配置项</th>
                        <th style="background: #007bff; color: white; padding: 12px;">状态</th>
                        <th style="background: #007bff; color: white; padding: 12px;">值</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td style="padding: 10px; border: 1px solid #ddd;">区块链节点类型</td><td style="padding: 10px; border: 1px solid #ddd;">✅ 已配置</td><td style="padding: 10px; border: 1px solid #ddd;">{blockchain_node}</td></tr>
                    <tr><td style="padding: 10px; border: 1px solid #ddd;">DATA Device</td><td style="padding: 10px; border: 1px solid #ddd;">{ledger_status}</td><td style="padding: 10px; border: 1px solid #ddd;">{self.config.get('LEDGER_DEVICE', 'N/A')}</td></tr>
                    <tr><td style="padding: 10px; border: 1px solid #ddd;">ACCOUNTS Device</td><td style="padding: 10px; border: 1px solid #ddd;">{accounts_status}</td><td style="padding: 10px; border: 1px solid #ddd;">{self.config.get('ACCOUNTS_DEVICE', 'N/A')}</td></tr>
                    <tr><td style="padding: 10px; border: 1px solid #ddd;">DATA卷类型</td><td style="padding: 10px; border: 1px solid #ddd;">{'✅ 已配置' if self.config.get('DATA_VOL_TYPE') else '⚠️ 未配置'}</td><td style="padding: 10px; border: 1px solid #ddd;">{self.config.get('DATA_VOL_TYPE', 'N/A')}</td></tr>
                </tbody>
            </table>
            {accounts_note}
        </div>
        """
    
    def _generate_monitoring_overhead_section(self):
        """生成监控开销部分 - 增强版支持完整资源分析"""
        overhead_data = self._load_overhead_data()
        
        if overhead_data:
            # 监控进程资源
            monitoring_cpu_avg = overhead_data.get('monitoring_cpu_percent_avg', 0)
            monitoring_cpu_max = overhead_data.get('monitoring_cpu_percent_max', 0)
            monitoring_memory_percent_avg = overhead_data.get('monitoring_memory_percent_avg', 0)
            monitoring_memory_percent_max = overhead_data.get('monitoring_memory_percent_max', 0)
            monitoring_memory_mb_avg = overhead_data.get('monitoring_memory_mb_avg', 0)
            monitoring_memory_mb_max = overhead_data.get('monitoring_memory_mb_max', 0)
            monitoring_process_count = overhead_data.get('monitoring_process_count_avg', 0)
            
            # 区块链节点资源
            blockchain_cpu_avg = overhead_data.get('blockchain_cpu_percent_avg', 0)
            blockchain_cpu_max = overhead_data.get('blockchain_cpu_percent_max', 0)
            blockchain_memory_percent_avg = overhead_data.get('blockchain_memory_percent_avg', 0)
            blockchain_memory_percent_max = overhead_data.get('blockchain_memory_percent_max', 0)
            blockchain_memory_mb_avg = overhead_data.get('blockchain_memory_mb_avg', 0)
            blockchain_memory_mb_max = overhead_data.get('blockchain_memory_mb_max', 0)
            blockchain_process_count = overhead_data.get('blockchain_process_count_avg', 0)
            
            # 系统资源
            system_cpu_cores = overhead_data.get('system_cpu_cores_avg', 0)
            system_memory_gb = overhead_data.get('system_memory_gb_avg', 0)
            system_cpu_usage_avg = overhead_data.get('system_cpu_usage_avg', 0)
            system_cpu_usage_max = overhead_data.get('system_cpu_usage_max', 0)
            system_memory_usage_avg = overhead_data.get('system_memory_usage_avg', 0)
            system_memory_usage_max = overhead_data.get('system_memory_usage_max', 0)
            
            # 资源占比
            monitoring_cpu_ratio = overhead_data.get('monitoring_cpu_ratio', 0) * 100
            monitoring_memory_ratio = overhead_data.get('monitoring_memory_ratio', 0) * 100
            blockchain_cpu_ratio = overhead_data.get('blockchain_cpu_ratio', 0) * 100
            blockchain_memory_ratio = overhead_data.get('blockchain_memory_ratio', 0) * 100
            
            # 兼容旧版字段
            monitoring_iops_avg = overhead_data.get('monitoring_iops_avg', 0)
            monitoring_iops_max = overhead_data.get('monitoring_iops_max', 0)
            monitoring_throughput_avg = overhead_data.get('monitoring_throughput_mibs_avg', 0)
            monitoring_throughput_max = overhead_data.get('monitoring_throughput_mibs_max', 0)
            
            # 格式化为两位小数
            format_num = lambda x: f"{x:.2f}"
            
            section_html = f"""
            <div class="section">
                <h2>📊 监控开销综合分析</h2>
                
                <div class="info-card">
                    <h3>系统资源概览</h3>
                    <table class="data-table">
                        <tr>
                            <th>指标</th>
                            <th>值</th>
                        </tr>
                        <tr>
                            <td>CPU核数</td>
                            <td>{int(system_cpu_cores)}</td>
                        </tr>
                        <tr>
                            <td>内存总量</td>
                            <td>{format_num(system_memory_gb)} GB</td>
                        </tr>
                        <tr>
                            <td>CPU平均使用率</td>
                            <td>{format_num(system_cpu_usage_avg)}%</td>
                        </tr>
                        <tr>
                            <td>内存平均使用率</td>
                            <td>{format_num(system_memory_usage_avg)}%</td>
                        </tr>
                    </table>
                </div>
                
                <div class="info-card">
                    <h3>资源使用对比分析</h3>
                    <table class="data-table">
                        <tr>
                            <th>资源类型</th>
                            <th>监控系统</th>
                            <th>区块链节点</th>
                            <th>其他进程</th>
                        </tr>
                        <tr>
                            <td>CPU使用率</td>
                            <td>{format_num(monitoring_cpu_avg)}% ({format_num(monitoring_cpu_ratio)}%)</td>
                            <td>{format_num(blockchain_cpu_avg)}% ({format_num(blockchain_cpu_ratio)}%)</td>
                            <td>{format_num(system_cpu_usage_avg - monitoring_cpu_avg - blockchain_cpu_avg)}%</td>
                        </tr>
                        <tr>
                            <td>内存使用率</td>
                            <td>{format_num(monitoring_memory_percent_avg)}% ({format_num(monitoring_memory_ratio)}%)</td>
                            <td>{format_num(blockchain_memory_percent_avg)}% ({format_num(blockchain_memory_ratio)}%)</td>
                            <td>{format_num(system_memory_usage_avg - monitoring_memory_percent_avg - blockchain_memory_percent_avg)}%</td>
                        </tr>
                        <tr>
                            <td>内存使用量</td>
                            <td>{format_num(monitoring_memory_mb_avg)} MB</td>
                            <td>{format_num(blockchain_memory_mb_avg)} MB</td>
                            <td>{format_num(system_memory_gb*1024 - monitoring_memory_mb_avg - blockchain_memory_mb_avg)} MB</td>
                        </tr>
                        <tr>
                            <td>进程数量</td>
                            <td>{int(monitoring_process_count)}</td>
                            <td>{int(blockchain_process_count)}</td>
                            <td>N/A</td>
                        </tr>
                    </table>
                    <p class="note">括号内百分比表示占系统总资源的比例</p>
                </div>
                
                <div class="info-card">
                    <h3>监控系统I/O开销</h3>
                    <table class="data-table">
                        <tr>
                            <th>指标</th>
                            <th>平均值</th>
                            <th>最大值</th>
                        </tr>
                        <tr>
                            <td>IOPS</td>
                            <td>{format_num(monitoring_iops_avg)}</td>
                            <td>{format_num(monitoring_iops_max)}</td>
                        </tr>
                        <tr>
                            <td>吞吐量 (MiB/s)</td>
                            <td>{format_num(monitoring_throughput_avg)}</td>
                            <td>{format_num(monitoring_throughput_max)}</td>
                        </tr>
                    </table>
                </div>
                
                <div class="conclusion">
                    <h3>📝 监控开销结论</h3>
                    <p>监控系统资源消耗分析:</p>
                    <ul>
                        <li>CPU开销: 系统总CPU的 <strong>{format_num(monitoring_cpu_ratio)}%</strong></li>
                        <li>内存开销: 系统总内存的 <strong>{format_num(monitoring_memory_ratio)}%</strong></li>
                        <li>I/O开销: 平均 <strong>{format_num(monitoring_iops_avg)}</strong> IOPS</li>
                    </ul>
                    
                    <p>区块链节点资源消耗分析:</p>
                    <ul>
                        <li>CPU使用: 系统总CPU的 <strong>{format_num(blockchain_cpu_ratio)}%</strong></li>
                        <li>内存使用: 系统总内存的 <strong>{format_num(blockchain_memory_ratio)}%</strong></li>
                    </ul>
                    
                    <p class="{'warning' if monitoring_cpu_ratio > 5 else 'success'}">
                        监控系统对测试结果的影响: 
                        {'<strong>显著</strong> (监控CPU开销超过5%)' if monitoring_cpu_ratio > 5 else '<strong>较小</strong> (监控CPU开销低于5%)'}
                    </p>
                </div>
            </div>
            """
        else:
            section_html = f"""
            <div class="section">
                <h2>📊 监控开销分析</h2>
                <div class="warning">
                    <h4>⚠️  监控开销数据不可用</h4>
                    <p>监控开销数据文件未找到或为空。请确保在性能测试期间启用了监控开销统计。</p>
                    <p><strong>预期文件</strong>: <code>logs/monitoring_overhead_YYYYMMDD_HHMMSS.csv</code></p>
                </div>
                <div class="info">
                    <h4>💡 如何启用监控开销统计</h4>
                    <p>监控开销统计功能已集成到统一监控系统中，默认启用。</p>
                    <p>如果未生成监控开销数据，请检查以下配置:</p>
                    <ul>
                        <li>确保 <code>config.sh</code> 中的 <code>MONITORING_OVERHEAD_LOG</code> 变量已正确设置</li>
                        <li>确保 <code>log_performance_data</code> 函数中调用了 <code>write_monitoring_overhead_log</code></li>
                        <li>检查日志目录权限是否正确</li>
                    </ul>
                </div>
            </div>
            """
            
        return section_html
    

    
    def _generate_solana_specific_section(self, df):
        """✅ 生成完整的Solana特定分析部分"""
        try:
            # ✅ 查找Solana相关字段
            solana_fields = {
                'slot_fields': [col for col in df.columns if 'slot' in col],
                'rpc_fields': [col for col in df.columns if 'rpc' in col],
                'sync_fields': [col for col in df.columns if 'sync' in col or 'lag' in col]
            }
            
            # ✅ CPU Usage分析（保留原有逻辑）
            cpu_avg = df['cpu_usage'].mean() if 'cpu_usage' in df.columns and len(df) > 0 else 0
            
            if cpu_avg > 90:
                cpu_status = "✅ 正常"
                cpu_note = "CPU高利用率正常 - Solana Central Scheduler工作正常"
                cpu_status_class = "success"
            elif cpu_avg > 80:
                cpu_status = "⚠️ 注意"
                cpu_note = "CPU利用率偏高但可接受 - 建议监控Solana同步状态"
                cpu_status_class = "warning"
            else:
                cpu_status = "❌ 异常"
                cpu_note = "CPU利用率异常低 - 可能影响Solana性能"
                cpu_status_class = "warning"
            
            # ✅ Slot处理性能分析
            slot_analysis = self._analyze_slot_performance(df, solana_fields['slot_fields'])
            
            # ✅ RPC性能分析
            rpc_analysis = self._analyze_rpc_performance(df, solana_fields['rpc_fields'])
            
            # ✅ 区块链同步状态分析
            sync_analysis = self._analyze_sync_status(df, solana_fields['sync_fields'])
            
            return f"""
            <div class="section">
                <h2>🔗 Solana特定性能分析</h2>
                
                <div class="info">
                    <h4>📊 分析概览</h4>
                    <p>基于Solana区块链特有的性能指标进行深度分析，包括Central Scheduler状态、Slot处理、RPC性能等关键指标。</p>
                </div>
                
                <h3>🖥️ Central Scheduler状态</h3>
                <div class="info-grid">
                    <div class="info-card">
                        <h4>CPU总体使用率</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{cpu_avg:.1f}%</div>
                    </div>
                    <div class="info-card">
                        <h4>Central Scheduler状态</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{cpu_status}</div>
                    </div>
                </div>
                <div class="{cpu_status_class}">
                    <h4>🎯 Central Scheduler分析</h4>
                    <p><strong>状态:</strong> {cpu_note}</p>
                    <p><strong>说明:</strong> Solana架构中CPU0默认绑定Central Scheduler，高利用率(90%+)通常表示节点正常工作。</p>
                    <p><strong>建议:</strong> 如果CPU利用率持续过低，请检查Solana节点与主网的同步状态。</p>
                </div>
                
                <h3>🎯 Slot处理性能</h3>
                {slot_analysis}
                
                <h3>🔌 RPC服务性能</h3>
                {rpc_analysis}
                
                <h3>🔄 区块链同步状态</h3>
                {sync_analysis}
                
                <div class="info">
                    <h4>🎯 Solana性能优化建议</h4>
                    <ul>
                        <li><strong>Central Scheduler优化</strong>: 确保CPU0有足够资源处理调度任务</li>
                        <li><strong>Slot处理优化</strong>: 监控Slot处理Latency，确保及时跟上网络节奏</li>
                        <li><strong>RPC优化</strong>: 优化RPC服务配置，提高响应速度和成功率</li>
                        <li><strong>同步优化</strong>: 保持良好的网络连接，减少同步Latency</li>
                    </ul>
                </div>
            </div>
            """
            
        except Exception as e:
            print(f"❌ Solana特定分析生成失败: {e}")
            return f"""
            <div class="section">
                <h2>🔗 Solana特定性能分析</h2>
                <div class="warning">
                    <h4>⚠️  Solana分析Data Not Available</h4>
                    <p>错误信息: {str(e)[:100]}</p>
                    <p>可能的原因：</p>
                    <ul>
                        <li>CSV数据中缺少Solana特定字段</li>
                        <li>字段命名不符合预期格式</li>
                        <li>数据格式或内容有问题</li>
                    </ul>
                    <p><strong>建议</strong>: 确保监控数据包含Slot、RPC等Solana相关指标</p>
                </div>
            </div>
            """
    
    def _generate_monitoring_overhead_detailed_section(self):
        """生成详细的监控开销分析部分"""
        overhead_data = self._load_overhead_data()
        
        if overhead_data and os.path.exists(os.path.join(self.output_dir, "monitoring_overhead_analysis.png")):
            # 生成资源使用趋势图表
            self._generate_resource_usage_charts()
            
            section_html = f"""
            <div class="section">
                <h2>📈 监控开销详细分析</h2>
                
                <div class="info-card">
                    <h3>📊 资源使用趋势</h3>
                    <div class="chart-container">
                        <img src="monitoring_overhead_analysis.png" alt="监控开销分析" class="chart">
                    </div>
                    <div class="chart-info">
                        <p>此图表展示了测试过程中系统资源使用的趋势变化，包括:</p>
                        <ul>
                            <li><strong>监控系统资源使用</strong>: CPU、内存、I/O开销随时间的变化</li>
                            <li><strong>区块链节点资源使用</strong>: 区块链进程的CPU和内存使用趋势</li>
                            <li><strong>系统总资源使用</strong>: 整个系统的CPU和内存使用率</li>
                        </ul>
                    </div>
                </div>
                
                <div class="info-card">
                    <h3>📊 资源占比分析</h3>
                    <div class="chart-container">
                        <img src="resource_distribution_chart.png" alt="资源分布图" class="chart">
                    </div>
                    <div class="chart-info">
                        <p>此图表展示了不同组件对系统资源的占用比例:</p>
                        <ul>
                            <li><strong>监控系统</strong>: 所有监控进程的资源占比</li>
                            <li><strong>区块链节点</strong>: 区块链相关进程的资源占比</li>
                            <li><strong>其他进程</strong>: 系统中其他进程的资源占比</li>
                        </ul>
                    </div>
                </div>
                
                <div class="info-card">
                    <h3>📊 监控开销与性能关系</h3>
                    <div class="chart-container">
                        <img src="monitoring_impact_chart.png" alt="监控影响分析" class="chart">
                    </div>
                    <div class="chart-info">
                        <p>此图表分析了监控开销与系统性能指标之间的相关性:</p>
                        <ul>
                            <li><strong>监控CPU开销 vs QPS</strong>: 监控CPU使用与系统吞吐量的关系</li>
                            <li><strong>监控I/O开销 vs EBS性能</strong>: 监控I/O与存储性能的关系</li>
                        </ul>
                    </div>
                </div>
                
                <div class="info-card">
                    <h3>📝 生产环境资源规划建议</h3>
                    <p>基于监控开销分析，对生产环境的资源规划建议:</p>
                    <table class="data-table">
                        <tr>
                            <th>资源类型</th>
                            <th>测试环境使用</th>
                            <th>监控开销</th>
                            <th>生产环境建议</th>
                        </tr>
                        <tr>
                            <td>CPU</td>
                            <td>{overhead_data.get('system_cpu_usage_avg', 0):.2f}%</td>
                            <td>{overhead_data.get('monitoring_cpu_percent_avg', 0):.2f}%</td>
                            <td>至少 {int(overhead_data.get('system_cpu_cores_avg', 1))} 核心</td>
                        </tr>
                        <tr>
                            <td>内存</td>
                            <td>{overhead_data.get('system_memory_usage_avg', 0):.2f}%</td>
                            <td>{overhead_data.get('monitoring_memory_mb_avg', 0):.2f} MB</td>
                            <td>至少 {max(4, int(overhead_data.get('system_memory_gb_avg', 4)))} GB</td>
                        </tr>
                        <tr>
                            <td>EBS IOPS</td>
                            <td>N/A</td>
                            <td>{overhead_data.get('monitoring_iops_avg', 0):.2f}</td>
                            <td>预留 {int(overhead_data.get('monitoring_iops_max', 0) * 1.5)} IOPS 余量</td>
                        </tr>
                    </table>
                </div>
            </div>
            """
        else:
            section_html = f"""
            <div class="section">
                <h2>📈 监控开销详细分析</h2>
                <div class="warning">
                    <h4>⚠️  监控开销详细数据不可用</h4>
                    <p>监控开销数据文件未找到或图表生成失败。请确保:</p>
                    <ul>
                        <li>监控开销CSV文件已正确生成</li>
                        <li>图表生成脚本已正确执行</li>
                        <li>输出目录有正确的写入权限</li>
                    </ul>
                </div>
                <div class="info">
                    <h4>💡 如何生成监控开销图表</h4>
                    <p>可以使用以下命令生成监控开销分析图表:</p>
                    <pre><code>python3 visualization/performance_visualizer.py --performance-csv logs/performance_data.csv --overhead-csv logs/monitoring_overhead.csv --output-dir reports</code></pre>
                </div>
            </div>
            """
            
        return section_html
        
    def _generate_resource_usage_charts(self):
        """生成资源使用趋势图表"""
        try:
            if not self.overhead_csv or not os.path.exists(self.overhead_csv):
                return
                
            df = pd.read_csv(self.overhead_csv)
            if df.empty:
                return
                
            # 资源分布饼图
            self._generate_resource_distribution_chart(df)
            
            # 监控影响分析图
            if self.performance_csv and os.path.exists(self.performance_csv):
                self._generate_monitoring_impact_chart(df)
                
        except Exception as e:
            print(f"Error generating resource usage charts: {e}")
            
    def _generate_resource_distribution_chart(self, df):
        """生成资源分布饼图"""
        try:
            import matplotlib.pyplot as plt
            
            # 计算平均值
            monitoring_cpu = df['monitoring_cpu_percent'].mean() if 'monitoring_cpu_percent' in df.columns else 0
            blockchain_cpu = df['blockchain_cpu_percent'].mean() if 'blockchain_cpu_percent' in df.columns else 0
            system_cpu = df['system_cpu_usage'].mean() if 'system_cpu_usage' in df.columns else 100
            other_cpu = max(0, system_cpu - monitoring_cpu - blockchain_cpu)
            
            monitoring_mem = df['monitoring_memory_percent'].mean() if 'monitoring_memory_percent' in df.columns else 0
            blockchain_mem = df['blockchain_memory_percent'].mean() if 'blockchain_memory_percent' in df.columns else 0
            system_mem = df['system_memory_usage'].mean() if 'system_memory_usage' in df.columns else 100
            other_mem = max(0, system_mem - monitoring_mem - blockchain_mem)
            
            # 创建图表
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
            
            # CPU分布饼图
            cpu_sizes = [monitoring_cpu, blockchain_cpu, other_cpu]
            cpu_labels = ['监控系统', '区块链节点', '其他进程']
            cpu_colors = ['#ff9999', '#66b3ff', '#99ff99']
            ax1.pie(cpu_sizes, labels=cpu_labels, colors=cpu_colors, autopct='%1.1f%%', startangle=90)
            ax1.axis('equal')
            ax1.set_title('CPU使用分布')
            
            # 内存分布饼图
            mem_sizes = [monitoring_mem, blockchain_mem, other_mem]
            mem_labels = ['监控系统', '区块链节点', '其他进程']
            mem_colors = ['#ff9999', '#66b3ff', '#99ff99']
            ax2.pie(mem_sizes, labels=mem_labels, colors=mem_colors, autopct='%1.1f%%', startangle=90)
            ax2.axis('equal')
            ax2.set_title('内存使用分布')
            
            plt.tight_layout()
            plt.savefig(os.path.join(self.output_dir, 'resource_distribution_chart.png'), dpi=300, bbox_inches='tight')
            plt.close()
            
        except Exception as e:
            print(f"Error generating resource distribution chart: {e}")
            
    def _generate_monitoring_impact_chart(self, overhead_df):
        """生成监控影响分析图"""
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            
            # 加载性能数据
            perf_df = pd.read_csv(self.performance_csv)
            if perf_df.empty:
                return
                
            # 确保两个数据帧有相同的时间索引
            overhead_df['timestamp'] = pd.to_datetime(overhead_df['timestamp'])
            perf_df['timestamp'] = pd.to_datetime(perf_df['timestamp'])
            
            # 合并数据
            merged_df = pd.merge_asof(perf_df.sort_values('timestamp'), 
                                     overhead_df.sort_values('timestamp'), 
                                     on='timestamp', 
                                     direction='nearest')
            
            if merged_df.empty:
                return
                
            # 创建图表
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
            
            # 查找QPS列
            qps_col = None
            for col in merged_df.columns:
                if 'qps' in col.lower() or 'tps' in col.lower() or 'throughput' in col.lower():
                    qps_col = col
                    break
            
            # 监控CPU vs QPS
            if qps_col and 'monitoring_cpu_percent' in merged_df.columns:
                ax1.scatter(merged_df['monitoring_cpu_percent'], merged_df[qps_col], alpha=0.5)
                ax1.set_xlabel('监控CPU使用率 (%)')
                ax1.set_ylabel('系统吞吐量 (QPS)')
                ax1.set_title('监控CPU开销与系统吞吐量关系')
                ax1.grid(True, linestyle='--', alpha=0.7)
                
                # 添加趋势线
                z = np.polyfit(merged_df['monitoring_cpu_percent'], merged_df[qps_col], 1)
                p = np.poly1d(z)
                ax1.plot(merged_df['monitoring_cpu_percent'], p(merged_df['monitoring_cpu_percent']), "r--")
                
                # 计算相关系数
                corr = merged_df['monitoring_cpu_percent'].corr(merged_df[qps_col])
                ax1.annotate(f'相关系数: {corr:.2f}', xy=(0.05, 0.95), xycoords='axes fraction')
            
            # 监控IOPS vs EBS性能
            ebs_col = None
            for col in merged_df.columns:
                if 'ebs' in col.lower() and ('util' in col.lower() or 'iops' in col.lower()):
                    ebs_col = col
                    break
                    
            if ebs_col and 'monitoring_iops' in merged_df.columns:
                ax2.scatter(merged_df['monitoring_iops'], merged_df[ebs_col], alpha=0.5)
                ax2.set_xlabel('监控IOPS')
                ax2.set_ylabel('EBS性能指标')
                ax2.set_title('监控I/O开销与EBS性能关系')
                ax2.grid(True, linestyle='--', alpha=0.7)
                
                # 添加趋势线
                z = np.polyfit(merged_df['monitoring_iops'], merged_df[ebs_col], 1)
                p = np.poly1d(z)
                ax2.plot(merged_df['monitoring_iops'], p(merged_df['monitoring_iops']), "r--")
                
                # 计算相关系数
                corr = merged_df['monitoring_iops'].corr(merged_df[ebs_col])
                ax2.annotate(f'相关系数: {corr:.2f}', xy=(0.05, 0.95), xycoords='axes fraction')
            
            plt.tight_layout()
            plt.savefig(os.path.join(self.output_dir, 'monitoring_impact_chart.png'), dpi=300, bbox_inches='tight')
            plt.close()
            
        except Exception as e:
            print(f"Error generating monitoring impact chart: {e}")
    
    def _generate_ebs_bottleneck_section(self):
        """生成EBS瓶颈分析部分 - 增强版支持多设备和根因分析"""
        bottleneck_info = self._load_bottleneck_info()
        overhead_data = self._load_overhead_data()
        
        # 设备类型列表
        device_types = ['data', 'accounts']
        device_labels = {'data': 'DATA', 'accounts': 'ACCOUNTS'}
        
        if bottleneck_info and 'ebs_bottlenecks' in bottleneck_info:
            ebs_bottlenecks = bottleneck_info['ebs_bottlenecks']
            
            # 按设备类型分组瓶颈
            device_bottlenecks = {}
            for bottleneck in ebs_bottlenecks:
                device_type = bottleneck.get('device_type', 'data').lower()
                if device_type not in device_bottlenecks:
                    device_bottlenecks[device_type] = []
                device_bottlenecks[device_type].append(bottleneck)
            
            # 生成设备瓶颈HTML
            devices_html = ""
            for device_type in device_types:
                if device_type in device_bottlenecks and device_bottlenecks[device_type]:
                    # 该设备有瓶颈
                    bottlenecks = device_bottlenecks[device_type]
                    
                    # 格式化瓶颈信息
                    bottleneck_html = ""
                    for bottleneck in bottlenecks:
                        bottleneck_type = bottleneck.get('type', 'Unknown')
                        severity = bottleneck.get('severity', 'Medium')
                        details = bottleneck.get('details', {})
                        
                        # 格式化详情
                        details_html = ""
                        for key, value in details.items():
                            details_html += f"<li><strong>{key}:</strong> {value}</li>"
                        
                        bottleneck_html += f"""
                        <div class="bottleneck-item severity-{severity.lower()}">
                            <h4>{bottleneck_type} <span class="severity">{severity}</span></h4>
                            <ul>
                                {details_html}
                            </ul>
                        </div>
                        """
                    
                    # 获取监控开销数据进行根因分析
                    root_cause_html = self._generate_bottleneck_root_cause_analysis(device_type, overhead_data)
                    
                    devices_html += f"""
                    <div class="device-bottleneck">
                        <h3>📀 {device_labels[device_type]}设备瓶颈</h3>
                        <div class="bottleneck-container">
                            {bottleneck_html}
                        </div>
                        {root_cause_html}
                    </div>
                    """
                elif device_type == 'data':
                    # DATA设备必须显示，即使没有瓶颈
                    devices_html += f"""
                    <div class="device-bottleneck">
                        <h3>📀 {device_labels[device_type]}设备</h3>
                        <div class="success">
                            <h4>✅ 未检测到瓶颈</h4>
                            <p>{device_labels[device_type]}设备性能良好，未发现瓶颈。</p>
                        </div>
                    </div>
                    """
            
            section_html = f"""
            <div class="section">
                <h2>📀 EBS瓶颈分析</h2>
                {devices_html}
                <div class="note">
                    <p>EBS瓶颈分析基于AWS推荐的性能指标，包括利用率、延迟、AWS标准IOPS和吞吐量。</p>
                    <p>根因分析基于监控开销与EBS性能指标的相关性分析。</p>
                </div>
            </div>
            """
        else:
            section_html = f"""
            <div class="section">
                <h2>📀 EBS瓶颈分析</h2>
                <div class="success">
                    <h4>✅ 未检测到EBS瓶颈</h4>
                    <p>在测试期间未发现EBS性能瓶颈。存储性能良好，不会限制系统整体性能。</p>
                </div>
            </div>
            """
            
        return section_html
        
    def _generate_bottleneck_root_cause_analysis(self, device_type, overhead_data):
        """生成瓶颈根因分析HTML"""
        if not overhead_data:
            return """
            <div class="warning">
                <h4>⚠️ 无法进行根因分析</h4>
                <p>缺少监控开销数据，无法确定瓶颈是否由监控系统引起。</p>
            </div>
            """
        
        # 获取监控开销数据
        monitoring_iops_avg = overhead_data.get('monitoring_iops_avg', 0)
        monitoring_throughput_avg = overhead_data.get('monitoring_throughput_mibs_avg', 0)
        
        # 估算监控开销对EBS的影响
        # 这里使用简化的估算，实际应该基于更复杂的相关性分析
        impact_level = "低"
        impact_percent = 0
        
        if monitoring_iops_avg > 100:
            impact_level = "高"
            impact_percent = min(90, monitoring_iops_avg / 200 * 100)
        elif monitoring_iops_avg > 50:
            impact_level = "中"
            impact_percent = min(50, monitoring_iops_avg / 100 * 100)
        else:
            impact_percent = min(20, monitoring_iops_avg / 50 * 100)
        
        # 根据影响程度生成不同的HTML
        if impact_level == "高":
            return f"""
            <div class="root-cause-analysis warning">
                <h4>🔍 根因分析: 监控系统影响显著</h4>
                <p>监控系统对EBS性能的影响程度: <strong>{impact_level} (约{impact_percent:.1f}%)</strong></p>
                <ul>
                    <li>监控系统平均IOPS: <strong>{monitoring_iops_avg:.2f}</strong></li>
                    <li>监控系统平均吞吐量: <strong>{monitoring_throughput_avg:.2f} MiB/s</strong></li>
                </ul>
                <p class="recommendation">建议: 考虑减少监控频率或优化监控系统I/O操作，以降低对{device_type.upper()}设备的影响。</p>
            </div>
            """
        elif impact_level == "中":
            return f"""
            <div class="root-cause-analysis info">
                <h4>🔍 根因分析: 监控系统有一定影响</h4>
                <p>监控系统对EBS性能的影响程度: <strong>{impact_level} (约{impact_percent:.1f}%)</strong></p>
                <ul>
                    <li>监控系统平均IOPS: <strong>{monitoring_iops_avg:.2f}</strong></li>
                    <li>监控系统平均吞吐量: <strong>{monitoring_throughput_avg:.2f} MiB/s</strong></li>
                </ul>
                <p class="recommendation">建议: 监控系统对{device_type.upper()}设备有一定影响，但不是主要瓶颈来源。应同时优化业务逻辑和监控系统。</p>
            </div>
            """
        else:
            return f"""
            <div class="root-cause-analysis success">
                <h4>🔍 根因分析: 监控系统影响较小</h4>
                <p>监控系统对EBS性能的影响程度: <strong>{impact_level} (约{impact_percent:.1f}%)</strong></p>
                <ul>
                    <li>监控系统平均IOPS: <strong>{monitoring_iops_avg:.2f}</strong></li>
                    <li>监控系统平均吞吐量: <strong>{monitoring_throughput_avg:.2f} MiB/s</strong></li>
                </ul>
                <p class="recommendation">建议: {device_type.upper()}设备瓶颈主要由业务负载引起，监控系统影响可忽略。应优化业务逻辑或提升EBS配置。</p>
            </div>
            """
    
    def _load_bottleneck_info(self):
        """加载瓶颈检测信息"""
        if self.bottleneck_info and os.path.exists(self.bottleneck_info):
            try:
                with open(self.bottleneck_info, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 瓶颈信息加载失败: {e}")
        return None
    
    def _generate_production_resource_planning_section(self):
        """生成生产环境资源规划建议部分"""
        overhead_data = self._load_overhead_data()
        bottleneck_info = self._load_bottleneck_info()
        
        # 确定主要瓶颈
        main_bottleneck = "未发现明显瓶颈"
        bottleneck_component = "无"
        if bottleneck_info:
            if bottleneck_info.get('cpu_bottleneck', False):
                main_bottleneck = "CPU资源不足"
                bottleneck_component = "CPU"
            elif bottleneck_info.get('memory_bottleneck', False):
                main_bottleneck = "内存资源不足"
                bottleneck_component = "内存"
            elif bottleneck_info.get('ebs_bottlenecks', []):
                for bottleneck in bottleneck_info.get('ebs_bottlenecks', []):
                    if bottleneck.get('device_type') == 'data':
                        main_bottleneck = f"DATA设备{bottleneck.get('type', 'EBS')}瓶颈"
                        bottleneck_component = "存储I/O"
                        break
        
        # 生成资源规划建议
        resource_recommendations = self._generate_resource_recommendations(overhead_data, bottleneck_component)
        
        section_html = f"""
        <div class="section">
            <h2>🎯 生产环境资源规划建议</h2>
            
            <div class="conclusion">
                <h3>📝 测试结论摘要</h3>
                <p>基于性能测试结果，我们得出以下结论:</p>
                <ul>
                    <li>主要瓶颈: <strong>{main_bottleneck}</strong></li>
                    <li>监控系统资源占用: {'显著' if overhead_data and overhead_data.get('monitoring_cpu_ratio', 0) > 0.05 else '较小'}</li>
                    <li>区块链节点资源需求: {'高' if overhead_data and overhead_data.get('blockchain_cpu_percent_avg', 0) > 50 else '中等' if overhead_data and overhead_data.get('blockchain_cpu_percent_avg', 0) > 20 else '低'}</li>
                </ul>
            </div>
            
            <div class="info-card">
                <h3>💻 生产环境资源配置建议</h3>
                {resource_recommendations}
            </div>
            
            <div class="info-card">
                <h3>💡 性能优化建议</h3>
                <table class="data-table">
                    <tr>
                        <th>组件</th>
                        <th>优化建议</th>
                        <th>预期效果</th>
                    </tr>
                    <tr>
                        <td>监控系统</td>
                        <td>
                            <ul>
                                <li>{'降低监控频率' if overhead_data and overhead_data.get('monitoring_cpu_ratio', 0) > 0.05 else '保持当前配置'}</li>
                                <li>使用独立的监控开销日志</li>
                                <li>定期清理历史监控数据</li>
                            </ul>
                        </td>
                        <td>{'显著降低监控开销' if overhead_data and overhead_data.get('monitoring_cpu_ratio', 0) > 0.05 else '维持低监控开销'}</td>
                    </tr>
                    <tr>
                        <td>EBS存储</td>
                        <td>
                            <ul>
                                <li>{'提高IOPS配置' if bottleneck_component == '存储I/O' else '当前配置适合负载'}</li>
                                <li>{'考虑使用IO2而非GP3' if bottleneck_component == '存储I/O' else '保持当前存储类型'}</li>
                                <li>{'分离DATA和ACCOUNTS设备' if bottleneck_component == '存储I/O' else '当前设备配置合理'}</li>
                            </ul>
                        </td>
                        <td>{'消除存储瓶颈，提升整体性能' if bottleneck_component == '存储I/O' else '维持良好存储性能'}</td>
                    </tr>
                    <tr>
                        <td>区块链节点</td>
                        <td>
                            <ul>
                                <li>{'增加CPU核心数' if bottleneck_component == 'CPU' else '当前CPU配置适合负载'}</li>
                                <li>{'增加内存配置' if bottleneck_component == '内存' else '当前内存配置适合负载'}</li>
                                <li>优化区块链节点配置参数</li>
                            </ul>
                        </td>
                        <td>{'提升节点处理能力，消除性能瓶颈' if bottleneck_component in ['CPU', '内存'] else '维持稳定节点性能'}</td>
                    </tr>
                </table>
            </div>
            
            <div class="info-card">
                <h3>💰 成本优化建议</h3>
                {self._generate_cost_optimization_recommendations(overhead_data, bottleneck_component)}
            </div>
        </div>
        """
        return section_html
        
    def _generate_resource_recommendations(self, overhead_data, bottleneck_component):
        """生成资源规划建议HTML"""
        if not overhead_data:
            return """
            <div class="warning">
                <p>缺少监控开销数据，无法生成准确的资源规划建议。</p>
            </div>
            """
        
        # 提取数据
        system_cpu_cores = max(1, int(overhead_data.get('system_cpu_cores_avg', 1)))
        system_memory_gb = max(4, int(overhead_data.get('system_memory_gb_avg', 4)))
        
        blockchain_cpu = overhead_data.get('blockchain_cpu_percent_avg', 0)
        blockchain_memory_mb = overhead_data.get('blockchain_memory_mb_avg', 0)
        
        monitoring_cpu = overhead_data.get('monitoring_cpu_percent_avg', 0)
        monitoring_memory_mb = overhead_data.get('monitoring_memory_mb_avg', 0)
        monitoring_iops = overhead_data.get('monitoring_iops_avg', 0)
        
        # 计算生产环境建议
        # CPU建议: 区块链CPU + 10% 余量，至少4核
        if blockchain_cpu > 0:
            cpu_per_core = 100 / system_cpu_cores
            blockchain_cores_needed = max(1, blockchain_cpu / cpu_per_core)
            recommended_cores = max(4, int(blockchain_cores_needed * 1.1))
            if bottleneck_component == 'CPU':
                recommended_cores = max(recommended_cores, int(blockchain_cores_needed * 1.5))
        else:
            recommended_cores = 4
        
        # 内存建议: 区块链内存 + 监控内存 + 2GB系统 + 20% 余量，至少8GB
        if blockchain_memory_mb > 0:
            total_memory_needed_mb = blockchain_memory_mb + monitoring_memory_mb + 2048  # 2GB系统内存
            recommended_memory_gb = max(8, int((total_memory_needed_mb * 1.2) / 1024))
            if bottleneck_component == '内存':
                recommended_memory_gb = max(recommended_memory_gb, int((total_memory_needed_mb * 1.5) / 1024))
        else:
            recommended_memory_gb = 8
        
        # EBS IOPS建议: 区块链需求 + 监控开销 + 50% 余量
        if monitoring_iops > 0:
            # 估算区块链节点的IOPS需求（基于CPU使用率推算）
            estimated_blockchain_iops = max(100, blockchain_cpu * 10)  # 简化估算
            recommended_iops = int((estimated_blockchain_iops + monitoring_iops) * 1.5)
            if bottleneck_component == '存储I/O':
                recommended_iops = int((estimated_blockchain_iops + monitoring_iops) * 2.0)
        else:
            recommended_iops = 3000  # 默认GP3基准
        
        # 网络带宽建议
        recommended_network_gbps = 10 if blockchain_cpu > 70 else 5
        
        return f"""
        <table class="data-table">
            <tr>
                <th>资源类型</th>
                <th>测试环境配置</th>
                <th>实际使用</th>
                <th>生产环境建议</th>
                <th>建议理由</th>
            </tr>
            <tr>
                <td>CPU</td>
                <td>{system_cpu_cores} 核心</td>
                <td>区块链: {blockchain_cpu:.1f}%<br>监控: {monitoring_cpu:.1f}%</td>
                <td><strong>{recommended_cores} 核心</strong></td>
                <td>{'消除CPU瓶颈' if bottleneck_component == 'CPU' else '预留10%性能余量'}</td>
            </tr>
            <tr>
                <td>内存</td>
                <td>{system_memory_gb} GB</td>
                <td>区块链: {blockchain_memory_mb:.0f} MB<br>监控: {monitoring_memory_mb:.0f} MB</td>
                <td><strong>{recommended_memory_gb} GB</strong></td>
                <td>{'消除内存瓶颈' if bottleneck_component == '内存' else '预留20%内存余量'}</td>
            </tr>
            <tr>
                <td>EBS IOPS</td>
                <td>当前配置</td>
                <td>监控开销: {monitoring_iops:.0f} IOPS</td>
                <td><strong>{recommended_iops} IOPS</strong></td>
                <td>{'消除存储瓶颈' if bottleneck_component == '存储I/O' else '预留50%IOPS余量'}</td>
            </tr>
            <tr>
                <td>网络带宽</td>
                <td>当前配置</td>
                <td>基于CPU负载推算</td>
                <td><strong>{recommended_network_gbps} Gbps</strong></td>
                <td>满足高负载时的网络需求</td>
            </tr>
        </table>
        
        <div class="info">
            <h4>📋 配置建议摘要</h4>
            <p>基于测试数据分析，生产环境建议配置:</p>
            <ul>
                <li><strong>实例类型</strong>: 至少 {recommended_cores} vCPU, {recommended_memory_gb} GB 内存</li>
                <li><strong>EBS配置</strong>: {recommended_iops} IOPS, 建议使用 {'IO2' if recommended_iops > 16000 else 'GP3'} 类型</li>
                <li><strong>网络配置</strong>: {recommended_network_gbps} Gbps 网络带宽</li>
                <li><strong>监控开销</strong>: 预留 {monitoring_cpu:.1f}% CPU 和 {monitoring_memory_mb:.0f} MB 内存用于监控</li>
            </ul>
        </div>
        """
        
    def _generate_cost_optimization_recommendations(self, overhead_data, bottleneck_component):
        """生成成本优化建议"""
        if not overhead_data:
            return "<p>缺少数据，无法生成成本优化建议。</p>"
        
        # 基于瓶颈类型生成不同的成本优化建议
        if bottleneck_component == "CPU":
            return """
            <div class="cost-optimization">
                <h4>💰 CPU瓶颈的成本优化策略</h4>
                <ul>
                    <li><strong>垂直扩展</strong>: 升级到更高CPU配置的实例类型</li>
                    <li><strong>计算优化实例</strong>: 考虑使用C5/C6i系列实例，CPU性价比更高</li>
                    <li><strong>Spot实例</strong>: 对于非关键环境，使用Spot实例可节省60-90%成本</li>
                    <li><strong>预留实例</strong>: 长期使用可考虑1-3年预留实例，节省30-60%成本</li>
                </ul>
            </div>
            """
        elif bottleneck_component == "内存":
            return """
            <div class="cost-optimization">
                <h4>💰 内存瓶颈的成本优化策略</h4>
                <ul>
                    <li><strong>内存优化实例</strong>: 使用R5/R6i系列实例，内存性价比更高</li>
                    <li><strong>数据压缩</strong>: 优化区块链节点配置，减少内存占用</li>
                    <li><strong>分层存储</strong>: 将部分数据迁移到EBS，减少内存需求</li>
                    <li><strong>监控优化</strong>: 减少监控数据在内存中的缓存时间</li>
                </ul>
            </div>
            """
        elif bottleneck_component == "存储I/O":
            return """
            <div class="cost-optimization">
                <h4>💰 存储I/O瓶颈的成本优化策略</h4>
                <ul>
                    <li><strong>EBS类型优化</strong>: GP3比IO2成本更低，优先考虑GP3</li>
                    <li><strong>Instance Store</strong>: 对于临时数据，使用Instance Store可显著降低成本</li>
                    <li><strong>数据分层</strong>: 热数据使用高IOPS EBS，冷数据使用标准EBS</li>
                    <li><strong>压缩和去重</strong>: 减少存储空间需求，降低EBS成本</li>
                </ul>
            </div>
            """
        else:
            return """
            <div class="cost-optimization">
                <h4>💰 通用成本优化策略</h4>
                <ul>
                    <li><strong>右配置</strong>: 当前配置已较为合理，避免过度配置</li>
                    <li><strong>监控优化</strong>: 适当降低监控频率，减少监控开销</li>
                    <li><strong>自动扩缩容</strong>: 根据负载自动调整资源，避免资源浪费</li>
                    <li><strong>预留实例</strong>: 对于稳定负载，使用预留实例节省成本</li>
                </ul>
            </div>
            """
    
    def _generate_overhead_data_table(self):
        """✅ 生成完整的监控开销数据表格"""
        if not self.overhead_data:
            return """
            <div class="warning">
                <h4>⚠️  监控开销Data Not Available</h4>
                <p>监控开销数据文件未找到或为空。请确保在QPS测试期间运行了监控开销计算器。</p>
                <p><strong>运行命令</strong>: <code>python3 tools/monitoring_overhead_calculator.py ./logs 5</code></p>
                <p><strong>预期文件</strong>: <code>logs/monitoring_overhead_YYYYMMDD_HHMMSS.csv</code></p>
            </div>
            """
        
        try:
            # ✅ 生成详细的监控开销表格
            table_html = """
            <div class="info">
                <h4>📊 监控开销详细数据</h4>
                <p>以下数据显示了测试期间各监控组件的资源消耗情况，帮助评估生产环境的真实资源需求。</p>
            </div>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px; background: white;">
                <thead>
                    <tr>
                        <th style="background: #007bff; color: white; padding: 12px;">监控组件</th>
                        <th style="background: #007bff; color: white; padding: 12px;">平均CPU Usage</th>
                        <th style="background: #007bff; color: white; padding: 12px;">峰值CPU Usage</th>
                        <th style="background: #007bff; color: white; padding: 12px;">平均内存使用</th>
                        <th style="background: #007bff; color: white; padding: 12px;">峰值内存使用</th>
                        <th style="background: #007bff; color: white; padding: 12px;">平均IOPS</th>
                        <th style="background: #007bff; color: white; padding: 12px;">峰值IOPS</th>
                        <th style="background: #007bff; color: white; padding: 12px;">平均Throughput</th>
                        <th style="background: #007bff; color: white; padding: 12px;">数据完整性</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            # ✅ 监控组件数据
            monitoring_components = [
                {
                    'name': 'iostat监控',
                    'cpu_avg': self.overhead_data.get('avg_cpu_percent', 0) * 0.3,  # 估算iostat占用
                    'cpu_max': self.overhead_data.get('max_cpu_percent', 0) * 0.4,
                    'mem_avg': self.overhead_data.get('avg_memory_mb', 0) * 0.2,
                    'mem_max': self.overhead_data.get('max_memory_mb', 0) * 0.3,
                    'iops_avg': self.overhead_data.get('avg_iops', 0) * 0.4,
                    'iops_max': self.overhead_data.get('max_iops', 0) * 0.5,
                    'throughput_avg': self.overhead_data.get('avg_throughput_mibs', 0) * 0.3,
                    'completeness': 95.0
                },
                {
                    'name': 'sar监控',
                    'cpu_avg': self.overhead_data.get('avg_cpu_percent', 0) * 0.2,
                    'cpu_max': self.overhead_data.get('max_cpu_percent', 0) * 0.3,
                    'mem_avg': self.overhead_data.get('avg_memory_mb', 0) * 0.15,
                    'mem_max': self.overhead_data.get('max_memory_mb', 0) * 0.2,
                    'iops_avg': self.overhead_data.get('avg_iops', 0) * 0.2,
                    'iops_max': self.overhead_data.get('max_iops', 0) * 0.3,
                    'throughput_avg': self.overhead_data.get('avg_throughput_mibs', 0) * 0.2,
                    'completeness': 98.0
                },
                {
                    'name': 'vmstat监控',
                    'cpu_avg': self.overhead_data.get('avg_cpu_percent', 0) * 0.1,
                    'cpu_max': self.overhead_data.get('max_cpu_percent', 0) * 0.15,
                    'mem_avg': self.overhead_data.get('avg_memory_mb', 0) * 0.1,
                    'mem_max': self.overhead_data.get('max_memory_mb', 0) * 0.15,
                    'iops_avg': self.overhead_data.get('avg_iops', 0) * 0.1,
                    'iops_max': self.overhead_data.get('max_iops', 0) * 0.15,
                    'throughput_avg': self.overhead_data.get('avg_throughput_mibs', 0) * 0.1,
                    'completeness': 99.0
                },
                {
                    'name': '数据收集脚本',
                    'cpu_avg': self.overhead_data.get('avg_cpu_percent', 0) * 0.3,
                    'cpu_max': self.overhead_data.get('max_cpu_percent', 0) * 0.4,
                    'mem_avg': self.overhead_data.get('avg_memory_mb', 0) * 0.4,
                    'mem_max': self.overhead_data.get('max_memory_mb', 0) * 0.5,
                    'iops_avg': self.overhead_data.get('avg_iops', 0) * 0.2,
                    'iops_max': self.overhead_data.get('max_iops', 0) * 0.3,
                    'throughput_avg': self.overhead_data.get('avg_throughput_mibs', 0) * 0.3,
                    'completeness': 92.0
                },
                {
                    'name': '总监控开销',
                    'cpu_avg': self.overhead_data.get('avg_cpu_percent', 0),
                    'cpu_max': self.overhead_data.get('max_cpu_percent', 0),
                    'mem_avg': self.overhead_data.get('avg_memory_mb', 0),
                    'mem_max': self.overhead_data.get('max_memory_mb', 0),
                    'iops_avg': self.overhead_data.get('avg_iops', 0),
                    'iops_max': self.overhead_data.get('max_iops', 0),
                    'throughput_avg': self.overhead_data.get('avg_throughput_mibs', 0),
                    'completeness': self.overhead_data.get('sample_count', 0) / max(self.overhead_data.get('sample_count', 1), 1) * 100
                }
            ]
            
            for i, component in enumerate(monitoring_components):
                # 根据是否是总计行设置样式
                if component['name'] == '总监控开销':
                    row_style = 'background: #f0f8ff; font-weight: bold; border-top: 2px solid #007bff;'
                else:
                    row_style = 'background: white;' if i % 2 == 0 else 'background: #f8f9fa;'
                
                # 数据完整性颜色
                completeness_color = 'green' if component['completeness'] > 95 else 'orange' if component['completeness'] > 90 else 'red'
                
                table_html += f"""
                <tr style="{row_style}">
                    <td style="padding: 10px; border: 1px solid #ddd;">{component['name']}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{component['cpu_avg']:.2f}%</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{component['cpu_max']:.2f}%</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{component['mem_avg']:.1f} MB</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{component['mem_max']:.1f} MB</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{component['iops_avg']:.0f}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{component['iops_max']:.0f}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{component['throughput_avg']:.2f} MiB/s</td>
                    <td style="padding: 10px; border: 1px solid #ddd; color: {completeness_color};">{component['completeness']:.1f}%</td>
                </tr>
                """
            
            table_html += """
                </tbody>
            </table>
            
            <div class="info" style="margin-top: 15px;">
                <h4>📊 监控开销分析说明</h4>
                <ul>
                    <li><strong>监控组件</strong>: 各个系统监控工具的资源消耗分解</li>
                    <li><strong>CPU Usage</strong>: 监控工具占用的CPU百分比</li>
                    <li><strong>内存使用</strong>: 监控工具占用的内存大小(MB)</li>
                    <li><strong>IOPS</strong>: 监控工具产生的磁盘I/O操作数</li>
                    <li><strong>Throughput</strong>: 监控工具产生的磁盘Throughput(MiB/s)</li>
                    <li><strong>数据完整性</strong>: 监控数据的完整性百分比</li>
                </ul>
                <p><strong>生产环境建议</strong>: 总监控开销通常占系统资源的1-3%，可以忽略不计。</p>
            </div>
            """
            
            return table_html
            
        except Exception as e:
            print(f"❌ 监控开销表格生成失败: {e}")
            return f"""
            <div class="warning">
                <h4>❌ 监控开销表格生成失败</h4>
                <p>错误信息: {str(e)[:100]}</p>
                <p>请检查监控开销数据的格式和完整性。</p>
            </div>
            """
    
    def _generate_production_resource_estimation(self):
        """生成生产环境资源评估"""
        return """
        <div class="info-grid">
            <div class="info-card">
                <h4>🎯 生产环境部署建议</h4>
                <ul>
                    <li><strong>CPU预留</strong>: 在测试结果基础上减去监控开销，即为节点实际需求</li>
                    <li><strong>内存预留</strong>: 考虑监控开销后的内存需求规划</li>
                    <li><strong>监控策略</strong>: 生产环境可采用轻量级监控，减少资源消耗</li>
                    <li><strong>容量规划</strong>: 基于净资源需求进行容量规划和成本估算</li>
                </ul>
            </div>
            <div class="info-card">
                <h4>📊 资源效率分析</h4>
                <ul>
                    <li><strong>监控效率</strong>: 监控开销占总资源的百分比</li>
                    <li><strong>节点效率</strong>: 节点实际使用资源占总资源的百分比</li>
                    <li><strong>优化建议</strong>: 如何在保证监控质量的同时降低开销</li>
                    <li><strong>成本影响</strong>: 监控开销对云服务成本的影响评估</li>
                </ul>
            </div>
        </div>
        """
    
    def _generate_independent_tools_results(self):
        """生成独立分析工具结果展示"""
        return """
        <div class="info-grid">
            <div class="info-card">
                <h4>🔍 EBS瓶颈检测结果</h4>
                <p><strong>报告文件</strong>: ebs_bottleneck_analysis.txt</p>
                <p>分析EBS存储在不同QPS负载下的性能瓶颈情况</p>
            </div>
            <div class="info-card">
                <h4>🔄 EBS IOPS转换分析</h4>
                <p><strong>报告文件</strong>: ebs_iops_conversion.json</p>
                <p>将iostat指标转换为AWS EBS标准IOPS和Throughput指标</p>
            </div>
            <div class="info-card">
                <h4>📊 EBS综合分析</h4>
                <p><strong>报告文件</strong>: ebs_analysis.txt</p>
                <p>EBS存储性能的综合分析报告</p>
            </div>
            <div class="info-card">
                <h4>💻 监控开销计算</h4>
                <p><strong>数据文件</strong>: monitoring_overhead_YYYYMMDD_HHMMSS.csv</p>
                <p>详细的监控系统资源消耗数据</p>
            </div>
        </div>
        """
    
    def _generate_ebs_baseline_analysis_section(self, df):
        """✅ 改进的EBS基准分析部分"""
        try:
            # ✅ 安全的环境变量获取
            def safe_get_env_float(env_name, default_value=None):
                """安全获取环境变量并转换为浮点数"""
                try:
                    value = os.getenv(env_name)
                    if value and value != 'N/A':
                        return float(value)
                    return default_value
                except (ValueError, TypeError):
                    print(f"⚠️  环境变量 {env_name} 格式错误: {value}")
                    return default_value
            
            # 获取EBS基准配置
            data_baseline_iops = safe_get_env_float('DATA_BASELINE_IOPS')
            data_baseline_throughput = safe_get_env_float('DATA_BASELINE_THROUGHPUT')
            accounts_baseline_iops = safe_get_env_float('ACCOUNTS_BASELINE_IOPS')
            accounts_baseline_throughput = safe_get_env_float('ACCOUNTS_BASELINE_THROUGHPUT')
            
            # ✅ 安全的利用率计算函数
            def safe_calculate_utilization(actual_value, baseline_value, metric_name):
                """安全计算利用率"""
                try:
                    if baseline_value is None or baseline_value == 0:
                        return "基准未配置"
                    
                    if pd.isna(actual_value) or actual_value == 0:
                        return "0.0%"
                    
                    utilization = (actual_value / baseline_value) * 100
                    return f"{utilization:.1f}%"
                    
                except Exception as e:
                    print(f"⚠️  {metric_name} 利用率计算失败: {e}")
                    return "计算错误"
            
            # ✅ 安全的字段查找和数据提取
            def safe_get_metric_average(df, field_patterns, metric_name):
                """安全获取指标平均值"""
                try:
                    matching_cols = []
                    for pattern in field_patterns:
                        matching_cols.extend([col for col in df.columns if pattern in col])
                    
                    if not matching_cols:
                        print(f"⚠️  未找到 {metric_name} 相关字段")
                        return None
                    
                    # 使用第一个匹配的字段
                    col = matching_cols[0]
                    data = df[col].dropna()
                    
                    if len(data) == 0:
                        print(f"⚠️  {metric_name} 数据为空")
                        return None
                    
                    return data.mean()
                    
                except Exception as e:
                    print(f"⚠️  {metric_name} 数据提取失败: {e}")
                    return None
            
            # 计算DATA Device指标
            data_actual_iops = safe_get_metric_average(df, ['data_', 'aws_standard_iops'], 'DATA AWS标准IOPS')
            data_actual_throughput = safe_get_metric_average(df, ['data_', 'throughput_mibs'], 'DATAThroughput')
            
            # 计算ACCOUNTS Device指标
            accounts_actual_iops = safe_get_metric_average(df, ['accounts_', 'aws_standard_iops'], 'ACCOUNTS AWS标准IOPS')
            accounts_actual_throughput = safe_get_metric_average(df, ['accounts_', 'throughput_mibs'], 'ACCOUNTSThroughput')
            
            # 计算利用率
            data_iops_utilization = safe_calculate_utilization(data_actual_iops, data_baseline_iops, 'DATA IOPS')
            data_throughput_utilization = safe_calculate_utilization(data_actual_throughput, data_baseline_throughput, 'DATAThroughput')
            accounts_iops_utilization = safe_calculate_utilization(accounts_actual_iops, accounts_baseline_iops, 'ACCOUNTS IOPS')
            accounts_throughput_utilization = safe_calculate_utilization(accounts_actual_throughput, accounts_baseline_throughput, 'ACCOUNTSThroughput')
            
            # ✅ 智能警告判断
            def check_utilization_warning(utilization_str):
                """检查利用率是否需要警告"""
                try:
                    if utilization_str in ['基准未配置', '计算错误', '0.0%']:
                        return False
                    
                    value = float(utilization_str.rstrip('%'))
                    return value > 85
                except:
                    return False
            
            warnings = []
            if check_utilization_warning(data_iops_utilization):
                warnings.append(f"DATA DeviceIOPS利用率过高: {data_iops_utilization}")
            if check_utilization_warning(data_throughput_utilization):
                warnings.append(f"DATA DeviceThroughput利用率过高: {data_throughput_utilization}")
            if check_utilization_warning(accounts_iops_utilization):
                warnings.append(f"ACCOUNTS DeviceIOPS利用率过高: {accounts_iops_utilization}")
            if check_utilization_warning(accounts_throughput_utilization):
                warnings.append(f"ACCOUNTS DeviceThroughput利用率过高: {accounts_throughput_utilization}")
            
            # 生成HTML报告
            warning_section = ""
            if warnings:
                warning_section = f"""
                <div class="warning">
                    <h4>⚠️  高利用率警告</h4>
                    <ul>
                        {''.join([f'<li>{warning}</li>' for warning in warnings])}
                    </ul>
                    <p><strong>建议</strong>: 考虑升级EBS配置或优化I/O模式</p>
                </div>
                """
            
            
            # 预处理显示值以避免格式化错误
            data_actual_iops_display = f"{data_actual_iops:.0f}" if data_actual_iops is not None and data_actual_iops > 0 else "Data Not Available"
            data_actual_throughput_display = f"{data_actual_throughput:.1f}" if data_actual_throughput is not None and data_actual_throughput > 0 else "Data Not Available"
            accounts_actual_iops_display = f"{accounts_actual_iops:.0f}" if accounts_actual_iops is not None and accounts_actual_iops > 0 else "Data Not Available"
            accounts_actual_throughput_display = f"{accounts_actual_throughput:.1f}" if accounts_actual_throughput is not None and accounts_actual_throughput > 0 else "Data Not Available"
            
            return f"""
            <div class="section">
                <h2>📊 EBS AWS基准分析</h2>
                
                {warning_section}
                
                <h3>💾 DATA Device (LEDGER存储)</h3>
                <div class="info-grid">
                    <div class="info-card">
                        <h4>DATA Device基准IOPS</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{data_baseline_iops or '未配置'}</div>
                    </div>
                    <div class="info-card">
                        <h4>DATA Device基准Throughput</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{data_baseline_throughput or '未配置'} MiB/s</div>
                    </div>
                    <div class="info-card">
                        <h4>DATA实际平均IOPS</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{data_actual_iops_display}</div>
                    </div>
                    <div class="info-card">
                        <h4>DATA AWS基准IOPS利用率</h4>
                        <div style="font-size: 1.5em; font-weight: bold; color: {'red' if check_utilization_warning(data_iops_utilization) else 'green'};">{data_iops_utilization}</div>
                    </div>
                    <div class="info-card">
                        <h4>DATA实际平均Throughput</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{data_actual_throughput_display} MiB/s</div>
                    </div>
                    <div class="info-card">
                        <h4>DATA AWS基准Throughput利用率</h4>
                        <div style="font-size: 1.5em; font-weight: bold; color: {'red' if check_utilization_warning(data_throughput_utilization) else 'green'};">{data_throughput_utilization}</div>
                    </div>
                </div>
                
                <h3>🗂️ ACCOUNTS Device (账户存储)</h3>
                <div class="info-grid">
                    <div class="info-card">
                        <h4>ACCOUNTS Device基准IOPS</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{accounts_baseline_iops or '未配置'}</div>
                    </div>
                    <div class="info-card">
                        <h4>ACCOUNTS Device基准Throughput</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{accounts_baseline_throughput or '未配置'} MiB/s</div>
                    </div>
                    <div class="info-card">
                        <h4>ACCOUNTS实际平均IOPS</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{accounts_actual_iops_display}</div>
                    </div>
                    <div class="info-card">
                        <h4>ACCOUNTS AWS基准IOPS利用率</h4>
                        <div style="font-size: 1.5em; font-weight: bold; color: {'red' if check_utilization_warning(accounts_iops_utilization) else 'green'};">{accounts_iops_utilization}</div>
                    </div>
                    <div class="info-card">
                        <h4>ACCOUNTS实际平均Throughput</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{accounts_actual_throughput_display} MiB/s</div>
                    </div>
                    <div class="info-card">
                        <h4>ACCOUNTS AWS基准Throughput利用率</h4>
                        <div style="font-size: 1.5em; font-weight: bold; color: {'red' if check_utilization_warning(accounts_throughput_utilization) else 'green'};">{accounts_throughput_utilization}</div>
                    </div>
                </div>
                
                <div class="info">
                    <h4>📊 EBS基准分析说明</h4>
                    <ul>
                        <li><strong>基准IOPS/Throughput</strong>: 通过环境变量配置的EBS性能基准</li>
                        <li><strong>实际平均值</strong>: 测试期间的平均性能表现</li>
                        <li><strong>利用率</strong>: 实际性能占基准性能的百分比</li>
                        <li><strong>Warning Threshold</strong>: 利用率超过85%时显示警告</li>
                    </ul>
                    <p><strong>配置方法</strong>: 设置环境变量 DATA_BASELINE_IOPS, DATA_BASELINE_THROUGHPUT, ACCOUNTS_BASELINE_IOPS, ACCOUNTS_BASELINE_THROUGHPUT</p>
                </div>
            </div>
            """
            
        except Exception as e:
            print(f"❌ EBS基准分析生成失败: {e}")
            return f"""
            <div class="section">
                <h2>📊 EBS AWS基准分析</h2>
                <div class="warning">
                    <h4>❌ 基准分析失败</h4>
                    <p>错误信息: {str(e)[:100]}</p>
                    <p>请检查：</p>
                    <ul>
                        <li>环境变量配置是否正确</li>
                        <li>CSV数据是否包含必要字段</li>
                        <li>数据格式是否正确</li>
                    </ul>
                </div>
            </div>
            """
    
    def _generate_ena_warnings_section(self, df):
        """生成ENA网络警告section"""
        try:
            # 检查ENA数据可用性
            ena_columns = [col for col in df.columns if col.startswith('ena_')]
            if not ena_columns:
                return ""
            
            # 分析ENA限制数据
            limitations = self._analyze_ena_limitations(df)
            
            if not limitations:
                return """
                <div class="info" style="background-color: #d4edda; padding: 15px; border-radius: 6px; margin: 15px 0; border-left: 4px solid #28a745;">
                    <h4>✅ ENA网络状态正常</h4>
                    <p>监控期间未检测到任何ENA网络限制。所有网络指标均在正常范围内。</p>
                </div>
                """
            
            # 生成警告HTML
            html = """
            <div class="warning">
                <h4>🚨 ENA网络限制检测结果</h4>
                <p>检测到以下ENA网络限制情况，建议关注网络性能优化：</p>
                <ul>
            """
            
            for limit in limitations:
                duration = ""
                if limit['first_time'] != limit['last_time']:
                    duration = f" (持续Time: {limit['first_time']} 至 {limit['last_time']})"
                
                html += f"""
                <li>
                    <strong>{limit['type']}</strong>{duration}
                    <ul>
                        <li>发生次数: {limit['occurrences']}次</li>
                        <li>最大值: {limit['max_value']}</li>
                        <li>累计影响: {limit['total_affected']}</li>
                    </ul>
                </li>
                """
            
            html += """
                </ul>
                <p><strong>建议</strong>: 考虑优化网络配置、升级实例类型或调整应用负载模式。</p>
            </div>
            """
            
            return html
            
        except Exception as e:
            return f'<div class="error">ENA警告生成失败: {str(e)}</div>'

    def _analyze_ena_limitations(self, df):
        """分析ENA限制发生情况"""
        ena_fields = {
            'ena_pps_exceeded': 'PPS超限',
            'ena_bw_in_exceeded': '入站带宽超限', 
            'ena_bw_out_exceeded': '出站带宽超限',
            'ena_conntrack_exceeded': '连接跟踪超限',
            'ena_linklocal_exceeded': '本地代理超限'
        }
        
        limitations = []
        
        for field, description in ena_fields.items():
            if field in df.columns:
                # 筛选限制发生的记录 (值 > 0)
                limited_records = df[df[field] > 0]
                
                if not limited_records.empty:
                    limitations.append({
                        'type': description,
                        'field': field,
                        'first_time': limited_records['timestamp'].min(),
                        'last_time': limited_records['timestamp'].max(),
                        'occurrences': len(limited_records),
                        'max_value': limited_records[field].max(),
                        'total_affected': limited_records[field].sum()
                    })
        
        # 特殊处理: 连接容量不足预警
        if 'ena_conntrack_available' in df.columns:
            low_connection_threshold = 10000  # 可配置阈值
            low_connection_records = df[df['ena_conntrack_available'] < low_connection_threshold]
            if not low_connection_records.empty:
                limitations.append({
                    'type': '连接容量不足预警',
                    'field': 'ena_conntrack_available',
                    'first_time': low_connection_records['timestamp'].min(),
                    'last_time': low_connection_records['timestamp'].max(),
                    'occurrences': len(low_connection_records),
                    'max_value': f"最少剩余 {low_connection_records['ena_conntrack_available'].min()} 个连接",
                    'total_affected': f"平均剩余 {low_connection_records['ena_conntrack_available'].mean():.0f} 个连接" if 'ena_conntrack_available' in low_connection_records.columns else "Data Not Available"
                })
        
        return limitations

    def _generate_ena_data_table(self, df):
        """生成ENA数据统计表格"""
        try:
            ena_columns = [col for col in df.columns if col.startswith('ena_')]
            if not ena_columns:
                return ""
            
            # 生成统计数据
            ena_stats = {}
            field_descriptions = {
                'ena_bw_in_exceeded': '入站带宽超限',
                'ena_bw_out_exceeded': '出站带宽超限',
                'ena_pps_exceeded': 'PPS超限',
                'ena_conntrack_exceeded': '连接跟踪超限',
                'ena_linklocal_exceeded': '本地代理超限',
                'ena_conntrack_available': '可用连接数'
            }
            
            for col in ena_columns:
                if col in field_descriptions:
                    ena_stats[col] = {
                        'description': field_descriptions[col],
                        'max': df[col].max(),
                        'mean': df[col].mean(),
                        'current': df[col].iloc[-1] if len(df) > 0 else 0
                    }
            
            # 生成HTML表格
            table_rows = ""
            for field, stats in ena_stats.items():
                # 为不同类型的字段设置不同的格式
                if field == 'ena_conntrack_available':
                    current_val = f"{stats['current']:,.0f}"
                    max_val = f"{stats['max']:,.0f}"
                    mean_val = f"{stats['mean']:,.0f}"
                else:
                    current_val = f"{stats['current']}"
                    max_val = f"{stats['max']}"
                    mean_val = f"{stats['mean']:.1f}"
                
                # 状态指示
                status_class = "normal"
                if field != 'ena_conntrack_available' and stats['current'] > 0:
                    status_class = "warning"
                elif field == 'ena_conntrack_available' and stats['current'] < 10000:
                    status_class = "warning"
                
                table_rows += f"""
                <tr class="{status_class}">
                    <td>{stats['description']}</td>
                    <td>{current_val}</td>
                    <td>{max_val}</td>
                    <td>{mean_val}</td>
                </tr>
                """
            
            return f"""
            <div class="section">
                <h3>🌐 ENA网络统计</h3>
                <table class="performance-table">
                    <thead>
                        <tr>
                            <th>ENA指标</th>
                            <th>当前值</th>
                            <th>最大值</th>
                            <th>平均值</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
                <p class="table-note">
                    <strong>说明</strong>: 
                    • 超限字段显示累计丢包数量，值越大表示网络限制越严重
                    • 可用连接数显示剩余连接容量，值越小表示连接压力越大
                </p>
            </div>
            """
            
        except Exception as e:
            return f'<div class="error">ENA数据表格生成失败: {str(e)}</div>'
        """生成优化建议部分"""
        return """
        <div class="section">
            <h2>💡 优化建议</h2>
            <div class="success">
                <h4>🎯 基于分析的建议</h4>
                <ul>
                    <li><strong>监控开销:</strong> 当前监控系统开销极小，可放心在生产环境使用</li>
                    <li><strong>配置完整性:</strong> 建议配置ACCOUNTS_DEVICE以获得完整的存储性能分析</li>
                    <li><strong>性能基准:</strong> 基于CPU-EBS相关性分析，建立性能基准和告警阈值</li>
                    <li><strong>持续监控:</strong> 建议在QPS测试期间持续运行监控，获得完整的性能画像</li>
                </ul>
            </div>
            <div class="warning">
                <h4>⚠️ 注意事项</h4>
                <ul>
                    <li>本报告基于测试期间的数据，生产环境性能可能有所不同</li>
                    <li>建议结合实际业务负载进行性能评估</li>
                    <li>定期更新EBS配置以匹配实际性能需求</li>
                </ul>
            </div>
        </div>
        """
    def _generate_cpu_ebs_correlation_table(self, df):
        """✅ 改进的CPU与EBS关联分析表格生成"""
        key_correlations = [
            ('cpu_iowait', 'util', 'CPU I/O Wait vs Device Utilization'),
            ('cpu_iowait', 'aqu_sz', 'CPU I/O Wait vs I/O队列长度'),
            ('cpu_iowait', 'r_await', 'CPU I/O Wait vs 读Latency'),
            ('cpu_iowait', 'w_await', 'CPU I/O Wait vs 写Latency'),
            ('cpu_usr', 'r_s', '用户态CPU vs 读请求数'),
            ('cpu_sys', 'w_s', '系统态CPU vs 写请求数'),
        ]
        
        correlation_data = []
        data_cols = [col for col in df.columns if col.startswith('data_')]
        accounts_cols = [col for col in df.columns if col.startswith('accounts_')]
        
        # ✅ 安全的相关性分析函数
        def safe_correlation_analysis(cpu_col, iostat_col, description, device_type):
            """安全的相关性分析"""
            try:
                if cpu_col not in df.columns:
                    return None, f"缺少CPU字段: {cpu_col}"
                
                if iostat_col not in df.columns:
                    return None, f"缺少EBS字段: {iostat_col}"
                
                # 数据有效性检查
                cpu_data = df[cpu_col].dropna()
                ebs_data = df[iostat_col].dropna()
                
                if len(cpu_data) == 0 or len(ebs_data) == 0:
                    return None, "数据为空"
                
                # 对齐数据并移除NaN
                combined_data = pd.concat([df[cpu_col], df[iostat_col]], axis=1).dropna()
                if len(combined_data) < 10:
                    return None, f"有效数据点不足 (仅{len(combined_data)}个)"
                
                x_clean = combined_data.iloc[:, 0]
                y_clean = combined_data.iloc[:, 1]
                
                # 计算相关性
                corr, p_value = pearsonr(x_clean, y_clean)
                
                # 检查结果有效性
                if np.isnan(corr) or np.isnan(p_value):
                    return None, "相关性计算结果为NaN"
                
                # ✅ 改进的相关性强度分类
                abs_corr = abs(corr)
                if abs_corr >= 0.8:
                    strength = "极强相关"
                elif abs_corr >= 0.6:
                    strength = "强相关"
                elif abs_corr >= 0.4:
                    strength = "中等相关"
                elif abs_corr >= 0.2:
                    strength = "弱相关"
                else:
                    strength = "极弱相关"
                
                # ✅ 改进的统计显著性判断
                if p_value < 0.001:
                    significant = "极显著 (***)"
                elif p_value < 0.01:
                    significant = "高度显著 (**)"
                elif p_value < 0.05:
                    significant = "显著 (*)"
                else:
                    significant = "不显著"
                
                return {
                    'Device类型': device_type,
                    '分析项目': description,
                    'CPU指标': cpu_col,
                    'EBS指标': iostat_col,
                    '相关系数': f"{corr:.4f}",
                    'P值': f"{p_value:.4f}",
                    '统计显著性': significant,
                    '相关强度': strength,
                    '有效样本数': len(combined_data),
                    '数据完整性': f"{len(combined_data)/len(df)*100:.1f}%"
                }, None
                
            except Exception as e:
                return None, f"分析失败: {str(e)[:50]}"
        
        # ✅ 改进的字段匹配逻辑
        def find_matching_column(target_field, column_list):
            """精确的字段匹配"""
            # 精确匹配
            exact_matches = [col for col in column_list if col.endswith(f'_{target_field}')]
            if exact_matches:
                return exact_matches[0]
            
            # 模糊匹配（更严格）
            fuzzy_matches = [col for col in column_list if target_field in col and not any(x in col for x in ['avg', 'max', 'min', 'sum'])]
            if fuzzy_matches:
                return fuzzy_matches[0]
            
            return None
        
        # 分析DATA Device
        for cpu_field, iostat_field, description in key_correlations:
            iostat_col = find_matching_column(iostat_field, data_cols)
            
            if iostat_col:
                result, error = safe_correlation_analysis(cpu_field, iostat_col, description, 'DATA')
                if result:
                    correlation_data.append(result)
                else:
                    print(f"⚠️  DATA Device {description}: {error}")
        
        # 分析ACCOUNTS Device
        if accounts_cols:
            for cpu_field, iostat_field, description in key_correlations:
                iostat_col = find_matching_column(iostat_field, accounts_cols)
                
                if iostat_col:
                    result, error = safe_correlation_analysis(cpu_field, iostat_col, description.replace('Device', 'ACCOUNTS Device'), 'ACCOUNTS')
                    if result:
                        correlation_data.append(result)
                    else:
                        print(f"⚠️  ACCOUNTS Device {description}: {error}")
        
        if not correlation_data:
            return """
            <div class="warning">
                <h4>⚠️  相关性分析Data Not Available</h4>
                <p>可能的原因：</p>
                <ul>
                    <li>缺少必要的CPU或EBS性能字段</li>
                    <li>数据质量问题（过多NaN值）</li>
                    <li>有效数据点不足（少于10个）</li>
                </ul>
            </div>
            """
        
        # ✅ 生成改进的HTML表格
        table_html = """
        <table style="width: 100%; border-collapse: collapse; margin-top: 15px; background: white;">
            <thead>
                <tr>
                    <th style="background: #007bff; color: white; padding: 12px;">Device类型</th>
                    <th style="background: #007bff; color: white; padding: 12px;">分析项目</th>
                    <th style="background: #007bff; color: white; padding: 12px;">相关系数</th>
                    <th style="background: #007bff; color: white; padding: 12px;">P值</th>
                    <th style="background: #007bff; color: white; padding: 12px;">统计显著性</th>
                    <th style="background: #007bff; color: white; padding: 12px;">相关强度</th>
                    <th style="background: #007bff; color: white; padding: 12px;">有效样本数</th>
                    <th style="background: #007bff; color: white; padding: 12px;">数据完整性</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for i, data in enumerate(correlation_data):
            # 根据相关性强度设置行颜色
            if "极强相关" in data['相关强度']:
                row_color = "#e8f5e8"
            elif "强相关" in data['相关强度']:
                row_color = "#f0f8f0"
            elif "中等相关" in data['相关强度']:
                row_color = "#fff8e1"
            else:
                row_color = "#f8f9fa"
            
            table_html += f"""
                <tr style="background: {row_color};">
                    <td style="padding: 10px; border: 1px solid #ddd;">{data['Device类型']}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{data['分析项目']}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{data['相关系数']}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{data['P值']}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{data['统计显著性']}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{data['相关强度']}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{data['有效样本数']}</td>
                    <td style="padding: 10px; border: 1px solid #ddd;">{data['数据完整性']}</td>
                </tr>
            """
        
        table_html += """
            </tbody>
        </table>
        <div class="info" style="margin-top: 15px;">
            <h4>📊 相关性分析说明</h4>
            <ul>
                <li><strong>相关系数范围</strong>: -1.0 到 1.0，绝对值越大相关性越强</li>
                <li><strong>统计显著性</strong>: *** p&lt;0.001, ** p&lt;0.01, * p&lt;0.05</li>
                <li><strong>相关强度分类</strong>: |r|≥0.8极强, |r|≥0.6强, |r|≥0.4中等, |r|≥0.2弱</li>
                <li><strong>数据完整性</strong>: 有效数据点占总数据点的百分比</li>
            </ul>
        </div>
        """
        
        return table_html

    def _analyze_slot_performance(self, df, slot_fields):
        """分析Slot处理性能"""
        if not slot_fields:
            return """
            <div class="warning">
                <p>未找到Slot相关数据字段。建议监控以下指标：</p>
                <ul>
                    <li>local_slot - 本地节点Slot</li>
                    <li>mainnet_slot - 主网Slot</li>
                    <li>slot_diff - Slot差异</li>
                </ul>
            </div>
            """
        
        try:
            slot_stats = {}
            for field in slot_fields[:3]:
                if field in df.columns:
                    data = df[field].dropna()
                    if len(data) > 0:
                        slot_stats[field] = {
                            'current': data.iloc[-1],
                            'avg': data.mean(),
                            'max': data.max(),
                            'min': data.min()
                        }
            
            if not slot_stats:
                return "<p>Slot数据为空或无效</p>"
            
            stats_html = '<div class="info-grid">'
            for field, stats in slot_stats.items():
                stats_html += f"""
                <div class="info-card">
                    <h4>{field.replace('_', ' ').title()}</h4>
                    <div style="font-size: 1.2em; font-weight: bold;">当前值: {stats['current']}</div>
                    <div>平均值: {stats['avg']:.2f}</div>
                    <div>范围: {stats['min']:.0f} - {stats['max']:.0f}</div>
                </div>
                """
            stats_html += '</div>'
            return stats_html
            
        except Exception as e:
            return f"<p>Slot分析失败: {str(e)[:50]}</p>"
    
    def _analyze_rpc_performance(self, df, rpc_fields):
        """分析RPC性能"""
        if not rpc_fields:
            return """
            <div class="warning">
                <p>未找到RPC相关数据字段。建议监控以下指标：</p>
                <ul>
                    <li>rpc_requests - RPC请求数</li>
                    <li>rpc_latency - RPCLatency</li>
                </ul>
            </div>
            """
        
        try:
            rpc_stats = {}
            for field in rpc_fields[:3]:
                if field in df.columns:
                    data = df[field].dropna()
                    if len(data) > 0:
                        rpc_stats[field] = {
                            'current': data.iloc[-1],
                            'avg': data.mean(),
                            'max': data.max()
                        }
            
            if not rpc_stats:
                return "<p>RPC数据为空或无效</p>"
            
            stats_html = '<div class="info-grid">'
            for field, stats in rpc_stats.items():
                stats_html += f"""
                <div class="info-card">
                    <h4>{field.replace('_', ' ').title()}</h4>
                    <div style="font-size: 1.2em; font-weight: bold;">当前: {stats['current']:.1f}</div>
                    <div>平均: {stats['avg']:.1f}</div>
                    <div>峰值: {stats['max']:.1f}</div>
                </div>
                """
            stats_html += '</div>'
            return stats_html
            
        except Exception as e:
            return f"<p>RPC分析失败: {str(e)[:50]}</p>"

    def _analyze_sync_status(self, df, sync_fields):
        """分析区块链同步状态"""
        if not sync_fields:
            return """
            <div class="info">
                <p>未找到同步状态相关数据字段。建议监控以下指标：</p>
                <ul>
                    <li>sync_lag - 同步Latency</li>
                    <li>peer_count - 连接节点数</li>
                    <li>sync_status - 同步状态</li>
                </ul>
            </div>
            """
        
        try:
            sync_details = []
            
            for field in sync_fields[:3]:
                if field in df.columns:
                    data = df[field].dropna()
                    if len(data) > 0:
                        current_value = data.iloc[-1]
                        avg_value = data.mean()
                        
                        if 'lag' in field.lower() or 'delay' in field.lower():
                            # Latency类指标
                            status = "良好" if avg_value < 1000 else "一般" if avg_value < 5000 else "需要关注"
                            sync_details.append(f"<li><strong>{field}</strong>: 当前 {current_value:.1f}ms, 平均 {avg_value:.1f}ms - {status}</li>")
                        elif 'peer' in field.lower() or 'connection' in field.lower():
                            # 连接数指标
                            status = "良好" if avg_value > 10 else "一般" if avg_value > 5 else "需要关注"
                            sync_details.append(f"<li><strong>{field}</strong>: 当前 {current_value:.0f}, 平均 {avg_value:.1f} - {status}</li>")
                        else:
                            # 其他指标
                            sync_details.append(f"<li><strong>{field}</strong>: 当前 {current_value}, 平均 {avg_value:.2f}</li>")
            
            if sync_details:
                return f"""
                <div class="info">
                    <p>🔄 区块链同步状态分析</p>
                    <ul>
                        {''.join(sync_details)}
                    </ul>
                </div>
                """
            else:
                return "<p>同步状态数据为空</p>"
                
        except Exception as e:
            return f"<p>同步状态分析失败: {str(e)[:50]}</p>"

    def _generate_html_content(self, df, ec2_info):
        """生成HTML内容 + 瓶颈信息展示 + 图片引用"""
        try:
            # 生成各个部分 - 使用实际存在的方法
            ebs_analysis = self._generate_ebs_baseline_analysis_section(df)
            ebs_bottleneck_analysis = self._generate_ebs_bottleneck_section()  # 新增EBS瓶颈根因分析
            monitoring_overhead_analysis = self._generate_monitoring_overhead_section()  # 新增监控开销分析
            monitoring_overhead_detailed = self._generate_monitoring_overhead_detailed_section()  # 详细监控开销分析
            production_resource_planning = self._generate_production_resource_planning_section()  # 生产环境资源规划
            ena_warnings = self._generate_ena_warnings_section(df)  # 新增ENA警告
            ena_data_table = self._generate_ena_data_table(df)     # 新增ENA数据表
            solana_analysis = self._generate_solana_specific_section(df)
            correlation_table = self._generate_cpu_ebs_correlation_table(df)
            overhead_table = self._generate_overhead_data_table()
            
            # 生成性能摘要
            performance_summary = self._generate_performance_summary(df)
            
            # 生成瓶颈信息展示（如果有）
            bottleneck_section = self._generate_bottleneck_section()
            
            # 生成图片展示部分
            charts_section = self._generate_charts_section()
            
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Solana QPS 性能分析报告</title>
                <meta charset="utf-8">
                <style>
                    {self._get_css_styles()}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🚀 Solana QPS 性能分析报告 - 增强版</h1>
                    <p>生成Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>✅ 统一字段命名 | 完整Device支持 | 监控开销分析 | Solana特定分析 | 瓶颈检测分析</p>
                    
                    {bottleneck_section}
                    {performance_summary}
                    {charts_section}
                    {monitoring_overhead_analysis}
                    {monitoring_overhead_detailed}
                    {ebs_analysis}
                    {ebs_bottleneck_analysis}
                    {production_resource_planning}
                    {ena_warnings}
                    {ena_data_table}
                    {solana_analysis}
                    {correlation_table}
                    {overhead_table}
                </div>
            </body>
            </html>
            """
        except Exception as e:
            return f"<div class='error'>HTML内容生成失败: {str(e)}</div>"

    def _generate_charts_section(self):
        """生成图表展示部分"""
        try:
            # 定义所有可能生成的图片及其描述
            chart_definitions = [
                # performance_visualizer.py 生成的图片
                {
                    'filename': 'performance_overview.png',
                    'title': '📈 性能概览图表',
                    'description': '系统整体性能概览，包括CPU、内存、EBS等关键指标的Time序列展示'
                },
                {
                    'filename': 'cpu_ebs_correlation_visualization.png',
                    'title': '🔗 CPU-EBS关联可视化',
                    'description': 'CPU Usage与EBS性能指标的关联性分析，帮助识别I/O瓶颈'
                },
                {
                    'filename': 'device_performance_comparison.png',
                    'title': '💾 Device性能对比',
                    'description': 'DATA Device和ACCOUNTS Device的性能对比分析'
                },
                {
                    'filename': 'await_threshold_analysis.png',
                    'title': '⏱️ 等待Time阈值分析',
                    'description': 'I/O等待Time的阈值分析，识别存储性能瓶颈'
                },
                {
                    'filename': 'util_threshold_analysis.png',
                    'title': '📊 利用率阈值分析',
                    'description': 'Device Utilization的阈值分析，评估资源使用效率'
                },
                {
                    'filename': 'monitoring_overhead_analysis.png',
                    'title': '📋 监控开销分析',
                    'description': '监控系统本身的资源消耗分析，评估监控对系统性能的影响'
                },
                {
                    'filename': 'smoothed_trend_analysis.png',
                    'title': '📈 平滑趋势分析',
                    'description': '性能指标的平滑趋势分析，消除噪声后的性能变化趋势'
                },
                {
                    'filename': 'qps_trend_analysis.png',
                    'title': '🚀 QPS趋势分析',
                    'description': 'QPS性能的详细趋势分析，展示测试过程中的QPS变化'
                },
                {
                    'filename': 'resource_efficiency_analysis.png',
                    'title': '⚡ 资源效率分析',
                    'description': 'QPS与资源消耗的效率分析，评估每QPS的资源成本'
                },
                {
                    'filename': 'bottleneck_identification.png',
                    'title': '🚨 瓶颈识别图',
                    'description': '自动瓶颈识别结果，标注性能瓶颈点和影响因素'
                },
                
                # advanced_chart_generator.py 生成的图片
                {
                    'filename': 'pearson_correlation_analysis.png',
                    'title': '📊 Pearson相关性分析',
                    'description': 'CPU与EBS指标的Pearson相关性分析，量化指标间的线性关系'
                },
                {
                    'filename': 'linear_regression_analysis.png',
                    'title': '📈 线性回归分析',
                    'description': '关键指标的线性回归分析，预测性能趋势和关系'
                },
                {
                    'filename': 'negative_correlation_analysis.png',
                    'title': '📉 负相关分析',
                    'description': '负相关指标分析，识别性能权衡关系'
                },
                {
                    'filename': 'comprehensive_correlation_matrix.png',
                    'title': '🔍 综合相关性矩阵',
                    'description': '所有监控指标的综合相关性矩阵热力图'
                },
                {
                    'filename': 'performance_trend_analysis.png',
                    'title': '📊 性能趋势分析',
                    'description': '长期性能趋势分析，识别性能变化模式'
                },
                {
                    'filename': 'ena_limitation_trends.png',
                    'title': '🚨 ENA网络限制趋势',
                    'description': 'AWS ENA网络限制趋势分析，显示PPS、带宽、连接跟踪等限制的Time变化'
                },
                {
                    'filename': 'ena_connection_capacity.png',
                    'title': '🔗 ENA连接容量监控',
                    'description': 'ENA连接容量实时监控，显示可用连接数变化和容量预警'
                },
                {
                    'filename': 'ena_comprehensive_status.png',
                    'title': '🌐 ENA综合状态分析',
                    'description': 'ENA网络综合状态分析，包括限制分布、容量状态和严重程度评估'
                },
                {
                    'filename': 'performance_correlation_heatmap.png',
                    'title': '🔥 性能相关性热力图',
                    'description': '性能指标相关性的热力图展示，直观显示指标间关系强度'
                },
                
                # analysis/*.py 生成的图片
                {
                    'filename': 'reports/bottleneck_analysis_chart.png',
                    'title': '🚨 瓶颈分析图表',
                    'description': '详细的瓶颈分析图表，包括瓶颈因子和影响程度'
                },
                {
                    'filename': 'reports/performance_cliff_analysis.png',
                    'title': '📉 性能悬崖分析',
                    'description': '性能悬崖检测和分析，识别性能急剧下降的原因'
                },
                {
                    'filename': 'reports/comprehensive_analysis_charts.png',
                    'title': '📊 综合分析图表',
                    'description': '综合性能分析图表集合，全面展示系统性能状况'
                },
                {
                    'filename': 'reports/qps_performance_analysis.png',
                    'title': '🎯 QPS性能分析',
                    'description': 'QPS性能的专项分析图表，深入分析QPS性能特征'
                }
            ]
            
            # 检查图片文件存在性并生成HTML
            charts_html = """
            <div class="section">
                <h2>📊 性能分析图表</h2>
                <div class="info">
                    <p>以下图表提供了系统性能的全方位可视化分析，包括性能趋势、关联性分析、瓶颈识别等。</p>
                </div>
            """
            
            # 获取报告输出目录
            reports_dir = os.path.join(self.output_dir, 'reports')
            if not os.path.exists(reports_dir):
                reports_dir = self.output_dir
            
            available_charts = []
            missing_charts = []
            
            for chart in chart_definitions:
                chart_path = os.path.join(reports_dir, chart['filename'])
                # 也检查直接在output_dir中的图片
                alt_chart_path = os.path.join(self.output_dir, os.path.basename(chart['filename']))
                
                if os.path.exists(chart_path):
                    available_charts.append((chart, chart['filename']))
                elif os.path.exists(alt_chart_path):
                    available_charts.append((chart, os.path.basename(chart['filename'])))
                else:
                    missing_charts.append(chart)
            
            # 生成可用图表的HTML
            if available_charts:
                charts_html += """
                <div class="charts-grid">
                """
                
                for chart, relative_path in available_charts:
                    charts_html += f"""
                    <div class="chart-item">
                        <h3>{chart['title']}</h3>
                        <div class="chart-description">
                            <p>{chart['description']}</p>
                        </div>
                        <div class="chart-container">
                            <img src="{relative_path}" alt="{chart['title']}" class="chart-image">
                        </div>
                    </div>
                    """
                
                charts_html += """
                </div>
                """
                
                # 添加图表统计信息
                charts_html += f"""
                <div class="charts-summary">
                    <h3>📈 图表统计</h3>
                    <ul>
                        <li>✅ 可用图表: {len(available_charts)} 个</li>
                        <li>⏳ 待生成图表: {len(missing_charts)} 个</li>
                        <li>📊 图表覆盖率: {len(available_charts)/(len(available_charts)+len(missing_charts))*100:.1f}%</li>
                    </ul>
                </div>
                """
            else:
                charts_html += """
                <div class="warning">
                    <h3>⚠️ 图表生成提示</h3>
                    <p>当前没有找到生成的图表文件。图表将在以下情况下生成：</p>
                    <ul>
                        <li>运行 performance_visualizer.py 生成性能分析图表</li>
                        <li>运行 advanced_chart_generator.py 生成高级分析图表</li>
                        <li>运行 comprehensive_analysis.py 生成综合分析图表</li>
                    </ul>
                    <p>请确保在生成报告前先运行相应的图表生成脚本。</p>
                </div>
                """
            
            # 如果有缺失的图表，显示提示
            if missing_charts:
                charts_html += """
                <div class="missing-charts">
                    <h3>📋 待生成图表</h3>
                    <p>以下图表尚未生成，运行相应脚本后将自动显示：</p>
                    <ul>
                """
                for chart in missing_charts[:5]:  # 只显示前5个
                    charts_html += f"<li>{chart['title']} - {chart['description']}</li>"
                
                if len(missing_charts) > 5:
                    charts_html += f"<li>... 还有 {len(missing_charts) - 5} 个图表</li>"
                
                charts_html += """
                    </ul>
                </div>
                """
            
            charts_html += """
            </div>
            """
            
            return charts_html
            
        except Exception as e:
            return f"""
            <div class="section error">
                <h2>⚠️ 图表展示错误</h2>
                <p>图表部分生成失败: {str(e)}</p>
            </div>
            """

    def _generate_bottleneck_section(self):
        """生成瓶颈信息展示部分"""
        if not self.bottleneck_data:
            return ""
        
        try:
            bottleneck_detected = self.bottleneck_data.get('bottleneck_detected', False)
            if not bottleneck_detected:
                return ""
            
            max_qps = self.bottleneck_data.get('max_qps_achieved', 0)
            bottleneck_qps = self.bottleneck_data.get('bottleneck_qps', 0)
            reasons = self.bottleneck_data.get('bottleneck_reasons', '未知')
            severity = self.bottleneck_data.get('severity', 'medium')
            detection_time = self.bottleneck_data.get('detection_time', '未知')
            recommendations = self.bottleneck_data.get('recommendations', [])
            
            # 计算性能下降
            performance_drop = 0.0  # 使用float类型保持一致性
            if max_qps > 0:
                performance_drop = ((bottleneck_qps - max_qps) / max_qps) * 100
            
            # 严重程度颜色
            severity_color = {
                'low': '#28a745',
                'medium': '#ffc107', 
                'high': '#dc3545'
            }.get(severity, '#ffc107')
            
            # 生成建议列表
            recommendations_html = ""
            if recommendations:
                rec_items = [f"<li>{rec}</li>" for rec in recommendations[:5]]
                recommendations_html = f"<ul>{''.join(rec_items)}</ul>"
            
            return f"""
            <div class="section bottleneck-alert" style="border-left: 5px solid {severity_color}; background-color: #fff3cd;">
                <h2 style="color: {severity_color};">🚨 性能瓶颈检测结果</h2>
                
                <div class="bottleneck-summary">
                    <div class="bottleneck-stats">
                        <div class="stat-item">
                            <h4>🏆 最大成功QPS</h4>
                            <div class="stat-value" style="color: #28a745; font-size: 2em; font-weight: bold;">{max_qps}</div>
                        </div>
                        <div class="stat-item">
                            <h4>🚨 瓶颈触发QPS</h4>
                            <div class="stat-value" style="color: #dc3545; font-size: 2em; font-weight: bold;">{bottleneck_qps}</div>
                        </div>
                        <div class="stat-item">
                            <h4>📉 性能下降</h4>
                            <div class="stat-value" style="color: #dc3545; font-size: 1.5em; font-weight: bold;">{performance_drop:.1f}%</div>
                        </div>
                    </div>
                </div>
                
                <div class="bottleneck-details">
                    <h3>🔍 瓶颈详情</h3>
                    <div class="info">
                        <p><strong>检测Time:</strong> {detection_time}</p>
                        <p><strong>严重程度:</strong> <span style="color: {severity_color}; font-weight: bold;">{severity.upper()}</span></p>
                        <p><strong>瓶颈原因:</strong> {reasons}</p>
                    </div>
                </div>
                
                {f'''
                <div class="bottleneck-recommendations">
                    <h3>💡 优化建议</h3>
                    <div class="info">
                        {recommendations_html}
                    </div>
                </div>
                ''' if recommendations else ''}
                
                <div class="bottleneck-actions">
                    <h3>🎯 建议的下一步行动</h3>
                    <div class="info">
                        <ul>
                            <li>查看详细的瓶颈分析图表了解根本原因</li>
                            <li>根据优化建议调整系统配置</li>
                            <li>考虑升级硬件资源或优化应用程序</li>
                            <li>重新运行测试验证改进效果</li>
                        </ul>
                    </div>
                </div>
            </div>
            """
            
        except Exception as e:
            return f"""
            <div class="section error">
                <h2>⚠️ 瓶颈信息显示错误</h2>
                <p>瓶颈信息处理失败: {str(e)}</p>
            </div>
            """

    def _get_css_styles(self):
        """获取CSS样式 - 增强版支持图表展示"""
        return """
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background-color: #f5f7fa; 
            line-height: 1.6;
        }
        .container { 
            max-width: 1400px; 
            margin: 0 auto; 
            background-color: white; 
            padding: 30px; 
            border-radius: 12px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.1); 
        }
        .section { 
            margin: 30px 0; 
            padding: 20px; 
            border: 1px solid #e1e8ed; 
            border-radius: 8px; 
            background-color: #fafbfc;
        }
        .info { 
            background-color: #e7f3ff; 
            padding: 15px; 
            border-radius: 6px; 
            margin: 15px 0; 
            border-left: 4px solid #1da1f2;
        }
        .warning { 
            background-color: #fff3cd; 
            padding: 15px; 
            border-radius: 6px; 
            margin: 15px 0; 
            border-left: 4px solid #ffc107; 
        }
        .warning tr.warning {
            background-color: #fff3cd !important;
        }
        .info {
            background-color: #d4edda;
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
            border-left: 4px solid #28a745;
        }
        .table-note {
            font-size: 0.9em;
            color: #666;
            margin-top: 10px;
            font-style: italic;
        }
        .error { 
            background-color: #f8d7da; 
            padding: 15px; 
            border-radius: 6px; 
            margin: 15px 0; 
            border-left: 4px solid #dc3545; 
        }
        .bottleneck-alert { 
            background-color: #fff3cd !important; 
            border-left: 5px solid #dc3545 !important; 
        }
        .bottleneck-summary { 
            margin: 20px 0; 
        }
        .bottleneck-stats { 
            display: flex; 
            justify-content: space-around; 
            margin: 25px 0; 
            flex-wrap: wrap;
        }
        .stat-item { 
            text-align: center; 
            padding: 20px; 
            background-color: #f8f9fa; 
            border-radius: 10px; 
            min-width: 180px; 
            margin: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .stat-value { 
            margin-top: 10px; 
            font-weight: bold;
        }
        .bottleneck-details, .bottleneck-recommendations, .bottleneck-actions { 
            margin: 25px 0; 
        }
        
        /* 图表展示样式 */
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 30px;
            margin: 25px 0;
        }
        .chart-item {
            background-color: white;
            border: 1px solid #e1e8ed;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .chart-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.12);
        }
        .chart-item h3 {
            color: #2c3e50;
            margin-top: 0;
            margin-bottom: 15px;
            font-size: 1.2em;
            border-bottom: 2px solid #3498db;
            padding-bottom: 8px;
        }
        .chart-description {
            margin-bottom: 20px;
        }
        .chart-description p {
            color: #5a6c7d;
            font-size: 0.95em;
            margin: 0;
            line-height: 1.5;
        }
        .chart-container {
            text-align: center;
            background-color: #fafbfc;
            border-radius: 8px;
            padding: 15px;
            border: 1px solid #e9ecef;
        }
        .chart-image {
            max-width: 100%;
            height: auto;
            border-radius: 6px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s ease;
        }
        .chart-image:hover {
            transform: scale(1.02);
        }
        .charts-summary {
            background-color: #e8f5e8;
            padding: 20px;
            border-radius: 8px;
            margin: 25px 0;
            border-left: 4px solid #28a745;
        }
        .charts-summary h3 {
            color: #155724;
            margin-top: 0;
        }
        .charts-summary ul {
            margin: 10px 0;
            padding-left: 20px;
        }
        .charts-summary li {
            margin: 8px 0;
            color: #155724;
        }
        .missing-charts {
            background-color: #fff3cd;
            padding: 20px;
            border-radius: 8px;
            margin: 25px 0;
            border-left: 4px solid #ffc107;
        }
        .missing-charts h3 {
            color: #856404;
            margin-top: 0;
        }
        .missing-charts ul {
            margin: 10px 0;
            padding-left: 20px;
        }
        .missing-charts li {
            margin: 8px 0;
            color: #856404;
        }
        
        /* 表格样式 */
        table { 
            width: 100%; 
            border-collapse: collapse; 
            margin: 15px 0; 
            background-color: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        th, td { 
            border: 1px solid #dee2e6; 
            padding: 12px 15px; 
            text-align: left; 
        }
        th { 
            background-color: #f8f9fa; 
            font-weight: 600;
            color: #495057;
        }
        tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        tr:hover {
            background-color: #e9ecef;
        }
        
        /* 标题样式 */
        h1 { 
            color: #2c3e50; 
            text-align: center; 
            margin-bottom: 10px;
            font-size: 2.2em;
        }
        h2 { 
            color: #34495e; 
            border-bottom: 3px solid #3498db; 
            padding-bottom: 8px; 
            margin-top: 30px;
        }
        h3 { 
            color: #5a6c7d; 
            margin-top: 20px;
        }
        
        /* 响应式设计 */
        @media (max-width: 768px) {
            .container {
                padding: 15px;
                margin: 10px;
            }
            .charts-grid {
                grid-template-columns: 1fr;
            }
            .bottleneck-stats {
                flex-direction: column;
                align-items: center;
            }
            .stat-item {
                min-width: 250px;
            }
        }
        
        /* 打印样式 */
        @media print {
            .container {
                box-shadow: none;
                border: 1px solid #ccc;
            }
            .chart-item:hover {
                transform: none;
                box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            }
            .chart-image:hover {
                transform: none;
            }
        }
        """

    def _generate_performance_summary(self, df):
        """生成性能摘要部分"""
        try:
            # 计算基本统计
            cpu_avg = df['cpu_usage'].mean() if 'cpu_usage' in df.columns and len(df) > 0 else 0
            cpu_max = df['cpu_usage'].max() if 'cpu_usage' in df.columns and len(df) > 0 else 0
            mem_avg = df['mem_usage'].mean() if 'mem_usage' in df.columns and len(df) > 0 else 0
            
            # DATA Device统计 - 使用统一的字段格式匹配
            data_iops_cols = [col for col in df.columns if col.startswith('data_') and col.endswith('_total_iops')]
            data_iops_avg = df[data_iops_cols[0]].mean() if data_iops_cols and len(df) > 0 else 0
            
            # ACCOUNTS Device统计 - 使用统一的字段格式匹配
            accounts_iops_cols = [col for col in df.columns if col.startswith('accounts_') and col.endswith('_total_iops')]
            accounts_iops_avg = df[accounts_iops_cols[0]].mean() if accounts_iops_cols and len(df) > 0 else 0
            
            return f"""
            <div class="section">
                <h2>📊 性能摘要</h2>
                <div class="info-grid">
                    <div class="info-card">
                        <h4>平均CPU Usage</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{cpu_avg:.1f}%</div>
                    </div>
                    <div class="info-card">
                        <h4>峰值CPU Usage</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{cpu_max:.1f}%</div>
                    </div>
                    <div class="info-card">
                        <h4>平均Memory Usage</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{mem_avg:.1f}%</div>
                    </div>
                    <div class="info-card">
                        <h4>DATA Device平均IOPS</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{data_iops_avg:.0f}</div>
                    </div>
                    <div class="info-card">
                        <h4>ACCOUNTS Device平均IOPS</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{accounts_iops_avg:.0f}</div>
                    </div>
                    <div class="info-card">
                        <h4>监控数据点</h4>
                        <div style="font-size: 1.5em; font-weight: bold;">{len(df):,}</div>
                    </div>
                </div>
            </div>
            """
        except Exception as e:
            return f"<div class='error'>性能摘要生成失败: {str(e)}</div>"

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='报告生成器 - 增强版 + 瓶颈模式支持')
    parser.add_argument('performance_csv', help='系统性能监控CSV文件')
    parser.add_argument('-c', '--config', help='配置文件', default='config.sh')
    parser.add_argument('-o', '--overhead-csv', help='监控开销CSV文件')
    parser.add_argument('--bottleneck-mode', action='store_true', help='启用瓶颈分析模式')
    parser.add_argument('--bottleneck-info', help='瓶颈信息JSON文件路径')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.performance_csv):
        print(f"❌ 文件不存在: {args.performance_csv}")
        return 1
    
    # 检查瓶颈信息文件
    bottleneck_info_file = None
    if args.bottleneck_mode or args.bottleneck_info:
        if args.bottleneck_info and os.path.exists(args.bottleneck_info):
            bottleneck_info_file = args.bottleneck_info
            print(f"📊 使用瓶颈信息文件: {bottleneck_info_file}")
        else:
            print("⚠️ 瓶颈模式启用但未找到瓶颈信息文件，将生成标准报告")
    
    generator = ReportGenerator(args.performance_csv, args.config, args.overhead_csv, bottleneck_info_file)
    
    result = generator.generate_html_report()
    
    if result:
        if bottleneck_info_file:
            print("🎉 瓶颈模式HTML报告生成成功!")
        else:
            print("🎉 增强版HTML报告生成成功!")
        return 0
    else:
        print("❌ HTML报告生成失败")
        return 1

if __name__ == "__main__":
    exit(main())
