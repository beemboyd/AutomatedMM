#!/usr/bin/env python3
"""
Dashboard Server for Daily Market Regime
Serves the HTML dashboard with auto-refresh
"""

from flask import Flask, send_from_directory, jsonify
import os
import json
from datetime import datetime

app = Flask(__name__)

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DIR = os.path.join(SCRIPT_DIR, 'dashboards')
REGIME_DIR = os.path.join(SCRIPT_DIR, 'regime_analysis')

@app.route('/')
def serve_dashboard():
    """Serve the main dashboard HTML"""
    return send_from_directory(DASHBOARD_DIR, 'market_regime_dashboard.html')

@app.route('/api/latest')
def get_latest_data():
    """Get latest regime data as JSON"""
    summary_file = os.path.join(REGIME_DIR, 'latest_regime_summary.json')
    
    if os.path.exists(summary_file):
        with open(summary_file, 'r') as f:
            data = json.load(f)
            # Add age of data
            timestamp = datetime.fromisoformat(data['timestamp'])
            age_minutes = (datetime.now() - timestamp).total_seconds() / 60
            data['data_age_minutes'] = round(age_minutes, 1)
            return jsonify(data)
    
    return jsonify({'error': 'No data available'})

@app.route('/api/status')
def get_status():
    """Get system status"""
    summary_file = os.path.join(REGIME_DIR, 'latest_regime_summary.json')
    
    status = {
        'dashboard_available': os.path.exists(os.path.join(DASHBOARD_DIR, 'market_regime_dashboard.html')),
        'data_available': os.path.exists(summary_file),
        'last_update': None,
        'regime': None,
        'confidence': None
    }
    
    if os.path.exists(summary_file):
        with open(summary_file, 'r') as f:
            data = json.load(f)
            status['last_update'] = data['timestamp']
            status['regime'] = data['market_regime']['regime']
            status['confidence'] = data['market_regime']['confidence']
    
    return jsonify(status)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Daily Market Regime Dashboard Server")
    print("="*60)
    print(f"\nDashboard URL: http://localhost:7078")
    print("\nEndpoints:")
    print("  /           - Main dashboard")
    print("  /api/latest - Latest regime data (JSON)")
    print("  /api/status - System status")
    print("\nPress Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=7078, debug=False)