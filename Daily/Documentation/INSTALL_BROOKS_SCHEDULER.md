# Brooks Reversal Scheduler Installation Guide

This guide helps you set up the Al Brooks Higher Probability Reversal script to run automatically every 30 minutes during market hours (9:00 AM to 3:30 PM IST) on weekdays only.

## Files Created

1. **brooks_reversal_scheduler.py** - Python wrapper script that checks if it's market hours before running the main script
2. **com.india-ts.brooks_reversal_simple.plist** - Simple launchd configuration that runs every 30 minutes
3. **com.india-ts.brooks_reversal_30min.plist** - Alternative detailed plist with specific time slots (optional)

## Installation Steps

### Option 1: Using the Simple Scheduler (Recommended)

1. Make the scheduler script executable:
```bash
chmod +x /Users/maverick/PycharmProjects/India-TS/Daily/scripts/brooks_reversal_scheduler.py
```

2. Copy the plist to LaunchAgents:
```bash
cp /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.brooks_reversal_simple.plist ~/Library/LaunchAgents/
```

3. Load the scheduler:
```bash
launchctl load ~/Library/LaunchAgents/com.india-ts.brooks_reversal_simple.plist
```

### Option 2: Using the Detailed Scheduler

If you prefer more control over exact times:

```bash
cp /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.brooks_reversal_30min.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.india-ts.brooks_reversal_30min.plist
```

## Management Commands

### Check if the scheduler is running:
```bash
launchctl list | grep brooks_reversal
```

### Stop the scheduler:
```bash
launchctl unload ~/Library/LaunchAgents/com.india-ts.brooks_reversal_simple.plist
```

### Start the scheduler:
```bash
launchctl load ~/Library/LaunchAgents/com.india-ts.brooks_reversal_simple.plist
```

### Remove the scheduler:
```bash
launchctl unload ~/Library/LaunchAgents/com.india-ts.brooks_reversal_simple.plist
rm ~/Library/LaunchAgents/com.india-ts.brooks_reversal_simple.plist
```

## Monitoring

### Check logs:
```bash
# Main output log
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/brooks_reversal.log

# Error log
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/brooks_reversal_error.log

# Scheduler log (shows when it runs/skips)
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/brooks_scheduler.log
```

## How It Works

1. **Simple Scheduler Method**: 
   - Runs `brooks_reversal_scheduler.py` every 30 minutes
   - The Python script checks if it's a weekday and within market hours
   - Only executes the main Brooks script if conditions are met
   - Logs all activities including skipped runs

2. **Detailed Scheduler Method**:
   - Has specific time entries for each 30-minute slot
   - Includes weekday restrictions (1=Monday, 5=Friday)
   - More verbose but doesn't require the wrapper script

## Troubleshooting

1. **Script not running**: Check if Python path is correct:
```bash
which python3
```

2. **Permission issues**: Ensure scripts have execute permissions:
```bash
chmod +x /Users/maverick/PycharmProjects/India-TS/Daily/scripts/Al_Brooks_Higher_Probability_Reversal.py
chmod +x /Users/maverick/PycharmProjects/India-TS/Daily/scripts/brooks_reversal_scheduler.py
```

3. **View launchd errors**:
```bash
# Check system log for launchd errors
log show --predicate 'subsystem == "com.apple.xpc.launchd"' --info --last 1h | grep brooks
```

## Schedule Summary

- **Days**: Monday to Friday only
- **Hours**: 9:00 AM to 3:30 PM IST
- **Frequency**: Every 30 minutes
- **Total runs per day**: 14 times (9:00, 9:30, 10:00, ..., 3:00, 3:30)

The scheduler will automatically skip execution on weekends and outside market hours, saving system resources.