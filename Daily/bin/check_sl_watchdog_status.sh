#!/bin/bash

# Check SL Watchdog Status Script
# This script checks the status of all SL watchdog processes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Set paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DAILY_DIR="$(dirname "$SCRIPT_DIR")"
PID_DIR="$DAILY_DIR/pids"

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
        fi
    fi
    return 1  # Process not running or PID file doesn't exist
}

# Function to get detailed process info
get_detailed_process_info() {
    local pid_file=$1
    local process_name=$2
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "\n${GREEN}✓ $process_name is RUNNING${NC}"
            echo -e "${CYAN}PID:${NC} $pid"
            
            # Get process details
            local cmd=$(ps -p "$pid" -o args= 2>/dev/null)
            local start_time=$(ps -p "$pid" -o lstart= 2>/dev/null)
            local runtime=$(ps -p "$pid" -o etime= 2>/dev/null)
            local cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null)
            local mem=$(ps -p "$pid" -o %mem= 2>/dev/null)
            
            echo -e "${CYAN}Command:${NC} $cmd"
            echo -e "${CYAN}Started:${NC} $start_time"
            echo -e "${CYAN}Runtime:${NC} $runtime"
            echo -e "${CYAN}CPU Usage:${NC} $cpu%"
            echo -e "${CYAN}Memory Usage:${NC} $mem%"
            
            # Try to extract user from process or log file
            if [[ "$cmd" == *"SL_watchdog"* ]]; then
                # Look for most recent log file
                local log_pattern="$DAILY_DIR/logs/*/SL_watchdog*_*.log"
                local latest_log=$(ls -t $log_pattern 2>/dev/null | head -1)
                if [ -n "$latest_log" ]; then
                    local user_from_path=$(echo "$latest_log" | sed -n 's/.*\/logs\/\([^\/]*\)\/.*/\1/p')
                    if [ -n "$user_from_path" ]; then
                        echo -e "${CYAN}User:${NC} $user_from_path"
                    fi
                    echo -e "${CYAN}Log file:${NC} $latest_log"
                fi
            fi
        else
            echo -e "\n${RED}✗ $process_name is NOT RUNNING${NC}"
            echo -e "${YELLOW}(PID file exists but process is dead)${NC}"
            echo -e "${CYAN}Dead PID:${NC} $pid"
        fi
    else
        echo -e "\n${YELLOW}○ $process_name is NOT RUNNING${NC}"
        echo -e "${CYAN}(No PID file found)${NC}"
    fi
}

# Function to check for orphaned Python processes
check_orphaned_processes() {
    echo -e "\n${BLUE}Checking for orphaned SL watchdog processes...${NC}"
    
    # Look for Python processes running SL_watchdog scripts
    local orphaned=$(ps aux | grep -E "[p]ython.*SL_watchdog" | grep -v grep)
    
    if [ -n "$orphaned" ]; then
        echo -e "${YELLOW}⚠️  Found potential orphaned processes:${NC}"
        echo "$orphaned" | while read line; do
            local pid=$(echo "$line" | awk '{print $2}')
            local cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
            echo -e "${RED}PID $pid:${NC} $cmd"
        done
        echo -e "${YELLOW}These processes are running but not tracked by PID files.${NC}"
        echo -e "To kill them, use: ${CYAN}kill <PID>${NC}"
    else
        echo -e "${GREEN}✓ No orphaned processes found${NC}"
    fi
}

# Main execution
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}    SL Watchdog Status Check${NC}"
echo -e "${BLUE}======================================${NC}"

# Check standard SL watchdog
get_detailed_process_info "$SL_WATCHDOG_PID" "Standard SL Watchdog"

# Check regime SL watchdog
get_detailed_process_info "$SL_WATCHDOG_REGIME_PID" "Regime SL Watchdog"

# Check for orphaned processes
check_orphaned_processes

# Summary and recommendations
echo -e "\n${BLUE}======================================${NC}"
echo -e "${BLUE}Summary:${NC}"

standard_running=false
regime_running=false

is_process_running "$SL_WATCHDOG_PID" && standard_running=true
is_process_running "$SL_WATCHDOG_REGIME_PID" && regime_running=true

if $standard_running && $regime_running; then
    echo -e "${RED}⚠️  WARNING: Both SL watchdogs are running!${NC}"
    echo -e "${YELLOW}This is not recommended. Please stop one of them.${NC}"
    echo -e "To stop standard: ${CYAN}$DAILY_DIR/bin/stop_sl_watchdog.sh${NC}"
    echo -e "To stop regime: ${CYAN}$DAILY_DIR/bin/stop_sl_watchdog_regime.sh${NC}"
elif $standard_running; then
    echo -e "${GREEN}Standard SL Watchdog is active${NC}"
    echo -e "To switch to regime version: ${CYAN}$DAILY_DIR/bin/start_sl_watchdog_regime.sh${NC}"
elif $regime_running; then
    echo -e "${GREEN}Regime SL Watchdog is active${NC}"
    echo -e "Using intelligent market regime-based stop losses"
else
    echo -e "${YELLOW}No SL watchdog is currently running${NC}"
    echo -e "To start regime version: ${CYAN}$DAILY_DIR/bin/start_sl_watchdog_regime.sh${NC}"
    echo -e "To start standard version: ${CYAN}$DAILY_DIR/bin/start_sl_watchdog.sh${NC}"
fi

echo -e "${BLUE}======================================${NC}"