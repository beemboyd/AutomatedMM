#!/usr/bin/env python3
"""Check all positions including CNC, MIS, and T1 holdings"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kiteconnect import KiteConnect
from scanners.VSR_Momentum_Scanner import load_daily_config

def check_all_positions():
    # Load credentials
    config = load_daily_config('Sai')
    api_key = config.get('API_CREDENTIALS_Sai', 'api_key')
    access_token = config.get('API_CREDENTIALS_Sai', 'access_token')
    
    # Connect to Kite
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    # Get positions
    positions = kite.positions()
    
    # Get holdings (includes T1 quantities)
    holdings = kite.holdings()
    
    print("="*80)
    print("COMPLETE PORTFOLIO ANALYSIS")
    print("="*80)
    
    # Check net positions
    print("\n=== NET POSITIONS (All Products) ===")
    all_positions = {}
    
    for pos in positions.get('net', []):
        if pos['quantity'] != 0:
            ticker = pos['tradingsymbol']
            all_positions[ticker] = {
                'quantity': pos['quantity'],
                'product': pos['product'],
                'avg_price': pos['average_price'],
                'ltp': pos['last_price'],
                'pnl': pos['pnl']
            }
            print(f"{ticker:15} | Qty: {pos['quantity']:6} | Product: {pos['product']:4} | "
                  f"Avg: ₹{pos['average_price']:8.2f} | LTP: ₹{pos['last_price']:8.2f} | "
                  f"P&L: ₹{pos['pnl']:8.2f}")
    
    # Check holdings (includes T1)
    print("\n=== HOLDINGS (Including T1) ===")
    for holding in holdings:
        ticker = holding['tradingsymbol']
        t1_qty = holding.get('t1_quantity', 0)
        total_qty = holding['quantity']
        
        if total_qty > 0 or t1_qty > 0:
            print(f"{ticker:15} | Total Qty: {total_qty:6} | T1 Qty: {t1_qty:6} | "
                  f"Avg: ₹{holding['average_price']:8.2f} | LTP: ₹{holding['last_price']:8.2f} | "
                  f"P&L: ₹{holding['pnl']:8.2f}")
    
    # Separate by product type
    print("\n=== BREAKDOWN BY PRODUCT TYPE ===")
    
    cnc_positions = [ticker for ticker, data in all_positions.items() if data['product'] == 'CNC']
    mis_positions = [ticker for ticker, data in all_positions.items() if data['product'] == 'MIS']
    
    print(f"\nCNC Positions ({len(cnc_positions)}):")
    for ticker in cnc_positions:
        data = all_positions[ticker]
        print(f"  - {ticker}: Qty={data['quantity']}, Avg=₹{data['avg_price']:.2f}")
    
    print(f"\nMIS Positions ({len(mis_positions)}):")
    for ticker in mis_positions:
        data = all_positions[ticker]
        print(f"  - {ticker}: Qty={data['quantity']}, Avg=₹{data['avg_price']:.2f}")
    
    # Check for specific tickers mentioned
    print("\n=== CHECKING FOR SPECIFIC TICKERS ===")
    check_tickers = ['APOLLOHOSP', 'APOLLO', 'PAYTM', 'BOSCHLTD', 'PNBHOUSING']
    
    for ticker in check_tickers:
        found = False
        
        # Check in positions
        if ticker in all_positions:
            data = all_positions[ticker]
            print(f"{ticker}: Found in positions - Product={data['product']}, Qty={data['quantity']}")
            found = True
        
        # Check in holdings
        for holding in holdings:
            if holding['tradingsymbol'] == ticker and holding['quantity'] > 0:
                print(f"{ticker}: Found in holdings - Qty={holding['quantity']}, T1={holding.get('t1_quantity', 0)}")
                found = True
                break
        
        if not found:
            print(f"{ticker}: NOT FOUND in current positions or holdings")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    check_all_positions()