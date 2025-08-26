#!/bin/bash
# ICT Stop Loss Watch - 15 Minute Scheduler
# Runs ICT analysis on CNC positions every 15 minutes during market hours

# Configuration
BASE_DIR="/Users/maverick/PycharmProjects/India-TS"
DAILY_DIR="${BASE_DIR}/Daily"
LOG_DIR="${DAILY_DIR}/logs/ict_watchdog"
LOG_FILE="${LOG_DIR}/ict_watchdog_$(date '+%Y%m%d').log"

# Create log directory if it doesn't exist
mkdir -p "${LOG_DIR}"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

# Function to check if market is open
is_market_open() {
    current_hour=$(date '+%H')
    current_min=$(date '+%M')
    current_time=$((current_hour * 100 + current_min))
    
    # Market hours: 9:15 AM to 3:30 PM
    if [ $current_time -ge 915 ] && [ $current_time -le 1530 ]; then
        return 0
    else
        return 1
    fi
}

# Function to check if it's a trading day (Monday to Friday)
is_trading_day() {
    day_of_week=$(date '+%u')
    if [ $day_of_week -ge 1 ] && [ $day_of_week -le 5 ]; then
        return 0
    else
        return 1
    fi
}

# Main execution
cd "${DAILY_DIR}"

log_message "========================================="
log_message "ICT Stop Loss Watchdog - 15 Min Analysis"
log_message "========================================="

# Check if it's a trading day
if ! is_trading_day; then
    log_message "Not a trading day (Weekend). Skipping analysis."
    exit 0
fi

# Check if market is open
if ! is_market_open; then
    log_message "Market is closed. Skipping analysis."
    exit 0
fi

log_message "Market is open. Starting ICT analysis..."

# Run the ICT analysis with timeout (5 minutes max)
timeout 300 python3 portfolio/SL_Watch_ICT.py --user Sai >> "${LOG_FILE}" 2>&1

# Check exit status
exit_status=$?

if [ $exit_status -eq 0 ]; then
    log_message "✓ ICT analysis completed successfully"
    
    # Check if any positions need immediate attention
    latest_json=$(ls -t portfolio/ict_analysis/ict_sl_analysis_*.json 2>/dev/null | head -1)
    
    if [ -f "$latest_json" ]; then
        # Extract critical alerts (positions with BEARISH structure or high correction probability)
        critical_alerts=$(python3 -c "
import json
import sys

try:
    with open('$latest_json', 'r') as f:
        data = json.load(f)
    
    alerts = []
    for analysis in data:
        if 'BEARISH' in analysis.get('market_structure', '') or \
           analysis.get('correction_probability', 0) > 60:
            alerts.append(f\"{analysis['ticker']} ({analysis['timeframe']}): {analysis['recommendation']}\")
    
    if alerts:
        print('CRITICAL ALERTS:')
        for alert in alerts:
            print(f'  - {alert}')
    else:
        print('No critical alerts')
except Exception as e:
    print(f'Error checking alerts: {e}')
" 2>/dev/null)
        
        if [ ! -z "$critical_alerts" ]; then
            log_message "$critical_alerts"
        fi
    fi
    
elif [ $exit_status -eq 124 ]; then
    log_message "⚠ ICT analysis timed out after 5 minutes"
else
    log_message "✗ ICT analysis failed with exit code: $exit_status"
fi

# Create status file for monitoring
STATUS_FILE="${DAILY_DIR}/portfolio/ict_analysis/watchdog_status.json"
cat > "$STATUS_FILE" << EOF
{
    "last_run": "$(date '+%Y-%m-%d %H:%M:%S')",
    "status": "$([ $exit_status -eq 0 ] && echo 'success' || echo 'failed')",
    "exit_code": $exit_status,
    "log_file": "${LOG_FILE}"
}
EOF

log_message "Next run in 15 minutes..."
log_message "========================================="

exit $exit_status