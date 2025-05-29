#!/bin/bash

# ATR-Based Stop Loss Watchdog Startup Script
# This script starts the ATR-based stop loss watchdog for monitoring CNC positions

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WATCHDOG_SCRIPT="$SCRIPT_DIR/scripts/SL_watchdog.py"
PID_FILE="$SCRIPT_DIR/hourly_watchdog.pid"
LOG_DIR="$SCRIPT_DIR/logs"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

# Function to check if watchdog is already running
check_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            return 0  # Running
        else
            # PID file exists but process is not running, remove stale PID file
            rm -f "$PID_FILE"
            return 1  # Not running
        fi
    fi
    return 1  # Not running
}

# Function to find the most recent orders file
find_recent_orders_file() {
    local user_name="$1"
    local orders_dir="$SCRIPT_DIR/Current_Orders"
    
    if [ -n "$user_name" ]; then
        # Look for specific user's orders
        find "$orders_dir/$user_name" -name "orders_*.json" -type f 2>/dev/null | sort -r | head -1
    else
        # Look for any user's orders
        find "$orders_dir" -name "orders_*.json" -type f 2>/dev/null | sort -r | head -1
    fi
}

# Function to list available users
list_users() {
    local orders_dir="$SCRIPT_DIR/Current_Orders"
    if [ -d "$orders_dir" ]; then
        find "$orders_dir" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [options] [orders_file]"
    echo ""
    echo "Options:"
    echo "  -u, --user USER     Specify user name to find their latest orders file"
    echo "  -l, --list-users    List available users"
    echo "  -v, --verbose       Enable verbose logging"
    echo "  -i, --interval SEC  Set price polling interval in seconds (default: 5.0)"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                          # Auto-find latest orders file"
    echo "  $0 -u Sai                                  # Use latest orders file for user 'Sai'"
    echo "  $0 Current_Orders/Sai/orders_Sai_*.json   # Use specific orders file"
    echo "  $0 -v -i 3.0 -u Som                       # Verbose mode, 3-second polling, user 'Som'"
}

# Parse command line arguments
ORDERS_FILE=""
USER_NAME=""
VERBOSE=""
POLL_INTERVAL="5.0"

while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--user)
            USER_NAME="$2"
            shift 2
            ;;
        -l|--list-users)
            print_status "Available users:"
            list_users
            exit 0
            ;;
        -v|--verbose)
            VERBOSE="--verbose"
            shift
            ;;
        -i|--interval)
            POLL_INTERVAL="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        -*)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            ORDERS_FILE="$1"
            shift
            ;;
    esac
done

print_status "Starting ATR-Based Stop Loss Watchdog..."

# Check if already running
if check_running; then
    PID=$(cat "$PID_FILE")
    print_warning "ATR-Based Stop Loss Watchdog is already running (PID: $PID)"
    exit 1
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Find orders file if not specified
if [ -z "$ORDERS_FILE" ]; then
    ORDERS_FILE=$(find_recent_orders_file "$USER_NAME")
    if [ -z "$ORDERS_FILE" ]; then
        if [ -n "$USER_NAME" ]; then
            print_error "No orders file found for user: $USER_NAME"
        else
            print_error "No orders file found. Available users:"
            list_users
        fi
        exit 1
    fi
    print_status "Auto-selected orders file: $(basename "$ORDERS_FILE")"
fi

# Check if orders file exists
if [ ! -f "$ORDERS_FILE" ]; then
    print_error "Orders file not found: $ORDERS_FILE"
    exit 1
fi

# Check if Python script exists
if [ ! -f "$WATCHDOG_SCRIPT" ]; then
    print_error "Watchdog script not found: $WATCHDOG_SCRIPT"
    exit 1
fi

# Extract user name from orders file for logging
if [ -z "$USER_NAME" ]; then
    USER_NAME=$(basename "$(dirname "$ORDERS_FILE")")
fi

print_status "Orders file: $ORDERS_FILE"
print_status "User: $USER_NAME"
print_status "Polling interval: ${POLL_INTERVAL}s"

# Build command
CMD="python3 '$WATCHDOG_SCRIPT' '$ORDERS_FILE' --poll-interval $POLL_INTERVAL"
if [ -n "$VERBOSE" ]; then
    CMD="$CMD $VERBOSE"
fi

print_status "Starting watchdog in background..."

# Start the watchdog in background and capture PID
nohup bash -c "$CMD" > "$LOG_DIR/hourly_watchdog_startup.log" 2>&1 &
WATCHDOG_PID=$!

# Save PID to file
echo $WATCHDOG_PID > "$PID_FILE"

# Wait a moment to see if the process starts successfully
sleep 3

# Check if process is still running
if ps -p $WATCHDOG_PID > /dev/null 2>&1; then
    print_success "ATR-Based Stop Loss Watchdog started successfully (PID: $WATCHDOG_PID)"
    print_status "Log files will be in: $LOG_DIR/$USER_NAME/"
    print_status "To stop the watchdog, run: $SCRIPT_DIR/stop_hourly_watchdog.sh"
    print_status "To check status, run: ps -p $WATCHDOG_PID"
else
    print_error "Failed to start ATR-Based Stop Loss Watchdog"
    print_error "Check the log file: $LOG_DIR/hourly_watchdog_startup.log"
    rm -f "$PID_FILE"
    exit 1
fi