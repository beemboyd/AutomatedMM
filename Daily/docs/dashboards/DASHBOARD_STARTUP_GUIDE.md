# India-TS Dashboard Startup Guide

This guide explains how to start and manage the India-TS dashboards.

## Overview

India-TS has two main dashboards:

1. **Main Market Regime Dashboard** - Port 8080
   - Full market analysis and visualizations
   - Real-time regime tracking
   - Historical trends and metrics

2. **System Health Dashboard** - Port 7080
   - System health monitoring
   - India-TS jobs status
   - Scanner and analysis status

## Quick Start

### Start Both Dashboards (Recommended)
```bash
# Load the dashboard jobs
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist
```

### Access the Dashboards
- Main Dashboard: http://localhost:8080
- Health Dashboard: http://localhost:7080

## Detailed Instructions

### 1. Starting the Main Market Regime Dashboard (Port 8080)

#### Option A: Using LaunchAgent (Persistent - Recommended)
```bash
# Load the service
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist

# Verify it's running
launchctl list | grep market_regime_dashboard
lsof -i :8080
```

#### Option B: Manual Start (Temporary)
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime
python3 dashboard_enhanced.py
```

### 2. Starting the Health Dashboard (Port 7080)

#### Option A: Using LaunchAgent (Persistent - Recommended)
```bash
# Load the service
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist

# Verify it's running
launchctl list | grep health_dashboard
lsof -i :7080
```

#### Option B: Manual Start (Temporary)
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime
python3 dashboard_health_check.py
```

## Managing Dashboards

### Check Dashboard Status
```bash
# Check if dashboards are loaded
launchctl list | grep -E "market_regime_dashboard|health_dashboard"

# Check if ports are in use
lsof -i :8080  # Main dashboard
lsof -i :7080  # Health dashboard

# Check running Python processes
ps aux | grep -E "dashboard_enhanced|dashboard_health_check" | grep -v grep
```

### Stop Dashboards
```bash
# Stop main dashboard
launchctl unload /Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist

# Stop health dashboard
launchctl unload /Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist
```

### Restart Dashboards
```bash
# Restart main dashboard
launchctl unload /Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist
sleep 1
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist

# Restart health dashboard
launchctl unload /Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist
sleep 1
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist
```

## After System Reboot

The dashboards are configured with `RunAtLoad` and `KeepAlive`, so they should start automatically after reboot. However, if they don't:

```bash
# Load all India-TS jobs including dashboards
/Users/maverick/PycharmProjects/India-TS/Daily/utils/load_all_jobs.sh

# Or load just the dashboards
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist
```

## Troubleshooting

### Dashboard Not Starting

1. **Check error logs:**
```bash
# Main dashboard logs
tail -50 /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/logs/dashboard_error.log

# Health dashboard logs
tail -50 /Users/maverick/PycharmProjects/India-TS/logs/health_dashboard_error.log
```

2. **Port already in use:**
```bash
# Find what's using the port
lsof -i :8080  # or :7080

# Kill the process if needed
kill -9 <PID>
```

3. **Python path issues:**
```bash
# Check Python installation
which python3
/usr/local/bin/python3 --version
```

4. **Permission issues:**
```bash
# Check file permissions
ls -la /Users/maverick/Library/LaunchAgents/com.india-ts.*.plist
```

### Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| Port already in use | Kill existing process: `kill -9 $(lsof -ti :8080)` |
| Dashboard not loading | Check if plist is loaded: `launchctl list \| grep dashboard` |
| No data showing | Ensure market regime analyzer is running |
| Jobs not showing (Health Dashboard) | Restart the health dashboard |

## Dashboard Features

### Main Dashboard (Port 8080)
- **Real-time Updates**: Refreshes every 30 seconds
- **Market Regime Display**: Current regime with confidence
- **Trend Analysis**: Market, trend, and volatility scores
- **Historical Charts**: 24-hour metric history
- **Scanner Results**: Long/short reversal counts
- **Pattern Distribution**: Visual breakdown of detected patterns

### Health Dashboard (Port 7080)
- **System Status**: Scanner and regime analysis health
- **Job Monitoring**: All 13 India-TS jobs with status
- **Schedule Tracking**: Shows completed/missed runs
- **Real-time Alerts**: System issues and warnings
- **Job Summary**: Running, successful, and error counts

## Configuration Files

### Main Dashboard
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/dashboard_enhanced.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist`
- **Port**: 8080

### Health Dashboard
- **Script**: `/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/dashboard_health_check.py`
- **Plist**: `/Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist`
- **Port**: 7080

## Best Practices

1. **Always use LaunchAgent** for production - it ensures dashboards restart on failure
2. **Check logs regularly** for any errors or warnings
3. **Monitor both dashboards** during market hours for complete system visibility
4. **Restart dashboards** if they become unresponsive
5. **Keep ports consistent** - don't change default ports unless necessary

## Quick Reference Card

```bash
# Start everything
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist
launchctl load /Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist

# Check status
launchctl list | grep dashboard
lsof -i :8080
lsof -i :7080

# Access dashboards
open http://localhost:8080  # Main dashboard
open http://localhost:7080  # Health dashboard

# Stop everything
launchctl unload /Users/maverick/Library/LaunchAgents/com.india-ts.market_regime_dashboard.plist
launchctl unload /Users/maverick/Library/LaunchAgents/com.india-ts.health_dashboard.plist
```

---

Last Updated: 2025-07-04