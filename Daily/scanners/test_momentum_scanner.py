#!/usr/bin/env python3
"""Test momentum scanner with limited tickers"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.scanners.momentum_scanner import MomentumScanner

# Create scanner
scanner = MomentumScanner(user_name='Sai')

# Limit to 5 tickers for test
scanner.tickers = scanner.tickers[:5]
print(f"Testing with tickers: {scanner.tickers}")

# Run scan
results = scanner.run_scan()

# Get counts for previous day
import datetime
yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
yesterday_counts = scanner.get_counts_for_date(yesterday)

print(f"\nYesterday's counts: Daily={yesterday_counts['Daily']}, Weekly={yesterday_counts['Weekly']}")
print(f"Today's counts: Daily={len(results['Daily'])}, Weekly={len(results['Weekly'])}")