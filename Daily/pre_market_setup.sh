#!/bin/bash
# Pre-Market Setup Script for India-TS
# Run this AFTER manually updating access token via loginz.py

cd /Users/maverick/PycharmProjects/India-TS/Daily

echo "=== India-TS Pre-Market Setup ==="
echo "Time: $(date '+%I:%M %p')"
echo "Note: Ensure you have already updated access token via loginz.py"
echo ""

echo "Step 1: Run Long/Short Reversal scanners first"
echo "Running Long Reversal Daily scanner..."
python3 scanners/Long_Reversal_Daily.py > /dev/null 2>&1 &
LONG_PID=$!
echo "Running Short Reversal Daily scanner..."
python3 scanners/Short_Reversal_Daily.py > /dev/null 2>&1 &
SHORT_PID=$!
echo "Waiting for scanners to complete (max 60 seconds)..."
COUNTER=0
while [ $COUNTER -lt 60 ]; do
    if ! ps -p $LONG_PID > /dev/null && ! ps -p $SHORT_PID > /dev/null; then
        echo "✓ Long/Short Reversal scanners completed"
        break
    fi
    sleep 1
    COUNTER=$((COUNTER + 1))
done
if [ $COUNTER -eq 60 ]; then
    kill $LONG_PID 2>/dev/null
    kill $SHORT_PID 2>/dev/null
    echo "⚠ Scanners took too long, proceeding anyway"
fi
echo ""
echo "Step 2: Clean up JSON persistence files"
echo "Resetting tracker persistence files for new day..."
CURRENT_TIME=$(date '+%Y-%m-%d %H:%M:00')
echo "{\"tickers\": {}, \"last_updated\": \"$CURRENT_TIME\"}" > /Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence_hourly_long.json
echo "{\"tickers\": {}, \"last_updated\": \"$CURRENT_TIME\"}" > /Users/maverick/PycharmProjects/India-TS/Daily/data/short_momentum/vsr_ticker_persistence_hourly_short.json
echo "{\"tickers\": {}, \"last_updated\": \"$CURRENT_TIME\"}" > /Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence.json
echo "✓ JSON persistence files reset"

echo ""
echo "Step 3: Restart tracker services for new date"
echo "Restarting services to use today's date for log files..."
# Kill any existing tracker processes first
pkill -f "hourly_tracker_service" 2>/dev/null
pkill -f "hourly_short_tracker_service" 2>/dev/null
sleep 2
# Restart via launchctl
launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist 2>/dev/null
sleep 1
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist
launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly-short-tracker-service.plist 2>/dev/null
sleep 1
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-short-tracker-service.plist
launchctl unload ~/Library/LaunchAgents/com.india-ts.short-momentum-tracker.plist 2>/dev/null
sleep 1
launchctl load ~/Library/LaunchAgents/com.india-ts.short-momentum-tracker.plist
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-tracker-enhanced.plist 2>/dev/null
sleep 1
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-tracker-enhanced.plist
echo "✓ Tracker services restarted"

echo ""
echo "Step 4: Run VSR scanner"
python3 scanners/VSR_Momentum_Scanner.py -u Sai
if [ $? -eq 0 ]; then
    echo "✓ VSR scanner completed successfully"
else
    echo "✗ VSR scanner failed - check access token"
    exit 1
fi

echo ""
echo "Step 5: Restart Telegram alert services with fresh access token"
echo "Stopping ALL existing Telegram services..."
# Kill all VSR telegram related processes
pkill -f "vsr_telegram" 2>/dev/null
pkill -f "telegram.*enhanced" 2>/dev/null
pkill -f "telegram.*market.*hours" 2>/dev/null
# Also unload from launchctl to prevent auto-restart
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist 2>/dev/null
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts.plist 2>/dev/null
sleep 3  # Give processes time to fully terminate

# Verify all telegram services are stopped
if pgrep -f "vsr_telegram" > /dev/null; then
    echo "⚠ Warning: Some telegram processes still running, force killing..."
    pkill -9 -f "vsr_telegram" 2>/dev/null
    sleep 2
fi

echo "Starting VSR Telegram service with updated token..."
nohup python3 /Users/maverick/PycharmProjects/India-TS/Daily/alerts/vsr_telegram_service.py --momentum-threshold 5.0 --score-threshold 30 --interval 60 > /Users/maverick/PycharmProjects/India-TS/Daily/logs/vsr_telegram/vsr_telegram_$(date +%Y%m%d).log 2>&1 &
echo "✓ VSR Telegram service started with fresh access token (single instance)"

echo ""
echo "Step 6: Start hourly breakout"
./alerts/start_hourly_breakout_alerts.sh
echo "✓ Hourly breakout service started"

echo ""
echo "Step 7: Restart dashboards for fresh data"
echo "Killing existing dashboard processes..."
# Kill all dashboard processes thoroughly
pkill -f "tracker_dashboard.py" 2>/dev/null
pkill -f "momentum_dashboard.py" 2>/dev/null
pkill -f "trend_continuation_dashboard.py" 2>/dev/null
sleep 3  # Give processes time to terminate

# Use specific Python 3.11 path for consistent execution
PYTHON_PATH="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"

echo "Starting dashboards with Python 3.11..."
cd dashboards

# Start each dashboard with explicit Python path
nohup $PYTHON_PATH vsr_tracker_dashboard.py > vsr_dashboard.log 2>&1 &
echo "✓ VSR Dashboard started on port 3001"

nohup $PYTHON_PATH hourly_tracker_dashboard_enhanced.py > hourly_dashboard.log 2>&1 &
echo "✓ Hourly Tracker Dashboard (with Persistence Levels) started on port 3002"

nohup $PYTHON_PATH short_momentum_dashboard.py > short_momentum_dashboard.log 2>&1 &
echo "✓ Short Momentum Dashboard started on port 3003"

nohup $PYTHON_PATH hourly_short_tracker_dashboard.py > hourly_short_dashboard.log 2>&1 &
echo "✓ Hourly Short Dashboard started on port 3004"

# Kill any existing ICT dashboard process first
pkill -f "ict_analysis_dashboard.py" 2>/dev/null
sleep 2
nohup $PYTHON_PATH ict_analysis_dashboard.py > ict_dashboard.log 2>&1 &
echo "✓ ICT Analysis Dashboard started on port 3008"

# Note: Port 5001 is used by Market Breadth Dashboard, not Trend Continuation

cd ..

echo ""
echo "Step 8: Start ICT Continuous Monitor"
# Start continuous ICT monitoring that updates every 5 minutes
cd portfolio
./start_ict_monitor.sh > /dev/null 2>&1
echo "✓ ICT continuous monitor started (updates every 5 minutes)"
cd ..

echo ""
echo "Step 9: Initialize Market Breadth Dashboard"
# Kill any existing instances
pkill -f "market_breadth_dashboard.py" 2>/dev/null
pkill -f "dashboard_enhanced.py" 2>/dev/null  # Kill the enhanced dashboard on 8080 if running
sleep 2
# Copy latest available breadth data for initialization
if [ -f "Market_Regime/breadth_data/market_breadth_20250814_154114.json" ]; then
    cp Market_Regime/breadth_data/market_breadth_20250814_154114.json Market_Regime/breadth_data/market_breadth_latest.json 2>/dev/null
elif [ ! -f "Market_Regime/breadth_data/market_breadth_latest.json" ]; then
    echo '{"timestamp":"'$(date '+%Y-%m-%d %H:%M:%S')'","overall":{"total_tickers":603,"above_sma20":300,"below_sma20":303,"percentage_above":49.8}}' > Market_Regime/breadth_data/market_breadth_latest.json
fi
# Start dashboards
cd Market_Regime
# Start Market Breadth Dashboard on port 5001 (default port in the script)
nohup python3 market_breadth_dashboard.py > market_breadth_5001.log 2>&1 &
echo "✓ Market Breadth Dashboard initialized on port 5001"
# Start Enhanced Dashboard on port 8080
nohup python3 dashboard_enhanced.py > dashboard_enhanced.log 2>&1 &
cd ..
echo "✓ Market Regime Dashboard running on port 8080"
echo "  Note: Full breadth scan will run at 9:30 AM when market opens"

echo ""
echo "Step 10: Check system status"
./check_all_systems.sh

echo ""
echo "Step 11: Load Market Regime Analyzer (5-min schedule)"
echo "Loading market regime analyzer to run every 5 minutes during market hours..."
# Unload first in case it's already loaded
launchctl unload ~/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist 2>/dev/null
sleep 1
# Load the plist
if [ -f ~/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist ]; then
    launchctl load ~/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist
    echo "✓ Market Regime Analyzer loaded (will run every 5 min during market hours)"
else
    # Copy from scheduler directory if not in LaunchAgents
    if [ -f /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/plists/com.india-ts.market_regime_analyzer_5min.plist ]; then
        cp /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/plists/com.india-ts.market_regime_analyzer_5min.plist ~/Library/LaunchAgents/
        launchctl load ~/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist
        echo "✓ Market Regime Analyzer installed and loaded"
    else
        echo "⚠ Market Regime Analyzer plist not found - skipping"
    fi
fi

echo ""
echo "Step 12: Run ICT SL Analysis"
echo "Running ICT stop loss analysis for all CNC positions..."
cd portfolio
python3 ict_analysis_runner.py -u Sai 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ ICT SL analysis completed successfully"
else
    echo "⚠ ICT SL analysis had no positions to analyze or encountered an error"
fi
cd ..

echo ""
echo "Step 13: Start Persistence Level Tracker"
echo "Starting VSR Persistence Level Tracker with Telegram notifications..."
./services/start_persistence_tracker.sh
if [ $? -eq 0 ]; then
    echo "✓ Persistence Level Tracker started successfully"
else
    echo "⚠ Failed to start Persistence Level Tracker"
fi

echo ""
echo "Step 14: Start ML Regime Feedback System (Phase 2)"
echo "Loading Market Regime feedback collection services..."

# Unload first in case they're already loaded
launchctl unload ~/Library/LaunchAgents/com.india-ts.regime-feedback-collector.plist 2>/dev/null
launchctl unload ~/Library/LaunchAgents/com.india-ts.regime-validation-monitor.plist 2>/dev/null
sleep 1

# Copy plists to LaunchAgents if not already there
if [ ! -f ~/Library/LaunchAgents/com.india-ts.regime-feedback-collector.plist ]; then
    cp /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/plists/com.india-ts.regime-feedback-collector.plist ~/Library/LaunchAgents/
    echo "  Installed regime feedback collector plist"
fi

if [ ! -f ~/Library/LaunchAgents/com.india-ts.regime-validation-monitor.plist ]; then
    cp /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/plists/com.india-ts.regime-validation-monitor.plist ~/Library/LaunchAgents/
    echo "  Installed regime validation monitor plist"
fi

# Load the services
launchctl load ~/Library/LaunchAgents/com.india-ts.regime-feedback-collector.plist
if [ $? -eq 0 ]; then
    echo "✓ Regime Feedback Collector loaded (runs every 5 min during market hours)"
else
    echo "⚠ Failed to load Regime Feedback Collector"
fi

launchctl load ~/Library/LaunchAgents/com.india-ts.regime-validation-monitor.plist
if [ $? -eq 0 ]; then
    echo "✓ Regime Validation Monitor loaded (runs hourly 10 AM - 4 PM)"
else
    echo "⚠ Failed to load Regime Validation Monitor"
fi

# Run initial feedback collection if market is open
CURRENT_TIME=$(date +%H%M)
DAY_OF_WEEK=$(date +%u)
if [ $DAY_OF_WEEK -ge 1 ] && [ $DAY_OF_WEEK -le 5 ]; then
    if [ $CURRENT_TIME -ge 915 ] && [ $CURRENT_TIME -le 1530 ]; then
        echo "  Running initial feedback collection..."
        cd Market_Regime
        python3 actual_regime_calculator.py > /dev/null 2>&1 &
        cd ..
        echo "✓ Initial feedback collection started"
    fi
fi

echo ""
echo "====================================="
echo "Pre-Market Setup Complete!"
echo "====================================="
echo ""
echo "=== Active Dashboards ==="
echo "  - VSR Tracker: http://localhost:3001"
echo "  - Hourly Long Tracker: http://localhost:3002 (with Persistence Levels)"
echo "  - Short Momentum: http://localhost:3003"
echo "  - Hourly Short Tracker: http://localhost:3004"
echo "  - Market Breadth: http://localhost:5001"
echo "  - Market Regime Enhanced: http://localhost:8080"
echo "  - ICT SL Analysis: http://localhost:3008"
echo ""
echo "=== Telegram Alerts Status ==="
echo "✅ VSR Telegram Service: Active with fresh access token"
echo "   - Momentum threshold: 5.0%"
echo "   - Score threshold: 30"
echo "   - Update interval: 60 seconds"
echo "   - Log file: logs/vsr_telegram/vsr_telegram_$(date +%Y%m%d).log"
echo ""
echo "✅ Persistence Level Tracker: Active"
echo "   - Monitors persistence level transitions"
echo "   - Sends scale-in/scale-out notifications"
echo "   - Tracks: Low (1-10), Medium (11-25), High (26-50), Very High (51-75), Extreme (75+)"
echo "   - Log file: logs/persistence_tracker/persistence_tracker_$(date +%Y%m%d).log"
echo ""
echo "=== Scheduled Jobs Status ==="
echo "✅ Market Regime Analyzer: Scheduled every 5 min (9:00 AM - 3:30 PM)"
echo "   - Emergency mode: Auto-retraining DISABLED"
echo "   - Using baseline model v_20250702_094009 (94% accuracy)"
echo "   - Data normalization: Enforced [-1, 1] range"
echo ""
echo "✅ ML Regime Feedback System (Phase 2): Active"
echo "   - Feedback Collector: Runs every 5 min during market hours"
echo "   - Calculates actual regime 45 min after predictions"
echo "   - Validation Monitor: Runs hourly (10 AM - 4 PM)"
echo "   - Target: 80% feedback coverage, 70% accuracy"
echo "   - Monitor progress: python3 Market_Regime/monitor_phase2.py"
echo ""
echo "⚠️  IMPORTANT NOTES:"
echo "1. Access token has been refreshed for all services"
echo "2. Monitor Telegram channel for momentum alerts"
echo "3. All tracker services using today's date for logs"
echo "4. Dashboards will auto-refresh with live data"
echo "5. Market Regime ML System Status:"
echo "   - Phase 1: ✅ COMPLETED (Emergency fixes applied)"
echo "   - Phase 2: 🔄 IN PROGRESS (Feedback collection active)"
echo "   - Phase 3: ⏳ PENDING (Requires 100+ validated predictions)"