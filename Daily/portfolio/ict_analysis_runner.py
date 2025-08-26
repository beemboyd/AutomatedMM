#!/usr/bin/env python3
"""
ICT Analysis Runner - Runs ICT analysis for automatic updates
Called by LaunchAgent every 15 minutes during market hours
"""

import os
import sys
import datetime
import subprocess
import logging

# Setup logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs', 'ict_analysis')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'scheduler.log')),
        logging.StreamHandler()
    ]
)

def is_market_hours():
    """Check if current time is within market hours"""
    now = datetime.datetime.now()
    current_time = now.hour * 100 + now.minute
    
    # Market hours: 9:15 AM to 3:30 PM
    return 915 <= current_time <= 1530

def run_ict_analysis():
    """Run the ICT analysis script"""
    try:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'SL_Watch_ICT.py')
        
        # Run the analysis
        result = subprocess.run(
            [sys.executable, script_path, '--user', 'Sai'],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        
        if result.returncode == 0:
            logging.info("ICT Analysis completed successfully")
            # Log summary of positions analyzed
            if 'Found' in result.stdout:
                for line in result.stdout.split('\n'):
                    if 'Found' in line and 'positions' in line:
                        logging.info(line.strip())
            return True
        else:
            logging.error(f"ICT Analysis failed with return code {result.returncode}")
            if result.stderr:
                logging.error(f"Error: {result.stderr[:500]}")  # Log first 500 chars of error
            return False
            
    except subprocess.TimeoutExpired:
        logging.error("ICT Analysis timed out after 2 minutes")
        return False
    except Exception as e:
        logging.error(f"Error running ICT Analysis: {e}")
        return False

def main():
    """Main execution"""
    logging.info("="*60)
    logging.info("ICT Analysis Scheduler Started")
    
    if not is_market_hours():
        logging.info("Outside market hours, skipping analysis")
        return
    
    logging.info("Market hours confirmed, running analysis...")
    
    # Run the analysis
    success = run_ict_analysis()
    
    if success:
        logging.info("Dashboard will reflect updated stop loss recommendations")
    else:
        logging.warning("Analysis failed, dashboard may show stale data")
    
    logging.info("="*60)

if __name__ == "__main__":
    main()