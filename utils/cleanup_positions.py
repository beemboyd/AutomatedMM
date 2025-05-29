#!/usr/bin/env python
"""
cleanup_positions.py

This script synchronizes position data across multiple sources:
1. Zerodha API (actual positions)
2. Position data file (position_data.json)
3. Daily ticker tracker (daily_ticker_tracker.json)
4. Position state files (long_positions.txt and short_positions.txt)
5. GTT tracker (gttz_gtt_tracker.json)

It ensures all sources are consistent to prevent duplicate orders and phantom positions.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config
from data_handler import get_data_handler
from order_manager import get_order_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Synchronize position data across multiple sources")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Make changes without confirmation"
    )
    parser.add_argument(
        "--include-zerodha",
        action="store_true",
        help="Synchronize with Zerodha API data (requires active API connection)"
    )
    parser.add_argument(
        "--sync-mode",
        choices=["local", "zerodha-priority", "local-priority"],
        default="local",
        help="Synchronization mode: local (local files only), zerodha-priority (use Zerodha as source of truth), local-priority (prefer local files)"
    )
    parser.add_argument(
        "--ticker",
        help="Only process a specific ticker (e.g., 'AVANTIFEED')"
    )
    parser.add_argument(
        "--fix-inconsistencies",
        action="store_true",
        help="Automatically detect and fix inconsistencies in tracking files"
    )
    parser.add_argument(
        "--clean-all",
        action="store_true",
        help="Remove all positions that aren't in Zerodha (requires --include-zerodha)"
    )
    return parser.parse_args()

def load_position_data(data_dir):
    """Load position data from file"""
    position_file = os.path.join(data_dir, "position_data.json")
    if not os.path.exists(position_file):
        logger.error(f"Position data file not found: {position_file}")
        return {}
        
    try:
        with open(position_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.exception(f"Error loading position data: {e}")
        return {}

def load_daily_ticker_tracker(data_dir):
    """Load the daily ticker tracker data"""
    tracker_file = os.path.join(data_dir, "daily_ticker_tracker.json")
    if not os.path.exists(tracker_file):
        logger.error(f"Daily ticker tracker file not found: {tracker_file}")
        return None
        
    try:
        with open(tracker_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.exception(f"Error loading daily ticker tracker: {e}")
        return None

def load_gtt_tracker(data_dir):
    """Load the GTT tracker data"""
    gttz_file = os.path.join(data_dir, "gttz_gtt_tracker.json")
    if not os.path.exists(gttz_file):
        logger.info(f"GTT tracker file not found: {gttz_file}, initializing new tracker")
        return {"tickers": {}}
        
    try:
        with open(gttz_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.exception(f"Error loading GTT tracker: {e}")
        return {"tickers": {}}

def load_position_state_file(data_dir, position_type):
    """Load position state file (long_positions.txt or short_positions.txt)"""
    state_file = os.path.join(data_dir, f"{'long' if position_type == 'LONG' else 'short'}_positions.txt")
    position_state = {}
    
    if not os.path.exists(state_file):
        logger.warning(f"Position state file not found: {state_file}")
        return position_state
        
    try:
        with open(state_file, "r") as f:
            content = f.read().strip()
        if content:
            pairs = [p.strip() for p in content.split(",") if p.strip()]
            for pair in pairs:
                parts = pair.split(":")
                # Expected format: ticker:quantity:timestamp (ISO format)
                if len(parts) >= 2:
                    ticker = parts[0].strip().upper()
                    try:
                        quantity = int(parts[1].strip())
                    except:
                        logger.warning(f"Invalid quantity for {ticker} in state file: {parts[1]}")
                        continue
                    
                    # Get timestamp if available
                    if len(parts) >= 3:
                        try:
                            ts = datetime.fromisoformat(parts[2].strip())
                        except Exception as e:
                            logger.warning(f"Invalid timestamp for {ticker} in state file: {parts[2]}")
                            ts = datetime.now()
                    else:
                        ts = datetime.now()
                    
                    position_state[ticker] = {"quantity": quantity, "timestamp": ts}
        
        return position_state
    
    except Exception as e:
        logger.exception(f"Error loading position state file {state_file}: {e}")
        return {}

def save_position_data(data_dir, position_data, dry_run=False):
    """Save position data to file"""
    position_file = os.path.join(data_dir, "position_data.json")
    
    if dry_run:
        logger.info(f"DRY RUN: Would save updated position data to {position_file}")
        return True
        
    try:
        with open(position_file, 'w') as f:
            json.dump(position_data, f, indent=2)
        logger.info(f"Updated position data saved to {position_file}")
        return True
    except Exception as e:
        logger.exception(f"Error saving position data: {e}")
        return False

def save_daily_ticker_tracker(data_dir, tracker_data, dry_run=False):
    """Save daily ticker tracker data to file"""
    tracker_file = os.path.join(data_dir, "daily_ticker_tracker.json")
    
    if dry_run:
        logger.info(f"DRY RUN: Would save updated daily ticker tracker to {tracker_file}")
        return True
        
    try:
        with open(tracker_file, 'w') as f:
            json.dump(tracker_data, f, indent=4)
        logger.info(f"Updated daily ticker tracker saved with {len(tracker_data.get('long_tickers', []))} long tickers " + 
                    f"and {len(tracker_data.get('short_tickers', []))} short tickers")
        return True
    except Exception as e:
        logger.exception(f"Error saving daily ticker tracker: {e}")
        return False

def save_gtt_tracker(data_dir, gtt_data, dry_run=False):
    """Save GTT tracker data to file"""
    gttz_file = os.path.join(data_dir, "gttz_gtt_tracker.json")
    
    if dry_run:
        logger.info(f"DRY RUN: Would save updated GTT tracker to {gttz_file}")
        return True
        
    try:
        with open(gttz_file, 'w') as f:
            json.dump(gtt_data, f, indent=4)
        logger.info(f"Updated GTT tracker saved with {len(gtt_data.get('tickers', {}))} tickers")
        return True
    except Exception as e:
        logger.exception(f"Error saving GTT tracker: {e}")
        return False

def save_position_state_file(data_dir, position_state, position_type, dry_run=False):
    """Save position state file (long_positions.txt or short_positions.txt)"""
    state_file = os.path.join(data_dir, f"{'long' if position_type == 'LONG' else 'short'}_positions.txt")
    
    if dry_run:
        logger.info(f"DRY RUN: Would save updated position state to {state_file}")
        return True
    
    try:
        state_entries = [f"{ticker}:{position_state[ticker]['quantity']}:{position_state[ticker]['timestamp'].isoformat()}"
                         for ticker in position_state]
        
        with open(state_file, "w") as f:
            f.write(", ".join(state_entries))
            
        logger.info(f"Updated position state file {os.path.basename(state_file)} with {len(state_entries)} entries")
        return True
    except Exception as e:
        logger.exception(f"Error saving position state file {state_file}: {e}")
        return False

def get_zerodha_positions(order_manager):
    """Get current positions from Zerodha API"""
    try:
        # Get positions from Zerodha
        long_portfolio, short_portfolio = order_manager.get_portfolio_positions()
        logger.info(f"Retrieved {len(long_portfolio)} LONG and {len(short_portfolio)} SHORT positions from Zerodha")
        
        return long_portfolio, short_portfolio
    except Exception as e:
        logger.exception(f"Error getting positions from Zerodha: {e}")
        return {}, {}

def synchronize_data(data_dir, include_zerodha, sync_mode, ticker_filter=None, dry_run=False):
    """Synchronize position data across all sources"""
    changes = []
    
    # Load all local data sources
    position_data = load_position_data(data_dir)
    daily_tracker = load_daily_ticker_tracker(data_dir)
    gtt_tracker = load_gtt_tracker(data_dir)
    long_state = load_position_state_file(data_dir, "LONG")
    short_state = load_position_state_file(data_dir, "SHORT")
    
    # Initialize Zerodha data (empty by default)
    zerodha_long = {}
    zerodha_short = {}
    
    if include_zerodha:
        # Get order manager
        order_manager = get_order_manager()
        zerodha_long, zerodha_short = get_zerodha_positions(order_manager)

    # Create sets of tickers from different sources
    position_data_tickers = set(position_data.keys())
    daily_long_tickers = set(daily_tracker.get("long_tickers", []))
    daily_short_tickers = set(daily_tracker.get("short_tickers", []))
    long_state_tickers = set(long_state.keys())
    short_state_tickers = set(short_state.keys())
    gtt_tickers = set(gtt_tracker.get("tickers", {}).keys())
    zerodha_long_tickers = set(zerodha_long.keys())
    zerodha_short_tickers = set(zerodha_short.keys())
    
    # Determine source of truth based on sync mode
    if sync_mode == "zerodha-priority" and include_zerodha:
        # Use Zerodha as source of truth
        logger.info("Using Zerodha API as the source of truth")
        source_long_tickers = zerodha_long_tickers
        source_short_tickers = zerodha_short_tickers
    else:
        # Use local files as source of truth (position_data.json is primary, with state files as fallback)
        logger.info("Using local files as the source of truth")
        
        # Create sets of long and short tickers from position_data
        position_data_long = {ticker for ticker, info in position_data.items() if info.get("type") == "LONG"}
        position_data_short = {ticker for ticker, info in position_data.items() if info.get("type") == "SHORT"}
        
        # Determine source tickers (with state files as fallback)
        source_long_tickers = position_data_long if position_data_long else long_state_tickers
        source_short_tickers = position_data_short if position_data_short else short_state_tickers
    
    # Filter by ticker if specified
    if ticker_filter:
        ticker_filter = ticker_filter.upper()
        if ticker_filter in source_long_tickers:
            source_long_tickers = {ticker_filter}
            source_short_tickers = set()
        elif ticker_filter in source_short_tickers:
            source_long_tickers = set()
            source_short_tickers = {ticker_filter}
        else:
            logger.warning(f"Ticker {ticker_filter} not found in source positions")
            source_long_tickers = set()
            source_short_tickers = set()
    
    # Check for potentially inconsistent tickers (in both long and short sources)
    inconsistent_tickers = source_long_tickers.intersection(source_short_tickers)
    if inconsistent_tickers:
        logger.warning(f"Found {len(inconsistent_tickers)} tickers with inconsistent position types: {inconsistent_tickers}")
        
        if sync_mode == "zerodha-priority" and include_zerodha:
            # For Zerodha priority, resolve based on Zerodha data
            for ticker in inconsistent_tickers:
                if ticker in zerodha_long_tickers:
                    logger.info(f"Resolving conflict for {ticker}: Using LONG type from Zerodha")
                    source_short_tickers.discard(ticker)
                elif ticker in zerodha_short_tickers:
                    logger.info(f"Resolving conflict for {ticker}: Using SHORT type from Zerodha")
                    source_long_tickers.discard(ticker)
                else:
                    # If not in Zerodha, prefer position_data.json classification
                    if ticker in position_data and position_data[ticker].get("type") == "LONG":
                        logger.info(f"Resolving conflict for {ticker}: Using LONG type from position_data.json")
                        source_short_tickers.discard(ticker)
                    elif ticker in position_data and position_data[ticker].get("type") == "SHORT":
                        logger.info(f"Resolving conflict for {ticker}: Using SHORT type from position_data.json")
                        source_long_tickers.discard(ticker)
                    else:
                        # Default to removing from both if can't determine
                        logger.warning(f"Unable to determine correct position type for {ticker}, removing from both sources")
                        source_long_tickers.discard(ticker)
                        source_short_tickers.discard(ticker)
        else:
            # For local priority, prefer position_data.json classification
            for ticker in inconsistent_tickers:
                if ticker in position_data and position_data[ticker].get("type") == "LONG":
                    logger.info(f"Resolving conflict for {ticker}: Using LONG type from position_data.json")
                    source_short_tickers.discard(ticker)
                elif ticker in position_data and position_data[ticker].get("type") == "SHORT":
                    logger.info(f"Resolving conflict for {ticker}: Using SHORT type from position_data.json")
                    source_long_tickers.discard(ticker)
                else:
                    # Default to long if can't determine (arbitrary choice)
                    logger.warning(f"Unable to determine correct position type for {ticker}, defaulting to LONG")
                    source_short_tickers.discard(ticker)
    
    # Process LONG positions
    for ticker in source_long_tickers:
        # Check for conflicts (ticker in both LONG and SHORT sources)
        if ticker in source_short_tickers:
            changes.append(f"Conflict detected: {ticker} is in both LONG and SHORT sources")
            if sync_mode == "zerodha-priority" and include_zerodha:
                # Prefer Zerodha's classification
                if ticker in zerodha_long_tickers:
                    changes.append(f"Keeping {ticker} as LONG based on Zerodha data")
                    # Remove from SHORT sources
                    source_short_tickers.discard(ticker)
                elif ticker in zerodha_short_tickers:
                    changes.append(f"Keeping {ticker} as SHORT based on Zerodha data")
                    # Remove from LONG sources
                    source_long_tickers.discard(ticker)
                    continue
            else:
                # For local sync, keep in LONG and remove from SHORT
                changes.append(f"Keeping {ticker} as LONG based on local priority")
                source_short_tickers.discard(ticker)
        
        # Update position data
        if ticker not in position_data or position_data[ticker].get("type") != "LONG":
            changes.append(f"Adding/updating {ticker} as LONG in position_data.json")
            
            # Get best available data for the position
            if include_zerodha and ticker in zerodha_long:
                # Use Zerodha data
                entry_price = zerodha_long[ticker].get("purchase_price", 0)
                best_price = entry_price
            elif ticker in position_data:
                # Use existing data but update type
                entry_price = position_data[ticker].get("entry_price", 0)
                best_price = position_data[ticker].get("best_price", entry_price)
            else:
                # No existing data, use default values
                entry_price = 0
                best_price = 0
                
            position_data[ticker] = {
                "type": "LONG",
                "entry_price": entry_price,
                "best_price": best_price
            }
        
        # Update daily tracker
        if ticker not in daily_long_tickers:
            changes.append(f"Adding {ticker} to daily long tickers")
            daily_tracker.setdefault("long_tickers", []).append(ticker)
        
        # Ensure not in daily short tickers
        if ticker in daily_short_tickers:
            changes.append(f"Removing {ticker} from daily short tickers")
            daily_tracker["short_tickers"].remove(ticker)
        
        # Update long state file
        if ticker not in long_state:
            # Get quantity from best available source
            if include_zerodha and ticker in zerodha_long:
                quantity = zerodha_long[ticker].get("quantity", 1)
            else:
                quantity = 1  # Default
                
            changes.append(f"Adding {ticker} to long position state file with quantity {quantity}")
            long_state[ticker] = {
                "quantity": quantity,
                "timestamp": datetime.now()
            }
        
        # Remove from short state file if present
        if ticker in short_state:
            changes.append(f"Removing {ticker} from short position state file")
            del short_state[ticker]
        
        # Update GTT tracker if needed
        if ticker in gtt_tickers:
            current_gtt_type = gtt_tracker["tickers"].get(ticker, {}).get("position_type")
            if current_gtt_type and current_gtt_type != "LONG":
                changes.append(f"Updating GTT tracker position type for {ticker} from {current_gtt_type} to LONG")
                gtt_tracker["tickers"][ticker]["position_type"] = "LONG"
    
    # Process SHORT positions
    for ticker in source_short_tickers:
        # Update position data
        if ticker not in position_data or position_data[ticker].get("type") != "SHORT":
            changes.append(f"Adding/updating {ticker} as SHORT in position_data.json")
            
            # Get best available data for the position
            if include_zerodha and ticker in zerodha_short:
                # Use Zerodha data
                entry_price = zerodha_short[ticker].get("purchase_price", 0)
                best_price = entry_price
            elif ticker in position_data:
                # Use existing data but update type
                entry_price = position_data[ticker].get("entry_price", 0)
                best_price = position_data[ticker].get("best_price", entry_price)
            else:
                # No existing data, use default values
                entry_price = 0
                best_price = 0
                
            position_data[ticker] = {
                "type": "SHORT",
                "entry_price": entry_price,
                "best_price": best_price
            }
        
        # Update daily tracker
        if ticker not in daily_short_tickers:
            changes.append(f"Adding {ticker} to daily short tickers")
            daily_tracker.setdefault("short_tickers", []).append(ticker)
        
        # Ensure not in daily long tickers
        if ticker in daily_long_tickers:
            changes.append(f"Removing {ticker} from daily long tickers")
            daily_tracker["long_tickers"].remove(ticker)
        
        # Update short state file
        if ticker not in short_state:
            # Get quantity from best available source
            if include_zerodha and ticker in zerodha_short:
                quantity = zerodha_short[ticker].get("quantity", 1)
            else:
                quantity = 1  # Default
                
            changes.append(f"Adding {ticker} to short position state file with quantity {quantity}")
            short_state[ticker] = {
                "quantity": quantity,
                "timestamp": datetime.now()
            }
        
        # Remove from long state file if present
        if ticker in long_state:
            changes.append(f"Removing {ticker} from long position state file")
            del long_state[ticker]
        
        # Update GTT tracker if needed
        if ticker in gtt_tickers:
            current_gtt_type = gtt_tracker["tickers"].get(ticker, {}).get("position_type")
            if current_gtt_type and current_gtt_type != "SHORT":
                changes.append(f"Updating GTT tracker position type for {ticker} from {current_gtt_type} to SHORT")
                gtt_tracker["tickers"][ticker]["position_type"] = "SHORT"
    
    # Clean up position data (remove entries that aren't in source)
    all_source_tickers = source_long_tickers.union(source_short_tickers)
    for ticker in list(position_data.keys()):
        if ticker not in all_source_tickers:
            changes.append(f"Removing {ticker} from position_data.json (not in source positions)")
            del position_data[ticker]
    
    # Clean up daily tracker (remove entries that aren't in source)
    for ticker in list(daily_long_tickers):
        if ticker not in source_long_tickers:
            changes.append(f"Removing {ticker} from daily long tickers (not in source positions)")
            if ticker in daily_tracker.get("long_tickers", []):
                daily_tracker["long_tickers"].remove(ticker)
    
    for ticker in list(daily_short_tickers):
        if ticker not in source_short_tickers:
            changes.append(f"Removing {ticker} from daily short tickers (not in source positions)")
            if ticker in daily_tracker.get("short_tickers", []):
                daily_tracker["short_tickers"].remove(ticker)
    
    # Clean up long state file (remove entries that aren't in source)
    for ticker in list(long_state.keys()):
        if ticker not in source_long_tickers:
            changes.append(f"Removing {ticker} from long position state file (not in source positions)")
            del long_state[ticker]
    
    # Clean up short state file (remove entries that aren't in source)
    for ticker in list(short_state.keys()):
        if ticker not in source_short_tickers:
            changes.append(f"Removing {ticker} from short position state file (not in source positions)")
            del short_state[ticker]
    
    # Clean up GTT tracker (only update position types, don't remove entries)
    # GTT entries should be managed by the GTT cleanup utility
    
    # Save changes if not in dry run mode
    if not dry_run:
        save_position_data(data_dir, position_data, dry_run)
        save_daily_ticker_tracker(data_dir, daily_tracker, dry_run)
        save_position_state_file(data_dir, long_state, "LONG", dry_run)
        save_position_state_file(data_dir, short_state, "SHORT", dry_run)
        save_gtt_tracker(data_dir, gtt_tracker, dry_run)
    
    return changes

def main():
    # Parse command line arguments
    args = parse_args()
    
    logger.info("Starting position data synchronization utility")
    
    # Validate arguments
    if args.clean_all and not args.include_zerodha:
        logger.error("--clean-all requires --include-zerodha. Please specify both.")
        return 1
    
    # Get configuration
    config = get_config()
    data_dir = config.get('System', 'data_dir')
    
    # For fix-inconsistencies mode, force Zerodha as the source of truth
    if args.fix_inconsistencies and args.include_zerodha and args.sync_mode == "local":
        logger.info("Setting sync-mode to zerodha-priority for inconsistency fixing")
        sync_mode = "zerodha-priority"
    else:
        sync_mode = args.sync_mode
    
    # Process multiple tickers if specified via stdin
    if sys.stdin.isatty():
        # Normal mode: use single ticker from command line if specified
        ticker_filter = None if args.clean_all else args.ticker
        process_multiple_tickers = False
    else:
        # Input is being piped, read tickers from stdin
        stdin_content = sys.stdin.read().strip()
        if stdin_content:
            tickers = [t.strip().upper() for t in stdin_content.split(',') if t.strip()]
            if tickers:
                logger.info(f"Processing {len(tickers)} tickers from stdin: {', '.join(tickers)}")
                process_multiple_tickers = True
            else:
                ticker_filter = None
                process_multiple_tickers = False
        else:
            ticker_filter = None
            process_multiple_tickers = False
    
    # Process one ticker or all tickers
    if not process_multiple_tickers:
        # Synchronize data for a single ticker or all tickers
        changes = synchronize_data(
            data_dir,
            include_zerodha=args.include_zerodha,
            sync_mode=sync_mode,
            ticker_filter=ticker_filter,
            dry_run=args.dry_run
        )
        
        # Show changes
        if changes:
            logger.info(f"Found {len(changes)} changes to make:")
            for change in changes:
                logger.info(f"  - {change}")
        else:
            logger.info("No changes needed - all data sources are in sync.")
            return 0
        
        # Ask for confirmation if not forced
        if not args.force and not args.dry_run:
            confirm = input("\nDo you want to apply these changes? [y/N]: ")
            if confirm.lower() != 'y':
                logger.info("Operation cancelled by user.")
                return 0
    else:
        # Process multiple tickers from stdin
        all_changes = []
        for ticker in tickers:
            logger.info(f"Processing ticker: {ticker}")
            changes = synchronize_data(
                data_dir,
                include_zerodha=args.include_zerodha,
                sync_mode=sync_mode,
                ticker_filter=ticker,
                dry_run=args.dry_run
            )
            
            if changes:
                logger.info(f"Found {len(changes)} changes for {ticker}:")
                for change in changes:
                    logger.info(f"  - {change}")
                all_changes.extend(changes)
        
        # If no changes for any ticker, exit
        if not all_changes:
            logger.info("No changes needed for any ticker - all data sources are in sync.")
            return 0
        
        # Ask for confirmation if not forced
        if not args.force and not args.dry_run:
            confirm = input(f"\nDo you want to apply these {len(all_changes)} changes for all tickers? [y/N]: ")
            if confirm.lower() != 'y':
                logger.info("Operation cancelled by user.")
                return 0
        
        changes = all_changes
    
    logger.info(f"Position data synchronization {'simulation' if args.dry_run else 'execution'} completed.")
    logger.info(f"{'Simulated' if args.dry_run else 'Applied'} {len(changes)} changes.")
    
    # If this was a dry run, show how to run for real
    if args.dry_run:
        cmd = f"python {os.path.basename(__file__)}"
        if args.include_zerodha:
            cmd += " --include-zerodha"
        if args.sync_mode != "local":
            cmd += f" --sync-mode {args.sync_mode}"
        if args.fix_inconsistencies:
            cmd += " --fix-inconsistencies"
        if args.clean_all:
            cmd += " --clean-all"
        if args.ticker and not process_multiple_tickers:
            cmd += f" --ticker {args.ticker}"
        logger.info(f"To apply these changes, run: {cmd}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())