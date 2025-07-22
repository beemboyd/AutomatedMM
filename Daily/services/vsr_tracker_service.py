#!/usr/bin/env python
"""
VSR Tracker Service - Simplified Version
Continuously tracks all tickers from Long_Reversal_Daily with scores
Logs results for all users in one place with minute-by-minute updates
"""

import os
import sys
import time
import logging
import datetime
import json
import glob
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from dateutil.relativedelta import relativedelta

# Add parent directories to path
# Add Daily to path for imports
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

class VSRTracker:
    """Simplified VSR tracker that logs all ticker results continuously"""
    
    def __init__(self, user_name='Sai'):
        self.user_name = user_name
        self.data_cache = DataCache()
        
        # Setup logging
        self.setup_logging()
        
        # Load config
        self.config = load_daily_config(user_name)
        
        # Track results for trending
        self.previous_results = {}
        
        self.logger.info(f"VSR Tracker initialized for user: {user_name}")
    
    def setup_logging(self):
        """Set up consolidated logging for all users"""
        # Create consolidated logs directory
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'vsr_tracker')
        os.makedirs(logs_dir, exist_ok=True)
        
        # Daily log file
        today = datetime.datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(logs_dir, f'vsr_tracker_{today}.log')
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Logging to: {log_file}")
    
    def get_latest_long_reversal_tickers(self):
        """Get tickers from latest Long_Reversal_Daily file"""
        try:
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
                except Exception:
                    return datetime.datetime.fromtimestamp(os.path.getmtime(filename))
                
                return datetime.datetime.fromtimestamp(os.path.getmtime(filename))
            
            long_reversal_files.sort(key=extract_timestamp, reverse=True)
            latest_file = long_reversal_files[0]
            
            # Read tickers
            df = pd.read_excel(latest_file)
            tickers = df['Ticker'].dropna().tolist()
            
            self.logger.info(f"[{self.user_name}] Loaded {len(tickers)} tickers from {os.path.basename(latest_file)}")
            return tickers, os.path.basename(latest_file)
            
        except Exception as e:
            self.logger.error(f"[{self.user_name}] Error reading Long_Reversal_Daily file: {e}")
            return [], ""
    
    def get_current_price_volume(self, ticker):
        """Get current price and volume for a ticker"""
        try:
            # Get 1-minute data for the last 2 hours to ensure we have recent data
            now = datetime.datetime.now()
            from_date = (now - relativedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
            to_date = now.strftime('%Y-%m-%d %H:%M:%S')
            
            # Fetch 1-minute data - this will now refresh every minute due to cache TTL
            data = fetch_data_kite(ticker, 'minute', from_date, to_date)
            
            if data.empty:
                return None, None
            
            # Get latest values
            latest = data.iloc[-1]
            current_price = latest['Close']
            current_volume = latest['Volume']
            
            return current_price, current_volume
            
        except Exception as e:
            self.logger.debug(f"[{self.user_name}] Error getting price/volume for {ticker}: {e}")
            return None, None
    
    def detect_momentum_build(self, hourly_data):
        """Detect if VSR momentum is building over recent hourly bars"""
        try:
            if len(hourly_data) < 3:
                return 0
            
            # Get last 3 hourly bars
            recent_bars = hourly_data.tail(3)
            vsr_ratios = recent_bars['VSR_Ratio'].values
            
            # Check for increasing VSR over last 3 hours
            if len(vsr_ratios) >= 3:
                if vsr_ratios[-1] > vsr_ratios[-2] > vsr_ratios[-3]:
                    return 20  # Strong momentum build
                elif vsr_ratios[-1] > vsr_ratios[-2]:
                    return 10  # Moderate momentum build
            
            return 0
        except Exception:
            return 0
    
    def analyze_ticker_simple(self, ticker):
        """Enhanced analysis using hourly data for VSR scoring with minute-by-minute updates"""
        try:
            now = datetime.datetime.now()
            
            # Fetch hourly data for last 15 days (need 50+ data points for VSR calculation)
            from_date = (now - relativedelta(days=15)).strftime('%Y-%m-%d')
            to_date = now.strftime('%Y-%m-%d')
            
            # Fetch hourly data for VSR calculation
            hourly_data = fetch_data_kite(ticker, 'hour', from_date, to_date)
            
            if hourly_data.empty:
                return None
            
            # Calculate VSR indicators on hourly data
            hourly_with_indicators = calculate_vsr_indicators(hourly_data)
            if hourly_with_indicators is None:
                return None
            
            # Get latest hourly bar for VSR metrics
            latest_hourly = hourly_with_indicators.iloc[-1]
            
            # Calculate VSR score based on hourly data
            vsr_ratio = latest_hourly.get('VSR_Ratio', 0)
            vsr_roc = latest_hourly.get('VSR_ROC', 0)
            volume_ratio = latest_hourly.get('VolumeRatio', 0)
            momentum_hourly = latest_hourly.get('ROC5', 0)  # 5-hour momentum
            
            # Check for momentum build using recent hourly bars
            momentum_build = self.detect_momentum_build(hourly_with_indicators)
            
            # Enhanced scoring (0-100) based on hourly VSR data
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
            
            # Add momentum build bonus (key for scaling opportunities)
            score += momentum_build
            
            # Get current price and volume
            current_price, current_volume = self.get_current_price_volume(ticker)
            
            result = {
                'ticker': ticker,
                'timestamp': now.isoformat(),
                'score': min(score, 100),
                'vsr_ratio': vsr_ratio,
                'vsr_roc': vsr_roc,
                'volume_ratio': volume_ratio,
                'momentum_hourly': momentum_hourly,
                'momentum_build': momentum_build,
                'current_price': current_price,
                'current_volume': current_volume,
                'close_price': latest_hourly['Close'],
                'sector': get_sector_for_ticker(ticker)
            }
            
            return result
            
        except Exception as e:
            self.logger.debug(f"[{self.user_name}] Error analyzing {ticker}: {e}")
            return None
    
    def format_trend_indicator(self, ticker, current_score, current_price):
        """Format trend indicator showing if score/price is rising/falling"""
        if ticker not in self.previous_results:
            return "NEW"
        
        prev = self.previous_results[ticker]
        
        # Score trend
        score_trend = ""
        if current_score > prev['score']:
            score_trend = "📈"
        elif current_score < prev['score']:
            score_trend = "📉"
        else:
            score_trend = "➡️"
        
        # Price trend
        price_trend = ""
        if current_price and prev['current_price']:
            if current_price > prev['current_price']:
                price_trend = "💹"
            elif current_price < prev['current_price']:
                price_trend = "🔻"
            else:
                price_trend = "➡️"
        
        return f"{score_trend}{price_trend}"
    
    def run_tracking_cycle(self):
        """Run a single tracking cycle"""
        cycle_start = datetime.datetime.now()
        self.logger.info(f"[{self.user_name}] ━━━ Starting tracking cycle at {cycle_start.strftime('%H:%M:%S')} ━━━")
        
        # Get tickers
        tickers, source_file = self.get_latest_long_reversal_tickers()
        if not tickers:
            self.logger.warning(f"[{self.user_name}] No tickers to track")
            return
        
        results = []
        
        for ticker in tickers:
            try:
                result = self.analyze_ticker_simple(ticker)
                
                if result:
                    # Calculate trend
                    trend = self.format_trend_indicator(ticker, result['score'], result['current_price'])
                    
                    # Log the result
                    price_str = f"₹{result['current_price']:.2f}" if result['current_price'] else "N/A"
                    volume_str = f"{result['current_volume']:,}" if result['current_volume'] else "N/A"
                    
                    momentum_build_str = f"📈{result['momentum_build']:2d}" if result['momentum_build'] > 0 else "  0"
                    self.logger.info(f"[{self.user_name}] {ticker:12} | Score: {result['score']:3d} | VSR: {result['vsr_ratio']:5.2f} | "
                                   f"Price: {price_str:8} | Vol: {volume_str:10} | Momentum: {result['momentum_hourly']:6.1f}% | "
                                   f"Build: {momentum_build_str} | Trend: {trend} | Sector: {result['sector']}")
                    
                    results.append(result)
                    
                    # Update previous results
                    self.previous_results[ticker] = result
                
                # Small delay to avoid API rate limits
                time.sleep(0.2)
                
            except Exception as e:
                self.logger.error(f"[{self.user_name}] Error processing {ticker}: {e}")
                continue
        
        # Log summary
        cycle_duration = (datetime.datetime.now() - cycle_start).total_seconds()
        high_scores = [r for r in results if r['score'] >= 50]
        rising_scores = [r for r in results if r['ticker'] in self.previous_results and r['score'] > self.previous_results[r['ticker']]['score']]
        
        self.logger.info(f"[{self.user_name}] ━━━ Cycle complete: {len(results)} tracked, {len(high_scores)} with score ≥50, "
                        f"{len(rising_scores)} rising, took {cycle_duration:.1f}s ━━━")
        
        # No JSON saving needed - we just want simple logs
    
    def run(self):
        """Main tracking loop"""
        self.logger.info(f"[{self.user_name}] VSR Tracker Service started - Minute-by-minute scoring with hourly data")
        
        while True:
            try:
                start_time = time.time()
                
                # Run tracking cycle
                self.run_tracking_cycle()
                
                # Calculate sleep time for next minute
                cycle_duration = time.time() - start_time
                sleep_time = max(60 - cycle_duration, 10)  # At least 10 seconds
                
                self.logger.info(f"[{self.user_name}] Next cycle in {sleep_time:.0f} seconds...")
                time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                self.logger.info(f"[{self.user_name}] Service stopped by user")
                break
            except Exception as e:
                self.logger.error(f"[{self.user_name}] Unexpected error: {e}")
                time.sleep(60)  # Wait a minute before retrying

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='VSR Tracker Service - Simplified')
    parser.add_argument('-u', '--user', default='Sai', help='User name for credentials')
    
    args = parser.parse_args()
    
    # Create and run tracker
    tracker = VSRTracker(user_name=args.user)
    tracker.run()

if __name__ == "__main__":
    main()