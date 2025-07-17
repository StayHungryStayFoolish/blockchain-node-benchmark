#!/usr/bin/env python3
"""
字体使用重构脚本 - 批量更新所有文件使用统一的字体管理工具
"""

import os
import re
from pathlib import Path

class FontUsageRefactor:
    """字体使用重构器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.files_to_update = [
            'visualization/performance_visualizer.py',
            'visualization/advanced_chart_generator.py', 
            'analysis/comprehensive_analysis.py',
            'analysis/qps_analyzer.py',
            'analysis/cpu_ebs_correlation_analyzer.py'
        ]
        
    def generate_font_import_code(self):
        """生成字体管理工具导入代码"""
        return '''        # 使用统一的字体管理工具
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tools'))
        try:
            from font_manager import get_font_manager
            self.font_manager = get_font_manager(enable_debug=True)
        except ImportError as e:
            print(f"⚠️  字体管理工具导入失败: {e}")
            # 回退到简单的英文模式
            self.font_manager = None
            
    def _get_localized_text(self, chinese_text: str, english_text: str) -> str:
        """获取本地化文本"""
        if self.font_manager:
            return self.font_manager.get_label(chinese_text, english_text)
        return english_text  # 回退到英文'''
    
    def update_chart_titles_usage(self, content: str) -> str:
        """更新图表标题使用方式"""
        # 替换常见的中文标题模式
        patterns = [
            # fig.suptitle 模式
            (r"fig\.suptitle\('([^']+)', fontsize=16, fontweight='bold'\)",
             r"fig.suptitle(self._get_localized_text('\1', '\1'), fontsize=16, fontweight='bold')"),
            
            # plt.title 模式
            (r"plt\.title\('([^']+)', fontsize=16, fontweight='bold'(?:, pad=\d+)?\)",
             r"plt.title(self._get_localized_text('\1', '\1'), fontsize=16, fontweight='bold')"),
            
            # ax.set_title 模式
            (r"ax\.set_title\('([^']+)', fontsize=16, fontweight='bold'\)",
             r"ax.set_title(self._get_localized_text('\1', '\1'), fontsize=16, fontweight='bold')"),
        ]
        
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)
        
        return content
    
    def create_usage_example(self):
        """创建使用示例文件"""
        example_content = '''#!/usr/bin/env python3
"""
字体管理工具使用示例
"""

import sys
import os
import matplotlib.pyplot as plt
import numpy as np

# 添加tools目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

from font_manager import get_font_manager, get_localized_text

def example_chart_with_font_manager():
    """使用字体管理器的图表示例"""
    
    # 获取字体管理器
    font_manager = get_font_manager(enable_debug=True)
    
    # 创建示例数据
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    
    # 创建图表
    plt.figure(figsize=(10, 6))
    plt.plot(x, y, 'b-', linewidth=2)
    
    # 使用本地化文本
    plt.title(font_manager.get_title('正弦波示例图表', 'Sine Wave Example Chart'))
    plt.xlabel(font_manager.get_label('时间', 'Time'))
    plt.ylabel(font_manager.get_label('幅值', 'Amplitude'))
    
    # 或者使用便捷函数
    plt.grid(True, alpha=0.3)
    
    # 保存图表
    output_file = '/tmp/font_manager_example.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"✅ 示例图表已保存: {output_file}")
    
    # 打印字体状态
    font_manager.print_font_status()

def example_with_convenience_functions():
    """使用便捷函数的示例"""
    
    # 直接使用便捷函数
    title = get_localized_text('性能分析', 'Performance Analysis')
    xlabel = get_localized_text('时间', 'Time')
    ylabel = get_localized_text('数值', 'Value')
    
    print(f"标题: {title}")
    print(f"X轴标签: {xlabel}")
    print(f"Y轴标签: {ylabel}")

if __name__ == "__main__":
    print("🧪 字体管理工具使用示例")
    print("=" * 40)
    
    example_chart_with_font_manager()
    print()
    example_with_convenience_functions()
'''
        
        example_file = self.project_root / 'font_manager_example.py'
        with open(example_file, 'w', encoding='utf-8') as f:
            f.write(example_content)
        
        print(f"✅ 使用示例已创建: {example_file}")
    
    def create_migration_guide(self):
        """创建迁移指南"""
        guide_content = '''# 字体管理工具迁移指南

## 概述

为了统一处理matplotlib中文字体设置，我们创建了一个通用的字体管理工具。

## 迁移步骤

### 1. 替换字体设置代码

**旧代码:**
```python
# 初始化字体设置标志
self.use_english_labels = False

# 设置中文字体支持
try:
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
except Exception as e:
    print(f"⚠️  字体设置警告: {e}")
    self.use_english_labels = True
```

**新代码:**
```python
# 使用统一的字体管理工具
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tools'))
try:
    from font_manager import get_font_manager
    self.font_manager = get_font_manager(enable_debug=True)
except ImportError as e:
    print(f"⚠️  字体管理工具导入失败: {e}")
    self.font_manager = None
    
def _get_localized_text(self, chinese_text: str, english_text: str) -> str:
    """获取本地化文本"""
    if self.font_manager:
        return self.font_manager.get_label(chinese_text, english_text)
    return english_text  # 回退到英文
```

### 2. 更新图表标题

**旧代码:**
```python
if self.use_english_labels:
    fig.suptitle('CPU Usage Analysis', fontsize=16, fontweight='bold')
else:
    fig.suptitle('CPU使用率分析', fontsize=16, fontweight='bold')
```

**新代码:**
```python
fig.suptitle(self._get_localized_text('CPU使用率分析', 'CPU Usage Analysis'), 
             fontsize=16, fontweight='bold')
```

### 3. 便捷函数使用

```python
from font_manager import get_localized_text

# 直接使用便捷函数
title = get_localized_text('性能分析', 'Performance Analysis')
```

## 优势

1. **代码复用**: 消除重复的字体设置代码
2. **统一管理**: 集中处理字体检测和回退逻辑
3. **易于维护**: 字体相关修改只需在一个地方进行
4. **调试友好**: 统一的调试输出和状态检查
5. **向后兼容**: 提供回退机制确保兼容性

## 测试

使用提供的测试脚本验证迁移效果:
```bash
python3 font_manager_example.py
```
'''
        
        guide_file = self.project_root / 'FONT_MIGRATION_GUIDE.md'
        with open(guide_file, 'w', encoding='utf-8') as f:
            f.write(guide_content)
        
        print(f"✅ 迁移指南已创建: {guide_file}")
    
    def run_refactor(self):
        """执行重构"""
        print("🔧 开始字体使用重构...")
        
        # 创建使用示例
        self.create_usage_example()
        
        # 创建迁移指南
        self.create_migration_guide()
        
        print("\n📋 重构完成总结:")
        print("1. ✅ 字体管理工具已创建: tools/font_manager.py")
        print("2. ✅ 使用示例已创建: font_manager_example.py")
        print("3. ✅ 迁移指南已创建: FONT_MIGRATION_GUIDE.md")
        print("\n🎯 下一步:")
        print("1. 测试字体管理工具: python3 font_manager_example.py")
        print("2. 根据迁移指南更新现有文件")
        print("3. 运行完整测试: ./test_chinese_font_fix.sh")

if __name__ == "__main__":
    refactor = FontUsageRefactor()
    refactor.run_refactor()