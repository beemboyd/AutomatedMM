#!/bin/bash
# Stop Hourly Short Tracker Dashboard

echo "Stopping Hourly Short Tracker Dashboard..."

# Check if PID file exists
if [ -f "/Users/maverick/PycharmProjects/India-TS/Daily/dashboards/hourly_short_dashboard.pid" ]; then
    PID=$(cat /Users/maverick/PycharmProjects/India-TS/Daily/dashboards/hourly_short_dashboard.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo "Hourly Short Tracker Dashboard (PID: $PID) stopped"
    else
        echo "Hourly Short Tracker Dashboard process not found (PID: $PID)"
    fi
    rm -f /Users/maverick/PycharmProjects/India-TS/Daily/dashboards/hourly_short_dashboard.pid
else
    echo "PID file not found. Checking port 3004..."
    # Try to kill by port
    lsof -ti:3004 | xargs kill -9 2>/dev/null && echo "Killed process on port 3004" || echo "No process found on port 3004"
fi