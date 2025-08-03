#!/usr/bin/env python3
"""Test script to check SMA data fetching"""

import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kiteconnect import KiteConnect
import configparser

def load_config():
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Daily', 'config.ini')
    config.read(config_path)
    return config

def main():
    # Load config
    config = load_config()
    
    # Get Mom's credentials
    section = 'API_CREDENTIALS_Mom'
    api_key = config.get(section, 'api_key')
    access_token = config.get(section, 'access_token')
    
    # Initialize Kite
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    # Test with a single ticker
    ticker = "CONCORDBIO"
    exchange = "NSE"
    
    try:
        # Get instrument token
        instruments = kite.instruments(exchange)
        instrument_token = None
        
        for inst in instruments:
            if inst['tradingsymbol'] == ticker:
                instrument_token = inst['instrument_token']
                break
        
        if instrument_token:
            print(f"Found instrument token for {ticker}: {instrument_token}")
            
            # Get historical data
            to_date = datetime.now()
            from_date = to_date - timedelta(days=5)  # Get 5 days of data
            
            print(f"\nFetching hourly data from {from_date} to {to_date}")
            
            candles = kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval="60minute"
            )
            
            print(f"\nGot {len(candles)} hourly candles")
            
            if candles:
                print("\nLast 5 candles:")
                for candle in candles[-5:]:
                    print(f"  {candle['date']}: Close={candle['close']}")
                
                # Calculate 20 SMA
                if len(candles) >= 20:
                    closes = [float(c['close']) for c in candles[-20:]]
                    sma_20 = sum(closes) / 20
                    current_price = candles[-1]['close']
                    
                    print(f"\n20 SMA: {sma_20:.2f}")
                    print(f"Last Close: {current_price:.2f}")
                    print(f"Status: {'Above' if current_price >= sma_20 else 'Below'} SMA")
                else:
                    print(f"\nNot enough data for 20 SMA (need 20, have {len(candles)})")
        else:
            print(f"Could not find instrument token for {ticker}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()