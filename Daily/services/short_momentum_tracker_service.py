#!/usr/bin/env python
"""
Short Momentum Tracker Service
Tracks tickers from Short_Reversal_Daily scanner outputs from past 3 days
Identifies and persists tickers showing negative momentum
Follows the same pattern as VSR Enhanced Tracker
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

class ShortMomentumTracker:
    """Tracks short-side momentum for tickers from past 3 days"""
    
    def __init__(self, user_name='Sai'):
        self.user_name = user_name
        self.data_cache = DataCache()
        self.persistence_days = 3
        self.last_ticker_files = []
        self.last_file_check_time = None
        self.file_check_interval = 300  # Check for new files every 5 minutes
        
        # Setup logging
        self.setup_logging()
        
        # Load config
        self.config = load_daily_config(user_name)
        
        # Track results
        self.tracked_tickers = {}
        self.momentum_data = {}
        self.current_momentum_data = {}
        
        # Output paths
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'short_momentum')
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.logger.info(f"Short Momentum Tracker initialized for user: {user_name}")
        self.logger.info(f"Tracking tickers from past {self.persistence_days} days")
    
    def setup_logging(self):
        """Set up logging"""
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'short_momentum')
        os.makedirs(logs_dir, exist_ok=True)
        
        today = datetime.datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(logs_dir, f'short_momentum_tracker_{today}.log')
        
        # Remove existing handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
            
        # Create handlers
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
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
    
    def get_short_reversal_tickers(self, force_check=False):
        """Get unique tickers from Short_Reversal_Daily files from past 3 days"""
        try:
            # Check if we should look for new files
            now = datetime.datetime.now()
            should_check_files = force_check or (
                self.last_file_check_time is None or 
                (now - self.last_file_check_time).total_seconds() >= self.file_check_interval
            )
            
            if should_check_files:
                self.logger.info(f"[{self.user_name}] 🔍 Checking for Short_Reversal_Daily files from past {self.persistence_days} days...")
            
            if not should_check_files and hasattr(self, '_cached_tickers'):
                return self._cached_tickers, self._cached_ticker_data
            
            # Get files for past N days
            results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results-s')
            all_tickers = set()
            ticker_data = {}
            files_found = []
            
            for i in range(self.persistence_days):
                date = datetime.datetime.now() - timedelta(days=i)
                date_str = date.strftime("%Y%m%d")
                pattern = os.path.join(results_dir, f'Short_Reversal_Daily_{date_str}_*.xlsx')
                daily_files = glob.glob(pattern)
                files_found.extend(daily_files)
            
            if not files_found:
                self.logger.warning("No Short_Reversal_Daily files found in the past 3 days")
                return [], {}
            
            # Sort files by timestamp (newest first)
            def extract_timestamp(filename):
                try:
                    basename = os.path.basename(filename)
                    timestamp_part = basename.replace("Short_Reversal_Daily_", "").replace(".xlsx", "")
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
            
            files_found.sort(key=extract_timestamp, reverse=True)
            
            # Check for new files
            current_file_set = set(files_found)
            last_file_set = set(self.last_ticker_files)
            new_files = current_file_set - last_file_set
            
            if new_files:
                self.logger.info(f"🆕 New Short_Reversal_Daily files detected: {len(new_files)} new files")
                for f in sorted(new_files):
                    self.logger.info(f"  - {os.path.basename(f)}")
            
            # Load tickers from all files
            for file in files_found:
                try:
                    df = pd.read_excel(file)
                    if 'ticker' in df.columns:
                        ticker_col = 'ticker'
                    elif 'Ticker' in df.columns:
                        ticker_col = 'Ticker'
                    else:
                        self.logger.error(f"No ticker column found in {file}")
                        continue
                    
                    for _, row in df.iterrows():
                        ticker = row[ticker_col]
                        all_tickers.add(ticker)
                        
                        # Store ticker data
                        if ticker not in ticker_data:
                            ticker_data[ticker] = {
                                'first_seen': file,
                                'last_seen': file,
                                'appearances': 1,
                                'latest_score': row.get('Score', 0),
                                'files': [file]
                            }
                        else:
                            ticker_data[ticker]['last_seen'] = file
                            ticker_data[ticker]['appearances'] += 1
                            ticker_data[ticker]['latest_score'] = row.get('Score', 0)
                            ticker_data[ticker]['files'].append(file)
                
                except Exception as e:
                    self.logger.error(f"Error loading {file}: {str(e)}")
            
            # Update cache
            self._cached_tickers = list(all_tickers)
            self._cached_ticker_data = ticker_data
            self.last_ticker_files = files_found
            self.last_file_check_time = now
            
            self.logger.info(f"[{self.user_name}] Loaded {len(all_tickers)} unique tickers from {len(files_found)} files")
            
            # Log summary by day
            for i in range(self.persistence_days):
                date = datetime.datetime.now() - timedelta(days=i)
                date_str = date.strftime("%Y-%m-%d")
                day_files = [f for f in files_found if date.strftime("%Y%m%d") in f]
                if day_files:
                    self.logger.info(f"  {date_str}: {len(day_files)} files")
            
            return self._cached_tickers, self._cached_ticker_data
            
        except Exception as e:
            self.logger.error(f"Error loading Short_Reversal_Daily tickers: {e}")
            return [], {}
    
    def track_ticker(self, ticker):
        """Track a single ticker and return its short momentum data"""
        try:
            now = datetime.datetime.now()
            
            # Date range for fetching data
            from_date = (now - timedelta(days=5)).strftime('%Y-%m-%d')
            to_date = now.strftime('%Y-%m-%d')
            
            # Fetch minute data for intraday momentum
            minute_data = fetch_data_kite(ticker, 'minute', from_date, to_date)
            
            if minute_data is None or minute_data.empty:
                return None
            
            # Calculate indicators
            minute_with_indicators = calculate_vsr_indicators(minute_data)
            
            if minute_with_indicators.empty:
                return None
            
            # Get latest values
            latest = minute_with_indicators.iloc[-1]
            
            # Calculate price changes
            price_change_1h = 0
            price_change_3h = 0
            price_change_1d = 0
            
            if len(minute_with_indicators) > 60:
                price_change_1h = ((latest['Close'] - minute_with_indicators.iloc[-61]['Close']) / 
                                  minute_with_indicators.iloc[-61]['Close'] * 100)
            
            if len(minute_with_indicators) > 180:
                price_change_3h = ((latest['Close'] - minute_with_indicators.iloc[-181]['Close']) / 
                                  minute_with_indicators.iloc[-181]['Close'] * 100)
            
            # Fetch daily data for 1-day change
            daily_data = fetch_data_kite(ticker, 'day', from_date, to_date)
            if daily_data is not None and len(daily_data) >= 2:
                price_change_1d = ((daily_data.iloc[-1]['Close'] - daily_data.iloc[-2]['Close']) / 
                                  daily_data.iloc[-2]['Close'] * 100)
            
            # Build momentum data
            momentum_data = {
                'ticker': ticker,
                'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
                'close': float(latest['Close']),
                'volume': int(latest['Volume']),
                'vsr': float(latest.get('VSR_Ratio', 0)),
                'price_change_1h': round(price_change_1h, 2),
                'price_change_3h': round(price_change_3h, 2),
                'price_change_1d': round(price_change_1d, 2),
                'rsi': float(latest.get('RSI', 50)),
                'bb_position': float((latest['Close'] - latest.get('BB_Lower', latest['Close'])) / 
                                   (latest.get('BB_Upper', latest['Close']) - latest.get('BB_Lower', latest['Close'])) 
                                   if latest.get('BB_Upper', latest['Close']) != latest.get('BB_Lower', latest['Close']) else 0.5),
                'atr': float(latest.get('ATR', 0)),
                'sector': get_sector_for_ticker(ticker),
                'volume_ratio': float(latest['Volume'] / minute_with_indicators['Volume'].rolling(20).mean().iloc[-1] 
                                    if len(minute_with_indicators) > 20 else 1)
            }
            
            # Calculate short momentum score (higher score = better short opportunity)
            score = 0
            
            # Price momentum (negative is good)
            if price_change_1h < -0.5:
                score += 20
            if price_change_3h < -1:
                score += 25
            if price_change_1d < -2:
                score += 30
            
            # RSI (lower is better for shorts)
            if momentum_data['rsi'] < 30:
                score += 20
            elif momentum_data['rsi'] < 40:
                score += 10
            
            # Bollinger Band position (lower is better)
            if momentum_data['bb_position'] < 0.2:
                score += 15
            
            # VSR (lower is better for shorts, VSR_Ratio < 1 indicates selling pressure)
            if momentum_data['vsr'] < 0.5:
                score += 20
            elif momentum_data['vsr'] < 0.8:
                score += 10
            
            # Volume spike
            if momentum_data['volume_ratio'] > 1.5:
                score += 10
            
            momentum_data['momentum_score'] = score
            momentum_data['momentum_status'] = self._get_momentum_status(score)
            
            return momentum_data
            
        except Exception as e:
            self.logger.error(f"Error tracking {ticker}: {e}")
            return None
    
    def _get_momentum_status(self, score):
        """Get momentum status based on score"""
        if score >= 80:
            return "Strong Short"
        elif score >= 60:
            return "Short"
        elif score >= 40:
            return "Weak Short"
        elif score >= 20:
            return "Neutral"
        else:
            return "No Signal"
    
    def run_scan(self):
        """Run a single scan iteration"""
        try:
            self.logger.info("=" * 80)
            self.logger.info(f"[{self.user_name}] Starting Short Momentum scan at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Get tickers from past 3 days
            tickers, ticker_data = self.get_short_reversal_tickers()
            
            if not tickers:
                self.logger.warning("No tickers to track")
                return
            
            # Track momentum for each ticker
            results = []
            errors = []
            
            for i, ticker in enumerate(tickers):
                try:
                    self.logger.info(f"[{i+1}/{len(tickers)}] Tracking {ticker}...")
                    momentum = self.track_ticker(ticker)
                    
                    if momentum:
                        # Add persistence data
                        momentum['appearances'] = ticker_data[ticker]['appearances']
                        momentum['persistence_score'] = ticker_data[ticker]['appearances'] * 10
                        momentum['total_score'] = momentum['momentum_score'] + momentum['persistence_score']
                        
                        results.append(momentum)
                        self.current_momentum_data[ticker] = momentum
                    else:
                        errors.append(ticker)
                        
                except Exception as e:
                    self.logger.error(f"Error tracking {ticker}: {e}")
                    errors.append(ticker)
            
            # Save results
            if results:
                self.save_results(results)
                
                # Log summary
                top_shorts = sorted(results, key=lambda x: x['total_score'], reverse=True)[:10]
                
                self.logger.info("\n" + "="*80)
                self.logger.info("🎯 TOP SHORT OPPORTUNITIES")
                self.logger.info("="*80)
                
                for i, ticker_data in enumerate(top_shorts):
                    # Log in VSR-style format for dashboard parsing
                    self.logger.info(
                        f"[{self.user_name}] {ticker_data['ticker']} | "
                        f"Score: {ticker_data['total_score']} | "
                        f"VSR: {ticker_data['vsr']:.2f} | "
                        f"Price: ₹{ticker_data['close']:.2f} | "
                        f"Vol: {ticker_data['volume']:,} | "
                        f"Momentum: {ticker_data['price_change_1d']:.2f}% | "
                        f"Build: {ticker_data['momentum_score']} | "
                        f"Trend: {ticker_data['momentum_status']} | "
                        f"Days: {ticker_data['appearances']} | "
                        f"Sector: {ticker_data['sector']}"
                    )
                
                self.logger.info("="*80)
                self.logger.info(f"✅ Successfully tracked: {len(results)} tickers")
                if errors:
                    self.logger.info(f"❌ Failed to track: {len(errors)} tickers")
            
        except Exception as e:
            self.logger.error(f"Error in scan: {e}")
    
    def save_results(self, results):
        """Save scan results"""
        try:
            timestamp = datetime.datetime.now()
            
            # Save to JSON
            json_data = {
                'timestamp': timestamp.isoformat(),
                'user': self.user_name,
                'tracker_type': 'short_momentum',
                'persistence_days': self.persistence_days,
                'total_tickers': len(results),
                'results': results
            }
            
            # Save timestamped version
            json_file = os.path.join(self.output_dir, 
                                   f"short_momentum_{timestamp.strftime('%Y%m%d_%H%M%S')}.json")
            with open(json_file, 'w') as f:
                json.dump(json_data, f, indent=2)
            
            # Save latest version
            latest_file = os.path.join(self.output_dir, 'latest_short_momentum.json')
            with open(latest_file, 'w') as f:
                json.dump(json_data, f, indent=2)
            
            self.logger.info(f"Saved results to {json_file}")
            
            # Create Excel summary
            self.create_excel_summary(results)
            
        except Exception as e:
            self.logger.error(f"Error saving results: {e}")
    
    def create_excel_summary(self, results):
        """Create Excel summary of results"""
        try:
            df = pd.DataFrame(results)
            
            # Sort by total score
            df = df.sort_values('total_score', ascending=False)
            
            # Select columns for Excel
            columns = ['ticker', 'sector', 'total_score', 'momentum_score', 'persistence_score',
                      'price_change_1h', 'price_change_3h', 'price_change_1d', 
                      'rsi', 'bb_position', 'vsr', 'volume_ratio', 'momentum_status',
                      'appearances', 'close']
            
            df = df[columns]
            
            # Save to Excel
            timestamp = datetime.datetime.now()
            excel_file = os.path.join(self.output_dir, 
                                    f"short_momentum_{timestamp.strftime('%Y%m%d_%H%M%S')}.xlsx")
            
            with pd.ExcelWriter(excel_file, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Short Momentum', index=False)
                
                # Format worksheet
                worksheet = writer.sheets['Short Momentum']
                worksheet.set_column('A:A', 12)  # Ticker
                worksheet.set_column('B:B', 20)  # Sector
                worksheet.set_column('C:O', 12)  # Other columns
            
            # Save latest version
            latest_excel = os.path.join(self.output_dir, 'latest_short_momentum.xlsx')
            df.to_excel(latest_excel, index=False)
            
            self.logger.info(f"Created Excel summary: {excel_file}")
            
        except Exception as e:
            self.logger.error(f"Error creating Excel summary: {e}")
    
    def run(self, interval_seconds=60):
        """Run the tracker service"""
        self.logger.info(f"Starting Short Momentum Tracker Service")
        self.logger.info(f"Update interval: {interval_seconds} seconds")
        self.logger.info(f"User: {self.user_name}")
        
        while True:
            try:
                # Check if within market hours
                now = datetime.datetime.now()
                market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
                market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
                
                if market_start <= now <= market_end:
                    self.run_scan()
                else:
                    self.logger.info(f"Outside market hours. Next scan at {market_start}")
                
                # Wait for next iteration
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                self.logger.info("Shutting down Short Momentum Tracker...")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                time.sleep(interval_seconds)

def main():
    parser = argparse.ArgumentParser(description='Short Momentum Tracker Service')
    parser.add_argument('--user', type=str, default='Sai', help='User name for config')
    parser.add_argument('--interval', type=int, default=60, help='Update interval in seconds')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    
    args = parser.parse_args()
    
    # Create tracker
    tracker = ShortMomentumTracker(user_name=args.user)
    
    if args.once:
        # Run once and exit
        tracker.run_scan()
    else:
        # Run continuously
        tracker.run(interval_seconds=args.interval)

if __name__ == "__main__":
    main()