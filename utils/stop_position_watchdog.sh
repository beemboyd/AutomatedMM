#!/bin/bash

# This script stops the position_watchdog service

echo "Stopping Position Watchdog service..."

# Directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Check if PID file exists
PID_FILE="$PROJECT_DIR/utils/position_watchdog.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    echo "Found Position Watchdog PID: $PID"
    
    # Check if process is running
    if ps -p $PID > /dev/null; then
        echo "Stopping Position Watchdog with PID: $PID"
        kill $PID
        sleep 2
        
        # Check if process is still running and force kill if needed
        if ps -p $PID > /dev/null; then
            echo "Process still running, force killing..."
            kill -9 $PID
        fi
        
        echo "Position Watchdog stopped"
    else
        echo "Process with PID $PID is not running"
    fi
    
    # Remove PID file
    rm "$PID_FILE"
else
    # Try to find process by name if PID file doesn't exist
    PID=$(pgrep -f "python.*position_watchdog.py" || echo "")
    if [ ! -z "$PID" ]; then
        echo "Found Position Watchdog with PID: $PID"
        kill $PID
        sleep 2
        
        # Check if process is still running and force kill if needed
        if ps -p $PID > /dev/null; then
            echo "Process still running, force killing..."
            kill -9 $PID
        fi
        
        echo "Position Watchdog stopped"
    else
        echo "No running Position Watchdog process found"
    fi
fi