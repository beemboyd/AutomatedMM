#!/usr/bin/env python
"""
FNO Scanner Scheduler - Run KC Upper and Lower Limit Trending scanners for F&O stocks
Runs hourly between 9 AM - 3 PM IST on weekdays
"""

import os
import sys
import subprocess
import time
import logging
from datetime import datetime, time as dt_time
import pytz
import argparse

# Add parent directory to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "fno_scanner_scheduler.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Define IST timezone
IST = pytz.timezone('Asia/Kolkata')

# Trading hours
MARKET_OPEN = dt_time(9, 0)  # 9:00 AM IST
MARKET_CLOSE = dt_time(15, 30)  # 3:30 PM IST

# Scanner scripts
SCANNER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scanners")
KC_UPPER_SCANNER = os.path.join(SCANNER_DIR, "KC_Upper_Limit_Trending_FNO.py")
KC_LOWER_SCANNER = os.path.join(SCANNER_DIR, "KC_Lower_Limit_Trending_FNO.py")

def is_trading_time():
    """Check if current time is within trading hours"""
    now = datetime.now(IST)
    current_time = now.time()
    
    # Check if it's a weekday (Monday=0, Friday=4)
    if now.weekday() > 4:  # Saturday or Sunday
        return False
    
    # Check if within trading hours
    if current_time < MARKET_OPEN or current_time > MARKET_CLOSE:
        return False
    
    return True

def is_market_holiday():
    """Check if today is a market holiday"""
    # This is a simple implementation. You may want to maintain a holiday list
    # or integrate with a holiday calendar API
    holidays = [
        # Add NSE holidays here
        # Example: datetime(2025, 1, 26).date(),  # Republic Day
    ]
    
    today = datetime.now(IST).date()
    return today in holidays

def run_scanner(scanner_path, scanner_name, user="Sai"):
    """Run a single scanner"""
    try:
        logger.info(f"Starting {scanner_name} scanner...")
        
        # Run the scanner
        cmd = [sys.executable, scanner_path, "-u", user]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for completion with timeout of 5 minutes
        stdout, stderr = process.communicate(timeout=300)
        
        if process.returncode == 0:
            logger.info(f"{scanner_name} scanner completed successfully")
            return True
        else:
            logger.error(f"{scanner_name} scanner failed with return code {process.returncode}")
            if stderr:
                logger.error(f"Error output: {stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"{scanner_name} scanner timed out after 5 minutes")
        process.kill()
        return False
    except Exception as e:
        logger.error(f"Error running {scanner_name} scanner: {e}")
        return False

def run_fno_scanners(user="Sai"):
    """Run both KC Upper and Lower scanners for FNO stocks"""
    logger.info("=" * 60)
    logger.info("Running FNO KC scanners")
    logger.info(f"Time: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}")
    logger.info("=" * 60)
    
    # Check if scanner files exist
    if not os.path.exists(KC_UPPER_SCANNER):
        logger.error(f"KC Upper scanner not found: {KC_UPPER_SCANNER}")
        return False
    
    if not os.path.exists(KC_LOWER_SCANNER):
        logger.error(f"KC Lower scanner not found: {KC_LOWER_SCANNER}")
        return False
    
    # Run both scanners
    upper_success = run_scanner(KC_UPPER_SCANNER, "KC Upper Limit Trending FNO", user)
    lower_success = run_scanner(KC_LOWER_SCANNER, "KC Lower Limit Trending FNO", user)
    
    if upper_success and lower_success:
        logger.info("All FNO scanners completed successfully")
        return True
    else:
        logger.warning("Some FNO scanners failed")
        return False

def continuous_scheduler(user="Sai", interval_minutes=60):
    """Run scanners continuously during market hours"""
    logger.info("Starting FNO scanner scheduler in continuous mode")
    logger.info(f"Will run every {interval_minutes} minutes during market hours")
    logger.info(f"Using credentials for user: {user}")
    
    while True:
        try:
            now = datetime.now(IST)
            
            # Check if it's trading time
            if not is_trading_time():
                logger.info(f"Outside trading hours. Current time: {now.strftime('%H:%M:%S IST')}")
                # Sleep for 5 minutes and check again
                time.sleep(300)
                continue
            
            # Check if it's a market holiday
            if is_market_holiday():
                logger.info("Market is closed today (holiday)")
                # Sleep for 1 hour and check again
                time.sleep(3600)
                continue
            
            # Run the scanners
            run_fno_scanners(user)
            
            # Calculate next run time
            next_run = now.replace(second=0, microsecond=0)
            
            # If we're at the start of an hour, schedule for the next hour
            if now.minute < 5:  # Give 5 minute buffer
                next_run = next_run.replace(minute=0)
                next_run = next_run.replace(hour=next_run.hour + 1)
            else:
                # Otherwise schedule for the next hour
                if next_run.hour < 23:
                    next_run = next_run.replace(hour=next_run.hour + 1, minute=0)
                else:
                    # End of day, stop
                    logger.info("End of trading day. Scheduler stopping.")
                    break
            
            # Check if next run would be after market close
            if next_run.time() > MARKET_CLOSE:
                logger.info("Next scheduled run would be after market close. Stopping scheduler.")
                break
            
            # Calculate sleep time
            sleep_seconds = (next_run - datetime.now(IST)).total_seconds()
            
            if sleep_seconds > 0:
                logger.info(f"Next run scheduled at: {next_run.strftime('%H:%M:%S IST')}")
                logger.info(f"Sleeping for {int(sleep_seconds)} seconds...")
                time.sleep(sleep_seconds)
            
        except KeyboardInterrupt:
            logger.info("Scheduler interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in scheduler: {e}")
            # Sleep for 5 minutes before retrying
            time.sleep(300)

def single_run(user="Sai"):
    """Run scanners once"""
    if not is_trading_time():
        logger.warning("Outside trading hours. Running anyway as requested.")
    
    if is_market_holiday():
        logger.warning("Market is closed today (holiday). Running anyway as requested.")
    
    return run_fno_scanners(user)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="FNO KC Scanner Scheduler")
    parser.add_argument("-u", "--user", default="Sai", help="User name for API credentials (default: Sai)")
    parser.add_argument("-m", "--mode", choices=["single", "continuous"], default="continuous",
                       help="Run mode: single (run once) or continuous (run hourly during market)")
    parser.add_argument("-i", "--interval", type=int, default=60,
                       help="Interval in minutes for continuous mode (default: 60)")
    
    args = parser.parse_args()
    
    logger.info("FNO Scanner Scheduler Started")
    logger.info(f"Mode: {args.mode}")
    logger.info(f"User: {args.user}")
    
    if args.mode == "single":
        success = single_run(args.user)
        sys.exit(0 if success else 1)
    else:
        continuous_scheduler(args.user, args.interval)

if __name__ == "__main__":
    main()