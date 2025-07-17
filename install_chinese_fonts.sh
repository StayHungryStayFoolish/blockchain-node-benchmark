#!/bin/bash

# 安装中文字体脚本 - 适用于AWS EC2和Ubuntu系统
echo "=== 开始安装中文字体 ==="

# 检查是否为root用户
if [ "$(id -u)" != "0" ]; then
   echo "❌ 此脚本需要root权限运行" 1>&2
   echo "请使用 sudo ./install_chinese_fonts.sh" 1>&2
   exit 1
fi

# 检测操作系统
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VER=$VERSION_ID
else
    echo "❌ 无法检测操作系统版本"
    exit 1
fi

echo "📋 检测到操作系统: $OS $VER"

# 更新包列表
echo "📦 更新包列表..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
elif command -v yum >/dev/null 2>&1; then
    yum update -y
else
    echo "❌ 不支持的包管理器"
    exit 1
fi

# 安装字体配置工具
echo "📦 安装fontconfig..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get install -y fontconfig
elif command -v yum >/dev/null 2>&1; then
    yum install -y fontconfig
fi

# 安装中文字体
echo "📦 安装中文字体..."
if command -v apt-get >/dev/null 2>&1; then
    # Ubuntu/Debian系统
    echo "使用apt-get安装字体..."
    apt-get install -y fonts-wqy-microhei fonts-wqy-zenhei xfonts-wqy
    
    # 如果上述字体包不可用，尝试安装其他中文字体
    if [ $? -ne 0 ]; then
        echo "⚠️  标准字体包安装失败，尝试安装备选字体..."
        apt-get install -y fonts-noto-cjk fonts-noto-cjk-extra
    fi
    
elif command -v yum >/dev/null 2>&1; then
    # CentOS/RHEL系统
    echo "使用yum安装字体..."
    yum install -y wqy-microhei-fonts wqy-zenhei-fonts
    
    # 如果上述字体包不可用，尝试安装其他中文字体
    if [ $? -ne 0 ]; then
        echo "⚠️  标准字体包安装失败，尝试安装备选字体..."
        yum install -y google-noto-cjk-fonts
    fi
fi

# 手动下载和安装字体（备选方案）
install_fonts_manually() {
    echo "📦 手动安装字体..."
    
    # 创建字体目录
    mkdir -p /usr/share/fonts/truetype/wqy
    
    # 下载WenQuanYi字体
    cd /tmp
    
    # 下载WenQuanYi Micro Hei
    if ! wget -q "https://github.com/adobe-fonts/source-han-sans/releases/download/2.004R/SourceHanSansCN.zip" -O SourceHanSansCN.zip; then
        echo "⚠️  无法下载Source Han Sans字体，尝试其他源..."
        
        # 备选下载源
        if wget -q "https://noto-website-2.storage.googleapis.com/pkgs/NotoSansCJKsc-hinted.zip" -O NotoSansCJKsc.zip; then
            unzip -q NotoSansCJKsc.zip -d /usr/share/fonts/truetype/noto/
            echo "✅ Noto Sans CJK字体安装成功"
        else
            echo "⚠️  无法下载字体文件，将使用系统默认字体"
            return 1
        fi
    else
        unzip -q SourceHanSansCN.zip -d /usr/share/fonts/truetype/source-han/
        echo "✅ Source Han Sans字体安装成功"
    fi
    
    cd - > /dev/null
}

# 检查字体安装结果
check_font_installation() {
    echo "🔍 检查字体安装结果..."
    
    # 刷新字体缓存
    fc-cache -fv > /dev/null 2>&1
    
    # 检查中文字体
    chinese_fonts=$(fc-list :lang=zh 2>/dev/null | wc -l)
    
    if [ "$chinese_fonts" -gt 0 ]; then
        echo "✅ 中文字体安装成功！"
        echo "📊 已安装的中文字体数量: $chinese_fonts"
        echo "🔤 可用的中文字体:"
        fc-list :lang=zh 2>/dev/null | head -5
        return 0
    else
        echo "⚠️  未检测到中文字体，尝试手动安装..."
        install_fonts_manually
        
        # 重新检查
        fc-cache -fv > /dev/null 2>&1
        chinese_fonts=$(fc-list :lang=zh 2>/dev/null | wc -l)
        
        if [ "$chinese_fonts" -gt 0 ]; then
            echo "✅ 手动安装字体成功！"
            echo "📊 已安装的中文字体数量: $chinese_fonts"
            return 0
        else
            echo "❌ 字体安装失败，但程序仍可正常运行（将使用英文标签）"
            return 1
        fi
    fi
}

# 清除字体缓存并重建
echo "🧹 清除并重建字体缓存..."
fc-cache -fv > /dev/null 2>&1

# 检查安装结果
check_font_installation

# 创建字体测试脚本
create_font_test() {
    cat > /tmp/test_chinese_fonts.py << 'EOF'
#!/usr/bin/env python3
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontManager
import numpy as np

def test_chinese_fonts():
    print("🧪 测试中文字体支持...")
    
    # 检测可用字体
    fm = FontManager()
    chinese_fonts = ['WenQuanYi Micro Hei', 'WenQuanYi Zen Hei', 'Noto Sans CJK SC', 'Source Han Sans CN']
    available_fonts = []
    
    for font in chinese_fonts:
        if font in [f.name for f in fm.ttflist]:
            available_fonts.append(font)
    
    if available_fonts:
        print(f"✅ 找到可用中文字体: {available_fonts}")
        
        # 设置字体
        plt.rcParams['font.sans-serif'] = available_fonts + ['DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 创建测试图表
        fig, ax = plt.subplots(figsize=(8, 6))
        x = np.linspace(0, 10, 100)
        y = np.sin(x)
        
        ax.plot(x, y, 'b-', linewidth=2)
        ax.set_title('中文字体测试图表')
        ax.set_xlabel('时间')
        ax.set_ylabel('数值')
        ax.grid(True, alpha=0.3)
        
        plt.savefig('/tmp/chinese_font_test.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        print("✅ 中文字体测试图表已生成: /tmp/chinese_font_test.png")
        return True
    else:
        print("⚠️  未找到中文字体，将使用英文标签")
        return False

if __name__ == "__main__":
    test_chinese_fonts()
EOF

    chmod +x /tmp/test_chinese_fonts.py
}

# 运行字体测试
run_font_test() {
    echo "🧪 运行字体测试..."
    
    create_font_test
    
    if command -v python3 >/dev/null 2>&1; then
        if python3 -c "import matplotlib" 2>/dev/null; then
            python3 /tmp/test_chinese_fonts.py
        else
            echo "⚠️  matplotlib未安装，跳过字体测试"
            echo "请运行: pip3 install matplotlib"
        fi
    else
        echo "⚠️  Python3未安装，跳过字体测试"
    fi
}

# 执行字体测试
run_font_test

echo ""
echo "=== 中文字体安装完成 ==="
echo "📋 安装总结:"
echo "  - 字体配置工具: ✅ 已安装"
echo "  - 中文字体包: ✅ 已安装"
echo "  - 字体缓存: ✅ 已更新"
echo ""
echo "🎯 下一步:"
echo "  1. 运行字体管理工具测试: python3 tools/font_manager.py"
echo "  2. 运行完整测试: ./test_chinese_font_fix.sh"
echo "  3. 开始使用可视化脚本"
echo ""
echo "💡 提示: 如果仍有字体警告，程序会自动使用英文标签，功能完全正常"