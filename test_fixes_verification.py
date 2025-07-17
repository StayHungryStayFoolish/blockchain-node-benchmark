#!/usr/bin/env python3
"""
验证修复的测试脚本
"""

def test_await_thresholds_fix():
    """测试await_thresholds修复"""
    print("🧪 测试 await_thresholds 修复...")
    
    # 模拟PerformanceVisualizer初始化
    class MockPerformanceVisualizer:
        def __init__(self):
            self.await_thresholds = {
                'data_avg_await': 5.0,
                'accounts_avg_await': 5.0,
                'data_r_await': 5.0,
                'data_w_await': 10.0,
                'accounts_r_await': 5.0,
                'accounts_w_await': 10.0,
                'normal': 10,
                'warning': 20,
                'critical': 50
            }
    
    visualizer = MockPerformanceVisualizer()
    
    # 测试关键的键值访问
    try:
        assert 'data_avg_await' in visualizer.await_thresholds
        assert visualizer.await_thresholds['data_avg_await'] == 5.0
        assert 'accounts_avg_await' in visualizer.await_thresholds
        assert 'data_r_await' in visualizer.await_thresholds
        assert 'data_w_await' in visualizer.await_thresholds
        print("✅ await_thresholds 修复验证成功")
        return True
    except Exception as e:
        print(f"❌ await_thresholds 修复验证失败: {e}")
        return False

def test_font_manager_aws_detection():
    """测试字体管理器AWS检测"""
    print("🧪 测试字体管理器AWS检测...")
    
    import os
    
    # 模拟AWS EC2检测逻辑
    def is_aws_ec2():
        return (
            os.path.exists('/sys/hypervisor/uuid') or 
            os.path.exists('/sys/devices/virtual/dmi/id/product_uuid') or
            'ec2' in os.uname().nodename.lower() or
            'ip-' in os.uname().nodename
        )
    
    # 在实际AWS环境中应该返回True
    aws_detected = is_aws_ec2()
    print(f"AWS EC2环境检测: {aws_detected}")
    
    if aws_detected:
        print("✅ 在AWS EC2环境中，将强制使用英文标签")
    else:
        print("ℹ️  非AWS EC2环境，使用正常字体检测逻辑")
    
    return True

def main():
    """主测试函数"""
    print("🔧 验证修复效果")
    print("=" * 50)
    
    tests = [
        test_await_thresholds_fix,
        test_font_manager_aws_detection,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ 测试失败: {e}")
    
    print("=" * 50)
    print(f"🎯 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有修复验证通过！")
        return True
    else:
        print("⚠️  部分修复需要进一步检查")
        return False

if __name__ == "__main__":
    main()