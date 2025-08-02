#!/usr/bin/env python3
"""Run momentum scan immediately"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.scanners.momentum_scanner import MomentumScanner

# Create scanner - will use all tickers
scanner = MomentumScanner(user_name='Sai')

# Limit to first 50 tickers for quick test
scanner.tickers = scanner.tickers[:50]
print(f"Running scan with {len(scanner.tickers)} tickers...")

# Run scan
results = scanner.run_scan()

# Print results
print(f"\nScan complete!")
print(f"Daily momentum: {len(results.get('Daily', []))} tickers")
print(f"Weekly momentum: {len(results.get('Weekly', []))} tickers")

if results.get('Daily'):
    print("\nTop 5 Daily momentum stocks:")
    for i, row in results['Daily'].head(5).iterrows():
        print(f"  {row['Ticker']}: Slope={row['Slope']:.2f}%, WM={row['WM']:.2f}")

if results.get('Weekly'):  
    print("\nTop 5 Weekly momentum stocks:")
    for i, row in results['Weekly'].head(5).iterrows():
        print(f"  {row['Ticker']}: Slope={row['Slope']:.2f}%, WM={row['WM']:.2f}")