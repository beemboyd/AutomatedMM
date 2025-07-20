#!/usr/bin/env python3
"""Test script to verify score filtering logic"""

import pandas as pd
import os
import sys

# Add parent directory to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import the function we want to test
from Daily.trading.place_orders_daily import get_top_stocks, get_latest_brooks_file

def test_score_filtering():
    """Test the score filtering functionality"""
    
    # Find the latest Long Reversal Daily file
    brooks_file = get_latest_brooks_file()
    if not brooks_file:
        print("No Long Reversal Daily file found!")
        return
    
    print(f"Testing with file: {os.path.basename(brooks_file)}")
    
    # Read the file to see original data
    df = pd.read_excel(brooks_file)
    print(f"\nTotal stocks in file: {len(df)}")
    
    # Show score distribution
    if 'Score' in df.columns:
        print("\nScore distribution:")
        print(df['Score'].value_counts().sort_index())
        
        # Count stocks with score >= 5/7
        def parse_score(score_str):
            try:
                if pd.isna(score_str) or score_str == '':
                    return 0
                if isinstance(score_str, str) and '/' in score_str:
                    numerator = int(score_str.split('/')[0])
                    return numerator
                return 0
            except:
                return 0
        
        df['score_value'] = df['Score'].apply(parse_score)
        eligible_count = len(df[df['score_value'] >= 5])
        print(f"\nStocks with score >= 5/7: {eligible_count}")
    
    # Test get_top_stocks function with different target_positions
    print("\n" + "="*60)
    print("Testing get_top_stocks function:")
    print("="*60)
    
    for target in [5, 10, 15, 20]:
        stocks, _ = get_top_stocks(brooks_file, target, None, None)
        print(f"\nRequested {target} positions -> Got {len(stocks)} stocks")
        
        if stocks:
            print("Selected tickers:")
            for i, stock in enumerate(stocks[:5], 1):  # Show first 5
                print(f"  {i}. {stock['ticker']}")
            if len(stocks) > 5:
                print(f"  ... and {len(stocks) - 5} more")

if __name__ == "__main__":
    test_score_filtering()