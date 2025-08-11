#!/usr/bin/env python3
"""
First Hour Breakout Service for 5-minute candle monitoring
Monitors VSR tickers during first hour (9:15-10:15 AM) and alerts on 5-min breakouts
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
class FirstHourBreakout:
    """Data class for first hour breakouts"""
    ticker: str
    current_price: float
    prev_5min_high: float
    breakout_pct: float
    volume_ratio: float
    momentum: float
    timestamp: datetime

class FirstHourBreakoutService:
    """Service to monitor 5-minute breakouts during first hour"""
    
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
        self.tracked_tickers = {}    # {ticker: ticker_data}
        
        # Paths
        self.state_file = os.path.join(self.base_dir, 'data', 'first_hour_state.json')
        
        # Configuration
        self.breakout_threshold = self.config.getfloat('FIRST_HOUR', 'breakout_threshold_pct', fallback=0.2)
        self.alert_cooldown_minutes = self.config.getint('FIRST_HOUR', 'alert_cooldown_minutes', fallback=5)
        self.check_interval_seconds = self.config.getint('FIRST_HOUR', 'check_interval_seconds', fallback=20)
        self.enabled = self.config.getboolean('FIRST_HOUR', 'enabled', fallback=True)
        
        # Market hours
        self.market_start = dtime(9, 15)
        self.first_hour_end = dtime(10, 15)
        
        # Load previous state
        self._load_state()
        
        self.logger.info(f"First Hour Breakout Service initialized for user: {user_name}")
        self.logger.info(f"Breakout threshold: {self.breakout_threshold}%")
        self.logger.info(f"Alert cooldown: {self.alert_cooldown_minutes} minutes")
        
        # Send startup message
        if self.telegram.is_configured() and self.enabled:
            self._send_startup_message()
            time.sleep(2)
    
    def _setup_logging(self):
        """Set up logging configuration"""
        log_dir = os.path.join(self.base_dir, 'logs', 'alerts_firsthour')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'first_hour_{datetime.now().strftime("%Y%m%d")}.log')
        
        logger = logging.getLogger('FirstHourBreakout')
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
        
        # Ensure FIRST_HOUR section exists
        if 'FIRST_HOUR' not in config:
            config['FIRST_HOUR'] = {
                'enabled': 'yes',
                'breakout_threshold_pct': '0.2',
                'alert_cooldown_minutes': '5',
                'check_interval_seconds': '20'
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
                    # Only load alerts from today
                    today = datetime.now().date().isoformat()
                    self.alerted_breakouts = {
                        k: datetime.fromisoformat(v) 
                        for k, v in state.get('alerted_breakouts', {}).items()
                        if v.startswith(today)
                    }
                    self.logger.info(f"Loaded state with {len(self.alerted_breakouts)} alerts from today")
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
                'last_update': datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")
    
    def _send_startup_message(self):
        """Send service startup notification"""
        message = f"""🌅 <b>First Hour Breakout Service Started</b>

⏰ <b>Active Hours:</b> 9:15 AM - 10:15 AM
📊 <b>Configuration:</b>
• Timeframe: 5-minute candles
• Breakout Threshold: {self.breakout_threshold}%
• Alert Cooldown: {self.alert_cooldown_minutes} min
• Tracking: Active VSR tickers

🎯 <b>Alert Trigger:</b>
When price crosses above previous 5-min high

Time: {datetime.now().strftime('%I:%M %p')}"""
        
        self.telegram.send_message(message, parse_mode='HTML')
    
    def load_tracked_tickers(self):
        """Load tickers from hourly breakout state file"""
        try:
            # Load from hourly breakout state
            hourly_state_file = os.path.join(self.base_dir, 'data', 'hourly_breakout_state.json')
            if os.path.exists(hourly_state_file):
                with open(hourly_state_file, 'r') as f:
                    hourly_state = json.load(f)
                    self.tracked_tickers = hourly_state.get('tracked_tickers', {})
                    self.logger.info(f"Loaded {len(self.tracked_tickers)} tickers from hourly breakout state")
            else:
                self.logger.warning("Hourly breakout state file not found")
        except Exception as e:
            self.logger.error(f"Error loading tracked tickers: {e}")
    
    def get_5min_candle_data(self, ticker: str) -> Optional[Dict]:
        """Get current and previous 5-minute candle data"""
        if not self.kite:
            return None
        
        try:
            # Get instrument token
            instruments = self.kite.ltp([f"NSE:{ticker}"])
            if f"NSE:{ticker}" not in instruments:
                return None
            
            # Get 5-minute candle data (last 10 candles)
            to_date = datetime.now()
            from_date = to_date - timedelta(minutes=60)
            
            candles = self.kite.historical_data(
                instrument_token=instruments[f"NSE:{ticker}"]['instrument_token'],
                from_date=from_date,
                to_date=to_date,
                interval='5minute'
            )
            
            if len(candles) >= 2:
                # Get volume ratio
                recent_volumes = [c['volume'] for c in candles[-5:]]
                avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0
                current_volume = candles[-1]['volume']
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
                
                return {
                    'current_candle': candles[-1],
                    'prev_candle': candles[-2],
                    'current_price': instruments[f"NSE:{ticker}"]['last_price'],
                    'volume_ratio': volume_ratio
                }
            
        except Exception as e:
            if "Too many requests" not in str(e):
                self.logger.error(f"Error getting 5-min data for {ticker}: {e}")
        
        return None
    
    def check_breakouts(self):
        """Check for 5-minute breakouts on tracked tickers"""
        if not self.tracked_tickers:
            self.logger.info("No tickers to track")
            return
        
        breakout_alerts = []
        
        for ticker, data in self.tracked_tickers.items():
            try:
                # Get 5-minute candle data
                candle_data = self.get_5min_candle_data(ticker)
                if not candle_data:
                    continue
                
                current_price = candle_data['current_price']
                prev_high = candle_data['prev_candle']['high']
                volume_ratio = candle_data['volume_ratio']
                
                # Check for breakout above previous 5-min high
                if current_price > prev_high:
                    breakout_pct = ((current_price - prev_high) / prev_high) * 100
                    
                    # Check if breakout is significant enough
                    if breakout_pct >= self.breakout_threshold:
                        # Check cooldown
                        last_alert = self.alerted_breakouts.get(ticker)
                        if last_alert:
                            minutes_since_alert = (datetime.now() - last_alert).total_seconds() / 60
                            if minutes_since_alert < self.alert_cooldown_minutes:
                                continue
                        
                        # Get momentum from daily data
                        momentum = data.get('daily_data', {}).get('momentum', 0)
                        
                        # Create breakout alert
                        alert = FirstHourBreakout(
                            ticker=ticker,
                            current_price=current_price,
                            prev_5min_high=prev_high,
                            breakout_pct=breakout_pct,
                            volume_ratio=volume_ratio,
                            momentum=momentum,
                            timestamp=datetime.now()
                        )
                        
                        breakout_alerts.append(alert)
                        self.alerted_breakouts[ticker] = datetime.now()
                
            except Exception as e:
                if "Too many requests" not in str(e):
                    self.logger.error(f"Error checking breakout for {ticker}: {e}")
        
        # Send alerts
        if breakout_alerts:
            self._send_breakout_alerts(breakout_alerts)
            self._save_state()
    
    def _send_breakout_alerts(self, alerts: List[FirstHourBreakout]):
        """Send breakout alerts via Telegram"""
        for alert in alerts:
            try:
                # Determine alert priority based on volume
                if alert.volume_ratio > 2.0:
                    emoji = "🚀🚀🚀"
                    volume_tag = "HIGH VOLUME"
                elif alert.volume_ratio > 1.5:
                    emoji = "🚀🚀"
                    volume_tag = "STRONG VOLUME"
                else:
                    emoji = "🚀"
                    volume_tag = "BREAKOUT"
                
                message = f"""{emoji} <b>5-Min Breakout Alert</b>

🎯 <b>{alert.ticker}</b>
💰 Current: ₹{alert.current_price:.2f}
📊 Prev 5m High: ₹{alert.prev_5min_high:.2f}
📈 Breakout: +{alert.breakout_pct:.2f}%

📊 <b>Volume:</b> {alert.volume_ratio:.1f}x avg
💪 <b>Momentum:</b> {alert.momentum:.1f}%

⏰ {alert.timestamp.strftime('%I:%M %p')}
🏷️ {volume_tag}

<i>First hour 5-min breakout detected</i>"""
                
                self.telegram.send_message(message, parse_mode='HTML')
                self.logger.info(f"Sent 5-min breakout alert for {alert.ticker} (+{alert.breakout_pct:.2f}%, Vol: {alert.volume_ratio:.1f}x)")
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error sending alert for {alert.ticker}: {e}")
    
    def is_within_first_hour(self) -> bool:
        """Check if current time is within first hour of trading"""
        current_time = datetime.now().time()
        return self.market_start <= current_time <= self.first_hour_end
    
    def run_monitoring_cycle(self):
        """Run a single monitoring cycle"""
        try:
            # Load tracked tickers at start of each cycle
            self.load_tracked_tickers()
            
            # Check for breakouts
            if self.tracked_tickers:
                self.check_breakouts()
            
        except Exception as e:
            self.logger.error(f"Error in monitoring cycle: {e}")
    
    def run_continuous_monitoring(self):
        """Run continuous monitoring during first hour"""
        self.logger.info("Starting first hour breakout monitoring...")
        
        while True:
            try:
                current_time = datetime.now()
                
                # Only run during first hour (9:15 AM to 10:15 AM)
                if self.is_within_first_hour():
                    if self.enabled:
                        self.run_monitoring_cycle()
                    else:
                        self.logger.info("Service is disabled in config")
                        time.sleep(60)
                else:
                    # Clear alerts at start of new day
                    if current_time.hour == 9 and current_time.minute < 15:
                        self.alerted_breakouts.clear()
                        self.logger.info("Cleared alert history for new trading day")
                    
                    # Service complete for the day after 10:15 AM
                    if current_time.hour >= 10 and current_time.minute > 15:
                        self.logger.info("First hour complete. Service stopping.")
                        self._send_completion_message()
                        break
                    
                    self.logger.debug("Outside first hour, waiting...")
                    time.sleep(60)
                    continue
                
                # Sleep for configured interval
                time.sleep(self.check_interval_seconds)
                
            except KeyboardInterrupt:
                self.logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in continuous monitoring: {e}")
                time.sleep(30)
    
    def _send_completion_message(self):
        """Send service completion notification"""
        alert_count = len(self.alerted_breakouts)
        message = f"""✅ <b>First Hour Trading Complete</b>

📊 <b>Summary:</b>
• Total Alerts: {alert_count}
• Tickers Tracked: {len(self.tracked_tickers)}
• Session: 9:15 AM - 10:15 AM

Service will restart tomorrow at 9:15 AM.

Time: {datetime.now().strftime('%I:%M %p')}"""
        
        self.telegram.send_message(message, parse_mode='HTML')


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='First Hour Breakout Service')
    parser.add_argument('-u', '--user', default='Sai', help='User name')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    args = parser.parse_args()
    
    # Create and run service
    service = FirstHourBreakoutService(user_name=args.user)
    
    if args.test:
        # Test mode - run one cycle
        service.run_monitoring_cycle()
    else:
        # Run continuous monitoring
        service.run_continuous_monitoring()


if __name__ == "__main__":
    main()