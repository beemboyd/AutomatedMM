#!/bin/bash

# Run Market Regime Analyzer every 5 minutes during market hours
# This script checks if it's market hours before running

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Get current time
CURRENT_HOUR=$(date +%H)
CURRENT_DAY=$(date +%u)  # 1=Monday, 7=Sunday

# Check if it's a weekday (Monday-Friday)
if [ $CURRENT_DAY -ge 6 ]; then
    echo "Weekend - skipping regime analysis"
    exit 0
fi

# Check if it's market hours (9:00 AM - 3:30 PM)
if [ $CURRENT_HOUR -lt 9 ] || [ $CURRENT_HOUR -ge 16 ]; then
    echo "Outside market hours - skipping regime analysis"
    exit 0
fi

# Special case for 3:30 PM cutoff
if [ $CURRENT_HOUR -eq 15 ]; then
    CURRENT_MIN=$(date +%M)
    if [ $CURRENT_MIN -gt 30 ]; then
        echo "After 3:30 PM - skipping regime analysis"
        exit 0
    fi
fi

echo "Running Market Regime Analyzer at $(date)"
python3 market_regime_analyzer.py --force