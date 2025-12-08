#!/usr/bin/env python3
"""
Hourly Tracker Dashboard
Monitors Long Reversal Hourly scanner results with VSR analysis
Port: 3002
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
import json
import os
import datetime
import logging
from collections import defaultdict
import re
import requests

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BASE_DIR, 'logs', 'hourly_tracker')
DATA_DIR = os.path.join(BASE_DIR, 'data')

def parse_hourly_logs(hours=2):
    """Parse hourly tracker logs to extract trending tickers"""
    trending_tickers = defaultdict(list)
    
    # Get current date log file
    today = datetime.datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(LOGS_DIR, f'hourly_tracker_{today}.log')
    
    if not os.path.exists(log_file):
        logger.warning(f"Log file not found: {log_file}")
        return trending_tickers
    
    # Time cutoff
    cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
    
    # Patterns to match
    ticker_pattern = re.compile(
        r'\[(.*?)\]\s+(\w+)\s*\|\s*'
        r'Score:\s*(\d+)\s*\|\s*'
        r'VSR:\s*([\d.]+)\s*\|\s*'
        r'Price:\s*₹\s*([\d.]+)\s*\|\s*'
        r'Vol:\s*([\d,]+)\s*\|\s*'
        r'Momentum:\s*([-\d.]+)%\s*\|\s*'
        r'Build:\s*([-\d]+)\s*\|\s*'
        r'Trend:\s*(\w+)\s*\|\s*'
        r'Days:\s*(\d+)\s*\|\s*'
        r'Sector:\s*(.+?)$'
    )
    
    top_pattern = re.compile(
        r'(\d+)\.\s*\[(.*?)\]\s+(\w+)\s*\|\s*'
        r'Score:\s*(\d+)\s*\|\s*'
        r'VSR:\s*([\d.]+)\s*\|\s*'
        r'Price:\s*₹([\d.]+)\s*\|\s*'
        r'Momentum:\s*([-\d.]+)%\s*\|\s*'
        r'Sector:\s*([^|]+)'
    )
    
    try:
        with open(log_file, 'r') as f:
            for line in f:
                # Extract timestamp
                timestamp_match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if not timestamp_match:
                    continue
                
                timestamp = datetime.datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
                
                # Skip old entries
                if timestamp < cutoff_time:
                    continue
                
                # Try to match ticker pattern
                match = ticker_pattern.search(line)
                if not match:
                    match = top_pattern.search(line)
                    if match:
                        # Rearrange groups for top pattern
                        groups = match.groups()
                        ticker = groups[2]
                        score = int(groups[3])
                        vsr = float(groups[4])
                        price = float(groups[5])
                        volume = 0  # Not in top pattern
                        momentum = float(groups[6])
                        build = 0  # Not in top pattern
                        trend = "Unknown"
                        sector = groups[7].strip()
                    else:
                        continue
                else:
                    groups = match.groups()
                    ticker = groups[1]
                    score = int(groups[2])
                    vsr = float(groups[3])
                    price = float(groups[4])
                    volume = int(groups[5].replace(',', ''))
                    momentum = float(groups[6])
                    build = float(groups[7])
                    trend = groups[8]
                    days = int(groups[9])
                    sector = groups[10].strip()
                
                # Store ticker data
                ticker_data = {
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'ticker': ticker,
                    'score': score,
                    'vsr': vsr,
                    'price': price,
                    'volume': volume,
                    'momentum': momentum,
                    'build': build,
                    'trend': trend,
                    'sector': sector
                }
                
                trending_tickers[ticker].append(ticker_data)
                
    except Exception as e:
        logger.error(f"Error parsing log file: {e}")
    
    return trending_tickers

def fetch_liquidity_data(tickers):
    """Fetch liquidity data for multiple tickers from the API"""
    liquidity_data = {}
    
    # Fetch individually since batch API returns null for uncached data
    for ticker in tickers:
        try:
            response = requests.get(
                f'http://localhost:5555/liquidity/{ticker}',
                timeout=2
            )
            if response.status_code == 200:
                result = response.json()
                if result.get('data'):
                    liquidity_data[ticker] = result['data']
        except Exception as e:
            logger.debug(f"Error fetching liquidity for {ticker}: {e}")
            continue
    
    return liquidity_data

def get_latest_ticker_data(trending_tickers):
    """Get the most recent data for each ticker"""
    latest_data = {}
    
    for ticker, data_list in trending_tickers.items():
        # Sort by timestamp and get the latest
        sorted_data = sorted(data_list, key=lambda x: x['timestamp'], reverse=True)
        latest = sorted_data[0]
        
        # Add appearance count
        latest['appearances'] = len(data_list)
        latest['first_seen'] = sorted_data[-1]['timestamp']
        latest['last_seen'] = sorted_data[0]['timestamp']
        
        latest_data[ticker] = latest
    
    return latest_data

def categorize_tickers(latest_data, persistence_data=None, liquidity_data=None):
    """Categorize tickers based on criteria and persistence tiers"""
    categories = {
        'liquid_stocks': [],  # Grade B+ and above (high liquidity) with positive momentum
        'perfect_scores': [],
        'high_vsr': [],
        'high_momentum': [],
        'strong_build': [],
        'all_tickers': [],
        # Persistence tiers
        'extreme_persistence': [],  # 75+ alerts
        'very_high_persistence': [],  # 51-75 alerts  
        'high_persistence': [],  # 26-50 alerts
        'medium_persistence': [],  # 11-25 alerts
        'low_persistence': []  # 1-10 alerts
    }
    
    for ticker, data in latest_data.items():
        # FILTER: Only include tickers with positive momentum
        if data.get('momentum', 0) <= 0:
            continue
            
        # Add liquidity info if available
        if liquidity_data and ticker in liquidity_data:
            liq = liquidity_data[ticker]
            data['liquidity_grade'] = liq.get('liquidity_grade', 'F')
            data['liquidity_score'] = liq.get('liquidity_score', 0)
            data['avg_turnover_cr'] = liq.get('avg_daily_turnover_cr', 0)
        
        # Add persistence info if available
        if persistence_data and 'tickers' in persistence_data:
            ticker_persistence = persistence_data['tickers'].get(ticker, {})
            if ticker_persistence:
                # Calculate total alerts (sum of all scores > 0)
                scores = ticker_persistence.get('scores', [])
                total_alerts = len([s for s in scores if s > 0])
                data['persistence_alerts'] = total_alerts
                data['persistence_days'] = ticker_persistence.get('days_tracked', 0)
                data['avg_score'] = ticker_persistence.get('avg_score', 0)
                data['max_score'] = ticker_persistence.get('max_score', 0)
                
                # Categorize by persistence tier
                if total_alerts >= 75:
                    categories['extreme_persistence'].append(data)
                elif total_alerts >= 51:
                    categories['very_high_persistence'].append(data)
                elif total_alerts >= 26:
                    categories['high_persistence'].append(data)
                elif total_alerts >= 11:
                    categories['medium_persistence'].append(data)
                elif total_alerts >= 1:
                    categories['low_persistence'].append(data)
        
        # Add to all tickers (only positive momentum)
        categories['all_tickers'].append(data)
        
        # Liquid stocks - Grade B+ and above with positive momentum
        liquidity_grade = data.get('liquidity_grade', 'F')
        if liquidity_grade in ['A', 'A+', 'B', 'B+'] and data.get('momentum', 0) > 0:
            categories['liquid_stocks'].append(data)
        
        # Categorize (only positive momentum tickers)
        if data['score'] == 100:
            categories['perfect_scores'].append(data)
        
        if data['vsr'] >= 10:
            categories['high_vsr'].append(data)
            
        if data['momentum'] >= 5:
            categories['high_momentum'].append(data)
            
        if data.get('build', 0) >= 10:
            categories['strong_build'].append(data)
    
    # Sort each category by score (descending), persistence tiers by alerts count
    for category in categories:
        if 'persistence' in category:
            # Sort persistence tiers by number of alerts
            categories[category].sort(key=lambda x: x.get('persistence_alerts', 0), reverse=True)
        elif category == 'liquid_stocks':
            # Sort liquid stocks by persistence (alerts), then score, then momentum
            categories[category].sort(key=lambda x: (
                x.get('persistence_alerts', 0),  # Higher persistence first
                x['score'],  # Higher score second
                x.get('momentum', 0)  # Higher momentum third
            ), reverse=True)
        else:
            categories[category].sort(key=lambda x: x['score'], reverse=True)
    
    return categories

def load_state_file():
    """Load the latest state from hourly tracker"""
    state_file = os.path.join(DATA_DIR, 'hourly_tracker_state.json')
    
    try:
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading state file: {e}")
    
    return None

@app.route('/')
def index():
    """Render the dashboard"""
    return render_template('hourly_tracker_dashboard.html')

@app.route('/api/trending-tickers')
def get_trending_tickers():
    """API endpoint to get trending tickers"""
    try:
        # Load persistence data
        persistence_data = None
        persistence_file = os.path.join(DATA_DIR, 'vsr_ticker_persistence_hourly_long.json')
        if os.path.exists(persistence_file):
            with open(persistence_file, 'r') as f:
                persistence_data = json.load(f)
        
        # Parse logs
        trending_tickers = parse_hourly_logs(hours=2)
        latest_data = get_latest_ticker_data(trending_tickers)
        
        # Fetch liquidity data for all tickers
        liquidity_data = {}
        if latest_data:
            tickers = list(latest_data.keys())
            liquidity_data = fetch_liquidity_data(tickers)
        
        categories = categorize_tickers(latest_data, persistence_data, liquidity_data)
        
        # Also load state file for additional data
        state = load_state_file()
        
        # Count only positive momentum tickers
        positive_momentum_count = len(categories.get('all_tickers', []))
        
        response = {
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST'),
            'categories': categories,
            'total_tickers': positive_momentum_count,
            'filter_mode': 'POSITIVE_MOMENTUM_ONLY',
            'state_data': state
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in get_trending_tickers: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ticker-details/<ticker>')
def get_ticker_details(ticker):
    """Get detailed history for a specific ticker"""
    try:
        # Parse logs for last 24 hours
        trending_tickers = parse_hourly_logs(hours=24)
        
        if ticker not in trending_tickers:
            return jsonify({'error': 'Ticker not found'}), 404
        
        # Sort by timestamp
        ticker_history = sorted(trending_tickers[ticker], key=lambda x: x['timestamp'])
        
        response = {
            'ticker': ticker,
            'history': ticker_history,
            'total_appearances': len(ticker_history)
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in get_ticker_details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/hourly-persistence')
def get_hourly_persistence():
    """Get hourly persistence data"""
    try:
        persistence_file = os.path.join(DATA_DIR, 'vsr_ticker_persistence_hourly_long.json')
        
        if os.path.exists(persistence_file):
            with open(persistence_file, 'r') as f:
                data = json.load(f)
            return jsonify(data)
        else:
            return jsonify({'error': 'Persistence file not found'}), 404
            
    except Exception as e:
        logger.error(f"Error loading persistence: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Starting Hourly Tracker Dashboard on port 3002...")
    print("Access the dashboard at: http://localhost:3002")
    app.run(host='0.0.0.0', port=3002, debug=False)