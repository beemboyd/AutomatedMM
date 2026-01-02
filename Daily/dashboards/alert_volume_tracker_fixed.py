#!/usr/bin/env python3
"""
Alert Volume Tracker Dashboard - Simplified Version
Displays yesterday's alerts from saved data
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, jsonify
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

class AlertTracker:
    def __init__(self):
        self.yesterday_alerts = []
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
                    if data.get('last_update'):
                        self.last_update = datetime.fromisoformat(data['last_update'])
                    logger.info(f"Loaded {len(self.yesterday_alerts)} alerts from saved data")
                    return True
            else:
                logger.warning("No saved data file found")
        except Exception as e:
            logger.error(f"Error loading data: {e}")
        return False

# Global tracker instance
tracker = AlertTracker()

@app.route('/')
def dashboard():
    """Render the dashboard"""
    # Ensure data is loaded
    if not tracker.yesterday_alerts:
        tracker.load_latest_data()

    return render_template_string(DASHBOARD_TEMPLATE,
                                 alerts=tracker.yesterday_alerts,
                                 last_update=tracker.last_update)

@app.route('/api/data')
def get_data():
    """API endpoint for getting current data"""
    return jsonify({
        'alerts': tracker.yesterday_alerts,
        'last_update': tracker.last_update.isoformat() if tracker.last_update else None
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
    <title>Alert Tracker Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
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

        .title {
            font-size: 2.5em;
            color: #2c3e50;
            margin-bottom: 10px;
        }

        .subtitle {
            color: #7f8c8d;
            font-size: 1.1em;
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            text-align: center;
        }

        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
        }

        .stat-label {
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

        .high-score {
            color: #f39c12;
            font-weight: bold;
        }

        .very-high-score {
            color: #e74c3c;
            font-weight: bold;
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

        .no-data {
            text-align: center;
            color: #7f8c8d;
            padding: 40px;
            font-size: 1.1em;
        }

        .update-time {
            text-align: center;
            color: #7f8c8d;
            margin-top: 20px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h1 class="title">📊 Alert Tracker Dashboard</h1>
                    <p class="subtitle">Yesterday's Trading Alerts</p>
                </div>
                <button class="refresh-btn" onclick="refreshData()">🔄 Refresh</button>
            </div>
        </div>

        <!-- Statistics -->
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{{ alerts|length }}</div>
                <div class="stat-label">Total Alerts</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ alerts|selectattr('score', 'ge', 100)|list|length }}</div>
                <div class="stat-label">High Score (≥100)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ alerts|selectattr('score', 'ge', 110)|list|length }}</div>
                <div class="stat-label">Very High Score (≥110)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ '{:.1f}%'.format(alerts|map(attribute='momentum')|sum / alerts|length if alerts else 0) }}</div>
                <div class="stat-label">Avg Momentum</div>
            </div>
        </div>

        <!-- All Alerts Table -->
        <div class="table-container">
            <h2>📈 All Yesterday's Alerts</h2>
            {% if alerts %}
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Ticker</th>
                        <th>Alert Time</th>
                        <th>Alert Type</th>
                        <th>Score</th>
                        <th>Momentum</th>
                    </tr>
                </thead>
                <tbody>
                    {% for alert in alerts %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td><strong>{{ alert.ticker }}</strong></td>
                        <td>{{ alert.alert_time }}</td>
                        <td>{{ alert.alert_type }}</td>
                        <td class="{% if alert.score >= 110 %}very-high-score{% elif alert.score >= 100 %}high-score{% endif %}">
                            {{ alert.score }}
                        </td>
                        <td>{{ '{:.1f}%'.format(alert.momentum) }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="no-data">No alert data available</div>
            {% endif %}
        </div>

        {% if last_update %}
        <div class="update-time">
            Last Updated: {{ last_update.strftime('%Y-%m-%d %H:%M:%S') }} IST
        </div>
        {% endif %}
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
            location.reload();
        }, 300000);
    </script>
</body>
</html>
'''

def run_server():
    """Run the Flask server"""
    app.run(host='0.0.0.0', port=2002, debug=False)

if __name__ == '__main__':
    logger.info(f"Starting Alert Volume Tracker Dashboard on port 2002...")
    logger.info(f"Loaded {len(tracker.yesterday_alerts)} alerts from yesterday")
    run_server()