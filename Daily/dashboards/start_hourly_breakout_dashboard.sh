#!/bin/bash

# Start Hourly Breakout Dashboard
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DASHBOARD_SCRIPT="$SCRIPT_DIR/hourly_breakout_dashboard.py"
PORT=3005

echo "Starting Hourly Breakout Dashboard on port $PORT..."

# Check if already running
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "Dashboard is already running on port $PORT"
    echo "Access it at: http://localhost:$PORT"
    exit 1
fi

# Start the dashboard
nohup python3 "$DASHBOARD_SCRIPT" > /dev/null 2>&1 &
PID=$!

# Wait a moment for it to start
sleep 2

# Check if it started successfully
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ Hourly Breakout Dashboard started successfully!"
    echo "   PID: $PID"
    echo "   Port: $PORT"
    echo "   URL: http://localhost:$PORT"
else
    echo "❌ Failed to start dashboard"
    exit 1
fi