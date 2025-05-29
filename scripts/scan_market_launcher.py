#!/usr/bin/env python

import os
import sys
import logging
import argparse
from datetime import datetime
import importlib

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config

# Set up logging
def setup_logging():
    config = get_config()
    log_dir = config.get('System', 'log_dir')
    log_level = config.get('System', 'log_level')
    
    os.makedirs(log_dir, exist_ok=True)
    
    # Create scanner launcher log file
    log_file = os.path.join(log_dir, 'scan_market_launcher.log')
    
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
    parser = argparse.ArgumentParser(description="Launch market scanner based on config settings")
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
        "-s", "--scanner", 
        help="Override scanner type from config (default or bull_trend_pullback)"
    )
    parser.add_argument(
        "-t", "--timeframe", 
        help="Override timeframe from config (day or hour)"
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
    logger.info(f"===== Market Scanner Launcher Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    
    # Get configuration
    config = get_config()
    
    # Determine which scanner to run
    scanner_type = args.scanner or config.get('Scanner', 'scanner_type', fallback='default')
    timeframe = args.timeframe or config.get('Scanner', 'timeframe', fallback='day')
    
    logger.info(f"Using scanner type: {scanner_type}, timeframe: {timeframe}")
    
    # Import the appropriate scanner module based on configuration
    try:
        if scanner_type.lower() == 'bull_trend_pullback':
            logger.info("Launching Bull Trend Pullback scanner")
            import scan_market_BTPB
            scanner_module = scan_market_BTPB
        else:
            logger.info("Launching default scanner")
            import scan_market
            scanner_module = scan_market
            
        # Execute the scanner's main function
        # We're using sys.argv to pass the original command line arguments
        # This is because the main functions expect to parse them directly
        sys.argv = [scanner_module.__file__]
        if args.input:
            sys.argv.extend(['-i', args.input])
        if args.verbose:
            sys.argv.append('-v')
            
        # Run the scanner's main function
        scanner_module.main()
        
        logger.info(f"Scanner {scanner_type} completed successfully")
        
    except ImportError as e:
        logger.error(f"Failed to import scanner module: {e}")
    except Exception as e:
        logger.exception(f"Error running scanner: {e}")
    
    # Log end of execution
    logger.info(f"===== Market Scanner Launcher Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====\n")

if __name__ == "__main__":
    main()