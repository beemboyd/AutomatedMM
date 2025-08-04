#!/bin/bash

# Hourly Breakout Alert Service Startup Script
# Monitors Long Reversal tickers for breakouts above previous hourly close

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
SERVICE_NAME="com.india-ts.hourly-breakout-alerts"
PLIST_FILE="$HOME/Library/LaunchAgents/${SERVICE_NAME}.plist"

echo "Starting Hourly Breakout Alert Service..."

# Check if already running
if launchctl list | grep -q "$SERVICE_NAME"; then
    echo "Service is already running. Stopping it first..."
    launchctl bootout gui/$(id -u) "$PLIST_FILE" 2>/dev/null
    sleep 2
fi

# Create plist file
cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${SERVICE_NAME}</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>${PROJECT_ROOT}/.venv/bin/python</string>
        <string>${SCRIPT_DIR}/hourly_breakout_alert_service.py</string>
        <string>-u</string>
        <string>Sai</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>${PROJECT_ROOT}</string>
    
    <key>StandardOutPath</key>
    <string>${PROJECT_ROOT}/Daily/logs/hourly_breakout_alerts.log</string>
    
    <key>StandardErrorPath</key>
    <string>${PROJECT_ROOT}/Daily/logs/hourly_breakout_alerts_error.log</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>${PROJECT_ROOT}</string>
    </dict>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>Crashed</key>
        <true/>
    </dict>
    
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>9</integer>
            <key>Minute</key>
            <integer>0</integer>
        </dict>
    </array>
    
    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
EOF

# Load the service
echo "Loading service..."
launchctl bootstrap gui/$(id -u) "$PLIST_FILE"

# Check status
sleep 2
if launchctl list | grep -q "$SERVICE_NAME"; then
    echo "✅ Hourly Breakout Alert Service started successfully!"
    echo "Service name: $SERVICE_NAME"
    echo ""
    echo "To check logs:"
    echo "  tail -f ${PROJECT_ROOT}/Daily/logs/hourly_breakout_alerts.log"
    echo ""
    echo "To stop the service:"
    echo "  launchctl bootout gui/\$(id -u) $PLIST_FILE"
else
    echo "❌ Failed to start service. Check error logs:"
    echo "  cat ${PROJECT_ROOT}/Daily/logs/hourly_breakout_alerts_error.log"
fi