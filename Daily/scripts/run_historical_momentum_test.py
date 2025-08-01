#!/usr/bin/env python3
"""
Run Historical Momentum Scans - Test Mode
Runs the momentum scanner for the past 14 days with limited tickers
"""

import os
import sys
import datetime
from datetime import timedelta
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.scanners.momentum_scanner_standalone import StandaloneMomentumScanner

def run_historical_scans(days: int = 14):
    """Run momentum scanner for past N days"""
    print(f"Starting historical momentum scan for past {days} days (TEST MODE)...")
    
    # Initialize scanner
    scanner = StandaloneMomentumScanner(user_name='Sai')
    
    # Limit to first 50 tickers for faster processing
    scanner.tickers = scanner.tickers[:50]
    print(f"Running with {len(scanner.tickers)} tickers in test mode")
    
    # Start from 14 days ago
    end_date = datetime.datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Process each day
    current_date = start_date
    successful_scans = 0
    
    while current_date <= end_date:
        # Skip weekends
        if current_date.weekday() >= 5:
            print(f"Skipping weekend: {current_date.strftime('%Y-%m-%d')}")
            current_date += timedelta(days=1)
            continue
        
        print(f"\n{'='*60}")
        print(f"Running scan for: {current_date.strftime('%Y-%m-%d %A')}")
        print(f"{'='*60}")
        
        try:
            # Check if report already exists
            date_str = current_date.strftime('%Y%m%d')
            existing_files = [f for f in os.listdir(scanner.momentum_dir) 
                            if f.startswith(f"India-Momentum_Report_{date_str}")]
            
            if existing_files:
                print(f"Report already exists for {date_str}: {existing_files[0]}")
                successful_scans += 1
            else:
                # Run the scan
                results = scanner.run_scan(current_date)
                
                # Print summary
                for timeframe, df in results.items():
                    print(f"{timeframe}: {len(df)} tickers with positive momentum")
                
                successful_scans += 1
                
                # Add a delay to avoid rate limiting
                time.sleep(5)
            
        except Exception as e:
            print(f"Error running scan for {current_date}: {e}")
        
        # Move to next day
        current_date += timedelta(days=1)
    
    print(f"\n{'='*60}")
    print(f"Historical scan complete! Successfully scanned {successful_scans} days")
    print(f"{'='*60}")
    
    # Print summary of all files created
    print("\nGenerated files:")
    all_files = sorted([f for f in os.listdir(scanner.momentum_dir) 
                       if f.startswith("India-Momentum_Report_")])
    for f in all_files[-days:]:  # Show last N files
        print(f"  - {f}")
    
    # Generate count summary
    print("\nDaily and Weekly counts by date:")
    print(f"{'Date':<12} {'Daily':<8} {'Weekly':<8}")
    print("-" * 30)
    
    test_date = start_date
    while test_date <= end_date:
        if test_date.weekday() < 5:  # Weekday
            counts = scanner.get_counts_for_date(test_date)
            print(f"{test_date.strftime('%Y-%m-%d'):<12} {counts['Daily']:<8} {counts['Weekly']:<8}")
        test_date += timedelta(days=1)


if __name__ == '__main__':
    run_historical_scans(14)