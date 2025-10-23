#!/usr/bin/env python
# Institutional_Accumulation_Daily.py - Filter stocks based on institutional accumulation patterns:
# 1. Repeated up-days with high volume (1.5x to 2x average daily volume)
# 2. Price closes near the high on high volume days
# 3. Multiple green candles suggesting quiet institutional buying

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

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "institutional_accumulation_daily.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Institutional Accumulation Daily Analysis")
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
RESULTS_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "reports")  # Changed to reports as requested
HTML_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "reports")

# Ensure directories exist
for dir_path in [RESULTS_DIR, HTML_DIR]:
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
# Calculate Indicators for Institutional Accumulation
# -----------------------------
def calculate_indicators(daily_data):
    """Calculate indicators for institutional accumulation pattern detection (all 8 patterns)"""
    if daily_data.empty or len(daily_data) < 50:
        logger.warning(f"Insufficient data points for {daily_data['Ticker'].iloc[0] if not daily_data.empty else 'unknown ticker'}")
        return None
        
    # Create a copy to avoid SettingWithCopyWarning
    df = daily_data.copy()
    
    # 1. Volume indicators for Pattern 1 (Repeated Up-Days on Volume)
    df['AvgVolume20'] = df['Volume'].rolling(window=20).mean()
    df['VolumeRatio'] = df['Volume'] / df['AvgVolume20']
    
    # Calculate where close is relative to the range
    df['Range'] = df['High'] - df['Low']
    df['ClosePosition'] = (df['Close'] - df['Low']) / df['Range']
    df['ClosePosition'] = df['ClosePosition'].fillna(0.5)  # Handle zero range bars
    
    # Identify up/down days
    df['IsUpDay'] = df['Close'] > df['Open']
    df['IsDownDay'] = df['Close'] < df['Open']
    df['IsGreenClose'] = df['Close'] > df['Close'].shift(1)
    
    # 2. For Pattern 2 (Quiet Pullbacks) - track down day volumes
    df['DownDayVolume'] = df['Volume'].where(df['IsDownDay'], np.nan)
    df['UpDayVolume'] = df['Volume'].where(df['IsUpDay'], np.nan)
    
    # Calculate body size
    df['Body'] = abs(df['Close'] - df['Open'])
    df['BodyPercent'] = (df['Body'] / df['Range']) * 100
    df['BodyPercent'] = df['BodyPercent'].fillna(0)
    
    # Calculate price change
    df['PriceChange'] = ((df['Close'] - df['Close'].shift(1)) / df['Close'].shift(1)) * 100
    
    # 3. For Pattern 3 (Tight Trading Ranges) - calculate range volatility
    df['ATR'] = df['Range'].rolling(window=14).mean()
    df['RangeRatio'] = df['Range'] / df['ATR']  # Lower = tighter range
    df['TightRange'] = df['RangeRatio'] < 0.7  # Flag tight range days
    
    # 4. For Pattern 4 (Higher Lows) - track swing lows
    df['SwingLow'] = df['Low'].rolling(window=5).min()
    df['PrevSwingLow'] = df['SwingLow'].shift(5)
    df['HigherLow'] = df['SwingLow'] > df['PrevSwingLow']
    
    # Count consecutive higher lows
    df['HigherLowStreak'] = 0
    streak = 0
    for i in range(len(df)):
        if i > 0:
            if df.iloc[i]['HigherLow']:
                streak += 1
            else:
                streak = 0
            df.iloc[i, df.columns.get_loc('HigherLowStreak')] = streak
    
    # Calculate trend using SMAs FIRST (moved up)
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    
    # 5. For Pattern 5 (Relative Strength) - calculate RS vs market
    # We'll use SMA50 as proxy for market trend
    df['RS'] = df['Close'] / df['SMA50'].rolling(window=20).mean()
    df['RS_Trend'] = df['RS'].rolling(window=10).mean()
    df['RS_Improving'] = df['RS'] > df['RS_Trend']
    
    # 6. For Pattern 6 (EMA Support) - calculate EMAs
    df['EMA8'] = df['Close'].ewm(span=8, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    
    # Check if price bounces off EMAs
    df['NearEMA8'] = abs(df['Low'] - df['EMA8']) / df['EMA8'] < 0.01  # Within 1%
    df['NearEMA21'] = abs(df['Low'] - df['EMA21']) / df['EMA21'] < 0.015  # Within 1.5%
    df['BouncedEMA8'] = df['NearEMA8'] & (df['Close'] > df['EMA8'])
    df['BouncedEMA21'] = df['NearEMA21'] & (df['Close'] > df['EMA21'])
    
    # 7. For Pattern 7 (Volume Dry-ups at Lows) - identify low volume at support
    df['LowVolume'] = df['Volume'] < df['AvgVolume20'] * 0.6  # 60% below average
    df['AtSupport'] = df['Low'] <= df['Low'].rolling(window=10).min() * 1.02  # Near 10-day low
    df['VolumeDryUp'] = df['LowVolume'] & df['AtSupport']
    
    # Calculate cumulative volume for trend analysis
    df['CumVolume3'] = df['Volume'].rolling(window=3).sum()
    df['CumVolume5'] = df['Volume'].rolling(window=5).sum()
    df['CumVolume10'] = df['Volume'].rolling(window=10).sum()
    
    # Calculate average cumulative volume
    df['AvgCumVolume3'] = df['CumVolume3'].rolling(window=20).mean()
    df['AvgCumVolume5'] = df['CumVolume5'].rolling(window=20).mean()
    df['AvgCumVolume10'] = df['CumVolume10'].rolling(window=20).mean()
    
    # Volume accumulation ratios
    df['VolumeAccum3'] = df['CumVolume3'] / df['AvgCumVolume3']
    df['VolumeAccum5'] = df['CumVolume5'] / df['AvgCumVolume5']
    df['VolumeAccum10'] = df['CumVolume10'] / df['AvgCumVolume10']
    
    # Price strength relative to moving averages (SMAs already calculated above)
    df['PriceAboveSMA20'] = df['Close'] > df['SMA20']
    df['PriceAboveSMA50'] = df['Close'] > df['SMA50']
    df['PriceAboveSMA200'] = df['Close'] > df['SMA200']
    
    return df

# -----------------------------
# Institutional Accumulation Pattern Detection
# -----------------------------
def detect_institutional_accumulation(data):
    """
    Detect institutional accumulation patterns based on:
    1. Repeated up-days on high volume
    2. Price closes near the high on volume days
    3. Multiple green candles suggesting quiet buying
    
    Returns a dictionary with pattern details if found, None otherwise
    """
    if data is None or data.empty or len(data) < 20:
        return None

    # Analyze last 10 trading days for accumulation patterns
    last_10_bars = data.tail(10)
    last_5_bars = data.tail(5)
    last_3_bars = data.tail(3)
    last_bar = data.iloc[-1]
    
    # Check for accumulation patterns
    accumulation_pattern = detect_accumulation_pattern(data, last_10_bars, last_5_bars, last_3_bars, last_bar)
    if accumulation_pattern:
        return accumulation_pattern
    
    return None

def detect_accumulation_pattern(data, last_10_bars, last_5_bars, last_3_bars, last_bar):
    """Detect all 8 institutional accumulation patterns with comprehensive scoring"""
    
    # Pattern 1: Repeated Up-Days on Volume
    up_days_10 = last_10_bars['IsUpDay'].sum()
    up_days_5 = last_5_bars['IsUpDay'].sum()
    up_day_volume_ratios = last_10_bars[last_10_bars['IsUpDay']]['VolumeRatio']
    high_volume_up_days = (up_day_volume_ratios >= 1.5).sum() if len(up_day_volume_ratios) > 0 else 0
    up_day_close_positions = last_10_bars[last_10_bars['IsUpDay']]['ClosePosition']
    closes_near_high = (up_day_close_positions >= 0.7).sum() if len(up_day_close_positions) > 0 else 0
    
    pattern1_score = 0
    if up_days_10 >= 6: pattern1_score += 1
    if high_volume_up_days >= 3: pattern1_score += 1
    if closes_near_high >= 3: pattern1_score += 1
    
    # Pattern 2: Quiet Pullbacks (down days with low volume)
    down_days_data = last_10_bars[last_10_bars['IsDownDay']]
    up_days_data = last_10_bars[last_10_bars['IsUpDay']]
    
    if len(down_days_data) > 0 and len(up_days_data) > 0:
        avg_down_volume = down_days_data['VolumeRatio'].mean()
        avg_up_volume = up_days_data['VolumeRatio'].mean()
        quiet_pullbacks = avg_down_volume < 0.8 and avg_up_volume > 1.2  # Down days quieter than up days
    else:
        quiet_pullbacks = False
        avg_down_volume = 1
        avg_up_volume = 1
    
    pattern2_score = 1 if quiet_pullbacks else 0
    
    # Pattern 3: Tight Trading Ranges (narrow range after rally)
    tight_range_days = last_5_bars['TightRange'].sum()
    recent_rally = last_10_bars['PriceChange'].sum() > 5  # 5% rally in 10 days
    tight_consolidation = tight_range_days >= 3 and recent_rally
    
    pattern3_score = 1 if tight_consolidation else 0
    
    # Pattern 4: Higher Lows (staircase pattern)
    higher_low_streak = last_bar['HigherLowStreak']
    pattern4_score = 0
    if higher_low_streak >= 2: pattern4_score += 0.5
    if higher_low_streak >= 3: pattern4_score += 0.5
    
    # Pattern 5: Strong Relative Strength
    rs_improving = last_5_bars['RS_Improving'].sum() >= 4
    price_above_ma = last_bar['PriceAboveSMA50'] and last_bar['PriceAboveSMA20']
    pattern5_score = 0
    if rs_improving: pattern5_score += 0.5
    if price_above_ma: pattern5_score += 0.5
    
    # Pattern 6: Support at Key EMAs
    ema_bounces = last_5_bars['BouncedEMA8'].sum() + last_5_bars['BouncedEMA21'].sum()
    pattern6_score = 0
    if ema_bounces >= 2: pattern6_score += 0.5
    if ema_bounces >= 3: pattern6_score += 0.5
    
    # Pattern 7: Volume Dry-ups at Lows
    volume_dryups = last_5_bars['VolumeDryUp'].sum()
    pattern7_score = 1 if volume_dryups >= 2 else 0
    
    # Pattern 8: Sector Strength (will be calculated separately with sector data)
    # For now, we'll check if the stock is in a strong trend
    strong_trend = (last_bar['PriceAboveSMA20'] and 
                   last_bar['PriceAboveSMA50'] and 
                   last_bar['PriceAboveSMA200'])
    pattern8_score = 1 if strong_trend else 0
    
    # Additional scoring factors
    volume_accumulation_trend = (
        last_bar['VolumeAccum3'] > 1.2 or
        last_bar['VolumeAccum5'] > 1.3 or
        last_bar['VolumeAccum10'] > 1.4
    )
    recent_price_gain = last_5_bars['PriceChange'].sum()
    up_day_body_percent = last_10_bars[last_10_bars['IsUpDay']]['BodyPercent'].mean() if len(up_days_data) > 0 else 0
    
    # Calculate total score
    total_score = (pattern1_score + pattern2_score + pattern3_score + 
                  pattern4_score + pattern5_score + pattern6_score + 
                  pattern7_score + pattern8_score)
    
    # Detailed conditions dictionary
    conditions = {
        'pattern1_updays_volume': pattern1_score,
        'pattern2_quiet_pullbacks': pattern2_score,
        'pattern3_tight_ranges': pattern3_score,
        'pattern4_higher_lows': pattern4_score,
        'pattern5_relative_strength': pattern5_score,
        'pattern6_ema_support': pattern6_score,
        'pattern7_volume_dryups': pattern7_score,
        'pattern8_strong_trend': pattern8_score,
        'volume_accumulation': volume_accumulation_trend,
        'recent_strength': recent_price_gain > 2
    }
    
    # Need at least 5 out of 10 total score for accumulation pattern
    if total_score >= 5:
        # Calculate entry and stop loss
        entry_price = last_bar['Close']
        
        # Stop loss at recent swing low or 2% below entry
        recent_low = last_10_bars['Low'].min()
        percent_stop = entry_price * 0.98
        stop_loss = min(recent_low, percent_stop)
        
        # Targets based on accumulation strength
        risk = entry_price - stop_loss
        target1 = entry_price + (2 * risk)  # 1:2 risk-reward
        target2 = entry_price + (3 * risk)  # 1:3 risk-reward
        target3 = entry_price + (5 * risk)  # 1:5 risk-reward (for strong accumulation)
        
        # Calculate risk-reward ratio
        if risk > 0:
            risk_reward_ratio = abs(target1 - entry_price) / risk
        else:
            risk_reward_ratio = 0
        
        return {
            'pattern': 'Institutional_Accumulation',
            'description': f'Accumulation Score: {total_score:.1f}/10 | {up_days_10}/10 up-days | {high_volume_up_days} high vol days',
            'direction': 'LONG',
            'score': total_score,
            'max_score': 10,
            'pattern_scores': {
                'P1_UpDays_Volume': pattern1_score,
                'P2_Quiet_Pullbacks': pattern2_score,
                'P3_Tight_Ranges': pattern3_score,
                'P4_Higher_Lows': pattern4_score,
                'P5_Relative_Strength': pattern5_score,
                'P6_EMA_Support': pattern6_score,
                'P7_Volume_DryUps': pattern7_score,
                'P8_Strong_Trend': pattern8_score
            },
            'conditions_met': conditions,
            'up_days_10': up_days_10,
            'up_days_5': up_days_5,
            'high_volume_up_days': high_volume_up_days,
            'closes_near_high': closes_near_high,
            'avg_up_volume_ratio': avg_up_volume if avg_up_volume else 0,
            'avg_down_volume_ratio': avg_down_volume if avg_down_volume else 0,
            'quiet_pullbacks': quiet_pullbacks,
            'tight_range_days': tight_range_days,
            'higher_low_streak': higher_low_streak,
            'ema_bounces': ema_bounces,
            'volume_dryups': volume_dryups,
            'recent_price_gain': recent_price_gain,
            'volume_accum_3d': last_bar['VolumeAccum3'],
            'volume_accum_5d': last_bar['VolumeAccum5'],
            'volume_accum_10d': last_bar['VolumeAccum10'],
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'target1': target1,
            'target2': target2,
            'target3': target3,
            'risk': risk,
            'risk_reward_ratio': risk_reward_ratio,
            'current_volume_ratio': last_bar['VolumeRatio']
        }
    
    return None

# -----------------------------
# Process Single Ticker
# -----------------------------
def process_ticker(ticker):
    """Process a single ticker for institutional accumulation patterns"""
    logger.info(f"Processing {ticker}")
    
    try:
        now = datetime.datetime.now()
        
        # Extended date range for better pattern recognition
        from_date_daily = (now - relativedelta(months=3)).strftime('%Y-%m-%d')
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
            
        # Detect institutional accumulation pattern
        accumulation_pattern = detect_institutional_accumulation(daily_with_indicators)
        
        if accumulation_pattern is None:
            logger.info(f"{ticker} - No institutional accumulation pattern detected")
            return None
        
        # Get sector information
        sector = get_sector_for_ticker(ticker)
        
        # Log the findings
        logger.info(f"{ticker} - Institutional Accumulation Detected!")
        logger.info(f"{ticker} - Pattern Score: {accumulation_pattern['score']}/{accumulation_pattern['max_score']}")
        logger.info(f"{ticker} - Up Days: {accumulation_pattern['up_days_10']}/10, High Volume Days: {accumulation_pattern['high_volume_up_days']}")
        logger.info(f"{ticker} - Entry: {accumulation_pattern['entry_price']:.2f}, Stop: {accumulation_pattern['stop_loss']:.2f}")
        logger.info(f"{ticker} - Sector: {sector}")
        
        # Prepare result with all pattern scores
        pattern_scores = accumulation_pattern['pattern_scores']
        result = {
            'Ticker': ticker,
            'Sector': sector,
            'Pattern': accumulation_pattern['pattern'],
            'Direction': accumulation_pattern['direction'],
            'Score': accumulation_pattern['score'],  # Keep as numeric for calculations
            'Score_Text': f"{accumulation_pattern['score']:.1f}/{accumulation_pattern['max_score']}",
            # Individual pattern scores
            'P1_UpDays_Vol': pattern_scores['P1_UpDays_Volume'],
            'P2_Quiet_Pull': pattern_scores['P2_Quiet_Pullbacks'],
            'P3_Tight_Range': pattern_scores['P3_Tight_Ranges'],
            'P4_Higher_Lows': pattern_scores['P4_Higher_Lows'],
            'P5_Rel_Strength': pattern_scores['P5_Relative_Strength'],
            'P6_EMA_Support': pattern_scores['P6_EMA_Support'],
            'P7_Vol_DryUp': pattern_scores['P7_Volume_DryUps'],
            'P8_Trend': pattern_scores['P8_Strong_Trend'],
            # Detailed metrics
            'Up_Days_10': accumulation_pattern['up_days_10'],
            'Up_Days_5': accumulation_pattern['up_days_5'],
            'High_Volume_Days': accumulation_pattern['high_volume_up_days'],
            'Closes_Near_High': accumulation_pattern['closes_near_high'],
            'Quiet_Pullbacks': 'Yes' if accumulation_pattern['quiet_pullbacks'] else 'No',
            'Tight_Range_Days': accumulation_pattern['tight_range_days'],
            'Higher_Low_Streak': accumulation_pattern['higher_low_streak'],
            'EMA_Bounces': accumulation_pattern['ema_bounces'],
            'Volume_DryUps': accumulation_pattern['volume_dryups'],
            'Avg_Up_Volume': f"{accumulation_pattern['avg_up_volume_ratio']:.2f}x",
            'Avg_Down_Volume': f"{accumulation_pattern['avg_down_volume_ratio']:.2f}x",
            'Recent_Gain_%': f"{accumulation_pattern['recent_price_gain']:.2f}",
            'Volume_Accum_3D': f"{accumulation_pattern['volume_accum_3d']:.2f}x",
            'Volume_Accum_5D': f"{accumulation_pattern['volume_accum_5d']:.2f}x",
            'Entry_Price': accumulation_pattern['entry_price'],
            'Stop_Loss': accumulation_pattern['stop_loss'],
            'Target1': accumulation_pattern['target1'],
            'Target2': accumulation_pattern['target2'],
            'Target3': accumulation_pattern['target3'],
            'Risk': accumulation_pattern['risk'],
            'Risk_Reward_Ratio': accumulation_pattern['risk_reward_ratio'],
            'Description': accumulation_pattern['description']
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing {ticker}: {e}")
        return None

# -----------------------------
# Read Ticker File with Sector Information
# -----------------------------
def read_ticker_file():
    """Read tickers from the Ticker_with_Sector Excel file"""
    ticker_file = os.path.join(DATA_DIR, "Ticker_with_Sector.xlsx")
    
    try:
        if not os.path.exists(ticker_file):
            logger.error(f"Ticker file not found: {ticker_file}")
            # Fallback to regular Ticker.xlsx
            ticker_file = os.path.join(DATA_DIR, "Ticker.xlsx")
            if os.path.exists(ticker_file):
                logger.info(f"Using fallback ticker file: {ticker_file}")
                df = pd.read_excel(ticker_file, sheet_name="Ticker")
                tickers = df['Ticker'].dropna().tolist()
                logger.info(f"Read {len(tickers)} tickers from {ticker_file}")
                return tickers
            return []
        
        df = pd.read_excel(ticker_file)
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
        <title>Institutional Accumulation Daily - {formatted_date}</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1600px;
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
            .ticker-card {{
                background-color: white;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 15px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                border-left: 5px solid #3498db;
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
                background-color: #27ae60;
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
                background-color: #e8f4fd;
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
            .accumulation-indicator {{
                background-color: #f39c12;
                color: white;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 0.85em;
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
                background-color: #3498db;
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
            .accumulation-summary {{
                background-color: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 8px;
                padding: 15px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <h1>🏦 Institutional Accumulation Daily Scanner</h1>
        <div class="header-info">
            <div>Date: {formatted_date} | Time: {formatted_time}</div>
            <div>Filtered from: Ticker.xlsx | Accumulation Patterns Only</div>
        </div>

        <div class="accumulation-summary">
            <h3>🎯 What This Scanner Detects:</h3>
            <ul>
                <li><strong>Repeated Up-Days:</strong> Multiple green candles where price closes near the high</li>
                <li><strong>Volume Expansion:</strong> 1.5x to 2x average daily volume on up-days</li>
                <li><strong>Quiet Accumulation:</strong> Institutions buying in pieces over multiple days</li>
                <li><strong>Price Strength:</strong> Closes near highs showing buying pressure</li>
            </ul>
        </div>

        <h2>Institutional Accumulation Patterns ({len(filtered_df)} matches)</h2>
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

    # Add table view
    html_content += """
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Sector</th>
                    <th>Score</th>
                    <th>Up Days (10D)</th>
                    <th>High Vol Days</th>
                    <th>Avg Up Vol</th>
                    <th>Recent Gain</th>
                    <th>Entry Price</th>
                    <th>Stop Loss</th>
                    <th>Target 1</th>
                    <th>Risk:Reward</th>
                </tr>
            </thead>
            <tbody>
    """

    # Add rows for each ticker
    for idx, row in filtered_df.iterrows():
        html_content += f"""
            <tr>
                <td><strong>{row['Ticker']}</strong></td>
                <td><span class="sector-badge">{row['Sector']}</span></td>
                <td>{row['Score']}</td>
                <td>{row['Up_Days_10']}/10</td>
                <td>{row['High_Volume_Days']}</td>
                <td>{row['Avg_Up_Volume']}</td>
                <td>{row['Recent_Gain_%']}%</td>
                <td>₹{row['Entry_Price']:.2f}</td>
                <td>₹{row['Stop_Loss']:.2f}</td>
                <td>₹{row['Target1']:.2f}</td>
                <td>{row['Risk_Reward_Ratio']:.2f}</td>
            </tr>
        """

    html_content += """
            </tbody>
        </table>
    """

    # Add detailed cards for each ticker
    html_content += "<h2>Detailed Analysis</h2>"
    
    for idx, row in filtered_df.iterrows():
        html_content += f"""
        <div class="ticker-card">
            <div class="ticker-header">
                <div class="ticker-name">
                    {row['Ticker']}
                    <span class="sector-badge">{row['Sector']}</span>
                    <span class="accumulation-indicator">Accumulation Pattern</span>
                </div>
                <div>
                    <span class="ticker-direction">LONG</span>
                    <span class="score-badge">Score: {row['Score']}</span>
                </div>
            </div>
            
            <div class="ticker-details">
                <div class="detail-item">
                    <div class="detail-label">Up Days (10D/5D)</div>
                    <div class="detail-value">{row['Up_Days_10']}/10, {row['Up_Days_5']}/5</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">High Volume Days</div>
                    <div class="detail-value">{row['High_Volume_Days']} days</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Closes Near High</div>
                    <div class="detail-value">{row['Closes_Near_High']} days</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Avg Up Day Volume</div>
                    <div class="detail-value">{row['Avg_Up_Volume']}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Avg Down Day Volume</div>
                    <div class="detail-value">{row['Avg_Down_Volume']}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Recent Gain (5D)</div>
                    <div class="detail-value">{row['Recent_Gain_%']}%</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Volume Accum (3D/5D/10D)</div>
                    <div class="detail-value">{row['Volume_Accum_3D']}/{row['Volume_Accum_5D']}/{row['Volume_Accum_5D']}</div>
                </div>
                
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
                    <div class="detail-label">Target 3 (1:5)</div>
                    <div class="detail-value">₹{row['Target3']:.2f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Risk Amount</div>
                    <div class="detail-value">₹{row['Risk']:.2f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Risk:Reward</div>
                    <div class="detail-value">{row['Risk_Reward_Ratio']:.2f}</div>
                </div>
            </div>
            
            <div class="pattern-info">
                <strong>Pattern:</strong> {row['Description']}
            </div>
        </div>
        """

    # Complete HTML
    html_content += f"""
        <div class="source-info">
            <p>Generated on {formatted_date} at {formatted_time} | Institutional Accumulation Daily Scanner</p>
            <p><strong>Note:</strong> These patterns indicate potential institutional accumulation based on volume and price action analysis.</p>
            <p>Look for stocks with 6+ up-days in 10 trading days with volume expansion for best results.</p>
        </div>
    </body>
    </html>
    """

    # Write HTML file
    with open(output_file, 'w') as f:
        f.write(html_content)

    return output_file

# -----------------------------
# Sector Cluster Analysis
# -----------------------------
def analyze_sector_clusters(results_df):
    """Analyze sector clusters for Pattern 8: Cluster of Breakouts in a Sector"""
    if results_df.empty:
        return {}
    
    # Count stocks per sector
    sector_counts = results_df['Sector'].value_counts()
    
    # Calculate average score per sector
    sector_scores = results_df.groupby('Sector')['Score'].mean()
    
    # Identify hot sectors (3+ stocks with accumulation)
    hot_sectors = sector_counts[sector_counts >= 3].index.tolist()
    
    # Create sector strength dictionary
    sector_strength = {}
    for sector in sector_counts.index:
        count = sector_counts[sector]
        avg_score = sector_scores[sector]
        is_hot = sector in hot_sectors
        
        sector_strength[sector] = {
            'count': count,
            'avg_score': avg_score,
            'is_hot': is_hot,
            'strength_rating': 'Strong' if is_hot and avg_score >= 6 else 'Moderate' if count >= 2 else 'Weak'
        }
    
    return sector_strength

# -----------------------------
# Main Function
# -----------------------------
def main():
    """Main function to filter tickers for institutional accumulation patterns"""
    logger.info("Starting Institutional Accumulation Daily Scanner")
    
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
        excel_file = os.path.join(RESULTS_DIR, f"Institutional_Accumulation_{formatted_date}_{formatted_time}.xlsx")
        html_file = os.path.join(HTML_DIR, f"Institutional_Accumulation_{formatted_date}_{formatted_time.replace('_', '-')}.html")
        
        if results:
            # Convert to DataFrame
            results_df = pd.DataFrame(results)
            
            # Perform sector cluster analysis
            sector_strength = analyze_sector_clusters(results_df)
            
            # Add sector strength bonus to stocks in hot sectors
            for idx, row in results_df.iterrows():
                sector = row['Sector']
                if sector in sector_strength and sector_strength[sector]['is_hot']:
                    # Add bonus score for being in a hot sector (Pattern 8)
                    results_df.at[idx, 'Sector_Bonus'] = 1
                    results_df.at[idx, 'Final_Score'] = row['Score'] + 1
                    results_df.at[idx, 'Sector_Strength'] = sector_strength[sector]['strength_rating']
                else:
                    results_df.at[idx, 'Sector_Bonus'] = 0
                    results_df.at[idx, 'Final_Score'] = row['Score']
                    results_df.at[idx, 'Sector_Strength'] = sector_strength.get(sector, {}).get('strength_rating', 'Weak')
            
            # Sort by Final Score (descending) then by Up Days (descending)
            results_df = results_df.sort_values(by=['Final_Score', 'Score', 'Up_Days_10', 'High_Volume_Days'], ascending=[False, False, False, False])
            
            # Round numeric columns for better readability
            numeric_cols = ['Entry_Price', 'Stop_Loss', 'Target1', 'Target2', 'Target3', 'Risk', 'Risk_Reward_Ratio']
            for col in numeric_cols:
                if col in results_df.columns:
                    results_df[col] = results_df[col].astype(float).round(2)
            
            # Write to Excel
            results_df.to_excel(excel_file, index=False)
            logger.info(f"Successfully wrote {len(results_df)} filtered tickers to {excel_file}")
            
            # Generate HTML report
            html_output = generate_html_report(results_df, html_file, "Ticker.xlsx")
            logger.info(f"Generated HTML report at {html_output}")
            
            # HTML report generated - browser auto-launch disabled
            logger.info(f"HTML report generated at: {html_output}")
            # Uncomment below to auto-launch in browser:
            # try:
            #     webbrowser.open('file://' + os.path.abspath(html_output))
            #     logger.info(f"Opened HTML report in browser")
            # except Exception as e:
            #     logger.warning(f"Could not open browser automatically: {e}")
            
            # Print summary to console
            print("\n===== Institutional Accumulation Results =====")
            print(f"Found {len(results_df)} stocks showing institutional accumulation patterns")
            
            # Print sector cluster analysis
            print("\n🔍 SECTOR CLUSTER ANALYSIS (Pattern 8):")
            print("-" * 50)
            hot_sectors = [s for s, info in sector_strength.items() if info['is_hot']]
            if hot_sectors:
                print("🔥 HOT SECTORS (3+ stocks with accumulation):")
                for sector in hot_sectors:
                    info = sector_strength[sector]
                    print(f"  • {sector}: {info['count']} stocks | Avg Score: {info['avg_score']:.1f} | Strength: {info['strength_rating']}")
            else:
                print("No hot sectors detected (need 3+ stocks per sector)")
            
            print("\nAll Sector Distribution:")
            for sector, info in sorted(sector_strength.items(), key=lambda x: x[1]['count'], reverse=True):
                print(f"  {sector}: {info['count']} stocks | Avg Score: {info['avg_score']:.1f} | {info['strength_rating']}")
            
            print("\n📊 TOP 10 ACCUMULATION PATTERNS (All 8 Patterns Scored):")
            print("-" * 80)
            for idx, row in results_df.head(10).iterrows():
                print(f"\n{idx+1}. {row['Ticker']} ({row['Sector']})")
                print(f"   Final Score: {row['Final_Score']:.1f}/11 (Base: {row['Score']:.1f} + Sector Bonus: {row['Sector_Bonus']})")
                print(f"   Pattern Breakdown: P1:{row['P1_UpDays_Vol']:.0f} P2:{row['P2_Quiet_Pull']:.0f} P3:{row['P3_Tight_Range']:.0f} P4:{row['P4_Higher_Lows']:.1f}")
                print(f"                      P5:{row['P5_Rel_Strength']:.1f} P6:{row['P6_EMA_Support']:.1f} P7:{row['P7_Vol_DryUp']:.0f} P8:{row['P8_Trend']:.0f}")
                print(f"   Metrics: {row['Up_Days_10']}/10 up-days | {row['High_Volume_Days']} high vol days | Entry: ₹{row['Entry_Price']:.2f}")

            print(f"\nDetailed results saved to: {excel_file}")
            print(f"HTML report opened in browser: {html_file}")
            
        else:
            # Create empty Excel with columns
            empty_cols = ['Ticker', 'Sector', 'Pattern', 'Direction', 'Score', 'Up_Days_10', 'Up_Days_5', 
                          'High_Volume_Days', 'Closes_Near_High', 'Avg_Up_Volume', 'Avg_Down_Volume',
                          'Recent_Gain_%', 'Volume_Accum_3D', 'Volume_Accum_5D', 'Entry_Price', 
                          'Stop_Loss', 'Target1', 'Target2', 'Target3', 'Risk', 'Risk_Reward_Ratio', 'Description']
            pd.DataFrame(columns=empty_cols).to_excel(excel_file, index=False)
            
            # Generate empty HTML report
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Institutional Accumulation Daily - {formatted_date}</title>
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
                <h1>🏦 Institutional Accumulation Daily Scanner</h1>
                <div class="no-results">
                    <h2>No Accumulation Patterns Found</h2>
                    <p>No tickers matched the institutional accumulation criteria in today's scan.</p>
                    <p>The scanner looks for:</p>
                    <ul style="display: inline-block; text-align: left;">
                        <li>Multiple up-days (6+ in last 10 days)</li>
                        <li>High volume on up-days (1.5x+ average)</li>
                        <li>Price closes near daily highs</li>
                        <li>Volume accumulation patterns</li>
                        <li>Score of 6/9 or higher</li>
                    </ul>
                    <p><strong>Note:</strong> Institutional accumulation patterns are less frequent but can signal strong future moves.</p>
                </div>
                <div style="margin-top: 50px; color: #999;">
                    <p>Generated on {formatted_date} at {formatted_time.replace('_', ':')} | Institutional Accumulation Scanner</p>
                </div>
            </body>
            </html>
            """
            with open(html_file, 'w') as f:
                f.write(html_content)
                
            # Browser auto-launch disabled
            logger.info(f"HTML report saved at: {html_file}")
            # Uncomment below to auto-launch in browser:
            # try:
            #     webbrowser.open('file://' + os.path.abspath(html_file))
            # except Exception as e:
            #     logger.warning(f"Could not open browser automatically: {e}")
                
            logger.info(f"No institutional accumulation patterns found. Empty output files created at {excel_file} and {html_file}")
            print("\nNo institutional accumulation patterns found.")
            print(f"Empty results saved to: {excel_file} and {html_file}")
            
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
    print("\n" + "=" * 80)
    print("       INSTITUTIONAL ACCUMULATION SCANNER - 8 PATTERN ANALYSIS")
    print("=" * 80)
    print("\n📊 SCANNING FOR ALL 8 INSTITUTIONAL ACCUMULATION PATTERNS:\n")
    print("  1️⃣  Repeated Up-Days on Volume (1.5x-2x average)")
    print("  2️⃣  Quiet Pullbacks (low volume on down days)")
    print("  3️⃣  Tight Trading Ranges (supply absorption)")
    print("  4️⃣  Higher Lows (staircase pattern)")
    print("  5️⃣  Strong Relative Strength (outperforming market)")
    print("  6️⃣  Support at Key EMAs (8 & 21 EMA bounces)")
    print("  7️⃣  Volume Dry-ups at Lows (seller exhaustion)")
    print("  8️⃣  Sector Clusters (multiple breakouts in same sector)")
    print("\n" + "=" * 80)
    print(f"📁 Input: Ticker_with_Sector.xlsx | 📊 Output: reports/")
    print(f"👤 Using credentials for: {user_name}")
    print("=" * 80 + "\n")

    result = main()
    sys.exit(result)