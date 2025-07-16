#!/usr/bin/env python
"""
VSR Real-Time Monitoring Service
Continuously monitors tickers from Long_Reversal_Daily file for VSR momentum opportunities
Uses 5-minute timeframe for real-time detection
"""

import os
import sys
import time
import logging
import datetime
import json
import glob
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from dateutil.relativedelta import relativedelta

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import required modules
from Daily.scanners.VSR_Momentum_Scanner import (
    load_daily_config,
    calculate_vsr_indicators,
    detect_vsr_momentum,
    get_sector_for_ticker,
    DataCache,
    fetch_data_kite,
    interval_mapping
)

# Initialize logger
def setup_logging(user_name):
    """Set up logging configuration"""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', user_name)
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'vsr_monitor_{user_name}_{datetime.datetime.now().strftime("%Y%m%d")}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

class VSRMonitor:
    """Real-time VSR monitoring service"""
    
    def __init__(self, user_name='Sai', interval='5m', alert_threshold=50):
        self.user_name = user_name
        self.interval = interval
        self.alert_threshold = alert_threshold  # Minimum probability score for alerts
        self.logger = setup_logging(user_name)
        self.data_cache = DataCache()
        
        # Load config
        self.config = load_daily_config(user_name)
        
        # Track alerted tickers to avoid spam
        self.alerted_tickers = {}  # {ticker: last_alert_time}
        self.alert_cooldown = 3600  # 1 hour cooldown between alerts for same ticker
        
        # Output paths
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                      'alerts', user_name, 'vsr_monitor')
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.logger.info(f"VSR Monitor initialized - User: {user_name}, Interval: {interval}, Alert Threshold: {alert_threshold}")
    
    def get_latest_long_reversal_tickers(self):
        """Get tickers from latest Long_Reversal_Daily file"""
        try:
            results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
            long_reversal_files = glob.glob(os.path.join(results_dir, "Long_Reversal_Daily_*.xlsx"))
            
            if not long_reversal_files:
                self.logger.error("No Long_Reversal_Daily files found")
                return []
            
            # Sort by timestamp (newest first)
            def extract_timestamp(filename):
                try:
                    basename = os.path.basename(filename)
                    timestamp_part = basename.replace("Long_Reversal_Daily_", "").replace(".xlsx", "")
                    parts = timestamp_part.split("_")
                    if len(parts) == 2:
                        date_part, time_part = parts
                        year = int(date_part[:4])
                        month = int(date_part[4:6])
                        day = int(date_part[6:8])
                        hour = int(time_part[:2])
                        minute = int(time_part[2:4])
                        second = int(time_part[4:6])
                        return datetime.datetime(year, month, day, hour, minute, second)
                except Exception:
                    return datetime.datetime.fromtimestamp(os.path.getmtime(filename))
                
                return datetime.datetime.fromtimestamp(os.path.getmtime(filename))
            
            long_reversal_files.sort(key=extract_timestamp, reverse=True)
            latest_file = long_reversal_files[0]
            
            # Check if file is from today
            file_timestamp = extract_timestamp(latest_file)
            if file_timestamp.date() != datetime.datetime.now().date():
                self.logger.warning(f"Latest Long_Reversal_Daily file is from {file_timestamp.date()}, not today")
            
            # Read tickers
            df = pd.read_excel(latest_file)
            tickers = df['Ticker'].dropna().tolist()
            
            self.logger.info(f"Loaded {len(tickers)} tickers from {os.path.basename(latest_file)}")
            return tickers
            
        except Exception as e:
            self.logger.error(f"Error reading Long_Reversal_Daily file: {e}")
            return []
    
    def analyze_ticker(self, ticker):
        """Analyze a single ticker for VSR momentum"""
        try:
            now = datetime.datetime.now()
            
            # Fetch data based on interval
            if self.interval == '5m':
                # For 5-minute data, fetch last 2 days
                from_date = (now - relativedelta(days=2)).strftime('%Y-%m-%d')
            elif self.interval == '15m':
                # For 15-minute data, fetch last 5 days
                from_date = (now - relativedelta(days=5)).strftime('%Y-%m-%d')
            else:
                # Default to 10 days
                from_date = (now - relativedelta(days=10)).strftime('%Y-%m-%d')
            
            to_date = now.strftime('%Y-%m-%d')
            
            # Fetch data
            data = fetch_data_kite(ticker, interval_mapping.get(self.interval, '5minute'), 
                                 from_date, to_date)
            
            if data.empty:
                return None
            
            # Calculate VSR indicators
            data_with_indicators = calculate_vsr_indicators(data)
            if data_with_indicators is None:
                return None
            
            # Detect VSR momentum pattern
            vsr_pattern = detect_vsr_momentum(data_with_indicators)
            
            if vsr_pattern and vsr_pattern['probability_score'] >= self.alert_threshold:
                # Get sector
                sector = get_sector_for_ticker(ticker)
                
                # Prepare alert data
                alert_data = {
                    'timestamp': now.isoformat(),
                    'ticker': ticker,
                    'sector': sector,
                    'pattern': vsr_pattern['pattern'],
                    'probability_score': vsr_pattern['probability_score'],
                    'vsr_ratio': vsr_pattern['vsr_ratio'],
                    'vsr_roc': vsr_pattern['vsr_roc'],
                    'entry_price': vsr_pattern['entry_price'],
                    'stop_loss': vsr_pattern['stop_loss'],
                    'target1': vsr_pattern['target1'],
                    'target2': vsr_pattern['target2'],
                    'climax_score': vsr_pattern['climax_score'],
                    'buying_climax': vsr_pattern.get('buying_climax_count', 0),
                    'selling_climax': vsr_pattern.get('selling_climax_count', 0),
                    'has_divergence': vsr_pattern.get('has_pos_divergence', False) or vsr_pattern.get('has_neg_divergence', False),
                    'description': vsr_pattern['description']
                }
                
                return alert_data
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error analyzing {ticker}: {e}")
            return None
    
    def should_alert(self, ticker):
        """Check if we should send alert for this ticker"""
        if ticker not in self.alerted_tickers:
            return True
        
        last_alert_time = self.alerted_tickers[ticker]
        time_since_alert = time.time() - last_alert_time
        
        return time_since_alert >= self.alert_cooldown
    
    def save_alert(self, alert_data):
        """Save alert to file and manage alerts"""
        ticker = alert_data['ticker']
        
        # Check cooldown
        if not self.should_alert(ticker):
            return False
        
        # Save to daily alerts file
        today = datetime.datetime.now().strftime("%Y%m%d")
        alerts_file = os.path.join(self.output_dir, f"vsr_alerts_{today}.json")
        
        # Load existing alerts
        existing_alerts = []
        if os.path.exists(alerts_file):
            try:
                with open(alerts_file, 'r') as f:
                    existing_alerts = json.load(f)
            except:
                existing_alerts = []
        
        # Add new alert
        existing_alerts.append(alert_data)
        
        # Save updated alerts
        with open(alerts_file, 'w') as f:
            json.dump(existing_alerts, f, indent=2)
        
        # Update alert tracking
        self.alerted_tickers[ticker] = time.time()
        
        # Also save to latest alerts file for easy access
        latest_file = os.path.join(self.output_dir, "latest_alerts.json")
        
        # Keep only alerts from last 2 hours in latest file
        two_hours_ago = datetime.datetime.now() - datetime.timedelta(hours=2)
        recent_alerts = [a for a in existing_alerts 
                        if datetime.datetime.fromisoformat(a['timestamp']) > two_hours_ago]
        
        with open(latest_file, 'w') as f:
            json.dump(recent_alerts, f, indent=2)
        
        # Log alert
        self.logger.info(f"🚨 ALERT: {ticker} - {alert_data['pattern']} - Score: {alert_data['probability_score']:.1f}")
        
        # Generate HTML dashboard
        self.generate_dashboard(recent_alerts)
        
        return True
    
    def generate_dashboard(self, alerts):
        """Generate HTML dashboard for alerts"""
        dashboard_file = os.path.join(self.output_dir, "vsr_monitor_dashboard.html")
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>VSR Monitor Dashboard</title>
            <meta http-equiv="refresh" content="30">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    background-color: #f5f5f5;
                }}
                .header {{
                    background-color: #2c3e50;
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                }}
                .alert-card {{
                    background: white;
                    padding: 15px;
                    margin: 10px 0;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    border-left: 4px solid #3498db;
                }}
                .high-score {{
                    border-left-color: #e74c3c;
                }}
                .climax-warning {{
                    background-color: #fff3cd;
                    border-left-color: #ffc107;
                }}
                .ticker-name {{
                    font-size: 1.2em;
                    font-weight: bold;
                    color: #2c3e50;
                }}
                .score {{
                    float: right;
                    font-size: 1.1em;
                    font-weight: bold;
                }}
                .details {{
                    margin-top: 10px;
                    display: grid;
                    grid-template-columns: repeat(4, 1fr);
                    gap: 10px;
                }}
                .timestamp {{
                    color: #7f8c8d;
                    font-size: 0.9em;
                }}
                .no-alerts {{
                    text-align: center;
                    padding: 50px;
                    color: #7f8c8d;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🔍 VSR Real-Time Monitor</h1>
                <p>Last Update: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Monitoring {len(self.get_latest_long_reversal_tickers())} tickers | Interval: {self.interval} | Alert Threshold: {self.alert_threshold}</p>
            </div>
        """
        
        if alerts:
            # Sort by timestamp (newest first)
            alerts.sort(key=lambda x: x['timestamp'], reverse=True)
            
            for alert in alerts:
                # Determine card class
                card_class = "alert-card"
                if alert['probability_score'] >= 70:
                    card_class += " high-score"
                if alert.get('buying_climax', 0) > 0 or alert.get('selling_climax', 0) > 0:
                    card_class += " climax-warning"
                
                # Format timestamp
                alert_time = datetime.datetime.fromisoformat(alert['timestamp'])
                time_ago = self.format_time_ago(alert_time)
                
                html_content += f"""
                <div class="{card_class}">
                    <div>
                        <span class="ticker-name">{alert['ticker']} - {alert['sector']}</span>
                        <span class="score" style="color: {'#e74c3c' if alert['probability_score'] >= 70 else '#3498db'}">
                            Score: {alert['probability_score']:.0f}
                        </span>
                    </div>
                    <div class="timestamp">{time_ago} | {alert['pattern']}</div>
                    <p style="margin: 10px 0; font-style: italic; color: #7f8c8d;">"{alert['description']}"</p>
                    <div class="details">
                        <div>
                            <strong>VSR Ratio:</strong> {alert['vsr_ratio']:.2f}x<br>
                            <strong>VSR ROC:</strong> {alert['vsr_roc']:.1f}%
                        </div>
                        <div>
                            <strong>Entry:</strong> ₹{alert['entry_price']:.2f}<br>
                            <strong>Stop:</strong> ₹{alert['stop_loss']:.2f}
                        </div>
                        <div>
                            <strong>Target 1:</strong> ₹{alert['target1']:.2f}<br>
                            <strong>Target 2:</strong> ₹{alert['target2']:.2f}
                        </div>
                        <div>
                            <strong>Climax Score:</strong> {alert['climax_score']}<br>
                            <strong>Divergence:</strong> {'Yes' if alert['has_divergence'] else 'No'}
                        </div>
                    </div>
                """
                
                # Add warnings
                if alert.get('buying_climax', 0) > 0:
                    html_content += '<p style="color: #e74c3c; margin-top: 10px;">⚠️ BUYING CLIMAX detected - potential exhaustion!</p>'
                if alert.get('selling_climax', 0) > 0:
                    html_content += '<p style="color: #e74c3c; margin-top: 10px;">⚠️ SELLING CLIMAX detected - potential capitulation!</p>'
                
                html_content += "</div>"
        else:
            html_content += '<div class="no-alerts">No alerts in the last 2 hours</div>'
        
        html_content += """
        </body>
        </html>
        """
        
        with open(dashboard_file, 'w') as f:
            f.write(html_content)
    
    def format_time_ago(self, timestamp):
        """Format timestamp as 'X minutes ago' style"""
        now = datetime.datetime.now()
        diff = now - timestamp
        
        if diff.total_seconds() < 60:
            return "Just now"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
    
    def run_scan_cycle(self):
        """Run a single scan cycle"""
        self.logger.info("Starting scan cycle...")
        
        # Get latest tickers
        tickers = self.get_latest_long_reversal_tickers()
        if not tickers:
            self.logger.warning("No tickers to monitor")
            return
        
        alerts_found = 0
        
        for ticker in tickers:
            try:
                alert_data = self.analyze_ticker(ticker)
                
                if alert_data:
                    if self.save_alert(alert_data):
                        alerts_found += 1
                        self.logger.info(f"✓ {ticker}: {alert_data['pattern']} (Score: {alert_data['probability_score']:.1f})")
                else:
                    self.logger.debug(f"  {ticker}: No pattern or below threshold")
                    
                # Small delay to avoid API rate limits
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Error processing {ticker}: {e}")
                continue
        
        self.logger.info(f"Scan cycle complete. {alerts_found} new alerts found.")
    
    def run(self):
        """Main service loop"""
        self.logger.info("VSR Monitor Service started")
        
        while True:
            try:
                # Run scan cycle
                start_time = time.time()
                self.run_scan_cycle()
                scan_duration = time.time() - start_time
                
                # Calculate sleep time
                if self.interval == '5m':
                    sleep_time = max(300 - scan_duration, 60)  # 5 minutes minus scan time, min 1 minute
                elif self.interval == '15m':
                    sleep_time = max(900 - scan_duration, 60)  # 15 minutes
                else:
                    sleep_time = 300  # Default 5 minutes
                
                self.logger.info(f"Sleeping for {sleep_time:.0f} seconds until next cycle...")
                time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                self.logger.info("Service stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(60)  # Wait a minute before retrying

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='VSR Real-Time Monitoring Service')
    parser.add_argument('-u', '--user', default='Sai', help='User name for credentials')
    parser.add_argument('-i', '--interval', default='5m', choices=['5m', '15m', '30m'], 
                       help='Timeframe interval for analysis')
    parser.add_argument('-t', '--threshold', type=int, default=50, 
                       help='Minimum probability score for alerts (default: 50)')
    
    args = parser.parse_args()
    
    # Create and run monitor
    monitor = VSRMonitor(user_name=args.user, interval=args.interval, alert_threshold=args.threshold)
    monitor.run()

if __name__ == "__main__":
    main()