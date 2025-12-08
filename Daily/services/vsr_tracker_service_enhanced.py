#!/usr/bin/env python
"""
Enhanced VSR Tracker Service with 3-Day Ticker Persistence
Tracks tickers from Long_Reversal_Daily + historical tickers with momentum
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
    interval_mapping,
    calculate_liquidity_metrics
)

# Import persistence manager
from services.vsr_ticker_persistence import VSRTickerPersistence, merge_ticker_lists

# Import liquidity cache
from services.liquidity_cache import LiquidityCache

class EnhancedVSRTracker:
    """Enhanced VSR tracker with 3-day ticker persistence"""
    
    def __init__(self, user_name='Sai'):
        self.user_name = user_name
        self.data_cache = DataCache()
        self.persistence_manager = VSRTickerPersistence()
        self.liquidity_cache = LiquidityCache(ttl_hours=1)  # Cache liquidity for 1 hour
        self.last_ticker_file = None
        self.last_file_check_time = None
        self.file_check_interval = 300  # Check for new files every 5 minutes
        
        # Setup logging
        self.setup_logging()
        
        # Load config
        self.config = load_daily_config(user_name)
        
        # Track results for trending
        self.previous_results = {}
        
        # Track momentum data for persistence
        self.current_momentum_data = {}
        
        self.logger.info(f"Enhanced VSR Tracker initialized for user: {user_name}")
        self.logger.info("3-day ticker persistence enabled")
    
    def setup_logging(self):
        """Set up consolidated logging for all users"""
        # Create consolidated logs directory
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'vsr_tracker')
        os.makedirs(logs_dir, exist_ok=True)
        
        # Daily log file
        today = datetime.datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(logs_dir, f'vsr_tracker_enhanced_{today}.log')
        
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
    
    def get_latest_long_reversal_tickers(self, force_check=False):
        """Get tickers from latest Long_Reversal_Daily file"""
        try:
            # Check if we should look for new files
            now = datetime.datetime.now()
            should_check_files = force_check or (
                self.last_file_check_time is None or 
                (now - self.last_file_check_time).total_seconds() >= self.file_check_interval
            )
            
            if should_check_files:
                self.logger.info(f"[{self.user_name}] 🔍 Checking for new Long_Reversal_Daily files...")
            
            if not should_check_files and hasattr(self, '_cached_tickers'):
                return self._cached_tickers
            
            results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
            long_reversal_files = glob.glob(os.path.join(results_dir, "Long_Reversal_Daily_*.xlsx"))
            
            if not long_reversal_files:
                self.logger.error("No Long_Reversal_Daily files found")
                return []
            
            # Sort by timestamp (newest first)
            def extract_timestamp(filename):
                try:
                    basename = os.path.basename(filename)
                    timestamp_part = basename.replace("Long_Reversal_Daily_", "").replace(".xlsx", "")
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
            
            long_reversal_files.sort(key=extract_timestamp, reverse=True)
            latest_file = long_reversal_files[0]
            
            # Check if this is a new file
            if latest_file != self.last_ticker_file:
                self.logger.info(f"🆕 New Long_Reversal_Daily file detected: {os.path.basename(latest_file)}")
                self.last_ticker_file = latest_file
                
                # Read the Excel file
                df = pd.read_excel(latest_file)
                if 'ticker' in df.columns:
                    tickers = df['ticker'].tolist()
                elif 'Ticker' in df.columns:
                    tickers = df['Ticker'].tolist()
                else:
                    self.logger.error(f"No ticker column found in {latest_file}")
                    return []
                
                # Check for new tickers
                if hasattr(self, '_cached_tickers'):
                    new_tickers = set(tickers) - set(self._cached_tickers)
                    if new_tickers:
                        self.logger.info(f"✨ New tickers found: {', '.join(sorted(new_tickers))}")
                
                self._cached_tickers = tickers
                self.logger.info(f"[{self.user_name}] Loaded {len(tickers)} tickers from {os.path.basename(latest_file)}")
            else:
                # Same file, return cached tickers
                tickers = self._cached_tickers if hasattr(self, '_cached_tickers') else []
            
            # Update last check time
            self.last_file_check_time = now
            return tickers
            
        except Exception as e:
            self.logger.error(f"Error loading Long_Reversal_Daily tickers: {e}")
            return []
    
    def track_ticker(self, ticker):
        """Track a single ticker and return its VSR data"""
        try:
            now = datetime.datetime.now()
            
            # Fetch hourly data for last 15 days (need 50+ data points for VSR calculation)
            from_date = (now - relativedelta(days=15)).strftime('%Y-%m-%d')
            to_date = now.strftime('%Y-%m-%d')
            
            # Fetch hourly data for VSR calculation
            hourly_data = fetch_data_kite(ticker, 'hour', from_date, to_date)
            
            if hourly_data is None or hourly_data.empty:
                return None
            
            # Calculate VSR indicators on hourly data
            hourly_with_indicators = calculate_vsr_indicators(hourly_data)
            if hourly_with_indicators is None:
                return None
            
            # Get latest hourly bar for VSR metrics
            latest_hourly = hourly_with_indicators.iloc[-1]
            
            # Get current price and volume from minute data
            minute_from = (now - relativedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
            minute_to = now.strftime('%Y-%m-%d %H:%M:%S')
            minute_data = fetch_data_kite(ticker, 'minute', minute_from, minute_to)
            
            if minute_data is not None and not minute_data.empty:
                latest_minute = minute_data.iloc[-1]
                current_price = latest_minute['Close']
                current_volume = latest_minute['Volume']
            else:
                current_price = latest_hourly.get('Close', 0)
                current_volume = latest_hourly.get('Volume', 0)
            
            # Calculate VSR score based on hourly data
            vsr_ratio = latest_hourly.get('VSR_Ratio', 0)
            vsr_roc = latest_hourly.get('VSR_ROC', 0)
            volume_ratio = latest_hourly.get('VolumeRatio', 0)
            momentum_hourly = latest_hourly.get('ROC5', 0)  # 5-hour momentum
            
            # Check for momentum build
            momentum_build = 0
            if len(hourly_with_indicators) >= 3:
                recent_bars = hourly_with_indicators.tail(3)
                vsr_ratios = recent_bars['VSR_Ratio'].values
                if vsr_ratios[-1] > vsr_ratios[-2] > vsr_ratios[-3]:
                    momentum_build = 20  # Strong momentum build
                elif vsr_ratios[-1] > vsr_ratios[-2]:
                    momentum_build = 10  # Moderate momentum build
            
            # Calculate score (0-100)
            score = 0
            
            # Base VSR scoring (based on hourly data)
            if vsr_ratio > 1.0:
                score += 20
            if vsr_ratio > 2.0:
                score += 25
            if vsr_ratio > 3.0:
                score += 15
            if vsr_roc > 50:
                score += 15
            if volume_ratio > 1.5:
                score += 10
            if momentum_hourly > 0:
                score += 5
            
            # Add momentum build bonus
            score += momentum_build
            
            # Calculate price change percentage
            price_change = momentum_hourly
            
            # Check if building
            prev_score = self.previous_results.get(ticker, {}).get('score', 0)
            building = momentum_build > 0
            
            # Determine trend
            if ticker not in self.previous_results:
                trend = "NEW"
            elif score > self.previous_results[ticker]['score']:
                trend = "UP"
            elif score < self.previous_results[ticker]['score']:
                trend = "DOWN"
            else:
                trend = "FLAT"
            
            # Get sector
            sector = get_sector_for_ticker(ticker)
            
            # Check liquidity cache first
            liquidity_metrics = self.liquidity_cache.get(ticker)
            
            if liquidity_metrics is None:
                # Calculate liquidity metrics if not in cache
                self.logger.debug(f"Calculating liquidity for {ticker} (not in cache)")
                liquidity_metrics = calculate_liquidity_metrics(ticker, hourly_with_indicators)
                
                # Cache the result
                if liquidity_metrics:
                    self.liquidity_cache.set(ticker, liquidity_metrics)
            else:
                self.logger.debug(f"Using cached liquidity for {ticker}")
            
            # Store momentum for persistence
            self.current_momentum_data[ticker] = price_change
            
            # Get persistence stats
            persistence_stats = self.persistence_manager.get_ticker_stats(ticker)
            days_tracked = persistence_stats['days_tracked'] if persistence_stats else 0
            occurrences = persistence_stats['appearances'] if persistence_stats else 0
            alerts_last_30_days = persistence_stats.get('alerts_last_30_days', 0) if persistence_stats else 0
            first_seen = persistence_stats['first_seen'] if persistence_stats else None
            penultimate_alert_date = persistence_stats.get('penultimate_alert_date') if persistence_stats else None
            penultimate_alert_price = persistence_stats.get('penultimate_alert_price') if persistence_stats else None

            # Safely extract liquidity data (handle None case)
            if liquidity_metrics:
                liquidity_grade = liquidity_metrics.get('liquidity_grade', 'F')
                liquidity_score = liquidity_metrics.get('liquidity_score', 0)
                avg_turnover_cr = liquidity_metrics.get('avg_daily_turnover_cr', 0)
                liquidity_rank = liquidity_metrics.get('liquidity_rank', 'Low')
            else:
                liquidity_grade = 'F'
                liquidity_score = 0
                avg_turnover_cr = 0
                liquidity_rank = 'Low'
            
            result = {
                'ticker': ticker,
                'score': score,
                'vsr': vsr_ratio,
                'price': current_price,
                'volume': int(current_volume),
                'momentum': price_change,
                'building': building,
                'trend': trend,
                'sector': sector,
                'days_tracked': days_tracked,
                'occurrences': occurrences,
                'alerts_last_30_days': alerts_last_30_days,
                'first_seen': first_seen,
                'penultimate_alert_date': penultimate_alert_date,
                'penultimate_alert_price': penultimate_alert_price,
                'liquidity_grade': liquidity_grade,
                'liquidity_score': liquidity_score,
                'avg_turnover_cr': avg_turnover_cr,
                'liquidity_rank': liquidity_rank,
                'timestamp': datetime.datetime.now()
            }
            
            # Store for next comparison
            self.previous_results[ticker] = result
            
            return result
                
        except Exception as e:
            self.logger.error(f"Error tracking {ticker}: {e}")
            return None
    
    def log_result(self, result):
        """Log a single result in formatted way"""
        if result:
            # Format the output
            ticker_str = f"{result['ticker']:<12}"
            score_str = f"Score: {result['score']:>3}"
            vsr_str = f"VSR: {result['vsr']:>5.2f}"
            price_str = f"Price: ₹{result['price']:<8.2f}"
            volume_str = f"Vol: {result['volume']:>10,}"
            momentum_str = f"Momentum: {result['momentum']:>6.1f}%"
            
            # Building indicator
            build_str = "📈10" if result['building'] else "  0"
            build_str = f"Build: {build_str}"
            
            # Trend indicator
            trend_str = f"Trend: {result['trend']:<4}"

            # Days tracked indicator
            days_str = f"Days: {result['days_tracked']}"

            # Occurrences/Persistence indicator
            occur_str = f"Alerts: {result.get('occurrences', 0)}"

            # Liquidity indicators
            liquidity_str = f"Liq: {result.get('liquidity_grade', 'F')}({result.get('liquidity_score', 0):>2})"
            turnover_str = f"TO: ₹{result.get('avg_turnover_cr', 0):.1f}Cr"
            
            # Sector
            sector_str = f"Sector: {result['sector']}"
            
            # Full log line with liquidity data and occurrences
            log_line = f"[{self.user_name}] {ticker_str} | {score_str} | {vsr_str} | {price_str} | {volume_str} | {momentum_str} | {build_str} | {trend_str} | {days_str} | {occur_str} | {liquidity_str} | {turnover_str} | {sector_str}"

            self.logger.info(log_line)
    
    def run_tracking_cycle(self):
        """Run one complete tracking cycle"""
        try:
            # Clean expired cache entries periodically
            if hasattr(self, '_last_cache_cleanup'):
                if (datetime.datetime.now() - self._last_cache_cleanup).total_seconds() > 3600:
                    expired = self.liquidity_cache.clear_expired()
                    if expired > 0:
                        self.logger.info(f"Cleared {expired} expired liquidity cache entries")
                    self._last_cache_cleanup = datetime.datetime.now()
            else:
                self._last_cache_cleanup = datetime.datetime.now()
            
            # Get current scan tickers (checks for new files every 5 minutes)
            current_tickers = self.get_latest_long_reversal_tickers()
            
            # Update persistence with current tickers (without momentum data yet)
            self.persistence_manager.update_tickers(current_tickers)
            
            # Merge with persistent tickers
            all_tickers = merge_ticker_lists(current_tickers, self.persistence_manager)
            
            # Log persistence summary
            summary = self.persistence_manager.get_persistence_summary()
            self.logger.info(f"[{self.user_name}] Tracking {len(all_tickers)} tickers "
                           f"({len(current_tickers)} from current scan + "
                           f"{len(all_tickers) - len(current_tickers)} from persistence)")
            
            if summary['momentum_leaders']:
                leaders = [f"{t['ticker']} ({t['days']}d)" for t in summary['momentum_leaders'][:5]]
                self.logger.info(f"[{self.user_name}] Momentum leaders: {', '.join(leaders)}")
            
            # Reset momentum and price data
            self.current_momentum_data = {}
            self.current_price_data = {}

            # Track each ticker
            results = []
            for ticker in sorted(all_tickers):
                result = self.track_ticker(ticker)
                if result:
                    results.append(result)
                    self.log_result(result)
                    # Collect price data for persistence
                    self.current_price_data[ticker] = result.get('price', 0)

            # Update persistence with momentum and price data
            if self.current_momentum_data or self.current_price_data:
                self.persistence_manager.update_tickers(
                    list(set(self.current_momentum_data.keys()) | set(self.current_price_data.keys())),
                    self.current_momentum_data,
                    self.current_price_data
                )
            
            # Sort results by score for summary
            results.sort(key=lambda x: x['score'], reverse=True)
            
            # Log top movers
            if results:
                self.logger.info(f"[{self.user_name}] ━━━ Top 5 by Score ━━━")
                for result in results[:5]:
                    self.logger.info(f"[{self.user_name}]   {result['ticker']:<10} Score: {result['score']:>3} | VSR: {result['vsr']:>5.2f} | Days: {result['days_tracked']}")
            
            # Log cache statistics
            cache_stats = self.liquidity_cache.get_stats()
            self.logger.info(f"[{self.user_name}] Liquidity cache: {cache_stats['valid_entries']}/{cache_stats['total_entries']} valid entries (TTL: {cache_stats['ttl_hours']}h)")
            
        except Exception as e:
            self.logger.error(f"Error in tracking cycle: {e}")
    
    def run_continuous(self, interval_seconds=60):
        """Run continuous tracking with specified interval"""
        self.logger.info(f"[{self.user_name}] Enhanced VSR Tracker Service started - Minute-by-minute scoring with 3-day persistence")
        
        while True:
            try:
                # Check if market is open
                now = datetime.datetime.now()
                if now.weekday() < 5 and datetime.time(9, 15) <= now.time() <= datetime.time(15, 30):
                    self.logger.info(f"[{self.user_name}] ━━━ Starting tracking cycle at {now.strftime('%H:%M:%S')} ━━━")
                    self.run_tracking_cycle()
                else:
                    self.logger.info(f"[{self.user_name}] Market closed, waiting...")
                
                # Wait for next cycle
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                self.logger.info(f"[{self.user_name}] Tracker stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in continuous tracking: {e}")
                time.sleep(interval_seconds)


def main():
    parser = argparse.ArgumentParser(description='Enhanced VSR Tracker Service with 3-Day Persistence')
    parser.add_argument('--user', type=str, default='Sai', help='User name for config')
    parser.add_argument('--interval', type=int, default=60, help='Update interval in seconds')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    
    args = parser.parse_args()
    
    # Create tracker
    tracker = EnhancedVSRTracker(user_name=args.user)
    
    if args.once:
        # Run single cycle
        tracker.run_tracking_cycle()
    else:
        # Run continuous
        tracker.run_continuous(interval_seconds=args.interval)


if __name__ == "__main__":
    main()