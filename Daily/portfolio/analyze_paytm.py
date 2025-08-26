#!/usr/bin/env python3
"""Quick script to analyze PAYTM position using ICT concepts"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from portfolio.SL_Watch_ICT import ICTAnalyzer

def analyze_paytm():
    """Analyze PAYTM or any ticker containing PAYTM"""
    analyzer = ICTAnalyzer(user_name='Sai')
    positions = analyzer.get_cnc_positions()
    
    # Check for PAYTM or ONE97 (PAYTM's BSE code)
    paytm_position = None
    for pos in positions:
        if 'PAYTM' in pos['ticker'].upper() or 'ONE97' in pos['ticker'].upper():
            paytm_position = pos
            print(f"Found PAYTM position: {pos['ticker']}")
            print(f"  Entry Price: ₹{pos['average_price']:.2f}")
            print(f"  Current Price: ₹{pos['last_price']:.2f}")
            print(f"  Quantity: {pos['quantity']}")
            print(f"  P&L: ₹{pos['pnl']:.2f} ({pos['pnl_percent']:.2f}%)")
            break
    
    if not paytm_position:
        print("No PAYTM position found in CNC holdings")
        print("\nCurrent CNC positions:")
        for pos in positions:
            print(f"  - {pos['ticker']}: ₹{pos['average_price']:.2f} → ₹{pos['last_price']:.2f}")
        
        # Try to analyze PAYTM as a test even without position
        print("\n" + "="*60)
        print("Running ICT analysis on PAYTM for demonstration...")
        print("="*60)
        
        # Create a mock position for analysis
        mock_position = {
            'ticker': 'PAYTM',
            'quantity': 100,
            'average_price': 900.0,  # Example entry price
            'last_price': 950.0,  # Will be updated with real price
            'pnl': 0,
            'pnl_percent': 0
        }
        
        try:
            hourly = analyzer.analyze_position(mock_position, 'hourly')
            if hourly:
                print(analyzer.format_analysis_report(hourly))
            
            daily = analyzer.analyze_position(mock_position, 'daily')
            if daily:
                print(analyzer.format_analysis_report(daily))
                
            if hourly and daily:
                print(f"\nSUMMARY:")
                print(f"  Hourly Structure: {hourly.market_structure.value}")
                print(f"  Daily Structure: {daily.market_structure.value}")
                print(f"  Hourly SL: ₹{hourly.optimal_sl:.2f}")
                print(f"  Daily SL: ₹{daily.optimal_sl:.2f}")
                print(f"  Conservative SL: ₹{min(hourly.optimal_sl, daily.optimal_sl):.2f}")
        except Exception as e:
            print(f"Error analyzing PAYTM: {e}")
    else:
        # Analyze actual PAYTM position
        print("\n" + "="*60)
        print("Running ICT Analysis on PAYTM position...")
        print("="*60)
        
        hourly = analyzer.analyze_position(paytm_position, 'hourly')
        daily = analyzer.analyze_position(paytm_position, 'daily')
        
        if hourly:
            print(analyzer.format_analysis_report(hourly))
        if daily:
            print(analyzer.format_analysis_report(daily))
        
        if hourly and daily:
            print(f"\nFINAL RECOMMENDATION:")
            print(f"  Conservative Stop Loss: ₹{min(hourly.optimal_sl, daily.optimal_sl):.2f}")
            print(f"  Risk from current: {((paytm_position['last_price'] - min(hourly.optimal_sl, daily.optimal_sl)) / paytm_position['last_price'] * 100):.2f}%")

if __name__ == "__main__":
    analyze_paytm()