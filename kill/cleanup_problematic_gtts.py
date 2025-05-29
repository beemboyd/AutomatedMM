#!/usr/bin/env python
"""
Script to specifically cleanup GTT orders for problematic tickers like RAYMOND and SANOFI.
"""

import os
import sys
import json
import logging
import argparse
import requests
import time

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config
from risk_management import get_risk_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'cleanup_gtts.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Clean up GTT orders for problematic tickers")
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Show what would be deleted without making changes"
    )
    parser.add_argument(
        "--force", 
        action="store_true", 
        help="Delete GTT orders without confirmation"
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=["RAYMOND", "SANOFI", "BIRLACORPN", "BIRLACORP", "POKARNA", 
                "CGPOWER", "SAMMAANCAP", "TFCILTD", "RADIANTCMS", "KANSAINER"],
        help="List of ticker symbols to check and clean up"
    )
    return parser.parse_args()

def get_api_credentials():
    """Get API credentials from config"""
    config = get_config()
    api_key = config.get('API', 'api_key')
    access_token = config.get('API', 'access_token')
    
    if not api_key or not access_token:
        logger.error("API key or access token not found in config")
        return None, None
    
    return api_key, access_token

def get_all_gtt_orders(api_key, access_token):
    """Fetch all existing GTT orders from Zerodha"""
    if not api_key or not access_token:
        logger.error("API key or access token not provided")
        return []
        
    headers = {
        "X-Kite-Version": "3",
        "Authorization": f"token {api_key}:{access_token}"
    }
    gtt_url = "https://api.kite.trade/gtt/triggers"
    
    try:
        response = requests.get(gtt_url, headers=headers)
        if response.ok:
            data = response.json()
            return data.get("data", [])
        else:
            logger.error(f"Failed to fetch GTT orders: {response.status_code} {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error fetching GTT orders: {e}")
        return []

def delete_gtt_order(api_key, access_token, order_id):
    """Delete a GTT order by ID"""
    if not api_key or not access_token:
        logger.error("API key or access token not provided")
        return False
        
    headers = {
        "X-Kite-Version": "3",
        "Authorization": f"token {api_key}:{access_token}"
    }
    del_url = f"https://api.kite.trade/gtt/triggers/{order_id}"
    
    try:
        response = requests.delete(del_url, headers=headers)
        if response.ok:
            logger.info(f"Successfully deleted GTT order {order_id}")
            return True
        else:
            logger.error(f"Failed to delete GTT order {order_id}: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error deleting GTT order {order_id}: {e}")
        return False

def extract_ticker_from_gtt(gtt_order):
    """Extract the ticker symbol from a GTT order"""
    try:
        condition = gtt_order.get("condition", {})
        if isinstance(condition, str):
            try:
                condition = json.loads(condition)
            except:
                condition = {}
        
        return condition.get("tradingsymbol", "").upper()
    except Exception as e:
        logger.error(f"Error extracting ticker from GTT order: {e}")
        return ""

def update_gtt_tracker(risk_manager, deleted_tickers):
    """Update the GTT tracker file to remove deleted tickers"""
    gtt_tracker = risk_manager.load_gtt_tracker()
    tickers = gtt_tracker.get("tickers", {})
    
    for ticker in deleted_tickers:
        if ticker in tickers:
            del tickers[ticker]
    
    risk_manager.save_gtt_tracker(gtt_tracker)
    logger.info(f"Updated GTT tracker by removing {len(deleted_tickers)} tickers")

def cleanup_position_data(deleted_tickers):
    """Remove problematic tickers from position_data.json"""
    config = get_config()
    data_dir = config.get('System', 'data_dir')
    position_file = os.path.join(data_dir, "position_data.json")
    
    if not os.path.exists(position_file):
        logger.error(f"Position data file not found: {position_file}")
        return
    
    try:
        # Load position data
        with open(position_file, 'r') as f:
            position_data = json.load(f)
        
        # Track which tickers were removed
        removed = []
        
        # Remove problematic tickers
        for ticker in deleted_tickers:
            if ticker in position_data:
                removed.append(ticker)
                del position_data[ticker]
        
        # Save updated data
        with open(position_file, 'w') as f:
            json.dump(position_data, f, indent=2)
        
        if removed:
            logger.info(f"Removed {len(removed)} problematic tickers from position_data.json: {removed}")
        else:
            logger.info("No tickers needed to be removed from position_data.json")
    
    except Exception as e:
        logger.exception(f"Error cleaning up position data: {e}")

def main():
    args = parse_args()
    logger.info("Starting problematic GTT cleanup")
    
    # Get API credentials
    api_key, access_token = get_api_credentials()
    if not api_key or not access_token:
        return 1
    
    # Verify we're in MIS mode
    config = get_config()
    product_type = config.get('Trading', 'product_type')
    if product_type != "MIS":
        logger.error(f"This utility can only operate on MIS product type, but found {product_type}")
        logger.error("GTT orders are only supported for MIS product type")
        return 1
    
    # Get risk manager
    risk_manager = get_risk_manager()
    
    # Get all GTT orders
    gtt_orders = get_all_gtt_orders(api_key, access_token)
    
    # Filter for problematic tickers
    problematic_gtts = []
    problematic_tickers = [t.upper() for t in args.tickers]
    
    for order in gtt_orders:
        ticker = extract_ticker_from_gtt(order)
        if ticker in problematic_tickers:
            order_id = order.get("id")
            problematic_gtts.append({
                "ticker": ticker,
                "order_id": order_id
            })
    
    if not problematic_gtts:
        logger.info(f"No GTT orders found for problematic tickers: {problematic_tickers}")
        return 0
    
    # Display found GTTs
    logger.info(f"Found {len(problematic_gtts)} GTT orders for problematic tickers:")
    for gtt in problematic_gtts:
        logger.info(f"  - {gtt['ticker']}: Order ID {gtt['order_id']}")
    
    # Check if dry run
    if args.dry_run:
        logger.info("DRY RUN: Would delete the above GTT orders")
        return 0
    
    # Ask for confirmation unless forced
    if not args.force:
        confirm = input(f"Delete {len(problematic_gtts)} GTT orders for problematic tickers? (yes/no): ")
        if confirm.lower() != "yes":
            logger.info("Operation cancelled by user")
            return 0
    
    # Delete GTTs
    deleted_count = 0
    deleted_tickers = []
    
    for gtt in problematic_gtts:
        ticker = gtt["ticker"]
        order_id = gtt["order_id"]
        
        logger.info(f"Deleting GTT order for {ticker} (ID: {order_id})...")
        if delete_gtt_order(api_key, access_token, order_id):
            deleted_count += 1
            deleted_tickers.append(ticker)
        time.sleep(0.5)  # Avoid rate limiting
    
    # Update GTT tracker
    update_gtt_tracker(risk_manager, deleted_tickers)
    
    # Clean up position data
    cleanup_position_data(problematic_tickers)
    
    logger.info(f"Successfully deleted {deleted_count} out of {len(problematic_gtts)} GTT orders and cleaned up position data")
    return 0

if __name__ == "__main__":
    sys.exit(main())