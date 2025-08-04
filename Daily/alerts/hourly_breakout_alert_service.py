#!/usr/bin/env python3
"""
Hourly Breakout Alert Service for Long Reversal Tickers
Monitors tickers from Long Reversal Scanner and alerts when they cross above previous hourly candle close
"""

import os
import sys
import time
import logging
import json
import glob
from datetime import datetime, time as dtime, timedelta
from typing import Dict, List, Set, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass
import configparser

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_notifier import TelegramNotifier
from kiteconnect import KiteConnect

@dataclass
class BreakoutAlert:
    """Data class for breakout alerts"""
    ticker: str
    current_price: float
    prev_hourly_close: float
    breakout_pct: float
    daily_momentum: float
    daily_score: str
    pattern: str
    timestamp: datetime

class HourlyBreakoutAlertService:
    """Service to monitor hourly breakouts on Long Reversal tickers"""
    
    def __init__(self, user_name='Sai'):
        """Initialize the service"""
        self.user_name = user_name
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Set up logging
        self.logger = self._setup_logging()
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize components
        self.telegram = TelegramNotifier()
        self.kite = self._initialize_kite()
        
        # Alert tracking
        self.alerted_breakouts = {}  # {ticker: last_alert_time}
        self.tracked_tickers = {}    # {ticker: {'prev_close': x, 'daily_data': {...}}}
        self.last_scan_time = None
        
        # Paths
        self.daily_results_dir = os.path.join(self.base_dir, 'results')
        self.state_file = os.path.join(self.base_dir, 'data', 'hourly_breakout_state.json')
        
        # Configuration
        self.breakout_threshold = self.config.getfloat('HOURLY_BREAKOUT', 'breakout_threshold_pct', fallback=0.1)
        self.alert_cooldown_minutes = self.config.getint('HOURLY_BREAKOUT', 'alert_cooldown_minutes', fallback=60)
        self.min_daily_score = self.config.getint('HOURLY_BREAKOUT', 'min_daily_score', fallback=5)
        self.enabled = self.config.getboolean('HOURLY_BREAKOUT', 'enabled', fallback=True)
        
        # Load previous state
        self._load_state()
        
        self.logger.info(f"Hourly Breakout Alert Service initialized for user: {user_name}")
        self.logger.info(f"Breakout threshold: {self.breakout_threshold}%")
        self.logger.info(f"Alert cooldown: {self.alert_cooldown_minutes} minutes")
        
        # Send startup message
        if self.telegram.is_configured() and self.enabled:
            self._send_startup_message()
            # Small delay to ensure startup message is delivered first
            time.sleep(2)
    
    def _setup_logging(self):
        """Set up logging configuration"""
        log_dir = os.path.join(self.base_dir, 'logs', 'alerts_hourlybo')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'hourly_breakout_{datetime.now().strftime("%Y%m%d")}.log')
        
        logger = logging.getLogger('HourlyBreakoutAlert')
        logger.setLevel(logging.INFO)
        
        # File handler
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger
    
    def _load_config(self):
        """Load configuration from config.ini"""
        config_path = os.path.join(self.base_dir, 'config.ini')
        config = configparser.ConfigParser()
        config.read(config_path)
        
        # Ensure HOURLY_BREAKOUT section exists
        if 'HOURLY_BREAKOUT' not in config:
            config['HOURLY_BREAKOUT'] = {
                'enabled': 'yes',
                'breakout_threshold_pct': '0.1',
                'alert_cooldown_minutes': '60',
                'min_daily_score': '5',
                'check_interval_seconds': '30'
            }
            
            # Save updated config
            with open(config_path, 'w') as f:
                config.write(f)
        
        return config
    
    def _initialize_kite(self):
        """Initialize KiteConnect instance"""
        try:
            # Load config
            config_path = os.path.join(self.base_dir, 'config.ini')
            config = configparser.ConfigParser()
            config.read(config_path)
            
            # Get credentials for user
            credential_section = f'API_CREDENTIALS_{self.user_name}'
            api_key = config.get(credential_section, 'api_key')
            access_token = config.get(credential_section, 'access_token')
            
            if not api_key or not access_token:
                self.logger.error(f"Missing API credentials for user {self.user_name}")
                return None
            
            # Initialize Kite
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
            return kite
        except Exception as e:
            self.logger.error(f"Failed to initialize Kite: {e}")
            return None
    
    def _load_state(self):
        """Load previous state from file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.alerted_breakouts = {
                        k: datetime.fromisoformat(v) for k, v in state.get('alerted_breakouts', {}).items()
                    }
                    self.tracked_tickers = state.get('tracked_tickers', {})
                    self.logger.info(f"Loaded state with {len(self.tracked_tickers)} tracked tickers")
            except Exception as e:
                self.logger.error(f"Error loading state: {e}")
    
    def _save_state(self):
        """Save current state to file"""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            state = {
                'alerted_breakouts': {
                    k: v.isoformat() for k, v in self.alerted_breakouts.items()
                },
                'tracked_tickers': self.tracked_tickers,
                'last_update': datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")
    
    def _send_startup_message(self):
        """Send service startup notification"""
        message = f"""🚀 <b>Hourly Breakout Alert Service Started</b>

📊 <b>Configuration:</b>
• Breakout Threshold: {self.breakout_threshold}%
• Alert Cooldown: {self.alert_cooldown_minutes} min
• Tracking: VSR (2.0+) & High Momentum (10%+) tickers

🎯 <b>Alert Trigger:</b>
When price crosses above previous hourly close

Time: {datetime.now().strftime('%I:%M %p')}"""
        
        self.telegram.send_message(message, parse_mode='HTML')
    
    def update_tracked_tickers(self):
        """Update list of tickers from latest VSR scans (hourly and daily)"""
        try:
            current_date = datetime.now().strftime('%Y%m%d')
            tracked_tickers_set = set()
            
            # Get persistence data to check historical appearance
            hourly_persistence_file = os.path.join(self.base_dir, 'data', 'vsr_ticker_persistence_hourly_long.json')
            daily_persistence_file = os.path.join(self.base_dir, 'data', 'vsr_ticker_persistence.json')
            
            # Load persistence data
            hourly_persistence = {}
            daily_persistence = {}
            
            if os.path.exists(hourly_persistence_file):
                with open(hourly_persistence_file, 'r') as f:
                    hourly_persistence = json.load(f)
            
            if os.path.exists(daily_persistence_file):
                with open(daily_persistence_file, 'r') as f:
                    daily_persistence = json.load(f)
            
            # 1. Load Hourly VSR results - ONLY TODAY's appearances
            hourly_vsr_dir = os.path.join(self.base_dir, 'scanners', 'Hourly')
            hourly_pattern = f"VSR_{current_date}_*.xlsx"
            hourly_files = glob.glob(os.path.join(hourly_vsr_dir, hourly_pattern))
            
            if hourly_files:
                latest_hourly = max(hourly_files, key=os.path.getmtime)
                self.logger.info(f"Loading hourly VSR from: {os.path.basename(latest_hourly)}")
                
                try:
                    hourly_df = pd.read_excel(latest_hourly)
                    # Filter for good VSR ratios (2.0+ for hourly) AND first appearance today
                    hourly_filtered = hourly_df[hourly_df['VSR_Ratio'] >= 2.0]
                    
                    for ticker in hourly_filtered['Ticker']:
                        # Check if ticker appeared today for the first time
                        if ticker in hourly_persistence.get('tickers', {}):
                            ticker_data = hourly_persistence['tickers'][ticker]
                            first_seen = ticker_data.get('first_seen', '')
                            # Check if first seen today
                            if first_seen.startswith(current_date[:4] + '-' + current_date[4:6] + '-' + current_date[6:]):
                                tracked_tickers_set.add(ticker)
                                self.logger.info(f"Added {ticker} - first appearance today in hourly VSR")
                        else:
                            # New ticker appearing today
                            tracked_tickers_set.add(ticker)
                            self.logger.info(f"Added {ticker} - new ticker in hourly VSR")
                    
                    self.logger.info(f"Added {len([t for t in hourly_filtered['Ticker'] if t in tracked_tickers_set])} tickers from today's hourly VSR")
                except Exception as e:
                    self.logger.error(f"Error reading hourly VSR file: {e}")
            
            # 2. Check Long Reversal Daily for high momentum tickers - THIS WEEK only
            # Get dates for current week (Monday to today)
            today = datetime.now()
            monday = today - timedelta(days=today.weekday())
            week_dates = [(monday + timedelta(days=i)).strftime('%Y%m%d') 
                         for i in range((today - monday).days + 1)]
            
            daily_pattern = f"Long_Reversal_Daily_{current_date}_*.xlsx"
            daily_files = glob.glob(os.path.join(self.daily_results_dir, daily_pattern))
            
            if daily_files:
                latest_daily = max(daily_files, key=os.path.getmtime)
                self.logger.info(f"Loading daily scan from: {os.path.basename(latest_daily)}")
                
                try:
                    daily_df = pd.read_excel(latest_daily)
                    # Only track high momentum tickers from daily scan (10%+)
                    high_momentum = daily_df[daily_df['Momentum_5D'] >= 10.0]
                    
                    for ticker in high_momentum['Ticker']:
                        # Check if ticker first appeared this week
                        if ticker in daily_persistence.get('tickers', {}):
                            ticker_data = daily_persistence['tickers'][ticker]
                            first_seen = ticker_data.get('first_seen', '')
                            # Parse first_seen date
                            if first_seen:
                                try:
                                    first_seen_date = datetime.fromisoformat(first_seen.split('T')[0])
                                    # Check if first seen this week
                                    if first_seen_date >= monday:
                                        tracked_tickers_set.add(ticker)
                                        self.logger.info(f"Added {ticker} - appeared this week in daily scan (first seen: {first_seen_date.strftime('%Y-%m-%d')})")
                                except:
                                    pass
                        else:
                            # New ticker appearing today
                            tracked_tickers_set.add(ticker)
                            self.logger.info(f"Added {ticker} - new ticker in daily scan")
                    
                    self.logger.info(f"Added {len([t for t in high_momentum['Ticker'] if t in tracked_tickers_set])} high momentum tickers from this week")
                except Exception as e:
                    self.logger.error(f"Error reading daily scan file: {e}")
            
            if not tracked_tickers_set:
                self.logger.warning("No VSR or high momentum tickers found")
                return
            
            # Clear old tickers not in current scan
            self.tracked_tickers = {
                k: v for k, v in self.tracked_tickers.items() 
                if k in tracked_tickers_set
            }
            
            # Now get detailed data for tracked tickers from daily scan
            if daily_files and tracked_tickers_set:
                df = pd.read_excel(max(daily_files, key=os.path.getmtime))
                
                # Update tracked tickers with daily data
                for _, row in df.iterrows():
                    ticker = row['Ticker']
                    
                    # Only update if ticker is in our tracked set
                    if ticker in tracked_tickers_set:
                        if ticker not in self.tracked_tickers:
                            self.tracked_tickers[ticker] = {}
                        
                        # Update daily data
                        self.tracked_tickers[ticker]['daily_data'] = {
                            'score': row['Score'],
                            'momentum': row['Momentum_5D'],
                            'pattern': row['Pattern'],
                            'entry_price': row['Entry_Price'],
                            'stop_loss': row['Stop_Loss'],
                            'last_update': datetime.now().isoformat()
                        }
            
            self.logger.info(f"Tracking {len(self.tracked_tickers)} tickers (VSR + High Momentum)")
            self._save_state()
            
        except Exception as e:
            self.logger.error(f"Error updating tracked tickers: {e}")
    
    def get_hourly_candle_data(self, ticker: str) -> Optional[Dict]:
        """Get current and previous hourly candle data"""
        if not self.kite:
            return None
        
        try:
            # Get instrument token
            instruments = self.kite.ltp([f"NSE:{ticker}"])
            if f"NSE:{ticker}" not in instruments:
                return None
            
            # Get hourly candle data (last 2 candles)
            to_date = datetime.now()
            from_date = to_date - timedelta(hours=3)
            
            candles = self.kite.historical_data(
                instrument_token=instruments[f"NSE:{ticker}"]['instrument_token'],
                from_date=from_date,
                to_date=to_date,
                interval='60minute'
            )
            
            if len(candles) >= 2:
                return {
                    'current_candle': candles[-1],
                    'prev_candle': candles[-2],
                    'current_price': instruments[f"NSE:{ticker}"]['last_price']
                }
            
        except Exception as e:
            self.logger.error(f"Error getting hourly data for {ticker}: {e}")
        
        return None
    
    def check_breakouts(self):
        """Check for hourly breakouts on tracked tickers"""
        if not self.tracked_tickers:
            self.logger.info("No tickers to track")
            return
        
        breakout_alerts = []
        
        for ticker, data in self.tracked_tickers.items():
            try:
                # Get hourly candle data
                candle_data = self.get_hourly_candle_data(ticker)
                if not candle_data:
                    continue
                
                current_price = candle_data['current_price']
                prev_close = candle_data['prev_candle']['close']
                
                # Store previous close for tracking
                self.tracked_tickers[ticker]['prev_hourly_close'] = prev_close
                
                # Check for breakout
                if current_price > prev_close:
                    breakout_pct = ((current_price - prev_close) / prev_close) * 100
                    
                    # Check if breakout is significant enough
                    if breakout_pct >= self.breakout_threshold:
                        # Check cooldown
                        last_alert = self.alerted_breakouts.get(ticker)
                        if last_alert:
                            minutes_since_alert = (datetime.now() - last_alert).total_seconds() / 60
                            if minutes_since_alert < self.alert_cooldown_minutes:
                                continue
                        
                        # Create breakout alert
                        alert = BreakoutAlert(
                            ticker=ticker,
                            current_price=current_price,
                            prev_hourly_close=prev_close,
                            breakout_pct=breakout_pct,
                            daily_momentum=data['daily_data']['momentum'],
                            daily_score=data['daily_data']['score'],
                            pattern=data['daily_data']['pattern'],
                            timestamp=datetime.now()
                        )
                        
                        breakout_alerts.append(alert)
                        self.alerted_breakouts[ticker] = datetime.now()
                
            except Exception as e:
                self.logger.error(f"Error checking breakout for {ticker}: {e}")
        
        # Send alerts
        if breakout_alerts:
            self._send_breakout_alerts(breakout_alerts)
            self._save_state()
    
    def _send_breakout_alerts(self, alerts: List[BreakoutAlert]):
        """Send breakout alerts via Telegram"""
        for alert in alerts:
            try:
                # Determine alert priority
                if alert.daily_momentum > 10:
                    emoji = "🔥🔥🔥"
                    priority = "HIGH MOMENTUM"
                elif alert.daily_momentum > 5:
                    emoji = "🔥🔥"
                    priority = "MODERATE"
                else:
                    emoji = "🔥"
                    priority = "BREAKOUT"
                
                message = f"""{emoji} <b>Hourly Breakout Alert</b>

🎯 <b>{alert.ticker}</b>
💰 Current: ₹{alert.current_price:.2f}
📊 Prev Hr Close: ₹{alert.prev_hourly_close:.2f}
📈 Breakout: +{alert.breakout_pct:.2f}%

📊 <b>Daily Setup:</b>
• Score: {alert.daily_score}
• Momentum: {alert.daily_momentum:.2f}%
• Pattern: {alert.pattern}

⏰ {alert.timestamp.strftime('%I:%M %p')}

<i>Price crossed above previous hourly close</i>"""
                
                self.telegram.send_message(message, parse_mode='HTML')
                self.logger.info(f"Sent breakout alert for {alert.ticker} (+{alert.breakout_pct:.2f}%)")
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error sending alert for {alert.ticker}: {e}")
    
    def run_monitoring_cycle(self):
        """Run a single monitoring cycle"""
        try:
            current_time = datetime.now()
            
            # Update tracked tickers every 30 minutes
            if (self.last_scan_time is None or 
                (current_time - self.last_scan_time).total_seconds() > 1800):
                self.update_tracked_tickers()
                self.last_scan_time = current_time
            
            # Check for breakouts
            self.check_breakouts()
            
        except Exception as e:
            self.logger.error(f"Error in monitoring cycle: {e}")
    
    def run_continuous_monitoring(self):
        """Run continuous monitoring"""
        self.logger.info("Starting continuous hourly breakout monitoring...")
        
        check_interval = self.config.getint('HOURLY_BREAKOUT', 'check_interval_seconds', fallback=30)
        
        while True:
            try:
                current_time = datetime.now()
                
                # Only run during market hours (9:15 AM to 3:30 PM)
                if (current_time.hour == 9 and current_time.minute >= 15) or \
                   (10 <= current_time.hour <= 14) or \
                   (current_time.hour == 15 and current_time.minute <= 30):
                    
                    if self.enabled:
                        self.run_monitoring_cycle()
                    else:
                        self.logger.info("Service is disabled in config")
                        time.sleep(300)  # Check again in 5 minutes
                else:
                    # Clear alerts at start of new day
                    if current_time.hour == 9 and current_time.minute < 15:
                        self.alerted_breakouts.clear()
                        self.logger.info("Cleared alert history for new trading day")
                    
                    self.logger.debug("Outside market hours, sleeping...")
                    time.sleep(60)  # Check every minute outside market hours
                    continue
                
                # Sleep for configured interval
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in continuous monitoring: {e}")
                time.sleep(60)


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Hourly Breakout Alert Service')
    parser.add_argument('-u', '--user', default='Sai', help='User name')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    args = parser.parse_args()
    
    # Create and run service
    service = HourlyBreakoutAlertService(user_name=args.user)
    
    if args.test:
        # Test mode - run one cycle
        service.run_monitoring_cycle()
    else:
        # Run continuous monitoring
        service.run_continuous_monitoring()


if __name__ == "__main__":
    main()