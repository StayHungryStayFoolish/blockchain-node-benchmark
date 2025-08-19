"""ENA字段统一访问接口 - 完全基于配置驱动，无硬编码"""

import os
import pandas as pd
from typing import Dict, List, Optional, Any

class ENAFieldAccessor:
    """ENA字段统一访问接口 - 基于system_config.sh配置，完全配置驱动"""
    
    # 基于AWS官方ENA文档的准确字段配置
    FIELD_CONFIG = {
        'bw_in_allowance_exceeded': {
            'display_name': 'Inbound Bandwidth Allowance Exceeded',
            'type': 'counter',
            'unit': 'packets',
            'description': '因入站聚合带宽超过实例最大值而排队和/或丢弃的数据包数量',
            'aws_description': 'Packets queued/dropped due to inbound aggregate bandwidth exceeding instance maximum'
        },
        'bw_out_allowance_exceeded': {
            'display_name': 'Outbound Bandwidth Allowance Exceeded', 
            'type': 'counter',
            'unit': 'packets',
            'description': '因出站聚合带宽超过实例最大值而排队和/或丢弃的数据包数量',
            'aws_description': 'Packets queued/dropped due to outbound aggregate bandwidth exceeding instance maximum'
        },
        'pps_allowance_exceeded': {
            'display_name': 'PPS Allowance Exceeded',
            'type': 'counter', 
            'unit': 'packets',
            'description': '因双向PPS超过实例最大值而排队和/或丢弃的数据包数量',
            'aws_description': 'Packets queued/dropped due to bidirectional PPS exceeding instance maximum'
        },
        'conntrack_allowance_exceeded': {
            'display_name': 'Connection Tracking Allowance Exceeded',
            'type': 'counter',
            'unit': 'events', 
            'description': '连接跟踪配额超限事件数量',
            'aws_description': 'Connection tracking allowance exceeded events'
        },
        'linklocal_allowance_exceeded': {
            'display_name': 'Link Local Allowance Exceeded',
            'type': 'counter',
            'unit': 'packets',
            'description': '因到本地代理服务(DNS/元数据/时间同步)的流量PPS超过网络接口最大值而丢弃的数据包数量',
            'aws_description': 'Packets dropped due to PPS to local proxy services exceeding network interface maximum'
        },
        'conntrack_allowance_available': {
            'display_name': 'Connection Tracking Allowance Available',
            'type': 'gauge',
            'unit': 'connections',
            'description': '实例在达到连接跟踪配额限制前可以建立的跟踪连接数量 (仅Nitro实例ENA驱动2.8.1+)',
            'aws_description': 'Number of tracked connections that can be established before hitting allowance (Nitro instances only, ENA driver 2.8.1+)'
        }
    }
    
    @classmethod
    def get_configured_ena_fields(cls) -> List[str]:
        """从环境变量获取ENA字段名配置 - 基于现有system_config.sh配置"""
        # 优先使用字符串格式的环境变量
        ena_fields_str = os.getenv('ENA_ALLOWANCE_FIELDS_STR', '')
        
        # 如果字符串格式不可用，尝试原始格式
        if not ena_fields_str:
            ena_fields_str = os.getenv('ENA_ALLOWANCE_FIELDS', '')
        
        if ena_fields_str:
            # 处理bash数组格式: (field1 field2 field3) 或 field1 field2 field3
            ena_fields_str = ena_fields_str.strip('()')
            fields = [field.strip('"\'') for field in ena_fields_str.split()]
            if fields and fields[0]:  # 确保不是空列表
                return fields
        
        # 如果环境变量不可用，提供详细的诊断信息
        print("⚠️ 无法从环境变量获取ENA字段配置")
        print("   诊断信息:")
        print(f"   - ENA_ALLOWANCE_FIELDS_STR: '{os.getenv('ENA_ALLOWANCE_FIELDS_STR', '')}'")
        print(f"   - ENA_ALLOWANCE_FIELDS: '{os.getenv('ENA_ALLOWANCE_FIELDS', '')}'")
        print(f"   - ENA_MONITOR_ENABLED: {os.getenv('ENA_MONITOR_ENABLED', 'undefined')}")
        print("   - 可能原因:")
        print("     1. config_loader.sh未正确加载")
        print("     2. system_config.sh中的export语句未执行")
        print("     3. 环境变量传递到Python进程失败")
        print("   - 解决方案:")
        print("     1. 确保脚本通过source config/config_loader.sh启动")
        print("     2. 检查system_config.sh的export语句")
        print("     3. 使用ENA_ALLOWANCE_FIELDS_STR环境变量")
        
        return []
    
    @classmethod
    def get_available_ena_fields(cls, df: pd.DataFrame) -> List[str]:
        """获取数据中实际存在的ENA字段 - 配置驱动"""
        configured_fields = cls.get_configured_ena_fields()
        available_fields = []
        
        for field_name in configured_fields:
            if field_name in df.columns:
                available_fields.append(field_name)
        
        return available_fields
    
    @classmethod
    def analyze_ena_field(cls, df: pd.DataFrame, field_name: str) -> Optional[Dict[str, Any]]:
        """分析单个ENA字段 - 基于AWS官方定义"""
        try:
            # 字段存在性检查
            if field_name not in df.columns:
                return None
                
            # 数据有效性检查
            field_data = df[field_name].dropna()
            if len(field_data) == 0:
                return None
                
            # 数据类型检查
            if not pd.api.types.is_numeric_dtype(field_data):
                print(f"⚠️ ENA字段 {field_name} 不是数值类型")
                return None
            
            # 获取字段配置，如果不存在则使用默认配置
            field_config = cls.FIELD_CONFIG.get(field_name, {
                'display_name': field_name.replace('_', ' ').title(),
                'type': 'counter' if 'exceeded' in field_name else 'gauge',
                'unit': 'packets' if 'exceeded' in field_name else 'units',
                'description': f'ENA字段: {field_name}',
                'aws_description': f'ENA metric: {field_name}'
            })
            
            analysis = {
                'field_name': field_name,
                'display_name': field_config['display_name'],
                'type': field_config['type'],
                'unit': field_config['unit'],
                'description': field_config['description'],
                'aws_description': field_config.get('aws_description', '')
            }
            
            if field_config['type'] == 'counter':
                # 对于计数器类型，统计累计和峰值
                analysis.update({
                    'total_count': int(field_data.sum()) if not field_data.empty else 0,
                    'max_count': int(field_data.max()) if not field_data.empty else 0,
                    'events_detected': field_data.sum() > 0 if not field_data.empty else False,
                    'status': '⚠️ 检测到限制事件' if (not field_data.empty and field_data.sum() > 0) else '✅ 无限制事件',
                    'interpretation': '累计计数器 - 值越高表示限制事件越频繁'
                })
            elif field_config['type'] == 'gauge':
                # 对于仪表类型，统计范围和趋势
                analysis.update({
                    'min_value': int(field_data.min()) if not field_data.empty else 0,
                    'max_value': int(field_data.max()) if not field_data.empty else 0,
                    'avg_value': int(field_data.mean()) if not field_data.empty else 0,
                    'current_value': int(field_data.iloc[-1]) if len(field_data) > 0 else 0,
                    'trend': 'decreasing' if (len(field_data) > 1 and field_data.iloc[-1] < field_data.iloc[0]) else 'stable',
                    'interpretation': '瞬时值 - 显示当前可用资源量'
                })
                
            return analysis
            
        except Exception as e:
            print(f"❌ ENA字段 {field_name} 分析失败: {str(e)}")
            return None
    
    @classmethod
    def get_unified_network_thresholds(cls) -> Dict[str, Any]:
        """获取统一的网络阈值配置"""
        return {
            'network_utilization_threshold': int(os.getenv('BOTTLENECK_NETWORK_THRESHOLD', 80)),
            'network_utilization_source': 'internal_config.sh',
            'ena_allowance_note': 'ENA allowance exceeded事件无预设阈值，任何非零值都表示发生了限制',
            'aws_recommendation': '监控exceeded类型字段的增长率，available类型字段的下降趋势'
        }