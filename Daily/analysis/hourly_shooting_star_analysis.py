#!/usr/bin/env python3
"""
Analyze how many loss trades could have been avoided by checking
hourly candle patterns (shooting star with >60% upper shadow)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys

# Add parent directory to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ..user_context_manager import UserContextManager

class HourlyShootingStarAnalysis:
    def __init__(self):
        self.user_context = UserContextManager().get_default_context()
        self.kite = self.user_context.kite
        
    def analyze_hourly_candle(self, candle):
        """Check if hourly candle is a shooting star"""
        total_range = candle['high'] - candle['low']
        if total_range == 0:
            return False, 0
            
        body = abs(candle['close'] - candle['open'])
        upper_shadow = candle['high'] - max(candle['open'], candle['close'])
        lower_shadow = min(candle['open'], candle['close']) - candle['low']
        
        # Calculate ratios
        upper_shadow_ratio = upper_shadow / total_range
        body_ratio = body / total_range
        lower_shadow_ratio = lower_shadow / total_range
        
        # Shooting star criteria
        is_shooting_star = upper_shadow_ratio > 0.60  # >60% upper shadow
        
        return is_shooting_star, upper_shadow_ratio * 100
    
    def check_entry_hour(self, symbol, entry_time):
        """Check if entry was made during an hourly shooting star candle"""
        try:
            # Get the hourly candle that contains the entry time
            hour_start = entry_time.replace(minute=0, second=0, microsecond=0)
            hour_end = hour_start + timedelta(hours=1)
            
            # Fetch hourly data
            instruments = self.kite.ltp([f'NSE:{symbol}'])
            if not instruments or f'NSE:{symbol}' not in instruments:
                return None, "No instrument data"
                
            instrument_token = list(instruments.values())[0]['instrument_token']
            
            # Fetch data for the day
            from_date = entry_time.date()
            to_date = from_date + timedelta(days=1)
            
            hourly_data = self.kite.historical_data(
                instrument_token,
                from_date,
                to_date,
                '60minute'
            )
            
            if not hourly_data:
                return None, "No hourly data"
            
            # Find the hourly candle that contains entry time
            df = pd.DataFrame(hourly_data)
            df['date'] = pd.to_datetime(df['date'])
            
            # Get the candle that contains our entry
            entry_candle = None
            for _, candle in df.iterrows():
                candle_start = candle['date']
                candle_end = candle_start + timedelta(hours=1)
                if candle_start <= entry_time < candle_end:
                    entry_candle = candle
                    break
            
            if entry_candle is None:
                # Try the previous candle if entry was at exact hour
                mask = df['date'] < entry_time
                if any(mask):
                    entry_candle = df[mask].iloc[-1]
                else:
                    return None, "No matching candle"
            
            # Analyze the candle
            is_shooting_star, upper_shadow_pct = self.analyze_hourly_candle(entry_candle)
            
            return {
                'is_shooting_star': is_shooting_star,
                'upper_shadow_pct': upper_shadow_pct,
                'candle_time': entry_candle['date'],
                'high': entry_candle['high'],
                'low': entry_candle['low'],
                'open': entry_candle['open'],
                'close': entry_candle['close'],
                'volume': entry_candle['volume']
            }, None
            
        except Exception as e:
            return None, str(e)
    
    def analyze_loss_trades(self):
        """Analyze all loss trades for hourly shooting star patterns"""
        # Load loss trades
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
        
        results = []
        
        for _, pnl_row in loss_trades.iterrows():
            symbol = pnl_row['Symbol']
            symbol_trans = trans_df[trans_df['Symbol'] == symbol].sort_values('Order Execution Time')
            
            if symbol_trans.empty:
                continue
            
            buys = symbol_trans[symbol_trans['Trade Type'] == 'buy']
            if buys.empty:
                continue
            
            # Get entry details
            entry_time = buys['Order Execution Time'].iloc[0]
            entry_price = buys['Price'].iloc[0]
            
            print(f"\nAnalyzing {symbol} - Entry at {entry_time}")
            
            # Check hourly candle
            candle_analysis, error = self.check_entry_hour(symbol, entry_time)
            
            if error:
                print(f"  Error: {error}")
                results.append({
                    'symbol': symbol,
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'total_loss': pnl_row['Total P&L'],
                    'loss_pct': ((pnl_row['Sell Value'] / pnl_row['Buy Value'] - 1) * 100) if pnl_row['Buy Value'] > 0 else 0,
                    'hourly_shooting_star': None,
                    'upper_shadow_pct': None,
                    'error': error
                })
            else:
                print(f"  Hourly Shooting Star: {candle_analysis['is_shooting_star']}")
                print(f"  Upper Shadow: {candle_analysis['upper_shadow_pct']:.1f}%")
                
                results.append({
                    'symbol': symbol,
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'total_loss': pnl_row['Total P&L'],
                    'loss_pct': ((pnl_row['Sell Value'] / pnl_row['Buy Value'] - 1) * 100) if pnl_row['Buy Value'] > 0 else 0,
                    'hourly_shooting_star': candle_analysis['is_shooting_star'],
                    'upper_shadow_pct': candle_analysis['upper_shadow_pct'],
                    'candle_details': candle_analysis,
                    'error': None
                })
        
        return results
    
    def generate_report(self, results):
        """Generate analysis report"""
        print("\n" + "="*100)
        print("HOURLY SHOOTING STAR ANALYSIS REPORT")
        print("="*100)
        
        # Filter successful analyses
        valid_results = [r for r in results if r['error'] is None]
        shooting_star_entries = [r for r in valid_results if r['hourly_shooting_star']]
        
        print(f"\nTotal Loss Trades Analyzed: {len(results)}")
        print(f"Successfully Analyzed: {len(valid_results)}")
        print(f"Entries on Hourly Shooting Star: {len(shooting_star_entries)}")
        
        if valid_results:
            avoidance_rate = len(shooting_star_entries) / len(valid_results) * 100
            print(f"Could Have Avoided: {avoidance_rate:.1f}% of losses")
        
        # Calculate potential savings
        total_losses = sum(r['total_loss'] for r in results)
        avoidable_losses = sum(r['total_loss'] for r in shooting_star_entries)
        
        print(f"\nFinancial Impact:")
        print(f"Total Losses: ₹{abs(total_losses):,.2f}")
        print(f"Avoidable Losses: ₹{abs(avoidable_losses):,.2f}")
        print(f"Potential Savings: {abs(avoidable_losses)/abs(total_losses)*100:.1f}%")
        
        # Show specific trades that could have been avoided
        if shooting_star_entries:
            print("\n" + "-"*100)
            print("TRADES THAT COULD HAVE BEEN AVOIDED (Hourly Shooting Star)")
            print("-"*100)
            print(f"{'Symbol':<12} {'Entry Time':<20} {'Upper Shadow':<15} {'Loss':<15} {'Loss %':<10}")
            print("-"*100)
            
            for trade in sorted(shooting_star_entries, key=lambda x: x['total_loss']):
                print(f"{trade['symbol']:<12} {trade['entry_time'].strftime('%Y-%m-%d %H:%M'):<20} "
                      f"{trade['upper_shadow_pct']:<14.1f}% ₹{trade['total_loss']:<14,.2f} "
                      f"{trade['loss_pct']:<9.2f}%")
        
        # Additional insights
        print("\n" + "-"*100)
        print("INSIGHTS:")
        print("-"*100)
        
        if valid_results:
            avg_shadow_all = np.mean([r['upper_shadow_pct'] for r in valid_results if r['upper_shadow_pct'] is not None])
            avg_shadow_losses = np.mean([r['upper_shadow_pct'] for r in shooting_star_entries]) if shooting_star_entries else 0
            
            print(f"Average upper shadow on all loss trades: {avg_shadow_all:.1f}%")
            print(f"Average upper shadow on avoidable trades: {avg_shadow_losses:.1f}%")
            
            # Different threshold analysis
            thresholds = [50, 60, 70]
            print("\nAvoidance rate at different thresholds:")
            for threshold in thresholds:
                avoidable = [r for r in valid_results if r['upper_shadow_pct'] and r['upper_shadow_pct'] > threshold]
                rate = len(avoidable) / len(valid_results) * 100 if valid_results else 0
                savings = sum(r['total_loss'] for r in avoidable)
                print(f"  >{threshold}% upper shadow: {len(avoidable)} trades ({rate:.1f}%), "
                      f"savings: ₹{abs(savings):,.2f}")
        
        return {
            'total_analyzed': len(results),
            'shooting_star_entries': len(shooting_star_entries),
            'avoidable_losses': abs(avoidable_losses),
            'avoidance_rate': len(shooting_star_entries) / len(valid_results) * 100 if valid_results else 0
        }


if __name__ == "__main__":
    analyzer = HourlyShootingStarAnalysis()
    
    print("Analyzing loss trades for hourly shooting star patterns...")
    print("This will check if entries were made during hourly candles with >60% upper shadow")
    print("-" * 80)
    
    results = analyzer.analyze_loss_trades()
    report = analyzer.generate_report(results)
    
    # Save results
    df = pd.DataFrame(results)
    df.to_excel('hourly_shooting_star_analysis.xlsx', index=False)
    print(f"\nDetailed results saved to: hourly_shooting_star_analysis.xlsx")