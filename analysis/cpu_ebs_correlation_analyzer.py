#!/usr/bin/env python3
"""
CPU-EBS相关性分析器 - 严格按照文档实现18种统计分析方法
基于 CPU和EBS性能相关性的分析.md 文档的要求实现完整的相关性分析
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
import statsmodels.api as sm
from typing import Dict, List, Tuple, Optional
from utils.unified_logger import get_logger

logger = get_logger(__name__)


class CPUEBSCorrelationAnalyzer:
    """CPU-EBS相关性分析器 - 实现文档中的18种分析方法"""
    
    def __init__(self, data_file: str):
        """
        初始化分析器
        
        Args:
            data_file: 包含CPU和EBS数据的CSV文件路径
        """
        self.data_file = data_file
        self.df = None
        self.analysis_results = {}
        
        # 初始化字体设置标志
        self.use_english_labels = False
        
        # 设置中文字体支持
        self._setup_fonts()
    
    def _setup_fonts(self):
        """增强的字体设置函数，处理AWS EC2环境中的中文字体问题"""
        try:
            # 1. 清除字体缓存，强制重新检测
            from matplotlib.font_manager import _rebuild
            _rebuild()
            
            # 2. 尝试多种中文字体，包括AWS EC2常见字体
            chinese_fonts = [
                'WenQuanYi Micro Hei', 'WenQuanYi Zen Hei',  # AWS上常用的中文字体
                'Noto Sans CJK SC', 'Noto Sans CJK TC',      # Google Noto字体
                'SimHei', 'Microsoft YaHei',                  # Windows中文字体
                'PingFang SC', 'Heiti SC',                    # macOS中文字体
                'DejaVu Sans', 'Arial Unicode MS',            # 通用字体
                'sans-serif'                                  # 最后的回退
            ]
            
            # 3. 设置字体
            plt.rcParams['font.sans-serif'] = chinese_fonts
            plt.rcParams['axes.unicode_minus'] = False
            
            # 4. 验证字体是否可用
            from matplotlib.font_manager import FontManager
            fm = FontManager()
            font_names = set([f.name for f in fm.ttflist])
            
            # 检查是否有任何中文字体可用
            available_chinese_fonts = [f for f in chinese_fonts if f in font_names]
            
            if not available_chinese_fonts:
                print("⚠️  未找到可用的中文字体，将使用英文标签")
                self.use_english_labels = True
            else:
                print(f"✅ 找到可用的中文字体: {available_chinese_fonts[0]}")
                
        except Exception as e:
            print(f"⚠️  字体设置警告: {e}")
            # 使用英文标签作为备选方案
            self.use_english_labels = True
        
    def _check_device_configured(self, logical_name: str) -> bool:
        """检查设备是否配置并且有数据"""
        if self.df is None:
            return False
        
        # 通过列名前缀检查设备是否存在
        device_cols = [col for col in self.df.columns if col.startswith(f'{logical_name}_')]
        return len(device_cols) > 0
        
    def load_and_prepare_data(self) -> bool:
        """加载和准备数据"""
        try:
            self.df = pd.read_csv(self.data_file)
            logger.info(f"✅ 加载数据成功: {len(self.df)} 行, {len(self.df.columns)} 列")
            
            # 验证必要的列是否存在
            required_cpu_cols = ['cpu_iowait', 'cpu_usr', 'cpu_sys', 'cpu_idle', 'cpu_soft']
            required_ebs_cols = []
            
            # 查找EBS设备列 - 使用统一的字段格式匹配
            for col in self.df.columns:
                if (col.startswith('data_') and col.endswith('_util')) or \
                   (col.startswith('accounts_') and col.endswith('_util')):
                    required_ebs_cols.append(col)
                    
            missing_cols = []
            for col in required_cpu_cols:
                if col not in self.df.columns:
                    missing_cols.append(col)
                    
            if missing_cols:
                logger.error(f"❌ 缺少必要的CPU列: {missing_cols}")
                return False
                
            if not required_ebs_cols:
                logger.error("❌ 未找到EBS设备数据列")
                return False
                
            logger.info(f"✅ 数据验证通过，找到 {len(required_ebs_cols)} 个EBS设备")
            return True
            
        except Exception as e:
            logger.error(f"❌ 数据加载失败: {e}")
            return False
    
    def run_complete_analysis(self) -> Dict:
        """运行完整的18种相关性分析"""
        if not self.load_and_prepare_data():
            return {}
            
        print("🔍 开始CPU-EBS完整相关性分析 (18种方法)")
        print("=" * 60)
        
        # 1. Pearson相关性分析 (8种)
        pearson_results = self._analyze_pearson_correlations()
        
        # 2. 线性回归分析 (4种)
        regression_results = self._analyze_linear_regressions()
        
        # 3. 负相关分析 (2种)
        negative_corr_results = self._analyze_negative_correlations()
        
        # 4. 多元回归分析 (4种)
        multiple_regression_results = self._analyze_multiple_regressions()
        
        # 整合所有结果
        self.analysis_results = {
            'pearson_correlations': pearson_results,
            'linear_regressions': regression_results,
            'negative_correlations': negative_corr_results,
            'multiple_regressions': multiple_regression_results,
            'summary': self._generate_analysis_summary()
        }
        
        return self.analysis_results
    
    def _analyze_pearson_correlations(self) -> Dict:
        """分析Pearson相关性 (8种分析)"""
        print("\n📊 1. Pearson相关性分析 (8种)")
        
        results = {}
        
        # 找到设备列 - 使用统一的字段格式匹配
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')]
        
        data_aqu_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_aqu_sz')]
        accounts_aqu_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_aqu_sz')]
        
        data_await_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_avg_await')]
        accounts_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_avg_await')]
        
        # 1-4: CPU I/O wait vs 设备利用率/队列长度/延迟 (DATA设备)
        if data_util_cols and 'cpu_iowait' in self.df.columns:
            corr, p_value = stats.pearsonr(self.df['cpu_iowait'], self.df[data_util_cols[0]])
            results['iowait_vs_data_util'] = {
                'correlation': corr,
                'p_value': p_value,
                'description': 'CPU I/O等待 vs DATA设备利用率',
                'strength': self._interpret_correlation_strength(corr),
                'method': 'pearson'
            }
            print(f"  ✅ CPU I/O等待 vs DATA设备利用率: {corr:.4f} (p={p_value:.4f})")
        
        if data_aqu_cols and 'cpu_iowait' in self.df.columns:
            corr, p_value = stats.pearsonr(self.df['cpu_iowait'], self.df[data_aqu_cols[0]])
            results['iowait_vs_data_queue'] = {
                'correlation': corr,
                'p_value': p_value,
                'description': 'CPU I/O等待 vs DATA设备队列长度',
                'strength': self._interpret_correlation_strength(corr),
                'method': 'pearson'
            }
            print(f"  ✅ CPU I/O等待 vs DATA设备队列长度: {corr:.4f} (p={p_value:.4f})")
        
        if data_await_cols and 'cpu_iowait' in self.df.columns:
            corr, p_value = stats.pearsonr(self.df['cpu_iowait'], self.df[data_await_cols[0]])
            results['iowait_vs_data_latency'] = {
                'correlation': corr,
                'p_value': p_value,
                'description': 'CPU I/O等待 vs DATA设备延迟',
                'strength': self._interpret_correlation_strength(corr),
                'method': 'pearson'
            }
            print(f"  ✅ CPU I/O等待 vs DATA设备延迟: {corr:.4f} (p={p_value:.4f})")
        
        # 5-8: 同样的分析用于ACCOUNTS设备 (仅在ACCOUNTS设备配置时执行)
        accounts_configured = self._check_device_configured('accounts')
        
        if accounts_configured and accounts_util_cols and 'cpu_iowait' in self.df.columns:
            corr, p_value = stats.pearsonr(self.df['cpu_iowait'], self.df[accounts_util_cols[0]])
            results['iowait_vs_accounts_util'] = {
                'correlation': corr,
                'p_value': p_value,
                'description': 'CPU I/O等待 vs ACCOUNTS设备利用率',
                'strength': self._interpret_correlation_strength(corr),
                'method': 'pearson'
            }
            print(f"  ✅ CPU I/O等待 vs ACCOUNTS设备利用率: {corr:.4f} (p={p_value:.4f})")
        
        # 添加缺失的ACCOUNTS设备队列长度分析 (仅在ACCOUNTS设备配置时执行)
        if accounts_configured and accounts_aqu_cols and 'cpu_iowait' in self.df.columns:
            corr, p_value = stats.pearsonr(self.df['cpu_iowait'], self.df[accounts_aqu_cols[0]])
            results['iowait_vs_accounts_queue'] = {
                'correlation': corr,
                'p_value': p_value,
                'description': 'CPU I/O等待 vs ACCOUNTS设备队列长度',
                'strength': self._interpret_correlation_strength(corr),
                'method': 'pearson'
            }
            print(f"  ✅ CPU I/O等待 vs ACCOUNTS设备队列长度: {corr:.4f} (p={p_value:.4f})")
        
        # 添加缺失的ACCOUNTS设备延迟分析 (仅在ACCOUNTS设备配置时执行)
        if accounts_configured and accounts_await_cols and 'cpu_iowait' in self.df.columns:
            corr, p_value = stats.pearsonr(self.df['cpu_iowait'], self.df[accounts_await_cols[0]])
            results['iowait_vs_accounts_latency'] = {
                'correlation': corr,
                'p_value': p_value,
                'description': 'CPU I/O等待 vs ACCOUNTS设备延迟',
                'strength': self._interpret_correlation_strength(corr),
                'method': 'pearson'
            }
            print(f"  ✅ CPU I/O等待 vs ACCOUNTS设备延迟: {corr:.4f} (p={p_value:.4f})")
        elif not accounts_configured:
            print(f"  ⚠️  跳过ACCOUNTS设备分析 (未配置ACCOUNTS设备)")
        
        return results
    
    def _analyze_linear_regressions(self) -> Dict:
        """分析线性回归 (4种分析)"""
        print("\n📈 2. 线性回归分析 (4种)")
        
        results = {}
        
        # 找到读写请求列 - 使用统一的字段格式匹配
        data_r_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_r_s')]
        data_w_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_w_s')]
        accounts_r_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_r_s')]
        accounts_w_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_w_s')]
        
        # 1-2: User CPU vs 读请求, System CPU vs 写请求 (DATA设备)
        if data_r_cols and 'cpu_usr' in self.df.columns:
            X = self.df[['cpu_usr']].values
            y = self.df[data_r_cols[0]].values
            
            model = LinearRegression()
            model.fit(X, y)
            r2 = r2_score(y, model.predict(X))
            
            results['usr_cpu_vs_data_reads'] = {
                'r_squared': r2,
                'coefficient': model.coef_[0],
                'intercept': model.intercept_,
                'description': 'User CPU使用率 vs DATA设备读请求',
                'method': 'linear_regression'
            }
            print(f"  ✅ User CPU vs DATA读请求: R²={r2:.4f}, 系数={model.coef_[0]:.4f}")
        
        if data_w_cols and 'cpu_sys' in self.df.columns:
            X = self.df[['cpu_sys']].values
            y = self.df[data_w_cols[0]].values
            
            model = LinearRegression()
            model.fit(X, y)
            r2 = r2_score(y, model.predict(X))
            
            results['sys_cpu_vs_data_writes'] = {
                'r_squared': r2,
                'coefficient': model.coef_[0],
                'intercept': model.intercept_,
                'description': 'System CPU使用率 vs DATA设备写请求',
                'method': 'linear_regression'
            }
            print(f"  ✅ System CPU vs DATA写请求: R²={r2:.4f}, 系数={model.coef_[0]:.4f}")
        
        # 3-4: 同样的分析用于ACCOUNTS设备 (仅在ACCOUNTS设备配置时执行)
        accounts_configured = self._check_device_configured('accounts')
        
        if accounts_configured and accounts_r_cols and 'cpu_usr' in self.df.columns:
            X = self.df[['cpu_usr']].values
            y = self.df[accounts_r_cols[0]].values
            
            model = LinearRegression()
            model.fit(X, y)
            r2 = r2_score(y, model.predict(X))
            
            results['usr_cpu_vs_accounts_reads'] = {
                'r_squared': r2,
                'coefficient': model.coef_[0],
                'intercept': model.intercept_,
                'description': 'User CPU使用率 vs ACCOUNTS设备读请求',
                'method': 'linear_regression'
            }
            print(f"  ✅ User CPU vs ACCOUNTS读请求: R²={r2:.4f}, 系数={model.coef_[0]:.4f}")
        
        # 添加缺失的ACCOUNTS设备写请求分析 (仅在ACCOUNTS设备配置时执行)
        if accounts_configured and accounts_w_cols and 'cpu_sys' in self.df.columns:
            X = self.df[['cpu_sys']].values
            y = self.df[accounts_w_cols[0]].values
            
            model = LinearRegression()
            model.fit(X, y)
            r2 = r2_score(y, model.predict(X))
            
            results['sys_cpu_vs_accounts_writes'] = {
                'r_squared': r2,
                'coefficient': model.coef_[0],
                'intercept': model.intercept_,
                'description': 'System CPU使用率 vs ACCOUNTS设备写请求',
                'method': 'linear_regression'
            }
            print(f"  ✅ System CPU vs ACCOUNTS写请求: R²={r2:.4f}, 系数={model.coef_[0]:.4f}")
        elif not accounts_configured:
            print(f"  ⚠️  跳过ACCOUNTS设备线性回归分析 (未配置ACCOUNTS设备)")
        
        return results
    
    def _analyze_negative_correlations(self) -> Dict:
        """分析负相关性 (2种分析)"""
        print("\n📉 3. 负相关分析 (2种)")
        
        results = {}
        
        # 找到队列长度列 - 使用统一的字段格式匹配
        data_aqu_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_aqu_sz')]
        accounts_aqu_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_aqu_sz')]
        
        # 1: CPU空闲 vs DATA设备I/O队列长度
        if data_aqu_cols and 'cpu_idle' in self.df.columns:
            corr, p_value = stats.pearsonr(self.df['cpu_idle'], self.df[data_aqu_cols[0]])
            results['idle_vs_data_queue'] = {
                'correlation': corr,
                'p_value': p_value,
                'description': 'CPU空闲时间 vs DATA设备I/O队列长度',
                'is_negative': corr < 0,
                'strength': self._interpret_correlation_strength(abs(corr)),
                'method': 'negative_correlation'
            }
            print(f"  ✅ CPU空闲 vs DATA队列长度: {corr:.4f} ({'负相关' if corr < 0 else '正相关'})")
        
        # 2: CPU空闲 vs ACCOUNTS设备I/O队列长度 (仅在ACCOUNTS设备配置时执行)
        accounts_configured = self._check_device_configured('accounts')
        
        if accounts_configured and accounts_aqu_cols and 'cpu_idle' in self.df.columns:
            corr, p_value = stats.pearsonr(self.df['cpu_idle'], self.df[accounts_aqu_cols[0]])
            results['idle_vs_accounts_queue'] = {
                'correlation': corr,
                'p_value': p_value,
                'description': 'CPU空闲时间 vs ACCOUNTS设备I/O队列长度',
                'is_negative': corr < 0,
                'strength': self._interpret_correlation_strength(abs(corr)),
                'method': 'negative_correlation'
            }
            print(f"  ✅ CPU空闲 vs ACCOUNTS队列长度: {corr:.4f} ({'负相关' if corr < 0 else '正相关'})")
        elif not accounts_configured:
            print(f"  ⚠️  跳过ACCOUNTS设备负相关分析 (未配置ACCOUNTS设备)")
        
        return results
    
    def _analyze_multiple_regressions(self) -> Dict:
        """分析多元回归 (4种分析)"""
        print("\n📊 4. 多元回归分析 (4种)")
        
        results = {}
        
        # 找到相关列 - 使用统一的字段格式匹配
        data_rrqm_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_rrqm_s')]
        data_wrqm_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_wrqm_s')]
        data_rareq_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_rareq_sz')]
        data_wareq_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_wareq_sz')]
        
        # ACCOUNTS设备相关列 - 使用统一的字段格式匹配
        accounts_rrqm_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_rrqm_s')]
        accounts_wrqm_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_wrqm_s')]
        accounts_rareq_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_rareq_sz')]
        accounts_wareq_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_wareq_sz')]
        
        # 1: 软中断 vs I/O请求合并 (DATA设备)
        if data_rrqm_cols and data_wrqm_cols and 'cpu_soft' in self.df.columns:
            try:
                X = self.df[[data_rrqm_cols[0], data_wrqm_cols[0]]].values
                y = self.df['cpu_soft'].values
                
                # 添加常数项
                X_with_const = sm.add_constant(X)
                model = sm.OLS(y, X_with_const).fit()
                
                results['soft_vs_data_merge'] = {
                    'r_squared': model.rsquared,
                    'coefficients': model.params.tolist(),
                    'p_values': model.pvalues.tolist(),
                    'description': '软中断处理 vs DATA设备I/O请求合并',
                    'method': 'multiple_regression'
                }
                print(f"  ✅ 软中断 vs DATA设备I/O合并: R²={model.rsquared:.4f}")
            except Exception as e:
                logger.warning(f"多元回归分析失败: {e}")
        
        # 2: CPU使用率 vs I/O请求大小 (DATA设备)
        if data_rareq_cols and data_wareq_cols and 'cpu_usr' in self.df.columns and 'cpu_sys' in self.df.columns:
            try:
                X = self.df[[data_rareq_cols[0], data_wareq_cols[0]]].values
                y = (self.df['cpu_usr'] + self.df['cpu_sys']).values
                
                X_with_const = sm.add_constant(X)
                model = sm.OLS(y, X_with_const).fit()
                
                results['cpu_vs_data_io_size'] = {
                    'r_squared': model.rsquared,
                    'coefficients': model.params.tolist(),
                    'p_values': model.pvalues.tolist(),
                    'description': 'CPU使用率 vs DATA设备I/O请求大小',
                    'method': 'multiple_regression'
                }
                print(f"  ✅ CPU使用率 vs DATA设备I/O大小: R²={model.rsquared:.4f}")
            except Exception as e:
                logger.warning(f"多元回归分析失败: {e}")
        
        # 3-4: 同样的分析用于ACCOUNTS设备 (仅在ACCOUNTS设备配置时执行)
        accounts_configured = self._check_device_configured('accounts')
        
        # 3: 软中断 vs I/O请求合并 (ACCOUNTS设备)
        if accounts_configured and accounts_rrqm_cols and accounts_wrqm_cols and 'cpu_soft' in self.df.columns:
            try:
                X = self.df[[accounts_rrqm_cols[0], accounts_wrqm_cols[0]]].values
                y = self.df['cpu_soft'].values
                
                # 添加常数项
                X_with_const = sm.add_constant(X)
                model = sm.OLS(y, X_with_const).fit()
                
                results['soft_vs_accounts_merge'] = {
                    'r_squared': model.rsquared,
                    'coefficients': model.params.tolist(),
                    'p_values': model.pvalues.tolist(),
                    'description': '软中断处理 vs ACCOUNTS设备I/O请求合并',
                    'method': 'multiple_regression'
                }
                print(f"  ✅ 软中断 vs ACCOUNTS设备I/O合并: R²={model.rsquared:.4f}")
            except Exception as e:
                logger.warning(f"ACCOUNTS设备多元回归分析失败: {e}")
        
        # 4: CPU使用率 vs I/O请求大小 (ACCOUNTS设备)
        if accounts_configured and accounts_rareq_cols and accounts_wareq_cols and 'cpu_usr' in self.df.columns and 'cpu_sys' in self.df.columns:
            try:
                X = self.df[[accounts_rareq_cols[0], accounts_wareq_cols[0]]].values
                y = (self.df['cpu_usr'] + self.df['cpu_sys']).values
                
                X_with_const = sm.add_constant(X)
                model = sm.OLS(y, X_with_const).fit()
                
                results['cpu_vs_accounts_io_size'] = {
                    'r_squared': model.rsquared,
                    'coefficients': model.params.tolist(),
                    'p_values': model.pvalues.tolist(),
                    'description': 'CPU使用率 vs ACCOUNTS设备I/O请求大小',
                    'method': 'multiple_regression'
                }
                print(f"  ✅ CPU使用率 vs ACCOUNTS设备I/O大小: R²={model.rsquared:.4f}")
            except Exception as e:
                logger.warning(f"ACCOUNTS设备多元回归分析失败: {e}")
        elif not accounts_configured:
            print(f"  ⚠️  跳过ACCOUNTS设备多元回归分析 (未配置ACCOUNTS设备)")
        
        return results
    
    def _interpret_correlation_strength(self, corr: float) -> str:
        """解释相关性强度"""
        abs_corr = abs(corr)
        if abs_corr >= 0.8:
            return "很强"
        elif abs_corr >= 0.6:
            return "强"
        elif abs_corr >= 0.4:
            return "中等"
        elif abs_corr >= 0.2:
            return "弱"
        else:
            return "很弱"
    
    def _generate_analysis_summary(self) -> Dict:
        """生成分析摘要"""
        summary = {
            'total_analyses': 0,
            'significant_correlations': 0,
            'strong_correlations': [],
            'recommendations': []
        }
        
        # 统计所有分析
        for category in ['pearson_correlations', 'linear_regressions', 'negative_correlations', 'multiple_regressions']:
            if category in self.analysis_results:
                summary['total_analyses'] += len(self.analysis_results[category])
        
        # 找出强相关性
        if 'pearson_correlations' in self.analysis_results:
            for name, result in self.analysis_results['pearson_correlations'].items():
                if abs(result.get('correlation', 0)) >= 0.6:
                    summary['strong_correlations'].append({
                        'name': name,
                        'correlation': result['correlation'],
                        'description': result['description']
                    })
        
        # 生成建议
        if len(summary['strong_correlations']) > 0:
            summary['recommendations'].append("发现强相关性，可用于性能预测和优化")
        
        return summary
    
    def generate_comprehensive_report(self) -> str:
        """生成完整的分析报告"""
        if not self.analysis_results:
            return "❌ 未执行分析，无法生成报告"
        
        report = f"""
# CPU-EBS性能相关性完整分析报告
生成时间: {pd.Timestamp.now()}

## 分析概述
- **总分析数**: {self.analysis_results['summary']['total_analyses']}
- **强相关关系数**: {len(self.analysis_results['summary']['strong_correlations'])}
- **数据点数**: {len(self.df) if self.df is not None else 0}

## 1. Pearson相关性分析结果 (8种)
"""
        
        if 'pearson_correlations' in self.analysis_results:
            for name, result in self.analysis_results['pearson_correlations'].items():
                report += f"""
### {result['description']}
- **相关系数**: {result['correlation']:.4f}
- **P值**: {result['p_value']:.4f}
- **相关强度**: {result['strength']}
- **统计显著性**: {'是' if result['p_value'] < 0.05 else '否'}
"""
        
        report += "\n## 2. 线性回归分析结果 (4种)\n"
        if 'linear_regressions' in self.analysis_results:
            for name, result in self.analysis_results['linear_regressions'].items():
                report += f"""
### {result['description']}
- **R²值**: {result['r_squared']:.4f}
- **回归系数**: {result['coefficient']:.4f}
- **截距**: {result['intercept']:.4f}
- **模型质量**: {'好' if result['r_squared'] > 0.5 else '中等' if result['r_squared'] > 0.3 else '差'}
"""
        
        report += "\n## 3. 负相关分析结果 (2种)\n"
        if 'negative_correlations' in self.analysis_results:
            for name, result in self.analysis_results['negative_correlations'].items():
                report += f"""
### {result['description']}
- **相关系数**: {result['correlation']:.4f}
- **是否负相关**: {'是' if result['is_negative'] else '否'}
- **相关强度**: {result['strength']}
"""
        
        report += "\n## 4. 多元回归分析结果 (4种)\n"
        if 'multiple_regressions' in self.analysis_results:
            for name, result in self.analysis_results['multiple_regressions'].items():
                report += f"""
### {result['description']}
- **R²值**: {result['r_squared']:.4f}
- **模型显著性**: {'显著' if result['r_squared'] > 0.3 else '不显著'}
"""
        
        report += f"""
## 分析结论和建议

### 强相关关系发现
"""
        for corr in self.analysis_results['summary']['strong_correlations']:
            report += f"- **{corr['description']}**: {corr['correlation']:.4f}\n"
        
        report += f"""
### 优化建议
"""
        for rec in self.analysis_results['summary']['recommendations']:
            report += f"- {rec}\n"
        
        return report


# 使用示例
if __name__ == "__main__":
    print("📋 CPU-EBS相关性分析器使用示例:")
    print("analyzer = CPUEBSCorrelationAnalyzer('performance_data.csv')")
    print("results = analyzer.run_complete_analysis()")
    print("report = analyzer.generate_comprehensive_report()")
