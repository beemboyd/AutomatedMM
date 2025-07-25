#!/usr/bin/env python3
"""
India-TS Job Manager Dashboard
Provides web interface to monitor and control all scheduled jobs and dashboards
"""

import os
import sys
import json
import time
import subprocess
import logging
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import threading
import psutil
import pytz

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Time restriction function
def is_within_market_hours():
    """Check if current time is between 9:00 AM and 4:00 PM IST"""
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist)
    
    # Extended hours: 9:00 AM to 4:00 PM
    market_start = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
    market_end = current_time.replace(hour=16, minute=0, second=0, microsecond=0)
    
    return market_start <= current_time <= market_end

# Job definitions with their details
JOBS = {
    'com.india-ts.brooks_reversal_4times': {
        'name': 'Brooks Reversal 4 Times',
        'script': 'Al_Brooks_Higher_Probability_Reversal.py',
        'schedule': '9:30, 11:30, 13:30, 16:00 (Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/analysis'
    },
    'com.india-ts.brooks_reversal_simple': {
        'name': 'Brooks Reversal Simple',
        'script': 'brooks_reversal_scheduler.py',
        'schedule': 'Every 30 minutes (RunAtLoad)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/analysis'
    },
    'com.india-ts.consolidated_score': {
        'name': 'Consolidated Score',
        'script': 'Action_Plan_Score.py',
        'schedule': '9:00 AM daily (Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/analysis'
    },
    'com.india-ts.daily_action_plan': {
        'name': 'Daily Action Plan',
        'script': 'Action_plan.py',
        'schedule': '8:30 AM daily (Mon-Fri, RunAtLoad)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/analysis'
    },
    'com.india-ts.long_reversal_daily': {
        'name': 'Long Reversal Daily',
        'script': 'Long_Reversal_Daily.py',
        'schedule': 'Every 30 min (9:00-15:30, Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/scanners'
    },
    'com.india-ts.short_reversal_daily': {
        'name': 'Short Reversal Daily',
        'script': 'Short_Reversal_Daily.py',
        'schedule': 'Every 30 min (9:00-15:30, Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/scanners'
    },
    'com.india-ts.fno_liquid_reversal_scanners': {
        'name': 'FNO Liquid Reversal Scanners',
        'script': 'run_fno_liquid_reversal_scanners.py',
        'schedule': 'Every hour at :19 (9:19-15:19, Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/scanners'
    },
    'com.india-ts.market_breadth_scanner': {
        'name': 'Market Breadth Scanner',
        'script': 'Market_Breadth_Scanner.py',
        'schedule': 'Every 30 min (9:00-15:30, Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime'
    },
    'com.india-ts.health_dashboard': {
        'name': 'Health Dashboard',
        'script': 'dashboard_health_check.py',
        'schedule': '24/7 (KeepAlive, RunAtLoad)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime',
        'port': 7080
    },
    'com.india-ts.market_regime_dashboard': {
        'name': 'Market Regime Dashboard',
        'script': 'dashboard_enhanced.py',
        'schedule': '24/7 (KeepAlive, RunAtLoad)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime',
        'port': 8080
    },
    'com.india-ts.market_regime_analyzer_5min': {
        'name': 'Market Regime Analyzer (5-min)',
        'script': 'run_regime_analyzer_5min.sh',
        'schedule': 'Every 5 min (9:00-15:30, Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime'
    },
    'com.india-ts.sl_watchdog_stop': {
        'name': 'SL Watchdog Stop',
        'script': 'pkill -f "SL_watchdog.py.*India-TS"',
        'schedule': '3:30 PM daily (Mon-Fri)',
        'path': 'N/A'
    },
    'com.india-ts.strategyc_filter': {
        'name': 'Strategy C Filter',
        'script': 'StrategyC_Auto.py',
        'schedule': '9:45, 11:45, 13:45, 16:15 (Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/trading'
    },
    'com.india-ts.synch_zerodha_local': {
        'name': 'Sync Zerodha Local',
        'script': 'synch_zerodha_cnc_positions.py --force',
        'schedule': 'Every 15 min (9:15-15:30, Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/utils'
    },
    'com.india-ts.weekly_backup': {
        'name': 'Weekly Backup',
        'script': 'weekly_backup.sh',
        'schedule': 'Sundays 3:00 AM',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/utils'
    },
    'com.india-ts.kc_upper_limit_trending': {
        'name': 'KC Upper Limit Trending',
        'script': 'KC_Upper_Limit_Trending.py',
        'schedule': 'Every 30 min (9:00-15:30, Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/scanners'
    },
    'com.india-ts.kc_lower_limit_trending': {
        'name': 'KC Lower Limit Trending',
        'script': 'KC_Lower_Limit_Trending.py',
        'schedule': 'Every 30 min (9:00-15:30, Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/scanners'
    },
    'com.india-ts.kc_upper_limit_trending_fno': {
        'name': 'KC Upper Limit Trending FNO',
        'script': 'KC_Upper_Limit_Trending_FNO.py',
        'schedule': 'Every 30 min (9:00-15:30, Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/scanners'
    },
    'com.india-ts.kc_lower_limit_trending_fno': {
        'name': 'KC Lower Limit Trending FNO',
        'script': 'KC_Lower_Limit_Trending_FNO.py',
        'schedule': 'Every 30 min (9:00-15:30, Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/scanners'
    },
    'com.india-ts.g_pattern_master_tracker': {
        'name': 'G Pattern Master Tracker',
        'script': 'g_pattern_master_tracker.py',
        'schedule': 'Every 30 min (9:00-15:30, Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/G_Pattern_Master'
    },
    'com.tradingsystem.momentum.analyzer': {
        'name': 'Strong Momentum Candidates',
        'script': 'run_momentum_analysis.py --force',
        'schedule': 'Every hour at :15 (9:15-15:15, Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/scanners/Filtered'
    },
    'com.india-ts.long_reversal_fno': {
        'name': 'Long Reversal FNO',
        'script': 'Long_Reversal_Daily_FNO.py',
        'schedule': 'Every hour at :19 (9:19-15:19, Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/scanners'
    },
    'com.india-ts.short_reversal_fno': {
        'name': 'Short Reversal FNO',
        'script': 'Short_Reversal_Daily_FNO.py',
        'schedule': 'Every hour at :19 (9:19-15:19, Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/scanners'
    },
    'com.india-ts.vsr-tracker-enhanced': {
        'name': 'VSR Enhanced Tracker',
        'script': 'vsr_tracker_service_enhanced.py',
        'schedule': '9:15 AM (Mon-Fri, Runs continuously)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/services'
    },
    'com.india-ts.vsr-dashboard': {
        'name': 'VSR Dashboard Service',
        'script': 'vsr_tracker_dashboard.py',
        'schedule': '9:15 AM (Mon-Fri, RunAtLoad)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards'
    },
    'com.india-ts.vsr-shutdown': {
        'name': 'VSR Shutdown Service',
        'script': 'stop_vsr_services.py',
        'schedule': '3:30 PM (Mon-Fri)',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/scripts'
    }
}

# Dashboard definitions - handled separately
DASHBOARDS = {
    'health_dashboard_manual': {
        'name': 'Health Dashboard (Manual)',
        'script': 'dashboard_health_check.py',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime',
        'port': 7080,
        'start_script': None,  # Managed by launchctl
        'stop_script': None
    },
    'market_regime_dashboard_manual': {
        'name': 'Market Regime Dashboard (Manual)',
        'script': 'dashboard_enhanced.py',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime',
        'port': 8080,
        'start_script': None,  # Managed by launchctl
        'stop_script': None
    },
    'market_breadth_dashboard': {
        'name': 'Market Breadth Dashboard',
        'script': 'market_breadth_dashboard.py',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime',
        'port': 5001,
        'start_script': '/Users/maverick/PycharmProjects/India-TS/Daily/utils/start_market_breadth_dashboard.sh',
        'stop_script': '/Users/maverick/PycharmProjects/India-TS/Daily/utils/stop_market_breadth_dashboard.sh'
    },
    'job_manager_dashboard': {
        'name': 'Job Manager Dashboard (This Dashboard)',
        'script': 'job_manager_dashboard.py',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/Health',
        'port': 9090,
        'start_script': '/Users/maverick/PycharmProjects/India-TS/Daily/Health/start_job_manager.sh',
        'stop_script': '/Users/maverick/PycharmProjects/India-TS/Daily/Health/stop_job_manager.sh'
    },
    'vsr_tracker_dashboard': {
        'name': 'VSR Tracker Dashboard',
        'script': 'vsr_tracker_dashboard.py',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards',
        'port': 3001,
        'start_script': '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards/start_vsr_dashboard.sh',
        'stop_script': '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards/stop_vsr_dashboard.sh'
    },
    'sl_watchdog_dashboard': {
        'name': 'SL Watchdog Dashboard',
        'script': 'sl_watchdog_dashboard.py',
        'path': '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards',
        'port': 2001,
        'start_script': '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards/start_sl_watchdog_dashboard.sh',
        'stop_script': None
    }
}

def get_dashboard_status(dashboard_info):
    """Get status of a dashboard by checking if it's running on its port"""
    try:
        port = dashboard_info.get('port')
        if not port:
            return {'status': 'unknown', 'pid': None}
        
        # Check if something is listening on the port
        result = subprocess.run(['lsof', '-i', f':{port}'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # First line is header
                # Parse the output to get PID
                parts = lines[1].split()
                if len(parts) >= 2:
                    pid = parts[1]
                    return {'status': 'running', 'pid': pid}
        
        return {'status': 'stopped', 'pid': None}
    except Exception as e:
        logger.error(f"Error getting dashboard status: {e}")
        return {'status': 'unknown', 'pid': None, 'error': str(e)}

def get_job_status(job_id):
    """Get status of a specific job"""
    try:
        result = subprocess.run(['launchctl', 'list', job_id], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                parts = output.split('\t')
                if len(parts) >= 3:
                    pid = parts[0]
                    exit_code = parts[1]
                    
                    if pid != '-':
                        return {
                            'status': 'running',
                            'pid': pid,
                            'exit_code': None
                        }
                    else:
                        exit_code_int = int(exit_code) if exit_code != '-' else None
                        if exit_code_int == 0:
                            return {
                                'status': 'success',
                                'pid': None,
                                'exit_code': exit_code_int
                            }
                        elif exit_code_int is not None:
                            return {
                                'status': 'error',
                                'pid': None,
                                'exit_code': exit_code_int
                            }
        
        return {
            'status': 'not_loaded',
            'pid': None,
            'exit_code': None
        }
    except Exception as e:
        logger.error(f"Error getting status for {job_id}: {e}")
        return {
            'status': 'unknown',
            'pid': None,
            'exit_code': None,
            'error': str(e)
        }

def reload_job(job_id):
    """Reload a job (unload and load)"""
    try:
        # Determine the correct plist path
        plist_paths = [
            f'/Users/maverick/Library/LaunchAgents/{job_id}.plist',
            f'/Library/LaunchDaemons/{job_id}.plist'
        ]
        
        plist_path = None
        for path in plist_paths:
            if os.path.exists(path):
                plist_path = path
                break
        
        if not plist_path:
            return {'success': False, 'message': f'Plist file not found for {job_id}'}
        
        # First unload
        subprocess.run(['launchctl', 'unload', plist_path], 
                      capture_output=True, text=True)
        time.sleep(1)
        
        # Then load
        result = subprocess.run(['launchctl', 'load', plist_path], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            return {'success': True, 'message': f'Job {job_id} reloaded successfully'}
        else:
            return {'success': False, 'message': result.stderr}
    except Exception as e:
        logger.error(f"Error reloading job {job_id}: {e}")
        return {'success': False, 'message': str(e)}

def restart_job(job_id):
    """Restart a job (stop and start)"""
    try:
        # Stop the job
        subprocess.run(['launchctl', 'stop', job_id], capture_output=True, text=True)
        time.sleep(2)
        
        # Start the job
        result = subprocess.run(['launchctl', 'start', job_id], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            return {'success': True, 'message': f'Job {job_id} restarted successfully'}
        else:
            return {'success': False, 'message': result.stderr}
    except Exception as e:
        logger.error(f"Error restarting job {job_id}: {e}")
        return {'success': False, 'message': str(e)}

def stop_job(job_id):
    """Stop a job"""
    try:
        result = subprocess.run(['launchctl', 'stop', job_id], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            return {'success': True, 'message': f'Job {job_id} stopped successfully'}
        else:
            return {'success': False, 'message': result.stderr}
    except Exception as e:
        logger.error(f"Error stopping job {job_id}: {e}")
        return {'success': False, 'message': str(e)}

def start_dashboard(dashboard_id):
    """Start a dashboard using its start script"""
    try:
        dashboard = DASHBOARDS.get(dashboard_id)
        if not dashboard:
            return {'success': False, 'message': 'Invalid dashboard ID'}
        
        # Check if this is a launchctl-managed dashboard
        if dashboard_id == 'health_dashboard_manual':
            # Use launchctl to start
            result = subprocess.run(['launchctl', 'start', 'com.india-ts.health_dashboard'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return {'success': True, 'message': f'{dashboard["name"]} started successfully'}
            else:
                return {'success': False, 'message': result.stderr or 'Failed to start via launchctl'}
        elif dashboard_id == 'market_regime_dashboard_manual':
            # Use launchctl to start
            result = subprocess.run(['launchctl', 'start', 'com.india-ts.market_regime_dashboard'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return {'success': True, 'message': f'{dashboard["name"]} started successfully'}
            else:
                return {'success': False, 'message': result.stderr or 'Failed to start via launchctl'}
        
        start_script = dashboard.get('start_script')
        if not start_script:
            return {'success': False, 'message': 'No start script defined'}
        
        result = subprocess.run([start_script], capture_output=True, text=True)
        
        if result.returncode == 0:
            return {'success': True, 'message': f'{dashboard["name"]} started successfully'}
        else:
            return {'success': False, 'message': result.stderr or result.stdout}
    except Exception as e:
        logger.error(f"Error starting dashboard {dashboard_id}: {e}")
        return {'success': False, 'message': str(e)}

def stop_dashboard(dashboard_id):
    """Stop a dashboard using its stop script or by killing the process"""
    try:
        dashboard = DASHBOARDS.get(dashboard_id)
        if not dashboard:
            return {'success': False, 'message': 'Invalid dashboard ID'}
        
        # Check if this is a launchctl-managed dashboard
        if dashboard_id == 'health_dashboard_manual':
            # Use launchctl to stop
            result = subprocess.run(['launchctl', 'stop', 'com.india-ts.health_dashboard'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return {'success': True, 'message': f'{dashboard["name"]} stopped successfully'}
            else:
                return {'success': False, 'message': result.stderr or 'Failed to stop via launchctl'}
        elif dashboard_id == 'market_regime_dashboard_manual':
            # Use launchctl to stop
            result = subprocess.run(['launchctl', 'stop', 'com.india-ts.market_regime_dashboard'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return {'success': True, 'message': f'{dashboard["name"]} stopped successfully'}
            else:
                return {'success': False, 'message': result.stderr or 'Failed to stop via launchctl'}
        
        # Try using stop script first
        stop_script = dashboard.get('stop_script')
        if stop_script and os.path.exists(stop_script):
            result = subprocess.run([stop_script], capture_output=True, text=True)
            if result.returncode == 0:
                return {'success': True, 'message': f'{dashboard["name"]} stopped successfully'}
        
        # Fallback to killing by port
        port = dashboard.get('port')
        if port:
            subprocess.run(['pkill', '-f', f'port={port}'], capture_output=True)
            # Also try lsof method
            result = subprocess.run(['lsof', '-t', f'-i:{port}'], capture_output=True, text=True)
            if result.stdout:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    subprocess.run(['kill', '-9', pid], capture_output=True)
            
            return {'success': True, 'message': f'{dashboard["name"]} stopped'}
        
        return {'success': False, 'message': 'Could not stop dashboard'}
    except Exception as e:
        logger.error(f"Error stopping dashboard {dashboard_id}: {e}")
        return {'success': False, 'message': str(e)}

def restart_dashboard(dashboard_id):
    """Restart a dashboard"""
    try:
        # First stop
        stop_result = stop_dashboard(dashboard_id)
        if not stop_result['success']:
            return stop_result
        
        time.sleep(2)
        
        # Then start
        return start_dashboard(dashboard_id)
    except Exception as e:
        logger.error(f"Error restarting dashboard {dashboard_id}: {e}")
        return {'success': False, 'message': str(e)}

@app.route('/')
def index():
    """Main dashboard page"""
    if not is_within_market_hours():
        # Return a simple message when outside market hours
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>India-TS Job Manager</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                    background-color: #f5f5f5;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                }
                .message-container {
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    text-align: center;
                }
                h1 {
                    color: #333;
                    margin-bottom: 20px;
                }
                p {
                    color: #666;
                    font-size: 18px;
                    margin: 10px 0;
                }
                .time {
                    color: #2196F3;
                    font-weight: bold;
                }
            </style>
        </head>
        <body>
            <div class="message-container">
                <h1>India-TS Job Manager Dashboard</h1>
                <p>This dashboard is only available during market hours</p>
                <p class="time">9:00 AM - 4:00 PM IST</p>
                <p>Please access during market hours</p>
            </div>
        </body>
        </html>
        '''
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/jobs')
def get_jobs():
    """Get all jobs with their current status"""
    if not is_within_market_hours():
        return jsonify({'error': 'Dashboard only available during market hours (9:00 AM - 4:00 PM IST)'}), 403
    
    jobs_data = []
    
    # Add regular jobs
    for job_id, job_info in JOBS.items():
        status_info = get_job_status(job_id)
        jobs_data.append({
            'id': job_id,
            'name': job_info['name'],
            'script': job_info['script'],
            'schedule': job_info['schedule'],
            'path': job_info['path'],
            'port': job_info.get('port'),
            'type': 'job',
            **status_info
        })
    
    # Add dashboards
    for dashboard_id, dashboard_info in DASHBOARDS.items():
        status_info = get_dashboard_status(dashboard_info)
        jobs_data.append({
            'id': dashboard_id,
            'name': dashboard_info['name'],
            'script': dashboard_info['script'],
            'schedule': 'Manual/On-demand',
            'path': dashboard_info['path'],
            'port': dashboard_info.get('port'),
            'type': 'dashboard',
            **status_info
        })
    
    return jsonify({
        'jobs': jobs_data,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/job/<job_id>/reload', methods=['POST'])
def api_reload_job(job_id):
    """Reload a specific job"""
    if not is_within_market_hours():
        return jsonify({'error': 'Dashboard only available during market hours (9:00 AM - 4:00 PM IST)'}), 403
    
    if job_id not in JOBS:
        return jsonify({'success': False, 'message': 'Invalid job ID'}), 404
    
    result = reload_job(job_id)
    return jsonify(result)

@app.route('/api/job/<job_id>/restart', methods=['POST'])
def api_restart_job(job_id):
    """Restart a specific job"""
    if not is_within_market_hours():
        return jsonify({'error': 'Dashboard only available during market hours (9:00 AM - 4:00 PM IST)'}), 403
    
    if job_id not in JOBS:
        return jsonify({'success': False, 'message': 'Invalid job ID'}), 404
    
    result = restart_job(job_id)
    return jsonify(result)

@app.route('/api/job/<job_id>/stop', methods=['POST'])
def api_stop_job(job_id):
    """Stop a specific job"""
    if not is_within_market_hours():
        return jsonify({'error': 'Dashboard only available during market hours (9:00 AM - 4:00 PM IST)'}), 403
    
    if job_id not in JOBS:
        return jsonify({'success': False, 'message': 'Invalid job ID'}), 404
    
    result = stop_job(job_id)
    return jsonify(result)

@app.route('/api/dashboard/<dashboard_id>/start', methods=['POST'])
def api_start_dashboard(dashboard_id):
    """Start a specific dashboard"""
    if not is_within_market_hours():
        return jsonify({'error': 'Dashboard only available during market hours (9:00 AM - 4:00 PM IST)'}), 403
    
    if dashboard_id not in DASHBOARDS:
        return jsonify({'success': False, 'message': 'Invalid dashboard ID'}), 404
    
    result = start_dashboard(dashboard_id)
    return jsonify(result)

@app.route('/api/dashboard/<dashboard_id>/stop', methods=['POST'])
def api_stop_dashboard(dashboard_id):
    """Stop a specific dashboard"""
    if not is_within_market_hours():
        return jsonify({'error': 'Dashboard only available during market hours (9:00 AM - 4:00 PM IST)'}), 403
    
    if dashboard_id not in DASHBOARDS:
        return jsonify({'success': False, 'message': 'Invalid dashboard ID'}), 404
    
    result = stop_dashboard(dashboard_id)
    return jsonify(result)

@app.route('/api/dashboard/<dashboard_id>/restart', methods=['POST'])
def api_restart_dashboard(dashboard_id):
    """Restart a specific dashboard"""
    if not is_within_market_hours():
        return jsonify({'error': 'Dashboard only available during market hours (9:00 AM - 4:00 PM IST)'}), 403
    
    if dashboard_id not in DASHBOARDS:
        return jsonify({'success': False, 'message': 'Invalid dashboard ID'}), 404
    
    result = restart_dashboard(dashboard_id)
    return jsonify(result)

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>India-TS Job & Dashboard Manager</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #0a0a0a;
            color: #e0e0e0;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            color: #4fc3f7;
        }
        
        .header p {
            color: #9e9e9e;
            font-size: 1.1em;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            transition: all 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        .stat-card h3 {
            font-size: 2em;
            margin-bottom: 5px;
        }
        
        .stat-card.total { border-top: 3px solid #4fc3f7; }
        .stat-card.running { border-top: 3px solid #4caf50; }
        .stat-card.success { border-top: 3px solid #8bc34a; }
        .stat-card.error { border-top: 3px solid #f44336; }
        .stat-card.dashboards { border-top: 3px solid #9c27b0; }
        
        .section-title {
            font-size: 1.8em;
            margin: 30px 0 15px;
            color: #4fc3f7;
            padding-bottom: 10px;
            border-bottom: 2px solid #333;
        }
        
        .jobs-table {
            background: #1a1a1a;
            border-radius: 8px;
            overflow-x: auto;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
            margin-bottom: 20px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            min-width: 900px;
        }
        
        th {
            background: #2a2a2a;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #4fc3f7;
            border-bottom: 2px solid #333;
            font-size: 0.95em;
        }
        
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #333;
            font-size: 0.9em;
        }
        
        tr:hover {
            background: #222;
        }
        
        tr.dashboard-row {
            background: #1a1a2e;
        }
        
        tr.dashboard-row:hover {
            background: #222;
        }
        
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
        }
        
        .status-running {
            background: #4caf50;
            color: white;
        }
        
        .status-success {
            background: #8bc34a;
            color: white;
        }
        
        .status-error {
            background: #f44336;
            color: white;
        }
        
        .status-not_loaded {
            background: #666;
            color: white;
        }
        
        .status-stopped {
            background: #f44336;
            color: white;
        }
        
        .action-buttons {
            display: flex;
            gap: 8px;
        }
        
        .btn {
            padding: 6px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9em;
            transition: all 0.3s ease;
            font-weight: 500;
        }
        
        .btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }
        
        .btn-reload, .btn-start {
            background: #2196f3;
            color: white;
        }
        
        .btn-restart {
            background: #ff9800;
            color: white;
        }
        
        .btn-stop {
            background: #f44336;
            color: white;
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .refresh-info {
            text-align: center;
            margin-top: 20px;
            color: #9e9e9e;
        }
        
        .loading {
            opacity: 0.6;
        }
        
        .error-message {
            background: #d32f2f;
            color: white;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
            display: none;
        }
        
        .success-message {
            background: #388e3c;
            color: white;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
            display: none;
        }
        
        .port-info {
            font-size: 0.85em;
            color: #9e9e9e;
            margin-left: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>India-TS Job & Dashboard Manager</h1>
            <p>Monitor and control all scheduled jobs and dashboards</p>
        </div>
        
        <div id="messages"></div>
        
        <div class="stats-grid" id="stats">
            <div class="stat-card total">
                <h3 id="total-count">0</h3>
                <p>Total Items</p>
            </div>
            <div class="stat-card running">
                <h3 id="running-count">0</h3>
                <p>Running</p>
            </div>
            <div class="stat-card success">
                <h3 id="success-count">0</h3>
                <p>Success</p>
            </div>
            <div class="stat-card error">
                <h3 id="error-count">0</h3>
                <p>Error</p>
            </div>
            <div class="stat-card dashboards">
                <h3 id="dashboard-count">0</h3>
                <p>Dashboards</p>
            </div>
        </div>
        
        <h2 class="section-title">Scheduled Jobs</h2>
        <div class="jobs-table">
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Script</th>
                        <th>Schedule</th>
                        <th>Status</th>
                        <th>PID/Exit Code</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="jobs-tbody">
                    <tr>
                        <td colspan="6" style="text-align: center; padding: 40px;">
                            Loading jobs...
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <h2 class="section-title">Dashboards</h2>
        <div class="jobs-table">
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Script</th>
                        <th>Port</th>
                        <th>Status</th>
                        <th>PID</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="dashboards-tbody">
                    <tr>
                        <td colspan="6" style="text-align: center; padding: 40px;">
                            Loading dashboards...
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <div class="refresh-info">
            <p>Last updated: <span id="last-update">Never</span> | Auto-refresh every 10 seconds</p>
        </div>
    </div>
    
    <script>
        let allData = [];
        
        function showMessage(message, type = 'success') {
            const messagesDiv = document.getElementById('messages');
            const msgDiv = document.createElement('div');
            msgDiv.className = type === 'success' ? 'success-message' : 'error-message';
            msgDiv.textContent = message;
            msgDiv.style.display = 'block';
            messagesDiv.appendChild(msgDiv);
            
            setTimeout(() => {
                msgDiv.remove();
            }, 5000);
        }
        
        function updateStats() {
            const stats = {
                total: allData.length,
                running: 0,
                success: 0,
                error: 0,
                dashboards: 0
            };
            
            allData.forEach(item => {
                if (item.type === 'dashboard') {
                    stats.dashboards++;
                }
                if (item.status === 'running') stats.running++;
                else if (item.status === 'success') stats.success++;
                else if (item.status === 'error') stats.error++;
            });
            
            document.getElementById('total-count').textContent = stats.total;
            document.getElementById('running-count').textContent = stats.running;
            document.getElementById('success-count').textContent = stats.success;
            document.getElementById('error-count').textContent = stats.error;
            document.getElementById('dashboard-count').textContent = stats.dashboards;
        }
        
        function getStatusBadge(status) {
            return `<span class="status-badge status-${status}">${status.toUpperCase()}</span>`;
        }
        
        function getPidExitCode(item) {
            if (item.pid) return `PID: ${item.pid}`;
            if (item.exit_code !== null) return `Exit: ${item.exit_code}`;
            return '-';
        }
        
        async function performAction(action, itemId, itemName, itemType) {
            try {
                const endpoint = itemType === 'dashboard' 
                    ? `/api/dashboard/${itemId}/${action}`
                    : `/api/job/${itemId}/${action}`;
                    
                const response = await fetch(endpoint, {
                    method: 'POST'
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showMessage(`${itemName}: ${result.message}`, 'success');
                    setTimeout(loadData, 1000);
                } else {
                    showMessage(`${itemName}: ${result.message}`, 'error');
                }
            } catch (error) {
                showMessage(`Error: ${error.message}`, 'error');
            }
        }
        
        function renderJobs() {
            const jobs = allData.filter(item => item.type === 'job');
            const tbody = document.getElementById('jobs-tbody');
            
            if (jobs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No jobs found</td></tr>';
                return;
            }
            
            tbody.innerHTML = jobs.map(job => `
                <tr>
                    <td><strong>${job.name}</strong>${job.port ? `<span class="port-info">Port ${job.port}</span>` : ''}</td>
                    <td><code>${job.script}</code></td>
                    <td>${job.schedule}</td>
                    <td>${getStatusBadge(job.status)}</td>
                    <td>${getPidExitCode(job)}</td>
                    <td>
                        <div class="action-buttons">
                            <button class="btn btn-reload" onclick="performAction('reload', '${job.id}', '${job.name}', 'job')">
                                Reload
                            </button>
                            <button class="btn btn-restart" onclick="performAction('restart', '${job.id}', '${job.name}', 'job')"
                                    ${job.status !== 'running' ? 'disabled' : ''}>
                                Restart
                            </button>
                            <button class="btn btn-stop" onclick="performAction('stop', '${job.id}', '${job.name}', 'job')"
                                    ${job.status !== 'running' ? 'disabled' : ''}>
                                Stop
                            </button>
                        </div>
                    </td>
                </tr>
            `).join('');
        }
        
        function renderDashboards() {
            const dashboards = allData.filter(item => item.type === 'dashboard');
            const tbody = document.getElementById('dashboards-tbody');
            
            if (dashboards.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No dashboards found</td></tr>';
                return;
            }
            
            tbody.innerHTML = dashboards.map(dashboard => `
                <tr class="dashboard-row">
                    <td><strong>${dashboard.name}</strong></td>
                    <td><code>${dashboard.script}</code></td>
                    <td>${dashboard.port || '-'}</td>
                    <td>${getStatusBadge(dashboard.status)}</td>
                    <td>${dashboard.pid ? `PID: ${dashboard.pid}` : '-'}</td>
                    <td>
                        <div class="action-buttons">
                            ${dashboard.status !== 'running' ? `
                                <button class="btn btn-start" onclick="performAction('start', '${dashboard.id}', '${dashboard.name}', 'dashboard')">
                                    Start
                                </button>
                            ` : ''}
                            <button class="btn btn-restart" onclick="performAction('restart', '${dashboard.id}', '${dashboard.name}', 'dashboard')"
                                    ${dashboard.status !== 'running' ? 'disabled' : ''}>
                                Restart
                            </button>
                            <button class="btn btn-stop" onclick="performAction('stop', '${dashboard.id}', '${dashboard.name}', 'dashboard')"
                                    ${dashboard.status !== 'running' ? 'disabled' : ''}>
                                Stop
                            </button>
                        </div>
                    </td>
                </tr>
            `).join('');
        }
        
        async function loadData() {
            try {
                const response = await fetch('/api/jobs');
                const data = await response.json();
                
                allData = data.jobs;
                updateStats();
                renderJobs();
                renderDashboards();
                
                document.getElementById('last-update').textContent = data.timestamp;
            } catch (error) {
                showMessage(`Error loading data: ${error.message}`, 'error');
            }
        }
        
        // Initial load
        loadData();
        
        // Auto-refresh every 10 seconds
        setInterval(loadData, 10000);
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    logger.info("Starting India-TS Job & Dashboard Manager on port 9090...")
    app.run(host='0.0.0.0', port=9090, debug=False)