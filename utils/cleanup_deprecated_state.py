#!/usr/bin/env python
"""
cleanup_deprecated_state.py

This script cleans up deprecated state files that are no longer needed
after migrating to the single source of truth (trading_state.json).

Files that will be archived:
1. position_data.json
2. gttz_gtt_tracker.json
3. long_positions.txt and short_positions.txt

The existing files will be renamed with .bak extension rather than being deleted.
"""

import os
import sys
import logging
import argparse
import json
from datetime import datetime

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config
from state_manager import get_state_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Clean up deprecated state files")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Don't ask for confirmation before archiving files"
    )
    return parser.parse_args()

def main():
    # Parse command line arguments
    args = parse_args()
    
    # Get data directory
    config = get_config()
    data_dir = config.get('System', 'data_dir')
    
    # Get state manager
    state_manager = get_state_manager()
    
    # Ensure state is loaded
    positions = state_manager.get_all_positions()
    gtts = state_manager.get_all_gtts()
    
    logger.info(f"Current state contains {len(positions)} positions and {len(gtts)} GTT orders.")
    
    # Files to archive
    deprecated_files = [
        os.path.join(data_dir, "position_data.json"),
        os.path.join(data_dir, "gttz_gtt_tracker.json"),
        os.path.join(data_dir, "long_positions.txt"),
        os.path.join(data_dir, "short_positions.txt")
    ]
    
    # If --dry-run flag is used, just show what would be done
    if args.dry_run:
        logger.info("DRY RUN MODE: No files will be modified.")
        
    # Check for existence of each file and rename it
    for file_path in deprecated_files:
        if os.path.exists(file_path):
            backup_path = f"{file_path}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            if args.dry_run:
                logger.info(f"Would rename {file_path} to {backup_path}")
                continue
                
            if not args.force:
                # Ask for confirmation
                response = input(f"Archive {file_path} to {backup_path}? (y/n): ")
                if response.lower() != 'y':
                    logger.info(f"Skipping {file_path}")
                    continue
            
            # Rename the file
            try:
                os.rename(file_path, backup_path)
                logger.info(f"Renamed {file_path} to {backup_path}")
            except Exception as e:
                logger.error(f"Error renaming {file_path}: {e}")
        else:
            logger.info(f"File {file_path} does not exist, skipping.")
    
    # Provide help for recovery if needed
    if not args.dry_run:
        logger.info("\nFiles have been renamed with .bak extension. If you need to restore them:")
        logger.info("1. First try running the system without the backed up files.")
        logger.info("2. If issues occur, rename the files back by removing the .bak extension.")
    
    logger.info("\nCleanup complete. The system now uses trading_state.json as single source of truth.")

if __name__ == "__main__":
    main()