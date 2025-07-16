#!/usr/bin/env python
# VSR_Momentum_Scanner.py - Volume Spread Ratio Momentum Scanner
# Identifies stocks with strong momentum using hourly data and volume spread analysis
# 1. Uses hourly timeframe for intraday momentum detection
# 2. Calculates Volume Spread Ratio (VSR) = Volume * Price Range
# 3. Identifies stocks with expanding VSR indicating momentum
# 4. Combines with price action patterns for high probability setups
# 5. Outputs to Hourly folder with VSR_{Date}_{Time}.xlsx format

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
# PDF generation imports - optional
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
    logger.warning("reportlab not available - PDF generation disabled")

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "vsr_momentum_scanner.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="VSR Momentum Scanner with Hourly Data")
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
RESULTS_DIR = os.path.join(SCRIPT_DIR, "Hourly")  # Output to Hourly folder
HTML_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "Detailed_Analysis", "Hourly")
PDF_DIR = os.path.join(RESULTS_DIR, "PDF")

# Ensure directories exist
dirs_to_create = [RESULTS_DIR, HTML_DIR]
if REPORTLAB_AVAILABLE:
    dirs_to_create.append(PDF_DIR)
    
for dir_path in dirs_to_create:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# For data retrieval fallback
FALLBACK_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'BT', 'data')

# Mapping for interval to Kite Connect API parameters
interval_mapping = {
    '5m': '5minute',
    '15m': '15minute',
    '30m': '30minute',
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

    return pd.DataFrame()

# -----------------------------
# Calculate VSR Indicators
# -----------------------------
def calculate_vsr_indicators(hourly_data):
    """Calculate Volume Spread Ratio and momentum indicators for hourly data"""
    if hourly_data.empty or len(hourly_data) < 50:
        logger.warning(f"Insufficient data points for {hourly_data['Ticker'].iloc[0] if not hourly_data.empty else 'unknown ticker'}")
        return None
        
    # Create a copy to avoid SettingWithCopyWarning
    df = hourly_data.copy()
    
    # Calculate price spread (range)
    df['Spread'] = df['High'] - df['Low']
    df['Spread_Pct'] = (df['Spread'] / df['Close']) * 100
    
    # Calculate Volume Spread Ratio (VSR)
    # VSR = Volume * Spread (normalized by average)
    df['VSR'] = df['Volume'] * df['Spread']
    
    # Calculate moving averages of VSR
    df['VSR_MA20'] = df['VSR'].rolling(window=20).mean()
    df['VSR_MA50'] = df['VSR'].rolling(window=50).mean()
    
    # VSR expansion ratio
    df['VSR_Ratio'] = df['VSR'] / df['VSR_MA20']
    
    # Calculate VSR momentum
    df['VSR_ROC'] = ((df['VSR'] - df['VSR'].shift(10)) / df['VSR'].shift(10)) * 100
    
    # Price EMAs for trend
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    # Volume analysis
    df['AvgVolume20'] = df['Volume'].rolling(window=20).mean()
    df['VolumeRatio'] = df['Volume'] / df['AvgVolume20']
    
    # Momentum indicators
    df['ROC5'] = ((df['Close'] - df['Close'].shift(5)) / df['Close'].shift(5)) * 100
    df['ROC10'] = ((df['Close'] - df['Close'].shift(10)) / df['Close'].shift(10)) * 100
    df['ROC20'] = ((df['Close'] - df['Close'].shift(20)) / df['Close'].shift(20)) * 100
    
    # ATR for volatility
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift(1)).abs()
    low_close = (df['Low'] - df['Close'].shift(1)).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    df['TR'] = ranges.max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()
    df['ATR_Pct'] = (df['ATR'] / df['Close']) * 100
    
    # Keltner Channel for context
    kc_multiplier = 2.0
    df['KC_Upper'] = df['EMA21'] + (kc_multiplier * df['ATR'])
    df['KC_Lower'] = df['EMA21'] - (kc_multiplier * df['ATR'])
    df['KC_Middle'] = df['EMA21']
    
    # Position relative to KC
    df['Above_KC_Upper'] = df['Close'] > df['KC_Upper']
    df['KC_Distance'] = ((df['Close'] - df['KC_Upper']) / df['KC_Upper']) * 100
    
    # Detect VSR surges
    df['VSR_Surge'] = df['VSR_Ratio'] > 2.0  # VSR is 2x average
    df['VSR_Extreme'] = df['VSR_Ratio'] > 3.0  # VSR is 3x average
    
    # Count recent VSR surges
    df['VSR_Surge_Count_10'] = df['VSR_Surge'].rolling(window=10).sum()
    df['VSR_Surge_Count_20'] = df['VSR_Surge'].rolling(window=20).sum()
    
    # Trend alignment
    df['Bullish_Trend'] = (df['Close'] > df['EMA9']) & (df['EMA9'] > df['EMA21']) & (df['EMA21'] > df['EMA50'])
    df['EMA_Aligned'] = df['Bullish_Trend'].astype(int)
    
    # Price action patterns
    df['Higher_High'] = (df['High'] > df['High'].shift(1)) & (df['Low'] > df['Low'].shift(1))
    df['HH_Count'] = df['Higher_High'].rolling(window=5).sum()
    
    # Breakout detection
    df['High_20'] = df['High'].rolling(window=20).max()
    df['Low_20'] = df['Low'].rolling(window=20).min()
    df['Near_Breakout'] = df['Close'] > (df['High_20'] * 0.98)  # Within 2% of 20-bar high
    df['Breakout'] = df['Close'] > df['High_20'].shift(1)
    
    # VSR divergence detection
    # Positive divergence: Price making lower lows but VSR making higher lows
    price_low_5 = df['Low'].rolling(window=5).min()
    vsr_low_5 = df['VSR'].rolling(window=5).min()
    df['Price_Lower_Low'] = price_low_5 < price_low_5.shift(5)
    df['VSR_Higher_Low'] = vsr_low_5 > vsr_low_5.shift(5)
    df['VSR_Pos_Divergence'] = df['Price_Lower_Low'] & df['VSR_Higher_Low']
    
    # Negative divergence: Price making higher highs but VSR making lower highs
    price_high_5 = df['High'].rolling(window=5).max()
    vsr_high_5 = df['VSR'].rolling(window=5).max()
    df['Price_Higher_High'] = price_high_5 > price_high_5.shift(5)
    df['VSR_Lower_High'] = vsr_high_5 < vsr_high_5.shift(5)
    df['VSR_Neg_Divergence'] = df['Price_Higher_High'] & df['VSR_Lower_High']
    
    # Buying Climax detection
    # Extreme volume + wide spread + close near high + after uptrend
    df['Wide_Spread'] = df['Spread_Pct'] > df['Spread_Pct'].rolling(window=20).mean() * 1.5
    df['Close_Near_High'] = (df['Close'] - df['Low']) / (df['High'] - df['Low']) > 0.8
    df['Extreme_Volume'] = df['VolumeRatio'] > 2.5
    df['Uptrend_20'] = df['ROC20'] > 10
    
    df['Buying_Climax'] = (
        df['Extreme_Volume'] & 
        df['Wide_Spread'] & 
        df['Close_Near_High'] & 
        df['Uptrend_20'] &
        (df['VSR_Ratio'] > 3.0)
    )
    
    # Selling Climax detection
    # Extreme volume + wide spread + close near low + after downtrend
    df['Close_Near_Low'] = (df['Close'] - df['Low']) / (df['High'] - df['Low']) < 0.2
    df['Downtrend_20'] = df['ROC20'] < -10
    
    df['Selling_Climax'] = (
        df['Extreme_Volume'] & 
        df['Wide_Spread'] & 
        df['Close_Near_Low'] & 
        df['Downtrend_20'] &
        (df['VSR_Ratio'] > 3.0)
    )
    
    # Climax with divergence (strongest signals)
    df['Buying_Climax_Divergence'] = df['Buying_Climax'] & df['VSR_Neg_Divergence']
    df['Selling_Climax_Divergence'] = df['Selling_Climax'] & df['VSR_Pos_Divergence']
    
    # Count recent climaxes
    df['Buying_Climax_Count_10'] = df['Buying_Climax'].rolling(window=10).sum()
    df['Selling_Climax_Count_10'] = df['Selling_Climax'].rolling(window=10).sum()
    
    # Accumulation detection
    # High volume with small spread = accumulation
    df['Accumulation'] = (df['VolumeRatio'] > 1.5) & (df['Spread_Pct'] < df['Spread_Pct'].rolling(window=20).mean())
    df['Accumulation_Count'] = df['Accumulation'].rolling(window=10).sum()
    
    # Distribution detection
    # High volume with small spread after uptrend = distribution
    df['Distribution'] = (df['VolumeRatio'] > 1.5) & (df['Spread_Pct'] < df['Spread_Pct'].rolling(window=20).mean()) & (df['ROC10'] > 5)
    df['Distribution_Count'] = df['Distribution'].rolling(window=10).sum()
    
    # Momentum building pattern
    df['Momentum_Building'] = (
        (df['VSR_Surge_Count_10'] >= 2) &  # Multiple VSR surges
        (df['ROC10'] > 0) &  # Positive momentum
        (df['EMA_Aligned'] == 1) &  # Trend aligned
        (df['HH_Count'] >= 2)  # Making higher highs
    )
    
    # Calculate composite momentum score
    df['VSR_Score'] = 0
    df.loc[df['VSR_Ratio'] > 1.5, 'VSR_Score'] += 1
    df.loc[df['VSR_Ratio'] > 2.0, 'VSR_Score'] += 1
    df.loc[df['VSR_Ratio'] > 3.0, 'VSR_Score'] += 1
    df.loc[df['VSR_ROC'] > 20, 'VSR_Score'] += 1
    df.loc[df['VSR_ROC'] > 50, 'VSR_Score'] += 1
    df.loc[df['EMA_Aligned'] == 1, 'VSR_Score'] += 1
    df.loc[df['VolumeRatio'] > 2.0, 'VSR_Score'] += 1
    df.loc[df['Near_Breakout'], 'VSR_Score'] += 1
    df.loc[df['Momentum_Building'], 'VSR_Score'] += 2
    
    return df

# -----------------------------
# VSR Momentum Detection
# -----------------------------
def detect_vsr_momentum(data):
    """
    Detect high probability momentum setups using VSR analysis
    Returns a dictionary with pattern details if found, None otherwise
    """
    if data is None or data.empty or len(data) < 50:
        return None

    # Get last few bars for analysis
    last_bar = data.iloc[-1]
    last_5_bars = data.tail(5)
    last_10_bars = data.tail(10)
    
    # Basic filtering - require some VSR activity
    if last_bar['VSR_Ratio'] < 1.0 and last_bar['VSR_Score'] < 3:
        return None
    
    # Calculate base conditions
    base_conditions = {
        'positive_momentum': last_bar['ROC10'] > 0,
        'vsr_expansion': last_bar['VSR_Ratio'] > 1.5,
        'volume_present': last_bar['VolumeRatio'] > 0.8,
        'trend_aligned': last_bar['EMA_Aligned'] == 1,
        'making_highs': last_bar['HH_Count'] >= 1,
        'low_volatility': last_bar['ATR_Pct'] < 5.0,  # Not too volatile
        'price_strength': last_bar['Close'] > last_bar['EMA9'],
    }
    
    # VSR specific conditions
    vsr_conditions = {
        'vsr_surge': last_bar['VSR_Surge'],
        'vsr_extreme': last_bar['VSR_Extreme'],
        'recent_vsr_activity': last_bar['VSR_Surge_Count_10'] >= 2,
        'vsr_momentum': last_bar['VSR_ROC'] > 20,
        'vsr_above_ma': last_bar['VSR'] > last_bar['VSR_MA20'],
    }
    
    # Momentum conditions
    momentum_conditions = {
        'momentum_building': last_bar['Momentum_Building'],
        'near_breakout': last_bar['Near_Breakout'],
        'actual_breakout': last_bar['Breakout'],
        'accumulation_present': last_bar['Accumulation_Count'] >= 2,
        'strong_momentum': last_bar['ROC5'] > 2,
    }
    
    # Advanced patterns
    advanced_conditions = {
        'vsr_pos_divergence': last_bar['VSR_Pos_Divergence'] if 'VSR_Pos_Divergence' in last_bar else False,
        'vsr_neg_divergence': last_bar['VSR_Neg_Divergence'] if 'VSR_Neg_Divergence' in last_bar else False,
        'multiple_surges': last_5_bars['VSR_Surge'].sum() >= 2,
        'consistent_vsr': last_5_bars['VSR_Ratio'].mean() > 1.5,
        'volume_confirmation': last_5_bars['VolumeRatio'].max() > 2.0,
        'price_momentum': last_bar['ROC20'] > 5,
    }
    
    # Climax conditions
    climax_conditions = {
        'buying_climax': last_bar['Buying_Climax'] if 'Buying_Climax' in last_bar else False,
        'selling_climax': last_bar['Selling_Climax'] if 'Selling_Climax' in last_bar else False,
        'buying_climax_divergence': last_bar['Buying_Climax_Divergence'] if 'Buying_Climax_Divergence' in last_bar else False,
        'selling_climax_divergence': last_bar['Selling_Climax_Divergence'] if 'Selling_Climax_Divergence' in last_bar else False,
        'recent_buying_climax': last_bar['Buying_Climax_Count_10'] > 0 if 'Buying_Climax_Count_10' in last_bar else False,
        'recent_selling_climax': last_bar['Selling_Climax_Count_10'] > 0 if 'Selling_Climax_Count_10' in last_bar else False,
    }
    
    # Calculate scores
    base_score = sum(base_conditions.values())
    vsr_score = sum(vsr_conditions.values())
    momentum_score = sum(momentum_conditions.values())
    advanced_score = sum(advanced_conditions.values())
    climax_score = sum(climax_conditions.values())
    
    # Calculate weighted total score
    weighted_score = (
        base_score * 1.0 +
        vsr_score * 3.0 +  # VSR is most important
        momentum_score * 2.0 +
        advanced_score * 2.5 +
        climax_score * 4.0  # Climax patterns are very important
    )
    
    max_base_score = len(base_conditions)
    max_vsr_score = len(vsr_conditions)
    max_momentum_score = len(momentum_conditions)
    max_advanced_score = len(advanced_conditions)
    max_climax_score = len(climax_conditions)
    max_weighted_score = (max_base_score * 1.0 + max_vsr_score * 3.0 + 
                         max_momentum_score * 2.0 + max_advanced_score * 2.5 + max_climax_score * 4.0)
    
    # Require minimum scores
    if base_score >= 4 and vsr_score >= 2:
        # Calculate probability score
        normalized_score = (weighted_score / max_weighted_score) * 100
        
        # Pattern bonuses
        pattern_bonus = 0
        if vsr_conditions['vsr_extreme'] and momentum_conditions['actual_breakout']:
            pattern_bonus += 20
        elif vsr_conditions['vsr_surge'] and momentum_conditions['near_breakout']:
            pattern_bonus += 15
        elif advanced_conditions['multiple_surges']:
            pattern_bonus += 10
        
        probability_score = min(100, normalized_score + pattern_bonus)
        
        # Calculate targets based on ATR
        atr_multiplier = 2.0
        stop_loss = last_bar['Close'] - (atr_multiplier * last_bar['ATR'])
        risk = last_bar['Close'] - stop_loss
        target1 = last_bar['Close'] + (2 * risk)
        target2 = last_bar['Close'] + (3 * risk)
        
        # Determine pattern type
        if climax_conditions['buying_climax_divergence']:
            pattern_type = 'Buying_Climax_Divergence'
            description = 'BUYING CLIMAX with divergence - POTENTIAL TOP! Consider profit taking!'
        elif climax_conditions['selling_climax_divergence']:
            pattern_type = 'Selling_Climax_Divergence'  
            description = 'SELLING CLIMAX with divergence - POTENTIAL BOTTOM! Watch for reversal!'
        elif climax_conditions['buying_climax']:
            pattern_type = 'Buying_Climax'
            description = 'Buying climax detected - CAUTION at highs!'
        elif climax_conditions['selling_climax']:
            pattern_type = 'Selling_Climax'
            description = 'Selling climax detected - Possible capitulation!'
        elif vsr_conditions['vsr_extreme'] and momentum_conditions['actual_breakout']:
            pattern_type = 'VSR_Extreme_Breakout'
            description = 'Extreme VSR with price breakout - HIGHEST MOMENTUM!'
        elif vsr_conditions['vsr_surge'] and momentum_conditions['momentum_building']:
            pattern_type = 'VSR_Momentum_Build'
            description = 'VSR surge with building momentum - POSITION ENTRY!'
        elif advanced_conditions['multiple_surges'] and momentum_conditions['near_breakout']:
            pattern_type = 'VSR_Pre_Breakout'
            description = 'Multiple VSR surges near breakout - WATCH CLOSELY!'
        elif vsr_conditions['recent_vsr_activity'] and base_conditions['trend_aligned']:
            pattern_type = 'VSR_Trend_Aligned'
            description = 'VSR activity in aligned trend - MOMENTUM STARTING!'
        elif advanced_conditions['vsr_pos_divergence']:
            pattern_type = 'VSR_Pos_Divergence'
            description = 'Positive VSR divergence - ACCUMULATION DETECTED!'
        elif advanced_conditions['vsr_neg_divergence']:
            pattern_type = 'VSR_Neg_Divergence'
            description = 'Negative VSR divergence - DISTRIBUTION WARNING!'
        else:
            pattern_type = 'VSR_Signal'
            description = 'VSR expansion detected - EARLY MOMENTUM!'
        
        # Calculate recent VSR statistics
        vsr_stats = {
            'avg_vsr_ratio': last_10_bars['VSR_Ratio'].mean(),
            'max_vsr_ratio': last_10_bars['VSR_Ratio'].max(),
            'vsr_surges_10': int(last_bar['VSR_Surge_Count_10']),
            'vsr_surges_20': int(last_bar['VSR_Surge_Count_20']),
        }
        
        return {
            'pattern': pattern_type,
            'description': description,
            'direction': 'LONG' if not ('Selling' in pattern_type) else 'SHORT',
            'probability_score': probability_score,
            'base_score': base_score,
            'vsr_score': vsr_score,
            'momentum_score': momentum_score,
            'advanced_score': advanced_score,
            'climax_score': climax_score,
            'weighted_score': weighted_score,
            'max_base_score': max_base_score,
            'max_vsr_score': max_vsr_score,
            'max_momentum_score': max_momentum_score,
            'max_advanced_score': max_advanced_score,
            'max_climax_score': max_climax_score,
            'vsr_ratio': last_bar['VSR_Ratio'],
            'vsr_roc': last_bar['VSR_ROC'],
            'vsr_stats': vsr_stats,
            'volume_ratio': last_bar['VolumeRatio'],
            'spread_pct': last_bar['Spread_Pct'],
            'entry_price': last_bar['Close'],
            'stop_loss': stop_loss,
            'target1': target1,
            'target2': target2,
            'atr': last_bar['ATR'],
            'atr_pct': last_bar['ATR_Pct'],
            'momentum_5h': last_bar['ROC5'],
            'momentum_10h': last_bar['ROC10'],
            'momentum_20h': last_bar['ROC20'],
            'kc_distance': last_bar['KC_Distance'],
            'accumulation_count': int(last_bar['Accumulation_Count']),
            'distribution_count': int(last_bar['Distribution_Count']) if 'Distribution_Count' in last_bar else 0,
            'hh_count': int(last_bar['HH_Count']),
            'buying_climax_count': int(last_bar['Buying_Climax_Count_10']) if 'Buying_Climax_Count_10' in last_bar else 0,
            'selling_climax_count': int(last_bar['Selling_Climax_Count_10']) if 'Selling_Climax_Count_10' in last_bar else 0,
            'has_pos_divergence': last_bar['VSR_Pos_Divergence'] if 'VSR_Pos_Divergence' in last_bar else False,
            'has_neg_divergence': last_bar['VSR_Neg_Divergence'] if 'VSR_Neg_Divergence' in last_bar else False,
            'base_conditions': base_conditions,
            'vsr_conditions': vsr_conditions,
            'momentum_conditions': momentum_conditions,
            'advanced_conditions': advanced_conditions,
            'climax_conditions': climax_conditions
        }
    
    return None

# -----------------------------
# Process Single Ticker
# -----------------------------
def process_ticker(ticker):
    """Process a single ticker for VSR momentum patterns"""
    logger.info(f"Processing {ticker}")
    
    try:
        now = datetime.datetime.now()
        
        # For hourly data, we need at least 10 days of data
        from_date_hourly = (now - relativedelta(days=15)).strftime('%Y-%m-%d')
        to_date = now.strftime('%Y-%m-%d')
        
        # Fetch hourly data
        hourly_data = fetch_data_kite(ticker, interval_mapping['1h'], from_date_hourly, to_date)
        if hourly_data.empty:
            logger.warning(f"No hourly data available for {ticker}, skipping")
            return None
            
        # Calculate VSR indicators
        hourly_with_indicators = calculate_vsr_indicators(hourly_data)
        if hourly_with_indicators is None:
            logger.warning(f"Could not calculate indicators for {ticker}, skipping")
            return None
            
        # Detect VSR momentum pattern
        vsr_pattern = detect_vsr_momentum(hourly_with_indicators)
        
        if vsr_pattern is None:
            logger.info(f"{ticker} - No VSR momentum pattern detected")
            return None
        
        # Get the most recent values
        last_bar = hourly_with_indicators.iloc[-1]
        
        # Calculate risk and reward
        entry_price = vsr_pattern['entry_price']
        stop_loss = vsr_pattern['stop_loss']
        risk = entry_price - stop_loss
        
        # Calculate risk-reward ratio
        if risk > 0:
            risk_reward_ratio = abs(vsr_pattern['target1'] - entry_price) / risk
        else:
            risk_reward_ratio = 0
        
        # Get sector information
        sector = get_sector_for_ticker(ticker)
        
        # Log the findings
        logger.info(f"{ticker} - {vsr_pattern['pattern']} Detected!")
        logger.info(f"{ticker} - Probability Score: {vsr_pattern['probability_score']:.1f}/100")
        logger.info(f"{ticker} - VSR Ratio: {vsr_pattern['vsr_ratio']:.2f}, VSR ROC: {vsr_pattern['vsr_roc']:.1f}%")
        logger.info(f"{ticker} - Entry: {entry_price:.2f}, Stop: {stop_loss:.2f}, Target1: {vsr_pattern['target1']:.2f}")
        logger.info(f"{ticker} - Sector: {sector}")
        
        # Prepare result
        result = {
            'Ticker': ticker,
            'Sector': sector,
            'Pattern': vsr_pattern['pattern'],
            'Direction': vsr_pattern['direction'],
            'Probability_Score': vsr_pattern['probability_score'],
            'VSR_Ratio': vsr_pattern['vsr_ratio'],
            'VSR_ROC': vsr_pattern['vsr_roc'],
            'Volume_Ratio': vsr_pattern['volume_ratio'],
            'Spread_Pct': vsr_pattern['spread_pct'],
            'Base_Score': f"{vsr_pattern['base_score']}/{vsr_pattern['max_base_score']}",
            'VSR_Score': f"{vsr_pattern['vsr_score']}/{vsr_pattern['max_vsr_score']}",
            'Momentum_Score': f"{vsr_pattern['momentum_score']}/{vsr_pattern['max_momentum_score']}",
            'Advanced_Score': f"{vsr_pattern['advanced_score']}/{vsr_pattern['max_advanced_score']}",
            'Climax_Score': f"{vsr_pattern['climax_score']}/{vsr_pattern['max_climax_score']}",
            'VSR_Surges_10H': vsr_pattern['vsr_stats']['vsr_surges_10'],
            'VSR_Surges_20H': vsr_pattern['vsr_stats']['vsr_surges_20'],
            'Avg_VSR_Ratio': vsr_pattern['vsr_stats']['avg_vsr_ratio'],
            'Max_VSR_Ratio': vsr_pattern['vsr_stats']['max_vsr_ratio'],
            'Accumulation_Count': vsr_pattern['accumulation_count'],
            'Distribution_Count': vsr_pattern['distribution_count'],
            'HH_Count': vsr_pattern['hh_count'],
            'Buying_Climax_10H': vsr_pattern['buying_climax_count'],
            'Selling_Climax_10H': vsr_pattern['selling_climax_count'],
            'Has_Pos_Divergence': vsr_pattern['has_pos_divergence'],
            'Has_Neg_Divergence': vsr_pattern['has_neg_divergence'],
            'Entry_Price': entry_price,
            'Stop_Loss': stop_loss,
            'Target1': vsr_pattern['target1'],
            'Target2': vsr_pattern['target2'],
            'Risk': risk,
            'Risk_Reward_Ratio': risk_reward_ratio,
            'ATR': vsr_pattern['atr'],
            'ATR_Pct': vsr_pattern['atr_pct'],
            'Momentum_5H': vsr_pattern['momentum_5h'],
            'Momentum_10H': vsr_pattern['momentum_10h'],
            'Momentum_20H': vsr_pattern['momentum_20h'],
            'KC_Distance_%': vsr_pattern['kc_distance'],
            'Description': vsr_pattern['description']
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
def generate_html_report(filtered_df, output_file):
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
        <title>VSR Momentum Scanner - {formatted_date}</title>
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
                border-bottom: 2px solid #9b59b6;
                padding-bottom: 10px;
            }}
            .header-info {{
                display: flex;
                justify-content: space-between;
                color: #7f8c8d;
                margin-bottom: 20px;
            }}
            .vsr-info {{
                background-color: #f3e5f5;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                border-left: 4px solid #9b59b6;
            }}
            .sector-summary {{
                margin: 20px 0;
                padding: 15px;
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                background-color: white;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            thead tr {{
                background-color: #9b59b6;
                color: white;
            }}
            tbody tr:nth-of-type(even) {{
                background-color: #f8f9fa;
            }}
            tbody tr:hover {{
                background-color: #e9ecef;
                cursor: pointer;
            }}
            .extreme-vsr {{
                background-color: #e74c3c;
                color: white;
                padding: 3px 8px;
                border-radius: 12px;
                font-weight: bold;
            }}
            .high-vsr {{
                background-color: #f39c12;
                color: white;
                padding: 3px 8px;
                border-radius: 12px;
            }}
            .normal-vsr {{
                background-color: #3498db;
                color: white;
                padding: 3px 8px;
                border-radius: 12px;
            }}
            .probability-high {{
                background-color: #27ae60;
                color: white;
                padding: 4px 10px;
                border-radius: 4px;
                font-weight: bold;
            }}
            .probability-medium {{
                background-color: #f39c12;
                color: white;
                padding: 4px 10px;
                border-radius: 4px;
                font-weight: bold;
            }}
            .probability-low {{
                background-color: #95a5a6;
                color: white;
                padding: 4px 10px;
                border-radius: 4px;
            }}
            .momentum-positive {{
                color: #27ae60;
                font-weight: bold;
            }}
            .momentum-negative {{
                color: #e74c3c;
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
        <h1>📊 VSR Momentum Scanner</h1>
        <div class="header-info">
            <div>Date: {formatted_date} | Time: {formatted_time}</div>
            <div>Hourly Timeframe | Volume Spread Ratio Analysis</div>
        </div>

        <div class="vsr-info">
            <h3>What is Volume Spread Ratio (VSR)?</h3>
            <p>VSR combines volume and price spread to identify momentum surges:</p>
            <ul>
                <li><strong>VSR = Volume × Price Spread</strong> - Higher values indicate strong momentum</li>
                <li><strong>VSR Ratio > 2.0</strong> - Significant momentum surge detected</li>
                <li><strong>VSR Ratio > 3.0</strong> - Extreme momentum, often precedes major moves</li>
                <li><strong>Multiple VSR Surges</strong> - Sustained momentum building</li>
                <li><strong>Hourly Analysis</strong> - Captures intraday momentum shifts early</li>
            </ul>
            <h4>🎯 Enhanced with Climax Detection:</h4>
            <ul>
                <li><strong>Buying Climax</strong> - Extreme volume + wide spread + close near high (potential exhaustion at tops)</li>
                <li><strong>Selling Climax</strong> - Extreme volume + wide spread + close near low (potential capitulation at bottoms)</li>
                <li><strong>Divergences</strong> - Price-VSR divergences signal potential reversals or continuation</li>
                <li><strong>⚠️ Climax + Divergence</strong> - Highest risk of reversal, use extreme caution!</li>
            </ul>
        </div>

        <h2>🚀 Momentum Opportunities ({len(filtered_df)} matches)</h2>
    """

    # Add summary statistics with climax information
    if len(filtered_df) > 0:
        # Calculate statistics
        extreme_vsr = len(filtered_df[filtered_df['VSR_Ratio'] >= 3.0])
        high_vsr = len(filtered_df[(filtered_df['VSR_Ratio'] >= 2.0) & (filtered_df['VSR_Ratio'] < 3.0)])
        high_prob = len(filtered_df[filtered_df['Probability_Score'] >= 70])
        
        # Climax statistics
        buying_climax = len(filtered_df[filtered_df.get('Buying_Climax_10H', 0) > 0]) if 'Buying_Climax_10H' in filtered_df.columns else 0
        selling_climax = len(filtered_df[filtered_df.get('Selling_Climax_10H', 0) > 0]) if 'Selling_Climax_10H' in filtered_df.columns else 0
        pos_divergence = len(filtered_df[filtered_df.get('Has_Pos_Divergence', False) == True]) if 'Has_Pos_Divergence' in filtered_df.columns else 0
        neg_divergence = len(filtered_df[filtered_df.get('Has_Neg_Divergence', False) == True]) if 'Has_Neg_Divergence' in filtered_df.columns else 0
        
        html_content += f"""
        <div class="stats-summary" style="background: #f8f9fa; padding: 15px; margin: 20px 0; border-radius: 8px;">
            <h3>📊 Key Statistics</h3>
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px;">
                <div>
                    <strong>VSR Analysis:</strong><br>
                    Extreme VSR (≥3.0): {extreme_vsr}<br>
                    High VSR (2.0-3.0): {high_vsr}<br>
                    High Probability (≥70): {high_prob}
                </div>
                <div>
                    <strong>Climax Events:</strong><br>
                    Buying Climax: {buying_climax}<br>
                    Selling Climax: {selling_climax}<br>
                    Total Climax: {buying_climax + selling_climax}
                </div>
                <div>
                    <strong>Divergences:</strong><br>
                    Positive Divergence: {pos_divergence}<br>
                    Negative Divergence: {neg_divergence}<br>
                    Total Divergences: {pos_divergence + neg_divergence}
                </div>
                <div>
                    <strong>Risk Alerts:</strong><br>
                    Climax + Divergence: {len(filtered_df[(filtered_df.get('Buying_Climax_10H', 0) > 0) | (filtered_df.get('Selling_Climax_10H', 0) > 0) & ((filtered_df.get('Has_Pos_Divergence', False) == True) | (filtered_df.get('Has_Neg_Divergence', False) == True))])} ⚠️<br>
                    Watch closely for reversals!
                </div>
            </div>
        </div>
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

    # Add summary table
    html_content += """
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Sector</th>
                    <th>Probability</th>
                    <th>VSR Ratio</th>
                    <th>VSR Surges</th>
                    <th>Pattern</th>
                    <th>Climax</th>
                    <th>Entry</th>
                    <th>Stop Loss</th>
                    <th>Target 1</th>
                    <th>Momentum</th>
                </tr>
            </thead>
            <tbody>
    """

    # Add rows for each ticker
    for idx, row in filtered_df.iterrows():
        # Determine VSR class
        vsr_class = "extreme-vsr" if row['VSR_Ratio'] >= 3.0 else "high-vsr" if row['VSR_Ratio'] >= 2.0 else "normal-vsr"
        
        # Determine probability class
        prob_class = "probability-high" if row['Probability_Score'] >= 70 else "probability-medium" if row['Probability_Score'] >= 50 else "probability-low"
        
        # Momentum class
        momentum_class = "momentum-positive" if row['Momentum_10H'] > 0 else "momentum-negative"
        
        # Determine climax indicators
        climax_html = ""
        if row.get('Buying_Climax_10H', 0) > 0 or row.get('Selling_Climax_10H', 0) > 0:
            if row.get('Has_Pos_Divergence', False) or row.get('Has_Neg_Divergence', False):
                climax_html = '<span style="color: #e74c3c; font-weight: bold;">⚠️ CLIMAX+DIV</span>'
            else:
                climax_html = '<span style="color: #e67e22;">⚠️ CLIMAX</span>'
        elif row.get('Has_Pos_Divergence', False):
            climax_html = '<span style="color: #27ae60;">↗️ POS DIV</span>'
        elif row.get('Has_Neg_Divergence', False):
            climax_html = '<span style="color: #e74c3c;">↘️ NEG DIV</span>'
        else:
            climax_html = '-'
        
        html_content += f"""
            <tr>
                <td style="font-weight: bold;">{row['Ticker']}</td>
                <td>{row['Sector']}</td>
                <td><span class="{prob_class}">{row['Probability_Score']:.0f}</span></td>
                <td><span class="{vsr_class}">{row['VSR_Ratio']:.2f}x</span></td>
                <td>{row['VSR_Surges_10H']} / {row['VSR_Surges_20H']}</td>
                <td>{row['Pattern']}</td>
                <td>{climax_html}</td>
                <td>₹{row['Entry_Price']:.2f}</td>
                <td>₹{row['Stop_Loss']:.2f}</td>
                <td>₹{row['Target1']:.2f}</td>
                <td class="{momentum_class}">{row['Momentum_10H']:.1f}%</td>
            </tr>
        """

    html_content += """
            </tbody>
        </table>
    """

    # Add detailed analysis section
    html_content += "<h2>📈 Detailed Analysis</h2>"
    
    # Group by pattern type
    pattern_groups = filtered_df.groupby('Pattern')
    
    for pattern, group_df in pattern_groups:
        pattern_emoji = "🔥" if "Extreme" in pattern else "📈" if "Momentum" in pattern else "👀"
        html_content += f"""
        <h3>{pattern_emoji} {pattern.replace('_', ' ')} ({len(group_df)} stocks)</h3>
        <div style="margin-bottom: 30px;">
        """
        
        for idx, row in group_df.iterrows():
            html_content += f"""
            <div style="background: white; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #9b59b6;">
                <h4 style="margin: 0 0 10px 0; color: #2c3e50;">{row['Ticker']} - {row['Sector']}</h4>
                <p style="margin: 5px 0; color: #7f8c8d; font-style: italic;">"{row['Description']}"</p>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 15px;">
                    <div>
                        <strong>VSR Analysis:</strong><br>
                        Ratio: {row['VSR_Ratio']:.2f}x<br>
                        ROC: {row['VSR_ROC']:.1f}%<br>
                        Avg: {row['Avg_VSR_Ratio']:.2f}x
                    </div>
                    <div>
                        <strong>Momentum:</strong><br>
                        5H: {row['Momentum_5H']:.1f}%<br>
                        10H: {row['Momentum_10H']:.1f}%<br>
                        20H: {row['Momentum_20H']:.1f}%
                    </div>
                    <div>
                        <strong>Trading Levels:</strong><br>
                        Entry: ₹{row['Entry_Price']:.2f}<br>
                        Stop: ₹{row['Stop_Loss']:.2f}<br>
                        Risk: ₹{row['Risk']:.2f}
                    </div>
                    <div>
                        <strong>Scores:</strong><br>
                        VSR: {row['VSR_Score']}<br>
                        Momentum: {row['Momentum_Score']}<br>
                        Climax: {row['Climax_Score']}<br>
                        Overall: {row['Probability_Score']:.0f}/100
                    </div>
                </div>"""
            
            # Add climax warning if applicable
            if row.get('Buying_Climax_10H', 0) > 0 or row.get('Selling_Climax_10H', 0) > 0:
                climax_type = "Buying" if row.get('Buying_Climax_10H', 0) > 0 else "Selling"
                climax_count = row.get('Buying_Climax_10H', 0) if climax_type == "Buying" else row.get('Selling_Climax_10H', 0)
                divergence_text = ""
                if row.get('Has_Pos_Divergence', False):
                    divergence_text = " with POSITIVE DIVERGENCE"
                elif row.get('Has_Neg_Divergence', False):
                    divergence_text = " with NEGATIVE DIVERGENCE"
                
                html_content += f"""
                <div style="background: #ffe6e6; padding: 10px; margin-top: 10px; border-radius: 5px; border: 1px solid #ffcccc;">
                    <strong style="color: #d9534f;">⚠️ CLIMAX WARNING:</strong> {climax_count} {climax_type} Climax event(s) detected in last 10 hours{divergence_text}.
                    {' EXTREME CAUTION - Potential reversal zone!' if divergence_text else ' Monitor closely for potential exhaustion.'}
                </div>"""
            elif row.get('Has_Pos_Divergence', False) or row.get('Has_Neg_Divergence', False):
                div_type = "Positive" if row.get('Has_Pos_Divergence', False) else "Negative"
                div_color = "#5cb85c" if div_type == "Positive" else "#d9534f"
                html_content += f"""
                <div style="background: #f0f8ff; padding: 10px; margin-top: 10px; border-radius: 5px; border: 1px solid #d0e0ff;">
                    <strong style="color: {div_color};">📊 DIVERGENCE:</strong> {div_type} divergence detected between price and VSR.
                    {' Potential accumulation phase.' if div_type == "Positive" else ' Potential distribution phase.'}
                </div>"""
            
            html_content += """
            </div>
            """
        
        html_content += "</div>"

    # Complete HTML
    html_content += f"""
        <div class="source-info">
            <p>Generated on {formatted_date} at {formatted_time} | VSR Momentum Scanner with Climax Detection</p>
            <p><strong>Note:</strong> VSR analysis identifies stocks with expanding volume-spread momentum on hourly timeframe.</p>
            <p><strong>Climax Detection:</strong> Buying/Selling climaxes indicate extreme volume and spread, often marking potential reversals.</p>
            <p><strong>Divergences:</strong> Price-VSR divergences can signal accumulation (positive) or distribution (negative) phases.</p>
            <p><strong>Risk Management:</strong> Use proper position sizing. Higher VSR ratios indicate stronger momentum but also higher volatility. Extra caution with climax signals!</p>
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
    """Main function to scan for VSR momentum patterns"""
    logger.info("Starting VSR Momentum Scanner with hourly data")
    
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
        excel_file = os.path.join(RESULTS_DIR, f"VSR_{formatted_date}_{formatted_time}.xlsx")
        html_file = os.path.join(HTML_DIR, f"VSR_{formatted_date}_{formatted_time}.html")
        
        if results:
            # Convert to DataFrame
            results_df = pd.DataFrame(results)
            
            # Sort by Probability Score (descending) - highest probability first
            results_df = results_df.sort_values(by=['Probability_Score', 'VSR_Ratio'], ascending=[False, False])
            
            # Round numeric columns for better readability
            numeric_cols = ['Entry_Price', 'Stop_Loss', 'Target1', 'Target2', 'Risk', 'Risk_Reward_Ratio', 
                          'VSR_Ratio', 'VSR_ROC', 'Volume_Ratio', 'Spread_Pct', 'Avg_VSR_Ratio', 'Max_VSR_Ratio',
                          'ATR', 'ATR_Pct', 'Momentum_5H', 'Momentum_10H', 'Momentum_20H', 'KC_Distance_%', 
                          'Probability_Score']
            for col in numeric_cols:
                if col in results_df.columns:
                    results_df[col] = results_df[col].astype(float).round(2)
            
            # Reorder columns to put important ones first
            priority_cols = ['Ticker', 'Sector', 'Pattern', 'Direction', 'Probability_Score', 
                           'VSR_Ratio', 'VSR_ROC', 'VSR_Surges_10H', 'VSR_Surges_20H',
                           'Volume_Ratio', 'Spread_Pct', 
                           'Entry_Price', 'Stop_Loss', 'Target1', 'Target2', 'Risk', 'Risk_Reward_Ratio']
            # Only include columns that actually exist
            existing_priority_cols = [col for col in priority_cols if col in results_df.columns]
            other_cols = [col for col in results_df.columns if col not in existing_priority_cols]
            results_df = results_df[existing_priority_cols + other_cols]
            
            # Write to Excel
            results_df.to_excel(excel_file, index=False)
            logger.info(f"Successfully wrote {len(results_df)} filtered tickers to {excel_file}")
            
            # Generate HTML report
            html_output = generate_html_report(results_df, html_file)
            logger.info(f"Generated HTML report at {html_output}")
            
            # Open the HTML report in the default browser
            try:
                webbrowser.open('file://' + os.path.abspath(html_output))
                logger.info(f"Opened HTML report in browser")
            except Exception as e:
                logger.warning(f"Could not open browser automatically: {e}")
            
            # Print summary to console
            print("\n===== VSR Momentum Opportunities =====")
            print(f"Found {len(results_df)} stocks with momentum patterns")
            
            # Separate by pattern type
            extreme_patterns = results_df[results_df['Pattern'].str.contains('Extreme')]
            high_vsr = results_df[results_df['VSR_Ratio'] >= 2.0]
            high_prob = results_df[results_df['Probability_Score'] >= 70]
            
            if len(extreme_patterns) > 0:
                print(f"\n🔥 EXTREME VSR PATTERNS ({len(extreme_patterns)} stocks):")
                for idx, row in extreme_patterns.head(5).iterrows():
                    print(f"  {row['Ticker']} ({row['Sector']}): VSR {row['VSR_Ratio']:.1f}x, "
                          f"Score {row['Probability_Score']:.0f}, Entry ₹{row['Entry_Price']:.2f}")
            
            if len(high_vsr) > 0:
                print(f"\n📈 HIGH VSR MOMENTUM ({len(high_vsr)} stocks with VSR >= 2.0x):")
                for idx, row in high_vsr.head(5).iterrows():
                    print(f"  {row['Ticker']} ({row['Sector']}): VSR {row['VSR_Ratio']:.1f}x, "
                          f"Surges {row['VSR_Surges_10H']}/10h, Momentum {row['Momentum_10H']:.1f}%")
            
            # Print sector summary
            sector_counts = results_df['Sector'].value_counts()
            print("\nSector Distribution:")
            for sector, count in sector_counts.head(5).items():
                print(f"  {sector}: {count} stocks")
            
            print("\nTop 10 momentum opportunities:")
            for idx, row in results_df.head(10).iterrows():
                print(f"{idx+1:2d}. {row['Ticker']:12s} ({row['Sector'][:15]:15s}): "
                      f"VSR {row['VSR_Ratio']:4.1f}x, Score {row['Probability_Score']:3.0f}, "
                      f"Pattern: {row['Pattern']}")

            print(f"\nDetailed results saved to: {excel_file}")
            print(f"HTML report: {html_file}")
        else:
            # Create empty Excel with columns
            empty_cols = ['Ticker', 'Sector', 'Pattern', 'Direction', 'Probability_Score', 
                          'VSR_Ratio', 'VSR_ROC', 'Volume_Ratio', 'Spread_Pct',
                          'Base_Score', 'VSR_Score', 'Momentum_Score', 'Advanced_Score',
                          'VSR_Surges_10H', 'VSR_Surges_20H', 'Avg_VSR_Ratio', 'Max_VSR_Ratio',
                          'Accumulation_Count', 'HH_Count',
                          'Entry_Price', 'Stop_Loss', 'Target1', 'Target2', 'Risk', 'Risk_Reward_Ratio',
                          'ATR', 'ATR_Pct', 'Momentum_5H', 'Momentum_10H', 'Momentum_20H', 
                          'KC_Distance_%', 'Description']
            pd.DataFrame(columns=empty_cols).to_excel(excel_file, index=False)
            
            logger.info(f"No VSR momentum patterns found. Empty file created at {excel_file}")
            print("\nNo VSR momentum patterns found in current market conditions.")
            print(f"Empty results saved to: {excel_file}")
            
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
    print("\n=====================================")
    print("VSR Momentum Scanner")
    print("=====================================")
    print("Volume Spread Ratio Analysis:")
    print("- Hourly timeframe for early detection")
    print("- VSR = Volume × Price Spread")
    print("- Identifies momentum expansion")
    print("- Combines with trend alignment")
    print("- Detects accumulation patterns")
    print("=====================================")
    print(f"Using credentials for user: {user_name}")
    print("=====================================\n")

    sys.exit(main())