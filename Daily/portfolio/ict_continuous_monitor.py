#!/usr/bin/env python3
"""
ICT Continuous Monitor - Runs ICT analysis every 5 minutes during market hours
Automatically detects position changes and updates stop loss recommendations
"""

import os
import sys
import time
import json
import datetime
import logging
from typing import Set, Dict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from portfolio.SL_Watch_ICT import ICTAnalyzer

class ICTContinuousMonitor:
    """Continuous monitoring of positions with ICT analysis"""
    
    def __init__(self, user_name: str = 'Sai', update_interval: int = 300):
        """
        Initialize continuous monitor
        Args:
            user_name: Kite user name
            update_interval: Update interval in seconds (default 5 minutes)
        """
        self.user_name = user_name
        self.update_interval = update_interval
        self.previous_positions = set()
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                              'logs', 'ict_analysis')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, 
                               f'continuous_monitor_{datetime.date.today().strftime("%Y%m%d")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def is_market_hours(self) -> bool:
        """Check if current time is within market hours"""
        now = datetime.datetime.now()
        current_time = now.hour * 100 + now.minute
        
        # Market hours: 9:15 AM to 3:30 PM
        return 915 <= current_time <= 1530
    
    def get_current_positions(self) -> Set[str]:
        """Get current position tickers"""
        try:
            analyzer = ICTAnalyzer(self.user_name)
            positions = analyzer.get_all_positions(include_mis=True, include_holdings=True)
            return set(p['ticker'] for p in positions)
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return set()
    
    def detect_position_changes(self, current_positions: Set[str]) -> Dict[str, Set[str]]:
        """Detect position changes"""
        changes = {
            'added': current_positions - self.previous_positions,
            'removed': self.previous_positions - current_positions,
            'unchanged': current_positions & self.previous_positions
        }
        return changes
    
    def run_analysis(self):
        """Run ICT analysis and update dashboard data"""
        try:
            self.logger.info("Starting ICT analysis...")
            
            # Create analyzer instance
            analyzer = ICTAnalyzer(self.user_name)
            
            # Run full analysis
            analyzer.run(include_mis=True)
            
            # Get current positions
            current_positions = self.get_current_positions()
            
            # Detect changes
            changes = self.detect_position_changes(current_positions)
            
            # Log changes
            if changes['added']:
                self.logger.info(f"📈 New positions detected: {', '.join(changes['added'])}")
            
            if changes['removed']:
                self.logger.info(f"📉 Positions closed: {', '.join(changes['removed'])}")
            
            if not changes['added'] and not changes['removed']:
                self.logger.info(f"No position changes. Monitoring {len(current_positions)} positions")
            
            # Update previous positions
            self.previous_positions = current_positions
            
            # Save update timestamp
            self.save_update_status(current_positions)
            
            self.logger.info("Analysis completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during analysis: {e}")
            return False
    
    def save_update_status(self, positions: Set[str]):
        """Save update status for dashboard"""
        status_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'portfolio', 'ict_analysis', 'monitor_status.json'
        )
        
        os.makedirs(os.path.dirname(status_file), exist_ok=True)
        
        status = {
            'last_update': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_positions': len(positions),
            'positions': list(positions),
            'update_interval': self.update_interval,
            'is_market_hours': self.is_market_hours()
        }
        
        with open(status_file, 'w') as f:
            json.dump(status, f, indent=2)
    
    def run(self):
        """Main continuous monitoring loop"""
        self.logger.info("="*60)
        self.logger.info("ICT Continuous Monitor Started")
        self.logger.info(f"Update Interval: {self.update_interval} seconds")
        self.logger.info("="*60)
        
        # Initial analysis
        if self.is_market_hours():
            self.run_analysis()
        
        # Continuous monitoring loop
        while True:
            try:
                # Wait for next update
                time.sleep(self.update_interval)
                
                # Check market hours
                if not self.is_market_hours():
                    self.logger.debug("Outside market hours, waiting...")
                    continue
                
                # Run analysis
                self.logger.info(f"\n{'='*40}")
                self.logger.info(f"Update at {datetime.datetime.now().strftime('%H:%M:%S')}")
                self.logger.info("="*40)
                
                self.run_analysis()
                
            except KeyboardInterrupt:
                self.logger.info("\nMonitor stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                time.sleep(60)  # Wait a minute before retrying

def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ICT Continuous Position Monitor')
    parser.add_argument('--user', '-u', type=str, default='Sai',
                       help='User name for Kite connection')
    parser.add_argument('--interval', '-i', type=int, default=300,
                       help='Update interval in seconds (default: 300)')
    
    args = parser.parse_args()
    
    # Create and run monitor
    monitor = ICTContinuousMonitor(
        user_name=args.user,
        update_interval=args.interval
    )
    
    monitor.run()

if __name__ == "__main__":
    main()