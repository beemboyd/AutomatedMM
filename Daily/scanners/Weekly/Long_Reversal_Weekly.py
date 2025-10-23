#!/usr/bin/env python
# Long_Reversal_Weekly.py - Filter stocks based on higher probability reversal criteria with Sector information:
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
import webbrowser

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                       "logs", "long_reversal_weekly.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Long Reversal Weekly Analysis with Sector Information")
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
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), "results")
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
# Calculate Indicators for Higher Probability Analysis
# -----------------------------
def calculate_indicators(weekly_data):
    """Calculate indicators for higher probability reversal detection"""
    if weekly_data.empty or len(weekly_data) < 50:
        logger.warning(f"Insufficient data points for {weekly_data['Ticker'].iloc[0] if not weekly_data.empty else 'unknown ticker'}")
        return None
        
    # Create a copy to avoid SettingWithCopyWarning
    df = weekly_data.copy()
    
    # ATR (Average True Range) - 14 periods
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = true_range.rolling(window=14).mean()
    
    # SMA
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    
    # Volume SMA
    df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
    df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
    
    # Price patterns
    df['High_20'] = df['High'].rolling(window=20).max()
    df['Low_20'] = df['Low'].rolling(window=20).min()
    
    # Momentum indicators
    df['Momentum_5'] = (df['Close'] / df['Close'].shift(5) - 1) * 100
    df['Momentum_10'] = (df['Close'] / df['Close'].shift(10) - 1) * 100
    
    # Pattern characteristics
    df['Body'] = df['Close'] - df['Open']
    df['Upper_Shadow'] = df['High'] - df[['Close', 'Open']].max(axis=1)
    df['Lower_Shadow'] = df[['Close', 'Open']].min(axis=1) - df['Low']
    df['Range'] = df['High'] - df['Low']
    
    # Trend identification
    df['Downtrend'] = (df['Close'] < df['SMA20']) & (df['Close'].shift(1) < df['SMA20'].shift(1))
    
    return df

# -----------------------------
# Higher Probability Reversal Detection
# -----------------------------
def detect_higher_probability_reversal(df):
    """
    Detect higher probability reversal patterns (60%+ success rate)
    Focus on confirmed reversals with strong breakouts
    """
    if df is None or len(df) < 20:
        return None
    
    # Get the last few bars for pattern analysis
    current_bar = df.iloc[-1]
    prev_bar_1 = df.iloc[-2]
    prev_bar_2 = df.iloc[-3]
    prev_bar_3 = df.iloc[-4] if len(df) > 3 else prev_bar_2
    
    # Initialize scoring system
    reversal_score = 0
    max_score = 100
    reasons = []
    
    # 1. Price breaking above 20-week high (strongest signal) - 30 points
    if current_bar['Close'] > prev_bar_1['High_20']:
        reversal_score += 30
        reasons.append("Breakout above 20-week high")
    
    # 2. Strong bullish candle with volume - 20 points
    body_size = abs(current_bar['Body'])
    avg_range = df['Range'].tail(20).mean()
    
    if current_bar['Body'] > 0 and body_size > avg_range * 0.7:
        if current_bar['Volume_Ratio'] > 1.5:
            reversal_score += 20
            reasons.append("Strong bullish candle with high volume")
        else:
            reversal_score += 10
            reasons.append("Strong bullish candle")
    
    # 3. Multiple confirmation bars - 15 points
    bullish_bars = 0
    for i in range(1, min(4, len(df))):
        if df.iloc[-i]['Body'] > 0:
            bullish_bars += 1
    
    if bullish_bars >= 3:
        reversal_score += 15
        reasons.append("Multiple bullish confirmation bars")
    elif bullish_bars >= 2:
        reversal_score += 8
        reasons.append("Bullish confirmation")
    
    # 4. Volume expansion pattern - 15 points
    recent_volume = df['Volume'].tail(3).mean()
    prior_volume = df['Volume'].tail(10).head(7).mean()
    
    if recent_volume > prior_volume * 1.5:
        reversal_score += 15
        reasons.append("Volume expansion on reversal")
    
    # 5. Breaking above SMA20 with conviction - 10 points
    if (prev_bar_1['Close'] < prev_bar_1['SMA20'] and 
        current_bar['Close'] > current_bar['SMA20'] and
        current_bar['Close'] > current_bar['Open']):
        reversal_score += 10
        reasons.append("Broke above SMA20")
    
    # 6. Momentum shift - 10 points
    if (current_bar['Momentum_5'] > 0 and 
        prev_bar_1['Momentum_5'] < 0):
        reversal_score += 10
        reasons.append("Momentum turned positive")
    
    # Calculate probability based on score
    probability = (reversal_score / max_score) * 100
    
    # Only return patterns with 60%+ probability
    if probability >= 60:
        return {
            'detected': True,
            'score': reversal_score,
            'max_score': max_score,
            'probability': probability,
            'reasons': reasons,
            'pattern': 'Higher Probability Long Reversal',
            'description': ' | '.join(reasons)
        }
    
    return None

# -----------------------------
# Process Each Ticker
# -----------------------------
def process_ticker(ticker):
    """Process a single ticker for reversal pattern"""
    try:
        # Get current date
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.datetime.now(ist)
        
        # For weekly data, fetch 2 years of data
        from_date_weekly = (now - relativedelta(years=2)).strftime('%Y-%m-%d')
        to_date = now.strftime('%Y-%m-%d')
        
        # Fetch weekly data for pattern detection
        weekly_data = fetch_data_kite(ticker, interval_mapping['1w'], from_date_weekly, to_date)
        if weekly_data.empty:
            logger.warning(f"No weekly data available for {ticker}, skipping")
            return None
            
        # Calculate indicators
        weekly_with_indicators = calculate_indicators(weekly_data)
        if weekly_with_indicators is None:
            logger.warning(f"Could not calculate indicators for {ticker}, skipping")
            return None
            
        # Detect higher probability reversal pattern
        reversal_pattern = detect_higher_probability_reversal(weekly_with_indicators)
        
        if reversal_pattern and reversal_pattern['detected']:
            # Get the last bar for entry/exit calculations
            last_bar = weekly_with_indicators.iloc[-1]
            
            # Entry at close of the signal bar
            entry_price = last_bar['Close']
            
            # Stop loss: 1.5 ATR below the low of the signal bar
            stop_loss = last_bar['Low'] - (1.5 * last_bar['ATR'])
            
            # Targets based on risk-reward
            risk = entry_price - stop_loss
            target1 = entry_price + (2 * risk)  # 1:2 risk-reward
            target2 = entry_price + (3 * risk)  # 1:3 risk-reward
            
            # Calculate risk-reward ratio
            risk_reward_ratio = abs(target1 - entry_price) / risk
        else:
            risk_reward_ratio = 0
        
        # Get sector information
        sector = get_sector_for_ticker(ticker)
        
        # Log the findings
        logger.info(f"{ticker} - Higher Probability LONG Reversal Detected!")
        logger.info(f"{ticker} - Pattern Score: {reversal_pattern['score']}/{reversal_pattern['max_score']}")
        logger.info(f"{ticker} - Entry: {entry_price:.2f}, Stop: {stop_loss:.2f}, Target1: {target1:.2f}")
        logger.info(f"{ticker} - Volume Ratio: {last_bar['Volume_Ratio']:.2f}")
        logger.info(f"{ticker} - Sector: {sector}")
        
        return {
            'Ticker': ticker,
            'Sector': sector,
            'Direction': 'LONG',
            'Score': reversal_pattern['score'],
            'Probability': reversal_pattern['probability'],
            'Entry_Price': round(entry_price, 2),
            'Stop_Loss': round(stop_loss, 2),
            'Target1': round(target1, 2),
            'Target2': round(target2, 2),
            'Risk': round(risk, 2),
            'Risk_Reward_Ratio': round(risk_reward_ratio, 2),
            'Volume_Ratio': round(last_bar['Volume_Ratio'], 2),
            'ATR': round(last_bar['ATR'], 2),
            'Momentum_5W': round(last_bar['Momentum_5'], 2),
            'Description': reversal_pattern['description']
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
    """Generate HTML report with filtered results"""
    
    # Get current date and time
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)
    formatted_date = now.strftime('%Y-%m-%d')
    formatted_time = now.strftime('%H:%M IST')
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Long Reversal Weekly Filter - {formatted_date}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 20px;
                background-color: #f8f9fa;
                color: #333;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 30px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
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
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
                border-left: 4px solid #667eea;
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
                background: #f8f9fa;
                border-radius: 8px;
            }}
            .summary-value {{
                font-size: 2em;
                font-weight: bold;
                color: #667eea;
            }}
            .summary-label {{
                color: #6c757d;
                font-size: 0.9em;
                margin-top: 5px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
            }}
            th {{
                background: #667eea;
                color: white;
                padding: 15px;
                text-align: left;
                font-weight: 600;
                font-size: 0.95em;
                letter-spacing: 0.5px;
            }}
            td {{
                padding: 12px 15px;
                border-bottom: 1px solid #e9ecef;
            }}
            tr:hover {{
                background-color: #f8f9fa;
            }}
            .ticker-direction {{
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.85em;
                font-weight: 600;
                background: #28a745;
                color: white;
            }}
            .score-badge {{
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: 600;
                background: #e3f2fd;
                color: #1976d2;
            }}
            .sector-badge {{
                display: inline-block;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.85em;
                background: #f3e5f5;
                color: #7b1fa2;
            }}
            .ticker-card {{
                background: white;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
                border-left: 4px solid #28a745;
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
                color: #333;
            }}
            .ticker-details {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin-top: 15px;
            }}
            .detail-item {{
                padding: 10px;
                background: #f8f9fa;
                border-radius: 6px;
            }}
            .detail-label {{
                font-size: 0.85em;
                color: #6c757d;
                margin-bottom: 3px;
            }}
            .detail-value {{
                font-size: 1.1em;
                font-weight: 600;
                color: #333;
            }}
            .pattern-info {{
                margin-top: 15px;
                padding: 15px;
                background: #e7f5ff;
                border-radius: 6px;
                color: #0c5460;
            }}
            .footer {{
                text-align: center;
                padding: 20px;
                color: #6c757d;
                margin-top: 40px;
                border-top: 1px solid #e9ecef;
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
            <h1>Long Reversal Weekly Filter with Sector Information</h1>
            <div class="subtitle">Generated on {formatted_date} at {formatted_time}</div>
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
                    <div class="summary-value">{filtered_df['Probability'].mean():.0f}%</div>
                    <div class="summary-label">Average Probability</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value">{filtered_df['Volume_Ratio'].mean():.1f}x</div>
                    <div class="summary-label">Avg Volume Expansion</div>
                </div>
            </div>
            <div style="margin-top: 20px; color: #666;">
                <strong>Filter Criteria:</strong> Higher probability reversal patterns (60%+ success rate) | 
                Strong breakouts with volume confirmation | Multiple bullish bars | 
                Risk-Reward ratio 1:2 minimum
            </div>
        </div>
    """
    
    # Add table with results
    html_content += """
        <h2>Detailed Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Sector</th>
                    <th>Direction</th>
                    <th>Score</th>
                    <th>Entry Price</th>
                    <th>Stop Loss</th>
                    <th>Target 1 (1:2)</th>
                    <th>Risk:Reward</th>
                    <th>Volume Ratio</th>
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
                <td><span class="ticker-direction">LONG</span></td>
                <td>{row['Score']}</td>
                <td>₹{row['Entry_Price']:.2f}</td>
                <td>₹{row['Stop_Loss']:.2f}</td>
                <td>₹{row['Target1']:.2f}</td>
                <td>{row['Risk_Reward_Ratio']:.2f}</td>
                <td>{row['Volume_Ratio']:.2f}x</td>
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
                    <span class="ticker-direction">LONG</span>
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
                    <div class="detail-label">Volume Expansion</div>
                    <div class="detail-value">{row['Volume_Ratio']:.2f}x Average</div>
                </div>
                
                <div class="detail-item">
                    <div class="detail-label">5-Week Momentum</div>
                    <div class="detail-value">{row['Momentum_5W']:.2f}%</div>
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

    # Add footer
    html_content += f"""
        <div class="footer">
            <p>Generated on {formatted_date} at {formatted_time} | Long Reversal Weekly Filter with Sector Information</p>
            <p><small>Filtered from: {scanner_file} | LONG ONLY | Higher Probability: 60%+</small></p>
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
    try:
        logger.info("Long Reversal Weekly filter with Sector Information")
        logger.info("="*50)
        
        # Read tickers from file
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
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.datetime.now(ist)
        formatted_date = now.strftime('%Y%m%d')
        formatted_time = now.strftime('%H%M%S')
        
        excel_file = os.path.join(RESULTS_DIR, f"Long_Reversal_Weekly_{formatted_date}_{formatted_time}.xlsx")
        html_file = os.path.join(HTML_DIR, f"Long_Reversal_Weekly_{formatted_date}_{formatted_time.replace('_', '-')}.html")
        
        if results:
            # Create DataFrame and sort by score
            results_df = pd.DataFrame(results)
            results_df = results_df.sort_values('Score', ascending=False)
            
            # Save to Excel
            results_df.to_excel(excel_file, index=False, sheet_name='Long_Reversal_Weekly')
            logger.info(f"Results saved to: {excel_file}")
            
            # Generate HTML report
            html_output = generate_html_report(results_df, html_file, "Ticker.xlsx")
            logger.info(f"HTML report saved to: {html_output}")
            
            # Print summary
            print("\n" + "="*60)
            print("Long Reversal Weekly Analysis Complete!")
            print("="*60)
            print(f"Total patterns found: {len(results_df)}")
            print(f"Average pattern score: {results_df['Score'].mean():.1f}")
            print(f"Average probability: {results_df['Probability'].mean():.1f}%")
            print(f"Average volume ratio: {results_df['Volume_Ratio'].mean():.1f}x")
            
            print("\nTop 5 LONG patterns by score:")
            for idx, row in results_df.head(5).iterrows():
                print(f"{row['Ticker']} ({row['Sector']}): Score {row['Score']}, Entry ₹{row['Entry_Price']:.2f}, SL ₹{row['Stop_Loss']:.2f}, R:R {row['Risk_Reward_Ratio']:.2f}")
            
            print(f"\nDetailed results saved to: {excel_file}")
            print(f"HTML report saved to: {html_file}")
            
            # Also create a simple HTML version
            simple_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Long Reversal Weekly Filter - {formatted_date}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #4CAF50; color: white; }}
                    tr:nth-child(even) {{ background-color: #f2f2f2; }}
                </style>
            </head>
            <body>
                <h1>📈 Long Reversal Weekly Filter with Sector Information</h1>
                <p>Generated on: {now.strftime('%Y-%m-%d %H:%M:%S')} IST</p>
                <p>Total patterns found: {len(results_df)}</p>
                
                <table>
                    <tr>
                        <th>Ticker</th>
                        <th>Sector</th>
                        <th>Score</th>
                        <th>Entry</th>
                        <th>Stop Loss</th>
                        <th>Target 1</th>
                        <th>Volume Ratio</th>
                    </tr>
            """
            
            for idx, row in results_df.iterrows():
                simple_html += f"""
                    <tr>
                        <td>{row['Ticker']}</td>
                        <td>{row['Sector']}</td>
                        <td>{row['Score']}</td>
                        <td>₹{row['Entry_Price']:.2f}</td>
                        <td>₹{row['Stop_Loss']:.2f}</td>
                        <td>₹{row['Target1']:.2f}</td>
                        <td>{row['Volume_Ratio']:.2f}x</td>
                    </tr>
                """
            
            simple_html += """
                </table>
                <p style="margin-top: 20px; color: #666;">
                    <small>Generated on {formatted_date} at {formatted_time.replace('_', ':')} | Long Reversal Weekly Filter</small>
                </p>
            </body>
            </html>
            """
            
            # HTML report generated - browser auto-launch disabled
            logger.info(f"HTML report generated at: {html_file}")
            # Uncomment below to auto-launch in browser:
            # webbrowser.open(f"file://{os.path.abspath(html_file)}")
            
        else:
            print("\nNo reversal patterns found matching the criteria (60%+ probability)")
            logger.info("No patterns found")
            
            # Create empty Excel file
            empty_df = pd.DataFrame(columns=['Ticker', 'Sector', 'Direction', 'Score', 'Probability', 
                                           'Entry_Price', 'Stop_Loss', 'Target1', 'Target2', 
                                           'Risk', 'Risk_Reward_Ratio', 'Volume_Ratio', 
                                           'ATR', 'Momentum_5W', 'Description'])
            empty_df.to_excel(excel_file, index=False, sheet_name='Long_Reversal_Weekly')
            logger.info(f"Empty results file created: {excel_file}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        print(f"\nError occurred: {e}")
        return 1

# -----------------------------
# Entry Point
# -----------------------------
if __name__ == "__main__":
    print("Long Reversal Weekly Filter with Sector")
    print("=" * 50)
    print("Scanning for higher probability reversal patterns (60%+)")
    print("Looking for confirmed breakouts with volume expansion")
    print("=" * 50)
    
    exit_code = main()
    sys.exit(exit_code)