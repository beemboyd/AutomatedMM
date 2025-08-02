#!/usr/bin/env python3
"""
Run Full Momentum Scan with Rate Limit Handling
Analyzes all 603 tickers with proper delays to avoid rate limiting
"""

import os
import sys
import datetime
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.scanners.momentum_scanner_standalone import StandaloneMomentumScanner

def run_full_scan(date_str=None):
    """Run momentum scanner for all tickers with rate limit handling"""
    
    # Parse date if provided
    if date_str:
        try:
            scan_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            print(f"Invalid date format: {date_str}. Using current date.")
            scan_date = None
    else:
        scan_date = None
    
    print(f"Running FULL momentum scan for {scan_date.strftime('%Y-%m-%d') if scan_date else 'today'}")
    print("This will analyze ALL 603 tickers...")
    print("Expected runtime: 15-20 minutes due to API rate limits")
    print("-" * 60)
    
    # Create scanner - it will use all tickers by default
    scanner = StandaloneMomentumScanner(user_name='Sai')
    
    # Add small delays between ticker processing to avoid rate limits
    # Modify the scanner to add delays
    original_analyze = scanner.analyze_timeframe
    
    def analyze_with_delay(ticker, interval, days):
        result = original_analyze(ticker, interval, days)
        # Add 0.5 second delay between each analysis to avoid rate limits
        time.sleep(0.5)
        return result
    
    scanner.analyze_timeframe = analyze_with_delay
    
    # Run the scan
    start_time = time.time()
    results = scanner.run_scan(scan_date)
    end_time = time.time()
    
    # Print detailed summary
    print("\n" + "="*60)
    print("FULL MOMENTUM SCAN COMPLETE")
    print("="*60)
    print(f"Total tickers analyzed: {len(scanner.tickers)}")
    print(f"Time taken: {(end_time - start_time)/60:.1f} minutes")
    print(f"\nResults for {scan_date.strftime('%Y-%m-%d') if scan_date else datetime.datetime.now().strftime('%Y-%m-%d')}:")
    
    for timeframe, df in results.items():
        print(f"\n{timeframe} Momentum:")
        print(f"  - Matching tickers: {len(df)}")
        if not df.empty:
            print(f"  - Tickers: {', '.join(df['Ticker'].tolist())}")
            print(f"  - Top 5 by WM:")
            for i, row in df.head(5).iterrows():
                ticker = row['Ticker']
                wm = row['WM'] if 'WM' in row and not pd.isna(row['WM']) else 0
                slope = row['Slope'] if 'Slope' in row and not pd.isna(row['Slope']) else 0
                print(f"    {i+1}. {ticker}: WM={wm:.2f}, Slope={slope:.2f}%")
    
    return results

if __name__ == '__main__':
    import argparse
    import pandas as pd
    
    parser = argparse.ArgumentParser(description='Run full momentum scan for all tickers')
    parser.add_argument('--date', type=str, help='Date to scan (YYYY-MM-DD format)')
    
    args = parser.parse_args()
    
    run_full_scan(args.date)