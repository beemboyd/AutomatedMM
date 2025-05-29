#!/usr/bin/env python
"""
test_problematic_tickers.py

This script tests each ticker in the problematic tickers list to see if it still
has issues with GTT orders. It helps clean up the list of problematic tickers
by identifying which ones can actually have GTT orders properly.
"""

import os
import sys
import json
import logging
import time
import argparse
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import trading system modules
from config import get_config
from kiteconnect import KiteConnect
from risk_management import get_risk_manager
from state_manager import get_state_manager

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
    parser = argparse.ArgumentParser(description="Test problematic tickers for GTT order issues")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=["BIRLACORPN", "BIRLACORP", "RAYMOND", "SANOFI", "POKARNA", "CGPOWER", 
                "SAMMAANCAP", "TFCILTD", "RADIANTCMS", "KANSAINER"],
        help="List of ticker symbols to test"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean up all test GTT orders after testing"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only check without creating or deleting GTT orders"
    )
    return parser.parse_args()

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

def get_current_price(kite, ticker, exchange="NSE"):
    """Get current market price for a ticker"""
    try:
        ltp_data = kite.ltp([f"{exchange}:{ticker}"])
        return ltp_data[f"{exchange}:{ticker}"]["last_price"]
    except Exception as e:
        logger.error(f"Error getting price for {ticker}: {e}")
        return None

def create_test_gtt(risk_manager, ticker, position_type="LONG", exchange="NSE"):
    """Create a test GTT order for a ticker"""
    try:
        logger.info(f"Creating test GTT for {ticker} ({position_type})")
        
        # Get current price
        kite = risk_manager.kite
        current_price = get_current_price(kite, ticker, exchange)
        if not current_price:
            logger.error(f"Could not get price for {ticker}")
            return False, None
        
        # Set trigger prices
        if position_type == "LONG":
            trigger_price = round(current_price * 0.92, 1)  # 8% below current price
        else:  # SHORT
            trigger_price = round(current_price * 1.08, 1)  # 8% above current price
        
        # Set GTT parameters
        quantity = 1
        gtt_type = "single" if position_type == "LONG" else "single"  # Use 'single' for both cases for simplicity
        
        # Create condition
        condition = {
            "exchange": exchange,
            "tradingsymbol": ticker,
            "trigger_values": [trigger_price],
            "last_price": current_price
        }
        
        # Create orders
        price = trigger_price  # For simplicity, use trigger price as limit price
        
        if position_type == "LONG":
            transaction_type = "SELL"  # SELL to close a LONG position
        else:  # SHORT
            transaction_type = "BUY"   # BUY to close a SHORT position
        
        orders = [{
            "exchange": exchange,
            "tradingsymbol": ticker,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "order_type": "LIMIT",
            "product": "MIS",
            "price": price
        }]
        
        # Create GTT
        try:
            trigger_id = kite.place_gtt(
                trigger_type=gtt_type,
                tradingsymbol=ticker,
                exchange=exchange,
                trigger_values=[trigger_price],
                last_price=current_price,
                orders=orders
            )
            
            logger.info(f"Successfully created GTT for {ticker} with ID {trigger_id}")
            
            # Update GTT tracker
            gtt_tracker = risk_manager.load_gtt_tracker()
            if "tickers" not in gtt_tracker:
                gtt_tracker["tickers"] = {}
            
            gtt_tracker["tickers"][ticker] = {
                "position_type": position_type,
                "trigger_id": trigger_id,
                "trigger_price": trigger_price,
                "timestamp": datetime.now().isoformat()
            }
            
            risk_manager.save_gtt_tracker(gtt_tracker)
            return True, trigger_id
        except Exception as e:
            error_str = str(e).lower()
            if "duplicate" in error_str or "already exists" in error_str:
                logger.warning(f"Duplicate GTT for {ticker}: {e}")
                return False, None
            else:
                logger.error(f"Error creating GTT for {ticker}: {e}")
                return False, None
    except Exception as e:
        logger.error(f"Failed to create test GTT for {ticker}: {e}")
        return False, None

def delete_test_gtt(risk_manager, ticker, trigger_id):
    """Delete a test GTT order"""
    try:
        logger.info(f"Deleting test GTT for {ticker} with ID {trigger_id}")
        result = risk_manager.delete_gtt_order(trigger_id, ticker)
        
        if result:
            logger.info(f"Successfully deleted GTT for {ticker}")
            return True
        else:
            logger.error(f"Failed to delete GTT for {ticker}")
            return False
    except Exception as e:
        logger.error(f"Error deleting GTT for {ticker}: {e}")
        return False

def main():
    args = parse_args()
    
    logger.info("Starting problematic ticker testing")
    
    # Initialize risk manager
    risk_manager = get_risk_manager()
    
    # Initialize Kite
    kite = initialize_kite()
    if not kite:
        return 1
    
    # Verify we're in MIS mode
    config = get_config()
    product_type = config.get('Trading', 'product_type')
    if product_type != "MIS":
        logger.error(f"This utility can only operate on MIS product type, but found {product_type}")
        logger.error("GTT orders are only supported for MIS product type")
        return 1
    
    # Get state manager
    state_manager = get_state_manager()
    
    # Test each ticker
    results = []
    test_gtts = []
    
    if args.dry_run:
        logger.info("DRY RUN: Will check tickers without creating GTT orders")
        
        for ticker in args.tickers:
            logger.info(f"Checking if {ticker} has existing GTT orders...")
            
            # Check if ticker exists
            try:
                ltp_data = kite.ltp([f"NSE:{ticker}"])
                if f"NSE:{ticker}" in ltp_data:
                    price = ltp_data[f"NSE:{ticker}"]["last_price"]
                    logger.info(f"{ticker} exists with current price: {price}")
                    results.append({
                        "ticker": ticker,
                        "exists": True,
                        "price": price,
                        "ok_to_remove": "Unknown (needs testing)"
                    })
                else:
                    logger.warning(f"{ticker} does not exist or cannot be found")
                    results.append({
                        "ticker": ticker,
                        "exists": False,
                        "price": None,
                        "ok_to_remove": True
                    })
            except Exception as e:
                logger.error(f"Error checking {ticker}: {e}")
                results.append({
                    "ticker": ticker,
                    "exists": False,
                    "price": None,
                    "ok_to_remove": "Unknown (error encountered)"
                })
    else:
        # Create GTTs and test each ticker
        for ticker in args.tickers:
            logger.info(f"Testing ticker: {ticker}")
            
            # Try to create GTT
            success, trigger_id = create_test_gtt(risk_manager, ticker, "LONG")
            
            if success:
                logger.info(f"Successfully created GTT for {ticker}")
                test_gtts.append({"ticker": ticker, "trigger_id": trigger_id})
                
                # Try to delete right away
                time.sleep(1)  # Brief pause to avoid rate limiting
                delete_success = delete_test_gtt(risk_manager, ticker, trigger_id)
                
                if delete_success:
                    logger.info(f"GTT for {ticker} created and deleted successfully")
                    results.append({
                        "ticker": ticker,
                        "success": True,
                        "gtt_created": True,
                        "gtt_deleted": True,
                        "ok_to_remove": True
                    })
                else:
                    logger.warning(f"GTT for {ticker} created but could not be deleted")
                    results.append({
                        "ticker": ticker,
                        "success": True,
                        "gtt_created": True,
                        "gtt_deleted": False,
                        "ok_to_remove": False
                    })
            else:
                logger.warning(f"Could not create GTT for {ticker}")
                results.append({
                    "ticker": ticker,
                    "success": False,
                    "gtt_created": False,
                    "gtt_deleted": False,
                    "ok_to_remove": False
                })
            
            # Sleep to avoid rate limiting
            time.sleep(2)
    
    # If --clean flag is set, clean up any remaining test GTTs
    if args.clean and test_gtts:
        logger.info("Cleaning up all test GTT orders")
        
        for test_gtt in test_gtts:
            ticker = test_gtt["ticker"]
            trigger_id = test_gtt["trigger_id"]
            
            delete_success = delete_test_gtt(risk_manager, ticker, trigger_id)
            if delete_success:
                logger.info(f"Cleaned up GTT for {ticker}")
            else:
                logger.warning(f"Failed to clean up GTT for {ticker}")
    
    # Display results
    logger.info("\n===== TESTING RESULTS =====")
    
    if args.dry_run:
        for result in results:
            status = "EXISTS" if result["exists"] else "NOT FOUND"
            price = f", Price: {result['price']}" if result["price"] else ""
            logger.info(f"{result['ticker']}: {status}{price}")
    else:
        ok_to_remove = []
        keep_problematic = []
        
        for result in results:
            ticker = result["ticker"]
            
            if result.get("ok_to_remove", False):
                status = "OK TO REMOVE from problematic list"
                ok_to_remove.append(ticker)
            else:
                status = "KEEP in problematic list"
                keep_problematic.append(ticker)
            
            success_str = ""
            if "success" in result:
                gtt_created = "GTT created" if result.get("gtt_created", False) else "GTT creation failed"
                gtt_deleted = "GTT deleted" if result.get("gtt_deleted", False) else "GTT deletion failed"
                success_str = f" ({gtt_created}, {gtt_deleted})"
            
            logger.info(f"{ticker}: {status}{success_str}")
        
        if ok_to_remove:
            logger.info("\nTickers that can be removed from problematic list:")
            logger.info(", ".join(ok_to_remove))
        
        if keep_problematic:
            logger.info("\nTickers that should remain in problematic list:")
            logger.info(", ".join(keep_problematic))
    
    return 0

if __name__ == "__main__":
    sys.exit(main())