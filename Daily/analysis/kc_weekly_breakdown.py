#!/usr/bin/env python3
"""
KC Limit Weekly Breakdown Analysis
Analyzes KC Upper and Lower Limit patterns week by week without price data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import glob
import json
from collections import defaultdict

class KCWeeklyBreakdown:
    def __init__(self):
        """Initialize the analyzer"""
        self.results_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/results'
        self.results_s_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/results-s'
        
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
        
        # Known performance from reversal analysis
        self.reversal_performance = {
            'Week 1': {'long_win': 31.9, 'short_win': 58.5},
            'Week 2': {'long_win': 41.4, 'short_win': 66.9},
            'Week 3': {'long_win': 36.8, 'short_win': 67.8},
            'Week 4': {'long_win': 17.6, 'short_win': 77.4}
        }
        
    def analyze_kc_patterns(self, direction='long'):
        """Analyze KC patterns for given direction"""
        if direction == 'long':
            pattern = os.path.join(self.results_dir, 'KC_Upper_Limit_Trending_*.xlsx')
            strategy = 'KC Upper Limit'
        else:
            pattern = os.path.join(self.results_s_dir, 'KC_Lower_Limit_Trending_*.xlsx')
            strategy = 'KC Lower Limit'
        
        all_files = glob.glob(pattern)
        
        weekly_data = defaultdict(lambda: {
            'unique_tickers': set(),
            'daily_counts': defaultdict(int),
            'high_score_tickers': set(),
            'pattern_strength': [],
            'file_count': 0
        })
        
        for file_path in all_files:
            try:
                # Extract date from filename
                filename = os.path.basename(file_path)
                date_str = filename.split('_')[-2]
                file_date = datetime.strptime(date_str, '%Y%m%d')
                
                # Find which week this belongs to
                week_label = None
                for week in self.weeks:
                    if week['start'].date() <= file_date.date() <= week['end'].date():
                        week_label = f"Week {week['week_num']}"
                        break
                
                if not week_label:
                    continue
                
                # Read file
                df = pd.read_excel(file_path)
                
                if df.empty:
                    continue
                
                weekly_data[week_label]['file_count'] += 1
                
                # Process each ticker
                for _, row in df.iterrows():
                    ticker = row['Ticker']
                    weekly_data[week_label]['unique_tickers'].add(ticker)
                    weekly_data[week_label]['daily_counts'][file_date.date()] += 1
                    
                    # Check scores
                    advanced_score = pd.to_numeric(row.get('Advanced_Score', 0), errors='coerce')
                    if pd.notna(advanced_score) and advanced_score >= 70:
                        weekly_data[week_label]['high_score_tickers'].add(ticker)
                    
                    pattern_strength = pd.to_numeric(row.get('Pattern_Strength', 0), errors='coerce')
                    if pd.notna(pattern_strength):
                        weekly_data[week_label]['pattern_strength'].append(pattern_strength)
                        
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue
        
        return dict(weekly_data), strategy
    
    def print_comparison(self):
        """Print comparison between KC and Reversal strategies"""
        print("\n" + "="*80)
        print("KC LIMIT vs REVERSAL STRATEGY COMPARISON")
        print("="*80)
        
        # Analyze KC Upper (Long)
        kc_long_data, _ = self.analyze_kc_patterns('long')
        
        # Analyze KC Lower (Short)
        kc_short_data, _ = self.analyze_kc_patterns('short')
        
        # Print week by week comparison
        for week_num in range(1, 5):
            week_key = f"Week {week_num}"
            week_info = self.weeks[week_num - 1]
            
            print(f"\n{week_info['label']}")
            print("-" * 60)
            
            # Reversal performance
            rev_perf = self.reversal_performance.get(week_key, {})
            print(f"Reversal Strategy Performance:")
            print(f"  Long Win Rate: {rev_perf.get('long_win', 'N/A')}%")
            print(f"  Short Win Rate: {rev_perf.get('short_win', 'N/A')}%")
            print(f"  Better Direction: {'SHORT' if rev_perf.get('short_win', 0) > rev_perf.get('long_win', 0) else 'LONG'}")
            
            # KC Upper Limit
            kc_long = kc_long_data.get(week_key, {})
            if kc_long:
                print(f"\nKC Upper Limit (Long):")
                print(f"  Unique Tickers: {len(kc_long['unique_tickers'])}")
                print(f"  High Score Tickers (>70): {len(kc_long['high_score_tickers'])}")
                print(f"  Scan Files: {kc_long['file_count']}")
                if kc_long['pattern_strength']:
                    avg_strength = np.mean(kc_long['pattern_strength'])
                    print(f"  Avg Pattern Strength: {avg_strength:.1f}")
            
            # KC Lower Limit
            kc_short = kc_short_data.get(week_key, {})
            if kc_short:
                print(f"\nKC Lower Limit (Short):")
                print(f"  Unique Tickers: {len(kc_short['unique_tickers'])}")
                print(f"  High Score Tickers (>70): {len(kc_short['high_score_tickers'])}")
                print(f"  Scan Files: {kc_short['file_count']}")
                if kc_short['pattern_strength']:
                    avg_strength = np.mean(kc_short['pattern_strength'])
                    print(f"  Avg Pattern Strength: {avg_strength:.1f}")
            
            # Signal comparison
            print(f"\nSignal Volume Comparison:")
            long_signals = len(kc_long.get('unique_tickers', set()))
            short_signals = len(kc_short.get('unique_tickers', set()))
            
            if long_signals > 0 or short_signals > 0:
                print(f"  KC Long Signals: {long_signals}")
                print(f"  KC Short Signals: {short_signals}")
                print(f"  KC Signal Bias: {'LONG' if long_signals > short_signals else 'SHORT'}")
                
                # Does KC bias match reversal performance?
                kc_bias = 'LONG' if long_signals > short_signals else 'SHORT'
                rev_winner = 'SHORT' if rev_perf.get('short_win', 0) > rev_perf.get('long_win', 0) else 'LONG'
                match = '✓' if kc_bias == rev_winner else '✗'
                print(f"  KC Bias Matches Reversal Winner: {match}")
        
        # Overall summary
        print("\n" + "="*80)
        print("OVERALL SUMMARY")
        print("="*80)
        
        total_kc_long = sum(len(v.get('unique_tickers', set())) for v in kc_long_data.values())
        total_kc_short = sum(len(v.get('unique_tickers', set())) for v in kc_short_data.values())
        
        print(f"\nTotal KC Signals (4 weeks):")
        print(f"  KC Upper Limit (Long): {total_kc_long} unique tickers")
        print(f"  KC Lower Limit (Short): {total_kc_short} unique tickers")
        print(f"  Overall KC Bias: {'LONG' if total_kc_long > total_kc_short else 'SHORT'}")
        
        print(f"\nReversal Strategy Performance (4 weeks):")
        print(f"  Long strategies averaged: {np.mean([v['long_win'] for v in self.reversal_performance.values()]):.1f}% win rate")
        print(f"  Short strategies averaged: {np.mean([v['short_win'] for v in self.reversal_performance.values()]):.1f}% win rate")
        print(f"  Consistent winner: SHORT strategies")
        
        # Save detailed results
        self.save_results(kc_long_data, kc_short_data)
    
    def save_results(self, kc_long_data, kc_short_data):
        """Save analysis results"""
        output_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports'
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create summary data
        summary = {
            'analysis_date': timestamp,
            'weeks_analyzed': 4,
            'kc_upper_limit': {},
            'kc_lower_limit': {},
            'reversal_comparison': self.reversal_performance
        }
        
        # Process KC data
        for week_key, data in kc_long_data.items():
            summary['kc_upper_limit'][week_key] = {
                'unique_tickers': len(data['unique_tickers']),
                'high_score_count': len(data['high_score_tickers']),
                'file_count': data['file_count'],
                'avg_pattern_strength': np.mean(data['pattern_strength']) if data['pattern_strength'] else 0,
                'tickers': list(data['unique_tickers'])
            }
        
        for week_key, data in kc_short_data.items():
            summary['kc_lower_limit'][week_key] = {
                'unique_tickers': len(data['unique_tickers']),
                'high_score_count': len(data['high_score_tickers']),
                'file_count': data['file_count'],
                'avg_pattern_strength': np.mean(data['pattern_strength']) if data['pattern_strength'] else 0,
                'tickers': list(data['unique_tickers'])
            }
        
        # Save JSON
        json_file = os.path.join(output_dir, f'kc_vs_reversal_comparison_{timestamp}.json')
        with open(json_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Save Excel
        excel_file = os.path.join(output_dir, f'kc_vs_reversal_comparison_{timestamp}.xlsx')
        
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = []
            for week_num in range(1, 5):
                week_key = f"Week {week_num}"
                kc_long = summary['kc_upper_limit'].get(week_key, {})
                kc_short = summary['kc_lower_limit'].get(week_key, {})
                rev_perf = self.reversal_performance.get(week_key, {})
                
                summary_data.append({
                    'Week': week_key,
                    'KC_Long_Signals': kc_long.get('unique_tickers', 0),
                    'KC_Short_Signals': kc_short.get('unique_tickers', 0),
                    'KC_Bias': 'LONG' if kc_long.get('unique_tickers', 0) > kc_short.get('unique_tickers', 0) else 'SHORT',
                    'Reversal_Long_Win%': rev_perf.get('long_win', 0),
                    'Reversal_Short_Win%': rev_perf.get('short_win', 0),
                    'Reversal_Winner': 'SHORT' if rev_perf.get('short_win', 0) > rev_perf.get('long_win', 0) else 'LONG',
                    'KC_Matches_Winner': 'Yes' if (
                        ('LONG' if kc_long.get('unique_tickers', 0) > kc_short.get('unique_tickers', 0) else 'SHORT') ==
                        ('SHORT' if rev_perf.get('short_win', 0) > rev_perf.get('long_win', 0) else 'LONG')
                    ) else 'No'
                })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Weekly_Summary', index=False)
            
            # KC Upper details
            kc_upper_details = []
            for week_key, data in summary['kc_upper_limit'].items():
                for ticker in data['tickers']:
                    kc_upper_details.append({
                        'Week': week_key,
                        'Ticker': ticker,
                        'High_Score': ticker in kc_long_data[week_key]['high_score_tickers']
                    })
            
            if kc_upper_details:
                pd.DataFrame(kc_upper_details).to_excel(writer, sheet_name='KC_Upper_Details', index=False)
            
            # KC Lower details
            kc_lower_details = []
            for week_key, data in summary['kc_lower_limit'].items():
                for ticker in data['tickers']:
                    kc_lower_details.append({
                        'Week': week_key,
                        'Ticker': ticker,
                        'High_Score': ticker in kc_short_data[week_key]['high_score_tickers']
                    })
            
            if kc_lower_details:
                pd.DataFrame(kc_lower_details).to_excel(writer, sheet_name='KC_Lower_Details', index=False)
        
        print(f"\nResults saved to:")
        print(f"  - {json_file}")
        print(f"  - {excel_file}")


def main():
    """Main function"""
    analyzer = KCWeeklyBreakdown()
    analyzer.print_comparison()


if __name__ == "__main__":
    main()