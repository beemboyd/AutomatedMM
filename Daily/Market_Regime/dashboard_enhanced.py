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
                        <h5 class="card-title"><i class="fas fa-bullseye"></i> Position Recommendations</h5>
                        <div class="row text-center">
                            <div class="col-6 mb-3">
                                <div class="metric-value" id="position-size">-</div>
                                <small>Position Size</small>
                            </div>
                            <div class="col-6 mb-3">
                                <div class="metric-value" id="stop-loss">-</div>
                                <small>Stop Loss</small>
                            </div>
                            <div class="col-6">
                                <div class="metric-value" id="max-positions">-</div>
                                <small>Max Positions</small>
                            </div>
                            <div class="col-6">
                                <div class="metric-value" id="risk-per-trade">-</div>
                                <small>Risk/Trade</small>
                            </div>
                        </div>
                        <div class="alert alert-warning mt-3 mb-0">
                            <strong>Direction:</strong> <span id="preferred-direction">-</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
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
            <div class="col-md-6 mb-3">
                <div class="chart-container">
                    <h5>Regime History</h5>
                    <canvas id="regime-history-chart" height="150"></canvas>
                </div>
            </div>
            
            <div class="col-md-6 mb-3">
                <div class="chart-container">
                    <h5>Confidence Trend</h5>
                    <canvas id="confidence-trend-chart" height="150"></canvas>
                </div>
            </div>
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
        
        <!-- G Pattern Strategy Section -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">🎯 G Pattern Strategy</h5>
                        
                        <div class="row">
                            <!-- G Pattern Confirmed -->
                            <div class="col-md-4 mb-3">
                                <div class="card" style="border: 2px solid #27ae60; background: rgba(39, 174, 96, 0.1);">
                                    <div class="card-body text-center">
                                        <h6 style="color: #27ae60;">G PATTERN CONFIRMED</h6>
                                        <div id="g-pattern-confirmed-count" style="font-size: 2.5em; font-weight: bold; color: #27ae60;">-</div>
                                        <p class="mb-2">10% Allocation per Position</p>
                                        <div id="g-pattern-confirmed-list" style="font-size: 0.9em; text-left; max-height: 150px; overflow-y: auto;">
                                            <div class="text-muted">Loading...</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Pattern Emerging -->
                            <div class="col-md-4 mb-3">
                                <div class="card" style="border: 2px solid #3498db; background: rgba(52, 152, 219, 0.1);">
                                    <div class="card-body text-center">
                                        <h6 style="color: #3498db;">PATTERN EMERGING</h6>
                                        <div id="g-pattern-emerging-count" style="font-size: 2.5em; font-weight: bold; color: #3498db;">-</div>
                                        <p class="mb-2">5% Allocation per Position</p>
                                        <div id="g-pattern-emerging-list" style="font-size: 0.9em; text-left; max-height: 150px; overflow-y: auto;">
                                            <div class="text-muted">Loading...</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Watch Closely -->
                            <div class="col-md-4 mb-3">
                                <div class="card" style="border: 2px solid #f39c12; background: rgba(243, 156, 18, 0.1);">
                                    <div class="card-body text-center">
                                        <h6 style="color: #f39c12;">PATTERN DEVELOPING</h6>
                                        <div id="g-pattern-developing-count" style="font-size: 2.5em; font-weight: bold; color: #f39c12;">-</div>
                                        <p class="mb-2">5% Allocation per Position</p>
                                        <div id="g-pattern-developing-list" style="font-size: 0.9em; text-left; max-height: 150px; overflow-y: auto;">
                                            <div class="text-muted">Loading...</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Strategy Summary -->
                        <div class="alert alert-info mt-3">
                            <h6 class="alert-heading">📅 Trading Strategy</h6>
                            <div class="row">
                                <div class="col-md-6">
                                    <p class="mb-1"><strong>G Pattern Confirmed:</strong> 10% allocation per position</p>
                                    <p class="mb-1"><strong>Pattern Emerging/Developing:</strong> 5% allocation per position</p>
                                    <p class="mb-1"><strong>Risk Management:</strong> Follow predefined stop losses</p>
                                </div>
                                <div class="col-md-6">
                                    <div class="bg-white p-2 rounded">
                                        <strong>Active Opportunities:</strong> <span id="g-pattern-opportunities" class="text-primary">Loading...</span><br>
                                        <strong>Next Action:</strong> <span class="text-success">Review positions for allocation</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Early Bird Section -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">🐦 Early Bird Opportunities - KC Breakout Watch</h5>
                        <p class="text-muted mb-3">First appearances of KC_Breakout_Watch pattern - stocks breaking above Keltner Channel without volume confirmation yet</p>
                        
                        <div class="row" id="early-bird-container">
                            <div class="col-12 text-center">
                                <div class="spinner-border text-primary" role="status">
                                    <span class="visually-hidden">Loading...</span>
                                </div>
                            </div>
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
    
    <script>
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
        const regimeHistoryChart = new Chart(document.getElementById('regime-history-chart'), {
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
        
        const confidenceTrendChart = new Chart(document.getElementById('confidence-trend-chart'), {
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
        
        let previousData = null;
        
        function updateDashboard() {
            fetch('/api/current_analysis')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error(data.error);
                        return;
                    }
                    
                    // Update regime display
                    const regimeBadge = document.getElementById('regime-badge');
                    regimeBadge.className = 'regime-badge ' + data.regime;
                    regimeBadge.innerHTML = data.regime.replace('_', ' ').toUpperCase();
                    
                    // Update confidence and ratio
                    document.getElementById('confidence-display').textContent = 
                        (data.confidence * 100).toFixed(1) + '%';
                    document.getElementById('ratio-display').textContent = 
                        data.ratio === 'inf' ? '∞' : data.ratio.toFixed(2);
                    
                    // Update proximity marker
                    const marketScore = data.indicators.market_score || 0;
                    const position = ((marketScore + 1) / 2) * 100;
                    document.getElementById('proximity-marker').style.left = position + '%';
                    
                    // Update strategy
                    document.getElementById('strategy-text').textContent = data.strategy;
                    
                    // Update position recommendations
                    if (data.position_recommendations) {
                        const recs = data.position_recommendations;
                        document.getElementById('position-size').textContent = recs.position_size_multiplier + 'x';
                        document.getElementById('stop-loss').textContent = recs.stop_loss_multiplier + 'x';
                        document.getElementById('max-positions').textContent = recs.max_positions;
                        document.getElementById('risk-per-trade').textContent = (recs.risk_per_trade * 100).toFixed(1) + '%';
                        document.getElementById('preferred-direction').textContent = recs.preferred_direction.toUpperCase();
                    }
                    
                    // Update metrics
                    updateMetric('market-score', marketScore, previousData?.indicators?.market_score);
                    updateMetric('trend-score', data.indicators.trend_score, previousData?.indicators?.trend_score);
                    updateMetric('volatility-score', data.indicators.volatility_score, 
                               previousData?.indicators?.volatility_score);
                    
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
                        document.getElementById('regime-duration').textContent = 
                            ctx.regime_duration_hours.toFixed(1) + ' hours';
                        document.getElementById('stability-score').textContent = 
                            (ctx.stability_24h * 100).toFixed(0) + '%';
                    }
                    
                    if (data.model_performance) {
                        document.getElementById('model-accuracy').textContent = 
                            (data.model_performance.accuracy * 100).toFixed(1) + '%';
                    }
                    
                    document.getElementById('last-update').textContent = 
                        new Date(data.timestamp).toLocaleTimeString();
                    
                    // Update charts
                    updateCharts(data);
                    
                    // Draw sparklines
                    drawSparklines(data);
                    
                    // Update Macro/Micro View
                    updateMacroMicroView(data);
                    
                    previousData = data;
                })
                .catch(error => console.error('Error fetching data:', error));
            
            // Update G Pattern data
            updateGPatternData();
            
            // Update Reversal Patterns data
            updateReversalPatterns();
            
            // Update Early Bird data
            updateEarlyBirdPatterns();
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
        
        function updateEarlyBirdPatterns() {
            fetch('/api/early_bird')
                .then(response => response.json())
                .then(data => {
                    const container = document.getElementById('early-bird-container');
                    
                    if (data.error || !data.early_birds || data.early_birds.length === 0) {
                        container.innerHTML = '<div class="col-12 text-center text-muted">No Early Bird opportunities found today</div>';
                        return;
                    }
                    
                    let html = '';
                    data.early_birds.forEach(bird => {
                        html += `
                            <div class="col-md-4 mb-3">
                                <div class="card" style="border: 1px solid #4ade80; background: rgba(74, 222, 128, 0.05);">
                                    <div class="card-body">
                                        <h6 class="mb-1" style="color: #4ade80;">
                                            ${bird.ticker} 
                                            <small class="text-warning">@ ${bird.time_appeared}</small>
                                        </h6>
                                        <div class="small text-muted mb-2">${bird.sector}</div>
                                        <div class="row text-center small">
                                            <div class="col-4">
                                                <div class="text-muted">Entry</div>
                                                <div>₹${bird.entry_price}</div>
                                            </div>
                                            <div class="col-4">
                                                <div class="text-muted">SL</div>
                                                <div class="text-danger">₹${bird.stop_loss}</div>
                                            </div>
                                            <div class="col-4">
                                                <div class="text-muted">Target</div>
                                                <div class="text-success">₹${bird.target1}</div>
                                            </div>
                                        </div>
                                        <hr class="my-2">
                                        <div class="row text-center small">
                                            <div class="col-4">
                                                <div class="text-muted">Score</div>
                                                <div style="color: #4ade80; font-weight: bold;">${bird.probability_score}</div>
                                            </div>
                                            <div class="col-4">
                                                <div class="text-muted">Vol</div>
                                                <div>${bird.volume_ratio}x</div>
                                            </div>
                                            <div class="col-4">
                                                <div class="text-muted">KC%</div>
                                                <div>${bird.kc_distance}%</div>
                                            </div>
                                        </div>
                                        <div class="mt-2 small text-warning" style="font-size: 0.75em;">
                                            ${bird.description}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                    
                    container.innerHTML = html;
                })
                .catch(error => {
                    console.error('Error fetching early bird patterns:', error);
                    document.getElementById('early-bird-container').innerHTML = 
                        '<div class="col-12 text-center text-danger">Error loading Early Bird data</div>';
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
                    regimeHistoryChart.data.labels = [];
                    regimeHistoryChart.data.datasets[0].data = [];
                    regimeHistoryChart.data.datasets[0].backgroundColor = [];
                    
                    // Set new data
                    regimeHistoryChart.data.labels = distData.labels;
                    regimeHistoryChart.data.datasets[0].data = distData.values;
                    regimeHistoryChart.data.datasets[0].backgroundColor = distData.colors;
                    regimeHistoryChart.update('none'); // Use 'none' animation mode to prevent visual issues
                });
            
            // Update confidence trend from API
            fetch('/api/confidence_trend')
                .then(response => response.json())
                .then(trendData => {
                    // Clear existing data first
                    confidenceTrendChart.data.labels = [];
                    confidenceTrendChart.data.datasets[0].data = [];
                    
                    // Set new data
                    confidenceTrendChart.data.labels = trendData.labels;
                    confidenceTrendChart.data.datasets[0].data = trendData.values;
                    confidenceTrendChart.update('none'); // Use 'none' animation mode to prevent visual issues
                });
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
        
        // Update every 30 seconds
        setInterval(updateDashboard, 30000);
        
        // Initial update
        updateDashboard();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(ENHANCED_DASHBOARD_HTML)

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
                'market_score': data['trend_analysis'].get('market_score', 0),
                'trend_score': data['trend_analysis'].get('trend_score', 0),
                'volatility_score': data.get('volatility', {}).get('volatility_score', 0),
                'breadth_score': data.get('breadth_indicators', {}).get('breadth_score', 0)
            },
            'volatility': data.get('volatility', {}),
            'position_recommendations': data.get('position_recommendations', {}),
            'model_performance': data.get('model_performance', {}),
            'historical_context': data.get('historical_context', {})
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

@app.route('/api/early_bird')
def get_early_bird_patterns():
    """Get Early Bird (KC_Breakout_Watch first appearances) patterns"""
    try:
        # Get today's date
        today = datetime.now(IST).strftime('%Y%m%d')
        
        # Find KC Upper Limit files for today
        kc_files = sorted(glob.glob(os.path.join(LONG_RESULTS_DIR, f'KC_Upper_Limit_Trending_{today}_*.xlsx')))
        
        if not kc_files:
            # Try yesterday if no files today
            yesterday = (datetime.now(IST) - timedelta(days=1)).strftime('%Y%m%d')
            kc_files = sorted(glob.glob(os.path.join(LONG_RESULTS_DIR, f'KC_Upper_Limit_Trending_{yesterday}_*.xlsx')))
        
        early_birds = []
        seen_tickers = set()
        
        # Process files chronologically to find first appearances
        for filepath in kc_files:
            try:
                df = pd.read_excel(filepath)
                
                # Filter for KC_Breakout_Watch pattern
                kc_breakout = df[df['Pattern'] == 'KC_Breakout_Watch']
                
                for _, row in kc_breakout.iterrows():
                    ticker = row['Ticker']
                    if ticker not in seen_tickers:
                        seen_tickers.add(ticker)
                        
                        # Extract timestamp from filename
                        filename = os.path.basename(filepath)
                        timestamp_str = filename.replace('KC_Upper_Limit_Trending_', '').replace('.xlsx', '')
                        time_parts = timestamp_str.split('_')
                        if len(time_parts) == 2:
                            hour = time_parts[1][:2]
                            minute = time_parts[1][2:4]
                            time_str = f"{hour}:{minute}"
                        else:
                            time_str = "N/A"
                        
                        early_birds.append({
                            'ticker': ticker,
                            'sector': row.get('Sector', 'Unknown'),
                            'entry_price': round(row.get('Entry_Price', 0), 2),
                            'stop_loss': round(row.get('Stop_Loss', 0), 2),
                            'target1': round(row.get('Target1', 0), 2),
                            'probability_score': round(row.get('Probability_Score', 0), 1),
                            'volume_ratio': round(row.get('Volume_Ratio', 0), 2),
                            'time_appeared': time_str,
                            'description': row.get('Description', ''),
                            'kc_distance': round(row.get('KC_Distance_%', 0), 2),
                            'adx': round(row.get('ADX', 0), 1),
                            'momentum_5d': round(row.get('Momentum_5D', 0), 2)
                        })
            except Exception as e:
                print(f"Error processing KC file {filepath}: {e}")
                continue
        
        # Sort by probability score descending
        early_birds.sort(key=lambda x: x['probability_score'], reverse=True)
        
        return jsonify({
            'early_birds': early_birds[:15],  # Top 15
            'total_count': len(early_birds),
            'last_update': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'early_birds': [],
            'total_count': 0
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

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Daily Market Regime - Enhanced Dashboard")
    print("="*60)
    print(f"\nDashboard URL: http://localhost:8080")
    print("\nPress Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=8080, debug=False)