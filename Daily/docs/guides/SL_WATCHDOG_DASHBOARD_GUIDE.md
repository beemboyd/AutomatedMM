# SL Watchdog Dashboard Guide

## Overview
The SL Watchdog Dashboard is a web-based interface for monitoring and controlling the Stop Loss (SL) watchdog service. It provides real-time log viewing, user selection, and service control capabilities.

## Features

### 1. Real-time Log Viewer
- Displays the last 300 lines of SL watchdog logs
- Color-coded log entries for better readability:
  - 🔴 **Red**: Errors and stop loss triggers
  - 🟡 **Yellow**: Warnings (including 2% peak drop warnings)
  - 🟢 **Green**: Buy orders
  - 🔴 **Light Red**: Sell orders
  - ⚪ **Gray**: Debug information (ATR, trailing stops)

### 2. User Selection
- Dropdown menu to switch between different users
- Automatically detects available users from log directories
- Persists selected user across page refreshes

### 3. Service Control
- **Start Button**: Launch SL watchdog for selected user
- **Stop Button**: Terminate SL watchdog for selected user
- **Status Indicator**: Shows running/stopped state with visual indicator

### 4. Manual Refresh
- Refresh button to manually update logs
- More efficient than auto-refresh (reduces server load)
- Shows loading state during refresh

## Access Instructions

### Quick Start
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/dashboards
./start_sl_watchdog_dashboard.sh
```

### Manual Start
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/dashboards
python3 sl_watchdog_dashboard.py
```

### Access URL
Open your browser and navigate to: http://localhost:2001

## Usage Guide

### 1. Select User
- Use the dropdown menu at the top to select a user
- Dashboard will automatically load the latest logs for that user

### 2. View Logs
- Logs are displayed in reverse chronological order (newest first)
- Scroll through logs to see historical entries
- Log metadata shows file size and last modified time

### 3. Control Service
- **To Start**: Click "Start Watchdog" button
- **To Stop**: Click "Stop Watchdog" button
- Status indicator shows current state

### 4. Refresh Data
- Click the "🔄 Refresh" button to update logs
- Shows "⏳ Refreshing..." while loading
- Success/error messages appear at the top

## Technical Details

### Port Configuration
- Default port: **2001**
- Can be modified in `sl_watchdog_dashboard.py` if needed

### Log File Pattern
- Logs are located at: `/Daily/logs/{user}/SL_watchdog_*.log`
- Dashboard automatically finds the most recent log file

### Performance Optimization
- Reads only last 300 lines for efficiency
- Manual refresh instead of auto-refresh
- Lightweight Flask application

## Troubleshooting

### Dashboard Won't Start
```bash
# Check if port 2001 is in use
lsof -i :2001

# Kill existing process if needed
lsof -ti:2001 | xargs kill -9
```

### No Logs Showing
- Ensure SL watchdog has been run for the selected user
- Check if log files exist in `/Daily/logs/{user}/`
- Verify user has appropriate permissions

### Service Won't Start/Stop
- Check if orders file exists for the user
- Verify Python path and dependencies
- Check system logs for errors

## Integration with SL Watchdog

### 2% Peak Warning Feature
The dashboard displays special warnings when a position drops 2% from its peak value:
```
⚠️  TICKER: Price dropped 2.1% from peak!
```

This helps identify positions that may need attention before hitting the stop loss.

### Log Format
Logs follow the format:
```
YYYY-MM-DD HH:MM:SS,mmm - LEVEL - Message
```

Where LEVEL can be:
- INFO: General information
- WARNING: Important notifications
- ERROR: Critical issues
- DEBUG: Detailed tracking information

## Security Considerations
- Dashboard is read-only for log viewing
- Service control requires system permissions
- No authentication (assumes local access only)

## Related Documentation
- [Dashboard Quick Reference](/Daily/docs/dashboards/DASHBOARD_QUICK_REFERENCE.md)
- [SL Watchdog Service Documentation](/Daily/portfolio/README.md)
- [Trading System Overview](/Daily/docs/README.md)

---
Last Updated: 2025-07-24