"""ENA Field Unified Access Interface - Fully configuration-driven, no hardcoding"""

import os
import pandas as pd
from typing import Dict, List, Optional, Any

class ENAFieldAccessor:
    """ENA Field Unified Access Interface - Based on system_config.sh configuration, fully configuration-driven"""
    
    # Accurate field configuration based on AWS official ENA documentation
    FIELD_CONFIG = {
        'bw_in_allowance_exceeded': {
            'display_name': 'Inbound Bandwidth Allowance Exceeded',
            'type': 'counter',
            'unit': 'packets',
            'description': 'Number of packets queued/dropped due to inbound aggregate bandwidth exceeding instance maximum',
            'aws_description': 'Packets queued/dropped due to inbound aggregate bandwidth exceeding instance maximum'
        },
        'bw_out_allowance_exceeded': {
            'display_name': 'Outbound Bandwidth Allowance Exceeded', 
            'type': 'counter',
            'unit': 'packets',
            'description': 'Number of packets queued/dropped due to outbound aggregate bandwidth exceeding instance maximum',
            'aws_description': 'Packets queued/dropped due to outbound aggregate bandwidth exceeding instance maximum'
        },
        'pps_allowance_exceeded': {
            'display_name': 'PPS Allowance Exceeded',
            'type': 'counter', 
            'unit': 'packets',
            'description': 'Number of packets queued/dropped due to bidirectional PPS exceeding instance maximum',
            'aws_description': 'Packets queued/dropped due to bidirectional PPS exceeding instance maximum'
        },
        'conntrack_allowance_exceeded': {
            'display_name': 'Connection Tracking Allowance Exceeded',
            'type': 'counter',
            'unit': 'events', 
            'description': 'Number of connection tracking allowance exceeded events',
            'aws_description': 'Connection tracking allowance exceeded events'
        },
        'linklocal_allowance_exceeded': {
            'display_name': 'Link Local Allowance Exceeded',
            'type': 'counter',
            'unit': 'packets',
            'description': 'Number of packets dropped due to PPS to local proxy services (DNS/metadata/time sync) exceeding network interface maximum',
            'aws_description': 'Packets dropped due to PPS to local proxy services exceeding network interface maximum'
        },
        'conntrack_allowance_available': {
            'display_name': 'Connection Tracking Allowance Available',
            'type': 'gauge',
            'unit': 'connections',
            'description': 'Number of tracked connections that can be established before hitting connection tracking allowance limit (Nitro instances only, ENA driver 2.8.1+)',
            'aws_description': 'Number of tracked connections that can be established before hitting allowance (Nitro instances only, ENA driver 2.8.1+)'
        }
    }
    
    @classmethod
    def get_configured_ena_fields(cls) -> List[str]:
        """Get ENA field name configuration from environment variables - based on existing system_config.sh configuration"""
        # Prioritize string format environment variable
        ena_fields_str = os.getenv('ENA_ALLOWANCE_FIELDS_STR', '')
        
        # If string format not available, try original format
        if not ena_fields_str:
            ena_fields_str = os.getenv('ENA_ALLOWANCE_FIELDS', '')
        
        if ena_fields_str:
            # Handle bash array format: (field1 field2 field3) or field1 field2 field3
            ena_fields_str = ena_fields_str.strip('()')
            fields = [field.strip('"\'') for field in ena_fields_str.split()]
            if fields and fields[0]:  # Ensure not empty list
                return fields
        
        # If environment variable not available, use standard ENA field list as fallback
        print("⚠️ Unable to get ENA field configuration from environment variables")
        print("   Diagnostic information:")
        print(f"   - ENA_ALLOWANCE_FIELDS_STR: '{os.getenv('ENA_ALLOWANCE_FIELDS_STR', '')}'")
        print(f"   - ENA_ALLOWANCE_FIELDS: '{os.getenv('ENA_ALLOWANCE_FIELDS', '')}'")
        print(f"   - ENA_MONITOR_ENABLED: {os.getenv('ENA_MONITOR_ENABLED', 'undefined')}")
        print("   - Using standard ENA field list as fallback")
        
        # Return standard ENA field list
        return list(cls.FIELD_CONFIG.keys())
    
    @classmethod
    def get_available_ena_fields(cls, df: pd.DataFrame) -> List[str]:
        """Get ENA fields actually present in data - configuration-driven"""
        configured_fields = cls.get_configured_ena_fields()
        available_fields = []
        
        for field_name in configured_fields:
            if field_name in df.columns:
                available_fields.append(field_name)
        
        return available_fields
    
    @classmethod
    def analyze_ena_field(cls, df: pd.DataFrame, field_name: str) -> Optional[Dict[str, Any]]:
        """Analyze single ENA field - based on AWS official definition"""
        try:
            # Field existence check
            if field_name not in df.columns:
                return None
                
            # Data validity check
            field_data = df[field_name].dropna()
            if len(field_data) == 0:
                return None
                
            # Data type check
            if not pd.api.types.is_numeric_dtype(field_data):
                print(f"⚠️ ENA field {field_name} is not numeric type")
                return None
            
            # Get field configuration, use default configuration if not exists
            field_config = cls.FIELD_CONFIG.get(field_name, {
                'display_name': field_name.replace('_', ' ').title(),
                'type': 'counter' if 'exceeded' in field_name else 'gauge',
                'unit': 'packets' if 'exceeded' in field_name else 'units',
                'description': f'ENA field: {field_name}',
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
                # For counter type, calculate cumulative and peak values
                analysis.update({
                    'total_count': int(field_data.sum()) if not field_data.empty else 0,
                    'max_count': int(field_data.max()) if not field_data.empty else 0,
                    'events_detected': field_data.sum() > 0 if not field_data.empty else False,
                    'status': '⚠️ Limitation events detected' if (not field_data.empty and field_data.sum() > 0) else '✅ No limitation events',
                    'interpretation': 'Cumulative counter - higher values indicate more frequent limitation events'
                })
            elif field_config['type'] == 'gauge':
                # For gauge type, calculate range and trend
                analysis.update({
                    'min_value': int(field_data.min()) if not field_data.empty else 0,
                    'max_value': int(field_data.max()) if not field_data.empty else 0,
                    'avg_value': int(field_data.mean()) if not field_data.empty else 0,
                    'current_value': int(field_data.iloc[-1]) if len(field_data) > 0 else 0,
                    'trend': 'decreasing' if (len(field_data) > 1 and field_data.iloc[-1] < field_data.iloc[0]) else 'stable',
                    'interpretation': 'Instantaneous value - shows current available resource amount'
                })
                
            return analysis
            
        except Exception as e:
            print(f"❌ ENA field {field_name} analysis failed: {str(e)}")
            return None
    
    @classmethod
    def get_unified_network_thresholds(cls) -> Dict[str, Any]:
        """Get unified network threshold configuration"""
        return {
            'network_utilization_threshold': int(os.getenv('BOTTLENECK_NETWORK_THRESHOLD', 80)),
            'network_utilization_source': 'internal_config.sh',
            'ena_allowance_note': 'ENA allowance exceeded events have no preset threshold, any non-zero value indicates limitation occurred',
            'aws_recommendation': 'Monitor growth rate of exceeded type fields and downward trend of available type fields'
        }