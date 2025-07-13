#!/usr/bin/env python3
"""
Test script for Market Regime Analysis with sample data
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add parent directories to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.market_regime_ml import MarketRegimeML

def create_sample_data(ticker, trend='bullish', volatility='normal'):
    """Create sample OHLCV data for testing"""
    dates = pd.date_range(end=datetime.now(), periods=365, freq='D')
    
    # Base price
    base_price = 100
    
    # Create trend
    if trend == 'bullish':
        trend_component = np.linspace(0, 50, len(dates))
    elif trend == 'bearish':
        trend_component = np.linspace(0, -30, len(dates))
    else:  # sideways
        trend_component = np.zeros(len(dates))
    
    # Add volatility
    if volatility == 'high':
        noise = np.random.normal(0, 5, len(dates))
    elif volatility == 'low':
        noise = np.random.normal(0, 1, len(dates))
    else:
        noise = np.random.normal(0, 2, len(dates))
    
    # Generate prices
    close_prices = base_price + trend_component + noise.cumsum()
    
    # Ensure positive prices
    close_prices = np.maximum(close_prices, 10)
    
    # Generate OHLC
    high_prices = close_prices + np.abs(np.random.normal(0, 1, len(dates)))
    low_prices = close_prices - np.abs(np.random.normal(0, 1, len(dates)))
    open_prices = close_prices + np.random.normal(0, 0.5, len(dates))
    
    # Generate volume
    base_volume = 1000000
    volume = base_volume + np.random.randint(-500000, 500000, len(dates))
    
    data = pd.DataFrame({
        'date': dates,
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volume
    })
    
    data.set_index('date', inplace=True)
    
    return data

def main():
    """Run test regime analysis"""
    print("Market Regime Analysis - Test Mode")
    print("=" * 60)
    
    # Initialize regime detector
    regime_detector = MarketRegimeML()
    
    # Test different market conditions
    test_cases = [
        ('BULLISH_STOCK', 'bullish', 'normal'),
        ('BEARISH_STOCK', 'bearish', 'normal'),
        ('VOLATILE_STOCK', 'sideways', 'high'),
        ('STABLE_STOCK', 'sideways', 'low'),
    ]
    
    results = {}
    
    for ticker, trend, volatility in test_cases:
        print(f"\nAnalyzing {ticker} (trend={trend}, volatility={volatility})...")
        
        # Create sample data
        data = create_sample_data(ticker, trend, volatility)
        
        # Detect regime
        try:
            regime, details = regime_detector.detect_regime(ticker, data, use_ensemble=False)
            
            results[ticker] = {
                'regime': regime,
                'confidence': details['confidence'],
                'volatility': details['metrics'].get('volatility', 'N/A'),
                'trend_strength': details['metrics'].get('trend_strength', 'N/A'),
                'position_adjustment': details['position_adjustment'],
                'stop_loss_multipliers': details['stop_loss_multipliers']
            }
            
            print(f"  Regime: {regime}")
            print(f"  Confidence: {details['confidence']:.2%}")
            print(f"  Position Adjustment: {details['position_adjustment']:.1f}x")
            print(f"  Stop Loss (Long): {details['stop_loss_multipliers']['long']}x ATR")
            
        except Exception as e:
            print(f"  Error: {str(e)}")
            results[ticker] = {'error': str(e)}
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    print("\nPosition Sizing Recommendations:")
    print("-" * 40)
    for ticker, result in results.items():
        if 'error' not in result:
            adjustment = result['position_adjustment']
            regime = result['regime']
            print(f"{ticker:15} | {regime:15} | {adjustment:.1f}x")
    
    print("\nRisk Management Implications:")
    print("-" * 40)
    
    # Market outlook based on majority
    regimes = [r['regime'] for r in results.values() if 'regime' in r]
    if regimes:
        bullish_count = sum(1 for r in regimes if 'BULLISH' in r)
        bearish_count = sum(1 for r in regimes if 'BEARISH' in r)
        
        if bullish_count > bearish_count:
            print("Market Outlook: BULLISH - Consider increasing exposure")
        elif bearish_count > bullish_count:
            print("Market Outlook: BEARISH - Consider reducing exposure")
        else:
            print("Market Outlook: MIXED - Be selective with positions")
    
    print("\nRecommended Actions:")
    print("-" * 40)
    
    for ticker, result in results.items():
        if 'regime' in result:
            regime = result['regime']
            if regime in ['STRONG_BEARISH', 'CRISIS']:
                print(f"- {ticker}: Consider exiting or reducing position")
            elif regime == 'HIGH_VOLATILITY':
                print(f"- {ticker}: Widen stops, reduce position size")
            elif regime == 'STRONG_BULLISH':
                print(f"- {ticker}: Can increase position size")

if __name__ == "__main__":
    main()