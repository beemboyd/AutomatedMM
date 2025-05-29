#!/usr/bin/env python3
# Standard library imports
import os
import time
import logging
import datetime
import functools
import concurrent.futures
import sys
import argparse
import configparser

# Third-party imports
import numpy as np
import pandas as pd
import pytz
from dateutil.relativedelta import relativedelta
from kiteconnect import KiteConnect

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    parser = argparse.ArgumentParser(description="Daily SMA20 Scanner")
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
MAX_WORKERS = 5  # Adjust based on your system capabilities

# Global Parameters
ACCOUNT_VALUE = config.get_float('Trading', 'account_value', fallback=100000.0)
VOLUME_SPIKE_THRESHOLD = 4.0  # Threshold for volume spike
MAX_CONCURRENT_REQUESTS = 3  # Limit concurrent API requests
REQUEST_DELAY = 0.5  # Add delay between API requests (seconds)

# Define the input file path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
input_file_path = os.path.join(SCRIPT_DIR, "Ticker.xlsx")

# Construct the output file paths with formatted date and time
today = datetime.datetime.now()
formatted_date = today.strftime("%d_%m_%Y")
formatted_time = today.strftime("%H_%M")
output_file_path = os.path.join(SCRIPT_DIR, f'Daily_SMA20_{formatted_date}_{formatted_time}.xlsx')

# Mapping for interval to Kite Connect API parameters
interval_mapping = {
    '5m': '5minute',
    '1h': '60minute',
    '1d': 'day',
    '1w': 'week'
}

# Define the required columns for the summary output
required_columns = [
    'Ticker', 'SL', 'TP', 'PosSize', 'Slope', 'Volume_Spike_Ratio'
]


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
                    backup_file = os.path.join(SCRIPT_DIR, "instruments_backup.csv")
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
                backup_file = os.path.join(SCRIPT_DIR, "instruments_backup.csv")
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
            backup_file = os.path.join(SCRIPT_DIR, "instruments_backup.csv")
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
        # Add more manual mappings as needed
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

    if cache_key in cache.data_cache:
        return cache.data_cache[cache_key]

    token = get_instrument_token(ticker)
    if token is None:
        logger.warning(f"Instrument token for {ticker} not found.")
        return pd.DataFrame()

    max_retries = 3
    retry_delay = 2  # seconds

    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching data for {ticker} with interval {interval} from {from_date} to {to_date}...")
            data = kite.historical_data(token, from_date, to_date, interval)

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

            df['Date'] = pd.to_datetime(df['Date'])
            df['Ticker'] = ticker

            cache.data_cache[cache_key] = df
            logger.info(f"Data successfully fetched for {ticker}.")
            return df

        except Exception as e:
            if "Too many requests" in str(e) and attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                logger.warning(
                    f"Rate limit hit for {ticker}. Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
            else:
                logger.error(f"Error fetching data for {ticker}: {e}")
                return pd.DataFrame()

    logger.error(f"Failed to fetch data for {ticker} after {max_retries} attempts.")
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
            return np.nan

    except Exception as e:
        logger.error(f"Error fetching current close for {ticker}: {e}")
        return np.nan


# -----------------------------
# Technical Indicator Calculations
# -----------------------------
def calculate_weekly_vwap(data):
    """Calculate Weekly Volume Weighted Average Price"""
    data['Week'] = data['Date'].dt.isocalendar().week
    data['Year'] = data['Date'].dt.isocalendar().year
    data['TP'] = (data['High'] + data['Low'] + data['Close']) / 3
    data['TPV'] = data['TP'] * data['Volume']
    weekly_data = data.groupby(['Year', 'Week']).agg({
        'TPV': 'sum',
        'Volume': 'sum',
        'Date': 'last'
    }).reset_index()
    weekly_data['Weekly_VWAP'] = weekly_data['TPV'] / weekly_data['Volume']
    latest_vwap = weekly_data.iloc[-1]['Weekly_VWAP']
    return latest_vwap


def calculate_indicators_daily(daily_data):
    """Calculate daily indicators for SMA20 strategy"""
    if len(daily_data) < 50:
        logger.warning(
            f"Insufficient daily data points. Only {len(daily_data)} records available, minimum of 50 required.")
        return None

    # Calculate SMAs and EMAs
    daily_data['SMA20'] = daily_data['Close'].rolling(window=20).mean()
    daily_data['EMA21'] = daily_data['Close'].ewm(span=21, adjust=False).mean()
    daily_data['EMA50'] = daily_data['Close'].ewm(span=50, adjust=False).mean()
    
    # Calculate WM (spread between EMA21 and EMA50)
    daily_data['WM'] = daily_data['EMA21'] - daily_data['EMA50']

    # Calculate ATR for position sizing and risk management
    prev_close = daily_data['Close'].shift(1)
    tr1 = daily_data['High'] - daily_data['Low']
    tr2 = (daily_data['High'] - prev_close).abs()
    tr3 = (daily_data['Low'] - prev_close).abs()
    daily_data['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    daily_data['ATR'] = daily_data['TR'].rolling(window=20).mean()

    # Volume analysis
    daily_data['Vol_MA20'] = daily_data['Volume'].rolling(window=20).mean()
    daily_data['Volume_Ratio'] = daily_data['Volume'] / daily_data['Vol_MA20']
    
    # Calculate volume spike ratio (today's volume / average of previous 3 days)
    daily_data['Vol_Prev3_Avg'] = daily_data['Volume'].shift(1).rolling(window=3).mean()
    daily_data['Volume_Spike_Ratio'] = daily_data['Volume'] / daily_data['Vol_Prev3_Avg']

    # Slope calculation for momentum
    def calculate_slope(y):
        if len(y) < 8 or y[-1] == 0:
            return np.nan
        return (np.polyfit(np.arange(len(y)), y, 1)[0] / y[-1]) * 100

    daily_data['Slope'] = daily_data['Close'].rolling(window=8).apply(
        calculate_slope, raw=True
    )

    # Risk management parameters
    daily_data['PosSize'] = (ACCOUNT_VALUE * 0.01) / daily_data['ATR']  # Risk 1% of account per trade
    daily_data['SL'] = daily_data['Close'] - (1.5 * daily_data['ATR'])  # Stop loss at 1.5 ATR below current price
    daily_data['TP'] = daily_data['Close'] + (3 * daily_data['ATR'])    # Take profit at 3 ATR above current price

    return daily_data


# -----------------------------
# Ticker Processing Functions
# -----------------------------
def process_ticker(ticker):
    """Process a single ticker based on the SMA20 strategy criteria."""
    if not isinstance(ticker, str) or ticker.strip() == "":
        logger.warning(f"Skipping invalid ticker: {ticker}")
        return None, None

    logger.info(f"Processing {ticker} with SMA20 strategy analysis.")
    now = datetime.datetime.now()

    # Fetch data for different timeframes
    from_date_weekly = (now - relativedelta(months=3)).strftime('%Y-%m-%d')
    from_date_daily = (now - relativedelta(months=6)).strftime('%Y-%m-%d')
    to_date = now.strftime('%Y-%m-%d')

    weekly_data = fetch_data_kite(ticker, interval_mapping['1w'], from_date_weekly, to_date)
    daily_data = fetch_data_kite(ticker, interval_mapping['1d'], from_date_daily, to_date)

    if weekly_data.empty or daily_data.empty:
        logger.warning(f"Insufficient data for {ticker}, skipping.")
        return ticker, None

    try:
        weekly_vwap = calculate_weekly_vwap(weekly_data)
        daily_data_with_indicators = calculate_indicators_daily(daily_data)

        if daily_data_with_indicators is None:
            logger.warning(f"Failed to calculate indicators for {ticker}.")
            return ticker, None

        current_bar = daily_data_with_indicators.iloc[-1]
        current_close = current_bar['Close']

        # Fetch real-time price if available
        current_market_price = fetch_current_close(ticker)
        if not np.isnan(current_market_price):
            current_close = current_market_price

        # --- SMA20 Strategy Screening Conditions ---
        # 1. Price is above the Weekly VWAP
        condition1 = current_close > weekly_vwap
        
        # 2. WM indicator (spread between EMA21 and EMA50) is positive
        condition2 = current_bar['WM'] > 0
        
        # 3. Price is at or above the 20-day SMA
        condition3 = current_close >= current_bar['SMA20']
        
        # 4. Volume spike condition (volume > 1.5x 20-day average)
        condition4 = current_bar['Volume_Spike_Ratio'] >= 1.5

        logger.info(f"{ticker} - Condition 1 (Current Close > Weekly VWAP): {condition1}")
        logger.info(f"{ticker} - Condition 2 (WM indicator > 0): {condition2}")
        logger.info(f"{ticker} - Condition 3 (Current Close >= SMA20): {condition3}")
        logger.info(f"{ticker} - Condition 4 (Volume Spike): {condition4}")
        logger.info(f"{ticker} - Volume Spike Ratio: {current_bar['Volume_Spike_Ratio']:.2f}")

        if condition1 and condition2 and condition3 and condition4:
            logger.info(f"{ticker} meets all SMA20 strategy conditions!")
            
            # Build summary
            summary = pd.DataFrame({
                'Ticker': [ticker],
                'SL': [current_bar['SL']],
                'TP': [current_bar['TP']],
                'PosSize': [current_bar['PosSize']],
                'Slope': [current_bar['Slope']],
                'Volume_Spike_Ratio': [current_bar['Volume_Spike_Ratio']]
            })
            return ticker, summary
        else:
            logger.info(f"{ticker} does not meet all SMA20 strategy conditions.")
            return ticker, None

    except Exception as e:
        logger.error(f"Error processing {ticker}: {e}")
        return ticker, None


# -----------------------------
# Parallel Processing Functions
# -----------------------------
def process_tickers_parallel(tickers):
    """Process all tickers in parallel with rate limiting"""
    results = []
    missing_tickers = []
    batch_size = MAX_CONCURRENT_REQUESTS
    ticker_batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    logger.info(
        f"Processing {len(tickers)} tickers in {len(ticker_batches)} batches of up to {batch_size} tickers each")

    for batch_idx, ticker_batch in enumerate(ticker_batches):
        logger.info(f"Processing batch {batch_idx + 1}/{len(ticker_batches)}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
            futures = {executor.submit(process_ticker, ticker): ticker for ticker in ticker_batch}
            for future in concurrent.futures.as_completed(futures):
                ticker = futures[future]
                try:
                    ticker, ticker_result = future.result()
                    if ticker_result is None:
                        missing_tickers.append(ticker)
                    else:
                        results.append(ticker_result)
                except Exception as e:
                    logger.error(f"Error processing {ticker}: {e}")
                    missing_tickers.append(ticker)
        if batch_idx < len(ticker_batches) - 1:
            delay = REQUEST_DELAY * batch_size
            logger.info(f"Waiting {delay:.2f} seconds before starting next batch...")
            time.sleep(delay)
    return results, missing_tickers


# -----------------------------
# Excel Output Function
# -----------------------------
def write_results_to_excel(results, required_columns, output_file_path):
    """Write results to Excel with proper sorting by Slope (momentum)"""
    try:
        if not results:
            logger.info("No tickers met all SMA20 strategy conditions. Creating empty output file.")
            pd.DataFrame(columns=required_columns).to_excel(output_file_path, sheet_name="SMA20_Results", index=False)
            return

        results_df = pd.concat(results)
        
        # Sort by slope (momentum) descending
        results_df = results_df.sort_values(by='Slope', ascending=False)
        
        # Round numeric columns for readability
        for col in ['SL', 'TP', 'PosSize', 'Slope', 'Volume_Spike_Ratio']:
            if col in results_df.columns:
                results_df[col] = results_df[col].round(2)
        
        # Write to Excel
        results_df.to_excel(output_file_path, sheet_name="SMA20_Results", index=False)
        logger.info(f"Successfully wrote {len(results_df)} qualified tickers to {output_file_path}")

    except Exception as e:
        logger.error(f"Error writing results to Excel file: {e}")


# -----------------------------
# Main Function
# -----------------------------
def main():
    """Main function to run the SMA20 strategy scanner"""
    start_time = time.time()

    # First check if we need to initialize or update the instruments data backup
    backup_file = os.path.join(SCRIPT_DIR, "instruments_backup.csv")
    if not os.path.exists(backup_file):
        logger.info("Instruments backup file not found. Attempting to create it...")
        save_instruments_data()

    # Attempt to preload the instruments data
    get_instruments_data()
    
    try:
        df_tickers = pd.read_excel(input_file_path, sheet_name='Ticker', engine='openpyxl')
        tickers = df_tickers['Ticker'].str.strip().dropna().tolist()
        logger.info(f"Loaded {len(tickers)} tickers for SMA20 strategy scanning")
    except FileNotFoundError:
        logger.error(f"Error: File not found at {input_file_path}")
        exit()
    except Exception as e:
        logger.error(f"Error reading ticker file: {e}")
        exit()

    results, missing_tickers = process_tickers_parallel(tickers)
    write_results_to_excel(results, required_columns, output_file_path)

    if missing_tickers:
        logger.warning(f"Unable to process {len(set(missing_tickers))} tickers: {', '.join(set(missing_tickers))}")

    logger.info(f"Found {len(results)} tickers that met all SMA20 strategy conditions")
    logger.info(f"Total execution time: {time.time() - start_time:.2f} seconds")


# -----------------------------
# Entry Point
# -----------------------------
if __name__ == "__main__":
    # Print banner
    print(f"\n===================================")
    print(f"Daily SMA20 Scanner")
    print(f"===================================")
    print(f"Using credentials for user: {user_name}")
    print(f"===================================\n")

    main()