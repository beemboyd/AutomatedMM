#!/usr/bin/env python3
"""
Telegram Notification Service for India-TS
Sends alerts for high momentum tickers via ZTTrending bot
"""

import os
import logging
import requests
import json
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Optional
import configparser
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TelegramNotifier:
    """Handles Telegram notifications for trading alerts"""
    
    def __init__(self, bot_token: str = None, chat_id: str = None, config_file: str = None):
        """
        Initialize Telegram notifier
        
        Args:
            bot_token: Telegram bot token (optional)
            chat_id: Telegram chat ID (optional)
            config_file: Path to config.ini file (optional)
        """
        # Configure logging
        self.logger = logging.getLogger(__name__)
        
        # Load from config.ini if available
        self.config = self._load_config(config_file)
        
        # Priority: direct params > config.ini > environment variables
        self.bot_token = bot_token or self.config.get('bot_token') or os.environ.get('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or self.config.get('chat_id') or os.environ.get('TELEGRAM_CHAT_ID')
        self.bot_name = self.config.get('bot_name', 'ZTTrending')
        
        # Check if enabled
        self.enabled = self.config.get('enabled', 'yes').lower() == 'yes'
        
        # Load thresholds from config
        self.high_momentum_threshold = float(self.config.get('high_momentum_threshold', 10.0))
        self.extreme_momentum_threshold = float(self.config.get('extreme_momentum_threshold', 20.0))
        self.min_score_for_alert = int(self.config.get('min_score_for_alert', 60))
        self.high_score_threshold = int(self.config.get('high_score_threshold', 80))
        
        # Track sent notifications to avoid duplicates
        self.sent_notifications = {}  # ticker -> last_sent_time
        self.notification_cooldown = float(self.config.get('ticker_cooldown_hours', 1.0)) * 3600
        
        # Alert limits
        self.max_alerts_per_hour = int(self.config.get('max_alerts_per_hour', 20))
        self.max_alerts_per_day = int(self.config.get('max_alerts_per_day', 100))
        self.hourly_alert_count = 0
        self.daily_alert_count = 0
        self.last_hour_reset = datetime.now()
        self.last_day_reset = datetime.now()
        
        # IST timezone
        self.IST = pytz.timezone('Asia/Kolkata')
        
        if not self.enabled:
            self.logger.info("Telegram notifications are disabled in config")
        elif not self.bot_token or not self.chat_id:
            self.logger.warning("Telegram credentials not configured. Check config.ini or set environment variables")
    
    def _load_config(self, config_file: str = None) -> Dict:
        """Load configuration from config.ini"""
        config_dict = {}
        
        # Default config file location
        if not config_file:
            config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
        
        if os.path.exists(config_file):
            try:
                config = configparser.ConfigParser()
                config.read(config_file)
                
                if 'TELEGRAM' in config:
                    config_dict = dict(config['TELEGRAM'])
                    self.logger.info(f"Loaded Telegram config from {config_file}")
            except Exception as e:
                self.logger.error(f"Error loading config file: {e}")
        
        return config_dict
    
    def is_configured(self) -> bool:
        """Check if Telegram is properly configured"""
        return bool(self.enabled and self.bot_token and self.chat_id)
    
    def should_send_notification(self, ticker: str) -> bool:
        """Check if we should send notification for this ticker"""
        # Check if enabled
        if not self.enabled:
            return False
        
        # Check rate limits
        if not self._check_rate_limits():
            return False
        
        if ticker not in self.sent_notifications:
            return True
        
        last_sent = self.sent_notifications[ticker]
        current_time = datetime.now()
        
        # Check if cooldown period has passed
        if (current_time - last_sent).total_seconds() > self.notification_cooldown:
            return True
        
        return False
    
    def _check_rate_limits(self) -> bool:
        """Check if we're within rate limits"""
        current_time = datetime.now()
        
        # Reset hourly counter
        if (current_time - self.last_hour_reset).total_seconds() >= 3600:
            self.hourly_alert_count = 0
            self.last_hour_reset = current_time
        
        # Reset daily counter
        if current_time.date() > self.last_day_reset.date():
            self.daily_alert_count = 0
            self.last_day_reset = current_time
        
        # Check limits
        if self.hourly_alert_count >= self.max_alerts_per_hour:
            self.logger.warning(f"Hourly alert limit reached ({self.max_alerts_per_hour})")
            return False
        
        if self.daily_alert_count >= self.max_alerts_per_day:
            self.logger.warning(f"Daily alert limit reached ({self.max_alerts_per_day})")
            return False
        
        return True
    
    def format_momentum_alert(self, ticker_data: Dict) -> str:
        """Format a high momentum alert message"""
        ticker = ticker_data.get('ticker', 'Unknown')
        price = ticker_data.get('price', 0)
        momentum = ticker_data.get('momentum', 0)
        building = ticker_data.get('building', False)
        trend = ticker_data.get('trend', '')
        alerts_last_30_days = ticker_data.get('alerts_last_30_days', 0)  # Alert count in last 30 days
        last_3_alerts = ticker_data.get('last_3_alerts', [])  # Last 3 historical alerts

        # Liquidity information
        liquidity_grade = ticker_data.get('liquidity_grade', ticker_data.get('Liquidity_Grade', 'N/A'))
        avg_turnover_cr = ticker_data.get('avg_turnover_cr', ticker_data.get('Avg_Turnover_Cr', 0))

        # Create emoji indicators
        score_emoji = "🔥"
        trend_emoji = "🚀" if trend == "UP" else "⬆️" if trend == "up" else "➡️"
        building_emoji = "🏗️" if building else ""

        # Liquidity emoji only
        liquidity_emoji = "💎" if liquidity_grade == 'A' else "💧" if liquidity_grade == 'B' else "💦" if liquidity_grade == 'C' else "⚠️" if liquidity_grade in ['D', 'E'] else "❌"
        liquidity_text = f"{liquidity_emoji} ({avg_turnover_cr:.1f} Cr)" if avg_turnover_cr > 0 else liquidity_emoji

        # Format alert history (last 3 occurrences)
        history_section = ""

        if not last_3_alerts or len(last_3_alerts) == 0:
            history_section = "*Alert History:* First alert 🆕"
        else:
            history_section = "*Alert History:*\n"
            try:
                from datetime import datetime as dt
                today = dt.now().date()

                for i, alert in enumerate(last_3_alerts[:3]):  # Max 3
                    alert_date_str = alert.get('date')
                    alert_price = alert.get('price')
                    alert_count = alert.get('count', 1)

                    if not alert_date_str:
                        continue

                    # Format date
                    prev_date = dt.fromisoformat(alert_date_str).date()
                    days_ago = (today - prev_date).days

                    if days_ago == 1:
                        date_text = "Yesterday"
                    elif days_ago == 2:
                        date_text = "2 days ago"
                    elif days_ago <= 7:
                        date_text = f"{days_ago} days ago"
                    else:
                        date_text = prev_date.strftime('%b %d')

                    # Format price and change
                    if alert_price and alert_price > 0:
                        price_change_pct = ((price - alert_price) / alert_price) * 100
                        change_emoji = "📈" if price_change_pct > 0 else "📉" if price_change_pct < 0 else "➡️"
                        price_text = f"₹{alert_price:.2f} {change_emoji} {price_change_pct:+.1f}%"
                    else:
                        price_text = "₹N/A"

                    # Add count if multiple alerts that day
                    count_text = f" ({alert_count}x)" if alert_count > 1 else ""

                    history_section += f"  • {date_text}: {price_text}{count_text}\n"
            except Exception as e:
                history_section = "*Alert History:* N/A"

        # Format the message
        message = f"""
{score_emoji} *HIGH MOMENTUM ALERT* {score_emoji}

*Ticker:* `{ticker}`
{history_section}
*Total Alerts (30d):* {alerts_last_30_days} alerts {building_emoji}
*Current Price:* ₹{price:.2f}
*Momentum:* {momentum:.1f}% {trend_emoji}
*Liquidity:* {liquidity_text}

_Alert from {self.bot_name} at {datetime.now(self.IST).strftime('%H:%M IST')}_
"""

        return message
    
    def format_batch_alert(self, high_momentum_tickers: List[Dict]) -> str:
        """Format multiple high momentum tickers in one message"""
        if not high_momentum_tickers:
            return ""

        # Sort by momentum
        high_momentum_tickers.sort(key=lambda x: x.get('momentum', 0), reverse=True)

        message = f"""
🔥 *HIGH MOMENTUM BATCH ALERT* 🔥
_Found {len(high_momentum_tickers)} high momentum tickers_

"""

        for i, ticker_data in enumerate(high_momentum_tickers[:10], 1):  # Limit to top 10
            ticker = ticker_data.get('ticker', 'Unknown')
            momentum = ticker_data.get('momentum', 0)
            trend = ticker_data.get('trend', '')
            alerts_last_30_days = ticker_data.get('alerts_last_30_days', 0)
            liquidity_grade = ticker_data.get('liquidity_grade', ticker_data.get('Liquidity_Grade', ''))
            penultimate_alert_date = ticker_data.get('penultimate_alert_date')

            trend_emoji = "🚀" if trend == "UP" else "⬆️" if trend == "up" else "➡️"
            liq_emoji = "💎" if liquidity_grade == 'A' else "💧" if liquidity_grade == 'B' else "💦" if liquidity_grade == 'C' else "⚠️" if liquidity_grade in ['D', 'E'] else "❌"

            # Format penultimate alert date for batch
            days_ago_text = ""
            # Only show "First alert" emoji if this is truly the first time in the 30-day window
            # Also check if penultimate_alert_date is None/empty (no previous alert)
            if alerts_last_30_days == 1 or not penultimate_alert_date:
                days_ago_text = "🆕"
            elif penultimate_alert_date:
                try:
                    from datetime import datetime as dt
                    prev_date = dt.fromisoformat(penultimate_alert_date).date()
                    today = dt.now().date()
                    days_ago = (today - prev_date).days
                    if days_ago == 1:
                        days_ago_text = "(Yday)"
                    elif days_ago <= 7:
                        days_ago_text = f"({days_ago}d)"
                except:
                    pass

            message += f"{i}. `{ticker}` {days_ago_text} - Mom: {momentum:.1f}% | {liq_emoji} | {alerts_last_30_days} alerts {trend_emoji}\n"

        message += f"\n_Alert from {self.bot_name} at {datetime.now(self.IST).strftime('%H:%M IST')}_"

        return message
    
    def send_message(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """Send a message via Telegram"""
        if not self.is_configured():
            self.logger.warning("Telegram not configured, skipping notification")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                self.logger.info("Telegram notification sent successfully")
                return True
            else:
                self.logger.error(f"Failed to send Telegram notification: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending Telegram notification: {e}")
            return False
    
    def send_momentum_alert(self, ticker_data: Dict) -> bool:
        """Send high momentum alert for a single ticker"""
        ticker = ticker_data.get('ticker', '')
        
        if not ticker:
            return False
        
        # Check cooldown
        if not self.should_send_notification(ticker):
            self.logger.debug(f"Skipping notification for {ticker} - in cooldown period")
            return False
        
        # Format and send message
        message = self.format_momentum_alert(ticker_data)
        success = self.send_message(message)
        
        if success:
            # Update sent notifications
            self.sent_notifications[ticker] = datetime.now()
            # Update counters
            self.hourly_alert_count += 1
            self.daily_alert_count += 1
        
        return success
    
    def send_batch_momentum_alert(self, high_momentum_tickers: List[Dict]) -> bool:
        """Send batch alert for multiple high momentum tickers"""
        if not high_momentum_tickers:
            return False
        
        # Filter out tickers in cooldown
        new_alerts = []
        for ticker_data in high_momentum_tickers:
            ticker = ticker_data.get('ticker', '')
            if ticker and self.should_send_notification(ticker):
                new_alerts.append(ticker_data)
        
        if not new_alerts:
            self.logger.debug("No new alerts to send - all tickers in cooldown")
            return False
        
        # Format and send message
        message = self.format_batch_alert(new_alerts)
        success = self.send_message(message)
        
        if success:
            # Update sent notifications
            current_time = datetime.now()
            for ticker_data in new_alerts:
                ticker = ticker_data.get('ticker', '')
                if ticker:
                    self.sent_notifications[ticker] = current_time
        
        return success
    
    def send_daily_summary(self, summary_data: Dict) -> bool:
        """Send daily summary of VSR tracking"""
        try:
            total_tracked = summary_data.get('total_tracked', 0)
            high_momentum_count = summary_data.get('high_momentum_count', 0)
            top_gainers = summary_data.get('top_gainers', [])
            
            message = f"""
📊 *VSR DAILY SUMMARY* 📊

*Total Tickers Tracked:* {total_tracked}
*High Momentum Alerts:* {high_momentum_count}

*Top 5 Gainers:*
"""
            
            for i, gainer in enumerate(top_gainers[:5], 1):
                ticker = gainer.get('ticker', 'Unknown')
                momentum = gainer.get('momentum', 0)
                message += f"{i}. `{ticker}` - {momentum:.1f}%\n"
            
            message += f"\n_Summary from {self.bot_name} at {datetime.now(self.IST).strftime('%H:%M IST')}_"
            
            return self.send_message(message)
            
        except Exception as e:
            self.logger.error(f"Error sending daily summary: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test Telegram connection"""
        test_message = f"✅ {self.bot_name} connection test successful!"
        return self.send_message(test_message)


# Example usage and configuration
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Test the notifier
    # You need to set these environment variables:
    # export TELEGRAM_BOT_TOKEN="your_bot_token"
    # export TELEGRAM_CHAT_ID="your_chat_id"
    
    notifier = TelegramNotifier()
    
    if notifier.is_configured():
        # Test connection
        if notifier.test_connection():
            print("✅ Telegram connection successful!")
            
            # Test momentum alert
            test_ticker = {
                'ticker': 'TESTSTOCK',
                'score': 85,
                'vsr': 2.45,
                'price': 1250.50,
                'momentum': 12.5,
                'volume': 1500000,
                'sector': 'Technology',
                'days_tracked': 2,
                'building': True,
                'trend': 'UP'
            }
            
            notifier.send_momentum_alert(test_ticker)
    else:
        print("❌ Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables")