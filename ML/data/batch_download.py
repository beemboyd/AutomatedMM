#!/usr/bin/env python3
"""
Batch OHLC Data Downloader

This script downloads OHLC data in batches to avoid overwhelming the API and handle large
ticker lists more efficiently. It's especially useful for downloading the initial data set
or when you need to refresh data for a large number of tickers.

Usage:
    python batch_download.py                 # Downloads daily data in batches
    python batch_download.py --all           # Downloads all timeframes in batches
    python batch_download.py --batch-size 20 # Sets batch size to 20 tickers
"""

import os
import sys
import logging
import argparse
import time
from datetime import datetime
import pandas as pd
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"batch_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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

def process_batch(batch_tickers, timeframes, force_refresh=False):
    """
    Process a batch of tickers.
    
    Args:
        batch_tickers (list): List of tickers to process
        timeframes (list): List of timeframes to download
        force_refresh (bool): Whether to force refresh all data
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Get path to the main downloader script
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download_ohlc_data.py")
    
    # Build the command
    cmd = [sys.executable, script_path, "--tickers", ",".join(batch_tickers), 
           "--timeframes", ",".join(timeframes)]
    
    if force_refresh:
        cmd.append("--force-refresh")
    
    logger.info(f"Processing batch of {len(batch_tickers)} tickers: {', '.join(batch_tickers)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"Batch completed with exit code {result.returncode}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Batch processing failed with exit code {e.returncode}")
        logger.error(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Error processing batch: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Download OHLC data in batches")
    
    parser.add_argument("--tickers-file", type=str, help="Path to Excel file with tickers")
    parser.add_argument("--batch-size", type=int, default=10, help="Number of tickers to process in each batch")
    parser.add_argument("--delay", type=int, default=5, help="Delay in seconds between batches")
    
    parser.add_argument("--all", action="store_true", help="Download all timeframes")
    parser.add_argument("--daily", action="store_true", help="Download daily data only (default)")
    parser.add_argument("--hourly", action="store_true", help="Download hourly data only")
    parser.add_argument("--5min", action="store_true", help="Download 5-minute data only")
    parser.add_argument("--force-refresh", action="store_true", help="Force refresh all data (don't update existing)")
    
    args = parser.parse_args()
    
    # Get tickers
    tickers_file = args.tickers_file
    if not tickers_file:
        # Default to Ticker.xlsx in the script's directory
        tickers_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Ticker.xlsx")
    
    if not os.path.exists(tickers_file):
        logger.error(f"Tickers file not found: {tickers_file}")
        return 1
    
    tickers = extract_tickers_from_excel(tickers_file)
    if not tickers:
        logger.error("No tickers to download data for")
        return 1
    
    # Determine timeframes
    timeframes = []
    if args.all:
        timeframes = ["5minute", "hour", "day"]
    elif args.hourly:
        timeframes.append("hour")
    elif args.daily:
        timeframes.append("day")
    elif args.__getattribute__("5min"):
        timeframes.append("5minute")
    else:
        # Default to daily if nothing specified
        timeframes.append("day")
    
    # Process in batches
    batch_size = max(1, min(args.batch_size, len(tickers)))  # Ensure batch size is reasonable
    delay = max(1, args.delay)  # Ensure delay is at least 1 second
    
    logger.info(f"Starting batch download for {len(tickers)} tickers in batches of {batch_size}")
    logger.info(f"Timeframes: {', '.join(timeframes)}")
    
    # Create batches
    batches = [tickers[i:i+batch_size] for i in range(0, len(tickers), batch_size)]
    successful_batches = 0
    
    # Create output directory if it doesn't exist
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ohlc_data")
    for timeframe in timeframes:
        folder_name = "daily" if timeframe == "day" else ("hour" if timeframe == "hour" else "5min")
        os.makedirs(os.path.join(output_dir, folder_name), exist_ok=True)
    
    # Process each batch
    for i, batch in enumerate(batches):
        logger.info(f"Processing batch {i+1}/{len(batches)} ({len(batch)} tickers)")
        
        start_time = time.time()
        success = process_batch(batch, timeframes, args.force_refresh)
        
        if success:
            successful_batches += 1
        
        # Sleep between batches (if not the last batch)
        if i < len(batches) - 1:
            # Calculate how much time to sleep (ensure we sleep at least 1 second)
            elapsed = time.time() - start_time
            sleep_time = max(1, delay - elapsed)
            
            logger.info(f"Waiting {sleep_time:.1f} seconds before next batch...")
            time.sleep(sleep_time)
    
    logger.info(f"Batch download completed: {successful_batches}/{len(batches)} batches successful")
    
    return 0 if successful_batches == len(batches) else 1

if __name__ == "__main__":
    sys.exit(main())