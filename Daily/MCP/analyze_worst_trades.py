#!/usr/bin/env python3
"""
Find top 20 worst performing trades from P&L file
"""

import pandas as pd
import numpy as np

# Read the P&L Excel file
df = pd.read_excel('/Users/maverick/PycharmProjects/India-TS/Daily/data/Transactions/06192025-07202025-PNL.xlsx', 
                   sheet_name='Equity', header=0)

# Calculate total P&L
df['Total P&L'] = df['Realized P&L'].fillna(0) + df['Unrealized P&L'].fillna(0)
df['Has Activity'] = (df['Buy Value'] > 0) | (df['Sell Value'] > 0) | (df['Open Quantity'] > 0)

# Filter active trades and sort by Total P&L (ascending for worst first)
active_trades = df[df['Has Activity']].copy()
active_trades = active_trades.sort_values('Total P&L', ascending=True)

# Get worst 20 trades
worst_trades = active_trades.head(20)

print("="*120)
print("TOP 20 TRADES WITH NEGATIVE IMPACT ON PORTFOLIO (June 19 - July 20, 2025)")
print("="*120)

# Display worst 20 trades
for idx, (_, row) in enumerate(worst_trades.iterrows(), 1):
    print(f"\n{idx}. {row['Symbol']}")
    total_qty = (row['Quantity'] if pd.notna(row['Quantity']) else 0) + (row['Open Quantity'] if pd.notna(row['Open Quantity']) else 0)
    print(f"   Total Quantity: {total_qty:,.0f} shares")
    
    if row['Buy Value'] > 0 and row['Sell Value'] > 0:
        # Completed trade
        print(f"   Buy Value: ₹{row['Buy Value']:,.2f}")
        print(f"   Sell Value: ₹{row['Sell Value']:,.2f}")
        print(f"   Realized Loss: ₹{row['Realized P&L']:,.2f} ({row['Realized P&L Pct.']:.2f}%)")
    
    if row['Open Quantity'] > 0:
        # Open position
        print(f"   Open Quantity: {row['Open Quantity']:,.0f} shares")
        print(f"   Open Value: ₹{row['Open Value']:,.2f}")
        print(f"   Current Price: ₹{row['Previous Closing Price']:,.2f}")
        print(f"   Unrealized Loss: ₹{row['Unrealized P&L']:,.2f} ({row['Unrealized P&L Pct.']:.2f}%)")
    
    print(f"   TOTAL LOSS: ₹{row['Total P&L']:,.2f}")
    
    # Investment info
    buy_val = row['Buy Value'] if pd.notna(row['Buy Value']) else 0
    open_val = row['Open Value'] if pd.notna(row['Open Value']) else 0
    total_investment = buy_val + open_val
    if total_investment > 0:
        print(f"   Total Investment: ₹{total_investment:,.2f}")
        loss_pct = (row['Total P&L'] / total_investment) * 100
        print(f"   Loss on Investment: {loss_pct:.2f}%")

# Summary statistics
print("\n" + "="*120)
print("LOSS SUMMARY STATISTICS")
print("="*120)

total_losses = worst_trades['Total P&L'].sum()
realized_losses = worst_trades['Realized P&L'][worst_trades['Realized P&L'] < 0].sum()
unrealized_losses = worst_trades['Unrealized P&L'][worst_trades['Unrealized P&L'] < 0].sum()

print(f"Total Loss from 20 Worst Trades: ₹{total_losses:,.2f}")
print(f"Realized Losses: ₹{realized_losses:,.2f}")
print(f"Unrealized Losses: ₹{unrealized_losses:,.2f}")

# Category breakdown
realized_only = worst_trades[(worst_trades['Realized P&L'] < 0) & (worst_trades['Open Quantity'] == 0)]
unrealized_only = worst_trades[(worst_trades['Unrealized P&L'] < 0) & (worst_trades['Sell Value'] == 0)]
mixed = worst_trades[(worst_trades['Realized P&L'] < 0) & (worst_trades['Unrealized P&L'] < 0)]

print(f"\nLoss Categories:")
print(f"- Closed Positions with Loss: {len(realized_only)} trades")
print(f"- Open Positions with Loss: {len(unrealized_only)} trades")
print(f"- Mixed (Partially closed with loss): {len(mixed)} trades")

# Worst percentage losers
worst_pct = worst_trades.copy()
worst_pct['Worst P&L %'] = worst_pct[['Realized P&L Pct.', 'Unrealized P&L Pct.']].min(axis=1)
worst_pct = worst_pct.sort_values('Worst P&L %', ascending=True)

print("\n" + "="*120)
print("TOP 10 BY PERCENTAGE LOSS")
print("="*120)
for idx, (_, row) in enumerate(worst_pct.head(10).iterrows(), 1):
    loss_type = "Realized" if row['Realized P&L'] < row['Unrealized P&L'] else "Unrealized"
    print(f"{idx}. {row['Symbol']}: {row['Worst P&L %']:.2f}% (₹{row['Total P&L']:,.2f}) - {loss_type}")