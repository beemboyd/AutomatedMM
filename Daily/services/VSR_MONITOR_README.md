# VSR Real-Time Monitor Service

## Overview
The VSR Monitor Service continuously tracks stocks from the latest Long_Reversal_Daily file and alerts on Volume Spread Ratio (VSR) momentum opportunities using short timeframes (5-minute by default).

## Features
- **Real-time Monitoring**: Polls tickers every 5 minutes for momentum opportunities
- **Smart Alerts**: Only alerts when probability score exceeds threshold (default: 50)
- **Climax Detection**: Warns about buying/selling climaxes with divergences
- **Alert Cooldown**: Prevents spam by implementing 1-hour cooldown per ticker
- **HTML Dashboard**: Auto-updating dashboard shows recent alerts
- **Multi-user Support**: Can run separate instances for different users

## Usage

### Start the Service
```bash
./start_vsr_monitor.sh [-u USER] [-i INTERVAL] [-t THRESHOLD]

# Examples:
./start_vsr_monitor.sh                    # Default: User=Sai, Interval=5m, Threshold=50
./start_vsr_monitor.sh -u John -i 15m     # User John, 15-minute interval
./start_vsr_monitor.sh -t 70              # Only alert on high probability (≥70)
```

### Stop the Service
```bash
./stop_vsr_monitor.sh [-u USER]

# Examples:
./stop_vsr_monitor.sh          # Stop for default user (Sai)
./stop_vsr_monitor.sh -u John  # Stop for user John
```

### Check Status
```bash
./status_vsr_monitor.sh [-u USER]

# Examples:
./status_vsr_monitor.sh          # Check status for default user
./status_vsr_monitor.sh -u John  # Check status for user John
```

## Parameters
- **User (-u)**: User profile for API credentials (default: Sai)
- **Interval (-i)**: Timeframe for analysis - 5m, 15m, 30m (default: 5m)
- **Threshold (-t)**: Minimum probability score for alerts 0-100 (default: 50)

## Output Files

### Alerts Directory
`Daily/alerts/{USER}/vsr_monitor/`
- `vsr_alerts_YYYYMMDD.json`: Daily alert history
- `latest_alerts.json`: Recent alerts (last 2 hours)
- `vsr_monitor_dashboard.html`: Live dashboard (auto-refreshes every 30s)

### Logs Directory
`Daily/logs/{USER}/`
- `vsr_monitor_{USER}_YYYYMMDD.log`: Service logs

### PID Directory
`Daily/pids/`
- `vsr_monitor_{USER}.pid`: Process ID file

## Alert Structure
Each alert contains:
- Ticker and sector information
- Pattern type and probability score
- VSR metrics (ratio, ROC)
- Trading levels (entry, stop loss, targets)
- Climax indicators and divergences
- Timestamp and description

## Dashboard Features
- Real-time updates (refreshes every 30 seconds)
- Color-coded alerts by probability score
- Climax warnings highlighted
- Time-based filtering (shows last 2 hours)
- Direct links to trading levels

## Monitoring Logic
1. Reads tickers from latest Long_Reversal_Daily file
2. Fetches real-time data for each ticker
3. Calculates VSR indicators and patterns
4. Alerts if probability score ≥ threshold
5. Implements cooldown to prevent alert spam
6. Updates dashboard with latest alerts

## Best Practices
- Run during market hours for real-time opportunities
- Use 5m interval for day trading, 15m for swing trading
- Set threshold based on risk tolerance (50-70 recommended)
- Monitor dashboard for consolidated view of opportunities
- Check logs for detailed analysis information

## Troubleshooting
- Service won't start: Check if already running with status command
- No alerts: Lower threshold or check if Long_Reversal_Daily file exists
- API errors: Verify credentials in config.ini
- Dashboard not updating: Check if service is running

## Example Workflow
```bash
# 1. Start monitoring with high probability alerts
./start_vsr_monitor.sh -t 60

# 2. Check status
./status_vsr_monitor.sh

# 3. View dashboard in browser
# Open the dashboard URL shown in status output

# 4. Monitor logs in real-time
tail -f ../logs/Sai/vsr_monitor_Sai_$(date +%Y%m%d).log

# 5. Stop at end of day
./stop_vsr_monitor.sh
```