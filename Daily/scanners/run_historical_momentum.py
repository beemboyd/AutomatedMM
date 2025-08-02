#!/usr/bin/env python3
"""
Run momentum scanner for past 14 days with historical data
"""

import os
import sys
from datetime import datetime, timedelta
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.scanners.momentum_scanner import MomentumScanner

def run_historical_scan(days=14):
    """Run momentum scanner for past N days"""
    print(f"Starting historical momentum scan for past {days} days...")
    
    # Create scanner instance
    scanner = MomentumScanner(user_name='Sai')
    
    # Store results
    historical_data = []
    
    # Run for each day
    for i in range(days, -1, -1):
        scan_date = datetime.now() - timedelta(days=i)
        
        # Skip weekends
        if scan_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            print(f"Skipping weekend: {scan_date.strftime('%Y-%m-%d %A')}")
            continue
        
        print(f"\nProcessing date: {scan_date.strftime('%Y-%m-%d %A')}")
        
        try:
            # Run scan for this date
            results = scanner.run_scan(scan_date)
            
            # Get counts
            daily_count = len(results.get('Daily', pd.DataFrame()))
            weekly_count = len(results.get('Weekly', pd.DataFrame()))
            
            # Store data
            historical_data.append({
                'Date': scan_date.strftime('%Y-%m-%d'),
                'Day': scan_date.strftime('%A'),
                'Daily_Count': daily_count,
                'Weekly_Count': weekly_count,
                'Total_Unique': daily_count + weekly_count  # This will be recalculated if we have overlap data
            })
            
            print(f"  Daily: {daily_count} tickers")
            print(f"  Weekly: {weekly_count} tickers")
            
        except Exception as e:
            print(f"  Error processing {scan_date.strftime('%Y-%m-%d')}: {e}")
            historical_data.append({
                'Date': scan_date.strftime('%Y-%m-%d'),
                'Day': scan_date.strftime('%A'),
                'Daily_Count': 0,
                'Weekly_Count': 0,
                'Total_Unique': 0
            })
    
    # Save historical summary
    summary_df = pd.DataFrame(historical_data)
    summary_file = os.path.join(scanner.momentum_dir, f'Historical_Momentum_Summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
    
    with pd.ExcelWriter(summary_file, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Historical_Summary', index=False)
        
        # Add formula reference sheet
        formula_data = pd.DataFrame({
            'Indicator': ['EMA_5', 'EMA_8', 'EMA_13', 'EMA_21', 'EMA_50', 'EMA_100', 
                         'WM (Weighted Momentum)', 'Slope', 'Criteria'],
            'Formula/Description': [
                'Exponential Moving Average (5 periods)',
                'Exponential Moving Average (8 periods)', 
                'Exponential Moving Average (13 periods)',
                'Exponential Moving Average (21 periods)',
                'Exponential Moving Average (50 periods)',
                'Exponential Moving Average (100 periods)',
                'WM = ((EMA5-EMA8) + (EMA8-EMA13) + (EMA13-EMA21) + (EMA21-EMA50)) / 4',
                'Linear regression slope over 8 periods as percentage',
                'Price > EMA_100 AND Slope > 0'
            ]
        })
        formula_data.to_excel(writer, sheet_name='Formula_Reference', index=False)
    
    print(f"\nHistorical summary saved to: {summary_file}")
    print("\nSummary:")
    print(summary_df.to_string(index=False))
    
    return summary_df


if __name__ == '__main__':
    # Run for past 14 days
    run_historical_scan(14)