#!/usr/bin/env python3
"""
Persistence Level Tracker Service
Tracks ticker persistence levels and sends Telegram notifications for level transitions
"""

import os
import sys
import json
import time
import logging
import datetime
import requests
from typing import Dict, List, Optional, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from user_context_manager import UserContextManager

# Persistence level definitions
PERSISTENCE_LEVELS = {
    'Extreme': {
        'min': 75, 
        'max': float('inf'), 
        'emoji': '🔥',
        'position_size': '12.5%',
        'win_rate': '100%',
        'avg_return': '9.68%',
        'action': 'MAXIMUM POSITION',
        'priority': 5
    },
    'Very High': {
        'min': 51, 
        'max': 75, 
        'emoji': '⚡',
        'position_size': '10%',
        'win_rate': '100%',
        'avg_return': '5.73%',
        'action': 'PREMIUM POSITION',
        'priority': 4
    },
    'High': {
        'min': 26, 
        'max': 50, 
        'emoji': '🚀',
        'position_size': '7.5%',
        'win_rate': '88.9%',
        'avg_return': '2.72%',
        'action': 'ENHANCED POSITION',
        'priority': 3
    },
    'Medium': {
        'min': 11, 
        'max': 25, 
        'emoji': '📈',
        'position_size': '5%',
        'win_rate': '76.5%',
        'avg_return': '1.49%',
        'action': 'STANDARD POSITION',
        'priority': 2
    },
    'Low': {
        'min': 1, 
        'max': 10, 
        'emoji': '📊',
        'position_size': '2.5%',
        'win_rate': '45.2%',
        'avg_return': '0.28%',
        'action': 'MINIMAL/AVOID',
        'priority': 1
    }
}

class PersistenceLevelTracker:
    def __init__(self, user_name: str = 'Sai'):
        """Initialize the persistence level tracker"""
        self.user_name = user_name
        self.ucm = UserContextManager()
        
        # Setup logging
        self.setup_logging()
        
        # Initialize paths
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(self.base_dir, 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Persistence files
        self.persistence_file = os.path.join(self.data_dir, 'vsr_ticker_persistence_hourly_long.json')
        self.history_file = os.path.join(self.data_dir, 'persistence_level_changes.json')
        self.notification_log = os.path.join(self.data_dir, 'persistence_notifications.json')
        
        # Load existing data
        self.persistence_data = self.load_persistence_data()
        self.level_history = self.load_level_history()
        self.notification_history = self.load_notification_history()
        
        # Telegram settings
        self.setup_telegram()
        
        self.logger.info(f"Persistence Level Tracker initialized for {user_name}")
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'persistence_tracker')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'persistence_tracker_{datetime.date.today().strftime("%Y%m%d")}.log')
        
        # Create logger
        self.logger = logging.getLogger('PersistenceTracker')
        self.logger.setLevel(logging.INFO)
        
        # File handler
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        # Add handlers
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
    
    def setup_telegram(self):
        """Setup Telegram configuration"""
        try:
            config_path = os.path.join(self.base_dir, 'config.ini')
            import configparser
            config = configparser.ConfigParser()
            config.read(config_path)
            
            # Get Telegram settings
            self.telegram_enabled = config.getboolean('TELEGRAM', 'enabled', fallback=True)
            self.bot_token = config.get('TELEGRAM', 'bot_token', fallback='')
            self.chat_id = config.get('TELEGRAM', 'chat_id', fallback='')
            
            if not self.bot_token or not self.chat_id:
                self.telegram_enabled = False
                self.logger.warning("Telegram credentials not found, notifications disabled")
            else:
                self.logger.info("Telegram notifications enabled")
                
        except Exception as e:
            self.telegram_enabled = False
            self.logger.error(f"Error setting up Telegram: {e}")
    
    def load_persistence_data(self) -> Dict:
        """Load current persistence data"""
        if os.path.exists(self.persistence_file):
            try:
                with open(self.persistence_file, 'r') as f:
                    data = json.load(f)
                    # Handle new format with 'tickers' key
                    if 'tickers' in data:
                        return data['tickers']
                    return data
            except Exception as e:
                self.logger.error(f"Error loading persistence data: {e}")
        return {}
    
    def load_level_history(self) -> Dict:
        """Load persistence level change history"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading level history: {e}")
        return {}
    
    def load_notification_history(self) -> Dict:
        """Load notification history"""
        if os.path.exists(self.notification_log):
            try:
                with open(self.notification_log, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading notification history: {e}")
        return {}
    
    def save_level_history(self):
        """Save level history to file"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.level_history, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving level history: {e}")
    
    def save_notification_history(self):
        """Save notification history to file"""
        try:
            with open(self.notification_log, 'w') as f:
                json.dump(self.notification_history, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving notification history: {e}")
    
    def get_persistence_level(self, alert_count: int) -> Tuple[str, Dict]:
        """Determine persistence level based on alert count"""
        for level, criteria in PERSISTENCE_LEVELS.items():
            if criteria['min'] <= alert_count <= criteria['max']:
                return level, criteria
        return 'Low', PERSISTENCE_LEVELS['Low']
    
    def send_telegram_notification(self, message: str, parse_mode: str = 'HTML'):
        """Send Telegram notification"""
        if not self.telegram_enabled:
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                self.logger.info("Telegram notification sent successfully")
                return True
            else:
                self.logger.error(f"Failed to send Telegram notification: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending Telegram notification: {e}")
            return False
    
    def format_transition_message(self, ticker: str, from_level: str, to_level: str, 
                                 alert_count: int, price: float = None) -> str:
        """Format transition notification message"""
        from_info = PERSISTENCE_LEVELS.get(from_level, PERSISTENCE_LEVELS['Low'])
        to_info = PERSISTENCE_LEVELS.get(to_level, PERSISTENCE_LEVELS['Low'])
        
        # Determine if this is an upgrade or downgrade
        is_upgrade = to_info['priority'] > from_info['priority']
        
        if is_upgrade:
            title = f"🎯 PERSISTENCE UPGRADE: {ticker}"
            action_emoji = "⬆️"
        else:
            title = f"⚠️ PERSISTENCE DOWNGRADE: {ticker}"
            action_emoji = "⬇️"
        
        message = f"<b>{title}</b>\n\n"
        message += f"{action_emoji} <b>Level Change:</b> {from_level} → {to_level}\n"
        message += f"{to_info['emoji']} <b>New Level:</b> {to_level}\n"
        message += f"📊 <b>Alert Count:</b> {alert_count} alerts\n"
        
        if price:
            message += f"💰 <b>Current Price:</b> ₹{price:.2f}\n"
        
        message += f"\n<b>📈 New Position Parameters:</b>\n"
        message += f"• Position Size: {to_info['position_size']}\n"
        message += f"• Expected Win Rate: {to_info['win_rate']}\n"
        message += f"• Expected Return: {to_info['avg_return']}\n"
        message += f"• Action: {to_info['action']}\n"
        
        if is_upgrade and to_info['priority'] >= 3:  # High or above
            message += f"\n✅ <b>SCALE IN OPPORTUNITY</b>"
            message += f"\nConsider adding to position"
        elif not is_upgrade and to_info['priority'] <= 2:  # Medium or below
            message += f"\n⚠️ <b>CONSIDER REDUCING</b>"
            message += f"\nMomentum weakening"
        
        message += f"\n\n🕐 {datetime.datetime.now().strftime('%H:%M:%S IST')}"
        
        return message
    
    def check_and_notify_transitions(self):
        """Check for persistence level transitions and send notifications"""
        transitions = []
        current_persistence = self.load_persistence_data()
        
        for ticker, data in current_persistence.items():
            alert_count = data.get('alert_count', 0)
            current_level, level_info = self.get_persistence_level(alert_count)
            
            # Check if we have history for this ticker
            if ticker in self.level_history:
                previous_level = self.level_history[ticker].get('level')
                previous_count = self.level_history[ticker].get('alert_count', 0)
                
                # Check if level has changed
                if previous_level and previous_level != current_level:
                    # Get current price if available
                    price = data.get('last_price')
                    
                    # Create transition record
                    transition = {
                        'ticker': ticker,
                        'from_level': previous_level,
                        'to_level': current_level,
                        'from_count': previous_count,
                        'to_count': alert_count,
                        'price': price,
                        'timestamp': datetime.datetime.now().isoformat()
                    }
                    
                    transitions.append(transition)
                    
                    # Send notification
                    message = self.format_transition_message(
                        ticker, previous_level, current_level, alert_count, price
                    )
                    
                    if self.send_telegram_notification(message):
                        # Log notification
                        if ticker not in self.notification_history:
                            self.notification_history[ticker] = []
                        
                        self.notification_history[ticker].append({
                            'type': 'level_change',
                            'from': previous_level,
                            'to': current_level,
                            'timestamp': datetime.datetime.now().isoformat()
                        })
                    
                    self.logger.info(f"Level transition: {ticker} {previous_level} → {current_level} ({alert_count} alerts)")
            
            # Update history
            self.level_history[ticker] = {
                'level': current_level,
                'alert_count': alert_count,
                'last_updated': datetime.datetime.now().isoformat()
            }
        
        # Save updated history
        if transitions:
            self.save_level_history()
            self.save_notification_history()
        
        return transitions
    
    def send_daily_summary(self):
        """Send daily summary of persistence levels"""
        try:
            persistence_data = self.load_persistence_data()
            
            # Calculate distribution
            distribution = {}
            ticker_lists = {}
            
            for level in PERSISTENCE_LEVELS.keys():
                distribution[level] = 0
                ticker_lists[level] = []
            
            for ticker, data in persistence_data.items():
                alert_count = data.get('alert_count', 0)
                level, _ = self.get_persistence_level(alert_count)
                distribution[level] += 1
                ticker_lists[level].append((ticker, alert_count))
            
            # Sort ticker lists by alert count
            for level in ticker_lists:
                ticker_lists[level].sort(key=lambda x: x[1], reverse=True)
            
            # Format message
            message = "<b>📊 PERSISTENCE LEVEL SUMMARY</b>\n"
            message += f"<i>{datetime.datetime.now().strftime('%Y-%m-%d %H:%M IST')}</i>\n\n"
            
            total_tickers = sum(distribution.values())
            message += f"<b>Total Tracked Tickers:</b> {total_tickers}\n\n"
            
            for level in ['Extreme', 'Very High', 'High', 'Medium', 'Low']:
                info = PERSISTENCE_LEVELS[level]
                count = distribution[level]
                
                if count > 0:
                    message += f"{info['emoji']} <b>{level}:</b> {count} tickers\n"
                    
                    # Show top 3 tickers for high levels
                    if level in ['Extreme', 'Very High', 'High'] and ticker_lists[level]:
                        message += f"   Top: "
                        top_tickers = ticker_lists[level][:3]
                        ticker_str = ", ".join([f"{t[0]} ({t[1]})" for t in top_tickers])
                        message += f"{ticker_str}\n"
                    
                    message += f"   Position: {info['position_size']} | "
                    message += f"Win: {info['win_rate']} | "
                    message += f"Return: {info['avg_return']}\n\n"
            
            # Add recommendations
            if ticker_lists['Extreme'] or ticker_lists['Very High']:
                message += "\n✅ <b>HIGH PRIORITY TICKERS</b>\n"
                all_high_priority = ticker_lists['Extreme'] + ticker_lists['Very High']
                all_high_priority.sort(key=lambda x: x[1], reverse=True)
                
                for ticker, count in all_high_priority[:5]:
                    level, info = self.get_persistence_level(count)
                    message += f"{info['emoji']} {ticker}: {count} alerts - {info['action']}\n"
            
            self.send_telegram_notification(message)
            self.logger.info("Daily summary sent")
            
        except Exception as e:
            self.logger.error(f"Error sending daily summary: {e}")
    
    def run(self):
        """Main run loop"""
        self.logger.info("Starting Persistence Level Tracker")
        
        last_check = datetime.datetime.now()
        last_summary = datetime.datetime.now()
        
        while True:
            try:
                current_time = datetime.datetime.now()
                
                # Check every 5 minutes
                if (current_time - last_check).seconds >= 300:
                    self.check_and_notify_transitions()
                    last_check = current_time
                
                # Send daily summary at market close
                if current_time.hour == 15 and current_time.minute == 30:
                    if (current_time - last_summary).seconds >= 3600:
                        self.send_daily_summary()
                        last_summary = current_time
                
                time.sleep(60)  # Check every minute
                
            except KeyboardInterrupt:
                self.logger.info("Persistence tracker stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(60)

if __name__ == "__main__":
    tracker = PersistenceLevelTracker(user_name='Sai')
    tracker.run()