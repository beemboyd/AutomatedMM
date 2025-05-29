#!/usr/bin/env python3

import os
import sys
import configparser
import json
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kiteconnect import KiteConnect
from user_context_manager import UserCredentials

def load_daily_config():
    """Load configuration from Daily/config.ini file"""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini file not found at {config_path}")
    
    config.read(config_path)
    return config

def get_user_from_config(user_name: str, config):
    """Get user credentials from config"""
    section = f'API_CREDENTIALS_{user_name}'
    if section not in config.sections():
        return None

    api_key = config.get(section, 'api_key', fallback='')
    api_secret = config.get(section, 'api_secret', fallback='')
    access_token = config.get(section, 'access_token', fallback='')

    if not (api_key and api_secret and access_token):
        return None

    return UserCredentials(
        name=user_name,
        api_key=api_key,
        api_secret=api_secret,
        access_token=access_token
    )

def test_cnc_positions(user_name):
    """Test and display CNC positions for a specific user"""
    print(f"=" * 80)
    print(f"Testing CNC Positions for User: {user_name}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"=" * 80)
    
    try:
        # Load config
        config = load_daily_config()
        print(f"✓ Config loaded successfully")
        
        # Get user credentials
        user_credentials = get_user_from_config(user_name, config)
        if not user_credentials:
            print(f"✗ Could not find credentials for user: {user_name}")
            print("Available users in config:")
            for section in config.sections():
                if section.startswith('API_CREDENTIALS_'):
                    user = section.replace('API_CREDENTIALS_', '')
                    print(f"  - {user}")
            return False
        
        print(f"✓ Found credentials for user: {user_name}")
        
        # Initialize KiteConnect
        kite = KiteConnect(api_key=user_credentials.api_key)
        kite.set_access_token(user_credentials.access_token)
        print(f"✓ KiteConnect initialized")
        
        # Test connection and get profile
        try:
            profile = kite.profile()
            print(f"✓ Connected to Zerodha account:")
            print(f"  User Name: {profile['user_name']}")
            print(f"  User ID: {profile['user_id']}")
            print(f"  Email: {profile['email']}")
            print(f"  Broker: {profile['broker']}")
        except Exception as e:
            print(f"✗ Failed to get profile: {e}")
            return False
        
        print(f"\n" + "-" * 60)
        print(f"FETCHING POSITIONS...")
        print(f"-" * 60)
        
        # Get all positions
        positions = kite.positions()
        
        print(f"Raw position data:")
        print(f"  Net positions: {len(positions.get('net', []))}")
        print(f"  Day positions: {len(positions.get('day', []))}")
        
        # Analyze all positions
        all_positions = []
        cnc_positions = []
        
        for position in positions['net']:
            ticker = position.get('tradingsymbol', '')
            product = position.get('product', '')
            quantity = int(position.get('quantity', 0))
            avg_price = float(position.get('average_price', 0))
            last_price = float(position.get('last_price', 0))
            pnl = float(position.get('pnl', 0))
            
            all_positions.append({
                'ticker': ticker,
                'product': product,
                'quantity': quantity,
                'avg_price': avg_price,
                'last_price': last_price,
                'pnl': pnl
            })
            
            if product == 'CNC' and quantity != 0:
                cnc_positions.append({
                    'ticker': ticker,
                    'quantity': quantity,
                    'avg_price': avg_price,
                    'last_price': last_price,
                    'pnl': pnl,
                    'investment': avg_price * abs(quantity)
                })
        
        print(f"\n" + "=" * 60)
        print(f"ALL POSITIONS IN ACCOUNT ({len(all_positions)})")
        print(f"=" * 60)
        
        if all_positions:
            print(f"{'Ticker':<15} {'Product':<8} {'Qty':<8} {'Avg Price':<12} {'PnL':<12}")
            print(f"-" * 60)
            for pos in all_positions[:20]:  # Show first 20
                print(f"{pos['ticker']:<15} {pos['product']:<8} {pos['quantity']:<8} ₹{pos['avg_price']:<11.2f} ₹{pos['pnl']:<11.2f}")
            if len(all_positions) > 20:
                print(f"... and {len(all_positions) - 20} more positions")
        else:
            print("No positions found in account")
        
        print(f"\n" + "=" * 60)
        print(f"CNC POSITIONS ONLY ({len(cnc_positions)})")
        print(f"=" * 60)
        
        if cnc_positions:
            total_investment = 0
            total_pnl = 0
            
            print(f"{'Ticker':<15} {'Qty':<8} {'Avg Price':<12} {'Investment':<15} {'PnL':<12}")
            print(f"-" * 70)
            
            for pos in cnc_positions:
                print(f"{pos['ticker']:<15} {pos['quantity']:<8} ₹{pos['avg_price']:<11.2f} ₹{pos['investment']:<14.2f} ₹{pos['pnl']:<11.2f}")
                total_investment += pos['investment']
                total_pnl += pos['pnl']
            
            print(f"-" * 70)
            print(f"{'TOTAL':<15} {'':<8} {'':<12} ₹{total_investment:<14.2f} ₹{total_pnl:<11.2f}")
            
            print(f"\nCNC Tickers: {', '.join([pos['ticker'] for pos in cnc_positions])}")
        else:
            print("✓ No CNC positions found in account")
            print("This could mean:")
            print("  - All positions are MIS (intraday)")
            print("  - All positions have been closed")
            print("  - Account has no current holdings")
        
        # Also check day positions for context
        day_cnc = []
        for position in positions['day']:
            if position.get('product') == 'CNC' and int(position.get('quantity', 0)) != 0:
                day_cnc.append(position['tradingsymbol'])
        
        if day_cnc:
            print(f"\nDay CNC positions (today's trades): {', '.join(day_cnc)}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing CNC positions: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 test_cnc_positions.py <user_name>")
        print("Example: python3 test_cnc_positions.py Sai")
        sys.exit(1)
    
    user_name = sys.argv[1]
    success = test_cnc_positions(user_name)
    
    if success:
        print(f"\n✓ Test completed successfully for user: {user_name}")
    else:
        print(f"\n✗ Test failed for user: {user_name}")
        sys.exit(1)

if __name__ == "__main__":
    main()