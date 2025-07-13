#!/usr/bin/env python3
"""
Portfolio Pruning Script - SMA Based

This script prunes positions that are trading below the 20 SMA in the hourly timeframe.

Exit Rule: If current price < 20 SMA (hourly), exit position.

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
import pandas as pd
import numpy as np

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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
    
    log_file = os.path.join(log_dir, f'prune_portfolio_sma_{user_name}.log')
    
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

class PortfolioPrunerSMA:
    """
    Portfolio pruning system based on 20 SMA in hourly timeframe.
    
    Exit Rule: If current price < 20 SMA (hourly), exit position.
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
        
        # SMA period
        self.sma_period = 20
        
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
        self.logger.info("PORTFOLIO PRUNING - 20 SMA ANALYSIS (HOURLY)")
        self.logger.info("Exit Rule: If current price < 20 SMA (hourly), exit position")
        self.logger.info("This helps exit positions that have lost momentum")
        self.logger.info("=" * 60)
    
    def calculate_sma(self, candles: List[Dict], period: int) -> Optional[float]:
        """Calculate Simple Moving Average from candle data"""
        if len(candles) < period:
            return None
        
        # Get the last 'period' closing prices
        closes = [float(candle['close']) for candle in candles[-period:]]
        return sum(closes) / period
    
    def get_hourly_data(self, ticker: str) -> Optional[List[Dict]]:
        """Get hourly candle data for a ticker"""
        try:
            # Try to get instrument token from data_handler first
            instrument_token = None
            try:
                instrument_token = self.data_handler.get_instrument_token(ticker)
            except:
                pass
            
            # If that fails, fetch directly from Kite
            if not instrument_token:
                try:
                    instruments = self.kite.instruments(self.exchange)
                    for inst in instruments:
                        if inst['tradingsymbol'] == ticker:
                            instrument_token = inst['instrument_token']
                            break
                except Exception as e:
                    self.logger.error(f"Error fetching instruments: {e}")
            
            if not instrument_token:
                self.logger.error(f"Could not find instrument token for {ticker}")
                return None
            
            # Calculate from_date (need at least 20 hours of data)
            to_date = datetime.now()
            # Get 5 days of hourly data to ensure we have enough
            from_date = to_date - timedelta(days=5)
            
            # Fetch historical data
            candles = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval="60minute"
            )
            
            return candles
            
        except Exception as e:
            self.logger.error(f"Error fetching hourly data for {ticker}: {e}")
            return None
    
    def analyze_positions_sma(self, positions: List[Dict]) -> List[Tuple[str, float, float, Dict]]:
        """Analyze positions against 20 SMA and identify those that closed below SMA"""
        below_sma_positions = []
        excluded_tickers = []
        
        # Track all positions for summary
        all_positions_analysis = []
        
        for position in positions:
            ticker = position.get('tradingsymbol', '')
            quantity = int(position.get('quantity', 0))
            
            # Skip if no position
            if quantity <= 0:
                continue
            
            # Get current price
            try:
                ltp_data = self.kite.ltp(f"{self.exchange}:{ticker}")
                current_price = ltp_data[f"{self.exchange}:{ticker}"]["last_price"]
            except Exception as e:
                self.logger.error(f"Error fetching price for {ticker}: {e}")
                continue
            
            # Get hourly data and calculate SMA
            hourly_data = self.get_hourly_data(ticker)
            if not hourly_data:
                self.logger.warning(f"Could not get hourly data for {ticker}")
                continue
            
            sma_20 = self.calculate_sma(hourly_data, self.sma_period)
            if sma_20 is None:
                self.logger.warning(f"Could not calculate 20 SMA for {ticker}")
                continue
            
            # Get the last closed hourly candle
            if len(hourly_data) > 0:
                last_closed_candle = hourly_data[-1]
                last_close = float(last_closed_candle['close'])
                last_close_time = last_closed_candle['date']
            else:
                self.logger.warning(f"No hourly data available for {ticker}")
                continue
            
            # Calculate percentage difference for current price
            sma_diff_pct = ((current_price - sma_20) / sma_20) * 100
            
            # Calculate if last hourly close was below SMA
            last_close_below_sma = last_close < sma_20
            last_close_diff_pct = ((last_close - sma_20) / sma_20) * 100
            
            # Store analysis for all positions
            all_positions_analysis.append({
                'ticker': ticker,
                'current_price': current_price,
                'last_close': last_close,
                'sma_20': sma_20,
                'diff_pct': sma_diff_pct,
                'last_close_diff_pct': last_close_diff_pct,
                'quantity': quantity,
                'position_above_sma': current_price >= sma_20,
                'closed_below_sma': last_close_below_sma
            })
            
            # Log the analysis
            status = "ABOVE" if current_price >= sma_20 else "BELOW"
            close_status = "CLOSED BELOW" if last_close_below_sma else "CLOSED ABOVE"
            self.logger.info(f"{ticker}: Price: ₹{current_price:.2f}, Last Close: ₹{last_close:.2f}, "
                           f"20 SMA: ₹{sma_20:.2f}, Diff: {sma_diff_pct:+.2f}% - {status} SMA ({close_status})")
            
            # Check if CLOSED below SMA (not just current price)
            if last_close_below_sma:
                avg_price = float(position.get('average_price', 0)) or float(position.get('last_price', current_price))
                
                below_sma_positions.append((ticker, current_price, sma_20, {
                    'quantity': quantity,
                    'average_price': avg_price,
                    'current_price': current_price,
                    'last_close': last_close,
                    'sma_20': sma_20,
                    'diff_pct': sma_diff_pct,
                    'last_close_diff_pct': last_close_diff_pct,
                    'position_value': quantity * current_price
                }))
                self.logger.warning(f"{ticker} CLOSED BELOW 20 SMA by {abs(last_close_diff_pct):.2f}%")
        
        # Show summary of all positions
        if all_positions_analysis:
            print("\n" + "=" * 100)
            print("ALL POSITIONS ANALYSIS:")
            print("=" * 100)
            print(f"{'Ticker':<12} {'Current':<10} {'Last Close':<10} {'20 SMA':<10} {'Close Diff%':<12} {'Status':<15} {'Qty':<8}")
            print("-" * 100)
            
            for pos in sorted(all_positions_analysis, key=lambda x: x['last_close_diff_pct']):
                # Determine status based on last close
                if pos['closed_below_sma']:
                    status = "CLOSED BELOW"
                    status_color = "\033[91m"  # Red
                else:
                    status = "CLOSED ABOVE"
                    status_color = "\033[92m"  # Green
                reset_color = "\033[0m"
                
                print(f"{pos['ticker']:<12} "
                      f"₹{pos['current_price']:<9.2f} "
                      f"₹{pos['last_close']:<9.2f} "
                      f"₹{pos['sma_20']:<9.2f} "
                      f"{pos['last_close_diff_pct']:>+11.2f}% "
                      f"{status_color}{status:<15}{reset_color} "
                      f"{pos['quantity']:<8}")
            
            print("=" * 100)
            
            # Summary statistics
            total_positions = len(all_positions_analysis)
            closed_above_sma = sum(1 for p in all_positions_analysis if not p['closed_below_sma'])
            closed_below_sma = sum(1 for p in all_positions_analysis if p['closed_below_sma'])
            
            print(f"\nTotal Positions: {total_positions}")
            print(f"Closed Above 20 SMA: {closed_above_sma} ({closed_above_sma/total_positions*100:.1f}%)")
            print(f"Closed Below 20 SMA: {closed_below_sma} ({closed_below_sma/total_positions*100:.1f}%)")
        
        # If positions are below SMA, ask for exclusions
        if below_sma_positions and not hasattr(self, 'skip_confirmation'):
            print("\n" + "=" * 80)
            print("POSITIONS THAT CLOSED BELOW 20 SMA (TO BE SOLD):")
            print("=" * 80)
            
            for i, (ticker, current_price, sma_20, info) in enumerate(below_sma_positions, 1):
                last_close = info['last_close']
                last_close_diff = info['last_close_diff_pct']
                print(f"{i}. {ticker}: Last Close ₹{last_close:.2f} < SMA ₹{sma_20:.2f} "
                      f"(Closed {abs(last_close_diff):.2f}% below SMA)")
            
            print("\nWould you like to exclude any tickers from being sold?")
            exclude_input = input("Enter ticker numbers to exclude (comma-separated) or press Enter to continue: ").strip()
            
            if exclude_input:
                try:
                    exclude_indices = [int(x.strip()) - 1 for x in exclude_input.split(',')]
                    excluded_tickers = []
                    
                    # Create filtered list
                    filtered_positions = []
                    for i, position_data in enumerate(below_sma_positions):
                        if i in exclude_indices:
                            excluded_tickers.append(position_data[0])
                        else:
                            filtered_positions.append(position_data)
                    
                    below_sma_positions = filtered_positions
                    
                    if excluded_tickers:
                        print(f"\nExcluded tickers: {', '.join(excluded_tickers)}")
                        self.logger.info(f"User excluded tickers: {', '.join(excluded_tickers)}")
                        
                except Exception as e:
                    print(f"Error parsing exclusions: {e}. Continuing with all positions.")
        
        return below_sma_positions
    
    def place_exit_orders(self, below_sma_positions: List[Tuple[str, float, float, Dict]], skip_confirmation: bool = False):
        """Place exit orders for positions below SMA"""
        if not below_sma_positions:
            self.logger.info("No positions below 20 SMA to exit")
            return
        
        # Show summary and ask for confirmation
        if not skip_confirmation:
            print("\n" + "=" * 80)
            print("POSITIONS TO BE EXITED (CLOSED BELOW 20 SMA):")
            print("=" * 80)
            total_value = 0
            for ticker, current_price, sma_20, position_info in below_sma_positions:
                qty = position_info['quantity']
                value = position_info['position_value']
                total_value += value
                last_close = position_info['last_close']
                last_close_diff = position_info['last_close_diff_pct']
                print(f"{ticker}: {qty} shares @ Current ₹{current_price:.2f} = ₹{value:,.2f}")
                print(f"       Last Close: ₹{last_close:.2f} | SMA: ₹{sma_20:.2f} | "
                      f"Closed {abs(last_close_diff):.2f}% below SMA")
            
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
        
        self.logger.info(f"Placing exit orders for {len(below_sma_positions)} positions below 20 SMA")
        
        for ticker, current_price, sma_20, position_info in below_sma_positions:
            try:
                quantity = position_info['quantity']
                
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
                               f"(Below 20 SMA by {abs(position_info['diff_pct']):.2f}%). Order ID: {order_id}")
                
                # Calculate expected P&L if average price is available
                avg_price = position_info.get('average_price', 0)
                if avg_price > 0:
                    expected_pnl = (current_price - avg_price) * quantity
                    expected_pnl_pct = ((current_price - avg_price) / avg_price) * 100
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
    
    def run_pruning(self, dry_run: bool = False, skip_confirmation: bool = False):
        """Main pruning logic"""
        self.skip_confirmation = skip_confirmation
        
        self.logger.info("=" * 60)
        self.logger.info(f"Starting Portfolio Pruning (20 SMA) at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
        
        # Analyze positions against 20 SMA
        below_sma_positions = self.analyze_positions_sma(cnc_positions)
        
        # Summary
        self.logger.info("=" * 60)
        self.logger.info("PRUNING SUMMARY")
        self.logger.info(f"Total positions analyzed: {len(cnc_positions)}")
        self.logger.info(f"Positions below 20 SMA: {len(below_sma_positions)}")
        
        if below_sma_positions:
            self.logger.info("Positions to exit:")
            for ticker, current_price, sma_20, info in below_sma_positions:
                self.logger.info(f"  - {ticker}: ₹{current_price:.2f} < ₹{sma_20:.2f} "
                               f"(Below by {abs(info['diff_pct']):.2f}%)")
        
        # Place exit orders (or show what would be done in dry run)
        if dry_run:
            if below_sma_positions:
                print("\n" + "=" * 80)
                print("DRY RUN - POSITIONS THAT WOULD BE EXITED:")
                print("=" * 80)
                total_value = 0
                for ticker, current_price, sma_20, position_info in below_sma_positions:
                    qty = position_info['quantity']
                    value = position_info['position_value']
                    total_value += value
                    last_close = position_info['last_close']
                    last_close_diff = position_info['last_close_diff_pct']
                    print(f"{ticker}: {qty} shares @ Current ₹{current_price:.2f} = ₹{value:,.2f}")
                    print(f"       Last Close: ₹{last_close:.2f} < SMA: ₹{sma_20:.2f} "
                          f"(Closed {abs(last_close_diff):.2f}% below)")
                print(f"\nTotal value that would be sold: ₹{total_value:,.2f}")
                print("=" * 80)
        else:
            self.place_exit_orders(below_sma_positions, skip_confirmation=skip_confirmation)
        
        self.logger.info("=" * 60)
        self.logger.info("Portfolio pruning completed")
        self.logger.info("=" * 60)
        
        return True

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Portfolio Pruning - Exit positions below 20 SMA (hourly)"
    )
    parser.add_argument(
        "--user",
        help="User name for which to run pruning"
    )
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
        pruner = PortfolioPrunerSMA(user_credentials, config)
        
        # Run pruning with appropriate flags
        success = pruner.run_pruning(
            dry_run=args.dry_run,
            skip_confirmation=args.no_confirm
        )
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())