#!/usr/bin/env python3
"""
Check ABFRL Keltner Channel with different parameters
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import configparser

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kiteconnect import KiteConnect

def check_abfrl_variations():
    # Setup paths
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Load config
    config_path = os.path.join(base_dir, 'Daily', 'config.ini')
    config = configparser.ConfigParser()
    config.read(config_path)
    
    # Get API credentials
    api_key = config.get('API_CREDENTIALS_Sai', 'api_key')
    access_token = config.get('API_CREDENTIALS_Sai', 'access_token')
    
    # Initialize Kite
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    # Get instrument token for ABFRL
    instruments = kite.instruments("NSE")
    instrument_token = None
    for instrument in instruments:
        if instrument['tradingsymbol'] == 'ABFRL':
            instrument_token = instrument['instrument_token']
            break
    
    if not instrument_token:
        print("ABFRL not found")
        return
    
    # Fetch daily data
    to_date = datetime.now()
    from_date = to_date - timedelta(days=730)
    
    historical_data = kite.historical_data(
        instrument_token,
        from_date,
        to_date,
        interval='day'
    )
    
    # Convert to DataFrame
    df = pd.DataFrame(historical_data)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    
    # Resample to monthly
    monthly_df = pd.DataFrame()
    monthly_df['open'] = df['open'].resample('ME').first()
    monthly_df['high'] = df['high'].resample('ME').max()
    monthly_df['low'] = df['low'].resample('ME').min()
    monthly_df['close'] = df['close'].resample('ME').last()
    
    monthly_df.dropna(inplace=True)
    monthly_df.reset_index(inplace=True)
    
    # Test different parameters
    print("\nTesting different Keltner Channel parameters for ABFRL (August 2025):")
    print("=" * 80)
    
    periods = [10, 15, 20, 25, 30]
    multipliers = [1.0, 1.5, 2.0, 2.5, 3.0]
    
    for period in periods:
        # Calculate True Range
        monthly_df['TR'] = pd.concat([
            monthly_df['high'] - monthly_df['low'],
            (monthly_df['high'] - monthly_df['close'].shift(1)).abs(),
            (monthly_df['low'] - monthly_df['close'].shift(1)).abs()
        ], axis=1).max(axis=1)
        
        # Calculate ATR
        monthly_df[f'ATR_{period}'] = monthly_df['TR'].rolling(window=period).mean()
        
        # Calculate EMA
        monthly_df[f'EMA_{period}'] = monthly_df['close'].ewm(span=period, adjust=False).mean()
        
        # Get August data
        august_idx = len(monthly_df) - 1  # Last row should be August
        august_data = monthly_df.iloc[august_idx]
        
        print(f"\nPeriod = {period}:")
        print(f"EMA: {august_data[f'EMA_{period}']:.2f}, ATR: {august_data[f'ATR_{period}']:.2f}")
        print(f"{'Multiplier':<12} {'KC_Lower':<10} {'Match 59.67?':<15}")
        print("-" * 40)
        
        for mult in multipliers:
            kc_lower = august_data[f'EMA_{period}'] - (mult * august_data[f'ATR_{period}'])
            is_match = abs(kc_lower - 59.67) < 1.0
            print(f"{mult:<12.1f} {kc_lower:<10.2f} {'YES!' if is_match else '':<15}")
    
    # Also check using SMA instead of EMA
    print("\n\nUsing SMA instead of EMA (Period=20):")
    print("=" * 50)
    monthly_df['SMA_20'] = monthly_df['close'].rolling(window=20).mean()
    august_data = monthly_df.iloc[-1]
    
    print(f"SMA: {august_data['SMA_20']:.2f}, ATR: {august_data['ATR_20']:.2f}")
    print(f"{'Multiplier':<12} {'KC_Lower':<10} {'Match 59.67?':<15}")
    print("-" * 40)
    
    for mult in multipliers:
        kc_lower = august_data['SMA_20'] - (mult * august_data['ATR_20'])
        is_match = abs(kc_lower - 59.67) < 1.0
        print(f"{mult:<12.1f} {kc_lower:<10.2f} {'YES!' if is_match else '':<15}")

if __name__ == "__main__":
    check_abfrl_variations()