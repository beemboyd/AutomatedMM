#!/bin/bash
# Quick status check for Phase 2 ML Regime Feedback System

echo "======================================"
echo " ML REGIME PHASE 2 STATUS CHECK"
echo "======================================"
echo ""

# Check if services are loaded
echo "📋 LaunchAgent Status:"
echo "-----------------------"
launchctl list | grep -E "com.india-ts.regime-feedback-collector" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    PID=$(launchctl list | grep "com.india-ts.regime-feedback-collector" | awk '{print $1}')
    if [ "$PID" != "-" ]; then
        echo "✅ Feedback Collector: LOADED (PID: $PID)"
    else
        echo "⚠️  Feedback Collector: LOADED but NOT RUNNING"
    fi
else
    echo "❌ Feedback Collector: NOT LOADED"
fi

launchctl list | grep -E "com.india-ts.regime-validation-monitor" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    PID=$(launchctl list | grep "com.india-ts.regime-validation-monitor" | awk '{print $1}')
    if [ "$PID" != "-" ]; then
        echo "✅ Validation Monitor: LOADED (PID: $PID)"
    else
        echo "⚠️  Validation Monitor: LOADED but NOT RUNNING"
    fi
else
    echo "❌ Validation Monitor: NOT LOADED"
fi

echo ""
echo "🔄 Running Processes:"
echo "---------------------"
pgrep -f "regime_feedback_collector.py" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    PID=$(pgrep -f "regime_feedback_collector.py")
    echo "✅ Feedback Collector Process: RUNNING (PID: $PID)"
else
    echo "❌ Feedback Collector Process: NOT RUNNING"
fi

# Check database
echo ""
echo "💾 Database Status:"
echo "-------------------"
if [ -f "/Users/maverick/PycharmProjects/India-TS/data/regime_feedback.db" ]; then
    SIZE=$(du -h "/Users/maverick/PycharmProjects/India-TS/data/regime_feedback.db" | cut -f1)
    echo "✅ Feedback Database: EXISTS ($SIZE)"
    
    # Get record count using Python
    python3 -c "
import sqlite3
conn = sqlite3.connect('/Users/maverick/PycharmProjects/India-TS/data/regime_feedback.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM regime_feedback')
count = cursor.fetchone()[0]
print(f'   Total feedback records: {count}')
conn.close()
" 2>/dev/null
else
    echo "❌ Feedback Database: NOT FOUND"
fi

# Check recent logs
echo ""
echo "📝 Recent Log Activity:"
echo "-----------------------"
LOG_FILE="/Users/maverick/PycharmProjects/India-TS/Daily/logs/regime_feedback_collector.log"
if [ -f "$LOG_FILE" ]; then
    echo "Last 3 log entries:"
    tail -3 "$LOG_FILE" | while read line; do
        echo "   $line"
    done
else
    echo "❌ Log file not found"
fi

echo ""
echo "======================================"
echo " Use './Market_Regime/monitor_phase2.py' for detailed metrics"
echo "======================================"