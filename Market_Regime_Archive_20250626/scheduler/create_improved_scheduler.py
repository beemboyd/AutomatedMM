#!/usr/bin/env python3
"""
Create improved scheduler for Market Regime Analysis
Runs from 9:00 AM to 4:00 PM IST on weekdays
"""

import os
import subprocess

def create_plist():
    """Create optimized plist with runs from 9 AM to 4 PM"""
    
    # Generate time slots from 9:00 AM to 4:00 PM every 30 minutes
    time_slots = []
    
    # Start at 9:00 AM (not 9:15)
    for hour in range(9, 17):  # 9 AM to 4 PM (17 = 5 PM, but we stop at 4:00)
        for minute in [0, 30]:
            # Skip 4:30 PM (only want up to 4:00 PM)
            if hour == 16 and minute == 30:
                continue
            
            # Add entry for each weekday (1-5)
            for weekday in range(1, 6):
                time_slots.append(f"""        <dict>
            <key>Hour</key>
            <integer>{hour}</integer>
            <key>Minute</key>
            <integer>{minute}</integer>
            <key>Weekday</key>
            <integer>{weekday}</integer>
        </dict>""")
    
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.india-ts.market_regime_analysis</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/market_regime_analyzer.py</string>
    </array>
    
    <key>StartCalendarInterval</key>
    <array>
        <!-- Run every 30 minutes from 9:00 AM to 4:00 PM IST on weekdays -->
        <!-- Total runs per day: 15 (9:00, 9:30, 10:00... 3:30, 4:00) -->
{chr(10).join(time_slots)}
    </array>
    
    <key>StandardOutPath</key>
    <string>/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/logs/market_regime_analysis.log</string>
    
    <key>StandardErrorPath</key>
    <string>/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/logs/market_regime_analysis_error.log</string>
    
    <key>WorkingDirectory</key>
    <string>/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
        <key>PYTHONPATH</key>
        <string>/Users/maverick/PycharmProjects/India-TS</string>
    </dict>
    
    <key>RunAtLoad</key>
    <false/>
    
</dict>
</plist>"""
    
    return plist_content

def main():
    print("Creating improved Market Regime scheduler...")
    
    # Create plist content
    plist_content = create_plist()
    
    # Define paths
    plist_path = os.path.expanduser("~/Library/LaunchAgents/com.india-ts.market_regime_analysis.plist")
    
    # Unload existing if present
    try:
        subprocess.run(['launchctl', 'unload', plist_path], capture_output=True)
        print("Unloaded existing scheduler")
    except:
        pass
    
    # Write new plist
    with open(plist_path, 'w') as f:
        f.write(plist_content)
    
    print(f"Created new plist at: {plist_path}")
    
    # Load the new plist
    result = subprocess.run(['launchctl', 'load', plist_path], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Scheduler loaded successfully!")
        print("\nSchedule:")
        print("- Runs every 30 minutes")
        print("- From 9:00 AM to 4:00 PM IST")
        print("- Monday through Friday")
        print("- Total: 15 runs per day")
        print("\nTimes: 9:00, 9:30, 10:00, 10:30, 11:00, 11:30, 12:00, 12:30, 1:00, 1:30, 2:00, 2:30, 3:00, 3:30, 4:00")
    else:
        print(f"❌ Error loading scheduler: {result.stderr}")
    
    # Verify it's loaded
    list_result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
    if 'com.india-ts.market_regime_analysis' in list_result.stdout:
        print("\n✅ Verified: Scheduler is active")
    else:
        print("\n⚠️  Warning: Scheduler might not be active")

if __name__ == "__main__":
    main()