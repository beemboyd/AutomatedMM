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

### 2025-07-29 21:16 IST - [Claude]
**Changes:**
- Fixed SMA breadth historical update job that was not running correctly after market hours
- Issue: Wrong script (sma_breadth_historical_collector.py) was running instead of append_historical_breadth.py
- Enhanced append_historical_breadth.py to trigger dashboard refresh after data update
- Added refresh calls to dashboards on ports 8080 and 5001
- Added automatic run of incremental collector after historical update
- Updated PLIST_MASTER_SCHEDULE.md to include sma_breadth_historical_update job

**Impact:**
- Daily breadth data will now update correctly at 6:30 PM
- Dashboards will automatically refresh to show latest data
- Plist correctly configured to run append_historical_breadth.py
- No manual intervention needed for daily updates
- Files updated: /Daily/Market_Regime/append_historical_breadth.py, /Daily/scheduler/PLIST_MASTER_SCHEDULE.md

---

### 2025-07-29 21:25 IST - [Claude]
**Changes:**
- Fixed dashboard at port 8080 not loading chart content due to data format inconsistency
- Issue: Incremental collector was adding data without `total_stocks` and `volume_breadth` fields
- Modified dashboard_enhanced.py to handle missing fields gracefully with safe defaults
- Updated append_historical_breadth.py to ensure proper data format with all required fields
- Added default values: total_stocks=500, empty volume_breadth object if missing

**Impact:**
- Dashboard charts now load correctly with historical data
- API endpoints return data without errors
- Future data updates will include all required fields
- No data loss - existing data still works with safe defaults
- Files updated: /Daily/Market_Regime/dashboard_enhanced.py, /Daily/Market_Regime/append_historical_breadth.py

---

### 2025-07-29 16:00 IST - [Claude]
**Changes:**
- Created comprehensive dashboard management system for all 6 dashboards
- Created dashboard_manager.py to control all dashboards centrally
- Added plists to start dashboards at 8 AM IST and stop at 8 PM IST
- Implemented refresh control mechanism for market-hours dashboards (3001, 5001, 3003) to stop refreshing after 3:30 PM
- Created manage_all_dashboards.sh utility script for manual control
- Added dashboard_refresh_controller.py and wrapper for refresh control

**Impact:**
- All dashboards now run on schedule: 8 AM - 8 PM IST daily
- Dashboards on ports 3001 (VSR), 3003 (Short Momentum), 5001 (Market Breadth) stop data refresh after 3:30 PM
- Dashboards on ports 7080 (Health), 8080 (Market Regime), 9090 (Job Manager) continue refreshing till 8 PM
- Files created:
  - /Daily/scheduler/dashboard_manager.py
  - /Daily/scheduler/plists/com.india-ts.dashboard_manager_start.plist
  - /Daily/scheduler/plists/com.india-ts.dashboard_manager_stop.plist
  - /Daily/scheduler/plists/com.india-ts.dashboard_refresh_control.plist
  - /Daily/scheduler/plists/com.india-ts.job_manager_dashboard.plist
  - /Daily/utils/manage_all_dashboards.sh
  - /Daily/utils/dashboard_refresh_controller.py
  - /Daily/utils/dashboard_refresh_wrapper.py

---

### 2025-07-29 16:30 IST - [Claude]
**Changes:**
- Created Telegram integration for VSR service to send high momentum alerts
- Added Telegram configuration section to config.ini with ZTTrending bot token
- Created telegram_notifier.py with rate limiting and cooldown features
- Extended VSR service with vsr_telegram_service.py for momentum alerts
- Added helper scripts for setup and chat ID retrieval
- Integrated config.ini reading for all Telegram settings

**Impact:**
- VSR service can now send real-time alerts via Telegram for high momentum tickers
- Configurable thresholds: momentum >= 10%, score >= 60
- Rate limiting: max 20 alerts/hour, 100 alerts/day
- Cooldown: 1 hour per ticker to prevent spam
- Files created:
  - /Daily/Alerts/telegram_notifier.py
  - /Daily/Alerts/vsr_telegram_service.py
  - /Daily/Alerts/telegram_config.py
  - /Daily/Alerts/get_telegram_chat_id.py
  - /Daily/Alerts/start_vsr_telegram_alerts.sh
  - /Daily/Alerts/TELEGRAM_SETUP_GUIDE.md
- Updated config.ini with TELEGRAM section

---

### 2025-07-29 17:00 IST - [Claude]
**Changes:**
- Updated start_vsr_telegram_alerts.sh to read chat_id from config.ini instead of environment variables
- Confirmed Telegram bot is properly configured and responding to API calls
- Bot token verified working: receiving empty updates array indicates successful connection

**Impact:**
- VSR Telegram service now fully integrated with config.ini
- No need for environment variables - all configuration in one place
- Ready to receive chat_id and begin sending alerts
- User needs to message the bot and run get_telegram_chat_id.py to obtain chat_id

---

### 2025-07-29 20:53 IST - [Claude]
**Changes:**
- Updated job_manager_dashboard.py to run from 8 AM to 8 PM IST (previously 9 AM to 4 PM)
- Started all 6 dashboards successfully
- Fixed dashboard startup issues by directly launching each dashboard
- Enabled refresh control for all dashboards

**Impact:**
- All dashboards now operational on extended hours (8 AM - 8 PM IST)
- Dashboard ports confirmed running:
  - 3001: VSR Tracker Dashboard
  - 3003: Short Momentum Dashboard
  - 5001: Market Breadth Dashboard
  - 7080: Health Check Dashboard
  - 8080: Market Regime Enhanced Dashboard
  - 9090: Job Manager Dashboard
- Refresh control system activated for post-market hours management
- Market-hours dashboards (3001, 5001, 3003) will stop refreshing after 3:30 PM IST

---

### 2025-07-29 22:30 IST - [Claude]
**Changes:**
- Added volume breadth charts to Market Regime Enhanced Dashboard (port 8080)
- Created two new visual components: Volume Breadth History and Volume Participation Rate charts
- Updated API endpoint to serve volume breadth data from historical JSON
- Verified scheduled job for daily historical breadth updates (runs at 6:30 PM IST)
- Created comprehensive update script for historical breadth data

**Impact:**
- Dashboard now displays complete market internals: price breadth (SMA20/50) and volume breadth
- Volume charts show percentage of stocks above average volume and participation rate
- Automated daily updates via com.india-ts.sma_breadth_historical_update.plist
- One-time calculation with incremental daily updates after market hours
- Files created/updated:
  - /Daily/Market_Regime/dashboard_enhanced.py (added volume charts)
  - /Daily/Market_Regime/update_historical_breadth_comprehensive.py (new script)
  - /Daily/scheduler/plists/com.india-ts.sma_breadth_historical_update.plist (updated path)

---

### 2025-07-29 23:00 IST - [Claude]
**Changes:**
- Fixed Volume Participation Rate chart display issue on Market Regime Enhanced Dashboard (port 8080)
- Changed data processing to multiply volume_participation values by 100 for proper percentage display
- Updated Y-axis scale from 0-1 to 0-100 with percentage labels
- Updated tooltip to show participation rate as percentage
- Identified that sma_breadth_incremental_collector.py handles daily updates to sma_breadth_historical_latest.json

**Impact:**
- Volume Participation Rate chart now properly displays data (was showing blank due to tiny decimal values)
- Chart now shows meaningful percentage values (e.g., 24% instead of 0.24)
- No dashboard restart required - changes apply on next page refresh
- Confirmed data flow: incremental collector updates → JSON file → dashboards read and display

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

### 2025-07-30 00:15 IST - [Claude]
**Changes:**
- Created plists for VSR Telegram Alert Service
- com.india-ts.vsr-telegram-alerts.plist - starts service at 9:07 AM
- com.india-ts.vsr-telegram-shutdown.plist - stops service at 3:30 PM
- Updated Jobs dashboard to include VSR Telegram service entries
- Updated PLIST_MASTER_SCHEDULE.md documentation

**Impact:**
- VSR Telegram alerts now automatically start at 9:07 AM on weekdays
- Service checks every 60 seconds for high-scoring VSR tickers
- Sends alerts when: score >= 60 and momentum >= 1.0%
- Service automatically stops at 3:30 PM after market close
- Logs stored in: /Daily/logs/vsr_telegram/
- Total India-TS scheduled jobs increased from 30 to 32

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

### 2025-07-30 03:13 IST - [Claude]
**Changes:**
- Restarted VSR Tracker Dashboard on port 3001 with network access
- Restarted Short Momentum Dashboard on port 3003 with network access
- Launched SL Watchdog Log Viewer Dashboard on port 2001 with network access
- All dashboards configured with host='0.0.0.0' for network accessibility

**Impact:**
- VSR Dashboard running on http://0.0.0.0:3001 (accessible from network)
- Short Momentum Dashboard running on http://0.0.0.0:3003 (accessible from network)
- SL Watchdog Dashboard running on http://0.0.0.0:2001 (accessible from network)
- All dashboards accessible from any device on the same network
- Process IDs: VSR (32732), Short Momentum (32728), SL Watchdog (33883)

---

### 2025-07-30 03:30 IST - [Claude]
**Changes:**
- Created Long_Reversal_Hourly.py and Short_Reversal_Hourly.py scanners by cloning daily versions
- Modified hourly scanners to output to results-h and results-s-h directories
- Disabled HTML generation in hourly scanners (xlsx output only)
- Created plists for both scanners to run every 30 minutes from 9:30 AM to 3:30 PM
- Updated job manager dashboard and PLIST_MASTER_SCHEDULE.md

**Impact:**
- Two new automated scanners running every 30 minutes during market hours
- Long_Reversal_Hourly outputs to Daily/results-h/
- Short_Reversal_Hourly outputs to Daily/results-s-h/
- Both scanners produce xlsx files only (no HTML reports)
- Total India-TS scheduled jobs increased from 32 to 34
- Files created:
  - /Daily/scanners/Long_Reversal_Hourly.py
  - /Daily/scanners/Short_Reversal_Hourly.py
  - /Daily/scheduler/plists/com.india-ts.long-reversal-hourly.plist
  - /Daily/scheduler/plists/com.india-ts.short-reversal-hourly.plist

---
