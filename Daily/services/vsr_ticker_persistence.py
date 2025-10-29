#!/usr/bin/env python
"""
VSR Ticker Persistence Manager
Maintains a 15-day rolling window of tickers with momentum tracking
Counts unique days each ticker appeared (max 1 count per day)
"""

import os
import json
import datetime
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import pandas as pd

class VSRTickerPersistence:
    """Manages persistent tracking of VSR tickers over a 30-day window"""

    def __init__(self, persistence_file: str = None, window_days: int = 30):
        if persistence_file is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
            os.makedirs(data_dir, exist_ok=True)
            persistence_file = os.path.join(data_dir, 'vsr_ticker_persistence.json')

        self.persistence_file = persistence_file
        self.window_days = window_days  # Track for 30 days
        self.ticker_data = self.load_persistence_data()
        
    def load_persistence_data(self) -> Dict:
        """Load existing persistence data or create new"""
        if os.path.exists(self.persistence_file):
            try:
                with open(self.persistence_file, 'r') as f:
                    data = json.load(f)
                # Convert date strings back to datetime objects
                for ticker in data.get('tickers', {}):
                    if 'first_seen' in data['tickers'][ticker] and data['tickers'][ticker]['first_seen']:
                        data['tickers'][ticker]['first_seen'] = datetime.datetime.fromisoformat(
                            data['tickers'][ticker]['first_seen']
                        )
                    if 'last_seen' in data['tickers'][ticker] and data['tickers'][ticker]['last_seen']:
                        data['tickers'][ticker]['last_seen'] = datetime.datetime.fromisoformat(
                            data['tickers'][ticker]['last_seen']
                        )
                    if 'last_positive_momentum' in data['tickers'][ticker] and data['tickers'][ticker]['last_positive_momentum']:
                        data['tickers'][ticker]['last_positive_momentum'] = datetime.datetime.fromisoformat(
                            data['tickers'][ticker]['last_positive_momentum']
                        )
                return data
            except Exception as e:
                print(f"Error loading persistence data: {e}")
                return self._create_empty_data()
        return self._create_empty_data()
    
    def _create_empty_data(self) -> Dict:
        """Create empty persistence structure"""
        return {
            'tickers': {},
            'last_updated': datetime.datetime.now().isoformat()
        }
    
    def save_persistence_data(self):
        """Save persistence data to file"""
        try:
            # Convert datetime objects to strings for JSON serialization
            data_to_save = {
                'tickers': {},
                'last_updated': datetime.datetime.now().isoformat()
            }
            
            for ticker, info in self.ticker_data.get('tickers', {}).items():
                data_to_save['tickers'][ticker] = {}
                for key, value in info.items():
                    if isinstance(value, datetime.datetime):
                        data_to_save['tickers'][ticker][key] = value.isoformat()
                    else:
                        data_to_save['tickers'][ticker][key] = value
            
            with open(self.persistence_file, 'w') as f:
                json.dump(data_to_save, f, indent=2)
        except Exception as e:
            print(f"Error saving persistence data: {e}")
    
    def update_tickers(self, current_tickers: List[str], momentum_data: Dict[str, float] = None, price_data: Dict[str, float] = None):
        """Update ticker list with new scan results, momentum data, and price data"""
        now = datetime.datetime.now()
        momentum_data = momentum_data or {}
        price_data = price_data or {}

        # Update existing tickers or add new ones
        for ticker in current_tickers:
            if ticker not in self.ticker_data['tickers']:
                # New ticker
                self.ticker_data['tickers'][ticker] = {
                    'first_seen': now,
                    'last_seen': now,
                    'days_tracked': 1,
                    'appearances': 1,
                    'positive_momentum_days': 0,
                    'last_positive_momentum': None,
                    'momentum_history': [],
                    'daily_appearances': {now.date().isoformat(): 1},  # Track unique days
                    'daily_prices': {}  # Track price on each unique day
                }
            else:
                # Existing ticker
                ticker_info = self.ticker_data['tickers'][ticker]
                ticker_info['last_seen'] = now
                ticker_info['appearances'] += 1

                # Track daily appearances (max 1 per day)
                today = now.date().isoformat()
                if 'daily_appearances' not in ticker_info:
                    ticker_info['daily_appearances'] = {}
                if 'daily_prices' not in ticker_info:
                    ticker_info['daily_prices'] = {}

                if today not in ticker_info['daily_appearances']:
                    ticker_info['daily_appearances'][today] = 1
                else:
                    ticker_info['daily_appearances'][today] += 1

                # Clean up old daily appearances (keep only last 15 days)
                cutoff_date = (now.date() - datetime.timedelta(days=self.window_days)).isoformat()
                ticker_info['daily_appearances'] = {
                    date: count for date, count in ticker_info['daily_appearances'].items()
                    if date >= cutoff_date
                }

                # Update days tracked (count unique days in last 15 days)
                ticker_info['days_tracked'] = len(ticker_info['daily_appearances'])

            # Store price for today if provided
            if ticker in price_data:
                ticker_info = self.ticker_data['tickers'][ticker]
                today = now.date().isoformat()
                # Store first price of the day (don't overwrite if already set today)
                if today not in ticker_info.get('daily_prices', {}):
                    if 'daily_prices' not in ticker_info:
                        ticker_info['daily_prices'] = {}
                    ticker_info['daily_prices'][today] = price_data[ticker]

                # Clean up old daily prices (keep only last 15 days)
                cutoff_date = (now.date() - datetime.timedelta(days=self.window_days)).isoformat()
                ticker_info['daily_prices'] = {
                    date: price for date, price in ticker_info.get('daily_prices', {}).items()
                    if date >= cutoff_date
                }
            
            # Update momentum data if provided
            if ticker in momentum_data:
                momentum = momentum_data[ticker]
                ticker_info = self.ticker_data['tickers'][ticker]
                
                # Add to momentum history
                ticker_info['momentum_history'].append({
                    'date': now.isoformat(),
                    'momentum': momentum
                })
                
                # Keep only last 15 days of history
                cutoff_date = now - datetime.timedelta(days=self.window_days)
                ticker_info['momentum_history'] = [
                    h for h in ticker_info['momentum_history']
                    if datetime.datetime.fromisoformat(h['date']) > cutoff_date
                ]
                
                # Update positive momentum tracking
                if momentum > 0:
                    ticker_info['last_positive_momentum'] = now
                    # Count unique days with positive momentum
                    positive_days = set()
                    for h in ticker_info['momentum_history']:
                        if h['momentum'] > 0:
                            positive_days.add(datetime.datetime.fromisoformat(h['date']).date())
                    ticker_info['positive_momentum_days'] = len(positive_days)
        
        # Clean up old tickers
        self._cleanup_old_tickers()
        
        # Save updated data
        self.save_persistence_data()
    
    def _cleanup_old_tickers(self):
        """Remove tickers that haven't appeared in 15 days or have no positive momentum for 15 days"""
        now = datetime.datetime.now()
        cutoff_date = now - datetime.timedelta(days=self.window_days)
        
        tickers_to_remove = []
        
        for ticker, info in self.ticker_data['tickers'].items():
            # Remove if not seen in 15 days
            if info['last_seen'] < cutoff_date:
                tickers_to_remove.append(ticker)
                continue

            # Remove if no positive momentum in 15 days
            if info['last_positive_momentum'] is None:
                # Never had positive momentum, check if tracked for 15 days
                if (now - info['first_seen']).days >= self.window_days:
                    tickers_to_remove.append(ticker)
            elif info['last_positive_momentum'] < cutoff_date:
                # Had positive momentum but not in last 15 days
                tickers_to_remove.append(ticker)
        
        # Remove tickers
        for ticker in tickers_to_remove:
            del self.ticker_data['tickers'][ticker]
        
        if tickers_to_remove:
            print(f"Removed {len(tickers_to_remove)} tickers: {', '.join(tickers_to_remove)}")
    
    def get_active_tickers(self) -> Set[str]:
        """Get all tickers that should be tracked (appeared in last 15 days with momentum criteria)"""
        active_tickers = set()
        now = datetime.datetime.now()
        cutoff_date = now - datetime.timedelta(days=self.window_days)
        
        for ticker, info in self.ticker_data['tickers'].items():
            # Include if seen recently
            if info['last_seen'] >= cutoff_date:
                # Check momentum criteria
                if info['positive_momentum_days'] > 0 or (now - info['first_seen']).days < 1:
                    active_tickers.add(ticker)
        
        return active_tickers
    
    def get_ticker_stats(self, ticker: str) -> Dict:
        """Get statistics for a specific ticker"""
        if ticker not in self.ticker_data['tickers']:
            return None

        ticker_info = self.ticker_data['tickers'][ticker].copy()

        # Calculate total alerts in last 30 days
        now = datetime.datetime.now()
        cutoff_date = (now.date() - datetime.timedelta(days=30)).isoformat()
        daily_appearances = ticker_info.get('daily_appearances', {})

        # Sum all appearances in last 30 days
        alerts_last_30_days = sum(
            count for date, count in daily_appearances.items()
            if date >= cutoff_date
        )
        ticker_info['alerts_last_30_days'] = alerts_last_30_days

        # Get last 3 alert dates and prices (excluding today)
        if 'daily_appearances' in ticker_info and len(ticker_info['daily_appearances']) > 0:
            # Get sorted dates (newest first)
            sorted_dates = sorted(ticker_info['daily_appearances'].keys(), reverse=True)
            daily_prices = ticker_info.get('daily_prices', {})

            # Get today's date for comparison
            today_str = now.date().isoformat()

            # Build list of last 3 historical alerts (excluding today)
            historical_alerts = []
            for date_str in sorted_dates:
                if date_str != today_str:  # Skip today
                    alert_info = {
                        'date': date_str,
                        'count': daily_appearances[date_str],
                        'price': daily_prices.get(date_str)
                    }
                    historical_alerts.append(alert_info)
                    if len(historical_alerts) >= 3:
                        break

            ticker_info['last_3_alerts'] = historical_alerts

            # Keep penultimate (most recent non-today) for backward compatibility
            if len(historical_alerts) > 0:
                ticker_info['penultimate_alert_date'] = historical_alerts[0]['date']
                ticker_info['penultimate_alert_price'] = historical_alerts[0]['price']
            else:
                ticker_info['penultimate_alert_date'] = None
                ticker_info['penultimate_alert_price'] = None
        else:
            ticker_info['last_3_alerts'] = []
            ticker_info['penultimate_alert_date'] = None
            ticker_info['penultimate_alert_price'] = None

        return ticker_info
    
    def get_persistence_summary(self) -> Dict:
        """Get summary of persistence data"""
        now = datetime.datetime.now()
        active_tickers = self.get_active_tickers()
        
        summary = {
            'total_tracked': len(self.ticker_data['tickers']),
            'active_tickers': len(active_tickers),
            'tickers_by_days': defaultdict(int),
            'tickers_by_momentum': defaultdict(int),
            'recent_additions': [],
            'momentum_leaders': []
        }
        
        for ticker, info in self.ticker_data['tickers'].items():
            if ticker in active_tickers:
                # Group by days tracked
                summary['tickers_by_days'][info['days_tracked']] += 1
                
                # Group by positive momentum days
                summary['tickers_by_momentum'][info['positive_momentum_days']] += 1
                
                # Recent additions (added today)
                if info['first_seen'].date() == now.date():
                    summary['recent_additions'].append(ticker)
                
                # Momentum leaders (positive momentum for 3 days)
                if info['positive_momentum_days'] >= 3:
                    summary['momentum_leaders'].append({
                        'ticker': ticker,
                        'days': info['positive_momentum_days'],
                        'appearances': info['appearances']
                    })
        
        # Sort momentum leaders by days and appearances
        summary['momentum_leaders'].sort(
            key=lambda x: (x['days'], x['appearances']), 
            reverse=True
        )
        
        return summary


def merge_ticker_lists(current_tickers: List[str], persistence_manager: VSRTickerPersistence) -> List[str]:
    """Merge current scan results with persistent tickers"""
    # Get active persistent tickers
    persistent_tickers = persistence_manager.get_active_tickers()
    
    # Combine both lists (using set to avoid duplicates)
    all_tickers = set(current_tickers) | persistent_tickers
    
    return list(all_tickers)


if __name__ == "__main__":
    # Test the persistence manager
    pm = VSRTickerPersistence()
    
    # Simulate some ticker updates
    test_tickers = ['RELIANCE', 'TCS', 'INFY', 'HDFC']
    test_momentum = {
        'RELIANCE': 2.5,
        'TCS': -0.5,
        'INFY': 1.2,
        'HDFC': 0.8
    }
    
    pm.update_tickers(test_tickers, test_momentum)
    
    # Get summary
    summary = pm.get_persistence_summary()
    print(json.dumps(summary, indent=2, default=str))
    
    # Get active tickers
    active = pm.get_active_tickers()
    print(f"\nActive tickers: {active}")