#!/bin/bash
# Stop VSR Monitor Service

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

if [ ! -f "$PID_FILE" ]; then
    echo "VSR Monitor is not running for user $USER (no PID file found)"
    exit 0
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "Stopping VSR Monitor for user $USER (PID: $PID)..."
    kill "$PID"
    
    # Wait for process to stop
    sleep 2
    
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Process didn't stop gracefully, forcing..."
        kill -9 "$PID"
    fi
    
    echo "✓ VSR Monitor stopped"
else
    echo "VSR Monitor process not found (PID: $PID)"
fi

# Remove PID file
rm -f "$PID_FILE"