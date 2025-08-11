# Pre-Market Playbook for India-TS System

## Daily Pre-Market Checklist (8:30 AM - 9:15 AM)

### Step 1: Update Access Token (8:30 AM)

**1.1 Get New Access Token**
```bash
# Run the login script
cd /Users/maverick/PycharmProjects/India-TS/Daily
python3 loginz.py

# Follow the prompts to get new access token
```

**1.2 Update config.ini**
```bash
# Edit config.ini
nano config.ini

# Update the access_token for your user (e.g., Sai)
[API_CREDENTIALS_Sai]
api_key = ms2m54xupkjzvbwj
api_secret = 84a716dpcnupceyrtk3rsuayzqxwems4
access_token = YOUR_NEW_ACCESS_TOKEN_HERE  # <-- Update this line
```

### Step 2: Verify Core Services (8:35 AM)

**2.1 Check Scanner Services**
```bash
# Verify reversal scanners are loaded
launchctl list | grep -E "long_reversal_daily|short_reversal_daily"

# Expected output (PID can be - or a number):
# -    0    com.india-ts.long_reversal_daily
# -    0    com.india-ts.short_reversal_daily
```

**2.2 Check Market Regime Analyzer**
```bash
# Verify market regime analyzer is running
launchctl list | grep market_regime_analyzer_5min

# Expected output:
# PID  0    com.india-ts.market_regime_analyzer_5min
```

### Step 3: Run VSR Scanner Manually (8:40 AM)

```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/scanners
python3 VSR_Momentum_Scanner.py -u Sai

# Verify output created
ls -la Hourly/VSR_$(date +%Y%m%d)*.xlsx
```

### Step 4: Start Alert Services (8:45 AM)

**4.1 Start VSR Telegram Alerts**
```bash
# Restart VSR Telegram service (picks up new access token)
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist

# Verify it's running
ps aux | grep vsr_telegram | grep -v grep
```

**4.2 Start Hourly Breakout Service**
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/alerts
./start_hourly_breakout_alerts.sh

# Verify it's running
ps aux | grep hourly_breakout | grep -v grep
```

### Step 5: Verify Dashboards (8:50 AM)

**5.1 Check All Dashboards**
```bash
# Quick status check
for port in 3001 3002 3003 3004 3005 3006 8080; do
    curl -s http://localhost:$port > /dev/null 2>&1 && echo "Port $port: ✓ Running" || echo "Port $port: ✗ Not responding"
done
```

**5.2 Open Critical Dashboards**
```bash
# Open in browser
open http://localhost:3001  # VSR Dashboard
open http://localhost:3005  # Trend Continuation Dashboard
open http://localhost:8080  # Market Regime Dashboard
```

### Step 6: Clear Stale Data (8:55 AM)

**6.1 Check Persistence Files**
```bash
# Check if persistence files are from today
ls -la /Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence*.json

# If files are old (check timestamp), reset them:
cd /Users/maverick/PycharmProjects/India-TS/Daily/data
for file in vsr_ticker_persistence*.json; do
    if [ -f "$file" ]; then
        echo "Backing up $file"
        mv "$file" "${file}.backup_$(date +%Y%m%d_%H%M%S)"
        echo "{}" > "$file"
    fi
done
```

### Step 7: Final Health Check (9:00 AM)

**7.1 Run Complete Status Check**
```bash
#!/bin/bash
# Save this as check_all_systems.sh

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

echo "=== System Ready for Market Open ==="
```

### Step 8: Monitor First 15 Minutes (9:15 AM - 9:30 AM)

**8.1 Check for Scanner Activity**
```bash
# Watch for scanner outputs
watch -n 60 'ls -la /Users/maverick/PycharmProjects/India-TS/Daily/results/*$(date +%Y%m%d)*.xlsx | tail -5'
```

**8.2 Monitor Alerts**
```bash
# Check alert logs
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_hourlybo/hourly_breakout_$(date +%Y%m%d)*.log
```

## Troubleshooting Quick Fixes

### Issue: "401 Unauthorized" or API errors
```bash
# Solution: Update access token
python3 loginz.py
# Update config.ini with new token
# Restart all services that use API
```

### Issue: No data on dashboards
```bash
# Solution: Reset persistence files
cd /Users/maverick/PycharmProjects/India-TS/Daily
python3 -c "
import os
import json
files = ['data/vsr_ticker_persistence.json', 
         'data/vsr_ticker_persistence_hourly_long.json',
         'data/short_momentum/vsr_ticker_persistence_hourly_short.json']
for f in files:
    if os.path.exists(f):
        with open(f, 'w') as file:
            json.dump({}, file)
        print(f'Reset: {f}')
"

# Restart tracker services
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-tracker-enhanced.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-tracker-enhanced.plist
```

### Issue: Telegram not sending alerts
```bash
# Test Telegram connection
python3 -c "
from Daily.alerts.telegram_notifier import TelegramNotifier
t = TelegramNotifier()
if t.test_connection():
    print('✓ Telegram working')
else:
    print('✗ Check Telegram config in config.ini')
"
```

## Service Restart Commands

### Restart Everything (Nuclear Option)
```bash
#!/bin/bash
# Save as restart_all_services.sh

echo "Stopping all services..."
# Stop dashboards
pkill -f "tracker_dashboard.py"
pkill -f "momentum_dashboard.py"
pkill -f "market_regime_dashboard"

# Unload all services
for plist in ~/Library/LaunchAgents/com.india-ts.*.plist; do
    if [ -f "$plist" ]; then
        launchctl unload "$plist" 2>/dev/null
    fi
done

echo "Waiting 5 seconds..."
sleep 5

echo "Starting core services..."
# Load scanners
launchctl load ~/Library/LaunchAgents/com.india-ts.long_reversal_daily.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.short_reversal_daily.plist

# Load market regime
launchctl load ~/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist

# Load VSR telegram
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist

# Start dashboards
cd /Users/maverick/PycharmProjects/India-TS/Daily
./utils/start_market_breadth_dashboard.sh &
./alerts/start_hourly_breakout_alerts.sh &

echo "All services restarted!"
```

## Critical Success Factors

1. **Access Token MUST be fresh** - Updated daily via loginz.py
2. **VSR Scanner MUST run** - At least once before market open
3. **Persistence files MUST be clean** - No stale data from previous days
4. **Telegram config MUST be valid** - Test connection before market
5. **Dashboards MUST be accessible** - Check all ports respond

## Emergency Contacts & Resources

- Dashboard URLs:
  - VSR: http://localhost:3001
  - Trend Continuation: http://localhost:3005
  - Market Regime: http://localhost:8080
  
- Log Locations:
  - VSR: `/Daily/logs/vsr_tracker/`
  - Alerts: `/Daily/logs/alerts_hourlybo/`
  - Market Regime: `/Daily/Market_Regime/market_regime_analyzer.log`

- Config Files:
  - Main: `/Daily/config.ini`
  - Plists: `~/Library/LaunchAgents/com.india-ts.*.plist`

## One-Command Pre-Market Setup

```bash
#!/bin/bash
# Save as pre_market_setup.sh
cd /Users/maverick/PycharmProjects/India-TS/Daily

echo "Step 1: Update access token"
python3 loginz.py

echo "Step 2: Run VSR scanner"
cd scanners && python3 VSR_Momentum_Scanner.py -u Sai && cd ..

echo "Step 3: Restart alert services"
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist

echo "Step 4: Start hourly breakout"
./alerts/start_hourly_breakout_alerts.sh

echo "Step 5: Check system status"
./check_all_systems.sh

echo "Pre-market setup complete!"
```

---

Last Updated: 2025-08-05
Time Required: 15-20 minutes
Critical Window: 8:30 AM - 9:00 AM