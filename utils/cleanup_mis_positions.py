#!/usr/bin/env python
"""
cleanup_mis_positions.py

This script provides tools to clean up MIS positions and reset state:
1. Reset all positions (both MIS and CNC)
2. Reset only MIS positions, keep CNC positions
3. Synchronize local positions with broker
4. Remove a specific ticker from state

Usage examples:
- python utils/cleanup_mis_positions.py --reset-mis      # Reset only MIS positions
- python utils/cleanup_mis_positions.py --sync-broker    # Sync with broker positions
- python utils/cleanup_mis_positions.py --reset-all      # Reset everything (use with caution)
- python utils/cleanup_mis_positions.py --remove-ticker GODREJPROP  # Remove specific ticker
"""

import os
import sys
import logging
import argparse
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config
from kiteconnect import KiteConnect
from state_manager import get_state_manager

def setup_logging():
    """Set up logging with console and file output"""
    config = get_config()
    log_dir = config.get('System', 'log_dir')
    log_level = config.get('System', 'log_level')
    
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'cleanup_mis_positions.log')
    
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
    parser = argparse.ArgumentParser(description="Clean up MIS positions and reset state")
    parser.add_argument(
        "--reset-all",
        action="store_true",
        help="Reset all positions and daily tickers"
    )
    parser.add_argument(
        "--reset-mis",
        action="store_true",
        help="Reset only MIS positions, keep CNC positions"
    )
    parser.add_argument(
        "--sync-broker",
        action="store_true",
        help="Synchronize with broker positions (removes positions not in broker)"
    )
    parser.add_argument(
        "--remove-ticker",
        type=str,
        help="Remove a specific ticker from state"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually modify any files, just report issues"
    )
    return parser.parse_args()

def fetch_zerodha_positions():
    """Fetch positions from Zerodha API"""
    config = get_config()
    api_key = config.get('API', 'api_key')
    access_token = config.get('API', 'access_token')
    
    try:
        # Initialize KiteConnect client
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        
        # Fetch positions
        positions_data = kite.positions()
        
        return positions_data
    except Exception as e:
        logging.error(f"Error fetching positions from Zerodha: {e}")
        return None

def reset_all_positions(dry_run=False):
    """Reset all positions and daily tickers"""
    logger = logging.getLogger()
    state_manager = get_state_manager()
    
    if dry_run:
        logger.info("DRY RUN: Would reset all positions and daily tickers")
        return True
    
    # Force reset the state manager
    reset_success = state_manager.reset_for_new_trading_day(force=True)
    
    # Additionally, completely clear positions to be safe
    state_manager.state["positions"] = {}
    state_manager.state["daily_tickers"] = {"long": [], "short": []}
    state_manager.state["meta"]["last_updated"] = datetime.now().isoformat()
    state_manager._save_state()
    
    logger.info("Successfully reset all positions and daily tickers")
    return reset_success

def reset_mis_positions(dry_run=False):
    """Reset only MIS positions, keep CNC positions"""
    logger = logging.getLogger()
    state_manager = get_state_manager()
    
    if dry_run:
        logger.info("DRY RUN: Would reset MIS positions")
        positions = state_manager.get_all_positions()
        mis_count = 0
        cnc_count = 0
        
        for ticker, data in positions.items():
            product_type = data.get("product_type", "").upper()
            if product_type == "CNC":
                cnc_count += 1
            else:
                mis_count += 1
        
        logger.info(f"Would remove {mis_count} MIS positions and keep {cnc_count} CNC positions")
        return True
    
    # Force reset the state manager which handles MIS position cleanup
    reset_success = state_manager.reset_for_new_trading_day(force=True)
    
    logger.info("Successfully reset MIS positions")
    return reset_success

def sync_with_broker(dry_run=False):
    """Synchronize local positions with broker"""
    logger = logging.getLogger()
    state_manager = get_state_manager()
    
    # Fetch broker positions
    zerodha_positions = fetch_zerodha_positions()
    if not zerodha_positions:
        logger.error("Failed to fetch positions from broker")
        return False
    
    config = get_config()
    exchange = config.get('Trading', 'exchange')
    
    # Process broker positions
    broker_positions = {}
    for pos in zerodha_positions.get("net", []):
        if pos.get("exchange") != exchange or pos.get("quantity") == 0:
            continue
        
        ticker = pos.get("tradingsymbol")
        quantity = pos.get("quantity")
        product = pos.get("product")
        
        if quantity > 0:
            position_type = "LONG"
        else:
            position_type = "SHORT"
            quantity = abs(quantity)
        
        broker_positions[ticker] = {
            "type": position_type,
            "quantity": quantity,
            "product_type": product,
            "entry_price": pos.get("average_price", 0)
        }
    
    if dry_run:
        logger.info(f"DRY RUN: Would sync {len(broker_positions)} positions from broker")
        # Compare with local state
        local_positions = state_manager.get_all_positions()
        to_add = set(broker_positions.keys()) - set(local_positions.keys())
        to_remove = set(local_positions.keys()) - set(broker_positions.keys())
        to_update = set(broker_positions.keys()) & set(local_positions.keys())
        
        logger.info(f"Would add {len(to_add)} positions: {', '.join(to_add) if to_add else 'none'}")
        logger.info(f"Would remove {len(to_remove)} positions: {', '.join(to_remove) if to_remove else 'none'}")
        logger.info(f"Would update {len(to_update)} positions: {', '.join(to_update) if to_update else 'none'}")
        return True
    
    # Get current positions
    current_positions = state_manager.get_all_positions()
    
    # Remove positions not in broker
    removed_positions = []
    for ticker in list(current_positions.keys()):
        if ticker not in broker_positions:
            state_manager.remove_position(ticker)
            removed_positions.append(ticker)
    
    # Add or update positions from broker
    added_positions = []
    updated_positions = []
    for ticker, data in broker_positions.items():
        if ticker not in current_positions:
            # Add new position
            state_manager.add_position(
                ticker=ticker,
                position_type=data["type"],
                quantity=data["quantity"],
                entry_price=data["entry_price"],
                product_type=data["product_type"],
                timestamp=datetime.now().isoformat()
            )
            added_positions.append(ticker)
        else:
            # Update existing position
            existing = current_positions[ticker]
            if existing.get("type") != data["type"] or existing.get("quantity") != data["quantity"]:
                # Type or quantity changed, update position
                state_manager.add_position(
                    ticker=ticker,
                    position_type=data["type"],
                    quantity=data["quantity"],
                    entry_price=data["entry_price"],
                    product_type=data["product_type"],
                    timestamp=datetime.now().isoformat()
                )
                updated_positions.append(ticker)
    
    # Log results
    if removed_positions:
        logger.info(f"Removed {len(removed_positions)} positions: {', '.join(removed_positions)}")
    if added_positions:
        logger.info(f"Added {len(added_positions)} positions: {', '.join(added_positions)}")
    if updated_positions:
        logger.info(f"Updated {len(updated_positions)} positions: {', '.join(updated_positions)}")
    
    logger.info(f"Successfully synchronized {len(broker_positions)} positions from broker")
    return True

def remove_specific_ticker(ticker, dry_run=False):
    """Remove a specific ticker from state"""
    logger = logging.getLogger()
    state_manager = get_state_manager()
    
    ticker = ticker.upper()
    
    # Check if ticker exists in positions
    position = state_manager.get_position(ticker)
    if not position:
        logger.warning(f"Ticker {ticker} not found in positions")
        return False
    
    if dry_run:
        logger.info(f"DRY RUN: Would remove {ticker} position ({position.get('type', '?')}, qty: {position.get('quantity', '?')})")
        return True
    
    # Remove position
    removed = state_manager.remove_position(ticker)
    
    # Also remove from daily tickers if present
    if state_manager.is_long_ticker(ticker):
        state_manager.remove_daily_ticker(ticker, "long")
    if state_manager.is_short_ticker(ticker):
        state_manager.remove_daily_ticker(ticker, "short")
    
    logger.info(f"Successfully removed {ticker} from all state")
    return removed

def main():
    # Parse command line arguments
    args = parse_args()
    
    # Initialize logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Log start of execution
    logger.info(f"===== Position Cleanup Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    
    # Get state manager
    state_manager = get_state_manager()
    
    # Process based on arguments
    if args.reset_all:
        reset_all_positions(dry_run=args.dry_run)
    elif args.reset_mis:
        reset_mis_positions(dry_run=args.dry_run)
    elif args.sync_broker:
        sync_with_broker(dry_run=args.dry_run)
    elif args.remove_ticker:
        remove_specific_ticker(args.remove_ticker, dry_run=args.dry_run)
    else:
        # Show current state if no action specified
        positions = state_manager.get_all_positions()
        long_positions = {k: v for k, v in positions.items() if v.get("type") == "LONG"}
        short_positions = {k: v for k, v in positions.items() if v.get("type") == "SHORT"}
        
        logger.info(f"Current state: {len(positions)} positions ({len(long_positions)} long, {len(short_positions)} short)")
        logger.info(f"Long positions: {', '.join(long_positions.keys()) if long_positions else 'none'}")
        logger.info(f"Short positions: {', '.join(short_positions.keys()) if short_positions else 'none'}")
        logger.info("Use one of the action flags to modify state (--reset-all, --reset-mis, --sync-broker, --remove-ticker)")
    
    logger.info(f"===== Position Cleanup Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")

if __name__ == "__main__":
    main()