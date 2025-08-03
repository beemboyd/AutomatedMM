#!/usr/bin/env python3
"""
Check specific days we analyzed earlier
"""

import json
import pandas as pd
from datetime import datetime

# Load breadth data
breadth_file = '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/historical_breadth_data/sma_breadth_historical_latest.json'

with open(breadth_file, 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data)
df['date'] = pd.to_datetime(df['date'])
df['sma20_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma20_percent', 0))
df['sma50_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma50_percent', 0))

# Check specific dates
dates_to_check = ['2025-07-22', '2025-07-25', '2025-07-28']

print("Checking breadth for specific dates:")
print("="*60)

for date_str in dates_to_check:
    date = pd.to_datetime(date_str)
    row = df[df['date'] == date]
    
    if not row.empty:
        sma20 = row['sma20_percent'].values[0]
        sma50 = row['sma50_percent'].values[0]
        print(f"\nDate: {date_str}")
        print(f"SMA20 Breadth: {sma20}%")
        print(f"SMA50 Breadth: {sma50}%")
        
        # Our known performance
        if date_str == '2025-07-22':
            print("Known Performance: 80% success, +2.91% avg PnL")
        elif date_str == '2025-07-25':
            print("Known Performance: 66.7% success, +0.66% avg PnL")
        elif date_str == '2025-07-28':
            print("Known Performance: 57.1% success, -0.86% avg PnL")

# Find more dates with very low breadth
print("\n" + "="*60)
print("Days with SMA20 breadth < 30%:")
print("="*60)

low_breadth = df[df['sma20_percent'] < 30].sort_values('date', ascending=False).head(20)

print(f"\n{'Date':<12} {'SMA20':<8} {'SMA50':<8} {'Regime':<20}")
print("-"*50)

for _, row in low_breadth.iterrows():
    regime = row.get('market_regime', 'N/A')
    print(f"{row['date'].strftime('%Y-%m-%d'):<12} {row['sma20_percent']:<8.1f} {row['sma50_percent']:<8.1f} {regime:<20}")