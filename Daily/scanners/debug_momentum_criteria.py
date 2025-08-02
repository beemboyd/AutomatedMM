#!/usr/bin/env python3
"""Debug momentum scanner criteria"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.scanners.momentum_scanner import MomentumScanner
import pandas as pd

# Create scanner
scanner = MomentumScanner(user_name='Sai')

# Test with a few known liquid stocks
test_tickers = ['RELIANCE', 'TCS', 'INFY', 'HDFC', 'ICICIBANK']

print("Testing momentum criteria with liquid stocks...")
print("="*60)

for ticker in test_tickers:
    print(f"\nAnalyzing {ticker}:")
    
    # Fetch daily data
    data = scanner.fetch_ticker_data(ticker, 'day', 365)
    if data is None:
        print(f"  No data available")
        continue
    
    print(f"  Raw data shape: {data.shape}")
    if not data.empty:
        print(f"  Columns: {data.columns.tolist()}")
        
    # Calculate indicators
    data = scanner.calculate_indicators(data)
    
    if data.empty:
        print(f"  No data after calculating indicators")
        continue
    
    print(f"  Data shape: {data.shape}")
    print(f"  Date range: {data['date'].min()} to {data['date'].max()}")
    
    # Get latest values
    latest = data.iloc[-1]
    
    print(f"  Close: {latest['close']:.2f}")
    if 'EMA_100' in latest:
        print(f"  EMA_100: {latest['EMA_100']:.2f}")
        print(f"  Price > EMA_100: {latest['close'] > latest['EMA_100']}")
    
    if 'Slope' in latest:
        print(f"  Slope: {latest['Slope']:.2f}%")
        print(f"  Slope > 0: {latest['Slope'] > 0}")
        
    if 'WM' in latest:
        print(f"  WM: {latest['WM']:.2f}")
        
    # Check if it would pass
    passes = True
    if 'EMA_100' in latest and not pd.isna(latest['EMA_100']):
        if latest['close'] <= latest['EMA_100']:
            passes = False
            print("  ❌ Failed: Price below EMA_100")
    
    if 'Slope' in latest and not pd.isna(latest['Slope']):
        if latest['Slope'] <= 0:
            passes = False
            print("  ❌ Failed: Negative slope")
            
    if passes:
        print("  ✅ PASSES momentum criteria!")