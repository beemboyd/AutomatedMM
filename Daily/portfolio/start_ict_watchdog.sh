#!/bin/bash
# Start ICT Stop Loss Watchdog Service

echo "Starting ICT Stop Loss Watchdog Service..."

# Copy plist to LaunchAgents
cp /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/plists/com.india-ts.ict-sl-watchdog.plist ~/Library/LaunchAgents/

# Unload if already loaded
launchctl unload ~/Library/LaunchAgents/com.india-ts.ict-sl-watchdog.plist 2>/dev/null

# Load the service
launchctl load ~/Library/LaunchAgents/com.india-ts.ict-sl-watchdog.plist

# Check if loaded successfully
if launchctl list | grep -q "com.india-ts.ict-sl-watchdog"; then
    echo "✓ ICT Watchdog service started successfully"
    echo "  - Runs every 15 minutes during market hours (9:15 AM - 3:30 PM)"
    echo "  - Logs: /Users/maverick/PycharmProjects/India-TS/Daily/logs/ict_watchdog/"
    echo "  - Analysis results: /Users/maverick/PycharmProjects/India-TS/Daily/portfolio/ict_analysis/"
else
    echo "✗ Failed to start ICT Watchdog service"
    exit 1
fi