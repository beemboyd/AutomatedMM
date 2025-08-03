#!/usr/bin/env python3
"""
Simple wrapper script for the OHLC data downloader utility.

This script provides a simpler interface to download OHLC data for use in price-volume
analysis and market regime detection.

Usage:
    python download_data.py              # Downloads daily data for all tickers in Ticker.xlsx
    python download_data.py --all        # Downloads all timeframes (5min, hourly, daily) for all tickers
    python download_data.py --ticker TCS # Downloads daily data for TCS only
"""

import os
import sys
import logging
import argparse
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="Download OHLC data for stocks")
    
    parser.add_argument("--ticker", type=str, help="Single ticker to download data for")
    parser.add_argument("--all", action="store_true", help="Download data for all timeframes")
    parser.add_argument("--daily", action="store_true", help="Download daily data only (default)")
    parser.add_argument("--hourly", action="store_true", help="Download hourly data only")
    parser.add_argument("--5min", action="store_true", help="Download 5-minute data only")
    parser.add_argument("--force-refresh", action="store_true", help="Force refresh all data (don't update existing)")
    
    args = parser.parse_args()
    return args

def build_command(args):
    # Get path to the main downloader script
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download_ohlc_data.py")
    
    # Start building the command
    cmd = [sys.executable, script_path]
    
    # Add ticker argument if specified
    if args.ticker:
        cmd.extend(["--tickers", args.ticker])
    else:
        tickers_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Ticker.xlsx")
        cmd.extend(["--tickers-file", tickers_file])
    
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
    
    cmd.extend(["--timeframes", ",".join(timeframes)])
    
    # Add force refresh if specified
    if args.force_refresh:
        cmd.append("--force-refresh")
    
    return cmd

def main():
    args = parse_args()
    cmd = build_command(args)
    
    logger.info(f"Executing: {' '.join(cmd)}")
    
    # Execute the command
    try:
        result = subprocess.run(cmd, check=True)
        logger.info(f"Download completed with exit code {result.returncode}")
        return result.returncode
    except subprocess.CalledProcessError as e:
        logger.error(f"Download failed with exit code {e.returncode}")
        return e.returncode
    except Exception as e:
        logger.error(f"Error executing download command: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())