#!/bin/bash

echo "=========================================="
echo "Unloading all India-TS LaunchAgent jobs..."
echo "=========================================="

# Get all loaded india-ts jobs
loaded_jobs=$(launchctl list | grep india-ts | awk '{print $3}')

if [ -z "$loaded_jobs" ]; then
    echo "No India-TS jobs are currently loaded."
    exit 0
fi

UNLOAD_COUNT=0
FAILED_COUNT=0

for job in $loaded_jobs; do
    echo -n "Unloading $job... "
    plist_path="/Users/maverick/Library/LaunchAgents/$job.plist"
    
    if [ -f "$plist_path" ]; then
        if launchctl unload "$plist_path" 2>/dev/null; then
            echo "✅ Success"
            ((UNLOAD_COUNT++))
        else
            echo "❌ Failed"
            ((FAILED_COUNT++))
        fi
    else
        # Try unloading anyway (job might be loaded but plist moved)
        if launchctl remove "$job" 2>/dev/null; then
            echo "✅ Removed (plist not found)"
            ((UNLOAD_COUNT++))
        else
            echo "❌ Failed (plist not found)"
            ((FAILED_COUNT++))
        fi
    fi
done

echo ""
echo "=========================================="
echo "Summary: $UNLOAD_COUNT unloaded, $FAILED_COUNT failed"
echo "=========================================="
echo ""

# Check if any jobs are still loaded
remaining=$(launchctl list | grep -c india-ts)
if [ "$remaining" -eq 0 ]; then
    echo "✅ All India-TS jobs have been unloaded successfully."
else
    echo "⚠️  Warning: $remaining India-TS jobs are still loaded:"
    launchctl list | grep india-ts
fi