#!/usr/bin/env python3
"""
Strategy Performance vs Market Regime Correlation Analysis
Correlates Long/Short reversal strategy performance with market regime indicators
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import glob
from collections import defaultdict
import matplotlib.pyplot as plt
import seaborn as sns

class StrategyRegimeCorrelation:
    def __init__(self, weeks_to_analyze=4):
        self.weeks_to_analyze = weeks_to_analyze
        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(weeks=weeks_to_analyze)
        
        # Paths
        self.regime_path = '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime'
        self.results_path = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports'
        
    def load_strategy_results(self):
        """Load the latest strategy analysis results"""
        # Load long reversal results
        with open(os.path.join(self.results_path, 'latest_simple_analysis.json'), 'r') as f:
            self.long_results = json.load(f)
            
        # Load short reversal results
        with open(os.path.join(self.results_path, 'latest_short_simple_analysis.json'), 'r') as f:
            self.short_results = json.load(f)
    
    def load_regime_data(self):
        """Load market regime data for the analysis period"""
        # Load regime history
        with open(os.path.join(self.regime_path, 'data/regime_history.json'), 'r') as f:
            regime_history = json.load(f)
        
        # Load SMA breadth historical data
        with open(os.path.join(self.regime_path, 'historical_breadth_data/sma_breadth_historical_latest.json'), 'r') as f:
            sma_breadth_data = json.load(f)
        
        # Convert to DataFrame for easier analysis
        self.regime_df = pd.DataFrame(regime_history)
        self.regime_df['timestamp'] = pd.to_datetime(self.regime_df['timestamp'])
        
        self.breadth_df = pd.DataFrame(sma_breadth_data)
        self.breadth_df['date'] = pd.to_datetime(self.breadth_df['date'])
        
        # Filter to analysis period
        self.regime_df = self.regime_df[
            (self.regime_df['timestamp'] >= self.start_date) & 
            (self.regime_df['timestamp'] <= self.end_date)
        ]
        
        self.breadth_df = self.breadth_df[
            (self.breadth_df['date'] >= self.start_date) & 
            (self.breadth_df['date'] <= self.end_date)
        ]
    
    def analyze_regime_distribution(self):
        """Analyze regime distribution during the period"""
        regime_counts = self.regime_df['regime'].value_counts()
        regime_percentages = (regime_counts / len(self.regime_df) * 100).round(2)
        
        return {
            'regime_counts': regime_counts.to_dict(),
            'regime_percentages': regime_percentages.to_dict(),
            'total_observations': len(self.regime_df)
        }
    
    def analyze_breadth_metrics(self):
        """Analyze average breadth metrics during the period"""
        breadth_summary = {
            'sma20_breadth': {
                'mean': self.breadth_df['sma_breadth'].apply(lambda x: x['sma20_percent']).mean(),
                'min': self.breadth_df['sma_breadth'].apply(lambda x: x['sma20_percent']).min(),
                'max': self.breadth_df['sma_breadth'].apply(lambda x: x['sma20_percent']).max(),
                'std': self.breadth_df['sma_breadth'].apply(lambda x: x['sma20_percent']).std()
            },
            'sma50_breadth': {
                'mean': self.breadth_df['sma_breadth'].apply(lambda x: x['sma50_percent']).mean(),
                'min': self.breadth_df['sma_breadth'].apply(lambda x: x['sma50_percent']).min(),
                'max': self.breadth_df['sma_breadth'].apply(lambda x: x['sma50_percent']).max(),
                'std': self.breadth_df['sma_breadth'].apply(lambda x: x['sma50_percent']).std()
            },
            'volume_participation': {
                'mean': self.breadth_df['volume_breadth'].apply(lambda x: x['volume_participation']).mean(),
                'min': self.breadth_df['volume_breadth'].apply(lambda x: x['volume_participation']).min(),
                'max': self.breadth_df['volume_breadth'].apply(lambda x: x['volume_participation']).max(),
                'std': self.breadth_df['volume_breadth'].apply(lambda x: x['volume_participation']).std()
            }
        }
        
        return breadth_summary
    
    def correlate_with_performance(self):
        """Correlate regime indicators with strategy performance"""
        # Extract daily regime data
        daily_regime = self.regime_df.groupby(self.regime_df['timestamp'].dt.date).agg({
            'regime': lambda x: x.value_counts().index[0],  # Most common regime
            'market_score': 'mean',
            'confidence': 'mean'
        })
        
        # Extract daily breadth data  
        daily_breadth = self.breadth_df.set_index('date')
        
        # Create correlation analysis
        correlation_analysis = {
            'strategy_performance': {
                'long_win_rate': self.long_results['summary']['win_rate'],
                'long_avg_return': self.long_results['summary']['overall_average'],
                'short_win_rate': self.short_results['summary']['win_rate'],
                'short_avg_return': self.short_results['summary']['overall_average']
            },
            'regime_correlation': self.analyze_regime_distribution(),
            'breadth_metrics': self.analyze_breadth_metrics(),
            'insights': []
        }
        
        # Generate insights
        avg_sma20 = correlation_analysis['breadth_metrics']['sma20_breadth']['mean']
        avg_sma50 = correlation_analysis['breadth_metrics']['sma50_breadth']['mean']
        
        if avg_sma20 < 40:
            correlation_analysis['insights'].append(
                f"Very weak market breadth (SMA20: {avg_sma20:.1f}%) explains poor long performance"
            )
        elif avg_sma20 < 50:
            correlation_analysis['insights'].append(
                f"Below-average breadth (SMA20: {avg_sma20:.1f}%) favored short strategies"
            )
        
        # Check regime alignment
        bearish_regimes = ['downtrend', 'strong_downtrend', 'choppy_bearish']
        bearish_percentage = sum(
            correlation_analysis['regime_correlation']['regime_percentages'].get(r, 0) 
            for r in bearish_regimes
        )
        
        if bearish_percentage > 60:
            correlation_analysis['insights'].append(
                f"Market in bearish regimes {bearish_percentage:.1f}% of time - aligns with short outperformance"
            )
        
        return correlation_analysis
    
    def generate_report(self):
        """Generate comprehensive correlation report"""
        print("\n" + "="*80)
        print("STRATEGY PERFORMANCE vs MARKET REGIME CORRELATION")
        print("="*80)
        print(f"Analysis Period: {self.start_date.date()} to {self.end_date.date()}")
        
        # Load data
        self.load_strategy_results()
        self.load_regime_data()
        
        # Perform correlation analysis
        correlation = self.correlate_with_performance()
        
        # Print strategy performance
        print("\n## STRATEGY PERFORMANCE")
        print(f"Long Reversal: {correlation['strategy_performance']['long_win_rate']:.1f}% win rate, "
              f"{correlation['strategy_performance']['long_avg_return']:.2f}% avg return")
        print(f"Short Reversal: {correlation['strategy_performance']['short_win_rate']:.1f}% win rate, "
              f"{correlation['strategy_performance']['short_avg_return']:.2f}% avg return")
        
        # Print regime distribution
        print("\n## MARKET REGIME DISTRIBUTION")
        for regime, pct in correlation['regime_correlation']['regime_percentages'].items():
            print(f"{regime}: {pct:.1f}%")
        
        # Print breadth metrics
        print("\n## AVERAGE BREADTH METRICS")
        breadth = correlation['breadth_metrics']
        print(f"SMA20 Breadth: {breadth['sma20_breadth']['mean']:.1f}% "
              f"(range: {breadth['sma20_breadth']['min']:.1f}% - {breadth['sma20_breadth']['max']:.1f}%)")
        print(f"SMA50 Breadth: {breadth['sma50_breadth']['mean']:.1f}% "
              f"(range: {breadth['sma50_breadth']['min']:.1f}% - {breadth['sma50_breadth']['max']:.1f}%)")
        print(f"Volume Participation: {breadth['volume_participation']['mean']:.2f} "
              f"(range: {breadth['volume_participation']['min']:.2f} - {breadth['volume_participation']['max']:.2f})")
        
        # Print insights
        print("\n## KEY INSIGHTS")
        for i, insight in enumerate(correlation['insights'], 1):
            print(f"{i}. {insight}")
        
        # Save detailed report
        report_path = os.path.join(self.results_path, f'regime_correlation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(report_path, 'w') as f:
            json.dump(correlation, f, indent=2, default=str)
        
        print(f"\nDetailed report saved to: {report_path}")
        
        return correlation

def main():
    analyzer = StrategyRegimeCorrelation(weeks_to_analyze=4)
    analyzer.generate_report()

if __name__ == "__main__":
    main()