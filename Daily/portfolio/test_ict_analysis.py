#!/usr/bin/env python3
"""
Test script for ICT Stop Loss Analysis
Tests the analysis with sample data or actual positions
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from portfolio.SL_Watch_ICT import ICTAnalyzer, MarketStructure
import logging

def test_with_sample_position():
    """Test ICT analysis with a sample position"""
    print("="*80)
    print("Testing ICT Analysis with Sample Position")
    print("="*80)
    
    # Create analyzer
    analyzer = ICTAnalyzer(user_name='Sai')
    
    # Create a sample position for testing
    sample_position = {
        'ticker': 'RELIANCE',
        'quantity': 10,
        'average_price': 2500.0,
        'last_price': 2550.0,
        'pnl': 500.0,
        'pnl_percent': 2.0
    }
    
    print(f"\nSample Position: {sample_position['ticker']}")
    print(f"  Entry: ₹{sample_position['average_price']}")
    print(f"  Current: ₹{sample_position['last_price']}")
    print(f"  P&L: ₹{sample_position['pnl']} ({sample_position['pnl_percent']:.2f}%)")
    
    # Test hourly analysis
    print("\n" + "-"*40)
    print("Testing HOURLY timeframe analysis...")
    print("-"*40)
    
    try:
        hourly_analysis = analyzer.analyze_position(sample_position, 'hourly')
        if hourly_analysis:
            print(f"✓ Hourly analysis successful")
            print(f"  Market Structure: {hourly_analysis.market_structure.value}")
            print(f"  Optimal SL: ₹{hourly_analysis.optimal_sl:.2f}")
            print(f"  Reasoning: {hourly_analysis.sl_reasoning}")
            print(f"  Recommendation: {hourly_analysis.recommendation}")
        else:
            print("✗ Hourly analysis returned no data")
    except Exception as e:
        print(f"✗ Hourly analysis failed: {e}")
    
    # Test daily analysis
    print("\n" + "-"*40)
    print("Testing DAILY timeframe analysis...")
    print("-"*40)
    
    try:
        daily_analysis = analyzer.analyze_position(sample_position, 'daily')
        if daily_analysis:
            print(f"✓ Daily analysis successful")
            print(f"  Market Structure: {daily_analysis.market_structure.value}")
            print(f"  Optimal SL: ₹{daily_analysis.optimal_sl:.2f}")
            print(f"  Reasoning: {daily_analysis.sl_reasoning}")
            print(f"  Recommendation: {daily_analysis.recommendation}")
        else:
            print("✗ Daily analysis returned no data")
    except Exception as e:
        print(f"✗ Daily analysis failed: {e}")
    
    print("\n" + "="*80)
    print("Test completed")
    print("="*80)

def test_actual_positions():
    """Test with actual CNC positions from portfolio"""
    print("="*80)
    print("Testing ICT Analysis with Actual Positions")
    print("="*80)
    
    try:
        analyzer = ICTAnalyzer(user_name='Sai')
        positions = analyzer.get_cnc_positions()
        
        if positions:
            print(f"\nFound {len(positions)} CNC positions")
            for pos in positions:
                print(f"  - {pos['ticker']}: ₹{pos['average_price']:.2f} → ₹{pos['last_price']:.2f} ({pos['pnl_percent']:.2f}%)")
            
            # Analyze first position as test
            if positions:
                first_pos = positions[0]
                print(f"\nAnalyzing {first_pos['ticker']}...")
                
                hourly = analyzer.analyze_position(first_pos, 'hourly')
                daily = analyzer.analyze_position(first_pos, 'daily')
                
                if hourly and daily:
                    print(f"✓ Analysis complete")
                    print(f"  Hourly SL: ₹{hourly.optimal_sl:.2f}")
                    print(f"  Daily SL: ₹{daily.optimal_sl:.2f}")
                    print(f"  Conservative SL: ₹{min(hourly.optimal_sl, daily.optimal_sl):.2f}")
        else:
            print("No CNC positions found. Testing with sample position instead...")
            test_with_sample_position()
            
    except Exception as e:
        print(f"Error: {e}")
        print("\nFalling back to sample position test...")
        test_with_sample_position()

def main():
    """Main test execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test ICT Stop Loss Analysis')
    parser.add_argument('--sample', action='store_true', 
                       help='Test with sample position only')
    parser.add_argument('--actual', action='store_true',
                       help='Test with actual positions only')
    
    args = parser.parse_args()
    
    if args.sample:
        test_with_sample_position()
    elif args.actual:
        test_actual_positions()
    else:
        # Test both
        print("Testing with actual positions first...")
        test_actual_positions()

if __name__ == "__main__":
    main()