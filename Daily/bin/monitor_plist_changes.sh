#!/bin/bash

# Script to monitor plist files for KeepAlive changes
PLIST_DIR="$HOME/Library/LaunchAgents"
LOG_FILE="/Users/maverick/PycharmProjects/India-TS/Daily/logs/plist_monitor.log"

echo "Starting plist monitoring at $(date)" >> "$LOG_FILE"

# Function to check KeepAlive value
check_keepalive() {
    local plist_file="$1"
    local filename=$(basename "$plist_file")
    
    if [[ -f "$plist_file" ]]; then
        local keepalive_value=$(plutil -p "$plist_file" 2>/dev/null | grep -i "KeepAlive" | awk '{print $3}')
        local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
        
        if [[ "$keepalive_value" == "1" ]]; then
            echo "[$timestamp] WARNING: $filename has KeepAlive=true" >> "$LOG_FILE"
            # Also check file modification time
            local mod_time=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$plist_file")
            echo "  File was last modified: $mod_time" >> "$LOG_FILE"
        else
            echo "[$timestamp] OK: $filename has KeepAlive=false" >> "$LOG_FILE"
        fi
    fi
}

# Check all India-TS plist files
for plist in "$PLIST_DIR"/com.india-ts.*.plist; do
    check_keepalive "$plist"
done

echo "Monitoring complete at $(date)" >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"