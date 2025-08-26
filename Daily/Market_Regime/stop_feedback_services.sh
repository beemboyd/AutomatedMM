#!/bin/bash
# Stop the ML Regime Feedback Services

echo "Stopping ML Regime Feedback Services..."
echo ""

# Unload launchctl services
echo "Unloading scheduled services..."
launchctl unload ~/Library/LaunchAgents/com.india-ts.regime-feedback-collector.plist 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Regime Feedback Collector unloaded"
else
    echo "⚠ Feedback Collector was not loaded"
fi

launchctl unload ~/Library/LaunchAgents/com.india-ts.regime-validation-monitor.plist 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Regime Validation Monitor unloaded"
else
    echo "⚠ Validation Monitor was not loaded"
fi

# Kill any running processes
echo ""
echo "Stopping running processes..."
pkill -f "regime_feedback_collector.py" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Killed feedback collector process"
fi

pkill -f "monitor_phase2.py" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Killed validation monitor process"
fi

pkill -f "actual_regime_calculator.py" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Killed regime calculator process"
fi

echo ""
echo "ML Regime Feedback Services stopped."
echo ""
echo "To restart services:"
echo "  - Run pre-market setup: ./pre_market_setup.sh"
echo "  - Or manually: launchctl load ~/Library/LaunchAgents/com.india-ts.regime-feedback-collector.plist"