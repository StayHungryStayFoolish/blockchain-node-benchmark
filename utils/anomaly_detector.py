#!/usr/bin/env python3
"""
异常检测工具 - IQR方法实现
提供比2σ规则更鲁棒的异常检测算法
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Union
from utils.unified_logger import get_logger

logger = get_logger(__name__)

class AnomalyDetector:
    """
    异常检测器 - 基于IQR方法
    相比2σ规则，IQR方法对极值更鲁棒，更适合非正态分布数据
    """
    
    def __init__(self, iqr_multiplier: float = 1.5):
        """
        初始化异常检测器
        
        Args:
            iqr_multiplier: IQR倍数，默认1.5 (标准值)
                          - 1.5: 标准异常检测 (约99.3%数据在范围内)
                          - 3.0: 极端异常检测 (约99.9%数据在范围内)
        """
        self.iqr_multiplier = iqr_multiplier
        
    def detect_outliers_iqr(self, data: Union[pd.Series, np.ndarray], 
                           return_bounds: bool = False) -> Union[pd.Series, Tuple[pd.Series, Dict]]:
        """
        使用IQR方法检测异常值
        
        Args:
            data: 输入数据 (pandas Series 或 numpy array)
            return_bounds: 是否返回异常检测边界信息
            
        Returns:
            如果return_bounds=False: 布尔Series，True表示异常值
            如果return_bounds=True: (异常值布尔Series, 边界信息字典)
        """
        if isinstance(data, np.ndarray):
            data = pd.Series(data)
        
        # 确保 data 是 pd.Series 类型（用于IDE类型推断）
        data: pd.Series = data
        
        # ✅ 添加日志记录
        logger.info(f"🔍 开始IQR异常检测，数据点数: {len(data)}")
        logger.debug(f"📊 数据统计: min={data.min():.2f}, max={data.max():.2f}, mean={data.mean():.2f}")
            
        # 计算四分位数
        Q1 = data.quantile(0.25)
        Q3 = data.quantile(0.75)
        IQR = Q3 - Q1
        
        # 计算异常检测边界
        lower_bound = Q1 - self.iqr_multiplier * IQR
        upper_bound = Q3 + self.iqr_multiplier * IQR
        
        # ✅ 添加边界信息日志
        logger.debug(f"📏 IQR边界: Q1={Q1:.2f}, Q3={Q3:.2f}, IQR={IQR:.2f}")
        logger.debug(f"🎯 异常检测边界: [{lower_bound:.2f}, {upper_bound:.2f}]")
        
        # 检测异常值
        outliers_mask = (data < lower_bound) | (data > upper_bound)
        outliers: pd.Series = pd.Series(outliers_mask, dtype=bool)
        
        # ✅ 添加检测结果日志
        outlier_count = outliers.sum()
        outlier_percentage = (outlier_count / len(data)) * 100
        logger.info(f"✅ IQR异常检测完成: 发现 {outlier_count} 个异常点 ({outlier_percentage:.1f}%)")
        
        if return_bounds:
            bounds_info = {
                'Q1': Q1,
                'Q3': Q3,
                'IQR': IQR,
                'lower_bound': lower_bound,
                'upper_bound': upper_bound,
                'outlier_count': outliers.sum(),
                'outlier_percentage': (outliers.sum() / len(data)) * 100,
                'method': 'IQR',
                'multiplier': self.iqr_multiplier
            }
            return outliers, bounds_info
        
        return outliers
    
    def detect_outliers_sigma(self, data: Union[pd.Series, np.ndarray], 
                             sigma_multiplier: float = 2.0,
                             return_bounds: bool = False) -> Union[pd.Series, Tuple[pd.Series, Dict]]:
        """
        使用σ规则检测异常值 (作为对比)
        
        Args:
            data: 输入数据
            sigma_multiplier: σ倍数，默认2.0
            return_bounds: 是否返回边界信息
            
        Returns:
            异常值检测结果
        """
        if isinstance(data, np.ndarray):
            data = pd.Series(data)
        
        # 确保 data 是 pd.Series 类型（用于IDE类型推断）
        data: pd.Series = data
        
        # ✅ 添加日志记录
        logger.info(f"🔍 开始σ规则异常检测，数据点数: {len(data)}, σ倍数: {sigma_multiplier}")
            
        mean = data.mean()
        std = data.std()
        
        lower_bound = mean - sigma_multiplier * std
        upper_bound = mean + sigma_multiplier * std
        
        # ✅ 添加边界信息日志
        logger.debug(f"📊 σ规则统计: mean={mean:.2f}, std={std:.2f}")
        logger.debug(f"🎯 异常检测边界: [{lower_bound:.2f}, {upper_bound:.2f}]")
        
        outliers_mask = (data < lower_bound) | (data > upper_bound)
        outliers: pd.Series = pd.Series(outliers_mask, dtype=bool)
        
        # ✅ 添加检测结果日志
        outlier_count = outliers.sum()
        outlier_percentage = (outlier_count / len(data)) * 100
        logger.info(f"✅ σ规则异常检测完成: 发现 {outlier_count} 个异常点 ({outlier_percentage:.1f}%)")
        
        if return_bounds:
            bounds_info = {
                'mean': mean,
                'std': std,
                'lower_bound': lower_bound,
                'upper_bound': upper_bound,
                'outlier_count': outliers.sum(),
                'outlier_percentage': (outliers.sum() / len(data)) * 100,
                'method': f'{sigma_multiplier}σ',
                'multiplier': sigma_multiplier
            }
            return outliers, bounds_info
        
        return outliers
    
    def compare_methods(self, data: Union[pd.Series, np.ndarray]) -> Dict:
        """
        比较IQR和2σ方法的异常检测结果
        
        Args:
            data: 输入数据
            
        Returns:
            比较结果字典
        """
        if isinstance(data, np.ndarray):
            data = pd.Series(data)
            
        # IQR方法
        iqr_outliers, iqr_bounds = self.detect_outliers_iqr(data, return_bounds=True)
        
        # 2σ方法
        sigma_outliers, sigma_bounds = self.detect_outliers_sigma(data, return_bounds=True)
        
        # 计算重叠度
        both_methods = iqr_outliers & sigma_outliers
        only_iqr = iqr_outliers & ~sigma_outliers
        only_sigma = sigma_outliers & ~iqr_outliers
        
        comparison = {
            'data_points': len(data),
            'iqr_method': iqr_bounds,
            'sigma_method': sigma_bounds,
            'overlap': {
                'both_methods_count': both_methods.sum(),
                'only_iqr_count': only_iqr.sum(),
                'only_sigma_count': only_sigma.sum(),
                'agreement_rate': (both_methods.sum() / max(iqr_outliers.sum(), sigma_outliers.sum())) * 100 if max(iqr_outliers.sum(), sigma_outliers.sum()) > 0 else 100
            },
            'recommendation': self._get_method_recommendation(iqr_bounds, sigma_bounds, data)
        }
        
        return comparison
    
    def _get_method_recommendation(self, iqr_bounds: Dict, sigma_bounds: Dict, data: pd.Series) -> str:
        """
        基于数据特征推荐最适合的异常检测方法
        """
        # 检查数据分布特征
        skewness = data.skew()
        kurtosis = data.kurtosis()
        
        # 推荐逻辑
        if abs(skewness) > 1.0 or kurtosis > 3.0:
            return "IQR方法 - 数据分布偏斜或有重尾，IQR更鲁棒"
        elif iqr_bounds['outlier_count'] > sigma_bounds['outlier_count'] * 2:
            return "2σ方法 - IQR可能过于敏感"
        elif sigma_bounds['outlier_count'] > iqr_bounds['outlier_count'] * 2:
            return "IQR方法 - 2σ可能过于敏感"
        else:
            return "IQR方法 - 通常更鲁棒，推荐作为默认选择"

    def analyze_performance_anomalies(self, df: pd.DataFrame, 
                                    metrics: List[str] = None) -> Dict:
        """
        分析性能指标中的异常值
        
        Args:
            df: 性能数据DataFrame
            metrics: 要分析的指标列表，None表示分析所有数值列
            
        Returns:
            异常分析结果
        """
        if metrics is None:
            # 自动选择数值型列
            metrics = df.select_dtypes(include=[np.number]).columns.tolist()
            # 排除时间戳等不适合异常检测的列
            exclude_cols = ['timestamp', 'current_qps', 'test_duration']
            metrics = [col for col in metrics if col not in exclude_cols]
        
        results = {
            'analyzed_metrics': metrics,
            'anomaly_summary': {},
            'method_comparison': {},
            'recommendations': []
        }
        
        for metric in metrics:
            if metric not in df.columns:
                continue
                
            data = df[metric].dropna()
            if len(data) < 10:  # 数据点太少，跳过
                continue
                
            # 比较两种方法
            comparison = self.compare_methods(data)
            results['method_comparison'][metric] = comparison
            
            # 使用IQR方法检测异常
            outliers, bounds = self.detect_outliers_iqr(data, return_bounds=True)
            
            results['anomaly_summary'][metric] = {
                'outlier_indices': data[outliers].index.tolist(),
                'outlier_values': data[outliers].tolist(),
                'bounds': bounds,
                'severity': self._classify_anomaly_severity(bounds['outlier_percentage'])
            }
        
        # 生成总体建议
        results['recommendations'] = self._generate_anomaly_recommendations(results)
        
        return results
    
    def _classify_anomaly_severity(self, outlier_percentage: float) -> str:
        """分类异常严重程度"""
        if outlier_percentage < 1.0:
            return "轻微"
        elif outlier_percentage < 5.0:
            return "中等"
        elif outlier_percentage < 10.0:
            return "严重"
        else:
            return "极严重"
    
    def _generate_anomaly_recommendations(self, results: Dict) -> List[str]:
        """生成异常检测建议"""
        recommendations = []
        
        high_anomaly_metrics = []
        for metric, summary in results['anomaly_summary'].items():
            if summary['bounds']['outlier_percentage'] > 5.0:
                high_anomaly_metrics.append(metric)
        
        if high_anomaly_metrics:
            recommendations.append(f"发现高异常率指标: {', '.join(high_anomaly_metrics)}")
            recommendations.append("建议检查这些指标对应的系统组件")
        
        if len(results['anomaly_summary']) > 0:
            avg_anomaly_rate = np.mean([s['bounds']['outlier_percentage'] 
                                      for s in results['anomaly_summary'].values()])
            if avg_anomaly_rate > 3.0:
                recommendations.append("整体异常率较高，建议进行系统性能调优")
        
        return recommendations


# 使用示例
if __name__ == "__main__":
    # 创建测试数据
    np.random.seed(42)
    normal_data = np.random.normal(50, 10, 1000)
    # 添加一些异常值
    outliers = np.array([100, 120, 150, -10, -20])
    test_data = np.concatenate([normal_data, outliers])
    
    # 创建异常检测器
    detector = AnomalyDetector()
    
    # 检测异常
    outliers_detected, bounds = detector.detect_outliers_iqr(test_data, return_bounds=True)
    
    print("IQR异常检测结果:")
    print(f"检测到异常值: {outliers_detected.sum()} 个")
    print(f"异常率: {bounds['outlier_percentage']:.2f}%")
    print(f"检测边界: [{bounds['lower_bound']:.2f}, {bounds['upper_bound']:.2f}]")
    
    # 比较两种方法
    comparison = detector.compare_methods(test_data)
    print(f"\n方法比较:")
    print(f"IQR方法检测到: {comparison['iqr_method']['outlier_count']} 个异常")
    print(f"2σ方法检测到: {comparison['sigma_method']['outlier_count']} 个异常")
    print(f"推荐: {comparison['recommendation']}")
