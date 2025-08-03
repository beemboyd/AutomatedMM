#!/usr/bin/env python3
"""
Analyze correlation between hourly VSR filtered tickers and daily VSR tickers
Identify which hourly tickers made it to daily and had impulse moves
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import glob
import json
import re
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class VSRHourlyDailyAnalyzer:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.hourly_results_dir = os.path.join(self.base_dir, 'Daily', 'results-h')
        self.daily_results_dir = os.path.join(self.base_dir, 'Daily', 'results')
        self.vsr_logs_dir = os.path.join(self.base_dir, 'Daily', 'logs', 'vsr_tracker')
        self.hourly_logs_dir = os.path.join(self.base_dir, 'Daily', 'logs', 'hourly_tracker')
        
    def load_hourly_tickers(self, date_str):
        """Load all hourly VSR tickers for a given date"""
        hourly_tickers = defaultdict(list)
        
        # Pattern for hourly files
        pattern = f"Long_Reversal_Hourly_{date_str}_*.xlsx"
        files = glob.glob(os.path.join(self.hourly_results_dir, pattern))
        
        for file in sorted(files):
            # Extract time from filename
            time_match = re.search(r'(\d{6})\.xlsx$', file)
            if time_match:
                time_str = time_match.group(1)
                hour = int(time_str[:2])
                
                try:
                    df = pd.read_excel(file)
                    if 'Ticker' in df.columns:
                        tickers = df['Ticker'].tolist()
                        hourly_tickers[hour].extend(tickers)
                        print(f"Hour {hour}: Found {len(tickers)} tickers")
                except Exception as e:
                    print(f"Error reading {file}: {e}")
                    
        return hourly_tickers
    
    def load_daily_tickers(self, date_str):
        """Load all daily VSR/Long Reversal tickers for a given date"""
        daily_tickers_by_time = {}
        
        # Pattern for daily files
        pattern = f"Long_Reversal_Daily_{date_str}_*.xlsx"
        files = glob.glob(os.path.join(self.daily_results_dir, pattern))
        
        for file in sorted(files):
            # Extract time from filename
            time_match = re.search(r'(\d{6})\.xlsx$', file)
            if time_match:
                time_str = time_match.group(1)
                
                try:
                    df = pd.read_excel(file)
                    if 'Ticker' in df.columns:
                        tickers = df['Ticker'].tolist()
                        daily_tickers_by_time[time_str] = tickers
                        print(f"Daily scan at {time_str}: Found {len(tickers)} tickers")
                except Exception as e:
                    print(f"Error reading {file}: {e}")
                    
        return daily_tickers_by_time
    
    def parse_vsr_logs(self, date_str):
        """Parse VSR tracker logs to identify impulse moves"""
        log_file = os.path.join(self.vsr_logs_dir, f"vsr_tracker_enhanced_{date_str}.log")
        
        impulse_moves = {}
        ticker_performance = {}
        momentum_threshold = 2.0  # Consider 2%+ momentum as impulse
        
        if os.path.exists(log_file):
            print(f"\nParsing VSR log: {log_file}")
            
            with open(log_file, 'r') as f:
                for line in f:
                    # Parse ticker lines with momentum info
                    if " | Score:" in line and " | Momentum:" in line:
                        # Extract ticker symbol
                        ticker_match = re.search(r'\[Sai\]\s+(\w+)\s+\|', line)
                        if ticker_match:
                            ticker = ticker_match.group(1).strip()
                            
                            # Extract momentum
                            momentum_match = re.search(r'Momentum:\s+([-+]?\d+\.\d+)%', line)
                            if momentum_match:
                                momentum = float(momentum_match.group(1))
                                
                                # Extract other metrics
                                price_match = re.search(r'Price:\s*₹([\d,]+\.?\d*)', line)
                                volume_match = re.search(r'Vol:\s*([\d,]+)', line)
                                score_match = re.search(r'Score:\s*(\d+)', line)
                                
                                if ticker not in ticker_performance or momentum > ticker_performance.get(ticker, {}).get('momentum', -999):
                                    ticker_performance[ticker] = {
                                        'momentum': momentum,
                                        'price': float(price_match.group(1).replace(',', '')) if price_match else 0,
                                        'volume': int(volume_match.group(1).replace(',', '')) if volume_match else 0,
                                        'score': int(score_match.group(1)) if score_match else 0
                                    }
                                
                                # Mark as impulse move if momentum exceeds threshold
                                if momentum >= momentum_threshold:
                                    impulse_moves[ticker] = {
                                        'momentum': momentum,
                                        'score': int(score_match.group(1)) if score_match else 0
                                    }
        
        print(f"Found {len(impulse_moves)} tickers with impulse moves (>={momentum_threshold}% momentum)")
        return impulse_moves, ticker_performance
    
    def analyze_correlation(self, date_str):
        """Analyze correlation between hourly and daily VSR tickers"""
        print(f"\n=== Analyzing VSR Correlation for {date_str} ===\n")
        
        # Load data
        hourly_tickers = self.load_hourly_tickers(date_str)
        daily_tickers = self.load_daily_tickers(date_str)
        impulse_moves, ticker_performance = self.parse_vsr_logs(date_str)
        
        # Analysis results
        results = {
            'date': date_str,
            'hourly_to_daily_transitions': {},
            'impulse_move_analysis': {},
            'success_metrics': {}
        }
        
        # Track unique tickers
        all_hourly_tickers = set()
        for hour_tickers in hourly_tickers.values():
            all_hourly_tickers.update(hour_tickers)
        
        all_daily_tickers = set()
        for time_tickers in daily_tickers.values():
            all_daily_tickers.update(time_tickers)
        
        # Find tickers that appeared in both hourly and daily
        common_tickers = all_hourly_tickers.intersection(all_daily_tickers)
        
        print(f"\nTotal unique hourly tickers: {len(all_hourly_tickers)}")
        print(f"Total unique daily tickers: {len(all_daily_tickers)}")
        print(f"Tickers appearing in both: {len(common_tickers)}")
        print(f"Transition rate: {len(common_tickers)/len(all_hourly_tickers)*100:.1f}%")
        
        # Analyze impulse moves
        impulse_from_hourly = 0
        impulse_from_daily_only = 0
        
        for ticker in impulse_moves:
            if ticker in all_hourly_tickers:
                impulse_from_hourly += 1
            elif ticker in all_daily_tickers:
                impulse_from_daily_only += 1
        
        print(f"\nImpulse Moves Analysis:")
        print(f"Total tickers with impulse moves: {len(impulse_moves)}")
        print(f"Impulse moves from hourly tickers: {impulse_from_hourly}")
        print(f"Impulse moves from daily-only tickers: {impulse_from_daily_only}")
        
        # Hour-by-hour analysis
        print(f"\n=== Hour-by-Hour Transition Analysis ===")
        
        hourly_success = {}
        for hour, hour_tickers in sorted(hourly_tickers.items()):
            if hour_tickers:
                # Check how many made it to daily
                made_to_daily = [t for t in hour_tickers if t in all_daily_tickers]
                # Check how many had impulse moves
                had_impulse = [t for t in hour_tickers if t in impulse_moves]
                
                success_rate = len(made_to_daily) / len(hour_tickers) * 100
                impulse_rate = len(had_impulse) / len(hour_tickers) * 100
                
                hourly_success[hour] = {
                    'total': len(hour_tickers),
                    'to_daily': len(made_to_daily),
                    'impulse': len(had_impulse),
                    'success_rate': success_rate,
                    'impulse_rate': impulse_rate
                }
                
                print(f"\nHour {hour:02d}:00")
                print(f"  Total tickers: {len(hour_tickers)}")
                print(f"  Made to daily: {len(made_to_daily)} ({success_rate:.1f}%)")
                print(f"  Had impulse: {len(had_impulse)} ({impulse_rate:.1f}%)")
                
                # Show top performers
                if had_impulse:
                    print("  Top impulse movers:")
                    impulse_details = [(t, impulse_moves[t]['momentum']) for t in had_impulse if t in impulse_moves]
                    impulse_details.sort(key=lambda x: x[1], reverse=True)
                    for ticker, momentum in impulse_details[:5]:
                        print(f"    {ticker}: {momentum:.1f}% momentum")
        
        # Best hours for catching impulse moves
        best_hours = sorted(hourly_success.items(), 
                          key=lambda x: x[1]['impulse_rate'], 
                          reverse=True)[:3]
        
        print(f"\n=== Best Hours for Impulse Moves ===")
        for hour, metrics in best_hours:
            print(f"Hour {hour:02d}:00 - {metrics['impulse_rate']:.1f}% impulse rate ({metrics['impulse']}/{metrics['total']} tickers)")
        
        # Save detailed results
        results['hourly_success'] = hourly_success
        results['summary'] = {
            'total_hourly_tickers': len(all_hourly_tickers),
            'total_daily_tickers': len(all_daily_tickers),
            'common_tickers': len(common_tickers),
            'transition_rate': len(common_tickers)/len(all_hourly_tickers)*100 if all_hourly_tickers else 0,
            'total_impulse_moves': len(impulse_moves),
            'impulse_from_hourly': impulse_from_hourly,
            'impulse_success_rate': impulse_from_hourly/len(all_hourly_tickers)*100 if all_hourly_tickers else 0
        }
        
        return results
    
    def analyze_multiple_days(self, days=5):
        """Analyze multiple days of data"""
        all_results = []
        
        # Get recent dates
        dates = []
        for i in range(days):
            date = datetime.now() - timedelta(days=i+1)
            # Skip weekends
            if date.weekday() < 5:
                dates.append(date.strftime('%Y%m%d'))
        
        for date_str in dates:
            try:
                results = self.analyze_correlation(date_str)
                all_results.append(results)
            except Exception as e:
                print(f"Error analyzing {date_str}: {e}")
        
        # Aggregate results
        if all_results:
            print(f"\n\n=== AGGREGATE ANALYSIS ({len(all_results)} days) ===")
            
            avg_transition_rate = np.mean([r['summary']['transition_rate'] for r in all_results])
            avg_impulse_rate = np.mean([r['summary']['impulse_success_rate'] for r in all_results])
            
            print(f"\nAverage hourly to daily transition rate: {avg_transition_rate:.1f}%")
            print(f"Average impulse move success rate: {avg_impulse_rate:.1f}%")
            
            # Best hours across all days
            hour_aggregate = defaultdict(lambda: {'impulse_total': 0, 'ticker_total': 0})
            
            for result in all_results:
                for hour, metrics in result['hourly_success'].items():
                    hour_aggregate[hour]['impulse_total'] += metrics['impulse']
                    hour_aggregate[hour]['ticker_total'] += metrics['total']
            
            print(f"\n=== Best Hours Across All Days ===")
            for hour in sorted(hour_aggregate.keys()):
                data = hour_aggregate[hour]
                if data['ticker_total'] > 0:
                    impulse_rate = data['impulse_total'] / data['ticker_total'] * 100
                    print(f"Hour {hour:02d}:00 - {impulse_rate:.1f}% impulse rate ({data['impulse_total']}/{data['ticker_total']} total)")
        
        return all_results

def main():
    analyzer = VSRHourlyDailyAnalyzer()
    
    # Analyze recent days
    results = analyzer.analyze_multiple_days(days=3)
    
    # Save results
    output_file = os.path.join(analyzer.base_dir, 'Daily', 'analysis', 'vsr_hourly_daily_correlation_report.json')
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    main()