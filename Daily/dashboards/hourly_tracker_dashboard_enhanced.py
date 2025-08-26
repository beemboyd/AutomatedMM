#!/usr/bin/env python3
"""
Enhanced Hourly Tracker Dashboard with Persistence Levels
Monitors Long Reversal Hourly scanner results with VSR analysis and persistence categorization
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

app = Flask(__name__)
CORS(app)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BASE_DIR, 'logs', 'hourly_tracker')
DATA_DIR = os.path.join(BASE_DIR, 'data')

# Persistence level definitions based on hourly alerts
PERSISTENCE_LEVELS = {
    'Extreme': {'min': 75, 'max': float('inf'), 'color': '#FF1744', 'position_size': '12.5%', 'win_rate': '100%', 'avg_return': '9.68%'},
    'Very High': {'min': 51, 'max': 75, 'color': '#FF6F00', 'position_size': '10%', 'win_rate': '100%', 'avg_return': '5.73%'},
    'High': {'min': 26, 'max': 50, 'color': '#FFC107', 'position_size': '7.5%', 'win_rate': '88.9%', 'avg_return': '2.72%'},
    'Medium': {'min': 11, 'max': 25, 'color': '#4CAF50', 'position_size': '5%', 'win_rate': '76.5%', 'avg_return': '1.49%'},
    'Low': {'min': 1, 'max': 10, 'color': '#9E9E9E', 'position_size': '2.5%', 'win_rate': '45.2%', 'avg_return': '0.28%'}
}

def get_persistence_level(alert_count):
    """Determine persistence level based on alert count"""
    for level, criteria in PERSISTENCE_LEVELS.items():
        if criteria['min'] <= alert_count <= criteria['max']:
            return level, criteria
    return 'Low', PERSISTENCE_LEVELS['Low']

def load_persistence_data():
    """Load VSR ticker persistence data"""
    persistence_file = os.path.join(DATA_DIR, 'vsr_ticker_persistence_hourly_long.json')
    
    if os.path.exists(persistence_file):
        try:
            with open(persistence_file, 'r') as f:
                data = json.load(f)
                # Handle new format with 'tickers' key
                if 'tickers' in data:
                    return data['tickers']
                return data
        except Exception as e:
            logger.error(f"Error loading persistence data: {e}")
    return {}

def load_persistence_history():
    """Load persistence level change history"""
    history_file = os.path.join(DATA_DIR, 'persistence_level_changes.json')
    
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def parse_hourly_logs(hours=2):
    """Parse hourly tracker logs to extract trending tickers with persistence data"""
    trending_tickers = defaultdict(list)
    persistence_data = load_persistence_data()
    
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
                if match:
                    groups = match.groups()
                    ticker = groups[1]
                    
                    # Get persistence data for this ticker
                    ticker_persistence = persistence_data.get(ticker, {})
                    alert_count = ticker_persistence.get('alert_count', 0)
                    persistence_level, level_info = get_persistence_level(alert_count)
                    
                    ticker_data = {
                        'ticker': ticker,
                        'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        'score': int(groups[2]),
                        'vsr': float(groups[3]),
                        'price': float(groups[4]),
                        'volume': int(groups[5].replace(',', '')),
                        'momentum': float(groups[6]),
                        'build': int(groups[7]),
                        'trend': groups[8],
                        'days': int(groups[9]),
                        'sector': groups[10].strip(),
                        'alert_count': alert_count,
                        'persistence_level': persistence_level,
                        'level_color': level_info['color'],
                        'position_size': level_info['position_size'],
                        'expected_win_rate': level_info['win_rate'],
                        'expected_return': level_info['avg_return']
                    }
                    
                    trending_tickers[ticker].append(ticker_data)
    except Exception as e:
        logger.error(f"Error parsing log file: {e}")
    
    return trending_tickers

def get_latest_ticker_data(trending_tickers):
    """Get the latest data for each ticker"""
    latest_data = {}
    
    for ticker, entries in trending_tickers.items():
        if entries:
            # Get the most recent entry
            latest_entry = max(entries, key=lambda x: x['timestamp'])
            latest_data[ticker] = latest_entry
    
    return latest_data

def categorize_tickers_by_persistence(latest_data):
    """Categorize tickers based on persistence levels"""
    categories = {
        'Extreme': [],
        'Very High': [],
        'High': [],
        'Medium': [],
        'Low': [],
        'all_tickers': []
    }
    
    for ticker, data in latest_data.items():
        # FILTER: Only include tickers with positive momentum
        if data.get('momentum', 0) <= 0:
            continue
            
        # Add to all tickers (only positive momentum)
        categories['all_tickers'].append(data)
        
        # Add to persistence category
        persistence_level = data.get('persistence_level', 'Low')
        if persistence_level in categories:
            categories[persistence_level].append(data)
    
    # Sort each category by alert count (descending) then by score
    for category in categories:
        categories[category].sort(key=lambda x: (x.get('alert_count', 0), x.get('score', 0)), reverse=True)
    
    return categories

def check_persistence_transitions():
    """Check for tickers that have moved between persistence levels"""
    transitions = []
    persistence_data = load_persistence_data()
    history = load_persistence_history()
    
    for ticker, data in persistence_data.items():
        alert_count = data.get('alert_count', 0)
        current_level, _ = get_persistence_level(alert_count)
        
        # Check if this ticker has history
        if ticker in history:
            previous_level = history[ticker].get('level')
            if previous_level and previous_level != current_level:
                # Level has changed
                transitions.append({
                    'ticker': ticker,
                    'from_level': previous_level,
                    'to_level': current_level,
                    'alert_count': alert_count,
                    'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
    
    return transitions

@app.route('/')
def index():
    """Render the enhanced dashboard"""
    return render_template('hourly_tracker_dashboard_enhanced.html')

@app.route('/api/trending-tickers')
def get_trending_tickers():
    """API endpoint to get trending tickers with persistence levels"""
    try:
        # Parse logs
        trending_tickers = parse_hourly_logs(hours=2)
        latest_data = get_latest_ticker_data(trending_tickers)
        categories = categorize_tickers_by_persistence(latest_data)
        
        # Check for persistence level transitions
        transitions = check_persistence_transitions()
        
        # Calculate statistics
        stats = {}
        for level in PERSISTENCE_LEVELS.keys():
            level_tickers = categories.get(level, [])
            stats[level] = {
                'count': len(level_tickers),
                'info': PERSISTENCE_LEVELS[level],
                'top_tickers': level_tickers[:3] if level_tickers else []
            }
        
        response = {
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST'),
            'categories': categories,
            'persistence_stats': stats,
            'transitions': transitions,
            'total_tickers': len(categories.get('all_tickers', [])),
            'filter_mode': 'POSITIVE_MOMENTUM_WITH_PERSISTENCE'
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in get_trending_tickers: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ticker-details/<ticker>')
def get_ticker_details(ticker):
    """Get detailed history for a specific ticker including persistence evolution"""
    try:
        # Parse logs for last 24 hours
        trending_tickers = parse_hourly_logs(hours=24)
        
        if ticker not in trending_tickers:
            return jsonify({'error': 'Ticker not found'}), 404
        
        # Sort by timestamp
        ticker_history = sorted(trending_tickers[ticker], key=lambda x: x['timestamp'])
        
        # Get persistence history
        persistence_data = load_persistence_data()
        ticker_persistence = persistence_data.get(ticker, {})
        
        response = {
            'ticker': ticker,
            'history': ticker_history,
            'persistence_data': ticker_persistence,
            'current_level': ticker_history[-1]['persistence_level'] if ticker_history else 'Unknown',
            'alert_count': ticker_persistence.get('alert_count', 0)
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in get_ticker_details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/persistence-levels')
def get_persistence_levels():
    """Get persistence level definitions and current distribution"""
    try:
        persistence_data = load_persistence_data()
        
        # Calculate distribution
        distribution = {level: 0 for level in PERSISTENCE_LEVELS.keys()}
        
        for ticker, data in persistence_data.items():
            alert_count = data.get('alert_count', 0)
            level, _ = get_persistence_level(alert_count)
            distribution[level] += 1
        
        response = {
            'levels': PERSISTENCE_LEVELS,
            'distribution': distribution,
            'total_tracked': sum(distribution.values())
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in get_persistence_levels: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3002, debug=False)