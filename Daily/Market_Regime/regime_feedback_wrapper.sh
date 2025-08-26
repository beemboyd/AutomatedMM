#!/bin/bash
# Wrapper script for regime feedback collector
# Runs only during market hours (9:15 AM - 3:30 PM IST) on weekdays

# Get current day of week (1=Monday, 7=Sunday)
DAY_OF_WEEK=$(date +%u)

# Get current time in HHMM format
CURRENT_TIME=$(date +%H%M)

# Check if it's a weekday (Monday-Friday)
if [ $DAY_OF_WEEK -ge 1 ] && [ $DAY_OF_WEEK -le 5 ]; then
    # Check if within market hours (9:15 AM to 3:30 PM)
    if [ $CURRENT_TIME -ge 915 ] && [ $CURRENT_TIME -le 1530 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Regime Feedback Collector (Market Hours)"
        
        # Check if already running
        if pgrep -f "regime_feedback_collector.py" > /dev/null; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Feedback collector already running"
        else
            cd /Users/maverick/PycharmProjects/India-TS/Daily
            /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 Market_Regime/regime_feedback_collector.py
        fi
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Outside market hours ($CURRENT_TIME), skipping"
        
        # Kill any running instance after market hours
        if [ $CURRENT_TIME -gt 1530 ]; then
            pkill -f "regime_feedback_collector.py" 2>/dev/null
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Stopped feedback collector (market closed)"
        fi
    fi
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Weekend (Day $DAY_OF_WEEK), skipping"
fi