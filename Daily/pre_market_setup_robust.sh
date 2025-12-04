#!/bin/bash
# Robust Pre-Market Setup Script for India-TS
# Version: 2.0
# Purpose: Ensure system starts in correct state every day without issues
# Author: Claude/System

# Exit on error
set -e

# Configuration
BASE_DIR="/Users/maverick/PycharmProjects/India-TS"
DAILY_DIR="${BASE_DIR}/Daily"
LOG_DIR="${DAILY_DIR}/logs/pre_market"
LOG_FILE="${LOG_DIR}/pre_market_$(date '+%Y%m%d').log"

# Create log directory if it doesn't exist
mkdir -p "${LOG_DIR}"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# Function to check if a service is running
check_service() {
    local service_name=$1
    if pgrep -f "$service_name" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to wait for file with timeout
wait_for_file() {
    local file_path=$1
    local timeout=$2
    local counter=0
    
    while [ $counter -lt $timeout ]; do
        if [ -f "$file_path" ]; then
            return 0
        fi
        sleep 1
        counter=$((counter + 1))
    done
    return 1
}

# Function to verify Kite connection
verify_kite_connection() {
    local test_script="${DAILY_DIR}/utils/test_kite_connection.py"
    if [ ! -f "$test_script" ]; then
        # Create a simple test script
        cat > "$test_script" << 'EOF'
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scanners.VSR_Momentum_Scanner import load_daily_config
from kiteconnect import KiteConnect

try:
    config = load_daily_config('Sai')
    api_key = config.get('API_CREDENTIALS_Sai', 'api_key')
    access_token = config.get('API_CREDENTIALS_Sai', 'access_token')
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    profile = kite.profile()
    print(f"Connected as: {profile.get('user_name', 'Unknown')}")
    sys.exit(0)
except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit(1)
EOF
        chmod +x "$test_script"
    fi
    
    python3 "$test_script"
    return $?
}

# Function to clean persistence files with proper initialization
clean_persistence_files() {
    local current_time=$(date '+%Y-%m-%d %H:%M:%S')

    # VSR Long tracker persistence (hourly tracking - reset daily)
    local vsr_long_file="${DAILY_DIR}/data/vsr_ticker_persistence_hourly_long.json"
    mkdir -p "$(dirname "$vsr_long_file")"
    echo "{\"tickers\": {}, \"last_updated\": \"$current_time\"}" > "$vsr_long_file"

    # VSR Short tracker persistence (hourly tracking - reset daily)
    local vsr_short_file="${DAILY_DIR}/data/short_momentum/vsr_ticker_persistence_hourly_short.json"
    mkdir -p "$(dirname "$vsr_short_file")"
    echo "{\"tickers\": {}, \"last_updated\": \"$current_time\"}" > "$vsr_short_file"

    # Main VSR persistence - DO NOT CLEAR (maintains 30-day alert history)
    # This file tracks historical alerts for "Last Alerted" dates in telegram notifications
    local vsr_main_file="${DAILY_DIR}/data/vsr_ticker_persistence.json"
    if [ ! -f "$vsr_main_file" ]; then
        mkdir -p "$(dirname "$vsr_main_file")"
        echo "{\"tickers\": {}, \"last_updated\": \"$current_time\"}" > "$vsr_main_file"
        log_message "✓ Created new main VSR persistence file"
    else
        log_message "✓ Preserved main VSR persistence file (30-day history intact)"
    fi

    log_message "✓ Hourly persistence files cleaned and initialized"
}

# Function to wait for market data availability
wait_for_market_data() {
    local test_script="${DAILY_DIR}/utils/test_market_data.py"
    cat > "$test_script" << 'EOF'
#!/usr/bin/env python3
import sys
import os
import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scanners.VSR_Momentum_Scanner import fetch_data_kite, load_daily_config
from kiteconnect import KiteConnect

try:
    config = load_daily_config('Sai')
    api_key = config.get('API_CREDENTIALS_Sai', 'api_key')
    access_token = config.get('API_CREDENTIALS_Sai', 'access_token')
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    
    # Test with a liquid stock
    now = datetime.datetime.now()
    from_date = (now - datetime.timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
    to_date = now.strftime('%Y-%m-%d %H:%M:%S')
    
    data = kite.historical_data(
        instrument_token=738561,  # RELIANCE
        from_date=from_date,
        to_date=to_date,
        interval='minute'
    )
    
    if data and len(data) >= 20:
        print(f"Market data available: {len(data)} data points")
        sys.exit(0)
    else:
        print(f"Insufficient data: {len(data) if data else 0} points")
        sys.exit(1)
except Exception as e:
    print(f"Data fetch failed: {e}")
    sys.exit(1)
EOF
    chmod +x "$test_script"
    
    local max_attempts=10
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if python3 "$test_script" > /dev/null 2>&1; then
            log_message "✓ Market data is available"
            return 0
        fi
        attempt=$((attempt + 1))
        log_message "Waiting for market data... (attempt $attempt/$max_attempts)"
        sleep 30
    done
    
    log_message "⚠ Warning: Could not verify market data availability"
    return 1
}

# Main execution starts here
log_message "========================================="
log_message "India-TS Robust Pre-Market Setup Starting"
log_message "========================================="

cd "${DAILY_DIR}"

# Step 0: Kill any existing caffeinate and start fresh for market hours
pkill -f "caffeinate.*market_hours" 2>/dev/null || true

# Prevent system sleep during market hours (9:00 AM to 4:00 PM IST = 7 hours)
# -d: Prevent display sleep, -i: Prevent idle sleep, -s: Prevent system sleep
log_message ""
log_message "Step 0: Starting caffeinate to prevent sleep during market hours"
caffeinate -dis -t 25200 &  # 7 hours = 25200 seconds
CAFFEINATE_PID=$!
echo $CAFFEINATE_PID > /tmp/caffeinate_market_hours.pid
log_message "✓ Caffeinate started (PID: $CAFFEINATE_PID) - system will not sleep for 7 hours"

# Step 1: Pre-flight checks
log_message ""
log_message "Step 1: Pre-flight checks"

# Check Python availability
if ! command -v python3 &> /dev/null; then
    log_message "✗ Python3 not found"
    exit 1
fi
log_message "✓ Python3 available"

# Check if config.ini exists
if [ ! -f "config.ini" ]; then
    log_message "✗ config.ini not found"
    exit 1
fi
log_message "✓ config.ini found"

# Step 2: Verify Kite connection
log_message ""
log_message "Step 2: Verifying Kite connection"
if verify_kite_connection; then
    log_message "✓ Kite connection verified"
else
    log_message "✗ Kite connection failed - please update access token via loginz.py"
    exit 1
fi

# Step 3: Run refresh_token_services.sh to ensure clean restart with current token
log_message ""
log_message "Step 3: Running token refresh service restart"
if [ -f "./refresh_token_services.sh" ]; then
    log_message "Executing refresh_token_services.sh to ensure all services use current token..."
    ./refresh_token_services.sh > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        log_message "✓ Token refresh service restart completed"
    else
        log_message "⚠ Token refresh service restart had warnings"
    fi
else
    log_message "⚠ refresh_token_services.sh not found, falling back to manual cleanup"
    pkill -f "hourly_tracker_service" 2>/dev/null || true
    pkill -f "short_tracker_service" 2>/dev/null || true
    pkill -f "vsr_tracker" 2>/dev/null || true
    pkill -f "tracker_dashboard.py" 2>/dev/null || true
    pkill -f "momentum_dashboard.py" 2>/dev/null || true
    pkill -f "alert_volume_tracker" 2>/dev/null || true
    sleep 2
    log_message "✓ Stale processes cleaned manually"
fi

# Step 4: Initialize persistence files
log_message ""
log_message "Step 4: Initializing persistence files"
clean_persistence_files

# Step 5: Run initial scanners with proper sequencing
log_message ""
log_message "Step 5: Running initial scanners"

# Run Unified Reversal Daily
log_message "Running Unified Reversal Daily scanner..."
if timeout 180 python3 scanners/Unified_Reversal_Daily.py > /dev/null 2>&1; then
    log_message "✓ Unified Reversal Daily completed"
else
    log_message "⚠ Unified Reversal Daily timed out or failed"
fi

# Step 6: Wait for sufficient market data
log_message ""
log_message "Step 6: Checking market data availability"
current_hour=$(date '+%H')
current_min=$(date '+%M')

# If market just opened (9:15-9:30), wait for data
if [ $current_hour -eq 9 ] && [ $current_min -ge 15 ] && [ $current_min -le 30 ]; then
    log_message "Market just opened, waiting for sufficient data..."
    wait_for_market_data
fi

# Step 7: Run VSR scanner with retry logic
log_message ""
log_message "Step 7: Running VSR scanner"
max_retries=3
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if python3 scanners/VSR_Momentum_Scanner.py -u Sai > /dev/null 2>&1; then
        log_message "✓ VSR scanner completed successfully"
        break
    else
        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $max_retries ]; then
            log_message "⚠ VSR scanner failed (attempt $retry_count/$max_retries), retrying in 10 seconds..."
            sleep 10
        else
            log_message "✗ VSR scanner failed after $max_retries attempts"
        fi
    fi
done

# Step 8: Verify tracker services are running (already started by refresh_token_services.sh)
log_message ""
log_message "Step 8: Verifying tracker services"

# Step 9: Verify services are running
log_message ""
log_message "Step 9: Verifying services"
sleep 5

if check_service "hourly_tracker_service"; then
    log_message "✓ Hourly tracker service is running"
else
    log_message "⚠ Hourly tracker service not detected"
fi

if check_service "vsr_tracker"; then
    log_message "✓ VSR tracker service is running"
else
    log_message "⚠ VSR tracker service not detected"
fi

# Step 10: Verify alert services (already started by refresh_token_services.sh)
log_message ""
log_message "Step 10: Verifying alert services"
if pgrep -f "telegram" > /dev/null; then
    log_message "✓ Telegram alert services are running"
else
    log_message "⚠ Telegram alert services not detected"
fi

# Step 11: Verify dashboards (already started by refresh_token_services.sh)
log_message ""
log_message "Step 11: Verifying dashboards"

# Check each dashboard port
if lsof -i :3001 | grep LISTEN > /dev/null 2>&1; then
    log_message "✓ VSR Dashboard running on port 3001"
else
    log_message "⚠ VSR Dashboard not detected on port 3001"
fi

if lsof -i :3002 | grep LISTEN > /dev/null 2>&1; then
    log_message "✓ Hourly Tracker Dashboard running on port 3002"
else
    log_message "⚠ Hourly Tracker Dashboard not detected on port 3002"
fi

if lsof -i :3003 | grep LISTEN > /dev/null 2>&1; then
    log_message "✓ Short Momentum Dashboard running on port 3003"
else
    log_message "⚠ Short Momentum Dashboard not detected on port 3003"
fi

if lsof -i :3004 | grep LISTEN > /dev/null 2>&1; then
    log_message "✓ Hourly Short Dashboard running on port 3004"
else
    log_message "⚠ Hourly Short Dashboard not detected on port 3004"
fi

if lsof -i :2002 | grep LISTEN > /dev/null 2>&1; then
    log_message "✓ PDH Breakout Tracker running on port 2002"
else
    log_message "⚠ PDH Breakout Tracker not detected on port 2002"
fi

# Step 12: Initialize Market Breadth Dashboard
log_message ""
log_message "Step 12: Initializing Market Breadth Dashboard"
pkill -f "market_breadth_dashboard.py" 2>/dev/null || true
sleep 2

# Ensure breadth data directory exists
mkdir -p Market_Regime/breadth_data

# Create initial breadth data if needed
if [ ! -f "Market_Regime/breadth_data/market_breadth_latest.json" ]; then
    echo "{\"timestamp\":\"$(date '+%Y-%m-%d %H:%M:%S')\",\"overall\":{\"total_tickers\":603,\"above_sma20\":300,\"below_sma20\":303,\"percentage_above\":49.8}}" > Market_Regime/breadth_data/market_breadth_latest.json
fi

(cd Market_Regime && nohup python3 market_breadth_dashboard.py > /dev/null 2>&1 &)
log_message "✓ Market Breadth Dashboard started on port 8080"

# Step 13: Wait for services to stabilize
log_message ""
log_message "Step 13: Waiting for services to stabilize"
sleep 10

# Step 14: Verify persistence files are being populated
log_message ""
log_message "Step 14: Verifying data population"

check_persistence_file() {
    local file_path=$1
    local file_desc=$2
    
    if [ -f "$file_path" ]; then
        local file_size=$(stat -f%z "$file_path" 2>/dev/null || stat -c%s "$file_path" 2>/dev/null)
        if [ "$file_size" -gt 50 ]; then
            log_message "✓ ${file_desc} is being populated (${file_size} bytes)"
            return 0
        else
            log_message "⚠ ${file_desc} exists but may be empty (${file_size} bytes)"
            return 1
        fi
    else
        log_message "⚠ ${file_desc} not found"
        return 1
    fi
}

# Wait a bit for initial data population
sleep 15

check_persistence_file "${DAILY_DIR}/data/vsr_ticker_persistence_hourly_long.json" "Long tracker persistence"
check_persistence_file "${DAILY_DIR}/data/short_momentum/vsr_ticker_persistence_hourly_short.json" "Short tracker persistence"

# Step 15: Final system check
log_message ""
log_message "Step 15: Running final system check"
if [ -f "./check_all_systems.sh" ]; then
    ./check_all_systems.sh >> "${LOG_FILE}" 2>&1
else
    log_message "⚠ check_all_systems.sh not found"
fi

# Step 16: Summary
log_message ""
log_message "========================================="
log_message "Pre-Market Setup Complete!"
log_message "========================================="
log_message ""
log_message "Dashboard URLs:"
log_message "  VSR Dashboard: http://localhost:3001"
log_message "  Hourly Tracker: http://localhost:3002" 
log_message "  Short Momentum: http://localhost:3003"
log_message "  Hourly Short: http://localhost:3004"
log_message "  Market Breadth: http://localhost:8080"
log_message ""
log_message "Log file: ${LOG_FILE}"
log_message ""

# Check for any warnings
if grep -q "⚠" "${LOG_FILE}"; then
    log_message "Note: Some warnings were detected. Review the log for details."
fi

# Create a status file for monitoring
echo "{
    \"last_run\": \"$(date '+%Y-%m-%d %H:%M:%S')\",
    \"status\": \"completed\",
    \"dashboards\": {
        \"vsr\": \"http://localhost:3001\",
        \"hourly_tracker\": \"http://localhost:3002\",
        \"short_momentum\": \"http://localhost:3003\",
        \"hourly_short\": \"http://localhost:3004\",
        \"pdh_breakout\": \"http://localhost:2002\",
        \"market_breadth\": \"http://localhost:8080\"
    }
}" > "${DAILY_DIR}/data/pre_market_status.json"

exit 0