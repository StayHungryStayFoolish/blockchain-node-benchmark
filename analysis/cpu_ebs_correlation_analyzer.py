#!/usr/bin/env python3
"""
CPU-EBS Correlation Analyzer
Implements complete correlation analysis based on CPU and EBS Performance Correlation Analysis.md document requirements
"""

import sys
import os

# Add project root directory to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
from scipy import stats
from sklearn.linear_model import LinearRegression
from visualization.chart_style_config import UnifiedChartStyle

from sklearn.metrics import r2_score
import statsmodels.api as sm
from typing import Dict, List, Tuple, Optional
from utils.unified_logger import get_logger

logger = get_logger(__name__)


class CPUEBSCorrelationAnalyzer:
    """CPU-EBS Correlation Analyzer - Implements 18 analysis methods from the document"""
    
    def __init__(self, data_file: str):
        """
        Initialize analyzer
        
        Args:
            data_file: CSV file path containing CPU and EBS data
        """
        self.data_file = data_file
        self.df = None
        self.analysis_results = {}

    def _check_device_configured(self, logical_name: str) -> bool:
        """Check if device is configured and has data"""
        if self.df is None:
            return False
        
        # Check if device exists by column name prefix
        device_cols = [col for col in self.df.columns if col.startswith(f'{logical_name}_')]
        return len(device_cols) > 0
        
    def load_and_prepare_data(self) -> bool:
        """Load and prepare data"""
        try:
            self.df = pd.read_csv(self.data_file)
            logger.info(f"✅ Data loaded successfully: {len(self.df)} rows, {len(self.df.columns)} columns")
            
            # Verify required columns exist
            required_cpu_cols = ['cpu_iowait', 'cpu_usr', 'cpu_sys', 'cpu_idle', 'cpu_soft']
            required_ebs_cols = []
            
            # Find EBS device columns - use unified field format matching
            for col in self.df.columns:
                if (col.startswith('data_') and col.endswith('_util')) or \
                   (col.startswith('accounts_') and col.endswith('_util')):
                    required_ebs_cols.append(col)
                    
            missing_cols = []
            for col in required_cpu_cols:
                if col not in self.df.columns:
                    missing_cols.append(col)
                    
            if missing_cols:
                logger.error(f"❌ Missing required CPU columns: {missing_cols}")
                return False
                
            if not required_ebs_cols:
                logger.error("❌ No EBS device data columns found")
                return False
                
            logger.info(f"✅ Data validation passed, found {len(required_ebs_cols)} EBS devices")
            return True
            
        except Exception as e:
            logger.error(f"❌ Data loading failed: {e}")
            return False
    
    def run_complete_analysis(self) -> Dict:
        """Run complete 18 correlation analysis methods"""
        if not self.load_and_prepare_data():
            return {}
            
        print("🔍 Starting CPU-EBS Complete Correlation Analysis (18 methods)")
        print("=" * 60)
        
        # 1. Pearson correlation analysis (8 methods)
        pearson_results = self._analyze_pearson_correlations()
        
        # 2. Linear regression analysis (4 methods)
        regression_results = self._analyze_linear_regressions()
        
        # 3. Negative correlation analysis (2 methods)
        negative_corr_results = self._analyze_negative_correlations()
        
        # 4. Multiple regression analysis (4 methods)
        multiple_regression_results = self._analyze_multiple_regressions()
        
        # Integrate all results
        self.analysis_results = {
            'pearson_correlations': pearson_results,
            'linear_regressions': regression_results,
            'negative_correlations': negative_corr_results,
            'multiple_regressions': multiple_regression_results,
            'summary': self._generate_analysis_summary()
        }
        
        return self.analysis_results
    
    def _analyze_pearson_correlations(self) -> Dict:
        """Analyze Pearson correlations (8 analysis methods)"""
        print("\n📊 1. Pearson Correlation Analysis (8 methods)")
        
        results = {}
        
        # Find device columns - use unified field format matching
        data_util_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_util')]
        data_aqu_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_aqu_sz')]
        data_await_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_avg_await')]
        
        # ACCOUNTS device columns - only search when ACCOUNTS device is configured
        accounts_configured = self._check_device_configured('accounts')
        accounts_util_cols = []
        accounts_aqu_cols = []
        accounts_await_cols = []
        
        if accounts_configured:
            accounts_util_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_util')]
            accounts_aqu_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_aqu_sz')]
            accounts_await_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_avg_await')]
        
        # 1-4: CPU I/O wait vs device utilization/queue length/latency (DATA device)
        if data_util_cols and 'cpu_iowait' in self.df.columns:
            try:
                corr, p_value = stats.pearsonr(self.df['cpu_iowait'], self.df[data_util_cols[0]])
                results['iowait_vs_data_util'] = {
                    'correlation': corr,
                    'p_value': p_value,
                    'description': 'CPU I/O wait vs DATA device utilization',
                    'strength': self._interpret_correlation_strength(corr),
                    'method': 'pearson'
                }
                print(f"  ✅ CPU I/O wait vs DATA device utilization: {corr:.4f} (p={p_value:.4f})")
            except Exception as e:
                logger.warning(f"⚠️ CPU I/O wait vs DATA device utilization analysis failed: {e}")
        
        if data_aqu_cols and 'cpu_iowait' in self.df.columns:
            try:
                corr, p_value = stats.pearsonr(self.df['cpu_iowait'], self.df[data_aqu_cols[0]])
                results['iowait_vs_data_queue'] = {
                    'correlation': corr,
                    'p_value': p_value,
                    'description': 'CPU I/O wait vs DATA device queue length',
                    'strength': self._interpret_correlation_strength(corr),
                    'method': 'pearson'
                }
                print(f"  ✅ CPU I/O wait vs DATA device queue length: {corr:.4f} (p={p_value:.4f})")
            except Exception as e:
                logger.warning(f"⚠️ CPU I/O wait vs DATA device queue length analysis failed: {e}")
        
        if data_await_cols and 'cpu_iowait' in self.df.columns:
            try:
                corr, p_value = stats.pearsonr(self.df['cpu_iowait'], self.df[data_await_cols[0]])
                results['iowait_vs_data_latency'] = {
                    'correlation': corr,
                    'p_value': p_value,
                    'description': 'CPU I/O wait vs DATA device latency',
                    'strength': self._interpret_correlation_strength(corr),
                    'method': 'pearson'
                }
                print(f"  ✅ CPU I/O wait vs DATA device latency: {corr:.4f} (p={p_value:.4f})")
            except Exception as e:
                logger.warning(f"⚠️ CPU I/O wait vs DATA device latency analysis failed: {e}")
        
        # 5-8: Same analysis for ACCOUNTS device (only execute when ACCOUNTS device is configured)
        accounts_configured = self._check_device_configured('accounts')
        
        if accounts_configured and accounts_util_cols and 'cpu_iowait' in self.df.columns:
            corr, p_value = stats.pearsonr(self.df['cpu_iowait'], self.df[accounts_util_cols[0]])
            results['iowait_vs_accounts_util'] = {
                'correlation': corr,
                'p_value': p_value,
                'description': 'CPU I/O wait vs ACCOUNTS device utilization',
                'strength': self._interpret_correlation_strength(corr),
                'method': 'pearson'
            }
            print(f"  ✅ CPU I/O wait vs ACCOUNTS device utilization: {corr:.4f} (p={p_value:.4f})")
        
        # ACCOUNTS device queue length analysis (only execute when ACCOUNTS device is configured)
        if accounts_configured and accounts_aqu_cols and 'cpu_iowait' in self.df.columns:
            corr, p_value = stats.pearsonr(self.df['cpu_iowait'], self.df[accounts_aqu_cols[0]])
            results['iowait_vs_accounts_queue'] = {
                'correlation': corr,
                'p_value': p_value,
                'description': 'CPU I/O wait vs ACCOUNTS device queue length',
                'strength': self._interpret_correlation_strength(corr),
                'method': 'pearson'
            }
            print(f"  ✅ CPU I/O wait vs ACCOUNTS device queue length: {corr:.4f} (p={p_value:.4f})")
        
        # ACCOUNTS device latency analysis (only execute when ACCOUNTS device is configured)
        if accounts_configured and accounts_await_cols and 'cpu_iowait' in self.df.columns:
            corr, p_value = stats.pearsonr(self.df['cpu_iowait'], self.df[accounts_await_cols[0]])
            results['iowait_vs_accounts_latency'] = {
                'correlation': corr,
                'p_value': p_value,
                'description': 'CPU I/O wait vs ACCOUNTS device latency',
                'strength': self._interpret_correlation_strength(corr),
                'method': 'pearson'
            }
            print(f"  ✅ CPU I/O wait vs ACCOUNTS device latency: {corr:.4f} (p={p_value:.4f})")
        elif not accounts_configured:
            print(f"  ⚠️  Skipping ACCOUNTS device analysis (ACCOUNTS device not configured)")
        
        return results
    
    def _analyze_linear_regressions(self) -> Dict:
        """Analyze linear regressions (4 analysis methods)"""
        print("\n📈 2. Linear Regression Analysis (4 methods)")
        
        results = {}
        
        # Find read/write request columns - use unified field format matching
        data_r_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_r_s')]
        data_w_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_w_s')]
        
        # ACCOUNTS device columns - only search when ACCOUNTS device is configured
        accounts_configured = self._check_device_configured('accounts')
        accounts_r_cols = []
        accounts_w_cols = []
        
        if accounts_configured:
            accounts_r_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_r_s')]
            accounts_w_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_w_s')]
        
        # 1-2: User CPU vs read requests, System CPU vs write requests (DATA device)
        if data_r_cols and 'cpu_usr' in self.df.columns:
            x = self.df[['cpu_usr']].values
            y = self.df[data_r_cols[0]].values
            
            model = LinearRegression()
            model.fit(x, y)
            r2 = r2_score(y, model.predict(x))
            
            results['usr_cpu_vs_data_reads'] = {
                'r_squared': r2,
                'coefficient': model.coef_[0],
                'intercept': model.intercept_,
                'description': 'User CPU usage vs DATA device read requests',
                'method': 'linear_regression'
            }
            print(f"  ✅ User CPU vs DATA read requests: R²={r2:.4f}, coefficient={model.coef_[0]:.4f}")
        
        if data_w_cols and 'cpu_sys' in self.df.columns:
            x = self.df[['cpu_sys']].values
            y = self.df[data_w_cols[0]].values
            
            model = LinearRegression()
            model.fit(x, y)
            r2 = r2_score(y, model.predict(x))
            
            results['sys_cpu_vs_data_writes'] = {
                'r_squared': r2,
                'coefficient': model.coef_[0],
                'intercept': model.intercept_,
                'description': 'System CPU usage vs DATA device write requests',
                'method': 'linear_regression'
            }
            print(f"  ✅ System CPU vs DATA write requests: R²={r2:.4f}, coefficient={model.coef_[0]:.4f}")
        
        # 3-4: Same analysis for ACCOUNTS device (only execute when ACCOUNTS device is configured)
        accounts_configured = self._check_device_configured('accounts')
        
        if accounts_configured and accounts_r_cols and 'cpu_usr' in self.df.columns:
            x = self.df[['cpu_usr']].values
            y = self.df[accounts_r_cols[0]].values
            
            model = LinearRegression()
            model.fit(x, y)
            r2 = r2_score(y, model.predict(x))
            
            results['usr_cpu_vs_accounts_reads'] = {
                'r_squared': r2,
                'coefficient': model.coef_[0],
                'intercept': model.intercept_,
                'description': 'User CPU usage vs ACCOUNTS device read requests',
                'method': 'linear_regression'
            }
            print(f"  ✅ User CPU vs ACCOUNTS read requests: R²={r2:.4f}, coefficient={model.coef_[0]:.4f}")
        
        # ACCOUNTS device write request analysis (only execute when ACCOUNTS device is configured)
        if accounts_configured and accounts_w_cols and 'cpu_sys' in self.df.columns:
            x = self.df[['cpu_sys']].values
            y = self.df[accounts_w_cols[0]].values
            
            model = LinearRegression()
            model.fit(x, y)
            r2 = r2_score(y, model.predict(x))
            
            results['sys_cpu_vs_accounts_writes'] = {
                'r_squared': r2,
                'coefficient': model.coef_[0],
                'intercept': model.intercept_,
                'description': 'System CPU usage vs ACCOUNTS device write requests',
                'method': 'linear_regression'
            }
            print(f"  ✅ System CPU vs ACCOUNTS write requests: R²={r2:.4f}, coefficient={model.coef_[0]:.4f}")
        elif not accounts_configured:
            print(f"  ⚠️  Skipping ACCOUNTS device linear regression analysis (ACCOUNTS device not configured)")
        
        return results
    
    def _analyze_negative_correlations(self) -> Dict:
        """Analyze negative correlations (2 analysis methods)"""
        print("\n📉 3. Negative Correlation Analysis (2 methods)")
        
        results = {}
        
        # Find queue length columns - use unified field format matching
        data_aqu_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_aqu_sz')]
        
        # ACCOUNTS device columns - only search when ACCOUNTS device is configured
        accounts_configured = self._check_device_configured('accounts')
        accounts_aqu_cols = []
        
        if accounts_configured:
            accounts_aqu_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_aqu_sz')]
        
        # 1: CPU idle vs DATA device I/O queue length
        if data_aqu_cols and 'cpu_idle' in self.df.columns:
            corr, p_value = stats.pearsonr(self.df['cpu_idle'], self.df[data_aqu_cols[0]])
            results['idle_vs_data_queue'] = {
                'correlation': corr,
                'p_value': p_value,
                'description': 'CPU idle time vs DATA device I/O queue length',
                'is_negative': corr < 0,
                'strength': self._interpret_correlation_strength(abs(corr)),
                'method': 'negative_correlation'
            }
            print(f"  ✅ CPU idle vs DATA queue length: {corr:.4f} ({'negative correlation' if corr < 0 else 'positive correlation'})")
        
        # 2: CPU idle vs ACCOUNTS device I/O queue length (only execute when ACCOUNTS device is configured)
        accounts_configured = self._check_device_configured('accounts')
        
        if accounts_configured and accounts_aqu_cols and 'cpu_idle' in self.df.columns:
            corr, p_value = stats.pearsonr(self.df['cpu_idle'], self.df[accounts_aqu_cols[0]])
            results['idle_vs_accounts_queue'] = {
                'correlation': corr,
                'p_value': p_value,
                'description': 'CPU idle time vs ACCOUNTS device I/O queue length',
                'is_negative': corr < 0,
                'strength': self._interpret_correlation_strength(abs(corr)),
                'method': 'negative_correlation'
            }
            print(f"  ✅ CPU idle vs ACCOUNTS queue length: {corr:.4f} ({'negative correlation' if corr < 0 else 'positive correlation'})")
        elif not accounts_configured:
            print(f"  ⚠️  Skipping ACCOUNTS device negative correlation analysis (ACCOUNTS device not configured)")
        
        return results
    
    def _analyze_multiple_regressions(self) -> Dict:
        """Analyze multiple regressions (4 analysis methods)"""
        print("\n📊 4. Multiple Regression Analysis (4 methods)")
        
        results = {}
        
        # Find related columns - use unified field format matching
        data_rrqm_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_rrqm_s')]
        data_wrqm_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_wrqm_s')]
        data_rareq_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_rareq_sz')]
        data_wareq_cols = [col for col in self.df.columns if col.startswith('data_') and col.endswith('_wareq_sz')]
        
        # Check if ACCOUNTS device is configured
        accounts_configured = self._check_device_configured('accounts')
        
        # ACCOUNTS device related columns - only search when ACCOUNTS device is configured
        accounts_rrqm_cols = []
        accounts_wrqm_cols = []
        accounts_rareq_cols = []
        accounts_wareq_cols = []
        
        if accounts_configured:
            accounts_rrqm_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_rrqm_s')]
            accounts_wrqm_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_wrqm_s')]
            accounts_rareq_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_rareq_sz')]
            accounts_wareq_cols = [col for col in self.df.columns if col.startswith('accounts_') and col.endswith('_wareq_sz')]
        
        # 1: Soft interrupt vs I/O request merge (DATA device)
        if data_rrqm_cols and data_wrqm_cols and 'cpu_soft' in self.df.columns:
            try:
                x = self.df[[data_rrqm_cols[0], data_wrqm_cols[0]]].values
                y = self.df['cpu_soft'].values
                
                # Add constant term
                x_with_const = sm.add_constant(x)
                model = sm.OLS(y, x_with_const).fit()
                
                results['soft_vs_data_merge'] = {
                    'r_squared': model.rsquared,
                    'coefficients': model.params.tolist(),
                    'p_values': model.pvalues.tolist(),
                    'description': 'Soft interrupt processing vs DATA device I/O request merge',
                    'method': 'multiple_regression'
                }
                print(f"  ✅ Soft interrupt vs DATA device I/O merge: R²={model.rsquared:.4f}")
            except Exception as e:
                logger.warning(f"Multiple regression analysis failed: {e}")
        
        # 2: CPU usage vs I/O request size (DATA device)
        if data_rareq_cols and data_wareq_cols and 'cpu_usr' in self.df.columns and 'cpu_sys' in self.df.columns:
            try:
                x = self.df[[data_rareq_cols[0], data_wareq_cols[0]]].values
                y = (self.df['cpu_usr'] + self.df['cpu_sys']).values
                
                x_with_const = sm.add_constant(x)
                model = sm.OLS(y, x_with_const).fit()
                
                results['cpu_vs_data_io_size'] = {
                    'r_squared': model.rsquared,
                    'coefficients': model.params.tolist(),
                    'p_values': model.pvalues.tolist(),
                    'description': 'CPU usage vs DATA device I/O request size',
                    'method': 'multiple_regression'
                }
                print(f"  ✅ CPU usage vs DATA device I/O size: R²={model.rsquared:.4f}")
            except Exception as e:
                logger.warning(f"Multiple regression analysis failed: {e}")
        
        # 3-4: Same analysis for ACCOUNTS device (only execute when ACCOUNTS device is configured)
        accounts_configured = self._check_device_configured('accounts')
        
        # 3: Soft interrupt vs I/O request merge (ACCOUNTS device)
        if accounts_configured and accounts_rrqm_cols and accounts_wrqm_cols and 'cpu_soft' in self.df.columns:
            try:
                x = self.df[[accounts_rrqm_cols[0], accounts_wrqm_cols[0]]].values
                y = self.df['cpu_soft'].values
                
                # Add constant term
                x_with_const = sm.add_constant(x)
                model = sm.OLS(y, x_with_const).fit()
                
                results['soft_vs_accounts_merge'] = {
                    'r_squared': model.rsquared,
                    'coefficients': model.params.tolist(),
                    'p_values': model.pvalues.tolist(),
                    'description': 'Soft interrupt processing vs ACCOUNTS device I/O request merge',
                    'method': 'multiple_regression'
                }
                print(f"  ✅ Soft interrupt vs ACCOUNTS device I/O merge: R²={model.rsquared:.4f}")
            except Exception as e:
                logger.warning(f"ACCOUNTS device multiple regression analysis failed: {e}")
        
        # 4: CPU usage vs I/O request size (ACCOUNTS device)
        if accounts_configured and accounts_rareq_cols and accounts_wareq_cols and 'cpu_usr' in self.df.columns and 'cpu_sys' in self.df.columns:
            try:
                x = self.df[[accounts_rareq_cols[0], accounts_wareq_cols[0]]].values
                y = (self.df['cpu_usr'] + self.df['cpu_sys']).values
                
                x_with_const = sm.add_constant(x)
                model = sm.OLS(y, x_with_const).fit()
                
                results['cpu_vs_accounts_io_size'] = {
                    'r_squared': model.rsquared,
                    'coefficients': model.params.tolist(),
                    'p_values': model.pvalues.tolist(),
                    'description': 'CPU usage vs ACCOUNTS device I/O request size',
                    'method': 'multiple_regression'
                }
                print(f"  ✅ CPU usage vs ACCOUNTS device I/O size: R²={model.rsquared:.4f}")
            except Exception as e:
                logger.warning(f"ACCOUNTS device multiple regression analysis failed: {e}")
        elif not accounts_configured:
            print(f"  ⚠️  Skipping ACCOUNTS device multiple regression analysis (ACCOUNTS device not configured)")
        
        return results
    
    def _interpret_correlation_strength(self, corr: float) -> str:
        """Interpret correlation strength"""
        abs_corr = abs(corr)
        if abs_corr >= 0.8:
            return "very strong"
        elif abs_corr >= 0.6:
            return "strong"
        elif abs_corr >= 0.4:
            return "moderate"
        elif abs_corr >= 0.2:
            return "weak"
        else:
            return "very weak"
    
    def _generate_analysis_summary(self) -> Dict:
        """Generate analysis summary"""
        summary = {
            'total_analyses': 0,
            'significant_correlations': 0,
            'strong_correlations': [],
            'recommendations': []
        }
        
        # Count all analyses
        for category in ['pearson_correlations', 'linear_regressions', 'negative_correlations', 'multiple_regressions']:
            if category in self.analysis_results:
                summary['total_analyses'] += len(self.analysis_results[category])
        
        # Find strong correlations
        if 'pearson_correlations' in self.analysis_results:
            for name, result in self.analysis_results['pearson_correlations'].items():
                if abs(result.get('correlation', 0)) >= 0.6:
                    summary['strong_correlations'].append({
                        'name': name,
                        'correlation': result['correlation'],
                        'description': result['description']
                    })
        
        # Generate recommendations
        if len(summary['strong_correlations']) > 0:
            summary['recommendations'].append("Strong correlations found, can be used for performance prediction and optimization")
        
        return summary
    
    def generate_comprehensive_report(self) -> str:
        """Generate complete analysis report"""
        if not self.analysis_results:
            return "❌ Analysis not executed, cannot generate report"
        
        report = f"""
# CPU-EBS Performance Correlation Complete Analysis Report
Generation time: {pd.Timestamp.now()}

## Analysis Overview
- **Total analyses**: {self.analysis_results['summary']['total_analyses']}
- **Strong correlations**: {len(self.analysis_results['summary']['strong_correlations'])}
- **Data points**: {len(self.df) if self.df is not None else 0}

## 1. Pearson Correlation Analysis Results (8 methods)
"""
        
        if 'pearson_correlations' in self.analysis_results:
            for name, result in self.analysis_results['pearson_correlations'].items():
                report += f"""
### {result['description']}
- **Correlation coefficient**: {result['correlation']:.4f}
- **P-value**: {result['p_value']:.4f}
- **Correlation strength**: {result['strength']}
- **Statistical significance**: {'Yes' if result['p_value'] < 0.05 else 'No'}
"""
        
        report += "\n## 2. Linear Regression Analysis Results (4 methods)\n"
        if 'linear_regressions' in self.analysis_results:
            for name, result in self.analysis_results['linear_regressions'].items():
                report += f"""
### {result['description']}
- **R² value**: {result['r_squared']:.4f}
- **Regression coefficient**: {result['coefficient']:.4f}
- **Intercept**: {result['intercept']:.4f}
- **Model quality**: {'Good' if result['r_squared'] > 0.5 else 'Moderate' if result['r_squared'] > 0.3 else 'Poor'}
"""
        
        report += "\n## 3. Negative Correlation Analysis Results (2 methods)\n"
        if 'negative_correlations' in self.analysis_results:
            for name, result in self.analysis_results['negative_correlations'].items():
                report += f"""
### {result['description']}
- **Correlation coefficient**: {result['correlation']:.4f}
- **Is negative correlation**: {'Yes' if result['is_negative'] else 'No'}
- **Correlation strength**: {result['strength']}
"""
        
        report += "\n## 4. Multiple Regression Analysis Results (4 methods)\n"
        if 'multiple_regressions' in self.analysis_results:
            for name, result in self.analysis_results['multiple_regressions'].items():
                report += f"""
### {result['description']}
- **R² value**: {result['r_squared']:.4f}
- **Model significance**: {'Significant' if result['r_squared'] > 0.3 else 'Not significant'}
"""
        
        report += f"""
## Analysis Conclusions and Recommendations

### Strong Correlations Found
"""
        for corr in self.analysis_results['summary']['strong_correlations']:
            report += f"- **{corr['description']}**: {corr['correlation']:.4f}\n"
        
        report += f"""
### Optimization Recommendations
"""
        for rec in self.analysis_results['summary']['recommendations']:
            report += f"- {rec}\n"
        
        return report


# Usage example
if __name__ == "__main__":
    print("📋 CPU-EBS Correlation Analyzer usage example:")
    print("analyzer = CPUEBSCorrelationAnalyzer('performance_data.csv')")
    print("results = analyzer.run_complete_analysis()")
    print("report = analyzer.generate_comprehensive_report()")
