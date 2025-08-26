#!/usr/bin/env python3
"""Analyze all positions including T+1 and options using ICT concepts"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from portfolio.SL_Watch_ICT import ICTAnalyzer
from kiteconnect import KiteConnect
from scanners.VSR_Momentum_Scanner import load_daily_config

def analyze_all_positions():
    """Analyze all positions including APOLLOHOSP and PAYTM options"""
    
    # Initialize
    config = load_daily_config('Sai')
    api_key = config.get('API_CREDENTIALS_Sai', 'api_key')
    access_token = config.get('API_CREDENTIALS_Sai', 'access_token')
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    analyzer = ICTAnalyzer(user_name='Sai')
    
    # Analyze APOLLOHOSP from holdings
    print("="*80)
    print("ICT ANALYSIS FOR APOLLOHOSP (HOLDINGS)")
    print("="*80)
    
    apollo_position = {
        'ticker': 'APOLLOHOSP',
        'quantity': 500,
        'average_price': 7800.50,
        'last_price': 7822.50,
        'pnl': 11000.00,
        'pnl_percent': (11000.00 / (7800.50 * 500)) * 100
    }
    
    print(f"\nPosition Details:")
    print(f"  Entry: ₹{apollo_position['average_price']:.2f}")
    print(f"  Current: ₹{apollo_position['last_price']:.2f}")
    print(f"  P&L: ₹{apollo_position['pnl']:.2f} ({apollo_position['pnl_percent']:.2f}%)")
    
    try:
        hourly = analyzer.analyze_position(apollo_position, 'hourly')
        daily = analyzer.analyze_position(apollo_position, 'daily')
        
        if hourly and daily:
            print(f"\nICT Analysis Results:")
            print(f"  Hourly Structure: {hourly.market_structure.value}")
            print(f"  Daily Structure: {daily.market_structure.value}")
            print(f"  Hourly SL: ₹{hourly.optimal_sl:.2f}")
            print(f"  Daily SL: ₹{daily.optimal_sl:.2f}")
            print(f"  Conservative SL: ₹{min(hourly.optimal_sl, daily.optimal_sl):.2f}")
            print(f"\nKey Levels:")
            
            # Show nearest support levels
            support_levels = [l for l in hourly.key_levels if l.price < hourly.current_price]
            support_levels.sort(key=lambda x: x.price, reverse=True)
            for level in support_levels[:3]:
                print(f"  {level.level_type}: ₹{level.price:.2f}")
    except Exception as e:
        print(f"Error analyzing APOLLOHOSP: {e}")
    
    # Analyze PAYTM spot for options reference
    print("\n" + "="*80)
    print("PAYTM SPOT ANALYSIS (For Options Position Reference)")
    print("="*80)
    
    print("\nYour Options Position: PAYTM25AUG1140CE")
    print("  Quantity: 1450")
    print("  Average: ₹23.00")
    print("  Current: ₹48.20")
    print("  P&L: ₹36,540.00")
    print("  Strike: 1140 CE")
    
    # Get PAYTM spot price
    try:
        ltp = kite.ltp(['NSE:PAYTM'])
        paytm_spot = ltp['NSE:PAYTM']['last_price']
        print(f"\nPAYTM Spot Price: ₹{paytm_spot:.2f}")
        print(f"Distance from Strike: ₹{paytm_spot - 1140:.2f} ({((paytm_spot - 1140)/1140*100):.2f}% ITM)")
        
        # Analyze PAYTM spot
        paytm_position = {
            'ticker': 'PAYTM',
            'quantity': 1,
            'average_price': 1140,  # Using strike as reference
            'last_price': paytm_spot,
            'pnl': 0,
            'pnl_percent': 0
        }
        
        hourly = analyzer.analyze_position(paytm_position, 'hourly')
        if hourly:
            print(f"\nPAYTM Spot ICT Analysis:")
            print(f"  Market Structure: {hourly.market_structure.value}")
            print(f"  Trend Strength: {hourly.trend_strength:.1f}%")
            
            # Find key support levels near strike
            print(f"\nKey Levels Around Strike (1140):")
            for level in hourly.key_levels:
                if 1100 <= level.price <= 1180:
                    print(f"  {level.level_type}: ₹{level.price:.2f}")
            
            print(f"\nOptions Strategy Recommendation:")
            if hourly.market_structure.value in ['Bullish Trending', 'Bullish Pullback']:
                print("  ✓ Hold CE position - Bullish structure intact")
                print(f"  Consider booking partial profits if PAYTM crosses ₹1180")
            elif 'Correction' in hourly.market_structure.value:
                print("  ⚠ Monitor closely - In correction phase")
                print("  Consider booking profits or hedging")
            else:
                print("  Consider position based on risk appetite")
                
    except Exception as e:
        print(f"Error analyzing PAYTM: {e}")
    
    # Summary of all T+1 positions
    print("\n" + "="*80)
    print("T+1 POSITIONS SUMMARY")
    print("="*80)
    
    positions = kite.positions()
    for pos in positions.get('day', []):
        if pos['quantity'] != 0 and pos['product'] == 'CNC':
            print(f"\n{pos['tradingsymbol']}:")
            print(f"  Qty: {pos['quantity']} | Avg: ₹{pos['average_price']:.2f}")
            print(f"  LTP: ₹{pos['last_price']:.2f} | P&L: ₹{pos['pnl']:.2f}")

if __name__ == "__main__":
    analyze_all_positions()