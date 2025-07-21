#!/bin/bash

# VSR Tracker Dashboard Stop Script

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PID_FILE="$SCRIPT_DIR/vsr_dashboard.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "VSR Dashboard is not running (no PID file found)"
    exit 0
fi

PID=$(cat "$PID_FILE")

if ps -p $PID > /dev/null 2>&1; then
    echo "Stopping VSR Dashboard (PID: $PID)..."
    kill $PID
    sleep 2
    
    # Force kill if still running
    if ps -p $PID > /dev/null 2>&1; then
        echo "Force stopping..."
        kill -9 $PID
    fi
    
    rm "$PID_FILE"
    echo "VSR Dashboard stopped"
else
    echo "VSR Dashboard is not running (process not found)"
    rm "$PID_FILE"
fi