#!/bin/bash
# Check status of ICT Stop Loss Watchdog Service

echo "========================================="
echo "ICT Stop Loss Watchdog Service Status"
echo "========================================="

# Check if service is loaded
if launchctl list | grep -q "com.india-ts.ict-sl-watchdog"; then
    echo "✓ Service is ACTIVE"
    
    # Get PID if running
    PID=$(launchctl list | grep "com.india-ts.ict-sl-watchdog" | awk '{print $1}')
    if [ "$PID" != "-" ]; then
        echo "  Process ID: $PID"
    else
        echo "  Status: Scheduled (waiting for next run)"
    fi
else
    echo "✗ Service is NOT RUNNING"
fi

echo ""
echo "Schedule: Every 15 minutes from 9:15 AM to 3:30 PM (Mon-Fri)"

# Check last run status
STATUS_FILE="/Users/maverick/PycharmProjects/India-TS/Daily/portfolio/ict_analysis/watchdog_status.json"
if [ -f "$STATUS_FILE" ]; then
    echo ""
    echo "Last Run Information:"
    python3 -c "
import json
with open('$STATUS_FILE', 'r') as f:
    data = json.load(f)
    print(f\"  Time: {data['last_run']}\")
    print(f\"  Status: {data['status']}\")
    print(f\"  Log: {data['log_file']}\")
"
fi

# Check for recent analysis files
echo ""
echo "Recent Analysis Files:"
ls -lt /Users/maverick/PycharmProjects/India-TS/Daily/portfolio/ict_analysis/ict_sl_analysis_*.json 2>/dev/null | head -5 | awk '{print "  " $9}'

# Check today's log
LOG_FILE="/Users/maverick/PycharmProjects/India-TS/Daily/logs/ict_watchdog/ict_watchdog_$(date '+%Y%m%d').log"
if [ -f "$LOG_FILE" ]; then
    echo ""
    echo "Today's Activity:"
    echo "  Total runs: $(grep -c "ICT Stop Loss Watchdog" "$LOG_FILE")"
    echo "  Successful: $(grep -c "completed successfully" "$LOG_FILE")"
    echo "  Failed: $(grep -c "failed" "$LOG_FILE")"
    
    # Show last critical alert if any
    LAST_ALERT=$(grep "CRITICAL ALERTS:" "$LOG_FILE" | tail -1)
    if [ ! -z "$LAST_ALERT" ]; then
        echo ""
        echo "Last Critical Alert:"
        grep -A 5 "CRITICAL ALERTS:" "$LOG_FILE" | tail -6
    fi
fi

echo ""
echo "========================================="