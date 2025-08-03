#!/usr/bin/env python3
"""
Market Breadth Momentum Widget
Calculates momentum based on market breadth data: WM = (SMA20 - SMA50) / 2
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from flask import jsonify
import requests

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class MarketBreadthMomentumWidget:
    def __init__(self):
        self.market_breadth_api = "http://localhost:5001/api/sma-breadth-history"
        self.historical_data_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            'Market_Regime', 'historical_breadth_data', 'sma_breadth_historical_latest.json'
        )
        # Load historical momentum data
        self.momentum_history_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'analysis', 'momentum_historical', 'momentum_historical_20250802.json'
        )
    
    def get_market_breadth_data(self):
        """Get market breadth data from API or file"""
        try:
            # Try API first
            response = requests.get(self.market_breadth_api, timeout=5)
            if response.status_code == 200:
                data = response.json()
                # The API returns arrays, need to reconstruct
                if isinstance(data, dict) and 'labels' in data:
                    return self._parse_api_response(data)
        except:
            pass
        
        # Fallback to file
        try:
            with open(self.historical_data_path, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def _parse_api_response(self, api_data):
        """Parse API response into standard format"""
        result = []
        labels = api_data.get('labels', [])
        sma20_values = api_data.get('sma20_values', [])
        sma50_values = api_data.get('sma50_values', [])
        
        for i in range(len(labels)):
            if i < len(sma20_values) and i < len(sma50_values):
                result.append({
                    'date': labels[i],
                    'sma_breadth': {
                        'sma20_percent': sma20_values[i],
                        'sma50_percent': sma50_values[i]
                    }
                })
        
        return result
    
    def calculate_momentum(self, sma20, sma50):
        """Calculate momentum using simple formula: WM = (SMA20 - SMA50) / 2"""
        return (sma20 - sma50) / 2
    
    def get_momentum_data(self):
        """Get momentum data for dashboard widget"""
        try:
            # Get market breadth data
            breadth_data = self.get_market_breadth_data()
            
            if not breadth_data:
                return self._empty_response()
            
            # Get last 14 days of data
            recent_data = breadth_data[-14:] if len(breadth_data) >= 14 else breadth_data
            
            # Calculate momentum for each day
            momentum_values = []
            dates = []
            
            for entry in recent_data:
                sma_data = entry.get('sma_breadth', {})
                sma20 = sma_data.get('sma20_percent', 0)
                sma50 = sma_data.get('sma50_percent', 0)
                
                momentum = self.calculate_momentum(sma20, sma50)
                momentum_values.append(momentum)
                dates.append(entry.get('date', ''))
            
            # Get current values (latest)
            current_entry = breadth_data[-1] if breadth_data else {}
            current_sma = current_entry.get('sma_breadth', {})
            current_sma20 = current_sma.get('sma20_percent', 0)
            current_sma50 = current_sma.get('sma50_percent', 0)
            current_momentum = self.calculate_momentum(current_sma20, current_sma50)
            
            # Get yesterday's values
            yesterday_momentum = momentum_values[-2] if len(momentum_values) > 1 else 0
            momentum_change = current_momentum - yesterday_momentum
            
            # Load historical ticker counts
            ticker_counts = self._load_historical_ticker_counts()
            
            # Market regime interpretation
            regime = self._interpret_momentum(current_momentum)
            
            return {
                'status': 'success',
                'data': {
                    'current': {
                        'sma20': round(current_sma20, 2),
                        'sma50': round(current_sma50, 2),
                        'momentum': round(current_momentum, 2),
                        'change': round(momentum_change, 2),
                        'regime': regime
                    },
                    'trend': {
                        'dates': dates,
                        'values': [round(v, 2) for v in momentum_values]
                    },
                    'ticker_analysis': ticker_counts,
                    'formula': 'WM = (SMA20 - SMA50) / 2',
                    'interpretation': self._get_interpretation(current_momentum, regime),
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'data': self._empty_response()['data']
            }
    
    def _load_historical_ticker_counts(self):
        """Load historical ticker counts from momentum analysis"""
        try:
            with open(self.momentum_history_path, 'r') as f:
                historical_data = json.load(f)
            
            # Get last 7 days of ticker counts
            recent_counts = historical_data[-7:] if len(historical_data) >= 7 else historical_data
            
            daily_counts = [d['daily_count'] for d in recent_counts]
            weekly_counts = [d['weekly_count'] for d in recent_counts]
            
            return {
                'daily': {
                    'current': daily_counts[-1] if daily_counts else 0,
                    'average': round(np.mean(daily_counts), 1) if daily_counts else 0,
                    'trend': daily_counts
                },
                'weekly': {
                    'current': weekly_counts[-1] if weekly_counts else 0,
                    'average': round(np.mean(weekly_counts), 1) if weekly_counts else 0,
                    'trend': weekly_counts
                }
            }
        except:
            return {
                'daily': {'current': 0, 'average': 0, 'trend': []},
                'weekly': {'current': 0, 'average': 0, 'trend': []}
            }
    
    def _interpret_momentum(self, momentum):
        """Interpret momentum value into market regime"""
        if momentum > 10:
            return "Strong Bullish"
        elif momentum > 5:
            return "Bullish"
        elif momentum > 0:
            return "Mildly Bullish"
        elif momentum > -5:
            return "Mildly Bearish"
        elif momentum > -10:
            return "Bearish"
        else:
            return "Strong Bearish"
    
    def _get_interpretation(self, momentum, regime):
        """Get detailed interpretation"""
        if momentum > 5:
            return f"{regime}: Strong upward momentum. More stocks above SMA20 than SMA50."
        elif momentum > 0:
            return f"{regime}: Slight positive momentum. Market trying to recover."
        elif momentum > -5:
            return f"{regime}: Slight negative momentum. Market under pressure."
        else:
            return f"{regime}: Strong downward momentum. More stocks below both SMAs."
    
    def _empty_response(self):
        """Return empty response structure"""
        return {
            'status': 'success',
            'data': {
                'current': {
                    'sma20': 0,
                    'sma50': 0,
                    'momentum': 0,
                    'change': 0,
                    'regime': 'Unknown'
                },
                'trend': {
                    'dates': [],
                    'values': []
                },
                'ticker_analysis': {
                    'daily': {'current': 0, 'average': 0, 'trend': []},
                    'weekly': {'current': 0, 'average': 0, 'trend': []}
                },
                'formula': 'WM = (SMA20 - SMA50) / 2',
                'interpretation': 'No data available',
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }

# Flask integration functions
def get_market_breadth_momentum_data():
    """Get momentum data based on market breadth"""
    widget = MarketBreadthMomentumWidget()
    return jsonify(widget.get_momentum_data())

def get_market_breadth_momentum_trend():
    """Get historical momentum trend data"""
    widget = MarketBreadthMomentumWidget()
    data = widget.get_momentum_data()
    
    if data['status'] == 'success':
        trend_data = data['data']['trend']
        ticker_data = data['data']['ticker_analysis']
        
        return jsonify({
            'status': 'success',
            'data': {
                'momentum_trend': trend_data,
                'ticker_counts': {
                    'dates': trend_data['dates'][-7:],
                    'daily': ticker_data['daily']['trend'],
                    'weekly': ticker_data['weekly']['trend']
                }
            }
        })
    else:
        return jsonify(data)