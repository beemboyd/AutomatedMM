#!/bin/bash

# Start VSR Paper Trading System

echo "🚀 Starting VSR Paper Trading System..."

# Set up paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create necessary directories
mkdir -p data logs config

# Check if config exists
if [ ! -f "config/paper_trading_config.json" ]; then
    echo "Creating default configuration..."
    python3 vsr_paper_trader.py --init-config
fi

# Start the dashboard in background
echo "Starting dashboard on port 5005..."
python3 vsr_paper_dashboard.py &
DASHBOARD_PID=$!
echo "Dashboard PID: $DASHBOARD_PID"

# Give dashboard time to start
sleep 2

# Start the paper trader
echo "Starting VSR Paper Trader..."
python3 vsr_paper_trader.py

# When trader exits, kill dashboard
echo "Shutting down dashboard..."
kill $DASHBOARD_PID

echo "✅ VSR Paper Trading System stopped"