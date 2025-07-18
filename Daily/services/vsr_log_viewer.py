#!/usr/bin/env python3
"""
VSR Log Viewer
Displays the last 100 lines of VSR logs (anomaly and tracker) in a web interface with auto-refresh
"""

import os
import sys
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
from datetime import datetime
import threading
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
LOG_PATHS = {
    'anomaly': "/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_anomaly",
    'tracker': "/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker"
}
LINES_TO_DISPLAY = 100
REFRESH_INTERVAL = 60  # seconds

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>VSR Log Viewer</title>
    <style>
        body {
            font-family: 'Courier New', monospace;
            background-color: #1e1e1e;
            color: #d4d4d4;
            margin: 20px;
            padding: 0;
        }
        .header {
            background-color: #2d2d30;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        h1 {
            color: #4EC9B0;
            margin: 0 0 10px 0;
        }
        .info {
            color: #808080;
            font-size: 14px;
        }
        .log-container {
            background-color: #1e1e1e;
            border: 1px solid #3e3e42;
            border-radius: 5px;
            padding: 20px;
            overflow-x: auto;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        .log-content {
            white-space: pre-wrap;
            word-wrap: break-word;
            line-height: 1.5;
            font-size: 13px;
        }
        .timestamp {
            color: #569cd6;
        }
        .info-level {
            color: #4EC9B0;
        }
        .warning-level {
            color: #dcdcaa;
        }
        .error-level {
            color: #f44747;
        }
        .anomaly-detected {
            color: #ff6b6b;
            font-weight: bold;
        }
        .ticker {
            color: #c586c0;
            font-weight: bold;
        }
        .refresh-timer {
            position: fixed;
            top: 20px;
            right: 20px;
            background-color: #2d2d30;
            padding: 10px 15px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        .loading {
            color: #569cd6;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .no-data {
            color: #808080;
            text-align: center;
            padding: 40px;
        }
    </style>
    <script>
        let countdown = {{ refresh_interval }};
        
        function updateCountdown() {
            countdown--;
            if (countdown <= 0) {
                document.getElementById('timer').innerHTML = '<span class="loading">Refreshing...</span>';
                location.reload();
            } else {
                document.getElementById('timer').textContent = `Refresh in ${countdown}s`;
            }
        }
        
        function formatLogLine(line) {
            // Highlight timestamps
            line = line.replace(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})/g, '<span class="timestamp">$1</span>');
            
            // Highlight log levels
            line = line.replace(/- INFO -/g, '<span class="info-level">- INFO -</span>');
            line = line.replace(/- WARNING -/g, '<span class="warning-level">- WARNING -</span>');
            line = line.replace(/- ERROR -/g, '<span class="error-level">- ERROR -</span>');
            
            // Highlight anomaly detections
            line = line.replace(/(ANOMALY DETECTED|Anomaly detected)/g, '<span class="anomaly-detected">$1</span>');
            
            // Highlight tickers (assuming they're in uppercase)
            line = line.replace(/\b([A-Z]{2,})\b/g, function(match) {
                if (match.length >= 2 && match.length <= 15 && match !== 'INFO' && match !== 'ERROR' && match !== 'WARNING') {
                    return '<span class="ticker">' + match + '</span>';
                }
                return match;
            });
            
            return line;
        }
        
        function changeLogType() {
            const selector = document.getElementById('log-selector');
            const newType = selector.value;
            const currentUrl = new URL(window.location);
            currentUrl.searchParams.set('type', newType);
            window.location.href = currentUrl.toString();
        }
        
        // Auto-refresh every second for countdown
        setInterval(updateCountdown, 1000);
        
        // Format log lines on page load
        window.onload = function() {
            const logContent = document.getElementById('log-content');
            if (logContent) {
                const lines = logContent.innerHTML.split('\\n');
                const formattedLines = lines.map(line => formatLogLine(line));
                logContent.innerHTML = formattedLines.join('\\n');
            }
        };
    </script>
</head>
<body>
    <div class="refresh-timer" id="timer">Refresh in {{ refresh_interval }}s</div>
    
    <div class="header">
        <h1>VSR Log Viewer</h1>
        <div class="info">
            <p>
                <label for="log-selector">Select Log: </label>
                <select id="log-selector" onchange="changeLogType()" style="background-color: #3e3e42; color: #d4d4d4; border: 1px solid #555; padding: 5px; border-radius: 3px;">
                    <option value="anomaly" {% if log_type == 'anomaly' %}selected{% endif %}>VSR Anomaly Log</option>
                    <option value="tracker" {% if log_type == 'tracker' %}selected{% endif %}>VSR Tracker Log</option>
                </select>
            </p>
            <p>Log File: {{ log_file }}</p>
            <p>Last Updated: {{ last_updated }}</p>
            <p>Showing last {{ lines_count }} lines | Auto-refresh every {{ refresh_interval }} seconds</p>
        </div>
    </div>
    
    <div class="log-container">
        {% if log_lines %}
        <div class="log-content" id="log-content">{{ log_lines }}</div>
        {% else %}
        <div class="no-data">No log data available</div>
        {% endif %}
    </div>
</body>
</html>
'''

def get_latest_log_file(log_type='anomaly'):
    """Get the most recent VSR log file of specified type"""
    if log_type not in LOG_PATHS:
        log_type = 'anomaly'
    
    log_base_path = LOG_PATHS[log_type]
    today = datetime.now().strftime('%Y%m%d')
    
    # Determine the log file pattern based on type
    if log_type == 'anomaly':
        log_file = os.path.join(log_base_path, f"vsr_anomaly_{today}.log")
        prefix = "vsr_anomaly_"
    else:  # tracker
        log_file = os.path.join(log_base_path, f"vsr_tracker_{today}.log")
        prefix = "vsr_tracker_"
    
    if os.path.exists(log_file):
        return log_file
    
    # If today's log doesn't exist, find the most recent one
    try:
        files = [f for f in os.listdir(log_base_path) if f.startswith(prefix) and f.endswith('.log')]
        if files:
            files.sort(reverse=True)
            return os.path.join(log_base_path, files[0])
    except Exception as e:
        logger.error(f"Error finding log files: {e}")
    
    return None

def read_last_n_lines(file_path, n=100):
    """Read the last n lines from a file efficiently"""
    try:
        with open(file_path, 'rb') as f:
            # Go to the end of the file
            f.seek(0, 2)
            file_size = f.tell()
            
            # Read chunks from the end until we have enough lines
            lines = []
            chunk_size = 8192
            remaining_size = file_size
            
            while len(lines) < n and remaining_size > 0:
                # Calculate chunk position
                chunk_start = max(0, remaining_size - chunk_size)
                chunk_len = remaining_size - chunk_start
                
                # Read chunk
                f.seek(chunk_start)
                chunk = f.read(chunk_len)
                
                # Split into lines
                chunk_lines = chunk.decode('utf-8', errors='ignore').splitlines()
                
                # If this is not the first chunk, the first line might be partial
                if chunk_start > 0:
                    chunk_lines = chunk_lines[1:]
                
                lines = chunk_lines + lines
                remaining_size = chunk_start
            
            # Return the last n lines
            return lines[-n:] if len(lines) > n else lines
            
    except Exception as e:
        logger.error(f"Error reading log file: {e}")
        return []

@app.route('/')
def index():
    """Main page showing log viewer"""
    log_type = request.args.get('type', 'anomaly')
    if log_type not in LOG_PATHS:
        log_type = 'anomaly'
    
    log_file = get_latest_log_file(log_type)
    
    if not log_file:
        return render_template_string(HTML_TEMPLATE,
                                    log_type=log_type,
                                    log_file="No log file found",
                                    last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    lines_count=0,
                                    refresh_interval=REFRESH_INTERVAL,
                                    log_lines=None)
    
    log_lines = read_last_n_lines(log_file, LINES_TO_DISPLAY)
    log_content = '\\n'.join(log_lines) if log_lines else ""
    
    return render_template_string(HTML_TEMPLATE,
                                log_type=log_type,
                                log_file=os.path.basename(log_file),
                                last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                lines_count=len(log_lines),
                                refresh_interval=REFRESH_INTERVAL,
                                log_lines=log_content)

@app.route('/api/logs')
def get_logs():
    """API endpoint to get log data as JSON"""
    log_type = request.args.get('type', 'anomaly')
    if log_type not in LOG_PATHS:
        log_type = 'anomaly'
    
    log_file = get_latest_log_file(log_type)
    
    if not log_file:
        return jsonify({
            'status': 'error',
            'message': 'No log file found',
            'log_type': log_type
        })
    
    log_lines = read_last_n_lines(log_file, LINES_TO_DISPLAY)
    
    return jsonify({
        'status': 'success',
        'log_type': log_type,
        'log_file': os.path.basename(log_file),
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'lines_count': len(log_lines),
        'log_lines': log_lines
    })

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='VSR Anomaly Log Viewer')
    parser.add_argument('--port', type=int, default=9901, help='Port to run the server on')
    parser.add_argument('--lines', type=int, default=100, help='Number of lines to display')
    parser.add_argument('--refresh', type=int, default=60, help='Refresh interval in seconds')
    
    args = parser.parse_args()
    
    LINES_TO_DISPLAY = args.lines
    REFRESH_INTERVAL = args.refresh
    
    logger.info(f"Starting VSR Anomaly Log Viewer on port {args.port}")
    logger.info(f"Displaying last {LINES_TO_DISPLAY} lines, refreshing every {REFRESH_INTERVAL} seconds")
    
    app.run(host='0.0.0.0', port=args.port, debug=False)