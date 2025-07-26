#!/usr/bin/env python
"""
Simplified Long Reversal Performance Analyzer
Analyzes all Long Reversal signals from past 4 weeks to see:
1. All unique tickers signaled
2. How many grew from entry price
3. By how much they grew
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

# Add parent directories to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import get_config

class SimpleLongReversalAnalyzer:
    def __init__(self, weeks_to_analyze=4, user='Sai'):
        """Initialize the analyzer"""
        self.weeks_to_analyze = weeks_to_analyze
        self.user = user
        
        # Initialize Kite connection
        self.config = get_config()
        credential_section = f'API_CREDENTIALS_{user}'
        
        if not self.config.config.has_section(credential_section):
            raise ValueError(f"No credentials found for user {user}")
            
        self.api_key = self.config.get(credential_section, 'api_key')
        self.access_token = self.config.get(credential_section, 'access_token')
        
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        
        # Paths
        self.results_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/results'
        self.output_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports'
        os.makedirs(self.output_dir, exist_ok=True)
        
    def find_scan_files(self):
        """Find all Long Reversal scan files from past 4 weeks"""
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=self.weeks_to_analyze)
        
        print(f"\nSearching for Long Reversal signals from {start_date.date()} to {end_date.date()}")
        
        scan_files = []
        pattern = os.path.join(self.results_dir, 'Long_Reversal_Daily_*.xlsx')
        
        for file_path in glob.glob(pattern):
            filename = os.path.basename(file_path)
            try:
                # Extract date from filename: Long_Reversal_Daily_YYYYMMDD_HHMMSS.xlsx
                date_str = filename.split('_')[3]
                file_date = datetime.strptime(date_str, '%Y%m%d')
                
                if start_date <= file_date <= end_date:
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
        """Get current price for a ticker"""
        try:
            ltp_data = self.kite.ltp(f"NSE:{ticker}")
            key = f"NSE:{ticker}"
            if ltp_data and key in ltp_data:
                return ltp_data[key]["last_price"]
        except Exception as e:
            print(f"Error getting price for {ticker}: {e}")
        return None
    
    def analyze(self):
        """Run the simplified analysis"""
        # Find all scan files
        scan_files = self.find_scan_files()
        if not scan_files:
            print("No scan files found!")
            return
        
        # Collect all signals
        all_signals = []
        
        for scan_file in scan_files:
            try:
                df = pd.read_excel(scan_file['file'])
                
                # Add signal date to each row
                df['signal_date'] = scan_file['date']
                df['signal_file'] = scan_file['filename']
                
                # Filter for 5/7 score
                df_filtered = df[df['Score'] == '5/7']
                
                # Take top 10
                df_filtered = df_filtered.head(10)
                
                if not df_filtered.empty:
                    all_signals.append(df_filtered)
                    
            except Exception as e:
                print(f"Error reading {scan_file['filename']}: {e}")
                continue
        
        if not all_signals:
            print("No signals found!")
            return
        
        # Combine all signals
        signals_df = pd.concat(all_signals, ignore_index=True)
        print(f"\nTotal signals collected: {len(signals_df)}")
        
        # Get unique tickers
        unique_tickers = signals_df['Ticker'].unique()
        print(f"Unique tickers: {len(unique_tickers)}")
        
        # Analyze each unique ticker
        ticker_analysis = []
        
        for ticker in unique_tickers:
            # Get all signals for this ticker
            ticker_signals = signals_df[signals_df['Ticker'] == ticker].sort_values('signal_date')
            
            # Get first signal (earliest entry)
            first_signal = ticker_signals.iloc[0]
            entry_price = first_signal['Entry_Price']
            signal_date = first_signal['signal_date']
            
            # Get current price
            current_price = self.get_current_price(ticker)
            
            if current_price:
                price_change = current_price - entry_price
                price_change_pct = (price_change / entry_price) * 100
                grew = price_change > 0
                
                ticker_analysis.append({
                    'ticker': ticker,
                    'first_signal_date': signal_date,
                    'signal_count': len(ticker_signals),
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'price_change': price_change,
                    'price_change_pct': price_change_pct,
                    'grew': grew
                })
                
                print(f"{ticker}: Entry={entry_price:.2f}, Current={current_price:.2f}, "
                      f"Change={price_change_pct:+.2f}% {'✓' if grew else '✗'}")
        
        # Summary statistics
        analysis_df = pd.DataFrame(ticker_analysis)
        
        if not analysis_df.empty:
            winners = analysis_df[analysis_df['grew']].shape[0]
            total = len(analysis_df)
            win_rate = (winners / total) * 100
            
            avg_gain = analysis_df[analysis_df['grew']]['price_change_pct'].mean() if winners > 0 else 0
            avg_loss = analysis_df[~analysis_df['grew']]['price_change_pct'].mean() if (total - winners) > 0 else 0
            overall_avg = analysis_df['price_change_pct'].mean()
            
            # Create summary
            summary = {
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'weeks_analyzed': self.weeks_to_analyze,
                'total_signals': len(signals_df),
                'unique_tickers': len(unique_tickers),
                'winners': winners,
                'losers': total - winners,
                'win_rate': win_rate,
                'average_gain': avg_gain,
                'average_loss': avg_loss,
                'overall_average': overall_avg,
                'best_performer': {
                    'ticker': analysis_df.loc[analysis_df['price_change_pct'].idxmax()]['ticker'],
                    'gain': analysis_df['price_change_pct'].max()
                },
                'worst_performer': {
                    'ticker': analysis_df.loc[analysis_df['price_change_pct'].idxmin()]['ticker'],
                    'loss': analysis_df['price_change_pct'].min()
                }
            }
            
            # Print summary
            print("\n" + "="*60)
            print("SUMMARY")
            print("="*60)
            print(f"Total unique tickers analyzed: {total}")
            print(f"Winners (grew from entry): {winners} ({win_rate:.1f}%)")
            print(f"Losers: {total - winners} ({100-win_rate:.1f}%)")
            print(f"Average gain: {avg_gain:+.2f}%")
            print(f"Average loss: {avg_loss:+.2f}%")
            print(f"Overall average: {overall_avg:+.2f}%")
            print(f"Best performer: {summary['best_performer']['ticker']} ({summary['best_performer']['gain']:+.2f}%)")
            print(f"Worst performer: {summary['worst_performer']['ticker']} ({summary['worst_performer']['loss']:+.2f}%)")
            print("="*60)
            
            # Save results
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Save detailed analysis
            excel_file = os.path.join(self.output_dir, f'simple_long_reversal_analysis_{timestamp}.xlsx')
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # Summary sheet
                summary_df = pd.DataFrame([summary])
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Detailed ticker analysis
                analysis_df.to_excel(writer, sheet_name='Ticker_Analysis', index=False)
                
                # All signals
                signals_df.to_excel(writer, sheet_name='All_Signals', index=False)
            
            # Save JSON report
            json_file = os.path.join(self.output_dir, f'simple_long_reversal_analysis_{timestamp}.json')
            report = {
                'summary': summary,
                'ticker_analysis': analysis_df.to_dict('records'),
                'signal_files': [sf['filename'] for sf in scan_files]
            }
            
            with open(json_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            # Save latest version
            latest_excel = os.path.join(self.output_dir, 'latest_simple_analysis.xlsx')
            analysis_df.to_excel(latest_excel, index=False)
            
            latest_json = os.path.join(self.output_dir, 'latest_simple_analysis.json')
            with open(latest_json, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            print(f"\nResults saved to:")
            print(f"  - {excel_file}")
            print(f"  - {json_file}")
            print(f"  - {latest_excel}")
            print(f"  - {latest_json}")

def main():
    """Main function"""
    analyzer = SimpleLongReversalAnalyzer(weeks_to_analyze=4, user='Sai')
    analyzer.analyze()

if __name__ == "__main__":
    main()