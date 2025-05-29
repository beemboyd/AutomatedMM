#!/usr/bin/env python
"""
Zerodha Server-Local CNC Orders Synchronization Script
======================================================
This script synchronizes CNC positions between Zerodha server and local Current_Orders files.
It ensures that all existing CNC positions (both from today's orders and historical holdings)
are tracked locally so the watchdog can monitor them with stop loss logic.

Key Features:
- Syncs server-side CNC positions with local orders files
- Tracks both new orders and existing portfolio holdings
- Handles server-side changes (sells, partial sells, new buys)
- Multi-user support with auto-detection
- Creates/updates orders files to match server state
- Maintains order history while adding missing positions

Designed for:
- Scheduled runs to keep local files in sync with server
- Ensuring watchdog monitors ALL CNC positions
- Tracking portfolio changes made outside the system
- Maintaining consistent state between server and local files

Author: Claude Code Assistant
Created: 2025-05-24
Rewritten: 2025-05-26
"""

# Standard library imports
import os
import sys
import json
import logging
import datetime
import glob
import configparser
import argparse
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import user-aware components (if available, but don't rely on them)
try:
    from user_context_manager import get_context_manager, get_user_order_manager, get_user_data_handler
    USER_CONTEXT_AVAILABLE = True
except ImportError:
    USER_CONTEXT_AVAILABLE = False

@dataclass
class UserCredentials:
    """User API credentials container"""
    name: str
    api_key: str
    api_secret: str
    access_token: str

def load_daily_config(user_name="Sai"):
    """Load configuration from Daily/config.ini file with user-specific credentials"""
    daily_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(daily_dir, 'config.ini')

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini not found at {config_path}")

    config = configparser.ConfigParser()
    config.read(config_path)

    # Get user-specific API credentials
    credential_section = f'API_CREDENTIALS_{user_name}'
    if credential_section not in config.sections():
        raise ValueError(f"No credentials found for user {user_name} in {config_path}")

    return config, credential_section

# Set up logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, 'synch_zerodha_local.log'))
    ]
)
logger = logging.getLogger(__name__)


class ZerodhaServerLocalSynchronizer:
    """Synchronizes CNC positions between Zerodha server and local Current_Orders files"""
    
    def __init__(self, default_user="Sai"):
        """Initialize the synchronizer"""
        try:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
            self.daily_dir = os.path.dirname(self.script_dir)
            self.current_orders_dir = os.path.join(self.daily_dir, "Current_Orders")
            self.default_user = default_user

            # Initialize user context manager if available
            self.context_manager = None
            if USER_CONTEXT_AVAILABLE:
                try:
                    self.context_manager = get_context_manager()
                    logger.info("User context manager initialized successfully")
                except Exception as e:
                    logger.warning(f"Could not initialize user context manager: {e}")

            logger.info("Initialized Zerodha Server-Local Synchronizer")
            logger.info(f"Current Orders Directory: {self.current_orders_dir}")
            logger.info(f"Default user: {default_user}")

        except Exception as e:
            logger.error(f"Failed to initialize synchronizer: {e}")
            raise
    
    def find_users_with_credentials(self) -> List[str]:
        """Find users with orders directories (assumes shared credentials)"""
        users = []
        if not os.path.exists(self.current_orders_dir):
            logger.warning(f"Current_Orders directory not found: {self.current_orders_dir}")
            return users
        
        try:
            # Find all user directories
            for item in os.listdir(self.current_orders_dir):
                user_dir = os.path.join(self.current_orders_dir, item)
                if (os.path.isdir(user_dir) and 
                    item.replace('_', '').replace('-', '').isalnum() and
                    len(item) < 20):  # Reasonable user name length
                    users.append(item)
            
            # If no users found, try to detect from existing files
            if not users:
                orders_files = glob.glob(os.path.join(self.current_orders_dir, "*", "orders_*.json"))
                for orders_file in orders_files:
                    user_name = os.path.basename(os.path.dirname(orders_file))
                    if user_name not in users:
                        users.append(user_name)
            
            logger.info(f"Found {len(users)} users: {users}")
            return sorted(users)
            
        except Exception as e:
            logger.error(f"Error finding users: {e}")
            return []
    
    def get_user_credentials(self, user_name: str) -> Optional[UserCredentials]:
        """Get user credentials from Daily/config.ini"""
        try:
            # First check environment variables (for backward compatibility)
            api_key = os.getenv('ZERODHA_API_KEY')
            api_secret = os.getenv('ZERODHA_API_SECRET')
            access_token = os.getenv('ZERODHA_ACCESS_TOKEN')

            if api_key and api_secret and access_token:
                logger.info(f"Using API credentials from environment variables for {user_name}")
                return UserCredentials(
                    name=user_name,
                    api_key=api_key,
                    api_secret=api_secret,
                    access_token=access_token
                )

            # If not available in environment, use config.ini
            try:
                config, credential_section = load_daily_config(user_name)
                api_key = config.get(credential_section, 'api_key')
                api_secret = config.get(credential_section, 'api_secret')
                access_token = config.get(credential_section, 'access_token')

                logger.info(f"Using API credentials from config.ini for user {user_name}")
                return UserCredentials(
                    name=user_name,
                    api_key=api_key,
                    api_secret=api_secret,
                    access_token=access_token
                )
            except (FileNotFoundError, ValueError) as e:
                logger.warning(f"Could not load credentials from config.ini: {e}")

            logger.error(f"No valid credentials found for user {user_name}")
            return None

        except Exception as e:
            logger.error(f"Error getting credentials for {user_name}: {e}")
            return None
    
    def get_server_cnc_positions(self, user_name: str) -> List[Dict[str, Any]]:
        """Get all CNC positions from Zerodha server"""
        try:
            # Get user credentials from config.ini
            credentials = self.get_user_credentials(user_name)
            if not credentials:
                logger.error(f"Could not get credentials for {user_name}")
                return []

            # Use credentials object already obtained from get_user_credentials

            # If user context manager is available, set current user
            if self.context_manager:
                self.context_manager.set_current_user(user_name, credentials)
                logger.info(f"Set current user in context manager to {user_name}")

            # Import KiteConnect if not already imported
            from kiteconnect import KiteConnect

            # Try to get user-specific data handler or create our own KiteConnect instance
            kite = None

            if USER_CONTEXT_AVAILABLE:
                # Try to get data handler from user context manager
                try:
                    data_handler = get_user_data_handler()
                    if data_handler and hasattr(data_handler, 'kite'):
                        kite = data_handler.kite
                        logger.info(f"Using data handler from user context manager for {user_name}")
                except Exception as e:
                    logger.warning(f"Could not get data handler from user context: {e}")

            # If no kite instance yet, create our own
            if not kite:
                logger.info(f"Creating KiteConnect instance for {user_name}")
                kite = KiteConnect(api_key=credentials.api_key)
                kite.set_access_token(credentials.access_token)

            # Log API key being used to verify
            logger.info(f"Using API Key: {kite.api_key[:6]}... for {user_name}")

            # Get positions and holdings
            positions_data = kite.positions()
            holdings_data = kite.holdings()
            
            cnc_positions = []
            
            # Process net positions (CNC from today's trading)
            for pos in positions_data.get('net', []):
                if (pos.get('quantity', 0) != 0 and 
                    pos.get('product') == 'CNC'):
                    
                    position = {
                        'tradingsymbol': pos.get('tradingsymbol', ''),
                        'exchange': pos.get('exchange', 'NSE'),
                        'quantity': pos.get('quantity', 0),
                        'average_price': pos.get('average_price', 0),
                        'last_price': pos.get('last_price', 0),
                        'pnl': pos.get('pnl', 0),
                        'unrealised': pos.get('unrealised', 0),
                        'instrument_token': pos.get('instrument_token', 0),
                        'source': 'server_cnc_positions',
                        'position_type': 'net_cnc'
                    }
                    cnc_positions.append(position)
            
            # Process holdings (long-term CNC)
            for holding in holdings_data:
                total_qty = holding.get('quantity', 0) + holding.get('t1_quantity', 0)
                if total_qty > 0:
                    position = {
                        'tradingsymbol': holding.get('tradingsymbol', ''),
                        'exchange': holding.get('exchange', 'NSE'),
                        'quantity': total_qty,
                        'average_price': holding.get('average_price', 0),
                        'last_price': holding.get('last_price', 0),
                        'pnl': holding.get('pnl', 0),
                        'unrealised': holding.get('pnl', 0),
                        'instrument_token': holding.get('instrument_token', 0),
                        'source': 'server_holdings',
                        'position_type': 'holdings',
                        't1_quantity': holding.get('t1_quantity', 0),
                        'realised_quantity': holding.get('quantity', 0)
                    }
                    cnc_positions.append(position)
            
            logger.info(f"Retrieved {len(cnc_positions)} CNC positions from server for {user_name}")
            return cnc_positions
            
        except Exception as e:
            logger.error(f"Error getting server CNC positions for {user_name}: {e}")
            return []
    
    def get_latest_orders_file(self, user_name: str) -> Optional[str]:
        """Get the most recent orders file for a user"""
        try:
            user_dir = os.path.join(self.current_orders_dir, user_name)
            if not os.path.exists(user_dir):
                os.makedirs(user_dir, exist_ok=True)
                return None
            
            orders_pattern = os.path.join(user_dir, "orders_*.json")
            orders_files = glob.glob(orders_pattern)
            
            if not orders_files:
                return None
            
            # Return the most recent file
            latest_file = max(orders_files, key=os.path.getmtime)
            return latest_file
            
        except Exception as e:
            logger.error(f"Error getting latest orders file for {user_name}: {e}")
            return None
    
    def load_local_orders_file(self, orders_file: str) -> Dict[str, Any]:
        """Load existing local orders file"""
        try:
            if not os.path.exists(orders_file):
                return {'orders': [], 'metadata': {}}
            
            with open(orders_file, 'r') as f:
                data = json.load(f)
            
            return data
            
        except Exception as e:
            logger.error(f"Error loading orders file {orders_file}: {e}")
            return {'orders': [], 'metadata': {}}
    
    def create_order_from_position(self, position: Dict[str, Any], order_id_base: str = None) -> Dict[str, Any]:
        """Create an order entry from a server position"""
        
        # Determine transaction type based on quantity
        if position['quantity'] > 0:
            transaction_type = "BUY"
            quantity = abs(position['quantity'])
        else:
            transaction_type = "SELL"
            quantity = abs(position['quantity'])
        
        # Generate order ID
        if not order_id_base:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            order_id_base = f"SYNC_{position['tradingsymbol']}_{timestamp}"
        
        order = {
            "order_id": order_id_base,
            "tradingsymbol": position['tradingsymbol'],
            "exchange": position.get('exchange', 'NSE'),
            "instrument_token": position.get('instrument_token', 0),
            "transaction_type": transaction_type,
            "product": "CNC",
            "order_type": "MARKET",
            "quantity": quantity,
            "filled_quantity": quantity,
            "price": position['average_price'],
            "average_price": position['average_price'],
            "status": "COMPLETE",
            "order_timestamp": datetime.datetime.now().isoformat(),
            "status_message": f"Synced from server {position['source']}",
            "data_source": "server_sync",
            "sync_timestamp": datetime.datetime.now().isoformat(),
            "position_type": position.get('position_type', 'unknown'),
            "notes": f"Auto-synced from Zerodha server - {position['source']}"
        }
        
        # Add additional fields for holdings
        if position.get('t1_quantity'):
            order['t1_quantity'] = position['t1_quantity']
            order['realised_quantity'] = position.get('realised_quantity', 0)
        
        return order
    
    def sync_user_positions(self, user_name: str) -> Dict[str, Any]:
        """Synchronize server CNC positions with local orders file for a user"""
        logger.info(f"Synchronizing server CNC positions to local file for user: {user_name}")
        
        sync_result = {
            'user': user_name,
            'success': False,
            'orders_file': None,
            'server_positions_count': 0,
            'local_orders_count': 0,
            'positions_added': 0,
            'positions_updated': 0,
            'positions_removed': 0,
            'sync_time': datetime.datetime.now().isoformat(),
            'changes': [],
            'recommendations': []
        }
        
        try:
            # Get server CNC positions
            server_positions = self.get_server_cnc_positions(user_name)
            sync_result['server_positions_count'] = len(server_positions)
            
            if not server_positions:
                sync_result['recommendations'].append(f"No CNC positions found on server for {user_name}")
                sync_result['success'] = True
                return sync_result
            
            # Get or create orders file
            orders_file = self.get_latest_orders_file(user_name)
            if not orders_file:
                # Create new orders file
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                user_dir = os.path.join(self.current_orders_dir, user_name)
                os.makedirs(user_dir, exist_ok=True)
                orders_file = os.path.join(user_dir, f"orders_{user_name}_{timestamp}.json")
                
                # Initialize with empty structure
                orders_data = {
                    'metadata': {
                        'user': user_name,
                        'created': datetime.datetime.now().isoformat(),
                        'source': 'server_sync_new'
                    },
                    'orders': []
                }
            else:
                # Load existing orders file
                orders_data = self.load_local_orders_file(orders_file)
            
            sync_result['orders_file'] = os.path.basename(orders_file)
            sync_result['local_orders_count'] = len(orders_data.get('orders', []))
            
            # Create lookup of existing CNC orders in local file
            existing_cnc_orders = {}
            other_orders = []
            
            for order in orders_data.get('orders', []):
                if (order.get('product') == 'CNC' and 
                    order.get('status') == 'COMPLETE'):
                    symbol = order.get('tradingsymbol', '')
                    if symbol:
                        if symbol not in existing_cnc_orders:
                            existing_cnc_orders[symbol] = []
                        existing_cnc_orders[symbol].append(order)
                else:
                    # Keep non-CNC orders as-is
                    other_orders.append(order)
            
            # Process server positions
            updated_cnc_orders = []
            
            for position in server_positions:
                symbol = position['tradingsymbol']
                server_qty = position['quantity']
                
                if symbol in existing_cnc_orders:
                    # Check if local orders match server position
                    local_orders = existing_cnc_orders[symbol]
                    
                    # Calculate net quantity from local orders
                    local_net_qty = 0
                    for order in local_orders:
                        if order.get('transaction_type') == 'BUY':
                            local_net_qty += order.get('filled_quantity', 0)
                        else:
                            local_net_qty -= order.get('filled_quantity', 0)
                    
                    if local_net_qty == server_qty:
                        # Quantities match, keep existing orders
                        updated_cnc_orders.extend(local_orders)
                        sync_result['changes'].append(f"✓ {symbol}: Quantities match (Local: {local_net_qty}, Server: {server_qty})")
                    else:
                        # Quantities don't match, create new order for server position
                        new_order = self.create_order_from_position(position)
                        updated_cnc_orders.append(new_order)
                        sync_result['positions_updated'] += 1
                        sync_result['changes'].append(f"🔄 {symbol}: Updated (Local: {local_net_qty} → Server: {server_qty})")
                else:
                    # New position from server, add it
                    new_order = self.create_order_from_position(position)
                    updated_cnc_orders.append(new_order)
                    sync_result['positions_added'] += 1
                    sync_result['changes'].append(f"➕ {symbol}: Added new position (Qty: {server_qty})")
            
            # Check for positions that exist locally but not on server
            server_symbols = {pos['tradingsymbol'] for pos in server_positions}
            for symbol in existing_cnc_orders:
                if symbol not in server_symbols:
                    sync_result['positions_removed'] += 1
                    sync_result['changes'].append(f"➖ {symbol}: Removed (not on server)")
            
            # Combine all orders (non-CNC + updated CNC)
            all_orders = other_orders + updated_cnc_orders
            
            # Update metadata
            orders_data['orders'] = all_orders
            if 'metadata' not in orders_data:
                orders_data['metadata'] = {}

            orders_data['metadata'].update({
                'last_server_sync': datetime.datetime.now().isoformat(),
                'server_sync_count': len(server_positions),
                'positions_added': sync_result['positions_added'],
                'positions_updated': sync_result['positions_updated'],
                'positions_removed': sync_result['positions_removed']
            })
            
            # Save updated orders file
            with open(orders_file, 'w') as f:
                json.dump(orders_data, f, indent=2, default=str)
            
            # Generate recommendations
            if sync_result['positions_added'] + sync_result['positions_updated'] + sync_result['positions_removed'] == 0:
                sync_result['recommendations'].append("✅ Local orders file is perfectly synchronized with server")
            else:
                sync_result['recommendations'].append(f"🔄 Synchronized {sync_result['positions_added']} new, {sync_result['positions_updated']} updated, {sync_result['positions_removed']} removed positions")
                sync_result['recommendations'].append("🎯 Restart watchdog to monitor updated positions")
            
            sync_result['success'] = True
            logger.info(f"Sync completed for {user_name}: {sync_result['positions_added']} added, {sync_result['positions_updated']} updated, {sync_result['positions_removed']} removed")
            
        except Exception as e:
            logger.error(f"Error syncing positions for {user_name}: {e}")
            sync_result['recommendations'].append(f"❌ Sync failed: {str(e)}")
        
        return sync_result
    
    def sync_all_users(self) -> Dict[str, Any]:
        """Synchronize server CNC positions with local files for all users"""
        logger.info("Starting server-local synchronization for all users")
        
        overall_result = {
            'sync_time': datetime.datetime.now().isoformat(),
            'users_found': 0,
            'users_synced': 0,
            'total_positions_added': 0,
            'total_positions_updated': 0,
            'total_positions_removed': 0,
            'user_results': [],
            'summary': []
        }
        
        try:
            # Find users
            users = self.find_users_with_credentials()
            overall_result['users_found'] = len(users)
            
            if not users:
                overall_result['summary'].append("No users found - please ensure Current_Orders directory structure exists")
                return overall_result
            
            # Sync each user
            for user_name in users:
                user_result = self.sync_user_positions(user_name)
                overall_result['user_results'].append(user_result)
                
                if user_result['success']:
                    overall_result['users_synced'] += 1
                    overall_result['total_positions_added'] += user_result['positions_added']
                    overall_result['total_positions_updated'] += user_result['positions_updated']
                    overall_result['total_positions_removed'] += user_result['positions_removed']
            
            # Generate overall summary
            overall_result['summary'].append(f"Synchronized {overall_result['users_synced']}/{overall_result['users_found']} users successfully")
            overall_result['summary'].append(f"Changes: {overall_result['total_positions_added']} added, {overall_result['total_positions_updated']} updated, {overall_result['total_positions_removed']} removed")
            
            if (overall_result['total_positions_added'] + 
                overall_result['total_positions_updated'] + 
                overall_result['total_positions_removed'] == 0):
                overall_result['summary'].append("✅ All local files are synchronized with server")
            else:
                overall_result['summary'].append("🎯 Restart watchdogs to monitor updated positions")
            
            logger.info(f"Overall sync completed: {overall_result['users_synced']}/{overall_result['users_found']} users")
            
        except Exception as e:
            logger.error(f"Error in overall sync: {e}")
            overall_result['summary'].append(f"❌ Overall sync failed: {str(e)}")
        
        return overall_result
    
    def print_sync_report(self, sync_result: Dict[str, Any]):
        """Print detailed synchronization report"""
        print("\n" + "="*100)
        print("ZERODHA SERVER ↔ LOCAL CNC POSITIONS SYNCHRONIZATION REPORT")
        print("="*100)
        
        if 'user_results' in sync_result:
            # Multi-user report
            print(f"Sync Time: {sync_result['sync_time']}")
            print(f"Users Found: {sync_result['users_found']}")
            print(f"Users Synced: {sync_result['users_synced']}")
            print(f"Total Changes: +{sync_result['total_positions_added']} ~{sync_result['total_positions_updated']} -{sync_result['total_positions_removed']}")
            print("-"*100)
            
            for user_result in sync_result['user_results']:
                self._print_user_report(user_result)
                print("-"*100)
            
            print("OVERALL SUMMARY:")
            for summary_line in sync_result['summary']:
                print(f"  {summary_line}")
        else:
            # Single user report
            self._print_user_report(sync_result)
        
        print("="*100)
    
    def _print_user_report(self, user_result: Dict[str, Any]):
        """Print report for a single user"""
        user = user_result['user']
        print(f"USER: {user}")
        print(f"  Orders File: {user_result.get('orders_file', 'NEW FILE CREATED')}")
        print(f"  Server Positions: {user_result['server_positions_count']}")
        print(f"  Local Orders: {user_result['local_orders_count']}")
        print(f"  Changes: +{user_result['positions_added']} ~{user_result['positions_updated']} -{user_result['positions_removed']}")
        
        if user_result['changes']:
            print(f"  DETAILED CHANGES:")
            for change in user_result['changes'][:10]:  # Show first 10 changes
                print(f"    {change}")
            if len(user_result['changes']) > 10:
                print(f"    ... and {len(user_result['changes']) - 10} more changes")
        
        print(f"  RECOMMENDATIONS:")
        for rec in user_result['recommendations']:
            print(f"    {rec}")


def main():
    """Main function to synchronize server CNC positions with local files"""

    parser = argparse.ArgumentParser(description='Synchronize Zerodha server CNC positions with local orders files')
    parser.add_argument('--user', '-u', type=str, default='Sai',
                        help='User whose API credentials to use (default: Sai)')
    parser.add_argument('--sync-user', '-s', type=str,
                        help='Sync only a specific user (default: all users)')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress detailed output')
    parser.add_argument('--json-output', '-j', type=str,
                        help='Save results to JSON file')
    parser.add_argument('--detect-users', '-d', action='store_true',
                        help='Auto-detect users based on Current_Orders folder structure')

    args = parser.parse_args()

    try:
        logger.info(f"Starting Zerodha server-local synchronization using credentials for {args.user}")

        # Initialize synchronizer with the user credentials to use
        synchronizer = ZerodhaServerLocalSynchronizer(default_user=args.user)

        # Sync positions
        if args.sync_user:
            # Sync specific user
            logger.info(f"Syncing only user: {args.sync_user}")
            result = synchronizer.sync_user_positions(args.sync_user)
        elif args.detect_users:
            # Auto-detect users and sync all
            logger.info("Auto-detecting users from Current_Orders directory structure")
            result = synchronizer.sync_all_users()
        else:
            # Sync default user
            logger.info(f"Syncing default user: {args.user}")
            result = synchronizer.sync_user_positions(args.user)
        
        # Save JSON output if requested
        if args.json_output:
            with open(args.json_output, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            print(f"Results saved to: {args.json_output}")
        
        # Print report unless quiet mode
        if not args.quiet:
            synchronizer.print_sync_report(result)
        
        # Return appropriate exit code
        if 'user_results' in result:
            # Multi-user result
            return 0 if result['users_synced'] == result['users_found'] else 1
        else:
            # Single user result
            return 0 if result['success'] else 1
        
    except KeyboardInterrupt:
        logger.info("Synchronization interrupted by user")
        print("\nSynchronization interrupted by user.")
        return 0
    except Exception as e:
        logger.exception(f"Error in synchronization: {e}")
        print(f"Synchronization failed: {str(e)}")
        return 1


if __name__ == "__main__":
    # Print banner
    print("\n" + "="*100)
    print("ZERODHA SERVER ↔ LOCAL CNC POSITIONS SYNCHRONIZATION SCRIPT")
    print("="*100)
    print("This script synchronizes CNC positions between Zerodha server and local Current_Orders files")
    print("")
    print("Purpose:")
    print("• Sync server-side CNC positions (holdings + net positions) with local orders files")
    print("• Ensure watchdog monitors ALL CNC positions including existing portfolio")
    print("• Track server-side changes (sells, partial sells, new purchases)")
    print("• Maintain consistent state between server and local tracking")
    print("• Support scheduled runs to keep files synchronized")
    print("")
    print("Command-line Options:")
    print("• --user, -u NAME       : User whose API credentials to use (default: Sai)")
    print("• --sync-user, -s NAME  : Sync only a specific user instead of all users")
    print("• --detect-users, -d    : Auto-detect users based on Current_Orders directory")
    print("• --quiet, -q           : Suppress detailed output")
    print("• --json-output, -j FILE: Save results to JSON file")
    print("")
    print("Examples:")
    print("• Basic usage              : python synch_zerodha_local.py")
    print("• Use specific credentials : python synch_zerodha_local.py -u Som")
    print("• Sync only one user       : python synch_zerodha_local.py -u Som -s Som")
    print("• Auto-detect all users    : python synch_zerodha_local.py -u Som -d")
    print("="*100)

    exit_code = main()
    sys.exit(exit_code)