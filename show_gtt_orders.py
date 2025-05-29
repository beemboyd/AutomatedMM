#!/usr/bin/env python
"""
show_gtt_orders.py

This script shows all active GTT orders for the account.
"""

import os
import sys
import json
import logging
import argparse
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

def initialize_kite():
    """Initialize KiteConnect client"""
    config = get_config()
    api_key = config.get('API', 'api_key')
    access_token = config.get('API', 'access_token')
    
    if not api_key or not access_token:
        logger.error("API key or access token not found in config")
        return None
    
    try:
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        profile = kite.profile()
        logger.info(f"Successfully connected to Kite as {profile['user_name']}")
        return kite
    except Exception as e:
        logger.error(f"Failed to initialize KiteConnect: {e}")
        return None

def get_all_gtt_orders(kite):
    """Fetch all GTT orders"""
    try:
        gtt_orders = kite.get_gtts()
        return gtt_orders
    except Exception as e:
        logger.error(f"Error fetching GTT orders: {e}")
        return []

def main():
    # Initialize Kite
    kite = initialize_kite()
    if not kite:
        return 1
    
    # Get all GTT orders
    gtt_orders = get_all_gtt_orders(kite)
    
    if not gtt_orders:
        logger.info("No GTT orders found")
        return 0
    
    logger.info(f"Found {len(gtt_orders)} GTT orders:")
    
    # Show each GTT order
    for i, order in enumerate(gtt_orders, 1):
        try:
            trigger_id = order.get("id")
            status = order.get("status")
            
            # Extract trading symbol
            condition = order.get("condition", {})
            if isinstance(condition, str):
                try:
                    condition = json.loads(condition)
                except:
                    condition = {}
            
            symbol = condition.get("tradingsymbol", "Unknown")
            exchange = condition.get("exchange", "Unknown")
            trigger_values = condition.get("trigger_values", [])
            last_price = condition.get("last_price")
            
            # Print order details
            logger.info(f"Order {i}:")
            logger.info(f"  - ID: {trigger_id}")
            logger.info(f"  - Status: {status}")
            logger.info(f"  - Symbol: {symbol} ({exchange})")
            logger.info(f"  - Trigger values: {trigger_values}")
            logger.info(f"  - Last price: {last_price}")
            logger.info(f"  - Created at: {order.get('created_at')}")
            logger.info(f"  - Updated at: {order.get('updated_at')}")
            logger.info("")
        except Exception as e:
            logger.error(f"Error processing GTT order: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())