#!/bin/bash

# Start First Hour Breakout Alert Service

SERVICE_NAME="com.india-ts.first-hour-alerts"
PLIST_FILE="$HOME/Library/LaunchAgents/${SERVICE_NAME}.plist"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo "Starting First Hour Breakout Alert Service..."

# Check if already running
if launchctl list | grep -q "${SERVICE_NAME}"; then
    echo "Service is already running. Stopping it first..."
    launchctl bootout gui/$(id -u) "${PLIST_FILE}" 2>/dev/null
    sleep 2
fi

# Create plist file
cat > "${PLIST_FILE}" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${SERVICE_NAME}</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>${PROJECT_ROOT}/.venv/bin/python</string>
        <string>${SCRIPT_DIR}/first_hour_breakout_service.py</string>
        <string>-u</string>
        <string>Sai</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>${PROJECT_ROOT}</string>
    
    <key>StandardOutPath</key>
    <string>${PROJECT_ROOT}/Daily/logs/alerts_firsthour/first_hour_alerts.log</string>
    
    <key>StandardErrorPath</key>
    <string>${PROJECT_ROOT}/Daily/logs/alerts_firsthour/first_hour_alerts_error.log</string>
    
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
        <true/>
    </dict>
    
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>9</integer>
            <key>Minute</key>
            <integer>14</integer>
        </dict>
    </array>
    
    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
EOF

# Load the service
echo "Loading service..."
launchctl bootstrap gui/$(id -u) "${PLIST_FILE}"

# Wait a moment
sleep 2

# Check if service started
if launchctl list | grep -q "${SERVICE_NAME}"; then
    echo "✅ First Hour Breakout Alert Service started successfully!"
    echo "Service name: ${SERVICE_NAME}"
    echo ""
    echo "To check logs:"
    echo "  tail -f ${PROJECT_ROOT}/Daily/logs/alerts_firsthour/first_hour_alerts.log"
    echo ""
    echo "To stop the service:"
    echo "  launchctl bootout gui/\$(id -u) ${PLIST_FILE}"
else
    echo "❌ Failed to start service"
    echo "Check error log: ${PROJECT_ROOT}/Daily/logs/alerts_firsthour/first_hour_alerts_error.log"
    exit 1
fi