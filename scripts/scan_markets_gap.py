#!/usr/bin/env python

import os
import sys
import logging
import argparse
import datetime
import pandas as pd
import numpy as np
from collections import defaultdict

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config
from data_handler import get_data_handler

# Set up logging
def setup_logging():
    config = get_config()
    log_dir = config.get('System', 'log_dir')
    log_level = config.get('System', 'log_level')
    
    os.makedirs(log_dir, exist_ok=True)
    
    # Create scan_markets_gap.log in the log directory
    log_file = os.path.join(log_dir, 'scan_markets_gap.log')
    
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
    parser = argparse.ArgumentParser(description="Scan market for gap trading opportunities")
    parser.add_argument(
        "-i", "--input", 
        help="Path to input Excel file with ticker list"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Increase output verbosity"
    )
    parser.add_argument(
        "--gap-up-threshold",
        type=float,
        default=1.0,
        help="Minimum gap up percentage to consider (default: 1.0)"
    )
    parser.add_argument(
        "--gap-down-threshold",
        type=float,
        default=-1.0,
        help="Maximum gap down percentage to consider (default: -1.0)"
    )
    parser.add_argument(
        "--enforce-end-time",
        help="Exit if current time is after this time (format: HH:MM)"
    )
    return parser.parse_args()

def calculate_gap(data):
    """Calculate gap percentage from previous day close to current day open"""
    if len(data) < 2:
        return 0.0
    
    data = data.sort_values('Date')
    
    # Group data by date to handle intraday data properly
    data['date_only'] = data['Date'].dt.date
    date_groups = data.groupby('date_only')
    
    # Get list of unique dates
    unique_dates = sorted(data['date_only'].unique())
    
    if len(unique_dates) < 2:
        return 0.0
    
    # Get the last close of the previous day
    prev_day = unique_dates[-2]
    prev_day_data = date_groups.get_group(prev_day)
    prev_close = prev_day_data['Close'].iloc[-1]
    
    # Get the first open of the current day
    current_day = unique_dates[-1]
    current_day_data = date_groups.get_group(current_day)
    current_open = current_day_data['Open'].iloc[0]
    
    # Calculate gap percentage
    gap_percent = ((current_open - prev_close) / prev_close) * 100
    
    return gap_percent

def identify_trends(data):
    """
    Identify if a ticker is trending up or down based on Higher Highs/Higher Lows 
    or Lower Highs/Lower Lows patterns in 5-minute candles
    """
    if len(data) < 3:
        return None, None, None
    
    # Sort data by date in ascending order
    data = data.sort_values('Date')
    
    # Get the last 3 candles (including the gap candle and two subsequent ones)
    last_three_candles = data.tail(3).reset_index(drop=True)
    
    # Extract highs and lows
    highs = last_three_candles['High'].values
    lows = last_three_candles['Low'].values
    
    # Check for Higher Highs and Higher Lows (uptrend)
    higher_highs = (highs[1] > highs[0] and highs[2] > highs[1])
    higher_lows = (lows[1] > lows[0] and lows[2] > lows[1])
    
    # Check for Lower Highs and Lower Lows (downtrend)
    lower_highs = (highs[1] < highs[0] and highs[2] < highs[1])
    lower_lows = (lows[1] < lows[0] and lows[2] < lows[1])
    
    # Determine trend direction
    uptrend = higher_highs and higher_lows
    downtrend = lower_highs and lower_lows
    
    # Return the gap candle (for reference) and the trend information
    gap_candle = last_three_candles.iloc[0]
    
    return gap_candle, uptrend, downtrend

def generate_signals(tickers, gap_up_threshold, gap_down_threshold, logger):
    """Generate trading signals based on gap analysis and trend detection"""
    data_handler = get_data_handler()
    config = get_config()
    exchange = config.get('Trading', 'exchange')
    
    long_signals = []
    short_signals = []
    
    # Current date and time for timestamp
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M")
    
    # Set the default end time to now
    end_date = now.strftime("%Y-%m-%d")
    
    # Set the start date to 5 days ago to capture enough daily data
    start_date = (now - datetime.timedelta(days=5)).strftime("%Y-%m-%d")
    
    # Process each ticker
    for ticker in tickers:
        try:
            logger.info(f"Processing {ticker} for gap analysis...")
            
            # Get daily data for gap detection
            daily_data = data_handler.fetch_historical_data(ticker, "day", start_date, end_date)
            if daily_data.empty:
                logger.warning(f"No daily data found for {ticker}, skipping.")
                continue
                
            # Calculate gap percentage
            gap_percent = calculate_gap(daily_data)
            logger.info(f"{ticker}: Gap percent = {gap_percent:.2f}%")
            
            # Skip if the gap doesn't meet thresholds
            if gap_percent < gap_up_threshold and gap_percent > gap_down_threshold:
                logger.info(f"{ticker}: Gap {gap_percent:.2f}% doesn't meet thresholds, skipping.")
                continue
            
            # Get 5-minute data for trend analysis (last day only)
            yesterday = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            minute_data = data_handler.fetch_historical_data(ticker, "5minute", yesterday, end_date)
            if len(minute_data) < 3:
                logger.warning(f"Insufficient 5-minute data for {ticker}, skipping.")
                continue
            
            # Identify trend patterns
            gap_candle, uptrend, downtrend = identify_trends(minute_data)
            if gap_candle is None:
                logger.warning(f"Could not identify trends for {ticker}, skipping.")
                continue
            
            # Current price for reference
            current_price = data_handler.fetch_current_price(ticker)
            
            # Create signal data
            signal_data = {
                'Ticker': ticker,
                'Date': now,
                'Gap%': gap_percent,
                'Open': gap_candle['Open'],
                'High': gap_candle['High'],
                'Low': gap_candle['Low'],
                'Close': gap_candle['Close'],
                'Current': current_price,
                'Uptrend': uptrend,
                'Downtrend': downtrend
            }
            
            # Apply the strategy rules to categorize the signal
            # Rule 1: Gapped up ticker trending down (LH, LL) = Short
            if gap_percent >= gap_up_threshold and downtrend:
                logger.info(f"{ticker}: Gap up ({gap_percent:.2f}%) with downtrend detected. Adding to SHORT candidates.")
                short_signals.append(signal_data)
                
            # Rule 2: Gapped down ticker trending up (HH, HL) = Long
            elif gap_percent <= gap_down_threshold and uptrend:
                logger.info(f"{ticker}: Gap down ({gap_percent:.2f}%) with uptrend detected. Adding to LONG candidates.")
                long_signals.append(signal_data)
                
            # Rule 3: Gapped up ticker with continued uptrend = Long
            elif gap_percent >= gap_up_threshold and uptrend:
                logger.info(f"{ticker}: Gap up ({gap_percent:.2f}%) with continued uptrend. Adding to LONG candidates.")
                long_signals.append(signal_data)
                
            # Rule 4: Gapped down ticker with continued downtrend = Short
            elif gap_percent <= gap_down_threshold and downtrend:
                logger.info(f"{ticker}: Gap down ({gap_percent:.2f}%) with continued downtrend. Adding to SHORT candidates.")
                short_signals.append(signal_data)
                
        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
    
    # Convert signals to DataFrames
    long_df = pd.DataFrame(long_signals) if long_signals else pd.DataFrame(columns=['Ticker', 'Date', 'Gap%', 'Open', 'High', 'Low', 'Close', 'Current', 'Uptrend', 'Downtrend'])
    short_df = pd.DataFrame(short_signals) if short_signals else pd.DataFrame(columns=['Ticker', 'Date', 'Gap%', 'Open', 'High', 'Low', 'Close', 'Current', 'Uptrend', 'Downtrend'])
    
    # Sort by gap percentage (absolute value)
    if not long_df.empty:
        long_df['AbsGap'] = long_df['Gap%'].abs()
        long_df = long_df.sort_values('AbsGap', ascending=False).drop('AbsGap', axis=1)
        
    if not short_df.empty:
        short_df['AbsGap'] = short_df['Gap%'].abs()
        short_df = short_df.sort_values('AbsGap', ascending=False).drop('AbsGap', axis=1)
    
    # Prepare file paths
    data_dir = config.get('System', 'data_dir')
    long_file = os.path.join(data_dir, f"Gap_Strategy_Long_{timestamp}.xlsx")
    short_file = os.path.join(data_dir, f"Gap_Strategy_Short_{timestamp}.xlsx")
    
    # Save to Excel files
    with pd.ExcelWriter(long_file, engine='openpyxl') as writer:
        long_df.to_excel(writer, sheet_name="Long_Signals", index=False)
        
    with pd.ExcelWriter(short_file, engine='openpyxl') as writer:
        short_df.to_excel(writer, sheet_name="Short_Signals", index=False)
    
    logger.info(f"Generated {len(long_df)} LONG signals and {len(short_df)} SHORT signals")
    logger.info(f"Long signals saved to: {long_file}")
    logger.info(f"Short signals saved to: {short_file}")
    
    return long_file, short_file

def main():
    # Parse command line arguments
    args = parse_args()
    
    # Initialize logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Log start of execution
    logger.info(f"===== Gap Strategy Market Scan Started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    
    # Get configuration
    config = get_config()
    data_handler = get_data_handler()
    
    # Check if we need to enforce an end time
    now = datetime.datetime.now()
    if args.enforce_end_time:
        try:
            hour, minute = map(int, args.enforce_end_time.split(':'))
            end_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if now > end_time:
                logger.info(f"Current time ({now.strftime('%H:%M:%S')}) is after end time ({args.enforce_end_time}). Exiting.")
                return
            else:
                logger.info(f"Running within allowed time window. End time: {args.enforce_end_time}")
        except Exception as e:
            logger.error(f"Error parsing end time ({args.enforce_end_time}): {e}")
    
    # Verify that we're only operating during market hours (9:30 AM to 9:45 AM)
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=9, minute=45, second=0, microsecond=0)
    
    # Allow running at any time if not in production (for testing)
    is_production = config.get_bool('System', 'is_production', fallback=False)
    
    if is_production and (now < market_open or now > market_close):
        logger.warning(f"This scan is designed to run between 9:30 AM and 9:45 AM. Current time: {now.strftime('%H:%M:%S')}")
        if args.verbose:
            logger.info("Running anyway due to verbose flag...")
        else:
            logger.error("Exiting due to out-of-hours execution. Use --verbose to override.")
            return
    
    # Input file handling
    input_file = args.input
    if input_file is None:
        input_file = os.path.join(config.get('System', 'data_dir'), "Ticker.xlsx")
        
    # Load tickers
    logger.info(f"Loading tickers from {input_file}")
    tickers = data_handler.get_tickers_from_file(input_file)
    if not tickers:
        logger.error(f"No tickers found in {input_file}")
        return
        
    logger.info(f"Loaded {len(tickers)} tickers for processing")
    
    # Generate signals
    try:
        long_file, short_file = generate_signals(
            tickers, 
            args.gap_up_threshold, 
            args.gap_down_threshold,
            logger
        )
        
        if long_file and short_file:
            logger.info(f"Successfully generated signal files:")
            logger.info(f"  Long signals: {os.path.basename(long_file)}")
            logger.info(f"  Short signals: {os.path.basename(short_file)}")
        else:
            logger.error("Failed to generate signal files")
            
    except Exception as e:
        logger.exception(f"Error during gap analysis: {e}")
    
    # Log end of execution
    logger.info(f"===== Gap Strategy Market Scan Completed at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====\n")

if __name__ == "__main__":
    main()