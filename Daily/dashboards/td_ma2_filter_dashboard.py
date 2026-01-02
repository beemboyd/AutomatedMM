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


def calculate_td_exhaustion(df: pd.DataFrame) -> Dict:
    """
    Calculate full Tom DeMark exhaustion stack:

    1. TD Setup 9 → maturity (not exhaustion)
    2. Countdown >= 11 → vulnerability
    3. Countdown 13 → exhaustion condition
    4. Stall + TD MA failure → exhaustion confirmation
    5. TDST break → trend invalidation

    Also calculates TD MA I and TD MA II status for confirmation.
    """
    result = {
        # TD Setup
        'setup_count': 0,
        'setup_complete': False,
        'bars_since_setup9': 0,

        # TD Countdown
        'countdown': 0,
        'countdown_complete': False,

        # TD MA I (5-SMA of lows, triggered when low > highest low of 12 bars)
        'td_ma1_active': False,
        'td_ma1_value': 0.0,

        # TDST Support
        'tdst_support': 0.0,
        'tdst_active': False,
        'tdst_broken': False,

        # Stall detection
        'stall_detected': False,
        'range_compression': False,

        # Exhaustion assessment
        'exhaustion_level': 'NONE',  # NONE, MATURING, VULNERABLE, EXHAUSTED, CONFIRMED
        'exhaustion_signals': []
    }

    if df is None or len(df) < 20:
        return result

    try:
        # ========== TD SETUP 9 (Bullish) ==========
        # Condition: Close > Close[4] for 9 consecutive bars
        df['setup_cond'] = df['close'] > df['close'].shift(4)

        setup_count = 0
        setup_complete = False
        setup_bar9_idx = None
        setup_lowest_low = 0.0

        for i in range(4, len(df)):
            if df['setup_cond'].iloc[i]:
                setup_count += 1
                if setup_count == 1:
                    setup_lowest_low = df['low'].iloc[i]
                elif setup_count <= 9:
                    setup_lowest_low = min(setup_lowest_low, df['low'].iloc[i])
                if setup_count == 9:
                    setup_complete = True
                    setup_bar9_idx = i
            else:
                setup_count = 0
                setup_lowest_low = 0.0

        result['setup_count'] = min(setup_count, 9)
        result['setup_complete'] = setup_complete

        # ========== TD COUNTDOWN 13 (Bullish) ==========
        # After Setup 9, count bars where Close >= High[2]
        # Bars don't need to be consecutive
        countdown = 0
        if setup_bar9_idx is not None:
            result['bars_since_setup9'] = len(df) - 1 - setup_bar9_idx

            for i in range(setup_bar9_idx + 1, len(df)):
                if i >= 2 and df['close'].iloc[i] >= df['high'].iloc[i-2]:
                    countdown += 1
                    if countdown >= 13:
                        break

        result['countdown'] = countdown
        result['countdown_complete'] = countdown >= 13

        # ========== TD MA I (Bullish) ==========
        # Trigger: Low > Lowest low of prior 12 bars
        # Value: 5-bar SMA of lows
        # Duration: 4 bars, extends if re-triggered
        df['lowest_low_12'] = df['low'].shift(1).rolling(window=12).min()
        df['td_ma1_trigger'] = df['low'] > df['lowest_low_12']
        df['td_ma1_sma'] = df['low'].rolling(window=5).mean()

        # Check if TD MA I is currently active (within 4 bars of last trigger)
        td_ma1_active = False
        td_ma1_value = 0.0
        bars_remaining = 0

        for i in range(max(12, len(df) - 10), len(df)):  # Check last 10 bars
            if df['td_ma1_trigger'].iloc[i]:
                bars_remaining = 4
                td_ma1_value = float(df['td_ma1_sma'].iloc[i])
            elif bars_remaining > 0:
                bars_remaining -= 1

        td_ma1_active = bars_remaining > 0
        result['td_ma1_active'] = td_ma1_active
        result['td_ma1_value'] = round(td_ma1_value, 2)

        # ========== TDST SUPPORT ==========
        # Lowest low of Setup bars 1-4
        if setup_bar9_idx is not None and setup_bar9_idx >= 8:
            setup_start = setup_bar9_idx - 8
            setup_bar4 = setup_bar9_idx - 5
            tdst_support = float(df['low'].iloc[setup_start:setup_bar4+1].min())
            result['tdst_support'] = round(tdst_support, 2)
            result['tdst_active'] = True

            # Check if TDST is broken (close below support)
            latest_close = float(df['close'].iloc[-1])
            if latest_close < tdst_support:
                result['tdst_broken'] = True
                result['tdst_active'] = False

        # ========== STALL DETECTION ==========
        # Look for range compression and loss of directional progress
        if len(df) >= 5:
            recent_ranges = df['high'].iloc[-5:] - df['low'].iloc[-5:]
            avg_recent_range = recent_ranges.mean()
            prior_ranges = df['high'].iloc[-10:-5] - df['low'].iloc[-10:-5] if len(df) >= 10 else recent_ranges
            avg_prior_range = prior_ranges.mean()

            # Range compression: recent ranges < 70% of prior ranges
            if avg_prior_range > 0 and avg_recent_range < avg_prior_range * 0.7:
                result['range_compression'] = True

            # Check for overlapping closes (stall)
            recent_closes = df['close'].iloc[-5:]
            close_range = recent_closes.max() - recent_closes.min()
            if avg_recent_range > 0 and close_range < avg_recent_range * 0.5:
                result['stall_detected'] = True

        # ========== EXHAUSTION ASSESSMENT ==========
        signals = []

        # Level 1: Maturing (Setup 9 complete)
        if setup_complete:
            signals.append("Setup 9 Complete")

        # Level 2: Vulnerable (Countdown 11-12)
        if countdown >= 11 and countdown < 13:
            signals.append(f"Countdown {countdown}/13")

        # Level 3: Exhausted (Countdown 13)
        if countdown >= 13:
            signals.append("Countdown 13 Complete")

        # Confirmation signals
        if not td_ma1_active and setup_complete:
            signals.append("TD MA I Failed")

        if result['stall_detected']:
            signals.append("Stall Detected")

        if result['range_compression']:
            signals.append("Range Compression")

        if result['tdst_broken']:
            signals.append("TDST Broken")

        result['exhaustion_signals'] = signals

        # Determine exhaustion level
        if result['tdst_broken']:
            result['exhaustion_level'] = 'CONFIRMED'
        elif countdown >= 13 and (not td_ma1_active or result['stall_detected']):
            result['exhaustion_level'] = 'EXHAUSTED'
        elif countdown >= 13:
            result['exhaustion_level'] = 'EXHAUSTED'
        elif countdown >= 11:
            result['exhaustion_level'] = 'VULNERABLE'
        elif setup_complete:
            result['exhaustion_level'] = 'MATURING'
        else:
            result['exhaustion_level'] = 'NONE'

        return result

    except Exception as e:
        logger.error(f"Error calculating exhaustion: {e}")
        return result


def calculate_td_ma2_blue(df: pd.DataFrame) -> Dict:
    """
    Calculate TD MA II Blue conditions + Exhaustion status

    From PineScript:
    - smaFast = ta.sma(close, 3)
    - smaSlow = ta.sma(close, 34)
    - rocFast = smaFast - smaFast[2]  (change over 2 bars)
    - rocSlow = smaSlow - smaSlow[1]  (change over 1 bar)
    - Fast Blue: rocFast >= 0
    - Slow Blue: rocSlow >= 0
    - Entry Valid: Fast Blue AND Slow Blue AND Fast > Slow

    Returns:
        Dict with MA2 state, values, and exhaustion status
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

        # Calculate exhaustion status
        exhaustion = calculate_td_exhaustion(df)

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
            'pct_above_slow': round(pct_above_slow, 2),
            # Exhaustion data
            'setup_count': exhaustion['setup_count'],
            'countdown': exhaustion['countdown'],
            'exhaustion_level': exhaustion['exhaustion_level'],
            'exhaustion_signals': exhaustion['exhaustion_signals'],
            'td_ma1_active': exhaustion['td_ma1_active'],
            'tdst_support': exhaustion['tdst_support'],
            'tdst_broken': exhaustion['tdst_broken'],
            'stall_detected': exhaustion['stall_detected']
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
        .ma-badge.yellow-bg { background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid #f59e0b; }
        .ma-badge.orange-bg { background: rgba(249, 115, 22, 0.2); color: #f97316; border: 1px solid #f97316; }
        .ma-badge.purple-bg { background: rgba(168, 85, 247, 0.2); color: #a855f7; border: 1px solid #a855f7; }

        .exhaustion-row {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            margin-top: 6px;
            padding-top: 6px;
            border-top: 1px solid #444;
        }
        .exhaustion-badge {
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.7em;
            font-weight: bold;
        }
        .exhaustion-none { background: rgba(107, 114, 128, 0.2); color: #6b7280; border: 1px solid #6b7280; }
        .exhaustion-maturing { background: rgba(59, 130, 246, 0.2); color: #3b82f6; border: 1px solid #3b82f6; }
        .exhaustion-vulnerable { background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid #f59e0b; }
        .exhaustion-exhausted { background: rgba(249, 115, 22, 0.2); color: #f97316; border: 1px solid #f97316; }
        .exhaustion-confirmed { background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid #ef4444; }

        .signal-tag {
            padding: 1px 4px;
            border-radius: 3px;
            font-size: 0.65em;
            background: rgba(255, 255, 255, 0.1);
            color: #999;
        }

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

        function getExhaustionClass(level) {
            const classes = {
                'NONE': 'exhaustion-none',
                'MATURING': 'exhaustion-maturing',
                'VULNERABLE': 'exhaustion-vulnerable',
                'EXHAUSTED': 'exhaustion-exhausted',
                'CONFIRMED': 'exhaustion-confirmed'
            };
            return classes[level] || 'exhaustion-none';
        }

        function getExhaustionIcon(level) {
            const icons = {
                'NONE': '',
                'MATURING': '📊',
                'VULNERABLE': '⚠️',
                'EXHAUSTED': '🔥',
                'CONFIRMED': '🛑'
            };
            return icons[level] || '';
        }

        function createTickerElement(ticker) {
            const fastColor = ticker.fast_blue ? 'blue' : 'red';
            const slowColor = ticker.slow_blue ? 'blue' : 'red';
            const entryColor = ticker.entry_valid ? 'green' : 'yellow';
            const exhaustionLevel = ticker.exhaustion_level || 'NONE';
            const exhaustionSignals = ticker.exhaustion_signals || [];

            return `
                <div class="ticker-item">
                    <div>
                        <div class="ticker-symbol">${ticker.ticker}</div>
                        <div class="ma-status">
                            <span class="ma-badge ${ticker.fast_blue ? 'blue-bg' : 'red-bg'}">Fast ${ticker.fast_blue ? 'Blue' : 'Red'}</span>
                            <span class="ma-badge ${ticker.slow_blue ? 'blue-bg' : 'red-bg'}">Slow ${ticker.slow_blue ? 'Blue' : 'Red'}</span>
                        </div>
                        ${ticker.entry_valid ? '<span class="ma-badge green-bg" style="margin-top:4px;">ENTRY VALID</span>' : ''}
                        ${exhaustionLevel !== 'NONE' ? `
                        <div class="exhaustion-row">
                            <span class="exhaustion-badge ${getExhaustionClass(exhaustionLevel)}">
                                ${getExhaustionIcon(exhaustionLevel)} ${exhaustionLevel}
                            </span>
                            ${ticker.countdown > 0 ? `<span class="signal-tag">CD: ${ticker.countdown}/13</span>` : ''}
                            ${ticker.setup_count > 0 ? `<span class="signal-tag">Setup: ${ticker.setup_count}/9</span>` : ''}
                        </div>
                        ` : ''}
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
                            <span class="detail-label">TD MA I</span>
                            <span class="detail-value ${ticker.td_ma1_active ? 'green' : 'red'}">${ticker.td_ma1_active ? 'Active' : 'Failed'}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">TDST</span>
                            <span class="detail-value ${ticker.tdst_broken ? 'red' : ''}">${ticker.tdst_support > 0 ? '₹' + ticker.tdst_support : 'N/A'}${ticker.tdst_broken ? ' ❌' : ''}</span>
                        </div>
                    </div>
                    ${exhaustionSignals.length > 0 ? `
                    <div style="grid-column: 1 / -1; margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px;">
                        ${exhaustionSignals.map(sig => `<span class="signal-tag">${sig}</span>`).join('')}
                    </div>
                    ` : ''}
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
            setInterval(fetchData, 300000);  // Refresh every 5 minutes
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
