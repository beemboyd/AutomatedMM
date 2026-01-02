#!/usr/bin/env python3
"""
Alert Volume Tracker Dashboard with Real-Time Price Data
Tracks yesterday's alerts and shows only those holding above PDH
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template_string, jsonify
import threading
import time
import pytz
import configparser
from kiteconnect import KiteConnect

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
log_dir = Path("/Users/maverick/PycharmProjects/India-TS/Daily/logs/alert_tracker")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f'alert_tracker_realtime_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class RealTimeAlertTracker:
    def __init__(self):
        self.all_alerts = []  # Changed from yesterday_alerts to all_alerts
        self.alerts_by_date = {}  # Group alerts by date
        self.volume_data = []
        self.filtered_tickers = []
        self.last_update = None
        self.ist = pytz.timezone('Asia/Kolkata')
        self.data_dir = Path("/Users/maverick/PycharmProjects/India-TS/Daily/data/alert_tracker")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.kite = None
        self.initialize_kite()
        self.load_multi_day_alerts()  # Load 3 days of data
        
    def initialize_kite(self):
        """Initialize Kite connection using Sai's credentials from config.ini"""
        try:
            config = configparser.ConfigParser()
            config.read('/Users/maverick/PycharmProjects/India-TS/Daily/config.ini')
            
            api_key = config['API_CREDENTIALS_Sai']['api_key']
            access_token = config['API_CREDENTIALS_Sai']['access_token']
            
            self.kite = KiteConnect(api_key=api_key)
            self.kite.set_access_token(access_token)
            
            # Test connection
            profile = self.kite.profile()
            logger.info(f"Kite connection established for user: {profile.get('user_name')}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Kite: {e}")
            
    def load_multi_day_alerts(self):
        """Load alerts from past 3 days"""
        try:
            # First check if multi-day file exists
            multi_day_file = self.data_dir / "multi_day_alerts.json"
            if multi_day_file.exists():
                with open(multi_day_file, 'r') as f:
                    data = json.load(f)
                    self.all_alerts = data.get('all_alerts', [])
                    self.alerts_by_date = data.get('alerts_by_date', {})
                    logger.info(f"Loaded {len(self.all_alerts)} alerts from {len(self.alerts_by_date)} days")
            else:
                # Fall back to yesterday's alerts
                latest_file = self.data_dir / "latest_alert_tracker.json"
                if latest_file.exists():
                    with open(latest_file, 'r') as f:
                        data = json.load(f)
                        yesterday_alerts = data.get('yesterday_alerts', [])
                        self.all_alerts = yesterday_alerts
                        if yesterday_alerts:
                            date = yesterday_alerts[0].get('date', 'unknown')
                            self.alerts_by_date = {date: yesterday_alerts}
                        logger.info(f"Loaded {len(yesterday_alerts)} alerts from yesterday's file")
        except Exception as e:
            logger.error(f"Error loading alerts: {e}")
            
    def fetch_realtime_data(self):
        """Fetch real-time price and volume data using Kite API"""
        try:
            if not self.kite:
                logger.error("Kite connection not available")
                return
                
            current_time = datetime.now(self.ist)
            current_hour = current_time.hour
            
            all_data = []
            filtered = []
            
            # Get instruments
            instruments = self.kite.instruments("NSE")
            instrument_map = {i['tradingsymbol']: i['instrument_token'] for i in instruments}
            
            for i, alert in enumerate(self.all_alerts):
                ticker = alert['ticker']
                
                if ticker == 'MARKET_REGIME':
                    continue
                    
                # Add small delay between tickers to avoid rate limits
                if i > 0 and i % 10 == 0:
                    time.sleep(0.2)
                    
                if ticker not in instrument_map:
                    logger.warning(f"Ticker {ticker} not found in instruments")
                    continue
                    
                try:
                    token = instrument_map[ticker]
                    
                    # Get quote for current price
                    quote = self.kite.quote(f"NSE:{ticker}")
                    ticker_data = quote.get(f"NSE:{ticker}", {})
                    
                    if not ticker_data:
                        continue
                        
                    # Extract price data
                    current_price = ticker_data.get('last_price', 0)
                    today_open = ticker_data.get('ohlc', {}).get('open', 0)
                    today_high = ticker_data.get('ohlc', {}).get('high', 0)
                    today_low = ticker_data.get('ohlc', {}).get('low', 0)
                    prev_close = ticker_data.get('ohlc', {}).get('close', 0)
                    
                    # Get previous day's high (PDH) from historical data
                    yesterday = (current_time - timedelta(days=1)).date()
                    to_date = yesterday + timedelta(days=1)
                    
                    historical = self.kite.historical_data(
                        token,
                        yesterday,
                        to_date,
                        interval="day"
                    )
                    
                    pdh = 0
                    yesterday_close = prev_close
                    
                    if historical and len(historical) > 0:
                        pdh = historical[0].get('high', 0)
                        yesterday_close = historical[0].get('close', 0)
                    
                    # Calculate if holding above PDH
                    above_pdh = current_price > pdh if pdh > 0 else False
                    pdh_crossed = today_high > pdh if pdh > 0 else False
                    pct_above_pdh = ((current_price - pdh) / pdh * 100) if pdh > 0 else 0
                    
                    # Get volume data
                    volume = ticker_data.get('volume', 0)
                    avg_volume = ticker_data.get('average_price', 0) * volume / current_price if current_price > 0 else 0
                    
                    # Calculate change percentages
                    change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
                    
                    ticker_info = {
                        'ticker': ticker,
                        'alert_time': alert['alert_time'],
                        'alert_date': alert.get('date', 'N/A'),
                        'score': alert.get('score', 0),
                        'momentum': alert.get('momentum', 0),
                        'current_price': round(current_price, 2),
                        'pdh': round(pdh, 2),
                        'today_high': round(today_high, 2),
                        'today_low': round(today_low, 2),
                        'prev_close': round(prev_close, 2),
                        'above_pdh': above_pdh,
                        'pdh_crossed': pdh_crossed,
                        'pct_above_pdh': round(pct_above_pdh, 2),
                        'change_pct': round(change_pct, 2),
                        'volume': volume,
                        'current_hour': current_hour
                    }
                    
                    # Determine status
                    if above_pdh and pct_above_pdh > 0.5:  # Holding at least 0.5% above PDH
                        ticker_info['status'] = 'STRONG'
                        ticker_info['trend'] = '🚀'
                        filtered.append(ticker_info)
                    elif pdh_crossed and pct_above_pdh > -0.5:  # Crossed but pulled back slightly
                        ticker_info['status'] = 'BREAKOUT'
                        ticker_info['trend'] = '📈'
                        filtered.append(ticker_info)
                    else:
                        ticker_info['status'] = 'BELOW'
                        ticker_info['trend'] = '📉'
                        
                    all_data.append(ticker_info)
                    
                except Exception as e:
                    logger.error(f"Error fetching data for {ticker}: {e}")
                    if "Too many requests" in str(e):
                        time.sleep(0.5)  # Add delay if rate limited
                    continue
                    
            self.volume_data = all_data
            self.filtered_tickers = filtered
            self.last_update = current_time
            
            # Save to file
            self.save_data()
            
            logger.info(f"Processed {len(all_data)} tickers, {len(filtered)} above PDH and holding")
            
        except Exception as e:
            logger.error(f"Error fetching realtime data: {e}")
            
    def save_data(self):
        """Save current data to JSON file"""
        try:
            data = {
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'all_alerts': self.all_alerts,
                'alerts_by_date': self.alerts_by_date,
                'volume_data': self.volume_data,
                'filtered_tickers': self.filtered_tickers
            }
            
            output_file = self.data_dir / f"alert_tracker_realtime_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
                
            # Also save as latest
            latest_file = self.data_dir / "latest_alert_tracker_realtime.json"
            with open(latest_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
                
            logger.info(f"Data saved to {output_file}")
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            
    def run_background_updates(self):
        """Initial data fetch only - no periodic updates"""
        try:
            logger.info("Performing initial data fetch...")
            self.fetch_realtime_data()
            # Dashboard runs 24/7 for analysis purposes
                
        except Exception as e:
            logger.error(f"Error in initial data fetch: {e}")

# Global tracker instance
tracker = RealTimeAlertTracker()

@app.route('/')
def dashboard():
    """Render the dashboard"""
    # Ensure data is fresh
    if not tracker.filtered_tickers:
        tracker.fetch_realtime_data()
    
    return render_template_string(DASHBOARD_TEMPLATE, 
                                 data=tracker.volume_data,
                                 filtered=tracker.filtered_tickers,
                                 last_update=tracker.last_update)

@app.route('/api/data')
def get_data():
    """API endpoint for getting current data"""
    return jsonify({
        'volume_data': tracker.volume_data,
        'filtered_tickers': tracker.filtered_tickers,
        'last_update': tracker.last_update.isoformat() if tracker.last_update else None
    })

@app.route('/api/refresh')
def refresh_data():
    """Force refresh data"""
    tracker.fetch_realtime_data()
    return jsonify({'status': 'success', 'message': 'Data refreshed'})

# Dashboard HTML template
DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Alert Tracker - PDH Breakouts</title>
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
        
        .sortable {
            cursor: pointer;
            position: relative;
            user-select: none;
        }
        
        .sortable:hover {
            background: #e9ecef;
        }
        
        .sortable::after {
            content: ' ⇅';
            font-size: 0.8em;
            color: #999;
        }
        
        .sorted-asc::after {
            content: ' ↑';
            color: #333;
        }
        
        .sorted-desc::after {
            content: ' ↓';
            color: #333;
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
        
        .status-strong {
            color: #27ae60;
            font-weight: bold;
        }
        
        .status-breakout {
            color: #f39c12;
            font-weight: bold;
        }
        
        .status-below {
            color: #e74c3c;
            font-weight: bold;
        }
        
        .price-above {
            color: #27ae60;
            font-weight: bold;
        }
        
        .price-below {
            color: #e74c3c;
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
            <h1>🎯 PDH Breakout Tracker - Real-Time</h1>
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
                    <div class="summary-label">Above PDH</div>
                </div>
                <div class="summary-card">
                    <div class="summary-value" style="color: #e74c3c;">{{ (data|length - filtered|length) }}</div>
                    <div class="summary-label">Below PDH</div>
                </div>
                <div class="summary-card">
                    <div class="summary-value">{{ '{:.1%}'.format(filtered|length / data|length if data else 0) }}</div>
                    <div class="summary-label">Success Rate</div>
                </div>
            </div>
            
            <div class="auto-refresh">Manual refresh only - Click refresh button to update data</div>
        </div>
        
        <!-- Active Alerts Table - Only PDH Breakouts -->
        <div class="table-container">
            <h2>🚀 Active Alerts (Above Previous Day High)</h2>
            {% if filtered %}
            <table id="filtered-table">
                <thead>
                    <tr>
                        <th class="sortable" onclick="sortTable(0, 'filtered-table')">Ticker</th>
                        <th class="sortable" onclick="sortTable(1, 'filtered-table')">Alert Date</th>
                        <th class="sortable" onclick="sortTable(2, 'filtered-table')">Alert Time</th>
                        <th class="sortable" onclick="sortTable(3, 'filtered-table', true)">Score</th>
                        <th class="sortable" onclick="sortTable(4, 'filtered-table', true)">Current Price</th>
                        <th class="sortable" onclick="sortTable(5, 'filtered-table', true)">PDH</th>
                        <th class="sortable" onclick="sortTable(6, 'filtered-table', true)">Today High</th>
                        <th class="sortable" onclick="sortTable(7, 'filtered-table', true)">% Above PDH</th>
                        <th class="sortable" onclick="sortTable(8, 'filtered-table', true)">Day Change</th>
                        <th class="sortable" onclick="sortTable(9, 'filtered-table', true)">Volume</th>
                        <th class="sortable" onclick="sortTable(10, 'filtered-table')">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in filtered %}
                    <tr>
                        <td><strong>{{ item.ticker }}</strong></td>
                        <td>{{ item.alert_date }}</td>
                        <td>{{ item.alert_time }}</td>
                        <td>{{ item.score }}</td>
                        <td class="price-above">₹{{ '{:.2f}'.format(item.current_price) }}</td>
                        <td>₹{{ '{:.2f}'.format(item.pdh) }}</td>
                        <td>₹{{ '{:.2f}'.format(item.today_high) }}</td>
                        <td class="{% if item.pct_above_pdh > 1 %}price-above{% else %}price-below{% endif %}">
                            {{ '{:+.2f}%'.format(item.pct_above_pdh) }}
                        </td>
                        <td class="{% if item.change_pct > 0 %}price-above{% else %}price-below{% endif %}">
                            {{ '{:+.2f}%'.format(item.change_pct) }}
                        </td>
                        <td>{{ '{:,.0f}'.format(item.volume) }}</td>
                        <td class="{% if item.status == 'STRONG' %}status-strong{% else %}status-breakout{% endif %}">
                            {{ item.status }} {{ item.trend }}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="no-data">No alerts currently above previous day high</div>
            {% endif %}
        </div>
        
        <!-- All Alerts Table -->
        <div class="table-container">
            <h2>📋 All Alerts (Past 3 Days) - Performance</h2>
            {% if data %}
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Alert Date</th>
                        <th>Alert Time</th>
                        <th>Score</th>
                        <th>Momentum</th>
                        <th>Current Price</th>
                        <th>PDH</th>
                        <th>% vs PDH</th>
                        <th>Day Change</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in data %}
                    <tr>
                        <td><strong>{{ item.ticker }}</strong></td>
                        <td>{{ item.alert_date }}</td>
                        <td>{{ item.alert_time }}</td>
                        <td>{{ item.score }}</td>
                        <td>{{ '{:.1f}%'.format(item.momentum) }}</td>
                        <td>₹{{ '{:.2f}'.format(item.current_price) }}</td>
                        <td>₹{{ '{:.2f}'.format(item.pdh) }}</td>
                        <td class="{% if item.pct_above_pdh > 0 %}price-above{% else %}price-below{% endif %}">
                            {{ '{:+.2f}%'.format(item.pct_above_pdh) }}
                        </td>
                        <td class="{% if item.change_pct > 0 %}price-above{% else %}price-below{% endif %}">
                            {{ '{:+.2f}%'.format(item.change_pct) }}
                        </td>
                        <td class="{% if item.status == 'STRONG' %}status-strong{% elif item.status == 'BREAKOUT' %}status-breakout{% else %}status-below{% endif %}">
                            {{ item.status }} {{ item.trend }}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="no-data">No alert data available</div>
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
        
        // No auto-refresh - manual refresh only
        
        // Sorting functionality
        let sortDirection = {};
        
        function sortTable(columnIndex, tableId, isNumeric = false) {
            const table = document.getElementById(tableId);
            const tbody = table.getElementsByTagName('tbody')[0];
            const rows = Array.from(tbody.getElementsByTagName('tr'));
            const headers = table.getElementsByTagName('th');
            
            // Toggle sort direction
            const currentDirection = sortDirection[tableId + '_' + columnIndex] || 'asc';
            const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
            sortDirection[tableId + '_' + columnIndex] = newDirection;
            
            // Update header classes
            Array.from(headers).forEach((header, index) => {
                header.classList.remove('sorted-asc', 'sorted-desc');
            });
            headers[columnIndex].classList.add('sorted-' + newDirection);
            
            // Sort rows
            rows.sort((a, b) => {
                let aValue = a.getElementsByTagName('td')[columnIndex].textContent.trim();
                let bValue = b.getElementsByTagName('td')[columnIndex].textContent.trim();
                
                // Remove currency symbols and percentage signs for numeric comparison
                if (isNumeric) {
                    aValue = parseFloat(aValue.replace(/[₹,%+]/g, '')) || 0;
                    bValue = parseFloat(bValue.replace(/[₹,%+]/g, '')) || 0;
                }
                
                if (isNumeric) {
                    return newDirection === 'asc' ? aValue - bValue : bValue - aValue;
                } else {
                    if (aValue < bValue) return newDirection === 'asc' ? -1 : 1;
                    if (aValue > bValue) return newDirection === 'asc' ? 1 : -1;
                    return 0;
                }
            });
            
            // Reorder rows in table
            rows.forEach(row => tbody.appendChild(row));
        }
    </script>
</body>
</html>
'''

def run_server():
    """Run the Flask server"""
    app.run(host='0.0.0.0', port=2002, debug=False)

if __name__ == '__main__':
    # Fetch initial data
    tracker.fetch_realtime_data()
    
    # Start background update thread
    background_thread = threading.Thread(target=tracker.run_background_updates, daemon=True)
    background_thread.start()
    
    # Start Flask server
    logger.info("Starting Real-Time Alert Tracker Dashboard on port 2002...")
    logger.info(f"Tracking {len(tracker.all_alerts)} alerts for PDH breakouts")
    run_server()