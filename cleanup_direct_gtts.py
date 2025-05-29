#!/usr/bin/env python
"""
cleanup_direct_gtts.py

This script directly uses the Zerodha API to delete GTT orders for problematic tickers
using direct API calls instead of the KiteConnect library.
"""

import os
import sys
import json
import logging
import argparse
import requests
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import trading system modules
from config import get_config
from kiteconnect import KiteConnect

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
    parser = argparse.ArgumentParser(description="Clean up GTT orders for problematic tickers")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        help="List of specific tickers to clean up (default: all)"
    )
    return parser.parse_args()

def initialize_kite():
    """Initialize KiteConnect client"""
    config = get_config()
    api_key = config.get('API', 'api_key')
    access_token = config.get('API', 'access_token')
    
    if not api_key or not access_token:
        logger.error("API key or access token not found in config")
        return None, None, None
    
    try:
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        profile = kite.profile()
        logger.info(f"Successfully connected to Kite as {profile['user_name']}")
        return kite, api_key, access_token
    except Exception as e:
        logger.error(f"Failed to initialize KiteConnect: {e}")
        return None, api_key, access_token

def get_all_gtt_orders(kite):
    """Fetch all GTT orders"""
    try:
        gtt_orders = kite.get_gtts()
        return gtt_orders
    except Exception as e:
        logger.error(f"Error fetching GTT orders: {e}")
        return []

def delete_gtt_order_direct(api_key, access_token, order_id):
    """Delete a GTT order using direct API call"""
    try:
        headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {api_key}:{access_token}"
        }
        
        # Make the request to delete the GTT order
        url = f"https://api.kite.trade/gtt/triggers/{order_id}"
        response = requests.delete(url, headers=headers)
        
        if response.status_code == 200:
            logger.info(f"Successfully deleted GTT order {order_id}")
            return True
        else:
            logger.error(f"Failed to delete GTT order {order_id}: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error deleting GTT order {order_id}: {e}")
        return False

def main():
    args = parse_args()
    
    logger.info("Starting direct GTT cleanup")
    
    # Initialize Kite
    kite, api_key, access_token = initialize_kite()
    if not kite:
        return 1
    
    # Get all GTT orders
    gtt_orders = get_all_gtt_orders(kite)
    
    if not gtt_orders:
        logger.info("No GTT orders found")
        return 0
    
    # Filter orders if specific tickers provided
    if args.tickers:
        tickers_set = set(t.upper() for t in args.tickers)
        filtered_orders = []
        
        for order in gtt_orders:
            try:
                # Extract trading symbol
                condition = order.get("condition", {})
                if isinstance(condition, str):
                    try:
                        condition = json.loads(condition)
                    except:
                        condition = {}
                
                symbol = condition.get("tradingsymbol", "").upper()
                
                if symbol in tickers_set:
                    filtered_orders.append(order)
            except Exception as e:
                logger.error(f"Error processing order: {e}")
        
        logger.info(f"Filtered from {len(gtt_orders)} to {len(filtered_orders)} orders for specified tickers")
        gtt_orders = filtered_orders
    
    logger.info(f"Found {len(gtt_orders)} GTT orders to clean up")
    
    # Process each order
    if args.dry_run:
        logger.info("DRY RUN: Would delete the following GTT orders:")
        for order in gtt_orders:
            try:
                trigger_id = order.get("id")
                
                # Extract trading symbol
                condition = order.get("condition", {})
                if isinstance(condition, str):
                    try:
                        condition = json.loads(condition)
                    except:
                        condition = {}
                
                symbol = condition.get("tradingsymbol", "Unknown")
                
                logger.info(f"  - {symbol}: ID {trigger_id}")
            except Exception as e:
                logger.error(f"Error processing order: {e}")
    else:
        # Delete orders
        deleted_count = 0
        for order in gtt_orders:
            try:
                trigger_id = order.get("id")
                
                # Extract trading symbol
                condition = order.get("condition", {})
                if isinstance(condition, str):
                    try:
                        condition = json.loads(condition)
                    except:
                        condition = {}
                
                symbol = condition.get("tradingsymbol", "Unknown")
                
                logger.info(f"Deleting GTT order for {symbol} (ID: {trigger_id})...")
                
                if delete_gtt_order_direct(api_key, access_token, trigger_id):
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Error processing order: {e}")
        
        logger.info(f"Successfully deleted {deleted_count} out of {len(gtt_orders)} GTT orders")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())