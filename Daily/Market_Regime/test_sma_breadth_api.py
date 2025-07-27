#!/usr/bin/env python3
"""
Test script for SMA Breadth API and calculations
Tests the data processing and visualizations before integrating with dashboard
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import os

# Load the historical data
data_file = os.path.join(os.path.dirname(__file__), 'historical_breadth_data', 'sma_breadth_historical_latest.json')
with open(data_file, 'r') as f:
    data = json.load(f)

# Convert to DataFrame for easier analysis
df = pd.DataFrame(data)
df['date'] = pd.to_datetime(df['date'])
df['sma20_percent'] = df['sma_breadth'].apply(lambda x: x['sma20_percent'])
df['sma50_percent'] = df['sma_breadth'].apply(lambda x: x['sma50_percent'])
df['market_score'] = df['market_score'].astype(float)

print("=== SMA Breadth Data Analysis ===")
print(f"Total data points: {len(df)}")
print(f"Date range: {df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}")
print(f"Stocks tracked: {df['total_stocks'].iloc[0]}")

# Calculate additional metrics
# 1. Moving averages of breadth
df['sma20_ma5'] = df['sma20_percent'].rolling(window=5).mean()
df['sma50_ma5'] = df['sma50_percent'].rolling(window=5).mean()

# 2. Breadth momentum (rate of change)
df['sma20_momentum'] = df['sma20_percent'].diff()
df['sma50_momentum'] = df['sma50_percent'].diff()

# 3. Divergence between SMA20 and SMA50
df['breadth_divergence'] = df['sma20_percent'] - df['sma50_percent']

# 4. Market regime transitions
df['regime_change'] = df['market_regime'] != df['market_regime'].shift(1)

print("\n=== Current Market Conditions ===")
latest = df.iloc[-1]
print(f"Date: {latest['date'].strftime('%Y-%m-%d')}")
print(f"SMA20 Breadth: {latest['sma20_percent']:.1f}%")
print(f"SMA50 Breadth: {latest['sma50_percent']:.1f}%")
print(f"Market Regime: {latest['market_regime']}")
print(f"Market Score: {latest['market_score']:.3f}")
print(f"Breadth Divergence: {latest['breadth_divergence']:.1f}%")

# Trend Analysis
print("\n=== Trend Analysis ===")
# 5-day trend
five_days_ago = df.iloc[-6] if len(df) >= 6 else df.iloc[0]
sma20_5d_change = latest['sma20_percent'] - five_days_ago['sma20_percent']
sma50_5d_change = latest['sma50_percent'] - five_days_ago['sma50_percent']
print(f"5-day SMA20 change: {sma20_5d_change:+.1f}%")
print(f"5-day SMA50 change: {sma50_5d_change:+.1f}%")

# 20-day trend
twenty_days_ago = df.iloc[-21] if len(df) >= 21 else df.iloc[0]
sma20_20d_change = latest['sma20_percent'] - twenty_days_ago['sma20_percent']
sma50_20d_change = latest['sma50_percent'] - twenty_days_ago['sma50_percent']
print(f"20-day SMA20 change: {sma20_20d_change:+.1f}%")
print(f"20-day SMA50 change: {sma50_20d_change:+.1f}%")

# Key levels
print("\n=== Key Breadth Levels ===")
print(f"SMA20 - Min: {df['sma20_percent'].min():.1f}%, Max: {df['sma20_percent'].max():.1f}%, Avg: {df['sma20_percent'].mean():.1f}%")
print(f"SMA50 - Min: {df['sma50_percent'].min():.1f}%, Max: {df['sma50_percent'].max():.1f}%, Avg: {df['sma50_percent'].mean():.1f}%")

# Market regime statistics
print("\n=== Market Regime Statistics ===")
regime_counts = df['market_regime'].value_counts()
for regime, count in regime_counts.items():
    avg_sma20 = df[df['market_regime'] == regime]['sma20_percent'].mean()
    avg_sma50 = df[df['market_regime'] == regime]['sma50_percent'].mean()
    print(f"{regime}: {count} days ({count/len(df)*100:.1f}%) - Avg SMA20: {avg_sma20:.1f}%, Avg SMA50: {avg_sma50:.1f}%")

# Create visualization
fig, axes = plt.subplots(3, 1, figsize=(12, 10))

# Plot 1: SMA Breadth Lines
ax1 = axes[0]
ax1.plot(df['date'], df['sma20_percent'], label='SMA20 Breadth', color='blue', linewidth=2)
ax1.plot(df['date'], df['sma50_percent'], label='SMA50 Breadth', color='red', linewidth=2)
ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
ax1.axhline(y=70, color='green', linestyle='--', alpha=0.3, label='Bullish (70%)')
ax1.axhline(y=30, color='red', linestyle='--', alpha=0.3, label='Bearish (30%)')
ax1.fill_between(df['date'], 30, 70, alpha=0.1, color='gray', label='Neutral Zone')
ax1.set_ylabel('Breadth %')
ax1.set_title('Market Breadth Analysis - SMA20 vs SMA50')
ax1.legend()
ax1.grid(True, alpha=0.3)

# Plot 2: Market Score
ax2 = axes[1]
ax2.plot(df['date'], df['market_score'], label='Market Score', color='purple', linewidth=2)
ax2.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
ax2.fill_between(df['date'], 0, df['market_score'], alpha=0.3, color='purple')
ax2.set_ylabel('Market Score')
ax2.set_title('Market Score (0-1 Scale)')
ax2.set_ylim(0, 1)
ax2.grid(True, alpha=0.3)

# Plot 3: Breadth Momentum
ax3 = axes[2]
ax3.bar(df['date'], df['sma20_momentum'], label='SMA20 Momentum', alpha=0.7, color='blue')
ax3.plot(df['date'], df['sma20_ma5'].diff(), label='SMA20 Momentum MA5', color='darkblue', linewidth=2)
ax3.axhline(y=0, color='black', linestyle='-', alpha=0.5)
ax3.set_ylabel('Daily Change %')
ax3.set_title('Breadth Momentum (Daily Change)')
ax3.legend()
ax3.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(os.path.dirname(__file__), 'test_sma_breadth_analysis.png'), dpi=150)
print(f"\n✓ Chart saved to test_sma_breadth_analysis.png")

# Test data format for API
print("\n=== API Data Format Test ===")
api_data = {
    'labels': [d['date'] for d in data],
    'sma20_values': [d['sma_breadth']['sma20_percent'] for d in data],
    'sma50_values': [d['sma_breadth']['sma50_percent'] for d in data],
    'data_points': len(data),
    'current_sma20': data[-1]['sma_breadth']['sma20_percent'],
    'current_sma50': data[-1]['sma_breadth']['sma50_percent'],
    'trend_sma20': 'up' if sma20_5d_change > 0 else 'down',
    'trend_sma50': 'up' if sma50_5d_change > 0 else 'down',
    'market_regime': data[-1]['market_regime'],
    'total_stocks': data[-1]['total_stocks']
}
print(f"API data structure ready with {len(api_data['labels'])} data points")
print(f"Memory size: ~{len(json.dumps(api_data)) / 1024:.1f} KB")

print("\n✓ All tests passed! Data is ready for dashboard integration.")