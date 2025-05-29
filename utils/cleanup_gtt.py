#!/usr/bin/env python
"""
cleanup_gtt.py

This script reconciles and cleans up inconsistent GTT orders by:
1. Checking all GTT orders against the daily ticker tracker
2. Deleting any GTT orders that have position type conflicts
3. Updating the position_data.json file to be consistent
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
from risk_management import get_risk_manager
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
    parser = argparse.ArgumentParser(description="Clean up and reconcile GTT orders")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--force-delete",
        action="store_true",
        help="Delete conflicting GTT orders without confirmation"
    )
    return parser.parse_args()

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

def save_position_data(data_dir, position_data):
    """Save position data to file"""
    position_file = os.path.join(data_dir, "position_data.json")
    try:
        with open(position_file, 'w') as f:
            json.dump(position_data, f, indent=2)
        logger.info(f"Updated position data saved to {position_file}")
        return True
    except Exception as e:
        logger.exception(f"Error saving position data: {e}")
        return False

def fix_position_data(position_data, daily_tracker, dry_run=False):
    """Fix position data based on daily tracker"""
    fixed_positions = position_data.copy()
    changes_made = False
    
    long_tickers = daily_tracker.get("long_tickers", [])
    short_tickers = daily_tracker.get("short_tickers", [])
    
    # Check each position against the daily tracker
    for ticker, data in position_data.items():
        ticker_upper = ticker.upper()
        position_type = data.get("type")
        
        # If ticker is in long_tickers but position type is SHORT, fix it
        if ticker_upper in long_tickers and position_type == "SHORT":
            logger.warning(f"Position type mismatch for {ticker}: Daily tracker says LONG but position data says SHORT")
            if not dry_run:
                fixed_positions[ticker]["type"] = "LONG"
                changes_made = True
        
        # If ticker is in short_tickers but position type is LONG, fix it
        elif ticker_upper in short_tickers and position_type == "LONG":
            logger.warning(f"Position type mismatch for {ticker}: Daily tracker says SHORT but position data says LONG")
            if not dry_run:
                fixed_positions[ticker]["type"] = "SHORT"
                changes_made = True
    
    return fixed_positions, changes_made

def check_gtt_conflicts(risk_manager, daily_tracker):
    """Check for conflicts between GTT orders and daily tracker"""
    gtt_tracker = risk_manager.load_gtt_tracker()
    conflicts = []
    
    long_tickers = daily_tracker.get("long_tickers", [])
    short_tickers = daily_tracker.get("short_tickers", [])
    
    # Known problematic tickers that should be carefully checked
    problematic_tickers = ["BIRLACORPN", "BIRLACORP", "RAYMOND", "SANOFI", "POKARNA", "CGPOWER", 
                          "SAMMAANCAP", "TFCILTD", "RADIANTCMS", "KANSAINER"]
    
    # Check each GTT against the daily tracker
    for ticker, data in gtt_tracker.get("tickers", {}).items():
        ticker_upper = ticker.upper()
        position_type = data.get("position_type")
        trigger_id = data.get("trigger_id")
        
        # If ticker is in long_tickers but GTT position type is SHORT, it's a conflict
        if ticker_upper in long_tickers and position_type == "SHORT":
            logger.warning(f"GTT conflict for {ticker}: Daily tracker says LONG but GTT is for SHORT")
            conflicts.append({
                "ticker": ticker_upper,
                "expected_type": "LONG",
                "actual_type": "SHORT",
                "trigger_id": trigger_id
            })
        
        # If ticker is in short_tickers but GTT position type is LONG, it's a conflict
        elif ticker_upper in short_tickers and position_type == "LONG":
            logger.warning(f"GTT conflict for {ticker}: Daily tracker says SHORT but GTT is for LONG")
            conflicts.append({
                "ticker": ticker_upper,
                "expected_type": "SHORT",
                "actual_type": "LONG",
                "trigger_id": trigger_id
            })
        
        # Remove GTT orders for tickers that aren't in the daily tracker at all
        elif ticker_upper not in long_tickers and ticker_upper not in short_tickers:
            logger.warning(f"GTT for {ticker} exists but ticker is not in daily tracker")
            conflicts.append({
                "ticker": ticker_upper,
                "expected_type": "NONE",
                "actual_type": position_type,
                "trigger_id": trigger_id
            })
        
        # Explicitly check known problematic tickers
        elif ticker_upper in problematic_tickers:
            if (position_type == "LONG" and ticker_upper not in long_tickers) or \
               (position_type == "SHORT" and ticker_upper not in short_tickers):
                logger.warning(f"Problematic ticker {ticker} has GTT but isn't properly tracked")
                conflicts.append({
                    "ticker": ticker_upper,
                    "expected_type": "NONE" if ticker_upper not in long_tickers and ticker_upper not in short_tickers else 
                                   ("LONG" if ticker_upper in long_tickers else "SHORT"),
                    "actual_type": position_type,
                    "trigger_id": trigger_id
                })
    
    return conflicts

def fix_gtt_conflicts(risk_manager, conflicts, dry_run=False, force_delete=False):
    """Fix conflicts by deleting conflicting GTT orders"""
    if not conflicts:
        logger.info("No GTT conflicts found")
        return 0
    
    logger.info(f"Found {len(conflicts)} GTT conflicts")
    
    if dry_run:
        logger.info("DRY RUN: Would delete the following GTT orders:")
        for conflict in conflicts:
            logger.info(f"  - Ticker: {conflict['ticker']}, ID: {conflict['trigger_id']}, " +
                       f"Expected: {conflict['expected_type']}, Actual: {conflict['actual_type']}")
        return 0
    
    # Ask for confirmation if not forced
    if not force_delete:
        logger.info("The following GTT orders will be deleted:")
        for conflict in conflicts:
            logger.info(f"  - Ticker: {conflict['ticker']}, ID: {conflict['trigger_id']}, " +
                       f"Expected: {conflict['expected_type']}, Actual: {conflict['actual_type']}")
        
        confirm = input("Do you want to delete these GTT orders? (yes/no): ")
        if confirm.lower() != "yes":
            logger.info("Operation cancelled by user")
            return 0
    
    # Delete conflicting GTT orders
    deleted_count = 0
    for conflict in conflicts:
        ticker = conflict["ticker"]
        trigger_id = conflict["trigger_id"]
        logger.info(f"Deleting GTT order for {ticker} with ID {trigger_id}")
        if risk_manager.delete_gtt_order(trigger_id, ticker):
            deleted_count += 1
        else:
            logger.error(f"Failed to delete GTT order for {ticker} with ID {trigger_id}")
    
    logger.info(f"Deleted {deleted_count} out of {len(conflicts)} conflicting GTT orders")
    return deleted_count

def main():
    # Parse command line arguments
    args = parse_args()
    
    logger.info("Starting GTT cleanup utility")
    
    # Get configuration
    config = get_config()
    data_dir = config.get('System', 'data_dir')
    
    # Verify that we're only operating on MIS product type
    product_type = config.get('Trading', 'product_type')
    if product_type != "MIS":
        logger.error(f"This utility can only operate on MIS product type, but found {product_type}")
        logger.error("GTT orders are only supported for MIS product type")
        return 1
    
    # Get risk manager and order manager
    risk_manager = get_risk_manager()
    order_manager = get_order_manager()
    
    # Load daily ticker tracker
    daily_tracker = load_daily_ticker_tracker(data_dir)
    if not daily_tracker:
        logger.error("Failed to load daily ticker tracker. Exiting.")
        return 1
    
    logger.info(f"Loaded daily ticker tracker from {datetime.now().strftime('%Y-%m-%d')}:")
    logger.info(f"  - Long tickers: {len(daily_tracker.get('long_tickers', []))}")
    logger.info(f"  - Short tickers: {len(daily_tracker.get('short_tickers', []))}")
    
    # Check for specific tickers from stdin
    specific_tickers = []
    if not sys.stdin.isatty():
        stdin_content = sys.stdin.read().strip()
        if stdin_content:
            specific_tickers = [t.strip().upper() for t in stdin_content.split(',') if t.strip()]
            if specific_tickers:
                logger.info(f"Processing specific tickers from stdin: {', '.join(specific_tickers)}")
    
    # Step 1: Fix position data
    position_data = load_position_data(data_dir)
    fixed_positions, changes_made = fix_position_data(position_data, daily_tracker, args.dry_run)
    
    if changes_made and not args.dry_run:
        if save_position_data(data_dir, fixed_positions):
            logger.info("Position data updated successfully")
        else:
            logger.error("Failed to save updated position data")
    elif args.dry_run and changes_made:
        logger.info("DRY RUN: Would update position data")
    
    # Step 2: Check and fix GTT conflicts
    conflicts = check_gtt_conflicts(risk_manager, daily_tracker)
    
    # Filter conflicts for specific tickers if needed
    if specific_tickers:
        filtered_conflicts = [c for c in conflicts if c["ticker"] in specific_tickers]
        if filtered_conflicts:
            logger.info(f"Filtered from {len(conflicts)} conflicts to {len(filtered_conflicts)} for specified tickers")
            conflicts = filtered_conflicts
        else:
            logger.info(f"No conflicts found for specified tickers ({', '.join(specific_tickers)})")
            conflicts = []
    
    deleted_count = fix_gtt_conflicts(risk_manager, conflicts, args.dry_run, args.force_delete)
    
    logger.info("GTT cleanup completed.")
    if args.dry_run:
        logger.info("This was a dry run. No changes were made.")
    elif deleted_count > 0 or changes_made:
        logger.info(f"Fixed {deleted_count} GTT conflicts and made {'position data changes' if changes_made else 'no position data changes'}")
    else:
        logger.info("No changes were needed.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())