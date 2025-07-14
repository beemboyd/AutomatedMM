#!/usr/bin/env python3
"""
Daily Market Regime Health Check Dashboard
Monitors the health of the Daily Market_Regime system
"""

from flask import Flask, render_template_string, jsonify
import os
import json
import glob
from datetime import datetime, timedelta
import pytz
import subprocess
from pathlib import Path

app = Flask(__name__)

# Timezone setup
IST = pytz.timezone('Asia/Kolkata')

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGIME_DIR = os.path.join(SCRIPT_DIR, 'regime_analysis')
SCAN_RESULTS_DIR = os.path.join(SCRIPT_DIR, 'scan_results')
TREND_DIR = os.path.join(SCRIPT_DIR, 'trend_analysis')
DATA_DIR = os.path.join(SCRIPT_DIR, 'data')
DAILY_DIR = os.path.dirname(SCRIPT_DIR)  # This is the Daily directory
RESULTS_DIR = os.path.join(DAILY_DIR, 'results')
RESULTS_SHORT_DIR = os.path.join(DAILY_DIR, 'results-s')
BASE_DIR = SCRIPT_DIR  # Add BASE_DIR for model performance path

# Dashboard HTML Template
HEALTH_DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>India-TS Daily Market Regime - Health Check</title>
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
            max-width: 1400px;
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
        }
        
        .status-card.good {
            border-color: #27ae60;
            background: #0a1a0a;
        }
        
        .status-card.warning {
            border-color: #f39c12;
            background: #1a1500;
        }
        
        .status-card.critical {
            border-color: #e74c3c;
            background: #1a0a0a;
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .card-title {
            font-size: 1.2em;
            font-weight: bold;
        }
        
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        .status-indicator.running {
            background: #27ae60;
        }
        
        .status-indicator.stopped {
            background: #e74c3c;
        }
        
        .status-indicator.warning {
            background: #f39c12;
        }
        
        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.6; transform: scale(0.9); }
            100% { opacity: 1; transform: scale(1); }
        }
        
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            margin: 10px 0;
        }
        
        .metric-label {
            color: #888;
            font-size: 0.9em;
        }
        
        .schedule-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(60px, 1fr));
            gap: 5px;
            margin-top: 10px;
        }
        
        .schedule-slot {
            background: #2a2a2a;
            border-radius: 4px;
            padding: 5px;
            text-align: center;
            font-size: 0.8em;
        }
        
        .schedule-slot.completed {
            background: #27ae60;
        }
        
        .schedule-slot.missed {
            background: #e74c3c;
        }
        
        .schedule-slot.pending {
            background: #34495e;
        }
        
        .timestamp {
            text-align: center;
            color: #888;
            margin-top: 20px;
            font-size: 0.9em;
        }
        
        .jobs-section {
            margin-top: 30px;
        }
        
        .jobs-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        
        .job-card {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .job-card.running {
            border-color: #27ae60;
            background: linear-gradient(to right, #0a1a0a, #1a1a1a);
        }
        
        .job-card.success {
            border-color: #2ecc71;
        }
        
        .job-card.error {
            border-color: #e74c3c;
            background: linear-gradient(to right, #1a0a0a, #1a1a1a);
        }
        
        .job-card.not-loaded {
            border-color: #555;
            opacity: 0.6;
        }
        
        .job-info {
            flex: 1;
        }
        
        .job-name {
            font-weight: bold;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        
        .job-schedule {
            color: #888;
            font-size: 0.8em;
        }
        
        .job-status {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .job-pid {
            color: #27ae60;
            font-size: 0.8em;
        }
        
        .job-exit-code {
            font-size: 0.8em;
        }
        
        .section-title {
            font-size: 1.8em;
            margin-bottom: 20px;
            color: #ff9933;
        }
        
        .jobs-summary {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .summary-item {
            background: #1a1a1a;
            padding: 15px 25px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #333;
        }
        
        .summary-count {
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .summary-label {
            color: #888;
            font-size: 0.9em;
        }
        
        .regime-display {
            background: #1a1a1a;
            border-radius: 12px;
            padding: 30px;
            text-align: center;
            margin-bottom: 30px;
            border: 2px solid;
        }
        
        .regime-display.strong_uptrend { border-color: #27ae60; }
        .regime-display.uptrend { border-color: #2ecc71; }
        .regime-display.choppy_bullish { border-color: #3498db; }
        .regime-display.choppy { border-color: #95a5a6; }
        .regime-display.choppy_bearish { border-color: #e67e22; }
        .regime-display.downtrend { border-color: #e74c3c; }
        .regime-display.strong_downtrend { border-color: #c0392b; }
        
        .regime-name {
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 10px;
        }
        
        .regime-confidence {
            font-size: 1.2em;
            color: #888;
        }
        
        .alert-box {
            background: #e74c3c;
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
        }
        
        .alert-box.show {
            display: block;
        }
    </style>
    <script>
        function updateDashboard() {
            fetch('/api/health')
                .then(response => response.json())
                .then(data => {
                    // Update regime display
                    const regimeDisplay = document.getElementById('regime-display');
                    if (data.current_regime) {
                        regimeDisplay.className = 'regime-display ' + data.current_regime.regime;
                        document.getElementById('regime-name').textContent = data.current_regime.regime.replace('_', ' ').toUpperCase();
                        document.getElementById('regime-confidence').textContent = 
                            `Confidence: ${(data.current_regime.confidence * 100).toFixed(1)}% (${data.current_regime.confidence_level})`;
                    }
                    
                    // Update scanner status
                    updateStatusCard('scanner-status', data.scanner_status);
                    updateStatusCard('regime-status', data.regime_analysis_status);
                    updateStatusCard('g-pattern-status', data.g_pattern_status);
                    
                    // Update metrics
                    document.getElementById('long-count').textContent = data.scanner_counts.long;
                    document.getElementById('short-count').textContent = data.scanner_counts.short;
                    document.getElementById('total-patterns').textContent = data.scanner_counts.total;
                    
                    // Update G Pattern metrics
                    if (data.g_pattern_counts) {
                        document.getElementById('g-confirmed').textContent = data.g_pattern_counts.confirmed;
                        document.getElementById('g-emerging').textContent = data.g_pattern_counts.emerging;
                        document.getElementById('g-watch').textContent = data.g_pattern_counts.watch;
                    }
                    
                    if (data.model_performance) {
                        document.getElementById('model-accuracy').textContent = 
                            (data.model_performance.accuracy * 100).toFixed(1) + '%';
                        document.getElementById('total-predictions').textContent = 
                            data.model_performance.total_predictions;
                    }
                    
                    // Update schedule
                    updateSchedule(data.schedule_status);
                    
                    // Update scores if available
                    if (data.scores) {
                        document.getElementById('market-score').textContent = 
                            (data.scores.market_score * 100).toFixed(1) + '%';
                        document.getElementById('trend-score').textContent = 
                            (data.scores.trend_score * 100).toFixed(1) + '%';
                        document.getElementById('volatility-score').textContent = 
                            data.scores.volatility_score ? (data.scores.volatility_score * 100).toFixed(1) + '%' : 'N/A';
                    }
                    
                    // Update alerts
                    const alertBox = document.getElementById('alert-box');
                    if (data.alerts && data.alerts.length > 0) {
                        alertBox.className = 'alert-box show';
                        alertBox.innerHTML = '<strong>Alerts:</strong><br>' + data.alerts.join('<br>');
                    } else {
                        alertBox.className = 'alert-box';
                    }
                    
                    // Update timestamp
                    document.getElementById('last-update').textContent = 
                        'Last updated: ' + new Date().toLocaleString();
                    
                    // Update jobs if available
                    if (data.jobs) {
                        updateJobs(data.jobs);
                    }
                    
                    // Update Macro/Micro View
                    updateMacroMicroView(data);
                });
        }
        
        function updateJobs(jobs) {
            const container = document.getElementById('jobs-grid');
            container.innerHTML = '';
            
            // Update summary counts
            let totalJobs = jobs.length;
            let runningJobs = 0;
            let successfulJobs = 0;
            let errorJobs = 0;
            
            jobs.forEach(job => {
                if (job.status_class === 'running') runningJobs++;
                else if (job.status_class === 'success') successfulJobs++;
                else if (job.status_class === 'error') errorJobs++;
            });
            
            document.getElementById('total-jobs').textContent = totalJobs;
            document.getElementById('running-jobs').textContent = runningJobs;
            document.getElementById('successful-jobs').textContent = successfulJobs;
            document.getElementById('error-jobs').textContent = errorJobs;
            
            jobs.forEach(job => {
                const card = document.createElement('div');
                card.className = 'job-card ' + job.status_class;
                
                let statusHtml = '';
                if (job.pid && job.pid !== '-') {
                    statusHtml = `<span class="job-pid">PID: ${job.pid}</span>`;
                } else if (job.exit_code !== undefined && job.exit_code !== '-') {
                    const codeClass = job.exit_code === '0' ? 'success' : 'error';
                    statusHtml = `<span class="job-exit-code ${codeClass}">Exit: ${job.exit_code}</span>`;
                } else {
                    statusHtml = `<span class="job-exit-code">Not loaded</span>`;
                }
                
                card.innerHTML = `
                    <div class="job-info">
                        <div class="job-name">${job.name}</div>
                        <div class="job-schedule">${job.schedule}</div>
                    </div>
                    <div class="job-status">
                        ${statusHtml}
                        <div class="status-indicator ${job.status_class}"></div>
                    </div>
                `;
                
                container.appendChild(card);
            });
        }
        
        function updateStatusCard(cardId, status) {
            const card = document.getElementById(cardId);
            const indicator = card.querySelector('.status-indicator');
            const statusText = card.querySelector('.status-text');
            
            card.className = 'status-card ' + status.level;
            indicator.className = 'status-indicator ' + status.state;
            statusText.textContent = status.message;
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
            if (data.current_regime) {
                const regime = data.current_regime.regime;
                const microStatus = regime.replace(/_/g, ' ').toUpperCase();
                const longCount = data.scanner_counts.long;
                const shortCount = data.scanner_counts.short;
                const ratio = longCount / (shortCount || 1);
                
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
                    <div style="margin: 5px 0;"><strong>L/S Ratio:</strong> ${ratio.toFixed(2)}</div>
                    <div style="margin: 5px 0;"><strong>Confidence:</strong> ${(data.current_regime.confidence * 100).toFixed(1)}%</div>
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
                        <div style="font-size: 1.1em; font-weight: bold; color: #e74c3c; margin-bottom: 10px;">⚠️ DIVERGENCE DETECTED</div>
                        <p style="margin: 0; font-size: 0.9em;">Macro and Micro views diverge - Reduce position sizes and wait for confirmation</p>
                    `;
                } else {
                    actionSummary.style.borderColor = '#2ecc71';
                    actionSummary.innerHTML = `
                        <div style="font-size: 1.1em; font-weight: bold; color: #2ecc71; margin-bottom: 10px;">✅ VIEWS ALIGNED</div>
                        <p style="margin: 0; font-size: 0.9em;">Both views align - Follow regime recommendations with confidence</p>
                    `;
                }
            }
        }
        
        function updateSchedule(scheduleData) {
            const container = document.getElementById('schedule-grid');
            container.innerHTML = '';
            
            scheduleData.slots.forEach(slot => {
                const div = document.createElement('div');
                div.className = 'schedule-slot ' + slot.status;
                div.textContent = slot.time;
                div.title = `${slot.time} - ${slot.status}`;
                container.appendChild(div);
            });
        }
        
        // Update every 30 seconds
        setInterval(updateDashboard, 30000);
        
        // Initial update
        updateDashboard();
    </script>
</head>
<body>
    <div class="container">
        <h1>India-TS Daily Market Regime - System Health</h1>
        
        <div id="alert-box" class="alert-box"></div>
        
        <div id="regime-display" class="regime-display">
            <div id="regime-name" class="regime-name">Loading...</div>
            <div id="regime-confidence" class="regime-confidence"></div>
        </div>
        
        <!-- Macro/Micro View Section -->
        <div class="status-card" style="margin-bottom: 20px;">
            <div class="card-header">
                <div class="card-title">🌍 Market Regime: Macro vs Micro View</div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 20px;">
                <!-- Macro View -->
                <div style="background: rgba(0,0,0,0.5); padding: 15px; border-radius: 8px; border: 1px solid #333;">
                    <h4 style="color: #3498db; margin-bottom: 10px;">🌐 MACRO VIEW (Index-Based)</h4>
                    <div id="macro-status" style="font-size: 1.5em; font-weight: bold; margin: 10px 0;">Loading...</div>
                    <p id="macro-recommendation" style="margin: 10px 0; font-size: 0.9em;">Analyzing indices...</p>
                    <div id="macro-details" style="margin-top: 10px; font-size: 0.85em;">
                        <!-- Index details will be populated here -->
                    </div>
                </div>
                
                <!-- Micro View -->
                <div style="background: rgba(0,0,0,0.5); padding: 15px; border-radius: 8px; border: 1px solid #333;">
                    <h4 style="color: #9b59b6; margin-bottom: 10px;">🔬 MICRO VIEW (Pattern-Based)</h4>
                    <div id="micro-status" style="font-size: 1.5em; font-weight: bold; margin: 10px 0;">Loading...</div>
                    <p id="micro-recommendation" style="margin: 10px 0; font-size: 0.9em;">Analyzing patterns...</p>
                    <div id="micro-details" style="margin-top: 10px; font-size: 0.85em;">
                        <!-- Pattern details will be populated here -->
                    </div>
                </div>
            </div>
            
            <!-- Action Summary -->
            <div id="action-summary" style="margin: 20px; padding: 15px; background: rgba(0,0,0,0.5); border-radius: 8px; text-align: center; border: 2px solid #2ecc71;">
                <div style="font-size: 1.1em; font-weight: bold; margin-bottom: 10px;">📈 Analyzing...</div>
                <p style="margin: 0; font-size: 0.9em;">Please wait while we analyze market conditions...</p>
            </div>
        </div>
        
        <div class="status-grid">
            <div id="scanner-status" class="status-card">
                <div class="card-header">
                    <div class="card-title">Scanner Status</div>
                    <div class="status-indicator"></div>
                </div>
                <div class="status-text">Checking...</div>
                <div class="metric-label">Long: <span id="long-count">-</span> | Short: <span id="short-count">-</span></div>
                <div class="metric-label">Total Patterns: <span id="total-patterns">-</span></div>
            </div>
            
            <div id="regime-status" class="status-card">
                <div class="card-header">
                    <div class="card-title">Regime Analysis</div>
                    <div class="status-indicator"></div>
                </div>
                <div class="status-text">Checking...</div>
                <div class="metric-label">Model Accuracy: <span id="model-accuracy">-</span></div>
                <div class="metric-label">Predictions: <span id="total-predictions">-</span></div>
            </div>
            
            <div id="g-pattern-status" class="status-card">
                <div class="card-header">
                    <div class="card-title">G Pattern Scanner</div>
                    <div class="status-indicator"></div>
                </div>
                <div class="status-text">Checking...</div>
                <div class="metric-label">Confirmed: <span id="g-confirmed">-</span> | Emerging: <span id="g-emerging">-</span></div>
                <div class="metric-label">Watch List: <span id="g-watch">-</span></div>
            </div>
            
            <div class="status-card">
                <div class="card-header">
                    <div class="card-title">Today's Schedule</div>
                </div>
                <div id="schedule-grid" class="schedule-grid"></div>
            </div>
            
            <div class="status-card">
                <div class="card-header">
                    <div class="card-title">Market Scores</div>
                </div>
                <div class="metric-label">Market Score: <span id="market-score">-</span></div>
                <div class="metric-label">Trend Score: <span id="trend-score">-</span></div>
                <div class="metric-label">Volatility Score: <span id="volatility-score">-</span></div>
            </div>
        </div>
        
        <div class="jobs-section">
            <h2 class="section-title">India-TS System Jobs</h2>
            <div class="jobs-summary">
                <div class="summary-item">
                    <div class="summary-count" id="total-jobs">0</div>
                    <div class="summary-label">Total Jobs</div>
                </div>
                <div class="summary-item">
                    <div class="summary-count" id="running-jobs" style="color: #27ae60;">0</div>
                    <div class="summary-label">Running</div>
                </div>
                <div class="summary-item">
                    <div class="summary-count" id="successful-jobs" style="color: #2ecc71;">0</div>
                    <div class="summary-label">Successful</div>
                </div>
                <div class="summary-item">
                    <div class="summary-count" id="error-jobs" style="color: #e74c3c;">0</div>
                    <div class="summary-label">Errors</div>
                </div>
            </div>
            <div id="jobs-grid" class="jobs-grid">
                <!-- Jobs will be populated here -->
            </div>
        </div>
        
        <div class="timestamp" id="last-update"></div>
    </div>
</body>
</html>
'''

def get_jobs_status():
    """Get status of all India-TS jobs from launchctl"""
    jobs_info = []
    
    # Define expected jobs with their schedules
    job_definitions = {
        'com.india-ts.brooks_reversal_4times': '9:30, 11:30, 13:30, 16:00',
        'com.india-ts.brooks_reversal_simple': 'Every 30 minutes',
        'com.india-ts.consolidated_score': '9:00 AM daily',
        'com.india-ts.daily_action_plan': '8:30 AM daily',
        'com.india-ts.health_dashboard': '24/7 (KeepAlive)',
        'com.india-ts.kc_g_pattern_scanner': '9:00 AM, 12:30 PM, 3:15 PM',
        'com.india-ts.long_reversal_daily': 'Every 30 min (9:00-15:30)',
        'com.india-ts.market_regime_analysis': 'Every 30 min (9:15-15:30)',
        'com.india-ts.market_regime_dashboard': '5:00 PM daily',
        'com.india-ts.short_reversal_daily': 'Every 30 min (9:00-15:30)',
        'com.india-ts.sl_watchdog_stop': '3:45 PM daily',
        'com.india-ts.strategyc_filter': '3:45 PM daily',
        'com.india-ts.synch_zerodha_local': 'Every 15 min (9:15-15:30)',
        'com.india-ts.weekly_backup': 'Saturdays 10:00 AM'
    }
    
    try:
        # Get launchctl list output
        result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            
            # Parse launchctl output
            launchctl_jobs = {}
            for line in lines:
                if 'india-ts' in line or 'indiaTS' in line:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        pid = parts[0].strip()
                        exit_code = parts[1].strip()
                        job_name = parts[2].strip()
                        launchctl_jobs[job_name] = {'pid': pid, 'exit_code': exit_code}
            
            # Build job list with status
            for job_name, schedule in job_definitions.items():
                job_info = {
                    'name': job_name.replace('com.india-ts.', '').replace('_', ' ').title(),
                    'full_name': job_name,
                    'schedule': schedule,
                    'pid': '-',
                    'exit_code': '-',
                    'status_class': 'not-loaded'
                }
                
                if job_name in launchctl_jobs:
                    job_data = launchctl_jobs[job_name]
                    job_info['pid'] = job_data['pid']
                    job_info['exit_code'] = job_data['exit_code']
                    
                    # Determine status class
                    if job_data['pid'] != '-':
                        job_info['status_class'] = 'running'
                    elif job_data['exit_code'] == '0':
                        job_info['status_class'] = 'success'
                    else:
                        job_info['status_class'] = 'error'
                
                jobs_info.append(job_info)
    
    except Exception as e:
        print(f"Error getting jobs status: {e}")
    
    return jobs_info

@app.route('/')
def index():
    return render_template_string(HEALTH_DASHBOARD_HTML)

@app.route('/api/health')
def get_health_status():
    """Get comprehensive health status of Daily Market Regime system"""
    now = datetime.now(IST)
    # Use IST date, not system date
    today = now.strftime('%Y%m%d')
    
    health_data = {
        'timestamp': now.isoformat(),
        'current_regime': None,
        'scanner_status': {'level': 'good', 'state': 'running', 'message': 'OK'},
        'regime_analysis_status': {'level': 'good', 'state': 'running', 'message': 'OK'},
        'scanner_counts': {'long': 0, 'short': 0, 'total': 0},
        'g_pattern_status': {'level': 'good', 'state': 'running', 'message': 'OK'},
        'g_pattern_counts': {'confirmed': 0, 'emerging': 0, 'watch': 0},
        'model_performance': None,
        'schedule_status': {'slots': []},
        'alerts': []
    }
    
    # Check current regime
    try:
        summary_file = os.path.join(REGIME_DIR, 'latest_regime_summary.json')
        if os.path.exists(summary_file):
            with open(summary_file, 'r') as f:
                regime_data = json.load(f)
                health_data['current_regime'] = {
                    'regime': regime_data['market_regime']['regime'],
                    'confidence': regime_data['market_regime']['confidence'],
                    'confidence_level': regime_data['market_regime']['confidence_level'],
                    'timestamp': regime_data['timestamp']
                }
                
                # Add index analysis if available
                if 'index_analysis' in regime_data:
                    health_data['index_analysis'] = regime_data['index_analysis']
                
                # Extract scores from trend_analysis
                if 'trend_analysis' in regime_data:
                    health_data['scores'] = {
                        'market_score': regime_data['trend_analysis'].get('market_score', 0),
                        'trend_score': regime_data['trend_analysis'].get('trend_score', 0),
                        'volatility_score': regime_data.get('volatility', {}).get('volatility_score', 0)
                    }
                
                # Check age
                regime_time = datetime.fromisoformat(regime_data['timestamp'])
                # Make regime_time timezone-aware if it isn't
                if regime_time.tzinfo is None:
                    regime_time = IST.localize(regime_time)
                age_minutes = (now - regime_time).total_seconds() / 60
                if age_minutes > 40:  # More than 40 minutes old
                    health_data['alerts'].append(f'Regime data is {age_minutes:.0f} minutes old')
                    health_data['regime_analysis_status'] = {
                        'level': 'warning', 
                        'state': 'warning',
                        'message': f'Stale ({age_minutes:.0f}m old)'
                    }
    except Exception as e:
        health_data['alerts'].append(f'Error reading regime data: {str(e)}')
        health_data['regime_analysis_status'] = {
            'level': 'critical',
            'state': 'stopped', 
            'message': 'Error'
        }
    
    # Check scanner results
    try:
        # Check for today's scanner files
        # The files use format: Long_Reversal_Daily_20250626_HHMMSS.xlsx
        long_files = glob.glob(os.path.join(RESULTS_DIR, f'Long_Reversal_Daily_{today}*.xlsx'))
        short_files = glob.glob(os.path.join(RESULTS_SHORT_DIR, f'Short_Reversal_Daily_{today}*.xlsx'))
        
        if not long_files:
            health_data['alerts'].append('No Long reversal results found today')
            health_data['scanner_status']['level'] = 'warning'
        if not short_files:
            health_data['alerts'].append('No Short reversal results found today')
            health_data['scanner_status']['level'] = 'warning'
            
        # Get counts from latest regime report
        if health_data['current_regime']:
            try:
                # Use the latest regime report instead of summary file
                regime_files = glob.glob(os.path.join(REGIME_DIR, f'regime_report_{today}_*.json'))
                if regime_files:
                    latest_regime = max(regime_files)  # Get the most recent file
                    with open(latest_regime, 'r') as f:
                        data = json.load(f)
                        counts = data.get('reversal_counts', {})
                        health_data['scanner_counts'] = {
                            'long': counts.get('long', 0),
                            'short': counts.get('short', 0),
                            'total': counts.get('total', 0)
                        }
                        # Also update scores if not already set
                        if 'scores' not in health_data and 'trend_analysis' in data:
                            health_data['scores'] = {
                                'market_score': data['trend_analysis'].get('market_score', 0),
                                'trend_score': data['trend_analysis'].get('trend_score', 0),
                                'volatility_score': data.get('volatility', {}).get('volatility_score', 0)
                            }
            except:
                pass
                
    except Exception as e:
        health_data['alerts'].append(f'Scanner check error: {str(e)}')
        health_data['scanner_status'] = {
            'level': 'critical',
            'state': 'stopped',
            'message': 'Error'
        }
    
    # Check model performance
    try:
        # Look for model performance file
        perf_file = os.path.join(BASE_DIR, 'predictions', 'model_performance.json')
        if os.path.exists(perf_file):
            with open(perf_file, 'r') as f:
                data = json.load(f)
                if 'performance' in data:
                    perf = data['performance']
                    health_data['model_performance'] = {
                        'accuracy': perf.get('accuracy', 0),
                        'total_predictions': perf.get('total_predictions', 0)
                    }
    except:
        pass
    
    # Generate schedule status (30-minute intervals from 9:30 to 15:30)
    schedule_slots = []
    start_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
    end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    current_slot = start_time
    while current_slot <= end_time:
        slot_time = current_slot.strftime('%H:%M')
        
        if current_slot > now:
            status = 'pending'
        else:
            # Check if we have results around this time
            slot_date = current_slot.strftime('%H%M')
            # Check if we have regime reports from around this time (within 5 minutes)
            regime_files = glob.glob(os.path.join(REGIME_DIR, f'regime_report_{today}_{slot_date[:2]}*.json'))
            if regime_files:
                status = 'completed'
            else:
                status = 'missed' if current_slot < now - timedelta(minutes=5) else 'pending'
        
        schedule_slots.append({
            'time': slot_time,
            'status': status
        })
        
        current_slot += timedelta(minutes=30)
    
    health_data['schedule_status']['slots'] = schedule_slots
    
    # Get G Pattern data
    try:
        g_pattern_summary = os.path.join(DAILY_DIR, 'G_Pattern_Master', 'G_Pattern_Summary.txt')
        if os.path.exists(g_pattern_summary):
            g_pattern_counts = {'confirmed': 0, 'emerging': 0, 'watch': 0}
            with open(g_pattern_summary, 'r') as f:
                content = f.read()
                # Count stocks in each category
                if 'G PATTERN CONFIRMED' in content:
                    confirmed_section = content.split('G PATTERN CONFIRMED')[1].split('PATTERN EMERGING')[0]
                    g_pattern_counts['confirmed'] = confirmed_section.count('Score')
                if 'PATTERN EMERGING' in content:
                    emerging_section = content.split('PATTERN EMERGING')[1].split('WATCH CLOSELY')[0]
                    g_pattern_counts['emerging'] = emerging_section.count('Score')
                if 'WATCH CLOSELY' in content:
                    watch_section = content.split('WATCH CLOSELY')[1].split('WATCH ONLY')[0]
                    g_pattern_counts['watch'] = watch_section.count('Score')
            
            health_data['g_pattern_counts'] = g_pattern_counts
            health_data['g_pattern_status'] = {
                'level': 'good',
                'state': 'running',
                'message': f'{g_pattern_counts["confirmed"]} confirmed, {g_pattern_counts["emerging"]} emerging'
            }
        
        # Check for latest KC scanner results
        kc_results = glob.glob(os.path.join(DAILY_DIR, 'results', f'KC_Upper_Limit_Trending_{today}_*.xlsx'))
        if kc_results:
            latest_kc = max(kc_results)
            file_time = datetime.fromtimestamp(os.path.getmtime(latest_kc))
            if file_time.tzinfo is None:
                file_time = IST.localize(file_time)
            age_minutes = (now - file_time).total_seconds() / 60
            if age_minutes > 240:  # More than 4 hours old
                health_data['g_pattern_status'] = {
                    'level': 'warning',
                    'state': 'warning',
                    'message': f'Scanner data is {age_minutes:.0f}m old'
                }
    except Exception as e:
        health_data['g_pattern_status'] = {
            'level': 'warning',
            'state': 'stopped',
            'message': 'Data unavailable'
        }
        health_data['g_pattern_counts'] = {'confirmed': 0, 'emerging': 0, 'watch': 0}
    
    # Get India-TS jobs status
    health_data['jobs'] = get_jobs_status()
    
    return jsonify(health_data)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Daily Market Regime - Health Check Dashboard")
    print("="*60)
    print(f"\nDashboard URL: http://localhost:7080")
    print("\nPress Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=7080, debug=False)