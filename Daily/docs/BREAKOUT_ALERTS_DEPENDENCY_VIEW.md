# Breakout Alerts Services - Dependency View & Daily Playbook

## Service Dependency Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BREAKOUT ALERT SERVICES                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────┐         ┌──────────────────────┐         │
│  │ Hourly Breakout      │         │ First Hour Breakout  │         │
│  │ Alert Service        │         │ Service              │         │
│  │ (9:00 AM - 3:30 PM)  │         │ (9:15 AM - 10:15 AM) │         │
│  └──────────┬───────────┘         └──────────┬───────────┘         │
│             │                                 │                      │
│             └─────────────┬───────────────────┘                     │
│                           │                                          │
│                           ▼                                          │
│              ┌────────────────────────┐                            │
│              │ SHARED DEPENDENCIES    │                            │
│              └────────────────────────┘                            │
│                           │                                          │
│      ┌────────────────────┼────────────────────┐                   │
│      ▼                    ▼                    ▼                   │
│ ┌─────────────┐  ┌──────────────────┐  ┌──────────────┐          │
│ │ VSR Scanner │  │ Long Reversal    │  │ Market Data  │          │
│ │ (Hourly)    │  │ Daily Scanner    │  │ (KiteConnect)│          │
│ └─────────────┘  └──────────────────┘  └──────────────┘          │
│      │                    │                    │                    │
│      ▼                    ▼                    │                    │
│ ┌─────────────┐  ┌──────────────────┐         │                   │
│ │ VSR         │  │ Scanner Results  │         │                   │
│ │ Persistence │  │ (Excel Files)    │         │                   │
│ │ JSON        │  └──────────────────┘         │                   │
│ └─────────────┘                               │                   │
│                                               ▼                    │
│                                    ┌──────────────────┐           │
│                                    │ Telegram Bot    │           │
│                                    │ (Alerts)        │           │
│                                    └──────────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

## Service Dependencies

### 1. Hourly Breakout Alert Service
**File**: `/Users/maverick/PycharmProjects/India-TS/Daily/alerts/hourly_breakout_alert_service.py`

#### Dependencies:
- **VSR Scanner Data**
  - Source: VSR persistence file (`data/vsr_ticker_persistence.json`)
  - Requirement: VSR ratio >= 2.0
  - Updated by: VSR Momentum Scanner (runs throughout the day)

- **Long Reversal Scanner Results**
  - Source: Excel files in `results/` directory
  - Requirement: Momentum >= 10%
  - Updated by: Long Reversal Daily scanner (every 30 minutes)

- **Market Data**
  - Source: KiteConnect API
  - Credentials: From `config.ini` (user-specific)
  - Used for: Real-time price monitoring

- **State Files**
  - `data/hourly_breakout_state.json` - Tracks alerted tickers and state

### 2. First Hour Breakout Service
**File**: `/Users/maverick/PycharmProjects/India-TS/Daily/alerts/first_hour_breakout_service.py`

#### Dependencies:
- **Hourly Breakout State**
  - Source: `data/hourly_breakout_state.json`
  - Loads tracked tickers from hourly service
  - Must run AFTER hourly service has initialized

- **Market Data**
  - Source: KiteConnect API
  - 5-minute candle data
  - Volume calculations

- **State Files**
  - `data/first_hour_state.json` - Tracks 5-min breakouts

## Required Services & Their Schedule

### Core Scanner Services (Must be running)

1. **Long Reversal Daily Scanner**
   - Plist: `com.india-ts.long_reversal_daily`
   - Schedule: Every 30 minutes (9:00 AM - 3:30 PM)
   - Generates: Scanner results with momentum data

2. **VSR Momentum Scanner**
   - Manual run or scheduled
   - Updates: VSR persistence file
   - Critical for: Identifying high VSR ratio tickers

3. **Market Regime Analyzer** (Optional but recommended)
   - Plist: `com.india-ts.market_regime_analyzer_5min`
   - Provides: Market context

## Dashboard Overview

### Hourly Breakout Dashboard (Port 3005)
**URL**: http://localhost:3005

**Features**:
- Real-time alert log viewer
- Statistics: Total alerts, unique tickers, alert rate
- Alert timeline visualization
- Service control buttons (Start/Stop)
- Auto-refresh every 30 seconds

**Key Metrics Displayed**:
- Total Alerts Sent
- Unique Tickers Alerted
- Alerts in Last Hour
- Currently Tracked Tickers
- Last Alert Time

### First Hour Dashboard (Port 3006)
**URL**: http://localhost:3006

**Features**:
- 5-minute breakout alert viewer
- First hour specific metrics (9:15-10:15 AM)
- Volume ratio indicators
- Alert distribution by time
- Service status indicator

**Key Metrics Displayed**:
- Total 5-min Breakouts
- Average Volume Ratio
- Breakout Distribution Chart
- Active Monitoring Status

## Complete Service Startup Sequence

### Service Startup Timeline

```
8:30 AM ─┬─ Job Manager Dashboard
         └─ Core Scanner Services (Long/Short Reversal)
         
8:45 AM ─┬─ Market Regime Analyzer
         └─ VSR Scanner (Manual Run)
         
8:55 AM ─── VSR Telegram Alerts (Optional)

9:00 AM ─┬─ Hourly Breakout Service
         └─ Wait for scanner results...
         
9:14 AM ─── First Hour Service (Auto-starts)

9:15 AM ─── Market Opens - All services active
```

### System Boot / Fresh Start Sequence

This section documents the complete startup sequence from a fresh boot or when all services need to be started.

#### Phase 1: Core Infrastructure (8:30 AM)

**Step 1.1: Start Job Manager Dashboard**
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/Health
./start_job_manager.sh

# Verify it's running
open http://localhost:2000
```

**Step 1.2: Start Core Scanner Services**
```bash
# Load the reversal scanners (if not already loaded)
launchctl load ~/Library/LaunchAgents/com.india-ts.long_reversal_daily.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.short_reversal_daily.plist

# Verify they're loaded
launchctl list | grep -E "long_reversal_daily|short_reversal_daily"
```

**Step 1.3: Start Market Regime Analyzer**
```bash
# Load market regime analyzer
launchctl load ~/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist

# Check status
launchctl list | grep market_regime
```

#### Phase 2: VSR and Momentum Services (8:45 AM)

**Step 2.1: Run VSR Scanner Manually (First Time)**
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/scanners
python3 VSR_Momentum_Scanner.py -u Sai

# Verify persistence file is created/updated
ls -la ../data/vsr_ticker_persistence.json
```

**Step 2.2: Start VSR Telegram Alerts (Optional)**
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/Alerts
./start_vsr_telegram_alerts.sh

# Check if running
ps aux | grep vsr_telegram | grep -v grep
```

#### Phase 3: Breakout Alert Services (9:00 AM)

**Step 3.1: Start Hourly Breakout Service**
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/alerts
./start_hourly_breakout_alerts.sh

# Verify service started
ps aux | grep hourly_breakout | grep -v grep

# Check dashboard
open http://localhost:3005
```

**Step 3.2: Verify Hourly Service Initialization**
```bash
# Check if service is tracking tickers
tail -20 /Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_hourlybo/hourly_breakout_*.log | grep "Loaded.*tickers"

# Check state file
cat /Users/maverick/PycharmProjects/India-TS/Daily/data/hourly_breakout_state.json | jq '.tracked_tickers | length'
```

**Step 3.3: First Hour Service (Auto-starts at 9:14 AM)**
```bash
# Verify plist is loaded (should auto-start)
launchctl list | grep first-hour

# If not loaded, load it manually
launchctl load ~/Library/LaunchAgents/com.india-ts.first-hour-alerts.plist

# At 9:15 AM, verify it's running
ps aux | grep first_hour | grep -v grep

# Check dashboard
open http://localhost:3006
```

## Daily Playbook - Service Startup Checklist

### Pre-Market (8:45 AM - 9:00 AM)

#### Step 1: Run Complete Status Check
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/alerts
./check_breakout_status.sh
```

#### Step 2: Verify Core Services
```bash
# Check if core scanners are loaded
launchctl list | grep -E "long_reversal_daily|short_reversal_daily"

# Expected output should show both services with PID 0 or -
```

#### Step 2: Check VSR Scanner Status
```bash
# Verify VSR persistence file exists and is recent
ls -la /Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence.json

# Check last modified time - should be from previous day
```

#### Step 3: Start Hourly Breakout Service
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/alerts
./start_hourly_breakout_alerts.sh

# Verify it's running
ps aux | grep hourly_breakout | grep -v grep
```

#### Step 4: Verify Hourly Service Dashboard
```bash
# Check dashboard is accessible
curl -s http://localhost:3005 | head -5

# Or open in browser
open http://localhost:3005
```

#### Step 5: Start First Hour Service (at 9:14 AM)
```bash
# This should start automatically via plist
# But can manually start if needed:
cd /Users/maverick/PycharmProjects/India-TS/Daily/alerts
./start_first_hour_alerts.sh

# Verify dashboard
open http://localhost:3006
```

### Market Hours Monitoring (9:15 AM - 3:30 PM)

#### Dashboard Monitoring
```bash
# Open all monitoring dashboards in browser
open http://localhost:3005  # Hourly Breakout Dashboard
open http://localhost:3006  # First Hour Dashboard (active until 10:15 AM)
open http://localhost:2000  # Job Manager Dashboard (optional)
```

#### Dashboard Health Indicators

**Hourly Breakout Dashboard (3005)**:
- ✅ Green status light = Service running
- 🔴 Red status light = Service stopped
- Check "Currently Tracking" counter > 0
- Monitor "Alerts in Last Hour" for activity
- Review alert log for any error messages

**First Hour Dashboard (3006)**:
- Active only 9:15 AM - 10:15 AM
- Check "Session Status" indicator
- Monitor 5-min breakout frequency
- Volume ratio should typically be > 1.0 for valid breakouts

#### Regular Health Checks (Every Hour)
```bash
# 1. Check service status
launchctl list | grep -E "hourly-breakout|first-hour"

# 2. Check for recent alerts in logs
tail -20 /Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_hourlybo/hourly_breakout_*.log

# 3. Verify Telegram connectivity (check for any errors)
grep -i "error" /Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_hourlybo/hourly_breakout_*.log | tail -10

# 4. Quick dashboard status check
curl -s http://localhost:3005/api/status | jq '.'
curl -s http://localhost:3006/api/status | jq '.'
```

#### Quick Status Script
Create this helper script at `/Users/maverick/PycharmProjects/India-TS/Daily/alerts/check_breakout_status.sh`:

```bash
#!/bin/bash

echo "=== Breakout Alert Services Status ==="
echo ""

# Check services
echo "1. Service Status:"
echo "   Hourly Breakout: $(launchctl list | grep hourly-breakout-alerts | awk '{print $1}')"
echo "   First Hour: $(launchctl list | grep first-hour-alerts | awk '{print $1}')"
echo ""

# Check processes
echo "2. Running Processes:"
ps aux | grep -E "hourly_breakout|first_hour" | grep -v grep | wc -l | xargs echo "   Active processes:"
echo ""

# Check recent alerts
echo "3. Recent Alerts (last hour):"
find /Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_hourlybo -name "*.log" -mmin -60 -exec grep "Alert sent" {} \; | wc -l | xargs echo "   Hourly alerts:"
find /Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_firsthour -name "*.log" -mmin -60 -exec grep "Alert sent" {} \; | wc -l | xargs echo "   First hour alerts:"
echo ""

# Check tracked tickers
echo "4. Tracked Tickers:"
python3 -c "
import json
try:
    with open('/Users/maverick/PycharmProjects/India-TS/Daily/data/hourly_breakout_state.json', 'r') as f:
        data = json.load(f)
        print(f'   Total tracked: {len(data.get(\"tracked_tickers\", {}))}')
        print(f'   Alerts sent today: {len(data.get(\"alerted_breakouts\", {}))}')
except:
    print('   Unable to read state file')
"
echo ""

# Check dashboards
echo "5. Dashboard Status:"
curl -s http://localhost:3005 > /dev/null 2>&1 && echo "   Port 3005: ✓ Running" || echo "   Port 3005: ✗ Not responding"
curl -s http://localhost:3006 > /dev/null 2>&1 && echo "   Port 3006: ✓ Running" || echo "   Port 3006: ✗ Not responding"
```

### Post-Market (3:30 PM - 4:00 PM)

#### Step 1: Verify Service Completion
```bash
# Check that first hour service has stopped (after 10:15 AM)
ps aux | grep first_hour | grep -v grep
# Should return nothing

# Check hourly service is still running
ps aux | grep hourly_breakout | grep -v grep
# Should show the process
```

#### Step 2: Review Daily Performance
```bash
# Count total alerts sent
grep "Alert sent" /Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_hourlybo/hourly_breakout_*.log | wc -l

# Review alert distribution
python3 -c "
import json
from datetime import datetime
with open('/Users/maverick/PycharmProjects/India-TS/Daily/data/hourly_breakout_state.json', 'r') as f:
    data = json.load(f)
    alerts = data.get('alerted_breakouts', {})
    print(f'Total unique tickers alerted: {len(alerts)}')
    for ticker, timestamp in sorted(alerts.items()):
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        print(f'  {ticker}: {dt.strftime(\"%I:%M %p\")}')"
```

## Troubleshooting Guide

### Common Issues & Solutions

#### 1. No Alerts Being Sent
```bash
# Check if tickers are being tracked
cat /Users/maverick/PycharmProjects/India-TS/Daily/data/hourly_breakout_state.json | jq '.tracked_tickers | length'

# If 0, check VSR scanner ran recently
ls -la /Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence.json

# Check Long Reversal scanner results
ls -la /Users/maverick/PycharmProjects/India-TS/Daily/results/Long_Reversal_Daily_*.xlsx | head -5
```

#### 2. Telegram Errors
```bash
# Test Telegram connectivity
python3 -c "
from utils.telegram_utils import TelegramBot
bot = TelegramBot()
bot.send_message('Test message from breakout alerts')"
```

#### 3. Service Won't Start
```bash
# Check plist syntax
plutil -lint ~/Library/LaunchAgents/com.india-ts.hourly-breakout-alerts.plist

# Check Python path
/Users/maverick/PycharmProjects/India-TS/.venv/bin/python --version

# Check for port conflicts
lsof -i :3005
lsof -i :3006
```

#### 4. Multiple Completion Messages (First Hour)
```bash
# Ensure KeepAlive is removed from plist
grep -A2 "KeepAlive" ~/Library/LaunchAgents/com.india-ts.first-hour-alerts.plist
# Should return nothing

# Force unload and reload
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.india-ts.first-hour-alerts.plist
```

## Quick Reference Commands

### Start Services
```bash
# Hourly Breakout
cd /Users/maverick/PycharmProjects/India-TS/Daily/alerts
./start_hourly_breakout_alerts.sh

# First Hour (if manual start needed)
./start_first_hour_alerts.sh
```

### Stop Services
```bash
# Hourly Breakout
./stop_hourly_breakout_alerts.sh

# First Hour
./stop_first_hour_alerts.sh
```

### View Dashboards
```bash
open http://localhost:3005  # Hourly breakout
open http://localhost:3006  # First hour
```

### Check Logs
```bash
# Today's hourly alerts
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_hourlybo/hourly_breakout_$(date +%Y%m%d)*.log

# Today's first hour alerts
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_firsthour/first_hour_$(date +%Y%m%d)*.log
```

## Quick Start Scripts

### One-Command Startup (All Breakout Services)

Create `/Users/maverick/PycharmProjects/India-TS/Daily/alerts/start_all_breakout_services.sh`:

```bash
#!/bin/bash

echo "Starting all breakout alert services..."

# 1. Check prerequisites
echo "Checking prerequisites..."
if ! launchctl list | grep -q "long_reversal_daily"; then
    echo "WARNING: Long Reversal scanner not running!"
fi

# 2. Run VSR scanner if needed
if [ ! -f "/Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence.json" ] || 
   [ $(find "/Users/maverick/PycharmProjects/India-TS/Daily/data/vsr_ticker_persistence.json" -mtime +1 | wc -l) -gt 0 ]; then
    echo "Running VSR scanner..."
    cd /Users/maverick/PycharmProjects/India-TS/Daily/scanners
    python3 VSR_Momentum_Scanner.py -u Sai
fi

# 3. Start hourly breakout service
echo "Starting hourly breakout service..."
cd /Users/maverick/PycharmProjects/India-TS/Daily/alerts
./start_hourly_breakout_alerts.sh

# 4. Load first hour service plist
echo "Loading first hour service..."
launchctl load ~/Library/LaunchAgents/com.india-ts.first-hour-alerts.plist 2>/dev/null

# 5. Open dashboards
echo "Opening dashboards..."
sleep 2
open http://localhost:3005
open http://localhost:3006

# 6. Run status check
sleep 3
./check_breakout_status.sh

echo "All breakout services started!"
```

Make it executable:
```bash
chmod +x /Users/maverick/PycharmProjects/India-TS/Daily/alerts/start_all_breakout_services.sh
```

## Service Dependencies Summary

1. **VSR Scanner** → Updates persistence file → **Hourly Breakout** reads VSR tickers
2. **Long Reversal Scanner** → Creates result files → **Hourly Breakout** reads high momentum tickers
3. **Hourly Breakout** → Updates state file → **First Hour** reads tracked tickers
4. **KiteConnect API** → Provides market data → Both services monitor prices
5. **Telegram Bot** → Sends notifications → Both services alert on breakouts

## Critical Success Factors

1. **VSR Persistence File** must be updated daily
2. **Long Reversal Scanner** must run before market open
3. **Hourly Breakout Service** must start before First Hour Service
4. **Telegram Bot Token** must be valid in config.ini
5. **KiteConnect Access Token** must be fresh (daily login)

---

Last Updated: 2025-08-04