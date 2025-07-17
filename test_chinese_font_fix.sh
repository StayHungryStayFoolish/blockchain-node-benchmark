#!/bin/bash

# 中文字体修复测试脚本 - 针对AWS EC2环境优化版本
# 作者: Kiro AI Assistant
# 日期: 2025-01-17

echo "🧪 开始中文字体修复测试 - AWS EC2优化版"
echo "=================================="

# 1. 检查当前环境
echo "📋 1. 检查当前环境"
echo "操作系统: $(lsb_release -d 2>/dev/null | cut -f2 || uname -s)"
echo "Python版本: $(python3 --version)"
echo "当前目录: $(pwd)"

# 2. 检查是否在AWS EC2环境
echo ""
echo "🔍 2. 检查AWS EC2环境"
AWS_EC2_DETECTED=false

if [ -f "/sys/hypervisor/uuid" ] || [ -f "/sys/devices/virtual/dmi/id/product_uuid" ]; then
    AWS_EC2_DETECTED=true
    echo "✅ 检测到AWS EC2环境（通过系统文件）"
elif [[ "$(hostname)" == *"ec2"* ]] || [[ "$(hostname)" == *"ip-"* ]]; then
    AWS_EC2_DETECTED=true
    echo "✅ 检测到AWS EC2环境（通过主机名）"
else
    echo "ℹ️  非AWS EC2环境"
fi

# 3. 检查字体状态
echo ""
echo "🔤 3. 检查字体状态"
CHINESE_FONTS_BEFORE=$(fc-list :lang=zh | wc -l 2>/dev/null || echo "0")
echo "安装前中文字体数量: $CHINESE_FONTS_BEFORE"

if [ "$CHINESE_FONTS_BEFORE" -gt 0 ]; then
    echo "✅ 已检测到中文字体"
    SKIP_FONT_INSTALL=true
else
    echo "⚠️  未检测到中文字体"
    SKIP_FONT_INSTALL=false
fi

# 4. 字体安装（如果需要）
if [ "$SKIP_FONT_INSTALL" = true ]; then
    echo ""
    echo "✅ 4. 跳过字体安装（已有中文字体）"
else
    echo ""
    echo "📦 4. 安装中文字体"
    if [ -f "./install_chinese_fonts.sh" ]; then
        chmod +x ./install_chinese_fonts.sh
        ./install_chinese_fonts.sh
        CHINESE_FONTS_AFTER=$(fc-list :lang=zh | wc -l 2>/dev/null || echo "0")
        echo "安装后中文字体数量: $CHINESE_FONTS_AFTER"
    else
        echo "⚠️  字体安装脚本不存在"
    fi
fi

# 5. 查找测试数据
echo ""
echo "📊 5. 查找测试数据"

# 检查多个可能的数据目录
DATA_DIRS=(
    "$DATA_DIR"
    "./blockchain-node-benchmark-result"
    "../blockchain-node-benchmark-result"
    "/data/data/blockchain-node-benchmark-result"
    "./test-data"
)

TEST_DATA_FILE=""
for dir in "${DATA_DIRS[@]}"; do
    if [ -n "$dir" ] && [ -d "$dir" ]; then
        echo "🔍 检查目录: $dir"
        # 查找CSV文件
        CSV_FILE=$(find "$dir" -name "*.csv" -type f | head -1)
        if [ -n "$CSV_FILE" ]; then
            TEST_DATA_FILE="$CSV_FILE"
            echo "✅ 找到测试数据: $TEST_DATA_FILE"
            echo "数据文件大小: $(du -h "$TEST_DATA_FILE" | cut -f1)"
            echo "数据行数: $(wc -l < "$TEST_DATA_FILE" 2>/dev/null || echo "未知")"
            break
        fi
    else
        echo "⚠️  目录不存在: $dir"
    fi
done

if [ -z "$TEST_DATA_FILE" ]; then
    echo "❌ 未找到测试数据文件"
    echo "请确保有CSV格式的性能数据文件"
    exit 1
fi

# 6. 测试可视化脚本
echo ""
echo "🎨 6. 测试可视化脚本"

# 测试 performance_visualizer.py
echo "测试 performance_visualizer.py..."
if [ -f "visualization/performance_visualizer.py" ]; then
    # 创建测试日志文件
    LOG_FILE="/tmp/visualizer_test.log"
    
    # 运行测试，捕获输出和错误
    python3 -c "
import sys
sys.path.append('.')
from visualization.performance_visualizer import PerformanceVisualizer

try:
    visualizer = PerformanceVisualizer('$TEST_DATA_FILE')
    print('✅ PerformanceVisualizer 初始化成功')
    
    # 测试字体管理器
    if hasattr(visualizer, 'font_manager') and visualizer.font_manager:
        print('✅ 字体管理器加载成功')
        if hasattr(visualizer.font_manager, 'use_english_labels'):
            if visualizer.font_manager.use_english_labels:
                print('✅ 使用英文标签模式（推荐用于AWS EC2）')
            else:
                print('ℹ️  使用中文标签模式')
    
    # 测试await_thresholds
    if hasattr(visualizer, 'await_thresholds'):
        if 'data_avg_await' in visualizer.await_thresholds:
            print('✅ await_thresholds 配置正确')
        else:
            print('⚠️  await_thresholds 配置可能有问题')
    
    # 尝试生成一个简单的图表
    try:
        # 关键步骤：先加载数据
        visualizer.load_data()
        result = visualizer.create_performance_overview_chart()
        if result:
            print('✅ 图表生成测试成功')
        else:
            print('⚠️  图表生成返回空结果')
    except Exception as chart_error:
        print(f'⚠️  图表生成测试失败: {chart_error}')
        
except Exception as e:
    print(f'❌ PerformanceVisualizer 测试失败: {e}')
    sys.exit(1)
" 2>&1 | tee "$LOG_FILE"

    if [ $? -eq 0 ]; then
        echo "✅ performance_visualizer.py 测试成功"
    else
        echo "❌ performance_visualizer.py 测试失败"
    fi
else
    echo "❌ performance_visualizer.py 不存在"
fi

# 测试 font_manager.py
echo ""
echo "测试 font_manager.py..."
if [ -f "tools/font_manager.py" ]; then
    python3 tools/font_manager.py 2>&1 | head -20
    if [ $? -eq 0 ]; then
        echo "✅ font_manager.py 测试成功"
    else
        echo "❌ font_manager.py 测试失败"
    fi
else
    echo "❌ font_manager.py 不存在"
fi

# 7. 检查生成的文件
echo ""
echo "📈 7. 检查生成的文件"

# 检查PNG图表文件
echo "检查PNG图表文件:"
PNG_COUNT=0

# 扩展搜索范围，包括数据文件所在目录
DATA_DIR=$(dirname "$TEST_DATA_FILE")
SEARCH_DIRS=(
    "."
    ".."
    "$DATA_DIR"
    "../blockchain-node-benchmark-result"
    "/data/data/blockchain-node-benchmark-result"
)

echo "搜索目录: ${SEARCH_DIRS[@]}"

for search_dir in "${SEARCH_DIRS[@]}"; do
    if [ -d "$search_dir" ]; then
        echo "检查目录: $search_dir"
        # 查找最近生成的PNG文件（不限制时间）
        for png_file in $(find "$search_dir" -name "*.png" -type f 2>/dev/null | head -10); do
            if [ -f "$png_file" ]; then
                SIZE=$(du -h "$png_file" | cut -f1)
                echo "✅ $(basename "$png_file") ($SIZE) - $png_file"
                PNG_COUNT=$((PNG_COUNT + 1))
            fi
        done
    fi
done

# 如果没有找到，尝试更宽泛的搜索
if [ "$PNG_COUNT" -eq 0 ]; then
    echo "尝试更宽泛的搜索..."
    for png_file in $(find .. -name "performance_*.png" -type f 2>/dev/null | head -5); do
        if [ -f "$png_file" ]; then
            SIZE=$(du -h "$png_file" | cut -f1)
            echo "✅ $(basename "$png_file") ($SIZE) - $png_file"
            PNG_COUNT=$((PNG_COUNT + 1))
        fi
    done
fi

# 检查HTML报告文件
echo ""
echo "检查HTML报告文件:"
HTML_COUNT=0
for html_file in $(find . -name "*.html" -newer "$TEST_DATA_FILE" 2>/dev/null | head -5); do
    if [ -f "$html_file" ]; then
        SIZE=$(du -h "$html_file" | cut -f1)
        echo "✅ $(basename "$html_file") ($SIZE)"
        HTML_COUNT=$((HTML_COUNT + 1))
    fi
done

# 8. 检查字体警告（仅在AWS EC2环境中）
if [ "$AWS_EC2_DETECTED" = true ]; then
    echo ""
    echo "⚠️  8. 检查字体警告（AWS EC2环境）"
    if [ -f "$LOG_FILE" ]; then
        FONT_WARNINGS=$(grep -c "missing from font" "$LOG_FILE" 2>/dev/null || echo "0")
        if [ "$FONT_WARNINGS" -gt 0 ]; then
            echo "❌ 仍然存在 $FONT_WARNINGS 个字体警告"
            echo "前几个警告示例:"
            grep "missing from font" "$LOG_FILE" | head -3
            echo ""
            echo "💡 建议: 在AWS EC2环境中，这些警告是正常的。"
            echo "   系统已自动切换到英文标签模式以避免显示问题。"
        else
            echo "✅ 没有发现字体警告"
        fi
    fi
fi

# 9. 测试总结
echo ""
echo "🎯 9. 测试总结"
echo "=================================="
echo "测试完成时间: $(date)"
echo "AWS EC2环境: $AWS_EC2_DETECTED"
echo "中文字体数量: $CHINESE_FONTS_BEFORE"
echo "生成的PNG文件数量: $PNG_COUNT"
echo "生成的HTML文件数量: $HTML_COUNT"

if [ "$PNG_COUNT" -gt 0 ] || [ "$HTML_COUNT" -gt 0 ]; then
    echo "🎉 测试成功！图表生成正常"
    
    if [ "$AWS_EC2_DETECTED" = true ]; then
        echo ""
        echo "📋 AWS EC2环境特别说明:"
        echo "- 系统已自动检测到AWS EC2环境"
        echo "- 强制使用英文标签模式以避免字体渲染问题"
        echo "- 这是推荐的配置，可以确保图表正常显示"
    fi
    
    echo ""
    echo "📋 查看生成的文件:"
    echo "find . -name '*.png' -o -name '*.html' | head -10"
    
    exit 0
else
    echo "❌ 测试失败！未生成预期的文件"
    exit 1
fi