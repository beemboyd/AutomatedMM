#!/bin/bash

# ATR-Based Stop Loss Watchdog Log Checker
# Quick script to check watchdog logs

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/hourly_watchdog.pid"
LOG_DIR="$SCRIPT_DIR/logs"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [options] [user_name]"
    echo ""
    echo "Options:"
    echo "  -f, --follow      Follow log in real-time"
    echo "  -t, --tail N      Show last N lines (default: 50)"
    echo "  -e, --errors      Show only errors and warnings"
    echo "  -s, --status      Show process status"
    echo "  -p, --portfolio   Show portfolio summaries only"
    echo "  -o, --orders      Show order-related logs only"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 Sai                    # Show last 50 lines for user Sai"
    echo "  $0 -f Sai                # Follow Sai's logs in real-time"
    echo "  $0 -e Sai                # Show errors for user Sai"
    echo "  $0 -s                     # Show process status"
    echo "  $0 -t 100 Som             # Show last 100 lines for user Som"
}

# Default values
FOLLOW=false
TAIL_LINES=50
SHOW_ERRORS=false
SHOW_STATUS=false
SHOW_PORTFOLIO=false
SHOW_ORDERS=false
USER_NAME=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -t|--tail)
            TAIL_LINES="$2"
            shift 2
            ;;
        -e|--errors)
            SHOW_ERRORS=true
            shift
            ;;
        -s|--status)
            SHOW_STATUS=true
            shift
            ;;
        -p|--portfolio)
            SHOW_PORTFOLIO=true
            shift
            ;;
        -o|--orders)
            SHOW_ORDERS=true
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
            USER_NAME="$1"
            shift
            ;;
    esac
done

# Show process status
if [ "$SHOW_STATUS" = true ]; then
    print_status "Checking ATR-Based Stop Loss Watchdog status..."
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            print_success "Watchdog is running (PID: $PID)"
            
            # Show process details
            echo ""
            print_status "Process details:"
            ps -p $PID -o pid,ppid,cmd,etime,pcpu,pmem
            
            # Show log file info
            if [ -n "$USER_NAME" ]; then
                LOG_FILE="$LOG_DIR/$USER_NAME/SL_watchdog_$USER_NAME.log"
                if [ -f "$LOG_FILE" ]; then
                    echo ""
                    print_status "Log file: $LOG_FILE"
                    print_status "Log size: $(du -h "$LOG_FILE" | cut -f1)"
                    print_status "Last modified: $(stat -f "%Sm" "$LOG_FILE")"
                fi
            fi
        else
            print_warning "PID file exists but process is not running"
            print_status "Removing stale PID file..."
            rm -f "$PID_FILE"
        fi
    else
        print_warning "Watchdog is not running (no PID file found)"
    fi
    
    echo ""
    print_status "Available log directories:"
    if [ -d "$LOG_DIR" ]; then
        find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort
    else
        print_warning "No log directory found"
    fi
    
    exit 0
fi

# Auto-detect user if not specified
if [ -z "$USER_NAME" ]; then
    print_status "Auto-detecting user from available logs..."
    if [ -d "$LOG_DIR" ]; then
        USERS=($(find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort))
        if [ ${#USERS[@]} -eq 1 ]; then
            USER_NAME="${USERS[0]}"
            print_status "Using user: $USER_NAME"
        elif [ ${#USERS[@]} -gt 1 ]; then
            print_status "Multiple users found. Please specify one:"
            printf '%s\n' "${USERS[@]}"
            exit 1
        else
            print_error "No user log directories found"
            exit 1
        fi
    else
        print_error "Log directory not found: $LOG_DIR"
        exit 1
    fi
fi

# Set log file path
LOG_FILE="$LOG_DIR/$USER_NAME/SL_watchdog_$USER_NAME.log"

# Check if log file exists
if [ ! -f "$LOG_FILE" ]; then
    print_error "Log file not found: $LOG_FILE"
    print_status "Available users:"
    if [ -d "$LOG_DIR" ]; then
        find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort
    fi
    exit 1
fi

print_status "Checking logs for user: $USER_NAME"
print_status "Log file: $LOG_FILE"

# Show different types of logs based on options
if [ "$SHOW_ERRORS" = true ]; then
    print_status "Showing errors and warnings:"
    grep -i -E "(error|warning)" "$LOG_FILE" | tail -$TAIL_LINES
elif [ "$SHOW_PORTFOLIO" = true ]; then
    print_status "Showing portfolio summaries:"
    if [ "$FOLLOW" = true ]; then
        tail -f "$LOG_FILE" | grep "Portfolio Summary\|P/L:\|Total Portfolio"
    else
        grep "Portfolio Summary\|P/L:\|Total Portfolio" "$LOG_FILE" | tail -$TAIL_LINES
    fi
elif [ "$SHOW_ORDERS" = true ]; then
    print_status "Showing order-related logs:"
    if [ "$FOLLOW" = true ]; then
        tail -f "$LOG_FILE" | grep -E "(Queued|Order placed|fell below hourly|Updated hourly)"
    else
        grep -E "(Queued|Order placed|fell below hourly|Updated hourly)" "$LOG_FILE" | tail -$TAIL_LINES
    fi
elif [ "$FOLLOW" = true ]; then
    print_status "Following logs in real-time (Ctrl+C to stop):"
    tail -f "$LOG_FILE"
else
    print_status "Showing last $TAIL_LINES lines:"
    tail -$TAIL_LINES "$LOG_FILE"
fi