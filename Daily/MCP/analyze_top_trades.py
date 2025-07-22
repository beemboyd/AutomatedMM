#!/usr/bin/env python3
"""
Find top 10 most profitable trades from P&L file
"""

import pandas as pd
import numpy as np

# Read the P&L Excel file with proper header
file_path = '/Users/maverick/PycharmProjects/India-TS/Daily/data/Transactions/06192025-07202025-PNL.xlsx'
df = pd.read_excel(file_path, sheet_name='Equity', header=0)

# Filter out rows where there's actual trading activity (either realized or unrealized P&L)
df['Total P&L'] = df['Realized P&L'].fillna(0) + df['Unrealized P&L'].fillna(0)
df['Has Activity'] = (df['Buy Value'] > 0) | (df['Sell Value'] > 0) | (df['Open Quantity'] > 0)

# Filter active trades
active_trades = df[df['Has Activity']].copy()

# Calculate total investment for each trade
active_trades['Total Investment'] = active_trades['Buy Value'].fillna(0) + active_trades['Open Value'].fillna(0)
active_trades['Total Quantity'] = active_trades['Quantity'].fillna(0) + active_trades['Open Quantity'].fillna(0)

# Sort by Total P&L
active_trades = active_trades.sort_values('Total P&L', ascending=False)

print("="*100)
print("TOP 10 MOST PROFITABLE TRADES (June 19 - July 20, 2025)")
print("="*100)

# Display top 10 trades
for idx, (_, row) in enumerate(active_trades.head(10).iterrows(), 1):
    print(f"\n{idx}. {row['Symbol']}")
    print(f"   Total Quantity: {row['Total Quantity']:,.0f} shares")
    
    if row['Buy Value'] > 0 and row['Sell Value'] > 0:
        # Completed trade
        print(f"   Buy Value: ₹{row['Buy Value']:,.2f}")
        print(f"   Sell Value: ₹{row['Sell Value']:,.2f}")
        print(f"   Realized P&L: ₹{row['Realized P&L']:,.2f} ({row['Realized P&L Pct.']:.2f}%)")
    
    if row['Open Quantity'] > 0:
        # Open position
        print(f"   Open Quantity: {row['Open Quantity']:,.0f} shares")
        print(f"   Open Value: ₹{row['Open Value']:,.2f}")
        print(f"   Current Price: ₹{row['Previous Closing Price']:,.2f}")
        print(f"   Unrealized P&L: ₹{row['Unrealized P&L']:,.2f} ({row['Unrealized P&L Pct.']:.2f}%)")
    
    print(f"   TOTAL P&L: ₹{row['Total P&L']:,.2f}")

# Summary statistics
print("\n" + "="*100)
print("SUMMARY STATISTICS")
print("="*100)

total_realized_pnl = active_trades['Realized P&L'].sum()
total_unrealized_pnl = active_trades['Unrealized P&L'].sum()
total_pnl = active_trades['Total P&L'].sum()

profitable_trades = active_trades[active_trades['Total P&L'] > 0]
losing_trades = active_trades[active_trades['Total P&L'] < 0]

print(f"Total Trades: {len(active_trades)}")
print(f"Profitable Trades: {len(profitable_trades)} ({len(profitable_trades)/len(active_trades)*100:.1f}%)")
print(f"Losing Trades: {len(losing_trades)} ({len(losing_trades)/len(active_trades)*100:.1f}%)")
print(f"\nTotal Realized P&L: ₹{total_realized_pnl:,.2f}")
print(f"Total Unrealized P&L: ₹{total_unrealized_pnl:,.2f}")
print(f"TOTAL P&L: ₹{total_pnl:,.2f}")

# Top gainers and losers
print("\n" + "="*100)
print("BIGGEST WINNERS AND LOSERS")
print("="*100)

print("\nTop 5 Winners:")
for idx, (_, row) in enumerate(active_trades.head(5).iterrows(), 1):
    pnl_type = "Realized" if row['Realized P&L'] > row['Unrealized P&L'] else "Unrealized"
    print(f"{idx}. {row['Symbol']}: ₹{row['Total P&L']:,.2f} ({pnl_type})")

print("\nTop 5 Losers:")
for idx, (_, row) in enumerate(active_trades.tail(5).iterrows(), 1):
    pnl_type = "Realized" if row['Realized P&L'] < 0 else "Unrealized"
    print(f"{idx}. {row['Symbol']}: ₹{row['Total P&L']:,.2f} ({pnl_type})")

# Best percentage gainers
active_trades['Best P&L %'] = active_trades[['Realized P&L Pct.', 'Unrealized P&L Pct.']].max(axis=1)
best_pct_gainers = active_trades[active_trades['Total P&L'] > 0].sort_values('Best P&L %', ascending=False)

print("\n" + "="*100)
print("TOP 5 BY PERCENTAGE GAIN")
print("="*100)
for idx, (_, row) in enumerate(best_pct_gainers.head(5).iterrows(), 1):
    print(f"{idx}. {row['Symbol']}: {row['Best P&L %']:.2f}% (₹{row['Total P&L']:,.2f})")