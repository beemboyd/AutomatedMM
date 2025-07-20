#!/usr/bin/env python3
"""
Double Up Position Size - Interactive Portfolio Management Tool

This program allows users to double their position sizes on performing stocks.
It reads the current portfolio, calculates performance metrics, and presents
an interactive interface to select stocks for position doubling.

Features:
- Displays current portfolio with performance metrics
- Sorts stocks by performance (best to worst)
- Interactive selection of stocks to double up
- Places CNC orders to add equal quantity
- Confirmation prompts for safety
"""

import os
import sys
import json
import logging
import argparse
import configparser
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import pandas as pd
from tabulate import tabulate
import time

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

def setup_logging():
    """Set up basic logging"""
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger()

def get_available_users(config) -> List[str]:
    """Get list of available users from config"""
    users = []
    for section in config.sections():
        if section.startswith('API_CREDENTIALS_'):
            user = section.replace('API_CREDENTIALS_', '')
            users.append(user)
    return sorted(users)

def prompt_for_user(available_users: List[str]) -> Optional[str]:
    """Prompt user to select from available users"""
    print("\n" + "=" * 60)
    print("Double Up Position Size - User Selection")
    print("=" * 60)
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

class PositionDoubler:
    """Main class for doubling position sizes"""
    
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
        self.product_type = 'CNC'  # Always CNC for position doubling
        
        # Initialize KiteConnect client
        try:
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(self.access_token)
            profile = self.kite.profile()
            self.logger.info(f"Connected as {profile['user_name']} ({profile['user_id']})")
        except Exception as e:
            self.logger.error(f"Failed to initialize KiteConnect: {e}")
            raise
        
        # Portfolio data
        self.positions = []
        self.holdings = []
        self.portfolio_data = []
    
    def get_portfolio_data(self) -> List[Dict]:
        """Fetch and combine positions and holdings data"""
        try:
            # Get positions
            positions_response = self.kite.positions()
            net_positions = positions_response.get('net', [])
            
            # Filter CNC positions with quantity > 0
            cnc_positions = []
            for pos in net_positions:
                if pos.get('product') == 'CNC' and int(pos.get('quantity', 0)) > 0:
                    cnc_positions.append({
                        'symbol': pos['tradingsymbol'],
                        'quantity': int(pos['quantity']),
                        'avg_price': float(pos['average_price']),
                        'ltp': 0,  # Will be updated
                        'pnl': float(pos.get('pnl', 0)),
                        'pnl_percent': 0,  # Will be calculated
                        'current_value': 0,  # Will be calculated
                        'investment': 0,  # Will be calculated
                        'source': 'positions'
                    })
            
            # Get holdings
            holdings = self.kite.holdings()
            
            # Process holdings (avoid duplicates)
            existing_symbols = {pos['symbol'] for pos in cnc_positions}
            
            for holding in holdings:
                symbol = holding['tradingsymbol']
                quantity = int(holding['quantity'])
                
                if quantity > 0 and symbol not in existing_symbols:
                    cnc_positions.append({
                        'symbol': symbol,
                        'quantity': quantity,
                        'avg_price': float(holding['average_price']),
                        'ltp': float(holding.get('last_price', 0)),
                        'pnl': float(holding.get('pnl', 0)),
                        'pnl_percent': 0,  # Will be calculated
                        'current_value': 0,  # Will be calculated
                        'investment': 0,  # Will be calculated
                        'source': 'holdings'
                    })
            
            self.portfolio_data = cnc_positions
            self.logger.info(f"Found {len(self.portfolio_data)} CNC positions")
            
            return self.portfolio_data
            
        except Exception as e:
            self.logger.error(f"Error fetching portfolio data: {e}")
            return []
    
    def update_live_prices(self):
        """Update live prices for all positions"""
        if not self.portfolio_data:
            return
        
        try:
            # Create list of symbols for LTP fetch
            symbols = [f"{self.exchange}:{pos['symbol']}" for pos in self.portfolio_data]
            
            # Fetch LTP in batches (max 500 per request)
            batch_size = 500
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i+batch_size]
                ltp_data = self.kite.ltp(batch)
                
                # Update portfolio data with live prices
                for pos in self.portfolio_data[i:i+batch_size]:
                    symbol_key = f"{self.exchange}:{pos['symbol']}"
                    if symbol_key in ltp_data:
                        pos['ltp'] = ltp_data[symbol_key]['last_price']
                        
                        # Calculate metrics
                        pos['investment'] = pos['avg_price'] * pos['quantity']
                        pos['current_value'] = pos['ltp'] * pos['quantity']
                        pos['pnl'] = pos['current_value'] - pos['investment']
                        pos['pnl_percent'] = (pos['pnl'] / pos['investment']) * 100 if pos['investment'] > 0 else 0
            
            self.logger.info("Updated live prices for all positions")
            
        except Exception as e:
            self.logger.error(f"Error updating live prices: {e}")
    
    def display_portfolio(self):
        """Display portfolio in a formatted table sorted by performance"""
        if not self.portfolio_data:
            print("\nNo positions found in portfolio.")
            return
        
        # Sort by P&L percentage (descending)
        sorted_portfolio = sorted(self.portfolio_data, key=lambda x: x['pnl_percent'], reverse=True)
        
        # Prepare data for table
        table_data = []
        for i, pos in enumerate(sorted_portfolio, 1):
            # Color coding for P&L
            pnl_color = '\033[92m' if pos['pnl'] >= 0 else '\033[91m'  # Green for profit, Red for loss
            reset_color = '\033[0m'
            
            table_data.append([
                i,
                pos['symbol'],
                pos['quantity'],
                f"₹{pos['avg_price']:.2f}",
                f"₹{pos['ltp']:.2f}",
                f"₹{pos['investment']:,.2f}",
                f"₹{pos['current_value']:,.2f}",
                f"{pnl_color}₹{pos['pnl']:,.2f}{reset_color}",
                f"{pnl_color}{pos['pnl_percent']:.2f}%{reset_color}"
            ])
        
        # Calculate totals
        total_investment = sum(pos['investment'] for pos in self.portfolio_data)
        total_value = sum(pos['current_value'] for pos in self.portfolio_data)
        total_pnl = sum(pos['pnl'] for pos in self.portfolio_data)
        total_pnl_percent = (total_pnl / total_investment) * 100 if total_investment > 0 else 0
        
        # Print table
        print("\n" + "=" * 120)
        print(f"PORTFOLIO PERFORMANCE - {self.user_name}")
        print("=" * 120)
        
        headers = ['#', 'Symbol', 'Qty', 'Avg Price', 'LTP', 'Investment', 'Current Value', 'P&L', 'P&L %']
        print(tabulate(table_data, headers=headers, tablefmt='grid', numalign='right'))
        
        # Print summary
        pnl_color = '\033[92m' if total_pnl >= 0 else '\033[91m'
        reset_color = '\033[0m'
        
        print("\n" + "-" * 120)
        print(f"TOTAL: Investment: ₹{total_investment:,.2f} | "
              f"Current Value: ₹{total_value:,.2f} | "
              f"P&L: {pnl_color}₹{total_pnl:,.2f} ({total_pnl_percent:.2f}%){reset_color}")
        print("-" * 120)
    
    def select_positions_to_double(self) -> List[Dict]:
        """Interactive selection of positions to double"""
        if not self.portfolio_data:
            return []
        
        print("\n" + "=" * 60)
        print("SELECT POSITIONS TO DOUBLE")
        print("=" * 60)
        print("\nEnter position numbers to double (comma-separated)")
        print("Example: 1,3,5 or 1-5 or ALL")
        print("Enter 0 or press Enter to cancel")
        
        while True:
            try:
                selection = input("\nYour selection: ").strip().upper()
                
                if not selection or selection == '0':
                    print("Cancelled.")
                    return []
                
                selected_positions = []
                
                if selection == 'ALL':
                    selected_positions = self.portfolio_data.copy()
                else:
                    # Parse selection
                    selected_indices = set()
                    
                    for part in selection.split(','):
                        part = part.strip()
                        if '-' in part:
                            # Range selection
                            try:
                                start, end = part.split('-')
                                start = int(start)
                                end = int(end)
                                selected_indices.update(range(start, end + 1))
                            except:
                                print(f"Invalid range: {part}")
                                continue
                        else:
                            # Single selection
                            try:
                                selected_indices.add(int(part))
                            except:
                                print(f"Invalid number: {part}")
                                continue
                    
                    # Get selected positions
                    sorted_portfolio = sorted(self.portfolio_data, key=lambda x: x['pnl_percent'], reverse=True)
                    for idx in selected_indices:
                        if 1 <= idx <= len(sorted_portfolio):
                            selected_positions.append(sorted_portfolio[idx - 1])
                
                if selected_positions:
                    return selected_positions
                else:
                    print("No valid positions selected.")
                    
            except KeyboardInterrupt:
                print("\n\nCancelled.")
                return []
            except Exception as e:
                print(f"Error: {e}")
    
    def confirm_and_place_orders(self, selected_positions: List[Dict]) -> bool:
        """Confirm selection and place orders"""
        if not selected_positions:
            return False
        
        # Calculate total investment needed
        total_new_investment = sum(pos['ltp'] * pos['quantity'] for pos in selected_positions)
        
        # Display confirmation
        print("\n" + "=" * 80)
        print("CONFIRMATION - POSITIONS TO DOUBLE")
        print("=" * 80)
        
        table_data = []
        for pos in selected_positions:
            new_investment = pos['ltp'] * pos['quantity']
            table_data.append([
                pos['symbol'],
                pos['quantity'],
                f"₹{pos['ltp']:.2f}",
                f"₹{new_investment:,.2f}",
                f"{pos['pnl_percent']:.2f}%"
            ])
        
        headers = ['Symbol', 'Qty to Add', 'Current Price', 'Investment Needed', 'Current P&L %']
        print(tabulate(table_data, headers=headers, tablefmt='grid', numalign='right'))
        
        print(f"\nTotal Investment Required: ₹{total_new_investment:,.2f}")
        print("=" * 80)
        
        # Get available funds
        try:
            funds_response = self.kite.margins()
            available_cash = funds_response['equity']['available']['cash']
            print(f"Available Cash: ₹{available_cash:,.2f}")
            
            if available_cash < total_new_investment:
                print(f"\n⚠️  WARNING: Insufficient funds! Need ₹{total_new_investment - available_cash:,.2f} more.")
        except Exception as e:
            self.logger.warning(f"Could not fetch available funds: {e}")
        
        # Final confirmation
        confirm = input("\nProceed with orders? (YES/NO): ").strip().upper()
        if confirm != 'YES':
            print("Orders cancelled.")
            return False
        
        # Place orders
        successful_orders = 0
        failed_orders = 0
        
        print("\n" + "=" * 60)
        print("PLACING ORDERS")
        print("=" * 60)
        
        for pos in selected_positions:
            try:
                order_params = {
                    "variety": "regular",
                    "exchange": self.exchange,
                    "tradingsymbol": pos['symbol'],
                    "transaction_type": "BUY",
                    "quantity": pos['quantity'],
                    "product": self.product_type,
                    "order_type": "MARKET",
                    "validity": "DAY",
                    "tag": "DOUBLE_UP"
                }
                
                order_id = self.kite.place_order(**order_params)
                print(f"✅ {pos['symbol']}: Order placed successfully (ID: {order_id})")
                successful_orders += 1
                
                # Small delay between orders
                time.sleep(0.5)
                
            except Exception as e:
                print(f"❌ {pos['symbol']}: Failed to place order - {e}")
                failed_orders += 1
        
        print("\n" + "=" * 60)
        print(f"Orders Summary: {successful_orders} successful, {failed_orders} failed")
        print("=" * 60)
        
        return True
    
    def run(self):
        """Main execution flow"""
        print("\n" + "=" * 60)
        print("DOUBLE UP POSITION SIZE")
        print("=" * 60)
        print(f"User: {self.user_name}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Fetch portfolio
        print("\nFetching portfolio data...")
        self.get_portfolio_data()
        
        if not self.portfolio_data:
            print("No CNC positions found.")
            return
        
        # Update live prices
        print("Updating live prices...")
        self.update_live_prices()
        
        # Display portfolio
        self.display_portfolio()
        
        # Select positions
        selected_positions = self.select_positions_to_double()
        
        if selected_positions:
            # Confirm and place orders
            self.confirm_and_place_orders(selected_positions)
        
        print("\nDone.")

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Double up position sizes on performing stocks"
    )
    parser.add_argument(
        "--user",
        help="User name for the operation"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Setup logging
    logger = setup_logging()
    
    # Load config
    try:
        config = load_daily_config()
    except Exception as e:
        print(f"Error loading config: {e}")
        return 1
    
    # Determine user
    if args.user:
        user_name = args.user
        available_users = get_available_users(config)
        if user_name not in available_users:
            print(f"Error: User '{user_name}' not found.")
            print(f"Available users: {', '.join(available_users)}")
            return 1
    else:
        # Interactive user selection
        available_users = get_available_users(config)
        if not available_users:
            print("No users found in configuration.")
            return 1
        
        if len(available_users) == 1:
            user_name = available_users[0]
            print(f"Using the only available user: {user_name}")
        else:
            user_name = prompt_for_user(available_users)
            if user_name is None:
                return 0
    
    # Get user credentials
    user_credentials = get_user_from_config(user_name, config)
    if not user_credentials:
        logger.error(f"Invalid credentials for user {user_name}")
        return 1
    
    # Create and run position doubler
    try:
        doubler = PositionDoubler(user_credentials, config)
        doubler.run()
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())