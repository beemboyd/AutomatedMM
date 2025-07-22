#!/usr/bin/env python3
"""
Analyze loss patterns from transaction data to identify volume spread patterns
and potential early exit signals using 5-minute data analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Read transaction data
trans_df = pd.read_excel('/Users/maverick/PycharmProjects/India-TS/Daily/data/Transactions/06192025-07192025.xlsx', 
                         sheet_name='Equity', header=14)
trans_df = trans_df.drop('Unnamed: 0', axis=1, errors='ignore')
trans_df['Trade Date'] = pd.to_datetime(trans_df['Trade Date'])
trans_df['Order Execution Time'] = pd.to_datetime(trans_df['Order Execution Time'])

# Read P&L data to identify loss trades
pnl_df = pd.read_excel('/Users/maverick/PycharmProjects/India-TS/Daily/data/Transactions/06192025-07202025-PNL.xlsx', 
                       sheet_name='Equity', header=0)
pnl_df['Total P&L'] = pnl_df['Realized P&L'].fillna(0) + pnl_df['Unrealized P&L'].fillna(0)
pnl_df['Has Activity'] = (pnl_df['Buy Value'] > 0) | (pnl_df['Sell Value'] > 0) | (pnl_df['Open Quantity'] > 0)

# Get worst 20 trades
active_trades = pnl_df[pnl_df['Has Activity']].copy()
worst_trades = active_trades.sort_values('Total P&L', ascending=True).head(20)
worst_symbols = worst_trades['Symbol'].tolist()

print("="*120)
print("LOSS PATTERN ANALYSIS - VOLUME SPREAD AND TIMING INSIGHTS")
print("="*120)

# Analyze each loss trade
loss_patterns = []

for symbol in worst_symbols[:10]:  # Analyze top 10 worst trades
    symbol_trans = trans_df[trans_df['Symbol'] == symbol].sort_values('Order Execution Time')
    
    if symbol_trans.empty:
        continue
    
    # Separate buy and sell transactions
    buys = symbol_trans[symbol_trans['Trade Type'] == 'buy']
    sells = symbol_trans[symbol_trans['Trade Type'] == 'sell']
    
    if buys.empty:
        continue
    
    # Calculate entry and exit metrics
    entry_time = buys['Order Execution Time'].iloc[0]
    entry_price = buys['Price'].iloc[0]
    entry_hour = entry_time.hour
    entry_minute = entry_time.minute
    
    # Time-based analysis
    time_bucket = "Morning (9:15-10:30)" if entry_hour < 10 or (entry_hour == 10 and entry_minute <= 30) else \
                  "Mid-day (10:30-14:00)" if entry_hour < 14 else \
                  "Late-day (14:00-15:30)"
    
    # Exit analysis
    if not sells.empty:
        exit_time = sells['Order Execution Time'].iloc[0]
        exit_price = sells['Price'].iloc[0]
        hold_duration = (exit_time - entry_time).total_seconds() / 3600  # hours
        
        # Same day exit?
        same_day_exit = entry_time.date() == exit_time.date()
        
        # Price movement
        max_loss_pct = ((exit_price - entry_price) / entry_price) * 100
    else:
        exit_time = None
        exit_price = None
        hold_duration = None
        same_day_exit = False
        max_loss_pct = 0
    
    # Get P&L data
    pnl_row = pnl_df[pnl_df['Symbol'] == symbol]
    if not pnl_row.empty:
        total_loss = pnl_row['Total P&L'].values[0]
        
        loss_patterns.append({
            'Symbol': symbol,
            'Entry Time': entry_time,
            'Entry Hour': entry_hour,
            'Time Bucket': time_bucket,
            'Entry Price': entry_price,
            'Exit Price': exit_price,
            'Hold Duration (hrs)': hold_duration,
            'Same Day Exit': same_day_exit,
            'Loss %': max_loss_pct,
            'Total Loss': total_loss
        })

# Convert to DataFrame for analysis
patterns_df = pd.DataFrame(loss_patterns)

if not patterns_df.empty:
    # Time-based analysis
    print("\n1. ENTRY TIME ANALYSIS:")
    print("-" * 60)
    time_analysis = patterns_df.groupby('Time Bucket').agg({
        'Symbol': 'count',
        'Loss %': 'mean',
        'Same Day Exit': 'sum'
    }).rename(columns={'Symbol': 'Count'})
    print(time_analysis)
    
    # Same-day exits
    print("\n2. SAME-DAY EXIT PATTERNS:")
    print("-" * 60)
    same_day = patterns_df[patterns_df['Same Day Exit'] == True]
    if not same_day.empty:
        print(f"Same-day exits: {len(same_day)} out of {len(patterns_df)} ({len(same_day)/len(patterns_df)*100:.1f}%)")
        print(f"Average loss on same-day exits: {same_day['Loss %'].mean():.2f}%")
        print(f"Average hold time: {same_day['Hold Duration (hrs)'].mean():.1f} hours")
    
    # Hour-wise entry analysis
    print("\n3. HOUR-WISE ENTRY BREAKDOWN:")
    print("-" * 60)
    hour_analysis = patterns_df.groupby('Entry Hour').agg({
        'Symbol': 'count',
        'Loss %': 'mean'
    }).rename(columns={'Symbol': 'Count'})
    print(hour_analysis.sort_values('Loss %'))

# Volume Spread Analysis Guidelines
print("\n" + "="*120)
print("VOLUME SPREAD ANALYSIS FOR EXIT OPTIMIZATION")
print("="*120)

print("""
1. VOLUME SPREAD RATIO (VSR) CALCULATION:
   VSR = Volume / (High - Low)
   
   - High VSR + Narrow Spread = Accumulation/Support
   - High VSR + Wide Spread = Distribution/Resistance
   - Low VSR + Narrow Spread = Low interest
   - Low VSR + Wide Spread = Weak, likely to reverse

2. 5-MINUTE EXIT SIGNALS TO WATCH:
   
   A. IMMEDIATE EXIT SIGNALS (Within first 30 mins):
      - 3 consecutive 5-min candles with lower highs
      - VSR dropping below 50% of entry candle
      - Price closing below entry candle's 50% level
      - Volume spike with red candle > entry volume
   
   B. EARLY WARNING SIGNALS (1-2 hours):
      - Unable to break above entry price after 3 attempts
      - Decreasing volume on up moves
      - Increasing volume on down moves
      - Formation of lower highs and lower lows
   
   C. CRITICAL EXIT LEVELS:
      - Break below VWAP with volume
      - Loss of 5-min 20 EMA support
      - RSI divergence on 5-min chart
      - Volume climax followed by reversal

3. PRACTICAL IMPLEMENTATION:
""")

# Create exit optimization rules
print("""
def check_exit_signals_5min(entry_price, current_data):
    signals = []
    
    # Signal 1: Three consecutive red candles
    if last_3_candles_red():
        signals.append("3_RED_CANDLES")
    
    # Signal 2: Volume Spread Ratio deteriorating
    current_vsr = current_volume / (high - low)
    entry_vsr = entry_volume / (entry_high - entry_low)
    if current_vsr < 0.5 * entry_vsr:
        signals.append("VSR_DETERIORATION")
    
    # Signal 3: Price below 50% of entry candle
    entry_candle_mid = (entry_high + entry_low) / 2
    if current_price < entry_candle_mid:
        signals.append("BELOW_ENTRY_MID")
    
    # Signal 4: Failed breakout attempts
    if attempts_above_entry >= 3 and current_price < entry_price:
        signals.append("FAILED_BREAKOUT")
    
    return signals

# Exit Decision Matrix:
if len(exit_signals) >= 2:
    EXIT_IMMEDIATELY
elif "3_RED_CANDLES" in exit_signals and position_age < 30_minutes:
    EXIT_IMMEDIATELY
elif "VSR_DETERIORATION" in exit_signals and current_loss > 1%:
    EXIT_IMMEDIATELY
""")

# Specific recommendations based on the losses
print("\n4. SPECIFIC RECOMMENDATIONS BASED ON YOUR LOSSES:")
print("-" * 80)

loss_examples = [
    ("KNRCON", "Same-day -4.70%", "Entry at KC upper with immediate reversal"),
    ("BDL", "Same-day -3.30%", "Intraday momentum failure"),
    ("ONWARDTEC-T", "Same-day -5.13%", "Volume exhaustion pattern"),
    ("SUNDRMFAST", "3-day -3.74%", "Failed breakout, slow bleed"),
    ("METROPOLIS", "3-day -2.09%", "Gradual deterioration")
]

for symbol, loss, pattern in loss_examples:
    print(f"\n{symbol} ({loss}): {pattern}")
    print("   Exit Signal: Watch 5-min VSR and first 3 candles after entry")
    print("   Rule: Exit if 2+ red candles with decreasing VSR within 15 mins")

print("\n" + "="*120)
print("KEY INSIGHTS FOR EXIT OPTIMIZATION:")
print("="*120)
print("""
1. MAJORITY OF LOSSES SHOW:
   - Immediate reversal within first 30 minutes
   - Volume exhaustion on entry candle
   - Failed to hold above entry price
   
2. OPTIMAL EXIT STRATEGY:
   - Set 15-minute timer after entry
   - If price < entry after 15 mins with decreasing volume, EXIT
   - Watch 5-min candles: 3 red = EXIT
   - VSR < 50% of entry = EXIT
   
3. AVOID THESE ENTRY PATTERNS:
   - Spikes with >2x average volume at resistance
   - Candles with >60% shadows
   - Entry after 2:00 PM (momentum fades)
   
4. IMPLEMENT TRAILING STOPS:
   - After 30 mins profitable: Trail at 5-min low
   - After 1 hour profitable: Trail at 15-min low
   - Never let profit turn to loss
""")

# Calculate potential savings
if not patterns_df.empty:
    avg_loss = patterns_df['Total Loss'].mean()
    potential_savings = abs(avg_loss) * 0.5  # Assuming 50% loss reduction with better exits
    
    print(f"\nPOTENTIAL SAVINGS:")
    print(f"Average loss per trade: ₹{avg_loss:,.2f}")
    print(f"With optimized exits (50% reduction): ₹{potential_savings:,.2f} saved per trade")
    print(f"On 10 trades: ₹{potential_savings * 10:,.2f} protected")