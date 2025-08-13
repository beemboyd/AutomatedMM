#!/usr/bin/env python3
"""
Hourly Short Tracker Service
Tracks Short_Reversal_Hourly tickers with proper initialization
"""

import os
import sys
import json
import time
import logging
import datetime
import pandas as pd
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import required functions
from scanners.VSR_Momentum_Scanner import (
    calculate_vsr_indicators,
    get_sector_for_ticker,
    DataCache,
    fetch_data_kite,
    interval_mapping,
    load_daily_config
)

# Import Kite Connect
from kiteconnect import KiteConnect

# Import Telegram notifier
from alerts.telegram_notifier import TelegramNotifier

# Global kite variable for fetch_data_kite function
kite = None

class HourlyShortTrackerService:
    def __init__(self, user_name: str = 'Sai', interval: int = 60, enable_telegram: bool = True):
        """Initialize the hourly short tracker service"""
        self.user_name = user_name
        self.interval = interval
        
        # Setup logging
        self.setup_logging()
        
        # Initialize Kite connection
        self.kite = self.initialize_kite_connection()
        
        # Set global kite for fetch_data_kite
        global kite
        kite = self.kite
        
        # Track previous results for momentum build
        self.previous_results = {}
        
        # Initialize persistence data
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(self.base_dir, 'data')
        self.short_momentum_dir = os.path.join(self.data_dir, 'short_momentum')
        self.persistence_file = os.path.join(self.short_momentum_dir, 'vsr_ticker_persistence_hourly_short.json')
        self.persistence_data = self.load_persistence()
        
        # Initialize Telegram notifier
        self.telegram_notifier = None
        if enable_telegram:
            try:
                self.telegram_notifier = TelegramNotifier()
                if self.telegram_notifier.enabled:
                    self.logger.info("Telegram notifications: ENABLED")
                else:
                    self.logger.info("Telegram notifications: DISABLED (config)")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Telegram notifier: {e}")
                self.logger.info("Telegram notifications: DISABLED")
        else:
            self.logger.info("Telegram notifications: DISABLED")
        
        self.logger.info(f"[{user_name}] Hourly Short Tracker Service initialized")
        self.logger.info(f"Scan interval: {interval} seconds")
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'hourly_short_tracker')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'hourly_short_tracker_{datetime.date.today().strftime("%Y%m%d")}.log')
        
        # Create logger
        self.logger = logging.getLogger('HourlyShortTracker')
        self.logger.setLevel(logging.INFO)
        
        # File handler
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter - matching VSR tracker format
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        # Add handlers
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
    
    def initialize_kite_connection(self):
        """Initialize Kite connection using config"""
        try:
            # Load config
            config = load_daily_config(self.user_name)
            credential_section = f'API_CREDENTIALS_{self.user_name}'
            
            # Get credentials
            api_key = config.get(credential_section, 'api_key')
            access_token = config.get(credential_section, 'access_token')
            
            # Initialize Kite
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            
            # Test connection
            profile = kite.profile()
            self.logger.info(f"Connected to Kite as: {profile.get('user_name', 'Unknown')}")
            
            return kite
        except Exception as e:
            self.logger.error(f"Failed to initialize Kite connection: {e}")
            raise
    
    def load_persistence(self) -> dict:
        """Load persistence data"""
        if os.path.exists(self.persistence_file):
            try:
                with open(self.persistence_file, 'r') as f:
                    data = json.load(f)
                    # Handle new format with 'tickers' key
                    if 'tickers' in data:
                        return data['tickers']
                    # Fallback to old format
                    return data
            except:
                pass
        return {}
    
    def save_persistence(self):
        """Save persistence data"""
        os.makedirs(os.path.dirname(self.persistence_file), exist_ok=True)
        # Save in new format with 'tickers' key and timestamp
        data_to_save = {
            'tickers': self.persistence_data,
            'last_updated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        with open(self.persistence_file, 'w') as f:
            json.dump(data_to_save, f, indent=2)
    
    def get_latest_short_reversal_tickers(self) -> List[str]:
        """Get tickers from the latest Short_Reversal_Hourly Excel file"""
        results_dir = os.path.join(self.base_dir, 'results-s-h')
        
        if not os.path.exists(results_dir):
            self.logger.warning(f"Results directory not found: {results_dir}")
            return []
        
        # Find the latest Short_Reversal_Hourly file
        files = [f for f in os.listdir(results_dir) if f.startswith('Short_Reversal_Hourly_') and f.endswith('.xlsx')]
        
        if not files:
            self.logger.warning("No Short_Reversal_Hourly files found")
            return []
        
        # Sort by filename (which includes timestamp) and get the latest
        latest_file = sorted(files)[-1]
        file_path = os.path.join(results_dir, latest_file)
        
        try:
            # Read the Excel file
            df = pd.read_excel(file_path)
            if 'Ticker' in df.columns:
                tickers = df['Ticker'].tolist()
                self.logger.info(f"Loaded {len(tickers)} tickers from {latest_file}")
                return tickers
            else:
                self.logger.warning(f"No 'Ticker' column found in {latest_file}")
                return []
        except Exception as e:
            self.logger.error(f"Error reading {file_path}: {e}")
            return []
    
    def fetch_minute_data(self, ticker: str) -> Optional[pd.DataFrame]:
        """Fetch minute data for a ticker"""
        try:
            # Use fetch_data_kite from VSR_Momentum_Scanner
            now = datetime.datetime.now()
            from_date = (now - datetime.timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
            to_date = now.strftime('%Y-%m-%d %H:%M:%S')
            
            # Fetch data using the imported function
            df = fetch_data_kite(ticker, 'minute', from_date, to_date)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching minute data for {ticker}: {e}")
            return None
    
    def track_ticker_vsr(self, ticker: str) -> Optional[Dict]:
        """Track VSR for a single ticker using same logic as daily VSR tracker"""
        try:
            # Fetch minute data
            minute_data = self.fetch_minute_data(ticker)
            
            if minute_data is None or minute_data.empty:
                return None
            
            # Get current price and volume
            latest_minute = minute_data.iloc[-1]
            current_price = latest_minute['Close']
            current_volume = latest_minute['Volume']
            
            # Add technical indicators
            minute_with_indicators = calculate_vsr_indicators(minute_data)
            if minute_with_indicators is None or minute_with_indicators.empty:
                return None
            
            # Calculate 5-minute momentum
            if len(minute_with_indicators) >= 5:
                price_5min_ago = minute_with_indicators.iloc[-5]['Close']
                momentum_5min = ((current_price - price_5min_ago) / price_5min_ago) * 100
            else:
                momentum_5min = 0
            
            # Get latest indicators
            latest_indicators = minute_with_indicators.iloc[-1]
            vsr_ratio = latest_indicators.get('VSR_Ratio', 0)
            vsr_roc = latest_indicators.get('VSR_ROC', 0)
            volume_ratio = latest_indicators.get('VolumeRatio', 0)
            
            # Check for momentum build (for shorts, we look for downward momentum)
            momentum_build = 0
            if len(minute_with_indicators) >= 15:  # 15 minutes
                recent_bars = minute_with_indicators.tail(15)
                vsr_ratios = recent_bars['VSR_Ratio'].values
                
                # Check if VSR is building (for shorts)
                if len(vsr_ratios) >= 15:
                    if vsr_ratios[-1] > vsr_ratios[-5] > vsr_ratios[-10]:
                        momentum_build = 20  # Strong momentum build
                    elif vsr_ratios[-1] > vsr_ratios[-5]:
                        momentum_build = 10  # Moderate momentum build
            
            # Calculate score (0-100) - Adjusted for short positions
            score = 0
            
            # Base VSR scoring
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
            # For shorts, negative momentum is good
            if momentum_5min < 0:
                score += 10
            if momentum_5min < -1:
                score += 5
            
            # Add momentum build to score
            score += momentum_build
            
            # Cap score at 100
            score = min(score, 100)
            
            # Determine trend
            if len(minute_with_indicators) >= 10:
                recent_prices = minute_with_indicators.tail(10)['Close'].values
                if all(recent_prices[i] >= recent_prices[i+1] for i in range(len(recent_prices)-1)):
                    trend = "STRONG_DOWN"
                elif recent_prices[-1] < recent_prices[0]:
                    trend = "DOWN"
                elif recent_prices[-1] > recent_prices[0]:
                    trend = "UP"
                else:
                    trend = "FLAT"
            else:
                trend = "FLAT"
            
            # Get sector
            sector = get_sector_for_ticker(ticker)
            
            # Update persistence tracking
            now = datetime.datetime.now()
            ticker_data = self.persistence_data.get(ticker, {
                'first_seen': now.strftime('%Y-%m-%d'),
                'days_tracked': 0,
                'scores': [],
                'last_score': 0,
                'max_score': 0,
                'avg_score': 0
            })
            
            # Calculate days tracked
            first_seen_date = datetime.datetime.strptime(ticker_data['first_seen'], '%Y-%m-%d').date()
            days_tracked = (now.date() - first_seen_date).days + 1
            
            # Update scores
            ticker_data['scores'].append(score)
            if len(ticker_data['scores']) > 48:  # Keep last 48 hours
                ticker_data['scores'] = ticker_data['scores'][-48:]
            
            ticker_data['last_score'] = score
            ticker_data['max_score'] = max(ticker_data['scores'])
            ticker_data['avg_score'] = sum(ticker_data['scores']) / len(ticker_data['scores'])
            ticker_data['days_tracked'] = days_tracked
            ticker_data['last_updated'] = now.strftime('%Y-%m-%d %H:%M:%S')
            
            self.persistence_data[ticker] = ticker_data
            
            return {
                'Ticker': ticker,
                'Score': score,
                'VSR': vsr_ratio,
                'Price': current_price,
                'Volume': current_volume,
                'Momentum': momentum_5min,
                'Build': momentum_build,
                'Trend': trend,
                'Days': days_tracked,
                'Sector': sector
            }
            
        except Exception as e:
            self.logger.error(f"Error tracking {ticker}: {e}")
            return None
    
    def format_ticker_display(self, result: Dict) -> str:
        """Format ticker result for display - matching daily VSR format"""
        ticker = result['Ticker'].ljust(12)
        score = f"Score: {result['Score']:3d}"
        vsr = f"VSR: {result['VSR']:5.2f}"
        price = f"Price: ₹{result['Price']:8.2f}"
        volume = f"Vol: {result['Volume']:10,d}"
        momentum = f"Momentum: {result['Momentum']:6.1f}%"
        build = f"Build: {result['Build']:3d}"
        trend = f"Trend: {result['Trend']}"
        days = f"Days: {result['Days']}"
        sector = f"Sector: {result['Sector']}"
        
        return f"[{self.user_name}] {ticker} | {score} | {vsr} | {price} | {volume} | {momentum} | {build} | {trend} | {days} | {sector}"
    
    def run_scan(self):
        """Run a single scan iteration"""
        try:
            self.logger.info("="*80)
            self.logger.info(f"[{self.user_name}] Starting Hourly Short tracker scan at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Get tickers from latest Short_Reversal_Hourly file
            tickers = self.get_latest_short_reversal_tickers()
            
            if not tickers:
                self.logger.warning("No tickers to track")
                return
            
            # Track VSR for each ticker
            results = []
            
            for i, ticker in enumerate(tickers, 1):
                self.logger.info(f"[{i}/{len(tickers)}] Tracking {ticker}...")
                
                result = self.track_ticker_vsr(ticker)
                if result:
                    results.append(result)
                    # Log in VSR format for dashboard parsing
                    self.logger.info(self.format_ticker_display(result))
                    time.sleep(0.5)  # Small delay between requests
            
            # Sort by score descending
            results.sort(key=lambda x: x['Score'], reverse=True)
            
            # Display summary
            self.logger.info(f"\n[{self.user_name}] ━━━ Hourly Short Tracker Summary ━━━")
            self.logger.info(f"[{self.user_name}] Total tickers tracked: {len(results)}")
            
            if results:
                # Show breakdown by score ranges
                high_score = [r for r in results if r['Score'] >= 50]
                medium_score = [r for r in results if 20 <= r['Score'] < 50]
                low_score = [r for r in results if r['Score'] < 20]
                
                self.logger.info(f"[{self.user_name}] High Score (≥50): {len(high_score)} tickers")
                self.logger.info(f"[{self.user_name}] Medium Score (20-49): {len(medium_score)} tickers")
                self.logger.info(f"[{self.user_name}] Low Score (<20): {len(low_score)} tickers")
                
                # Show top 5 by score
                self.logger.info(f"\n[{self.user_name}] ━━━ Top 5 by Score ━━━")
                for result in results[:5]:
                    ticker_display = f"{result['Ticker']:10s} Score: {result['Score']:3d} | VSR: {result['VSR']:5.2f} | Days: {result['Days']}"
                    self.logger.info(f"[{self.user_name}]   {ticker_display}")
            
            # Save persistence data
            self.save_persistence()
            
            # Send Telegram notifications for high score tickers
            if self.telegram_notifier and self.telegram_notifier.enabled:
                high_score_tickers = [r for r in results if r['Score'] >= 80]
                if high_score_tickers:
                    self.send_telegram_alerts(high_score_tickers)
            
            # Clean up old tickers from persistence
            current_date = datetime.datetime.now().date()
            tickers_to_remove = []
            
            for ticker, data in self.persistence_data.items():
                if ticker not in tickers:
                    # Check if 'last_seen' exists (new format) or 'last_updated' (old format)
                    if 'last_seen' in data:
                        last_seen = datetime.datetime.strptime(data['last_seen'], '%Y-%m-%d %H:%M:%S').date()
                    elif 'last_updated' in data:
                        last_seen = datetime.datetime.strptime(data['last_updated'], '%Y-%m-%d %H:%M:%S').date()
                    else:
                        # If neither exists, mark for removal
                        tickers_to_remove.append(ticker)
                        continue
                    
                    if (current_date - last_seen).days > 3:
                        tickers_to_remove.append(ticker)
            
            for ticker in tickers_to_remove:
                del self.persistence_data[ticker]
                self.logger.info(f"Removed {ticker} from persistence (not seen in 3 days)")
            
            if tickers_to_remove:
                self.save_persistence()
            
        except Exception as e:
            self.logger.error(f"Error in scan: {e}", exc_info=True)
    
    def send_telegram_alerts(self, high_score_tickers):
        """Send Telegram alerts for high score tickers"""
        try:
            for result in high_score_tickers:
                ticker = result['Ticker']
                score = result['Score']
                vsr = result['VSR']
                momentum = result['Momentum']
                price = result['Price']
                sector = result['Sector']
                
                # Format message
                message = (
                    f"🚨 **HOURLY SHORT ALERT** 🚨\n\n"
                    f"📊 **{ticker}**\n"
                    f"💯 Score: {score}\n"
                    f"📈 VSR: {vsr:.2f}x\n"
                    f"🚀 Momentum: {momentum:.2f}%\n"
                    f"💰 Price: ₹{price:.2f}\n"
                    f"🏭 Sector: {sector}\n"
                    f"⏰ Time: {datetime.datetime.now().strftime('%I:%M %p')}\n"
                    f"📱 Source: Short Reversal Hourly"
                )
                
                # Send notification
                if self.telegram_notifier.send_message(message):
                    self.logger.info(f"Telegram alert sent for {ticker}")
                else:
                    self.logger.warning(f"Failed to send Telegram alert for {ticker}")
                    
        except Exception as e:
            self.logger.error(f"Error sending Telegram alerts: {e}")
    
    def run(self):
        """Main run loop"""
        self.logger.info(f"[{self.user_name}] Hourly Short Tracker Service started")
        self.logger.info("Service will run from 8:00 AM to 4:00 PM IST")
        
        while True:
            try:
                current_time = datetime.datetime.now()
                current_hour = current_time.hour
                
                # Check if within trading hours (8 AM to 4 PM)
                if 8 <= current_hour < 16:
                    self.run_scan()
                else:
                    self.logger.info(f"Outside trading hours (current: {current_hour}:00). Waiting...")
                
                # Wait for next scan
                self.logger.info(f"Waiting {self.interval} seconds for next scan...")
                time.sleep(self.interval)
                
            except KeyboardInterrupt:
                self.logger.info("Service stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(60)  # Wait a minute before retrying


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Hourly Short Tracker Service')
    parser.add_argument('--user', type=str, default='Sai', help='User name for tracking')
    parser.add_argument('--interval', type=int, default=60, help='Scan interval in seconds')
    
    args = parser.parse_args()
    
    # Check if short alerts are enabled in config
    config = load_daily_config(args.user)
    enable_telegram = config.get('TELEGRAM', 'enable_short_alerts', fallback='yes').lower() == 'yes'
    
    service = HourlyShortTrackerService(args.user, args.interval, enable_telegram=enable_telegram)
    service.run()


if __name__ == '__main__':
    main()