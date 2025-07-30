#!/usr/bin/env python3
"""
Analyze which tickers have graduated from hourly to daily VSR tracking
"""

import json
import os
from datetime import datetime
from collections import defaultdict

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'data')

# VSR persistence files
DAILY_VSR = os.path.join(DATA_DIR, 'vsr_ticker_persistence.json')
HOURLY_LONG_VSR = os.path.join(DATA_DIR, 'vsr_ticker_persistence_hourly_long.json')
HOURLY_SHORT_VSR = os.path.join(DATA_DIR, 'short_momentum', 'vsr_ticker_persistence_hourly_short.json')

def load_vsr_data(filepath):
    """Load VSR persistence data from file"""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {'tickers': {}}

def analyze_graduation():
    """Analyze which tickers have graduated from hourly to daily tracking"""
    
    # Load all VSR data
    daily_data = load_vsr_data(DAILY_VSR)
    hourly_long_data = load_vsr_data(HOURLY_LONG_VSR)
    hourly_short_data = load_vsr_data(HOURLY_SHORT_VSR)
    
    # Extract ticker sets
    daily_tickers = set(daily_data['tickers'].keys())
    hourly_long_tickers = set(hourly_long_data['tickers'].keys())
    hourly_short_tickers = set(hourly_short_data['tickers'].keys())
    
    # Find graduated tickers (present in both hourly and daily)
    graduated_long = hourly_long_tickers.intersection(daily_tickers)
    graduated_short = hourly_short_tickers.intersection(daily_tickers)
    
    # Analyze graduation details
    graduation_report = {
        'long_side': [],
        'short_side': [],
        'summary': {}
    }
    
    # Process long side graduations
    for ticker in graduated_long:
        hourly_info = hourly_long_data['tickers'][ticker]
        daily_info = daily_data['tickers'][ticker]
        
        graduation_report['long_side'].append({
            'ticker': ticker,
            'hourly_first_seen': hourly_info['first_seen'],
            'hourly_last_seen': hourly_info['last_seen'],
            'hourly_appearances': hourly_info['appearances'],
            'daily_first_seen': daily_info['first_seen'],
            'daily_days_tracked': daily_info['days_tracked'],
            'daily_appearances': daily_info['appearances'],
            'status': 'GRADUATED'
        })
    
    # Process short side graduations
    for ticker in graduated_short:
        hourly_info = hourly_short_data['tickers'][ticker]
        daily_info = daily_data['tickers'][ticker]
        
        graduation_report['short_side'].append({
            'ticker': ticker,
            'hourly_first_seen': hourly_info['first_seen'],
            'hourly_last_seen': hourly_info['last_seen'],
            'hourly_appearances': hourly_info['appearances'],
            'daily_first_seen': daily_info['first_seen'],
            'daily_days_tracked': daily_info['days_tracked'],
            'daily_appearances': daily_info['appearances'],
            'status': 'GRADUATED'
        })
    
    # Find tickers only in hourly (potential future graduates)
    hourly_only_long = hourly_long_tickers - daily_tickers
    hourly_only_short = hourly_short_tickers - daily_tickers
    
    # Summary statistics
    graduation_report['summary'] = {
        'total_daily_tickers': len(daily_tickers),
        'total_hourly_long_tickers': len(hourly_long_tickers),
        'total_hourly_short_tickers': len(hourly_short_tickers),
        'graduated_long_count': len(graduated_long),
        'graduated_short_count': len(graduated_short),
        'hourly_only_long_count': len(hourly_only_long),
        'hourly_only_short_count': len(hourly_only_short),
        'graduated_long_tickers': sorted(list(graduated_long)),
        'graduated_short_tickers': sorted(list(graduated_short)),
        'hourly_only_long_tickers': sorted(list(hourly_only_long)),
        'hourly_only_short_tickers': sorted(list(hourly_only_short))
    }
    
    return graduation_report

def print_report(report):
    """Print formatted graduation report"""
    print("\n" + "="*60)
    print("VSR TICKER GRADUATION REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Summary
    summary = report['summary']
    print("\nSUMMARY:")
    print(f"Total Daily VSR Tickers: {summary['total_daily_tickers']}")
    print(f"Total Hourly Long Tickers: {summary['total_hourly_long_tickers']}")
    print(f"Total Hourly Short Tickers: {summary['total_hourly_short_tickers']}")
    
    print(f"\nGRADUATED TO DAILY:")
    print(f"  Long Side: {summary['graduated_long_count']} tickers")
    print(f"  Short Side: {summary['graduated_short_count']} tickers")
    
    # Long side graduates
    if summary['graduated_long_count'] > 0:
        print("\nLONG SIDE GRADUATES:")
        print("-" * 40)
        for ticker_info in sorted(report['long_side'], key=lambda x: x['ticker']):
            print(f"\n{ticker_info['ticker']}:")
            print(f"  Hourly Tracking: {ticker_info['hourly_appearances']} appearances")
            print(f"  Daily Tracking: {ticker_info['daily_days_tracked']} days, {ticker_info['daily_appearances']} appearances")
            print(f"  First seen (hourly): {ticker_info['hourly_first_seen'][:19]}")
            print(f"  First seen (daily): {ticker_info['daily_first_seen'][:19]}")
    
    # Short side graduates
    if summary['graduated_short_count'] > 0:
        print("\nSHORT SIDE GRADUATES:")
        print("-" * 40)
        for ticker_info in sorted(report['short_side'], key=lambda x: x['ticker']):
            print(f"\n{ticker_info['ticker']}:")
            print(f"  Hourly Tracking: {ticker_info['hourly_appearances']} appearances")
            print(f"  Daily Tracking: {ticker_info['daily_days_tracked']} days, {ticker_info['daily_appearances']} appearances")
            print(f"  First seen (hourly): {ticker_info['hourly_first_seen'][:19]}")
            print(f"  First seen (daily): {ticker_info['daily_first_seen'][:19]}")
    
    # Tickers only in hourly (potential future graduates)
    print("\n\nPOTENTIAL FUTURE GRADUATES (Hourly Only):")
    print("-" * 40)
    print(f"Long Side: {summary['hourly_only_long_count']} tickers")
    if summary['hourly_only_long_count'] > 0:
        print(f"  {', '.join(summary['hourly_only_long_tickers'][:10])}")
        if summary['hourly_only_long_count'] > 10:
            print(f"  ... and {summary['hourly_only_long_count'] - 10} more")
    
    print(f"\nShort Side: {summary['hourly_only_short_count']} tickers")
    if summary['hourly_only_short_count'] > 0:
        print(f"  {', '.join(summary['hourly_only_short_tickers'][:10])}")
        if summary['hourly_only_short_count'] > 10:
            print(f"  ... and {summary['hourly_only_short_count'] - 10} more")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    report = analyze_graduation()
    print_report(report)
    
    # Save report to file
    report_file = os.path.join(os.path.dirname(SCRIPT_DIR), 'analysis', 'vsr_graduation_report.json')
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to: {report_file}")