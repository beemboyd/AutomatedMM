#!/bin/bash

# Start Standard SL Watchdog Script
# This script starts the standard ATR-based SL watchdog

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Set paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DAILY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$DAILY_DIR")"
PORTFOLIO_DIR="$DAILY_DIR/portfolio"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
PID_DIR="$DAILY_DIR/pids"

# Create PID directory if it doesn't exist
mkdir -p "$PID_DIR"

# PID files
SL_WATCHDOG_PID="$PID_DIR/sl_watchdog.pid"
SL_WATCHDOG_REGIME_PID="$PID_DIR/sl_watchdog_regime.pid"

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
echo -e "${BLUE}   Standard SL Watchdog Starter${NC}"
echo -e "${BLUE}======================================${NC}"

# Check if regime SL watchdog is running
if is_process_running "$SL_WATCHDOG_REGIME_PID"; then
    echo -e "\n${RED}⚠️  WARNING: Regime SL Watchdog is already running!${NC}"
    echo -e "\n${YELLOW}Only one SL watchdog should run at a time.${NC}"
    echo -e "Do you want to stop the regime watchdog and start the standard version?"
    read -p "Type 'yes' to proceed: " response
    
    if [ "$response" != "yes" ]; then
        echo -e "${YELLOW}Operation cancelled.${NC}"
        exit 1
    fi
    
    # Stop the regime watchdog
    "$SCRIPT_DIR/stop_sl_watchdog_regime.sh"
fi

# Check if standard SL watchdog is already running
if is_process_running "$SL_WATCHDOG_PID"; then
    echo -e "\n${YELLOW}Standard SL Watchdog is already running!${NC}"
    echo -e "\nDo you want to restart it?"
    read -p "Type 'yes' to restart: " response
    
    if [ "$response" != "yes" ]; then
        echo -e "${GREEN}Keeping existing process running.${NC}"
        exit 0
    fi
    
    # Stop the existing process
    "$SCRIPT_DIR/stop_sl_watchdog.sh"
fi

# Get user selection
echo -e "\n${BLUE}Select user for SL Watchdog:${NC}"
echo "1. Sai"
echo "2. Som"
echo "3. Su"
echo "4. Tinks"
echo "5. Mom"
echo "6. Prash"
echo "7. Ravi"

read -p "Enter user number (1-7): " user_choice

case $user_choice in
    1) USER_NAME="Sai" ;;
    2) USER_NAME="Som" ;;
    3) USER_NAME="Su" ;;
    4) USER_NAME="Tinks" ;;
    5) USER_NAME="Mom" ;;
    6) USER_NAME="Prash" ;;
    7) USER_NAME="Ravi" ;;
    *) echo -e "${RED}Invalid selection.${NC}"; exit 1 ;;
esac

# Ask about orders file
echo -e "\n${BLUE}Do you want to specify an orders file?${NC}"
echo "1. No - Monitor all CNC positions from Zerodha"
echo "2. Yes - Specify an orders file"

read -p "Enter choice (1-2): " orders_choice

ORDERS_FILE=""
if [ "$orders_choice" == "2" ]; then
    read -p "Enter orders file path: " ORDERS_FILE
    if [ ! -f "$ORDERS_FILE" ]; then
        echo -e "${RED}Error: Orders file not found: $ORDERS_FILE${NC}"
        exit 1
    fi
fi

# Create log directory
LOG_DIR="$DAILY_DIR/logs/$USER_NAME"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/SL_watchdog_${USER_NAME}_$(date +%Y%m%d_%H%M%S).log"

# Start the standard SL watchdog
echo -e "\n${GREEN}Starting Standard SL Watchdog for user: $USER_NAME${NC}"
echo -e "Log file: $LOG_FILE"

# Change to portfolio directory
cd "$PORTFOLIO_DIR"

# Set environment variable for user
export TRADING_USER="$USER_NAME"

# Start the process in background
if [ -z "$ORDERS_FILE" ]; then
    nohup "$VENV_PYTHON" SL_watchdog.py > "$LOG_FILE" 2>&1 &
else
    nohup "$VENV_PYTHON" SL_watchdog.py "$ORDERS_FILE" > "$LOG_FILE" 2>&1 &
fi

# Get the PID
PID=$!

# Save PID to file
echo $PID > "$SL_WATCHDOG_PID"

# Wait a moment to check if process started successfully
sleep 3

# Check if process is still running
if ps -p $PID > /dev/null; then
    echo -e "\n${GREEN}✓ Standard SL Watchdog started successfully!${NC}"
    echo -e "PID: $PID"
    echo -e "User: $USER_NAME"
    echo -e "\n${BLUE}To view logs:${NC}"
    echo -e "tail -f $LOG_FILE"
    echo -e "\n${BLUE}To stop:${NC}"
    echo -e "$DAILY_DIR/bin/stop_sl_watchdog.sh"
else
    echo -e "\n${RED}✗ Failed to start Standard SL Watchdog${NC}"
    echo -e "Check the log file for errors:"
    echo -e "tail -50 $LOG_FILE"
    rm -f "$SL_WATCHDOG_PID"
    exit 1
fi

echo -e "\n${BLUE}======================================${NC}"