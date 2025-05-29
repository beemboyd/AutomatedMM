#!/usr/bin/env python3

import os
import sys
import subprocess
import argparse
import logging
from pathlib import Path

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import trading system modules
from config import get_config

def setup_logging():
    """Configure logging"""
    config = get_config()
    log_dir = config.get('System', 'log_dir')
    log_level = config.get('System', 'log_level')
    
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'service_management.log')
    
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger()

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Manage Gap Strategy LaunchAgent")
    parser.add_argument(
        "action", 
        choices=["install", "uninstall", "start", "stop", "status"],
        help="Action to perform"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Increase output verbosity"
    )
    return parser.parse_args()

def get_plist_paths():
    """Get system and source plist paths"""
    config = get_config()
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    source_plist = os.path.join(project_dir, "plist", "com.indiaTS.gap_strategy.plist")
    target_plist = os.path.expanduser("~/Library/LaunchAgents/com.indiaTS.gap_strategy.plist")
    
    return source_plist, target_plist

def install_service(logger):
    """Install the Gap Strategy service as a LaunchAgent"""
    source_plist, target_plist = get_plist_paths()
    
    # Check if source plist exists
    if not os.path.exists(source_plist):
        logger.error(f"Source plist file not found: {source_plist}")
        return False
    
    # Create LaunchAgents directory if it doesn't exist
    os.makedirs(os.path.dirname(target_plist), exist_ok=True)
    
    # Copy plist file to LaunchAgents directory
    try:
        import shutil
        shutil.copy2(source_plist, target_plist)
        logger.info(f"Copied plist from {source_plist} to {target_plist}")
    except Exception as e:
        logger.error(f"Error copying plist file: {e}")
        return False
    
    # Set permissions
    try:
        os.chmod(target_plist, 0o644)
        logger.info(f"Set permissions on {target_plist}")
    except Exception as e:
        logger.error(f"Error setting permissions: {e}")
        return False
    
    logger.info("Gap Strategy service installed successfully")
    logger.info("Use 'python utils/install_gap_strategy_service.py start' to start the service")
    return True

def uninstall_service(logger):
    """Uninstall the Gap Strategy service"""
    _, target_plist = get_plist_paths()
    
    # Check if service is loaded
    if is_service_running():
        # Unload the service
        try:
            subprocess.run(["launchctl", "unload", target_plist], check=True)
            logger.info("Service unloaded")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error unloading service: {e}")
    
    # Remove plist file
    if os.path.exists(target_plist):
        try:
            os.remove(target_plist)
            logger.info(f"Removed plist file: {target_plist}")
        except Exception as e:
            logger.error(f"Error removing plist file: {e}")
            return False
    else:
        logger.info(f"Plist file not found: {target_plist}")
    
    logger.info("Gap Strategy service uninstalled successfully")
    return True

def start_service(logger):
    """Start the Gap Strategy service"""
    _, target_plist = get_plist_paths()
    
    # Check if plist exists
    if not os.path.exists(target_plist):
        logger.error(f"Plist file not found: {target_plist}")
        logger.error("Please install the service first with 'python utils/install_gap_strategy_service.py install'")
        return False
    
    # Check if service is already running
    if is_service_running():
        logger.info("Service is already running")
        return True
    
    # Load the service
    try:
        subprocess.run(["launchctl", "load", target_plist], check=True)
        logger.info("Service loaded and will run at the scheduled times")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error starting service: {e}")
        return False

def stop_service(logger):
    """Stop the Gap Strategy service"""
    _, target_plist = get_plist_paths()
    
    # Check if plist exists
    if not os.path.exists(target_plist):
        logger.error(f"Plist file not found: {target_plist}")
        return False
    
    # Check if service is running
    if not is_service_running():
        logger.info("Service is not running")
        return True
    
    # Unload the service
    try:
        subprocess.run(["launchctl", "unload", target_plist], check=True)
        logger.info("Service stopped successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error stopping service: {e}")
        return False

def is_service_running():
    """Check if the Gap Strategy service is running"""
    try:
        result = subprocess.run(
            ["launchctl", "list", "com.indiaTS.gap_strategy"], 
            capture_output=True, 
            text=True
        )
        return result.returncode == 0
    except subprocess.CalledProcessError:
        return False

def show_service_status(logger):
    """Show the status of the Gap Strategy service"""
    _, target_plist = get_plist_paths()
    
    # Check if plist exists
    if not os.path.exists(target_plist):
        logger.info(f"Plist file not found: {target_plist}")
        logger.info("Service is not installed")
        return
    
    # Check if service is running
    running = is_service_running()
    
    logger.info(f"Service installed: {os.path.exists(target_plist)}")
    logger.info(f"Service running: {running}")
    
    # Show scheduled run times
    if os.path.exists(target_plist):
        logger.info("Service will run at:")
        logger.info("  - Starting at 9:30 AM on weekdays (Monday-Friday)")
        logger.info("  - Running every 3 minutes until 9:45 AM")

def main():
    """Main entry point"""
    args = parse_args()
    logger = setup_logging()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    if args.action == "install":
        install_service(logger)
    elif args.action == "uninstall":
        uninstall_service(logger)
    elif args.action == "start":
        start_service(logger)
    elif args.action == "stop":
        stop_service(logger)
    elif args.action == "status":
        show_service_status(logger)
    else:
        logger.error(f"Unknown action: {args.action}")

if __name__ == "__main__":
    main()