import os
import pandas as pd
import logging
import datetime
import json
from dateutil.relativedelta import relativedelta
import time
import glob
from kiteconnect import KiteConnect

from config import get_config

logger = logging.getLogger(__name__)

class DataHandler:
    """Handles market data fetching and processing"""
    
    def __init__(self):
        self.config = get_config()
        self.api_key = self.config.get('API', 'api_key')
        self.access_token = self.config.get('API', 'access_token')
        self.exchange = self.config.get('Trading', 'exchange')
        
        # Cache for data
        self.instruments_df = None
        self.instrument_tokens = {}
        self.data_cache = {}
        self.ltp_cache = {}
        self.ltp_timestamp = {}
        
        # For persistent state storage
        self.data_dir = self.config.get('System', 'data_dir')
        self.state_file = os.path.join(self.data_dir, 'persistent_state.json')
        self.state_data = self._load_state_data()
        
        # Initialize Kite Connect
        self.kite = self._initialize_kite()
        
    def _initialize_kite(self):
        """Initialize Kite Connect client with error handling"""
        try:
            kite = KiteConnect(api_key=self.api_key)
            kite.set_access_token(self.access_token)
            logger.info("KiteConnect initialized successfully")
            return kite
        except Exception as e:
            logger.error(f"Failed to initialize KiteConnect: {e}")
            raise
    
    def get_instruments_data(self):
        """Fetch instruments data with caching"""
        if self.instruments_df is None:
            try:
                logger.info("Fetching instruments data from exchange")
                instruments = self.kite.instruments(self.exchange)
                self.instruments_df = pd.DataFrame(instruments)
                logger.info(f"Fetched {len(instruments)} instruments successfully")
            except Exception as e:
                logger.error(f"Error fetching instruments data: {e}")
                self.instruments_df = pd.DataFrame()
        return self.instruments_df
    
    def get_instrument_token(self, ticker):
        """Get instrument token for a ticker with caching"""
        ticker = ticker.upper()
        if ticker in self.instrument_tokens:
            return self.instrument_tokens[ticker]

        df = self.get_instruments_data()
        if df.empty:
            logger.warning("Instruments data is empty. Cannot lookup instrument token.")
            return None

        # Use vectorized operations for filtering
        df_filtered = df[df['tradingsymbol'].str.upper() == ticker]

        if not df_filtered.empty:
            token = int(df_filtered.iloc[0]['instrument_token'])
            self.instrument_tokens[ticker] = token
            return token
        else:
            logger.warning(f"Instrument token for {ticker} not found.")
            return None
    
    def fetch_historical_data(self, ticker, interval, from_date, to_date):
        """Fetch historical data with caching and error handling"""
        cache_key = f"{ticker}_{interval}_{from_date}_{to_date}"

        # Check if data is in cache
        if cache_key in self.data_cache:
            return self.data_cache[cache_key]

        token = self.get_instrument_token(ticker)
        if token is None:
            logger.warning(f"Instrument token for {ticker} not found.")
            return pd.DataFrame()

        try:
            logger.info(f"Fetching data for {ticker} with interval {interval} from {from_date} to {to_date}...")
            data = self.kite.historical_data(token, from_date, to_date, interval)

            if not data:
                logger.warning(f"No data returned for {ticker}.")
                return pd.DataFrame()

            df = pd.DataFrame(data)
            df.rename(columns={
                "date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume"
            }, inplace=True)

            # Optimize date handling
            df['Date'] = pd.to_datetime(df['Date'])
            df['Ticker'] = ticker

            # Store in cache
            self.data_cache[cache_key] = df
            logger.info(f"Data successfully fetched for {ticker}.")
            return df

        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return pd.DataFrame()
    
    def fetch_current_price(self, ticker, max_retries=3):
        """Fetch current close price with caching to reduce API calls"""
        current_time = time.time()
        ticker = ticker.upper()
        cache_ttl = 60  # seconds

        # Use cached value if available and not expired
        if ticker in self.ltp_cache and current_time - self.ltp_timestamp.get(ticker, 0) < cache_ttl:
            return self.ltp_cache[ticker]

        token = self.get_instrument_token(ticker)
        if token is None:
            logger.warning(f"Instrument token for {ticker} not found.")
            return None

        for retry in range(max_retries):
            try:
                ltp_data = self.kite.ltp(f"{self.exchange}:{ticker}")
                key = f"{self.exchange}:{ticker}"

                if ltp_data and key in ltp_data:
                    current_price = ltp_data[key]["last_price"]

                    # Update cache
                    self.ltp_cache[ticker] = current_price
                    self.ltp_timestamp[ticker] = current_time

                    logger.info(f"[Real-time] Ticker {ticker} - Current Price: {current_price}")
                    return current_price
                else:
                    logger.warning(f"No LTP data for {ticker}.")
                    if retry < max_retries - 1:
                        time.sleep(0.5)  # Wait before retrying
                    else:
                        return None
            except Exception as e:
                logger.error(f"Error fetching current price for {ticker}: {e}")
                if retry < max_retries - 1:
                    time.sleep(0.5)  # Wait before retrying
                else:
                    return None
        
        return None
    
    def get_tickers_from_file(self, file_path):
        """Load ticker symbols from Excel file"""
        try:
            df = pd.read_excel(file_path, sheet_name='Ticker', engine='openpyxl')
            tickers = df['Ticker'].str.strip().dropna().tolist()
            logger.info(f"Loaded {len(tickers)} tickers from {file_path}")
            return tickers
        except Exception as e:
            logger.error(f"Error loading tickers from {file_path}: {e}")
            return []
    
    def get_latest_signal_files(self):
        """Find the latest signal files in the data directory"""
        data_dir = self.config.get('System', 'data_dir')
        
        # Find long file
        long_pattern = os.path.join(data_dir, "EMA_KV_F_Zerodha*.xlsx")
        long_files = glob.glob(long_pattern)
        if not long_files:
            logger.error("No long signal files found in the data directory.")
            return None, None
            
        latest_long_file = max(long_files, key=os.path.getmtime)
        
        # Find short file
        short_pattern = os.path.join(data_dir, "EMA_KV_F_Short_Zerodha*.xlsx")
        short_files = glob.glob(short_pattern)
        if not short_files:
            logger.error("No short signal files found in the data directory.")
            return latest_long_file, None
            
        latest_short_file = max(short_files, key=os.path.getmtime)
        
        logger.info(f"Latest long file: {os.path.basename(latest_long_file)}")
        logger.info(f"Latest short file: {os.path.basename(latest_short_file)}")
        
        return latest_long_file, latest_short_file
        
    def get_previous_candle(self, ticker, interval="60minute", max_retries=3):
        """Get the previous completed candle for a given ticker
        
        Args:
            ticker (str): The trading symbol
            interval (str): Candle timeframe (default: 60minute)
            max_retries (int): Number of retries on failure
            
        Returns:
            dict: Previous candle with open, high, low, close values or None if not available
        """
        ticker = ticker.upper()
        token = self.get_instrument_token(ticker)
        if token is None:
            logger.error(f"Token not found for {ticker}. Cannot get previous candle.")
            return None
            
        # Calculate start and end times to get the last 2 candles
        end_date = datetime.datetime.now()
        
        # Determine time offset based on interval
        if interval == "5minute":
            start_date = end_date - datetime.timedelta(minutes=15)  # Get last 3 candles
        elif interval == "15minute":
            start_date = end_date - datetime.timedelta(minutes=45)  # Get last 3 candles
        elif interval == "30minute":
            start_date = end_date - datetime.timedelta(minutes=90)  # Get last 3 candles
        elif interval == "60minute" or interval == "1hour":
            start_date = end_date - datetime.timedelta(minutes=180)  # Get last 3 candles
        else:
            start_date = end_date - datetime.timedelta(minutes=180)  # Default to 3x60min
        
        retry = 0
        while retry < max_retries:
            try:
                candles = self.kite.historical_data(token, start_date, end_date, interval)
                if len(candles) >= 2:
                    # Return the previous (second to last) candle
                    return candles[-2]
                elif len(candles) == 1:
                    # Only one candle available, use it
                    logger.warning(f"Only one candle available for {ticker}, using it as previous candle")
                    return candles[0]
                else:
                    logger.warning(f"No candles found for {ticker}")
                    return None
            except Exception as e:
                retry += 1
                wait_time = 2 ** retry  # Exponential backoff
                logger.error(f"Error getting previous candle for {ticker}: {e}")
                if retry < max_retries:
                    logger.info(f"Retrying {retry}/{max_retries} after {wait_time} seconds.")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"Max retries reached for {ticker}. Cannot get previous candle.")
                    return None
        
        return None
        
    def _load_state_data(self):
        """Load persistent state data from JSON file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    logger.debug(f"Loaded persistent state data from {self.state_file}")
                    return data
            else:
                logger.info(f"No persistent state file found at {self.state_file}, creating new one")
                return {}
        except Exception as e:
            logger.error(f"Error loading persistent state data: {e}")
            return {}
            
    def _save_state_data(self):
        """Save persistent state data to JSON file"""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.state_data, f, indent=2)
            logger.debug(f"Saved persistent state data to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving persistent state data: {e}")
            
    def get_state_value(self, key, default=None):
        """Get a value from the persistent state storage"""
        return self.state_data.get(key, default)
        
    def set_state_value(self, key, value):
        """Set a value in the persistent state storage"""
        self.state_data[key] = value
        self._save_state_data()

# Create singleton instance
_data_handler = None

def get_data_handler():
    """Get or create the singleton data handler instance"""
    global _data_handler
    if _data_handler is None:
        _data_handler = DataHandler()
    return _data_handler
