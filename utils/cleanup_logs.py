#!/usr/bin/env python
"""
cleanup_logs.py

This script archives and rotates log files to maintain a smaller footprint.
It can be run at the end of each trading day to:
1. Archive large log files by compressing and timestamping them
2. Clear current log files for a fresh start
3. Optionally delete archives older than a specified number of days
"""

import os
import sys
import gzip
import shutil
import logging
import argparse
from datetime import datetime, timedelta
import glob

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config

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
    parser = argparse.ArgumentParser(description="Archive and clear log files")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--preserve-days",
        type=int,
        default=7,
        help="Number of days to preserve archived logs (default: 7)"
    )
    parser.add_argument(
        "--archive-dir",
        type=str,
        help="Custom directory for storing archived logs (default: logs/archives)"
    )
    parser.add_argument(
        "--keep-current",
        action="store_true",
        help="Keep current log files intact (don't clear them)"
    )
    return parser.parse_args()

def archive_log_file(log_file, archive_dir, dry_run=False):
    """Archive a log file by compressing it and adding a timestamp"""
    try:
        # Create a timestamped filename for the archive
        basename = os.path.basename(log_file)
        timestamp = datetime.now().strftime("%Y%m%d")
        archive_name = f"{basename}.{timestamp}.gz"
        archive_path = os.path.join(archive_dir, archive_name)
        
        if dry_run:
            logger.info(f"Would compress {log_file} to {archive_path}")
            return True
            
        # Ensure the archive directory exists
        os.makedirs(archive_dir, exist_ok=True)
        
        # Compress the log file
        with open(log_file, 'rb') as f_in:
            with gzip.open(archive_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
                
        logger.info(f"Archived {log_file} to {archive_path}")
        return True
    except Exception as e:
        logger.error(f"Error archiving {log_file}: {e}")
        return False

def clear_log_file(log_file, dry_run=False):
    """Clear a log file while preserving it"""
    try:
        if dry_run:
            logger.info(f"Would clear {log_file}")
            return True
            
        # Open the file in write mode to truncate it
        with open(log_file, 'w') as f:
            # Optionally write a header indicating the file was cleared
            f.write(f"# Log file cleared on {datetime.now().isoformat()}\n")
            
        logger.info(f"Cleared {log_file}")
        return True
    except Exception as e:
        logger.error(f"Error clearing {log_file}: {e}")
        return False

def cleanup_old_archives(archive_dir, days_to_keep, dry_run=False):
    """Clean up archived log files older than the specified number of days"""
    try:
        if not os.path.exists(archive_dir):
            logger.info(f"Archive directory {archive_dir} doesn't exist, nothing to clean up")
            return True
            
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted_count = 0
        
        # Get all archived log files
        for archive_file in glob.glob(os.path.join(archive_dir, "*.gz")):
            # Get the file's modification time
            file_mtime = datetime.fromtimestamp(os.path.getmtime(archive_file))
            
            # If the file is older than the cutoff date, delete it
            if file_mtime < cutoff_date:
                if dry_run:
                    logger.info(f"Would delete old archive: {archive_file} (modified: {file_mtime.isoformat()})")
                else:
                    os.remove(archive_file)
                    logger.info(f"Deleted old archive: {archive_file}")
                deleted_count += 1
                
        logger.info(f"{'Would delete' if dry_run else 'Deleted'} {deleted_count} old archive files")
        return True
    except Exception as e:
        logger.error(f"Error cleaning up old archives: {e}")
        return False

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_args()
    
    # Get configuration
    config = get_config()
    log_dir = config.get('System', 'log_dir')
    
    # Set archive directory
    archive_dir = args.archive_dir if args.archive_dir else os.path.join(log_dir, "archives")
    
    # Show configuration
    logger.info(f"Log directory: {log_dir}")
    logger.info(f"Archive directory: {archive_dir}")
    logger.info(f"Days to preserve archives: {args.preserve_days}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Keep current logs: {args.keep_current}")
    
    # Get all log files
    log_files = glob.glob(os.path.join(log_dir, "*.log"))
    
    if not log_files:
        logger.info(f"No log files found in {log_dir}")
        return
        
    # Process each log file
    for log_file in log_files:
        # Skip directory entries (shouldn't happen with *.log pattern)
        if os.path.isdir(log_file):
            continue
            
        # Check if the file is empty or very small (less than 1KB)
        file_size = os.path.getsize(log_file)
        if file_size < 1024:
            logger.info(f"Skipping small log file: {log_file} ({file_size} bytes)")
            continue
            
        # Archive the log file
        archived = archive_log_file(log_file, archive_dir, args.dry_run)
        
        # Clear the log file if requested and archiving was successful
        if archived and not args.keep_current:
            clear_log_file(log_file, args.dry_run)
    
    # Clean up old archives if configured
    if args.preserve_days > 0:
        cleanup_old_archives(archive_dir, args.preserve_days, args.dry_run)
    
    logger.info("Log cleanup completed")

if __name__ == "__main__":
    main()