#!/usr/bin/env python3
"""
Momentum Widget for Dashboard
Shows daily and weekly momentum counts and trends
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta
from flask import jsonify

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.scanners.momentum_scanner_standalone import StandaloneMomentumScanner as MomentumScanner

class MomentumWidget:
    def __init__(self):
        self.momentum_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Momentum')
        self.scanner = MomentumScanner(user_name='Sai')
    
    def get_momentum_data(self) -> dict:
        """Get momentum data for dashboard widget"""
        try:
            # Get today's data
            today = datetime.now()
            today_counts = self.scanner.get_counts_for_date(today)
            
            # Get yesterday's data
            yesterday = today - timedelta(days=1)
            yesterday_counts = self.scanner.get_counts_for_date(yesterday)
            
            # Get week ago data
            week_ago = today - timedelta(days=7)
            week_ago_counts = self.scanner.get_counts_for_date(week_ago)
            
            # Calculate changes
            daily_change = today_counts['Daily'] - yesterday_counts['Daily']
            weekly_change = today_counts['Weekly'] - yesterday_counts['Weekly']
            
            # Get top movers from today's report
            top_daily = []
            top_weekly = []
            
            # Try to load today's report
            date_str = today.strftime('%Y%m%d')
            files = [f for f in os.listdir(self.momentum_dir) 
                    if f.startswith(f"India-Momentum_Report_{date_str}")]
            
            if files:
                latest_file = sorted(files)[-1]
                filepath = os.path.join(self.momentum_dir, latest_file)
                
                try:
                    # Read Daily sheet
                    df_daily = pd.read_excel(filepath, sheet_name='Daily_Summary')
                    if not df_daily.empty:
                        top_daily = df_daily.head(5)[['Ticker', 'WM', 'Slope']].to_dict('records')
                except:
                    pass
                
                try:
                    # Read Weekly sheet
                    df_weekly = pd.read_excel(filepath, sheet_name='Weekly_Summary')
                    if not df_weekly.empty:
                        top_weekly = df_weekly.head(5)[['Ticker', 'WM', 'Slope']].to_dict('records')
                except:
                    pass
            
            return {
                'status': 'success',
                'data': {
                    'daily': {
                        'count': today_counts['Daily'],
                        'change': daily_change,
                        'change_pct': (daily_change / yesterday_counts['Daily'] * 100) if yesterday_counts['Daily'] > 0 else 0,
                        'yesterday': yesterday_counts['Daily'],
                        'week_ago': week_ago_counts['Daily'],
                        'top_movers': top_daily
                    },
                    'weekly': {
                        'count': today_counts['Weekly'],
                        'change': weekly_change,
                        'change_pct': (weekly_change / yesterday_counts['Weekly'] * 100) if yesterday_counts['Weekly'] > 0 else 0,
                        'yesterday': yesterday_counts['Weekly'],
                        'week_ago': week_ago_counts['Weekly'],
                        'top_movers': top_weekly
                    },
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'next_update': '16:00 IST'
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'data': {
                    'daily': {'count': 0, 'change': 0, 'change_pct': 0, 'yesterday': 0, 'week_ago': 0, 'top_movers': []},
                    'weekly': {'count': 0, 'change': 0, 'change_pct': 0, 'yesterday': 0, 'week_ago': 0, 'top_movers': []},
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'next_update': '16:00 IST'
                }
            }
    
    def get_historical_trend(self, days: int = 30) -> dict:
        """Get historical trend data for charts"""
        try:
            # First try to get data from integrated historical file
            historical_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                         'Market_Regime', 'historical_breadth_data', 'sma_breadth_historical_latest.json')
            
            if os.path.exists(historical_file):
                with open(historical_file, 'r') as f:
                    historical_data = json.load(f)
                
                # Extract momentum data
                trend_data = {
                    'dates': [],
                    'daily_counts': [],
                    'weekly_counts': [],
                    'formula': {
                        'criteria': 'Price > EMA_100 AND Slope > 0',
                        'wm_formula': 'WM = ((EMA5-EMA8) + (EMA8-EMA13) + (EMA13-EMA21) + (EMA21-EMA50)) / 4',
                        'description': 'Stocks showing positive momentum based on EMA crossover strategy'
                    }
                }
                
                # Get last N days with momentum data
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                
                for entry in historical_data:
                    entry_date = datetime.strptime(entry['date'], '%Y-%m-%d')
                    if start_date <= entry_date <= end_date:
                        trend_data['dates'].append(entry['date'])
                        
                        # Get momentum counts if available
                        if 'momentum_breadth' in entry:
                            trend_data['daily_counts'].append(entry['momentum_breadth']['daily_count'])
                            trend_data['weekly_counts'].append(entry['momentum_breadth']['weekly_count'])
                        else:
                            # Fall back to individual file lookup
                            counts = self.scanner.get_counts_for_date(entry_date)
                            trend_data['daily_counts'].append(counts['Daily'])
                            trend_data['weekly_counts'].append(counts['Weekly'])
                
                # Calculate moving averages
                if len(trend_data['daily_counts']) >= 5:
                    daily_ma = pd.Series(trend_data['daily_counts']).rolling(5).mean().tolist()
                    weekly_ma = pd.Series(trend_data['weekly_counts']).rolling(5).mean().tolist()
                    trend_data['daily_ma'] = daily_ma
                    trend_data['weekly_ma'] = weekly_ma
                
                # Add market regime based on momentum
                regimes = []
                for count in trend_data['daily_counts']:
                    if count > 100:
                        regimes.append('Strong Bullish')
                    elif count > 70:
                        regimes.append('Bullish')
                    elif count > 40:
                        regimes.append('Neutral')
                    elif count > 20:
                        regimes.append('Bearish')
                    else:
                        regimes.append('Strong Bearish')
                trend_data['regimes'] = regimes
                
                return {
                    'status': 'success',
                    'data': trend_data
                }
            else:
                # Fall back to original method
                trend_data = {
                    'dates': [],
                    'daily_counts': [],
                    'weekly_counts': [],
                    'formula': {
                        'criteria': 'Price > EMA_100 AND Slope > 0',
                        'wm_formula': 'WM = ((EMA5-EMA8) + (EMA8-EMA13) + (EMA13-EMA21) + (EMA21-EMA50)) / 4',
                        'description': 'Stocks showing positive momentum based on EMA crossover strategy'
                    }
                }
                
                # Get data for past N days
                for i in range(days, -1, -1):
                    date = datetime.now() - timedelta(days=i)
                    
                    # Skip weekends
                    if date.weekday() >= 5:
                        continue
                        
                    counts = self.scanner.get_counts_for_date(date)
                    
                    trend_data['dates'].append(date.strftime('%Y-%m-%d'))
                    trend_data['daily_counts'].append(counts['Daily'])
                    trend_data['weekly_counts'].append(counts['Weekly'])
                
                # Calculate moving averages
                if len(trend_data['daily_counts']) >= 5:
                    daily_ma = pd.Series(trend_data['daily_counts']).rolling(5).mean().tolist()
                    weekly_ma = pd.Series(trend_data['weekly_counts']).rolling(5).mean().tolist()
                    trend_data['daily_ma'] = daily_ma
                    trend_data['weekly_ma'] = weekly_ma
                
                return {
                    'status': 'success',
                    'data': trend_data
                }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'data': {
                    'dates': [], 
                    'daily_counts': [], 
                    'weekly_counts': [],
                    'formula': {
                        'criteria': 'Price > EMA_100 AND Slope > 0',
                        'wm_formula': 'WM = ((EMA5-EMA8) + (EMA8-EMA13) + (EMA13-EMA21) + (EMA21-EMA50)) / 4',
                        'description': 'Stocks showing positive momentum based on EMA crossover strategy'
                    }
                }
            }


# Flask route handler
def get_momentum_widget_data():
    """Flask route handler for momentum widget"""
    widget = MomentumWidget()
    return jsonify(widget.get_momentum_data())

def get_momentum_trend_data():
    """Flask route handler for momentum trend chart"""
    widget = MomentumWidget()
    return jsonify(widget.get_historical_trend())


if __name__ == '__main__':
    # Test the widget
    widget = MomentumWidget()
    data = widget.get_momentum_data()
    print(json.dumps(data, indent=2))