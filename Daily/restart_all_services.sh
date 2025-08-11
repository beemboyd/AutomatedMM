#!/bin/bash
# Emergency Restart Script - Restarts all India-TS services
# Use when system is not responding correctly

echo "=== Stopping all India-TS services ==="

# Stop dashboards
echo "Stopping dashboards..."
pkill -f "tracker_dashboard.py"
pkill -f "momentum_dashboard.py"
pkill -f "market_regime_dashboard"
pkill -f "hourly_breakout_dashboard"

# Unload all services
echo "Unloading launchctl services..."
for plist in ~/Library/LaunchAgents/com.india-ts.*.plist; do
    if [ -f "$plist" ]; then
        launchctl unload "$plist" 2>/dev/null
        echo "  Unloaded: $(basename $plist)"
    fi
done

echo ""
echo "Waiting 5 seconds..."
sleep 5

echo ""
echo "=== Starting core services ==="

# Load scanners
echo "Loading scanner services..."
launchctl load ~/Library/LaunchAgents/com.india-ts.long_reversal_daily.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.short_reversal_daily.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.long-reversal-hourly.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.short-reversal-hourly.plist

# Load market regime
echo "Loading market regime analyzer..."
launchctl load ~/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist

# Load VSR services
echo "Loading VSR services..."
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-tracker-enhanced.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist

# Load tracker services
echo "Loading tracker services..."
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.short-momentum-tracker.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-short-tracker-service.plist

# Start dashboards
echo "Starting dashboards..."
cd /Users/maverick/PycharmProjects/India-TS/Daily
./utils/start_market_breadth_dashboard.sh &
./alerts/start_hourly_breakout_alerts.sh &
./dashboards/start_vsr_dashboard.sh &

echo ""
echo "Waiting for services to start..."
sleep 10

echo ""
echo "=== Service Status ==="
launchctl list | grep com.india-ts | grep -v "^-" | awk '{print $3 " (PID: " $1 ")"}'

echo ""
echo "All services restarted!"
echo ""
echo "Verify dashboards:"
echo "  - VSR: http://localhost:3001"
echo "  - Hourly Long: http://localhost:3002"
echo "  - Short Momentum: http://localhost:3003"
echo "  - Hourly Short: http://localhost:3004"
echo "  - Trend Continuation: http://localhost:3005"
echo "  - Market Regime: http://localhost:8080"