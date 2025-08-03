#!/usr/bin/env python3
"""
Frequency-Profit Correlation Analysis
=====================================
Analyzes the correlation between how frequently a ticker appears in Brooks Higher
Probability LONG Reversal reports and its profit success rate.

Features:
- Analyzes past 10 days of reports
- Calculates correlation metrics
- Groups tickers by frequency ranges
- Generates visualization charts
- Provides statistical insights

Author: Claude Code Assistant
Created: 2025-06-06
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import argparse
import time
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from the ticker performance analyzer
from Frequent_ticker_performance import FrequentTickerPerformanceAnalyzer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FrequencyProfitCorrelationAnalyzer(FrequentTickerPerformanceAnalyzer):
    """Analyze correlation between ticker frequency and profit success"""
    
    def __init__(self, user_name="Sai", days_back=10):
        """Initialize the analyzer for correlation analysis"""
        super().__init__(user_name=user_name, days_back=days_back)
        self.frequency_groups = {}
        self.correlation_data = []
        
    def group_tickers_by_frequency(self, returns_data):
        """Group tickers by their appearance frequency"""
        frequency_groups = {
            '1 appearance': [],
            '2-5 appearances': [],
            '6-10 appearances': [],
            '11-15 appearances': [],
            '16+ appearances': []
        }
        
        for ticker, data in returns_data.items():
            appearances = data['appearances']
            return_pct = data['return_pct']
            
            if appearances == 1:
                frequency_groups['1 appearance'].append((ticker, return_pct))
            elif 2 <= appearances <= 5:
                frequency_groups['2-5 appearances'].append((ticker, return_pct))
            elif 6 <= appearances <= 10:
                frequency_groups['6-10 appearances'].append((ticker, return_pct))
            elif 11 <= appearances <= 15:
                frequency_groups['11-15 appearances'].append((ticker, return_pct))
            else:
                frequency_groups['16+ appearances'].append((ticker, return_pct))
        
        return frequency_groups
    
    def calculate_group_statistics(self, frequency_groups):
        """Calculate statistics for each frequency group"""
        group_stats = {}
        
        for group_name, tickers in frequency_groups.items():
            if not tickers:
                continue
                
            returns = [r[1] for r in tickers]
            winners = [r for r in returns if r > 0]
            
            group_stats[group_name] = {
                'count': len(tickers),
                'avg_return': np.mean(returns),
                'median_return': np.median(returns),
                'std_return': np.std(returns),
                'min_return': np.min(returns),
                'max_return': np.max(returns),
                'win_rate': len(winners) / len(returns) * 100,
                'total_winners': len(winners),
                'total_losers': len(returns) - len(winners)
            }
        
        return group_stats
    
    def calculate_correlation_metrics(self, returns_data):
        """Calculate correlation between frequency and returns"""
        frequencies = []
        returns = []
        win_rates = []
        
        # Aggregate data by frequency
        frequency_returns = defaultdict(list)
        for ticker, data in returns_data.items():
            frequency_returns[data['appearances']].append(data['return_pct'])
        
        # Calculate metrics for each frequency
        for freq, ret_list in frequency_returns.items():
            frequencies.append(freq)
            returns.append(np.mean(ret_list))
            win_rates.append(len([r for r in ret_list if r > 0]) / len(ret_list) * 100)
        
        # Calculate correlations
        freq_return_corr = stats.pearsonr(frequencies, returns)[0] if len(frequencies) > 1 else 0
        freq_winrate_corr = stats.pearsonr(frequencies, win_rates)[0] if len(frequencies) > 1 else 0
        
        # Prepare data for detailed analysis
        self.correlation_data = []
        for ticker, data in returns_data.items():
            self.correlation_data.append({
                'ticker': ticker,
                'frequency': data['appearances'],
                'return': data['return_pct'],
                'is_winner': data['return_pct'] > 0
            })
        
        return {
            'frequency_return_correlation': freq_return_corr,
            'frequency_winrate_correlation': freq_winrate_corr,
            'frequency_returns': dict(frequency_returns)
        }
    
    def create_visualization_charts(self, returns_data, group_stats, correlation_metrics, output_dir):
        """Create visualization charts for the analysis"""
        # Set style
        plt.style.use('seaborn-v0_8-darkgrid')
        
        # Create figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Frequency-Profit Correlation Analysis\nBrooks Higher Probability LONG Reversal Strategy', 
                     fontsize=16, fontweight='bold')
        
        # 1. Scatter plot: Frequency vs Return
        ax1 = axes[0, 0]
        df = pd.DataFrame(self.correlation_data)
        
        # Color points by winner/loser status
        winners = df[df['is_winner']]
        losers = df[~df['is_winner']]
        
        ax1.scatter(winners['frequency'], winners['return'], alpha=0.6, color='green', label='Winners', s=50)
        ax1.scatter(losers['frequency'], losers['return'], alpha=0.6, color='red', label='Losers', s=50)
        
        # Add trend line
        z = np.polyfit(df['frequency'], df['return'], 1)
        p = np.poly1d(z)
        ax1.plot(df['frequency'].sort_values(), p(df['frequency'].sort_values()), 
                "k--", alpha=0.8, label=f'Trend (r={correlation_metrics["frequency_return_correlation"]:.3f})')
        
        ax1.set_xlabel('Appearance Frequency')
        ax1.set_ylabel('Return %')
        ax1.set_title('Ticker Frequency vs Return Performance')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. Box plot: Returns by frequency group
        ax2 = axes[0, 1]
        box_data = []
        box_labels = []
        
        for group in ['1 appearance', '2-5 appearances', '6-10 appearances', '11-15 appearances', '16+ appearances']:
            if group in group_stats:
                group_returns = [r[1] for r in self.frequency_groups[group]]
                if group_returns:
                    box_data.append(group_returns)
                    box_labels.append(f"{group}\n(n={len(group_returns)})")
        
        bp = ax2.boxplot(box_data, labels=box_labels, patch_artist=True)
        for patch in bp['boxes']:
            patch.set_facecolor('lightblue')
        
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax2.set_ylabel('Return %')
        ax2.set_title('Return Distribution by Frequency Group')
        ax2.grid(True, alpha=0.3)
        
        # 3. Bar chart: Win rate by frequency group
        ax3 = axes[1, 0]
        groups = []
        win_rates = []
        colors = []
        
        for group in ['1 appearance', '2-5 appearances', '6-10 appearances', '11-15 appearances', '16+ appearances']:
            if group in group_stats:
                groups.append(f"{group}\n(n={group_stats[group]['count']})")
                win_rates.append(group_stats[group]['win_rate'])
                colors.append('green' if group_stats[group]['win_rate'] > 50 else 'red')
        
        bars = ax3.bar(groups, win_rates, color=colors, alpha=0.7)
        ax3.axhline(y=50, color='black', linestyle='--', alpha=0.5, label='50% threshold')
        ax3.set_ylabel('Win Rate %')
        ax3.set_title('Success Rate by Frequency Group')
        ax3.legend()
        
        # Add value labels on bars
        for bar, rate in zip(bars, win_rates):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{rate:.1f}%', ha='center', va='bottom')
        
        # 4. Heatmap: Frequency vs Return Range
        ax4 = axes[1, 1]
        
        # Create frequency-return matrix
        freq_bins = [1, 2, 5, 10, 15, 20, 30]
        return_bins = [-10, -5, -2, 0, 2, 5, 10, 15]
        
        matrix = np.zeros((len(return_bins)-1, len(freq_bins)-1))
        
        for _, row in df.iterrows():
            freq_idx = np.digitize(row['frequency'], freq_bins) - 1
            ret_idx = np.digitize(row['return'], return_bins) - 1
            
            if 0 <= freq_idx < len(freq_bins)-1 and 0 <= ret_idx < len(return_bins)-1:
                matrix[ret_idx, freq_idx] += 1
        
        # Create heatmap
        im = ax4.imshow(matrix, cmap='YlOrRd', aspect='auto', origin='lower')
        
        # Set ticks
        ax4.set_xticks(range(len(freq_bins)-1))
        ax4.set_xticklabels([f'{freq_bins[i]}-{freq_bins[i+1]}' for i in range(len(freq_bins)-1)])
        ax4.set_yticks(range(len(return_bins)-1))
        ax4.set_yticklabels([f'{return_bins[i]}-{return_bins[i+1]}%' for i in range(len(return_bins)-1)])
        
        ax4.set_xlabel('Frequency Range')
        ax4.set_ylabel('Return Range %')
        ax4.set_title('Distribution of Tickers by Frequency and Return')
        
        # Add colorbar
        plt.colorbar(im, ax=ax4, label='Count')
        
        plt.tight_layout()
        
        # Save chart
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chart_path = os.path.join(output_dir, f'frequency_correlation_analysis_{timestamp}.png')
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Visualization chart saved to: {chart_path}")
        return chart_path
    
    def analyze_correlation(self):
        """Main analysis function for correlation study"""
        # Run base analysis
        returns_data = self.analyze_reports()
        
        if not returns_data:
            logger.error("No returns data available for correlation analysis")
            return
        
        # Group tickers by frequency
        self.frequency_groups = self.group_tickers_by_frequency(returns_data)
        
        # Calculate group statistics
        group_stats = self.calculate_group_statistics(self.frequency_groups)
        
        # Calculate correlation metrics
        correlation_metrics = self.calculate_correlation_metrics(returns_data)
        
        # Create visualizations
        chart_path = self.create_visualization_charts(returns_data, group_stats, correlation_metrics, self.output_dir)
        
        # Generate detailed report
        self.generate_correlation_report(returns_data, group_stats, correlation_metrics, chart_path)
        
        return group_stats, correlation_metrics
    
    def generate_correlation_report(self, returns_data, group_stats, correlation_metrics, chart_path):
        """Generate comprehensive correlation analysis report"""
        output_lines = []
        output_lines.append("=" * 100)
        output_lines.append("FREQUENCY-PROFIT CORRELATION ANALYSIS")
        output_lines.append("Brooks Higher Probability LONG Reversal Strategy")
        output_lines.append("=" * 100)
        output_lines.append(f"\nAnalysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output_lines.append(f"Analysis Period: Past {self.days_back} days")
        output_lines.append(f"Total unique tickers analyzed: {len(returns_data)}")
        output_lines.append(f"Total report occurrences: {sum(data['appearances'] for data in returns_data.values())}")
        
        # Correlation Summary
        output_lines.append("\n" + "-" * 100)
        output_lines.append("CORRELATION SUMMARY")
        output_lines.append("-" * 100)
        
        freq_return_corr = correlation_metrics['frequency_return_correlation']
        freq_winrate_corr = correlation_metrics['frequency_winrate_correlation']
        
        output_lines.append(f"\nFrequency vs Average Return Correlation: {freq_return_corr:.4f}")
        output_lines.append(f"Interpretation: {'Positive' if freq_return_corr > 0 else 'Negative'} correlation")
        output_lines.append(f"Strength: {self._interpret_correlation_strength(abs(freq_return_corr))}")
        
        output_lines.append(f"\nFrequency vs Win Rate Correlation: {freq_winrate_corr:.4f}")
        output_lines.append(f"Interpretation: {'Positive' if freq_winrate_corr > 0 else 'Negative'} correlation")
        output_lines.append(f"Strength: {self._interpret_correlation_strength(abs(freq_winrate_corr))}")
        
        # Statistical Significance
        output_lines.append(f"\nStatistical Insight:")
        if abs(freq_return_corr) > 0.3:
            output_lines.append(f"- There is a {self._interpret_correlation_strength(abs(freq_return_corr)).lower()} "
                              f"{'positive' if freq_return_corr > 0 else 'negative'} relationship between "
                              f"frequency and returns")
        else:
            output_lines.append("- There is no significant linear relationship between frequency and returns")
        
        # Group Performance Analysis
        output_lines.append("\n" + "-" * 100)
        output_lines.append("PERFORMANCE BY FREQUENCY GROUP")
        output_lines.append("-" * 100)
        
        output_lines.append(f"\n{'Group':<20} {'Count':<8} {'Avg Return':<12} {'Win Rate':<10} {'Best':<10} {'Worst':<10}")
        output_lines.append("-" * 88)
        
        for group in ['1 appearance', '2-5 appearances', '6-10 appearances', '11-15 appearances', '16+ appearances']:
            if group in group_stats:
                stats = group_stats[group]
                output_lines.append(
                    f"{group:<20} {stats['count']:<8} "
                    f"{stats['avg_return']:<12.2f} {stats['win_rate']:<10.1f} "
                    f"{stats['max_return']:<10.2f} {stats['min_return']:<10.2f}"
                )
        
        # Key Findings
        output_lines.append("\n" + "-" * 100)
        output_lines.append("KEY FINDINGS")
        output_lines.append("-" * 100)
        
        # Find best performing group
        best_group = max(group_stats.items(), key=lambda x: x[1]['avg_return'])
        highest_winrate = max(group_stats.items(), key=lambda x: x[1]['win_rate'])
        
        output_lines.append(f"\n1. Best Average Return: {best_group[0]} with {best_group[1]['avg_return']:.2f}% average return")
        output_lines.append(f"2. Highest Win Rate: {highest_winrate[0]} with {highest_winrate[1]['win_rate']:.1f}% success rate")
        
        # Analyze trend
        if freq_return_corr > 0.2:
            output_lines.append("3. Trend Analysis: More frequent appearances tend to correlate with better performance")
        elif freq_return_corr < -0.2:
            output_lines.append("3. Trend Analysis: More frequent appearances tend to correlate with worse performance")
        else:
            output_lines.append("3. Trend Analysis: No clear trend between frequency and performance")
        
        # Risk analysis
        output_lines.append("\n" + "-" * 100)
        output_lines.append("RISK ANALYSIS BY FREQUENCY")
        output_lines.append("-" * 100)
        
        for group, stats in group_stats.items():
            if stats['count'] > 0:
                risk_reward = abs(stats['max_return']) / abs(stats['min_return']) if stats['min_return'] != 0 else 0
                output_lines.append(f"\n{group}:")
                output_lines.append(f"  - Standard Deviation: {stats['std_return']:.2f}%")
                output_lines.append(f"  - Risk/Reward Ratio: {risk_reward:.2f}")
                output_lines.append(f"  - Consistency: {'High' if stats['std_return'] < 3 else 'Medium' if stats['std_return'] < 5 else 'Low'}")
        
        # Top performers by frequency group
        output_lines.append("\n" + "-" * 100)
        output_lines.append("TOP PERFORMERS BY FREQUENCY GROUP")
        output_lines.append("-" * 100)
        
        for group, tickers in self.frequency_groups.items():
            if tickers:
                sorted_tickers = sorted(tickers, key=lambda x: x[1], reverse=True)[:3]
                output_lines.append(f"\n{group}:")
                for ticker, return_pct in sorted_tickers:
                    output_lines.append(f"  - {ticker}: {return_pct:.2f}%")
        
        # Recommendations
        output_lines.append("\n" + "-" * 100)
        output_lines.append("STRATEGIC RECOMMENDATIONS")
        output_lines.append("-" * 100)
        
        if freq_return_corr > 0.3:
            output_lines.append("\n1. Focus on tickers that appear frequently in the Brooks reversal signals")
            output_lines.append("2. Consider giving more weight to persistent signals")
        elif freq_return_corr < -0.3:
            output_lines.append("\n1. Be cautious with frequently appearing tickers")
            output_lines.append("2. Fresh signals might offer better opportunities")
        else:
            output_lines.append("\n1. Frequency alone is not a strong predictor of success")
            output_lines.append("2. Consider other factors in conjunction with frequency")
        
        if highest_winrate[1]['win_rate'] > 60:
            output_lines.append(f"3. The {highest_winrate[0]} group shows strong consistency - consider this sweet spot")
        
        # Chart reference
        output_lines.append(f"\n\nVisualization chart saved to: {chart_path}")
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"frequency_correlation_report_{timestamp}.txt"
        report_path = os.path.join(self.output_dir, report_filename)
        
        with open(report_path, 'w') as f:
            f.write('\n'.join(output_lines))
        
        logger.info(f"Correlation analysis report saved to: {report_path}")
        
        # Print summary
        print("\n".join(output_lines[:80]))
        if len(output_lines) > 80:
            print(f"\n... (Full report saved to {report_path})")
        
        return report_path
    
    def _interpret_correlation_strength(self, corr_value):
        """Interpret correlation strength"""
        if corr_value < 0.1:
            return "Negligible"
        elif corr_value < 0.3:
            return "Weak"
        elif corr_value < 0.5:
            return "Moderate"
        elif corr_value < 0.7:
            return "Strong"
        else:
            return "Very Strong"

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Analyze correlation between ticker frequency and profit success')
    parser.add_argument('--user', type=str, default='Sai', help='Zerodha user name')
    parser.add_argument('--days', type=int, default=10, help='Number of days to analyze')
    
    args = parser.parse_args()
    
    analyzer = FrequencyProfitCorrelationAnalyzer(user_name=args.user, days_back=args.days)
    analyzer.analyze_correlation()

if __name__ == "__main__":
    main()