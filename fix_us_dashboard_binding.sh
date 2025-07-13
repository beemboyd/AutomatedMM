#!/bin/bash
# Script to fix US-TS dashboard binding to allow Tailscale access

echo "Fixing US-TS Market Regime Dashboard binding..."

# Path to the dashboard file
DASHBOARD_FILE="/Users/maverick/PycharmProjects/US-TS/Market_Regime/dashboard/regime_dashboard_8090_enhanced.py"

# Check if file exists
if [ ! -f "$DASHBOARD_FILE" ]; then
    echo "Error: Dashboard file not found at $DASHBOARD_FILE"
    exit 1
fi

# Create backup
cp "$DASHBOARD_FILE" "${DASHBOARD_FILE}.backup"
echo "Created backup: ${DASHBOARD_FILE}.backup"

# Replace the binding
sed -i '' "s/app.run(host='127.0.0.1', port=8090, debug=False)/app.run(host='0.0.0.0', port=8090, debug=False)/" "$DASHBOARD_FILE"

# Verify the change
if grep -q "host='0.0.0.0', port=8090" "$DASHBOARD_FILE"; then
    echo "✅ Successfully updated dashboard to bind to all interfaces"
else
    echo "❌ Failed to update binding. Restoring backup..."
    cp "${DASHBOARD_FILE}.backup" "$DASHBOARD_FILE"
    exit 1
fi

# Restart the service
echo "Restarting the dashboard service..."
launchctl start com.usts.regime_dashboard

# Wait for service to start
sleep 3

# Check if it's running
if lsof -i :8090 | grep -q "LISTEN"; then
    echo "✅ Dashboard is running"
    
    # Check binding
    if lsof -i :8090 | grep LISTEN | grep -q "*:8090"; then
        echo "✅ Dashboard is now accessible on all interfaces"
        echo ""
        echo "You can now access the dashboard at:"
        echo "  http://localhost:8090"
        echo "  http://macbook-pro.tailf149df.ts.net:8090"
    else
        echo "⚠️  Dashboard is running but may still be bound to localhost only"
        echo "Output of lsof:"
        lsof -i :8090 | grep LISTEN
    fi
else
    echo "❌ Dashboard failed to start. Check logs at:"
    echo "  /Users/maverick/PycharmProjects/US-TS/Market_Regime/logs/dashboard_error.log"
fi