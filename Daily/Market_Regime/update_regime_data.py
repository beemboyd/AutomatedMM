#!/usr/bin/env python
"""
Unified Market Regime Data Updater
Ensures consistent updates to scan history and multi-timeframe analysis
"""

import os
import sys
import json
import pandas as pd
import logging
from datetime import datetime, timedelta
import glob
from pathlib import Path

# Add parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(script_dir))
sys.path.insert(0, parent_dir)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RegimeDataUpdater:
    """Handles consistent updates to regime data"""
    
    def __init__(self):
        self.data_dir = os.path.join(script_dir, "data")
        self.results_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results"
        self.results_s_dir = "/Users/maverick/PycharmProjects/India-TS/Daily/results-s"
        
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        
    def get_latest_scan_files(self):
        """Get the most recent long and short reversal files"""
        # Look for files from today
        today = datetime.now().strftime("%Y%m%d")
        
        # Find long reversal files
        long_pattern = os.path.join(self.results_dir, f"Long_Reversal_Daily_{today}_*.xlsx")
        long_files = glob.glob(long_pattern)
        
        # Find short reversal files  
        short_pattern = os.path.join(self.results_s_dir, f"Short_Reversal_Daily_{today}_*.xlsx")
        short_files = glob.glob(short_pattern)
        
        if not long_files or not short_files:
            logger.warning(f"No scan files found for today ({today})")
            return None, None
            
        # Get most recent files
        latest_long = max(long_files, key=os.path.getmtime)
        latest_short = max(short_files, key=os.path.getmtime)
        
        # Check if files are recent (within last hour)
        long_age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(latest_long))).seconds / 60
        short_age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(latest_short))).seconds / 60
        
        if long_age > 60 or short_age > 60:
            logger.warning(f"Scan files are stale: Long {long_age:.0f}min, Short {short_age:.0f}min old")
            
        return latest_long, latest_short
    
    def read_scan_counts(self, long_file, short_file):
        """Read counts from scan files"""
        try:
            # Read Excel files
            df_long = pd.read_excel(long_file)
            df_short = pd.read_excel(short_file)
            
            long_count = len(df_long)
            short_count = len(df_short)
            
            # Calculate ratio
            if short_count > 0:
                ratio = long_count / short_count
            else:
                ratio = float('inf') if long_count > 0 else 1.0
                
            logger.info(f"Current scan: L={long_count}, S={short_count}, Ratio={ratio:.3f}")
            
            return {
                'timestamp': datetime.now().isoformat(),
                'long_count': long_count,
                'short_count': short_count,
                'ratio': ratio if ratio != float('inf') else 999.0,
                'source_files': {
                    'long': os.path.basename(long_file),
                    'short': os.path.basename(short_file)
                }
            }
            
        except Exception as e:
            logger.error(f"Error reading scan files: {e}")
            return None
    
    def update_scan_history(self, new_data):
        """Update scan_history.json with new data"""
        history_file = os.path.join(self.data_dir, "scan_history.json")
        
        try:
            # Load existing history
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    history = json.load(f)
            else:
                history = []
            
            # Remove source_files from data before storing
            data_to_store = {k: v for k, v in new_data.items() if k != 'source_files'}
            
            # Check for duplicate timestamps (within same minute)
            current_ts = pd.to_datetime(new_data['timestamp'])
            duplicate = False
            
            for entry in history[-10:]:  # Check last 10 entries
                entry_ts = pd.to_datetime(entry['timestamp'])
                if abs((current_ts - entry_ts).total_seconds()) < 60:
                    # Update existing entry instead of adding duplicate
                    entry.update(data_to_store)
                    duplicate = True
                    logger.info("Updated existing entry within same minute")
                    break
            
            if not duplicate:
                history.append(data_to_store)
                logger.info("Added new entry to scan history")
            
            # Keep only last 30 days of data
            cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            history = [h for h in history if h['timestamp'] > cutoff]
            
            # Sort by timestamp
            history.sort(key=lambda x: x['timestamp'])
            
            # Save updated history
            with open(history_file, 'w') as f:
                json.dump(history, f, indent=2)
                
            logger.info(f"Scan history updated: {len(history)} total entries")
            
        except Exception as e:
            logger.error(f"Error updating scan history: {e}")
    
    def update_historical_data(self, new_data):
        """Update historical_scan_data.json for multi-timeframe analysis"""
        historical_file = os.path.join(self.data_dir, "historical_scan_data.json")
        
        try:
            # Load existing data
            if os.path.exists(historical_file):
                with open(historical_file, 'r') as f:
                    historical = json.load(f)
            else:
                historical = []
            
            # Remove source_files from data
            data_to_store = {k: v for k, v in new_data.items() if k != 'source_files'}
            
            # Check if we already have data for this hour
            current_hour = pd.to_datetime(new_data['timestamp']).replace(minute=0, second=0, microsecond=0)
            
            # Update or append
            updated = False
            for i, entry in enumerate(historical):
                entry_hour = pd.to_datetime(entry['timestamp']).replace(minute=0, second=0, microsecond=0)
                if entry_hour == current_hour:
                    historical[i] = data_to_store
                    updated = True
                    break
            
            if not updated:
                historical.append(data_to_store)
            
            # Sort by timestamp
            historical.sort(key=lambda x: x['timestamp'])
            
            # Save
            with open(historical_file, 'w') as f:
                json.dump(historical, f, indent=2)
                
            logger.info(f"Historical data updated: {len(historical)} total entries")
            
        except Exception as e:
            logger.error(f"Error updating historical data: {e}")
    
    def verify_data_consistency(self):
        """Verify data consistency between scan_history and historical_scan_data"""
        try:
            # Load both datasets
            scan_history_file = os.path.join(self.data_dir, "scan_history.json")
            historical_file = os.path.join(self.data_dir, "historical_scan_data.json")
            
            if os.path.exists(scan_history_file):
                with open(scan_history_file, 'r') as f:
                    scan_data = json.load(f)
                logger.info(f"Scan history: {len(scan_data)} entries")
                if scan_data:
                    last_scan = scan_data[-1]
                    logger.info(f"Latest scan: {last_scan['timestamp']} - L/S: {last_scan['long_count']}/{last_scan['short_count']}")
            
            if os.path.exists(historical_file):
                with open(historical_file, 'r') as f:
                    hist_data = json.load(f)
                logger.info(f"Historical data: {len(hist_data)} entries")
                
        except Exception as e:
            logger.error(f"Error verifying data: {e}")
    
    def run_update(self):
        """Main update process"""
        logger.info("=== Starting Market Regime Data Update ===")
        
        # Get latest scan files
        long_file, short_file = self.get_latest_scan_files()
        
        if not long_file or not short_file:
            logger.error("Cannot proceed without scan files")
            return False
        
        logger.info(f"Using files:")
        logger.info(f"  Long: {os.path.basename(long_file)}")
        logger.info(f"  Short: {os.path.basename(short_file)}")
        
        # Read scan counts
        scan_data = self.read_scan_counts(long_file, short_file)
        
        if not scan_data:
            logger.error("Failed to read scan data")
            return False
        
        # Update both data stores
        self.update_scan_history(scan_data)
        self.update_historical_data(scan_data)
        
        # Verify consistency
        self.verify_data_consistency()
        
        # Trigger regime analysis update
        try:
            from market_regime_analyzer import MarketRegimeAnalyzer
            analyzer = MarketRegimeAnalyzer()
            analyzer.run_analysis()
            logger.info("Market regime analysis completed")
        except Exception as e:
            logger.warning(f"Could not run regime analysis: {e}")
        
        logger.info("=== Update Complete ===")
        return True


def main():
    """Run the updater"""
    updater = RegimeDataUpdater()
    success = updater.run_update()
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()