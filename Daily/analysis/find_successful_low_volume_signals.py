#!/usr/bin/env python3
"""
Find specific examples of successful low volume signals that achieved H2 targets
"""

import pandas as pd
import numpy as np
import glob
import os
from datetime import datetime

# Load the enhanced analysis results
results_file = "/Users/maverick/PycharmProjects/India-TS/Daily/analysis/enhanced_h2_analysis/enhanced_signal_analysis.csv"
df = pd.read_csv(results_file)

# Convert entry_date to datetime
df['entry_date'] = pd.to_datetime(df['entry_date'])

# Create volume categories
df['volume_category'] = pd.qcut(
    df['volume_ratio'], 
    q=[0, 0.25, 0.5, 0.75, 0.9, 1.0],
    labels=['Very Low', 'Low', 'Medium', 'High', 'Very High']
)

# Find successful Very Low volume signals that achieved H2
successful_low_volume = df[
    (df['volume_category'] == 'Very Low') & 
    (df['h2_achieved'] == True)
].sort_values('final_pnl_pct', ascending=False)

print("=== SUCCESSFUL LOW VOLUME SIGNALS THAT ACHIEVED H2 ===\n")
print(f"Total Very Low volume signals that achieved H2: {len(successful_low_volume)}")
print(f"Success rate: {len(successful_low_volume) / len(df[df['volume_category'] == 'Very Low']) * 100:.1f}%\n")

# Show top 20 examples with details
print("Top 20 Examples (sorted by profit):")
print("-" * 120)
print(f"{'Ticker':<12} {'Entry Date':<12} {'Vol Ratio':<10} {'Pattern':<10} {'Momentum':<10} {'Days to H2':<10} {'P&L %':<10}")
print("-" * 85)

for idx, row in successful_low_volume.head(20).iterrows():
    print(f"{row['ticker']:<12} {row['entry_date'].strftime('%Y-%m-%d'):<12} {row['volume_ratio']:<10.2f} "
          f"{row['pattern_score']:<10.1f} {row['momentum_5d']:<10.1f} {row['days_to_h2']:<10.0f} {row['final_pnl_pct']:<10.1f}")

# Now let's find the actual entry details from original files
print("\n\n=== DETAILED SIGNAL INFORMATION FOR TOP PERFORMERS ===\n")

# Function to find original signal details
def find_original_signal(ticker, entry_date):
    date_str = entry_date.strftime('%Y%m%d')
    pattern = f"/Users/maverick/PycharmProjects/India-TS/Daily/results/Long_Reversal_Daily_{date_str}_*.xlsx"
    files = glob.glob(pattern)
    
    for file in files:
        try:
            df_orig = pd.read_excel(file)
            signal = df_orig[df_orig['Ticker'] == ticker]
            if not signal.empty:
                return signal.iloc[0], os.path.basename(file)
        except:
            continue
    return None, None

# Show detailed info for top 10
top_10 = successful_low_volume.head(10)

for idx, row in top_10.iterrows():
    original, filename = find_original_signal(row['ticker'], row['entry_date'])
    
    if original is not None:
        print(f"\n{'='*80}")
        print(f"TICKER: {row['ticker']} | SIGNAL DATE: {row['entry_date'].strftime('%Y-%m-%d')}")
        print(f"File: {filename}")
        print(f"{'='*80}")
        print(f"Pattern: {original['Pattern']} | Direction: {original['Direction']}")
        print(f"Sector: {original['Sector']}")
        print(f"Entry Price: ₹{original['Entry_Price']:.2f}")
        print(f"Stop Loss: ₹{original['Stop_Loss']:.2f} ({(original['Stop_Loss']/original['Entry_Price']-1)*100:.1f}%)")
        print(f"Target 1: ₹{original['Target1']:.2f} ({(original['Target1']/original['Entry_Price']-1)*100:.1f}%)")
        print(f"Target 2: ₹{original['Target2']:.2f} ({(original['Target2']/original['Entry_Price']-1)*100:.1f}%)")
        print(f"Volume Ratio: {original['Volume_Ratio']:.2f}")
        print(f"Momentum 5D: {original['Momentum_5D']:.2f}%")
        print(f"Pattern Score: {original['Score']:.1f}")
        print(f"ATR: {original['ATR']:.2f}")
        print(f"\nRESULT: H2 achieved in {row['days_to_h2']:.0f} days | Final P&L: {row['final_pnl_pct']:.2f}%")
        
        # Show description if available
        if 'Description' in original and pd.notna(original['Description']):
            print(f"\nSignal Description: {original['Description']}")

# Analyze patterns in successful low volume signals
print("\n\n=== PATTERN ANALYSIS OF SUCCESSFUL LOW VOLUME SIGNALS ===\n")

# Group by pattern score ranges
successful_low_volume['score_range'] = pd.cut(
    successful_low_volume['pattern_score'], 
    bins=[0, 60, 70, 80, 90, 100],
    labels=['50-60', '60-70', '70-80', '80-90', '90-100']
)

score_analysis = successful_low_volume.groupby('score_range').agg({
    'ticker': 'count',
    'final_pnl_pct': 'mean',
    'days_to_h2': 'mean'
}).round(2)

print("Pattern Score vs Success:")
print(score_analysis)

# Momentum analysis
print("\n\nMomentum Analysis:")
successful_low_volume['momentum_category'] = pd.cut(
    successful_low_volume['momentum_5d'],
    bins=[-100, -5, 0, 5, 10, 100],
    labels=['Strong Negative', 'Negative', 'Neutral', 'Positive', 'Strong Positive']
)

momentum_analysis = successful_low_volume.groupby('momentum_category').agg({
    'ticker': 'count',
    'final_pnl_pct': 'mean',
    'days_to_h2': 'mean'
}).round(2)

print(momentum_analysis)

# Time analysis
print("\n\nDays to H2 Distribution:")
print(f"Minimum: {successful_low_volume['days_to_h2'].min():.0f} days")
print(f"Maximum: {successful_low_volume['days_to_h2'].max():.0f} days") 
print(f"Average: {successful_low_volume['days_to_h2'].mean():.1f} days")
print(f"Median: {successful_low_volume['days_to_h2'].median():.0f} days")

# Recent examples (last 30 days)
recent_date = datetime.now().date() - pd.Timedelta(days=30)
recent_successes = successful_low_volume[successful_low_volume['entry_date'].dt.date >= recent_date]

print(f"\n\nRecent Successful Low Volume Signals (Last 30 Days): {len(recent_successes)} signals")
if len(recent_successes) > 0:
    print("\nMost Recent Examples:")
    print("-" * 80)
    print(f"{'Ticker':<12} {'Entry Date':<12} {'Vol Ratio':<10} {'Pattern':<10} {'Days to H2':<10} {'P&L %':<10}")
    print("-" * 80)
    
    for idx, row in recent_successes.head(10).iterrows():
        print(f"{row['ticker']:<12} {row['entry_date'].strftime('%Y-%m-%d'):<12} {row['volume_ratio']:<10.2f} "
              f"{row['pattern_score']:<10.1f} {row['days_to_h2']:<10.0f} {row['final_pnl_pct']:<10.1f}")