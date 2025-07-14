#!/usr/bin/env python
"""
Start SL Watchdog for all users with valid access tokens in config.ini
This script launches separate SL watchdog processes for each user
"""

import os
import sys
import subprocess
import configparser
import time
import logging
from datetime import datetime
import pytz

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/maverick/PycharmProjects/India-TS/Daily/logs/sl_watchdog_master.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration from Daily/config.ini file"""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini file not found at {config_path}")
    
    config.read(config_path)
    return config

def get_users_with_access_tokens(config):
    """Get list of users who have valid access tokens"""
    users = []
    
    for section in config.sections():
        if section.startswith('API_CREDENTIALS_'):
            user_name = section.replace('API_CREDENTIALS_', '')
            
            # Check if user has access token
            access_token = config.get(section, 'access_token', fallback='').strip()
            api_key = config.get(section, 'api_key', fallback='').strip()
            
            if access_token and api_key:
                users.append(user_name)
                logger.info(f"Found valid credentials for user: {user_name}")
            else:
                if api_key and not access_token:
                    logger.warning(f"User {user_name} has api_key but missing access_token")
                else:
                    logger.warning(f"User {user_name} missing credentials")
    
    return users

def is_market_hours():
    """Check if current time is within market hours"""
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist)
    
    # Check if weekday (Monday = 0, Sunday = 6)
    if current_time.weekday() > 4:  # Saturday or Sunday
        return False
    
    # Market hours: 9:15 AM to 3:30 PM IST
    market_start = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = current_time.replace(hour=15, minute=30, second=0, microsecond=0)
    
    return market_start <= current_time <= market_end

def start_watchdog_for_user(user_name):
    """Start SL watchdog for a specific user"""
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'SL_watchdog.py')
    pid_file = f'/Users/maverick/PycharmProjects/India-TS/Daily/pids/watchdog_{user_name}.pid'
    
    # Check if already running
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is actually running
            os.kill(pid, 0)
            logger.info(f"SL Watchdog for {user_name} already running with PID {pid}")
            return True
        except (OSError, ValueError):
            # Process not running, remove stale PID file
            os.remove(pid_file)
    
    # Start the watchdog
    cmd = [sys.executable, script_path, '-u', user_name]
    
    try:
        # Start process in background
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        # Give it a moment to start
        time.sleep(2)
        
        # Check if process started successfully
        if process.poll() is None:
            logger.info(f"Successfully started SL Watchdog for {user_name} (PID: {process.pid})")
            return True
        else:
            stderr = process.stderr.read().decode() if process.stderr else ""
            logger.error(f"Failed to start SL Watchdog for {user_name}: {stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error starting SL Watchdog for {user_name}: {str(e)}")
        return False

def main():
    """Main function to start SL watchdogs for all users"""
    logger.info("=" * 60)
    logger.info("Starting SL Watchdog Master Controller")
    logger.info("=" * 60)
    
    # Check if market hours
    if not is_market_hours():
        logger.info("Outside market hours. SL Watchdogs will not be started.")
        return
    
    try:
        # Load config
        config = load_config()
        
        # Get users with valid access tokens
        users = get_users_with_access_tokens(config)
        
        if not users:
            logger.error("No users found with valid access tokens!")
            return
        
        logger.info(f"Found {len(users)} users with valid credentials: {', '.join(users)}")
        
        # Start watchdog for each user
        successful = 0
        failed = 0
        
        for user in users:
            logger.info(f"\nStarting SL Watchdog for {user}...")
            if start_watchdog_for_user(user):
                successful += 1
            else:
                failed += 1
            
            # Small delay between starts
            time.sleep(1)
        
        logger.info("\n" + "=" * 60)
        logger.info(f"Summary: {successful} successful, {failed} failed")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()