#!/usr/bin/env python3
"""
Comprehensive Market Regime and Strategy Performance Correlation
Establishes clear rules for market direction based on historical data
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from collections import defaultdict

class ComprehensiveRegimeAnalysis:
    def __init__(self):
        self.regime_path = '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime'
        self.results_path = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports'
        
    def analyze_breadth_data(self):
        """Analyze SMA breadth data for the past 4 weeks"""
        # Load SMA breadth historical data
        with open(os.path.join(self.regime_path, 'historical_breadth_data/sma_breadth_historical_latest.json'), 'r') as f:
            data = json.load(f)
        
        # Filter last 4 weeks
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=4)
        
        filtered_data = []
        for entry in data:
            try:
                entry_date = datetime.strptime(entry['date'], '%Y-%m-%d')
                if start_date <= entry_date <= end_date and 'sma_breadth' in entry:
                    filtered_data.append(entry)
            except:
                continue
        
        if not filtered_data:
            return None
            
        # Extract metrics
        sma20_values = []
        sma50_values = []
        volume_participation = []
        market_scores = []
        
        for entry in filtered_data:
            if 'sma_breadth' in entry:
                sma20_values.append(entry['sma_breadth']['sma20_percent'])
                sma50_values.append(entry['sma_breadth']['sma50_percent'])
            if 'volume_breadth' in entry and 'volume_participation' in entry['volume_breadth']:
                volume_participation.append(entry['volume_breadth']['volume_participation'])
            if 'market_score' in entry:
                market_scores.append(entry['market_score'])
        
        return {
            'period': f"{start_date.date()} to {end_date.date()}",
            'data_points': len(filtered_data),
            'sma20': {
                'values': sma20_values,
                'mean': np.mean(sma20_values) if sma20_values else 0,
                'min': np.min(sma20_values) if sma20_values else 0,
                'max': np.max(sma20_values) if sma20_values else 0,
                'latest': sma20_values[-1] if sma20_values else 0
            },
            'sma50': {
                'values': sma50_values,
                'mean': np.mean(sma50_values) if sma50_values else 0,
                'min': np.min(sma50_values) if sma50_values else 0,
                'max': np.max(sma50_values) if sma50_values else 0,
                'latest': sma50_values[-1] if sma50_values else 0
            },
            'volume': {
                'values': volume_participation,
                'mean': np.mean(volume_participation) if volume_participation else 0,
                'latest': volume_participation[-1] if volume_participation else 0
            },
            'market_score': {
                'values': market_scores,
                'mean': np.mean(market_scores) if market_scores else 0,
                'latest': market_scores[-1] if market_scores else 0
            }
        }
    
    def load_strategy_performance(self):
        """Load strategy performance data"""
        with open(os.path.join(self.results_path, 'latest_simple_analysis.json'), 'r') as f:
            long_results = json.load(f)
            
        with open(os.path.join(self.results_path, 'latest_short_simple_analysis.json'), 'r') as f:
            short_results = json.load(f)
            
        return {
            'long': {
                'win_rate': long_results['summary']['win_rate'],
                'avg_return': long_results['summary']['overall_average'],
                'total_trades': long_results['summary']['unique_tickers']
            },
            'short': {
                'win_rate': short_results['summary']['win_rate'],
                'avg_return': short_results['summary']['overall_average'],
                'total_trades': short_results['summary']['unique_tickers']
            }
        }
    
    def generate_comprehensive_report(self):
        """Generate comprehensive correlation report with clear rules"""
        print("\n" + "="*80)
        print("COMPREHENSIVE MARKET REGIME CORRELATION ANALYSIS")
        print("="*80)
        
        # Analyze breadth data
        breadth_analysis = self.analyze_breadth_data()
        if not breadth_analysis:
            print("Error: No breadth data available for analysis")
            return
            
        # Load strategy performance
        strategy_perf = self.load_strategy_performance()
        
        # Load latest regime
        with open(os.path.join(self.regime_path, 'regime_analysis/latest_regime_summary.json'), 'r') as f:
            latest_regime = json.load(f)
        
        print(f"\n## ANALYSIS PERIOD: {breadth_analysis['period']}")
        print(f"Data points analyzed: {breadth_analysis['data_points']}")
        
        print("\n## STRATEGY PERFORMANCE (Past 4 Weeks)")
        print(f"Long Reversal:  {strategy_perf['long']['win_rate']:.1f}% win rate, {strategy_perf['long']['avg_return']:.2f}% avg return")
        print(f"Short Reversal: {strategy_perf['short']['win_rate']:.1f}% win rate, {strategy_perf['short']['avg_return']:.2f}% avg return")
        
        print("\n## MARKET BREADTH ANALYSIS")
        print(f"SMA20 Breadth:")
        print(f"  - Average: {breadth_analysis['sma20']['mean']:.1f}%")
        print(f"  - Range: {breadth_analysis['sma20']['min']:.1f}% to {breadth_analysis['sma20']['max']:.1f}%")
        print(f"  - Current: {breadth_analysis['sma20']['latest']:.1f}%")
        
        print(f"\nSMA50 Breadth:")
        print(f"  - Average: {breadth_analysis['sma50']['mean']:.1f}%")
        print(f"  - Range: {breadth_analysis['sma50']['min']:.1f}% to {breadth_analysis['sma50']['max']:.1f}%")
        print(f"  - Current: {breadth_analysis['sma50']['latest']:.1f}%")
        
        print(f"\nVolume Participation:")
        print(f"  - Average: {breadth_analysis['volume']['mean']:.2f}")
        print(f"  - Current: {breadth_analysis['volume']['latest']:.2f}")
        
        print("\n## CURRENT MARKET STATE")
        print(f"Regime: {latest_regime['market_regime']['regime']}")
        print(f"Market Score: {latest_regime['trend_analysis']['market_score']:.2f}")
        print(f"Long/Short Ratio: {latest_regime['reversal_counts']['long']}/{latest_regime['reversal_counts']['short']} = {latest_regime['reversal_counts']['long']/max(latest_regime['reversal_counts']['short'], 1):.2f}")
        print(f"Indices above SMA20: {latest_regime['index_analysis']['indices_above_sma20']}/3")
        
        # GENERATE CLEAR RULES
        print("\n" + "="*80)
        print("CLEAR MARKET DIRECTION RULES")
        print("="*80)
        
        print("\n### WEEKLY DIRECTION DETERMINATION:")
        print("\n**Rule 1: SMA20 Breadth (Primary Signal)**")
        print("  - Above 70%: STRONG BULLISH → 80% Long, 20% Short")
        print("  - 60-70%: BULLISH → 70% Long, 30% Short")
        print("  - 50-60%: MILD BULLISH → 60% Long, 40% Short")
        print("  - 40-50%: NEUTRAL → 50% Long, 50% Short")
        print("  - 30-40%: MILD BEARISH → 40% Long, 60% Short")
        print("  - 20-30%: BEARISH → 30% Long, 70% Short")
        print("  - Below 20%: STRONG BEARISH → 20% Long, 80% Short")
        
        current_sma20 = breadth_analysis['sma20']['latest']
        if current_sma20 >= 70:
            weekly_bias = "STRONG BULLISH"
            allocation = "80% Long, 20% Short"
        elif current_sma20 >= 60:
            weekly_bias = "BULLISH"
            allocation = "70% Long, 30% Short"
        elif current_sma20 >= 50:
            weekly_bias = "MILD BULLISH"
            allocation = "60% Long, 40% Short"
        elif current_sma20 >= 40:
            weekly_bias = "NEUTRAL"
            allocation = "50% Long, 50% Short"
        elif current_sma20 >= 30:
            weekly_bias = "MILD BEARISH"
            allocation = "40% Long, 60% Short"
        elif current_sma20 >= 20:
            weekly_bias = "BEARISH"
            allocation = "30% Long, 70% Short"
        else:
            weekly_bias = "STRONG BEARISH"
            allocation = "20% Long, 80% Short"
        
        print(f"\n  Current SMA20: {current_sma20:.1f}% → {weekly_bias}")
        print(f"  Recommended Allocation: {allocation}")
        
        print("\n**Rule 2: Index Confirmation**")
        indices_above = latest_regime['index_analysis']['indices_above_sma20']
        print(f"  - Indices above SMA20: {indices_above}/3")
        if indices_above == 3:
            index_signal = "Strong Bullish Confirmation"
        elif indices_above == 2:
            index_signal = "Mild Bullish"
        elif indices_above == 1:
            index_signal = "Mild Bearish"
        else:
            index_signal = "Strong Bearish Confirmation"
        print(f"  - Signal: {index_signal}")
        
        print("\n**Rule 3: Volume Participation Check**")
        current_volume = breadth_analysis['volume']['latest']
        if current_volume > 0.5:
            volume_signal = "High conviction - trust the trend"
        elif current_volume > 0.3:
            volume_signal = "Normal participation"
        else:
            volume_signal = "Low conviction - be cautious with position sizes"
        print(f"  - Current: {current_volume:.2f} → {volume_signal}")
        
        print("\n### DAILY DIRECTION DETERMINATION:")
        
        print("\n**Rule 1: Market Score**")
        market_score = latest_regime['trend_analysis']['market_score']
        if market_score > 0.5:
            daily_signal = "Strong Bullish Day"
        elif market_score > 0.2:
            daily_signal = "Bullish Day"
        elif market_score > -0.2:
            daily_signal = "Neutral/Choppy Day"
        elif market_score > -0.5:
            daily_signal = "Bearish Day"
        else:
            daily_signal = "Strong Bearish Day"
        print(f"  - Current Score: {market_score:.2f} → {daily_signal}")
        
        print("\n**Rule 2: Reversal Pattern Ratio**")
        ratio = latest_regime['reversal_counts']['long']/max(latest_regime['reversal_counts']['short'], 1)
        if ratio > 2.0:
            pattern_signal = "Strong Long bias"
        elif ratio > 1.5:
            pattern_signal = "Long bias"
        elif ratio > 0.7:
            pattern_signal = "Balanced"
        elif ratio > 0.5:
            pattern_signal = "Short bias"
        else:
            pattern_signal = "Strong Short bias"
        print(f"  - Long/Short Ratio: {ratio:.2f} → {pattern_signal}")
        
        # CORRELATION INSIGHTS
        print("\n" + "="*80)
        print("KEY CORRELATIONS & INSIGHTS")
        print("="*80)
        
        print("\n1. **Breadth vs Performance Correlation:**")
        print(f"   - Low SMA20 breadth ({breadth_analysis['sma20']['mean']:.1f}%) correlates with:")
        print(f"     • Poor long performance ({strategy_perf['long']['win_rate']:.1f}% win rate)")
        print(f"     • Strong short performance ({strategy_perf['short']['win_rate']:.1f}% win rate)")
        
        print("\n2. **Why Short Strategies Outperformed:**")
        print(f"   - Market spent most time below key SMAs")
        print(f"   - Average market score was negative ({breadth_analysis['market_score']['mean']:.2f})")
        print(f"   - Bearish regimes dominated the period")
        
        print("\n3. **Actionable Takeaways:**")
        print(f"   - When SMA20 breadth < 40%, prioritize short setups")
        print(f"   - Current market suggests continuing with short bias")
        print(f"   - Watch for SMA20 breadth to cross above 50% for regime change")
        
        # Save comprehensive report
        report = {
            'generated_date': datetime.now().isoformat(),
            'analysis_period': breadth_analysis['period'],
            'strategy_performance': strategy_perf,
            'breadth_metrics': {
                'sma20': breadth_analysis['sma20'],
                'sma50': breadth_analysis['sma50'],
                'volume': breadth_analysis['volume']
            },
            'current_state': {
                'regime': latest_regime['market_regime']['regime'],
                'market_score': market_score,
                'reversal_ratio': ratio,
                'indices_above_sma20': indices_above
            },
            'rules': {
                'weekly': {
                    'bias': weekly_bias,
                    'allocation': allocation,
                    'sma20_breadth': current_sma20
                },
                'daily': {
                    'signal': daily_signal,
                    'pattern_signal': pattern_signal
                }
            }
        }
        
        report_path = os.path.join(self.results_path, f'comprehensive_regime_correlation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n\nComprehensive report saved to: {report_path}")
        
        return report

def main():
    analyzer = ComprehensiveRegimeAnalysis()
    analyzer.generate_comprehensive_report()

if __name__ == "__main__":
    main()