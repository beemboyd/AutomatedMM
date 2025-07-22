# Market Regime Analyzer - 5-Minute Update

## Overview
The Market Regime Analyzer has been updated from running every 30 minutes to running every 5 minutes during market hours. This change addresses a critical timing issue where the analyzer was missing the latest reversal scan results.

## Problem Statement
Previously, the regime analyzer experienced a synchronization issue:
- Reversal scans run at :30 and :00 (e.g., 10:30 AM, 11:00 AM)
- Regime analyzer also ran at :30 and :00
- The regime analyzer would execute **before** the reversal scans completed
- This caused the dashboard to show outdated L/S ratios

### Example of the Issue (July 18, 2025)
- 10:30 AM reversal scans showed: 13 Long, 42 Short (L/S ratio = 0.31)
- 10:30 AM regime analyzer used: 30 Long, 26 Short from 10:06 AM files (L/S ratio = 1.15)
- Dashboard displayed incorrect bullish bias when market was actually bearish

## Solution
By running the regime analyzer every 5 minutes:
- It picks up the latest reversal scan results within 5 minutes
- Dashboard stays current with actual market conditions
- Reduces lag between data availability and dashboard updates

## Implementation Details

### New Schedule
- **Frequency**: Every 5 minutes
- **Hours**: 9:00 AM - 3:30 PM IST
- **Days**: Monday through Friday
- **LaunchAgent**: `com.india-ts.market_regime_analyzer_5min`

### Files Created/Modified
1. **`run_regime_analyzer_5min.sh`** - Script that checks market hours before running
2. **`com.india-ts.market_regime_analyzer_5min.plist`** - LaunchAgent configuration
3. **`migrate_to_5min_scheduler.sh`** - Migration script for graceful transition
4. **`job_manager_dashboard.py`** - Updated to show both old and new schedulers

### Migration Process
To migrate from 30-minute to 5-minute scheduler:

```bash
cd ~/PycharmProjects/India-TS/Daily/Market_Regime
./migrate_to_5min_scheduler.sh
```

This script will:
1. Unload existing 30-minute schedulers
2. Archive old plist files
3. Load the new 5-minute scheduler
4. Verify successful migration

### Manual Migration (if needed)
```bash
# Unload old scheduler
launchctl unload ~/Library/LaunchAgents/com.india-ts.market_regime_analysis.plist

# Load new scheduler
launchctl load ~/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist

# Verify it's running
launchctl list | grep market_regime_analyzer_5min
```

## Benefits
1. **Timely Updates**: L/S ratios update within 5 minutes of new scan data
2. **Accurate Dashboard**: Breadth indicators reflect current market conditions
3. **Better Trading Decisions**: No lag between actual reversals and regime analysis
4. **Smoother Transitions**: Regime changes detected more quickly

## Monitoring

### Check Scheduler Status
```bash
launchctl list | grep market_regime_analyzer_5min
```

### View Logs
```bash
tail -f ~/PycharmProjects/India-TS/Daily/logs/market_regime_analyzer_5min.log
```

### Verify Dashboard Updates
1. Check dashboard at http://localhost:8080
2. Compare L/S ratio with latest reversal reports
3. Should match within 5 minutes of scan completion

## Troubleshooting

### Scheduler Not Running
```bash
# Check if loaded
launchctl list | grep regime

# Reload if needed
launchctl unload ~/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist
```

### Dashboard Still Shows Old Data
1. Force run the analyzer: `cd ~/PycharmProjects/India-TS/Daily/Market_Regime && python3 market_regime_analyzer.py --force`
2. Refresh dashboard page
3. Check `latest_regime_summary.json` for correct counts

### Performance Concerns
The 5-minute frequency is optimized for market hours only:
- No runs outside 9:00 AM - 3:30 PM
- No runs on weekends
- Minimal resource usage (quick file reads and calculations)

## Rollback (if needed)
To revert to 30-minute scheduling:
```bash
# Unload 5-minute scheduler
launchctl unload ~/Library/LaunchAgents/com.india-ts.market_regime_analyzer_5min.plist

# Restore and load old scheduler
mv ~/Library/LaunchAgents/com.india-ts.market_regime_analysis.plist.backup.* ~/Library/LaunchAgents/com.india-ts.market_regime_analysis.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.market_regime_analysis.plist
```

## Future Enhancements
- Consider event-driven updates when reversal scans complete
- Add health checks to ensure analyzer picks up latest files
- Implement alerts for large L/S ratio changes