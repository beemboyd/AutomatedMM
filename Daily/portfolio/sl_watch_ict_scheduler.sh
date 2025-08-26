#!/bin/bash
# ICT Stop Loss Watch Scheduler
# Runs ICT analysis on CNC positions at regular intervals

cd /Users/maverick/PycharmProjects/India-TS/Daily

echo "================================"
echo "ICT Stop Loss Analysis"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================"

# Run the ICT analysis
python3 portfolio/SL_Watch_ICT.py --user Sai

# Check if it completed successfully
if [ $? -eq 0 ]; then
    echo "✓ ICT analysis completed successfully"
else
    echo "✗ ICT analysis failed"
    exit 1
fi

echo "================================"
echo "Analysis complete"
echo "================================"