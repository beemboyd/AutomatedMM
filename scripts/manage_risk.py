#!/usr/bin/env python

import os
import sys
import logging
import argparse
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config
from order_manager import get_order_manager
from risk_management import get_risk_manager
from state_manager import get_state_manager

# Set up loggingx`
def setup_logging():
    config = get_config()
    log_dir = config.get('System', 'log_dir')
    log_level = config.get('System', 'log_level')
    
    os.makedirs(log_dir, exist_ok=True)
    
    # Create manage_risk.log in the log directory
    log_file = os.path.join(log_dir, 'manage_risk.log')
    
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
    parser = argparse.ArgumentParser(description="Manage risk for existing positions")
    parser.add_argument(
        "--no-trailing-stop", 
        action="store_true", 
        help="Disable trailing stop-loss updates"
    )
    parser.add_argument(
        "--no-take-profit", 
        action="store_true", 
        help="Disable take-profit exits"
    )
    parser.add_argument(
        "-p", "--profit-target", 
        type=float,
        help="Custom profit target percentage"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Increase output verbosity"
    )
    parser.add_argument(
        "--timeframe",
        help="Override the candle timeframe for stop-loss calculation (e.g. 5minute, 15minute, 30minute, 60minute)"
    )
    return parser.parse_args()

def process_long_positions(risk_manager, order_manager, profit_target, no_trailing_stop, no_take_profit):
    """Process long positions for risk management"""
    logger = logging.getLogger()
    state_manager = get_state_manager()
    
    try:
        # 1. Fetch actual positions from broker API
        long_positions, _ = order_manager.get_portfolio_positions()
        
        # 2. Get the state manager's record of positions
        state_positions = state_manager.get_all_positions()
        
        # 3. Clean up any positions in state that no longer exist
        for ticker in list(state_positions.keys()):
            # If position exists in state but not in actual positions and it's a LONG position
            if ticker not in long_positions and state_positions[ticker].get("type") == "LONG":
                logger.info(f"Position {ticker} exists in state but not in actual positions. Removing from state.")
                state_manager.remove_position(ticker)
                # Also remove any GTT associated with this ticker
                state_manager.remove_gtt(ticker)
        
        # 4. Update daily tickers to match actual positions
        for ticker in long_positions.keys():
            if not state_manager.is_long_ticker(ticker):
                logger.info(f"Adding {ticker} to daily tracker's long_tickers list")
                state_manager.add_long_ticker(ticker)
                
        # 5. Filter out problematic positions
        tickers_to_remove = []
        
        # Check for position type conflicts (same ticker in both long and short lists)
        for ticker in long_positions.keys():
            if state_manager.is_short_ticker(ticker):
                logger.warning(f"Inconsistency detected: {ticker} is in long positions but also in short_tickers. Ignoring.")
                tickers_to_remove.append(ticker)
        
        # Known problematic tickers to specifically check
        problematic_tickers = ["BIRLACORPN", "BIRLACORP", "RAYMOND", "SANOFI", "POKARNA", "CGPOWER", 
                              "SAMMAANCAP", "TFCILTD", "RADIANTCMS", "KANSAINER"]
        
        # Make sure none of these problematic tickers are in the wrong list
        for ticker in problematic_tickers:
            if ticker in long_positions:
                logger.warning(f"Removing known problematic ticker {ticker} from long positions")
                tickers_to_remove.append(ticker)
        
        # Remove any conflicting tickers from positions
        for ticker in tickers_to_remove:
            if ticker in long_positions:
                del long_positions[ticker]
        
        if not long_positions:
            logger.info("No long positions found to manage")
            return
            
        logger.info(f"Found {len(long_positions)} long positions to manage: {list(long_positions.keys())}")
        
        # Load position tracking data from state manager
        position_tracking_data = risk_manager.load_position_data()
        
        # No need to pre-calculate ATRs as we're using previous candle for stop-loss
        logger.info("Using previous candle data for stop-loss calculations...")
        
        # Get existing GTT orders
        existing_gtt_orders = risk_manager.get_existing_gtt_orders_by_symbol()
        
        # Process each long position
        for ticker, data in long_positions.items():
            qty = data["quantity"]
            purchase_price = data["purchase_price"]
            current_price = risk_manager.data_handler.fetch_current_price(ticker)
            
            if current_price is None:
                logger.error(f"Could not fetch current price for {ticker}. Skipping risk management.")
                continue
            
            # Update trailing stop tracking data for this position
            old_position_data = position_tracking_data.get(ticker, {})
            old_best_price = old_position_data.get("best_price", 0)
            
            position_tracking_data = risk_manager.update_trailing_stop_data(
                position_tracking_data, ticker, "LONG", current_price, purchase_price
            )
            
            # Check if position moved favorably (price increased)
            price_improved = current_price > old_best_price if old_best_price > 0 else False
            
            # Calculate profit percentage
            profit_pct = ((current_price - purchase_price) / purchase_price) * 100
            
            logger.info(f"LONG {ticker}: Current price = {current_price}, Purchase price = {purchase_price}, " +
                         f"Profit = {profit_pct:.2f}%, Best price = {position_tracking_data[ticker]['best_price']}")
            
            # Take profit if target reached and not disabled
            if not no_take_profit and profit_pct > profit_target:
                logger.info(f"LONG {ticker}: Profit target hit with profit {profit_pct:.2f}% (>{profit_target}%). " +
                             f"Placing MARKET sell order at current price {current_price}.")
                risk_manager.place_market_order(ticker, qty, "SELL")
                continue
            
            # Update trailing stop-loss if not disabled
            if not no_trailing_stop:
                # Get the previous hourly candle
                prev_candle = risk_manager.get_previous_candle(ticker, interval="60minute")
                
                if prev_candle is None:
                    logger.warning(f"Could not get previous candle for {ticker}. Skipping stop-loss update.")
                    continue
                
                # For long positions, use the previous candle's low as stop-loss
                stop_loss = prev_candle["low"]
                
                logger.info(f"LONG {ticker}: Using previous candle low as stop-loss. " +
                             f"Current price: {current_price}, computed SL: {stop_loss}")
                
                # Check if current price is already below calculated stop-loss value
                if current_price <= stop_loss:
                    logger.info(f"LONG {ticker}: Current price {current_price} is below SL {stop_loss}. Selling immediately.")
                    risk_manager.place_market_order(ticker, qty, "SELL")
                    # Remove from state to prevent further management
                    state_manager.remove_position(ticker)
                    state_manager.remove_gtt(ticker)
                    continue
                
                # Check if we need to update the existing GTT order
                existing_orders = existing_gtt_orders.get(ticker, [])
                matching_orders = [order for order in existing_orders if order["transaction_type"].upper() == "SELL"]
                
                if not matching_orders:
                    # No GTT order exists for this position, always place one
                    logger.info(f"LONG {ticker}: No existing GTT order found, placing new one at {stop_loss}")
                    risk_manager.place_new_gtt_order(ticker, qty, stop_loss, "SELL")
                elif not price_improved:
                    # Skip updating since price hasn't improved
                    logger.info(f"LONG {ticker}: Price hasn't improved, keeping existing GTT order with trigger at {matching_orders[0]['trigger_price']}")
                else:
                    # Price improved, update GTT order with new stop loss
                    for order in matching_orders:
                        old_trigger = order["trigger_price"]
                        # Only update if new stop loss is higher (better) than current one
                        if stop_loss > old_trigger:
                            logger.info(f"LONG {ticker}: Updating GTT order from {old_trigger} to {stop_loss}")
                            risk_manager.delete_gtt_order(order["trigger_id"], ticker)
                            risk_manager.place_new_gtt_order(ticker, qty, stop_loss, "SELL")
                        else:
                            logger.info(f"LONG {ticker}: New calculated SL ({stop_loss}) not better than existing ({old_trigger}), keeping existing GTT order")
        
        # Save updated position tracking data
        risk_manager.save_position_data(position_tracking_data)
        
    except Exception as e:
        logger.exception(f"Error processing long positions: {e}")

def process_short_positions(risk_manager, order_manager, profit_target, no_trailing_stop, no_take_profit):
    """Process short positions for risk management"""
    logger = logging.getLogger()
    state_manager = get_state_manager()
    
    try:
        # 1. Fetch actual positions from broker API
        _, short_positions = order_manager.get_portfolio_positions()
        
        # 2. Get the state manager's record of positions
        state_positions = state_manager.get_all_positions()
        
        # 3. Clean up any positions in state that no longer exist
        for ticker in list(state_positions.keys()):
            # If position exists in state but not in actual positions and it's a SHORT position
            if ticker not in short_positions and state_positions[ticker].get("type") == "SHORT":
                logger.info(f"Position {ticker} exists in state but not in actual positions. Removing from state.")
                state_manager.remove_position(ticker)
                # Also remove any GTT associated with this ticker
                state_manager.remove_gtt(ticker)
        
        # 4. Update daily tickers to match actual positions
        for ticker in short_positions.keys():
            if not state_manager.is_short_ticker(ticker):
                logger.info(f"Adding {ticker} to daily tracker's short_tickers list")
                state_manager.add_short_ticker(ticker)
        
        # 5. Filter out problematic positions
        tickers_to_remove = []
        
        # Check for position type conflicts (same ticker in both long and short lists)
        for ticker in short_positions.keys():
            if state_manager.is_long_ticker(ticker):
                logger.warning(f"Inconsistency detected: {ticker} is in short positions but also in long_tickers. Ignoring.")
                tickers_to_remove.append(ticker)
        
        # Known problematic tickers to specifically check
        problematic_tickers = ["BIRLACORPN", "BIRLACORP", "RAYMOND", "SANOFI", "POKARNA", "CGPOWER", 
                              "SAMMAANCAP", "TFCILTD", "RADIANTCMS", "KANSAINER"]
        
        # Explicitly check for and remove known problematic tickers
        for ticker in problematic_tickers:
            if ticker in short_positions:
                logger.warning(f"Removing known problematic ticker {ticker} from short positions")
                tickers_to_remove.append(ticker)
        
        # Remove any conflicting tickers from positions
        for ticker in tickers_to_remove:
            if ticker in short_positions:
                del short_positions[ticker]
        
        if not short_positions:
            logger.info("No short positions found to manage")
            return
            
        logger.info(f"Found {len(short_positions)} short positions to manage: {list(short_positions.keys())}")
        
        # Load position tracking data from state manager
        position_tracking_data = risk_manager.load_position_data()
        
        # No need to pre-calculate ATRs as we're using previous candle for stop-loss
        logger.info("Using previous candle data for stop-loss calculations...")
        
        # Get existing GTT orders
        existing_gtt_orders = risk_manager.get_existing_gtt_orders_by_symbol()
        
        # Process each short position
        for ticker, data in short_positions.items():
            qty = data["quantity"]
            purchase_price = data["purchase_price"]
            current_price = risk_manager.data_handler.fetch_current_price(ticker)
            
            if current_price is None:
                logger.error(f"Could not fetch current price for {ticker}. Skipping risk management.")
                continue
            
            # Update trailing stop tracking data for this position
            old_position_data = position_tracking_data.get(ticker, {})
            old_best_price = old_position_data.get("best_price", float('inf')) if old_position_data else float('inf')
            
            position_tracking_data = risk_manager.update_trailing_stop_data(
                position_tracking_data, ticker, "SHORT", current_price, purchase_price
            )
            
            # Check if position moved favorably (price decreased for shorts)
            price_improved = current_price < old_best_price if old_best_price < float('inf') else False
            
            # Calculate profit percentage for short position
            profit_pct = ((purchase_price - current_price) / purchase_price) * 100
            
            logger.info(f"SHORT {ticker}: Current price = {current_price}, Purchase price = {purchase_price}, " +
                         f"Profit = {profit_pct:.2f}%, Best price = {position_tracking_data[ticker]['best_price']}")
            
            # Take profit if target reached and not disabled
            if not no_take_profit and profit_pct > profit_target:
                logger.info(f"SHORT {ticker}: Profit target hit with profit {profit_pct:.2f}% (>{profit_target}%). " +
                             f"Placing MARKET buy order at current price {current_price}.")
                risk_manager.place_market_order(ticker, qty, "BUY")
                # Remove from state to prevent further management
                state_manager.remove_position(ticker)
                state_manager.remove_gtt(ticker)
                continue
            
            # Update trailing stop-loss if not disabled
            if not no_trailing_stop:
                # Get the previous hourly candle
                prev_candle = risk_manager.get_previous_candle(ticker, interval="60minute")
                
                if prev_candle is None:
                    logger.warning(f"Could not get previous candle for {ticker}. Skipping stop-loss update.")
                    continue
                
                # For short positions, use the previous candle's high as stop-loss
                stop_loss = prev_candle["high"]
                
                logger.info(f"SHORT {ticker}: Using previous candle high as stop-loss. " +
                             f"Current price: {current_price}, computed SL: {stop_loss}")
                
                # Check if current price is already above calculated stop-loss value
                if current_price >= stop_loss:
                    logger.info(f"SHORT {ticker}: Current price {current_price} is above SL {stop_loss}. Buying immediately to cover.")
                    risk_manager.place_market_order(ticker, qty, "BUY")
                    # Remove from state to prevent further management
                    state_manager.remove_position(ticker)
                    state_manager.remove_gtt(ticker)
                    continue
                
                # Check if we need to update the existing GTT order
                existing_orders = existing_gtt_orders.get(ticker, [])
                matching_orders = [order for order in existing_orders if order["transaction_type"].upper() == "BUY"]
                
                if not matching_orders:
                    # No GTT order exists for this position, always place one
                    logger.info(f"SHORT {ticker}: No existing GTT order found, placing new one at {stop_loss}")
                    risk_manager.place_new_gtt_order(ticker, qty, stop_loss, "BUY")
                elif not price_improved:
                    # Skip updating since price hasn't improved
                    logger.info(f"SHORT {ticker}: Price hasn't improved, keeping existing GTT order with trigger at {matching_orders[0]['trigger_price']}")
                else:
                    # Price improved, update GTT order with new stop loss
                    for order in matching_orders:
                        old_trigger = order["trigger_price"]
                        # Only update if new stop loss is lower (better) than current one for shorts
                        if stop_loss < old_trigger:
                            logger.info(f"SHORT {ticker}: Updating GTT order from {old_trigger} to {stop_loss}")
                            risk_manager.delete_gtt_order(order["trigger_id"], ticker)
                            risk_manager.place_new_gtt_order(ticker, qty, stop_loss, "BUY")
                        else:
                            logger.info(f"SHORT {ticker}: New calculated SL ({stop_loss}) not better than existing ({old_trigger}), keeping existing GTT order")
        
        # Save updated position tracking data
        risk_manager.save_position_data(position_tracking_data)
        
    except Exception as e:
        logger.exception(f"Error processing short positions: {e}")

def main():
    # Parse command line arguments
    args = parse_args()
    
    # Initialize logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Log start of execution
    logger.info(f"===== Risk Management Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    
    # Get configuration
    config = get_config()
    
    # Verify that we're only operating on MIS product type
    product_type = config.get('Trading', 'product_type')
    if product_type != "MIS":
        logger.error(f"This script can only operate on MIS product type, but found {product_type}")
        logger.error("For CNC (delivery) orders, use the scripts in the Daily folder")
        return
    
    # Get risk manager and order manager
    risk_manager = get_risk_manager()
    order_manager = get_order_manager()
    
    # Apply command line overrides for candle timeframe if provided
    if hasattr(args, 'timeframe') and args.timeframe:
        logger.info(f"Overriding candle timeframe with command line value: {args.timeframe}")
        risk_manager._candle_timeframe = args.timeframe
        
        # Create a wrapper for the get_previous_candle method
        original_get_previous_candle = risk_manager.get_previous_candle
        
        def get_previous_candle_wrapper(ticker, interval=None, max_retries=3):
            if interval is None:
                interval = risk_manager._candle_timeframe
            return original_get_previous_candle(ticker, interval, max_retries)
        
        # Replace the method with our wrapper
        risk_manager.get_previous_candle = get_previous_candle_wrapper
    
    # Get profit target from args or config
    profit_target = args.profit_target or config.get_float('Trading', 'profit_target', fallback=10.0)
    
    # Process positions
    try:
        # Process long positions
        logger.info("=== Processing LONG positions ===")
        process_long_positions(risk_manager, order_manager, profit_target, args.no_trailing_stop, args.no_take_profit)
        
        # Process short positions
        logger.info("=== Processing SHORT positions ===")
        process_short_positions(risk_manager, order_manager, profit_target, args.no_trailing_stop, args.no_take_profit)
        
        # Log portfolio summary
        logger.info("=== Portfolio Summary ===")
        long_positions, short_positions = order_manager.get_portfolio_positions()
        
        # Calculate total values
        total_value = 0
        total_cost = 0
        
        # Process long positions
        for ticker, data in long_positions.items():
            qty = data["quantity"]
            purchase_price = data["purchase_price"]
            current_price = risk_manager.data_handler.fetch_current_price(ticker) or purchase_price
            
            position_value = current_price * qty
            position_cost = purchase_price * qty
            position_profit = (current_price - purchase_price) * qty
            profit_pct = ((current_price - purchase_price) / purchase_price) * 100
            
            total_value += position_value
            total_cost += position_cost
            
            logger.info(f"LONG {ticker}: {qty} shares, Entry: {purchase_price}, Current: {current_price}, " +
                         f"P/L: {position_profit:.2f} ({profit_pct:.2f}%)")
        
        # Process short positions
        for ticker, data in short_positions.items():
            qty = data["quantity"]
            purchase_price = data["purchase_price"]
            current_price = risk_manager.data_handler.fetch_current_price(ticker) or purchase_price
            
            position_value = current_price * qty
            position_cost = purchase_price * qty
            position_profit = (purchase_price - current_price) * qty
            profit_pct = ((purchase_price - current_price) / purchase_price) * 100
            
            total_value += position_value
            total_cost += position_cost
            
            logger.info(f"SHORT {ticker}: {qty} shares, Entry: {purchase_price}, Current: {current_price}, " +
                         f"P/L: {position_profit:.2f} ({profit_pct:.2f}%)")
        
        # Calculate overall profit percentage
        if total_cost > 0:
            total_profit = total_value - total_cost
            total_profit_pct = (total_profit / total_cost) * 100
            logger.info(f"Total portfolio value: {total_value:.2f}, Cost: {total_cost:.2f}, " +
                         f"P/L: {total_profit:.2f} ({total_profit_pct:.2f}%)")
        else:
            logger.info("No positions to calculate total profit.")
        
    except Exception as e:
        logger.exception(f"Error during risk management: {e}")
    
    # Validate GTT coverage for all positions using state manager
    try:
        # Get all current positions from broker API
        long_positions, short_positions = order_manager.get_portfolio_positions()
        all_position_tickers = set(list(long_positions.keys()) + list(short_positions.keys()))
        
        # Get positions and GTTs from the state manager
        state_manager = get_state_manager()
        state_positions = state_manager.get_all_positions()
        state_gtts = state_manager.get_all_gtts()
        
        # Check for positions without GTTs
        missing_gtts = []
        for ticker in all_position_tickers:
            if ticker not in state_gtts:
                missing_gtts.append(ticker)
        
        # Log summary
        logger.info(f"GTT Coverage Validation: {len(state_gtts)} GTTs for {len(all_position_tickers)} MIS positions")
        
        # Log warning if any positions are missing GTTs
        if missing_gtts:
            logger.warning(f"BUG-Investigate further - GTT missing for {sorted(missing_gtts)}")
            
            # Add cleanup suggestion
            logger.info("Run cleanup utilities to resolve inconsistencies:")
            logger.info("   python utils/cleanup_positions.py --include-zerodha --fix-inconsistencies")
            logger.info("   python utils/cleanup_gtt.py")
        else:
            logger.info("All positions have corresponding GTT orders - risk management complete")
    except Exception as e:
        logger.exception(f"Error during GTT validation check: {e}")
    
    # Log end of execution
    logger.info(f"===== Risk Management Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====\n")

if __name__ == "__main__":
    main()
