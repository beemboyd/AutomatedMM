#!/usr/bin/env python3
"""
Test Telegram connection and send a test alert
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_notifier import TelegramNotifier

def main():
    print("Testing Telegram connection...")
    
    # Initialize notifier (will load from config.ini)
    notifier = TelegramNotifier()
    
    if notifier.is_configured():
        print(f"✅ Telegram configured:")
        print(f"   Bot: {notifier.bot_name}")
        print(f"   Chat ID: {notifier.chat_id}")
        
        # Test connection
        if notifier.test_connection():
            print("✅ Connection test successful!")
            
            # Send a test momentum alert
            test_ticker = {
                'ticker': 'TESTSTOCK',
                'score': 85,
                'vsr': 2.45,
                'price': 1250.50,
                'momentum': 15.5,
                'volume': 1500000,
                'sector': 'Technology',
                'days_tracked': 2,
                'building': True,
                'trend': 'UP'
            }
            
            print("\nSending test momentum alert...")
            if notifier.send_momentum_alert(test_ticker):
                print("✅ Test alert sent successfully!")
                print("\nCheck your Telegram for the alert message.")
            else:
                print("❌ Failed to send test alert")
        else:
            print("❌ Connection test failed")
    else:
        print("❌ Telegram not properly configured")

if __name__ == "__main__":
    main()