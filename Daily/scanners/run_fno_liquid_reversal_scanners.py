#!/usr/bin/env python
"""
Run FNO Liquid Reversal Scanners
Runs both Long and Short Reversal Daily scanners for FNO Liquid stocks
"""

import os
import sys
import subprocess
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "logs", "fno_liquid_reversal_scanner.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_scanner(scanner_script):
    """Run a scanner script"""
    try:
        logger.info(f"Running {scanner_script}...")
        result = subprocess.run([sys.executable, scanner_script], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"{scanner_script} completed successfully")
            return True
        else:
            logger.error(f"{scanner_script} failed with error: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error running {scanner_script}: {e}")
        return False

def main():
    """Main execution"""
    logger.info("=" * 50)
    logger.info(f"Starting FNO Liquid Reversal Scanners at {datetime.now()}")
    
    # Get scanner directory
    scanner_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define scanner scripts
    long_scanner = os.path.join(scanner_dir, "Long_Reversal_Daily_FNO_Liquid.py")
    short_scanner = os.path.join(scanner_dir, "Short_Reversal_Daily_FNO_Liquid.py")
    
    # Run both scanners
    success_count = 0
    
    # Run Long Reversal scanner
    if run_scanner(long_scanner):
        success_count += 1
    
    # Run Short Reversal scanner
    if run_scanner(short_scanner):
        success_count += 1
    
    # Summary
    logger.info(f"Completed running FNO Liquid Reversal scanners: {success_count}/2 successful")
    logger.info("=" * 50)
    
    return success_count == 2

if __name__ == "__main__":
    sys.exit(0 if main() else 1)