#!/bin/bash

# VSR Anomaly Detector Service Stop Script

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
PID_DIR="$BASE_DIR/pids"
PID_FILE="$PID_DIR/vsr_anomaly_detector.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "VSR Anomaly Detector is not running (no PID file found)"
    exit 0
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "Stopping VSR Anomaly Detector (PID: $PID)..."
    kill "$PID"
    
    # Wait for process to stop
    COUNT=0
    while ps -p "$PID" > /dev/null 2>&1 && [ $COUNT -lt 10 ]; do
        sleep 1
        COUNT=$((COUNT+1))
    done
    
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Process didn't stop gracefully, forcing..."
        kill -9 "$PID"
    fi
    
    rm "$PID_FILE"
    echo "VSR Anomaly Detector stopped successfully"
else
    echo "VSR Anomaly Detector is not running (process not found)"
    rm "$PID_FILE"
fi