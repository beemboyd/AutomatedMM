#!/usr/bin/env python3
"""
Simple demonstration of market regime detection
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import the traditional regime detector which is simpler
from ML.utils.market_regime import MarketRegimeDetector, MarketRegimeType

def create_sample_market_data(scenario='bull'):
    """Create sample market data for different scenarios"""
    dates = pd.date_range(end=datetime.now(), periods=252, freq='D')
    
    if scenario == 'bull':
        # Bull market: steady uptrend
        trend = np.linspace(100, 150, len(dates))
        volatility = 0.01
        
    elif scenario == 'bear':
        # Bear market: steady downtrend
        trend = np.linspace(100, 70, len(dates))
        volatility = 0.02
        
    elif scenario == 'volatile':
        # High volatility sideways
        trend = np.ones(len(dates)) * 100
        volatility = 0.05
        
    else:  # 'range'
        # Low volatility range
        trend = np.ones(len(dates)) * 100
        volatility = 0.005
    
    # Add random walk
    returns = np.random.normal(0, volatility, len(dates))
    prices = trend * np.exp(np.cumsum(returns))
    
    # Create OHLC
    data = pd.DataFrame({
        'Open': prices * (1 + np.random.normal(0, 0.001, len(dates))),
        'High': prices * (1 + np.abs(np.random.normal(0, 0.01, len(dates)))),
        'Low': prices * (1 - np.abs(np.random.normal(0, 0.01, len(dates)))),
        'Close': prices,
        'Volume': np.random.randint(900000, 1100000, len(dates))
    }, index=dates)
    
    return data

def main():
    print("Market Regime Detection Demo")
    print("=" * 80)
    print()
    
    # Initialize detector
    detector = MarketRegimeDetector()
    
    # Test different market scenarios
    scenarios = {
        'bull': 'Bull Market (Steady Uptrend)',
        'bear': 'Bear Market (Steady Downtrend)',
        'volatile': 'High Volatility Market',
        'range': 'Low Volatility Range'
    }
    
    print("REGIME DETECTION RESULTS:")
    print("-" * 80)
    
    for scenario, description in scenarios.items():
        # Create sample data
        data = create_sample_market_data(scenario)
        
        # Detect regime
        regime, metrics = detector.detect_consolidated_regime(data)
        
        # Get current regime
        current_regime = regime.iloc[-1]
        
        # Get metrics
        volatility = metrics['volatility'].iloc[-1] if 'volatility' in metrics else 0
        trend_strength = metrics['trend_strength'].iloc[-1] if 'trend_strength' in metrics else 0
        hurst = metrics['hurst'].iloc[-1] if 'hurst' in metrics else 0.5
        
        print(f"\n{description}:")
        print(f"  Detected Regime: {current_regime}")
        print(f"  Volatility: {volatility:.4f}")
        print(f"  Trend Strength: {trend_strength:.2f}")
        print(f"  Hurst Exponent: {hurst:.3f}")
        
        # Position sizing recommendation
        if current_regime == MarketRegimeType.TRENDING_BULLISH.value:
            position_factor = 1.2
            stop_multiplier = 2.0
        elif current_regime == MarketRegimeType.TRENDING_BEARISH.value:
            position_factor = 0.4
            stop_multiplier = 1.0
        elif current_regime == MarketRegimeType.RANGING_HIGH_VOL.value:
            position_factor = 0.5
            stop_multiplier = 2.5
        else:
            position_factor = 0.8
            stop_multiplier = 1.5
        
        print(f"  Position Size Factor: {position_factor}x")
        print(f"  Stop Loss Multiplier: {stop_multiplier}x ATR")
    
    print("\n" + "=" * 80)
    print("TRADING RECOMMENDATIONS BASED ON REGIME:")
    print("=" * 80)
    
    print("\n1. Position Sizing:")
    print("   - TRENDING_BULLISH: 120% of normal size")
    print("   - TRENDING_BEARISH: 40% of normal size")
    print("   - RANGING_HIGH_VOL: 50% of normal size")
    print("   - RANGING_LOW_VOL: 80% of normal size")
    
    print("\n2. Stop Loss Strategy:")
    print("   - TRENDING_BULLISH: 2.0x ATR (wider stops for trend)")
    print("   - TRENDING_BEARISH: 1.0x ATR (tighter stops)")
    print("   - RANGING_HIGH_VOL: 2.5x ATR (accommodate swings)")
    print("   - RANGING_LOW_VOL: 1.5x ATR (normal stops)")
    
    print("\n3. Entry Strategy:")
    print("   - TRENDING_BULLISH: Buy pullbacks, trend following")
    print("   - TRENDING_BEARISH: Avoid longs, consider shorts")
    print("   - RANGING_HIGH_VOL: Reduce activity, wider stops")
    print("   - RANGING_LOW_VOL: Mean reversion at extremes")
    
    print("\n" + "=" * 80)
    print("HOW TO USE THIS DAILY:")
    print("=" * 80)
    
    print("\n1. Run regime detection on market indices (NIFTY, BANKNIFTY)")
    print("2. Run on your portfolio stocks")
    print("3. Adjust position sizes based on regime")
    print("4. Update stop losses using ATR multipliers")
    print("5. Focus on stocks aligned with market regime")
    print("\nExample: If market is TRENDING_BULLISH but stock is TRENDING_BEARISH,")
    print("consider exiting or reducing position size significantly.")

if __name__ == "__main__":
    main()