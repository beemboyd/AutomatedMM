#!/usr/bin/env python
"""
Analysis of Brooks Higher Probability Reversal Strategy Backtest Results.

This script analyzes the 1-year backtest results to identify optimal market conditions
where the Brooks strategy performed well.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

def analyze_backtest_results(excel_file):
    """Analyze the backtest results from Excel file"""
    
    print(f"\n=== Brooks Higher Probability Reversal Strategy - 1 Year Backtest Analysis ===")
    print(f"Analyzing: {excel_file}")
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Read the Excel file
        xls = pd.ExcelFile(excel_file)
        
        # Print available sheets
        print(f"\nAvailable sheets: {xls.sheet_names}")
        
        # Read trades data
        if 'Trades' in xls.sheet_names:
            trades_df = pd.read_excel(excel_file, sheet_name='Trades')
            print(f"\n=== TRADES ANALYSIS ===")
            print(f"Total Trades: {len(trades_df)}")
            
            if not trades_df.empty:
                # Convert dates
                trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
                trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
                
                # Calculate holding period
                trades_df['holding_days'] = (trades_df['exit_time'] - trades_df['entry_time']).dt.days
                
                # Basic statistics
                winning_trades = trades_df[trades_df['profit_loss'] > 0]
                losing_trades = trades_df[trades_df['profit_loss'] <= 0]
                
                win_rate = len(winning_trades) / len(trades_df) * 100
                avg_win = winning_trades['profit_loss'].mean() if len(winning_trades) > 0 else 0
                avg_loss = losing_trades['profit_loss'].mean() if len(losing_trades) > 0 else 0
                
                print(f"Win Rate: {win_rate:.2f}%")
                print(f"Average Winning Trade: ${avg_win:.2f}")
                print(f"Average Losing Trade: ${avg_loss:.2f}")
                print(f"Average Holding Period: {trades_df['holding_days'].mean():.1f} days")
                
                # Profit factor
                gross_profit = winning_trades['profit_loss'].sum()
                gross_loss = abs(losing_trades['profit_loss'].sum())
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                print(f"Profit Factor: {profit_factor:.2f}")
                
                # Monthly analysis
                trades_df['entry_month'] = trades_df['entry_time'].dt.to_period('M')
                monthly_stats = trades_df.groupby('entry_month').agg({
                    'profit_loss': ['count', 'sum', 'mean'],
                    'ticker': 'nunique'
                }).round(2)
                
                print(f"\n=== MONTHLY PERFORMANCE ===")
                monthly_stats.columns = ['Trade_Count', 'Total_PnL', 'Avg_PnL', 'Unique_Tickers']
                monthly_stats['Win_Rate'] = trades_df.groupby('entry_month').apply(
                    lambda x: (x['profit_loss'] > 0).sum() / len(x) * 100
                ).round(2)
                
                print(monthly_stats)
                
                # Exit reason analysis
                if 'exit_reason' in trades_df.columns:
                    print(f"\n=== EXIT REASON ANALYSIS ===")
                    exit_analysis = trades_df.groupby('exit_reason').agg({
                        'profit_loss': ['count', 'mean', 'sum']
                    }).round(2)
                    exit_analysis.columns = ['Count', 'Avg_PnL', 'Total_PnL']
                    exit_analysis['Win_Rate'] = trades_df.groupby('exit_reason').apply(
                        lambda x: (x['profit_loss'] > 0).sum() / len(x) * 100
                    ).round(2)
                    print(exit_analysis)
                
                # Top performing tickers
                print(f"\n=== TOP PERFORMING TICKERS ===")
                ticker_perf = trades_df.groupby('ticker').agg({
                    'profit_loss': ['count', 'sum', 'mean']
                }).round(2)
                ticker_perf.columns = ['Trade_Count', 'Total_PnL', 'Avg_PnL']
                ticker_perf['Win_Rate'] = trades_df.groupby('ticker').apply(
                    lambda x: (x['profit_loss'] > 0).sum() / len(x) * 100
                ).round(2)
                
                # Show top 10 by total PnL
                top_tickers = ticker_perf.sort_values('Total_PnL', ascending=False).head(10)
                print("Top 10 Tickers by Total P&L:")
                print(top_tickers)
                
                # Worst performing tickers
                worst_tickers = ticker_perf.sort_values('Total_PnL', ascending=True).head(5)
                print("\nWorst 5 Tickers by Total P&L:")
                print(worst_tickers)
                
        # Read metrics if available
        if 'Metrics' in xls.sheet_names:
            metrics_df = pd.read_excel(excel_file, sheet_name='Metrics')
            print(f"\n=== PERFORMANCE METRICS ===")
            print(metrics_df.to_string(index=False))
        
        # Read equity curve if available
        if 'Equity_Curve' in xls.sheet_names:
            equity_df = pd.read_excel(excel_file, sheet_name='Equity_Curve')
            print(f"\n=== EQUITY CURVE SUMMARY ===")
            print(f"Starting Equity: ${equity_df.iloc[0]['equity']:.2f}")
            print(f"Ending Equity: ${equity_df.iloc[-1]['equity']:.2f}")
            print(f"Total Return: {(equity_df.iloc[-1]['equity'] / equity_df.iloc[0]['equity'] - 1) * 100:.2f}%")
            
            # Calculate max drawdown
            equity_df['peak'] = equity_df['equity'].cummax()
            equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
            max_drawdown = equity_df['drawdown'].min()
            print(f"Maximum Drawdown: {max_drawdown:.2f}%")
            
        print(f"\n=== MARKET CONDITIONS ANALYSIS ===")
        if not trades_df.empty:
            # Analyze when trades were most successful
            trades_df['quarter'] = trades_df['entry_time'].dt.quarter
            trades_df['year'] = trades_df['entry_time'].dt.year
            
            # Quarterly analysis
            quarterly_stats = trades_df.groupby(['year', 'quarter']).agg({
                'profit_loss': ['count', 'sum', 'mean']
            }).round(2)
            quarterly_stats.columns = ['Trade_Count', 'Total_PnL', 'Avg_PnL']
            quarterly_stats['Win_Rate'] = trades_df.groupby(['year', 'quarter']).apply(
                lambda x: (x['profit_loss'] > 0).sum() / len(x) * 100
            ).round(2)
            
            print("Quarterly Performance:")
            print(quarterly_stats)
            
            # Best performing periods
            best_quarters = quarterly_stats.sort_values('Total_PnL', ascending=False).head(3)
            print(f"\nBest Performing Quarters:")
            print(best_quarters)
            
        print(f"\n=== STRATEGY INSIGHTS ===")
        print("The Brooks Higher Probability Reversal strategy showed:")
        print(f"• {win_rate:.1f}% win rate over 1 year")
        print(f"• {len(trades_df)} total trades generated")
        print(f"• Average trade duration: {trades_df['holding_days'].mean():.1f} days")
        print(f"• Profit factor: {profit_factor:.2f}")
        
        if profit_factor > 1.5:
            print("✓ Strategy shows positive profit factor indicating profitability")
        elif profit_factor > 1.0:
            print("~ Strategy is marginally profitable")
        else:
            print("✗ Strategy shows losses over the backtest period")
            
        if win_rate > 55:
            print("✓ Win rate above 55% indicates good signal quality")
        elif win_rate > 45:
            print("~ Win rate is acceptable but could be improved")
        else:
            print("✗ Win rate below 45% suggests signal quality issues")
            
    except Exception as e:
        print(f"Error analyzing file: {e}")
        return False
    
    return True

def main():
    """Main function"""
    
    # Find the most recent Brooks backtest results
    import glob
    results_files = glob.glob("./results/brooks_day_*.xlsx")
    
    if not results_files:
        print("No Brooks backtest results found in ./results/")
        return 1
    
    # Get the most recent file
    latest_file = max(results_files, key=os.path.getctime)
    
    # Analyze the results
    success = analyze_backtest_results(latest_file)
    
    if success:
        print(f"\n=== RECOMMENDATIONS ===")
        print("Based on this 1-year backtest analysis:")
        print("1. Review the monthly and quarterly performance to identify seasonal patterns")
        print("2. Focus on the top-performing tickers for future strategy refinement")
        print("3. Analyze exit reasons to optimize stop loss and take profit levels")
        print("4. Consider market conditions during best performing periods")
        print("5. Use this data to refine entry criteria and risk management")
        
        print(f"\nDetailed results saved in: {latest_file}")
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())