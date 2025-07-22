#!/usr/bin/env python3
"""
Create a summary table of top 10 trades with entry/exit details
"""

import pandas as pd
import numpy as np
from datetime import datetime

# Read transaction data
trans_df = pd.read_excel('/Users/maverick/PycharmProjects/India-TS/Daily/data/Transactions/06192025-07192025.xlsx', 
                         sheet_name='Equity', header=14)
trans_df = trans_df.drop('Unnamed: 0', axis=1, errors='ignore')
trans_df['Trade Date'] = pd.to_datetime(trans_df['Trade Date'])

# Read P&L data
pnl_df = pd.read_excel('/Users/maverick/PycharmProjects/India-TS/Daily/data/Transactions/06192025-07202025-PNL.xlsx', 
                       sheet_name='Equity', header=0)

# Top 10 symbols
top_symbols = ['HINDUNILVR', 'THERMAX', 'CUB', 'ASHAPURMIN', 'LAURUSLABS', 
               'JAIBALAJI', 'BALAMINES', 'MCX', 'JKLAKSHMI', 'HARIOMPIPE']

print("="*120)
print("TOP 10 MOST PROFITABLE TRADES - ENTRY/EXIT SUMMARY")
print("="*120)
print(f"{'Rank':<5} {'Symbol':<12} {'Entry Date':<12} {'Avg Buy':<10} {'Exit Date':<12} {'Avg Sell':<10} {'Days':<6} {'Quantity':<10} {'Profit (₹)':<15} {'Return %':<10}")
print("-"*120)

trade_data = []

for rank, symbol in enumerate(top_symbols, 1):
    # Get transactions
    symbol_trans = trans_df[trans_df['Symbol'] == symbol].sort_values('Trade Date')
    
    if symbol_trans.empty:
        continue
    
    # Separate buys and sells
    buys = symbol_trans[symbol_trans['Trade Type'] == 'buy']
    sells = symbol_trans[symbol_trans['Trade Type'] == 'sell']
    
    # Calculate weighted averages and dates
    if not buys.empty:
        buy_value = (buys['Price'] * buys['Quantity']).sum()
        buy_qty = buys['Quantity'].sum()
        avg_buy_price = buy_value / buy_qty if buy_qty > 0 else 0
        entry_date = buys['Trade Date'].min()
        last_buy_date = buys['Trade Date'].max()
    else:
        avg_buy_price = 0
        entry_date = None
        buy_qty = 0
    
    if not sells.empty:
        sell_value = (sells['Price'] * sells['Quantity']).sum()
        sell_qty = sells['Quantity'].sum()
        avg_sell_price = sell_value / sell_qty if sell_qty > 0 else 0
        exit_date = sells['Trade Date'].max()
        first_sell_date = sells['Trade Date'].min()
    else:
        avg_sell_price = 0
        exit_date = None
        sell_qty = 0
    
    # Get P&L data
    pnl_row = pnl_df[pnl_df['Symbol'] == symbol]
    if not pnl_row.empty:
        total_pnl = pnl_row['Realized P&L'].values[0] + pnl_row['Unrealized P&L'].values[0]
        
        # Determine if position is still open
        if pnl_row['Open Quantity'].values[0] > 0:
            status = f"(Open: {int(pnl_row['Open Quantity'].values[0]):,})"
        else:
            status = ""
    else:
        total_pnl = 0
        status = ""
    
    # Calculate holding period
    if entry_date and exit_date:
        holding_days = (exit_date - entry_date).days
    else:
        holding_days = 0
    
    # Calculate return percentage
    if avg_buy_price > 0 and avg_sell_price > 0:
        return_pct = ((avg_sell_price - avg_buy_price) / avg_buy_price) * 100
    else:
        return_pct = 0
    
    # Format output
    entry_str = entry_date.strftime('%Y-%m-%d') if entry_date else "N/A"
    exit_str = exit_date.strftime('%Y-%m-%d') if exit_date else "Open"
    
    # Use matched quantity
    matched_qty = min(buy_qty, sell_qty) if sell_qty > 0 else buy_qty
    
    print(f"{rank:<5} {symbol:<12} {entry_str:<12} ₹{avg_buy_price:<9.2f} {exit_str:<12} "
          f"₹{avg_sell_price:<9.2f} {holding_days:<6} {matched_qty:<10,} ₹{total_pnl:<14,.2f} "
          f"{return_pct:<9.2f}% {status}")

print("-"*120)

# Summary notes
print("\nNOTES:")
print("- Entry Date: First buy date")
print("- Exit Date: Last sell date (or 'Open' if position still held)")
print("- Days: Total holding period from first buy to last sell")
print("- Quantity: Matched quantity (minimum of buy and sell quantities)")
print("- Profit includes both realized and unrealized P&L")
print("- ASHAPURMIN shows negative realized P&L but has significant unrealized gains on open position")