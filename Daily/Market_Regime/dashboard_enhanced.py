#!/usr/bin/env python3
"""
Daily Market Regime Enhanced Dashboard
Advanced visualization with real-time updates and trend analysis
"""

from flask import Flask, render_template_string, jsonify
import os
import json
import glob
from datetime import datetime, timedelta
import pytz
from collections import deque
import pandas as pd
import re
import logging
import sys
import configparser

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import momentum widget
from dashboards.market_breadth_momentum_widget import get_market_breadth_momentum_data, get_market_breadth_momentum_trend

# Import ML integration
try:
    from ml_dashboard_integration import get_ml_insights, get_ml_alerts, get_ml_performance
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("ML integration not available - joblib module may be missing")

app = Flask(__name__)

# Timezone setup
IST = pytz.timezone('Asia/Kolkata')

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGIME_DIR = os.path.join(SCRIPT_DIR, 'regime_analysis')
SCAN_RESULTS_DIR = os.path.join(SCRIPT_DIR, 'scan_results')
DATA_DIR = os.path.join(SCRIPT_DIR, 'data')
TREND_DIR = os.path.join(SCRIPT_DIR, 'trend_analysis')
DAILY_DIR = os.path.dirname(SCRIPT_DIR)
G_PATTERN_DIR = os.path.join(DAILY_DIR, 'G_Pattern_Master')
LONG_RESULTS_DIR = os.path.join(DAILY_DIR, 'results')
SHORT_RESULTS_DIR = os.path.join(DAILY_DIR, 'results-s')

# Load dashboard configuration
config = configparser.ConfigParser()
config_path = os.path.join(DAILY_DIR, 'config.ini')
config.read(config_path)

# Get dashboard settings with defaults
DASHBOARD_CONFIG = {
    'show_ml_insights': config.getboolean('Dashboard', 'show_ml_insights', fallback=True),
    'show_market_regime': config.getboolean('Dashboard', 'show_market_regime', fallback=True),
    'show_sma_breadth': config.getboolean('Dashboard', 'show_sma_breadth', fallback=True),
    'show_volume_breadth': config.getboolean('Dashboard', 'show_volume_breadth', fallback=True),
    'show_reversal_patterns': config.getboolean('Dashboard', 'show_reversal_patterns', fallback=True),
    'show_g_pattern': config.getboolean('Dashboard', 'show_g_pattern', fallback=True),
    'show_vsr_tracker': config.getboolean('Dashboard', 'show_vsr_tracker', fallback=True),
    'show_optimal_conditions': config.getboolean('Dashboard', 'show_optimal_conditions', fallback=True),
    'show_momentum_scanner': config.getboolean('Dashboard', 'show_momentum_scanner', fallback=False),
    'show_regime_history': config.getboolean('Dashboard', 'show_regime_history', fallback=False),
    'show_confidence_trend': config.getboolean('Dashboard', 'show_confidence_trend', fallback=False),
    'show_weekly_bias': config.getboolean('Dashboard', 'show_weekly_bias', fallback=False)
}

logger.info(f"Dashboard configuration loaded: {DASHBOARD_CONFIG}")

# Store historical data for charts
HISTORY_WINDOW = 50
regime_history = deque(maxlen=HISTORY_WINDOW)
score_history = {
    'market_score': deque(maxlen=HISTORY_WINDOW),
    'trend_score': deque(maxlen=HISTORY_WINDOW),
    'volatility_score': deque(maxlen=HISTORY_WINDOW),
    'confidence': deque(maxlen=HISTORY_WINDOW)
}

# Enhanced Dashboard HTML
ENHANCED_DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>India-TS Market Regime & G Pattern Dashboard</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    
    <style>
        body {
            background-color: #f8f9fa;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow-x: hidden;
            min-height: 100vh;
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
            position: relative;
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
            position: relative;
        }
        
        .strong_uptrend { background-color: #006400; color: white; }
        .uptrend { background-color: #32CD32; color: white; }
        .choppy_bullish { background-color: #FFD700; color: black; }
        .choppy { background-color: #D3D3D3; color: black; }
        .choppy_bearish { background-color: #FF8C00; color: white; }
        .downtrend { background-color: #FF6347; color: white; }
        .strong_downtrend { background-color: #8B0000; color: white; }
        
        .metric-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            height: 100%;
        }
        
        .metric-title {
            font-size: 0.9rem;
            color: #6c757d;
            margin-bottom: 10px;
        }
        
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
            margin-bottom: 5px;
            cursor: help;
        }
        
        .kelly-details {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 10px;
            margin-top: 10px;
            font-size: 0.85rem;
        }
        
        .kelly-formula {
            font-family: 'Courier New', monospace;
            background: #e9ecef;
            padding: 5px;
            border-radius: 3px;
            display: inline-block;
        }
        
        .metric-delta {
            font-size: 0.9rem;
        }
        
        .metric-delta.positive { color: #28a745; }
        .metric-delta.negative { color: #dc3545; }
        
        .sparkline-container {
            display: block;
            width: 100%;
            max-width: 200px;
            height: 50px;
            margin: 10px auto 0;
        }
        
        .position-rec-card {
            background: #e8f4f8;
            border: 2px solid #17a2b8;
            border-radius: 10px;
            padding: 20px;
        }
        
        .proximity-bar {
            height: 30px;
            background: linear-gradient(to right, #8B0000, #FF6347, #FFD700, #32CD32, #006400);
            border-radius: 15px;
            position: relative;
            margin: 20px 0;
        }
        
        .proximity-marker {
            position: absolute;
            top: -5px;
            width: 40px;
            height: 40px;
            background: white;
            border: 3px solid #333;
            border-radius: 50%;
            transform: translateX(-50%);
            transition: left 0.5s ease;
        }
        
        .chart-container {
            background: white;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            height: 250px;
            position: relative;
        }
        
        .chart-container canvas {
            max-height: 150px !important;
        }
        
        .loading {
            text-align: center;
            color: #6c757d;
            padding: 20px;
        }
        
        /* SMA Breadth Section Styles */
        #sma20-breadth-chart,
        #sma50-breadth-chart {
            max-height: 450px !important;
            height: 450px !important;
        }
        
        /* Volume Breadth Section Styles */
        #volume-breadth-chart,
        #volume-participation-chart {
            max-height: 450px !important;
            height: 450px !important;
        }
        
        .sma-breadth-stats {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
        }
        
        .sma-breadth-stats .col-md-2 {
            border-right: 1px solid #dee2e6;
            padding: 10px;
        }
        
        .sma-breadth-stats .col-md-2:last-child {
            border-right: none;
        }
        
        .sma-breadth-stats strong {
            display: block;
            font-size: 0.85rem;
            color: #495057;
            margin-bottom: 5px;
        }
        
        .sma-breadth-stats .h5 {
            font-size: 1.5rem;
            font-weight: 600;
            margin: 0;
        }
        
        /* Multi-timeframe styles */
        .timeframe-card {
            border: 2px solid #dee2e6;
            transition: all 0.3s ease;
        }
        
        .timeframe-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .tf-regime {
            font-size: 0.9rem;
            text-transform: uppercase;
        }
        
        .timeframe-card.strong_downtrend {
            border-color: #c0392b;
        }
        
        .timeframe-card.downtrend {
            border-color: #e74c3c;
        }
        
        .timeframe-card.choppy_bearish {
            border-color: #e67e22;
        }
        
        .timeframe-card.choppy {
            border-color: #95a5a6;
        }
        
        .timeframe-card.choppy_bullish {
            border-color: #3498db;
        }
        
        .timeframe-card.uptrend {
            border-color: #27ae60;
        }
        
        .timeframe-card.strong_uptrend {
            border-color: #2ecc71;
        }
        
        /* ML Styles */
        .ml-strategy-box {
            background: #6c757d;
            color: white;
            transition: all 0.3s ease;
        }
        
        .ml-metrics, .ml-conditions {
            background: #f8f9fa;
            border-radius: 8px;
        }
        
        .metric-row, .condition-row {
            padding: 8px 0;
            border-bottom: 1px solid #e9ecef;
        }
        
        .metric-row:last-child, .condition-row:last-child {
            border-bottom: none;
        }
        
        .insight-card {
            background: #f8f9fa;
            transition: transform 0.2s;
        }
        
        .insight-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        #mlInsightsCard {
            border: 2px solid #007bff;
            box-shadow: 0 4px 12px rgba(0,123,255,0.15);
        }
    </style>
</head>
<body>
    <div class="dashboard-header">
        <div class="container">
            <h1 class="text-center mb-0">
                <i class="fas fa-chart-line"></i> India-TS Daily Market Regime Dashboard
            </h1>
            <p class="text-center mt-2 mb-0">Real-time Market Analysis & Recommendations</p>
        </div>
    </div>
    
    <div class="container">
        <!-- Current Regime Section -->
        <div class="row mb-4">
            <div class="col-lg-8">
                <div class="card regime-card">
                    <div class="card-body">
                        <h5 class="card-title">Current Market Regime</h5>
                        <div id="regime-badge" class="regime-badge">
                            <div class="loading">Loading...</div>
                        </div>
                        
                        <div class="row text-center mb-3">
                            <div class="col">
                                <h4 id="confidence-display">-</h4>
                                <small class="text-muted">Confidence</small>
                            </div>
                            <div class="col">
                                <h4 id="ratio-display">-</h4>
                                <small class="text-muted">Long/Short Ratio</small>
                            </div>
                        </div>
                        
                        <div class="proximity-bar">
                            <div id="proximity-marker" class="proximity-marker" style="left: 50%;"></div>
                        </div>
                        
                        <div id="strategy-box" class="alert alert-info mt-3">
                            <strong>Strategy:</strong> <span id="strategy-text">Loading...</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-lg-4">
                <div class="card position-rec-card h-100">
                    <div class="card-body">
                        <h5 class="card-title" title="Kelly Criterion calculates optimal position size based on win probability and payoff ratio"><i class="fas fa-bullseye"></i> Kelly Criterion Position Sizing</h5>
                        <div class="row text-center">
                            <div class="col-6 mb-3">
                                <div class="metric-value" id="kelly-fraction">-</div>
                                <small>Kelly %</small>
                            </div>
                            <div class="col-6 mb-3">
                                <div class="metric-value" id="expected-value">-</div>
                                <small>Expected Value</small>
                            </div>
                            <div class="col-6 mb-3">
                                <div class="metric-value" id="win-probability">-</div>
                                <small>Win Probability</small>
                            </div>
                            <div class="col-6 mb-3">
                                <div class="metric-value" id="win-loss-ratio">-</div>
                                <small>Win/Loss Ratio</small>
                            </div>
                            <div class="col-6">
                                <div class="metric-value" id="max-positions">-</div>
                                <small>Max Positions</small>
                            </div>
                            <div class="col-6">
                                <div class="metric-value" id="stop-loss">-</div>
                                <small>Stop Loss</small>
                            </div>
                        </div>
                        <div class="alert alert-warning mt-3 mb-0">
                            <strong>Direction:</strong> <span id="preferred-direction">-</span>
                        </div>
                        <div class="kelly-details mt-3" style="display: none;" id="kelly-details">
                            <small class="text-muted">
                                <strong>Kelly Formula:</strong> <span class="kelly-formula">f* = (p×b - q) / b</span><br>
                                <strong>Components:</strong> <span id="kelly-components">-</span>
                            </small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        {% if config.show_weekly_bias %}
        <!-- Weekly Bias Section -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title"><i class="fas fa-calendar-week"></i> Weekly Market Bias</h5>
                        <div class="row">
                            <div class="col-md-4">
                                <div class="text-center">
                                    <h3 id="weekly-direction" class="mb-0">-</h3>
                                    <small class="text-muted">Primary Direction</small>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="text-center">
                                    <h3 id="weekly-strength" class="mb-0">-</h3>
                                    <small class="text-muted">Strength</small>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="text-center">
                                    <h3 id="weekly-allocation" class="mb-0">-</h3>
                                    <small class="text-muted">Allocation %</small>
                                </div>
                            </div>
                        </div>
                        <div class="mt-3">
                            <div class="alert alert-light mb-0">
                                <strong>Rationale:</strong> <span id="weekly-rationale">-</span>
                            </div>
                        </div>
                        <div class="row mt-3">
                            <div class="col-md-6">
                                <small class="text-muted">Enhanced Market Score: <strong id="enhanced-score">-</strong></small>
                            </div>
                            <div class="col-md-6">
                                <small class="text-muted">Breadth Score: <strong id="breadth-score-display">-</strong></small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
        
        <!-- Index Analysis Section -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">📈 Index SMA20 Analysis</h5>
                        <div class="row text-center">
                            <div class="col-md-4">
                                <div class="card" style="border: 1px solid #dee2e6;">
                                    <div class="card-body">
                                        <h6>NIFTY 50</h6>
                                        <div id="nifty-position" style="font-size: 1.5em; font-weight: bold;">-</div>
                                        <small id="nifty-status">Loading...</small>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="card" style="border: 1px solid #dee2e6;">
                                    <div class="card-body">
                                        <h6>NIFTY MIDCAP 100</h6>
                                        <div id="midcap-position" style="font-size: 1.5em; font-weight: bold;">-</div>
                                        <small id="midcap-status">Loading...</small>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="card" style="border: 1px solid #dee2e6;">
                                    <div class="card-body">
                                        <h6>NIFTY SMALLCAP 100</h6>
                                        <div id="smallcap-position" style="font-size: 1.5em; font-weight: bold;">-</div>
                                        <small id="smallcap-status">Loading...</small>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="row mt-3">
                            <div class="col text-center">
                                <p class="mb-0"><strong>Index Trend:</strong> <span id="index-trend" style="font-weight: bold;">-</span></p>
                                <small id="index-analysis" class="text-muted">Loading analysis...</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Macro/Micro View Section -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card" style="background-color: #2c3e50; color: white;">
                    <div class="card-body">
                        <h5 class="card-title" style="color: white; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-bottom: 20px;">🌍 Market Regime: Macro vs Micro View</h5>
                        <div class="row">
                            <!-- Macro View -->
                            <div class="col-md-6">
                                <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 8px; height: 100%;">
                                    <h6 style="color: #3498db; margin-bottom: 15px;">🌐 MACRO VIEW (Index-Based)</h6>
                                    <div id="macro-status" style="font-size: 2em; font-weight: bold; margin: 10px 0;">Loading...</div>
                                    <p id="macro-recommendation" style="margin: 10px 0;">Analyzing indices...</p>
                                    <div id="macro-details" style="margin-top: 15px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 15px;">
                                        <!-- Index details will be populated here -->
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Micro View -->
                            <div class="col-md-6">
                                <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 8px; height: 100%;">
                                    <h6 style="color: #9b59b6; margin-bottom: 15px;">🔬 MICRO VIEW (Pattern-Based)</h6>
                                    <div id="micro-status" style="font-size: 2em; font-weight: bold; margin: 10px 0;">Loading...</div>
                                    <p id="micro-recommendation" style="margin: 10px 0;">Analyzing patterns...</p>
                                    <div id="micro-details" style="margin-top: 15px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 15px;">
                                        <!-- Pattern details will be populated here -->
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Action Summary -->
                        <div id="action-summary" style="margin-top: 20px; padding: 15px; background: rgba(255,255,255,0.1); border-radius: 8px; text-align: center; border: 2px solid #2ecc71;">
                            <div style="font-size: 1.3em; font-weight: bold; margin-bottom: 10px;">📈 Analyzing...</div>
                            <p style="margin: 0;">Please wait while we analyze market conditions...</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Metrics Section -->
        <div class="row mb-4">
            <div class="col-md-3 mb-3">
                <div class="metric-card">
                    <div class="metric-title">Market Score</div>
                    <div class="metric-value" id="market-score">-</div>
                    <div class="metric-delta" id="market-score-delta"></div>
                    <canvas id="market-score-sparkline" class="sparkline-container" width="200" height="50"></canvas>
                </div>
            </div>
            
            <div class="col-md-3 mb-3">
                <div class="metric-card">
                    <div class="metric-title">Trend Score</div>
                    <div class="metric-value" id="trend-score">-</div>
                    <div class="metric-delta" id="trend-score-delta"></div>
                    <canvas id="trend-score-sparkline" class="sparkline-container" width="200" height="50"></canvas>
                </div>
            </div>
            
            <div class="col-md-3 mb-3">
                <div class="metric-card">
                    <div class="metric-title">Volatility Score</div>
                    <div class="metric-value" id="volatility-score">-</div>
                    <div class="metric-subtitle" id="avg-atr" style="font-size: 0.8em; color: #7f8c8d; margin-top: -5px;">-</div>
                    <div class="metric-delta" id="volatility-score-delta"></div>
                    <canvas id="volatility-score-sparkline" class="sparkline-container" width="200" height="50"></canvas>
                </div>
            </div>
            
            <div class="col-md-3 mb-3">
                <div class="metric-card">
                    <div class="metric-title">Pattern Count</div>
                    <div class="metric-value" id="pattern-count">-</div>
                    <div class="text-muted">
                        L: <span id="long-count">-</span> | S: <span id="short-count">-</span>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Charts Section -->
        <div class="row mb-4">
            {% if config.show_regime_history %}
            <div class="col-md-6 mb-3">
                <div class="chart-container">
                    <h5>Regime History</h5>
                    <canvas id="regime-history-chart" height="150"></canvas>
                </div>
            </div>
            {% endif %}
            
            {% if config.show_confidence_trend %}
            <div class="col-md-6 mb-3">
                <div class="chart-container">
                    <h5>Confidence Trend</h5>
                    <canvas id="confidence-trend-chart" height="150"></canvas>
                </div>
            </div>
            {% endif %}
        </div>
        
        <!-- Historical Context -->
        <div class="row">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Historical Context</h5>
                        <div class="row" id="historical-stats">
                            <div class="col-md-3">
                                <strong>Current Regime Duration:</strong> <span id="regime-duration">-</span>
                            </div>
                            <div class="col-md-3">
                                <strong>24h Stability:</strong> <span id="stability-score">-</span>
                            </div>
                            <div class="col-md-3">
                                <strong>Model Accuracy:</strong> <span id="model-accuracy">-</span>
                            </div>
                            <div class="col-md-3">
                                <strong>Last Update:</strong> <span id="last-update">-</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- SMA Breadth Historical Analysis Section -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">📊 SMA Breadth Historical Analysis <small class="text-success" id="stocks-tracked">[Loading...]</small></h5>
                        
                        <!-- Separate Charts for SMA20 and SMA50 -->
                        <div class="row">
                            <div class="col-md-6">
                                <div class="chart-container" style="height: 500px; position: relative;">
                                    <h6 class="text-center mb-3">SMA20 Breadth History</h6>
                                    <canvas id="sma20-breadth-chart"></canvas>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="chart-container" style="height: 500px; position: relative;">
                                    <h6 class="text-center mb-3">SMA50 Breadth History</h6>
                                    <canvas id="sma50-breadth-chart"></canvas>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Volume Breadth Charts -->
                        <div class="row mt-4">
                            <div class="col-12">
                                <h6 class="text-center mb-3">Volume Breadth Analysis</h6>
                            </div>
                            <div class="col-md-6">
                                <div class="chart-container" style="height: 500px; position: relative;">
                                    <h6 class="text-center mb-3">Volume Breadth History</h6>
                                    <canvas id="volume-breadth-chart"></canvas>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="chart-container" style="height: 500px; position: relative;">
                                    <h6 class="text-center mb-3">Volume Participation Rate</h6>
                                    <canvas id="volume-participation-chart"></canvas>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Current Stats Row -->
                        <div class="row mt-3">
                            <div class="col-12">
                                <div class="sma-breadth-stats">
                                    <div class="row text-center">
                                        <div class="col-md-2">
                                            <strong>Current SMA20</strong>
                                            <div class="h5 text-primary"><span id="current-sma20-breadth">-</span>%</div>
                                        </div>
                                        <div class="col-md-2">
                                            <strong>Current SMA50</strong>
                                            <div class="h5 text-danger"><span id="current-sma50-breadth">-</span>%</div>
                                        </div>
                                        <div class="col-md-2">
                                            <strong>Market Regime</strong>
                                            <div id="current-market-regime" class="h5">-</div>
                                        </div>
                                        <div class="col-md-2">
                                            <strong>Market Score</strong>
                                            <div id="current-market-score" class="h5 text-secondary">-</div>
                                        </div>
                                        <div class="col-md-2">
                                            <strong>5-Day Trend</strong>
                                            <div id="sma-5day-trend" class="small">-</div>
                                        </div>
                                        <div class="col-md-2">
                                            <strong>20-Day Trend</strong>
                                            <div id="sma-20day-trend" class="small">-</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Breadth Levels Analysis -->
                        <div class="row mt-3">
                            <div class="col-md-6">
                                <div class="card bg-light">
                                    <div class="card-body">
                                        <h6 class="card-subtitle mb-2 text-muted">Breadth Zones</h6>
                                        <small>
                                            <div><span class="badge bg-success">Strong Bullish</span> SMA20 & SMA50 > 70%</div>
                                            <div><span class="badge bg-primary">Bullish</span> SMA20 & SMA50 > 60%</div>
                                            <div><span class="badge bg-secondary">Neutral</span> Between 30-60%</div>
                                            <div><span class="badge bg-warning">Bearish</span> SMA20 & SMA50 < 40%</div>
                                            <div><span class="badge bg-danger">Strong Bearish</span> SMA20 & SMA50 < 30%</div>
                                        </small>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card bg-light">
                                    <div class="card-body">
                                        <h6 class="card-subtitle mb-2 text-muted">Key Statistics</h6>
                                        <small>
                                            <div>Data Points: <span id="sma-data-points">-</span> days</div>
                                            <div>Date Range: <span id="sma-date-range">-</span></div>
                                            <div>Stocks Tracked: <span id="sma-stocks-tracked">-</span></div>
                                            <div>Last Update: <span id="sma-last-update">-</span></div>
                                        </small>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        {% if config.show_momentum_scanner %}
        <!-- Momentum Scanner Section -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">🚀 Momentum Scanner Analysis</h5>
                        
                        <!-- Current Momentum Stats -->
                        <div class="row mb-4">
                            <div class="col-md-4">
                                <div class="card bg-light">
                                    <div class="card-body text-center">
                                        <h6 class="text-muted">Market Momentum (WM)</h6>
                                        <div class="display-4" id="market-momentum-value">-</div>
                                        <div class="small">
                                            <span class="text-muted">Change: </span>
                                            <span id="momentum-change" class="fw-bold">-</span>
                                        </div>
                                        <div class="mt-2">
                                            <div id="momentum-regime" class="badge bg-secondary">Loading...</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="card bg-light">
                                    <div class="card-body text-center">
                                        <h6 class="text-muted">Daily Ticker Count</h6>
                                        <div class="display-4 text-primary" id="daily-ticker-count">-</div>
                                        <div class="small">
                                            <span class="text-muted">7-day Avg: </span>
                                            <span id="daily-ticker-avg" class="fw-bold">-</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="card bg-light">
                                    <div class="card-body text-center">
                                        <h6 class="text-muted">Weekly Ticker Count</h6>
                                        <div class="display-4 text-success" id="weekly-ticker-count">-</div>
                                        <div class="small">
                                            <span class="text-muted">7-day Avg: </span>
                                            <span id="weekly-ticker-avg" class="fw-bold">-</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Momentum Trend Chart -->
                        <div class="row mb-3">
                            <div class="col-12">
                                <h6 class="text-center mb-3">Momentum Trend (14 Days)</h6>
                                <div class="chart-container" style="height: 400px; position: relative;">
                                    <canvas id="momentum-trend-chart"></canvas>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Formula Reference -->
                        <div class="row">
                            <div class="col-12">
                                <div class="alert alert-info">
                                    <h6 class="alert-heading">📊 Momentum Formula</h6>
                                    <p class="mb-2"><strong>Formula:</strong> WM = (SMA20 - SMA50) / 2</p>
                                    <p class="mb-0"><strong>Current Market Breadth:</strong> SMA20: <span id="current-sma20">-</span>%, SMA50: <span id="current-sma50">-</span>%</p>
                                    <small class="text-muted">Market momentum based on breadth differential</small>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Market Interpretation -->
                        <div class="row mt-3">
                            <div class="col-12">
                                <div class="alert alert-secondary">
                                    <h6 class="alert-heading">📈 Market Analysis</h6>
                                    <p class="mb-0" id="momentum-interpretation">Loading analysis...</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
        
        <!-- Multi-Timeframe Analysis Section -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">📊 Multi-Timeframe Analysis</h5>
                        
                        <!-- Individual Timeframes -->
                        <div class="row mb-3">
                            <div class="col-md-3 mb-3">
                                <div class="card timeframe-card" id="daily-tf-card">
                                    <div class="card-body text-center">
                                        <h6 class="text-muted">DAILY</h6>
                                        <div class="tf-regime fw-bold mb-2" id="daily-regime">-</div>
                                        <div class="small">
                                            <div>L/S: <span id="daily-ls">-</span></div>
                                            <div>Ratio: <span id="daily-ratio">-</span></div>
                                            <div>Conf: <span id="daily-conf">-</span></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="col-md-3 mb-3">
                                <div class="card timeframe-card" id="weekly-tf-card">
                                    <div class="card-body text-center">
                                        <h6 class="text-muted">WEEKLY</h6>
                                        <div class="tf-regime fw-bold mb-2" id="weekly-regime">-</div>
                                        <div class="small">
                                            <div>L/S: <span id="weekly-ls">-</span></div>
                                            <div>Ratio: <span id="weekly-ratio">-</span></div>
                                            <div>Conf: <span id="weekly-conf">-</span></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="col-md-3 mb-3">
                                <div class="card timeframe-card" id="biweekly-tf-card">
                                    <div class="card-body text-center">
                                        <h6 class="text-muted">BI-WEEKLY</h6>
                                        <div class="tf-regime fw-bold mb-2" id="biweekly-regime">-</div>
                                        <div class="small">
                                            <div>L/S: <span id="biweekly-ls">-</span></div>
                                            <div>Ratio: <span id="biweekly-ratio">-</span></div>
                                            <div>Conf: <span id="biweekly-conf">-</span></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="col-md-3 mb-3">
                                <div class="card timeframe-card" id="monthly-tf-card">
                                    <div class="card-body text-center">
                                        <h6 class="text-muted">MONTHLY</h6>
                                        <div class="tf-regime fw-bold mb-2" id="monthly-regime">-</div>
                                        <div class="small">
                                            <div>L/S: <span id="monthly-ls">-</span></div>
                                            <div>Ratio: <span id="monthly-ratio">-</span></div>
                                            <div>Conf: <span id="monthly-conf">-</span></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Combined Analysis -->
                        <div class="alert alert-info">
                            <div class="row align-items-center">
                                <div class="col-md-4 text-center">
                                    <h4 class="mb-0">Alignment: <span id="mtf-alignment" class="fw-bold">-</span></h4>
                                    <small id="mtf-alignment-status">-</small>
                                </div>
                                <div class="col-md-4 text-center">
                                    <h4 class="mb-0">Combined: <span id="mtf-combined-regime" class="fw-bold">-</span></h4>
                                    <small>Confidence: <span id="mtf-confidence">-</span></small>
                                </div>
                                <div class="col-md-4">
                                    <strong>Recommendation:</strong>
                                    <div id="mtf-recommendation" class="mt-1">-</div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Divergence Alert (if any) -->
                        <div id="mtf-divergence-alert" class="alert alert-warning d-none">
                            <strong>⚠️ Timeframe Divergences Detected:</strong>
                            <div id="mtf-divergences"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Reversal Patterns Section -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">📈 Reversal Patterns - Top 10</h5>
                        
                        <div class="row">
                            <!-- Long Reversals -->
                            <div class="col-md-6 mb-3">
                                <div class="card" style="border: 2px solid #2ecc71; background: rgba(46, 204, 113, 0.05);">
                                    <div class="card-body">
                                        <h6 class="text-center" style="color: #27ae60;">
                                            <i class="fas fa-chart-line"></i> Long Reversals
                                            <small id="long-reversal-time" class="text-muted ms-2">-</small>
                                        </h6>
                                        <div id="long-reversal-list" style="max-height: 400px; overflow-y: auto;">
                                            <div class="text-center text-muted py-3">Loading...</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Short Reversals -->
                            <div class="col-md-6 mb-3">
                                <div class="card" style="border: 2px solid #e74c3c; background: rgba(231, 76, 60, 0.05);">
                                    <div class="card-body">
                                        <h6 class="text-center" style="color: #c0392b;">
                                            <i class="fas fa-chart-line fa-flip-vertical"></i> Short Reversals
                                            <small id="short-reversal-time" class="text-muted ms-2">-</small>
                                        </h6>
                                        <div id="short-reversal-list" style="max-height: 400px; overflow-y: auto;">
                                            <div class="text-center text-muted py-3">Loading...</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <!-- Chart.js Date Adapter for time scale -->
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    
    <script>
        // Dashboard configuration from backend
        const dashboardConfig = {{ config | tojson }};
        
        // Test if JavaScript is executing
        console.log('Dashboard JavaScript loaded at', new Date().toISOString());
        document.addEventListener('DOMContentLoaded', function() {
            console.log('DOM Content Loaded');
        });
        window.addEventListener('load', function() {
            console.log('Window fully loaded');
        });
        
        // Chart configurations
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true }
            }
        };
        
        // Initialize charts
        // Initialize Regime History Chart only if enabled
        let regimeHistoryChart = null;
        if (dashboardConfig.show_regime_history) {
            const regimeHistoryCanvas = document.getElementById('regime-history-chart');
            if (regimeHistoryCanvas) {
                regimeHistoryChart = new Chart(regimeHistoryCanvas, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    backgroundColor: []
                }]
            },
            options: chartOptions
                });
            }
        }
        
        // Initialize Confidence Trend Chart only if enabled
        let confidenceTrendChart = null;
        if (dashboardConfig.show_confidence_trend) {
            const confidenceTrendCanvas = document.getElementById('confidence-trend-chart');
            if (confidenceTrendCanvas) {
                confidenceTrendChart = new Chart(confidenceTrendCanvas, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    borderColor: '#17a2b8',
                    fill: false
                }]
            },
            options: chartOptions
                });
            }
        }
        
        // Initialize Momentum Trend Chart only if enabled
        let momentumTrendChart = null;
        if (dashboardConfig.show_momentum_scanner) {
            const momentumCanvas = document.getElementById('momentum-trend-chart');
            if (momentumCanvas) {
            window.momentumTrendChart = new Chart(momentumCanvas, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Market Momentum (WM)',
                        data: [],
                        borderColor: '#ff6b6b',
                        backgroundColor: 'rgba(255, 107, 107, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4,
                        yAxisID: 'y1'
                    }, {
                        label: 'Daily Ticker Count',
                        data: [],
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4,
                        yAxisID: 'y2'
                    }, {
                        label: 'Weekly Ticker Count',
                        data: [],
                        borderColor: '#28a745',
                        backgroundColor: 'rgba(40, 167, 69, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4,
                        yAxisID: 'y2'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { 
                            display: true,
                            position: 'top'
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': ' + context.parsed.y + ' stocks';
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: 'Date'
                            }
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: {
                                display: true,
                                text: 'Market Momentum (WM)'
                            },
                            grid: {
                                drawOnChartArea: false
                            }
                        },
                        y2: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Ticker Count'
                            }
                        }
                    }
                }
            });
            momentumTrendChart = window.momentumTrendChart;
            }
        }
        
        // Initialize SMA breadth charts - TEMPORARILY DISABLED
        /*
        const sma20Canvas = document.getElementById('sma20-breadth-chart');
        const sma50Canvas = document.getElementById('sma50-breadth-chart');
        
        if (sma20Canvas) {
            window.sma20BreadthChart = new Chart(sma20Canvas, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'SMA20 Breadth %',
                    data: [],
                    borderColor: '#28a745',
                    backgroundColor: 'rgba(40, 167, 69, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return 'Above SMA20: ' + context.parsed.y.toFixed(1) + '%';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'day',
                            round: 'day',
                            displayFormats: {
                                day: 'MMM DD',
                                week: 'MMM DD',
                                month: 'MMM YYYY'
                            }
                        },
                        title: {
                            display: true,
                            text: 'Date'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                }
            }
        });
        }
        
        if (sma50Canvas) {
            window.sma50BreadthChart = new Chart(sma50Canvas, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'SMA50 Breadth %',
                    data: [],
                    borderColor: '#17a2b8',
                    backgroundColor: 'rgba(23, 162, 184, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return 'Above SMA50: ' + context.parsed.y.toFixed(1) + '%';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'day',
                            round: 'day',
                            displayFormats: {
                                day: 'MMM DD',
                                week: 'MMM DD',
                                month: 'MMM YYYY'
                            }
                        },
                        title: {
                            display: true,
                            text: 'Date'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                }
            }
        });
        }
        */
        
        // SMA Breadth Chart Variables
        let sma20BreadthChart = null;
        let sma50BreadthChart = null;
        let volumeBreadthChart = null;
        let volumeParticipationChart = null;
        
        // Initialize SMA Breadth Charts
        function initializeSMABreadthChart() {
            // Initialize SMA20 Chart
            const ctx20 = document.getElementById('sma20-breadth-chart');
            if (!ctx20) {
                console.error('SMA20 Breadth canvas element not found');
                return;
            }
            
            sma20BreadthChart = new Chart(ctx20, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'SMA20 Breadth %',
                        data: [],
                        borderColor: 'rgb(54, 162, 235)',
                        backgroundColor: 'rgba(54, 162, 235, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.1,
                        pointRadius: 2,
                        pointHoverRadius: 6,
                        pointBackgroundColor: 'rgb(54, 162, 235)',
                        pointBorderColor: 'rgb(54, 162, 235)'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: { display: false },
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return 'Above SMA20: ' + context.parsed.y.toFixed(1) + '%';
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            title: { display: true, text: 'Date' },
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45,
                                autoSkip: true,
                                maxTicksLimit: 30,
                                font: {
                                    size: 10
                                }
                            }
                        },
                        y: {
                            display: true,
                            title: { display: true, text: 'Breadth %' },
                            min: 0,
                            max: 100,
                            ticks: {
                                callback: function(value) {
                                    return value + '%';
                                }
                            },
                            grid: {
                                color: function(context) {
                                    if (context.tick.value === 30) return 'rgba(255, 0, 0, 0.3)';
                                    if (context.tick.value === 50) return 'rgba(128, 128, 128, 0.3)';
                                    if (context.tick.value === 70) return 'rgba(0, 255, 0, 0.3)';
                                    return 'rgba(0, 0, 0, 0.1)';
                                }
                            }
                        }
                    }
                }
            });
            
            // Initialize SMA50 Chart
            const ctx50 = document.getElementById('sma50-breadth-chart');
            if (!ctx50) {
                console.error('SMA50 Breadth canvas element not found');
                return;
            }
            
            sma50BreadthChart = new Chart(ctx50, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'SMA50 Breadth %',
                        data: [],
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.1,
                        pointRadius: 2,
                        pointHoverRadius: 6,
                        pointBackgroundColor: 'rgb(255, 99, 132)',
                        pointBorderColor: 'rgb(255, 99, 132)'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: { display: false },
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return 'Above SMA50: ' + context.parsed.y.toFixed(1) + '%';
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            title: { display: true, text: 'Date' },
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45,
                                autoSkip: true,
                                maxTicksLimit: 30,
                                font: {
                                    size: 10
                                }
                            }
                        },
                        y: {
                            display: true,
                            title: { display: true, text: 'Breadth %' },
                            min: 0,
                            max: 100,
                            ticks: {
                                callback: function(value) {
                                    return value + '%';
                                }
                            },
                            grid: {
                                color: function(context) {
                                    if (context.tick.value === 30) return 'rgba(255, 0, 0, 0.3)';
                                    if (context.tick.value === 50) return 'rgba(128, 128, 128, 0.3)';
                                    if (context.tick.value === 70) return 'rgba(0, 255, 0, 0.3)';
                                    return 'rgba(0, 0, 0, 0.1)';
                                }
                            }
                        }
                    }
                }
            });
            
            // Initialize Volume Breadth Chart
            const ctxVolume = document.getElementById('volume-breadth-chart');
            if (ctxVolume) {
                volumeBreadthChart = new Chart(ctxVolume, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'Volume Breadth %',
                            data: [],
                            borderColor: 'rgb(75, 192, 192)',
                            backgroundColor: 'rgba(75, 192, 192, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.1,
                            pointRadius: 2,
                            pointHoverRadius: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: { display: false },
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        return 'Above Avg Volume: ' + context.parsed.y.toFixed(1) + '%';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                display: true,
                                title: { display: true, text: 'Date' },
                                ticks: {
                                    maxRotation: 45,
                                    minRotation: 45,
                                    autoSkip: true,
                                    maxTicksLimit: 30,
                                    font: { size: 10 }
                                }
                            },
                            y: {
                                display: true,
                                title: { display: true, text: 'Volume Breadth %' },
                                min: 0,
                                max: 100,
                                ticks: {
                                    callback: function(value) {
                                        return value + '%';
                                    }
                                }
                            }
                        }
                    }
                });
            }
            
            // Initialize Volume Participation Chart
            const ctxParticipation = document.getElementById('volume-participation-chart');
            if (ctxParticipation) {
                volumeParticipationChart = new Chart(ctxParticipation, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'Volume Participation',
                            data: [],
                            borderColor: 'rgb(153, 102, 255)',
                            backgroundColor: 'rgba(153, 102, 255, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.1,
                            pointRadius: 2,
                            pointHoverRadius: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            title: { display: false },
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        return 'Participation: ' + context.parsed.y.toFixed(1) + '%';
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                display: true,
                                title: { display: true, text: 'Date' },
                                ticks: {
                                    maxRotation: 45,
                                    minRotation: 45,
                                    autoSkip: true,
                                    maxTicksLimit: 30,
                                    font: { size: 10 }
                                }
                            },
                            y: {
                                display: true,
                                title: { display: true, text: 'Participation Rate (%)' },
                                min: 0,
                                max: 100,
                                ticks: {
                                    callback: function(value) {
                                        return value.toFixed(0) + '%';
                                    }
                                }
                            }
                        }
                    }
                });
            }
        }
        
        // Update SMA Breadth Charts
        function updateSMABreadthChart(data) {
            if (!sma20BreadthChart || !sma50BreadthChart) {
                console.error('SMA Breadth charts not initialized');
                return;
            }
            
            try {
                // Update SMA20 chart
                sma20BreadthChart.data.labels = data.labels;
                sma20BreadthChart.data.datasets[0].data = data.sma20_values;
                sma20BreadthChart.update();
                
                // Update SMA50 chart  
                sma50BreadthChart.data.labels = data.labels;
                sma50BreadthChart.data.datasets[0].data = data.sma50_values;
                sma50BreadthChart.update();
                
                // Update current stats with null checks
                const sma20Element = document.getElementById('current-sma20-breadth');
                if (sma20Element) sma20Element.textContent = data.current_sma20.toFixed(1);
                
                const sma50Element = document.getElementById('current-sma50-breadth');
                if (sma50Element) sma50Element.textContent = data.current_sma50.toFixed(1);
                
                const regimeTextElement = document.getElementById('current-market-regime');
                if (regimeTextElement) regimeTextElement.textContent = data.market_regime;
                
                const scoreElement = document.getElementById('current-market-score');
                if (scoreElement) scoreElement.textContent = data.market_score ? data.market_score.toFixed(3) : '-';
                
                // Update trends with arrows
                const sma20Trend = data.sma20_5d_change > 0 ? '↑' : '↓';
                const sma50Trend = data.sma50_5d_change > 0 ? '↑' : '↓';
                const trend5d = `SMA20: ${sma20Trend} ${Math.abs(data.sma20_5d_change).toFixed(1)}%<br>SMA50: ${sma50Trend} ${Math.abs(data.sma50_5d_change).toFixed(1)}%`;
                
                const sma20Trend20d = data.sma20_20d_change > 0 ? '↑' : '↓';
                const sma50Trend20d = data.sma50_20d_change > 0 ? '↑' : '↓';
                const trend20d = `SMA20: ${sma20Trend20d} ${Math.abs(data.sma20_20d_change).toFixed(1)}%<br>SMA50: ${sma50Trend20d} ${Math.abs(data.sma50_20d_change).toFixed(1)}%`;
                
                const trend5dElement = document.getElementById('sma-5day-trend');
                if (trend5dElement) trend5dElement.innerHTML = trend5d;
                
                const trend20dElement = document.getElementById('sma-20day-trend');
                if (trend20dElement) trend20dElement.innerHTML = trend20d;
                
                // Update statistics with null checks
                const dataPointsElement = document.getElementById('sma-data-points');
                if (dataPointsElement) dataPointsElement.textContent = data.data_points;
                
                const dateRangeElement = document.getElementById('sma-date-range');
                if (dateRangeElement) dateRangeElement.textContent = data.date_range;
                
                const stocksTrackedElement = document.getElementById('sma-stocks-tracked');
                if (stocksTrackedElement) stocksTrackedElement.textContent = data.total_stocks;
                
                const lastUpdateElement = document.getElementById('sma-last-update');
                if (lastUpdateElement) lastUpdateElement.textContent = new Date().toLocaleTimeString();
                
                // Color code regime
                const regimeElement = document.getElementById('current-market-regime');
                if (regimeElement) {
                    regimeElement.className = 'h5';
                    if (data.market_regime.includes('Strong Uptrend')) {
                        regimeElement.classList.add('text-success');
                    } else if (data.market_regime.includes('Uptrend')) {
                        regimeElement.classList.add('text-primary');
                    } else if (data.market_regime.includes('Strong Downtrend')) {
                        regimeElement.classList.add('text-danger');
                    } else if (data.market_regime.includes('Downtrend')) {
                        regimeElement.classList.add('text-warning');
                    } else {
                        regimeElement.classList.add('text-secondary');
                    }
                }
                
                // Update volume breadth charts if they exist
                if (volumeBreadthChart && data.volume_breadth_values) {
                    volumeBreadthChart.data.labels = data.labels;
                    volumeBreadthChart.data.datasets[0].data = data.volume_breadth_values;
                    volumeBreadthChart.update();
                    
                    // Update current volume breadth stat
                    if (data.current_volume_breadth !== undefined) {
                        const volumeBreadthElement = document.getElementById('current-volume-breadth');
                        if (volumeBreadthElement) {
                            volumeBreadthElement.textContent = data.current_volume_breadth.toFixed(1);
                        }
                    }
                }
                
                if (volumeParticipationChart && data.volume_participation_values) {
                    console.log('Volume Participation Data:', data.volume_participation_values);
                    console.log('Labels:', data.labels);
                    volumeParticipationChart.data.labels = data.labels;
                    volumeParticipationChart.data.datasets[0].data = data.volume_participation_values;
                    volumeParticipationChart.update();
                } else {
                    console.log('Volume Participation Chart issue - Chart exists:', !!volumeParticipationChart, 'Data exists:', !!data.volume_participation_values);
                }
                
            } catch (error) {
                console.error('Error updating SMA breadth chart:', error);
            }
        }
        
        // Fetch SMA Breadth Data
        function fetchSMABreadthData() {
            fetch('/api/sma-breadth-historical')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error('Error fetching SMA breadth data:', data.error);
                        return;
                    }
                    updateSMABreadthChart(data);
                    
                    // Update stock count from data
                    if (data.total_stocks) {
                        document.getElementById('stocks-tracked').textContent = `[${data.total_stocks} stocks tracked]`;
                    }
                })
                .catch(error => {
                    console.error('Error fetching SMA breadth data:', error);
                });
        }
        
        let previousData = null;
        
        function updateDashboard() {
            console.log('Fetching current analysis...');
            fetch('/api/current_analysis')
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('Received data:', data);
                    if (data.error) {
                        console.error('API error:', data.error);
                        return;
                    }
                    
                    // Update regime display
                    const regimeBadge = document.getElementById('regime-badge');
                    if (regimeBadge) {
                        regimeBadge.className = 'regime-badge ' + data.regime;
                        regimeBadge.innerHTML = data.regime.replace('_', ' ').toUpperCase();
                    }
                    
                    // Update confidence and ratio
                    const confDisplay = document.getElementById('confidence-display');
                    if (confDisplay) {
                        confDisplay.textContent = (data.confidence * 100).toFixed(1) + '%';
                    }
                    
                    const ratioDisplay = document.getElementById('ratio-display');
                    if (ratioDisplay) {
                        ratioDisplay.textContent = data.ratio === 'inf' ? '∞' : data.ratio.toFixed(2);
                    }
                    
                    // Update proximity marker
                    const marketScore = data.indicators.market_score || 0;
                    const position = ((marketScore + 1) / 2) * 100;
                    document.getElementById('proximity-marker').style.left = position + '%';
                    
                    // Update strategy
                    document.getElementById('strategy-text').textContent = data.strategy;
                    
                    // Update Kelly Criterion recommendations
                    if (data.position_recommendations) {
                        const recs = data.position_recommendations;
                        console.log('Position Recommendations:', recs);  // Debug log
                        
                        // Check if we have Kelly data or old format
                        const hasKellyData = recs.hasOwnProperty('kelly_fraction');
                        
                        // Kelly metrics with null checks
                        const kellyPercent = recs.position_size_percent || 0;
                        document.getElementById('kelly-fraction').textContent = kellyPercent.toFixed(2) + '%';
                        document.getElementById('kelly-fraction').style.color = (recs.kelly_fraction || 0) > 0.15 ? '#27ae60' : 
                                                                               (recs.kelly_fraction || 0) > 0.05 ? '#f39c12' : '#e74c3c';
                        
                        // Expected value with color coding
                        const ev = recs.expected_value || 0;
                        const evText = isNaN(ev) ? '0.0%' : (ev > 0 ? '+' : '') + (ev * 100).toFixed(1) + '%';
                        document.getElementById('expected-value').textContent = evText;
                        document.getElementById('expected-value').style.color = ev > 0 ? '#27ae60' : '#e74c3c';
                        
                        // Win probability
                        const winProb = recs.win_probability || 0.5;
                        document.getElementById('win-probability').textContent = (winProb * 100).toFixed(1) + '%';
                        document.getElementById('win-probability').style.color = winProb > 0.6 ? '#27ae60' : 
                                                                                winProb > 0.5 ? '#f39c12' : '#e74c3c';
                        
                        // Win/Loss ratio
                        const wlRatio = recs.win_loss_ratio || 1.0;
                        document.getElementById('win-loss-ratio').textContent = wlRatio.toFixed(2) + ':1';
                        
                        // Traditional metrics (handle both formats)
                        document.getElementById('max-positions').textContent = recs.max_positions || 0;
                        const stopLoss = recs.stop_loss_percent || (recs.stop_loss_multiplier ? (recs.stop_loss_multiplier * 2).toFixed(1) : 2.0);
                        document.getElementById('stop-loss').textContent = typeof stopLoss === 'number' ? stopLoss.toFixed(1) + '%' : stopLoss;
                        document.getElementById('preferred-direction').textContent = (recs.preferred_direction || 'none').toUpperCase();
                        
                        // Update guidance section if present
                        if (recs.specific_guidance && recs.specific_guidance.length > 0) {
                            const strategyText = document.getElementById('strategy-text');
                            if (strategyText) {
                                strategyText.innerHTML = data.strategy + '<br><small>' + recs.specific_guidance[0] + '</small>';
                            }
                        }
                        
                        // Update Kelly details
                        if (recs.kelly_components) {
                            const kellyDetails = document.getElementById('kelly-details');
                            const kellyComponents = document.getElementById('kelly-components');
                            if (kellyDetails && kellyComponents) {
                                kellyComponents.innerHTML = `Raw: ${(recs.kelly_components.raw_kelly * 100).toFixed(2)}%, ` +
                                                          `Safety: ${recs.kelly_components.safety_factor}, ` +
                                                          `Limit: ${(recs.kelly_components.regime_limit * 100).toFixed(0)}%`;
                                kellyDetails.style.display = recs.kelly_fraction > 0 ? 'block' : 'none';
                            }
                        }
                    }
                    
                    // Update metrics
                    updateMetric('market-score', marketScore, previousData?.indicators?.market_score);
                    updateMetric('trend-score', data.indicators.trend_score, previousData?.indicators?.trend_score);
                    updateMetric('volatility-score', data.indicators.volatility_score, 
                               previousData?.indicators?.volatility_score);
                    
                    // Update average ATR subtitle
                    const avgAtrElement = document.getElementById('avg-atr');
                    if (avgAtrElement && data.volatility && data.volatility.avg_atr) {
                        avgAtrElement.textContent = `Avg ATR: ${data.volatility.avg_atr.toFixed(2)}%`;
                    }
                    
                    // Update weekly bias section
                    if (data.weekly_bias && dashboardConfig.show_weekly_bias) {
                        const bias = data.weekly_bias;
                        const weeklyDirection = document.getElementById('weekly-direction');
                        const weeklyStrength = document.getElementById('weekly-strength');
                        const weeklyAllocation = document.getElementById('weekly-allocation');
                        const weeklyRationale = document.getElementById('weekly-rationale');
                        
                        if (weeklyDirection) {
                            weeklyDirection.textContent = bias.direction;
                            weeklyDirection.className = 
                                bias.direction === 'LONG' ? 'mb-0 text-success' : 
                                bias.direction === 'SHORT' ? 'mb-0 text-danger' : 'mb-0 text-warning';
                        }
                        if (weeklyStrength) weeklyStrength.textContent = bias.strength;
                        if (weeklyAllocation) weeklyAllocation.textContent = bias.allocation + '%';
                        if (weeklyRationale) weeklyRationale.textContent = bias.rationale;
                    }
                    
                    // Update enhanced scores
                    if (data.indicators.market_score !== undefined) {
                        const enhancedScoreEl = document.getElementById('enhanced-score');
                        if (enhancedScoreEl) {
                            enhancedScoreEl.textContent = data.indicators.market_score.toFixed(3);
                        }
                    }
                    if (data.indicators.breadth_score !== undefined) {
                        const breadthScoreEl = document.getElementById('breadth-score-display');
                        if (breadthScoreEl) {
                            breadthScoreEl.textContent = data.indicators.breadth_score.toFixed(3);
                        }
                    }
                    
                    // Update pattern counts
                    document.getElementById('pattern-count').textContent = data.counts.total;
                    document.getElementById('long-count').textContent = data.counts.long;
                    document.getElementById('short-count').textContent = data.counts.short;
                    
                    // Update index analysis
                    if (data.index_analysis) {
                        const idx = data.index_analysis;
                        
                        // Update NIFTY 50
                        if (idx.index_details && idx.index_details['NIFTY 50']) {
                            const nifty = idx.index_details['NIFTY 50'];
                            document.getElementById('nifty-position').textContent = 
                                nifty.sma_position_pct.toFixed(1) + '%';
                            document.getElementById('nifty-position').style.color = 
                                nifty.above_sma20 ? '#27ae60' : '#e74c3c';
                            document.getElementById('nifty-status').textContent = 
                                nifty.above_sma20 ? 'Above SMA20' : 'Below SMA20';
                        }
                        
                        // Update MIDCAP
                        if (idx.index_details && idx.index_details['NIFTY MIDCAP 100']) {
                            const midcap = idx.index_details['NIFTY MIDCAP 100'];
                            document.getElementById('midcap-position').textContent = 
                                midcap.sma_position_pct.toFixed(1) + '%';
                            document.getElementById('midcap-position').style.color = 
                                midcap.above_sma20 ? '#27ae60' : '#e74c3c';
                            document.getElementById('midcap-status').textContent = 
                                midcap.above_sma20 ? 'Above SMA20' : 'Below SMA20';
                        }
                        
                        // Update SMALLCAP
                        if (idx.index_details && idx.index_details['NIFTY SMLCAP 100']) {
                            const smallcap = idx.index_details['NIFTY SMLCAP 100'];
                            document.getElementById('smallcap-position').textContent = 
                                smallcap.sma_position_pct.toFixed(1) + '%';
                            document.getElementById('smallcap-position').style.color = 
                                smallcap.above_sma20 ? '#27ae60' : '#e74c3c';
                            document.getElementById('smallcap-status').textContent = 
                                smallcap.above_sma20 ? 'Above SMA20' : 'Below SMA20';
                        }
                        
                        // Update overall trend
                        document.getElementById('index-trend').textContent = 
                            idx.trend.replace('_', ' ').toUpperCase();
                        document.getElementById('index-trend').style.color = 
                            idx.trend.includes('bullish') ? '#27ae60' : 
                            idx.trend.includes('bearish') ? '#e74c3c' : '#95a5a6';
                        document.getElementById('index-analysis').textContent = idx.analysis;
                    }
                    
                    // Update historical context
                    if (data.historical_context) {
                        const ctx = data.historical_context;
                        const regimeDurationEl = document.getElementById('regime-duration');
                        const stabilityScoreEl = document.getElementById('stability-score');
                        
                        if (regimeDurationEl) {
                            regimeDurationEl.textContent = ctx.regime_duration_hours.toFixed(1) + ' hours';
                        }
                        if (stabilityScoreEl) {
                            stabilityScoreEl.textContent = (ctx.stability_24h * 100).toFixed(0) + '%';
                        }
                    }
                    
                    if (data.model_performance) {
                        document.getElementById('model-accuracy').textContent = 
                            (data.model_performance.accuracy * 100).toFixed(1) + '%';
                    }
                    
                    document.getElementById('last-update').textContent = 
                        new Date(data.timestamp).toLocaleTimeString();
                    
                    // Update charts
                    updateCharts(data);
                    
                    // Update SMA breadth charts - TEMPORARILY DISABLED
                    // updateSMABreadthCharts();
                    
                    // Draw sparklines
                    drawSparklines(data);
                    
                    // Update Macro/Micro View
                    updateMacroMicroView(data);
                    
                    // Update Multi-Timeframe Analysis
                    updateMultiTimeframeAnalysis(data);
                    
                    previousData = data;
                })
                .catch(error => console.error('Error fetching data:', error));
            
            // Update Reversal Patterns data
            updateReversalPatterns();
        }
        
        function updateGPatternData() {
            fetch('/api/g_pattern_data')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error('Error fetching G Pattern data:', data.error);
                        return;
                    }
                    
                    // Update confirmed patterns
                    document.getElementById('g-pattern-confirmed-count').textContent = data.counts.confirmed;
                    const confirmedList = document.getElementById('g-pattern-confirmed-list');
                    if (data.categories.confirmed.length > 0) {
                        confirmedList.innerHTML = data.categories.confirmed.slice(0, 5).map(stock => 
                            `<div>• ${stock.ticker} (Score: ${stock.score})</div>`
                        ).join('');
                        if (data.categories.confirmed.length > 5) {
                            confirmedList.innerHTML += `<div class="text-muted">+${data.categories.confirmed.length - 5} more...</div>`;
                        }
                    } else {
                        confirmedList.innerHTML = '<div class="text-muted">No confirmed patterns</div>';
                    }
                    
                    // Update emerging patterns
                    document.getElementById('g-pattern-emerging-count').textContent = data.counts.emerging;
                    const emergingList = document.getElementById('g-pattern-emerging-list');
                    if (data.categories.emerging.length > 0) {
                        emergingList.innerHTML = data.categories.emerging.slice(0, 5).map(stock => 
                            `<div>• ${stock.ticker} (Score: ${stock.score})</div>`
                        ).join('');
                        if (data.categories.emerging.length > 5) {
                            emergingList.innerHTML += `<div class="text-muted">+${data.categories.emerging.length - 5} more...</div>`;
                        }
                    } else {
                        emergingList.innerHTML = '<div class="text-muted">No emerging patterns</div>';
                    }
                    
                    // Update developing patterns
                    document.getElementById('g-pattern-developing-count').textContent = data.counts.developing;
                    const developingList = document.getElementById('g-pattern-developing-list');
                    if (data.categories.developing.length > 0) {
                        developingList.innerHTML = data.categories.developing.slice(0, 5).map(stock => 
                            `<div>• ${stock.ticker} (Score: ${stock.score})</div>`
                        ).join('');
                        if (data.categories.developing.length > 5) {
                            developingList.innerHTML += `<div class="text-muted">+${data.categories.developing.length - 5} more...</div>`;
                        }
                    } else {
                        developingList.innerHTML = '<div class="text-muted">No developing patterns</div>';
                    }
                    
                    // Update stats
                    const totalTracked = data.counts.confirmed + data.counts.developing + 
                                       data.counts.emerging + data.counts.watch_closely + data.counts.watch_only;
                    document.getElementById('g-pattern-total-tracked').textContent = totalTracked;
                    document.getElementById('g-pattern-watch-closely').textContent = data.counts.watch_closely;
                    document.getElementById('g-pattern-watch-only').textContent = data.counts.watch_only;
                    document.getElementById('g-pattern-last-update').textContent = data.generated_time || '-';
                    
                    // Update opportunities count
                    const opportunities = data.counts.confirmed + data.counts.developing + data.counts.emerging;
                    document.getElementById('g-pattern-opportunities').textContent = 
                        `${opportunities} stocks (${data.counts.confirmed} confirmed, ${data.counts.developing + data.counts.emerging} developing/emerging)`;
                })
                .catch(error => console.error('Error fetching G Pattern data:', error));
        }
        
        function updateReversalPatterns() {
            fetch('/api/reversal_patterns')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error('Error fetching reversal patterns:', data.error);
                        return;
                    }
                    
                    // Update Long Reversals
                    const longList = document.getElementById('long-reversal-list');
                    if (data.long_reversals && data.long_reversals.length > 0) {
                        let longHtml = '<div class="table-responsive"><table class="table table-sm table-hover">';
                        longHtml += '<thead><tr><th>#</th><th>Ticker</th><th>Score</th><th>Entry</th><th>SL</th><th>Target</th></tr></thead>';
                        longHtml += '<tbody>';
                        
                        data.long_reversals.forEach((stock, index) => {
                            const riskReward = ((stock.Target1 - stock.Entry_Price) / (stock.Entry_Price - stock.Stop_Loss)).toFixed(2);
                            longHtml += `<tr>
                                <td>${index + 1}</td>
                                <td><strong>${stock.Ticker}</strong></td>
                                <td><span class="badge bg-success">${stock.Score}</span></td>
                                <td>₹${stock.Entry_Price}</td>
                                <td class="text-danger">₹${stock.Stop_Loss}</td>
                                <td class="text-success">₹${stock.Target1}</td>
                            </tr>`;
                        });
                        
                        longHtml += '</tbody></table></div>';
                        longList.innerHTML = longHtml;
                    } else {
                        longList.innerHTML = '<div class="text-center text-muted py-3">No long reversal patterns found</div>';
                    }
                    
                    // Update Short Reversals
                    const shortList = document.getElementById('short-reversal-list');
                    if (data.short_reversals && data.short_reversals.length > 0) {
                        let shortHtml = '<div class="table-responsive"><table class="table table-sm table-hover">';
                        shortHtml += '<thead><tr><th>#</th><th>Ticker</th><th>Score</th><th>Entry</th><th>SL</th><th>Target</th></tr></thead>';
                        shortHtml += '<tbody>';
                        
                        data.short_reversals.forEach((stock, index) => {
                            const riskReward = ((stock.Entry_Price - stock.Target1) / (stock.Stop_Loss - stock.Entry_Price)).toFixed(2);
                            shortHtml += `<tr>
                                <td>${index + 1}</td>
                                <td><strong>${stock.Ticker}</strong></td>
                                <td><span class="badge bg-danger">${stock.Score}</span></td>
                                <td>₹${stock.Entry_Price}</td>
                                <td class="text-danger">₹${stock.Stop_Loss}</td>
                                <td class="text-success">₹${stock.Target1}</td>
                            </tr>`;
                        });
                        
                        shortHtml += '</tbody></table></div>';
                        shortList.innerHTML = shortHtml;
                    } else {
                        shortList.innerHTML = '<div class="text-center text-muted py-3">No short reversal patterns found</div>';
                    }
                    
                    // Update timestamps
                    if (data.long_file_time) {
                        document.getElementById('long-reversal-time').textContent = `Updated: ${data.long_file_time}`;
                    }
                    if (data.short_file_time) {
                        document.getElementById('short-reversal-time').textContent = `Updated: ${data.short_file_time}`;
                    }
                })
                .catch(error => console.error('Error fetching reversal patterns:', error));
        }
        
        function updateMacroMicroView(data) {
            // Update Macro View (Index-based)
            if (data.index_analysis) {
                const idx = data.index_analysis;
                const indicesAbove = idx.indices_above_sma20 || 0;
                const totalIndices = idx.total_indices || 3;
                
                let macroStatus, macroColor, macroRecommendation;
                
                if (indicesAbove === totalIndices) {
                    macroStatus = 'BULLISH';
                    macroColor = '#2ecc71';
                    macroRecommendation = 'All indices above SMA20 - Scale into positions';
                } else if (indicesAbove >= 2) {
                    macroStatus = 'MODERATELY BULLISH';
                    macroColor = '#3498db';
                    macroRecommendation = `${indicesAbove}/${totalIndices} indices above SMA20 - Normal position sizing`;
                } else if (indicesAbove === 1) {
                    macroStatus = 'NEUTRAL';
                    macroColor = '#f39c12';
                    macroRecommendation = 'Mixed signals - Reduce position sizes';
                } else {
                    macroStatus = 'BEARISH';
                    macroColor = '#e74c3c';
                    macroRecommendation = 'All indices below SMA20 - Consider scaling out';
                }
                
                document.getElementById('macro-status').textContent = macroStatus;
                document.getElementById('macro-status').style.color = macroColor;
                document.getElementById('macro-recommendation').textContent = macroRecommendation;
                
                // Update index details
                let detailsHtml = '';
                if (idx.index_details) {
                    for (const [indexName, indexData] of Object.entries(idx.index_details)) {
                        const position = indexData.sma_position_pct || 0;
                        const color = indexData.above_sma20 ? '#2ecc71' : '#e74c3c';
                        detailsHtml += `<div style="margin: 5px 0;"><strong>${indexName}:</strong> <span style="color: ${color}">${position > 0 ? '+' : ''}${position.toFixed(1)}%</span></div>`;
                    }
                }
                document.getElementById('macro-details').innerHTML = detailsHtml;
            }
            
            // Update Micro View (Pattern-based)
            const regime = data.regime;
            const microStatus = regime.replace(/_/g, ' ').toUpperCase();
            const longCount = data.counts.long;
            const shortCount = data.counts.short;
            const ratio = data.ratio;
            
            let microColor = '#95a5a6';
            let microRecommendation = '';
            
            if (regime.includes('strong_uptrend') || regime.includes('uptrend')) {
                microColor = '#2ecc71';
                microRecommendation = `Strong reversal patterns (${longCount}L/${shortCount}S) - Take long positions`;
            } else if (regime.includes('strong_downtrend') || regime.includes('downtrend')) {
                microColor = '#e74c3c';
                microRecommendation = `Bearish patterns dominate (${longCount}L/${shortCount}S) - Focus on shorts`;
            } else {
                microColor = '#f39c12';
                microRecommendation = `Mixed patterns (${longCount}L/${shortCount}S) - Be selective`;
            }
            
            document.getElementById('micro-status').textContent = microStatus;
            document.getElementById('micro-status').style.color = microColor;
            document.getElementById('micro-recommendation').textContent = microRecommendation;
            
            // Update micro details
            const microDetailsHtml = `
                <div style="margin: 5px 0;"><strong>Reversal Patterns:</strong> ${longCount} Long, ${shortCount} Short</div>
                <div style="margin: 5px 0;"><strong>L/S Ratio:</strong> ${ratio === 'inf' ? 'Infinite' : ratio.toFixed(2)}</div>
                <div style="margin: 5px 0;"><strong>Confidence:</strong> ${(data.confidence * 100).toFixed(1)}%</div>
            `;
            document.getElementById('micro-details').innerHTML = microDetailsHtml;
            
            // Update Action Summary
            let divergence = false;
            if (data.index_analysis) {
                const idxTrend = data.index_analysis.trend || '';
                if ((idxTrend.includes('bearish') && (regime.includes('uptrend') || regime.includes('bullish'))) ||
                    (idxTrend.includes('bullish') && (regime.includes('downtrend') || regime.includes('bearish')))) {
                    divergence = true;
                }
            }
            
            const actionSummary = document.getElementById('action-summary');
            if (divergence) {
                actionSummary.style.borderColor = '#e74c3c';
                actionSummary.innerHTML = `
                    <div style="font-size: 1.3em; font-weight: bold; color: #e74c3c; margin-bottom: 10px;">⚠️ DIVERGENCE DETECTED</div>
                    <p style="margin: 0;">Macro and Micro views diverge - Reduce position sizes and wait for confirmation</p>
                `;
            } else {
                actionSummary.style.borderColor = '#2ecc71';
                actionSummary.innerHTML = `
                    <div style="font-size: 1.3em; font-weight: bold; color: #2ecc71; margin-bottom: 10px;">✅ VIEWS ALIGNED</div>
                    <p style="margin: 0;">Both views align - Follow regime recommendations with confidence</p>
                `;
            }
        }
        
        function updateMultiTimeframeAnalysis(data) {
            if (!data.multi_timeframe_analysis) {
                console.log('No multi-timeframe data available');
                return;
            }
            
            const mtf = data.multi_timeframe_analysis;
            
            // Update individual timeframes
            const timeframes = ['daily', 'weekly', 'biweekly', 'monthly'];
            
            timeframes.forEach(tf => {
                if (mtf.timeframes && mtf.timeframes[tf]) {
                    const tfData = mtf.timeframes[tf];
                    
                    // Update regime
                    const regimeElement = document.getElementById(`${tf}-regime`);
                    if (regimeElement) {
                        regimeElement.textContent = tfData.regime.replace(/_/g, ' ').toUpperCase();
                        regimeElement.className = `tf-regime fw-bold mb-2 ${tfData.regime}`;
                    }
                    
                    // Update L/S
                    const lsElement = document.getElementById(`${tf}-ls`);
                    if (lsElement) {
                        lsElement.textContent = `${tfData.long_count}/${tfData.short_count}`;
                    }
                    
                    // Update ratio
                    const ratioElement = document.getElementById(`${tf}-ratio`);
                    if (ratioElement) {
                        ratioElement.textContent = tfData.ratio.toFixed(2);
                    }
                    
                    // Update confidence
                    const confElement = document.getElementById(`${tf}-conf`);
                    if (confElement) {
                        confElement.textContent = `${(tfData.confidence * 100).toFixed(0)}%`;
                    }
                    
                    // Update card border color based on regime
                    const card = document.getElementById(`${tf}-tf-card`);
                    if (card) {
                        card.className = `card timeframe-card ${tfData.regime}`;
                    }
                }
            });
            
            // Update combined analysis
            if (mtf.combined_signals) {
                const combined = mtf.combined_signals;
                
                // Update alignment
                const alignmentElement = document.getElementById('mtf-alignment');
                if (alignmentElement) {
                    alignmentElement.textContent = `${(combined.alignment_score * 100).toFixed(0)}%`;
                    alignmentElement.style.color = combined.alignment_score >= 0.8 ? '#2ecc71' : 
                                                   combined.alignment_score >= 0.6 ? '#3498db' : 
                                                   combined.alignment_score >= 0.4 ? '#f39c12' : '#e74c3c';
                }
                
                // Update alignment status
                const statusElement = document.getElementById('mtf-alignment-status');
                if (statusElement) {
                    let status = 'Divergence';
                    if (combined.alignment_score >= 0.8) status = 'Strong Alignment';
                    else if (combined.alignment_score >= 0.6) status = 'Moderate Alignment';
                    else if (combined.alignment_score >= 0.4) status = 'Weak Alignment';
                    statusElement.textContent = status;
                }
                
                // Update combined regime
                const regimeElement = document.getElementById('mtf-combined-regime');
                if (regimeElement) {
                    regimeElement.textContent = combined.combined_regime.replace(/_/g, ' ').toUpperCase();
                    regimeElement.className = `fw-bold ${combined.combined_regime}`;
                }
                
                // Update confidence
                const confElement = document.getElementById('mtf-confidence');
                if (confElement) {
                    confElement.textContent = `${(combined.confidence * 100).toFixed(0)}%`;
                }
            }
            
            // Update recommendation
            if (mtf.recommendation) {
                const recElement = document.getElementById('mtf-recommendation');
                if (recElement) {
                    recElement.textContent = mtf.recommendation;
                }
            }
            
            // Update divergences if any
            const divergenceAlert = document.getElementById('mtf-divergence-alert');
            const divergencesElement = document.getElementById('mtf-divergences');
            if (mtf.divergences && mtf.divergences.length > 0) {
                divergenceAlert.classList.remove('d-none');
                divergencesElement.innerHTML = mtf.divergences.map(d => `<div>• ${d}</div>`).join('');
            } else {
                divergenceAlert.classList.add('d-none');
            }
        }
        
        function updateVSRScores() {
            fetch('/api/vsr_scores')
                .then(response => response.json())
                .then(data => {
                    const container = document.getElementById('vsr-scores-container');
                    
                    if (data.error || !data.top_scores || data.top_scores.length === 0) {
                        container.innerHTML = '<div class="col-12 text-center text-muted">No VSR momentum data available</div>';
                        return;
                    }
                    
                    let html = '';
                    data.top_scores.forEach(stock => {
                        // Determine color based on score
                        let scoreColor = '#dc3545'; // red for low scores
                        if (stock.score >= 85) scoreColor = '#28a745'; // green for high scores
                        else if (stock.score >= 50) scoreColor = '#ffc107'; // yellow for medium scores
                        
                        // Trend indicator
                        let trendIcon = stock.trend === 'NEW' ? '🆕' : 
                                       stock.trend.includes('📈') ? '📈' : 
                                       stock.trend.includes('📉') ? '📉' : '➡️';
                        
                        html += `
                            <div class="col-md-4 mb-3">
                                <div class="card" style="border: 1px solid ${scoreColor}; background: rgba(255, 255, 255, 0.95);">
                                    <div class="card-body">
                                        <h6 class="mb-1">
                                            ${stock.ticker} 
                                            <span class="badge" style="background-color: ${scoreColor}; color: white;">Score: ${stock.score}</span>
                                            <small>${trendIcon}</small>
                                        </h6>
                                        <div class="small text-muted mb-2">${stock.sector}</div>
                                        <div class="row text-center small">
                                            <div class="col-4">
                                                <div class="text-muted">Price</div>
                                                <div>₹${stock.price}</div>
                                            </div>
                                            <div class="col-4">
                                                <div class="text-muted">VSR</div>
                                                <div class="fw-bold">${stock.vsr.toFixed(2)}</div>
                                            </div>
                                            <div class="col-4">
                                                <div class="text-muted">Volume</div>
                                                <div>${stock.volume}</div>
                                            </div>
                                        </div>
                                        <hr class="my-2">
                                        <div class="row text-center small">
                                            <div class="col-4">
                                                <div class="text-muted">Momentum</div>
                                                <div class="${stock.momentum > 0 ? 'text-success' : 'text-danger'} fw-bold">${stock.momentum}%</div>
                                            </div>
                                            <div class="col-4">
                                                <div class="text-muted">Build</div>
                                                <div style="color: #4ade80; font-weight: bold;">${stock.build}</div>
                                            </div>
                                            <div class="col-4">
                                                <div class="text-muted">Time</div>
                                                <div>${stock.time}</div>
                                            </div>
                                        </div>
                                        <div class="mt-2 small text-info" style="font-size: 0.75em;">
                                            Hourly VSR Analysis - Updated ${stock.last_update}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                    
                    container.innerHTML = html;
                })
                .catch(error => {
                    console.error('Error fetching VSR scores:', error);
                    document.getElementById('vsr-scores-container').innerHTML = 
                        '<div class="col-12 text-center text-danger">Error loading VSR data</div>';
                });
        }
        
        function updateMomentumData() {
            if (!dashboardConfig.show_momentum_scanner) return;
            fetch('/api/momentum_data')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success' && data.data) {
                        const current = data.data.current;
                        const tickerAnalysis = data.data.ticker_analysis;
                        
                        // Update market momentum
                        const momentumValue = current.momentum;
                        const momentumEl = document.getElementById('market-momentum-value');
                        momentumEl.textContent = momentumValue.toFixed(2);
                        
                        // Set color based on value
                        if (momentumValue > 5) {
                            momentumEl.className = 'display-4 text-success';
                        } else if (momentumValue > 0) {
                            momentumEl.className = 'display-4 text-info';
                        } else if (momentumValue > -5) {
                            momentumEl.className = 'display-4 text-warning';
                        } else {
                            momentumEl.className = 'display-4 text-danger';
                        }
                        
                        // Update change
                        const change = current.change;
                        const changeEl = document.getElementById('momentum-change');
                        changeEl.textContent = (change >= 0 ? '+' : '') + change.toFixed(2);
                        changeEl.className = 'fw-bold ' + (change >= 0 ? 'text-success' : 'text-danger');
                        
                        // Update regime
                        const regimeEl = document.getElementById('momentum-regime');
                        if (regimeEl) {
                            regimeEl.textContent = current.regime;
                            regimeEl.className = 'badge ' + getRegimeBadgeClass(current.regime);
                        }
                        
                        // Update SMA values
                        const sma20El = document.getElementById('current-sma20');
                        const sma50El = document.getElementById('current-sma50');
                        if (sma20El) sma20El.textContent = current.sma20;
                        if (sma50El) sma50El.textContent = current.sma50;
                        
                        // Update ticker counts
                        const dailyCountEl = document.getElementById('daily-ticker-count');
                        const dailyAvgEl = document.getElementById('daily-ticker-avg');
                        const weeklyCountEl = document.getElementById('weekly-ticker-count');
                        const weeklyAvgEl = document.getElementById('weekly-ticker-avg');
                        
                        if (dailyCountEl) dailyCountEl.textContent = tickerAnalysis.daily.current;
                        if (dailyAvgEl) dailyAvgEl.textContent = tickerAnalysis.daily.average;
                        if (weeklyCountEl) weeklyCountEl.textContent = tickerAnalysis.weekly.current;
                        if (weeklyAvgEl) weeklyAvgEl.textContent = tickerAnalysis.weekly.average;
                        
                        // Update interpretation
                        const interpretEl = document.getElementById('momentum-interpretation');
                        if (interpretEl && data.data.interpretation) {
                            interpretEl.textContent = data.data.interpretation;
                        }
                    }
                })
                .catch(error => {
                    console.error('Error fetching momentum data:', error);
                });
        }
        
        function getRegimeBadgeClass(regime) {
            if (regime.includes('Strong Bullish')) return 'bg-success';
            if (regime.includes('Bullish')) return 'bg-info';
            if (regime.includes('Mildly Bearish')) return 'bg-warning';
            if (regime.includes('Bearish')) return 'bg-danger';
            return 'bg-secondary';
        }
        
        function updateMomentumTrend() {
            fetch('/api/momentum_trend')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success' && data.data) {
                        const momentumTrend = data.data.momentum_trend;
                        const tickerCounts = data.data.ticker_counts;
                        
                        // Update momentum trend chart
                        if (window.momentumTrendChart) {
                            window.momentumTrendChart.data.labels = momentumTrend.dates;
                            window.momentumTrendChart.data.datasets[0].data = momentumTrend.values;
                            window.momentumTrendChart.data.datasets[1].data = tickerCounts.daily;
                            window.momentumTrendChart.data.datasets[2].data = tickerCounts.weekly;
                            window.momentumTrendChart.update();
                        }
                    }
                })
                .catch(error => {
                    console.error('Error fetching momentum trend:', error);
                });
        }
        
        function updateMetric(elementId, value, previousValue) {
            const element = document.getElementById(elementId);
            element.textContent = value.toFixed(2);
            
            const deltaElement = document.getElementById(elementId + '-delta');
            if (previousValue !== undefined && previousValue !== null) {
                const delta = value - previousValue;
                deltaElement.textContent = (delta >= 0 ? '+' : '') + delta.toFixed(3);
                deltaElement.className = 'metric-delta ' + (delta >= 0 ? 'positive' : 'negative');
            }
        }
        
        function updateCharts(data) {
            // Update regime history from API
            fetch('/api/regime_distribution')
                .then(response => response.json())
                .then(distData => {
                    // Clear existing data first
                    if (regimeHistoryChart) {
                        regimeHistoryChart.data.labels = [];
                        regimeHistoryChart.data.datasets[0].data = [];
                        regimeHistoryChart.data.datasets[0].backgroundColor = [];
                    }
                    
                    // Set new data
                    if (regimeHistoryChart) {
                        regimeHistoryChart.data.labels = distData.labels;
                        regimeHistoryChart.data.datasets[0].data = distData.values;
                        regimeHistoryChart.data.datasets[0].backgroundColor = distData.colors;
                        regimeHistoryChart.update('none'); // Use 'none' animation mode to prevent visual issues
                    }
                });
            
            // Update confidence trend from API
            fetch('/api/confidence_trend')
                .then(response => response.json())
                .then(trendData => {
                    // Clear existing data first
                    if (confidenceTrendChart) {
                        confidenceTrendChart.data.labels = [];
                        confidenceTrendChart.data.datasets[0].data = [];
                        
                        // Set new data
                        confidenceTrendChart.data.labels = trendData.labels;
                        confidenceTrendChart.data.datasets[0].data = trendData.values;
                        confidenceTrendChart.update('none'); // Use 'none' animation mode to prevent visual issues
                    }
                });
        }
        
        function updateSMABreadthCharts() {
            // Check if charts exist
            if (!window.sma20BreadthChart || !window.sma50BreadthChart) {
                console.log('SMA breadth charts not yet initialized');
                return;
            }
            
            // Fetch SMA breadth history
            fetch('/api/sma_breadth_history')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error('Error fetching SMA breadth history:', data.error);
                        // Clear loading message
                        const container = document.querySelector('.sma-breadth-container');
                        if (container) {
                            container.innerHTML = '<div class="text-center text-muted">No SMA breadth data available</div>';
                        }
                        return;
                    }
                    
                    // Update SMA20 chart
                    sma20BreadthChart.data.labels = data.labels;
                    sma20BreadthChart.data.datasets[0].data = data.sma20_values;
                    sma20BreadthChart.update('none');
                    
                    // Update SMA50 chart
                    sma50BreadthChart.data.labels = data.labels;
                    sma50BreadthChart.data.datasets[0].data = data.sma50_values;
                    sma50BreadthChart.update('none');
                    
                    // Update current values and trends
                    if (data.sma20_values.length > 0) {
                        const currentSMA20 = data.sma20_values[data.sma20_values.length - 1];
                        const previousSMA20 = data.sma20_values.length > 1 ? data.sma20_values[data.sma20_values.length - 2] : currentSMA20;
                        document.getElementById('current-sma20-breadth').textContent = currentSMA20.toFixed(1);
                        
                        // Calculate trend
                        const sma20Trend = currentSMA20 > previousSMA20 ? '↑ Improving' : 
                                         currentSMA20 < previousSMA20 ? '↓ Declining' : '→ Stable';
                        const sma20TrendElement = document.getElementById('sma20-trend');
                        sma20TrendElement.textContent = sma20Trend;
                        sma20TrendElement.style.color = currentSMA20 > previousSMA20 ? '#28a745' : 
                                                       currentSMA20 < previousSMA20 ? '#dc3545' : '#6c757d';
                    }
                    
                    if (data.sma50_values.length > 0) {
                        const currentSMA50 = data.sma50_values[data.sma50_values.length - 1];
                        const previousSMA50 = data.sma50_values.length > 1 ? data.sma50_values[data.sma50_values.length - 2] : currentSMA50;
                        document.getElementById('current-sma50-breadth').textContent = currentSMA50.toFixed(1);
                        
                        // Calculate trend
                        const sma50Trend = currentSMA50 > previousSMA50 ? '↑ Improving' : 
                                         currentSMA50 < previousSMA50 ? '↓ Declining' : '→ Stable';
                        const sma50TrendElement = document.getElementById('sma50-trend');
                        sma50TrendElement.textContent = sma50Trend;
                        sma50TrendElement.style.color = currentSMA50 > previousSMA50 ? '#17a2b8' : 
                                                       currentSMA50 < previousSMA50 ? '#dc3545' : '#6c757d';
                    }
                })
                .catch(error => console.error('Error updating SMA breadth charts:', error));
        }
        
        function drawSparklines(data) {
            // Simple sparkline implementation using canvas
            const metrics = ['market-score', 'trend-score', 'volatility-score'];
            
            metrics.forEach(metric => {
                const canvas = document.getElementById(metric + '-sparkline');
                if (!canvas) return;
                
                const ctx = canvas.getContext('2d');
                const width = canvas.width;
                const height = canvas.height;
                
                // Get historical values from API
                fetch(`/api/metric_history/${metric}`)
                    .then(response => response.json())
                    .then(history => {
                        if (!history.values || history.values.length < 2) return;
                        
                        ctx.clearRect(0, 0, width, height);
                        
                        const values = history.values;
                        const min = Math.min(...values);
                        const max = Math.max(...values);
                        const range = max - min || 1;
                        
                        ctx.strokeStyle = '#17a2b8';
                        ctx.lineWidth = 2;
                        ctx.beginPath();
                        
                        values.forEach((value, index) => {
                            const x = (index / (values.length - 1)) * width;
                            const y = height - ((value - min) / range) * height;
                            
                            if (index === 0) {
                                ctx.moveTo(x, y);
                            } else {
                                ctx.lineTo(x, y);
                            }
                        });
                        
                        ctx.stroke();
                    });
            });
        }
        
        // Initialize when everything is loaded
        function initializeDashboard() {
            console.log('Dashboard initialization started');
            
            // Show initialization message
            const regimeBadge = document.getElementById('regime-badge');
            if (regimeBadge) {
                regimeBadge.innerHTML = 'Initializing...';
            }
            
            // Initialize SMA Breadth Chart
            try {
                initializeSMABreadthChart();
                fetchSMABreadthData();
                console.log('SMA Breadth chart initialized');
            } catch (error) {
                console.error('Error initializing SMA breadth chart:', error);
            }
            
            // Initial update with error handling
            try {
                updateDashboard();
                updateMomentumData();
                updateMomentumTrend();
                console.log('Initial update triggered');
            } catch (error) {
                console.error('Error in updateDashboard:', error);
                if (regimeBadge) {
                    regimeBadge.innerHTML = 'Error loading data';
                }
            }
            
            // Update every 30 seconds
            setInterval(function() {
                try {
                    updateDashboard();
                } catch (error) {
                    console.error('Error in periodic update:', error);
                }
            }, 30000);
            
            // Update SMA breadth data every 60 seconds
            setInterval(function() {
                try {
                    fetchSMABreadthData();
                } catch (error) {
                    console.error('Error updating SMA breadth data:', error);
                }
            }, 60000);
            
            // Update momentum data every 5 minutes
            setInterval(function() {
                try {
                    updateMomentumData();
                    updateMomentumTrend();
                } catch (error) {
                    console.error('Error updating momentum data:', error);
                }
            }, 300000);
            
            // Update ML insights every 5 minutes if enabled
            if (dashboardConfig.show_ml_insights) {
                updateMLInsights();
                setInterval(function() {
                    try {
                        updateMLInsights();
                    } catch (error) {
                        console.error('Error updating ML insights:', error);
                    }
                }, 300000);
            }
        }
        
        // ML Functions
        async function updateMLInsights() {
            try {
                const response = await fetch('/api/ml_insights');
                if (!response.ok) {
                    throw new Error('ML insights not available');
                }
                
                const data = await response.json();
                
                // Update strategy recommendation
                const strategyEl = document.getElementById('mlStrategy');
                const strategyBox = document.getElementById('mlStrategyBox');
                if (strategyEl && data.strategy) {
                    strategyEl.textContent = data.strategy.recommended;
                    
                    // Update box color based on strategy
                    strategyBox.className = 'ml-strategy-box text-center p-3 rounded';
                    if (data.strategy.recommended === 'LONG') {
                        strategyBox.style.background = '#28a745';
                        strategyBox.style.color = 'white';
                    } else if (data.strategy.recommended === 'SHORT') {
                        strategyBox.style.background = '#dc3545';
                        strategyBox.style.color = 'white';
                    } else {
                        strategyBox.style.background = '#6c757d';
                        strategyBox.style.color = 'white';
                    }
                    
                    // Update confidence
                    const confidenceEl = document.getElementById('mlConfidence');
                    if (confidenceEl) {
                        confidenceEl.textContent = `Confidence: ${(data.strategy.confidence * 100).toFixed(0)}%`;
                    }
                }
                
                // Update expected returns
                document.getElementById('mlLongPnL').textContent = 
                    `${data.strategy.long_expected_pnl.toFixed(2)}%`;
                document.getElementById('mlShortPnL').textContent = 
                    `${data.strategy.short_expected_pnl.toFixed(2)}%`;
                
                // Update market conditions
                if (data.market_conditions) {
                    document.getElementById('mlSMA20').textContent = 
                        `${data.market_conditions.sma20_breadth.toFixed(1)}%`;
                    document.getElementById('mlTrend').textContent = 
                        data.market_conditions.breadth_trend;
                }
                
                // Update actionable insights
                updateMLActionableInsights(data.actionable_insights);
                
                // Update alerts
                updateMLAlerts();
                
            } catch (error) {
                console.error('Error fetching ML insights:', error);
                document.getElementById('mlStrategy').textContent = 'Unavailable';
            }
        }
        
        function updateMLActionableInsights(insights) {
            const container = document.getElementById('mlInsightsList');
            if (!container || !insights) return;
            
            container.innerHTML = insights.map(insight => `
                <div class="col-md-6 mb-3">
                    <div class="insight-card p-3 border rounded">
                        <h6><i class="fas ${insight.icon}"></i> ${insight.title}</h6>
                        <p class="mb-1">${insight.description}</p>
                        <small class="text-primary"><strong>Action:</strong> ${insight.action}</small>
                        <div class="mt-2">
                            <div class="progress" style="height: 5px;">
                                <div class="progress-bar" role="progressbar" 
                                     style="width: ${insight.confidence * 100}%"
                                     aria-valuenow="${insight.confidence * 100}">
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `).join('');
        }
        
        async function updateMLAlerts() {
            try {
                const response = await fetch('/api/ml_alerts');
                const alerts = await response.json();
                
                const container = document.getElementById('mlAlertsList');
                if (!container) return;
                
                if (alerts.length === 0) {
                    container.innerHTML = '<p class="text-muted">No active alerts</p>';
                    return;
                }
                
                container.innerHTML = alerts.map(alert => {
                    let badgeClass = 'badge-info';
                    if (alert.severity === 'high') badgeClass = 'badge-danger';
                    else if (alert.severity === 'warning') badgeClass = 'badge-warning';
                    
                    return `
                        <div class="alert alert-${alert.severity === 'high' ? 'danger' : 
                                        alert.severity === 'warning' ? 'warning' : 'info'} 
                                    alert-dismissible fade show" role="alert">
                            <span class="badge ${badgeClass}">${alert.type}</span>
                            <strong>${alert.title}:</strong> ${alert.message}
                            <button type="button" class="close" data-dismiss="alert">
                                <span aria-hidden="true">&times;</span>
                            </button>
                        </div>
                    `;
                }).join('');
                
            } catch (error) {
                console.error('Error fetching ML alerts:', error);
            }
        }
        
        // Try multiple initialization methods
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initializeDashboard);
        } else {
            // DOM is already loaded
            initializeDashboard();
        }
    </script>
    
    {% if config.show_ml_insights %}
    <!-- ML Strategy Recommendations -->
    <div class="card mb-4" id="mlInsightsCard">
        <div class="card-header bg-primary text-white">
            <h4 class="mb-0">🤖 ML-Based Strategy Recommendations</h4>
            <small>Real-time predictions updated every 5 minutes</small>
        </div>
        <div class="card-body">
            <div class="row">
                <div class="col-md-4">
                    <div class="ml-strategy-box text-center p-3 rounded" id="mlStrategyBox">
                        <h3 class="mb-0" id="mlStrategy">Loading...</h3>
                        <small class="text-muted">Recommended Strategy</small>
                        <div class="mt-2">
                            <span class="badge badge-info" id="mlConfidence">Confidence: --</span>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="ml-metrics p-3">
                        <h5>Expected Returns</h5>
                        <div class="metric-row">
                            <span>Long PnL:</span>
                            <span id="mlLongPnL" class="float-right">--</span>
                        </div>
                        <div class="metric-row">
                            <span>Short PnL:</span>
                            <span id="mlShortPnL" class="float-right">--</span>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="ml-conditions p-3">
                        <h5>Market Conditions</h5>
                        <div class="condition-row">
                            <span>SMA20:</span>
                            <span id="mlSMA20" class="float-right">--</span>
                        </div>
                        <div class="condition-row">
                            <span>Trend:</span>
                            <span id="mlTrend" class="float-right">--</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- ML Alerts -->
            <div class="mt-4" id="mlAlertsContainer">
                <h5>ML Alerts</h5>
                <div id="mlAlertsList">
                    <!-- Alerts will be populated here -->
                </div>
            </div>
            
            <!-- Actionable Insights -->
            <div class="mt-4" id="mlInsightsContainer">
                <h5>Actionable Insights</h5>
                <div class="row" id="mlInsightsList">
                    <!-- Insights will be populated here -->
                </div>
            </div>
        </div>
    </div>
    {% endif %}
    
    {% if config.show_optimal_conditions %}
    <!-- Optimal Trading Conditions -->
    <div class="card" style="margin-top: 20px; margin-bottom: 30px; background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);">
        <div class="card-header" style="background: transparent; border-bottom: 2px solid rgba(255,255,255,0.1);">
            <h4 class="mb-0 text-white">🎯 Optimal SMA20 Breadth Trading Conditions</h4>
        </div>
        <div class="card-body">
            <div class="row">
                <div class="col-md-6">
                    <div class="optimal-conditions-box" style="background: rgba(255,255,255,0.05); border-radius: 10px; padding: 20px; margin-bottom: 20px;">
                        <h5 class="text-warning mb-3">📉 SHORT REVERSAL STRATEGY</h5>
                        <div class="condition-item mb-2">
                            <span class="badge badge-success">BEST</span>
                            <span class="text-white ml-2">SMA20: 35-50%</span>
                            <small class="text-muted d-block ml-5">Success: 80% | Avg PnL: +2.91%</small>
                        </div>
                        <div class="condition-item mb-2">
                            <span class="badge badge-warning">GOOD</span>
                            <span class="text-white ml-2">SMA20: 25-35%</span>
                            <small class="text-muted d-block ml-5">Success: 66.7% | Avg PnL: +0.66%</small>
                        </div>
                        <div class="condition-item mb-2">
                            <span class="badge badge-danger">AVOID</span>
                            <span class="text-white ml-2">SMA20: Below 20%</span>
                            <small class="text-muted d-block ml-5">Oversold bounce risk</small>
                        </div>
                        <div class="condition-item">
                            <span class="badge badge-danger">AVOID</span>
                            <span class="text-white ml-2">SMA20: Above 50%</span>
                            <small class="text-muted d-block ml-5">Bullish conditions</small>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="optimal-conditions-box" style="background: rgba(255,255,255,0.05); border-radius: 10px; padding: 20px; margin-bottom: 20px;">
                        <h5 class="text-info mb-3">📈 LONG REVERSAL STRATEGY</h5>
                        <div class="condition-item mb-2">
                            <span class="badge badge-success">BEST</span>
                            <span class="text-white ml-2">SMA20: 55-70%</span>
                            <small class="text-muted d-block ml-5">Success: 43-46% | Avg PnL: +0.29-0.47%</small>
                        </div>
                        <div class="condition-item mb-2">
                            <span class="badge badge-warning">MODERATE</span>
                            <span class="text-white ml-2">SMA20: 45-55%</span>
                            <small class="text-muted d-block ml-5">Mixed results, use caution</small>
                        </div>
                        <div class="condition-item mb-2">
                            <span class="badge badge-danger">AVOID</span>
                            <span class="text-white ml-2">SMA20: Below 45%</span>
                            <small class="text-muted d-block ml-5">Poor success rates</small>
                        </div>
                        <div class="condition-item">
                            <span class="badge badge-danger">AVOID</span>
                            <span class="text-white ml-2">SMA20: Above 70%</span>
                            <small class="text-muted d-block ml-5">Potentially overbought</small>
                        </div>
                    </div>
                </div>
            </div>
            <div class="alert alert-info mt-3" style="background: rgba(52, 152, 219, 0.1); border: 1px solid rgba(52, 152, 219, 0.3);">
                <h6 class="alert-heading">💡 Key Insights:</h6>
                <ul class="mb-0 small">
                    <li>Shorts work best in moderately weak markets (35-50% breadth)</li>
                    <li>Longs work best in moderately strong markets (55-70% breadth)</li>
                    <li>Extreme breadth readings (&lt;20% or &gt;70%) should be avoided</li>
                    <li>Analysis based on 4-day holding period for reversal trades</li>
                </ul>
            </div>
        </div>
    </div>
    {% endif %}
    
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(ENHANCED_DASHBOARD_HTML, config=DASHBOARD_CONFIG)

@app.route('/api/current_analysis')
def get_current_analysis():
    """Get current regime analysis data"""
    try:
        # Load from same source as other dashboards
        summary_file = os.path.join(REGIME_DIR, 'latest_regime_summary.json')
        
        if not os.path.exists(summary_file):
            return jsonify({'error': 'No regime data available'})
        
        with open(summary_file, 'r') as f:
            data = json.load(f)
        
        # Format for dashboard
        response = {
            'timestamp': data['timestamp'],
            'regime': data['market_regime']['regime'],
            'confidence': data['market_regime']['confidence'],
            'strategy': data['market_regime']['strategy'],
            'ratio': data['trend_analysis']['ratio'],
            'counts': data['reversal_counts'],
            'smoothed_counts': data.get('smoothed_counts', data['reversal_counts']),
            'index_analysis': data.get('index_analysis', {}),
            'indicators': {
                'market_score': data['trend_analysis'].get('enhanced_market_score') or data['trend_analysis'].get('market_score', 0),
                'trend_score': data['trend_analysis'].get('trend_score', 0),
                'volatility_score': data.get('volatility', {}).get('volatility_score', 0),
                'breadth_score': data['trend_analysis'].get('breadth_score') or (data.get('breadth_indicators', {}).get('breadth_score', 0) if data.get('breadth_indicators') else 0)
            },
            'weekly_bias': data['trend_analysis'].get('weekly_bias'),
            'enhanced_direction': data['trend_analysis'].get('enhanced_direction'),
            'volatility': data.get('volatility', {}),
            'position_recommendations': data.get('position_recommendations', {}),
            'model_performance': data.get('model_performance', {}),
            'historical_context': data.get('historical_context', {}),
            'multi_timeframe_analysis': data.get('multi_timeframe_analysis', {})
        }
        
        # Store in history
        regime_history.append({
            'timestamp': data['timestamp'],
            'regime': data['market_regime']['regime']
        })
        
        for key in ['market_score', 'trend_score', 'volatility_score']:
            score_history[key].append(response['indicators'].get(key, 0))
        score_history['confidence'].append(response['confidence'])
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/regime_distribution')
def get_regime_distribution():
    """Get regime distribution for chart"""
    # Count regimes from history
    regime_counts = {}
    for entry in regime_history:
        regime = entry['regime']
        regime_counts[regime] = regime_counts.get(regime, 0) + 1
    
    # Define colors
    colors = {
        'strong_uptrend': '#006400',
        'uptrend': '#32CD32',
        'choppy_bullish': '#FFD700',
        'choppy': '#D3D3D3',
        'choppy_bearish': '#FF8C00',
        'downtrend': '#FF6347',
        'strong_downtrend': '#8B0000'
    }
    
    labels = list(regime_counts.keys())
    values = list(regime_counts.values())
    chart_colors = [colors.get(regime, '#808080') for regime in labels]
    
    return jsonify({
        'labels': [r.replace('_', ' ').title() for r in labels],
        'values': values,
        'colors': chart_colors
    })

@app.route('/api/confidence_trend')
def get_confidence_trend():
    """Get confidence trend for chart"""
    # Get last 20 values
    values = list(score_history['confidence'])[-20:]
    labels = [f'-{20-i}' for i in range(len(values))]
    
    return jsonify({
        'labels': labels,
        'values': [v * 100 for v in values]  # Convert to percentage
    })

@app.route('/api/metric_history/<metric>')
def get_metric_history(metric):
    """Get historical values for a specific metric"""
    metric_map = {
        'market-score': 'market_score',
        'trend-score': 'trend_score',
        'volatility-score': 'volatility_score'
    }
    
    metric_key = metric_map.get(metric)
    if metric_key and metric_key in score_history:
        return jsonify({
            'values': list(score_history[metric_key])
        })
    
    return jsonify({'values': []})

@app.route('/api/g_pattern_data')
def get_g_pattern_data():
    """Get G Pattern data from G_Pattern_Summary.txt"""
    try:
        summary_file = os.path.join(G_PATTERN_DIR, 'G_Pattern_Summary.txt')
        if not os.path.exists(summary_file):
            return jsonify({
                'error': 'G Pattern Summary file not found',
                'categories': {}
            })
        
        with open(summary_file, 'r') as f:
            content = f.read()
        
        # Parse the G Pattern Summary
        categories = {
            'confirmed': [],
            'developing': [],
            'emerging': [],
            'watch_closely': [],
            'watch_only': []
        }
        
        current_category = None
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for category headers
            if 'G PATTERN CONFIRMED' in line:
                current_category = 'confirmed'
            elif 'G PATTERN DEVELOPING' in line:
                current_category = 'developing'
            elif 'PATTERN EMERGING' in line and 'INITIAL POSITION' in line:
                current_category = 'emerging'
            elif 'WATCH CLOSELY' in line:
                current_category = 'watch_closely'
            elif 'WATCH ONLY' in line:
                current_category = 'watch_only'
            elif current_category and ':' in line and 'Score' in line:
                # Parse stock entry
                try:
                    parts = line.split(':')
                    ticker_sector = parts[0].strip()
                    
                    # Extract ticker and sector
                    if '(' in ticker_sector:
                        ticker = ticker_sector.split('(')[0].strip()
                        sector = ticker_sector.split('(')[1].rstrip(')')
                    else:
                        ticker = ticker_sector
                        sector = 'Unknown'
                    
                    # Extract score, days, and entry price
                    details = parts[1].strip()
                    score = int(details.split('Score')[1].split(',')[0].strip())
                    days = int(details.split('Days')[1].split(',')[0].strip())
                    entry_price = float(details.split('₹')[1].strip())
                    
                    categories[current_category].append({
                        'ticker': ticker,
                        'sector': sector,
                        'score': score,
                        'days': days,
                        'entry_price': entry_price
                    })
                except Exception as e:
                    print(f"Error parsing line: {line}, Error: {e}")
                    continue
        
        # Get generation time
        generated_time = None
        for line in lines[:5]:  # Check first few lines
            if 'Generated:' in line:
                generated_time = line.split('Generated:')[1].strip()
                break
        
        # Count totals
        total_count = len(g_pattern_df)
        
        return jsonify({
            'generated_time': generated_time,
            'categories': categories,
            'counts': {
                'confirmed': len(categories['confirmed']),
                'developing': len(categories['developing']),
                'emerging': len(categories['emerging']),
                'watch_closely': len(categories['watch_closely']),
                'watch_only': len(categories['watch_only'])
            },
            'total_count': total_count,
            'source_file': os.path.basename(latest_file)
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'categories': {}
        })

@app.route('/api/vsr_scores')
def get_vsr_scores():
    """Get top VSR scores from tracker logs"""
    try:
        # Get today's VSR tracker log
        today = datetime.now().strftime('%Y%m%d')
        vsr_log_path = os.path.join(DAILY_DIR, 'logs', 'vsr_tracker', f'vsr_tracker_{today}.log')
        
        if not os.path.exists(vsr_log_path):
            return jsonify({
                'error': 'No VSR tracker log found for today',
                'top_scores': [],
                'total_count': 0
            })
        
        # Parse the log file to extract latest scores
        ticker_data = {}
        
        # Pattern to match VSR tracker log lines
        pattern = r'\[(.*?)\]\s+(\w+)\s+\|\s+Score:\s+(\d+)\s+\|\s+VSR:\s+([\d.]+)\s+\|\s+Price:\s+₹([\d.]+)\s+\|\s+Vol:\s+([\d,N/A]+)\s+\|\s+Momentum:\s+([-\d.]+)%\s+\|\s+Build:\s+(.*?)\s+\|\s+Trend:\s+(.*?)\s+\|\s+Sector:\s+(.*?)$'
        
        # Read the log file
        with open(vsr_log_path, 'r') as f:
            for line in f:
                if '| Score:' in line and 'VSR:' in line:
                    match = re.search(pattern, line)
                    if match:
                        user = match.group(1)
                        ticker = match.group(2)
                        score = int(match.group(3))
                        vsr = float(match.group(4))
                        price = float(match.group(5))
                        volume = match.group(6).replace(',', '') if match.group(6) != 'N/A' else 'N/A'
                        momentum = float(match.group(7))
                        build = match.group(8).strip()
                        trend = match.group(9).strip()
                        sector = match.group(10).strip()
                        
                        # Extract timestamp from the line
                        time_match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                        timestamp = time_match.group(1) if time_match else ''
                        
                        # Update with latest data for each ticker
                        ticker_data[ticker] = {
                            'ticker': ticker,
                            'score': score,
                            'vsr': vsr,
                            'price': price,
                            'volume': volume,
                            'momentum': momentum,
                            'build': build,
                            'trend': trend,
                            'sector': sector,
                            'timestamp': timestamp,
                            'time': timestamp.split(' ')[1] if timestamp else '',
                            'last_update': timestamp.split(' ')[1] if timestamp else ''
                        }
        
        # Filter for high scores (>=50) and sort by score
        top_scores = [data for data in ticker_data.values() if data['score'] >= 50]
        top_scores.sort(key=lambda x: x['score'], reverse=True)
        
        # Get top 15
        top_15 = top_scores[:15]
        
        return jsonify({
            'top_scores': top_15,
            'total_count': len(top_scores),
            'last_update': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'top_scores': [],
            'total_count': 0
        })

@app.route('/api/sma_breadth_history')
def get_sma_breadth_history():
    """Get historical SMA breadth data for charting - 7 months of data"""
    try:
        # Check for historical data file first
        historical_data_file = os.path.join(SCRIPT_DIR, 'historical_breadth_data', 'sma_breadth_historical_latest.json')
        
        labels = []
        sma20_values = []
        sma50_values = []
        
        if os.path.exists(historical_data_file):
            # Use the 7-month historical data
            try:
                with open(historical_data_file, 'r') as f:
                    historical_data = json.load(f)
                
                # Process historical data
                for day_data in historical_data:
                    # Parse the date
                    date_str = day_data.get('date', '')
                    if date_str:
                        # Convert to proper date format for Chart.js time scale
                        try:
                            from datetime import datetime
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            formatted_date = date_obj.strftime('%Y-%m-%d')
                            # Add data point
                            labels.append(formatted_date)
                            sma20_values.append(day_data.get('sma_breadth', {}).get('sma20_percent', 0))
                            sma50_values.append(day_data.get('sma_breadth', {}).get('sma50_percent', 0))
                        except Exception as e:
                            logger.error(f"Error parsing date {date_str}: {e}")
                            continue
                
                logger.info(f"Loaded {len(labels)} days of historical SMA breadth data")
                
            except Exception as e:
                logger.error(f"Error loading historical data: {e}")
        
        # If no historical data or it's empty, fall back to current breadth data
        if not labels:
            logger.warning("No historical data found, falling back to current breadth data")
            
            breadth_dir = os.path.join(SCRIPT_DIR, 'breadth_data')
            if os.path.exists(breadth_dir):
                # Get all breadth files except 'latest'
                all_files = [f for f in os.listdir(breadth_dir) 
                            if f.startswith('market_breadth_') and f.endswith('.json') 
                            and 'latest' not in f]
                
                # Sort by filename (which includes timestamp)
                all_files.sort()
                
                # Take the last 30 days worth of data (assuming ~14 files per day)
                breadth_files = all_files[-420:]  # 30 days * 14 files/day
                
                # Process each file
                for filename in breadth_files:
                    filepath = os.path.join(breadth_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            data = json.load(f)
                        
                        # Extract timestamp from data
                        timestamp_str = data.get('timestamp', '')
                        if timestamp_str:
                            # Parse the timestamp
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            
                            # Format label as daily date only
                            date_str = timestamp.strftime('%Y-%m-%d')
                            
                            # Add data point (daily aggregation)
                            labels.append(date_str)
                            sma20_values.append(data.get('sma_breadth', {}).get('sma20_percent', 0))
                            sma50_values.append(data.get('sma_breadth', {}).get('sma50_percent', 0))
                        
                    except Exception as e:
                        logger.error(f"Error processing breadth file {filename}: {e}")
                        continue
        
        # Downsample for better chart display (keep every nth point for optimal viewing)
        if len(labels) > 100:
            step = max(1, len(labels) // 100)
            labels = labels[::step]
            sma20_values = sma20_values[::step]
            sma50_values = sma50_values[::step]
        
        return jsonify({
            'labels': labels,
            'sma20_values': sma20_values,
            'sma50_values': sma50_values,
            'data_points': len(labels)
        })
        
    except Exception as e:
        logger.error(f"Error fetching SMA breadth history: {e}")
        return jsonify({
            'error': str(e),
            'labels': [],
            'sma20_values': [],
            'sma50_values': [],
            'data_points': 0
        })

@app.route('/api/reversal_patterns')
def get_reversal_patterns():
    """Get top Long and Short Reversal patterns"""
    try:
        # Get today's date
        today = datetime.now().strftime('%Y%m%d')
        
        # Find ALL Long Reversal files and get the latest
        all_long_files = glob.glob(os.path.join(LONG_RESULTS_DIR, 'Long_Reversal_Daily_*.xlsx'))
        # Filter for today's files
        long_files = [f for f in all_long_files if today in f]
        
        # Find ALL Short Reversal files and get the latest
        all_short_files = glob.glob(os.path.join(SHORT_RESULTS_DIR, 'Short_Reversal_Daily_*.xlsx'))
        # Filter for today's files
        short_files = [f for f in all_short_files if today in f]
        
        result = {
            'long_reversals': [],
            'short_reversals': [],
            'long_file_time': None,
            'short_file_time': None,
            'error': None
        }
        
        # Process Long Reversals
        if long_files:
            latest_long = max(long_files, key=os.path.getctime)
            try:
                df = pd.read_excel(latest_long)
                # Convert Score to numeric if it's not already
                if 'Score' in df.columns:
                    # Handle fraction format like "7/7", "6/7"
                    if df['Score'].dtype == 'object' and len(df) > 0:
                        # Convert fractions to numeric scores
                        def fraction_to_score(score_str):
                            try:
                                if '/' in str(score_str):
                                    num, denom = str(score_str).split('/')
                                    return (float(num) / float(denom)) * 100
                                else:
                                    return float(score_str)
                            except:
                                return 0
                        
                        df['Score'] = df['Score'].apply(fraction_to_score)
                    else:
                        df['Score'] = pd.to_numeric(df['Score'], errors='coerce')
                    
                    # Remove rows with NaN scores
                    df = df.dropna(subset=['Score'])
                    # Get top 10 by Score (descending)
                    if len(df) > 0:
                        top_long = df.nlargest(10, 'Score')[['Ticker', 'Score', 'Entry_Price', 'Stop_Loss', 'Target1']].to_dict('records')
                    for item in top_long:
                        item['Entry_Price'] = round(item.get('Entry_Price', 0), 2)
                        item['Stop_Loss'] = round(item.get('Stop_Loss', 0), 2)
                        item['Target1'] = round(item.get('Target1', 0), 2)
                        item['Score'] = round(item.get('Score', 0), 1)
                    result['long_reversals'] = top_long
                    
                # Get file time
                file_time = datetime.fromtimestamp(os.path.getmtime(latest_long))
                result['long_file_time'] = file_time.strftime('%H:%M')
            except Exception as e:
                result['error'] = f"Error reading long reversal file: {str(e)}"
                print(f"Error reading long reversal file: {e}")
        
        # Process Short Reversals
        if short_files:
            latest_short = max(short_files, key=os.path.getctime)
            try:
                df = pd.read_excel(latest_short)
                # Convert Score to numeric if it's not already
                if 'Score' in df.columns:
                    # Handle fraction format like "7/7", "6/7"
                    if df['Score'].dtype == 'object' and len(df) > 0:
                        # Convert fractions to numeric scores
                        def fraction_to_score(score_str):
                            try:
                                if '/' in str(score_str):
                                    num, denom = str(score_str).split('/')
                                    return (float(num) / float(denom)) * 100
                                else:
                                    return float(score_str)
                            except:
                                return 0
                        
                        df['Score'] = df['Score'].apply(fraction_to_score)
                    else:
                        df['Score'] = pd.to_numeric(df['Score'], errors='coerce')
                    
                    # Remove rows with NaN scores
                    df = df.dropna(subset=['Score'])
                    # Get top 10 by Score (descending)
                    if len(df) > 0:
                        top_short = df.nlargest(10, 'Score')[['Ticker', 'Score', 'Entry_Price', 'Stop_Loss', 'Target1']].to_dict('records')
                    for item in top_short:
                        item['Entry_Price'] = round(item.get('Entry_Price', 0), 2)
                        item['Stop_Loss'] = round(item.get('Stop_Loss', 0), 2)
                        item['Target1'] = round(item.get('Target1', 0), 2)
                        item['Score'] = round(item.get('Score', 0), 1)
                    result['short_reversals'] = top_short
                    
                # Get file time
                file_time = datetime.fromtimestamp(os.path.getmtime(latest_short))
                result['short_file_time'] = file_time.strftime('%H:%M')
            except Exception as e:
                result['error'] = f"Error reading short reversal file: {str(e)}"
                print(f"Error reading short reversal file: {e}")
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'long_reversals': [],
            'short_reversals': []
        })

@app.route('/api/sma-breadth-historical')
def get_sma_breadth_historical():
    """Get historical SMA breadth data"""
    try:
        # Load historical data
        data_file = os.path.join(SCRIPT_DIR, 'historical_breadth_data', 'sma_breadth_historical_latest.json')
        
        if not os.path.exists(data_file):
            return jsonify({'error': 'Historical data not found'})
        
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        if not data:
            return jsonify({'error': 'No data available'})
        
        # Calculate trend metrics with safe access
        current = data[-1]
        five_days_ago = data[-6] if len(data) >= 6 else data[0]
        twenty_days_ago = data[-21] if len(data) >= 21 else data[0]
        
        # Safe access to breadth values
        current_sma20 = current.get('sma_breadth', {}).get('sma20_percent', 0)
        current_sma50 = current.get('sma_breadth', {}).get('sma50_percent', 0)
        five_ago_sma20 = five_days_ago.get('sma_breadth', {}).get('sma20_percent', 0)
        five_ago_sma50 = five_days_ago.get('sma_breadth', {}).get('sma50_percent', 0)
        twenty_ago_sma20 = twenty_days_ago.get('sma_breadth', {}).get('sma20_percent', 0)
        twenty_ago_sma50 = twenty_days_ago.get('sma_breadth', {}).get('sma50_percent', 0)
        
        sma20_5d_change = current_sma20 - five_ago_sma20
        sma50_5d_change = current_sma50 - five_ago_sma50
        sma20_20d_change = current_sma20 - twenty_ago_sma20
        sma50_20d_change = current_sma50 - twenty_ago_sma50
        
        # Prepare response with safe access to potentially missing fields
        response_data = {
            'labels': [d['date'] for d in data],
            'sma20_values': [d.get('sma_breadth', {}).get('sma20_percent', 0) for d in data],
            'sma50_values': [d.get('sma_breadth', {}).get('sma50_percent', 0) for d in data],
            'market_scores': [d.get('market_score', 0.5) for d in data],
            'data_points': len(data),
            'current_sma20': current.get('sma_breadth', {}).get('sma20_percent', 0),
            'current_sma50': current.get('sma_breadth', {}).get('sma50_percent', 0),
            'market_regime': current.get('market_regime', 'Unknown'),
            'market_score': current.get('market_score', 0.5),
            'total_stocks': current.get('total_stocks', 500),  # Default to 500 if not present
            'date_range': f"{data[0]['date']} to {data[-1]['date']}",
            'sma20_5d_change': sma20_5d_change,
            'sma50_5d_change': sma50_5d_change,
            'sma20_20d_change': sma20_20d_change,
            'sma50_20d_change': sma50_20d_change,
            # Add volume breadth data with safe defaults
            # Handle both old format (volume_breadth) and new format (volume_analysis)
            'volume_breadth_values': [
                # Try old format first
                d.get('volume_breadth', {}).get('volume_breadth_percent') if d.get('volume_breadth', {}).get('volume_breadth_percent') is not None
                # Fall back to new format calculation
                else ((d.get('volume_analysis', {}).get('high_volume', 0) / d.get('total_stocks', 1)) * 100 
                if d.get('total_stocks', 0) > 0 and d.get('volume_analysis') else 0)
                for d in data
            ],
            # Use volume participation from old format or avg_volume_ratio from new format
            'volume_participation_values': [
                # Try old format first (already in percentage)
                (d.get('volume_breadth', {}).get('volume_participation', 0) * 100) if d.get('volume_breadth', {}).get('volume_participation') is not None
                # Fall back to new format
                else (d.get('volume_analysis', {}).get('avg_volume_ratio', 0) * 100 if d.get('volume_analysis') else 0)
                for d in data
            ],
            'current_volume_breadth': (
                # Try old format first
                current.get('volume_breadth', {}).get('volume_breadth_percent', 0) or
                # Fall back to new format
                ((current.get('volume_analysis', {}).get('high_volume', 0) / current.get('total_stocks', 1)) * 100
                if current.get('total_stocks', 0) > 0 else 0)
            )
        }
        
        # Debug log
        logger.info(f"Volume breadth values sample: {response_data['volume_breadth_values'][:5]}")
        logger.info(f"Volume participation values sample: {response_data['volume_participation_values'][:5]}")
        logger.info(f"Current volume breadth: {response_data['current_volume_breadth']}")
        
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Error in get_sma_breadth_historical: {e}")
        return jsonify({'error': str(e)})

@app.route('/api/momentum_data')
def get_momentum_data():
    """Get momentum scanner data"""
    return get_market_breadth_momentum_data()

@app.route('/api/momentum_trend')
def get_momentum_trend():
    """Get momentum historical trend data"""
    return get_market_breadth_momentum_trend()

@app.route('/api/ml_insights')
def api_ml_insights():
    """Get ML insights and recommendations"""
    if not ML_AVAILABLE:
        return jsonify({'error': 'ML integration not available'}), 503
    
    try:
        insights = get_ml_insights()
        return jsonify(insights)
    except Exception as e:
        logger.error(f"Error getting ML insights: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml_alerts')
def api_ml_alerts():
    """Get ML-based alerts"""
    if not ML_AVAILABLE:
        return jsonify([])
    
    try:
        alerts = get_ml_alerts()
        return jsonify(alerts)
    except Exception as e:
        logger.error(f"Error getting ML alerts: {e}")
        return jsonify([])

@app.route('/api/ml_performance')
def api_ml_performance():
    """Get ML model performance metrics"""
    if not ML_AVAILABLE:
        return jsonify({'error': 'ML integration not available'}), 503
    
    try:
        performance = get_ml_performance()
        return jsonify(performance)
    except Exception as e:
        logger.error(f"Error getting ML performance: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Daily Market Regime - Enhanced Dashboard")
    print("="*60)
    print(f"\nDashboard URL: http://localhost:8080")
    print("\nPress Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=8080, debug=True)