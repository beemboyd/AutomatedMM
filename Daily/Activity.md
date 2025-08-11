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

### 2025-08-11 13:22 IST - [Claude]
**Changes:**
- Created new VSR breakout trading script: place_orders_daily_long_vsr.py
- Integrated with VSR Dashboard API (http://localhost:3001/)
- Implemented hourly candlestick breakout strategy
- Added 1% portfolio position sizing with max 5 positions
- Created comprehensive documentation and flow diagrams

**Impact:**
- New automated trading capability based on VSR momentum signals
- Entry criteria: VSR score >= 60, positive momentum >= 2%
- Entry signal: Break above previous hourly candle high
- Risk management: 2% stop loss, 1% position size
- User controls: Interactive ticker selection and confirmation
- Ready for manual testing, future automation via cron/launchd
- Maximum portfolio exposure limited to 5%

**Files Created:**
- /Daily/trading/place_orders_daily_long_vsr.py - Main trading script
- /Daily/docs/VSR_BREAKOUT_TRADING.md - Comprehensive documentation
- /Daily/Diagrams/vsr_breakout_trading_flow.md - System flow diagrams

**Files Modified:**
- /Daily/docs/system/dependencies_analysis.md - Added new script dependencies

**Future Automation:**
- Schedule: 5 minutes after every hour (10:05, 11:05, 12:05, 13:05 IST)
- Days: Monday to Friday (weekdays only)
- Mode: Automated with --auto flag (to be implemented)

---

### 2025-08-11 12:16 IST - [Claude]
**Changes:**
- Enhanced VSR Telegram alert service to filter out negative momentum tickers
- Added automatic loading of short momentum tickers from multiple sources
- Implemented filtering logic to prevent high momentum alerts for tickers in short positions
- Added hourly refresh of negative momentum ticker list

**Impact:**
- Telegram notifications now exclude tickers that are in negative/short momentum
- Prevents conflicting signals where a ticker might appear in both long and short lists
- Loads negative momentum tickers from:
  - vsr_ticker_persistence_hourly_short.json (33 tickers loaded)
  - latest_short_momentum.json
  - Short_Reversal_Daily scanner results
- Filters applied to both hourly and daily high momentum alerts
- Automatic refresh every hour to keep list current

**Files Modified:**
- /Daily/alerts/vsr_telegram_service_enhanced.py - Added negative momentum filtering

---

### 2025-08-11 11:10 IST - [Claude]
**Changes:**
- Created VSR Efficiency Analyzer program (vsr_efficiency_analyzer.py)
- Generated efficiency analysis reports for last 10 business days
- Created new analysis/Efficiency folder for storing reports
- Implemented Excel report generation with naming convention: Eff_Analysis_{type}_{fromdate}_{todate}.xlsx

**Impact:**
- New capability to analyze VSR alert efficiency over time
- Generated reports for:
  - Long positions: 224 tickers tracked with alert frequency analysis
  - Short positions: 388 tickers tracked with alert frequency analysis
- Reports include: Ticker, First Alert Date/Time, First Price, Alert Count, Max Score, Avg Score
- Provides ability to analyze which tickers generate most alerts and track their effectiveness
- Can be scheduled to run periodically for ongoing efficiency monitoring

**Files Created:**
- /Daily/analysis/vsr_efficiency_analyzer.py - Main analyzer program
- /Daily/analysis/Efficiency/Eff_Analysis_long_20250811_20250729.xlsx
- /Daily/analysis/Efficiency/Eff_Analysis_short_20250811_20250729.xlsx

---

### 2025-08-11 09:37 IST - [Claude]
**Changes:**
- Documented root cause of recurring dashboard data refresh issues
- Created comprehensive analysis document: DASHBOARD_DATA_REFRESH_ISSUE.md
- Developed enhanced pre_market_data_refresh.sh script to automate all fixes
- Identified 4 root causes: no automated data generation, static symlinks, date filtering, service restart requirements

**Impact:**
- Clear understanding of why dashboards show stale data every morning
- Automated solution script that handles all refresh tasks:
  - Runs Market Breadth Scanner
  - Updates symlinks to latest files
  - Runs VSR Scanner
  - Updates historical breadth data
  - Clears persistence files
  - Restarts all tracker services
- Script can be scheduled via launchctl for 8:45 AM daily execution
- Permanent fix for recurring "dashboard shows old date" issue

**Root Causes Identified:**
1. Market Breadth Scanner doesn't run automatically pre-market
2. Symlinks don't auto-update to newest files
3. Services filter out "previous day" data on weekends
4. Services don't roll over to new date at midnight

---

### 2025-08-11 09:32 IST - [Claude]  
**Changes:**
- Ran Market Breadth Scanner to generate today's data (August 11)
- Updated symlink to point to market_breadth_20250811_091020.json
- Ran append_historical_breadth.py to include today in historical data
- Market Breadth Dashboard now shows August 11 data

**Impact:**
- Market Breadth Dashboard (5001) now displaying current date (8/11)
- SMA20: 32.26%, SMA50: 37.26% for August 11
- Historical breadth data includes today's entry
- Dashboard properly showing fresh market data

---

### 2025-08-11 09:02 IST - [Claude]
**Changes:**
- Fixed Market Breadth Dashboard (port 5001) not showing current data
- Updated symlink market_breadth_latest.json to point to August 8th data (was pointing to August 1st)
- Restarted Market Breadth Dashboard (PID: 12028)
- Dashboard now accessible and showing latest breadth data

**Impact:**
- Market Breadth Dashboard (5001) now showing data from August 8, 2025
- Symlink fixed: market_breadth_latest.json -> market_breadth_20250808_154058.json  
- Historical breadth data confirmed up to date through August 8th
- Dashboard properly refreshed and serving content

---

### 2025-08-11 08:55 IST - [Claude]
**Changes:**
- Executed pre-market setup routine for Sunday trading preparation
- Restarted all tracker services to ensure correct date logging (20250811):
  - VSR Tracker Enhanced service
  - Hourly tracker service (PID: 10617)
  - Hourly short tracker service (PID: 10674)
  - Short momentum tracker service (PID: 10684)
- Restarted VSR Telegram alerts enhanced service (PID: 10753)
- Started missing dashboards:
  - VSR Dashboard on port 3001 (PID: 10910)
  - Short Momentum Dashboard on port 3003 (PID: 10953)
- Ran VSR scanner successfully with Sai's credentials
- Restarted hourly breakout alert service

**Impact:**
- All services now logging to correct date files (20250811) instead of previous dates
- Fresh VSR scan data generated at 08:54 AM
- All 7 main dashboards operational:
  - Port 3001: VSR Dashboard ✓
  - Port 3002: Hourly Tracker Dashboard ✓
  - Port 3003: Short Momentum Dashboard ✓
  - Port 3004: Hourly Short Dashboard ✓
  - Port 3005: Hourly Breakout Dashboard ✓
  - Port 5001: Market Breadth Dashboard ✓
  - Port 8080: Market Regime Dashboard ✓
- System ready for market open with all services using current date
- Resolved repeat issue where services were stuck on old dates

**Services Verified:**
- All tracker services writing to logs/*/20250811.log files
- Telegram alerts operational and connected
- VSR persistence files updated
- System status check shows 6 scanner runs today

---

### 2025-08-08 20:01 IST - [Claude]
**Changes:**
- Removed Early Bird Opportunities section from Market Breadth Dashboard (port 5001)
- Commented out `/api/early-bird` endpoint in market_breadth_dashboard.py
- Commented out HTML display section and JavaScript functions in templates/market_breadth_dashboard.html
- Created archive documentation at Daily/Market_Regime/archive/early_bird_20250808/

**Impact:**
- Dashboard continues functioning normally without Early Bird section
- No data loss - KC Upper Limit results still being generated
- Feature can be restored by uncommenting archived code sections
- Sent HUP signal to dashboard process (PID 55035) to reload changes

**Findings:**
- Identified SMA breadth discrepancy: 16.9% is real-time intraday value, 33.6% is historical daily close value
- Both values are correct but represent different timeframes

---

### 2025-08-08 13:06 IST - [Claude]
**Changes:**
- Disabled Telegram alerts for hourly short and continuation trend (hourly breakout) alerts
- Modified config.ini: Set `enable_short_alerts = no` in TELEGRAM section
- Modified config.ini: Set `[HOURLY_BREAKOUT] enabled = no`
- Restarted services to pick up new configuration:
  - com.india-ts.hourly-short-tracker-service.plist
  - com.india-ts.short-momentum-tracker.plist
  - com.india-ts.vsr-telegram-alerts-enhanced.plist
  - com.india-ts.hourly-breakout-alerts.plist

**Impact:**
- System will NOT send Telegram alerts for short momentum signals from hourly short tracker service
- Continuation trend breakouts from hourly breakout alert service will NOT trigger alerts
- Services confirmed running with disabled alert configuration

---

### 2025-08-08 12:52 IST - [Claude]
**Changes:**
- Enabled Telegram alerts for hourly short and continuation trend (hourly breakout) alerts
- Modified config.ini: Set `enable_short_alerts = yes` in TELEGRAM section
- Verified `[HOURLY_BREAKOUT] enabled = yes` was already set
- Restarted services to pick up new configuration:
  - com.india-ts.hourly-short-tracker-service.plist
  - com.india-ts.short-momentum-tracker.plist
  - com.india-ts.vsr-telegram-alerts-enhanced.plist
  - com.india-ts.hourly-breakout-alerts.plist

**Impact:**
- System will now send Telegram alerts for short momentum signals from hourly short tracker service
- Continuation trend breakouts from hourly breakout alert service will trigger alerts
- All alerts will be sent to channel ID -1002690613302
- Services confirmed running with new configuration

---

### 2025-08-08 10:05 IST - [Claude]
**Changes:**
- Fixed hourly tracker services (ports 3002, 3004) not showing data due to persistence file issues
- Modified hourly_tracker_service_fixed.py and hourly_short_tracker_service.py to handle new persistence format
- Fixed date format mismatch (ISO format vs standard datetime) in persistence cleanup logic
- Completely reset persistence files to clear corrupted July 30 data
- Services now correctly tracking and displaying VSR scores

**Impact:**
- Hourly Tracker Dashboard (3002) now showing VSR scores for Long Reversal tickers
- Hourly Short Dashboard (3004) processing Short Reversal tickers
- Fixed persistence file format to include 'tickers' key and 'last_updated' timestamp
- Services properly logging VSR scores: KRBL (55), LICI (10), KAJARIACER (10), etc.
- Dashboards will now display real-time tracking data throughout the day

**Root Cause:**
- Old persistence data from July 30 kept being restored
- Date format mismatch between ISO format (2025-07-30T08:26:48) and expected format
- Missing 'last_updated' field at root level of persistence JSON

---

### 2025-08-08 09:40 IST - [Claude]
**Changes:**
- Fixed VSR tracker enhanced service not running and applied log file date fix
- Restarted com.india-ts.vsr-tracker-enhanced service (PID: 13027)
- Service now correctly logging to vsr_tracker_enhanced_20250808.log
- Applied same fix as documented on 2025-08-07 for date rollover issue

**Impact:**
- VSR tracker service now operational and logging to correct date file
- Service will track VSR momentum indicators throughout the day
- Dashboard on port 3001 will show real-time VSR data
- Fix ensures service uses current date for log files after pre-market restart

---

### 2025-08-07 10:35 IST - [Claude]
**Changes:**
- Fixed dashboard data display issues on ports 3002, 3003, 3004
- Identified root cause: Tracker services using previous day's date for log files
- Updated pre_market_setup.sh to include service restarts in Step 2
- Fixed date format in vsr_ticker_persistence_hourly_long.json
- Created missing log file hourly_tracker_20250807.log
- Documented optimal pre-market service restart schedule

**Impact:**
- All dashboards now display data correctly after service restart
- Pre-market setup script automatically handles service restarts
- Services will use correct date for log files going forward
- Dashboards read from properly dated log files

**Root Cause:**
- Tracker services don't automatically update date at midnight
- Services continue writing to previous day's log file
- Dashboards look for today's date in log filename
- Result: Dashboard shows no data despite services running

**Solution:**
- Restart all tracker services during pre-market (9:00 AM)
- This ensures log files use current date
- Added to pre_market_setup.sh for automation

---

### 2025-08-06 10:15 IST - [Claude]
**Changes:**
- Fixed and restarted dashboards on ports 3002, 3003, 3004
- Killed stale processes that were blocking these ports
- Started Hourly Tracker Dashboard (port 3002)
- Started Short Momentum Dashboard (port 3003)
- Started Hourly Short Tracker Dashboard (port 3004)
- Started corresponding tracker services

**Impact:**
- All 6 main dashboards now running and accessible
- Port 3001: VSR Dashboard
- Port 3002: Hourly Tracker Dashboard
- Port 3003: Short Momentum Dashboard
- Port 3004: Hourly Short Dashboard
- Port 3005: Hourly Breakout Dashboard
- Port 3006: First Hour Dashboard

**Services Started:**
- com.india-ts.hourly-short-tracker-service
- com.india-ts.short-momentum-tracker

---

### 2025-08-06 09:35 IST - [Claude]
**Changes:**
- Fixed VSR Telegram alert service errors
- Fixed AttributeError for missing base_dir in vsr_telegram_service_enhanced.py
- Fixed method name mismatch (run_monitoring_cycle -> run_tracking_cycle)
- Added missing check_high_momentum method
- Enabled hourly VSR alerts in config.ini

**Impact:**
- VSR Telegram alerts now working correctly
- Both hourly and daily VSR alerts enabled
- Service successfully processing 112 tickers
- Dashboard running on port 3001
- Telegram notifications being sent to channel -1002690613302

**Files Modified:**
- Daily/alerts/vsr_telegram_service_enhanced.py (fixed multiple errors)
- Daily/config.ini (enabled hourly_telegram_on)

**Services Restarted:**
- com.india-ts.vsr-telegram-alerts-enhanced (running PID: 11475)
- VSR Dashboard (already running PID: 65489)

---

### 2025-08-05 12:00 IST - [Claude]
**Changes:**
- Added market regime change Telegram alerts
- Created regime_change_notifier.py to monitor regime changes
- Integrated notifier into market_regime_analyzer.py
- Created comprehensive dependency map for market regime system

**Impact:**
- Users will receive Telegram alerts when market regime changes
- Alerts include regime transition, confidence, and current conditions
- Regime changes tracked in state file to prevent duplicate alerts
- Dashboard link included in alerts for quick access

**Files Created/Modified:**
- Daily/Market_Regime/regime_change_notifier.py (created)
- Daily/Market_Regime/market_regime_analyzer.py (modified)
- Daily/docs/MARKET_REGIME_DEPENDENCY_MAP.md (created)

---

### 2025-08-05 11:45 IST - [Claude]
**Changes:**
- Renamed hourly breakout alerts to "Trend Continuation Detected"
- Changed alert message from "Hourly Breakout Alert" to "Trend Continuation Detected"
- Updated description to "Uptrend continuation - Price sustaining above hourly close"
- Changed "Breakout:" label to "Continuation:" in alert

**Impact:**
- More accurately describes the signal (continuation vs breakout)
- Clearer messaging about what the alert represents
- Service restarted to apply changes

**Files Modified:**
- Daily/alerts/hourly_breakout_alert_service.py

---

### 2025-08-05 11:30 IST - [Claude]
**Changes:**
- Created comprehensive alerts and dashboards dependency mapping document
- Added ALERTS_DASHBOARDS_DEPENDENCY_MAP.md to docs folder
- Documented all service dependencies, configuration locations, and troubleshooting steps

**Impact:**
- Quick reference for diagnosing alert and dashboard issues
- Clear service dependency matrix showing data flow
- Troubleshooting decision tree for common problems
- Service control commands organized by type (long/short)

**Files Created:**
- Daily/docs/ALERTS_DASHBOARDS_DEPENDENCY_MAP.md

---

### 2025-08-05 11:20 IST - [Claude]
**Changes:**
- Disabled hourly short alerts by stopping related services
- Stopped com.india-ts.hourly-short-tracker-service (was sending HOURLY SHORT ALERT messages)
- Stopped com.india-ts.short-reversal-hourly scanner
- Stopped com.india-ts.short-momentum-tracker service

**Impact:**
- No more "HOURLY SHORT ALERT" Telegram messages
- Short reversal hourly scanner will not run
- Short momentum tracking is paused
- Dashboards remain running for monitoring but won't send alerts
- To re-enable: Use launchctl load with the respective plist files

**Services Stopped:**
- hourly-short-tracker-service.plist
- short-reversal-hourly.plist
- short-momentum-tracker.plist

---

### 2025-08-05 11:00 IST - [Claude]
**Changes:**
- Added configuration option to disable short-side alerts in VSR Telegram service
- Added `enable_short_alerts = no` to config.ini TELEGRAM section
- Modified vsr_telegram_service_enhanced.py to filter out SHORT signals when disabled
- Applied filter to both hourly and daily VSR alerts

**Impact:**
- Short signals will no longer trigger Telegram alerts when `enable_short_alerts = no`
- Long signals continue to work normally
- Service restarted to apply configuration changes
- Both hourly and daily alerts respect this setting

**Files Modified:**
- Daily/config.ini (added enable_short_alerts parameter)
- Daily/alerts/vsr_telegram_service_enhanced.py (added short signal filtering logic)

---

### 2025-08-05 10:30 IST - [Claude]
**Changes:**
- Diagnosed and fixed dashboard issues (ports 3002, 3003, 3004 showing no data)
- Root cause: Persistence files contained stale data from July 30 with incompatible format
- Created PLAYBOOK_DASHBOARD_TROUBLESHOOTING.md with detailed troubleshooting guide
- Reset persistence files for hourly trackers after backing up old data

**Impact:**
- All dashboards now operational and showing real-time data
- Hourly tracker services recovered from KeyError: 'last_updated' issue
- Created comprehensive playbook to prevent future occurrences
- Established daily maintenance checklist and emergency recovery procedures

**Files Modified:**
- Daily/PLAYBOOK_DASHBOARD_TROUBLESHOOTING.md (created)
- Daily/data/vsr_ticker_persistence_hourly_long.json (reset)
- Daily/data/short_momentum/vsr_ticker_persistence_hourly_short.json (reset)

---

### 2025-08-04 18:35 IST - [Claude]
**Changes:**
- Modified Telegram notifications to send alerts to channel ID -1002690613302 instead of personal chat
- Updated config.ini TELEGRAM section with new channel chat_id
- All Telegram services will now broadcast to the channel instead of individual user

**Impact:**
- All alerts (VSR, hourly breakout, first hour breakout, etc.) will go to the channel
- Multiple users can monitor alerts by joining the channel
- No changes needed to individual service files as they read chat_id from config.ini
- Channel alerts support same formatting and features as personal chat messages

**Files Modified:**
- Daily/config.ini - Updated chat_id in TELEGRAM section to -1002690613302

---

### 2025-08-04 13:50 IST - [Claude]
**Changes:**
- Created hourly breakout alert service for monitoring VSR-filtered tickers
- Created first hour breakout service for 5-minute candle monitoring (9:15-10:15 AM)
- Created Flask dashboards on ports 3005 and 3006 for viewing alerts
- Updated job manager dashboard to include both new services
- Updated INDIA_TS_JOBS_DOCUMENTATION.md with service details

**Impact:**
- Hourly breakout service tracks VSR tickers (ratio >= 2.0) and high momentum daily tickers (>= 10%)
- First hour service monitors same tickers for 5-minute candle breakouts during market open
- Both services send real-time Telegram alerts with HTML formatting
- Log files organized in dedicated folders: alerts_hourlybo/ and alerts_firsthour/
- Services integrated into job manager for centralized monitoring

**Service Details:**
- hourly_breakout_alert_service.py: 0.1% threshold, 30-min cooldown
- first_hour_breakout_service.py: 0.2% threshold, 5-min cooldown, volume ratio tracking
- Both services maintain state persistence in JSON files
- Plists created for automation: com.india-ts.hourly-breakout-alerts, com.india-ts.first-hour-alerts

---

### 2025-08-03 19:00 IST - [Claude]
**Changes:**
- Loaded enhanced VSR Telegram alerts service (com.india-ts.vsr-telegram-alerts-enhanced)
- Updated job manager dashboard to include the enhanced VSR Telegram service
- Updated INDIA_TS_JOBS_DOCUMENTATION.md with new service details
- Service is now active and running with market hours management (9 AM - 3:30 PM IST)

**Impact:**
- New service provides dual hourly and daily VSR alerts via Telegram
- Hourly alerts: 2%+ momentum, 2x+ VSR ratio threshold
- Daily alerts: 10%+ momentum, 60+ score threshold
- Market hours auto-management ensures service only runs during trading hours
- Both alert types can be independently toggled via config.ini

---

### 2025-08-03 19:15 IST - [Claude]
**Changes:**
- Created enhanced VSR Telegram service with configurable hourly/daily alerts
- Added new configuration parameters to config.ini TELEGRAM section:
  - hourly_telegram_on (yes/no) - Enable/disable hourly VSR alerts
  - daily_telegram_on (yes/no) - Enable/disable daily VSR alerts  
  - hourly_momentum_threshold (default: 2.0%) - Momentum threshold for hourly alerts
  - hourly_vsr_threshold (default: 2.0x) - VSR ratio threshold for hourly alerts
- Created vsr_telegram_service_enhanced.py with dual alert system
- Created com.india-ts.vsr-telegram-alerts-enhanced.plist for continuous monitoring
- Added test script test_enhanced_telegram.py for configuration verification

**Impact:**
- Users can now receive Telegram alerts for both hourly and daily VSR signals
- Hourly alerts catch early momentum moves (2%+ momentum, 2x+ VSR ratio)
- Daily alerts for confirmed high momentum moves (10%+ momentum, score 60+)
- Each alert type can be toggled on/off independently via config.ini
- Service monitors hourly VSR scan results in real-time during market hours
- Prevents duplicate alerts with ticker tracking for each timeframe

**Files Modified:**
- Daily/alerts/vsr_telegram_service_enhanced.py (new)
- Daily/alerts/test_enhanced_telegram.py (new)
- Daily/config.ini (updated TELEGRAM section)
- Daily/scheduler/plists/com.india-ts.vsr-telegram-alerts-enhanced.plist (new)

---

### 2025-08-03 18:20 IST - [Claude]
**Changes:**
- Created comprehensive ML training system for strategy prediction
- Fixed API authentication issues in comprehensive_reversal_trainer.py to use Sai's config
- Created train_ml_strategy_predictor.py - simplified trainer without Zerodha API dependency
- Successfully trained ML model with 83.3% test accuracy
- Created hourly_strategy_predictor service to run predictions every hour during market hours
- Fixed import issues in ml_dashboard_integration_scheduled.py
- Created plist for hourly predictions (com.india-ts.hourly_strategy_predictor)
- Updated PLIST_MASTER_SCHEDULE.md with new hourly predictor service

**Impact:**
- ML model now trained on actual reversal signal data and market breadth correlations
- System can predict optimal strategy (LONG/SHORT/NEUTRAL) based on current conditions
- Hourly predictions during market hours provide real-time strategy guidance
- Dashboard ML section now shows meaningful predictions with confidence scores
- Weekend/off-hours use cached Friday data as designed
- Model Performance: RandomForest 83.3% test accuracy, top features: signal_strength_diff (0.42), signal_ratio (0.22)

**Files Modified:**
- Daily/ML/training/comprehensive_reversal_trainer.py
- Daily/ML/training/train_ml_strategy_predictor.py (new)
- Daily/Market_Regime/ml_dashboard_integration_scheduled.py
- Daily/scheduler/plists/com.india-ts.hourly_strategy_predictor.plist (new)
- Daily/scheduler/PLIST_MASTER_SCHEDULE.md

---

### 2025-08-03 17:45 IST - [Claude]
**Changes:**
- Implemented scheduled ML service for weekday/weekend data management
- Created ml_dashboard_integration_scheduled.py to handle time-based data logic
- Created save_friday_breadth_data.py script to cache Friday 3:30 PM data
- Added plist job com.india-ts.save_friday_breadth_data to run every Friday at 3:30 PM
- Updated dashboard_enhanced.py to use scheduled ML integration
- Added data source metadata to ML insights API response

**Impact:**
- ML predictions now use live data during weekdays (9:15 AM - 3:30 PM)
- On weekends and outside market hours, ML uses Friday 3:30 PM cached data
- API response includes metadata showing data source (live_data vs friday_cache)
- Friday data automatically backed up with timestamps (keeps last 4 weeks)
- No manual intervention needed for weekend operations
- Dashboard continues to provide ML insights 24/7 with appropriate data

---

### 2025-08-03 14:00 IST - [Claude]
**Changes:**
- Fixed dashboard restart functionality in Job Manager Dashboard (port 9090)
- Modified restart_dashboard function to properly handle launchctl-managed dashboards with KeepAlive setting
- Changed from using launchctl start/stop to launchctl unload/load for proper restart
- Fixed logger initialization order in dashboard_enhanced.py to prevent NameError on startup
- Installed joblib module for system Python (/usr/bin/python3) to resolve import errors
- Created/updated documentation at Daily/docs/DASHBOARD_RESTART_FIX.md

**Impact:**
- Market Regime Dashboard (port 8080) can now be properly restarted from Job Manager Dashboard
- Health Dashboard (port 7080) can now be properly restarted from Job Manager Dashboard
- Resolves issue where dashboards with KeepAlive=true would immediately restart after being stopped
- Fixed dashboard startup failures due to missing dependencies and initialization order
- Job Manager Dashboard updated and restarted with the fix
- Market Regime Dashboard is now running successfully on port 8080
- No impact on other services or dashboards

---

### 2025-08-03 10:15 IST - [Claude]
**Changes:**
- Completely reorganized Daily/ML folder structure for better organization and maintainability
- Created proper subdirectories: core/, predictors/, analyzers/, training/, utils/, notebooks/, experiments/
- Moved existing ML files to appropriate subdirectories:
  - breadth_optimization_model.py → core/
  - breadth_strategy_predictor.py → predictors/
  - keltner_channel_filter_analyzer.py → analyzers/
  - retrain_breadth_model.py → training/
  - show_filtered_tickers.py, fix_excel_dates.py → utils/
- Copied Market_Regime/model_manager.py to ML/core/regime_model_manager.py for centralized ML model management
- Created comprehensive README.md documentation with:
  - Complete directory structure explanation
  - Usage examples for all ML components
  - Integration guidelines
  - Development best practices
  - Future enhancement roadmap

**Impact:**
- Improved ML module organization and discoverability
- Better separation of concerns (core models, predictors, analyzers, training)
- Enhanced documentation for developers and users
- Centralized ML model management
- Maintained backward compatibility with existing ML_MODULE_SUMMARY.md
- All existing functionality preserved, just better organized
- Future ML development will benefit from clear structure

---

### 2025-08-03 14:15 IST - [Claude]
**Changes:**
- Created ML-based breadth optimization module for continuous strategy optimization
- Implemented breadth_optimization_model.py with GradientBoostingRegressor
- Created breadth_strategy_predictor.py for real-time strategy recommendations
- Built retrain_breadth_model.py for weekly model updates
- Organized ML folder with proper structure (core/, predictors/, analyzers/, training/, utils/)
- Created comprehensive documentation (README.md and ML_MODULE_SUMMARY.md)
- Removed ML from .gitignore to enable version control
- Trained initial models achieving R² scores of 0.78 (long) and 0.83 (short)

**Impact:**
- ML model validates optimal SMA20 breadth ranges: Long (55-70%), Short (35-50%)
- Provides data-driven strategy recommendations based on current market breadth
- Enables continuous learning and adaptation to changing market conditions
- Integrated with existing trading system for enhanced decision making
- Weekly retraining ensures model stays current with market patterns
- All ML components now properly version controlled in git

---

### 2025-08-01 15:30 IST - [Claude]
**Changes:**
- Updated Job Manager Dashboard (job_manager_dashboard.py) to include ALL 46 services
- Added 19 missing services to the JOBS dictionary including:
  - consolidated_score, daily_action_plan
  - dashboard_manager_start/stop, dashboard_refresh_control  
  - g_pattern_master_tracker, kc_g_pattern_scanner
  - kc_lower_limit_trending, kc_upper_limit_trending
  - momentum_scanner, outcome_resolver
  - regime_data_updater, regime_data_updater_10min
  - sl_watchdog_start, sma_breadth_historical_update
  - strategyc_filter, fix_plists_on_startup
  - job_manager_dashboard (self), market_breadth_dashboard (service)

**Impact:**
- Job Manager Dashboard on port 9090 now shows complete visibility of all services
- Users can now restart ALL services after token refresh using the dashboard
- No need to use command line to find missing services
- Better monitoring and control of the entire India-TS ecosystem

---

### 2025-08-01 12:40 IST - [Claude]
**Changes:**
- Created standalone momentum scanner module (`momentum_scanner_standalone.py`) - completely independent from VSR scanner
- Implemented EMA crossover strategy: Price > EMA_100 AND Slope > 0
- Created momentum widget for dashboard showing daily/weekly counts and historical trends
- Successfully ran historical momentum scan for past 14 days with test data (50 tickers)
- Generated momentum reports for dates from 2025-07-18 to 2025-08-01
- Updated momentum widget to show formula reference: WM = ((EMA5-EMA8) + (EMA8-EMA13) + (EMA13-EMA21) + (EMA21-EMA50)) / 4

**Impact:**
- Historical momentum data now available for dashboard trend visualization
- Dashboard APIs functional: `/api/momentum_data` and `/api/momentum_trend`
- Daily momentum counts ranging from 9-10 tickers (test mode)
- Ready for full production scan at 4 PM IST daily
- All timezone issues resolved for Excel compatibility

---

### 2025-08-01 12:09 IST - [Claude]
**Changes:**
- Created momentum scanner module at `/Daily/scanners/momentum_scanner.py`
- Adapted Yahoo Finance EMA crossover strategy to use Zerodha API
- Created plist scheduler `com.india-ts.momentum_scanner` for 4 PM IST daily execution
- Created `/Daily/Momentum/` folder for output reports
- Added momentum widget endpoints to Market Regime dashboard (port 8080)
- Updated PLIST_MASTER_SCHEDULE.md with new job entry

**Impact:**
- New automated daily momentum analysis for Indian stocks
- Dashboard now displays momentum counts and trends at `/api/momentum_data` and `/api/momentum_trend`
- Excel reports generated daily with pattern `India-Momentum_Report_{Date}_{Time}.xlsx`
- Analyzes ~600 tickers for daily and weekly momentum signals

---

### 2025-08-02 12:30 IST - [Claude]
**Changes:**
- Running weekly profitability analysis for both Long and Short reversal signals
- Using existing simple analyzers: long_reversal_simple_analyzer.py and short_reversal_simple_analyzer.py
- Analyzing past 4 weeks of scan data to determine ticker profitability
- Generating comprehensive reports for both long and short strategies

**Impact:**
- Weekly performance reports will be generated in Daily/analysis/Weekly_Reports/
- Analysis includes all unique tickers that appeared in scans
- Calculates win rate and profitability percentages using current Zerodha prices
- Provides insights for strategy performance evaluation

---

### 2025-08-02 16:30 IST - [Claude]
**Changes:**
- Created comprehensive market regime correlation analysis
- Correlated strategy performance with SMA20/50 breadth and volume participation
- Generated clear market direction rules based on 4 weeks of data
- Created MARKET_DIRECTION_RULES_GUIDE.md with actionable weekly/daily rules
- Established thresholds for market bias determination

**Impact:**
- Clear rules for weekly direction: SMA20 breadth thresholds (70%/60%/50%/40%/30%/20%)
- Daily direction rules based on market score and reversal ratios
- Confirmed correlation: Low SMA20 breadth (48.8% avg) → Poor long performance (24.7% win rate)
- Confirmed correlation: Bearish regimes → Excellent short performance (80.8% win rate)
- Current recommendation: 40% Long, 60% Short allocation based on 34.2% SMA20 breadth

---

### 2025-08-02 16:35 IST - [Claude]
**Changes:**
- Updated market regime historical breadth data for August 2, 2025
- Successfully appended SMA breadth data showing SMA20: 34.24%, SMA50: 39.24%
- Attempted to update momentum breadth but encountered Excel format issues
- Market regime remains in "Downtrend" with market score of 0.362

**Impact:**
- Dashboard should now reflect updated SMA breadth data
- Current SMA20 breadth (34.2%) confirms continued MILD BEARISH bias
- Recommendation remains: 40% Long, 60% Short allocation
- Dashboards running on ports 8080 (Market Regime) and 9090 (Job Manager)

---

### 2025-08-02 16:40 IST - [Claude]
**Changes:**
- Fixed date issue in historical breadth data (August 2 is Saturday, market closed)
- Corrected data to show August 1, 2025 (Friday) with proper SMA breadth values
- Created fix_breadth_dates.py script to merge and correct the data
- Removed incorrect Saturday entry and updated Friday data

**Impact:**
- Historical breadth data now correctly shows August 1, 2025 as the latest trading day
- SMA20: 34.24%, SMA50: 39.24% for August 1, 2025
- Data integrity maintained for accurate weekly/monthly analysis
- Dashboards will show correct date alignment

---

### 2025-08-02 16:45 IST - [Claude]
**Changes:**
- Fixed missing volume breadth data for August 1, 2025
- Added volume breadth metrics from market breadth scan data
- Created fix_volume_breadth.py script to populate missing volume data
- Volume breadth data now complete for both July 31 and August 1

**Impact:**
- Dashboard volume charts will now display properly for both dates
- July 31: Volume participation 17.37%
- August 1: Volume participation 14.12%
- Low volume participation confirms lack of conviction in market moves
- Supports the mild bearish bias recommendation

---

### 2025-08-02 16:45 IST - [Claude]
**Changes:**
- Verified momentum scanner is operational and integrated with dashboard
- Momentum Scanner Analysis widget on Market Regime Dashboard (port 8080) is working
- Current momentum criteria: Price > EMA_100 AND Slope > 0
- Formula displayed: WM = ((EMA5-EMA8) + (EMA8-EMA13) + (EMA13-EMA21) + (EMA21-EMA50)) / 4
- API endpoints functional: `/api/momentum_data` and `/api/momentum_trend`

**Impact:**
- Dashboard shows 7 daily momentum tickers (up from 1 yesterday)
- Weekly momentum shows 0 tickers (down from 1)
- Momentum scanner runs daily at 4 PM IST via plist
- Widget displays top movers but WM/Slope values showing as NaN (known issue with Excel timezone handling)
- Historical trend data available for dashboard visualization

---

### 2025-08-02 16:50 IST - [Claude]
**Changes:**
- Created historical momentum analysis for past 2 months
- Analyzed 18 momentum reports from July 18 to August 2
- Generated trend plots showing daily and weekly momentum counts
- Created momentum_historical_simple.py for analyzing existing reports

**Impact:**
- Daily momentum averaged 16.8 tickers (Max: 103 on July 18)
- Weekly momentum averaged 10.2 tickers (Max: 97)
- Significant drop from July 18 (103 tickers) to current levels (7 tickers)
- Plots saved: momentum_trend_20250802.png and momentum_analysis_20250802.png
- Data shows declining momentum trend consistent with bearish market regime

---

### 2025-08-02 17:00 IST - [Claude]
**Changes:**
- Updated Momentum Scanner Analysis section on Market Regime Dashboard (port 8080)
- Changed formula from complex EMA-based to simple: WM = (SMA20 - SMA50) / 2
- Integrated with Market Breadth dashboard API on port 5001
- Created market_breadth_momentum_widget.py for new calculations
- Updated dashboard to show Market Momentum (WM), Daily/Weekly ticker counts, and market interpretation

**Impact:**
- Current Market Momentum: -2.5 (Mildly Bearish)
- Formula now directly correlates with market breadth data
- Dashboard shows dual-axis chart: momentum trend and ticker counts
- Real-time interpretation: "Mildly Bearish: Slight negative momentum. Market under pressure."
- Simplified analysis aligns with overall market regime assessment

---

### 2025-08-03 10:00 IST - [Claude]
**Changes:**
- Created Keltner Channel monthly scanner (keltner_monthly_scanner.py)
- Analyzes all tickers for Keltner Channel upper/lower limit touches on monthly timeframe
- Uses 20-period EMA with 2x ATR multiplier for channel calculation
- Scans 3 years of monthly data to identify touches and crosses

**Impact:**
- Upper Limit Touches: 99 tickers (16.4% of 603 scanned)
  - Top tickers near upper limit: LAURUSLABS (-10.6%), BSE (-2.8%), VENUSREM (-2.2%)
  - Several tickers currently above upper KC: INDIGO, LLOYDSME, NAVA, CEINSYSTECH
- Lower Limit Touches: 15 tickers (2.5% of 603 scanned)
  - ABFRL currently below lower KC (-18.95%)
  - Most touched lower limit in April-May 2025
- Results saved to: Daily/analysis/keltner_monthly_results/
- Provides insight into extreme price movements on monthly timeframe

---

### 2025-07-31 14:48 IST - [Claude]
**Changes:**
- Unloaded and archived 7 plists that are no longer in use:
  Phase 1 (14:45):
  1. com.india-ts.strategyc_filter.plist
  2. com.india-ts.kc_g_pattern_scanner.plist
  3. com.india-ts.g_pattern_master_tracker.plist
  4. com.india-ts.kc_lower_limit_trending.plist
  5. com.india-ts.kc_upper_limit_trending.plist
  
  Phase 2 (14:48):
  6. com.india-ts.consolidated_score.plist
  7. com.india-ts.daily_action_plan.plist
  
- Archived plists to: /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/plists/archived/20250731/
- Updated PLIST_MASTER_SCHEDULE.md (reduced job count from 39 to 32)
- Updated job_manager_dashboard.py (removed 6 entries from JOBS dictionary)
- Updated INDIA_TS_JOBS_DOCUMENTATION.md (marked 5 jobs as archived)

**Impact:**
- Reduced system load by removing 7 unused jobs
- Cleaned up job dashboard display
- Scanner runs reduced from ~100 to ~65 per day
- Removed non-essential analysis jobs (consolidated score, daily action plan)
- Remaining active scanners: reversal scanners (daily/hourly), FNO scanners, market breadth scanner
- No impact on active trading operations

---

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

### 2025-07-31 08:55 IST - [Claude]
**Changes:**
- Updated Job Manager Dashboard plist configuration to enable KeepAlive=true and RunAtLoad=true
- Updated both the active plist in ~/Library/LaunchAgents/ and backup in Daily/scheduler/plists/
- Reloaded the launchctl service to apply changes
- Dashboard is now configured to always stay running on port 9090

**Impact:**
- Job Manager Dashboard (port 9090) will now automatically restart if it crashes
- Dashboard will start automatically at system boot/login
- Files updated: ~/Library/LaunchAgents/com.india-ts.job_manager_dashboard.plist, Daily/scheduler/plists/com.india-ts.job_manager_dashboard.plist
- Service status verified - dashboard is accessible at http://localhost:9090

---

### 2025-07-31 09:02 IST - [Claude]
**Changes:**
- Created new plist configuration for hourly_tracker_service_fixed.py service
- Service was not scheduled to run at 8 AM because no plist existed
- Created com.india-ts.hourly-tracker-service.plist with KeepAlive and RunAtLoad enabled
- Fixed command arguments (removed unsupported --interval parameter)
- Loaded and started the service via launchctl

**Impact:**
- Hourly tracker service now runs continuously from 8 AM to 4 PM IST
- Service tracks VSR indicators for tickers from Long_Reversal_Hourly scan results
- Files created: Daily/scheduler/plists/com.india-ts.hourly-tracker-service.plist, ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist
- Service is now active and will restart automatically if it crashes
- Logs available at: Daily/logs/hourly_tracker_service.log and hourly_tracker_service_error.log

---

### 2025-07-31 09:15 IST - [Claude]
**Changes:**
- Created start/stop scripts for Short Momentum Dashboard to fix "No Startup Script found" error
- Created plists for hourly_tracker_dashboard.py and hourly_short_tracker_dashboard.py 
- Updated job_manager_dashboard.py to include start/stop scripts for all hourly dashboards
- Started both hourly tracker dashboards via launchctl
- Updated PLIST_MASTER_SCHEDULE.md to include hourly_tracker_service

**Impact:**
- Short Momentum Dashboard now has start/stop scripts at Daily/dashboards/
- Hourly Tracker Dashboard running on port 3002
- Hourly Short Tracker Dashboard running on port 3004
- All dashboards can now be started/stopped from Job Manager Dashboard (port 9090)
- Files created: 4 start/stop scripts, 2 new plists in scheduler/plists/
- Updated job count in documentation from 35 to 36

---

### 2025-07-31 09:47 IST - [Claude]
**Changes:**
- Fixed dashboards not showing data on ports 3002, 3003, and 3004
- Identified issue: services were logging to previous day's log files (20250730 instead of 20250731)
- Restarted short_momentum_tracker_service to force creation of today's log file
- Restarted hourly_tracker_service and hourly_short_tracker_service
- Created proper plist for hourly_short_tracker_service

**Impact:**
- Short Momentum Dashboard (3003) now showing data with 115 tracked tickers
- Services now logging to correct date-stamped files (20250731)
- All tracker services properly configured with plists and auto-restart enabled
- Dashboards should now populate with real-time tracking data
- Log files: short_momentum_tracker_20250731.log created with VSR-formatted entries

---

### 2025-07-31 09:50 IST - [Claude]
**Changes:**
- Updated job_manager_dashboard.py to include new hourly dashboard plist entries
- Updated PLIST_MASTER_SCHEDULE.md with all new services and dashboards
- Added hourly_tracker_dashboard and hourly_short_tracker_dashboard to JOBS dictionary
- Updated total job count from 36 to 39 in documentation
- Updated last modified timestamp in documentation

**Impact:**
- Job Manager Dashboard now tracks all 39 India-TS jobs including new dashboards
- All 43 active plists are properly documented and backed up (45 in backup directory)
- New services documented: hourly_short_tracker_service, hourly_tracker_dashboard, hourly_short_tracker_dashboard
- Dashboard entries properly show "Continuous (KeepAlive)" schedule status
- Complete plist tracking maintained across system

---

### 2025-07-30 16:20 IST - [Claude]
**Changes:**
- Fixed Volume Breadth Analysis showing zeros on dashboard (http://localhost:8080/)
- Updated symlink latest_market_breadth.json to point to current data (was pointing to July 15)
- Modified dashboard_enhanced.py to handle both old (volume_breadth) and new (volume_analysis) data formats
- Updated append_historical_breadth.py to convert new format to old format for compatibility
- Manually fixed July 29 volume data showing as 0 by extracting from breadth files
- Created VSR graduation analysis scripts to track tickers moving from hourly to daily
- Ran append_historical_breadth.py to ensure data is up to date

**Impact:**
- Volume Breadth charts now display correct data instead of zeros
- Dashboard handles both old and new data formats seamlessly
- July 29 data fixed with 11.79% volume breadth
- Identified only 2 true VSR graduations today: GATEWAY and WELCORP
- Historical breadth data updated successfully for 2025-07-30
- Files updated: /Daily/Market_Regime/dashboard_enhanced.py, /Daily/Market_Regime/append_historical_breadth.py
- New analysis scripts: /Daily/analysis/vsr_graduation_report.py, /Daily/analysis/vsr_true_graduation_analysis.py

---

### 2025-07-30 16:30 IST - [Claude]
**Changes:**
- Fixed July 30 volume data showing as 0 in dashboard
- Corrected volume participation values for July 28-30 in historical data
- July 28: Volume breadth=9.26%, Volume participation=0.0926
- July 29: Volume breadth=11.79%, Volume participation=0.1179  
- July 30: Volume breadth=14.17%, Volume participation=0.1417
- Discovered that volume_participation in old format (ratio) differs from avg_volume_ratio (0.94-0.99 range)

**Impact:**
- Dashboard now shows correct volume data for July 28-30
- Volume participation correctly calculated as high_volume/total_stocks ratio
- Historical data consistency improved for recent dates
- File updated: /Daily/Market_Regime/historical_breadth_data/sma_breadth_historical_latest.json

---

### 2025-07-30 18:42 IST - [Claude]
**Changes:**
- Fixed bug in append_historical_breadth.py that was using avg_volume_ratio instead of high_volume/total_stocks for volume_participation
- Updated sma_breadth_incremental_collector.py to preserve existing volume_breadth data when updating SMA data
- Re-ran append_historical_breadth.py to restore July 30 volume data after 6:30 PM job overwrote it
- Volume participation calculation now correctly uses: volume_participation = high_volume / total_stocks

**Impact:**
- Permanent fix prevents future 6:30 PM jobs from overwriting volume data
- July 30 volume data restored: Volume breadth=14.17%, Volume participation=0.1417
- Dashboard will now maintain correct volume data through scheduled updates
- Files updated: /Daily/Market_Regime/append_historical_breadth.py, /Daily/Market_Regime/sma_breadth_incremental_collector.py

---

### 2025-07-30 12:55 IST - [Claude]
**Changes:**
- Fixed hourly tracker service (port 3002) initialization issues with Kite API
- Created hourly_tracker_service_fixed.py with proper config loading and credential handling
- Updated hourly_tracker_dashboard.py regex pattern to match service log format including Days field
- Created new hourly short tracker service and dashboard (port 3004) for Short_Reversal_Hourly results
- Updated dashboard_manager.py to include port 3004 configuration
- Added both hourly services and dashboards to job_manager_dashboard.py at port 9090

**Impact:**
- Hourly tracker dashboard (3002) now correctly populates with tickers from Long_Reversal_Hourly scans
- New hourly short tracker dashboard (3004) provides same functionality for short positions
- Both services use VSR scoring logic adapted for their respective directions
- Services: hourly_tracker_service_fixed.py, hourly_short_tracker_service.py
- Dashboards: hourly_tracker_dashboard.py (3002), hourly_short_tracker_dashboard.py (3004)
- Job manager dashboard (9090) now shows all hourly tracker services for monitoring

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

## 2025-07-30 15:11 IST - Claude - Fix Volume Breadth Display on Dashboard

**Changes:**
- Fixed market_breadth_latest.json symlink to point to today's data (market_breadth_20250730_144316.json)
- Updated dashboard_enhanced.py to use correct field names from actual data structure
- Changed volume_breadth calculation to use volume_analysis.high_volume / total_stocks * 100
- Changed volume_participation to use volume_analysis.avg_volume_ratio * 100

**Impact:**
- Volume Breadth Analysis section on dashboard (http://localhost:8080/) now displays correct data
- Dashboard properly calculates volume breadth percentage from high_volume stocks
- Volume participation chart shows average volume ratio as percentage
- Fixed issue where volume breadth was showing zeros due to incorrect field mapping
- API now returns volume_breadth_values and volume_participation_values correctly
- Dashboard handles both old format (volume_breadth) and new format (volume_analysis) data

---

## 2025-07-30 15:19 IST - Claude - Fix Volume Breadth Chart Display

**Changes:**
- Updated append_historical_breadth.py to convert volume_analysis to volume_breadth format
- Manually updated today's historical entry with volume breadth data (12.94%)
- Volume breadth now correctly displays on dashboard charts

**Impact:**
- Volume Breadth charts now show actual data instead of zeros
- July 29th still shows 0 as it lacks volume data in historical file
- Dashboard properly displays volume trends over time
- append_historical_breadth.py now handles both old and new data formats

---

## 2025-07-30 15:21 IST - Claude - Update July 29th Volume Data

**Changes:**
- Created and ran one-time script to update July 29th historical data with volume information
- Used market_breadth_20250729_154253.json to extract volume data
- Updated historical data: Volume breadth 11.79%, Volume participation 0.9540

**Impact:**
- July 29th now displays correct volume data on dashboard charts
- All historical data points now show volume information
- Volume Breadth Analysis charts show complete trend without gaps
- Removed temporary update script after successful update

---

## 2025-08-04 12:30 IST - Claude - Hourly Breakout Alert Service

**Changes:**
- Created new service: `hourly_breakout_alert_service.py` in Daily/alerts/
- Purpose: Alerts when Long Reversal Scanner tickers cross above previous hourly candle close
- Configuration: Added [HOURLY_BREAKOUT] section to config.ini
  - breakout_threshold_pct = 0.1% (minimal threshold to catch all breakouts)
  - alert_cooldown_minutes = 30 (allows multiple alerts per day)
  - min_daily_score = 5/7 (only tracks high-quality setups)
  - check_interval_seconds = 30 (checks every 30 seconds during market hours)
- Scripts: 
  - start_hourly_breakout_alerts.sh - starts the service
  - stop_hourly_breakout_alerts.sh - stops the service
- Plist: com.india-ts.hourly-breakout-alerts.plist
- Impact: Provides timely entry signals for Long Reversal setups when they break above hourly resistance

---

**Changes:**
- Created and ran one-time script to update July 29th historical data with volume information
- Used market_breadth_20250729_154253.json to extract volume data
- Updated historical data: Volume breadth 11.79%, Volume participation 0.9540

**Impact:**
- July 29th now displays correct volume data on dashboard charts
- All historical data points now show volume information
- Volume Breadth Analysis charts show complete trend without gaps
- Removed temporary update script after successful update

---
