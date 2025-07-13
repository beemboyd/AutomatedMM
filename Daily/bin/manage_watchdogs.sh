#!/bin/bash

# Multi-User ATR-Based Stop Loss Watchdog Manager
# Automatically detects users with active orders and manages watchdog processes for all of them

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAILY_DIR="$(dirname "$SCRIPT_DIR")"
WATCHDOG_SCRIPT="$DAILY_DIR/portfolio/SL_watchdog.py"
ORDERS_DIR="$DAILY_DIR/Current_Orders"
LOG_DIR="$DAILY_DIR/logs"
PID_DIR="$DAILY_DIR/pids"

# Create PID directory if it doesn't exist
mkdir -p "$PID_DIR"

# Function to print colored output
print_header() {
    echo -e "${BOLD}${CYAN}============================================================${NC}"
    echo -e "${BOLD}${CYAN}          Multi-User Watchdog Manager${NC}"
    echo -e "${BOLD}${CYAN}============================================================${NC}"
}

print_status() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}[$(date '+%H:%M:%S')]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[$(date '+%H:%M:%S')]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 <command> [options]

Commands:
  start              Start watchdogs for all users with active orders
  stop               Stop all running watchdogs
  restart            Restart all watchdogs (stop + start)
  status             Show status of all watchdogs
  logs <user>        Show logs for specific user
  follow <user>      Follow logs for specific user in real-time
  list-users         List all users with active orders
  cleanup            Clean up stale PID files and processes

Options:
  -i, --interval SEC Set price polling interval in seconds (default: 45.0)
  -v, --verbose      Enable verbose logging
  -f, --force        Force operations (for stop/cleanup)
  -h, --help         Show this help message

Examples:
  $0 start                    # Start watchdogs for all users
  $0 start -i 3.0             # Start with 3-second polling
  $0 stop                     # Stop all watchdogs
  $0 status                   # Show status of all watchdogs
  $0 logs Sai                 # Show recent logs for user Sai
  $0 follow Som               # Follow Som's logs in real-time
  $0 restart -v               # Restart all with verbose logging
EOF
}

# Function to check if user has populated access token
has_valid_access_token() {
    local user_name="$1"
    local config_file="$DAILY_DIR/config.ini"

    if [ ! -f "$config_file" ]; then
        return 1
    fi

    # Look for the user's API credentials section and access_token
    local in_user_section=false
    while IFS= read -r line; do
        # Check if we're entering the user's credentials section
        if [[ "$line" =~ ^\[API_CREDENTIALS_${user_name}\]$ ]]; then
            in_user_section=true
            continue
        fi

        # Check if we're entering a different section
        if [[ "$line" =~ ^\[.*\]$ ]] && [ "$in_user_section" = true ]; then
            in_user_section=false
            continue
        fi

        # If we're in the user's section, look for access_token
        if [ "$in_user_section" = true ] && [[ "$line" =~ ^access_token[[:space:]]*=[[:space:]]*(.*)$ ]]; then
            local token="${BASH_REMATCH[1]}"
            # Remove leading/trailing whitespace
            token=$(echo "$token" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            # Check if token is not empty
            if [ -n "$token" ] && [ "$token" != "" ]; then
                return 0  # Valid token found
            else
                return 1  # Empty token
            fi
        fi
    done < "$config_file"

    return 1  # Token not found or empty
}

# Function to find users (from config files or orders directory)
find_users_with_orders() {
    local users=()

    # First, try to find users from config.ini API credentials with valid access tokens
    local config_file="$DAILY_DIR/config.ini"
    if [ -f "$config_file" ]; then
        while IFS= read -r line; do
            if [[ "$line" =~ ^\[API_CREDENTIALS_([a-zA-Z0-9_]+)\]$ ]]; then
                user_name="${BASH_REMATCH[1]}"
                # Only include users with populated access tokens
                if has_valid_access_token "$user_name"; then
                    users+=("$user_name")
                fi
            fi
        done < "$config_file"
    fi

    # If no users found in config, fall back to orders directory
    if [ ${#users[@]} -eq 0 ] && [ -d "$ORDERS_DIR" ]; then
        while IFS= read -r -d '' user_dir; do
            user_name=$(basename "$user_dir")
            # Skip non-user directories and only include if they have valid access tokens
            if [[ "$user_name" =~ ^[a-zA-Z0-9_]+$ ]] && has_valid_access_token "$user_name"; then
                users+=("$user_name")
            fi
        done < <(find "$ORDERS_DIR" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
    fi

    # Remove duplicates and sort
    printf '%s\n' "${users[@]}" | sort -u
}

# Function to get most recent orders file for a user
get_recent_orders_file() {
    local user_name="$1"
    find "$ORDERS_DIR/$user_name" -name "orders_*.json" -type f 2>/dev/null | sort -r | head -1
}

# Function to get PID file for a user
get_pid_file() {
    local user_name="$1"
    echo "$PID_DIR/watchdog_${user_name}.pid"
}

# Function to check if watchdog is running for a user
is_watchdog_running() {
    local user_name="$1"
    local pid_file=$(get_pid_file "$user_name")
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            return 0  # Running
        else
            # PID file exists but process is not running, remove stale PID file
            rm -f "$pid_file"
            return 1  # Not running
        fi
    fi
    return 1  # Not running
}

# Function to start watchdog for a user
start_user_watchdog() {
    local user_name="$1"
    local poll_interval="$2"
    local verbose="$3"
    local orders_file=$(get_recent_orders_file "$user_name")
    local pid_file=$(get_pid_file "$user_name")

    if is_watchdog_running "$user_name"; then
        local pid=$(cat "$pid_file")
        print_warning "Watchdog already running for $user_name (PID: $pid)"
        return 0
    fi

    print_status "Starting ATR-based stop loss watchdog for user: $user_name"
    if [ -n "$orders_file" ]; then
        print_info "  Orders file: $(basename "$orders_file")"
    else
        print_info "  Monitoring all CNC positions from Zerodha account"
    fi
    print_info "  Polling interval: ${poll_interval}s"

    # Create log directory for user
    mkdir -p "$LOG_DIR/$user_name"

    # Build command - orders file is now optional
    local cmd="python3 '$WATCHDOG_SCRIPT' --poll-interval $poll_interval"
    if [ -n "$orders_file" ]; then
        cmd="python3 '$WATCHDOG_SCRIPT' '$orders_file' --poll-interval $poll_interval"
    fi
    if [ "$verbose" = "true" ]; then
        cmd="$cmd --verbose"
    fi

    # Start the watchdog in background
    nohup bash -c "$cmd" > "$LOG_DIR/$user_name/startup.log" 2>&1 &
    local watchdog_pid=$!

    # Save PID to file
    echo $watchdog_pid > "$pid_file"

    # Wait a moment to see if the process starts successfully
    sleep 2

    # Check if process is still running
    if ps -p $watchdog_pid > /dev/null 2>&1; then
        print_success "Watchdog started for $user_name (PID: $watchdog_pid)"
        return 0
    else
        print_error "Failed to start watchdog for $user_name"
        print_error "Check startup log: $LOG_DIR/$user_name/startup.log"
        rm -f "$pid_file"
        return 1
    fi
}

# Function to kill ALL SL_watchdog processes system-wide
stop_all_watchdogs_force() {
    print_status "Killing ALL SL_watchdog.py processes system-wide..."

    # Find all SL_watchdog.py processes
    local all_processes=($(pgrep -f "SL_watchdog.py" 2>/dev/null))
    local killed_count=0

    if [ ${#all_processes[@]} -gt 0 ]; then
        print_status "Found ${#all_processes[@]} SL_watchdog processes total"
        for pid in "${all_processes[@]}"; do
            print_status "Killing SL_watchdog process (PID: $pid)"
            kill -TERM $pid 2>/dev/null
            sleep 1
            if ps -p $pid > /dev/null 2>&1; then
                kill -9 $pid 2>/dev/null
                sleep 1
            fi
            if ! ps -p $pid > /dev/null 2>&1; then
                killed_count=$((killed_count + 1))
            fi
        done
    fi

    # Clean up all PID files
    if [ -d "$PID_DIR" ]; then
        rm -f "$PID_DIR"/watchdog_*.pid
        print_status "Cleaned up all PID files"
    fi

    # Verify all processes are stopped
    local remaining_processes=($(pgrep -f "SL_watchdog.py" 2>/dev/null))
    if [ ${#remaining_processes[@]} -eq 0 ]; then
        if [ $killed_count -gt 0 ]; then
            print_success "Killed $killed_count SL_watchdog processes total"
        else
            print_warning "No SL_watchdog processes found"
        fi
        return 0
    else
        print_error "Failed to stop all SL_watchdog processes. Remaining: ${remaining_processes[*]}"
        return 1
    fi
}

# Function to stop watchdog for a user
stop_user_watchdog() {
    local user_name="$1"
    local force="$2"
    local pid_file=$(get_pid_file "$user_name")

    # First, kill ALL SL_watchdog.py processes for this user (regardless of PID tracking)
    local user_processes=($(pgrep -f "SL_watchdog.py.*$user_name" 2>/dev/null))
    local killed_count=0

    if [ ${#user_processes[@]} -gt 0 ]; then
        print_status "Found ${#user_processes[@]} SL_watchdog processes for user $user_name"
        for pid in "${user_processes[@]}"; do
            print_status "Killing SL_watchdog process for $user_name (PID: $pid)"
            kill -TERM $pid 2>/dev/null
            sleep 1
            if ps -p $pid > /dev/null 2>&1; then
                kill -9 $pid 2>/dev/null
                sleep 1
            fi
            if ! ps -p $pid > /dev/null 2>&1; then
                killed_count=$((killed_count + 1))
            fi
        done
    fi

    # Also handle tracked PID file
    if [ -f "$pid_file" ]; then
        local tracked_pid=$(cat "$pid_file")
        if ps -p $tracked_pid > /dev/null 2>&1; then
            print_status "Stopping tracked watchdog for $user_name (PID: $tracked_pid)"
            kill -TERM $tracked_pid 2>/dev/null
            sleep 1
            if ps -p $tracked_pid > /dev/null 2>&1; then
                kill -9 $tracked_pid 2>/dev/null
            fi
        fi
        rm -f "$pid_file"
    fi

    # Verify all processes are stopped
    local remaining_processes=($(pgrep -f "SL_watchdog.py.*$user_name" 2>/dev/null))
    if [ ${#remaining_processes[@]} -eq 0 ]; then
        if [ $killed_count -gt 0 ]; then
            print_success "Stopped $killed_count SL_watchdog processes for $user_name"
        else
            print_warning "No SL_watchdog processes found for user: $user_name"
        fi
        return 0
    else
        print_error "Failed to stop all SL_watchdog processes for $user_name. Remaining: ${remaining_processes[*]}"
        return 1
    fi
}

# Function to show status of all watchdogs
show_status() {
    print_header
    
    local users=($(find_users_with_orders))
    if [ ${#users[@]} -eq 0 ]; then
        print_warning "No users with active orders found"
        return 0
    fi
    
    print_status "Users configured for monitoring: ${#users[@]}"
    echo ""
    
    local running_count=0
    local total_positions=0
    
    printf "%-12s %-8s %-10s %-20s %-15s\n" "USER" "STATUS" "PID" "ORDERS FILE" "POSITIONS"
    printf "%-12s %-8s %-10s %-20s %-15s\n" "----" "------" "---" "-----------" "---------"
    
    for user in "${users[@]}"; do
        local status="STOPPED"
        local pid_display="-"
        local orders_file=$(get_recent_orders_file "$user")
        local orders_basename=$(basename "$orders_file" 2>/dev/null || echo "N/A")
        local positions=0
        
        if is_watchdog_running "$user"; then
            status="${GREEN}RUNNING${NC}"
            local pid=$(cat "$(get_pid_file "$user")")
            pid_display="$pid"
            running_count=$((running_count + 1))
            
            # Try to count positions from orders file
            if [ -f "$orders_file" ]; then
                positions=$(grep -c '"status": "COMPLETE"' "$orders_file" 2>/dev/null || echo "0")
                if [[ "$positions" =~ ^[0-9]+$ ]]; then
                    total_positions=$((total_positions + positions))
                else
                    positions=0
                fi
            fi
        else
            status="${RED}STOPPED${NC}"
        fi
        
        printf "%-12s %-8s %-10s %-20s %-15s\n" "$user" "$status" "$pid_display" "$orders_basename" "$positions"
    done
    
    echo ""
    print_info "Summary: $running_count/${#users[@]} watchdogs running, monitoring $total_positions positions total"
    
    # Show system resource usage if any watchdogs are running
    if [ $running_count -gt 0 ]; then
        echo ""
        print_status "Resource usage:"
        ps -o pid,pcpu,pmem,cmd -p $(pgrep -f "SL_watchdog.py" | tr '\n' ',' | sed 's/,$//') 2>/dev/null | head -10
    fi
}

# Function to show logs for a user
show_user_logs() {
    local user_name="$1"
    local follow="$2"
    local log_file="$LOG_DIR/$user_name/SL_watchdog_$user_name.log"
    
    if [ ! -f "$log_file" ]; then
        print_error "Log file not found for user: $user_name"
        print_status "Available users:"
        find_users_with_orders
        return 1
    fi
    
    print_status "Showing logs for user: $user_name"
    print_info "Log file: $log_file"
    echo ""
    
    if [ "$follow" = "true" ]; then
        print_status "Following logs in real-time (Ctrl+C to stop):"
        tail -f "$log_file"
    else
        print_status "Last 50 lines:"
        tail -50 "$log_file"
    fi
}

# Function to cleanup stale processes and PID files
cleanup() {
    local force="$1"
    
    print_status "Cleaning up stale watchdog processes and PID files..."
    
    # Find all stale PID files
    local cleaned=0
    if [ -d "$PID_DIR" ]; then
        for pid_file in "$PID_DIR"/watchdog_*.pid; do
            if [ -f "$pid_file" ]; then
                local pid=$(cat "$pid_file" 2>/dev/null)
                if [ -n "$pid" ]; then
                    if ! ps -p $pid > /dev/null 2>&1; then
                        print_status "Removing stale PID file: $(basename "$pid_file")"
                        rm -f "$pid_file"
                        cleaned=$((cleaned + 1))
                    fi
                fi
            fi
        done
    fi
    
    # Find orphaned watchdog processes
    local orphaned_pids=($(pgrep -f "SL_watchdog.py" | while read pid; do
        # Check if this PID is tracked in our PID files
        local tracked=false
        for pid_file in "$PID_DIR"/watchdog_*.pid; do
            if [ -f "$pid_file" ]; then
                local tracked_pid=$(cat "$pid_file" 2>/dev/null)
                if [ "$pid" = "$tracked_pid" ]; then
                    tracked=true
                    break
                fi
            fi
        done
        if [ "$tracked" = "false" ]; then
            echo "$pid"
        fi
    done))
    
    if [ ${#orphaned_pids[@]} -gt 0 ]; then
        print_warning "Found ${#orphaned_pids[@]} orphaned watchdog processes"
        if [ "$force" = "true" ]; then
            for pid in "${orphaned_pids[@]}"; do
                print_status "Killing orphaned process: $pid"
                kill -TERM "$pid" 2>/dev/null
                sleep 1
                if ps -p "$pid" > /dev/null 2>&1; then
                    kill -9 "$pid" 2>/dev/null
                fi
                cleaned=$((cleaned + 1))
            done
        else
            print_info "Use --force to clean up orphaned processes: ${orphaned_pids[*]}"
        fi
    fi
    
    if [ $cleaned -gt 0 ]; then
        print_success "Cleaned up $cleaned items"
    else
        print_success "No cleanup needed"
    fi
}

# Parse command line arguments
COMMAND=""
POLL_INTERVAL="45.0"
VERBOSE="false"
FORCE="false"
USER_ARG=""

if [ $# -eq 0 ]; then
    show_usage
    exit 1
fi

COMMAND="$1"
shift

while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--interval)
            POLL_INTERVAL="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE="true"
            shift
            ;;
        -f|--force)
            FORCE="true"
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
            USER_ARG="$1"
            shift
            ;;
    esac
done

# Main command execution
case "$COMMAND" in
    start)
        print_header
        print_status "Starting watchdogs for all users with active orders..."
        
        users=($(find_users_with_orders))
        if [ ${#users[@]} -eq 0 ]; then
            print_warning "No users configured for monitoring found"
            exit 0
        fi

        print_status "Found ${#users[@]} users configured for monitoring: ${users[*]}"
        echo ""
        
        success_count=0
        for user in "${users[@]}"; do
            if start_user_watchdog "$user" "$POLL_INTERVAL" "$VERBOSE"; then
                success_count=$((success_count + 1))
            fi
        done
        
        echo ""
        print_success "Started $success_count/${#users[@]} watchdogs successfully"
        ;;
        
    stop)
        print_header
        print_status "Stopping all watchdogs..."

        # Always use force mode to kill ALL SL_watchdog processes
        if stop_all_watchdogs_force; then
            print_success "All SL_watchdog processes stopped successfully"
        else
            print_error "Failed to stop all SL_watchdog processes"
            exit 1
        fi
        ;;
        
    restart)
        print_header
        print_status "Restarting all watchdogs..."

        # Stop all first using force mode
        stop_all_watchdogs_force >/dev/null 2>&1

        sleep 2
        
        # Start all
        users=($(find_users_with_orders))
        success_count=0
        for user in "${users[@]}"; do
            if start_user_watchdog "$user" "$POLL_INTERVAL" "$VERBOSE"; then
                success_count=$((success_count + 1))
            fi
        done
        
        echo ""
        print_success "Restarted $success_count/${#users[@]} watchdogs successfully"
        ;;
        
    status)
        show_status
        ;;
        
    logs)
        if [ -z "$USER_ARG" ]; then
            print_error "User name required for logs command"
            print_status "Available users:"
            find_users_with_orders
            exit 1
        fi
        show_user_logs "$USER_ARG" "false"
        ;;
        
    follow)
        if [ -z "$USER_ARG" ]; then
            print_error "User name required for follow command"
            print_status "Available users:"
            find_users_with_orders
            exit 1
        fi
        show_user_logs "$USER_ARG" "true"
        ;;
        
    list-users)
        print_status "Users with active orders:"
        users=($(find_users_with_orders))
        if [ ${#users[@]} -eq 0 ]; then
            print_warning "No users with active orders found"
        else
            for user in "${users[@]}"; do
                orders_file=$(get_recent_orders_file "$user")
                orders_date=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$orders_file" 2>/dev/null || echo "Unknown")
                running_status="STOPPED"
                if is_watchdog_running "$user"; then
                    running_status="${GREEN}RUNNING${NC}"
                fi
                printf "  %-10s %-10s %s\n" "$user" "$running_status" "($orders_date)"
            done
        fi
        ;;
        
    cleanup)
        cleanup "$FORCE"
        ;;
        
    *)
        print_error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac