#!/usr/bin/env python3
"""
Unified KC Limit Trending Analyzer
Analyzes KC Upper Limit (Long) and KC Lower Limit (Short) strategies
Similar to unified_reversal_analyzer.py but for KC strategies
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
import json
import glob
import argparse
from collections import defaultdict

# Add parent directories to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import configuration and utilities
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import get_config
from analysis.user_aware_data_handler import UserAwareDataHandler

class UnifiedKCLimitAnalyzer:
    def __init__(self, direction='long', from_date=None, to_date=None, user='Sai'):
        """
        Initialize analyzer for KC Limit strategies
        
        Args:
            direction: 'long' for KC Upper Limit or 'short' for KC Lower Limit
            from_date: Start date for analysis
            to_date: End date for analysis
            user: User for API credentials
        """
        self.direction = direction.lower()
        self.user = user
        
        # Set dates
        if to_date is None:
            self.to_date = datetime.now()
        else:
            self.to_date = datetime.strptime(to_date, '%Y-%m-%d') if isinstance(to_date, str) else to_date
            
        if from_date is None:
            self.from_date = self.to_date - timedelta(days=7)
        else:
            self.from_date = datetime.strptime(from_date, '%Y-%m-%d') if isinstance(from_date, str) else from_date
        
        # Set file patterns and directories based on direction
        if self.direction == 'long':
            self.results_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/results'
            self.file_pattern = 'KC_Upper_Limit_Trending_*.xlsx'
            self.strategy_name = 'KC Upper Limit Trending'
        else:  # short
            self.results_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/results-s'
            self.file_pattern = 'KC_Lower_Limit_Trending_*.xlsx'
            self.strategy_name = 'KC Lower Limit Trending'
        
        # Score filters - KC strategies typically use different scoring
        # We'll use Pattern_Strength or Advanced_Score
        self.score_column = 'Advanced_Score'
        self.min_score_threshold = 50  # Adjust based on KC scoring system
        
        # Load configuration
        self.config = get_config()
        credential_section = f'API_CREDENTIALS_{user}'
        
        # Initialize data handler
        try:
            self.data_handler = UserAwareDataHandler(
                api_key=self.config.get(credential_section, 'api_key'),
                access_token=self.config.get(credential_section, 'access_token')
            )
        except Exception as e:
            raise ValueError(f"No credentials found for user {user}: {e}")
        
        # Analysis storage
        self.all_tickers = set()
        self.daily_tickers = defaultdict(list)
        self.ticker_appearances = defaultdict(list)
        self.ticker_performance = {}
        
    def find_scan_files(self):
        """Find all scan files within the date range"""
        pattern = os.path.join(self.results_dir, self.file_pattern)
        all_files = glob.glob(pattern)
        
        valid_files = []
        for file_path in all_files:
            try:
                # Extract date from filename
                filename = os.path.basename(file_path)
                date_str = filename.split('_')[-2]  # Format: KC_Upper_Limit_Trending_YYYYMMDD_HHMMSS.xlsx
                file_date = datetime.strptime(date_str, '%Y%m%d')
                
                if self.from_date.date() <= file_date.date() <= self.to_date.date():
                    valid_files.append({
                        'path': file_path,
                        'date': file_date,
                        'datetime': datetime.strptime(f"{date_str}_{filename.split('_')[-1].split('.')[0]}", '%Y%m%d_%H%M%S')
                    })
            except Exception as e:
                print(f"Error parsing file {file_path}: {e}")
                continue
        
        # Sort by datetime
        valid_files.sort(key=lambda x: x['datetime'])
        
        return valid_files
    
    def process_scan_file(self, file_info):
        """Process a single scan file"""
        try:
            df = pd.read_excel(file_info['path'])
            
            if df.empty:
                return
            
            # Filter by score if score column exists
            if self.score_column in df.columns:
                # Convert score to numeric, handling string values
                df[self.score_column] = pd.to_numeric(df[self.score_column], errors='coerce')
                df = df[df[self.score_column] >= self.min_score_threshold]
                df = df.dropna(subset=[self.score_column])
            
            # For each ticker in the scan
            for _, row in df.iterrows():
                ticker = row['Ticker']
                date = file_info['date'].date()
                
                # Store ticker info
                self.all_tickers.add(ticker)
                self.daily_tickers[date].append(ticker)
                
                # Store appearance details
                appearance = {
                    'date': date,
                    'datetime': file_info['datetime'],
                    'entry_price': row.get('Entry_Price', 0),
                    'stop_loss': row.get('Stop_Loss', 0),
                    'target1': row.get('Target1', 0),
                    'target2': row.get('Target2', 0),
                    'score': row.get(self.score_column, 0),
                    'pattern_strength': row.get('Pattern_Strength', 0),
                    'h2_count': row.get('H2_Count', 0),
                    'momentum_10d': row.get('Momentum_10D', 0)
                }
                
                self.ticker_appearances[ticker].append(appearance)
                
        except Exception as e:
            print(f"Error processing file {file_info['path']}: {e}")
    
    def analyze_ticker_performance(self, ticker, appearances):
        """Analyze performance of a ticker based on its appearances"""
        try:
            # Get the first appearance within our date range
            first_appearance = appearances[0]
            entry_price = first_appearance['entry_price']
            
            if entry_price <= 0:
                return None
            
            # Fetch historical data
            historical_data = self.data_handler.fetch_historical_data(
                ticker, 
                'day',
                self.from_date - timedelta(days=5),  # Extra days for context
                self.to_date + timedelta(days=1)
            )
            
            if historical_data is None or historical_data.empty:
                return None
            
            # Find entry date data
            entry_date = pd.Timestamp(first_appearance['date'])
            
            # Get data from entry date onwards
            # Ensure index is datetime
            historical_data.index = pd.to_datetime(historical_data.index)
            mask = historical_data.index >= entry_date
            future_data = historical_data[mask]
            
            if future_data.empty:
                return None
            
            # Calculate returns for different holding periods
            entry_idx = 0
            results = {
                'ticker': ticker,
                'entry_date': first_appearance['date'],
                'entry_price': entry_price,
                'stop_loss': first_appearance['stop_loss'],
                'target1': first_appearance['target1'],
                'target2': first_appearance['target2'],
                'score': first_appearance['score'],
                'pattern_strength': first_appearance['pattern_strength'],
                'appearances': len(appearances)
            }
            
            # Check if stop loss or targets were hit
            for i, (date, row) in enumerate(future_data.iterrows()):
                if i == 0:
                    continue  # Skip entry day
                
                low = row['low']
                high = row['high']
                close = row['close']
                
                # For long positions
                if self.direction == 'long':
                    # Check stop loss
                    if low <= first_appearance['stop_loss']:
                        results['exit_type'] = 'stop_loss'
                        results['exit_date'] = date
                        results['exit_price'] = first_appearance['stop_loss']
                        results['return_pct'] = ((results['exit_price'] - entry_price) / entry_price) * 100
                        results['days_held'] = i
                        break
                    
                    # Check targets
                    if high >= first_appearance['target1'] and 'exit_type' not in results:
                        results['target1_hit'] = True
                        results['target1_date'] = date
                        results['target1_days'] = i
                        
                    if high >= first_appearance['target2']:
                        results['exit_type'] = 'target2'
                        results['exit_date'] = date
                        results['exit_price'] = first_appearance['target2']
                        results['return_pct'] = ((results['exit_price'] - entry_price) / entry_price) * 100
                        results['days_held'] = i
                        break
                        
                else:  # short positions
                    # Check stop loss
                    if high >= first_appearance['stop_loss']:
                        results['exit_type'] = 'stop_loss'
                        results['exit_date'] = date
                        results['exit_price'] = first_appearance['stop_loss']
                        results['return_pct'] = ((entry_price - results['exit_price']) / entry_price) * 100
                        results['days_held'] = i
                        break
                    
                    # Check targets
                    if low <= first_appearance['target1'] and 'target1_hit' not in results:
                        results['target1_hit'] = True
                        results['target1_date'] = date
                        results['target1_days'] = i
                        
                    if low <= first_appearance['target2']:
                        results['exit_type'] = 'target2'
                        results['exit_date'] = date
                        results['exit_price'] = first_appearance['target2']
                        results['return_pct'] = ((entry_price - results['exit_price']) / entry_price) * 100
                        results['days_held'] = i
                        break
            
            # If no exit, calculate return to end date
            if 'exit_type' not in results and len(future_data) > 1:
                last_close = future_data.iloc[-1]['close']
                results['exit_type'] = 'end_of_period'
                results['exit_date'] = future_data.index[-1]
                results['exit_price'] = last_close
                
                if self.direction == 'long':
                    results['return_pct'] = ((last_close - entry_price) / entry_price) * 100
                else:
                    results['return_pct'] = ((entry_price - last_close) / entry_price) * 100
                    
                results['days_held'] = len(future_data) - 1
            
            # Mark as winner/loser
            if 'return_pct' in results:
                results['is_winner'] = results['return_pct'] > 0
            
            return results
            
        except Exception as e:
            print(f"Error analyzing ticker {ticker}: {e}")
            return None
    
    def run_analysis(self):
        """Run the complete analysis"""
        print(f"\n{'='*80}")
        print(f"{self.strategy_name} Analysis")
        print(f"Period: {self.from_date.strftime('%Y-%m-%d')} to {self.to_date.strftime('%Y-%m-%d')}")
        print(f"Direction: {self.direction.upper()}")
        print(f"{'='*80}\n")
        
        # Find and process all scan files
        scan_files = self.find_scan_files()
        print(f"Found {len(scan_files)} scan files in date range")
        
        for file_info in scan_files:
            self.process_scan_file(file_info)
        
        # Analyze each ticker's performance
        print(f"\nAnalyzing performance for {len(self.all_tickers)} unique tickers...")
        
        for ticker in self.all_tickers:
            appearances = self.ticker_appearances[ticker]
            performance = self.analyze_ticker_performance(ticker, appearances)
            if performance:
                self.ticker_performance[ticker] = performance
        
        # Generate summary statistics
        self.generate_summary()
        
        # Save detailed results
        self.save_results()
    
    def generate_summary(self):
        """Generate and print summary statistics"""
        if not self.ticker_performance:
            print("No performance data available")
            return
        
        # Convert to DataFrame for easier analysis
        perf_df = pd.DataFrame(list(self.ticker_performance.values()))
        
        # Overall statistics
        total_trades = len(perf_df)
        winners = perf_df[perf_df['is_winner'] == True]
        losers = perf_df[perf_df['is_winner'] == False]
        
        win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0
        avg_return = perf_df['return_pct'].mean()
        avg_winner = winners['return_pct'].mean() if len(winners) > 0 else 0
        avg_loser = losers['return_pct'].mean() if len(losers) > 0 else 0
        
        print(f"\n{'='*60}")
        print(f"SUMMARY STATISTICS - {self.strategy_name}")
        print(f"{'='*60}")
        print(f"Total Unique Tickers: {total_trades}")
        print(f"Winners: {len(winners)} ({win_rate:.1f}%)")
        print(f"Losers: {len(losers)} ({100-win_rate:.1f}%)")
        print(f"\nAverage Return: {avg_return:.2f}%")
        print(f"Average Winner: {avg_winner:.2f}%")
        print(f"Average Loser: {avg_loser:.2f}%")
        
        # Exit type analysis
        if 'exit_type' in perf_df.columns:
            print(f"\nExit Type Distribution:")
            exit_types = perf_df['exit_type'].value_counts()
            for exit_type, count in exit_types.items():
                pct = (count / total_trades * 100)
                print(f"  {exit_type}: {count} ({pct:.1f}%)")
        
        # Target hit analysis
        if 'target1_hit' in perf_df.columns:
            target1_hits = perf_df['target1_hit'].sum()
            print(f"\nTarget 1 Hit Rate: {target1_hits}/{total_trades} ({target1_hits/total_trades*100:.1f}%)")
        
        # Days held analysis
        if 'days_held' in perf_df.columns:
            print(f"\nAverage Days Held: {perf_df['days_held'].mean():.1f}")
            print(f"  Winners: {winners['days_held'].mean():.1f}" if len(winners) > 0 else "  Winners: N/A")
            print(f"  Losers: {losers['days_held'].mean():.1f}" if len(losers) > 0 else "  Losers: N/A")
        
        # Top performers
        print(f"\nTop 5 Performers:")
        top_performers = perf_df.nlargest(5, 'return_pct')
        for _, row in top_performers.iterrows():
            print(f"  {row['ticker']}: {row['return_pct']:.2f}% in {row.get('days_held', 'N/A')} days")
        
        print(f"\nBottom 5 Performers:")
        bottom_performers = perf_df.nsmallest(5, 'return_pct')
        for _, row in bottom_performers.iterrows():
            print(f"  {row['ticker']}: {row['return_pct']:.2f}% in {row.get('days_held', 'N/A')} days")
        
        # Score analysis
        if self.score_column in perf_df.columns:
            print(f"\nPerformance by Score Range:")
            score_bins = pd.cut(perf_df[self.score_column], bins=[0, 60, 70, 80, 90, 100])
            score_analysis = perf_df.groupby(score_bins).agg({
                'return_pct': ['mean', 'count'],
                'is_winner': 'mean'
            })
            
            for score_range, data in score_analysis.iterrows():
                if data[('return_pct', 'count')] > 0:
                    print(f"  {score_range}: {data[('return_pct', 'mean')]:.2f}% avg return, "
                          f"{data[('is_winner', 'mean')]*100:.1f}% win rate "
                          f"(n={int(data[('return_pct', 'count')])})")
    
    def save_results(self):
        """Save detailed results to files"""
        if not self.ticker_performance:
            return
        
        # Create output directory
        output_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports'
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert to DataFrame
        perf_df = pd.DataFrame(list(self.ticker_performance.values()))
        
        # Save to Excel
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_file = os.path.join(output_dir, f'kc_{self.direction}_analysis_{timestamp}.xlsx')
        
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = {
                'Metric': ['Total Tickers', 'Winners', 'Losers', 'Win Rate %', 
                          'Avg Return %', 'Avg Winner %', 'Avg Loser %'],
                'Value': [
                    len(perf_df),
                    len(perf_df[perf_df['is_winner'] == True]),
                    len(perf_df[perf_df['is_winner'] == False]),
                    (perf_df['is_winner'].sum() / len(perf_df) * 100) if len(perf_df) > 0 else 0,
                    perf_df['return_pct'].mean(),
                    perf_df[perf_df['is_winner'] == True]['return_pct'].mean() if any(perf_df['is_winner']) else 0,
                    perf_df[perf_df['is_winner'] == False]['return_pct'].mean() if any(~perf_df['is_winner']) else 0
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Detailed results
            perf_df.to_excel(writer, sheet_name='Detailed_Results', index=False)
            
            # Daily ticker counts
            daily_counts = []
            for date, tickers in sorted(self.daily_tickers.items()):
                daily_counts.append({
                    'Date': date,
                    'Ticker_Count': len(tickers),
                    'Tickers': ', '.join(sorted(tickers))
                })
            if daily_counts:
                daily_df = pd.DataFrame(daily_counts)
                daily_df.to_excel(writer, sheet_name='Daily_Counts', index=False)
        
        # Save to JSON
        json_file = os.path.join(output_dir, f'kc_{self.direction}_analysis_{timestamp}.json')
        analysis_data = {
            'strategy': self.strategy_name,
            'direction': self.direction,
            'from_date': self.from_date.strftime('%Y-%m-%d'),
            'to_date': self.to_date.strftime('%Y-%m-%d'),
            'summary': {
                'total_tickers': len(perf_df),
                'win_rate': (perf_df['is_winner'].sum() / len(perf_df) * 100) if len(perf_df) > 0 else 0,
                'avg_return': perf_df['return_pct'].mean()
            },
            'ticker_performance': self.ticker_performance
        }
        
        with open(json_file, 'w') as f:
            json.dump(analysis_data, f, indent=2, default=str)
        
        print(f"\nResults saved to:")
        print(f"  - {excel_file}")
        print(f"  - {json_file}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Analyze KC Limit Trending strategies')
    parser.add_argument('--direction', choices=['long', 'short'], default='long',
                       help='Direction to analyze (long for KC Upper, short for KC Lower)')
    parser.add_argument('--from-date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--to-date', help='End date (YYYY-MM-DD)')
    parser.add_argument('--user', default='Sai', help='User for API credentials')
    
    args = parser.parse_args()
    
    analyzer = UnifiedKCLimitAnalyzer(
        direction=args.direction,
        from_date=args.from_date,
        to_date=args.to_date,
        user=args.user
    )
    
    analyzer.run_analysis()


if __name__ == "__main__":
    main()