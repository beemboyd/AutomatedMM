#!/usr/bin/env python
# Long_Reversal_D_SMC.py - Enhanced reversal scanner with Smart Money Concepts (SMC)
# Incorporates: BOS, CHoCH, Liquidity Sweeps, Order Blocks, Fair Value Gaps
# Provides optimal entry points, stop loss levels, and take profit zones

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
                                       "logs", "long_reversal_d_smc.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Long Reversal Daily SMC Analysis - Smart Money Concepts Enhanced")
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
    df['LastSwingHigh'] = df['SwingHigh'].fillna(method='ffill')
    df['LastSwingLow'] = df['SwingLow'].fillna(method='ffill')
    
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
# SMC FUNCTIONS - Market Structure
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

def detect_market_structure(df):
    """Detect BOS (Break of Structure) and CHoCH (Change of Character)"""
    swing_highs, swing_lows = identify_swing_points(df)
    
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return None
    
    # Get last few swing points
    last_high = swing_highs[-1]
    prev_high = swing_highs[-2] if len(swing_highs) > 1 else None
    last_low = swing_lows[-1]
    prev_low = swing_lows[-2] if len(swing_lows) > 1 else None
    
    # Current price
    current_price = df.iloc[-1]['Close']
    
    # Detect BOS (Break of Structure)
    bos_bullish = False
    if prev_high and current_price > prev_high['price']:
        bos_bullish = True
    
    # Detect CHoCH (Change of Character)
    choch_bullish = False
    if len(swing_lows) >= 3:
        # Check if we have higher lows (bullish structure)
        if swing_lows[-1]['price'] > swing_lows[-2]['price'] and swing_lows[-2]['price'] > swing_lows[-3]['price']:
            choch_bullish = True
    
    return {
        'bos_bullish': bos_bullish,
        'choch_bullish': choch_bullish,
        'last_swing_high': last_high['price'] if last_high else None,
        'last_swing_low': last_low['price'] if last_low else None,
        'prev_swing_high': prev_high['price'] if prev_high else None,
        'prev_swing_low': prev_low['price'] if prev_low else None
    }

# -----------------------------
# SMC FUNCTIONS - Liquidity
# -----------------------------
def find_liquidity_zones(df, tolerance=0.002):
    """Find liquidity zones (equal highs/lows) and sweeps"""
    liquidity_zones = []
    
    # Find equal highs (liquidity above)
    for i in range(len(df) - 20, max(0, len(df) - 100), -1):
        current_high = df.iloc[i]['High']
        for j in range(i - 1, max(0, i - 20), -1):
            if abs(df.iloc[j]['High'] - current_high) / current_high <= tolerance:
                liquidity_zones.append({
                    'type': 'equal_high',
                    'price': current_high,
                    'strength': 2  # Number of touches
                })
                break
    
    # Find equal lows (liquidity below)
    for i in range(len(df) - 20, max(0, len(df) - 100), -1):
        current_low = df.iloc[i]['Low']
        for j in range(i - 1, max(0, i - 20), -1):
            if abs(df.iloc[j]['Low'] - current_low) / current_low <= tolerance:
                liquidity_zones.append({
                    'type': 'equal_low',
                    'price': current_low,
                    'strength': 2
                })
                break
    
    return liquidity_zones

def detect_liquidity_sweep(df, liquidity_zones):
    """Detect if recent price action swept liquidity"""
    if len(df) < 5 or not liquidity_zones:
        return None
    
    last_bars = df.tail(5)
    
    for zone in liquidity_zones:
        if zone['type'] == 'equal_low':
            # Check for sweep below and recovery
            for i in range(len(last_bars) - 1):
                if last_bars.iloc[i]['Low'] < zone['price'] and last_bars.iloc[i+1]['Close'] > zone['price']:
                    return {
                        'type': 'bullish_sweep',
                        'swept_level': zone['price'],
                        'sweep_low': last_bars.iloc[i]['Low']
                    }
    
    return None

# -----------------------------
# SMC FUNCTIONS - Order Blocks
# -----------------------------
def identify_order_blocks(df, lookback=20):
    """Identify bullish order blocks (last down candle before up move)"""
    order_blocks = []
    
    for i in range(len(df) - 3, max(len(df) - lookback, 0), -1):
        # Check for bearish candle
        if df.iloc[i]['Close'] < df.iloc[i]['Open']:
            # Check if next candles are bullish
            if (df.iloc[i+1]['Close'] > df.iloc[i+1]['Open'] and 
                df.iloc[i+2]['Close'] > df.iloc[i+2]['Open']):
                
                # Check for significant move
                move_size = (df.iloc[i+2]['Close'] - df.iloc[i]['Low']) / df.iloc[i]['Low']
                if move_size > 0.02:  # 2% move
                    # Check volume confirmation
                    if df.iloc[i+1]['VolumeRatio'] > 1.2 or df.iloc[i+2]['VolumeRatio'] > 1.2:
                        order_blocks.append({
                            'index': i,
                            'high': df.iloc[i]['High'],
                            'low': df.iloc[i]['Low'],
                            'mid': (df.iloc[i]['High'] + df.iloc[i]['Low']) / 2,
                            'volume_ratio': max(df.iloc[i+1]['VolumeRatio'], df.iloc[i+2]['VolumeRatio']),
                            'strength': move_size
                        })
    
    # Return the most recent valid order block
    if order_blocks:
        return order_blocks[0]
    return None

def check_order_block_mitigation(df, order_block):
    """Check if price has returned to test/mitigate the order block"""
    if not order_block:
        return False
    
    current_price = df.iloc[-1]['Close']
    ob_mid = order_block['mid']
    
    # Check if price is within the order block zone
    if order_block['low'] <= current_price <= order_block['high']:
        return True
    
    # Check if price is near the order block (within 1%)
    if abs(current_price - ob_mid) / ob_mid <= 0.01:
        return True
    
    return False

# -----------------------------
# SMC FUNCTIONS - Fair Value Gaps
# -----------------------------
def calculate_fair_value_gaps(df, min_gap_size=0.001):
    """Identify Fair Value Gaps (imbalances) in price action"""
    fvgs = []
    
    for i in range(2, len(df)):
        # Bullish FVG: Gap between previous high and current low
        gap_size = (df.iloc[i]['Low'] - df.iloc[i-2]['High']) / df.iloc[i-2]['High']
        if gap_size > min_gap_size:
            fvgs.append({
                'type': 'bullish',
                'top': df.iloc[i]['Low'],
                'bottom': df.iloc[i-2]['High'],
                'mid': (df.iloc[i]['Low'] + df.iloc[i-2]['High']) / 2,
                'index': i
            })
    
    # Return most recent FVG if any
    if fvgs:
        return fvgs[-1]
    return None

# -----------------------------
# SMC FUNCTIONS - Entry/Exit Optimization
# -----------------------------
def determine_optimal_entry(df, order_block, fvg, market_structure):
    """Calculate optimal entry based on SMC confluence"""
    current_price = df.iloc[-1]['Close']
    last_low = df.iloc[-1]['Low']
    last_high = df.iloc[-1]['High']
    entries = []
    
    # Order Block entry (only if price is near or within OB)
    if order_block:
        ob_mid = order_block['mid']
        # Only consider OB if it's within reasonable range (5% of current price)
        if abs(ob_mid - current_price) / current_price <= 0.05:
            entries.append({
                'price': ob_mid,
                'reason': 'Order Block Midpoint',
                'strength': order_block['strength']
            })
    
    # FVG entry (only if price is near FVG)
    if fvg:
        fvg_mid = fvg['mid']
        # Only consider FVG if it's within reasonable range
        if abs(fvg_mid - current_price) / current_price <= 0.03:
            entries.append({
                'price': fvg_mid,
                'reason': 'Fair Value Gap Fill',
                'strength': 0.5
            })
    
    # Fibonacci OTE (62-79% retracement)
    if market_structure and market_structure['last_swing_high'] and market_structure['last_swing_low']:
        swing_range = market_structure['last_swing_high'] - market_structure['last_swing_low']
        fib_62 = market_structure['last_swing_low'] + (swing_range * 0.62)
        fib_79 = market_structure['last_swing_low'] + (swing_range * 0.79)
        fib_mid = (fib_62 + fib_79) / 2
        
        # Only use Fib if price is near these levels
        if last_low <= fib_mid <= last_high * 1.02:
            entries.append({
                'price': fib_mid,
                'reason': 'Fibonacci OTE Zone',
                'strength': 0.7
            })
    
    # If we have valid entries, select the best one
    if entries:
        # Filter entries that are too far from current price (>3% away)
        valid_entries = [e for e in entries if abs(e['price'] - current_price) / current_price <= 0.03]
        
        if valid_entries:
            # Sort by strength and select best
            best_entry = max(valid_entries, key=lambda x: x['strength'])
            return best_entry['price'], best_entry['reason']
    
    # Default to current price or slightly below for limit order
    entry_price = current_price * 0.995  # 0.5% below current price for better fill
    return entry_price, "Current Market Price (Limit Order)"

def set_smc_stop_loss(df, market_structure, order_block, entry_price):
    """Set stop loss based on market structure - ensuring good R:R"""
    current_price = df.iloc[-1]['Close']
    atr = df.iloc[-1]['ATR']
    stops = []
    
    # Below last swing low with buffer
    if market_structure and market_structure['last_swing_low']:
        swing_stop = market_structure['last_swing_low'] - (atr * 0.3)
        # Only use if it provides reasonable risk (not more than 5% from entry)
        if (entry_price - swing_stop) / entry_price <= 0.05:
            stops.append(swing_stop)
    
    # Below order block with small buffer
    if order_block:
        ob_stop = order_block['low'] - (atr * 0.2)
        # Only use if it provides reasonable risk
        if (entry_price - ob_stop) / entry_price <= 0.04:
            stops.append(ob_stop)
    
    # ATR-based stop (tighter for better R:R)
    atr_stop = entry_price - (atr * 1.5)  # Reduced from 2.5 to 1.5 for better R:R
    stops.append(atr_stop)
    
    # Use the highest stop (least risk) for better R:R
    if stops:
        return max(stops)  # Changed from min to max for tighter stop
    
    # Fallback to 2% stop
    return entry_price * 0.98

def calculate_smc_targets(df, entry_price, stop_loss, liquidity_zones, market_structure):
    """Calculate take profit levels based on liquidity and structure"""
    risk = abs(entry_price - stop_loss)
    
    # Ensure risk is valid
    if risk <= 0:
        risk = df.iloc[-1]['ATR'] * 2  # Use 2x ATR as default risk
        stop_loss = entry_price - risk
    
    targets = []
    
    # TP1: Minimum 1.5R or next liquidity level
    above_liquidity = [z['price'] for z in liquidity_zones if z['price'] > entry_price]
    tp1_price = entry_price + (risk * 1.5)  # Minimum 1.5R
    
    if above_liquidity:
        liquidity_tp = min(above_liquidity)
        if liquidity_tp > tp1_price:  # Only use liquidity if it provides better R:R
            tp1_price = liquidity_tp
            tp1_reason = 'Next Liquidity Level'
        else:
            tp1_reason = '1.5R Minimum Target'
    else:
        tp1_reason = '1.5R Target'
    
    targets.append({
        'price': tp1_price,
        'reason': tp1_reason,
        'rr': (tp1_price - entry_price) / risk
    })
    
    # TP2: Minimum 2R or previous high
    tp2_price = entry_price + (risk * 2)  # Minimum 2R
    
    if market_structure and market_structure['prev_swing_high']:
        structure_tp = market_structure['prev_swing_high']
        if structure_tp > tp2_price:  # Only use if better than 2R
            tp2_price = structure_tp
            tp2_reason = 'Previous Swing High'
        else:
            tp2_reason = '2R Target'
    else:
        tp2_reason = '2R Target'
    
    targets.append({
        'price': tp2_price,
        'reason': tp2_reason,
        'rr': (tp2_price - entry_price) / risk
    })
    
    # TP3: 3R or major resistance
    tp3_price = entry_price + (risk * 3)
    
    # Check for major resistance levels
    if market_structure and market_structure['last_swing_high']:
        major_resistance = market_structure['last_swing_high'] * 1.02  # 2% above last high
        if major_resistance > tp3_price:
            tp3_price = major_resistance
            tp3_reason = 'Major Resistance'
        else:
            tp3_reason = '3R Target'
    else:
        tp3_reason = '3R Target'
    
    targets.append({
        'price': tp3_price,
        'reason': tp3_reason,
        'rr': (tp3_price - entry_price) / risk
    })
    
    return targets

# -----------------------------
# SMC Confluence Scoring
# -----------------------------
def score_smc_confluence(market_structure, liquidity_sweep, order_block, fvg, 
                         order_block_mitigated, volume_expansion, momentum):
    """Calculate SMC confluence score (0-100)"""
    score = 0
    factors = []
    
    # Market Structure (30 points)
    if market_structure:
        if market_structure['bos_bullish']:
            score += 15
            factors.append("BOS Confirmed")
        if market_structure['choch_bullish']:
            score += 15
            factors.append("CHoCH Bullish")
    
    # Liquidity (25 points)
    if liquidity_sweep:
        score += 15
        factors.append("Liquidity Sweep")
    
    # Add points for untapped liquidity (will be checked separately)
    # This is placeholder - actual implementation would check liquidity_zones
    
    # Order Blocks (20 points)
    if order_block:
        score += 10
        factors.append("Order Block Present")
        if order_block_mitigated:
            score += 10
            factors.append("OB Mitigation")
    
    # Fair Value Gaps (15 points)
    if fvg:
        score += 10
        factors.append("FVG Present")
        # Check if price respecting FVG would add 5 more points
    
    # Volume & Momentum (10 points)
    if volume_expansion:
        score += 7
        factors.append("Volume Expansion")
    if momentum > 2:
        score += 3
        factors.append("Positive Momentum")
    
    # Confluence bonus (10 points)
    if len(factors) >= 4:
        score += 10
        factors.append("High Confluence")
    
    return score, factors

# -----------------------------
# Multi-Timeframe Analysis Functions
# -----------------------------
def analyze_weekly_trend(weekly_data):
    """Analyze weekly timeframe for major trend and levels"""
    if weekly_data.empty or len(weekly_data) < 20:
        return None
    
    weekly_indicators = calculate_indicators(weekly_data)
    if weekly_indicators is None:
        return None
    
    last_week = weekly_indicators.iloc[-1]
    
    # Determine weekly trend
    weekly_trend = "neutral"
    if last_week['Close'] > last_week['SMA20'] and last_week['SMA20'] > last_week['SMA50']:
        weekly_trend = "bullish"
    elif last_week['Close'] < last_week['SMA20'] and last_week['SMA20'] < last_week['SMA50']:
        weekly_trend = "bearish"
    
    # Get weekly structure
    weekly_structure = detect_market_structure(weekly_indicators)
    
    return {
        'trend': weekly_trend,
        'resistance': last_week['LastSwingHigh'] if 'LastSwingHigh' in last_week else None,
        'support': last_week['LastSwingLow'] if 'LastSwingLow' in last_week else None,
        'structure': weekly_structure,
        'sma20': last_week['SMA20'],
        'sma50': last_week['SMA50']
    }

def analyze_hourly_for_entry(hourly_data, daily_entry_zone):
    """Analyze hourly timeframe for precise entry"""
    if hourly_data.empty or len(hourly_data) < 50:
        return None
    
    hourly_indicators = calculate_indicators(hourly_data)
    if hourly_indicators is None:
        return None
    
    # Look for hourly order blocks near daily entry zone
    hourly_ob = identify_order_blocks(hourly_indicators, lookback=10)
    
    # Check for hourly liquidity sweeps
    hourly_liquidity_zones = find_liquidity_zones(hourly_indicators, tolerance=0.001)
    hourly_sweep = detect_liquidity_sweep(hourly_indicators, hourly_liquidity_zones)
    
    # Find precise entry on hourly
    last_hour = hourly_indicators.iloc[-1]
    hourly_structure = detect_market_structure(hourly_indicators)
    
    # Look for bullish confirmation on hourly
    hourly_bullish = False
    if hourly_structure and hourly_structure['bos_bullish']:
        hourly_bullish = True
    
    # Check if hourly is at/near daily entry zone
    entry_proximity = abs(last_hour['Close'] - daily_entry_zone) / daily_entry_zone <= 0.02
    
    return {
        'bullish_confirmation': hourly_bullish,
        'order_block': hourly_ob,
        'liquidity_sweep': hourly_sweep,
        'at_entry_zone': entry_proximity,
        'last_close': last_hour['Close'],
        'hourly_atr': last_hour['ATR']
    }

# -----------------------------
# Process Single Ticker with SMC
# -----------------------------
def process_ticker_smc(ticker):
    """Process a single ticker for SMC-enhanced reversal patterns with multi-timeframe analysis"""
    logger.info(f"Processing {ticker} with Multi-Timeframe SMC analysis")
    
    try:
        now = datetime.datetime.now()
        
        # Date ranges for different timeframes
        from_date_weekly = (now - relativedelta(months=12)).strftime('%Y-%m-%d')
        from_date_daily = (now - relativedelta(months=6)).strftime('%Y-%m-%d')
        from_date_hourly = (now - relativedelta(days=30)).strftime('%Y-%m-%d')
        to_date = now.strftime('%Y-%m-%d')
        
        # Fetch WEEKLY data for major trend
        weekly_data = fetch_data_kite(ticker, interval_mapping['1w'], from_date_weekly, to_date)
        if weekly_data.empty:
            logger.warning(f"No weekly data available for {ticker}, skipping")
            return None
        
        # Analyze weekly trend
        weekly_analysis = analyze_weekly_trend(weekly_data)
        if not weekly_analysis:
            logger.warning(f"Could not analyze weekly trend for {ticker}")
            return None
        
        # Only proceed if weekly trend is bullish or neutral (not bearish)
        if weekly_analysis['trend'] == 'bearish':
            logger.info(f"{ticker} - Weekly trend is bearish, skipping")
            return None
        
        # Fetch DAILY data for main analysis
        daily_data = fetch_data_kite(ticker, interval_mapping['1d'], from_date_daily, to_date)
        if daily_data.empty:
            logger.warning(f"No daily data available for {ticker}, skipping")
            return None
            
        # Calculate daily indicators
        daily_with_indicators = calculate_indicators(daily_data)
        if daily_with_indicators is None:
            logger.warning(f"Could not calculate indicators for {ticker}, skipping")
            return None
        
        # Fetch HOURLY data for precise entry
        hourly_data = fetch_data_kite(ticker, interval_mapping['1h'], from_date_hourly, to_date)
        if hourly_data.empty:
            logger.warning(f"No hourly data available for {ticker}, using daily only")
            hourly_analysis = None
        else:
            hourly_analysis = None  # Will be calculated after we have daily entry zone
        
        # SMC Analysis on DAILY
        market_structure = detect_market_structure(daily_with_indicators)
        liquidity_zones = find_liquidity_zones(daily_with_indicators)
        liquidity_sweep = detect_liquidity_sweep(daily_with_indicators, liquidity_zones)
        order_block = identify_order_blocks(daily_with_indicators)
        order_block_mitigated = check_order_block_mitigation(daily_with_indicators, order_block)
        fvg = calculate_fair_value_gaps(daily_with_indicators)
        
        # Get current values
        last_bar = daily_with_indicators.iloc[-1]
        volume_expansion = last_bar['VolumeRatio'] > 1.5
        momentum = last_bar['ROC5']
        
        # Calculate SMC Score with weekly trend bonus
        smc_score, confluence_factors = score_smc_confluence(
            market_structure, liquidity_sweep, order_block, fvg,
            order_block_mitigated, volume_expansion, momentum
        )
        
        # Add bonus for weekly trend alignment
        if weekly_analysis['trend'] == 'bullish':
            smc_score += 10
            confluence_factors.append("Weekly Bullish Trend")
        
        # Add bonus for weekly structure
        if weekly_analysis['structure'] and weekly_analysis['structure']['bos_bullish']:
            smc_score += 5
            confluence_factors.append("Weekly BOS")
        
        # Only proceed if score is high enough (40+ for SMC setups)
        if smc_score < 40:
            logger.info(f"{ticker} - SMC Score too low: {smc_score}/100")
            return None
        
        # Determine optimal entry on DAILY
        daily_entry_price, daily_entry_reason = determine_optimal_entry(
            daily_with_indicators, order_block, fvg, market_structure
        )
        
        # Now analyze HOURLY for precise entry if available
        if hourly_data is not None and not hourly_data.empty:
            hourly_analysis = analyze_hourly_for_entry(hourly_data, daily_entry_price)
            
            # Refine entry based on hourly
            if hourly_analysis and hourly_analysis['at_entry_zone']:
                if hourly_analysis['order_block']:
                    # Use hourly order block for more precise entry
                    entry_price = hourly_analysis['order_block']['mid']
                    entry_reason = "Hourly Order Block at Daily Zone"
                    confluence_factors.append("Hourly OB Confluence")
                else:
                    entry_price = hourly_analysis['last_close']
                    entry_reason = "Hourly Confirmation at Daily Zone"
                
                # Add hourly confirmations to score
                if hourly_analysis['bullish_confirmation']:
                    smc_score += 5
                    confluence_factors.append("Hourly BOS")
                if hourly_analysis['liquidity_sweep']:
                    smc_score += 5
                    confluence_factors.append("Hourly Liquidity Sweep")
            else:
                # Use daily entry if hourly not at zone
                entry_price = daily_entry_price
                entry_reason = daily_entry_reason
        else:
            # No hourly data, use daily entry
            entry_price = daily_entry_price
            entry_reason = daily_entry_reason
        
        # Set stop loss using multi-timeframe levels
        stop_loss = set_smc_stop_loss(daily_with_indicators, market_structure, order_block, entry_price)
        
        # Use hourly ATR for tighter stop if available
        if hourly_analysis and hourly_analysis.get('hourly_atr'):
            hourly_stop = entry_price - (hourly_analysis['hourly_atr'] * 2)
            # Use tighter stop if it's reasonable
            if hourly_stop > stop_loss and (entry_price - hourly_stop) / entry_price <= 0.03:
                stop_loss = hourly_stop
                entry_reason += " (Hourly ATR Stop)"
        
        # Calculate targets
        targets = calculate_smc_targets(
            daily_with_indicators, entry_price, stop_loss,
            liquidity_zones, market_structure
        )
        
        # Validate risk-reward ratio - minimum 1:1.5 for TP1
        if not targets or targets[0]['rr'] < 1.5:
            logger.info(f"{ticker} - Risk-Reward too low: {targets[0]['rr']:.2f}R for TP1" if targets else f"{ticker} - No valid targets")
            return None
        
        # Validate that entry price makes sense (not too far from current price)
        current_close = daily_with_indicators.iloc[-1]['Close']
        if abs(entry_price - current_close) / current_close > 0.05:  # More than 5% away
            logger.info(f"{ticker} - Entry price too far from current: Entry={entry_price:.2f}, Current={current_close:.2f}")
            return None
        
        # Validate stop loss is below entry (for long positions)
        if stop_loss >= entry_price:
            logger.info(f"{ticker} - Invalid stop loss: Stop={stop_loss:.2f} >= Entry={entry_price:.2f}")
            return None
        
        # Get sector information
        sector = get_sector_for_ticker(ticker)
        
        # Determine trade quality
        if smc_score >= 70:
            trade_quality = "HIGH"
        elif smc_score >= 50:
            trade_quality = "MEDIUM"
        else:
            trade_quality = "LOW"
        
        # Log the findings
        logger.info(f"{ticker} - Multi-TF SMC Reversal! Score: {smc_score}/100")
        logger.info(f"{ticker} - Weekly: {weekly_analysis['trend']}, Daily: Entry @ {entry_price:.2f}")
        logger.info(f"{ticker} - Confluence: {', '.join(confluence_factors)}")
        
        # Prepare result with multi-timeframe data
        result = {
            'Ticker': ticker,
            'Sector': sector,
            'Weekly_Trend': weekly_analysis['trend'].upper(),
            'SMC_Score': smc_score,
            'Trade_Quality': trade_quality,
            'Entry_Price': entry_price,
            'Entry_Reason': entry_reason,
            'Stop_Loss': stop_loss,
            'TP1': targets[0]['price'] if targets else entry_price * 1.02,
            'TP1_RR': targets[0]['rr'] if targets else 1.5,
            'TP1_Reason': targets[0]['reason'] if targets else "Default",
            'TP2': targets[1]['price'] if len(targets) > 1 else entry_price * 1.04,
            'TP2_RR': targets[1]['rr'] if len(targets) > 1 else 2.0,
            'TP2_Reason': targets[1]['reason'] if len(targets) > 1 else "Default",
            'TP3': targets[2]['price'] if len(targets) > 2 else entry_price * 1.06,
            'TP3_RR': targets[2]['rr'] if len(targets) > 2 else 3.0,
            'TP3_Reason': targets[2]['reason'] if len(targets) > 2 else "Default",
            'Risk': entry_price - stop_loss,
            'Volume_Ratio': last_bar['VolumeRatio'],
            'Momentum_5D': momentum,
            'ATR': last_bar['ATR'],
            'Confluence_Factors': ', '.join(confluence_factors),
            'Weekly_Support': weekly_analysis['support'] if weekly_analysis['support'] else 0,
            'Weekly_Resistance': weekly_analysis['resistance'] if weekly_analysis['resistance'] else 0,
            'BOS': market_structure['bos_bullish'] if market_structure else False,
            'CHoCH': market_structure['choch_bullish'] if market_structure else False,
            'Liquidity_Sweep': liquidity_sweep is not None,
            'Order_Block': order_block is not None,
            'FVG': fvg is not None,
            'Hourly_Confirmation': hourly_analysis['bullish_confirmation'] if hourly_analysis else False
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
# Generate Enhanced HTML Report with SMC
# -----------------------------
def generate_smc_html_report(filtered_df, output_file):
    """Generate an enhanced HTML report with SMC analysis"""
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
        <title>Long Reversal SMC Analysis - {formatted_date}</title>
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
            <h1>📊 Long Reversal Daily - Smart Money Concepts Analysis</h1>
            <div class="header-info">
                <div>Date: {formatted_date} | Time: {formatted_time}</div>
                <div>Enhanced with SMC: BOS, CHoCH, Liquidity Sweeps, Order Blocks, FVGs</div>
            </div>
    """
    
    # Add summary statistics
    if len(filtered_df) > 0:
        avg_score = filtered_df['SMC_Score'].mean()
        high_quality = len(filtered_df[filtered_df['Trade_Quality'] == 'HIGH'])
        medium_quality = len(filtered_df[filtered_df['Trade_Quality'] == 'MEDIUM'])
        
        html_content += f"""
            <div class="summary-stats">
                <div class="stat-card">
                    <div class="stat-value">{len(filtered_df)}</div>
                    <div class="stat-label">Total Setups Found</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{avg_score:.0f}</div>
                    <div class="stat-label">Average SMC Score</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{high_quality}</div>
                    <div class="stat-label">High Quality Trades</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{medium_quality}</div>
                    <div class="stat-label">Medium Quality Trades</div>
                </div>
            </div>
        """
    
    # Add detailed table
    html_content += """
        <h2>📈 Multi-Timeframe SMC Reversal Opportunities</h2>
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Sector</th>
                    <th>Weekly</th>
                    <th>SMC Score</th>
                    <th>Quality</th>
                    <th>Entry</th>
                    <th>Stop Loss</th>
                    <th>TP1 (RR)</th>
                    <th>TP2 (RR)</th>
                    <th>SMC Signals</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # Add rows for each ticker
    for idx, row in filtered_df.iterrows():
        # Create SMC badges
        smc_badges = ""
        if row['BOS']:
            smc_badges += '<span class="smc-badge badge-bos">BOS</span>'
        if row['CHoCH']:
            smc_badges += '<span class="smc-badge badge-choch">CHoCH</span>'
        if row['Liquidity_Sweep']:
            smc_badges += '<span class="smc-badge badge-sweep">SWEEP</span>'
        if row['Order_Block']:
            smc_badges += '<span class="smc-badge badge-ob">OB</span>'
        if row['FVG']:
            smc_badges += '<span class="smc-badge badge-fvg">FVG</span>'
        
        # Quality class
        quality_class = f"quality-{row['Trade_Quality'].lower()}"
        
        # Weekly trend badge color
        weekly_color = "green" if row.get('Weekly_Trend', '') == 'BULLISH' else "orange"
        
        html_content += f"""
            <tr>
                <td><strong>{row['Ticker']}</strong></td>
                <td>{row['Sector']}</td>
                <td><span style="color: {weekly_color}; font-weight: bold;">{row.get('Weekly_Trend', 'N/A')}</span></td>
                <td>
                    {row['SMC_Score']}/100
                    <div class="score-meter">
                        <div class="score-fill score-{row['Trade_Quality'].lower()}" style="width: {row['SMC_Score']}%"></div>
                    </div>
                </td>
                <td><span class="quality-badge {quality_class}">{row['Trade_Quality']}</span></td>
                <td>₹{row['Entry_Price']:.2f}</td>
                <td>₹{row['Stop_Loss']:.2f}</td>
                <td>₹{row['TP1']:.2f} ({row['TP1_RR']:.1f}R)</td>
                <td>₹{row['TP2']:.2f} ({row['TP2_RR']:.1f}R)</td>
                <td>{smc_badges}</td>
            </tr>
        """
    
    html_content += """
            </tbody>
        </table>
    """
    
    # Add detailed cards for each ticker
    html_content += "<h2>📋 Detailed Multi-Timeframe SMC Analysis</h2>"
    
    for idx, row in filtered_df.iterrows():
        # Create SMC indicator badges
        smc_indicators = ""
        if row['BOS']:
            smc_indicators += '<span class="smc-badge badge-bos">BOS ✓</span>'
        if row['CHoCH']:
            smc_indicators += '<span class="smc-badge badge-choch">CHoCH ✓</span>'
        if row['Liquidity_Sweep']:
            smc_indicators += '<span class="smc-badge badge-sweep">Liquidity Sweep ✓</span>'
        if row['Order_Block']:
            smc_indicators += '<span class="smc-badge badge-ob">Order Block ✓</span>'
        if row['FVG']:
            smc_indicators += '<span class="smc-badge badge-fvg">Fair Value Gap ✓</span>'
        
        quality_class = f"quality-{row['Trade_Quality'].lower()}"
        
        html_content += f"""
        <div class="ticker-card">
            <div class="ticker-header">
                <div>
                    <span class="ticker-name">{row['Ticker']}</span>
                    <span style="color: #7f8c8d; margin-left: 15px;">{row['Sector']}</span>
                </div>
                <div>
                    <span class="quality-badge {quality_class}">{row['Trade_Quality']}</span>
                    <span style="margin-left: 15px; font-size: 1.2em; font-weight: bold;">
                        Score: {row['SMC_Score']}/100
                    </span>
                </div>
            </div>
            
            <div class="smc-indicators">
                {smc_indicators}
            </div>
            
            <div style="background-color: #f0f4f8; padding: 10px; border-radius: 8px; margin: 15px 0;">
                <strong>📊 Multi-Timeframe Analysis:</strong>
                <span style="margin-left: 15px;">Weekly: <strong style="color: {'green' if row.get('Weekly_Trend') == 'BULLISH' else 'orange'};">{row.get('Weekly_Trend', 'N/A')}</strong></span>
                <span style="margin-left: 15px;">Daily: <strong>SMC Setup</strong></span>
                <span style="margin-left: 15px;">Hourly: <strong>{'✓ Confirmed' if row.get('Hourly_Confirmation') else 'Pending'}</strong></span>
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
                    <span><strong>TP1:</strong> ₹{row['TP1']:.2f}</span>
                    <span>RR: {row['TP1_RR']:.1f}</span>
                    <span style="color: #7f8c8d;">{row['TP1_Reason']}</span>
                </div>
                <div class="target-row">
                    <span><strong>TP2:</strong> ₹{row['TP2']:.2f}</span>
                    <span>RR: {row['TP2_RR']:.1f}</span>
                    <span style="color: #7f8c8d;">{row['TP2_Reason']}</span>
                </div>
                <div class="target-row">
                    <span><strong>TP3:</strong> ₹{row['TP3']:.2f}</span>
                    <span>RR: {row['TP3_RR']:.1f}</span>
                    <span style="color: #7f8c8d;">{row['TP3_Reason']}</span>
                </div>
            </div>
            
            <div class="confluence-section">
                <strong>Confluence Factors:</strong> {row['Confluence_Factors']}
            </div>
        </div>
        """
    
    # Complete HTML
    html_content += f"""
            <div style="margin-top: 50px; padding: 20px; background-color: #f8f9fa; border-radius: 10px; text-align: center;">
                <p style="color: #7f8c8d;">
                    Generated on {formatted_date} at {formatted_time} | 
                    Long Reversal Daily with Smart Money Concepts
                </p>
                <p style="color: #95a5a6; font-size: 0.9em;">
                    This analysis incorporates institutional trading concepts including market structure analysis,
                    liquidity zones, order blocks, and fair value gaps for enhanced accuracy.
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
    """Main function to filter tickers using SMC analysis"""
    logger.info("Starting Long Reversal Daily SMC Analysis")
    
    start_time = time.time()

    try:
        # Read the tickers
        tickers = read_ticker_file()
        if not tickers:
            logger.error("No tickers found, exiting")
            return 1
        
        logger.info(f"Starting SMC analysis for {len(tickers)} tickers")
        
        # Process each ticker with SMC
        results = []
        for ticker in tickers:
            result = process_ticker_smc(ticker)
            if result:
                results.append(result)
        
        # Create output files with timestamp
        today = datetime.datetime.now()
        formatted_date = today.strftime("%Y%m%d")
        formatted_time = today.strftime("%H%M%S")
        excel_file = os.path.join(RESULTS_DIR, f"Long_Reversal_D_SMC_{formatted_date}_{formatted_time}.xlsx")
        html_file = os.path.join(HTML_DIR, f"Long_Reversal_D_SMC_{formatted_date}_{formatted_time}.html")
        
        if results:
            # Convert to DataFrame
            results_df = pd.DataFrame(results)
            
            # Sort by SMC Score (descending) then by Trade Quality
            quality_order = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
            results_df['Quality_Order'] = results_df['Trade_Quality'].map(quality_order)
            results_df = results_df.sort_values(by=['Quality_Order', 'SMC_Score'], ascending=[False, False])
            results_df = results_df.drop('Quality_Order', axis=1)
            
            # Round numeric columns for better readability
            numeric_cols = ['Entry_Price', 'Stop_Loss', 'TP1', 'TP2', 'TP3', 
                          'Risk', 'Volume_Ratio', 'Momentum_5D', 'ATR',
                          'TP1_RR', 'TP2_RR', 'TP3_RR']
            for col in numeric_cols:
                if col in results_df.columns:
                    results_df[col] = results_df[col].astype(float).round(2)
            
            # Write to Excel
            results_df.to_excel(excel_file, index=False)
            logger.info(f"Successfully wrote {len(results_df)} SMC setups to {excel_file}")
            
            # Generate HTML report
            html_output = generate_smc_html_report(results_df, html_file)
            logger.info(f"Generated SMC HTML report at {html_output}")
            
            # Open the HTML report in the default browser
            try:
                webbrowser.open('file://' + os.path.abspath(html_output))
                logger.info(f"Opened HTML report in browser")
            except Exception as e:
                logger.warning(f"Could not open browser automatically: {e}")
            
            # Print summary to console
            print("\n" + "="*60)
            print("   SMART MONEY CONCEPTS - REVERSAL ANALYSIS RESULTS")
            print("="*60)
            print(f"\n📊 Found {len(results_df)} SMC Reversal Setups")
            
            # Quality breakdown
            quality_counts = results_df['Trade_Quality'].value_counts()
            print("\n🎯 Trade Quality Distribution:")
            for quality, count in quality_counts.items():
                print(f"   {quality}: {count} setups")
            
            # Top setups
            print("\n🏆 Top 5 SMC Setups by Score:")
            for idx, row in results_df.head(5).iterrows():
                smc_signals = []
                if row['BOS']: smc_signals.append("BOS")
                if row['CHoCH']: smc_signals.append("CHoCH")
                if row['Liquidity_Sweep']: smc_signals.append("SWEEP")
                if row['Order_Block']: smc_signals.append("OB")
                if row['FVG']: smc_signals.append("FVG")
                
                print(f"\n   {row['Ticker']} ({row['Sector']})")
                print(f"   Score: {row['SMC_Score']}/100 | Quality: {row['Trade_Quality']}")
                print(f"   Entry: ₹{row['Entry_Price']:.2f} | Stop: ₹{row['Stop_Loss']:.2f}")
                print(f"   Targets: TP1={row['TP1_RR']:.1f}R, TP2={row['TP2_RR']:.1f}R, TP3={row['TP3_RR']:.1f}R")
                print(f"   SMC: {' + '.join(smc_signals)}")

            print(f"\n📁 Results saved to:")
            print(f"   Excel: {excel_file}")
            print(f"   HTML: {html_file}")
        else:
            # Create empty Excel
            empty_cols = ['Ticker', 'Sector', 'SMC_Score', 'Trade_Quality', 'Entry_Price', 
                         'Entry_Reason', 'Stop_Loss', 'TP1', 'TP1_RR', 'TP1_Reason',
                         'TP2', 'TP2_RR', 'TP2_Reason', 'TP3', 'TP3_RR', 'TP3_Reason',
                         'Risk', 'Volume_Ratio', 'Momentum_5D', 'ATR', 'Confluence_Factors',
                         'BOS', 'CHoCH', 'Liquidity_Sweep', 'Order_Block', 'FVG']
            pd.DataFrame(columns=empty_cols).to_excel(excel_file, index=False)
            
            logger.info(f"No SMC reversal patterns found. Empty output created at {excel_file}")
            print("\nNo SMC reversal patterns found meeting the criteria.")
            print(f"Empty results saved to: {excel_file}")
            
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
    print("   LONG REVERSAL DAILY - SMART MONEY CONCEPTS (SMC)")
    print("="*60)
    print("\n📊 Enhanced Reversal Detection using:")
    print("   • BOS (Break of Structure)")
    print("   • CHoCH (Change of Character)")
    print("   • Liquidity Sweeps & Pools")
    print("   • Order Blocks (OB)")
    print("   • Fair Value Gaps (FVG)")
    print("   • Optimal Trade Entry (OTE)")
    print("   • Structure-based Stop Loss")
    print("   • Liquidity-based Take Profits")
    print("\n" + "="*60)
    print(f"👤 Using credentials for: {user_name}")
    print("="*60 + "\n")

    result = main()
    
    # Trigger market regime analysis after successful scan
    if result == 0:
        try:
            import subprocess
            logger.info("Triggering market regime analysis...")
            subprocess.run([
                sys.executable, 
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                            "Market_Regime", "market_regime_analyzer.py")
            ], timeout=60)
        except Exception as e:
            logger.warning(f"Could not trigger market regime analysis: {e}")
    
    sys.exit(result)