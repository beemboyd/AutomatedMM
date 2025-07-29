#!/bin/bash
# Manage all India-TS dashboards

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function show_usage {
    echo "Usage: $0 [start|stop|status|restart]"
    echo ""
    echo "Commands:"
    echo "  start   - Start all dashboards (8 AM - 8 PM schedule)"
    echo "  stop    - Stop all dashboards"
    echo "  status  - Check status of all dashboards"
    echo "  restart - Restart all dashboards"
    echo ""
    echo "Dashboards:"
    echo "  Port 3001 - VSR Tracker Dashboard"
    echo "  Port 3003 - Short Momentum Dashboard"
    echo "  Port 5001 - Market Breadth Dashboard"
    echo "  Port 7080 - Health Check Dashboard"
    echo "  Port 8080 - Market Regime Enhanced Dashboard"
    echo "  Port 9090 - Job Manager Dashboard"
}

function check_dashboard_status {
    python3 "$PROJECT_DIR/scheduler/dashboard_manager.py" status
}

function start_dashboards {
    echo -e "${GREEN}Starting all dashboards...${NC}"
    python3 "$PROJECT_DIR/scheduler/dashboard_manager.py" start
    
    # Give dashboards time to start
    sleep 10
    
    echo -e "\n${GREEN}Dashboard Status:${NC}"
    check_dashboard_status
}

function stop_dashboards {
    echo -e "${RED}Stopping all dashboards...${NC}"
    python3 "$PROJECT_DIR/scheduler/dashboard_manager.py" stop
    
    # Give dashboards time to stop
    sleep 5
    
    echo -e "\n${GREEN}Dashboard Status:${NC}"
    check_dashboard_status
}

function install_scheduler {
    echo -e "${YELLOW}Installing dashboard scheduler plists...${NC}"
    
    # Install the new scheduler plists
    launchctl unload ~/Library/LaunchAgents/com.india-ts.dashboard_manager_start.plist 2>/dev/null
    launchctl unload ~/Library/LaunchAgents/com.india-ts.dashboard_manager_stop.plist 2>/dev/null
    launchctl unload ~/Library/LaunchAgents/com.india-ts.dashboard_refresh_control.plist 2>/dev/null
    
    cp "$PROJECT_DIR/scheduler/plists/com.india-ts.dashboard_manager_start.plist" ~/Library/LaunchAgents/
    cp "$PROJECT_DIR/scheduler/plists/com.india-ts.dashboard_manager_stop.plist" ~/Library/LaunchAgents/
    cp "$PROJECT_DIR/scheduler/plists/com.india-ts.dashboard_refresh_control.plist" ~/Library/LaunchAgents/
    
    launchctl load ~/Library/LaunchAgents/com.india-ts.dashboard_manager_start.plist
    launchctl load ~/Library/LaunchAgents/com.india-ts.dashboard_manager_stop.plist
    launchctl load ~/Library/LaunchAgents/com.india-ts.dashboard_refresh_control.plist
    
    echo -e "${GREEN}Dashboard schedulers installed:${NC}"
    echo "  - Dashboards will start at 8:00 AM IST"
    echo "  - Dashboards will stop at 8:00 PM IST"
    echo "  - Ports 3001, 3003, 5001 will stop refreshing at 3:30 PM IST"
}

# Main logic
case "$1" in
    start)
        start_dashboards
        ;;
    stop)
        stop_dashboards
        ;;
    status)
        check_dashboard_status
        ;;
    restart)
        stop_dashboards
        echo -e "\n${YELLOW}Waiting before restart...${NC}"
        sleep 5
        start_dashboards
        ;;
    install-scheduler)
        install_scheduler
        ;;
    *)
        show_usage
        exit 1
        ;;
esac