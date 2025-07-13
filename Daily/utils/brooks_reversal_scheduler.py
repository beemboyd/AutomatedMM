#!/usr/bin/env python3
"""
Wrapper script to run Al_Brooks_Higher_Probability_Reversal.py
only during market hours (9:00 AM to 3:30 PM IST) on weekdays
"""

import os
import sys
import subprocess
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/maverick/PycharmProjects/India-TS/Daily/logs/brooks_scheduler.log'),
        logging.StreamHandler()
    ]
)

def is_market_hours():
    """Check if current time is within market hours and on a weekday"""
    now = datetime.now()
    
    # Check if it's a weekday (Monday=0, Sunday=6)
    if now.weekday() >= 5:  # Saturday or Sunday
        logging.info(f"Skipping - Weekend (Day: {now.strftime('%A')})")
        return False
    
    # Check time (9:00 AM to 3:30 PM)
    current_time = now.time()
    market_open = datetime.strptime("09:00", "%H:%M").time()
    market_close = datetime.strptime("15:30", "%H:%M").time()
    
    if current_time < market_open or current_time > market_close:
        logging.info(f"Skipping - Outside market hours (Current time: {current_time})")
        return False
    
    return True

def main():
    """Main function to check conditions and run the Brooks script"""
    logging.info("Brooks Reversal Scheduler - Checking conditions...")
    
    if not is_market_hours():
        return
    
    # Run the Al Brooks script
    script_path = "/Users/maverick/PycharmProjects/India-TS/Daily/scripts/Al_Brooks_Higher_Probability_Reversal.py"
    python_path = "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
    
    logging.info("Market hours confirmed - Running Al Brooks Higher Probability Reversal script...")
    
    try:
        # Run the script
        result = subprocess.run(
            [python_path, script_path],
            capture_output=True,
            text=True,
            cwd="/Users/maverick/PycharmProjects/India-TS/Daily"
        )
        
        if result.returncode == 0:
            logging.info("Script executed successfully")
            if result.stdout:
                logging.info(f"Output: {result.stdout[-500:]}")  # Last 500 chars
        else:
            logging.error(f"Script failed with return code: {result.returncode}")
            if result.stderr:
                logging.error(f"Error: {result.stderr}")
                
    except Exception as e:
        logging.error(f"Exception running script: {e}")

if __name__ == "__main__":
    main()