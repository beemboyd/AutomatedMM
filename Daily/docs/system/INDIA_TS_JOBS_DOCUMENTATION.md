# India-TS LaunchAgent Jobs Documentation

This document provides a comprehensive overview of all India-TS system jobs, their purposes, schedules, and management instructions.

## Table of Contents
1. [Active Jobs](#active-jobs)
2. [Deprecated/Removed Jobs](#deprecatedremoved-jobs)  
3. [Job Management Scripts](#job-management-scripts)
4. [Troubleshooting](#troubleshooting)
5. [System Reboot Instructions](#system-reboot-instructions)

## Active Jobs

### Daily Trading Jobs

#### 1. **com.india-ts.long_reversal_daily**
- **Purpose**: Scans for long reversal opportunities
- **Schedule**: Every 30 minutes from 9:00 AM to 3:30 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/scanners/Scanner_Reversals_India.py --type long`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.long_reversal_daily.plist`
- **Status**: ✅ Active

#### 2. **com.india-ts.short_reversal_daily**
- **Purpose**: Scans for short reversal opportunities
- **Schedule**: Every 30 minutes from 9:00 AM to 3:30 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/scanners/Scanner_Reversals_India.py --type short`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.short_reversal_daily.plist`
- **Status**: ✅ Active

#### 3. **com.india-ts.brooks_reversal_simple**
- **Purpose**: Al Brooks reversal pattern scanner (runs every 30 minutes)
- **Schedule**: Every 30 minutes (24/7)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/utils/brooks_reversal_scheduler.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.brooks_reversal_simple.plist`
- **Status**: ✅ Active (Fixed path issue on 2025-07-04)

#### 4. **com.india-ts.brooks_reversal_4times**
- **Purpose**: Al Brooks reversal pattern scanner (runs 4 times daily)
- **Schedule**: 9:30 AM, 11:30 AM, 1:30 PM, 4:00 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/utils/brooks_reversal_scheduler.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.brooks_reversal_4times.plist`
- **Status**: ✅ Active

### Market Analysis Jobs

#### 5. **com.india-ts.market_regime_analyzer_5min** *(Updated July 18, 2025)*
- **Purpose**: Analyzes market regime based on scanner results with improved timing
- **Schedule**: Every 5 minutes from 9:00 AM to 3:30 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/run_regime_analyzer_5min.sh`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist`
- **Status**: ✅ Active
- **Change Reason**: Fixed timing issue where analyzer was missing latest reversal scan files
- **Migration**: Run `./migrate_to_5min_scheduler.sh` in Market_Regime directory

#### 5a. **com.india-ts.market_regime_analysis** *(DEPRECATED)*
- **Purpose**: Old 30-minute regime analyzer
- **Schedule**: Every 30 minutes from 8:30 AM to 3:30 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/market_regime_analyzer.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_analysis.plist`
- **Status**: ❌ Deprecated - Replaced by 5-minute version

#### 6. **com.india-ts.kc_lower_limit_trending** *(ARCHIVED 2025-07-31)*
- **Purpose**: Scans for stocks trending at Keltner Channel lower limit
- **Schedule**: Every hour from 9:15 AM to 3:15 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/scanners/KC_Lower_Limit_Trending.py`
- **Plist**: ARCHIVED to `/Users/maverick/PycharmProjects/India-TS/Daily/scheduler/plists/archived/20250731/`
- **Status**: ❌ Archived (Not in use)
- **Archived**: 2025-07-31 - Scanner not being used

#### 7. **com.india-ts.kc_upper_limit_trending** *(ARCHIVED 2025-07-31)*
- **Purpose**: Scans for stocks trending at Keltner Channel upper limit
- **Schedule**: Every hour from 9:10 AM to 3:10 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/scanners/KC_Upper_Limit_Trending.py`
- **Plist**: ARCHIVED to `/Users/maverick/PycharmProjects/India-TS/Daily/scheduler/plists/archived/20250731/`
- **Status**: ❌ Archived (Not in use)
- **Archived**: 2025-07-31 - Scanner not being used

#### 8. **com.india-ts.market_regime_dashboard**
- **Purpose**: Generates market regime dashboard
- **Schedule**: 5:00 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/market_regime_dashboard.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist`
- **Status**: ✅ Active

### Utility Jobs

#### 9. **com.india-ts.daily_action_plan** *(ARCHIVED 2025-07-31)*
- **Purpose**: Generates daily trading action plan
- **Schedule**: 8:30 AM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Action_plan.py`
- **Plist**: ARCHIVED to `/Users/maverick/PycharmProjects/India-TS/Daily/scheduler/plists/archived/20250731/`
- **Status**: ❌ Archived (Not in use)
- **Archived**: 2025-07-31 - No longer required

#### 10. **com.india-ts.consolidated_score** *(ARCHIVED 2025-07-31)*
- **Purpose**: Generates consolidated scoring report
- **Schedule**: 9:00 AM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/scanners/Consolidated_Score.py`
- **Plist**: ARCHIVED to `/Users/maverick/PycharmProjects/India-TS/Daily/scheduler/plists/archived/20250731/`
- **Status**: ❌ Archived (Not in use)
- **Archived**: 2025-07-31 - No longer required

#### 11. **com.india-ts.synch_zerodha_local**
- **Purpose**: Synchronizes Zerodha CNC positions with local state
- **Schedule**: Every 15 minutes from 9:15 AM to 3:30 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/utils/synch_zerodha_cnc_positions.py --force`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.synch_zerodha_local.plist`
- **Status**: ⚠️ Active with warnings (exit code 1 when discrepancies found)

#### 12. **com.india-ts.weekly_backup**
- **Purpose**: Creates weekly backup of trading data
- **Schedule**: Saturdays at 10:00 AM IST
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/utils/Weekly_Backup.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.weekly_backup.plist`
- **Status**: ✅ Active

#### 13. **com.india-ts.health_dashboard**
- **Purpose**: System health monitoring dashboard
- **Schedule**: Runs continuously (KeepAlive)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/diagnostics/health_dashboard.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist`
- **Status**: ✅ Running (PID: 758)

#### 14. **com.india-ts.strategyc_filter** *(ARCHIVED 2025-07-31)*
- **Purpose**: Strategy C filter processing
- **Schedule**: 3:45 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Strategy_C_Filter.py`
- **Plist**: ARCHIVED to `/Users/maverick/PycharmProjects/India-TS/Daily/scheduler/plists/archived/20250731/`
- **Status**: ❌ Archived (Not in use)
- **Archived**: 2025-07-31 - Scanner not being used

#### 15. **com.india-ts.sl_watchdog_stop**
- **Purpose**: Stops the SL watchdog service
- **Schedule**: 3:45 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/utils/stop_sl_watchdog.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.sl_watchdog_stop.plist`
- **Status**: ✅ Active
- **Note**: SL Watchdog now includes volume-price anomaly detection for exhaustion pattern warnings

#### 16. **com.india-ts.vsr-telegram-alerts-enhanced** *(New - August 3, 2025)*
- **Purpose**: Enhanced VSR Telegram alerts service with dual hourly and daily momentum alerts
- **Schedule**: 8:55 AM - 3:30 PM IST (weekdays, auto-managed)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/alerts/vsr_telegram_market_hours_manager.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist`
- **Status**: ✅ Active
- **Features**:
  - Hourly VSR alerts (2%+ momentum, 2x+ VSR ratio)
  - Daily VSR alerts (10%+ momentum, 60+ score)
  - Configurable thresholds in config.ini
  - Independent hourly/daily toggle (hourly_telegram_on, daily_telegram_on)
  - Market hours auto-management (9 AM - 3:30 PM)
- **Configuration**: See `/Users/maverick/PycharmProjects/India-TS/Daily/docs/VSR_TELEGRAM_ENHANCED_GUIDE.md`

#### 17. **com.india-ts.hourly-breakout-alerts** *(New - August 4, 2025)*
- **Purpose**: Monitors VSR-filtered tickers for hourly candle breakouts
- **Schedule**: Runs continuously from 9:00 AM to 3:30 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/alerts/hourly_breakout_alert_service.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.hourly-breakout-alerts.plist`
- **Dashboard**: Port 3005 - `/Users/maverick/PycharmProjects/India-TS/Daily/dashboards/hourly_breakout_dashboard.py`
- **Status**: ✅ Active
- **Features**:
  - Tracks tickers from hourly VSR scans (VSR ratio >= 2.0)
  - Tracks tickers from daily Long Reversal scans (momentum >= 10%)
  - 0.1% breakout threshold above previous hourly candle close
  - 30-minute cooldown between alerts per ticker
  - Real-time Telegram notifications with HTML formatting
  - State persistence in JSON
- **Logs**: `/Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_hourlybo/`

#### 18. **com.india-ts.first-hour-alerts** *(New - August 4, 2025)*
- **Purpose**: Monitors 5-minute candle breakouts during first hour of trading
- **Schedule**: 9:14 AM IST (weekdays), runs until 10:15 AM
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/alerts/first_hour_breakout_service.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.first-hour-alerts.plist`
- **Dashboard**: Port 3006 - `/Users/maverick/PycharmProjects/India-TS/Daily/dashboards/first_hour_dashboard.py`
- **Status**: ✅ Active
- **Features**:
  - Monitors same tickers as hourly breakout service
  - 5-minute candle breakout detection
  - 0.2% breakout threshold above previous 5-min high
  - 5-minute cooldown between alerts per ticker
  - Volume ratio tracking
  - Real-time Telegram notifications
- **Logs**: `/Users/maverick/PycharmProjects/India-TS/Daily/logs/alerts_firsthour/`

## Deprecated/Removed Jobs

These jobs have been removed or disabled due to system migration or missing dependencies:

#### 1. **com.india-ts.outcome_resolver**
- **Reason**: Market Regime system migrated, script no longer exists
- **Action Taken**: Unloaded on 2025-07-04

#### 2. **com.india-ts.market_regime_daily_metrics**
- **Reason**: Market Regime system migrated, script no longer exists
- **Action Taken**: Unloaded on 2025-07-04

#### 3. **com.india-ts.sl_watchdog_start**
- **Reason**: Missing credentials for user "Mom"
- **Action Taken**: Unloaded on 2025-07-04
- **Fix Required**: Configure proper user credentials in config.ini

## Job Management Scripts

### Load All Jobs Script
Create this script at `/Users/maverick/PycharmProjects/India-TS/Daily/utils/load_all_jobs.sh`:

```bash
#!/bin/bash

echo "Loading all India-TS LaunchAgent jobs..."

# List of all active plist files
PLIST_FILES=(
    "com.india-ts.brooks_reversal_4times.plist"
    "com.india-ts.brooks_reversal_simple.plist"
    "com.india-ts.health_dashboard.plist"
    "com.india-ts.long_reversal_daily.plist"
    "com.india-ts.market_regime_analysis.plist"
    "com.india-ts.market_regime_dashboard.plist"
    "com.india-ts.short_reversal_daily.plist"
    "com.india-ts.sl_watchdog_stop.plist"
    "com.india-ts.synch_zerodha_local.plist"
    "com.india-ts.vsr-telegram-alerts-enhanced.plist"
    "com.india-ts.weekly_backup.plist"
    "com.india-ts.hourly-breakout-alerts.plist"
    "com.india-ts.first-hour-alerts.plist"
)

LAUNCHAGENTS_DIR="/Users/maverick/Library/LaunchAgents"

for plist in "${PLIST_FILES[@]}"; do
    plist_path="$LAUNCHAGENTS_DIR/$plist"
    if [ -f "$plist_path" ]; then
        echo "Loading $plist..."
        launchctl load "$plist_path"
    else
        echo "WARNING: $plist not found!"
    fi
done

echo "Done! Checking status..."
launchctl list | grep india-ts
```

### Unload All Jobs Script
Create this script at `/Users/maverick/PycharmProjects/India-TS/Daily/utils/unload_all_jobs.sh`:

```bash
#!/bin/bash

echo "Unloading all India-TS LaunchAgent jobs..."

# Get all loaded india-ts jobs
loaded_jobs=$(launchctl list | grep india-ts | awk '{print $3}')

for job in $loaded_jobs; do
    echo "Unloading $job..."
    plist_path="/Users/maverick/Library/LaunchAgents/$job.plist"
    if [ -f "$plist_path" ]; then
        launchctl unload "$plist_path"
    fi
done

echo "Done! Checking status..."
launchctl list | grep india-ts
```

### Tracker Services

#### 19. **com.india-ts.hourly-tracker-service** *(Critical for Dashboard)*
- **Purpose**: Tracks Long Reversal Hourly tickers and provides data for dashboard
- **Schedule**: Runs continuously during market hours
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/services/hourly_tracker_service_fixed.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist`
- **Dashboard**: Port 3002 - Hourly Tracker Dashboard
- **Status**: ✅ Active
- **Critical Note**: Must restart daily at 9:00 AM or log files use wrong date

#### 20. **com.india-ts.hourly-short-tracker-service** *(Critical for Dashboard)*
- **Purpose**: Tracks Short Reversal Hourly tickers
- **Schedule**: Runs continuously during market hours
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/services/hourly_short_tracker_service.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.hourly-short-tracker-service.plist`
- **Dashboard**: Port 3004 - Hourly Short Dashboard
- **Status**: ✅ Active
- **Critical Note**: Must restart daily at 9:00 AM or log files use wrong date

#### 21. **com.india-ts.short-momentum-tracker** *(Critical for Dashboard)*
- **Purpose**: Tracks Short Reversal Daily momentum
- **Schedule**: Runs continuously during market hours
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/services/short_momentum_tracker_service.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.short-momentum-tracker.plist`
- **Dashboard**: Port 3003 - Short Momentum Dashboard
- **Status**: ✅ Active
- **Critical Note**: Must restart daily at 9:00 AM or log files use wrong date

#### 22. **com.india-ts.vsr-tracker-enhanced** *(Critical for Dashboard)*
- **Purpose**: Enhanced VSR tracking service
- **Schedule**: Runs continuously during market hours
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/services/VSR_Tracker_Enhanced.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.vsr-tracker-enhanced.plist`
- **Dashboard**: Port 3001 - VSR Dashboard
- **Status**: ✅ Active
- **Critical Note**: Must restart daily at 9:00 AM for fresh state

## Troubleshooting

### Common Issues and Solutions

1. **Exit Code 2**: Usually means the script file doesn't exist or has a syntax error
   - Check if the script path in the plist is correct
   - Verify Python path is correct
   - Check error logs in `/Users/maverick/PycharmProjects/India-TS/Daily/logs/`

2. **Exit Code 1**: Script ran but encountered an error
   - Check the specific error log for the job
   - Common causes: missing credentials, API errors, file not found

3. **Job Not Loading**: 
   - Verify plist syntax: `plutil -lint /path/to/plist`
   - Check file permissions: `ls -la /path/to/plist`
   - Ensure plist is in `/Users/maverick/Library/LaunchAgents/`

4. **Dashboard Shows No Data** (Ports 3002, 3003, 3004):
   - **Root Cause**: Tracker services use previous day's date for log files
   - **Solution**: Restart tracker services daily at 9:00 AM
   - **Automated Fix**: Run `./pre_market_setup.sh` which now includes service restarts
   - **Manual Fix**: 
     ```bash
     launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist
     launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist
     # Repeat for other tracker services
     ```

### Log File Locations

- Daily logs: `/Users/maverick/PycharmProjects/India-TS/Daily/logs/`
- Market Regime logs: `/Users/maverick/PycharmProjects/India-TS/Market_Regime/logs/`
- System logs: `/Users/maverick/PycharmProjects/India-TS/logs/`

## Pre-Market Setup Schedule (Critical)

**Daily at 9:00 AM IST:**
1. Update access token via `loginz.py`
2. **Restart all tracker services** (hourly-tracker, short-momentum, vsr-tracker)
3. Run VSR Scanner
4. Restart alert services
5. Start hourly breakout alerts
6. Start all dashboards

**Note**: Step 2 is critical - services must restart to use correct date for log files.

## System Reboot Instructions

After system reboot, follow these steps:

1. **Check which jobs are loaded**:
   ```bash
   launchctl list | grep india-ts
   ```

2. **Load all jobs using the script**:
   ```bash
   chmod +x /Users/maverick/PycharmProjects/India-TS/Daily/utils/load_all_jobs.sh
   /Users/maverick/PycharmProjects/India-TS/Daily/utils/load_all_jobs.sh
   ```

3. **Verify all jobs are loaded correctly**:
   ```bash
   launchctl list | grep india-ts
   ```

4. **Check for any errors**:
   ```bash
   # Check recent error logs
   tail -50 /Users/maverick/PycharmProjects/India-TS/Daily/logs/*error*.log
   ```

5. **Monitor health dashboard**:
   - The health dashboard should be running continuously
   - Check its status with: `launchctl list | grep health_dashboard`

## Maintenance Notes

- **Schedule Conflicts**: Some jobs run at the same time (e.g., 9:00 AM has 4 jobs). Monitor for performance issues.
- **Python Versions**: Different jobs use different Python versions (3.11, 3.12). Ensure all versions are installed.
- **Credentials**: Ensure all required credentials are properly configured in config files.
- **Market Hours**: Most jobs only run during Indian market hours (9:00 AM - 3:30 PM IST on weekdays).
- **Volume Anomaly Detection**: SL Watchdog services now include volume-price anomaly detection to identify exhaustion patterns

---

Last Updated: 2025-08-04