#!/usr/bin/env python3
"""
调试数据加载问题
"""

import sys
import os
sys.path.append('.')

def debug_load_data():
    """调试数据加载问题"""
    print("🔍 调试数据加载问题")
    print("=" * 50)
    
    # 1. 查找CSV文件
    csv_file = None
    for root, dirs, files in os.walk('..'):
        for file in files:
            if 'performance_' in file and file.endswith('.csv'):
                csv_file = os.path.join(root, file)
                break
        if csv_file:
            break
    
    if not csv_file:
        print("❌ 未找到CSV文件")
        return
    
    print(f"📊 使用CSV文件: {csv_file}")
    print(f"📏 文件大小: {os.path.getsize(csv_file)} bytes")
    
    # 2. 测试直接pandas读取
    print("\n🧪 测试直接pandas读取...")
    try:
        import pandas as pd
        df = pd.read_csv(csv_file)
        print(f"✅ 直接读取成功: {len(df)} 行, {len(df.columns)} 列")
        print(f"📋 列名: {list(df.columns)[:5]}...")
    except Exception as e:
        print(f"❌ 直接读取失败: {e}")
        return
    
    # 3. 测试CSVDataProcessor
    print("\n🧪 测试CSVDataProcessor...")
    try:
        from utils.csv_data_processor import CSVDataProcessor
        processor = CSVDataProcessor()
        success = processor.load_csv_data(csv_file)
        print(f"✅ CSVDataProcessor加载: {success}")
        if processor.df is not None:
            print(f"✅ 数据框存在: {len(processor.df)} 行")
        else:
            print("❌ 数据框为None")
    except Exception as e:
        print(f"❌ CSVDataProcessor测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. 测试PerformanceVisualizer初始化
    print("\n🧪 测试PerformanceVisualizer初始化...")
    try:
        from visualization.performance_visualizer import PerformanceVisualizer
        visualizer = PerformanceVisualizer(csv_file)
        print("✅ PerformanceVisualizer初始化成功")
        
        # 检查初始状态
        print(f"📊 初始df状态: {type(visualizer.df)}")
        
        # 测试load_data
        print("\n🧪 测试load_data方法...")
        success = visualizer.load_data()
        print(f"✅ load_data返回: {success}")
        print(f"📊 加载后df状态: {type(visualizer.df)}")
        
        if visualizer.df is not None:
            print(f"✅ 数据加载成功: {len(visualizer.df)} 行")
            
            # 测试图表生成
            print("\n🧪 测试图表生成...")
            result = visualizer.create_performance_overview_chart()
            if result:
                print(f"✅ 图表生成成功: {result}")
            else:
                print("❌ 图表生成失败")
        else:
            print("❌ 数据加载后df仍为None")
            
    except Exception as e:
        print(f"❌ PerformanceVisualizer测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_load_data()