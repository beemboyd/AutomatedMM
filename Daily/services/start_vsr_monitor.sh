#!/bin/bash
# Start VSR Monitor Service

# Set working directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Default values
USER="Sai"
INTERVAL="5m"
THRESHOLD=50

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--user)
            USER="$2"
            shift 2
            ;;
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        -t|--threshold)
            THRESHOLD="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [-u USER] [-i INTERVAL] [-t THRESHOLD]"
            echo "  -u USER: User name (default: Sai)"
            echo "  -i INTERVAL: Time interval - 5m, 15m, 30m (default: 5m)"
            echo "  -t THRESHOLD: Alert threshold score 0-100 (default: 50)"
            exit 1
            ;;
    esac
done

# Create PID directory
PID_DIR="../pids"
mkdir -p "$PID_DIR"
PID_FILE="$PID_DIR/vsr_monitor_${USER}.pid"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "VSR Monitor is already running for user $USER (PID: $OLD_PID)"
        echo "Stop it first with: ./stop_vsr_monitor.sh -u $USER"
        exit 1
    else
        echo "Removing stale PID file"
        rm "$PID_FILE"
    fi
fi

# Create log directory
LOG_DIR="../logs/$USER"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/vsr_monitor_${USER}_$(date +%Y%m%d).log"

echo "Starting VSR Monitor Service..."
echo "User: $USER"
echo "Interval: $INTERVAL"
echo "Alert Threshold: $THRESHOLD"
echo "Log file: $LOG_FILE"

# Start the service in background
nohup python3 vsr_monitor_service.py -u "$USER" -i "$INTERVAL" -t "$THRESHOLD" >> "$LOG_FILE" 2>&1 &
PID=$!

# Save PID
echo $PID > "$PID_FILE"

# Wait a moment to check if it started successfully
sleep 2

if ps -p "$PID" > /dev/null 2>&1; then
    echo "✓ VSR Monitor started successfully (PID: $PID)"
    echo "Dashboard: file://$(pwd)/../alerts/$USER/vsr_monitor/vsr_monitor_dashboard.html"
    echo "Logs: tail -f $LOG_FILE"
else
    echo "✗ Failed to start VSR Monitor"
    rm "$PID_FILE"
    exit 1
fi