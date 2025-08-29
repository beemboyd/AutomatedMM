#!/usr/bin/env python3
"""
One-time script to collect initial 30 days of hourly SMA breadth data
This populates the historical hourly data for the dashboard
"""

import sys
import os
import logging
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the hourly collector
from sma_breadth_hourly_collector import SMABreadthHourlyCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """
    Main function to collect initial 30 days of hourly data
    """
    logger.info("=" * 60)
    logger.info("INITIAL HOURLY SMA BREADTH DATA COLLECTION")
    logger.info("=" * 60)
    logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Create collector instance
        collector = SMABreadthHourlyCollector()
        
        # Collect 30 days of hourly data
        logger.info("Collecting 30 days of hourly SMA breadth data...")
        logger.info("This may take several minutes depending on the number of tickers...")
        
        hourly_breadth = collector.collect_hourly_data(days=30)
        
        if hourly_breadth:
            logger.info("=" * 60)
            logger.info("✅ COLLECTION SUCCESSFUL!")
            logger.info("=" * 60)
            logger.info(f"Total data points collected: {len(hourly_breadth)}")
            logger.info(f"Date range: {hourly_breadth[0]['datetime']} to {hourly_breadth[-1]['datetime']}")
            
            # Display sample data
            logger.info("\nSample of recent data points:")
            for point in hourly_breadth[-5:]:
                logger.info(f"  {point['datetime']} - SMA20: {point['sma20_breadth']:.1f}%, "
                          f"SMA50: {point['sma50_breadth']:.1f}%, "
                          f"Volume: {point['volume_breadth']:.1f}%")
            
            logger.info("\n✅ Hourly data is now available for the dashboard!")
            logger.info("Navigate to http://localhost:8080 to see the hourly charts")
            
        else:
            logger.error("❌ Failed to collect hourly data")
            logger.error("Please check the logs for errors and ensure:")
            logger.error("1. Zerodha API credentials are configured in config.ini")
            logger.error("2. Market data access is available")
            logger.error("3. Internet connection is stable")
            
    except Exception as e:
        logger.error(f"❌ Error during collection: {e}")
        logger.error("Please check the configuration and try again")
    
    finally:
        logger.info(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()