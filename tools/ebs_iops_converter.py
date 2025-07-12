#!/usr/bin/env python3
"""
AWS EBS IOPS标准化转换工具
将实际的IOPS和I/O大小转换为AWS EBS标准的16KiB基准IOPS
"""

import subprocess
import json
from typing import Dict

class EBSIOPSConverter:
    """AWS EBS IOPS标准化转换器"""
    
    # AWS EBS IOPS基准单位
    AWS_EBS_BASELINE_IO_SIZE = 16 * 1024  # 16KiB in bytes
    
    def convert_to_ebs_standard_iops(self, actual_iops: float, actual_io_size: int) -> float:
        """
        将实际IOPS转换为AWS EBS标准的16KiB基准IOPS
        
        公式: EBS标准IOPS = 实际IOPS × (实际I/O大小 / 16KiB)
        
        Args:
            actual_iops: 实际测量的IOPS
            actual_io_size: 实际I/O大小（字节）
            
        Returns:
            转换后的EBS标准IOPS
        """
        if actual_iops <= 0:
            return 0.0
        
        # 计算I/O大小比例
        io_size_ratio = actual_io_size / self.AWS_EBS_BASELINE_IO_SIZE
        
        # 转换为EBS标准IOPS
        ebs_standard_iops = actual_iops * io_size_ratio
        
        return ebs_standard_iops
    
    def analyze_device_iops(self, device: str, actual_io_size_kb: int = 256) -> Dict:
        """
        分析设备的IOPS并转换为EBS标准
        
        Args:
            device: 设备名称（如nvme1n1）
            actual_io_size_kb: 实际I/O大小（KiB），默认256KiB
            
        Returns:
            包含原始IOPS和EBS标准IOPS的字典
        """
        try:
            # 获取当前IOPS数据
            cmd = f"iostat -x 1 2 {device}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                return {"error": f"Failed to get iostat data for {device}"}
            
            lines = result.stdout.strip().split('\n')
            device_data = None
            
            # 解析最后一次的统计数据
            for line in reversed(lines):
                if device in line and not line.startswith('Device'):
                    parts = line.split()
                    if len(parts) >= 14:
                        try:
                            device_data = {
                                'read_iops': float(parts[1]),
                                'write_iops': float(parts[2]),
                                'util_percent': float(parts[13])
                            }
                            break
                        except (ValueError, IndexError):
                            continue
            
            if not device_data:
                return {"error": f"Could not parse iostat data for {device}"}
            
            # 计算总IOPS
            total_iops = device_data['read_iops'] + device_data['write_iops']
            
            # 实际I/O大小（字节）
            actual_io_size = actual_io_size_kb * 1024
            
            # 转换为EBS标准IOPS
            ebs_standard_iops = self.convert_to_ebs_standard_iops(total_iops, actual_io_size)
            ebs_read_iops = self.convert_to_ebs_standard_iops(device_data['read_iops'], actual_io_size)
            ebs_write_iops = self.convert_to_ebs_standard_iops(device_data['write_iops'], actual_io_size)
            
            return {
                'device': device,
                'actual_io_size_kb': actual_io_size_kb,
                'aws_baseline_io_size_kb': self.AWS_EBS_BASELINE_IO_SIZE // 1024,
                'io_size_ratio': actual_io_size / self.AWS_EBS_BASELINE_IO_SIZE,
                'original_iops': {
                    'read': device_data['read_iops'],
                    'write': device_data['write_iops'],
                    'total': total_iops
                },
                'ebs_standard_iops': {
                    'read': ebs_read_iops,
                    'write': ebs_write_iops,
                    'total': ebs_standard_iops
                },
                'utilization_percent': device_data['util_percent']
            }
            
        except Exception as e:
            return {"error": f"Error analyzing {device}: {str(e)}"}
    
    def check_ebs_iops_limit(self, device: str, configured_iops: int, actual_io_size_kb: int = 256) -> Dict:
        """
        检查设备是否超过了配置的EBS IOPS限制
        
        Args:
            device: 设备名称
            configured_iops: 配置的EBS IOPS限制（基于16KiB）
            actual_io_size_kb: 实际I/O大小（KiB）
            
        Returns:
            包含限制检查结果的字典
        """
        analysis = self.analyze_device_iops(device, actual_io_size_kb)
        
        if 'error' in analysis:
            return analysis
        
        ebs_total_iops = analysis['ebs_standard_iops']['total']
        utilization_ratio = ebs_total_iops / configured_iops if configured_iops > 0 else 0
        
        return {
            **analysis,
            'configured_ebs_iops_limit': configured_iops,
            'ebs_iops_utilization_ratio': utilization_ratio,
            'ebs_iops_utilization_percent': utilization_ratio * 100,
            'is_exceeding_limit': ebs_total_iops > configured_iops,
            'available_ebs_iops': max(0, configured_iops - ebs_total_iops),
            'recommendation': self._get_recommendation(utilization_ratio)
        }
    
    def _get_recommendation(self, utilization_ratio: float) -> str:
        """生成基于IOPS使用情况的建议"""
        if utilization_ratio > 1.0:
            return f"⚠️  EBS IOPS超限 ({utilization_ratio:.1%})！建议升级到更高IOPS的EBS卷"
        elif utilization_ratio > 0.8:
            return f"⚠️  EBS IOPS使用率较高 ({utilization_ratio:.1%})，建议监控或考虑升级"
        elif utilization_ratio > 0.6:
            return f"✅ EBS IOPS使用率正常 ({utilization_ratio:.1%})"
        else:
            return f"✅ EBS IOPS使用率较低 ({utilization_ratio:.1%})，有充足余量"

def main():
    """命令行工具主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AWS EBS IOPS标准化转换工具')
    parser.add_argument('device', help='设备名称 (如: nvme1n1)')
    parser.add_argument('--configured-iops', type=int, help='配置的EBS IOPS限制')
    parser.add_argument('--io-size', type=int, default=256, help='实际I/O大小 (KiB，默认256)')
    parser.add_argument('--json', action='store_true', help='以JSON格式输出')
    
    args = parser.parse_args()
    
    converter = EBSIOPSConverter()
    
    if args.configured_iops:
        result = converter.check_ebs_iops_limit(args.device, args.configured_iops, args.io_size)
    else:
        result = converter.analyze_device_iops(args.device, args.io_size)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        # 格式化输出
        if 'error' in result:
            print(f"❌ 错误: {result['error']}")
            return
        
        print(f"📊 设备 {result['device']} 的EBS IOPS分析:")
        print(f"   实际I/O大小: {result['actual_io_size_kb']}KiB")
        print(f"   AWS基准I/O大小: {result['aws_baseline_io_size_kb']}KiB")
        print(f"   I/O大小比例: {result['io_size_ratio']:.2f}x")
        print()
        print(f"📈 原始IOPS (iostat):")
        print(f"   读取: {result['original_iops']['read']:.1f}")
        print(f"   写入: {result['original_iops']['write']:.1f}")
        print(f"   总计: {result['original_iops']['total']:.1f}")
        print()
        print(f"🎯 EBS标准IOPS (16KiB基准):")
        print(f"   读取: {result['ebs_standard_iops']['read']:.1f}")
        print(f"   写入: {result['ebs_standard_iops']['write']:.1f}")
        print(f"   总计: {result['ebs_standard_iops']['total']:.1f}")
        print()
        print(f"⚡ 磁盘利用率: {result['utilization_percent']:.1f}%")
        
        if 'configured_ebs_iops_limit' in result:
            print()
            print(f"🎯 EBS IOPS限制检查:")
            print(f"   配置限制: {result['configured_ebs_iops_limit']} IOPS")
            print(f"   当前使用: {result['ebs_standard_iops']['total']:.1f} IOPS")
            print(f"   使用率: {result['ebs_iops_utilization_percent']:.1f}%")
            print(f"   剩余可用: {result['available_ebs_iops']:.1f} IOPS")
            print(f"   建议: {result['recommendation']}")

if __name__ == "__main__":
    main()
