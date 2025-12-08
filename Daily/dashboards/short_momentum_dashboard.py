#!/usr/bin/env python3
"""
Short Momentum Tracker Dashboard
Shows all short momentum tickers from tracker logs
Runs on port 3003
Matches VSR dashboard design and functionality
"""

from flask import Flask, render_template, jsonify
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
import glob
import pytz
import sys
import json
import logging
import math

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__, static_folder='static', static_url_path='/static')

# Configuration
PORT = 3003
SHORT_LOG_DIR = "/Users/maverick/PycharmProjects/India-TS/Daily/logs/short_momentum"
SHORT_DATA_DIR = "/Users/maverick/PycharmProjects/India-TS/Daily/data/short_momentum"
IST = pytz.timezone('Asia/Kolkata')

def clean_nan_values(obj):
    """Replace NaN values with 0 in nested dictionaries/lists"""
    if isinstance(obj, dict):
        return {k: clean_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan_values(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0
        return obj
    return obj

def parse_short_momentum_logs(hours=2):
    """Parse short momentum tracker logs from the last N hours"""
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
        'scores': [],
        'days_tracked': 0,
        'price_change_1h': 0,
        'price_change_3h': 0,
        'price_change_1d': 0,
        'rsi': 50,
        'persistence_score': 0
    })
    
    # Get current time
    current_time = datetime.now(IST)
    cutoff_time = current_time - timedelta(hours=hours)
    
    # Get today's log file
    today = current_time.strftime('%Y%m%d')
    log_file = os.path.join(SHORT_LOG_DIR, f'short_momentum_tracker_{today}.log')
    
    if not os.path.exists(log_file):
        print(f"No log file found for today ({today})")
        return {}
    
    # Pattern to match short momentum tracker log lines (VSR-style format)
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*\[(\w+)\]\s+(\S+)\s+\|\s+Score:\s*(\d+)\s*\|\s*VSR:\s*([\d.]+)\s*\|\s*Price:\s*₹([\d,.]+)\s*\|\s*Vol:\s*([\d,]+)\s*\|\s*Momentum:\s*([-\d.]+)%\s*\|\s*Build:\s*(\d+)\s*\|\s*Trend:\s*([^|]+)\|\s*Days:\s*(\d+)\s*\|\s*Sector:\s*(.+)'
    
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
                # Handle NaN/Inf values
                if math.isnan(vsr) or math.isinf(vsr):
                    vsr = 0.0
                price = float(match.group(6).replace(',', ''))
                volume = int(match.group(7).replace(',', ''))
                momentum = float(match.group(8))
                build = int(match.group(9))
                trend = match.group(10).strip()
                days_tracked = int(match.group(11))
                sector = match.group(12).strip()
                
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
                data['days_tracked'] = days_tracked
                data['occurrences'] += 1
                data['last_seen'] = timestamp
                data['scores'].append(score)
    
    # Also load from latest JSON for complete data
    latest_json = os.path.join(SHORT_DATA_DIR, 'latest_short_momentum.json')
    if os.path.exists(latest_json):
        try:
            with open(latest_json, 'r') as f:
                json_data = json.load(f)
                
            if 'results' in json_data:
                for ticker_data in json_data['results']:
                    ticker = ticker_data['ticker']
                    if ticker not in tickers_data:
                        tickers_data[ticker] = {
                            'ticker': ticker,
                            'score': ticker_data.get('total_score', 0),
                            'vsr': ticker_data.get('vsr', 0),
                            'price': ticker_data.get('close', 0),
                            'volume': ticker_data.get('volume', 0),
                            'momentum': ticker_data.get('price_change_1d', 0),
                            'build': ticker_data.get('momentum_score', 0),
                            'trend': ticker_data.get('momentum_status', ''),
                            'sector': ticker_data.get('sector', 'Unknown'),
                            'days_tracked': ticker_data.get('appearances', 0),
                            'occurrences': 1,
                            'last_seen': datetime.now(IST),
                            'scores': [ticker_data.get('total_score', 0)],
                            'price_change_1h': ticker_data.get('price_change_1h', 0),
                            'price_change_3h': ticker_data.get('price_change_3h', 0),
                            'price_change_1d': ticker_data.get('price_change_1d', 0),
                            'rsi': ticker_data.get('rsi', 50),
                            'persistence_score': ticker_data.get('persistence_score', 0)
                        }
        except Exception as e:
            print(f"Error loading JSON data: {e}")
    
    # Calculate average score and filter
    result = {}
    for ticker, data in tickers_data.items():
        if data['scores']:
            data['avg_score'] = sum(data['scores']) / len(data['scores'])
            # Include tickers with negative momentum (short opportunities)
            if data['momentum'] < 0:  # Negative momentum for shorts
                result[ticker] = data
    
    return result

def get_short_momentum_tickers():
    """Get short momentum tickers sorted by various criteria"""
    tickers_data = parse_short_momentum_logs(hours=24)  # Look at last 24 hours
    
    # Convert to list and filter for negative momentum only
    tickers_list = [ticker for ticker in tickers_data.values() if ticker['momentum'] < 0]
    
    # Sort by score, then VSR (inverted for shorts), then momentum (more negative is better)
    tickers_list.sort(key=lambda x: (x['score'], -x['vsr'], -x['momentum']), reverse=True)
    
    # Categorize tickers
    categories = {
        'high_scores': [],  # Score >= 80
        'strong_negative': [],  # Momentum < -2%
        'low_rsi': [],  # RSI < 40
        'high_volume': [],  # Volume ratio > 1.5
        'persistence_leaders': [],  # Days tracked >= 10
        'new_shorts': [],  # New short opportunities
        'all_tickers': []
    }
    
    for ticker in tickers_list:
        categories['all_tickers'].append(ticker)
        
        if ticker['score'] >= 80:
            categories['high_scores'].append(ticker)
        
        if ticker['momentum'] < -2:
            categories['strong_negative'].append(ticker)
        
        if ticker.get('rsi', 50) < 40:
            categories['low_rsi'].append(ticker)
        
        if ticker['days_tracked'] >= 10:
            categories['persistence_leaders'].append(ticker)
        
        if ticker['days_tracked'] <= 2 and ticker['momentum'] < -1:
            categories['new_shorts'].append(ticker)
        
        # Check volume (would need volume ratio in data)
        if ticker['volume'] > 100000:  # High volume threshold
            categories['high_volume'].append(ticker)
    
    # Sort each category
    for category in categories:
        if category == 'strong_negative':
            categories[category].sort(key=lambda x: x['momentum'])  # Most negative first
        elif category == 'low_rsi':
            categories[category].sort(key=lambda x: x.get('rsi', 50))
        elif category == 'persistence_leaders':
            categories[category].sort(key=lambda x: (x['days_tracked'], x['score']), reverse=True)
        elif category == 'high_scores':
            categories[category].sort(key=lambda x: x['score'], reverse=True)
        elif category == 'high_volume':
            categories[category].sort(key=lambda x: x['volume'], reverse=True)
    
    return categories

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('short_momentum_dashboard.html')

@app.route('/api/short-momentum')
def api_short_momentum():
    """API endpoint to get short momentum tickers"""
    try:
        categories = get_short_momentum_tickers()
        
        # Add timestamp
        current_time = datetime.now(IST)
        response = {
            'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S IST'),
            'categories': categories,
            'total_tickers': len(categories['all_tickers']),
            'tracker_type': 'short_momentum'
        }
        
        # Clean any NaN values before sending
        response = clean_nan_values(response)
        
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ticker-details/<ticker>')
def api_ticker_details(ticker):
    """Get detailed information for a specific ticker"""
    try:
        tickers_data = parse_short_momentum_logs(hours=24)
        
        if ticker in tickers_data:
            # Clean any NaN values before sending
            ticker_data = clean_nan_values(tickers_data[ticker])
            return jsonify(ticker_data)
        else:
            return jsonify({'error': 'Ticker not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(template_dir, exist_ok=True)
    
    print(f"Starting Short Momentum Dashboard on port {PORT}")
    print(f"Access the dashboard at: http://localhost:{PORT}")
    
    app.run(host='0.0.0.0', port=PORT, debug=True)