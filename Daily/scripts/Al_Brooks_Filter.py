#!/usr/bin/env python
# Standard library imports
import os
import time
import logging
import datetime
import glob
import sys
import argparse
import configparser
import webbrowser
from pathlib import Path

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
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "al_brooks_filter.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Al Brooks Filter Analysis")
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

# Define the scanner files directory path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCANNER_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "scanner_files")
RESULTS_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "results")
HTML_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "Detailed_Analysis")

# Ensure directories exist
for dir_path in [RESULTS_DIR, HTML_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# For data retrieval
FALLBACK_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'BT', 'data')

# Mapping for interval to Kite Connect API parameters
interval_mapping = {
    '5m': '5minute',
    '1h': '60minute',
    '1d': 'day',
    '1w': 'week'
}

# -----------------------------
# Data Cache Implementation
# -----------------------------
class DataCache:
    def __init__(self):
        self.instruments_df = None
        self.instrument_tokens = {}
        self.data_cache = {}

cache = DataCache()

# -----------------------------
# Kite Connect Client Initialization
# -----------------------------
def initialize_kite():
    """Initialize Kite Connect client with error handling"""
    try:
        kite = KiteConnect(api_key=KITE_API_KEY)
        kite.set_access_token(ACCESS_TOKEN)
        return kite
    except Exception as e:
        logger.error(f"Failed to initialize Kite Connect: {e}")
        raise

kite = initialize_kite()

# -----------------------------
# File Operations
# -----------------------------
def get_latest_scanner_file():
    """Find the most recent Custom_Scanner file"""
    try:
        pattern = os.path.join(SCANNER_DIR, "Custom_Scanner_*.xlsx")
        files = glob.glob(pattern)
        if not files:
            logger.error("No Custom_Scanner files found in directory")
            return None
        
        # Sort files by modification time (most recent first)
        latest_file = max(files, key=os.path.getmtime)
        logger.info(f"Found latest scanner file: {os.path.basename(latest_file)}")
        return latest_file
    except Exception as e:
        logger.error(f"Error finding latest scanner file: {e}")
        return None

def read_scanner_file(file_path):
    """Read the scanner file and return the ticker data"""
    try:
        df = pd.read_excel(file_path, engine='openpyxl')
        logger.info(f"Successfully read {len(df)} tickers from {os.path.basename(file_path)}")
        return df
    except Exception as e:
        logger.error(f"Error reading scanner file: {e}")
        return pd.DataFrame()

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
                    backup_file = os.path.join(os.path.dirname(SCRIPT_DIR), "data", "instruments_backup.csv")
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
                backup_file = os.path.join(os.path.dirname(SCRIPT_DIR), "data", "instruments_backup.csv")
                if os.path.exists(backup_file):
                    cache.instruments_df = pd.read_csv(backup_file)
                    logger.info("Loaded instruments data from backup file after API error.")
                else:
                    cache.instruments_df = pd.DataFrame()
            except Exception as backup_e:
                logger.error(f"Error loading backup instruments data: {backup_e}")
                cache.instruments_df = pd.DataFrame()
    return cache.instruments_df

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
    cache_key = f"{ticker}_{interval}_{from_date}_{to_date}"

    # Fast path: check cache first
    if cache_key in cache.data_cache:
        return cache.data_cache[cache_key]

    # Check for token
    token = get_instrument_token(ticker)
    if token is None:
        logger.warning(f"Instrument token for {ticker} not found.")
        # Try fallback to CSV data if available
        if interval == 'day':
            df = fetch_fallback_data(ticker, interval)
            if not df.empty:
                cache.data_cache[cache_key] = df  # Cache the fallback data
                return df
        return pd.DataFrame()

    # Try API with retries
    max_retries = 3
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
    if interval == 'day':
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

# -----------------------------
# Al Brooks Pattern Analysis
# -----------------------------
def identify_brooks_patterns(data):
    """
    Identify Al Brooks H1-H4 and L1-L4 patterns from price data for HIGH PROBABILITY TRADES

    Al Brooks HIGH PROBABILITY Patterns:
    - H1: Bar closes at or near its high with a strong body (strong bull trend bar)
       → HIGHEST PROBABILITY when occurring at support or after pullback in bull trend
    - H2: Strong bull trend bar closing above prior high
       → HIGHEST PROBABILITY when breaking out of bull flag or trading range
    - H3: Strong gap up bar showing bullish momentum
       → HIGHEST PROBABILITY when confirming prior strong bull signal
    - H4: Strong bull breakout bar after consolidation
       → HIGHEST PROBABILITY when volume confirms the breakout

    Al Brooks BEARISH Patterns (for avoiding poor entries):
    - L1: Bar closes at or near its low with a strong body (strong bear trend bar)
    - L2: Strong bear trend bar closing below prior low
    - L3: Strong gap down bar showing bearish momentum
    - L4: Strong bear breakout bar after consolidation
    """
    if data.empty or len(data) < 10:  # Need more data for reliable analysis
        logger.warning("Not enough data points to identify Al Brooks patterns")
        return {
            'H1': False, 'H2': False, 'H3': False, 'H4': False,
            'L1': False, 'L2': False, 'L3': False, 'L4': False,
            'patterns': [],
            'key_levels': {},
            'brooks_recommendation': '',
            'brooks_stoploss': None,
            'entry_price': None
        }

    # Create a copy to avoid SettingWithCopyWarning
    df = data.copy()

    # Calculate basic indicators
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Range'] = df['High'] - df['Low']
    df['BodyPercent'] = (df['Body'] / df['Range']) * 100
    df['TopTail'] = df['High'] - df[['Open', 'Close']].max(axis=1)
    df['BottomTail'] = df[['Open', 'Close']].min(axis=1) - df['Low']
    df['TopTailPercent'] = (df['TopTail'] / df['Range']) * 100
    df['BottomTailPercent'] = (df['BottomTail'] / df['Range']) * 100
    df['PrevClose'] = df['Close'].shift(1)
    df['PrevLow'] = df['Low'].shift(1)
    df['PrevHigh'] = df['High'].shift(1)
    df['PrevOpen'] = df['Open'].shift(1)

    # Calculate 20-period ATR for volatility context
    df['TR'] = df.apply(
        lambda x: max(
            x['High'] - x['Low'],
            abs(x['High'] - x['PrevClose']) if not pd.isna(x['PrevClose']) else 0,
            abs(x['Low'] - x['PrevClose']) if not pd.isna(x['PrevClose']) else 0
        ),
        axis=1
    )
    df['ATR20'] = df['TR'].rolling(window=20).mean()

    # Calculate moving averages for trend context
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['EMA10'] = df['Close'].ewm(span=10, adjust=False).mean()

    # Calculate Additional Brooks Indicators
    # Higher timeframe trending context (using simple approximation)
    df['HigherTF_Trend'] = df['Close'].rolling(window=50).mean() > df['Close'].rolling(window=50).mean().shift(10)

    # Identify pattern for each bar, focusing on the last 5 bars
    recent_bars = min(5, len(df))
    patterns = []
    high_probability_setups = []

    # Add more context for high probability setup detection
    df['Pullback'] = False
    df['AtSupport'] = False
    df['BullFlag'] = False
    df['BreakoutVolume'] = False
    df['TrendStrength'] = 0

    # Calculate additional indicators to improve pattern quality
    # Check for higher volume on possible breakout bars
    df['AvgVolume'] = df['Volume'].rolling(window=10).mean()
    df['VolumeRatio'] = df['Volume'] / df['AvgVolume']

    # Find pullbacks in bull trend (price dropping to EMA10 in uptrend)
    for i in range(5, len(df)):
        # Skip if i is out of range
        if i >= len(df):
            continue

        # Detect pullbacks to moving average in bull trend
        if i >= 5 and 'EMA10' in df.columns:
            if (df['Close'].iloc[i-3:i].min() < df['EMA10'].iloc[i-3:i].max() and
                df['Close'].iloc[i] > df['EMA10'].iloc[i] and
                df['EMA10'].iloc[i] > df['EMA10'].iloc[i-5]):
                df.loc[df.index[i], 'Pullback'] = True

        # Detect test of support level
        if i >= 10:
            recent_lows = df['Low'].iloc[i-10:i-1]
            current_low = df['Low'].iloc[i]
            support_zone = recent_lows.min() * 1.02  # Support zone is within 2% of recent low
            if current_low <= support_zone and df['Close'].iloc[i] > current_low * 1.01:
                df.loc[df.index[i], 'AtSupport'] = True

        # Detect bull flag pattern (consolidation after uptrend)
        if i >= 10 and 'ATR20' in df.columns and 'SMA20' in df.columns:
            if not pd.isna(df['ATR20'].iloc[i]) and not pd.isna(df['SMA20'].iloc[i]) and not pd.isna(df['SMA20'].iloc[i-5]):
                if ((df['High'].iloc[i-5:i].max() - df['Low'].iloc[i-5:i].min()) < df['ATR20'].iloc[i] * 2 and
                    df['High'].iloc[i-10:i-5].max() > df['High'].iloc[i-5:i].max() and
                    df['SMA20'].iloc[i] > df['SMA20'].iloc[i-5]):
                    df.loc[df.index[i], 'BullFlag'] = True

        # Check for volume confirmation on potential breakout
        if 'VolumeRatio' in df.columns and not pd.isna(df['VolumeRatio'].iloc[i]) and df['VolumeRatio'].iloc[i] > 1.5:
            df.loc[df.index[i], 'BreakoutVolume'] = True

        # Calculate trend strength (1-10 scale)
        if i >= 5 and 'SMA20' in df.columns and 'ATR20' in df.columns:
            if not pd.isna(df['SMA20'].iloc[i]) and not pd.isna(df['SMA20'].iloc[i-5]) and not pd.isna(df['ATR20'].iloc[i]):
                trend_strength = min(10, max(0,
                    5 * (df['SMA20'].iloc[i] / df['SMA20'].iloc[i-5] - 1) / (df['ATR20'].iloc[i] / df['Close'].iloc[i]) +
                    (3 if 'EMA10' in df.columns and df['EMA10'].iloc[i] > df['SMA20'].iloc[i] else 0) +
                    (2 if 'HigherTF_Trend' in df.columns and df['HigherTF_Trend'].iloc[i] else 0)
                ))
                df.loc[df.index[i], 'TrendStrength'] = trend_strength

    for i in range(len(df) - recent_bars, len(df)):
        if i < 1 or i >= len(df):  # Skip first bar as we need previous data
            continue

        row = df.iloc[i]
        patterns_found = []
        probability = "NORMAL"  # Default probability

        # Basic conditions
        is_bull = row['Close'] > row['Open']
        is_bear = row['Close'] < row['Open']
        strong_body = row['BodyPercent'] > 60  # Body is more than 60% of range
        small_top_tail = row['TopTailPercent'] < 20  # Small top tail
        small_bottom_tail = row['BottomTailPercent'] < 20  # Small bottom tail

        # Trend context
        above_sma = row['Close'] > row['SMA20'] if not pd.isna(row['SMA20']) else False
        below_sma = row['Close'] < row['SMA20'] if not pd.isna(row['SMA20']) else False

        # Gap calculations
        gap_up = row['Low'] > row['PrevHigh']
        gap_down = row['High'] < row['PrevLow']

        # Volatility context - bar size relative to ATR
        bar_size_vs_atr = row['Range'] / row['ATR20'] if not pd.isna(row['ATR20']) and row['ATR20'] > 0 else 1
        large_range = bar_size_vs_atr > 1.2  # Bar range is larger than average

        # Previous bars for context (check for consolidation)
        prev_idx = max(0, i-5)
        if prev_idx < i:
            prev_bars = df.iloc[prev_idx:i]
            consolidation = False
            if 'ATR20' in row and not pd.isna(row['ATR20']) and row['ATR20'] > 0:
                if (prev_bars['High'].max() - prev_bars['Low'].min()) < (2 * row['ATR20']):
                    consolidation = True
        else:
            consolidation = False

        # H1: Strong bull trend bar (closes near high with strong body)
        if is_bull and strong_body and small_top_tail and above_sma:
            patterns_found.append('H1')

            # Assess probability for H1
            if 'Pullback' in row and row['Pullback'] or 'AtSupport' in row and row['AtSupport']:
                # H1 at support is high probability setup
                probability = "HIGH"
                high_probability_setups.append({'Pattern': 'H1', 'Bar': i, 'Reason': 'At support or after pullback'})
                if 'TrendStrength' in row and row['TrendStrength'] > 6:
                    probability = "VERY HIGH"

        # H2: Strong bull trend bar closing above prior high
        if is_bull and strong_body and row['Close'] > row['PrevHigh'] and above_sma:
            patterns_found.append('H2')

            # Assess probability for H2
            if 'BullFlag' in row and row['BullFlag']:
                # H2 breaking out of bull flag is high probability
                probability = "HIGH"
                high_probability_setups.append({'Pattern': 'H2', 'Bar': i, 'Reason': 'Breakout from bull flag'})
                if 'BreakoutVolume' in row and row['BreakoutVolume']:
                    probability = "VERY HIGH"

        # H3: Strong gap up bar showing bullish momentum
        if gap_up and is_bull and above_sma:
            patterns_found.append('H3')

            # Assess probability for H3
            prior_patterns = [p.get('Patterns', []) for p in patterns[-3:] if patterns]
            if any(['H1' in pats or 'H2' in pats for pats in prior_patterns]):
                # H3 confirming prior bull signal is high probability
                probability = "HIGH"
                high_probability_setups.append({'Pattern': 'H3', 'Bar': i, 'Reason': 'Confirms prior bull signal'})
                if 'TrendStrength' in row and row['TrendStrength'] > 7:
                    probability = "VERY HIGH"

        # H4: Strong bull breakout bar after consolidation
        if is_bull and strong_body and large_range and consolidation and above_sma:
            patterns_found.append('H4')

            # Assess probability for H4
            if 'BreakoutVolume' in row and row['BreakoutVolume']:
                # H4 with volume confirmation is high probability
                probability = "HIGH"
                high_probability_setups.append({'Pattern': 'H4', 'Bar': i, 'Reason': 'Volume confirms breakout'})
                if 'TrendStrength' in row and row['TrendStrength'] > 5:
                    probability = "VERY HIGH"

        # L1: Strong bear trend bar (closes near low with strong body)
        if is_bear and strong_body and small_bottom_tail and below_sma:
            patterns_found.append('L1')

        # L2: Strong bear trend bar closing below prior low
        if is_bear and strong_body and row['Close'] < row['PrevLow'] and below_sma:
            patterns_found.append('L2')

        # L3: Strong gap down bar showing bearish momentum
        if gap_down and is_bear and below_sma:
            patterns_found.append('L3')

        # L4: Strong bear breakout bar after consolidation
        if is_bear and strong_body and large_range and consolidation and below_sma:
            patterns_found.append('L4')

        if patterns_found:
            patterns.append({
                'Date': row['Date'],
                'Patterns': patterns_found,
                'Probability': probability
            })

    # Determine which patterns exist in the last 3 bars and track highest probability
    last_3_bars_patterns = set()
    highest_probability = "NORMAL"
    probability_reasons = []

    for p in patterns[-3:] if patterns else []:
        last_3_bars_patterns.update(p['Patterns'])
        # Track the highest probability
        if p.get('Probability') == "VERY HIGH" and highest_probability != "VERY HIGH":
            highest_probability = "VERY HIGH"
        elif p.get('Probability') == "HIGH" and highest_probability not in ["VERY HIGH"]:
            highest_probability = "HIGH"

    # Identify key Brooks levels
    latest_data = df.iloc[-10:] if len(df) >= 10 else df

    # Find significant price levels (per Brooks methodology)
    key_levels = {}

    # 1. Major swing points from the recent past
    highs = latest_data[latest_data['High'] > latest_data['High'].shift(1)]
    highs = highs[highs['High'] > highs['High'].shift(-1)]

    lows = latest_data[latest_data['Low'] < latest_data['Low'].shift(1)]
    lows = lows[lows['Low'] < lows['Low'].shift(-1)]

    # Keep only significant swing points (use ATR to filter)
    last_atr = df['ATR20'].iloc[-1] if not df['ATR20'].iloc[-1:].isna().all() else df['Range'].iloc[-5:].mean()

    # Resistance levels (potential targets)
    resistance_levels = []
    if not highs.empty:
        for _, high in highs.iterrows():
            if high['High'] > df['Close'].iloc[-1]:
                resistance_levels.append(high['High'])

    # Support levels (potential stop losses)
    support_levels = []
    if not lows.empty:
        for _, low in lows.iterrows():
            if low['Low'] < df['Close'].iloc[-1]:
                support_levels.append(low['Low'])

    # 2. Recent consolidation boundaries
    recent_range_high = latest_data['High'].max()
    recent_range_low = latest_data['Low'].min()

    # 3. Entry price (for immediate entry recommendations)
    current_close = df['Close'].iloc[-1]
    entry_price = current_close

    # Determine Al Brooks stop loss based on pattern type
    h_patterns = any([p in last_3_bars_patterns for p in ['H1', 'H2', 'H3', 'H4']])
    brooks_stoploss = None

    if h_patterns:
        # For H1 pattern (strong bull trend bar), Brooks often recommends stop below the signal bar's low
        if 'H1' in last_3_bars_patterns:
            brooks_stoploss = max(df['Low'].iloc[-2] - (0.25 * last_atr), support_levels[0] if support_levels else (df['Low'].iloc[-1] - last_atr))

        # For H2 (bar closing above prior high), stop below the breakout bar or prior swing low
        elif 'H2' in last_3_bars_patterns:
            brooks_stoploss = max(df['Low'].iloc[-1] - (0.5 * last_atr), support_levels[0] if support_levels else (df['Low'].iloc[-1] - 1.5 * last_atr))

        # For H3 (gap up), stop below the gap or under the last swing low
        elif 'H3' in last_3_bars_patterns:
            brooks_stoploss = max(df['Low'].iloc[-1] - (0.5 * last_atr), min(df['Low'].iloc[-3:]) - (0.3 * last_atr))

        # For H4 (breakout from consolidation), stop below the consolidation range
        elif 'H4' in last_3_bars_patterns:
            brooks_stoploss = recent_range_low - (0.3 * last_atr)

        # Fallback to a standard stop loss approach
        else:
            brooks_stoploss = df['Low'].iloc[-1] - last_atr

    # Adjust stop loss to a nice round number
    if brooks_stoploss is not None:
        # Round to the nearest 0.05 for stocks < 100, 0.5 for stocks < 1000, 1 for stocks >= 1000
        if current_close < 100:
            brooks_stoploss = round(brooks_stoploss * 20) / 20  # nearest 0.05
        elif current_close < 1000:
            brooks_stoploss = round(brooks_stoploss * 2) / 2    # nearest 0.5
        else:
            brooks_stoploss = round(brooks_stoploss)            # nearest 1

    # Create Brooks recommendation based on patterns
    brooks_recommendation = ""
    if h_patterns:
        if 'H1' in last_3_bars_patterns:
            brooks_recommendation = "Bull Trend Bar - Enter on minor pullback with stop below bar low"
        elif 'H2' in last_3_bars_patterns:
            brooks_recommendation = "Breakout - Enter at market or on limit order with stop below bar low"
        elif 'H3' in last_3_bars_patterns:
            brooks_recommendation = "Gap Up - Enter at market with wider stop below the gap"
        elif 'H4' in last_3_bars_patterns:
            brooks_recommendation = "Breakout from Consolidation - Enter at market with stop below consolidation low"
        else:
            brooks_recommendation = "Bullish pattern - Enter with stop under recent swing low"
    else:
        brooks_recommendation = "No clear Al Brooks pattern - avoid entry"

    # Organize key levels in order of importance
    key_levels['entry'] = entry_price
    key_levels['stoploss'] = brooks_stoploss if brooks_stoploss is not None else None
    key_levels['support'] = sorted(support_levels)[:3] if support_levels else []  # Top 3 support levels
    key_levels['resistance'] = sorted(resistance_levels)[:3] if resistance_levels else []  # Top 3 resistance levels
    key_levels['recent_range_high'] = recent_range_high
    key_levels['recent_range_low'] = recent_range_low

    # Create a list of reasons for high probability setup
    high_probability_reasons = []
    for setup in high_probability_setups:
        if setup['Pattern'] in last_3_bars_patterns:
            high_probability_reasons.append(f"{setup['Pattern']}: {setup['Reason']}")

    # Enhance the recommendation based on probability
    if highest_probability == "VERY HIGH":
        brooks_recommendation = f"HIGH PROBABILITY SETUP - {brooks_recommendation}"
    elif highest_probability == "HIGH":
        brooks_recommendation = f"STRONG SETUP - {brooks_recommendation}"

    # Add trading plan with specific entry, stop and target levels
    if entry_price is not None and brooks_stoploss is not None:
        risk = entry_price - brooks_stoploss
        if key_levels and 'resistance' in key_levels and key_levels['resistance']:
            primary_target = key_levels['resistance'][0]
            reward = primary_target - entry_price
            risk_reward = reward / risk if risk > 0 else 0
            trading_plan = f"ENTER: {entry_price:.2f} | STOP: {brooks_stoploss:.2f} | TARGET: {primary_target:.2f} | R:R = {risk_reward:.2f}"
        else:
            # No resistance found, use 2:1 reward-to-risk ratio
            primary_target = entry_price + (2 * risk)
            trading_plan = f"ENTER: {entry_price:.2f} | STOP: {brooks_stoploss:.2f} | TARGET: {primary_target:.2f} | R:R = 2.0"
    else:
        trading_plan = "Insufficient data for complete trading plan"

    result = {
        'H1': 'H1' in last_3_bars_patterns,
        'H2': 'H2' in last_3_bars_patterns,
        'H3': 'H3' in last_3_bars_patterns,
        'H4': 'H4' in last_3_bars_patterns,
        'L1': 'L1' in last_3_bars_patterns,
        'L2': 'L2' in last_3_bars_patterns,
        'L3': 'L3' in last_3_bars_patterns,
        'L4': 'L4' in last_3_bars_patterns,
        'patterns': list(last_3_bars_patterns),
        'key_levels': key_levels,
        'brooks_recommendation': brooks_recommendation,
        'brooks_stoploss': brooks_stoploss,
        'entry_price': entry_price,
        'probability': highest_probability,
        'high_probability_reasons': high_probability_reasons,
        'trading_plan': trading_plan
    }

    return result

def filter_tickers_by_brooks_patterns(ticker_df):
    """
    Filter tickers based on Al Brooks H1-H4 and L1-L4 patterns
    to identify HIGH PROBABILITY trading setups with precise entry and exit points
    """
    results = []

    # Calculate date ranges for data fetching
    now = datetime.datetime.now()
    from_date = (now - relativedelta(days=30)).strftime('%Y-%m-%d')
    to_date = now.strftime('%Y-%m-%d')

    for idx, row in ticker_df.iterrows():
        ticker = row['Ticker']
        try:
            # Fetch daily data for pattern analysis
            daily_data = fetch_data_kite(ticker, interval_mapping['1d'], from_date, to_date)

            if daily_data.empty:
                logger.warning(f"No daily data found for {ticker}, skipping pattern analysis")
                continue

            # Identify Brooks patterns
            patterns = identify_brooks_patterns(daily_data)

            # Determine if this ticker should be included based on patterns
            # Include if it has any H pattern (bullish) without any L pattern (bearish)
            h_patterns = any([patterns['H1'], patterns['H2'], patterns['H3'], patterns['H4']])
            l_patterns = any([patterns['L1'], patterns['L2'], patterns['L3'], patterns['L4']])

            if h_patterns and not l_patterns:
                # Add patterns to the row data
                pattern_row = row.copy()
                pattern_row['Patterns'] = ','.join(patterns['patterns'])
                pattern_row['HasHPattern'] = h_patterns
                pattern_row['HasLPattern'] = l_patterns

                # Add probability information
                pattern_row['Probability'] = patterns.get('probability', 'NORMAL')
                if 'high_probability_reasons' in patterns and patterns['high_probability_reasons']:
                    pattern_row['Probability_Reasons'] = '; '.join(patterns['high_probability_reasons'])
                else:
                    pattern_row['Probability_Reasons'] = "Standard pattern detection"

                # Add Brooks-specific levels and recommendations
                pattern_row['Brooks_SL'] = patterns['brooks_stoploss']
                pattern_row['Brooks_Entry'] = patterns['entry_price']
                pattern_row['Brooks_Recommendation'] = patterns['brooks_recommendation']

                # Add trading plan
                if 'trading_plan' in patterns:
                    pattern_row['Trading_Plan'] = patterns['trading_plan']
                else:
                    # Create trading plan based on available data
                    if patterns['brooks_stoploss'] is not None and patterns['entry_price'] is not None:
                        risk = patterns['entry_price'] - patterns['brooks_stoploss']
                        target = patterns['entry_price'] + (2 * risk)  # 2:1 reward-to-risk
                        pattern_row['Trading_Plan'] = f"ENTER: {patterns['entry_price']:.2f}, STOP: {patterns['brooks_stoploss']:.2f}, TARGET: {target:.2f}"
                    else:
                        pattern_row['Trading_Plan'] = "Unable to calculate complete trading plan"

                # Add key support/resistance levels
                if patterns['key_levels'] and 'resistance' in patterns['key_levels'] and patterns['key_levels']['resistance']:
                    pattern_row['Key_Resistance'] = patterns['key_levels']['resistance'][0]
                else:
                    pattern_row['Key_Resistance'] = None

                if patterns['key_levels'] and 'support' in patterns['key_levels'] and patterns['key_levels']['support']:
                    pattern_row['Key_Support'] = patterns['key_levels']['support'][0]
                else:
                    pattern_row['Key_Support'] = None

                # Calculate risk-reward ratio
                if pattern_row['Brooks_SL'] is not None and pattern_row['Key_Resistance'] is not None:
                    risk = pattern_row['Brooks_Entry'] - pattern_row['Brooks_SL']
                    reward = pattern_row['Key_Resistance'] - pattern_row['Brooks_Entry']
                    if risk > 0:
                        pattern_row['RiskRewardRatio'] = round(reward / risk, 2)
                    else:
                        pattern_row['RiskRewardRatio'] = 0
                else:
                    pattern_row['RiskRewardRatio'] = None

                # Add original SL and TP from scanner
                pattern_row['Scanner_SL'] = row['SL'] if 'SL' in row else None
                pattern_row['Scanner_TP'] = row['TP'] if 'TP' in row else None

                results.append(pattern_row)
                logger.info(f"{ticker} matched bullish patterns: {patterns['patterns']} with Brooks SL at {patterns['brooks_stoploss']}")
            else:
                logger.info(f"{ticker} did not match filter criteria. Patterns: {patterns['patterns']}")

        except Exception as e:
            logger.error(f"Error processing {ticker} for Brooks patterns: {e}")

    # Convert results to DataFrame
    if results:
        result_df = pd.DataFrame(results)

        # Sort by risk-reward ratio if available, otherwise by original Slope
        if 'RiskRewardRatio' in result_df.columns and not result_df['RiskRewardRatio'].isna().all():
            result_df = result_df.sort_values(by='RiskRewardRatio', ascending=False)
        elif 'Slope' in result_df.columns:
            result_df = result_df.sort_values(by='Slope', ascending=False)

        return result_df
    else:
        logger.warning("No tickers matched the Brooks pattern criteria")
        return pd.DataFrame()

# -----------------------------
# HTML Report Generation
# -----------------------------
def generate_html_report(filtered_df, output_file, scanner_file):
    """Generate an HTML report with the Al Brooks pattern analysis"""
    today = datetime.datetime.now()
    formatted_date = today.strftime("%d-%m-%Y")
    formatted_time = today.strftime("%H:%M")

    # HTML template with modern styling
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Al Brooks Pattern Analysis - {formatted_date}</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f9f9f9;
            }}
            h1, h2, h3 {{
                color: #2c3e50;
            }}
            h1 {{
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
            }}
            .header-info {{
                display: flex;
                justify-content: space-between;
                color: #7f8c8d;
                margin-bottom: 20px;
            }}
            .high-probability {{
                background-color: #e8f4fd;
                border-left: 5px solid #3498db;
                padding: 15px;
                margin-bottom: 20px;
                border-radius: 5px;
            }}
            .ticker-card {{
                background-color: white;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 15px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .ticker-header {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 10px;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }}
            .ticker-name {{
                font-weight: bold;
                font-size: 1.2em;
                color: #2c3e50;
            }}
            .patterns {{
                background-color: #f1f8e9;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 0.9em;
            }}
            .probability {{
                font-weight: bold;
                padding: 3px 8px;
                border-radius: 4px;
                margin-left: 10px;
            }}
            .high {{
                background-color: #4caf50;
                color: white;
            }}
            .very-high {{
                background-color: #2e7d32;
                color: white;
            }}
            .normal {{
                background-color: #90a4ae;
                color: white;
            }}
            .ticker-details {{
                margin-left: 15px;
            }}
            .detail-label {{
                color: #7f8c8d;
                width: 80px;
                display: inline-block;
            }}
            .trading-plan {{
                background-color: #fff8e1;
                border-radius: 4px;
                padding: 10px;
                margin-top: 10px;
                font-family: monospace;
                font-size: 1.1em;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 12px 15px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            thead tr {{
                background-color: #3498db;
                color: white;
            }}
            tbody tr:nth-of-type(even) {{
                background-color: #f3f3f3;
            }}
            tbody tr:hover {{
                background-color: #e9e9e9;
            }}
            .rr-ratio {{
                font-weight: bold;
                color: #e67e22;
            }}
            .small-label {{
                font-size: 0.85em;
                color: #7f8c8d;
            }}
            .star-icon {{
                color: #f1c40f;
                font-size: 1.2em;
            }}
            .source-info {{
                margin-top: 30px;
                font-size: 0.9em;
                color: #95a5a6;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <h1>🔍 Al Brooks Pattern Analysis</h1>
        <div class="header-info">
            <div>Date: {formatted_date} | Time: {formatted_time}</div>
            <div>Source: {os.path.basename(scanner_file)}</div>
        </div>
    """

    # Add high probability setups section
    high_prob_df = filtered_df[filtered_df['Probability'].isin(['HIGH', 'VERY HIGH'])] if 'Probability' in filtered_df.columns else pd.DataFrame()

    if not high_prob_df.empty:
        html_content += f"""
        <div class="high-probability">
            <h2>⭐ HIGH PROBABILITY SETUPS: {len(high_prob_df)} tickers</h2>
        """

        for idx, row in high_prob_df.iterrows():
            ticker = row['Ticker']
            patterns = row['Patterns']
            probability = row['Probability']
            prob_class = "very-high" if probability == "VERY HIGH" else "high"

            html_content += f"""
            <div class="ticker-card">
                <div class="ticker-header">
                    <div>
                        <span class="ticker-name">{ticker}</span>
                        <span class="patterns">{patterns}</span>
                        <span class="probability {prob_class.lower()}">{probability}</span>
                    </div>
                </div>
                <div class="ticker-details">
            """

            if 'Brooks_Recommendation' in row and not pd.isna(row['Brooks_Recommendation']):
                html_content += f"""
                    <div><span class="detail-label">Strategy:</span> {row['Brooks_Recommendation']}</div>
                """

            if 'Trading_Plan' in row and not pd.isna(row['Trading_Plan']):
                html_content += f"""
                    <div><span class="detail-label">Plan:</span> <span class="trading-plan">{row['Trading_Plan']}</span></div>
                """

            if 'Probability_Reasons' in row and not pd.isna(row['Probability_Reasons']):
                html_content += f"""
                    <div><span class="detail-label">Why:</span> {row['Probability_Reasons']}</div>
                """

            html_content += """
                </div>
            </div>
            """

        html_content += """
        </div>
        """

    # Add other promising setups
    remaining = len(filtered_df) - len(high_prob_df) if not high_prob_df.empty else len(filtered_df)

    if remaining > 0:
        html_content += """
        <h2>Other Promising Setups</h2>
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Patterns</th>
                    <th>Entry</th>
                    <th>Stop Loss</th>
                    <th>Target</th>
                    <th>R:R</th>
                    <th>Recommendation</th>
                </tr>
            </thead>
            <tbody>
        """

        display_df = filtered_df
        if not high_prob_df.empty and len(high_prob_df) < len(filtered_df):
            display_df = filtered_df[~filtered_df.index.isin(high_prob_df.index)]

        for idx, row in display_df.head(10).iterrows():
            entry = row['Brooks_Entry'] if 'Brooks_Entry' in row and not pd.isna(row['Brooks_Entry']) else "-"
            stop = row['Brooks_SL'] if 'Brooks_SL' in row and not pd.isna(row['Brooks_SL']) else "-"
            target = row['Key_Resistance'] if 'Key_Resistance' in row and not pd.isna(row['Key_Resistance']) else (
                     entry + 2 * (entry - stop) if entry != "-" and stop != "-" else "-")
            rr = row['RiskRewardRatio'] if 'RiskRewardRatio' in row and not pd.isna(row['RiskRewardRatio']) else "-"
            recommendation = row['Brooks_Recommendation'] if 'Brooks_Recommendation' in row and not pd.isna(row['Brooks_Recommendation']) else "-"

            html_content += f"""
            <tr>
                <td>{row['Ticker']}</td>
                <td>{row['Patterns']}</td>
                <td>{entry if isinstance(entry, str) else f"{entry:.2f}"}</td>
                <td>{stop if isinstance(stop, str) else f"{stop:.2f}"}</td>
                <td>{target if isinstance(target, str) else f"{target:.2f}"}</td>
                <td class="rr-ratio">{rr if isinstance(rr, str) else f"{rr:.2f}"}</td>
                <td><span class="small-label">{recommendation[:50] + '...' if isinstance(recommendation, str) and len(recommendation) > 50 else recommendation}</span></td>
            </tr>
            """

        html_content += """
            </tbody>
        </table>
        """

    # Complete HTML
    html_content += f"""
        <div class="source-info">
            <p>Generated on {formatted_date} at {formatted_time} | Al Brooks Pattern Filter</p>
        </div>
    </body>
    </html>
    """

    # Write HTML file
    with open(output_file, 'w') as f:
        f.write(html_content)

    return output_file

# -----------------------------
# Main Function
# -----------------------------
def main():
    """Main function to filter tickers based on Al Brooks patterns"""
    logger.info("Starting Al Brooks pattern filter")

    try:
        # Get the latest scanner file
        latest_file = get_latest_scanner_file()
        if not latest_file:
            logger.error("No scanner file found, exiting")
            return 1

        # Read the scanner file
        ticker_df = read_scanner_file(latest_file)
        if ticker_df.empty:
            logger.error("Scanner file is empty or could not be read")
            return 1

        logger.info(f"Starting analysis for {len(ticker_df)} tickers")

        # Filter tickers based on Brooks patterns
        filtered_df = filter_tickers_by_brooks_patterns(ticker_df)

        # Create output files with timestamp
        today = datetime.datetime.now()
        formatted_date = today.strftime("%d_%m_%Y")
        formatted_time = today.strftime("%H_%M")
        excel_file = os.path.join(RESULTS_DIR, f"Brooks_Filter_{formatted_date}_{formatted_time}.xlsx")
        html_file = os.path.join(HTML_DIR, f"Detailed_Analysis_{formatted_date}_{formatted_time.replace('_', '-')}.html")

        if not filtered_df.empty:
            # Round numeric columns for better readability
            numeric_cols = ['Brooks_SL', 'Brooks_Entry', 'Key_Resistance', 'Key_Support', 'RiskRewardRatio']
            for col in numeric_cols:
                if col in filtered_df.columns:
                    filtered_df[col] = filtered_df[col].astype(float).round(2)

            # Reorder columns for better readability
            cols_order = [
                'Ticker', 'Patterns', 'Probability', 'Brooks_Recommendation',
                'Brooks_Entry', 'Brooks_SL', 'Key_Resistance', 'Key_Support', 'RiskRewardRatio',
                'Trading_Plan', 'Probability_Reasons', 'Scanner_SL', 'Scanner_TP', 'PosSize', 'Slope'
            ]
            # Only include columns that exist
            cols_order = [col for col in cols_order if col in filtered_df.columns]
            # Add any remaining columns
            for col in filtered_df.columns:
                if col not in cols_order:
                    cols_order.append(col)

            filtered_df = filtered_df[cols_order]

            # Write to Excel
            filtered_df.to_excel(excel_file, index=False)
            logger.info(f"Successfully wrote {len(filtered_df)} filtered tickers to {excel_file}")

            # Generate HTML report
            html_output = generate_html_report(filtered_df, html_file, latest_file)
            logger.info(f"Generated HTML report at {html_output}")

            # Open the HTML report in the default browser
            try:
                webbrowser.open('file://' + os.path.abspath(html_output))
                logger.info(f"Opened HTML report in browser")
            except Exception as e:
                logger.warning(f"Could not open browser automatically: {e}")

            # Print summary to console
            print("\n===== Al Brooks Pattern Filter Results =====")
            print(f"Found {len(filtered_df)} tickers with bullish Al Brooks patterns")

            # Identify high probability setups
            high_prob_df = filtered_df[filtered_df['Probability'].isin(['HIGH', 'VERY HIGH'])] if 'Probability' in filtered_df.columns else pd.DataFrame()
            if not high_prob_df.empty:
                print(f"\n🌟 HIGH PROBABILITY SETUPS: {len(high_prob_df)} tickers")
                for idx, row in high_prob_df.head(3).iterrows():
                    print(f"\n{row['Ticker']} - {row['Patterns']} ({row['Probability']})")
                    if 'Brooks_Recommendation' in row:
                        print(f"  Strategy: {row['Brooks_Recommendation']}")
                    if 'Trading_Plan' in row:
                        print(f"  Plan: {row['Trading_Plan']}")
                    if 'Probability_Reasons' in row:
                        print(f"  Why: {row['Probability_Reasons']}")

            # Print regular setups if any remain
            remaining = len(filtered_df) - len(high_prob_df) if not high_prob_df.empty else len(filtered_df)
            if remaining > 0:
                print(f"\nOther promising setups with good risk/reward:")

                # Display other tickers based on risk/reward ratio
                display_df = filtered_df
                if not high_prob_df.empty and len(high_prob_df) < len(filtered_df):
                    display_df = filtered_df[~filtered_df.index.isin(high_prob_df.index)]

                top_5 = display_df.head(5)
                if not top_5.empty:
                    for idx, row in top_5.iterrows():
                        ticker_info = [f"{row['Ticker']}: {row['Patterns']}"]
                        if 'Trading_Plan' in row:
                            ticker_info.append(f"{row['Trading_Plan']}")
                        elif 'Brooks_Entry' in row and 'Brooks_SL' in row and 'Key_Resistance' in row:
                            ticker_info.append(f"Entry: {row['Brooks_Entry']:.2f}, SL: {row['Brooks_SL']:.2f}, Target: {row['Key_Resistance']:.2f}")
                        if 'RiskRewardRatio' in row and not pd.isna(row['RiskRewardRatio']):
                            ticker_info.append(f"R/R: {row['RiskRewardRatio']:.2f}")
                        print(" | ".join(ticker_info))

            print(f"\nDetailed results saved to: {excel_file}")
            print(f"HTML report opened in browser: {html_file}")
        else:
            # Create empty output with columns
            empty_cols = ['Ticker', 'Patterns', 'Probability', 'Brooks_Recommendation', 'Brooks_Entry', 'Brooks_SL',
                          'Key_Resistance', 'Key_Support', 'RiskRewardRatio', 'Trading_Plan', 'Scanner_SL', 'Scanner_TP',
                          'PosSize', 'Slope']
            pd.DataFrame(columns=empty_cols).to_excel(excel_file, index=False)

            # Generate empty HTML report
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Al Brooks Pattern Analysis - {formatted_date}</title>
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 1200px;
                        margin: 0 auto;
                        padding: 20px;
                        background-color: #f9f9f9;
                        text-align: center;
                    }}
                    h1 {{
                        color: #2c3e50;
                        border-bottom: 2px solid #3498db;
                        padding-bottom: 10px;
                    }}
                    .no-results {{
                        margin-top: 50px;
                        padding: 30px;
                        background-color: #f8f9fa;
                        border-radius: 10px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
                    }}
                </style>
            </head>
            <body>
                <h1>🔍 Al Brooks Pattern Analysis</h1>
                <div class="no-results">
                    <h2>No Pattern Matches Found</h2>
                    <p>No tickers matched the Al Brooks pattern criteria in today's scan.</p>
                    <p>Try again with a different scanner file or adjust the pattern criteria.</p>
                </div>
                <div style="margin-top: 50px; color: #999;">
                    <p>Generated on {formatted_date} at {formatted_time.replace('_', ':')} | Al Brooks Pattern Filter</p>
                </div>
            </body>
            </html>
            """
            with open(html_file, 'w') as f:
                f.write(html_content)

            try:
                webbrowser.open('file://' + os.path.abspath(html_file))
            except Exception as e:
                logger.warning(f"Could not open browser automatically: {e}")

            logger.info(f"No tickers matched the pattern criteria. Empty output files created at {excel_file} and {html_file}")
            print("\nNo tickers matched the Al Brooks pattern criteria.")
            print(f"Empty results saved to: {excel_file} and {html_file}")

        return 0

    except Exception as e:
        logger.error(f"Error in main function: {e}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    # Print banner
    print("\n===================================")
    print("🔍 Al Brooks HIGH PROBABILITY Pattern Filter")
    print("===================================")
    print("Finding stocks with H1-H4 patterns (strong bull patterns)")
    print("Prioritizing setups with highest probability of success")
    print("Providing precise entry, stop-loss and target levels")
    print("Generating interactive HTML report in browser")
    print("===================================")
    print(f"Using credentials for user: {user_name}")
    print("===================================\n")

    sys.exit(main())