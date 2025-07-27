#!/usr/bin/env python3
"""
Simple Long Reversal and Market Breadth Correlation Analysis
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import matplotlib.pyplot as plt

# Load breadth data
breadth_file = '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/historical_breadth_data/sma_breadth_historical_latest.json'
with open(breadth_file, 'r') as f:
    breadth_data = json.load(f)

# Convert to DataFrame
breadth_df = pd.DataFrame(breadth_data)
breadth_df['date'] = pd.to_datetime(breadth_df['date'])
breadth_df['sma20_percent'] = breadth_df['sma_breadth'].apply(lambda x: x['sma20_percent'])
breadth_df['sma50_percent'] = breadth_df['sma_breadth'].apply(lambda x: x['sma50_percent'])

# Count Long Reversal files by date
reversal_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/results'
signal_counts = {}

for filename in os.listdir(reversal_dir):
    if 'Long_Reversal' in filename and filename.endswith('.xlsx'):
        try:
            parts = filename.replace('.xlsx', '').split('_')
            date_str = parts[3]
            date = pd.to_datetime(date_str, format='%Y%m%d')
            
            # Count signals for this date
            if date not in signal_counts:
                signal_counts[date] = 0
            signal_counts[date] += 1
        except:
            continue

# Create signal DataFrame
signal_df = pd.DataFrame(list(signal_counts.items()), columns=['date', 'signal_count'])
signal_df = signal_df.sort_values('date')

# Merge with breadth data
merged_df = signal_df.merge(breadth_df[['date', 'sma20_percent', 'sma50_percent', 'market_regime']], 
                            on='date', how='left')

print("=== Long Reversal Signal Frequency vs Market Breadth ===\n")
print(f"Total dates with signals: {len(merged_df)}")
print(f"Total signals: {merged_df['signal_count'].sum()}")
print(f"\nSignals per day by market regime:")
print(merged_df.groupby('market_regime')['signal_count'].agg(['mean', 'count']))

# Calculate correlation
if len(merged_df) > 3:
    corr_sma20 = merged_df['signal_count'].corr(merged_df['sma20_percent'])
    corr_sma50 = merged_df['signal_count'].corr(merged_df['sma50_percent'])
    
    print(f"\nCorrelation Analysis:")
    print(f"Signal Count vs SMA20 Breadth: {corr_sma20:.3f}")
    print(f"Signal Count vs SMA50 Breadth: {corr_sma50:.3f}")
    
    # Create visualization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Scatter plot 1: Signals vs SMA20
    ax1.scatter(merged_df['sma20_percent'], merged_df['signal_count'], alpha=0.7, s=100)
    ax1.set_xlabel('SMA20 Breadth %')
    ax1.set_ylabel('Number of Signals per Day')
    ax1.set_title(f'Long Reversal Signals vs SMA20 Breadth\nCorrelation: {corr_sma20:.3f}')
    ax1.grid(True, alpha=0.3)
    
    # Add trend line
    z = np.polyfit(merged_df['sma20_percent'].dropna(), merged_df['signal_count'], 1)
    p = np.poly1d(z)
    ax1.plot(sorted(merged_df['sma20_percent']), p(sorted(merged_df['sma20_percent'])), "r--", alpha=0.8)
    
    # Scatter plot 2: Signals vs SMA50
    ax2.scatter(merged_df['sma50_percent'], merged_df['signal_count'], alpha=0.7, s=100, color='orange')
    ax2.set_xlabel('SMA50 Breadth %')
    ax2.set_ylabel('Number of Signals per Day')
    ax2.set_title(f'Long Reversal Signals vs SMA50 Breadth\nCorrelation: {corr_sma50:.3f}')
    ax2.grid(True, alpha=0.3)
    
    # Add trend line
    z = np.polyfit(merged_df['sma50_percent'].dropna(), merged_df['signal_count'], 1)
    p = np.poly1d(z)
    ax2.plot(sorted(merged_df['sma50_percent']), p(sorted(merged_df['sma50_percent'])), "r--", alpha=0.8)
    
    plt.tight_layout()
    
    # Save plot
    output_file = f'/Users/maverick/PycharmProjects/India-TS/Daily/analysis/breadth_correlation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
    plt.savefig(output_file, dpi=150)
    print(f"\nVisualization saved to: {output_file}")
    plt.show()
    
    # Trading insights
    print("\n=== Trading Insights ===")
    
    # Breadth threshold analysis
    high_breadth = merged_df[merged_df['sma20_percent'] > 60]
    low_breadth = merged_df[merged_df['sma20_percent'] < 40]
    
    if len(high_breadth) > 0 and len(low_breadth) > 0:
        print(f"\nHigh Breadth (>60%): Avg {high_breadth['signal_count'].mean():.1f} signals/day")
        print(f"Low Breadth (<40%): Avg {low_breadth['signal_count'].mean():.1f} signals/day")
    
    # Best breadth range for signals
    if len(merged_df) > 10:
        merged_df['breadth_bin'] = pd.cut(merged_df['sma20_percent'], bins=5)
        bin_analysis = merged_df.groupby('breadth_bin')['signal_count'].agg(['mean', 'count'])
        print(f"\nSignal frequency by breadth range:")
        print(bin_analysis)
    
else:
    print("\nNot enough data points for correlation analysis")

print("\n✓ Analysis complete!")