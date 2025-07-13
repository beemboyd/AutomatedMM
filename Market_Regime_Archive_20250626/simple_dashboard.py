#!/usr/bin/env python3
"""
Simple standalone dashboard for testing
"""

from flask import Flask, render_template_string
import json
from datetime import datetime

app = Flask(__name__)

# Simple HTML template embedded in code
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Market Regime Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .regime-box { 
            background: #f0f0f0; 
            padding: 20px; 
            border-radius: 10px; 
            text-align: center;
            margin-bottom: 20px;
        }
        .regime { font-size: 48px; font-weight: bold; }
        .confidence { font-size: 24px; color: #666; }
        .metric { 
            display: inline-block; 
            margin: 10px; 
            padding: 15px; 
            background: white; 
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .metric-label { color: #666; font-size: 14px; }
        .metric-value { font-size: 24px; font-weight: bold; }
        .refresh-btn { 
            padding: 10px 20px; 
            background: #007bff; 
            color: white; 
            border: none; 
            border-radius: 5px; 
            cursor: pointer;
        }
    </style>
</head>
<body>
    <h1>Market Regime Dashboard (Simple Version)</h1>
    
    <div class="regime-box">
        <div class="regime" id="regime">Loading...</div>
        <div class="confidence" id="confidence">-</div>
    </div>
    
    <div style="text-align: center;">
        <div class="metric">
            <div class="metric-label">Market Score</div>
            <div class="metric-value" id="market-score">-</div>
        </div>
        <div class="metric">
            <div class="metric-label">Volatility</div>
            <div class="metric-value" id="volatility">-</div>
        </div>
        <div class="metric">
            <div class="metric-label">Position Size</div>
            <div class="metric-value" id="position-size">-</div>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 20px;">
        <button class="refresh-btn" onclick="refreshData()">Refresh</button>
    </div>
    
    <div style="margin-top: 20px; color: #666;">
        Last updated: <span id="last-update">-</span>
    </div>
    
    <script>
        function refreshData() {
            fetch('/api/data')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('regime').textContent = data.regime.toUpperCase().replace('_', ' ');
                    document.getElementById('confidence').textContent = 'Confidence: ' + (data.confidence * 100).toFixed(1) + '%';
                    document.getElementById('market-score').textContent = data.market_score.toFixed(2);
                    document.getElementById('volatility').textContent = data.volatility.toFixed(2);
                    document.getElementById('position-size').textContent = data.position_size + 'x';
                    document.getElementById('last-update').textContent = new Date().toLocaleString();
                    
                    // Color code regime
                    const regimeElement = document.getElementById('regime');
                    const colors = {
                        'strong_bull': '#006400',
                        'bull': '#32CD32',
                        'neutral': '#FFD700',
                        'bear': '#FF6347',
                        'strong_bear': '#8B0000',
                        'volatile': '#FF8C00',
                        'crisis': '#800080'
                    };
                    regimeElement.style.color = colors[data.regime] || '#000';
                });
        }
        
        // Auto refresh every 5 seconds
        setInterval(refreshData, 5000);
        refreshData();
    </script>
</body>
</html>
'''

# Sample data (in real app, this would come from regime analysis)
def get_sample_data():
    return {
        'regime': 'neutral',
        'confidence': 0.75,
        'market_score': 0.12,
        'volatility': 0.65,
        'position_size': 0.8,
        'timestamp': datetime.now().isoformat()
    }

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def api_data():
    return json.dumps(get_sample_data())

if __name__ == '__main__':
    print("\n" + "="*60)
    print("SIMPLE MARKET REGIME DASHBOARD")
    print("="*60)
    print("\nStarting dashboard at: http://localhost:8888")
    print("Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    app.run(host='localhost', port=8888, debug=True)