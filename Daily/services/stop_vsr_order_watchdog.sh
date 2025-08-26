#!/bin/bash

# VSR Order Watchdog Stop Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_ROOT/trading/vsr_order_watchdog.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  Stopping VSR Order Watchdog${NC}"
echo -e "${YELLOW}========================================${NC}"

if [ ! -f "$PID_FILE" ]; then
    echo -e "${YELLOW}⚠️  VSR Order Watchdog is not running (no PID file found)${NC}"
    
    # Check if process is running without PID file
    PIDS=$(pgrep -f "order_watchdog_vsr.py")
    if [ ! -z "$PIDS" ]; then
        echo -e "${YELLOW}Found orphaned process(es): $PIDS${NC}"
        echo -e "${YELLOW}Killing orphaned process(es)...${NC}"
        kill $PIDS
        sleep 2
        echo -e "${GREEN}✅ Orphaned process(es) stopped${NC}"
    fi
    exit 0
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo -e "${YELLOW}Stopping VSR Order Watchdog (PID: $PID)...${NC}"
    kill "$PID"
    
    # Wait for process to stop
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    
    # Force kill if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}Process didn't stop gracefully, force killing...${NC}"
        kill -9 "$PID"
        sleep 1
    fi
    
    echo -e "${GREEN}✅ VSR Order Watchdog stopped${NC}"
else
    echo -e "${YELLOW}Process not found (PID: $PID), removing stale PID file${NC}"
fi

# Remove PID file
rm -f "$PID_FILE"

echo -e "${GREEN}✅ Cleanup complete${NC}"