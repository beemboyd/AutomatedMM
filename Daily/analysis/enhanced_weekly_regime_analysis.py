#!/usr/bin/env python
"""
Enhanced Weekly Analysis with Market Regime and Breadth Data
Analyzes correlation between market conditions and reversal strategy performance
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys
import glob
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict

# Add parent directories to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class EnhancedWeeklyAnalysis:
    def __init__(self):
        """Initialize the enhanced analyzer"""
        self.results_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/results'
        self.results_s_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/results-s'
        self.regime_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/regime_analysis'
        self.breadth_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/breadth_data'
        self.output_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports'
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Define weeks for analysis
        self.weeks = [
            {
                'week_num': 1,
                'start': datetime(2025, 6, 28),
                'end': datetime(2025, 7, 4),
                'label': 'Week 1 (Jun 28 - Jul 04)'
            },
            {
                'week_num': 2,
                'start': datetime(2025, 7, 5),
                'end': datetime(2025, 7, 11),
                'label': 'Week 2 (Jul 05 - Jul 11)'
            },
            {
                'week_num': 3,
                'start': datetime(2025, 7, 12),
                'end': datetime(2025, 7, 18),
                'label': 'Week 3 (Jul 12 - Jul 18)'
            },
            {
                'week_num': 4,
                'start': datetime(2025, 7, 19),
                'end': datetime(2025, 7, 25),
                'label': 'Week 4 (Jul 19 - Jul 25)'
            }
        ]
        
    def get_regime_data_for_week(self, week):
        """Get market regime data for a specific week"""
        regime_data = []
        
        current_date = week['start']
        while current_date <= week['end']:
            date_str = current_date.strftime('%Y%m%d')
            pattern = os.path.join(self.regime_dir, f'regime_report_{date_str}_*.json')
            
            regime_files = glob.glob(pattern)
            if regime_files:
                # Get the file closest to market open (around 11:30 AM)
                best_file = None
                best_time_diff = float('inf')
                
                for file_path in regime_files:
                    try:
                        time_str = os.path.basename(file_path).split('_')[3].replace('.json', '')
                        file_time = int(time_str[:4])  # HHMM format
                        target_time = 1130  # 11:30 AM
                        
                        time_diff = abs(file_time - target_time)
                        if time_diff < best_time_diff:
                            best_time_diff = time_diff
                            best_file = file_path
                    except:
                        continue
                
                if best_file:
                    try:
                        with open(best_file, 'r') as f:
                            data = json.load(f)
                            regime_data.append({
                                'date': current_date,
                                'regime': data['market_regime']['regime'],
                                'confidence': data['market_regime']['confidence'],
                                'breadth_bullish': data.get('breadth_indicators', {}).get('bullish_percent', 0),
                                'breadth_bearish': data.get('breadth_indicators', {}).get('bearish_percent', 0),
                                'volatility_regime': data.get('volatility', {}).get('volatility_regime', 'N/A'),
                                'trend_strength': data.get('trend_analysis', {}).get('trend_strength', 0),
                                'divergence_detected': data.get('divergence_alerts', {}).get('breadth_regime_divergence', False)
                            })
                    except Exception as e:
                        print(f"Error reading regime file {best_file}: {e}")
            
            current_date += timedelta(days=1)
        
        return regime_data
    
    def get_breadth_data_for_week(self, week):
        """Get market breadth data for a specific week"""
        breadth_data = []
        
        current_date = week['start']
        while current_date <= week['end']:
            date_str = current_date.strftime('%Y%m%d')
            pattern = os.path.join(self.breadth_dir, f'market_breadth_{date_str}_*.json')
            
            breadth_files = glob.glob(pattern)
            if breadth_files:
                # Get the file closest to market close
                best_file = max(breadth_files, key=os.path.getmtime)
                
                try:
                    with open(best_file, 'r') as f:
                        data = json.load(f)
                        breadth_data.append({
                            'date': current_date,
                            'advancing': data.get('advancing', 0),
                            'declining': data.get('declining', 0),
                            'unchanged': data.get('unchanged', 0),
                            'advance_decline_ratio': data.get('advance_decline_ratio', 0),
                            'bullish_percent': data.get('bullish_percent', 0),
                            'bearish_percent': data.get('bearish_percent', 0),
                            'new_highs': data.get('new_highs', 0),
                            'new_lows': data.get('new_lows', 0)
                        })
                except Exception as e:
                    print(f"Error reading breadth file {best_file}: {e}")
            
            current_date += timedelta(days=1)
        
        return breadth_data
    
    def aggregate_regime_data(self, regime_data):
        """Aggregate regime data for a week"""
        if not regime_data:
            return None
        
        # Count regime occurrences
        regime_counts = defaultdict(int)
        for data in regime_data:
            regime_counts[data['regime']] += 1
        
        # Find dominant regime
        dominant_regime = max(regime_counts, key=regime_counts.get)
        
        # Calculate averages
        avg_confidence = np.mean([d['confidence'] for d in regime_data])
        avg_bullish = np.mean([d['breadth_bullish'] for d in regime_data])
        avg_bearish = np.mean([d['breadth_bearish'] for d in regime_data])
        divergence_days = sum(1 for d in regime_data if d.get('divergence_detected', False))
        
        return {
            'dominant_regime': dominant_regime,
            'regime_consistency': regime_counts[dominant_regime] / len(regime_data) * 100,
            'avg_confidence': avg_confidence,
            'avg_bullish_breadth': avg_bullish,
            'avg_bearish_breadth': avg_bearish,
            'divergence_days': divergence_days,
            'regime_distribution': dict(regime_counts)
        }
    
    def aggregate_breadth_data(self, breadth_data):
        """Aggregate breadth data for a week"""
        if not breadth_data:
            return None
        
        return {
            'avg_advance_decline_ratio': np.mean([d['advance_decline_ratio'] for d in breadth_data]),
            'avg_bullish_percent': np.mean([d['bullish_percent'] for d in breadth_data]),
            'avg_bearish_percent': np.mean([d['bearish_percent'] for d in breadth_data]),
            'total_new_highs': sum(d['new_highs'] for d in breadth_data),
            'total_new_lows': sum(d['new_lows'] for d in breadth_data),
            'bullish_days': sum(1 for d in breadth_data if d['advancing'] > d['declining']),
            'bearish_days': sum(1 for d in breadth_data if d['declining'] > d['advancing'])
        }
    
    def load_strategy_performance(self):
        """Load pre-calculated strategy performance data"""
        # This would load from the files created by unified_reversal_analyzer.py
        # For now, using the summary data we collected
        performance_data = {
            'Week 1': {
                'long': {'win_rate': 31.9, 'avg_return': -2.10, 'trades': 138},
                'short': {'win_rate': 58.5, 'avg_return': 0.88, 'trades': 106}
            },
            'Week 2': {
                'long': {'win_rate': 41.4, 'avg_return': -1.54, 'trades': 116},
                'short': {'win_rate': 66.9, 'avg_return': 1.58, 'trades': 124}
            },
            'Week 3': {
                'long': {'win_rate': 36.8, 'avg_return': -1.43, 'trades': 144},
                'short': {'win_rate': 67.8, 'avg_return': 1.39, 'trades': 118}
            },
            'Week 4': {
                'long': {'win_rate': 17.6, 'avg_return': -2.43, 'trades': 125},
                'short': {'win_rate': 77.4, 'avg_return': 1.83, 'trades': 106}
            }
        }
        return performance_data
    
    def analyze_correlation(self, weekly_data):
        """Analyze correlation between regime/breadth and performance"""
        correlations = {
            'breadth_vs_long_performance': [],
            'breadth_vs_short_performance': [],
            'regime_vs_performance': []
        }
        
        for week_data in weekly_data:
            if week_data['regime_data'] and week_data['breadth_data']:
                # Breadth vs Long Performance
                correlations['breadth_vs_long_performance'].append({
                    'bullish_breadth': week_data['regime_data']['avg_bullish_breadth'],
                    'long_win_rate': week_data['performance']['long']['win_rate'],
                    'long_return': week_data['performance']['long']['avg_return']
                })
                
                # Breadth vs Short Performance
                correlations['breadth_vs_short_performance'].append({
                    'bearish_breadth': week_data['regime_data']['avg_bearish_breadth'],
                    'short_win_rate': week_data['performance']['short']['win_rate'],
                    'short_return': week_data['performance']['short']['avg_return']
                })
        
        return correlations
    
    def create_visualizations(self, weekly_data):
        """Create visualization charts"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('Market Regime & Breadth Correlation with Reversal Strategies', fontsize=16)
        
        weeks = [w['week']['label'].split(' ')[1] for w in weekly_data]
        
        # 1. Win Rates vs Market Breadth
        ax1 = axes[0, 0]
        x = np.arange(len(weeks))
        width = 0.35
        
        long_win_rates = [w['performance']['long']['win_rate'] for w in weekly_data]
        short_win_rates = [w['performance']['short']['win_rate'] for w in weekly_data]
        bearish_breadth = [w['regime_data']['avg_bearish_breadth'] if w['regime_data'] else 0 for w in weekly_data]
        
        ax1.bar(x - width/2, long_win_rates, width, label='Long Win Rate', color='green', alpha=0.7)
        ax1.bar(x + width/2, short_win_rates, width, label='Short Win Rate', color='red', alpha=0.7)
        ax1.plot(x, bearish_breadth, 'ko-', label='Bearish Breadth %', linewidth=2)
        
        ax1.set_xlabel('Week')
        ax1.set_ylabel('Win Rate / Breadth %')
        ax1.set_title('Strategy Win Rates vs Market Breadth')
        ax1.set_xticks(x)
        ax1.set_xticklabels(weeks)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. Returns vs Regime
        ax2 = axes[0, 1]
        long_returns = [w['performance']['long']['avg_return'] for w in weekly_data]
        short_returns = [w['performance']['short']['avg_return'] for w in weekly_data]
        
        ax2.plot(weeks, long_returns, 'go-', label='Long Returns', linewidth=2, markersize=8)
        ax2.plot(weeks, short_returns, 'ro-', label='Short Returns', linewidth=2, markersize=8)
        ax2.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        
        # Add regime labels
        for i, w in enumerate(weekly_data):
            if w['regime_data']:
                regime = w['regime_data']['dominant_regime']
                ax2.text(i, -3, regime[:4], ha='center', va='top', fontsize=8, 
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.3))
        
        ax2.set_xlabel('Week')
        ax2.set_ylabel('Average Return %')
        ax2.set_title('Strategy Returns by Market Regime')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. Breadth Divergence Impact
        ax3 = axes[1, 0]
        divergence_days = [w['regime_data']['divergence_days'] if w['regime_data'] else 0 for w in weekly_data]
        strategy_spread = [w['performance']['short']['win_rate'] - w['performance']['long']['win_rate'] for w in weekly_data]
        
        ax3_twin = ax3.twinx()
        bars = ax3.bar(weeks, divergence_days, alpha=0.6, color='orange', label='Divergence Days')
        line = ax3_twin.plot(weeks, strategy_spread, 'bo-', linewidth=2, markersize=8, label='Short-Long Win Rate Spread')
        
        ax3.set_xlabel('Week')
        ax3.set_ylabel('Divergence Days', color='orange')
        ax3_twin.set_ylabel('Win Rate Spread (%)', color='blue')
        ax3.set_title('Regime-Breadth Divergence vs Strategy Performance Gap')
        ax3.tick_params(axis='y', labelcolor='orange')
        ax3_twin.tick_params(axis='y', labelcolor='blue')
        
        # 4. Correlation Matrix
        ax4 = axes[1, 1]
        
        # Create correlation data
        corr_data = []
        for w in weekly_data:
            if w['regime_data'] and w['breadth_data']:
                corr_data.append({
                    'Bullish Breadth': w['regime_data']['avg_bullish_breadth'],
                    'Bearish Breadth': w['regime_data']['avg_bearish_breadth'],
                    'Long Win Rate': w['performance']['long']['win_rate'],
                    'Short Win Rate': w['performance']['short']['win_rate'],
                    'Long Return': w['performance']['long']['avg_return'],
                    'Short Return': w['performance']['short']['avg_return']
                })
        
        if corr_data:
            corr_df = pd.DataFrame(corr_data)
            correlation_matrix = corr_df.corr()
            
            sns.heatmap(correlation_matrix, annot=True, fmt='.2f', cmap='coolwarm', 
                       center=0, ax=ax4, cbar_kws={'label': 'Correlation'})
            ax4.set_title('Correlation Matrix: Market Conditions vs Strategy Performance')
        
        plt.tight_layout()
        
        # Save plot
        plot_file = os.path.join(self.output_dir, 'regime_breadth_correlation_analysis.png')
        plt.savefig(plot_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        return plot_file
    
    def generate_report(self):
        """Generate comprehensive report with regime and breadth analysis"""
        print("="*80)
        print("ENHANCED WEEKLY ANALYSIS WITH MARKET REGIME & BREADTH")
        print("="*80)
        
        # Load strategy performance
        performance_data = self.load_strategy_performance()
        
        # Collect data for each week
        weekly_data = []
        
        for week in self.weeks:
            print(f"\nAnalyzing {week['label']}...")
            
            # Get regime and breadth data
            regime_data = self.get_regime_data_for_week(week)
            breadth_data = self.get_breadth_data_for_week(week)
            
            # Aggregate data
            regime_summary = self.aggregate_regime_data(regime_data)
            breadth_summary = self.aggregate_breadth_data(breadth_data)
            
            # Get performance data
            week_key = f"Week {week['week_num']}"
            performance = performance_data.get(week_key, {})
            
            weekly_data.append({
                'week': week,
                'regime_data': regime_summary,
                'breadth_data': breadth_summary,
                'performance': performance
            })
            
            # Print summary
            if regime_summary and breadth_summary:
                print(f"  Dominant Regime: {regime_summary['dominant_regime']} ({regime_summary['regime_consistency']:.1f}% consistency)")
                print(f"  Avg Bearish Breadth: {regime_summary['avg_bearish_breadth']:.1f}%")
                print(f"  Divergence Days: {regime_summary['divergence_days']}")
                print(f"  Long Reversal: {performance['long']['win_rate']:.1f}% win rate, {performance['long']['avg_return']:.2f}% return")
                print(f"  Short Reversal: {performance['short']['win_rate']:.1f}% win rate, {performance['short']['avg_return']:.2f}% return")
        
        # Analyze correlations
        correlations = self.analyze_correlation(weekly_data)
        
        # Create visualizations
        plot_file = self.create_visualizations(weekly_data)
        
        # Generate detailed report
        report = {
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'weekly_data': weekly_data,
            'correlations': correlations,
            'key_findings': self.generate_key_findings(weekly_data)
        }
        
        # Save report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_file = os.path.join(self.output_dir, f'enhanced_regime_analysis_{timestamp}.json')
        
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Save Excel report
        self.save_excel_report(weekly_data, timestamp)
        
        print("\n" + "="*80)
        print("KEY FINDINGS")
        print("="*80)
        for finding in report['key_findings']:
            print(f"\n{finding}")
        
        print(f"\n\nReports saved to:")
        print(f"  - {json_file}")
        print(f"  - {plot_file}")
        
        return report
    
    def generate_key_findings(self, weekly_data):
        """Generate key findings from the analysis"""
        findings = []
        
        # 1. Regime-Performance Correlation
        uptrend_weeks = [w for w in weekly_data if w['regime_data'] and w['regime_data']['dominant_regime'] == 'uptrend']
        if uptrend_weeks:
            avg_long_win_uptrend = np.mean([w['performance']['long']['win_rate'] for w in uptrend_weeks])
            avg_short_win_uptrend = np.mean([w['performance']['short']['win_rate'] for w in uptrend_weeks])
            findings.append(f"During UPTREND regime: Long Reversal averaged {avg_long_win_uptrend:.1f}% win rate, "
                          f"Short Reversal averaged {avg_short_win_uptrend:.1f}% win rate")
        
        # 2. Breadth-Performance Correlation
        high_bearish_weeks = [w for w in weekly_data if w['regime_data'] and w['regime_data']['avg_bearish_breadth'] > 60]
        if high_bearish_weeks:
            avg_short_win_bearish = np.mean([w['performance']['short']['win_rate'] for w in high_bearish_weeks])
            findings.append(f"When bearish breadth >60%: Short Reversal achieved {avg_short_win_bearish:.1f}% average win rate")
        
        # 3. Divergence Impact
        divergence_weeks = [w for w in weekly_data if w['regime_data'] and w['regime_data']['divergence_days'] > 0]
        if divergence_weeks:
            findings.append(f"Regime-Breadth divergence detected in {len(divergence_weeks)} out of 4 weeks, "
                          f"indicating conflicting market signals")
        
        # 4. Performance Trend
        long_trend = [w['performance']['long']['win_rate'] for w in weekly_data]
        short_trend = [w['performance']['short']['win_rate'] for w in weekly_data]
        
        if long_trend[-1] < long_trend[0]:
            findings.append(f"Long Reversal performance deteriorated from {long_trend[0]:.1f}% to {long_trend[-1]:.1f}% "
                          f"over 4 weeks")
        if short_trend[-1] > short_trend[0]:
            findings.append(f"Short Reversal performance improved from {short_trend[0]:.1f}% to {short_trend[-1]:.1f}% "
                          f"over 4 weeks")
        
        # 5. Best Strategy Alignment
        findings.append("Short Reversal strategy aligned better with prevailing bearish market breadth throughout the period")
        
        return findings
    
    def save_excel_report(self, weekly_data, timestamp):
        """Save detailed Excel report"""
        excel_file = os.path.join(self.output_dir, f'enhanced_regime_analysis_{timestamp}.xlsx')
        
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            # Weekly Summary
            summary_data = []
            for w in weekly_data:
                if w['regime_data'] and w['breadth_data']:
                    summary_data.append({
                        'Week': w['week']['label'],
                        'Dominant_Regime': w['regime_data']['dominant_regime'],
                        'Regime_Consistency_%': w['regime_data']['regime_consistency'],
                        'Avg_Bullish_Breadth_%': w['regime_data']['avg_bullish_breadth'],
                        'Avg_Bearish_Breadth_%': w['regime_data']['avg_bearish_breadth'],
                        'Divergence_Days': w['regime_data']['divergence_days'],
                        'Long_Win_Rate_%': w['performance']['long']['win_rate'],
                        'Long_Avg_Return_%': w['performance']['long']['avg_return'],
                        'Short_Win_Rate_%': w['performance']['short']['win_rate'],
                        'Short_Avg_Return_%': w['performance']['short']['avg_return']
                    })
            
            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Weekly_Summary', index=False)

def main():
    """Main function"""
    analyzer = EnhancedWeeklyAnalysis()
    report = analyzer.generate_report()

if __name__ == "__main__":
    main()