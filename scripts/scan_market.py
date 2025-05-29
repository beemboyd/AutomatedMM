#!/usr/bin/env python

import os
import sys
import logging
import argparse
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config
from trading_logic import get_trading_logic
from data_handler import get_data_handler

# Set up logging
def setup_logging():
    config = get_config()
    log_dir = config.get('System', 'log_dir')
    log_level = config.get('System', 'log_level')
    
    os.makedirs(log_dir, exist_ok=True)
    
    # Create scan_market.log in the log directory
    log_file = os.path.join(log_dir, 'scan_market.log')
    
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
    parser = argparse.ArgumentParser(description="Scan market for trading opportunities")
    parser.add_argument(
        "-i", "--input", 
        help="Path to input Excel file with ticker list"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Increase output verbosity"
    )
    return parser.parse_args()

def main():
    # Parse command line arguments
    args = parse_args()
    
    # Initialize logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Log start of execution
    logger.info(f"===== Market Scan Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    
    # Get configuration
    config = get_config()
    
    # Verify that we're using MIS product type for scanning
    scan_product_type = config.get('Trading', 'scan_product_type', fallback='MIS')
    if scan_product_type != "MIS":
        logger.error(f"This script can only operate on MIS scan_product_type, but found {scan_product_type}")
        logger.error("For CNC (delivery) orders, use the scripts in the Daily folder")
        logger.error("Set scan_product_type = MIS in config.ini [Trading] section for hourly scanning")
        return
    
    # Get trading logic
    trading_logic = get_trading_logic()
    
    # Generate trading signals
    input_file = args.input
    logger.info(f"Generating trading signals from {input_file if input_file else 'default ticker list'}")
    
    # Log gap filtering settings
    gap_up_threshold = trading_logic.gap_up_threshold
    gap_down_threshold = trading_logic.gap_down_threshold
    logger.info(f"Gap filtering enabled: Excluding long signals with gap up > {gap_up_threshold}% and short signals with gap down < {gap_down_threshold}%")
    
    try:
        long_file, short_file = trading_logic.generate_trading_signals(input_file)
        
        if long_file and short_file:
            logger.info(f"Successfully generated signal files:")
            logger.info(f"  Long signals: {os.path.basename(long_file)}")
            logger.info(f"  Short signals: {os.path.basename(short_file)}")
        else:
            logger.error("Failed to generate signal files")
        
    except Exception as e:
        logger.exception(f"Error during market scan: {e}")
    
    # Log end of execution
    logger.info(f"===== Market Scan Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====\n")

if __name__ == "__main__":
    main()
