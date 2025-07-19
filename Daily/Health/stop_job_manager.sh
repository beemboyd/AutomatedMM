#!/bin/bash

# India-TS Job Manager Dashboard Stop Script

echo "Stopping India-TS Job Manager Dashboard..."

# Find and kill the process
if pkill -f 'job_manager_dashboard.py'; then
    echo "✅ Job Manager Dashboard stopped successfully"
else
    echo "⚠️  Job Manager Dashboard was not running"
fi

# Verify it's stopped
sleep 1
if lsof -i :9090 > /dev/null 2>&1; then
    echo "❌ Dashboard still running on port 9090. Forcing kill..."
    kill -9 $(lsof -t -i:9090)
fi