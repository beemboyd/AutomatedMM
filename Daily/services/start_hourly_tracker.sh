#!/bin/bash
# Start Hourly Tracker Service

echo "Starting Hourly Tracker Service..."

# Change to the services directory
cd /Users/maverick/PycharmProjects/India-TS/Daily/services

# Kill any existing hourly tracker process
pkill -f "hourly_tracker_service.py" 2>/dev/null

# Start the service in the background
nohup python3 hourly_tracker_service.py --user Sai --interval 60 > hourly_tracker.log 2>&1 &

# Save the PID
echo $! > hourly_tracker.pid

echo "Hourly Tracker Service started"
echo "PID: $(cat hourly_tracker.pid)"
echo "Logs: hourly_tracker.log"
echo "Dashboard: http://localhost:3002"