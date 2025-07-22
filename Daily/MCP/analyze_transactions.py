#!/usr/bin/env python3
"""
Analyze profitable transactions from the Excel file
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Read the Excel file with correct header
df = pd.read_excel('/Users/maverick/PycharmProjects/India-TS/Daily/data/Transactions/06192025-07192025.xlsx', 
                   sheet_name='Equity', header=14)

# Clean up the dataframe
df = df.drop('Unnamed: 0', axis=1, errors='ignore')

# Convert Trade Date to datetime
df['Trade Date'] = pd.to_datetime(df['Trade Date'])

# Filter for last 3 weeks (21 days)
three_weeks_ago = datetime.now() - timedelta(days=21)
df_recent = df[df['Trade Date'] >= three_weeks_ago]

print(f'Total transactions: {len(df)}')
print(f'Transactions in last 3 weeks: {len(df_recent)}')
date_min = df_recent['Trade Date'].min()
date_max = df_recent['Trade Date'].max()
print(f'Date range: {date_min} to {date_max}')

# Check trade types
print('\nTrade type distribution:')
print(df_recent['Trade Type'].value_counts())

# Group by symbol to match buys and sells
print('\nAnalyzing profitable transactions...')

# Calculate P&L by matching buy and sell trades
symbol_trades = {}
for _, row in df_recent.iterrows():
    symbol = row['Symbol']
    if symbol not in symbol_trades:
        symbol_trades[symbol] = {'buys': [], 'sells': []}
    
    if row['Trade Type'] == 'buy':
        symbol_trades[symbol]['buys'].append(row)
    else:
        symbol_trades[symbol]['sells'].append(row)

# Calculate profits for symbols with both buy and sell
profitable_trades = []
for symbol, trades in symbol_trades.items():
    if trades['buys'] and trades['sells']:
        # Simple FIFO matching
        buy_queue = sorted(trades['buys'], key=lambda x: x['Trade Date'])
        sell_queue = sorted(trades['sells'], key=lambda x: x['Trade Date'])
        
        for sell in sell_queue:
            if buy_queue:
                buy = buy_queue[0]
                quantity = min(buy['Quantity'], sell['Quantity'])
                profit = (sell['Price'] - buy['Price']) * quantity
                profit_pct = ((sell['Price'] - buy['Price']) / buy['Price']) * 100
                
                profitable_trades.append({
                    'Symbol': symbol,
                    'Buy Date': buy['Trade Date'],
                    'Sell Date': sell['Trade Date'],
                    'Buy Price': buy['Price'],
                    'Sell Price': sell['Price'],
                    'Quantity': quantity,
                    'Profit': profit,
                    'Profit %': profit_pct,
                    'Days Held': (sell['Trade Date'] - buy['Trade Date']).days
                })

# Convert to DataFrame and sort by profit
profit_df = pd.DataFrame(profitable_trades)
if not profit_df.empty:
    profit_df = profit_df.sort_values('Profit', ascending=False)
    
    print('\nTop 10 Most Profitable Transactions:')
    print('=' * 80)
    for idx in range(min(10, len(profit_df))):
        row = profit_df.iloc[idx]
        print(f"\n{idx+1}. {row['Symbol']}:")
        print(f"   Buy:  ₹{row['Buy Price']:,.2f} on {row['Buy Date'].strftime('%Y-%m-%d')}")
        print(f"   Sell: ₹{row['Sell Price']:,.2f} on {row['Sell Date'].strftime('%Y-%m-%d')}")
        print(f"   Quantity: {row['Quantity']:,}")
        print(f"   Profit: ₹{row['Profit']:,.2f} ({row['Profit %']:.2f}%)")
        print(f"   Days held: {row['Days Held']}")
    
    print('\n' + '=' * 80)
    print('Summary Statistics:')
    print(f'Total completed trades: {len(profit_df)}')
    print(f'Profitable trades: {len(profit_df[profit_df["Profit"] > 0])}')
    print(f'Losing trades: {len(profit_df[profit_df["Profit"] < 0])}')
    print(f'Total profit: ₹{profit_df["Profit"].sum():,.2f}')
    print(f'Average profit per trade: ₹{profit_df["Profit"].mean():,.2f}')
    
    if len(profit_df) > 0:
        best = profit_df.iloc[0]
        worst = profit_df.iloc[-1]
        print(f'\nBest trade: {best["Symbol"]} - ₹{best["Profit"]:,.2f} ({best["Profit %"]:.2f}%)')
        print(f'Worst trade: {worst["Symbol"]} - ₹{worst["Profit"]:,.2f} ({worst["Profit %"]:.2f}%)')
else:
    print('No completed trades (buy and sell) found in the last 3 weeks')

# Show symbols with open positions
print('\n' + '=' * 80)
print('Symbols with open positions (only buys or only sells):')
open_positions = []
for symbol, trades in symbol_trades.items():
    if (trades['buys'] and not trades['sells']) or (not trades['buys'] and trades['sells']):
        buy_count = len(trades['buys'])
        sell_count = len(trades['sells'])
        open_positions.append(f"{symbol}: {buy_count} buys, {sell_count} sells")

for pos in sorted(open_positions):
    print(f"  - {pos}")