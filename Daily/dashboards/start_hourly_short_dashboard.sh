#!/bin/bash
# Start Hourly Short Tracker Dashboard

echo "Starting Hourly Short Tracker Dashboard..."

# Change to the dashboard directory
cd /Users/maverick/PycharmProjects/India-TS/Daily/dashboards

# Kill any existing process on port 3004
lsof -ti:3004 | xargs kill -9 2>/dev/null

# Start the dashboard in the background
nohup python3 hourly_short_tracker_dashboard.py > hourly_short_dashboard.log 2>&1 &

# Save the PID
echo $! > hourly_short_dashboard.pid

echo "Hourly Short Tracker Dashboard started on port 3004"
echo "PID: $(cat hourly_short_dashboard.pid)"
echo "Access at: http://localhost:3004"
echo "Logs: hourly_short_dashboard.log"