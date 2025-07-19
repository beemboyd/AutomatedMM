#!/bin/bash

# India-TS Job Manager Dashboard Startup Script

echo "Starting India-TS Job Manager Dashboard..."

# Set the working directory
cd /Users/maverick/PycharmProjects/India-TS/Daily/Health

# Check if already running
if lsof -i :9090 > /dev/null 2>&1; then
    echo "Job Manager Dashboard is already running on port 9090"
    echo "Access it at: http://localhost:9090"
    exit 0
fi

# Start the dashboard
echo "Starting dashboard on port 9090..."
python3 job_manager_dashboard.py &

# Wait a moment for the server to start
sleep 2

# Check if it started successfully
if lsof -i :9090 > /dev/null 2>&1; then
    echo "✅ Job Manager Dashboard started successfully!"
    echo "Access it at: http://localhost:9090"
    echo ""
    echo "Features:"
    echo "- Monitor all India-TS scheduled jobs"
    echo "- Real-time status updates"
    echo "- Reload, restart, and stop controls for each job"
    echo ""
    echo "To stop the dashboard, use: pkill -f 'job_manager_dashboard.py'"
else
    echo "❌ Failed to start Job Manager Dashboard"
    exit 1
fi