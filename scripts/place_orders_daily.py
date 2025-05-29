#!/usr/bin/env python

import os
import sys
import logging
import argparse
import pandas as pd
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config
from data_handler import get_data_handler
from order_manager import get_order_manager
from trading_logic import get_trading_logic

# Set up logging
def setup_logging():
    config = get_config()
    log_dir = config.get('System', 'log_dir')
    log_level = config.get('System', 'log_level')
    
    os.makedirs(log_dir, exist_ok=True)
    
    # Create place_orders_daily.log in the log directory
    log_file = os.path.join(log_dir, 'place_orders_daily.log')
    
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
    parser = argparse.ArgumentParser(description="Place daily CNC orders based on BTPB signals")
    parser.add_argument(
        "-f", "--signal-file", 
        help="Path to BTPB signal file"
    )
    parser.add_argument(
        "-m", "--max-positions", 
        type=int,
        help="Maximum number of positions to take (default: 5)"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Increase output verbosity"
    )
    return parser.parse_args()

def place_orders_from_btpb(order_manager, signal_file, max_positions=5):
    """Place orders based on BTPB signal file"""
    logger = logging.getLogger()
    
    # Load the signal file
    if not os.path.exists(signal_file):
        logger.error(f"Signal file {signal_file} not found")
        return
    
    try:
        # Determine file type and load accordingly
        if signal_file.endswith('.xlsx'):
            # Load Excel file
            signals_df = pd.read_excel(signal_file, engine="openpyxl")
        elif signal_file.endswith('.txt'):
            # Parse text file
            signals = []
            with open(signal_file, 'r') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 6:  # Ticker, Entry, SL, T1, T2, T3
                        ticker = parts[0].strip()
                        
                        # Extract numeric values from strings like "Entry: 296.90"
                        entry = float(parts[1].split(':')[1].strip())
                        sl = float(parts[2].split(':')[1].strip())
                        t1 = float(parts[3].split(':')[1].strip())
                        t2 = float(parts[4].split(':')[1].strip())
                        t3 = float(parts[5].split(':')[1].strip())
                        
                        signals.append({
                            'Ticker': ticker, 
                            'Entry_Price': entry,
                            'Stop_Loss': sl,
                            'Target1': t1,
                            'Target2': t2,
                            'Target3': t3
                        })
            
            signals_df = pd.DataFrame(signals)
        else:
            logger.error(f"Unsupported file format for {signal_file}")
            return
            
        if signals_df.empty:
            logger.info("No opportunities found in signal file")
            return
        
        # Take only the top N opportunities
        signals_df = signals_df.head(max_positions)
        logger.info(f"Selected top {max_positions} opportunities for trading")
        
        # Build order info dictionary
        order_info = {}
        for idx, row in signals_df.iterrows():
            ticker = str(row.get("Ticker", "")).strip()
            if not ticker:
                continue
                
            # Use a standard quantity of 1 for all tickers
            quantity = 1
            stop_loss = row.get("Stop_Loss")
            
            order_info[ticker.upper()] = {
                "quantity": quantity,
                "stop_loss": stop_loss
            }
        
        logger.info(f"Order entries: {list(order_info.keys())}")
        
        # Load previous positions
        previous_state = order_manager.load_position_state(order_manager.long_state_file)
        logger.info(f"Previous positions: {list(previous_state.keys())}")
        
        # Fetch current portfolio positions and pending orders
        portfolio_positions, _ = order_manager.get_portfolio_positions()
        pending_orders = order_manager.get_pending_orders()
        
        # Place orders for new positions
        orders_placed = {}
        for ticker, info in order_info.items():
            if ticker in portfolio_positions or ticker in pending_orders:
                logger.info(f"Order for {ticker} skipped as position already exists or order is pending")
                continue
                
            qty = info["quantity"]
            # Force CNC product type for daily orders
            original_product_type = order_manager.product_type
            order_manager.product_type = "CNC"
            
            # Place the order
            success = order_manager.place_order(ticker, "BUY", "MARKET", qty)
            
            # Restore original product type
            order_manager.product_type = original_product_type
            
            if success:
                orders_placed[ticker] = {"quantity": qty, "timestamp": datetime.now()}
                logger.info(f"Successfully placed CNC BUY order for {ticker} with quantity {qty}")
            else:
                logger.error(f"Failed to place CNC BUY order for {ticker}")
        
        # Update position state for tracking
        new_state = {}
        for ticker, info in order_info.items():
            ticker_upper = ticker.upper()
            if ticker_upper in orders_placed:
                new_state[ticker_upper] = orders_placed[ticker_upper]
            elif ticker_upper in previous_state:
                new_state[ticker_upper] = previous_state[ticker_upper]
        
        order_manager.save_position_state(order_manager.long_state_file, new_state)
        
        # Place stop loss orders for new positions
        if orders_placed:
            # Map tickers to stop loss values
            sl_mapping = {}
            for _, row in signals_df.iterrows():
                ticker = str(row.get("Ticker", "")).strip().upper()
                if ticker in orders_placed:
                    stop_loss = row.get("Stop_Loss")
                    if pd.notna(stop_loss):
                        sl_mapping[ticker] = round(float(stop_loss), 1)
            
            # Place stop loss orders for new positions
            for ticker, order_data in orders_placed.items():
                if ticker not in sl_mapping:
                    logger.warning(f"No Stop_Loss value found for {ticker}; skipping SL order.")
                    continue
                    
                if order_manager.check_existing_gtt_order(ticker):
                    logger.info(f"Existing SL order found for {ticker}; skipping SL placement.")
                    continue
                
                stop_loss = sl_mapping[ticker]
                logger.info(f"Placing GTT SL order for {ticker} with stop loss = {stop_loss}")
                
                # Force MIS product type for GTT orders
                original_product_type = order_manager.product_type
                order_manager.product_type = "MIS"
                
                # Place the GTT order
                order_manager.place_gtt_stoploss_order(ticker, order_data["quantity"], stop_loss, "LONG")
                
                # Restore original product type
                order_manager.product_type = original_product_type
        else:
            logger.info("No new orders placed; skipping stop loss orders.")
            
    except Exception as e:
        logger.exception(f"Error placing orders: {e}")

def main():
    # Parse command line arguments
    args = parse_args()
    
    # Initialize logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Log start of execution
    logger.info(f"===== Daily Order Placement Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    
    # Get configuration
    config = get_config()
    
    # Get order manager
    order_manager = get_order_manager()
    
    # Get max positions from args or default to 5
    max_positions = args.max_positions or 5
    
    # Get latest signal file if not specified
    data_handler = get_data_handler()
    signal_file = args.signal_file
    
    if not signal_file:
        logger.info("Signal file not specified, looking for latest BTPB_Signals_daily file...")
        data_dir = config.get('System', 'data_dir')
        
        # Find the latest BTPB_Signals_daily file
        files = [f for f in os.listdir(data_dir) if f.startswith('BTPB_Signals_daily_') and (f.endswith('.xlsx') or f.endswith('.txt'))]
        if files:
            # Sort by filename which includes timestamp
            latest_file = sorted(files)[-1]
            signal_file = os.path.join(data_dir, latest_file)
            logger.info(f"Found latest BTPB signal file: {signal_file}")
        else:
            logger.error("No BTPB_Signals_daily file found in data directory")
            return
    
    logger.info(f"Using signal file: {signal_file}")
    
    # Place orders
    try:
        logger.info("=== Processing BTPB signals for daily CNC orders ===")
        place_orders_from_btpb(order_manager, signal_file, max_positions)
    except Exception as e:
        logger.exception(f"Error during order placement: {e}")
    
    # Log end of execution
    logger.info(f"===== Daily Order Placement Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====\n")

if __name__ == "__main__":
    main()