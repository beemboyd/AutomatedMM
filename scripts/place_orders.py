#!/usr/bin/env python
"""
Place Orders Script

This script is responsible for placing new orders based on signal files.
It ONLY places new orders when new trading signals are found in signal files.
It does NOT close positions when tickers drop out of signal files.

Position closing is handled exclusively by:
1. position_watchdog.py when stop loss conditions are met
2. End-of-day closure from Zerodha for MIS positions

Features:
- Respects ticker cooldown period (ticker_cooldown_hours in config.ini) to prevent
  placing multiple orders for the same ticker within the specified timeframe
- Default cooldown is 2 hours if not specified in config

Updated: 2025-05-07
"""

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
from state_manager import get_state_manager
from trading_logic import get_trading_logic

# Set up logging
def setup_logging():
    config = get_config()
    log_dir = config.get('System', 'log_dir')
    log_level = config.get('System', 'log_level')
    
    os.makedirs(log_dir, exist_ok=True)
    
    # Create place_orders.log in the log directory
    log_file = os.path.join(log_dir, 'place_orders.log')
    
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
    parser = argparse.ArgumentParser(description="Place orders based on trading signals")
    parser.add_argument(
        "-l", "--long-file", 
        help="Path to long signal Excel file"
    )
    parser.add_argument(
        "-s", "--short-file", 
        help="Path to short signal Excel file"
    )
    parser.add_argument(
        "-m", "--max-positions", 
        type=int,
        help="Maximum number of positions to take"
    )
    parser.add_argument(
        "--respect-market-breadth",
        action="store_true",
        help="Override config and respect market breadth analysis"
    )
    parser.add_argument(
        "--ignore-market-breadth",
        action="store_true",
        help="Override config and ignore market breadth analysis"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--disable-long", 
        action="store_true", 
        help="Disable long orders"
    )
    parser.add_argument(
        "--disable-short", 
        action="store_true", 
        help="Disable short orders"
    )
    return parser.parse_args()

def place_long_orders(order_manager, long_file, max_positions, args=None):
    """Place new long orders based on signal file
    
    Important: This function ONLY opens new positions based on signal files.
    It does NOT close positions when tickers drop out of scan results.
    Position closing is handled by:
    1. position_watchdog.py based on stop loss conditions
    2. End-of-day closure from Zerodha for MIS positions
    """
    logger = logging.getLogger()
    
    # Load the long signal file
    if not os.path.exists(long_file):
        logger.error(f"Long signal file {long_file} not found")
        return
    
    try:
        long_df = pd.read_excel(long_file, sheet_name="Hourly_Summary", engine="openpyxl")
        if long_df.empty:
            logger.info("No long opportunities found in signal file")
            return
        
        # Get advancing/declining information from Summary sheet
        summary_df = pd.read_excel(long_file, sheet_name="Summary", engine="openpyxl")
        advances = summary_df[summary_df['Metric'] == 'Advances']['Value'].iloc[0] if not summary_df.empty else 0
        declines = summary_df[summary_df['Metric'] == 'Declines']['Value'].iloc[0] if not summary_df.empty else 0
        
        logger.info(f"Market breadth - Advances: {advances}, Declines: {declines}")
        
        # Get only the top N long opportunities
        trading_logic = get_trading_logic()
        config = get_config()
        
        # Check if we should ignore market breadth analysis
        # Command line args override config
        ignore_market_breadth = False
        respect_market_breadth = False
        
        # Check command line arguments
        if hasattr(args, 'ignore_market_breadth') and args.ignore_market_breadth:
            ignore_market_breadth = True
            respect_market_breadth = False
            logger.info("Command line flag --ignore-market-breadth set")
        elif hasattr(args, 'respect_market_breadth') and args.respect_market_breadth:
            respect_market_breadth = True
            ignore_market_breadth = False
            logger.info("Command line flag --respect-market-breadth set")
        else:
            # Use config value if no command line override
            ignore_market_breadth = config.get_bool('Trading', 'ignore_market_breadth', fallback=False)
            respect_market_breadth = not ignore_market_breadth
            # Force respect market breadth since config has it disabled
            if not ignore_market_breadth:
                respect_market_breadth = True
            logger.info(f"Using config setting for market breadth analysis: ignore_market_breadth={ignore_market_breadth}")
        
        # Calculate market breadth first to log the ratio
        ratio, disable_long, disable_short = trading_logic.analyze_market_breadth(advances, declines)
        logger.info(f"Market breadth - Advances/Declines Ratio: {ratio:.2f}, Disable Longs: {disable_long}, Disable Shorts: {disable_short}")
        logger.info(f"Raw values - Advances: {advances}, Declines: {declines}")
        
        if ignore_market_breadth:
            disable_long_trades = False
            logger.info("*** MARKET BREADTH ANALYSIS OVERRIDDEN - LONG TRADES ALLOWED ***")
        elif respect_market_breadth:
            disable_long_trades = disable_long
            logger.info("Using market breadth analysis to determine if long trades are allowed")
        else:
            disable_long_trades = disable_long
        
        if disable_long_trades:
            logger.info("Long trades disabled based on market breadth analysis")
            logger.info("Exiting long trade processing - NO LONG TRADES WILL BE PLACED")
            return
            
        logger.info("Long trades are ENABLED - continuing with order placement")
        
        # Take only the top N opportunities
        long_order_df = long_df.head(max_positions)
        logger.info(f"Selected top {max_positions} long opportunities for trading")
        
        # Build order info dictionary
        long_order_info = {}
        for idx, row in long_order_df.iterrows():
            ticker = str(row.get("Ticker", "")).strip()
            if not ticker:
                continue
            pos_size = row.get("PosSize", None)
            if pd.isna(pos_size):
                continue
            quantity = max(1, int(round(pos_size)))
            long_order_info[ticker.upper()] = {"quantity": quantity}
        
        logger.info(f"Long order entries: {list(long_order_info.keys())}")
        
        # Get long positions from state manager
        state_manager = get_state_manager()
        positions = state_manager.get_positions_by_type("LONG")
        
        # Convert to expected format
        long_previous_state = {}
        for ticker, data in positions.items():
            long_previous_state[ticker] = {
                "quantity": data.get("quantity", 0),
                "timestamp": datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat()))
            }
        logger.info(f"Previous long positions: {list(long_previous_state.keys())}")
        
        # Fetch current portfolio long positions and pending orders
        long_portfolio, _ = order_manager.get_portfolio_positions()
        pending_orders = order_manager.get_pending_orders()
        
        # We no longer close positions when tickers drop out of scan results
        # This is now handled by position_watchdog or EOD closure from Zerodha
        now = datetime.now()
        all_long_tickers = long_df['Ticker'].dropna().astype(str).apply(lambda x: x.upper()).tolist()
        
        # Empty dictionary - no positions to close based on scan results
        tickers_to_sell = {}
        
        # Determine new positions to open
        tickers_to_buy = {}
        for ticker, info in long_order_info.items():
            if ticker in long_previous_state:
                last_time = long_previous_state[ticker]["timestamp"]
                cooldown_hours = config.get_float('Trading', 'ticker_cooldown_hours', fallback=2.0)
                cooldown_seconds = cooldown_hours * 3600
                if (now - last_time).total_seconds() < cooldown_seconds:  # Configurable cooldown period
                    logger.info(f"Buy order for {ticker} skipped as last order was placed less than {cooldown_hours} hours ago at {last_time}.")
                    continue
            if ticker not in long_portfolio and ticker not in pending_orders:
                tickers_to_buy[ticker] = info
        
        logger.info(f"NOT closing any long positions - this is now handled by position_watchdog or EOD closure")
        logger.info(f"New long positions to open: {tickers_to_buy}")
        
        # We no longer close positions based on scan results
        # This comment replaces the code that used to close positions
        
        # Place buy orders to open new positions
        long_orders_placed = {}
        for ticker, info in tickers_to_buy.items():
            qty = info["quantity"]
            success = order_manager.place_order(ticker, "BUY", "MARKET", qty)
            if success:
                long_orders_placed[ticker] = {"quantity": qty, "timestamp": datetime.now()}
        
        # Update long position state
        new_long_state = {}
        for ticker, info in long_order_info.items():
            ticker_upper = ticker.upper()
            if ticker_upper in long_orders_placed:
                new_long_state[ticker_upper] = long_orders_placed[ticker_upper]
            elif ticker_upper in long_previous_state:
                new_long_state[ticker_upper] = long_previous_state[ticker_upper]
        
        order_manager.save_position_state(order_manager.long_state_file, new_long_state)
        
        # No longer placing GTT orders here - stop loss handled by position_watchdog
        if long_orders_placed:
            logger.info(f"Placed {len(long_orders_placed)} new long orders. Stop losses will be managed by position_watchdog.")
        else:
            logger.info("No new long orders placed.")
            
    except Exception as e:
        logger.exception(f"Error placing long orders: {e}")

def place_short_orders(order_manager, short_file, max_positions, args=None):
    """Place new short orders based on signal file
    
    Important: This function ONLY opens new positions based on signal files.
    It does NOT close positions when tickers drop out of scan results.
    Position closing is handled by:
    1. position_watchdog.py based on stop loss conditions
    2. End-of-day closure from Zerodha for MIS positions
    """
    logger = logging.getLogger()
    
    # Load the short signal file
    if not os.path.exists(short_file):
        logger.error(f"Short signal file {short_file} not found")
        return
    
    try:
        short_df = pd.read_excel(short_file, sheet_name="Hourly_Summary", engine="openpyxl")
        if short_df.empty:
            logger.info("No short opportunities found in signal file")
            return
        
        # Get advancing/declining information from Summary sheet
        summary_df = pd.read_excel(short_file, sheet_name="Summary", engine="openpyxl")
        advances = summary_df[summary_df['Metric'] == 'Advances']['Value'].iloc[0] if not summary_df.empty else 0
        declines = summary_df[summary_df['Metric'] == 'Declines']['Value'].iloc[0] if not summary_df.empty else 0
        
        logger.info(f"Market breadth - Advances: {advances}, Declines: {declines}")
        
        # Get only the top N short opportunities
        trading_logic = get_trading_logic()
        config = get_config()
        
        # Check if we should ignore market breadth analysis
        # Command line args override config
        ignore_market_breadth = False
        respect_market_breadth = False
        
        # Check command line arguments
        if hasattr(args, 'ignore_market_breadth') and args.ignore_market_breadth:
            ignore_market_breadth = True
            respect_market_breadth = False
            logger.info("Command line flag --ignore-market-breadth set")
        elif hasattr(args, 'respect_market_breadth') and args.respect_market_breadth:
            respect_market_breadth = True
            ignore_market_breadth = False
            logger.info("Command line flag --respect-market-breadth set")
        else:
            # Use config value if no command line override
            ignore_market_breadth = config.get_bool('Trading', 'ignore_market_breadth', fallback=False)
            respect_market_breadth = not ignore_market_breadth
            # Force respect market breadth since config has it disabled
            if not ignore_market_breadth:
                respect_market_breadth = True
            logger.info(f"Using config setting for market breadth analysis: ignore_market_breadth={ignore_market_breadth}")
        
        # Calculate market breadth - use same function as long orders
        ratio, disable_long, disable_short = trading_logic.analyze_market_breadth(advances, declines)
        logger.info(f"Market breadth - Advances/Declines Ratio: {ratio:.2f}, Disable Longs: {disable_long}, Disable Shorts: {disable_short}")
        logger.info(f"Raw values - Advances: {advances}, Declines: {declines}")
        
        if ignore_market_breadth:
            disable_short_trades = False
            logger.info("*** MARKET BREADTH ANALYSIS OVERRIDDEN - SHORT TRADES ALLOWED ***")
        elif respect_market_breadth:
            disable_short_trades = disable_short
            logger.info("Using market breadth analysis to determine if short trades are allowed")
        else:
            disable_short_trades = disable_short
        
        if disable_short_trades:
            logger.info("Short trades disabled based on market breadth analysis")
            logger.info("Exiting short trade processing - NO SHORT TRADES WILL BE PLACED")
            return
            
        logger.info("Short trades are ENABLED - continuing with order placement")
        
        # Take only the top N opportunities
        short_order_df = short_df.head(max_positions)
        logger.info(f"Selected top {max_positions} short opportunities for trading")
        
        # Build order info dictionary
        short_order_info = {}
        for idx, row in short_order_df.iterrows():
            ticker = str(row.get("Ticker", "")).strip()
            if not ticker:
                continue
            pos_size = row.get("PosSize", None)
            if pd.isna(pos_size):
                continue
            quantity = max(1, int(round(pos_size)))
            short_order_info[ticker.upper()] = {"quantity": quantity}
        
        logger.info(f"Short order entries: {list(short_order_info.keys())}")
        
        # Get short positions from state manager
        state_manager = get_state_manager()
        positions = state_manager.get_positions_by_type("SHORT")
        
        # Convert to expected format
        short_previous_state = {}
        for ticker, data in positions.items():
            short_previous_state[ticker] = {
                "quantity": data.get("quantity", 0),
                "timestamp": datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat()))
            }
        logger.info(f"Previous short positions: {list(short_previous_state.keys())}")
        
        # Fetch current portfolio short positions and pending orders
        _, short_portfolio = order_manager.get_portfolio_positions()
        pending_orders = order_manager.get_pending_orders()
        
        # We no longer close positions when tickers drop out of scan results
        # This is now handled by position_watchdog or EOD closure from Zerodha
        now = datetime.now()
        all_short_tickers = short_df['Ticker'].dropna().astype(str).apply(lambda x: x.upper()).tolist()
        
        # Empty dictionary - no positions to close based on scan results
        tickers_to_cover = {}
        
        # Determine new positions to open
        tickers_to_short = {}
        for ticker, info in short_order_info.items():
            if ticker in short_previous_state:
                last_time = short_previous_state[ticker]["timestamp"]
                cooldown_hours = config.get_float('Trading', 'ticker_cooldown_hours', fallback=2.0)
                cooldown_seconds = cooldown_hours * 3600
                if (now - last_time).total_seconds() < cooldown_seconds:  # Configurable cooldown period
                    logger.info(f"Short order for {ticker} skipped as last order was placed less than {cooldown_hours} hours ago at {last_time}.")
                    continue
            if ticker not in short_portfolio and ticker not in pending_orders:
                tickers_to_short[ticker] = info
        
        logger.info(f"NOT covering any short positions - this is now handled by position_watchdog or EOD closure")
        logger.info(f"New short positions to open: {tickers_to_short}")
        
        # We no longer close positions based on scan results
        # This comment replaces the code that used to close positions
        
        # Place sell orders to open new short positions
        short_orders_placed = {}
        for ticker, info in tickers_to_short.items():
            qty = info["quantity"]
            success = order_manager.place_order(ticker, "SELL", "MARKET", qty)
            if success:
                short_orders_placed[ticker] = {"quantity": qty, "timestamp": datetime.now()}
        
        # Update short position state
        new_short_state = {}
        for ticker, info in short_order_info.items():
            ticker_upper = ticker.upper()
            if ticker_upper in short_orders_placed:
                new_short_state[ticker_upper] = short_orders_placed[ticker_upper]
            elif ticker_upper in short_previous_state:
                new_short_state[ticker_upper] = short_previous_state[ticker_upper]
        
        order_manager.save_position_state(order_manager.short_state_file, new_short_state)
        
        # No longer placing GTT orders here - stop loss handled by position_watchdog
        if short_orders_placed:
            logger.info(f"Placed {len(short_orders_placed)} new short orders. Stop losses will be managed by position_watchdog.")
        else:
            logger.info("No new short orders placed.")
            
    except Exception as e:
        logger.exception(f"Error placing short orders: {e}")

def main():
    # Parse command line arguments
    args = parse_args()
    
    # Initialize logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Log start of execution
    logger.info(f"===== Order Placement Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    
    # Get configuration
    config = get_config()
    
    # Verify that we're only operating on MIS product type
    product_type = config.get('Trading', 'product_type')
    if product_type != "MIS":
        logger.error(f"This script can only operate on MIS product type, but found {product_type}")
        logger.error("For CNC (delivery) orders, use the scripts in the Daily folder")
        return
    
    # We already imported pandas at the top
    
    # Get order manager
    order_manager = get_order_manager()
    
    # Get max positions from args or config
    max_positions = args.max_positions or config.get_int('Trading', 'max_positions', fallback=3)
    
    # Get latest signal files if not specified
    data_handler = get_data_handler()
    long_file = args.long_file
    short_file = args.short_file
    
    if not (long_file and short_file):
        logger.info("Signal files not specified, looking for latest files...")
        latest_long, latest_short = data_handler.get_latest_signal_files()
        long_file = long_file or latest_long
        short_file = short_file or latest_short
    
    logger.info(f"Using signal files:")
    logger.info(f"  Long: {long_file}")
    logger.info(f"  Short: {short_file}")
    
    # Place orders
    try:
        if not args.disable_long and long_file:
            logger.info("=== Processing LONG positions ===")
            place_long_orders(order_manager, long_file, max_positions, args)
        else:
            logger.info("Long orders disabled")
        
        if not args.disable_short and short_file:
            logger.info("=== Processing SHORT positions ===")
            place_short_orders(order_manager, short_file, max_positions, args)
        else:
            logger.info("Short orders disabled")
            
    except Exception as e:
        logger.exception(f"Error during order placement: {e}")
    
    # Log end of execution
    logger.info(f"===== Order Placement Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====\n")

if __name__ == "__main__":
    main()