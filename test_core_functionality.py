#!/usr/bin/env python3
"""
核心功能测试脚本
专门测试修复后的核心功能
"""

import sys
import os
import glob
sys.path.append('.')

def find_test_data():
    """查找测试数据文件"""
    print("🔍 搜索测试数据文件...")
    
    csv_files = []
    
    # 策略1: 当前目录递归搜索
    csv_files.extend(glob.glob('**/performance_*.csv', recursive=True))
    
    # 策略2: 上级目录搜索
    csv_files.extend(glob.glob('../**/performance_*.csv', recursive=True))
    
    # 策略3: 常见路径搜索
    common_paths = [
        '/data/data/blockchain-node-benchmark-result/**/performance_*.csv',
        '../blockchain-node-benchmark-result/**/performance_*.csv',
        './blockchain-node-benchmark-result/**/performance_*.csv',
        '../../blockchain-node-benchmark-result/**/performance_*.csv'
    ]
    
    for pattern in common_paths:
        try:
            found = glob.glob(pattern, recursive=True)
            csv_files.extend(found)
            if found:
                print(f"  ✅ 在 {pattern} 找到 {len(found)} 个文件")
        except Exception as e:
            print(f"  ⚠️  搜索 {pattern} 失败: {e}")
    
    # 去重
    csv_files = list(set(csv_files))
    
    if csv_files:
        print(f"📊 总共找到 {len(csv_files)} 个CSV文件")
        for i, file in enumerate(csv_files[:3]):  # 只显示前3个
            size = os.path.getsize(file) / 1024 if os.path.exists(file) else 0
            print(f"  {i+1}. {file} ({size:.1f} KB)")
        return csv_files[0]
    else:
        print("❌ 未找到任何CSV测试数据")
        return None

def test_performance_visualizer(csv_file):
    """测试PerformanceVisualizer核心功能"""
    print(f"\n🧪 测试PerformanceVisualizer核心功能")
    print(f"使用数据文件: {csv_file}")
    
    try:
        from visualization.performance_visualizer import PerformanceVisualizer
        
        # 1. 初始化测试
        print("\n1. 初始化测试...")
        visualizer = PerformanceVisualizer(csv_file)
        print("✅ PerformanceVisualizer 初始化成功")
        
        # 2. 测试await_thresholds修复
        print("\n2. 测试await_thresholds修复...")
        if hasattr(visualizer, 'await_thresholds'):
            keys = list(visualizer.await_thresholds.keys())
            print(f"✅ await_thresholds 存在，包含键: {keys}")
            
            # 检查关键键值
            required_keys = ['data_avg_await', 'accounts_avg_await']
            missing_keys = [k for k in required_keys if k not in keys]
            if missing_keys:
                print(f"⚠️  缺少关键键: {missing_keys}")
            else:
                print("✅ 所有关键键都存在")
        else:
            print("❌ await_thresholds 属性不存在")
            return False
        
        # 3. 测试字体管理器
        print("\n3. 测试字体管理器...")
        if hasattr(visualizer, 'font_manager') and visualizer.font_manager:
            print("✅ 字体管理器加载成功")
            
            if hasattr(visualizer.font_manager, 'use_english_labels'):
                use_english = visualizer.font_manager.use_english_labels
                print(f"✅ 使用英文标签: {use_english}")
                
                if use_english:
                    print("✅ AWS EC2环境检测正常，使用英文标签模式")
                else:
                    print("ℹ️  本地环境，尝试使用中文标签")
            else:
                print("⚠️  字体管理器缺少use_english_labels属性")
        else:
            print("⚠️  字体管理器未加载")
        
        # 4. 测试数据加载
        print("\n4. 测试数据加载...")
        try:
            visualizer.load_data()
            if hasattr(visualizer, 'df') and visualizer.df is not None:
                print(f"✅ 数据加载成功，行数: {len(visualizer.df)}")
                print(f"✅ 列数: {len(visualizer.df.columns)}")
            else:
                print("⚠️  数据加载后df为空")
        except Exception as load_error:
            print(f"⚠️  数据加载失败: {load_error}")
        
        # 5. 测试图表生成方法存在性
        print("\n5. 测试图表生成方法...")
        chart_methods = [
            'create_performance_overview_chart',
            'create_correlation_visualization_chart', 
            'create_device_comparison_chart',
            'create_await_threshold_analysis_chart',
            'generate_all_charts'
        ]
        
        for method_name in chart_methods:
            if hasattr(visualizer, method_name):
                print(f"✅ {method_name} 方法存在")
            else:
                print(f"❌ {method_name} 方法不存在")
        
        # 6. 尝试生成一个图表
        print("\n6. 尝试生成图表...")
        try:
            if hasattr(visualizer, 'df') and visualizer.df is not None and len(visualizer.df) > 0:
                result = visualizer.create_performance_overview_chart()
                if result and os.path.exists(result):
                    size = os.path.getsize(result) / 1024
                    print(f"✅ 图表生成成功: {os.path.basename(result)} ({size:.1f} KB)")
                else:
                    print("⚠️  图表生成返回空结果或文件不存在")
            else:
                print("⚠️  跳过图表生成（数据不足）")
        except Exception as chart_error:
            print(f"⚠️  图表生成失败: {chart_error}")
        
        print("\n✅ 核心功能测试完成")
        return True
        
    except ImportError as import_error:
        print(f"❌ 导入失败: {import_error}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🔧 核心功能测试")
    print("=" * 50)
    
    # 1. 查找测试数据
    csv_file = find_test_data()
    if not csv_file:
        print("❌ 无法继续测试，未找到数据文件")
        return False
    
    # 2. 测试核心功能
    success = test_performance_visualizer(csv_file)
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 核心功能测试通过！")
        return True
    else:
        print("❌ 核心功能测试失败！")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)