#!/bin/bash

# VSR Anomaly Detector Service Startup Script

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$BASE_DIR/logs/vsr_anomaly"
PID_DIR="$BASE_DIR/pids"

# Create directories if they don't exist
mkdir -p "$LOG_DIR"
mkdir -p "$PID_DIR"

# Check if already running
PID_FILE="$PID_DIR/vsr_anomaly_detector.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "VSR Anomaly Detector is already running (PID: $PID)"
        exit 1
    else
        echo "Removing stale PID file"
        rm "$PID_FILE"
    fi
fi

# Default values
USER_NAME="Sai"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--user)
            USER_NAME="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [-u|--user USERNAME]"
            exit 1
            ;;
    esac
done

echo "Starting VSR Anomaly Detector Service..."
echo "User: $USER_NAME"

# Get today's date for log file
TODAY=$(date +%Y%m%d)
LOG_FILE="$LOG_DIR/vsr_anomaly_${TODAY}.log"

# Start the service in background
cd "$BASE_DIR"
nohup python3 services/vsr_anomaly_detector.py -u "$USER_NAME" >> "$LOG_FILE" 2>&1 &

# Get the PID and save it
PID=$!
echo $PID > "$PID_FILE"

# Wait a bit to check if it started successfully
sleep 3

if ps -p "$PID" > /dev/null; then
    echo "VSR Anomaly Detector started successfully (PID: $PID)"
    echo "Log file: $LOG_FILE"
    echo ""
    echo "To view logs: tail -f $LOG_FILE"
    echo "To stop: $SCRIPT_DIR/stop_vsr_anomaly.sh"
else
    echo "Failed to start VSR Anomaly Detector"
    rm "$PID_FILE"
    exit 1
fi