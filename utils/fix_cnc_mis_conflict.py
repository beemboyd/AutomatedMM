#!/usr/bin/env python
"""
fix_cnc_mis_conflict.py

This utility identifies and fixes conflicts between CNC and MIS positions.
It specifically addresses the issue where CNC transactions (delivery) are incorrectly
tracked as MIS (intraday) positions.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
import time

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config
from risk_management import get_risk_manager
from order_manager import get_order_manager

# Configure logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'fix_cnc_mis_conflict.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Fix conflicts between CNC and MIS positions")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without making changes"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Make changes without confirmation"
    )
    return parser.parse_args()

def get_all_positions(kite):
    """Get all positions (both CNC and MIS) from Zerodha"""
    try:
        positions_data = kite.positions()
        
        # Get day positions (usually CNC)
        day_positions = positions_data.get("day", [])
        # Get net positions
        net_positions = positions_data.get("net", [])
        
        # Extract CNC positions
        cnc_positions = []
        for pos in day_positions + net_positions:
            if pos.get("product") == "CNC":
                cnc_positions.append(pos)
        
        # Extract MIS positions
        mis_positions = []
        for pos in day_positions + net_positions:
            if pos.get("product") == "MIS":
                mis_positions.append(pos)
        
        logger.info(f"Found {len(cnc_positions)} CNC positions and {len(mis_positions)} MIS positions")
        return cnc_positions, mis_positions
    
    except Exception as e:
        logger.exception(f"Error fetching positions: {e}")
        return [], []

def identify_conflicts(cnc_positions, mis_positions, daily_tracker, target_tickers=None):
    """Identify conflicts between CNC and MIS positions
    
    Args:
        cnc_positions: List of CNC positions from Zerodha
        mis_positions: List of MIS positions from Zerodha
        daily_tracker: Daily ticker tracker data
        target_tickers: Optional list of specific tickers to check (case insensitive)
    
    Returns:
        List of conflict dictionaries
    """
    conflicts = []
    
    # Extract ticker symbols
    cnc_tickers = set(pos.get("tradingsymbol", "").upper() for pos in cnc_positions)
    mis_tickers = set(pos.get("tradingsymbol", "").upper() for pos in mis_positions)
    
    # Get tickers from daily tracker
    long_tickers = set(daily_tracker.get("long_tickers", []))
    short_tickers = set(daily_tracker.get("short_tickers", []))
    tracked_tickers = long_tickers.union(short_tickers)
    
    # Filter for target tickers if specified
    if target_tickers:
        target_tickers = set(t.upper() for t in target_tickers)
        cnc_tickers = cnc_tickers.intersection(target_tickers)
        tracked_tickers = tracked_tickers.intersection(target_tickers)
    
    # Check for CNC tickers that are also being tracked as MIS in our system
    for ticker in cnc_tickers:
        if ticker in tracked_tickers:
            # This is a conflict
            is_long = ticker in long_tickers
            is_short = ticker in short_tickers
            
            # Find the CNC position details
            cnc_details = next((pos for pos in cnc_positions if pos.get("tradingsymbol", "").upper() == ticker), {})
            qty = cnc_details.get("quantity", 0)
            pos_type = "LONG" if qty > 0 else "SHORT"
            
            # Add to conflicts list
            conflicts.append({
                "ticker": ticker,
                "cnc_position_type": pos_type,
                "tracked_as": "LONG" if is_long else ("SHORT" if is_short else "UNKNOWN"),
                "quantity": abs(qty),
                "needs_removal": True
            })
    
    return conflicts

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

def update_daily_tracker(data_dir, conflicts, dry_run=False):
    """Update daily ticker tracker to remove conflicting tickers"""
    tracker_file = os.path.join(data_dir, "daily_ticker_tracker.json")
    
    try:
        with open(tracker_file, 'r') as f:
            daily_tracker = json.load(f)
        
        long_tickers = daily_tracker.get("long_tickers", [])
        short_tickers = daily_tracker.get("short_tickers", [])
        changes_made = False
        
        for conflict in conflicts:
            ticker = conflict["ticker"]
            if ticker in long_tickers:
                if not dry_run:
                    long_tickers.remove(ticker)
                logger.info(f"Removing {ticker} from long_tickers in daily tracker")
                changes_made = True
            if ticker in short_tickers:
                if not dry_run:
                    short_tickers.remove(ticker)
                logger.info(f"Removing {ticker} from short_tickers in daily tracker")
                changes_made = True
        
        if changes_made and not dry_run:
            daily_tracker["long_tickers"] = long_tickers
            daily_tracker["short_tickers"] = short_tickers
            with open(tracker_file, 'w') as f:
                json.dump(daily_tracker, f, indent=4)
            logger.info(f"Updated daily ticker tracker")
        elif changes_made:
            logger.info("DRY RUN: Would update daily ticker tracker")
        else:
            logger.info("No changes needed for daily ticker tracker")
        
        return changes_made
            
    except Exception as e:
        logger.exception(f"Error updating daily ticker tracker: {e}")
        return False

def cleanup_position_data(data_dir, conflicts, dry_run=False):
    """Remove conflicting tickers from position_data.json"""
    position_file = os.path.join(data_dir, "position_data.json")
    
    if not os.path.exists(position_file):
        logger.error(f"Position data file not found: {position_file}")
        return False
    
    try:
        # Load position data
        with open(position_file, 'r') as f:
            position_data = json.load(f)
        
        # Track which tickers were removed
        removed = []
        
        # Remove conflicting tickers
        for conflict in conflicts:
            ticker = conflict["ticker"]
            if ticker in position_data:
                removed.append(ticker)
                if not dry_run:
                    del position_data[ticker]
                logger.info(f"Removing {ticker} from position_data.json")
        
        # Save updated data if changes were made
        if removed and not dry_run:
            with open(position_file, 'w') as f:
                json.dump(position_data, f, indent=2)
            logger.info(f"Updated position_data.json by removing {len(removed)} tickers")
            return True
        elif removed:
            logger.info(f"DRY RUN: Would remove {len(removed)} tickers from position_data.json")
            return True
        else:
            logger.info("No changes needed for position_data.json")
            return False
    
    except Exception as e:
        logger.exception(f"Error cleaning up position data: {e}")
        return False

def clean_gtt_orders(risk_manager, conflicts, dry_run=False):
    """Remove GTT orders for conflicting tickers"""
    if not conflicts:
        logger.info("No conflicts to check for GTT orders")
        return False
    
    # Get conflict tickers
    conflict_tickers = [conflict["ticker"] for conflict in conflicts]
    
    # Load GTT tracker
    gtt_tracker = risk_manager.load_gtt_tracker()
    tickers = gtt_tracker.get("tickers", {})
    
    # Find conflicting GTTs
    gtt_conflicts = []
    for ticker, data in tickers.items():
        if ticker in conflict_tickers:
            gtt_conflicts.append({
                "ticker": ticker,
                "trigger_id": data.get("trigger_id"),
                "position_type": data.get("position_type")
            })
    
    if not gtt_conflicts:
        logger.info("No GTT orders found for conflicting tickers")
        return False
    
    logger.info(f"Found {len(gtt_conflicts)} GTT orders for conflicting tickers")
    
    # Delete GTT orders if not in dry run mode
    if dry_run:
        logger.info("DRY RUN: Would delete the following GTT orders:")
        for gtt in gtt_conflicts:
            logger.info(f"  - {gtt['ticker']} ({gtt['position_type']}): ID {gtt['trigger_id']}")
        return True
    
    # Delete GTT orders
    deleted_count = 0
    for gtt in gtt_conflicts:
        logger.info(f"Deleting GTT order for {gtt['ticker']} (ID: {gtt['trigger_id']})...")
        try:
            if risk_manager.delete_gtt_order(gtt['trigger_id'], gtt['ticker']):
                deleted_count += 1
                # Remove from tracker
                if gtt['ticker'] in tickers:
                    del tickers[gtt['ticker']]
            time.sleep(0.5)  # Avoid rate limiting
        except Exception as e:
            logger.error(f"Error deleting GTT for {gtt['ticker']}: {e}")
    
    # Save updated tracker
    if deleted_count > 0:
        risk_manager.save_gtt_tracker(gtt_tracker)
        logger.info(f"Updated GTT tracker after deleting {deleted_count} orders")
        return True
    
    return False

def main():
    # Parse command line arguments
    args = parse_args()
    
    logger.info("Starting CNC-MIS conflict resolution")
    
    # Get configuration
    config = get_config()
    data_dir = config.get('System', 'data_dir')
    
    # Make sure we're in MIS mode
    product_type = config.get('Trading', 'product_type')
    if product_type != "MIS":
        logger.error(f"This script can only operate when product_type is set to MIS, but found {product_type}")
        return 1
    
    # Get risk manager and order manager
    risk_manager = get_risk_manager()
    order_manager = get_order_manager()
    
    # Check for specific tickers from stdin
    target_tickers = None
    if not sys.stdin.isatty():
        stdin_content = sys.stdin.read().strip()
        if stdin_content:
            target_tickers = [t.strip() for t in stdin_content.split(',') if t.strip()]
            if target_tickers:
                logger.info(f"Processing specific tickers from stdin: {', '.join(target_tickers)}")
    
    # Get all positions from Zerodha
    cnc_positions, mis_positions = get_all_positions(order_manager.kite)
    
    # Load daily ticker tracker
    daily_tracker = load_daily_ticker_tracker(data_dir)
    if not daily_tracker:
        logger.error("Failed to load daily ticker tracker. Exiting.")
        return 1
    
    # Identify conflicts
    conflicts = identify_conflicts(cnc_positions, mis_positions, daily_tracker, target_tickers)
    
    if not conflicts:
        if target_tickers:
            logger.info(f"No CNC-MIS conflicts found for the specified tickers: {', '.join(target_tickers)}")
        else:
            logger.info("No CNC-MIS conflicts found. All good!")
        return 0
    
    logger.info(f"Found {len(conflicts)} CNC-MIS conflicts:")
    for conflict in conflicts:
        logger.info(f"  - {conflict['ticker']}: CNC {conflict['cnc_position_type']} position but tracked as MIS {conflict['tracked_as']}")
    
    # Check if dry run
    if args.dry_run:
        logger.info("DRY RUN: Would fix the conflicts by:")
        logger.info("  1. Removing conflicting tickers from daily_ticker_tracker.json")
        logger.info("  2. Removing conflicting tickers from position_data.json")
        logger.info("  3. Deleting GTT orders for conflicting tickers")
        
        # Simulate the fixes in dry run mode
        update_daily_tracker(data_dir, conflicts, dry_run=True)
        cleanup_position_data(data_dir, conflicts, dry_run=True)
        clean_gtt_orders(risk_manager, conflicts, dry_run=True)
        
        return 0
    
    # Ask for confirmation unless forced
    if not args.force:
        conflict_list = ", ".join([c['ticker'] for c in conflicts])
        confirm = input(f"Fix {len(conflicts)} CNC-MIS conflicts for tickers: {conflict_list}? (yes/no): ")
        if confirm.lower() != "yes":
            logger.info("Operation cancelled by user")
            return 0
    
    # Fix the conflicts
    changes1 = update_daily_tracker(data_dir, conflicts)
    changes2 = cleanup_position_data(data_dir, conflicts)
    changes3 = clean_gtt_orders(risk_manager, conflicts)
    
    if changes1 or changes2 or changes3:
        logger.info("Successfully fixed CNC-MIS conflicts")
    else:
        logger.info("No changes were needed")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())