#!/usr/bin/env python3
"""
Get detailed entry/exit dates and prices for top profitable trades
"""

import pandas as pd
import numpy as np
from datetime import datetime

# Read the transaction book
trans_df = pd.read_excel('/Users/maverick/PycharmProjects/India-TS/Daily/data/Transactions/06192025-07192025.xlsx', 
                         sheet_name='Equity', header=14)

# Clean data
trans_df = trans_df.drop('Unnamed: 0', axis=1, errors='ignore')
trans_df['Trade Date'] = pd.to_datetime(trans_df['Trade Date'])
trans_df['Order Execution Time'] = pd.to_datetime(trans_df['Order Execution Time'])

# Top 10 symbols from P&L analysis
top_symbols = ['HINDUNILVR', 'THERMAX', 'CUB', 'ASHAPURMIN', 'LAURUSLABS', 
               'JAIBALAJI', 'BALAMINES', 'MCX', 'JKLAKSHMI', 'HARIOMPIPE']

print("="*100)
print("DETAILED ENTRY/EXIT ANALYSIS FOR TOP 10 PROFITABLE TRADES")
print("="*100)

for symbol in top_symbols:
    # Filter transactions for this symbol
    symbol_trans = trans_df[trans_df['Symbol'] == symbol].sort_values('Order Execution Time')
    
    if symbol_trans.empty:
        continue
    
    # Separate buy and sell transactions
    buys = symbol_trans[symbol_trans['Trade Type'] == 'buy']
    sells = symbol_trans[symbol_trans['Trade Type'] == 'sell']
    
    print(f"\n{'='*80}")
    print(f"{symbol}")
    print('='*80)
    
    # Entry details (buys)
    if not buys.empty:
        print("\nENTRY TRANSACTIONS:")
        print(f"{'Date':<12} {'Time':<10} {'Quantity':<10} {'Price':<12} {'Value':<15}")
        print("-"*70)
        
        total_buy_qty = 0
        total_buy_value = 0
        
        for _, buy in buys.iterrows():
            print(f"{buy['Trade Date'].strftime('%Y-%m-%d'):<12} "
                  f"{buy['Order Execution Time'].strftime('%H:%M:%S'):<10} "
                  f"{buy['Quantity']:<10,} "
                  f"₹{buy['Price']:<11,.2f} "
                  f"₹{buy['Price'] * buy['Quantity']:<14,.2f}")
            total_buy_qty += buy['Quantity']
            total_buy_value += buy['Price'] * buy['Quantity']
        
        avg_buy_price = total_buy_value / total_buy_qty if total_buy_qty > 0 else 0
        print("-"*70)
        print(f"{'TOTAL BUY':<34} {total_buy_qty:<10,} "
              f"₹{avg_buy_price:<11,.2f} ₹{total_buy_value:<14,.2f}")
        
        first_buy_date = buys['Trade Date'].min()
        last_buy_date = buys['Trade Date'].max()
        print(f"\nEntry Period: {first_buy_date.strftime('%Y-%m-%d')} to {last_buy_date.strftime('%Y-%m-%d')}")
    
    # Exit details (sells)
    if not sells.empty:
        print("\nEXIT TRANSACTIONS:")
        print(f"{'Date':<12} {'Time':<10} {'Quantity':<10} {'Price':<12} {'Value':<15}")
        print("-"*70)
        
        total_sell_qty = 0
        total_sell_value = 0
        
        for _, sell in sells.iterrows():
            print(f"{sell['Trade Date'].strftime('%Y-%m-%d'):<12} "
                  f"{sell['Order Execution Time'].strftime('%H:%M:%S'):<10} "
                  f"{sell['Quantity']:<10,} "
                  f"₹{sell['Price']:<11,.2f} "
                  f"₹{sell['Price'] * sell['Quantity']:<14,.2f}")
            total_sell_qty += sell['Quantity']
            total_sell_value += sell['Price'] * sell['Quantity']
        
        avg_sell_price = total_sell_value / total_sell_qty if total_sell_qty > 0 else 0
        print("-"*70)
        print(f"{'TOTAL SELL':<34} {total_sell_qty:<10,} "
              f"₹{avg_sell_price:<11,.2f} ₹{total_sell_value:<14,.2f}")
        
        first_sell_date = sells['Trade Date'].min()
        last_sell_date = sells['Trade Date'].max()
        print(f"\nExit Period: {first_sell_date.strftime('%Y-%m-%d')} to {last_sell_date.strftime('%Y-%m-%d')}")
    
    # Calculate holding period and profit
    if not buys.empty and not sells.empty:
        holding_days = (sells['Trade Date'].max() - buys['Trade Date'].min()).days
        matched_qty = min(total_buy_qty, total_sell_qty)
        profit = (avg_sell_price - avg_buy_price) * matched_qty
        profit_pct = ((avg_sell_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price > 0 else 0
        
        print(f"\nTRADE SUMMARY:")
        print(f"Holding Period: {holding_days} days")
        print(f"Matched Quantity: {matched_qty:,}")
        print(f"Profit: ₹{profit:,.2f} ({profit_pct:.2f}%)")
        
        # Check for open positions
        if total_buy_qty > total_sell_qty:
            open_qty = total_buy_qty - total_sell_qty
            print(f"Open Position: {open_qty:,} shares (still holding)")
    
    # If only buys (open position)
    elif not buys.empty and sells.empty:
        print(f"\nOPEN POSITION: {total_buy_qty:,} shares bought, no sells yet")
        print(f"Average Buy Price: ₹{avg_buy_price:,.2f}")
        print(f"Total Investment: ₹{total_buy_value:,.2f}")