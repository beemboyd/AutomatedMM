#!/usr/bin/env python

import os
import sys
import logging
import argparse
import json
import time
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config
from order_manager import get_order_manager
from risk_management import RiskManager
from data_handler import get_data_handler
from kiteconnect import KiteConnect

# Set up logging
def setup_logging():
    config = get_config()
    log_dir = config.get('System', 'log_dir')
    log_level = config.get('System', 'log_level')
    
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'local_manage_risk.log')
    
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
    parser = argparse.ArgumentParser(description="Local risk management for positions")
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

def retry_api_call(func, max_retries=3, backoff_factor=2, *args, **kwargs):
    """Execute an API call with retry logic and exponential backoff"""
    logger = logging.getLogger()
    retry = 0
    last_exception = None
    
    while retry < max_retries:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            retry += 1
            last_exception = e
            wait_time = backoff_factor ** (retry - 1)
            logger.warning(f"API call failed (attempt {retry}/{max_retries}): {str(e)}. Retrying in {wait_time} seconds.")
            time.sleep(wait_time)
    
    logger.error(f"API call failed after {max_retries} attempts: {last_exception}")
    raise last_exception

class LocalRiskManager:
    """A self-contained risk manager that does not rely on state files"""
    
    def __init__(self, candle_timeframe=None):
        self.logger = logging.getLogger()
        self.config = get_config()
        self.data_handler = get_data_handler()
        self.order_manager = get_order_manager()
        
        # API configuration
        self.api_key = self.config.get('API', 'api_key')
        self.access_token = self.config.get('API', 'access_token')
        self.exchange = self.config.get('Trading', 'exchange')
        self.product_type = self.config.get('Trading', 'product_type')
        self.profit_target = self.config.get_float('Trading', 'profit_target', fallback=10.0)
        
        # Initialize KiteConnect client
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        
        # Zerodha API endpoints for GTT
        self.headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }
        self.gtt_url = "https://api.kite.trade/gtt/triggers"
        
        # Set candle timeframe
        self._candle_timeframe = candle_timeframe or self.config.get('Trading', 'risk_atr_timeframe', fallback="60minute")
    
    def get_all_positions(self):
        """Fetch all positions from the broker API"""
        try:
            return retry_api_call(self.order_manager.get_portfolio_positions)
        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            return {}, {}
    
    def fetch_all_active_gtt_orders(self):
        """Fetch all GTT orders from Zerodha's API and organize by symbol and type"""
        try:
            response = retry_api_call(lambda: self.kite.kite.gtt_get_orders())
            all_orders = response or []
            
            orders_by_symbol = {}
            
            for order in all_orders:
                order_status = order.get("status", "").lower()
                if order_status == "triggered":
                    continue
                    
                # Extract order details
                try:
                    condition = order.get("condition", {})
                    if isinstance(condition, str):
                        condition = json.loads(condition)
                        
                    symbol = condition.get("tradingsymbol", "").upper()
                    if not symbol:
                        continue
                        
                    trigger_id = order.get("id")
                    if not trigger_id:
                        self.logger.warning(f"No valid trigger id found in order: {order}")
                        continue
                        
                    # Get transaction type (BUY/SELL) to know if it's for a long or short position
                    orders_data = order.get("orders", [])
                    if isinstance(orders_data, str):
                        orders_data = json.loads(orders_data)
                        
                    if len(orders_data) == 0:
                        continue
                        
                    transaction_type = orders_data[0].get("transaction_type", "")
                    trigger_price = condition.get("trigger_values", [None])[0]
                    quantity = orders_data[0].get("quantity", 0)
                    
                    # Store order details
                    if symbol not in orders_by_symbol:
                        orders_by_symbol[symbol] = []
                        
                    orders_by_symbol[symbol].append({
                        "trigger_id": trigger_id,
                        "transaction_type": transaction_type,
                        "trigger_price": trigger_price,
                        "quantity": quantity
                    })
                except Exception as e:
                    self.logger.error(f"Error parsing GTT order: {e}")
                    continue
            
            self.logger.info(f"Found GTT orders for {len(orders_by_symbol)} symbols")
            return orders_by_symbol
        except Exception as e:
            self.logger.error(f"Error fetching GTT orders: {e}")
            return {}
    
    def delete_gtt_order(self, trigger_id):
        """Delete a GTT order by trigger ID"""
        try:
            self.logger.info(f"Deleting GTT order with ID: {trigger_id}")
            return retry_api_call(lambda: self.kite.delete_gtt(trigger_id))
        except Exception as e:
            self.logger.error(f"Failed to delete GTT order {trigger_id}: {e}")
            return False
    
    def place_market_order(self, ticker, quantity, transaction_type):
        """Place an immediate market order for take profit or stop loss"""
        try:
            self.logger.info(f"Placing market {transaction_type} order for {ticker}, quantity: {quantity}")
            order_id = retry_api_call(
                lambda: self.kite.place_order(
                    variety="regular",
                    exchange=self.exchange,
                    tradingsymbol=ticker,
                    transaction_type=transaction_type,
                    quantity=quantity,
                    order_type="MARKET",
                    product=self.product_type,
                    validity="DAY"
                )
            )
            self.logger.info(f"Market order placed for {ticker} with order id {order_id}")
            return order_id
        except Exception as e:
            self.logger.error(f"Failed to place market order for {ticker}: {e}")
            return None
    
    def get_previous_candle(self, ticker, interval=None, max_retries=3):
        """Get the previous completed candle for a ticker"""
        if interval is None:
            interval = self._candle_timeframe
            
        token = self.data_handler.get_instrument_token(ticker)
        if token is None:
            self.logger.error(f"Token not found for {ticker}. Cannot get previous candle.")
            return None
            
        # Calculate start and end times to get the last 2 candles
        end_date = datetime.now()
        
        # Determine time offset based on interval
        if interval == "5minute":
            start_date = end_date.replace(minute=(end_date.minute - end_date.minute % 5) - 15)
        elif interval == "15minute":
            start_date = end_date.replace(minute=(end_date.minute - end_date.minute % 15) - 45)
        elif interval == "30minute":
            start_date = end_date.replace(minute=(end_date.minute - end_date.minute % 30) - 90)
        elif interval == "60minute" or interval == "1hour":
            start_date = end_date.replace(minute=0, hour=end_date.hour - 3)
        else:
            start_date = end_date.replace(minute=0, hour=end_date.hour - 3)
        
        try:
            candles = retry_api_call(lambda: self.kite.historical_data(token, start_date, end_date, interval))
            if len(candles) >= 2:
                # Return the previous (second to last) candle
                return candles[-2]
            elif len(candles) == 1:
                # Only one candle available, use it
                self.logger.warning(f"Only one candle available for {ticker}, using it as previous candle")
                return candles[0]
            else:
                self.logger.warning(f"No candles found for {ticker}")
                return None
        except Exception as e:
            self.logger.error(f"Failed to fetch previous candle for {ticker}: {e}")
            return None
    
    def place_new_gtt_order(self, ticker, quantity, stop_loss, transaction_type):
        """Place a new GTT order for stop loss"""
        try:
            self.logger.info(f"Placing new GTT {transaction_type} order for {ticker}, quantity: {quantity}, trigger: {stop_loss}")
            
            # Check if price has already moved past the stop-loss
            ltp = self.data_handler.fetch_current_price(ticker)
            if ltp is None:
                self.logger.error(f"Could not fetch current price for {ticker}. Skipping GTT placement.")
                return False
                
            if (transaction_type == "SELL" and ltp <= stop_loss) or (transaction_type == "BUY" and ltp >= stop_loss):
                self.logger.warning(f"Current price ({ltp}) has already crossed stop-loss ({stop_loss}) for {ticker}")
                self.logger.info(f"Placing immediate market order instead of GTT for {ticker}")
                return self.place_market_order(ticker, quantity, transaction_type)

            # Adjust stop loss to ensure it's at least 0.25% away from current price
            min_distance = 0.0025 * ltp
            if transaction_type == "SELL" and (ltp - stop_loss) < min_distance:
                adjusted_stop = ltp - min_distance - 0.05  # Extra buffer to be safe
                self.logger.info(f"Adjusting stop loss for {ticker} from {stop_loss} to {adjusted_stop} to ensure minimum distance")
                stop_loss = adjusted_stop
            elif transaction_type == "BUY" and (stop_loss - ltp) < min_distance:
                adjusted_stop = ltp + min_distance + 0.05  # Extra buffer to be safe
                self.logger.info(f"Adjusting stop loss for {ticker} from {stop_loss} to {adjusted_stop} to ensure minimum distance")
                stop_loss = adjusted_stop
                
            # Round to ensure price is a multiple of tick size (0.05 for most equities)
            tick_size = 0.05
            stop_loss = round(stop_loss / tick_size) * tick_size
            
            # Create the GTT order
            return retry_api_call(
                lambda: self.kite.place_gtt(
                    trigger_type="single",
                    tradingsymbol=ticker,
                    exchange=self.exchange,
                    trigger_values=[stop_loss],
                    last_price=ltp,
                    orders=[{
                        "transaction_type": transaction_type,
                        "quantity": quantity,
                        "price": stop_loss,
                        "order_type": "LIMIT",
                        "product": self.product_type
                    }]
                )
            )
        except Exception as e:
            if "Trigger price was too close" in str(e):
                # Try again with a further adjusted stop loss
                try:
                    extra_buffer = 0.01 * ltp  # 1% additional buffer
                    if transaction_type == "SELL":
                        new_stop = stop_loss - extra_buffer
                    else:
                        new_stop = stop_loss + extra_buffer
                    
                    # Round to ensure price is a multiple of tick size
                    new_stop = round(new_stop / tick_size) * tick_size
                    
                    self.logger.info(f"Retrying GTT with further adjusted stop loss for {ticker}: {new_stop}")
                    return retry_api_call(
                        lambda: self.kite.place_gtt(
                            trigger_type="single",
                            tradingsymbol=ticker,
                            exchange=self.exchange,
                            trigger_values=[new_stop],
                            last_price=ltp,
                            orders=[{
                                "transaction_type": transaction_type,
                                "quantity": quantity,
                                "price": new_stop,
                                "order_type": "LIMIT",
                                "product": self.product_type
                            }]
                        )
                    )
                except Exception as e2:
                    self.logger.error(f"Failed to place GTT with adjusted stop loss for {ticker}: {e2}")
                    return False
            self.logger.error(f"Failed to place GTT order for {ticker}: {e}")
            return False
    
    def manage_long_position(self, ticker, data, existing_gtt_orders, no_trailing_stop, no_take_profit, profit_target):
        """Manage a single long position"""
        qty = data["quantity"]
        purchase_price = data["purchase_price"]
        current_price = self.data_handler.fetch_current_price(ticker)
        
        if current_price is None:
            self.logger.error(f"Could not fetch current price for {ticker}. Skipping risk management.")
            return
        
        # Calculate profit percentage
        profit_pct = ((current_price - purchase_price) / purchase_price) * 100
        
        self.logger.info(f"LONG {ticker}: Current price = {current_price}, Purchase price = {purchase_price}, Profit = {profit_pct:.2f}%")
        
        # Take profit if target reached and not disabled
        if not no_take_profit and profit_pct > profit_target:
            self.logger.info(f"LONG {ticker}: Profit target hit with profit {profit_pct:.2f}% (>{profit_target}%). Placing MARKET sell order.")
            self.place_market_order(ticker, qty, "SELL")
            return
        
        # Update trailing stop-loss if not disabled
        if not no_trailing_stop:
            # Get the previous candle
            prev_candle = self.get_previous_candle(ticker)
            
            if prev_candle is None:
                self.logger.warning(f"Could not get previous candle for {ticker}. Skipping stop-loss update.")
                return
            
            # For long positions, use the previous candle's low as stop-loss
            stop_loss = prev_candle["low"]
            
            self.logger.info(f"LONG {ticker}: Using previous candle low as stop-loss. Current price: {current_price}, computed SL: {stop_loss}")
            
            # Check if current price is already below calculated stop-loss value
            if current_price <= stop_loss:
                self.logger.info(f"LONG {ticker}: Current price {current_price} is below SL {stop_loss}. Selling immediately.")
                self.place_market_order(ticker, qty, "SELL")
                return
            
            # Check if we need to update the existing GTT order
            existing_orders = existing_gtt_orders.get(ticker, [])
            matching_orders = [order for order in existing_orders if order["transaction_type"].upper() == "SELL"]
            
            if not matching_orders:
                # No GTT order exists for this position, place one
                self.logger.info(f"LONG {ticker}: No existing GTT order found, placing new one at {stop_loss}")
                self.place_new_gtt_order(ticker, qty, stop_loss, "SELL")
            else:
                # Compare with existing GTT order
                current_trigger = matching_orders[0]["trigger_price"]
                
                # Only update if new stop loss is higher (better) than current one
                if stop_loss > current_trigger:
                    self.logger.info(f"LONG {ticker}: Updating GTT order from {current_trigger} to {stop_loss}")
                    self.delete_gtt_order(matching_orders[0]["trigger_id"])
                    self.place_new_gtt_order(ticker, qty, stop_loss, "SELL")
                else:
                    self.logger.info(f"LONG {ticker}: New calculated SL ({stop_loss}) not better than existing ({current_trigger}), keeping existing GTT order")
    
    def manage_short_position(self, ticker, data, existing_gtt_orders, no_trailing_stop, no_take_profit, profit_target):
        """Manage a single short position"""
        qty = data["quantity"]
        purchase_price = data["purchase_price"]
        current_price = self.data_handler.fetch_current_price(ticker)
        
        if current_price is None:
            self.logger.error(f"Could not fetch current price for {ticker}. Skipping risk management.")
            return
        
        # Calculate profit percentage for short position
        profit_pct = ((purchase_price - current_price) / purchase_price) * 100
        
        self.logger.info(f"SHORT {ticker}: Current price = {current_price}, Purchase price = {purchase_price}, Profit = {profit_pct:.2f}%")
        
        # Take profit if target reached and not disabled
        if not no_take_profit and profit_pct > profit_target:
            self.logger.info(f"SHORT {ticker}: Profit target hit with profit {profit_pct:.2f}% (>{profit_target}%). Placing MARKET buy order.")
            self.place_market_order(ticker, qty, "BUY")
            return
        
        # Update trailing stop-loss if not disabled
        if not no_trailing_stop:
            # Get the previous candle
            prev_candle = self.get_previous_candle(ticker)
            
            if prev_candle is None:
                self.logger.warning(f"Could not get previous candle for {ticker}. Skipping stop-loss update.")
                return
            
            # For short positions, use the previous candle's high as stop-loss
            stop_loss = prev_candle["high"]
            
            self.logger.info(f"SHORT {ticker}: Using previous candle high as stop-loss. Current price: {current_price}, computed SL: {stop_loss}")
            
            # Check if current price is already above calculated stop-loss value
            if current_price >= stop_loss:
                self.logger.info(f"SHORT {ticker}: Current price {current_price} is above SL {stop_loss}. Buying immediately to cover.")
                self.place_market_order(ticker, qty, "BUY")
                return
            
            # Check if we need to update the existing GTT order
            existing_orders = existing_gtt_orders.get(ticker, [])
            matching_orders = [order for order in existing_orders if order["transaction_type"].upper() == "BUY"]
            
            if not matching_orders:
                # No GTT order exists for this position, place one
                self.logger.info(f"SHORT {ticker}: No existing GTT order found, placing new one at {stop_loss}")
                self.place_new_gtt_order(ticker, qty, stop_loss, "BUY")
            else:
                # Compare with existing GTT order
                current_trigger = matching_orders[0]["trigger_price"]
                
                # Only update if new stop loss is lower (better) than current one for shorts
                if stop_loss < current_trigger:
                    self.logger.info(f"SHORT {ticker}: Updating GTT order from {current_trigger} to {stop_loss}")
                    self.delete_gtt_order(matching_orders[0]["trigger_id"])
                    self.place_new_gtt_order(ticker, qty, stop_loss, "BUY")
                else:
                    self.logger.info(f"SHORT {ticker}: New calculated SL ({stop_loss}) not better than existing ({current_trigger}), keeping existing GTT order")
    
    def run(self, no_trailing_stop=False, no_take_profit=False, profit_target=None):
        """Run risk management processes for all positions"""
        self.logger.info("Starting local risk management process")
        
        # Use profit target from config if not provided
        if profit_target is None:
            profit_target = self.profit_target
            
        try:
            # Step 1: Get all positions from broker API
            long_positions, short_positions = self.get_all_positions()
            
            # Step 2: Get existing GTT orders
            existing_gtt_orders = self.fetch_all_active_gtt_orders()
            
            # Step 3: Filter problematic tickers
            problematic_tickers = ["BIRLACORPN", "BIRLACORP", "RAYMOND", "SANOFI", "POKARNA", "CGPOWER", 
                                  "SAMMAANCAP", "TFCILTD", "RADIANTCMS", "KANSAINER"]
            
            for ticker in problematic_tickers:
                if ticker in long_positions:
                    self.logger.warning(f"Removing known problematic ticker {ticker} from long positions")
                    del long_positions[ticker]
                if ticker in short_positions:
                    self.logger.warning(f"Removing known problematic ticker {ticker} from short positions")
                    del short_positions[ticker]
            
            # Step 4: Process long positions
            self.logger.info(f"Processing {len(long_positions)} long positions")
            for ticker, data in long_positions.items():
                try:
                    self.manage_long_position(ticker, data, existing_gtt_orders, no_trailing_stop, no_take_profit, profit_target)
                except Exception as e:
                    self.logger.error(f"Error managing long position for {ticker}: {e}")
            
            # Step 5: Process short positions
            self.logger.info(f"Processing {len(short_positions)} short positions")
            for ticker, data in short_positions.items():
                try:
                    self.manage_short_position(ticker, data, existing_gtt_orders, no_trailing_stop, no_take_profit, profit_target)
                except Exception as e:
                    self.logger.error(f"Error managing short position for {ticker}: {e}")
            
            # Step 6: Check for proper GTT coverage
            self.check_gtt_coverage(long_positions, short_positions, existing_gtt_orders)
            
            # Step 7: Generate portfolio summary
            self.generate_portfolio_summary(long_positions, short_positions)
            
            self.logger.info("Local risk management completed successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error in risk management process: {e}")
            return False
            
    def check_gtt_coverage(self, long_positions, short_positions, existing_gtt_orders):
        """Check if all positions have GTT coverage"""
        self.logger.info("Checking GTT coverage for all positions")
        
        all_position_tickers = set(list(long_positions.keys()) + list(short_positions.keys()))
        missing_gtts = []
        
        for ticker in all_position_tickers:
            if ticker not in existing_gtt_orders:
                missing_gtts.append(ticker)
                
        if missing_gtts:
            self.logger.warning(f"Found {len(missing_gtts)} positions without GTT coverage: {sorted(missing_gtts)}")
            self.logger.info("Setting up GTT orders for positions with missing coverage")
            
            for ticker in missing_gtts:
                try:
                    if ticker in long_positions:
                        data = long_positions[ticker]
                        prev_candle = self.get_previous_candle(ticker)
                        if prev_candle:
                            stop_loss = prev_candle["low"]
                            self.logger.info(f"LONG {ticker}: Setting up missing GTT with SL at {stop_loss}")
                            self.place_new_gtt_order(ticker, data["quantity"], stop_loss, "SELL")
                    elif ticker in short_positions:
                        data = short_positions[ticker]
                        prev_candle = self.get_previous_candle(ticker)
                        if prev_candle:
                            stop_loss = prev_candle["high"]
                            self.logger.info(f"SHORT {ticker}: Setting up missing GTT with SL at {stop_loss}")
                            self.place_new_gtt_order(ticker, data["quantity"], stop_loss, "BUY")
                except Exception as e:
                    self.logger.error(f"Error setting up GTT for {ticker}: {e}")
        else:
            self.logger.info("All positions have GTT coverage")
    
    def generate_portfolio_summary(self, long_positions, short_positions):
        """Generate a summary of the current portfolio"""
        self.logger.info("=== Portfolio Summary ===")
        
        total_value = 0
        total_cost = 0
        
        # Process long positions
        for ticker, data in long_positions.items():
            qty = data["quantity"]
            purchase_price = data["purchase_price"]
            current_price = self.data_handler.fetch_current_price(ticker) or purchase_price
            
            position_value = current_price * qty
            position_cost = purchase_price * qty
            position_profit = (current_price - purchase_price) * qty
            profit_pct = ((current_price - purchase_price) / purchase_price) * 100
            
            total_value += position_value
            total_cost += position_cost
            
            self.logger.info(f"LONG {ticker}: {qty} shares, Entry: {purchase_price}, Current: {current_price}, " +
                           f"P/L: {position_profit:.2f} ({profit_pct:.2f}%)")
        
        # Process short positions
        for ticker, data in short_positions.items():
            qty = data["quantity"]
            purchase_price = data["purchase_price"]
            current_price = self.data_handler.fetch_current_price(ticker) or purchase_price
            
            position_value = current_price * qty
            position_cost = purchase_price * qty
            position_profit = (purchase_price - current_price) * qty
            profit_pct = ((purchase_price - current_price) / purchase_price) * 100
            
            total_value += position_value
            total_cost += position_cost
            
            self.logger.info(f"SHORT {ticker}: {qty} shares, Entry: {purchase_price}, Current: {current_price}, " +
                           f"P/L: {position_profit:.2f} ({profit_pct:.2f}%)")
        
        # Calculate overall profit percentage
        if total_cost > 0:
            total_profit = total_value - total_cost
            total_profit_pct = (total_profit / total_cost) * 100
            self.logger.info(f"Total portfolio value: {total_value:.2f}, Cost: {total_cost:.2f}, " +
                           f"P/L: {total_profit:.2f} ({total_profit_pct:.2f}%)")
        else:
            self.logger.info("No positions to calculate total profit")

def main():
    # Parse command line arguments
    args = parse_args()
    
    # Initialize logging
    logger = setup_logging()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Log start of execution
    logger.info(f"===== Local Risk Management Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    
    # Get configuration
    config = get_config()
    
    # Verify that we're only operating on MIS product type
    product_type = config.get('Trading', 'product_type')
    if product_type != "MIS":
        logger.error(f"This script can only operate on MIS product type, but found {product_type}")
        logger.error("For CNC (delivery) orders, use the scripts in the Daily folder")
        return
    
    # Create local risk manager instance
    risk_manager = LocalRiskManager(args.timeframe)
    
    # Get profit target from args or config
    profit_target = args.profit_target or config.get_float('Trading', 'profit_target', fallback=10.0)
    
    # Run the risk management process
    success = risk_manager.run(
        no_trailing_stop=args.no_trailing_stop,
        no_take_profit=args.no_take_profit,
        profit_target=profit_target
    )
    
    status = "Successfully completed" if success else "Completed with errors"
    logger.info(f"===== Local Risk Management {status} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")

if __name__ == "__main__":
    main()