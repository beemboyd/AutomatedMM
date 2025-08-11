# Dashboard Data Refresh Issue - Root Cause Analysis & Solutions

## Issue Summary
Dashboards frequently show stale data from previous days, requiring manual intervention every morning.

## Affected Dashboards & Their Data Dependencies

### 1. Market Breadth Dashboard (Port 5001)
- **Data Source**: `breadth_data/market_breadth_latest.json` (symlink)
- **Issue**: Symlink points to old data files
- **Current State**: Points to files from previous trading days
- **Manual Fix Required**: Update symlink to latest market_breadth_YYYYMMDD_*.json

### 2. Hourly Tracker Dashboard (Port 3002)
- **Data Source**: `results-h/Long_Reversal_Hourly_*.xlsx`
- **Issue**: Service loads tickers but shows 0 tracked
- **Root Cause**: Persistence file contains old dates, service filters out "stale" tickers
- **Manual Fix Required**: Restart service to reset persistence

### 3. Hourly Short Tracker Dashboard (Port 3004)
- **Data Source**: `results-s-h/Short_Reversal_Hourly_*.xlsx`
- **Issue**: Similar to 3002, shows 0 tickers
- **Root Cause**: Same persistence file date mismatch issue
- **Manual Fix Required**: Restart service

### 4. VSR Dashboard (Port 3001)
- **Data Source**: `scanners/Hourly/VSR_*.xlsx`
- **Issue**: May show previous day's data
- **Root Cause**: VSR scanner needs to run after market open
- **Manual Fix Required**: Run VSR scanner manually

## Root Causes

### 1. No Automated Data Generation
- Market Breadth Scanner doesn't run automatically on weekends/pre-market
- VSR Scanner needs manual execution
- Scanners that run on schedule may not align with dashboard expectations

### 2. Static Symlinks
- `market_breadth_latest.json` doesn't auto-update to newest file
- No mechanism to detect and link to most recent data file

### 3. Date-Based Filtering in Services
- Services check if data is "current" based on date
- Weekend/holiday data gets filtered out as "stale"
- Persistence files retain old dates causing mismatches

### 4. Service Restart Requirements
- Services cache date at startup
- Don't automatically roll over to new date at midnight
- Continue writing to previous day's log files

## Solution Options

### Option 1: Pre-Market Automation Script (Recommended)
Create a comprehensive pre-market script that:
```bash
#!/bin/bash
# pre_market_data_refresh.sh

# 1. Generate fresh market breadth data
python3 scanners/Market_Breadth_Scanner.py -u Sai

# 2. Update symlinks to latest files
cd breadth_data
latest_file=$(ls -t market_breadth_*.json | head -1)
ln -sf $latest_file market_breadth_latest.json

# 3. Run VSR scanner
python3 scanners/VSR_Momentum_Scanner.py -u Sai

# 4. Restart all tracker services
launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist
# ... repeat for all services

# 5. Update historical breadth data
python3 Market_Regime/append_historical_breadth.py
```

Schedule this via launchctl to run at 8:45 AM IST daily.

### Option 2: Dynamic Symlink Updates
Modify dashboards to:
- Look for the most recent file directly instead of using symlinks
- Auto-detect latest data file based on timestamp
- Example code:
```python
import glob
import os

def get_latest_breadth_file():
    files = glob.glob('breadth_data/market_breadth_*.json')
    if files:
        return max(files, key=os.path.getmtime)
    return None
```

### Option 3: Service Intelligence
Enhance services to:
- Detect date changes and auto-refresh
- Handle weekend/holiday data gracefully
- Not filter out "previous day" data on weekends

### Option 4: Centralized Data Manager
Create a data management service that:
- Monitors for stale data
- Automatically generates fresh data when needed
- Updates all symlinks and dependencies
- Sends notifications when data is refreshed

## Immediate Actions

1. **Update pre_market_setup.sh** to include:
   - Market Breadth Scanner execution
   - Symlink updates
   - Historical breadth data update

2. **Create launchctl plist** for automated pre-market refresh:
   - Runs at 8:45 AM IST
   - Executes all data generation scripts
   - Restarts necessary services

3. **Modify service persistence logic** to:
   - Clear persistence on date change
   - Not filter weekend data as stale

## Long-term Recommendations

1. **Implement Option 1** as immediate fix
2. **Work towards Option 2** for robustness
3. **Consider Option 4** for enterprise-grade solution

## Testing Checklist

After implementing solution, verify:
- [ ] Market Breadth Dashboard shows current date
- [ ] Hourly trackers load tickers properly
- [ ] VSR Dashboard has fresh scan data
- [ ] Historical breadth includes latest data
- [ ] All services log to current date files

## Related Issues
- Services stuck on old log dates (resolved by restart)
- Persistence files with stale data
- Weekend data handling

## Files to Monitor
- `/Daily/Market_Regime/breadth_data/market_breadth_latest.json`
- `/Daily/data/vsr_ticker_persistence_hourly_long.json`
- `/Daily/data/short_momentum/vsr_ticker_persistence_hourly_short.json`
- `/Daily/logs/*/[service]_YYYYMMDD.log`

---
Created: 2025-08-11
Last Updated: 2025-08-11
Status: Active Issue - Requires Daily Manual Intervention