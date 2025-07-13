# Market Breadth Scanner Schedule

## Status
✅ **SCHEDULED** - The Market Breadth Scanner is now scheduled to run automatically.

## Schedule Times (Monday - Friday)
The scanner runs every 30 minutes during market hours:

- 9:00 AM
- 9:30 AM
- 10:00 AM
- 10:30 AM
- 11:00 AM
- 11:30 AM
- 12:00 PM
- 12:30 PM
- 1:00 PM
- 1:30 PM
- 2:00 PM
- 2:30 PM
- 3:00 PM
- 3:30 PM

## Manual Commands

### Check Status
```bash
launchctl list | grep market_breadth_scanner
```

### Unload (Stop Scheduling)
```bash
launchctl unload /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.market_breadth_scanner.plist
```

### Reload (If Modified)
```bash
launchctl unload /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.market_breadth_scanner.plist
launchctl load /Users/maverick/PycharmProjects/India-TS/Daily/scheduler/com.india-ts.market_breadth_scanner.plist
```

### Run Manually
```bash
/Users/maverick/PycharmProjects/India-TS/.venv/bin/python /Users/maverick/PycharmProjects/India-TS/Daily/scanners/Market_Breadth_Scanner.py -u Sai
```

### Check Logs
```bash
# Scanner output
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/market_breadth_scanner.log

# Scanner errors
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/market_breadth_scanner_error.log
```

## Dashboard Access
The Market Breadth Dashboard automatically reads the latest scan data:
- URL: http://localhost:5001
- Auto-refresh: Every 2 minutes
- Data location: `/Daily/Market_Regime/breadth_data/market_breadth_latest.json`

## Notes
- Each scan takes approximately 3-4 minutes to complete (598 tickers)
- The scanner implements rate limiting (0.35s delay between tickers)
- If access token expires, some tickers may fail but the scan will continue
- Dashboard will display partial results if some tickers fail