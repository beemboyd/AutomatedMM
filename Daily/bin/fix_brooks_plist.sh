#!/bin/bash

# Script to fix the Brooks reversal plist and ensure KeepAlive is false

PLIST_SOURCE="/Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.brooks_reversal_fixed.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.india-ts.brooks_reversal_simple.plist"
LOG_FILE="/Users/maverick/PycharmProjects/India-TS/Daily/logs/plist_fix.log"

echo "[$(date)] Starting plist fix..." >> "$LOG_FILE"

# Check current KeepAlive value
if [[ -f "$PLIST_DEST" ]]; then
    current_keepalive=$(plutil -p "$PLIST_DEST" 2>/dev/null | grep -i "KeepAlive" | awk '{print $3}')
    echo "[$(date)] Current KeepAlive value: $current_keepalive" >> "$LOG_FILE"
    
    if [[ "$current_keepalive" == "1" ]]; then
        echo "[$(date)] WARNING: KeepAlive is true, fixing..." >> "$LOG_FILE"
        
        # Unload the current plist
        launchctl unload "$PLIST_DEST" 2>/dev/null
        
        # Copy the fixed version
        cp "$PLIST_SOURCE" "$PLIST_DEST"
        
        # Reload with the fixed version
        launchctl load "$PLIST_DEST"
        
        # Verify the fix
        new_keepalive=$(plutil -p "$PLIST_DEST" 2>/dev/null | grep -i "KeepAlive" | awk '{print $3}')
        echo "[$(date)] New KeepAlive value: $new_keepalive" >> "$LOG_FILE"
        
        if [[ "$new_keepalive" == "0" ]]; then
            echo "[$(date)] Successfully fixed KeepAlive to false" >> "$LOG_FILE"
        else
            echo "[$(date)] ERROR: Failed to fix KeepAlive" >> "$LOG_FILE"
        fi
    else
        echo "[$(date)] KeepAlive is already false, no action needed" >> "$LOG_FILE"
    fi
else
    echo "[$(date)] Plist not found, installing fresh copy..." >> "$LOG_FILE"
    cp "$PLIST_SOURCE" "$PLIST_DEST"
    launchctl load "$PLIST_DEST"
fi

echo "[$(date)] Fix complete" >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"