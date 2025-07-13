#!/usr/bin/env python3
"""
Automated StrategyC Runner
Runs StrategyKV_C_Filter without user prompts for scheduled execution
"""

import os
import sys
import subprocess
import logging
from datetime import datetime

def setup_logging():
    """Setup logging for automated run"""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'strategyc_auto_{datetime.now().strftime("%Y%m%d")}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

def main():
    """Run StrategyC with default parameters"""
    logger = setup_logging()
    
    logger.info("="*60)
    logger.info("Starting Automated StrategyC Filter")
    logger.info("="*60)
    
    try:
        # Change to Daily directory
        daily_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.chdir(daily_dir)
        
        # Default parameters
        num_reports = 5
        
        logger.info(f"Running with parameters:")
        logger.info(f"  - Number of reports to analyze: {num_reports}")
        logger.info(f"  - Mode: Automated (no prompts)")
        
        # Run the original script with input piped in
        # Send "n" for test mode, then the number of reports
        script_path = os.path.join(daily_dir, "scanners", "StrategyKV_C_Filter.py")
        
        # Create input for the interactive prompts
        input_data = f"n\n{num_reports}\n"
        
        # Run the script
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=input_data)
        
        # Log output
        if stdout:
            logger.info("Script output:")
            for line in stdout.strip().split('\n'):
                logger.info(f"  {line}")
        
        if stderr:
            logger.error("Script errors:")
            for line in stderr.strip().split('\n'):
                logger.error(f"  {line}")
        
        if process.returncode == 0:
            logger.info("StrategyC completed successfully")
        else:
            logger.error(f"StrategyC failed with return code: {process.returncode}")
            
    except Exception as e:
        logger.error(f"Error running StrategyC: {str(e)}", exc_info=True)
        sys.exit(1)
    
    logger.info("="*60)
    logger.info("StrategyC Filter Completed")
    logger.info("="*60)

if __name__ == "__main__":
    main()