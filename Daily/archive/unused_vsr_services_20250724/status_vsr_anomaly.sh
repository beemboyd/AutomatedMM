#!/bin/bash

# VSR Anomaly Detector Service Status Script

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
PID_DIR="$BASE_DIR/pids"
LOG_DIR="$BASE_DIR/logs/vsr_anomaly"
PID_FILE="$PID_DIR/vsr_anomaly_detector.pid"

echo "=== VSR Anomaly Detector Service Status ==="
echo ""

if [ ! -f "$PID_FILE" ]; then
    echo "Status: STOPPED (no PID file found)"
    exit 0
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "Status: RUNNING"
    echo "PID: $PID"
    
    # Get process info
    echo ""
    echo "Process Info:"
    ps -p "$PID" -o pid,ppid,user,%cpu,%mem,etime,cmd | tail -n +1
    
    # Get latest log file
    TODAY=$(date +%Y%m%d)
    LOG_FILE="$LOG_DIR/vsr_anomaly_${TODAY}.log"
    
    if [ -f "$LOG_FILE" ]; then
        echo ""
        echo "Recent log entries:"
        echo "-------------------"
        tail -n 20 "$LOG_FILE"
        echo ""
        echo "Log file: $LOG_FILE"
    fi
else
    echo "Status: STOPPED (process not found)"
    echo "Stale PID: $PID"
    rm "$PID_FILE"
fi