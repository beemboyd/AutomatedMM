#!/usr/bin/env python

import os
import sys
import json
import time
import logging
import argparse
import threading
import signal
from datetime import datetime
from queue import Queue
from typing import Dict, List, Tuple, Optional

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config
from kiteconnect import KiteConnect, KiteTicker
from data_handler import get_data_handler

# Set up logging
def setup_logging():
    config = get_config()
    log_dir = config.get('System', 'log_dir')
    log_level = config.get('System', 'log_level')
    
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'position_watchdog.log')
    
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
    parser = argparse.ArgumentParser(description="Real-time position watchdog with polling approach")
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Increase output verbosity"
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=60,
        help="Interval in seconds to check for new positions (default: 60)"
    )
    parser.add_argument(
        "--profit-target",
        type=float,
        default=None,
        help="Take profit percentage target (overrides config)"
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=None,
        help="Interval in seconds to poll prices (default: 5.0, from config.ini)"
    )
    return parser.parse_args()

class PositionWatchdog:
    """A real-time position monitoring system using polling approach"""
    
    def __init__(self, profit_target=None, check_interval=60, price_poll_interval=None):
        self.logger = logging.getLogger()
        
        try:
            self.config = get_config()
            self.logger.info(f"Loaded configuration from {self.config.config_file}")
            
            # API configuration
            self.api_key = self.config.get('API', 'api_key')
            self.logger.info(f"Using API key: {self.api_key}")
            
            # Get access token and log partial value for debugging
            self.access_token = self.config.get('API', 'access_token')
            if self.access_token:
                self.logger.info(f"Access token loaded: {self.access_token[:5]}...{self.access_token[-5:]}")
            else:
                self.logger.error("Access token is empty! Authentication will fail.")
            
            self.exchange = self.config.get('Trading', 'exchange')
            self.product_type = self.config.get('Trading', 'product_type')
            self.logger.info(f"Trading on {self.exchange} with product type {self.product_type}")
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            # Set default values to prevent further errors
            self.api_key = ""
            self.access_token = ""
            self.exchange = "NSE"
            self.product_type = "MIS"
            
        self.data_handler = get_data_handler()
        
        # Risk parameters
        self.profit_target = profit_target or self.config.get_float('Trading', 'profit_target', fallback=10.0)
        self.check_interval = check_interval
        
        # How often to poll prices in seconds
        # - Lower values (1-2 seconds) provide faster reaction time but use more API calls
        # - Higher values (5-10 seconds) use fewer API calls but may miss quick price movements
        # - For liquid stocks, 5 seconds is a good balance
        # - For less liquid stocks or volatile conditions, consider 2-3 seconds
        # - Zerodha has API rate limits, so be careful with values < 1 second
        self.price_poll_interval = price_poll_interval or self.config.get_float('Watchdog', 'price_poll_interval', fallback=5.0)
        
        # Initialize KiteConnect client with better error handling
        try:
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(self.access_token)
            self.logger.info("KiteConnect client initialized successfully")
            
            # Test the connection by retrieving profile
            try:
                profile = self.kite.profile()
                self.logger.info(f"Successfully authenticated as {profile['user_name']} ({profile['user_id']})")
            except Exception as e:
                self.logger.error(f"Failed to authenticate with Zerodha: {e}")
                self.logger.error("Position monitoring will not work! Please check your API credentials.")
        except Exception as e:
            self.logger.error(f"Error initializing KiteConnect client: {e}")
            # Create a dummy instance to prevent attribute errors
            self.kite = KiteConnect(api_key="dummy")
        
        # Position tracking
        self.active_positions = {}  # All current positions from broker
        self.tracked_positions = {}  # Positions we're specifically monitoring
        
        # Stop loss tracking for each position
        self.stop_losses = {}  # ticker -> stop loss price
        self.best_prices = {}  # ticker -> best price seen
        self.current_prices = {}  # ticker -> latest price
        
        # Tick size mapping (default fallback for unknown tickers)
        self.default_tick_size = 0.05
        self.tick_sizes = {
            "CREDITACC": 0.10,
            # Add more specific tick sizes here as needed
        }
        
        # Message queue for order execution
        self.order_queue = Queue()
        
        # Monitoring state
        self.running = False
        self.last_portfolio_check = 0
        self.last_stop_loss_check = 0
        self.last_price_check = 0
        
        # Threads
        self.price_poll_thread = None
        self.order_thread = None
        
        # Subscribe to shutdown signals
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info("Shutdown signal received. Cleaning up...")
        self.stop()
        sys.exit(0)
    
    def fetch_positions(self) -> Tuple[Dict, Dict]:
        """Fetch current positions from broker API, filtering for MIS positions only"""
        try:
            self.logger.info("Fetching current positions from broker (MIS only)")
            positions = self.kite.positions()
            
            # Process into long and short positions
            long_positions = {}
            short_positions = {}
            
            if positions and "net" in positions:
                for position in positions["net"]:
                    # Only process MIS positions
                    if position["product"] != "MIS":
                        continue
                        
                    if position["quantity"] == 0:
                        continue
                    
                    ticker = position["tradingsymbol"]
                    quantity = abs(position["quantity"])
                    purchase_price = abs(position["average_price"])
                    
                    if position["quantity"] > 0:  # Long position
                        long_positions[ticker] = {
                            "quantity": quantity,
                            "purchase_price": purchase_price
                        }
                    else:  # Short position
                        short_positions[ticker] = {
                            "quantity": quantity,
                            "purchase_price": purchase_price
                        }
            
            self.logger.info(f"Found {len(long_positions)} MIS long positions and {len(short_positions)} MIS short positions")
            return long_positions, short_positions
        except Exception as e:
            self.logger.error(f"Error fetching positions: {e}")
            return {}, {}
    
    def poll_prices(self):
        """Poll for latest prices of all tracked positions"""
        try:
            while self.running:
                try:
                    current_time = time.time()
                    # Only poll every price_poll_interval seconds
                    if current_time - self.last_price_check < self.price_poll_interval:
                        time.sleep(0.1)
                        continue
                    
                    self.last_price_check = current_time
                    
                    if not self.tracked_positions:
                        time.sleep(1)
                        continue
                    
                    # Create list of symbols to fetch prices for
                    symbols = [f"{self.exchange}:{ticker}" for ticker in self.tracked_positions.keys()]
                    
                    if not symbols:
                        time.sleep(1)
                        continue
                    
                    # Split into batches of 500 max (API limit)
                    symbols_batches = [symbols[i:i+500] for i in range(0, len(symbols), 500)]
                    
                    self.logger.debug(f"Polling prices for {len(symbols)} instruments")
                    
                    # Process each batch
                    for batch in symbols_batches:
                        try:
                            # Get last traded prices
                            ltp_data = self.kite.ltp(batch)
                            
                            # Process each ticker's price
                            for symbol, data in ltp_data.items():
                                try:
                                    exchange, ticker = symbol.split(":")
                                    
                                    if ticker not in self.tracked_positions:
                                        continue
                                    
                                    price = data.get("last_price")
                                    if not price:
                                        continue
                                    
                                    # Update current price
                                    self.current_prices[ticker] = price
                                    
                                    # Update best price if needed
                                    position_type = self.tracked_positions[ticker]["type"]
                                    current_best = self.best_prices.get(ticker, 0)
                                    
                                    if position_type == "LONG" and (current_best == 0 or price > current_best):
                                        self.best_prices[ticker] = price
                                        self.logger.debug(f"Updated best price for LONG {ticker}: {price}")
                                    elif position_type == "SHORT" and (current_best == 0 or price < current_best):
                                        self.best_prices[ticker] = price
                                        self.logger.debug(f"Updated best price for SHORT {ticker}: {price}")
                                    
                                    # Check stop losses
                                    self.check_stop_loss_for_ticker(ticker, price)
                                    
                                    # Check take profit
                                    self.check_take_profit_for_ticker(ticker, price)
                                    
                                except Exception as e:
                                    self.logger.error(f"Error processing price for {ticker}: {e}")
                        except Exception as e:
                            self.logger.error(f"Error fetching batch of prices: {e}")
                            time.sleep(5)  # Backoff on error
                
                except Exception as e:
                    self.logger.error(f"Error in price polling loop: {e}")
                    time.sleep(5)  # Backoff on error
                
                time.sleep(0.1)  # Small sleep to prevent CPU hogging
                
        except Exception as e:
            self.logger.error(f"Fatal error in price polling thread: {e}")
    
    def check_stop_loss_for_ticker(self, ticker, price):
        """Check if stop loss is hit for a specific ticker"""
        if ticker not in self.stop_losses:
            return
            
        # Check if this position already has a pending order
        if self.tracked_positions[ticker].get("has_pending_order", False):
            self.logger.debug(f"Skipping SL check for {ticker} as it already has a pending order")
            return
            
        stop_loss = self.stop_losses[ticker]
        position_type = self.tracked_positions[ticker]["type"]
        
        # Add detailed logging for stop loss checks
        self.logger.info(f"SL Check - {ticker}: Current Price: {price}, Stop Loss: {stop_loss}, Position Type: {position_type}")
        
        # For LONG positions
        if position_type == "LONG":
            # Log comparison details
            sl_triggered = price <= stop_loss
            self.logger.info(f"LONG {ticker}: Price {price} <= Stop Loss {stop_loss}? {sl_triggered}")
            
            if sl_triggered:
                # Get appropriate tick size for this ticker
                tick_size = self.tick_sizes.get(ticker, self.default_tick_size)
                # Calculate order price as a multiple of tick size
                order_price = round((stop_loss * 0.995) / tick_size) * tick_size
                self.logger.info(f"LONG {ticker}: Price {price} crossed stop loss {stop_loss}. Queuing SELL order at {order_price}.")
                self.queue_order(ticker, self.tracked_positions[ticker]["quantity"], "SELL", "Stop-loss triggered", order_price)
        
        # For SHORT positions
        elif position_type == "SHORT":
            # Log comparison details
            sl_triggered = price >= stop_loss
            self.logger.info(f"SHORT {ticker}: Price {price} >= Stop Loss {stop_loss}? {sl_triggered}")
            
            if sl_triggered:
                # Get appropriate tick size for this ticker
                tick_size = self.tick_sizes.get(ticker, self.default_tick_size)
                # Calculate order price as a multiple of tick size
                order_price = round((stop_loss * 1.005) / tick_size) * tick_size
                self.logger.info(f"SHORT {ticker}: Price {price} crossed stop loss {stop_loss}. Queuing BUY order at {order_price}.")
                self.queue_order(ticker, self.tracked_positions[ticker]["quantity"], "BUY", "Stop-loss triggered", order_price)
    
    def check_take_profit_for_ticker(self, ticker, price):
        """Check if take profit is hit for a specific ticker"""
        if ticker not in self.tracked_positions:
            return
            
        # Check if this position already has a pending order
        if self.tracked_positions[ticker].get("has_pending_order", False):
            self.logger.debug(f"Skipping TP check for {ticker} as it already has a pending order")
            return
            
        position_type = self.tracked_positions[ticker]["type"]
        entry_price = self.tracked_positions[ticker]["entry_price"]
        
        # For LONG positions
        if position_type == "LONG":
            profit_pct = ((price - entry_price) / entry_price) * 100
            if profit_pct >= self.profit_target:
                # Get appropriate tick size for this ticker
                tick_size = self.tick_sizes.get(ticker, self.default_tick_size)
                # Calculate order price as a multiple of tick size
                order_price = round((price * 0.995) / tick_size) * tick_size
                self.logger.info(f"LONG {ticker}: Take profit target reached. Current: {price}, Entry: {entry_price}, Profit: {profit_pct:.2f}%. Queuing SELL order at {order_price}.")
                self.queue_order(ticker, self.tracked_positions[ticker]["quantity"], "SELL", "Take-profit triggered", order_price)
        
        # For SHORT positions
        elif position_type == "SHORT":
            profit_pct = ((entry_price - price) / entry_price) * 100
            if profit_pct >= self.profit_target:
                # Get appropriate tick size for this ticker
                tick_size = self.tick_sizes.get(ticker, self.default_tick_size)
                # Calculate order price as a multiple of tick size
                order_price = round((price * 1.005) / tick_size) * tick_size
                self.logger.info(f"SHORT {ticker}: Take profit target reached. Current: {price}, Entry: {entry_price}, Profit: {profit_pct:.2f}%. Queuing BUY order at {order_price}.")
                self.queue_order(ticker, self.tracked_positions[ticker]["quantity"], "BUY", "Take-profit triggered", order_price)
    
    def refresh_stop_losses(self):
        """Recalculate stop losses for all positions"""
        self.logger.info("Refreshing stop losses for all positions")
        
        for ticker, position in self.tracked_positions.items():
            try:
                # Get the previous candle
                prev_candle = self.get_previous_candle(ticker)
                
                if prev_candle is None:
                    self.logger.warning(f"Could not get previous candle for {ticker}. Skipping stop-loss update.")
                    continue
                
                position_type = position["type"]
                current_price = self.kite.ltp([f"{self.exchange}:{ticker}"])[f"{self.exchange}:{ticker}"]["last_price"]
                
                if position_type == "LONG":
                    # For long positions, use the previous candle's low as stop-loss
                    prev_low = prev_candle["low"]
                    self.logger.debug(f"LONG {ticker}: Previous candle low: {prev_low}, high: {prev_candle['high']}, open: {prev_candle['open']}, close: {prev_candle['close']}")
                    stop_loss = prev_low
                    
                    # If the best price is higher than current price, also consider a trailing stop
                    best_price = self.best_prices.get(ticker, 0)
                    if best_price > current_price and best_price > 0:
                        best_price_stop = best_price * 0.98  # 2% below best price as safety
                        # Use the higher of the two stops (more conservative)
                        stop_loss = max(stop_loss, best_price_stop)
                    
                    # First check global highest stop loss to maintain value across position resets
                    # This prevents stop loss from ever decreasing for a ticker even after a reset
                    global_key = f"global_highest_sl_{ticker}"
                    global_highest_sl = self.data_handler.get_state_value(global_key, 0)
                    
                    # Then get current position-specific stop loss
                    old_stop = self.stop_losses.get(ticker, 0)
                    
                    # Never let stop loss decrease
                    final_stop_loss = max(stop_loss, old_stop, global_highest_sl)
                    
                    if old_stop == 0 or final_stop_loss > old_stop:
                        self.logger.info(f"LONG {ticker}: Updated stop loss from {old_stop} to {final_stop_loss} (candle low: {prev_low})")
                        self.stop_losses[ticker] = final_stop_loss
                        
                        # Save highest value to persist across restarts/resets
                        if final_stop_loss > global_highest_sl:
                            self.data_handler.set_state_value(global_key, final_stop_loss)
                    else:
                        self.logger.info(f"LONG {ticker}: Keeping current stop loss at {old_stop} (new calculated: {stop_loss}, candle low: {prev_low})")
                else:  # SHORT
                    # For short positions, use the previous candle's high as stop-loss
                    prev_high = prev_candle["high"]
                    self.logger.debug(f"SHORT {ticker}: Previous candle high: {prev_high}, low: {prev_candle['low']}, open: {prev_candle['open']}, close: {prev_candle['close']}")
                    stop_loss = prev_high
                    
                    # If the best price is lower than current price, also consider a trailing stop
                    best_price = self.best_prices.get(ticker, float('inf'))
                    if best_price < current_price and best_price < float('inf'):
                        best_price_stop = best_price * 1.02  # 2% above best price as safety
                        # Use the lower of the two stops (more conservative)
                        stop_loss = min(stop_loss, best_price_stop)
                    
                    # First check global lowest stop loss to maintain value across position resets
                    # This prevents stop loss from ever increasing for a ticker even after a reset
                    global_key = f"global_lowest_sl_{ticker}"
                    global_lowest_sl = self.data_handler.get_state_value(global_key, float('inf'))
                    
                    # Then get current position-specific stop loss
                    old_stop = self.stop_losses.get(ticker, float('inf'))
                    
                    # Never let stop loss increase
                    final_stop_loss = min(
                        stop_loss if stop_loss != float('inf') else old_stop,
                        old_stop if old_stop != float('inf') else stop_loss,
                        global_lowest_sl if global_lowest_sl != float('inf') else stop_loss
                    )
                    
                    if old_stop == float('inf') or final_stop_loss < old_stop:
                        self.logger.info(f"SHORT {ticker}: Updated stop loss from {old_stop if old_stop != float('inf') else 'None'} to {final_stop_loss} (candle high: {prev_high})")
                        self.stop_losses[ticker] = final_stop_loss
                        
                        # Save lowest value to persist across restarts/resets
                        if final_stop_loss < global_lowest_sl or global_lowest_sl == float('inf'):
                            self.data_handler.set_state_value(global_key, final_stop_loss)
                    else:
                        self.logger.info(f"SHORT {ticker}: Keeping current stop loss at {old_stop} (new calculated: {stop_loss}, candle high: {prev_high})")
            except Exception as e:
                self.logger.error(f"Error refreshing stop loss for {ticker}: {e}")
    
    def get_previous_candle(self, ticker, interval="60minute"):
        """Get the previous completed candle for a ticker"""
        try:
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
                
            candles = self.kite.historical_data(token, start_date, end_date, interval)
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
            self.logger.error(f"Error getting previous candle for {ticker}: {e}")
            return None
    
    def check_new_positions(self):
        """Check for new positions and update tracking"""
        try:
            current_time = time.time()
            # Only check every check_interval seconds
            if current_time - self.last_portfolio_check < self.check_interval:
                return
                
            self.logger.info("Checking for portfolio position updates")
            self.last_portfolio_check = current_time
            
            # Fetch positions from broker
            long_positions, short_positions = self.fetch_positions()
            
            # Update active positions
            self.active_positions = {**long_positions, **short_positions}
            
            # Create a set of all current tickers
            current_tickers = set(list(long_positions.keys()) + list(short_positions.keys()))
            
            # Filter out problematic tickers
            # These tickers have issues with GTT order deletion through the KiteConnect library
            # They require direct API access to delete GTT orders via https://api.kite.trade/gtt/triggers/{trigger_id}
            problematic_tickers = ["BIRLACORPN", "BIRLACORP", "RAYMOND", "SANOFI", "POKARNA", "CGPOWER", 
                                "SAMMAANCAP", "TFCILTD", "RADIANTCMS", "KANSAINER"]
                                
            for ticker in problematic_tickers:
                if ticker in current_tickers:
                    self.logger.warning(f"Ignoring known problematic ticker: {ticker}")
                    current_tickers.remove(ticker)
                    if ticker in long_positions:
                        del long_positions[ticker]
                    if ticker in short_positions:
                        del short_positions[ticker]
            
            # Get the daily ticker lists to determine the correct position type
            # Import state_manager here to avoid circular imports
            from state_manager import get_state_manager
            state_manager = get_state_manager()
            
            # Get daily ticker lists from the state manager
            daily_tickers = state_manager.get_daily_tickers()
            daily_long_tickers = daily_tickers.get('long', [])
            daily_short_tickers = daily_tickers.get('short', [])
            
            # Clean up daily tickers that don't have actual positions
            # This prevents auto-adding positions that might have been closed elsewhere
            # or should not be actively tracked
            current_tickers_set = set(current_tickers)
            for ticker in list(daily_long_tickers):
                if ticker not in current_tickers_set:
                    # This ticker is in daily_long_tickers but not in broker positions
                    # It should be removed from daily_long_tickers to prevent auto-adding
                    self.logger.warning(f"Removing {ticker} from daily_long_tickers as it's not in broker positions")
                    state_manager.remove_daily_ticker(ticker, "long")
            
            for ticker in list(daily_short_tickers):
                if ticker not in current_tickers_set:
                    # This ticker is in daily_short_tickers but not in broker positions
                    # It should be removed from daily_short_tickers to prevent auto-adding
                    self.logger.warning(f"Removing {ticker} from daily_short_tickers as it's not in broker positions")
                    state_manager.remove_daily_ticker(ticker, "short")
            
            # Re-fetch the daily tickers after cleanup
            daily_tickers = state_manager.get_daily_tickers()
            daily_long_tickers = daily_tickers.get('long', [])
            daily_short_tickers = daily_tickers.get('short', [])
            
            # Track new positions
            for ticker, data in long_positions.items():
                if ticker not in self.tracked_positions:
                    # Track all LONG positions regardless of daily candidates list
                    position_type = "LONG"
                    if ticker in daily_long_tickers:
                        self.logger.info(f"Adding new LONG position for {ticker} (verified as long strategy candidate)")
                    else:
                        self.logger.info(f"Adding new LONG position for {ticker} (not in daily candidates but still tracking)")
                    
                    # Add to daily long tickers if not already there
                    if ticker not in daily_long_tickers:
                        state_manager.add_daily_ticker(ticker, "long")
                        
                    current_price = self.kite.ltp([f"{self.exchange}:{ticker}"])[f"{self.exchange}:{ticker}"]["last_price"]
                    self.tracked_positions[ticker] = {
                        "type": position_type,
                        "quantity": data["quantity"],
                        "entry_price": data["purchase_price"],
                        "current_price": current_price,
                        "start_time": datetime.now().isoformat()
                    }
                    # Initialize best price
                    self.best_prices[ticker] = current_price
                
            for ticker, data in short_positions.items():
                if ticker not in self.tracked_positions:
                    # Track all SHORT positions regardless of daily candidates list
                    position_type = "SHORT"
                    if ticker in daily_short_tickers:
                        self.logger.info(f"Adding new SHORT position for {ticker} (verified as short strategy candidate)")
                    else:
                        self.logger.info(f"Adding new SHORT position for {ticker} (not in daily candidates but still tracking)")
                    
                    # Add to daily short tickers if not already there
                    if ticker not in daily_short_tickers:
                        state_manager.add_daily_ticker(ticker, "short")
                        
                    current_price = self.kite.ltp([f"{self.exchange}:{ticker}"])[f"{self.exchange}:{ticker}"]["last_price"]
                    self.tracked_positions[ticker] = {
                        "type": position_type,
                        "quantity": data["quantity"],
                        "entry_price": data["purchase_price"],
                        "current_price": current_price,
                        "start_time": datetime.now().isoformat()
                    }
                    # Initialize best price
                    self.best_prices[ticker] = current_price
            
            # Remove positions that no longer exist
            for ticker in list(self.tracked_positions.keys()):
                # Check if we should remove this position
                if ticker not in current_tickers:
                    position = self.tracked_positions[ticker]
                    
                    # If position has a pending order, check if it's old enough to clean up
                    if position.get("has_pending_order") and position.get("order_executed"):
                        execution_time = position.get("order_execution_time")
                        if execution_time:
                            try:
                                # Parse the ISO timestamp
                                exec_time = datetime.fromisoformat(execution_time)
                                # Check if it's been more than 5 minutes since execution
                                if (datetime.now() - exec_time).total_seconds() > 300:
                                    self.logger.info(f"Removing {ticker} position after successful order execution (confirmed by broker)")
                                    del self.tracked_positions[ticker]
                                    if ticker in self.stop_losses:
                                        del self.stop_losses[ticker]
                                    if ticker in self.best_prices:
                                        del self.best_prices[ticker]
                                    if ticker in self.current_prices:
                                        del self.current_prices[ticker]
                            except Exception as e:
                                self.logger.error(f"Error parsing execution time for {ticker}: {e}")
                                # If we can't parse the timestamp, just remove it
                                del self.tracked_positions[ticker]
                    else:
                        # No pending order, so directly remove the position
                        self.logger.info(f"Removing closed position for {ticker}")
                        del self.tracked_positions[ticker]
                        if ticker in self.stop_losses:
                            del self.stop_losses[ticker]
                        if ticker in self.best_prices:
                            del self.best_prices[ticker]
                        if ticker in self.current_prices:
                            del self.current_prices[ticker]
            
            # Update quantity for existing positions
            for ticker in self.tracked_positions:
                if ticker in long_positions:
                    self.tracked_positions[ticker]["quantity"] = long_positions[ticker]["quantity"]
                elif ticker in short_positions:
                    self.tracked_positions[ticker]["quantity"] = short_positions[ticker]["quantity"]
            
            # No need to update websocket subscriptions in polling implementation
                
            # After checking positions, update stop losses
            self.refresh_stop_losses()
            
            self.logger.info(f"Now tracking {len(self.tracked_positions)} positions with active monitoring")
            
        except Exception as e:
            self.logger.error(f"Error checking new positions: {e}")
    
    def queue_order(self, ticker, quantity, transaction_type, reason, price=None):
        """Add an order to the queue for execution"""
        order_info = {
            "ticker": ticker,
            "quantity": quantity,
            "transaction_type": transaction_type,
            "reason": reason,
            "price": price,  # Optional price for limit orders
            "timestamp": datetime.now().isoformat(),
            "position_data": self.tracked_positions.get(ticker, {}).copy()  # Save position data in the order
        }
        
        # Check if we should ignore this order
        if ticker not in self.tracked_positions:
            self.logger.warning(f"Ignoring order for {ticker} as it's not in tracked positions")
            return False
        
        # Add to queue for execution
        self.order_queue.put(order_info)
        order_type = "LIMIT" if price else "MARKET"
        price_info = f" at {price}" if price else ""
        self.logger.info(f"Queued {transaction_type} {order_type} order for {ticker} (qty: {quantity}){price_info}: {reason}")
        
        # Flag position as having a pending order to prevent duplicate orders
        # We'll keep it in tracking until the order is executed
        self.tracked_positions[ticker]["has_pending_order"] = True
        self.logger.info(f"Marked {ticker} as having a pending order to prevent duplicates")
            
        return True
    
    def process_order_queue(self):
        """Process queued orders with retry mechanism for rate limit errors"""
        try:
            while self.running:
                try:
                    # Non-blocking wait for order
                    if self.order_queue.empty():
                        time.sleep(0.5)
                        continue
                    
                    order_info = self.order_queue.get(block=False)
                    ticker = order_info["ticker"]
                    
                    # Position might have been removed from tracking by another thread
                    # Use position data saved in the order if needed
                    position_data = order_info.get("position_data", {})
                    if ticker not in self.tracked_positions and not position_data:
                        self.logger.warning(f"Skipping order for {ticker} as it's not in tracked positions and no position data is available")
                        self.order_queue.task_done()
                        continue
                    
                    # Execute the order with retries
                    price = order_info.get("price")
                    order_type = "LIMIT" if price else "MARKET"
                    price_str = f" at {price}" if price else ""
                    
                    self.logger.info(f"Executing {order_info['transaction_type']} {order_type} order for {ticker}{price_str}")
                    
                    max_retries = 5
                    retry_count = 0
                    rate_limit_pause = 2  # seconds
                    backoff_factor = 1.5  # exponential backoff
                    
                    while retry_count <= max_retries:
                        try:
                            # Prepare order parameters
                            order_params = {
                                "variety": "regular",
                                "exchange": self.exchange,
                                "tradingsymbol": ticker,
                                "transaction_type": order_info["transaction_type"],
                                "quantity": order_info["quantity"],
                                "product": self.product_type,
                                "validity": "DAY"
                            }
                            
                            # Set order type and price if applicable
                            if price:
                                order_params["order_type"] = "LIMIT"
                                order_params["price"] = price
                            else:
                                order_params["order_type"] = "MARKET"
                            
                            # Place the order
                            order_id = self.kite.place_order(**order_params)
                            
                            self.logger.info(f"Order placed successfully for {ticker} with ID {order_id}")
                            
                            # Don't immediately remove position after order execution
                            # Just mark it as complete. The check_new_positions will handle removal
                            # when it confirms with the broker that the position no longer exists
                            if ticker in self.tracked_positions:
                                self.logger.info(f"Order executed for {ticker}, waiting for broker confirmation before removal")
                                # Instead of removing, just keep the pending order flag to prevent more orders
                                self.tracked_positions[ticker]["has_pending_order"] = True
                                self.tracked_positions[ticker]["order_executed"] = True
                                self.tracked_positions[ticker]["order_execution_time"] = datetime.now().isoformat()
                            self.logger.info(f"Order execution completed for {ticker}")
                                
                            # Success - break out of retry loop
                            break
                            
                        except Exception as e:
                            error_str = str(e).lower()
                            
                            # Check if this is a duplicate or already-executed order
                            if "order already completed" in error_str or "duplicate order" in error_str:
                                self.logger.warning(f"Order for {ticker} appears to be already executed.")
                                if ticker in self.tracked_positions:
                                    self.logger.info(f"Marking {ticker} as having a completed order, waiting for broker confirmation")
                                    # Instead of removing, just keep the pending order flag to prevent more orders
                                    self.tracked_positions[ticker]["has_pending_order"] = True
                                    self.tracked_positions[ticker]["order_executed"] = True
                                    self.tracked_positions[ticker]["order_execution_time"] = datetime.now().isoformat()
                                break  # No need to retry
                                
                            # Handle rate limit errors specifically
                            elif "rate limit" in error_str or "too many requests" in error_str or "429" in error_str:
                                retry_count += 1
                                wait_time = rate_limit_pause * (backoff_factor ** (retry_count - 1))
                                
                                if retry_count <= max_retries:
                                    self.logger.warning(f"Rate limit hit when placing order for {ticker}. Retry {retry_count}/{max_retries} after {wait_time:.2f}s")
                                    time.sleep(wait_time)
                                else:
                                    self.logger.error(f"Failed to place order for {ticker} after {max_retries} retries due to rate limits")
                                    break
                            
                            # Other errors - retry with a basic backoff
                            else:
                                retry_count += 1
                                wait_time = 1 * (backoff_factor ** (retry_count - 1))
                                
                                if retry_count <= max_retries:
                                    self.logger.warning(f"Error placing order for {ticker}: {e}. Retry {retry_count}/{max_retries} after {wait_time:.2f}s")
                                    time.sleep(wait_time)
                                else:
                                    self.logger.error(f"Failed to place order for {ticker} after {max_retries} retries: {e}")
                                    break
                    
                    self.order_queue.task_done()
                except Exception as e:
                    if not isinstance(e, Exception) or "Empty" not in str(e):
                        self.logger.error(f"Error in order queue processing: {e}")
                    time.sleep(0.5)
        except Exception as e:
            self.logger.error(f"Fatal error in order thread: {e}")
    
    def perform_startup_sync(self):
        """
        Synchronize local position tracking with broker positions on startup
        to prevent tracking positions that no longer exist with the broker
        """
        self.logger.info("Performing broker position synchronization on startup...")
        
        # Import state_manager here to avoid circular imports
        from state_manager import get_state_manager
        state_manager = get_state_manager()
        
        # Fetch current broker positions
        long_positions, short_positions = self.fetch_positions()
        broker_positions = set(list(long_positions.keys()) + list(short_positions.keys()))
        
        # Get positions from state manager
        local_positions = set(state_manager.get_all_positions().keys())
        
        # Find ghost positions (in state but not in broker)
        ghost_positions = local_positions - broker_positions
        
        # Remove ghost positions from state
        for ticker in ghost_positions:
            self.logger.warning(f"Found ghost position for {ticker} - removing from state")
            state_manager.remove_position(ticker)
            
            # Also remove from watchdog tracking
            if ticker in self.tracked_positions:
                del self.tracked_positions[ticker]
            if ticker in self.stop_losses:
                del self.stop_losses[ticker]
            if ticker in self.best_prices:
                del self.best_prices[ticker]
            if ticker in self.current_prices:
                del self.current_prices[ticker]
                
        # Resync daily tickers
        daily_tickers = state_manager.get_daily_tickers()
        daily_long_tickers = set(daily_tickers.get('long', []))
        daily_short_tickers = set(daily_tickers.get('short', []))
        
        # Remove tickers that no longer have positions
        for ticker in list(daily_long_tickers):
            if ticker not in broker_positions:
                self.logger.warning(f"Removing {ticker} from daily_long_tickers as it's not in broker positions")
                state_manager.remove_daily_ticker(ticker, "long")
                
        for ticker in list(daily_short_tickers):
            if ticker not in broker_positions:
                self.logger.warning(f"Removing {ticker} from daily_short_tickers as it's not in broker positions")
                state_manager.remove_daily_ticker(ticker, "short")
                
        self.logger.info(f"Startup sync complete. Removed {len(ghost_positions)} ghost positions.")
        
        # Return number of positions removed for testing purposes
        return len(ghost_positions)
        
    def start(self):
        """Start the watchdog monitoring system"""
        self.logger.info("Starting position watchdog...")
        self.running = True
        
        # Start price polling thread
        self.price_poll_thread = threading.Thread(target=self.poll_prices)
        self.price_poll_thread.daemon = True
        self.price_poll_thread.start()
        self.logger.info(f"Started price polling thread (interval: {self.price_poll_interval}s)")
        
        # Start order processing thread
        self.order_thread = threading.Thread(target=self.process_order_queue)
        self.order_thread.daemon = True
        self.order_thread.start()
        self.logger.info("Started order processing thread")
        
        # Force state reset on startup to prevent tracking ghost positions (positions that no longer exist with broker)
        self.perform_startup_sync()
        
        # Initial position check
        self.check_new_positions()
        
        # Main monitoring loop
        try:
            while self.running:
                self.check_new_positions()
                time.sleep(1)
        except Exception as e:
            self.logger.error(f"Error in main monitoring loop: {e}")
            self.stop()
            return False
        
        return True
    
    def stop(self):
        """Stop the watchdog monitoring system"""
        self.logger.info("Stopping position watchdog...")
        self.running = False
                
        # Wait for threads to complete
        if self.price_poll_thread and self.price_poll_thread.is_alive():
            self.price_poll_thread.join(timeout=5)
        
        if self.order_thread and self.order_thread.is_alive():
            self.order_thread.join(timeout=5)
        
        self.logger.info("Position watchdog stopped")
        return True
    
    def get_status(self):
        """Get the current status of the watchdog"""
        status = {
            "running": self.running,
            "tracked_positions": len(self.tracked_positions),
            "stop_losses": self.stop_losses,
            "best_prices": self.best_prices,
            "current_prices": self.current_prices,
            "pending_orders": self.order_queue.qsize()
        }
        return status
    
    def print_portfolio_summary(self):
        """Print a summary of the current portfolio"""
        self.logger.info("=== Portfolio Summary ===")
        
        total_value = 0
        total_cost = 0
        
        # Process positions
        for ticker, position in self.tracked_positions.items():
            position_type = position["type"]
            qty = position["quantity"]
            purchase_price = position["entry_price"]
            
            # Get current price (from ticker or LTP API)
            try:
                current_price = self.kite.ltp([f"{self.exchange}:{ticker}"])[f"{self.exchange}:{ticker}"]["last_price"]
            except Exception:
                current_price = purchase_price  # Fallback
            
            if position_type == "LONG":
                position_value = current_price * qty
                position_cost = purchase_price * qty
                position_profit = (current_price - purchase_price) * qty
                profit_pct = ((current_price - purchase_price) / purchase_price) * 100
                
                total_value += position_value
                total_cost += position_cost
                
                self.logger.info(f"LONG {ticker}: {qty} shares, Entry: {purchase_price}, Current: {current_price}, " +
                               f"P/L: {position_profit:.2f} ({profit_pct:.2f}%), SL: {self.stop_losses.get(ticker, 'None')}")
            else:  # SHORT
                position_value = current_price * qty
                position_cost = purchase_price * qty
                position_profit = (purchase_price - current_price) * qty
                profit_pct = ((purchase_price - current_price) / purchase_price) * 100
                
                total_value += position_value
                total_cost += position_cost
                
                self.logger.info(f"SHORT {ticker}: {qty} shares, Entry: {purchase_price}, Current: {current_price}, " +
                               f"P/L: {position_profit:.2f} ({profit_pct:.2f}%), SL: {self.stop_losses.get(ticker, 'None')}")
        
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
    logger.info(f"===== Position Watchdog Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    
    # Get configuration and verify product type
    config = get_config()
    product_type = config.get('Trading', 'product_type')
    
    if product_type != "MIS":
        logger.error(f"This utility can only operate on MIS product type, but found {product_type}")
        logger.error("For CNC (delivery) orders, use the scripts in the Daily folder")
        return
        
    logger.info(f"Operating on {product_type} product type only")
    
    # Create watchdog instance
    watchdog = PositionWatchdog(
        profit_target=args.profit_target,
        check_interval=args.check_interval,
        price_poll_interval=args.poll_interval
    )
    
    # Start the watchdog
    try:
        watchdog.start()
        
        # Keep the main thread alive
        while True:
            try:
                # Print summary every 5 minutes
                watchdog.print_portfolio_summary()
                time.sleep(300)
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(10)
    except KeyboardInterrupt:
        logger.info("User requested shutdown")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        # Ensure proper cleanup
        watchdog.stop()
        logger.info(f"===== Position Watchdog Stopped at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")

if __name__ == "__main__":
    main()