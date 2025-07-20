#!/usr/bin/env python3
"""
Comprehensive Loss Analysis Runner
Analyzes your historical losses and provides actionable insights
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys
from vsr_loss_analyzer import VSRLossAnalyzer
from loss_pattern_backtest import LossPatternBacktest

def load_actual_losses():
    """Load your actual loss trades from transaction files"""
    trans_file = '../data/Transactions/06192025-07192025.xlsx'
    pnl_file = '../data/Transactions/06192025-07202025-PNL.xlsx'
    
    # Read transaction data
    trans_df = pd.read_excel(trans_file, sheet_name='Equity', header=14)
    trans_df = trans_df.drop('Unnamed: 0', axis=1, errors='ignore')
    trans_df['Trade Date'] = pd.to_datetime(trans_df['Trade Date'])
    trans_df['Order Execution Time'] = pd.to_datetime(trans_df['Order Execution Time'])
    
    # Read P&L data
    pnl_df = pd.read_excel(pnl_file, sheet_name='Equity', header=0)
    pnl_df['Total P&L'] = pnl_df['Realized P&L'].fillna(0) + pnl_df['Unrealized P&L'].fillna(0)
    
    # Get worst 20 trades
    loss_trades = pnl_df[pnl_df['Total P&L'] < 0].sort_values('Total P&L').head(20)
    
    # Map to transaction details
    detailed_losses = []
    for _, row in loss_trades.iterrows():
        symbol = row['Symbol']
        symbol_trans = trans_df[trans_df['Symbol'] == symbol].sort_values('Order Execution Time')
        
        if not symbol_trans.empty:
            buys = symbol_trans[symbol_trans['Trade Type'] == 'buy']
            sells = symbol_trans[symbol_trans['Trade Type'] == 'sell']
            
            if not buys.empty:
                entry_time = buys['Order Execution Time'].iloc[0]
                entry_price = buys['Price'].iloc[0]
                entry_date = buys['Trade Date'].iloc[0]
                
                if not sells.empty:
                    exit_time = sells['Order Execution Time'].iloc[-1]
                    exit_price = sells['Price'].iloc[-1]
                    exit_date = sells['Trade Date'].iloc[-1]
                else:
                    exit_time = datetime.now()
                    exit_price = row['Previous Closing Price'] if pd.notna(row['Previous Closing Price']) else entry_price
                    exit_date = datetime.now().date()
                
                detailed_losses.append({
                    'symbol': symbol,
                    'entry_date': entry_date,
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'exit_date': exit_date,
                    'exit_time': exit_time,
                    'exit_price': exit_price,
                    'quantity': buys['Quantity'].sum(),
                    'total_loss': row['Total P&L'],
                    'loss_pct': ((exit_price - entry_price) / entry_price) * 100,
                    'hold_days': (exit_date - entry_date).days
                })
    
    return detailed_losses

def main():
    print("="*100)
    print("COMPREHENSIVE LOSS PATTERN ANALYSIS")
    print("="*100)
    
    # Load actual losses
    print("\n1. Loading your actual loss trades...")
    losses = load_actual_losses()
    print(f"Found {len(losses)} loss trades")
    
    # Display top 10 losses
    print("\n2. Your Top 10 Losses:")
    print("-"*100)
    print(f"{'Rank':<5} {'Symbol':<12} {'Entry Date':<12} {'Entry Price':<12} {'Exit Price':<12} {'Loss %':<10} {'Loss Amount':<15}")
    print("-"*100)
    
    for i, loss in enumerate(losses[:10], 1):
        print(f"{i:<5} {loss['symbol']:<12} {loss['entry_date'].strftime('%Y-%m-%d'):<12} "
              f"₹{loss['entry_price']:<11.2f} ₹{loss['exit_price']:<11.2f} "
              f"{loss['loss_pct']:<9.2f}% ₹{loss['total_loss']:<14,.2f}")
    
    # Analyze patterns
    print("\n3. Loss Pattern Analysis:")
    print("-"*100)
    
    # Same-day losses
    same_day_losses = [l for l in losses if l['hold_days'] == 0]
    if same_day_losses:
        print(f"Same-day losses: {len(same_day_losses)} ({len(same_day_losses)/len(losses)*100:.1f}%)")
        avg_same_day_loss = np.mean([l['loss_pct'] for l in same_day_losses])
        print(f"Average same-day loss: {avg_same_day_loss:.2f}%")
    
    # Quick losses (within 3 days)
    quick_losses = [l for l in losses if l['hold_days'] <= 3]
    if quick_losses:
        print(f"Quick losses (≤3 days): {len(quick_losses)} ({len(quick_losses)/len(losses)*100:.1f}%)")
        avg_quick_loss = np.mean([l['loss_pct'] for l in quick_losses])
        print(f"Average quick loss: {avg_quick_loss:.2f}%")
    
    # Time-based analysis
    print("\n4. Entry Time Analysis:")
    print("-"*100)
    
    time_buckets = {
        'Morning (9:15-10:30)': [],
        'Mid-day (10:30-14:00)': [],
        'Late-day (14:00-15:30)': []
    }
    
    for loss in losses:
        hour = loss['entry_time'].hour
        minute = loss['entry_time'].minute
        
        if hour < 10 or (hour == 10 and minute <= 30):
            time_buckets['Morning (9:15-10:30)'].append(loss['loss_pct'])
        elif hour < 14:
            time_buckets['Mid-day (10:30-14:00)'].append(loss['loss_pct'])
        else:
            time_buckets['Late-day (14:00-15:30)'].append(loss['loss_pct'])
    
    for time_slot, loss_pcts in time_buckets.items():
        if loss_pcts:
            print(f"{time_slot}: {len(loss_pcts)} trades, avg loss: {np.mean(loss_pcts):.2f}%")
    
    # VSR Analysis Summary
    print("\n5. VSR-Based Exit Optimization Potential:")
    print("-"*100)
    
    # Initialize VSR analyzer
    analyzer = VSRLossAnalyzer()
    
    # Sample analysis on top 5 losses
    print("Analyzing top 5 losses for VSR patterns...")
    vsr_savings = 0
    
    for loss in losses[:5]:
        try:
            analysis = analyzer.analyze_trade_entry_exit(
                loss['symbol'],
                loss['entry_time'],
                loss['exit_time'],
                loss['entry_price'],
                loss['exit_price']
            )
            
            if analysis and analysis['exit_signals']:
                earliest_signal = min(analysis['exit_signals'], key=lambda x: x['minutes_after_entry'])
                potential_savings = abs(loss['total_loss']) * 0.5  # Assume 50% loss reduction
                vsr_savings += potential_savings
                
                print(f"\n{loss['symbol']}:")
                print(f"  - Shooting Star Entry: {analysis['is_shooting_star']}")
                print(f"  - Entry VSR Ratio: {analysis['entry_vsr_ratio']:.2f}x average")
                print(f"  - First Exit Signal: {earliest_signal['signal']} at {earliest_signal['minutes_after_entry']:.0f} minutes")
                print(f"  - Potential Savings: ₹{potential_savings:,.2f}")
        except Exception as e:
            print(f"Could not analyze {loss['symbol']}: {e}")
    
    # Summary and Recommendations
    print("\n" + "="*100)
    print("KEY FINDINGS AND RECOMMENDATIONS")
    print("="*100)
    
    total_losses = sum(abs(l['total_loss']) for l in losses)
    print(f"\n1. Total Losses Analyzed: ₹{total_losses:,.2f}")
    print(f"2. Potential Savings with VSR Exit Rules: ₹{vsr_savings:,.2f} (on top 5 trades alone)")
    
    print("\n3. ACTIONABLE RECOMMENDATIONS:")
    print("-"*80)
    
    recommendations = [
        "ENTRY FILTERS:",
        "  • Skip entries with >60% upper shadow (shooting star pattern)",
        "  • Avoid entries when VSR > 2x average (exhaustion signal)",
        "  • Be cautious with late-day entries (after 2 PM)",
        "",
        "EXIT RULES (First 30 minutes):",
        "  • Exit if VSR drops below 50% of entry VSR",
        "  • Exit on 3 consecutive red 5-minute candles",
        "  • Exit if price closes below entry candle's midpoint",
        "",
        "POSITION MONITORING:",
        "  • Use the VSR Exit Dashboard for real-time monitoring",
        "  • Set alerts for VSR deterioration patterns",
        "  • Trail stop loss after 30 minutes of profit"
    ]
    
    for rec in recommendations:
        print(rec)
    
    print("\n4. IMPLEMENTATION STEPS:")
    print("-"*80)
    print("1. Run the VSR Exit Dashboard: python vsr_exit_dashboard.py")
    print("2. Add your open positions to monitor")
    print("3. Follow the exit signals strictly")
    print("4. Review this analysis weekly to refine rules")
    
    # Save analysis results
    output_data = {
        'analysis_date': datetime.now().isoformat(),
        'total_losses_analyzed': len(losses),
        'total_loss_amount': total_losses,
        'same_day_loss_percentage': len(same_day_losses) / len(losses) * 100 if losses else 0,
        'potential_vsr_savings': vsr_savings,
        'top_losses': losses[:10]
    }
    
    with open('loss_analysis_results.json', 'w') as f:
        json.dump(output_data, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: loss_analysis_results.json")
    
    # Create summary Excel file
    summary_df = pd.DataFrame(losses)
    summary_df.to_excel('loss_analysis_summary.xlsx', index=False)
    print(f"Summary Excel saved to: loss_analysis_summary.xlsx")

if __name__ == "__main__":
    main()