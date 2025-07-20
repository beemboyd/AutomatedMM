#!/usr/bin/env python3
"""
Sell All CNC Positions

This script sells all CNC (delivery) positions for a selected user.
Includes user selection and confirmation before executing trades.
"""

import sys
import os
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
from datetime import datetime
import json
import time
try:
    from tabulate import tabulate
except ImportError:
    tabulate = None

try:
    from utils.broker_interface import BrokerInterface
except ImportError:
    # Try alternative import path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.broker_interface import BrokerInterface

from state_manager import StateManager
from ..user_context_manager import UserContextManager

# Check if the environment supports colors
SUPPORTS_COLOR = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

# Simple color class to replace colorama
class Colors:
    """Simple ANSI color codes"""
    if SUPPORTS_COLOR:
        RED = '\033[91m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        BLUE = '\033[94m'
        CYAN = '\033[96m'
        RESET = '\033[0m'
        BOLD = '\033[1m'
    else:
        # No colors in non-TTY environments
        RED = ''
        GREEN = ''
        YELLOW = ''
        BLUE = ''
        CYAN = ''
        RESET = ''
        BOLD = ''

# Create color aliases
class Fore:
    RED = Colors.RED
    GREEN = Colors.GREEN
    YELLOW = Colors.YELLOW
    BLUE = Colors.BLUE
    CYAN = Colors.CYAN

class Style:
    RESET_ALL = Colors.RESET

class CNCSeller:
    """Handle selling of all CNC positions"""
    
    def __init__(self):
        self.user_manager = UserContextManager()
        self.selected_user = None
        self.broker = None
        self.state_manager = None
        
    def select_user(self):
        """Allow user to select which user's positions to sell"""
        users = self.user_manager.get_all_users()
        
        if not users:
            print(f"{Fore.RED}No users found in configuration!")
            return False
            
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.YELLOW}Select User for CNC Position Sale")
        print(f"{Fore.CYAN}{'='*60}")
        
        for i, user in enumerate(users, 1):
            print(f"{i}. {user}")
            
        while True:
            try:
                choice = input(f"\n{Fore.GREEN}Enter user number (1-{len(users)}): {Style.RESET_ALL}")
                user_idx = int(choice) - 1
                
                if 0 <= user_idx < len(users):
                    self.selected_user = users[user_idx]
                    print(f"\n{Fore.GREEN}Selected user: {self.selected_user}")
                    return True
                else:
                    print(f"{Fore.RED}Invalid selection. Please try again.")
            except ValueError:
                print(f"{Fore.RED}Please enter a valid number.")
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}Operation cancelled.")
                return False
                
    def initialize_broker(self):
        """Initialize broker connection for selected user"""
        try:
            # Switch to selected user context
            self.user_manager.switch_user(self.selected_user)
            
            # Initialize broker
            self.broker = BrokerInterface(self.selected_user)
            
            # Initialize state manager
            state_file = f'/Users/maverick/PycharmProjects/India-TS/Daily/states/trading_state_{self.selected_user}.json'
            self.state_manager = StateManager(state_file)
            
            return True
            
        except Exception as e:
            print(f"{Fore.RED}Error initializing broker: {e}")
            return False
            
    def get_cnc_positions(self):
        """Get all CNC positions from broker"""
        try:
            positions = self.broker.kite.positions()
            
            # Filter CNC positions
            cnc_positions = []
            for pos in positions['net']:
                if pos['product'] == 'CNC' and pos['quantity'] != 0:
                    cnc_positions.append({
                        'symbol': pos['tradingsymbol'],
                        'quantity': pos['quantity'],
                        'average_price': pos['average_price'],
                        'last_price': pos['last_price'],
                        'pnl': pos['pnl'],
                        'pnl_percent': (pos['pnl'] / (abs(pos['quantity']) * pos['average_price'])) * 100 if pos['average_price'] > 0 else 0,
                        'value': abs(pos['quantity']) * pos['last_price']
                    })
                    
            return cnc_positions
            
        except Exception as e:
            print(f"{Fore.RED}Error fetching positions: {e}")
            return []
            
    def display_positions(self, positions):
        """Display CNC positions in a formatted table"""
        if not positions:
            print(f"\n{Fore.YELLOW}No CNC positions found for {self.selected_user}")
            return
            
        print(f"\n{Fore.CYAN}{'='*100}")
        print(f"{Fore.YELLOW}CNC Positions for {self.selected_user}")
        print(f"{Fore.CYAN}{'='*100}")
        
        # Prepare data for table
        table_data = []
        total_value = 0
        total_pnl = 0
        
        for pos in positions:
            # Color code P&L
            pnl_color = Fore.GREEN if pos['pnl'] >= 0 else Fore.RED
            pnl_str = f"{pnl_color}₹{pos['pnl']:,.2f} ({pos['pnl_percent']:+.2f}%){Style.RESET_ALL}"
            
            table_data.append([
                pos['symbol'],
                pos['quantity'],
                f"₹{pos['average_price']:,.2f}",
                f"₹{pos['last_price']:,.2f}",
                pnl_str,
                f"₹{pos['value']:,.2f}"
            ])
            
            total_value += pos['value']
            total_pnl += pos['pnl']
            
        # Display table
        headers = ['Symbol', 'Quantity', 'Avg Price', 'LTP', 'P&L', 'Value']
        if tabulate:
            print(tabulate(table_data, headers=headers, tablefmt='grid'))
        else:
            # Fallback display without tabulate
            print(f"\n{'Symbol':<15} {'Quantity':>10} {'Avg Price':>12} {'LTP':>12} {'P&L':>20} {'Value':>15}")
            print('-' * 95)
            for row in table_data:
                symbol, qty, avg_price, ltp, pnl, value = row
                # Remove color codes for alignment
                pnl_plain = pnl.replace(Fore.GREEN, '').replace(Fore.RED, '').replace(Style.RESET_ALL, '')
                print(f"{symbol:<15} {qty:>10} {avg_price:>12} {ltp:>12} {pnl_plain:>20} {value:>15}")
        
        # Display totals
        print(f"\n{Fore.CYAN}Summary:")
        print(f"Total Positions: {len(positions)}")
        print(f"Total Value: ₹{total_value:,.2f}")
        pnl_color = Fore.GREEN if total_pnl >= 0 else Fore.RED
        print(f"Total P&L: {pnl_color}₹{total_pnl:,.2f}{Style.RESET_ALL}")
        
    def confirm_sale(self, positions):
        """Get user confirmation before selling"""
        print(f"\n{Fore.YELLOW}{'='*60}")
        print(f"{Fore.RED}⚠️  WARNING: This will SELL ALL CNC positions!")
        print(f"{Fore.YELLOW}{'='*60}")
        
        total_value = sum(pos['value'] for pos in positions)
        print(f"\nYou are about to sell {len(positions)} positions worth ₹{total_value:,.2f}")
        
        # First confirmation
        confirm1 = input(f"\n{Fore.YELLOW}Are you sure you want to proceed? (yes/no): {Style.RESET_ALL}").lower()
        if confirm1 != 'yes':
            print(f"{Fore.GREEN}Operation cancelled.")
            return False
            
        # Second confirmation with explicit typing
        print(f"\n{Fore.RED}This action cannot be undone!")
        confirm2 = input(f"{Fore.YELLOW}Type 'SELL ALL' to confirm: {Style.RESET_ALL}")
        if confirm2 != 'SELL ALL':
            print(f"{Fore.GREEN}Operation cancelled.")
            return False
            
        return True
        
    def execute_sales(self, positions):
        """Execute sell orders for all positions"""
        print(f"\n{Fore.CYAN}Executing sell orders...")
        print(f"{Fore.CYAN}{'='*60}")
        
        successful = 0
        failed = 0
        errors = []
        
        for i, pos in enumerate(positions, 1):
            try:
                print(f"\n[{i}/{len(positions)}] Selling {pos['symbol']}...", end='', flush=True)
                
                # Place sell order
                order_id = self.broker.kite.place_order(
                    variety=self.broker.kite.VARIETY_REGULAR,
                    exchange=self.broker.kite.EXCHANGE_NSE,
                    tradingsymbol=pos['symbol'],
                    transaction_type=self.broker.kite.TRANSACTION_TYPE_SELL,
                    quantity=abs(pos['quantity']),
                    product=self.broker.kite.PRODUCT_CNC,
                    order_type=self.broker.kite.ORDER_TYPE_MARKET
                )
                
                print(f" {Fore.GREEN}✓ Success (Order ID: {order_id})")
                successful += 1
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                print(f" {Fore.RED}✗ Failed: {str(e)}")
                failed += 1
                errors.append({
                    'symbol': pos['symbol'],
                    'error': str(e)
                })
                
        # Display summary
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.YELLOW}Execution Summary:")
        print(f"{Fore.GREEN}Successful: {successful}")
        print(f"{Fore.RED}Failed: {failed}")
        
        if errors:
            print(f"\n{Fore.RED}Failed Orders:")
            for err in errors:
                print(f"  - {err['symbol']}: {err['error']}")
                
        # Update state
        if successful > 0:
            self.update_state(positions, successful, failed)
            
        return successful, failed
        
    def update_state(self, positions, successful, failed):
        """Update state after selling positions"""
        try:
            # Log the sale action
            sale_log = {
                'timestamp': datetime.now().isoformat(),
                'user': self.selected_user,
                'action': 'bulk_cnc_sale',
                'total_positions': len(positions),
                'successful': successful,
                'failed': failed,
                'positions': [pos['symbol'] for pos in positions]
            }
            
            # Save to state
            state = self.state_manager.load_state()
            if 'cnc_sale_history' not in state:
                state['cnc_sale_history'] = []
            state['cnc_sale_history'].append(sale_log)
            self.state_manager.save_state(state)
            
            print(f"\n{Fore.GREEN}State updated successfully.")
            
        except Exception as e:
            print(f"\n{Fore.YELLOW}Warning: Could not update state: {e}")
            
    def run(self):
        """Main execution flow"""
        print(f"{Fore.CYAN}{'='*60}")
        print(f"{Fore.YELLOW}CNC Position Seller")
        print(f"{Fore.CYAN}{'='*60}")
        
        # Step 1: Select user
        if not self.select_user():
            return
            
        # Step 2: Initialize broker
        print(f"\n{Fore.CYAN}Initializing broker connection...")
        if not self.initialize_broker():
            return
            
        # Step 3: Get positions
        print(f"{Fore.CYAN}Fetching CNC positions...")
        positions = self.get_cnc_positions()
        
        if not positions:
            print(f"\n{Fore.YELLOW}No CNC positions to sell.")
            return
            
        # Step 4: Display positions
        self.display_positions(positions)
        
        # Step 5: Get confirmation
        if not self.confirm_sale(positions):
            return
            
        # Step 6: Execute sales
        successful, failed = self.execute_sales(positions)
        
        # Final message
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Fore.GREEN}Process completed!")
        print(f"{Fore.CYAN}{'='*60}")
        

def main():
    """Main entry point"""
    try:
        seller = CNCSeller()
        seller.run()
        
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Operation cancelled by user.")
    except Exception as e:
        print(f"\n{Fore.RED}Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        

if __name__ == "__main__":
    main()