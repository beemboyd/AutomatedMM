#!/usr/bin/env python3

import os
import sys
import argparse
import configparser
from kiteconnect import KiteConnect

def update_access_token(request_token=None):
    """
    Update the access token in the config.ini file
    
    If request_token is provided, generate a new access token.
    Otherwise, just print the login URL to get a request token.
    """
    # Get config file path
    config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    
    # Read the current config
    config = configparser.ConfigParser()
    config.read(config_file)
    
    # Get API credentials
    api_key = config.get('API', 'api_key')
    api_secret = config.get('API', 'api_secret')
    
    # Initialize KiteConnect
    kite = KiteConnect(api_key=api_key)
    
    if not request_token:
        # Just print the login URL
        print(f"Login URL: {kite.login_url()}")
        print("\nOpen this URL in your browser.")
        print("After logging in, you'll be redirected to a URL with request_token parameter.")
        print("Run this script again with the request token to generate a new access token:")
        print(f"python3 {sys.argv[0]} --request-token=YOUR_REQUEST_TOKEN")
        return
    
    try:
        # Generate session and get access token
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        
        # Update config with new access token
        config.set('API', 'access_token', access_token)
        
        # Save updated config
        with open(config_file, 'w') as f:
            config.write(f)
        
        print(f"Access token updated successfully: {access_token}")
        print("The position_watchdog service should now work correctly.")
        print("You may need to restart the service with:")
        print("launchctl unload ~/Library/LaunchAgents/com.indiaTS.position_watchdog.plist")
        print("launchctl load ~/Library/LaunchAgents/com.indiaTS.position_watchdog.plist")
        
    except Exception as e:
        print(f"Error generating access token: {e}")
        return False
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Update Zerodha access token in config.ini')
    parser.add_argument('--request-token', help='Request token from Zerodha login redirect')
    args = parser.parse_args()
    
    update_access_token(args.request_token)

if __name__ == "__main__":
    main()