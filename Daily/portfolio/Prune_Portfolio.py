#!/usr/bin/env python3
"""
Portfolio Pruning Script

This script prunes positions based on:
1. Day 1 Return analysis (original method)
2. 20 SMA in hourly timeframe (new method)
3. Age-based pruning: Positions >3 days old with <2% growth

Exit Rules:
- Method 1: If end_of_day_1_return < 1.0%, exit position
- Method 2: If current price < 20 SMA (hourly), exit position
- Method 3: If position is >3 days old AND growth <2%, exit position

This script can be run at any time during market hours to check and prune positions.
"""

import os
import sys
import json
import logging
import argparse
import configparser
from datetime import datetime, timedelta, time
import pytz
from typing import Dict, List, Optional, Tuple
import glob

# Add parent directory to path so we can import modules
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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
    """Set up logging with user-specific log files"""
    # Create user-specific log directory
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', user_name)
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'prune_portfolio_{user_name}.log')
    
    # Configure logging
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ],
        force=True
    )
    
    logger = logging.getLogger()
    logger.info(f"Logging initialized for user {user_name}")
    
    return logger

def is_market_hours():
    """Check if current time is during market hours (9:15 AM - 3:30 PM IST)"""
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist)
    
    # Check if it's a weekday
    if current_time.weekday() >= 5:  # Saturday or Sunday
        return False
    
    # Market hours
    market_open = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = current_time.replace(hour=15, minute=30, second=0, microsecond=0)
    
    return market_open <= current_time <= market_close

# Removed get_execution_time() function - no longer needed

class PortfolioPruner:
    """
    Portfolio pruning system based on Day 1 Return analysis.
    
    Exit Rule: If end_of_day_1_return < 1.0%, exit position.
    Based on statistical analysis showing 311.5% performance difference between winners and losers.
    """
    
    def __init__(self, user_credentials: UserCredentials, config):
        self.logger = logging.getLogger()
        self.user_name = user_credentials.name
        self.config = config
        
        # Set up user context
        context_manager = get_context_manager()
        context_manager.set_current_user(user_credentials.name, user_credentials)
        
        # API configuration
        self.api_key = user_credentials.api_key
        self.api_secret = user_credentials.api_secret
        self.access_token = user_credentials.access_token
        self.exchange = config.get('DEFAULT', 'exchange', fallback='NSE')
        self.product_type = config.get('DEFAULT', 'product_type', fallback='CNC')
        
        # Day 1 return threshold (from statistical analysis)
        self.day1_return_threshold = 1.0  # 1.0% threshold
        
        # Initialize KiteConnect client
        try:
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(self.access_token)
            self.logger.info("KiteConnect client initialized successfully")
            
            # Test the connection
            profile = self.kite.profile()
            self.logger.info(f"Connected as {profile['user_name']} ({profile['user_id']})")
        except Exception as e:
            self.logger.error(f"Failed to initialize KiteConnect: {e}")
            raise
        
        # Initialize user-specific data handler
        self.data_handler = get_user_data_handler()
        
        # Initialize instruments data
        try:
            self.logger.info("Initializing instruments data")
            self.data_handler.initialize_instruments()
            self.logger.info(f"Initialized {len(self.data_handler.get_all_instruments())} instruments")
        except Exception as e:
            self.logger.warning(f"Could not initialize instruments: {e}")
        
        # Log the pruning rules
        self.logger.info("=" * 60)
        self.logger.info("PORTFOLIO PRUNING RULES")
        self.logger.info("=" * 60)
        self.logger.info("1. DAY 1 RETURN ANALYSIS")
        self.logger.info("   Exit Rule: If Day 1 return < 1.0%, exit position")
        self.logger.info("   Statistical Evidence:")
        self.logger.info("   - Winners average: ~2.5% on Day 1")
        self.logger.info("   - Losers average: ~0.6% on Day 1")
        self.logger.info("   - Performance difference: 311.5%")
        self.logger.info("   - Early momentum is crucial for success")
        self.logger.info("")
        self.logger.info("2. AGE-BASED ANALYSIS")
        self.logger.info("   Exit Rule: If position > 3 days old AND growth < 2%, exit position")
        self.logger.info("   Rationale: Positions that haven't grown 2% after 3 days are underperforming")
        self.logger.info("=" * 60)
    
    def get_todays_orders(self) -> Dict[str, Dict]:
        """Get today's orders from the orders JSON files"""
        today_orders = {}
        
        try:
            # Find today's orders file
            script_dir = os.path.dirname(os.path.abspath(__file__))
            daily_dir = os.path.dirname(script_dir)
            orders_dir = os.path.join(daily_dir, "Current_Orders", self.user_name)
            
            if not os.path.exists(orders_dir):
                self.logger.warning(f"Orders directory not found: {orders_dir}")
                return today_orders
            
            # Look for today's orders file
            today = datetime.now().strftime('%Y%m%d')
            pattern = os.path.join(orders_dir, f"orders_{self.user_name}_{today}_*.json")
            order_files = glob.glob(pattern)
            
            if not order_files:
                self.logger.info(f"No orders file found for today ({today})")
                return today_orders
            
            # Use the most recent file if multiple exist
            latest_file = max(order_files, key=os.path.getmtime)
            
            with open(latest_file, 'r') as f:
                orders_data = json.load(f)
            
            # Extract orders placed today
            for order in orders_data.get('orders', []):
                if order.get('order_success', False):
                    ticker = order.get('ticker')
                    if ticker:
                        # Store order info with entry price and timestamp
                        today_orders[ticker] = {
                            'entry_price': order.get('current_price', 0),
                            'quantity': order.get('position_size', 0),
                            'order_timestamp': order.get('order_timestamp', ''),
                            'investment_amount': order.get('investment_amount', 0)
                        }
            
            self.logger.info(f"Loaded {len(today_orders)} orders from today's file: {latest_file}")
            
        except Exception as e:
            self.logger.error(f"Error loading today's orders: {e}")
        
        return today_orders
    
    def get_all_orders(self) -> Dict[str, Dict]:
        """Get all orders from the orders JSON files (for age-based analysis)"""
        all_orders = {}
        
        try:
            # Find all orders files
            script_dir = os.path.dirname(os.path.abspath(__file__))
            daily_dir = os.path.dirname(script_dir)
            orders_dir = os.path.join(daily_dir, "Current_Orders", self.user_name)
            
            if not os.path.exists(orders_dir):
                self.logger.warning(f"Orders directory not found: {orders_dir}")
                return all_orders
            
            # Look for all orders files
            pattern = os.path.join(orders_dir, f"orders_{self.user_name}_*.json")
            order_files = glob.glob(pattern)
            
            if not order_files:
                self.logger.info(f"No orders files found")
                return all_orders
            
            self.logger.info(f"Found {len(order_files)} order files to process")
            
            # Process all order files
            for order_file in order_files:
                try:
                    with open(order_file, 'r') as f:
                        orders_data = json.load(f)
                    
                    # Extract orders
                    for order in orders_data.get('orders', []):
                        if order.get('order_success', False):
                            ticker = order.get('ticker')
                            if ticker and ticker not in all_orders:  # Take the first occurrence (oldest)
                                # Store order info with entry price and timestamp
                                timestamp = order.get('order_timestamp', '')
                                self.logger.debug(f"Processing {ticker} with timestamp: {timestamp}")
                                
                                all_orders[ticker] = {
                                    'entry_price': order.get('current_price', 0),
                                    'quantity': order.get('position_size', 0),
                                    'order_timestamp': timestamp,
                                    'investment_amount': order.get('investment_amount', 0),
                                    'order_file': os.path.basename(order_file)
                                }
                except Exception as e:
                    self.logger.warning(f"Error loading order file {order_file}: {e}")
            
            self.logger.info(f"Loaded {len(all_orders)} total unique orders from all files")
            
            # Log sample timestamps for debugging
            if all_orders:
                sample_ticker = list(all_orders.keys())[0]
                sample_timestamp = all_orders[sample_ticker].get('order_timestamp', '')
                self.logger.info(f"Sample timestamp format - {sample_ticker}: '{sample_timestamp}'")
            
        except Exception as e:
            self.logger.error(f"Error loading all orders: {e}")
        
        return all_orders
    
    def calculate_day1_returns(self, positions: List[Dict], today_orders: Dict[str, Dict]) -> List[Tuple[str, float, Dict]]:
        """Calculate Day 1 returns for positions and identify underperformers"""
        underperformers = []
        
        for position in positions:
            ticker = position.get('tradingsymbol', '')
            quantity = int(position.get('quantity', 0))
            
            # Skip if no position or not in today's orders
            if quantity <= 0 or ticker not in today_orders:
                continue
            
            # Get entry price from today's orders
            order_info = today_orders[ticker]
            entry_price = float(order_info.get('entry_price', 0))
            
            if entry_price <= 0:
                self.logger.warning(f"Invalid entry price for {ticker}, skipping")
                continue
            
            # Get current price
            try:
                ltp_data = self.kite.ltp(f"{self.exchange}:{ticker}")
                current_price = ltp_data[f"{self.exchange}:{ticker}"]["last_price"]
            except Exception as e:
                self.logger.error(f"Error fetching price for {ticker}: {e}")
                continue
            
            # Calculate Day 1 return
            day1_return = ((current_price - entry_price) / entry_price) * 100
            
            # Log the analysis
            self.logger.info(f"{ticker}: Entry: ₹{entry_price:.2f}, Current: ₹{current_price:.2f}, "
                           f"Day 1 Return: {day1_return:.2f}%")
            
            # Check if underperforming
            if day1_return < self.day1_return_threshold:
                underperformers.append((ticker, day1_return, {
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'investment': order_info.get('investment_amount', entry_price * quantity)
                }))
                self.logger.warning(f"{ticker} UNDERPERFORMING: {day1_return:.2f}% < {self.day1_return_threshold}% threshold")
            else:
                self.logger.info(f"{ticker} performing well: {day1_return:.2f}% >= {self.day1_return_threshold}% threshold")
        
        return underperformers
    
    def calculate_age_based_returns(self, positions: List[Dict], all_orders: Dict[str, Dict], exclusions: List[str] = None) -> List[Tuple[str, float, int, Dict]]:
        """Calculate returns for positions older than 3 days and identify underperformers (<2% growth)"""
        age_based_underperformers = []
        exclusions = exclusions or []
        
        for position in positions:
            ticker = position.get('tradingsymbol', '')
            quantity = int(position.get('quantity', 0))
            
            # Skip if no position, not in order history, or in exclusions
            if quantity <= 0 or ticker not in all_orders or ticker in exclusions:
                continue
            
            # Get entry info from order history
            order_info = all_orders[ticker]
            entry_price = float(order_info.get('entry_price', 0))
            order_timestamp = order_info.get('order_timestamp', '')
            
            if entry_price <= 0:
                self.logger.warning(f"Invalid entry price for {ticker}, skipping")
                continue
            
            # Calculate age in days
            try:
                # Parse the timestamp - it's in format '2025-06-06T12:20:47.792315' without timezone
                if 'T' in order_timestamp:
                    # Remove microseconds if present for easier parsing
                    if '.' in order_timestamp:
                        timestamp_base = order_timestamp.split('.')[0]
                    else:
                        timestamp_base = order_timestamp.split('+')[0].split('Z')[0]
                    
                    # Parse the datetime
                    order_date = datetime.strptime(timestamp_base, '%Y-%m-%dT%H:%M:%S')
                    # Assume it's in IST (since this is for Indian markets)
                    order_date = pytz.timezone('Asia/Kolkata').localize(order_date)
                else:
                    # Simple datetime string
                    order_date = datetime.strptime(order_timestamp, '%Y-%m-%d %H:%M:%S')
                    order_date = pytz.timezone('Asia/Kolkata').localize(order_date)
                
                # Get current time in IST
                current_time = datetime.now(pytz.timezone('Asia/Kolkata'))
                age_days = (current_time - order_date).days
            except Exception as e:
                self.logger.warning(f"Error parsing order date for {ticker}: {e}, timestamp: '{order_timestamp}'")
                continue
            
            # Skip if position is 3 days or younger
            if age_days <= 3:
                self.logger.info(f"{ticker}: Position is only {age_days} days old, skipping age-based check")
                continue
            
            # Get current price
            try:
                ltp_data = self.kite.ltp(f"{self.exchange}:{ticker}")
                current_price = ltp_data[f"{self.exchange}:{ticker}"]["last_price"]
            except Exception as e:
                self.logger.error(f"Error fetching price for {ticker}: {e}")
                continue
            
            # Calculate return percentage
            return_pct = ((current_price - entry_price) / entry_price) * 100
            
            # Log the analysis
            self.logger.info(f"{ticker}: Age: {age_days} days, Entry: ₹{entry_price:.2f}, Current: ₹{current_price:.2f}, "
                           f"Return: {return_pct:.2f}%")
            
            # Check if underperforming (less than 2% growth)
            if return_pct < 2.0:
                age_based_underperformers.append((ticker, return_pct, age_days, {
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'investment': order_info.get('investment_amount', entry_price * quantity)
                }))
                self.logger.warning(f"{ticker} UNDERPERFORMING (AGE-BASED): {return_pct:.2f}% < 2.0% after {age_days} days")
            else:
                self.logger.info(f"{ticker} performing adequately: {return_pct:.2f}% >= 2.0% after {age_days} days")
        
        return age_based_underperformers
    
    def place_exit_orders(self, underperformers: List[Tuple], skip_confirmation: bool = False, is_age_based: bool = False):
        """Place exit orders for underperforming positions"""
        if not underperformers:
            self.logger.info("No underperforming positions to exit")
            return
        
        # Show summary and ask for confirmation
        if not skip_confirmation:
            print("\n" + "=" * 60)
            if is_age_based:
                print("AGE-BASED POSITIONS TO BE EXITED (>3 days old with <2% growth):")
            else:
                print("DAY 1 UNDERPERFORMING POSITIONS TO BE EXITED:")
            print("=" * 60)
            total_value = 0
            
            for item in underperformers:
                if is_age_based:
                    ticker, return_pct, age_days, position_info = item
                    qty = position_info['quantity']
                    current_price = position_info['current_price']
                    value = qty * current_price
                    total_value += value
                    print(f"{ticker}: {qty} shares @ ₹{current_price:.2f} = ₹{value:,.2f} (Return: {return_pct:.2f}%, Age: {age_days} days)")
                else:
                    ticker, day1_return, position_info = item
                    qty = position_info['quantity']
                    current_price = position_info['current_price']
                    value = qty * current_price
                    total_value += value
                    print(f"{ticker}: {qty} shares @ ₹{current_price:.2f} = ₹{value:,.2f} (Day 1 Return: {day1_return:.2f}%)")
            
            print(f"\nTotal value to be sold: ₹{total_value:,.2f}")
            print("=" * 60)
            
            # Ask for confirmation
            while True:
                confirm = input("\nProceed with exit orders? (yes/no): ").strip().lower()
                if confirm in ['yes', 'y']:
                    break
                elif confirm in ['no', 'n']:
                    self.logger.info("User cancelled exit orders")
                    print("Exit orders cancelled.")
                    return
                else:
                    print("Please enter 'yes' or 'no'")
        
        self.logger.info(f"Placing exit orders for {len(underperformers)} underperforming positions")
        
        for item in underperformers:
            try:
                if is_age_based:
                    ticker, return_pct, age_days, position_info = item
                    reason = f"Age: {age_days} days, Return: {return_pct:.2f}%"
                else:
                    ticker, day1_return, position_info = item
                    reason = f"Day 1 Return: {day1_return:.2f}%"
                
                quantity = position_info['quantity']
                current_price = position_info['current_price']
                
                # Place SELL order at market price
                order_params = {
                    "variety": "regular",
                    "exchange": self.exchange,
                    "tradingsymbol": ticker,
                    "transaction_type": "SELL",
                    "quantity": quantity,
                    "product": self.product_type,
                    "order_type": "MARKET",
                    "validity": "DAY"
                }
                
                order_id = self.kite.place_order(**order_params)
                
                self.logger.info(f"EXIT ORDER PLACED - {ticker}: Sold {quantity} shares at market "
                               f"({reason}). Order ID: {order_id}")
                
                # Calculate expected P&L
                entry_price = position_info['entry_price']
                investment = position_info['investment']
                expected_sale_value = quantity * current_price
                expected_pnl = expected_sale_value - investment
                expected_pnl_pct = (expected_pnl / investment) * 100
                
                self.logger.info(f"  Expected P&L for {ticker}: ₹{expected_pnl:.2f} ({expected_pnl_pct:.2f}%)")
                
            except Exception as e:
                self.logger.error(f"Error placing exit order for {ticker}: {e}")
    
    def get_cnc_positions(self) -> List[Dict]:
        """Get all CNC positions from Zerodha"""
        cnc_positions = []
        
        try:
            # Get positions
            positions = self.kite.positions()
            
            for position in positions['net']:
                if position.get('product') == 'CNC' and int(position.get('quantity', 0)) > 0:
                    cnc_positions.append(position)
            
            # Also check holdings
            try:
                holdings = self.kite.holdings()
                for holding in holdings:
                    if int(holding.get('quantity', 0)) > 0:
                        # Convert to position format
                        cnc_positions.append({
                            'tradingsymbol': holding.get('tradingsymbol'),
                            'quantity': holding.get('quantity'),
                            'product': 'CNC',
                            'average_price': holding.get('average_price'),
                            'last_price': holding.get('last_price')
                        })
            except Exception as e:
                self.logger.warning(f"Could not fetch holdings: {e}")
            
            self.logger.info(f"Found {len(cnc_positions)} CNC positions")
            
        except Exception as e:
            self.logger.error(f"Error fetching positions: {e}")
        
        return cnc_positions
    
    def run_pruning(self, dry_run: bool = False, skip_confirmation: bool = False, include_age_based: bool = True):
        """Main pruning logic"""
        self.logger.info("=" * 60)
        self.logger.info(f"Starting Portfolio Pruning at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if dry_run:
            self.logger.info("DRY RUN MODE - No orders will be placed")
        self.logger.info("=" * 60)
        
        # Check if market hours
        if not is_market_hours():
            self.logger.warning("Market is closed. Pruning can only run during market hours.")
            return False
        
        # Get current CNC positions
        cnc_positions = self.get_cnc_positions()
        if not cnc_positions:
            self.logger.info("No CNC positions found.")
            return True
        
        # Method 1: Day 1 returns analysis
        today_orders = self.get_todays_orders()
        underperformers = []
        if today_orders:
            self.logger.info(f"Found {len(today_orders)} orders placed today: {', '.join(today_orders.keys())}")
            underperformers = self.calculate_day1_returns(cnc_positions, today_orders)
        else:
            self.logger.info("No orders placed today. Skipping Day 1 return analysis.")
        
        # Method 2: Age-based analysis (if enabled)
        age_based_underperformers = []
        exclusions = []
        
        if include_age_based:
            self.logger.info("\n" + "=" * 60)
            self.logger.info("AGE-BASED ANALYSIS (>3 days old with <2% growth)")
            self.logger.info("=" * 60)
            
            # Get all orders for age analysis
            all_orders = self.get_all_orders()
            
            if all_orders:
                # First, show positions that qualify for age-based analysis
                eligible_positions = []
                print("\n" + "=" * 60)
                print("POSITIONS ELIGIBLE FOR AGE-BASED ANALYSIS")
                print("=" * 60)
                
                for position in cnc_positions:
                    ticker = position.get('tradingsymbol', '')
                    quantity = int(position.get('quantity', 0))
                    
                    if quantity <= 0 or ticker not in all_orders:
                        continue
                    
                    order_info = all_orders[ticker]
                    entry_price = float(order_info.get('entry_price', 0))
                    order_timestamp = order_info.get('order_timestamp', '')
                    
                    if entry_price <= 0:
                        continue
                    
                    try:
                        # Parse the timestamp - it's in format '2025-06-06T12:20:47.792315' without timezone
                        if 'T' in order_timestamp:
                            # Remove microseconds if present for easier parsing
                            if '.' in order_timestamp:
                                timestamp_base = order_timestamp.split('.')[0]
                            else:
                                timestamp_base = order_timestamp.split('+')[0].split('Z')[0]
                            
                            # Parse the datetime
                            order_date = datetime.strptime(timestamp_base, '%Y-%m-%dT%H:%M:%S')
                            # Assume it's in IST (since this is for Indian markets)
                            order_date = pytz.timezone('Asia/Kolkata').localize(order_date)
                        else:
                            # Simple datetime string
                            order_date = datetime.strptime(order_timestamp, '%Y-%m-%d %H:%M:%S')
                            order_date = pytz.timezone('Asia/Kolkata').localize(order_date)
                        
                        # Get current time in IST
                        current_time = datetime.now(pytz.timezone('Asia/Kolkata'))
                        age_days = (current_time - order_date).days
                    except:
                        continue
                    
                    if age_days > 3:
                        try:
                            ltp_data = self.kite.ltp(f"{self.exchange}:{ticker}")
                            current_price = ltp_data[f"{self.exchange}:{ticker}"]["last_price"]
                            return_pct = ((current_price - entry_price) / entry_price) * 100
                            
                            eligible_positions.append({
                                'ticker': ticker,
                                'age_days': age_days,
                                'return_pct': return_pct,
                                'entry_price': entry_price,
                                'current_price': current_price,
                                'quantity': quantity
                            })
                            
                            status = "WILL BE PRUNED" if return_pct < 2.0 else "OK"
                            print(f"{ticker:12} | Age: {age_days:3d} days | Return: {return_pct:6.2f}% | Status: {status}")
                        except:
                            pass
                
                if not eligible_positions:
                    print("No positions older than 3 days found.")
                else:
                    # Ask for exclusions
                    if not skip_confirmation:
                        print("\n" + "=" * 60)
                        print("EXCLUSIONS")
                        print("=" * 60)
                        print("Enter tickers to exclude from age-based pruning (comma-separated, or press Enter for none):")
                        print("Tickers marked 'WILL BE PRUNED' above will be sold unless excluded.")
                        exclusion_input = input("Exclusions: ").strip()
                        if exclusion_input:
                            exclusions = [ticker.strip().upper() for ticker in exclusion_input.split(',')]
                            print(f"Excluding: {', '.join(exclusions)}")
                
                # Calculate age-based returns
                age_based_underperformers = self.calculate_age_based_returns(cnc_positions, all_orders, exclusions)
            else:
                self.logger.info("No order history found. Skipping age-based analysis.")
        
        # Summary
        self.logger.info("\n" + "=" * 60)
        self.logger.info("PRUNING SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Total CNC positions: {len(cnc_positions)}")
        
        if today_orders:
            self.logger.info(f"Day 1 underperformers (< {self.day1_return_threshold}%): {len(underperformers)}")
            if underperformers:
                for ticker, day1_return, _ in underperformers:
                    self.logger.info(f"  - {ticker}: {day1_return:.2f}%")
        
        if include_age_based:
            self.logger.info(f"Age-based underperformers (>3 days, <2% growth): {len(age_based_underperformers)}")
            if age_based_underperformers:
                for ticker, return_pct, age_days, _ in age_based_underperformers:
                    self.logger.info(f"  - {ticker}: {return_pct:.2f}% after {age_days} days")
        
        # Handle dry run
        if dry_run:
            if underperformers:
                print("\n" + "=" * 60)
                print("DRY RUN - DAY 1 POSITIONS THAT WOULD BE EXITED:")
                print("=" * 60)
                total_value = 0
                for ticker, day1_return, position_info in underperformers:
                    qty = position_info['quantity']
                    current_price = position_info['current_price']
                    value = qty * current_price
                    total_value += value
                    print(f"{ticker}: {qty} shares @ ₹{current_price:.2f} = ₹{value:,.2f} (Return: {day1_return:.2f}%)")
                print(f"\nTotal value that would be sold: ₹{total_value:,.2f}")
            
            if age_based_underperformers:
                print("\n" + "=" * 60)
                print("DRY RUN - AGE-BASED POSITIONS THAT WOULD BE EXITED:")
                print("=" * 60)
                total_value = 0
                for ticker, return_pct, age_days, position_info in age_based_underperformers:
                    qty = position_info['quantity']
                    current_price = position_info['current_price']
                    value = qty * current_price
                    total_value += value
                    print(f"{ticker}: {qty} shares @ ₹{current_price:.2f} = ₹{value:,.2f} (Return: {return_pct:.2f}%, Age: {age_days} days)")
                print(f"\nTotal value that would be sold: ₹{total_value:,.2f}")
                print("=" * 60)
        else:
            # Place exit orders for Day 1 underperformers
            if underperformers:
                self.place_exit_orders(underperformers, skip_confirmation=skip_confirmation, is_age_based=False)
            
            # Place exit orders for age-based underperformers
            if age_based_underperformers:
                self.place_exit_orders(age_based_underperformers, skip_confirmation=skip_confirmation, is_age_based=True)
        
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Portfolio pruning completed")
        self.logger.info("=" * 60)
        
        return True

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Portfolio Pruning - Exit underperforming positions based on Day 1 returns and age-based criteria"
    )
    parser.add_argument(
        "--user",
        help="User name for which to run pruning"
    )
    # Removed --force argument as time check is no longer needed
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze positions without placing orders"
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip confirmation prompt (for automated runs)"
    )
    parser.add_argument(
        "--no-age-based",
        action="store_true",
        help="Disable age-based pruning (only use Day 1 returns)"
    )
    return parser.parse_args()

def get_available_users(config) -> List[str]:
    """Get list of available users from config and orders directory"""
    users = set()
    
    # Get users from config file
    for section in config.sections():
        if section.startswith('API_CREDENTIALS_'):
            user = section.replace('API_CREDENTIALS_', '')
            users.add(user)
    
    # Also check Current_Orders directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    daily_dir = os.path.dirname(script_dir)
    orders_dir = os.path.join(daily_dir, "Current_Orders")
    
    if os.path.exists(orders_dir):
        for d in os.listdir(orders_dir):
            if os.path.isdir(os.path.join(orders_dir, d)):
                users.add(d)
    
    return sorted(list(users))

def prompt_for_user(available_users: List[str]) -> Optional[str]:
    """Prompt user to select from available users"""
    print("\n" + "=" * 50)
    print("Portfolio Pruning - User Selection")
    print("=" * 50)
    print("\nAvailable users:")
    for i, user in enumerate(available_users, 1):
        print(f"  {i}. {user}")
    print("  0. Exit")
    
    while True:
        try:
            choice = input("\nSelect user number (or 0 to exit): ").strip()
            
            if not choice:
                continue
                
            choice_num = int(choice)
            
            if choice_num == 0:
                print("Exiting...")
                return None
            
            if 1 <= choice_num <= len(available_users):
                selected_user = available_users[choice_num - 1]
                print(f"\nSelected user: {selected_user}")
                return selected_user
            else:
                print(f"Invalid choice. Please select 1-{len(available_users)} or 0 to exit.")
                
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\n\nOperation cancelled.")
            return None

def main():
    args = parse_args()
    
    # Load config
    try:
        config = load_daily_config()
    except Exception as e:
        print(f"Error loading config: {e}")
        return 1
    
    # Determine user
    if args.user:
        user_name = args.user
        # Verify user exists
        available_users = get_available_users(config)
        if user_name not in available_users:
            print(f"Error: User '{user_name}' not found.")
            print(f"Available users: {', '.join(available_users)}")
            return 1
    else:
        # Get available users
        available_users = get_available_users(config)
        
        if not available_users:
            print("No users found in configuration.")
            return 1
        
        if len(available_users) == 1:
            # Only one user, use it automatically
            user_name = available_users[0]
            print(f"Using the only available user: {user_name}")
        else:
            # Multiple users, prompt for selection
            user_name = prompt_for_user(available_users)
            if user_name is None:
                return 0  # User chose to exit
    
    # Setup logging
    logger = setup_logging(user_name)
    
    # Log current market time
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist)
    logger.info(f"Current IST time: {current_time.strftime('%H:%M:%S')}")
    
    # Get user credentials
    user_credentials = get_user_from_config(user_name, config)
    if not user_credentials:
        logger.error(f"Invalid credentials for user {user_name}")
        return 1
    
    # Create pruner instance
    try:
        pruner = PortfolioPruner(user_credentials, config)
        
        # Run pruning with appropriate flags
        success = pruner.run_pruning(
            dry_run=args.dry_run,
            skip_confirmation=args.no_confirm,
            include_age_based=not args.no_age_based
        )
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())