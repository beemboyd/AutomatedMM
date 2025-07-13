#!/usr/bin/env python3
"""
One Ticker Sell Script

This script allows selling a specific ticker across all user portfolios.
It gathers all positions for the specified ticker, shows a summary,
and executes sell orders after user confirmation.

Usage: python One_ticker_sell.py
"""

import os
import sys
import logging
import argparse
import configparser
from datetime import datetime
import pytz
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from tabulate import tabulate

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kiteconnect import KiteConnect
from user_context_manager import (
    get_context_manager,
    UserCredentials
)

class OneTickerSeller:
    """
    Manages selling a specific ticker across all user portfolios
    """
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.config = self._load_config()
        self.context_manager = get_context_manager()
        self.exchange = self.config.get('DEFAULT', 'exchange', fallback='NSE')
        
    def _setup_logging(self):
        """Set up logging configuration"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, 'one_ticker_sell.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ],
            force=True
        )
        
        return logging.getLogger(__name__)
    
    def _load_config(self):
        """Load configuration from Daily/config.ini file"""
        config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"config.ini file not found at {config_path}")
        
        config.read(config_path)
        return config
    
    def get_all_users(self) -> List[UserCredentials]:
        """Get all available users from config"""
        users = []
        for section in self.config.sections():
            if section.startswith('API_CREDENTIALS_'):
                user_name = section.replace('API_CREDENTIALS_', '')
                api_key = self.config.get(section, 'api_key', fallback='')
                api_secret = self.config.get(section, 'api_secret', fallback='')
                access_token = self.config.get(section, 'access_token', fallback='')
                
                if api_key and api_secret and access_token:
                    users.append(UserCredentials(
                        name=user_name,
                        api_key=api_key,
                        api_secret=api_secret,
                        access_token=access_token
                    ))
        
        return users
    
    def get_ticker_from_user(self) -> str:
        """Get ticker symbol from user input"""
        print("\n" + "=" * 60)
        print("ONE TICKER SELL - Portfolio-wide Ticker Sale")
        print("=" * 60)
        
        while True:
            ticker = input("\nEnter ticker symbol to sell (or 'exit' to quit): ").strip().upper()
            
            if ticker.lower() == 'exit':
                print("Exiting...")
                sys.exit(0)
            
            if ticker and ticker.isalnum():
                confirm = input(f"\nYou entered: {ticker}. Is this correct? (y/n): ").strip().lower()
                if confirm == 'y':
                    return ticker
                else:
                    print("Let's try again...")
            else:
                print("Invalid ticker symbol. Please enter a valid alphanumeric ticker.")
    
    def gather_positions(self, ticker: str) -> Dict[str, Dict]:
        """
        Gather all positions for the specified ticker across all users
        
        Returns:
            Dict with user as key and position details as value
        """
        positions = {}
        users = self.get_all_users()
        
        print(f"\nSearching for {ticker} positions across {len(users)} users...")
        
        for user in users:
            try:
                # Set user context
                self.context_manager.set_current_user(user.name, user)
                
                # Initialize KiteConnect for this user
                kite = KiteConnect(api_key=user.api_key)
                kite.set_access_token(user.access_token)
                
                # Get positions
                user_positions = kite.positions()
                
                # Check net positions for the ticker
                for pos in user_positions.get('net', []):
                    if (pos.get('tradingsymbol') == ticker and 
                        pos.get('product') == 'CNC' and 
                        int(pos.get('quantity', 0)) > 0):
                        
                        positions[user.name] = {
                            'quantity': int(pos.get('quantity', 0)),
                            'average_price': float(pos.get('average_price', 0)),
                            'last_price': float(pos.get('last_price', 0)),
                            'pnl': float(pos.get('pnl', 0)),
                            'value': float(pos.get('value', 0))
                        }
                        self.logger.info(f"Found {ticker} position for {user.name}: {pos.get('quantity')} shares")
                        break
                
                # Also check holdings for T1 positions
                holdings = kite.holdings()
                for holding in holdings:
                    if holding.get('tradingsymbol') == ticker:
                        quantity = int(holding.get('quantity', 0))
                        t1_quantity = int(holding.get('t1_quantity', 0))
                        total_quantity = quantity + t1_quantity
                        
                        if total_quantity > 0 and user.name not in positions:
                            positions[user.name] = {
                                'quantity': total_quantity,
                                'settled_quantity': quantity,
                                't1_quantity': t1_quantity,
                                'average_price': float(holding.get('average_price', 0)),
                                'last_price': float(holding.get('last_price', 0)),
                                'pnl': float(holding.get('pnl', 0)),
                                'value': total_quantity * float(holding.get('last_price', 0))
                            }
                            self.logger.info(f"Found {ticker} holding for {user.name}: {total_quantity} shares (T1: {t1_quantity})")
                            break
                
            except Exception as e:
                self.logger.warning(f"Error checking positions for {user.name}: {e}")
                continue
        
        return positions
    
    def display_positions_summary(self, ticker: str, positions: Dict[str, Dict]) -> Tuple[int, float]:
        """
        Display a summary of all positions found
        
        Returns:
            Tuple of (total_quantity, total_value)
        """
        if not positions:
            print(f"\n❌ No positions found for {ticker} across any portfolio.")
            return 0, 0.0
        
        print(f"\n📊 POSITIONS FOUND FOR {ticker}")
        print("=" * 80)
        
        # Prepare data for tabulation
        table_data = []
        total_quantity = 0
        total_value = 0.0
        total_pnl = 0.0
        
        for user, pos in positions.items():
            quantity = pos['quantity']
            value = pos.get('value', 0)
            pnl = pos.get('pnl', 0)
            avg_price = pos.get('average_price', 0)
            last_price = pos.get('last_price', 0)
            
            # Add T1 info if available
            quantity_str = str(quantity)
            if 't1_quantity' in pos and pos['t1_quantity'] > 0:
                quantity_str = f"{quantity} (T1: {pos['t1_quantity']})"
            
            table_data.append([
                user,
                quantity_str,
                f"₹{avg_price:,.2f}",
                f"₹{last_price:,.2f}",
                f"₹{value:,.2f}",
                f"₹{pnl:,.2f}" if pnl >= 0 else f"-₹{abs(pnl):,.2f}",
                f"{(pnl/value*100):.1f}%" if value > 0 else "0.0%"
            ])
            
            total_quantity += quantity
            total_value += value
            total_pnl += pnl
        
        # Display table
        headers = ["User", "Quantity", "Avg Price", "LTP", "Value", "P&L", "P&L %"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        # Display totals
        print("\n" + "=" * 80)
        print(f"TOTAL SHARES: {total_quantity}")
        print(f"TOTAL VALUE: ₹{total_value:,.2f}")
        print(f"TOTAL P&L: ₹{total_pnl:,.2f}" if total_pnl >= 0 else f"TOTAL P&L: -₹{abs(total_pnl):,.2f}")
        print("=" * 80)
        
        return total_quantity, total_value
    
    def confirm_sell(self, ticker: str, positions: Dict[str, Dict], total_quantity: int, total_value: float) -> bool:
        """
        Get user confirmation before executing sell orders
        """
        print(f"\n⚠️  WARNING: You are about to sell ALL {ticker} positions across {len(positions)} portfolios!")
        print(f"   Total shares to be sold: {total_quantity}")
        print(f"   Estimated total value: ₹{total_value:,.2f}")
        
        print("\nThis action will:")
        print("1. Place MARKET SELL orders for all positions")
        print("2. Execute immediately at current market price")
        print("3. Cannot be undone once executed")
        
        # First confirmation
        confirm1 = input("\nDo you want to proceed with selling? (yes/no): ").strip().lower()
        if confirm1 != 'yes':
            print("❌ Sell operation cancelled.")
            return False
        
        # Second confirmation for safety
        confirm2 = input(f"\n🔴 FINAL CONFIRMATION: Type '{ticker}' to confirm selling all {ticker} positions: ").strip().upper()
        if confirm2 != ticker:
            print("❌ Sell operation cancelled - confirmation mismatch.")
            return False
        
        return True
    
    def execute_sell_orders(self, ticker: str, positions: Dict[str, Dict]):
        """
        Execute sell orders for all positions
        """
        print("\n🚀 EXECUTING SELL ORDERS...")
        print("=" * 60)
        
        success_count = 0
        failed_users = []
        
        for user_name, position in positions.items():
            try:
                # Get user credentials
                user = next((u for u in self.get_all_users() if u.name == user_name), None)
                if not user:
                    self.logger.error(f"Could not find credentials for {user_name}")
                    failed_users.append((user_name, "No credentials"))
                    continue
                
                # Set user context
                self.context_manager.set_current_user(user.name, user)
                
                # Initialize KiteConnect
                kite = KiteConnect(api_key=user.api_key)
                kite.set_access_token(user.access_token)
                
                # Place sell order
                quantity = position['quantity']
                
                order_params = {
                    "variety": "regular",
                    "exchange": self.exchange,
                    "tradingsymbol": ticker,
                    "transaction_type": "SELL",
                    "quantity": quantity,
                    "product": "CNC",
                    "order_type": "MARKET",
                    "validity": "DAY"
                }
                
                order_id = kite.place_order(**order_params)
                
                print(f"✅ {user_name}: Sell order placed for {quantity} shares. Order ID: {order_id}")
                self.logger.info(f"Sell order placed for {user_name}: {ticker} x {quantity}, Order ID: {order_id}")
                success_count += 1
                
            except Exception as e:
                error_msg = str(e)
                print(f"❌ {user_name}: Failed to place order - {error_msg}")
                self.logger.error(f"Failed to place sell order for {user_name}: {error_msg}")
                failed_users.append((user_name, error_msg))
        
        # Summary
        print("\n" + "=" * 60)
        print("EXECUTION SUMMARY")
        print("=" * 60)
        print(f"✅ Successful orders: {success_count}/{len(positions)}")
        
        if failed_users:
            print(f"\n❌ Failed orders: {len(failed_users)}")
            for user, error in failed_users:
                print(f"   - {user}: {error}")
        
        print("\n📝 Check individual broker terminals for order status.")
        self.logger.info(f"Sell execution completed: {success_count} success, {len(failed_users)} failed")
    
    def run(self):
        """Main execution flow"""
        try:
            # Get ticker from user
            ticker = self.get_ticker_from_user()
            
            # Gather positions
            positions = self.gather_positions(ticker)
            
            # Display summary
            total_quantity, total_value = self.display_positions_summary(ticker, positions)
            
            if not positions:
                return
            
            # Get confirmation
            if not self.confirm_sell(ticker, positions, total_quantity, total_value):
                return
            
            # Execute sell orders
            self.execute_sell_orders(ticker, positions)
            
        except KeyboardInterrupt:
            print("\n\n❌ Operation cancelled by user.")
            self.logger.info("Operation cancelled by user")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            self.logger.exception("Unexpected error in one_ticker_sell")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Sell a specific ticker across all user portfolios"
    )
    args = parser.parse_args()
    
    seller = OneTickerSeller()
    seller.run()

if __name__ == "__main__":
    main()