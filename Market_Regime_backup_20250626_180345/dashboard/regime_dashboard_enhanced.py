"""
Market Regime Dashboard - Enhanced Version with Subtle Change Indicators

Real-time dashboard for market regime analysis with improved visualization of subtle changes.
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
from collections import deque

from Market_Regime.integration.daily_integration import DailyTradingIntegration
from Market_Regime.core.regime_detector import MarketRegime

# Embedded HTML template with enhanced indicators
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Market Regime Dashboard - Enhanced</title>
    
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
        
        .regime-transition-indicator {
            position: absolute;
            top: 10px;
            right: 10px;
            font-size: 0.9rem;
            padding: 5px 10px;
            border-radius: 20px;
            background: rgba(255,255,255,0.3);
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .strong_bull { background-color: #006400; color: white; }
        .bull { background-color: #32CD32; color: white; }
        .neutral { background-color: #FFD700; color: black; }
        .bear { background-color: #FF6347; color: white; }
        .strong_bear { background-color: #8B0000; color: white; }
        .volatile { background-color: #FF8C00; color: white; }
        .crisis { background-color: #800080; color: white; }
        
        .trending-bull { border-right: 10px solid #32CD32; }
        .trending-bear { border-right: 10px solid #FF6347; }
        .trending-neutral { border-right: 10px solid #FFD700; }
        
        .metric-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            position: relative;
        }
        
        .metric-delta {
            font-size: 0.8rem;
            margin-left: 10px;
        }
        
        .delta-positive { color: #28a745; }
        .delta-negative { color: #dc3545; }
        .delta-neutral { color: #6c757d; }
        
        .metric-label {
            color: #6c757d;
            font-size: 0.9rem;
            margin-bottom: 5px;
        }
        
        .metric-value {
            font-size: 1.8rem;
            font-weight: bold;
            color: #212529;
            display: inline-block;
        }
        
        .metric-trend {
            font-size: 0.8rem;
            color: #6c757d;
        }
        
        .metric-sparkline {
            position: absolute;
            bottom: 10px;
            right: 10px;
            width: 60px;
            height: 20px;
        }
        
        .transition-alert {
            background: #fff3cd;
            border-left: 5px solid #ffc107;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            animation: slideIn 0.5s ease-out;
        }
        
        @keyframes slideIn {
            from { transform: translateX(-100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        .breadth-indicator {
            padding: 10px;
            border-radius: 10px;
            text-align: center;
            font-weight: bold;
            margin: 5px 0;
        }
        
        .breadth-positive { background-color: #d4edda; color: #155724; }
        .breadth-negative { background-color: #f8d7da; color: #721c24; }
        .breadth-neutral { background-color: #fff3cd; color: #856404; }
        
        .regime-proximity {
            margin-top: 15px;
            padding: 10px;
            background: #f0f0f0;
            border-radius: 5px;
        }
        
        .proximity-bar {
            height: 20px;
            background: linear-gradient(to right, #8B0000, #FF6347, #FFD700, #32CD32, #006400);
            border-radius: 10px;
            position: relative;
            margin: 10px 0;
        }
        
        .proximity-marker {
            position: absolute;
            top: -5px;
            width: 30px;
            height: 30px;
            background: white;
            border: 3px solid #333;
            border-radius: 50%;
            transform: translateX(-50%);
            transition: left 0.5s ease;
        }
        
        .threshold-marker {
            position: absolute;
            top: 0;
            width: 2px;
            height: 20px;
            background: rgba(0,0,0,0.3);
        }
        
        .chart-container {
            background: white;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        
        .update-time {
            text-align: center;
            color: #6c757d;
            margin-top: 20px;
            font-size: 0.9rem;
        }
        
        .loading {
            text-align: center;
            color: #6c757d;
            padding: 20px;
        }
        
        .action-item {
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            border-left: 3px solid;
        }
        
        .action-HIGH { 
            background-color: #f8d7da; 
            border-left-color: #dc3545;
        }
        
        .action-MEDIUM { 
            background-color: #fff3cd; 
            border-left-color: #ffc107;
        }
        
        .action-LOW { 
            background-color: #d1ecf1; 
            border-left-color: #17a2b8;
        }
        
        .alert-item {
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            border-left: 5px solid;
        }
        
        .alert-HIGH { 
            background-color: #f8d7da; 
            border-left-color: #dc3545;
        }
        
        .alert-MEDIUM { 
            background-color: #fff3cd; 
            border-left-color: #ffc107;
        }
        
        .alert-LOW { 
            background-color: #d1ecf1; 
            border-left-color: #17a2b8;
        }
    </style>
</head>
<body>
    <div class="dashboard-header">
        <div class="container">
            <h1 class="text-center mb-0">
                <i class="fas fa-chart-line"></i> Market Regime Dashboard - Enhanced
            </h1>
            <p class="text-center mt-2 mb-0">Real-time Market Analysis with Subtle Change Detection</p>
        </div>
    </div>
    
    <div class="container">
        <!-- Transition Alert (shown when subtle changes detected) -->
        <div id="transition-alert" style="display: none;">
            <div class="transition-alert">
                <h5><i class="fas fa-info-circle"></i> Market Transition Detected</h5>
                <p id="transition-message" class="mb-0"></p>
            </div>
        </div>
        
        <!-- Current Regime Section -->
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card regime-card" id="regime-main-card">
                    <div class="card-body">
                        <h2 class="card-title"><i class="fas fa-compass"></i> Current Market Regime</h2>
                        <div id="current-regime-content">
                            <div class="loading">
                                <i class="fas fa-spinner fa-spin fa-2x"></i><br>
                                Analyzing market conditions...
                            </div>
                        </div>
                        
                        <!-- Regime Proximity Indicator -->
                        <div class="regime-proximity">
                            <h6>Regime Proximity (Market Score: <span id="proximity-score">0.00</span>)</h6>
                            <div class="proximity-bar">
                                <div class="threshold-marker" style="left: 20%;"></div>
                                <div class="threshold-marker" style="left: 40%;"></div>
                                <div class="threshold-marker" style="left: 60%;"></div>
                                <div class="threshold-marker" style="left: 80%;"></div>
                                <div class="proximity-marker" id="proximity-marker" style="left: 50%;"></div>
                            </div>
                            <div class="d-flex justify-content-between mt-2">
                                <small>Strong Bear</small>
                                <small>Bear</small>
                                <small>Neutral</small>
                                <small>Bull</small>
                                <small>Strong Bull</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Key Metrics Row with Deltas -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="metric-label">Market Score</div>
                    <div>
                        <span class="metric-value" id="market-score">-</span>
                        <span class="metric-delta" id="market-score-delta"></span>
                    </div>
                    <div class="metric-trend" id="market-score-trend"></div>
                    <canvas class="metric-sparkline" id="market-score-sparkline"></canvas>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="metric-label">Trend Score</div>
                    <div>
                        <span class="metric-value" id="trend-score">-</span>
                        <span class="metric-delta" id="trend-score-delta"></span>
                    </div>
                    <div class="metric-trend" id="trend-score-trend"></div>
                    <canvas class="metric-sparkline" id="trend-score-sparkline"></canvas>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="metric-label">Volatility Score</div>
                    <div>
                        <span class="metric-value" id="volatility-score">-</span>
                        <span class="metric-delta" id="volatility-score-delta"></span>
                    </div>
                    <div class="metric-trend" id="volatility-score-trend"></div>
                    <canvas class="metric-sparkline" id="volatility-score-sparkline"></canvas>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="metric-label">Breadth Score</div>
                    <div>
                        <span class="metric-value" id="breadth-score">-</span>
                        <span class="metric-delta" id="breadth-score-delta"></span>
                    </div>
                    <div class="metric-trend" id="breadth-score-trend"></div>
                    <canvas class="metric-sparkline" id="breadth-score-sparkline"></canvas>
                </div>
            </div>
        </div>
        
        <!-- Scanner vs NIFTY Breadth Comparison -->
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card regime-card">
                    <div class="card-body">
                        <h3 class="card-title"><i class="fas fa-search"></i> Scanner Breadth (Primary)</h3>
                        <div class="row">
                            <div class="col-6">
                                <div class="breadth-indicator" id="scanner-breadth-status">
                                    <div>A/D Ratio: <span id="ad-ratio">-</span></div>
                                    <div>Bullish: <span id="bullish-percent">-</span></div>
                                </div>
                            </div>
                            <div class="col-6">
                                <div class="breadth-indicator">
                                    <div>Bearish: <span id="bearish-percent">-</span></div>
                                    <div>Momentum: <span id="momentum-ratio">-</span></div>
                                </div>
                            </div>
                        </div>
                        <div class="mt-3 text-center">
                            <small class="text-muted">Volume Participation: <span id="volume-participation">-</span></small>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card regime-card">
                    <div class="card-body">
                        <h3 class="card-title"><i class="fas fa-chart-bar"></i> NIFTY Breadth (Reference)</h3>
                        <div class="row">
                            <div class="col-6">
                                <div class="breadth-indicator" id="nifty-breadth-status">
                                    <div>A/D Ratio: <span id="nifty-ad-ratio">-</span></div>
                                    <div>Bullish: <span id="nifty-bullish-percent">-</span></div>
                                </div>
                            </div>
                            <div class="col-6">
                                <div class="breadth-indicator">
                                    <div>Bearish: <span id="nifty-bearish-percent">-</span></div>
                                    <div>Score: <span id="nifty-breadth-score">-</span></div>
                                </div>
                            </div>
                        </div>
                        <div class="mt-3 text-center">
                            <small class="text-muted">Market internals reference only</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Volatility Analysis Section -->
        <div class="row mb-4">
            <div class="col-md-12">
                <div class="card regime-card">
                    <div class="card-body">
                        <h3 class="card-title"><i class="fas fa-chart-area"></i> Volatility Analysis</h3>
                        <div class="row mt-3">
                            <div class="col-md-4">
                                <div class="metric-card">
                                    <div class="metric-label">Scanner Volatility</div>
                                    <div>
                                        <span class="metric-value" id="scanner-vol-regime">-</span>
                                        <span class="metric-delta" id="scanner-vol-score"></span>
                                    </div>
                                    <div class="metric-trend">
                                        <small>Avg ATR: <span id="scanner-avg-atr">-</span>%</small>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="metric-card">
                                    <div class="metric-label">High Volatility Stocks</div>
                                    <div>
                                        <span class="metric-value" id="high-vol-percent">-</span>%
                                    </div>
                                    <div class="metric-trend">
                                        <small>Volume Expansion: <span id="vol-expansion">-</span>x</small>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="metric-card">
                                    <div class="metric-label">NIFTY Volatility</div>
                                    <div>
                                        <span class="metric-value" id="nifty-vol-regime">-</span>
                                    </div>
                                    <div class="metric-trend">
                                        <small>Historical Vol: <span id="nifty-hist-vol">-</span>%</small>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="row mt-3">
                            <div class="col-12">
                                <h6>Volatility Insights:</h6>
                                <div id="volatility-insights" class="small">
                                    <div class="loading">Analyzing volatility...</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Trading Parameters and Actions -->
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
        
        // Store previous values for delta calculation
        let previousValues = {
            market_score: null,
            trend_score: null,
            volatility_score: null,
            breadth_score: null,
            regime: null,
            confidence: null
        };
        
        // Store history for sparklines
        let scoreHistory = {
            market_score: [],
            trend_score: [],
            volatility_score: [],
            breadth_score: []
        };
        
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
        
        // Calculate and format delta
        function formatDelta(current, previous) {
            if (previous === null || current === null || current === undefined) return '';
            const delta = current - previous;
            const deltaStr = delta >= 0 ? '+' + formatNumber(delta) : formatNumber(delta);
            const deltaClass = delta > 0 ? 'delta-positive' : delta < 0 ? 'delta-negative' : 'delta-neutral';
            const icon = delta > 0 ? '↑' : delta < 0 ? '↓' : '→';
            return `<span class="${deltaClass}">${icon} ${deltaStr}</span>`;
        }
        
        // Update proximity marker position
        function updateProximityMarker(marketScore) {
            // Convert market score (-1 to 1) to percentage position (0 to 100)
            const position = ((marketScore + 1) / 2) * 100;
            const marker = document.getElementById('proximity-marker');
            marker.style.left = position + '%';
            document.getElementById('proximity-score').textContent = formatNumber(marketScore);
        }
        
        // Update regime card styling based on trend
        function updateRegimeCardStyling(currentRegime, previousRegime, marketScore, previousScore) {
            const card = document.getElementById('regime-main-card');
            card.classList.remove('trending-bull', 'trending-bear', 'trending-neutral');
            
            if (previousScore !== null && marketScore !== null) {
                const delta = marketScore - previousScore;
                if (Math.abs(delta) > 0.05) {  // Significant change
                    if (delta > 0) {
                        card.classList.add('trending-bull');
                    } else {
                        card.classList.add('trending-bear');
                    }
                } else if (currentRegime === 'neutral') {
                    card.classList.add('trending-neutral');
                }
            }
        }
        
        // Show transition alert
        function showTransitionAlert(message) {
            const alertDiv = document.getElementById('transition-alert');
            const messageSpan = document.getElementById('transition-message');
            messageSpan.textContent = message;
            alertDiv.style.display = 'block';
            
            // Auto-hide after 30 seconds
            setTimeout(() => {
                alertDiv.style.display = 'none';
            }, 30000);
        }
        
        // Draw mini sparkline
        function drawSparkline(canvasId, data) {
            const canvas = document.getElementById(canvasId);
            if (!canvas) return;
            
            const ctx = canvas.getContext('2d');
            const width = canvas.width;
            const height = canvas.height;
            
            ctx.clearRect(0, 0, width, height);
            
            if (data.length < 2) return;
            
            const min = Math.min(...data);
            const max = Math.max(...data);
            const range = max - min || 1;
            
            ctx.strokeStyle = '#007bff';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            
            data.forEach((value, index) => {
                const x = (index / (data.length - 1)) * width;
                const y = height - ((value - min) / range) * height;
                
                if (index === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            });
            
            ctx.stroke();
        }
        
        // Update current regime display
        function updateCurrentRegime(data) {
            // Check for subtle changes
            if (previousValues.regime !== null) {
                const scoreDelta = Math.abs(data.market_score - previousValues.market_score);
                const confidenceDelta = Math.abs(data.confidence - previousValues.confidence);
                
                // Detect subtle regime changes
                if (data.regime === previousValues.regime && scoreDelta > 0.1) {
                    const direction = data.market_score > previousValues.market_score ? 'strengthening' : 'weakening';
                    showTransitionAlert(`Market conditions ${direction} within ${data.regime.replace('_', ' ')} regime. Market score changed by ${formatNumber(scoreDelta)}.`);
                } else if (data.regime !== previousValues.regime) {
                    showTransitionAlert(`Regime changed from ${previousValues.regime.replace('_', ' ')} to ${data.regime.replace('_', ' ')}`);
                } else if (confidenceDelta > 0.2) {
                    showTransitionAlert(`Regime confidence significantly changed from ${formatPercent(previousValues.confidence)} to ${formatPercent(data.confidence)}`);
                }
            }
            
            // Update regime card styling
            updateRegimeCardStyling(data.regime, previousValues.regime, data.market_score, previousValues.market_score);
            
            const regimeHtml = `
                <div class="row">
                    <div class="col-md-6">
                        <div class="regime-badge ${data.regime}">
                            ${data.regime.replace('_', ' ').toUpperCase()}
                            ${data.regime_changed ? '<span class="regime-transition-indicator">Transition</span>' : ''}
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
            
            // Update proximity marker
            updateProximityMarker(data.market_score);
            
            // Update metric cards with deltas
            document.getElementById('market-score').textContent = formatNumber(data.market_score);
            document.getElementById('market-score-delta').innerHTML = formatDelta(data.market_score, previousValues.market_score);
            
            document.getElementById('trend-score').textContent = formatNumber(data.trend_score);
            document.getElementById('trend-score-delta').innerHTML = formatDelta(data.trend_score, previousValues.trend_score);
            
            document.getElementById('volatility-score').textContent = formatNumber(data.volatility_score);
            document.getElementById('volatility-score-delta').innerHTML = formatDelta(data.volatility_score, previousValues.volatility_score);
            
            document.getElementById('breadth-score').textContent = formatNumber(data.breadth_score);
            document.getElementById('breadth-score-delta').innerHTML = formatDelta(data.breadth_score, previousValues.breadth_score);
            
            // Update score history and draw sparklines
            ['market_score', 'trend_score', 'volatility_score', 'breadth_score'].forEach(score => {
                if (data[score] !== undefined) {
                    scoreHistory[score].push(data[score]);
                    if (scoreHistory[score].length > 20) {
                        scoreHistory[score].shift();
                    }
                    drawSparkline(score + '-sparkline', scoreHistory[score]);
                }
            });
            
            // Update breadth indicators with styling
            if (data.breadth_indicators) {
                const scannerBreadthDiv = document.getElementById('scanner-breadth-status');
                const adRatio = data.breadth_indicators.advance_decline_ratio;
                scannerBreadthDiv.className = 'breadth-indicator ' + 
                    (adRatio > 1.5 ? 'breadth-positive' : adRatio < 0.67 ? 'breadth-negative' : 'breadth-neutral');
                
                document.getElementById('ad-ratio').textContent = formatNumber(adRatio);
                document.getElementById('bullish-percent').textContent = formatPercent(data.breadth_indicators.bullish_percent);
                document.getElementById('bearish-percent').textContent = formatPercent(data.breadth_indicators.bearish_percent);
                document.getElementById('momentum-ratio').textContent = formatNumber(data.breadth_indicators.momentum_ratio);
                document.getElementById('volume-participation').textContent = formatPercent(data.breadth_indicators.volume_participation);
            }
            
            // Update NIFTY breadth indicators
            if (data.nifty_breadth) {
                const niftyBreadthDiv = document.getElementById('nifty-breadth-status');
                const niftyAdRatio = data.nifty_breadth.advance_decline_ratio;
                niftyBreadthDiv.className = 'breadth-indicator ' + 
                    (niftyAdRatio > 1.5 ? 'breadth-positive' : niftyAdRatio < 0.67 ? 'breadth-negative' : 'breadth-neutral');
                
                document.getElementById('nifty-ad-ratio').textContent = formatNumber(niftyAdRatio);
                document.getElementById('nifty-bullish-percent').textContent = formatPercent(data.nifty_breadth.bullish_percent);
                document.getElementById('nifty-bearish-percent').textContent = formatPercent(data.nifty_breadth.bearish_percent);
                document.getElementById('nifty-breadth-score').textContent = formatNumber(data.nifty_breadth.breadth_score);
            }
            
            // Update volatility indicators
            updateVolatilityIndicators(data);
            
            // Store current values as previous for next update
            previousValues = {
                market_score: data.market_score,
                trend_score: data.trend_score,
                volatility_score: data.volatility_score,
                breadth_score: data.breadth_score,
                regime: data.regime,
                confidence: data.confidence
            };
        }
        
        // Update volatility indicators
        function updateVolatilityIndicators(data) {
            // Scanner-based volatility
            if (data.scanner_volatility_regime) {
                document.getElementById('scanner-vol-regime').textContent = data.scanner_volatility_regime.toUpperCase();
                const volRegimeDiv = document.getElementById('scanner-vol-regime').parentElement.parentElement;
                
                // Color code based on volatility regime
                volRegimeDiv.classList.remove('bg-success', 'bg-warning', 'bg-danger');
                if (data.scanner_volatility_regime === 'low') {
                    volRegimeDiv.classList.add('bg-light');
                } else if (data.scanner_volatility_regime === 'normal') {
                    // Default styling
                } else if (data.scanner_volatility_regime === 'high') {
                    volRegimeDiv.classList.add('bg-warning', 'bg-opacity-25');
                } else if (data.scanner_volatility_regime === 'extreme') {
                    volRegimeDiv.classList.add('bg-danger', 'bg-opacity-25');
                }
                
                if (data.scanner_volatility_score !== undefined) {
                    document.getElementById('scanner-vol-score').innerHTML = `(Score: ${formatNumber(data.scanner_volatility_score * 100)})`;
                }
            }
            
            // Scanner volatility metrics
            if (data.scanner_avg_atr_percent) {
                document.getElementById('scanner-avg-atr').textContent = formatNumber(data.scanner_avg_atr_percent);
            }
            if (data.scanner_high_vol_prevalence) {
                document.getElementById('high-vol-percent').textContent = formatNumber(data.scanner_high_vol_prevalence);
            }
            if (data.scanner_volume_expansion) {
                document.getElementById('vol-expansion').textContent = formatNumber(data.scanner_volume_expansion);
            }
            
            // NIFTY volatility
            const niftyVolRegime = data.volatility_regime || 'normal';
            document.getElementById('nifty-vol-regime').textContent = niftyVolRegime.toUpperCase();
            if (data.hist_volatility) {
                document.getElementById('nifty-hist-vol').textContent = formatNumber(data.hist_volatility);
            }
            
            // Volatility insights
            if (data.volatility_insights && data.volatility_insights.length > 0) {
                let insightsHtml = '<ul class="mb-0">';
                data.volatility_insights.forEach(insight => {
                    insightsHtml += `<li>${insight}</li>`;
                });
                insightsHtml += '</ul>';
                document.getElementById('volatility-insights').innerHTML = insightsHtml;
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
            // Fetch and update regime distribution chart
            fetch('/api/charts/regime_distribution')
                .then(response => response.json())
                .then(data => {
                    Plotly.newPlot('regime-distribution-chart', data.data, data.layout, {responsive: true});
                });
            
            // Fetch and update confidence trend chart
            fetch('/api/charts/confidence_trend')
                .then(response => response.json())
                .then(data => {
                    Plotly.newPlot('confidence-trend-chart', data.data, data.layout, {responsive: true});
                });
            
            // Fetch and update market score trend chart
            fetch('/api/charts/market_score_trend')
                .then(response => response.json())
                .then(data => {
                    Plotly.newPlot('market-score-trend-chart', data.data, data.layout, {responsive: true});
                });
        }
        
        // Main update function
        function updateDashboard() {
            // Fetch current analysis
            fetch('/api/current_analysis')
                .then(response => response.json())
                .then(data => {
                    updateCurrentRegime(data);
                    document.getElementById('last-update').textContent = new Date().toLocaleString();
                })
                .catch(error => {
                    console.error('Error fetching current analysis:', error);
                });
            
            // Fetch recommendations
            fetch('/api/recommendations')
                .then(response => response.json())
                .then(data => {
                    updateTradingParams(data);
                    updateSpecificActions(data.specific_actions || []);
                    updateAlerts(data.alerts || []);
                })
                .catch(error => {
                    console.error('Error fetching recommendations:', error);
                });
            
            // Update charts
            updateCharts();
        }
        
        // Initial load
        updateDashboard();
        
        // Set up auto-refresh
        setInterval(updateDashboard, UPDATE_INTERVAL);
    </script>
</body>
</html>'''


class RegimeDashboardApp:
    """Market Regime Dashboard Application - Enhanced Version"""
    
    def __init__(self, host='127.0.0.1', port=8080):
        self.app = Flask(__name__)
        self.host = host
        self.port = port
        self.integration = DailyTradingIntegration()
        self.latest_analysis = None
        self.latest_recommendations = None
        self.analysis_history = deque(maxlen=50)  # Store recent analyses
        
        # Set up routes
        self._setup_routes()
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
    def _setup_routes(self):
        """Set up Flask routes"""
        
        @self.app.route('/')
        def index():
            return render_template_string(HTML_TEMPLATE)
        
        @self.app.route('/api/current_analysis')
        def get_current_analysis():
            """Get current regime analysis"""
            if self.latest_analysis:
                regime_data = self.latest_analysis['regime_analysis']
                
                # Extract breadth indicators
                indicators = regime_data['indicators']
                breadth_indicators = {
                    'advance_decline_ratio': indicators.get('advance_decline_ratio', 1.0),
                    'bullish_percent': indicators.get('bullish_percent', 0.5),
                    'bearish_percent': indicators.get('bearish_percent', 0.5),
                    'positive_momentum_percent': indicators.get('positive_momentum_percent', 0.5),
                    'momentum_ratio': indicators.get('momentum_ratio', 1.0),
                    'volume_participation': indicators.get('volume_participation', 0.5)
                }
                
                # Extract NIFTY breadth (separate)
                nifty_breadth = {
                    'advance_decline_ratio': indicators.get('nifty_advance_decline_ratio', 1.0),
                    'bullish_percent': indicators.get('nifty_bullish_percent', 0.5),
                    'bearish_percent': indicators.get('nifty_bearish_percent', 0.5),
                    'breadth_score': indicators.get('nifty_breadth_score', 0.0)
                }
                
                # Load volatility insights if available
                volatility_insights = []
                try:
                    vol_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                          'volatility_data', 'volatility_analysis_latest.json')
                    if os.path.exists(vol_file):
                        with open(vol_file, 'r') as f:
                            vol_data = json.load(f)
                            volatility_insights = vol_data.get('insights', [])
                except:
                    pass
                
                return jsonify({
                    'regime': regime_data['enhanced_regime'],
                    'confidence': regime_data['enhanced_confidence'],
                    'regime_changed': regime_data.get('regime_changed', False),
                    'market_score': indicators.get('market_score', 0),
                    'trend_score': indicators.get('trend_score', 0),
                    'volatility_score': indicators.get('volatility_score', 0),
                    'breadth_score': indicators.get('breadth_score', 0),
                    'breadth_indicators': breadth_indicators,
                    'nifty_breadth': nifty_breadth,
                    # Scanner-based volatility indicators
                    'scanner_volatility_regime': indicators.get('scanner_volatility_regime'),
                    'scanner_volatility_score': indicators.get('scanner_volatility_score'),
                    'scanner_avg_atr_percent': indicators.get('scanner_avg_atr_percent'),
                    'scanner_high_vol_prevalence': indicators.get('scanner_high_vol_prevalence'),
                    'scanner_volume_expansion': indicators.get('scanner_volume_expansion'),
                    # NIFTY volatility for comparison
                    'volatility_regime': indicators.get('volatility_regime', 'normal'),
                    'hist_volatility': indicators.get('hist_volatility', 0),
                    'atr_percent': indicators.get('atr_percent', 0),
                    # Volatility insights
                    'volatility_insights': volatility_insights,
                    'timestamp': regime_data['timestamp']
                })
            
            return jsonify({
                'regime': 'initializing',
                'confidence': 0,
                'message': 'Market regime analysis will be available after first scan'
            })
        
        @self.app.route('/api/recommendations')
        def get_recommendations():
            """Get current recommendations"""
            if self.latest_recommendations:
                return jsonify(self.latest_recommendations)
            
            return jsonify({
                'position_sizing': {'size_multiplier': 1.0, 'max_position_size': 0.1},
                'risk_management': {'stop_loss_multiplier': 1.0, 'risk_per_trade': 0.01},
                'capital_deployment': {'deployment_rate': 0.5, 'cash_allocation': 0.5},
                'sector_preferences': {'preferred_sectors': [], 'avoid_sectors': []},
                'specific_actions': [],
                'alerts': []
            })
        
        @self.app.route('/api/charts/regime_distribution')
        def get_regime_distribution():
            """Get regime distribution chart data"""
            if not self.analysis_history:
                return jsonify({'data': [], 'layout': {}})
            
            regimes = [a['regime_analysis']['enhanced_regime'] for a in self.analysis_history]
            regime_counts = pd.Series(regimes).value_counts()
            
            data = [{
                'type': 'pie',
                'labels': regime_counts.index.tolist(),
                'values': regime_counts.values.tolist(),
                'hole': 0.4,
                'marker': {
                    'colors': ['#006400', '#32CD32', '#FFD700', '#FF6347', '#8B0000', '#FF8C00', '#800080']
                }
            }]
            
            layout = {
                'title': 'Regime Distribution',
                'height': 300,
                'margin': {'l': 0, 'r': 0, 't': 40, 'b': 0}
            }
            
            return jsonify({'data': data, 'layout': layout})
        
        @self.app.route('/api/charts/confidence_trend')
        def get_confidence_trend():
            """Get confidence trend chart data"""
            if not self.analysis_history:
                return jsonify({'data': [], 'layout': {}})
            
            timestamps = [datetime.fromisoformat(a['timestamp']) for a in self.analysis_history]
            confidences = [a['regime_analysis']['enhanced_confidence'] for a in self.analysis_history]
            
            data = [{
                'type': 'scatter',
                'x': timestamps,
                'y': confidences,
                'mode': 'lines+markers',
                'name': 'Confidence',
                'line': {'color': '#17a2b8', 'width': 2}
            }]
            
            layout = {
                'title': 'Regime Confidence Trend',
                'height': 300,
                'yaxis': {'title': 'Confidence', 'range': [0, 1]},
                'margin': {'l': 60, 'r': 20, 't': 40, 'b': 40}
            }
            
            return jsonify({'data': data, 'layout': layout})
        
        @self.app.route('/api/charts/market_score_trend')
        def get_market_score_trend():
            """Get market score trend chart data"""
            if not self.analysis_history:
                return jsonify({'data': [], 'layout': {}})
            
            timestamps = [datetime.fromisoformat(a['timestamp']) for a in self.analysis_history]
            market_scores = [a['regime_analysis']['indicators'].get('market_score', 0) for a in self.analysis_history]
            
            # Add regime background colors
            shapes = []
            for i, analysis in enumerate(self.analysis_history):
                if i < len(self.analysis_history) - 1:
                    regime = analysis['regime_analysis']['enhanced_regime']
                    color = {
                        'strong_bull': 'rgba(0,100,0,0.2)',
                        'bull': 'rgba(50,205,50,0.2)',
                        'neutral': 'rgba(255,215,0,0.2)',
                        'bear': 'rgba(255,99,71,0.2)',
                        'strong_bear': 'rgba(139,0,0,0.2)',
                        'volatile': 'rgba(255,140,0,0.2)',
                        'crisis': 'rgba(128,0,128,0.2)'
                    }.get(regime, 'rgba(128,128,128,0.2)')
                    
                    shapes.append({
                        'type': 'rect',
                        'x0': timestamps[i],
                        'x1': timestamps[i+1],
                        'y0': -1,
                        'y1': 1,
                        'fillcolor': color,
                        'line': {'width': 0}
                    })
            
            data = [{
                'type': 'scatter',
                'x': timestamps,
                'y': market_scores,
                'mode': 'lines+markers',
                'name': 'Market Score',
                'line': {'color': '#007bff', 'width': 2}
            }]
            
            layout = {
                'title': 'Market Score Trend',
                'height': 300,
                'yaxis': {'title': 'Market Score', 'range': [-1, 1]},
                'shapes': shapes,
                'margin': {'l': 60, 'r': 20, 't': 40, 'b': 40}
            }
            
            return jsonify({'data': data, 'layout': layout})
        
        @self.app.route('/api/history')
        def get_history():
            """Get regime history data"""
            history_data = []
            for analysis in list(self.analysis_history)[-20:]:  # Last 20 entries
                history_data.append({
                    'timestamp': analysis['timestamp'],
                    'regime': analysis['regime_analysis']['enhanced_regime'],
                    'confidence': analysis['confidence'],
                    'market_score': analysis['regime_analysis']['indicators'].get('market_score', 0),
                    'trend_score': analysis['regime_analysis']['indicators'].get('trend_score', 0),
                    'volatility_score': analysis['regime_analysis']['indicators'].get('volatility_score', 0),
                    'breadth_score': analysis['regime_analysis']['indicators'].get('breadth_score', 0)
                })
            
            return jsonify({
                'status': 'success',
                'data': history_data
            })
    
    def update_analysis(self):
        """Periodically update regime analysis"""
        while True:
            try:
                # Run analysis
                analysis = self.integration.analyze_current_market_regime()
                
                if 'error' not in analysis:
                    self.latest_analysis = analysis
                    self.latest_recommendations = analysis['recommendations']
                    self.analysis_history.append(analysis)
                    self.logger.info(f"Updated regime analysis: {analysis['regime_analysis']['enhanced_regime']}")
                
            except Exception as e:
                self.logger.error(f"Error updating analysis: {e}")
            
            # Wait 5 minutes before next update
            time.sleep(300)
    
    def run(self):
        """Run the dashboard application"""
        # Start background update thread
        update_thread = threading.Thread(target=self.update_analysis, daemon=True)
        update_thread.start()
        
        # Run initial analysis
        try:
            analysis = self.integration.analyze_current_market_regime()
            if 'error' not in analysis:
                self.latest_analysis = analysis
                self.latest_recommendations = analysis['recommendations']
                self.analysis_history.append(analysis)
        except Exception as e:
            self.logger.error(f"Error in initial analysis: {e}")
        
        # Print startup message
        print("\n" + "="*60)
        print("MARKET REGIME DASHBOARD - ENHANCED")
        print("="*60)
        print(f"\nStarting dashboard at: http://{self.host}:{self.port}")
        print("\nFeatures:")
        print("- Subtle regime change detection")
        print("- Market score proximity indicator")
        print("- Delta values for all metrics")
        print("- Sparkline visualizations")
        print("- Transition alerts")
        print("- Scanner vs NIFTY breadth comparison")
        print("\nPress Ctrl+C to stop the dashboard")
        print("="*60 + "\n")
        
        # Run Flask app
        self.app.run(host=self.host, port=self.port, debug=False)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Market Regime Dashboard - Enhanced')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to (default: 8080)')
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run dashboard
    dashboard = RegimeDashboardApp(host=args.host, port=args.port)
    
    try:
        dashboard.run()
    except KeyboardInterrupt:
        print("\n\nShutting down dashboard...")
        sys.exit(0)


if __name__ == '__main__':
    main()