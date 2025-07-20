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
import numpy as np

# Add parent directory to path so we can import modules
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import trading system modules
from kiteconnect import KiteConnect
from ..user_context_manager import (
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
    parser = argparse.ArgumentParser(description="ATR-based stop loss watchdog for CNC positions with VSR monitoring")
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
    ATR-based trailing stop loss position monitoring system with VSR monitoring.

    ATR-Based Logic: Uses 20-day ATR on daily timeframe to set trailing stop losses:
    - Low Volatility (ATR <2%): Stop = 1.0x ATR
    - Medium Volatility (ATR 2-4%): Stop = 1.5x ATR
    - High Volatility (ATR >4%): Stop = 2.0x ATR

    VSR-Based Exit Rules (Hourly):
    - Exit if hourly VSR drops below 50% of entry VSR
    - Exit if position shows -2% loss

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
        
        # Profit target exits configuration
        profit_target_str = config.get('DEFAULT', 'profit_target_exits', fallback='no').lower()
        self.profit_target_exits_enabled = profit_target_str in ['yes', 'true', '1', 'on']

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
        self.logger.info("ATR-BASED TRAILING STOP LOSS WITH VSR MONITORING ENABLED")
        self.logger.info("Stop loss calculation based on 20-day ATR:")
        self.logger.info("- Low Volatility (ATR <2%): Stop = 1.0x ATR")
        self.logger.info("- Medium Volatility (ATR 2-4%): Stop = 1.5x ATR")
        self.logger.info("- High Volatility (ATR >4%): Stop = 2.0x ATR")
        self.logger.info("")
        self.logger.info("VSR-BASED EXIT RULES (Hourly):")
        self.logger.info("- Exit if hourly VSR drops < 50% of entry VSR")
        self.logger.info("- Exit if position shows -2% loss")
        self.logger.info("")
        self.logger.info("TRUE TRAILING STOP FEATURE: Stop losses automatically rise as prices reach new highs")
        self.logger.info("- Trailing stops only move upward, never downward")
        self.logger.info("- Stop losses recalculated based on highest price reached since position entry")
        self.logger.info("- Profits are protected while still allowing for volatility")
        self.logger.info("")
        if self.profit_target_exits_enabled:
            self.logger.info("PROFIT TARGET EXITS ENABLED")
            self.logger.info("- Partial exits at predefined ATR multiples based on volatility")
            self.logger.info("- Low Vol: 50% at SL, 30% at 2x ATR, 20% at 3x ATR")
            self.logger.info("- Med Vol: 40% at SL, 30% at 2.5x ATR, 30% at 4x ATR")
            self.logger.info("- High Vol: 30% at SL, 30% at 3x ATR, 40% at 5x ATR")
        else:
            self.logger.info("PROFIT TARGET EXITS DISABLED - Only stop losses will trigger exits")
        self.logger.info("=" * 60)

    def calculate_vsr(self, high, low, volume):
        """Calculate Volume Spread Ratio"""
        spread = high - low
        if spread > 0:
            return volume / spread
        return 0

    def fetch_hourly_data(self, ticker):
        """Fetch hourly candle data for VSR calculation"""
        try:
            instrument_token = self.get_instrument_token(ticker)
            if not instrument_token:
                return None
            
            # Get last 24 hours of hourly data
            to_date = datetime.now()
            from_date = to_date - timedelta(days=1)
            
            historical_data = self.kite.historical_data(
                instrument_token,
                from_date,
                to_date,
                '60minute'
            )
            
            if historical_data:
                # Store in hourly candles cache
                self.hourly_candles[ticker] = historical_data
                return historical_data
            
        except Exception as e:
            self.logger.error(f"Error fetching hourly data for {ticker}: {e}")
        
        return None

    def check_vsr_conditions(self, ticker):
        """Check VSR-based exit conditions on hourly timeframe"""
        try:
            # Only check once per hour
            current_time = datetime.now()
            if ticker in self.vsr_data:
                last_check = self.vsr_data[ticker].get('last_hourly_check')
                if last_check and (current_time - last_check).total_seconds() < 3600:
                    return None
            
            # Fetch latest hourly data
            hourly_data = self.fetch_hourly_data(ticker)
            if not hourly_data or len(hourly_data) < 2:
                return None
            
            # Get the latest complete hourly candle
            latest_candle = hourly_data[-1]
            current_vsr = self.calculate_vsr(
                latest_candle['high'],
                latest_candle['low'],
                latest_candle['volume']
            )
            
            # Initialize VSR data if not exists
            if ticker not in self.vsr_data:
                # Use first candle as entry VSR (or calculate average of recent candles)
                entry_vsr = current_vsr
                if len(hourly_data) >= 20:
                    # Calculate 20-period average VSR
                    vsr_values = [self.calculate_vsr(c['high'], c['low'], c['volume']) for c in hourly_data[-20:]]
                    entry_vsr = np.mean([v for v in vsr_values if v > 0])
                
                self.vsr_data[ticker] = {
                    'entry_vsr': entry_vsr,
                    'current_vsr': current_vsr,
                    'vsr_history': [current_vsr],
                    'last_hourly_check': current_time,
                    'avg_vsr': entry_vsr
                }
                
                self.logger.info(f"{ticker}: VSR monitoring initialized - Entry VSR: {entry_vsr:.0f}, Current VSR: {current_vsr:.0f}")
                return None
            
            # Update VSR data
            vsr_info = self.vsr_data[ticker]
            vsr_info['current_vsr'] = current_vsr
            vsr_info['vsr_history'].append(current_vsr)
            vsr_info['last_hourly_check'] = current_time
            
            # Keep only last 24 hours of history
            if len(vsr_info['vsr_history']) > 24:
                vsr_info['vsr_history'] = vsr_info['vsr_history'][-24:]
            
            # Check VSR deterioration
            avg_vsr = vsr_info['avg_vsr']
            vsr_ratio = current_vsr / avg_vsr if avg_vsr > 0 else 1
            
            if vsr_ratio < 0.5:
                self.logger.warning(f"{ticker}: VSR DETERIORATION DETECTED - Current VSR: {current_vsr:.0f} "
                                  f"({vsr_ratio*100:.0f}% of average {avg_vsr:.0f})")
                return {
                    'exit_signal': 'VSR_DETERIORATION',
                    'current_vsr': current_vsr,
                    'avg_vsr': avg_vsr,
                    'vsr_ratio': vsr_ratio,
                    'reason': f"VSR dropped to {vsr_ratio*100:.0f}% of average"
                }
            
            self.logger.debug(f"{ticker}: VSR Check - Current: {current_vsr:.0f}, Avg: {avg_vsr:.0f}, Ratio: {vsr_ratio*100:.0f}%")
            
        except Exception as e:
            self.logger.error(f"Error checking VSR conditions for {ticker}: {e}")
        
        return None

    def check_loss_threshold(self, ticker, current_price):
        """Check if position has -2% loss"""
        if ticker not in self.tracked_positions:
            return None
        
        position_data = self.tracked_positions[ticker]
        entry_price = position_data.get("entry_price", 0)
        
        if entry_price <= 0:
            return None
        
        loss_pct = ((current_price - entry_price) / entry_price) * 100
        
        if loss_pct <= -2.0:
            self.logger.warning(f"{ticker}: LOSS THRESHOLD BREACHED - Current loss: {loss_pct:.2f}%")
            return {
                'exit_signal': 'LOSS_THRESHOLD',
                'loss_pct': loss_pct,
                'entry_price': entry_price,
                'current_price': current_price,
                'reason': f"Position loss exceeded -2% (current: {loss_pct:.2f}%)"
            }
        
        return None

    def check_atr_stop_loss(self, ticker, current_price):
        """Check if current price is below ATR-based trailing stop loss with VSR checks"""
        if ticker not in self.atr_data:
            return

        # Check if this position already has a pending order
        if self.tracked_positions[ticker].get("has_pending_order", False):
            self.logger.debug(f"Skipping stop loss check for {ticker} as it already has a pending order")
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
        
        # Continue with existing ATR stop loss logic...
        # [Rest of the existing check_atr_stop_loss method remains the same]
        
    # Include all other existing methods from the original file
    # For brevity, I'm showing only the modified parts
    
# Copy all remaining methods from the original SL_watchdog.py file
# This includes: handle_shutdown, is_market_closed, get_tick_size, round_to_tick_size,
# verify_position_exists, get_instruments_data, get_instrument_token, 
# remove_position_from_tracking, load_cnc_positions_from_zerodha, 
# load_positions_from_orders_file, fetch_daily_high, calculate_atr_and_stop_loss,
# update_atr_stop_losses, check_sma20_hourly_violations, update_sma20_hourly_data,
# sync_positions_with_broker, poll_prices, queue_partial_order, queue_order,
# process_order_queue, start, check_sma20_today_only, check_sma20_exit_at_230pm,
# stop, print_portfolio_summary

# Also copy the standalone functions: find_orders_file, extract_user_from_orders_file,
# get_default_user, main

if __name__ == "__main__":
    main()