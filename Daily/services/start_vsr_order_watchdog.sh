#!/bin/bash

# VSR Order Watchdog Startup Script
# Monitors VSR tickers for breakout/breakdown signals and places orders

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_PATH="/usr/bin/env python3"
WATCHDOG_SCRIPT="$PROJECT_ROOT/trading/order_watchdog_vsr.py"
PID_FILE="$PROJECT_ROOT/trading/vsr_order_watchdog.pid"
LOG_DIR="$PROJECT_ROOT/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  VSR Order Watchdog Service${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  VSR Order Watchdog is already running (PID: $OLD_PID)${NC}"
        echo -e "${YELLOW}   Stop it first with: ./stop_vsr_order_watchdog.sh${NC}"
        exit 1
    else
        echo -e "${YELLOW}Removing stale PID file${NC}"
        rm "$PID_FILE"
    fi
fi

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Start the watchdog
echo -e "${GREEN}Starting VSR Order Watchdog...${NC}"
echo -e "  Strategy: Buy on 4-candle breakout, Sell on 2-candle breakdown"
echo -e "  Min Score: 60, Min Momentum: 2%"
echo -e "  Position Size: 1% per position, Max: 5 positions"
echo -e "  Poll Interval: 60 seconds"

# Run in background with nohup
nohup "$PYTHON_PATH" "$WATCHDOG_SCRIPT" --user Sai > "$LOG_DIR/vsr_order_watchdog_console.log" 2>&1 &
PID=$!

# Save PID
echo $PID > "$PID_FILE"

# Wait a moment to check if it started successfully
sleep 2

if ps -p "$PID" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ VSR Order Watchdog started successfully (PID: $PID)${NC}"
    echo -e "${GREEN}   Logs: $LOG_DIR/Sai/order_watchdog_vsr_$(date +%Y%m%d).log${NC}"
    echo -e "${GREEN}   Console: $LOG_DIR/vsr_order_watchdog_console.log${NC}"
    echo -e "${GREEN}   Stop with: ./stop_vsr_order_watchdog.sh${NC}"
else
    echo -e "${RED}❌ Failed to start VSR Order Watchdog${NC}"
    rm "$PID_FILE"
    echo -e "${RED}   Check console log for errors: $LOG_DIR/vsr_order_watchdog_console.log${NC}"
    exit 1
fi