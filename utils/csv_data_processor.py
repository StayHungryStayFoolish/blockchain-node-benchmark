#!/usr/bin/env python3
"""
简化的CSV数据处理器
移除字段映射功能，专注于核心数据处理
"""

import pandas as pd
import numpy as np
from utils.unified_logger import get_logger
from typing import List, Dict, Optional, Any
import os

logger = get_logger(__name__)

class CSVDataProcessor:
    """简化的CSV数据处理器 - 专注于核心数据处理功能"""
    
    def __init__(self):
        """初始化处理器"""
        self.df = None
        self.csv_file = None
        
    def load_csv_data(self, csv_file: str) -> bool:
        """
        增强的CSV数据加载，包含完整验证
        
        Args:
            csv_file: CSV文件路径
            
        Returns:
            bool: 加载是否成功
        """
        try:
            if not os.path.exists(csv_file):
                logger.error(f"❌ CSV文件不存在: {csv_file}")
                return False
            
            # 检查文件大小
            file_size = os.path.getsize(csv_file)
            if file_size == 0:
                logger.warning(f"⚠️ CSV文件为空: {csv_file}")
                return False
            
            # 检查文件格式 - 读取前几行验证
            with open(csv_file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if not first_line:
                    logger.error(f"❌ CSV文件无内容: {csv_file}")
                    return False
                
                if ',' not in first_line:
                    logger.error(f"❌ CSV文件格式无效，缺少逗号分隔符: {csv_file}")
                    return False
                
                # 检查是否有足够的列
                column_count = len(first_line.split(','))
                if column_count < 2:
                    logger.error(f"❌ CSV文件列数不足: {column_count} 列")
                    return False
            
            # 尝试读取CSV
            self.df = pd.read_csv(csv_file)
            self.csv_file = csv_file
            
            # 验证数据完整性
            if self.df.empty:
                logger.warning(f"⚠️ CSV数据为空: {csv_file}")
                return False
            
            if len(self.df.columns) == 0:
                logger.error(f"❌ CSV文件无有效列: {csv_file}")
                return False
            
            logger.info(f"✅ 成功加载CSV数据: {len(self.df)} 行, {len(self.df.columns)} 列")
            return True
            
        except pd.errors.EmptyDataError:
            logger.error(f"❌ CSV文件无数据行: {csv_file}")
            return False
        except pd.errors.ParserError as e:
            logger.error(f"❌ CSV解析错误: {e}")
            return False
        except UnicodeDecodeError as e:
            logger.error(f"❌ CSV文件编码错误: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 加载CSV数据失败: {e}")
            return False
    
    def get_device_columns_safe(self, device_prefix: str, metric_suffix: str) -> List[str]:
        """
        安全获取设备相关列
        
        Args:
            device_prefix: 设备前缀 (如 'data', 'accounts')
            metric_suffix: 指标后缀 (如 'util', 'iops')
            
        Returns:
            List[str]: 匹配的列名列表
        """
        if self.df is None:
            return []
        
        matching_cols = []
        for col in self.df.columns:
            if col.startswith(f'{device_prefix}_') and metric_suffix in col:
                matching_cols.append(col)
        
        return matching_cols
    
    def has_field(self, field_name: str) -> bool:
        """
        检查字段是否存在
        
        Args:
            field_name: 字段名
            
        Returns:
            bool: 字段是否存在
        """
        return self.df is not None and field_name in self.df.columns
    
    def validate_required_fields(self, required_fields: List[str]) -> Dict[str, bool]:
        """
        验证必需字段是否存在
        
        Args:
            required_fields: 必需字段列表
            
        Returns:
            Dict[str, bool]: 字段存在性映射
        """
        if self.df is None:
            return {field: False for field in required_fields}
        
        return {field: field in self.df.columns for field in required_fields}
    
    def get_available_fields(self) -> List[str]:
        """
        获取所有可用字段
        
        Returns:
            List[str]: 可用字段列表
        """
        if self.df is None:
            return []
        return list(self.df.columns)
    
    def clean_data(self) -> bool:
        """
        清洗数据
        
        Returns:
            bool: 清洗是否成功
        """
        if self.df is None:
            return False
        
        try:
            # 1. 处理数值字段的数据类型
            numeric_keywords = ['cpu', 'mem', 'usage', 'percent', 'util', 'iops', 'throughput', 'mbps', 'gbps']
            
            for col in self.df.columns:
                if any(keyword in col.lower() for keyword in numeric_keywords):
                    # 转换为数值类型，无法转换的设为NaN
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
                elif 'util' in col.lower():
                    # 利用率字段特殊处理
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
                    # 确保利用率在0-100范围内
                    self.df[col] = self.df[col].clip(0, 100)
                elif any(keyword in col.lower() for keyword in ['await', 'latency', 'delay']):
                    # 延迟字段处理
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
                elif any(keyword in col.lower() for keyword in ['iops', 'throughput', '_s', 'mbps', 'gbps']):
                    # 性能指标字段处理
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
            
            # 2. 处理时间戳字段
            timestamp_cols = [col for col in self.df.columns if 'timestamp' in col.lower()]
            for col in timestamp_cols:
                try:
                    self.df[col] = pd.to_datetime(self.df[col])
                except:
                    logger.warning(f"⚠️ 无法转换时间戳字段: {col}")
            
            # 3. 移除完全为空的列
            self.df = self.df.dropna(axis=1, how='all')
            
            # 4. 基本数据验证
            if len(self.df) == 0:
                logger.warning("⚠️ 数据清洗后没有剩余数据")
                return False
            
            logger.info(f"✅ 数据清洗完成: {len(self.df)} 行, {len(self.df.columns)} 列")
            return True
            
        except Exception as e:
            logger.error(f"❌ 数据清洗失败: {e}")
            return False
    
    def get_summary_info(self) -> Dict:
        """
        获取数据摘要信息
        
        Returns:
            Dict: 数据摘要
        """
        if self.df is None:
            return {}
        
        try:
            summary = {
                'total_rows': len(self.df),
                'total_columns': len(self.df.columns),
                'csv_file': self.csv_file,
                'columns': list(self.df.columns),
                'data_types': self.df.dtypes.to_dict(),
                'memory_usage': self.df.memory_usage(deep=True).sum(),
                'null_counts': self.df.isnull().sum().to_dict()
            }
            
            # 添加数值字段的基本统计
            numeric_cols = self.df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                summary['numeric_summary'] = self.df[numeric_cols].describe().to_dict()
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ 获取摘要信息失败: {e}")
            return {}

def load_csv_with_processor(csv_file: str) -> CSVDataProcessor:
    """
    便捷函数：加载CSV文件并返回处理器实例
    
    Args:
        csv_file: CSV文件路径
        
    Returns:
        CSVDataProcessor: 处理器实例
    """
    processor = CSVDataProcessor()
    if processor.load_csv_data(csv_file):
        processor.clean_data()
    return processor

if __name__ == "__main__":
    # 测试代码
    processor = CSVDataProcessor()
    print("✅ 简化的CSV数据处理器初始化成功")
    print("主要功能:")
    print("  - load_csv_data(): 加载CSV数据")
    print("  - get_device_columns_safe(): 安全获取设备字段")
    print("  - clean_data(): 数据清洗")
    print("  - get_summary_info(): 获取数据摘要")
