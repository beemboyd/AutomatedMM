#!/bin/bash
# Start VSR Tracker Service - Simplified Version

# Set working directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Default user
USER="Sai"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--user)
            USER="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [-u USER]"
            echo "  -u USER: User name (default: Sai)"
            exit 1
            ;;
    esac
done

# Create PID directory
PID_DIR="../pids"
mkdir -p "$PID_DIR"
PID_FILE="$PID_DIR/vsr_tracker_${USER}.pid"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "VSR Tracker is already running for user $USER (PID: $OLD_PID)"
        echo "Stop it first with: ./stop_vsr_tracker.sh -u $USER"
        exit 1
    else
        echo "Removing stale PID file"
        rm "$PID_FILE"
    fi
fi

# Create log directory
LOG_DIR="../logs/vsr_tracker"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/vsr_tracker_$(date +%Y%m%d).log"

echo "Starting VSR Tracker Service..."
echo "User: $USER"
echo "Mode: Minute-by-minute scoring with hourly data"
echo "Log file: $LOG_FILE"

# Start the service in background
nohup python3 vsr_tracker_service.py -u "$USER" >> "$LOG_FILE" 2>&1 &
PID=$!

# Save PID
echo $PID > "$PID_FILE"

# Wait a moment to check if it started successfully
sleep 3

if ps -p "$PID" > /dev/null 2>&1; then
    echo "✓ VSR Tracker started successfully (PID: $PID)"
    echo "View logs: tail -f $LOG_FILE"
    echo "High scores: tail -f $LOG_FILE | grep -E 'Score: [5-9][0-9]|Score: 100'"
else
    echo "✗ Failed to start VSR Tracker"
    rm "$PID_FILE"
    exit 1
fi