#!/usr/bin/env python3
"""
VSR Telegram Alert Service
Monitors VSR tracker for high momentum tickers and sends Telegram alerts
"""

import os
import sys
import time
import logging
import json
from datetime import datetime, time as dtime
from typing import Dict, List, Set

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_notifier import TelegramNotifier
from services.vsr_tracker_service_enhanced import EnhancedVSRTracker

class VSRTelegramService(EnhancedVSRTracker):
    """Extended VSR tracker with Telegram notifications"""
    
    def __init__(self, user_name='Sai', 
                 momentum_threshold=10.0,
                 score_threshold=60,
                 batch_alerts=False):
        """
        Initialize VSR Telegram Service
        
        Args:
            user_name: User name for tracking
            momentum_threshold: Minimum momentum % to trigger alert (default: 10%)
            score_threshold: Minimum score to trigger alert (default: 60)
            batch_alerts: If True, send batch alerts instead of individual
        """
        super().__init__(user_name)
        
        # Initialize Telegram notifier (will load from config.ini)
        self.telegram = TelegramNotifier()
        
        # Alert thresholds
        self.momentum_threshold = momentum_threshold
        self.score_threshold = score_threshold
        self.batch_alerts = batch_alerts
        
        # Track high momentum tickers for batch alerts
        self.high_momentum_batch = []
        self.last_batch_time = datetime.now()
        self.batch_interval = 300  # 5 minutes between batch alerts
        
        # Daily summary tracking
        self.daily_alerts_count = 0
        self.daily_top_gainers = []
        
        self.logger.info(f"VSR Telegram Service initialized - Momentum threshold: {momentum_threshold}%, Score threshold: {score_threshold}")
        
        # Test Telegram connection
        if self.telegram.is_configured():
            if self.telegram.test_connection():
                self.logger.info("✅ Telegram connection successful")
            else:
                self.logger.error("❌ Telegram connection failed")
        else:
            self.logger.warning("⚠️ Telegram not configured - alerts will be logged only")
    
    def check_high_momentum(self, result: Dict) -> bool:
        """Check if ticker meets high momentum criteria"""
        score = result.get('score', 0)
        momentum = result.get('momentum', 0)
        building = result.get('building', False)
        
        # Check thresholds
        if score >= self.score_threshold and momentum >= self.momentum_threshold:
            # Extra criteria for stronger signals
            if score >= 80 or (score >= 70 and building):
                return True
            # For lower scores, require higher momentum
            if score >= 60 and momentum >= self.momentum_threshold * 1.5:
                return True
        
        return False
    
    def log_result(self, result):
        """Override to add Telegram alerts"""
        # Call parent method for standard logging
        super().log_result(result)
        
        # Check for high momentum
        if self.check_high_momentum(result):
            ticker = result.get('ticker', '')
            self.logger.info(f"🔥 HIGH MOMENTUM DETECTED: {ticker} - Score: {result['score']}, Momentum: {result['momentum']:.1f}%")
            
            if self.batch_alerts:
                # Add to batch
                self.high_momentum_batch.append(result)
            else:
                # Send individual alert
                if self.telegram.is_configured():
                    success = self.telegram.send_momentum_alert(result)
                    if success:
                        self.daily_alerts_count += 1
            
            # Track top gainers
            self.update_top_gainers(result)
    
    def update_top_gainers(self, result: Dict):
        """Update daily top gainers list"""
        self.daily_top_gainers.append({
            'ticker': result.get('ticker', ''),
            'momentum': result.get('momentum', 0),
            'score': result.get('score', 0)
        })
        
        # Keep only top 10 by momentum
        self.daily_top_gainers.sort(key=lambda x: x['momentum'], reverse=True)
        self.daily_top_gainers = self.daily_top_gainers[:10]
    
    def process_batch_alerts(self):
        """Process and send batch alerts if needed"""
        current_time = datetime.now()
        time_since_last_batch = (current_time - self.last_batch_time).total_seconds()
        
        # Send batch if we have alerts and enough time has passed
        if self.high_momentum_batch and time_since_last_batch >= self.batch_interval:
            if self.telegram.is_configured():
                success = self.telegram.send_batch_momentum_alert(self.high_momentum_batch)
                if success:
                    self.daily_alerts_count += len(self.high_momentum_batch)
            
            # Clear batch
            self.high_momentum_batch = []
            self.last_batch_time = current_time
    
    def run_tracking_cycle(self):
        """Override to add batch processing"""
        # Call parent method
        super().run_tracking_cycle()
        
        # Process batch alerts if enabled
        if self.batch_alerts:
            self.process_batch_alerts()
    
    def send_daily_summary(self):
        """Send daily summary via Telegram"""
        if not self.telegram.is_configured():
            return
        
        summary_data = {
            'total_tracked': len(self.persistence_manager.get_active_tickers()),
            'high_momentum_count': self.daily_alerts_count,
            'top_gainers': self.daily_top_gainers
        }
        
        self.telegram.send_daily_summary(summary_data)
        
        # Reset daily counters
        self.daily_alerts_count = 0
        self.daily_top_gainers = []
    
    def run_continuous(self, interval_seconds=60):
        """Override to add daily summary"""
        self.logger.info(f"[{self.user_name}] VSR Telegram Service started - High momentum alerts enabled")
        
        last_summary_date = datetime.now().date()
        
        while True:
            try:
                now = datetime.now()
                
                # Check if market is open
                if now.weekday() < 5 and dtime(9, 15) <= now.time() <= dtime(15, 30):
                    self.logger.info(f"[{self.user_name}] ━━━ Starting tracking cycle at {now.strftime('%H:%M:%S')} ━━━")
                    self.run_tracking_cycle()
                else:
                    # Send daily summary at end of day
                    if now.date() > last_summary_date and now.hour >= 16:
                        self.send_daily_summary()
                        last_summary_date = now.date()
                    
                    self.logger.info(f"[{self.user_name}] Market closed, waiting...")
                
                # Sleep for the specified interval
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                self.logger.info("Received interrupt signal, shutting down...")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(interval_seconds)


def main():
    """Main function to run the service"""
    import argparse
    
    parser = argparse.ArgumentParser(description='VSR Telegram Alert Service')
    parser.add_argument('--user', '-u', default='Sai', help='User name for tracking')
    parser.add_argument('--momentum-threshold', '-m', type=float, default=10.0, 
                       help='Minimum momentum percentage for alerts (default: 10.0)')
    parser.add_argument('--score-threshold', '-s', type=int, default=60,
                       help='Minimum score for alerts (default: 60)')
    parser.add_argument('--batch', '-b', action='store_true',
                       help='Send batch alerts instead of individual alerts')
    parser.add_argument('--interval', '-i', type=int, default=60,
                       help='Tracking interval in seconds (default: 60)')
    
    args = parser.parse_args()
    
    # Create and run service
    service = VSRTelegramService(
        user_name=args.user,
        momentum_threshold=args.momentum_threshold,
        score_threshold=args.score_threshold,
        batch_alerts=args.batch
    )
    
    try:
        service.run_continuous(interval_seconds=args.interval)
    except KeyboardInterrupt:
        print("\nService stopped by user")
    except Exception as e:
        print(f"Service error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()