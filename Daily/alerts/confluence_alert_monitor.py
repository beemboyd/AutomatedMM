#!/usr/bin/env python3
"""
Confluence Alert Monitor
Monitors hourly-daily confluence and generates actionable alerts
Can be run via cron/plist every 30 minutes during market hours
"""

import os
import sys
import json
import datetime
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.hourly_daily_confluence_analyzer import HourlyDailyConfluenceAnalyzer

class ConfluenceAlertMonitor:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.alerts_dir = os.path.join(self.base_dir, 'alerts')
        os.makedirs(self.alerts_dir, exist_ok=True)
        
        # Setup logging
        self.setup_logging()
        
        # State tracking
        self.state_file = os.path.join(self.alerts_dir, 'confluence_monitor_state.json')
        self.state = self.load_state()
        
    def setup_logging(self):
        """Setup logging for alerts"""
        log_file = os.path.join(self.alerts_dir, f'confluence_alerts_{datetime.datetime.now().strftime("%Y%m%d")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_state(self):
        """Load previous state to track transitions"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            'last_hourly_tickers': set(),
            'last_daily_tickers': set(),
            'alerted_confluences': {},
            'last_check': None
        }
    
    def save_state(self):
        """Save current state"""
        # Convert sets to lists for JSON serialization
        state_to_save = {
            'last_hourly_tickers': list(self.state['last_hourly_tickers']),
            'last_daily_tickers': list(self.state['last_daily_tickers']),
            'alerted_confluences': self.state['alerted_confluences'],
            'last_check': datetime.datetime.now().isoformat()
        }
        
        with open(self.state_file, 'w') as f:
            json.dump(state_to_save, f, indent=2)
    
    def check_for_alerts(self):
        """Check for new alert conditions"""
        analyzer = HourlyDailyConfluenceAnalyzer()
        results = analyzer.analyze_confluence()
        
        current_hourly = set(analyzer.hourly_data.get('tickers', {}).keys())
        current_daily = set(analyzer.daily_data.get('tickers', {}).keys())
        
        alerts_generated = []
        
        # 1. New Daily Transitions (Hourly → Daily)
        if self.state['last_hourly_tickers'] and self.state['last_daily_tickers']:
            # Tickers that were in hourly but not daily, now in daily
            previous_hourly_only = self.state['last_hourly_tickers'] - self.state['last_daily_tickers']
            new_to_daily = previous_hourly_only & current_daily
            
            for ticker in new_to_daily:
                alert = {
                    'type': 'TRANSITION',
                    'ticker': ticker,
                    'message': f"✅ {ticker} confirmed - transitioned from hourly to daily tracking",
                    'priority': 'HIGH',
                    'timestamp': datetime.datetime.now().isoformat()
                }
                alerts_generated.append(alert)
                self.logger.info(f"[TRANSITION] {alert['message']}")
        
        # 2. Strong Confluence Alerts (not previously alerted)
        for ticker_data in results['confluence_tickers'][:5]:  # Top 5
            ticker = ticker_data['ticker']
            score = ticker_data['confluence_score']
            
            # Check if we've already alerted for this confluence in the last 24 hours
            last_alert = self.state['alerted_confluences'].get(ticker)
            if last_alert:
                last_alert_time = datetime.datetime.fromisoformat(last_alert)
                if (datetime.datetime.now() - last_alert_time).total_seconds() < 86400:
                    continue
            
            if score > 75 and ticker_data['signal'] in ['STRONG', 'MEDIUM']:
                alert = {
                    'type': 'CONFLUENCE',
                    'ticker': ticker,
                    'message': f"🎯 {ticker} showing strong hourly+daily confluence (Score: {score:.0f}, Signal: {ticker_data['signal']})",
                    'priority': 'HIGH',
                    'timestamp': datetime.datetime.now().isoformat(),
                    'details': {
                        'hourly_appearances': ticker_data['hourly_appearances'],
                        'daily_appearances': ticker_data['daily_appearances'],
                        'avg_momentum': (ticker_data['hourly_momentum_avg'] + ticker_data['daily_momentum_avg']) / 2
                    }
                }
                alerts_generated.append(alert)
                self.logger.info(f"[CONFLUENCE] {alert['message']}")
                self.state['alerted_confluences'][ticker] = datetime.datetime.now().isoformat()
        
        # 3. Emerging Ticker Alerts
        for ticker_data in results['emerging_tickers'][:3]:  # Top 3
            if ticker_data['hourly_strength'] > 80 and ticker_data['hourly_appearances'] >= 3:
                alert = {
                    'type': 'EMERGING',
                    'ticker': ticker_data['ticker'],
                    'message': f"🚀 {ticker_data['ticker']} building strong momentum in hourly scans ({ticker_data['hourly_appearances']} appearances, {ticker_data['hourly_momentum_avg']:.1f}% avg momentum)",
                    'priority': 'MEDIUM',
                    'timestamp': datetime.datetime.now().isoformat()
                }
                alerts_generated.append(alert)
                self.logger.info(f"[EMERGING] {alert['message']}")
        
        # Update state
        self.state['last_hourly_tickers'] = current_hourly
        self.state['last_daily_tickers'] = current_daily
        self.save_state()
        
        # Save alerts
        if alerts_generated:
            self.save_alerts(alerts_generated)
        
        return alerts_generated
    
    def save_alerts(self, alerts):
        """Save alerts to file for dashboard consumption"""
        alerts_file = os.path.join(self.alerts_dir, 'latest_confluence_alerts.json')
        
        # Load existing alerts
        existing_alerts = []
        if os.path.exists(alerts_file):
            try:
                with open(alerts_file, 'r') as f:
                    data = json.load(f)
                    existing_alerts = data.get('alerts', [])
            except:
                pass
        
        # Add new alerts
        existing_alerts.extend(alerts)
        
        # Keep only last 50 alerts
        existing_alerts = existing_alerts[-50:]
        
        # Save
        with open(alerts_file, 'w') as f:
            json.dump({
                'alerts': existing_alerts,
                'last_update': datetime.datetime.now().isoformat(),
                'active_count': len([a for a in existing_alerts if self.is_alert_active(a)])
            }, f, indent=2)
    
    def is_alert_active(self, alert):
        """Check if alert is still active (within last 4 hours)"""
        alert_time = datetime.datetime.fromisoformat(alert['timestamp'])
        return (datetime.datetime.now() - alert_time).total_seconds() < 14400  # 4 hours
    
    def generate_summary(self):
        """Generate summary for logging"""
        analyzer = HourlyDailyConfluenceAnalyzer()
        results = analyzer.analyze_confluence()
        
        self.logger.info("="*60)
        self.logger.info("CONFLUENCE MONITOR SUMMARY")
        self.logger.info("="*60)
        self.logger.info(f"Confluence Tickers: {len(results['confluence_tickers'])}")
        self.logger.info(f"Emerging Tickers: {len(results['emerging_tickers'])}")
        self.logger.info(f"Top Confluences: {', '.join([t['ticker'] for t in results['confluence_tickers'][:5]])}")
        self.logger.info(f"Top Emerging: {', '.join([t['ticker'] for t in results['emerging_tickers'][:3]])}")
        self.logger.info("="*60)

def main():
    """Run alert monitor"""
    # Check if within market hours (9:15 AM - 3:30 PM)
    now = datetime.datetime.now()
    market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    if not (market_start <= now <= market_end):
        print(f"Outside market hours. Current time: {now.strftime('%H:%M')}")
        return
    
    monitor = ConfluenceAlertMonitor()
    monitor.logger.info("Starting confluence alert check...")
    
    # Generate summary
    monitor.generate_summary()
    
    # Check for alerts
    alerts = monitor.check_for_alerts()
    
    if alerts:
        monitor.logger.info(f"Generated {len(alerts)} new alerts")
    else:
        monitor.logger.info("No new alerts generated")
    
    monitor.logger.info("Confluence alert check completed")

if __name__ == "__main__":
    main()