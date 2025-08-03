#!/usr/bin/env python3
"""Debug performance calculation"""

import pandas as pd
import sys
import os
from datetime import datetime, timedelta
import configparser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from kiteconnect import KiteConnect

# Initialize Kite
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
config_path = os.path.join(base_dir, 'Daily', 'config.ini')
config = configparser.ConfigParser()
config.read(config_path)

api_key = config.get('API_CREDENTIALS_Sai', 'api_key')
access_token = config.get('API_CREDENTIALS_Sai', 'access_token')

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

# Test with one ticker
ticker = "BSE"
instrument_token = None

instruments = kite.instruments("NSE")
for instrument in instruments:
    if instrument['tradingsymbol'] == ticker:
        instrument_token = instrument['instrument_token']
        break

if not instrument_token:
    instruments = kite.instruments("BSE")
    for instrument in instruments:
        if instrument['tradingsymbol'] == ticker:
            instrument_token = instrument['instrument_token']
            break

print(f"Ticker: {ticker}, Token: {instrument_token}")

# Fetch data from July 30 to Aug 2
from_date = datetime(2025, 7, 30)
to_date = datetime(2025, 8, 2)

historical_data = kite.historical_data(
    instrument_token,
    from_date,
    to_date,
    interval='day'
)

print("\nData fetched:")
for data in historical_data:
    print(f"{data['date']}: Open={data['open']}, High={data['high']}, Low={data['low']}, Close={data['close']}")

# Calculate performance if shorted on July 30
if len(historical_data) >= 2:
    entry = historical_data[0]
    exit = historical_data[-1]
    
    entry_price = entry['close']
    exit_price = exit['close']
    
    # For short: profit when price goes down
    pnl_percent = ((entry_price - exit_price) / entry_price) * 100
    
    print(f"\nShort Performance:")
    print(f"Entry (July 30): {entry_price}")
    print(f"Exit (Aug 2): {exit_price}")
    print(f"PnL%: {pnl_percent:.2f}%")