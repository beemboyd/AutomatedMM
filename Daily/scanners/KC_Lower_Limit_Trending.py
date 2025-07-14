#!/usr/bin/env python
# KC_Lower_Limit_Trending.py - Filter stocks based on Keltner Channel lower limit breakdown with trend following:
# 1. Stock must be trading below Keltner Channel lower band
# 2. Strong downtrending behavior (avoiding congestion/ranging stocks)
# 3. Volume confirmation on breakdown
# 4. Momentum confirmation (negative)
# 5. Daily timeframe focus
# 6. Add Sector information to output

# Standard library imports
import os
import time
import logging
import datetime
import glob
import sys
import argparse
import configparser
from pathlib import Path

# Third-party imports
import numpy as np
import pandas as pd
import pytz
from dateutil.relativedelta import relativedelta
from kiteconnect import KiteConnect
import webbrowser
# PDF generation imports - commented out if reportlab not installed
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("reportlab not installed - PDF generation will be skipped")

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "kc_lower_limit_trending.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="KC Lower Limit Trending Analysis with Sector Information")
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

# Define paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data")
RESULTS_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "results-s")
HTML_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "Detailed_Analysis")
PDF_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "results-s", "PDF")

# Ensure directories exist
for dir_path in [RESULTS_DIR, HTML_DIR, PDF_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# For data retrieval fallback
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
        self.sector_data = None

cache = DataCache()

# -----------------------------
# Sector Data Functions
# -----------------------------
def load_sector_data():
    """Load sector data from Ticker_with_Sector.xlsx"""
    if cache.sector_data is None:
        sector_file = os.path.join(DATA_DIR, "Ticker_with_Sector.xlsx")
        try:
            if os.path.exists(sector_file):
                cache.sector_data = pd.read_excel(sector_file)
                logger.info(f"Loaded sector data from {sector_file}")
            else:
                logger.warning(f"Sector file not found: {sector_file}")
                cache.sector_data = pd.DataFrame()
        except Exception as e:
            logger.error(f"Error loading sector data: {e}")
            cache.sector_data = pd.DataFrame()
    return cache.sector_data

def get_sector_for_ticker(ticker):
    """Get sector information for a specific ticker"""
    sector_df = load_sector_data()
    if sector_df.empty:
        return "Unknown"
    
    # Look up ticker in sector data
    ticker_upper = ticker.upper()
    matching_rows = sector_df[sector_df['Ticker'].str.upper() == ticker_upper]
    
    if not matching_rows.empty and 'Sector' in matching_rows.columns:
        sector = matching_rows.iloc[0]['Sector']
        return sector if pd.notna(sector) else "Unknown"
    
    return "Unknown"

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
# Calculate Indicators for Keltner Channel Analysis (Inverted for Shorting)
# -----------------------------
def calculate_indicators(daily_data):
    """Calculate indicators for Keltner Channel trend detection (inverted for shorting)"""
    if daily_data.empty or len(daily_data) < 50:
        logger.warning(f"Insufficient data points for {daily_data['Ticker'].iloc[0] if not daily_data.empty else 'unknown ticker'}")
        return None
        
    # Create a copy to avoid SettingWithCopyWarning
    df = daily_data.copy()
    
    # Calculate EMAs for Keltner Channel
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # Calculate ATR for Keltner Channel bands
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift(1)).abs()
    low_close = (df['Low'] - df['Close'].shift(1)).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    df['TR'] = ranges.max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()
    
    # Calculate Keltner Channel bands (using 2x ATR as default)
    kc_multiplier = 2.0
    df['KC_Upper'] = df['EMA20'] + (kc_multiplier * df['ATR'])
    df['KC_Lower'] = df['EMA20'] - (kc_multiplier * df['ATR'])
    df['KC_Middle'] = df['EMA20']
    
    # Calculate position relative to Keltner Channel (inverted for shorting)
    df['Below_KC_Lower'] = df['Close'] < df['KC_Lower']
    df['KC_Distance'] = ((df['KC_Lower'] - df['Close']) / df['KC_Lower']) * 100  # % below lower band
    
    # Calculate trend strength indicators
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    
    # ADX for trend strength
    df['Plus_DM'] = df['High'].diff()
    df['Minus_DM'] = -df['Low'].diff()
    df['Plus_DM'] = df.apply(lambda row: row['Plus_DM'] if row['Plus_DM'] > 0 and row['Plus_DM'] > row['Minus_DM'] else 0, axis=1)
    df['Minus_DM'] = df.apply(lambda row: row['Minus_DM'] if row['Minus_DM'] > 0 and row['Minus_DM'] > row['Plus_DM'] else 0, axis=1)
    
    df['Plus_DI14'] = 100 * (df['Plus_DM'].rolling(window=14).mean() / df['ATR'])
    df['Minus_DI14'] = 100 * (df['Minus_DM'].rolling(window=14).mean() / df['ATR'])
    df['DX'] = 100 * (abs(df['Plus_DI14'] - df['Minus_DI14']) / (df['Plus_DI14'] + df['Minus_DI14']))
    df['ADX'] = df['DX'].rolling(window=14).mean()
    
    # Calculate congestion/ranging detection
    # Method 1: Price range over last N days
    lookback_days = 20
    df['High_20D'] = df['High'].rolling(window=lookback_days).max()
    df['Low_20D'] = df['Low'].rolling(window=lookback_days).min()
    df['Range_20D'] = df['High_20D'] - df['Low_20D']
    df['Range_Percent'] = (df['Range_20D'] / df['Close']) * 100
    
    # Method 2: Count days within narrow band
    narrow_band_pct = 5.0  # 5% band
    df['In_Narrow_Band'] = (df['Range_Percent'] < narrow_band_pct).astype(int)
    df['Congestion_Days'] = df['In_Narrow_Band'].rolling(window=lookback_days).sum()
    
    # Method 3: Keltner Channel squeeze (bands getting narrower)
    df['KC_Width'] = df['KC_Upper'] - df['KC_Lower']
    df['KC_Width_MA'] = df['KC_Width'].rolling(window=20).mean()
    df['KC_Squeeze'] = df['KC_Width'] < df['KC_Width_MA']
    
    # Volume indicators
    df['AvgVolume20'] = df['Volume'].rolling(window=20).mean()
    df['VolumeRatio'] = df['Volume'] / df['AvgVolume20']
    
    # Momentum indicators (inverted for shorting)
    df['ROC5'] = ((df['Close'] - df['Close'].shift(5)) / df['Close'].shift(5)) * 100
    df['ROC10'] = ((df['Close'] - df['Close'].shift(10)) / df['Close'].shift(10)) * 100
    df['ROC20'] = ((df['Close'] - df['Close'].shift(20)) / df['Close'].shift(20)) * 100
    
    # Trend consistency (how many of last N days were below KC lower)
    df['Days_Below_KC'] = df['Below_KC_Lower'].rolling(window=10).sum()
    
    # Calculate if this is a fresh breakdown (just crossed below KC lower)
    # Handle NaN values properly
    df['Was_Above_KC'] = ~df['Below_KC_Lower'].shift(1).fillna(False)
    df['Fresh_Breakdown'] = df['Below_KC_Lower'] & df['Was_Above_KC']
    
    # Days since last breakdown
    df['Breakdown_Signal'] = df['Fresh_Breakdown'].astype(int)
    df['Days_Since_Breakdown'] = 0
    for i in range(1, len(df)):
        if df.iloc[i]['Breakdown_Signal'] == 1:
            df.iloc[i, df.columns.get_loc('Days_Since_Breakdown')] = 0
        else:
            df.iloc[i, df.columns.get_loc('Days_Since_Breakdown')] = df.iloc[i-1]['Days_Since_Breakdown'] + 1
    
    # Calculate trend score (inverted for shorting)
    df['Trend_Score'] = 0
    # Add points for bearish trend alignment
    df.loc[df['Close'] < df['SMA50'], 'Trend_Score'] += 1
    df.loc[df['Close'] < df['SMA200'], 'Trend_Score'] += 1
    df.loc[df['SMA50'] < df['SMA200'], 'Trend_Score'] += 1
    df.loc[df['ADX'] > 25, 'Trend_Score'] += 1
    df.loc[df['ROC20'] < -10, 'Trend_Score'] += 1
    
    # L2 Pattern Detection (Two consecutive bars closing below previous low - inverted H2)
    df['L2_Bar'] = False
    df['L2_Count'] = 0
    df['L2_Volume_Surge'] = False
    df['L2_Strength'] = 0.0  # Measure how strongly price closed below previous low
    
    # Check for L2 pattern (inverted H2)
    for i in range(2, len(df)):
        # L2: Current bar closes below previous bar's low AND previous bar closed below its previous low
        if (df.iloc[i]['Close'] < df.iloc[i-1]['Low'] and 
            df.iloc[i-1]['Close'] < df.iloc[i-2]['Low']):
            df.iloc[i, df.columns.get_loc('L2_Bar')] = True
            
            # Calculate L2 strength (% below previous low)
            l2_strength = ((df.iloc[i-1]['Low'] - df.iloc[i]['Close']) / df.iloc[i-1]['Low']) * 100
            df.iloc[i, df.columns.get_loc('L2_Strength')] = l2_strength
            
            # Check volume surge on L2
            if df.iloc[i]['VolumeRatio'] > 1.5:
                df.iloc[i, df.columns.get_loc('L2_Volume_Surge')] = True
    
    # Count consecutive L2 bars
    l2_count = 0
    for i in range(len(df)):
        if df.iloc[i]['L2_Bar']:
            l2_count += 1
        else:
            l2_count = 0
        df.iloc[i, df.columns.get_loc('L2_Count')] = l2_count
    
    # Track L2 patterns near KC breakdowns
    df['L2_Near_KC_Break'] = False
    df['L2_Days_In_Week'] = 0  # Count L2 patterns in last 5 days
    df['Volume_Surge_Days'] = 0  # Count volume surge days in last 5 days
    df['Building_Momentum'] = False  # Flag for bearish momentum patterns
    
    for i in range(5, len(df)):
        # Check if L2 occurred within 3 bars of KC breakdown
        if df.iloc[i]['L2_Bar']:
            # Look back 3 bars for KC breakdown
            for j in range(max(0, i-3), i+1):
                if j > 0 and df.iloc[j]['Below_KC_Lower'] and not df.iloc[j-1]['Below_KC_Lower']:
                    df.iloc[i, df.columns.get_loc('L2_Near_KC_Break')] = True
                    break
        
        # Count L2 patterns in last 5 days (week)
        l2_week_count = df.iloc[i-4:i+1]['L2_Bar'].sum()
        df.iloc[i, df.columns.get_loc('L2_Days_In_Week')] = l2_week_count
        
        # Count volume surge days in last 5 days
        vol_surge_count = (df.iloc[i-4:i+1]['VolumeRatio'] > 1.5).sum()
        df.iloc[i, df.columns.get_loc('Volume_Surge_Days')] = vol_surge_count
        
        # Identify bearish momentum building pattern
        # Multiple L2s in a week with increasing volume
        if (l2_week_count >= 2 and vol_surge_count >= 1 and 
            df.iloc[i]['ROC5'] < -3 and df.iloc[i]['ADX'] > 20):
            df.iloc[i, df.columns.get_loc('Building_Momentum')] = True
    
    # Pattern strength based on L2 and KC combination
    df['Pattern_Strength'] = 0
    df.loc[df['Below_KC_Lower'] & df['L2_Bar'], 'Pattern_Strength'] = 3  # Strongest
    df.loc[df['Below_KC_Lower'] & ~df['L2_Bar'], 'Pattern_Strength'] = 2  # Medium
    df.loc[~df['Below_KC_Lower'] & df['L2_Bar'], 'Pattern_Strength'] = 1  # Building strength
    
    return df

# -----------------------------
# Keltner Channel Trend Detection (Inverted for Shorting)
# -----------------------------
def detect_kc_lower_trend(data):
    """
    Detect high probability shorting opportunities using:
    1. Keltner Channel position and breakdowns
    2. L2 bar patterns (consecutive closes below previous lows)
    3. Volume confirmation
    4. Trend strength and momentum (bearish)
    5. Low congestion/ranging behavior
    
    Focus on identification and scoring, not immediate entry.
    Returns a dictionary with pattern details if found, None otherwise
    """
    if data is None or data.empty or len(data) < 50:
        return None

    # Get last few bars for analysis
    last_bar = data.iloc[-1]
    last_5_bars = data.tail(5)
    
    # We're looking for high probability shorting setups
    # Include stocks near KC lower or showing L2 strength
    if not (last_bar['Below_KC_Lower'] or 
            last_bar['L2_Bar'] or 
            last_bar['KC_Distance'] > -2.0):  # Within 2% of KC lower
        return None
    
    # Check if this is a fresh breakdown (high priority)
    is_fresh_breakdown = last_bar['Fresh_Breakdown']
    days_since_breakdown = last_bar['Days_Since_Breakdown']
    
    # Check L2 pattern status
    has_l2 = last_bar['L2_Bar']
    l2_count = last_bar['L2_Count']
    l2_with_volume = last_bar['L2_Volume_Surge']
    l2_near_kc = last_bar['L2_Near_KC_Break']
    l2_strength = last_bar['L2_Strength'] if 'L2_Strength' in last_bar else 0
    
    # Recent L2 activity (check last 5 bars)
    recent_l2_count = last_5_bars['L2_Bar'].sum()
    recent_l2_volume_surges = last_5_bars['L2_Volume_Surge'].sum()
    
    # Bearish pattern indicators
    l2_days_in_week = last_bar['L2_Days_In_Week']
    volume_surge_days = last_bar['Volume_Surge_Days']
    building_momentum = last_bar['Building_Momentum']
    
    # Calculate base conditions for high probability shorting setups
    base_conditions = {
        'near_or_below_kc': last_bar['KC_Distance'] > -2.0,  # Within 2% or below KC lower
        'trend_alignment': last_bar['Trend_Score'] >= 3,  # Good bearish trend structure
        'low_congestion': last_bar['Congestion_Days'] < 10,  # Low ranging behavior
        'negative_momentum': last_bar['ROC10'] < -2,  # Negative 10-day momentum
        'volume_activity': last_bar['VolumeRatio'] > 1.0,  # At least average volume
        'adx_trending': last_bar['ADX'] > 18,  # Some trend present
        'no_squeeze': not last_bar['KC_Squeeze'],  # KC bands not in squeeze
        'pattern_developing': last_bar['Pattern_Strength'] >= 1,  # Some pattern strength
    }
    
    # L2 Pattern conditions (high value indicators for shorting)
    l2_conditions = {
        'has_l2_today': has_l2,  # L2 bar today
        'l2_with_volume': l2_with_volume,  # L2 with volume surge
        'l2_near_kc_break': l2_near_kc,  # L2 near KC breakdown
        'multiple_l2_bars': l2_count >= 2,  # Consecutive L2 bars
        'recent_l2_activity': recent_l2_count >= 2,  # Multiple L2s in last 5 bars
    }
    
    # KC Breakdown conditions
    kc_conditions = {
        'below_kc_lower': last_bar['Below_KC_Lower'],
        'fresh_kc_break': is_fresh_breakdown,  # Just broke below KC
        'recent_kc_break': days_since_breakdown <= 3,  # Recent KC breakdown
        'strong_kc_distance': last_bar['KC_Distance'] > 1.5,  # Well below KC
        'days_below_kc': last_bar['Days_Below_KC'] >= 3,  # Sustained below KC
    }
    
    # Advanced conditions for highest probability shorting
    advanced_conditions = {
        'l2_kc_combo': last_bar['Below_KC_Lower'] and has_l2,  # Both patterns together
        'volume_surge': last_bar['VolumeRatio'] > 2.0,  # Major volume expansion
        'strong_momentum': last_bar['ROC5'] < -5,  # Strong negative 5-day momentum
        'l2_volume_combo': recent_l2_count >= 2 and recent_l2_volume_surges >= 1,  # L2s with volume
        'expanding_volatility': last_bar['KC_Width'] > last_bar['KC_Width_MA'],  # Expanding bands
    }
    
    # Bearish pattern conditions (multi-day momentum building)
    bearish_pattern_conditions = {
        'building_momentum_flag': building_momentum,  # Algorithm detected pattern
        'multi_day_l2': l2_days_in_week >= 2,  # Multiple L2s in a week
        'volume_confirmation': volume_surge_days >= 1,  # At least one volume surge
        'l2_strength_good': l2_strength > 0.5 if has_l2 else False,  # Strong L2 close
        'consistent_momentum': last_bar['ROC5'] < -3 and last_bar['ROC10'] < -5,  # Building bearish momentum
        'ready_to_double': l2_days_in_week >= 3 and recent_l2_volume_surges >= 1,  # Time to double short position
    }
    
    # Calculate scores with weighted importance
    base_score = sum(base_conditions.values())
    l2_score = sum(l2_conditions.values())
    kc_score = sum(kc_conditions.values())
    advanced_score = sum(advanced_conditions.values())
    bearish_pattern_score = sum(bearish_pattern_conditions.values())
    
    # Calculate weighted total score
    # Bearish patterns get highest weight as they show multi-day momentum
    weighted_score = (
        base_score * 1.0 +      # Base conditions
        l2_score * 3.0 +        # L2 patterns are 3x weighted
        kc_score * 2.0 +        # KC breakdowns are 2x weighted
        advanced_score * 4.0 +  # Advanced combos are 4x weighted
        bearish_pattern_score * 5.0   # Bearish patterns are 5x weighted (highest)
    )
    
    max_base_score = len(base_conditions)
    max_l2_score = len(l2_conditions)
    max_kc_score = len(kc_conditions)
    max_advanced_score = len(advanced_conditions)
    max_bearish_pattern_score = len(bearish_pattern_conditions)
    max_weighted_score = (max_base_score * 1.0 + max_l2_score * 3.0 + 
                         max_kc_score * 2.0 + max_advanced_score * 4.0 + max_bearish_pattern_score * 5.0)
    
    # Require minimum base score of 4 out of 8
    if base_score >= 4:
        # Calculate congestion penalty (lower is better)
        congestion_penalty = last_bar['Congestion_Days'] / 20.0  # 0 to 1 scale
        trend_strength = 1 - congestion_penalty  # Higher is better
        
        # Calculate high-probability score (0-100)
        # Normalize weighted score to 0-100 scale
        normalized_score = (weighted_score / max_weighted_score) * 100
        
        # Apply pattern-specific bonuses
        pattern_bonus = 0
        if advanced_conditions['l2_kc_combo']:  # L2 + KC combo is highest value
            pattern_bonus += 15
        if l2_conditions['l2_with_volume']:  # L2 with volume surge
            pattern_bonus += 10
        if l2_conditions['multiple_l2_bars']:  # Multiple consecutive L2s
            pattern_bonus += 5
            
        # Final probability score
        probability_score = min(100, normalized_score + pattern_bonus)
        
        # Calculate stop loss (above KC middle or recent swing high)
        atr_multiplier = 2.0
        stop_loss_atr = last_bar['Close'] + (atr_multiplier * last_bar['ATR'])
        stop_loss_kc = last_bar['KC_Middle'] + (0.5 * last_bar['ATR'])
        
        # Use the lower of the two (less aggressive stop)
        stop_loss = min(stop_loss_atr, stop_loss_kc)
        
        # Calculate targets (inverted for shorting)
        risk = stop_loss - last_bar['Close']
        target1 = last_bar['Close'] - (2 * risk)  # 1:2 risk-reward
        target2 = last_bar['Close'] - (3 * risk)  # 1:3 risk-reward
        
        # Determine pattern type based on combinations
        if bearish_pattern_conditions['ready_to_double']:
            pattern_type = 'Bearish_G_Pattern'
            description = 'Multi-day L2 bearish momentum with volume - TIME TO DOUBLE SHORT POSITION!'
        elif bearish_pattern_conditions['building_momentum_flag'] and bearish_pattern_conditions['multi_day_l2']:
            pattern_type = 'Building_Bearish'
            description = 'Building multi-day bearish momentum - WATCH CLOSELY!'
        elif advanced_conditions['l2_kc_combo'] and l2_days_in_week >= 2:
            pattern_type = 'Strong_L2_KC_Combo'
            description = 'L2 + KC with multi-day bearish momentum - HIGH PROBABILITY SHORT'
        elif has_l2 and l2_with_volume and l2_strength > 1.0:
            pattern_type = 'Power_L2_Volume'
            description = 'Strong L2 with volume surge - BEARISH MOMENTUM ACCELERATING'
        elif last_bar['Below_KC_Lower'] and recent_l2_count >= 2:
            pattern_type = 'KC_Multi_L2'
            description = 'Below KC with multiple L2s - SHORT POSITION BUILDING OPPORTUNITY'
        elif has_l2 and l2_days_in_week >= 1:
            pattern_type = 'L2_Momentum_Start'
            description = 'L2 pattern starting - POTENTIAL BEARISH SETUP FORMING'
        elif last_bar['Below_KC_Lower']:
            pattern_type = 'KC_Breakdown_Watch'
            description = 'Below KC lower - MONITOR FOR L2 DEVELOPMENT'
        else:
            pattern_type = 'Early_Short_Setup'
            description = 'Near breakdown zone - EARLY STAGE MONITORING'
        
        return {
            'pattern': pattern_type,
            'description': description,
            'direction': 'SHORT',
            'probability_score': probability_score,
            'base_score': base_score,
            'l2_score': l2_score,
            'kc_score': kc_score,
            'advanced_score': advanced_score,
            'weighted_score': weighted_score,
            'max_base_score': max_base_score,
            'max_l2_score': max_l2_score,
            'max_kc_score': max_kc_score,
            'max_advanced_score': max_advanced_score,
            'trend_strength': trend_strength,
            'congestion_days': int(last_bar['Congestion_Days']),
            'has_l2': has_l2,
            'l2_count': int(l2_count),
            'l2_with_volume': l2_with_volume,
            'l2_strength': l2_strength,
            'recent_l2_count': int(recent_l2_count),
            'l2_days_in_week': int(l2_days_in_week),
            'volume_surge_days': int(volume_surge_days),
            'building_momentum': building_momentum,
            'l2_near_kc': l2_near_kc,
            'is_fresh_breakdown': is_fresh_breakdown,
            'days_since_breakdown': int(days_since_breakdown) if last_bar['Below_KC_Lower'] else -1,
            'base_conditions': base_conditions,
            'l2_conditions': l2_conditions,
            'kc_conditions': kc_conditions,
            'advanced_conditions': advanced_conditions,
            'bearish_pattern_conditions': bearish_pattern_conditions,
            'bearish_pattern_score': bearish_pattern_score,
            'max_bearish_pattern_score': max_bearish_pattern_score,
            'entry_price': last_bar['Close'],
            'stop_loss': stop_loss,
            'target1': target1,
            'target2': target2,
            'kc_lower': last_bar['KC_Lower'],
            'kc_middle': last_bar['KC_Middle'],
            'kc_distance_pct': last_bar['KC_Distance'],
            'adx': last_bar['ADX'],
            'volume_ratio': last_bar['VolumeRatio'],
            'momentum_10d': last_bar['ROC10'],
            'momentum_5d': last_bar['ROC5'],
            'pattern_strength': int(last_bar['Pattern_Strength']),
            'atr': last_bar['ATR']
        }
    
    return None

# -----------------------------
# Process Single Ticker
# -----------------------------
def process_ticker(ticker):
    """Process a single ticker for Keltner Channel lower trend patterns"""
    logger.info(f"Processing {ticker}")
    
    try:
        now = datetime.datetime.now()
        
        # Extended date range for better pattern recognition
        from_date_daily = (now - relativedelta(months=6)).strftime('%Y-%m-%d')
        to_date = now.strftime('%Y-%m-%d')
        
        # Fetch daily data for pattern detection
        daily_data = fetch_data_kite(ticker, interval_mapping['1d'], from_date_daily, to_date)
        if daily_data.empty:
            logger.warning(f"No daily data available for {ticker}, skipping")
            return None
            
        # Calculate indicators
        daily_with_indicators = calculate_indicators(daily_data)
        if daily_with_indicators is None:
            logger.warning(f"Could not calculate indicators for {ticker}, skipping")
            return None
            
        # Detect Keltner Channel lower trend pattern
        kc_pattern = detect_kc_lower_trend(daily_with_indicators)
        
        if kc_pattern is None:
            logger.info(f"{ticker} - No KC lower trend pattern detected")
            return None
        
        # Get the most recent values
        last_bar = daily_with_indicators.iloc[-1]
        
        # Calculate risk and reward (inverted for shorting)
        entry_price = kc_pattern['entry_price']
        stop_loss = kc_pattern['stop_loss']
        risk = stop_loss - entry_price  # Inverted for shorting
        
        # Calculate risk-reward ratio
        if risk > 0:
            risk_reward_ratio = abs(entry_price - kc_pattern['target1']) / risk
        else:
            risk_reward_ratio = 0
        
        # Get sector information
        sector = get_sector_for_ticker(ticker)
        
        # Log the findings
        logger.info(f"{ticker} - {kc_pattern['pattern']} Detected!")
        logger.info(f"{ticker} - Probability Score: {kc_pattern['probability_score']:.1f}/100")
        logger.info(f"{ticker} - Scores: Base={kc_pattern['base_score']}/{kc_pattern['max_base_score']}, "
                   f"L2={kc_pattern['l2_score']}/{kc_pattern['max_l2_score']}, "
                   f"KC={kc_pattern['kc_score']}/{kc_pattern['max_kc_score']}, "
                   f"Advanced={kc_pattern['advanced_score']}/{kc_pattern['max_advanced_score']}, "
                   f"Bearish={kc_pattern['bearish_pattern_score']}/{kc_pattern['max_bearish_pattern_score']}")
        logger.info(f"{ticker} - L2 Status: Has L2={kc_pattern['has_l2']}, L2s in week={kc_pattern['l2_days_in_week']}, "
                   f"Volume surges={kc_pattern['volume_surge_days']}, Building={kc_pattern['building_momentum']}")
        logger.info(f"{ticker} - Entry: {entry_price:.2f}, Stop: {stop_loss:.2f}, Target1: {kc_pattern['target1']:.2f}")
        logger.info(f"{ticker} - Sector: {sector}")
        
        # Prepare result
        result = {
            'Ticker': ticker,
            'Sector': sector,
            'Pattern': kc_pattern['pattern'],
            'Direction': kc_pattern['direction'],
            'Probability_Score': kc_pattern['probability_score'],
            'Has_L2': kc_pattern['has_l2'],
            'L2_Count': kc_pattern['l2_count'],
            'L2_Volume': kc_pattern['l2_with_volume'],
            'Recent_L2s': kc_pattern['recent_l2_count'],
            'Base_Score': f"{kc_pattern['base_score']}/{kc_pattern['max_base_score']}",
            'L2_Score': f"{kc_pattern['l2_score']}/{kc_pattern['max_l2_score']}",
            'KC_Score': f"{kc_pattern['kc_score']}/{kc_pattern['max_kc_score']}",
            'Advanced_Score': f"{kc_pattern['advanced_score']}/{kc_pattern['max_advanced_score']}",
            'Bearish_Score': f"{kc_pattern['bearish_pattern_score']}/{kc_pattern['max_bearish_pattern_score']}",
            'L2_Days_Week': kc_pattern['l2_days_in_week'],
            'Volume_Surge_Days': kc_pattern['volume_surge_days'],
            'Building_Momentum': kc_pattern['building_momentum'],
            'Days_Since_KC_Break': kc_pattern['days_since_breakdown'],
            'Trend_Strength': kc_pattern['trend_strength'],
            'Congestion_Days': kc_pattern['congestion_days'],
            'Entry_Price': entry_price,
            'Stop_Loss': stop_loss,
            'Target1': kc_pattern['target1'],
            'Target2': kc_pattern['target2'],
            'Risk': risk,
            'Risk_Reward_Ratio': risk_reward_ratio,
            'KC_Lower': kc_pattern['kc_lower'],
            'KC_Middle': kc_pattern['kc_middle'],
            'KC_Distance_%': kc_pattern['kc_distance_pct'],
            'ADX': kc_pattern['adx'],
            'Volume_Ratio': kc_pattern['volume_ratio'],
            'Momentum_10D': kc_pattern['momentum_10d'],
            'Momentum_5D': kc_pattern['momentum_5d'],
            'Pattern_Strength': kc_pattern['pattern_strength'],
            'ATR': kc_pattern['atr'],
            'Description': kc_pattern['description']
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing {ticker}: {e}")
        return None

# -----------------------------
# Read Ticker File
# -----------------------------
def read_ticker_file():
    """Read tickers from the Excel file"""
    ticker_file = os.path.join(DATA_DIR, "Ticker.xlsx")
    
    try:
        if not os.path.exists(ticker_file):
            logger.error(f"Ticker file not found: {ticker_file}")
            return []
        
        df = pd.read_excel(ticker_file, sheet_name="Ticker")
        tickers = df['Ticker'].dropna().tolist()
        logger.info(f"Read {len(tickers)} tickers from {ticker_file}")
        return tickers
    except Exception as e:
        logger.error(f"Error reading ticker file: {e}")
        return []

# -----------------------------
# Generate HTML Report
# -----------------------------
def generate_html_report(filtered_df, output_file, scanner_file):
    """Generate an HTML report with the filtered stocks"""
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
        <title>KC Lower Limit Trending Filter - {formatted_date}</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1400px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f9f9f9;
            }}
            h1, h2, h3 {{
                color: #2c3e50;
            }}
            h1 {{
                border-bottom: 2px solid #e74c3c;
                padding-bottom: 10px;
            }}
            .header-info {{
                display: flex;
                justify-content: space-between;
                color: #7f8c8d;
                margin-bottom: 20px;
            }}
            .ticker-card {{
                background-color: white;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 15px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                border-left: 5px solid #e74c3c;
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
            .ticker-direction {{
                font-weight: bold;
                font-size: 1.1em;
                padding: 5px 10px;
                border-radius: 4px;
                color: white;
                background-color: #e74c3c;
            }}
            .sector-badge {{
                background-color: #9b59b6;
                color: white;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 0.85em;
                margin-left: 10px;
            }}
            .ticker-details {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 10px;
            }}
            .detail-item {{
                background-color: #f8f9fa;
                padding: 8px;
                border-radius: 4px;
            }}
            .detail-label {{
                color: #7f8c8d;
                font-size: 0.85em;
            }}
            .detail-value {{
                font-weight: bold;
            }}
            .pattern-info {{
                background-color: #ffe3e3;
                padding: 10px;
                border-radius: 4px;
                margin-top: 10px;
            }}
            .score-badge {{
                background-color: #e74c3c;
                color: white;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 0.8em;
                margin-left: 10px;
            }}
            .potential-score {{
                font-weight: bold;
                font-size: 1.1em;
                padding: 5px 10px;
                border-radius: 4px;
                color: white;
            }}
            .score-high {{
                background-color: #e74c3c;
            }}
            .score-medium {{
                background-color: #f39c12;
            }}
            .score-low {{
                background-color: #95a5a6;
            }}
            .fresh-badge {{
                background-color: #e74c3c;
                color: white;
                padding: 3px 8px;
                border-radius: 12px;
                font-size: 0.85em;
                animation: pulse 1.5s infinite;
            }}
            @keyframes pulse {{
                0% {{ opacity: 1; }}
                50% {{ opacity: 0.7; }}
                100% {{ opacity: 1; }}
            }}
            .trend-strength {{
                display: inline-block;
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 0.9em;
                font-weight: bold;
            }}
            .trend-strong {{
                background-color: #e74c3c;
                color: white;
            }}
            .trend-medium {{
                background-color: #f39c12;
                color: white;
            }}
            .trend-weak {{
                background-color: #2ecc71;
                color: white;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 10px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            thead tr {{
                background-color: #e74c3c;
                color: white;
            }}
            tbody tr:nth-of-type(even) {{
                background-color: #f3f3f3;
            }}
            tbody tr:hover {{
                background-color: #e9e9e9;
            }}
            .source-info {{
                margin-top: 30px;
                font-size: 0.9em;
                color: #95a5a6;
                text-align: center;
            }}
            .sector-summary {{
                margin: 20px 0;
                padding: 15px;
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .kc-info {{
                background-color: #fff3cd;
                padding: 10px;
                border-radius: 4px;
                margin-bottom: 20px;
                border-left: 4px solid #ffc107;
            }}
        </style>
    </head>
    <body>
        <h1>Keltner Channel Lower Limit Trending Filter (Shorting)</h1>
        <div class="header-info">
            <div>Date: {formatted_date} | Time: {formatted_time}</div>
            <div>Filtered from: Ticker.xlsx | Daily Timeframe | Trend Following Short Strategy</div>
        </div>

        <div class="kc-info">
            <h3>Strategy Overview</h3>
            <p>This scanner identifies high-probability shorting opportunities using:</p>
            <ul>
                <li><strong>L2 Pattern:</strong> Two consecutive bars closing below previous lows (bearish momentum confirmation)</li>
                <li><strong>KC Breakdowns:</strong> Price breaking below Keltner Channel lower band</li>
                <li><strong>Volume Surge:</strong> Increased volume on L2 bars shows institutional selling</li>
                <li><strong>Pattern Combos:</strong> L2 + KC + Volume = Highest probability short setups</li>
                <li><strong>Early Detection:</strong> Identifies stocks building weakness before major declines</li>
            </ul>
        </div>

        <h2>High Probability Short Setups ({len(filtered_df)} matches)</h2>
    """

    # Add sector summary if we have matches
    if len(filtered_df) > 0:
        sector_counts = filtered_df['Sector'].value_counts()
        html_content += """
        <div class="sector-summary">
            <h3>Sector Distribution</h3>
            <ul>
        """
        for sector, count in sector_counts.items():
            html_content += f"<li><strong>{sector}:</strong> {count} stocks</li>"
        html_content += """
            </ul>
        </div>
        """

    # Group results by pattern type for better organization
    l2_kc_combos = filtered_df[filtered_df['Pattern'] == 'L2_KC_Combo']
    l2_patterns = filtered_df[filtered_df['Has_L2'] == True]
    high_probability = filtered_df[filtered_df['Probability_Score'] >= 70]
    
    # Add section for highest probability setups
    if len(l2_kc_combos) > 0:
        html_content += """
        <h3 style="color: #e74c3c;">🔥 L2 + KC Combos (HIGHEST PROBABILITY SHORTS)</h3>
        <p>These stocks show both L2 pattern AND KC breakdown - ideal for short position building!</p>
        """
    elif len(l2_patterns) > 0:
        html_content += """
        <h3 style="color: #f39c12;">📉 L2 Patterns Detected</h3>
        <p>These stocks show L2 bearish momentum patterns - watch for continuation!</p>
        """
    
    # Add table view
    html_content += """
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Sector</th>
                    <th>Probability</th>
                    <th>Pattern</th>
                    <th>L2</th>
                    <th>Entry Price</th>
                    <th>Stop Loss</th>
                    <th>Target 1</th>
                    <th>Risk:Reward</th>
                    <th>Volume</th>
                </tr>
            </thead>
            <tbody>
    """

    # Add rows for each ticker
    for idx, row in filtered_df.iterrows():
        # Determine score class
        score_class = "score-high" if row['Probability_Score'] >= 70 else "score-medium" if row['Probability_Score'] >= 50 else "score-low"
        
        # L2 indicator
        l2_indicator = ''
        if row['Has_L2'] and row['L2_Volume']:
            l2_indicator = '<span class="fresh-badge">L2+Vol</span>'
        elif row['Has_L2']:
            l2_indicator = '<span style="color: #e74c3c; font-weight: bold;">L2</span>'
        elif row['Recent_L2s'] > 0:
            l2_indicator = f'<span style="color: #f39c12;">{int(row["Recent_L2s"])} recent</span>'
        
        html_content += f"""
            <tr>
                <td>{row['Ticker']}</td>
                <td><span class="sector-badge">{row['Sector']}</span></td>
                <td><span class="potential-score {score_class}">{row['Probability_Score']:.0f}</span></td>
                <td>{row['Pattern']}</td>
                <td>{l2_indicator}</td>
                <td>₹{row['Entry_Price']:.2f}</td>
                <td>₹{row['Stop_Loss']:.2f}</td>
                <td>₹{row['Target1']:.2f}</td>
                <td>{row['Risk_Reward_Ratio']:.2f}</td>
                <td>{row['Volume_Ratio']:.1f}x</td>
            </tr>
        """

    html_content += """
            </tbody>
        </table>
    """

    # Add detailed cards for each ticker
    html_content += "<h2>Detailed Analysis</h2>"
    
    for idx, row in filtered_df.iterrows():
        trend_class = "trend-strong" if row['Trend_Strength'] > 0.7 else "trend-medium" if row['Trend_Strength'] > 0.5 else "trend-weak"
        score_class = "score-high" if row['Probability_Score'] >= 70 else "score-medium" if row['Probability_Score'] >= 50 else "score-low"
        
        # L2 status
        l2_status = ""
        if row['Has_L2'] and row['L2_Volume']:
            l2_status = '<span class="fresh-badge">L2 WITH VOLUME!</span>'
        elif row['Has_L2']:
            l2_status = '<span style="background: #e74c3c; color: white; padding: 3px 8px; border-radius: 12px;">L2 PATTERN</span>'
        
        html_content += f"""
        <div class="ticker-card">
            <div class="ticker-header">
                <div class="ticker-name">
                    {row['Ticker']}
                    <span class="sector-badge">{row['Sector']}</span>
                    {l2_status}
                </div>
                <div>
                    <span class="potential-score {score_class}">Score: {row['Probability_Score']:.0f}/100</span>
                    <span class="ticker-direction">{row['Pattern']}</span>
                </div>
            </div>
            
            <div class="ticker-details">
                <div class="detail-item">
                    <div class="detail-label">Entry Price</div>
                    <div class="detail-value">₹{row['Entry_Price']:.2f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Stop Loss</div>
                    <div class="detail-value">₹{row['Stop_Loss']:.2f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Target 1 (1:2)</div>
                    <div class="detail-value">₹{row['Target1']:.2f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Target 2 (1:3)</div>
                    <div class="detail-value">₹{row['Target2']:.2f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Risk Amount</div>
                    <div class="detail-value">₹{row['Risk']:.2f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Risk:Reward</div>
                    <div class="detail-value">{row['Risk_Reward_Ratio']:.2f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">KC Lower Band</div>
                    <div class="detail-value">₹{row['KC_Lower']:.2f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">KC Distance</div>
                    <div class="detail-value">{row['KC_Distance_%']:.1f}%</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">ADX (Trend Strength)</div>
                    <div class="detail-value">{row['ADX']:.1f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Congestion Days</div>
                    <div class="detail-value">{row['Congestion_Days']} / 20</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Volume Expansion</div>
                    <div class="detail-value">{row['Volume_Ratio']:.2f}x Average</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">10-Day Momentum</div>
                    <div class="detail-value">{row['Momentum_10D']:.2f}%</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">5-Day Momentum</div>
                    <div class="detail-value">{row['Momentum_5D']:.2f}%</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">L2 Count</div>
                    <div class="detail-value">{row['L2_Count']}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Recent L2s (5 bars)</div>
                    <div class="detail-value">{row['Recent_L2s']}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Base Score</div>
                    <div class="detail-value">{row['Base_Score']}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">L2 Score</div>
                    <div class="detail-value">{row['L2_Score']}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">KC Score</div>
                    <div class="detail-value">{row['KC_Score']}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Advanced Score</div>
                    <div class="detail-value">{row['Advanced_Score']}</div>
                </div>
            </div>
            
            <div class="pattern-info">
                <strong>Pattern:</strong> {row['Description']}
                <br>
                <strong>Key Insight:</strong> {
                    "L2 + KC combo detected - HIGHEST probability short setup!" if row['Pattern'] == 'L2_KC_Combo' else
                    "L2 with volume surge - Strong bearish momentum building!" if row['Pattern'] == 'L2_Volume_Surge' else
                    "Multiple L2 patterns below KC - Short position building opportunity!" if row['Pattern'] == 'KC_Multi_L2' else
                    "L2 pattern forming - Watch for bearish continuation!" if row['Has_L2'] else
                    "Near KC lower band - Monitor for L2 development"
                }
                <br>
                <strong>Position Strategy:</strong> {
                    "Initial short on L2 confirmation, add on volume surge" if row['Has_L2'] else
                    "Wait for L2 pattern to develop before entry"
                }
                <br>
                <strong>Risk Level:</strong> {"Low" if row['Congestion_Days'] < 5 else "Moderate" if row['Congestion_Days'] < 10 else "High"} congestion risk ({row['Congestion_Days']} days).
            </div>
        </div>
        """

    # Complete HTML
    html_content += f"""
        <div class="source-info">
            <p>Generated on {formatted_date} at {formatted_time} | KC Lower Limit Trending Filter</p>
            <p><strong>Note:</strong> These setups identify stocks breaking down below Keltner Channel lower band with strong bearish trending characteristics.</p>
            <p><strong>Risk Management:</strong> Use proper position sizing for shorting. Stocks with lower congestion days and higher trend strength typically perform better.</p>
        </div>
    </body>
    </html>
    """

    # Write HTML file
    with open(output_file, 'w') as f:
        f.write(html_content)

    return output_file

# -----------------------------
# Generate PDF Report
# -----------------------------
def generate_pdf_report(filtered_df, output_file):
    """Generate a PDF report with the filtered stocks"""
    if not REPORTLAB_AVAILABLE:
        logger.warning("PDF generation skipped - reportlab not installed")
        return None
        
    today = datetime.datetime.now()
    formatted_date = today.strftime("%d-%m-%Y")
    formatted_time = today.strftime("%H:%M")

    try:
        # Create PDF
        doc = SimpleDocTemplate(output_file, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        story = []
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            spaceBefore=12
        )
        
        normal_style = styles['Normal']
        normal_style.fontSize = 10
        
        # Title
        story.append(Paragraph("KC Lower Limit Trending Filter (Shorting)", title_style))
        story.append(Paragraph(f"Date: {formatted_date} | Time: {formatted_time}", normal_style))
        story.append(Spacer(1, 0.5*inch))
        
        # Strategy Overview
        story.append(Paragraph("Strategy Overview", heading_style))
        overview_text = """This scanner identifies high-probability shorting opportunities using:
        • L2 Pattern: Two consecutive bars closing below previous lows
        • KC Breakdowns: Price breaking below Keltner Channel lower band
        • Volume Surge: Increased volume on L2 bars shows institutional selling
        • Pattern Combos: L2 + KC + Volume = Highest probability short setups
        • Early Detection: Identifies stocks building weakness before major declines"""
        story.append(Paragraph(overview_text.replace('\n', '<br/>'), normal_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Summary
        story.append(Paragraph(f"High Probability Short Setups ({len(filtered_df)} matches)", heading_style))
        
        if len(filtered_df) > 0:
            # Sector summary
            sector_counts = filtered_df['Sector'].value_counts()
            story.append(Paragraph("Sector Distribution:", normal_style))
            for sector, count in sector_counts.items():
                story.append(Paragraph(f"• {sector}: {count} stocks", normal_style))
            story.append(Spacer(1, 0.3*inch))
            
            # Create summary table
            summary_data = [['Ticker', 'Sector', 'Score', 'Pattern', 'Entry', 'Stop', 'Target 1', 'R:R']]
            
            for idx, row in filtered_df.iterrows():
                summary_data.append([
                    row['Ticker'],
                    row['Sector'][:20],  # Truncate long sector names
                    f"{row['Probability_Score']:.0f}",
                    row['Pattern'][:15],  # Truncate long pattern names
                    f"₹{row['Entry_Price']:.2f}",
                    f"₹{row['Stop_Loss']:.2f}",
                    f"₹{row['Target1']:.2f}",
                    f"{row['Risk_Reward_Ratio']:.2f}"
                ])
            
            # Create table
            summary_table = Table(summary_data, colWidths=[1.2*inch, 1.5*inch, 0.6*inch, 1.3*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.6*inch])
            
            # Table style
            summary_table.setStyle(TableStyle([
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                # Data rows
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f3f3')]),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#ddd')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ]))
            
            story.append(summary_table)
            story.append(PageBreak())
            
            # Detailed Analysis
            story.append(Paragraph("Detailed Analysis", heading_style))
            
            # Create detailed entries for each stock
            for idx, row in filtered_df.iterrows():
                # Stock header
                stock_style = ParagraphStyle(
                    'StockHeader',
                    parent=styles['Heading3'],
                    fontSize=14,
                    textColor=colors.HexColor('#2c3e50'),
                    spaceAfter=10
                )
                story.append(Paragraph(f"{row['Ticker']} - {row['Sector']}", stock_style))
                
                # Pattern and score
                pattern_text = f"<b>Pattern:</b> {row['Pattern']} | <b>Score:</b> {row['Probability_Score']:.0f}/100"
                story.append(Paragraph(pattern_text, normal_style))
                
                # Key metrics table
                metrics_data = [
                    ['Entry Price', f"₹{row['Entry_Price']:.2f}", 'Stop Loss', f"₹{row['Stop_Loss']:.2f}"],
                    ['Target 1', f"₹{row['Target1']:.2f}", 'Target 2', f"₹{row['Target2']:.2f}"],
                    ['Risk', f"₹{row['Risk']:.2f}", 'Risk:Reward', f"{row['Risk_Reward_Ratio']:.2f}"],
                    ['KC Distance', f"{row['KC_Distance_%']:.1f}%", 'ADX', f"{row['ADX']:.1f}"],
                    ['Volume Ratio', f"{row['Volume_Ratio']:.2f}x", 'Momentum 10D', f"{row['Momentum_10D']:.2f}%"],
                    ['L2 Count', f"{row['L2_Count']}", 'Recent L2s', f"{row['Recent_L2s']}"],
                    ['Base Score', row['Base_Score'], 'L2 Score', row['L2_Score']],
                    ['KC Score', row['KC_Score'], 'Advanced Score', row['Advanced_Score']]
                ]
                
                metrics_table = Table(metrics_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
                metrics_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
                    ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f8f9fa')),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                
                story.append(Spacer(1, 0.1*inch))
                story.append(metrics_table)
                
                # Description
                story.append(Spacer(1, 0.1*inch))
                desc_text = f"<b>Description:</b> {row['Description']}"
                story.append(Paragraph(desc_text, normal_style))
                
                # Add spacing between stocks
                story.append(Spacer(1, 0.4*inch))
                
                # Page break after every 2 stocks for readability
                if (idx + 1) % 2 == 0 and idx < len(filtered_df) - 1:
                    story.append(PageBreak())
        else:
            story.append(Paragraph("No KC lower trend patterns found in today's scan.", normal_style))
        
        # Footer
        story.append(Spacer(1, 0.5*inch))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#95a5a6'),
            alignment=TA_CENTER
        )
        story.append(Paragraph(f"Generated on {formatted_date} at {formatted_time} | KC Lower Limit Trending Filter", footer_style))
        story.append(Paragraph("Risk Management: Use proper position sizing for shorting. Stocks with lower congestion days typically perform better.", footer_style))
        
        # Build PDF
        doc.build(story)
        logger.info(f"PDF report generated successfully: {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"Error generating PDF report: {e}")
        return None

# -----------------------------
# Main Function
# -----------------------------
def main():
    """Main function to filter tickers for KC lower limit trending patterns"""
    logger.info("KC Lower Limit Trending filter with Sector Information (Shorting)")
    
    start_time = time.time()

    try:
        # Read the tickers
        tickers = read_ticker_file()
        if not tickers:
            logger.error("No tickers found, exiting")
            return 1
        
        logger.info(f"Starting analysis for {len(tickers)} tickers")
        
        # Process each ticker
        results = []
        for ticker in tickers:
            result = process_ticker(ticker)
            if result:
                results.append(result)
        
        # Create output files with timestamp
        today = datetime.datetime.now()
        formatted_date = today.strftime("%Y%m%d")
        formatted_time = today.strftime("%H%M%S")
        excel_file = os.path.join(RESULTS_DIR, f"KC_Lower_Limit_Trending_{formatted_date}_{formatted_time}.xlsx")
        html_file = os.path.join(HTML_DIR, f"KC_Lower_Limit_Trending_{formatted_date}_{formatted_time.replace('_', '-')}.html")
        pdf_file = os.path.join(PDF_DIR, f"KC_Lower_Limit_Trending_{formatted_date}_{formatted_time}.pdf")
        
        if results:
            # Convert to DataFrame
            results_df = pd.DataFrame(results)
            
            # Sort by Probability Score (descending) - highest probability trades first
            results_df = results_df.sort_values(by=['Probability_Score'], ascending=[False])
            
            # Round numeric columns for better readability
            numeric_cols = ['Entry_Price', 'Stop_Loss', 'Target1', 'Target2', 'Risk', 'Risk_Reward_Ratio', 
                          'KC_Lower', 'KC_Middle', 'KC_Distance_%', 'ADX', 'Volume_Ratio', 'Momentum_10D', 'Momentum_5D', 
                          'ATR', 'Trend_Strength', 'Probability_Score']
            for col in numeric_cols:
                if col in results_df.columns:
                    results_df[col] = results_df[col].astype(float).round(2)
            
            # Reorder columns to put important ones first
            priority_cols = ['Ticker', 'Sector', 'Pattern', 'Direction', 'Probability_Score', 
                           'Has_L2', 'L2_Count', 'L2_Volume', 'Recent_L2s',
                           'Trend_Strength', 'Congestion_Days', 
                           'Entry_Price', 'Stop_Loss', 'Target1', 'Target2', 'Risk', 'Risk_Reward_Ratio']
            # Only include columns that actually exist
            existing_priority_cols = [col for col in priority_cols if col in results_df.columns]
            other_cols = [col for col in results_df.columns if col not in existing_priority_cols]
            results_df = results_df[existing_priority_cols + other_cols]
            
            # Write to Excel
            results_df.to_excel(excel_file, index=False)
            logger.info(f"Successfully wrote {len(results_df)} filtered tickers to {excel_file}")
            
            # Also save a copy to Market_Regime/results for regime analysis
            try:
                market_regime_dir = os.path.join(os.path.dirname(RESULTS_DIR), 'Market_Regime', 'results')
                os.makedirs(market_regime_dir, exist_ok=True)
                market_regime_file = os.path.join(market_regime_dir, f"KC_Lower_Limit_Trending_{formatted_date}_{formatted_time}.xlsx")
                results_df.to_excel(market_regime_file, index=False)
                logger.info(f"Also saved copy to Market_Regime: {market_regime_file}")
            except Exception as e:
                logger.warning(f"Could not save to Market_Regime/results: {e}")
            
            # Generate HTML report
            html_output = generate_html_report(results_df, html_file, "Ticker.xlsx")
            logger.info(f"Generated HTML report at {html_output}")
            
            # Generate PDF report
            pdf_output = generate_pdf_report(results_df, pdf_file)
            if pdf_output:
                logger.info(f"Generated PDF report at {pdf_output}")
            else:
                logger.warning("Failed to generate PDF report")
            
            # Open the HTML report in the default browser
            try:
                webbrowser.open('file://' + os.path.abspath(html_output))
                logger.info(f"Opened HTML report in browser")
            except Exception as e:
                logger.warning(f"Could not open browser automatically: {e}")
            
            # Print summary to console
            print("\n===== High Probability Shorting Opportunities =====")
            print(f"Found {len(results_df)} high probability short setups")
            
            # Separate by pattern type
            bearish_patterns = results_df[results_df['Pattern'].isin(['Bearish_G_Pattern', 'Building_Bearish'])]
            l2_kc_combos = results_df[results_df['Pattern'].isin(['Strong_L2_KC_Combo', 'Power_L2_Volume'])]
            l2_patterns = results_df[results_df['Has_L2'] == True]
            high_prob = results_df[results_df['Probability_Score'] >= 70]
            
            if len(bearish_patterns) > 0:
                print(f"\n💎 BEARISH PATTERNS ({len(bearish_patterns)} stocks) - TIME TO BUILD/DOUBLE SHORT POSITIONS:")
                for idx, row in bearish_patterns.iterrows():
                    action = "DOUBLE SHORT NOW!" if row['Pattern'] == 'Bearish_G_Pattern' else "WATCH CLOSELY"
                    print(f"  {row['Ticker']} ({row['Sector']}): Score {row['Probability_Score']:.0f}/100, "
                          f"L2s in week: {row['L2_Days_Week']}, Volume surges: {row['Volume_Surge_Days']}, "
                          f"Action: {action}, Entry ₹{row['Entry_Price']:.2f}")
            
            if len(l2_kc_combos) > 0:
                print(f"\n🔥 STRONG L2 + KC COMBOS ({len(l2_kc_combos)} stocks) - HIGH PROBABILITY SHORTS:")
                for idx, row in l2_kc_combos.iterrows():
                    print(f"  {row['Ticker']} ({row['Sector']}): Score {row['Probability_Score']:.0f}/100, "
                          f"L2 Count: {row['L2_Count']}, Volume {row['Volume_Ratio']:.1f}x, "
                          f"Entry ₹{row['Entry_Price']:.2f}")
            
            if len(l2_patterns) > 0:
                print(f"\n📉 L2 Patterns Detected ({len(l2_patterns)} stocks):")
                for idx, row in l2_patterns.head(5).iterrows():
                    l2_vol = "with VOLUME" if row['L2_Volume'] else "building"
                    print(f"  {row['Ticker']} ({row['Sector']}): Score {row['Probability_Score']:.0f}/100, "
                          f"L2 {l2_vol}, Recent L2s: {row['Recent_L2s']}")
            
            # High probability summary
            if len(high_prob) > 0:
                print(f"\n⭐ High Probability Short Setups (Score >= 70): {len(high_prob)} stocks")
            
            # Print sector summary
            sector_counts = results_df['Sector'].value_counts()
            print("\nSector Distribution:")
            for sector, count in sector_counts.items():
                print(f"  {sector}: {count} stocks")
            
            print("\nTop 5 short setups by probability score:")
            for idx, row in results_df.head(5).iterrows():
                l2_status = f"L2:{row['L2_Count']}" if row['Has_L2'] else "No L2"
                print(f"{row['Ticker']} ({row['Sector']}): Score {row['Probability_Score']:.0f}/100, "
                      f"{row['Pattern']}, {l2_status}, Volume {row['Volume_Ratio']:.1f}x, "
                      f"Entry ₹{row['Entry_Price']:.2f}")

            print(f"\nDetailed results saved to: {excel_file}")
            print(f"HTML report opened in browser: {html_file}")
            if pdf_output:
                print(f"PDF report saved to: {pdf_file}")
        else:
            # Create empty Excel with columns
            empty_cols = ['Ticker', 'Sector', 'Pattern', 'Direction', 'Probability_Score', 
                          'Has_L2', 'L2_Count', 'L2_Volume', 'Recent_L2s',
                          'Base_Score', 'L2_Score', 'KC_Score', 'Advanced_Score', 'Bearish_Score',
                          'L2_Days_Week', 'Volume_Surge_Days', 'Building_Momentum',
                          'Days_Since_KC_Break', 'Trend_Strength', 'Congestion_Days',
                          'Entry_Price', 'Stop_Loss', 'Target1', 'Target2', 'Risk', 'Risk_Reward_Ratio',
                          'KC_Lower', 'KC_Middle', 'KC_Distance_%', 'ADX', 'Volume_Ratio', 
                          'Momentum_10D', 'Momentum_5D', 'Pattern_Strength', 'ATR', 'Description']
            pd.DataFrame(columns=empty_cols).to_excel(excel_file, index=False)
            
            # Generate empty HTML report
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>KC Lower Limit Trending Filter - {formatted_date}</title>
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
                        border-bottom: 2px solid #e74c3c;
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
                <h1>📉 KC Lower Limit Trending Filter (Shorting)</h1>
                <div class="no-results">
                    <h2>No KC Lower Trend Patterns Found</h2>
                    <p>No tickers matched the Keltner Channel lower limit trending criteria for shorting in today's scan.</p>
                    <p>The filter searched for stocks with:</p>
                    <ul style="display: inline-block; text-align: left;">
                        <li>Price trading below Keltner Channel lower band</li>
                        <li>Strong bearish trending behavior (ADX > 25)</li>
                        <li>Low congestion (less than 10 days in narrow range)</li>
                        <li>Negative momentum and volume expansion</li>
                        <li>Score of 6/9 or higher for trend confirmation</li>
                    </ul>
                    <p><strong>Note:</strong> KC lower trend patterns for shorting are selective and appear during strong downtrending markets.</p>
                </div>
                <div style="margin-top: 50px; color: #999;">
                    <p>Generated on {formatted_date} at {formatted_time.replace('_', ':')} | KC Lower Limit Trending Filter</p>
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
            
            # Generate empty PDF report
            pdf_output = generate_pdf_report(pd.DataFrame(), pdf_file)
            
            logger.info(f"No KC lower trend patterns found. Empty output files created at {excel_file}, {html_file}, and {pdf_file}")
            print("\nNo KC lower trend patterns found for shorting.")
            print(f"Empty results saved to: {excel_file}, {html_file}, and {pdf_file}")
            
        # Calculate and print execution time
        execution_time = time.time() - start_time
        logger.info(f"Total execution time: {execution_time:.2f} seconds")
        print(f"\nExecution time: {execution_time:.2f} seconds")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    # Print banner
    print("\n===================================")
    print("High Probability Shorting Scanner")
    print("===================================")
    print("Identifying Bearish G-Pattern setups:")
    print("1. L2 Pattern: 2+ bars closing below previous lows")
    print("2. Multi-day bearish momentum building (3-5 days)")
    print("3. Volume surge confirmation for adding shorts")
    print("4. KC breakdown for trend confirmation")
    print("5. Low congestion for clean moves")
    print("")
    print("Short Position Strategy:")
    print("- Initial: L2 pattern forms")
    print("- Add: Volume surge on L2 (day 3-5)")
    print("- Hold: For multi-week declines")
    print("===================================")
    print(f"Using credentials for user: {user_name}")
    print("===================================\n")

    sys.exit(main())