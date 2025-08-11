#!/bin/bash

# Breakout Alert Services Status Check Script
# This script provides a comprehensive status check of all breakout alert services

echo "=== Breakout Alert Services Status ==="
echo "Timestamp: $(date '+%Y-%m-%d %I:%M %p IST')"
echo ""

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check services
echo "1. Service Status:"
hourly_status=$(launchctl list | grep hourly-breakout-alerts | awk '{print $1}')
first_hour_status=$(launchctl list | grep first-hour-alerts | awk '{print $1}')

if [ "$hourly_status" == "0" ] || [ "$hourly_status" == "-" ]; then
    echo -e "   Hourly Breakout: ${GREEN}✓ Running${NC} (PID: $hourly_status)"
else
    echo -e "   Hourly Breakout: ${RED}✗ Not Running${NC}"
fi

if [ "$first_hour_status" == "0" ] || [ "$first_hour_status" == "-" ]; then
    echo -e "   First Hour: ${GREEN}✓ Running${NC} (PID: $first_hour_status)"
else
    echo -e "   First Hour: ${RED}✗ Not Running${NC}"
fi
echo ""

# Check processes
echo "2. Running Processes:"
hourly_procs=$(ps aux | grep -E "hourly_breakout_alert_service.py" | grep -v grep | wc -l)
first_hour_procs=$(ps aux | grep -E "first_hour_breakout_service.py" | grep -v grep | wc -l)
echo "   Hourly breakout processes: $hourly_procs"
echo "   First hour processes: $first_hour_procs"
echo ""

# Check recent alerts
echo "3. Recent Alerts (last hour):"
if [ -d "/Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_hourlybo" ]; then
    hourly_alerts=$(find /Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_hourlybo -name "*.log" -mmin -60 -exec grep "Alert sent" {} \; 2>/dev/null | wc -l)
    echo "   Hourly breakout alerts: $hourly_alerts"
fi

if [ -d "/Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_firsthour" ]; then
    first_hour_alerts=$(find /Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_firsthour -name "*.log" -mmin -60 -exec grep "Alert sent" {} \; 2>/dev/null | wc -l)
    echo "   First hour alerts: $first_hour_alerts"
fi
echo ""

# Check tracked tickers
echo "4. Tracked Tickers:"
python3 -c "
import json
import os
from datetime import datetime

try:
    state_file = '/Users/maverick/PycharmProjects/India-TS/Daily/data/hourly_breakout_state.json'
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            data = json.load(f)
            tracked = len(data.get('tracked_tickers', {}))
            alerted = len(data.get('alerted_breakouts', {}))
            last_update = data.get('last_update', 'Unknown')
            
            print(f'   Total tracked: {tracked}')
            print(f'   Alerts sent today: {alerted}')
            print(f'   Last update: {last_update}')
            
            # Show top movers if any
            if tracked > 0:
                print('\\n   Top momentum tickers:')
                tickers = data.get('tracked_tickers', {})
                sorted_tickers = sorted(tickers.items(), 
                                      key=lambda x: x[1].get('daily_data', {}).get('momentum', 0), 
                                      reverse=True)[:5]
                for ticker, info in sorted_tickers:
                    momentum = info.get('daily_data', {}).get('momentum', 0)
                    print(f'     {ticker}: {momentum:.2f}%')
except Exception as e:
    print(f'   Unable to read state file: {e}')
" 2>/dev/null || echo "   Unable to read state file"
echo ""

# Check dashboards
echo "5. Dashboard Status:"
if curl -s http://localhost:3005 > /dev/null 2>&1; then
    echo -e "   Port 3005 (Hourly): ${GREEN}✓ Running${NC}"
    # Get some stats from dashboard if available
    stats=$(curl -s http://localhost:3005/api/stats 2>/dev/null || echo "{}")
    if [ "$stats" != "{}" ]; then
        echo "     $stats" | python3 -m json.tool 2>/dev/null | head -5 || true
    fi
else
    echo -e "   Port 3005 (Hourly): ${RED}✗ Not responding${NC}"
fi

if curl -s http://localhost:3006 > /dev/null 2>&1; then
    echo -e "   Port 3006 (First Hour): ${GREEN}✓ Running${NC}"
else
    current_hour=$(date +%H)
    if [ $current_hour -ge 10 ] && [ $current_hour -lt 16 ]; then
        echo -e "   Port 3006 (First Hour): ${YELLOW}○ Not active (outside first hour)${NC}"
    else
        echo -e "   Port 3006 (First Hour): ${RED}✗ Not responding${NC}"
    fi
fi
echo ""

# Check for errors in recent logs
echo "6. Recent Errors (last 30 minutes):"
echo "   Hourly service errors:"
find /Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_hourlybo -name "*.log" -mmin -30 -exec grep -i "error\|exception\|failed" {} \; 2>/dev/null | tail -3 || echo "     No recent errors"

echo "   First hour service errors:"
find /Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_firsthour -name "*.log" -mmin -30 -exec grep -i "error\|exception\|failed" {} \; 2>/dev/null | tail -3 || echo "     No recent errors"
echo ""

# Quick recommendations
echo "7. Recommendations:"
if [ "$hourly_procs" -eq 0 ]; then
    echo -e "   ${YELLOW}⚠ Hourly breakout service not running. Run: ./start_hourly_breakout_alerts.sh${NC}"
fi

current_hour=$(date +%H)
current_min=$(date +%M)
if [ $current_hour -eq 9 ] && [ $current_min -ge 15 ] && [ $current_min -le 59 ]; then
    if [ "$first_hour_procs" -eq 0 ]; then
        echo -e "   ${YELLOW}⚠ First hour service should be running. Check plist configuration.${NC}"
    fi
fi

# Check if it's market hours
if [ $current_hour -ge 9 ] && [ $current_hour -lt 16 ]; then
    if [ "$hourly_alerts" -eq 0 ]; then
        echo -e "   ${YELLOW}ℹ No alerts in last hour. Check if market conditions are suitable.${NC}"
    fi
fi

echo ""
echo "=== End of Status Report ==="