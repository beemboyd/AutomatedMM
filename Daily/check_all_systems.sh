#!/bin/bash
# India-TS System Status Check
# Run this after updating access token to verify all systems are ready

echo "=== India-TS System Status Check ==="
echo "Time: $(date '+%I:%M %p')"
echo ""

# 1. Check config
echo "1. Access Token Status:"
grep -A2 "API_CREDENTIALS_Sai" /Users/maverick/PycharmProjects/India-TS/Daily/config.ini | grep access_token | awk '{print "   Token: " (length($3) > 0 ? "✓ Present" : "✗ Missing")}'
echo ""

# 2. Check services
echo "2. Core Services:"
launchctl list | grep -E "long_reversal_daily|short_reversal_daily" | wc -l | xargs echo "   Scanners loaded:"
launchctl list | grep market_regime | grep -v "^-" > /dev/null && echo "   Market Regime: ✓ Running" || echo "   Market Regime: ✗ Not running"
ps aux | grep vsr_telegram | grep -v grep > /dev/null && echo "   VSR Alerts: ✓ Running" || echo "   VSR Alerts: ✗ Not running"
ps aux | grep hourly_breakout | grep -v grep > /dev/null && echo "   Trend Continuation: ✓ Running" || echo "   Trend Continuation: ✗ Not running"
echo ""

# 3. Check data freshness
echo "3. Data Status:"
ls -la /Users/maverick/PycharmProjects/India-TS/Daily/scanners/Hourly/VSR_*$(date +%Y%m%d)*.xlsx 2>/dev/null | wc -l | xargs echo "   VSR scans today:"
ls -la /Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence.json 2>/dev/null && echo "   Persistence file: ✓ Exists" || echo "   Persistence file: ✗ Missing"
echo ""

# 4. Dashboard status
echo "4. Dashboards:"
for port in 3001 3005 8080; do
    curl -s http://localhost:$port > /dev/null 2>&1 && echo "   Port $port: ✓ Accessible" || echo "   Port $port: ✗ Not accessible"
done
echo ""

# 5. Telegram connectivity
echo "5. Telegram Status:"
python3 -c "
import sys
sys.path.insert(0, '/Users/maverick/PycharmProjects/India-TS')
try:
    from Daily.alerts.telegram_notifier import TelegramNotifier
    t = TelegramNotifier()
    if t.test_connection():
        print('   Telegram: ✓ Connected')
    else:
        print('   Telegram: ✗ Not connected')
except Exception as e:
    print(f'   Telegram: ✗ Error - {str(e)}')
" 2>/dev/null || echo "   Telegram: ✗ Check failed"
echo ""

# 6. Recent activity
echo "6. Recent Activity:"
echo "   Scanner runs today: $(find /Users/maverick/PycharmProjects/India-TS/Daily -name "*$(date +%Y%m%d)*.xlsx" -type f | wc -l)"
echo "   Last VSR scan: $(ls -t /Users/maverick/PycharmProjects/India-TS/Daily/scanners/Hourly/VSR_*.xlsx 2>/dev/null | head -1 | xargs basename 2>/dev/null || echo 'None')"
echo ""

# 7. Check for errors in logs
echo "7. Error Check (last 10 minutes):"
error_count=$(find /Users/maverick/PycharmProjects/India-TS/Daily/logs -name "*.log" -mmin -10 -exec grep -l "ERROR\|CRITICAL\|401\|Unauthorized" {} \; 2>/dev/null | wc -l)
if [ $error_count -eq 0 ]; then
    echo "   ✓ No errors found in recent logs"
else
    echo "   ✗ Found errors in $error_count log files"
    echo "   Check with: find /Users/maverick/PycharmProjects/India-TS/Daily/logs -name '*.log' -mmin -10 -exec grep -l 'ERROR' {} \;"
fi
echo ""

echo "=== System Ready for Market Open ==="