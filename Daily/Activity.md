# India-TS Activity Log

This file maintains a chronological record of all changes made to the India-TS system.
Each entry should include: Date, Time, Author, Changes Made, and Impact.

## Format
```
### YYYY-MM-DD HH:MM IST - [Author]
**Changes:**
- Description of changes

**Impact:**
- Systems/services affected
- Any configuration updates
- Testing performed

---
```

## Activity Log

### 2025-07-29 15:15 IST - [Claude]
**Changes:**
- Verified market regime dashboards (ports 5001 and 8080) are correctly configured to use sma_breadth_historical_latest.json
- Created append_historical_breadth.py script to append incremental daily breadth data to historical file
- Script runs after market hours to update the 7-month historical data with latest day's data
- Maintains rolling 210-day window and creates timestamped backups

**Impact:**
- Market breadth charts on both dashboards now display 7 months of historical data
- Daily updates can be automated via scheduler after market close
- File paths: /Daily/Market_Regime/append_historical_breadth.py
- No changes needed to existing dashboard code

---

### 2025-07-29 15:30 IST - [Claude]
**Changes:**
- Updated market regime dashboards to dynamically display correct stock count instead of hardcoded "176 stocks tracked"
- Modified dashboard_enhanced.py (port 8080) to show dynamic stock count from data
- Modified sma_breadth_dashboard_integration.py template to show dynamic stock count
- Stock count now updates from sma_breadth_historical_latest.json (currently showing 564 stocks)

**Impact:**
- Both dashboards now display accurate stock count from actual data
- No dashboard restart required - changes are in JavaScript that loads dynamically
- Files updated: /Daily/Market_Regime/dashboard_enhanced.py, /Daily/Market_Regime/sma_breadth_dashboard_integration.py

---

### 2025-07-23 14:50 IST - [System]
**Changes:**
- Implemented Git-based plist management system
- Created backup of all India-TS plists in Daily/scheduler/plists/
- Added install_plists.py and validate_plists.py scripts
- Updated PLIST_MASTER_SCHEDULE.md documentation

**Impact:**
- Prevents accidental cross-project plist contamination
- All India-TS plists now have versioned backups
- Easier recovery from plist corruption or accidental changes

---

### 2025-07-23 09:28 IST - [System]
**Changes:**
- Added FNO Liquid reversal scanner plist (com.india-ts.fno_liquid_reversal_scanners)
- Configured to run on hourly schedule

**Impact:**
- New automated scanner for FNO liquid stocks
- Integrated with existing reversal scanning infrastructure

---

### 2025-07-25 03:35 IST - [Claude/System]
**Changes:**
- Updated job_manager_dashboard.py to fix PID column visibility issue
- Added horizontal scrolling to tables (overflow-x: auto)
- Reduced font sizes and padding for better space utilization
- Added minimum table width of 900px
- Updated VSR job entries in JOBS dictionary

**Impact:**
- PID column now visible in job manager dashboard
- Added VSR jobs: vsr-tracker-enhanced, vsr-dashboard, vsr-shutdown
- Better table layout with horizontal scrolling when needed
- VSR dashboard available on port 3001

---

### 2025-07-25 09:07 IST - [Claude/System]
**Changes:**
- Updated job_manager_dashboard.py time restrictions
- Changed from 9:30 AM - 3:30 PM to 9:00 AM - 4:00 PM IST
- Updated all error messages to reflect new time range

**Impact:**
- Job manager dashboard now accessible from 9:00 AM to 4:00 PM IST
- Provides 30 minutes earlier access and 30 minutes later access
- Better accommodates pre-market and post-market activities

---

### 2025-07-25 09:11 IST - [Claude/System]
**Changes:**
- Verified Long_Reversal_Daily and Short_Reversal_Daily scanner execution
- Both scanners ran successfully at 9:09 AM today
- Note: Plists show Monday-only schedule but scanners ran on Friday

**Impact:**
- Long_Reversal_Daily created output at 09:09:19 AM
- Short_Reversal_Daily created output at 09:09:25 AM
- May need to investigate scheduling discrepancy

---

### 2025-07-25 09:23 IST - [Claude/System]
**Changes:**
- Investigated VSR Enhanced Tracker not auto-starting at 9:15 AM
- Manually loaded and started VSR Enhanced Tracker service
- Verified all VSR components are now operational

**Impact:**
- VSR Enhanced Tracker now running (PID: 50103)
- VSR Dashboard accessible at http://localhost:3001
- Currently tracking top performers: BAJFINANCE, ICICIBANK, RECLTD
- Service will run until scheduled shutdown at 3:30 PM

---

### 2025-07-25 10:12 IST - [Claude/System]
**Changes:**
- Created new Short Momentum Tracker service and dashboard
- Tracks short-side scanner outputs from past 3 days
- Identifies tickers with negative momentum
- Created plists for both services

**Impact:**
- Short Momentum Tracker service: tracks and persists short opportunities
- Short Momentum Dashboard: accessible at http://localhost:3003
- Both services scheduled to start at 9:15 AM daily
- Plists backed up to Daily/scheduler/plists/

---
