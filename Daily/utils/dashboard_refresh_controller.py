#!/usr/bin/env python3
"""
Dashboard Refresh Controller
Creates a file-based signal for dashboards to check if they should refresh data
"""

import os
import json
from datetime import datetime
import pytz

REFRESH_CONTROL_FILE = '/Users/maverick/PycharmProjects/India-TS/Daily/data/dashboard_refresh_control.json'
IST = pytz.timezone('Asia/Kolkata')

def set_refresh_status(port, enabled):
    """Set refresh status for a specific dashboard port"""
    # Load existing status
    if os.path.exists(REFRESH_CONTROL_FILE):
        with open(REFRESH_CONTROL_FILE, 'r') as f:
            status = json.load(f)
    else:
        status = {}
    
    # Update status
    status[str(port)] = {
        'refresh_enabled': enabled,
        'last_updated': datetime.now(IST).isoformat(),
        'message': 'Data refresh enabled' if enabled else 'Data refresh paused after market hours'
    }
    
    # Save status
    os.makedirs(os.path.dirname(REFRESH_CONTROL_FILE), exist_ok=True)
    with open(REFRESH_CONTROL_FILE, 'w') as f:
        json.dump(status, f, indent=2)

def get_refresh_status(port):
    """Get refresh status for a specific dashboard port"""
    if not os.path.exists(REFRESH_CONTROL_FILE):
        return True  # Default to enabled
    
    with open(REFRESH_CONTROL_FILE, 'r') as f:
        status = json.load(f)
    
    port_status = status.get(str(port), {})
    return port_status.get('refresh_enabled', True)

def enable_all_refresh():
    """Enable refresh for all dashboards"""
    for port in ['3001', '3003', '5001', '7080', '8080', '9090']:
        set_refresh_status(port, True)

def disable_market_hours_refresh():
    """Disable refresh for market hours dashboards after 3:30 PM"""
    # Only disable for specific dashboards
    for port in ['3001', '3003', '5001']:
        set_refresh_status(port, False)
    
    # Keep these running
    for port in ['7080', '8080', '9090']:
        set_refresh_status(port, True)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'enable':
            enable_all_refresh()
            print("Enabled refresh for all dashboards")
        elif sys.argv[1] == 'disable-market':
            disable_market_hours_refresh()
            print("Disabled refresh for market hours dashboards (3001, 3003, 5001)")
        elif sys.argv[1] == 'status':
            if os.path.exists(REFRESH_CONTROL_FILE):
                with open(REFRESH_CONTROL_FILE, 'r') as f:
                    print(json.dumps(json.load(f), indent=2))
            else:
                print("No refresh control file found")
    else:
        print("Usage: dashboard_refresh_controller.py [enable|disable-market|status]")