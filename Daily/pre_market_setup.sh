#!/bin/bash
# Pre-Market Setup Script for India-TS
# Run this AFTER manually updating access token via loginz.py

cd /Users/maverick/PycharmProjects/India-TS/Daily

echo "=== India-TS Pre-Market Setup ==="
echo "Time: $(date '+%I:%M %p')"
echo "Note: Ensure you have already updated access token via loginz.py"
echo ""

echo "Step 1: Run Long/Short Reversal scanners first"
echo "Running Long Reversal Daily scanner..."
cd scanners && python3 Long_Reversal_Daily.py > /dev/null 2>&1 &
LONG_PID=$!
echo "Running Short Reversal Daily scanner..."
python3 Short_Reversal_Daily.py > /dev/null 2>&1 &
SHORT_PID=$!
echo "Waiting for scanners to complete (max 60 seconds)..."
COUNTER=0
while [ $COUNTER -lt 60 ]; do
    if ! ps -p $LONG_PID > /dev/null && ! ps -p $SHORT_PID > /dev/null; then
        echo "✓ Long/Short Reversal scanners completed"
        break
    fi
    sleep 1
    COUNTER=$((COUNTER + 1))
done
if [ $COUNTER -eq 60 ]; then
    kill $LONG_PID 2>/dev/null
    kill $SHORT_PID 2>/dev/null
    echo "⚠ Scanners took too long, proceeding anyway"
fi
cd ..

echo ""
echo "Step 2: Clean up JSON persistence files"
echo "Resetting tracker persistence files for new day..."
CURRENT_TIME=$(date '+%Y-%m-%d %H:%M:00')
echo "{\"tickers\": {}, \"last_updated\": \"$CURRENT_TIME\"}" > /Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence_hourly_long.json
echo "{\"tickers\": {}, \"last_updated\": \"$CURRENT_TIME\"}" > /Users/maverick/PycharmProjects/India-TS/Daily/data/short_momentum/vsr_ticker_persistence_hourly_short.json
echo "{\"tickers\": {}, \"last_updated\": \"$CURRENT_TIME\"}" > /Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence.json
echo "✓ JSON persistence files reset"

echo ""
echo "Step 3: Restart tracker services for new date"
echo "Restarting services to use today's date for log files..."
# Kill any existing tracker processes first
pkill -f "hourly_tracker_service" 2>/dev/null
pkill -f "hourly_short_tracker_service" 2>/dev/null
sleep 2
# Restart via launchctl
launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist 2>/dev/null
sleep 1
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist
launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly-short-tracker-service.plist 2>/dev/null
sleep 1
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-short-tracker-service.plist
launchctl unload ~/Library/LaunchAgents/com.india-ts.short-momentum-tracker.plist 2>/dev/null
sleep 1
launchctl load ~/Library/LaunchAgents/com.india-ts.short-momentum-tracker.plist
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-tracker-enhanced.plist 2>/dev/null
sleep 1
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-tracker-enhanced.plist
echo "✓ Tracker services restarted"

echo ""
echo "Step 4: Run VSR scanner"
cd scanners && python3 VSR_Momentum_Scanner.py -u Sai && cd ..
if [ $? -eq 0 ]; then
    echo "✓ VSR scanner completed successfully"
else
    echo "✗ VSR scanner failed - check access token"
    exit 1
fi

echo ""
echo "Step 5: Restart alert services"
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist
echo "✓ VSR Telegram service restarted"

echo ""
echo "Step 6: Start hourly breakout"
./alerts/start_hourly_breakout_alerts.sh
echo "✓ Hourly breakout service started"

echo ""
echo "Step 7: Restart dashboards for fresh data"
echo "Killing existing dashboard processes..."
pkill -f "tracker_dashboard.py" 2>/dev/null
pkill -f "momentum_dashboard.py" 2>/dev/null
sleep 2
echo "Starting dashboards..."
cd dashboards
nohup python3 vsr_tracker_dashboard.py > vsr_dashboard.log 2>&1 &
echo "✓ VSR Dashboard started on port 3001"
nohup python3 hourly_tracker_dashboard.py > hourly_dashboard.log 2>&1 &
echo "✓ Hourly Tracker Dashboard started on port 3002"
nohup python3 short_momentum_dashboard.py > short_momentum_dashboard.log 2>&1 &
echo "✓ Short Momentum Dashboard started on port 3003"
nohup python3 hourly_short_tracker_dashboard.py > hourly_short_dashboard.log 2>&1 &
echo "✓ Hourly Short Dashboard started on port 3004"
cd ..

echo ""
echo "Step 8: Check system status"
./check_all_systems.sh

echo ""
echo "Pre-market setup complete!"
echo "Open dashboards:"
echo "  - VSR: http://localhost:3001"
echo "  - Trend Continuation: http://localhost:3005"
echo "  - Market Regime: http://localhost:8080"