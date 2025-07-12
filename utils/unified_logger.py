#!/usr/bin/env python3
"""
统一日志管理器 - Python版本
============================
提供统一的Python日志配置、格式化和管理功能
解决项目中Python日志配置不统一的问题
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json

# =====================================================================
# 日志配置常量
# =====================================================================

# 日志级别映射
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

# 默认配置
DEFAULT_CONFIG = {
    'level': 'INFO',
    'format': '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
    'max_file_size': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5,
    'console_output': True,
    'file_output': True,
    'json_format': False
}

# 颜色配置
COLORS = {
    'DEBUG': '\033[0;36m',    # 青色
    'INFO': '\033[0;32m',     # 绿色
    'WARNING': '\033[0;33m',  # 黄色
    'ERROR': '\033[0;31m',    # 红色
    'CRITICAL': '\033[0;35m', # 紫色
    'RESET': '\033[0m'
}

# =====================================================================
# 自定义格式化器
# =====================================================================

class ColoredFormatter(logging.Formatter):
    """带颜色的控制台日志格式化器"""
    
    def format(self, record):
        # 添加颜色
        level_color = COLORS.get(record.levelname, COLORS['RESET'])
        record.levelname = f"{level_color}{record.levelname}{COLORS['RESET']}"
        
        # 格式化消息
        formatted = super().format(record)
        
        return formatted

class JSONFormatter(logging.Formatter):
    """JSON格式日志格式化器"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # 添加异常信息
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # 添加自定义字段
        if hasattr(record, 'component'):
            log_entry['component'] = record.component
        if hasattr(record, 'metric'):
            log_entry['metric'] = record.metric
        if hasattr(record, 'performance'):
            log_entry['performance'] = record.performance
        
        return json.dumps(log_entry, ensure_ascii=False)

# =====================================================================
# 统一日志管理器
# =====================================================================

class UnifiedLogger:
    """统一日志管理器"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """设置日志器"""
        # 清除现有处理器
        self.logger.handlers.clear()
        
        # 设置日志级别
        level = LOG_LEVELS.get(self.config['level'].upper(), logging.INFO)
        self.logger.setLevel(level)
        
        # 添加控制台处理器
        if self.config['console_output']:
            self._add_console_handler()
        
        # 添加文件处理器
        if self.config['file_output']:
            self._add_file_handler()
        
        # 防止日志传播到根日志器
        self.logger.propagate = False
    
    def _add_console_handler(self):
        """添加控制台处理器"""
        console_handler = logging.StreamHandler(sys.stdout)
        
        if self.config['json_format']:
            formatter = JSONFormatter()
        else:
            formatter = ColoredFormatter(
                fmt=self.config['format'],
                datefmt=self.config['date_format']
            )
        
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
    
    def _add_file_handler(self):
        """添加文件处理器"""
        # 获取日志文件路径
        log_file = self._get_log_file_path()
        
        # 确保日志目录存在
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建轮转文件处理器
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file),
            maxBytes=self.config['max_file_size'],
            backupCount=self.config['backup_count'],
            encoding='utf-8'
        )
        
        # 设置格式化器（文件不使用颜色）
        if self.config['json_format']:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                fmt=self.config['format'],
                datefmt=self.config['date_format']
            )
        
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
    
    def _get_log_file_path(self) -> Path:
        """获取日志文件路径"""
        # 从环境变量获取日志目录
        logs_dir = os.environ.get('LOGS_DIR', '/tmp/logs')
        
        # 生成标准化文件名
        timestamp = datetime.now().strftime('%Y%m%d')
        filename = f"{self.name}_{timestamp}.log"
        
        return Path(logs_dir) / filename
    
    # =====================================================================
    # 日志方法
    # =====================================================================
    
    def debug(self, message: str, **kwargs):
        """调试日志"""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """信息日志"""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """警告日志"""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """错误日志"""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """严重错误日志"""
        self._log(logging.CRITICAL, message, **kwargs)
    
    def _log(self, level: int, message: str, **kwargs):
        """内部日志方法"""
        # 创建日志记录
        record = self.logger.makeRecord(
            name=self.logger.name,
            level=level,
            fn='',
            lno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        
        # 添加自定义属性
        for key, value in kwargs.items():
            setattr(record, key, value)
        
        # 处理日志记录
        self.logger.handle(record)
    
    # =====================================================================
    # 特殊日志方法
    # =====================================================================
    
    def performance(self, metric: str, value: float, unit: str = '', **kwargs):
        """性能日志"""
        perf_data = {
            'metric': metric,
            'value': value,
            'unit': unit,
            **kwargs
        }
        
        message = f"PERF: {metric}={value}"
        if unit:
            message += f" {unit}"
        
        self._log(logging.INFO, message, performance=perf_data)
    
    def bottleneck(self, bottleneck_type: str, severity: str, details: str, **kwargs):
        """瓶颈日志"""
        bottleneck_data = {
            'type': bottleneck_type,
            'severity': severity,
            'details': details,
            **kwargs
        }
        
        message = f"BOTTLENECK: {bottleneck_type} (severity: {severity}) - {details}"
        self._log(logging.WARNING, message, bottleneck=bottleneck_data)
    
    def error_trace(self, error_message: str, function_name: str = '', 
                   line_number: int = 0, **kwargs):
        """错误追踪日志"""
        trace_data = {
            'error_message': error_message,
            'function': function_name,
            'line': line_number,
            **kwargs
        }
        
        message = f"ERROR_TRACE: {error_message}"
        if function_name:
            message += f" (function: {function_name}"
            if line_number:
                message += f", line: {line_number}"
            message += ")"
        
        self._log(logging.ERROR, message, error_trace=trace_data)
    
    def analysis_result(self, analysis_type: str, result: Dict[str, Any], **kwargs):
        """分析结果日志"""
        result_data = {
            'analysis_type': analysis_type,
            'result': result,
            **kwargs
        }
        
        message = f"ANALYSIS: {analysis_type} completed"
        self._log(logging.INFO, message, analysis=result_data)

# =====================================================================
# 工厂函数和工具函数
# =====================================================================

def get_logger(name: str, config: Optional[Dict[str, Any]] = None) -> UnifiedLogger:
    """获取统一日志器实例"""
    return UnifiedLogger(name, config)

def setup_logging_from_env():
    """从环境变量设置日志配置"""
    config = {}
    
    # 从环境变量读取配置
    if 'LOG_LEVEL' in os.environ:
        config['level'] = os.environ['LOG_LEVEL']
    
    if 'LOG_FORMAT' in os.environ:
        config['format'] = os.environ['LOG_FORMAT']
    
    if 'LOG_JSON' in os.environ:
        config['json_format'] = os.environ['LOG_JSON'].lower() in ('true', '1', 'yes')
    
    if 'LOG_CONSOLE' in os.environ:
        config['console_output'] = os.environ['LOG_CONSOLE'].lower() in ('true', '1', 'yes')
    
    if 'LOG_FILE' in os.environ:
        config['file_output'] = os.environ['LOG_FILE'].lower() in ('true', '1', 'yes')
    
    return config

def configure_root_logger(config: Optional[Dict[str, Any]] = None):
    """配置根日志器"""
    if config is None:
        config = setup_logging_from_env()
    
    # 配置根日志器
    root_config = {**DEFAULT_CONFIG, **config}
    level = LOG_LEVELS.get(root_config['level'].upper(), logging.INFO)
    
    logging.basicConfig(
        level=level,
        format=root_config['format'],
        datefmt=root_config['date_format']
    )

# =====================================================================
# 示例和测试
# =====================================================================

def main():
    """主函数 - 用于测试"""
    print("🧪 测试统一日志管理器...")
    
    # 创建测试日志器
    logger = get_logger('test_component', {
        'level': 'DEBUG',
        'json_format': False
    })
    
    # 测试各种日志级别
    logger.debug("这是调试信息")
    logger.info("这是一般信息")
    logger.warning("这是警告信息")
    logger.error("这是错误信息")
    logger.critical("这是严重错误")
    
    # 测试特殊日志方法
    logger.performance("test_metric", 100.5, "ms")
    logger.bottleneck("CPU", "HIGH", "CPU使用率超过90%")
    logger.error_trace("测试错误", "main", 123)
    logger.analysis_result("qps_analysis", {"max_qps": 1500, "avg_latency": 50})
    
    print("✅ 测试完成")

if __name__ == "__main__":
    main()
