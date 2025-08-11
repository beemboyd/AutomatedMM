# Dashboard Dependencies and Data Flow

## Overview
This document details the data dependencies for all India-TS dashboards and the critical timing requirements for proper operation.

## Dashboard Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Pre-Market Setup (9:00 AM)              │
│  - Restart all tracker services (CRITICAL)                  │
│  - Services must use today's date for log files             │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│                        Data Sources                          │
├───────────────────────────┬─────────────────────────────────┤
│   Scanner Files (.xlsx)   │    Tracker Services (logs)      │
└───────────────────────────┴─────────────────────────────────┘
             │                              │
             ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Dashboards                            │
├──────────┬──────────┬──────────┬───────────┬────────────────┤
│VSR (3001)│Hour(3002)│Short(3003)│H-Short(3004)│Regime(8080)  │
└──────────┴──────────┴──────────┴───────────┴────────────────┘
```

## Dashboard Details

### 1. VSR Dashboard (Port 3001)
**Service**: `com.india-ts.vsr-tracker-enhanced`
**Data Source**: 
- Primary: `/Daily/scanners/Hourly/VSR_*.xlsx`
- Secondary: `/Daily/data/vsr_ticker_persistence.json`
**Tracker Service**: VSR_Tracker_Enhanced.py
**Critical Requirement**: Service restart at 9:00 AM

### 2. Hourly Tracker Dashboard (Port 3002)
**Service**: `com.india-ts.hourly-tracker-service`
**Data Source**: 
- Primary: `/Daily/results-h/Long_Reversal_Hourly_*.xlsx`
- Log File: `/Daily/logs/hourly_tracker/hourly_tracker_YYYYMMDD.log`
**Tracker Service**: hourly_tracker_service_fixed.py
**Critical Requirement**: 
- Service MUST restart daily or log file uses wrong date
- Dashboard reads from date-specific log file

### 3. Short Momentum Dashboard (Port 3003)
**Service**: `com.india-ts.short-momentum-tracker`
**Data Source**: 
- Primary: `/Daily/results-s/Short_Reversal_Daily_*.xlsx`
- Secondary: `/Daily/data/short_momentum/latest_short_momentum.json`
**Tracker Service**: short_momentum_tracker_service.py
**Critical Requirement**: Service restart at 9:00 AM

### 4. Hourly Short Dashboard (Port 3004)
**Service**: `com.india-ts.hourly-short-tracker-service`
**Data Source**: 
- Primary: `/Daily/results-s-h/Short_Reversal_Hourly_*.xlsx`
- Log File: `/Daily/logs/hourly_short_tracker/short_tracker_YYYYMMDD.log`
**Tracker Service**: hourly_short_tracker_service.py
**Critical Requirement**: Service restart at 9:00 AM

### 5. Market Regime Dashboard (Port 8080)
**Service**: `com.india-ts.market-regime-dashboard`
**Data Source**: 
- Primary: `/Daily/Market_Regime/regime_analysis/latest_regime_summary.json`
- Long Reversals: `/Daily/results/Long_Reversal_Daily_*.xlsx`
- Short Reversals: `/Daily/results-s/Short_Reversal_Daily_*.xlsx`
- Index Data: Real-time Zerodha API
- **PCR Data**: Real-time NIFTY option chain from Zerodha API
**Components**:
- Market Regime Analyzer: market_regime_analyzer.py
- PCR Analyzer: pcr_analyzer.py
- Dashboard: dashboard_enhanced.py
**Features**:
- Real-time market regime classification
- Put-Call Ratio (PCR) analysis with 20% weightage
- Multi-timeframe analysis
- Index SMA20 tracking
- Position recommendations based on regime
**PCR Integration**:
- Fetches NIFTY option chain data every 30 minutes
- Calculates PCR (OI) and PCR (Volume)
- Combined PCR = 70% OI + 30% Volume
- Contrarian interpretation (High PCR = Bullish signal)
**Critical Requirement**: Zerodha API access for real-time data

## Data Flow Sequence

### Morning Startup (9:00 AM)
1. **Restart Tracker Services** ← CRITICAL STEP
   - Forces services to use today's date for log files
   - Clears stale state from previous day
   
2. **Run Scanners**
   - Long_Reversal_Daily.py → results/*.xlsx
   - Short_Reversal_Daily.py → results-s/*.xlsx
   - VSR_Momentum_Scanner.py → scanners/Hourly/*.xlsx
   
3. **Tracker Services Process Data**
   - Read scanner output files
   - Write to date-specific log files
   - Update persistence JSON files
   
4. **Dashboards Read Data**
   - Look for today's date in log filenames
   - Parse JSON and Excel files
   - Display real-time updates via API

## Common Issues and Root Causes

### Issue: Dashboard Shows No Data
**Root Cause**: Tracker service using previous day's date
**Example**: 
- Service writes to: `hourly_tracker_20250806.log`
- Dashboard looks for: `hourly_tracker_20250807.log`
**Solution**: Restart tracker service to use current date

### Issue: Stale Data in Dashboard
**Root Cause**: Service not restarted since previous day
**Solution**: Run pre_market_setup.sh which includes service restarts

### Issue: API Returns Empty Response
**Root Cause**: Missing or incorrectly formatted persistence file
**Solution**: Check JSON format in persistence files

## Date Format Requirements

### Log Files
Format: `service_name_YYYYMMDD.log`
Example: `hourly_tracker_20250807.log`

### Persistence Files
Date field format: `YYYY-MM-DD HH:MM:SS`
Example: `"last_updated": "2025-08-07 10:30:00"`

### Scanner Output Files
Format: `Scanner_Name_YYYYMMDD_HHMMSS.xlsx`
Example: `VSR_20250807_093022.xlsx`

## Service Restart Commands

### Individual Service Restart
```bash
# Hourly Tracker (Port 3002)
launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist

# Short Momentum (Port 3003)
launchctl unload ~/Library/LaunchAgents/com.india-ts.short-momentum-tracker.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.short-momentum-tracker.plist

# Hourly Short (Port 3004)
launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly-short-tracker-service.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-short-tracker-service.plist

# VSR Tracker (Port 3001)
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-tracker-enhanced.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-tracker-enhanced.plist

# Market Regime Dashboard (Port 8080)
# Manual restart (not a launchctl service)
pkill -f "dashboard_enhanced.py"
cd /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime
nohup python3 dashboard_enhanced.py > /dev/null 2>&1 &
```

### Batch Restart (Recommended)
```bash
# Run pre-market setup which includes all restarts
./pre_market_setup.sh
```

## Monitoring and Verification

### Check Service Status
```bash
launchctl list | grep -E "hourly-tracker|short-momentum|vsr-tracker"
```

### Verify Log Files
```bash
ls -la /Users/maverick/PycharmProjects/India-TS/Daily/logs/hourly_tracker/*$(date +%Y%m%d)*
```

### Test Dashboard APIs
```bash
# Port 3002
curl -s http://localhost:3002/api/trending-tickers | jq '.tickers | length'

# Port 3003
curl -s http://localhost:3003/api/tracked | jq '.tickers | length'

# Port 3004
curl -s http://localhost:3004/api/tracked | jq '.tickers | length'

# Port 3001
curl -s http://localhost:3001/api/tracked | jq '.tickers | length'
```

## Key Learnings

1. **Services don't auto-update date at midnight** - They continue using the date from when they started
2. **Dashboards are date-aware** - They look for today's date in log filenames
3. **Daily restart is mandatory** - Not optional for proper operation
4. **Pre-market setup is critical** - Must include service restarts, not just scanner runs
5. **Log file naming is strict** - Must match YYYYMMDD format exactly

## Recommended Daily Schedule

**9:00 AM**: Run pre_market_setup.sh
- Updates access token
- **Restarts all tracker services** (Step 2 - Critical)
- Runs VSR scanner
- Restarts alert services
- Starts hourly breakout alerts
- Verifies system status

**9:15 AM**: Market Opens
- All dashboards showing current data
- Services writing to correct log files
- Real-time tracking active

**3:30 PM**: Market Closes
- Services continue running (OK)
- Will need restart tomorrow morning

## Contact

For issues or questions about dashboard dependencies:
- Check Activity.md for recent changes
- Review this document for troubleshooting
- Verify services were restarted today