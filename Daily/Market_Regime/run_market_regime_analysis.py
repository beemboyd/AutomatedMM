#!/usr/bin/env python
"""
Run Market Regime Analysis
Simple runner script for scheduled execution
"""

import os
import sys
import subprocess
import datetime
import logging

# Add parent directories to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up logging
log_dir = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "scheduled_runs.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Run the market regime analysis"""
    logger.info("="*50)
    logger.info(f"Starting scheduled market regime analysis at {datetime.datetime.now()}")
    
    try:
        # Run the market regime analyzer
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                   "market_regime_analyzer.py")
        
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("Market regime analysis completed successfully")
            if result.stdout:
                logger.info(f"Output:\n{result.stdout}")
        else:
            logger.error(f"Market regime analysis failed with return code {result.returncode}")
            if result.stderr:
                logger.error(f"Error output:\n{result.stderr}")
                
        logger.info(f"Completed at {datetime.datetime.now()}")
        logger.info("="*50 + "\n")
        
        return result.returncode
        
    except Exception as e:
        logger.error(f"Exception during market regime analysis: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())