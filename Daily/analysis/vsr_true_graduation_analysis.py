#!/usr/bin/env python3
"""
Analyze true VSR graduations - tickers that started in hourly and moved to daily today
"""

import json
import os
from datetime import datetime, date

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

def parse_date(date_string):
    """Parse date string to date object"""
    try:
        # Handle different date formats
        if 'T' in date_string:
            return datetime.fromisoformat(date_string.split('.')[0]).date()
        else:
            return datetime.strptime(date_string, '%Y-%m-%d').date()
    except:
        return None

def analyze_true_graduations():
    """Analyze which tickers truly graduated from hourly to daily today"""
    
    # Load all VSR data
    daily_data = load_vsr_data(DAILY_VSR)
    hourly_long_data = load_vsr_data(HOURLY_LONG_VSR)
    hourly_short_data = load_vsr_data(HOURLY_SHORT_VSR)
    
    today = date(2025, 7, 30)
    
    # Analyze graduations
    true_graduates = {
        'long': [],
        'short': []
    }
    
    # Check long side
    for ticker, hourly_info in hourly_long_data['tickers'].items():
        if ticker in daily_data['tickers']:
            daily_info = daily_data['tickers'][ticker]
            
            # Parse first seen dates
            hourly_first_date = parse_date(hourly_info['first_seen'])
            daily_first_date = parse_date(daily_info['first_seen'])
            
            # Check if daily tracking started today
            if daily_first_date == today and hourly_first_date == today:
                true_graduates['long'].append({
                    'ticker': ticker,
                    'hourly_first_seen': hourly_info['first_seen'],
                    'daily_first_seen': daily_info['first_seen'],
                    'status': 'NEW_GRADUATE_TODAY'
                })
            elif daily_first_date == today and hourly_first_date != today:
                true_graduates['long'].append({
                    'ticker': ticker,
                    'hourly_first_seen': hourly_info['first_seen'],
                    'daily_first_seen': daily_info['first_seen'],
                    'status': 'GRADUATED_TODAY_FROM_EARLIER_HOURLY'
                })
    
    # Check short side
    for ticker, hourly_info in hourly_short_data['tickers'].items():
        if ticker in daily_data['tickers']:
            daily_info = daily_data['tickers'][ticker]
            
            # Parse first seen dates
            hourly_first_date = parse_date(hourly_info['first_seen'])
            daily_first_date = parse_date(daily_info['first_seen'])
            
            # Check if daily tracking started today
            if daily_first_date == today and hourly_first_date == today:
                true_graduates['short'].append({
                    'ticker': ticker,
                    'hourly_first_seen': hourly_info['first_seen'],
                    'daily_first_seen': daily_info['first_seen'],
                    'status': 'NEW_GRADUATE_TODAY'
                })
            elif daily_first_date == today and hourly_first_date != today:
                true_graduates['short'].append({
                    'ticker': ticker,
                    'hourly_first_seen': hourly_info['first_seen'],
                    'daily_first_seen': daily_info['first_seen'],
                    'status': 'GRADUATED_TODAY_FROM_EARLIER_HOURLY'
                })
    
    # Also check daily tickers that started today
    daily_new_today = []
    for ticker, daily_info in daily_data['tickers'].items():
        daily_first_date = parse_date(daily_info['first_seen'])
        if daily_first_date == today:
            daily_new_today.append({
                'ticker': ticker,
                'first_seen': daily_info['first_seen'],
                'days_tracked': daily_info['days_tracked'],
                'appearances': daily_info['appearances']
            })
    
    return true_graduates, daily_new_today

def print_graduation_report(graduates, new_daily):
    """Print detailed graduation report"""
    print("\n" + "="*60)
    print("TRUE VSR GRADUATION ANALYSIS - July 30, 2025")
    print("="*60)
    
    # Long side graduates
    print("\n🔺 LONG SIDE GRADUATIONS TO DAILY:")
    if graduates['long']:
        for grad in graduates['long']:
            print(f"\n{grad['ticker']}:")
            print(f"  Status: {grad['status']}")
            print(f"  Hourly first seen: {grad['hourly_first_seen']}")
            print(f"  Daily first seen: {grad['daily_first_seen']}")
    else:
        print("  None - All hourly long tickers were already in daily tracking")
    
    # Short side graduates
    print("\n🔻 SHORT SIDE GRADUATIONS TO DAILY:")
    if graduates['short']:
        for grad in graduates['short']:
            print(f"\n{grad['ticker']}:")
            print(f"  Status: {grad['status']}")
            print(f"  Hourly first seen: {grad['hourly_first_seen']}")
            print(f"  Daily first seen: {grad['daily_first_seen']}")
    else:
        print("  None - No short tickers graduated to daily today")
    
    # New daily tickers today
    print("\n📊 ALL NEW DAILY VSR TICKERS TODAY:")
    if new_daily:
        print(f"Total: {len(new_daily)} tickers")
        for ticker_info in sorted(new_daily, key=lambda x: x['ticker']):
            print(f"  {ticker_info['ticker']}: {ticker_info['appearances']} appearances")
    else:
        print("  None")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    graduates, new_daily = analyze_true_graduations()
    print_graduation_report(graduates, new_daily)