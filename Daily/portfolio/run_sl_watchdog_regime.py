#!/usr/bin/env python
"""
Script to run the regime-based SL watchdog
Usage: python run_sl_watchdog_regime.py [user_name] [orders_file]
"""

import sys
import os

# Add parent directory to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def main():
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python run_sl_watchdog_regime.py [user_name] [orders_file_optional]")
        print("Available users: Sai, Som, Su, Tinks, Mom, Prash, Ravi")
        sys.exit(1)
    
    user_name = sys.argv[1]
    orders_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Import and run the regime-based watchdog
    try:
        # Run the script with proper arguments
        import subprocess
        
        cmd = [sys.executable, "SL_watchdog_regime.py"]
        
        # Add orders file if provided
        if orders_file:
            cmd.append(orders_file)
        
        # Set environment variable for user
        env = os.environ.copy()
        env['TRADING_USER'] = user_name
        
        # Run the watchdog
        print(f"Starting regime-based SL watchdog for user {user_name}...")
        if orders_file:
            print(f"Using orders file: {orders_file}")
        else:
            print("Monitoring all CNC positions from Zerodha account")
        
        subprocess.run(cmd, env=env)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()