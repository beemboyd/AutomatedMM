#!/bin/bash

# SL Watchdog Dashboard Launcher
# Port: 2001

echo "🛡️  Starting SL Watchdog Dashboard..."
echo "=========================================="

cd "$(dirname "$0")"

# Kill any existing process on port 2001
lsof -ti:2001 | xargs kill -9 2>/dev/null

# Start the dashboard
python3 sl_watchdog_dashboard.py

echo "Dashboard stopped."