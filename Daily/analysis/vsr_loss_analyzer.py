#!/usr/bin/env python3
"""
VSR Loss Pattern Analyzer using Zerodha Historical Data
Analyzes historical losses to identify volume spread patterns and optimize exits
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys

# Add parent directory to path for imports
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ..user_context_manager import UserContextManager

class VSRLossAnalyzer:
    def __init__(self, user_context=None):
        """Initialize VSR Loss Analyzer with user context"""
        self.user_context = user_context or UserContextManager().get_default_context()
        self.kite = self.user_context.kite
        
    def get_historical_data(self, symbol, from_date, to_date, interval='5minute'):
        """Fetch historical data from Zerodha"""
        try:
            # Get instrument token
            instruments = self.kite.ltp([f'NSE:{symbol}'])
            if not instruments or f'NSE:{symbol}' not in instruments:
                print(f"Could not find instrument token for {symbol}")
                return None
                
            instrument_token = list(instruments.values())[0]['instrument_token']
            
            # Fetch historical data
            historical_data = self.kite.historical_data(
                instrument_token,
                from_date,
                to_date,
                interval
            )
            
            # Convert to DataFrame
            df = pd.DataFrame(historical_data)
            df['symbol'] = symbol
            return df
            
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return None
    
    def calculate_vsr(self, df):
        """Calculate Volume Spread Ratio for each candle"""
        df['spread'] = df['high'] - df['low']
        # Avoid division by zero
        df['vsr'] = np.where(df['spread'] > 0, df['volume'] / df['spread'], 0)
        df['vsr_sma'] = df['vsr'].rolling(window=20).mean()
        return df
    
    def identify_shooting_star(self, candle):
        """Identify if a candle is a shooting star pattern"""
        body = abs(candle['close'] - candle['open'])
        range_total = candle['high'] - candle['low']
        upper_shadow = candle['high'] - max(candle['open'], candle['close'])
        lower_shadow = min(candle['open'], candle['close']) - candle['low']
        
        if range_total == 0:
            return False, 0
        
        # Shooting star criteria
        body_ratio = body / range_total
        upper_shadow_ratio = upper_shadow / range_total
        lower_shadow_ratio = lower_shadow / range_total
        
        is_shooting_star = (
            upper_shadow_ratio > 0.6 and  # Long upper shadow
            body_ratio < 0.3 and          # Small body
            lower_shadow_ratio < 0.1      # Little to no lower shadow
        )
        
        # Score from 0-100
        score = (
            upper_shadow_ratio * 50 +     # Weight upper shadow heavily
            (1 - body_ratio) * 30 +       # Small body is good
            (1 - lower_shadow_ratio) * 20 # No lower shadow is good
        ) * 100
        
        return is_shooting_star, score
    
    def analyze_trade_entry_exit(self, symbol, entry_time, exit_time, entry_price, exit_price):
        """Analyze a specific trade using 5-minute data"""
        # Fetch data from entry to exit (plus some buffer)
        from_date = entry_time - timedelta(days=1)
        to_date = exit_time + timedelta(days=1)
        
        df = self.get_historical_data(symbol, from_date, to_date, '5minute')
        if df is None or df.empty:
            return None
            
        # Calculate VSR
        df = self.calculate_vsr(df)
        
        # Find entry candle
        df['date'] = pd.to_datetime(df['date'])
        entry_mask = (df['date'] <= entry_time) & (df['date'] > entry_time - timedelta(minutes=5))
        entry_candle = df[entry_mask].iloc[-1] if any(entry_mask) else None
        
        if entry_candle is None:
            return None
            
        # Analyze entry pattern
        is_shooting_star, shooting_score = self.identify_shooting_star(entry_candle)
        
        # Get post-entry candles (first 30 minutes)
        post_entry_mask = (df['date'] > entry_time) & (df['date'] <= entry_time + timedelta(minutes=30))
        post_entry_candles = df[post_entry_mask]
        
        # Analyze VSR patterns
        analysis = {
            'symbol': symbol,
            'entry_time': entry_time,
            'exit_time': exit_time,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'loss_percent': ((exit_price - entry_price) / entry_price) * 100,
            'entry_vsr': entry_candle['vsr'],
            'entry_vsr_ratio': entry_candle['vsr'] / entry_candle['vsr_sma'] if entry_candle['vsr_sma'] > 0 else 0,
            'is_shooting_star': is_shooting_star,
            'shooting_star_score': shooting_score,
            'entry_volume': entry_candle['volume'],
            'exit_signals': []
        }
        
        # Check for exit signals in first 30 minutes
        if not post_entry_candles.empty:
            # Signal 1: VSR deterioration
            min_vsr = post_entry_candles['vsr'].min()
            if min_vsr < 0.5 * entry_candle['vsr']:
                first_signal_time = post_entry_candles[post_entry_candles['vsr'] < 0.5 * entry_candle['vsr']].iloc[0]['date']
                analysis['exit_signals'].append({
                    'signal': 'VSR_DETERIORATION',
                    'time': first_signal_time,
                    'minutes_after_entry': (first_signal_time - entry_time).total_seconds() / 60
                })
            
            # Signal 2: Consecutive red candles
            post_entry_candles['is_red'] = post_entry_candles['close'] < post_entry_candles['open']
            for i in range(len(post_entry_candles) - 2):
                if all(post_entry_candles['is_red'].iloc[i:i+3]):
                    analysis['exit_signals'].append({
                        'signal': 'THREE_RED_CANDLES',
                        'time': post_entry_candles.iloc[i+2]['date'],
                        'minutes_after_entry': (post_entry_candles.iloc[i+2]['date'] - entry_time).total_seconds() / 60
                    })
                    break
            
            # Signal 3: Price below entry
            below_entry = post_entry_candles[post_entry_candles['close'] < entry_price]
            if not below_entry.empty:
                first_below = below_entry.iloc[0]
                if first_below['vsr'] < entry_candle['vsr']:
                    analysis['exit_signals'].append({
                        'signal': 'WEAK_SUPPORT',
                        'time': first_below['date'],
                        'minutes_after_entry': (first_below['date'] - entry_time).total_seconds() / 60
                    })
        
        return analysis
    
    def generate_report(self, analyses):
        """Generate comprehensive report from analyses"""
        report = {
            'summary': {
                'total_trades_analyzed': len(analyses),
                'shooting_star_entries': sum(1 for a in analyses if a['is_shooting_star']),
                'high_vsr_entries': sum(1 for a in analyses if a['entry_vsr_ratio'] > 2),
                'trades_with_early_exit_signals': sum(1 for a in analyses if a['exit_signals'])
            },
            'exit_signal_effectiveness': {},
            'recommendations': []
        }
        
        # Analyze exit signals
        signal_counts = {}
        signal_timings = {}
        
        for analysis in analyses:
            for signal in analysis['exit_signals']:
                signal_type = signal['signal']
                if signal_type not in signal_counts:
                    signal_counts[signal_type] = 0
                    signal_timings[signal_type] = []
                signal_counts[signal_type] += 1
                signal_timings[signal_type].append(signal['minutes_after_entry'])
        
        # Calculate effectiveness
        for signal_type, count in signal_counts.items():
            avg_timing = np.mean(signal_timings[signal_type])
            report['exit_signal_effectiveness'][signal_type] = {
                'count': count,
                'percentage': (count / len(analyses)) * 100,
                'avg_minutes_after_entry': avg_timing
            }
        
        # Generate recommendations
        if report['summary']['shooting_star_entries'] > len(analyses) * 0.3:
            report['recommendations'].append(
                "High percentage of entries on shooting star patterns. "
                "Implement pre-entry filter to avoid candles with >60% upper shadow."
            )
        
        if report['summary']['high_vsr_entries'] > len(analyses) * 0.4:
            report['recommendations'].append(
                "Many entries on abnormally high VSR (>2x average). "
                "These often indicate exhaustion. Add VSR threshold check."
            )
        
        if 'VSR_DETERIORATION' in report['exit_signal_effectiveness']:
            vsr_data = report['exit_signal_effectiveness']['VSR_DETERIORATION']
            if vsr_data['avg_minutes_after_entry'] < 15:
                report['recommendations'].append(
                    f"VSR deterioration occurs on average within {vsr_data['avg_minutes_after_entry']:.1f} minutes. "
                    "Implement 15-minute VSR monitoring rule."
                )
        
        return report


# Example usage
if __name__ == "__main__":
    print("VSR Loss Pattern Analyzer")
    print("="*80)
    
    # Initialize analyzer
    analyzer = VSRLossAnalyzer()
    
    # Example trade analysis (you would get these from your transaction data)
    example_trades = [
        {
            'symbol': 'KNRCON',
            'entry_time': datetime(2025, 6, 26, 10, 30),
            'exit_time': datetime(2025, 6, 26, 14, 30),
            'entry_price': 238.27,
            'exit_price': 227.07
        },
        {
            'symbol': 'BDL',
            'entry_time': datetime(2025, 6, 19, 9, 30),
            'exit_time': datetime(2025, 6, 19, 15, 15),
            'entry_price': 1944.42,
            'exit_price': 1880.18
        }
    ]
    
    # Analyze trades
    analyses = []
    for trade in example_trades:
        print(f"\nAnalyzing {trade['symbol']}...")
        analysis = analyzer.analyze_trade_entry_exit(**trade)
        if analysis:
            analyses.append(analysis)
            print(f"Entry VSR: {analysis['entry_vsr']:.2f}")
            print(f"Shooting Star: {analysis['is_shooting_star']} (Score: {analysis['shooting_star_score']:.1f})")
            print(f"Exit Signals Found: {len(analysis['exit_signals'])}")
            for signal in analysis['exit_signals']:
                print(f"  - {signal['signal']} at {signal['minutes_after_entry']:.1f} minutes")
    
    # Generate report
    if analyses:
        report = analyzer.generate_report(analyses)
        print("\n" + "="*80)
        print("ANALYSIS REPORT")
        print("="*80)
        print(f"Total Trades Analyzed: {report['summary']['total_trades_analyzed']}")
        print(f"Shooting Star Entries: {report['summary']['shooting_star_entries']}")
        print(f"High VSR Entries: {report['summary']['high_vsr_entries']}")
        print(f"Trades with Early Exit Signals: {report['summary']['trades_with_early_exit_signals']}")
        
        print("\nExit Signal Effectiveness:")
        for signal, data in report['exit_signal_effectiveness'].items():
            print(f"  {signal}: {data['count']} trades ({data['percentage']:.1f}%), "
                  f"avg {data['avg_minutes_after_entry']:.1f} min after entry")
        
        print("\nRecommendations:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"{i}. {rec}")