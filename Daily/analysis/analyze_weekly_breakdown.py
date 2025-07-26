#!/usr/bin/env python
"""
Analyze weekly breakdown from the simple analysis data
"""

import pandas as pd
import json
from datetime import datetime, timedelta
import os

def analyze_weekly_breakdown():
    """Analyze the weekly breakdown from existing data"""
    
    # Load the latest simple analysis
    json_file = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports/latest_simple_analysis.json'
    
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Get ticker analysis data
    ticker_analysis = data['ticker_analysis']
    
    # Convert to DataFrame
    df = pd.DataFrame(ticker_analysis)
    df['first_signal_date'] = pd.to_datetime(df['first_signal_date'])
    
    # Get the date range
    end_date = df['first_signal_date'].max()
    start_date = end_date - timedelta(weeks=4)
    
    # Define weeks
    weeks = []
    for i in range(4):
        week_end = end_date - timedelta(weeks=i)
        week_start = week_end - timedelta(days=6)
        weeks.append({
            'week_num': 4 - i,
            'start': week_start,
            'end': week_end,
            'label': f"Week {4-i}"
        })
    
    print("="*60)
    print("WEEKLY BREAKDOWN OF LONG REVERSAL PERFORMANCE")
    print("="*60)
    print(f"\nAnalysis Period: {start_date.date()} to {end_date.date()}")
    print(f"Total Unique Tickers: {len(df)}")
    print(f"Overall Win Rate: {(df['grew'].sum() / len(df) * 100):.1f}%")
    print(f"Overall Average Return: {df['price_change_pct'].mean():.2f}%")
    
    # Analyze by week
    print("\n" + "="*60)
    print("PERFORMANCE BY SIGNAL WEEK")
    print("="*60)
    
    weekly_summary = []
    
    for week in weeks:
        # Filter tickers that were signaled in this week
        week_df = df[(df['first_signal_date'] >= week['start']) & 
                     (df['first_signal_date'] <= week['end'])]
        
        if len(week_df) > 0:
            winners = week_df['grew'].sum()
            total = len(week_df)
            win_rate = winners / total * 100
            avg_return = week_df['price_change_pct'].mean()
            
            # Find best and worst
            best_idx = week_df['price_change_pct'].idxmax()
            worst_idx = week_df['price_change_pct'].idxmin()
            best = week_df.loc[best_idx]
            worst = week_df.loc[worst_idx]
            
            weekly_summary.append({
                'Week': week['label'],
                'Period': f"{week['start'].strftime('%b %d')} - {week['end'].strftime('%b %d')}",
                'Tickers': total,
                'Winners': winners,
                'Losers': total - winners,
                'Win_Rate': win_rate,
                'Avg_Return': avg_return,
                'Best_Ticker': best['ticker'],
                'Best_Return': best['price_change_pct'],
                'Worst_Ticker': worst['ticker'],
                'Worst_Return': worst['price_change_pct']
            })
            
            print(f"\n{week['label']} ({week['start'].strftime('%b %d')} - {week['end'].strftime('%b %d')})")
            print(f"  Unique Tickers: {total}")
            print(f"  Winners: {winners} ({win_rate:.1f}%)")
            print(f"  Average Return: {avg_return:.2f}%")
            print(f"  Best: {best['ticker']} ({best['price_change_pct']:+.2f}%)")
            print(f"  Worst: {worst['ticker']} ({worst['price_change_pct']:+.2f}%)")
    
    # Create summary DataFrame
    summary_df = pd.DataFrame(weekly_summary)
    
    # Show trend
    print("\n" + "="*60)
    print("WEEKLY TREND ANALYSIS")
    print("="*60)
    
    for i, row in summary_df.iterrows():
        bar_length = int(row['Win_Rate'] / 2)  # Scale to fit
        bar = '█' * bar_length
        print(f"{row['Week']}: {bar} {row['Win_Rate']:.1f}%")
    
    # Save weekly breakdown
    output_file = '/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Weekly_Reports/weekly_breakdown_summary.xlsx'
    summary_df.to_excel(output_file, index=False)
    print(f"\n\nWeekly breakdown saved to: {output_file}")
    
    # Additional insights
    print("\n" + "="*60)
    print("KEY INSIGHTS")
    print("="*60)
    
    # Best and worst weeks
    best_week = summary_df.loc[summary_df['Win_Rate'].idxmax()]
    worst_week = summary_df.loc[summary_df['Win_Rate'].idxmin()]
    
    print(f"\nBest Week: {best_week['Week']} - {best_week['Win_Rate']:.1f}% win rate")
    print(f"Worst Week: {worst_week['Week']} - {worst_week['Win_Rate']:.1f}% win rate")
    
    # Trend analysis
    if len(summary_df) > 1:
        first_half_avg = summary_df.iloc[:2]['Win_Rate'].mean()
        second_half_avg = summary_df.iloc[2:]['Win_Rate'].mean()
        
        if second_half_avg > first_half_avg:
            print("\nTrend: Performance IMPROVED in recent weeks")
        else:
            print("\nTrend: Performance DECLINED in recent weeks")
        
        print(f"  First 2 weeks avg win rate: {first_half_avg:.1f}%")
        print(f"  Last 2 weeks avg win rate: {second_half_avg:.1f}%")

if __name__ == "__main__":
    analyze_weekly_breakdown()