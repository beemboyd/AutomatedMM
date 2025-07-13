#!/usr/local/bin/python3
"""
Standalone dashboard without complex imports for debugging
"""

import os
import sys
from flask import Flask, render_template_string, jsonify
import json
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# HTML Template (simplified version)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Market Regime Dashboard (Debug)</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f8f9fa; }
        .container { max-width: 1200px; margin: 0 auto; }
        .regime-card { 
            background: white; 
            padding: 30px; 
            border-radius: 10px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            text-align: center;
        }
        .regime-badge {
            font-size: 48px;
            font-weight: bold;
            padding: 20px;
            border-radius: 10px;
            display: inline-block;
            margin-bottom: 10px;
        }
        .neutral { background: #FFD700; color: black; }
        .bull { background: #32CD32; color: white; }
        .bear { background: #FF6347; color: white; }
        .metric {
            display: inline-block;
            margin: 10px;
            padding: 20px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            min-width: 150px;
        }
        .metric-label { color: #666; font-size: 14px; margin-bottom: 5px; }
        .metric-value { font-size: 28px; font-weight: bold; }
        .status { 
            background: #e8f5e9; 
            color: #2e7d32;
            padding: 10px 20px; 
            border-radius: 5px; 
            display: inline-block;
            margin: 20px 0;
        }
        .error {
            background: #ffebee;
            color: #c62828;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Market Regime Dashboard</h1>
        
        <div class="status" id="status">
            Dashboard is running in standalone mode
        </div>
        
        <div class="regime-card">
            <div class="regime-badge neutral" id="regime">
                NEUTRAL
            </div>
            <h3>Confidence: <span id="confidence">75%</span></h3>
        </div>
        
        <div style="text-align: center;">
            <div class="metric">
                <div class="metric-label">Market Score</div>
                <div class="metric-value" id="market-score">0.15</div>
            </div>
            <div class="metric">
                <div class="metric-label">Volatility</div>
                <div class="metric-value" id="volatility">0.45</div>
            </div>
            <div class="metric">
                <div class="metric-label">Position Size</div>
                <div class="metric-value" id="position-size">0.8x</div>
            </div>
            <div class="metric">
                <div class="metric-label">Stop Loss</div>
                <div class="metric-value" id="stop-loss">1.0x</div>
            </div>
        </div>
        
        <div style="text-align: center; margin-top: 20px;">
            <button onclick="testAPI()" style="padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer;">
                Test API
            </button>
            <button onclick="loadFullAnalysis()" style="padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 5px; cursor: pointer; margin-left: 10px;">
                Load Full Analysis
            </button>
        </div>
        
        <div style="margin-top: 20px; text-align: center; color: #666;">
            Last updated: <span id="last-update">{{ timestamp }}</span>
        </div>
    </div>
    
    <script>
        function updateStatus(message, isError = false) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = isError ? 'status error' : 'status';
        }
        
        function testAPI() {
            fetch('/api/test')
                .then(response => response.json())
                .then(data => {
                    updateStatus('API is working! ' + JSON.stringify(data));
                })
                .catch(error => {
                    updateStatus('API Error: ' + error, true);
                });
        }
        
        function loadFullAnalysis() {
            updateStatus('Loading analysis...');
            fetch('/api/analysis')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        document.getElementById('regime').textContent = data.regime.toUpperCase().replace('_', ' ');
                        document.getElementById('confidence').textContent = (data.confidence * 100).toFixed(1) + '%';
                        document.getElementById('market-score').textContent = data.market_score.toFixed(2);
                        document.getElementById('volatility').textContent = data.volatility_score.toFixed(2);
                        document.getElementById('position-size').textContent = data.position_size + 'x';
                        document.getElementById('stop-loss').textContent = data.stop_loss + 'x';
                        document.getElementById('last-update').textContent = new Date().toLocaleString();
                        updateStatus('Analysis loaded successfully!');
                        
                        // Update regime color
                        const regimeEl = document.getElementById('regime');
                        regimeEl.className = 'regime-badge ' + data.regime;
                    } else {
                        updateStatus('Error: ' + data.message, true);
                    }
                })
                .catch(error => {
                    updateStatus('Failed to load analysis: ' + error, true);
                });
        }
        
        // Auto-load on start
        setTimeout(loadFullAnalysis, 1000);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@app.route('/api/test')
def api_test():
    return jsonify({
        'status': 'success',
        'message': 'API is working',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/analysis')
def api_analysis():
    try:
        # Try to import and run analysis
        logger.info("Attempting to import daily_integration...")
        
        # Add parent paths
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        grandparent_dir = os.path.dirname(parent_dir)
        if grandparent_dir not in sys.path:
            sys.path.insert(0, grandparent_dir)
        
        logger.info(f"Python path: {sys.path[:3]}")
        
        # Try importing step by step
        try:
            from Market_Regime.integration.daily_integration import DailyTradingIntegration
            logger.info("Successfully imported DailyTradingIntegration")
            
            # Create integration instance
            integration = DailyTradingIntegration()
            logger.info("Created integration instance")
            
            # Try to get analysis
            analysis = integration.analyze_current_market_regime()
            logger.info("Got analysis")
            
            if 'error' not in analysis:
                return jsonify({
                    'status': 'success',
                    'regime': analysis['regime_analysis']['enhanced_regime'],
                    'confidence': analysis['regime_analysis']['enhanced_confidence'],
                    'market_score': analysis['regime_analysis']['indicators'].get('market_score', 0),
                    'volatility_score': analysis['regime_analysis']['indicators'].get('volatility_score', 0.5),
                    'position_size': analysis['recommendations']['position_sizing']['size_multiplier'],
                    'stop_loss': analysis['recommendations']['risk_management']['stop_loss_multiplier']
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f"Analysis error: {analysis['error']}"
                })
                
        except ImportError as e:
            logger.error(f"Import error: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Import error: {str(e)}'
            })
            
    except Exception as e:
        logger.error(f"Error in analysis: {e}")
        import traceback
        traceback.print_exc()
        
        # Return mock data
        return jsonify({
            'status': 'success',
            'regime': 'neutral',
            'confidence': 0.75,
            'market_score': 0.15,
            'volatility_score': 0.45,
            'position_size': 0.8,
            'stop_loss': 1.0,
            'message': f'Using mock data due to error: {str(e)}'
        })

if __name__ == '__main__':
    print("\n" + "="*60)
    print("MARKET REGIME DASHBOARD (Standalone Debug Version)")
    print("="*60)
    print("\nStarting dashboard at: http://localhost:7777")
    print("\nThis version helps debug import issues")
    print("="*60 + "\n")
    
    app.run(host='localhost', port=7777, debug=True)