#!/bin/bash

# Start First Hour Breakout Dashboard on port 3006

PORT=3006
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DASHBOARD_SCRIPT="${SCRIPT_DIR}/first_hour_dashboard.py"

echo "Starting First Hour Breakout Dashboard on port $PORT..."

# Check if port is already in use
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "Port $PORT is already in use. Stopping existing process..."
    kill -9 $(lsof -Pi :$PORT -sTCP:LISTEN -t)
    sleep 2
fi

# Start the dashboard
nohup python3 "$DASHBOARD_SCRIPT" > /dev/null 2>&1 &

# Wait a moment for it to start
sleep 2

# Check if it started successfully
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "✅ First Hour Breakout Dashboard started successfully!"
    echo "   Access it at: http://localhost:$PORT"
else
    echo "❌ Failed to start dashboard"
    exit 1
fi