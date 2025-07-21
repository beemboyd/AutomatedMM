#!/usr/bin/env python3
"""
VSR Tracker Dashboard
Shows all trending tickers from VSR tracker logs
Runs on port 3001
"""

from flask import Flask, render_template, jsonify
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
import glob
import pytz

app = Flask(__name__)

# Configuration
PORT = 3001
VSR_LOG_DIR = "/Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_tracker"
IST = pytz.timezone('Asia/Kolkata')

def parse_vsr_logs(hours=2):
    """Parse VSR tracker logs from the last N hours"""
    tickers_data = defaultdict(lambda: {
        'ticker': '',
        'score': 0,
        'vsr': 0,
        'price': 0,
        'volume': 0,
        'momentum': 0,
        'build': 0,
        'trend': '',
        'sector': '',
        'occurrences': 0,
        'last_seen': None,
        'scores': []
    })
    
    # Get current time
    current_time = datetime.now(IST)
    cutoff_time = current_time - timedelta(hours=hours)
    
    # Get today's log file
    today = current_time.strftime('%Y%m%d')
    log_file = os.path.join(VSR_LOG_DIR, f'vsr_tracker_{today}.log')
    
    if not os.path.exists(log_file):
        return {}
    
    # Pattern to match VSR tracker log lines
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*\[(\w+)\]\s+(\S+)\s+\|\s+Score:\s*(\d+)\s*\|\s*VSR:\s*([\d.]+)\s*\|\s*Price:\s*₹([\d,.]+)\s*\|\s*Vol:\s*([\d,]+)\s*\|\s*Momentum:\s*([\d.]+)%\s*\|\s*Build:\s*(?:📈)?(\d*)\s*\|\s*Trend:\s*([^|]+)\|\s*Sector:\s*(.+)'
    
    with open(log_file, 'r') as f:
        for line in f:
            match = re.match(pattern, line)
            if match:
                timestamp_str = match.group(1)
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                timestamp = IST.localize(timestamp)
                
                # Skip if outside time window
                if timestamp < cutoff_time:
                    continue
                
                user = match.group(2)
                ticker = match.group(3).strip()
                score = int(match.group(4))
                vsr = float(match.group(5))
                price = float(match.group(6).replace(',', ''))
                volume = int(match.group(7).replace(',', ''))
                momentum = float(match.group(8))
                build = int(match.group(9)) if match.group(9) else 0
                trend = match.group(10).strip()
                sector = match.group(11).strip()
                
                # Update ticker data
                data = tickers_data[ticker]
                data['ticker'] = ticker
                data['score'] = score
                data['vsr'] = vsr
                data['price'] = price
                data['volume'] = volume
                data['momentum'] = momentum
                data['build'] = build
                data['trend'] = trend
                data['sector'] = sector
                data['occurrences'] += 1
                data['last_seen'] = timestamp
                data['scores'].append(score)
    
    # Calculate average score and filter
    result = {}
    for ticker, data in tickers_data.items():
        if data['scores']:
            data['avg_score'] = sum(data['scores']) / len(data['scores'])
            # Include tickers with high scores or high momentum
            if data['score'] >= 75 or data['momentum'] >= 5.0 or data['vsr'] >= 10.0:
                result[ticker] = data
    
    return result

def get_trending_tickers():
    """Get trending tickers sorted by various criteria"""
    tickers_data = parse_vsr_logs(hours=2)
    
    # Convert to list and sort
    tickers_list = list(tickers_data.values())
    
    # Sort by score, then VSR, then momentum
    tickers_list.sort(key=lambda x: (x['score'], x['vsr'], x['momentum']), reverse=True)
    
    # Categorize tickers
    categories = {
        'perfect_scores': [],
        'high_vsr': [],
        'high_momentum': [],
        'strong_build': [],
        'all_tickers': []
    }
    
    for ticker in tickers_list:
        categories['all_tickers'].append(ticker)
        
        if ticker['score'] == 100:
            categories['perfect_scores'].append(ticker)
        
        if ticker['vsr'] >= 10.0:
            categories['high_vsr'].append(ticker)
        
        if ticker['momentum'] >= 5.0:
            categories['high_momentum'].append(ticker)
        
        if ticker['build'] >= 10:
            categories['strong_build'].append(ticker)
    
    # Sort each category
    for category in categories:
        if category == 'high_vsr':
            categories[category].sort(key=lambda x: x['vsr'], reverse=True)
        elif category == 'high_momentum':
            categories[category].sort(key=lambda x: x['momentum'], reverse=True)
        elif category == 'strong_build':
            categories[category].sort(key=lambda x: x['build'], reverse=True)
    
    return categories

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('vsr_tracker_dashboard.html')

@app.route('/api/trending-tickers')
def api_trending_tickers():
    """API endpoint to get trending tickers"""
    try:
        categories = get_trending_tickers()
        
        # Add timestamp
        current_time = datetime.now(IST)
        response = {
            'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S IST'),
            'categories': categories,
            'total_tickers': len(categories['all_tickers'])
        }
        
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ticker-details/<ticker>')
def api_ticker_details(ticker):
    """Get detailed information for a specific ticker"""
    try:
        tickers_data = parse_vsr_logs(hours=24)  # Look at last 24 hours for details
        
        if ticker in tickers_data:
            return jsonify(tickers_data[ticker])
        else:
            return jsonify({'error': 'Ticker not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(template_dir, exist_ok=True)
    
    print(f"Starting VSR Tracker Dashboard on port {PORT}")
    print(f"Access the dashboard at: http://localhost:{PORT}")
    
    app.run(host='0.0.0.0', port=PORT, debug=True)