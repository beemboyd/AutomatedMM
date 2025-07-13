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

#### 5. **com.india-ts.market_regime_analysis**
- **Purpose**: Analyzes market regime based on scanner results
- **Schedule**: Every 30 minutes from 9:15 AM to 3:30 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/market_regime_analyzer.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_analysis.plist`
- **Status**: ✅ Active

#### 6. **com.india-ts.market_regime_dashboard**
- **Purpose**: Generates market regime dashboard
- **Schedule**: 5:00 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/market_regime_dashboard.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist`
- **Status**: ✅ Active

### Utility Jobs

#### 7. **com.india-ts.daily_action_plan**
- **Purpose**: Generates daily trading action plan
- **Schedule**: 8:30 AM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Action_plan.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.daily_action_plan.plist`
- **Status**: ✅ Active

#### 8. **com.india-ts.consolidated_score**
- **Purpose**: Generates consolidated scoring report
- **Schedule**: 9:00 AM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/scanners/Consolidated_Score.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.consolidated_score.plist`
- **Status**: ✅ Active

#### 9. **com.india-ts.synch_zerodha_local**
- **Purpose**: Synchronizes Zerodha CNC positions with local state
- **Schedule**: Every 15 minutes from 9:15 AM to 3:30 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/utils/synch_zerodha_cnc_positions.py --force`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.synch_zerodha_local.plist`
- **Status**: ⚠️ Active with warnings (exit code 1 when discrepancies found)

#### 10. **com.india-ts.weekly_backup**
- **Purpose**: Creates weekly backup of trading data
- **Schedule**: Saturdays at 10:00 AM IST
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/utils/Weekly_Backup.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.weekly_backup.plist`
- **Status**: ✅ Active

#### 11. **com.india-ts.health_dashboard**
- **Purpose**: System health monitoring dashboard
- **Schedule**: Runs continuously (KeepAlive)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/diagnostics/health_dashboard.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist`
- **Status**: ✅ Running (PID: 758)

#### 12. **com.india-ts.strategyc_filter**
- **Purpose**: Strategy C filter processing
- **Schedule**: 3:45 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/analysis/Strategy_C_Filter.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.strategyc_filter.plist`
- **Status**: ✅ Active

#### 13. **com.india-ts.sl_watchdog_stop**
- **Purpose**: Stops the SL watchdog service
- **Schedule**: 3:45 PM IST (weekdays)
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/utils/stop_sl_watchdog.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.sl_watchdog_stop.plist`
- **Status**: ✅ Active
- **Note**: SL Watchdog now includes volume-price anomaly detection for exhaustion pattern warnings

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
    "com.india-ts.consolidated_score.plist"
    "com.india-ts.daily_action_plan.plist"
    "com.india-ts.health_dashboard.plist"
    "com.india-ts.long_reversal_daily.plist"
    "com.india-ts.market_regime_analysis.plist"
    "com.india-ts.market_regime_dashboard.plist"
    "com.india-ts.short_reversal_daily.plist"
    "com.india-ts.sl_watchdog_stop.plist"
    "com.india-ts.strategyc_filter.plist"
    "com.india-ts.synch_zerodha_local.plist"
    "com.india-ts.weekly_backup.plist"
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

### Log File Locations

- Daily logs: `/Users/maverick/PycharmProjects/India-TS/Daily/logs/`
- Market Regime logs: `/Users/maverick/PycharmProjects/India-TS/Market_Regime/logs/`
- System logs: `/Users/maverick/PycharmProjects/India-TS/logs/`

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

Last Updated: 2025-07-13