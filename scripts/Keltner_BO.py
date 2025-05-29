#!/usr/bin/env python
"""
Keltner Channel Breakout Scanner

This script scans all tickers to identify those that are currently trading
above their Keltner Channel Upper Limit, which can indicate potential breakout trades.

Features:
- Calculates Keltner Channels (20-period SMA with 2 ATR multiplier)
- Identifies tickers trading above their Keltner Channel Upper Limit
- Generates Excel report with various metrics for breakout candidates
- Includes volume conditions to ensure liquidity
- Sorts results by strength metrics to identify highest probability trades

Created: 2025-05-08
"""

import os
import sys
import time
import logging
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
import concurrent.futures

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config
from data_handler import get_data_handler
from kiteconnect import KiteConnect

# Set up logging
def setup_logging():
    config = get_config()
    log_dir = config.get('System', 'log_dir')
    log_level = config.get('System', 'log_level')
    
    os.makedirs(log_dir, exist_ok=True)
    
    # Create Keltner_BO.log in the log directory
    log_file = os.path.join(log_dir, 'Keltner_BO.log')
    
    # Configure logging
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger()
    logger.info(f"Logging initialized at level {log_level}")
    
    return logger

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Scan for tickers above Keltner Channel Upper Limit")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "-i", "--input",
        help="Path to input Excel file with tickers to scan (default: Daily/Ticker.xlsx)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to output Excel file (default: generates timestamped filename)"
    )
    parser.add_argument(
        "--kc-period",
        type=int,
        default=20,
        help="Keltner Channel period (default: 20)"
    )
    parser.add_argument(
        "--atr-period",
        type=int,
        default=14,
        help="ATR period (default: 14)"
    )
    parser.add_argument(
        "--atr-multiplier",
        type=float,
        default=2.0,
        help="ATR multiplier for Keltner Channel width (default: 2.0)"
    )
    parser.add_argument(
        "--min-volume",
        type=int,
        default=100000,
        help="Minimum average volume requirement (default: 100,000)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=5,
        help="Maximum number of worker threads (default: 5)"
    )
    return parser.parse_args()

def get_tickers_from_file(input_file):
    """Load tickers from input Excel file"""
    logger = logging.getLogger()
    
    try:
        df = pd.read_excel(input_file, sheet_name='Ticker', engine='openpyxl')
        tickers = df['Ticker'].dropna().astype(str).tolist()
        logger.info(f"Loaded {len(tickers)} tickers from {input_file}")
        return tickers
    except Exception as e:
        logger.error(f"Error loading tickers from {input_file}: {e}")
        return []

def get_zerodha_instruments():
    """Get all instruments from Zerodha"""
    logger = logging.getLogger()
    config = get_config()
    
    try:
        kite = KiteConnect(api_key=config.get('API', 'api_key'))
        kite.set_access_token(config.get('API', 'access_token'))
        
        instruments = kite.instruments("NSE")
        if instruments:
            df = pd.DataFrame(instruments)
            # Filter out indices, ETFs, etc. - keep only EQ segment
            df = df[df['segment'] == 'NSE']
            tickers = df['tradingsymbol'].dropna().astype(str).tolist()
            logger.info(f"Loaded {len(tickers)} instruments from Zerodha")
            return tickers
        else:
            logger.warning("No instruments returned from Zerodha")
            return []
    except Exception as e:
        logger.error(f"Error getting instruments from Zerodha: {e}")
        return []

def fetch_historical_data(ticker, interval, from_date, to_date, kite, retry_delay=2, max_retries=3):
    """Fetch historical data from Kite API"""
    logger = logging.getLogger()
    
    # Get instrument token from data handler
    data_handler = get_data_handler()
    token = data_handler.get_instrument_token(ticker)
    if token is None:
        logger.warning(f"Instrument token for {ticker} not found.")
        return pd.DataFrame()

    for attempt in range(max_retries):
        try:
            logger.debug(f"Fetching data for {ticker} with interval {interval} from {from_date} to {to_date}...")
            data = kite.historical_data(token, from_date, to_date, interval)

            if not data:
                logger.warning(f"No data returned for {ticker}.")
                return pd.DataFrame()

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

            logger.debug(f"Data successfully fetched for {ticker} with {len(df)} records.")
            return df

        except Exception as e:
            if "Too many requests" in str(e) and attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                logger.warning(
                    f"Rate limit hit for {ticker}. Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
            else:
                logger.error(f"Error fetching data for {ticker}: {e}")
                return pd.DataFrame()

    logger.error(f"Failed to fetch data for {ticker} after {max_retries} attempts.")
    return pd.DataFrame()

def get_current_market_price(ticker, kite):
    """Get the current market price for a ticker"""
    logger = logging.getLogger()
    
    try:
        ltp_data = kite.ltp(f"NSE:{ticker}")
        key = f"NSE:{ticker}"
        
        if ltp_data and key in ltp_data:
            current_close = ltp_data[key]["last_price"]
            logger.debug(f"[Real-time] Ticker {ticker} - Current Close: {current_close}")
            return current_close
        else:
            logger.warning(f"No LTP data for {ticker}.")
            return np.nan
    except Exception as e:
        logger.error(f"Error fetching current close for {ticker}: {e}")
        return np.nan

def calculate_keltner_channels(data, kc_period=20, atr_period=14, atr_multiplier=2.0):
    """Calculate Keltner Channels for a DataFrame"""
    # Calculate SMA
    data['SMA'] = data['Close'].rolling(window=kc_period).mean()
    
    # Calculate ATR
    high_low = data['High'] - data['Low']
    high_close = (data['High'] - data['Close'].shift()).abs()
    low_close = (data['Low'] - data['Close'].shift()).abs()
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    
    data['ATR'] = true_range.rolling(window=atr_period).mean()
    
    # Calculate Keltner Channels
    data['KC_Upper'] = data['SMA'] + (data['ATR'] * atr_multiplier)
    data['KC_Middle'] = data['SMA']
    data['KC_Lower'] = data['SMA'] - (data['ATR'] * atr_multiplier)
    
    # Calculate previous day's low
    data['Prev_Low'] = data['Low'].shift(1)
    
    return data

def analyze_ticker(ticker, kite, args):
    """Analyze a ticker for Keltner Channel breakout"""
    logger = logging.getLogger()
    logger.info(f"Analyzing {ticker} for Keltner Channel breakout")
    
    try:
        # Get historical data
        now = datetime.now()
        from_date = (now - relativedelta(months=6)).strftime('%Y-%m-%d')
        to_date = now.strftime('%Y-%m-%d')
        
        # Fetch data
        data = fetch_historical_data(
            ticker, 
            'day', 
            from_date, 
            to_date, 
            kite
        )
        
        if data.empty or len(data) < 50:
            logger.warning(f"Insufficient historical data for {ticker}")
            return None
        
        # Get current price
        current_price = get_current_market_price(ticker, kite)
        if pd.isna(current_price):
            logger.warning(f"Could not get current price for {ticker}")
            return None
        
        # Calculate Keltner Channels
        data = calculate_keltner_channels(
            data, 
            kc_period=args.kc_period,
            atr_period=args.atr_period,
            atr_multiplier=args.atr_multiplier
        )
        
        # Get most recent values
        latest = data.iloc[-1]
        
        # Check average volume over last 20 days
        avg_volume = data['Volume'].tail(20).mean()
        if avg_volume < args.min_volume:
            logger.debug(f"{ticker} - Average volume {avg_volume} is below minimum {args.min_volume}")
            return None
        
        # Check if price is above Keltner Channel Upper Limit
        kc_upper = latest['KC_Upper']
        is_above_kc = current_price > kc_upper
        
        if not is_above_kc:
            logger.debug(f"{ticker} - Price {current_price} is not above KC Upper {kc_upper}")
            return None
        
        # Calculate additional metrics for the breakout
        breakout_strength = (current_price - kc_upper) / kc_upper * 100  # Percentage above KC
        
        # Check volume spike
        recent_volume_avg = data['Volume'].tail(3).mean()
        prior_volume_avg = data['Volume'].iloc[-20:-3].mean() if len(data) >= 20 else data['Volume'].mean()
        volume_ratio = recent_volume_avg / prior_volume_avg if prior_volume_avg > 0 else 0
        
        # Calculate distance from SMA and 50 EMA
        sma20 = latest['SMA']
        ema50 = data['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
        
        sma_distance = (current_price - sma20) / sma20 * 100
        ema50_distance = (current_price - ema50) / ema50 * 100
        
        # Calculate ATR percentage
        atr_percentage = latest['ATR'] / current_price * 100
        
        # Slope calculation (8-day slope)
        def calculate_slope(y):
            if len(y) < 8 or y[-1] == 0:
                return np.nan
            return (np.polyfit(np.arange(len(y)), y, 1)[0] / y[-1]) * 100
            
        price_slope = calculate_slope(data['Close'].tail(8).values)
        
        # Create result dictionary
        result = {
            'Ticker': ticker,
            'Current_Price': current_price,
            'KC_Upper': kc_upper,
            'KC_Middle': latest['KC_Middle'],
            'KC_Lower': latest['KC_Lower'],
            'Breakout_Strength': breakout_strength,
            'Volume_Ratio': volume_ratio,
            'SMA20': sma20,
            'EMA50': ema50,
            'SMA_Distance': sma_distance,
            'EMA50_Distance': ema50_distance,
            'ATR': latest['ATR'],
            'ATR_Percentage': atr_percentage,
            'Price_Slope': price_slope,
            'Avg_Volume': avg_volume,
            'Prev_Low': latest['Prev_Low'],
            'SL_Keltner': latest['KC_Middle'],  # Middle Keltner as potential stop loss
            'SL_Prev_Low': latest['Prev_Low'],  # Previous day's low as potential stop loss
            'SL_SMA20': sma20,  # SMA20 as potential stop loss
        }
        
        logger.info(f"{ticker} - BREAKOUT DETECTED: Price {current_price} > KC Upper {kc_upper} by {breakout_strength:.2f}%")
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing {ticker}: {e}")
        return None

def scan_tickers(tickers, args):
    """Scan all tickers for Keltner Channel breakouts"""
    logger = logging.getLogger()
    logger.info(f"Scanning {len(tickers)} tickers for Keltner Channel breakouts")
    
    config = get_config()
    kite = KiteConnect(api_key=config.get('API', 'api_key'))
    kite.set_access_token(config.get('API', 'access_token'))
    
    # Use ThreadPoolExecutor for parallel processing
    results = []
    max_workers = min(args.max_workers, len(tickers))
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {executor.submit(analyze_ticker, ticker, kite, args): ticker for ticker in tickers}
        
        for future in concurrent.futures.as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
    
    # Convert results to DataFrame
    if results:
        df = pd.DataFrame(results)
        
        # Sort by breakout strength
        df = df.sort_values(by='Breakout_Strength', ascending=False)
        
        logger.info(f"Found {len(df)} tickers with Keltner Channel breakouts")
        return df
    else:
        logger.info("No tickers with Keltner Channel breakouts found")
        return pd.DataFrame()

def save_results(results_df, output_file):
    """Save results to Excel file"""
    logger = logging.getLogger()
    
    try:
        # Round numeric columns to 2 decimal places
        numeric_cols = results_df.select_dtypes(include=['float64', 'float32']).columns
        results_df[numeric_cols] = results_df[numeric_cols].round(2)
        
        # Save to Excel
        results_df.to_excel(output_file, index=False, engine='openpyxl')
        logger.info(f"Results saved to {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error saving results to {output_file}: {e}")
        return False

def main():
    """Main function"""
    # Parse arguments
    args = parse_args()
    
    # Setup logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Log start of execution
    logger.info(f"===== Keltner Channel Breakout Scanner Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    
    try:
        # Get tickers to scan
        if args.input:
            tickers = get_tickers_from_file(args.input)
        else:
            # Default to Daily/Ticker.xlsx if no input file specified
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            default_input = os.path.join(project_root, "Daily", "Ticker.xlsx")
            
            if os.path.exists(default_input):
                tickers = get_tickers_from_file(default_input)
            else:
                logger.warning(f"Default input file {default_input} not found, fetching all Zerodha instruments")
                tickers = get_zerodha_instruments()
        
        if not tickers:
            logger.error("No tickers to scan")
            return
        
        # Scan tickers
        results = scan_tickers(tickers, args)
        
        if results.empty:
            logger.info("No tickers found above Keltner Channel Upper Limit")
            return
        
        # Determine output file path
        if args.output:
            output_file = args.output
        else:
            # Default to timestamped file
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            results_dir = os.path.join(project_root, "Daily")
            
            # Create directory if it doesn't exist
            os.makedirs(results_dir, exist_ok=True)
            
            # Create timestamped filename
            timestamp = datetime.now().strftime("%d_%m_%Y_%H_%M")
            output_file = os.path.join(results_dir, f"Keltner_Breakout_{timestamp}.xlsx")
        
        # Save results
        save_results(results, output_file)
        
    except Exception as e:
        logger.exception(f"Error during Keltner Channel breakout scanning: {e}")
    
    # Log end of execution
    logger.info(f"===== Keltner Channel Breakout Scanner Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====\n")

if __name__ == "__main__":
    main()