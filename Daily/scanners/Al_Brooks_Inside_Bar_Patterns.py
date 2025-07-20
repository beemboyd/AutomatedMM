#!/usr/bin/env python
# Al_Brooks_Inside_Bar_Patterns.py - Identify II, III, and IOI patterns based on Al Brooks theories
# II Pattern: Two consecutive inside bars
# III Pattern: Three consecutive inside bars
# IOI Pattern: Inside-Outside-Inside (inside bar, outside bar, inside bar)
# These patterns indicate market indecision and potential breakout setups

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
from functools import wraps
from typing import Callable, Any

# Third-party imports
import numpy as np
import pandas as pd
import pytz
from dateutil.relativedelta import relativedelta
from kiteconnect import KiteConnect
import webbrowser

# Add parent directories to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "al_brooks_inside_bar.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def retry_on_rate_limit(max_retries: int = 5, initial_delay: float = 1.0, backoff_factor: float = 2.0):
    """
    Decorator to retry function calls when rate limited
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        backoff_factor: Factor to multiply delay by after each retry
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e).lower()
                    # Check for rate limit errors
                    if any(phrase in error_msg for phrase in ['too many requests', 'rate limit', '429', 'throttle']):
                        last_exception = e
                        if attempt < max_retries:
                            logger.warning(f"Rate limit hit on attempt {attempt + 1}/{max_retries + 1}. "
                                         f"Retrying in {delay:.1f} seconds...")
                            time.sleep(delay)
                            delay *= backoff_factor
                            continue
                        else:
                            logger.error(f"Max retries ({max_retries}) exceeded for rate limit")
                    # For other errors, raise immediately
                    raise e
            
            # If we get here, we've exhausted retries
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Al Brooks Inside Bar Pattern Analysis (II, III, and IOI patterns)")
    parser.add_argument("-u", "--user", default="Sai", help="User name to use for API credentials (default: Sai)")
    return parser.parse_args()

# Load credentials from Daily/config.ini
def load_daily_config(user_name="Sai"):
    """Load configuration from Daily/config.ini"""
    config = configparser.ConfigParser()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    daily_dir = os.path.dirname(script_dir)
    config_path = os.path.join(daily_dir, 'config.ini')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at {config_path}")
    
    config.read(config_path)
    
    # Build section name with prefix
    section_name = f"API_CREDENTIALS_{user_name}"
    
    # Check if user section exists
    if section_name not in config:
        # List available users (remove the prefix for display)
        available_users = [s.replace("API_CREDENTIALS_", "") for s in config.sections() if s.startswith("API_CREDENTIALS_")]
        raise ValueError(f"User '{user_name}' not found in config.ini. Available users: {', '.join(available_users)}")
    
    user_config = config[section_name]
    
    return {
        'api_key': user_config.get('api_key'),
        'api_secret': user_config.get('api_secret'),
        'access_token': user_config.get('access_token', ''),
        'user_id': user_config.get('user_id'),
        'password': user_config.get('password'),
        'totp_secret': user_config.get('totp_secret', ''),
        'base_dir': daily_dir
    }

def load_ticker_data():
    """Load ticker data from Excel file"""
    ticker_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "data", "Ticker.xlsx")
    
    if not os.path.exists(ticker_file):
        logger.error(f"Ticker file not found: {ticker_file}")
        return pd.DataFrame()
    
    df = pd.read_excel(ticker_file)
    logger.info(f"Loaded {len(df)} tickers from {ticker_file}")
    return df

def login_kite(api_key, api_secret, access_token=None):
    """Login to Kite Connect and return authenticated session"""
    try:
        kite = KiteConnect(api_key=api_key)
        
        # If access token provided in config, use it directly
        if access_token:
            kite.set_access_token(access_token)
            # Verify token works
            try:
                kite.profile()
                logger.info("Using access token from config file")
                return kite
            except Exception as e:
                logger.error(f"Access token from config invalid: {e}")
                raise ValueError("Access token in config.ini is invalid or expired. Please update it.")
        
        # Fallback to file-based token (for backward compatibility)
        access_token_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                        "data", "access_token.txt")
        
        if os.path.exists(access_token_file):
            # Check if token is recent (less than 8 hours old)
            file_time = os.path.getmtime(access_token_file)
            if time.time() - file_time < 8 * 3600:
                with open(access_token_file, 'r') as f:
                    file_access_token = f.read().strip()
                if file_access_token:
                    kite.set_access_token(file_access_token)
                    # Verify token works
                    try:
                        kite.profile()
                        logger.info("Using existing access token from file")
                        return kite
                    except:
                        logger.info("File token invalid")
        
        # If no valid token, raise error
        raise ValueError("No valid access token found. Please update the access_token in config.ini")
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise

# Global cache for instruments to reduce API calls
_instruments_cache = None

@retry_on_rate_limit(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
def get_instruments(kite, exchange="NSE"):
    """Get instruments with caching to reduce API calls"""
    global _instruments_cache
    if _instruments_cache is None:
        logger.info(f"Fetching instruments for {exchange}...")
        _instruments_cache = kite.instruments(exchange)
    return _instruments_cache

@retry_on_rate_limit(max_retries=5, initial_delay=2.0, backoff_factor=2.0)
def get_historical_data(kite, symbol, days=30):
    """Fetch historical data for a symbol with automatic retry on rate limits"""
    try:
        # Get instrument token from cache
        instruments = get_instruments(kite, "NSE")
        instrument = next((i for i in instruments if i['tradingsymbol'] == symbol), None)
        
        if not instrument:
            logger.warning(f"Symbol {symbol} not found")
            return pd.DataFrame()
        
        # Calculate date range
        to_date = datetime.datetime.now()
        from_date = to_date - datetime.timedelta(days=days)
        
        # Fetch daily candles
        data = kite.historical_data(
            instrument['instrument_token'],
            from_date.date(),
            to_date.date(),
            interval="day"
        )
        
        if not data:
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        df['symbol'] = symbol
        return df
        
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame()

def identify_inside_bar(current_bar, previous_bar):
    """Check if current bar is inside previous bar"""
    # Inside bar: High is lower than previous high AND Low is higher than previous low
    return (current_bar['high'] < previous_bar['high'] and 
            current_bar['low'] > previous_bar['low'])

def identify_outside_bar(current_bar, previous_bar):
    """Check if current bar is outside previous bar (engulfing)"""
    # Outside bar: High is higher than previous high AND Low is lower than previous low
    return (current_bar['high'] > previous_bar['high'] and 
            current_bar['low'] < previous_bar['low'])

def identify_ii_iii_ioi_patterns(df):
    """Identify II, III, and IOI patterns in the dataframe"""
    if len(df) < 4:  # Need at least 4 bars for patterns
        return None, None
    
    patterns = []
    
    # Sort by date to ensure proper order
    df = df.sort_values('date').reset_index(drop=True)
    
    # Check for patterns (need at least last 4 bars)
    for i in range(3, len(df)):
        # Get the last 4 bars
        bar_0 = df.iloc[i-3]  # Oldest
        bar_1 = df.iloc[i-2]
        bar_2 = df.iloc[i-1]
        bar_3 = df.iloc[i]    # Most recent
        
        # Check for III pattern (3 consecutive inside bars)
        if (identify_inside_bar(bar_1, bar_0) and 
            identify_inside_bar(bar_2, bar_1) and 
            identify_inside_bar(bar_3, bar_2)):
            
            pattern = {
                'type': 'III',
                'date': bar_3['date'],
                'mother_bar': bar_0,  # The bar that contains all inside bars
                'inside_bars': [bar_1, bar_2, bar_3],
                'high_breakout': bar_0['high'],
                'low_breakout': bar_0['low'],
                'range': bar_0['high'] - bar_0['low'],
                'current_price': bar_3['close']
            }
            patterns.append(pattern)
            
        # Check for IOI pattern (Inside-Outside-Inside)
        elif (identify_inside_bar(bar_1, bar_0) and 
              identify_outside_bar(bar_2, bar_1) and 
              identify_inside_bar(bar_3, bar_2)):
            
            pattern = {
                'type': 'IOI',
                'date': bar_3['date'],
                'mother_bar': bar_2,  # The outside bar is the key reference
                'pattern_bars': [bar_0, bar_1, bar_2, bar_3],
                'high_breakout': bar_2['high'],  # Outside bar high
                'low_breakout': bar_2['low'],    # Outside bar low
                'range': bar_2['high'] - bar_2['low'],
                'current_price': bar_3['close']
            }
            patterns.append(pattern)
            
        # Check for II pattern (2 consecutive inside bars)
        elif (identify_inside_bar(bar_2, bar_1) and 
              identify_inside_bar(bar_3, bar_2)):
            
            pattern = {
                'type': 'II',
                'date': bar_3['date'],
                'mother_bar': bar_1,  # The bar that contains the inside bars
                'inside_bars': [bar_2, bar_3],
                'high_breakout': bar_1['high'],
                'low_breakout': bar_1['low'],
                'range': bar_1['high'] - bar_1['low'],
                'current_price': bar_3['close']
            }
            patterns.append(pattern)
    
    # Return the most recent pattern if any
    if patterns:
        return patterns[-1], df
    else:
        return None, None

def calculate_pattern_strength(pattern, df):
    """Calculate strength score for inside bar pattern"""
    score = 0
    reasons = []
    
    # 1. Tighter inside bars (smaller range) = stronger pattern
    mother_range = pattern['range']
    
    if pattern['type'] == 'IOI':
        # For IOI, check the final inside bar compression
        last_inside_range = pattern['pattern_bars'][-1]['high'] - pattern['pattern_bars'][-1]['low']
    else:
        # For II and III patterns
        last_inside_range = pattern['inside_bars'][-1]['high'] - pattern['inside_bars'][-1]['low']
    
    compression_ratio = last_inside_range / mother_range
    
    if compression_ratio < 0.3:
        score += 2
        reasons.append("Very tight compression (<30%)")
    elif compression_ratio < 0.5:
        score += 1
        reasons.append("Good compression (<50%)")
    
    # 2. Volume analysis
    if pattern['type'] == 'IOI':
        # For IOI, check if outside bar had high volume and inside bar has low volume
        volumes = [bar['volume'] for bar in pattern['pattern_bars']]
        if volumes[2] > volumes[1] * 1.5 and volumes[3] < volumes[2] * 0.7:
            score += 1
            reasons.append("High volume on outside bar, low on inside")
    else:
        # For II and III - decreasing volume in inside bars
        volumes = [bar['volume'] for bar in pattern['inside_bars']]
        if all(volumes[i] < volumes[i-1] for i in range(1, len(volumes))):
            score += 1
            reasons.append("Decreasing volume pattern")
    
    # 3. Pattern type bonus
    if pattern['type'] == 'III':
        score += 1
        reasons.append("III pattern (stronger than II)")
    elif pattern['type'] == 'IOI':
        score += 2
        reasons.append("IOI pattern (high volatility setup)")
    
    # 4. Location relative to recent trend
    if len(df) >= 20:
        sma20 = df['close'].rolling(20).mean().iloc[-1]
        if pattern['current_price'] > sma20:
            score += 1
            reasons.append("Above 20-day SMA (bullish bias)")
    
    # 5. Range relative to ATR
    if len(df) >= 14:
        atr = calculate_atr(df, 14)
        if pattern['type'] == 'IOI':
            # IOI patterns typically have wider ranges due to outside bar
            if pattern['range'] > atr * 1.5:
                score += 1
                reasons.append("Wide range outside bar (strong volatility)")
        else:
            # II and III patterns benefit from tight ranges
            if pattern['range'] < atr * 0.7:
                score += 1
                reasons.append("Tight range relative to ATR")
    
    return score, reasons

def calculate_atr(df, period=14):
    """Calculate Average True Range"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(period).mean().iloc[-1]
    
    return atr

def analyze_ticker(kite, symbol):
    """Analyze a single ticker for inside bar patterns"""
    try:
        # Get historical data
        df = get_historical_data(kite, symbol, days=30)
        
        if df.empty:
            return None
        
        # Identify patterns
        pattern, price_df = identify_ii_iii_ioi_patterns(df)
        
        if not pattern:
            return None
        
        # Calculate pattern strength
        score, reasons = calculate_pattern_strength(pattern, df)
        
        # Calculate entry and stop loss levels
        entry_long = pattern['high_breakout'] * 1.001  # Entry above high
        entry_short = pattern['low_breakout'] * 0.999  # Entry below low
        
        # Stop loss at opposite side of pattern
        sl_long = pattern['low_breakout'] * 0.995
        sl_short = pattern['high_breakout'] * 1.005
        
        # Calculate risk-reward
        risk_long = entry_long - sl_long
        reward_long = risk_long * 2  # 2:1 RR
        target_long = entry_long + reward_long
        
        risk_short = sl_short - entry_short
        reward_short = risk_short * 2  # 2:1 RR
        target_short = entry_short - reward_short
        
        # Calculate compression based on pattern type
        if pattern['type'] == 'IOI':
            compression_range = pattern['pattern_bars'][-1]['high'] - pattern['pattern_bars'][-1]['low']
        else:
            compression_range = pattern['inside_bars'][-1]['high'] - pattern['inside_bars'][-1]['low']
        
        compression_pct = (compression_range / pattern['range']) * 100
        
        result = {
            'Symbol': symbol,
            'Pattern': pattern['type'],
            'Date': pattern['date'].strftime('%Y-%m-%d'),
            'Score': score,
            'Max_Score': 7,  # Increased max score to account for IOI bonus
            'Reasons': ', '.join(reasons),
            'Current_Price': round(pattern['current_price'], 2),
            'Mother_Bar_High': round(pattern['high_breakout'], 2),
            'Mother_Bar_Low': round(pattern['low_breakout'], 2),
            'Pattern_Range': round(pattern['range'], 2),
            'Compression': f"{compression_pct:.1f}%",
            'Entry_Long': round(entry_long, 2),
            'SL_Long': round(sl_long, 2),
            'Target_Long': round(target_long, 2),
            'Entry_Short': round(entry_short, 2),
            'SL_Short': round(sl_short, 2),
            'Target_Short': round(target_short, 2),
            'RR_Ratio': 2.0
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return None

def save_results(results, base_dir):
    """Save results to Excel file with StrategyR naming convention"""
    if not results:
        logger.warning("No results to save")
        return None
    
    # Create results dataframe
    df_results = pd.DataFrame(results)
    
    # Sort by score and pattern type
    df_results = df_results.sort_values(['Pattern', 'Score'], ascending=[True, False])
    
    # Generate filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Report_StrategyR_{timestamp}.xlsx"
    filepath = os.path.join(base_dir, "results", filename)
    
    # Ensure results directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Save to Excel with formatting
    with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
        df_results.to_excel(writer, sheet_name='Inside_Bar_Patterns', index=False)
        
        # Get workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Inside_Bar_Patterns']
        
        # Add formats
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BD',
            'border': 1
        })
        
        # Format headers
        for col_num, value in enumerate(df_results.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Adjust column widths
        worksheet.set_column('A:A', 12)  # Symbol
        worksheet.set_column('B:B', 10)  # Pattern
        worksheet.set_column('C:C', 12)  # Date
        worksheet.set_column('D:E', 8)   # Score
        worksheet.set_column('F:F', 40)  # Reasons
        worksheet.set_column('G:P', 12)  # Price columns
        
        # Add conditional formatting for scores
        worksheet.conditional_format('D2:D1000', {
            'type': '3_color_scale',
            'min_color': '#FF6B6B',
            'mid_color': '#FFE66D',
            'max_color': '#4ECDC4'
        })
    
    logger.info(f"Results saved to: {filepath}")
    return filepath

def generate_summary_report(results):
    """Generate and print summary report"""
    if not results:
        print("\n❌ No inside bar patterns found")
        return
    
    df = pd.DataFrame(results)
    
    print("\n" + "="*60)
    print("AL BROOKS INSIDE BAR PATTERNS - SUMMARY REPORT")
    print("="*60)
    
    # Pattern distribution
    pattern_counts = df['Pattern'].value_counts()
    print(f"\n📊 PATTERN DISTRIBUTION:")
    for pattern, count in pattern_counts.items():
        print(f"   {pattern} Patterns: {count}")
    
    # Top patterns by score
    print(f"\n🏆 TOP 10 PATTERNS BY SCORE:")
    top_patterns = df.nlargest(10, 'Score')
    
    for _, row in top_patterns.iterrows():
        print(f"\n{row['Symbol']} ({row['Pattern']} Pattern):")
        print(f"   Score: {row['Score']}/{row['Max_Score']}")
        print(f"   Date: {row['Date']}")
        print(f"   Current Price: ₹{row['Current_Price']}")
        print(f"   Breakout Levels: ₹{row['Mother_Bar_High']} / ₹{row['Mother_Bar_Low']}")
        print(f"   Compression: {row['Compression']}")
        print(f"   Reasons: {row['Reasons']}")
    
    # Statistics
    print(f"\n📈 STATISTICS:")
    print(f"   Total Patterns Found: {len(df)}")
    print(f"   Average Score: {df['Score'].mean():.2f}")
    print(f"   High Score Patterns (≥4): {len(df[df['Score'] >= 4])}")
    
    print("\n" + "="*60)

def main():
    """Main function"""
    start_time = time.time()
    
    # Parse arguments
    args = parse_args()
    user_name = args.user
    
    # Header
    print("\n" + "="*60)
    print("AL BROOKS INSIDE BAR PATTERN SCANNER")
    print("="*60)
    print("Scanning for II, III, and IOI patterns")
    print("II Pattern: Two consecutive inside bars")
    print("III Pattern: Three consecutive inside bars")
    print("IOI Pattern: Inside-Outside-Inside bar sequence")
    print("="*60)
    print(f"Using credentials for user: {user_name}")
    print("="*60 + "\n")
    
    try:
        # Load configuration
        config = load_daily_config(user_name)
        
        # Login to Kite
        kite = login_kite(config['api_key'], config['api_secret'], config.get('access_token'))
        
        # Load tickers
        ticker_df = load_ticker_data()
        if ticker_df.empty:
            logger.error("No tickers loaded")
            return
        
        # Analyze each ticker
        results = []
        total_tickers = len(ticker_df)
        batch_size = 10  # Process in batches to manage rate limits
        delay_between_tickers = 0.2  # 200ms delay between tickers
        
        print(f"Analyzing {total_tickers} tickers...")
        
        for idx, row in ticker_df.iterrows():
            symbol = row.get('Ticker', row.get('Symbol', ''))
            if not symbol:
                continue
            
            # Progress indicator
            if (idx + 1) % 10 == 0:
                print(f"Progress: {idx + 1}/{total_tickers} ({(idx + 1)/total_tickers*100:.1f}%)")
            
            try:
                result = analyze_ticker(kite, symbol)
                if result:
                    results.append(result)
                    logger.info(f"Found {result['Pattern']} pattern in {symbol} with score {result['Score']}")
            except Exception as e:
                if 'too many requests' in str(e).lower():
                    # If we still hit rate limit despite retries, pause longer
                    logger.warning(f"Rate limit hit for {symbol}, pausing for 30 seconds...")
                    time.sleep(30)
                    # Try once more
                    try:
                        result = analyze_ticker(kite, symbol)
                        if result:
                            results.append(result)
                    except Exception as retry_error:
                        logger.error(f"Failed to analyze {symbol} after retry: {retry_error}")
                else:
                    logger.error(f"Error analyzing {symbol}: {e}")
            
            # Small delay between requests to avoid rate limits
            time.sleep(delay_between_tickers)
            
            # Longer pause every batch_size tickers
            if (idx + 1) % batch_size == 0:
                logger.info(f"Completed batch {(idx + 1) // batch_size}, pausing for 2 seconds...")
                time.sleep(2)
        
        # Generate summary report
        generate_summary_report(results)
        
        # Save results
        if results:
            filepath = save_results(results, config['base_dir'])
            print(f"\n💾 Detailed results saved to: {filepath}")
        
        # Execution time
        execution_time = time.time() - start_time
        print(f"\n⏱️  Execution time: {execution_time:.2f} seconds")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()