#!/usr/bin/env python
"""
Quick Market Summary - Analyze recent StrategyB reports for CHoCH signals
"""

import os
import glob
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

def analyze_recent_market():
    """Quick analysis of recent market conditions"""
    base_dir = "/Users/maverick/PycharmProjects/India-TS/Daily"
    results_dir = os.path.join(base_dir, "results")
    
    # Load last 2 days of reports
    cutoff = datetime.now() - timedelta(days=2)
    pattern = os.path.join(results_dir, "StrategyB_Report_*.xlsx")
    files = sorted(glob.glob(pattern))[-10:]  # Last 10 files
    
    momentum_by_hour = []
    direction_counts = {'LONG': 0, 'SHORT': 0}
    
    for file in files:
        try:
            date_str = os.path.basename(file).replace("StrategyB_Report_", "").replace(".xlsx", "")
            file_date = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
            
            if file_date < cutoff:
                continue
                
            df = pd.read_excel(file)
            
            # Clean momentum data
            if 'Momentum_5D' in df.columns:
                df['Momentum_5D'] = pd.to_numeric(df['Momentum_5D'], errors='coerce').fillna(0)
                avg_momentum = df['Momentum_5D'].mean()
                momentum_by_hour.append({
                    'datetime': file_date,
                    'hour': file_date.hour,
                    'avg_momentum': avg_momentum,
                    'ticker_count': len(df)
                })
            
            # Count directions
            if 'Direction' in df.columns:
                direction_counts['LONG'] += (df['Direction'] == 'LONG').sum()
                direction_counts['SHORT'] += (df['Direction'] == 'SHORT').sum()
                
        except Exception as e:
            continue
    
    # Analyze results
    print("\n" + "="*60)
    print("QUICK MARKET SUMMARY - Last 2 Days")
    print("="*60)
    
    if momentum_by_hour:
        momentum_df = pd.DataFrame(momentum_by_hour)
        
        print(f"\n📊 MOMENTUM ANALYSIS")
        print(f"Average Momentum: {momentum_df['avg_momentum'].mean():.2f}%")
        print(f"Latest Momentum: {momentum_df['avg_momentum'].iloc[-1]:.2f}%")
        print(f"Momentum Trend: {'↑ Improving' if momentum_df['avg_momentum'].iloc[-1] > momentum_df['avg_momentum'].mean() else '↓ Weakening'}")
        
        print(f"\n📈 SIGNAL DISTRIBUTION")
        total_signals = direction_counts['LONG'] + direction_counts['SHORT']
        if total_signals > 0:
            long_pct = (direction_counts['LONG'] / total_signals) * 100
            print(f"Long Signals: {direction_counts['LONG']} ({long_pct:.1f}%)")
            print(f"Short Signals: {direction_counts['SHORT']} ({100-long_pct:.1f}%)")
            print(f"Long/Short Ratio: {direction_counts['LONG']/max(direction_counts['SHORT'], 1):.2f}")
        
        print(f"\n🎯 MARKET CHARACTER")
        if momentum_df['avg_momentum'].mean() > 5 and long_pct > 70:
            print("Strong Bullish - Momentum high, Long bias dominant")
        elif momentum_df['avg_momentum'].mean() > 0 and long_pct > 50:
            print("Bullish - Positive momentum, More longs than shorts")
        elif momentum_df['avg_momentum'].mean() < -5 and long_pct < 30:
            print("Strong Bearish - Negative momentum, Short bias dominant")
        elif momentum_df['avg_momentum'].mean() < 0 and long_pct < 50:
            print("Bearish - Negative momentum, More shorts than longs")
        else:
            print("Neutral/Transitioning - Mixed signals")
            
        # Check for CHoCH signals
        print(f"\n⚠️  CHOCH SIGNALS")
        choch_signals = []
        
        # Check momentum divergence
        recent_avg = momentum_df['avg_momentum'].iloc[-3:].mean() if len(momentum_df) >= 3 else momentum_df['avg_momentum'].mean()
        overall_avg = momentum_df['avg_momentum'].mean()
        
        if recent_avg < overall_avg - 3:
            choch_signals.append("Momentum deteriorating rapidly")
        if long_pct < 40 and momentum_df['avg_momentum'].mean() < 0:
            choch_signals.append("Bearish pattern dominance with negative momentum")
        if momentum_df['ticker_count'].iloc[-1] < momentum_df['ticker_count'].mean() * 0.7:
            choch_signals.append("Fewer opportunities (market breadth narrowing)")
            
        if choch_signals:
            for signal in choch_signals:
                print(f"  ⚠️  {signal}")
        else:
            print("  ✅ No significant character change detected")
            
    else:
        print("No recent data available")

if __name__ == "__main__":
    analyze_recent_market()