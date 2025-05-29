#!/usr/bin/env python3

import os
import sys
import argparse
import subprocess
import configparser
from datetime import datetime

def check_service_status():
    """Check if the position_watchdog service is currently running"""
    try:
        # Run launchctl list and grep for position_watchdog
        result = subprocess.run(
            ["launchctl", "list"], 
            capture_output=True, 
            text=True
        )
        
        if "com.indiaTS.position_watchdog" in result.stdout:
            print("✅ Position watchdog service is RUNNING")
            return True
        else:
            print("❌ Position watchdog service is NOT RUNNING")
            return False
    except Exception as e:
        print(f"Error checking service status: {e}")
        return False

def check_api_credentials():
    """Check if the API credentials in config.ini are valid"""
    try:
        # Import here to avoid dependency issues
        from kiteconnect import KiteConnect
        
        # Get config file path
        config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
        
        # Read the current config
        config = configparser.ConfigParser()
        config.read(config_file)
        
        # Get API credentials
        api_key = config.get('API', 'api_key')
        api_secret = config.get('API', 'api_secret', fallback="")
        access_token = config.get('API', 'access_token')
        
        print(f"API Key: {api_key}")
        print(f"API Secret: {'*' * len(api_secret) if api_secret else 'NOT SET'}")
        print(f"Access Token: {access_token[:5]}...{access_token[-5:] if len(access_token) > 10 else ''}")
        
        # Initialize KiteConnect
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        
        # Try to fetch profile to test authentication
        profile = kite.profile()
        print(f"✅ Authentication successful as {profile['user_name']} ({profile['user_id']})")
        return True
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return False

def start_service():
    """Start the position_watchdog service"""
    try:
        # First check if it's already running
        if check_service_status():
            print("Service is already running. No action taken.")
            return
            
        # Load the service
        subprocess.run(
            ["launchctl", "load", "~/Library/LaunchAgents/com.indiaTS.position_watchdog.plist"], 
            shell=True,
            check=True
        )
        print("✅ Position watchdog service started")
        
        # Verify it's running
        check_service_status()
    except Exception as e:
        print(f"❌ Error starting service: {e}")

def stop_service():
    """Stop the position_watchdog service"""
    try:
        # First check if it's running
        if not check_service_status():
            print("Service is not running. No action taken.")
            return
            
        # Unload the service
        subprocess.run(
            ["launchctl", "unload", "~/Library/LaunchAgents/com.indiaTS.position_watchdog.plist"], 
            shell=True,
            check=True
        )
        print("✅ Position watchdog service stopped")
        
        # Verify it's stopped
        check_service_status()
    except Exception as e:
        print(f"❌ Error stopping service: {e}")

def restart_service():
    """Restart the position_watchdog service"""
    stop_service()
    start_service()
    print("✅ Position watchdog service restarted")

def check_logs(lines=20):
    """Check the position_watchdog logs"""
    try:
        # Check the log file
        log_file = "/tmp/com.indiaTS.position_watchdog.stderr"
        
        if not os.path.exists(log_file):
            print(f"❌ Log file not found: {log_file}")
            return
            
        # Get the file modification time
        mod_time = os.path.getmtime(log_file)
        mod_time_str = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"Log file last modified: {mod_time_str}")
        print(f"Showing last {lines} lines:")
        print("="*80)
        
        # Read the last N lines
        with open(log_file, 'r') as f:
            content = f.readlines()
            for line in content[-lines:]:
                print(line.strip())
                
        print("="*80)
    except Exception as e:
        print(f"❌ Error reading logs: {e}")

def update_token():
    """Run the update_token.py script"""
    try:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'update_token.py')
        
        # Check if the request token was provided
        if len(sys.argv) > 2 and sys.argv[2].startswith('--request-token='):
            # Extract the token
            token = sys.argv[2].split('=', 1)[1]
            cmd = [sys.executable, script_path, f"--request-token={token}"]
        else:
            cmd = [sys.executable, script_path]
            
        # Run the script
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"❌ Error updating token: {e}")

def main():
    parser = argparse.ArgumentParser(description='Manage position_watchdog service')
    parser.add_argument('action', choices=['status', 'start', 'stop', 'restart', 'check-credentials', 'logs', 'update-token'],
                        help='Action to perform')
    parser.add_argument('--lines', type=int, default=20,
                        help='Number of log lines to show (for logs action)')
    
    # Parse only the first argument to handle the case where additional arguments are meant for update-token
    if len(sys.argv) > 1:
        args = parser.parse_args([sys.argv[1]])
    else:
        parser.print_help()
        return
    
    print(f"\n==== Position Watchdog Manager ====")
    print(f"Action: {args.action}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*40)
    
    if args.action == 'status':
        check_service_status()
    elif args.action == 'start':
        start_service()
    elif args.action == 'stop':
        stop_service()
    elif args.action == 'restart':
        restart_service()
    elif args.action == 'check-credentials':
        check_api_credentials()
    elif args.action == 'logs':
        check_logs(args.lines)
    elif args.action == 'update-token':
        update_token()
    
if __name__ == "__main__":
    main()