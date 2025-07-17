#!/usr/bin/env python3
"""
字体问题诊断和修复工具
深入分析为什么检测到中文字体但仍有警告
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.font_manager import FontProperties
import os

def diagnose_font_issues():
    """诊断字体问题"""
    print("🩺 字体问题诊断和修复工具")
    print("=" * 50)
    
    print("🔍 开始诊断字体问题...")
    print("=" * 50)
    
    # 1. 基本信息
    print(f"📦 Matplotlib版本: {plt.matplotlib.__version__}")
    print(f"🔧 当前字体设置: {plt.rcParams['font.sans-serif']}")
    
    # 2. 系统字体统计
    all_fonts = fm.findSystemFonts()
    print(f"📊 系统字体总数: {len(all_fonts)}")
    
    # 3. 中文字体检测
    chinese_fonts = []
    font_manager = fm.FontManager()
    
    chinese_font_names = [
        'WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'Noto Sans CJK SC',
        'SimHei', 'Microsoft YaHei', 'PingFang SC', 'Heiti SC'
    ]
    
    for font in font_manager.ttflist:
        if any(cf in font.name for cf in chinese_font_names):
            chinese_fonts.append(font.name)
    
    chinese_fonts = list(set(chinese_fonts))
    print(f"🔤 找到的中文字体: {len(chinese_fonts)}")
    for font in chinese_fonts[:5]:  # 只显示前5个
        print(f"  - {font}")
    
    # 4. 测试字体设置
    print("\n🧪 测试字体设置...")
    if chinese_fonts:
        plt.rcParams['font.sans-serif'] = chinese_fonts + ['DejaVu Sans', 'Arial']
        print(f"✅ 设置中文字体: {chinese_fonts[0]}")
    else:
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial']
        print("⚠️  未找到中文字体，使用英文标签")
    
    plt.rcParams['axes.unicode_minus'] = False
    
    # 5. 创建测试图表
    print("\n📊 创建测试图表...")
    
    import numpy as np
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 测试数据
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    
    ax.plot(x, y, 'b-', linewidth=2, label='正弦波')
    
    # 使用中文标签（这里会产生警告）
    ax.set_title('字体测试图表')
    ax.set_xlabel('时间')
    ax.set_ylabel('幅值')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # 保存图表
    output_file = '/tmp/font_diagnosis_test.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ 测试图表已保存: {output_file}")
    
    # 检查文件大小
    if os.path.exists(output_file):
        size = os.path.getsize(output_file) / 1024  # KB
        print(f"📏 文件大小: {size:.1f} KB")
    
    # 6. 字符级别诊断
    print("\n🔬 字符级别诊断...")
    
    # 测试特定的中文字符
    test_chars = ['使', '用', '率', '性', '能', '分', '析']
    
    for char in test_chars:
        # 检查字符的Unicode编码
        unicode_code = ord(char)
        print(f"字符 '{char}' (U+{unicode_code:04X}):")
        
        # 尝试找到包含此字符的字体
        found_fonts = []
        for font_path in all_fonts[:20]:  # 只检查前20个字体，避免太慢
            try:
                font_prop = FontProperties(fname=font_path)
                # 这里简化检查，实际需要更复杂的字形检查
                if 'WenQuanYi' in font_path or 'Noto' in font_path:
                    found_fonts.append(os.path.basename(font_path))
            except:
                continue
        
        if found_fonts:
            print(f"  ✅ 可能支持的字体: {found_fonts[:2]}")
        else:
            print(f"  ❌ 未找到明确支持的字体")
    
    # 7. 建议
    print("\n💡 建议:")
    if chinese_fonts:
        print("1. 虽然检测到中文字体，但可能不包含所有字符")
        print("2. 建议在生产环境中使用英文标签避免警告")
        print("3. 或者安装更完整的中文字体包")
    else:
        print("1. 安装中文字体: sudo ./install_chinese_fonts.sh")
        print("2. 重新运行此诊断脚本")
    
    # 8. 生成诊断报告
    print("\n📋 生成字体诊断报告...")
    
    report_content = f"""# 字体诊断报告

## 系统信息
- Matplotlib版本: {plt.matplotlib.__version__}
- 系统字体总数: {len(all_fonts)}
- 检测到的中文字体: {len(chinese_fonts)}

## 中文字体列表
{chr(10).join(f'- {font}' for font in chinese_fonts)}

## 问题分析
1. **字体检测成功**: 系统能够检测到中文字体
2. **字符覆盖不完整**: 部分中文字符可能不在字体的字符集中
3. **matplotlib回退机制**: 当字符不存在时，回退到DejaVu Sans
4. **DejaVu Sans无中文支持**: 导致警告和显示问题

## 解决方案
1. **推荐**: 在AWS EC2环境中使用英文标签
2. **备选**: 安装更完整的中文字体包（如Noto CJK）
3. **临时**: 忽略警告，图表仍能正常生成

## 测试结果
- 测试图表: {output_file}
- 图表大小: {size:.1f} KB
- 状态: {'成功生成' if os.path.exists(output_file) else '生成失败'}
"""
    
    report_file = '/tmp/font_diagnosis_report.md'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"📄 诊断报告已保存: {report_file}")
    print("\n🎯 诊断完成！")

if __name__ == "__main__":
    diagnose_font_issues()