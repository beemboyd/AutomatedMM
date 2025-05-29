#!/usr/bin/env python
"""
Script to remove all existing GTT (Good-Till-Triggered) orders.
This is useful for clearing all stop-loss orders at once.

Usage:
    python killgtt.py [--dry-run]
    
Options:
    --dry-run    List GTT orders but don't delete them
"""

import os
import sys
import json
import argparse
import logging
import requests
import time
from pathlib import Path

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config

# Set up logging
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
    parser = argparse.ArgumentParser(description="Delete all GTT (Good-Till-Triggered) orders")
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="List GTT orders but don't delete them"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Increase output verbosity"
    )
    return parser.parse_args()

def get_api_credentials():
    """Get API credentials from config"""
    config = get_config()
    api_key = config.get('API', 'api_key')
    access_token = config.get('API', 'access_token')
    
    if not api_key or not access_token:
        logger.error("API key or access token not found in config")
        sys.exit(1)
    
    return api_key, access_token

def get_all_gtt_orders(api_key, access_token, max_retries=3):
    """Fetch all existing GTT orders"""
    headers = {
        "X-Kite-Version": "3",
        "Authorization": f"token {api_key}:{access_token}"
    }
    gtt_url = "https://api.kite.trade/gtt/triggers"
    
    retry_count = 0
    while retry_count < max_retries:
        try:
            response = requests.get(gtt_url, headers=headers)
            if response.ok:
                data = response.json()
                orders = data.get("data", [])
                logger.info(f"Found {len(orders)} existing GTT orders")
                return orders
            else:
                logger.error(f"Failed to fetch GTT orders: {response.status_code} {response.text}")
                retry_count += 1
                if retry_count < max_retries:
                    logger.info(f"Retrying ({retry_count}/{max_retries})...")
                    time.sleep(1)  # Wait before retrying
                else:
                    logger.error(f"Max retries reached. Exiting.")
                    sys.exit(1)
        except Exception as e:
            logger.exception(f"Exception while fetching GTT orders: {e}")
            retry_count += 1
            if retry_count < max_retries:
                logger.info(f"Retrying ({retry_count}/{max_retries})...")
                time.sleep(1)  # Wait before retrying
            else:
                logger.error(f"Max retries reached. Exiting.")
                sys.exit(1)
    
    return []

def delete_gtt_order(api_key, access_token, order_id, max_retries=3):
    """Delete a specific GTT order"""
    headers = {
        "X-Kite-Version": "3",
        "Authorization": f"token {api_key}:{access_token}"
    }
    del_url = f"https://api.kite.trade/gtt/triggers/{order_id}"
    
    retry_count = 0
    while retry_count < max_retries:
        try:
            response = requests.delete(del_url, headers=headers)
            if response.ok:
                logger.info(f"Successfully deleted GTT order {order_id}")
                return True
            else:
                logger.error(f"Failed to delete GTT order {order_id}: {response.status_code} {response.text}")
                retry_count += 1
                if retry_count < max_retries:
                    logger.info(f"Retrying ({retry_count}/{max_retries})...")
                    time.sleep(1)  # Wait before retrying
                else:
                    logger.warning(f"Failed to delete GTT order {order_id} after {max_retries} retries")
                    return False
        except Exception as e:
            logger.exception(f"Exception while deleting GTT order {order_id}: {e}")
            retry_count += 1
            if retry_count < max_retries:
                logger.info(f"Retrying ({retry_count}/{max_retries})...")
                time.sleep(1)  # Wait before retrying
            else:
                logger.warning(f"Failed to delete GTT order {order_id} after {max_retries} retries")
                return False
    
    return False

def clear_gtt_tracker():
    """Clear the GTT tracker file"""
    config = get_config()
    data_dir = config.get('System', 'data_dir')
    gtt_tracker_file = os.path.join(data_dir, "gttz_gtt_tracker.json")
    
    if os.path.exists(gtt_tracker_file):
        try:
            # Create an empty tracker
            empty_tracker = {"tickers": {}}
            with open(gtt_tracker_file, 'w') as f:
                json.dump(empty_tracker, f, indent=4)
            logger.info(f"Cleared GTT tracker file: {gtt_tracker_file}")
        except Exception as e:
            logger.error(f"Error clearing GTT tracker file: {e}")
    else:
        logger.info(f"GTT tracker file not found: {gtt_tracker_file}")

def format_order_info(order):
    """Format GTT order information for display"""
    try:
        # Extract order details
        trigger_id = order.get("trigger_id") or order.get("id")
        
        # Parse condition
        condition = order.get("condition", {})
        if isinstance(condition, str):
            condition = json.loads(condition)
        
        symbol = condition.get("tradingsymbol", "UNKNOWN")
        exchange = condition.get("exchange", "UNKNOWN")
        trigger_values = condition.get("trigger_values", [])
        trigger_price = trigger_values[0] if trigger_values else "UNKNOWN"
        
        # Parse orders
        orders_data = order.get("orders", [])
        if isinstance(orders_data, str):
            orders_data = json.loads(orders_data)
        
        order_type = ""
        quantity = 0
        if orders_data and len(orders_data) > 0:
            order_type = orders_data[0].get("transaction_type", "UNKNOWN")
            quantity = orders_data[0].get("quantity", 0)
        
        # Determine position type (LONG/SHORT)
        position_type = "LONG" if order_type == "SELL" else "SHORT"
        
        return {
            "trigger_id": trigger_id,
            "symbol": symbol,
            "exchange": exchange,
            "position_type": position_type,
            "trigger_price": trigger_price,
            "order_type": order_type,
            "quantity": quantity
        }
    except Exception as e:
        logger.error(f"Error formatting order info: {e}")
        return {
            "trigger_id": order.get("trigger_id", "UNKNOWN"),
            "symbol": "ERROR",
            "error": str(e)
        }

def main():
    """Main function"""
    args = parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    logger.info("===== GTT Kill Switch Started =====")
    
    # Get configuration
    config = get_config()
    
    # Verify that we're only operating on MIS product type
    product_type = config.get('Trading', 'product_type')
    if product_type != "MIS":
        logger.error(f"This utility can only operate on MIS product type, but found {product_type}")
        logger.error("GTT orders are only supported for MIS product type")
        return
    
    # Get API credentials
    api_key, access_token = get_api_credentials()
    
    # Fetch all GTT orders
    orders = get_all_gtt_orders(api_key, access_token)
    
    if not orders:
        logger.info("No GTT orders found. Nothing to do.")
        return
    
    # Format and display order information
    logger.info(f"Found {len(orders)} GTT orders:")
    for i, order in enumerate(orders):
        order_info = format_order_info(order)
        logger.info(f"{i+1}. {order_info['symbol']} ({order_info['exchange']}) - " + 
                   f"{order_info['position_type']} - Trigger: {order_info['trigger_price']} - " +
                   f"Qty: {order_info['quantity']} - ID: {order_info['trigger_id']}")
    
    # Check if we're in dry-run mode
    if args.dry_run:
        logger.info("Dry run mode. No orders will be deleted.")
        return
    
    # Prompt for confirmation
    confirm = input("\nAre you sure you want to delete ALL GTT orders? [y/N]: ")
    if confirm.lower() != 'y':
        logger.info("Operation cancelled by user.")
        return
    
    # Delete all orders
    total_orders = len(orders)
    deleted_count = 0
    failed_count = 0
    
    logger.info(f"Deleting {total_orders} GTT orders...")
    for order in orders:
        try:
            order_info = format_order_info(order)
            trigger_id = order_info['trigger_id']
            
            if delete_gtt_order(api_key, access_token, trigger_id):
                deleted_count += 1
                logger.info(f"Deleted {deleted_count}/{total_orders}: {order_info['symbol']} - {trigger_id}")
            else:
                failed_count += 1
                logger.warning(f"Failed to delete: {order_info['symbol']} - {trigger_id}")
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.5)
        except Exception as e:
            failed_count += 1
            logger.exception(f"Error deleting order: {e}")
    
    # Clear GTT tracker file
    clear_gtt_tracker()
    
    # Summary
    logger.info("\n===== GTT Kill Switch Summary =====")
    logger.info(f"Total GTT orders: {total_orders}")
    logger.info(f"Successfully deleted: {deleted_count}")
    logger.info(f"Failed to delete: {failed_count}")
    logger.info("===== GTT Kill Switch Completed =====")

if __name__ == "__main__":
    main()