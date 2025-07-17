#!/usr/bin/env python3
"""
字体管理工具 - 统一处理matplotlib中文字体设置
解决AWS EC2环境中的中文字体显示问题
"""

import matplotlib.pyplot as plt
from typing import List, Optional
import os
import sys

class FontManager:
    """字体管理器 - 统一处理中文字体设置和回退机制"""
    
    def __init__(self, enable_debug: bool = False):
        """
        初始化字体管理器
        
        Args:
            enable_debug: 是否启用调试输出
        """
        self.enable_debug = enable_debug
        self.use_english_labels = False
        self.available_chinese_fonts = []
        
        # 预定义的中文字体列表（按优先级排序）
        self.chinese_fonts = [
            'WenQuanYi Micro Hei',    # AWS EC2上最常用
            'WenQuanYi Zen Hei',      # AWS EC2备选
            'Noto Sans CJK SC',       # Google Noto字体（简体中文）
            'Noto Sans CJK TC',       # Google Noto字体（繁体中文）
            'SimHei',                 # Windows中文字体
            'Microsoft YaHei',        # Windows现代中文字体
            'PingFang SC',            # macOS中文字体
            'Heiti SC',               # macOS备选中文字体
            'DejaVu Sans',            # 通用字体（支持部分中文）
            'Arial Unicode MS',       # 通用Unicode字体
            'sans-serif'              # 最后的系统回退
        ]
        
        # 自动设置字体
        self.setup_fonts()
    
    def _debug_print(self, message: str):
        """调试输出"""
        if self.enable_debug:
            print(f"[FontManager] {message}")
    
    def _rebuild_font_cache(self):
        """重建matplotlib字体缓存"""
        try:
            # 尝试新版本的方法
            from matplotlib.font_manager import fontManager
            fontManager.__init__()
            self._debug_print("字体缓存重建完成（新版本方法）")
        except Exception:
            try:
                # 尝试旧版本的方法
                from matplotlib.font_manager import _rebuild
                _rebuild()
                self._debug_print("字体缓存重建完成（旧版本方法）")
            except Exception as e:
                # 如果都失败，尝试手动清除缓存
                try:
                    import matplotlib as mpl
                    cache_dir = mpl.get_cachedir()
                    import shutil
                    import os
                    if os.path.exists(cache_dir):
                        shutil.rmtree(cache_dir, ignore_errors=True)
                    self._debug_print("字体缓存手动清除完成")
                except Exception as e2:
                    self._debug_print(f"字体缓存重建失败: {e}, 手动清除也失败: {e2}")
    
    def _detect_available_fonts(self) -> List[str]:
        """检测系统中可用的中文字体"""
        try:
            from matplotlib.font_manager import FontManager as MPLFontManager
            fm = MPLFontManager()
            system_font_names = set([f.name for f in fm.ttflist])
            
            # 检查哪些中文字体可用
            available = [font for font in self.chinese_fonts if font in system_font_names]
            
            self._debug_print(f"系统字体总数: {len(system_font_names)}")
            self._debug_print(f"可用中文字体: {available}")
            
            return available
            
        except Exception as e:
            self._debug_print(f"字体检测失败: {e}")
            return []
    
    def setup_fonts(self):
        """设置matplotlib中文字体支持"""
        try:
            # 1. 重建字体缓存
            self._rebuild_font_cache()
            
            # 2. 检测可用字体
            self.available_chinese_fonts = self._detect_available_fonts()
            
            # 3. 设置matplotlib字体参数 - 优化字体顺序
            if self.available_chinese_fonts:
                # 将检测到的可用字体放在最前面
                font_list = self.available_chinese_fonts + ['DejaVu Sans', 'Arial', 'sans-serif']
                plt.rcParams['font.sans-serif'] = font_list
                self._debug_print(f"设置字体列表: {font_list[:3]}...")
            else:
                # 如果没有中文字体，使用默认字体
                plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
                
            plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
            
            # 4. 强制刷新matplotlib的字体设置
            try:
                import matplotlib.pyplot as plt
                plt.rcdefaults()  # 重置为默认设置
                if self.available_chinese_fonts:
                    font_list = self.available_chinese_fonts + ['DejaVu Sans', 'Arial', 'sans-serif']
                    plt.rcParams['font.sans-serif'] = font_list
                plt.rcParams['axes.unicode_minus'] = False
            except Exception as refresh_error:
                self._debug_print(f"字体刷新失败: {refresh_error}")
            
            # 5. 判断是否需要使用英文标签
            if not self.available_chinese_fonts:
                self.use_english_labels = True
                self._debug_print("⚠️  未找到可用的中文字体，将使用英文标签")
            else:
                self.use_english_labels = False
                self._debug_print(f"✅ 找到可用的中文字体: {self.available_chinese_fonts[0]}")
                
        except Exception as e:
            self._debug_print(f"⚠️  字体设置警告: {e}")
            self.use_english_labels = True
    
    def get_label(self, chinese_text: str, english_text: str) -> str:
        """
        根据字体可用性返回合适的标签文本
        
        Args:
            chinese_text: 中文标签
            english_text: 英文标签
            
        Returns:
            合适的标签文本
        """
        return english_text if self.use_english_labels else chinese_text
    
    def get_title(self, chinese_title: str, english_title: str) -> str:
        """
        根据字体可用性返回合适的标题文本
        
        Args:
            chinese_title: 中文标题
            english_title: 英文标题
            
        Returns:
            合适的标题文本
        """
        return self.get_label(chinese_title, english_title)
    
    def is_using_english_labels(self) -> bool:
        """返回是否正在使用英文标签"""
        return self.use_english_labels
    
    def get_font_info(self) -> dict:
        """获取字体信息"""
        return {
            'use_english_labels': self.use_english_labels,
            'available_chinese_fonts': self.available_chinese_fonts,
            'configured_fonts': self.chinese_fonts,
            'current_font_family': plt.rcParams.get('font.sans-serif', [])
        }
    
    def print_font_status(self):
        """打印字体状态信息"""
        info = self.get_font_info()
        print("📝 字体管理器状态:")
        print(f"  使用英文标签: {'是' if info['use_english_labels'] else '否'}")
        print(f"  可用中文字体数量: {len(info['available_chinese_fonts'])}")
        if info['available_chinese_fonts']:
            print(f"  主要中文字体: {info['available_chinese_fonts'][0]}")
        print(f"  字体回退列表: {info['current_font_family'][:3]}...")


# 全局字体管理器实例
_global_font_manager: Optional[FontManager] = None

def get_font_manager(enable_debug: bool = False) -> FontManager:
    """
    获取全局字体管理器实例（单例模式）
    
    Args:
        enable_debug: 是否启用调试输出
        
    Returns:
        FontManager实例
    """
    global _global_font_manager
    if _global_font_manager is None:
        _global_font_manager = FontManager(enable_debug=enable_debug)
    return _global_font_manager

def setup_chinese_fonts(enable_debug: bool = False):
    """
    便捷函数：设置中文字体支持
    
    Args:
        enable_debug: 是否启用调试输出
    """
    font_manager = get_font_manager(enable_debug=enable_debug)
    return font_manager

def get_localized_text(chinese_text: str, english_text: str) -> str:
    """
    便捷函数：获取本地化文本
    
    Args:
        chinese_text: 中文文本
        english_text: 英文文本
        
    Returns:
        根据字体可用性返回的文本
    """
    font_manager = get_font_manager()
    return font_manager.get_label(chinese_text, english_text)


# 使用示例和测试代码
if __name__ == "__main__":
    print("🧪 字体管理工具测试")
    print("=" * 40)
    
    # 创建字体管理器
    fm = FontManager(enable_debug=True)
    
    # 打印状态
    fm.print_font_status()
    
    # 测试标签获取
    print("\n📝 标签测试:")
    print(f"CPU标签: {fm.get_label('CPU使用率', 'CPU Usage')}")
    print(f"内存标签: {fm.get_label('内存使用率', 'Memory Usage')}")
    print(f"标题: {fm.get_title('性能分析图表', 'Performance Analysis Chart')}")
    
    # 测试便捷函数
    print("\n🔧 便捷函数测试:")
    setup_chinese_fonts(enable_debug=True)
    print(f"本地化文本: {get_localized_text('测试文本', 'Test Text')}")
    
    # 生成测试图表
    print("\n📊 生成测试图表...")
    try:
        import numpy as np
        
        plt.figure(figsize=(8, 6))
        x = np.linspace(0, 10, 100)
        y = np.sin(x)
        
        plt.plot(x, y, 'b-', linewidth=2)
        plt.title(fm.get_title('正弦波测试图表', 'Sine Wave Test Chart'))
        plt.xlabel(fm.get_label('时间', 'Time'))
        plt.ylabel(fm.get_label('幅值', 'Amplitude'))
        plt.grid(True, alpha=0.3)
        
        test_output = '/tmp/font_manager_test.png'
        plt.savefig(test_output, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✅ 测试图表已保存: {test_output}")
        
    except Exception as e:
        print(f"❌ 测试图表生成失败: {e}")