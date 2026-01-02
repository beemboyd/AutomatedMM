#!/usr/bin/env python3
"""
Alert Volume Tracker Dashboard
Tracks yesterday's alerts and compares hourly volumes with today's data
Filters to show only tickers with matching or exceeding volumes
"""

import os
import sys
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import re
from typing import Dict, List, Tuple
import pytz
from flask import Flask, render_template_string, jsonify
import threading
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kiteconnect import KiteConnect
from user_context_manager import UserContextManager

# Setup logging
log_dir = Path("/Users/maverick/PycharmProjects/India-TS/Daily/logs/alert_tracker")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f'alert_tracker_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class AlertVolumeTracker:
    def __init__(self, user="Sai"):
        self.user = user
        self.kite = None
        self.yesterday_alerts = []
        self.volume_data = {}
        self.filtered_tickers = []
        self.last_update = None
        self.ist = pytz.timezone('Asia/Kolkata')
        self.data_dir = Path("/Users/maverick/PycharmProjects/India-TS/Daily/data/alert_tracker")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.initialize_kite()
        
    def initialize_kite(self):
        """Initialize Kite connection"""
        try:
            context_manager = UserContextManager()
            self.kite = context_manager.get_kite_instance(self.user)
            logger.info(f"Kite connection initialized for user: {self.user}")
        except Exception as e:
            logger.error(f"Failed to initialize Kite: {e}")
            
    def parse_alert_logs(self, date=None):
        """Parse yesterday's alert logs to extract tickers and alert details"""
        if date is None:
            date = (datetime.now(self.ist) - timedelta(days=1)).strftime("%Y-%m-%d")
            
        alerts = []
        
        # Parse VSR telegram logs
        vsr_log_dir = Path("/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_telegram")
        vsr_pattern = re.compile(
            rf"{date}.*HIGH MOMENTUM DETECTED: (\w+) - Score: (\d+), Momentum: ([\d.-]+)%"
        )
        
        for log_file in vsr_log_dir.glob("*.log"):
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        match = vsr_pattern.search(line)
                        if match:
                            ticker = match.group(1)
                            score = int(match.group(2))
                            momentum = float(match.group(3))
                            
                            # Extract time from line
                            time_match = re.search(rf"{date} (\d{{2}}:\d{{2}}:\d{{2}})", line)
                            if time_match:
                                alert_time = time_match.group(1)
                                alerts.append({
                                    'ticker': ticker,
                                    'alert_time': alert_time,
                                    'alert_type': 'HIGH_MOMENTUM',
                                    'score': score,
                                    'momentum': momentum,
                                    'date': date
                                })
            except Exception as e:
                logger.error(f"Error parsing {log_file}: {e}")
                
        # Parse market regime alerts
        regime_log = Path("/Users/maverick/PycharmProjects/India-TS/Daily/logs/market_regime_analyzer_5min_error.log")
        regime_pattern = re.compile(rf"{date}.*Sent regime change alert: (\w+) -> (\w+)")
        
        try:
            with open(regime_log, 'r') as f:
                for line in f:
                    match = regime_pattern.search(line)
                    if match:
                        time_match = re.search(rf"{date} (\d{{2}}:\d{{2}}:\d{{2}})", line)
                        if time_match:
                            alerts.append({
                                'ticker': 'MARKET_REGIME',
                                'alert_time': time_match.group(1),
                                'alert_type': 'REGIME_CHANGE',
                                'from_regime': match.group(1),
                                'to_regime': match.group(2),
                                'date': date
                            })
        except Exception as e:
            logger.error(f"Error parsing regime log: {e}")
            
        self.yesterday_alerts = alerts
        logger.info(f"Parsed {len(alerts)} alerts from {date}")
        return alerts
        
    def fetch_hourly_volumes(self, ticker, date):
        """Fetch hourly volume data for a ticker on a specific date"""
        try:
            if not self.kite:
                return {}
                
            # Get instrument token
            instruments = self.kite.instruments("NSE")
            instrument = next((i for i in instruments if i['tradingsymbol'] == ticker), None)
            
            if not instrument:
                logger.warning(f"Instrument not found: {ticker}")
                return {}
                
            token = instrument['instrument_token']
            
            # Fetch minute data
            from_date = datetime.strptime(date, "%Y-%m-%d").replace(hour=9, minute=0)
            to_date = from_date.replace(hour=15, minute=30)
            
            data = self.kite.historical_data(
                token, 
                from_date, 
                to_date, 
                interval="minute"
            )
            
            if not data:
                return {}
                
            # Convert to DataFrame
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df['hour'] = df['date'].dt.hour
            
            # Calculate hourly volumes
            hourly_volumes = df.groupby('hour')['volume'].sum().to_dict()
            
            return hourly_volumes
            
        except Exception as e:
            logger.error(f"Error fetching volumes for {ticker}: {e}")
            return {}
            
    def compare_volumes(self):
        """Compare today's volumes with yesterday's and filter tickers"""
        try:
            current_time = datetime.now(self.ist)
            current_hour = current_time.hour
            yesterday = (current_time - timedelta(days=1)).strftime("%Y-%m-%d")
            today = current_time.strftime("%Y-%m-%d")
            
            filtered = []
            
            for alert in self.yesterday_alerts:
                if alert['ticker'] == 'MARKET_REGIME':
                    continue
                    
                ticker = alert['ticker']
                
                # Fetch yesterday's volumes
                yesterday_vols = self.fetch_hourly_volumes(ticker, yesterday)
                
                # Fetch today's volumes  
                today_vols = self.fetch_hourly_volumes(ticker, today)
                
                if not yesterday_vols or not today_vols:
                    continue
                    
                # Compare current hour volume
                yesterday_current = yesterday_vols.get(current_hour, 0)
                today_current = today_vols.get(current_hour, 0)
                
                if yesterday_current > 0:
                    volume_ratio = today_current / yesterday_current
                else:
                    volume_ratio = 0
                    
                # Include if today's volume >= yesterday's
                if volume_ratio >= 1.0:
                    status = "ACTIVE"
                    trend = "📈"
                else:
                    status = "FILTERED"
                    trend = "📉"
                    
                ticker_data = {
                    'ticker': ticker,
                    'alert_time': alert['alert_time'],
                    'score': alert.get('score', 0),
                    'momentum': alert.get('momentum', 0),
                    'yesterday_volumes': yesterday_vols,
                    'today_volumes': today_vols,
                    'current_hour': current_hour,
                    'yesterday_current': yesterday_current,
                    'today_current': today_current,
                    'volume_ratio': volume_ratio,
                    'status': status,
                    'trend': trend
                }
                
                filtered.append(ticker_data)
                
                if status == "ACTIVE":
                    self.filtered_tickers.append(ticker_data)
                    
            self.volume_data = filtered
            self.last_update = current_time
            
            # Save to file
            self.save_data()
            
            logger.info(f"Processed {len(filtered)} tickers, {len(self.filtered_tickers)} active")
            
        except Exception as e:
            logger.error(f"Error comparing volumes: {e}")
            
    def save_data(self):
        """Save current data to JSON file"""
        try:
            data = {
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'yesterday_alerts': self.yesterday_alerts,
                'volume_data': self.volume_data,
                'filtered_tickers': self.filtered_tickers
            }
            
            output_file = self.data_dir / f"alert_tracker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
                
            # Also save as latest
            latest_file = self.data_dir / "latest_alert_tracker.json"
            with open(latest_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
                
            logger.info(f"Data saved to {output_file}")
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            
    def load_latest_data(self):
        """Load latest saved data"""
        try:
            latest_file = self.data_dir / "latest_alert_tracker.json"
            if latest_file.exists():
                with open(latest_file, 'r') as f:
                    data = json.load(f)
                    self.yesterday_alerts = data.get('yesterday_alerts', [])
                    self.volume_data = data.get('volume_data', [])
                    self.filtered_tickers = data.get('filtered_tickers', [])
                    if data.get('last_update'):
                        self.last_update = datetime.fromisoformat(data['last_update'])
                    logger.info("Loaded latest data from file")
                    return True
        except Exception as e:
            logger.error(f"Error loading data: {e}")
        return False
        
    def generate_hourly_heatmap(self):
        """Generate hourly volume heatmap data"""
        heatmap = []
        
        for ticker_data in self.volume_data:
            ticker = ticker_data['ticker']
            row = {'ticker': ticker}
            
            for hour in range(9, 16):
                yesterday_vol = ticker_data['yesterday_volumes'].get(hour, 0)
                today_vol = ticker_data['today_volumes'].get(hour, 0)
                
                if yesterday_vol > 0:
                    ratio = today_vol / yesterday_vol
                    if ratio >= 1.5:
                        status = "🟡"  # Gold - exceptional
                    elif ratio >= 1.0:
                        status = "🟢"  # Green - exceeding
                    else:
                        status = "🔴"  # Red - below
                    row[f'hour_{hour}'] = f"{status} {ratio:.1f}x"
                else:
                    row[f'hour_{hour}'] = "-"
                    
            heatmap.append(row)
            
        return heatmap
        
    def run_background_updates(self):
        """Run background updates during market hours"""
        while True:
            try:
                current_time = datetime.now(self.ist)
                
                # Check if market hours (9:15 AM to 3:30 PM)
                if current_time.hour >= 9 and current_time.hour < 16:
                    logger.info("Running background update...")
                    
                    # Parse alerts if not done today
                    if not self.yesterday_alerts:
                        self.parse_alert_logs()
                        
                    # Compare volumes
                    self.compare_volumes()
                    
                # Sleep for 5 minutes
                time.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in background update: {e}")
                time.sleep(60)

# Global tracker instance
tracker = AlertVolumeTracker()

@app.route('/')
def dashboard():
    """Render the dashboard"""
    return render_template_string(DASHBOARD_TEMPLATE, 
                                 data=tracker.volume_data,
                                 filtered=tracker.filtered_tickers,
                                 last_update=tracker.last_update,
                                 heatmap=tracker.generate_hourly_heatmap())

@app.route('/api/data')
def get_data():
    """API endpoint for getting current data"""
    return jsonify({
        'volume_data': tracker.volume_data,
        'filtered_tickers': tracker.filtered_tickers,
        'last_update': tracker.last_update.isoformat() if tracker.last_update else None,
        'heatmap': tracker.generate_hourly_heatmap()
    })

@app.route('/api/refresh')
def refresh_data():
    """Force refresh data"""
    tracker.compare_volumes()
    return jsonify({'status': 'success', 'message': 'Data refreshed'})

# Dashboard HTML template
DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Alert Volume Tracker Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .dashboard {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        
        h1 {
            color: #2c3e50;
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .timestamp {
            color: #7f8c8d;
            font-size: 0.9em;
        }
        
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .summary-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        
        .summary-value {
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
        }
        
        .summary-label {
            color: #7f8c8d;
            font-size: 0.9em;
        }
        
        .table-container {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            overflow-x: auto;
        }
        
        h2 {
            color: #2c3e50;
            margin-bottom: 20px;
            font-size: 1.8em;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th {
            background: #f8f9fa;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #2c3e50;
            border-bottom: 2px solid #dee2e6;
        }
        
        td {
            padding: 12px;
            border-bottom: 1px solid #dee2e6;
        }
        
        tr:hover {
            background: #f8f9fa;
        }
        
        .status-active {
            color: #27ae60;
            font-weight: bold;
        }
        
        .status-filtered {
            color: #e74c3c;
            font-weight: bold;
        }
        
        .ratio-high {
            color: #f39c12;
            font-weight: bold;
        }
        
        .ratio-good {
            color: #27ae60;
        }
        
        .ratio-low {
            color: #e74c3c;
        }
        
        .heatmap-cell {
            text-align: center;
            padding: 8px;
            font-size: 0.9em;
        }
        
        .refresh-btn {
            background: #3498db;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1em;
            margin-left: 20px;
        }
        
        .refresh-btn:hover {
            background: #2980b9;
        }
        
        .auto-refresh {
            color: #7f8c8d;
            font-size: 0.85em;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>📊 Alert Volume Tracker - Yesterday vs Today</h1>
            <div class="timestamp">
                Last Updated: {{ last_update.strftime('%Y-%m-%d %H:%M:%S IST') if last_update else 'Never' }}
                <button class="refresh-btn" onclick="refreshData()">🔄 Refresh Now</button>
            </div>
            
            <div class="summary">
                <div class="summary-card">
                    <div class="summary-value">{{ data|length }}</div>
                    <div class="summary-label">Yesterday's Alerts</div>
                </div>
                <div class="summary-card">
                    <div class="summary-value" style="color: #27ae60;">{{ filtered|length }}</div>
                    <div class="summary-label">Active Today</div>
                </div>
                <div class="summary-card">
                    <div class="summary-value" style="color: #e74c3c;">{{ (data|length - filtered|length) }}</div>
                    <div class="summary-label">Filtered Out</div>
                </div>
                <div class="summary-card">
                    <div class="summary-value">{{ '{:.1%}'.format(filtered|length / data|length if data else 0) }}</div>
                    <div class="summary-label">Active Rate</div>
                </div>
            </div>
            
            <div class="auto-refresh">Auto-refreshes every 5 minutes during market hours</div>
        </div>
        
        <!-- Active Alerts Table -->
        <div class="table-container">
            <h2>✅ Active Alerts (Volume Matching/Exceeding Yesterday)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Alert Time</th>
                        <th>Score</th>
                        <th>Momentum</th>
                        <th>Yesterday Vol (Current Hr)</th>
                        <th>Today Vol (Current Hr)</th>
                        <th>Ratio</th>
                        <th>Status</th>
                        <th>Trend</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in filtered %}
                    <tr>
                        <td><strong>{{ item.ticker }}</strong></td>
                        <td>{{ item.alert_time }}</td>
                        <td>{{ item.score }}</td>
                        <td>{{ '{:.1f}%'.format(item.momentum) }}</td>
                        <td>{{ '{:,}'.format(item.yesterday_current) }}</td>
                        <td>{{ '{:,}'.format(item.today_current) }}</td>
                        <td class="{% if item.volume_ratio >= 1.5 %}ratio-high{% elif item.volume_ratio >= 1.0 %}ratio-good{% else %}ratio-low{% endif %}">
                            {{ '{:.2f}×'.format(item.volume_ratio) }}
                        </td>
                        <td class="status-active">{{ item.status }}</td>
                        <td>{{ item.trend }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <!-- Hourly Volume Heatmap -->
        <div class="table-container">
            <h2>🔥 Hourly Volume Heatmap</h2>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>09:00</th>
                        <th>10:00</th>
                        <th>11:00</th>
                        <th>12:00</th>
                        <th>13:00</th>
                        <th>14:00</th>
                        <th>15:00</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in heatmap %}
                    <tr>
                        <td><strong>{{ row.ticker }}</strong></td>
                        {% for hour in range(9, 16) %}
                        <td class="heatmap-cell">{{ row['hour_' + hour|string] }}</td>
                        {% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <!-- All Alerts Table -->
        <div class="table-container">
            <h2>📋 All Yesterday's Alerts</h2>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Alert Time</th>
                        <th>Score</th>
                        <th>Momentum</th>
                        <th>Current Hr Ratio</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in data %}
                    <tr>
                        <td><strong>{{ item.ticker }}</strong></td>
                        <td>{{ item.alert_time }}</td>
                        <td>{{ item.score }}</td>
                        <td>{{ '{:.1f}%'.format(item.momentum) }}</td>
                        <td class="{% if item.volume_ratio >= 1.0 %}ratio-good{% else %}ratio-low{% endif %}">
                            {{ '{:.2f}×'.format(item.volume_ratio) }}
                        </td>
                        <td class="{% if item.status == 'ACTIVE' %}status-active{% else %}status-filtered{% endif %}">
                            {{ item.status }}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        function refreshData() {
            fetch('/api/refresh')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        location.reload();
                    }
                });
        }
        
        // Auto-refresh every 5 minutes
        setInterval(() => {
            const now = new Date();
            const hours = now.getHours();
            if (hours >= 9 && hours < 16) {
                location.reload();
            }
        }, 300000);
    </script>
</body>
</html>
'''

def run_server():
    """Run the Flask server"""
    app.run(host='0.0.0.0', port=2002, debug=False)

if __name__ == '__main__':
    # Load latest data if available
    if not tracker.load_latest_data():
        # Parse yesterday's alerts
        tracker.parse_alert_logs()
        
    # Start background update thread
    background_thread = threading.Thread(target=tracker.run_background_updates, daemon=True)
    background_thread.start()
    
    # Run initial comparison
    tracker.compare_volumes()
    
    # Start Flask server
    logger.info("Starting Alert Volume Tracker Dashboard on port 2002...")
    run_server()