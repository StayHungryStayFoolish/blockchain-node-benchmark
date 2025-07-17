#!/bin/bash

# 中文字体修复测试脚本
echo "🧪 开始中文字体修复测试"
echo "=================================="

# 1. 检查当前环境
echo "📋 1. 检查当前环境"
echo "操作系统: $(lsb_release -d | cut -f2)"
echo "Python版本: $(python3 --version)"
echo "当前目录: $(pwd)"

# 2. 检查字体状态
echo -e "\n🔤 2. 检查字体状态"
echo "安装前中文字体数量: $(fc-list :lang=zh 2>/dev/null | wc -l)"
if [ $(fc-list :lang=zh 2>/dev/null | wc -l) -eq 0 ]; then
    echo "⚠️  未检测到中文字体，需要安装"
    NEED_FONT_INSTALL=true
else
    echo "✅ 已检测到中文字体"
    NEED_FONT_INSTALL=false
fi

# 3. 安装字体（如果需要）
if [ "$NEED_FONT_INSTALL" = true ]; then
    echo -e "\n📦 3. 安装中文字体"
    if [ -f "./install_chinese_fonts.sh" ]; then
        echo "运行字体安装脚本..."
        sudo ./install_chinese_fonts.sh
        echo "安装后中文字体数量: $(fc-list :lang=zh 2>/dev/null | wc -l)"
    else
        echo "❌ 字体安装脚本不存在"
        exit 1
    fi
else
    echo -e "\n✅ 3. 跳过字体安装（已有中文字体）"
fi

# 4. 查找测试数据
echo -e "\n📊 4. 查找测试数据"
# 尝试多个可能的数据目录路径
POSSIBLE_DATA_DIRS=(
    "${DATA_DIR}"
    "/data/data/blockchain-node-benchmark-result"
    "~/blockchain-node-benchmark-result"
    "../blockchain-node-benchmark-result"
    "./blockchain-node-benchmark-result"
)

DATA_DIR=""
latest_csv=""

for dir in "${POSSIBLE_DATA_DIRS[@]}"; do
    # 展开波浪号
    expanded_dir=$(eval echo "$dir")
    if [ -d "$expanded_dir" ]; then
        echo "🔍 检查目录: $expanded_dir"
        csv_files=$(find "$expanded_dir" -name "*.csv" -type f 2>/dev/null)
        if [ -n "$csv_files" ]; then
            DATA_DIR="$expanded_dir"
            latest_csv=$(find "$DATA_DIR" -name "*.csv" -type f -exec ls -t {} + 2>/dev/null | head -n 1)
            echo "✅ 在 $DATA_DIR 中找到CSV文件"
            break
        else
            echo "⚠️  目录 $expanded_dir 存在但无CSV文件"
        fi
    else
        echo "⚠️  目录不存在: $expanded_dir"
    fi
done

if [ -z "$latest_csv" ]; then
    echo "❌ 未找到CSV测试数据文件"
    echo "请确保在 $DATA_DIR 目录下有CSV监控数据文件"
    exit 1
else
    echo "✅ 找到测试数据: $latest_csv"
    echo "数据文件大小: $(du -h "$latest_csv" | cut -f1)"
    echo "数据行数: $(wc -l < "$latest_csv")"
fi

# 5. 测试可视化脚本
echo -e "\n🎨 5. 测试可视化脚本"

# 测试性能可视化器
echo "测试 performance_visualizer.py..."
if python3 visualization/performance_visualizer.py "$latest_csv" 2>&1 | tee /tmp/visualizer_test.log; then
    echo "✅ performance_visualizer.py 测试成功"
else
    echo "❌ performance_visualizer.py 测试失败"
    echo "错误日志:"
    tail -10 /tmp/visualizer_test.log
fi

# 测试高级图表生成器
echo -e "\n测试 advanced_chart_generator.py..."
if python3 visualization/advanced_chart_generator.py "$latest_csv" 2>&1 | tee /tmp/advanced_test.log; then
    echo "✅ advanced_chart_generator.py 测试成功"
else
    echo "❌ advanced_chart_generator.py 测试失败"
    echo "错误日志:"
    tail -10 /tmp/advanced_test.log
fi

# 测试报告生成器
echo -e "\n测试 report_generator.py..."
if python3 visualization/report_generator.py "$latest_csv" 2>&1 | tee /tmp/report_test.log; then
    echo "✅ report_generator.py 测试成功"
else
    echo "❌ report_generator.py 测试失败"
    echo "错误日志:"
    tail -10 /tmp/report_test.log
fi

# 6. 检查生成的文件
echo -e "\n📈 6. 检查生成的文件"
output_dir=$(dirname "$latest_csv")

echo "检查PNG图表文件:"
png_files=$(find "$output_dir" -name "*.png" -mtime -1 2>/dev/null)
if [ -n "$png_files" ]; then
    echo "$png_files" | while read file; do
        echo "  ✅ $(basename "$file") ($(du -h "$file" | cut -f1))"
    done
else
    echo "  ⚠️  未找到新生成的PNG文件"
fi

echo -e "\n检查HTML报告文件:"
html_files=$(find "$output_dir" -name "*.html" -mtime -1 2>/dev/null)
if [ -n "$html_files" ]; then
    echo "$html_files" | while read file; do
        echo "  ✅ $(basename "$file") ($(du -h "$file" | cut -f1))"
    done
else
    echo "  ⚠️  未找到新生成的HTML文件"
fi

# 7. 检查字体警告
echo -e "\n⚠️  7. 检查字体警告"
if grep -q "missing from font" /tmp/visualizer_test.log /tmp/advanced_test.log /tmp/report_test.log 2>/dev/null; then
    echo "❌ 仍然存在字体警告:"
    grep "missing from font" /tmp/visualizer_test.log /tmp/advanced_test.log /tmp/report_test.log 2>/dev/null | head -3
    echo "建议: 检查字体安装是否成功，或确认英文回退机制是否正常工作"
else
    echo "✅ 未检测到字体警告，修复成功！"
fi

# 8. 测试总结
echo -e "\n🎯 8. 测试总结"
echo "=================================="
echo "测试完成时间: $(date)"
echo "中文字体数量: $(fc-list :lang=zh 2>/dev/null | wc -l)"
echo "生成的PNG文件数量: $(find "$output_dir" -name "*.png" -mtime -1 2>/dev/null | wc -l)"
echo "生成的HTML文件数量: $(find "$output_dir" -name "*.html" -mtime -1 2>/dev/null | wc -l)"

if [ $(find "$output_dir" -name "*.png" -mtime -1 2>/dev/null | wc -l) -gt 0 ]; then
    echo "🎉 测试成功！图表生成正常"
else
    echo "⚠️  测试需要检查，图表生成可能有问题"
fi

echo -e "\n📋 查看生成的文件:"
echo "ls -la $output_dir/*.png $output_dir/*.html 2>/dev/null"