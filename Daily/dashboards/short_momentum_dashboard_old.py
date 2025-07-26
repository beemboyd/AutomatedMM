#!/usr/bin/env python
"""
Short Momentum Dashboard
Web dashboard for viewing short-side momentum opportunities
Runs on port 3003
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS
import logging

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'short_momentum')

# HTML Template
DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Short Momentum Dashboard - India TS</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0e27;
            color: #e0e0e0;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 20px rgba(220, 53, 69, 0.3);
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            color: white;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .subtitle {
            font-size: 1.2em;
            color: #ffcccc;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: #1a1f3a;
            padding: 25px;
            border-radius: 10px;
            border: 1px solid #2a3050;
            text-align: center;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(220, 53, 69, 0.2);
        }
        
        .stat-value {
            font-size: 2.5em;
            font-weight: bold;
            color: #dc3545;
            margin-bottom: 5px;
        }
        
        .stat-label {
            color: #8892b0;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .table-container {
            background: #1a1f3a;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
            overflow-x: auto;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        
        .section-title {
            font-size: 1.8em;
            margin-bottom: 20px;
            color: #dc3545;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th {
            background: #252b48;
            color: #dc3545;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.85em;
            letter-spacing: 1px;
            border-bottom: 2px solid #dc3545;
        }
        
        td {
            padding: 12px 15px;
            border-bottom: 1px solid #2a3050;
        }
        
        tr:hover {
            background: #252b48;
        }
        
        .ticker-symbol {
            font-weight: bold;
            color: #fff;
            font-size: 1.1em;
        }
        
        .negative {
            color: #28a745;
            font-weight: bold;
        }
        
        .positive {
            color: #dc3545;
        }
        
        .score-high {
            background: #dc3545;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: bold;
            display: inline-block;
        }
        
        .score-medium {
            background: #ffc107;
            color: #1a1f3a;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: bold;
            display: inline-block;
        }
        
        .score-low {
            background: #6c757d;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            display: inline-block;
        }
        
        .momentum-bar {
            width: 100px;
            height: 8px;
            background: #2a3050;
            border-radius: 4px;
            overflow: hidden;
            display: inline-block;
            vertical-align: middle;
        }
        
        .momentum-fill {
            height: 100%;
            background: linear-gradient(90deg, #dc3545, #28a745);
            transition: width 0.3s;
        }
        
        .timestamp {
            color: #8892b0;
            font-size: 0.9em;
            text-align: center;
            margin-top: 20px;
        }
        
        .refresh-btn {
            background: #dc3545;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 1em;
            transition: background 0.3s;
            float: right;
        }
        
        .refresh-btn:hover {
            background: #c82333;
        }
        
        .persistence-badge {
            background: #17a2b8;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            margin-left: 5px;
        }
        
        .filters {
            background: #1a1f3a;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        
        .filter-group {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        .filter-label {
            color: #8892b0;
            font-size: 0.9em;
        }
        
        select, input {
            background: #252b48;
            color: #e0e0e0;
            border: 1px solid #2a3050;
            padding: 8px 12px;
            border-radius: 5px;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            .header h1 {
                font-size: 1.8em;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            table {
                font-size: 0.9em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
            <h1>📉 Short Momentum Dashboard</h1>
            <div class="subtitle">Tracking negative momentum opportunities from past 3 days</div>
        </div>
        
        <div class="stats-grid" id="stats-grid">
            <!-- Stats will be populated by JavaScript -->
        </div>
        
        <div class="filters">
            <div class="filter-group">
                <label class="filter-label">Min Score</label>
                <input type="number" id="minScore" value="50" onchange="filterTable()">
            </div>
            <div class="filter-group">
                <label class="filter-label">Sector</label>
                <select id="sectorFilter" onchange="filterTable()">
                    <option value="">All Sectors</option>
                </select>
            </div>
            <div class="filter-group">
                <label class="filter-label">Sort By</label>
                <select id="sortBy" onchange="sortTable()">
                    <option value="total_score">Total Score</option>
                    <option value="momentum_score">Momentum Score</option>
                    <option value="price_change_1d">1D Change</option>
                    <option value="price_change_3d">3D Change</option>
                    <option value="volume_ratio">Volume</option>
                </select>
            </div>
        </div>
        
        <div class="table-container">
            <h2 class="section-title">
                <span>🎯</span>
                <span>Top Short Opportunities</span>
            </h2>
            <table id="tickersTable">
                <thead>
                    <tr>
                        <th>Rank</th>
                        <th>Ticker</th>
                        <th>Sector</th>
                        <th>Total Score</th>
                        <th>Momentum</th>
                        <th>1D Change</th>
                        <th>3H Change</th>
                        <th>VSR</th>
                        <th>RSI</th>
                        <th>Volume</th>
                        <th>Persistence</th>
                    </tr>
                </thead>
                <tbody id="tickersBody">
                    <!-- Table rows will be populated by JavaScript -->
                </tbody>
            </table>
        </div>
        
        <div class="timestamp" id="timestamp">
            <!-- Timestamp will be populated by JavaScript -->
        </div>
    </div>
    
    <script>
        let allData = null;
        
        async function fetchData() {
            try {
                const response = await fetch('/api/short-momentum');
                const data = await response.json();
                console.log('Fetched data:', data);
                allData = data;
                updateDashboard(data);
            } catch (error) {
                console.error('Error fetching data:', error);
                document.getElementById('tickersBody').innerHTML = '<tr><td colspan="11" style="text-align: center; color: red;">Error loading data</td></tr>';
            }
        }
        
        function updateDashboard(data) {
            // Update stats
            updateStats(data);
            
            // Update table
            updateTable(data.tickers);
            
            // Update timestamp
            document.getElementById('timestamp').innerHTML = `Last updated: ${new Date(data.timestamp).toLocaleString()}`;
            
            // Populate sector filter
            populateSectorFilter(data.tickers);
        }
        
        function updateStats(data) {
            const statsHtml = `
                <div class="stat-card">
                    <div class="stat-value">${data.total_tickers}</div>
                    <div class="stat-label">Total Tickers</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${data.high_momentum_count || 0}</div>
                    <div class="stat-label">High Momentum</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${data.avg_momentum_score?.toFixed(1) || 0}</div>
                    <div class="stat-label">Avg Momentum Score</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${data.persistence_days}</div>
                    <div class="stat-label">Days Tracked</div>
                </div>
            `;
            document.getElementById('stats-grid').innerHTML = statsHtml;
        }
        
        function updateTable(tickers) {
            if (!tickers || Object.keys(tickers).length === 0) {
                document.getElementById('tickersBody').innerHTML = '<tr><td colspan="11" style="text-align: center;">No data available</td></tr>';
                return;
            }
            
            const tickerArray = Object.values(tickers).sort((a, b) => b.total_score - a.total_score);
            
            const tbody = document.getElementById('tickersBody');
            tbody.innerHTML = tickerArray.map((ticker, index) => {
                const scoreClass = ticker.total_score >= 80 ? 'score-high' : 
                                 ticker.total_score >= 50 ? 'score-medium' : 'score-low';
                
                return `
                    <tr data-ticker='${JSON.stringify(ticker)}'>
                        <td>${index + 1}</td>
                        <td class="ticker-symbol">${ticker.ticker}</td>
                        <td>${ticker.sector || 'Unknown'}</td>
                        <td><span class="${scoreClass}">${ticker.total_score.toFixed(0)}</span></td>
                        <td>
                            <div class="momentum-bar">
                                <div class="momentum-fill" style="width: ${Math.min(ticker.momentum_score, 100)}%"></div>
                            </div>
                            ${ticker.momentum_score.toFixed(0)}
                        </td>
                        <td class="${ticker.price_change_1d < 0 ? 'negative' : 'positive'}">
                            ${ticker.price_change_1d.toFixed(2)}%
                        </td>
                        <td class="${ticker.price_change_3h < 0 ? 'negative' : 'positive'}">
                            ${ticker.price_change_3h.toFixed(2)}%
                        </td>
                        <td class="${ticker.vsr < 0 ? 'negative' : ''}">
                            ${ticker.vsr.toFixed(2)}
                        </td>
                        <td>${ticker.rsi.toFixed(1)}</td>
                        <td>${ticker.volume_ratio.toFixed(2)}x</td>
                        <td>
                            <span class="persistence-badge">${ticker.appearances} days</span>
                        </td>
                    </tr>
                `;
            }).join('');
        }
        
        function populateSectorFilter(tickers) {
            const sectors = new Set();
            Object.values(tickers).forEach(ticker => {
                if (ticker.sector) sectors.add(ticker.sector);
            });
            
            const sectorFilter = document.getElementById('sectorFilter');
            sectorFilter.innerHTML = '<option value="">All Sectors</option>' +
                Array.from(sectors).sort().map(sector => 
                    `<option value="${sector}">${sector}</option>`
                ).join('');
        }
        
        function filterTable() {
            const minScore = parseFloat(document.getElementById('minScore').value) || 0;
            const sector = document.getElementById('sectorFilter').value;
            
            const rows = document.querySelectorAll('#tickersBody tr');
            rows.forEach(row => {
                const ticker = JSON.parse(row.dataset.ticker);
                const show = ticker.total_score >= minScore && 
                           (!sector || ticker.sector === sector);
                row.style.display = show ? '' : 'none';
            });
        }
        
        function sortTable() {
            const sortBy = document.getElementById('sortBy').value;
            const rows = Array.from(document.querySelectorAll('#tickersBody tr'));
            
            rows.sort((a, b) => {
                const tickerA = JSON.parse(a.dataset.ticker);
                const tickerB = JSON.parse(b.dataset.ticker);
                return tickerB[sortBy] - tickerA[sortBy];
            });
            
            const tbody = document.getElementById('tickersBody');
            tbody.innerHTML = '';
            rows.forEach((row, index) => {
                row.cells[0].textContent = index + 1;
                tbody.appendChild(row);
            });
        }
        
        // Auto-refresh every 60 seconds
        setInterval(fetchData, 60000);
        
        // Initial load
        fetchData();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """Render the dashboard"""
    return render_template_string(DASHBOARD_TEMPLATE)

@app.route('/api/short-momentum')
def get_short_momentum():
    """Get latest short momentum data"""
    try:
        # Load latest data
        latest_file = os.path.join(DATA_DIR, 'latest_short_momentum.json')
        
        if not os.path.exists(latest_file):
            return jsonify({
                'timestamp': datetime.now().isoformat(),
                'total_tickers': 0,
                'tickers': {},
                'persistence_days': 3
            })
        
        with open(latest_file, 'r') as f:
            data = json.load(f)
        
        # Calculate additional stats
        if 'results' in data and data['results']:
            tickers = {t['ticker']: t for t in data['results']}
            data['tickers'] = tickers
            high_momentum = [t for t in data['results'] if t['momentum_score'] >= 70]
            data['high_momentum_count'] = len(high_momentum)
            data['avg_momentum_score'] = sum(t['momentum_score'] for t in data['results']) / len(data['results'])
        else:
            data['tickers'] = {}
            data['high_momentum_count'] = 0
            data['avg_momentum_score'] = 0
        
        return jsonify(data)
        
    except Exception as e:
        logger.error(f"Error loading momentum data: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting Short Momentum Dashboard on port 3003...")
    app.run(host='0.0.0.0', port=3003, debug=False)