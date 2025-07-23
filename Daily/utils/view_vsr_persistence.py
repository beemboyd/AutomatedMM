#!/usr/bin/env python
"""
View VSR Ticker Persistence Data
Shows current persistent tickers and their statistics
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime
from tabulate import tabulate

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.vsr_ticker_persistence import VSRTickerPersistence

def format_datetime(dt):
    """Format datetime for display"""
    if dt is None:
        return "Never"
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt.strftime("%Y-%m-%d %H:%M")

def main():
    # Load persistence manager
    pm = VSRTickerPersistence()
    
    # Get summary
    summary = pm.get_persistence_summary()
    
    print("\n" + "="*80)
    print("VSR TICKER PERSISTENCE SUMMARY")
    print("="*80)
    
    print(f"\nTotal Tracked Tickers: {summary['total_tracked']}")
    print(f"Active Tickers: {summary['active_tickers']}")
    
    # Show breakdown by days
    print("\nTickers by Days Tracked:")
    for days in sorted(summary['tickers_by_days'].keys()):
        count = summary['tickers_by_days'][days]
        print(f"  {days} day(s): {count} tickers")
    
    # Show breakdown by momentum
    print("\nTickers by Positive Momentum Days:")
    for days in sorted(summary['tickers_by_momentum'].keys()):
        count = summary['tickers_by_momentum'][days]
        print(f"  {days} day(s): {count} tickers")
    
    # Show recent additions
    if summary['recent_additions']:
        print(f"\nToday's New Additions: {', '.join(summary['recent_additions'])}")
    
    # Show momentum leaders
    if summary['momentum_leaders']:
        print("\nMomentum Leaders (3+ days positive):")
        for leader in summary['momentum_leaders'][:10]:
            print(f"  {leader['ticker']}: {leader['days']} days, {leader['appearances']} appearances")
    
    # Show detailed ticker data
    print("\n" + "-"*80)
    print("DETAILED TICKER DATA")
    print("-"*80)
    
    # Get all active tickers
    active_tickers = pm.get_active_tickers()
    
    if active_tickers:
        # Prepare data for table
        table_data = []
        for ticker in sorted(active_tickers):
            stats = pm.get_ticker_stats(ticker)
            if stats:
                # Get latest momentum
                latest_momentum = "N/A"
                if stats['momentum_history']:
                    latest_momentum = f"{stats['momentum_history'][-1]['momentum']:.2f}%"
                
                table_data.append([
                    ticker,
                    stats['days_tracked'],
                    stats['appearances'],
                    stats['positive_momentum_days'],
                    format_datetime(stats['last_seen']),
                    format_datetime(stats['last_positive_momentum']),
                    latest_momentum
                ])
        
        # Print table
        headers = ["Ticker", "Days", "Appearances", "Positive Days", 
                  "Last Seen", "Last Positive", "Latest Momentum"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print("No active tickers found.")
    
    # Show tickers scheduled for removal
    print("\n" + "-"*80)
    print("TICKERS SCHEDULED FOR REMOVAL")
    print("-"*80)
    
    now = datetime.now()
    removal_candidates = []
    
    for ticker, info in pm.ticker_data['tickers'].items():
        if ticker not in active_tickers:
            reason = ""
            if (now - info['last_seen']).days >= 3:
                reason = "Not seen in 3+ days"
            elif info['last_positive_momentum'] is None and (now - info['first_seen']).days >= 3:
                reason = "No positive momentum in 3 days"
            elif info['last_positive_momentum'] and (now - info['last_positive_momentum']).days >= 3:
                reason = "No positive momentum in 3+ days"
            
            if reason:
                removal_candidates.append([
                    ticker,
                    format_datetime(info['last_seen']),
                    info['positive_momentum_days'],
                    reason
                ])
    
    if removal_candidates:
        headers = ["Ticker", "Last Seen", "Positive Days", "Removal Reason"]
        print(tabulate(removal_candidates, headers=headers, tablefmt="grid"))
    else:
        print("No tickers scheduled for removal.")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()