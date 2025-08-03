#!/usr/bin/env python3
"""
Quick check of ABFRL Keltner Channel values
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

def check_abfrl():
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
    
    # Fetch daily data for 2 years
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
    monthly_df['volume'] = df['volume'].resample('ME').sum()
    
    monthly_df.dropna(inplace=True)
    monthly_df.reset_index(inplace=True)
    
    # Calculate Keltner Channels
    kc_period = 20
    kc_multiplier = 2.0
    
    # Calculate True Range
    monthly_df['TR'] = pd.concat([
        monthly_df['high'] - monthly_df['low'],
        (monthly_df['high'] - monthly_df['close'].shift(1)).abs(),
        (monthly_df['low'] - monthly_df['close'].shift(1)).abs()
    ], axis=1).max(axis=1)
    
    # Calculate ATR
    monthly_df['ATR'] = monthly_df['TR'].rolling(window=kc_period).mean()
    
    # Calculate EMA of close
    monthly_df['EMA'] = monthly_df['close'].ewm(span=kc_period, adjust=False).mean()
    
    # Calculate Keltner Channels
    monthly_df['KC_Upper'] = monthly_df['EMA'] + (kc_multiplier * monthly_df['ATR'])
    monthly_df['KC_Lower'] = monthly_df['EMA'] - (kc_multiplier * monthly_df['ATR'])
    
    # Print last 5 months
    print("\nABFRL Monthly Data with Keltner Channels:")
    print("=" * 100)
    print(f"{'Date':<12} {'Open':>8} {'High':>8} {'Low':>8} {'Close':>8} {'EMA':>8} {'ATR':>8} {'KC_Upper':>10} {'KC_Lower':>10}")
    print("-" * 100)
    
    for _, row in monthly_df.tail(5).iterrows():
        print(f"{row['date'].strftime('%Y-%m-%d'):<12} "
              f"{row['open']:>8.2f} {row['high']:>8.2f} {row['low']:>8.2f} {row['close']:>8.2f} "
              f"{row['EMA']:>8.2f} {row['ATR']:>8.2f} {row['KC_Upper']:>10.2f} {row['KC_Lower']:>10.2f}")
    
    # Check August 2025 specifically
    august_data = monthly_df[monthly_df['date'].dt.month == 8]
    if not august_data.empty:
        latest = august_data.iloc[-1]
        print(f"\nAugust 2025 Analysis:")
        print(f"Current Price: {latest['close']:.2f}")
        print(f"KC Lower: {latest['KC_Lower']:.2f}")
        print(f"Low touched: {latest['low']:.2f}")
        print(f"Touched Lower KC: {latest['low'] <= latest['KC_Lower']}")
        print(f"Crossed Lower KC: {latest['close'] < latest['KC_Lower']}")

if __name__ == "__main__":
    check_abfrl()