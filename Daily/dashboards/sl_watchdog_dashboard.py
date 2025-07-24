#!/usr/bin/env python3
"""
SL Watchdog Dashboard
Displays logs from SL watchdog with start/stop controls
Runs on port 2001
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
PORT = 2001
LOG_DIR = "/Users/maverick/PycharmProjects/India-TS/Daily/logs"
WATCHDOG_SCRIPT = "/Users/maverick/PycharmProjects/India-TS/Daily/portfolio/SL_watchdog.py"
CONFIG_FILE = "/Users/maverick/PycharmProjects/India-TS/Daily/config.ini"

# Store last N lines for performance
LOG_CACHE = {}
MAX_LINES = 1000

def get_available_users():
    """Get list of users from log directory"""
    users = []
    try:
        # Look for user directories in logs
        log_dirs = [d for d in os.listdir(LOG_DIR) if os.path.isdir(os.path.join(LOG_DIR, d))]
        
        # Filter directories that have SL_watchdog logs (with wildcard pattern)
        for user_dir in log_dirs:
            watchdog_logs = glob.glob(os.path.join(LOG_DIR, user_dir, f"SL_watchdog_*.log"))
            if watchdog_logs:
                users.append(user_dir)
        
        # Also check config.ini for available users
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                content = f.read()
                # Find all API_CREDENTIALS_XXX sections
                import re
                pattern = r'\[API_CREDENTIALS_(\w+)\]'
                matches = re.findall(pattern, content)
                for user in matches:
                    if user not in users:
                        users.append(user)
        
    except Exception as e:
        print(f"Error getting users: {e}")
    
    return sorted(users)

def parse_log_lines(lines):
    """Parse log lines and format them for display"""
    formatted_lines = []
    
    for line in lines:
        # Parse timestamp and log level
        match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) - (\w+) - (.+)', line)
        if match:
            timestamp = match.group(1)
            level = match.group(2)
            message = match.group(3)
            
            # Determine CSS class based on content
            css_class = 'log-info'
            if level == 'ERROR':
                css_class = 'log-error'
            elif level == 'WARNING' or '⚠️' in message:
                css_class = 'log-warning'
            elif 'Stop loss triggered' in message or 'SELL order' in message:
                css_class = 'log-sell'
            elif 'BUY order' in message:
                css_class = 'log-buy'
            elif any(keyword in message for keyword in ['Updated position high', 'ATR:', 'Trailing stop']):
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

def read_log_tail(filepath, num_lines=100):
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

def is_watchdog_running(user):
    """Check if SL watchdog is running for a specific user"""
    try:
        # Check for running python processes with SL_watchdog.py
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        processes = result.stdout.splitlines()
        
        for process in processes:
            if 'SL_watchdog.py' in process and user in process:
                return True
        
        # Also check for any orders file being monitored
        for process in processes:
            if 'SL_watchdog' in process and f'orders_{user}_' in process:
                return True
                
        return False
    except Exception as e:
        print(f"Error checking watchdog status: {e}")
        return False

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('sl_watchdog_dashboard.html')

@app.route('/api/users')
def api_users():
    """Get list of available users"""
    users = get_available_users()
    return jsonify(users)

@app.route('/api/logs/<user>')
def api_logs(user):
    """Get logs for a specific user"""
    try:
        # Find all SL_watchdog log files for this user
        log_pattern = os.path.join(LOG_DIR, user, f"SL_watchdog_*.log")
        log_files = glob.glob(log_pattern)
        
        if not log_files:
            return jsonify({
                'error': f'No SL watchdog log files found for user {user}',
                'lines': []
            })
        
        # Get the most recent log file
        log_file = max(log_files, key=os.path.getmtime)
        
        # Read last 300 lines as requested for efficiency
        lines = read_log_tail(log_file, 300)
        formatted_lines = parse_log_lines(lines)
        
        # Get file stats
        stats = os.stat(log_file)
        last_modified = datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'lines': formatted_lines,
            'last_modified': last_modified,
            'total_lines': len(lines),
            'file_size': f"{stats.st_size / 1024:.1f} KB",
            'file_name': os.path.basename(log_file)
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'lines': []
        })

@app.route('/api/watchdog/status/<user>')
def api_watchdog_status(user):
    """Check if watchdog is running for a user"""
    running = is_watchdog_running(user)
    return jsonify({'running': running, 'user': user})

@app.route('/api/watchdog/start/<user>', methods=['POST'])
def api_watchdog_start(user):
    """Start SL watchdog for a user"""
    try:
        # Find the latest orders file for the user
        orders_pattern = f"/Users/maverick/PycharmProjects/India-TS/Daily/Current_Orders/{user}/orders_{user}_*.json"
        orders_files = glob.glob(orders_pattern)
        
        if not orders_files:
            return jsonify({
                'success': False,
                'error': f'No orders file found for user {user}'
            })
        
        # Get the latest orders file
        latest_orders = max(orders_files, key=os.path.getctime)
        
        # Start watchdog in background
        cmd = [
            'nohup',
            'python3',
            WATCHDOG_SCRIPT,
            latest_orders,
            '--poll-interval', '45'
        ]
        
        # Start process in background
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        
        # Give it a moment to start
        time.sleep(2)
        
        # Check if it started
        if is_watchdog_running(user):
            return jsonify({
                'success': True,
                'message': f'SL watchdog started for {user}',
                'orders_file': os.path.basename(latest_orders)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to start watchdog - check logs for details'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/watchdog/stop/<user>', methods=['POST'])
def api_watchdog_stop(user):
    """Stop SL watchdog for a user"""
    try:
        # Find and kill the watchdog process
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        processes = result.stdout.splitlines()
        
        killed = False
        for process in processes:
            if 'SL_watchdog.py' in process and (user in process or f'orders_{user}_' in process):
                # Extract PID
                parts = process.split()
                if len(parts) > 1:
                    pid = parts[1]
                    subprocess.run(['kill', '-9', pid])
                    killed = True
        
        if killed:
            return jsonify({
                'success': True,
                'message': f'SL watchdog stopped for {user}'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'No watchdog process found for {user}'
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
    
    print(f"Starting SL Watchdog Dashboard on port {PORT}")
    print(f"Access the dashboard at: http://localhost:{PORT}")
    
    app.run(host='0.0.0.0', port=PORT, debug=True)