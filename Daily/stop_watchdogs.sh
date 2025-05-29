#!/bin/bash

# Stop all SL_watchdog.py processes irrespective of user or status
# This script kills ALL SL_watchdog processes system-wide

cd "$(dirname "${BASH_SOURCE[0]}")"

echo "Stopping all SL_watchdog processes..."

# Kill all SL_watchdog.py processes
WATCHDOG_PIDS=$(pgrep -f "SL_watchdog.py" 2>/dev/null)

if [ -n "$WATCHDOG_PIDS" ]; then
    echo "Found SL_watchdog processes: $WATCHDOG_PIDS"
    echo "$WATCHDOG_PIDS" | xargs -I {} bash -c '
        echo "Killing process: {}"
        kill -TERM {} 2>/dev/null
        sleep 1
        if ps -p {} > /dev/null 2>&1; then
            echo "Force killing process: {}"
            kill -9 {} 2>/dev/null
        fi
    '

    # Clean up PID files
    if [ -d "pids" ]; then
        rm -f pids/watchdog_*.pid
        echo "Cleaned up PID files"
    fi

    echo "All SL_watchdog processes stopped"
else
    echo "No SL_watchdog processes found"
fi

# Also call the manage_watchdogs.sh stop for completeness
./manage_watchdogs.sh stop "$@"