#!/usr/bin/env python
# Al_Brooks_vWAP_SMA20.py - Filter stocks based on multiple criteria:
# 1. Above Weekly vWAP
# 2. Above Daily SMA20
# 3. H2 breakout pattern (Al Brooks concept)
# 4. Volume uptick of 3X threshold

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

# Add parent directory to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "al_brooks_vwap_sma20.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Al Brooks vWAP SMA20 Analysis")
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
# Calculate Weekly vWAP 
# -----------------------------
def calculate_weekly_vwap(data):
    """Calculate Weekly Volume Weighted Average Price"""
    if data.empty:
        return None
        
    # Create a copy to avoid SettingWithCopyWarning
    df = data.copy()
    
    # Extract week and year
    df['Week'] = df['Date'].dt.isocalendar().week
    df['Year'] = df['Date'].dt.isocalendar().year
    
    # Calculate typical price and volume
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['TPV'] = df['TP'] * df['Volume']
    
    # Calculate VWAP by week
    weekly_data = df.groupby(['Year', 'Week']).agg({
        'TPV': 'sum',
        'Volume': 'sum',
        'Date': 'last'
    }).reset_index()
    
    weekly_data['Weekly_VWAP'] = weekly_data['TPV'] / weekly_data['Volume']
    
    # Get the latest weekly VWAP
    if not weekly_data.empty:
        return weekly_data.iloc[-1]['Weekly_VWAP']
    return None

# -----------------------------
# Calculate Daily Indicators
# -----------------------------
def calculate_indicators(daily_data):
    """Calculate daily indicators for filter strategy"""
    if daily_data.empty or len(daily_data) < 30:
        logger.warning(f"Insufficient data points for {daily_data['Ticker'].iloc[0] if not daily_data.empty else 'unknown ticker'}")
        return None
        
    # Create a copy to avoid SettingWithCopyWarning
    df = daily_data.copy()
    
    # Calculate SMA20
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    
    # Calculate ATR for volatility
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift(1)).abs()
    low_close = (df['Low'] - df['Close'].shift(1)).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    df['TR'] = ranges.max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()
    
    # Calculate Keltner Channels for identifying breakouts
    df['KC_Middle'] = df['SMA20']
    df['KC_Upper'] = df['KC_Middle'] + (2 * df['ATR'])
    df['KC_Lower'] = df['KC_Middle'] - (2 * df['ATR'])
    
    # For identifying H2 breakout pattern (bar closes above prior high)
    df['PrevHigh'] = df['High'].shift(1)
    df['PrevLow'] = df['Low'].shift(1)
    df['PrevClose'] = df['Close'].shift(1)
    df['PrevOpen'] = df['Open'].shift(1)
    
    # Calculate body percentage (for strong trend bars)
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Range'] = df['High'] - df['Low']
    df['BodyPercent'] = (df['Body'] / df['Range']) * 100
    
    # Calculate volume indicators
    df['AvgVolume20'] = df['Volume'].rolling(window=20).mean()
    df['AvgVolume3'] = df['Volume'].shift(1).rolling(window=3).mean()
    df['VolumeRatio20'] = df['Volume'] / df['AvgVolume20']
    df['VolumeRatio3'] = df['Volume'] / df['AvgVolume3']
    
    return df

# -----------------------------
# H2 Pattern Detection 
# -----------------------------
def detect_h2_pattern(data):
    """
    Detect H2 pattern from Al Brooks methodology:
    H2: Strong bull trend bar closing above prior high
    
    Returns a dictionary with pattern details if found, None otherwise
    """
    if data is None or data.empty or len(data) < 5:
        return None
    
    # Get the last candle
    last_candle = data.iloc[-1]
    
    # Check if it's a bullish candle
    is_bull = last_candle['Close'] > last_candle['Open']
    
    # Check if it closed above the previous high
    close_above_prev_high = last_candle['Close'] > last_candle['PrevHigh']
    
    # Check if it's a strong body (>60% of range)
    strong_body = last_candle['BodyPercent'] > 60
    
    # Check if price is above SMA20
    above_sma20 = last_candle['Close'] > last_candle['SMA20']
    
    # Combined H2 pattern conditions
    h2_pattern = is_bull and close_above_prev_high and strong_body and above_sma20
    
    if h2_pattern:
        return {
            'pattern': 'H2',
            'description': 'Strong bull trend bar closing above prior high',
            'is_bull': is_bull,
            'close_above_prev_high': close_above_prev_high,
            'strong_body': strong_body,
            'above_sma20': above_sma20,
            'body_percent': last_candle['BodyPercent'],
            'stoploss': last_candle['Low'] - (0.5 * last_candle['ATR'])
        }
    
    return None

# -----------------------------
# Process Single Ticker
# -----------------------------
def process_ticker(ticker):
    """Process a single ticker based on all filtering criteria"""
    logger.info(f"Processing {ticker}")
    
    try:
        now = datetime.datetime.now()
        
        # Date ranges for weekly and daily data
        from_date_weekly = (now - relativedelta(months=3)).strftime('%Y-%m-%d')
        from_date_daily = (now - relativedelta(months=3)).strftime('%Y-%m-%d')
        to_date = now.strftime('%Y-%m-%d')
        
        # Fetch weekly data for vWAP calculation
        weekly_data = fetch_data_kite(ticker, interval_mapping['1w'], from_date_weekly, to_date)
        if weekly_data.empty:
            logger.warning(f"No weekly data available for {ticker}, skipping")
            return None
            
        # Calculate weekly vWAP
        weekly_vwap = calculate_weekly_vwap(weekly_data)
        if weekly_vwap is None:
            logger.warning(f"Could not calculate Weekly vWAP for {ticker}, skipping")
            return None
            
        # Fetch daily data for SMA20 and H2 pattern detection
        daily_data = fetch_data_kite(ticker, interval_mapping['1d'], from_date_daily, to_date)
        if daily_data.empty:
            logger.warning(f"No daily data available for {ticker}, skipping")
            return None
            
        # Calculate indicators on daily data
        daily_with_indicators = calculate_indicators(daily_data)
        if daily_with_indicators is None:
            logger.warning(f"Could not calculate indicators for {ticker}, skipping")
            return None
            
        # Get the most recent values
        last_price = daily_with_indicators['Close'].iloc[-1]
        last_sma20 = daily_with_indicators['SMA20'].iloc[-1]
        volume_ratio_20 = daily_with_indicators['VolumeRatio20'].iloc[-1]
        volume_ratio_3 = daily_with_indicators['VolumeRatio3'].iloc[-1]
        
        # Check filter criteria
        above_weekly_vwap = last_price > weekly_vwap
        above_daily_sma20 = last_price > last_sma20
        volume_spike = volume_ratio_3 >= 3.0  # 3X volume threshold
        
        # Detect H2 pattern
        h2_pattern = detect_h2_pattern(daily_with_indicators)
        has_h2_pattern = h2_pattern is not None
        
        # Log the findings
        logger.info(f"{ticker} - Above Weekly vWAP: {above_weekly_vwap}")
        logger.info(f"{ticker} - Above Daily SMA20: {above_daily_sma20}")
        logger.info(f"{ticker} - H2 Pattern Detected: {has_h2_pattern}")
        logger.info(f"{ticker} - Volume Spike (3X): {volume_spike} (Ratio: {volume_ratio_3:.2f})")
        
        # Check if all filters are satisfied
        if above_weekly_vwap and above_daily_sma20 and has_h2_pattern and volume_spike:
            logger.info(f"{ticker} meets all filtering criteria!")
            
            # Calculate ATR-based stop loss and targets
            last_atr = daily_with_indicators['ATR'].iloc[-1]
            
            if h2_pattern and 'stoploss' in h2_pattern:
                stop_loss = h2_pattern['stoploss']
            else:
                stop_loss = last_price - (1.5 * last_atr)
                
            # Calculate reward targets (1:2 and 1:3 risk-reward ratios)
            risk = last_price - stop_loss
            target1 = last_price + (2 * risk)  # 1:2 risk-reward
            target2 = last_price + (3 * risk)  # 1:3 risk-reward
            
            # Prepare result with all data
            result = {
                'Ticker': ticker,
                'Price': last_price,
                'SMA20': last_sma20,
                'Weekly_VWAP': weekly_vwap,
                'ATR': last_atr,
                'SL': stop_loss,
                'Target1': target1,
                'Target2': target2,
                'Volume_Ratio': volume_ratio_3,
                'Pattern': 'H2',
                'Pattern_Details': h2_pattern['description'] if h2_pattern else '',
                'Risk_Reward_Ratio': (target1 - last_price) / (last_price - stop_loss) if stop_loss < last_price else 0
            }
            
            return result
        else:
            logger.info(f"{ticker} does not meet all filtering criteria")
            return None
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
        <title>Al Brooks vWAP + SMA20 + H2 Filter - {formatted_date}</title>
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
            .ticker-price {{
                font-weight: bold;
                font-size: 1.1em;
            }}
            .ticker-details {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
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
        </style>
    </head>
    <body>
        <h1>🔍 Al Brooks vWAP + SMA20 + H2 Pattern Filter</h1>
        <div class="header-info">
            <div>Date: {formatted_date} | Time: {formatted_time}</div>
            <div>Filtered from: Ticker.xlsx</div>
        </div>
        
        <h2>Filtered Tickers ({len(filtered_df)} matches)</h2>
    """

    # Add table view
    html_content += """
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Price</th>
                    <th>Weekly vWAP</th>
                    <th>SMA20</th>
                    <th>Stop Loss</th>
                    <th>Target 1</th>
                    <th>Volume Ratio</th>
                    <th>Risk:Reward</th>
                </tr>
            </thead>
            <tbody>
    """

    # Add rows for each ticker
    for idx, row in filtered_df.iterrows():
        html_content += f"""
            <tr>
                <td>{row['Ticker']}</td>
                <td>{row['Price']:.2f}</td>
                <td>{row['Weekly_VWAP']:.2f}</td>
                <td>{row['SMA20']:.2f}</td>
                <td>{row['SL']:.2f}</td>
                <td>{row['Target1']:.2f}</td>
                <td>{row['Volume_Ratio']:.2f}x</td>
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
                <div class="ticker-name">{row['Ticker']}</div>
                <div class="ticker-price">₹{row['Price']:.2f}</div>
            </div>
            
            <div class="ticker-details">
                <div class="detail-item">
                    <div class="detail-label">Weekly vWAP</div>
                    <div class="detail-value">₹{row['Weekly_VWAP']:.2f} (Price Above ✓)</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Daily SMA20</div>
                    <div class="detail-value">₹{row['SMA20']:.2f} (Price Above ✓)</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Volume Spike</div>
                    <div class="detail-value">{row['Volume_Ratio']:.2f}x Recent Average</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">ATR (14)</div>
                    <div class="detail-value">₹{row['ATR']:.2f}</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">Stop Loss</div>
                    <div class="detail-value">₹{row['SL']:.2f}</div>
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
                    <div class="detail-label">Risk:Reward</div>
                    <div class="detail-value">{row['Risk_Reward_Ratio']:.2f}</div>
                </div>
            </div>
            
            <div class="pattern-info">
                <strong>H2 Pattern Detected:</strong> {row['Pattern_Details']}
            </div>
        </div>
        """

    # Complete HTML
    html_content += f"""
        <div class="source-info">
            <p>Generated on {formatted_date} at {formatted_time} | Al Brooks vWAP + SMA20 + H2 Filter</p>
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
    """Main function to filter tickers based on Al Brooks criteria"""
    logger.info("Starting Al Brooks vWAP + SMA20 + H2 filter")
    
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
        formatted_date = today.strftime("%d_%m_%Y")
        formatted_time = today.strftime("%H_%M")
        excel_file = os.path.join(RESULTS_DIR, f"Brooks_vWAP_SMA20_H2_{formatted_date}_{formatted_time}.xlsx")
        html_file = os.path.join(HTML_DIR, f"Detailed_Analysis_{formatted_date}_{formatted_time.replace('_', '-')}.html")
        
        if results:
            # Convert to DataFrame
            results_df = pd.DataFrame(results)
            
            # Sort by Risk-Reward ratio (descending)
            results_df = results_df.sort_values(by='Risk_Reward_Ratio', ascending=False)
            
            # Round numeric columns for better readability
            numeric_cols = ['Price', 'SMA20', 'Weekly_VWAP', 'ATR', 'SL', 'Target1', 'Target2', 'Volume_Ratio', 'Risk_Reward_Ratio']
            for col in numeric_cols:
                if col in results_df.columns:
                    results_df[col] = results_df[col].astype(float).round(2)
            
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
            print("\n===== Al Brooks vWAP + SMA20 + H2 Filter Results =====")
            print(f"Found {len(results_df)} tickers that meet all criteria")
            print("\nTop 5 tickers by Risk:Reward ratio:")
            for idx, row in results_df.head(5).iterrows():
                print(f"{row['Ticker']}: Price ${row['Price']:.2f}, SL ${row['SL']:.2f}, Target ${row['Target1']:.2f}, R:R {row['Risk_Reward_Ratio']:.2f}")
            
            print(f"\nDetailed results saved to: {excel_file}")
            print(f"HTML report opened in browser: {html_file}")
        else:
            # Create empty Excel with columns
            empty_cols = ['Ticker', 'Price', 'SMA20', 'Weekly_VWAP', 'ATR', 'SL', 'Target1', 'Target2', 
                          'Volume_Ratio', 'Pattern', 'Pattern_Details', 'Risk_Reward_Ratio']
            pd.DataFrame(columns=empty_cols).to_excel(excel_file, index=False)
            
            # Generate empty HTML report
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Al Brooks vWAP + SMA20 + H2 Filter - {formatted_date}</title>
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
                <h1>🔍 Al Brooks vWAP + SMA20 + H2 Filter</h1>
                <div class="no-results">
                    <h2>No Matches Found</h2>
                    <p>No tickers matched all filter criteria in today's scan.</p>
                    <p>The filter searched for tickers that meet all of the following criteria:</p>
                    <ul style="display: inline-block; text-align: left;">
                        <li>Price above Weekly vWAP</li>
                        <li>Price above Daily SMA20</li>
                        <li>H2 breakout pattern (strong bull trend bar closing above prior high)</li>
                        <li>Volume spike of at least 3x recent average</li>
                    </ul>
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
                
            logger.info(f"No tickers matched all criteria. Empty output files created at {excel_file} and {html_file}")
            print("\nNo tickers matched all filter criteria.")
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
    print("🔍 Al Brooks vWAP + SMA20 + H2 Filter")
    print("===================================")
    print("Finding stocks that meet all criteria:")
    print("1. Price above Weekly vWAP")
    print("2. Price above Daily SMA20")
    print("3. H2 breakout pattern")
    print("4. Volume spike of 3X threshold")
    print("===================================")
    print(f"Using credentials for user: {user_name}")
    print("===================================\n")

    sys.exit(main())