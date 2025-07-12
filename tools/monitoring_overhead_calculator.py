#!/usr/bin/env python3
"""
监控开销计算器 - 修复版
修复了IOPS计算逻辑和基准对比逻辑的严重错误
"""

import os
import sys
import time
import psutil
import pandas as pd
from datetime import datetime
from typing import Dict, List

class MonitoringOverheadCalculator:
    """监控开销计算器 - 修复版"""
    
    def __init__(self, logs_dir: str):
        self.logs_dir = logs_dir
        self.baseline_stats = {}
        self.overhead_log = os.path.join(logs_dir, f"monitoring_overhead_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        
    def get_monitoring_processes(self) -> List[psutil.Process]:
        """获取所有监控相关进程"""
        monitoring_keywords = [
            'iostat', 'mpstat', 'sar', 'vmstat', 'netstat',
            'unified_monitor', 'bottleneck_detector', 'ena_network_monitor',
            'performance_visualizer', 'correlation_analyzer', 'slot_monitor'
        ]
        
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                is_monitoring = any(keyword in cmdline.lower() or keyword in proc.info['name'].lower() 
                                  for keyword in monitoring_keywords)
                
                if is_monitoring and 'monitoring_overhead_calculator' not in cmdline:
                    processes.append(proc)
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        return processes
    
    def calculate_baseline_stats(self) -> Dict:
        """计算基准系统统计"""
        monitoring_procs = self.get_monitoring_processes()
        baseline_read_count = 0
        baseline_write_count = 0
        baseline_read_bytes = 0
        baseline_write_bytes = 0
        
        for proc in monitoring_procs:
            try:
                io_counters = proc.io_counters()
                baseline_read_count += io_counters.read_count
                baseline_write_count += io_counters.write_count
                baseline_read_bytes += io_counters.read_bytes
                baseline_write_bytes += io_counters.write_bytes
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return {
            'monitoring_read_count': baseline_read_count,
            'monitoring_write_count': baseline_write_count,
            'monitoring_read_bytes': baseline_read_bytes,
            'monitoring_write_bytes': baseline_write_bytes,
            'timestamp': time.time()
        }
    
    def calculate_monitoring_overhead(self) -> Dict:
        """计算监控开销 - 修复版"""
        monitoring_procs = self.get_monitoring_processes()
        
        total_cpu = 0
        total_memory_mb = 0
        total_read_count = 0
        total_write_count = 0
        total_read_bytes = 0
        total_write_bytes = 0
        
        for proc in monitoring_procs:
            try:
                total_cpu += proc.cpu_percent()
                total_memory_mb += proc.memory_info().rss / (1024 * 1024)
                
                io_counters = proc.io_counters()
                total_read_count += io_counters.read_count
                total_write_count += io_counters.write_count
                total_read_bytes += io_counters.read_bytes
                total_write_bytes += io_counters.write_bytes
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # 修复：基于实际I/O次数计算IOPS
        current_time = time.time()
        time_diff = current_time - self.baseline_stats.get('timestamp', current_time)
        
        if time_diff > 0:
            read_iops = (total_read_count - self.baseline_stats.get('monitoring_read_count', 0)) / time_diff
            write_iops = (total_write_count - self.baseline_stats.get('monitoring_write_count', 0)) / time_diff
            total_iops = read_iops + write_iops
            
            throughput_mibs = ((total_read_bytes + total_write_bytes) - 
                             (self.baseline_stats.get('monitoring_read_bytes', 0) + 
                              self.baseline_stats.get('monitoring_write_bytes', 0))) / time_diff / (1024 * 1024)
        else:
            total_iops = 0
            throughput_mibs = 0
        
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'monitoring_cpu_percent': round(total_cpu, 2),
            'monitoring_memory_mb': round(total_memory_mb, 2),
            'monitoring_iops': round(max(0, total_iops), 2),
            'monitoring_throughput_mibs': round(max(0, throughput_mibs), 4),
            'process_count': len(monitoring_procs)
        }
    
    def start_overhead_monitoring(self, interval: int = 5):
        """启动开销监控"""
        print(f"🔍 启动监控开销统计 (间隔: {interval}秒)")
        
        header = "timestamp,monitoring_cpu_percent,monitoring_memory_mb,monitoring_iops,monitoring_throughput_mibs,process_count"
        with open(self.overhead_log, 'w') as f:
            f.write(header + '\n')
        
        # 修复：只在开始时记录一次基准
        self.baseline_stats = self.calculate_baseline_stats()
        
        try:
            while True:
                overhead_stats = self.calculate_monitoring_overhead()
                
                with open(self.overhead_log, 'a') as f:
                    f.write(f"{overhead_stats['timestamp']},{overhead_stats['monitoring_cpu_percent']},"
                           f"{overhead_stats['monitoring_memory_mb']},{overhead_stats['monitoring_iops']},"
                           f"{overhead_stats['monitoring_throughput_mibs']},{overhead_stats['process_count']}\n")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print(f"\n🛑 监控开销统计已停止")
    
    def generate_overhead_report(self) -> Dict:
        """生成开销报告"""
        if not os.path.exists(self.overhead_log):
            return {"error": "监控开销数据文件不存在"}
        
        try:
            df = pd.read_csv(self.overhead_log)
            
            return {
                "avg_cpu_overhead_percent": round(df['monitoring_cpu_percent'].mean(), 2),
                "avg_memory_overhead_mb": round(df['monitoring_memory_mb'].mean(), 2),
                "avg_iops_overhead": round(df['monitoring_iops'].mean(), 2),
                "avg_throughput_overhead_mibs": round(df['monitoring_throughput_mibs'].mean(), 4),
                "sample_count": len(df)
            }
            
        except Exception as e:
            return {"error": f"生成开销报告失败: {e}"}

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 monitoring_overhead_calculator.py <logs_dir> [interval]")
        sys.exit(1)
    
    logs_dir = sys.argv[1]
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    calculator = MonitoringOverheadCalculator(logs_dir)
    calculator.start_overhead_monitoring(interval)

if __name__ == "__main__":
    main()
