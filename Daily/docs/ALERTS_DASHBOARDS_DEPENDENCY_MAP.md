# India-TS Alerts & Dashboards Dependency Map

## Overview
This document provides a comprehensive dependency mapping for all alert services and dashboards in the India-TS system, helping with quick diagnosis and troubleshooting.

## Service Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          INDIA-TS ALERTS & DASHBOARDS                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  DATA SOURCES                    SERVICES                      OUTPUTS           │
│  ────────────                    ────────                      ───────           │
│                                                                                  │
│  ┌─────────────────┐            ┌─────────────────┐          ┌──────────────┐  │
│  │ VSR Scanner     │───────────▶│ VSR Tracker     │─────────▶│ Dashboard    │  │
│  │ (Hourly)        │            │ Enhanced        │          │ (Port 3001)  │  │
│  └─────────────────┘            └────────┬────────┘          └──────────────┘  │
│                                          │                                      │
│                                          ▼                                      │
│  ┌─────────────────┐            ┌─────────────────┐          ┌──────────────┐  │
│  │ Long Reversal   │───────────▶│ Hourly Tracker  │─────────▶│ Dashboard    │  │
│  │ Daily Scanner   │            │ Service         │          │ (Port 3002)  │  │
│  └─────────────────┘            └────────┬────────┘          └──────────────┘  │
│                                          │                                      │
│                                          ▼                                      │
│  ┌─────────────────┐            ┌─────────────────┐          ┌──────────────┐  │
│  │ Short Reversal  │───────────▶│ Short Momentum  │─────────▶│ Dashboard    │  │
│  │ Daily Scanner   │            │ Tracker         │          │ (Port 3003)  │  │
│  └─────────────────┘            └────────┬────────┘          └──────────────┘  │
│                                          │                                      │
│                                          ▼                                      │
│  ┌─────────────────┐            ┌─────────────────┐          ┌──────────────┐  │
│  │ Short Reversal  │───────────▶│ Hourly Short    │─────────▶│ Dashboard    │  │
│  │ Hourly Scanner  │            │ Tracker         │          │ (Port 3004)  │  │
│  └─────────────────┘            └────────┬────────┘          └──────────────┘  │
│                                          │                                      │
│                                          ▼                                      │
│                                  ┌─────────────────┐                           │
│                                  │ VSR Telegram    │          ┌──────────────┐  │
│                                  │ Enhanced        │─────────▶│ Telegram     │  │
│                                  │ Service         │          │ Channel      │  │
│                                  └─────────────────┘          └──────────────┘  │
│                                                                                  │
│  ┌─────────────────┐            ┌─────────────────┐          ┌──────────────┐  │
│  │ Market Data     │───────────▶│ Hourly Breakout │─────────▶│ Dashboard    │  │
│  │ (KiteConnect)   │            │ Alert Service   │          │ (Port 3005)  │  │
│  └─────────────────┘            └────────┬────────┘          └──────────────┘  │
│                                          │                                      │
│                                          ▼                                      │
│                                  ┌─────────────────┐          ┌──────────────┐  │
│                                  │ First Hour      │─────────▶│ Dashboard    │  │
│                                  │ Breakout        │          │ (Port 3006)  │  │
│                                  └─────────────────┘          └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Service Dependencies Matrix

| Service | Depends On | Data Sources | Persistence Files | Dashboard Port | Telegram Alerts |
|---------|------------|--------------|-------------------|----------------|-----------------|
| VSR Tracker Enhanced | VSR Scanner | `scanners/Hourly/VSR_*.xlsx` | `data/vsr_ticker_persistence.json` | 3001 | Yes (Enhanced) |
| Hourly Tracker | Long Reversal Hourly | `results-h/Long_Reversal_Hourly_*.xlsx` | `data/vsr_ticker_persistence_hourly_long.json` | 3002 | Via Breakout Service |
| Short Momentum Tracker | Short Reversal Daily | `results-s/Short_Reversal_Daily_*.xlsx` | `data/short_momentum/latest_short_momentum.json` | 3003 | Yes |
| Hourly Short Tracker | Short Reversal Hourly | `results-s-h/Short_Reversal_Hourly_*.xlsx` | `data/short_momentum/vsr_ticker_persistence_hourly_short.json` | 3004 | Yes |
| Hourly Breakout Alert | VSR + Long Reversal | Multiple sources | `data/hourly_breakout_state.json` | 3005 | Yes |
| First Hour Breakout | Hourly Breakout State | Live market data | `data/first_hour_state.json` | 3006 | Yes |

## Alert Configuration Locations

### 1. Global Telegram Configuration
**File**: `/Users/maverick/PycharmProjects/India-TS/Daily/config.ini`

```ini
[TELEGRAM]
enabled = yes/no                      # Master switch for all Telegram alerts
hourly_telegram_on = yes/no          # Hourly VSR alerts
daily_telegram_on = yes/no           # Daily VSR alerts
enable_short_alerts = yes/no         # Short-side alerts (NEW)
```

### 2. Service-Specific Alert Controls

#### VSR Telegram Enhanced Service
- **Config Section**: `[TELEGRAM]` in config.ini
- **Control Parameters**:
  - `hourly_telegram_on`: Controls hourly VSR alerts
  - `daily_telegram_on`: Controls daily VSR alerts
  - `enable_short_alerts`: Filters out SHORT signals when set to 'no'

#### Hourly Breakout Alerts
- **Config Section**: `[HOURLY_BREAKOUT]` in config.ini
- **Control Parameters**:
  - `enabled`: Master switch for hourly breakout alerts
  - `breakout_threshold_pct`: Minimum % move to trigger alert

#### First Hour Breakout Alerts
- **Config Section**: `[FIRST_HOUR]` in config.ini
- **Control Parameters**:
  - `enabled`: Master switch for first hour alerts
  - `breakout_threshold_pct`: Minimum % move to trigger alert

## Service Control Commands

### Quick Disable Commands

```bash
# Disable ALL Telegram alerts (master switch)
# Edit config.ini: [TELEGRAM] enabled = no
# Then restart VSR Telegram service:
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist

# Disable only hourly VSR alerts
# Edit config.ini: [TELEGRAM] hourly_telegram_on = no
# Restart VSR Telegram service (same commands as above)

# Disable only short-side alerts
# Edit config.ini: [TELEGRAM] enable_short_alerts = no
# Restart VSR Telegram service (same commands as above)

# Stop specific services
launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly-short-tracker-service.plist
launchctl unload ~/Library/LaunchAgents/com.india-ts.short-reversal-hourly.plist
launchctl unload ~/Library/LaunchAgents/com.india-ts.short-momentum-tracker.plist
```

### Service Management by Type

#### Long-Side Services
```bash
# Scanners
com.india-ts.long_reversal_daily
com.india-ts.long-reversal-hourly

# Trackers
com.india-ts.vsr-tracker-enhanced
com.india-ts.hourly-tracker-service

# Alerts
com.india-ts.hourly-breakout-alerts
com.india-ts.first-hour-alerts
```

#### Short-Side Services
```bash
# Scanners
com.india-ts.short_reversal_daily
com.india-ts.short-reversal-hourly

# Trackers
com.india-ts.short-momentum-tracker
com.india-ts.hourly-short-tracker-service

# Dashboards (no alerts)
com.india-ts.short-momentum-dashboard
com.india-ts.hourly-short-tracker-dashboard
```

## Troubleshooting Decision Tree

### Problem: Receiving unwanted alerts

1. **Identify alert type from message**:
   - "🔥 HIGH MOMENTUM" → VSR Telegram Enhanced
   - "🚨 HOURLY BREAKOUT" → Hourly Breakout Service
   - "🚨 HOURLY SHORT ALERT" → Hourly Short Tracker
   - "⚡ 5-MIN BREAKOUT" → First Hour Service

2. **Disable specific alert type**:
   - For VSR alerts: Edit config.ini `[TELEGRAM]` section
   - For breakout alerts: Edit config.ini `[HOURLY_BREAKOUT]` or `[FIRST_HOUR]`
   - For short alerts: Stop short tracker services or set `enable_short_alerts = no`

### Problem: Dashboard shows no data

1. **Check scanner has run**:
   ```bash
   # For VSR Dashboard (3001)
   ls -la Daily/scanners/Hourly/VSR_*$(date +%Y%m%d)*.xlsx
   
   # For Hourly Tracker (3002)
   ls -la Daily/results-h/Long_Reversal_Hourly_*$(date +%Y%m%d)*.xlsx
   
   # For Short Momentum (3003)
   ls -la Daily/results-s/Short_Reversal_Daily_*$(date +%Y%m%d)*.xlsx
   ```

2. **Check persistence files**:
   ```bash
   # Look for stale data or corruption
   ls -la Daily/data/vsr_ticker_persistence*.json
   ls -la Daily/data/short_momentum/*.json
   
   # If corrupted, backup and reset:
   mv file.json file.json.backup_$(date +%Y%m%d)
   echo "{}" > file.json
   ```

3. **Restart tracker service**:
   ```bash
   # Find the appropriate service for the dashboard port
   # Use the Service Dependencies Matrix above
   ```

## Quick Status Check Script

```bash
#!/bin/bash
# save as: check_alerts_status.sh

echo "=== India-TS Alerts & Dashboards Status ==="
echo ""
echo "1. Configuration Status:"
grep -E "enabled|hourly_telegram_on|daily_telegram_on|enable_short_alerts" /Users/maverick/PycharmProjects/India-TS/Daily/config.ini | grep -A4 "[TELEGRAM]"
echo ""

echo "2. Running Services:"
launchctl list | grep com.india-ts | grep -v "^-" | awk '{print $3 " (PID: " $1 ")"}'
echo ""

echo "3. Dashboard Status:"
for port in 3001 3002 3003 3004 3005 3006; do
    curl -s http://localhost:$port > /dev/null 2>&1 && echo "Port $port: ✓ Running" || echo "Port $port: ✗ Not responding"
done
echo ""

echo "4. Recent Scanner Runs:"
echo "VSR: $(ls -la Daily/scanners/Hourly/VSR_*$(date +%Y%m%d)*.xlsx 2>/dev/null | wc -l) files today"
echo "Long Hourly: $(ls -la Daily/results-h/*$(date +%Y%m%d)*.xlsx 2>/dev/null | wc -l) files today"
echo "Short Daily: $(ls -la Daily/results-s/*$(date +%Y%m%d)*.xlsx 2>/dev/null | wc -l) files today"
echo "Short Hourly: $(ls -la Daily/results-s-h/*$(date +%Y%m%d)*.xlsx 2>/dev/null | wc -l) files today"
```

## Service Start Order (Critical)

1. **Data Generation Layer** (8:30 AM - 9:00 AM):
   - Scanners (VSR, Reversal scanners)
   - Must run before trackers

2. **Tracking Layer** (8:45 AM - 9:00 AM):
   - Tracker services (read scanner outputs)
   - Update persistence files
   - Must run before alert services

3. **Alert Layer** (9:00 AM):
   - VSR Telegram Enhanced
   - Breakout alert services
   - Read from tracker persistence files

4. **Dashboard Layer** (Anytime):
   - Can start anytime
   - Read-only from persistence files
   - No dependencies on alert services

## Common Issues & Solutions

### Issue: "KeyError: 'last_updated'" in logs
**Cause**: Persistence file has stale/corrupted data
**Solution**: Reset persistence file (see Troubleshooting section)

### Issue: Multiple duplicate alerts
**Cause**: Multiple instances of service running
**Solution**: 
```bash
pkill -f "service_name"
launchctl unload plist_file
launchctl load plist_file
```

### Issue: Alerts for wrong signal type (e.g., getting SHORT when only want LONG)
**Cause**: Missing configuration for signal filtering
**Solution**: Set `enable_short_alerts = no` in config.ini and restart VSR Telegram service

---

Last Updated: 2025-08-05