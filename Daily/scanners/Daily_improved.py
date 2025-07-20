#!/usr/bin/env python
# Standard library imports
import os
import time
import logging
import datetime
import functools
import concurrent.futures
import sys
import json
import traceback
import argparse
import configparser

# Third-party imports
import numpy as np  # Make sure numpy is properly imported
import pandas as pd
import pytz
from dateutil.relativedelta import relativedelta
from kiteconnect import KiteConnect

# Add parent directory to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Daily Improved Scanner")
    parser.add_argument("-u", "--user", default="Sai", help="User name to use for API credentials (default: Sai)")
    return parser.parse_args()

# Load credentials from Daily/config.ini
def load_daily_config(user_name="Sai"):
    """Load configuration from Daily/config.ini file with user-specific credentials"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')

    if not os.path.exists(config_path):
        logger.error(f"config.ini file not found at {config_path}")
        raise FileNotFoundError(f"config.ini file not found at {config_path}")

    config = configparser.ConfigParser()
    config.read(config_path)

    # Get user-specific API credentials
    credential_section = f'API_CREDENTIALS_{user_name}'
    if credential_section not in config.sections():
        logger.error(f"No credentials found for user {user_name} in {config_path}")
        raise ValueError(f"No credentials found for user {user_name}")

    return config

# Get user from arguments
args = parse_args()
user_name = args.user
logger.info(f"Using credentials for user: {user_name}")

# -----------------------------
# Settings & File Paths
# -----------------------------
# Get config and credentials
config = load_daily_config(user_name)
credential_section = f'API_CREDENTIALS_{user_name}'

# Zerodha Kite Connect credentials from config
KITE_API_KEY = config.get(credential_section, 'api_key')
ACCESS_TOKEN = config.get(credential_section, 'access_token')

# Validate credentials
if not KITE_API_KEY or not ACCESS_TOKEN:
    logger.error(f"Missing API credentials for user {user_name}. Please check config.ini")
    raise ValueError(f"API key or access token missing for user {user_name}")

logger.info(f"Successfully loaded API credentials for user {user_name}")

# Max workers for parallel processing
MAX_WORKERS = 10  # Increased for better parallelism

# Global Parameters
ACCOUNT_VALUE = config.get_float('Trading', 'account_value', fallback=100000.0)
VOLUME_SPIKE_THRESHOLD = 4.0  # Modified threshold for volume spike (not used directly now)
MAX_CONCURRENT_REQUESTS = 10  # Increased to process more tickers simultaneously
REQUEST_DELAY = 0.1  # Reduced delay between API requests for faster processing

# Define the input file path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data")
input_file_path = os.path.join(DATA_DIR, "Ticker.xlsx")

# Construct the output file paths with formatted date and time
today = datetime.datetime.now()
formatted_date = today.strftime("%d_%m_%Y")
formatted_time = today.strftime("%H_%M")
output_file_path = os.path.join(os.path.dirname(SCRIPT_DIR), 'scanner_files', f'Custom_Scanner_{formatted_date}_{formatted_time}.xlsx')

# Mapping for interval to Kite Connect API parameters
interval_mapping = {
    '5m': '5minute',
    '1h': '60minute',
    '1d': 'day',
    '1w': 'week'
}

# Define the required columns for the summary output
required_columns = [
    'Ticker', 'SL_New', 'TP_New', 'PosSize', 'Daily_Slope'
]

# Fallback to CSV data if API fails
USE_FALLBACK_DATA = True
FALLBACK_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'BT', 'data')

# -----------------------------
# Data Cache Implementation
# -----------------------------
class DataCache:
    def __init__(self):
        self.instruments_df = None
        self.instrument_tokens = {}
        self.data_cache = {}


cache = DataCache()

# LTP cache to reduce API calls for current prices
ltp_cache = {}
ltp_timestamp = {}
LTP_CACHE_TTL = 60  # seconds


# -----------------------------
# Kite Connect Client Initialization
# -----------------------------
def initialize_kite():
    """Initialize Kite Connect client with error handling"""
    try:
        # Log credential information
        logger.info(f"Initializing KiteConnect with credentials for user: {user_name}")

        kite = KiteConnect(api_key=KITE_API_KEY)
        kite.set_access_token(ACCESS_TOKEN)
        return kite
    except Exception as e:
        logger.error(f"Failed to initialize Kite Connect: {e}")
        raise


kite = initialize_kite()


# -----------------------------
# Instrument Token Lookup Functions
# -----------------------------
def get_instruments_data():
    """Fetch and cache instruments data from Zerodha"""
    if cache.instruments_df is None:
        try:
            instruments = kite.instruments("NSE")
            if instruments:
                cache.instruments_df = pd.DataFrame(instruments)
                logger.info("Fetched instruments data successfully.")
            else:
                # If instruments is empty, try to load from backup file
                try:
                    backup_file = os.path.join(DATA_DIR, "instruments_backup.csv")
                    if os.path.exists(backup_file):
                        cache.instruments_df = pd.read_csv(backup_file)
                        logger.info("Loaded instruments data from backup file.")
                    else:
                        cache.instruments_df = pd.DataFrame()
                        logger.error("No instruments data available and no backup file found.")
                except Exception as e:
                    logger.error(f"Error loading backup instruments data: {e}")
                    cache.instruments_df = pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching instruments data: {e}")
            # Try to load from backup file
            try:
                backup_file = os.path.join(DATA_DIR, "instruments_backup.csv")
                if os.path.exists(backup_file):
                    cache.instruments_df = pd.read_csv(backup_file)
                    logger.info("Loaded instruments data from backup file after API error.")
                else:
                    cache.instruments_df = pd.DataFrame()
            except Exception as backup_e:
                logger.error(f"Error loading backup instruments data: {backup_e}")
                cache.instruments_df = pd.DataFrame()
    return cache.instruments_df


def save_instruments_data():
    """Save instruments data to a backup file for future use"""
    try:
        instruments = kite.instruments("NSE")
        if instruments:
            df = pd.DataFrame(instruments)
            backup_file = os.path.join(DATA_DIR, "instruments_backup.csv")
            df.to_csv(backup_file, index=False)
            logger.info(f"Successfully saved instruments data to {backup_file}")
            return True
        else:
            logger.error("No instruments data to save")
            return False
    except Exception as e:
        logger.error(f"Error saving instruments data: {e}")
        return False


def get_instrument_token(ticker):
    """Get instrument token for a ticker with caching"""
    if ticker in cache.instrument_tokens:
        return cache.instrument_tokens[ticker]

    df = get_instruments_data()
    if df.empty:
        logger.warning("Instruments data is empty. Cannot lookup instrument token.")
        return None

    ticker_upper = ticker.upper()
    
    # Try to find by exact match on trading symbol first
    if 'tradingsymbol' in df.columns:
        df_filtered = df[df['tradingsymbol'].str.upper() == ticker_upper]
        if not df_filtered.empty:
            token = int(df_filtered.iloc[0]['instrument_token'])
            cache.instrument_tokens[ticker] = token
            return token
    
    # If not found and we have a manual mapping, use that
    manual_tokens = {
        "JYOTISTRUC": 2695937,
        # Add more manual mappings as needed for problematic tickers
        "LEMONTREE": 4536833,
        "RAYMOND": 7229441,
        "FEDERALBNK": 261889,
        "SANOFI": 7223553,
        "BIRLACORPN": 36865,
        "WARDINMOBI": 108033
    }
    
    if ticker_upper in manual_tokens:
        token = manual_tokens[ticker_upper]
        cache.instrument_tokens[ticker] = token
        logger.info(f"Using manually configured token {token} for {ticker}")
        return token
    
    logger.warning(f"Instrument token for {ticker} not found.")
    return None


# -----------------------------
# Data Fetching Functions
# -----------------------------
def fetch_data_kite(ticker, interval, from_date, to_date):
    """Fetch historical data with caching and error handling"""
    import time

    cache_key = f"{ticker}_{interval}_{from_date}_{to_date}"

    # Fast path: check cache first
    if cache_key in cache.data_cache:
        return cache.data_cache[cache_key]

    # Check for token
    token = get_instrument_token(ticker)
    if token is None:
        logger.warning(f"Instrument token for {ticker} not found.")
        # Try fallback to CSV data if available
        if USE_FALLBACK_DATA and interval == 'day':
            df = fetch_fallback_data(ticker, interval)
            if not df.empty:
                cache.data_cache[cache_key] = df  # Cache the fallback data
            return df
        return pd.DataFrame()

    # Try API with retries
    max_retries = 5
    retry_delay = 2  # seconds
    backoff_factor = 1.5  # Exponential backoff

    for attempt in range(max_retries):
        try:
            # Only log on the first attempt to reduce log bloat
            if attempt == 0:
                logger.info(f"Fetching data for {ticker} with interval {interval}...")
            else:
                logger.debug(f"Retry {attempt+1} for {ticker} with interval {interval}...")

            data = kite.historical_data(token, from_date, to_date, interval)

            if not data:
                logger.warning(f"No data returned for {ticker}.")
                break  # Break early on empty data

            # Process the data
            df = pd.DataFrame(data)
            df.rename(columns={
                "date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume"
            }, inplace=True)

            df['Date'] = pd.to_datetime(df['Date'])
            df['Ticker'] = ticker

            # Cache and return on success
            cache.data_cache[cache_key] = df
            return df

        except Exception as e:
            if "Too many requests" in str(e) and attempt < max_retries - 1:
                wait_time = retry_delay * (backoff_factor ** attempt)
                logger.warning(
                    f"Rate limit hit for {ticker}. Waiting {wait_time:.2f} seconds before retry...")
                time.sleep(wait_time)
            else:
                logger.error(f"Error fetching data for {ticker}: {e}")
                break  # Break on other errors

    # Fallback path if all attempts failed
    if USE_FALLBACK_DATA and interval == 'day':
        logger.info(f"Using fallback data for {ticker} after API failure")
        df = fetch_fallback_data(ticker, interval)
        if not df.empty:
            cache.data_cache[cache_key] = df  # Cache the fallback data
        return df

    return pd.DataFrame()


def fetch_fallback_data(ticker, interval):
    """Fetch data from backup CSV files"""
    try:
        # Check for daily data file
        if interval == 'day':
            csv_file = os.path.join(FALLBACK_DATA_DIR, f"{ticker}_day.csv")
            if os.path.exists(csv_file):
                logger.info(f"Using fallback CSV data for {ticker} from {csv_file}")
                df = pd.read_csv(csv_file)
                
                # Convert column names if needed
                columns_map = {
                    'date': 'Date',
                    'open': 'Open', 
                    'high': 'High',
                    'low': 'Low',
                    'close': 'Close',
                    'volume': 'Volume'
                }
                
                df = df.rename(columns={k: v for k, v in columns_map.items() if k in df.columns})
                
                # Ensure required columns exist
                required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
                missing_cols = [col for col in required_cols if col not in df.columns]
                
                if missing_cols:
                    logger.warning(f"CSV file for {ticker} is missing columns: {', '.join(missing_cols)}")
                    # Add placeholder columns
                    for col in missing_cols:
                        if col == 'Date':
                            df['Date'] = pd.date_range(start='2022-01-01', periods=len(df))
                        else:
                            df[col] = 0.0
                
                # Make sure Date is a datetime
                df['Date'] = pd.to_datetime(df['Date'])
                
                # Add ticker column
                df['Ticker'] = ticker
                
                return df
        
        logger.warning(f"No fallback data available for {ticker} with interval {interval}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error fetching fallback data for {ticker}: {e}")
        return pd.DataFrame()


def fetch_current_close(ticker):
    """Fetch current close price with caching to reduce API calls"""
    current_time = time.time()

    if ticker in ltp_cache and current_time - ltp_timestamp.get(ticker, 0) < LTP_CACHE_TTL:
        return ltp_cache[ticker]

    token = get_instrument_token(ticker)
    if token is None:
        logger.warning(f"Instrument token for {ticker} not found.")
        return np.nan

    try:
        ltp_data = kite.ltp(f"NSE:{ticker}")
        key = f"NSE:{ticker}"

        if ltp_data and key in ltp_data:
            current_close = ltp_data[key]["last_price"]
            ltp_cache[ticker] = current_close
            ltp_timestamp[ticker] = current_time
            logger.info(f"[Real-time] Ticker {ticker} - Current Close: {current_close}")
            return current_close
        else:
            logger.warning(f"No LTP data for {ticker}.")
            # Try to get the last close from historical data
            try:
                daily_data = fetch_data_kite(ticker, interval_mapping['1d'], 
                                            (datetime.datetime.now() - datetime.timedelta(days=5)).strftime('%Y-%m-%d'),
                                            datetime.datetime.now().strftime('%Y-%m-%d'))
                if not daily_data.empty:
                    last_close = daily_data['Close'].iloc[-1]
                    logger.info(f"Using historical last close for {ticker}: {last_close}")
                    ltp_cache[ticker] = last_close
                    ltp_timestamp[ticker] = current_time
                    return last_close
            except Exception as he:
                logger.warning(f"Could not get historical last close for {ticker}: {he}")
            
            return np.nan

    except Exception as e:
        logger.error(f"Error fetching current close for {ticker}: {e}")
        # Try to get the last close from historical data
        try:
            daily_data = fetch_data_kite(ticker, interval_mapping['1d'], 
                                        (datetime.datetime.now() - datetime.timedelta(days=5)).strftime('%Y-%m-%d'),
                                        datetime.datetime.now().strftime('%Y-%m-%d'))
            if not daily_data.empty:
                last_close = daily_data['Close'].iloc[-1]
                logger.info(f"Using historical last close for {ticker}: {last_close}")
                return last_close
        except Exception as he:
            logger.warning(f"Could not get historical last close for {ticker}: {he}")
            
        return np.nan


# -----------------------------
# Technical Indicator Calculations
# -----------------------------
def calculate_weekly_vwap(data):
    """Calculate Weekly Volume Weighted Average Price"""
    try:
        if data.empty or len(data) < 2:
            return None
            
        data['Week'] = data['Date'].dt.isocalendar().week
        data['Year'] = data['Date'].dt.isocalendar().year
        data['TP'] = (data['High'] + data['Low'] + data['Close']) / 3
        data['TPV'] = data['TP'] * data['Volume']
        
        # Check for zero volume
        if data['Volume'].sum() == 0:
            logger.warning(f"Zero volume data found when calculating VWAP for ticker {data['Ticker'].iloc[0]}")
            return data['Close'].iloc[-1]  # Use last close as fallback
            
        weekly_data = data.groupby(['Year', 'Week']).agg({
            'TPV': 'sum',
            'Volume': 'sum',
            'Date': 'last'
        }).reset_index()
        
        # Check for division by zero
        if weekly_data['Volume'].iloc[-1] == 0:
            logger.warning(f"Zero volume in last week for {data['Ticker'].iloc[0]}, using last close")
            return data['Close'].iloc[-1]
            
        weekly_data['Weekly_VWAP'] = weekly_data['TPV'] / weekly_data['Volume']
        latest_vwap = weekly_data.iloc[-1]['Weekly_VWAP']
        return latest_vwap
    except Exception as e:
        logger.error(f"Error calculating VWAP for {data['Ticker'].iloc[0] if 'Ticker' in data.columns and not data.empty else 'unknown ticker'}: {e}")
        if not data.empty:
            return data['Close'].iloc[-1]  # Use last close as fallback
        return None


def calculate_indicators_daily(daily_data):
    """Calculate daily indicators including SMA, EMA, Keltner Channel, ATR, WM, etc."""
    try:
        # Reduce the required points to handle more tickers
        min_required_points = 30  # Changed from 50
        
        if len(daily_data) < min_required_points:
            logger.warning(
                f"Insufficient daily data points for {daily_data['Ticker'].iloc[0]}. Only {len(daily_data)} records available, minimum of {min_required_points} required.")
            return None

        # Handle NaN values - use newer methods to avoid deprecation warning
        daily_data = daily_data.ffill().bfill()
        
        # Use try/except for each calculation to continue even if one fails
        try:
            daily_data['Daily_20SMA'] = daily_data['Close'].rolling(window=20).mean()
        except Exception as e:
            logger.warning(f"Error calculating 20SMA: {e}")
            daily_data['Daily_20SMA'] = daily_data['Close']
            
        try:
            daily_data['Daily_50EMA'] = daily_data['Close'].ewm(span=50, adjust=False).mean()
        except Exception as e:
            logger.warning(f"Error calculating 50EMA: {e}")
            daily_data['Daily_50EMA'] = daily_data['Close']

        # Calculate additional EMA and WM (for condition 2)
        try:
            daily_data['EMA21'] = daily_data['Close'].ewm(span=21, adjust=False).mean()
            daily_data['WM'] = (daily_data['EMA21'] - daily_data['Daily_50EMA']) / 2
        except Exception as e:
            logger.warning(f"Error calculating EMA21 or WM: {e}")
            daily_data['EMA21'] = daily_data['Close']
            daily_data['WM'] = 0

        # Calculate ATR components
        try:
            prev_close = daily_data['Close'].shift(1)
            tr1 = daily_data['High'] - daily_data['Low']
            tr2 = (daily_data['High'] - prev_close).abs()
            tr3 = (daily_data['Low'] - prev_close).abs()
            daily_data['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            daily_data['ATR'] = daily_data['TR'].rolling(window=20).mean()
        except Exception as e:
            logger.warning(f"Error calculating ATR: {e}")
            # Use a fallback ATR calculation
            daily_data['ATR'] = daily_data['Close'] * 0.02  # Default to 2% of price

        # Keltner Channel calculation (using 20-day SMA and 20-day ATR)
        try:
            daily_data['KC_upper'] = daily_data['Daily_20SMA'] + (2 * daily_data['ATR'])
            daily_data['KC_lower'] = daily_data['Daily_20SMA'] - (2 * daily_data['ATR'])
        except Exception as e:
            logger.warning(f"Error calculating Keltner Channels: {e}")
            daily_data['KC_upper'] = daily_data['Close'] * 1.04  # Default to 4% above price
            daily_data['KC_lower'] = daily_data['Close'] * 0.96  # Default to 4% below price

        # Daily Slope calculation (8-day slope)
        try:
            def calculate_slope(y):
                if len(y) < 8 or y[-1] == 0:
                    return np.nan
                return (np.polyfit(np.arange(len(y)), y, 1)[0] / y[-1]) * 100

            daily_data['Daily_Slope'] = daily_data['Close'].rolling(window=8).apply(
                calculate_slope, raw=True
            )
            
            # Fill NaN slopes with a small default value
            daily_data['Daily_Slope'] = daily_data['Daily_Slope'].fillna(0.01)
        except Exception as e:
            logger.warning(f"Error calculating slope: {e}")
            daily_data['Daily_Slope'] = 0.01  # Default to small positive slope

        # Calculate risk management parameters
        try:
            daily_data['PosSize'] = ACCOUNT_VALUE / daily_data['Close']
            daily_data['SL1'] = daily_data['Close'] - (1.2 * daily_data['ATR'])
            daily_data['SL2'] = daily_data['Close'] - (3 * daily_data['ATR'])
            daily_data['TP1'] = daily_data['Close'] + 2 * daily_data['ATR']
        except Exception as e:
            logger.warning(f"Error calculating risk parameters: {e}")
            daily_data['PosSize'] = ACCOUNT_VALUE / daily_data['Close']
            daily_data['SL1'] = daily_data['Close'] * 0.95  # Default to 5% below price
            daily_data['SL2'] = daily_data['Close'] * 0.90  # Default to 10% below price
            daily_data['TP1'] = daily_data['Close'] * 1.10  # Default to 10% above price

        return daily_data
    except Exception as e:
        logger.error(f"Error calculating daily indicators: {e}")
        return None


def calculate_hourly_indicators(hourly_data):
    """Calculate hourly VWAP and ATR for SL and TP calculations"""
    try:
        # Reduce minimum required points to handle more tickers
        min_required_points = 10  # Changed from 20
        
        if len(hourly_data) < min_required_points:
            logger.warning(
                f"Insufficient hourly data points for {hourly_data['Ticker'].iloc[0]}. Only {len(hourly_data)} records available, minimum of {min_required_points} required.")
                
            # Instead of returning None, provide fallback values
            if len(hourly_data) > 2:
                # Calculate a simplified ATR using average of high-low range
                avg_range = (hourly_data['High'] - hourly_data['Low']).mean()
                return hourly_data['Close'].mean(), avg_range
            return None, None

        # Handle NaN values - use newer methods to avoid deprecation warning
        hourly_data = hourly_data.ffill().bfill()
        
        try:
            hourly_data['Typical_Price'] = (hourly_data['High'] + hourly_data['Low'] + hourly_data['Close']) / 3
            hourly_data['TPV'] = hourly_data['Typical_Price'] * hourly_data['Volume']
            
            # Check for zero volume
            if hourly_data['Volume'].sum() == 0:
                logger.warning(f"Zero volume data found when calculating hourly VWAP for {hourly_data['Ticker'].iloc[0]}")
                hourly_vwap = hourly_data['Close'].mean()
            else:
                cumulative_tpv = hourly_data['TPV'].sum()
                cumulative_volume = hourly_data['Volume'].sum()
                hourly_vwap = cumulative_tpv / cumulative_volume if cumulative_volume > 0 else hourly_data['Close'].mean()
        except Exception as e:
            logger.warning(f"Error calculating hourly VWAP: {e}")
            hourly_vwap = hourly_data['Close'].mean()

        try:
            prev_close = hourly_data['Close'].shift(1)
            tr1 = hourly_data['High'] - hourly_data['Low']
            tr2 = (hourly_data['High'] - prev_close).abs()
            tr3 = (hourly_data['Low'] - prev_close).abs()
            hourly_data['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            hourly_data['Hourly_ATR'] = hourly_data['TR'].rolling(window=min(14, len(hourly_data)-1)).mean()
            
            # Fill NaN ATR values
            hourly_data['Hourly_ATR'] = hourly_data['Hourly_ATR'].fillna((hourly_data['High'] - hourly_data['Low']).mean())
            
            latest_atr = hourly_data['Hourly_ATR'].iloc[-1]
        except Exception as e:
            logger.warning(f"Error calculating hourly ATR: {e}")
            # Use a fallback ATR estimate
            latest_atr = (hourly_data['High'] - hourly_data['Low']).mean()

        return hourly_vwap, latest_atr
    except Exception as e:
        logger.error(f"Error calculating hourly indicators: {e}")
        
        # Try to return fallback values
        if not hourly_data.empty:
            avg_price = hourly_data['Close'].mean() if 'Close' in hourly_data.columns else None
            avg_range = (hourly_data['High'] - hourly_data['Low']).mean() if 'High' in hourly_data.columns and 'Low' in hourly_data.columns else None
            return avg_price, avg_range
            
        return None, None


# -----------------------------
# Ticker Processing Functions
# -----------------------------
def process_ticker(ticker):
    """Process a single ticker based on the modified screening conditions."""
    if not isinstance(ticker, str) or ticker.strip() == "":
        logger.warning(f"Skipping invalid ticker: {ticker}")
        return ticker, None

    logger.info(f"Processing {ticker} with daily timeframe analysis.")
    
    try:
        now = datetime.datetime.now()

        # Fetch data for different timeframes
        from_date_weekly = (now - relativedelta(months=3)).strftime('%Y-%m-%d')
        from_date_daily = (now - relativedelta(months=6)).strftime('%Y-%m-%d')
        from_date_hourly = (now - relativedelta(days=10)).strftime('%Y-%m-%d')
        to_date = now.strftime('%Y-%m-%d')

        # Fetch data in sequence with better error handling
        weekly_data = fetch_data_kite(ticker, interval_mapping['1w'], from_date_weekly, to_date)
        # If weekly data is empty, try extending the date range
        if weekly_data.empty:
            extended_from_date = (now - relativedelta(months=6)).strftime('%Y-%m-%d')
            weekly_data = fetch_data_kite(ticker, interval_mapping['1w'], extended_from_date, to_date)
            if weekly_data.empty:
                logger.warning(f"Could not fetch weekly data for {ticker} even with extended date range")
        
        daily_data = fetch_data_kite(ticker, interval_mapping['1d'], from_date_daily, to_date)
        # If daily data is empty, try extending the date range
        if daily_data.empty:
            extended_from_date = (now - relativedelta(months=12)).strftime('%Y-%m-%d')
            daily_data = fetch_data_kite(ticker, interval_mapping['1d'], extended_from_date, to_date)
            if daily_data.empty:
                logger.warning(f"Could not fetch daily data for {ticker} even with extended date range")
        
        hourly_data = fetch_data_kite(ticker, interval_mapping['1h'], from_date_hourly, to_date)
        # If hourly data is empty, try a shorter range
        if hourly_data.empty:
            shorter_from_date = (now - relativedelta(days=5)).strftime('%Y-%m-%d')
            hourly_data = fetch_data_kite(ticker, interval_mapping['1h'], shorter_from_date, to_date)
            if hourly_data.empty:
                logger.warning(f"Could not fetch hourly data for {ticker} even with shorter date range")
                # Create a minimal hourly dataframe with daily data
                if not daily_data.empty:
                    logger.info(f"Creating synthetic hourly data from daily data for {ticker}")
                    hourly_data = daily_data.copy()
                    # Create 7 hourly rows per day by repeating the daily data
                    expanded_data = []
                    for _, row in hourly_data.iterrows():
                        base_date = row['Date']
                        for hour in range(9, 16):  # 9 AM to 3 PM
                            hour_row = row.copy()
                            hour_row['Date'] = pd.Timestamp(base_date.year, base_date.month, base_date.day, hour)
                            expanded_data.append(hour_row)
                    if expanded_data:
                        hourly_data = pd.DataFrame(expanded_data)

        # Check if we have at least daily data
        if daily_data.empty:
            logger.warning(f"No daily data for {ticker}, skipping.")
            return ticker, None

        # Even if we're missing some data, try to process what we have
        if weekly_data.empty and not hourly_data.empty:
            logger.warning(f"Weekly data missing for {ticker}, using daily data for weekly calculations.")
            weekly_data = daily_data.copy()
            # Resample to weekly if needed
            weekly_data['WeekNum'] = weekly_data['Date'].dt.isocalendar().week
            weekly_data['Year'] = weekly_data['Date'].dt.isocalendar().year
            weekly_data = weekly_data.groupby(['Year', 'WeekNum']).agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum',
                'Date': 'last',
                'Ticker': 'first'
            }).reset_index()

        # Calculate indicators with robust error handling
        try:
            if not weekly_data.empty:
                weekly_vwap = calculate_weekly_vwap(weekly_data)
            else:
                weekly_vwap = None
                
            daily_data_with_indicators = calculate_indicators_daily(daily_data)
            
            if not hourly_data.empty:
                hourly_vwap, hourly_atr = calculate_hourly_indicators(hourly_data)
            else:
                hourly_vwap, hourly_atr = None, None
                
            # If any major calculation fails, use fallbacks
            if weekly_vwap is None and not daily_data.empty:
                logger.warning(f"Using daily close as fallback for weekly VWAP for {ticker}")
                weekly_vwap = daily_data['Close'].iloc[-1]
                
            if daily_data_with_indicators is None:
                logger.warning(f"Failed to calculate daily indicators for {ticker}")
                return ticker, None
                
            if hourly_vwap is None and hourly_atr is None:
                logger.warning(f"Using daily data for hourly indicators for {ticker}")
                hourly_vwap = daily_data['Close'].iloc[-1]
                # Estimate hourly ATR as 1/7 of daily ATR
                if 'ATR' in daily_data_with_indicators.columns:
                    hourly_atr = daily_data_with_indicators['ATR'].iloc[-1] / 7
                else:
                    hourly_atr = (daily_data['High'].iloc[-1] - daily_data['Low'].iloc[-1]) / 7

            current_bar = daily_data_with_indicators.iloc[-1]
            current_close = current_bar['Close']

            # Fetch real-time price if available
            current_market_price = fetch_current_close(ticker)
            if not np.isnan(current_market_price):
                current_close = current_market_price

            # --- New SL and TP Calculations ---
            # SL is set as 98% of the daily KC lower channel
            new_sl = current_bar['KC_lower'] * 0.98
            risk = current_close - new_sl
            new_tp = current_close + 2 * risk

            # --- Screening Conditions ---
            condition1 = current_close > weekly_vwap
            condition2 = current_bar['WM'] > 0
            condition3 = current_close > current_bar['Daily_20SMA']
            condition4 = current_close >= current_bar['KC_upper']
            
            # Volume spike calculation with better error handling
            spike_condition = False
            try:
                if len(daily_data_with_indicators) >= 4:
                    avg_prev_current = daily_data_with_indicators['Volume'].iloc[-4:-1].mean()
                    if avg_prev_current > 0:  # Avoid division by zero
                        spike_current = daily_data_with_indicators['Volume'].iloc[-1] >= 4 * avg_prev_current
                        spike_condition = spike_condition or spike_current
                        
                if len(daily_data_with_indicators) >= 5:
                    avg_prev_last = daily_data_with_indicators['Volume'].iloc[-5:-2].mean()
                    if avg_prev_last > 0:  # Avoid division by zero
                        spike_last = daily_data_with_indicators['Volume'].iloc[-2] >= 4 * avg_prev_last
                        spike_condition = spike_condition or spike_last
            except Exception as e:
                logger.warning(f"Error calculating volume spike for {ticker}: {e}")
                # Set to False instead of True - we don't want to default to including stocks
                spike_condition = False
                
            condition5 = spike_condition

            # More informative logging 
            conditions_status = {
                "Weekly VWAP": f"{condition1} ({current_close:.2f} vs {weekly_vwap:.2f})" if not np.isnan(weekly_vwap) else "N/A",
                "WM > 0": f"{condition2} ({current_bar['WM']:.4f})",
                "Above 20 SMA": f"{condition3} ({current_close:.2f} vs {current_bar['Daily_20SMA']:.2f})",
                "Above KC Upper": f"{condition4} ({current_close:.2f} vs {current_bar['KC_upper']:.2f})",
                "Volume Spike": f"{condition5}"
            }
            logger.info(f"{ticker} conditions: {conditions_status}")
            
            # Must meet all conditions 1, 2, 3, and 4 (volume spike is optional)
            # This ensures we only include stocks that meet the strict criteria
            if condition1 and condition2 and condition3 and condition4:
                logger.info(f"{ticker} meets all required screening conditions!")
                # Build summary without the KC and Above_KC_Upper columns:
                summary = pd.DataFrame({
                    'Ticker': [ticker],
                    'SL_New': [new_sl],
                    'TP_New': [new_tp],
                    'PosSize': [current_bar['PosSize']],
                    'Daily_Slope': [current_bar['Daily_Slope']]
                })
                return ticker, summary
            else:
                criteria_met = []
                criteria_missing = []

                if condition1: criteria_met.append("Weekly VWAP")
                else: criteria_missing.append("Weekly VWAP")

                if condition2: criteria_met.append("WM > 0")
                else: criteria_missing.append("WM > 0")

                if condition3: criteria_met.append("Above 20 SMA")
                else: criteria_missing.append("Above 20 SMA")

                if condition4: criteria_met.append("Above KC Upper")
                else: criteria_missing.append("Above KC Upper")

                if condition5: criteria_met.append("Volume Spike")

                logger.info(f"{ticker} meets: {', '.join(criteria_met)} but is missing: {', '.join(criteria_missing)}. Skipping.")
                return ticker, None

        except Exception as e:
            logger.error(f"Error processing indicators for {ticker}: {str(e)}")
            # Print full stack trace for debugging
            logger.debug(traceback.format_exc())
            return ticker, None

    except Exception as e:
        logger.error(f"Error processing {ticker}: {str(e)}")
        # Print full stack trace for debugging
        logger.debug(traceback.format_exc())
        return ticker, None


# -----------------------------
# Parallel Processing Functions
# -----------------------------
def process_tickers_parallel(tickers):
    """Process all tickers in parallel with rate limiting and better error handling"""
    results = []
    missing_tickers = []
    # Create smaller batches and use more backoff
    batch_size = MAX_CONCURRENT_REQUESTS
    # Setup batches
    ticker_batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    logger.info(
        f"Processing {len(tickers)} tickers in {len(ticker_batches)} batches of up to {batch_size} tickers each")

    # Process each batch with adaptive delays
    consecutive_errors = 0
    for batch_idx, ticker_batch in enumerate(ticker_batches):
        logger.info(f"Processing batch {batch_idx + 1}/{len(ticker_batches)}")
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
                futures = {executor.submit(process_ticker, ticker): ticker for ticker in ticker_batch}
                batch_successes = 0
                batch_failures = 0

                for future in concurrent.futures.as_completed(futures):
                    ticker = futures[future]
                    try:
                        ticker, ticker_result = future.result()
                        if ticker_result is None:
                            missing_tickers.append(ticker)
                            batch_failures += 1
                        else:
                            results.append(ticker_result)
                            batch_successes += 1
                    except Exception as e:
                        logger.error(f"Error processing {ticker}: {e}")
                        missing_tickers.append(ticker)
                        batch_failures += 1

            # Adaptive delay based on success rate
            if batch_idx < len(ticker_batches) - 1:
                success_rate = batch_successes / len(ticker_batch) if ticker_batch else 0

                # If we have a high success rate, reduce delay; if low, increase delay
                if success_rate > 0.7:  # Over 70% success
                    delay_factor = 0.3  # Significantly reduced delay for successful batches
                    consecutive_errors = 0
                elif success_rate < 0.3:  # Under 30% success
                    delay_factor = 1.0  # Keep normal delay for failing batches
                    consecutive_errors += 1
                else:
                    delay_factor = 0.5  # Reduced delay for moderately successful batches
                    consecutive_errors = max(0, consecutive_errors - 1)

                # Increase delay if we have multiple consecutive bad batches, but less aggressively
                if consecutive_errors > 3:  # Only increase after more failures
                    delay_factor *= (1 + consecutive_errors * 0.2)  # Less delay increase

                # Calculate delay but ensure it doesn't exceed 5 seconds
                base_delay = REQUEST_DELAY * min(batch_size, 5)  # Cap the batch size impact
                delay = min(base_delay * delay_factor, 5.0)  # Maximum 5 second delay

                logger.info(f"Batch success rate: {success_rate:.2f}, waiting {delay:.2f} seconds before next batch...")
                time.sleep(delay)
        except Exception as e:
            logger.error(f"Error in batch {batch_idx + 1}: {e}")
            consecutive_errors += 1
            # Continue to next batch even if one fails

    logger.info(f"Processed {len(tickers)} tickers, got {len(results)} results, {len(missing_tickers)} missing")
    return results, missing_tickers


# -----------------------------
# Excel Output Function
# -----------------------------
def write_results_to_excel(results, required_columns, output_file_path):
    """Write results to Excel with proper sorting by Daily Slope"""
    try:
        if not results:
            logger.info("No tickers met all conditions. Creating empty output file.")
            pd.DataFrame(columns=required_columns).to_excel(output_file_path, sheet_name="Scanner_Results", index=False)
            return

        # Handle potential errors with concat if different columns are present
        try:
            results_df = pd.concat(results, sort=False)
        except Exception as e:
            logger.error(f"Error concatenating results: {e}")
            # Try a more robust approach
            combined_results = []
            for result in results:
                if isinstance(result, pd.DataFrame) and not result.empty:
                    # Ensure all required columns exist
                    for col in required_columns:
                        if col not in result.columns:
                            result[col] = np.nan
                    combined_results.append(result)
            
            if not combined_results:
                logger.error("No valid results to combine")
                pd.DataFrame(columns=required_columns).to_excel(output_file_path, sheet_name="Scanner_Results", index=False)
                return
                
            results_df = pd.concat(combined_results, sort=False)
        
        # Filter out NaN values in the sorting column
        results_df = results_df.dropna(subset=['Daily_Slope'])
        
        # Handle empty result after filtering
        if results_df.empty:
            logger.info("No tickers with valid slope data. Creating empty output file.")
            pd.DataFrame(columns=required_columns).to_excel(output_file_path, sheet_name="Scanner_Results", index=False)
            return
            
        results_df = results_df.sort_values(by='Daily_Slope', ascending=False)
        
        # Rename SL_New and TP_New for final output clarity
        results_df = results_df.rename(columns={
            'SL_New': 'SL',
            'TP_New': 'TP',
            'Daily_Slope': 'Slope'
        })
        
        for col in ['SL', 'TP', 'PosSize', 'Slope']:
            if col in results_df.columns:
                results_df[col] = results_df[col].round(2)
                
        results_df.to_excel(output_file_path, sheet_name="Scanner_Results", index=False)
        logger.info(f"Successfully wrote {len(results_df)} qualified tickers to {output_file_path}")

    except Exception as e:
        logger.error(f"Error writing results to Excel file: {e}")
        # Try to save a minimal version to not lose all data
        try:
            minimal_df = pd.DataFrame({
                'Ticker': [r['Ticker'].iloc[0] for r in results if not r.empty],
            })
            minimal_df.to_excel(output_file_path, sheet_name="Scanner_Results", index=False)
            logger.info(f"Saved minimal ticker list with {len(minimal_df)} tickers after error")
        except Exception as e2:
            logger.critical(f"Could not save even minimal results: {e2}")


# Preload frequently used tickers' data to avoid repeated API calls
def preload_common_data():
    """Preload data for frequently used tickers to improve performance"""
    common_tickers = [
        "NIFTY 50", "BANKNIFTY", "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK",
        "INFY", "HINDUNILVR"
    ]
    now = datetime.datetime.now()
    from_date = (now - relativedelta(months=6)).strftime('%Y-%m-%d')
    to_date = now.strftime('%Y-%m-%d')

    logger.info("Preloading data for common indexes and stocks...")

    preloaded = []
    failed = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for ticker in common_tickers:
            # Only preload daily data as it's most commonly used
            futures[executor.submit(fetch_data_kite, ticker, interval_mapping['1d'], from_date, to_date)] = ticker

        for future in concurrent.futures.as_completed(futures):
            ticker = futures[future]
            try:
                result = future.result()
                if not result.empty:
                    preloaded.append(ticker)
                else:
                    failed.append(ticker)
            except Exception:
                failed.append(ticker)

    if preloaded:
        logger.info(f"Successfully preloaded data for {len(preloaded)} common tickers: {', '.join(preloaded)}")
    if failed:
        logger.warning(f"Failed to preload data for {len(failed)} tickers: {', '.join(failed)}")


# -----------------------------
# Main Function
# -----------------------------
def main():
    """Main function to run the stock scanner with improved error handling and performance"""
    start_time = time.time()

    # First check if we need to initialize or update the instruments data backup
    backup_file = os.path.join(DATA_DIR, "instruments_backup.csv")
    if not os.path.exists(backup_file):
        logger.info("Instruments backup file not found. Attempting to create it...")
        save_instruments_data()

    # Attempt to preload the instruments data (done in parallel with ticker loading)
    instruments_future = concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(get_instruments_data)

    # Preload common tickers' data in parallel
    preload_future = concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(preload_common_data)

    # Load tickers in parallel with instrument data loading
    tickers = []
    try:
        try:
            df_tickers = pd.read_excel(input_file_path, sheet_name='Ticker', engine='openpyxl')
            tickers = df_tickers['Ticker'].str.strip().dropna().tolist()
        except Exception as e:
            logger.error(f"Error reading Excel ticker file: {e}")
            # Try CSV as fallback
            try:
                df_tickers = pd.read_csv(input_file_path)
                tickers = df_tickers['Ticker'].str.strip().dropna().tolist()
            except Exception as e2:
                logger.error(f"Error reading CSV ticker file: {e2}")
                # Hard-coded fallback for nifty stocks
                logger.warning("Using hardcoded NIFTY100 list as fallback")
                tickers = [
                    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "HINDUNILVR", "INFY", "KOTAKBANK",
                    "BHARTIARTL", "ITC", "SBIN", "BAJFINANCE", "HCLTECH", "ASIANPAINT", "AXISBANK",
                    "HDFC", "MARUTI", "ULTRACEMCO", "LT", "TATASTEEL", "SUNPHARMA", "TATAMOTORS",
                    "TITAN", "BAJAJFINSV", "ONGC", "TECHM", "CIPLA", "POWERGRID", "DIVISLAB",
                    "DRREDDY", "BAJAJ-AUTO", "ADANIPORTS", "NTPC", "WIPRO", "HDFCLIFE", "IOC", "COALINDIA",
                    "GRASIM", "JSWSTEEL", "ADANIENT", "HINDALCO", "M&M", "SBILIFE", "BRITANNIA", "UPL",
                    "INDUSINDBK", "NESTLEIND", "BPCL", "TATACONSUM", "EICHERMOT", "SHREECEM"
                ]

        # Wait for instrument data to be ready (should be done by now)
        try:
            instruments_future.result(timeout=2)  # Short timeout because this should be done already
        except Exception as e:
            logger.warning(f"Instrument data loading didn't complete in time: {e}")

        # No need to wait for preloading to complete - it can continue in background

        logger.info(f"Loaded {len(tickers)} tickers for scanning")

        # Process tickers in parallel
        processing_start = time.time()
        results, missing_tickers = process_tickers_parallel(tickers)
        processing_time = time.time() - processing_start

        # Write results regardless of failures
        write_results_to_excel(results, required_columns, output_file_path)

        if missing_tickers:
            missing_count = len(set(missing_tickers))
            # Show only first 20 missing tickers to avoid log spam
            display_missing = list(set(missing_tickers))[:20]
            logger.warning(f"Unable to process {missing_count} tickers: {', '.join(display_missing)}{' ...' if missing_count > 20 else ''}")

        # Success rate stats
        success_rate = len(results) / len(tickers) if tickers else 0
        logger.info(f"Found {len(results)} tickers that met screening conditions (Success rate: {success_rate:.1%})")
        logger.info(f"Processing time: {processing_time:.2f} seconds, Total execution time: {time.time() - start_time:.2f} seconds")
        return 0

    except Exception as e:
        logger.error(f"Error in main function: {e}")
        # Print full stack trace for debugging
        logger.debug(traceback.format_exc())
        return 1


# -----------------------------
# Entry Point
# -----------------------------
if __name__ == "__main__":
    # Print banner
    print(f"\n===================================")
    print(f"Daily Improved Scanner")
    print(f"===================================")
    print(f"Using credentials for user: {user_name}")
    print(f"===================================\n")

    sys.exit(main())