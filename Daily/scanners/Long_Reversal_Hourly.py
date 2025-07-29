#!/usr/bin/env python
# Long_Reversal_Daily.py - Filter stocks based on higher probability reversal criteria with Sector information:
# 1. Wait for strong breakout in new direction (confirmed reversal)
# 2. Multiple confirmation bars in new trend
# 3. Break of significant support/resistance with conviction
# 4. Volume expansion on breakout
# 5. Accept wider stops for higher probability (60%+)
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
# import webbrowser  # Not needed for hourly version

# Add parent directories to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "long_reversal_daily.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Long Reversal Daily Analysis with Sector Information")
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
# Calculate Indicators for Higher Probability Analysis
# -----------------------------
def calculate_indicators(daily_data):
    """Calculate indicators for higher probability reversal detection"""
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
# Higher Probability Reversal Pattern Detection 
# -----------------------------
def detect_higher_probability_reversal(data):
    """
    Detect higher probability BULLISH reversal patterns based on  methodology:
    1. Strong breakout in new direction (confirmed reversal)
    2. Multiple confirmation bars
    3. Break of significant support/resistance
    4. Volume expansion
    5. Trend alignment confirmation

    Returns a dictionary with pattern details if found, None otherwise
    NOTE: This version filters for LONG setups only
    """
    if data is None or data.empty or len(data) < 10:
        return None

    # Get last few candles for confirmation
    last_3_bars = data.tail(3)
    last_bar = data.iloc[-1]
    prev_bar = data.iloc[-2]

    # Check for strong bullish reversal pattern ONLY
    bullish_reversal = detect_bullish_confirmation_pattern(data, last_3_bars, last_bar, prev_bar)
    if bullish_reversal:
        return bullish_reversal

    # Removed bearish reversal detection - LONGS ONLY

    return None

def detect_bullish_confirmation_pattern(data, last_3_bars, last_bar, prev_bar):
    """Detect bullish higher probability reversal pattern"""
    
    # 1. Strong breakout above resistance
    resistance_break = last_bar['Close'] > last_bar['LastSwingHigh']
    strong_close_above_resistance = last_bar['Close'] > (last_bar['LastSwingHigh'] * 1.02)  # 2% above resistance
    
    # 2. Multiple confirmation bars (at least 2 of last 3 bars are bullish)
    bullish_bars = sum([bar['Close'] > bar['Open'] for _, bar in last_3_bars.iterrows()])
    multiple_confirmations = bullish_bars >= 2
    
    # 3. Strong body candles (indicating conviction)
    strong_bodies = last_3_bars['BodyPercent'].mean() > 60
    
    # 4. Volume expansion on breakout
    volume_expansion = last_bar['VolumeRatio'] > 1.5
    
    # 5. Trend alignment (SMA alignment supporting reversal)
    trend_support = last_bar['Close'] > last_bar['SMA20']
    
    # 6. Momentum confirmation
    positive_momentum = last_bar['ROC5'] > 2  # 2% move in 5 days
    
    # 7. Price action confirmation (close in upper half of range)
    upper_range_close = (last_bar['Close'] - last_bar['Low']) / (last_bar['High'] - last_bar['Low']) > 0.7
    
    # Combined pattern scoring (need at least 5 out of 7 conditions)
    conditions = [
        resistance_break,
        multiple_confirmations,
        strong_bodies,
        volume_expansion,
        trend_support,
        positive_momentum,
        upper_range_close
    ]
    
    score = sum(conditions)
    
    if score >= 5:  # High probability threshold
        # Calculate wider stop loss for higher probability trade
        atr_multiplier = 2.5  # Wider stop for higher probability
        stop_loss = last_bar['Close'] - (atr_multiplier * last_bar['ATR'])
        
        # Alternative stop: below recent swing low
        swing_low_stop = last_bar['LastSwingLow'] - (0.5 * last_bar['ATR'])
        
        # Use the wider of the two stops (accepting higher risk for higher probability)
        final_stop = min(stop_loss, swing_low_stop)
        
        return {
            'pattern': 'Higher_Probability_Bull_Reversal',
            'description': 'Confirmed bullish reversal with multiple confirmations',
            'direction': 'LONG',
            'score': score,
            'max_score': 7,
            'conditions_met': {
                'resistance_break': resistance_break,
                'multiple_confirmations': multiple_confirmations,
                'strong_bodies': strong_bodies,
                'volume_expansion': volume_expansion,
                'trend_support': trend_support,
                'positive_momentum': positive_momentum,
                'upper_range_close': upper_range_close
            },
            'stop_loss': final_stop,
            'entry_price': last_bar['Close'],
            'resistance_level': last_bar['LastSwingHigh'],
            'volume_ratio': last_bar['VolumeRatio'],
            'momentum_5d': last_bar['ROC5'],
            'atr': last_bar['ATR']
        }
    
    return None

def detect_bearish_confirmation_pattern(data, last_3_bars, last_bar, prev_bar):
    """Detect bearish higher probability reversal pattern"""
    
    # 1. Strong breakdown below support
    support_break = last_bar['Close'] < last_bar['LastSwingLow']
    strong_close_below_support = last_bar['Close'] < (last_bar['LastSwingLow'] * 0.98)  # 2% below support
    
    # 2. Multiple confirmation bars (at least 2 of last 3 bars are bearish)
    bearish_bars = sum([bar['Close'] < bar['Open'] for _, bar in last_3_bars.iterrows()])
    multiple_confirmations = bearish_bars >= 2
    
    # 3. Strong body candles (indicating conviction)
    strong_bodies = last_3_bars['BodyPercent'].mean() > 60
    
    # 4. Volume expansion on breakdown
    volume_expansion = last_bar['VolumeRatio'] > 1.5
    
    # 5. Trend alignment (SMA alignment supporting reversal)
    trend_support = last_bar['Close'] < last_bar['SMA20']
    
    # 6. Momentum confirmation
    negative_momentum = last_bar['ROC5'] < -2  # -2% move in 5 days
    
    # 7. Price action confirmation (close in lower half of range)
    lower_range_close = (last_bar['Close'] - last_bar['Low']) / (last_bar['High'] - last_bar['Low']) < 0.3
    
    # Combined pattern scoring (need at least 5 out of 7 conditions)
    conditions = [
        support_break,
        multiple_confirmations,
        strong_bodies,
        volume_expansion,
        trend_support,
        negative_momentum,
        lower_range_close
    ]
    
    score = sum(conditions)
    
    if score >= 5:  # High probability threshold
        # Calculate wider stop loss for higher probability trade
        atr_multiplier = 2.5  # Wider stop for higher probability
        stop_loss = last_bar['Close'] + (atr_multiplier * last_bar['ATR'])
        
        # Alternative stop: above recent swing high
        swing_high_stop = last_bar['LastSwingHigh'] + (0.5 * last_bar['ATR'])
        
        # Use the wider of the two stops (accepting higher risk for higher probability)
        final_stop = max(stop_loss, swing_high_stop)
        
        return {
            'pattern': 'Higher_Probability_Bear_Reversal',
            'description': 'Confirmed bearish reversal with multiple confirmations',
            'direction': 'SHORT',
            'score': score,
            'max_score': 7,
            'conditions_met': {
                'support_break': support_break,
                'multiple_confirmations': multiple_confirmations,
                'strong_bodies': strong_bodies,
                'volume_expansion': volume_expansion,
                'trend_support': trend_support,
                'negative_momentum': negative_momentum,
                'lower_range_close': lower_range_close
            },
            'stop_loss': final_stop,
            'entry_price': last_bar['Close'],
            'support_level': last_bar['LastSwingLow'],
            'volume_ratio': last_bar['VolumeRatio'],
            'momentum_5d': last_bar['ROC5'],
            'atr': last_bar['ATR']
        }
    
    return None

# -----------------------------
# Process Single Ticker
# -----------------------------
def process_ticker(ticker):
    """Process a single ticker for higher probability reversal patterns"""
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
            
        # Detect higher probability reversal pattern
        reversal_pattern = detect_higher_probability_reversal(daily_with_indicators)
        
        if reversal_pattern is None:
            logger.info(f"{ticker} - No higher probability LONG reversal pattern detected")
            return None
        
        # Get the most recent values
        last_bar = daily_with_indicators.iloc[-1]
        last_price = last_bar['Close']
        
        # Calculate risk and reward (LONG ONLY)
        entry_price = reversal_pattern['entry_price']
        stop_loss = reversal_pattern['stop_loss']

        # Only LONG calculations since we filter for longs only
        risk = entry_price - stop_loss
        target1 = entry_price + (2 * risk)  # 1:2 risk-reward
        target2 = entry_price + (3 * risk)  # 1:3 risk-reward
        
        # Calculate risk-reward ratio
        if risk > 0:
            risk_reward_ratio = abs(target1 - entry_price) / risk
        else:
            risk_reward_ratio = 0
        
        # Get sector information
        sector = get_sector_for_ticker(ticker)
        
        # Log the findings
        logger.info(f"{ticker} - Higher Probability LONG Reversal Detected!")
        logger.info(f"{ticker} - Pattern Score: {reversal_pattern['score']}/{reversal_pattern['max_score']}")
        logger.info(f"{ticker} - Entry: {entry_price:.2f}, Stop: {stop_loss:.2f}, Target1: {target1:.2f}")
        logger.info(f"{ticker} - Sector: {sector}")
        
        # Prepare result
        result = {
            'Ticker': ticker,
            'Sector': sector,  # Add sector information
            'Pattern': reversal_pattern['pattern'],
            'Direction': reversal_pattern['direction'],
            'Score': f"{reversal_pattern['score']}/{reversal_pattern['max_score']}",
            'Entry_Price': entry_price,
            'Stop_Loss': stop_loss,
            'Target1': target1,
            'Target2': target2,
            'Risk': risk,
            'Risk_Reward_Ratio': risk_reward_ratio,
            'Volume_Ratio': reversal_pattern['volume_ratio'],
            'Momentum_5D': reversal_pattern['momentum_5d'],
            'ATR': reversal_pattern['atr'],
            'Description': reversal_pattern['description'],
            'Conditions_Met': str(reversal_pattern['conditions_met'])
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
# HTML Report Generation Removed for Hourly Version
# -----------------------------

# -----------------------------
# Main Function
# -----------------------------
def main():
    """Main function to filter tickers for higher probability LONG reversals with sector information"""
    logger.info("Long Reversal Daily filter with Sector Information")
    
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
        excel_file = os.path.join(RESULTS_DIR, f"Long_Reversal_Daily_{formatted_date}_{formatted_time}.xlsx")
        html_file = os.path.join(HTML_DIR, f"Long_Reversal_Daily_{formatted_date}_{formatted_time.replace('_', '-')}.html")
        
        if results:
            # Convert to DataFrame
            results_df = pd.DataFrame(results)
            
            # Sort by Score (descending) then by Risk-Reward ratio (descending)
            results_df = results_df.sort_values(by=['Score', 'Risk_Reward_Ratio'], ascending=[False, False])
            
            # Round numeric columns for better readability
            numeric_cols = ['Entry_Price', 'Stop_Loss', 'Target1', 'Target2', 'Risk', 'Risk_Reward_Ratio', 'Volume_Ratio', 'Momentum_5D', 'ATR']
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
            logger.info(f"Successfully wrote {len(results_df)} filtered tickers to {excel_file}")
            
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
            print("\n===== Long Reversal Daily Results with Sector Information =====")
            print(f"Found {len(results_df)} higher probability LONG reversal patterns")
            
            # Print sector summary
            sector_counts = results_df['Sector'].value_counts()
            print("\nSector Distribution:")
            for sector, count in sector_counts.items():
                print(f"  {sector}: {count} stocks")
            
            print("\nTop 5 LONG patterns by score:")
            for idx, row in results_df.head(5).iterrows():
                print(f"{row['Ticker']} ({row['Sector']}): Score {row['Score']}, Entry ₹{row['Entry_Price']:.2f}, SL ₹{row['Stop_Loss']:.2f}, R:R {row['Risk_Reward_Ratio']:.2f}")

            print(f"\nDetailed results saved to: {excel_file}")
            print(f"HTML report opened in browser: {html_file}")
        else:
            # Create empty Excel with columns
            empty_cols = ['Ticker', 'Sector', 'Pattern', 'Direction', 'Score', 'Entry_Price', 'Stop_Loss', 'Target1', 'Target2', 
                          'Risk', 'Risk_Reward_Ratio', 'Volume_Ratio', 'Momentum_5D', 'ATR', 'Description', 'Conditions_Met']
            pd.DataFrame(columns=empty_cols).to_excel(excel_file, index=False)
            
            logger.info(f"No higher probability LONG patterns found. Empty output file created at {excel_file}")
            print("\nNo higher probability LONG reversal patterns found.")
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
    print("\n===================================")
    print("Long Reversal Daily Filter with Sector")
    print("===================================")
    print("Finding higher probability reversal setups (60%+):")
    print("1. Strong breakout confirmation in new direction")
    print("2. Multiple confirmation bars")
    print("3. Break of significant resistance")
    print("4. Volume expansion on breakout")
    print("5. Wider stops for higher probability")
    print("6. Includes Sector information")
    print("===================================")
    print(f"Using credentials for user: {user_name}")
    print("===================================\n")

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