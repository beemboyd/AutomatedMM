#!/bin/bash

# Hourly Candle Watchdog Stop Script
# This script stops the hourly candle watchdog

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/hourly_watchdog.pid"

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

# Function to check if watchdog is running
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

# Function to show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -f, --force    Force kill the process if graceful shutdown fails"
    echo "  -h, --help     Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0           # Graceful shutdown"
    echo "  $0 --force   # Force kill if needed"
}

# Parse command line arguments
FORCE_KILL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--force)
            FORCE_KILL=true
            shift
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
            print_error "Unexpected argument: $1"
            show_usage
            exit 1
            ;;
    esac
done

print_status "Stopping Hourly Candle Watchdog..."

# Check if running
if ! check_running; then
    print_warning "Hourly Candle Watchdog is not running"
    # Clean up any stale PID file
    rm -f "$PID_FILE"
    exit 0
fi

PID=$(cat "$PID_FILE")
print_status "Found watchdog process (PID: $PID)"

# Try graceful shutdown first
print_status "Sending SIGTERM for graceful shutdown..."
kill -TERM $PID 2>/dev/null

# Wait for graceful shutdown
WAIT_TIME=0
MAX_WAIT=15  # Wait up to 15 seconds for graceful shutdown

while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    if ! ps -p $PID > /dev/null 2>&1; then
        print_success "Hourly Candle Watchdog stopped gracefully"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 1
    WAIT_TIME=$((WAIT_TIME + 1))
    echo -n "."
done

echo ""  # New line after dots

# If graceful shutdown failed
if ps -p $PID > /dev/null 2>&1; then
    if [ "$FORCE_KILL" = true ]; then
        print_warning "Graceful shutdown failed, force killing process..."
        kill -9 $PID 2>/dev/null
        sleep 2
        
        if ! ps -p $PID > /dev/null 2>&1; then
            print_success "Hourly Candle Watchdog force killed successfully"
            rm -f "$PID_FILE"
            exit 0
        else
            print_error "Failed to kill watchdog process (PID: $PID)"
            exit 1
        fi
    else
        print_error "Graceful shutdown failed. Process is still running (PID: $PID)"
        print_status "You can try force killing with: $0 --force"
        print_status "Or manually kill with: kill -9 $PID"
        exit 1
    fi
fi

# Clean up PID file
rm -f "$PID_FILE"
print_success "Hourly Candle Watchdog stopped successfully"