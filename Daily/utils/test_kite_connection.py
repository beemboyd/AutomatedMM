#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scanners.VSR_Momentum_Scanner import load_daily_config
from kiteconnect import KiteConnect

try:
    config = load_daily_config('Sai')
    api_key = config.get('API_CREDENTIALS_Sai', 'api_key')
    access_token = config.get('API_CREDENTIALS_Sai', 'access_token')
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    profile = kite.profile()
    print(f"Connected as: {profile.get('user_name', 'Unknown')}")
    sys.exit(0)
except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)
