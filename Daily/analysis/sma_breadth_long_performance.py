#!/usr/bin/env python3
"""
Analyze Long Performance based on SMA20 Breadth levels
Find optimal breadth thresholds for long positions
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, List
import configparser

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kiteconnect import KiteConnect

class SMABreadthLongAnalyzer:
    def __init__(self, user_name: str = 'Sai'):
        """Initialize the analyzer"""
        self.user_name = user_name
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        self.setup_logging()
        
        # Initialize Kite connection
        self.kite = self.initialize_kite_connection()
        
        # Results directory
        self.results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'performance_analysis')
        os.makedirs(self.results_dir, exist_ok=True)
        
        self.logger.info("Long reversal performance analyzer initialized")
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'long_performance_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def initialize_kite_connection(self) -> KiteConnect:
        """Initialize Kite connection"""
        try:
            config_path = os.path.join(self.base_dir, 'Daily', 'config.ini')
            config = configparser.ConfigParser()
            config.read(config_path)
            
            credential_section = f'API_CREDENTIALS_{self.user_name}'
            api_key = config.get(credential_section, 'api_key')
            access_token = config.get(credential_section, 'access_token')
            
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            
            # Test connection
            profile = kite.profile()
            self.logger.info(f"Connected to Kite as: {profile.get('user_name', 'Unknown')}")
            
            return kite
        except Exception as e:
            self.logger.error(f"Failed to initialize Kite connection: {e}")
            raise
    
    def load_signal_data(self, signal_file: str) -> pd.DataFrame:
        """Load long reversal signals from Excel file"""
        try:
            df = pd.read_excel(signal_file)
            self.logger.info(f"Loaded {len(df)} long signals from {signal_file}")
            return df
        except Exception as e:
            self.logger.error(f"Error loading signal file: {e}")
            return pd.DataFrame()
    
    def get_instrument_token(self, ticker: str) -> int:
        """Get instrument token for a ticker"""
        try:
            instruments = self.kite.instruments("NSE")
            for instrument in instruments:
                if instrument['tradingsymbol'] == ticker:
                    return instrument['instrument_token']
            
            # Try BSE if not found in NSE
            instruments = self.kite.instruments("BSE")
            for instrument in instruments:
                if instrument['tradingsymbol'] == ticker:
                    return instrument['instrument_token']
            
            return None
        except:
            return None
    
    def fetch_ticker_performance(self, ticker: str, entry_date: datetime, days: int = 5) -> Dict:
        """Fetch ticker performance from entry date for long positions"""
        try:
            instrument_token = self.get_instrument_token(ticker)
            if not instrument_token:
                return None
            
            # Fetch data from entry date
            from_date = entry_date
            to_date = entry_date + timedelta(days=days + 2)  # Add buffer for weekends
            
            historical_data = self.kite.historical_data(
                instrument_token,
                from_date,
                to_date,
                interval='day'
            )
            
            if not historical_data:
                return None
            
            df = pd.DataFrame(historical_data)
            df['date'] = pd.to_datetime(df['date'])
            
            # Get entry day data
            entry_day = df.iloc[0] if len(df) > 0 else None
            if entry_day is None:
                return None
            
            # Calculate performance for long position
            performance = {
                'ticker': ticker,
                'entry_date': entry_day['date'].strftime('%Y-%m-%d'),
                'entry_price': float(entry_day['close']),
                'entry_high': float(entry_day['high']),
                'entry_low': float(entry_day['low']),
                'daily_performance': []
            }
            
            # Track performance for each subsequent day
            for i in range(1, min(len(df), 6)):  # Max 5 days after entry
                day_data = df.iloc[i]
                
                # For long position: profit when price goes up
                pnl_percent = ((day_data['close'] - entry_day['close']) / entry_day['close']) * 100
                max_profit = ((day_data['high'] - entry_day['close']) / entry_day['close']) * 100
                max_loss = ((day_data['low'] - entry_day['close']) / entry_day['close']) * 100
                
                performance['daily_performance'].append({
                    'day': i,
                    'date': day_data['date'].strftime('%Y-%m-%d'),
                    'close': float(day_data['close']),
                    'high': float(day_data['high']),
                    'low': float(day_data['low']),
                    'pnl_percent': float(pnl_percent),
                    'max_profit_percent': float(max_profit),
                    'max_loss_percent': float(max_loss),
                    'volume': int(day_data['volume'])
                })
            
            # Calculate week-end performance
            if len(df) >= 5:
                last_day = df.iloc[4] if len(df) > 4 else df.iloc[-1]
                performance['week_end_price'] = float(last_day['close'])
                performance['week_end_pnl_percent'] = float(
                    ((last_day['close'] - entry_day['close']) / entry_day['close']) * 100
                )
                performance['week_end_date'] = last_day['date'].strftime('%Y-%m-%d')
            
            return performance
            
        except Exception as e:
            self.logger.error(f"Error fetching data for {ticker}: {e}")
            return None
    
    def analyze_performance(self, signal_file: str, signal_date: datetime):
        """Analyze performance of all long signals"""
        # Load signals
        signals_df = self.load_signal_data(signal_file)
        if signals_df.empty:
            self.logger.error("No signals found")
            return None
        
        # Get ticker column
        ticker_col = None
        for col in ['Ticker', 'ticker', 'Symbol', 'symbol']:
            if col in signals_df.columns:
                ticker_col = col
                break
        
        if not ticker_col:
            self.logger.error("No ticker column found in signal file")
            return None
        
        # Analyze each ticker
        performance_results = []
        successful_longs = 0
        total_pnl = 0
        
        for idx, row in signals_df.iterrows():
            ticker = row[ticker_col]
            self.logger.info(f"Analyzing {ticker} ({idx+1}/{len(signals_df)})")
            
            performance = self.fetch_ticker_performance(ticker, signal_date)
            if performance:
                performance_results.append(performance)
                
                # Check if profitable
                if 'week_end_pnl_percent' in performance:
                    if performance['week_end_pnl_percent'] > 0:
                        successful_longs += 1
                    total_pnl += performance['week_end_pnl_percent']
        
        # Create summary
        if performance_results:
            avg_pnl = total_pnl / len(performance_results)
            success_rate = (successful_longs / len(performance_results)) * 100
            
            return {
                'date': signal_date.strftime('%Y-%m-%d'),
                'total_signals': len(signals_df),
                'analyzed': len(performance_results),
                'successful': successful_longs,
                'success_rate': success_rate,
                'avg_pnl': avg_pnl,
                'total_pnl': total_pnl
            }
        
        return None

def analyze_specific_dates():
    """Analyze long performance for specific dates with known breadth"""
    analyzer = SMABreadthLongAnalyzer(user_name='Sai')
    
    # Test dates with different breadth levels
    test_cases = [
        {
            'date': '2025-07-28',
            'breadth': 19.5,
            'file_pattern': 'Long_Reversal_Daily_20250728_12'
        },
        {
            'date': '2025-07-25', 
            'breadth': 26.06,
            'file_pattern': 'Long_Reversal_Daily_20250725_11'
        },
        {
            'date': '2025-07-22',
            'breadth': 46.45,
            'file_pattern': 'Long_Reversal_Daily_20250722_11'
        },
        {
            'date': '2025-07-18',
            'breadth': 55.32,
            'file_pattern': 'Long_Reversal_Daily_20250718_11'
        },
        {
            'date': '2025-07-17',
            'breadth': 65.1,
            'file_pattern': 'Long_Reversal_Daily_20250717_12'
        },
        {
            'date': '2025-07-16',
            'breadth': 65.8,
            'file_pattern': 'Long_Reversal_Daily_20250716_12'
        }
    ]
    
    results = []
    
    for test in test_cases:
        # Find long reversal file
        results_dir = os.path.join(analyzer.base_dir, 'Daily', 'results')
        date_str = datetime.strptime(test['date'], '%Y-%m-%d').strftime('%Y%m%d')
        
        # Find matching file
        signal_file = None
        for file in os.listdir(results_dir):
            if file.startswith(test['file_pattern']) and file.endswith('.xlsx'):
                signal_file = os.path.join(results_dir, file)
                break
        
        if signal_file:
            print(f"\nAnalyzing {test['date']} (SMA20 Breadth: {test['breadth']}%)")
            print(f"File: {os.path.basename(signal_file)}")
            
            result = analyzer.analyze_performance(signal_file, datetime.strptime(test['date'], '%Y-%m-%d'))
            if result:
                result['sma20_breadth'] = test['breadth']
                results.append(result)
                print(f"Success Rate: {result['success_rate']:.1f}%")
                print(f"Average PnL: {result['avg_pnl']:.2f}%")
    
    # Summary
    print("\n" + "="*80)
    print("LONG REVERSAL PERFORMANCE vs SMA20 BREADTH")
    print("="*80)
    
    if results:
        df = pd.DataFrame(results)
        df = df.sort_values('sma20_breadth')
        
        print(f"\n{'Date':<12} {'SMA20':<8} {'Success%':<10} {'Avg PnL%':<10} {'Signals':<8}")
        print("-"*50)
        
        for _, row in df.iterrows():
            print(f"{row['date']:<12} {row['sma20_breadth']:<8.1f} "
                  f"{row['success_rate']:<10.1f} {row['avg_pnl']:<10.2f} {row['total_signals']:<8}")
        
        # Correlation
        corr_breadth_success = df['sma20_breadth'].corr(df['success_rate'])
        corr_breadth_pnl = df['sma20_breadth'].corr(df['avg_pnl'])
        
        print(f"\nCorrelation SMA20 vs Success Rate: {corr_breadth_success:.3f}")
        print(f"Correlation SMA20 vs Avg PnL: {corr_breadth_pnl:.3f}")
    
    return results

if __name__ == "__main__":
    print("Analyzing Long Reversal Performance vs SMA20 Breadth...")
    print("-" * 60)
    
    results = analyze_specific_dates()