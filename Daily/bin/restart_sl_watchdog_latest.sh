#!/bin/bash

# Script to restart SL_watchdog with the latest orders file
# This ensures we're always using the most recent orders, not old consolidated files

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAILY_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}=== Restarting SL Watchdog with Latest Orders ===${NC}"

# 1. Kill all existing SL_watchdog processes
echo -e "${YELLOW}Stopping all SL_watchdog processes...${NC}"
pkill -f "SL_watchdog.py.*India-TS"
sleep 2

# 2. Find the latest orders file (excluding consolidated files)
LATEST_ORDER_FILE=$(find "$DAILY_DIR/Current_Orders/Sai" -name "orders_Sai_*.json" ! -name "*consolidated*" -type f | sort -r | head -1)

if [ -z "$LATEST_ORDER_FILE" ]; then
    echo -e "${RED}No orders file found!${NC}"
    exit 1
fi

echo -e "${GREEN}Found latest orders file: $(basename "$LATEST_ORDER_FILE")${NC}"

# 3. Start SL_watchdog with the latest file
echo -e "${YELLOW}Starting SL_watchdog with latest orders...${NC}"
cd "$DAILY_DIR"
nohup python3 portfolio/SL_watchdog.py "$LATEST_ORDER_FILE" --poll-interval 45 > "logs/Sai/sl_watchdog_restart.log" 2>&1 &

NEW_PID=$!
echo -e "${GREEN}SL_watchdog started with PID: $NEW_PID${NC}"

# 4. Wait and verify
sleep 3
if ps -p $NEW_PID > /dev/null 2>&1; then
    echo -e "${GREEN}✓ SL_watchdog is running successfully${NC}"
    echo -e "${BLUE}Monitoring positions from: $(basename "$LATEST_ORDER_FILE")${NC}"
    
    # Show what's being monitored
    echo -e "\n${YELLOW}Fetching tracked positions...${NC}"
    sleep 2
    tail -20 "logs/Sai/sl_watchdog_restart.log" | grep -E "Tracking|Loading|positions" || true
else
    echo -e "${RED}✗ SL_watchdog failed to start${NC}"
    echo -e "${RED}Check logs at: logs/Sai/sl_watchdog_restart.log${NC}"
    exit 1
fi

echo -e "\n${BLUE}=== Done ===${NC}"
echo -e "To check status: ${YELLOW}ps aux | grep SL_watchdog${NC}"
echo -e "To view logs: ${YELLOW}tail -f logs/Sai/SL_watchdog_*.log${NC}"