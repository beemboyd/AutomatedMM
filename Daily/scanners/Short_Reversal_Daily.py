#!/usr/bin/env python
# Short_Reversal_Daily.py - Filter stocks based on higher probability SHORT reversal criteria with Sector information:
# 1. Al Brooks L2 (second leg) bar counting for bearish setups
# 2. Failed bull breakouts and double tops
# 3. Bear flags and wedge reversals
# 4. Strong bearish bars with follow-through
# 5. Volume expansion on bearish moves
# 6. Resistance rejection patterns

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

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "short_reversal_daily.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Short Reversal Daily Analysis with Al Brooks L2 Patterns")
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
RESULTS_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "results-s")  # Short results directory
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
# Calculate Indicators for Bearish Analysis
# -----------------------------
def calculate_indicators(daily_data):
    """Calculate indicators for bearish reversal detection with Al Brooks patterns"""
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
    
    # Bearish bar identification
    df['BearishBar'] = df['Close'] < df['Open']
    df['StrongBearishBar'] = (df['Close'] < df['Open']) & (df['BodyPercent'] > 60)
    
    # Calculate volume indicators for confirmation
    df['AvgVolume20'] = df['Volume'].rolling(window=20).mean()
    df['VolumeRatio'] = df['Volume'] / df['AvgVolume20']
    
    # Calculate momentum indicators
    df['ROC5'] = ((df['Close'] - df['Close'].shift(5)) / df['Close'].shift(5)) * 100
    df['ROC10'] = ((df['Close'] - df['Close'].shift(10)) / df['Close'].shift(10)) * 100
    
    # Al Brooks specific patterns
    # L2 (Second Leg) identification
    df['HigherHigh'] = df['High'] > df['High'].shift(1)
    df['LowerLow'] = df['Low'] < df['Low'].shift(1)
    df['LowerHigh'] = df['High'] < df['High'].shift(1)
    df['HigherLow'] = df['Low'] > df['Low'].shift(1)
    
    # Failed breakout detection
    df['FailedBullBreakout'] = (df['High'] > df['LastSwingHigh']) & (df['Close'] < df['LastSwingHigh'])
    
    # Double top pattern
    df['PotentialDoubleTop'] = False
    for i in range(10, len(df)):
        # Look for two similar highs within 10 bars
        recent_highs = df['High'].iloc[i-10:i]
        current_high = df['High'].iloc[i]
        if len(recent_highs[abs(recent_highs - current_high) / current_high < 0.01]) >= 2:
            df.loc[df.index[i], 'PotentialDoubleTop'] = True
    
    # Bear flag detection (downtrend followed by small consolidation)
    df['BearFlag'] = False
    for i in range(5, len(df)):
        # Check if we had a strong down move followed by tight consolidation
        if i >= 10:
            prior_move = df['Close'].iloc[i-10] - df['Close'].iloc[i-5]
            recent_range = df['High'].iloc[i-5:i].max() - df['Low'].iloc[i-5:i].min()
            if prior_move < -0.05 * df['Close'].iloc[i-10] and recent_range < df['ATR'].iloc[i]:
                df.loc[df.index[i], 'BearFlag'] = True
    
    # Calculate previous bar values for breakout detection
    df['PrevHigh'] = df['High'].shift(1)
    df['PrevLow'] = df['Low'].shift(1)
    df['PrevClose'] = df['Close'].shift(1)
    df['PrevOpen'] = df['Open'].shift(1)
    
    return df

# -----------------------------
# Al Brooks L2 Pattern Detection for Shorts
# -----------------------------
def detect_al_brooks_l2_short(data):
    """
    Detect Al Brooks L2 (second leg) SHORT patterns:
    1. Failed second leg up (L2 failure)
    2. Double top or lower high
    3. Strong bear bar after failure
    4. Resistance rejection
    5. Bear flag breakdown
    
    Returns a dictionary with pattern details if found, None otherwise
    """
    if data is None or data.empty or len(data) < 20:
        return None

    # Get last several bars for pattern analysis
    last_10_bars = data.tail(10)
    last_5_bars = data.tail(5)
    last_3_bars = data.tail(3)
    last_bar = data.iloc[-1]
    prev_bar = data.iloc[-2]

    # Check for bearish L2 patterns
    bearish_pattern = detect_bearish_l2_pattern(data, last_10_bars, last_5_bars, last_3_bars, last_bar, prev_bar)
    if bearish_pattern:
        return bearish_pattern

    return None

def detect_bearish_l2_pattern(data, last_10_bars, last_5_bars, last_3_bars, last_bar, prev_bar):
    """Detect bearish L2 (second leg) pattern for short entries"""
    
    # 1. Failed second leg up (L2 failure) - lower high after initial high
    lower_high_pattern = False
    if len(data) >= 20:
        recent_swing_highs = []
        for i in range(-20, -1):
            if i >= -len(data) + 1:
                if data.iloc[i]['High'] > data.iloc[i-1]['High'] and data.iloc[i]['High'] > data.iloc[i+1]['High']:
                    recent_swing_highs.append((i, data.iloc[i]['High']))
        
        if len(recent_swing_highs) >= 2:
            # Check if most recent swing high is lower than previous
            if recent_swing_highs[-1][1] < recent_swing_highs[-2][1]:
                lower_high_pattern = True
    
    # 2. Double top pattern detection
    double_top = last_bar['PotentialDoubleTop']
    
    # 3. Failed bull breakout
    failed_breakout = last_bar['FailedBullBreakout'] or prev_bar['FailedBullBreakout']
    
    # 4. Strong bearish bars (at least 2 of last 3 bars are bearish)
    bearish_bars = sum([bar['BearishBar'] for _, bar in last_3_bars.iterrows()])
    strong_bearish_bars = sum([bar['StrongBearishBar'] for _, bar in last_3_bars.iterrows()])
    multiple_bear_bars = bearish_bars >= 2
    
    # 5. Resistance rejection (close below resistance after testing)
    resistance_rejection = last_bar['High'] >= last_bar['LastSwingHigh'] and last_bar['Close'] < last_bar['LastSwingHigh']
    
    # 6. Bear flag breakdown
    bear_flag_breakdown = last_bar['BearFlag'] and last_bar['Close'] < prev_bar['Low']
    
    # 7. Volume expansion on bearish moves
    volume_expansion = last_bar['VolumeRatio'] > 1.3 and last_bar['BearishBar']
    
    # 8. Trend alignment (bearish)
    trend_bearish = last_bar['Close'] < last_bar['SMA20'] and last_bar['SMA20'] < last_bar['SMA50']
    
    # 9. Momentum confirmation
    negative_momentum = last_bar['ROC5'] < -1  # Negative momentum
    
    # 10. Price action confirmation (close in lower third of range)
    lower_range_close = (last_bar['Close'] - last_bar['Low']) / (last_bar['High'] - last_bar['Low']) < 0.33
    
    # 11. Wedge top pattern (converging highs with bearish resolution)
    wedge_top = False
    if len(last_5_bars) == 5:
        highs = last_5_bars['High'].values
        lows = last_5_bars['Low'].values
        if highs[-1] < highs[0] and lows[-1] > lows[0]:  # Converging pattern
            wedge_top = True
    
    # Combined pattern scoring (need at least 6 out of 11 conditions for high probability)
    conditions = [
        lower_high_pattern,
        double_top,
        failed_breakout,
        multiple_bear_bars,
        resistance_rejection,
        bear_flag_breakdown,
        volume_expansion,
        trend_bearish,
        negative_momentum,
        lower_range_close,
        wedge_top
    ]
    
    score = sum(conditions)
    
    if score >= 6:  # High probability threshold for shorts
        # Calculate stop loss above recent swing high
        atr_multiplier = 2.0  # Tighter stop for shorts
        stop_loss = last_bar['Close'] + (atr_multiplier * last_bar['ATR'])
        
        # Alternative stop: above recent swing high
        swing_high_stop = last_bar['LastSwingHigh'] + (0.5 * last_bar['ATR'])
        
        # Use the higher of the two stops for safety
        final_stop = max(stop_loss, swing_high_stop)
        
        # Calculate targets
        risk = final_stop - last_bar['Close']
        target1 = last_bar['Close'] - (2 * risk)  # 1:2 risk-reward
        target2 = last_bar['Close'] - (3 * risk)  # 1:3 risk-reward
        
        # Determine primary pattern
        if lower_high_pattern and failed_breakout:
            pattern_name = "L2_Failed_Second_Leg"
            description = "Failed second leg up (L2) with resistance rejection"
        elif double_top:
            pattern_name = "Double_Top_Reversal"
            description = "Double top pattern with bearish confirmation"
        elif bear_flag_breakdown:
            pattern_name = "Bear_Flag_Breakdown"
            description = "Bear flag pattern breaking down"
        elif wedge_top:
            pattern_name = "Wedge_Top_Reversal"
            description = "Rising wedge reversal pattern"
        else:
            pattern_name = "Bearish_L2_Reversal"
            description = "Multiple bearish signals with L2 characteristics"
        
        return {
            'pattern': pattern_name,
            'description': description,
            'direction': 'SHORT',
            'score': score,
            'max_score': 11,
            'conditions_met': {
                'lower_high_pattern': lower_high_pattern,
                'double_top': double_top,
                'failed_breakout': failed_breakout,
                'multiple_bear_bars': multiple_bear_bars,
                'resistance_rejection': resistance_rejection,
                'bear_flag_breakdown': bear_flag_breakdown,
                'volume_expansion': volume_expansion,
                'trend_bearish': trend_bearish,
                'negative_momentum': negative_momentum,
                'lower_range_close': lower_range_close,
                'wedge_top': wedge_top
            },
            'stop_loss': final_stop,
            'entry_price': last_bar['Close'],
            'target1': target1,
            'target2': target2,
            'resistance_level': last_bar['LastSwingHigh'],
            'support_level': last_bar['LastSwingLow'],
            'volume_ratio': last_bar['VolumeRatio'],
            'momentum_5d': last_bar['ROC5'],
            'atr': last_bar['ATR'],
            'strong_bear_bars': strong_bearish_bars
        }
    
    return None

# -----------------------------
# Process Single Ticker
# -----------------------------
def process_ticker(ticker):
    """Process a single ticker for bearish L2 patterns"""
    logger.info(f"Processing {ticker} for SHORT patterns")
    
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
            
        # Detect bearish L2 pattern
        bearish_pattern = detect_al_brooks_l2_short(daily_with_indicators)
        
        if bearish_pattern is None:
            logger.info(f"{ticker} - No high probability SHORT pattern detected")
            return None
        
        # Get the most recent values
        last_bar = daily_with_indicators.iloc[-1]
        
        # Calculate risk and reward
        entry_price = bearish_pattern['entry_price']
        stop_loss = bearish_pattern['stop_loss']
        target1 = bearish_pattern['target1']
        target2 = bearish_pattern['target2']
        
        # Calculate risk metrics
        risk = stop_loss - entry_price  # Risk is positive for shorts
        reward1 = entry_price - target1
        
        # Calculate risk-reward ratio
        if risk > 0:
            risk_reward_ratio = reward1 / risk
        else:
            risk_reward_ratio = 0
        
        # Get sector information
        sector = get_sector_for_ticker(ticker)
        
        # Log the findings
        logger.info(f"{ticker} - High Probability SHORT Pattern Detected!")
        logger.info(f"{ticker} - Pattern: {bearish_pattern['pattern']}")
        logger.info(f"{ticker} - Score: {bearish_pattern['score']}/{bearish_pattern['max_score']}")
        logger.info(f"{ticker} - Entry: {entry_price:.2f}, Stop: {stop_loss:.2f}, Target1: {target1:.2f}")
        logger.info(f"{ticker} - Sector: {sector}")
        
        # Prepare result
        result = {
            'Ticker': ticker,
            'Sector': sector,
            'Pattern': bearish_pattern['pattern'],
            'Direction': bearish_pattern['direction'],
            'Score': f"{bearish_pattern['score']}/{bearish_pattern['max_score']}",
            'Entry_Price': entry_price,
            'Stop_Loss': stop_loss,
            'Target1': target1,
            'Target2': target2,
            'Risk': risk,
            'Risk_Reward_Ratio': risk_reward_ratio,
            'Volume_Ratio': bearish_pattern['volume_ratio'],
            'Momentum_5D': bearish_pattern['momentum_5d'],
            'ATR': bearish_pattern['atr'],
            'Description': bearish_pattern['description'],
            'Strong_Bear_Bars': bearish_pattern['strong_bear_bars'],
            'Resistance_Level': bearish_pattern['resistance_level'],
            'Support_Level': bearish_pattern['support_level'],
            'Conditions_Met': str(bearish_pattern['conditions_met'])
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
# Generate HTML Report for Shorts
# -----------------------------
def generate_html_report(filtered_df, output_file, scanner_file):
    """Generate an HTML report with the filtered short candidates"""
    today = datetime.datetime.now()
    formatted_date = today.strftime("%d-%m-%Y")
    formatted_time = today.strftime("%H:%M")

    # HTML template with bearish styling
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Short Reversal Daily Filter - {formatted_date}</title>
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
                background-color: #95a5a6;
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
                background-color: #ffe8e8;
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
            .bear-indicator {{
                color: #e74c3c;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <h1>📉 Short Reversal Daily Filter - Al Brooks L2 Patterns</h1>
        <div class="header-info">
            <div>Date: {formatted_date} | Time: {formatted_time}</div>
            <div>Filtered from: Ticker.xlsx | SHORT ONLY | L2 & Bearish Patterns</div>
        </div>

        <h2>High Probability Short Patterns ({len(filtered_df)} matches)</h2>
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
                    <th>Pattern</th>
                    <th>Score</th>
                    <th>Entry Price</th>
                    <th>Stop Loss</th>
                    <th>Target 1</th>
                    <th>Risk:Reward</th>
                    <th>Bear Bars</th>
                </tr>
            </thead>
            <tbody>
    """

    # Add rows for each ticker
    for idx, row in filtered_df.iterrows():
        html_content += f"""
            <tr>
                <td>{row['Ticker']}</td>
                <td><span class="sector-badge">{row['Sector']}</span></td>
                <td>{row['Pattern']}</td>
                <td><span class="bear-indicator">{row['Score']}</span></td>
                <td>₹{row['Entry_Price']:.2f}</td>
                <td>₹{row['Stop_Loss']:.2f}</td>
                <td>₹{row['Target1']:.2f}</td>
                <td>{row['Risk_Reward_Ratio']:.2f}</td>
                <td class="bear-indicator">{row['Strong_Bear_Bars']}</td>
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
                </div>
                <div>
                    <span class="ticker-direction">SHORT</span>
                    <span class="score-badge">Score: {row['Score']}</span>
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
                    <div class="detail-label">Volume Ratio</div>
                    <div class="detail-value">{row['Volume_Ratio']:.2f}x</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">5-Day Momentum</div>
                    <div class="detail-value bear-indicator">{row['Momentum_5D']:.2f}%</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Strong Bear Bars</div>
                    <div class="detail-value bear-indicator">{row['Strong_Bear_Bars']}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Resistance Level</div>
                    <div class="detail-value">₹{row['Resistance_Level']:.2f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Support Level</div>
                    <div class="detail-value">₹{row['Support_Level']:.2f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">ATR (14)</div>
                    <div class="detail-value">₹{row['ATR']:.2f}</div>
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
            <p>Generated on {formatted_date} at {formatted_time} | Short Reversal Daily Filter - Al Brooks L2 Patterns</p>
            <p><strong>Note:</strong> These are high probability short setups based on Al Brooks L2 (second leg) patterns and bearish confirmations.</p>
            <p><strong>Risk Warning:</strong> Short selling involves significant risk. Ensure proper risk management and position sizing.</p>
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
    """Main function to filter tickers for high probability SHORT patterns"""
    logger.info("Short Reversal Daily filter with Al Brooks L2 Patterns")
    
    start_time = time.time()

    try:
        # Read the tickers
        tickers = read_ticker_file()
        if not tickers:
            logger.error("No tickers found, exiting")
            return 1
        
        logger.info(f"Starting SHORT pattern analysis for {len(tickers)} tickers")
        
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
        excel_file = os.path.join(RESULTS_DIR, f"Short_Reversal_Daily_{formatted_date}_{formatted_time}.xlsx")
        html_file = os.path.join(HTML_DIR, f"Short_Reversal_Daily_{formatted_date}_{formatted_time.replace('_', '-')}.html")
        
        if results:
            # Convert to DataFrame
            results_df = pd.DataFrame(results)
            
            # Sort by Score (descending) then by Risk-Reward ratio (descending)
            results_df = results_df.sort_values(by=['Score', 'Risk_Reward_Ratio'], ascending=[False, False])
            
            # Round numeric columns for better readability
            numeric_cols = ['Entry_Price', 'Stop_Loss', 'Target1', 'Target2', 'Risk', 'Risk_Reward_Ratio', 
                          'Volume_Ratio', 'Momentum_5D', 'ATR', 'Resistance_Level', 'Support_Level']
            for col in numeric_cols:
                if col in results_df.columns:
                    results_df[col] = results_df[col].astype(float).round(2)
            
            # Reorder columns to put Sector after Ticker
            cols = results_df.columns.tolist()
            cols.remove('Sector')
            cols.insert(1, 'Sector')
            results_df = results_df[cols]
            
            # Write to Excel
            results_df.to_excel(excel_file, index=False)
            logger.info(f"Successfully wrote {len(results_df)} SHORT candidates to {excel_file}")
            
            # Generate HTML report
            html_output = generate_html_report(results_df, html_file, "Ticker.xlsx")
            logger.info(f"Generated HTML report at {html_output}")
            
            # Open the HTML report in the default browser
            try:
                webbrowser.open('file://' + os.path.abspath(html_output))
                logger.info(f"Opened HTML report in browser")
            except Exception as e:
                logger.warning(f"Could not open browser automatically: {e}")
            
            # Print summary to console
            print("\n===== Short Reversal Daily Results =====")
            print(f"Found {len(results_df)} high probability SHORT patterns")
            
            # Print sector summary
            sector_counts = results_df['Sector'].value_counts()
            print("\nSector Distribution:")
            for sector, count in sector_counts.items():
                print(f"  {sector}: {count} stocks")
            
            # Print pattern summary
            pattern_counts = results_df['Pattern'].value_counts()
            print("\nPattern Distribution:")
            for pattern, count in pattern_counts.items():
                print(f"  {pattern}: {count} stocks")
            
            print("\nTop 5 SHORT patterns by score:")
            for idx, row in results_df.head(5).iterrows():
                print(f"{row['Ticker']} ({row['Sector']}): {row['Pattern']}, Score {row['Score']}, Entry ₹{row['Entry_Price']:.2f}, SL ₹{row['Stop_Loss']:.2f}, R:R {row['Risk_Reward_Ratio']:.2f}")

            print(f"\nDetailed results saved to: {excel_file}")
            print(f"HTML report opened in browser: {html_file}")
        else:
            # Create empty Excel with columns
            empty_cols = ['Ticker', 'Sector', 'Pattern', 'Direction', 'Score', 'Entry_Price', 'Stop_Loss', 
                          'Target1', 'Target2', 'Risk', 'Risk_Reward_Ratio', 'Volume_Ratio', 'Momentum_5D', 
                          'ATR', 'Description', 'Strong_Bear_Bars', 'Resistance_Level', 'Support_Level', 'Conditions_Met']
            pd.DataFrame(columns=empty_cols).to_excel(excel_file, index=False)
            
            # Generate empty HTML report
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Short Reversal Daily Filter - {formatted_date}</title>
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
                <h1>📉 Short Reversal Daily Filter - Al Brooks L2 Patterns</h1>
                <div class="no-results">
                    <h2>No High Probability SHORT Patterns Found</h2>
                    <p>No tickers matched the high probability SHORT criteria in today's scan.</p>
                    <p>The filter searched for BEARISH patterns with:</p>
                    <ul style="display: inline-block; text-align: left;">
                        <li>Failed second leg up (L2 failure)</li>
                        <li>Double tops and lower highs</li>
                        <li>Failed bull breakouts</li>
                        <li>Bear flags and wedge reversals</li>
                        <li>Multiple strong bearish bars</li>
                        <li>Resistance rejection patterns</li>
                        <li>Score of 6/11 or higher for high probability</li>
                    </ul>
                    <p><strong>Note:</strong> High probability SHORT setups require multiple bearish confirmations.</p>
                </div>
                <div style="margin-top: 50px; color: #999;">
                    <p>Generated on {formatted_date} at {formatted_time.replace('_', ':')} | Short Reversal Daily Filter</p>
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
                
            logger.info(f"No high probability SHORT patterns found. Empty output files created at {excel_file} and {html_file}")
            print("\nNo high probability SHORT patterns found.")
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
    print("\n=====================================")
    print("Short Reversal Daily Filter")
    print("=====================================")
    print("Finding high probability SHORT setups:")
    print("1. Al Brooks L2 (second leg) patterns")
    print("2. Failed bull breakouts & double tops")
    print("3. Bear flags and wedge reversals")
    print("4. Multiple strong bearish bars")
    print("5. Resistance rejection patterns")
    print("6. Volume expansion on bearish moves")
    print("=====================================")
    print(f"Using credentials for user: {user_name}")
    print("=====================================\n")

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