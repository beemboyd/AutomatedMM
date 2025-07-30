#!/bin/bash
# Stop Hourly Tracker Service

echo "Stopping Hourly Tracker Service..."

# Check if PID file exists
if [ -f hourly_tracker.pid ]; then
    PID=$(cat hourly_tracker.pid)
    if ps -p $PID > /dev/null; then
        kill $PID
        echo "Hourly Tracker Service (PID: $PID) stopped"
    else
        echo "Process not found for PID: $PID"
    fi
    rm hourly_tracker.pid
else
    echo "PID file not found"
    # Try to find and kill by process name
    pkill -f "hourly_tracker_service.py"
    echo "Killed any hourly_tracker_service.py processes"
fi