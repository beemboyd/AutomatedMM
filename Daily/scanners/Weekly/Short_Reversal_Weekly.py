#!/usr/bin/env python
# Short_Reversal_Weekly.py - Filter stocks based on higher probability SHORT reversal criteria with Sector information:
# 1. Al Brooks L2 (second leg) bar counting for bearish setups
# 2. Failed bull breakouts and double tops
# 3. Bear flags and wedge reversals
# 4. Strong bearish bars with follow-through
# 5. Volume expansion on bearish moves
# 6. Risk-Reward 1:2 or better

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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                       "logs", "short_reversal_weekly.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Short Reversal Weekly Analysis with Al Brooks L2 Patterns")
    parser.add_argument("-u", "--user", default="Sai", help="User name to use for API credentials (default: Sai)")
    return parser.parse_args()

# Load credentials from Daily/config.ini
def load_daily_config(user_name="Sai"):
    """Load configuration from Daily/config.ini file with user-specific credentials"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config.ini')
    
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
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), "data")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), "results-s")
HTML_DIR = os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), "Detailed_Analysis")

# Ensure directories exist
for dir_path in [RESULTS_DIR, HTML_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# For data retrieval fallback
FALLBACK_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'BT', 'data')

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
    sector_match = sector_df[sector_df['Ticker'].str.upper() == ticker_upper]
    
    if not sector_match.empty:
        return sector_match.iloc[0]['Sector']
    else:
        return "Unknown"

# -----------------------------
# Zerodha Kite Connect Setup
# -----------------------------
kite = KiteConnect(api_key=KITE_API_KEY)
kite.set_access_token(ACCESS_TOKEN)

def get_instruments_data():
    """Get and cache instruments data from Zerodha"""
    if cache.instruments_df is None:
        try:
            cache.instruments_df = pd.DataFrame(kite.instruments())
            logger.info(f"Loaded {len(cache.instruments_df)} instruments from Zerodha")
        except Exception as e:
            logger.error(f"Error loading instruments data: {e}")
            
            # Try to load from backup
            backup_file = os.path.join(DATA_DIR, "instruments_backup.csv")
            try:
                if os.path.exists(backup_file):
                    cache.instruments_df = pd.read_csv(backup_file)
                    logger.info(f"Loaded {len(cache.instruments_df)} instruments from backup")
                else:
                    logger.error(f"No backup instruments file found at {backup_file}")
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
        logger.warning(f"No instruments data available")
        return None

    # Try different exchanges
    ticker_upper = ticker.upper()
    for exchange in ['NSE', 'BSE']:
        mask = (df['tradingsymbol'] == ticker_upper) & (df['exchange'] == exchange)
        filtered = df[mask]
        
        if not filtered.empty:
            token = int(filtered.iloc[0]['instrument_token'])
            cache.instrument_tokens[ticker] = token
            logger.debug(f"Found instrument token {token} for {ticker} on {exchange}")
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
        # Add any other manual mappings here
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
def fetch_data_kite(ticker, interval, from_date, to_date, max_retries=3, retry_delay=1, backoff_factor=2):
    """Fetch historical data from Zerodha Kite with retry mechanism and caching"""
    # Check cache first
    cache_key = f"{ticker}_{interval}_{from_date}_{to_date}"
    if cache_key in cache.data_cache:
        logger.debug(f"Using cached data for {ticker}")
        return cache.data_cache[cache_key]

    # Check for token
    token = get_instrument_token(ticker)
    if token is None:
        logger.warning(f"Instrument token for {ticker} not found.")
        # Try fallback to CSV data if available
        if interval == 'week':
            df = fetch_fallback_data(ticker, interval)
            if not df.empty:
                cache.data_cache[cache_key] = df  # Cache the fallback data
                return df
        return pd.DataFrame()

    from_date = pd.to_datetime(from_date)
    to_date = pd.to_datetime(to_date)
    
    df = pd.DataFrame()

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
                'date': 'Date',
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }, inplace=True)
            df['Date'] = pd.to_datetime(df['Date'])
            df['Ticker'] = ticker

            # Cache the successful result
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
    if interval == 'week':
        logger.info(f"Using fallback data for {ticker} after API failure")
        df = fetch_fallback_data(ticker, interval)
        if not df.empty:
            cache.data_cache[cache_key] = df  # Cache the fallback data
            return df

    return df

def fetch_fallback_data(ticker, interval):
    """Fetch data from CSV files if API fails"""
    try:
        # Check for weekly data file
        if interval == 'week':
            csv_file = os.path.join(FALLBACK_DATA_DIR, f"{ticker}_week.csv")
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
                df.rename(columns=columns_map, inplace=True)
                
                # Convert date column
                df['Date'] = pd.to_datetime(df['Date'])
                
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
                            df[col] = 0
                
                # Sort by date
                df = df.sort_values('Date')
                
                # Add ticker column
                df['Ticker'] = ticker
                
                return df
        
        logger.warning(f"No fallback data available for {ticker} with interval {interval}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error fetching fallback data for {ticker}: {e}")
        return pd.DataFrame()

# -----------------------------
# Calculate Indicators
# -----------------------------
def calculate_indicators(data):
    """Calculate technical indicators for weekly data"""
    if data.empty or len(data) < 50:
        logger.warning("Insufficient data for indicator calculation")
        return None
    
    # Create a copy to avoid SettingWithCopyWarning
    df = data.copy()
    
    # ATR (Average True Range) - 14 periods
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = true_range.rolling(window=14).mean()
    
    # SMA
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=200).mean() if len(df) >= 200 else np.nan
    
    # Volume SMA
    df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
    df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
    
    # Find recent swing points
    df['LastSwingHigh'] = df['High'].rolling(window=10).max()
    df['LastSwingLow'] = df['Low'].rolling(window=10).min()
    
    # Resistance levels
    df['Resistance_10'] = df['High'].rolling(window=10).max()
    df['Resistance_20'] = df['High'].rolling(window=20).max()
    
    # Pattern characteristics
    df['Body'] = df['Close'] - df['Open']
    df['Body_Percent'] = (df['Body'] / df['Open']) * 100
    df['Upper_Shadow'] = df['High'] - df[['Close', 'Open']].max(axis=1)
    df['Lower_Shadow'] = df[['Close', 'Open']].min(axis=1) - df['Low']
    df['Range'] = df['High'] - df['Low']
    
    # Momentum
    df['Momentum_5'] = (df['Close'] / df['Close'].shift(5) - 1) * 100
    df['Momentum_10'] = (df['Close'] / df['Close'].shift(10) - 1) * 100
    
    # Trend identification
    df['Uptrend'] = (df['Close'] > df['SMA20']) & (df['SMA20'] > df['SMA50'])
    
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
    """
    if data is None or len(data) < 20:
        return None
    
    # Get the last few bars for pattern analysis
    last_10_bars = data.tail(10).copy()
    last_5_bars = data.tail(5).copy()
    last_3_bars = data.tail(3).copy()
    last_bar = data.iloc[-1]
    prev_bar = data.iloc[-2] if len(data) > 1 else last_bar
    
    # Call the pattern detection
    bearish_pattern = detect_bearish_l2_pattern(data, last_10_bars, last_5_bars, last_3_bars, last_bar, prev_bar)
    
    return bearish_pattern

def detect_bearish_l2_pattern(data, last_10_bars, last_5_bars, last_3_bars, last_bar, prev_bar):
    """Detect bearish L2 (second leg) pattern for short entries"""
    
    # 1. Failed second leg up (L2 failure) - lower high after initial high
    lower_high_pattern = False
    if len(data) >= 20:
        recent_swing_highs = []
        
        # Find swing highs in last 20 bars
        for i in range(1, min(20, len(data)-1)):
            if (data.iloc[-i]['High'] > data.iloc[-i-1]['High'] and 
                data.iloc[-i]['High'] > data.iloc[-(i-1)]['High']):
                recent_swing_highs.append((i, data.iloc[-i]['High']))
        
        # Check if recent high is lower than previous high
        if len(recent_swing_highs) >= 2:
            if recent_swing_highs[0][1] < recent_swing_highs[1][1]:
                lower_high_pattern = True
    
    # 2. Double top pattern
    double_top = False
    if len(last_10_bars) >= 6:
        high_tolerance = last_bar['ATR'] * 0.2
        highs = last_10_bars['High'].values
        
        # Look for two similar highs
        for i in range(len(highs)-3):
            for j in range(i+2, len(highs)):
                if abs(highs[i] - highs[j]) < high_tolerance:
                    double_top = True
                    break
    
    # 3. Strong bear bar (weekly)
    strong_bear_bar = (
        last_bar['Body'] < 0 and 
        abs(last_bar['Body']) > last_5_bars['Range'].mean() * 0.7 and
        last_bar['Close'] < last_bar['Open'] * 0.99  # At least 1% down
    )
    
    # 4. Failed breakout above resistance
    failed_breakout = (
        prev_bar['High'] > prev_bar['Resistance_10'] and
        last_bar['Close'] < prev_bar['Resistance_10']
    )
    
    # 5. Bear flag or wedge breakdown
    bear_flag = False
    if len(last_5_bars) >= 4:
        # Check for small consolidation after down move, then breakdown
        initial_down = data.iloc[-10:-5]['Close'].mean() > data.iloc[-5:-3]['Close'].mean()
        consolidation = abs(last_5_bars.iloc[:-1]['Body'].mean()) < last_5_bars['ATR'].mean() * 0.3
        breakdown = last_bar['Close'] < last_5_bars['Low'].min()
        bear_flag = initial_down and consolidation and breakdown
    
    # 6. Volume expansion on bearish bar
    volume_surge = last_bar['Volume_Ratio'] > 1.3
    
    # 7. Multiple red bars
    consecutive_red_bars = sum(1 for bar in last_3_bars['Body'] if bar < 0) >= 2
    
    # 8. Below SMA20
    below_sma20 = last_bar['Close'] < last_bar['SMA20']
    
    # 9. Resistance rejection
    resistance_rejection = (
        last_bar['High'] > last_bar['Resistance_10'] * 0.98 and
        last_bar['Close'] < last_bar['Resistance_10'] * 0.97
    )
    
    # 10. Momentum turning negative
    momentum_negative = last_bar['Momentum_5'] < 0 and last_bar['Momentum_10'] < 0
    
    # 11. Recent uptrend failure
    uptrend_failure = (
        data.iloc[-20:-10]['Uptrend'].sum() >= 5 and  # Was in uptrend
        last_5_bars['Uptrend'].sum() <= 2  # No longer in uptrend
    )
    
    # Calculate score
    conditions = [
        lower_high_pattern,
        double_top,
        strong_bear_bar,
        failed_breakout,
        bear_flag,
        volume_surge,
        consecutive_red_bars,
        below_sma20,
        resistance_rejection,
        momentum_negative,
        uptrend_failure
    ]
    
    score = sum(conditions)
    
    if score >= 6:  # High probability threshold for shorts
        # Calculate stop loss above recent swing high
        atr_multiplier = 2.0  # Tighter stop for shorts
        stop_loss = last_bar['Close'] + (atr_multiplier * last_bar['ATR'])
        
        # Alternative stop: above recent swing high
        swing_high_stop = last_bar['LastSwingHigh'] + (0.5 * last_bar['ATR'])
        
        # Use the higher stop for safety
        stop_loss = max(stop_loss, swing_high_stop)
        
        # Calculate targets
        risk = stop_loss - last_bar['Close']
        target1 = last_bar['Close'] - (2 * risk)  # 1:2 R:R
        target2 = last_bar['Close'] - (3 * risk)  # 1:3 R:R
        
        # Pattern naming
        if lower_high_pattern and strong_bear_bar:
            pattern_name = "L2 Failed Second Leg"
        elif double_top and volume_surge:
            pattern_name = "Double Top Breakdown"
        elif failed_breakout and resistance_rejection:
            pattern_name = "Failed Breakout Reversal"
        elif bear_flag and consecutive_red_bars:
            pattern_name = "Bear Flag Breakdown"
        else:
            pattern_name = "Bearish Reversal Setup"
        
        # Description
        reasons = []
        if lower_high_pattern: reasons.append("Lower high")
        if double_top: reasons.append("Double top")
        if strong_bear_bar: reasons.append("Strong bear bar")
        if failed_breakout: reasons.append("Failed breakout")
        if bear_flag: reasons.append("Bear flag")
        if volume_surge: reasons.append("High volume")
        if below_sma20: reasons.append("Below SMA20")
        if resistance_rejection: reasons.append("Resistance rejection")
        
        description = " | ".join(reasons)
        
        return {
            'pattern': pattern_name,
            'description': description,
            'direction': 'SHORT',
            'score': score,
            'max_score': 11,
            'conditions_met': {
                'lower_high_pattern': lower_high_pattern,
                'double_top': double_top,
                'strong_bear_bar': strong_bear_bar,
                'failed_breakout': failed_breakout,
                'bear_flag': bear_flag,
                'volume_surge': volume_surge,
                'consecutive_red_bars': consecutive_red_bars,
                'below_sma20': below_sma20,
                'resistance_rejection': resistance_rejection,
                'momentum_negative': momentum_negative,
                'uptrend_failure': uptrend_failure
            },
            'entry_price': last_bar['Close'],
            'stop_loss': stop_loss,
            'target1': target1,
            'target2': target2,
            'risk': risk,
            'reward1': last_bar['Close'] - target1,
            'risk_reward_ratio': (last_bar['Close'] - target1) / risk if risk > 0 else 0
        }
    
    return None

# -----------------------------
# Process Each Ticker
# -----------------------------
def process_ticker(ticker):
    """Process a single ticker for bearish L2 patterns"""
    logger.info(f"Processing {ticker} for SHORT patterns")
    
    try:
        now = datetime.datetime.now()
        
        # Extended date range for better pattern recognition
        from_date = (now - relativedelta(years=2)).strftime('%Y-%m-%d')
        to_date = now.strftime('%Y-%m-%d')
        
        # Fetch weekly data
        weekly_data = fetch_data_kite(ticker, interval_mapping['1w'], from_date, to_date)
        
        if weekly_data.empty:
            logger.warning(f"No data available for {ticker}")
            return None
            
        # Calculate indicators
        weekly_with_indicators = calculate_indicators(weekly_data)
        
        if weekly_with_indicators is None:
            logger.warning(f"Could not calculate indicators for {ticker}")
            return None
            
        # Detect bearish L2 pattern
        bearish_pattern = detect_al_brooks_l2_short(weekly_with_indicators)
        
        if bearish_pattern is None:
            logger.info(f"{ticker} - No high probability SHORT pattern detected")
            return None
        
        # Get the most recent values
        last_bar = weekly_with_indicators.iloc[-1]
        
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
        
        return {
            'Ticker': ticker,
            'Sector': sector,
            'Pattern': bearish_pattern['pattern'],
            'Direction': 'SHORT',
            'Score': bearish_pattern['score'],
            'Entry_Price': round(entry_price, 2),
            'Stop_Loss': round(stop_loss, 2),
            'Target1': round(target1, 2),
            'Target2': round(target2, 2),
            'Risk': round(risk, 2),
            'Risk_Reward_Ratio': round(risk_reward_ratio, 2),
            'Volume_Ratio': round(last_bar['Volume_Ratio'], 2),
            'ATR': round(last_bar['ATR'], 2),
            'Momentum_5W': round(last_bar['Momentum_5'], 2),
            'Momentum_10W': round(last_bar['Momentum_10'], 2),
            'Description': bearish_pattern['description']
        }
    
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
    """Generate an HTML report with the filtered short candidates"""
    today = datetime.datetime.now()
    formatted_date = today.strftime("%d-%m-%Y")
    formatted_time = today.strftime("%H:%M")

    # HTML template with bearish styling
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Short Reversal Weekly Filter - {formatted_date}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 20px;
                background-color: #1a1a1a;
                color: #e0e0e0;
            }}
            .header {{
                background: linear-gradient(135deg, #d32f2f 0%, #b71c1c 100%);
                color: white;
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 30px;
                box-shadow: 0 4px 15px rgba(211, 47, 47, 0.3);
            }}
            h1 {{
                margin: 0 0 10px 0;
                font-size: 2.5em;
                font-weight: 600;
            }}
            .subtitle {{
                font-size: 1.2em;
                opacity: 0.9;
            }}
            .summary {{
                background: #2a2a2a;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
                border-left: 4px solid #d32f2f;
            }}
            .summary-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-top: 15px;
            }}
            .summary-item {{
                text-align: center;
                padding: 15px;
                background: #333;
                border-radius: 8px;
            }}
            .summary-value {{
                font-size: 2em;
                font-weight: bold;
                color: #ff5252;
            }}
            .summary-label {{
                color: #999;
                font-size: 0.9em;
                margin-top: 5px;
            }}
            .header-info {{
                margin-top: 15px;
                font-size: 0.9em;
                opacity: 0.8;
                display: flex;
                justify-content: space-between;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                background: #2a2a2a;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
            }}
            th {{
                background: #d32f2f;
                color: white;
                padding: 15px;
                text-align: left;
                font-weight: 600;
                font-size: 0.95em;
                letter-spacing: 0.5px;
            }}
            td {{
                padding: 12px 15px;
                border-bottom: 1px solid #444;
            }}
            tr:hover {{
                background-color: #333;
            }}
            .ticker-direction {{
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.85em;
                font-weight: 600;
                background: #d32f2f;
                color: white;
            }}
            .score-badge {{
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: 600;
                background: #ffcdd2;
                color: #b71c1c;
            }}
            .sector-badge {{
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.85em;
                background: #424242;
                color: #e0e0e0;
            }}
            .ticker-card {{
                background: #2a2a2a;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
                border-left: 4px solid #d32f2f;
            }}
            .ticker-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            }}
            .ticker-name {{
                font-size: 1.5em;
                font-weight: bold;
                color: #ff5252;
            }}
            .ticker-details {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }}
            .detail-item {{
                padding: 10px;
                background: #333;
                border-radius: 6px;
            }}
            .detail-label {{
                font-size: 0.85em;
                color: #999;
                margin-bottom: 3px;
            }}
            .detail-value {{
                font-size: 1.1em;
                font-weight: 600;
                color: #e0e0e0;
            }}
            .pattern-info {{
                margin-top: 15px;
                padding: 15px;
                background: #3e2723;
                border-radius: 6px;
                color: #ffccbc;
            }}
            .footer {{
                text-align: center;
                padding: 20px;
                color: #999;
                margin-top: 40px;
                border-top: 1px solid #444;
            }}
            .risk-warning {{
                background: #b71c1c;
                color: white;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                text-align: center;
                font-weight: 600;
            }}
            @media (max-width: 768px) {{
                .summary-grid {{
                    grid-template-columns: 1fr;
                }}
                .ticker-details {{
                    grid-template-columns: 1fr 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📉 Short Reversal Weekly Filter - Al Brooks L2 Patterns</h1>
            <div class="subtitle">Weekly timeframe analysis for high probability short setups</div>
            <div class="header-info">
                <div>Date: {formatted_date} | Time: {formatted_time}</div>
                <div>Filtered from: Ticker.xlsx | SHORT ONLY | L2 & Bearish Patterns</div>
            </div>
        </div>

        <div class="risk-warning">
            ⚠️ Risk Warning: Short selling involves significant risk. Ensure proper risk management and position sizing.
        </div>
        
        <div class="summary">
            <h2>Summary</h2>
            <div class="summary-grid">
                <div class="summary-item">
                    <div class="summary-value">{len(filtered_df)}</div>
                    <div class="summary-label">Total Patterns Found</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{filtered_df['Score'].mean():.0f}</div>
                    <div class="summary-label">Average Score</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{filtered_df['Risk_Reward_Ratio'].mean():.1f}</div>
                    <div class="summary-label">Avg Risk:Reward</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{filtered_df['Volume_Ratio'].mean():.1f}x</div>
                    <div class="summary-label">Avg Volume Ratio</div>
                </div>
            </div>
            <div style="margin-top: 20px; color: #ccc;">
                <strong>Pattern Types:</strong> L2 Failed Second Leg | Double Tops | Failed Breakouts | 
                Bear Flags | Resistance Rejections | Score ≥ 6/11 for high probability
            </div>
        </div>

        <h2>High Probability Short Patterns ({len(filtered_df)} matches)</h2>
    """

    # Add table
    if not filtered_df.empty:
        html_content += """
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Sector</th>
                    <th>Pattern</th>
                    <th>Score</th>
                    <th>Entry</th>
                    <th>Stop Loss</th>
                    <th>Target 1</th>
                    <th>Risk:Reward</th>
                    <th>Volume</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for idx, row in filtered_df.iterrows():
            html_content += f"""
                <tr>
                    <td style="font-weight: bold; color: #ff5252;">{row['Ticker']}</td>
                    <td><span class="sector-badge">{row['Sector']}</span></td>
                    <td>{row['Pattern']}</td>
                    <td><span class="score-badge">{row['Score']}/11</span></td>
                    <td>₹{row['Entry_Price']:.2f}</td>
                    <td>₹{row['Stop_Loss']:.2f}</td>
                    <td>₹{row['Target1']:.2f}</td>
                    <td>{row['Risk_Reward_Ratio']:.1f}</td>
                    <td>{row['Volume_Ratio']:.1f}x</td>
                </tr>
            """
        
        html_content += """
            </tbody>
        </table>
        """
    
    # Add detailed analysis cards
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
                    <div class="detail-label">Pattern Type</div>
                    <div class="detail-value">{row['Pattern']}</div>
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
                    <div class="detail-label">ATR (14)</div>
                    <div class="detail-value">₹{row['ATR']:.2f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">5W Momentum</div>
                    <div class="detail-value">{row['Momentum_5W']:.1f}%</div>
                </div>
            </div>
            
            <div class="pattern-info">
                <strong>Pattern Details:</strong> {row['Description']}
            </div>
        </div>
        """
    
    # Add footer
    html_content += f"""
        <div class="footer">
            <p>Generated on {formatted_date} at {formatted_time} | Short Reversal Weekly Filter - Al Brooks L2 Patterns</p>
            <p><strong>Note:</strong> These are high probability short setups based on Al Brooks L2 (second leg) patterns and bearish confirmations.</p>
            <p><strong>Risk Warning:</strong> Short selling involves significant risk. Ensure proper risk management and position sizing.</p>
        </div>
    </body>
    </html>
    """
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return output_file

# -----------------------------
# Main Function
# -----------------------------
def main():
    """Main function to filter tickers for high probability SHORT patterns"""
    logger.info("Short Reversal Weekly filter with Al Brooks L2 Patterns")
    
    start_time = time.time()

    try:
        # Read tickers from file
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
        
        # Get timestamp for output files
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.datetime.now(ist)
        formatted_date = now.strftime('%Y%m%d')
        formatted_time = now.strftime('%H%M%S')
        
        # Output files
        excel_file = os.path.join(RESULTS_DIR, f"Short_Reversal_Weekly_{formatted_date}_{formatted_time}.xlsx")
        html_file = os.path.join(HTML_DIR, f"Short_Reversal_Weekly_{formatted_date}_{formatted_time.replace('_', '-')}.html")
        
        if results:
            # Create DataFrame and sort by score
            results_df = pd.DataFrame(results)
            results_df = results_df.sort_values('Score', ascending=False)
            
            # Write to Excel
            results_df.to_excel(excel_file, index=False)
            logger.info(f"Successfully wrote {len(results_df)} SHORT candidates to {excel_file}")
            
            # Also save a copy to Market_Regime/results for regime analysis
            try:
                market_regime_dir = os.path.join(os.path.dirname(RESULTS_DIR), 'Market_Regime', 'results')
                os.makedirs(market_regime_dir, exist_ok=True)
                
                market_regime_file = os.path.join(market_regime_dir, f"Short_Reversal_Weekly_{formatted_date}_{formatted_time}.xlsx")
                results_df.to_excel(market_regime_file, index=False)
                logger.info(f"Also saved to Market Regime directory: {market_regime_file}")
            except Exception as e:
                logger.warning(f"Could not save to Market Regime directory: {e}")
            
            # Generate HTML report
            html_output = generate_html_report(results_df, html_file, "Ticker.xlsx")
            logger.info(f"HTML report saved to: {html_output}")
            
            # Browser auto-launch disabled
            logger.info(f"HTML report saved at: {html_file}")
            # Uncomment below to auto-launch in browser:
            # try:
            #     webbrowser.open(f"file://{os.path.abspath(html_file)}")
            # except Exception as e:
            #     logger.warning(f"Could not open browser automatically: {e}")
            
            # Print summary to console
            print("\n===== Short Reversal Weekly Results =====")
            print(f"Found {len(results_df)} high probability SHORT patterns")
            
            # Print sector summary
            sector_counts = results_df['Sector'].value_counts()
            print("\nSector Distribution:")
            for sector, count in sector_counts.items():
                print(f"  {sector}: {count} stocks")
            
            # Print pattern type summary
            pattern_counts = results_df['Pattern'].value_counts()
            print("\nPattern Types:")
            for pattern, count in pattern_counts.items():
                print(f"  {pattern}: {count} stocks")
            
            print("\nTop 5 SHORT patterns by score:")
            for idx, row in results_df.head(5).iterrows():
                print(f"{row['Ticker']} ({row['Sector']}): {row['Pattern']}, Score {row['Score']}, Entry ₹{row['Entry_Price']:.2f}, SL ₹{row['Stop_Loss']:.2f}, R:R {row['Risk_Reward_Ratio']:.2f}")

            print(f"\nDetailed results saved to: {excel_file}")
            print(f"HTML report opened in browser: {html_file}")
            
        else:
            # Create empty results
            empty_df = pd.DataFrame(columns=['Ticker', 'Sector', 'Pattern', 'Direction', 'Score', 
                                           'Entry_Price', 'Stop_Loss', 'Target1', 'Target2', 
                                           'Risk', 'Risk_Reward_Ratio', 'Volume_Ratio', 'ATR', 
                                           'Momentum_5W', 'Momentum_10W', 'Description'])
            empty_df.to_excel(excel_file, index=False)
            
            # Create "no results" HTML
            no_results_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Short Reversal Weekly - No Patterns Found</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; 
                           background-color: #1a1a1a; color: #e0e0e0; }}
                    h1 {{ color: #ff5252; }}
                    .no-results {{ background: #2a2a2a; padding: 30px; border-radius: 10px; 
                                  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3); margin: 30px auto; 
                                  max-width: 600px; }}
                </style>
            </head>
            <body>
                <h1>📉 Short Reversal Weekly Filter - Al Brooks L2 Patterns</h1>
                <div class="no-results">
                    <h2>No High Probability SHORT Patterns Found</h2>
                    <p>No tickers matched the high probability SHORT criteria in today's scan.</p>
                    <p>The filter searched for BEARISH patterns with:</p>
                    <ul style="display: inline-block; text-align: left;">
                        <li>Failed second leg up (L2 failure)</li>
                        <li>Double tops and lower highs</li>
                        <li>Failed bull breakouts</li>
                        <li>Bear flags and wedge reversals</li>
                        <li>Strong bearish bars with volume</li>
                        <li>Resistance rejection patterns</li>
                        <li>Score of 6/11 or higher for high probability</li>
                    </ul>
                    <p><strong>Note:</strong> High probability SHORT setups require multiple bearish confirmations.</p>
                </div>
                <div style="margin-top: 50px; color: #999;">
                    <p>Generated on {formatted_date} at {formatted_time.replace('_', ':')} | Short Reversal Weekly Filter</p>
                </div>
            </body>
            </html>
            """
            
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(no_results_html)
            
            # Browser auto-launch disabled
            logger.info(f"HTML report saved at: {html_file}")
            # Uncomment below to auto-launch in browser:
            # try:
            #     webbrowser.open(f"file://{os.path.abspath(html_file)}")
            # except Exception as e:
            #     logger.warning(f"Could not open browser automatically: {e}")
                
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
        print(f"\nError occurred: {e}")
        return 1

# -----------------------------
# Entry Point
# -----------------------------
if __name__ == "__main__":
    print("\n")
    print("=====================================")
    print("Short Reversal Weekly Filter")
    print("=====================================")
    print("Finding high probability SHORT setups:")
    print("1. Al Brooks L2 (second leg) patterns")
    print("2. Failed bull breakouts & double tops")
    print("3. Bear flags and wedge reversals")
    print("4. Multiple strong bearish bars")
    print("5. Resistance rejection patterns")
    print("=====================================\n")
    
    exit_code = main()
    sys.exit(exit_code)