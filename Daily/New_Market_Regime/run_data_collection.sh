#!/bin/bash

# Data Collection Script for New Market Regime ML System
# Runs every 5 minutes during market hours to collect data

# Set up environment
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH"
export PYTHONPATH="/Users/maverick/PycharmProjects/India-TS:$PYTHONPATH"
export TZ="Asia/Kolkata"

# Change to project directory
cd /Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime

# Log start time
echo "=================================================="
echo "Starting data collection at $(date '+%Y-%m-%d %H:%M:%S IST')"
echo "=================================================="

# Check if it's a trading day and within market hours
python3 -c "
from datetime import datetime
import sys
import pytz

ist = pytz.timezone('Asia/Kolkata')
now = datetime.now(ist)

# Check if weekend
if now.weekday() >= 5:
    print('Skipping: Weekend - Market closed')
    sys.exit(1)

# Check if market hours (9:15 AM - 3:30 PM IST)
market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

if not (market_open <= now <= market_close):
    print(f'Skipping: Outside market hours (Current: {now.strftime(\"%H:%M\")} IST)')
    sys.exit(1)

print(f'Market is open. Proceeding with data collection at {now.strftime(\"%H:%M:%S\")} IST')
sys.exit(0)
"

if [ $? -eq 0 ]; then
    # Run the data collection pipeline
    echo "Running data collection pipeline..."
    python3 src/pipeline/data_collection_pipeline.py --mode once
    
    if [ $? -eq 0 ]; then
        echo "✅ Data collection completed successfully"
    else
        echo "❌ Data collection failed with error code: $?"
    fi
else
    echo "⏸ Data collection skipped (market closed or weekend)"
fi

echo "=================================================="
echo ""