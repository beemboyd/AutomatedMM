# VSR Enhanced Services Documentation

## Overview

The VSR (Volume-Supported Reversal) Enhanced Services provide continuous monitoring and tracking of tickers with momentum patterns. The system includes:

1. **Enhanced VSR Tracker Service** - Tracks tickers with 3-day persistence
2. **VSR Dashboard** - Web interface for viewing tracked tickers (port 3001)
3. **Automated Scheduling** - Runs from 9:15 AM to 3:30 PM IST daily

## Components

### 1. Enhanced VSR Tracker Service

**Script:** `Daily/services/vsr_tracker_service_enhanced.py`

**Features:**
- Tracks all tickers from Long_Reversal_Daily scanner results
- Maintains 3-day ticker persistence with momentum tracking
- Removes tickers with no positive momentum for 3 consecutive days
- Calculates VSR scores based on hourly data
- Updates every minute with real-time data
- Logs to: `Daily/logs/vsr_tracker/vsr_tracker_enhanced_YYYYMMDD.log`

**Persistence Data:**
- Stored in: `Daily/data/vsr_ticker_persistence.json`
- Tracks: first_seen, last_seen, days_tracked, momentum_history

### 2. VSR Dashboard

**Script:** `Daily/dashboards/vsr_tracker_dashboard.py`

**URL:** http://localhost:3001

**Features:**
- Real-time display of all tracked tickers
- Categories:
  - High Scores (≥50)
  - High VSR (≥1.0)
  - Positive Momentum
  - Strong Build (≥10)
  - 3-Day Leaders (persistence leaders)
  - New Entries
- Auto-refreshes every 60 seconds
- Displays: Score, VSR, Price, Volume, Momentum, Days Tracked

### 3. Scheduling System

**Plist Files:**
- `com.india-ts.vsr-tracker-enhanced.plist` - Starts tracker at 9:15 AM
- `com.india-ts.vsr-dashboard.plist` - Starts dashboard at 9:15 AM
- `com.india-ts.vsr-shutdown.plist` - Stops services at 3:30 PM

**Schedule:**
- Start: 9:15 AM IST (Mon-Fri)
- Stop: 3:30 PM IST (Mon-Fri)
- Updates: Every 60 seconds during market hours

## Installation

### 1. Load the plist files:
```bash
# Load VSR tracker
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.vsr-tracker-enhanced.plist

# Load dashboard
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.vsr-dashboard.plist

# Load shutdown scheduler
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.vsr-shutdown.plist
```

### 2. Manual Start (for testing):
```bash
# Start enhanced tracker
python Daily/services/vsr_tracker_service_enhanced.py --user Sai

# Start dashboard
python Daily/dashboards/vsr_tracker_dashboard.py

# View dashboard
open http://localhost:3001
```

## Monitoring

### Log Files:
- Enhanced tracker: `Daily/logs/vsr_tracker/vsr_tracker_enhanced_YYYYMMDD.log`
- Dashboard: `Daily/logs/vsr_tracker/vsr_dashboard.log`
- Service logs: `Daily/logs/vsr_tracker/vsr_enhanced_service.log`

### Check Service Status:
```bash
# Check if services are loaded
launchctl list | grep vsr

# View recent logs
tail -f Daily/logs/vsr_tracker/vsr_tracker_enhanced_$(date +%Y%m%d).log
```

### View Persistence Data:
```bash
# Check persistence data
python Daily/services/view_vsr_persistence.py

# View raw JSON
cat Daily/data/vsr_ticker_persistence.json | python -m json.tool
```

## Troubleshooting

### Dashboard shows 0 tickers:
- Check if enhanced tracker is running
- Verify log file exists: `vsr_tracker_enhanced_YYYYMMDD.log`
- Dashboard auto-detects enhanced vs basic log format

### Service won't start:
- Check Python path: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`
- Verify file permissions
- Check launchctl errors: `launchctl error com.india-ts.vsr-tracker-enhanced`

### Port 3001 already in use:
- Kill existing process: `lsof -ti:3001 | xargs kill -9`
- Or check what's using it: `lsof -i:3001`

## Technical Details

### VSR Score Calculation (0-100):
- VSR Ratio > 1.0: +20 points
- VSR Ratio > 2.0: +25 points
- VSR Ratio > 3.0: +15 points
- VSR ROC > 50: +15 points
- Volume Ratio > 1.5: +10 points
- Positive Momentum: +5 points
- Momentum Build: +10-20 points

### Persistence Rules:
- New tickers tracked for 3 days
- Requires positive momentum at least once to persist
- Removed if no positive momentum for 3 consecutive days
- Momentum history maintained for analysis

### Data Refresh:
- Minute data: 1-minute TTL cache
- Hourly data: 1-hour TTL cache
- Ensures real-time updates throughout the day

## Related Documentation
- VSR Momentum Scanner: `Daily/scanners/VSR_Momentum_Scanner.py`
- VSR Tracker Fix: `Daily/docs/VSR_TRACKER_REALTIME_FIX.md`
- Plist Management: `Daily/scheduler/PLIST_MASTER_SCHEDULE.md`