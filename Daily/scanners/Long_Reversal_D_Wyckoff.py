#!/usr/bin/env python
# Long_Reversal_D_Wyckoff.py - Wyckoff Accumulation Scanner for FNO Liquid Stocks
# Detects: SC (Selling Climax), ST-A (Secondary Test - Accumulation), SPRING, SOS (Sign of Strength)
# Incorporates: Volume Profile (HVN/LVN), Phase Analysis, Enhanced 10-point Scoring System

# Standard library imports
import os
import time
import logging
import datetime
import sys
import argparse
import configparser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Third-party imports
import numpy as np
import pandas as pd
import pytz
from dateutil.relativedelta import relativedelta
from kiteconnect import KiteConnect
import webbrowser

# Add parent directories to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "long_reversal_d_wyckoff.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Long Reversal Daily - Wyckoff Accumulation Analysis for FNO Liquid Stocks")
    parser.add_argument("-u", "--user", default="Sai", help="User name to use for API credentials (default: Sai)")
    parser.add_argument("--fno-only", action="store_true", default=True, help="Use FNO Liquid stocks only (default: True)")
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
RESULTS_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "results")
HTML_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "Detailed_Analysis")

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
# Calculate Basic Indicators
# -----------------------------
def calculate_indicators(daily_data):
    """Calculate indicators for analysis"""
    if daily_data.empty or len(daily_data) < 50:
        logger.warning(f"Insufficient data points for {daily_data['Ticker'].iloc[0] if not daily_data.empty else 'unknown ticker'}")
        return None
        
    # Create a copy to avoid SettingWithCopyWarning
    df = daily_data.copy()
    
    # Calculate multiple SMAs for trend confirmation
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean()
    
    # Calculate ATR for volatility and stop loss placement
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift(1)).abs()
    low_close = (df['Low'] - df['Close'].shift(1)).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    df['TR'] = ranges.max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()
    
    # Calculate support and resistance levels (swing highs/lows)
    df['SwingHigh'] = df['High'][(df['High'].shift(1) < df['High']) & (df['High'].shift(-1) < df['High'])]
    df['SwingLow'] = df['Low'][(df['Low'].shift(1) > df['Low']) & (df['Low'].shift(-1) > df['Low'])]
    
    # Forward fill swing highs and lows for resistance/support levels
    df['LastSwingHigh'] = df['SwingHigh'].ffill()
    df['LastSwingLow'] = df['SwingLow'].ffill()
    
    # Calculate trend direction based on SMA alignment
    df['TrendUp'] = (df['SMA20'] > df['SMA50']) & (df['SMA50'] > df['SMA200'])
    df['TrendDown'] = (df['SMA20'] < df['SMA50']) & (df['SMA50'] < df['SMA200'])
    
    # Calculate body strength for confirmation bars
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Range'] = df['High'] - df['Low']
    df['BodyPercent'] = (df['Body'] / df['Range']) * 100
    
    # Calculate volume indicators for confirmation
    df['AvgVolume20'] = df['Volume'].rolling(window=20).mean()
    df['VolumeRatio'] = df['Volume'] / df['AvgVolume20']
    
    # Calculate momentum indicators
    df['ROC5'] = ((df['Close'] - df['Close'].shift(5)) / df['Close'].shift(5)) * 100
    df['ROC10'] = ((df['Close'] - df['Close'].shift(10)) / df['Close'].shift(10)) * 100
    
    # Calculate previous bar values for breakout detection
    df['PrevHigh'] = df['High'].shift(1)
    df['PrevLow'] = df['Low'].shift(1)
    df['PrevClose'] = df['Close'].shift(1)
    df['PrevOpen'] = df['Open'].shift(1)
    
    return df

# -----------------------------
# WYCKOFF FUNCTIONS - Event Detection
# -----------------------------
def identify_swing_points(df, lookback=3):
    """Identify swing highs and lows using a lookback period"""
    swing_highs = []
    swing_lows = []
    
    for i in range(lookback, len(df) - lookback):
        # Check for swing high
        is_swing_high = True
        for j in range(1, lookback + 1):
            if df.iloc[i]['High'] <= df.iloc[i-j]['High'] or df.iloc[i]['High'] <= df.iloc[i+j]['High']:
                is_swing_high = False
                break
        
        if is_swing_high:
            swing_highs.append({
                'index': i,
                'price': df.iloc[i]['High'],
                'date': df.iloc[i]['Date']
            })
        
        # Check for swing low
        is_swing_low = True
        for j in range(1, lookback + 1):
            if df.iloc[i]['Low'] >= df.iloc[i-j]['Low'] or df.iloc[i]['Low'] >= df.iloc[i+j]['Low']:
                is_swing_low = False
                break
        
        if is_swing_low:
            swing_lows.append({
                'index': i,
                'price': df.iloc[i]['Low'],
                'date': df.iloc[i]['Date']
            })
    
    return swing_highs, swing_lows

def detect_selling_climax(df, lookback=20):
    """Detect Selling Climax (SC) - High volume selloff that marks potential bottom"""
    if len(df) < lookback:
        return None
    
    recent_bars = df.tail(lookback)
    sc_events = []
    
    for i in range(len(recent_bars) - 1):
        bar = recent_bars.iloc[i]
        
        # SC criteria (more lenient):
        # 1. Large down bar (close < open)
        # 2. High volume (> 1.5x average, reduced from 2x)
        # 3. Long lower wick (shows buying interest)
        is_down_bar = bar['Close'] < bar['Open']
        volume_spike = bar['VolumeRatio'] > 1.5  # Reduced threshold
        
        # Calculate wick ratio
        body = abs(bar['Close'] - bar['Open'])
        lower_wick = min(bar['Open'], bar['Close']) - bar['Low']
        upper_wick = bar['High'] - max(bar['Open'], bar['Close'])
        
        has_long_lower_wick = lower_wick > body * 0.5  # Lower wick > 50% of body
        
        if is_down_bar and volume_spike and has_long_lower_wick:
            sc_events.append({
                'index': i,
                'date': bar['Date'],
                'low': bar['Low'],
                'volume_ratio': bar['VolumeRatio'],
                'wick_ratio': lower_wick / body if body > 0 else 0
            })
    
    return sc_events[-1] if sc_events else None

def detect_secondary_test(df, sc_event, tolerance=0.02):
    """Detect Secondary Test (ST-A) - Retest of SC low with lower volume"""
    if not sc_event or len(df) < 5:
        return None
    
    # Look for ST after SC
    bars_after_sc = df[df['Date'] > sc_event['date']].tail(10)
    
    for i in range(len(bars_after_sc)):
        bar = bars_after_sc.iloc[i]
        
        # ST criteria:
        # 1. Price approaches SC low (within tolerance)
        # 2. Lower volume than SC
        # 3. Holds above SC low (ideally)
        price_near_sc = abs(bar['Low'] - sc_event['low']) / sc_event['low'] <= tolerance
        lower_volume = bar['VolumeRatio'] < sc_event['volume_ratio'] * 0.7
        holds_above = bar['Low'] >= sc_event['low'] * 0.995  # Allow slight undercut
        
        if price_near_sc and lower_volume:
            return {
                'date': bar['Date'],
                'low': bar['Low'],
                'held_above': holds_above,
                'volume_ratio': bar['VolumeRatio']
            }
    
    return None

def detect_spring(df, trading_range, lookback=15):
    """Detect SPRING - False breakdown below support that quickly recovers"""
    if len(df) < lookback or not trading_range:
        return None
    
    recent_bars = df.tail(lookback)  # Look at more bars
    support_level = trading_range['support']
    
    for i in range(len(recent_bars) - 1):
        bar = recent_bars.iloc[i]
        next_bar = recent_bars.iloc[i + 1] if i < len(recent_bars) - 1 else None
        
        # SPRING criteria (more lenient):
        # 1. Wick below or near support
        # 2. Close back inside or near range
        # 3. Any volume increase
        wick_below = bar['Low'] < support_level * 1.01  # Allow near support
        close_inside = bar['Close'] > support_level * 0.99  # More lenient
        
        if wick_below and close_inside:
            # Check for follow-through
            if next_bar is not None:
                bullish_followthrough = next_bar['Close'] > next_bar['Open']
                volume_expansion = next_bar['VolumeRatio'] > 1.1  # Reduced threshold
                
                if bullish_followthrough or volume_expansion or bar['VolumeRatio'] > 1.2:
                    return {
                        'date': bar['Date'],
                        'spring_low': bar['Low'],
                        'recovery_close': bar['Close'],
                        'volume_ratio': bar['VolumeRatio'],
                        'confirmed': bullish_followthrough
                    }
    
    return None

def detect_sign_of_strength(df, trading_range, lookback=10):
    """Detect Sign of Strength (SOS) - Breakout above resistance with volume"""
    if len(df) < lookback or not trading_range:
        return None
    
    recent_bars = df.tail(lookback)
    resistance_level = trading_range['resistance']
    
    for i in range(len(recent_bars)):
        bar = recent_bars.iloc[i]
        
        # SOS criteria (more lenient):
        # 1. Close near or above resistance
        # 2. Above average volume
        # 3. Bullish bar
        breaks_resistance = bar['Close'] > resistance_level * 0.99  # Near resistance
        high_volume = bar['VolumeRatio'] > 1.2  # Reduced threshold
        bullish_bar = bar['Close'] > bar['Open']
        strong_body = bar['BodyPercent'] > 50  # Reduced threshold
        
        if breaks_resistance and high_volume and bullish_bar and strong_body:
            return {
                'date': bar['Date'],
                'breakout_level': bar['Close'],
                'volume_ratio': bar['VolumeRatio'],
                'strength': (bar['Close'] - resistance_level) / resistance_level
            }
    
    return None

def identify_trading_range(df, lookback=50):
    """Identify the current trading range (support and resistance)"""
    if len(df) < lookback:
        return None
    
    recent_data = df.tail(lookback)
    
    # Find major highs and lows
    highs = recent_data['High'].rolling(window=5).max()
    lows = recent_data['Low'].rolling(window=5).min()
    
    # Get resistance and support levels
    resistance = highs.max()
    support = lows.min()
    
    # Calculate range metrics
    range_height = resistance - support
    range_percent = (range_height / support) * 100
    
    return {
        'resistance': resistance,
        'support': support,
        'range_height': range_height,
        'range_percent': range_percent,
        'midpoint': (resistance + support) / 2
    }

def determine_wyckoff_phase(sc, st, spring, sos, current_price, trading_range):
    """Determine the current Wyckoff phase - more lenient"""
    if not trading_range:
        return "ACCUMULATION"  # Default to accumulation if range exists
    
    # Phase A: SC and ST
    if sc and not spring and not sos:
        return "PHASE_A"
    
    # Phase B: Building cause (trading range)
    if sc and st and not spring and not sos:
        if trading_range['support'] < current_price < trading_range['resistance']:
            return "PHASE_B"
    
    # Phase C: Spring/Test
    if spring:
        return "PHASE_C"
    
    # Phase D: SOS and markup
    if sos:
        return "PHASE_D"
    
    # Phase E: Markup continuation
    if sos and current_price > trading_range['resistance'] * 1.05:
        return "PHASE_E"
    
    # More lenient: If we have any Wyckoff event or are in a range, consider it accumulation
    if sc or st or spring or (trading_range['range_percent'] < 30 and trading_range['range_percent'] > 5):
        return "ACCUMULATION"
    
    return "ACCUMULATION"  # Default to accumulation for scanning

# -----------------------------
# VOLUME PROFILE FUNCTIONS
# -----------------------------
def calculate_volume_profile(df, num_bins=20):
    """Calculate volume profile to identify HVN (High Volume Nodes) and LVN (Low Volume Nodes)"""
    if len(df) < 20:
        return None
    
    # Create price bins
    price_min = df['Low'].min()
    price_max = df['High'].max()
    bins = np.linspace(price_min, price_max, num_bins + 1)
    
    # Calculate volume at each price level
    volume_profile = {}
    bin_centers = []
    volumes = []
    
    for i in range(len(bins) - 1):
        bin_low = bins[i]
        bin_high = bins[i + 1]
        bin_center = (bin_low + bin_high) / 2
        
        # Calculate volume for bars that traded in this price range
        volume_sum = 0
        for idx, row in df.iterrows():
            if row['Low'] <= bin_high and row['High'] >= bin_low:
                # Estimate volume distribution within the bar
                overlap_ratio = min(row['High'], bin_high) - max(row['Low'], bin_low)
                overlap_ratio /= (row['High'] - row['Low']) if row['High'] > row['Low'] else 1
                volume_sum += row['Volume'] * overlap_ratio
        
        bin_centers.append(bin_center)
        volumes.append(volume_sum)
    
    # Identify HVN and LVN
    volumes_array = np.array(volumes)
    mean_volume = volumes_array.mean()
    std_volume = volumes_array.std()
    
    hvn_zones = []  # High Volume Nodes
    lvn_zones = []  # Low Volume Nodes
    gaps = []       # Price gaps
    
    for i, (price, vol) in enumerate(zip(bin_centers, volumes)):
        if vol > mean_volume + std_volume:
            hvn_zones.append({'price': price, 'volume': vol, 'strength': 'high'})
        elif vol < mean_volume - std_volume * 0.5:
            lvn_zones.append({'price': price, 'volume': vol, 'strength': 'low'})
        elif vol < mean_volume * 0.1:  # Very low volume = potential gap
            gaps.append({'price': price, 'volume': vol})
    
    # Find Point of Control (POC) - highest volume price
    poc_idx = np.argmax(volumes)
    poc = bin_centers[poc_idx]
    
    # Calculate Value Area (70% of volume)
    total_volume = sum(volumes)
    value_area_volume = total_volume * 0.7
    
    # Sort by volume and accumulate until we reach 70%
    sorted_indices = np.argsort(volumes)[::-1]
    accumulated_volume = 0
    value_area_prices = []
    
    for idx in sorted_indices:
        accumulated_volume += volumes[idx]
        value_area_prices.append(bin_centers[idx])
        if accumulated_volume >= value_area_volume:
            break
    
    vah = max(value_area_prices)  # Value Area High
    val = min(value_area_prices)  # Value Area Low
    
    return {
        'poc': poc,
        'vah': vah,
        'val': val,
        'hvn_zones': hvn_zones,
        'lvn_zones': lvn_zones,
        'gaps': gaps,
        'profile': list(zip(bin_centers, volumes))
    }

def check_lvn_spring_confluence(spring_event, volume_profile):
    """Check if Spring occurred at a Low Volume Node (LVN)"""
    if not spring_event or not volume_profile:
        return False
    
    spring_low = spring_event['spring_low']
    
    # Check if spring low is near any LVN
    for lvn in volume_profile['lvn_zones']:
        if abs(spring_low - lvn['price']) / lvn['price'] <= 0.02:  # Within 2%
            return True
    
    # Check if spring low is near a gap
    for gap in volume_profile['gaps']:
        if abs(spring_low - gap['price']) / gap['price'] <= 0.02:
            return True
    
    return False

# -----------------------------
# WYCKOFF SCORING SYSTEM - Enhanced 10-point system
# -----------------------------
def calculate_wyckoff_score(df, wyckoff_events, volume_profile, trading_range):
    """Calculate enhanced Wyckoff pattern score (10-point system)"""
    score = 0
    conditions_met = []
    last_bar = df.iloc[-1]
    recent_bars = df.tail(5)
    
    # 1. Resistance Break (1 point)
    if trading_range and last_bar['Close'] > trading_range['resistance']:
        score += 1
        conditions_met.append("Resistance Break")
    
    # 2. Multiple Bullish Bars (1 point)
    bullish_count = sum(1 for _, bar in recent_bars.tail(3).iterrows() if bar['Close'] > bar['Open'])
    if bullish_count >= 2:
        score += 1
        conditions_met.append("Multiple Bullish Bars")
    
    # 3. Strong Candle Bodies (1 point) - more lenient
    avg_body_percent = recent_bars['BodyPercent'].mean()
    if avg_body_percent > 40:  # Reduced from 60 to 40
        score += 1
        conditions_met.append("Strong Candle Bodies")
    
    # 4. Volume Expansion (1.5 points - enhanced weight) - more lenient
    if last_bar['VolumeRatio'] > 1.1:  # Reduced from 1.5 to 1.1
        score += 1.5
        conditions_met.append("Volume Expansion")
    
    # 5. Trend Support - Above SMA20 (1 point)
    if last_bar['Close'] > last_bar['SMA20']:
        score += 1
        conditions_met.append("Above SMA20")
    
    # 6. Momentum Positive - ROC5 > 0% (1 point) - more lenient
    if last_bar['ROC5'] > 0:  # Just needs to be positive
        score += 1
        conditions_met.append("Positive Momentum")
    
    # 7. Close in Upper Range - Top 50% (1 point) - more lenient
    day_range = last_bar['High'] - last_bar['Low']
    if day_range > 0:
        position_in_range = (last_bar['Close'] - last_bar['Low']) / day_range
        if position_in_range > 0.5:  # Reduced from 0.7 to 0.5
            score += 1
            conditions_met.append("Close in Upper Half")
    
    # 8. Wyckoff Event Confirmation (1.5 points - enhanced weight)
    if wyckoff_events.get('spring') or wyckoff_events.get('sos'):
        score += 1.5
        conditions_met.append("Wyckoff Event Confirmed")
    
    # 9. Long-term trend check - price above 50 SMA
    if last_bar['Close'] > last_bar.get('SMA50', last_bar['Close']):
        score += 1
        conditions_met.append("Above SMA50")
    
    # 10. Phase Confirmation (1 point)
    if wyckoff_events.get('phase') in ['PHASE_C', 'PHASE_D', 'ACCUMULATION']:
        score += 1
        conditions_met.append(f"Phase: {wyckoff_events.get('phase')}")
    
    return score, conditions_met

def determine_entry_exit_levels(df, wyckoff_events, volume_profile, trading_range):
    """Determine optimal entry, stop loss, and target levels based on Wyckoff"""
    last_bar = df.iloc[-1]
    atr = last_bar['ATR']
    
    # Entry determination
    if wyckoff_events.get('spring'):
        # Entry above spring high
        entry_price = wyckoff_events['spring']['recovery_close'] * 1.005
        entry_reason = "Above Spring Recovery"
    elif wyckoff_events.get('sos'):
        # Entry on SOS breakout
        entry_price = wyckoff_events['sos']['breakout_level']
        entry_reason = "SOS Breakout"
    elif wyckoff_events.get('st'):
        # Entry above secondary test
        entry_price = last_bar['Close'] * 1.002
        entry_reason = "Secondary Test Confirmation"
    else:
        # Default entry at current close
        entry_price = last_bar['Close']
        entry_reason = "Current Market Price"
    
    # Stop Loss determination
    if wyckoff_events.get('spring'):
        # Below spring low with buffer
        stop_loss = wyckoff_events['spring']['spring_low'] - (atr * 0.5)
    elif wyckoff_events.get('sc'):
        # Below SC low
        stop_loss = wyckoff_events['sc']['low'] - (atr * 0.5)
    else:
        # Default: 2.5x ATR below entry
        stop_loss = entry_price - (atr * 2.5)
    
    # Ensure stop gives reasonable risk (max 5%)
    max_risk = entry_price * 0.05
    if entry_price - stop_loss > max_risk:
        stop_loss = entry_price - max_risk
    
    # Target determination
    risk = entry_price - stop_loss
    
    # TP1: 1:2 Risk-Reward
    tp1 = entry_price + (risk * 2)
    tp1_reason = "2:1 Risk-Reward"
    
    # TP2: 1:3 Risk-Reward or resistance
    tp2 = entry_price + (risk * 3)
    if trading_range and trading_range['resistance'] > entry_price:
        if trading_range['resistance'] < tp2:
            tp2 = trading_range['resistance']
            tp2_reason = "Trading Range Top"
        else:
            tp2_reason = "3:1 Risk-Reward"
    else:
        tp2_reason = "3:1 Risk-Reward"
    
    # TP3: Range top or extended target
    if trading_range:
        range_extension = trading_range['range_height'] * 0.5
        tp3 = trading_range['resistance'] + range_extension
        tp3_reason = "Range Extension"
    else:
        tp3 = entry_price + (risk * 4)
        tp3_reason = "4:1 Risk-Reward"
    
    # Simplified targets without volume profile
    # TP1 stays as is (2:1 RR or resistance)
    
    return {
        'entry_price': entry_price,
        'entry_reason': entry_reason,
        'stop_loss': stop_loss,
        'tp1': tp1,
        'tp1_reason': tp1_reason,
        'tp2': tp2,
        'tp2_reason': tp2_reason,
        'tp3': tp3,
        'tp3_reason': tp3_reason,
        'risk': risk,
        'rr1': (tp1 - entry_price) / risk if risk > 0 else 0,
        'rr2': (tp2 - entry_price) / risk if risk > 0 else 0,
        'rr3': (tp3 - entry_price) / risk if risk > 0 else 0
    }


# -----------------------------
# MAIN WYCKOFF PROCESSING
# -----------------------------
def process_ticker_wyckoff(ticker):
    """Process a single ticker for Wyckoff accumulation patterns"""
    logger.info(f"Processing {ticker} with Wyckoff analysis")
    
    try:
        now = datetime.datetime.now()
        
        # Date ranges
        from_date_daily = (now - relativedelta(months=6)).strftime('%Y-%m-%d')
        to_date = now.strftime('%Y-%m-%d')
        
        # Fetch DAILY data
        daily_data = fetch_data_kite(ticker, interval_mapping['1d'], from_date_daily, to_date)
        if daily_data.empty or len(daily_data) < 50:
            logger.warning(f"Insufficient data for {ticker}, skipping")
            return None
            
        # Calculate indicators
        daily_with_indicators = calculate_indicators(daily_data)
        if daily_with_indicators is None:
            logger.warning(f"Could not calculate indicators for {ticker}, skipping")
            return None
        
        # Identify trading range
        trading_range = identify_trading_range(daily_with_indicators)
        if not trading_range:
            logger.warning(f"Could not identify trading range for {ticker}")
            return None
        
        # Detect Wyckoff events
        sc = detect_selling_climax(daily_with_indicators)
        st = detect_secondary_test(daily_with_indicators, sc) if sc else None
        spring = detect_spring(daily_with_indicators, trading_range)
        sos = detect_sign_of_strength(daily_with_indicators, trading_range)
        
        # Determine phase
        current_price = daily_with_indicators.iloc[-1]['Close']
        phase = determine_wyckoff_phase(sc, st, spring, sos, current_price, trading_range)
        
        # Skip if clearly not in accumulation (be more lenient)
        if phase == 'UNKNOWN':
            logger.info(f"{ticker} - Not in accumulation phase: {phase}")
            return None
        
        # For PHASE_A and PHASE_B, check if there's potential
        if phase in ['PHASE_A', 'PHASE_B']:
            # Check if price is near support (potential reversal)
            last_bar = daily_with_indicators.iloc[-1]
            near_support = abs(last_bar['Close'] - trading_range['support']) / trading_range['support'] < 0.05
            if not near_support and not sc and not st:
                logger.info(f"{ticker} - Early phase without reversal signals")
                return None
        
        # Skip volume profile for now (simplified approach)
        volume_profile = None
        lvn_confluence = False
        
        # Prepare Wyckoff events dictionary
        wyckoff_events = {
            'sc': sc,
            'st': st,
            'spring': spring,
            'sos': sos,
            'phase': phase,
            'lvn_confluence': lvn_confluence
        }
        
        # Calculate score
        score, conditions_met = calculate_wyckoff_score(
            daily_with_indicators, wyckoff_events, volume_profile, trading_range
        )
        
        # Minimum score requirement (3/10 - very lenient for finding opportunities)
        if score < 3:
            logger.info(f"{ticker} - Score too low: {score}/10")
            return None
        
        # Determine entry/exit levels
        levels = determine_entry_exit_levels(
            daily_with_indicators, wyckoff_events, volume_profile, trading_range
        )
        
        # Validate risk-reward (minimum 1:1.5 - more lenient)
        if levels['rr1'] < 1.5:
            logger.info(f"{ticker} - Risk-Reward too low: {levels['rr1']:.2f}")
            return None
        
        # Get current values
        last_bar = daily_with_indicators.iloc[-1]
        
        # Determine pattern description
        pattern_parts = []
        if sc: pattern_parts.append("SC")
        if st: pattern_parts.append("ST-A")
        if spring: pattern_parts.append("SPRING")
        if sos: pattern_parts.append("SOS")
        pattern = "+".join(pattern_parts) if pattern_parts else "ACCUMULATION"
        
        # Get sector
        sector = get_sector_for_ticker(ticker)
        
        # Log the findings
        logger.info(f"{ticker} - Wyckoff Setup Found! Score: {score}/10, Phase: {phase}")
        logger.info(f"{ticker} - Pattern: {pattern}, Entry: {levels['entry_price']:.2f}")
        
        # Prepare result
        result = {
            'Ticker': ticker,
            'Sector': sector,
            'Phase': phase,
            'Pattern': pattern,
            'Score': score,
            'Entry_Price': levels['entry_price'],
            'Entry_Reason': levels['entry_reason'],
            'Stop_Loss': levels['stop_loss'],
            'Target1': levels['tp1'],
            'Target1_RR': levels['rr1'],
            'Target1_Reason': levels['tp1_reason'],
            'Target2': levels['tp2'],
            'Target2_RR': levels['rr2'],
            'Target2_Reason': levels['tp2_reason'],
            'Target3': levels['tp3'],
            'Target3_RR': levels['rr3'],
            'Target3_Reason': levels['tp3_reason'],
            'Risk': levels['risk'],
            'Risk_Reward_Ratio': levels['rr1'],
            'Volume_Ratio': last_bar['VolumeRatio'],
            'Momentum_5D': last_bar['ROC5'],
            'ATR': last_bar['ATR'],
            'Conditions_Met': ', '.join(conditions_met),
            'Description': f"Wyckoff {phase} - {pattern}",
            'LVN_Confluence': False,
            'POC': 0,
            'VAH': 0,
            'VAL': 0,
            'Range_Top': trading_range['resistance'],
            'Range_Bottom': trading_range['support'],
            'Range_Percent': trading_range['range_percent']
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing {ticker}: {e}")
        return None






# -----------------------------
# Read Ticker File
# -----------------------------
def read_ticker_file(use_fno_liquid=True):
    """Read tickers from the Excel file"""
    # Always use Ticker.xlsx as requested by user
    ticker_file = os.path.join(DATA_DIR, "Ticker.xlsx")
    
    try:
        if not os.path.exists(ticker_file):
            logger.error(f"Ticker file not found: {ticker_file}")
            return []
        
        # Read the Ticker sheet
        df = pd.read_excel(ticker_file, sheet_name="Ticker")
        all_tickers = df['Ticker'].dropna().tolist()
        
        # Optional: Filter for FNO Liquid stocks if needed
        if use_fno_liquid:
            fno_file = os.path.join(DATA_DIR, "FNO_Liquid.xlsx")
            if os.path.exists(fno_file):
                try:
                    fno_df = pd.read_excel(fno_file)
                    fno_tickers = fno_df['Ticker'].dropna().tolist() if 'Ticker' in fno_df.columns else []
                    # Filter to only FNO liquid stocks that are in Ticker.xlsx
                    filtered_tickers = [t for t in all_tickers if t in fno_tickers]
                    if filtered_tickers:
                        logger.info(f"Using {len(filtered_tickers)} FNO Liquid stocks from {len(all_tickers)} total tickers")
                        return filtered_tickers
                except Exception as e:
                    logger.warning(f"Could not filter FNO Liquid stocks: {e}")
        
        logger.info(f"Read {len(all_tickers)} tickers from {ticker_file}")
        return all_tickers
    except Exception as e:
        logger.error(f"Error reading ticker file: {e}")
        return []

# -----------------------------
# Generate Enhanced HTML Report with Wyckoff
# -----------------------------
def generate_wyckoff_html_report(filtered_df, output_file):
    """Generate an enhanced HTML report with Wyckoff analysis"""
    today = datetime.datetime.now()
    formatted_date = today.strftime("%d-%m-%Y")
    formatted_time = today.strftime("%H:%M")

    # HTML template with modern styling and SMC enhancements
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Long Reversal Wyckoff Analysis - {formatted_date}</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1600px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .container {{
                background-color: white;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            h1, h2, h3 {{
                color: #2c3e50;
            }}
            h1 {{
                border-bottom: 3px solid #667eea;
                padding-bottom: 15px;
                margin-bottom: 30px;
            }}
            .header-info {{
                display: flex;
                justify-content: space-between;
                color: #7f8c8d;
                margin-bottom: 30px;
                padding: 15px;
                background-color: #f8f9fa;
                border-radius: 10px;
            }}
            .smc-badge {{
                display: inline-block;
                padding: 3px 8px;
                border-radius: 5px;
                font-size: 0.85em;
                font-weight: bold;
                margin: 2px;
            }}
            .badge-bos {{
                background-color: #00b894;
                color: white;
            }}
            .badge-choch {{
                background-color: #6c5ce7;
                color: white;
            }}
            .badge-sweep {{
                background-color: #fdcb6e;
                color: #2d3436;
            }}
            .badge-ob {{
                background-color: #74b9ff;
                color: white;
            }}
            .badge-fvg {{
                background-color: #a29bfe;
                color: white;
            }}
            .score-meter {{
                display: inline-block;
                width: 100px;
                height: 20px;
                background-color: #e0e0e0;
                border-radius: 10px;
                overflow: hidden;
                margin-left: 10px;
                vertical-align: middle;
            }}
            .score-fill {{
                height: 100%;
                transition: width 0.3s ease;
            }}
            .score-high {{ background: linear-gradient(90deg, #00b894, #00cec9); }}
            .score-medium {{ background: linear-gradient(90deg, #fdcb6e, #e17055); }}
            .score-low {{ background: linear-gradient(90deg, #fab1a0, #ff7675); }}
            .ticker-card {{
                background-color: white;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                border-left: 5px solid #667eea;
                transition: transform 0.3s ease;
            }}
            .ticker-card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            }}
            .ticker-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                padding-bottom: 15px;
                border-bottom: 2px solid #f0f0f0;
            }}
            .ticker-name {{
                font-weight: bold;
                font-size: 1.4em;
                color: #2c3e50;
            }}
            .quality-badge {{
                padding: 5px 15px;
                border-radius: 20px;
                font-weight: bold;
                text-transform: uppercase;
                font-size: 0.9em;
            }}
            .quality-high {{
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
            }}
            .quality-medium {{
                background: linear-gradient(135deg, #f093fb, #f5576c);
                color: white;
            }}
            .quality-low {{
                background: linear-gradient(135deg, #fa709a, #fee140);
                color: #2d3436;
            }}
            .smc-indicators {{
                display: flex;
                gap: 10px;
                margin: 15px 0;
                flex-wrap: wrap;
            }}
            .ticker-details {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 15px;
                margin-top: 20px;
            }}
            .detail-item {{
                background-color: #f8f9fa;
                padding: 12px;
                border-radius: 8px;
                border-left: 3px solid #667eea;
            }}
            .detail-label {{
                color: #7f8c8d;
                font-size: 0.85em;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .detail-value {{
                font-weight: bold;
                font-size: 1.1em;
                color: #2c3e50;
                margin-top: 5px;
            }}
            .targets-section {{
                background: linear-gradient(135deg, #f8f9fa, #e9ecef);
                padding: 15px;
                border-radius: 10px;
                margin-top: 20px;
            }}
            .target-row {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px;
                margin: 5px 0;
                background-color: white;
                border-radius: 8px;
            }}
            .confluence-section {{
                background-color: #e8f4fd;
                padding: 15px;
                border-radius: 8px;
                margin-top: 15px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                background-color: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }}
            th {{
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                padding: 15px;
                text-align: left;
                font-weight: 600;
                text-transform: uppercase;
                font-size: 0.9em;
                letter-spacing: 0.5px;
            }}
            td {{
                padding: 12px 15px;
                border-bottom: 1px solid #f0f0f0;
            }}
            tbody tr:hover {{
                background-color: #f8f9fa;
            }}
            .summary-stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }}
            .stat-card {{
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
            }}
            .stat-value {{
                font-size: 2em;
                font-weight: bold;
            }}
            .stat-label {{
                font-size: 0.9em;
                opacity: 0.9;
                margin-top: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Long Reversal Daily - Wyckoff Accumulation Analysis</h1>
            <div class="header-info">
                <div>Date: {formatted_date} | Time: {formatted_time}</div>
                <div>Wyckoff Events: SC, ST-A, SPRING, SOS | Volume Profile: HVN/LVN Analysis</div>
            </div>
    """
    
    # Add summary statistics
    if len(filtered_df) > 0:
        avg_score = filtered_df['Score'].mean()
        high_score = len(filtered_df[filtered_df['Score'] >= 7])
        medium_score = len(filtered_df[(filtered_df['Score'] >= 5) & (filtered_df['Score'] < 7)])
        
        html_content += f"""
            <div class="summary-stats">
                <div class="stat-card">
                    <div class="stat-value">{len(filtered_df)}</div>
                    <div class="stat-label">Total Setups Found</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{avg_score:.1f}</div>
                    <div class="stat-label">Average Score (10)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{high_score}</div>
                    <div class="stat-label">High Score (7+)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{medium_score}</div>
                    <div class="stat-label">Medium Score (5-7)</div>
                </div>
            </div>
        """
    
    # Add detailed table
    html_content += """
        <h2>📈 Wyckoff Accumulation Setups</h2>
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Sector</th>
                    <th>Phase</th>
                    <th>Pattern</th>
                    <th>Score</th>
                    <th>Entry</th>
                    <th>Stop Loss</th>
                    <th>Target1 (RR)</th>
                    <th>Target2 (RR)</th>
                    <th>Volume Profile</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # Add rows for each ticker
    for idx, row in filtered_df.iterrows():
        # Create volume profile info
        vp_info = ""
        if row.get('LVN_Confluence'):
            vp_info += '<span class="smc-badge badge-sweep">LVN</span>'
        if row.get('POC', 0) > 0:
            vp_info += f'<span class="smc-badge badge-ob">POC: ₹{row["POC"]:.0f}</span>'
        
        # Score quality class
        if row['Score'] >= 7:
            quality_class = "quality-high"
            quality_text = "HIGH"
        elif row['Score'] >= 5:
            quality_class = "quality-medium"
            quality_text = "MEDIUM"
        else:
            quality_class = "quality-low"
            quality_text = "LOW"
        
        # Phase color
        phase_color = "green" if row['Phase'] in ['PHASE_C', 'PHASE_D'] else "orange"
        
        html_content += f"""
            <tr>
                <td><strong>{row['Ticker']}</strong></td>
                <td>{row['Sector']}</td>
                <td><span style="color: {phase_color}; font-weight: bold;">{row['Phase']}</span></td>
                <td>{row['Pattern']}</td>
                <td>
                    {row['Score']:.1f}/10
                    <div class="score-meter">
                        <div class="score-fill score-{quality_text.lower()}" style="width: {row['Score']*10}%"></div>
                    </div>
                </td>
                <td>₹{row['Entry_Price']:.2f}</td>
                <td>₹{row['Stop_Loss']:.2f}</td>
                <td>₹{row['Target1']:.2f} ({row['Target1_RR']:.1f}R)</td>
                <td>₹{row['Target2']:.2f} ({row['Target2_RR']:.1f}R)</td>
                <td>{vp_info if vp_info else 'Standard'}</td>
            </tr>
        """
    
    html_content += """
            </tbody>
        </table>
    """
    
    # Add detailed cards for each ticker
    html_content += "<h2>📋 Detailed Wyckoff Analysis</h2>"
    
    for idx, row in filtered_df.iterrows():
        # Create Wyckoff indicator badges
        wyckoff_indicators = ""
        if 'SC' in row.get('Pattern', ''):
            wyckoff_indicators += '<span class="smc-badge badge-bos">SC ✓</span>'
        if 'ST-A' in row.get('Pattern', ''):
            wyckoff_indicators += '<span class="smc-badge badge-choch">ST-A ✓</span>'
        if 'SPRING' in row.get('Pattern', ''):
            wyckoff_indicators += '<span class="smc-badge badge-sweep">SPRING ✓</span>'
        if 'SOS' in row.get('Pattern', ''):
            wyckoff_indicators += '<span class="smc-badge badge-ob">SOS ✓</span>'
        if row.get('LVN_Confluence'):
            wyckoff_indicators += '<span class="smc-badge badge-fvg">LVN Confluence ✓</span>'
        
        # Quality class based on score
        if row['Score'] >= 7:
            quality_class = "quality-high"
            quality_text = "HIGH"
        elif row['Score'] >= 5:
            quality_class = "quality-medium"
            quality_text = "MEDIUM"
        else:
            quality_class = "quality-low"
            quality_text = "LOW"
        
        html_content += f"""
        <div class="ticker-card">
            <div class="ticker-header">
                <div>
                    <span class="ticker-name">{row['Ticker']}</span>
                    <span style="color: #7f8c8d; margin-left: 15px;">{row['Sector']}</span>
                </div>
                <div>
                    <span class="quality-badge {quality_class}">{quality_text}</span>
                    <span style="margin-left: 15px; font-size: 1.2em; font-weight: bold;">
                        Score: {row['Score']:.1f}/10
                    </span>
                </div>
            </div>
            
            <div class="smc-indicators">
                {wyckoff_indicators}
            </div>
            
            <div style="background-color: #f0f4f8; padding: 10px; border-radius: 8px; margin: 15px 0;">
                <strong>📊 Wyckoff Analysis:</strong>
                <span style="margin-left: 15px;">Phase: <strong style="color: {'green' if row['Phase'] in ['PHASE_C', 'PHASE_D'] else 'orange'};">{row['Phase']}</strong></span>
                <span style="margin-left: 15px;">Pattern: <strong>{row['Pattern']}</strong></span>
                <span style="margin-left: 15px;">Range: <strong>{row.get('Range_Percent', 0):.1f}%</strong></span>
            </div>
            
            <div class="ticker-details">
                <div class="detail-item">
                    <div class="detail-label">Entry Price</div>
                    <div class="detail-value">₹{row['Entry_Price']:.2f}</div>
                    <div style="font-size: 0.8em; color: #7f8c8d;">{row['Entry_Reason']}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Stop Loss</div>
                    <div class="detail-value">₹{row['Stop_Loss']:.2f}</div>
                    <div style="font-size: 0.8em; color: #e74c3c;">Risk: ₹{row['Risk']:.2f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Volume Ratio</div>
                    <div class="detail-value">{row['Volume_Ratio']:.2f}x</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">5-Day Momentum</div>
                    <div class="detail-value">{row['Momentum_5D']:.2f}%</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">ATR (14)</div>
                    <div class="detail-value">₹{row['ATR']:.2f}</div>
                </div>
            </div>
            
            <div class="targets-section">
                <h4>🎯 Take Profit Targets</h4>
                <div class="target-row">
                    <span><strong>T1:</strong> ₹{row['Target1']:.2f}</span>
                    <span>RR: {row['Target1_RR']:.1f}</span>
                    <span style="color: #7f8c8d;">{row.get('Target1_Reason', '2:1 RR')}</span>
                </div>
                <div class="target-row">
                    <span><strong>T2:</strong> ₹{row['Target2']:.2f}</span>
                    <span>RR: {row['Target2_RR']:.1f}</span>
                    <span style="color: #7f8c8d;">{row.get('Target2_Reason', '3:1 RR')}</span>
                </div>
                <div class="target-row">
                    <span><strong>T3:</strong> ₹{row['Target3']:.2f}</span>
                    <span>RR: {row['Target3_RR']:.1f}</span>
                    <span style="color: #7f8c8d;">{row.get('Target3_Reason', 'Range Top')}</span>
                </div>
            </div>
            
            <div class="confluence-section">
                <strong>Conditions Met:</strong> {row.get('Conditions_Met', 'N/A')}
            </div>
            <div style="margin-top: 10px; padding: 10px; background-color: #f8f9fa; border-radius: 8px;">
                <strong>Volume Profile:</strong>
                <span style="margin-left: 10px;">POC: ₹{row.get('POC', 0):.0f}</span>
                <span style="margin-left: 10px;">VAH: ₹{row.get('VAH', 0):.0f}</span>
                <span style="margin-left: 10px;">VAL: ₹{row.get('VAL', 0):.0f}</span>
            </div>
        </div>
        """
    
    # Complete HTML
    html_content += f"""
            <div style="margin-top: 50px; padding: 20px; background-color: #f8f9fa; border-radius: 10px; text-align: center;">
                <p style="color: #7f8c8d;">
                    Generated on {formatted_date} at {formatted_time} | 
                    Long Reversal Daily with Wyckoff Method
                </p>
                <p style="color: #95a5a6; font-size: 0.9em;">
                    This analysis uses Wyckoff accumulation patterns including Selling Climax (SC), Secondary Test (ST-A),
                    Spring, and Sign of Strength (SOS) combined with Volume Profile analysis for enhanced accuracy.
                </p>
            </div>
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
    """Main function to filter tickers using Wyckoff analysis"""
    logger.info("Starting Long Reversal Daily Wyckoff Analysis")
    
    start_time = time.time()

    try:
        # Read the tickers (use FNO Liquid filter based on args)
        tickers = read_ticker_file(use_fno_liquid=args.fno_only)
        if not tickers:
            logger.error("No tickers found, exiting")
            return 1
        
        logger.info(f"Starting Wyckoff analysis for {len(tickers)} tickers")
        
        # Process each ticker with Wyckoff
        results = []
        for ticker in tickers:
            result = process_ticker_wyckoff(ticker)
            if result:
                results.append(result)
        
        # Create output files with timestamp
        today = datetime.datetime.now()
        formatted_date = today.strftime("%Y%m%d")
        formatted_time = today.strftime("%H%M%S")
        excel_file = os.path.join(RESULTS_DIR, f"Long_Reversal_Wyckoff_{formatted_date}_{formatted_time}.xlsx")
        html_file = os.path.join(HTML_DIR, f"Long_Reversal_Wyckoff_{formatted_date}_{formatted_time}.html")
        
        if results:
            # Convert to DataFrame
            results_df = pd.DataFrame(results)
            
            # Sort by Score (descending)
            results_df = results_df.sort_values(by='Score', ascending=False)
            
            # Round numeric columns for better readability
            numeric_cols = ['Entry_Price', 'Stop_Loss', 'TP1', 'TP2', 'TP3', 
                          'Risk', 'Volume_Ratio', 'Momentum_5D', 'ATR',
                          'TP1_RR', 'TP2_RR', 'TP3_RR']
            for col in numeric_cols:
                if col in results_df.columns:
                    results_df[col] = results_df[col].astype(float).round(2)
            
            # Write to Excel
            results_df.to_excel(excel_file, index=False)
            logger.info(f"Successfully wrote {len(results_df)} Wyckoff setups to {excel_file}")
            
            # Generate HTML report
            html_output = generate_wyckoff_html_report(results_df, html_file)
            logger.info(f"Generated Wyckoff HTML report at {html_output}")
            
            # HTML report generated - browser auto-launch disabled
            logger.info(f"HTML report generated at: {html_output}")
            # Uncomment below to auto-launch in browser:
            # try:
            #     webbrowser.open('file://' + os.path.abspath(html_output))
            #     logger.info(f"Opened HTML report in browser")
            # except Exception as e:
            #     logger.warning(f"Could not open browser automatically: {e}")
            
            # Print summary to console
            print("\n" + "="*60)
            print("   WYCKOFF ACCUMULATION - ANALYSIS RESULTS")
            print("="*60)
            print(f"\n📊 Found {len(results_df)} Wyckoff Accumulation Setups")
            
            # Score breakdown
            high_score = len(results_df[results_df['Score'] >= 7])
            medium_score = len(results_df[(results_df['Score'] >= 5) & (results_df['Score'] < 7)])
            print("\n🎯 Score Distribution:")
            print(f"   High (7+): {high_score} setups")
            print(f"   Medium (5-7): {medium_score} setups")
            
            # Top setups
            print("\n🏆 Top 5 Wyckoff Setups by Score:")
            for idx, row in results_df.head(5).iterrows():
                print(f"\n   {row['Ticker']} ({row['Sector']})")
                print(f"   Phase: {row['Phase']} | Pattern: {row['Pattern']}")
                print(f"   Score: {row['Score']:.1f}/10")
                print(f"   Entry: ₹{row['Entry_Price']:.2f} | Stop: ₹{row['Stop_Loss']:.2f}")
                print(f"   Targets: T1={row['Target1_RR']:.1f}R, T2={row['Target2_RR']:.1f}R, T3={row['Target3_RR']:.1f}R")
                if row.get('LVN_Confluence'):
                    print(f"   Special: LVN Confluence at Spring/ST")

            print(f"\n📁 Results saved to:")
            print(f"   Excel: {excel_file}")
            print(f"   HTML: {html_file}")
        else:
            # Create empty Excel with correct columns
            empty_cols = ['Ticker', 'Sector', 'Phase', 'Pattern', 'Score', 'Entry_Price', 
                         'Entry_Reason', 'Stop_Loss', 'Target1', 'Target1_RR', 'Target1_Reason',
                         'Target2', 'Target2_RR', 'Target2_Reason', 'Target3', 'Target3_RR', 'Target3_Reason',
                         'Risk', 'Risk_Reward_Ratio', 'Volume_Ratio', 'Momentum_5D', 'ATR', 
                         'Conditions_Met', 'Description', 'LVN_Confluence', 'POC', 'VAH', 'VAL',
                         'Range_Top', 'Range_Bottom', 'Range_Percent']
            empty_df = pd.DataFrame(columns=empty_cols)
            empty_df.to_excel(excel_file, index=False)
            
            # Also create empty HTML
            generate_wyckoff_html_report(empty_df, html_file)
            
            logger.info(f"No Wyckoff accumulation patterns found. Empty output created at {excel_file}")
            print("\nNo Wyckoff accumulation patterns found meeting the criteria.")
            print(f"Empty results saved to: {excel_file}")
            print("\nTip: The market may not have many stocks in accumulation phase currently.")
            print("Consider running during market corrections or after selloffs for better results.")
            
        # Calculate and print execution time
        execution_time = time.time() - start_time
        logger.info(f"Total execution time: {execution_time:.2f} seconds")
        print(f"\n⏱️  Execution time: {execution_time:.2f} seconds")
        print("="*60)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    # Print banner
    print("\n" + "="*60)
    print("   LONG REVERSAL DAILY - WYCKOFF ACCUMULATION METHOD")
    print("="*60)
    print("\n📊 Wyckoff Accumulation Pattern Detection:")
    print("   • SC (Selling Climax) - High volume selloff")
    print("   • ST-A (Secondary Test) - Low volume retest")
    print("   • SPRING - False breakdown below support")
    print("   • SOS (Sign of Strength) - Breakout with volume")
    print("   • Volume Profile Analysis (HVN/LVN)")
    print("   • Phase Identification (A-E)")
    print("   • Enhanced 10-point Scoring System")
    print("   • FNO Liquid Stock Focus")
    print("\n" + "="*60)
    print(f"👤 Using credentials for: {user_name}")
    print(f"📁 Reading tickers from: Ticker.xlsx")
    print("="*60 + "\n")

    result = main()
    sys.exit(result)