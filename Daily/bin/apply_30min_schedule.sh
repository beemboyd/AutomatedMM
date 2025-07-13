#!/bin/bash
# Script to apply the new 30-minute schedule for Brooks analysis

echo "Applying 30-minute schedule for Al Brooks Higher Probability Reversal analysis..."

# Stop the current schedule if it's running
echo "Stopping current schedule..."
launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly_brooks_analysis.plist 2>/dev/null

# Copy the updated plist file
echo "Copying updated plist file..."
cp /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.hourly_brooks_analysis.plist ~/Library/LaunchAgents/

# Load the new schedule
echo "Loading new 30-minute schedule..."
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly_brooks_analysis.plist

# Verify it's loaded
echo "Verifying schedule is loaded..."
if launchctl list | grep -q "com.india-ts.hourly_brooks_analysis"; then
    echo "✅ Schedule successfully loaded!"
    echo ""
    echo "The Al Brooks Higher Probability Reversal analysis will now run every 30 minutes:"
    echo "- First run: 9:30 AM"
    echo "- Last run: 4:00 PM"
    echo "- Total runs per day: 14"
    echo ""
    echo "Schedule times: 9:30, 10:00, 10:30, 11:00, 11:30, 12:00, 12:30, 1:00, 1:30, 2:00, 2:30, 3:00, 3:30, 4:00"
else
    echo "❌ Failed to load schedule. Please check the logs."
fi

echo ""
echo "To monitor the logs, use:"
echo "tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/hourly_brooks.log"