#!/bin/bash

# Start Persistence Level Tracker Service
# This service tracks VSR persistence levels and sends Telegram notifications

echo "Starting Persistence Level Tracker Service..."

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

# Check if service is already running
if pgrep -f "persistence_level_tracker.py" > /dev/null; then
    echo "Persistence tracker is already running. Stopping existing instance..."
    pkill -f "persistence_level_tracker.py"
    sleep 2
fi

# Start the service in background
cd "$BASE_DIR"
nohup python3 services/persistence_level_tracker.py > logs/persistence_tracker/persistence_tracker.out 2>&1 &

echo "Persistence Level Tracker started with PID: $!"
echo "Logs: $BASE_DIR/logs/persistence_tracker/"

# Save PID for stopping later
echo $! > "$BASE_DIR/data/persistence_tracker.pid"

echo "✅ Persistence Level Tracker Service started successfully"