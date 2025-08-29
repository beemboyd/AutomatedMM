#!/usr/bin/env python3
"""
SMA Breadth Hourly Data Collector
Collects hourly SMA breadth data for intraday analysis
Stores data in structured format for dashboard display
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from pathlib import Path
import configparser
import time
from kiteconnect import KiteConnect
import yfinance as yf

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SMABreadthHourlyCollector:
    """Collects hourly SMA breadth data for dashboard display"""
    
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.daily_dir = os.path.dirname(self.script_dir)  # Daily folder
        self.data_dir = os.path.join(self.script_dir, 'hourly_breadth_data')
        self.ticker_file = os.path.join(self.daily_dir, 'data', 'Ticker.xlsx')
        
        # Create data directory
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        
        # Load user context for API access
        self._setup_user_context()
        
    def _setup_user_context(self):
        """Setup user context for API access using config.ini"""
        try:
            # Load config file
            config = configparser.ConfigParser()
            config_path = os.path.join(self.daily_dir, 'config.ini')
            
            if not os.path.exists(config_path):
                logger.warning(f"Config file not found: {config_path}")
                self.use_zerodha = False
                return
            
            config.read(config_path)
            
            # Use Sai's credentials (first user with access token)
            user_section = 'API_CREDENTIALS_Sai'
            if user_section not in config:
                logger.warning(f"User section {user_section} not found in config")
                self.use_zerodha = False
                return
            
            api_key = config[user_section].get('api_key')
            api_secret = config[user_section].get('api_secret')
            access_token = config[user_section].get('access_token')
            
            if not all([api_key, api_secret, access_token]):
                logger.warning(f"Incomplete credentials for {user_section}")
                self.use_zerodha = False
                return
            
            # Setup direct KiteConnect instance
            self.kite = KiteConnect(api_key=api_key)
            self.kite.set_access_token(access_token)
            
            # Test connection
            try:
                profile = self.kite.profile()
                logger.info(f"Connected to Zerodha API for user: {profile.get('user_name', 'Unknown')}")
                self.use_zerodha = True
            except Exception as e:
                logger.warning(f"Failed to connect to Zerodha API: {e}")
                self.use_zerodha = False
            
        except Exception as e:
            logger.warning(f"Failed to setup Zerodha context: {e}")
            self.use_zerodha = False
    
    def load_ticker_list(self):
        """Load ticker list from Excel file"""
        try:
            # First try to load FNO stocks for better market representation
            fno_file = os.path.join(self.daily_dir, 'data', 'Ticker.xlsx')
            if os.path.exists(fno_file):
                df = pd.read_excel(fno_file)
                # For hourly data, limit to top 100 most liquid stocks
                tickers = df['Ticker'].dropna().unique().tolist()[:100]
                logger.info(f"Loaded {len(tickers)} FNO tickers for hourly breadth analysis")
                return tickers
            
            # Fallback to regular ticker file
            if os.path.exists(self.ticker_file):
                df = pd.read_excel(self.ticker_file)
                # Limit to first 100 most liquid stocks for hourly data
                tickers = df['Ticker'].dropna().unique().tolist()[:100]
                logger.info(f"Loaded {len(tickers)} tickers from {self.ticker_file}")
                return tickers
            else:
                # Fallback to test tickers
                logger.warning(f"Ticker files not found")
                return self._get_fallback_tickers()
                
        except Exception as e:
            logger.error(f"Error loading ticker list: {e}")
            return self._get_fallback_tickers()
    
    def _get_fallback_tickers(self):
        """Fallback ticker list for testing - NIFTY 50 stocks"""
        return [
            'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR', 
            'ICICIBANK', 'KOTAKBANK', 'SBIN', 'BHARTIARTL', 'ITC',
            'HDFC', 'BAJFINANCE', 'LT', 'WIPRO', 'ASIANPAINT',
            'AXISBANK', 'MARUTI', 'ULTRACEMCO', 'SUNPHARMA', 'TITAN',
            'NESTLEIND', 'NTPC', 'POWERGRID', 'TECHM', 'TATAMOTORS',
            'HCLTECH', 'BAJAJ-AUTO', 'ONGC', 'ADANIPORTS', 'M&M',
            'TATASTEEL', 'JSWSTEEL', 'COALINDIA', 'GRASIM', 'INDUSINDBK',
            'DRREDDY', 'BRITANNIA', 'EICHERMOT', 'UPL', 'BAJAJFINSV',
            'DIVISLAB', 'SHREECEM', 'SBILIFE', 'CIPLA', 'BPCL',
            'TATACONSUM', 'APOLLOHOSP', 'ADANIENT', 'HEROMOTOCO', 'HINDALCO'
        ]
    
    def fetch_hourly_data_yfinance(self, ticker, days=30):
        """Fetch hourly data using yfinance"""
        try:
            # Convert NSE ticker to Yahoo format
            yahoo_ticker = f"{ticker}.NS"
            
            stock = yf.Ticker(yahoo_ticker)
            # Fetch hourly data for the past month
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            data = stock.history(start=start_date, end=end_date, interval='1h')
            
            if data.empty:
                return None
                
            # Convert to required format
            data = data.reset_index()
            data['DateTime'] = data['Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            return {
                'ticker': ticker,
                'data': data[['DateTime', 'Open', 'High', 'Low', 'Close', 'Volume']].to_dict('records')
            }
            
        except Exception as e:
            logger.error(f"Error fetching hourly data for {ticker}: {e}")
            return None
    
    def fetch_hourly_data_zerodha(self, ticker, days=30):
        """Fetch hourly data using Zerodha API"""
        try:
            if not self.use_zerodha:
                return self.fetch_hourly_data_yfinance(ticker, days)
                
            # Get instrument token for ticker
            instruments = self.kite.instruments("NSE")
            instrument = next((inst for inst in instruments if inst['tradingsymbol'] == ticker), None)
            
            if not instrument:
                logger.warning(f"Instrument not found for {ticker}, trying yfinance")
                return self.fetch_hourly_data_yfinance(ticker, days)
                
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Fetch hourly historical data
            data = self.kite.historical_data(
                instrument_token=instrument['instrument_token'],
                from_date=start_date,
                to_date=end_date,
                interval='60minute'  # Hourly interval
            )
            
            if not data:
                return None
                
            # Convert to required format
            formatted_data = []
            for candle in data:
                formatted_data.append({
                    'DateTime': candle['date'].strftime('%Y-%m-%d %H:%M:%S'),
                    'Open': candle['open'],
                    'High': candle['high'],
                    'Low': candle['low'],
                    'Close': candle['close'],
                    'Volume': candle['volume']
                })
            
            return {
                'ticker': ticker,
                'data': formatted_data
            }
            
        except Exception as e:
            logger.error(f"Error fetching Zerodha hourly data for {ticker}: {e}")
            # Fallback to yfinance
            return self.fetch_hourly_data_yfinance(ticker, days)
    
    def calculate_hourly_sma_metrics(self, ticker_data):
        """Calculate SMA metrics and volume analysis for hourly data"""
        try:
            df = pd.DataFrame(ticker_data['data'])
            df['DateTime'] = pd.to_datetime(df['DateTime'])
            df = df.sort_values('DateTime')
            
            # Filter for market hours only (9:15 AM to 3:30 PM)
            df['Hour'] = df['DateTime'].dt.hour
            df['Minute'] = df['DateTime'].dt.minute
            df = df[
                ((df['Hour'] == 9) & (df['Minute'] >= 15)) |
                ((df['Hour'] > 9) & (df['Hour'] < 15)) |
                ((df['Hour'] == 15) & (df['Minute'] <= 30))
            ]
            
            # Skip weekends
            df = df[df['DateTime'].dt.dayofweek < 5]
            
            # Calculate SMAs (using shorter periods for hourly data)
            df['SMA20'] = df['Close'].rolling(window=20, min_periods=1).mean()
            df['SMA50'] = df['Close'].rolling(window=50, min_periods=1).mean()
            
            # Calculate Volume metrics
            df['Volume_SMA20'] = df['Volume'].rolling(window=20, min_periods=1).mean()
            df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA20']
            
            # Calculate hourly metrics
            results = []
            for _, row in df.iterrows():
                above_sma20 = 1 if row['Close'] > row['SMA20'] else 0
                above_sma50 = 1 if row['Close'] > row['SMA50'] else 0
                above_avg_volume = 1 if row['Volume'] > row['Volume_SMA20'] else 0
                
                results.append({
                    'datetime': row['DateTime'].strftime('%Y-%m-%d %H:%M:%S'),
                    'ticker': ticker_data['ticker'],
                    'close': row['Close'],
                    'volume': row['Volume'],
                    'sma20': row['SMA20'],
                    'sma50': row['SMA50'],
                    'volume_sma20': row['Volume_SMA20'],
                    'volume_ratio': row['Volume_Ratio'],
                    'above_sma20': above_sma20,
                    'above_sma50': above_sma50,
                    'above_avg_volume': above_avg_volume
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error calculating hourly SMA metrics for {ticker_data['ticker']}: {e}")
            return []
    
    def aggregate_hourly_breadth(self, all_metrics):
        """Aggregate individual ticker metrics into hourly breadth data"""
        try:
            # Convert to DataFrame for easier aggregation
            df = pd.DataFrame(all_metrics)
            df['datetime'] = pd.to_datetime(df['datetime'])
            
            # Group by hour and calculate breadth metrics
            hourly_breadth = []
            
            for datetime_val, group in df.groupby('datetime'):
                total_stocks = len(group)
                above_sma20 = group['above_sma20'].sum()
                above_sma50 = group['above_sma50'].sum()
                above_avg_volume = group['above_avg_volume'].sum()
                
                sma20_percent = (above_sma20 / total_stocks) * 100
                sma50_percent = (above_sma50 / total_stocks) * 100
                volume_breadth_percent = (above_avg_volume / total_stocks) * 100
                
                # Calculate average volume ratio
                avg_volume_ratio = group['volume_ratio'].mean()
                
                # Volume participation score
                volume_participation = volume_breadth_percent * avg_volume_ratio / 100
                
                # Calculate market regime based on breadth
                if sma20_percent >= 70 and volume_participation > 1.0:
                    regime = "Strong Bullish"
                elif sma20_percent >= 60:
                    regime = "Bullish"
                elif sma20_percent <= 30:
                    regime = "Bearish"
                elif sma20_percent <= 40:
                    regime = "Weak"
                else:
                    regime = "Neutral"
                
                hourly_breadth.append({
                    'datetime': datetime_val.strftime('%Y-%m-%d %H:%M:%S'),
                    'date': datetime_val.strftime('%Y-%m-%d'),
                    'hour': datetime_val.hour,
                    'timestamp': datetime_val.isoformat(),
                    'total_stocks': int(total_stocks),
                    'sma20_breadth': round(float(sma20_percent), 2),
                    'sma50_breadth': round(float(sma50_percent), 2),
                    'volume_breadth': round(float(volume_breadth_percent), 2),
                    'volume_participation': round(float(volume_participation), 2),
                    'market_regime': regime
                })
            
            return sorted(hourly_breadth, key=lambda x: x['datetime'])
            
        except Exception as e:
            logger.error(f"Error aggregating hourly breadth: {e}")
            return []
    
    def collect_hourly_data(self, days=30):
        """Main method to collect hourly SMA breadth data"""
        try:
            logger.info(f"Collecting hourly data for the past {days} days")
            
            # Load tickers
            tickers = self.load_ticker_list()
            logger.info(f"Processing {len(tickers)} tickers")
            
            # Collect data for all tickers
            all_ticker_data = []
            successful = 0
            failed = 0
            
            for i, ticker in enumerate(tickers):
                try:
                    logger.info(f"Processing {ticker} ({i+1}/{len(tickers)})")
                    
                    # Fetch hourly data
                    ticker_data = self.fetch_hourly_data_zerodha(ticker, days)
                    
                    if ticker_data and ticker_data['data']:
                        all_ticker_data.append(ticker_data)
                        successful += 1
                        logger.info(f"✓ Collected hourly data for {ticker}")
                    else:
                        failed += 1
                        logger.warning(f"✗ No data for {ticker}")
                        
                    # Rate limiting - 0.5 second between requests
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"✗ Error collecting {ticker}: {e}")
                    failed += 1
                    time.sleep(1.0)
            
            logger.info(f"\nCollection Summary:")
            logger.info(f"  Successful: {successful}")
            logger.info(f"  Failed: {failed}")
            logger.info(f"  Success rate: {(successful/len(tickers)*100):.1f}%")
            
            # Calculate SMA metrics for all tickers
            all_metrics = []
            for ticker_data in all_ticker_data:
                metrics = self.calculate_hourly_sma_metrics(ticker_data)
                all_metrics.extend(metrics)
            
            logger.info(f"Calculated SMA metrics for {len(all_metrics)} hourly data points")
            
            # Aggregate into hourly breadth data
            hourly_breadth = self.aggregate_hourly_breadth(all_metrics)
            
            logger.info(f"Generated {len(hourly_breadth)} hours of breadth data")
            
            # Save results
            self._save_hourly_data(hourly_breadth)
            
            return hourly_breadth
            
        except Exception as e:
            logger.error(f"Error in collect_hourly_data: {e}")
            return []
    
    def _save_hourly_data(self, hourly_breadth):
        """Save hourly breadth data to files"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Save as JSON
            json_file = os.path.join(self.data_dir, f'sma_breadth_hourly_{timestamp}.json')
            with open(json_file, 'w') as f:
                json.dump(hourly_breadth, f, indent=2)
            
            # Save as CSV for analysis
            csv_file = os.path.join(self.data_dir, f'sma_breadth_hourly_{timestamp}.csv')
            
            # Convert to DataFrame for CSV
            df = pd.DataFrame(hourly_breadth)
            df.to_csv(csv_file, index=False)
            
            # Save latest data for dashboard
            latest_file = os.path.join(self.data_dir, 'sma_breadth_hourly_latest.json')
            with open(latest_file, 'w') as f:
                json.dump(hourly_breadth, f, indent=2)
            
            # Also save in main historical_breadth_data folder for dashboard access
            dashboard_file = os.path.join(self.script_dir, 'historical_breadth_data', 'sma_breadth_hourly_latest.json')
            Path(os.path.dirname(dashboard_file)).mkdir(parents=True, exist_ok=True)
            with open(dashboard_file, 'w') as f:
                json.dump(hourly_breadth, f, indent=2)
            
            logger.info(f"Hourly data saved to:")
            logger.info(f"  JSON: {json_file}")
            logger.info(f"  CSV: {csv_file}")
            logger.info(f"  Latest: {latest_file}")
            logger.info(f"  Dashboard: {dashboard_file}")
            
        except Exception as e:
            logger.error(f"Error saving hourly data: {e}")
    
    def update_hourly_data(self):
        """Update hourly data with latest information (called every hour during market)"""
        try:
            # Load existing data
            latest_file = os.path.join(self.data_dir, 'sma_breadth_hourly_latest.json')
            existing_data = []
            
            if os.path.exists(latest_file):
                with open(latest_file, 'r') as f:
                    existing_data = json.load(f)
            
            # Get current hour
            now = datetime.now()
            
            # Check if market is open
            if now.weekday() >= 5:  # Weekend
                logger.info("Market closed - weekend")
                return existing_data
            
            market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
            market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
            
            if now < market_open or now > market_close:
                logger.info("Market closed - outside trading hours")
                return existing_data
            
            logger.info(f"Updating hourly data for {now.strftime('%Y-%m-%d %H:00')}")
            
            # Collect data for current hour only
            tickers = self.load_ticker_list()
            current_hour_metrics = []
            
            for ticker in tickers[:50]:  # Limit to 50 for speed
                try:
                    # Fetch latest hourly data (last 2 hours)
                    ticker_data = self.fetch_hourly_data_zerodha(ticker, days=1)
                    
                    if ticker_data and ticker_data['data']:
                        # Get only the latest hour
                        latest = ticker_data['data'][-1] if ticker_data['data'] else None
                        if latest:
                            current_hour_metrics.append({
                                'datetime': latest['DateTime'],
                                'ticker': ticker,
                                'close': latest['Close'],
                                'volume': latest['Volume'],
                                'above_sma20': 1 if latest.get('Close', 0) > latest.get('SMA20', 0) else 0,
                                'above_sma50': 1 if latest.get('Close', 0) > latest.get('SMA50', 0) else 0,
                                'above_avg_volume': 1 if latest.get('Volume', 0) > latest.get('Volume_SMA20', 0) else 0
                            })
                    
                    time.sleep(0.2)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error updating {ticker}: {e}")
            
            # Aggregate current hour data
            if current_hour_metrics:
                hourly_update = self.aggregate_hourly_breadth(current_hour_metrics)
                
                # Merge with existing data
                if hourly_update:
                    # Remove any existing entry for current hour
                    current_hour_str = now.strftime('%Y-%m-%d %H:00:00')
                    existing_data = [d for d in existing_data if not d['datetime'].startswith(current_hour_str[:13])]
                    
                    # Add new hour data
                    existing_data.extend(hourly_update)
                    
                    # Sort by datetime
                    existing_data = sorted(existing_data, key=lambda x: x['datetime'])
                    
                    # Keep only last 30 days
                    cutoff = (now - timedelta(days=30)).isoformat()
                    existing_data = [d for d in existing_data if d['datetime'] > cutoff]
                    
                    # Save updated data
                    self._save_hourly_data(existing_data)
                    
                    logger.info(f"Updated hourly data with {len(hourly_update)} new entries")
            
            return existing_data
            
        except Exception as e:
            logger.error(f"Error updating hourly data: {e}")
            return existing_data


def main(days=30, update_only=False):
    """Main execution function"""
    logger.info("Starting SMA Breadth Hourly Data Collection")
    
    collector = SMABreadthHourlyCollector()
    
    if update_only:
        # Just update with latest hour
        logger.info("Update mode - collecting latest hour only")
        hourly_breadth = collector.update_hourly_data()
    else:
        # Full collection for specified days
        logger.info(f"Full collection mode - collecting {days} days of hourly data")
        hourly_breadth = collector.collect_hourly_data(days=days)
    
    if hourly_breadth:
        logger.info(f"✓ Successfully collected {len(hourly_breadth)} hours of breadth data")
        
        # Print summary statistics
        df = pd.DataFrame(hourly_breadth)
        if not df.empty:
            logger.info(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
            logger.info(f"SMA20 Breadth - Min: {df['sma20_breadth'].min():.1f}%, Max: {df['sma20_breadth'].max():.1f}%, Avg: {df['sma20_breadth'].mean():.1f}%")
            logger.info(f"SMA50 Breadth - Min: {df['sma50_breadth'].min():.1f}%, Max: {df['sma50_breadth'].max():.1f}%, Avg: {df['sma50_breadth'].mean():.1f}%")
            logger.info(f"Volume Breadth - Min: {df['volume_breadth'].min():.1f}%, Max: {df['volume_breadth'].max():.1f}%, Avg: {df['volume_breadth'].mean():.1f}%")
    else:
        logger.error("✗ Failed to collect hourly data")


if __name__ == "__main__":
    import sys
    
    # Check for command line arguments
    update_only = "--update" in sys.argv
    days = 30  # Default to 30 days
    
    # Check for custom days parameter
    for arg in sys.argv:
        if arg.startswith("--days="):
            try:
                days = int(arg.split("=")[1])
            except:
                pass
    
    main(days=days, update_only=update_only)