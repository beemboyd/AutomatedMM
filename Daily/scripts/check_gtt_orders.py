#!/usr/bin/env python
"""
Script to check existing GTT orders on Zerodha
"""
import os
import sys
import logging
import argparse
from pprint import pformat

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)

# Import zerodha handler
from zerodha_handler import get_zerodha_handler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

def get_gtt_orders(ticker=None):
    """
    Get all GTT orders or filter by ticker
    """
    try:
        z_handler = get_zerodha_handler()
        logger.info("Fetching GTT orders from Zerodha")
        
        # Get all GTT orders
        gtt_orders = z_handler.kite.get_gtts()
        
        # Get individual order details for each GTT
        detailed_orders = []
        for order in gtt_orders:
            try:
                order_id = order.get('id')
                if order_id:
                    gtt_detail = z_handler.kite.get_gtt(order_id)
                    if gtt_detail:
                        detailed_orders.append(gtt_detail)
            except Exception as e:
                logger.warning(f"Error getting details for GTT order {order.get('id')}: {e}")
                detailed_orders.append(order)  # Use basic info if detailed fetch fails
        
        if ticker:
            # Filter for specific ticker in condition.tradingsymbol
            filtered_orders = []
            for order in detailed_orders:
                if order.get('condition', {}).get('tradingsymbol') == ticker:
                    filtered_orders.append(order)
            logger.info(f"Found {len(filtered_orders)} GTT orders for {ticker}")
            return filtered_orders
        else:
            logger.info(f"Found {len(detailed_orders)} GTT orders in total")
            return detailed_orders
    except Exception as e:
        logger.error(f"Error getting GTT orders: {e}")
        return []

def display_gtt_orders(orders, verbose=False):
    """
    Display GTT orders in a formatted way
    """
    if not orders:
        print("No GTT orders found.")
        return
    
    print(f"\n{'=' * 130}")
    print(f"{'ID':<10} {'Ticker':<10} {'Type':<8} {'Trigger Price':<25} {'Current Price':<12} {'Qty':<6} {'Order Type':<10} {'Status':<8} {'Created':<20}")
    print(f"{'-' * 130}")
    
    for order in orders:
        trigger_id = order.get('id', 'N/A')
        trigger_type = order.get('type', 'N/A')
        
        # Get ticker and other info from condition
        cond = order.get('condition', {})
        ticker = cond.get('tradingsymbol', 'N/A')
        trigger_values = cond.get('trigger_values', ['N/A'])
        trigger_value = trigger_values[0] if trigger_values else 'N/A'
        last_price = cond.get('last_price', 'N/A')
        
        # Other details
        status = order.get('status', 'N/A')
        created_at = order.get('created_at', 'N/A')
        
        # Get order details (quantity, order_type, price)
        order_details = order.get('orders', [{}])[0] if order.get('orders') else {}
        quantity = order_details.get('quantity', 'N/A')
        order_type = order_details.get('order_type', 'N/A')
        limit_price = order_details.get('price', 'N/A')
        
        # Calculate trigger percentage from current price
        if isinstance(trigger_value, (int, float)) and isinstance(last_price, (int, float)) and last_price > 0:
            trigger_pct = ((trigger_value - last_price) / last_price) * 100
            trigger_value_str = f"{trigger_value} ({trigger_pct:.2f}%)"
            if order_type == 'LIMIT' and isinstance(limit_price, (int, float)):
                trigger_value_str += f" → {limit_price:.2f}"
        else:
            trigger_value_str = str(trigger_value)
        
        print(f"{trigger_id:<10} {ticker:<10} {trigger_type:<8} {trigger_value_str:<25} {last_price:<12} {quantity:<6} {order_type:<10} {status:<8} {created_at:<20}")
    
    print(f"{'=' * 130}\n")
    
    # Show detailed information if verbose is True
    if verbose:
        for i, order in enumerate(orders):
            print(f"\nDetailed information for order {i+1}:")
            print(pformat(order, indent=2))
            print("\n")

def main():
    parser = argparse.ArgumentParser(description='Check GTT orders on Zerodha')
    parser.add_argument('--ticker', '-t', help='Filter by ticker symbol')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed information')
    
    args = parser.parse_args()
    
    try:
        logger.info("Connecting to Zerodha...")
        gtt_orders = get_gtt_orders(args.ticker)
        display_gtt_orders(gtt_orders, args.verbose)
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())