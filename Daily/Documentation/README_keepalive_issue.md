# KeepAlive Reverting Issue - Investigation and Solutions

## Problem Description
The KeepAlive setting in the Brooks reversal plist files keeps reverting to `true` after machine restarts, causing the script to run continuously instead of every 30 minutes as intended.

## Root Cause Analysis

### Potential Causes Investigated:
1. **Scripts modifying plist files** - No scripts found that modify KeepAlive to true
2. **Multiple plist versions** - All source plists have KeepAlive=false
3. **System restore/backup** - No Time Machine or iCloud attributes found
4. **LaunchD behavior** - StartInterval and KeepAlive interaction

### Likely Cause:
The issue appears to be related to how macOS launchd handles services with `StartInterval` when the system restarts. In some cases, launchd may override the KeepAlive setting if it detects the service failed or exited unexpectedly.

## Solutions Implemented

### 1. Enhanced Plist Configuration
Created `com.india-ts.brooks_reversal_fixed.plist` with:
- Explicit `KeepAlive` set to `false`
- Added `ThrottleInterval` to prevent rapid restarts
- Added `ExitTimeOut` for proper exit handling

### 2. Monitoring Script
Created `monitor_plist_changes.sh` to:
- Check KeepAlive values in all India-TS plists
- Log any changes with timestamps
- Track file modification times

### 3. Automatic Fix Script
Created `fix_brooks_plist.sh` to:
- Detect when KeepAlive is incorrectly set to true
- Automatically unload, fix, and reload the plist
- Log all actions for troubleshooting

### 4. Startup Fix Service
Created `com.india-ts.fix_plists_on_startup.plist` to:
- Run the fix script on system startup
- Ensure correct plist configuration after restarts

## Installation Steps

### 1. Install the fixed plist:
```bash
# Unload current plist
launchctl unload ~/Library/LaunchAgents/com.india-ts.brooks_reversal_simple.plist

# Copy the fixed version
cp /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.brooks_reversal_fixed.plist ~/Library/LaunchAgents/com.india-ts.brooks_reversal_simple.plist

# Load the fixed version
launchctl load ~/Library/LaunchAgents/com.india-ts.brooks_reversal_simple.plist
```

### 2. Install the startup fix service:
```bash
# Copy the startup fix plist
cp /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.fix_plists_on_startup.plist ~/Library/LaunchAgents/

# Load it
launchctl load ~/Library/LaunchAgents/com.india-ts.fix_plists_on_startup.plist
```

### 3. Set up monitoring (optional):
```bash
# Add to crontab to run every hour
crontab -e
# Add this line:
0 * * * * /Users/maverick/PycharmProjects/India-TS/Daily/scripts/monitor_plist_changes.sh
```

## Manual Fix Commands

If the issue occurs again, run:
```bash
/Users/maverick/PycharmProjects/India-TS/Daily/scripts/fix_brooks_plist.sh
```

## Verification Commands

Check current KeepAlive value:
```bash
plutil -p ~/Library/LaunchAgents/com.india-ts.brooks_reversal_simple.plist | grep -i keepalive
```

Check if service is running correctly:
```bash
launchctl list | grep brooks_reversal
```

View logs:
```bash
# Fix script logs
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/plist_fix.log

# Monitor script logs
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/plist_monitor.log

# Brooks scheduler logs
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/brooks_scheduler.log
```

## Prevention Tips

1. Always use the fixed plist template when making changes
2. Avoid force-quitting the Python scripts
3. Check logs regularly for any issues
4. Run the fix script after system updates

## If Problems Persist

1. Check system logs for launchd errors:
   ```bash
   log show --predicate 'subsystem == "com.apple.xpc.launchd"' --info --last 1h | grep brooks
   ```

2. Try using StartCalendarInterval instead of StartInterval
3. Consider using a different scheduling method (cron, etc.)

## Related Files
- `/Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.brooks_reversal_fixed.plist` - Fixed plist template
- `/Users/maverick/PycharmProjects/India-TS/Daily/scripts/fix_brooks_plist.sh` - Automatic fix script
- `/Users/maverick/PycharmProjects/India-TS/Daily/scripts/monitor_plist_changes.sh` - Monitoring script
- `/Users/maverick/PycharmProjects/India-TS/Daily/logs/plist_fix.log` - Fix script logs
- `/Users/maverick/PycharmProjects/India-TS/Daily/logs/plist_monitor.log` - Monitoring logs