#!/usr/bin/env python3
"""
Dashboard Refresh Wrapper
Add this to dashboards that need to check refresh status
"""

import os
import json
from datetime import datetime
import pytz

REFRESH_CONTROL_FILE = '/Users/maverick/PycharmProjects/India-TS/Daily/data/dashboard_refresh_control.json'
IST = pytz.timezone('Asia/Kolkata')

def should_refresh_data(port):
    """
    Check if dashboard should refresh data
    Returns True if refresh is enabled, False otherwise
    """
    # Default behavior: always refresh before 3:30 PM
    current_time = datetime.now(IST)
    if current_time.hour < 15 or (current_time.hour == 15 and current_time.minute < 30):
        return True
    
    # After 3:30 PM, check control file
    if not os.path.exists(REFRESH_CONTROL_FILE):
        return True  # Default to enabled if no control file
    
    try:
        with open(REFRESH_CONTROL_FILE, 'r') as f:
            status = json.load(f)
        
        port_status = status.get(str(port), {})
        return port_status.get('refresh_enabled', True)
    except:
        return True  # Default to enabled on error

def get_refresh_message(port):
    """Get message about refresh status"""
    if not should_refresh_data(port):
        return "Data refresh paused after market hours (3:30 PM IST)"
    return None

# Example usage in dashboard:
"""
from utils.dashboard_refresh_wrapper import should_refresh_data, get_refresh_message

# In your dashboard update function:
def update_data():
    if should_refresh_data(3001):  # Use your dashboard's port
        # Normal data fetch and update
        data = fetch_latest_data()
        update_display(data)
    else:
        # Show static data with message
        message = get_refresh_message(3001)
        display_message(message)
"""