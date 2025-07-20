#!/usr/bin/env python3
"""
Improved place_orders_daily.py using User Context Manager
This eliminates singleton issues completely
"""
import os
import sys
import logging
import configparser
from typing import List, Dict

# Add parent directory to path for imports
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ..user_context_manager import (
    get_context_manager, 
    get_user_state_manager, 
    get_user_order_manager,
    UserCredentials
)

def load_daily_config():
    """Load configuration from Daily/config.ini file"""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    config.read(config_path)
    return config

def get_available_users(config) -> List[UserCredentials]:
    """Extract available user credentials from config"""
    users = []
    for section in config.sections():
        if section.startswith('API_CREDENTIALS_'):
            user_name = section.replace('API_CREDENTIALS_', '')
            api_key = config.get(section, 'api_key', fallback='')
            api_secret = config.get(section, 'api_secret', fallback='')
            access_token = config.get(section, 'access_token', fallback='')
            
            if api_key and api_secret and access_token:
                users.append(UserCredentials(
                    name=user_name,
                    api_key=api_key,
                    api_secret=api_secret,
                    access_token=access_token
                ))
    return users

def select_user(users: List[UserCredentials]) -> UserCredentials:
    """Allow user to select which credentials to use"""
    if not users:
        raise ValueError("No valid API credentials found in config.ini")
    
    print("\\nAvailable accounts:")
    for i, user in enumerate(users, 1):
        print(f"{i}. {user.name}")
    
    while True:
        try:
            choice = int(input(f"\\nSelect account (1-{len(users)}): "))
            if 1 <= choice <= len(users):
                return users[choice - 1]
            else:
                print(f"Please enter a number between 1 and {len(users)}")
        except ValueError:
            print("Please enter a valid number")

def setup_user_context(user_credentials: UserCredentials):
    """
    Set up user context - NO MORE SINGLETON CLEARING NEEDED!
    
    Args:
        user_credentials: Selected user's credentials
    """
    context_manager = get_context_manager()
    context_manager.set_current_user(user_credentials.name, user_credentials)
    
    # Set up user-specific logging
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                          'logs', user_credentials.name)
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(log_dir, f'place_orders_daily_{user_credentials.name}.log'))
        ],
        force=True
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"User context set up for: {user_credentials.name}")
    return logger

def main():
    """Main function with improved user handling"""
    try:
        print("=== CNC Order Placement Tool (Multi-User) ===")
        
        # Load config and get users
        config = load_daily_config()
        users = get_available_users(config)
        
        # Select user
        selected_user = select_user(users)
        print(f"\\nSelected account: {selected_user.name}")
        
        # Set up user context (replaces all singleton clearing!)
        logger = setup_user_context(selected_user)
        
        # Now get user-specific instances (no singleton conflicts!)
        state_manager = get_user_state_manager()  # User-specific instance
        order_manager = get_user_order_manager()  # User-specific instance
        
        logger.info(f"Initialized services for user: {selected_user.name}")
        logger.info(f"API Key in use: {order_manager.data_handler.api_key[:8]}...")
        
        # Rest of your trading logic here...
        # All services are now guaranteed to be user-specific!
        
        return 0
        
    except Exception as e:
        logging.exception(f"Error in main function: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())