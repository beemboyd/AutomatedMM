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
import numpy as np
from datetime import datetime, timedelta
import pytz
from queue import Queue
from typing import Dict, List, Tuple, Optional

# Add parent directory to path so we can import modules
# For self-contained Daily folder, add Daily to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    """Set up logging with user-specific log files and rotation"""
    from logging.handlers import RotatingFileHandler
    
    # Create user-specific log directory
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', user_name)
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'SL_watchdog_{user_name}.log')
    
    # Configure logging with rotation
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers = []  # Clear existing handlers
    
    # Create rotating file handler (10MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)
    
    logger.info(f"Logging initialized for user {user_name} with rotation (10MB max, 5 backups)")
    
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

    True Trailing Stop Loss: Stop losses trail upward based on the highest price reached since position entry,
    but never move downward. The system tracks the highest price since each position was entered and uses that
    to recalculate the stop loss, ensuring profits are protected while still giving room based on volatility.
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
        
        # Historical data cache for performance
        self.historical_cache = {}  # ticker -> (data, timestamp)
        self.cache_ttl = 300  # 5 minutes
        
        # Profit target exits configuration
        profit_target_str = config.get('DEFAULT', 'profit_target_exits', fallback='no').lower()
        self.profit_target_exits_enabled = profit_target_str in ['yes', 'true', '1', 'on']
        
        # VSR-based exit configuration
        vsr_exit_str = config.get('SL', 'vsr_exit_enabled', fallback='yes').lower()
        self.vsr_exit_enabled = vsr_exit_str in ['yes', 'true', '1', 'on']
        self.vsr_exit_threshold = config.getfloat('SL', 'vsr_exit_threshold', fallback=50.0)
        self.vsr_check_interval_hours = config.getfloat('SL', 'vsr_check_interval_hours', fallback=1.0)
        
        # Loss threshold exit configuration
        loss_threshold_str = config.get('SL', 'loss_threshold_enabled', fallback='yes').lower()
        self.loss_threshold_enabled = loss_threshold_str in ['yes', 'true', '1', 'on']
        self.loss_threshold_percent = config.getfloat('SL', 'loss_threshold_percent', fallback=2.0)
        
        # Candle length exit configuration
        candle_length_str = config.get('SL', 'candle_length_exit_enabled', fallback='yes').lower()
        self.candle_length_exit_enabled = candle_length_str in ['yes', 'true', '1', 'on']
        self.candle_length_multiplier = config.getfloat('SL', 'candle_length_multiplier', fallback=2.0)

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
        
        # Cache for instruments data
        self.instruments_cache = None
        self.instruments_last_fetch = 0

        # Position tracking
        self.tracked_positions = {}  # Positions we're monitoring from orders file
        self.current_prices = {}  # ticker -> latest price
        self.position_high_prices = {}  # ticker -> highest price since position entry
        self.daily_high_prices = {}  # ticker -> day's highest price (from market data) - kept for backward compatibility
        self.atr_data = {}  # ticker -> {'atr': value, 'atr_percentage': value, 'stop_loss': value, 'multiplier': value, 'position_high': value}
        self.sma20_hourly_data = {}  # ticker -> {'sma20_violations': count, 'hours_monitored': count, 'hours_above_sma20': count}
        self.peak_warning_issued = {}  # ticker -> bool, tracks if 2% warning has been issued

        # VSR tracking data
        self.vsr_data = {}  # ticker -> {'entry_vsr': value, 'current_vsr': value, 'vsr_history': [], 'last_hourly_check': datetime}
        self.hourly_candles = {}  # ticker -> list of hourly candles for VSR calculation

        # Tick size mapping (default fallback for unknown tickers)
        self.default_tick_size = 0.05
        self.tick_sizes = {}  # Will be populated dynamically from instruments data
        
        # Known tick sizes for specific tickers that often cause issues
        self.known_tick_sizes = {
            "AIAENG": 0.10,
            "CREDITACC": 0.10,
            # Add more as needed
        }
        
        # Common tick sizes based on price ranges (NSE guidelines)
        # These are fallbacks when instrument data is not available
        self.price_tick_ranges = [
            (0, 50, 0.01),      # Below ₹50: tick size 0.01
            (50, 100, 0.05),    # ₹50-100: tick size 0.05
            (100, 500, 0.05),   # ₹100-500: tick size 0.05
            (500, 1000, 0.10),  # ₹500-1000: tick size 0.10
            (1000, 5000, 0.25), # ₹1000-5000: tick size 0.25
            (5000, 10000, 0.50),# ₹5000-10000: tick size 0.50
            (10000, float('inf'), 1.00) # Above ₹10000: tick size 1.00
        ]

        # Message queue for order execution
        self.order_queue = Queue()

        # Monitoring state
        self.running = False
        self.last_price_check = 0
        self.last_atr_check = 0
        self.last_sma20_check = 0
        self.last_position_sync = 0
        self.last_vsr_check = 0  # Track last VSR check time

        # Threads
        self.price_poll_thread = None
        self.order_thread = None

        # Subscribe to shutdown signals
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        # Log the ATR-based stop loss logic being used
        self.logger.info("=" * 60)
        self.logger.info("ATR-BASED TRAILING STOP LOSS CONFIGURATION")
        self.logger.info("Stop loss calculation based on 20-day ATR:")
        self.logger.info("- Low Volatility (ATR <2%): Stop = 1.0x ATR")
        self.logger.info("- Medium Volatility (ATR 2-4%): Stop = 1.5x ATR")
        self.logger.info("- High Volatility (ATR >4%): Stop = 2.0x ATR")
        self.logger.info("TRUE TRAILING STOP FEATURE: Stop losses automatically rise as prices reach new highs")
        self.logger.info("- Trailing stops only move upward, never downward")
        self.logger.info("- Stop losses recalculated based on highest price reached since position entry")
        self.logger.info("- Profits are protected while still allowing for volatility")
        self.logger.info("")
        self.logger.info("VSR-BASED EXIT RULES:")
        if self.vsr_exit_enabled:
            self.logger.info(f"- ENABLED: Exit if hourly VSR drops < {self.vsr_exit_threshold}% of entry VSR")
            self.logger.info(f"- Check interval: {self.vsr_check_interval_hours} hours")
        else:
            self.logger.info("- DISABLED")
        self.logger.info("")
        self.logger.info("LOSS THRESHOLD EXIT RULES:")
        if self.loss_threshold_enabled:
            self.logger.info(f"- ENABLED: Exit if position shows -{self.loss_threshold_percent}% loss")
        else:
            self.logger.info("- DISABLED")
        self.logger.info("")
        self.logger.info("CANDLE LENGTH EXIT RULES:")
        if self.candle_length_exit_enabled:
            self.logger.info(f"- ENABLED: Exit if hourly candle length > {self.candle_length_multiplier}x ATR")
        else:
            self.logger.info("- DISABLED")
        self.logger.info("")
        if self.profit_target_exits_enabled:
            self.logger.info("PROFIT TARGET EXITS ENABLED")
            self.logger.info("- Partial exits at predefined ATR multiples based on volatility")
            self.logger.info("- Low Vol: 50% at SL, 30% at 2x ATR, 20% at 3x ATR")
            self.logger.info("- Med Vol: 40% at SL, 30% at 2.5x ATR, 30% at 4x ATR")
            self.logger.info("- High Vol: 30% at SL, 30% at 3x ATR, 40% at 5x ATR")
        else:
            self.logger.info("PROFIT TARGET EXITS DISABLED - Only stop losses will trigger exits")
        self.logger.info("")
        self.logger.info("SMA20 EXIT CHECKS DISABLED")
        self.logger.info("- SMA20 data is collected for monitoring only")
        self.logger.info("- No automatic exits based on SMA20 violations")
        self.logger.info("- Positions will only exit on ATR-based stop losses")
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
    
    def get_tick_size(self, ticker: str) -> float:
        """Get tick size for a ticker from instruments data or cache"""
        # Check cache first
        if ticker in self.tick_sizes:
            return self.tick_sizes[ticker]
        
        # Check known tick sizes
        if ticker.upper() in self.known_tick_sizes:
            tick_size = self.known_tick_sizes[ticker.upper()]
            self.tick_sizes[ticker] = tick_size
            self.logger.info(f"Using known tick size for {ticker}: {tick_size}")
            return tick_size
        
        try:
            # Try to get tick size from instruments data
            instruments = self.get_instruments_data()
            if instruments:
                # Find the instrument for this ticker
                for inst in instruments:
                    if inst.get('tradingsymbol', '').upper() == ticker.upper():
                        if 'tick_size' in inst:
                            tick_size = float(inst['tick_size'])
                            # Cache for future use
                            self.tick_sizes[ticker] = tick_size
                            self.logger.debug(f"Got tick size for {ticker}: {tick_size} (from instruments)")
                            return tick_size
                        break
                # Fallback: Use price-based tick size
                current_price = self.current_prices.get(ticker, 0)
                if current_price > 0:
                    # Find appropriate tick size based on price range
                    for min_price, max_price, tick in self.price_tick_ranges:
                        if min_price <= current_price < max_price:
                            self.tick_sizes[ticker] = tick  # Cache it
                            self.logger.info(f"Using price-based tick size for {ticker} @ ₹{current_price:.2f}: {tick}")
                            return tick
                
                # If all else fails, use default
                self.logger.warning(f"No tick size found for {ticker}, using default: {self.default_tick_size}")
                return self.default_tick_size
        except Exception as e:
            self.logger.error(f"Error getting tick size for {ticker}: {e}")
            return self.default_tick_size
    
    def round_to_tick_size(self, price: float, tick_size: float) -> float:
        """Round price to nearest valid tick size multiple"""
        if tick_size <= 0:
            tick_size = self.default_tick_size
        
        # Round to nearest tick size
        rounded_price = round(price / tick_size) * tick_size
        
        # Ensure we have proper decimal places
        # Count decimal places in tick_size
        tick_str = f"{tick_size:.10f}".rstrip('0').rstrip('.')
        decimal_places = len(tick_str.split('.')[-1]) if '.' in tick_str else 0
        
        # Format the price with same decimal places
        return round(rounded_price, decimal_places)

    def verify_position_exists(self, ticker: str, expected_quantity: int = None) -> bool:
        """Verify if a position exists with Zerodha before attempting to trade"""
        try:
            # First check our tracked positions (which handles partial sells correctly)
            tracked_pos = self.tracked_positions.get(ticker)
            if tracked_pos and tracked_pos.get('quantity', 0) > 0:
                actual_quantity = tracked_pos['quantity']
                if expected_quantity and actual_quantity != expected_quantity:
                    self.logger.warning(f"{ticker}: Expected {expected_quantity} shares but found {actual_quantity} in tracking")
                return True
            
            # Get current positions from Zerodha
            positions = self.kite.positions()
            
            # Check net positions for the ticker
            for position in positions.get('net', []):
                if (position.get('tradingsymbol', '').upper() == ticker.upper() and 
                    position.get('product') == 'CNC'):
                    actual_quantity = int(position.get('quantity', 0))
                    
                    if actual_quantity > 0:
                        # Position exists
                        if expected_quantity and actual_quantity != expected_quantity:
                            self.logger.warning(f"{ticker}: Expected {expected_quantity} shares but found {actual_quantity}")
                        return True
                    else:
                        self.logger.warning(f"{ticker}: Position exists but quantity is {actual_quantity}")
                        # Don't return False yet - check holdings for partial sell cases
                        pass
            
            # Also check holdings (including T1 positions)
            try:
                holdings = self.kite.holdings()
                for holding in holdings:
                    if holding.get('tradingsymbol', '').upper() == ticker.upper():
                        quantity = int(holding.get('quantity', 0))
                        t1_quantity = int(holding.get('t1_quantity', 0))
                        actual_quantity = quantity + t1_quantity
                        
                        if actual_quantity > 0:
                            if t1_quantity > 0:
                                # Get current stop loss value from atr_data
                                current_sl = "N/A"
                                if ticker in self.atr_data and 'stop_loss' in self.atr_data[ticker]:
                                    current_sl = f"₹{self.atr_data[ticker]['stop_loss']:.2f}"
                                self.logger.info(f"{ticker}: Found T1 holding - Settled: {quantity}, T1: {t1_quantity}, Total: {actual_quantity}, Current SL: {current_sl}")
                            if expected_quantity and actual_quantity != expected_quantity:
                                self.logger.warning(f"{ticker}: Expected {expected_quantity} shares but found {actual_quantity} in holdings")
                            return True
                        else:
                            self.logger.warning(f"{ticker}: Holding exists but total quantity (including T1) is {actual_quantity}")
                            return False
            except Exception as e:
                self.logger.debug(f"Could not check holdings for {ticker}: {e}")
            
            # Position not found
            self.logger.warning(f"{ticker}: Position not found in Zerodha account")
            return False
            
        except Exception as e:
            self.logger.error(f"Error verifying position for {ticker}: {e}")
            # On error, assume position exists to avoid accidental skips
            return True
    
    def get_instruments_data(self):
        """Get instruments data with caching (24 hour cache)"""
        current_time = time.time()
        cache_duration = 86400  # 24 hours
        
        # Return cached data if still valid
        if (self.instruments_cache and 
            current_time - self.instruments_last_fetch < cache_duration):
            return self.instruments_cache
        
        try:
            # Fetch fresh instruments data
            self.logger.info("Fetching instruments data from exchange")
            instruments = self.kite.instruments(self.exchange)
            self.instruments_cache = instruments
            self.instruments_last_fetch = current_time
            self.logger.info(f"Fetched {len(instruments)} instruments successfully")
            return instruments
        except Exception as e:
            self.logger.error(f"Error fetching instruments data: {e}")
            # Return cached data if available, even if expired
            if self.instruments_cache:
                self.logger.warning("Using expired instruments cache")
                return self.instruments_cache
            return []
    
    def get_instrument_token(self, ticker: str) -> Optional[int]:
        """Get instrument token for a ticker"""
        instruments = self.get_instruments_data()
        for inst in instruments:
            if inst.get('tradingsymbol', '').upper() == ticker.upper():
                return inst.get('instrument_token')
        
        self.logger.warning(f"Instrument token not found for {ticker}")
        return None
    
    def remove_position_from_tracking(self, ticker: str):
        """Remove a position from all tracking dictionaries"""
        self.logger.info(f"Removing {ticker} from all tracking")
        
        # Remove from main tracking
        if ticker in self.tracked_positions:
            del self.tracked_positions[ticker]
            
        # Remove from price tracking
        if ticker in self.current_prices:
            del self.current_prices[ticker]
            
        # Remove from position high tracking
        if ticker in self.position_high_prices:
            del self.position_high_prices[ticker]
            
        # Remove from daily high tracking (backward compatibility)
        if ticker in self.daily_high_prices:
            del self.daily_high_prices[ticker]
            
        # Remove from ATR data
        if ticker in self.atr_data:
            del self.atr_data[ticker]
            
        # Remove from SMA20 data
        if ticker in self.sma20_hourly_data:
            del self.sma20_hourly_data[ticker]
            
        # Remove from peak warning tracking
        if ticker in self.peak_warning_issued:
            del self.peak_warning_issued[ticker]
            
        # Remove from tick sizes
        if ticker in self.tick_sizes:
            del self.tick_sizes[ticker]
            
        self.logger.info(f"Successfully removed {ticker} from all tracking dictionaries")
    
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
                
                # Create a map of positions by ticker for easy lookup
                positions_by_ticker = {pos['tradingsymbol']: pos for pos in cnc_positions}

                for holding in holdings:
                    ticker = holding.get('tradingsymbol', '')
                    quantity = int(holding.get('quantity', 0))
                    t1_quantity = int(holding.get('t1_quantity', 0))
                    total_quantity = quantity + t1_quantity

                    # Check if this ticker has a negative position (partial sell)
                    existing_pos = positions_by_ticker.get(ticker)
                    if existing_pos and int(existing_pos.get('quantity', 0)) < 0:
                        # This is a partial sell case - update the position with holding data
                        self.logger.info(f"{ticker}: Found partial sell - Position shows {existing_pos['quantity']} (sold), Holdings shows {total_quantity} (remaining)")
                        # Update the position quantity to reflect remaining shares
                        existing_pos['quantity'] = total_quantity
                        existing_pos['original_quantity'] = int(holding.get('opening_quantity', total_quantity))
                        existing_pos['average_price'] = holding.get('average_price', existing_pos.get('average_price', 0))
                        existing_pos['used_quantity'] = int(holding.get('used_quantity', 0))
                        continue

                    if total_quantity > 0 and ticker != '' and ticker not in existing_tickers:
                        # Convert holding to position-like format
                        holding_as_position = {
                            'tradingsymbol': ticker,
                            'product': 'CNC',  # Holdings are always CNC
                            'quantity': total_quantity,
                            'settled_quantity': quantity,
                            't1_quantity': t1_quantity,
                            'average_price': holding.get('average_price', 0),
                            'last_price': holding.get('last_price', 0),
                            'pnl': holding.get('pnl', 0),
                            'exchange': holding.get('exchange', 'NSE'),
                            'instrument_token': holding.get('instrument_token', 0),
                            'unrealised': holding.get('day_change', 0) * total_quantity,
                            'realised': 0
                        }
                        cnc_positions.append(holding_as_position)
                        holdings_count += 1
                        if t1_quantity > 0:
                            self.logger.info(f"CNC Holding with T1 found: {ticker} - Settled: {quantity}, T1: {t1_quantity}, Total: {total_quantity} shares")
                        else:
                            self.logger.debug(f"CNC Holding found: {ticker} - {total_quantity} shares")
                    elif ticker in existing_tickers:
                        self.logger.debug(f"Skipping duplicate ticker {ticker} from holdings (already in positions)")
                    elif total_quantity <= 0:
                        self.logger.debug(f"Skipping {ticker} from holdings: settled={quantity}, t1={t1_quantity}, total={total_quantity}")

                self.logger.info(f"Added {holdings_count} holdings as CNC positions")

            except Exception as e:
                self.logger.warning(f"Could not fetch holdings: {e}")

            total_cnc_positions = len(cnc_positions)
            self.logger.info(f"Total CNC positions found: {total_cnc_positions} (positions + holdings)")

            if total_cnc_positions == 0:
                self.logger.warning("No CNC positions found in account")
                return 0

            # Load all order files to reconstruct position history
            self.logger.info("\n" + "="*60)
            self.logger.info("STATELESS MODE: Loading order files to reconstruct position history...")
            order_files = self.load_all_order_files()
            
            # Create a position lookup dictionary for easy access
            cnc_positions_by_ticker = {pos['tradingsymbol']: pos for pos in cnc_positions}
            
            # Process each CNC position with stateless reconstruction
            for position in cnc_positions:
                ticker = position['tradingsymbol']
                quantity = int(position['quantity'])

                # Skip if quantity is 0 or negative (will be handled by holdings check)
                if quantity <= 0:
                    self.logger.info(f"Skipping {ticker}: quantity is {quantity} (will check holdings for remaining shares)")
                    continue

                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"Reconstructing state for {ticker}...")
                
                # Reconstruct complete position state
                reconstructed_state = self.reconstruct_position_state(ticker, position, order_files)
                
                if not reconstructed_state:
                    self.logger.error(f"Failed to reconstruct state for {ticker}, using fallback approach...")
                    # Fallback to basic tracking without historical data
                    entry_price = float(position.get('average_price', position.get('last_price', 100)))
                    self.tracked_positions[ticker] = {
                        "type": "LONG",
                        "quantity": quantity,
                        "entry_price": entry_price,
                        "investment_amount": entry_price * quantity,
                        "product": position['product'],
                        "exchange": position['exchange'],
                        "instrument_token": position['instrument_token'],
                        "pnl": float(position.get('pnl', 0)),
                        "unrealised": float(position.get('unrealised', 0)),
                        "realised": float(position.get('realised', 0)),
                        "has_pending_order": False,
                        "zerodha_position": True,
                        "t1_quantity": position.get('t1_quantity', 0),
                        "settled_quantity": position.get('settled_quantity', quantity),
                        "entry_timestamp": datetime.now().isoformat()
                    }
                    self.position_high_prices[ticker] = entry_price
                    continue
                
                # Build tracked position from reconstructed state
                self.tracked_positions[ticker] = {
                    "type": "LONG",
                    "quantity": quantity,
                    "entry_price": reconstructed_state['entry_price'],
                    "investment_amount": reconstructed_state['entry_price'] * quantity,
                    "product": position['product'],
                    "exchange": position['exchange'],
                    "instrument_token": position['instrument_token'],
                    "pnl": float(position.get('pnl', 0)),
                    "unrealised": float(position.get('unrealised', 0)),
                    "realised": float(position.get('realised', 0)),
                    "has_pending_order": False,
                    "zerodha_position": True,
                    "t1_quantity": position.get('t1_quantity', 0),
                    "settled_quantity": position.get('settled_quantity', quantity),
                    "entry_timestamp": reconstructed_state['entry_timestamp'],
                    "position_source": reconstructed_state['source'],
                    "original_quantity": reconstructed_state.get('original_quantity', quantity)
                }
                
                # Set position high from reconstruction
                self.position_high_prices[ticker] = reconstructed_state['position_high']
                
                # Store ATR data with reconstructed stop loss
                self.atr_data[ticker] = reconstructed_state['atr_data']
                self.atr_data[ticker]['position_high'] = reconstructed_state['position_high']
                self.atr_data[ticker]['stop_loss'] = reconstructed_state['current_stop_loss']
                
                # Log the reconstruction summary
                self.logger.info(f"✅ {ticker} State Reconstructed:")
                self.logger.info(f"  Entry: {reconstructed_state['quantity']} shares @ ₹{reconstructed_state['entry_price']:.2f} on {reconstructed_state['entry_timestamp'][:10]}")
                self.logger.info(f"  Position High: ₹{reconstructed_state['position_high']:.2f}")
                self.logger.info(f"  Current Stop Loss: ₹{reconstructed_state['current_stop_loss']:.2f}")
                self.logger.info(f"  ATR: ₹{reconstructed_state['atr_data']['atr']:.2f} ({reconstructed_state['atr_data']['atr_percentage']:.2f}%)")
                self.logger.info(f"  Volatility: {reconstructed_state['atr_data']['volatility_category']} ({reconstructed_state['atr_data']['multiplier']}x)")
                self.logger.info(f"  Source: {reconstructed_state['source']}")
                self.logger.info(f"  Current P&L: ₹{float(position.get('pnl', 0)):,.2f}")

            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Stateless reconstruction complete. Tracking {len(self.tracked_positions)} positions.")
            
            # IMPORTANT: Check for breaches immediately after reconstruction
            # This handles gap-down scenarios where price breached stop during market close
            self.logger.info("Checking for stop loss breaches after reconstruction...")
            for ticker in list(self.tracked_positions.keys()):
                # Use the tracked position which has been corrected for partial sells
                tracked_pos = self.tracked_positions.get(ticker)
                if tracked_pos and tracked_pos.get('quantity', 0) > 0:
                    # Find the position for current price
                    position = cnc_positions_by_ticker.get(ticker)
                    if position:
                        current_price = float(position.get('last_price', 0))
                    else:
                        # If not in positions, check holdings
                        current_price = 0
                        for holding in holdings:
                            if holding.get('tradingsymbol') == ticker:
                                current_price = float(holding.get('last_price', 0))
                                break
                    
                    if current_price > 0:
                        # Store the current price
                        self.current_prices[ticker] = current_price
                        
                        # Check for stop loss breach
                        if ticker in self.atr_data:
                            stop_loss = self.atr_data[ticker].get('stop_loss', 0)
                            if stop_loss > 0 and current_price <= stop_loss:
                                gap_percent = ((stop_loss - current_price) / stop_loss) * 100
                                self.logger.warning(f"🚨 {ticker}: Gap breach detected! Current: ₹{current_price:.2f} < Stop: ₹{stop_loss:.2f} (gap: {gap_percent:.1f}%)")
                                # The check_atr_stop_loss will handle the order placement
                                self.check_atr_stop_loss(ticker, current_price)
            
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
                    "zerodha_position": False,  # Flag to indicate this came from orders file
                    "entry_timestamp": order_timestamp  # Use order timestamp as entry time
                }
                
                # Initialize highest price tracking with entry price
                self.position_high_prices[ticker] = entry_price

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
            token = self.get_instrument_token(ticker)
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
            token = self.get_instrument_token(ticker)
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
    
    def load_all_order_files(self) -> List[Dict]:
        """Load all order files for the user to find position entries"""
        order_files = []
        order_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Current_Orders', self.user_name)
        
        if not os.path.exists(order_dir):
            self.logger.warning(f"Order directory not found: {order_dir}")
            return order_files
        
        # Get all order files sorted by date (most recent first)
        pattern = f"orders_{self.user_name}_*.json"
        files = glob.glob(os.path.join(order_dir, pattern))
        
        for file_path in sorted(files, reverse=True):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    data['_filename'] = os.path.basename(file_path)
                    order_files.append(data)
                    self.logger.debug(f"Loaded order file: {os.path.basename(file_path)}")
            except Exception as e:
                self.logger.warning(f"Failed to load {file_path}: {e}")
        
        self.logger.info(f"Loaded {len(order_files)} order files for user {self.user_name}")
        return order_files
    
    def find_position_entry(self, ticker: str, order_files: List[Dict]) -> Optional[Dict]:
        """Find when we entered a position by searching through order files"""
        entries = []
        
        for order_file in order_files:
            for order in order_file.get('orders', []):
                # Match ticker in different formats
                order_ticker = order.get('ticker') or order.get('tradingsymbol')
                if order_ticker == ticker:
                    # Check if it's a BUY order
                    if order.get('transaction_type', 'BUY') == 'BUY':
                        entry_data = {
                            'order_timestamp': order.get('order_timestamp'),
                            'average_price': float(order.get('average_price', order.get('current_price', 0))),
                            'quantity': int(order.get('quantity', order.get('position_size', 0))),
                            'stop_loss': float(order.get('stop_loss', 0)),
                            'target_price': float(order.get('target_price', 0)),
                            'source_file': order_file.get('_filename', 'unknown')
                        }
                        # Only add if we have valid timestamp
                        if entry_data['order_timestamp']:
                            entries.append(entry_data)
                            self.logger.debug(f"Found entry for {ticker} in {entry_data['source_file']}: "
                                            f"{entry_data['quantity']} @ ₹{entry_data['average_price']:.2f}")
        
        if not entries:
            self.logger.warning(f"No entry found for {ticker} in order files")
            return None
        
        # Return the earliest entry
        earliest = min(entries, key=lambda x: x['order_timestamp'])
        self.logger.info(f"{ticker}: Using entry from {earliest['source_file']} - "
                        f"{earliest['quantity']} shares @ ₹{earliest['average_price']:.2f} "
                        f"on {earliest['order_timestamp']}")
        return earliest
    
    def calculate_position_high_since_entry(self, ticker: str, entry_timestamp: str) -> float:
        """Calculate the highest price since position entry using historical data"""
        try:
            # Check cache first
            cache_key = f"{ticker}_high_{entry_timestamp}"
            if cache_key in self.historical_cache:
                cached_data, cache_time = self.historical_cache[cache_key]
                if time.time() - cache_time < self.cache_ttl:
                    return cached_data
            
            token = self.get_instrument_token(ticker)
            if token is None:
                self.logger.error(f"Token not found for {ticker}")
                return 0
            
            # Parse entry timestamp with flexibility for different formats
            if isinstance(entry_timestamp, str):
                # Remove 'Z' suffix if present and handle ISO format
                entry_timestamp = entry_timestamp.replace('Z', '+00:00')
                # Try parsing with fromisoformat first (Python 3.7+)
                try:
                    entry_date = datetime.fromisoformat(entry_timestamp)
                except:
                    # Fallback to strptime for other formats
                    try:
                        entry_date = datetime.strptime(entry_timestamp[:19], '%Y-%m-%dT%H:%M:%S')
                    except:
                        entry_date = datetime.strptime(entry_timestamp[:10], '%Y-%m-%d')
            else:
                entry_date = entry_timestamp
            today = datetime.now()
            days_held = (today - entry_date).days
            
            position_high = 0
            
            # For positions held less than 60 days, we can use minute data for precision
            if days_held <= 60:
                # Fetch daily data first to get overall highs
                daily_data = self.kite.historical_data(
                    token,
                    entry_date.date(),
                    today.date(),
                    "day"
                )
                
                if daily_data:
                    position_high = max([candle['high'] for candle in daily_data])
                    self.logger.debug(f"{ticker}: Daily high since entry: ₹{position_high:.2f}")
                
                # For today, also check intraday high for more precision
                if today.date() == datetime.now().date():
                    try:
                        intraday_start = today.replace(hour=9, minute=15, second=0, microsecond=0)
                        intraday_data = self.kite.historical_data(
                            token,
                            intraday_start,
                            today,
                            "minute"
                        )
                        if intraday_data:
                            intraday_high = max([candle['high'] for candle in intraday_data])
                            position_high = max(position_high, intraday_high)
                            self.logger.debug(f"{ticker}: Including today's intraday high: ₹{intraday_high:.2f}")
                    except Exception as e:
                        self.logger.warning(f"Could not fetch intraday data for {ticker}: {e}")
            
            else:
                # For older positions, use daily data only
                daily_data = self.kite.historical_data(
                    token,
                    entry_date.date(),
                    today.date(),
                    "day"
                )
                
                if daily_data:
                    position_high = max([candle['high'] for candle in daily_data])
                    self.logger.debug(f"{ticker}: Daily high since entry (long-term position): ₹{position_high:.2f}")
            
            # Cache the result
            self.historical_cache[cache_key] = (position_high, time.time())
            
            return position_high
            
        except Exception as e:
            self.logger.error(f"Error calculating position high for {ticker}: {e}")
            return 0
    
    def reconstruct_position_state(self, ticker: str, broker_position: Dict, order_files: List[Dict]) -> Dict:
        """Reconstruct complete position state from broker data and order history"""
        try:
            # Find entry data from order files
            entry_data = self.find_position_entry(ticker, order_files)
            
            if not entry_data:
                # Handle positions with no order history (transferred in, etc.)
                self.logger.warning(f"{ticker}: No order history found, using conservative approach")
                # Use 30-day lookback as conservative approach
                lookback_date = datetime.now() - timedelta(days=30)
                entry_data = {
                    'order_timestamp': lookback_date.isoformat(),
                    'average_price': broker_position.get('average_price', broker_position.get('last_price', 0)),
                    'quantity': broker_position.get('quantity', 0),
                    'stop_loss': 0,
                    'target_price': 0,
                    'source_file': 'reconstructed'
                }
            
            # Calculate position high since entry
            position_high = self.calculate_position_high_since_entry(ticker, entry_data['order_timestamp'])
            
            # If position high calculation failed, use current price
            if position_high <= 0:
                current_price = broker_position.get('last_price', entry_data['average_price'])
                position_high = max(current_price, entry_data['average_price'])
                self.logger.warning(f"{ticker}: Using current/entry price as position high: ₹{position_high:.2f}")
            
            # Calculate current ATR and stop loss
            atr_data = self.calculate_atr_and_stop_loss(ticker)
            if not atr_data:
                self.logger.error(f"{ticker}: Could not calculate ATR")
                return None
            
            # Calculate trailing stop from position high
            stop_distance = atr_data['stop_loss_distance']
            trailing_stop = position_high - stop_distance
            
            # Never let stop go below initial stop (if provided)
            if entry_data.get('stop_loss', 0) > 0:
                trailing_stop = max(trailing_stop, entry_data['stop_loss'])
            
            return {
                'ticker': ticker,
                'entry_timestamp': entry_data['order_timestamp'],
                'entry_price': entry_data['average_price'],
                'quantity': broker_position.get('quantity', 0),
                'original_quantity': entry_data.get('quantity', broker_position.get('quantity', 0)),
                'position_high': position_high,
                'current_stop_loss': trailing_stop,
                'atr_data': atr_data,
                'initial_stop_loss': entry_data.get('stop_loss', 0),
                'target_price': entry_data.get('target_price', 0),
                'source': entry_data['source_file']
            }
            
        except Exception as e:
            self.logger.error(f"Error reconstructing state for {ticker}: {e}")
            return None
    
    def update_atr_stop_losses(self):
        """Update ATR-based stop losses for all tracked positions (daily basis)"""
        try:
            current_time = time.time()
            # Only update ATR data once per day (24 hours = 86400 seconds) or on first run
            # Check if we've updated recently (within 24 hours)
            if self.last_atr_check > 0 and (current_time - self.last_atr_check < 86400):  # 24 hours
                return

            # If no positions to track, skip update but still update the timestamp
            if not self.tracked_positions:
                self.last_atr_check = current_time
                return

            self.last_atr_check = current_time
            self.logger.info("Updating ATR-based stop losses for all positions (Daily Update)")

            for ticker in self.tracked_positions.keys():
                try:
                    # First calculate ATR
                    atr_result = self.calculate_atr_and_stop_loss(ticker)
                    if not atr_result:
                        self.logger.warning(f"Could not calculate ATR data for {ticker}")
                        continue

                    # Get the position high (highest price since position entry)
                    position_high = self.position_high_prices.get(ticker, 0)
                    current_price = self.current_prices.get(ticker, 0)
                    
                    # Use the higher of position_high or current_price (in case position_high not yet set)
                    if current_price > position_high:
                        position_high = current_price
                        self.position_high_prices[ticker] = position_high
                    
                    # If no position high available, try to get from entry price
                    if position_high <= 0:
                        position_data = self.tracked_positions.get(ticker, {})
                        entry_price = position_data.get('entry_price', 0)
                        if entry_price > 0:
                            position_high = entry_price
                            self.position_high_prices[ticker] = position_high
                            self.logger.info(f"{ticker}: Initialized position high with entry price: ₹{position_high:.2f}")
                    
                    if position_high > 0:
                        # Calculate stop loss based on ATR and position high
                        atr_value = atr_result['atr']
                        multiplier = atr_result['multiplier']
                        volatility_category = atr_result['volatility_category']
                        atr_percentage = atr_result['atr_percentage']

                        old_data = self.atr_data.get(ticker, {})
                        old_stop_loss = old_data.get('stop_loss', 0)

                        # Calculate new stop loss from position high
                        new_stop_loss = position_high - (atr_value * multiplier)

                        # Update the ATR data with the new stop loss
                        atr_result['stop_loss'] = new_stop_loss
                        atr_result['position_high'] = position_high
                        self.atr_data[ticker] = atr_result

                        # Log the update with position high information
                        self.logger.info(f"{ticker}: ATR Stop Loss Updated - "
                                       f"ATR: ₹{atr_value:.2f} ({atr_percentage:.2f}%), "
                                       f"{volatility_category} Volatility, "
                                       f"Multiplier: {multiplier}x, "
                                       f"Position High: ₹{position_high:.2f}, "
                                       f"Stop Loss: ₹{new_stop_loss:.2f} (was ₹{old_stop_loss:.2f})")
                    else:
                        # If we couldn't get position high, just use regular ATR stop
                        self.atr_data[ticker] = atr_result
                        new_stop_loss = atr_result['stop_loss']
                        old_stop_loss = old_data.get('stop_loss', 0)

                        self.logger.info(f"{ticker}: ATR Stop Loss Updated (no position high) - "
                                       f"ATR: ₹{atr_result['atr']:.2f} ({atr_result['atr_percentage']:.2f}%), "
                                       f"{atr_result['volatility_category']} Volatility, "
                                       f"Multiplier: {atr_result['multiplier']}x, "
                                       f"Stop Loss: ₹{new_stop_loss:.2f} (was ₹{old_stop_loss:.2f})")
                    
                    # Also fetch and store daily high for reference (backward compatibility)
                    daily_high = self.fetch_daily_high(ticker)
                    if daily_high:
                        self.daily_high_prices[ticker] = daily_high

                except Exception as e:
                    self.logger.error(f"Error updating ATR stop loss for {ticker}: {e}")

            time.sleep(0.5)  # Small delay between API calls

        except Exception as e:
            self.logger.error(f"Error updating ATR stop losses: {e}")
    
    def check_sma20_hourly_violations(self, ticker) -> Optional[Dict]:
        """Check SMA20 violations on hourly timeframe and return analysis
        
        Uses last 3 trading days of hourly data for more stable analysis
        """
        try:
            token = self.get_instrument_token(ticker)
            if token is None:
                self.logger.error(f"Token not found for {ticker}. Cannot check SMA20 hourly violations.")
                return None

            # Get hourly data for the last 3 trading days
            ist = pytz.timezone('Asia/Kolkata')
            now = datetime.now(ist)
            
            # Start from 3 trading days ago (accounting for weekends)
            # If today is Monday, go back to previous Wednesday
            # If today is Tuesday, go back to previous Thursday
            # Otherwise go back 3 days
            days_back = 3
            if now.weekday() == 0:  # Monday
                days_back = 5  # Go back to Wednesday
            elif now.weekday() == 1:  # Tuesday
                days_back = 5  # Go back to Thursday
            elif now.weekday() == 2:  # Wednesday
                days_back = 5  # Go back to Friday
                
            analysis_start = now - timedelta(days=days_back)
            analysis_start = analysis_start.replace(hour=9, minute=15, second=0, microsecond=0)
            end_date = now

            # Get additional historical data for proper SMA20 calculation
            history_start = analysis_start - timedelta(days=10)  # Get extra history for SMA calculation
            historical_hourly = self.kite.historical_data(token, history_start, end_date, "60minute")
            
            if len(historical_hourly) >= 20:
                df_full = pd.DataFrame(historical_hourly)
                df_full['SMA20'] = df_full['close'].rolling(window=20).mean()
                
                # Filter to only market hours (9:15 AM to 3:30 PM)
                df_full['date'] = pd.to_datetime(df_full['date'])
                df_full['hour'] = df_full['date'].dt.hour
                df_full['minute'] = df_full['date'].dt.minute
                market_hours_mask = ((df_full['hour'] == 9) & (df_full['minute'] >= 15)) | \
                                  ((df_full['hour'] >= 10) & (df_full['hour'] <= 14)) | \
                                  ((df_full['hour'] == 15) & (df_full['minute'] <= 30))
                
                # Get last 3 trading days data with proper SMA20 values
                analysis_mask = (df_full['date'] >= analysis_start) & market_hours_mask
                analysis_data = df_full[analysis_mask].copy()
                
                if len(analysis_data) > 0:
                    # Count violations and hours above SMA20
                    violations = 0
                    hours_above = 0
                    total_hours = 0
                    
                    for idx, row in analysis_data.iterrows():
                        if pd.notna(row['SMA20']):
                            total_hours += 1
                            if row['close'] < row['SMA20']:
                                violations += 1
                            else:
                                hours_above += 1
                    
                    # Calculate ratio
                    sma20_above_ratio = hours_above / total_hours if total_hours > 0 else 0
                    
                    # Get today's specific data if available
                    today_mask = df_full['date'].dt.date == now.date()
                    today_data = df_full[today_mask & market_hours_mask]
                    today_violations = 0
                    if len(today_data) > 0:
                        for idx, row in today_data.iterrows():
                            if pd.notna(row['SMA20']) and row['close'] < row['SMA20']:
                                today_violations += 1
                    
                    result = {
                        'sma20_violations': violations,
                        'hours_monitored': total_hours,
                        'hours_above_sma20': hours_above,
                        'sma20_above_ratio': sma20_above_ratio,
                        'today_violations': today_violations,
                        'analysis_days': days_back,
                        'latest_close': analysis_data['close'].iloc[-1] if len(analysis_data) > 0 else None,
                        'latest_sma20': analysis_data['SMA20'].iloc[-1] if len(analysis_data) > 0 and pd.notna(analysis_data['SMA20'].iloc[-1]) else None
                    }
                    
                    self.logger.debug(f"{ticker} SMA20 Hourly (Last {days_back} days): Violations={violations}, "
                                    f"Hours Above={hours_above}/{total_hours} ({sma20_above_ratio:.1%}), "
                                    f"Today's violations={today_violations}")
                    
                    return result
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking SMA20 hourly violations for {ticker}: {e}")
            return None
    
    def update_sma20_hourly_data(self):
        """Update SMA20 hourly data for all tracked positions"""
        try:
            current_time = time.time()
            # Update every 30 minutes during market hours
            if current_time - self.last_sma20_check < 1800:  # 30 minutes
                return
            
            self.last_sma20_check = current_time
            self.logger.info("Updating SMA20 hourly data for all positions")
            
            for ticker in self.tracked_positions.keys():
                try:
                    sma20_result = self.check_sma20_hourly_violations(ticker)
                    if sma20_result:
                        self.sma20_hourly_data[ticker] = sma20_result
                        
                        # Check exit conditions based on SMA20 violations
                        violations = sma20_result['sma20_violations']
                        sma20_ratio = sma20_result['sma20_above_ratio']
                        
                        # Log warning if approaching exit conditions
                        if violations >= 1:
                            self.logger.warning(f"{ticker}: SMA20 hourly violations detected: {violations} "
                                              f"(Exit at 2+ violations)")
                        
                        if sma20_ratio < 0.9 and sma20_ratio >= 0.8:
                            self.logger.warning(f"{ticker}: SMA20 above ratio low: {sma20_ratio:.1%} "
                                              f"(Exit at <80%)")
                        
                except Exception as e:
                    self.logger.error(f"Error updating SMA20 hourly data for {ticker}: {e}")
                
                time.sleep(0.5)  # Small delay between API calls
                
        except Exception as e:
            self.logger.error(f"Error in update_sma20_hourly_data: {e}")
    
    def sync_positions_with_broker(self):
        """Periodically sync tracked positions with actual broker positions"""
        try:
            current_time = time.time()
            # Sync every 10 minutes
            if current_time - self.last_position_sync < 600:  # 10 minutes
                return
            
            self.last_position_sync = current_time
            self.logger.info("Syncing positions with broker...")
            
            # Get current positions from broker
            positions = self.kite.positions()
            holdings = self.kite.holdings()
            
            # Build a set of actual positions and calculate PnL
            actual_positions = set()
            position_pnl_data = {}
            total_realized_pnl = 0
            total_unrealized_pnl = 0
            total_investment = 0
            
            # Check net positions for PnL
            for position in positions.get('net', []):
                if position.get('product') == 'CNC':
                    ticker = position.get('tradingsymbol', '').upper()
                    quantity = int(position.get('quantity', 0))
                    
                    if quantity > 0:
                        actual_positions.add(ticker)
                        
                        # Calculate PnL for this position
                        buy_value = float(position.get('buy_value', 0))
                        sell_value = float(position.get('sell_value', 0))
                        realized_pnl = float(position.get('realised', 0))
                        unrealized_pnl = float(position.get('unrealised', 0))
                        ltp = float(position.get('last_price', 0))
                        avg_price = float(position.get('average_price', 0))
                        
                        position_pnl_data[ticker] = {
                            'quantity': quantity,
                            'avg_price': avg_price,
                            'ltp': ltp,
                            'realized_pnl': realized_pnl,
                            'unrealized_pnl': unrealized_pnl,
                            'buy_value': buy_value,
                            'sell_value': sell_value
                        }
                        
                        total_realized_pnl += realized_pnl
                        total_unrealized_pnl += unrealized_pnl
                        if buy_value > 0:
                            total_investment += buy_value
            
            # Check holdings (including T1 positions) for PnL
            for holding in holdings:
                ticker = holding.get('tradingsymbol', '').upper()
                quantity = int(holding.get('quantity', 0))
                t1_quantity = int(holding.get('t1_quantity', 0))
                total_quantity = quantity + t1_quantity
                
                if total_quantity > 0:
                    actual_positions.add(ticker)
                    
                    # Calculate PnL if not already in positions
                    if ticker not in position_pnl_data:
                        avg_price = float(holding.get('average_price', 0))
                        ltp = float(holding.get('last_price', 0))
                        pnl = float(holding.get('pnl', 0))
                        
                        position_pnl_data[ticker] = {
                            'quantity': total_quantity,
                            'avg_price': avg_price,
                            'ltp': ltp,
                            'unrealized_pnl': pnl,
                            'realized_pnl': 0,
                            't1_quantity': t1_quantity
                        }
                        
                        total_unrealized_pnl += pnl
                        if avg_price > 0 and total_quantity > 0:
                            total_investment += (avg_price * total_quantity)
                    
                    if t1_quantity > 0:
                        self.logger.debug(f"Found T1 holding: {holding.get('tradingsymbol', '')} - "
                                        f"Settled: {quantity}, T1: {t1_quantity}, Total: {total_quantity}")
            
            # Log PnL Summary
            self.logger.info("=" * 60)
            self.logger.info("PORTFOLIO P&L SUMMARY")
            self.logger.info("=" * 60)
            
            # Log individual position PnL
            for ticker_upper, pnl_data in sorted(position_pnl_data.items()):
                # Find original case ticker
                original_ticker = None
                for t in self.tracked_positions.keys():
                    if t.upper() == ticker_upper:
                        original_ticker = t
                        break
                
                if original_ticker:
                    quantity = pnl_data['quantity']
                    avg_price = pnl_data['avg_price']
                    ltp = pnl_data['ltp']
                    unrealized = pnl_data['unrealized_pnl']
                    realized = pnl_data['realized_pnl']
                    total_pnl = unrealized + realized
                    
                    # Calculate percentage returns
                    if avg_price > 0 and quantity > 0:
                        investment = avg_price * quantity
                        pnl_percentage = (total_pnl / investment) * 100
                    else:
                        pnl_percentage = 0
                    
                    # Determine PnL status
                    pnl_status = "🟢" if total_pnl >= 0 else "🔴"
                    
                    self.logger.info(
                        f"{pnl_status} {original_ticker}: Qty={quantity}, "
                        f"Avg=₹{avg_price:.2f}, LTP=₹{ltp:.2f}, "
                        f"P&L=₹{total_pnl:,.2f} ({pnl_percentage:+.2f}%), "
                        f"Unreal=₹{unrealized:,.2f}, Real=₹{realized:,.2f}"
                    )
            
            # Log total portfolio PnL
            total_pnl = total_realized_pnl + total_unrealized_pnl
            if total_investment > 0:
                total_pnl_percentage = (total_pnl / total_investment) * 100
            else:
                total_pnl_percentage = 0
            
            self.logger.info("=" * 60)
            self.logger.info(f"TOTAL INVESTMENT: ₹{total_investment:,.2f}")
            self.logger.info(f"TOTAL REALIZED P&L: ₹{total_realized_pnl:,.2f}")
            self.logger.info(f"TOTAL UNREALIZED P&L: ₹{total_unrealized_pnl:,.2f}")
            self.logger.info(f"TOTAL P&L: ₹{total_pnl:,.2f} ({total_pnl_percentage:+.2f}%)")
            self.logger.info("=" * 60)
            
            # Find positions that are tracked but don't exist in broker
            tracked_tickers = set(ticker.upper() for ticker in self.tracked_positions.keys())
            ghost_positions = tracked_tickers - actual_positions
            
            # Remove ghost positions
            if ghost_positions:
                self.logger.warning(f"Found {len(ghost_positions)} ghost positions: {ghost_positions}")
                for ticker in ghost_positions:
                    # Find the original case ticker
                    original_ticker = None
                    for t in self.tracked_positions.keys():
                        if t.upper() == ticker:
                            original_ticker = t
                            break
                    
                    if original_ticker:
                        self.logger.warning(f"Removing ghost position: {original_ticker}")
                        self.remove_position_from_tracking(original_ticker)
            
            self.logger.info(f"Position sync complete. Tracking {len(self.tracked_positions)} positions.")
            
        except Exception as e:
            self.logger.error(f"Error syncing positions with broker: {e}")
    
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

                                    # Update position high if current price is higher than any price since position entry
                                    if ticker not in self.position_high_prices:
                                        # Initialize with current price if not set
                                        self.position_high_prices[ticker] = price
                                        self.logger.debug(f"{ticker}: Initialized position high price: ₹{price:.2f}")
                                    elif price > self.position_high_prices[ticker]:
                                        old_high = self.position_high_prices[ticker]
                                        self.position_high_prices[ticker] = price
                                        self.peak_warning_issued[ticker] = False  # Reset warning when new peak is reached
                                        
                                        # Recalculate trailing stop with new position high
                                        if ticker in self.atr_data:
                                            atr_data = self.atr_data[ticker]
                                            stop_distance = atr_data.get('stop_loss_distance', 0)
                                            
                                            if stop_distance > 0:
                                                new_trailing_stop = price - stop_distance
                                                old_stop = atr_data.get('stop_loss', 0)
                                                
                                                # Only update if new stop is higher (trailing stop only moves up)
                                                if new_trailing_stop > old_stop:
                                                    atr_data['stop_loss'] = new_trailing_stop
                                                    atr_data['position_high'] = price
                                                    
                                                    self.logger.info(f"{ticker}: POSITION HIGH TRAILING STOP UPDATED - New: ₹{new_trailing_stop:.2f} "
                                                                   f"(from: ₹{old_stop:.2f}), Based on position high: ₹{price:.2f}, "
                                                                   f"ATR: ₹{atr_data['atr']:.2f} ({atr_data['volatility_category']} volatility)")
                                                else:
                                                    self.logger.debug(f"{ticker}: New position high ₹{price:.2f} but stop remains at ₹{old_stop:.2f}")
                                        else:
                                            self.logger.debug(f"{ticker}: Updated position high: ₹{price:.2f} (was: ₹{old_high:.2f}) - No ATR data yet")
                                    
                                    # Check for 2% drop from peak
                                    position_high = self.position_high_prices.get(ticker, price)
                                    if position_high > 0:
                                        drop_from_peak_pct = ((position_high - price) / position_high) * 100
                                        if drop_from_peak_pct >= 2.0 and not self.peak_warning_issued.get(ticker, False):
                                            self.logger.warning(f"⚠️  {ticker}: Price dropped {drop_from_peak_pct:.1f}% from peak! Current: ₹{price:.2f}, Peak: ₹{position_high:.2f}")
                                            self.peak_warning_issued[ticker] = True
                                    
                                    # Also update daily high for backward compatibility
                                    if ticker in self.daily_high_prices and price > self.daily_high_prices[ticker]:
                                        self.daily_high_prices[ticker] = price

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
    
    def calculate_vsr(self, high, low, volume):
        """Calculate Volume Spread Ratio (VSR)"""
        if high <= low or volume == 0:
            return 0
        spread = high - low
        if spread == 0:
            return 0
        return volume / spread
    
    def check_vsr_conditions(self, ticker):
        """Check VSR-based exit conditions
        Returns signal dict if exit conditions are met, None otherwise
        """
        # Check if VSR exit is enabled
        if not self.vsr_exit_enabled:
            return None
            
        try:
            # Check if we have position data
            if ticker not in self.tracked_positions:
                return None
            
            position_data = self.tracked_positions[ticker]
            
            # Get current time
            current_time = datetime.now()
            
            # Initialize VSR data for this ticker if not exists
            if ticker not in self.vsr_data:
                self.vsr_data[ticker] = {
                    'entry_vsr': None,
                    'current_vsr': None,
                    'vsr_history': [],
                    'last_hourly_check': None
                }
            
            vsr_info = self.vsr_data[ticker]
            
            # Only check based on configured interval
            if vsr_info['last_hourly_check']:
                time_since_last_check = current_time - vsr_info['last_hourly_check']
                check_interval_seconds = self.vsr_check_interval_hours * 3600
                if time_since_last_check.total_seconds() < check_interval_seconds:
                    return None
            
            # Get hourly candle data
            token = self.get_instrument_token(ticker)
            if not token:
                self.logger.error(f"Cannot get instrument token for {ticker}")
                return None
            
            try:
                # Get last 2 hours of data
                end_date = current_time
                start_date = current_time - timedelta(hours=2)
                
                hourly_data = self.kite.historical_data(
                    token, 
                    start_date.strftime("%Y-%m-%d %H:%M:%S"), 
                    end_date.strftime("%Y-%m-%d %H:%M:%S"), 
                    "60minute"
                )
                
                if not hourly_data:
                    return None
                
                # Get the latest completed hourly candle
                latest_candle = hourly_data[-1]
                current_vsr = self.calculate_vsr(
                    latest_candle['high'],
                    latest_candle['low'],
                    latest_candle['volume']
                )
                
                # Update current VSR
                vsr_info['current_vsr'] = current_vsr
                vsr_info['last_hourly_check'] = current_time
                
                # If we don't have entry VSR, set it
                if vsr_info['entry_vsr'] is None:
                    vsr_info['entry_vsr'] = current_vsr
                    self.logger.info(f"{ticker}: Setting entry VSR to {current_vsr:.2f}")
                    return None
                
                # Add to history
                vsr_info['vsr_history'].append({
                    'timestamp': current_time,
                    'vsr': current_vsr
                })
                
                # Keep only last 24 hours of history
                if len(vsr_info['vsr_history']) > 24:
                    vsr_info['vsr_history'] = vsr_info['vsr_history'][-24:]
                
                # Check if current VSR has dropped below configured threshold of entry VSR
                entry_vsr = vsr_info['entry_vsr']
                vsr_threshold = entry_vsr * (self.vsr_exit_threshold / 100.0)
                
                if current_vsr < vsr_threshold:
                    vsr_drop_percent = ((entry_vsr - current_vsr) / entry_vsr) * 100
                    self.logger.warning(f"{ticker}: VSR EXIT SIGNAL - Current VSR ({current_vsr:.2f}) < {self.vsr_exit_threshold}% of entry VSR ({entry_vsr:.2f})")
                    return {
                        'signal': True,
                        'reason': f'VSR dropped {vsr_drop_percent:.1f}% from entry (Current: {current_vsr:.2f}, Entry: {entry_vsr:.2f})'
                    }
                
            except Exception as e:
                self.logger.error(f"Error fetching hourly data for {ticker}: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error in check_vsr_conditions for {ticker}: {e}")
            return None
        
        return None
    
    def check_loss_threshold(self, ticker, current_price):
        """Check if position has reached configured loss threshold
        Returns signal dict if exit conditions are met, None otherwise
        """
        # Check if loss threshold exit is enabled
        if not self.loss_threshold_enabled:
            return None
            
        try:
            if ticker not in self.tracked_positions:
                return None
            
            position_data = self.tracked_positions[ticker]
            entry_price = position_data.get('entry_price', 0)
            
            if entry_price <= 0:
                return None
            
            # Calculate current loss percentage
            loss_percent = ((current_price - entry_price) / entry_price) * 100
            
            # Check if loss exceeds configured threshold
            if loss_percent <= -self.loss_threshold_percent:
                self.logger.warning(f"{ticker}: LOSS THRESHOLD EXIT SIGNAL - Loss: {loss_percent:.2f}%")
                return {
                    'signal': True,
                    'reason': f'Loss threshold breached: {loss_percent:.2f}% (Price: {current_price:.2f}, Entry: {entry_price:.2f})'
                }
                
        except Exception as e:
            self.logger.error(f"Error in check_loss_threshold for {ticker}: {e}")
            
        return None
    
    def check_candle_length_conditions(self, ticker):
        """Check if hourly candle length exceeds configured multiple of ATR
        Returns signal dict if exit conditions are met, None otherwise
        """
        # Check if candle length exit is enabled
        if not self.candle_length_exit_enabled:
            return None
            
        try:
            if ticker not in self.tracked_positions:
                return None
                
            # Get ATR data
            if ticker not in self.atr_data:
                return None
                
            atr_value = self.atr_data[ticker]['atr']
            
            # Get current time
            current_time = datetime.now()
            
            # Get hourly candle data
            token = self.get_instrument_token(ticker)
            if not token:
                return None
                
            try:
                # Get last 2 hours of data
                end_date = current_time
                start_date = current_time - timedelta(hours=2)
                
                hourly_data = self.kite.historical_data(
                    token, 
                    start_date.strftime("%Y-%m-%d %H:%M:%S"), 
                    end_date.strftime("%Y-%m-%d %H:%M:%S"), 
                    "60minute"
                )
                
                if not hourly_data:
                    return None
                
                # Get the latest completed hourly candle
                latest_candle = hourly_data[-1]
                candle_length = latest_candle['high'] - latest_candle['low']
                
                # Check if candle length exceeds threshold
                length_threshold = atr_value * self.candle_length_multiplier
                
                if candle_length > length_threshold:
                    length_ratio = candle_length / atr_value
                    self.logger.warning(f"{ticker}: CANDLE LENGTH EXIT SIGNAL - Hourly candle length ({candle_length:.2f}) > {self.candle_length_multiplier}x ATR ({atr_value:.2f})")
                    return {
                        'signal': True,
                        'reason': f'Hourly candle length {length_ratio:.1f}x ATR (Length: {candle_length:.2f}, ATR: {atr_value:.2f})'
                    }
                    
            except Exception as e:
                self.logger.error(f"Error fetching hourly data for candle length check on {ticker}: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error in check_candle_length_conditions for {ticker}: {e}")
            
        return None
    
    def check_atr_stop_loss(self, ticker, current_price):
        """Check if current price is below ATR-based trailing stop loss with partial exits and SMA20 violations"""
        if ticker not in self.atr_data:
            return

        # Check if this position already has a pending order
        if self.tracked_positions[ticker].get("has_pending_order", False):
            self.logger.debug(f"Skipping ATR stop loss check for {ticker} as it already has a pending order")
            return
            
        # Also check if any order was placed recently (within last 5 minutes)
        last_order_time = self.tracked_positions[ticker].get("last_order_time")
        if last_order_time:
            time_since_order = datetime.now() - last_order_time
            if time_since_order.total_seconds() < 300:  # 5 minutes
                self.logger.info(f"{ticker}: Skipping ATR check - recent order placed {time_since_order.total_seconds():.0f}s ago")
                return
        
        # Pre-order validation: Verify position exists with broker
        position_data = self.tracked_positions.get(ticker, {})
        expected_quantity = position_data.get("quantity", 0)
        
        if not self.verify_position_exists(ticker, expected_quantity):
            self.logger.warning(f"{ticker}: Position not found or has 0 quantity in broker account. Removing from tracking.")
            self.remove_position_from_tracking(ticker)
            return
        

        # Check VSR conditions (hourly)
        vsr_signal = self.check_vsr_conditions(ticker)
        if vsr_signal:
            # Queue order for VSR-based exit
            self.queue_order(
                ticker,
                expected_quantity,
                "SELL",
                f"VSR_EXIT: {vsr_signal['reason']}",
                current_price
            )
            return

        # Check -2% loss threshold
        loss_signal = self.check_loss_threshold(ticker, current_price)
        if loss_signal:
            # Queue order for loss threshold exit
            self.queue_order(
                ticker,
                expected_quantity,
                "SELL",
                f"LOSS_EXIT: {loss_signal['reason']}",
                current_price
            )
            return

        # Check candle length conditions (hourly)
        candle_signal = self.check_candle_length_conditions(ticker)
        if candle_signal:
            # Queue order for candle length exit
            self.queue_order(
                ticker,
                expected_quantity,
                "SELL",
                f"CANDLE_EXIT: {candle_signal['reason']}",
                current_price
            )
            return

        # SMA20 violation checks are now only done at 2:30 PM IST
        # See check_sma20_exit_at_230pm() method

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

        # If exit_tranches is not set, initialize it based on volatility (only if profit targets are enabled)
        if not exit_tranches and self.profit_target_exits_enabled:
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

        # Check if position high has been updated
        if ticker in self.position_high_prices:
            position_high = self.position_high_prices[ticker]
            stored_position_high = atr_info.get('position_high', 0)

            # If the position high has increased, recalculate trailing stop
            if position_high > stored_position_high:
                # Calculate the new stop loss based on the position high
                new_stop_loss = position_high - (atr_value * multiplier)

                # Only adjust stop loss upward, never downward (trailing feature)
                if new_stop_loss > stop_loss_price:
                    old_stop_loss = stop_loss_price
                    self.atr_data[ticker]['stop_loss'] = new_stop_loss
                    self.atr_data[ticker]['position_high'] = position_high

                    # Log the trailing stop update
                    self.logger.info(f"{ticker}: POSITION HIGH TRAILING STOP UPDATED - New: ₹{new_stop_loss:.2f} (from: ₹{old_stop_loss:.2f}), "
                                  f"Based on position high: ₹{position_high:.2f}, ATR: ₹{atr_value:.2f} ({volatility_category} volatility)")

                    # Update the stop loss price for the current check
                    stop_loss_price = new_stop_loss

        # Log the ATR stop loss check for transparency
        self.logger.debug(f"ATR Stop Loss Check - {ticker}: Current Price: ₹{current_price:.2f}, "
                         f"Stop Loss: ₹{stop_loss_price:.2f}, ATR: ₹{atr_value:.2f} ({atr_percentage:.2f}%), "
                         f"{volatility_category} Volatility ({multiplier}x)")

        # 1. Check stop loss
        if current_price <= stop_loss_price:
            # If profit targets are disabled, sell full position
            if not self.profit_target_exits_enabled:
                sell_quantity = current_quantity
                sell_percent = 100
            else:
                # Use partial exit strategy
                stop_loss_tranche = exit_tranches.get("stop_loss", {"percent_of_position": 100, "triggered": False})
                if stop_loss_tranche["triggered"]:
                    return  # Already processed this stop loss
                sell_percent = stop_loss_tranche["percent_of_position"]
                sell_quantity = int(original_quantity * sell_percent / 100)
                # Ensure we sell at least 1 share and not more than available
                sell_quantity = max(1, min(sell_quantity, current_quantity))

            # Get appropriate tick size for this ticker
            tick_size = self.get_tick_size(ticker)

            # LONG position: SELL order slightly below stop loss
            raw_price = stop_loss_price * 0.995
            order_price = self.round_to_tick_size(raw_price, tick_size)

            self.logger.info(f"ATR STOP LOSS TRIGGERED - {ticker}: Current Price ₹{current_price:.2f} fell below "
                           f"ATR Stop Loss ₹{stop_loss_price:.2f} ({volatility_category} volatility, {multiplier}x ATR). "
                           f"Queuing SELL order for {sell_quantity} shares ({sell_percent}% of position) at ₹{order_price:.2f} "
                           f"(tick size: {tick_size}).")

            # Queue the order - use full order method if selling entire position
            if sell_percent == 100 and not self.profit_target_exits_enabled:
                self.queue_order(ticker, sell_quantity, "SELL",
                               f"ATR stop loss breach - Current: ₹{current_price:.2f}, "
                               f"Stop Loss: ₹{stop_loss_price:.2f}, ATR: ₹{atr_value:.2f} ({atr_percentage:.2f}%), "
                               f"{volatility_category} volatility ({multiplier}x)", order_price)
            else:
                self.queue_partial_order(ticker, sell_quantity, "SELL",
                               f"ATR stop loss breach - Current: ₹{current_price:.2f}, "
                               f"Stop Loss: ₹{stop_loss_price:.2f}, ATR: ₹{atr_value:.2f} ({atr_percentage:.2f}%), "
                               f"{volatility_category} volatility ({multiplier}x)", order_price, "stop_loss")

            return

        # 2. Check profit target tranches - only if enabled and above entry price
        if self.profit_target_exits_enabled and current_price > entry_price:
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
        
        # Pre-order validation for SELL orders
        if transaction_type == "SELL":
            if not self.verify_position_exists(ticker, None):
                self.logger.warning(f"{ticker}: Cannot queue SELL order - position not found in broker account")
                self.remove_position_from_tracking(ticker)
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

        # Flag position as having a pending order and record timestamp
        self.tracked_positions[ticker]["has_pending_order"] = True
        self.tracked_positions[ticker]["last_order_time"] = datetime.now()
        self.logger.info(f"Marked {ticker} as having a pending order to prevent duplicates")

        return True

    def queue_order(self, ticker, quantity, transaction_type, reason, price=None):
        """Add a full order to the queue for execution (for backward compatibility)"""
        # Check if we should ignore this order
        if ticker not in self.tracked_positions:
            self.logger.warning(f"Ignoring order for {ticker} as it's not in tracked positions")
            return False
        
        # Pre-order validation for SELL orders
        if transaction_type == "SELL":
            if not self.verify_position_exists(ticker, None):
                self.logger.warning(f"{ticker}: Cannot queue SELL order - position not found in broker account")
                self.remove_position_from_tracking(ticker)
                return False
        
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

        # Add to queue for execution
        self.order_queue.put(order_info)
        order_type = "LIMIT" if price else "MARKET"
        price_info = f" at {price}" if price else ""
        self.logger.info(f"Queued FULL {transaction_type} {order_type} order for {ticker} (qty: {quantity}){price_info}: {reason}")

        # Flag position as having a pending order to prevent duplicate orders
        self.tracked_positions[ticker]["has_pending_order"] = True
        self.tracked_positions[ticker]["last_order_time"] = datetime.now()
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
                                    # Don't reset the pending order flag immediately - let it expire via timestamp check
                                    # This prevents rapid duplicate orders
                                    pass

                                    # Check if this was the last part of the position
                                    if remaining_qty <= 0:
                                        self.logger.info(f"All shares of {ticker} sold, removing from tracking")
                                        del self.tracked_positions[ticker]
                                        if ticker in self.current_prices:
                                            del self.current_prices[ticker]
                                        if ticker in self.position_high_prices:
                                            del self.position_high_prices[ticker]
                                        if ticker in self.atr_data:
                                            del self.atr_data[ticker]
                                        if ticker in self.sma20_hourly_data:
                                            del self.sma20_hourly_data[ticker]
                                        if ticker in self.peak_warning_issued:
                                            del self.peak_warning_issued[ticker]
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
                                    if ticker in self.position_high_prices:
                                        del self.position_high_prices[ticker]
                                    if ticker in self.atr_data:
                                        del self.atr_data[ticker]
                                    if ticker in self.sma20_hourly_data:
                                        del self.sma20_hourly_data[ticker]
                                    if ticker in self.peak_warning_issued:
                                        del self.peak_warning_issued[ticker]

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
                                    if ticker in self.current_prices:
                                        del self.current_prices[ticker]
                                    if ticker in self.position_high_prices:
                                        del self.position_high_prices[ticker]
                                    if ticker in self.atr_data:
                                        del self.atr_data[ticker]
                                    if ticker in self.sma20_hourly_data:
                                        del self.sma20_hourly_data[ticker]
                                    if ticker in self.peak_warning_issued:
                                        del self.peak_warning_issued[ticker]
                                elif is_partial and ticker in self.tracked_positions:
                                    self.tracked_positions[ticker]["has_pending_order"] = False

                                break  # No need to retry

                            # Handle insufficient stock errors
                            elif "insufficient stock" in error_str or "holding quantity: 0" in error_str:
                                self.logger.error(f"{ticker}: No holdings available. Removing from tracking.")
                                self.remove_position_from_tracking(ticker)
                                break  # No need to retry
                            
                            # Handle tick size errors
                            elif "tick size" in error_str:
                                # Extract tick size from error message if possible
                                import re
                                tick_match = re.search(r'tick size.*?(\d+\.?\d*)', error_str)
                                if tick_match:
                                    correct_tick_size = float(tick_match.group(1))
                                    self.logger.warning(f"Tick size error for {ticker}. Expected: {correct_tick_size}. Updating and retrying...")
                                    
                                    # Update our tick size cache
                                    self.tick_sizes[ticker] = correct_tick_size
                                    self.known_tick_sizes[ticker.upper()] = correct_tick_size
                                    
                                    # Recalculate price with correct tick size
                                    if price:
                                        price = self.round_to_tick_size(price, correct_tick_size)
                                        order_params["price"] = price
                                        self.logger.info(f"Adjusted price to {price} with tick size {correct_tick_size}")
                                    
                                    retry_count += 1
                                    if retry_count <= max_retries:
                                        time.sleep(1)
                                        continue
                                else:
                                    self.logger.error(f"Tick size error but couldn't extract correct value: {e}")
                                    break
                            
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
        
        # Initialize SMA20 hourly data
        self.logger.info("Initializing SMA20 hourly data for all positions...")
        self.last_sma20_check = 0  # Force immediate update
        self.update_sma20_hourly_data()
        
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
                
                # Update SMA20 hourly data periodically (every 30 minutes)
                # This is for display/monitoring only, not for exit decisions
                self.update_sma20_hourly_data()
                
                # SMA20 exit check at 2:30 PM is DISABLED
                # self.check_sma20_exit_at_230pm()
                
                # Sync positions with broker periodically (every 10 minutes)
                self.sync_positions_with_broker()

                # Print summary every 10 minutes
                if int(time.time()) % 600 == 0:  # Every 10 minutes
                    self.print_portfolio_summary()

                time.sleep(10)  # Check every 10 seconds
        except Exception as e:
            self.logger.error(f"Error in main monitoring loop: {e}")
            self.stop()
            return False
        
        return True
    
    def check_sma20_today_only(self, ticker) -> Optional[Dict]:
        """Check SMA20 violations using only today's data from 9:15 AM to 2:30 PM
        
        This is used for the 2:30 PM exit check only
        """
        try:
            token = self.get_instrument_token(ticker)
            if token is None:
                self.logger.error(f"Token not found for {ticker}. Cannot check SMA20 hourly violations.")
                return None

            # Get hourly data for today only
            ist = pytz.timezone('Asia/Kolkata')
            now = datetime.now(ist)
            
            # Set start time to 9:15 AM today
            start_date = now.replace(hour=9, minute=15, second=0, microsecond=0)
            # Set end time to 2:30 PM today
            end_date = now.replace(hour=14, minute=30, second=0, microsecond=0)

            # Get historical data for proper SMA20 calculation (need more history)
            history_start = start_date - timedelta(days=10)
            historical_hourly = self.kite.historical_data(token, history_start, end_date, "60minute")
            
            if len(historical_hourly) >= 20:
                df_full = pd.DataFrame(historical_hourly)
                df_full['SMA20'] = df_full['close'].rolling(window=20).mean()
                
                # Get today's data only (9:15 AM to 2:30 PM)
                df_full['date'] = pd.to_datetime(df_full['date'])
                today_mask = (df_full['date'].dt.date == now.date()) & \
                           (df_full['date'] >= start_date) & \
                           (df_full['date'] <= end_date)
                today_data = df_full[today_mask].copy()
                
                if len(today_data) > 0:
                    # Count violations for today only
                    violations = 0
                    hours_above = 0
                    total_hours = 0
                    
                    for idx, row in today_data.iterrows():
                        if pd.notna(row['SMA20']):
                            total_hours += 1
                            if row['close'] < row['SMA20']:
                                violations += 1
                            else:
                                hours_above += 1
                    
                    # Calculate ratio
                    sma20_above_ratio = hours_above / total_hours if total_hours > 0 else 0
                    
                    result = {
                        'sma20_violations': violations,
                        'hours_monitored': total_hours,
                        'hours_above_sma20': hours_above,
                        'sma20_above_ratio': sma20_above_ratio,
                        'latest_close': today_data['close'].iloc[-1] if len(today_data) > 0 else None,
                        'latest_sma20': today_data['SMA20'].iloc[-1] if len(today_data) > 0 and pd.notna(today_data['SMA20'].iloc[-1]) else None
                    }
                    
                    self.logger.info(f"{ticker} SMA20 Check at 2:30 PM (Today only): "
                                   f"Violations={violations}/{total_hours}, "
                                   f"Above Ratio={sma20_above_ratio:.1%}")
                    
                    return result
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking SMA20 today only for {ticker}: {e}")
            return None

    def check_sma20_exit_at_230pm(self):
        """Check SMA20 exit conditions at 2:30 PM IST using today's data only"""
        try:
            ist = pytz.timezone('Asia/Kolkata')
            now = datetime.now(ist)
            
            # Check if it's 2:30 PM (with 1 minute tolerance)
            if now.hour == 14 and 29 <= now.minute <= 31:
                # Check if we've already done the 2:30 PM check today
                check_key = now.strftime("%Y-%m-%d")
                if hasattr(self, 'sma20_230pm_check_done') and self.sma20_230pm_check_done.get(check_key, False):
                    return
                
                self.logger.info("=== Performing 2:30 PM SMA20 Exit Check ===")
                
                # Mark that we've done today's check
                if not hasattr(self, 'sma20_230pm_check_done'):
                    self.sma20_230pm_check_done = {}
                self.sma20_230pm_check_done[check_key] = True
                
                positions_to_exit = []
                
                # Check each tracked position
                for ticker in list(self.tracked_positions.keys()):
                    try:
                        # Skip if position already has a pending order
                        if ticker in self.pending_orders:
                            continue
                        
                        # Get today's SMA20 data
                        sma20_result = self.check_sma20_today_only(ticker)
                        if not sma20_result:
                            continue
                        
                        violations = sma20_result.get('sma20_violations', 0)
                        sma20_ratio = sma20_result.get('sma20_above_ratio', 1.0)
                        
                        # Check exit conditions
                        exit_reason = None
                        
                        # Rule 1: Exit if hourly_close_below_SMA20 >= 2 times
                        if violations >= 2:
                            exit_reason = f"SMA20 hourly violations: {violations} (>= 2 threshold)"
                            self.logger.info(f"2:30 PM SMA20 VIOLATION EXIT - {ticker}: {violations} hourly closes below SMA20 today")
                        
                        # Rule 2: Exit if (hours_above_SMA20 / total_hours) < 80%
                        elif sma20_ratio < 0.8:
                            exit_reason = f"SMA20 above ratio: {sma20_ratio:.1%} (< 80% threshold)"
                            self.logger.info(f"2:30 PM SMA20 RATIO EXIT - {ticker}: Only {sma20_ratio:.1%} of hours above SMA20 today")
                        
                        if exit_reason:
                            position_data = self.tracked_positions.get(ticker, {})
                            quantity = position_data.get("quantity", 0)
                            positions_to_exit.append((ticker, quantity, exit_reason))
                    
                    except Exception as e:
                        self.logger.error(f"Error checking SMA20 for {ticker} at 2:30 PM: {e}")
                
                # Queue all exit orders
                for ticker, quantity, reason in positions_to_exit:
                    self.queue_order(ticker, quantity, "SELL", f"2:30 PM {reason}", None)
                
                if positions_to_exit:
                    self.logger.info(f"Queued {len(positions_to_exit)} positions for exit based on 2:30 PM SMA20 check")
                else:
                    self.logger.info("No positions qualified for SMA20 exit at 2:30 PM")
                
        except Exception as e:
            self.logger.error(f"Error in 2:30 PM SMA20 exit check: {e}")

    def check_gap_breaches(self):
        """Check if any positions gapped through their stop losses on restart"""
        try:
            self.logger.info("\n" + "="*60)
            self.logger.info("Checking for gap breaches through stop losses...")
            
            gap_breaches = []
            
            for ticker, position in self.tracked_positions.items():
                if ticker not in self.atr_data:
                    continue
                    
                stop_loss = self.atr_data[ticker].get('stop_loss', 0)
                if stop_loss <= 0:
                    continue
                
                # Get current price
                try:
                    ltp_data = self.kite.ltp(f"{position['exchange']}:{ticker}")
                    current_price = ltp_data[f"{position['exchange']}:{ticker}"]["last_price"]
                    
                    # Check if current price is below stop loss
                    if current_price < stop_loss:
                        gap_percent = ((stop_loss - current_price) / stop_loss) * 100
                        gap_breaches.append({
                            'ticker': ticker,
                            'stop_loss': stop_loss,
                            'current_price': current_price,
                            'gap_percent': gap_percent,
                            'quantity': position['quantity']
                        })
                        
                        self.logger.critical(f"🚨 {ticker}: GAPPED THROUGH STOP LOSS! "
                                           f"Stop: ₹{stop_loss:.2f}, Current: ₹{current_price:.2f}, "
                                           f"Gap: {gap_percent:.2f}%")
                        
                        # Queue immediate exit order
                        self.queue_order(
                            ticker,
                            position['quantity'],
                            "SELL",
                            f"GAP_BREACH: Price gapped {gap_percent:.1f}% below stop loss",
                            current_price * 0.995  # Slightly below current price for market-like execution
                        )
                
                except Exception as e:
                    self.logger.error(f"Error checking gap breach for {ticker}: {e}")
            
            if gap_breaches:
                self.logger.critical(f"\n⚠️  FOUND {len(gap_breaches)} POSITIONS THAT GAPPED THROUGH STOP LOSSES!")
                for breach in gap_breaches:
                    self.logger.critical(f"   - {breach['ticker']}: {breach['quantity']} shares, "
                                       f"Gap: {breach['gap_percent']:.2f}% below stop")
            else:
                self.logger.info("✅ No gap breaches detected. All positions within stop loss levels.")
            
            self.logger.info("="*60 + "\n")
            
        except Exception as e:
            self.logger.error(f"Error in gap breach check: {e}")
    
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

                # Get position high info for trailing information
                position_high = self.position_high_prices.get(ticker, 0)
                if position_high > 0 and position_high > current_price:
                    trail_info = f", Trail: {((position_high - current_price) / position_high * 100):.1f}% from position high ₹{position_high:.2f}"
                else:
                    trail_info = ""

                atr_display = f"₹{stop_loss:.2f} ({volatility} {multiplier}x, ATR: {atr_pct:.1f}%{trail_info})"
            else:
                atr_display = "Calculating..."
                current_price = self.current_prices.get(ticker, entry_price)
            
            # Get SMA20 hourly data for this ticker
            sma20_info = self.sma20_hourly_data.get(ticker, {})
            if sma20_info:
                violations = sma20_info.get('sma20_violations', 0)
                sma20_ratio = sma20_info.get('sma20_above_ratio', 0)
                sma20_display = f" | SMA20: {violations} viol, {sma20_ratio:.0%} above"
                
                # Add warning indicators
                if violations >= 1 or sma20_ratio < 0.9:
                    sma20_display += " ⚠️"
            else:
                sma20_display = ""

            current_value = current_price * qty
            profit_loss = current_value - investment
            profit_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

            total_investment += investment
            total_current_value += current_value

            self.logger.info(f"{ticker}: {qty} shares @ ₹{entry_price:.2f} | Current: ₹{current_price:.2f} | "
                           f"P/L: ₹{profit_loss:.2f} ({profit_pct:.2f}%) | ATR Stop: {atr_display}{sma20_display}")

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
        
        # Check for gaps through stop losses after restart
        watchdog.check_gap_breaches()
        
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