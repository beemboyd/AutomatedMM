#!/usr/bin/env python
"""
Hourly Tracker Service for Long Reversal Hourly
Tracks tickers from Long_Reversal_Hourly scanner outputs
Based on VSR tracker but for hourly data without Telegram notifications
"""

import os
import sys
import time
import logging
import datetime
from datetime import timedelta
import json
import glob
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from dateutil.relativedelta import relativedelta

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set flag to prevent VSR_Momentum_Scanner from executing its argparse
os.environ['VSR_MONITOR_SERVICE'] = '1'

# Import required modules
from scanners.VSR_Momentum_Scanner import (
    load_daily_config,
    calculate_vsr_indicators,
    detect_vsr_momentum,
    get_sector_for_ticker,
    DataCache,
    fetch_data_kite,
    interval_mapping
)

class HourlyTracker:
    """Hourly tracker for Long Reversal Hourly scanner results"""
    
    def __init__(self, user_name='Sai'):
        self.user_name = user_name
        self.data_cache = DataCache()
        self.last_ticker_file = None
        self.last_file_check_time = None
        self.file_check_interval = 300  # Check for new files every 5 minutes
        
        # Setup logging
        self.setup_logging()
        
        # Load config
        self.config = load_daily_config(user_name)
        
        # Track results for trending
        self.previous_results = {}
        
        # Track momentum data
        self.current_momentum_data = {}
        
        self.logger.info(f"Hourly Tracker initialized for user: {user_name}")
        self.logger.info("Monitoring Long_Reversal_Hourly scanner results")
    
    def setup_logging(self):
        """Set up logging for hourly tracker"""
        # Create logs directory
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'hourly_tracker')
        os.makedirs(logs_dir, exist_ok=True)
        
        # Daily log file
        today = datetime.datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(logs_dir, f'hourly_tracker_{today}.log')
        
        # Configure logging
        # Remove any existing handlers to avoid duplicates
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
            
        # Create file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Configure root logger
        logging.root.setLevel(logging.INFO)
        logging.root.addHandler(file_handler)
        logging.root.addHandler(console_handler)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Logging to: {log_file}")
    
    def get_latest_hourly_reversal_tickers(self, force_check=False):
        """Get tickers from latest Long_Reversal_Hourly file"""
        try:
            # Check if we should look for new files
            now = datetime.datetime.now()
            should_check_files = force_check or (
                self.last_file_check_time is None or 
                (now - self.last_file_check_time).total_seconds() >= self.file_check_interval
            )
            
            if should_check_files:
                self.logger.info(f"[{self.user_name}] 🔍 Checking for new Long_Reversal_Hourly files...")
            
            if not should_check_files and hasattr(self, '_cached_tickers'):
                return self._cached_tickers
            
            results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results-h")
            hourly_reversal_files = glob.glob(os.path.join(results_dir, "Long_Reversal_Hourly_*.xlsx"))
            
            if not hourly_reversal_files:
                self.logger.error("No Long_Reversal_Hourly files found")
                return []
            
            # Sort by timestamp (newest first)
            def extract_timestamp(filename):
                try:
                    basename = os.path.basename(filename)
                    timestamp_part = basename.replace("Long_Reversal_Hourly_", "").replace(".xlsx", "")
                    parts = timestamp_part.split("_")
                    if len(parts) == 2:
                        date_part, time_part = parts
                        year = int(date_part[:4])
                        month = int(date_part[4:6])
                        day = int(date_part[6:8])
                        hour = int(time_part[:2])
                        minute = int(time_part[2:4])
                        second = int(time_part[4:6])
                        return datetime.datetime(year, month, day, hour, minute, second)
                except:
                    pass
                return datetime.datetime.min
            
            hourly_reversal_files.sort(key=extract_timestamp, reverse=True)
            latest_file = hourly_reversal_files[0]
            
            # Check if this is a new file
            if latest_file != self.last_ticker_file:
                self.logger.info(f"🆕 New Long_Reversal_Hourly file detected: {os.path.basename(latest_file)}")
                self.last_ticker_file = latest_file
                
                # Clear cache to force reload
                if hasattr(self, '_cached_tickers'):
                    del self._cached_tickers
            
            # Load tickers from the latest file
            try:
                df = pd.read_excel(latest_file)
                if 'Ticker' in df.columns:
                    tickers = df['Ticker'].tolist()
                    self._cached_tickers = tickers
                    self.last_file_check_time = now
                    
                    # Log new tickers if file changed
                    if latest_file != self.last_ticker_file or not hasattr(self, '_last_logged_tickers'):
                        self.logger.info(f"✨ Loaded {len(tickers)} tickers from {os.path.basename(latest_file)}")
                        if len(tickers) > 0:
                            self.logger.info(f"Tickers: {', '.join(tickers[:10])}{'...' if len(tickers) > 10 else ''}")
                        self._last_logged_tickers = set(tickers)
                    
                    return tickers
                else:
                    self.logger.error(f"No 'Ticker' column found in {latest_file}")
                    return []
            except Exception as e:
                self.logger.error(f"Error reading {latest_file}: {e}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting hourly reversal tickers: {e}")
            return []
    
    def track_ticker(self, ticker):
        """Track a single ticker and return its VSR data"""
        try:
            now = datetime.datetime.now()
            
            # Date range for fetching data
            from_date = (now - timedelta(days=5)).strftime('%Y-%m-%d')
            to_date = now.strftime('%Y-%m-%d')
            
            # Fetch minute data for intraday VSR
            minute_data = fetch_data_kite(ticker, 'minute', from_date, to_date)
            
            if minute_data is None or minute_data.empty:
                return None
            
            # Calculate VSR indicators
            minute_with_indicators = calculate_vsr_indicators(minute_data)
            
            if minute_with_indicators.empty:
                return None
            
            # Detect VSR momentum (this gives us Score and other metrics)
            vsr_results = detect_vsr_momentum(minute_with_indicators)
            
            if not vsr_results:
                return None
            
            # Get the latest result
            latest_result = vsr_results[-1]
            
            # Add sector information
            latest_result['Sector'] = get_sector_for_ticker(ticker)
            
            # Calculate momentum build
            momentum_build = 0
            if self.previous_results.get(ticker):
                prev_momentum = self.previous_results[ticker].get('Momentum_5D', 0)
                curr_momentum = latest_result.get('Momentum_5D', 0)
                if curr_momentum > prev_momentum and curr_momentum > 0:
                    momentum_build = curr_momentum - prev_momentum
            
            latest_result['Momentum_Build'] = momentum_build
            
            # Store for next comparison
            self.previous_results[ticker] = latest_result
            
            return latest_result
            
        except Exception as e:
            self.logger.error(f"Error tracking {ticker}: {e}")
            return None
    
    def run_scan(self):
        """Run a single scan iteration"""
        try:
            self.logger.info("="*80)
            self.logger.info(f"[{self.user_name}] Starting Hourly tracker scan at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Get tickers from latest Long_Reversal_Hourly file
            tickers = self.get_latest_hourly_reversal_tickers()
            
            if not tickers:
                self.logger.warning("No tickers to track")
                return
            
            # Track VSR for each ticker
            results = []
            errors = []
            
            for i, ticker in enumerate(tickers):
                try:
                    self.logger.info(f"[{i+1}/{len(tickers)}] Tracking {ticker}...")
                    vsr_data = self.track_ticker(ticker)
                    
                    if vsr_data:
                        results.append(vsr_data)
                        self.current_momentum_data[ticker] = vsr_data
                        
                        # Log high-scoring opportunities (no Telegram)
                        if vsr_data.get('Score', 0) >= 75 or vsr_data.get('Momentum_5D', 0) >= 5.0:
                            self.logger.info(
                                f"[{self.user_name}] 🎯 {ticker} | "
                                f"Score: {vsr_data.get('Score', 0)} | "
                                f"VSR: {vsr_data.get('VSR_Ratio', 0):.2f} | "
                                f"Price: ₹{vsr_data.get('Last_Price', 0):.2f} | "
                                f"Vol: {vsr_data.get('Volume', 0):,} | "
                                f"Momentum: {vsr_data.get('Momentum_5D', 0):.2f}% | "
                                f"Build: {vsr_data.get('Momentum_Build', 0):.2f} | "
                                f"Trend: {vsr_data.get('Trend_Strength', 'Unknown')} | "
                                f"Sector: {vsr_data.get('Sector', 'Unknown')}"
                            )
                    else:
                        errors.append(ticker)
                        
                except Exception as e:
                    self.logger.error(f"Error tracking {ticker}: {e}")
                    errors.append(ticker)
            
            # Log summary
            if results:
                # Sort by score
                sorted_results = sorted(results, key=lambda x: x.get('Score', 0), reverse=True)
                
                self.logger.info("\n" + "="*80)
                self.logger.info("🎯 TOP HOURLY OPPORTUNITIES")
                self.logger.info("="*80)
                
                for i, ticker_data in enumerate(sorted_results[:10]):
                    self.logger.info(
                        f"{i+1}. [{self.user_name}] {ticker_data['Ticker']} | "
                        f"Score: {ticker_data.get('Score', 0)} | "
                        f"VSR: {ticker_data.get('VSR_Ratio', 0):.2f} | "
                        f"Price: ₹{ticker_data.get('Last_Price', 0):.2f} | "
                        f"Momentum: {ticker_data.get('Momentum_5D', 0):.2f}% | "
                        f"Sector: {ticker_data.get('Sector', 'Unknown')}"
                    )
                
                self.logger.info("="*80)
                self.logger.info(f"✅ Successfully tracked: {len(results)} tickers")
                if errors:
                    self.logger.info(f"❌ Failed to track: {len(errors)} tickers")
                    
                # Save current state for dashboard
                self.save_current_state(results)
            
        except Exception as e:
            self.logger.error(f"Error in scan: {e}")
    
    def save_current_state(self, results):
        """Save current tracking state for dashboard"""
        try:
            state_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'data', 'hourly_tracker_state.json'
            )
            
            state = {
                'timestamp': datetime.datetime.now().isoformat(),
                'user': self.user_name,
                'total_tickers': len(results),
                'results': results,
                'high_score_tickers': [r for r in results if r.get('Score', 0) >= 75],
                'high_momentum_tickers': [r for r in results if r.get('Momentum_5D', 0) >= 5.0],
                'high_vsr_tickers': [r for r in results if r.get('VSR_Ratio', 0) >= 10.0]
            }
            
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")
    
    def run(self, interval_seconds=60):
        """Run the tracker service"""
        self.logger.info(f"Starting Hourly Tracker Service")
        self.logger.info(f"Update interval: {interval_seconds} seconds")
        self.logger.info(f"User: {self.user_name}")
        self.logger.info("Telegram notifications: DISABLED")
        
        while True:
            try:
                # Check if within market hours (extended for pre-market)
                now = datetime.datetime.now()
                market_start = now.replace(hour=8, minute=0, second=0, microsecond=0)
                market_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
                
                if market_start <= now <= market_end:
                    self.run_scan()
                else:
                    self.logger.info(f"Outside market hours (8 AM - 4 PM). Next scan at {market_start}")
                
                # Wait for next iteration
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                self.logger.info("Shutting down Hourly Tracker...")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                time.sleep(interval_seconds)

def main():
    parser = argparse.ArgumentParser(description='Hourly Tracker Service')
    parser.add_argument('--user', type=str, default='Sai', help='User name for config')
    parser.add_argument('--interval', type=int, default=60, help='Update interval in seconds')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    
    args = parser.parse_args()
    
    # Create tracker
    tracker = HourlyTracker(user_name=args.user)
    
    if args.once:
        # Run once and exit
        tracker.run_scan()
    else:
        # Run continuously
        tracker.run(interval_seconds=args.interval)

if __name__ == "__main__":
    main()