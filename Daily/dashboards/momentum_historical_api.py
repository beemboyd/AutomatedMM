#!/usr/bin/env python3
"""
Momentum Historical Data API
Provides endpoints for historical momentum analysis
"""

import os
import sys
import sqlite3
import json
import pandas as pd
from datetime import datetime, timedelta
from flask import jsonify

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class MomentumHistoricalAPI:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = os.path.join(self.base_dir, 'Daily', 'Momentum', 'historical_data', 'momentum_history.db')
    
    def get_historical_trend(self, days: int = 210) -> dict:
        """Get historical momentum trend data"""
        try:
            if not os.path.exists(self.db_path):
                return {
                    'status': 'error',
                    'message': 'Historical database not found. Run momentum_historical_builder.py first.'
                }
            
            conn = sqlite3.connect(self.db_path)
            
            # Get daily summary data
            query = '''
                SELECT date, daily_count, weekly_count, daily_tickers, top_daily_wm
                FROM daily_summary
                WHERE date >= date('now', '-{} days')
                ORDER BY date
            '''.format(days)
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                return {
                    'status': 'error',
                    'message': 'No historical data available'
                }
            
            # Prepare data for chart
            dates = []
            daily_counts = []
            weekly_counts = []
            
            for _, row in df.iterrows():
                dates.append(row['date'])
                daily_counts.append(row['daily_count'])
                weekly_counts.append(row.get('weekly_count', row['daily_count']))  # Use daily if weekly not available
            
            # Calculate moving averages
            daily_ma = pd.Series(daily_counts).rolling(5).mean().tolist()
            weekly_ma = pd.Series(weekly_counts).rolling(5).mean().tolist()
            
            # Calculate market regime based on counts
            regimes = []
            for count in daily_counts:
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
            
            return {
                'status': 'success',
                'data': {
                    'dates': dates,
                    'daily_counts': daily_counts,
                    'weekly_counts': weekly_counts,
                    'daily_ma': daily_ma,
                    'weekly_ma': weekly_ma,
                    'regimes': regimes,
                    'statistics': {
                        'avg_daily': sum(daily_counts) / len(daily_counts) if daily_counts else 0,
                        'max_daily': max(daily_counts) if daily_counts else 0,
                        'min_daily': min(daily_counts) if daily_counts else 0,
                        'current_daily': daily_counts[-1] if daily_counts else 0,
                        'trend': 'Up' if len(daily_counts) > 1 and daily_counts[-1] > daily_counts[-2] else 'Down'
                    }
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def get_ticker_history(self, ticker: str, days: int = 30) -> dict:
        """Get historical momentum data for a specific ticker"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            query = '''
                SELECT date, close, wm, slope, wcross, ema_100, meets_criteria
                FROM momentum_data
                WHERE ticker = ? AND date >= date('now', '-{} days')
                ORDER BY date
            '''.format(days)
            
            df = pd.read_sql_query(query, conn, params=(ticker,))
            conn.close()
            
            if df.empty:
                return {
                    'status': 'error',
                    'message': f'No data found for {ticker}'
                }
            
            return {
                'status': 'success',
                'data': df.to_dict('records')
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def get_top_movers(self, date: str = None) -> dict:
        """Get top momentum movers for a specific date"""
        try:
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')
            
            conn = sqlite3.connect(self.db_path)
            
            # Get top movers by WM
            query = '''
                SELECT ticker, close, wm, slope, wcross
                FROM momentum_data
                WHERE date = ? AND meets_criteria = 1
                ORDER BY wm DESC
                LIMIT 20
            '''
            
            df = pd.read_sql_query(query, conn, params=(date,))
            conn.close()
            
            return {
                'status': 'success',
                'date': date,
                'data': df.to_dict('records')
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def get_market_breadth_history(self, days: int = 90) -> dict:
        """Get market breadth analysis over time"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Get breadth data
            query = '''
                SELECT 
                    date,
                    daily_count,
                    (SELECT COUNT(*) FROM momentum_data WHERE date = ds.date AND wcross = 'Yes') as wcross_count
                FROM daily_summary ds
                WHERE date >= date('now', '-{} days')
                ORDER BY date
            '''.format(days)
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if df.empty:
                return {
                    'status': 'error',
                    'message': 'No breadth data available'
                }
            
            # Calculate breadth percentages (assuming 603 total tickers)
            total_tickers = 603
            df['breadth_pct'] = (df['daily_count'] / total_tickers * 100).round(2)
            df['wcross_pct'] = (df['wcross_count'] / total_tickers * 100).round(2)
            
            return {
                'status': 'success',
                'data': {
                    'dates': df['date'].tolist(),
                    'breadth_pct': df['breadth_pct'].tolist(),
                    'wcross_pct': df['wcross_pct'].tolist(),
                    'counts': df['daily_count'].tolist(),
                    'wcross_counts': df['wcross_count'].tolist()
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }


# Flask route handlers
momentum_api = MomentumHistoricalAPI()

def get_momentum_historical_trend():
    """Flask route handler for historical trend"""
    return jsonify(momentum_api.get_historical_trend())

def get_momentum_ticker_history(ticker: str):
    """Flask route handler for ticker history"""
    return jsonify(momentum_api.get_ticker_history(ticker))

def get_momentum_top_movers(date: str = None):
    """Flask route handler for top movers"""
    return jsonify(momentum_api.get_top_movers(date))

def get_momentum_breadth_history():
    """Flask route handler for market breadth"""
    return jsonify(momentum_api.get_market_breadth_history())