#!/usr/bin/env python3
"""
Market Hours Manager for VSR Telegram Service
Ensures the service runs only from 9:00 AM to 3:30 PM IST on weekdays
"""

import os
import sys
import time
import signal
import subprocess
from datetime import datetime, time as dt_time
import pytz
import argparse
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class MarketHoursManager:
    def __init__(self, user_name='Sai'):
        self.user_name = user_name
        self.ist = pytz.timezone('Asia/Kolkata')
        self.market_open = dt_time(9, 0)
        self.market_close = dt_time(15, 30)
        self.service_process = None
        self.running = True
        
        # Setup logging
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'vsr_telegram')
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'market_hours_manager.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        self.stop_service()
        sys.exit(0)
    
    def is_market_hours(self):
        """Check if current time is within market hours"""
        now = datetime.now(self.ist)
        current_time = now.time()
        
        # Check if it's a weekday (Monday=0, Friday=4)
        if now.weekday() > 4:
            return False
        
        # Check if within market hours
        return self.market_open <= current_time <= self.market_close
    
    def start_service(self):
        """Start the VSR Telegram service"""
        if self.service_process is None or self.service_process.poll() is not None:
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vsr_telegram_service_enhanced.py')
            cmd = [sys.executable, script_path, '--user', self.user_name]
            
            self.logger.info(f"Starting VSR Telegram service: {' '.join(cmd)}")
            self.service_process = subprocess.Popen(cmd)
            self.logger.info(f"Service started with PID: {self.service_process.pid}")
    
    def stop_service(self):
        """Stop the VSR Telegram service"""
        if self.service_process and self.service_process.poll() is None:
            self.logger.info(f"Stopping VSR Telegram service (PID: {self.service_process.pid})")
            self.service_process.terminate()
            
            # Wait for graceful shutdown
            try:
                self.service_process.wait(timeout=10)
                self.logger.info("Service stopped gracefully")
            except subprocess.TimeoutExpired:
                self.logger.warning("Service didn't stop gracefully, forcing kill")
                self.service_process.kill()
                self.service_process.wait()
            
            self.service_process = None
    
    def run(self):
        """Main loop to manage service based on market hours"""
        self.logger.info("Market Hours Manager started")
        self.logger.info(f"Market hours: {self.market_open} - {self.market_close} IST")
        
        while self.running:
            try:
                if self.is_market_hours():
                    # Market is open
                    if self.service_process is None or self.service_process.poll() is not None:
                        self.start_service()
                else:
                    # Market is closed
                    if self.service_process and self.service_process.poll() is None:
                        self.logger.info("Market hours ended, stopping service")
                        self.stop_service()
                
                # Check every 30 seconds
                time.sleep(30)
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(30)
        
        # Ensure service is stopped when manager exits
        self.stop_service()
        self.logger.info("Market Hours Manager stopped")

def main():
    parser = argparse.ArgumentParser(description='Market Hours Manager for VSR Telegram Service')
    parser.add_argument('--user', default='Sai', help='User name for configuration')
    args = parser.parse_args()
    
    manager = MarketHoursManager(user_name=args.user)
    manager.run()

if __name__ == "__main__":
    main()