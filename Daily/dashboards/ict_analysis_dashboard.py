#!/usr/bin/env python3
"""
ICT Analysis Dashboard - Real-time display of ICT-based stop loss analysis
Displays analysis logs and recommendations for both CNC and MIS positions
"""

import os
import sys
import json
import glob
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify
import pandas as pd
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICT_ANALYSIS_DIR = os.path.join(BASE_DIR, 'portfolio', 'ict_analysis')
LOG_DIR = os.path.join(BASE_DIR, 'logs', 'ict_analysis')

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>ICT Stop Loss Analysis Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1600px;
            margin: 0 auto;
        }
        .header {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(45deg, #fff, #e0e0e0);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .stat-card {
            background: rgba(255, 255, 255, 0.15);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            margin: 5px 0;
        }
        .stat-label {
            font-size: 0.9em;
            opacity: 0.9;
        }
        .positions-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .position-card {
            background: rgba(255, 255, 255, 0.95);
            color: #333;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            transition: transform 0.3s;
        }
        .position-card:hover {
            transform: translateY(-5px);
        }
        .ticker-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }
        .ticker-symbol {
            font-size: 1.4em;
            font-weight: bold;
            color: #2a5298;
        }
        .product-type {
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: bold;
        }
        .product-cnc {
            background: #4CAF50;
            color: white;
        }
        .product-mis {
            background: #FF9800;
            color: white;
        }
        .product-holding {
            background: #9C27B0;
            color: white;
        }
        .price-info {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin: 15px 0;
        }
        .price-item {
            padding: 8px;
            background: #f5f5f5;
            border-radius: 8px;
        }
        .price-label {
            font-size: 0.8em;
            color: #666;
            margin-bottom: 3px;
        }
        .price-value {
            font-size: 1.1em;
            font-weight: bold;
            color: #333;
        }
        .sl-recommendation {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin: 15px 0;
        }
        .sl-value {
            font-size: 1.8em;
            font-weight: bold;
            margin: 5px 0;
        }
        .sl-reasoning {
            font-size: 0.9em;
            opacity: 0.95;
            margin-top: 8px;
        }
        .market-structure {
            padding: 10px;
            background: #f0f0f0;
            border-radius: 8px;
            margin: 10px 0;
        }
        .structure-label {
            font-size: 0.85em;
            color: #666;
            margin-bottom: 5px;
        }
        .structure-value {
            font-size: 1.1em;
            font-weight: bold;
            color: #333;
        }
        .probabilities {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin: 15px 0;
        }
        .prob-item {
            text-align: center;
            padding: 10px;
            background: #f8f8f8;
            border-radius: 8px;
        }
        .prob-label {
            font-size: 0.75em;
            color: #666;
            margin-bottom: 3px;
        }
        .prob-value {
            font-size: 1.2em;
            font-weight: bold;
        }
        .high-prob { color: #d32f2f; }
        .medium-prob { color: #ff9800; }
        .low-prob { color: #4caf50; }
        .recommendation-box {
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 12px;
            border-radius: 6px;
            margin-top: 15px;
        }
        .recommendation-text {
            color: #1565c0;
            font-size: 0.95em;
        }
        .timeframe-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }
        .tab {
            padding: 8px 15px;
            background: #e0e0e0;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9em;
            transition: all 0.3s;
        }
        .tab.active {
            background: #2196f3;
            color: white;
        }
        .no-data {
            text-align: center;
            padding: 50px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            color: #fff;
            font-size: 1.2em;
        }
        .refresh-info {
            text-align: center;
            margin-top: 20px;
            opacity: 0.8;
            font-size: 0.9em;
        }
        .log-section {
            background: rgba(255, 255, 255, 0.95);
            color: #333;
            border-radius: 12px;
            padding: 20px;
            margin-top: 30px;
        }
        .log-header {
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 15px;
            color: #2a5298;
        }
        .log-content {
            background: #f5f5f5;
            padding: 15px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            max-height: 400px;
            overflow-y: auto;
        }
        .log-entry {
            margin-bottom: 8px;
            padding: 5px;
            border-left: 3px solid transparent;
        }
        .log-info { border-left-color: #2196f3; }
        .log-warning { border-left-color: #ff9800; }
        .log-error { border-left-color: #f44336; }
        .pnl-positive { color: #4caf50; }
        .pnl-negative { color: #f44336; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 ICT Stop Loss Analysis Dashboard</h1>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Total Positions</div>
                    <div class="stat-value" id="total-positions">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">CNC Positions</div>
                    <div class="stat-value" id="cnc-positions">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">MIS Positions</div>
                    <div class="stat-value" id="mis-positions">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Holdings</div>
                    <div class="stat-value" id="holding-positions">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Last Analysis</div>
                    <div class="stat-value" id="last-analysis">--:--</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Risk</div>
                    <div class="stat-value" id="total-risk" style="color: #ff5252;">₹0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Reward</div>
                    <div class="stat-value" id="total-reward" style="color: #4caf50;">₹0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Available Funds</div>
                    <div class="stat-value" id="available-funds" style="color: #2196f3;">₹0</div>
                </div>
            </div>
        </div>

        <div id="positions-container" class="positions-grid">
            <!-- Position cards will be dynamically inserted here -->
        </div>

        <div class="log-section">
            <div class="log-header">📊 Recent Analysis Logs</div>
            <div class="log-content" id="log-content">
                <!-- Log entries will be dynamically inserted here -->
            </div>
        </div>

        <div class="refresh-info">
            Auto-refreshes every 30 seconds | Next refresh in <span id="countdown">30</span>s
        </div>
    </div>

    <script>
        let countdown = 30;
        let countdownInterval;

        async function loadAnalysisData() {
            try {
                const response = await fetch('/api/analysis');
                const data = await response.json();
                updateDashboard(data);
            } catch (error) {
                console.error('Error loading data:', error);
            }
        }

        function updateDashboard(data) {
            // Update stats
            document.getElementById('total-positions').textContent = data.stats.total;
            document.getElementById('cnc-positions').textContent = data.stats.cnc;
            document.getElementById('mis-positions').textContent = data.stats.mis;
            document.getElementById('holding-positions').textContent = data.stats.holdings || 0;
            document.getElementById('last-analysis').textContent = data.stats.last_analysis;
            
            // Format and display risk, reward and funds
            const totalRisk = data.stats.total_risk || 0;
            const totalReward = data.stats.total_reward || 0;
            const availableFunds = data.stats.available_funds || 0;
            document.getElementById('total-risk').textContent = '₹' + totalRisk.toLocaleString('en-IN', {maximumFractionDigits: 0});
            document.getElementById('total-reward').textContent = '₹' + totalReward.toLocaleString('en-IN', {maximumFractionDigits: 0});
            document.getElementById('available-funds').textContent = '₹' + availableFunds.toLocaleString('en-IN', {maximumFractionDigits: 0});

            // Update positions
            const container = document.getElementById('positions-container');
            container.innerHTML = '';

            if (data.positions.length === 0) {
                container.innerHTML = '<div class="no-data">No positions analyzed yet. Waiting for ICT analysis...</div>';
                return;
            }

            // Group positions by ticker
            const groupedPositions = {};
            data.positions.forEach(pos => {
                if (!groupedPositions[pos.ticker]) {
                    groupedPositions[pos.ticker] = {};
                }
                groupedPositions[pos.ticker][pos.timeframe] = pos;
            });

            // Create position cards
            Object.keys(groupedPositions).forEach(ticker => {
                const positions = groupedPositions[ticker];
                const hourly = positions.hourly;
                const daily = positions.daily;
                const pos = hourly || daily;

                const card = document.createElement('div');
                card.className = 'position-card';
                
                const pnlClass = pos.current_price > pos.position_price ? 'pnl-positive' : 'pnl-negative';
                const pnlPercent = ((pos.current_price - pos.position_price) / pos.position_price * 100).toFixed(2);
                
                card.innerHTML = `
                    <div class="ticker-header">
                        <span class="ticker-symbol">${ticker}</span>
                        <span class="product-type ${pos.product_type === 'MIS' ? 'product-mis' : pos.product_type === 'HOLDING' ? 'product-holding' : 'product-cnc'}">${pos.product_type}</span>
                    </div>
                    
                    <div class="price-info">
                        <div class="price-item">
                            <div class="price-label">Entry Price</div>
                            <div class="price-value">₹${pos.position_price.toFixed(2)}</div>
                        </div>
                        <div class="price-item">
                            <div class="price-label">Current Price</div>
                            <div class="price-value ${pnlClass}">₹${pos.current_price.toFixed(2)} (${pnlPercent}%)</div>
                        </div>
                    </div>

                    <div class="timeframe-tabs">
                        ${hourly ? '<div class="tab active">Hourly</div>' : ''}
                        ${daily ? '<div class="tab">Daily</div>' : ''}
                    </div>

                    ${hourly ? `
                        <div class="sl-recommendation">
                            <div class="sl-label">Recommended Stop Loss (Hourly)</div>
                            <div class="sl-value">₹${hourly.optimal_sl.toFixed(2)}</div>
                            <div class="sl-reasoning">${hourly.sl_reasoning}</div>
                        </div>
                        
                        <div class="market-structure">
                            <div class="structure-label">Market Structure</div>
                            <div class="structure-value">${hourly.market_structure}</div>
                        </div>

                        <div class="probabilities">
                            <div class="prob-item">
                                <div class="prob-label">Trend</div>
                                <div class="prob-value ${hourly.trend_strength > 70 ? 'low-prob' : hourly.trend_strength > 40 ? 'medium-prob' : 'high-prob'}">${hourly.trend_strength.toFixed(1)}%</div>
                            </div>
                            <div class="prob-item">
                                <div class="prob-label">Pullback</div>
                                <div class="prob-value ${hourly.pullback_probability > 60 ? 'high-prob' : hourly.pullback_probability > 30 ? 'medium-prob' : 'low-prob'}">${hourly.pullback_probability.toFixed(1)}%</div>
                            </div>
                            <div class="prob-item">
                                <div class="prob-label">Correction</div>
                                <div class="prob-value ${hourly.correction_probability > 50 ? 'high-prob' : hourly.correction_probability > 25 ? 'medium-prob' : 'low-prob'}">${hourly.correction_probability.toFixed(1)}%</div>
                            </div>
                        </div>
                    ` : ''}

                    <div class="recommendation-box">
                        <div class="recommendation-text">${pos.recommendation}</div>
                    </div>
                `;

                container.appendChild(card);
            });

            // Update logs
            const logContainer = document.getElementById('log-content');
            logContainer.innerHTML = '';
            
            data.logs.forEach(log => {
                const entry = document.createElement('div');
                entry.className = `log-entry log-${log.level.toLowerCase()}`;
                entry.textContent = `[${log.time}] ${log.message}`;
                logContainer.appendChild(entry);
            });
        }

        function startCountdown() {
            countdownInterval = setInterval(() => {
                countdown--;
                document.getElementById('countdown').textContent = countdown;
                
                if (countdown <= 0) {
                    countdown = 30;
                    loadAnalysisData();
                }
            }, 1000);
        }

        // Initial load
        loadAnalysisData();
        startCountdown();

        // Refresh every 30 seconds
        setInterval(loadAnalysisData, 30000);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

def calculate_risk_and_funds():
    """Calculate total risk, reward and available funds using ICT concepts"""
    try:
        # Import here to avoid circular imports
        from kiteconnect import KiteConnect
        from scanners.VSR_Momentum_Scanner import load_daily_config
        
        config = load_daily_config('Sai')
        api_key = config.get('API_CREDENTIALS_Sai', 'api_key')
        access_token = config.get('API_CREDENTIALS_Sai', 'access_token')
        
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        
        # Get margins (available funds)
        margins = kite.margins()
        available_funds = margins['equity'].get('available', {}).get('cash', 0)
        
        # Get positions for risk calculation
        positions_data = kite.positions()
        total_risk = 0
        total_reward = 0
        
        # Load latest analysis for stop losses and market structure
        analysis_files = glob.glob(os.path.join(ICT_ANALYSIS_DIR, 'ict_sl_analysis_*.json'))
        analysis_data = {}
        
        if analysis_files:
            latest_file = max(analysis_files, key=os.path.getctime)
            with open(latest_file, 'r') as f:
                analysis = json.load(f)
                for item in analysis:
                    ticker = item['ticker']
                    if ticker not in analysis_data or item['timeframe'] == 'hourly':
                        analysis_data[ticker] = {
                            'optimal_sl': item['optimal_sl'],
                            'market_structure': item.get('market_structure', 'Unknown'),
                            'trend_strength': item.get('trend_strength', 0),
                            'current_price': item.get('current_price', 0)
                        }
        
        # Calculate risk and reward for each position
        for pos in positions_data.get('net', []):
            if pos['quantity'] > 0:  # Long positions
                ticker = pos['tradingsymbol']
                current_price = pos['last_price']
                quantity = pos['quantity']
                
                # Get analysis data
                ticker_analysis = analysis_data.get(ticker, {})
                sl_price = ticker_analysis.get('optimal_sl', current_price * 0.95)
                market_structure = ticker_analysis.get('market_structure', 'Unknown')
                trend_strength = ticker_analysis.get('trend_strength', 0)
                
                # Calculate risk (positive value for potential loss)
                risk = (current_price - sl_price) * quantity
                total_risk += max(0, risk)
                
                # Calculate reward based on ICT market structure concepts
                reward_multiplier = 1.5  # Default conservative target
                
                if 'Bullish' in market_structure:
                    if trend_strength > 50:
                        reward_multiplier = 3.0  # Strong trend - target 3R
                    elif trend_strength > 30:
                        reward_multiplier = 2.5  # Moderate trend - target 2.5R
                    else:
                        reward_multiplier = 2.0  # Weak trend - target 2R
                elif 'Ranging' in market_structure or 'Consolidation' in market_structure:
                    reward_multiplier = 1.5  # Range bound - target range high (1.5R)
                elif 'Bearish' in market_structure:
                    reward_multiplier = 1.0  # Bearish - minimal target
                else:
                    reward_multiplier = 2.0  # Default to 2R
                
                # Calculate reward (risk * multiplier)
                position_reward = risk * reward_multiplier
                total_reward += max(0, position_reward)
        
        return total_risk, total_reward, available_funds
        
    except Exception as e:
        print(f"Error calculating risk and funds: {e}")
        return 0, 0, 0

@app.route('/api/analysis')
def get_analysis():
    """Get latest ICT analysis data"""
    try:
        # Get latest analysis files
        analysis_files = glob.glob(os.path.join(ICT_ANALYSIS_DIR, 'ict_sl_analysis_*.json'))
        
        positions = []
        if analysis_files:
            # Get the most recent file
            latest_file = max(analysis_files, key=os.path.getctime)
            
            with open(latest_file, 'r') as f:
                positions = json.load(f)
        
        # Get latest log entries
        log_files = glob.glob(os.path.join(LOG_DIR, 'sl_watch_ict_*.log'))
        logs = []
        
        if log_files:
            latest_log = max(log_files, key=os.path.getctime)
            
            # Read last 50 lines of log
            with open(latest_log, 'r') as f:
                lines = f.readlines()[-50:]
                
            for line in lines:
                if line.strip():
                    # Parse log line
                    parts = line.split(' - ', 2)
                    if len(parts) >= 3:
                        time_str = parts[0].strip()
                        level = parts[1].strip()
                        message = parts[2].strip()
                        
                        logs.append({
                            'time': time_str.split(' ')[1] if ' ' in time_str else time_str,
                            'level': level,
                            'message': message
                        })
        
        # Calculate stats
        cnc_count = sum(1 for p in positions if p.get('product_type', 'CNC') == 'CNC')
        mis_count = sum(1 for p in positions if p.get('product_type', 'CNC') == 'MIS')
        holding_count = sum(1 for p in positions if p.get('product_type', 'CNC') == 'HOLDING')
        
        last_analysis = '--:--'
        if positions:
            last_time = positions[0].get('analysis_time', '')
            if last_time:
                last_analysis = datetime.strptime(last_time, '%Y-%m-%d %H:%M:%S').strftime('%H:%M')
        
        # Calculate total risk, reward and available funds
        total_risk, total_reward, available_funds = calculate_risk_and_funds()
        
        return jsonify({
            'positions': positions,
            'logs': logs,
            'stats': {
                'total': len(set(p['ticker'] for p in positions)),
                'cnc': cnc_count,
                'mis': mis_count,
                'holdings': holding_count,
                'last_analysis': last_analysis,
                'total_risk': total_risk,
                'total_reward': total_reward,
                'available_funds': available_funds
            }
        })
        
    except Exception as e:
        print(f"Error loading analysis data: {e}")
        return jsonify({
            'positions': [],
            'logs': [],
            'stats': {
                'total': 0,
                'cnc': 0,
                'mis': 0,
                'last_analysis': '--:--'
            }
        })

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🎯 ICT Stop Loss Analysis Dashboard")
    print("="*60)
    print(f"Starting dashboard on port 3008...")
    print(f"Access at: http://localhost:3008")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=3008, debug=False)