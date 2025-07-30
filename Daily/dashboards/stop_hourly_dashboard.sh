#!/bin/bash
# Stop Hourly Tracker Dashboard

echo "Stopping Hourly Tracker Dashboard..."

# Check if PID file exists
if [ -f hourly_dashboard.pid ]; then
    PID=$(cat hourly_dashboard.pid)
    if ps -p $PID > /dev/null; then
        kill $PID
        echo "Hourly Tracker Dashboard (PID: $PID) stopped"
    else
        echo "Process not found for PID: $PID"
    fi
    rm hourly_dashboard.pid
else
    echo "PID file not found"
    # Try to find and kill by port
    lsof -ti:3002 | xargs kill -9 2>/dev/null
    echo "Killed any process on port 3002"
fi