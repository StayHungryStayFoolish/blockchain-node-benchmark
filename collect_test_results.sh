#!/bin/bash

# 测试结果收集脚本
echo "📊 收集中文字体修复测试结果"
echo "=================================="

# 创建测试结果目录
TEST_RESULTS_DIR="test_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$TEST_RESULTS_DIR"

# 1. 收集系统信息
echo "收集系统信息..."
{
    echo "# 系统信息"
    echo "操作系统: $(lsb_release -d | cut -f2)"
    echo "内核版本: $(uname -r)"
    echo "Python版本: $(python3 --version)"
    echo "测试时间: $(date)"
    echo ""
    
    echo "# 字体信息"
    echo "中文字体数量: $(fc-list :lang=zh 2>/dev/null | wc -l)"
    echo "可用中文字体:"
    fc-list :lang=zh 2>/dev/null | head -10
    echo ""
    
    echo "# Python包版本"
    python3 -c "
import matplotlib, seaborn, pandas, numpy
print(f'matplotlib: {matplotlib.__version__}')
print(f'seaborn: {seaborn.__version__}')
print(f'pandas: {pandas.__version__}')
print(f'numpy: {numpy.__version__}')
"
} > "$TEST_RESULTS_DIR/system_info.txt"

# 2. 收集生成的图表文件
echo "收集生成的图表文件..."
DATA_DIR=${DATA_DIR:-~/blockchain-node-benchmark-result}
find "$DATA_DIR" -name "*.png" -mtime -1 -exec cp {} "$TEST_RESULTS_DIR/" \; 2>/dev/null
find "$DATA_DIR" -name "*.html" -mtime -1 -exec cp {} "$TEST_RESULTS_DIR/" \; 2>/dev/null

# 3. 收集日志文件
echo "收集日志文件..."
cp /tmp/*_test.log "$TEST_RESULTS_DIR/" 2>/dev/null

# 4. 生成测试摘要
echo "生成测试摘要..."
{
    echo "# 中文字体修复测试摘要"
    echo "生成时间: $(date)"
    echo ""
    
    echo "## 文件统计"
    echo "PNG图表文件: $(ls -1 "$TEST_RESULTS_DIR"/*.png 2>/dev/null | wc -l)"
    echo "HTML报告文件: $(ls -1 "$TEST_RESULTS_DIR"/*.html 2>/dev/null | wc -l)"
    echo "日志文件: $(ls -1 "$TEST_RESULTS_DIR"/*.log 2>/dev/null | wc -l)"
    echo ""
    
    echo "## 生成的文件列表"
    ls -lh "$TEST_RESULTS_DIR"/ | grep -v "^total"
    echo ""
    
    echo "## 字体警告检查"
    if grep -q "missing from font" "$TEST_RESULTS_DIR"/*.log 2>/dev/null; then
        echo "❌ 发现字体警告:"
        grep "missing from font" "$TEST_RESULTS_DIR"/*.log 2>/dev/null | head -5
    else
        echo "✅ 未发现字体警告"
    fi
    echo ""
    
    echo "## 测试结论"
    if [ $(ls -1 "$TEST_RESULTS_DIR"/*.png 2>/dev/null | wc -l) -gt 0 ]; then
        echo "✅ 测试成功：图表生成正常"
    else
        echo "❌ 测试失败：未生成图表文件"
    fi
    
} > "$TEST_RESULTS_DIR/test_summary.md"

# 5. 创建压缩包
echo "创建测试结果压缩包..."
tar -czf "${TEST_RESULTS_DIR}.tar.gz" "$TEST_RESULTS_DIR"

echo "✅ 测试结果收集完成"
echo "结果目录: $TEST_RESULTS_DIR"
echo "压缩包: ${TEST_RESULTS_DIR}.tar.gz"
echo ""
echo "查看测试摘要:"
echo "cat $TEST_RESULTS_DIR/test_summary.md"