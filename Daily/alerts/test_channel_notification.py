#!/usr/bin/env python3
"""
Test script to verify Telegram channel notifications
"""

import sys
import os
import logging
from datetime import datetime
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alerts.telegram_notifier import TelegramNotifier

def test_channel_notification():
    """Test sending notification to Telegram channel"""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    # Create notifier (will read from config.ini)
    notifier = TelegramNotifier()
    
    # Check configuration
    logger.info(f"Bot configured: {notifier.is_configured()}")
    logger.info(f"Chat ID: {notifier.chat_id}")
    logger.info(f"Bot Name: {notifier.bot_name}")
    
    if not notifier.is_configured():
        logger.error("Telegram not configured properly")
        return False
    
    # Get current time in IST
    IST = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(IST).strftime('%H:%M:%S IST')
    
    # Send test message
    test_message = f"""
🔔 *CHANNEL NOTIFICATION TEST* 🔔

This is a test message to verify Telegram channel notifications are working correctly.

*Channel ID:* `{notifier.chat_id}`
*Bot Name:* {notifier.bot_name}
*Time:* {current_time}

✅ If you see this message, channel notifications are configured successfully!
"""
    
    logger.info("Sending test message to channel...")
    success = notifier.send_message(test_message, parse_mode='Markdown')
    
    if success:
        logger.info("✅ Test message sent successfully to channel!")
        
        # Test HTML formatting as well
        html_message = """
<b>🔔 HTML FORMAT TEST 🔔</b>

Testing <b>bold</b>, <i>italic</i>, and <code>monospace</code> formatting.

<pre>
Code block test
Line 2 of code
</pre>

✅ HTML formatting test complete!
"""
        
        logger.info("Testing HTML format...")
        html_success = notifier.send_message(html_message, parse_mode='HTML')
        
        if html_success:
            logger.info("✅ HTML format test successful!")
        else:
            logger.error("❌ HTML format test failed")
            
    else:
        logger.error("❌ Failed to send test message to channel")
    
    return success

if __name__ == "__main__":
    test_channel_notification()