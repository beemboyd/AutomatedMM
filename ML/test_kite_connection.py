"""
Quick test to verify Kite API connection
"""

import os
import sys
import configparser
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kiteconnect import KiteConnect

def test_connection(user_name="Sai"):
    """Test Kite API connection"""
    print(f"Testing Kite API connection for user: {user_name}")
    
    # Load config
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Daily', 'config.ini')
    config = configparser.ConfigParser()
    config.read(config_path)
    
    # Get credentials
    credential_section = f'API_CREDENTIALS_{user_name}'
    api_key = config.get(credential_section, 'api_key')
    access_token = config.get(credential_section, 'access_token')
    
    print(f"API Key: {api_key[:10]}...")
    print(f"Access Token: {access_token[:10]}...")
    
    # Initialize Kite
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    try:
        # Test 1: Get profile
        print("\nTest 1: Getting profile...")
        profile = kite.profile()
        print(f"✓ Profile fetched: {profile.get('user_name', 'Unknown')}")
        
        # Test 2: Get positions
        print("\nTest 2: Getting positions...")
        positions = kite.positions()
        print(f"✓ Positions fetched: {len(positions.get('net', []))} net positions")
        
        # Test 3: Get a sample ticker data
        print("\nTest 3: Fetching sample historical data...")
        # Try to get instrument token for RELIANCE
        instruments = kite.instruments("NSE")
        reliance = next((inst for inst in instruments if inst['tradingsymbol'] == 'RELIANCE'), None)
        
        if reliance:
            token = reliance['instrument_token']
            from_date = datetime.now() - timedelta(days=5)
            to_date = datetime.now()
            
            data = kite.historical_data(token, from_date, to_date, "day")
            print(f"✓ Historical data fetched: {len(data)} records for RELIANCE")
            if data:
                print(f"  Latest close: {data[-1]['close']}")
        else:
            print("✗ Could not find RELIANCE in instruments")
            
        print("\n✓ All tests passed! Kite API is working correctly.")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print(f"Error type: {type(e).__name__}")
        
        # Check if it's an authentication error
        if "Invalid" in str(e) or "expired" in str(e).lower():
            print("\nThe access token may have expired. Please update the access token in config.ini")
        

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--user', default='Sai', help='User name')
    args = parser.parse_args()
    
    test_connection(args.user)