#!/bin/bash

# ICT Analysis Scheduler - Runs every 15 minutes during market hours
# This ensures the dashboard always has fresh stop loss recommendations

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"

echo "Starting ICT Analysis Scheduler..."
echo "Will run analysis every 15 minutes during market hours (9:15 AM - 3:30 PM)"

while true; do
    # Get current time
    CURRENT_HOUR=$(date +%H)
    CURRENT_MIN=$(date +%M)
    CURRENT_TIME=$((CURRENT_HOUR * 100 + CURRENT_MIN))
    
    # Check if within market hours (9:15 AM to 3:30 PM)
    if [ $CURRENT_TIME -ge 915 ] && [ $CURRENT_TIME -le 1530 ]; then
        echo ""
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Running ICT Analysis..."
        
        # Run the ICT analysis
        cd "$SCRIPT_DIR"
        $PYTHON_PATH SL_Watch_ICT.py --user Sai > /dev/null 2>&1
        
        if [ $? -eq 0 ]; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') - ICT Analysis completed successfully"
        else
            echo "$(date '+%Y-%m-%d %H:%M:%S') - ICT Analysis failed"
        fi
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Outside market hours, skipping analysis"
    fi
    
    # Wait 15 minutes before next run
    sleep 900
done