#!/usr/bin/env python3
"""
Unified Logger Manager - Python Version
============================
Provides unified Python logging configuration, formatting, and management functionality
Solves inconsistent Python logging configuration issues in the project
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
# Logging configuration constants
# =====================================================================

# Log level mapping
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

# Default configuration
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

# Color configuration
COLORS = {
    'DEBUG': '\033[0;36m',    # Cyan
    'INFO': '\033[0;32m',     # Green
    'WARNING': '\033[0;33m',  # Yellow
    'ERROR': '\033[0;31m',    # Red
    'CRITICAL': '\033[0;35m', # Purple
    'RESET': '\033[0m'
}

# =====================================================================
# Custom formatters
# =====================================================================

class ColoredFormatter(logging.Formatter):
    """Colored console log formatter"""
    
    def format(self, record):
        # Add color
        level_color = COLORS.get(record.levelname, COLORS['RESET'])
        record.levelname = f"{level_color}{record.levelname}{COLORS['RESET']}"
        
        # Format message
        formatted = super().format(record)
        
        return formatted

class JSONFormatter(logging.Formatter):
    """JSON format log formatter"""
    
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
        
        # Add exception information
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add custom fields
        if hasattr(record, 'component'):
            log_entry['component'] = record.component
        if hasattr(record, 'metric'):
            log_entry['metric'] = record.metric
        if hasattr(record, 'performance'):
            log_entry['performance'] = record.performance
        
        return json.dumps(log_entry, ensure_ascii=False)

# =====================================================================
# Unified logger manager
# =====================================================================

class UnifiedLogger:
    """Unified logger manager"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Set up logger"""
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Set log level
        level = LOG_LEVELS.get(self.config['level'].upper(), logging.INFO)
        self.logger.setLevel(level)
        
        # Add console handler
        if self.config['console_output']:
            self._add_console_handler()
        
        # Add file handler
        if self.config['file_output']:
            self._add_file_handler()
        
        # Prevent log propagation to root logger
        self.logger.propagate = False
    
    def _add_console_handler(self):
        """Add console handler"""
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
        """Add file handler"""
        # Get log file path
        log_file = self._get_log_file_path()
        
        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file),
            maxBytes=self.config['max_file_size'],
            backupCount=self.config['backup_count'],
            encoding='utf-8'
        )
        
        # Set formatter (no color for files)
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
        """Get log file path"""
        # Get log directory from environment variable
        logs_dir = os.environ.get('LOGS_DIR', '/tmp/logs')
        
        # Generate standardized filename
        timestamp = datetime.now().strftime('%Y%m%d')
        filename = f"{self.name}_{timestamp}.log"
        
        return Path(logs_dir) / filename
    
    # =====================================================================
    # Log methods
    # =====================================================================
    
    def debug(self, message: str, **kwargs):
        """Debug log"""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Info log"""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Warning log"""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Error log"""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Critical error log"""
        self._log(logging.CRITICAL, message, **kwargs)
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal log method"""
        # Create log record
        record = self.logger.makeRecord(
            name=self.logger.name,
            level=level,
            fn='',
            lno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        
        # Add custom attributes
        for key, value in kwargs.items():
            setattr(record, key, value)
        
        # Handle log record
        self.logger.handle(record)
    
    # =====================================================================
    # Special log methods
    # =====================================================================
    
    def performance(self, metric: str, value: float, unit: str = '', **kwargs):
        """Performance log"""
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
        """Bottleneck log"""
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
        """Error trace log"""
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
        """Analysis result log"""
        result_data = {
            'analysis_type': analysis_type,
            'result': result,
            **kwargs
        }
        
        message = f"ANALYSIS: {analysis_type} completed"
        self._log(logging.INFO, message, analysis=result_data)

# =====================================================================
# Factory functions and utility functions
# =====================================================================

def get_logger(name: str, config: Optional[Dict[str, Any]] = None) -> UnifiedLogger:
    """Get unified logger instance"""
    return UnifiedLogger(name, config)

def setup_logging_from_env():
    """Set up logging configuration from environment variables"""
    config = {}
    
    # Read configuration from environment variables
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
    """Configure root logger"""
    if config is None:
        config = setup_logging_from_env()
    
    # Configure root logger
    root_config = {**DEFAULT_CONFIG, **config}
    level = LOG_LEVELS.get(root_config['level'].upper(), logging.INFO)
    
    logging.basicConfig(
        level=level,
        format=root_config['format'],
        datefmt=root_config['date_format']
    )

# =====================================================================
# Examples and tests
# =====================================================================

def main():
    """Main function - for testing"""
    print("🧪 Testing unified logger manager...")
    
    # Create test logger
    logger = get_logger('test_component', {
        'level': 'DEBUG',
        'json_format': False
    })
    
    # Test various log levels
    logger.debug("This is debug information")
    logger.info("This is general information")
    logger.warning("This is warning information")
    logger.error("This is error information")
    logger.critical("This is critical error")
    
    # Test special log methods
    logger.performance("test_metric", 100.5, "ms")
    logger.bottleneck("CPU", "HIGH", "CPU usage exceeds 90%")
    logger.error_trace("Test error", "main", 123)
    logger.analysis_result("qps_analysis", {"max_qps": 1500, "avg_latency": 50})
    
    print("✅ Testing completed")

if __name__ == "__main__":
    main()
