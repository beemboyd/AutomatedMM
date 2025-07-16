#!/bin/bash
# Check status of VSR Monitor Service

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

PID_FILE="../pids/vsr_monitor_${USER}.pid"
LOG_DIR="../logs/$USER"
ALERT_DIR="../alerts/$USER/vsr_monitor"

echo "=== VSR Monitor Status ==="
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
            LATEST_LOG=$(ls -t "$LOG_DIR"/vsr_monitor_${USER}_*.log 2>/dev/null | head -1)
            if [ -n "$LATEST_LOG" ]; then
                echo ""
                echo "Latest log entries:"
                tail -5 "$LATEST_LOG"
            fi
        fi
        
        # Check alerts
        if [ -d "$ALERT_DIR" ]; then
            LATEST_ALERTS="$ALERT_DIR/latest_alerts.json"
            if [ -f "$LATEST_ALERTS" ]; then
                echo ""
                ALERT_COUNT=$(python3 -c "import json; data=json.load(open('$LATEST_ALERTS')); print(len(data))" 2>/dev/null || echo "0")
                echo "Recent alerts: $ALERT_COUNT"
                
                # Show dashboard path
                DASHBOARD="$ALERT_DIR/vsr_monitor_dashboard.html"
                if [ -f "$DASHBOARD" ]; then
                    echo "Dashboard: file://$(realpath "$DASHBOARD")"
                fi
            fi
        fi
    else
        echo "Status: ✗ Not running (stale PID: $PID)"
        echo "Removing stale PID file..."
        rm "$PID_FILE"
    fi
fi