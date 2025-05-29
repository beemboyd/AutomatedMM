#!/usr/bin/env python3
"""
Migration Script: Convert Single State File to User-Specific State Files
This script migrates from the old shared trading_state.json to user-specific state files
"""
import os
import sys
import json
import shutil
import configparser
from datetime import datetime
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_daily_config():
    """Load configuration from Daily/config.ini file"""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini file not found at {config_path}")
    
    config.read(config_path)
    return config

def get_available_users(config):
    """Extract available user names from config"""
    users = []
    for section in config.sections():
        if section.startswith('API_CREDENTIALS_'):
            user_name = section.replace('API_CREDENTIALS_', '')
            api_key = config.get(section, 'api_key', fallback='')
            api_secret = config.get(section, 'api_secret', fallback='')
            access_token = config.get(section, 'access_token', fallback='')
            
            if api_key and api_secret and access_token:
                users.append(user_name)
    
    return users

def backup_original_state(data_dir: str) -> str:
    """Create backup of original state file"""
    original_state_file = os.path.join(data_dir, 'trading_state.json')
    
    if not os.path.exists(original_state_file):
        print("No existing trading_state.json found - nothing to migrate")
        return None
    
    # Create backup with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(data_dir, f'trading_state_backup_{timestamp}.json')
    
    shutil.copy2(original_state_file, backup_file)
    print(f"Created backup: {backup_file}")
    
    return backup_file

def load_original_state(data_dir: str) -> Dict:
    """Load the original shared state file"""
    original_state_file = os.path.join(data_dir, 'trading_state.json')
    
    if not os.path.exists(original_state_file):
        return None
    
    try:
        with open(original_state_file, 'r') as f:
            state = json.load(f)
        print(f"Loaded original state file with {len(state.get('positions', {}))} positions")
        return state
    except Exception as e:
        print(f"Error loading original state file: {e}")
        return None

def analyze_positions_by_user(state: Dict, current_orders_dir: str) -> Dict[str, List[str]]:
    """
    Analyze positions and try to determine which user they belong to
    by looking at Current_Orders files
    """
    user_positions = {}
    unassigned_positions = []
    
    positions = state.get('positions', {})
    
    # Get all tickers from positions
    position_tickers = set(positions.keys())
    
    # Look through Current_Orders directories to find which user owns which tickers
    if os.path.exists(current_orders_dir):
        for user_dir in os.listdir(current_orders_dir):
            user_path = os.path.join(current_orders_dir, user_dir)
            if os.path.isdir(user_path):
                user_tickers = set()
                
                # Look through order files for this user
                for order_file in os.listdir(user_path):
                    if order_file.endswith('.json'):
                        try:
                            order_file_path = os.path.join(user_path, order_file)
                            with open(order_file_path, 'r') as f:
                                order_data = json.load(f)
                            
                            # Extract tickers from orders
                            orders = order_data.get('orders', [])
                            for order in orders:
                                ticker = order.get('ticker')
                                if ticker and ticker in position_tickers:
                                    user_tickers.add(ticker)
                        
                        except Exception as e:
                            print(f"Error reading {order_file}: {e}")
                
                if user_tickers:
                    user_positions[user_dir] = list(user_tickers)
                    print(f"Found {len(user_tickers)} positions for user {user_dir}: {list(user_tickers)}")
    
    # Find unassigned positions
    assigned_tickers = set()
    for tickers in user_positions.values():
        assigned_tickers.update(tickers)
    
    unassigned_positions = [ticker for ticker in position_tickers if ticker not in assigned_tickers]
    
    if unassigned_positions:
        print(f"Found {len(unassigned_positions)} unassigned positions: {unassigned_positions}")
    
    return user_positions, unassigned_positions

def create_user_state_files(state: Dict, user_positions: Dict[str, List[str]], 
                          unassigned_positions: List[str], users: List[str], data_dir: str):
    """Create user-specific state files"""
    
    original_positions = state.get('positions', {})
    original_daily_tickers = state.get('daily_tickers', {'long': [], 'short': []})
    original_gtt_orders = state.get('gtt_orders', {})
    
    # Handle unassigned positions
    if unassigned_positions:
        print(f"\nUnassigned positions found: {unassigned_positions}")
        print("These positions cannot be automatically assigned to a user.")
        print("Please assign them manually:")
        
        for ticker in unassigned_positions:
            print(f"\nPosition: {ticker}")
            print("Available users:")
            for i, user in enumerate(users, 1):
                print(f"  {i}. {user}")
            print(f"  {len(users) + 1}. Skip this position")
            
            while True:
                try:
                    choice = int(input(f"Assign {ticker} to user (1-{len(users) + 1}): "))
                    if 1 <= choice <= len(users):
                        selected_user = users[choice - 1]
                        if selected_user not in user_positions:
                            user_positions[selected_user] = []
                        user_positions[selected_user].append(ticker)
                        print(f"Assigned {ticker} to {selected_user}")
                        break
                    elif choice == len(users) + 1:
                        print(f"Skipped {ticker}")
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(users) + 1}")
                except ValueError:
                    print("Please enter a valid number")
    
    # Create state file for each user
    created_files = []
    
    for user in users:
        user_state_file = os.path.join(data_dir, f'trading_state_{user}.json')
        user_tickers = user_positions.get(user, [])
        
        # Create user-specific state
        user_state = {
            "meta": {
                "user_name": user,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "last_updated": datetime.now().isoformat(),
                "created": datetime.now().isoformat(),
                "migrated_from": "trading_state.json"
            },
            "positions": {},
            "daily_tickers": {"long": [], "short": []},
            "gtt_orders": {},
            "session_data": {}
        }
        
        # Add user's positions
        for ticker in user_tickers:
            if ticker in original_positions:
                user_state["positions"][ticker] = original_positions[ticker]
        
        # Add user's daily tickers (if they can be determined)
        for position_type in ["long", "short"]:
            for ticker in original_daily_tickers.get(position_type, []):
                if ticker in user_tickers:
                    user_state["daily_tickers"][position_type].append(ticker)
        
        # Add user's GTT orders (if they can be determined)
        for gtt_id, gtt_data in original_gtt_orders.items():
            gtt_ticker = gtt_data.get('tradingsymbol') or gtt_data.get('ticker')
            if gtt_ticker and gtt_ticker in user_tickers:
                user_state["gtt_orders"][gtt_id] = gtt_data
        
        # Save user state file
        with open(user_state_file, 'w') as f:
            json.dump(user_state, f, indent=2, default=str)
        
        created_files.append(user_state_file)
        print(f"Created {user_state_file} with {len(user_state['positions'])} positions")
    
    return created_files

def main():
    """Main migration function"""
    print("=== Migration to User Context Architecture ===")
    print("This script will migrate from shared trading_state.json to user-specific state files")
    
    try:
        # Load config and get users
        config = load_daily_config()
        users = get_available_users(config)
        
        if not users:
            print("No valid users found in config.ini")
            return 1
        
        print(f"Found {len(users)} users: {users}")
        
        # Set up paths
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        current_orders_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Current_Orders')
        
        os.makedirs(data_dir, exist_ok=True)
        
        # Backup original state
        backup_file = backup_original_state(data_dir)
        if not backup_file:
            return 0  # Nothing to migrate
        
        # Load original state
        original_state = load_original_state(data_dir)
        if not original_state:
            print("Could not load original state file")
            return 1
        
        # Analyze positions by user
        print("\nAnalyzing positions...")
        user_positions, unassigned_positions = analyze_positions_by_user(original_state, current_orders_dir)
        
        # Create user-specific state files
        print("\nCreating user-specific state files...")
        created_files = create_user_state_files(
            original_state, user_positions, unassigned_positions, users, data_dir
        )
        
        # Summary
        print(f"\n=== Migration Complete ===")
        print(f"Created {len(created_files)} user-specific state files:")
        for file_path in created_files:
            print(f"  - {os.path.basename(file_path)}")
        
        print(f"\nOriginal file backed up to: {os.path.basename(backup_file)}")
        
        # Ask if user wants to remove original file
        response = input("\nRemove original trading_state.json? (y/N): ")
        if response.lower() == 'y':
            original_file = os.path.join(data_dir, 'trading_state.json')
            os.remove(original_file)
            print("Original trading_state.json removed")
        else:
            print("Original trading_state.json kept (you can remove it manually later)")
        
        print("\nMigration completed successfully!")
        print("You can now use the UserContextManager architecture.")
        
        return 0
        
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())