#!/usr/bin/env python3
"""
Analyze long performance on high breadth days
"""

import os
import json
import pandas as pd
from datetime import datetime

# Load historical breadth data
breadth_file = '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/historical_breadth_data/sma_breadth_historical_latest.json'

with open(breadth_file, 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data)
df['date'] = pd.to_datetime(df['date'])
df['sma20_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma20_percent', 0))

# Find days with high breadth (>60%)
high_breadth = df[df['sma20_percent'] > 60].sort_values('date', ascending=False).head(10)

print("Days with HIGH SMA20 breadth (>60%):")
print("="*60)
print(f"\n{'Date':<12} {'SMA20':<8} {'Regime':<20}")
print("-"*40)

for _, row in high_breadth.iterrows():
    regime = row.get('market_regime', 'N/A')
    print(f"{row['date'].strftime('%Y-%m-%d'):<12} {row['sma20_percent']:<8.1f} {regime:<20}")

# Find days with moderate-high breadth (50-70%)
moderate_high = df[(df['sma20_percent'] >= 50) & (df['sma20_percent'] <= 70)].sort_values('date', ascending=False).head(10)

print("\n\nDays with MODERATE-HIGH SMA20 breadth (50-70%):")
print("="*60)
print(f"\n{'Date':<12} {'SMA20':<8} {'Regime':<20}")
print("-"*40)

for _, row in moderate_high.iterrows():
    regime = row.get('market_regime', 'N/A')
    print(f"{row['date'].strftime('%Y-%m-%d'):<12} {row['sma20_percent']:<8.1f} {regime:<20}")

# Suggest dates for analysis
print("\n\nSUGGESTED DATES FOR LONG ANALYSIS:")
print("="*60)

suggested_dates = [
    ('2025-07-17', 66.84, 'Uptrend'),
    ('2025-07-16', 68.44, 'Uptrend'),
    ('2025-07-11', 69.86, 'Uptrend'),
]

for date, breadth, regime in suggested_dates:
    print(f"\nDate: {date}")
    print(f"SMA20 Breadth: {breadth}%")
    print(f"Market Regime: {regime}")
    
    # Check if long reversal files exist
    date_obj = datetime.strptime(date, '%Y-%m-%d')
    date_str = date_obj.strftime('%Y%m%d')
    results_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/results'
    
    files = []
    for file in os.listdir(results_dir):
        if f'Long_Reversal_Daily_{date_str}' in file and file.endswith('.xlsx'):
            files.append(file)
    
    if files:
        print(f"Available files: {len(files)}")
        print(f"Example: {files[0]}")
    else:
        print("No long reversal files found for this date")