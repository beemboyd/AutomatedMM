# India-TS System Startup Guide After Restart
**Created: 2025-08-13 16:37 IST**

## Quick Start Command
For a complete system startup, run:
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily
./pre_market_setup.sh
```

## Manual Startup Process (if pre_market_setup.sh fails)

### Step 1: Update Access Token (CRITICAL - Do this first!)
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily
python3 update_access_token.py --user Sai
```

### Step 2: Start Core Dashboards
Run these commands to start all dashboards:

```bash
# VSR Dashboard (Port 3001) - Main momentum tracker
cd /Users/maverick/PycharmProjects/India-TS/Daily/dashboards
./start_vsr_dashboard.sh

# Hourly Tracker Dashboard (Port 3002) - Long positions
./start_hourly_dashboard.sh

# Short Momentum Dashboard (Port 3003) - Short positions  
./start_short_momentum_dashboard.sh

# Hourly Short Tracker Dashboard (Port 3004) - Short hourly
./start_hourly_short_dashboard.sh

# Market Breadth Dashboard (Port 8080) - Market regime
cd /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime
./start_market_breadth_dashboard.sh
```

### Step 3: Run Morning Scanners
If scanners show 0 tickers, run these manually:

```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily

# Long scanners
python3 scanners/Long_Reversal_Daily.py
python3 scanners/Long_Reversal_Hourly.py

# Short scanners  
python3 scanners/Short_Reversal_Daily.py
python3 scanners/Short_Reversal_Hourly.py

# VSR Scanner
python3 scanners/VSR_Momentum_Scanner.py
```

### Step 4: Start Tracker Services
These services track ticker momentum throughout the day:

```bash
# Start via launchctl (recommended)
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-short-tracker-service.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.short-momentum-tracker.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-tracker-enhanced.plist
```

### Step 5: Start Alert Services
```bash
# VSR Telegram Alerts
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist

# Hourly Breakout Alerts (if needed)
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-breakout-alerts.plist
```

### Step 6: Verify Everything is Running
```bash
# Check dashboards
curl http://localhost:3001/api/tickers  # VSR Dashboard
curl http://localhost:3002/api/trending-tickers  # Hourly Tracker
curl http://localhost:3003/api/trending-tickers  # Short Momentum
curl http://localhost:3004/api/trending-tickers  # Hourly Short
curl http://localhost:8080/api/market-status  # Market Breadth

# Check services
launchctl list | grep "com.india-ts" | grep -v "^-"

# Check processes
ps aux | grep -E "vsr_telegram|tracker_service|momentum" | grep -v grep
```

## Dashboard URLs
After startup, access dashboards at:
- VSR Dashboard: http://localhost:3001
- Hourly Tracker: http://localhost:3002  
- Short Momentum: http://localhost:3003
- Hourly Short: http://localhost:3004
- Market Breadth: http://localhost:8080

## Common Issues & Solutions

### Issue: Dashboards show no tickers
**Solution:** Manually run the scanners (Step 3)

### Issue: Tracker services show wrong date in logs
**Solution:** Restart the services:
```bash
launchctl unload ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist
sleep 2
launchctl load ~/Library/LaunchAgents/com.india-ts.hourly-tracker-service.plist
```

### Issue: Telegram alerts not working
**Solution:** Check if VSR Telegram service is running:
```bash
ps aux | grep vsr_telegram | grep -v grep
# If not running, restart:
launchctl unload ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist
launchctl load ~/Library/LaunchAgents/com.india-ts.vsr-telegram-alerts-enhanced.plist
```

### Issue: Port already in use
**Solution:** Kill the process using the port:
```bash
# Find process
sudo lsof -i :PORT_NUMBER
# Kill it
kill -9 PID
```

## System Check Command
Run this to check all systems:
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily
./check_all_systems.sh
```

## Important Notes
1. **ALWAYS update access token first** - This is critical for API access
2. Dashboards may take 30-60 seconds to fully start
3. Scanners run automatically on schedule, but can be run manually if needed
4. VSR data updates every minute during market hours
5. Market breadth data updates at 6:30 PM daily

## Services That Start Automatically
These services should start automatically via launchctl after restart:
- Long/Short Reversal Daily scanners (9:00 AM)
- Market Breadth Scanner (every 30 minutes)
- SMA Breadth Historical Update (6:30 PM weekdays)

## Contact for Issues
If you encounter issues not covered here:
1. Check Activity.md for recent changes
2. Review logs in /Users/maverick/PycharmProjects/India-TS/Daily/logs/
3. Check service-specific logs in respective folders

---
**Last Updated:** 2025-08-13 16:37 IST by Claude