#!/usr/bin/env python
"""Quick test of Long_Reversal_Pivot scanner with a small subset of tickers"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Long_Reversal_Pivot import *

def test_scanner():
    """Test the scanner with a small subset of tickers"""
    # Override the ticker list with just a few tickers for testing
    test_tickers = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']
    
    results = []
    logger.info(f"Testing ChoCh pivot breakout scan for {len(test_tickers)} tickers")
    
    for ticker in test_tickers:
        try:
            # Get historical data
            df = get_historical_data(ticker, interval='1d', days=100)
            
            if df is None or df.empty:
                logger.warning(f"No data for {ticker}")
                continue
            
            # Detect ChoCh breakout pattern
            pattern = detect_choch_breakout(df)
            
            if pattern:
                # Get sector information
                sector = get_sector_for_ticker(ticker)
                
                # Add ticker and sector to pattern
                pattern['ticker'] = ticker
                pattern['sector'] = sector
                pattern['scan_time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                results.append(pattern)
                logger.info(f"Found ChoCh breakout for {ticker}: {pattern['description']}")
            else:
                logger.info(f"No breakout found for {ticker}")
                
        except Exception as e:
            logger.error(f"Error scanning {ticker}: {e}")
            continue
    
    return results

if __name__ == "__main__":
    try:
        logger.info("=" * 60)
        logger.info("Testing Long Reversal Pivot Scanner")
        logger.info("=" * 60)
        
        # Run the test
        results = test_scanner()
        
        if results:
            print("\n" + "=" * 80)
            print("TEST RESULTS - CHOCH BREAKOUTS FOUND")
            print("=" * 80)
            for result in results:
                print(f"\n{result['ticker']} ({result['sector']})")
                print(f"  Pattern: {result['pattern']} | Strength: {result['strength']}")
                print(f"  ▪ Pivot High: ₹{result['pivot_high']:.2f} on {result['pivot_date']} ({result['bars_since_pivot']} bars ago)")
                print(f"  ▪ Breakout: ₹{result['breakout_price']:.2f} on {result['breakout_date']} ({result['bars_since_breakout']} bars ago)")
                print(f"  ▪ Current Price: ₹{result['current_price']:.2f}")
                print(f"  ▪ Support Level: ₹{result['support_level']:.2f} | Stop Loss: ₹{result['stop_loss']:.2f}")
                print(f"  ▪ Momentum: {result['momentum']:.2f}% | Breakout Strength: {result['breakout_strength']:.2f}%")
        else:
            print("\nNo ChoCh breakouts found in test tickers")
        
        print("\nTest complete!")
        
    except Exception as e:
        logger.error(f"Error in test execution: {e}")
        raise