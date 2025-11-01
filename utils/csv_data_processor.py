#!/usr/bin/env python3
"""
Simplified CSV Data Processor
Removed field mapping functionality, focused on core data processing
"""

import pandas as pd
import numpy as np
from utils.unified_logger import get_logger
from typing import List, Dict, Optional, Any
import os

logger = get_logger(__name__)

class CSVDataProcessor:
    """Simplified CSV Data Processor - Focused on core data processing functionality"""
    
    def __init__(self):
        """Initialize processor"""
        self.df = None
        self.csv_file = None
        
    def load_csv_data(self, csv_file: str) -> bool:
        """
        Enhanced CSV data loading with complete validation
        
        Args:
            csv_file: CSV file path
            
        Returns:
            bool: Whether loading was successful
        """
        try:
            if not os.path.exists(csv_file):
                logger.error(f"❌ CSV file does not exist: {csv_file}")
                return False
            
            # Check file size
            file_size = os.path.getsize(csv_file)
            if file_size == 0:
                logger.warning(f"⚠️ CSV file is empty: {csv_file}")
                return False
            
            # Check file format - read first few lines for validation
            with open(csv_file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if not first_line:
                    logger.error(f"❌ CSV file has no content: {csv_file}")
                    return False
                
                if ',' not in first_line:
                    logger.error(f"❌ CSV file format invalid, missing comma delimiter: {csv_file}")
                    return False
                
                # Check if there are enough columns
                column_count = len(first_line.split(','))
                if column_count < 2:
                    logger.error(f"❌ CSV file has insufficient columns: {column_count} columns")
                    return False
            
            # Attempt to read CSV
            self.df = pd.read_csv(csv_file)
            self.csv_file = csv_file
            
            # Validate data integrity
            if self.df.empty:
                logger.warning(f"⚠️ CSV data is empty: {csv_file}")
                return False
            
            if len(self.df.columns) == 0:
                logger.error(f"❌ CSV file has no valid columns: {csv_file}")
                return False
            
            logger.info(f"✅ Successfully loaded CSV data: {len(self.df)} rows, {len(self.df.columns)} columns")
            return True
            
        except pd.errors.EmptyDataError:
            logger.error(f"❌ CSV file has no data rows: {csv_file}")
            return False
        except pd.errors.ParserError as e:
            logger.error(f"❌ CSV parsing error: {e}")
            return False
        except UnicodeDecodeError as e:
            logger.error(f"❌ CSV file encoding error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to load CSV data: {e}")
            return False
    
    def get_device_columns_safe(self, device_prefix: str, metric_suffix: str) -> List[str]:
        """
        Safely get device-related columns
        
        Args:
            device_prefix: Device prefix (e.g. 'data', 'accounts')
            metric_suffix: Metric suffix (e.g. 'util', 'iops')
            
        Returns:
            List[str]: List of matching column names
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
        Check if field exists
        
        Args:
            field_name: Field name
            
        Returns:
            bool: Whether field exists
        """
        return self.df is not None and field_name in self.df.columns
    
    def validate_required_fields(self, required_fields: List[str]) -> Dict[str, bool]:
        """
        Validate if required fields exist
        
        Args:
            required_fields: List of required fields
            
        Returns:
            Dict[str, bool]: Field existence mapping
        """
        if self.df is None:
            return {field: False for field in required_fields}
        
        return {field: field in self.df.columns for field in required_fields}
    
    def get_available_fields(self) -> List[str]:
        """
        Get all available fields
        
        Returns:
            List[str]: List of available fields
        """
        if self.df is None:
            return []
        return list(self.df.columns)
    
    def clean_data(self) -> bool:
        """
        Clean data
        
        Returns:
            bool: Whether cleaning was successful
        """
        if self.df is None:
            return False
        
        try:
            # 1. Handle data types for numeric fields
            numeric_keywords = ['cpu', 'mem', 'usage', 'percent', 'util', 'iops', 'throughput', 'mbps', 'gbps']
            
            for col in self.df.columns:
                if any(keyword in col.lower() for keyword in numeric_keywords):
                    # Convert to numeric type, set unconvertible values to NaN
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
                elif 'util' in col.lower():
                    # Special handling for utilization fields
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
                    # Ensure utilization is within 0-100 range
                    self.df[col] = self.df[col].clip(0, 100)
                elif any(keyword in col.lower() for keyword in ['await', 'latency', 'delay']):
                    # Latency field handling
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
                elif any(keyword in col.lower() for keyword in ['iops', 'throughput', '_s', 'mbps', 'gbps']):
                    # Performance metric field handling
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
            
            # 2. Handle timestamp fields
            timestamp_cols = [col for col in self.df.columns if 'timestamp' in col.lower()]
            for col in timestamp_cols:
                try:
                    self.df[col] = pd.to_datetime(self.df[col])
                except:
                    logger.warning(f"⚠️ Unable to convert timestamp field: {col}")
            
            # 3. Remove completely empty columns
            self.df = self.df.dropna(axis=1, how='all')
            
            # 4. Basic data validation
            if len(self.df) == 0:
                logger.warning("⚠️ No data remaining after cleaning")
                return False
            
            logger.info(f"✅ Data cleaning completed: {len(self.df)} rows, {len(self.df.columns)} columns")
            return True
            
        except Exception as e:
            logger.error(f"❌ Data cleaning failed: {e}")
            return False
    
    def get_summary_info(self) -> Dict:
        """
        Get data summary information
        
        Returns:
            Dict: Data summary
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
            
            # Add basic statistics for numeric fields
            numeric_cols = self.df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                summary['numeric_summary'] = self.df[numeric_cols].describe().to_dict()
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Failed to get summary information: {e}")
            return {}

def load_csv_with_processor(csv_file: str) -> CSVDataProcessor:
    """
    Convenience function: Load CSV file and return processor instance
    
    Args:
        csv_file: CSV file path
        
    Returns:
        CSVDataProcessor: Processor instance
    """
    processor = CSVDataProcessor()
    if processor.load_csv_data(csv_file):
        processor.clean_data()
    return processor

if __name__ == "__main__":
    # Test code
    processor = CSVDataProcessor()
    print("✅ Simplified CSV data processor initialized successfully")
    print("Main functions:")
    print("  - load_csv_data(): Load CSV data")
    print("  - get_device_columns_safe(): Safely get device fields")
    print("  - clean_data(): Data cleaning")
    print("  - get_summary_info(): Get data summary")
