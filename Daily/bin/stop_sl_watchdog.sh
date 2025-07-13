#!/bin/bash

# Stop Standard SL Watchdog Script
# This script stops the standard SL watchdog gracefully

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Set paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DAILY_DIR="$(dirname "$SCRIPT_DIR")"
PID_DIR="$DAILY_DIR/pids"

# PID file
SL_WATCHDOG_PID="$PID_DIR/sl_watchdog.pid"

# Function to check if process is running
is_process_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0  # Process is running
        else
            # PID file exists but process is not running
            rm -f "$pid_file"
            return 1
        fi
    fi
    return 1  # PID file doesn't exist
}

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}   Standard SL Watchdog Stopper${NC}"
echo -e "${BLUE}======================================${NC}"

# Check if standard SL watchdog is running
if ! is_process_running "$SL_WATCHDOG_PID"; then
    echo -e "\n${YELLOW}Standard SL Watchdog is not running.${NC}"
    exit 0
fi

# Get the PID
PID=$(cat "$SL_WATCHDOG_PID")

# Confirm before stopping
echo -e "\n${YELLOW}Are you sure you want to stop the Standard SL Watchdog?${NC}"
echo -e "PID: $PID"
read -p "Type 'yes' to confirm: " response

if [ "$response" != "yes" ]; then
    echo -e "${YELLOW}Operation cancelled.${NC}"
    exit 0
fi

# Send SIGTERM signal (graceful shutdown)
echo -e "\n${YELLOW}Sending shutdown signal...${NC}"
kill "$PID" 2>/dev/null

# Wait for process to stop (up to 10 seconds)
COUNTER=0
while [ $COUNTER -lt 10 ]; do
    if ! ps -p "$PID" > /dev/null 2>&1; then
        break
    fi
    echo -n "."
    sleep 1
    COUNTER=$((COUNTER + 1))
done
echo ""

# Check if process stopped
if ps -p "$PID" > /dev/null 2>&1; then
    echo -e "${YELLOW}Process did not stop gracefully. Force killing...${NC}"
    kill -9 "$PID" 2>/dev/null
    sleep 1
fi

# Remove PID file
rm -f "$SL_WATCHDOG_PID"

# Final check
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo -e "\n${GREEN}✓ Standard SL Watchdog stopped successfully!${NC}"
else
    echo -e "\n${RED}✗ Failed to stop Standard SL Watchdog${NC}"
    echo -e "You may need to manually kill the process: kill -9 $PID"
    exit 1
fi

echo -e "\n${BLUE}======================================${NC}"