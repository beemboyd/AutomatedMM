# Zerodha Local Synchronization Scheduler

This plist file schedules the `synch_zerodha_local.py` script to run every 15 minutes during Indian market hours (9:15 AM to 3:30 PM IST) on weekdays.

## Installation

1. Copy the plist file to the LaunchAgents directory:
```bash
cp /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.synch_zerodha_local.plist ~/Library/LaunchAgents/
```

2. Load the launch agent:
```bash
launchctl load ~/Library/LaunchAgents/com.india-ts.synch_zerodha_local.plist
```

3. Verify it's loaded:
```bash
launchctl list | grep com.india-ts.synch_zerodha_local
```

## Schedule Details

- **Frequency**: Every 15 minutes
- **Days**: Monday to Friday (weekdays 1-5)
- **Time Range**: 9:15 AM to 3:30 PM IST
- **Total Runs**: 25 executions per trading day
- **Execution Times**:
  - 9:15, 9:30, 9:45 AM
  - 10:00, 10:15, 10:30, 10:45 AM
  - 11:00, 11:15, 11:30, 11:45 AM
  - 12:00, 12:15, 12:30, 12:45 PM
  - 1:00, 1:15, 1:30, 1:45 PM
  - 2:00, 2:15, 2:30, 2:45 PM
  - 3:00, 3:15, 3:30 PM

## Management Commands

### Start the scheduler:
```bash
launchctl load ~/Library/LaunchAgents/com.india-ts.synch_zerodha_local.plist
```

### Stop the scheduler:
```bash
launchctl unload ~/Library/LaunchAgents/com.india-ts.synch_zerodha_local.plist
```

### Restart the scheduler:
```bash
launchctl unload ~/Library/LaunchAgents/com.india-ts.synch_zerodha_local.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.synch_zerodha_local.plist
```

### Check if it's running:
```bash
launchctl list | grep com.india-ts.synch_zerodha_local
```

### View recent logs:
```bash
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/synch_zerodha_local.log
```

### Run manually for testing:
```bash
launchctl start com.india-ts.synch_zerodha_local
```

## Logs

All output (both stdout and stderr) is logged to:
`/Users/maverick/PycharmProjects/India-TS/Daily/logs/synch_zerodha_local.log`

## Important Notes

1. **Market Hours**: The script only runs during Indian market hours (9:15 AM - 3:30 PM IST) on weekdays
2. **Automatic Synchronization**: Ensures local orders files stay synchronized with Zerodha server CNC positions
3. **Multi-User Support**: The script automatically detects and synchronizes for all users with orders files
4. **Error Handling**: All errors are logged to the log file for debugging
5. **Non-Disruptive**: Regular synchronization prevents "Insufficient Holdings" errors in watchdog processes

## Troubleshooting

### If the job isn't running:
1. Check if it's loaded: `launchctl list | grep synch_zerodha_local`
2. Check system logs: `tail -f /var/log/system.log | grep synch_zerodha_local`
3. Verify Python path: `which python3`
4. Test script manually: `cd /Users/maverick/PycharmProjects/India-TS/Daily && python3 scripts/synch_zerodha_local.py`

### If getting permission errors:
```bash
chmod +x /Users/maverick/PycharmProjects/India-TS/Daily/scripts/synch_zerodha_local.py
```

### To remove completely:
```bash
launchctl unload ~/Library/LaunchAgents/com.india-ts.synch_zerodha_local.plist
rm ~/Library/LaunchAgents/com.india-ts.synch_zerodha_local.plist
```