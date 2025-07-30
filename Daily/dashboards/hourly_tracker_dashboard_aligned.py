#!/usr/bin/env python3
"""
Hourly Tracker Dashboard (Aligned with VSR Dashboard)
Serves real-time hourly tracking data with same UI as VSR Dashboard
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask, render_template_string, jsonify
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)
IST = pytz.timezone('Asia/Kolkata')

# Try to import Kite for real-time prices
KITE_AVAILABLE = False
kite_client = None
try:
    from user_context_manager import UserContextManager
    context = UserContextManager("Sai")
    kite_client = context.kite
    KITE_AVAILABLE = True
except:
    print("Kite API not available - real-time prices disabled")

def get_latest_log_file():
    """Get the latest hourly tracker log file"""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'hourly_tracker')
    today = datetime.now().strftime('%Y%m%d')
    
    # First try aligned log
    aligned_log = os.path.join(log_dir, f'hourly_tracker_aligned_{today}.log')
    if os.path.exists(aligned_log):
        return aligned_log
    
    # Fall back to regular hourly tracker log
    regular_log = os.path.join(log_dir, f'hourly_tracker_{today}.log')
    if os.path.exists(regular_log):
        return regular_log
    
    return None

def parse_log_data(log_file, hours=4):
    """Parse the hourly tracker log file - aligned with VSR format"""
    if not log_file or not os.path.exists(log_file):
        return {}
    
    tickers_data = defaultdict(lambda: {
        'ticker': '',
        'score': 0,
        'vsr': 0.0,
        'price': 0.0,
        'volume': 0,
        'momentum': 0.0,
        'build': 0,
        'trend': '',
        'sector': '',
        'days_tracked': 0,
        'occurrences': 0,
        'last_seen': None,
        'scores': []
    })
    
    # Get current time and cutoff time (last N hours)
    current_time = datetime.now(IST)
    cutoff_time = current_time - timedelta(hours=hours)
    
    # Pattern matching aligned format (same as VSR)
    # [Sai] TICKER | Score: X | VSR: Y | Price: ₹Z | Vol: V | Momentum: M% | Build: B | Trend: T | Days: D | Sector: S
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+).*\[(\w+)\]\s+(\S+)\s+\|\s+Score:\s*(\d+)\s*\|\s*VSR:\s*([\d.]+)\s*\|\s*Price:\s*₹([\d,.]+)\s*\|\s*Vol:\s*([\d,]+)\s*\|\s*Momentum:\s*([\d.-]+)%\s*\|\s*Build:\s*(\d*)\s*\|\s*Trend:\s*([^|]+)\|\s*Days:\s*(\d+)\s*\|\s*Sector:\s*(.+)'
    
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
    
    # Calculate average score and filter
    result = {}
    for ticker, data in tickers_data.items():
        if data['scores']:
            data['avg_score'] = sum(data['scores']) / len(data['scores'])
            # Include all tickers with positive momentum
            if data['momentum'] >= 0:
                result[ticker] = data
    
    return result

def fetch_real_time_prices(tickers):
    """Fetch real-time prices and volume for given tickers"""
    if not KITE_AVAILABLE or not kite_client:
        return {}
    
    real_time_data = {}
    
    try:
        # Get LTP for all tickers in batches
        symbols = [f"NSE:{ticker}" for ticker in tickers]
        
        # Kite API has a limit on number of symbols per request
        batch_size = 100
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i+batch_size]
            try:
                quotes = kite_client.quote(batch)
                
                for symbol, quote_data in quotes.items():
                    ticker = symbol.replace("NSE:", "")
                    if quote_data:
                        real_time_data[ticker] = {
                            'price': quote_data.get('last_price', 0),
                            'volume': quote_data.get('volume', 0),
                            'change': quote_data.get('net_change', 0),
                            'change_percent': ((quote_data.get('last_price', 0) - quote_data.get('ohlc', {}).get('close', 0)) / quote_data.get('ohlc', {}).get('close', 1)) * 100 if quote_data.get('ohlc', {}).get('close', 0) > 0 else 0
                        }
            except Exception as e:
                print(f"Error fetching batch {i}: {e}")
                continue
                
    except Exception as e:
        print(f"Error fetching real-time data: {e}")
    
    return real_time_data

@app.route('/')
def index():
    """Render the main dashboard page - aligned with VSR dashboard"""
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Hourly Tracker Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #0f0f0f;
            color: #e0e0e0;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header-content h1 {
            font-size: 2.5em;
            font-weight: 600;
            background: linear-gradient(135deg, #4a9eff 0%, #00d4ff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 5px;
        }
        
        .last-updated {
            color: #888;
            font-size: 0.9em;
        }
        
        .real-time-status {
            color: #10b981;
            font-size: 12px;
            margin-top: 5px;
        }
        
        .refresh-btn {
            background: linear-gradient(135deg, #4a9eff 0%, #00d4ff 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        
        .refresh-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(74, 158, 255, 0.4);
        }
        
        .categories {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        
        .category-card {
            background: #1a1a1a;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }
        
        .category-title {
            font-size: 1.3em;
            font-weight: 600;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #333;
        }
        
        .icon-perfect { color: #ff6b6b; }
        .icon-vsr { color: #4ecdc4; }
        .icon-momentum { color: #ffe66d; }
        .icon-building { color: #a8ff78; }
        .icon-new { color: #ff78a8; }
        .icon-volume { color: #78d5ff; }
        
        .ticker-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .ticker-item {
            background: #252525;
            border-radius: 8px;
            padding: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.3s ease;
            border: 1px solid transparent;
        }
        
        .ticker-item:hover {
            background: #2a2a2a;
            border-color: #4a9eff;
            transform: translateX(5px);
        }
        
        .ticker-info {
            flex: 1;
        }
        
        .ticker-symbol {
            font-size: 1.1em;
            font-weight: 600;
            color: #4a9eff;
            margin-bottom: 5px;
        }
        
        .ticker-details {
            display: flex;
            gap: 15px;
            font-size: 0.85em;
            color: #888;
        }
        
        .detail-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .ticker-metrics {
            text-align: right;
        }
        
        .price {
            font-size: 1.1em;
            font-weight: 600;
            color: #e0e0e0;
        }
        
        .momentum {
            font-size: 0.9em;
            margin-top: 5px;
        }
        
        .positive { color: #10b981; }
        .negative { color: #ef4444; }
        
        .score-badge {
            background: linear-gradient(135deg, #ff6b6b 0%, #ff8787 100%);
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            margin-left: 10px;
        }
        
        .loading {
            text-align: center;
            padding: 50px;
            font-size: 1.2em;
            color: #666;
        }
        
        .error {
            background: #ff4444;
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        .vsr-indicator {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: 600;
        }
        
        .vsr-high { background: #4ecdc4; color: #000; }
        .vsr-medium { background: #ffe66d; color: #000; }
        .vsr-low { background: #666; color: #fff; }
        
        .volume-bar {
            height: 4px;
            background: #333;
            border-radius: 2px;
            margin-top: 5px;
            overflow: hidden;
        }
        
        .volume-fill {
            height: 100%;
            background: linear-gradient(90deg, #4a9eff 0%, #00d4ff 100%);
            transition: width 0.3s ease;
        }
        
        .trend-indicator {
            font-size: 0.8em;
            padding: 2px 6px;
            border-radius: 4px;
            margin-left: 5px;
        }
        
        .trend-up { background: #10b981; color: white; }
        .trend-down { background: #ef4444; color: white; }
        .trend-flat { background: #666; color: white; }
        
        .build-indicator {
            color: #a8ff78;
            font-weight: 600;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .real-time-update {
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-content">
                <h1>Hourly Tracker Dashboard - Long Reversal Hourly</h1>
                <div class="last-updated" id="lastUpdated"></div>
                <div class="real-time-status" id="realTimeStatus" style="color: #10b981; font-size: 12px; margin-top: 5px;"></div>
            </div>
            <button class="refresh-btn" onclick="refreshData()">🔄 Refresh</button>
        </div>
        
        <div id="loading" class="loading">Loading hourly tracker data...</div>
        <div id="error" class="error" style="display: none;"></div>
        
        <div id="categories" class="categories" style="display: none;">
            <!-- High Scores -->
            <div class="category-card">
                <h2 class="category-title icon-perfect">High Scores (≥50)</h2>
                <div id="highScores" class="ticker-list"></div>
            </div>
            
            <!-- High VSR -->
            <div class="category-card">
                <h2 class="category-title icon-vsr">High VSR (≥1.0)</h2>
                <div id="highVsr" class="ticker-list"></div>
            </div>
            
            <!-- Strong Momentum -->
            <div class="category-card">
                <h2 class="category-title icon-momentum">Strong Momentum (≥1%)</h2>
                <div id="strongMomentum" class="ticker-list"></div>
            </div>
            
            <!-- Building Momentum -->
            <div class="category-card">
                <h2 class="category-title icon-building">Building Momentum</h2>
                <div id="buildingMomentum" class="ticker-list"></div>
            </div>
            
            <!-- Multi-Day Tracking -->
            <div class="category-card">
                <h2 class="category-title icon-new">Multi-Day Tracking (≥2 days)</h2>
                <div id="multiDay" class="ticker-list"></div>
            </div>
            
            <!-- High Volume -->
            <div class="category-card">
                <h2 class="category-title icon-volume">High Volume Activity</h2>
                <div id="highVolume" class="ticker-list"></div>
            </div>
        </div>
    </div>
    
    <script>
        let tickersData = {};
        let realTimeData = {};
        
        function formatNumber(num) {
            if (num >= 10000000) return (num / 10000000).toFixed(2) + 'Cr';
            if (num >= 100000) return (num / 100000).toFixed(2) + 'L';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
            return num.toString();
        }
        
        function formatPrice(price) {
            return '₹' + price.toFixed(2);
        }
        
        function getTrendClass(trend) {
            if (trend.includes('UP')) return 'trend-up';
            if (trend.includes('DOWN')) return 'trend-down';
            return 'trend-flat';
        }
        
        function getVsrClass(vsr) {
            if (vsr >= 2.0) return 'vsr-high';
            if (vsr >= 1.0) return 'vsr-medium';
            return 'vsr-low';
        }
        
        function createTickerItem(ticker) {
            const data = tickersData[ticker];
            const realTime = realTimeData[ticker] || {};
            
            // Use real-time data if available
            const price = realTime.price || data.price;
            const volume = realTime.volume || data.volume;
            const momentum = realTime.change_percent !== undefined ? realTime.change_percent : data.momentum;
            
            const momentumClass = momentum >= 0 ? 'positive' : 'negative';
            const momentumSign = momentum >= 0 ? '+' : '';
            
            let buildIndicator = '';
            if (data.build > 0) {
                buildIndicator = `<span class="build-indicator">📈 ${data.build}</span>`;
            }
            
            return `
                <div class="ticker-item">
                    <div class="ticker-info">
                        <div class="ticker-symbol">${ticker}</div>
                        <div class="ticker-details">
                            <span class="detail-item">VSR: <span class="vsr-indicator ${getVsrClass(data.vsr)}">${data.vsr.toFixed(2)}</span></span>
                            <span class="detail-item">Vol: ${formatNumber(volume)}</span>
                            <span class="detail-item trend-indicator ${getTrendClass(data.trend)}">${data.trend}</span>
                            ${buildIndicator}
                            <span class="detail-item">Days: ${data.days_tracked}</span>
                        </div>
                        <div class="volume-bar">
                            <div class="volume-fill" style="width: ${Math.min(100, (volume / 1000000) * 100)}%"></div>
                        </div>
                    </div>
                    <div class="ticker-metrics">
                        <div class="price ${realTime.price ? 'real-time-update' : ''}">${formatPrice(price)}</div>
                        <div class="momentum ${momentumClass}">${momentumSign}${momentum.toFixed(2)}%</div>
                        <span class="score-badge">Score: ${data.score}</span>
                    </div>
                </div>
            `;
        }
        
        function updateCategories(data) {
            // Clear all categories
            document.getElementById('highScores').innerHTML = '';
            document.getElementById('highVsr').innerHTML = '';
            document.getElementById('strongMomentum').innerHTML = '';
            document.getElementById('buildingMomentum').innerHTML = '';
            document.getElementById('multiDay').innerHTML = '';
            document.getElementById('highVolume').innerHTML = '';
            
            // Convert to array and sort by score
            const tickers = Object.keys(data);
            
            // High Scores (≥50)
            const highScores = tickers.filter(t => data[t].score >= 50)
                .sort((a, b) => data[b].score - data[a].score);
            
            // High VSR (≥1.0)
            const highVsr = tickers.filter(t => data[t].vsr >= 1.0)
                .sort((a, b) => data[b].vsr - data[a].vsr);
            
            // Strong Momentum (≥1%)
            const strongMomentum = tickers.filter(t => data[t].momentum >= 1.0)
                .sort((a, b) => data[b].momentum - data[a].momentum);
            
            // Building Momentum
            const buildingMomentum = tickers.filter(t => data[t].build > 0)
                .sort((a, b) => data[b].build - data[a].build);
            
            // Multi-Day Tracking (≥2 days)
            const multiDay = tickers.filter(t => data[t].days_tracked >= 2)
                .sort((a, b) => data[b].days_tracked - data[a].days_tracked);
            
            // High Volume (top 20% by volume)
            const volumeSorted = [...tickers].sort((a, b) => data[b].volume - data[a].volume);
            const highVolume = volumeSorted.slice(0, Math.ceil(volumeSorted.length * 0.2));
            
            // Update categories
            highScores.forEach(ticker => {
                document.getElementById('highScores').innerHTML += createTickerItem(ticker);
            });
            
            highVsr.forEach(ticker => {
                document.getElementById('highVsr').innerHTML += createTickerItem(ticker);
            });
            
            strongMomentum.forEach(ticker => {
                document.getElementById('strongMomentum').innerHTML += createTickerItem(ticker);
            });
            
            buildingMomentum.forEach(ticker => {
                document.getElementById('buildingMomentum').innerHTML += createTickerItem(ticker);
            });
            
            multiDay.forEach(ticker => {
                document.getElementById('multiDay').innerHTML += createTickerItem(ticker);
            });
            
            highVolume.forEach(ticker => {
                document.getElementById('highVolume').innerHTML += createTickerItem(ticker);
            });
            
            // Add empty state messages
            if (highScores.length === 0) {
                document.getElementById('highScores').innerHTML = '<div class="empty-state">No tickers with score ≥50</div>';
            }
            if (highVsr.length === 0) {
                document.getElementById('highVsr').innerHTML = '<div class="empty-state">No tickers with VSR ≥1.0</div>';
            }
            if (strongMomentum.length === 0) {
                document.getElementById('strongMomentum').innerHTML = '<div class="empty-state">No tickers with momentum ≥1%</div>';
            }
            if (buildingMomentum.length === 0) {
                document.getElementById('buildingMomentum').innerHTML = '<div class="empty-state">No tickers building momentum</div>';
            }
            if (multiDay.length === 0) {
                document.getElementById('multiDay').innerHTML = '<div class="empty-state">No multi-day tracking tickers</div>';
            }
            if (highVolume.length === 0) {
                document.getElementById('highVolume').innerHTML = '<div class="empty-state">No high volume tickers</div>';
            }
        }
        
        async function fetchData() {
            try {
                const response = await fetch('/api/hourly_data');
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                
                if (data.error) {
                    throw new Error(data.error);
                }
                
                tickersData = data.tickers;
                realTimeData = data.real_time || {};
                
                // Update UI
                updateCategories(tickersData);
                
                // Update timestamp
                document.getElementById('lastUpdated').textContent = `Last updated: ${data.timestamp}`;
                
                // Update real-time status
                const hasRealTime = Object.keys(realTimeData).length > 0;
                document.getElementById('realTimeStatus').textContent = hasRealTime ? '🟢 Live prices active' : '';
                
                // Hide loading, show content
                document.getElementById('loading').style.display = 'none';
                document.getElementById('categories').style.display = 'grid';
                document.getElementById('error').style.display = 'none';
                
            } catch (error) {
                console.error('Error fetching data:', error);
                document.getElementById('error').textContent = `Error loading data: ${error.message}`;
                document.getElementById('error').style.display = 'block';
                document.getElementById('loading').style.display = 'none';
            }
        }
        
        function refreshData() {
            document.getElementById('loading').style.display = 'block';
            document.getElementById('categories').style.display = 'none';
            fetchData();
        }
        
        // Initial load
        fetchData();
        
        // Auto-refresh every 30 seconds
        setInterval(fetchData, 30000);
    </script>
</body>
</html>
    ''')

@app.route('/api/hourly_data')
def api_hourly_data():
    """API endpoint to get hourly tracker data"""
    try:
        log_file = get_latest_log_file()
        if not log_file:
            return jsonify({
                'error': 'No log file found',
                'tickers': {},
                'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')
            })
        
        # Parse log data
        tickers_data = parse_log_data(log_file)
        
        # Get real-time prices
        real_time_data = {}
        if tickers_data:
            tickers_list = list(tickers_data.keys())
            real_time_data = fetch_real_time_prices(tickers_list)
        
        return jsonify({
            'tickers': tickers_data,
            'real_time': real_time_data,
            'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST'),
            'log_file': os.path.basename(log_file)
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'tickers': {},
            'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')
        })

if __name__ == '__main__':
    print("Starting Hourly Tracker Dashboard (Aligned) on port 3002")
    print("Access the dashboard at: http://localhost:3002")
    app.run(host='0.0.0.0', port=3002, debug=True)