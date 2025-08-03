#!/usr/bin/env python3
"""
OHLC Data Downloader Utility

This script downloads historical OHLC data for tickers and organizes them in a structured
folder hierarchy. It fetches data from Zerodha API and updates existing files with new data.

Usage:
    python download_ohlc_data.py --tickers-file Ticker.xlsx --timeframes 5minute,day,hour
    python download_ohlc_data.py --tickers RELIANCE,TCS,HDFCBANK --timeframes day
    python download_ohlc_data.py --timeframes day,hour
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Import the data handler to use existing functionality
try:
    from data_handler import get_data_handler
except ImportError:
    print("Could not import data_handler. Make sure you're running this script from the project root.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
TIMEFRAMES = {
    "5minute": {"folder": "5min", "days_history": 30, "name": "5minute"},
    "hour": {"folder": "hour", "days_history": 90, "name": "60minute"},
    "day": {"folder": "daily", "days_history": 365, "name": "day"},
}
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ohlc_data")

def setup_directories(output_dir):
    """
    Create directories for each timeframe and ensure they exist.
    
    Args:
        output_dir (str): Base output directory
        
    Returns:
        dict: Dictionary of paths mapped to timeframes
    """
    paths = {}
    for timeframe, info in TIMEFRAMES.items():
        folder_path = os.path.join(output_dir, info["folder"])
        os.makedirs(folder_path, exist_ok=True)
        paths[timeframe] = folder_path
    
    logger.info(f"Created directories for data storage at {output_dir}")
    return paths

def extract_tickers_from_excel(file_path):
    """
    Extract tickers from an Excel file.
    
    Args:
        file_path (str): Path to Excel file
        
    Returns:
        list: List of tickers
    """
    try:
        # Try several common column names that might contain ticker symbols
        possible_columns = ["Ticker", "Symbol", "Scrip", "Stock", "Script", "Name", "SYMBOL", "TICKER"]
        
        df = pd.read_excel(file_path)
        
        # Find the first column that exists in the DataFrame
        ticker_column = None
        for col in possible_columns:
            if col in df.columns:
                ticker_column = col
                break
        
        if ticker_column is None:
            # If no standard column is found, use the first column
            ticker_column = df.columns[0]
            logger.warning(f"Using first column '{ticker_column}' as ticker column")
        
        tickers = df[ticker_column].dropna().astype(str).tolist()
        
        # Clean up tickers (remove any whitespace, special chars)
        tickers = [t.strip() for t in tickers]
        
        logger.info(f"Extracted {len(tickers)} tickers from {file_path}")
        return tickers
    
    except Exception as e:
        logger.error(f"Error extracting tickers from {file_path}: {str(e)}")
        return []

def get_historical_data(data_handler, ticker, timeframe, from_date, to_date):
    """
    Get historical data for a ticker.

    Args:
        data_handler: The data handler instance
        ticker (str): Ticker symbol
        timeframe (str): Timeframe to use
        from_date: Start date for data
        to_date: End date for data

    Returns:
        pd.DataFrame: Historical OHLC data
    """
    try:
        # Use data handler to fetch historical data
        data = data_handler.fetch_historical_data(ticker, timeframe, from_date, to_date)

        # Ensure we have enough data
        if data is None or len(data) == 0:
            logger.warning(f"Insufficient data for {ticker}: Got {len(data) if data is not None else 0} points")
            return None

        # Ensure data has required columns (check both upper and lower case)
        required_columns_upper = ['Open', 'High', 'Low', 'Close', 'Volume']
        required_columns_lower = ['open', 'high', 'low', 'close', 'volume']

        # Check if upper case columns exist
        has_upper_columns = all(col in data.columns for col in required_columns_upper)
        # Check if lower case columns exist
        has_lower_columns = all(col in data.columns for col in required_columns_lower)

        if not (has_upper_columns or has_lower_columns):
            logger.error(f"Missing required columns in data for {ticker}")
            return None

        return data

    except Exception as e:
        logger.error(f"Error fetching historical data for {ticker}: {str(e)}")
        return None

def download_data_for_ticker(data_handler, ticker, timeframe, output_path, update_existing=True):
    """
    Download OHLC data for a single ticker and timeframe.

    Args:
        data_handler: The data handler instance to use for fetching data
        ticker (str): Ticker symbol
        timeframe (str): Timeframe to download data for
        output_path (str): Directory to save the data to
        update_existing (bool): Whether to update existing files or overwrite

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        timeframe_info = TIMEFRAMES[timeframe]
        days_history = timeframe_info["days_history"]
        timeframe_name = timeframe_info["name"]
        
        output_file = os.path.join(output_path, f"{ticker}_{timeframe_name}.csv")
        
        # Determine the date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_history)
        
        # Check if file exists and we need to update it
        existing_data = None
        if update_existing and os.path.exists(output_file):
            try:
                existing_data = pd.read_csv(output_file)
                if 'date' in existing_data.columns:
                    existing_data['date'] = pd.to_datetime(existing_data['date'])
                    
                    # Get the latest date in the file
                    latest_date = existing_data['date'].max()
                    
                    # Only fetch data from the latest date onwards
                    start_date = latest_date
                    
                    logger.info(f"Updating existing data for {ticker} ({timeframe}) from {start_date.date()}")
                else:
                    logger.warning(f"Existing file for {ticker} does not have 'date' column, will overwrite")
                    existing_data = None
            except Exception as e:
                logger.warning(f"Error reading existing file for {ticker}: {str(e)}, will overwrite")
                existing_data = None
        
        # Fetch the data
        logger.info(f"Fetching {timeframe} data for {ticker} from {start_date.date()} to {end_date.date()}")
        data = data_handler.fetch_historical_data(
            ticker,
            timeframe_name,
            from_date=start_date.date(),
            to_date=end_date.date()
        )
        
        if data is None or len(data) == 0:
            logger.warning(f"No data returned for {ticker} ({timeframe})")
            return False
        
        # Check for the date column (either 'date' or 'Date')
        date_column = None
        if 'date' in data.columns:
            date_column = 'date'
        elif 'Date' in data.columns:
            date_column = 'Date'
        else:
            logger.error(f"Data for {ticker} does not have a date column (date or Date)")
            return False

        # Ensure the date column is datetime
        data[date_column] = pd.to_datetime(data[date_column])

        # Standardize column names for consistent output
        column_mapping = {
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
            'Ticker': 'ticker'
        }

        # Rename columns if needed
        for old_name, new_name in column_mapping.items():
            if old_name in data.columns:
                data.rename(columns={old_name: new_name}, inplace=True)
        
        # If there's existing data, merge with new data
        if existing_data is not None:
            # Remove duplicates
            data = pd.concat([existing_data, data])
            data = data.drop_duplicates(subset=['date'], keep='last')
            
            # Sort by date
            data = data.sort_values('date')
        
        # Save the data
        data.to_csv(output_file, index=False)
        logger.info(f"Saved {len(data)} rows of {timeframe} data for {ticker} to {output_file}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error downloading data for {ticker} ({timeframe}): {str(e)}")
        return False

def download_all_data(tickers, timeframes, output_dir, update_existing=True):
    """
    Download data for all tickers and timeframes.
    
    Args:
        tickers (list): List of tickers to download data for
        timeframes (list): List of timeframes to download
        output_dir (str): Directory to save the data to
        update_existing (bool): Whether to update existing files or overwrite
        
    Returns:
        dict: Dictionary with statistics about the download results
    """
    # Setup directories
    paths = setup_directories(output_dir)
    
    # Get data handler
    data_handler = get_data_handler()
    
    # Statistics
    stats = {
        "success": 0,
        "failed": 0,
        "total": len(tickers) * len(timeframes),
    }
    
    # Download data for each ticker and timeframe
    for ticker in tickers:
        for timeframe in timeframes:
            if timeframe not in TIMEFRAMES:
                logger.warning(f"Unknown timeframe: {timeframe}, skipping")
                stats["failed"] += 1
                continue
                
            output_path = paths[timeframe]
            result = download_data_for_ticker(
                data_handler, 
                ticker, 
                timeframe, 
                output_path, 
                update_existing
            )
            
            if result:
                stats["success"] += 1
            else:
                stats["failed"] += 1
    
    return stats

def main():
    parser = argparse.ArgumentParser(description="Download OHLC data for tickers")
    
    # Add arguments
    ticker_group = parser.add_mutually_exclusive_group()
    ticker_group.add_argument("--tickers", type=str, help="Comma-separated list of tickers")
    ticker_group.add_argument("--tickers-file", type=str, help="Path to Excel file with tickers")
    
    parser.add_argument("--timeframes", type=str, default="day", help="Comma-separated list of timeframes (5minute,hour,day)")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--force-refresh", action="store_true", help="Force refresh all data (don't update existing)")
    
    args = parser.parse_args()
    
    # Validate timeframes
    timeframes = [tf.strip() for tf in args.timeframes.split(",")]
    valid_timeframes = [tf for tf in timeframes if tf in TIMEFRAMES]
    if not valid_timeframes:
        logger.error(f"No valid timeframes provided. Valid options are: {', '.join(TIMEFRAMES.keys())}")
        return 1
    
    if len(valid_timeframes) != len(timeframes):
        logger.warning(f"Some timeframes are invalid and will be skipped. Valid options are: {', '.join(TIMEFRAMES.keys())}")
    
    # Get tickers
    tickers = []
    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",")]
    elif args.tickers_file:
        if not os.path.exists(args.tickers_file):
            # Try looking in the same directory as the script
            local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.basename(args.tickers_file))
            if os.path.exists(local_path):
                args.tickers_file = local_path
            else:
                logger.error(f"Tickers file not found: {args.tickers_file}")
                return 1
        tickers = extract_tickers_from_excel(args.tickers_file)
    else:
        # Default to Ticker.xlsx in the script's directory
        tickers_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Ticker.xlsx")
        if os.path.exists(tickers_file):
            tickers = extract_tickers_from_excel(tickers_file)
        else:
            logger.error("No tickers specified and default Ticker.xlsx not found")
            return 1
    
    if not tickers:
        logger.error("No tickers to download data for")
        return 1
    
    logger.info(f"Downloading data for {len(tickers)} tickers in {len(valid_timeframes)} timeframes")
    
    # Download data
    stats = download_all_data(
        tickers, 
        valid_timeframes, 
        args.output_dir, 
        update_existing=not args.force_refresh
    )
    
    # Print statistics
    logger.info(f"Download completed: {stats['success']}/{stats['total']} successful, {stats['failed']} failed")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())