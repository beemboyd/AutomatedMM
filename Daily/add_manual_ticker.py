#!/usr/bin/env python3
"""
Manual ticker addition tool for VSR and Hourly trackers
Allows adding tickers that meet criteria but weren't picked up by scanners
"""

import json
import os
import sys
import pandas as pd
from datetime import datetime
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from user_context_manager import UserContextManager
from kiteconnect import KiteConnect

def add_ticker_to_vsr_tracker(ticker, user='Sai'):
    """Add ticker to VSR tracker persistence file"""
    persistence_file = '/Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence.json'
    
    # Load existing data
    if os.path.exists(persistence_file):
        with open(persistence_file, 'r') as f:
            data = json.load(f)
    else:
        data = {'tickers': {}, 'last_updated': ''}
    
    # Add ticker if not present
    if ticker not in data['tickers']:
        data['tickers'][ticker] = {
            'first_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'score': 100.0,  # Manual entry gets high score
            'hourly_count': 1,
            'status': 'manual_add'
        }
        data['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Save updated data
        with open(persistence_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✓ Added {ticker} to VSR tracker")
        return True
    else:
        print(f"! {ticker} already in VSR tracker")
        return False

def add_ticker_to_hourly_tracker(ticker, user='Sai'):
    """Add ticker to hourly tracker persistence file"""
    persistence_file = '/Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence_hourly_long.json'
    
    # Load existing data
    if os.path.exists(persistence_file):
        with open(persistence_file, 'r') as f:
            data = json.load(f)
    else:
        data = {'tickers': {}, 'last_updated': ''}
    
    # Add ticker if not present
    if ticker not in data['tickers']:
        data['tickers'][ticker] = {
            'first_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'entry_score': 5,  # Manual entry score
            'peak_score': 5,
            'hourly_count': 1,
            'status': 'manual_add'
        }
        data['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Save updated data
        with open(persistence_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✓ Added {ticker} to Hourly tracker")
        return True
    else:
        print(f"! {ticker} already in Hourly tracker")
        return False

def get_ticker_data(ticker, user='Sai'):
    """Get current price data for ticker"""
    try:
        # Initialize Kite
        mgr = UserContextManager()
        context = mgr.load_context(user)
        kite = KiteConnect(api_key=context['api_key'])
        kite.set_access_token(context['access_token'])
        
        # Get quote
        quote = kite.quote(f'NSE:{ticker}')
        if f'NSE:{ticker}' in quote:
            data = quote[f'NSE:{ticker}']
            return {
                'last_price': data['last_price'],
                'change_percent': ((data['last_price'] - data['ohlc']['close']) / data['ohlc']['close']) * 100,
                'volume': data['volume'],
                'open': data['ohlc']['open'],
                'high': data['ohlc']['high'],
                'low': data['ohlc']['low']
            }
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
    return None

def main():
    parser = argparse.ArgumentParser(description='Manually add ticker to VSR and Hourly trackers')
    parser.add_argument('ticker', help='Ticker symbol to add (e.g., APOLLOHOSP)')
    parser.add_argument('--user', default='Sai', help='User for API credentials')
    parser.add_argument('--vsr', action='store_true', help='Add to VSR tracker')
    parser.add_argument('--hourly', action='store_true', help='Add to Hourly tracker')
    parser.add_argument('--both', action='store_true', help='Add to both trackers')
    
    args = parser.parse_args()
    
    ticker = args.ticker.upper()
    
    print(f"\n=== Manual Ticker Addition ===")
    print(f"Ticker: {ticker}")
    print(f"User: {args.user}")
    
    # Get current data
    data = get_ticker_data(ticker, args.user)
    if data:
        print(f"\nCurrent Data:")
        print(f"  Price: ₹{data['last_price']:.2f}")
        print(f"  Change: {data['change_percent']:.2f}%")
        print(f"  Volume: {data['volume']:,}")
    
    # Add to trackers
    if args.both or (args.vsr and args.hourly):
        print(f"\nAdding to both trackers...")
        add_ticker_to_vsr_tracker(ticker, args.user)
        add_ticker_to_hourly_tracker(ticker, args.user)
    elif args.vsr:
        print(f"\nAdding to VSR tracker...")
        add_ticker_to_vsr_tracker(ticker, args.user)
    elif args.hourly:
        print(f"\nAdding to Hourly tracker...")
        add_ticker_to_hourly_tracker(ticker, args.user)
    else:
        print("\nNo tracker specified. Use --vsr, --hourly, or --both")
        return 1
    
    print("\n✓ Manual addition complete")
    print("Note: Dashboards will refresh automatically within 60 seconds")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())