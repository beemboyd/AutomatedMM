#!/bin/bash

# Start Market Breadth Dashboard
# This script starts the enhanced market breadth dashboard on port 5001

echo "Starting Market Breadth Dashboard on port 5001..."

# Change to the Market_Regime directory
cd /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime

# Start the dashboard
python3 market_breadth_dashboard.py &

# Get the process ID
PID=$!

# Save the PID to a file for easy stopping later
echo $PID > /Users/maverick/PycharmProjects/India-TS/Daily/pids/market_breadth_dashboard.pid

echo "Market Breadth Dashboard started with PID: $PID"
echo "Access the dashboard at: http://localhost:5001"
echo ""
echo "To stop the dashboard, run: kill $PID"
echo "Or use the stop script: ./stop_market_breadth_dashboard.sh"