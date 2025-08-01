#!/usr/bin/env python3
"""
Daily Momentum Update Script
Updates the historical momentum database with today's data
To be run after market close each day
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.scripts.momentum_historical_builder import HistoricalMomentumBuilder

def main():
    """Update momentum data for today"""
    print(f"Updating momentum data for {datetime.now().strftime('%Y-%m-%d')}")
    print("-" * 60)
    
    # Create builder instance
    builder = HistoricalMomentumBuilder(user_name='Sai')
    
    # Update today's momentum
    builder.update_daily_momentum()
    
    # Get and display summary
    summary = builder.get_historical_summary()
    
    if not summary.empty:
        latest = summary.iloc[0]
        print(f"\nToday's Momentum Summary:")
        print(f"Date: {latest['date']}")
        print(f"Momentum Count: {latest['daily_count']}")
        
        # Parse and display top movers
        try:
            import json
            top_movers = json.loads(latest['top_daily_wm'])
            print(f"\nTop 5 by WM:")
            for i, mover in enumerate(top_movers[:5], 1):
                print(f"{i}. {mover['ticker']}: WM={mover['wm']:.2f}, Slope={mover['slope']:.2f}%")
        except:
            pass
        
        # Show trend
        if len(summary) > 1:
            yesterday = summary.iloc[1]
            change = latest['daily_count'] - yesterday['daily_count']
            print(f"\nChange from yesterday: {change:+d} ({change/yesterday['daily_count']*100:+.1f}%)")
        
        # Show last 7 days trend
        print(f"\nLast 7 days trend:")
        for _, row in summary.head(7).iterrows():
            print(f"  {row['date']}: {row['daily_count']} stocks")
    
    print("\nUpdate complete!")

if __name__ == '__main__':
    main()