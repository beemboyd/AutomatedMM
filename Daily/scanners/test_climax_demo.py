#!/usr/bin/env python
"""Quick demo of VSR scanner with climax detection"""

import os
import sys
import pandas as pd

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.scanners.VSR_Momentum_Scanner import process_ticker

# Test with a few tickers known to have good activity
test_tickers = ["RELIANCE", "TCS", "INFY", "HDFC", "ICICIBANK"]

print("Testing VSR Scanner with Climax Detection")
print("=" * 50)

results = []
for ticker in test_tickers:
    print(f"\nProcessing {ticker}...")
    result = process_ticker(ticker)
    if result:
        results.append(result)
        print(f"  ✓ Pattern: {result['Pattern']}")
        print(f"  ✓ Probability: {result['Probability_Score']:.1f}")
        print(f"  ✓ VSR Ratio: {result['VSR_Ratio']:.2f}")
        print(f"  ✓ Climax Score: {result['Climax_Score']}")
        
        # Check for climax events
        if result.get('Buying_Climax_10H', 0) > 0:
            print(f"  ⚠️ BUYING CLIMAX detected: {result['Buying_Climax_10H']} events")
        if result.get('Selling_Climax_10H', 0) > 0:
            print(f"  ⚠️ SELLING CLIMAX detected: {result['Selling_Climax_10H']} events")
        if result.get('Has_Pos_Divergence', False):
            print(f"  ↗️ POSITIVE DIVERGENCE detected")
        if result.get('Has_Neg_Divergence', False):
            print(f"  ↘️ NEGATIVE DIVERGENCE detected")
    else:
        print(f"  - No pattern detected")

print("\n" + "=" * 50)
print(f"Summary: {len(results)} patterns found out of {len(test_tickers)} tickers tested")

# Display results in DataFrame format
if results:
    df = pd.DataFrame(results)
    print("\nDetailed Results:")
    print(df[['Ticker', 'Pattern', 'Probability_Score', 'VSR_Ratio', 'Climax_Score', 
              'Buying_Climax_10H', 'Selling_Climax_10H', 'Has_Pos_Divergence', 'Has_Neg_Divergence']].to_string())