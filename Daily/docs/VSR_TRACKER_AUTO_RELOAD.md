# VSR Tracker Auto-Reload Feature

## Overview
The VSR Enhanced Tracker now automatically checks for new Long_Reversal_Daily files every 5 minutes without requiring a service restart.

## How It Works

### File Check Interval
- **Check Frequency**: Every 5 minutes
- **Log Indicator**: `🔍 Checking for new Long_Reversal_Daily files...`
- **New File Detection**: `🆕 New Long_Reversal_Daily file detected: filename.xlsx`
- **New Tickers Alert**: `✨ New tickers found: TICKER1, TICKER2...`

### Implementation Details
1. The tracker maintains:
   - `last_ticker_file`: Path to the last loaded file
   - `last_file_check_time`: Timestamp of last check
   - `file_check_interval`: 300 seconds (5 minutes)

2. On each tracking cycle:
   - If 5 minutes have passed since last check, it looks for new files
   - If a newer Long_Reversal_Daily file exists, it loads the tickers
   - New tickers are highlighted in the logs

3. Benefits:
   - No service restart needed when new scan results arrive
   - Automatic detection of new tickers throughout the day
   - Minimal performance impact (only checks every 5 minutes)

## Example Log Output

```
2025-07-24 13:39:05,928 - INFO - [Sai] 🔍 Checking for new Long_Reversal_Daily files...
2025-07-24 13:39:05,929 - INFO - 🆕 New Long_Reversal_Daily file detected: Long_Reversal_Daily_20250724_131005.xlsx
2025-07-24 13:39:05,981 - INFO - ✨ New tickers found: VIJAYA, RAINBOW, NEWSTOCK
2025-07-24 13:39:05,981 - INFO - [Sai] Loaded 23 tickers from Long_Reversal_Daily_20250724_131005.xlsx
```

## Configuration
No additional configuration needed. The feature is built into the enhanced VSR tracker service.

## Monitoring
To verify the auto-reload is working:
1. Check logs for `🔍 Checking for new` messages every 5 minutes
2. Look for `🆕 New Long_Reversal_Daily file detected` when new scans complete
3. Watch for `✨ New tickers found` to see newly added stocks

## Impact on VSR Momentum Trading
When new tickers are detected:
1. They're immediately added to the tracking list
2. VSR scores are calculated in the next cycle
3. High-scoring new tickers become available for momentum trading
4. The VSR dashboard at port 3001 will show them within 1-2 minutes

---
*Last Updated: July 24, 2025*