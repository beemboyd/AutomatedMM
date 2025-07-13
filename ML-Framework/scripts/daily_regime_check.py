#!/usr/bin/env python3
"""
Simplified Daily Market Regime Check
This script provides actionable regime analysis for daily trading decisions.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import json

# Add paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ML.utils.market_regime import MarketRegimeDetector, MarketRegimeType

class DailyRegimeChecker:
    def __init__(self):
        self.detector = MarketRegimeDetector()
        self.data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'BT', 'data'
        )
        
        # Regime-based parameters
        self.regime_params = {
            MarketRegimeType.TRENDING_BULLISH.value: {
                'position_factor': 1.2,
                'max_position': 0.10,
                'stop_multiplier_long': 2.0,
                'stop_multiplier_short': 1.2,
                'action': 'INCREASE_LONGS'
            },
            MarketRegimeType.TRENDING_BEARISH.value: {
                'position_factor': 0.4,
                'max_position': 0.03,
                'stop_multiplier_long': 1.0,
                'stop_multiplier_short': 2.0,
                'action': 'REDUCE_OR_EXIT'
            },
            MarketRegimeType.RANGING_HIGH_VOL.value: {
                'position_factor': 0.5,
                'max_position': 0.03,
                'stop_multiplier_long': 2.5,
                'stop_multiplier_short': 2.5,
                'action': 'REDUCE_SIZE'
            },
            MarketRegimeType.RANGING_LOW_VOL.value: {
                'position_factor': 0.8,
                'max_position': 0.05,
                'stop_multiplier_long': 1.5,
                'stop_multiplier_short': 1.5,
                'action': 'RANGE_TRADE'
            },
            MarketRegimeType.TRANSITIONING.value: {
                'position_factor': 0.7,
                'max_position': 0.05,
                'stop_multiplier_long': 2.0,
                'stop_multiplier_short': 2.0,
                'action': 'WAIT'
            }
        }
    
    def load_data(self, ticker):
        """Load historical data for a ticker"""
        file_path = os.path.join(self.data_dir, f'{ticker}_day.csv')
        
        if os.path.exists(file_path):
            data = pd.read_csv(file_path)
            data['date'] = pd.to_datetime(data['date'])
            data = data.set_index('date')
            
            # Use last 252 trading days (1 year)
            if len(data) > 252:
                data = data.iloc[-252:]
            
            return data
        
        return None
    
    def analyze_ticker(self, ticker):
        """Analyze regime for a single ticker"""
        data = self.load_data(ticker)
        
        if data is None:
            return {
                'ticker': ticker,
                'error': 'No data available'
            }
        
        # Detect regime
        regime, metrics = self.detector.detect_consolidated_regime(data)
        
        # Get current values
        current_regime = regime.iloc[-1]
        current_price = data['Close'].iloc[-1]
        
        # Get metrics
        volatility = metrics['volatility'].iloc[-1] if 'volatility' in metrics else 0
        trend_strength = metrics['trend_strength'].iloc[-1] if 'trend_strength' in metrics else 0
        
        # Get parameters for regime
        params = self.regime_params.get(current_regime, self.regime_params[MarketRegimeType.TRANSITIONING.value])
        
        # Calculate ATR for stop loss
        high = data['High']
        low = data['Low']
        close = data['Close']
        close_prev = close.shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close_prev)
        tr3 = abs(low - close_prev)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        return {
            'ticker': ticker,
            'regime': current_regime,
            'price': current_price,
            'volatility': volatility,
            'trend_strength': trend_strength,
            'atr': atr,
            'position_factor': params['position_factor'],
            'max_position': params['max_position'],
            'stop_multiplier_long': params['stop_multiplier_long'],
            'stop_multiplier_short': params['stop_multiplier_short'],
            'action': params['action'],
            'stop_loss_long': current_price - (atr * params['stop_multiplier_long']),
            'stop_loss_short': current_price + (atr * params['stop_multiplier_short'])
        }
    
    def load_portfolio_positions(self):
        """Load current positions from trading state"""
        state_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'data', 'trading_state.json'
        )
        
        if os.path.exists(state_path):
            with open(state_path, 'r') as f:
                state = json.load(f)
                return state.get('positions', {})
        
        return {}
    
    def generate_report(self, tickers=None):
        """Generate comprehensive regime report"""
        # Default tickers if none provided
        if tickers is None:
            # Try to get from portfolio
            positions = self.load_portfolio_positions()
            tickers = list(positions.keys()) if positions else []
            
            # Add some indices
            tickers.extend(['NIFTY', 'BANKNIFTY', 'RELIANCE', 'TCS'])
        
        # Remove duplicates
        tickers = list(set(tickers))
        
        print("=" * 80)
        print(f"DAILY MARKET REGIME ANALYSIS - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 80)
        
        results = []
        regime_counts = {}
        
        # Analyze each ticker
        for ticker in tickers:
            result = self.analyze_ticker(ticker)
            results.append(result)
            
            if 'regime' in result:
                regime_counts[result['regime']] = regime_counts.get(result['regime'], 0) + 1
        
        # Market Overview
        print("\nMARKET OVERVIEW:")
        print("-" * 40)
        
        if regime_counts:
            total = sum(regime_counts.values())
            for regime, count in sorted(regime_counts.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total) * 100
                print(f"{regime:25} | {count:3} stocks ({percentage:5.1f}%)")
            
            # Determine market sentiment
            bullish = regime_counts.get(MarketRegimeType.TRENDING_BULLISH.value, 0)
            bearish = regime_counts.get(MarketRegimeType.TRENDING_BEARISH.value, 0)
            
            if bullish > bearish * 2:
                sentiment = "BULLISH - Increase exposure"
            elif bearish > bullish * 2:
                sentiment = "BEARISH - Reduce exposure"
            else:
                sentiment = "MIXED - Be selective"
            
            print(f"\nOverall Sentiment: {sentiment}")
        
        # Individual Stock Analysis
        print("\n" + "=" * 80)
        print("INDIVIDUAL STOCK ANALYSIS:")
        print("=" * 80)
        
        # Sort by action priority
        action_priority = {
            'REDUCE_OR_EXIT': 1,
            'REDUCE_SIZE': 2,
            'WAIT': 3,
            'RANGE_TRADE': 4,
            'INCREASE_LONGS': 5
        }
        
        results_sorted = sorted(results, key=lambda x: action_priority.get(x.get('action', 'WAIT'), 3))
        
        for result in results_sorted:
            if 'error' in result:
                print(f"\n{result['ticker']}: {result['error']}")
                continue
            
            print(f"\n{result['ticker']}:")
            print(f"  Current Price: ₹{result['price']:.2f}")
            print(f"  Regime: {result['regime']}")
            print(f"  Action: {result['action']}")
            print(f"  Position Size: {result['position_factor']*100:.0f}% of normal")
            print(f"  Max Position: {result['max_position']*100:.1f}% of capital")
            print(f"  Stop Loss (Long): ₹{result['stop_loss_long']:.2f} ({result['stop_multiplier_long']}x ATR)")
            print(f"  Stop Loss (Short): ₹{result['stop_loss_short']:.2f} ({result['stop_multiplier_short']}x ATR)")
            
            # Special warnings
            if result['action'] == 'REDUCE_OR_EXIT':
                print(f"  ⚠️  WARNING: Consider exiting or significantly reducing position")
            elif result['volatility'] > 0.04:
                print(f"  ⚠️  HIGH VOLATILITY: {result['volatility']:.4f}")
        
        # Summary Recommendations
        print("\n" + "=" * 80)
        print("SUMMARY RECOMMENDATIONS:")
        print("=" * 80)
        
        # Group by action
        actions_summary = {}
        for result in results:
            if 'action' in result:
                action = result['action']
                if action not in actions_summary:
                    actions_summary[action] = []
                actions_summary[action].append(result['ticker'])
        
        for action, tickers in actions_summary.items():
            print(f"\n{action}:")
            print(f"  {', '.join(tickers)}")
        
        # Risk Management
        print("\n" + "=" * 80)
        print("RISK MANAGEMENT RULES FOR TODAY:")
        print("=" * 80)
        
        # Calculate average position factor
        position_factors = [r['position_factor'] for r in results if 'position_factor' in r]
        avg_factor = np.mean(position_factors) if position_factors else 1.0
        
        print(f"\n1. Overall Position Sizing: {avg_factor*100:.0f}% of normal")
        print(f"2. New Positions: Only in stocks with INCREASE_LONGS or RANGE_TRADE signals")
        print(f"3. Stop Losses: Update all stops based on regime multipliers above")
        print(f"4. Maximum Exposure: Keep total portfolio exposure under {avg_factor*80:.0f}%")
        
        return results

def main():
    """Main entry point"""
    checker = DailyRegimeChecker()
    
    # You can specify tickers or it will use portfolio positions
    # Example: checker.generate_report(['RELIANCE', 'TCS', 'INFY'])
    checker.generate_report()

if __name__ == "__main__":
    main()