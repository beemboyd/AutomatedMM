#!/usr/bin/env python3
"""
Daily Update Script for SMA Breadth Data (Both Daily and Hourly)
Runs at 6:30 PM IST every trading day to:
1. Update daily SMA breadth data
2. Update hourly SMA breadth data with latest market hours data
3. Clean up old data files
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import collectors
from sma_breadth_incremental_collector import SimplifiedSMABreadthCollector
from sma_breadth_hourly_collector import SMABreadthHourlyCollector

# Configure logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
Path(log_dir).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{log_dir}/breadth_update_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def is_trading_day():
    """Check if today is a trading day (Monday-Friday)"""
    today = datetime.now()
    # Skip weekends
    if today.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    return True

def update_daily_breadth():
    """Update daily SMA breadth data"""
    logger.info("=" * 60)
    logger.info("UPDATING DAILY SMA BREADTH DATA")
    logger.info("=" * 60)
    
    try:
        # Use the incremental collector for daily updates
        collector = SimplifiedSMABreadthCollector()
        
        # Load existing data
        latest_file = os.path.join(
            collector.data_dir, 
            'sma_breadth_historical_latest.json'
        )
        
        if os.path.exists(latest_file):
            with open(latest_file, 'r') as f:
                existing_data = json.load(f)
            logger.info(f"Loaded {len(existing_data)} existing daily data points")
        else:
            existing_data = []
            logger.info("No existing daily data found, will create new dataset")
        
        # Collect today's data
        logger.info("Collecting today's daily breadth data...")
        new_data = collector.update_daily_breadth()
        
        if new_data:
            # Check if today's data already exists
            today_str = datetime.now().strftime('%Y-%m-%d')
            existing_dates = [d['date'] for d in existing_data]
            
            if today_str in existing_dates:
                # Update existing entry
                for i, d in enumerate(existing_data):
                    if d['date'] == today_str:
                        existing_data[i] = new_data
                        logger.info(f"Updated existing entry for {today_str}")
                        break
            else:
                # Add new entry
                existing_data.append(new_data)
                logger.info(f"Added new entry for {today_str}")
            
            # Sort by date
            existing_data = sorted(existing_data, key=lambda x: x['date'])
            
            # Keep only last 7 months of data
            cutoff_date = (datetime.now() - timedelta(days=210)).strftime('%Y-%m-%d')
            existing_data = [d for d in existing_data if d['date'] >= cutoff_date]
            
            # Save updated data
            with open(latest_file, 'w') as f:
                json.dump(existing_data, f, indent=2)
            
            # Also save timestamped backup
            backup_file = os.path.join(
                collector.data_dir,
                f'sma_breadth_historical_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            )
            with open(backup_file, 'w') as f:
                json.dump(existing_data, f, indent=2)
            
            logger.info(f"✅ Daily breadth data updated successfully")
            logger.info(f"   Total data points: {len(existing_data)}")
            logger.info(f"   Date range: {existing_data[0]['date']} to {existing_data[-1]['date']}")
            
            # Log current values
            current = existing_data[-1]
            logger.info(f"   Current SMA20: {current['sma_breadth']['sma20_percent']:.1f}%")
            logger.info(f"   Current SMA50: {current['sma_breadth']['sma50_percent']:.1f}%")
            
            return True
        else:
            logger.error("Failed to collect today's daily data")
            return False
            
    except Exception as e:
        logger.error(f"Error updating daily breadth: {e}")
        return False

def update_hourly_breadth():
    """Update hourly SMA breadth data"""
    logger.info("=" * 60)
    logger.info("UPDATING HOURLY SMA BREADTH DATA")
    logger.info("=" * 60)
    
    try:
        collector = SMABreadthHourlyCollector()
        
        # Load existing hourly data
        latest_file = os.path.join(
            collector.script_dir,
            'historical_breadth_data',
            'sma_breadth_hourly_latest.json'
        )
        
        existing_data = []
        if os.path.exists(latest_file):
            with open(latest_file, 'r') as f:
                existing_data = json.load(f)
            logger.info(f"Loaded {len(existing_data)} existing hourly data points")
        
        # Collect today's hourly data (last trading day if after hours)
        logger.info("Collecting today's hourly breadth data...")
        
        # Get data for the last 2 days to ensure we have today's complete data
        new_hourly_data = collector.collect_hourly_data(days=2)
        
        if new_hourly_data:
            # Merge with existing data
            existing_dates = set(d['datetime'] for d in existing_data)
            
            # Add only new data points
            added_count = 0
            for point in new_hourly_data:
                if point['datetime'] not in existing_dates:
                    existing_data.append(point)
                    added_count += 1
            
            # Sort by datetime
            existing_data = sorted(existing_data, key=lambda x: x['datetime'])
            
            # Keep only last 30 days of hourly data
            cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            existing_data = [d for d in existing_data if d['datetime'] > cutoff]
            
            # Save updated hourly data
            with open(latest_file, 'w') as f:
                json.dump(existing_data, f, indent=2)
            
            # Also save in hourly_breadth_data folder
            hourly_dir = os.path.join(collector.data_dir, '../hourly_breadth_data')
            Path(hourly_dir).mkdir(parents=True, exist_ok=True)
            
            hourly_latest = os.path.join(hourly_dir, 'sma_breadth_hourly_latest.json')
            with open(hourly_latest, 'w') as f:
                json.dump(existing_data, f, indent=2)
            
            logger.info(f"✅ Hourly breadth data updated successfully")
            logger.info(f"   Added {added_count} new hourly data points")
            logger.info(f"   Total data points: {len(existing_data)}")
            if existing_data:
                logger.info(f"   Date range: {existing_data[0]['datetime']} to {existing_data[-1]['datetime']}")
                
                # Log latest hourly values
                latest = existing_data[-1]
                logger.info(f"   Latest SMA20: {latest['sma20_breadth']:.1f}%")
                logger.info(f"   Latest SMA50: {latest['sma50_breadth']:.1f}%")
                logger.info(f"   Latest Volume: {latest['volume_breadth']:.1f}%")
            
            return True
        else:
            logger.warning("No new hourly data collected")
            return False
            
    except Exception as e:
        logger.error(f"Error updating hourly breadth: {e}")
        return False

def cleanup_old_files():
    """Clean up old data files to save space"""
    logger.info("Cleaning up old data files...")
    
    try:
        data_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'historical_breadth_data'
        )
        
        # Keep only files from last 7 days (except latest files)
        cutoff_date = datetime.now() - timedelta(days=7)
        
        deleted_count = 0
        for file in os.listdir(data_dir):
            if 'latest' in file or not file.startswith('sma_breadth'):
                continue
                
            file_path = os.path.join(data_dir, file)
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            
            if file_time < cutoff_date:
                os.remove(file_path)
                deleted_count += 1
                logger.debug(f"Deleted old file: {file}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old data files")
            
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def main():
    """Main function to run daily updates"""
    start_time = datetime.now()
    logger.info("=" * 70)
    logger.info("STARTING DAILY BREADTH DATA UPDATE")
    logger.info("=" * 70)
    logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S IST')}")
    
    # Check if today is a trading day
    if not is_trading_day():
        logger.info("Today is not a trading day. Skipping update.")
        return
    
    # Check if market has closed (after 3:30 PM)
    current_time = datetime.now()
    market_close = current_time.replace(hour=15, minute=30, second=0, microsecond=0)
    
    if current_time < market_close:
        logger.warning(f"Market is still open (closes at 3:30 PM). Current time: {current_time.strftime('%H:%M')}")
        logger.warning("It's recommended to run this script after market close for complete data.")
    
    success_count = 0
    total_tasks = 3
    
    # Task 1: Update daily breadth data
    logger.info("\n📊 Task 1/3: Updating daily breadth data...")
    if update_daily_breadth():
        success_count += 1
        logger.info("✅ Daily breadth update: SUCCESS")
    else:
        logger.error("❌ Daily breadth update: FAILED")
    
    # Task 2: Update hourly breadth data
    logger.info("\n📈 Task 2/3: Updating hourly breadth data...")
    if update_hourly_breadth():
        success_count += 1
        logger.info("✅ Hourly breadth update: SUCCESS")
    else:
        logger.error("❌ Hourly breadth update: FAILED")
    
    # Task 3: Clean up old files
    logger.info("\n🗑️  Task 3/3: Cleaning up old files...")
    cleanup_old_files()
    success_count += 1
    logger.info("✅ Cleanup: COMPLETE")
    
    # Summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    logger.info("\n" + "=" * 70)
    logger.info("UPDATE SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Tasks completed: {success_count}/{total_tasks}")
    logger.info(f"Duration: {duration.total_seconds():.1f} seconds")
    logger.info(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S IST')}")
    
    if success_count == total_tasks:
        logger.info("\n✅ ALL UPDATES COMPLETED SUCCESSFULLY!")
        logger.info("Dashboard data has been refreshed.")
        logger.info("View at: http://localhost:8080")
    else:
        logger.warning(f"\n⚠️  PARTIAL SUCCESS: {total_tasks - success_count} task(s) failed")
        logger.warning("Check the logs above for error details.")
    
    logger.info("=" * 70)


if __name__ == "__main__":
    main()