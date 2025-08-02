#!/usr/bin/env python3
"""
Backfill momentum data for past 14 days
"""

import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.scanners.momentum_scanner import MomentumScanner

def backfill_momentum_data(days=14):
    """Run momentum scanner for past N days"""
    print(f"Starting backfill for past {days} days...")
    
    # Create scanner instance
    scanner = MomentumScanner(user_name='Sai')
    
    # Run for each day
    for i in range(days, -1, -1):
        scan_date = datetime.now() - timedelta(days=i)
        
        # Skip weekends
        if scan_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            print(f"Skipping weekend: {scan_date.strftime('%Y-%m-%d %A')}")
            continue
        
        print(f"\nProcessing date: {scan_date.strftime('%Y-%m-%d %A')}")
        
        try:
            # Run scan for this date
            results = scanner.run_scan(scan_date)
            
            # Print summary
            daily_count = len(results.get('Daily', []))
            weekly_count = len(results.get('Weekly', []))
            print(f"  Daily: {daily_count} tickers")
            print(f"  Weekly: {weekly_count} tickers")
            
        except Exception as e:
            print(f"  Error processing {scan_date.strftime('%Y-%m-%d')}: {e}")
    
    print("\nBackfill complete!")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Backfill momentum data')
    parser.add_argument('--days', type=int, default=14, help='Number of days to backfill')
    
    args = parser.parse_args()
    backfill_momentum_data(args.days)