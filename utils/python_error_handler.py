#!/usr/bin/env python3
"""
Python统一错误处理工具
为所有Python脚本提供标准化的错误处理、日志记录和恢复机制
这是一个新增的工具，不替代任何现有功能
"""

import sys
import os
from utils.unified_logger import get_logger
import traceback
import functools
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Dict, List

class FrameworkErrorHandler:
    """框架统一错误处理器"""
    
    def __init__(self, log_dir: str = None):
        # 优先使用传入的log_dir，然后尝试环境变量，最后使用默认值
        self.log_dir = (log_dir or 
                       os.environ.get('PYTHON_ERROR_LOG_DIR') or 
                       os.environ.get('LOGS_DIR', '/tmp/solana-qps-logs'))
        self.setup_logging()
        
    def setup_logging(self):
        """设置日志系统"""
        # 确保日志目录存在
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        
        # 配置日志格式
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # 创建日志文件名
        log_file = os.path.join(self.log_dir, f'python_errors_{datetime.now().strftime("%Y%m%d")}.log')
        
        # 使用统一日志管理器
        self.logger = get_logger('FrameworkErrorHandler')
        self.logger.info(f"✅ 错误处理器初始化完成，日志目录: {self.log_dir}")

    def handle_errors(self, 
                     return_default: Any = None, 
                     reraise: bool = False,
                     max_retries: int = 0,
                     retry_delay: float = 1.0):
        """
        错误处理装饰器
        
        Args:
            return_default: 发生错误时返回的默认值
            reraise: 是否重新抛出异常
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                
                for attempt in range(max_retries + 1):
                    try:
                        result = func(*args, **kwargs)
                        if attempt > 0:
                            self.logger.info(f"✅ 函数 {func.__name__} 在第 {attempt + 1} 次尝试后成功")
                        return result
                        
                    except Exception as e:
                        last_exception = e
                        error_msg = f"函数 {func.__name__} 执行失败 (尝试 {attempt + 1}/{max_retries + 1}): {str(e)}"
                        
                        if attempt < max_retries:
                            self.logger.warning(f"⚠️  {error_msg}，{retry_delay}秒后重试...")
                            time.sleep(retry_delay)
                        else:
                            self.logger.error(f"❌ {error_msg}")
                            self.logger.error(f"错误详情: {traceback.format_exc()}")
                
                # 所有重试都失败了
                if reraise and last_exception:
                    raise last_exception
                
                self.logger.warning(f"🔄 函数 {func.__name__} 返回默认值: {return_default}")
                return return_default
                
            return wrapper
        return decorator

    def safe_import(self, module_name: str, package: str = None) -> Optional[Any]:
        """安全导入模块"""
        try:
            if package:
                module = __import__(f"{package}.{module_name}", fromlist=[module_name])
            else:
                module = __import__(module_name)
            
            self.logger.info(f"✅ 成功导入模块: {module_name}")
            return module
            
        except ImportError as e:
            self.logger.warning(f"⚠️  模块导入失败: {module_name} - {str(e)}")
            return None

    def validate_file_exists(self, file_path: str, create_if_missing: bool = False) -> bool:
        """验证文件是否存在"""
        if os.path.exists(file_path):
            self.logger.info(f"✅ 文件存在: {file_path}")
            return True
        
        if create_if_missing:
            try:
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                Path(file_path).touch()
                self.logger.info(f"✅ 创建文件: {file_path}")
                return True
            except Exception as e:
                self.logger.error(f"❌ 无法创建文件 {file_path}: {str(e)}")
                return False
        
        self.logger.warning(f"⚠️  文件不存在: {file_path}")
        return False

    def validate_dataframe(self, df, required_columns: List[str] = None) -> bool:
        """验证DataFrame的有效性"""
        if df is None:
            self.logger.error("❌ DataFrame为None")
            return False
        
        if df.empty:
            self.logger.warning("⚠️  DataFrame为空")
            return False
        
        if required_columns:
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                self.logger.error(f"❌ DataFrame缺少必要列: {missing_columns}")
                return False
        
        self.logger.info(f"✅ DataFrame验证通过: {len(df)}行, {len(df.columns)}列")
        return True

    def safe_file_operation(self, operation: str, file_path: str, **kwargs) -> Any:
        """安全的文件操作"""
        try:
            if operation == 'read_csv':
                import pandas as pd
                result = pd.read_csv(file_path, **kwargs)
                self.logger.info(f"✅ 成功读取CSV: {file_path}")
                return result
                
            elif operation == 'read_json':
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                self.logger.info(f"✅ 成功读取JSON: {file_path}")
                return result
                
            elif operation == 'write_json':
                import json
                data = kwargs.get('data')
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.logger.info(f"✅ 成功写入JSON: {file_path}")
                return True
                
            else:
                self.logger.error(f"❌ 不支持的文件操作: {operation}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ 文件操作失败 ({operation}): {file_path} - {str(e)}")
            return None

    def check_system_resources(self, min_memory_mb: int = 512, min_disk_mb: int = 1024) -> bool:
        """检查系统资源"""
        try:
            import psutil
            
            # 检查内存
            memory = psutil.virtual_memory()
            available_memory_mb = memory.available / 1024 / 1024
            
            if available_memory_mb < min_memory_mb:
                self.logger.warning(f"⚠️  可用内存不足: {available_memory_mb:.0f}MB < {min_memory_mb}MB")
                return False
            
            # 检查磁盘空间
            disk = psutil.disk_usage('/')
            available_disk_mb = disk.free / 1024 / 1024
            
            if available_disk_mb < min_disk_mb:
                self.logger.warning(f"⚠️  可用磁盘空间不足: {available_disk_mb:.0f}MB < {min_disk_mb}MB")
                return False
            
            self.logger.info(f"✅ 系统资源充足: 内存 {available_memory_mb:.0f}MB, 磁盘 {available_disk_mb:.0f}MB")
            return True
            
        except ImportError:
            self.logger.warning("⚠️  psutil未安装，跳过系统资源检查")
            return True
        except Exception as e:
            self.logger.error(f"❌ 系统资源检查失败: {str(e)}")
            return False

    def create_safe_output_dir(self, base_dir: str, subdir: str = None) -> str:
        """创建安全的输出目录"""
        try:
            if subdir:
                output_dir = os.path.join(base_dir, subdir)
            else:
                output_dir = base_dir
            
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            self.logger.info(f"✅ 输出目录就绪: {output_dir}")
            return output_dir
            
        except Exception as e:
            # 如果无法创建指定目录，使用临时目录
            fallback_dir = os.path.join('/tmp', 'solana-qps-output', subdir or 'default')
            Path(fallback_dir).mkdir(parents=True, exist_ok=True)
            self.logger.warning(f"⚠️  使用备用目录: {fallback_dir} (原因: {str(e)})")
            return fallback_dir

# 全局错误处理器实例
_global_handler = None

def get_error_handler(log_dir: str = None) -> FrameworkErrorHandler:
    """获取全局错误处理器实例"""
    global _global_handler
    if _global_handler is None:
        _global_handler = FrameworkErrorHandler(log_dir)
    return _global_handler

# 便捷装饰器
def handle_errors(return_default=None, reraise=False, max_retries=0, retry_delay=1.0):
    """便捷的错误处理装饰器"""
    handler = get_error_handler()
    return handler.handle_errors(return_default, reraise, max_retries, retry_delay)

# 使用示例
if __name__ == "__main__":
    print("📋 Python错误处理工具使用示例:")
    print("")
    print("基本使用:")
    print("  from python_error_handler import handle_errors, get_error_handler")
    print("")
    print("装饰器使用:")
    print("  @handle_errors(return_default={}, max_retries=3)")
    print("  def my_function():")
    print("      # 你的代码")
    print("      pass")
    print("")
    print("手动使用:")
    print("  handler = get_error_handler()")
    print("  result = handler.safe_file_operation('read_csv', 'data.csv')")
    print("")
    
    # 演示功能
    handler = get_error_handler()
    handler.logger.info("🎯 Python错误处理工具演示完成")
