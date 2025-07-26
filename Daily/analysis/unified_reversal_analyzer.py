#!/usr/bin/env python
"""
Unified Reversal Strategy Analyzer
Analyzes both Long and Short Reversal strategies for any date range
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
import glob
import json
from collections import defaultdict
from kiteconnect import KiteConnect
import argparse

# Add parent directories to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import get_config

class UnifiedReversalAnalyzer:
    def __init__(self, direction='long', from_date=None, to_date=None, user='Sai'):
        """
        Initialize the analyzer
        
        Args:
            direction: 'long' or 'short' reversal strategy
            from_date: Start date (datetime or string)
            to_date: End date (datetime or string)
            user: User for API credentials
        """
        self.direction = direction.lower()
        self.user = user
        
        # Parse dates
        if isinstance(from_date, str):
            self.from_date = datetime.strptime(from_date, '%Y-%m-%d')
        else:
            self.from_date = from_date or (datetime.now() - timedelta(weeks=4))
            
        if isinstance(to_date, str):
            self.to_date = datetime.strptime(to_date, '%Y-%m-%d')
        else:
            self.to_date = to_date or datetime.now()
        
        # Initialize Kite connection
        self.config = get_config()
        credential_section = f'API_CREDENTIALS_{user}'
        
        if not self.config.config.has_section(credential_section):
            raise ValueError(f"No credentials found for user {user}")
            
        self.api_key = self.config.get(credential_section, 'api_key')
        self.access_token = self.config.get(credential_section, 'access_token')
        
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        
        # Set paths based on direction
        if self.direction == 'long':
            self.results_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/results'
            self.file_pattern = 'Long_Reversal_Daily_*.xlsx'
            self.score_filter = ['5/7']  # Long uses 5/7
        else:  # short
            self.results_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/results-s'
            self.file_pattern = 'Short_Reversal_Daily_*.xlsx'
            self.score_filter = ['7/11', '6/11']  # Short uses 7/11 or 6/11
            
        self.output_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports'
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Cache for current prices
        self.price_cache = {}
        
    def find_scan_files(self):
        """Find all scan files within the date range"""
        print(f"\nSearching for {self.direction.title()} Reversal signals from {self.from_date.date()} to {self.to_date.date()}")
        
        scan_files = []
        pattern = os.path.join(self.results_dir, self.file_pattern)
        
        for file_path in glob.glob(pattern):
            filename = os.path.basename(file_path)
            try:
                # Extract date from filename
                date_str = filename.split('_')[3]
                file_date = datetime.strptime(date_str, '%Y%m%d')
                
                # Only include files within our date range
                if self.from_date <= file_date <= self.to_date:
                    scan_files.append({
                        'file': file_path,
                        'date': file_date,
                        'filename': filename
                    })
            except (IndexError, ValueError):
                continue
        
        scan_files.sort(key=lambda x: x['date'])
        print(f"Found {len(scan_files)} scan files")
        return scan_files
    
    def get_current_price(self, ticker):
        """Get current price for a ticker (with caching)"""
        if ticker in self.price_cache:
            return self.price_cache[ticker]
            
        try:
            ltp_data = self.kite.ltp(f"NSE:{ticker}")
            key = f"NSE:{ticker}"
            if ltp_data and key in ltp_data:
                price = ltp_data[key]["last_price"]
                self.price_cache[ticker] = price
                return price
        except Exception as e:
            print(f"Error getting price for {ticker}: {e}")
        return None
    
    def calculate_performance(self, entry_price, current_price, direction):
        """Calculate performance based on direction"""
        if not current_price:
            return None, None, False
            
        if direction == 'long':
            # For long positions, profit comes from price increase
            price_change = current_price - entry_price
            price_change_pct = (price_change / entry_price) * 100
            success = price_change > 0
        else:  # short
            # For short positions, profit comes from price decrease
            price_change = entry_price - current_price
            price_change_pct = (price_change / entry_price) * 100
            success = price_change > 0
            
        return price_change_pct, price_change, success
    
    def analyze(self):
        """Run the analysis"""
        # Find all scan files
        scan_files = self.find_scan_files()
        if not scan_files:
            print("No scan files found!")
            return
        
        # Collect all signals
        all_signals = []
        signal_dates = defaultdict(list)  # Track signal dates for each ticker
        
        for scan_file in scan_files:
            try:
                df = pd.read_excel(scan_file['file'])
                
                # Filter by score
                mask = df['Score'].isin(self.score_filter)
                df_filtered = df[mask]
                
                # Take top 10
                df_filtered = df_filtered.head(10)
                
                if not df_filtered.empty:
                    # Add signal date
                    df_filtered['signal_date'] = scan_file['date']
                    df_filtered['signal_file'] = scan_file['filename']
                    all_signals.append(df_filtered)
                    
                    # Track signal dates for each ticker
                    for ticker in df_filtered['Ticker']:
                        signal_dates[ticker].append(scan_file['date'])
                    
            except Exception as e:
                print(f"Error reading {scan_file['filename']}: {e}")
                continue
        
        if not all_signals:
            print("No signals found!")
            return
        
        # Combine all signals
        signals_df = pd.concat(all_signals, ignore_index=True)
        print(f"\nTotal signals collected: {len(signals_df)}")
        
        # Get unique tickers (that appeared in the date range)
        unique_tickers = list(signal_dates.keys())
        print(f"Unique tickers in date range: {len(unique_tickers)}")
        
        # Analyze each unique ticker
        ticker_analysis = []
        
        print(f"\nAnalyzing {self.direction} positions...")
        for ticker in unique_tickers:
            # Get all signals for this ticker
            ticker_signals = signals_df[signals_df['Ticker'] == ticker].sort_values('signal_date')
            
            # Use the first signal as entry
            first_signal = ticker_signals.iloc[0]
            entry_price = first_signal['Entry_Price']
            first_signal_date = first_signal['signal_date']
            
            # Get current price
            current_price = self.get_current_price(ticker)
            
            if current_price:
                price_change_pct, price_change, success = self.calculate_performance(
                    entry_price, current_price, self.direction
                )
                
                ticker_analysis.append({
                    'ticker': ticker,
                    'first_signal_date': first_signal_date,
                    'signal_count': len(ticker_signals),
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'price_change_pct': price_change_pct,
                    'price_change': price_change,
                    'success': success
                })
                
                status = '✓' if success else '✗'
                print(f"{ticker}: Entry={entry_price:.2f}, Current={current_price:.2f}, "
                      f"Performance={price_change_pct:+.2f}% {status}")
        
        # Create analysis DataFrame and generate report
        if ticker_analysis:
            analysis_df = pd.DataFrame(ticker_analysis)
            self.generate_report(analysis_df, signals_df, signal_dates)
        else:
            print("No ticker analysis results!")
    
    def generate_report(self, analysis_df, signals_df, signal_dates):
        """Generate comprehensive report"""
        # Calculate summary statistics
        winners = analysis_df[analysis_df['success']].shape[0]
        total = len(analysis_df)
        win_rate = (winners / total) * 100
        
        avg_gain = analysis_df[analysis_df['success']]['price_change_pct'].mean() if winners > 0 else 0
        avg_loss = analysis_df[~analysis_df['success']]['price_change_pct'].mean() if (total - winners) > 0 else 0
        overall_avg = analysis_df['price_change_pct'].mean()
        
        # Stack rank tickers by performance
        analysis_df_sorted = analysis_df.sort_values('price_change_pct', ascending=False)
        
        # Create summary
        summary = {
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'strategy': f'{self.direction.title()} Reversal',
            'date_range': f"{self.from_date.date()} to {self.to_date.date()}",
            'total_signals': len(signals_df),
            'unique_tickers': total,
            'winners': winners,
            'losers': total - winners,
            'win_rate': win_rate,
            'average_gain': avg_gain,
            'average_loss': avg_loss,
            'overall_average': overall_avg,
            'best_performer': {
                'ticker': analysis_df_sorted.iloc[0]['ticker'],
                'performance': analysis_df_sorted.iloc[0]['price_change_pct']
            },
            'worst_performer': {
                'ticker': analysis_df_sorted.iloc[-1]['ticker'],
                'performance': analysis_df_sorted.iloc[-1]['price_change_pct']
            }
        }
        
        # Print summary
        print("\n" + "="*60)
        print(f"{self.direction.upper()} REVERSAL STRATEGY SUMMARY")
        print("="*60)
        print(f"Date Range: {self.from_date.date()} to {self.to_date.date()}")
        print(f"Total unique tickers analyzed: {total}")
        print(f"Winners: {winners} ({win_rate:.1f}%)")
        print(f"Losers: {total - winners} ({100-win_rate:.1f}%)")
        print(f"Average gain: {avg_gain:+.2f}%")
        print(f"Average loss: {avg_loss:+.2f}%")
        print(f"Overall average: {overall_avg:+.2f}%")
        print(f"Best performer: {summary['best_performer']['ticker']} ({summary['best_performer']['performance']:+.2f}%)")
        print(f"Worst performer: {summary['worst_performer']['ticker']} ({summary['worst_performer']['performance']:+.2f}%)")
        
        # Print top 10 and bottom 10
        print("\n" + "="*60)
        print("TOP 10 PERFORMERS")
        print("="*60)
        for i, row in analysis_df_sorted.head(10).iterrows():
            print(f"{row['ticker']:12} {row['price_change_pct']:+8.2f}%")
        
        print("\n" + "="*60)
        print("BOTTOM 10 PERFORMERS")
        print("="*60)
        for i, row in analysis_df_sorted.tail(10).iterrows():
            print(f"{row['ticker']:12} {row['price_change_pct']:+8.2f}%")
        
        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        date_range_str = f"{self.from_date.strftime('%Y%m%d')}_{self.to_date.strftime('%Y%m%d')}"
        
        # Save Excel file
        excel_file = os.path.join(self.output_dir, 
                                  f'{self.direction}_reversal_analysis_{date_range_str}_{timestamp}.xlsx')
        
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            # Summary sheet
            summary_df = pd.DataFrame([summary])
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Stack ranked ticker analysis
            analysis_df_sorted.to_excel(writer, sheet_name='Ticker_Performance', index=False)
            
            # Signal distribution by date
            signal_dist = signals_df.groupby('signal_date').size().reset_index(name='signal_count')
            signal_dist.to_excel(writer, sheet_name='Signal_Distribution', index=False)
        
        # Save JSON report
        json_file = os.path.join(self.output_dir, 
                                 f'{self.direction}_reversal_analysis_{date_range_str}_{timestamp}.json')
        
        report = {
            'summary': summary,
            'ticker_performance': analysis_df_sorted.to_dict('records'),
            'signal_distribution': signal_dist.to_dict('records')
        }
        
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n" + "="*60)
        print(f"Results saved to:")
        print(f"  - {excel_file}")
        print(f"  - {json_file}")

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description='Unified Reversal Strategy Analyzer')
    parser.add_argument('--direction', type=str, choices=['long', 'short'], 
                        default='long', help='Strategy direction (long or short)')
    parser.add_argument('--from-date', type=str, 
                        help='Start date (YYYY-MM-DD), default: 4 weeks ago')
    parser.add_argument('--to-date', type=str, 
                        help='End date (YYYY-MM-DD), default: today')
    parser.add_argument('--user', type=str, default='Sai', 
                        help='User for API credentials')
    
    args = parser.parse_args()
    
    # Run analysis
    analyzer = UnifiedReversalAnalyzer(
        direction=args.direction,
        from_date=args.from_date,
        to_date=args.to_date,
        user=args.user
    )
    analyzer.analyze()

if __name__ == "__main__":
    main()