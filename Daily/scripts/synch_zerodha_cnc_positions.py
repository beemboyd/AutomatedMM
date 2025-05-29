#!/usr/bin/env python
"""
Enhanced Zerodha CNC Positions Synchronization Script
=====================================================
This script synchronizes local orders files with server-side CNC positions from Zerodha broker.

Features:
- Auto-detects users with orders files in Current_Orders
- Syncs local orders files with current broker positions
- Updates existing orders files with server-side position data
- Handles discrepancies between local files and broker positions
- Provides detailed sync reports and recommendations
- Multi-user support with user-aware singleton management

IMPORTANT: This script copies SERVER positions TO LOCAL files.
It does NOT place any buy/sell orders on the server.

Designed for:
- Watchdog position synchronization
- Orders file validation and updates with server data
- CNC position drift detection and correction
- Multi-user trading system maintenance

Author: Claude Code Assistant
Enhanced: 2025-05-27
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

# Import user-aware components if available
try:
    from user_context_manager import get_context_manager, get_user_order_manager, get_user_data_handler
    from user_aware_state_manager import UserAwareStateManager
    USER_CONTEXT_AVAILABLE = True
except ImportError:
    USER_CONTEXT_AVAILABLE = False

# Load configuration from Daily/config.ini
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
        logging.FileHandler(os.path.join(log_dir, 'synch_zerodha_cnc_positions.log'))
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class PositionDiscrepancy:
    """Represents a discrepancy between local orders file and broker positions"""
    symbol: str
    local_qty: int
    broker_qty: int
    local_avg_price: float
    broker_avg_price: float
    discrepancy_type: str  # 'missing_broker', 'missing_local', 'quantity_mismatch', 'price_mismatch'
    recommendation: str


@dataclass
class UserCredentials:
    """User credentials for API access"""
    name: str
    api_key: str
    api_secret: str
    access_token: str


class ZerodhaCNCPositionsSynchronizer:
    """Enhanced synchronizer for CNC positions with multi-user support"""

    def __init__(self, dry_run=False, default_user="Sai"):
        """Initialize the synchronizer"""
        try:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
            self.daily_dir = os.path.dirname(self.script_dir)
            self.current_orders_dir = os.path.join(self.daily_dir, "Current_Orders")
            self.dry_run = dry_run
            self.default_user = default_user

            # Initialize user context manager if available
            self.context_manager = None
            if USER_CONTEXT_AVAILABLE:
                try:
                    self.context_manager = get_context_manager()
                    logger.info("User context manager initialized successfully")
                except Exception as e:
                    logger.warning(f"Could not initialize user context manager: {e}")

            logger.info("Initialized CNC Positions Synchronizer")
            logger.info(f"Current Orders Directory: {self.current_orders_dir}")
            logger.info(f"Dry Run Mode: {self.dry_run}")
            logger.info(f"Default User: {self.default_user}")

        except Exception as e:
            logger.error(f"Failed to initialize synchronizer: {e}")
            raise
    
    def find_users_with_orders(self) -> List[str]:
        """Find all users with orders files in Current_Orders directory"""
        users = []
        if not os.path.exists(self.current_orders_dir):
            logger.warning(f"Current_Orders directory not found: {self.current_orders_dir}")
            return users
        
        try:
            # Find all directories that contain recent orders files (last 7 days)
            for item in os.listdir(self.current_orders_dir):
                user_dir = os.path.join(self.current_orders_dir, item)
                if os.path.isdir(user_dir) and item.replace('_', '').replace('-', '').isalnum():
                    # Find recent orders files
                    orders_pattern = os.path.join(user_dir, "orders_*.json")
                    orders_files = glob.glob(orders_pattern)
                    
                    # Check if any files are recent (within 7 days)
                    for orders_file in orders_files:
                        file_age = datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(orders_file))
                        if file_age.days <= 7:
                            users.append(item)
                            break
            
            logger.info(f"Found {len(users)} users with recent orders: {users}")
            return sorted(users)
            
        except Exception as e:
            logger.error(f"Error finding users with orders: {e}")
            return []
    
    def get_user_credentials(self, user_name: str) -> Optional[UserCredentials]:
        """Get user credentials for API access"""
        try:
            # Use the load_daily_config function to get credentials
            try:
                config, section = load_daily_config(user_name)

                # Extract credentials
                api_key = config.get(section, 'api_key')
                api_secret = config.get(section, 'api_secret')
                access_token = config.get(section, 'access_token')

                logger.info(f"Successfully loaded credentials for user {user_name} from section [{section}]")
                return UserCredentials(user_name, api_key, api_secret, access_token)

            except (FileNotFoundError, ValueError) as e:
                logger.error(f"Could not load credentials for {user_name}: {e}")
                return None

        except Exception as e:
            logger.error(f"Error getting credentials for {user_name}: {e}")
            return None
    
    def get_latest_orders_file(self, user_name: str) -> Optional[str]:
        """Get the most recent orders file for a user"""
        try:
            user_dir = os.path.join(self.current_orders_dir, user_name)
            if not os.path.exists(user_dir):
                return None
            
            orders_pattern = os.path.join(user_dir, "orders_*.json")
            orders_files = glob.glob(orders_pattern)
            
            if not orders_files:
                return None
            
            # Return the most recent file
            latest_file = max(orders_files, key=os.path.getmtime)
            logger.info(f"Latest orders file for {user_name}: {os.path.basename(latest_file)}")
            return latest_file
            
        except Exception as e:
            logger.error(f"Error getting latest orders file for {user_name}: {e}")
            return None
    
    def load_orders_file_positions(self, orders_file: str) -> List[Dict[str, Any]]:
        """Load CNC positions from orders file"""
        try:
            with open(orders_file, 'r') as f:
                orders_data = json.load(f)
            
            positions = []
            orders = orders_data.get('orders', [])
            
            for order in orders:
                if (order.get('status') == 'COMPLETE' and 
                    order.get('product') == 'CNC' and 
                    order.get('transaction_type') == 'BUY'):
                    
                    position = {
                        'tradingsymbol': order.get('tradingsymbol', ''),
                        'exchange': order.get('exchange', 'NSE'),
                        'quantity': order.get('filled_quantity', order.get('quantity', 0)),
                        'average_price': order.get('average_price', 0),
                        'order_id': order.get('order_id', ''),
                        'order_timestamp': order.get('order_timestamp', ''),
                        'source': 'orders_file'
                    }
                    positions.append(position)
            
            logger.info(f"Loaded {len(positions)} CNC positions from orders file")
            return positions
            
        except Exception as e:
            logger.error(f"Error loading positions from orders file: {e}")
            return []
    
    def get_broker_cnc_positions(self, user_name: str) -> List[Dict[str, Any]]:
        """Get CNC positions from broker for a specific user"""
        try:
            # Get user credentials from config.ini
            credentials = self.get_user_credentials(user_name)
            if not credentials:
                logger.error(f"Could not get credentials for {user_name}")
                return []

            logger.info(f"Using credentials for {user_name}: API Key = {credentials.api_key[:8]}...")

            # Import KiteConnect if not already imported
            from kiteconnect import KiteConnect

            # Try to use user context manager if available
            kite = None
            if USER_CONTEXT_AVAILABLE and self.context_manager:
                try:
                    # Set user in context manager
                    self.context_manager.set_current_user(credentials.name, credentials)
                    logger.info(f"Set user context to {credentials.name}")

                    # Try to get data handler
                    data_handler = get_user_data_handler()
                    if data_handler and hasattr(data_handler, 'kite'):
                        kite = data_handler.kite
                        logger.info(f"Using data handler kite instance for {user_name}")
                except Exception as e:
                    logger.warning(f"Could not use user context manager: {e}")

            # If we don't have a kite instance yet, create our own
            if not kite:
                logger.info(f"Creating direct KiteConnect instance for {user_name}")
                kite = KiteConnect(api_key=credentials.api_key)
                kite.set_access_token(credentials.access_token)

            # Log API key being used
            logger.info(f"KiteConnect using API Key: {kite.api_key[:8]}...")

            # Get positions
            positions_data = kite.positions()
            holdings_data = kite.holdings()
            
            cnc_positions = []
            
            # Process net positions (CNC)
            for pos in positions_data.get('net', []):
                if (pos.get('quantity', 0) != 0 and 
                    pos.get('product') == 'CNC'):
                    
                    position = {
                        'tradingsymbol': pos.get('tradingsymbol', ''),
                        'exchange': pos.get('exchange', ''),
                        'quantity': pos.get('quantity', 0),
                        'average_price': pos.get('average_price', 0),
                        'last_price': pos.get('last_price', 0),
                        'pnl': pos.get('pnl', 0),
                        'unrealised': pos.get('unrealised', 0),
                        'instrument_token': pos.get('instrument_token', 0),
                        'source': 'broker_positions'
                    }
                    cnc_positions.append(position)
            
            # Process holdings (also CNC)
            for holding in holdings_data:
                total_qty = holding.get('quantity', 0) + holding.get('t1_quantity', 0)
                if total_qty > 0:
                    position = {
                        'tradingsymbol': holding.get('tradingsymbol', ''),
                        'exchange': holding.get('exchange', ''),
                        'quantity': total_qty,
                        'average_price': holding.get('average_price', 0),
                        'last_price': holding.get('last_price', 0),
                        'pnl': holding.get('pnl', 0),
                        'unrealised': holding.get('pnl', 0),
                        'instrument_token': holding.get('instrument_token', 0),
                        'source': 'broker_holdings',
                        't1_quantity': holding.get('t1_quantity', 0)
                    }
                    cnc_positions.append(position)
            
            logger.info(f"Retrieved {len(cnc_positions)} CNC positions from broker for {user_name}")
            return cnc_positions
            
        except Exception as e:
            logger.error(f"Error getting broker CNC positions for {user_name}: {e}")
            return []
    
    def compare_positions(self, local_positions: List[Dict], broker_positions: List[Dict]) -> List[PositionDiscrepancy]:
        """Compare local orders file positions with broker positions"""
        discrepancies = []
        
        # Create lookup dictionaries
        local_dict = {pos['tradingsymbol']: pos for pos in local_positions}
        broker_dict = {pos['tradingsymbol']: pos for pos in broker_positions}
        
        all_symbols = set(local_dict.keys()) | set(broker_dict.keys())
        
        for symbol in all_symbols:
            local_pos = local_dict.get(symbol)
            broker_pos = broker_dict.get(symbol)
            
            if local_pos and not broker_pos:
                # Position in local file but not in broker
                discrepancy = PositionDiscrepancy(
                    symbol=symbol,
                    local_qty=local_pos['quantity'],
                    broker_qty=0,
                    local_avg_price=local_pos['average_price'],
                    broker_avg_price=0,
                    discrepancy_type='missing_broker',
                    recommendation='Position in local file but not in broker. Local file may be outdated.'
                )
                discrepancies.append(discrepancy)
                
            elif broker_pos and not local_pos:
                # Position in broker but not in local file
                discrepancy = PositionDiscrepancy(
                    symbol=symbol,
                    local_qty=0,
                    broker_qty=broker_pos['quantity'],
                    local_avg_price=0,
                    broker_avg_price=broker_pos['average_price'],
                    discrepancy_type='missing_local',
                    recommendation='Position exists in broker but not in local file. Will be added to local file.'
                )
                discrepancies.append(discrepancy)
                
            elif local_pos and broker_pos:
                # Both exist, check for differences
                if local_pos['quantity'] != broker_pos['quantity']:
                    discrepancy = PositionDiscrepancy(
                        symbol=symbol,
                        local_qty=local_pos['quantity'],
                        broker_qty=broker_pos['quantity'],
                        local_avg_price=local_pos['average_price'],
                        broker_avg_price=broker_pos['average_price'],
                        discrepancy_type='quantity_mismatch',
                        recommendation='Quantity mismatch. Local file will be updated with broker data.'
                    )
                    discrepancies.append(discrepancy)
                    
                elif abs(local_pos['average_price'] - broker_pos['average_price']) > 0.01:
                    discrepancy = PositionDiscrepancy(
                        symbol=symbol,
                        local_qty=local_pos['quantity'],
                        broker_qty=broker_pos['quantity'],
                        local_avg_price=local_pos['average_price'],
                        broker_avg_price=broker_pos['average_price'],
                        discrepancy_type='price_mismatch',
                        recommendation='Average price mismatch. Local file will be updated with broker data.'
                    )
                    discrepancies.append(discrepancy)
        
        return discrepancies
    
    def update_local_orders_file(self, user_name: str, orders_file: str, broker_positions: List[Dict]) -> Dict[str, Any]:
        """Update local orders file with server-side broker positions"""
        try:
            # Load existing orders file
            with open(orders_file, 'r') as f:
                orders_data = json.load(f)
            
            # Get existing orders
            existing_orders = orders_data.get('orders', [])
            
            # Track changes
            added_positions = []
            updated_positions = []
            removed_positions = []
            
            # Create lookup for existing orders by symbol
            existing_symbols = {}
            for i, order in enumerate(existing_orders):
                symbol = order.get('tradingsymbol', '')
                if symbol and order.get('product') == 'CNC' and order.get('transaction_type') == 'BUY':
                    existing_symbols[symbol] = {'order': order, 'index': i}
            
            # Create lookup for broker positions (exclude sold positions)
            broker_symbols = {pos['tradingsymbol']: pos for pos in broker_positions if pos['quantity'] > 0}
            
            # Process broker positions - add new or update existing
            # Skip positions with negative quantities (sold positions)
            for broker_pos in broker_positions:
                symbol = broker_pos['tradingsymbol']
                raw_quantity = broker_pos['quantity']

                # Skip completely sold positions (negative quantities)
                if raw_quantity <= 0:
                    logger.info(f"Skipping sold position: {symbol} (quantity: {raw_quantity})")
                    continue

                quantity = raw_quantity  # Use actual positive quantity
                avg_price = broker_pos['average_price']
                
                if symbol not in existing_symbols:
                    # Add new position from broker to local file
                    new_order = {
                        'tradingsymbol': symbol,
                        'exchange': broker_pos.get('exchange', 'NSE'),
                        'transaction_type': 'BUY',
                        'product': 'CNC',
                        'quantity': quantity,
                        'filled_quantity': quantity,
                        'average_price': avg_price,
                        'status': 'COMPLETE',
                        'order_id': f'SYNCED_{symbol}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}',
                        'order_timestamp': datetime.datetime.now().isoformat(),
                        'tag': 'synced_from_broker',
                        'synced_from_broker': True,
                        'source': broker_pos.get('source', 'broker_positions')
                    }
                    existing_orders.append(new_order)
                    added_positions.append({
                        'symbol': symbol,
                        'quantity': quantity,
                        'average_price': avg_price,
                        'source': broker_pos.get('source', 'broker_positions')
                    })
                    logger.info(f"Added position from broker: {symbol} ({quantity} shares @ ₹{avg_price:.2f})")
                
                else:
                    # Update existing position with broker data if different
                    existing_order = existing_symbols[symbol]['order']
                    old_qty = existing_order.get('quantity', 0)
                    old_price = existing_order.get('average_price', 0)
                    
                    if abs(old_qty - quantity) > 0 or abs(old_price - avg_price) > 0.01:
                        existing_order['quantity'] = quantity
                        existing_order['filled_quantity'] = quantity
                        existing_order['average_price'] = avg_price
                        existing_order['synced_from_broker'] = True
                        existing_order['last_sync_timestamp'] = datetime.datetime.now().isoformat()
                        
                        updated_positions.append({
                            'symbol': symbol,
                            'old_quantity': old_qty,
                            'new_quantity': quantity,
                            'old_price': old_price,
                            'new_price': avg_price
                        })
                        logger.info(f"Updated position from broker: {symbol} (Qty: {old_qty}→{quantity}, Price: ₹{old_price:.2f}→₹{avg_price:.2f})")
            
            # Remove positions that exist in local file but not in broker (including sold positions)
            # Create a set of all broker symbols regardless of quantity for sold position detection
            all_broker_symbols = {pos['tradingsymbol']: pos for pos in broker_positions}

            orders_to_remove = []
            for symbol, info in existing_symbols.items():
                order = info['order']
                # Remove if position not in broker at all, OR if position is sold (negative quantity)
                if symbol not in broker_symbols:
                    if symbol in all_broker_symbols:
                        # Position exists in broker but with negative quantity (sold)
                        broker_qty = all_broker_symbols[symbol]['quantity']
                        logger.info(f"Removed sold position: {symbol} (broker quantity: {broker_qty})")
                    else:
                        # Position doesn't exist in broker at all
                        logger.info(f"Removed position no longer in broker: {symbol}")

                    removed_positions.append({
                        'symbol': symbol,
                        'quantity': order.get('quantity', 0),
                        'average_price': order.get('average_price', 0)
                    })
                    orders_to_remove.append(info['index'])
            
            # Remove orders (in reverse order to maintain indices)
            for index in sorted(orders_to_remove, reverse=True):
                del existing_orders[index]
            
            # Update orders data
            orders_data['orders'] = existing_orders
            orders_data['last_sync_timestamp'] = datetime.datetime.now().isoformat()
            orders_data['sync_source'] = 'broker_positions_sync'
            
            if self.dry_run:
                logger.info(f"DRY RUN: Would update orders file {orders_file} with {len(added_positions)} new, {len(updated_positions)} updated, {len(removed_positions)} removed positions")
                return {
                    'success': True,
                    'added_count': len(added_positions),
                    'updated_count': len(updated_positions),
                    'removed_count': len(removed_positions),
                    'added_positions': added_positions,
                    'updated_positions': updated_positions,
                    'removed_positions': removed_positions,
                    'dry_run': True
                }
            
            # Write updated orders file
            with open(orders_file, 'w') as f:
                json.dump(orders_data, f, indent=2)
            
            logger.info(f"Updated orders file: {len(added_positions)} added, {len(updated_positions)} updated, {len(removed_positions)} removed")
            
            return {
                'success': True,
                'added_count': len(added_positions),
                'updated_count': len(updated_positions),
                'removed_count': len(removed_positions),
                'added_positions': added_positions,
                'updated_positions': updated_positions,
                'removed_positions': removed_positions,
                'dry_run': False
            }
            
        except Exception as e:
            logger.error(f"Error updating orders file {orders_file}: {e}")
            return {
                'success': False,
                'error': str(e),
                'added_count': 0,
                'updated_count': 0,
                'removed_count': 0,
                'added_positions': [],
                'updated_positions': [],
                'removed_positions': []
            }
    
    def sync_user_positions(self, user_name: str) -> Dict[str, Any]:
        """Synchronize CNC positions for a specific user"""
        logger.info(f"Synchronizing CNC positions for user: {user_name}")
        
        sync_result = {
            'user': user_name,
            'success': False,
            'orders_file': None,
            'local_positions_count': 0,
            'broker_positions_count': 0,
            'initial_discrepancies': [],
            'file_update_result': {},
            'sync_time': datetime.datetime.now().isoformat(),
            'recommendations': []
        }
        
        try:
            # Get latest orders file
            orders_file = self.get_latest_orders_file(user_name)
            if not orders_file:
                sync_result['recommendations'].append(f"No orders file found for user {user_name}")
                return sync_result
            
            sync_result['orders_file'] = os.path.basename(orders_file)
            
            # Load local positions
            local_positions = self.load_orders_file_positions(orders_file)
            sync_result['local_positions_count'] = len(local_positions)
            
            # Get broker positions
            broker_positions = self.get_broker_cnc_positions(user_name)
            sync_result['broker_positions_count'] = len(broker_positions)
            
            # Compare positions
            discrepancies = self.compare_positions(local_positions, broker_positions)
            sync_result['initial_discrepancies'] = [
                {
                    'symbol': d.symbol,
                    'local_qty': d.local_qty,
                    'broker_qty': d.broker_qty,
                    'local_avg_price': d.local_avg_price,
                    'broker_avg_price': d.broker_avg_price,
                    'type': d.discrepancy_type,
                    'recommendation': d.recommendation
                }
                for d in discrepancies
            ]
            
            # Update local orders file with broker positions
            if broker_positions:
                file_update_result = self.update_local_orders_file(user_name, orders_file, broker_positions)
                sync_result['file_update_result'] = file_update_result
                
                if file_update_result['success']:
                    added = file_update_result['added_count']
                    updated = file_update_result['updated_count']
                    removed = file_update_result['removed_count']
                    
                    if added > 0 or updated > 0 or removed > 0:
                        mode_msg = "DRY RUN MODE - No actual changes made" if self.dry_run else "LIVE MODE - Local file updated"
                        sync_result['recommendations'].append(f"✅ Local file synchronized with broker ({mode_msg})")
                        
                        if added > 0:
                            sync_result['recommendations'].append(f"  📈 Added {added} new positions from broker")
                            for pos in file_update_result['added_positions']:
                                sync_result['recommendations'].append(f"    + {pos['symbol']}: {pos['quantity']} shares @ ₹{pos['average_price']:.2f}")
                        
                        if updated > 0:
                            sync_result['recommendations'].append(f"  🔄 Updated {updated} existing positions")
                            for pos in file_update_result['updated_positions']:
                                sync_result['recommendations'].append(f"    ~ {pos['symbol']}: {pos['old_quantity']}→{pos['new_quantity']} shares, ₹{pos['old_price']:.2f}→₹{pos['new_price']:.2f}")
                        
                        if removed > 0:
                            sync_result['recommendations'].append(f"  📉 Removed {removed} positions no longer in broker")
                            for pos in file_update_result['removed_positions']:
                                sync_result['recommendations'].append(f"    - {pos['symbol']}: {pos['quantity']} shares @ ₹{pos['average_price']:.2f}")
                    else:
                        sync_result['recommendations'].append("✅ Local file already synchronized with broker positions")
                else:
                    sync_result['recommendations'].append(f"❌ Failed to update local file: {file_update_result.get('error', 'Unknown error')}")
            else:
                sync_result['recommendations'].append("ℹ️ No broker positions found to sync")
            
            sync_result['success'] = True
            logger.info(f"Sync completed for {user_name}: {len(discrepancies)} initial discrepancies found")
            
        except Exception as e:
            logger.error(f"Error syncing positions for {user_name}: {e}")
            sync_result['recommendations'].append(f"❌ Sync failed: {str(e)}")
        
        return sync_result
    
    def sync_all_users(self) -> Dict[str, Any]:
        """Synchronize CNC positions for all users with valid access tokens"""
        logger.info("Starting CNC positions synchronization for all users with valid access tokens")

        overall_result = {
            'sync_time': datetime.datetime.now().isoformat(),
            'users_found': 0,
            'users_synced': 0,
            'total_initial_discrepancies': 0,
            'total_changes_made': 0,
            'user_results': [],
            'summary': []
        }

        try:
            # Find users with valid access tokens in config.ini
            users_with_tokens = find_users_with_access_tokens()

            # Find users with orders files in Current_Orders
            users_with_orders = self.find_users_with_orders()

            # Find users with both access tokens and orders files
            users = sorted(list(set(users_with_tokens) & set(users_with_orders)))
            logger.info(f"Found {len(users)} users with both access tokens and orders files: {users}")

            # Add users with tokens but no orders files (for reporting only)
            users_tokens_only = sorted(list(set(users_with_tokens) - set(users_with_orders)))
            if users_tokens_only:
                logger.info(f"Found {len(users_tokens_only)} users with access tokens but no orders files: {users_tokens_only}")
                overall_result['summary'].append(f"Users with access tokens but no orders files: {', '.join(users_tokens_only)}")

            # Add users with orders files but no tokens (for reporting only)
            users_orders_only = sorted(list(set(users_with_orders) - set(users_with_tokens)))
            if users_orders_only:
                logger.info(f"Found {len(users_orders_only)} users with orders files but no access tokens: {users_orders_only}")
                overall_result['summary'].append(f"Users with orders files but no access tokens: {', '.join(users_orders_only)}")

            overall_result['users_found'] = len(users)

            if not users:
                overall_result['summary'].append("No users with both access tokens and orders files found")
                return overall_result

            # Sync each user
            for user_name in users:
                logger.info(f"Starting synchronization for user: {user_name}")
                user_result = self.sync_user_positions(user_name)
                overall_result['user_results'].append(user_result)

                if user_result['success']:
                    overall_result['users_synced'] += 1
                    overall_result['total_initial_discrepancies'] += len(user_result['initial_discrepancies'])

                    file_result = user_result.get('file_update_result', {})
                    changes = file_result.get('added_count', 0) + file_result.get('updated_count', 0) + file_result.get('removed_count', 0)
                    overall_result['total_changes_made'] += changes

            # Generate overall summary
            overall_result['summary'].insert(0, f"Synchronized {overall_result['users_synced']}/{overall_result['users_found']} users")
            overall_result['summary'].insert(1, f"Total initial discrepancies: {overall_result['total_initial_discrepancies']}")
            overall_result['summary'].insert(2, f"Total changes made: {overall_result['total_changes_made']}")

            if overall_result['total_initial_discrepancies'] == 0:
                overall_result['summary'].insert(3, "✅ All users' local files are already synchronized with broker!")
            elif overall_result['total_changes_made'] > 0:
                mode_msg = "DRY RUN MODE" if self.dry_run else "LIVE MODE"
                overall_result['summary'].insert(3, f"🔄 Synchronization completed - {overall_result['total_changes_made']} changes made ({mode_msg})")
            else:
                overall_result['summary'].insert(3, "ℹ️ Some discrepancies found but no changes needed")

            logger.info(f"Overall sync completed: {overall_result['users_synced']}/{overall_result['users_found']} users")

        except Exception as e:
            logger.error(f"Error in overall sync: {e}")
            overall_result['summary'].append(f"❌ Overall sync failed: {str(e)}")

        return overall_result
    
    def print_sync_report(self, sync_result: Dict[str, Any]):
        """Print detailed synchronization report"""
        print("\n" + "="*100)
        print("CNC POSITIONS SYNCHRONIZATION REPORT")
        print("="*100)
        
        if 'user_results' in sync_result:
            # Multi-user report
            print(f"Sync Time: {sync_result['sync_time']}")
            print(f"Users Found: {sync_result['users_found']}")
            print(f"Users Synced: {sync_result['users_synced']}")
            print(f"Total Initial Discrepancies: {sync_result['total_initial_discrepancies']}")
            print(f"Total Changes Made: {sync_result['total_changes_made']}")
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
        print(f"  Orders File: {user_result.get('orders_file', 'N/A')}")
        print(f"  Local Positions: {user_result['local_positions_count']}")
        print(f"  Broker Positions: {user_result['broker_positions_count']}")
        print(f"  Initial Discrepancies: {len(user_result['initial_discrepancies'])}")
        
        file_result = user_result.get('file_update_result', {})
        changes = file_result.get('added_count', 0) + file_result.get('updated_count', 0) + file_result.get('removed_count', 0)
        print(f"  Changes Made: {changes}")
        
        if user_result['initial_discrepancies']:
            print(f"  INITIAL DISCREPANCIES:")
            for disc in user_result['initial_discrepancies']:
                print(f"    {disc['symbol']:12s} | Type: {disc['type']:15s} | Local: {disc['local_qty']:4d} | Broker: {disc['broker_qty']:4d}")
                print(f"                     | {disc['recommendation']}")
        
        if file_result and changes > 0:
            print(f"  FILE UPDATE RESULTS:")
            if file_result.get('added_count', 0) > 0:
                print(f"    Added: {file_result['added_count']} positions")
            if file_result.get('updated_count', 0) > 0:
                print(f"    Updated: {file_result['updated_count']} positions")
            if file_result.get('removed_count', 0) > 0:
                print(f"    Removed: {file_result['removed_count']} positions")
        
        print(f"  RECOMMENDATIONS:")
        for rec in user_result['recommendations']:
            print(f"    {rec}")


def find_users_with_access_tokens():
    """Find all users with valid access tokens in config.ini"""
    users = []
    try:
        daily_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(daily_dir, 'config.ini')

        if not os.path.exists(config_path):
            logger.error(f"Config file not found: {config_path}")
            return users

        config = configparser.ConfigParser()
        config.read(config_path)

        # Find all API_CREDENTIALS sections
        for section in config.sections():
            if section.startswith('API_CREDENTIALS_'):
                user_name = section.replace('API_CREDENTIALS_', '')

                # Check if the section has an access token
                if config.has_option(section, 'access_token') and config.get(section, 'access_token').strip():
                    users.append(user_name)
                    logger.info(f"Found user with access token: {user_name}")

        logger.info(f"Found {len(users)} users with access tokens: {users}")
        return sorted(users)

    except Exception as e:
        logger.error(f"Error finding users with access tokens: {e}")
        return []

def main():
    """Main function to synchronize CNC positions"""
    parser = argparse.ArgumentParser(description='Synchronize local orders files with Zerodha broker CNC positions')
    parser.add_argument('--credential-user', '-c', type=str, default='Sai',
                      help='User whose API credentials to use (default: Sai)')
    parser.add_argument('--sync-user', '-u', type=str,
                      help='Sync specific user only (overrides default all-users mode)')
    parser.add_argument('--sync-all', '-a', action='store_true', default=True,
                      help='Sync all users with valid access tokens (default: True)')
    parser.add_argument('--no-sync-all', '-na', action='store_false', dest='sync_all',
                      help='Disable all-users mode, sync only the credential user')
    parser.add_argument('--quiet', '-q', action='store_true',
                      help='Suppress detailed output')
    parser.add_argument('--json-output', '-j', type=str,
                      help='Save results to JSON file')
    parser.add_argument('--dry-run', '-d', action='store_true',
                      help='Dry run mode - show what would be done without making changes')
    parser.add_argument('--force', '-f', action='store_true',
                      help='Force live mode (deprecated - live mode is now default)')

    args = parser.parse_args()

    try:
        # Determine run mode
        if args.dry_run:
            dry_run = True
            logger.info("Starting CNC positions synchronization in DRY RUN MODE (no files will be modified)")
        else:
            dry_run = False  # Default to live mode for convenience
            logger.info("Starting CNC positions synchronization in LIVE MODE (will update local files)")

        if args.force:
            dry_run = False
            logger.info("Live mode explicitly enabled")

        # Initialize synchronizer with credential user
        credential_user = args.credential_user
        logger.info(f"Initializing synchronizer with credentials for user: {credential_user}")
        synchronizer = ZerodhaCNCPositionsSynchronizer(dry_run=dry_run, default_user=credential_user)

        # Determine which users to sync
        if args.sync_user:
            # Sync specific user
            logger.info(f"Syncing only user: {args.sync_user}")
            result = synchronizer.sync_user_positions(args.sync_user)
        elif not args.sync_all:
            # --sync-all is now default, but we can override with a non-sync-all option
            # If someone explicitly used --sync-all=False, sync only the credential user
            logger.info(f"Syncing only credential user: {credential_user} (overriding default all-users mode)")
            result = synchronizer.sync_user_positions(credential_user)
        else:
            # Default: Sync all users with valid access tokens
            logger.info("DEFAULT MODE: Syncing all users with valid access tokens")
            result = synchronizer.sync_all_users()

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
            return 0 if result['total_initial_discrepancies'] == 0 else 1
        else:
            # Single user result
            return 0 if result['success'] and len(result['initial_discrepancies']) == 0 else 1

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
    print("ENHANCED CNC POSITIONS SYNCHRONIZATION SCRIPT")
    print("="*100)
    print("This script synchronizes LOCAL orders files with SERVER-SIDE CNC positions from Zerodha broker")
    print("")
    print("Features:")
    print("• Copies server-side broker positions to local orders files")
    print("• Updates existing orders files with current broker data")
    print("• User-specific credential management from config.ini")
    print("• Multi-user synchronization with all-users mode")
    print("• Detailed sync reports and JSON output options")
    print("• Live mode (default) and dry run mode options")
    print("")
    print("Command-line Options:")
    print("• --credential-user, -c NAME : User whose API credentials to use (default: Sai)")
    print("• --sync-user, -u NAME       : Sync specific user only (overrides default all-users mode)")
    print("• --no-sync-all, -na         : Disable all-users mode, sync only the credential user")
    print("• --dry-run, -d              : Show what would be done without making changes")
    print("• --quiet, -q                : Suppress detailed output")
    print("• --json-output, -j FILE     : Save results to JSON file")
    print("")
    print("DEFAULT BEHAVIOR: This script now syncs ALL users with valid access tokens by default.")
    print("")
    print("IMPORTANT: This script ONLY updates local files with server data.")
    print("           It does NOT place any buy/sell orders on the server.")
    print("")
    print("Examples:")
    print("• Basic usage (all users): python synch_zerodha_cnc_positions.py")
    print("• Dry run mode          : python synch_zerodha_cnc_positions.py --dry-run")
    print("• Single user only      : python synch_zerodha_cnc_positions.py --no-sync-all")
    print("• Specific user only    : python synch_zerodha_cnc_positions.py --sync-user Som")
    print("• Using Som's credentials: python synch_zerodha_cnc_positions.py -c Som")
    print("="*100)

    exit_code = main()
    sys.exit(exit_code)