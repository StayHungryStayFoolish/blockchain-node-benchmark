#!/usr/bin/env python3
"""
字体解决方案对比测试
比较传统方案 vs 我们的环境自适应方案
"""

import matplotlib.pyplot as plt
import matplotlib
from matplotlib.font_manager import FontProperties, fontManager
import warnings
import os

def test_traditional_solutions():
    """测试传统的字体解决方案"""
    print("🧪 测试传统字体解决方案")
    print("=" * 50)
    
    # 1. 检查可用字体
    print("1. 检查系统可用字体:")
    available_fonts = [font.name for font in fontManager.ttflist]
    chinese_fonts = [f for f in available_fonts if any(keyword in f for keyword in 
                    ['SimHei', 'Microsoft YaHei', 'SimSun', 'WenQuanYi', 'Noto'])]
    
    print(f"   总字体数: {len(available_fonts)}")
    print(f"   中文相关字体: {chinese_fonts[:5]}")
    
    # 2. 测试方案1：全局字体配置
    print("\n2. 测试全局字体配置:")
    
    test_fonts = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'WenQuanYi Zen Hei']
    
    for font_name in test_fonts:
        if font_name in available_fonts:
            print(f"   ✅ 尝试设置字体: {font_name}")
            matplotlib.rcParams['font.family'] = font_name
            matplotlib.rcParams['axes.unicode_minus'] = False
            
            # 测试渲染
            warnings_count = test_chinese_rendering(f"全局字体_{font_name}")
            print(f"   警告数量: {warnings_count}")
            break
        else:
            print(f"   ❌ 字体不可用: {font_name}")
    
    # 3. 测试方案2：FontProperties方案
    print("\n3. 测试FontProperties方案:")
    
    # 查找字体文件路径
    font_paths = []
    for font in fontManager.ttflist:
        if 'WenQuanYi' in font.name:
            font_paths.append(font.fname)
    
    if font_paths:
        font_path = font_paths[0]
        print(f"   ✅ 找到字体文件: {os.path.basename(font_path)}")
        warnings_count = test_fontproperties_rendering(font_path)
        print(f"   警告数量: {warnings_count}")
    else:
        print("   ❌ 未找到中文字体文件")
    
    # 4. 测试我们的环境自适应方案
    print("\n4. 测试环境自适应方案:")
    warnings_count = test_adaptive_solution()
    print(f"   警告数量: {warnings_count}")

def test_chinese_rendering(test_name):
    """测试中文渲染并统计警告"""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # 使用各种中文文本
        chinese_texts = [
            '系统性能监控', 'CPU使用率', '内存使用率', '磁盘I/O',
            '网络带宽', '响应时间', '吞吐量', '错误率'
        ]
        
        for i, text in enumerate(chinese_texts):
            ax.text(0.1, 0.9 - i*0.1, text, transform=ax.transAxes)
        
        ax.set_title('中文字体测试')
        ax.set_xlabel('时间轴')
        ax.set_ylabel('数值')
        
        plt.tight_layout()
        plt.savefig(f'/tmp/{test_name}_test.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        # 统计字体相关警告
        font_warnings = [warning for warning in w if 'missing from font' in str(warning.message)]
        return len(font_warnings)

def test_fontproperties_rendering(font_path):
    """测试FontProperties方案"""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # 创建FontProperties对象
        font_prop = FontProperties(fname=font_path, size=12)
        
        chinese_texts = [
            '系统性能监控', 'CPU使用率', '内存使用率', '磁盘I/O'
        ]
        
        for i, text in enumerate(chinese_texts):
            ax.text(0.1, 0.9 - i*0.1, text, transform=ax.transAxes, fontproperties=font_prop)
        
        ax.set_title('FontProperties测试', fontproperties=font_prop)
        ax.set_xlabel('时间轴', fontproperties=font_prop)
        ax.set_ylabel('数值', fontproperties=font_prop)
        
        plt.tight_layout()
        plt.savefig('/tmp/fontproperties_test.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        font_warnings = [warning for warning in w if 'missing from font' in str(warning.message)]
        return len(font_warnings)

def test_adaptive_solution():
    """测试我们的环境自适应方案"""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        # 检测环境
        is_aws_ec2 = (
            os.path.exists('/sys/hypervisor/uuid') or 
            'ec2' in os.uname().nodename.lower() or
            'ip-' in os.uname().nodename
        )
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        if is_aws_ec2:
            # AWS环境：使用英文标签
            texts = [
                'System Performance', 'CPU Usage', 'Memory Usage', 'Disk I/O',
                'Network Bandwidth', 'Response Time', 'Throughput', 'Error Rate'
            ]
            title = 'Performance Monitoring'
            xlabel = 'Time'
            ylabel = 'Value'
        else:
            # 本地环境：尝试中文标签
            texts = [
                '系统性能监控', 'CPU使用率', '内存使用率', '磁盘I/O',
                '网络带宽', '响应时间', '吞吐量', '错误率'
            ]
            title = '性能监控'
            xlabel = '时间轴'
            ylabel = '数值'
        
        for i, text in enumerate(texts):
            ax.text(0.1, 0.9 - i*0.1, text, transform=ax.transAxes)
        
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        
        plt.tight_layout()
        plt.savefig('/tmp/adaptive_solution_test.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        font_warnings = [warning for warning in w if 'missing from font' in str(warning.message)]
        return len(font_warnings)

def compare_solutions():
    """对比不同解决方案"""
    print("\n📊 解决方案对比总结")
    print("=" * 50)
    
    print("方案对比:")
    print("1. 传统全局配置:")
    print("   ✅ 简单易用")
    print("   ❌ 在AWS EC2中仍有字体警告")
    print("   ❌ 依赖特定字体存在")
    
    print("\n2. FontProperties方案:")
    print("   ✅ 精确控制")
    print("   ❌ 代码冗余，需要每处都设置")
    print("   ❌ 在大型项目中维护困难")
    
    print("\n3. 环境自适应方案:")
    print("   ✅ 零警告，稳定可靠")
    print("   ✅ 自动适应不同环境")
    print("   ✅ 维护简单，向后兼容")
    print("   ❌ 在AWS环境中无法显示中文")
    
    print("\n🎯 推荐:")
    print("对于生产环境（特别是AWS EC2），推荐使用环境自适应方案")
    print("对于本地开发，可以尝试传统方案获得更好的中文显示效果")

if __name__ == "__main__":
    test_traditional_solutions()
    compare_solutions()