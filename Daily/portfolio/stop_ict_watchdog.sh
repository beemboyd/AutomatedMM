#!/bin/bash
# Stop ICT Stop Loss Watchdog Service

echo "Stopping ICT Stop Loss Watchdog Service..."

# Unload the service
launchctl unload ~/Library/LaunchAgents/com.india-ts.ict-sl-watchdog.plist 2>/dev/null

# Check if stopped successfully
if ! launchctl list | grep -q "com.india-ts.ict-sl-watchdog"; then
    echo "✓ ICT Watchdog service stopped successfully"
else
    echo "⚠ Service may still be running. Trying to force stop..."
    launchctl remove com.india-ts.ict-sl-watchdog 2>/dev/null
    echo "Service stopped"
fi