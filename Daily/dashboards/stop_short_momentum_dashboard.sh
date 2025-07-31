#!/bin/bash
# Stop Short Momentum Dashboard

echo "Stopping Short Momentum Dashboard..."

# Check if PID file exists
if [ -f "/Users/maverick/PycharmProjects/India-TS/Daily/dashboards/short_momentum_dashboard.pid" ]; then
    PID=$(cat /Users/maverick/PycharmProjects/India-TS/Daily/dashboards/short_momentum_dashboard.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo "Short Momentum Dashboard (PID: $PID) stopped"
    else
        echo "Short Momentum Dashboard process not found (PID: $PID)"
    fi
    rm -f /Users/maverick/PycharmProjects/India-TS/Daily/dashboards/short_momentum_dashboard.pid
else
    echo "PID file not found. Checking port 3003..."
    # Try to kill by port
    lsof -ti:3003 | xargs kill -9 2>/dev/null && echo "Killed process on port 3003" || echo "No process found on port 3003"
fi