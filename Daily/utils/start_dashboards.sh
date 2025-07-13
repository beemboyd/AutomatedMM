#!/bin/bash

echo "=========================================="
echo "Starting India-TS Dashboards"
echo "=========================================="

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -i :$port >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Start Main Dashboard (Port 8080)
echo -n "Starting Main Dashboard (Port 8080)... "
if check_port 8080; then
    echo "Already running!"
else
    launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist 2>/dev/null
    sleep 2
    if check_port 8080; then
        echo "✅ Started successfully"
    else
        echo "❌ Failed to start"
    fi
fi

# Start Health Dashboard (Port 7080)
echo -n "Starting Health Dashboard (Port 7080)... "
if check_port 7080; then
    echo "Already running!"
else
    launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist 2>/dev/null
    sleep 2
    if check_port 7080; then
        echo "✅ Started successfully"
    else
        echo "❌ Failed to start"
    fi
fi

echo ""
echo "=========================================="
echo "Dashboard Status:"
echo "=========================================="

# Check and display status
if check_port 8080; then
    echo "✅ Main Dashboard: http://localhost:8080"
else
    echo "❌ Main Dashboard: Not running"
fi

if check_port 7080; then
    echo "✅ Health Dashboard: http://localhost:7080"
else
    echo "❌ Health Dashboard: Not running"
fi

echo ""
echo "To open dashboards in browser:"
echo "  open http://localhost:8080  # Main dashboard"
echo "  open http://localhost:7080  # Health dashboard"
echo ""
echo "To stop dashboards, run:"
echo "  /Users/maverick/PycharmProjects/India-TS/Daily/utils/stop_dashboards.sh"