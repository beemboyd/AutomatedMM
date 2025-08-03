#!/usr/bin/env python3
"""
Summary report for Brooks Higher Probability LONG Reversal analysis
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

def create_performance_charts():
    # Read the detailed results
    df = pd.read_excel('/Users/maverick/PycharmProjects/India-TS/ML/results/brooks_reversal_analysis_20250526_212145.xlsx')
    
    # Set up the plotting style
    plt.style.use('default')
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    # 1. Win Rate by Date
    date_summary = df.groupby('file_date').agg({
        'is_profitable': ['count', 'sum']
    }).round(2)
    date_summary.columns = ['Total_Trades', 'Profitable_Trades']
    date_summary['Win_Rate'] = (date_summary['Profitable_Trades'] / date_summary['Total_Trades'] * 100).round(2)
    
    axes[0,0].bar(date_summary.index, date_summary['Win_Rate'], color='skyblue', edgecolor='navy')
    axes[0,0].set_title('Win Rate by Date', fontsize=14, fontweight='bold')
    axes[0,0].set_ylabel('Win Rate (%)')
    axes[0,0].set_xlabel('File Date')
    axes[0,0].tick_params(axis='x', rotation=45)
    
    # Add value labels on bars
    for i, v in enumerate(date_summary['Win_Rate']):
        axes[0,0].text(i, v + 1, f'{v:.1f}%', ha='center', va='bottom')
    
    # 2. P&L Distribution
    axes[0,1].hist(df['pnl_percentage'], bins=30, color='lightcoral', alpha=0.7, edgecolor='black')
    axes[0,1].axvline(0, color='red', linestyle='--', linewidth=2, label='Break-even')
    axes[0,1].set_title('P&L Distribution', fontsize=14, fontweight='bold')
    axes[0,1].set_xlabel('P&L Percentage (%)')
    axes[0,1].set_ylabel('Frequency')
    axes[0,1].legend()
    
    # 3. Top 10 Performers
    top_performers = df.nlargest(10, 'pnl_percentage')
    axes[1,0].barh(range(len(top_performers)), top_performers['pnl_percentage'], color='green', alpha=0.7)
    axes[1,0].set_yticks(range(len(top_performers)))
    axes[1,0].set_yticklabels(top_performers['ticker'])
    axes[1,0].set_title('Top 10 Individual Performers', fontsize=14, fontweight='bold')
    axes[1,0].set_xlabel('P&L Percentage (%)')
    
    # 4. Average P&L by Ticker (for tickers with >1 trade)
    ticker_stats = df.groupby('ticker').agg({
        'pnl_percentage': 'mean',
        'is_profitable': 'count'
    }).round(2)
    ticker_stats.columns = ['Avg_PnL', 'Trade_Count']
    
    # Filter tickers with more than 1 trade
    frequent_tickers = ticker_stats[ticker_stats['Trade_Count'] > 1].nlargest(10, 'Avg_PnL')
    
    axes[1,1].barh(range(len(frequent_tickers)), frequent_tickers['Avg_PnL'], color='orange', alpha=0.7)
    axes[1,1].set_yticks(range(len(frequent_tickers)))
    axes[1,1].set_yticklabels([f"{ticker} ({int(row['Trade_Count'])})" for ticker, row in frequent_tickers.iterrows()])
    axes[1,1].set_title('Top 10 Tickers by Avg P&L\n(Multiple Trades)', fontsize=14, fontweight='bold')
    axes[1,1].set_xlabel('Average P&L Percentage (%)')
    axes[1,1].axvline(0, color='red', linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    plt.savefig('/Users/maverick/PycharmProjects/India-TS/ML/results/brooks_reversal_performance_charts.png', 
                dpi=300, bbox_inches='tight')
    plt.show()
    
    print("Performance charts saved to: /Users/maverick/PycharmProjects/India-TS/ML/results/brooks_reversal_performance_charts.png")

if __name__ == "__main__":
    create_performance_charts()