#!/usr/bin/env python3
"""
Run momentum analysis and generate Strong Candidates report
Can be scheduled to run periodically (e.g., every hour during market hours)
"""

import os
import sys
import logging
from datetime import datetime
import subprocess

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from Daily.scanners.Filtered.momentum_analyzer import MomentumAnalyzer

# Configure logging
log_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/logs"
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f"momentum_analysis_{datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def is_market_hours():
    """Check if current time is within market hours"""
    now = datetime.now()
    # Market hours: 9:15 AM to 3:30 PM
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    # Also check if it's a weekday
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
        
    return market_open <= now <= market_close

def run_analysis():
    """Run the momentum analysis"""
    try:
        logger.info("="*50)
        logger.info("Starting momentum analysis run")
        
        # Initialize analyzer with 3-day lookback
        analyzer = MomentumAnalyzer(lookback_days=3)
        
        # Run analysis
        report_path = analyzer.run_analysis()
        
        logger.info(f"Analysis completed successfully")
        logger.info(f"Report generated: {report_path}")
        
        # Optionally open the PDF (comment out for automated runs)
        # subprocess.run(['open', report_path])
        
        return True
        
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}", exc_info=True)
        return False

def main():
    """Main entry point"""
    # Check if we should run (optional - remove for manual runs)
    if not is_market_hours() and '--force' not in sys.argv:
        logger.info("Outside market hours. Use --force to run anyway.")
        return
        
    # Run the analysis
    success = run_analysis()
    
    if success:
        logger.info("Momentum analysis completed successfully")
    else:
        logger.error("Momentum analysis failed")
        sys.exit(1)

if __name__ == "__main__":
    main()