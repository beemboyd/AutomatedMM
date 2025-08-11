#!/usr/bin/env python3
"""
Dashboard for First Hour Breakout Service
Displays 5-minute breakout alerts and statistics on port 3006
"""

import os
import sys
import re
import json
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request
import subprocess
from collections import defaultdict
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)

# Configuration
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'alerts_firsthour')
STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'first_hour_state.json')
SERVICE_NAME = "com.india-ts.first-hour-alerts"
PLIST_PATH = f"$HOME/Library/LaunchAgents/{SERVICE_NAME}.plist"

def get_log_files():
    """Get all log files sorted by date"""
    if not os.path.exists(LOG_DIR):
        return []
    
    files = []
    for filename in os.listdir(LOG_DIR):
        if filename.startswith('first_hour_') and filename.endswith('.log'):
            filepath = os.path.join(LOG_DIR, filename)
            files.append({
                'name': filename,
                'path': filepath,
                'date': datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d')
            })
    
    return sorted(files, key=lambda x: x['name'], reverse=True)

def parse_log_file(filepath: str) -> Dict:
    """Parse log file and extract alerts and statistics"""
    alerts = []
    errors = []
    stats = {
        'total_alerts': 0,
        'tickers_tracked': 0,
        'volume_breakouts': 0,
        'service_starts': 0,
        'last_update': None
    }
    
    if not os.path.exists(filepath):
        return {'alerts': alerts, 'errors': errors, 'stats': stats}
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    for line in lines:
        # Parse breakout alerts
        if 'Sent 5-min breakout alert for' in line:
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*Sent 5-min breakout alert for (\w+) \(\+([\d.]+)%, Vol: ([\d.]+)x\)', line)
            if match:
                timestamp, ticker, breakout_pct, volume = match.groups()
                alerts.append({
                    'timestamp': timestamp,
                    'ticker': ticker,
                    'breakout_pct': float(breakout_pct),
                    'volume_ratio': float(volume),
                    'alert_type': 'high_volume' if float(volume) > 2.0 else 'normal'
                })
                stats['total_alerts'] += 1
                if float(volume) > 1.5:
                    stats['volume_breakouts'] += 1
        
        # Parse errors
        elif 'ERROR' in line:
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if timestamp_match:
                errors.append({
                    'timestamp': timestamp_match.group(1),
                    'message': line.strip()
                })
        
        # Parse service starts
        elif 'First Hour Breakout Service initialized' in line:
            stats['service_starts'] += 1
        
        # Parse ticker tracking
        elif 'Loaded' in line and 'tickers from hourly breakout state' in line:
            match = re.search(r'Loaded (\d+) tickers', line)
            if match:
                stats['tickers_tracked'] = int(match.group(1))
        
        # Track last update
        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
        if timestamp_match:
            stats['last_update'] = timestamp_match.group(1)
    
    return {'alerts': alerts, 'errors': errors, 'stats': stats}

def get_service_status() -> Dict:
    """Get service status"""
    try:
        result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
        is_running = SERVICE_NAME in result.stdout
        
        # Get state file info
        state_info = {'exists': False}
        if os.path.exists(STATE_FILE):
            state_info['exists'] = True
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                    state_info['alerts_today'] = len([k for k, v in state.get('alerted_breakouts', {}).items() 
                                                     if v.startswith(datetime.now().date().isoformat())])
                    state_info['last_update'] = state.get('last_update', 'Unknown')
            except:
                pass
        
        return {
            'running': is_running,
            'service_name': SERVICE_NAME,
            'state': state_info
        }
    except Exception as e:
        return {
            'running': False,
            'service_name': SERVICE_NAME,
            'error': str(e)
        }

def get_alert_statistics(alerts: List[Dict]) -> Dict:
    """Calculate alert statistics"""
    if not alerts:
        return {
            'by_hour': {},
            'by_ticker': {},
            'top_movers': [],
            'volume_leaders': []
        }
    
    # Group by hour
    by_hour = defaultdict(int)
    by_ticker = defaultdict(lambda: {'count': 0, 'avg_breakout': 0, 'max_volume': 0})
    
    for alert in alerts:
        # By hour
        hour = alert['timestamp'].split(':')[0] + ':00'
        by_hour[hour] += 1
        
        # By ticker
        ticker = alert['ticker']
        by_ticker[ticker]['count'] += 1
        by_ticker[ticker]['avg_breakout'] += alert['breakout_pct']
        by_ticker[ticker]['max_volume'] = max(by_ticker[ticker]['max_volume'], alert['volume_ratio'])
    
    # Calculate averages
    for ticker in by_ticker:
        by_ticker[ticker]['avg_breakout'] /= by_ticker[ticker]['count']
    
    # Top movers by breakout percentage
    top_movers = sorted(alerts, key=lambda x: x['breakout_pct'], reverse=True)[:10]
    
    # Volume leaders
    volume_leaders = sorted(alerts, key=lambda x: x['volume_ratio'], reverse=True)[:10]
    
    return {
        'by_hour': dict(by_hour),
        'by_ticker': dict(by_ticker),
        'top_movers': top_movers,
        'volume_leaders': volume_leaders
    }

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template_string(DASHBOARD_TEMPLATE)

@app.route('/api/logs')
def api_logs():
    """API endpoint for log data"""
    date = request.args.get('date', datetime.now().strftime('%Y%m%d'))
    
    # Find log file for date
    log_file = os.path.join(LOG_DIR, f'first_hour_{date}.log')
    data = parse_log_file(log_file)
    
    # Add statistics
    data['statistics'] = get_alert_statistics(data['alerts'])
    
    # Add service status
    data['service'] = get_service_status()
    
    # Add available dates
    data['available_dates'] = [f['date'] for f in get_log_files()]
    
    return jsonify(data)

@app.route('/api/service/<action>')
def service_control(action):
    """Control service (start/stop)"""
    try:
        if action == 'start':
            script_path = os.path.join(os.path.dirname(__file__), '..', 'alerts', 'start_first_hour_alerts.sh')
            result = subprocess.run(['bash', script_path], capture_output=True, text=True)
            return jsonify({'success': True, 'message': 'Service started', 'output': result.stdout})
        elif action == 'stop':
            script_path = os.path.join(os.path.dirname(__file__), '..', 'alerts', 'stop_first_hour_alerts.sh')
            result = subprocess.run(['bash', script_path], capture_output=True, text=True)
            return jsonify({'success': True, 'message': 'Service stopped', 'output': result.stdout})
        else:
            return jsonify({'success': False, 'error': 'Invalid action'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# HTML Template
DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>First Hour Breakout Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0e27;
            color: #e0e0e0;
            line-height: 1.6;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #1a1f3a;
        }
        
        .title { 
            font-size: 28px; 
            font-weight: 600;
            background: linear-gradient(45deg, #00d4ff, #0099ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .status-badge {
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 500;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        
        .status-running { background: #00c851; color: white; }
        .status-stopped { background: #ff4444; color: white; }
        
        .controls {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s;
        }
        
        .btn-primary { background: #0099ff; color: white; }
        .btn-primary:hover { background: #0077cc; }
        .btn-danger { background: #ff4444; color: white; }
        .btn-danger:hover { background: #cc0000; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: #1a1f3a;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid #2a3f5f;
        }
        
        .stat-value {
            font-size: 32px;
            font-weight: 600;
            color: #00d4ff;
            margin-bottom: 5px;
        }
        
        .stat-label {
            font-size: 14px;
            color: #888;
            text-transform: uppercase;
        }
        
        .section {
            background: #1a1f3a;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid #2a3f5f;
        }
        
        .section-title {
            font-size: 20px;
            margin-bottom: 15px;
            color: #00d4ff;
        }
        
        .alerts-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .alerts-table th,
        .alerts-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #2a3f5f;
        }
        
        .alerts-table th {
            font-weight: 600;
            color: #00d4ff;
            text-transform: uppercase;
            font-size: 12px;
        }
        
        .ticker {
            font-weight: 600;
            color: #fff;
        }
        
        .breakout-positive { color: #00c851; }
        .volume-high { color: #ffbb33; font-weight: 600; }
        
        .chart-container {
            height: 300px;
            margin-top: 20px;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        .error {
            background: #ff4444;
            color: white;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
        
        .date-selector {
            padding: 8px 12px;
            background: #2a3f5f;
            border: 1px solid #3a4f6f;
            color: white;
            border-radius: 6px;
            cursor: pointer;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .pulse { animation: pulse 2s infinite; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">First Hour Breakout Dashboard (5-Min)</h1>
            <div class="controls">
                <select id="dateSelector" class="date-selector"></select>
                <div id="serviceStatus"></div>
                <button id="startBtn" class="btn btn-primary" onclick="controlService('start')">Start Service</button>
                <button id="stopBtn" class="btn btn-danger" onclick="controlService('stop')">Stop Service</button>
                <button class="btn btn-primary" onclick="refreshData()">Refresh</button>
            </div>
        </div>
        
        <div class="stats-grid" id="statsGrid">
            <div class="stat-card">
                <div class="stat-value">-</div>
                <div class="stat-label">Total Alerts</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">-</div>
                <div class="stat-label">Tickers Tracked</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">-</div>
                <div class="stat-label">Volume Breakouts</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">-</div>
                <div class="stat-label">Last Update</div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">Hourly Alert Distribution</h2>
            <div class="chart-container">
                <canvas id="hourlyChart"></canvas>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">Recent Breakout Alerts</h2>
            <div id="alertsContainer">
                <div class="loading">Loading alerts...</div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">Top Movers</h2>
            <div id="topMoversContainer">
                <div class="loading">Loading top movers...</div>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">Volume Leaders</h2>
            <div id="volumeLeadersContainer">
                <div class="loading">Loading volume leaders...</div>
            </div>
        </div>
    </div>
    
    <script>
        let hourlyChart = null;
        let currentDate = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        let autoRefreshInterval = null;
        
        function formatTime(timestamp) {
            return timestamp.split(' ')[1].substring(0, 5);
        }
        
        function updateStats(stats, service) {
            const cards = document.querySelectorAll('.stat-card');
            cards[0].querySelector('.stat-value').textContent = stats.total_alerts || '0';
            cards[1].querySelector('.stat-value').textContent = stats.tickers_tracked || '0';
            cards[2].querySelector('.stat-value').textContent = stats.volume_breakouts || '0';
            cards[3].querySelector('.stat-value').textContent = stats.last_update ? formatTime(stats.last_update) : 'N/A';
            
            // Update service status
            const statusHtml = service.running 
                ? '<span class="status-badge status-running pulse">● Running</span>'
                : '<span class="status-badge status-stopped">● Stopped</span>';
            document.getElementById('serviceStatus').innerHTML = statusHtml;
            
            // Update button states
            document.getElementById('startBtn').disabled = service.running;
            document.getElementById('stopBtn').disabled = !service.running;
        }
        
        function createAlertsTable(alerts) {
            if (!alerts || alerts.length === 0) {
                return '<p style="text-align: center; color: #666;">No alerts yet for this date</p>';
            }
            
            let html = '<table class="alerts-table"><thead><tr>';
            html += '<th>Time</th><th>Ticker</th><th>Breakout %</th><th>Volume</th>';
            html += '</tr></thead><tbody>';
            
            alerts.slice(-20).reverse().forEach(alert => {
                const volumeClass = alert.volume_ratio > 1.5 ? 'volume-high' : '';
                html += `<tr>
                    <td>${formatTime(alert.timestamp)}</td>
                    <td class="ticker">${alert.ticker}</td>
                    <td class="breakout-positive">+${alert.breakout_pct.toFixed(2)}%</td>
                    <td class="${volumeClass}">${alert.volume_ratio.toFixed(1)}x</td>
                </tr>`;
            });
            
            html += '</tbody></table>';
            return html;
        }
        
        function createTopMoversTable(movers) {
            if (!movers || movers.length === 0) {
                return '<p style="text-align: center; color: #666;">No data available</p>';
            }
            
            let html = '<table class="alerts-table"><thead><tr>';
            html += '<th>Ticker</th><th>Breakout %</th><th>Time</th>';
            html += '</tr></thead><tbody>';
            
            movers.slice(0, 10).forEach(alert => {
                html += `<tr>
                    <td class="ticker">${alert.ticker}</td>
                    <td class="breakout-positive">+${alert.breakout_pct.toFixed(2)}%</td>
                    <td>${formatTime(alert.timestamp)}</td>
                </tr>`;
            });
            
            html += '</tbody></table>';
            return html;
        }
        
        function createVolumeLeadersTable(leaders) {
            if (!leaders || leaders.length === 0) {
                return '<p style="text-align: center; color: #666;">No data available</p>';
            }
            
            let html = '<table class="alerts-table"><thead><tr>';
            html += '<th>Ticker</th><th>Volume</th><th>Breakout %</th><th>Time</th>';
            html += '</tr></thead><tbody>';
            
            leaders.slice(0, 10).forEach(alert => {
                html += `<tr>
                    <td class="ticker">${alert.ticker}</td>
                    <td class="volume-high">${alert.volume_ratio.toFixed(1)}x</td>
                    <td class="breakout-positive">+${alert.breakout_pct.toFixed(2)}%</td>
                    <td>${formatTime(alert.timestamp)}</td>
                </tr>`;
            });
            
            html += '</tbody></table>';
            return html;
        }
        
        function updateHourlyChart(statistics) {
            const ctx = document.getElementById('hourlyChart').getContext('2d');
            
            const hours = Object.keys(statistics.by_hour || {}).sort();
            const counts = hours.map(h => statistics.by_hour[h]);
            
            if (hourlyChart) {
                hourlyChart.destroy();
            }
            
            hourlyChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: hours,
                    datasets: [{
                        label: 'Alerts',
                        data: counts,
                        backgroundColor: '#00d4ff',
                        borderColor: '#0099ff',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { color: '#888' },
                            grid: { color: '#2a3f5f' }
                        },
                        x: {
                            ticks: { color: '#888' },
                            grid: { color: '#2a3f5f' }
                        }
                    }
                }
            });
        }
        
        async function loadData() {
            try {
                const response = await fetch(`/api/logs?date=${currentDate}`);
                const data = await response.json();
                
                updateStats(data.stats, data.service);
                document.getElementById('alertsContainer').innerHTML = createAlertsTable(data.alerts);
                document.getElementById('topMoversContainer').innerHTML = createTopMoversTable(data.statistics.top_movers);
                document.getElementById('volumeLeadersContainer').innerHTML = createVolumeLeadersTable(data.statistics.volume_leaders);
                updateHourlyChart(data.statistics);
                
                // Update date selector
                if (data.available_dates && data.available_dates.length > 0) {
                    updateDateSelector(data.available_dates);
                }
                
            } catch (error) {
                console.error('Error loading data:', error);
                document.getElementById('alertsContainer').innerHTML = 
                    '<div class="error">Error loading data: ' + error.message + '</div>';
            }
        }
        
        function updateDateSelector(dates) {
            const selector = document.getElementById('dateSelector');
            selector.innerHTML = '';
            
            dates.forEach(date => {
                const option = document.createElement('option');
                option.value = date.replace(/-/g, '');
                option.textContent = date;
                if (option.value === currentDate) {
                    option.selected = true;
                }
                selector.appendChild(option);
            });
            
            selector.addEventListener('change', (e) => {
                currentDate = e.target.value;
                loadData();
            });
        }
        
        async function controlService(action) {
            try {
                const response = await fetch(`/api/service/${action}`);
                const data = await response.json();
                
                if (data.success) {
                    setTimeout(loadData, 2000);
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                alert('Error controlling service: ' + error.message);
            }
        }
        
        function refreshData() {
            loadData();
        }
        
        function startAutoRefresh() {
            autoRefreshInterval = setInterval(loadData, 30000); // Refresh every 30 seconds
        }
        
        function stopAutoRefresh() {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
            }
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            loadData();
            startAutoRefresh();
        });
        
        // Clean up on page unload
        window.addEventListener('beforeunload', stopAutoRefresh);
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    print(f"Starting First Hour Breakout Dashboard on http://localhost:3006")
    app.run(host='0.0.0.0', port=3006, debug=False)