#!/usr/bin/env python3
"""
Optimal Lookback Period Analysis
=================================
Determines the best number of days to use for frequency-based trading decisions
by testing different lookback periods and their performance.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Frequent_ticker_performance import FrequentTickerPerformanceAnalyzer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OptimalLookbackAnalyzer:
    """Analyze optimal lookback period for frequency analysis"""
    
    def __init__(self, user_name="Sai"):
        self.user_name = user_name
        self.lookback_periods = [3, 5, 7, 10, 14, 20, 30]  # Different lookback periods to test
        self.results = {}
        
    def analyze_lookback_period(self, days_back):
        """Analyze performance for a specific lookback period"""
        try:
            analyzer = FrequentTickerPerformanceAnalyzer(user_name=self.user_name, days_back=days_back)
            returns_data = analyzer.analyze_reports()
            
            if not returns_data:
                return None
            
            # Calculate key metrics
            high_freq_tickers = [data for data in returns_data.values() if data['appearances'] >= 10]
            very_high_freq_tickers = [data for data in returns_data.values() if data['appearances'] >= 15]
            
            metrics = {
                'days_back': days_back,
                'total_tickers': len(returns_data),
                'high_freq_count': len(high_freq_tickers),
                'very_high_freq_count': len(very_high_freq_tickers),
                'overall_win_rate': len([d for d in returns_data.values() if d['return_pct'] > 0]) / len(returns_data) * 100,
                'high_freq_win_rate': len([d for d in high_freq_tickers if d['return_pct'] > 0]) / len(high_freq_tickers) * 100 if high_freq_tickers else 0,
                'very_high_freq_win_rate': len([d for d in very_high_freq_tickers if d['return_pct'] > 0]) / len(very_high_freq_tickers) * 100 if very_high_freq_tickers else 0,
                'overall_avg_return': np.mean([d['return_pct'] for d in returns_data.values()]),
                'high_freq_avg_return': np.mean([d['return_pct'] for d in high_freq_tickers]) if high_freq_tickers else 0,
                'very_high_freq_avg_return': np.mean([d['return_pct'] for d in very_high_freq_tickers]) if very_high_freq_tickers else 0,
            }
            
            # Calculate frequency groups performance
            freq_groups = defaultdict(list)
            for data in returns_data.values():
                if data['appearances'] == 1:
                    freq_groups['single'].append(data['return_pct'])
                elif 2 <= data['appearances'] <= 5:
                    freq_groups['low'].append(data['return_pct'])
                elif 6 <= data['appearances'] <= 10:
                    freq_groups['medium'].append(data['return_pct'])
                elif 11 <= data['appearances'] <= 15:
                    freq_groups['high'].append(data['return_pct'])
                else:
                    freq_groups['very_high'].append(data['return_pct'])
            
            # Calculate correlation
            frequencies = [d['appearances'] for d in returns_data.values()]
            returns = [d['return_pct'] for d in returns_data.values()]
            
            if len(frequencies) > 1:
                from scipy import stats
                correlation = stats.pearsonr(frequencies, returns)[0]
                metrics['frequency_return_correlation'] = correlation
            else:
                metrics['frequency_return_correlation'] = 0
            
            metrics['freq_groups'] = {k: {'count': len(v), 'avg_return': np.mean(v) if v else 0} 
                                    for k, v in freq_groups.items()}
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error analyzing {days_back} days: {e}")
            return None
    
    def analyze_all_periods(self):
        """Analyze all lookback periods"""
        logger.info("Starting optimal lookback period analysis...")
        
        for days in self.lookback_periods:
            logger.info(f"Analyzing {days}-day lookback period...")
            metrics = self.analyze_lookback_period(days)
            if metrics:
                self.results[days] = metrics
        
        return self.results
    
    def generate_report(self):
        """Generate comprehensive report on optimal lookback period"""
        if not self.results:
            logger.error("No results to report")
            return
        
        output_lines = []
        output_lines.append("=" * 80)
        output_lines.append("OPTIMAL LOOKBACK PERIOD ANALYSIS")
        output_lines.append("Brooks Higher Probability LONG Reversal Strategy")
        output_lines.append("=" * 80)
        output_lines.append(f"\nAnalysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output_lines.append(f"Lookback periods tested: {', '.join(map(str, sorted(self.results.keys())))} days")
        
        # Summary table
        output_lines.append("\n" + "-" * 80)
        output_lines.append("PERFORMANCE SUMMARY BY LOOKBACK PERIOD")
        output_lines.append("-" * 80)
        output_lines.append(f"\n{'Days':<6} {'Tickers':<10} {'High Freq':<12} {'Correlation':<12} {'Win Rate':<10} {'Avg Return':<12}")
        output_lines.append("-" * 80)
        
        for days in sorted(self.results.keys()):
            m = self.results[days]
            output_lines.append(
                f"{days:<6} {m['total_tickers']:<10} {m['high_freq_count']:<12} "
                f"{m['frequency_return_correlation']:<12.4f} {m['overall_win_rate']:<10.1f} "
                f"{m['overall_avg_return']:<12.2f}"
            )
        
        # High frequency performance
        output_lines.append("\n" + "-" * 80)
        output_lines.append("HIGH FREQUENCY (10+) TICKER PERFORMANCE")
        output_lines.append("-" * 80)
        output_lines.append(f"\n{'Days':<6} {'Count':<8} {'Win Rate':<10} {'Avg Return':<12}")
        output_lines.append("-" * 60)
        
        for days in sorted(self.results.keys()):
            m = self.results[days]
            if m['high_freq_count'] > 0:
                output_lines.append(
                    f"{days:<6} {m['high_freq_count']:<8} "
                    f"{m['high_freq_win_rate']:<10.1f} {m['high_freq_avg_return']:<12.2f}"
                )
        
        # Determine optimal period
        output_lines.append("\n" + "-" * 80)
        output_lines.append("OPTIMAL LOOKBACK PERIOD DETERMINATION")
        output_lines.append("-" * 80)
        
        # Score each period
        scores = {}
        for days, m in self.results.items():
            score = 0
            
            # Factor 1: Correlation strength (weight: 30%)
            score += abs(m['frequency_return_correlation']) * 30
            
            # Factor 2: High frequency win rate (weight: 40%)
            if m['high_freq_count'] > 0:
                score += (m['high_freq_win_rate'] / 100) * 40
            
            # Factor 3: Sample size adequacy (weight: 20%)
            sample_score = min(m['high_freq_count'] / 20, 1) * 20
            score += sample_score
            
            # Factor 4: Average return of high freq (weight: 10%)
            if m['high_freq_avg_return'] > 0:
                score += min(m['high_freq_avg_return'] / 10, 1) * 10
            
            scores[days] = score
        
        # Rank periods
        ranked_periods = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        output_lines.append("\nRanking by composite score:")
        for rank, (days, score) in enumerate(ranked_periods, 1):
            m = self.results[days]
            output_lines.append(
                f"{rank}. {days} days (Score: {score:.1f}) - "
                f"Correlation: {m['frequency_return_correlation']:.3f}, "
                f"High Freq Win Rate: {m['high_freq_win_rate']:.1f}%"
            )
        
        # Recommendations
        output_lines.append("\n" + "-" * 80)
        output_lines.append("RECOMMENDATIONS")
        output_lines.append("-" * 80)
        
        optimal_period = ranked_periods[0][0]
        output_lines.append(f"\nOPTIMAL LOOKBACK PERIOD: {optimal_period} days")
        
        output_lines.append("\nReasoning:")
        if optimal_period <= 7:
            output_lines.append("- Shorter period provides more responsive signals")
            output_lines.append("- Good for catching momentum early")
            output_lines.append("- May have more false signals")
        elif optimal_period <= 14:
            output_lines.append("- Balanced period between responsiveness and reliability")
            output_lines.append("- Good sample size for frequency analysis")
            output_lines.append("- Optimal for most market conditions")
        else:
            output_lines.append("- Longer period provides more stable signals")
            output_lines.append("- Better for filtering out noise")
            output_lines.append("- May miss some short-term opportunities")
        
        # Save report
        output_dir = "/Users/maverick/PycharmProjects/India-TS/ML/results"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"optimal_lookback_analysis_{timestamp}.txt")
        
        with open(report_path, 'w') as f:
            f.write('\n'.join(output_lines))
        
        logger.info(f"Report saved to: {report_path}")
        
        # Print summary
        print("\n".join(output_lines[:60]))
        if len(output_lines) > 60:
            print(f"\n... (Full report saved to {report_path})")
        
        return optimal_period, scores

def main():
    """Main function"""
    analyzer = OptimalLookbackAnalyzer()
    
    # Analyze all periods
    results = analyzer.analyze_all_periods()
    
    if results:
        # Generate report
        optimal_period, scores = analyzer.generate_report()
        print(f"\n\nRECOMMENDED LOOKBACK PERIOD: {optimal_period} days")

if __name__ == "__main__":
    main()