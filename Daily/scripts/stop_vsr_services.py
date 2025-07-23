#!/usr/bin/env python3
"""
Stop VSR Enhanced Tracker and Dashboard Services
Called by launchd at 3:30 PM to gracefully shutdown services
"""

import os
import sys
import subprocess
import time
import signal

def kill_process_by_name(process_names):
    """Kill processes matching the given names"""
    try:
        # Get all processes
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        
        killed = []
        for line in lines:
            for proc_name in process_names:
                if proc_name in line and 'grep' not in line:
                    parts = line.split()
                    if len(parts) > 1:
                        pid = parts[1]
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                            killed.append((pid, proc_name))
                            time.sleep(0.5)
                        except:
                            pass
        
        return killed
    except Exception as e:
        print(f"Error: {e}")
        return []

def main():
    print("Stopping VSR Enhanced Services...")
    
    # Services to stop
    services = [
        'vsr_tracker_service_enhanced.py',
        'vsr_tracker_dashboard.py'
    ]
    
    # Kill the processes
    killed = kill_process_by_name(services)
    
    if killed:
        print(f"Stopped {len(killed)} services:")
        for pid, name in killed:
            print(f"  - PID {pid}: {name}")
    else:
        print("No VSR services found running")
    
    # Also unload the launchd jobs to prevent immediate restart
    jobs = [
        'com.india-ts.vsr-tracker-enhanced',
        'com.india-ts.vsr-dashboard'
    ]
    
    for job in jobs:
        try:
            subprocess.run(['launchctl', 'unload', f'/Users/maverick/Library/LaunchAgents/{job}.plist'], 
                         capture_output=True)
            print(f"Unloaded {job}")
        except:
            pass

if __name__ == "__main__":
    main()