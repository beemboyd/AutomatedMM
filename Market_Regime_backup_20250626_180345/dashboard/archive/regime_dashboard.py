"""
Market Regime Dashboard

Real-time dashboard for market regime analysis and recommendations.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Flask, render_template, jsonify
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

# Get the directory of this file
dashboard_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(dashboard_dir, 'templates')

app = Flask(__name__, template_folder=template_dir)
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
    try:
        # Debug logging
        app.logger.info(f"Template folder: {app.template_folder}")
        app.logger.info(f"Looking for template at: {os.path.join(app.template_folder, 'regime_dashboard.html')}")
        
        # Check if template exists
        template_path = os.path.join(app.template_folder, 'regime_dashboard.html')
        if not os.path.exists(template_path):
            app.logger.error(f"Template not found at: {template_path}")
            return f"Template not found. Looking at: {template_path}", 404
            
        return render_template('regime_dashboard.html')
    except Exception as e:
        app.logger.error(f"Error rendering template: {e}")
        return f"Error: {str(e)}", 500


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


def run_dashboard(host='127.0.0.1', port=5000, debug=False):
    """Run the dashboard"""
    # Start update thread
    dashboard.start_updates()
    
    # Run initial analysis
    try:
        dashboard._update_loop()
    except Exception as e:
        app.logger.warning(f"Initial analysis failed: {e}")
    
    # Start Flask app with proper settings
    app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Run dashboard
    run_dashboard(debug=True)