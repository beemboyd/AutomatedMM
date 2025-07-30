#!/usr/bin/env python3
"""
Dashboard Manager - Manages all India-TS dashboards
Starts dashboards at 8 AM IST and stops them at 8 PM IST
For ports 3001, 5001, 3003 - stops data refresh after 3:30 PM
"""

import os
import sys
import time
import signal
import logging
import subprocess
from datetime import datetime, time as dtime
import pytz
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/maverick/PycharmProjects/India-TS/Daily/logs/dashboard_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Dashboard configurations
DASHBOARDS = {
    '3001': {
        'name': 'VSR Tracker Dashboard',
        'script': '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards/vsr_tracker_dashboard.py',
        'stop_refresh_after': '15:30',  # Stop refresh after 3:30 PM
        'workdir': '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards'
    },
    '3002': {
        'name': 'Hourly Tracker Dashboard',
        'script': '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards/hourly_tracker_dashboard.py',
        'stop_refresh_after': '15:30',  # Stop refresh after 3:30 PM
        'workdir': '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards'
    },
    '3003': {
        'name': 'Short Momentum Dashboard',
        'script': '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards/short_momentum_dashboard.py',
        'stop_refresh_after': '15:30',  # Stop refresh after 3:30 PM
        'workdir': '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards'
    },
    '3004': {
        'name': 'Hourly Short Tracker Dashboard',
        'script': '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards/hourly_short_tracker_dashboard.py',
        'stop_refresh_after': '15:30',  # Stop refresh after 3:30 PM
        'workdir': '/Users/maverick/PycharmProjects/India-TS/Daily/dashboards'
    },
    '5001': {
        'name': 'Market Breadth Dashboard',
        'script': '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/market_breadth_dashboard.py',
        'stop_refresh_after': '15:30',  # Stop refresh after 3:30 PM
        'workdir': '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime'
    },
    '7080': {
        'name': 'Health Check Dashboard',
        'script': '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/dashboard_health_check.py',
        'stop_refresh_after': None,  # Runs till 8 PM
        'workdir': '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime'
    },
    '8080': {
        'name': 'Market Regime Enhanced Dashboard',
        'script': '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/dashboard_enhanced.py',
        'stop_refresh_after': None,  # Runs till 8 PM
        'workdir': '/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime'
    },
    '9090': {
        'name': 'Job Manager Dashboard',
        'script': '/Users/maverick/PycharmProjects/India-TS/Daily/Health/job_manager_dashboard.py',
        'stop_refresh_after': None,  # Runs till 8 PM
        'workdir': '/Users/maverick/PycharmProjects/India-TS/Daily/Health'
    }
}

# IST timezone
IST = pytz.timezone('Asia/Kolkata')

def is_port_in_use(port):
    """Check if a port is in use"""
    for conn in psutil.net_connections():
        if conn.laddr.port == int(port) and conn.status == 'LISTEN':
            return True
    return False

def get_process_by_port(port):
    """Get process using a specific port"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            for conn in proc.connections():
                if conn.laddr.port == int(port) and conn.status == 'LISTEN':
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def start_dashboard(port, config):
    """Start a dashboard"""
    if is_port_in_use(port):
        logger.info(f"Port {port} already in use. {config['name']} might be running.")
        return None
    
    try:
        # Start the dashboard process
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        
        process = subprocess.Popen(
            ['/usr/bin/python3', config['script']],
            cwd=config['workdir'],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait a bit to ensure it started
        time.sleep(5)
        
        if process.poll() is None and is_port_in_use(port):
            logger.info(f"✅ Started {config['name']} on port {port} (PID: {process.pid})")
            return process
        else:
            logger.error(f"❌ Failed to start {config['name']} on port {port}")
            return None
            
    except Exception as e:
        logger.error(f"Error starting {config['name']}: {e}")
        return None

def stop_dashboard(port, config):
    """Stop a dashboard"""
    proc = get_process_by_port(port)
    if proc:
        try:
            logger.info(f"Stopping {config['name']} on port {port} (PID: {proc.pid})")
            proc.terminate()
            proc.wait(timeout=10)
            logger.info(f"✅ Stopped {config['name']}")
        except psutil.TimeoutExpired:
            logger.warning(f"Force killing {config['name']}")
            proc.kill()
        except Exception as e:
            logger.error(f"Error stopping {config['name']}: {e}")
    else:
        logger.info(f"No process found on port {port}")

def send_refresh_control(port, enable_refresh):
    """Send refresh control signal to dashboard"""
    try:
        # Use the refresh controller
        import sys
        sys.path.insert(0, '/Users/maverick/PycharmProjects/India-TS/Daily/utils')
        from dashboard_refresh_controller import set_refresh_status
        
        set_refresh_status(port, enable_refresh)
        action = "enabled" if enable_refresh else "disabled"
        logger.info(f"Refresh {action} for dashboard on port {port}")
    except Exception as e:
        logger.error(f"Error controlling refresh for port {port}: {e}")

def manage_dashboards(action):
    """Main dashboard management function"""
    current_time = datetime.now(IST)
    logger.info(f"Dashboard Manager - Action: {action} at {current_time.strftime('%Y-%m-%d %H:%M:%S IST')}")
    
    if action == 'start':
        # Start all dashboards
        for port, config in DASHBOARDS.items():
            start_dashboard(port, config)
            
    elif action == 'stop':
        # Stop all dashboards
        for port, config in DASHBOARDS.items():
            stop_dashboard(port, config)
            
    elif action == 'check_refresh':
        # Check if we need to stop refresh for certain dashboards
        current_time_str = current_time.strftime('%H:%M')
        
        for port, config in DASHBOARDS.items():
            if config['stop_refresh_after']:
                if current_time_str >= config['stop_refresh_after']:
                    logger.info(f"Time to stop refresh for {config['name']} (port {port})")
                    send_refresh_control(port, enable_refresh=False)
                    
    elif action == 'status':
        # Check status of all dashboards
        logger.info("Dashboard Status:")
        for port, config in DASHBOARDS.items():
            if is_port_in_use(port):
                proc = get_process_by_port(port)
                pid = proc.pid if proc else "Unknown"
                logger.info(f"✅ {config['name']} - Running on port {port} (PID: {pid})")
            else:
                logger.info(f"❌ {config['name']} - Not running on port {port}")

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: dashboard_manager.py [start|stop|check_refresh|status]")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action not in ['start', 'stop', 'check_refresh', 'status']:
        print(f"Invalid action: {action}")
        print("Valid actions: start, stop, check_refresh, status")
        sys.exit(1)
    
    try:
        manage_dashboards(action)
    except Exception as e:
        logger.error(f"Dashboard manager error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()