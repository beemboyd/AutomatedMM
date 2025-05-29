#!/usr/bin/env python3

import os
import sys
import configparser
from kiteconnect import KiteConnect

def test_api_credentials():
    """
    Test the API credentials in config.ini to see if they work
    """
    # Get config file path
    config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    
    # Read the current config
    config = configparser.ConfigParser()
    config.read(config_file)
    
    # Get API credentials
    api_key = config.get('API', 'api_key')
    api_secret = config.get('API', 'api_secret')
    access_token = config.get('API', 'access_token')
    
    print(f"Testing Zerodha API credentials from {config_file}")
    print(f"API Key: {api_key}")
    print(f"API Secret: {'*' * len(api_secret)}")
    print(f"Access Token: {access_token[:5]}...{access_token[-5:]}")
    
    # Initialize KiteConnect
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    try:
        # Try to fetch profile to test authentication
        profile = kite.profile()
        print("\nAuthentication successful!")
        print(f"User: {profile['user_name']} ({profile['user_id']})")
        print("The position_watchdog service should work with these credentials.")
        return True
    except Exception as e:
        print(f"\nAuthentication failed: {e}")
        print("\nTo fix this issue:")
        print("1. Run the token update script to get a login URL:")
        print("   python3 utils/update_token.py")
        print("2. Open the URL in your browser and login to Zerodha")
        print("3. Copy the request_token from the redirect URL")
        print("4. Run the update script with the token:")
        print("   python3 utils/update_token.py --request-token=YOUR_REQUEST_TOKEN")
        print("5. Restart the position_watchdog service")
        return False

if __name__ == "__main__":
    test_api_credentials()