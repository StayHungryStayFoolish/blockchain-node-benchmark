#!/usr/bin/env python3
"""
字体问题诊断和修复脚本
专门用于解决AWS EC2环境中matplotlib中文字体显示问题
"""

import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import os
import sys

def diagnose_font_issues():
    """诊断字体问题"""
    print("🔍 开始诊断字体问题...")
    print("=" * 50)
    
    # 1. 检查matplotlib版本
    print(f"📦 Matplotlib版本: {matplotlib.__version__}")
    
    # 2. 检查当前字体设置
    print(f"🔧 当前字体设置: {plt.rcParams['font.sans-serif']}")
    
    # 3. 列出所有可用字体
    fonts = [f.name for f in fm.fontManager.ttflist]
    print(f"📊 系统字体总数: {len(fonts)}")
    
    # 4. 查找中文字体
    chinese_fonts = []
    target_fonts = ['WenQuanYi', 'Noto', 'SimHei', 'Microsoft YaHei', 'PingFang', 'Heiti']
    
    for font in fonts:
        for target in target_fonts:
            if target in font:
                chinese_fonts.append(font)
                break
    
    print(f"🔤 找到的中文字体: {len(chinese_fonts)}")
    for font in chinese_fonts[:10]:  # 只显示前10个
        print(f"  - {font}")
    
    # 5. 测试字体设置
    print("\n🧪 测试字体设置...")
    
    if chinese_fonts:
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = chinese_fonts + ['DejaVu Sans', 'Arial', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False
        
        print("✅ 已设置中文字体")
        print(f"📝 字体优先级: {plt.rcParams['font.sans-serif'][:3]}")
        
        # 创建测试图表
        create_test_chart(use_chinese=True)
    else:
        print("⚠️  未找到中文字体，使用英文标签")
        create_test_chart(use_chinese=False)
    
    return chinese_fonts

def create_test_chart(use_chinese=True):
    """创建测试图表"""
    print("\n📊 创建测试图表...")
    
    try:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        # 测试数据
        x = np.linspace(0, 10, 100)
        y1 = np.sin(x)
        y2 = np.cos(x)
        
        # 图表1
        ax1.plot(x, y1, 'b-', linewidth=2, label='正弦波' if use_chinese else 'Sine Wave')
        ax1.set_title('正弦函数图' if use_chinese else 'Sine Function')
        ax1.set_xlabel('时间' if use_chinese else 'Time')
        ax1.set_ylabel('幅值' if use_chinese else 'Amplitude')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 图表2
        ax2.plot(x, y2, 'r-', linewidth=2, label='余弦波' if use_chinese else 'Cosine Wave')
        ax2.set_title('余弦函数图' if use_chinese else 'Cosine Function')
        ax2.set_xlabel('时间' if use_chinese else 'Time')
        ax2.set_ylabel('幅值' if use_chinese else 'Amplitude')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 主标题
        fig.suptitle('字体测试图表 - Font Test Chart', fontsize=16, fontweight='bold')
        
        plt.tight_layout()
        
        # 保存图表
        output_file = '/tmp/font_diagnosis_test.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ 测试图表已保存: {output_file}")
        
        # 检查文件大小
        if os.path.exists(output_file):
            size = os.path.getsize(output_file)
            print(f"📏 文件大小: {size/1024:.1f} KB")
        
        return True
        
    except Exception as e:
        print(f"❌ 图表生成失败: {e}")
        return False

def fix_font_issues():
    """修复字体问题"""
    print("\n🔧 开始修复字体问题...")
    
    try:
        # 1. 清除matplotlib缓存
        cache_dir = matplotlib.get_cachedir()
        print(f"📁 缓存目录: {cache_dir}")
        
        if os.path.exists(cache_dir):
            import shutil
            shutil.rmtree(cache_dir, ignore_errors=True)
            print("🧹 已清除matplotlib缓存")
        
        # 2. 重新初始化字体管理器
        fm.fontManager.__init__()
        print("🔄 已重新初始化字体管理器")
        
        # 3. 强制重新加载字体
        plt.rcdefaults()
        
        # 4. 重新检测字体
        fonts = [f.name for f in fm.fontManager.ttflist]
        chinese_fonts = []
        target_fonts = ['WenQuanYi', 'Noto', 'SimHei', 'Microsoft YaHei', 'PingFang', 'Heiti']
        
        for font in fonts:
            for target in target_fonts:
                if target in font:
                    chinese_fonts.append(font)
                    break
        
        if chinese_fonts:
            # 设置优化的字体列表
            font_list = chinese_fonts + ['DejaVu Sans', 'Arial', 'sans-serif']
            plt.rcParams['font.sans-serif'] = font_list
            plt.rcParams['axes.unicode_minus'] = False
            
            print(f"✅ 已设置优化字体列表: {font_list[:3]}...")
            
            # 再次测试
            success = create_test_chart(use_chinese=True)
            if success:
                print("🎉 字体问题修复成功！")
                return True
            else:
                print("⚠️  修复后仍有问题，建议使用英文标签")
                return False
        else:
            print("⚠️  系统中没有中文字体，建议运行 install_chinese_fonts.sh")
            return False
            
    except Exception as e:
        print(f"❌ 修复过程出错: {e}")
        return False

def generate_font_report():
    """生成字体诊断报告"""
    print("\n📋 生成字体诊断报告...")
    
    report_content = f"""# 字体诊断报告

## 系统信息
- 操作系统: {os.uname().sysname} {os.uname().release}
- Python版本: {sys.version}
- Matplotlib版本: {matplotlib.__version__}

## 字体检测结果
"""
    
    # 检测字体
    fonts = [f.name for f in fm.fontManager.ttflist]
    chinese_fonts = []
    target_fonts = ['WenQuanYi', 'Noto', 'SimHei', 'Microsoft YaHei', 'PingFang', 'Heiti']
    
    for font in fonts:
        for target in target_fonts:
            if target in font:
                chinese_fonts.append(font)
                break
    
    report_content += f"""
- 系统字体总数: {len(fonts)}
- 中文字体数量: {len(chinese_fonts)}
- 当前字体设置: {plt.rcParams['font.sans-serif']}

## 中文字体列表
"""
    
    for font in chinese_fonts:
        report_content += f"- {font}\n"
    
    report_content += f"""
## 建议
"""
    
    if chinese_fonts:
        report_content += "✅ 系统已安装中文字体，建议使用字体管理工具进行优化设置。\n"
    else:
        report_content += "⚠️  系统未安装中文字体，建议运行 `sudo ./install_chinese_fonts.sh` 安装中文字体。\n"
    
    # 保存报告
    report_file = '/tmp/font_diagnosis_report.md'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"📄 诊断报告已保存: {report_file}")
    return report_file

def main():
    """主函数"""
    print("🩺 字体问题诊断和修复工具")
    print("=" * 50)
    
    # 1. 诊断字体问题
    chinese_fonts = diagnose_font_issues()
    
    # 2. 尝试修复
    if chinese_fonts:
        fix_success = fix_font_issues()
        if not fix_success:
            print("\n💡 建议:")
            print("1. 确保已安装中文字体: sudo ./install_chinese_fonts.sh")
            print("2. 使用字体管理工具: python3 tools/font_manager.py")
            print("3. 如果问题持续，可以使用英文标签模式")
    else:
        print("\n💡 建议:")
        print("1. 安装中文字体: sudo ./install_chinese_fonts.sh")
        print("2. 重新运行此诊断脚本")
    
    # 3. 生成报告
    generate_font_report()
    
    print("\n🎯 诊断完成！")

if __name__ == "__main__":
    main()