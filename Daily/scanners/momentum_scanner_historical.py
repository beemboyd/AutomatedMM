#!/usr/bin/env python3
"""
Historical Momentum Scanner
Extended version of momentum scanner that can analyze historical dates
"""

import os
import sys
import numpy as np
import pandas as pd
import datetime
from datetime import timedelta
import logging
from typing import Dict, List, Optional, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Daily.scanners.momentum_scanner_standalone import StandaloneMomentumScanner

class HistoricalMomentumScanner(StandaloneMomentumScanner):
    """Extended momentum scanner with historical analysis capabilities"""
    
    def fetch_ticker_data_for_date(self, ticker: str, interval: str, target_date: datetime.datetime, days_back: int = 365) -> Optional[pd.DataFrame]:
        """Fetch historical data for a ticker up to a specific date"""
        try:
            # Calculate date range - fetch data up to target date
            to_date = target_date
            from_date = to_date - timedelta(days=days_back)
            
            # Fetch data using parent method
            data = super().fetch_ticker_data(ticker, interval, days_back)
            
            if data is not None and not data.empty:
                # Filter data up to target date
                data['date'] = pd.to_datetime(data['date'])
                # Remove timezone if present
                if data['date'].dt.tz is not None:
                    data['date'] = data['date'].dt.tz_localize(None)
                
                # Filter data up to target date
                target_date_naive = target_date.replace(tzinfo=None) if target_date.tzinfo else target_date
                data = data[data['date'] <= target_date_naive]
                
                if not data.empty:
                    data['Ticker'] = ticker
                    return data
            
            return None
                
        except Exception as e:
            self.logger.error(f"Error fetching historical data for {ticker}: {e}")
            return None
    
    def analyze_timeframe_for_date(self, ticker: str, interval: str, target_date: datetime.datetime) -> Optional[Dict]:
        """Analyze a single timeframe for a ticker on a specific date"""
        try:
            # Determine how many days back to fetch based on interval
            if interval == 'day':
                days_back = 365  # 1 year for daily
            else:
                days_back = 1825  # 5 years for weekly
            
            # Fetch data up to target date
            data = self.fetch_ticker_data_for_date(ticker, 'day', target_date, days_back)
            if data is None or data.empty:
                return None
            
            # For weekly analysis, resample the daily data
            if interval == 'week':
                # Resample to weekly
                data = data.set_index('date')
                weekly_data = pd.DataFrame()
                weekly_data['open'] = data['open'].resample('W-FRI').first()
                weekly_data['high'] = data['high'].resample('W-FRI').max()
                weekly_data['low'] = data['low'].resample('W-FRI').min()
                weekly_data['close'] = data['close'].resample('W-FRI').last()
                weekly_data['volume'] = data['volume'].resample('W-FRI').sum()
                weekly_data = weekly_data.dropna()
                weekly_data.reset_index(inplace=True)
                weekly_data['Ticker'] = ticker
                data = weekly_data
            
            # Calculate indicators
            data = self.calculate_indicators(data)
            if data.empty:
                return None
            
            # Get the latest data (which should be on or before target date)
            latest_data = data.iloc[-1]
            current_price = float(latest_data['close'])
            
            # Check EMA_100 condition - price must be above EMA_100
            if 'EMA_100' in latest_data and not pd.isna(latest_data['EMA_100']):
                if current_price < float(latest_data['EMA_100']):
                    return None
            
            # Check slope condition - must be positive
            if 'Slope' in latest_data:
                slope_val = latest_data['Slope']
                if pd.isna(slope_val) or float(slope_val) < 0:
                    return None
            
            # Get WCross information
            wcross_date = None
            wcross_value = None
            
            if 'WCross' in data.columns:
                # Find when the most recent crossover started
                wcross_changes = data.loc[(data['WCross'].shift(1) != data['WCross']) & 
                                         (data['WCross'] == 'Yes')]
                
                if not wcross_changes.empty:
                    wcross_date = wcross_changes.iloc[-1]['date']
                    # Remove timezone info
                    if hasattr(wcross_date, 'tz_localize'):
                        wcross_date = wcross_date.tz_localize(None)
                    elif hasattr(wcross_date, 'replace'):
                        wcross_date = wcross_date.replace(tzinfo=None)
                    wcross_value = float(wcross_changes.iloc[-1]['close'])
            
            # Convert timezone-aware datetime to timezone-naive
            date_value = latest_data['date']
            if hasattr(date_value, 'tz_localize'):
                date_value = date_value.tz_localize(None)
            elif hasattr(date_value, 'replace'):
                date_value = date_value.replace(tzinfo=None)
            
            # Return data for tickers that meet criteria
            return {
                'Ticker': ticker,
                'Date': date_value,
                'Close': current_price,
                'Slope': float(latest_data['Slope']) if not pd.isna(latest_data['Slope']) else None,
                'R': float(latest_data['R']) if not pd.isna(latest_data['R']) else None,
                'WCross': latest_data.get('WCross', 'No'),
                'Gap': float(latest_data['Gap']) if not pd.isna(latest_data['Gap']) else None,
                'WCross_Date': wcross_date,
                'WCross_Value': wcross_value,
                'WM': float(latest_data['WM']) if not pd.isna(latest_data['WM']) else None,
                'EMA_5': float(latest_data['EMA_5']) if not pd.isna(latest_data['EMA_5']) else None,
                'EMA_100': float(latest_data['EMA_100']) if not pd.isna(latest_data['EMA_100']) else None
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing {ticker} for {interval} on {target_date}: {e}")
            return None
    
    def run_scan_for_date(self, target_date: datetime.datetime) -> Dict[str, List]:
        """Run the momentum scan for all tickers on a specific historical date"""
        self.logger.info(f"Starting historical momentum scan for {target_date.strftime('%Y-%m-%d')}")
        
        # Results storage
        results = {
            'Daily': [],
            'Weekly': []
        }
        
        # Process each ticker
        total_tickers = len(self.tickers)
        for i, ticker in enumerate(self.tickers, 1):
            if i % 50 == 0:
                self.logger.info(f"Processing ticker {i}/{total_tickers}: {ticker}")
            
            # Analyze daily timeframe
            daily_result = self.analyze_timeframe_for_date(ticker, 'day', target_date)
            if daily_result:
                results['Daily'].append(daily_result)
            
            # Analyze weekly timeframe
            weekly_result = self.analyze_timeframe_for_date(ticker, 'week', target_date)
            if weekly_result:
                results['Weekly'].append(weekly_result)
        
        self.logger.info(f"Scan complete for {target_date.strftime('%Y-%m-%d')}: "
                        f"Daily: {len(results['Daily'])} tickers, "
                        f"Weekly: {len(results['Weekly'])} tickers")
        
        return results