#!/bin/bash

# VSR Tracker Dashboard Startup Script
# Runs on port 3001

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DASHBOARD_SCRIPT="$SCRIPT_DIR/vsr_tracker_dashboard.py"
PID_FILE="$SCRIPT_DIR/vsr_dashboard.pid"
LOG_FILE="$SCRIPT_DIR/vsr_dashboard.log"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "VSR Dashboard is already running (PID: $PID)"
        echo "Access at: http://localhost:3001"
        exit 0
    else
        echo "Removing stale PID file"
        rm "$PID_FILE"
    fi
fi

# Start the dashboard
echo "Starting VSR Tracker Dashboard..."
nohup /Library/Frameworks/Python.framework/Versions/3.11/Resources/Python.app/Contents/MacOS/Python "$DASHBOARD_SCRIPT" > "$LOG_FILE" 2>&1 &
PID=$!

# Save PID
echo $PID > "$PID_FILE"

# Wait a moment for startup
sleep 2

# Check if started successfully
if ps -p $PID > /dev/null 2>&1; then
    echo "VSR Dashboard started successfully (PID: $PID)"
    echo "Access at: http://localhost:3001"
    echo "Log file: $LOG_FILE"
else
    echo "Failed to start VSR Dashboard"
    rm "$PID_FILE"
    exit 1
fi