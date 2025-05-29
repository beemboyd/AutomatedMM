# Scheduling GTT Stop-Loss Updates

This directory contains plist files for scheduling the CNC stop-loss updater scripts using launchd on macOS.

## How to Install the Scheduled Job

1. Copy the plist file to your LaunchAgents directory:

```bash
cp /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.update_cnc_stoploss.plist ~/Library/LaunchAgents/
```

2. Load the scheduled job with launchctl:

```bash
launchctl load ~/Library/LaunchAgents/com.india-ts.update_cnc_stoploss.plist
```

## Job Details

- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/scripts/update_cnc_stoploss.py`
- **Schedule**: Runs daily at 2:00 PM IST
- **Options**: `--force-place` (allows placing GTT orders outside market hours), `--refresh` (forces data refresh)
- **Description**: Fetches all CNC positions, calculates stop-loss levels based on previous day's low price, removes any existing GTT orders, and places new GTT stop-loss orders on Zerodha's server.

See [README_update_cnc_stoploss.md](README_update_cnc_stoploss.md) for detailed information about the script and its options.

## Managing the Job

- **Start the job immediately**:
  ```bash
  launchctl start com.india-ts.update_cnc_stoploss
  ```

- **Check job status**:
  ```bash
  launchctl list | grep india-ts
  ```

- **Unload/remove the job**:
  ```bash
  launchctl unload ~/Library/LaunchAgents/com.india-ts.update_cnc_stoploss.plist
  ```

- **View logs**:
  ```bash
  cat /Users/maverick/PycharmProjects/India-TS/logs/update_cnc_stoploss.log
  cat /Users/maverick/PycharmProjects/India-TS/logs/update_cnc_stoploss_error.log
  ```

## Modifying the Schedule

If you want to change the schedule:

1. Edit the plist file
2. Unload the current job
3. Load the updated plist file

## Test Run

You can test the script manually first with the dry-run flag:

```bash
/Users/maverick/PycharmProjects/India-TS/.venv/bin/python /Users/maverick/PycharmProjects/India-TS/Daily/scripts/update_cnc_stoploss.py --dry-run
```

To test placement outside market hours:

```bash
/Users/maverick/PycharmProjects/India-TS/.venv/bin/python /Users/maverick/PycharmProjects/India-TS/Daily/scripts/update_cnc_stoploss.py --dry-run --force-place
```

Then run it without the dry-run flag if everything looks good:

```bash
/Users/maverick/PycharmProjects/India-TS/.venv/bin/python /Users/maverick/PycharmProjects/India-TS/Daily/scripts/update_cnc_stoploss.py --force-place
```

To check the GTT orders that have been placed:

```bash
/Users/maverick/PycharmProjects/India-TS/.venv/bin/python /Users/maverick/PycharmProjects/India-TS/Daily/scripts/check_gtt_orders.py
```

## Troubleshooting

If the job doesn't run as expected:
1. Check the error log
2. Verify the paths in the plist file
3. Ensure the Python virtual environment is properly activated
4. Make sure the script has execution permissions