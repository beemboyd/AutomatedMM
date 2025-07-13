#!/usr/bin/env python3
"""
Test volatility integration with scanner data
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime
from Market_Regime.core.volatility_scorer import calculate_volatility_score_from_scanner
from Market_Regime.core.regime_detector import RegimeDetector
import json

# Create sample scanner data
def create_sample_scanner_data():
    """Create sample scanner data for testing"""
    np.random.seed(42)
    
    tickers = ['TCS', 'INFY', 'RELIANCE', 'HDFC', 'ICICIBANK', 
               'WIPRO', 'HCLTECH', 'BAJFINANCE', 'MARUTI', 'TITAN',
               'ASIANPAINT', 'ULTRACEMCO', 'LT', 'AXISBANK', 'SBIN']
    
    data = []
    for ticker in tickers:
        price = np.random.uniform(500, 3000)
        atr = price * np.random.uniform(0.01, 0.04)  # 1-4% ATR
        
        data.append({
            'Ticker': ticker,
            'Entry_Price': price,
            'ATR': atr,
            'Volume_Ratio': np.random.uniform(0.5, 2.5),
            'Direction': np.random.choice(['LONG', 'SHORT']),
            'Risk': atr * 1.5,
            'Score': np.random.uniform(60, 90),
            'Momentum_5D': np.random.uniform(-10, 15),
            'Sector': np.random.choice(['IT', 'FINANCE', 'AUTO', 'CEMENT', 'PAINT'])
        })
    
    return pd.DataFrame(data)

# Test volatility analysis
print("Testing volatility integration...")
print("-" * 50)

# Create scanner data
scanner_df = create_sample_scanner_data()
print(f"Created scanner data with {len(scanner_df)} tickers")
print("\nSample data:")
print(scanner_df.head())

# Calculate volatility analysis
print("\nCalculating volatility analysis...")
volatility_analysis = calculate_volatility_score_from_scanner(scanner_df)

# Display results
print("\nMarket Volatility Metrics:")
market_vol = volatility_analysis['market_volatility']
for key, value in market_vol.items():
    if key != 'timestamp':
        print(f"  {key}: {value}")

print("\nSector Volatility:")
sector_vol = volatility_analysis['sector_volatility']
for sector, metrics in sector_vol.items():
    print(f"  {sector}: Score={metrics['volatility_score']:.1f}, Regime={metrics['volatility_regime']}")

print("\nInsights:")
for insight in volatility_analysis['insights']:
    print(f"  {insight}")

# Test integration with regime detector
print("\n" + "-" * 50)
print("Testing regime detector integration...")

# Load sample market data
market_data_path = "/Users/maverick/PycharmProjects/India-TS/Market_Regime/data/nifty_data.csv"
if os.path.exists(market_data_path):
    market_data = pd.read_csv(market_data_path)
    
    # Initialize regime detector
    detector = RegimeDetector()
    
    # Detect regime with scanner data
    regime_analysis = detector.detect_regime(market_data, scanner_df)
    
    print(f"\nRegime: {regime_analysis['regime']}")
    print(f"Confidence: {regime_analysis['confidence']:.2%}")
    
    # Check for scanner-based volatility indicators
    indicators = regime_analysis['indicators']
    scanner_vol_indicators = {k: v for k, v in indicators.items() if 'scanner' in k}
    
    if scanner_vol_indicators:
        print("\nScanner-based volatility indicators:")
        for key, value in scanner_vol_indicators.items():
            print(f"  {key}: {value}")
    else:
        print("\nNo scanner-based volatility indicators found in regime analysis")
else:
    print(f"Market data file not found: {market_data_path}")

print("\nTest complete!")