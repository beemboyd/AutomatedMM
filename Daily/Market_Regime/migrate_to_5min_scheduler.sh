#!/bin/bash

# Migration script to transition from 30-minute to 5-minute regime analyzer scheduler
# This ensures graceful transition without service interruption

echo "=============================================="
echo "Market Regime Analyzer Scheduler Migration"
echo "Transitioning from 30-minute to 5-minute runs"
echo "=============================================="
echo

# Define plist files
OLD_PLIST_30MIN="$HOME/Library/LaunchAgents/com.india-ts.market_regime_analysis.plist"
OLD_PLIST_USTS="$HOME/Library/LaunchAgents/com.usts.market_regime_analysis.plist"
NEW_PLIST_5MIN="$HOME/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist"

# Function to unload a plist if it exists and is loaded
unload_if_exists() {
    local plist=$1
    local label=$2
    
    if [ -f "$plist" ]; then
        echo "Found existing plist: $plist"
        
        # Check if it's loaded
        if launchctl list | grep -q "$label"; then
            echo "  - Unloading $label..."
            launchctl unload "$plist" 2>/dev/null
            if [ $? -eq 0 ]; then
                echo "  - Successfully unloaded"
            else
                echo "  - Already unloaded or error occurred"
            fi
        else
            echo "  - Not currently loaded"
        fi
        
        # Archive the old plist
        archive_name="${plist}.backup.$(date +%Y%m%d_%H%M%S)"
        echo "  - Archiving to: $archive_name"
        mv "$plist" "$archive_name"
    else
        echo "No existing plist found at: $plist"
    fi
    echo
}

# Step 1: Check for and unload existing schedulers
echo "Step 1: Checking for existing regime analyzer schedulers..."
echo

# Unload the 30-minute schedulers
unload_if_exists "$OLD_PLIST_30MIN" "com.india-ts.market_regime_analysis"
unload_if_exists "$OLD_PLIST_USTS" "com.usts.market_regime_analysis"

# Check if 5-minute scheduler is already loaded
if launchctl list | grep -q "com.india-ts.market_regime_analyzer_5min"; then
    echo "5-minute scheduler is already loaded, unloading for clean install..."
    launchctl unload "$NEW_PLIST_5MIN" 2>/dev/null
    echo
fi

# Step 2: Verify the new plist exists
echo "Step 2: Verifying new 5-minute scheduler plist..."
if [ ! -f "$NEW_PLIST_5MIN" ]; then
    echo "ERROR: New plist not found at $NEW_PLIST_5MIN"
    echo "Please ensure the plist file has been created before running this migration."
    exit 1
fi
echo "Found: $NEW_PLIST_5MIN"
echo

# Step 3: Load the new 5-minute scheduler
echo "Step 3: Loading new 5-minute scheduler..."
launchctl load "$NEW_PLIST_5MIN"
if [ $? -eq 0 ]; then
    echo "Successfully loaded 5-minute scheduler"
else
    echo "ERROR: Failed to load 5-minute scheduler"
    exit 1
fi
echo

# Step 4: Verify the new scheduler is running
echo "Step 4: Verifying new scheduler status..."
if launchctl list | grep -q "com.india-ts.market_regime_analyzer_5min"; then
    echo "✅ 5-minute scheduler is active"
    launchctl list | grep "com.india-ts.market_regime_analyzer_5min"
else
    echo "❌ 5-minute scheduler is not active"
    echo "Please check the logs for errors."
    exit 1
fi
echo

# Step 5: Display next run time
echo "Step 5: Schedule Information"
echo "The regime analyzer will now run:"
echo "  - Every 5 minutes during market hours"
echo "  - Monday through Friday"
echo "  - 9:00 AM to 3:30 PM IST"
echo "  - Next run will be within 5 minutes"
echo

# Step 6: Clean up any other regime-related jobs
echo "Step 6: Checking for other regime-related jobs..."
echo "Current regime-related jobs:"
launchctl list | grep -i regime | grep -v "com.india-ts.market_regime_analyzer_5min"
echo

echo "=============================================="
echo "Migration Complete!"
echo "=============================================="
echo
echo "The market regime analyzer has been successfully migrated to run every 5 minutes."
echo "This ensures more timely updates of L/S ratios and breadth indicators."
echo
echo "To monitor the analyzer:"
echo "  - Check logs: tail -f ~/PycharmProjects/India-TS/Daily/logs/market_regime_analyzer_5min.log"
echo "  - View status: launchctl list | grep market_regime_analyzer_5min"
echo "  - Dashboard: http://localhost:8080"
echo