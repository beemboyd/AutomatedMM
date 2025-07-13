#!/usr/bin/env python3
"""
India-TS Visual Health Check Dashboard

Comprehensive health monitoring with visual indicators and real-time updates.
Shows all critical metrics in one place with automatic refresh.
"""

from flask import Flask, render_template_string, jsonify
import os
import json
import sqlite3
from datetime import datetime, timedelta
import pytz
import subprocess
import pandas as pd
from pathlib import Path
import requests

app = Flask(__name__)

# Timezone setup
IST = pytz.timezone('Asia/Kolkata')

# Enhanced HTML Template with better visuals
VISUAL_DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>India-TS System Health Dashboard</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f0f;
            color: #ffffff;
            padding: 20px;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
        }
        
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            background: linear-gradient(45deg, #ff9933, #138808);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .status-card {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 20px;
            position: relative;
            overflow: hidden;
            transition: transform 0.2s;
        }
        
        .status-card:hover {
            transform: translateY(-2px);
            border-color: #ff9933;
        }
        
        .status-card.critical {
            border-color: #e74c3c;
            background: #1a0a0a;
        }
        
        .status-card.warning {
            border-color: #f39c12;
            background: #1a1500;
        }
        
        .status-card.good {
            border-color: #27ae60;
            background: #0a1a0a;
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .card-title {
            font-size: 1.2em;
            font-weight: 600;
        }
        
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        .status-good { background: #27ae60; }
        .status-warning { background: #f39c12; }
        .status-error { background: #e74c3c; }
        
        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(1.1); }
            100% { opacity: 1; transform: scale(1); }
        }
        
        .metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #333;
        }
        
        .metric:last-child {
            border-bottom: none;
        }
        
        .metric-label {
            color: #95a5a6;
            font-size: 0.9em;
        }
        
        .metric-value {
            font-weight: 600;
            font-size: 1.1em;
        }
        
        .big-number {
            font-size: 3em;
            font-weight: bold;
            text-align: center;
            margin: 20px 0;
        }
        
        .progress-ring {
            width: 120px;
            height: 120px;
            margin: 20px auto;
        }
        
        .progress-ring-circle {
            transition: stroke-dashoffset 0.5s;
            transform: rotate(-90deg);
            transform-origin: 50% 50%;
        }
        
        .time-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }
        
        .time-slot {
            text-align: center;
            padding: 8px;
            background: #2a2a2a;
            border-radius: 6px;
            font-size: 0.8em;
        }
        
        .time-slot.completed {
            background: #27ae60;
            color: white;
        }
        
        .time-slot.scheduled {
            background: #ff9933;
            color: white;
        }
        
        .time-slot.missed {
            background: #e74c3c;
            color: white;
        }
        
        .chart-container {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            height: 400px;
        }
        
        .alert-banner {
            background: #e74c3c;
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .alert-icon {
            font-size: 1.5em;
        }
        
        .refresh-indicator {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #ff9933;
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 0.9em;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #333;
        }
        
        th {
            background: #2a2a2a;
            font-weight: 600;
        }
        
        .delta-positive { color: #27ae60; }
        .delta-negative { color: #e74c3c; }
        .delta-neutral { color: #95a5a6; }
        
        .service-list {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-top: 10px;
        }
        
        .service-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px;
            background: #2a2a2a;
            border-radius: 6px;
        }
        
        .service-status {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        
        .last-update {
            text-align: center;
            color: #7f8c8d;
            margin-top: 30px;
            font-size: 0.9em;
        }
        
        .accordion {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 12px;
            margin: 20px 0;
            overflow: hidden;
        }
        
        .accordion-header {
            padding: 20px;
            cursor: pointer;
            background: #2a2a2a;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.3s;
        }
        
        .accordion-header:hover {
            background: #333;
        }
        
        .accordion-content {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
            padding: 0 20px;
        }
        
        .accordion-content.active {
            max-height: 1000px;
            padding: 20px;
        }
        
        .regime-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 10px;
        }
        
        .regime-card {
            background: #2a2a2a;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #ff9933;
        }
        
        .regime-card.bullish { border-left-color: #27ae60; }
        .regime-card.bearish { border-left-color: #e74c3c; }
        .regime-card.neutral { border-left-color: #f39c12; }
        .regime-card.volatile { border-left-color: #9b59b6; }
        
        .regime-title {
            font-weight: bold;
            font-size: 1.1em;
            margin-bottom: 10px;
            color: #ecf0f1;
        }
        
        .regime-description {
            color: #bdc3c7;
            font-size: 0.9em;
            line-height: 1.4;
        }
        
        .regime-indicators {
            margin-top: 10px;
            font-size: 0.85em;
            color: #95a5a6;
        }
        
        @media (max-width: 768px) {
            .status-grid {
                grid-template-columns: 1fr;
            }
            
            .time-grid {
                grid-template-columns: repeat(4, 1fr);
            }
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <h1>🏥 India-TS System Health Monitor</h1>
        
        <div class="refresh-indicator">
            <span id="refresh-countdown">Refreshing in 30s</span>
        </div>
        
        <div id="alerts-container"></div>
        
        <div class="status-grid">
            <!-- Market Status Card -->
            <div class="status-card" id="market-status-card">
                <div class="card-header">
                    <h3 class="card-title">📈 Market Status</h3>
                    <div class="status-indicator" id="market-indicator"></div>
                </div>
                <div id="market-content"></div>
            </div>
            
            <!-- Scanner Performance Card -->
            <div class="status-card" id="scanner-status-card">
                <div class="card-header">
                    <h3 class="card-title">📊 Scanner Performance</h3>
                    <div class="status-indicator" id="scanner-indicator"></div>
                </div>
                <div id="scanner-content"></div>
            </div>
            
            <!-- Regime Analysis Card -->
            <div class="status-card" id="regime-status-card">
                <div class="card-header">
                    <h3 class="card-title">🎯 Market Regime</h3>
                    <div class="status-indicator" id="regime-indicator"></div>
                </div>
                <div id="regime-content"></div>
            </div>
            
            <!-- System Services Card -->
            <div class="status-card" id="services-status-card">
                <div class="card-header">
                    <h3 class="card-title">⚙️ System Services</h3>
                    <div class="status-indicator" id="services-indicator"></div>
                </div>
                <div id="services-content"></div>
            </div>
            
            <!-- Learning System Card -->
            <div class="status-card" id="learning-status-card">
                <div class="card-header">
                    <h3 class="card-title">🧠 Learning System</h3>
                    <div class="status-indicator" id="learning-indicator"></div>
                </div>
                <div id="learning-content"></div>
            </div>
            
            <!-- Schedule Compliance Card -->
            <div class="status-card" id="schedule-status-card">
                <div class="card-header">
                    <h3 class="card-title">⏰ Schedule Compliance</h3>
                    <div class="status-indicator" id="schedule-indicator"></div>
                </div>
                <div id="schedule-content"></div>
            </div>
        </div>
        
        <!-- Run Schedule Timeline -->
        <div class="status-card">
            <h3 class="card-title">📅 Today's Run Schedule</h3>
            <div id="schedule-timeline"></div>
        </div>
        
        <!-- Signal Trends Chart -->
        <div class="chart-container">
            <h3 style="margin-bottom: 20px;">📊 Signal Trends (7 Days)</h3>
            <canvas id="signalChart"></canvas>
        </div>
        
        <!-- Detailed Metrics Table -->
        <div class="status-card">
            <h3 class="card-title">📈 Detailed Metrics</h3>
            <div id="detailed-metrics"></div>
        </div>
        
        <!-- Market Regime Guide Accordion -->
        <div class="accordion">
            <div class="accordion-header" onclick="toggleAccordion(this)">
                <h3 style="margin: 0;">💡 Market Regime Guide</h3>
                <span style="font-size: 1.5em;">▼</span>
            </div>
            <div class="accordion-content">
                <p style="margin-bottom: 20px; color: #95a5a6;">Understanding different market regimes helps in adapting trading strategies:</p>
                
                <div class="regime-grid">
                    <div class="regime-card bullish">
                        <div class="regime-title">🐂 BULLISH</div>
                        <div class="regime-description">
                            Strong upward momentum with consistent higher highs and higher lows. 
                            Markets are trending up with good breadth and positive sentiment.
                        </div>
                        <div class="regime-indicators">
                            <strong>Indicators:</strong> L/S Ratio > 3, Rising trend, Low volatility
                        </div>
                    </div>
                    
                    <div class="regime-card bullish">
                        <div class="regime-title">📈 UPTREND</div>
                        <div class="regime-description">
                            Moderate upward movement with occasional pullbacks. Generally positive 
                            but with less strength than a bullish regime.
                        </div>
                        <div class="regime-indicators">
                            <strong>Indicators:</strong> L/S Ratio 1.5-3, Positive trend, Normal volatility
                        </div>
                    </div>
                    
                    <div class="regime-card neutral">
                        <div class="regime-title">🔄 CHOPPY</div>
                        <div class="regime-description">
                            Sideways movement with no clear direction. Market oscillates within a 
                            range, making trend-following difficult.
                        </div>
                        <div class="regime-indicators">
                            <strong>Indicators:</strong> L/S Ratio near 1, Flat trend, Mixed signals
                        </div>
                    </div>
                    
                    <div class="regime-card bearish">
                        <div class="regime-title">📉 DOWNTREND</div>
                        <div class="regime-description">
                            Moderate downward movement with lower highs and lower lows. Selling 
                            pressure dominates but not extreme.
                        </div>
                        <div class="regime-indicators">
                            <strong>Indicators:</strong> L/S Ratio 0.3-0.7, Negative trend, Increasing volatility
                        </div>
                    </div>
                    
                    <div class="regime-card bearish">
                        <div class="regime-title">🐻 BEARISH</div>
                        <div class="regime-description">
                            Strong downward momentum with persistent selling. Markets are in clear 
                            decline with poor breadth.
                        </div>
                        <div class="regime-indicators">
                            <strong>Indicators:</strong> L/S Ratio < 0.3, Strong downtrend, High volatility
                        </div>
                    </div>
                    
                    <div class="regime-card volatile">
                        <div class="regime-title">⚡ VOLATILE</div>
                        <div class="regime-description">
                            High volatility with large price swings in both directions. Uncertainty 
                            dominates, making predictions difficult.
                        </div>
                        <div class="regime-indicators">
                            <strong>Indicators:</strong> India VIX > 20, Wide ranges, Rapid reversals
                        </div>
                    </div>
                </div>
                
                <div style="margin-top: 20px; padding: 15px; background: #2a2a2a; border-radius: 8px;">
                    <h4 style="margin-top: 0;">📊 Key Metrics Explained:</h4>
                    <ul style="margin: 10px 0; padding-left: 20px; color: #95a5a6;">
                        <li><strong>L/S Ratio:</strong> Long signals divided by Short signals. Higher = more bullish</li>
                        <li><strong>Trend Score:</strong> Momentum indicator based on scanner signals (0-5 scale)</li>
                        <li><strong>Market Score:</strong> Composite of trend (40%), breadth (40%), and volatility (20%)</li>
                        <li><strong>Confidence:</strong> AI model's certainty in regime classification (0-100%)</li>
                    </ul>
                </div>
            </div>
        </div>
        
        <div class="last-update">
            Last updated: <span id="last-update-time"></span>
        </div>
    </div>
    
    <script>
        let refreshCountdown = 30;
        let signalChart = null;
        
        function toggleAccordion(header) {
            const content = header.nextElementSibling;
            const arrow = header.querySelector('span');
            
            content.classList.toggle('active');
            arrow.textContent = content.classList.contains('active') ? '▲' : '▼';
        }
        
        function formatTimeAgo(timestamp) {
            if (!timestamp) return 'Never';
            const now = new Date();
            const then = new Date(timestamp);
            const diffMs = now - then;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMins / 60);
            
            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m ago`;
            if (diffHours < 24) return `${diffHours}h ${diffMins % 60}m ago`;
            return then.toLocaleString();
        }
        
        function getStatusClass(status) {
            if (status === 'good') return 'status-good';
            if (status === 'warning') return 'status-warning';
            return 'status-error';
        }
        
        function updateProgressRing(elementId, percentage) {
            const radius = 45;
            const circumference = 2 * Math.PI * radius;
            const offset = circumference - (percentage / 100) * circumference;
            
            const svg = `
                <svg class="progress-ring" viewBox="0 0 120 120">
                    <circle cx="60" cy="60" r="${radius}" fill="none" stroke="#333" stroke-width="10"/>
                    <circle class="progress-ring-circle" cx="60" cy="60" r="${radius}" 
                            fill="none" stroke="#ff9933" stroke-width="10"
                            stroke-dasharray="${circumference}"
                            stroke-dashoffset="${offset}"/>
                    <text x="60" y="65" text-anchor="middle" fill="white" font-size="24" font-weight="bold">
                        ${percentage}%
                    </text>
                </svg>
            `;
            
            document.getElementById(elementId).innerHTML = svg;
        }
        
        async function updateDashboard() {
            try {
                const response = await fetch('/api/comprehensive_health');
                const data = await response.json();
                
                // Update alerts
                if (data.alerts.length > 0) {
                    const alertsHtml = data.alerts.map(alert => `
                        <div class="alert-banner">
                            <span class="alert-icon">⚠️</span>
                            <div>
                                <strong>${alert.title}</strong>: ${alert.message}
                            </div>
                        </div>
                    `).join('');
                    document.getElementById('alerts-container').innerHTML = alertsHtml;
                } else {
                    document.getElementById('alerts-container').innerHTML = '';
                }
                
                // Update Market Status
                const marketCard = document.getElementById('market-status-card');
                const marketIndicator = document.getElementById('market-indicator');
                const marketStatus = data.market.is_open ? 'good' : 'warning';
                marketCard.className = `status-card ${marketStatus}`;
                marketIndicator.className = `status-indicator ${getStatusClass(marketStatus)}`;
                
                document.getElementById('market-content').innerHTML = `
                    <div class="big-number">${data.market.current_time}</div>
                    <div class="metric">
                        <span class="metric-label">Status</span>
                        <span class="metric-value">${data.market.is_open ? 'OPEN' : 'CLOSED'}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Session</span>
                        <span class="metric-value">${data.market.session}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Next Event</span>
                        <span class="metric-value">${data.market.next_event}</span>
                    </div>
                `;
                
                // Update Scanner Performance
                const scannerCard = document.getElementById('scanner-status-card');
                const scannerIndicator = document.getElementById('scanner-indicator');
                const scannerStatus = data.scanners.status;
                scannerCard.className = `status-card ${scannerStatus}`;
                scannerIndicator.className = `status-indicator ${getStatusClass(scannerStatus)}`;
                
                // Add status message based on staleness
                let statusMessage = '';
                if (scannerStatus === 'error') {
                    statusMessage = '<div style="color: #e74c3c; font-weight: bold; text-align: center; margin: 10px 0;">⚠️ SCANNERS MISSED SCHEDULED RUN!</div>';
                } else if (scannerStatus === 'warning') {
                    statusMessage = '<div style="color: #f39c12; font-weight: bold; text-align: center; margin: 10px 0;">⚠️ Scanner may miss next run</div>';
                }
                
                document.getElementById('scanner-content').innerHTML = `${statusMessage}
                    <div style="text-align: center; margin: 15px 0;">
                        <div style="display: inline-block; margin: 0 20px;">
                            <div class="big-number" style="color: #27ae60;">${data.scanners.long_signals}</div>
                            <div class="metric-label">Long Signals</div>
                        </div>
                        <div style="display: inline-block; margin: 0 20px;">
                            <div class="big-number" style="color: #e74c3c;">${data.scanners.short_signals}</div>
                            <div class="metric-label">Short Signals</div>
                        </div>
                    </div>
                    <div class="metric">
                        <span class="metric-label">L/S Ratio</span>
                        <span class="metric-value">${data.scanners.ls_ratio}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Last Long Scan</span>
                        <span class="metric-value">${formatTimeAgo(data.scanners.last_long_run)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Last Short Scan</span>
                        <span class="metric-value">${formatTimeAgo(data.scanners.last_short_run)}</span>
                    </div>
                `;
                
                // Update Regime Analysis
                const regimeCard = document.getElementById('regime-status-card');
                const regimeIndicator = document.getElementById('regime-indicator');
                const regimeStatus = data.regime.status;
                regimeCard.className = `status-card ${regimeStatus}`;
                regimeIndicator.className = `status-indicator ${getStatusClass(regimeStatus)}`;
                
                document.getElementById('regime-content').innerHTML = `
                    <div class="big-number" style="color: ${data.regime.regime_color};">
                        ${data.regime.current_regime}
                    </div>
                    <div id="confidence-ring"></div>
                    <div class="metric">
                        <span class="metric-label">Trend Score</span>
                        <span class="metric-value">${data.regime.trend_score}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Market Score</span>
                        <span class="metric-value">${data.regime.market_score}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Last Analysis</span>
                        <span class="metric-value">${formatTimeAgo(data.regime.last_update)}</span>
                    </div>
                `;
                
                updateProgressRing('confidence-ring', Math.round(data.regime.confidence * 100));
                
                // Update System Services
                const servicesCard = document.getElementById('services-status-card');
                const servicesIndicator = document.getElementById('services-indicator');
                const servicesStatus = data.services.status;
                servicesCard.className = `status-card ${servicesStatus}`;
                servicesIndicator.className = `status-indicator ${getStatusClass(servicesStatus)}`;
                
                const servicesHtml = data.services.services.map(service => `
                    <div class="service-item">
                        <div class="service-status ${service.running ? 'status-good' : 'status-error'}"></div>
                        <span>${service.name}</span>
                    </div>
                `).join('');
                
                document.getElementById('services-content').innerHTML = `
                    <div class="big-number">${data.services.running}/${data.services.total}</div>
                    <div class="service-list">${servicesHtml}</div>
                `;
                
                // Update Learning System
                const learningCard = document.getElementById('learning-status-card');
                const learningIndicator = document.getElementById('learning-indicator');
                const learningStatus = data.learning.status;
                learningCard.className = `status-card ${learningStatus}`;
                learningIndicator.className = `status-indicator ${getStatusClass(learningStatus)}`;
                
                document.getElementById('learning-content').innerHTML = `
                    <div id="accuracy-ring"></div>
                    <div class="metric">
                        <span class="metric-label">Predictions Today</span>
                        <span class="metric-value">${data.learning.predictions_today}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Learning Rate</span>
                        <span class="metric-value class="${data.learning.improvement_rate >= 0 ? 'delta-positive' : 'delta-negative'}">
                            ${data.learning.improvement_rate > 0 ? '+' : ''}${data.learning.improvement_rate}%/day
                        </span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Model Age</span>
                        <span class="metric-value">${data.learning.model_age}</span>
                    </div>
                `;
                
                updateProgressRing('accuracy-ring', Math.round(data.learning.accuracy * 100));
                
                // Update Schedule Compliance
                const scheduleCard = document.getElementById('schedule-status-card');
                const scheduleIndicator = document.getElementById('schedule-indicator');
                const scheduleStatus = data.schedule.status;
                scheduleCard.className = `status-card ${scheduleStatus}`;
                scheduleIndicator.className = `status-indicator ${getStatusClass(scheduleStatus)}`;
                
                document.getElementById('schedule-content').innerHTML = `
                    <div id="compliance-ring"></div>
                    <div class="metric">
                        <span class="metric-label">Runs Today</span>
                        <span class="metric-value">${data.schedule.runs_today}/${data.schedule.expected_runs}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Missed Runs</span>
                        <span class="metric-value">${data.schedule.missed_runs}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Next Run</span>
                        <span class="metric-value">${data.schedule.next_run}</span>
                    </div>
                `;
                
                updateProgressRing('compliance-ring', Math.round(data.schedule.compliance_rate * 100));
                
                // Update Schedule Timeline
                const timelineHtml = data.schedule.timeline.map(slot => `
                    <div class="time-slot ${slot.status}">
                        <div>${slot.time}</div>
                        <div style="font-size: 0.7em;">${slot.runs}</div>
                    </div>
                `).join('');
                document.getElementById('schedule-timeline').innerHTML = `<div class="time-grid">${timelineHtml}</div>`;
                
                // Update Signal Chart
                updateSignalChart(data.signal_history);
                
                // Update Detailed Metrics
                const metricsHtml = `
                    <table>
                        <thead>
                            <tr>
                                <th>Metric</th>
                                <th>Current</th>
                                <th>Previous</th>
                                <th>Change</th>
                                <th>% Change</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.detailed_metrics.map(metric => `
                                <tr>
                                    <td>${metric.name}</td>
                                    <td>${metric.current}</td>
                                    <td>${metric.previous}</td>
                                    <td class="${metric.change >= 0 ? 'delta-positive' : 'delta-negative'}">
                                        ${metric.change > 0 ? '+' : ''}${metric.change}
                                    </td>
                                    <td class="${metric.percent_change >= 0 ? 'delta-positive' : 'delta-negative'}">
                                        ${metric.percent_change > 0 ? '+' : ''}${metric.percent_change}%
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
                document.getElementById('detailed-metrics').innerHTML = metricsHtml;
                
                // Update last update time
                document.getElementById('last-update-time').textContent = new Date().toLocaleString();
                
            } catch (error) {
                console.error('Error updating dashboard:', error);
            }
        }
        
        function updateSignalChart(data) {
            const ctx = document.getElementById('signalChart').getContext('2d');
            
            if (signalChart) {
                signalChart.destroy();
            }
            
            signalChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.dates,
                    datasets: [{
                        label: 'Long Signals',
                        data: data.long_signals,
                        borderColor: '#27ae60',
                        backgroundColor: 'rgba(39, 174, 96, 0.1)',
                        tension: 0.1
                    }, {
                        label: 'Short Signals',
                        data: data.short_signals,
                        borderColor: '#e74c3c',
                        backgroundColor: 'rgba(231, 76, 60, 0.1)',
                        tension: 0.1
                    }, {
                        label: 'L/S Ratio',
                        data: data.ls_ratios,
                        borderColor: '#ff9933',
                        backgroundColor: 'rgba(255, 153, 51, 0.1)',
                        tension: 0.1,
                        yAxisID: 'y1'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: {
                                color: '#ffffff'
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: {
                                color: '#333'
                            },
                            ticks: {
                                color: '#ffffff'
                            }
                        },
                        y: {
                            position: 'left',
                            grid: {
                                color: '#333'
                            },
                            ticks: {
                                color: '#ffffff'
                            }
                        },
                        y1: {
                            position: 'right',
                            grid: {
                                drawOnChartArea: false
                            },
                            ticks: {
                                color: '#ffffff'
                            }
                        }
                    }
                }
            });
        }
        
        // Countdown timer
        setInterval(() => {
            refreshCountdown--;
            if (refreshCountdown <= 0) {
                refreshCountdown = 30;
                updateDashboard();
            }
            document.getElementById('refresh-countdown').textContent = `Refreshing in ${refreshCountdown}s`;
        }, 1000);
        
        // Initial load
        updateDashboard();
    </script>
</body>
</html>
'''

class VisualHealthMonitor:
    """Enhanced health monitoring with comprehensive metrics"""
    
    def __init__(self):
        self.base_dir = '/Users/maverick/PycharmProjects/India-TS'
        self.db_path = os.path.join(self.base_dir, 'Market_Regime/data/regime_learning.db')
        self.ist = IST
        
    def get_comprehensive_health(self):
        """Get all health metrics in one call"""
        now_ist = datetime.now(self.ist)
        
        return {
            'market': self._get_market_status(),
            'scanners': self._get_scanner_metrics(),
            'regime': self._get_regime_metrics(),
            'services': self._get_services_metrics(),
            'learning': self._get_learning_metrics(),
            'schedule': self._get_schedule_metrics(),
            'signal_history': self._get_signal_history(),
            'detailed_metrics': self._get_detailed_metrics(),
            'alerts': self._generate_alerts()
        }
    
    def _get_market_status(self):
        """Get current market status"""
        now_ist = datetime.now(self.ist)
        
        # Market hours
        market_open = now_ist.replace(hour=9, minute=15)
        market_close = now_ist.replace(hour=15, minute=30)
        pre_market_open = now_ist.replace(hour=9, minute=0)
        
        is_weekday = now_ist.weekday() < 5
        is_market_hours = market_open <= now_ist <= market_close
        
        if not is_weekday:
            session = "Weekend"
            next_event = "Market opens Monday 9:15 AM IST"
        elif now_ist < pre_market_open:
            session = "Pre-Open"
            next_event = "Pre-market at 9:00 AM IST"
        elif now_ist < market_open:
            session = "Pre-Market"
            next_event = f"Market opens at 9:15 AM IST"
        elif now_ist < market_close:
            session = "Regular Trading"
            next_event = f"Market closes at 3:30 PM IST"
        else:
            session = "Closed"
            next_event = "Market opens tomorrow at 9:15 AM IST"
        
        return {
            'current_time': now_ist.strftime('%I:%M %p IST'),
            'is_open': is_market_hours and is_weekday,
            'session': session,
            'next_event': next_event
        }
    
    def _get_scanner_metrics(self):
        """Get detailed scanner metrics"""
        results_dir = os.path.join(self.base_dir, 'Daily/results')
        results_dir_short = os.path.join(self.base_dir, 'Daily/results-s')  # Short results are in different dir
        today = datetime.now().strftime('%Y%m%d')
        
        metrics = {
            'long_signals': 0,
            'short_signals': 0,
            'ls_ratio': 'N/A',
            'last_long_run': None,
            'last_short_run': None,
            'status': 'good'
        }
        
        try:
            # Get latest files - changed to look for Excel files
            files = os.listdir(results_dir)
            long_files = [f for f in files if f.startswith(f'Long_Reversal_Daily_{today}') and f.endswith('.xlsx')]
            
            # Short files are in results-s directory
            if os.path.exists(results_dir_short):
                short_files = [f for f in os.listdir(results_dir_short) if f.startswith(f'Short_Reversal_Daily_{today}') and f.endswith('.xlsx')]
            else:
                short_files = []
            
            if long_files:
                latest_long = max(long_files)
                file_path = os.path.join(results_dir, latest_long)
                # Read Excel file to count signals
                import pandas as pd
                df = pd.read_excel(file_path)
                metrics['long_signals'] = len(df)
                
                # Use file modification time
                mtime = os.path.getmtime(file_path)
                metrics['last_long_run'] = datetime.fromtimestamp(mtime)
                
            if short_files:
                latest_short = max(short_files)
                file_path = os.path.join(results_dir_short, latest_short)
                # Read Excel file to count signals
                import pandas as pd
                df = pd.read_excel(file_path)
                metrics['short_signals'] = len(df)
                    
                # Use file modification time
                mtime = os.path.getmtime(file_path)
                metrics['last_short_run'] = datetime.fromtimestamp(mtime)
            
            # Calculate L/S ratio
            if metrics['short_signals'] > 0:
                metrics['ls_ratio'] = f"{metrics['long_signals'] / metrics['short_signals']:.2f}"
            elif metrics['long_signals'] > 0:
                metrics['ls_ratio'] = "∞"
            
            # Determine status based on staleness
            if not long_files or not short_files:
                metrics['status'] = 'error'
            else:
                last_run = max(metrics['last_long_run'] or datetime.min, 
                             metrics['last_short_run'] or datetime.min)
                minutes_ago = (datetime.now() - last_run).total_seconds() / 60
                
                # Set thresholds for scanner staleness
                if minutes_ago > 38:  # Critical - missed a scheduled run
                    metrics['status'] = 'error'
                elif minutes_ago > 32:  # Warning - getting close to missing
                    metrics['status'] = 'warning'
                else:
                    metrics['status'] = 'good'
                    
        except Exception as e:
            metrics['status'] = 'error'
            
        return metrics
    
    def _get_regime_metrics(self):
        """Get regime analysis metrics from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Get latest prediction
            query = '''
                SELECT 
                    predicted_regime,
                    confidence,
                    market_score,
                    indicators,
                    timestamp
                FROM regime_predictions
                ORDER BY timestamp DESC
                LIMIT 1
            '''
            
            result = conn.execute(query).fetchone()
            
            if result:
                regime = result[0]
                confidence = result[1]
                market_score = result[2]
                indicators_json = result[3]
                timestamp = result[4]
                
                # Parse indicators if available
                trend_score = 0
                if indicators_json:
                    try:
                        indicators = json.loads(indicators_json)
                        trend_score = indicators.get('trend_score', 0)
                    except:
                        pass
                
                regime_colors = {
                    'strong_uptrend': '#27ae60',
                    'uptrend': '#2ecc71',
                    'bullish': '#3498db',
                    'strong_downtrend': '#c0392b',
                    'downtrend': '#e74c3c',
                    'bearish': '#e67e22',
                    'volatile': '#9b59b6',
                    'volatile_bullish': '#8e44ad',
                    'volatile_bearish': '#d35400',
                    'sideways': '#f39c12',
                    'neutral': '#f39c12',
                    'choppy': '#95a5a6'
                }
                
                conn.close()
                
                return {
                    'current_regime': regime.upper().replace('_', ' '),
                    'regime_color': regime_colors.get(regime.lower(), '#95a5a6'),
                    'confidence': confidence * 100,  # Convert to percentage
                    'trend_score': f"{trend_score:.2f}",
                    'market_score': f"{market_score:.3f}",
                    'last_update': timestamp,
                    'status': 'good'
                }
            
            conn.close()
            
        except Exception as e:
            print(f"Error getting regime metrics: {e}")
            
        return {
            'current_regime': 'UNKNOWN',
            'regime_color': '#95a5a6',
            'confidence': 0,
            'trend_score': '0.00',
            'market_score': '0.000',
            'last_update': None,
            'status': 'error'
        }
    
    def _get_services_metrics(self):
        """Get service status metrics"""
        services = [
            ('Long Scanner', 'com.india-ts.long_reversal_daily'),
            ('Short Scanner', 'com.india-ts.short_reversal_daily'),
            ('Regime Analysis', 'com.india-ts.market_regime_analysis'),
            ('Dashboard', 'com.india-ts.market_regime_dashboard'),
            ('Consolidated Score', 'com.india-ts.consolidated_score'),
            ('Daily Action Plan', 'com.india-ts.daily_action_plan')
        ]
        
        result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
        loaded_services = result.stdout
        
        service_list = []
        running_count = 0
        
        for name, service_id in services:
            is_running = service_id in loaded_services
            if is_running:
                running_count += 1
            service_list.append({
                'name': name,
                'running': is_running
            })
        
        status = 'good' if running_count == len(services) else 'warning' if running_count > 3 else 'error'
        
        return {
            'services': service_list,
            'running': running_count,
            'total': len(services),
            'status': status
        }
    
    def _get_learning_metrics(self):
        """Get learning system metrics"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Get overall accuracy from all predictions with outcomes
            query = '''
                SELECT 
                    COUNT(CASE WHEN predicted_regime = actual_regime THEN 1 END) as correct,
                    COUNT(*) as total,
                    AVG(outcome_score) as avg_score
                FROM regime_predictions
                WHERE actual_regime IS NOT NULL
                AND actual_regime != ''
            '''
            result = conn.execute(query).fetchone()
            correct, total, avg_score = result
            accuracy = avg_score if avg_score is not None else 0
            
            # Get today's predictions
            today = datetime.now().strftime('%Y-%m-%d')
            today_query = '''
                SELECT COUNT(*) FROM regime_predictions
                WHERE substr(timestamp, 1, 10) = ?
            '''
            predictions_today = conn.execute(today_query, (today,)).fetchone()[0]
            
            # Get model age
            first_prediction = '''
                SELECT MIN(timestamp) FROM regime_predictions
            '''
            first = conn.execute(first_prediction).fetchone()[0]
            if first:
                # Handle timezone-aware timestamp
                try:
                    first_dt = datetime.fromisoformat(first.replace('T', ' ').split('+')[0])
                    model_age_days = (datetime.now() - first_dt).days
                    model_age = f"{model_age_days} days"
                except:
                    model_age = "Active"
            else:
                model_age = "New"
            
            # Get improvement rate by comparing recent vs older predictions
            improvement_query = '''
                WITH recent AS (
                    SELECT AVG(outcome_score) as recent_acc
                    FROM regime_predictions
                    WHERE actual_regime IS NOT NULL
                    AND timestamp >= datetime('now', '-7 days')
                ),
                older AS (
                    SELECT AVG(outcome_score) as older_acc
                    FROM regime_predictions
                    WHERE actual_regime IS NOT NULL
                    AND timestamp < datetime('now', '-7 days')
                    AND timestamp >= datetime('now', '-14 days')
                )
                SELECT recent.recent_acc, older.older_acc
                FROM recent, older
            '''
            result = conn.execute(improvement_query).fetchone()
            if result and result[0] is not None and result[1] is not None:
                improvement_rate = (result[0] - result[1]) * 100
            else:
                improvement_rate = 0
            
            conn.close()
            
            status = 'good' if accuracy > 0.6 else 'warning' if accuracy > 0.4 else 'error'
            
            return {
                'accuracy': accuracy,
                'predictions_today': predictions_today,
                'improvement_rate': improvement_rate,
                'model_age': model_age,
                'status': status
            }
        except Exception as e:
            print(f"Learning metrics error: {e}")
            return {
                'accuracy': 0,
                'predictions_today': 0,
                'improvement_rate': 0,
                'model_age': 'Unknown',
                'status': 'error'
            }
    
    def _get_schedule_metrics(self):
        """Get schedule compliance metrics"""
        now_ist = datetime.now(self.ist)
        
        # Market hours in IST
        market_open = now_ist.replace(hour=9, minute=15, second=0)
        market_close = now_ist.replace(hour=15, minute=30, second=0)
        
        # Calculate expected runs
        if now_ist.time() < market_open.time():
            expected_runs = 0
        elif now_ist.time() > market_close.time():
            expected_runs = 13  # Full day
        else:
            minutes_since_open = (now_ist - market_open).seconds / 60
            expected_runs = int(minutes_since_open / 30) + 1
        
        # Count actual runs
        results_dir = os.path.join(self.base_dir, 'Daily/results')
        today = datetime.now().strftime('%Y%m%d')
        
        try:
            files = os.listdir(results_dir)
            long_runs = len([f for f in files if f.startswith(f'Long_Reversal_Daily_{today}')])
            short_runs = len([f for f in files if f.startswith(f'Short_Reversal_Daily_{today}')])
            runs_today = min(long_runs, short_runs)  # Both should run together
        except:
            runs_today = 0
        
        compliance_rate = runs_today / max(expected_runs, 1)
        missed_runs = max(0, expected_runs - runs_today)
        
        # Build timeline
        timeline = []
        schedule_times = [
            (9, 15), (9, 45), (10, 15), (10, 45), (11, 15), (11, 45),
            (12, 15), (12, 45), (13, 15), (13, 45), (14, 15), (14, 45),
            (15, 15)
        ]
        
        for hour, minute in schedule_times:
            slot_time = now_ist.replace(hour=hour, minute=minute, second=0)
            
            # Check if this slot has run
            slot_hour_str = f"{hour:02d}{minute:02d}"
            has_run = any(slot_hour_str in f for f in files if today in f)
            
            if slot_time > now_ist:
                status = 'scheduled'
            elif has_run:
                status = 'completed'
            else:
                status = 'missed'
                
            timeline.append({
                'time': f"{hour:02d}:{minute:02d}",
                'status': status,
                'runs': '✓' if has_run else '○'
            })
        
        # Next run
        next_run = "Market Closed"
        for hour, minute in schedule_times:
            if hour > now_ist.hour or (hour == now_ist.hour and minute > now_ist.minute):
                next_run = f"{hour:02d}:{minute:02d} IST"
                break
        
        status = 'good' if compliance_rate > 0.8 else 'warning' if compliance_rate > 0.5 else 'error'
        
        return {
            'runs_today': runs_today,
            'expected_runs': expected_runs,
            'missed_runs': missed_runs,
            'compliance_rate': compliance_rate,
            'next_run': next_run,
            'timeline': timeline,
            'status': status
        }
    
    def _get_signal_history(self):
        """Get 7-day signal history for charting"""
        results_dir = os.path.join(self.base_dir, 'Daily/results')
        
        dates = []
        long_signals = []
        short_signals = []
        ls_ratios = []
        
        for days_back in range(6, -1, -1):
            date = (datetime.now() - timedelta(days=days_back))
            date_str = date.strftime('%Y%m%d')
            dates.append(date.strftime('%m/%d'))
            
            try:
                files = os.listdir(results_dir)
                
                # Get last file of the day
                long_files = [f for f in files if f.startswith(f'Long_Reversal_Daily_{date_str}') and f.endswith('.json')]
                short_files = [f for f in files if f.startswith(f'Short_Reversal_Daily_{date_str}') and f.endswith('.json')]
                
                long_count = 0
                short_count = 0
                
                if long_files:
                    with open(os.path.join(results_dir, max(long_files)), 'r') as f:
                        long_count = len(json.load(f))
                        
                if short_files:
                    with open(os.path.join(results_dir, max(short_files)), 'r') as f:
                        short_count = len(json.load(f))
                
                long_signals.append(long_count)
                short_signals.append(short_count)
                
                if short_count > 0:
                    ls_ratios.append(round(long_count / short_count, 2))
                else:
                    ls_ratios.append(5.0 if long_count > 0 else 1.0)
                    
            except:
                long_signals.append(0)
                short_signals.append(0)
                ls_ratios.append(1.0)
        
        return {
            'dates': dates,
            'long_signals': long_signals,
            'short_signals': short_signals,
            'ls_ratios': ls_ratios
        }
    
    def _get_detailed_metrics(self):
        """Get detailed metrics with comparisons"""
        metrics = []
        
        # Get today and yesterday data
        results_dir = os.path.join(self.base_dir, 'Daily/results')
        today = datetime.now().strftime('%Y%m%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        
        try:
            files = os.listdir(results_dir)
            
            # Signal counts
            today_long = [f for f in files if f.startswith(f'Long_Reversal_Daily_{today}') and f.endswith('.json')]
            today_short = [f for f in files if f.startswith(f'Short_Reversal_Daily_{today}') and f.endswith('.json')]
            yesterday_long = [f for f in files if f.startswith(f'Long_Reversal_Daily_{yesterday}') and f.endswith('.json')]
            yesterday_short = [f for f in files if f.startswith(f'Short_Reversal_Daily_{yesterday}') and f.endswith('.json')]
            
            # Long signals
            current_long = 0
            prev_long = 0
            if today_long:
                with open(os.path.join(results_dir, max(today_long)), 'r') as f:
                    current_long = len(json.load(f))
            if yesterday_long:
                with open(os.path.join(results_dir, max(yesterday_long)), 'r') as f:
                    prev_long = len(json.load(f))
                    
            metrics.append({
                'name': 'Long Signals',
                'current': current_long,
                'previous': prev_long,
                'change': current_long - prev_long,
                'percent_change': round(((current_long - prev_long) / max(prev_long, 1)) * 100, 1)
            })
            
            # Short signals
            current_short = 0
            prev_short = 0
            if today_short:
                with open(os.path.join(results_dir, max(today_short)), 'r') as f:
                    current_short = len(json.load(f))
            if yesterday_short:
                with open(os.path.join(results_dir, max(yesterday_short)), 'r') as f:
                    prev_short = len(json.load(f))
                    
            metrics.append({
                'name': 'Short Signals',
                'current': current_short,
                'previous': prev_short,
                'change': current_short - prev_short,
                'percent_change': round(((current_short - prev_short) / max(prev_short, 1)) * 100, 1)
            })
            
            # Total signals
            metrics.append({
                'name': 'Total Signals',
                'current': current_long + current_short,
                'previous': prev_long + prev_short,
                'change': (current_long + current_short) - (prev_long + prev_short),
                'percent_change': round((((current_long + current_short) - (prev_long + prev_short)) / max((prev_long + prev_short), 1)) * 100, 1)
            })
            
            # Scanner runs
            today_runs = len(today_long)
            yesterday_runs = len(yesterday_long)
            
            metrics.append({
                'name': 'Scanner Runs',
                'current': today_runs,
                'previous': yesterday_runs,
                'change': today_runs - yesterday_runs,
                'percent_change': round(((today_runs - yesterday_runs) / max(yesterday_runs, 1)) * 100, 1)
            })
            
        except Exception as e:
            pass
            
        return metrics
    
    def _generate_alerts(self):
        """Generate system alerts"""
        alerts = []
        
        # Check scanner freshness with proper thresholds
        scanner_metrics = self._get_scanner_metrics()
        
        # Check long scanner
        if scanner_metrics['last_long_run']:
            minutes_ago = (datetime.now() - scanner_metrics['last_long_run']).total_seconds() / 60
            if minutes_ago > 38:  # Missed scheduled run
                alerts.append({
                    'title': 'Long Scanner Failed',
                    'message': f'Last ran {int(minutes_ago)} minutes ago - MISSED SCHEDULED RUN!'
                })
            elif minutes_ago > 32:  # Warning threshold
                alerts.append({
                    'title': 'Long Scanner Warning',
                    'message': f'Last ran {int(minutes_ago)} minutes ago - may miss next run'
                })
        else:
            alerts.append({
                'title': 'Long Scanner Error',
                'message': 'No scanner results found today'
            })
            
        # Check short scanner
        if scanner_metrics['last_short_run']:
            minutes_ago = (datetime.now() - scanner_metrics['last_short_run']).total_seconds() / 60
            if minutes_ago > 38:  # Missed scheduled run
                alerts.append({
                    'title': 'Short Scanner Failed',
                    'message': f'Last ran {int(minutes_ago)} minutes ago - MISSED SCHEDULED RUN!'
                })
            elif minutes_ago > 32:  # Warning threshold
                alerts.append({
                    'title': 'Short Scanner Warning',
                    'message': f'Last ran {int(minutes_ago)} minutes ago - may miss next run'
                })
        else:
            alerts.append({
                'title': 'Short Scanner Error',
                'message': 'No scanner results found today'
            })
        
        # Check services
        services = self._get_services_metrics()
        if services['running'] < services['total']:
            down_services = [s['name'] for s in services['services'] if not s['running']]
            alerts.append({
                'title': 'Services Down',
                'message': f"Not running: {', '.join(down_services)}"
            })
        
        # Check learning accuracy
        learning = self._get_learning_metrics()
        if learning['accuracy'] < 0.5 and learning['predictions_today'] > 10:
            alerts.append({
                'title': 'Low Accuracy',
                'message': f'Model accuracy is only {learning["accuracy"]*100:.1f}%'
            })
        
        return alerts

# Flask routes
@app.route('/')
def index():
    return render_template_string(VISUAL_DASHBOARD_HTML)

@app.route('/api/comprehensive_health')
def comprehensive_health():
    monitor = VisualHealthMonitor()
    return jsonify(monitor.get_comprehensive_health())

if __name__ == '__main__':
    print("\n" + "="*60)
    print("INDIA-TS VISUAL HEALTH CHECK DASHBOARD")
    print("="*60)
    print(f"\nStarting dashboard at: http://localhost:7080")
    print("\nFeatures:")
    print("  ✓ Real-time system status monitoring")
    print("  ✓ Visual indicators and progress rings")
    print("  ✓ 7-day signal trend charts")
    print("  ✓ Detailed metrics with comparisons")
    print("  ✓ Automatic alerts for issues")
    print("  ✓ Schedule timeline visualization")
    print("\nPress Ctrl+C to stop")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=7080, debug=False)