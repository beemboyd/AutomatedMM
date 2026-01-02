#!/usr/bin/env python3
"""
Alert Volume Tracker Dashboard - Fixed Version
Tracks yesterday's alerts and compares hourly volumes with today's data
Properly loads and displays saved data
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, jsonify
import threading
import time
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    def __init__(self):
        self.yesterday_alerts = []
        self.volume_data = []
        self.filtered_tickers = []
        self.last_update = None
        self.ist = pytz.timezone('Asia/Kolkata')
        self.data_dir = Path("/Users/maverick/PycharmProjects/India-TS/Daily/data/alert_tracker")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Load data on initialization
        self.load_latest_data()
        
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
                    logger.info(f"Loaded data: {len(self.yesterday_alerts)} alerts, {len(self.volume_data)} volume entries, {len(self.filtered_tickers)} filtered")
                    return True
            else:
                logger.warning("No saved data file found")
        except Exception as e:
            logger.error(f"Error loading data: {e}")
        return False
        
    def generate_hourly_heatmap(self):
        """Generate hourly volume heatmap data"""
        heatmap = []
        
        for ticker_data in self.volume_data:
            ticker = ticker_data['ticker']
            row = {'ticker': ticker}
            
            yesterday_vols = ticker_data.get('yesterday_volumes', {})
            today_vols = ticker_data.get('today_volumes', {})
            
            for hour in range(9, 16):
                yesterday_vol = yesterday_vols.get(str(hour), 0)
                today_vol = today_vols.get(str(hour), 0)
                
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
        """Periodically reload data during market hours"""
        while True:
            try:
                current_time = datetime.now(self.ist)
                
                # Reload data every hour
                self.load_latest_data()
                logger.info(f"Reloaded data at {current_time.strftime('%H:%M:%S')}")
                
                # Sleep for 1 hour (3600 seconds)
                time.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in background update: {e}")
                time.sleep(60)

# Global tracker instance
tracker = AlertVolumeTracker()

@app.route('/')
def dashboard():
    """Render the dashboard"""
    # Ensure data is loaded
    if not tracker.yesterday_alerts:
        tracker.load_latest_data()

    return render_template_string(DASHBOARD_TEMPLATE,
                                 data=tracker.yesterday_alerts,  # Changed from volume_data to yesterday_alerts
                                 filtered=tracker.filtered_tickers,
                                 last_update=tracker.last_update,
                                 heatmap=tracker.generate_hourly_heatmap())

@app.route('/api/data')
def get_data():
    """API endpoint for getting current data"""
    return jsonify({
        'volume_data': tracker.yesterday_alerts,  # Changed to return yesterday_alerts
        'filtered_tickers': tracker.filtered_tickers,
        'last_update': tracker.last_update.isoformat() if tracker.last_update else None,
        'heatmap': tracker.generate_hourly_heatmap()
    })

@app.route('/api/refresh')
def refresh_data():
    """Force refresh data"""
    tracker.load_latest_data()
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
        
        .no-data {
            text-align: center;
            color: #7f8c8d;
            padding: 40px;
            font-size: 1.2em;
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
            
            <div class="auto-refresh">Auto-refreshes every hour during market hours</div>
        </div>
        
        <!-- Active Alerts Table -->
        <div class="table-container">
            <h2>✅ Active Alerts (Volume Matching/Exceeding Yesterday)</h2>
            {% if filtered %}
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
                        <td>{{ '{:,}'.format(item.yesterday_current|int) }}</td>
                        <td>{{ '{:,}'.format(item.today_current|int) }}</td>
                        <td class="{% if item.volume_ratio >= 1.5 %}ratio-high{% elif item.volume_ratio >= 1.0 %}ratio-good{% else %}ratio-low{% endif %}">
                            {{ '{:.2f}×'.format(item.volume_ratio) }}
                        </td>
                        <td class="status-active">{{ item.status }}</td>
                        <td>{{ item.trend }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="no-data">No active alerts at this time</div>
            {% endif %}
        </div>
        
        <!-- Hourly Volume Heatmap -->
        {% if heatmap %}
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
        {% endif %}
        
        <!-- All Alerts Table - Filtered for Above Previous High -->
        <div class="table-container">
            <h2>🎯 High Score Alerts from Yesterday</h2>
            {% set above_high_alerts = data | selectattr('score', 'ge', 90) | list %}
            {% if above_high_alerts %}
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Alert Time</th>
                        <th>Alert Type</th>
                        <th>Score</th>
                        <th>Momentum</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in above_high_alerts %}
                    <tr>
                        <td><strong>{{ item.ticker }}</strong></td>
                        <td>{{ item.alert_time }}</td>
                        <td>{{ item.alert_type }}</td>
                        <td>{{ item.score }}</td>
                        <td>{{ '{:.1f}%'.format(item.momentum) }}</td>
                        <td>{{ item.date }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <div style="margin-top: 15px; color: #7f8c8d; font-size: 0.9em;">
                Showing {{ above_high_alerts|length }} out of {{ data|length }} alerts with score ≥ 90
            </div>
            {% else %}
            <div class="no-data">No high score alerts from yesterday</div>
            {% endif %}
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
        
        // Auto-refresh every hour (3600000 ms)
        setInterval(() => {
            location.reload();
        }, 3600000);
    </script>
</body>
</html>
'''

def run_server():
    """Run the Flask server"""
    app.run(host='0.0.0.0', port=2002, debug=False)

if __name__ == '__main__':
    # Start background update thread
    background_thread = threading.Thread(target=tracker.run_background_updates, daemon=True)
    background_thread.start()

    # Start Flask server
    logger.info(f"Starting Alert Volume Tracker Dashboard on port 2002...")
    logger.info(f"Loaded {len(tracker.yesterday_alerts)} alerts from saved data")
    run_server()