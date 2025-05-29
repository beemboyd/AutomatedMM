#!/usr/bin/env python
# Al_Brooks_Higher_Probability_Reversal_Weekly.py - Filter stocks based on higher probability reversal criteria using WEEKLY timeframe:
# 1. Wait for strong breakout in new direction (confirmed reversal)
# 2. Multiple confirmation bars in new trend
# 3. Break of significant support/resistance with conviction
# 4. Volume expansion on breakout
# 5. Accept wider stops for higher probability (60%+)

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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "al_brooks_higher_probability_weekly.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Al Brooks Higher Probability Weekly Reversal Analysis")
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

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
TICKER_FILE = os.path.join(BASE_DIR, "data", "Ticker.xlsx")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
HTML_DIR = os.path.join(BASE_DIR, "Detailed_Analysis")

# Create directories if they don't exist
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)

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
        self.cache = {}
        self.instruments_df = None
        self.instrument_tokens = {}
        
    def get(self, key):
        return self.cache.get(key)
        
    def set(self, key, value):
        self.cache[key] = value
        
    def clear(self):
        self.cache.clear()

# Global cache instance
cache = DataCache()

def initialize_kite():
    """Initialize KiteConnect with credentials from config"""
    try:
        api_key = config.get(credential_section, 'api_key')
        access_token = config.get(credential_section, 'access_token')

        if not api_key or not access_token:
            logger.error(f"Missing API credentials for user {user_name}")
            raise ValueError(f"API key or access token missing for user {user_name}")

        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        
        # Test the connection
        kite.profile()
        logger.info("KiteConnect initialized successfully")
        return kite
    except Exception as e:
        logger.error(f"Failed to initialize KiteConnect: {e}")
        return None

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
    """Get instrument token for a ticker with caching and enhanced matching"""
    if ticker in cache.instrument_tokens:
        return cache.instrument_tokens[ticker]

    df = get_instruments_data()
    if df.empty:
        logger.warning("Instruments data is empty. Cannot lookup instrument token.")
        return None

    try:
        # Clean the ticker symbol - remove extra spaces
        clean_ticker = ticker.strip().replace('  ', ' ').replace(' ', '')

        # First try exact match
        instrument = df[df['tradingsymbol'] == clean_ticker]
        if not instrument.empty:
            token = instrument.iloc[0]['instrument_token']
            cache.instrument_tokens[ticker] = token
            return token

        # Try alternative matching for problematic symbols
        # Check for symbols with suffix variants (e.g., "-BE", "_B", etc.)
        potential_matches = df[df['tradingsymbol'].str.contains(clean_ticker.split('_')[0].split(' ')[0], case=False, na=False)]
        if not potential_matches.empty:
            # Prefer NSE exchange if multiple matches
            nse_matches = potential_matches[potential_matches['exchange'] == 'NSE']
            if not nse_matches.empty:
                token = nse_matches.iloc[0]['instrument_token']
                logger.info(f"Found alternative match for {ticker}: {nse_matches.iloc[0]['tradingsymbol']}")
                cache.instrument_tokens[ticker] = token
                return token
            else:
                token = potential_matches.iloc[0]['instrument_token']
                logger.info(f"Found alternative match for {ticker}: {potential_matches.iloc[0]['tradingsymbol']}")
                cache.instrument_tokens[ticker] = token
                return token

        logger.warning(f"Instrument token not found for {ticker}")
        cache.instrument_tokens[ticker] = None
        return None
    except Exception as e:
        logger.error(f"Error looking up instrument token for {ticker}: {e}")
        cache.instrument_tokens[ticker] = None
        return None

# -----------------------------
# Data Fetching Functions
# -----------------------------
def read_ticker_file():
    """Read tickers from Excel file"""
    try:
        if os.path.exists(TICKER_FILE):
            df = pd.read_excel(TICKER_FILE)
            if 'Ticker' in df.columns:
                tickers = df['Ticker'].dropna().unique().tolist()
                logger.info(f"Found {len(tickers)} unique tickers in {TICKER_FILE}")
                return tickers
            else:
                logger.error("'Ticker' column not found in the Excel file")
                return []
        else:
            logger.error(f"Ticker file not found: {TICKER_FILE}")
            return []
    except Exception as e:
        logger.error(f"Error reading ticker file: {e}")
        return []

def fetch_data_kite(ticker, interval, from_date, to_date):
    """Fetch historical data from Kite with caching"""
    cache_key = f"{ticker}_{interval}_{from_date}_{to_date}"
    cached_data = cache.get(cache_key)
    
    if cached_data is not None:
        return cached_data
    
    try:
        instrument_token = get_instrument_token(ticker)
        if instrument_token is None:
            logger.warning(f"Could not get instrument token for {ticker}")
            return pd.DataFrame()
        
        # Convert dates to datetime objects for Kite API
        from_date_dt = pd.to_datetime(from_date).date()
        to_date_dt = pd.to_datetime(to_date).date()
        
        if interval == 'day':
            data = kite.historical_data(instrument_token, from_date_dt, to_date_dt, 'day')
        elif interval == 'week':
            data = kite.historical_data(instrument_token, from_date_dt, to_date_dt, 'week')
        else:
            data = kite.historical_data(instrument_token, from_date_dt, to_date_dt, interval)
        
        if data:
            df = pd.DataFrame(data)
            df['Date'] = pd.to_datetime(df['date'])
            df = df.rename(columns={
                'open': 'Open',
                'high': 'High', 
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            })
            df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].copy()
            df = df.sort_values('Date').reset_index(drop=True)
            
            cache.set(cache_key, df)
            logger.debug(f"Fetched {len(df)} {interval} bars for {ticker}")
            return df
        else:
            logger.warning(f"No data returned for {ticker}")
            empty_df = pd.DataFrame()
            cache.set(cache_key, empty_df)
            return empty_df
            
    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {e}")
        
        # Try fallback to local files for weekly data
        try:
            fallback_file = os.path.join(FALLBACK_DATA_DIR, f"{ticker}_1W.csv")
            if os.path.exists(fallback_file):
                df = pd.read_csv(fallback_file)
                if interval == 'week':
                    # For weekly analysis, we can use the weekly file directly
                    df['Date'] = pd.to_datetime(df['Date'])
                    df = df.sort_values('Date').reset_index(drop=True)
                    
                    # Filter data to requested date range
                    df = df[(df['Date'] >= from_date) & (df['Date'] <= to_date)]
                    
                    cache.set(cache_key, df)
                    logger.info(f"Using fallback weekly data for {ticker} ({len(df)} bars)")
                    return df
        except Exception as fallback_e:
            logger.error(f"Error with fallback data for {ticker}: {fallback_e}")
        
        empty_df = pd.DataFrame()
        cache.set(cache_key, empty_df)
        return empty_df

# -----------------------------
# Technical Analysis Functions  
# -----------------------------
def calculate_atr(data, period=14):
    """Calculate Average True Range"""
    try:
        high_low = data['High'] - data['Low']
        high_close_prev = np.abs(data['High'] - data['Close'].shift(1))
        low_close_prev = np.abs(data['Low'] - data['Close'].shift(1))
        
        true_range = np.maximum(high_low, np.maximum(high_close_prev, low_close_prev))
        atr = true_range.rolling(window=period).mean()
        return atr
    except Exception as e:
        logger.error(f"Error calculating ATR: {e}")
        return pd.Series(index=data.index, dtype=float)

def calculate_sma(data, period):
    """Calculate Simple Moving Average"""
    try:
        return data['Close'].rolling(window=period).mean()
    except Exception as e:
        logger.error(f"Error calculating SMA: {e}")
        return pd.Series(index=data.index, dtype=float)

def calculate_ema(data, period):
    """Calculate Exponential Moving Average"""
    try:
        return data['Close'].ewm(span=period).mean()
    except Exception as e:
        logger.error(f"Error calculating EMA: {e}")
        return pd.Series(index=data.index, dtype=float)

def calculate_indicators(data):
    """Calculate all required technical indicators"""
    try:
        if data.empty or len(data) < 50:
            logger.warning("Insufficient data for indicator calculation")
            return None
        
        df = data.copy()
        
        # Basic moving averages
        df['SMA_20'] = calculate_sma(df, 20)
        df['SMA_50'] = calculate_sma(df, 50)
        df['EMA_20'] = calculate_ema(df, 20)
        
        # ATR for volatility analysis
        df['ATR'] = calculate_atr(df, 14)
        
        # Volume analysis
        df['Volume_SMA_20'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA_20']
        
        # Price position relative to moving averages
        df['Price_vs_SMA20'] = (df['Close'] - df['SMA_20']) / df['SMA_20'] * 100
        df['Price_vs_SMA50'] = (df['Close'] - df['SMA_50']) / df['SMA_50'] * 100
        
        # Trend analysis
        df['SMA20_Slope'] = df['SMA_20'].diff(5) / df['SMA_20'].shift(5) * 100
        df['SMA50_Slope'] = df['SMA_50'].diff(5) / df['SMA_50'].shift(5) * 100
        
        # Range analysis for Brooks methodology
        df['High_Low_Range'] = df['High'] - df['Low']
        df['Avg_Range_20'] = df['High_Low_Range'].rolling(window=20).mean()
        df['Range_Expansion'] = df['High_Low_Range'] / df['Avg_Range_20']
        
        # Body size analysis
        df['Body_Size'] = np.abs(df['Close'] - df['Open'])
        df['Avg_Body_20'] = df['Body_Size'].rolling(window=20).mean()
        df['Body_Ratio'] = df['Body_Size'] / df['Avg_Body_20']
        
        # Support/Resistance levels (swing highs/lows)
        df['Swing_High'] = df['High'].rolling(window=10, center=True).max() == df['High']
        df['Swing_Low'] = df['Low'].rolling(window=10, center=True).min() == df['Low']
        
        logger.debug("Technical indicators calculated successfully")
        return df
        
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        return None

def detect_higher_probability_reversal(data):
    """
    Detect higher probability LONG reversal patterns based on Al Brooks methodology
    
    Criteria for Higher Probability LONG Reversal:
    1. Strong bearish trend followed by reversal signs
    2. Multiple confirmation bars in new upward direction  
    3. Break of significant resistance with conviction
    4. Volume expansion on breakout
    5. Price above key moving averages after reversal
    """
    try:
        if data is None or len(data) < 50:
            return None
            
        df = data.copy()
        
        # Get the most recent bars for analysis
        last_bar = df.iloc[-1]
        prev_bars = df.iloc[-10:]  # Last 10 bars for pattern analysis
        
        # Criterion 1: Prior bearish trend (looking back 20-30 bars)
        lookback_bars = df.iloc[-30:] if len(df) >= 30 else df
        
        # Check if there was a bearish trend before the reversal
        early_trend = lookback_bars.iloc[:15]  # First half of lookback period
        recent_trend = lookback_bars.iloc[-15:]  # Second half for reversal
        
        if early_trend.empty or recent_trend.empty:
            return None
            
        # Was there a prior downtrend? (SMA20 declining)
        early_sma20_slope = early_trend['SMA20_Slope'].mean()
        
        # Criterion 2: Recent reversal - price moving above key levels
        current_price = last_bar['Close']
        sma_20 = last_bar['SMA_20'] 
        sma_50 = last_bar['SMA_50']
        
        # Must be above SMA20 for bullish bias
        if pd.isna(sma_20) or current_price < sma_20:
            return None
            
        # Criterion 3: Volume expansion on recent bars
        recent_volume_ratio = prev_bars['Volume_Ratio'].tail(5).mean()
        if recent_volume_ratio < 1.2:  # At least 20% above average volume
            return None
            
        # Criterion 4: Range expansion (volatility increase)
        recent_range_expansion = prev_bars['Range_Expansion'].tail(5).mean()
        if recent_range_expansion < 1.1:  # At least 10% above average range
            return None
            
        # Criterion 5: Multiple confirmation bars
        # Look for at least 2 bullish bars in last 5 bars
        recent_5_bars = prev_bars.tail(5)
        bullish_bars = (recent_5_bars['Close'] > recent_5_bars['Open']).sum()
        
        if bullish_bars < 2:
            return None
            
        # Criterion 6: Strong body bars (conviction)
        recent_body_ratio = prev_bars['Body_Ratio'].tail(5).mean()
        if recent_body_ratio < 1.0:  # Bodies should be at least average size
            return None
            
        # Criterion 7: Trend change confirmation
        recent_sma20_slope = recent_trend['SMA20_Slope'].tail(5).mean()
        if recent_sma20_slope <= 0:  # SMA20 should be turning up
            return None
            
        # If we've reached here, we have a higher probability long reversal pattern
        
        # Calculate entry, stop loss, and targets
        entry_price = current_price
        
        # Stop loss: Below recent swing low or SMA20, whichever is lower
        recent_swing_lows = df[df['Swing_Low'] == True]['Low'].tail(3)
        if not recent_swing_lows.empty:
            swing_low = recent_swing_lows.min()
            stop_loss = min(swing_low, sma_20 * 0.95)  # 5% below SMA20 as backup
        else:
            stop_loss = sma_20 * 0.95
            
        # Use ATR for more dynamic stop
        atr_stop = current_price - (last_bar['ATR'] * 2.0)  # 2 ATR stop
        stop_loss = max(stop_loss, atr_stop)  # Take the higher (less aggressive) stop
        
        # Calculate pattern strength score
        strength_score = 0
        
        # Volume strength (0-25 points)
        volume_score = min(25, (recent_volume_ratio - 1.0) * 50)
        strength_score += max(0, volume_score)
        
        # Range expansion (0-20 points)
        range_score = min(20, (recent_range_expansion - 1.0) * 40)
        strength_score += max(0, range_score)
        
        # Trend change strength (0-25 points)
        trend_score = min(25, recent_sma20_slope * 5)
        strength_score += max(0, trend_score)
        
        # Position above moving averages (0-20 points)
        ma_score = 0
        if current_price > sma_20:
            ma_score += 10
        if not pd.isna(sma_50) and current_price > sma_50:
            ma_score += 10
        strength_score += ma_score
        
        # Number of confirmation bars (0-10 points)
        confirmation_score = min(10, bullish_bars * 2)
        strength_score += confirmation_score
        
        return {
            'pattern_type': 'Higher Probability LONG Reversal',
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'strength_score': strength_score,
            'volume_expansion': recent_volume_ratio,
            'range_expansion': recent_range_expansion,
            'bullish_bars': bullish_bars,
            'trend_slope': recent_sma20_slope,
            'above_sma20': current_price > sma_20,
            'above_sma50': not pd.isna(sma_50) and current_price > sma_50
        }
        
    except Exception as e:
        logger.error(f"Error in higher probability reversal detection: {e}")
        return None

def process_ticker(ticker):
    """Process a single ticker for higher probability reversal patterns"""
    logger.info(f"Processing {ticker}")
    
    try:
        now = datetime.datetime.now()
        
        # Extended date range for weekly analysis (2 years for better pattern recognition)
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
        
        if reversal_pattern is None:
            logger.info(f"{ticker} - No higher probability LONG reversal pattern detected")
            return None
        
        # Get the most recent values
        last_bar = weekly_with_indicators.iloc[-1]
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
        
        # Log the findings
        logger.info(f"{ticker} - WEEKLY Higher Probability LONG Reversal detected:")
        logger.info(f"  Entry: ₹{entry_price:.2f}, Stop: ₹{stop_loss:.2f}, Target1: ₹{target1:.2f}")
        logger.info(f"  Risk: ₹{risk:.2f}, R:R: {risk_reward_ratio:.1f}, Strength: {reversal_pattern['strength_score']:.1f}")
        
        return {
            'Ticker': ticker,
            'Entry_Price': round(entry_price, 2),
            'Stop_Loss': round(stop_loss, 2),
            'Target_1': round(target1, 2),
            'Target_2': round(target2, 2),
            'Risk_Amount': round(risk, 2),
            'Risk_Reward_Ratio': round(risk_reward_ratio, 1),
            'Strength_Score': round(reversal_pattern['strength_score'], 1),
            'Volume_Expansion': round(reversal_pattern['volume_expansion'], 2),
            'Range_Expansion': round(reversal_pattern['range_expansion'], 2),
            'Bullish_Bars': reversal_pattern['bullish_bars'],
            'Trend_Slope': round(reversal_pattern['trend_slope'], 2),
            'Above_SMA20': reversal_pattern['above_sma20'],
            'Above_SMA50': reversal_pattern['above_sma50'],
            'ATR': round(last_bar['ATR'], 2),
            'Current_Price': round(last_price, 2),
            'SMA_20': round(last_bar['SMA_20'], 2) if not pd.isna(last_bar['SMA_20']) else 0,
            'SMA_50': round(last_bar['SMA_50'], 2) if not pd.isna(last_bar['SMA_50']) else 0,
            'Volume_Ratio': round(last_bar['Volume_Ratio'], 2),
            'Pattern_Type': reversal_pattern['pattern_type'],
            'Timeframe': 'Weekly'
        }
        
    except Exception as e:
        logger.error(f"Error processing {ticker}: {e}")
        return None

def generate_html_report(filtered_df, output_file, scanner_file):
    """Generate HTML report with detailed analysis"""
    try:
        # Calculate averages outside f-string to avoid formatting issues
        if not filtered_df.empty:
            avg_risk_reward = f"{filtered_df['Risk_Reward_Ratio'].mean():.1f}"
            avg_strength = f"{filtered_df['Strength_Score'].mean():.1f}"
            total_analyzed = len(filtered_df)
        else:
            avg_risk_reward = 'N/A'
            avg_strength = 'N/A'
            total_analyzed = 0

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Weekly Higher Probability LONG Reversal Analysis</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .header {{ background-color: #2c3e50; color: white; padding: 20px; border-radius: 10px; text-align: center; }}
        .summary {{ background-color: white; padding: 15px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stocks-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin: 20px 0; }}
        .stock-card {{ background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 5px solid #27ae60; }}
        .stock-header {{ font-size: 1.4em; font-weight: bold; color: #2c3e50; margin-bottom: 15px; }}
        .metric-row {{ display: flex; justify-content: space-between; margin: 8px 0; padding: 5px 0; }}
        .metric-label {{ font-weight: bold; color: #34495e; }}
        .metric-value {{ color: #2c3e50; }}
        .positive {{ color: #27ae60; }}
        .negative {{ color: #e74c3c; }}
        .neutral {{ color: #f39c12; }}
        .pattern-badge {{ background-color: #3498db; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; }}
        .strength-high {{ background-color: #27ae60; }}
        .strength-medium {{ background-color: #f39c12; }}
        .strength-low {{ background-color: #e74c3c; }}
        .footer {{ text-align: center; margin-top: 40px; color: #7f8c8d; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Weekly Higher Probability LONG Reversal Analysis</h1>
        <p>Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Timeframe: Weekly | Strategy: Al Brooks Higher Probability Reversal</p>
    </div>

    <div class="summary">
        <h2>📈 Summary</h2>
        <p><strong>Total Stocks Analyzed:</strong> {total_analyzed}</p>
        <p><strong>Higher Probability LONG Reversals Found:</strong> {len(filtered_df)}</p>
        <p><strong>Average Risk-Reward Ratio:</strong> {avg_risk_reward}</p>
        <p><strong>Average Strength Score:</strong> {avg_strength}</p>
        <p><strong>Source:</strong> {scanner_file}</p>
    </div>
"""
        
        if not filtered_df.empty:
            html_content += '<div class="stocks-grid">'
            
            for _, stock in filtered_df.iterrows():
                # Determine strength class
                strength_class = 'strength-high' if stock['Strength_Score'] >= 70 else 'strength-medium' if stock['Strength_Score'] >= 50 else 'strength-low'
                
                html_content += f"""
    <div class="stock-card">
        <div class="stock-header">
            {stock['Ticker']} 
            <span class="pattern-badge {strength_class}">Strength: {stock['Strength_Score']:.1f}</span>
        </div>
        
        <div class="metric-row">
            <span class="metric-label">Entry Price:</span>
            <span class="metric-value">₹{stock['Entry_Price']:.2f}</span>
        </div>
        
        <div class="metric-row">
            <span class="metric-label">Stop Loss:</span>
            <span class="metric-value negative">₹{stock['Stop_Loss']:.2f}</span>
        </div>
        
        <div class="metric-row">
            <span class="metric-label">Target 1 (1:2):</span>
            <span class="metric-value positive">₹{stock['Target_1']:.2f}</span>
        </div>
        
        <div class="metric-row">
            <span class="metric-label">Target 2 (1:3):</span>
            <span class="metric-value positive">₹{stock['Target_2']:.2f}</span>
        </div>
        
        <div class="metric-row">
            <span class="metric-label">Risk Amount:</span>
            <span class="metric-value">₹{stock['Risk_Amount']:.2f}</span>
        </div>
        
        <div class="metric-row">
            <span class="metric-label">Risk:Reward:</span>
            <span class="metric-value {'positive' if stock['Risk_Reward_Ratio'] >= 2 else 'neutral'}">1:{stock['Risk_Reward_Ratio']:.1f}</span>
        </div>
        
        <div class="metric-row">
            <span class="metric-label">Volume Expansion:</span>
            <span class="metric-value {'positive' if stock['Volume_Expansion'] > 1.5 else 'neutral'}">{stock['Volume_Expansion']:.2f}x</span>
        </div>
        
        <div class="metric-row">
            <span class="metric-label">Range Expansion:</span>
            <span class="metric-value {'positive' if stock['Range_Expansion'] > 1.3 else 'neutral'}">{stock['Range_Expansion']:.2f}x</span>
        </div>
        
        <div class="metric-row">
            <span class="metric-label">Bullish Bars:</span>
            <span class="metric-value">{stock['Bullish_Bars']}/5</span>
        </div>
        
        <div class="metric-row">
            <span class="metric-label">Above SMA20:</span>
            <span class="metric-value {'positive' if stock['Above_SMA20'] else 'negative'}">{'✓' if stock['Above_SMA20'] else '✗'}</span>
        </div>
        
        <div class="metric-row">
            <span class="metric-label">Above SMA50:</span>
            <span class="metric-value {'positive' if stock['Above_SMA50'] else 'negative'}">{'✓' if stock['Above_SMA50'] else '✗'}</span>
        </div>
        
        <div class="metric-row">
            <span class="metric-label">ATR:</span>
            <span class="metric-value">₹{stock['ATR']:.2f}</span>
        </div>
    </div>
"""
            
            html_content += '</div>'
        else:
            html_content += '<div class="summary"><p>No weekly higher probability LONG reversal patterns found.</p></div>'
        
        html_content += """
    <div class="footer">
        <p>📊 Weekly Higher Probability LONG Reversal Analysis | Based on Al Brooks Price Action Trading</p>
        <p><em>This analysis is for educational purposes only. Please do your own research before making investment decisions.</em></p>
    </div>
</body>
</html>
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML report generated: {output_file}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating HTML report: {e}")
        return False

def main():
    """Main function to filter tickers for higher probability LONG reversals using weekly timeframe"""
    logger.info("Weekly Higher Probability LONG Reversal filter")

    start_time = time.time()

    try:
        # Read the tickers
        tickers = read_ticker_file()
        if not tickers:
            logger.error("No tickers found, exiting")
            return 1

        logger.info(f"Starting weekly analysis for {len(tickers)} tickers")

        # Initialize counters for analysis
        counters = {
            'total_processed': 0,
            'no_instrument_token': 0,
            'no_weekly_data': 0,
            'insufficient_data': 0,
            'no_pattern': 0,
            'patterns_found': 0
        }

        # Process each ticker
        results = []
        for ticker in tickers:
            counters['total_processed'] += 1

            # Check if we already know this ticker has no instrument token
            if ticker in cache.instrument_tokens and cache.instrument_tokens[ticker] is None:
                counters['no_instrument_token'] += 1
                continue

            result = process_ticker(ticker)
            if result:
                results.append(result)
                counters['patterns_found'] += 1
        
        # Create output files with timestamp
        today = datetime.datetime.now()
        formatted_date = today.strftime("%d_%m_%Y")
        formatted_time = today.strftime("%H_%M")
        excel_file = os.path.join(RESULTS_DIR, f"Brooks_Higher_Probability_LONG_Reversal_Weekly_{formatted_date}_{formatted_time}.xlsx")
        html_file = os.path.join(HTML_DIR, f"Higher_Probability_LONG_Analysis_Weekly_{formatted_date}_{formatted_time.replace('_', '-')}.html")
        
        if results:
            # Create DataFrame and save to Excel
            df = pd.DataFrame(results)
            
            # Sort by strength score (highest first)
            df = df.sort_values('Strength_Score', ascending=False)
            
            # Save to Excel
            df.to_excel(excel_file, index=False)
            logger.info(f"Results saved to Excel: {excel_file}")
            
            # Generate HTML report
            generate_html_report(df, html_file, TICKER_FILE)
            
            # Open HTML file in browser
            try:
                webbrowser.open(f'file://{html_file}')
                logger.info("HTML report opened in browser")
            except Exception as e:
                logger.warning(f"Could not open HTML report in browser: {e}")
            
            # Summary
            logger.info(f"Weekly Analysis Summary:")
            logger.info(f"  Total tickers processed: {counters['total_processed']}")
            logger.info(f"  Skipped (no instrument token): {counters['no_instrument_token']}")
            logger.info(f"  Higher probability LONG reversals found: {len(results)}")
            logger.info(f"  Average strength score: {df['Strength_Score'].mean():.1f}")
            logger.info(f"  Average risk-reward ratio: 1:{df['Risk_Reward_Ratio'].mean():.1f}")

            # Show top results
            logger.info(f"Top 5 weekly candidates by strength:")
            for i, row in df.head(5).iterrows():
                logger.info(f"  {row['Ticker']}: Entry ₹{row['Entry_Price']:.2f}, R:R 1:{row['Risk_Reward_Ratio']:.1f}, Strength {row['Strength_Score']:.1f}")

        else:
            logger.info("No weekly higher probability LONG reversal patterns found")
            logger.info(f"Analysis Summary:")
            logger.info(f"  Total tickers processed: {counters['total_processed']}")
            logger.info(f"  Skipped (no instrument token): {counters['no_instrument_token']}")

            # Create empty Excel file
            empty_df = pd.DataFrame(columns=['Ticker', 'Entry_Price', 'Stop_Loss', 'Target_1', 'Target_2', 'Risk_Reward_Ratio', 'Strength_Score', 'Timeframe'])
            empty_df.to_excel(excel_file, index=False)

            # Generate empty HTML report
            generate_html_report(empty_df, html_file, TICKER_FILE)

        execution_time = time.time() - start_time
        logger.info(f"Weekly analysis completed in {execution_time:.2f} seconds")
        logger.info(f"Consistency Report - Tickers with instrument token issues: {counters['no_instrument_token']}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        return 1

if __name__ == "__main__":
    print("\n===================================")
    print("Higher Probability WEEKLY Reversal Filter")
    print("===================================")
    print("Finding weekly higher probability reversal setups (60%+):")
    print("1. Strong weekly breakout confirmation")
    print("2. Multiple confirmation weeks")
    print("3. Break of significant weekly levels")
    print("4. Volume expansion on breakout")
    print("5. Wider stops for higher probability")
    print("===================================")
    print(f"Using credentials for user: {user_name}")
    print("===================================\n")

    exit_code = main()
    sys.exit(exit_code)