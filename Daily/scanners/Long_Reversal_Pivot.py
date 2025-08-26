#!/usr/bin/env python
# Long_Reversal_Pivot.py - Filter stocks based on ChoCh (Change of Character) pattern:
# 1. Detect pivot highs and lows
# 2. Wait for price to break above pivot high (bullish ChoCh)
# 3. Confirm with volume delta analysis
# 4. Track the lowest point between pivot high and breakout for support
# 5. Filter for stocks with confirmed bullish breakout

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
                                       "logs", "long_reversal_pivot.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Long Reversal Pivot Analysis - ChoCh Pattern Detection")
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
    
    # Try to find the ticker in the sector data
    ticker_row = sector_df[sector_df['Ticker'] == ticker]
    if not ticker_row.empty:
        return ticker_row.iloc[0].get('Sector', 'Unknown')
    return "Unknown"

# -----------------------------
# Kite Connect Functions
# -----------------------------
def get_instruments_df():
    """Get the instruments data once per session"""
    if cache.instruments_df is None:
        kite = KiteConnect(api_key=KITE_API_KEY)
        kite.set_access_token(ACCESS_TOKEN)
        try:
            instruments = kite.instruments(exchange="NSE")
            cache.instruments_df = pd.DataFrame(instruments)
            logger.info(f"Loaded {len(cache.instruments_df)} instruments from Kite")
        except Exception as e:
            logger.error(f"Error fetching instruments: {e}")
            instruments_file = os.path.join(DATA_DIR, "instruments.csv")
            if os.path.exists(instruments_file):
                cache.instruments_df = pd.read_csv(instruments_file)
                logger.info(f"Loaded instruments from backup file")
            else:
                raise
    return cache.instruments_df

def get_instrument_token(ticker):
    """Get the instrument token for a given ticker - cached"""
    if ticker not in cache.instrument_tokens:
        instruments_df = get_instruments_df()
        instrument = instruments_df[instruments_df['tradingsymbol'] == ticker]
        
        if instrument.empty:
            logger.warning(f"No instrument found for ticker: {ticker}")
            cache.instrument_tokens[ticker] = None
        else:
            cache.instrument_tokens[ticker] = instrument.iloc[0]['instrument_token']
    
    return cache.instrument_tokens[ticker]

def load_ticker_list():
    """Load the ticker list from Excel file"""
    ticker_file = os.path.join(DATA_DIR, "Ticker.xlsx")
    
    if not os.path.exists(ticker_file):
        logger.error(f"Ticker file not found: {ticker_file}")
        raise FileNotFoundError(f"Ticker file not found: {ticker_file}")
    
    ticker_df = pd.read_excel(ticker_file)
    
    if 'Ticker' not in ticker_df.columns:
        logger.error("Ticker column not found in the Excel file")
        raise ValueError("Ticker column not found in the Excel file")
    
    ticker_list = ticker_df['Ticker'].tolist()
    logger.info(f"Loaded {len(ticker_list)} tickers from {ticker_file}")
    
    return ticker_list

def get_historical_data(ticker, interval='1d', days=100):
    """Fetch historical data with caching and fallback options"""
    cache_key = f"{ticker}_{interval}_{days}"
    
    if cache_key in cache.data_cache:
        return cache.data_cache[cache_key]
    
    instrument_token = get_instrument_token(ticker)
    if instrument_token is None:
        return None
    
    kite = KiteConnect(api_key=KITE_API_KEY)
    kite.set_access_token(ACCESS_TOKEN)
    
    to_date = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    from_date = to_date - relativedelta(days=days)
    
    kite_interval = interval_mapping.get(interval, 'day')
    
    try:
        historical_data = kite.historical_data(
            instrument_token=instrument_token,
            from_date=from_date.date(),
            to_date=to_date.date(),
            interval=kite_interval,
            continuous=False,
            oi=False
        )
        
        if historical_data:
            df = pd.DataFrame(historical_data)
            df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            df.set_index('Date', inplace=True)
            cache.data_cache[cache_key] = df
            return df
        else:
            logger.warning(f"No historical data received for {ticker}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {e}")
        return None

# -----------------------------
# Pivot and ChoCh Pattern Detection
# -----------------------------
def detect_pivots(df, lookback=10):
    """
    Detect pivot highs and lows based on lookback period
    Similar to ta.pivothigh and ta.pivotlow in PineScript
    """
    if len(df) < lookback * 2 + 1:
        return df
    
    # Initialize pivot columns
    df['PivotHigh'] = np.nan
    df['PivotLow'] = np.nan
    
    for i in range(lookback, len(df) - lookback):
        # Check for pivot high
        is_pivot_high = True
        current_high = df['High'].iloc[i]
        
        # Check left side
        for j in range(i - lookback, i):
            if df['High'].iloc[j] >= current_high:
                is_pivot_high = False
                break
        
        # Check right side
        if is_pivot_high:
            for j in range(i + 1, i + lookback + 1):
                if df['High'].iloc[j] >= current_high:
                    is_pivot_high = False
                    break
        
        if is_pivot_high:
            df.loc[df.index[i], 'PivotHigh'] = current_high
        
        # Check for pivot low
        is_pivot_low = True
        current_low = df['Low'].iloc[i]
        
        # Check left side
        for j in range(i - lookback, i):
            if df['Low'].iloc[j] <= current_low:
                is_pivot_low = False
                break
        
        # Check right side
        if is_pivot_low:
            for j in range(i + 1, i + lookback + 1):
                if df['Low'].iloc[j] <= current_low:
                    is_pivot_low = False
                    break
        
        if is_pivot_low:
            df.loc[df.index[i], 'PivotLow'] = current_low
    
    # Forward fill to get the last pivot values
    df['LastPivotHigh'] = df['PivotHigh'].ffill()
    df['LastPivotLow'] = df['PivotLow'].ffill()
    
    return df

def calculate_delta_volume(df, start_idx, end_idx):
    """
    Calculate delta volume between two points
    Delta = sum of volume where close > open minus sum where close < open
    """
    if start_idx >= end_idx or start_idx < 0 or end_idx >= len(df):
        return 0
    
    delta = 0
    for i in range(start_idx, end_idx + 1):
        if df['Close'].iloc[i] > df['Open'].iloc[i]:
            delta += df['Volume'].iloc[i]
        else:
            delta -= df['Volume'].iloc[i]
    
    return delta

def detect_choch_breakout(df, lookback=10, recent_bars=10):
    """
    Detect ChoCh (Change of Character) breakout pattern
    Based on the PineScript logic:
    1. Find pivot highs and lows
    2. Check if price breaks above pivot high (bullish ChoCh)
    3. Find the lowest point between pivot and breakout
    4. Calculate delta volume
    5. Only detect RECENT breakouts (within last 'recent_bars' candles)
    """
    
    # Detect pivots
    df = detect_pivots(df, lookback)
    
    if len(df) < 20:
        return None
    
    # Check for breakout in last 'recent_bars' candles
    for bar_idx in range(len(df) - recent_bars, len(df)):
        if bar_idx < 1:
            continue
            
        current_bar = df.iloc[bar_idx]
        prev_bar = df.iloc[bar_idx - 1]
        
        # Check for bullish breakout (price crossing above pivot high)
        if pd.notna(current_bar['LastPivotHigh']):
            # Check if this bar breaks above pivot high (fresh breakout)
            fresh_breakout = current_bar['High'] > current_bar['LastPivotHigh'] and prev_bar['High'] <= current_bar['LastPivotHigh']
            
            # Or if it's a recent sustained breakout
            recent_sustained = (bar_idx >= len(df) - 3) and current_bar['Close'] > current_bar['LastPivotHigh'] * 1.005
            
            if fresh_breakout or recent_sustained:
                # Find the pivot high index
                pivot_idx = -1
                pivot_date = None
                for i in range(bar_idx - 1, max(0, bar_idx - 50), -1):
                    if pd.notna(df['PivotHigh'].iloc[i]):
                        pivot_idx = i
                        pivot_date = df.index[i]
                        break
                
                if pivot_idx > 0:
                    # Calculate bars since pivot
                    bars_since_pivot = bar_idx - pivot_idx
                    
                    # Find the lowest point between pivot and breakout
                    low_between = df['Low'].iloc[pivot_idx:bar_idx+1].min()
                    low_idx_rel = df['Low'].iloc[pivot_idx:bar_idx+1].idxmin()
                    
                    # Find the highest point (extreme) between pivot and breakout
                    high_between = df['High'].iloc[pivot_idx:bar_idx+1].max()
                    
                    # Calculate delta volume
                    delta_volume = calculate_delta_volume(df, pivot_idx, bar_idx)
                    
                    # Calculate other indicators
                    df['ATR'] = calculate_atr(df)
                    df['AvgVolume20'] = df['Volume'].rolling(window=20).mean()
                    
                    # Volume confirmation
                    volume_ratio = current_bar['Volume'] / df['AvgVolume20'].iloc[bar_idx] if df['AvgVolume20'].iloc[bar_idx] > 0 else 1
                    
                    # Calculate stop loss below the low between pivot and breakout
                    stop_loss = low_between - (0.5 * df['ATR'].iloc[bar_idx]) if pd.notna(df['ATR'].iloc[bar_idx]) else low_between * 0.98
                    
                    # Calculate momentum
                    momentum = ((current_bar['Close'] - df['Close'].iloc[max(0, bar_idx-10)]) / df['Close'].iloc[max(0, bar_idx-10)] * 100) if bar_idx >= 10 else 0
                    
                    # Calculate breakout strength
                    breakout_strength = ((current_bar['Close'] - current_bar['LastPivotHigh']) / current_bar['LastPivotHigh']) * 100
                    
                    # Bars since breakout
                    bars_since_breakout = len(df) - bar_idx - 1
                    
                    return {
                        'pattern': 'ChoCh_Bullish_Breakout',
                        'description': f'Bullish pivot breakout {bars_since_breakout} bars ago',
                        'direction': 'LONG',
                        'pivot_high': current_bar['LastPivotHigh'],
                        'pivot_date': pivot_date.strftime('%Y-%m-%d') if pivot_date else 'Unknown',
                        'bars_since_pivot': bars_since_pivot,
                        'breakout_price': current_bar['High'],
                        'breakout_date': df.index[bar_idx].strftime('%Y-%m-%d'),
                        'bars_since_breakout': bars_since_breakout,
                        'support_level': low_between,
                        'extreme_high': high_between,
                        'extreme_low': low_between,
                        'delta_volume': delta_volume,
                        'volume_ratio': volume_ratio,
                        'entry_price': df.iloc[-1]['Close'],  # Current close
                        'current_price': df.iloc[-1]['Close'],
                        'stop_loss': stop_loss,
                        'momentum': momentum,
                        'breakout_strength': breakout_strength,
                        'strength': 'Strong' if delta_volume > 0 and volume_ratio > 1.2 and breakout_strength > 2 else 'Moderate'
                    }
    
    return None

def calculate_atr(df, period=14):
    """Calculate Average True Range"""
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift(1)).abs()
    low_close = (df['Low'] - df['Close'].shift(1)).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(window=period).mean()
    return atr

# -----------------------------
# Main Scanning Function
# -----------------------------
def scan_for_pivot_breakouts():
    """Scan all tickers for ChoCh pivot breakout patterns"""
    results = []
    ticker_list = load_ticker_list()
    
    logger.info(f"Starting ChoCh pivot breakout scan for {len(ticker_list)} tickers")
    
    for i, ticker in enumerate(ticker_list):
        if (i + 1) % 50 == 0:
            logger.info(f"Progress: {i + 1}/{len(ticker_list)} tickers scanned")
        
        try:
            # Get historical data
            df = get_historical_data(ticker, interval='1d', days=100)
            
            if df is None or df.empty:
                continue
            
            # Detect ChoCh breakout pattern
            pattern = detect_choch_breakout(df)
            
            if pattern:
                # Get sector information
                sector = get_sector_for_ticker(ticker)
                
                # Add ticker and sector to pattern
                pattern['ticker'] = ticker
                pattern['sector'] = sector
                pattern['scan_time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                results.append(pattern)
                logger.info(f"Found ChoCh breakout for {ticker}: {pattern['description']}")
                
        except Exception as e:
            logger.error(f"Error scanning {ticker}: {e}")
            continue
    
    logger.info(f"Scan complete. Found {len(results)} stocks with ChoCh breakout patterns")
    return results

def save_results(results):
    """Save scan results to Excel file with detailed pivot and extreme value information"""
    if not results:
        logger.info("No results to save")
        return None
    
    # Convert to DataFrame
    df = pd.DataFrame(results)
    
    # Replace NaN and Inf values with appropriate defaults
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.fillna({
        'momentum': 0,
        'breakout_strength': 0,
        'volume_ratio': 1,
        'delta_volume': 0,
        'bars_since_breakout': 0,
        'bars_since_pivot': 0
    })
    
    # Sort by bars_since_breakout (most recent first) then by breakout strength
    df = df.sort_values(['bars_since_breakout', 'breakout_strength'], ascending=[True, False])
    
    # Reorder columns for better readability
    column_order = [
        'ticker', 'sector', 'pattern', 'strength',
        'pivot_high', 'pivot_date', 'bars_since_pivot',
        'breakout_price', 'breakout_date', 'bars_since_breakout',
        'current_price', 'entry_price',
        'extreme_high', 'extreme_low', 'support_level', 'stop_loss',
        'delta_volume', 'volume_ratio',
        'momentum', 'breakout_strength',
        'description', 'direction', 'scan_time'
    ]
    
    # Reorder columns if they exist
    df = df[[col for col in column_order if col in df.columns]]
    
    # Generate filename with timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"Long_Reversal_Pivot_{timestamp}.xlsx"
    filepath = os.path.join(RESULTS_DIR, filename)
    
    # Save to Excel with formatting (handle NaN/Inf values)
    with pd.ExcelWriter(filepath, engine='xlsxwriter', engine_kwargs={'options': {'nan_inf_to_errors': True}}) as writer:
        df.to_excel(writer, sheet_name='ChoCh Breakouts', index=False)
        
        # Get workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['ChoCh Breakouts']
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BD',
            'border': 1
        })
        
        price_format = workbook.add_format({'num_format': '₹#,##0.00'})
        percent_format = workbook.add_format({'num_format': '0.00%'})
        number_format = workbook.add_format({'num_format': '#,##0'})
        
        # Write headers with formatting
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Apply number formatting to data
        for row_num in range(1, len(df) + 1):
            for col_num, col_name in enumerate(df.columns):
                value = df.iloc[row_num - 1][col_name]
                
                # Apply appropriate formatting based on column
                if col_name in ['pivot_high', 'breakout_price', 'current_price', 'entry_price', 
                               'extreme_high', 'extreme_low', 'support_level', 'stop_loss']:
                    worksheet.write(row_num, col_num, value, price_format)
                elif col_name in ['momentum', 'breakout_strength']:
                    worksheet.write(row_num, col_num, value / 100, percent_format)
                elif col_name in ['delta_volume']:
                    worksheet.write(row_num, col_num, value, number_format)
                else:
                    worksheet.write(row_num, col_num, value)
        
        # Adjust column widths
        worksheet.set_column('A:A', 12)  # Ticker
        worksheet.set_column('B:B', 15)  # Sector
        worksheet.set_column('C:C', 20)  # Pattern
        worksheet.set_column('D:D', 10)  # Strength
        worksheet.set_column('E:E', 12)  # Pivot High
        worksheet.set_column('F:F', 12)  # Pivot Date
        worksheet.set_column('G:G', 15)  # Bars Since Pivot
        worksheet.set_column('H:H', 12)  # Breakout Price
        worksheet.set_column('I:I', 12)  # Breakout Date
        worksheet.set_column('J:J', 18)  # Bars Since Breakout
        worksheet.set_column('K:L', 12)  # Current/Entry Price
        worksheet.set_column('M:P', 12)  # Extreme values
        worksheet.set_column('Q:R', 15)  # Volume metrics
        worksheet.set_column('S:T', 12)  # Momentum metrics
        worksheet.set_column('U:U', 35)  # Description
    
    logger.info(f"Results saved to {filepath}")
    return filepath

# -----------------------------
# Main Execution
# -----------------------------
def main():
    """Main execution function"""
    try:
        logger.info("=" * 60)
        logger.info("Starting Long Reversal Pivot Scanner (ChoCh Pattern)")
        logger.info("=" * 60)
        
        # Run the scan
        results = scan_for_pivot_breakouts()
        
        # Save results
        if results:
            filepath = save_results(results)
            logger.info(f"Found {len(results)} stocks with ChoCh breakout patterns")
            
            # Print summary
            print("\n" + "=" * 80)
            print("CHOCH PIVOT BREAKOUT SUMMARY - RECENT BREAKOUTS (Last 10 Candles)")
            print("=" * 80)
            for result in results[:10]:  # Show top 10
                print(f"\n{result['ticker']} ({result['sector']})")
                print(f"  Pattern: {result['pattern']} | Strength: {result['strength']}")
                print(f"  ▪ Pivot High: ₹{result['pivot_high']:.2f} on {result['pivot_date']} ({result['bars_since_pivot']} bars ago)")
                print(f"  ▪ Breakout: ₹{result['breakout_price']:.2f} on {result['breakout_date']} ({result['bars_since_breakout']} bars ago)")
                print(f"  ▪ Current Price: ₹{result['current_price']:.2f}")
                print(f"  ▪ Extreme High: ₹{result['extreme_high']:.2f} | Extreme Low: ₹{result['extreme_low']:.2f}")
                print(f"  ▪ Support Level: ₹{result['support_level']:.2f} | Stop Loss: ₹{result['stop_loss']:.2f}")
                print(f"  ▪ Delta Volume: {result['delta_volume']:,.0f} | Volume Ratio: {result['volume_ratio']:.2f}x")
                print(f"  ▪ Momentum: {result['momentum']:.2f}% | Breakout Strength: {result['breakout_strength']:.2f}%")
        else:
            logger.info("No ChoCh breakout patterns found")
        
        logger.info("Scan complete!")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        raise

if __name__ == "__main__":
    main()