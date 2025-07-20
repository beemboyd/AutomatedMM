#!/usr/bin/env python3
"""
Loss Pattern Backtest System
Analyzes your actual loss trades and backtests VSR exit strategies
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys
from vsr_loss_analyzer import VSRLossAnalyzer

class LossPatternBacktest:
    def __init__(self):
        self.analyzer = VSRLossAnalyzer()
        self.transaction_file = '../data/Transactions/06192025-07192025.xlsx'
        self.pnl_file = '../data/Transactions/06192025-07202025-PNL.xlsx'
        
    def load_loss_trades(self):
        """Load actual loss trades from transaction data"""
        # Read transaction data
        trans_df = pd.read_excel(self.transaction_file, sheet_name='Equity', header=14)
        trans_df = trans_df.drop('Unnamed: 0', axis=1, errors='ignore')
        trans_df['Trade Date'] = pd.to_datetime(trans_df['Trade Date'])
        trans_df['Order Execution Time'] = pd.to_datetime(trans_df['Order Execution Time'])
        
        # Read P&L data
        pnl_df = pd.read_excel(self.pnl_file, sheet_name='Equity', header=0)
        pnl_df['Total P&L'] = pnl_df['Realized P&L'].fillna(0) + pnl_df['Unrealized P&L'].fillna(0)
        
        # Get loss trades
        loss_trades = pnl_df[pnl_df['Total P&L'] < 0].copy()
        
        # Extract trade details
        trades = []
        for _, row in loss_trades.iterrows():
            symbol = row['Symbol']
            symbol_trans = trans_df[trans_df['Symbol'] == symbol].sort_values('Order Execution Time')
            
            if symbol_trans.empty:
                continue
                
            buys = symbol_trans[symbol_trans['Trade Type'] == 'buy']
            sells = symbol_trans[symbol_trans['Trade Type'] == 'sell']
            
            if not buys.empty:
                entry_time = buys['Order Execution Time'].iloc[0]
                entry_price = buys['Price'].iloc[0]
                
                if not sells.empty:
                    exit_time = sells['Order Execution Time'].iloc[-1]
                    exit_price = sells['Price'].iloc[-1]
                else:
                    # For open positions, use current date and last close price
                    exit_time = datetime.now()
                    exit_price = row['Previous Closing Price'] if pd.notna(row['Previous Closing Price']) else entry_price
                
                trades.append({
                    'symbol': symbol,
                    'entry_time': entry_time,
                    'exit_time': exit_time,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'actual_loss': row['Total P&L'],
                    'quantity': buys['Quantity'].sum()
                })
        
        return trades
    
    def backtest_vsr_strategy(self, trade, vsr_rules):
        """Backtest VSR exit strategy on a single trade"""
        analysis = self.analyzer.analyze_trade_entry_exit(
            trade['symbol'],
            trade['entry_time'],
            trade['exit_time'],
            trade['entry_price'],
            trade['exit_price']
        )
        
        if not analysis or not analysis['exit_signals']:
            return None
        
        # Find earliest exit signal based on rules
        earliest_exit = None
        earliest_time = trade['exit_time']
        
        for signal in analysis['exit_signals']:
            if signal['signal'] in vsr_rules and signal['time'] < earliest_time:
                earliest_exit = signal
                earliest_time = signal['time']
        
        if not earliest_exit:
            return None
        
        # Calculate what would have happened with early exit
        # Fetch price at exit signal time
        df = self.analyzer.get_historical_data(
            trade['symbol'],
            trade['entry_time'],
            earliest_time + timedelta(minutes=5),
            '5minute'
        )
        
        if df is None or df.empty:
            return None
        
        df['date'] = pd.to_datetime(df['date'])
        exit_candle_mask = (df['date'] <= earliest_time) & (df['date'] > earliest_time - timedelta(minutes=5))
        if not any(exit_candle_mask):
            return None
            
        exit_candle = df[exit_candle_mask].iloc[-1]
        optimized_exit_price = exit_candle['close']
        
        # Calculate savings
        original_loss_pct = ((trade['exit_price'] - trade['entry_price']) / trade['entry_price']) * 100
        optimized_loss_pct = ((optimized_exit_price - trade['entry_price']) / trade['entry_price']) * 100
        
        original_loss_amount = (trade['exit_price'] - trade['entry_price']) * trade['quantity']
        optimized_loss_amount = (optimized_exit_price - trade['entry_price']) * trade['quantity']
        amount_saved = original_loss_amount - optimized_loss_amount
        
        return {
            'symbol': trade['symbol'],
            'entry_time': trade['entry_time'],
            'original_exit_time': trade['exit_time'],
            'optimized_exit_time': earliest_time,
            'exit_signal': earliest_exit['signal'],
            'minutes_saved': (trade['exit_time'] - earliest_time).total_seconds() / 60,
            'original_loss_pct': original_loss_pct,
            'optimized_loss_pct': optimized_loss_pct,
            'loss_reduction_pct': original_loss_pct - optimized_loss_pct,
            'amount_saved': amount_saved,
            'shooting_star': analysis['is_shooting_star'],
            'entry_vsr_ratio': analysis['entry_vsr_ratio']
        }
    
    def run_backtest(self, vsr_rules=['VSR_DETERIORATION', 'THREE_RED_CANDLES', 'WEAK_SUPPORT']):
        """Run backtest on all loss trades"""
        print("Loading loss trades...")
        trades = self.load_loss_trades()
        print(f"Found {len(trades)} loss trades to analyze")
        
        results = []
        total_trades = len(trades)
        
        for i, trade in enumerate(trades):
            print(f"\rBacktesting {i+1}/{total_trades}: {trade['symbol']}...", end='')
            result = self.backtest_vsr_strategy(trade, vsr_rules)
            if result:
                results.append(result)
        
        print("\n\nBacktest Complete!")
        return results
    
    def generate_backtest_report(self, results):
        """Generate comprehensive backtest report"""
        if not results:
            print("No results to report")
            return
        
        df = pd.DataFrame(results)
        
        print("\n" + "="*100)
        print("VSR EXIT STRATEGY BACKTEST REPORT")
        print("="*100)
        
        print(f"\nTrades Analyzed: {len(results)}")
        print(f"Average Loss Reduction: {df['loss_reduction_pct'].mean():.2f}%")
        print(f"Total Amount Saved: ₹{df['amount_saved'].sum():,.2f}")
        print(f"Average Exit Time Saved: {df['minutes_saved'].mean():.1f} minutes")
        
        # Exit signal effectiveness
        print("\nExit Signal Effectiveness:")
        signal_stats = df.groupby('exit_signal').agg({
            'amount_saved': ['count', 'sum', 'mean'],
            'loss_reduction_pct': 'mean',
            'minutes_saved': 'mean'
        }).round(2)
        print(signal_stats)
        
        # Shooting star analysis
        shooting_star_trades = df[df['shooting_star'] == True]
        if not shooting_star_trades.empty:
            print(f"\nShooting Star Entries: {len(shooting_star_trades)} ({len(shooting_star_trades)/len(df)*100:.1f}%)")
            print(f"Average Loss on Shooting Stars: {shooting_star_trades['original_loss_pct'].mean():.2f}%")
            print(f"Could have been reduced to: {shooting_star_trades['optimized_loss_pct'].mean():.2f}%")
        
        # High VSR entries
        high_vsr_trades = df[df['entry_vsr_ratio'] > 2]
        if not high_vsr_trades.empty:
            print(f"\nHigh VSR Entries (>2x avg): {len(high_vsr_trades)} ({len(high_vsr_trades)/len(df)*100:.1f}%)")
            print(f"Average Loss on High VSR: {high_vsr_trades['original_loss_pct'].mean():.2f}%")
            print(f"Amount saved by early exit: ₹{high_vsr_trades['amount_saved'].sum():,.2f}")
        
        # Top opportunities
        print("\nTop 10 Missed Exit Opportunities:")
        top_saves = df.nlargest(10, 'amount_saved')[['symbol', 'exit_signal', 'minutes_saved', 'amount_saved', 'loss_reduction_pct']]
        for _, row in top_saves.iterrows():
            print(f"{row['symbol']}: Could save ₹{row['amount_saved']:,.2f} ({row['loss_reduction_pct']:.2f}%) "
                  f"by exiting {row['minutes_saved']:.0f} min earlier on {row['exit_signal']}")
        
        # Save detailed results
        output_file = 'vsr_backtest_results.xlsx'
        df.to_excel(output_file, index=False)
        print(f"\nDetailed results saved to: {output_file}")
        
        return df


if __name__ == "__main__":
    # Run backtest
    backtest = LossPatternBacktest()
    
    print("Running VSR Exit Strategy Backtest...")
    print("This will analyze your actual loss trades and show potential savings")
    print("-" * 80)
    
    # Define VSR rules to test
    vsr_rules = ['VSR_DETERIORATION', 'THREE_RED_CANDLES', 'WEAK_SUPPORT']
    
    # Run backtest
    results = backtest.run_backtest(vsr_rules)
    
    # Generate report
    backtest.generate_backtest_report(results)