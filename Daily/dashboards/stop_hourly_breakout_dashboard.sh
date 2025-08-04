#!/bin/bash

# Stop Hourly Breakout Dashboard
PORT=3005

echo "Stopping Hourly Breakout Dashboard on port $PORT..."

# Find and kill the process
PID=$(lsof -Pi :$PORT -sTCP:LISTEN -t)

if [ -z "$PID" ]; then
    echo "No dashboard running on port $PORT"
    exit 0
fi

kill -9 $PID

# Verify it stopped
sleep 1
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "❌ Failed to stop dashboard"
    exit 1
else
    echo "✅ Dashboard stopped successfully"
fi