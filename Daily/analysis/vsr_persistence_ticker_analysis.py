#!/usr/bin/env python3
"""
VSR Persistence-Performance Ticker Level Analysis
Provides detailed breakdown of tickers by persistence categories
"""

import pandas as pd
import json
import os
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict

def analyze_vsr_persistence_tickers():
    # Define the persistence categories
    persistence_categories = {
        'Low (1-10)': (1, 10),
        'Medium (11-25)': (11, 25), 
        'High (26-50)': (26, 50),
        'Very High (51-75)': (51, 75),
        'Extreme (75+)': (75, float('inf'))
    }

    # Load VSR efficiency data
    efficiency_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Efficiency'
    vsr_files = [f for f in os.listdir(efficiency_dir) if f.startswith('VSR_Efficiency_Report_')]

    # Aggregate data across all dates
    ticker_data = defaultdict(lambda: {
        'alert_count': 0,
        'total_score': 0,
        'price_changes': [],
        'dates': [],
        'entries': []
    })

    for file in vsr_files:
        file_path = os.path.join(efficiency_dir, file)
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            # Process long signals
            for ticker, info in data.get('long_signals', {}).items():
                ticker_data[ticker]['alert_count'] += info.get('alert_count', 0)
                ticker_data[ticker]['total_score'] += info.get('total_score', 0)
                
                if 'price_change' in info and info['price_change'] is not None:
                    ticker_data[ticker]['price_changes'].append(info['price_change'])
                
                ticker_data[ticker]['dates'].append(data.get('date', file.replace('VSR_Efficiency_Report_', '').replace('.json', '')))
                ticker_data[ticker]['entries'].append({
                    'date': data.get('date'),
                    'alert_count': info.get('alert_count', 0),
                    'avg_score': info.get('avg_score', 0),
                    'price_change': info.get('price_change', 0)
                })
        except Exception as e:
            print(f"Error processing {file}: {e}")
            continue

    # Categorize tickers by persistence level
    categorized_tickers = {}
    for category, (min_alerts, max_alerts) in persistence_categories.items():
        categorized_tickers[category] = []
        
        for ticker, data in ticker_data.items():
            if min_alerts <= data['alert_count'] <= max_alerts:
                avg_return = np.mean(data['price_changes']) if data['price_changes'] else 0
                win_rate = sum(1 for p in data['price_changes'] if p > 0) / len(data['price_changes']) * 100 if data['price_changes'] else 0
                
                categorized_tickers[category].append({
                    'ticker': ticker,
                    'alert_count': data['alert_count'],
                    'avg_score': data['total_score'] / data['alert_count'] if data['alert_count'] > 0 else 0,
                    'avg_return': avg_return,
                    'win_rate': win_rate,
                    'trade_count': len(data['price_changes']),
                    'best_return': max(data['price_changes']) if data['price_changes'] else 0,
                    'worst_return': min(data['price_changes']) if data['price_changes'] else 0,
                    'dates_active': len(set(data['dates']))
                })
        
        # Sort by average return
        categorized_tickers[category] = sorted(
            categorized_tickers[category], 
            key=lambda x: x['avg_return'], 
            reverse=True
        )

    # Print detailed breakdown
    print("\n" + "="*100)
    print("VSR PERSISTENCE-PERFORMANCE DETAILED TICKER ANALYSIS")
    print("Analysis Period: August 11-22, 2025 (Hourly Signals)")
    print("="*100)

    for category in ['Low (1-10)', 'Medium (11-25)', 'High (26-50)', 'Very High (51-75)', 'Extreme (75+)']:
        tickers = categorized_tickers[category]
        
        if not tickers:
            continue
        
        print(f"\n\n{'='*80}")
        print(f"{category.upper()} PERSISTENCE CATEGORY")
        print(f"Total Tickers: {len(tickers)}")
        
        # Calculate category statistics
        cat_win_rate = np.mean([t['win_rate'] for t in tickers])
        cat_avg_return = np.mean([t['avg_return'] for t in tickers])
        
        print(f"Category Win Rate: {cat_win_rate:.1f}%")
        print(f"Category Avg Return: {cat_avg_return:.2f}%")
        print(f"{'='*80}")
        
        # Print top performers
        print(f"\nTop 10 Performers:")
        print(f"{'Ticker':<12} {'Alerts':<8} {'Avg Score':<10} {'Avg Return':<12} {'Win Rate':<10} {'Best':<10} {'Worst':<10} {'Days Active':<12}")
        print("-" * 100)
        
        for ticker in tickers[:10]:
            print(f"{ticker['ticker']:<12} {ticker['alert_count']:<8} {ticker['avg_score']:<10.2f} "
                  f"{ticker['avg_return']:<12.2f}% {ticker['win_rate']:<10.1f}% "
                  f"{ticker['best_return']:<10.2f}% {ticker['worst_return']:<10.2f}% {ticker['dates_active']:<12}")
        
        if len(tickers) > 10:
            print(f"\n... and {len(tickers) - 10} more tickers in this category")
        
        # Show bottom performers if any
        if len(tickers) > 5:
            print(f"\nBottom 5 Performers:")
            print(f"{'Ticker':<12} {'Alerts':<8} {'Avg Score':<10} {'Avg Return':<12} {'Win Rate':<10} {'Best':<10} {'Worst':<10} {'Days Active':<12}")
            print("-" * 100)
            
            for ticker in tickers[-5:]:
                print(f"{ticker['ticker']:<12} {ticker['alert_count']:<8} {ticker['avg_score']:<10.2f} "
                      f"{ticker['avg_return']:<12.2f}% {ticker['win_rate']:<10.1f}% "
                      f"{ticker['best_return']:<10.2f}% {ticker['worst_return']:<10.2f}% {ticker['dates_active']:<12}")

    # Special focus on Extreme persistence tickers
    print(f"\n\n{'='*100}")
    print("EXTREME PERSISTENCE (75+ ALERTS) - DETAILED ANALYSIS")
    print("These tickers appeared in almost every hourly scan")
    print("="*100)

    extreme_tickers = categorized_tickers['Extreme (75+)']
    if extreme_tickers:
        for ticker in extreme_tickers:
            print(f"\n{ticker['ticker']}:")
            print(f"  Total Alerts: {ticker['alert_count']} (avg {ticker['alert_count']/10:.1f} per day)")
            print(f"  Average VSR Score: {ticker['avg_score']:.2f}")
            print(f"  Average Return: {ticker['avg_return']:.2f}%")
            print(f"  Win Rate: {ticker['win_rate']:.1f}%")
            print(f"  Best Day: {ticker['best_return']:.2f}%")
            print(f"  Worst Day: {ticker['worst_return']:.2f}%")
            print(f"  Days Active: {ticker['dates_active']} out of 10")

    return categorized_tickers

if __name__ == "__main__":
    analyze_vsr_persistence_tickers()