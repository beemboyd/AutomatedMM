#!/usr/bin/env python3
"""
Create a detailed summary table of worst 20 trades with entry/exit details
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

# Calculate total P&L and sort by worst first
pnl_df['Total P&L'] = pnl_df['Realized P&L'].fillna(0) + pnl_df['Unrealized P&L'].fillna(0)
pnl_df['Has Activity'] = (pnl_df['Buy Value'] > 0) | (pnl_df['Sell Value'] > 0) | (pnl_df['Open Quantity'] > 0)
active_trades = pnl_df[pnl_df['Has Activity']].copy()
worst_trades = active_trades.sort_values('Total P&L', ascending=True).head(20)

# Get symbols for worst 20
worst_symbols = worst_trades['Symbol'].tolist()

print("="*130)
print("TOP 20 TRADES WITH NEGATIVE PORTFOLIO IMPACT - ENTRY/EXIT SUMMARY")
print("="*130)
print(f"{'Rank':<5} {'Symbol':<12} {'Entry Date':<12} {'Avg Buy':<10} {'Exit Date':<12} {'Avg Sell':<10} {'Days':<6} {'Quantity':<10} {'Loss (₹)':<15} {'Loss %':<10} {'Status':<12}")
print("-"*130)

for rank, symbol in enumerate(worst_symbols, 1):
    # Get transactions
    symbol_trans = trans_df[trans_df['Symbol'] == symbol].sort_values('Trade Date')
    
    if symbol_trans.empty:
        continue
    
    # Get P&L data
    pnl_row = pnl_df[pnl_df['Symbol'] == symbol]
    if pnl_row.empty:
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
    else:
        avg_buy_price = 0
        entry_date = None
        buy_qty = 0
    
    if not sells.empty:
        sell_value = (sells['Price'] * sells['Quantity']).sum()
        sell_qty = sells['Quantity'].sum()
        avg_sell_price = sell_value / sell_qty if sell_qty > 0 else 0
        exit_date = sells['Trade Date'].max()
    else:
        avg_sell_price = 0
        exit_date = None
        sell_qty = 0
    
    # Get P&L data
    total_pnl = pnl_row['Total P&L'].values[0]
    
    # Determine status
    if pnl_row['Open Quantity'].values[0] > 0:
        if sell_qty > 0:
            status = "Partial Exit"
        else:
            status = "Open"
        open_qty = int(pnl_row['Open Quantity'].values[0])
    else:
        status = "Closed"
        open_qty = 0
    
    # Calculate holding period
    if entry_date and exit_date:
        holding_days = (exit_date - entry_date).days
    elif entry_date:
        # For open positions, calculate days to today
        holding_days = (datetime.now() - entry_date).days
    else:
        holding_days = 0
    
    # Calculate loss percentage
    if avg_buy_price > 0:
        if avg_sell_price > 0:
            loss_pct = ((avg_sell_price - avg_buy_price) / avg_buy_price) * 100
        else:
            # For open positions, use current price
            current_price = pnl_row['Previous Closing Price'].values[0]
            loss_pct = ((current_price - avg_buy_price) / avg_buy_price) * 100
    else:
        loss_pct = 0
    
    # Format output
    entry_str = entry_date.strftime('%Y-%m-%d') if entry_date else "N/A"
    exit_str = exit_date.strftime('%Y-%m-%d') if exit_date else "Open"
    
    # Use appropriate quantity
    if status == "Closed":
        display_qty = min(buy_qty, sell_qty)
    else:
        display_qty = buy_qty
    
    # Format sell price
    if avg_sell_price > 0:
        sell_price_str = f"₹{avg_sell_price:.2f}"
    elif status == "Open":
        current_price = pnl_row['Previous Closing Price'].values[0]
        sell_price_str = f"₹{current_price:.2f}*"
    else:
        sell_price_str = "N/A"
    
    print(f"{rank:<5} {symbol:<12} {entry_str:<12} ₹{avg_buy_price:<9.2f} {exit_str:<12} "
          f"{sell_price_str:<10} {holding_days:<6} {display_qty:<10,} ₹{total_pnl:<14,.2f} "
          f"{loss_pct:<9.2f}% {status:<12}")

print("-"*130)

# Summary statistics
total_loss = worst_trades['Total P&L'].sum()
realized_loss = worst_trades['Realized P&L'][worst_trades['Realized P&L'] < 0].sum()
unrealized_loss = worst_trades['Unrealized P&L'][worst_trades['Unrealized P&L'] < 0].sum()

print(f"\nTOTAL LOSS FROM 20 WORST TRADES: ₹{total_loss:,.2f}")
print(f"  - Realized Loss: ₹{realized_loss:,.2f}")
print(f"  - Unrealized Loss: ₹{unrealized_loss:,.2f}")

print("\nNOTES:")
print("- Entry Date: First buy date")
print("- Exit Date: Last sell date (or 'Open' if position still held)")
print("- Days: Total holding period from first buy")
print("- Loss %: Percentage loss based on average buy/sell prices")
print("- *Current price shown for open positions")
print("- Status: Closed = fully exited, Open = no sells yet, Partial Exit = some quantity still held")