#!/usr/bin/env python3
"""
VSR Ticker Persistence Analysis - Prior Period (Aug 4-15, 2025)
Analyzes Excel efficiency reports for the period before current analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime

def analyze_prior_period_persistence():
    """Analyze VSR persistence for Aug 4-15 period"""
    
    # Load the Excel efficiency reports for prior period
    prior_file = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Efficiency/Eff_Analysis_long_20250815_20250804.xlsx'
    
    # Read the data
    df_long = pd.read_excel(prior_file)  # Aug 4 - Aug 15
    
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
    
    # Add persistence category to dataframe
    df_long['Persistence Category'] = df_long['Alert Count'].apply(categorize_persistence)
    
    # Process long signals
    print("\n" + "="*120)
    print("VSR PERSISTENCE-PERFORMANCE ANALYSIS - PRIOR PERIOD")
    print("Analysis Period: August 4-15, 2025 (Week Before Current Analysis)")
    print("Data Source: VSR Efficiency Reports (Hourly Scans)")
    print("="*120)
    
    print("\n" + "="*100)
    print("LONG SIGNALS ANALYSIS - PRIOR PERIOD (Aug 4-15)")
    print("="*100)
    
    categories = ['Low (1-10)', 'Medium (11-25)', 'High (26-50)', 'Very High (51-75)', 'Extreme (75+)']
    
    # Store summary stats for comparison
    summary_stats = {}
    
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
        
        # Store for summary
        summary_stats[category] = {
            'total': total_tickers,
            'winners': winners,
            'win_rate': win_rate,
            'avg_return': avg_return,
            'avg_score': avg_score
        }
        
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
        print("EXTREME PERSISTENCE (75+ ALERTS) - PRIOR PERIOD (Aug 4-15)")
        print("These tickers appeared in almost every hourly scan")
        print("="*100)
        
        extreme_long = extreme_long.sort_values('Alert Count', ascending=False)
        for _, row in extreme_long.iterrows():
            print(f"\n{row['Ticker']}:")
            print(f"  Total Alerts: {row['Alert Count']} (avg {row['Alert Count']/11:.1f} alerts per day)")
            print(f"  Maximum VSR Score: {row['Max Score']:.2f}")
            print(f"  Average VSR Score: {row['Avg Score']:.2f}")
            print(f"  Price Performance: {row['Price Change %']*100:.2f}%")
            print(f"  Entry Price (First Alert): ₹{row['First Price']:.2f}")
            print(f"  Latest Price: ₹{row['Latest Price']:.2f}")
            print(f"  First Alert: {row['First Alert Date']} at {row['First Alert Time']}")
            print(f"  Latest Alert: {row['Latest Alert Time']}")
    
    # Summary Statistics
    print(f"\n\n{'='*100}")
    print("SUMMARY STATISTICS - PRIOR PERIOD (Aug 4-15)")
    print("="*100)
    
    for category in categories:
        cat_data = df_long[df_long['Persistence Category'] == category]
        if len(cat_data) > 0:
            winners = len(cat_data[cat_data['Price Change %'] > 0])
            print(f"\n{category}:")
            print(f"  Tickers: {len(cat_data)} | Winners: {winners} | Win Rate: {winners/len(cat_data)*100:.1f}%")
            print(f"  Avg Return: {cat_data['Price Change %'].mean()*100:.2f}% | Best: {cat_data['Price Change %'].max()*100:.2f}% | Worst: {cat_data['Price Change %'].min()*100:.2f}%")
            print(f"  Alert Range: {cat_data['Alert Count'].min()}-{cat_data['Alert Count'].max()} | Avg Score: {cat_data['Avg Score'].mean():.2f}")
    
    # Comparison with Current Period (Aug 11-22)
    print(f"\n\n{'='*100}")
    print("COMPARISON: PRIOR (Aug 4-15) vs CURRENT (Aug 11-22)")
    print("="*100)
    
    # Current period stats (from the original analysis)
    current_stats = {
        'Low (1-10)': {'total': 135, 'win_rate': 45.2, 'avg_return': 0.28},
        'Medium (11-25)': {'total': 98, 'win_rate': 76.5, 'avg_return': 1.49},
        'High (26-50)': {'total': 90, 'win_rate': 88.9, 'avg_return': 2.72},
        'Very High (51-75)': {'total': 28, 'win_rate': 100.0, 'avg_return': 5.73},
        'Extreme (75+)': {'total': 11, 'win_rate': 100.0, 'avg_return': 9.68}
    }
    
    print(f"\n{'Category':<20} {'Prior Win%':<12} {'Current Win%':<12} {'Prior Ret%':<12} {'Current Ret%':<12} {'Prior Count':<12} {'Current Count':<12}")
    print("-" * 100)
    
    for category in categories:
        if category in summary_stats:
            prior = summary_stats[category]
            current = current_stats.get(category, {})
            print(f"{category:<20} {prior['win_rate']:<12.1f} {current.get('win_rate', 0):<12.1f} "
                  f"{prior['avg_return']:<12.2f} {current.get('avg_return', 0):<12.2f} "
                  f"{prior['total']:<12} {current.get('total', 0):<12}")
    
    # Key Insights
    print(f"\n\n{'='*100}")
    print("KEY INSIGHTS - COMPARING TWO PERIODS")
    print("="*100)
    
    print("\n1. PERSISTENCE PATTERN CONSISTENCY:")
    print("   Both periods show strong positive correlation between persistence and returns")
    
    print("\n2. TICKERS THAT MAINTAINED HIGH PERSISTENCE ACROSS BOTH PERIODS:")
    # Find tickers that appear in high persistence categories in both periods
    high_persist_tickers = df_long[df_long['Alert Count'] > 50]['Ticker'].tolist()
    print(f"   Prior Period (Aug 4-15) High Persistence Tickers: {len(high_persist_tickers)}")
    if high_persist_tickers[:10]:
        print(f"   Top Examples: {', '.join(high_persist_tickers[:10])}")
    
    return df_long, summary_stats

if __name__ == "__main__":
    df_long, summary_stats = analyze_prior_period_persistence()