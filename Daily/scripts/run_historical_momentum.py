#!/usr/bin/env python3
"""
Run Historical Momentum Scans
Runs the momentum scanner for the past 14 days to generate historical data
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
    print(f"Starting historical momentum scan for past {days} days...")
    
    # Initialize scanner
    scanner = StandaloneMomentumScanner(user_name='Sai')
    
    # Start from 14 days ago
    end_date = datetime.datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Process each day
    current_date = start_date
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
                print("Skipping to avoid overwriting...")
            else:
                # Run the scan
                results = scanner.run_scan(current_date)
                
                # Print summary
                for timeframe, df in results.items():
                    print(f"{timeframe}: {len(df)} tickers with positive momentum")
                
                # Add a small delay to avoid rate limiting
                time.sleep(2)
            
        except Exception as e:
            print(f"Error running scan for {current_date}: {e}")
        
        # Move to next day
        current_date += timedelta(days=1)
    
    print(f"\n{'='*60}")
    print("Historical scan complete!")
    print(f"{'='*60}")
    
    # Print summary of all files created
    print("\nGenerated files:")
    all_files = sorted([f for f in os.listdir(scanner.momentum_dir) 
                       if f.startswith("India-Momentum_Report_")])
    for f in all_files[-days:]:  # Show last N files
        print(f"  - {f}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Run historical momentum scans')
    parser.add_argument('--days', type=int, default=14, help='Number of days to scan (default: 14)')
    
    args = parser.parse_args()
    
    run_historical_scans(args.days)