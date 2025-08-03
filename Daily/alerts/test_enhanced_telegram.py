#!/usr/bin/env python3
"""
Test script for Enhanced VSR Telegram Service
"""

import os
import sys
import configparser

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_config():
    """Test configuration loading"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    config = configparser.ConfigParser()
    config.read(config_path)
    
    print("=== Telegram Configuration ===")
    print(f"Config file: {config_path}")
    print("\nTelegram Settings:")
    
    telegram_config = config['TELEGRAM']
    
    # Display all settings
    for key, value in telegram_config.items():
        print(f"  {key}: {value}")
    
    print("\n=== Alert Status ===")
    hourly_on = telegram_config.getboolean('hourly_telegram_on', True)
    daily_on = telegram_config.getboolean('daily_telegram_on', True)
    
    print(f"Hourly Alerts: {'✅ ENABLED' if hourly_on else '❌ DISABLED'}")
    print(f"Daily Alerts: {'✅ ENABLED' if daily_on else '❌ DISABLED'}")
    
    print("\n=== Hourly Thresholds ===")
    print(f"Momentum Threshold: {telegram_config.getfloat('hourly_momentum_threshold', 2.0)}%")
    print(f"VSR Threshold: {telegram_config.getfloat('hourly_vsr_threshold', 2.0)}x")
    
    print("\n=== Daily Thresholds ===")
    print(f"Momentum Threshold: {telegram_config.getfloat('high_momentum_threshold', 10.0)}%")
    print(f"Min Score: {telegram_config.getint('min_score_for_alert', 60)}")

def test_service():
    """Test service initialization"""
    print("\n=== Testing Service Initialization ===")
    
    try:
        from vsr_telegram_service_enhanced import EnhancedVSRTelegramService
        
        # Initialize service
        service = EnhancedVSRTelegramService(user_name='Sai')
        
        print("✅ Service initialized successfully")
        print(f"Hourly alerts enabled: {service.hourly_alerts_enabled}")
        print(f"Daily alerts enabled: {service.daily_alerts_enabled}")
        
        # Test hourly scan check (won't send actual alerts)
        print("\n=== Testing Hourly Scan Check ===")
        service.check_hourly_vsr_scans()
        print("✅ Hourly scan check completed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_config()
    test_service()
    
    print("\n=== Configuration Instructions ===")
    print("To toggle alerts on/off, edit config.ini:")
    print("  hourly_telegram_on = yes/no")
    print("  daily_telegram_on = yes/no")
    print("\nTo adjust thresholds:")
    print("  hourly_momentum_threshold = 2.0  (for hourly alerts)")
    print("  hourly_vsr_threshold = 2.0       (for hourly alerts)")
    print("  high_momentum_threshold = 10.0   (for daily alerts)")
    print("  min_score_for_alert = 60         (for daily alerts)")