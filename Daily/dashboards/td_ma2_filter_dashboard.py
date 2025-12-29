#!/usr/bin/env python3
"""
TD MA II Filter Dashboard
Filters VSR alerts using Tom DeMark MA II Blue conditions

Port: 3005

Filter Logic (from PineScript):
- MA2 Fast (3-SMA): Blue when rising/flat over 2 bars (ROC >= 0)
- MA2 Slow (34-SMA): Blue when rising/flat over 1 bar (ROC >= 0)
- Entry Valid: Both Blue AND Fast > Slow

Shows tickers from VSR dashboard that pass the TD MA II filter.
"""

from flask import Flask, jsonify, Response
import os
import sys
import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pytz
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Kite for historical data
try:
    from scanners.VSR_Momentum_Scanner import load_daily_config, initialize_kite
    KITE_AVAILABLE = True
except ImportError:
    KITE_AVAILABLE = False
    logger.warning("Kite modules not available")

app = Flask(__name__)

# Configuration
PORT = 3005
VSR_API_URL = "http://localhost:3001/api/trending-tickers"
IST = pytz.timezone('Asia/Kolkata')

# Cache settings
PRICE_CACHE_TTL = 300  # 5 minutes
FILTER_CACHE_TTL = 60  # 1 minute

# Initialize Kite client
kite_client = None
instrument_cache = {}

def init_kite():
    """Initialize Kite client"""
    global kite_client, instrument_cache
    if not KITE_AVAILABLE:
        return False
    try:
        config = load_daily_config('Sai')
        kite_client = initialize_kite()
        # Load instruments for token lookup
        instruments = kite_client.instruments("NSE")
        instrument_cache = {i['tradingsymbol']: i['instrument_token'] for i in instruments}
        logger.info(f"Kite initialized. Loaded {len(instrument_cache)} instruments.")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Kite: {e}")
        return False


def get_instrument_token(ticker: str) -> Optional[int]:
    """Get instrument token for a ticker"""
    return instrument_cache.get(ticker)


def fetch_historical_data(ticker: str, days: int = 60) -> Optional[pd.DataFrame]:
    """
    Fetch historical daily OHLC data for a ticker

    Args:
        ticker: Stock symbol
        days: Number of days of history (need 34+ for slow MA)

    Returns:
        DataFrame with OHLC data or None
    """
    if not kite_client:
        return None

    token = get_instrument_token(ticker)
    if not token:
        logger.warning(f"No instrument token for {ticker}")
        return None

    try:
        now = datetime.now(IST)
        from_date = (now - timedelta(days=days)).strftime('%Y-%m-%d')
        to_date = now.strftime('%Y-%m-%d')

        data = kite_client.historical_data(
            instrument_token=token,
            from_date=from_date,
            to_date=to_date,
            interval='day'
        )

        if not data or len(data) < 35:  # Need at least 35 bars for 34-SMA
            logger.warning(f"{ticker}: Insufficient data ({len(data) if data else 0} bars)")
            return None

        df = pd.DataFrame(data)
        df.columns = [c.lower() for c in df.columns]
        return df

    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {e}")
        return None


def calculate_td_ma2_blue(df: pd.DataFrame) -> Dict:
    """
    Calculate TD MA II Blue conditions

    From PineScript:
    - smaFast = ta.sma(close, 3)
    - smaSlow = ta.sma(close, 34)
    - rocFast = smaFast - smaFast[2]  (change over 2 bars)
    - rocSlow = smaSlow - smaSlow[1]  (change over 1 bar)
    - Fast Blue: rocFast >= 0
    - Slow Blue: rocSlow >= 0
    - Entry Valid: Fast Blue AND Slow Blue AND Fast > Slow

    Returns:
        Dict with MA2 state and values
    """
    if df is None or len(df) < 35:
        return {
            'valid': False,
            'error': 'Insufficient data'
        }

    try:
        # Calculate SMAs
        df['ma2_fast'] = df['close'].rolling(window=3).mean()
        df['ma2_slow'] = df['close'].rolling(window=34).mean()

        # Calculate ROC (Rate of Change)
        # Fast: change over 2 bars
        df['roc_fast'] = df['ma2_fast'] - df['ma2_fast'].shift(2)
        # Slow: change over 1 bar
        df['roc_slow'] = df['ma2_slow'] - df['ma2_slow'].shift(1)

        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else None

        ma2_fast = latest['ma2_fast']
        ma2_slow = latest['ma2_slow']
        roc_fast = latest['roc_fast']
        roc_slow = latest['roc_slow']
        close = latest['close']

        # Blue conditions (convert to Python bool to avoid JSON serialization issues)
        fast_blue = bool(roc_fast >= 0)
        slow_blue = bool(roc_slow >= 0)
        both_blue = fast_blue and slow_blue

        # Fast above Slow
        fast_above_slow = bool(ma2_fast > ma2_slow)

        # Entry valid: Both Blue AND Fast > Slow
        entry_valid = both_blue and fast_above_slow

        # Calculate distance from MAs (for display)
        pct_above_fast = float((close - ma2_fast) / ma2_fast * 100) if ma2_fast > 0 else 0.0
        pct_above_slow = float((close - ma2_slow) / ma2_slow * 100) if ma2_slow > 0 else 0.0

        return {
            'valid': True,
            'close': round(float(close), 2),
            'ma2_fast': round(float(ma2_fast), 2),
            'ma2_slow': round(float(ma2_slow), 2),
            'roc_fast': round(float(roc_fast), 4),
            'roc_slow': round(float(roc_slow), 4),
            'fast_blue': fast_blue,
            'slow_blue': slow_blue,
            'both_blue': both_blue,
            'fast_above_slow': fast_above_slow,
            'entry_valid': entry_valid,
            'pct_above_fast': round(pct_above_fast, 2),
            'pct_above_slow': round(pct_above_slow, 2)
        }

    except Exception as e:
        logger.error(f"Error calculating MA2: {e}")
        return {
            'valid': False,
            'error': str(e)
        }


def fetch_vsr_tickers() -> List[Dict]:
    """Fetch tickers from VSR dashboard API"""
    try:
        response = requests.get(VSR_API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Get all tickers with positive momentum
        all_tickers = data.get('categories', {}).get('all_tickers', [])

        # Filter for positive momentum (same as VSR dashboard)
        positive_momentum = [t for t in all_tickers if t.get('momentum', 0) > 0]

        logger.info(f"Fetched {len(positive_momentum)} tickers with positive momentum from VSR API")
        return positive_momentum

    except Exception as e:
        logger.error(f"Error fetching VSR tickers: {e}")
        return []


def process_ticker(ticker_data: Dict) -> Optional[Dict]:
    """
    Process a single ticker - fetch data and calculate MA2 Blue status

    Args:
        ticker_data: Dict with ticker info from VSR API

    Returns:
        Enhanced ticker data with MA2 info, or None if failed
    """
    ticker = ticker_data.get('ticker')
    if not ticker:
        return None

    # Add small delay to avoid rate limiting (Zerodha allows ~3 requests/second)
    time.sleep(0.4)

    # Fetch historical data
    df = fetch_historical_data(ticker)
    if df is None:
        return None

    # Calculate MA2 Blue status
    ma2_status = calculate_td_ma2_blue(df)

    if not ma2_status.get('valid'):
        return None

    # Merge ticker data with MA2 status
    result = {**ticker_data, **ma2_status}
    return result


# Cache for filtered results
_filter_cache = {
    'data': None,
    'timestamp': 0
}

def get_filtered_tickers() -> Dict:
    """
    Get VSR tickers filtered by TD MA II Blue conditions
    Uses caching to avoid excessive API calls
    """
    global _filter_cache

    current_time = time.time()

    # Return cached data if fresh
    if _filter_cache['data'] and (current_time - _filter_cache['timestamp']) < FILTER_CACHE_TTL:
        return _filter_cache['data']

    # Fetch VSR tickers
    vsr_tickers = fetch_vsr_tickers()

    if not vsr_tickers:
        return {
            'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST'),
            'error': 'No VSR tickers available',
            'total_vsr': 0,
            'passed_filter': 0,
            'tickers': []
        }

    # Process tickers sequentially to avoid rate limiting (Zerodha ~3 req/sec)
    # Use ThreadPoolExecutor with limited workers
    filtered_tickers = []
    both_blue_only = []
    entry_valid = []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(process_ticker, t): t for t in vsr_tickers[:30]}  # Limit to top 30

        for future in as_completed(futures):
            result = future.result()
            if result:
                filtered_tickers.append(result)

                if result.get('both_blue'):
                    both_blue_only.append(result)

                if result.get('entry_valid'):
                    entry_valid.append(result)

    # Sort by score, then momentum
    filtered_tickers.sort(key=lambda x: (x.get('score', 0), x.get('momentum', 0)), reverse=True)
    both_blue_only.sort(key=lambda x: (x.get('score', 0), x.get('momentum', 0)), reverse=True)
    entry_valid.sort(key=lambda x: (x.get('score', 0), x.get('momentum', 0)), reverse=True)

    result = {
        'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST'),
        'total_vsr': len(vsr_tickers),
        'processed': len(filtered_tickers),
        'both_blue_count': len(both_blue_only),
        'entry_valid_count': len(entry_valid),
        'categories': {
            'entry_valid': entry_valid,  # Both Blue + Fast > Slow
            'both_blue': both_blue_only,  # Both Blue (may include Fast < Slow)
            'all_processed': filtered_tickers
        }
    }

    # Update cache
    _filter_cache['data'] = result
    _filter_cache['timestamp'] = current_time

    logger.info(f"Filter results: {len(entry_valid)} entry valid, {len(both_blue_only)} both blue, {len(filtered_tickers)} processed")

    return result


# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>TD MA II Filter Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #0f3460;
        }
        .header h1 { color: #4ecca3; font-size: 1.8em; }
        .header .meta { text-align: right; font-size: 0.9em; color: #888; }

        .stats-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: rgba(15, 52, 96, 0.5);
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            border: 1px solid #0f3460;
        }
        .stat-value { font-size: 2em; font-weight: bold; color: #4ecca3; }
        .stat-label { font-size: 0.8em; color: #888; text-transform: uppercase; }

        .filter-info {
            background: rgba(78, 204, 163, 0.1);
            border: 1px solid #4ecca3;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }
        .filter-info h3 { color: #4ecca3; margin-bottom: 10px; }
        .filter-info code { background: #1a1a2e; padding: 2px 6px; border-radius: 4px; }

        .categories { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
        .category-card {
            background: rgba(15, 52, 96, 0.5);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #0f3460;
        }
        .category-title {
            font-size: 1.3em;
            color: #4ecca3;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .category-title .count {
            background: #4ecca3;
            color: #000;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.7em;
        }

        .ticker-list { display: flex; flex-direction: column; gap: 10px; }
        .ticker-item {
            background: #2a2a2a;
            padding: 12px;
            border-radius: 8px;
            display: grid;
            grid-template-columns: 100px 1fr;
            gap: 15px;
        }
        .ticker-item:hover { background: #333; }
        .ticker-symbol { font-size: 1.1em; font-weight: bold; color: #3b82f6; }
        .ticker-details {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(70px, 1fr));
            gap: 8px;
        }
        .detail-item { display: flex; flex-direction: column; }
        .detail-label { font-size: 0.7em; color: #666; text-transform: uppercase; }
        .detail-value { font-size: 0.9em; font-weight: 500; }

        .blue { color: #3b82f6; }
        .red { color: #ef4444; }
        .green { color: #10b981; }
        .yellow { color: #f59e0b; }

        .ma-status {
            display: flex;
            gap: 8px;
            margin-top: 5px;
        }
        .ma-badge {
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
        }
        .ma-badge.blue-bg { background: rgba(59, 130, 246, 0.2); color: #3b82f6; border: 1px solid #3b82f6; }
        .ma-badge.red-bg { background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid #ef4444; }
        .ma-badge.green-bg { background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; }

        .refresh-btn {
            background: #4ecca3;
            color: #000;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
        }
        .refresh-btn:hover { background: #3db892; }

        .empty-state { text-align: center; color: #666; padding: 30px; }
        .loading { text-align: center; padding: 40px; color: #888; }
        .error { background: #dc2626; color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>TD MA II Filter Dashboard</h1>
            <div class="meta">Port: 3005 | Filters VSR alerts with TD MA II Blue conditions</div>
        </div>
        <div>
            <div id="lastUpdated" style="margin-bottom: 5px;"></div>
            <button class="refresh-btn" onclick="refreshData()">Refresh</button>
        </div>
    </div>

    <div class="filter-info">
        <h3>Filter Logic (Tom DeMark MA II)</h3>
        <p style="margin-bottom: 8px;">
            <strong>MA2 Fast (3-SMA):</strong> <span class="blue">Blue</span> when <code>smaFast - smaFast[2] >= 0</code> (rising/flat over 2 bars)
        </p>
        <p style="margin-bottom: 8px;">
            <strong>MA2 Slow (34-SMA):</strong> <span class="blue">Blue</span> when <code>smaSlow - smaSlow[1] >= 0</code> (rising/flat over 1 bar)
        </p>
        <p>
            <strong>Entry Valid:</strong> <span class="green">Both Blue</span> AND <code>Fast > Slow</code>
        </p>
    </div>

    <div id="stats" class="stats-row"></div>
    <div id="loading" class="loading">Loading TD MA II data...</div>
    <div id="error" class="error" style="display: none;"></div>
    <div id="categories" class="categories" style="display: none;"></div>

    <script>
        let currentData = null;

        function createTickerElement(ticker) {
            const fastColor = ticker.fast_blue ? 'blue' : 'red';
            const slowColor = ticker.slow_blue ? 'blue' : 'red';
            const entryColor = ticker.entry_valid ? 'green' : 'yellow';

            return `
                <div class="ticker-item">
                    <div>
                        <div class="ticker-symbol">${ticker.ticker}</div>
                        <div class="ma-status">
                            <span class="ma-badge ${ticker.fast_blue ? 'blue-bg' : 'red-bg'}">Fast ${ticker.fast_blue ? 'Blue' : 'Red'}</span>
                            <span class="ma-badge ${ticker.slow_blue ? 'blue-bg' : 'red-bg'}">Slow ${ticker.slow_blue ? 'Blue' : 'Red'}</span>
                        </div>
                        ${ticker.entry_valid ? '<span class="ma-badge green-bg" style="margin-top:4px;">ENTRY VALID</span>' : ''}
                    </div>
                    <div class="ticker-details">
                        <div class="detail-item">
                            <span class="detail-label">Score</span>
                            <span class="detail-value ${ticker.score >= 50 ? 'green' : ''}">${ticker.score}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">VSR</span>
                            <span class="detail-value">${ticker.vsr?.toFixed(2) || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Momentum</span>
                            <span class="detail-value ${ticker.momentum > 0 ? 'green' : 'red'}">${ticker.momentum?.toFixed(1)}%</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Close</span>
                            <span class="detail-value">₹${ticker.close?.toFixed(2) || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Fast MA</span>
                            <span class="detail-value ${fastColor}">₹${ticker.ma2_fast?.toFixed(2) || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Slow MA</span>
                            <span class="detail-value ${slowColor}">₹${ticker.ma2_slow?.toFixed(2) || 'N/A'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">vs Slow</span>
                            <span class="detail-value ${ticker.pct_above_slow > 0 ? 'green' : 'red'}">${ticker.pct_above_slow?.toFixed(1)}%</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Liq</span>
                            <span class="detail-value">${ticker.liquidity_grade || 'F'}</span>
                        </div>
                    </div>
                </div>
            `;
        }

        function updateUI(data) {
            // Update stats
            document.getElementById('stats').innerHTML = `
                <div class="stat-card">
                    <div class="stat-value">${data.total_vsr || 0}</div>
                    <div class="stat-label">VSR Tickers</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${data.processed || 0}</div>
                    <div class="stat-label">Processed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: #10b981;">${data.entry_valid_count || 0}</div>
                    <div class="stat-label">Entry Valid</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: #3b82f6;">${data.both_blue_count || 0}</div>
                    <div class="stat-label">Both Blue</div>
                </div>
            `;

            // Update categories
            const categories = data.categories || {};

            let html = '';

            // Entry Valid category (primary)
            html += `
                <div class="category-card" style="border: 2px solid #10b981;">
                    <h2 class="category-title">
                        Entry Valid (Both Blue + Fast > Slow)
                        <span class="count">${categories.entry_valid?.length || 0}</span>
                    </h2>
                    <div class="ticker-list">
                        ${categories.entry_valid?.length > 0
                            ? categories.entry_valid.map(t => createTickerElement(t)).join('')
                            : '<div class="empty-state">No tickers pass all entry criteria</div>'}
                    </div>
                </div>
            `;

            // Both Blue category
            html += `
                <div class="category-card" style="border: 2px solid #3b82f6;">
                    <h2 class="category-title">
                        Both Blue (Fast & Slow Rising)
                        <span class="count">${categories.both_blue?.length || 0}</span>
                    </h2>
                    <div class="ticker-list">
                        ${categories.both_blue?.length > 0
                            ? categories.both_blue.map(t => createTickerElement(t)).join('')
                            : '<div class="empty-state">No tickers with both MAs blue</div>'}
                    </div>
                </div>
            `;

            document.getElementById('categories').innerHTML = html;
            document.getElementById('lastUpdated').textContent = `Last updated: ${data.timestamp}`;
        }

        async function fetchData() {
            try {
                document.getElementById('loading').style.display = 'block';
                document.getElementById('error').style.display = 'none';
                document.getElementById('categories').style.display = 'none';

                const response = await fetch('/api/filtered-tickers');
                if (!response.ok) throw new Error(`HTTP ${response.status}`);

                const data = await response.json();
                currentData = data;

                updateUI(data);

                document.getElementById('loading').style.display = 'none';
                document.getElementById('categories').style.display = 'grid';

            } catch (error) {
                console.error('Error:', error);
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = `Error: ${error.message}`;
            }
        }

        function refreshData() { fetchData(); }

        document.addEventListener('DOMContentLoaded', function() {
            fetchData();
            setInterval(fetchData, 60000);  // Refresh every 60 seconds
        });
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    """Serve the dashboard HTML"""
    return Response(HTML_TEMPLATE, mimetype='text/html')


@app.route('/api/filtered-tickers')
def api_filtered_tickers():
    """API endpoint for filtered tickers"""
    try:
        result = get_filtered_tickers()
        return jsonify(result)
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'port': PORT,
        'kite_available': KITE_AVAILABLE,
        'instruments_loaded': len(instrument_cache)
    })


if __name__ == '__main__':
    logger.info(f"Starting TD MA II Filter Dashboard on port {PORT}")

    # Initialize Kite
    if init_kite():
        logger.info("Kite connection established")
    else:
        logger.warning("Running without Kite - will not be able to fetch price data")

    logger.info(f"Access the dashboard at: http://localhost:{PORT}")

    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
