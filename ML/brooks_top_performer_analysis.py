#!/usr/bin/env python
"""
Brooks Strategy Top Performer Analysis
=====================================
This script identifies common characteristics among top-performing tickers 
from Brooks Higher Probability LONG Reversal strategy to improve stock selection 
and portfolio allocation.

Features:
- Analyzes past performance of all strategy tickers using Zerodha data
- Identifies top N performers and compares their characteristics
- Extracts common patterns among winners (risk-reward, volume, etc.)
- Builds a scoring model for future allocation decisions
- Generates comprehensive report with actionable insights
- Provides visualization of key characteristics for top performers

Author: Claude Code Assistant
Created: 2025-05-30
"""

import os
import sys
import pandas as pd
import numpy as np
import datetime
import argparse
import logging
import glob
import re
import time
import json
import pytz
from typing import Dict, List, Tuple, Optional, Any
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from bs4 import BeautifulSoup

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from parent directory
try:
    from user_context_manager import get_context_manager, get_user_data_handler, UserCredentials
    USER_CONTEXT_AVAILABLE = True
except ImportError:
    USER_CONTEXT_AVAILABLE = False

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'brooks_top_performer_analysis.log'))
    ]
)
logger = logging.getLogger(__name__)

class BrooksTopPerformerAnalyzer:
    """Analyze characteristics of top-performing tickers from Brooks strategy"""
    
    def __init__(self, user_name="Sai", top_n=10):
        """Initialize the analyzer with user credentials"""
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.daily_dir = os.path.join(os.path.dirname(self.script_dir), "Daily")
        self.results_dir_source = os.path.join(self.daily_dir, "results")
        self.results_dir = os.path.join(self.script_dir, "results")
        self.user_name = user_name
        self.top_n = top_n
        
        # Create results directory if it doesn't exist
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Initialize user context and Zerodha connection
        self.data_handler = self._initialize_data_handler()
        
        # Additional market data metrics to extract
        self.additional_metrics = [
            'volume_ratio',        # Volume compared to 20-day average
            'body_ratio',          # Candle body size compared to 20-day average
            'price_to_sma20',      # Price relative to 20-day SMA
            'price_to_sma50',      # Price relative to 50-day SMA
            'atr_percent',         # ATR as percentage of price
            'adx',                 # Average Directional Index (trend strength)
            'rsi',                 # Relative Strength Index
            'sector',              # Stock sector/industry
            'market_cap'           # Market capitalization size
        ]
        
        logger.info(f"Initialized Brooks Top Performer Analyzer for user: {user_name}")
        logger.info(f"Will analyze top {top_n} performers")
    
    def _initialize_data_handler(self):
        """Initialize data handler with user credentials"""
        try:
            if USER_CONTEXT_AVAILABLE:
                # Set up user context
                context_manager = get_context_manager()
                
                # Load credentials from config.ini
                user_credentials = self._load_user_credentials()
                
                if user_credentials:
                    # Set current user context
                    context_manager.set_current_user(self.user_name, user_credentials)
                    
                    # Get data handler for current user
                    data_handler = get_user_data_handler()
                    
                    if data_handler and hasattr(data_handler, 'kite'):
                        logger.info(f"Successfully initialized Zerodha data handler for user: {self.user_name}")
                        logger.info(f"Using API Key: {data_handler.api_key[:8]}...")
                        return data_handler
            
            # Fallback to direct ZerodhaHandler if user context is not available
            logger.warning("User context not available, falling back to direct ZerodhaHandler")
            from zerodha_handler import get_zerodha_handler
            return get_zerodha_handler()
            
        except Exception as e:
            logger.error(f"Failed to initialize data handler: {e}")
            raise
    
    def _load_user_credentials(self) -> Optional[UserCredentials]:
        """Load user credentials from config.ini"""
        try:
            config_path = os.path.join(self.daily_dir, 'config.ini')
            
            if not os.path.exists(config_path):
                logger.error(f"Config file not found: {config_path}")
                return None
            
            import configparser
            config = configparser.ConfigParser()
            config.read(config_path)
            
            credential_section = f'API_CREDENTIALS_{self.user_name}'
            if credential_section not in config.sections():
                logger.error(f"No credentials found for user {self.user_name}")
                return None
            
            api_key = config.get(credential_section, 'api_key')
            api_secret = config.get(credential_section, 'api_secret')
            access_token = config.get(credential_section, 'access_token')
            
            if not all([api_key, api_secret, access_token]):
                logger.error(f"Incomplete credentials for user {self.user_name}")
                return None
            
            return UserCredentials(
                name=self.user_name,
                api_key=api_key,
                api_secret=api_secret,
                access_token=access_token
            )
            
        except Exception as e:
            logger.error(f"Error loading user credentials: {e}")
            return None
    
    def get_brooks_files(self) -> List[Tuple[str, datetime.datetime]]:
        """Get all Brooks Higher Probability LONG Reversal files sorted by date"""
        try:
            # First try Excel files
            files = glob.glob(os.path.join(self.results_dir_source, "Brooks_Higher_Probability_LONG_Reversal_*.xlsx"))
            
            # If no Excel files, look for HTML files in Daily/Detailed_Analysis
            if not files:
                html_dir = os.path.join(self.daily_dir, "Detailed_Analysis")
                files = glob.glob(os.path.join(html_dir, "Higher_Probability_LONG_Analysis_*.html"))
                # Exclude weekly files
                files = [f for f in files if "Weekly" not in f]
            
            file_dates = []
            for file_path in files:
                filename = os.path.basename(file_path)
                
                # Try Excel pattern first
                date_match = re.search(r'Brooks_Higher_Probability_LONG_Reversal_(\d{2})_(\d{2})_(\d{4})_(\d{2})_(\d{2})\.xlsx', filename)
                
                # Try HTML pattern if Excel didn't match
                if not date_match:
                    # Pattern: Higher_Probability_LONG_Analysis_DD_MM_YYYY_HH-MM.html
                    date_match = re.search(r'Higher_Probability_LONG_Analysis_(\d{2})_(\d{2})_(\d{4})_(\d{2})-(\d{2})\.html', filename)
                
                if date_match:
                    day, month, year, hour, minute = date_match.groups()
                    scan_date = datetime.datetime(int(year), int(month), int(day), int(hour), int(minute))
                    file_dates.append((file_path, scan_date))
            
            # Sort by date
            file_dates.sort(key=lambda x: x[1])
            
            logger.info(f"Found {len(file_dates)} Brooks strategy files")
            return file_dates
            
        except Exception as e:
            logger.error(f"Error getting Brooks files: {e}")
            return []
    
    def read_brooks_file(self, file_path: str) -> List[Dict]:
        """Read ticker data from a Brooks strategy file (Excel or HTML)"""
        try:
            if file_path.endswith('.xlsx'):
                return self._read_excel_file(file_path)
            elif file_path.endswith('.html'):
                return self._read_html_file(file_path)
            else:
                logger.warning(f"Unsupported file format: {file_path}")
                return []
                
        except Exception as e:
            logger.error(f"Error reading Brooks file {file_path}: {e}")
            return []
    
    def _read_excel_file(self, file_path: str) -> List[Dict]:
        """Read ticker data from Excel file"""
        try:
            # Read the Excel file
            df = pd.read_excel(file_path)
            
            if df.empty:
                logger.warning(f"Empty file: {os.path.basename(file_path)}")
                return []
            
            # Extract relevant columns
            required_cols = ['Ticker', 'Entry_Price', 'Stop_Loss', 'Target1', 'Risk_Reward_Ratio']
            
            # Check if required columns exist
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                logger.warning(f"Missing columns in {os.path.basename(file_path)}: {missing_cols}")
                # Try alternative column names
                col_mapping = {
                    'Entry_Price': ['Entry Price', 'EntryPrice', 'entry_price'],
                    'Stop_Loss': ['Stop Loss', 'StopLoss', 'stop_loss', 'SL'],
                    'Target1': ['Target', 'Target 1', 'target1', 'Target_1'],
                    'Risk_Reward_Ratio': ['Risk Reward Ratio', 'RiskRewardRatio', 'R:R', 'RR']
                }
                
                for std_col, alt_cols in col_mapping.items():
                    if std_col not in df.columns:
                        for alt_col in alt_cols:
                            if alt_col in df.columns:
                                df = df.rename(columns={alt_col: std_col})
                                break
            
            # Extract tickers and their strategy data
            strategy_data = []
            for _, row in df.iterrows():
                if pd.notna(row.get('Ticker')):
                    ticker_data = {
                        'ticker': str(row['Ticker']).strip().upper(),
                        'entry_price': float(row.get('Entry_Price', 0)) if pd.notna(row.get('Entry_Price')) else 0,
                        'stop_loss': float(row.get('Stop_Loss', 0)) if pd.notna(row.get('Stop_Loss')) else 0,
                        'target1': float(row.get('Target1', 0)) if pd.notna(row.get('Target1')) else 0,
                        'risk_reward_ratio': float(row.get('Risk_Reward_Ratio', 0)) if pd.notna(row.get('Risk_Reward_Ratio')) else 0
                    }
                    
                    # Extract additional metrics if available
                    for metric in self.additional_metrics:
                        if metric in df.columns and pd.notna(row.get(metric)):
                            ticker_data[metric] = float(row.get(metric, 0))
                    
                    strategy_data.append(ticker_data)
            
            logger.info(f"Read {len(strategy_data)} tickers from {os.path.basename(file_path)}")
            return strategy_data
            
        except Exception as e:
            logger.error(f"Error reading Excel file {file_path}: {e}")
            return []
    
    def _read_html_file(self, file_path: str) -> List[Dict]:
        """Read ticker data from HTML file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            
            strategy_data = []
            
            # Find all ticker cards
            ticker_cards = soup.find_all('div', class_='ticker-card')
            
            for card in ticker_cards:
                # Extract ticker symbol
                ticker_elem = card.find('h3')
                if not ticker_elem:
                    continue
                    
                ticker_text = ticker_elem.text.strip()
                # Extract ticker from format like "TICKER - Company Name"
                ticker = ticker_text.split(' - ')[0].strip()
                
                # Extract metrics from the card
                ticker_data = {
                    'ticker': ticker.upper(),
                    'entry_price': 0,
                    'stop_loss': 0,
                    'target1': 0,
                    'risk_reward_ratio': 0
                }
                
                # Look for metric rows in the card
                metric_rows = card.find_all('div', class_='metric-row')
                
                for row in metric_rows:
                    label = row.find('span', class_='metric-label')
                    value = row.find('span', class_='metric-value')
                    
                    if label and value:
                        label_text = label.text.strip().lower()
                        value_text = value.text.strip()
                        
                        # Try to extract numeric value
                        try:
                            # Remove currency symbols and commas
                            numeric_value = float(value_text.replace('₹', '').replace(',', '').strip())
                            
                            if 'entry' in label_text:
                                ticker_data['entry_price'] = numeric_value
                            elif 'stop' in label_text or 'sl' in label_text:
                                ticker_data['stop_loss'] = numeric_value
                            elif 'target' in label_text:
                                ticker_data['target1'] = numeric_value
                            elif 'risk' in label_text and 'reward' in label_text:
                                ticker_data['risk_reward_ratio'] = numeric_value
                        except ValueError:
                            pass
                
                # Only add if we have valid entry price
                if ticker_data['entry_price'] > 0:
                    strategy_data.append(ticker_data)
            
            logger.info(f"Read {len(strategy_data)} tickers from HTML file {os.path.basename(file_path)}")
            return strategy_data
            
        except Exception as e:
            logger.error(f"Error reading HTML file {file_path}: {e}")
            return []
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get current price for a ticker from Zerodha"""
        try:
            # Try to use data_handler's fetch_current_price method
            if hasattr(self.data_handler, 'fetch_current_price'):
                price = self.data_handler.fetch_current_price(ticker)
                if price is not None:
                    return price
            
            # Fallback to kite.ltp
            exchange = "NSE"  # Use NSE for Indian equities
            instrument = f"{exchange}:{ticker}"
            
            ltp_data = self.data_handler.kite.ltp(instrument)
            if ltp_data and instrument in ltp_data:
                price = ltp_data[instrument]['last_price']
                return price
            
            logger.warning(f"Could not get current price for {ticker}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting current price for {ticker}: {e}")
            return None
    
    def get_ticker_data(self, ticker: str, from_date: datetime.datetime, to_date: datetime.datetime = None, interval: str = "day") -> Optional[pd.DataFrame]:
        """Get historical OHLCV data for a ticker from Zerodha"""
        try:
            # Set to_date to current date if not provided
            if to_date is None:
                to_date = datetime.datetime.now()

            # Convert datetime objects to date strings for Zerodha API
            from_date_str = from_date.strftime('%Y-%m-%d')
            to_date_str = to_date.strftime('%Y-%m-%d')

            # Fetch historical data with specified interval
            historical_data = self.data_handler.fetch_historical_data(
                ticker,
                interval=interval,
                from_date=from_date_str,
                to_date=to_date_str
            )

            # Properly check if historical_data is empty
            min_required = 5 if interval == "day" else 20  # Need more data points for hourly
            if historical_data is None or (isinstance(historical_data, list) and len(historical_data) < min_required) or (isinstance(historical_data, pd.DataFrame) and historical_data.empty):
                logger.warning(f"Insufficient historical data for {ticker} (interval: {interval})")
                return None

            # Convert to DataFrame if it's not already
            if not isinstance(historical_data, pd.DataFrame):
                df = pd.DataFrame(historical_data)
            else:
                df = historical_data

            # Check if DataFrame is empty after conversion
            if df.empty or len(df) < min_required:
                logger.warning(f"Insufficient historical data after conversion for {ticker} (interval: {interval})")
                return None

            # Standardize column names
            columns_map = {
                'date': 'Date',
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }

            df = df.rename(columns={k: v for k, v in columns_map.items() if k in df.columns})

            # Ensure Date is datetime
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')
            df = df.reset_index(drop=True)

            return df

        except Exception as e:
            logger.error(f"Error getting historical data for {ticker}: {e}")
            return None
    
    def get_hourly_performance_after_signal(self, ticker: str, signal_date: datetime.datetime, hours_to_analyze: int = 24) -> Dict:
        """Get hourly performance data for a ticker after signal generation"""
        try:
            # Get hourly data starting from signal date
            # Need historical data for SMA calculation
            from_date = signal_date - datetime.timedelta(days=10)  # Get extra data for SMA20
            to_date = signal_date + datetime.timedelta(hours=hours_to_analyze + 6)  # Add buffer for market hours
            hourly_data = self.get_ticker_data(ticker, from_date, to_date, interval="60minute")
            
            if hourly_data is None or hourly_data.empty:
                return {
                    'ticker': ticker,
                    'signal_date': signal_date,
                    'hourly_data_available': False
                }
            
            # Calculate SMA20 for hourly data
            hourly_data['SMA20'] = hourly_data['Close'].rolling(window=20).mean()
            
            # Ensure signal_date is timezone aware if data is timezone aware
            if hourly_data['Date'].dt.tz is not None and signal_date.tzinfo is None:
                # Add IST timezone to signal_date
                ist = pytz.timezone('Asia/Kolkata')
                signal_date = ist.localize(signal_date)
            
            # Get previous day's data to calculate H2
            prev_day_end = signal_date.replace(hour=15, minute=30, second=0)
            prev_day_start = prev_day_end - datetime.timedelta(days=1)
            
            # Convert to pandas datetime for proper comparison
            hourly_data['Date'] = pd.to_datetime(hourly_data['Date'])
            
            # Make comparisons timezone-naive if needed
            if hourly_data['Date'].dt.tz is not None:
                prev_day_data = hourly_data[(hourly_data['Date'].dt.tz_localize(None) >= prev_day_start.replace(tzinfo=None)) & 
                                           (hourly_data['Date'].dt.tz_localize(None) <= prev_day_end.replace(tzinfo=None))]
            else:
                prev_day_data = hourly_data[(hourly_data['Date'] >= prev_day_start) & (hourly_data['Date'] <= prev_day_end)]
            
            # Calculate H2 (high of second half of previous day - after 12:15 PM)
            h2_threshold_time = prev_day_start.replace(hour=12, minute=15)
            if hourly_data['Date'].dt.tz is not None:
                second_half_data = prev_day_data[prev_day_data['Date'].dt.tz_localize(None) >= h2_threshold_time.replace(tzinfo=None)]
            else:
                second_half_data = prev_day_data[prev_day_data['Date'] >= h2_threshold_time]
            h2_level = second_half_data['High'].max() if not second_half_data.empty else None
            
            # Find the first candle after signal time
            if hourly_data['Date'].dt.tz is not None:
                hourly_after_signal = hourly_data[hourly_data['Date'].dt.tz_localize(None) >= signal_date.replace(tzinfo=None)].copy()
            else:
                hourly_after_signal = hourly_data[hourly_data['Date'] >= signal_date].copy()
            
            if hourly_after_signal.empty:
                return {
                    'ticker': ticker,
                    'signal_date': signal_date,
                    'hourly_data_available': False
                }
            
            # Get entry price (first hourly candle after signal)
            entry_candle = hourly_after_signal.iloc[0]
            entry_price = entry_candle['Open']
            entry_time = entry_candle['Date']
            
            # Analyze performance over next hours
            performance_metrics = {
                'ticker': ticker,
                'signal_date': signal_date,
                'entry_time': entry_time,
                'entry_price': entry_price,
                'h2_level': h2_level,
                'hourly_data_available': True,
                'hourly_performance': [],
                'sma20_violations': 0,
                'hours_above_sma20': 0,
                'h2_breakouts': 0,
                'consecutive_h2_breaks': 0,
                'max_consecutive_h2_breaks': 0
            }
            
            # Track hourly performance
            consecutive_h2_count = 0
            for i, (idx, candle) in enumerate(hourly_after_signal.iterrows()):
                if i >= hours_to_analyze:
                    break
                    
                hours_since_entry = i + 1
                high_pct = ((candle['High'] - entry_price) / entry_price) * 100
                low_pct = ((candle['Low'] - entry_price) / entry_price) * 100
                close_pct = ((candle['Close'] - entry_price) / entry_price) * 100
                
                # Check SMA20 position
                above_sma20 = candle['Low'] > candle['SMA20'] if pd.notna(candle['SMA20']) else None
                if above_sma20 is not None:
                    if above_sma20:
                        performance_metrics['hours_above_sma20'] += 1
                    else:
                        performance_metrics['sma20_violations'] += 1
                
                # Check H2 breakout
                h2_breakout = False
                if h2_level is not None:
                    h2_breakout = candle['High'] > h2_level
                    if h2_breakout:
                        performance_metrics['h2_breakouts'] += 1
                        consecutive_h2_count += 1
                        performance_metrics['max_consecutive_h2_breaks'] = max(
                            performance_metrics['max_consecutive_h2_breaks'], 
                            consecutive_h2_count
                        )
                    else:
                        consecutive_h2_count = 0
                
                hourly_perf = {
                    'hour': hours_since_entry,
                    'time': candle['Date'],
                    'high_pct': high_pct,
                    'low_pct': low_pct,
                    'close_pct': close_pct,
                    'volume': candle['Volume'],
                    'volatility': candle['High'] - candle['Low'],
                    'sma20': candle['SMA20'],
                    'above_sma20': above_sma20,
                    'h2_breakout': h2_breakout
                }
                
                performance_metrics['hourly_performance'].append(hourly_perf)
            
            # Calculate summary metrics
            if performance_metrics['hourly_performance']:
                all_highs = [h['high_pct'] for h in performance_metrics['hourly_performance']]
                all_lows = [h['low_pct'] for h in performance_metrics['hourly_performance']]
                all_closes = [h['close_pct'] for h in performance_metrics['hourly_performance']]
                
                performance_metrics['max_profit_pct'] = max(all_highs)
                performance_metrics['max_drawdown_pct'] = min(all_lows)
                performance_metrics['hours_to_peak'] = all_highs.index(max(all_highs)) + 1
                performance_metrics['final_return_pct'] = all_closes[-1] if all_closes else 0
                
                # Calculate SMA20 and H2 pattern metrics
                total_hours = len(performance_metrics['hourly_performance'])
                performance_metrics['sma20_above_ratio'] = performance_metrics['hours_above_sma20'] / total_hours if total_hours > 0 else 0
                performance_metrics['h2_breakout_ratio'] = performance_metrics['h2_breakouts'] / total_hours if total_hours > 0 else 0
                
                # Identify best exit hour
                best_exit_hour = 1
                best_return = all_closes[0] if all_closes else 0
                for i, close_pct in enumerate(all_closes):
                    if close_pct > best_return:
                        best_return = close_pct
                        best_exit_hour = i + 1
                        
                performance_metrics['best_exit_hour'] = best_exit_hour
                performance_metrics['best_exit_return_pct'] = best_return
            
            return performance_metrics
            
        except Exception as e:
            logger.error(f"Error getting hourly performance for {ticker}: {e}")
            return {
                'ticker': ticker,
                'signal_date': signal_date,
                'hourly_data_available': False,
                'error': str(e)
            }
    
    def calculate_performance(self, ticker: str, entry_price: float, entry_date: datetime.datetime) -> Dict:
        """Calculate performance metrics for a ticker including hourly analysis"""
        try:
            # Get current price
            current_price = self.get_current_price(ticker)
            
            if current_price is None or entry_price <= 0:
                return {
                    'ticker': ticker,
                    'entry_price': entry_price,
                    'current_price': None,
                    'pnl_percent': None,
                    'status': 'Error'
                }
            
            # Calculate basic PnL
            pnl_percent = ((current_price - entry_price) / entry_price) * 100
            
            # Get hourly performance data after signal
            hourly_performance = self.get_hourly_performance_after_signal(ticker, entry_date, hours_to_analyze=24)
            
            # Get historical data for the ticker
            # Use data from 60 days before entry to current date
            from_date = entry_date - datetime.timedelta(days=60)
            historical_df = self.get_ticker_data(ticker, from_date)
            
            performance_data = {
                'ticker': ticker,
                'entry_price': entry_price,
                'entry_date': entry_date,
                'current_price': current_price,
                'pnl_percent': pnl_percent,
                'status': 'Profit' if pnl_percent > 0 else 'Loss',
                # Add hourly performance metrics
                'hourly_data_available': hourly_performance.get('hourly_data_available', False),
                'max_intraday_profit_pct': hourly_performance.get('max_profit_pct', None),
                'max_intraday_drawdown_pct': hourly_performance.get('max_drawdown_pct', None),
                'best_exit_hour': hourly_performance.get('best_exit_hour', None),
                'best_exit_return_pct': hourly_performance.get('best_exit_return_pct', None),
                'hours_to_peak': hourly_performance.get('hours_to_peak', None),
                'day1_return_pct': hourly_performance.get('final_return_pct', None),
                # SMA20 and H2 pattern metrics
                'sma20_violations': hourly_performance.get('sma20_violations', None),
                'sma20_above_ratio': hourly_performance.get('sma20_above_ratio', None),
                'h2_breakouts': hourly_performance.get('h2_breakouts', None),
                'h2_breakout_ratio': hourly_performance.get('h2_breakout_ratio', None),
                'max_consecutive_h2_breaks': hourly_performance.get('max_consecutive_h2_breaks', None)
            }
            
            # Extract additional metrics from historical data
            if historical_df is not None:
                # Find the row closest to entry date
                entry_idx = None
                for idx, row in historical_df.iterrows():
                    if row['Date'].date() >= entry_date.date():
                        entry_idx = idx
                        break
                
                if entry_idx is not None:
                    # Calculate technical indicators at entry
                    entry_row = historical_df.iloc[entry_idx]
                    
                    # 1. Calculate SMA values
                    if entry_idx >= 20:
                        sma20 = historical_df.iloc[entry_idx-20:entry_idx]['Close'].mean()
                        performance_data['price_to_sma20_percent'] = ((entry_row['Close'] - sma20) / sma20) * 100
                    
                    if entry_idx >= 50:
                        sma50 = historical_df.iloc[entry_idx-50:entry_idx]['Close'].mean()
                        performance_data['price_to_sma50_percent'] = ((entry_row['Close'] - sma50) / sma50) * 100
                    
                    # 2. Calculate volume metrics
                    if entry_idx >= 20 and 'Volume' in historical_df.columns:
                        volume_data = historical_df.iloc[entry_idx-20:entry_idx]['Volume']
                        if not volume_data.empty:
                            avg_volume = volume_data.mean()
                            if pd.notnull(avg_volume) and avg_volume > 0 and pd.notnull(entry_row.get('Volume')):
                                performance_data['volume_ratio'] = entry_row['Volume'] / avg_volume
                    
                    # 3. Calculate volatility metrics
                    if entry_idx >= 14:
                        try:
                            # ATR calculation
                            atr_window = historical_df.iloc[entry_idx-14:entry_idx+1]
                            high_low = atr_window['High'] - atr_window['Low']
                            high_close = abs(atr_window['High'] - atr_window['Close'].shift(1))
                            low_close = abs(atr_window['Low'] - atr_window['Close'].shift(1))

                            # Handle NaN values
                            high_low = high_low.fillna(0)
                            high_close = high_close.fillna(0)
                            low_close = low_close.fillna(0)

                            true_ranges = pd.DataFrame({'HL': high_low, 'HC': high_close, 'LC': low_close})
                            true_range = true_ranges.max(axis=1)
                            atr = true_range.mean()

                            # ATR as percentage of price
                            if pd.notnull(atr) and atr > 0 and entry_row['Close'] > 0:
                                performance_data['atr_percent'] = (atr / entry_row['Close']) * 100
                        except Exception as atr_err:
                            logger.debug(f"Could not calculate ATR for {ticker}: {atr_err}")
                    
                    # 4. Calculate candle body ratio
                    if 'Open' in entry_row and pd.notnull(entry_row['Open']) and entry_row['Close'] != 0:
                        performance_data['body_size_percent'] = abs(entry_row['Close'] - entry_row['Open']) / entry_row['Close'] * 100

                    if entry_idx >= 20 and 'Open' in historical_df.columns:
                        # Safely calculate body sizes
                        try:
                            body_sizes = abs(historical_df.iloc[entry_idx-20:entry_idx]['Close'] -
                                          historical_df.iloc[entry_idx-20:entry_idx]['Open'])
                            avg_body_size = body_sizes.mean()
                            if pd.notnull(avg_body_size) and avg_body_size > 0:
                                current_body = abs(entry_row['Close'] - entry_row['Open'])
                                if pd.notnull(current_body):
                                    performance_data['body_ratio'] = current_body / avg_body_size
                        except Exception as body_err:
                            logger.debug(f"Could not calculate body ratio for {ticker}: {body_err}")
                    
                    # 5. Price movement after entry
                    subsequent_data = historical_df.iloc[entry_idx:].copy()
                    
                    # Calculate maximum drawdown
                    if not subsequent_data.empty:
                        rolling_max = subsequent_data['Close'].cummax()
                        drawdown = (subsequent_data['Close'] / rolling_max - 1.0) * 100
                        performance_data['max_drawdown'] = abs(drawdown.min())
                        
                        # Calculate days to reach maximum price
                        if len(subsequent_data) > 1:
                            max_price_idx = subsequent_data['Close'].idxmax()
                            if max_price_idx > entry_idx:
                                days_to_max = (subsequent_data.loc[max_price_idx, 'Date'] - entry_row['Date']).days
                                performance_data['days_to_max_price'] = days_to_max
            
            return performance_data
            
        except Exception as e:
            logger.error(f"Error calculating performance for {ticker}: {e}")
            return {
                'ticker': ticker,
                'entry_price': entry_price,
                'entry_date': entry_date,
                'current_price': None,
                'pnl_percent': None,
                'status': 'Error'
            }
    
    def analyze_top_performers(self) -> Dict:
        """Analyze characteristics of top performing tickers"""
        try:
            logger.info(f"Starting analysis of top {self.top_n} performers")
            
            # Get all Brooks strategy files
            brooks_files = self.get_brooks_files()
            
            if not brooks_files:
                logger.error("No Brooks strategy files found")
                return {}
            
            all_tickers = {}  # Dict to track unique tickers with their earliest entry
            
            # Process all files
            for file_path, scan_date in brooks_files:
                logger.info(f"Processing file: {os.path.basename(file_path)} - {scan_date.strftime('%Y-%m-%d')}")
                
                strategy_data = self.read_brooks_file(file_path)
                for ticker_data in strategy_data:
                    ticker = ticker_data['ticker']
                    entry_price = ticker_data['entry_price']
                    
                    # Only keep the earliest entry for each ticker
                    if ticker not in all_tickers or scan_date < all_tickers[ticker]['scan_date']:
                        all_tickers[ticker] = {
                            'ticker': ticker,
                            'entry_price': entry_price,
                            'scan_date': scan_date,
                            'file': os.path.basename(file_path),
                            'stop_loss': ticker_data['stop_loss'],
                            'target1': ticker_data['target1'],
                            'risk_reward_ratio': ticker_data['risk_reward_ratio']
                        }
                        
                        # Add any additional metrics found in the file
                        for metric in self.additional_metrics:
                            if metric in ticker_data:
                                all_tickers[ticker][metric] = ticker_data[metric]
            
            logger.info(f"Found {len(all_tickers)} unique tickers across all strategy files")
            
            # Calculate performance for each ticker
            performance_results = []
            
            for ticker, data in all_tickers.items():
                # Add a small delay to avoid API rate limits
                time.sleep(0.1)
                
                performance_data = self.calculate_performance(
                    ticker, 
                    data['entry_price'], 
                    data['scan_date']
                )
                
                # Merge with strategy data
                for key, value in data.items():
                    if key not in performance_data:
                        performance_data[key] = value
                        
                performance_results.append(performance_data)
            
            # Filter out tickers with errors
            valid_results = [r for r in performance_results if r.get('status') != 'Error']
            
            if not valid_results:
                logger.error("No valid performance results found")
                return {}
            
            # Sort by performance (PnL)
            valid_results.sort(key=lambda x: x.get('pnl_percent', 0), reverse=True)
            
            # Get top and bottom performers
            top_performers = valid_results[:self.top_n]
            bottom_performers = valid_results[-self.top_n:]
            
            # Analyze characteristics of top performers
            top_performer_analysis = self.analyze_characteristics(top_performers, bottom_performers)
            
            # Identify hourly success patterns
            hourly_patterns = self.identify_hourly_success_patterns(valid_results)
            top_performer_analysis['hourly_patterns'] = hourly_patterns
            
            # Generate Excel report
            excel_file = self.export_excel_report(valid_results, top_performers, bottom_performers, top_performer_analysis)
            
            # Generate visualizations
            chart_files = self.create_visualizations(valid_results, top_performers, bottom_performers, top_performer_analysis)
            
            # Print summary
            self.print_summary(top_performers, bottom_performers, top_performer_analysis)
            
            return {
                'all_results': valid_results,
                'top_performers': top_performers,
                'bottom_performers': bottom_performers,
                'analysis': top_performer_analysis,
                'excel_file': excel_file,
                'chart_files': chart_files
            }
            
        except Exception as e:
            logger.error(f"Error analyzing top performers: {e}")
            return {}
    
    def analyze_characteristics(self, top_performers: List[Dict], bottom_performers: List[Dict]) -> Dict:
        """Analyze characteristics that differentiate top performers from bottom performers"""
        try:
            analysis = {
                'key_metrics': {},
                'statistical_tests': {},
                'correlation_with_performance': {},
                'differentiating_factors': []
            }
            
            # Convert to DataFrame for easier analysis
            top_df = pd.DataFrame(top_performers)
            bottom_df = pd.DataFrame(bottom_performers)
            
            # 1. Calculate average metrics for both groups
            metrics_to_analyze = [
                'risk_reward_ratio',
                'volume_ratio',
                'body_ratio',
                'price_to_sma20_percent',
                'price_to_sma50_percent',
                'atr_percent',
                'body_size_percent',
                'max_drawdown',
                'days_to_max_price',
                # Hourly metrics
                'max_intraday_profit_pct',
                'max_intraday_drawdown_pct',
                'best_exit_hour',
                'best_exit_return_pct',
                'hours_to_peak',
                'day1_return_pct',
                # SMA20 and H2 metrics
                'sma20_violations',
                'sma20_above_ratio',
                'h2_breakouts',
                'h2_breakout_ratio',
                'max_consecutive_h2_breaks'
            ]
            
            for metric in metrics_to_analyze:
                if metric in top_df.columns and metric in bottom_df.columns:
                    top_values = top_df[metric].dropna()
                    bottom_values = bottom_df[metric].dropna()
                    
                    if len(top_values) > 0 and len(bottom_values) > 0:
                        # Calculate statistics
                        analysis['key_metrics'][metric] = {
                            'top_mean': top_values.mean(),
                            'top_median': top_values.median(),
                            'top_std': top_values.std(),
                            'bottom_mean': bottom_values.mean(),
                            'bottom_median': bottom_values.median(),
                            'bottom_std': bottom_values.std(),
                            'percent_difference': ((top_values.mean() - bottom_values.mean()) / bottom_values.mean() * 100) 
                                                if bottom_values.mean() != 0 else float('inf')
                        }
                        
                        # Run statistical test (t-test)
                        try:
                            t_stat, p_value = stats.ttest_ind(top_values, bottom_values, equal_var=False)
                            analysis['statistical_tests'][metric] = {
                                't_statistic': t_stat,
                                'p_value': p_value,
                                'significant': p_value < 0.05
                            }
                        except:
                            pass
            
            # 2. Calculate correlation of each metric with performance
            all_results_df = pd.concat([top_df, bottom_df])
            
            for metric in metrics_to_analyze:
                if metric in all_results_df.columns:
                    # Calculate correlation with PnL
                    if 'pnl_percent' in all_results_df.columns:
                        try:
                            # Filter out non-numeric and NaN values
                            valid_data = all_results_df[[metric, 'pnl_percent']].dropna()

                            # Only calculate if we have enough data points
                            if len(valid_data) >= 5:
                                correlation = valid_data.corr().iloc[0, 1]
                                # Check for NaN correlation (happens with constant values)
                                if pd.notnull(correlation):
                                    analysis['correlation_with_performance'][metric] = correlation
                        except Exception as corr_err:
                            logger.debug(f"Could not calculate correlation for {metric}: {corr_err}")
            
            # 3. Identify key differentiating factors
            differentiating_factors = []
            
            for metric, stats_data in analysis['statistical_tests'].items():
                if stats_data.get('significant', False):
                    # This metric significantly differs between top and bottom performers
                    metric_data = analysis['key_metrics'][metric]
                    correlation = analysis['correlation_with_performance'].get(metric, 0)
                    
                    difference_direction = "higher" if metric_data['top_mean'] > metric_data['bottom_mean'] else "lower"
                    
                    factor = {
                        'metric': metric,
                        'difference_direction': difference_direction,
                        'percent_difference': metric_data['percent_difference'],
                        'correlation_with_performance': correlation,
                        'p_value': stats_data['p_value'],
                        'top_mean': metric_data['top_mean'],
                        'bottom_mean': metric_data['bottom_mean']
                    }
                    
                    differentiating_factors.append(factor)
            
            # Sort differentiating factors by absolute correlation with performance
            differentiating_factors.sort(key=lambda x: abs(x['correlation_with_performance']), reverse=True)
            analysis['differentiating_factors'] = differentiating_factors
            
            # 4. Calculate portfolio allocation scores based on key factors
            analysis['allocation_formula'] = self.derive_allocation_formula(differentiating_factors)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing characteristics: {e}")
            return {}
    
    def identify_hourly_success_patterns(self, all_results: List[Dict]) -> Dict:
        """Identify patterns in hourly data that correlate with success"""
        try:
            # Filter results with hourly data
            hourly_results = [r for r in all_results if r.get('hourly_data_available', False)]
            
            if not hourly_results:
                logger.warning("No results with hourly data available")
                return {}
            
            # Convert to DataFrame for analysis
            df = pd.DataFrame(hourly_results)
            
            # Define success criteria
            success_threshold = df['pnl_percent'].quantile(0.75)  # Top 25%
            df['successful'] = df['pnl_percent'] > success_threshold
            
            patterns = {
                'total_analyzed': len(hourly_results),
                'successful_count': len(df[df['successful']]),
                'success_rate': len(df[df['successful']]) / len(df) * 100
            }
            
            # Analyze best exit hours
            if 'best_exit_hour' in df.columns:
                successful_exit_hours = df[df['successful']]['best_exit_hour'].dropna()
                if len(successful_exit_hours) > 0:
                    patterns['avg_best_exit_hour_success'] = successful_exit_hours.mean()
                    patterns['most_common_exit_hour'] = successful_exit_hours.mode().iloc[0] if not successful_exit_hours.mode().empty else None
            
            # Analyze intraday characteristics
            hourly_metrics = ['max_intraday_profit_pct', 'max_intraday_drawdown_pct', 
                            'hours_to_peak', 'day1_return_pct']
            
            for metric in hourly_metrics:
                if metric in df.columns:
                    success_values = df[df['successful']][metric].dropna()
                    fail_values = df[~df['successful']][metric].dropna()
                    
                    if len(success_values) > 0 and len(fail_values) > 0:
                        patterns[f'{metric}_success_avg'] = success_values.mean()
                        patterns[f'{metric}_fail_avg'] = fail_values.mean()
                        
                        # Statistical test
                        t_stat, p_value = stats.ttest_ind(success_values, fail_values, equal_var=False)
                        patterns[f'{metric}_p_value'] = p_value
                        patterns[f'{metric}_significant'] = p_value < 0.05
            
            # Test SMA20 and H2 theory
            sma20_h2_analysis = self.test_sma20_h2_theory(df)
            patterns.update(sma20_h2_analysis)
            
            # Identify tickers that consistently perform well in first few hours
            if 'day1_return_pct' in df.columns:
                early_winners = df[(df['day1_return_pct'] > 2) & (df['pnl_percent'] > 5)]
                if len(early_winners) > 0:
                    patterns['early_winner_tickers'] = early_winners['ticker'].tolist()
                    patterns['early_winner_count'] = len(early_winners)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error identifying hourly success patterns: {e}")
            return {}
    
    def test_sma20_h2_theory(self, df: pd.DataFrame) -> Dict:
        """Test the theory that successful stocks stay above SMA20 and break H2 consistently"""
        try:
            theory_results = {}
            
            # Check if we have the required columns
            required_cols = ['sma20_above_ratio', 'h2_breakout_ratio', 'max_consecutive_h2_breaks', 'successful']
            if not all(col in df.columns for col in required_cols):
                logger.warning("Missing required columns for SMA20/H2 theory analysis")
                return theory_results
            
            # Separate successful and unsuccessful trades
            successful_df = df[df['successful']]
            unsuccessful_df = df[~df['successful']]
            
            # 1. Analyze SMA20 behavior
            if 'sma20_above_ratio' in df.columns:
                success_sma20_ratio = successful_df['sma20_above_ratio'].dropna()
                fail_sma20_ratio = unsuccessful_df['sma20_above_ratio'].dropna()
                
                if len(success_sma20_ratio) > 0 and len(fail_sma20_ratio) > 0:
                    theory_results['sma20_theory'] = {
                        'success_avg_above_sma20': success_sma20_ratio.mean() * 100,
                        'fail_avg_above_sma20': fail_sma20_ratio.mean() * 100,
                        'success_always_above_sma20': len(successful_df[successful_df['sma20_violations'] == 0]),
                        'success_always_above_sma20_pct': len(successful_df[successful_df['sma20_violations'] == 0]) / len(successful_df) * 100 if len(successful_df) > 0 else 0
                    }
                    
                    # Statistical test
                    t_stat, p_value = stats.ttest_ind(success_sma20_ratio, fail_sma20_ratio, equal_var=False)
                    theory_results['sma20_theory']['p_value'] = p_value
                    theory_results['sma20_theory']['significant'] = p_value < 0.05
            
            # 2. Analyze H2 breakout behavior
            if 'h2_breakout_ratio' in df.columns:
                success_h2_ratio = successful_df['h2_breakout_ratio'].dropna()
                fail_h2_ratio = unsuccessful_df['h2_breakout_ratio'].dropna()
                
                if len(success_h2_ratio) > 0 and len(fail_h2_ratio) > 0:
                    theory_results['h2_theory'] = {
                        'success_avg_h2_breakouts': success_h2_ratio.mean() * 100,
                        'fail_avg_h2_breakouts': fail_h2_ratio.mean() * 100,
                        'success_avg_consecutive_h2': successful_df['max_consecutive_h2_breaks'].mean(),
                        'fail_avg_consecutive_h2': unsuccessful_df['max_consecutive_h2_breaks'].mean()
                    }
                    
                    # Statistical test
                    t_stat, p_value = stats.ttest_ind(success_h2_ratio, fail_h2_ratio, equal_var=False)
                    theory_results['h2_theory']['p_value'] = p_value
                    theory_results['h2_theory']['significant'] = p_value < 0.05
            
            # 3. Combined theory: Stocks that both stay above SMA20 AND break H2
            if 'sma20_above_ratio' in df.columns and 'h2_breakout_ratio' in df.columns:
                # Define "strong pattern" tickers
                strong_pattern = df[(df['sma20_above_ratio'] > 0.8) & (df['h2_breakout_ratio'] > 0.5)]
                
                theory_results['combined_theory'] = {
                    'strong_pattern_count': len(strong_pattern),
                    'strong_pattern_success_rate': len(strong_pattern[strong_pattern['successful']]) / len(strong_pattern) * 100 if len(strong_pattern) > 0 else 0,
                    'overall_success_rate': len(df[df['successful']]) / len(df) * 100,
                    'theory_validity': 'Strong' if len(strong_pattern[strong_pattern['successful']]) / len(strong_pattern) > 0.7 else 'Moderate' if len(strong_pattern[strong_pattern['successful']]) / len(strong_pattern) > 0.5 else 'Weak' if len(strong_pattern) > 0 else 'Insufficient Data'
                }
            
            return theory_results
            
        except Exception as e:
            logger.error(f"Error testing SMA20/H2 theory: {e}")
            return {}
    
    def derive_allocation_formula(self, differentiating_factors: List[Dict]) -> Dict:
        """Derive a formula for portfolio allocation based on key differentiating factors"""
        try:
            if not differentiating_factors:
                return {
                    'description': "No significant differentiating factors found",
                    'weights': {},
                    'scoring_function': "Default equal allocation"
                }
            
            # Use the top 3 differentiating factors or fewer if not available
            top_factors = differentiating_factors[:min(3, len(differentiating_factors))]
            
            # Assign weights based on correlation with performance
            total_correlation = sum(abs(f['correlation_with_performance']) for f in top_factors)
            
            if total_correlation == 0:
                weights = {f['metric']: 1.0 / len(top_factors) for f in top_factors}
            else:
                weights = {f['metric']: abs(f['correlation_with_performance']) / total_correlation for f in top_factors}
            
            # Create a description of the scoring function
            factor_descriptions = []
            
            for factor in top_factors:
                metric = factor['metric']
                direction = factor['difference_direction']
                weight = weights[metric]
                
                # Handle different metric types appropriately
                if direction == "higher":
                    factor_descriptions.append(f"Higher {metric} (weight: {weight:.2f})")
                else:
                    factor_descriptions.append(f"Lower {metric} (weight: {weight:.2f})")
            
            description = "Portfolio allocation score based on: " + ", ".join(factor_descriptions)
            
            return {
                'description': description,
                'weights': weights,
                'factors': top_factors,
                'scoring_function': "Weighted average of normalized factor values"
            }
            
        except Exception as e:
            logger.error(f"Error deriving allocation formula: {e}")
            return {
                'description': f"Error: {str(e)}",
                'weights': {},
                'scoring_function': "Default equal allocation"
            }
    
    def export_excel_report(self, all_results: List[Dict], top_performers: List[Dict], 
                          bottom_performers: List[Dict], analysis: Dict) -> str:
        """Export analysis results to Excel file"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_file = os.path.join(self.results_dir, f"brooks_top_performer_analysis_{timestamp}.xlsx")
            
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                # 1. All Results Sheet
                all_df = pd.DataFrame(all_results)
                if 'scan_date' in all_df.columns:
                    all_df['scan_date'] = all_df['scan_date'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else None)
                
                all_df.sort_values('pnl_percent', ascending=False, inplace=True)
                all_df.to_excel(writer, sheet_name='All_Results', index=False)
                
                # 2. Top Performers Sheet
                top_df = pd.DataFrame(top_performers)
                if 'scan_date' in top_df.columns:
                    top_df['scan_date'] = top_df['scan_date'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else None)
                
                top_df.to_excel(writer, sheet_name='Top_Performers', index=False)
                
                # 3. Bottom Performers Sheet
                bottom_df = pd.DataFrame(bottom_performers)
                if 'scan_date' in bottom_df.columns:
                    bottom_df['scan_date'] = bottom_df['scan_date'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else None)
                
                bottom_df.to_excel(writer, sheet_name='Bottom_Performers', index=False)
                
                # 4. Key Metrics Comparison Sheet
                if 'key_metrics' in analysis:
                    metrics_data = []
                    
                    for metric, values in analysis['key_metrics'].items():
                        row = {
                            'Metric': metric,
                            'Top_Mean': values.get('top_mean', 0),
                            'Top_Median': values.get('top_median', 0),
                            'Bottom_Mean': values.get('bottom_mean', 0),
                            'Bottom_Median': values.get('bottom_median', 0),
                            'Percent_Difference': values.get('percent_difference', 0)
                        }
                        
                        # Add statistical significance if available
                        if 'statistical_tests' in analysis and metric in analysis['statistical_tests']:
                            row['P_Value'] = analysis['statistical_tests'][metric].get('p_value', 1.0)
                            row['Significant'] = analysis['statistical_tests'][metric].get('significant', False)
                        
                        # Add correlation if available
                        if 'correlation_with_performance' in analysis and metric in analysis['correlation_with_performance']:
                            row['Correlation'] = analysis['correlation_with_performance'][metric]
                        
                        metrics_data.append(row)
                    
                    metrics_df = pd.DataFrame(metrics_data)
                    metrics_df.to_excel(writer, sheet_name='Metrics_Comparison', index=False)
                
                # 5. Allocation Formula Sheet
                if 'allocation_formula' in analysis:
                    formula = analysis['allocation_formula']
                    
                    formula_data = [
                        ['Description', formula.get('description', '')],
                        ['Scoring Function', formula.get('scoring_function', '')],
                        ['', ''],
                        ['Metric', 'Weight']
                    ]
                    
                    for metric, weight in formula.get('weights', {}).items():
                        formula_data.append([metric, weight])
                    
                    formula_df = pd.DataFrame(formula_data)
                    formula_df.to_excel(writer, sheet_name='Allocation_Formula', index=False, header=False)
                
                # 6. Hourly Patterns Sheet
                if 'hourly_patterns' in analysis and analysis['hourly_patterns']:
                    patterns = analysis['hourly_patterns']
                    
                    hourly_data = [
                        ['Metric', 'Value'],
                        ['Total Tickers with Hourly Data', patterns.get('total_analyzed', 0)],
                        ['Successful Tickers Count', patterns.get('successful_count', 0)],
                        ['Success Rate (%)', f"{patterns.get('success_rate', 0):.1f}"],
                        ['', ''],
                        ['Average Best Exit Hour (Successful)', f"{patterns.get('avg_best_exit_hour_success', 0):.1f}" if patterns.get('avg_best_exit_hour_success') else 'N/A'],
                        ['Most Common Exit Hour', patterns.get('most_common_exit_hour', 'N/A')],
                        ['', ''],
                        ['Intraday Metrics (Success vs Fail)', '']
                    ]
                    
                    # Add intraday metric comparisons
                    for metric in ['max_intraday_profit_pct', 'max_intraday_drawdown_pct', 'hours_to_peak', 'day1_return_pct']:
                        success_key = f'{metric}_success_avg'
                        fail_key = f'{metric}_fail_avg'
                        p_value_key = f'{metric}_p_value'
                        
                        if success_key in patterns and fail_key in patterns:
                            success_val = patterns[success_key]
                            fail_val = patterns[fail_key]
                            p_value = patterns.get(p_value_key, 1.0)
                            significant = '*' if p_value < 0.05 else ''
                            
                            hourly_data.append([
                                f"{metric.replace('_', ' ').title()}",
                                f"Success: {success_val:.2f}, Fail: {fail_val:.2f} {significant}"
                            ])
                    
                    # Add theory analysis results
                    if 'sma20_theory' in patterns or 'h2_theory' in patterns:
                        hourly_data.append(['', ''])
                        hourly_data.append(['SMA20 and H2 Theory Analysis', ''])
                        
                        if 'sma20_theory' in patterns:
                            sma20 = patterns['sma20_theory']
                            hourly_data.append(['Success Avg Above SMA20 (%)', f"{sma20.get('success_avg_above_sma20', 0):.1f}"])
                            hourly_data.append(['Fail Avg Above SMA20 (%)', f"{sma20.get('fail_avg_above_sma20', 0):.1f}"])
                            hourly_data.append(['Success Always Above SMA20', f"{sma20.get('success_always_above_sma20', 0)} ({sma20.get('success_always_above_sma20_pct', 0):.1f}%)"])
                            hourly_data.append(['SMA20 Pattern Significant', 'Yes' if sma20.get('significant', False) else 'No'])
                        
                        if 'h2_theory' in patterns:
                            hourly_data.append(['', ''])
                            h2 = patterns['h2_theory']
                            hourly_data.append(['Success Avg H2 Breakouts (%)', f"{h2.get('success_avg_h2_breakouts', 0):.1f}"])
                            hourly_data.append(['Fail Avg H2 Breakouts (%)', f"{h2.get('fail_avg_h2_breakouts', 0):.1f}"])
                            hourly_data.append(['Success Avg Consecutive H2', f"{h2.get('success_avg_consecutive_h2', 0):.1f}"])
                            hourly_data.append(['Fail Avg Consecutive H2', f"{h2.get('fail_avg_consecutive_h2', 0):.1f}"])
                            hourly_data.append(['H2 Pattern Significant', 'Yes' if h2.get('significant', False) else 'No'])
                        
                        if 'combined_theory' in patterns:
                            hourly_data.append(['', ''])
                            combined = patterns['combined_theory']
                            hourly_data.append(['Combined Theory Validation', combined.get('theory_validity', 'Unknown')])
                            hourly_data.append(['Strong Pattern Tickers', combined.get('strong_pattern_count', 0)])
                            hourly_data.append(['Strong Pattern Success Rate (%)', f"{combined.get('strong_pattern_success_rate', 0):.1f}"])
                    
                    hourly_df = pd.DataFrame(hourly_data)
                    hourly_df.to_excel(writer, sheet_name='Hourly_Patterns', index=False, header=False)
                
                # 7. Recommendations Sheet
                recommendations = self.generate_recommendations(analysis)
                rec_df = pd.DataFrame(recommendations, columns=['Recommendation'])
                rec_df.to_excel(writer, sheet_name='Recommendations', index=False)
            
            logger.info(f"Exported analysis to Excel: {excel_file}")
            return excel_file
            
        except Exception as e:
            logger.error(f"Error exporting Excel report: {e}")
            return ""
    
    def create_visualizations(self, all_results: List[Dict], top_performers: List[Dict], 
                            bottom_performers: List[Dict], analysis: Dict) -> List[str]:
        """Create visualization charts for analysis"""
        try:
            chart_files = []
            
            # Set style
            plt.style.use('seaborn-v0_8')
            
            # 1. Comparison of Key Metrics between Top and Bottom Performers
            if 'key_metrics' in analysis:
                # Get metrics with significant differences
                significant_metrics = [m for m in analysis.get('differentiating_factors', [])]
                
                if significant_metrics:
                    # Use up to 6 most significant metrics
                    metrics_to_plot = significant_metrics[:min(6, len(significant_metrics))]
                    
                    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
                    fig.suptitle('Comparison of Key Metrics: Top vs Bottom Performers', fontsize=16, fontweight='bold')
                    
                    axes = axes.flatten()
                    
                    for i, factor in enumerate(metrics_to_plot):
                        if i < len(axes):
                            metric = factor['metric']
                            
                            # Extract data
                            top_values = [t.get(metric, np.nan) for t in top_performers if metric in t]
                            bottom_values = [b.get(metric, np.nan) for b in bottom_performers if metric in b]
                            
                            # Filter out NaN values
                            top_values = [v for v in top_values if not np.isnan(v)]
                            bottom_values = [v for v in bottom_values if not np.isnan(v)]
                            
                            if top_values and bottom_values:
                                # Plot boxplot
                                boxplot_data = [top_values, bottom_values]
                                axes[i].boxplot(boxplot_data, labels=['Top', 'Bottom'])
                                
                                # Add jittered points
                                for j, data in enumerate([top_values, bottom_values]):
                                    x = np.random.normal(j+1, 0.04, size=len(data))
                                    axes[i].scatter(x, data, alpha=0.3, color='green' if j == 0 else 'red')
                                
                                # Format plot
                                axes[i].set_title(f"{metric}")
                                axes[i].grid(True, alpha=0.3)
                                
                                # Add p-value if available
                                if 'p_value' in factor:
                                    p_value = factor['p_value']
                                    significance = '***' if p_value < 0.001 else '**' if p_value < 0.01 else '*' if p_value < 0.05 else 'ns'
                                    axes[i].set_xlabel(f"p-value: {p_value:.4f} {significance}")
                    
                    # Hide any unused axes
                    for i in range(len(metrics_to_plot), len(axes)):
                        axes[i].set_visible(False)
                    
                    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
                    chart_file = os.path.join(self.results_dir, f"top_performer_metrics_comparison_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                    plt.savefig(chart_file, dpi=300, bbox_inches='tight')
                    plt.close()
                    chart_files.append(chart_file)
            
            # 2. Correlation Matrix of Metrics with Performance
            if 'correlation_with_performance' in analysis:
                correlations = analysis['correlation_with_performance']
                
                if correlations:
                    # Sort by absolute correlation value
                    sorted_corr = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
                    
                    # Take top 10 correlations
                    top_corr = sorted_corr[:min(10, len(sorted_corr))]
                    
                    metrics = [c[0] for c in top_corr]
                    corr_values = [c[1] for c in top_corr]
                    
                    fig, ax = plt.subplots(figsize=(10, 8))
                    
                    # Create horizontal bar chart
                    colors = ['green' if c >= 0 else 'red' for c in corr_values]
                    y_pos = np.arange(len(metrics))
                    
                    ax.barh(y_pos, corr_values, color=colors)
                    ax.set_yticks(y_pos)
                    ax.set_yticklabels(metrics)
                    ax.invert_yaxis()  # Labels read top-to-bottom
                    ax.set_xlabel('Correlation with Performance')
                    ax.set_title('Metrics Most Correlated with Performance', fontsize=14, fontweight='bold')
                    
                    # Add a vertical line at x=0
                    ax.axvline(x=0, color='black', linestyle='-', alpha=0.3)
                    
                    # Add correlation values as text
                    for i, v in enumerate(corr_values):
                        ax.text(v + (0.02 if v >= 0 else -0.08), i, f"{v:.2f}", 
                               va='center', color='black', fontweight='bold')
                    
                    plt.tight_layout()
                    chart_file = os.path.join(self.results_dir, f"performance_correlation_chart_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                    plt.savefig(chart_file, dpi=300, bbox_inches='tight')
                    plt.close()
                    chart_files.append(chart_file)
            
            # 3. PnL Distribution: Top vs Bottom
            if top_performers and bottom_performers:
                fig, ax = plt.subplots(figsize=(12, 6))
                
                top_pnl = [t.get('pnl_percent', 0) for t in top_performers if 'pnl_percent' in t]
                bottom_pnl = [b.get('pnl_percent', 0) for b in bottom_performers if 'pnl_percent' in b]
                
                ax.hist([top_pnl, bottom_pnl], bins=15, label=['Top Performers', 'Bottom Performers'],
                       color=['green', 'red'], alpha=0.6)
                
                ax.set_xlabel('Percent PnL (%)')
                ax.set_ylabel('Frequency')
                ax.set_title('PnL Distribution: Top vs Bottom Performers', fontsize=14, fontweight='bold')
                ax.legend()
                ax.grid(True, alpha=0.3)
                
                plt.tight_layout()
                chart_file = os.path.join(self.results_dir, f"pnl_distribution_chart_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                plt.savefig(chart_file, dpi=300, bbox_inches='tight')
                plt.close()
                chart_files.append(chart_file)
            
            # 4. Hourly Performance Analysis Chart
            hourly_results = [r for r in all_results if r.get('hourly_data_available', False)]
            if hourly_results:
                fig, axes = plt.subplots(2, 2, figsize=(15, 10))
                fig.suptitle('Hourly Performance Analysis', fontsize=16, fontweight='bold')
                
                # 4.1 Best Exit Hour Distribution
                exit_hours = [r['best_exit_hour'] for r in hourly_results if 'best_exit_hour' in r and r['best_exit_hour'] is not None]
                if exit_hours:
                    axes[0, 0].hist(exit_hours, bins=range(1, 25), alpha=0.7, color='blue', edgecolor='black')
                    axes[0, 0].set_xlabel('Hours After Signal')
                    axes[0, 0].set_ylabel('Frequency')
                    axes[0, 0].set_title('Distribution of Best Exit Hours')
                    axes[0, 0].grid(True, alpha=0.3)
                
                # 4.2 Intraday Profit vs Final Return
                intraday_profits = [r['max_intraday_profit_pct'] for r in hourly_results if 'max_intraday_profit_pct' in r and r['max_intraday_profit_pct'] is not None]
                final_returns = [r['pnl_percent'] for r in hourly_results if 'max_intraday_profit_pct' in r and r['max_intraday_profit_pct'] is not None]
                
                if intraday_profits and final_returns:
                    axes[0, 1].scatter(intraday_profits, final_returns, alpha=0.5)
                    axes[0, 1].set_xlabel('Max Intraday Profit (%)')
                    axes[0, 1].set_ylabel('Final Return (%)')
                    axes[0, 1].set_title('Intraday Profit vs Final Return')
                    axes[0, 1].grid(True, alpha=0.3)
                    
                    # Add diagonal line
                    max_val = max(max(intraday_profits), max(final_returns))
                    min_val = min(min(intraday_profits), min(final_returns))
                    axes[0, 1].plot([min_val, max_val], [min_val, max_val], 'r--', alpha=0.5)
                
                # 4.3 Hours to Peak vs Performance
                hours_to_peak = [(r['hours_to_peak'], r['pnl_percent']) for r in hourly_results 
                               if 'hours_to_peak' in r and r['hours_to_peak'] is not None]
                
                if hours_to_peak:
                    hours, returns = zip(*hours_to_peak)
                    axes[1, 0].scatter(hours, returns, alpha=0.5)
                    axes[1, 0].set_xlabel('Hours to Peak Price')
                    axes[1, 0].set_ylabel('Final Return (%)')
                    axes[1, 0].set_title('Time to Peak vs Performance')
                    axes[1, 0].grid(True, alpha=0.3)
                
                # 4.4 Day 1 Return Distribution: Winners vs Losers
                winners_day1 = [r['day1_return_pct'] for r in hourly_results 
                              if 'day1_return_pct' in r and r['day1_return_pct'] is not None and r['pnl_percent'] > 0]
                losers_day1 = [r['day1_return_pct'] for r in hourly_results 
                             if 'day1_return_pct' in r and r['day1_return_pct'] is not None and r['pnl_percent'] <= 0]
                
                if winners_day1 or losers_day1:
                    axes[1, 1].hist([winners_day1, losers_day1], bins=20, label=['Winners', 'Losers'],
                                   color=['green', 'red'], alpha=0.6)
                    axes[1, 1].set_xlabel('Day 1 Return (%)')
                    axes[1, 1].set_ylabel('Frequency')
                    axes[1, 1].set_title('Day 1 Returns: Winners vs Losers')
                    axes[1, 1].legend()
                    axes[1, 1].grid(True, alpha=0.3)
                
                plt.tight_layout(rect=[0, 0.03, 1, 0.95])
                chart_file = os.path.join(self.results_dir, f"hourly_performance_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                plt.savefig(chart_file, dpi=300, bbox_inches='tight')
                plt.close()
                chart_files.append(chart_file)
            
            # 5. SMA20 and H2 Theory Analysis Chart
            if 'hourly_patterns' in analysis and 'sma20_theory' in analysis['hourly_patterns']:
                fig, axes = plt.subplots(2, 2, figsize=(15, 10))
                fig.suptitle('SMA20 and H2 Pattern Analysis', fontsize=16, fontweight='bold')
                
                patterns = analysis['hourly_patterns']
                
                # 5.1 SMA20 Above Ratio Comparison
                if 'sma20_theory' in patterns:
                    sma20_data = patterns['sma20_theory']
                    categories = ['Successful', 'Unsuccessful']
                    sma20_values = [sma20_data.get('success_avg_above_sma20', 0), 
                                   sma20_data.get('fail_avg_above_sma20', 0)]
                    
                    axes[0, 0].bar(categories, sma20_values, color=['green', 'red'], alpha=0.7)
                    axes[0, 0].set_ylabel('% Time Above SMA20')
                    axes[0, 0].set_title('Average Time Above SMA20')
                    axes[0, 0].set_ylim(0, 100)
                    
                    # Add significance marker
                    if sma20_data.get('significant', False):
                        axes[0, 0].text(0.5, max(sma20_values) + 5, '***', ha='center', fontsize=12)
                
                # 5.2 H2 Breakout Ratio Comparison
                if 'h2_theory' in patterns:
                    h2_data = patterns['h2_theory']
                    h2_values = [h2_data.get('success_avg_h2_breakouts', 0), 
                                h2_data.get('fail_avg_h2_breakouts', 0)]
                    
                    axes[0, 1].bar(categories, h2_values, color=['green', 'red'], alpha=0.7)
                    axes[0, 1].set_ylabel('% Hours with H2 Breakout')
                    axes[0, 1].set_title('H2 Breakout Frequency')
                    axes[0, 1].set_ylim(0, 100)
                    
                    # Add significance marker
                    if h2_data.get('significant', False):
                        axes[0, 1].text(0.5, max(h2_values) + 5, '***', ha='center', fontsize=12)
                
                # 5.3 Consecutive H2 Breaks
                if 'h2_theory' in patterns:
                    consecutive_values = [h2_data.get('success_avg_consecutive_h2', 0), 
                                        h2_data.get('fail_avg_consecutive_h2', 0)]
                    
                    axes[1, 0].bar(categories, consecutive_values, color=['green', 'red'], alpha=0.7)
                    axes[1, 0].set_ylabel('Average Consecutive H2 Breaks')
                    axes[1, 0].set_title('Consecutive H2 Breakouts')
                
                # 5.4 Theory Validation Summary
                if 'combined_theory' in patterns:
                    combined = patterns['combined_theory']
                    
                    # Create text summary
                    summary_text = f"Theory Validation: {combined.get('theory_validity', 'Unknown')}\n\n"
                    summary_text += f"Strong Pattern Tickers: {combined.get('strong_pattern_count', 0)}\n"
                    summary_text += f"Strong Pattern Success Rate: {combined.get('strong_pattern_success_rate', 0):.1f}%\n"
                    summary_text += f"Overall Success Rate: {combined.get('overall_success_rate', 0):.1f}%\n\n"
                    summary_text += "Strong Pattern = >80% above SMA20 & >50% H2 breaks"
                    
                    axes[1, 1].text(0.1, 0.5, summary_text, transform=axes[1, 1].transAxes,
                                   fontsize=12, verticalalignment='center',
                                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
                    axes[1, 1].axis('off')
                
                plt.tight_layout(rect=[0, 0.03, 1, 0.95])
                chart_file = os.path.join(self.results_dir, f"sma20_h2_theory_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                plt.savefig(chart_file, dpi=300, bbox_inches='tight')
                plt.close()
                chart_files.append(chart_file)
            
            logger.info(f"Created {len(chart_files)} visualization charts")
            return chart_files
            
        except Exception as e:
            logger.error(f"Error creating visualizations: {e}")
            return []
    
    def generate_recommendations(self, analysis: Dict) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        try:
            recommendations = []
            
            # Add basic header
            recommendations.append(f"PORTFOLIO ALLOCATION RECOMMENDATIONS FOR BROOKS STRATEGY")
            recommendations.append(f"Based on analysis of top {self.top_n} performers vs bottom {self.top_n} performers")
            recommendations.append("")
            
            # Add key differentiating factors
            if 'differentiating_factors' in analysis and analysis['differentiating_factors']:
                recommendations.append("KEY CHARACTERISTICS OF TOP PERFORMERS:")
                
                for i, factor in enumerate(analysis['differentiating_factors'][:5], 1):
                    metric = factor['metric']
                    direction = factor['difference_direction']
                    diff_percent = factor.get('percent_difference', 0)
                    corr = factor.get('correlation_with_performance', 0)
                    
                    if direction == "higher":
                        recommendations.append(f"{i}. {metric.replace('_', ' ').title()} was {abs(diff_percent):.1f}% higher in top performers (correlation: {corr:.2f})")
                    else:
                        recommendations.append(f"{i}. {metric.replace('_', ' ').title()} was {abs(diff_percent):.1f}% lower in top performers (correlation: {corr:.2f})")
                
                recommendations.append("")
            
            # Add allocation formula
            if 'allocation_formula' in analysis:
                formula = analysis['allocation_formula']
                recommendations.append("RECOMMENDED PORTFOLIO ALLOCATION APPROACH:")
                recommendations.append(formula.get('description', 'Equal allocation across selected tickers'))
                
                if 'weights' in formula and formula['weights']:
                    recommendations.append("")
                    recommendations.append("Allocation Factor Weights:")
                    for metric, weight in formula['weights'].items():
                        recommendations.append(f"• {metric.replace('_', ' ').title()}: {weight:.2f}")
                
                recommendations.append("")
            
            # Add specific selection criteria
            recommendations.append("STOCK SELECTION CRITERIA:")
            
            if 'differentiating_factors' in analysis:
                factors = analysis['differentiating_factors']
                
                for factor in factors[:3]:  # Use top 3 factors
                    metric = factor['metric']
                    direction = factor['difference_direction']
                    
                    if metric == 'risk_reward_ratio' and direction == 'higher':
                        recommendations.append(f"• Prioritize tickers with risk-reward ratio > {factor['top_mean']:.2f}")
                    
                    elif metric == 'volume_ratio' and direction == 'higher':
                        recommendations.append(f"• Look for above-average volume (> {factor['top_mean']:.1f}x 20-day average)")
                    
                    elif metric == 'price_to_sma20_percent':
                        if direction == 'higher':
                            recommendations.append(f"• Select tickers trading more than {factor['top_mean']:.1f}% above their 20-day SMA")
                        else:
                            recommendations.append(f"• Avoid tickers trading too far above their 20-day SMA (< {factor['top_mean']:.1f}%)")
                    
                    elif metric == 'atr_percent':
                        if direction == 'higher':
                            recommendations.append(f"• Choose tickers with higher volatility (ATR > {factor['top_mean']:.1f}% of price)")
                        else:
                            recommendations.append(f"• Prefer lower volatility tickers (ATR < {factor['top_mean']:.1f}% of price)")
                    
                    elif metric == 'body_ratio' and direction == 'higher':
                        recommendations.append(f"• Select tickers with strong conviction candles (body > {factor['top_mean']:.1f}x average)")
            
            # Add hourly pattern insights
            if 'hourly_patterns' in analysis and analysis['hourly_patterns']:
                patterns = analysis['hourly_patterns']
                recommendations.append("")
                recommendations.append("HOURLY TRADING INSIGHTS:")
                
                if 'avg_best_exit_hour_success' in patterns:
                    recommendations.append(f"• Successful trades typically peak around hour {patterns['avg_best_exit_hour_success']:.0f} after signal")
                
                if 'max_intraday_profit_pct_success_avg' in patterns:
                    recommendations.append(f"• Winners show average intraday profit of {patterns['max_intraday_profit_pct_success_avg']:.1f}%")
                
                if 'day1_return_pct_success_avg' in patterns and 'day1_return_pct_fail_avg' in patterns:
                    success_day1 = patterns['day1_return_pct_success_avg']
                    fail_day1 = patterns['day1_return_pct_fail_avg']
                    recommendations.append(f"• Day 1 returns: Winners avg {success_day1:.1f}% vs Losers avg {fail_day1:.1f}%")
                
                if patterns.get('early_winner_count', 0) > 0:
                    recommendations.append(f"• {patterns['early_winner_count']} tickers showed >2% gain on Day 1 and >5% final return")
            
            # Add general recommendations
            recommendations.append("")
            recommendations.append("GENERAL RECOMMENDATIONS:")
            recommendations.append("• Re-analyze this data monthly to refine allocation strategy")
            recommendations.append("• Consider increasing position size for tickers with multiple positive factors")
            recommendations.append("• Monitor key metrics in real-time and adjust positions accordingly")
            recommendations.append("• Use stop-loss levels based on actual volatility (ATR-based stops)")
            recommendations.append("• Consider intraday exit strategies based on hourly performance patterns")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return ["Error generating recommendations"]
    
    def print_summary(self, top_performers: List[Dict], bottom_performers: List[Dict], analysis: Dict):
        """Print summary of top performer analysis to console"""
        print("\n" + "="*80)
        print(f"BROOKS HIGHER PROBABILITY LONG REVERSAL STRATEGY - TOP PERFORMER ANALYSIS")
        print(f"User: {self.user_name} | Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # Top performers summary
        print(f"TOP {len(top_performers)} PERFORMERS:")
        for i, ticker in enumerate(top_performers[:5], 1):
            print(f"{i}. {ticker['ticker']}: {ticker.get('pnl_percent', 0):.2f}% (₹{ticker.get('entry_price', 0):.2f} → ₹{ticker.get('current_price', 0):.2f})")
        
        print("\nBOTTOM PERFORMERS:")
        for i, ticker in enumerate(bottom_performers[:5], 1):
            print(f"{i}. {ticker['ticker']}: {ticker.get('pnl_percent', 0):.2f}% (₹{ticker.get('entry_price', 0):.2f} → ₹{ticker.get('current_price', 0):.2f})")
        
        print("-"*80)
        
        # Key differentiating factors
        if 'differentiating_factors' in analysis and analysis['differentiating_factors']:
            print("KEY DIFFERENTIATING FACTORS:")
            
            for i, factor in enumerate(analysis['differentiating_factors'][:5], 1):
                metric = factor['metric']
                direction = factor['difference_direction']
                diff_percent = factor.get('percent_difference', 0)
                
                if direction == "higher":
                    print(f"{i}. {metric.replace('_', ' ').title()} is {abs(diff_percent):.1f}% higher in top performers")
                else:
                    print(f"{i}. {metric.replace('_', ' ').title()} is {abs(diff_percent):.1f}% lower in top performers")
        
        print("-"*80)
        
        # Allocation recommendation
        if 'allocation_formula' in analysis:
            formula = analysis['allocation_formula']
            print("PORTFOLIO ALLOCATION RECOMMENDATION:")
            print(formula.get('description', 'Equal allocation across selected tickers'))
        
        print("-"*80)
        print(f"Detailed analysis saved to results directory: {self.results_dir}")
        print("="*80)


def main():
    """Main function"""
    try:
        # Create logs directory
        os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs'), exist_ok=True)
        
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Brooks Strategy Top Performer Analysis")
        parser.add_argument("--user", "-u", type=str, default="Sai", help="User whose API credentials to use (default: Sai)")
        parser.add_argument("--top-n", "-n", type=int, default=10, help="Number of top performers to analyze (default: 10)")
        parser.add_argument("--results-dir", "-d", type=str, help="Custom directory to save results")
        args = parser.parse_args()
        
        # Initialize analyzer with user credentials
        analyzer = BrooksTopPerformerAnalyzer(user_name=args.user, top_n=args.top_n)
        
        # Set custom results directory if provided
        if args.results_dir:
            analyzer.results_dir = os.path.abspath(args.results_dir)
            os.makedirs(analyzer.results_dir, exist_ok=True)
            logger.info(f"Custom results directory set: {analyzer.results_dir}")
        
        # Run analysis
        results = analyzer.analyze_top_performers()
        
        if results:
            print(f"\nBrooks strategy top performer analysis completed successfully!")
            print(f"Results saved to: {analyzer.results_dir}")
        else:
            print("Brooks strategy top performer analysis failed. Check logs for details.")
            
        return 0
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())