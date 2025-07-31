#!/bin/bash
# Start Short Momentum Dashboard

echo "Starting Short Momentum Dashboard..."

# Change to the dashboard directory
cd /Users/maverick/PycharmProjects/India-TS/Daily/dashboards

# Kill any existing process on port 3003
lsof -ti:3003 | xargs kill -9 2>/dev/null

# Start the dashboard in the background
nohup python3 short_momentum_dashboard.py > short_momentum_dashboard.log 2>&1 &

# Save the PID
echo $! > short_momentum_dashboard.pid

echo "Short Momentum Dashboard started on port 3003"
echo "PID: $(cat short_momentum_dashboard.pid)"
echo "Access at: http://localhost:3003"
echo "Logs: short_momentum_dashboard.log"