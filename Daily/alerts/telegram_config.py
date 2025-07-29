#!/usr/bin/env python3
"""
Telegram Configuration for ZTTrending Bot
Store your bot token and chat ID here or use environment variables
"""

import os
from typing import Dict, Optional

class TelegramConfig:
    """Telegram configuration management"""
    
    @staticmethod
    def get_config() -> Dict[str, Optional[str]]:
        """
        Get Telegram configuration
        
        Priority:
        1. Environment variables (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        2. Config file values
        3. None if not configured
        """
        config = {
            'bot_token': None,
            'chat_id': None,
            'bot_name': 'ZTTrending'
        }
        
        # Try environment variables first
        config['bot_token'] = os.environ.get('TELEGRAM_BOT_TOKEN')
        config['chat_id'] = os.environ.get('TELEGRAM_CHAT_ID')
        
        # If not in environment, you can set them here (NOT RECOMMENDED for production)
        # WARNING: Never commit actual tokens to git!
        if not config['bot_token']:
            # config['bot_token'] = 'YOUR_BOT_TOKEN_HERE'
            pass
        
        if not config['chat_id']:
            # config['chat_id'] = 'YOUR_CHAT_ID_HERE'
            pass
        
        return config
    
    @staticmethod
    def get_alert_settings() -> Dict:
        """Get alert configuration settings"""
        return {
            # Momentum thresholds
            'high_momentum_threshold': 10.0,  # 10% momentum
            'extreme_momentum_threshold': 20.0,  # 20% momentum
            
            # Score thresholds
            'min_score_for_alert': 60,
            'high_score_threshold': 80,
            
            # Cooldown periods (seconds)
            'ticker_cooldown': 3600,  # 1 hour between same ticker alerts
            'batch_interval': 300,    # 5 minutes between batch alerts
            
            # Alert limits
            'max_alerts_per_hour': 20,
            'max_alerts_per_day': 100,
            
            # Market hours (IST)
            'market_open_time': '09:15',
            'market_close_time': '15:30',
            'summary_time': '16:00'
        }
    
    @staticmethod
    def get_message_templates() -> Dict:
        """Get message templates for different alert types"""
        return {
            'high_momentum': """
🔥 *HIGH MOMENTUM ALERT* 🔥

*Ticker:* `{ticker}`
*Score:* {score}/100 {building_emoji}
*VSR:* {vsr:.2f}
*Price:* ₹{price:.2f}
*Momentum:* {momentum:.1f}% {trend_emoji}
*Volume:* {volume:,}
*Sector:* {sector}
*Days Tracked:* {days_tracked}

_Alert from ZTTrending at {time}_
""",
            
            'extreme_momentum': """
🚀 *EXTREME MOMENTUM ALERT* 🚀

⚡ *{ticker}* is showing exceptional momentum! ⚡

*Score:* {score}/100 {building_emoji}
*Momentum:* {momentum:.1f}% {trend_emoji}
*VSR:* {vsr:.2f}
*Price:* ₹{price:.2f}
*Volume:* {volume:,}

_Critical alert from ZTTrending at {time}_
""",
            
            'batch_alert': """
📊 *MOMENTUM BATCH UPDATE* 📊

Found {count} high momentum tickers:

{ticker_list}

_Batch update from ZTTrending at {time}_
""",
            
            'daily_summary': """
📈 *DAILY VSR SUMMARY* 📈

*Date:* {date}
*Total Tracked:* {total_tracked}
*High Momentum Alerts:* {alert_count}

*Top Gainers:*
{top_gainers}

*Market Status:* {market_status}

_Daily summary from ZTTrending_
"""
        }


# Test configuration
if __name__ == "__main__":
    config = TelegramConfig.get_config()
    settings = TelegramConfig.get_alert_settings()
    
    print("Telegram Configuration:")
    print(f"Bot Name: {config['bot_name']}")
    print(f"Bot Token Configured: {'Yes' if config['bot_token'] else 'No'}")
    print(f"Chat ID Configured: {'Yes' if config['chat_id'] else 'No'}")
    
    print("\nAlert Settings:")
    for key, value in settings.items():
        print(f"{key}: {value}")