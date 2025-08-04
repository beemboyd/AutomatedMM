#!/usr/bin/env python3
"""
Hourly Breakout Alert Dashboard
Displays logs from hourly breakout alert service
Runs on port 3005
"""

from flask import Flask, render_template, jsonify, request
import os
import subprocess
import glob
import re
from datetime import datetime
from collections import deque
import threading
import time

app = Flask(__name__)

# Configuration
PORT = 3005
LOG_DIR = "/Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_hourlybo"
SERVICE_NAME = "com.india-ts.hourly-breakout-alerts"
PLIST_FILE = f"/Users/maverick/Library/LaunchAgents/{SERVICE_NAME}.plist"

# Store last N lines for performance
LOG_CACHE = {}
MAX_LINES = 1000

def parse_log_lines(lines):
    """Parse log lines and format them for display"""
    formatted_lines = []
    
    for line in lines:
        # Parse timestamp and log level
        match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) - (\w+) - (\w+) - (.+)', line)
        if match:
            timestamp = match.group(1)
            logger_name = match.group(2)
            level = match.group(3)
            message = match.group(4)
            
            # Determine CSS class based on content
            css_class = 'log-info'
            if level == 'ERROR':
                css_class = 'log-error'
            elif level == 'WARNING':
                css_class = 'log-warning'
            elif 'Sent breakout alert' in message:
                css_class = 'log-alert'
            elif 'Started' in message or 'initialized' in message:
                css_class = 'log-success'
            elif 'Tracking' in message:
                css_class = 'log-tracking'
            elif 'Loading tickers' in message:
                css_class = 'log-debug'
            
            formatted_lines.append({
                'timestamp': timestamp,
                'level': level,
                'message': message,
                'class': css_class,
                'raw': line
            })
        else:
            # For lines that don't match the pattern, just display as-is
            formatted_lines.append({
                'timestamp': '',
                'level': '',
                'message': line.strip(),
                'class': 'log-info',
                'raw': line
            })
    
    return formatted_lines

def read_log_tail(filepath, num_lines=300):
    """Read last N lines from log file efficiently"""
    try:
        # Use deque for efficient line storage
        lines = deque(maxlen=num_lines)
        
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                lines.append(line.rstrip())
        
        return list(lines)
    except Exception as e:
        print(f"Error reading log file {filepath}: {e}")
        return []

def is_service_running():
    """Check if hourly breakout service is running"""
    try:
        result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
        return SERVICE_NAME in result.stdout
    except Exception as e:
        print(f"Error checking service status: {e}")
        return False

def get_alert_statistics(lines):
    """Extract statistics from log lines"""
    stats = {
        'total_alerts': 0,
        'alerts_by_ticker': {},
        'error_count': 0,
        'last_alert_time': None
    }
    
    for line in lines:
        if 'Sent breakout alert for' in line:
            stats['total_alerts'] += 1
            # Extract ticker and percentage
            match = re.search(r'Sent breakout alert for (\w+) \(\+([\d.]+)%\)', line)
            if match:
                ticker = match.group(1)
                percentage = float(match.group(2))
                if ticker not in stats['alerts_by_ticker']:
                    stats['alerts_by_ticker'][ticker] = []
                stats['alerts_by_ticker'][ticker].append(percentage)
            
            # Extract timestamp
            time_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if time_match:
                stats['last_alert_time'] = time_match.group(1)
        
        elif 'ERROR' in line:
            stats['error_count'] += 1
    
    return stats

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('hourly_breakout_dashboard.html')

@app.route('/api/logs')
def api_logs():
    """Get logs from the service"""
    try:
        # Find today's log file
        today = datetime.now().strftime('%Y%m%d')
        log_file = os.path.join(LOG_DIR, f'hourly_breakout_{today}.log')
        
        if not os.path.exists(log_file):
            # Try to find any log file
            log_files = glob.glob(os.path.join(LOG_DIR, 'hourly_breakout_*.log'))
            if log_files:
                log_file = max(log_files, key=os.path.getmtime)
            else:
                return jsonify({
                    'error': 'No log files found',
                    'lines': []
                })
        
        # Read last 300 lines
        lines = read_log_tail(log_file, 300)
        formatted_lines = parse_log_lines(lines)
        
        # Get statistics
        stats = get_alert_statistics(lines)
        
        # Get file stats
        file_stats = os.stat(log_file)
        last_modified = datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'lines': formatted_lines,
            'last_modified': last_modified,
            'total_lines': len(lines),
            'file_size': f"{file_stats.st_size / 1024:.1f} KB",
            'file_name': os.path.basename(log_file),
            'statistics': stats
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'lines': []
        })

@app.route('/api/service/status')
def api_service_status():
    """Check if service is running"""
    running = is_service_running()
    return jsonify({'running': running})

@app.route('/api/service/start', methods=['POST'])
def api_service_start():
    """Start the hourly breakout service"""
    try:
        if is_service_running():
            return jsonify({
                'success': False,
                'error': 'Service is already running'
            })
        
        # Load the service
        subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', PLIST_FILE], check=True)
        
        # Give it a moment to start
        time.sleep(2)
        
        if is_service_running():
            return jsonify({
                'success': True,
                'message': 'Hourly breakout service started'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to start service'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/service/stop', methods=['POST'])
def api_service_stop():
    """Stop the hourly breakout service"""
    try:
        if not is_service_running():
            return jsonify({
                'success': False,
                'error': 'Service is not running'
            })
        
        # Unload the service
        subprocess.run(['launchctl', 'bootout', f'gui/{os.getuid()}', PLIST_FILE], check=True)
        
        time.sleep(1)
        
        if not is_service_running():
            return jsonify({
                'success': True,
                'message': 'Hourly breakout service stopped'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to stop service'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(template_dir, exist_ok=True)
    
    print(f"Starting Hourly Breakout Dashboard on port {PORT}")
    print(f"Access the dashboard at: http://localhost:{PORT}")
    
    app.run(host='0.0.0.0', port=PORT, debug=True)