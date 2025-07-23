#!/usr/bin/env python
# Long_Reversal_Daily_FNO_Liquid.py - Filter FNO Liquid stocks based on higher probability reversal criteria with Sector information:
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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "long_reversal_fno_liquid.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse command line arguments for user
def parse_args():
    parser = argparse.ArgumentParser(description="Long Reversal Daily Analysis for FNO Liquid stocks with Sector Information")
    parser.add_argument("-u", "--user", default="Sai", help="User name to use for API credentials (default: Sai)")
    return parser.parse_args()

# Load credentials from Daily/config.ini
def load_credentials(user):
    config = configparser.ConfigParser()
    config.read(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.ini"))
    
    if user in config:
        api_key = config[user]['api_key']
        return api_key
    else:
        raise ValueError(f"User {user} not found in config.ini")

# The rest of the functions remain the same as Long_Reversal_Daily.py
# but will use FNO_Liquid.xlsx instead of Ticker.xlsx

from Daily.scanners.Long_Reversal_Daily import (
    convert_to_dynamic_period, reverse_adjust_price, round_to_nse_price,
    calculate_stop_loss, save_results_to_excel, create_hyperlink,
    create_detailed_analysis_report, process_ticker, analyze_longs
)
from Daily.market_regime_scanner import trigger_market_regime_analysis

# Main execution
if __name__ == "__main__":
    # Parse arguments
    args = parse_args()
    user = args.user
    
    # Load API credentials
    api_key = load_credentials(user)
    
    # Output paths - use FNO/Long/Liquid directory
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                              "FNO", "Long", "Liquid")
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_path = os.path.join(output_dir, f"Long_Reversal_Daily_FNO_{timestamp}.xlsx")
    html_path = os.path.join(output_dir, f"Long_Reversal_Daily_FNO_{timestamp}.html")
    
    try:
        # Load FNO Liquid ticker list
        ticker_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                   "data", "FNO_Liquid.xlsx")
        
        if os.path.exists(ticker_file):
            tickers_df = pd.read_excel(ticker_file)
            logger.info(f"Loaded {len(tickers_df)} FNO Liquid tickers from {ticker_file}")
        else:
            logger.error(f"FNO Liquid ticker file not found: {ticker_file}")
            sys.exit(1)
        
        # Run analysis
        logger.info("Starting Long Reversal analysis for FNO Liquid stocks...")
        results = analyze_longs(api_key, tickers_df, user=user)
        
        if results:
            # Save results
            save_results_to_excel(results, excel_path)
            create_detailed_analysis_report(results, html_path)
            
            logger.info(f"Analysis complete. Results saved to:")
            logger.info(f"  Excel: {excel_path}")
            logger.info(f"  HTML: {html_path}")
            
            # Open the HTML report
            webbrowser.open(f"file://{os.path.abspath(html_path)}")
            
            # Trigger market regime analysis
            try:
                trigger_market_regime_analysis()
            except Exception as e:
                logger.warning(f"Failed to trigger market regime analysis: {e}")
        else:
            logger.info("No stocks met the Long Reversal criteria for FNO Liquid stocks")
            
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        import traceback
        traceback.print_exc()