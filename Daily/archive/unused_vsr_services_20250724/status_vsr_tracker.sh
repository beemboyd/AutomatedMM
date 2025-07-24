#!/bin/bash
# Check status of VSR Tracker Service

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
            exit 1
            ;;
    esac
done

PID_FILE="../pids/vsr_tracker_${USER}.pid"
LOG_DIR="../logs/vsr_tracker"
RESULTS_DIR="../alerts/vsr_tracker"

echo "=== VSR Tracker Status ==="
echo "User: $USER"
echo ""

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo "Status: ✗ Not running (no PID file)"
else
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Status: ✓ Running"
        echo "PID: $PID"
        
        # Get process info
        ps -fp "$PID" | tail -n 1
        
        # Check latest log
        if [ -d "$LOG_DIR" ]; then
            LATEST_LOG=$(ls -t "$LOG_DIR"/vsr_tracker_*.log 2>/dev/null | head -1)
            if [ -n "$LATEST_LOG" ]; then
                echo ""
                echo "Latest log entries:"
                tail -5 "$LATEST_LOG"
            fi
        fi
        
        # Check recent high scores from logs
        if [ -d "$LOG_DIR" ]; then
            echo ""
            echo "Recent high scores (≥50):"
            tail -100 "$LATEST_LOG" | grep "Score:" | grep -E "Score: [5-9][0-9]|Score: 100" | tail -5
        fi
    else
        echo "Status: ✗ Not running (stale PID: $PID)"
        echo "Removing stale PID file..."
        rm "$PID_FILE"
    fi
fi

echo ""
echo "Log file: $LOG_DIR/vsr_tracker_$(date +%Y%m%d).log"
echo "View logs: tail -f $LOG_DIR/vsr_tracker_$(date +%Y%m%d).log"