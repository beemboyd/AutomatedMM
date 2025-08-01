#!/usr/bin/env python3
"""
Historical Momentum Data Builder
Downloads and stores historical data locally, then calculates momentum for past 7 months
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import sqlite3
import time
import logging
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kiteconnect import KiteConnect
import configparser

class HistoricalMomentumBuilder:
    def __init__(self, user_name: str = 'Sai'):
        """Initialize the historical momentum builder"""
        self.user_name = user_name
        self.setup_logging()
        
        # Setup paths
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.data_dir = os.path.join(self.base_dir, 'Daily', 'Momentum', 'historical_data')
        self.db_path = os.path.join(self.data_dir, 'momentum_history.db')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Initialize Kite connection
        self.kite = self.initialize_kite_connection()
        
        # Load tickers
        self.ticker_file = os.path.join(self.base_dir, 'Daily', 'data', 'Ticker.xlsx')
        self.tickers = self.load_tickers()
        
        # Cache for instrument tokens
        self.instrument_cache = {}
        self.load_instruments()
        
        # Initialize database
        self.init_database()
        
        self.logger.info(f"Historical Momentum Builder initialized with {len(self.tickers)} tickers")
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'momentum_history')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'momentum_history_{datetime.now().strftime("%Y%m%d")}.log')
        
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
        """Initialize Kite connection using config"""
        try:
            # Load config
            config_path = os.path.join(self.base_dir, 'Daily', 'config.ini')
            config = configparser.ConfigParser()
            config.read(config_path)
            
            credential_section = f'API_CREDENTIALS_{self.user_name}'
            
            # Get credentials
            api_key = config.get(credential_section, 'api_key')
            access_token = config.get(credential_section, 'access_token')
            
            # Initialize Kite
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            
            # Test connection
            profile = kite.profile()
            self.logger.info(f"Connected to Kite as: {profile.get('user_name', 'Unknown')}")
            
            return kite
        except Exception as e:
            self.logger.error(f"Failed to initialize Kite connection: {e}")
            raise
    
    def load_instruments(self):
        """Load and cache instrument data"""
        try:
            instruments = self.kite.instruments('NSE')
            for instrument in instruments:
                symbol = instrument['tradingsymbol']
                self.instrument_cache[symbol] = instrument['instrument_token']
            self.logger.info(f"Loaded {len(self.instrument_cache)} instruments")
        except Exception as e:
            self.logger.error(f"Error loading instruments: {e}")
    
    def load_tickers(self) -> List[str]:
        """Load tickers from Excel file"""
        try:
            df = pd.read_excel(self.ticker_file)
            if 'Ticker' in df.columns:
                tickers = df['Ticker'].str.strip().dropna().tolist()
                self.logger.info(f"Loaded {len(tickers)} tickers from {self.ticker_file}")
                return tickers
            else:
                self.logger.error("No 'Ticker' column found in Excel file")
                return []
        except Exception as e:
            self.logger.error(f"Error loading tickers: {e}")
            return []
    
    def init_database(self):
        """Initialize SQLite database for storing historical data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_data (
                ticker TEXT,
                date DATE,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                PRIMARY KEY (ticker, date)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS momentum_data (
                date DATE,
                ticker TEXT,
                timeframe TEXT,
                close REAL,
                ema_5 REAL,
                ema_8 REAL,
                ema_13 REAL,
                ema_21 REAL,
                ema_50 REAL,
                ema_100 REAL,
                wm REAL,
                ema_wm REAL,
                wcross TEXT,
                slope REAL,
                r_value REAL,
                atr REAL,
                meets_criteria INTEGER,
                PRIMARY KEY (date, ticker, timeframe)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_summary (
                date DATE PRIMARY KEY,
                daily_count INTEGER,
                weekly_count INTEGER,
                daily_tickers TEXT,
                weekly_tickers TEXT,
                top_daily_wm TEXT,
                top_weekly_wm TEXT,
                processed_timestamp TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def download_historical_data(self, ticker: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """Download and store historical data for a ticker"""
        try:
            # Check if we already have the data
            conn = sqlite3.connect(self.db_path)
            query = '''
                SELECT * FROM price_data 
                WHERE ticker = ? AND date >= ? AND date <= ?
                ORDER BY date
            '''
            existing_data = pd.read_sql_query(query, conn, params=(ticker, start_date, end_date))
            conn.close()
            
            # If we have complete data, return it
            if len(existing_data) > 0:
                expected_days = (end_date - start_date).days
                if len(existing_data) >= expected_days * 0.7:  # Allow for weekends/holidays
                    self.logger.info(f"Using cached data for {ticker}")
                    return existing_data
            
            # Otherwise, download from Kite
            instrument_token = self.instrument_cache.get(ticker)
            if not instrument_token:
                self.logger.warning(f"Instrument token not found for {ticker}")
                return None
            
            # Download data
            self.logger.info(f"Downloading data for {ticker} from {start_date} to {end_date}")
            data = self.kite.historical_data(
                instrument_token,
                start_date.strftime('%Y-%m-%d %H:%M:%S'),
                end_date.strftime('%Y-%m-%d %H:%M:%S'),
                'day',
                continuous=False,
                oi=False
            )
            
            if data:
                df = pd.DataFrame(data)
                df['ticker'] = ticker
                
                # Store in database
                conn = sqlite3.connect(self.db_path)
                df.to_sql('price_data', conn, if_exists='append', index=False)
                conn.close()
                
                return df
            else:
                return None
                
        except Exception as e:
            if "Too many requests" in str(e):
                self.logger.warning(f"Rate limit hit for {ticker}. Waiting...")
                time.sleep(2)
                return self.download_historical_data(ticker, start_date, end_date)
            else:
                self.logger.error(f"Error downloading data for {ticker}: {e}")
                return None
    
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators (EMAs, WM, ATR, Slope, etc.)"""
        if data.empty or 'close' not in data.columns:
            return pd.DataFrame()
        
        # Ensure data is sorted by date
        data = data.sort_values('date').copy()
        
        # Calculate various EMAs
        data['ema_5'] = data['close'].ewm(span=5, adjust=False).mean()
        data['ema_8'] = data['close'].ewm(span=8, adjust=False).mean()
        data['ema_13'] = data['close'].ewm(span=13, adjust=False).mean()
        data['ema_21'] = data['close'].ewm(span=21, adjust=False).mean()
        data['ema_50'] = data['close'].ewm(span=50, adjust=False).mean()
        data['ema_100'] = data['close'].ewm(span=100, adjust=False).mean()
        
        # Calculate WM (Weighted Momentum)
        data['wm'] = ((data['ema_5'] - data['ema_8']) +
                      (data['ema_8'] - data['ema_13']) +
                      (data['ema_13'] - data['ema_21']) +
                      (data['ema_21'] - data['ema_50'])) / 4
        
        # Only keep positive WM values
        data['wm'] = data['wm'].apply(lambda x: x if x > 0 else np.nan)
        data['ema_wm'] = data['wm'].ewm(span=5, adjust=False).mean()
        data['wcross'] = np.where((data['wm'] > data['ema_wm']) & (data['wm'] > 0), 'Yes', 'No')
        
        # Calculate ATR
        prev_close = data['close'].shift(1)
        tr1 = data['high'] - data['low']
        tr2 = (data['high'] - prev_close).abs()
        tr3 = (data['low'] - prev_close).abs()
        data['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        data['atr'] = data['tr'].rolling(window=20).mean()
        
        # Calculate Slope
        data['slope'] = data['close'].rolling(window=8).apply(
            lambda y: (np.polyfit(np.arange(len(y)), y, 1)[0] / y[-1] * 100) if len(y) > 0 and y[-1] != 0 else np.nan,
            raw=True
        )
        
        # Calculate R (correlation coefficient)
        data['r_value'] = data['close'].rolling(window=8).apply(
            lambda y: np.corrcoef(np.arange(len(y)), y)[0, 1] if len(y) > 1 else np.nan,
            raw=True
        )
        
        # Check if meets criteria (Price > EMA_100 AND Slope > 0)
        data['meets_criteria'] = ((data['close'] > data['ema_100']) & 
                                  (data['slope'] > 0) & 
                                  (~data['ema_100'].isna())).astype(int)
        
        return data
    
    def process_historical_momentum(self, start_date: datetime, end_date: datetime):
        """Process momentum for all tickers for historical period"""
        self.logger.info(f"Processing historical momentum from {start_date} to {end_date}")
        
        # Process in batches to manage memory
        batch_size = 50
        current_date = start_date
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            self.logger.info(f"\nProcessing date: {current_date.strftime('%Y-%m-%d')}")
            
            daily_results = []
            weekly_results = []
            
            # Process tickers in batches
            for i in range(0, len(self.tickers), batch_size):
                batch_tickers = self.tickers[i:i+batch_size]
                self.logger.info(f"Processing batch {i//batch_size + 1}/{(len(self.tickers)-1)//batch_size + 1}")
                
                for ticker in batch_tickers:
                    try:
                        # Get data up to current_date
                        data_end = current_date
                        data_start = current_date - timedelta(days=365)  # 1 year for daily
                        
                        # Download/retrieve data
                        price_data = self.download_historical_data(ticker, data_start, data_end)
                        if price_data is None or price_data.empty:
                            continue
                        
                        # Filter data up to current_date
                        price_data['date'] = pd.to_datetime(price_data['date'])
                        price_data = price_data[price_data['date'] <= current_date]
                        
                        # Calculate indicators
                        price_data = self.calculate_indicators(price_data)
                        
                        # Get the latest data point
                        if not price_data.empty and len(price_data) >= 100:  # Need at least 100 days for EMA_100
                            latest = price_data.iloc[-1]
                            
                            if latest['meets_criteria'] == 1:
                                result = {
                                    'date': current_date,
                                    'ticker': ticker,
                                    'close': latest['close'],
                                    'wm': latest['wm'],
                                    'slope': latest['slope'],
                                    'wcross': latest['wcross'],
                                    'ema_100': latest['ema_100']
                                }
                                daily_results.append(result)
                        
                        # Add small delay to avoid rate limits
                        time.sleep(0.1)
                        
                    except Exception as e:
                        self.logger.error(f"Error processing {ticker}: {e}")
                        continue
            
            # Store results for this date
            self.store_daily_results(current_date, daily_results)
            
            # Move to next date
            current_date += timedelta(days=1)
    
    def store_daily_results(self, date: datetime, results: List[Dict]):
        """Store daily momentum results in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Store individual ticker results
            for result in results:
                cursor.execute('''
                    INSERT OR REPLACE INTO momentum_data 
                    (date, ticker, timeframe, close, wm, slope, wcross, ema_100, meets_criteria)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    date.strftime('%Y-%m-%d'),
                    result['ticker'],
                    'daily',
                    result['close'],
                    result['wm'],
                    result['slope'],
                    result['wcross'],
                    result['ema_100'],
                    1
                ))
            
            # Store daily summary
            tickers = [r['ticker'] for r in results]
            top_wm = sorted(results, key=lambda x: x['wm'] if x['wm'] else 0, reverse=True)[:5]
            
            cursor.execute('''
                INSERT OR REPLACE INTO daily_summary 
                (date, daily_count, daily_tickers, top_daily_wm, processed_timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                date.strftime('%Y-%m-%d'),
                len(results),
                json.dumps(tickers),
                json.dumps(top_wm),
                datetime.now()
            ))
            
            conn.commit()
            self.logger.info(f"Stored {len(results)} momentum results for {date.strftime('%Y-%m-%d')}")
            
        except Exception as e:
            self.logger.error(f"Error storing results: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_historical_summary(self) -> pd.DataFrame:
        """Get historical momentum summary from database"""
        conn = sqlite3.connect(self.db_path)
        query = '''
            SELECT date, daily_count, daily_tickers, top_daily_wm
            FROM daily_summary
            ORDER BY date DESC
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    
    def update_daily_momentum(self):
        """Update momentum for today (to be run daily)"""
        today = datetime.now().date()
        self.process_historical_momentum(
            datetime.combine(today, datetime.min.time()),
            datetime.combine(today, datetime.min.time())
        )


def main():
    """Main function to build historical momentum data"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Build historical momentum database')
    parser.add_argument('--months', type=int, default=7, help='Number of months to process')
    parser.add_argument('--update', action='store_true', help='Update only today\'s data')
    
    args = parser.parse_args()
    
    builder = HistoricalMomentumBuilder()
    
    if args.update:
        # Just update today's data
        builder.update_daily_momentum()
    else:
        # Build historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.months * 30)
        
        print(f"Building historical momentum data for {args.months} months")
        print(f"From: {start_date.strftime('%Y-%m-%d')}")
        print(f"To: {end_date.strftime('%Y-%m-%d')}")
        print("This will take several hours due to API rate limits...")
        
        builder.process_historical_momentum(start_date, end_date)
        
        # Show summary
        summary = builder.get_historical_summary()
        print("\nHistorical Momentum Summary:")
        print(summary.head(10))


if __name__ == '__main__':
    main()