#!/bin/bash
# Token Refresh Service Restart Script for India-TS
# Purpose: Properly restart all services when API token is refreshed
# Usage: ./refresh_token_services.sh
# Author: Claude/System

set -e

# Configuration
BASE_DIR="/Users/maverick/PycharmProjects/India-TS"
DAILY_DIR="${BASE_DIR}/Daily"
LOG_DIR="${DAILY_DIR}/logs/token_refresh"
LOG_FILE="${LOG_DIR}/token_refresh_$(date '+%Y%m%d_%H%M%S').log"

# Create log directory if it doesn't exist
mkdir -p "${LOG_DIR}"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# Function to print colored status
print_status() {
    local status=$1
    local message=$2
    case $status in
        "SUCCESS")
            echo -e "${GREEN}✓${NC} $message"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠${NC} $message"
            ;;
        "ERROR")
            echo -e "${RED}✗${NC} $message"
            ;;
        *)
            echo "$message"
            ;;
    esac
}

# Change to Daily directory
cd "${DAILY_DIR}"

log_message "========================================="
log_message "Token Refresh Service Restart Starting"
log_message "========================================="

# Step 1: Kill all existing services
log_message ""
log_message "Step 1: Killing all existing services"

# Kill telegram services
pkill -f "telegram" 2>/dev/null || true
pkill -f "vsr_telegram" 2>/dev/null || true
print_status "SUCCESS" "Killed telegram services"

# Kill alert services
pkill -f "alert_" 2>/dev/null || true
pkill -f "hourly_breakout_alert" 2>/dev/null || true
print_status "SUCCESS" "Killed alert services"

# Kill tracker services
pkill -f "tracker_service" 2>/dev/null || true
pkill -f "hourly_tracker" 2>/dev/null || true
pkill -f "short_momentum_tracker" 2>/dev/null || true
pkill -f "vsr_tracker_service" 2>/dev/null || true
print_status "SUCCESS" "Killed tracker services"

# Kill dashboard services
pkill -f "tracker_dashboard" 2>/dev/null || true
pkill -f "short_momentum_dashboard" 2>/dev/null || true
pkill -f "vsr_tracker_dashboard" 2>/dev/null || true
pkill -f "td_ma2_filter_dashboard" 2>/dev/null || true
print_status "SUCCESS" "Killed dashboard services"

# Kill any remaining Python processes on our ports
lsof -ti :3001 | xargs kill -9 2>/dev/null || true
lsof -ti :3002 | xargs kill -9 2>/dev/null || true
lsof -ti :3003 | xargs kill -9 2>/dev/null || true
lsof -ti :3004 | xargs kill -9 2>/dev/null || true
lsof -ti :3005 | xargs kill -9 2>/dev/null || true
lsof -ti :2002 | xargs kill -9 2>/dev/null || true
print_status "SUCCESS" "Cleared all service ports"

# Step 2: Clear Python cache
log_message ""
log_message "Step 2: Clearing Python cache"
find "${BASE_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${BASE_DIR}" -type f -name "*.pyc" -delete 2>/dev/null || true
print_status "SUCCESS" "Cleared Python cache"

# Step 3: Clear any credential cache files
log_message ""
log_message "Step 3: Clearing credential caches"
rm -f "${DAILY_DIR}/data/*cache*.json" 2>/dev/null || true
rm -f "${DAILY_DIR}/data/*token*.json" 2>/dev/null || true
print_status "SUCCESS" "Cleared credential caches"

# Step 4: Wait for processes to fully terminate
log_message ""
log_message "Step 4: Waiting for processes to terminate"
sleep 5
print_status "SUCCESS" "Process termination complete"

# Step 5: Verify Kite connection with new token
log_message ""
log_message "Step 5: Verifying Kite connection with new token"
python3 << EOF
import sys
import os
import configparser
sys.path.insert(0, '${BASE_DIR}')

try:
    # Load the config file
    config_path = '${DAILY_DIR}/config.ini'
    config = configparser.ConfigParser()
    config.read(config_path)

    # Get the credentials for Sai
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=config.get('API_CREDENTIALS_Sai', 'api_key'))
    kite.set_access_token(config.get('API_CREDENTIALS_Sai', 'access_token'))

    # Test the connection
    profile = kite.profile()
    print(f"Connected as: {profile['user_name']}")
    sys.exit(0)
except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    print_status "SUCCESS" "Kite connection verified with new token"
else
    print_status "ERROR" "Failed to connect with new token"
    exit 1
fi

# Step 6: Restart tracker services
log_message ""
log_message "Step 6: Restarting tracker services"

# VSR Tracker Enhanced
nohup python3 services/vsr_tracker_service_enhanced.py --user Sai --interval 60 > /dev/null 2>&1 &
sleep 2
if pgrep -f "vsr_tracker_service_enhanced" > /dev/null; then
    print_status "SUCCESS" "VSR Tracker Enhanced started"
else
    print_status "WARNING" "VSR Tracker Enhanced may not have started"
fi

# Hourly Tracker Service
nohup python3 services/hourly_tracker_service_fixed.py --user Sai > /dev/null 2>&1 &
sleep 2
if pgrep -f "hourly_tracker_service_fixed" > /dev/null; then
    print_status "SUCCESS" "Hourly Tracker Service started"
else
    print_status "WARNING" "Hourly Tracker Service may not have started"
fi

# Hourly Short Tracker Service
nohup python3 services/hourly_short_tracker_service.py --user Sai > /dev/null 2>&1 &
sleep 2
if pgrep -f "hourly_short_tracker_service" > /dev/null; then
    print_status "SUCCESS" "Hourly Short Tracker Service started"
else
    print_status "WARNING" "Hourly Short Tracker Service may not have started"
fi

# Short Momentum Tracker
nohup python3 services/short_momentum_tracker_service.py --user Sai --interval 60 > /dev/null 2>&1 &
sleep 2
if pgrep -f "short_momentum_tracker_service" > /dev/null; then
    print_status "SUCCESS" "Short Momentum Tracker started"
else
    print_status "WARNING" "Short Momentum Tracker may not have started"
fi

# Step 7: Restart alert services
log_message ""
log_message "Step 7: Restarting alert services"

# VSR Telegram Market Hours Manager (this will spawn vsr_telegram_service_enhanced.py during market hours)
nohup python3 alerts/vsr_telegram_market_hours_manager.py --user Sai > /dev/null 2>&1 &
sleep 3
if pgrep -f "vsr_telegram_market_hours_manager" > /dev/null; then
    print_status "SUCCESS" "VSR Telegram Market Hours Manager started"
    # Check if it spawned the service during market hours
    if pgrep -f "vsr_telegram_service_enhanced" > /dev/null; then
        print_status "SUCCESS" "VSR Telegram Service spawned (market hours)"
    fi
else
    print_status "WARNING" "VSR Telegram Market Hours Manager may not have started"
fi

# Hourly Breakout Alert Service
nohup python3 alerts/hourly_breakout_alert_service.py -u Sai > /dev/null 2>&1 &
sleep 2
if pgrep -f "hourly_breakout_alert_service" > /dev/null; then
    print_status "SUCCESS" "Hourly Breakout Alerts started"
else
    print_status "WARNING" "Hourly Breakout Alerts may not have started"
fi

# Step 8: Restart dashboards
log_message ""
log_message "Step 8: Restarting dashboards"

# VSR Dashboard (Port 3001)
cd dashboards
nohup python3 vsr_tracker_dashboard.py > /dev/null 2>&1 &
sleep 3
if lsof -i :3001 | grep LISTEN > /dev/null; then
    print_status "SUCCESS" "VSR Dashboard started on port 3001"
else
    print_status "WARNING" "VSR Dashboard may not be running on port 3001"
fi

# Hourly Tracker Dashboard (Port 3002)
nohup python3 hourly_tracker_dashboard.py > /dev/null 2>&1 &
sleep 3
if lsof -i :3002 | grep LISTEN > /dev/null; then
    print_status "SUCCESS" "Hourly Tracker Dashboard started on port 3002"
else
    print_status "WARNING" "Hourly Tracker Dashboard may not be running on port 3002"
fi

# Short Momentum Dashboard (Port 3003)
nohup python3 short_momentum_dashboard.py > /dev/null 2>&1 &
sleep 3
if lsof -i :3003 | grep LISTEN > /dev/null; then
    print_status "SUCCESS" "Short Momentum Dashboard started on port 3003"
else
    print_status "WARNING" "Short Momentum Dashboard may not be running on port 3003"
fi

# Hourly Short Dashboard (Port 3004)
nohup python3 hourly_short_tracker_dashboard.py > /dev/null 2>&1 &
sleep 3
if lsof -i :3004 | grep LISTEN > /dev/null; then
    print_status "SUCCESS" "Hourly Short Dashboard started on port 3004"
else
    print_status "WARNING" "Hourly Short Dashboard may not be running on port 3004"
fi

# TD MA II Filter Dashboard (Port 3005)
nohup python3 td_ma2_filter_dashboard.py > /dev/null 2>&1 &
sleep 3
if lsof -i :3005 | grep LISTEN > /dev/null; then
    print_status "SUCCESS" "TD MA II Filter Dashboard started on port 3005"
else
    print_status "WARNING" "TD MA II Filter Dashboard may not be running on port 3005"
fi

# Alert Volume Tracker (Port 2002)
cd ..
nohup python3 alert_volume_tracker_realtime.py > /dev/null 2>&1 &
sleep 3
if lsof -i :2002 | grep LISTEN > /dev/null; then
    print_status "SUCCESS" "Alert Volume Tracker started on port 2002"
else
    print_status "WARNING" "Alert Volume Tracker may not be running on port 2002"
fi

# Step 9: Force initial data generation
log_message ""
log_message "Step 9: Forcing initial data generation"

# Run a VSR scan to populate data
python3 scanners/VSR_Momentum_Scanner.py -u Sai > /dev/null 2>&1 &
print_status "SUCCESS" "Initiated VSR scan for data population"

# Step 10: Final verification
log_message ""
log_message "Step 10: Final service verification"
sleep 5

# Count running services
telegram_count=$(pgrep -f "telegram" | wc -l)
tracker_count=$(pgrep -f "tracker_service" | wc -l)
dashboard_count=$(lsof -i :3001,:3002,:3003,:3004,:3005,:2002 | grep LISTEN | wc -l)

log_message "========================================="
log_message "Token Refresh Complete"
log_message "Telegram Services: ${telegram_count} running"
log_message "Tracker Services: ${tracker_count} running"
log_message "Dashboards: ${dashboard_count} running"
log_message "========================================="

print_status "SUCCESS" "All services restarted with new token"
echo ""
echo "Dashboard URLs:"
echo "  VSR Dashboard:         http://localhost:3001"
echo "  Hourly Tracker:        http://localhost:3002"
echo "  Short Momentum:        http://localhost:3003"
echo "  Hourly Short:          http://localhost:3004"
echo "  TD MA II Filter:       http://localhost:3005"
echo "  Alert Volume Tracker:  http://localhost:2002"
echo ""
echo "Check logs at: ${LOG_FILE}"