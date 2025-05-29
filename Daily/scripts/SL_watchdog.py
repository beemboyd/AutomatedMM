#!/usr/bin/env python

import os
import sys
import json
import time
import logging
import argparse
import threading
import signal
import configparser
import glob
import pandas as pd
from datetime import datetime, timedelta
import pytz
from queue import Queue
from typing import Dict, List, Tuple, Optional

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import trading system modules
from kiteconnect import KiteConnect
from user_context_manager import (
    get_context_manager,
    get_user_data_handler,
    UserCredentials
)

def load_daily_config():
    """Load configuration from Daily/config.ini file"""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini file not found at {config_path}")
    
    config.read(config_path)
    return config

def get_user_from_config(user_name: str, config):
    """Get user credentials from config"""
    section = f'API_CREDENTIALS_{user_name}'
    if section not in config.sections():
        return None

    api_key = config.get(section, 'api_key', fallback='')
    api_secret = config.get(section, 'api_secret', fallback='')
    access_token = config.get(section, 'access_token', fallback='')

    if not (api_key and api_secret and access_token):
        return None

    return UserCredentials(
        name=user_name,
        api_key=api_key,
        api_secret=api_secret,
        access_token=access_token
    )

def setup_logging(user_name: str):
    """Set up logging with user-specific log files"""
    # Create user-specific log directory
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', user_name)
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'SL_watchdog_{user_name}.log')
    
    # Configure logging
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ],
        force=True  # Force reconfiguration
    )
    
    logger = logging.getLogger()
    logger.info(f"Logging initialized for user {user_name}")
    
    return logger

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="ATR-based stop loss watchdog for CNC positions")
    parser.add_argument(
        "orders_file",
        nargs='?',  # Make orders file optional
        help="Path to the orders JSON file to monitor (optional - will monitor all CNC positions if not provided)"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Increase output verbosity"
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=45.0,
        help="Interval in seconds to poll prices (default: 45.0)"
    )
    return parser.parse_args()

class SLWatchdog:
    """
    ATR-based trailing stop loss position monitoring system.

    ATR-Based Logic: Uses 20-day ATR on daily timeframe to set trailing stop losses:
    - Low Volatility (ATR <2%): Stop = 1.0x ATR
    - Medium Volatility (ATR 2-4%): Stop = 1.5x ATR
    - High Volatility (ATR >4%): Stop = 2.0x ATR

    True Trailing Stop Loss: Stop losses trail upward based on daily high prices, but never move downward.
    The system uses each day's official high price from market data to recalculate the stop loss,
    ensuring profits are protected while still giving room based on volatility.
    """

    def __init__(self, user_credentials: UserCredentials, config, orders_file: str = None, price_poll_interval: float = 5.0):
        self.logger = logging.getLogger()
        self.orders_file = orders_file
        self.user_name = user_credentials.name
        self.price_poll_interval = price_poll_interval
        self.config = config

        # Set up user context for this watchdog
        context_manager = get_context_manager()
        context_manager.set_current_user(user_credentials.name, user_credentials)

        # API configuration
        self.api_key = user_credentials.api_key
        self.api_secret = user_credentials.api_secret
        self.access_token = user_credentials.access_token
        self.exchange = config.get('DEFAULT', 'exchange', fallback='NSE')
        self.product_type = config.get('DEFAULT', 'product_type', fallback='CNC')

        # Initialize KiteConnect client
        try:
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(self.access_token)
            self.logger.info("KiteConnect client initialized successfully")

            # Test the connection
            try:
                profile = self.kite.profile()
                self.logger.info(f"Successfully authenticated as {profile['user_name']} ({profile['user_id']})")
            except Exception as e:
                self.logger.error(f"Failed to authenticate with Zerodha: {e}")
                raise
        except Exception as e:
            self.logger.error(f"Error initializing KiteConnect client: {e}")
            raise

        # Initialize user-specific data handler
        self.data_handler = get_user_data_handler()

        # Initialize instruments data for token lookups
        try:
            self.logger.info("Initializing instruments data from exchange")
            self.data_handler.initialize_instruments()
            self.logger.info(f"Initialized {len(self.data_handler.get_all_instruments())} instruments successfully")
        except Exception as e:
            self.logger.warning(f"Could not initialize instruments data: {e}. Will initialize later.")

        # Position tracking
        self.tracked_positions = {}  # Positions we're monitoring from orders file
        self.current_prices = {}  # ticker -> latest price
        self.daily_high_prices = {}  # ticker -> day's highest price (from market data)
        self.atr_data = {}  # ticker -> {'atr': value, 'atr_percentage': value, 'stop_loss': value, 'multiplier': value}

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
        self.last_price_check = 0
        self.last_atr_check = 0

        # Threads
        self.price_poll_thread = None
        self.order_thread = None

        # Subscribe to shutdown signals
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        # Log the ATR-based stop loss logic being used
        self.logger.info("=" * 60)
        self.logger.info("ATR-BASED TRAILING STOP LOSS ENABLED")
        self.logger.info("Stop loss calculation based on 20-day ATR:")
        self.logger.info("- Low Volatility (ATR <2%): Stop = 1.0x ATR")
        self.logger.info("- Medium Volatility (ATR 2-4%): Stop = 1.5x ATR")
        self.logger.info("- High Volatility (ATR >4%): Stop = 2.0x ATR")
        self.logger.info("TRUE TRAILING STOP FEATURE: Stop losses automatically rise as prices reach new highs")
        self.logger.info("- Trailing stops only move upward, never downward")
        self.logger.info("- Stop losses recalculated based on highest price reached")
        self.logger.info("- Profits are protected while still allowing for volatility")
        self.logger.info("=" * 60)
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info("Shutdown signal received. Cleaning up...")
        self.stop()
        sys.exit(0)

    def is_market_closed(self):
        """Check if market is closed (after 3:30 PM IST)"""
        try:
            # Get current time in IST
            ist = pytz.timezone('Asia/Kolkata')
            current_time = datetime.now(ist)

            # Check if it's a weekday (Monday = 0, Sunday = 6)
            if current_time.weekday() >= 5:  # Saturday or Sunday
                return True

            # Market close time: 3:30 PM IST
            market_close = current_time.replace(hour=15, minute=30, second=0, microsecond=0)

            if current_time >= market_close:
                return True

            return False
        except Exception as e:
            self.logger.error(f"Error checking market hours: {e}")
            return False

    def load_cnc_positions_from_zerodha(self):
        """Load all CNC positions directly from Zerodha account (both positions and holdings)"""
        try:
            self.logger.info(f"Fetching all CNC positions from Zerodha account for user: {self.user_name}")

            # Verify we're connected to the right account
            try:
                profile = self.kite.profile()
                self.logger.info(f"Connected to Zerodha account: {profile['user_name']} (ID: {profile['user_id']})")
            except Exception as e:
                self.logger.error(f"Failed to verify Zerodha account connection: {e}")
                return 0

            # Get all positions from Zerodha
            positions = self.kite.positions()

            # Log raw position data for debugging
            self.logger.debug(f"Raw positions response: {len(positions.get('net', []))} net positions, {len(positions.get('day', []))} day positions")

            # Filter for CNC positions with non-zero quantities
            cnc_positions = []
            all_positions_debug = []

            for position in positions['net']:
                ticker = position.get('tradingsymbol', '')
                product = position.get('product', '')
                quantity = int(position.get('quantity', 0))

                # Log all positions for debugging
                all_positions_debug.append(f"{ticker}({product}:{quantity})")

                if (product == 'CNC' and quantity != 0 and ticker != ''):
                    cnc_positions.append(position)
                    self.logger.debug(f"CNC Position found: {ticker} - {quantity} shares, Product: {product}")

            self.logger.info(f"All positions in account: {', '.join(all_positions_debug[:10])}{'...' if len(all_positions_debug) > 10 else ''}")
            self.logger.info(f"Found {len(cnc_positions)} CNC positions from positions API")

            # Also get holdings (CNC positions carried overnight)
            try:
                holdings = self.kite.holdings()
                self.logger.info(f"Found {len(holdings)} holdings from holdings API")

                holdings_count = 0
                existing_tickers = {pos['tradingsymbol'] for pos in cnc_positions}

                for holding in holdings:
                    ticker = holding.get('tradingsymbol', '')
                    quantity = int(holding.get('quantity', 0))

                    if quantity > 0 and ticker != '' and ticker not in existing_tickers:
                        # Convert holding to position-like format
                        holding_as_position = {
                            'tradingsymbol': ticker,
                            'product': 'CNC',  # Holdings are always CNC
                            'quantity': quantity,
                            'average_price': holding.get('average_price', 0),
                            'last_price': holding.get('last_price', 0),
                            'pnl': holding.get('pnl', 0),
                            'exchange': holding.get('exchange', 'NSE'),
                            'instrument_token': holding.get('instrument_token', 0),
                            'unrealised': holding.get('day_change', 0) * quantity,
                            'realised': 0
                        }
                        cnc_positions.append(holding_as_position)
                        holdings_count += 1
                        self.logger.debug(f"CNC Holding found: {ticker} - {quantity} shares")
                    elif ticker in existing_tickers:
                        self.logger.debug(f"Skipping duplicate ticker {ticker} from holdings (already in positions)")
                    elif quantity <= 0:
                        self.logger.debug(f"Skipping {ticker} from holdings: quantity is {quantity}")

                self.logger.info(f"Added {holdings_count} holdings as CNC positions")

            except Exception as e:
                self.logger.warning(f"Could not fetch holdings: {e}")

            total_cnc_positions = len(cnc_positions)
            self.logger.info(f"Total CNC positions found: {total_cnc_positions} (positions + holdings)")

            if total_cnc_positions == 0:
                self.logger.warning("No CNC positions found in account")
                return 0

            # Create tracked positions from CNC positions
            for position in cnc_positions:
                ticker = position['tradingsymbol']
                quantity = int(position['quantity'])

                # Skip if quantity is 0 or negative (sold positions or short positions)
                if quantity <= 0:
                    self.logger.debug(f"Skipping {ticker}: quantity is {quantity} (no position or sold)")
                    continue

                # Calculate entry price (average price if available, else last price)
                entry_price = float(position.get('average_price', 0))
                if entry_price <= 0:
                    # If no average price, get current price as fallback
                    try:
                        ltp_data = self.kite.ltp(f"{self.exchange}:{ticker}")
                        entry_price = ltp_data[f"{self.exchange}:{ticker}"]["last_price"]
                    except Exception as e:
                        self.logger.warning(f"Could not get price for {ticker}: {e}")
                        entry_price = float(position.get('last_price', 100))  # Fallback

                # Calculate investment amount
                investment_amount = entry_price * quantity

                self.tracked_positions[ticker] = {
                    "type": "LONG",  # All remaining positions are LONG
                    "quantity": quantity,
                    "entry_price": entry_price,
                    "investment_amount": investment_amount,
                    "product": position['product'],
                    "exchange": position['exchange'],
                    "instrument_token": position['instrument_token'],
                    "pnl": float(position.get('pnl', 0)),
                    "unrealised": float(position.get('unrealised', 0)),
                    "realised": float(position.get('realised', 0)),
                    "has_pending_order": False,
                    "zerodha_position": True  # Flag to indicate this came from Zerodha
                }

                self.logger.info(f"Tracking CNC position - {ticker}: {quantity} shares @ ₹{entry_price:.2f}")
                self.logger.info(f"  Investment: ₹{investment_amount:.2f}, Current P&L: ₹{float(position.get('pnl', 0)):.2f}")

            return len(self.tracked_positions)

        except Exception as e:
            self.logger.error(f"Error loading CNC positions from Zerodha: {e}")
            return 0

    def load_positions_from_orders_file(self):
        """Load positions from the orders JSON file (fallback method)"""
        try:
            with open(self.orders_file, 'r') as f:
                orders_data = json.load(f)

            self.logger.info(f"Loading positions from orders file: {self.orders_file}")

            # Extract all orders (both successful orders and synced positions)
            orders = orders_data.get('orders', [])

            # Filter for valid orders: either successful orders or synced positions with BUY transaction
            valid_orders = []
            for order in orders:
                if order.get('order_success', False):
                    # Regular successful order
                    valid_orders.append(order)
                elif (order.get('data_source') == 'server_sync' and
                      order.get('status') == 'COMPLETE' and
                      order.get('transaction_type') == 'BUY' and
                      order.get('filled_quantity', 0) > 0):
                    # Synced BUY position from server
                    valid_orders.append(order)

            self.logger.info(f"Found {len(valid_orders)} valid orders/positions to monitor")

            # Create tracked positions from valid orders
            for order in valid_orders:
                # Handle both order formats
                if 'ticker' in order:
                    # Standard order format
                    ticker = order['ticker']
                    quantity = order['position_size']
                    entry_price = order['current_price']
                    stop_loss = order.get('stop_loss', 0)
                    target_price = order.get('target_price', 0)
                    investment_amount = order['investment_amount']
                    order_timestamp = order['order_timestamp']
                else:
                    # Synced order format
                    ticker = order['tradingsymbol']
                    quantity = order['filled_quantity']
                    entry_price = order['average_price']
                    stop_loss = 0  # No stop loss info in synced orders
                    target_price = 0  # No target info in synced orders
                    investment_amount = entry_price * quantity
                    order_timestamp = order['order_timestamp']

                # Skip if ticker already exists (avoid duplicates)
                if ticker in self.tracked_positions:
                    self.logger.debug(f"Skipping duplicate ticker {ticker} from orders file")
                    continue

                self.tracked_positions[ticker] = {
                    "type": "LONG",  # All CNC orders are assumed to be LONG positions
                    "quantity": quantity,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "target_price": target_price,
                    "risk_reward_ratio": order.get('risk_reward_ratio', 0),
                    "investment_amount": investment_amount,
                    "order_timestamp": order_timestamp,
                    "brooks_entry_price": order.get('brooks_entry_price', 0),
                    "has_pending_order": False,
                    "zerodha_position": False  # Flag to indicate this came from orders file
                }

                self.logger.info(f"Tracking {ticker}: {quantity} shares @ ₹{entry_price:.2f}")
                if stop_loss > 0:
                    self.logger.info(f"  Original SL: ₹{stop_loss:.2f}, Target: ₹{target_price:.2f}")
                else:
                    self.logger.info(f"  Synced position - no original SL/Target info")

            return len(self.tracked_positions)

        except Exception as e:
            self.logger.error(f"Error loading positions from orders file: {e}")
            return 0

    def fetch_daily_high(self, ticker) -> Optional[float]:
        """Fetch the daily high price for a ticker from market data"""
        try:
            token = self.data_handler.get_instrument_token(ticker)
            if token is None:
                self.logger.error(f"Token not found for {ticker}. Cannot fetch daily high.")
                return None

            # Get today's data
            end_date = datetime.now()
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)  # Start of today

            daily_data = self.kite.historical_data(token, start_date, end_date, "day")

            if not daily_data:
                # If no data for today yet, try to get yesterday's data
                yesterday = end_date - timedelta(days=1)
                yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
                daily_data = self.kite.historical_data(token, yesterday_start, end_date, "day")

                if not daily_data:
                    self.logger.warning(f"No recent daily data available for {ticker}")
                    return None

            # Get the most recent day's high
            most_recent = daily_data[-1]
            high_price = most_recent['high']

            self.logger.debug(f"Fetched daily high for {ticker}: ₹{high_price:.2f} (date: {most_recent['date']})")
            return high_price

        except Exception as e:
            self.logger.error(f"Error fetching daily high for {ticker}: {e}")
            return None

    def calculate_atr_and_stop_loss(self, ticker) -> Optional[Dict]:
        """Calculate 20-day ATR and determine appropriate stop loss based on volatility"""
        try:
            token = self.data_handler.get_instrument_token(ticker)
            if token is None:
                self.logger.error(f"Token not found for {ticker}. Cannot calculate ATR.")
                return None

            # Get 30 days of daily data to ensure we have enough for 20-day ATR
            end_date = datetime.now()
            start_date = end_date - timedelta(days=45)  # Get extra days to account for weekends/holidays

            daily_data = self.kite.historical_data(token, start_date, end_date, "day")

            if len(daily_data) < 21:  # Need at least 21 days for 20-day ATR
                self.logger.warning(f"Insufficient daily data for {ticker}. Only {len(daily_data)} days available.")
                return None

            # Convert to pandas DataFrame for easier calculation
            df = pd.DataFrame(daily_data)

            # Calculate True Range (TR)
            df['prev_close'] = df['close'].shift(1)
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = (df['high'] - df['prev_close']).abs()
            df['tr3'] = (df['low'] - df['prev_close']).abs()
            df['TR'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

            # Calculate 20-day ATR
            df['ATR'] = df['TR'].rolling(window=20).mean()

            # Get the latest values
            latest_close = df['close'].iloc[-1]
            latest_atr = df['ATR'].iloc[-1]

            if pd.isna(latest_atr) or latest_atr <= 0:
                self.logger.warning(f"Invalid ATR value for {ticker}: {latest_atr}")
                return None

            # Calculate ATR as percentage of price
            atr_percentage = (latest_atr / latest_close) * 100

            # Determine volatility category and multiplier
            if atr_percentage < 2.0:
                # Low volatility
                multiplier = 1.0
                volatility_category = "Low"
            elif atr_percentage <= 4.0:
                # Medium volatility
                multiplier = 1.5
                volatility_category = "Medium"
            else:
                # High volatility
                multiplier = 2.0
                volatility_category = "High"

            # Calculate trailing stop loss based on position type
            stop_loss_distance = latest_atr * multiplier

            # All positions are LONG now
            stop_loss_price = latest_close - stop_loss_distance

            result = {
                'atr': latest_atr,
                'atr_percentage': atr_percentage,
                'current_price': latest_close,
                'stop_loss': stop_loss_price,
                'multiplier': multiplier,
                'volatility_category': volatility_category,
                'stop_loss_distance': stop_loss_distance
            }

            self.logger.debug(f"{ticker}: ATR={latest_atr:.2f} ({atr_percentage:.2f}%), "
                            f"{volatility_category} volatility, Multiplier={multiplier}x, "
                            f"Stop Loss={stop_loss_price:.2f}")

            return result

        except Exception as e:
            self.logger.error(f"Error calculating ATR for {ticker}: {e}")
            return None
    
    def update_atr_stop_losses(self):
        """Update ATR-based stop losses for all tracked positions (daily basis)"""
        try:
            current_time = time.time()
            # Only update ATR data once per day (24 hours = 86400 seconds) or on first run
            if current_time - self.last_atr_check < 86400 and self.atr_data:  # 24 hours
                return

            self.last_atr_check = current_time
            self.logger.info("Updating ATR-based stop losses for all positions (Daily Update)")

            # Initialize instruments data for faster batch lookups
            try:
                self.logger.info("Fetching instruments data from exchange")
                self.data_handler.initialize_instruments()
                self.logger.info(f"Fetched {len(self.data_handler.get_all_instruments())} instruments successfully")
            except Exception as e:
                self.logger.error(f"Error initializing instruments data: {e}")

            for ticker in self.tracked_positions.keys():
                try:
                    # First calculate ATR
                    atr_result = self.calculate_atr_and_stop_loss(ticker)
                    if not atr_result:
                        self.logger.warning(f"Could not calculate ATR data for {ticker}")
                        continue

                    # Then fetch daily high
                    daily_high = self.fetch_daily_high(ticker)
                    if daily_high:
                        # Store daily high
                        self.daily_high_prices[ticker] = daily_high

                        # Calculate stop loss based on ATR and daily high
                        atr_value = atr_result['atr']
                        multiplier = atr_result['multiplier']
                        volatility_category = atr_result['volatility_category']
                        atr_percentage = atr_result['atr_percentage']

                        old_data = self.atr_data.get(ticker, {})
                        old_stop_loss = old_data.get('stop_loss', 0)

                        # Calculate new stop loss from daily high
                        new_stop_loss = daily_high - (atr_value * multiplier)

                        # Update the ATR data with the new stop loss
                        atr_result['stop_loss'] = new_stop_loss
                        atr_result['daily_high'] = daily_high
                        self.atr_data[ticker] = atr_result

                        # Log the update with daily high information
                        self.logger.info(f"{ticker}: ATR Stop Loss Updated - "
                                       f"ATR: ₹{atr_value:.2f} ({atr_percentage:.2f}%), "
                                       f"{volatility_category} Volatility, "
                                       f"Multiplier: {multiplier}x, "
                                       f"Daily High: ₹{daily_high:.2f}, "
                                       f"Stop Loss: ₹{new_stop_loss:.2f} (was ₹{old_stop_loss:.2f})")
                    else:
                        # If we couldn't get daily high, just use regular ATR stop
                        self.atr_data[ticker] = atr_result
                        new_stop_loss = atr_result['stop_loss']
                        old_stop_loss = old_data.get('stop_loss', 0)

                        self.logger.info(f"{ticker}: ATR Stop Loss Updated (no daily high) - "
                                       f"ATR: ₹{atr_result['atr']:.2f} ({atr_result['atr_percentage']:.2f}%), "
                                       f"{atr_result['volatility_category']} Volatility, "
                                       f"Multiplier: {atr_result['multiplier']}x, "
                                       f"Stop Loss: ₹{new_stop_loss:.2f} (was ₹{old_stop_loss:.2f})")

                except Exception as e:
                    self.logger.error(f"Error updating ATR stop loss for {ticker}: {e}")

            time.sleep(0.5)  # Small delay between API calls

        except Exception as e:
            self.logger.error(f"Error updating ATR stop losses: {e}")
    
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

                                    # Update daily high if current price is higher
                                    if ticker in self.daily_high_prices and price > self.daily_high_prices[ticker]:
                                        old_high = self.daily_high_prices[ticker]
                                        self.daily_high_prices[ticker] = price
                                        self.logger.debug(f"{ticker}: Updated daily high: ₹{price:.2f} (was: ₹{old_high:.2f})")

                                    # Check ATR-based stop loss
                                    self.check_atr_stop_loss(ticker, price)
                                    
                                except Exception as e:
                                    self.logger.error(f"Error processing price for {symbol}: {e}")
                        except Exception as e:
                            self.logger.error(f"Error fetching batch of prices: {e}")
                            time.sleep(5)  # Backoff on error
                
                except Exception as e:
                    self.logger.error(f"Error in price polling loop: {e}")
                    time.sleep(5)  # Backoff on error
                
                time.sleep(0.1)  # Small sleep to prevent CPU hogging
                
        except Exception as e:
            self.logger.error(f"Fatal error in price polling thread: {e}")
    
    def check_atr_stop_loss(self, ticker, current_price):
        """Check if current price is below ATR-based trailing stop loss with partial exits"""
        if ticker not in self.atr_data:
            return

        # Check if this position already has a pending order
        if self.tracked_positions[ticker].get("has_pending_order", False):
            self.logger.debug(f"Skipping ATR stop loss check for {ticker} as it already has a pending order")
            return

        # Get ATR-based stop loss data
        atr_info = self.atr_data[ticker]
        stop_loss_price = atr_info['stop_loss']
        atr_value = atr_info['atr']
        atr_percentage = atr_info['atr_percentage']
        volatility_category = atr_info['volatility_category']
        multiplier = atr_info['multiplier']

        # Get position data
        position_data = self.tracked_positions[ticker]
        original_quantity = position_data.get("original_quantity", position_data["quantity"])
        current_quantity = position_data["quantity"]
        entry_price = position_data["entry_price"]

        # Exit percentages for different volatility categories
        # We'll exit in 3 tranches: first tranche at SL, second at 1.5x profit, third at 2x profit
        exit_tranches = position_data.get("exit_tranches", {})

        # If exit_tranches is not set, initialize it based on volatility
        if not exit_tranches:
            # Default exit percentages by volatility
            if volatility_category == "Low":
                # Conservative exits for low volatility
                exit_tranches = {
                    "stop_loss": {"percent_of_position": 50, "triggered": False},  # 50% at stop loss
                    "profit_target_1": {"percent_of_position": 30, "triggered": False, "price_multiple": 2.0},  # 30% at 2x ATR profit
                    "profit_target_2": {"percent_of_position": 20, "triggered": False, "price_multiple": 3.0}   # 20% at 3x ATR profit
                }
            elif volatility_category == "Medium":
                # Balanced exits for medium volatility
                exit_tranches = {
                    "stop_loss": {"percent_of_position": 40, "triggered": False},  # 40% at stop loss
                    "profit_target_1": {"percent_of_position": 30, "triggered": False, "price_multiple": 2.5},  # 30% at 2.5x ATR profit
                    "profit_target_2": {"percent_of_position": 30, "triggered": False, "price_multiple": 4.0}   # 30% at 4x ATR profit
                }
            else:  # High volatility
                # Aggressive exits for high volatility
                exit_tranches = {
                    "stop_loss": {"percent_of_position": 30, "triggered": False},  # 30% at stop loss
                    "profit_target_1": {"percent_of_position": 30, "triggered": False, "price_multiple": 3.0},  # 30% at 3x ATR profit
                    "profit_target_2": {"percent_of_position": 40, "triggered": False, "price_multiple": 5.0}   # 40% at 5x ATR profit
                }

            # Store the tranches in position data
            position_data["exit_tranches"] = exit_tranches
            position_data["original_quantity"] = original_quantity
            self.tracked_positions[ticker] = position_data

            # Log the exit strategy
            self.logger.info(f"{ticker} Exit Strategy: {volatility_category} volatility")
            self.logger.info(f"  • Tranche 1: {exit_tranches['stop_loss']['percent_of_position']}% at stop loss")
            self.logger.info(f"  • Tranche 2: {exit_tranches['profit_target_1']['percent_of_position']}% at {exit_tranches['profit_target_1']['price_multiple']}x ATR profit")
            self.logger.info(f"  • Tranche 3: {exit_tranches['profit_target_2']['percent_of_position']}% at {exit_tranches['profit_target_2']['price_multiple']}x ATR profit")

        # Check if daily high has been updated
        if ticker in self.daily_high_prices:
            daily_high = self.daily_high_prices[ticker]
            stored_daily_high = atr_info.get('daily_high', 0)

            # If the daily high has increased, recalculate trailing stop
            if daily_high > stored_daily_high:
                # Calculate the new stop loss based on the daily high
                new_stop_loss = daily_high - (atr_value * multiplier)

                # Only adjust stop loss upward, never downward (trailing feature)
                if new_stop_loss > stop_loss_price:
                    old_stop_loss = stop_loss_price
                    self.atr_data[ticker]['stop_loss'] = new_stop_loss
                    self.atr_data[ticker]['daily_high'] = daily_high

                    # Log the trailing stop update
                    self.logger.info(f"{ticker}: DAILY HIGH TRAILING STOP UPDATED - New: ₹{new_stop_loss:.2f} (from: ₹{old_stop_loss:.2f}), "
                                  f"Based on daily high: ₹{daily_high:.2f}, ATR: ₹{atr_value:.2f} ({volatility_category} volatility)")

                    # Update the stop loss price for the current check
                    stop_loss_price = new_stop_loss

        # Log the ATR stop loss check for transparency
        self.logger.debug(f"ATR Stop Loss Check - {ticker}: Current Price: ₹{current_price:.2f}, "
                         f"Stop Loss: ₹{stop_loss_price:.2f}, ATR: ₹{atr_value:.2f} ({atr_percentage:.2f}%), "
                         f"{volatility_category} Volatility ({multiplier}x)")

        # 1. Check stop loss tranche
        stop_loss_tranche = exit_tranches["stop_loss"]
        if not stop_loss_tranche["triggered"] and current_price <= stop_loss_price:
            # Calculate number of shares to sell
            sell_percent = stop_loss_tranche["percent_of_position"]
            sell_quantity = int(original_quantity * sell_percent / 100)

            # Ensure we sell at least 1 share and not more than available
            sell_quantity = max(1, min(sell_quantity, current_quantity))

            # Get appropriate tick size for this ticker
            tick_size = self.tick_sizes.get(ticker, self.default_tick_size)

            # LONG position: SELL order slightly below stop loss
            order_price = round((stop_loss_price * 0.995) / tick_size) * tick_size

            self.logger.info(f"ATR STOP LOSS TRIGGERED - {ticker}: Current Price ₹{current_price:.2f} fell below "
                           f"ATR Stop Loss ₹{stop_loss_price:.2f} ({volatility_category} volatility, {multiplier}x ATR). "
                           f"Queuing SELL order for {sell_quantity} shares ({sell_percent}% of position) at ₹{order_price:.2f}.")

            # Queue the order for the calculated quantity
            self.queue_partial_order(ticker, sell_quantity, "SELL",
                           f"ATR stop loss breach - Current: ₹{current_price:.2f}, "
                           f"Stop Loss: ₹{stop_loss_price:.2f}, ATR: ₹{atr_value:.2f} ({atr_percentage:.2f}%), "
                           f"{volatility_category} volatility ({multiplier}x)", order_price, "stop_loss")

            return

        # 2. Check profit target tranches - only if above entry price
        if current_price > entry_price:
            profit_amount = current_price - entry_price
            profit_distance_in_atr = profit_amount / atr_value

            # Check profit target 2 (highest target) first
            profit_target_2 = exit_tranches["profit_target_2"]
            if not profit_target_2["triggered"] and profit_distance_in_atr >= profit_target_2["price_multiple"]:
                # Calculate number of shares to sell
                sell_percent = profit_target_2["percent_of_position"]
                sell_quantity = int(original_quantity * sell_percent / 100)

                # Ensure we sell at least 1 share and not more than available
                sell_quantity = max(1, min(sell_quantity, current_quantity))

                self.logger.info(f"PROFIT TARGET 2 REACHED - {ticker}: Current Price ₹{current_price:.2f} reached "
                               f"{profit_target_2['price_multiple']}x ATR profit. "
                               f"Queuing SELL order for {sell_quantity} shares ({sell_percent}% of position) at market price.")

                # Queue the order at market price
                self.queue_partial_order(ticker, sell_quantity, "SELL",
                               f"Profit target 2 reached - Current: ₹{current_price:.2f}, "
                               f"Profit: {profit_distance_in_atr:.2f}x ATR", None, "profit_target_2")
                return

            # Check profit target 1 (middle target)
            profit_target_1 = exit_tranches["profit_target_1"]
            if not profit_target_1["triggered"] and profit_distance_in_atr >= profit_target_1["price_multiple"]:
                # Calculate number of shares to sell
                sell_percent = profit_target_1["percent_of_position"]
                sell_quantity = int(original_quantity * sell_percent / 100)

                # Ensure we sell at least 1 share and not more than available
                sell_quantity = max(1, min(sell_quantity, current_quantity))

                self.logger.info(f"PROFIT TARGET 1 REACHED - {ticker}: Current Price ₹{current_price:.2f} reached "
                               f"{profit_target_1['price_multiple']}x ATR profit. "
                               f"Queuing SELL order for {sell_quantity} shares ({sell_percent}% of position) at market price.")

                # Queue the order at market price
                self.queue_partial_order(ticker, sell_quantity, "SELL",
                               f"Profit target 1 reached - Current: ₹{current_price:.2f}, "
                               f"Profit: {profit_distance_in_atr:.2f}x ATR", None, "profit_target_1")
                return

        # No exit condition triggered
        # Log that stop loss was not triggered for debugging
        distance_to_stop = current_price - stop_loss_price
        self.logger.debug(f"{ticker}: Current price ₹{current_price:.2f} above stop loss ₹{stop_loss_price:.2f} "
                        f"by ₹{distance_to_stop:.2f} - No trigger")
    
    def queue_partial_order(self, ticker, quantity, transaction_type, reason, price=None, tranche_id=None):
        """Add a partial order to the queue for execution with tracking of exit tranches"""
        # Check if we should ignore this order
        if ticker not in self.tracked_positions:
            self.logger.warning(f"Ignoring order for {ticker} as it's not in tracked positions")
            return False

        position_data = self.tracked_positions[ticker].copy()

        # Update the position data for this tranche if provided
        if tranche_id and "exit_tranches" in position_data and tranche_id in position_data["exit_tranches"]:
            position_data["exit_tranches"][tranche_id]["triggered"] = True
            self.tracked_positions[ticker]["exit_tranches"][tranche_id]["triggered"] = True
            self.logger.info(f"Marked {ticker} tranche '{tranche_id}' as triggered")

        # Calculate remaining quantity after this order
        current_quantity = position_data["quantity"]
        remaining_quantity = current_quantity - quantity

        # Create order info
        order_info = {
            "ticker": ticker,
            "quantity": quantity,
            "transaction_type": transaction_type,
            "reason": reason,
            "price": price,
            "timestamp": datetime.now().isoformat(),
            "position_data": position_data,
            "tranche_id": tranche_id,
            "is_partial": True,
            "remaining_quantity": remaining_quantity
        }

        # Add to queue for execution
        self.order_queue.put(order_info)
        order_type = "LIMIT" if price else "MARKET"
        price_info = f" at {price}" if price else ""
        self.logger.info(f"Queued PARTIAL {transaction_type} {order_type} order for {ticker} (qty: {quantity}/{current_quantity}){price_info}: {reason}")

        # Update the position quantity
        self.tracked_positions[ticker]["quantity"] = remaining_quantity

        # Flag position as having a pending order
        self.tracked_positions[ticker]["has_pending_order"] = True
        self.logger.info(f"Marked {ticker} as having a pending order to prevent duplicates")

        return True

    def queue_order(self, ticker, quantity, transaction_type, reason, price=None):
        """Add a full order to the queue for execution (for backward compatibility)"""
        order_info = {
            "ticker": ticker,
            "quantity": quantity,
            "transaction_type": transaction_type,
            "reason": reason,
            "price": price,
            "timestamp": datetime.now().isoformat(),
            "position_data": self.tracked_positions.get(ticker, {}).copy(),
            "is_partial": False
        }

        # Check if we should ignore this order
        if ticker not in self.tracked_positions:
            self.logger.warning(f"Ignoring order for {ticker} as it's not in tracked positions")
            return False

        # Add to queue for execution
        self.order_queue.put(order_info)
        order_type = "LIMIT" if price else "MARKET"
        price_info = f" at {price}" if price else ""
        self.logger.info(f"Queued FULL {transaction_type} {order_type} order for {ticker} (qty: {quantity}){price_info}: {reason}")

        # Flag position as having a pending order to prevent duplicate orders
        self.tracked_positions[ticker]["has_pending_order"] = True
        self.logger.info(f"Marked {ticker} as having a pending order to prevent duplicates")

        return True
    
    def process_order_queue(self):
        """Process queued orders with retry mechanism, handling partial orders"""
        try:
            while self.running:
                try:
                    # Non-blocking wait for order
                    if self.order_queue.empty():
                        time.sleep(0.5)
                        continue

                    order_info = self.order_queue.get(block=False)
                    ticker = order_info["ticker"]

                    # Position might have been removed from tracking
                    position_data = order_info.get("position_data", {})
                    if ticker not in self.tracked_positions and not position_data:
                        self.logger.warning(f"Skipping order for {ticker} as it's not in tracked positions and no position data is available")
                        self.order_queue.task_done()
                        continue

                    # Check if this is a partial order
                    is_partial = order_info.get("is_partial", False)
                    tranche_id = order_info.get("tranche_id")
                    remaining_qty = order_info.get("remaining_quantity", 0)

                    # Execute the order with retries
                    price = order_info.get("price")
                    order_type = "LIMIT" if price else "MARKET"
                    price_str = f" at {price}" if price else ""

                    order_desc = "PARTIAL " if is_partial else ""
                    self.logger.info(f"Executing {order_desc}{order_info['transaction_type']} {order_type} order for {ticker}{price_str}")

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

                            if is_partial:
                                tranche_info = f" (Tranche: {tranche_id})" if tranche_id else ""
                                self.logger.info(f"Partial order placed successfully for {ticker} with ID {order_id}{tranche_info}")

                                # Handle partial position update
                                if ticker in self.tracked_positions:
                                    # Reset the pending order flag so we can place more orders
                                    self.tracked_positions[ticker]["has_pending_order"] = False

                                    # Check if this was the last part of the position
                                    if remaining_qty <= 0:
                                        self.logger.info(f"All shares of {ticker} sold, removing from tracking")
                                        del self.tracked_positions[ticker]
                                        if ticker in self.current_prices:
                                            del self.current_prices[ticker]
                                        if ticker in self.atr_data:
                                            del self.atr_data[ticker]
                                    else:
                                        self.logger.info(f"Partial exit for {ticker}, remaining shares: {remaining_qty}")
                            else:
                                # Full position exit
                                self.logger.info(f"Full order placed successfully for {ticker} with ID {order_id}")

                                # Mark position as sold and remove from tracking
                                if ticker in self.tracked_positions:
                                    self.logger.info(f"Full exit for {ticker}, removing from tracking")
                                    del self.tracked_positions[ticker]
                                    if ticker in self.current_prices:
                                        del self.current_prices[ticker]
                                    if ticker in self.atr_data:
                                        del self.atr_data[ticker]

                            # Log the sale
                            order_quantity = order_info["quantity"]
                            sale_price = price if price else self.current_prices.get(ticker, 0)
                            sale_value = order_quantity * sale_price

                            if is_partial:
                                # For partial exits, calculate P&L proportionally
                                original_qty = position_data.get("original_quantity", order_quantity)
                                entry_price = position_data.get("entry_price", 0)
                                portion = order_quantity / original_qty if original_qty > 0 else 1
                                portion_investment = entry_price * order_quantity
                                profit_loss = sale_value - portion_investment

                                self.logger.info(f"Partial position ({order_quantity}/{original_qty} shares) closed - {ticker}: "
                                               f"Portion Investment: ₹{portion_investment:.2f}, "
                                               f"Sale: ₹{sale_value:.2f}, P/L: ₹{profit_loss:.2f}, "
                                               f"P/L %: {(profit_loss/portion_investment*100):.2f}%")
                            else:
                                # For full exits, use the total investment
                                investment = position_data.get('investment_amount', 0)
                                profit_loss = sale_value - investment

                                self.logger.info(f"Full position closed - {ticker}: Investment: ₹{investment:.2f}, "
                                               f"Sale: ₹{sale_value:.2f}, P/L: ₹{profit_loss:.2f}, "
                                               f"P/L %: {(profit_loss/investment*100) if investment > 0 else 0:.2f}%")

                            # Success - break out of retry loop
                            break

                        except Exception as e:
                            error_str = str(e).lower()

                            # Check if this is a duplicate or already-executed order
                            if "order already completed" in error_str or "duplicate order" in error_str:
                                self.logger.warning(f"Order for {ticker} appears to be already executed.")

                                # Handle cleanup based on whether this was partial or full
                                if not is_partial and ticker in self.tracked_positions:
                                    del self.tracked_positions[ticker]
                                elif is_partial and ticker in self.tracked_positions:
                                    self.tracked_positions[ticker]["has_pending_order"] = False

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
                                    # Reset pending order flag to allow future attempts
                                    if ticker in self.tracked_positions:
                                        self.tracked_positions[ticker]["has_pending_order"] = False
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
                                    # Reset pending order flag to allow future attempts
                                    if ticker in self.tracked_positions:
                                        self.tracked_positions[ticker]["has_pending_order"] = False
                                    break

                    self.order_queue.task_done()
                except Exception as e:
                    if not isinstance(e, Exception) or "Empty" not in str(e):
                        self.logger.error(f"Error in order queue processing: {e}")
                    time.sleep(0.5)
        except Exception as e:
            self.logger.error(f"Fatal error in order thread: {e}")
    
    def start(self):
        """Start the watchdog monitoring system"""
        self.logger.info(f"Starting ATR-based stop loss watchdog for user {self.user_name}...")

        # Check if market is already closed
        if self.is_market_closed():
            self.logger.warning("Market is closed (after 3:30 PM IST or weekend). SL_watchdog will not start.")
            return False
        else:
            # Log when shutdown will occur
            ist = pytz.timezone('Asia/Kolkata')
            current_time = datetime.now(ist)
            market_close = current_time.replace(hour=15, minute=30, second=0, microsecond=0)
            self.logger.info(f"SL_watchdog will automatically shutdown at {market_close.strftime('%H:%M IST')}")

        self.running = True

        # Load CNC positions using hybrid approach (both Zerodha API and orders file)
        positions_loaded = self.load_cnc_positions_from_zerodha()

        # Always also load from orders file to get complete picture (if provided)
        if self.orders_file and os.path.exists(self.orders_file):
            self.logger.info("Loading additional positions from orders file to ensure complete coverage...")
            orders_loaded = self.load_positions_from_orders_file()
            self.logger.info(f"Total positions after hybrid loading: {len(self.tracked_positions)}")
        else:
            self.logger.warning("No orders file provided - only using Zerodha API positions")

        if len(self.tracked_positions) == 0:
            self.logger.error("No positions to monitor. Exiting.")
            return False
        
        # Initialize ATR-based stop losses
        self.update_atr_stop_losses()
        
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
        
        # Print initial status
        self.print_portfolio_summary()
        
        # Main monitoring loop
        try:
            while self.running:
                # Check if market is closed and shutdown if needed
                if self.is_market_closed():
                    self.logger.info("Market has closed (3:30 PM IST). Shutting down SL_watchdog...")
                    self.stop()
                    break

                # Update ATR-based stop losses periodically (daily)
                self.update_atr_stop_losses()

                # Print summary every 10 minutes
                if int(time.time()) % 600 == 0:  # Every 10 minutes
                    self.print_portfolio_summary()

                time.sleep(10)  # Check every 10 seconds
        except Exception as e:
            self.logger.error(f"Error in main monitoring loop: {e}")
            self.stop()
            return False
        
        return True
    
    def stop(self):
        """Stop the watchdog monitoring system"""
        self.logger.info("Stopping ATR-based stop loss watchdog...")
        self.running = False

        # Wait for threads to complete
        if self.price_poll_thread and self.price_poll_thread.is_alive():
            self.price_poll_thread.join(timeout=5)

        if self.order_thread and self.order_thread.is_alive():
            self.order_thread.join(timeout=5)

        self.logger.info("ATR-based stop loss watchdog stopped")
        return True
    
    def print_portfolio_summary(self):
        """Print a summary of the current monitored positions"""
        self.logger.info("=== ATR-Based Trailing Stop Loss Portfolio Summary ===")

        if not self.tracked_positions:
            self.logger.info("No positions currently being monitored")
            return

        total_investment = 0
        total_current_value = 0

        for ticker, position in self.tracked_positions.items():
            qty = position["quantity"]
            entry_price = position["entry_price"]
            investment = position["investment_amount"]

            # Get ATR data for this ticker
            atr_info = self.atr_data.get(ticker, {})
            if atr_info:
                stop_loss = atr_info.get('stop_loss', 0)
                atr_pct = atr_info.get('atr_percentage', 0)
                volatility = atr_info.get('volatility_category', 'Unknown')
                multiplier = atr_info.get('multiplier', 0)

                # Get the current price before trying to use it
                current_price = self.current_prices.get(ticker, entry_price)

                # Get daily high info for trailing information
                daily_high = atr_info.get('daily_high', 0)
                if daily_high > 0 and daily_high > current_price:
                    trail_info = f", Trail: {((daily_high - current_price) / daily_high * 100):.1f}% from daily high ₹{daily_high:.2f}"
                else:
                    trail_info = ""

                atr_display = f"₹{stop_loss:.2f} ({volatility} {multiplier}x, ATR: {atr_pct:.1f}%{trail_info})"
            else:
                atr_display = "Calculating..."
                current_price = self.current_prices.get(ticker, entry_price)

            current_value = current_price * qty
            profit_loss = current_value - investment
            profit_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

            total_investment += investment
            total_current_value += current_value

            self.logger.info(f"{ticker}: {qty} shares @ ₹{entry_price:.2f} | Current: ₹{current_price:.2f} | "
                           f"P/L: ₹{profit_loss:.2f} ({profit_pct:.2f}%) | ATR Stop: {atr_display}")

        # Calculate overall performance
        total_profit_loss = total_current_value - total_investment
        total_profit_pct = (total_profit_loss / total_investment) * 100 if total_investment > 0 else 0

        self.logger.info(f"Total Portfolio: Investment: ₹{total_investment:.2f} | Current: ₹{total_current_value:.2f} | "
                        f"P/L: ₹{total_profit_loss:.2f} ({total_profit_pct:.2f}%)")
        self.logger.info(f"Positions monitored: {len(self.tracked_positions)}")

def find_orders_file(user_name: str = None) -> Optional[str]:
    """Find the most recent orders file, optionally for a specific user"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        daily_dir = os.path.dirname(script_dir)
        
        if user_name:
            # Look for files for specific user
            pattern = os.path.join(daily_dir, "Current_Orders", user_name, "orders_*.json")
        else:
            # Look for files for any user
            pattern = os.path.join(daily_dir, "Current_Orders", "*", "orders_*.json")
        
        order_files = glob.glob(pattern)
        
        if not order_files:
            return None
        
        # Sort by modification time (newest first)
        order_files.sort(key=os.path.getmtime, reverse=True)
        return order_files[0]
        
    except Exception as e:
        logging.error(f"Error finding orders file: {e}")
        return None

def extract_user_from_orders_file(orders_file: str) -> Optional[str]:
    """Extract user name from orders file path or content"""
    try:
        if not orders_file:
            return None

        # Try to extract from file path first
        path_parts = orders_file.split(os.sep)
        for i, part in enumerate(path_parts):
            if part == "Current_Orders" and i + 1 < len(path_parts):
                return path_parts[i + 1]

        # Try to extract from file content
        with open(orders_file, 'r') as f:
            data = json.load(f)
            return data.get('user_profile')

    except Exception as e:
        logging.error(f"Error extracting user from orders file: {e}")
        return None

def get_default_user() -> Optional[str]:
    """Get default user if no orders file is provided"""
    try:
        # Look for users with recent orders files
        script_dir = os.path.dirname(os.path.abspath(__file__))
        daily_dir = os.path.dirname(script_dir)
        orders_dir = os.path.join(daily_dir, "Current_Orders")

        if os.path.exists(orders_dir):
            users = []
            for user_dir in os.listdir(orders_dir):
                user_path = os.path.join(orders_dir, user_dir)
                if os.path.isdir(user_path):
                    users.append(user_dir)

            if len(users) == 1:
                return users[0]
            elif len(users) > 1:
                # Return the first user alphabetically
                return sorted(users)[0]

        return None
    except Exception as e:
        logging.error(f"Error getting default user: {e}")
        return None

def main():
    # Parse command line arguments
    args = parse_args()

    # Determine user name
    user_name = None
    if args.orders_file:
        # Extract user name from orders file
        user_name = extract_user_from_orders_file(args.orders_file)
        if not user_name:
            print(f"Error: Could not determine user name from orders file: {args.orders_file}")
            return 1
    else:
        # Try to get default user
        user_name = get_default_user()
        if not user_name:
            print("Error: No orders file provided and could not determine default user.")
            print("Please provide a user name or orders file.")
            return 1
        print(f"No orders file provided. Using default user: {user_name}")
    
    # Initialize logging
    logger = setup_logging(user_name)
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Log start of execution
    logger.info(f"===== ATR-Based Stop Loss Watchdog Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    if args.orders_file:
        logger.info(f"Orders file: {args.orders_file}")
    else:
        logger.info("Monitoring ALL CNC positions from Zerodha account")
    logger.info(f"User: {user_name}")
    
    try:
        # Load Daily config
        config = load_daily_config()
        
        # Get user credentials
        user_credentials = get_user_from_config(user_name, config)
        if not user_credentials:
            logger.error(f"Invalid or incomplete credentials for user {user_name}. Need api_key, api_secret, and access_token.")
            return 1
        
        # Verify orders file exists if provided
        if args.orders_file and not os.path.exists(args.orders_file):
            logger.error(f"Orders file not found: {args.orders_file}")
            return 1

        # Create watchdog instance
        watchdog = SLWatchdog(
            user_credentials=user_credentials,
            config=config,
            orders_file=args.orders_file,
            price_poll_interval=args.poll_interval
        )
        
        # Start the watchdog
        success = watchdog.start()
        if not success:
            return 1
        
        # Keep the main thread alive
        while True:
            try:
                time.sleep(60)  # Sleep for 1 minute
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(10)
                
    except KeyboardInterrupt:
        logger.info("User requested shutdown")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1
    finally:
        # Ensure proper cleanup
        if 'watchdog' in locals():
            watchdog.stop()
        logger.info(f"===== ATR-Based Stop Loss Watchdog Stopped at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())