#!/bin/bash

echo "=========================================="
echo "Stopping India-TS Dashboards"
echo "=========================================="

# Stop Main Dashboard
echo -n "Stopping Main Dashboard (Port 8080)... "
if launchctl unload /Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist 2>/dev/null; then
    echo "✅ Stopped"
else
    echo "⚠️  Not running or already stopped"
fi

# Stop Health Dashboard
echo -n "Stopping Health Dashboard (Port 7080)... "
if launchctl unload /Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist 2>/dev/null; then
    echo "✅ Stopped"
else
    echo "⚠️  Not running or already stopped"
fi

echo ""
echo "=========================================="
echo "Verifying shutdown..."
echo "=========================================="

sleep 2

# Check if ports are still in use
if lsof -i :8080 >/dev/null 2>&1; then
    echo "⚠️  Warning: Port 8080 still in use"
    echo "   PID: $(lsof -ti :8080)"
else
    echo "✅ Port 8080 is free"
fi

if lsof -i :7080 >/dev/null 2>&1; then
    echo "⚠️  Warning: Port 7080 still in use"
    echo "   PID: $(lsof -ti :7080)"
else
    echo "✅ Port 7080 is free"
fi

echo ""
echo "To restart dashboards, run:"
echo "  /Users/maverick/PycharmProjects/India-TS/Daily/utils/start_dashboards.sh"