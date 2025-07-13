#!/usr/bin/env python
"""
Trend Dashboard Generator
Creates visual HTML dashboard for market regime and trend strength
"""

import os
import sys
import json
import datetime
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class TrendDashboard:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.regime_dir = os.path.join(self.script_dir, "regime_analysis")
        self.output_dir = os.path.join(self.script_dir, "dashboards")
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
    def load_latest_regime_report(self):
        """Load the latest regime report"""
        summary_file = os.path.join(self.regime_dir, "latest_regime_summary.json")
        
        if os.path.exists(summary_file):
            with open(summary_file, 'r') as f:
                return json.load(f)
        return None
        
    def generate_dashboard(self):
        """Generate HTML dashboard"""
        report = self.load_latest_regime_report()
        
        if not report:
            print("No regime report found. Please run market_regime_analyzer.py first.")
            return None
            
        # Extract data
        regime = report['market_regime']['regime']
        confidence = report['market_regime'].get('confidence', 0.5)
        confidence_level = report['market_regime'].get('confidence_level', 'Moderate')
        long_count = report['reversal_counts']['long']
        short_count = report['reversal_counts']['short']
        total_count = report['reversal_counts']['total']
        ratio = report['trend_analysis']['ratio']
        
        # Extract breadth indicators
        breadth = report.get('breadth_indicators', {})
        
        # Extract position recommendations
        position_recs = report.get('position_recommendations', {})
        
        # Extract volatility
        volatility = report.get('volatility', {})
        
        # Determine colors and icons based on regime
        regime_colors = {
            'strong_uptrend': '#2ecc71',      # Green
            'uptrend': '#27ae60',             # Dark green
            'choppy_bullish': '#3498db',      # Blue
            'choppy': '#95a5a6',              # Gray
            'choppy_bearish': '#e67e22',      # Orange
            'downtrend': '#e74c3c',           # Red
            'strong_downtrend': '#c0392b'     # Dark red
        }
        
        regime_color = regime_colors.get(regime, '#95a5a6')
        
        # Create gauge percentage for visual
        if ratio == 'inf':
            gauge_percent = 100
        else:
            # Map ratio to 0-100 scale (0.5 = 0%, 1.0 = 50%, 2.0 = 100%)
            gauge_percent = min(100, max(0, (ratio - 0.5) * 100))
            
        # Format ratio properly
        ratio_display = "∞" if ratio == 'inf' or (isinstance(ratio, float) and ratio == float('inf')) else f"{ratio:.2f}"
        
        # Generate HTML
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300"> <!-- Auto-refresh every 5 minutes -->
    <title>India-TS Market Regime Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background-color: #f5f7fa;
            color: #2c3e50;
            line-height: 1.6;
        }}
        
        .dashboard {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            text-align: center;
        }}
        
        h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            color: #2c3e50;
        }}
        
        .timestamp {{
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        
        .regime-indicator {{
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            text-align: center;
        }}
        
        .regime-label {{
            font-size: 3em;
            font-weight: bold;
            color: {regime_color};
            margin-bottom: 10px;
            text-transform: uppercase;
        }}
        
        .regime-description {{
            font-size: 1.2em;
            color: #555;
            margin-bottom: 20px;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .metric-card {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .metric-value {{
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .metric-label {{
            color: #7f8c8d;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .long-value {{
            color: #27ae60;
        }}
        
        .short-value {{
            color: #e74c3c;
        }}
        
        .ratio-gauge {{
            width: 100%;
            height: 30px;
            background: #ecf0f1;
            border-radius: 15px;
            position: relative;
            overflow: hidden;
            margin: 20px 0;
        }}
        
        .gauge-fill {{
            height: 100%;
            background: linear-gradient(to right, #e74c3c 0%, #f39c12 25%, #95a5a6 50%, #3498db 75%, #27ae60 100%);
            width: 100%;
            position: absolute;
        }}
        
        .gauge-marker {{
            position: absolute;
            top: -5px;
            width: 4px;
            height: 40px;
            background: #2c3e50;
            left: {gauge_percent}%;
            transform: translateX(-50%);
            border-radius: 2px;
        }}
        
        .breadth-section {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        
        .section-title {{
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #2c3e50;
        }}
        
        .insights-section {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        
        .insights-title {{
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #2c3e50;
        }}
        
        .insight-item {{
            padding: 10px 0;
            border-bottom: 1px solid #ecf0f1;
        }}
        
        .insight-item:last-child {{
            border-bottom: none;
        }}
        
        .strategy-box {{
            background: {regime_color}15;
            border: 2px solid {regime_color};
            border-radius: 8px;
            padding: 20px;
            margin-top: 20px;
        }}
        
        .strategy-label {{
            font-weight: bold;
            color: {regime_color};
            margin-bottom: 10px;
        }}
        
        .footer {{
            text-align: center;
            color: #7f8c8d;
            font-size: 0.85em;
            margin-top: 40px;
        }}
        
        @media (max-width: 768px) {{
            .dashboard {{
                padding: 10px;
            }}
            
            h1 {{
                font-size: 2em;
            }}
            
            .regime-label {{
                font-size: 2em;
            }}
            
            .metric-value {{
                font-size: 2em;
            }}
        }}
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1>India-TS Market Regime Dashboard</h1>
            <div class="timestamp">Last Updated: {datetime.datetime.fromisoformat(report['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>
        
        <div class="regime-indicator">
            <div class="regime-label">{regime.replace('_', ' ')}</div>
            <div class="regime-description">{report['market_regime']['description']}</div>
            <div style="text-align: center; margin: 10px 0; font-size: 1.2em;">
                Confidence: <strong>{confidence:.1%}</strong> ({confidence_level})
            </div>
            
            <div class="ratio-gauge">
                <div class="gauge-fill"></div>
                <div class="gauge-marker"></div>
            </div>
            
            <div class="strategy-box">
                <div class="strategy-label">Trading Strategy</div>
                <div>{report['market_regime']['strategy']}</div>
            </div>
        </div>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value long-value">{long_count}</div>
                <div class="metric-label">Long Reversals</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-value short-value">{short_count}</div>
                <div class="metric-label">Short Reversals</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-value">{total_count}</div>
                <div class="metric-label">Total Patterns</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-value">{ratio_display}</div>
                <div class="metric-label">Long/Short Ratio</div>
            </div>
        </div>
        """
        
        # Add position recommendations section
        if position_recs:
            html_content += f"""
        <div class="recommendations-section" style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin-top: 20px;">
            <h2 class="section-title">📊 Position Recommendations</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-value" style="color: {regime_color};">{position_recs.get('position_size_multiplier', 1.0)}x</div>
                    <div class="metric-label">Position Size</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-value">{position_recs.get('stop_loss_multiplier', 1.0)}x</div>
                    <div class="metric-label">Stop Loss</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-value">{position_recs.get('max_positions', 5)}</div>
                    <div class="metric-label">Max Positions</div>
                </div>
                
                <div class="metric-card">
                    <div class="metric-value">{position_recs.get('risk_per_trade', 0.01):.1%}</div>
                    <div class="metric-label">Risk per Trade</div>
                </div>
            </div>
            
            <div style="margin-top: 15px; text-align: center;">
                <strong>Preferred Direction:</strong> <span style="color: {regime_color}; font-weight: bold;">{position_recs.get('preferred_direction', 'both').upper()}</span>
            </div>
        </div>
        """
        
        # Add volatility section if available
        if volatility:
            vol_score = volatility.get('volatility_score', 0.5)
            vol_color = '#2ecc71' if vol_score < 0.3 else '#f39c12' if vol_score < 0.7 else '#e74c3c'
            html_content += f"""
        <div class="volatility-section" style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin-top: 20px;">
            <h2 class="section-title">📈 Volatility Analysis</h2>
            <div style="text-align: center;">
                <div style="font-size: 2em; color: {vol_color}; margin: 10px 0;">{vol_score:.1%}</div>
                <div>Volatility Score</div>
                {f'<div style="margin-top: 10px;">Average ATR: {volatility.get("avg_atr", 0):.2f}%</div>' if 'avg_atr' in volatility else ''}
            </div>
        </div>
        """
        
        # Add breadth indicators section if available
        if breadth:
            html_content += """
        <div class="breadth-section">
            <h2 class="section-title">Market Breadth Indicators</h2>
            <div class="metrics-grid">
        """
            
            # Add advance/decline ratio
            if 'advance_decline_ratio' in breadth:
                ad_ratio = breadth['advance_decline_ratio']
                ad_display = "∞" if ad_ratio == float('inf') else f"{ad_ratio:.2f}"
                html_content += f"""
                <div class="metric-card">
                    <div class="metric-value">{ad_display}</div>
                    <div class="metric-label">Advance/Decline</div>
                </div>
                """
                
            # Add bullish/bearish percentages
            if 'bullish_percent' in breadth:
                html_content += f"""
                <div class="metric-card">
                    <div class="metric-value long-value">{breadth['bullish_percent']:.0%}</div>
                    <div class="metric-label">Bullish %</div>
                </div>
                """
                
            if 'bearish_percent' in breadth:
                html_content += f"""
                <div class="metric-card">
                    <div class="metric-value short-value">{breadth['bearish_percent']:.0%}</div>
                    <div class="metric-label">Bearish %</div>
                </div>
                """
                
            # Add momentum breadth
            if 'positive_momentum_percent' in breadth:
                html_content += f"""
                <div class="metric-card">
                    <div class="metric-value">{breadth['positive_momentum_percent']:.0%}</div>
                    <div class="metric-label">Positive Momentum</div>
                </div>
                """
                
            html_content += """
            </div>
        </div>
        """
        
        html_content += """
        <div class="insights-section">
            <h2 class="insights-title">Market Insights</h2>
"""
        
        # Add insights
        for insight in report['insights']:
            html_content += f"""
            <div class="insight-item">• {insight}</div>
"""
        
        # Add momentum if available
        if report.get('momentum_analysis'):
            html_content += f"""
            <div class="insight-item">• Momentum: {report['momentum_analysis']['description']}</div>
"""
        
        html_content += """
        </div>
        
        <div class="footer">
            <p>Dashboard auto-refreshes every 5 minutes</p>
            <p>Generated by India-TS Market Regime Analysis System</p>
        </div>
    </div>
</body>
</html>
"""
        
        # Save dashboard
        output_file = os.path.join(self.output_dir, "market_regime_dashboard.html")
        with open(output_file, 'w') as f:
            f.write(html_content)
            
        print(f"Dashboard generated: {output_file}")
        return output_file
        

def main():
    """Generate the trend dashboard"""
    dashboard = TrendDashboard()
    dashboard.generate_dashboard()
    

if __name__ == "__main__":
    main()