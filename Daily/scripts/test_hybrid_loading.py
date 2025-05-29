#!/usr/bin/env python3

import os
import sys
import json
import configparser

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kiteconnect import KiteConnect
from user_context_manager import UserCredentials

def test_hybrid_loading():
    """Test the hybrid loading approach"""
    print("Testing Hybrid Loading Approach")
    print("=" * 50)
    
    # Load config
    config = configparser.ConfigParser()
    config.read('../config.ini')
    
    section = 'API_CREDENTIALS_Sai'
    user_creds = UserCredentials(
        name='Sai',
        api_key=config.get(section, 'api_key'),
        api_secret=config.get(section, 'api_secret'),
        access_token=config.get(section, 'access_token')
    )

    kite = KiteConnect(api_key=user_creds.api_key)
    kite.set_access_token(user_creds.access_token)
    
    tracked_positions = {}
    
    # 1. Load from Holdings API
    print("\n1. Loading from Holdings API...")
    try:
        holdings = kite.holdings()
        holdings_count = 0
        
        for holding in holdings:
            ticker = holding.get('tradingsymbol', '')
            quantity = int(holding.get('quantity', 0))
            
            if quantity > 0 and ticker != '':
                tracked_positions[ticker] = {
                    'source': 'holdings',
                    'quantity': quantity,
                    'entry_price': holding.get('average_price', 0)
                }
                holdings_count += 1
                print(f"  {ticker}: {quantity} shares @ ₹{holding.get('average_price', 0):.2f}")
        
        print(f"Holdings loaded: {holdings_count}")
        
    except Exception as e:
        print(f"Error loading holdings: {e}")
    
    # 2. Load from Orders File
    print("\n2. Loading from Orders File...")
    orders_file = '/Users/maverick/PycharmProjects/India-TS/Daily/Current_Orders/Sai/orders_Sai_20250526_132849.json'
    
    try:
        with open(orders_file, 'r') as f:
            orders_data = json.load(f)
        
        orders = orders_data.get('orders', [])
        orders_count = 0
        
        # Filter for valid orders
        for order in orders:
            ticker = None
            quantity = 0
            entry_price = 0
            
            if order.get('order_success', False):
                # Regular successful order
                ticker = order['ticker']
                quantity = order['position_size']
                entry_price = order['current_price']
            elif (order.get('data_source') == 'server_sync' and 
                  order.get('status') == 'COMPLETE' and 
                  order.get('transaction_type') == 'BUY' and
                  order.get('filled_quantity', 0) > 0):
                # Synced BUY position from server
                ticker = order['tradingsymbol']
                quantity = order['filled_quantity']
                entry_price = order['average_price']
            
            if ticker and quantity > 0:
                if ticker not in tracked_positions:
                    tracked_positions[ticker] = {
                        'source': 'orders_file',
                        'quantity': quantity,
                        'entry_price': entry_price
                    }
                    orders_count += 1
                    print(f"  {ticker}: {quantity} shares @ ₹{entry_price:.2f} (NEW)")
                else:
                    print(f"  {ticker}: {quantity} shares @ ₹{entry_price:.2f} (DUPLICATE - skipped)")
        
        print(f"Orders file additions: {orders_count}")
        
    except Exception as e:
        print(f"Error loading orders file: {e}")
    
    # 3. Summary
    print(f"\n3. Summary")
    print(f"Total unique tickers: {len(tracked_positions)}")
    
    holdings_tickers = [t for t, p in tracked_positions.items() if p['source'] == 'holdings']
    orders_tickers = [t for t, p in tracked_positions.items() if p['source'] == 'orders_file']
    
    print(f"From Holdings API ({len(holdings_tickers)}): {holdings_tickers}")
    print(f"From Orders File ({len(orders_tickers)}): {orders_tickers}")
    
    print(f"\nAll tracked tickers: {sorted(tracked_positions.keys())}")

if __name__ == "__main__":
    test_hybrid_loading()