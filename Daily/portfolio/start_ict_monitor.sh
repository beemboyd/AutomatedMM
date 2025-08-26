#!/bin/bash

# Start ICT Continuous Monitor
# This runs throughout the trading day, updating every 5 minutes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
LOG_DIR="$SCRIPT_DIR/../logs/ict_analysis"

# Create log directory if needed
mkdir -p "$LOG_DIR"

# Check if already running
if pgrep -f "ict_continuous_monitor.py" > /dev/null; then
    echo "ICT Monitor is already running"
    exit 1
fi

echo "Starting ICT Continuous Monitor..."
echo "Updates every 5 minutes during market hours"
echo "Dashboard at http://localhost:3008 will auto-refresh"

# Start the monitor in background
cd "$SCRIPT_DIR"
nohup $PYTHON_PATH ict_continuous_monitor.py --user Sai --interval 300 > "$LOG_DIR/monitor.log" 2>&1 &

echo "ICT Monitor started with PID: $!"
echo "Check logs at: $LOG_DIR/monitor.log"