#!/usr/bin/env python
"""
Risk Manager New Daily Script

This script updates stop loss orders for CNC (delivery) positions based on price action:
- If price is above KC Upper Limit, SL is adjusted to previous day's low
- If price is above SMA20 and within KC Upper Channel, SL is adjusted to SMA20
- The script runs the same calculations as scan_market_daily.py to determine indicators

Features:
- Updates stop losses based on current market conditions
- Uses the same technical indicator calculation as scan_market_daily.py
- Logs all actions with detailed information
- Supports dry run mode

Created: 2025-05-08
"""

import os
import sys
import time
import json
import logging
import argparse
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config
from data_handler import get_data_handler
from order_manager import get_order_manager
from state_manager import get_state_manager

# Set up logging
def setup_logging():
    config = get_config()
    log_dir = config.get('System', 'log_dir')
    log_level = config.get('System', 'log_level')
    
    os.makedirs(log_dir, exist_ok=True)
    
    # Create risk_manager_new_daily.log in the log directory
    log_file = os.path.join(log_dir, 'risk_manager_new_daily.log')
    
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
    parser = argparse.ArgumentParser(description="Update stop loss orders for CNC positions based on price action")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without modifying stop loss orders"
    )
    parser.add_argument(
        "-t", "--ticker",
        help="Process only a specific ticker (default: process all CNC positions)"
    )
    return parser.parse_args()

# --- Technical indicator calculation functions (copied from scan_market_daily.py) ---

def fetch_data_kite(ticker, interval, from_date, to_date, kite, retry_delay=2, max_retries=3):
    """Fetch historical data from Kite"""
    logger = logging.getLogger()
    
    # Get instrument token from data handler
    data_handler = get_data_handler()
    token = data_handler.get_instrument_token(ticker)
    if token is None:
        logger.warning(f"Instrument token for {ticker} not found.")
        return pd.DataFrame()

    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching data for {ticker} with interval {interval} from {from_date} to {to_date}...")
            data = kite.historical_data(token, from_date, to_date, interval)

            if not data:
                logger.warning(f"No data returned for {ticker}.")
                return pd.DataFrame()

            df = pd.DataFrame(data)
            df.rename(columns={
                "date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume"
            }, inplace=True)

            df['Date'] = pd.to_datetime(df['Date'])
            df['Ticker'] = ticker

            logger.info(f"Data successfully fetched for {ticker} with {len(df)} records.")
            return df

        except Exception as e:
            if "Too many requests" in str(e) and attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                logger.warning(
                    f"Rate limit hit for {ticker}. Waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
            else:
                logger.error(f"Error fetching data for {ticker}: {e}")
                return pd.DataFrame()

    logger.error(f"Failed to fetch data for {ticker} after {max_retries} attempts.")
    return pd.DataFrame()

def calculate_indicators_daily(daily_data):
    """Calculate daily indicators including SMA, EMA, Keltner Channel, ATR, etc."""
    logger = logging.getLogger()
    
    if len(daily_data) < 50:
        logger.warning(
            f"Insufficient daily data points for {daily_data['Ticker'].iloc[0]}. Only {len(daily_data)} records available, minimum of 50 required.")
        return None

    daily_data['Daily_20SMA'] = daily_data['Close'].rolling(window=20).mean()
    daily_data['Daily_50EMA'] = daily_data['Close'].ewm(span=50, adjust=False).mean()

    # Calculate EMA and WM 
    daily_data['EMA21'] = daily_data['Close'].ewm(span=21, adjust=False).mean()
    daily_data['WM'] = (daily_data['EMA21'] - daily_data['Daily_50EMA']) / 2

    # Calculate ATR components
    prev_close = daily_data['Close'].shift(1)
    tr1 = daily_data['High'] - daily_data['Low']
    tr2 = (daily_data['High'] - prev_close).abs()
    tr3 = (daily_data['Low'] - prev_close).abs()
    daily_data['TR'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    daily_data['ATR'] = daily_data['TR'].rolling(window=20).mean()

    # Keltner Channel calculation (using 20-day SMA and 20-day ATR)
    daily_data['KC_upper'] = daily_data['Daily_20SMA'] + (2 * daily_data['ATR'])
    daily_data['KC_lower'] = daily_data['Daily_20SMA'] - (2 * daily_data['ATR'])

    # Store previous day's low for SL adjustment
    daily_data['Prev_Low'] = daily_data['Low'].shift(1)

    return daily_data

def get_current_market_price(ticker):
    """Get current market price for a ticker"""
    try:
        data_handler = get_data_handler()
        return data_handler.fetch_current_price(ticker)
    except Exception as e:
        logging.error(f"Error getting current price for {ticker}: {e}")
        return None

# --- Risk management functions ---

def update_stop_loss_order(ticker, new_sl_price, dry_run=False):
    """Update the stop loss order for a ticker"""
    logger = logging.getLogger()
    state_manager = get_state_manager()
    order_manager = get_order_manager()
    
    # Get current position data
    position = state_manager.get_position(ticker)
    if not position:
        logger.warning(f"No position found for {ticker}, cannot update stop loss")
        return False
    
    # In our system, CNC positions may not have quantity set correctly
    # Let's use a default quantity of 1 for CNC positions if not available
    quantity = 1
    
    # If quantity is present in the position data, try to use it
    if "quantity" in position:
        try:
            qty_val = position.get("quantity")
            quantity = int(qty_val)
            if quantity <= 0:
                logger.info(f"Invalid quantity in position data: {qty_val}, using default of 1")
                quantity = 1
        except (ValueError, TypeError):
            logger.info(f"Quantity in position data is not a number: {position.get('quantity')}, using default of 1")
    else:
        logger.info(f"No quantity found in position data for {ticker}, using default of 1")
        
    # Get current stop loss price if any
    current_sl = position.get("sl_price", 0)
    
    # Get current GTT order if any
    gtt_data = state_manager.get_gtt(ticker)
    gtt_trigger_id = None
    if gtt_data:
        gtt_trigger_id = gtt_data.get("trigger_id")
        logger.info(f"Found existing GTT stop loss order for {ticker} with ID {gtt_trigger_id}")
    
    # Round stop loss price to 2 decimal places
    new_sl_price = round(new_sl_price, 2)
    
    # If dry run, just log what would be done
    if dry_run:
        if gtt_trigger_id:
            logger.info(f"DRY RUN: Would update stop loss for {ticker} from {current_sl} to {new_sl_price}")
        else:
            logger.info(f"DRY RUN: Would place new stop loss for {ticker} at {new_sl_price}")
        return True
    
    # If there's an existing GTT order, we need to check if it needs to be updated
    if gtt_trigger_id:
        # Check if the stop loss price has changed significantly
        current_trigger_price = gtt_data.get("trigger_price", 0)
        price_difference = abs(current_trigger_price - new_sl_price) / current_trigger_price if current_trigger_price else 1.0
        
        # If the stop loss price hasn't changed by more than 1%, keep the existing order
        if price_difference < 0.01:
            logger.info(f"Existing GTT SL price for {ticker} ({current_trigger_price}) is within 1% of new SL price ({new_sl_price}). Keeping existing order.")
            
            # Update the position data with the current SL price for tracking
            current_position = state_manager.get_position(ticker)
            if current_position:
                current_position["sl_price"] = current_trigger_price
                state_manager._save_state()
                logger.info(f"Updated position state with current stop loss price for {ticker}")
            
            return True
        
        # If the price has changed by more than 1%, update the GTT order
        logger.info(f"Updating GTT order for {ticker}. Old SL: {current_trigger_price}, New SL: {new_sl_price}")
        
        # For now, we'll delete the old GTT order and create a new one
        try:
            # Delete existing GTT order via Kite API
            headers = order_manager.headers
            url = f"{order_manager.gtt_url}/{gtt_trigger_id}"
            response = requests.delete(url, headers=headers)
            
            if response.ok:
                logger.info(f"Successfully deleted existing GTT order for {ticker}")
                # Remove from state manager (we'll create a new one)
                state_manager.remove_gtt(ticker)
            else:
                logger.error(f"Failed to delete GTT order for {ticker}: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error deleting GTT order for {ticker}: {e}")
            return False
    
    # Place a new GTT order (either because there was no existing order or we deleted the old one)
    try:
        # Get the latest position data (without cleaning)
        current_position = state_manager.get_position(ticker)
        
        # Check if the position still exists (might have been removed by another process)
        if not current_position:
            logger.warning(f"Position data for {ticker} not found. Recreating position data.")
            state_manager.add_position(
                ticker=ticker,
                position_type="LONG",  # For CNC positions, we always use LONG
                quantity=quantity,
                entry_price=0,  # We don't know the entry price, will be updated when actual data is available
                product_type="CNC"
            )
        
        # Place a new GTT stop loss order
        success = order_manager.place_gtt_stoploss_order(
            tradingsymbol=ticker, 
            quantity=quantity, 
            stop_loss=new_sl_price, 
            position_type="LONG"  # For CNC positions, we always use LONG
        )
        
        if success:
            logger.info(f"Successfully updated stop loss for {ticker} to {new_sl_price}")
            
            # Update position with new stop loss price
            current_position = state_manager.get_position(ticker)
            if current_position:
                current_position["sl_price"] = new_sl_price
                state_manager._save_state()
                logger.info(f"Updated position state with new stop loss price for {ticker}")
            else:
                logger.warning(f"Position data for {ticker} still not found after GTT placement. This is unexpected.")
            
            return True
        else:
            logger.error(f"Failed to place new GTT order for {ticker}")
            return False
            
    except Exception as e:
        logger.error(f"Error placing new GTT order for {ticker}: {e}")
        return False

def process_ticker(ticker, dry_run=False):
    """Process a single ticker and update stop loss if needed"""
    logger = logging.getLogger()
    config = get_config()
    
    logger.info(f"Processing {ticker} for stop loss update")
    logger.info(f"Dry run mode: {dry_run}")
    
    try:
        # Get Kite Connect client
        import time
        from kiteconnect import KiteConnect
        api_key = config.get('API', 'api_key')
        access_token = config.get('API', 'access_token')
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        
        # Fetch historical data for analysis
        now = datetime.now()
        from_date_daily = (now - relativedelta(months=6)).strftime('%Y-%m-%d')
        to_date = now.strftime('%Y-%m-%d')
        
        # Map interval for Kite Connect API
        interval_mapping = {
            '5m': '5minute',
            '1h': '60minute',
            '1d': 'day',
            '1w': 'week'
        }
        
        # Fetch daily data
        daily_data = fetch_data_kite(ticker, interval_mapping['1d'], from_date_daily, to_date, kite)
        
        if daily_data.empty:
            logger.warning(f"Insufficient data for {ticker}, skipping.")
            return False
        
        # Calculate indicators
        daily_data_with_indicators = calculate_indicators_daily(daily_data)
        
        if daily_data_with_indicators is None:
            logger.warning(f"Failed to calculate indicators for {ticker}.")
            return False
        
        # Get current market price
        current_price = get_current_market_price(ticker)
        if current_price is None:
            logger.warning(f"Could not get current market price for {ticker}, skipping")
            return False
        
        # Get the latest bar's data
        current_bar = daily_data_with_indicators.iloc[-1]
        
        # Determine the appropriate stop loss price based on current price position
        # Default SL is set as 98% of the daily KC lower channel
        new_sl = current_bar['KC_lower'] * 0.98
        sl_reason = "default (98% of KC_lower)"
        
        # Logic to update stop loss based on price action
        if current_price > current_bar['KC_upper']:
            # If price is above KC Upper Limit, SL should be adjusted to low of previous candle
            new_sl = current_bar['Prev_Low']
            sl_reason = "above KC Upper (previous day's low)"
            logger.info(f"{ticker} - Price ({current_price}) above KC Upper ({current_bar['KC_upper']}), setting SL to previous day's low: {new_sl}")
        elif current_price > current_bar['Daily_20SMA'] and current_price < current_bar['KC_upper']:
            # If price is above SMA20 and within KC Upper Channel, SL should be SMA20
            new_sl = current_bar['Daily_20SMA']
            sl_reason = "above SMA20 within KC Upper (SMA20)"
            logger.info(f"{ticker} - Price ({current_price}) above SMA20 ({current_bar['Daily_20SMA']}) and within KC Upper, setting SL to SMA20: {new_sl}")
        
        # Log technical analysis data
        logger.info(f"{ticker} Technical Analysis:")
        logger.info(f"  Current Price: {current_price}")
        logger.info(f"  SMA20: {current_bar['Daily_20SMA']}")
        logger.info(f"  KC Upper: {current_bar['KC_upper']}")
        logger.info(f"  KC Lower: {current_bar['KC_lower']}")
        logger.info(f"  Prev Day Low: {current_bar['Prev_Low']}")
        logger.info(f"  New SL ({sl_reason}): {new_sl}")
        
        # Update the stop loss order
        success = update_stop_loss_order(ticker, new_sl, dry_run)
        
        if success:
            logger.info(f"Successfully processed {ticker} with new stop loss: {new_sl} ({sl_reason})")
            return True
        else:
            logger.warning(f"Failed to update stop loss for {ticker}")
            return False
            
    except Exception as e:
        logger.exception(f"Error processing {ticker}: {e}")
        return False

def process_all_positions(dry_run=False, specific_ticker=None):
    """Process all CNC positions or a specific ticker if specified"""
    logger = logging.getLogger()
    state_manager = get_state_manager()
    
    # Get all positions and filter for CNC
    all_positions = state_manager.get_all_positions()
    cnc_positions = {
        ticker: data for ticker, data in all_positions.items() 
        if data.get("product_type") == "CNC"
    }
    
    if not cnc_positions:
        logger.info("No CNC positions found to process")
        return
    
    if specific_ticker:
        specific_ticker = specific_ticker.upper()
        if specific_ticker in cnc_positions:
            logger.info(f"Processing specific ticker: {specific_ticker}")
            process_ticker(specific_ticker, dry_run)
        else:
            logger.warning(f"Ticker {specific_ticker} not found in CNC positions")
    else:
        logger.info(f"Processing {len(cnc_positions)} CNC positions")
        for ticker in cnc_positions:
            process_ticker(ticker, dry_run)

def check_state_consistency():
    """Check if trading_state and Zerodha positions are consistent"""
    logger = logging.getLogger()
    state_manager = get_state_manager()
    order_manager = get_order_manager()
    
    logger.info("Checking state consistency with Zerodha positions")
    
    try:
        # Get CNC positions from state_manager
        all_positions = state_manager.get_all_positions()
        cnc_positions = {
            ticker: data for ticker, data in all_positions.items() 
            if data.get("product_type") == "CNC"
        }
        
        # Get CNC positions from Zerodha via Portfolio API
        try:
            # For this we need to use the kite client directly
            kite = order_manager.kite
            zerodha_positions = kite.positions().get("day", [])
            cnc_zerodha_positions = {}
            
            for pos in zerodha_positions:
                if pos.get("product") == "CNC" and pos.get("quantity", 0) > 0:
                    ticker = pos.get("tradingsymbol")
                    cnc_zerodha_positions[ticker] = {
                        "quantity": pos.get("quantity", 0),
                        "entry_price": pos.get("average_price", 0),
                        "pnl": pos.get("pnl", 0)
                    }
            
            logger.info(f"Found {len(cnc_zerodha_positions)} CNC positions in Zerodha portfolio")
            
            # Compare positions
            missing_in_state = [t for t in cnc_zerodha_positions if t not in cnc_positions]
            missing_in_zerodha = [t for t in cnc_positions if t not in cnc_zerodha_positions]
            
            if missing_in_state:
                logger.warning(f"Found {len(missing_in_state)} positions in Zerodha but not in state: {missing_in_state}")
                # Fix missing positions
                for ticker in missing_in_state:
                    data = cnc_zerodha_positions[ticker]
                    logger.info(f"Recreating state for {ticker} with quantity {data['quantity']} and price {data['entry_price']}")
                    state_manager.add_position(
                        ticker=ticker,
                        position_type="LONG",  # For CNC positions, we always use LONG
                        quantity=data["quantity"],
                        entry_price=data["entry_price"],
                        product_type="CNC"
                    )
            
            if missing_in_zerodha:
                logger.warning(f"Found {len(missing_in_zerodha)} positions in state but not in Zerodha: {missing_in_zerodha}")
                # We don't remove these as they might be legitimate CNC positions that haven't settled yet
                
            logger.info("State consistency check completed")
            
        except Exception as e:
            logger.error(f"Error fetching Zerodha positions: {e}")
            
    except Exception as e:
        logger.error(f"Error during state consistency check: {e}")

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_args()
    
    # Initialize logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Log start of execution
    logger.info(f"===== Risk Manager CNC Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    
    try:
        # First, check state consistency with Zerodha positions
        check_state_consistency()
        
        # Then process all positions or specific ticker
        process_all_positions(args.dry_run, args.ticker)
    except Exception as e:
        logger.exception(f"Error during risk management: {e}")
    
    # Log end of execution
    logger.info(f"===== Risk Manager CNC Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====\n")

if __name__ == "__main__":
    import time
    import requests
    main()