#!/usr/bin/env python3
"""
Real-time Dashboard for VSR Paper Trading System
Shows active positions, pending slices, and performance metrics
"""

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS
import pandas as pd

app = Flask(__name__)
CORS(app)

DB_PATH = "data/paper_trades.db"

# HTML Template
DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>VSR Paper Trading Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #1a1a1a;
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: #2a2a2a;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #4a90e2;
        }
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            margin: 5px 0;
        }
        .positive { color: #4caf50; }
        .negative { color: #f44336; }
        .neutral { color: #ffc107; }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #333;
        }
        th {
            background: #2a2a2a;
            color: #4a90e2;
            font-weight: bold;
        }
        tr:hover {
            background: #2a2a2a;
        }
        .section-title {
            font-size: 1.5em;
            margin: 20px 0 10px;
            color: #4a90e2;
        }
        .slice-progress {
            width: 100%;
            height: 20px;
            background: #333;
            border-radius: 10px;
            overflow: hidden;
        }
        .slice-fill {
            height: 100%;
            background: #4a90e2;
            transition: width 0.3s ease;
        }
        .refresh-info {
            text-align: center;
            margin-top: 20px;
            color: #888;
        }
        .signal-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            margin: 2px;
        }
        .vsr-high { background: #f44336; }
        .vsr-medium { background: #ff9800; }
        .vsr-low { background: #4caf50; }
    </style>
    <script>
        async function refreshData() {
            try {
                const response = await fetch('/api/dashboard');
                const data = await response.json();
                updateDashboard(data);
            } catch (error) {
                console.error('Error fetching data:', error);
            }
        }
        
        function updateDashboard(data) {
            // Update metrics
            document.getElementById('total-positions').textContent = data.metrics.total_positions;
            document.getElementById('total-pnl').textContent = '₹' + data.metrics.total_pnl.toLocaleString('en-IN', {maximumFractionDigits: 0});
            document.getElementById('win-rate').textContent = data.metrics.win_rate.toFixed(1) + '%';
            document.getElementById('pending-slices').textContent = data.metrics.pending_slices;
            
            // Update positions table
            const positionsBody = document.getElementById('positions-body');
            positionsBody.innerHTML = data.positions.map(pos => `
                <tr>
                    <td><strong>${pos.ticker}</strong></td>
                    <td>${pos.quantity}</td>
                    <td>₹${pos.avg_price.toFixed(2)}</td>
                    <td>₹${pos.current_price.toFixed(2)}</td>
                    <td class="${pos.pnl >= 0 ? 'positive' : 'negative'}">
                        ₹${pos.pnl.toFixed(0)} (${pos.pnl_pct.toFixed(2)}%)
                    </td>
                    <td><span class="signal-badge ${pos.vsr >= 10 ? 'vsr-high' : pos.vsr >= 5 ? 'vsr-medium' : 'vsr-low'}">VSR: ${pos.vsr.toFixed(1)}</span></td>
                    <td>${pos.momentum_score}</td>
                    <td>${new Date(pos.entry_time).toLocaleTimeString()}</td>
                </tr>
            `).join('');
            
            // Update pending slices
            const slicesBody = document.getElementById('slices-body');
            slicesBody.innerHTML = data.pending_slices.map(slice => `
                <tr>
                    <td><strong>${slice.ticker}</strong></td>
                    <td>${slice.completed}/${slice.total}</td>
                    <td>
                        <div class="slice-progress">
                            <div class="slice-fill" style="width: ${slice.progress}%"></div>
                        </div>
                    </td>
                    <td>${slice.next_slice_time || 'Completed'}</td>
                    <td>₹${slice.remaining_value.toFixed(0)}</td>
                </tr>
            `).join('');
            
            // Update recent trades
            const tradesBody = document.getElementById('trades-body');
            tradesBody.innerHTML = data.recent_trades.map(trade => `
                <tr>
                    <td>${new Date(trade.timestamp).toLocaleTimeString()}</td>
                    <td><strong>${trade.ticker}</strong></td>
                    <td>${trade.action}</td>
                    <td>${trade.quantity}</td>
                    <td>₹${trade.price.toFixed(2)}</td>
                    <td>Slice ${trade.slice_number}/${trade.total_slices}</td>
                    <td><span class="signal-badge ${trade.vsr >= 10 ? 'vsr-high' : trade.vsr >= 5 ? 'vsr-medium' : 'vsr-low'}">VSR: ${trade.vsr.toFixed(1)}</span></td>
                </tr>
            `).join('');
            
            // Update last refresh time
            document.getElementById('last-update').textContent = new Date().toLocaleString();
        }
        
        // Refresh every 5 seconds
        setInterval(refreshData, 5000);
        
        // Initial load
        refreshData();
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>VSR Paper Trading Dashboard</h1>
            <p>Real-time monitoring of VSR-based entry signals and order slicing</p>
        </div>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Active Positions</div>
                <div class="metric-value" id="total-positions">0</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total P&L</div>
                <div class="metric-value" id="total-pnl">₹0</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Win Rate</div>
                <div class="metric-value" id="win-rate">0%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Pending Slices</div>
                <div class="metric-value" id="pending-slices">0</div>
            </div>
        </div>
        
        <h2 class="section-title">Active Positions</h2>
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Quantity</th>
                    <th>Avg Price</th>
                    <th>Current Price</th>
                    <th>P&L</th>
                    <th>VSR</th>
                    <th>Score</th>
                    <th>Entry Time</th>
                </tr>
            </thead>
            <tbody id="positions-body">
                <tr><td colspan="8" style="text-align: center;">Loading...</td></tr>
            </tbody>
        </table>
        
        <h2 class="section-title">Pending Order Slices</h2>
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Slices Completed</th>
                    <th>Progress</th>
                    <th>Next Slice Time</th>
                    <th>Remaining Value</th>
                </tr>
            </thead>
            <tbody id="slices-body">
                <tr><td colspan="5" style="text-align: center;">No pending slices</td></tr>
            </tbody>
        </table>
        
        <h2 class="section-title">Recent Trades</h2>
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Ticker</th>
                    <th>Action</th>
                    <th>Quantity</th>
                    <th>Price</th>
                    <th>Slice</th>
                    <th>VSR</th>
                </tr>
            </thead>
            <tbody id="trades-body">
                <tr><td colspan="7" style="text-align: center;">No trades yet</td></tr>
            </tbody>
        </table>
        
        <div class="refresh-info">
            Last updated: <span id="last-update">Never</span> | Auto-refresh every 5 seconds
        </div>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(DASHBOARD_TEMPLATE)

@app.route('/api/dashboard')
def get_dashboard_data():
    """Get all dashboard data"""
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Get positions
        positions_query = '''
            SELECT * FROM positions 
            WHERE status = 'OPEN' 
            ORDER BY entry_time DESC
        '''
        positions_df = pd.read_sql_query(positions_query, conn)
        
        # Calculate P&L percentages
        positions_data = []
        for _, pos in positions_df.iterrows():
            pnl_pct = ((pos['current_price'] - pos['avg_price']) / pos['avg_price']) * 100
            positions_data.append({
                'ticker': pos['ticker'],
                'quantity': pos['quantity'],
                'avg_price': pos['avg_price'],
                'current_price': pos['current_price'] or pos['avg_price'],
                'pnl': pos['pnl'] or 0,
                'pnl_pct': pnl_pct,
                'vsr': pos['vsr'] or 0,
                'momentum_score': pos['momentum_score'] or 0,
                'entry_time': pos['entry_time']
            })
        
        # Get recent trades
        trades_query = '''
            SELECT * FROM trades 
            WHERE date(timestamp) = date('now') 
            ORDER BY timestamp DESC 
            LIMIT 20
        '''
        trades_df = pd.read_sql_query(trades_query, conn)
        
        # Calculate metrics
        total_pnl = positions_df['pnl'].sum() if not positions_df.empty else 0
        win_rate = (positions_df['pnl'] > 0).sum() / len(positions_df) * 100 if not positions_df.empty else 0
        
        # Get pending slices (simplified for now)
        pending_slices_data = []
        
        conn.close()
        
        return jsonify({
            'metrics': {
                'total_positions': len(positions_df),
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'pending_slices': len(pending_slices_data)
            },
            'positions': positions_data,
            'pending_slices': pending_slices_data,
            'recent_trades': trades_df.to_dict('records') if not trades_df.empty else []
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    app.run(host='0.0.0.0', port=5005, debug=False)