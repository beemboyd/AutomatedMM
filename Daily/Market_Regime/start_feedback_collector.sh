#!/bin/bash
# Start the Regime Feedback Collector Service

cd /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime

echo "Starting Regime Feedback Collector Service..."
echo "This service will:"
echo "  - Collect feedback on predictions every 5 minutes"
echo "  - Calculate actual regimes 45 minutes after predictions"
echo "  - Generate daily reports at 3:35 PM"
echo ""

# Create log directory if it doesn't exist
mkdir -p /Users/maverick/PycharmProjects/India-TS/Daily/logs

# Kill any existing feedback collector process
pkill -f "regime_feedback_collector.py" 2>/dev/null

# Start the service in background
nohup python3 regime_feedback_collector.py > /Users/maverick/PycharmProjects/India-TS/Daily/logs/regime_feedback_collector.log 2>&1 &

echo "Feedback Collector started with PID: $!"
echo "Logs: /Users/maverick/PycharmProjects/India-TS/Daily/logs/regime_feedback_collector.log"
echo ""
echo "To stop the service, run: pkill -f regime_feedback_collector.py"