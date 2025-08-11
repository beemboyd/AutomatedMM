#!/bin/bash
# Pre-Market Setup Script for India-TS
# Run this after updating access token to ensure system is ready

cd /Users/maverick/PycharmProjects/India-TS/Daily

echo "=== India-TS Pre-Market Setup ==="
echo "Time: $(date '+%I:%M %p')"
echo ""

echo "Step 1: Update access token"
echo "Please run: python3 loginz.py"
echo "Press Enter after updating config.ini with new token..."
read

echo ""
echo "Step 2: Restart tracker services for new date"
echo "Restarting services to use today's date for log files..."
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
echo "Step 3: Run VSR scanner"
cd scanners && python3 VSR_Momentum_Scanner.py -u Sai && cd ..
if [ $? -eq 0 ]; then
    echo "✓ VSR scanner completed successfully"
else
    echo "✗ VSR scanner failed - check access token"
    exit 1
fi

echo ""
echo "Step 4: Restart alert services"
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist
echo "✓ VSR Telegram service restarted"

echo ""
echo "Step 5: Start hourly breakout"
./alerts/start_hourly_breakout_alerts.sh
echo "✓ Hourly breakout service started"

echo ""
echo "Step 6: Check system status"
./check_all_systems.sh

echo ""
echo "Pre-market setup complete!"
echo "Open dashboards:"
echo "  - VSR: http://localhost:3001"
echo "  - Trend Continuation: http://localhost:3005"
echo "  - Market Regime: http://localhost:8080"