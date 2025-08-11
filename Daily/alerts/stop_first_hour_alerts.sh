#!/bin/bash

# Stop First Hour Breakout Alert Service

SERVICE_NAME="com.india-ts.first-hour-alerts"
PLIST_FILE="$HOME/Library/LaunchAgents/${SERVICE_NAME}.plist"

echo "Stopping First Hour Breakout Alert Service..."

# Check if service is running
if ! launchctl list | grep -q "${SERVICE_NAME}"; then
    echo "Service is not running"
else
    # Stop the service
    launchctl bootout gui/$(id -u) "${PLIST_FILE}"
    echo "✅ Service stopped successfully"
fi

# Remove plist file
if [ -f "${PLIST_FILE}" ]; then
    rm "${PLIST_FILE}"
    echo "✅ Removed plist file"
fi