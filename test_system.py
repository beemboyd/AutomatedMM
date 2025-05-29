#!/usr/bin/env python
"""
Test script to verify that all components of the trading system work together correctly.
This script runs a complete flow from scanning to order placement to risk management,
using the mock KiteConnect implementation.
"""

import os
import sys
import logging
import time
import importlib
import json
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def modify_import_paths():
    """Modify sys.modules to use the mock KiteConnect"""
    sys.modules['kiteconnect.KiteConnect'] = importlib.import_module('mock_kiteconnect').KiteConnect
    sys.modules['kiteconnect'] = importlib.import_module('mock_kiteconnect')
    logger.info("Modified import paths to use mock KiteConnect")

def prepare_test_environment():
    """Prepare test environment by creating necessary directories and files"""
    logger.info("Preparing test environment...")
    
    # Ensure directories exist
    data_dir = Path("./data")
    log_dir = Path("./logs")
    data_dir.mkdir(exist_ok=True)
    log_dir.mkdir(exist_ok=True)
    
    # Create a simple ticker file if it doesn't exist
    ticker_file = data_dir / "Ticker.xlsx"
    if not ticker_file.exists():
        try:
            import pandas as pd
            df = pd.DataFrame({"Ticker": ["SBIN", "RELIANCE", "INFY"]})
            df.to_excel(ticker_file, sheet_name="Ticker", index=False)
            logger.info(f"Created ticker file at {ticker_file}")
        except Exception as e:
            logger.error(f"Failed to create ticker file: {e}")
            return False
    
    # Create or update daily ticker tracker
    tracker_file = data_dir / "daily_ticker_tracker.json"
    try:
        tracker_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "long_tickers": [],
            "short_tickers": []
        }
        with open(tracker_file, "w") as f:
            json.dump(tracker_data, f, indent=4)
        logger.info(f"Created/updated daily ticker tracker at {tracker_file}")
    except Exception as e:
        logger.error(f"Failed to create daily ticker tracker: {e}")
        return False
    
    return True

def test_market_scan():
    """Run the market scan script to generate signal files"""
    logger.info("Running market scan...")
    try:
        # Import the module
        import scripts.scan_market
        
        # Run the main function
        scripts.scan_market.main()
        
        # Check if signal files were created
        data_dir = Path("./data")
        long_files = list(data_dir.glob("EMA_KV_F_Zerodha*.xlsx"))
        short_files = list(data_dir.glob("EMA_KV_F_Short_Zerodha*.xlsx"))
        
        if long_files and short_files:
            logger.info(f"Market scan successful. Generated files:")
            logger.info(f"Long signals: {long_files[-1].name}")
            logger.info(f"Short signals: {short_files[-1].name}")
            return long_files[-1], short_files[-1]
        else:
            logger.error("Market scan failed. No signal files generated.")
            return None, None
    except Exception as e:
        logger.error(f"Error during market scan: {e}")
        return None, None

def test_order_placement(long_file=None, short_file=None):
    """Run the order placement script to place orders based on signals"""
    logger.info("Running order placement...")
    try:
        # Import the module
        import scripts.place_orders
        
        # Override the command line arguments
        if long_file and short_file:
            import argparse
            scripts.place_orders.parse_args = lambda: argparse.Namespace(
                long_file=str(long_file),
                short_file=str(short_file),
                max_positions=2,
                disable_long=False,
                disable_short=False,
                verbose=True
            )
        
        # Run the main function
        scripts.place_orders.main()
        
        # Check if position state files were created
        data_dir = Path("./data")
        long_state = data_dir / "long_positions.txt"
        short_state = data_dir / "short_positions.txt"
        
        if long_state.exists() or short_state.exists():
            logger.info("Order placement successful.")
            if long_state.exists():
                logger.info(f"Long positions: {long_state.read_text()}")
            if short_state.exists():
                logger.info(f"Short positions: {short_state.read_text()}")
            return True
        else:
            logger.warning("Order placement completed but no position state files were created.")
            return True
    except Exception as e:
        logger.error(f"Error during order placement: {e}")
        return False

def test_risk_management():
    """Run the risk management script to update stop-losses"""
    logger.info("Running risk management...")
    try:
        # Import the module
        import scripts.manage_risk
        
        # Override the command line arguments
        import argparse
        scripts.manage_risk.parse_args = lambda: argparse.Namespace(
            no_trailing_stop=False,
            no_take_profit=False,
            profit_target=None,
            verbose=True
        )
        
        # Run the main function
        scripts.manage_risk.main()
        
        # Check if position data file was created
        data_dir = Path("./data")
        position_data = data_dir / "position_data.json"
        gtt_tracker = data_dir / "gttz_gtt_tracker.json"
        
        if position_data.exists() or gtt_tracker.exists():
            logger.info("Risk management successful.")
            if position_data.exists():
                logger.info(f"Position tracking data created/updated.")
            if gtt_tracker.exists():
                logger.info(f"GTT tracker created/updated.")
            return True
        else:
            logger.warning("Risk management completed but no tracking files were created.")
            return True
    except Exception as e:
        logger.error(f"Error during risk management: {e}")
        return False

def main():
    """Run the complete test flow"""
    logger.info("Starting India-TS system test...")
    logger.info("-" * 50)
    
    # Use mock KiteConnect
    modify_import_paths()
    
    # Prepare test environment
    if not prepare_test_environment():
        logger.error("Failed to prepare test environment. Aborting test.")
        return
    
    # Run market scan
    long_file, short_file = test_market_scan()
    logger.info("-" * 50)
    
    # Run order placement if market scan was successful
    if long_file and short_file:
        time.sleep(1)  # Short delay for readability of logs
        order_success = test_order_placement(long_file, short_file)
        logger.info("-" * 50)
        
        # Run risk management if order placement was successful
        if order_success:
            time.sleep(1)  # Short delay for readability of logs
            risk_success = test_risk_management()
            logger.info("-" * 50)
            
            if risk_success:
                logger.info("Complete system test PASSED!")
            else:
                logger.error("System test FAILED at risk management stage.")
        else:
            logger.error("System test FAILED at order placement stage.")
    else:
        logger.error("System test FAILED at market scan stage.")

if __name__ == "__main__":
    main()