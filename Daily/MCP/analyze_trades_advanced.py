#!/usr/bin/env python3
"""
Advanced analysis of trades - grouping transactions into complete trades
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Read the Excel file
df = pd.read_excel('/Users/maverick/PycharmProjects/India-TS/Daily/data/Transactions/06192025-07192025.xlsx', 
                   sheet_name='Equity', header=14)

# Clean and prepare data
df = df.drop('Unnamed: 0', axis=1, errors='ignore')
df['Trade Date'] = pd.to_datetime(df['Trade Date'])
df['Order Execution Time'] = pd.to_datetime(df['Order Execution Time'])

# Filter for last 3 weeks
three_weeks_ago = datetime.now() - timedelta(days=21)
df_recent = df[df['Trade Date'] >= three_weeks_ago].copy()

print(f'Analyzing transactions from last 3 weeks...')
print(f'Date range: {df_recent["Trade Date"].min().date()} to {df_recent["Trade Date"].max().date()}')
print(f'Total transactions: {len(df_recent)}')

# Group transactions by symbol and date to identify complete trades
complete_trades = []

# Process each symbol
for symbol in df_recent['Symbol'].unique():
    symbol_df = df_recent[df_recent['Symbol'] == symbol].sort_values('Order Execution Time')
    
    # Group by trade date
    for trade_date in symbol_df['Trade Date'].unique():
        day_trades = symbol_df[symbol_df['Trade Date'] == trade_date]
        
        # Separate buys and sells
        buys = day_trades[day_trades['Trade Type'] == 'buy']
        sells = day_trades[day_trades['Trade Type'] == 'sell']
        
        if not buys.empty and not sells.empty:
            # This is a complete trade (bought and sold same day)
            total_buy_qty = buys['Quantity'].sum()
            total_sell_qty = sells['Quantity'].sum()
            matched_qty = min(total_buy_qty, total_sell_qty)
            
            # Calculate weighted average prices
            avg_buy_price = (buys['Price'] * buys['Quantity']).sum() / buys['Quantity'].sum()
            avg_sell_price = (sells['Price'] * sells['Quantity']).sum() / sells['Quantity'].sum()
            
            # Calculate profit
            profit = (avg_sell_price - avg_buy_price) * matched_qty
            profit_pct = ((avg_sell_price - avg_buy_price) / avg_buy_price) * 100
            
            # Investment amount
            investment = avg_buy_price * matched_qty
            
            complete_trades.append({
                'Symbol': symbol,
                'Trade Date': trade_date,
                'Buy Price': avg_buy_price,
                'Sell Price': avg_sell_price,
                'Quantity': matched_qty,
                'Investment': investment,
                'Profit': profit,
                'Profit %': profit_pct,
                'Buy Transactions': len(buys),
                'Sell Transactions': len(sells),
                'First Buy Time': buys['Order Execution Time'].min(),
                'Last Sell Time': sells['Order Execution Time'].max(),
                'Trade Duration': (sells['Order Execution Time'].max() - buys['Order Execution Time'].min()).total_seconds() / 3600
            })

# Convert to DataFrame and sort by profit
trades_df = pd.DataFrame(complete_trades)
if not trades_df.empty:
    trades_df = trades_df.sort_values('Profit', ascending=False)
    
    print(f'\nFound {len(trades_df)} complete trades (bought and sold)')
    print('\n' + '=' * 100)
    print('TOP 15 MOST PROFITABLE TRADES (Last 3 Weeks)')
    print('=' * 100)
    
    for idx in range(min(15, len(trades_df))):
        row = trades_df.iloc[idx]
        print(f"\n{idx+1}. {row['Symbol']} - {row['Trade Date'].strftime('%Y-%m-%d')}")
        print(f"   Buy Price:  ₹{row['Buy Price']:,.2f} (avg of {row['Buy Transactions']} transactions)")
        print(f"   Sell Price: ₹{row['Sell Price']:,.2f} (avg of {row['Sell Transactions']} transactions)")
        print(f"   Quantity: {row['Quantity']:,}")
        print(f"   Investment: ₹{row['Investment']:,.2f}")
        print(f"   Profit: ₹{row['Profit']:,.2f} ({row['Profit %']:.2f}%)")
        print(f"   Trade Duration: {row['Trade Duration']:.1f} hours")
    
    # Summary statistics
    print('\n' + '=' * 100)
    print('SUMMARY STATISTICS')
    print('=' * 100)
    
    profitable = trades_df[trades_df['Profit'] > 0]
    losing = trades_df[trades_df['Profit'] < 0]
    
    print(f'Total Complete Trades: {len(trades_df)}')
    print(f'Profitable Trades: {len(profitable)} ({len(profitable)/len(trades_df)*100:.1f}%)')
    print(f'Losing Trades: {len(losing)} ({len(losing)/len(trades_df)*100:.1f}%)')
    print(f'\nTotal Investment: ₹{trades_df["Investment"].sum():,.2f}')
    print(f'Total Profit: ₹{trades_df["Profit"].sum():,.2f}')
    print(f'Overall Return: {(trades_df["Profit"].sum() / trades_df["Investment"].sum() * 100):.2f}%')
    print(f'\nAverage Profit per Trade: ₹{trades_df["Profit"].mean():,.2f}')
    print(f'Average Return per Trade: {trades_df["Profit %"].mean():.2f}%')
    
    # Best performing symbols
    symbol_summary = trades_df.groupby('Symbol').agg({
        'Profit': 'sum',
        'Investment': 'sum',
        'Trade Date': 'count'
    }).rename(columns={'Trade Date': 'Trade Count'})
    symbol_summary['Return %'] = (symbol_summary['Profit'] / symbol_summary['Investment'] * 100)
    symbol_summary = symbol_summary.sort_values('Profit', ascending=False)
    
    print('\n' + '=' * 100)
    print('TOP 10 SYMBOLS BY TOTAL PROFIT')
    print('=' * 100)
    print(f"{'Symbol':<15} {'Trades':<10} {'Total Profit':<20} {'Total Investment':<20} {'Return %':<10}")
    print('-' * 75)
    
    for symbol in symbol_summary.head(10).index:
        row = symbol_summary.loc[symbol]
        print(f"{symbol:<15} {int(row['Trade Count']):<10} ₹{row['Profit']:>17,.2f} ₹{row['Investment']:>17,.2f} {row['Return %']:>8.2f}%")
    
    # Analyze trading frequency
    trades_by_date = trades_df.groupby('Trade Date').size()
    print(f'\n\nMost Active Trading Day: {trades_by_date.idxmax().strftime("%Y-%m-%d")} with {trades_by_date.max()} trades')
    print(f'Average Trades per Day: {trades_by_date.mean():.1f}')
    
else:
    print('No complete trades found in the data')