#!/usr/bin/env python3
"""
Enhanced VSR Telegram Alert Service
Monitors both hourly and daily VSR scanners with configurable alerts
"""

import os
import sys
import time
import logging
import json
import glob
from datetime import datetime, time as dtime, timedelta
from typing import Dict, List, Set, Optional
import pandas as pd
import configparser

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_notifier import TelegramNotifier
from services.vsr_tracker_service_enhanced import EnhancedVSRTracker

class EnhancedVSRTelegramService(EnhancedVSRTracker):
    """Extended VSR tracker with configurable hourly/daily Telegram notifications"""
    
    def __init__(self, user_name='Sai'):
        """Initialize Enhanced VSR Telegram Service"""
        # Set base_dir before calling parent init
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        super().__init__(user_name)
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize Telegram notifier
        self.telegram = TelegramNotifier()
        
        # Alert configuration from config.ini
        telegram_config = self.config['TELEGRAM']
        self.hourly_alerts_enabled = telegram_config.getboolean('hourly_telegram_on', True)
        self.daily_alerts_enabled = telegram_config.getboolean('daily_telegram_on', True)
        self.momentum_threshold = telegram_config.getfloat('high_momentum_threshold', 10.0)
        self.score_threshold = telegram_config.getint('min_score_for_alert', 60)
        self.batch_alerts = telegram_config.getboolean('batch_alerts', False)
        self.batch_interval = telegram_config.getint('batch_interval_minutes', 5) * 60
        
        # Hourly specific thresholds
        self.hourly_momentum_threshold = telegram_config.getfloat('hourly_momentum_threshold', 2.0)
        self.hourly_vsr_threshold = telegram_config.getfloat('hourly_vsr_threshold', 2.0)
        
        # Short alerts configuration
        self.enable_short_alerts = telegram_config.getboolean('enable_short_alerts', True)
        
        # Track alerts separately for hourly and daily
        self.hourly_alerts_sent = set()
        self.daily_alerts_sent = set()
        
        # Load negative momentum (short) tickers to filter
        self.negative_momentum_tickers = set()
        self._load_negative_momentum_tickers()
        self.hourly_batch = []
        self.daily_batch = []
        self.last_hourly_batch_time = datetime.now()
        self.last_daily_batch_time = datetime.now()
        self.daily_alerts_count = 0
        self.hourly_alerts_count = 0
        
        # Hourly scan tracking
        self.last_hourly_scan_time = None
        self.hourly_scan_results = {}
        
        # VSR paths
        self.hourly_results_dir = os.path.join(self.base_dir, 'results-h')
        self.daily_results_dir = os.path.join(self.base_dir, 'results')
        
        self.logger.info(f"Enhanced VSR Telegram Service initialized")
        self.logger.info(f"Hourly alerts: {'ON' if self.hourly_alerts_enabled else 'OFF'}")
        self.logger.info(f"Daily alerts: {'ON' if self.daily_alerts_enabled else 'OFF'}")
        
        # Test Telegram connection
        if self.telegram.is_configured():
            if self.telegram.test_connection():
                self.logger.info("✅ Telegram connection successful")
                # Send startup message
                self._send_startup_message()
            else:
                self.logger.error("❌ Telegram connection failed")
    
    def _load_negative_momentum_tickers(self):
        """Load tickers that are in negative/short momentum"""
        try:
            # Load from short momentum persistence file
            short_persist_file = os.path.join(self.base_dir, 'data', 'short_momentum', 'vsr_ticker_persistence_hourly_short.json')
            if os.path.exists(short_persist_file):
                with open(short_persist_file, 'r') as f:
                    data = json.load(f)
                    tickers = data.get('tickers', {})
                    self.negative_momentum_tickers = set(tickers.keys())
                    self.logger.info(f"Loaded {len(self.negative_momentum_tickers)} negative momentum tickers to filter")
            
            # Also load from latest short momentum data
            latest_short_file = os.path.join(self.base_dir, 'data', 'short_momentum', 'latest_short_momentum.json')
            if os.path.exists(latest_short_file):
                with open(latest_short_file, 'r') as f:
                    data = json.load(f)
                    short_tickers = data.get('tickers', [])
                    if short_tickers:
                        self.negative_momentum_tickers.update(short_tickers)
                        
            # Load from short reversal daily results
            short_results_dir = os.path.join(self.base_dir, 'results-s')
            if os.path.exists(short_results_dir):
                today_str = datetime.now().strftime('%Y%m%d')
                short_files = glob.glob(os.path.join(short_results_dir, f'Short_Reversal_Daily_{today_str}*.xlsx'))
                
                for short_file in short_files[-1:]:  # Latest file only
                    try:
                        df = pd.read_excel(short_file)
                        if 'Ticker' in df.columns:
                            short_tickers = df['Ticker'].tolist()
                            self.negative_momentum_tickers.update(short_tickers)
                    except Exception as e:
                        self.logger.debug(f"Error loading short file {short_file}: {e}")
            
            if self.negative_momentum_tickers:
                self.logger.info(f"Total negative momentum tickers to filter: {len(self.negative_momentum_tickers)}")
                self.logger.debug(f"Negative momentum tickers: {sorted(self.negative_momentum_tickers)}")
                
        except Exception as e:
            self.logger.error(f"Error loading negative momentum tickers: {e}")
    
    def _load_config(self):
        """Load configuration from config.ini"""
        config_path = os.path.join(self.base_dir, 'config.ini')
        config = configparser.ConfigParser()
        config.read(config_path)
        
        # Ensure required sections exist
        if 'TELEGRAM' not in config:
            config['TELEGRAM'] = {}
        
        # Add new parameters if not present
        telegram_section = config['TELEGRAM']
        if 'hourly_telegram_on' not in telegram_section:
            telegram_section['hourly_telegram_on'] = 'yes'
        if 'daily_telegram_on' not in telegram_section:
            telegram_section['daily_telegram_on'] = 'yes'
        if 'hourly_momentum_threshold' not in telegram_section:
            telegram_section['hourly_momentum_threshold'] = '2.0'
        if 'hourly_vsr_threshold' not in telegram_section:
            telegram_section['hourly_vsr_threshold'] = '2.0'
        if 'enable_short_alerts' not in telegram_section:
            telegram_section['enable_short_alerts'] = 'yes'
        
        # Save updated config
        with open(config_path, 'w') as f:
            config.write(f)
        
        return config
    
    def _send_startup_message(self):
        """Send service startup notification"""
        message = f"""🚀 <b>VSR Telegram Service Started</b>

📊 <b>Configuration:</b>
• Hourly Alerts: {'✅ ON' if self.hourly_alerts_enabled else '❌ OFF'}
• Daily Alerts: {'✅ ON' if self.daily_alerts_enabled else '❌ OFF'}
• Short Side Alerts: {'✅ ON' if self.enable_short_alerts else '❌ OFF'}

📈 <b>Hourly Thresholds:</b>
• Momentum: {self.hourly_momentum_threshold}%
• VSR Ratio: {self.hourly_vsr_threshold}x

📊 <b>Daily Thresholds:</b>
• Momentum: {self.momentum_threshold}%
• Min Score: {self.score_threshold}

Time: {datetime.now().strftime('%I:%M %p')}"""
        
        self.telegram.send_message(message)
    
    def check_hourly_vsr_scans(self):
        """Check for new hourly VSR scan results"""
        if not self.hourly_alerts_enabled:
            return
        
        # Look for recent VSR files in hourly results
        current_time = datetime.now()
        
        # Check files from last hour
        pattern = f"VSR_{current_time.strftime('%Y%m%d')}_*.xlsx"
        vsr_files = glob.glob(os.path.join(self.hourly_results_dir, pattern))
        
        for file_path in sorted(vsr_files):
            # Extract time from filename
            filename = os.path.basename(file_path)
            try:
                file_time_str = filename.split('_')[-1].replace('.xlsx', '')
                file_hour = int(file_time_str[:2])
                file_minute = int(file_time_str[2:4])
                file_time = current_time.replace(hour=file_hour, minute=file_minute)
                
                # Skip if file is older than 1 hour
                if (current_time - file_time).total_seconds() > 3600:
                    continue
                
                # Skip if already processed
                if file_path in self.hourly_scan_results:
                    continue
                
                # Process new file
                self.logger.info(f"Processing hourly VSR scan: {filename}")
                self._process_hourly_vsr_file(file_path)
                self.hourly_scan_results[file_path] = current_time
                
            except Exception as e:
                self.logger.error(f"Error processing {filename}: {e}")
    
    def _process_hourly_vsr_file(self, file_path):
        """Process hourly VSR scan results"""
        try:
            df = pd.read_excel(file_path)
            
            if df.empty:
                return
            
            high_momentum_tickers = []
            
            for _, row in df.iterrows():
                ticker = row.get('Ticker', '')
                
                # Filter out negative momentum tickers from hourly alerts
                if ticker in self.negative_momentum_tickers:
                    self.logger.debug(f"Filtering out {ticker} from hourly alert - ticker is in negative momentum list")
                    continue
                
                vsr_ratio = row.get('VSR_Ratio', 0)
                momentum = row.get('Momentum%', 0)
                pattern = row.get('Pattern', '')
                score = row.get('Score', 0)
                direction = row.get('Direction', 'LONG')
                
                # Filter out short signals if disabled
                if not self.enable_short_alerts and direction == 'SHORT':
                    self.logger.debug(f"Skipping SHORT signal for {ticker} - short alerts disabled")
                    continue
                
                # Filter out tickers with negative momentum
                if momentum < 0:
                    self.logger.debug(f"Filtering out {ticker} - negative momentum {momentum:.1f}%")
                    continue
                    
                # Check hourly thresholds
                if (vsr_ratio >= self.hourly_vsr_threshold and 
                    momentum >= self.hourly_momentum_threshold and
                    ticker not in self.hourly_alerts_sent):
                    
                    alert_data = {
                        'ticker': ticker,
                        'vsr_ratio': vsr_ratio,
                        'momentum': momentum,
                        'pattern': pattern,
                        'score': score,
                        'type': 'hourly',
                        'time': datetime.now().strftime('%I:%M %p')
                    }
                    
                    high_momentum_tickers.append(alert_data)
                    self.hourly_alerts_sent.add(ticker)
            
            # Send alerts
            if high_momentum_tickers:
                if self.batch_alerts:
                    self.hourly_batch.extend(high_momentum_tickers)
                    self._check_batch_alerts('hourly')
                else:
                    for ticker_data in high_momentum_tickers:
                        self._send_hourly_alert(ticker_data)
                        time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            self.logger.error(f"Error processing hourly VSR file {file_path}: {e}")
    
    def _send_hourly_alert(self, ticker_data):
        """Send hourly VSR alert"""
        ticker = ticker_data['ticker']
        vsr_ratio = ticker_data['vsr_ratio']
        momentum = ticker_data['momentum']
        pattern = ticker_data.get('pattern', 'VSR Signal')
        
        # Determine urgency emoji
        if vsr_ratio >= 3.0:
            urgency = "🔥🔥🔥"
            alert_type = "EXTREME VSR"
        elif vsr_ratio >= 2.5:
            urgency = "🔥🔥"
            alert_type = "HIGH VSR"
        else:
            urgency = "🔥"
            alert_type = "VSR SURGE"
        
        message = f"""{urgency} <b>Hourly {alert_type}</b>

🎯 <b>{ticker}</b>
📊 VSR Ratio: {vsr_ratio:.1f}x
📈 Momentum: {momentum:.1f}%
🎯 Pattern: {pattern}
⏰ Time: {ticker_data['time']}

<i>Hourly VSR Scanner Alert</i>"""
        
        self.telegram.send_message(message)
        self.logger.info(f"Sent hourly alert for {ticker}")
    
    def _check_batch_alerts(self, alert_type='daily'):
        """Check if batch alerts should be sent"""
        current_time = datetime.now()
        
        if alert_type == 'hourly':
            if (current_time - self.last_hourly_batch_time).total_seconds() >= self.batch_interval:
                if self.hourly_batch:
                    self._send_hourly_batch_alert()
                    self.hourly_batch = []
                    self.last_hourly_batch_time = current_time
        else:
            if (current_time - self.last_daily_batch_time).total_seconds() >= self.batch_interval:
                if self.daily_batch:
                    self._send_daily_batch_alert()
                    self.daily_batch = []
                    self.last_daily_batch_time = current_time
    
    def _send_hourly_batch_alert(self):
        """Send batch alert for hourly VSR signals"""
        if not self.hourly_batch:
            return
        
        # Sort by VSR ratio
        sorted_batch = sorted(self.hourly_batch, key=lambda x: x['vsr_ratio'], reverse=True)
        
        message = f"""🔥 <b>Hourly VSR Batch Alert</b> 🔥
<b>{len(sorted_batch)} High VSR Signals</b>

"""
        
        for ticker_data in sorted_batch[:10]:  # Top 10
            ticker = ticker_data['ticker']
            vsr_ratio = ticker_data['vsr_ratio']
            momentum = ticker_data['momentum']
            
            message += f"• <b>{ticker}</b> - VSR: {vsr_ratio:.1f}x, Mom: {momentum:.1f}%\n"
        
        if len(sorted_batch) > 10:
            message += f"\n<i>...and {len(sorted_batch) - 10} more signals</i>"
        
        message += f"\n\n⏰ {datetime.now().strftime('%I:%M %p')}"
        
        self.telegram.send_message(message)
        self.logger.info(f"Sent hourly batch alert with {len(sorted_batch)} tickers")
    
    def check_high_momentum(self, result):
        """Check if result has high momentum worthy of alert"""
        momentum = abs(result.get('momentum', 0))
        score = result.get('score', 0)
        ticker = result.get('ticker', '')
        
        # Filter out negative momentum tickers from high momentum (long) alerts
        direction = result.get('direction', 'LONG')
        if direction == 'LONG' and ticker in self.negative_momentum_tickers:
            self.logger.debug(f"Filtering out {ticker} from high momentum alert - ticker is in negative momentum list")
            return False
        
        # Check momentum and score thresholds
        return momentum >= self.momentum_threshold and score >= self.score_threshold
    
    def log_result(self, result):
        """Override to add daily Telegram alerts"""
        # Call parent method for standard logging
        super().log_result(result)
        
        # Only process daily alerts if enabled
        if not self.daily_alerts_enabled:
            return
        
        # Filter out short signals if disabled
        if not self.enable_short_alerts:
            direction = result.get('direction', 'LONG')
            if direction == 'SHORT':
                self.logger.debug(f"Skipping SHORT signal for {result.get('ticker', '')} - short alerts disabled")
                return
        
        # Check for high momentum (daily)
        if self.check_high_momentum(result):
            ticker = result.get('ticker', '')
            
            if ticker not in self.daily_alerts_sent:
                self.logger.info(f"🔥 HIGH MOMENTUM DETECTED: {ticker} - Score: {result['score']}, Momentum: {result['momentum']:.1f}%")
                self.daily_alerts_sent.add(ticker)
                
                if self.batch_alerts:
                    self.daily_batch.append(result)
                    self._check_batch_alerts('daily')
                else:
                    # Send individual alert
                    if self.telegram.is_configured():
                        success = self.telegram.send_momentum_alert(result)
                        if success:
                            self.daily_alerts_count += 1
    
    def _send_daily_batch_alert(self):
        """Send batch alert for daily signals"""
        if not self.daily_batch:
            return
        
        # Sort by score
        sorted_batch = sorted(self.daily_batch, key=lambda x: x['score'], reverse=True)
        
        message = f"""📊 <b>Daily VSR Batch Alert</b> 📊
<b>{len(sorted_batch)} High Momentum Signals</b>

"""
        
        for result in sorted_batch[:10]:  # Top 10
            ticker = result['ticker']
            score = result['score']
            momentum = result['momentum']
            
            message += f"• <b>{ticker}</b> - Score: {score}, Mom: {momentum:.1f}%\n"
        
        if len(sorted_batch) > 10:
            message += f"\n<i>...and {len(sorted_batch) - 10} more signals</i>"
        
        message += f"\n\n⏰ {datetime.now().strftime('%I:%M %p')}"
        
        self.telegram.send_message(message)
        self.logger.info(f"Sent daily batch alert with {len(sorted_batch)} tickers")
    
    def run_monitoring_cycle(self):
        """Run a complete monitoring cycle"""
        try:
            # Refresh negative momentum tickers periodically (every hour)
            current_time = datetime.now()
            if not hasattr(self, '_last_refresh_time'):
                self._last_refresh_time = current_time
            
            if (current_time - self._last_refresh_time).total_seconds() >= 3600:  # Every hour
                self._load_negative_momentum_tickers()
                self._last_refresh_time = current_time
            
            # Check hourly VSR scans
            self.check_hourly_vsr_scans()
            
            # Run normal VSR tracking (daily)
            if self.daily_alerts_enabled:
                super().run_tracking_cycle()
            
            # Send any pending batch alerts
            if self.batch_alerts:
                self._check_batch_alerts('hourly')
                self._check_batch_alerts('daily')
                
        except Exception as e:
            self.logger.error(f"Error in monitoring cycle: {e}")
    
    def run_continuous_monitoring(self):
        """Run continuous monitoring with hourly checks"""
        self.logger.info("Starting enhanced VSR monitoring with Telegram alerts...")
        
        while True:
            try:
                current_time = datetime.now()
                
                # Check if market hours (9:00 AM to 4:00 PM)
                if 9 <= current_time.hour <= 16:
                    self.run_monitoring_cycle()
                    
                    # Clear sent alerts at start of new day
                    if current_time.hour == 9 and current_time.minute < 5:
                        self.hourly_alerts_sent.clear()
                        self.daily_alerts_sent.clear()
                        self.logger.info("Cleared alert history for new trading day")
                
                # Sleep for 60 seconds
                time.sleep(60)
                
            except KeyboardInterrupt:
                self.logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in continuous monitoring: {e}")
                time.sleep(60)


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced VSR Telegram Alert Service')
    parser.add_argument('-u', '--user', default='Sai', help='User name for tracking')
    args = parser.parse_args()
    
    # Create and run service
    service = EnhancedVSRTelegramService(user_name=args.user)
    
    # Send test alerts if requested
    if False:  # Set to True for testing
        test_hourly = {
            'ticker': 'TEST',
            'vsr_ratio': 3.5,
            'momentum': 5.2,
            'pattern': 'VSR Breakout',
            'score': 85,
            'type': 'hourly',
            'time': datetime.now().strftime('%I:%M %p')
        }
        service._send_hourly_alert(test_hourly)
    
    # Run continuous monitoring
    service.run_continuous_monitoring()


if __name__ == "__main__":
    main()