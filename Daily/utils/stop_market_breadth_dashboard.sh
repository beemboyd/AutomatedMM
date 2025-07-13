#!/bin/bash

# Stop Market Breadth Dashboard

PID_FILE="/Users/maverick/PycharmProjects/India-TS/Daily/pids/market_breadth_dashboard.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    
    if ps -p $PID > /dev/null; then
        echo "Stopping Market Breadth Dashboard (PID: $PID)..."
        kill $PID
        sleep 2
        
        # Check if process is still running
        if ps -p $PID > /dev/null; then
            echo "Process still running, forcing stop..."
            kill -9 $PID
        fi
        
        echo "Market Breadth Dashboard stopped."
        rm -f "$PID_FILE"
    else
        echo "Market Breadth Dashboard is not running (PID $PID not found)."
        rm -f "$PID_FILE"
    fi
else
    echo "PID file not found. Market Breadth Dashboard might not be running."
    echo "Checking for any running instances..."
    
    # Try to find and kill any running instances
    PIDS=$(ps aux | grep "market_breadth_dashboard.py" | grep -v grep | awk '{print $2}')
    
    if [ ! -z "$PIDS" ]; then
        echo "Found running instances: $PIDS"
        for PID in $PIDS; do
            echo "Killing PID: $PID"
            kill $PID
        done
        echo "All instances stopped."
    else
        echo "No running instances found."
    fi
fi