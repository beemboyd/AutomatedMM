"""
Market Regime Dashboard - Fixed Version

Real-time dashboard for market regime analysis and recommendations.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Flask, render_template_string, jsonify
import json
import threading
import time
from datetime import datetime
import logging
import pandas as pd
import plotly.graph_objs as go
import plotly.utils

from Market_Regime.integration.daily_integration import DailyTradingIntegration
from Market_Regime.core.regime_detector import MarketRegime

# Embedded HTML template
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Market Regime Dashboard</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    
    <!-- Plotly -->
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    
    <style>
        body {
            background-color: #f8f9fa;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .dashboard-header {
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            color: white;
            padding: 20px 0;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .regime-card {
            border-radius: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.3s;
            height: 100%;
        }
        
        .regime-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
        }
        
        .regime-badge {
            font-size: 2.5rem;
            font-weight: bold;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 15px;
        }
        
        .strong_bull { background-color: #006400; color: white; }
        .bull { background-color: #32CD32; color: white; }
        .neutral { background-color: #FFD700; color: black; }
        .bear { background-color: #FF6347; color: white; }
        .strong_bear { background-color: #8B0000; color: white; }
        .volatile { background-color: #FF8C00; color: white; }
        .crisis { background-color: #800080; color: white; }
        
        .metric-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .metric-label {
            color: #6c757d;
            font-size: 0.9rem;
            margin-bottom: 5px;
        }
        
        .metric-value {
            font-size: 1.8rem;
            font-weight: bold;
        }
        
        .action-item {
            padding: 10px 15px;
            margin-bottom: 10px;
            border-radius: 5px;
            border-left: 4px solid;
        }
        
        .action-HIGH { border-left-color: #dc3545; background-color: #f8d7da; }
        .action-MEDIUM { border-left-color: #ffc107; background-color: #fff3cd; }
        .action-LOW { border-left-color: #28a745; background-color: #d4edda; }
        
        .alert-item {
            padding: 10px 15px;
            margin-bottom: 10px;
            border-radius: 5px;
        }
        
        .alert-CRITICAL { background-color: #dc3545; color: white; }
        .alert-HIGH { background-color: #fd7e14; color: white; }
        .alert-MEDIUM { background-color: #ffc107; color: black; }
        
        .chart-container {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .update-time {
            color: #6c757d;
            font-size: 0.9rem;
            text-align: right;
            margin-top: 10px;
        }
        
        .loading {
            text-align: center;
            padding: 50px;
            color: #6c757d;
        }
        
        .spinner-border {
            width: 3rem;
            height: 3rem;
        }
    </style>
</head>
<body>
    <div class="dashboard-header">
        <div class="container">
            <h1><i class="fas fa-chart-line"></i> Market Regime Dashboard</h1>
            <p class="mb-0">Real-time market regime analysis and trading recommendations</p>
        </div>
    </div>
    
    <div class="container">
        <!-- Current Regime Section -->
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card regime-card">
                    <div class="card-body">
                        <h2 class="card-title mb-4">Current Market Regime</h2>
                        <div id="current-regime-content" class="loading">
                            <div class="spinner-border text-primary" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <p class="mt-3">Loading regime analysis...</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Key Metrics Row -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="metric-label">Market Score</div>
                    <div class="metric-value" id="market-score">-</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="metric-label">Trend Score</div>
                    <div class="metric-value" id="trend-score">-</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="metric-label">Volatility Score</div>
                    <div class="metric-value" id="volatility-score">-</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="metric-label">Breadth Score</div>
                    <div class="metric-value" id="breadth-score">-</div>
                </div>
            </div>
        </div>
        
        <!-- Scanner Breadth Section (Primary) -->
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card regime-card">
                    <div class="card-body">
                        <h3 class="card-title"><i class="fas fa-chart-bar"></i> Scanner Breadth Indicators</h3>
                        <div class="row mt-3">
                            <div class="col-md-2">
                                <div class="metric-card">
                                    <div class="metric-label">A/D Ratio</div>
                                    <div class="metric-value" id="ad-ratio">-</div>
                                </div>
                            </div>
                            <div class="col-md-2">
                                <div class="metric-card">
                                    <div class="metric-label">Bullish %</div>
                                    <div class="metric-value text-success" id="bullish-percent">-</div>
                                </div>
                            </div>
                            <div class="col-md-2">
                                <div class="metric-card">
                                    <div class="metric-label">Bearish %</div>
                                    <div class="metric-value text-danger" id="bearish-percent">-</div>
                                </div>
                            </div>
                            <div class="col-md-2">
                                <div class="metric-card">
                                    <div class="metric-label">Positive Mom. %</div>
                                    <div class="metric-value" id="positive-momentum">-</div>
                                </div>
                            </div>
                            <div class="col-md-2">
                                <div class="metric-card">
                                    <div class="metric-label">Mom. Ratio</div>
                                    <div class="metric-value" id="momentum-ratio">-</div>
                                </div>
                            </div>
                            <div class="col-md-2">
                                <div class="metric-card">
                                    <div class="metric-label">Vol. Participation</div>
                                    <div class="metric-value" id="volume-participation">-</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- NIFTY Market Breadth Section (Supplementary) -->
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card regime-card">
                    <div class="card-body">
                        <h3 class="card-title"><i class="fas fa-chart-line"></i> NIFTY Market Breadth</h3>
                        <div class="row mt-3">
                            <div class="col-md-3">
                                <div class="metric-card">
                                    <div class="metric-label">NIFTY A/D Ratio</div>
                                    <div class="metric-value" id="nifty-ad-ratio">-</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="metric-card">
                                    <div class="metric-label">NIFTY Bullish %</div>
                                    <div class="metric-value text-success" id="nifty-bullish-percent">-</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="metric-card">
                                    <div class="metric-label">NIFTY Bearish %</div>
                                    <div class="metric-value text-danger" id="nifty-bearish-percent">-</div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="metric-card">
                                    <div class="metric-label">NIFTY Breadth Score</div>
                                    <div class="metric-value" id="nifty-breadth-score">-</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Recommendations Section -->
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card regime-card">
                    <div class="card-body">
                        <h3 class="card-title"><i class="fas fa-cogs"></i> Trading Parameters</h3>
                        <div id="trading-params" class="mt-3">
                            <div class="loading">Loading...</div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card regime-card">
                    <div class="card-body">
                        <h3 class="card-title"><i class="fas fa-tasks"></i> Specific Actions</h3>
                        <div id="specific-actions" class="mt-3">
                            <div class="loading">Loading...</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Alerts Section -->
        <div class="row mb-4" id="alerts-section" style="display: none;">
            <div class="col-md-12">
                <div class="card regime-card">
                    <div class="card-body">
                        <h3 class="card-title"><i class="fas fa-exclamation-triangle"></i> Active Alerts</h3>
                        <div id="alerts-content" class="mt-3"></div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Charts Section -->
        <div class="row mb-4">
            <div class="col-md-4">
                <div class="chart-container">
                    <div id="regime-distribution-chart"></div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="chart-container">
                    <div id="confidence-trend-chart"></div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="chart-container">
                    <div id="market-score-trend-chart"></div>
                </div>
            </div>
        </div>
        
        <!-- Update Time -->
        <div class="update-time">
            Last updated: <span id="last-update">-</span>
        </div>
    </div>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    
    <script>
        // Update interval (5 seconds for UI, actual data updates every 5 minutes)
        const UPDATE_INTERVAL = 5000;
        
        // Format number
        function formatNumber(num, decimals = 2) {
            if (num === null || num === undefined) return '-';
            return num.toFixed(decimals);
        }
        
        // Format percentage
        function formatPercent(num) {
            if (num === null || num === undefined) return '-';
            return (num * 100).toFixed(1) + '%';
        }
        
        // Update current regime display
        function updateCurrentRegime(data) {
            const regimeHtml = `
                <div class="row">
                    <div class="col-md-6">
                        <div class="regime-badge ${data.regime}">
                            ${data.regime.replace('_', ' ').toUpperCase()}
                        </div>
                        <div class="text-center">
                            <h4>Confidence: ${formatPercent(data.confidence)}</h4>
                            ${data.regime_changed ? '<span class="badge bg-warning">Regime Changed!</span>' : ''}
                        </div>
                    </div>
                    <div class="col-md-6">
                        <h5>Market Indicators</h5>
                        <table class="table table-sm">
                            <tr>
                                <td>Market Score:</td>
                                <td class="text-end"><strong>${formatNumber(data.market_score)}</strong></td>
                            </tr>
                            <tr>
                                <td>Trend Score:</td>
                                <td class="text-end"><strong>${formatNumber(data.trend_score)}</strong></td>
                            </tr>
                            <tr>
                                <td>Volatility Score:</td>
                                <td class="text-end"><strong>${formatNumber(data.volatility_score)}</strong></td>
                            </tr>
                            <tr>
                                <td>Breadth Score:</td>
                                <td class="text-end"><strong>${formatNumber(data.breadth_score)}</strong></td>
                            </tr>
                        </table>
                    </div>
                </div>
            `;
            
            document.getElementById('current-regime-content').innerHTML = regimeHtml;
            
            // Update metric cards
            document.getElementById('market-score').textContent = formatNumber(data.market_score);
            document.getElementById('trend-score').textContent = formatNumber(data.trend_score);
            document.getElementById('volatility-score').textContent = formatNumber(data.volatility_score);
            document.getElementById('breadth-score').textContent = formatNumber(data.breadth_score);
            
            // Update scanner breadth indicators (primary)
            if (data.breadth_indicators) {
                document.getElementById('ad-ratio').textContent = formatNumber(data.breadth_indicators.advance_decline_ratio);
                document.getElementById('bullish-percent').textContent = formatPercent(data.breadth_indicators.bullish_percent);
                document.getElementById('bearish-percent').textContent = formatPercent(data.breadth_indicators.bearish_percent);
                document.getElementById('positive-momentum').textContent = formatPercent(data.breadth_indicators.positive_momentum_percent);
                document.getElementById('momentum-ratio').textContent = formatNumber(data.breadth_indicators.momentum_ratio);
                document.getElementById('volume-participation').textContent = formatPercent(data.breadth_indicators.volume_participation);
            }
            
            // Update NIFTY breadth indicators (supplementary)
            if (data.nifty_breadth) {
                document.getElementById('nifty-ad-ratio').textContent = formatNumber(data.nifty_breadth.advance_decline_ratio);
                document.getElementById('nifty-bullish-percent').textContent = formatPercent(data.nifty_breadth.bullish_percent);
                document.getElementById('nifty-bearish-percent').textContent = formatPercent(data.nifty_breadth.bearish_percent);
                document.getElementById('nifty-breadth-score').textContent = formatNumber(data.nifty_breadth.breadth_score);
            }
        }
        
        // Update trading parameters
        function updateTradingParams(data) {
            const paramsHtml = `
                <table class="table table-sm">
                    <tr>
                        <td>Position Size Multiplier:</td>
                        <td class="text-end"><strong>${data.position_sizing.size_multiplier}x</strong></td>
                    </tr>
                    <tr>
                        <td>Max Position Size:</td>
                        <td class="text-end"><strong>${formatPercent(data.position_sizing.max_position_size)}</strong></td>
                    </tr>
                    <tr>
                        <td>Stop Loss Multiplier:</td>
                        <td class="text-end"><strong>${data.risk_management.stop_loss_multiplier}x</strong></td>
                    </tr>
                    <tr>
                        <td>Risk Per Trade:</td>
                        <td class="text-end"><strong>${formatPercent(data.risk_management.risk_per_trade)}</strong></td>
                    </tr>
                    <tr>
                        <td>Capital Deployment:</td>
                        <td class="text-end"><strong>${formatPercent(data.capital_deployment.deployment_rate)}</strong></td>
                    </tr>
                    <tr>
                        <td>Cash Allocation:</td>
                        <td class="text-end"><strong>${formatPercent(data.capital_deployment.cash_allocation)}</strong></td>
                    </tr>
                </table>
                <div class="mt-3">
                    <h6>Preferred Sectors:</h6>
                    <p>${data.sector_preferences.preferred_sectors.join(', ') || 'None'}</p>
                </div>
            `;
            
            document.getElementById('trading-params').innerHTML = paramsHtml;
        }
        
        // Update specific actions
        function updateSpecificActions(actions) {
            let actionsHtml = '';
            
            actions.forEach(action => {
                actionsHtml += `
                    <div class="action-item action-${action.priority}">
                        <strong>[${action.priority}] ${action.action}</strong><br>
                        ${action.description}<br>
                        <small class="text-muted">${action.reason}</small>
                    </div>
                `;
            });
            
            document.getElementById('specific-actions').innerHTML = actionsHtml || '<p>No specific actions at this time.</p>';
        }
        
        // Update alerts
        function updateAlerts(alerts) {
            if (alerts && alerts.length > 0) {
                let alertsHtml = '';
                
                alerts.forEach(alert => {
                    alertsHtml += `
                        <div class="alert-item alert-${alert.severity}">
                            <strong>${alert.type}</strong><br>
                            ${alert.message}
                        </div>
                    `;
                });
                
                document.getElementById('alerts-content').innerHTML = alertsHtml;
                document.getElementById('alerts-section').style.display = 'block';
            } else {
                document.getElementById('alerts-section').style.display = 'none';
            }
        }
        
        // Update charts
        function updateCharts() {
            // Regime distribution
            fetch('/api/charts/regime_distribution')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        const chart = JSON.parse(data.chart);
                        Plotly.newPlot('regime-distribution-chart', chart.data, chart.layout, {responsive: true});
                    }
                });
            
            // Confidence trend
            fetch('/api/charts/confidence_trend')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        const chart = JSON.parse(data.chart);
                        Plotly.newPlot('confidence-trend-chart', chart.data, chart.layout, {responsive: true});
                    }
                });
            
            // Market score trend
            fetch('/api/charts/market_score_trend')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        const chart = JSON.parse(data.chart);
                        Plotly.newPlot('market-score-trend-chart', chart.data, chart.layout, {responsive: true});
                    }
                });
        }
        
        // Main update function
        function updateDashboard() {
            // Update current analysis
            fetch('/api/current_analysis')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        updateCurrentRegime(data.data);
                        document.getElementById('last-update').textContent = new Date().toLocaleString();
                    }
                });
            
            // Update recommendations
            fetch('/api/recommendations')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        updateTradingParams(data.data);
                        updateSpecificActions(data.data.specific_actions);
                        updateAlerts(data.data.alerts);
                    }
                });
            
            // Update charts (less frequently)
            updateCharts();
        }
        
        // Initial update
        updateDashboard();
        
        // Set up periodic updates
        setInterval(updateDashboard, UPDATE_INTERVAL);
    </script>
</body>
</html>'''

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Global variables
current_analysis = None
analysis_history = []
update_thread = None
update_interval = 300  # 5 minutes


class RegimeDashboard:
    """Dashboard controller for regime analysis"""
    
    def __init__(self):
        self.integration = DailyTradingIntegration()
        self.logger = logging.getLogger(__name__)
        self.is_running = False
        
    def start_updates(self):
        """Start periodic updates"""
        self.is_running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        
    def stop_updates(self):
        """Stop periodic updates"""
        self.is_running = False
        
    def _update_loop(self):
        """Update loop for periodic analysis"""
        global current_analysis, analysis_history
        
        while self.is_running:
            try:
                # Run analysis
                analysis = self.integration.analyze_current_market_regime()
                
                if 'error' not in analysis:
                    current_analysis = analysis
                    
                    # Add to history
                    analysis_history.append({
                        'timestamp': analysis['timestamp'],
                        'regime': analysis['regime_analysis']['enhanced_regime'],
                        'confidence': analysis['regime_analysis']['enhanced_confidence'],
                        'market_score': analysis['regime_analysis']['indicators'].get('market_score', 0)
                    })
                    
                    # Keep only last 100 entries
                    if len(analysis_history) > 100:
                        analysis_history = analysis_history[-100:]
                    
                    self.logger.info(f"Updated regime analysis: {analysis['regime_analysis']['enhanced_regime']}")
                    
            except Exception as e:
                self.logger.error(f"Error in update loop: {e}")
            
            # Wait for next update
            time.sleep(update_interval)
    
    def get_current_analysis(self):
        """Get current analysis data"""
        return current_analysis
    
    def get_history_data(self):
        """Get historical regime data"""
        return analysis_history
    
    def get_regime_chart_data(self):
        """Generate regime distribution chart data"""
        if not analysis_history:
            return None
        
        # Count regimes
        regime_counts = {}
        for entry in analysis_history:
            regime = entry['regime']
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
        
        # Create pie chart
        fig = go.Figure(data=[go.Pie(
            labels=list(regime_counts.keys()),
            values=list(regime_counts.values()),
            hole=.3,
            marker=dict(colors=self._get_regime_colors(list(regime_counts.keys())))
        )])
        
        fig.update_layout(
            title="Regime Distribution",
            showlegend=True,
            height=300
        )
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def get_confidence_chart_data(self):
        """Generate confidence trend chart data"""
        if not analysis_history:
            return None
        
        # Extract data
        timestamps = [entry['timestamp'] for entry in analysis_history]
        confidences = [entry['confidence'] * 100 for entry in analysis_history]
        
        # Create line chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=confidences,
            mode='lines+markers',
            name='Confidence',
            line=dict(color='blue', width=2)
        ))
        
        fig.update_layout(
            title="Regime Confidence Trend",
            xaxis_title="Time",
            yaxis_title="Confidence (%)",
            height=300,
            yaxis=dict(range=[0, 100])
        )
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def get_market_score_chart_data(self):
        """Generate market score trend chart data"""
        if not analysis_history:
            return None
        
        # Extract data
        timestamps = [entry['timestamp'] for entry in analysis_history]
        scores = [entry['market_score'] for entry in analysis_history]
        
        # Create line chart with color zones
        fig = go.Figure()
        
        # Add background zones
        fig.add_hrect(y0=0.5, y1=1, fillcolor="green", opacity=0.1)
        fig.add_hrect(y0=-0.5, y1=0.5, fillcolor="yellow", opacity=0.1)
        fig.add_hrect(y0=-1, y1=-0.5, fillcolor="red", opacity=0.1)
        
        # Add score line
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=scores,
            mode='lines+markers',
            name='Market Score',
            line=dict(color='black', width=2)
        ))
        
        fig.update_layout(
            title="Market Score Trend",
            xaxis_title="Time",
            yaxis_title="Score",
            height=300,
            yaxis=dict(range=[-1, 1])
        )
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def _get_regime_colors(self, regimes):
        """Get color scheme for regimes"""
        color_map = {
            'strong_bull': '#006400',  # Dark green
            'bull': '#32CD32',         # Lime green
            'neutral': '#FFD700',      # Gold
            'bear': '#FF6347',         # Tomato
            'strong_bear': '#8B0000',  # Dark red
            'volatile': '#FF8C00',     # Dark orange
            'crisis': '#800080'        # Purple
        }
        
        return [color_map.get(regime, '#808080') for regime in regimes]


# Initialize dashboard
dashboard = RegimeDashboard()


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/current_analysis')
def api_current_analysis():
    """API endpoint for current analysis"""
    analysis = dashboard.get_current_analysis()
    
    if analysis:
        return jsonify({
            'status': 'success',
            'data': {
                'regime': analysis['regime_analysis']['enhanced_regime'],
                'confidence': analysis['regime_analysis']['enhanced_confidence'],
                'previous_regime': analysis['regime_analysis'].get('previous_regime'),
                'regime_changed': analysis['regime_analysis'].get('regime_changed', False),
                'market_score': analysis['regime_analysis']['indicators'].get('market_score', 0),
                'trend_score': analysis['regime_analysis']['indicators'].get('trend_score', 0),
                'volatility_score': analysis['regime_analysis']['indicators'].get('volatility_score', 0),
                'breadth_score': analysis['regime_analysis']['indicators'].get('breadth_score', 0),
                'breadth_indicators': {
                    'advance_decline_ratio': analysis['regime_analysis']['indicators'].get('advance_decline_ratio', 1.0),
                    'bullish_percent': analysis['regime_analysis']['indicators'].get('bullish_percent', 0.5),
                    'bearish_percent': analysis['regime_analysis']['indicators'].get('bearish_percent', 0.5),
                    'positive_momentum_percent': analysis['regime_analysis']['indicators'].get('positive_momentum_percent', 0.5),
                    'momentum_ratio': analysis['regime_analysis']['indicators'].get('momentum_ratio', 1.0),
                    'volume_participation': analysis['regime_analysis']['indicators'].get('volume_participation', 0.5)
                },
                'nifty_breadth': {
                    'advance_decline_ratio': analysis['regime_analysis']['indicators'].get('nifty_advance_decline_ratio', 1.0),
                    'bullish_percent': analysis['regime_analysis']['indicators'].get('nifty_bullish_percent', 0.5),
                    'bearish_percent': analysis['regime_analysis']['indicators'].get('nifty_bearish_percent', 0.5),
                    'breadth_score': analysis['regime_analysis']['indicators'].get('nifty_breadth_score', 0.0)
                },
                'timestamp': analysis['timestamp']
            }
        })
    else:
        return jsonify({
            'status': 'no_data',
            'message': 'No analysis data available yet'
        })


@app.route('/api/recommendations')
def api_recommendations():
    """API endpoint for recommendations"""
    analysis = dashboard.get_current_analysis()
    
    if analysis and 'recommendations' in analysis:
        recs = analysis['recommendations']
        
        return jsonify({
            'status': 'success',
            'data': {
                'position_sizing': recs['position_sizing'],
                'risk_management': recs['risk_management'],
                'capital_deployment': recs['capital_deployment'],
                'sector_preferences': recs['sector_preferences'],
                'specific_actions': recs['specific_actions'][:5],  # Top 5 actions
                'alerts': recs['alerts']
            }
        })
    else:
        return jsonify({
            'status': 'no_data',
            'message': 'No recommendations available yet'
        })


@app.route('/api/charts/regime_distribution')
def api_regime_distribution():
    """API endpoint for regime distribution chart"""
    chart_data = dashboard.get_regime_chart_data()
    
    if chart_data:
        return jsonify({
            'status': 'success',
            'chart': chart_data
        })
    else:
        return jsonify({
            'status': 'no_data'
        })


@app.route('/api/charts/confidence_trend')
def api_confidence_trend():
    """API endpoint for confidence trend chart"""
    chart_data = dashboard.get_confidence_chart_data()
    
    if chart_data:
        return jsonify({
            'status': 'success',
            'chart': chart_data
        })
    else:
        return jsonify({
            'status': 'no_data'
        })


@app.route('/api/charts/market_score_trend')
def api_market_score_trend():
    """API endpoint for market score trend chart"""
    chart_data = dashboard.get_market_score_chart_data()
    
    if chart_data:
        return jsonify({
            'status': 'success',
            'chart': chart_data
        })
    else:
        return jsonify({
            'status': 'no_data'
        })


@app.route('/api/history')
def api_history():
    """API endpoint for regime history"""
    history = dashboard.get_history_data()
    
    return jsonify({
        'status': 'success',
        'data': history[-20:]  # Last 20 entries
    })


def run_dashboard(host='localhost', port=5000, debug=False):
    """Run the dashboard"""
    # Start update thread
    dashboard.start_updates()
    
    # Run initial analysis
    try:
        print("Running initial analysis...")
        analysis = dashboard.integration.analyze_current_market_regime()
        if 'error' not in analysis:
            global current_analysis
            current_analysis = analysis
            print(f"Initial analysis complete: {analysis['regime_analysis']['enhanced_regime']}")
        else:
            print(f"Initial analysis error: {analysis['error']}")
    except Exception as e:
        print(f"Initial analysis failed: {e}")
    
    # Start Flask app
    app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Run dashboard
    run_dashboard(debug=True)