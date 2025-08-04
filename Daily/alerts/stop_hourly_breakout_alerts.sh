#!/bin/bash

# Stop Hourly Breakout Alert Service

SERVICE_NAME="com.india-ts.hourly-breakout-alerts"
PLIST_FILE="$HOME/Library/LaunchAgents/${SERVICE_NAME}.plist"

echo "Stopping Hourly Breakout Alert Service..."

if launchctl list | grep -q "$SERVICE_NAME"; then
    launchctl bootout gui/$(id -u) "$PLIST_FILE"
    echo "✅ Service stopped successfully"
else
    echo "⚠️  Service was not running"
fi

# Remove plist file
if [ -f "$PLIST_FILE" ]; then
    rm "$PLIST_FILE"
    echo "✅ Removed plist file"
fi