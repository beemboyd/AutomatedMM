#!/usr/bin/env python3
"""
Setup log rotation for SL_watchdog logs

This script configures automatic log rotation to prevent log files from growing too large.
"""

import os
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

def setup_rotating_logger(log_file_path, max_bytes=10*1024*1024, backup_count=5):
    """
    Setup a logger with automatic rotation based on file size
    
    Args:
        log_file_path: Path to the log file
        max_bytes: Maximum size of each log file (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Create rotating file handler
    handler = RotatingFileHandler(
        log_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    
    # Set format
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(handler)
    
    # Also add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

def setup_timed_rotating_logger(log_file_path, when='midnight', interval=1, backup_count=7):
    """
    Setup a logger with automatic rotation based on time
    
    Args:
        log_file_path: Path to the log file
        when: When to rotate ('midnight', 'H' for hourly, 'D' for daily)
        interval: Interval for rotation
        backup_count: Number of backup files to keep (default: 7 days)
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Create timed rotating file handler
    handler = TimedRotatingFileHandler(
        log_file_path,
        when=when,
        interval=interval,
        backupCount=backup_count
    )
    
    # Set format
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(handler)
    
    # Also add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# Example usage
if __name__ == "__main__":
    # Size-based rotation example
    logger1 = setup_rotating_logger(
        "test_size_rotation.log",
        max_bytes=1024*1024,  # 1MB
        backup_count=3
    )
    
    # Time-based rotation example
    logger2 = setup_timed_rotating_logger(
        "test_time_rotation.log",
        when='midnight',
        backup_count=7  # Keep 7 days
    )
    
    print("Log rotation setup complete!")
    print("\nSize-based rotation: Rotates when file reaches 1MB, keeps 3 backups")
    print("Time-based rotation: Rotates daily at midnight, keeps 7 days of logs")