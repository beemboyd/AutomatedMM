#!/bin/bash

# This script starts the position_watchdog service for monitoring MIS positions
# It must be run with appropriate permissions

echo "Starting Position Watchdog service..."

# Directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Check if the service is already running
PID=$(pgrep -f "python.*position_watchdog.py" || echo "")
if [ ! -z "$PID" ]; then
    echo "Position Watchdog is already running with PID: $PID"
    echo "To stop it, use: kill $PID"
    exit 0
fi

# Set up log directory
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/position_watchdog.log"

echo "Starting Position Watchdog..."
echo "Logs will be written to: $LOG_FILE"

# Start the watchdog service in the background
nohup python3 "$PROJECT_DIR/utils/position_watchdog.py" --check-interval 30 > "$LOG_FILE" 2>&1 &

# Get the PID of the newly started process
PID=$!
echo "Position Watchdog started with PID: $PID"

# Write PID to a file for later reference
echo $PID > "$PROJECT_DIR/utils/position_watchdog.pid"
echo "PID saved to: $PROJECT_DIR/utils/position_watchdog.pid"

echo "To stop the service: kill $PID or run stop_position_watchdog.sh"