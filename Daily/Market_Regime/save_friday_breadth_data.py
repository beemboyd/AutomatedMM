#!/usr/bin/env python3
"""
Save Friday Breadth Data for Weekend Use
This script should be run every Friday at 3:30 PM IST
"""

import os
import sys
import json
import shutil
from datetime import datetime
import pytz
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def save_friday_data():
    """Save current breadth data as Friday cache"""
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        
        # Check if it's Friday
        if now.weekday() != 4:
            logger.warning(f"Today is not Friday (weekday: {now.weekday()}). This script should run on Fridays.")
        
        # Paths
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        historical_dir = os.path.join(base_dir, 'Daily', 'Market_Regime', 'historical_breadth_data')
        
        current_file = os.path.join(historical_dir, 'sma_breadth_historical_latest.json')
        friday_cache = os.path.join(historical_dir, 'sma_breadth_friday_cache.json')
        
        # Check if source exists
        if not os.path.exists(current_file):
            logger.error(f"Source file not found: {current_file}")
            return False
        
        # Copy current data to Friday cache
        shutil.copy2(current_file, friday_cache)
        logger.info(f"Friday data cached successfully at {friday_cache}")
        
        # Also save a timestamped backup
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(historical_dir, f'sma_breadth_friday_{timestamp}.json')
        shutil.copy2(current_file, backup_file)
        logger.info(f"Timestamped backup saved at {backup_file}")
        
        # Add metadata to the Friday cache
        with open(friday_cache, 'r') as f:
            data = json.load(f)
        
        # Add metadata at the beginning of the file
        metadata = {
            'cache_created': now.isoformat(),
            'cache_type': 'friday_eod',
            'original_file': current_file
        }
        
        # If data is a list, wrap it
        if isinstance(data, list):
            cache_data = {
                'metadata': metadata,
                'data': data
            }
        else:
            data['cache_metadata'] = metadata
            cache_data = data
        
        # Save with metadata
        with open(friday_cache, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        logger.info("Friday data cache created with metadata")
        
        # Clean up old backups (keep only last 4 weeks)
        cleanup_old_backups(historical_dir)
        
        return True
        
    except Exception as e:
        logger.error(f"Error saving Friday data: {e}")
        return False

def cleanup_old_backups(historical_dir):
    """Keep only the last 4 Friday backups"""
    try:
        import glob
        
        # Find all Friday backup files
        backup_pattern = os.path.join(historical_dir, 'sma_breadth_friday_*.json')
        backup_files = glob.glob(backup_pattern)
        
        # Sort by modification time
        backup_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        # Keep only the 4 most recent
        if len(backup_files) > 4:
            for old_file in backup_files[4:]:
                os.remove(old_file)
                logger.info(f"Removed old backup: {old_file}")
                
    except Exception as e:
        logger.error(f"Error cleaning up old backups: {e}")

if __name__ == "__main__":
    logger.info("Starting Friday breadth data save process...")
    
    if save_friday_data():
        logger.info("Friday data save completed successfully")
    else:
        logger.error("Friday data save failed")
        sys.exit(1)