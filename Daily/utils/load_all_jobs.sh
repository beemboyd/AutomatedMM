#!/bin/bash

echo "=========================================="
echo "Loading all India-TS LaunchAgent jobs..."
echo "=========================================="

# List of all active plist files
PLIST_FILES=(
    "com.india-ts.brooks_reversal_4times.plist"
    "com.india-ts.brooks_reversal_simple.plist"
    "com.india-ts.consolidated_score.plist"
    "com.india-ts.daily_action_plan.plist"
    "com.india-ts.health_dashboard.plist"
    "com.india-ts.kc_lower_limit_trending.plist"
    "com.india-ts.kc_upper_limit_trending.plist"
    "com.india-ts.long_reversal_daily.plist"
    "com.india-ts.market_regime_analysis.plist"
    "com.india-ts.market_regime_dashboard.plist"
    "com.india-ts.short_reversal_daily.plist"
    "com.india-ts.sl_watchdog_stop.plist"
    "com.india-ts.strategyc_filter.plist"
    "com.india-ts.synch_zerodha_local.plist"
    "com.india-ts.weekly_backup.plist"
)

LAUNCHAGENTS_DIR="/Users/maverick/Library/LaunchAgents"
SUCCESS_COUNT=0
FAILED_COUNT=0

for plist in "${PLIST_FILES[@]}"; do
    plist_path="$LAUNCHAGENTS_DIR/$plist"
    if [ -f "$plist_path" ]; then
        echo -n "Loading $plist... "
        if launchctl load "$plist_path" 2>/dev/null; then
            echo "✅ Success"
            ((SUCCESS_COUNT++))
        else
            # Check if already loaded
            job_name="${plist%.plist}"
            if launchctl list | grep -q "$job_name"; then
                echo "⚠️  Already loaded"
                ((SUCCESS_COUNT++))
            else
                echo "❌ Failed"
                ((FAILED_COUNT++))
            fi
        fi
    else
        echo "❌ WARNING: $plist not found!"
        ((FAILED_COUNT++))
    fi
done

echo ""
echo "=========================================="
echo "Summary: $SUCCESS_COUNT loaded, $FAILED_COUNT failed"
echo "=========================================="
echo ""
echo "Current status of India-TS jobs:"
echo ""

# Show status with better formatting
launchctl list | grep india-ts | while read line; do
    pid=$(echo $line | awk '{print $1}')
    status=$(echo $line | awk '{print $2}')
    name=$(echo $line | awk '{print $3}')
    
    if [ "$pid" != "-" ]; then
        echo "✅ $name (PID: $pid, running)"
    elif [ "$status" = "0" ]; then
        echo "✅ $name (last exit: success)"
    elif [ "$status" != "-" ]; then
        echo "⚠️  $name (last exit: $status)"
    else
        echo "⏸️  $name (not yet run)"
    fi
done

echo ""
echo "To check logs for errors, run:"
echo "tail -50 /Users/maverick/PycharmProjects/India-TS/Daily/logs/*error*.log"