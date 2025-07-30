#!/bin/bash
# Start Hourly Tracker Dashboard

echo "Starting Hourly Tracker Dashboard..."

# Change to the dashboard directory
cd /Users/maverick/PycharmProjects/India-TS/Daily/dashboards

# Kill any existing process on port 3002
lsof -ti:3002 | xargs kill -9 2>/dev/null

# Start the dashboard in the background
nohup python3 hourly_tracker_dashboard.py > hourly_dashboard.log 2>&1 &

# Save the PID
echo $! > hourly_dashboard.pid

echo "Hourly Tracker Dashboard started on port 3002"
echo "PID: $(cat hourly_dashboard.pid)"
echo "Access at: http://localhost:3002"
echo "Logs: hourly_dashboard.log"