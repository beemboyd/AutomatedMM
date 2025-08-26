#!/usr/bin/env python3
"""
VSR Ticker Persistence Analysis - Detailed Breakdown
Analyzes Excel efficiency reports to provide ticker-level details by persistence category
"""

import pandas as pd
import numpy as np
from datetime import datetime

def analyze_ticker_persistence():
    """Analyze VSR persistence and provide detailed ticker breakdown"""
    
    # Load the Excel efficiency reports
    long_file = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Efficiency/Eff_Analysis_long_20250822_20250811.xlsx'
    short_file = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Efficiency/Eff_Analysis_short_20250822_20250811.xlsx'
    
    # Read the data
    df_long = pd.read_excel(long_file)
    df_short = pd.read_excel(short_file)
    
    # Define persistence categories based on alert count
    def categorize_persistence(alert_count):
        if 1 <= alert_count <= 10:
            return 'Low (1-10)'
        elif 11 <= alert_count <= 25:
            return 'Medium (11-25)'
        elif 26 <= alert_count <= 50:
            return 'High (26-50)'
        elif 51 <= alert_count <= 75:
            return 'Very High (51-75)'
        elif alert_count > 75:
            return 'Extreme (75+)'
        else:
            return 'Unknown'
    
    # Add persistence category to dataframes
    df_long['Persistence Category'] = df_long['Alert Count'].apply(categorize_persistence)
    df_short['Persistence Category'] = df_short['Alert Count'].apply(categorize_persistence)
    
    # Process long signals
    print("\n" + "="*120)
    print("VSR PERSISTENCE-PERFORMANCE DETAILED TICKER ANALYSIS")
    print("Analysis Period: August 11-22, 2025")
    print("Data Source: VSR Efficiency Reports (Hourly Scans)")
    print("="*120)
    
    print("\n" + "="*100)
    print("LONG SIGNALS ANALYSIS")
    print("="*100)
    
    categories = ['Low (1-10)', 'Medium (11-25)', 'High (26-50)', 'Very High (51-75)', 'Extreme (75+)']
    
    for category in categories:
        cat_data = df_long[df_long['Persistence Category'] == category].copy()
        
        if len(cat_data) == 0:
            continue
            
        # Sort by price change for better visibility
        cat_data = cat_data.sort_values('Price Change %', ascending=False)
        
        # Calculate statistics
        total_tickers = len(cat_data)
        winners = len(cat_data[cat_data['Price Change %'] > 0])
        win_rate = (winners / total_tickers * 100) if total_tickers > 0 else 0
        avg_return = cat_data['Price Change %'].mean() * 100
        avg_score = cat_data['Avg Score'].mean()
        
        print(f"\n{'='*80}")
        print(f"{category.upper()} PERSISTENCE CATEGORY")
        print(f"Total Tickers: {total_tickers}")
        print(f"Winners: {winners} | Losers: {total_tickers - winners}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Average Return: {avg_return:.2f}%")
        print(f"Average VSR Score: {avg_score:.2f}")
        print(f"{'='*80}")
        
        # Table headers
        print(f"\n{'Ticker':<12} {'Alerts':<8} {'Max Score':<10} {'Avg Score':<10} {'Return %':<12} {'First Date':<12} {'First Price':<12} {'Latest Price':<12}")
        print("-" * 110)
        
        # Show all tickers for categories with less than 20, otherwise top 15 and bottom 5
        if len(cat_data) <= 20:
            for _, row in cat_data.iterrows():
                print(f"{row['Ticker']:<12} {row['Alert Count']:<8} {row['Max Score']:<10.2f} {row['Avg Score']:<10.2f} "
                      f"{row['Price Change %']*100:<12.2f}% {str(row['First Alert Date'])[:10]:<12} "
                      f"{row['First Price']:<12.2f} {row['Latest Price']:<12.2f}")
        else:
            # Top 15 performers
            print("\nTop 15 Performers:")
            for _, row in cat_data.head(15).iterrows():
                print(f"{row['Ticker']:<12} {row['Alert Count']:<8} {row['Max Score']:<10.2f} {row['Avg Score']:<10.2f} "
                      f"{row['Price Change %']*100:<12.2f}% {str(row['First Alert Date'])[:10]:<12} "
                      f"{row['First Price']:<12.2f} {row['Latest Price']:<12.2f}")
            
            print(f"\n... {len(cat_data) - 20} more tickers ...")
            
            # Bottom 5 performers
            print("\nBottom 5 Performers:")
            for _, row in cat_data.tail(5).iterrows():
                print(f"{row['Ticker']:<12} {row['Alert Count']:<8} {row['Max Score']:<10.2f} {row['Avg Score']:<10.2f} "
                      f"{row['Price Change %']*100:<12.2f}% {str(row['First Alert Date'])[:10]:<12} "
                      f"{row['First Price']:<12.2f} {row['Latest Price']:<12.2f}")
    
    # Special Analysis for Extreme Persistence
    extreme_long = df_long[df_long['Persistence Category'] == 'Extreme (75+)'].copy()
    if len(extreme_long) > 0:
        print(f"\n\n{'='*100}")
        print("EXTREME PERSISTENCE (75+ ALERTS) - SPECIAL FOCUS")
        print("These tickers appeared in almost every hourly scan (8+ times per day)")
        print("="*100)
        
        extreme_long = extreme_long.sort_values('Alert Count', ascending=False)
        for _, row in extreme_long.iterrows():
            print(f"\n{row['Ticker']}:")
            print(f"  Total Alerts: {row['Alert Count']} (avg {row['Alert Count']/10:.1f} alerts per day)")
            print(f"  Maximum VSR Score: {row['Max Score']:.2f}")
            print(f"  Average VSR Score: {row['Avg Score']:.2f}")
            print(f"  Price Performance: {row['Price Change %']*100:.2f}%")
            print(f"  Entry Price (First Alert): ₹{row['First Price']:.2f}")
            print(f"  Latest Price: ₹{row['Latest Price']:.2f}")
            print(f"  First Alert: {row['First Alert Date']} at {row['First Alert Time']}")
            print(f"  Latest Alert: {row['Latest Alert Time']}")
    
    # Summary Statistics
    print(f"\n\n{'='*100}")
    print("SUMMARY STATISTICS - LONG SIGNALS")
    print("="*100)
    
    for category in categories:
        cat_data = df_long[df_long['Persistence Category'] == category]
        if len(cat_data) > 0:
            winners = len(cat_data[cat_data['Price Change %'] > 0])
            print(f"\n{category}:")
            print(f"  Tickers: {len(cat_data)} | Winners: {winners} | Win Rate: {winners/len(cat_data)*100:.1f}%")
            print(f"  Avg Return: {cat_data['Price Change %'].mean()*100:.2f}% | Best: {cat_data['Price Change %'].max()*100:.2f}% | Worst: {cat_data['Price Change %'].min()*100:.2f}%")
            print(f"  Alert Range: {cat_data['Alert Count'].min()}-{cat_data['Alert Count'].max()} | Avg Score: {cat_data['Avg Score'].mean():.2f}")
    
    return df_long, df_short

if __name__ == "__main__":
    df_long, df_short = analyze_ticker_persistence()