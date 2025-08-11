#!/bin/bash

# Start All Breakout Alert Services
# This script starts all required services for breakout alerts in the correct order

echo "=== Starting All Breakout Alert Services ==="
echo "Timestamp: $(date '+%Y-%m-%d %I:%M %p IST')"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Base directory
BASE_DIR="/Users/maverick/PycharmProjects/India-TS"

# 1. Check prerequisites
echo "1. Checking prerequisites..."
prereq_ok=true

# Check Long Reversal scanner
if launchctl list | grep -q "long_reversal_daily"; then
    echo -e "   ${GREEN}✓${NC} Long Reversal scanner is loaded"
else
    echo -e "   ${RED}✗${NC} Long Reversal scanner not loaded!"
    echo "   Loading scanner..."
    launchctl load ~/Library/LaunchAgents/com.india-ts.long_reversal_daily.plist
fi

# Check config.ini exists
if [ -f "$BASE_DIR/Daily/config.ini" ]; then
    echo -e "   ${GREEN}✓${NC} config.ini found"
else
    echo -e "   ${RED}✗${NC} config.ini not found!"
    prereq_ok=false
fi

if [ "$prereq_ok" = false ]; then
    echo -e "\n${RED}Prerequisites not met. Please fix issues and try again.${NC}"
    exit 1
fi

echo ""

# 2. Run VSR scanner if needed
echo "2. Checking VSR scanner data..."
VSR_FILE="$BASE_DIR/Daily/data/vsr_ticker_persistence.json"

if [ ! -f "$VSR_FILE" ]; then
    echo -e "   ${YELLOW}!${NC} VSR persistence file not found. Running scanner..."
    need_vsr=true
elif [ $(find "$VSR_FILE" -mmin +360 | wc -l) -gt 0 ]; then
    echo -e "   ${YELLOW}!${NC} VSR data is older than 6 hours. Running scanner..."
    need_vsr=true
else
    echo -e "   ${GREEN}✓${NC} VSR data is recent"
    need_vsr=false
fi

if [ "$need_vsr" = true ]; then
    cd "$BASE_DIR/Daily/scanners"
    echo "   Running VSR scanner..."
    python3 VSR_Momentum_Scanner.py -u Sai
    if [ $? -eq 0 ]; then
        echo -e "   ${GREEN}✓${NC} VSR scanner completed"
    else
        echo -e "   ${RED}✗${NC} VSR scanner failed"
    fi
fi

echo ""

# 3. Start hourly breakout service
echo "3. Starting Hourly Breakout Service..."
cd "$BASE_DIR/Daily/alerts"

# Check if already running
if ps aux | grep -q "[h]ourly_breakout_alert_service.py"; then
    echo -e "   ${YELLOW}!${NC} Service already running"
else
    ./start_hourly_breakout_alerts.sh > /dev/null 2>&1
    sleep 2
    if ps aux | grep -q "[h]ourly_breakout_alert_service.py"; then
        echo -e "   ${GREEN}✓${NC} Hourly breakout service started"
    else
        echo -e "   ${RED}✗${NC} Failed to start hourly breakout service"
    fi
fi

echo ""

# 4. Load first hour service plist
echo "4. Loading First Hour Service..."
current_hour=$(date +%H)
current_min=$(date +%M)

if launchctl list | grep -q "first-hour-alerts"; then
    echo -e "   ${GREEN}✓${NC} First hour service plist already loaded"
else
    launchctl load ~/Library/LaunchAgents/com.india-ts.first-hour-alerts.plist 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "   ${GREEN}✓${NC} First hour service plist loaded"
    else
        echo -e "   ${YELLOW}!${NC} First hour service plist may already be loaded"
    fi
fi

# Check if it should be running now
if [ $current_hour -eq 9 ] && [ $current_min -ge 14 ]; then
    echo "   Note: First hour service should be active now"
elif [ $current_hour -ge 10 ]; then
    echo "   Note: First hour service only runs 9:14-10:15 AM"
fi

echo ""

# 5. Wait for services to initialize
echo "5. Waiting for services to initialize..."
sleep 3

# 6. Verify services are tracking tickers
echo "6. Verifying service status..."
python3 -c "
import json
try:
    with open('$BASE_DIR/Daily/data/hourly_breakout_state.json', 'r') as f:
        data = json.load(f)
        tracked = len(data.get('tracked_tickers', {}))
        if tracked > 0:
            print(f'   ✓ Tracking {tracked} tickers')
        else:
            print('   ! No tickers being tracked yet')
except:
    print('   ! State file not ready yet')
"

echo ""

# 7. Open dashboards
echo "7. Opening dashboards..."
echo "   Opening Hourly Breakout Dashboard (port 3005)..."
open http://localhost:3005 2>/dev/null || echo "   Note: Dashboard may take a moment to load"

if [ $current_hour -eq 9 ] && [ $current_min -ge 14 ] || [ $current_hour -eq 10 ] && [ $current_min -lt 15 ]; then
    echo "   Opening First Hour Dashboard (port 3006)..."
    open http://localhost:3006 2>/dev/null || echo "   Note: Dashboard may take a moment to load"
fi

echo ""

# 8. Run comprehensive status check
echo "8. Running comprehensive status check..."
echo ""
sleep 2
./check_breakout_status.sh

echo ""
echo "=== Startup Complete ==="
echo ""
echo "Quick Commands:"
echo "  - Check status:    ./check_breakout_status.sh"
echo "  - View logs:       tail -f ../logs/alerts_hourlybo/hourly_breakout_*.log"
echo "  - Stop services:   ./stop_hourly_breakout_alerts.sh"
echo ""