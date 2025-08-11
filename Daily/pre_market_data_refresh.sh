#!/bin/bash
# Enhanced Pre-Market Data Refresh Script
# Addresses all dashboard data staleness issues
# Run this at 8:45 AM IST daily

cd /Users/maverick/PycharmProjects/India-TS/Daily

echo "==================================================="
echo "India-TS Pre-Market Data Refresh"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S IST')"
echo "==================================================="
echo ""

# Function to handle errors
handle_error() {
    echo "❌ Error: $1"
    echo "Continuing with next step..."
}

# Step 1: Generate Market Breadth Data
echo "Step 1: Generating Market Breadth Data..."
echo "----------------------------------------"
cd scanners
timeout 300 python3 Market_Breadth_Scanner.py -u Sai 2>&1 | tail -5
if [ $? -eq 0 ] || [ $? -eq 124 ]; then
    echo "✅ Market Breadth Scanner completed or timed out gracefully"
else
    handle_error "Market Breadth Scanner failed"
fi
cd ..

# Step 2: Update Market Breadth Symlink
echo ""
echo "Step 2: Updating Market Breadth Symlink..."
echo "-------------------------------------------"
cd Market_Regime/breadth_data
latest_breadth=$(ls -t market_breadth_2*.json 2>/dev/null | head -1)
if [ ! -z "$latest_breadth" ]; then
    rm -f market_breadth_latest.json
    ln -s "$latest_breadth" market_breadth_latest.json
    echo "✅ Symlink updated to: $latest_breadth"
else
    handle_error "No market breadth files found"
fi
cd ../..

# Step 3: Run VSR Scanner
echo ""
echo "Step 3: Running VSR Scanner..."
echo "-------------------------------"
cd scanners
timeout 120 python3 VSR_Momentum_Scanner.py -u Sai 2>&1 | tail -5
if [ $? -eq 0 ] || [ $? -eq 124 ]; then
    echo "✅ VSR Scanner completed"
else
    handle_error "VSR Scanner failed"
fi
cd ..

# Step 4: Update Historical Breadth Data
echo ""
echo "Step 4: Updating Historical Breadth Data..."
echo "--------------------------------------------"
cd Market_Regime
python3 append_historical_breadth.py 2>&1 | tail -5
if [ $? -eq 0 ]; then
    echo "✅ Historical breadth data updated"
else
    handle_error "Historical breadth update failed"
fi
cd ..

# Step 5: Clear Persistence Files
echo ""
echo "Step 5: Clearing Stale Persistence Data..."
echo "-------------------------------------------"
# Reset persistence files to today's date
today=$(date '+%Y-%m-%d %H:%M:%S')
echo "{\"tickers\": {}, \"last_updated\": \"$today\"}" > data/vsr_ticker_persistence_hourly_long.json
echo "{\"tickers\": {}, \"last_updated\": \"$today\"}" > data/short_momentum/vsr_ticker_persistence_hourly_short.json
echo "✅ Persistence files reset for today"

# Step 6: Restart All Tracker Services
echo ""
echo "Step 6: Restarting Tracker Services..."
echo "---------------------------------------"
services=(
    "hourly-tracker-service"
    "hourly-short-tracker-service"
    "short-momentum-tracker"
    "vsr-tracker-enhanced"
    "vsr-telegram-alerts-enhanced"
)

for service in "${services[@]}"; do
    echo "Restarting $service..."
    launchctl unload ~/Library/LaunchAgents/com.india-ts.$service.plist 2>/dev/null
    sleep 1
    launchctl load ~/Library/LaunchAgents/com.india-ts.$service.plist
done
echo "✅ All tracker services restarted"

# Step 7: Restart Alert Services
echo ""
echo "Step 7: Restarting Alert Services..."
echo "-------------------------------------"
launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly-breakout-alerts.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-breakout-alerts.plist
echo "✅ Alert services restarted"

# Step 8: Verify Dashboard Accessibility
echo ""
echo "Step 8: Verifying Dashboard Status..."
echo "--------------------------------------"
dashboards=(
    "3001:VSR"
    "3002:Hourly Tracker"
    "3003:Short Momentum"
    "3004:Hourly Short"
    "3005:Hourly Breakout"
    "5001:Market Breadth"
    "8080:Market Regime"
)

for dashboard in "${dashboards[@]}"; do
    port="${dashboard%%:*}"
    name="${dashboard##*:}"
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:$port | grep -q "200"; then
        echo "✅ $name Dashboard (port $port): Running"
    else
        echo "⚠️  $name Dashboard (port $port): Not accessible"
    fi
done

# Step 9: Summary
echo ""
echo "==================================================="
echo "Pre-Market Data Refresh Complete!"
echo "==================================================="
echo ""
echo "Key Updates:"
echo "  • Market Breadth: $(ls -la Market_Regime/breadth_data/market_breadth_latest.json | awk '{print $NF}')"
echo "  • VSR Scan: $(ls -t scanners/Hourly/VSR_*.xlsx 2>/dev/null | head -1 | xargs basename)"
echo "  • Services: All restarted with today's date"
echo "  • Persistence: Reset for fresh tracking"
echo ""
echo "Next Steps:"
echo "  1. Update access token if needed: python3 loginz.py"
echo "  2. Check dashboards at URLs listed above"
echo "  3. Monitor logs in Daily/logs/ for any issues"
echo ""
echo "Time completed: $(date '+%H:%M:%S')"